# Futebol_Alertas_Ligas_Especificas_Corrigido.py
import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# CONFIGURAÇÕES
# =============================
API_KEY_FD = "9058de85e3324bdb969adc005b5d918a"  # football-data.org
HEADERS_FD = {"X-Auth-Token": API_KEY_FD}
BASE_URL_FD = "https://api.football-data.org/v4"

# API-Football (RapidAPI) como fallback - CADASTRE-SE EM: https://rapidapi.com/api-sports/api/api-football/
API_FOOTBALL_KEY = "sua_chave_aqui"  # Obtenha em rapidapi.com
HEADERS_API_FOOTBALL = {
    "X-RapidAPI-Key": API_FOOTBALL_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}
BASE_URL_API_FOOTBALL = "https://api-football-v1.p.rapidapi.com/v3"

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

# =============================
# LIGAS ESPECÍFICAS (IDs CORRETOS)
# =============================
LIGAS_ESPECIFICAS = {
    "MLS (EUA/Canadá)": {"fd_id": 214, "api_football_id": 253},    # MLS
    "Liga MX (México)": {"fd_id": 2032, "api_football_id": 262},   # Liga MX
    "Série B (Brasil)": {"fd_id": 2022, "api_football_id": 73},    # Brazilian Serie B
    "Liga Árabe (Arábia Saudita)": {"fd_id": 2079, "api_football_id": 307}  # Saudi Pro League
}

# =============================
# Funções de persistência / cache em disco
# =============================
def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_alertas():
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos():
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao():
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode":"Markdown"})
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")

def enviar_alerta_telegram_generico(home, away, data_str_brt, hora_str, liga, tendencia, estimativa, confianca, chat_id=TELEGRAM_CHAT_ID):
    msg = (
        f"⚽ *Alerta de Gols!*\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_str_brt} ⏰ {hora_str} (BRT)\n"
        f"🔥 Tendência: {tendencia}\n"
        f"📊 Estimativa: {estimativa:.2f} gols\n"
        f"✅ Confiança: {confianca:.0f}%\n"
        f"📌 Liga: {liga}"
    )
    enviar_telegram(msg, chat_id)

# =============================
# API-Football (RapidAPI) - FALLBACK PRINCIPAL
# =============================
def obter_classificacao_api_football(liga_id):
    cache = carregar_cache_classificacao()
    cache_key = f"api_fb_{liga_id}"
    
    if cache_key in cache:
        cache_time_str = cache[cache_key].get("cache_time")
        if cache_time_str:
            try:
                cache_time = datetime.fromisoformat(cache_time_str)
                if datetime.now() - cache_time < timedelta(hours=6):
                    return cache[cache_key].get("standings", {})
            except:
                pass
    
    try:
        url = f"{BASE_URL_API_FOOTBALL}/standings"
        params = {"season": "2024", "league": liga_id}  # Ajuste o season conforme necessário
        resp = requests.get(url, headers=HEADERS_API_FOOTBALL, params=params, timeout=10)
        
        if resp.status_code != 200:
            st.warning(f"Erro API-Football standings: {resp.status_code}")
            return {}
            
        data = resp.json()
        standings = {}
        
        if data.get("response"):
            for standing_data in data["response"]:
                standings_list = standing_data.get("league", {}).get("standings", [])
                for standing_group in standings_list:
                    for team in standing_group:
                        name = team.get("team", {}).get("name")
                        if name:
                            goals = team.get("goals", {})
                            played = team.get("all", {}).get("played", 1)
                            standings[name] = {
                                "scored": goals.get("for", 0),
                                "against": goals.get("against", 0),
                                "played": played
                            }
        
        cache[cache_key] = {
            "standings": standings,
            "cache_time": datetime.now().isoformat()
        }
        salvar_cache_classificacao(cache)
        return standings
        
    except Exception as e:
        st.warning(f"Erro obter classificação API-Football para liga {liga_id}: {e}")
        return {}

def obter_jogos_api_football(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"api_fb_{liga_id}_{data}"
    
    if key in cache:
        return cache[key]
    
    try:
        url = f"{BASE_URL_API_FOOTBALL}/fixtures"
        params = {"date": data, "league": liga_id, "season": "2024"}
        resp = requests.get(url, headers=HEADERS_API_FOOTBALL, params=params, timeout=10)
        
        if resp.status_code != 200:
            st.warning(f"Erro API-Football fixtures: {resp.status_code}")
            return []
            
        data_json = resp.json()
        jogos = data_json.get("response", [])
        cache[key] = jogos
        salvar_cache_jogos(cache)
        return jogos
        
    except Exception as e:
        st.warning(f"Erro obter jogos API-Football para liga {liga_id}: {e}")
        return []

# =============================
# Football-Data.org (Tentativa Inicial)
# =============================
def obter_classificacao_fd(liga_id):
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
        resp = requests.get(url, headers=HEADERS_FD, timeout=10)
        
        if resp.status_code == 403:
            st.warning(f"Liga {liga_id} não disponível no plano gratuito do Football-Data")
            return None
        elif resp.status_code == 404:
            st.warning(f"Liga {liga_id} não encontrada no Football-Data")
            return None
            
        resp.raise_for_status()
        data = resp.json()
        standings = {}
        
        for s in data.get("standings", []):
            if s.get("type") != "TOTAL":
                continue
            for t in s.get("table", []):
                name = t["team"]["name"]
                gols_marcados = t.get("goalsFor", 0)
                gols_sofridos = t.get("goalsAgainst", 0)
                partidas = t.get("playedGames", 1) or 1
                standings[name] = {
                    "scored": gols_marcados,
                    "against": gols_sofridos,
                    "played": partidas
                }
        return standings
        
    except Exception as e:
        st.warning(f"Erro Football-Data classificacao {liga_id}: {e}")
        return None

def obter_jogos_fd(liga_id, data):
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/matches"
        params = {"dateFrom": data, "dateTo": data}
        resp = requests.get(url, headers=HEADERS_FD, params=params, timeout=10)
        
        if resp.status_code == 403:
            return None
        elif resp.status_code == 404:
            return None
            
        resp.raise_for_status()
        jogos = resp.json().get("matches", [])
        return jogos
        
    except Exception as e:
        st.warning(f"Erro Football-Data jogos {liga_id}: {e}")
        return None

# =============================
# Sistema Híbrido (Tenta FD primeiro, depois API-Football)
# =============================
def obter_classificacao_hibrido(liga_info):
    # Primeiro tenta Football-Data
    if liga_info.get("fd_id"):
        classificacao = obter_classificacao_fd(liga_info["fd_id"])
        if classificacao is not None:
            return classificacao, "FD"
    
    # Fallback para API-Football
    if liga_info.get("api_football_id"):
        classificacao = obter_classificacao_api_football(liga_info["api_football_id"])
        if classificacao:
            return classificacao, "API_FB"
    
    return {}, "NENHUM"

def obter_jogos_hibrido(liga_info, data):
    # Primeiro tenta Football-Data
    if liga_info.get("fd_id"):
        jogos = obter_jogos_fd(liga_info["fd_id"], data)
        if jogos is not None:
            return jogos, "FD"
    
    # Fallback para API-Football
    if liga_info.get("api_football_id"):
        jogos = obter_jogos_api_football(liga_info["api_football_id"], data)
        if jogos:
            return jogos, "API_FB"
    
    return [], "NENHUM"

# =============================
# Tendência (Adaptada para múltiplas fontes)
# =============================
def calcular_tendencia(home, away, classificacao):
    if not classificacao:
        return 2.5, 60, "Mais 2.5"  # Fallback padrão
    
    dados_home = classificacao.get(home, {"scored":0, "against":0, "played":1})
    dados_away = classificacao.get(away, {"scored":0, "against":0, "played":1})

    media_home_feitos = dados_home["scored"] / max(1, dados_home["played"])
    media_home_sofridos = dados_home["against"] / max(1, dados_home["played"])
    media_away_feitos = dados_away["scored"] / max(1, dados_away["played"])
    media_away_sofridos = dados_away["against"] / max(1, dados_away["played"])

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0)*10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0)*10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa)*10)

    return round(estimativa, 2), round(confianca, 0), tendencia

# =============================
# Função para tratar tempo e formatar data/hora (BRT)
# =============================
def parse_time_iso_to_brt(iso_str):
    if not iso_str:
        return "-", "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_brt = dt - timedelta(hours=3)
        return dt_brt.strftime("%d/%m/%Y"), dt_brt.strftime("%H:%M")
    except Exception:
        return "-", "-"

def parse_time_api_football(fixture_data):
    try:
        date_str = fixture_data.get("fixture", {}).get("date", "")
        if date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            dt_brt = dt - timedelta(hours=3)
            return dt_brt.strftime("%d/%m/%Y"), dt_brt.strftime("%H:%M")
    except:
        pass
    return "-", "-"

# =============================
# UI e Lógica principal
# =============================
st.set_page_config(page_title="⚽ Alertas - MLS, Liga MX, Série B, Liga Árabe", layout="wide")
st.title("⚽ Sistema de Alertas - Ligas Específicas")
st.markdown("**Ligas disponíveis:** MLS (EUA/Canadá), Liga MX (México), Série B (Brasil), Liga Árabe (Arábia Saudita)")

# Configuração da API
st.sidebar.header("🔧 Configuração da API")
st.sidebar.info("""
**Para usar todas as ligas:**
1. Cadastre-se em [RapidAPI](https://rapidapi.com/api-sports/api/api-football/)
2. Obtenha sua chave API
3. Cole abaixo
""")

api_football_key = st.sidebar.text_input("Chave API-Football (RapidAPI):", value=API_FOOTBALL_KEY, type="password")
if api_football_key != "sua_chave_aqui":
    HEADERS_API_FOOTBALL["X-RapidAPI-Key"] = api_football_key

# Data
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Seleção de ligas
st.sidebar.header("🏆 Ligas para Análise")
ligas_selecionadas = st.sidebar.multiselect(
    "Selecione as ligas:",
    options=list(LIGAS_ESPECIFICAS.keys()),
    default=list(LIGAS_ESPECIFICAS.keys())
)

# Botões principais
st.markdown("---")
col1, col2 = st.columns([1,1])
with col1:
    buscar_btn = st.button("🔍 Buscar partidas e analisar")
with col2:
    conferir_btn = st.button("📊 Conferir resultados")

# =================================================================================
# Buscar partidas - SISTEMA HÍBRIDO
# =================================================================================
if buscar_btn:
    if not ligas_selecionadas:
        st.error("⚠️ Selecione pelo menos uma liga para análise.")
    else:
        st.info(f"Buscando partidas para {data_str}...")
        total_top_jogos = []
        stats_api = {"FD": 0, "API_FB": 0, "NENHUM": 0}

        for liga_nome in ligas_selecionadas:
            liga_info = LIGAS_ESPECIFICAS[liga_nome]
            
            # Obter dados via sistema híbrido
            classificacao, fonte_class = obter_classificacao_hibrido(liga_info)
            jogos, fonte_jogos = obter_jogos_hibrido(liga_info, data_str)
            
            stats_api[fonte_class] += 1
            
            if not jogos:
                st.warning(f"⚠️ Nenhum jogo encontrado para *{liga_nome}* em {data_str}")
                continue

            st.header(f"🏆 {liga_nome} ({len(jogos)} jogos) - Fonte: {fonte_jogos}")
            
            for jogo in jogos:
                # Processar conforme a fonte dos dados
                if fonte_jogos == "FD":
                    home = jogo.get("homeTeam", {}).get("name", "Desconhecido")
                    away = jogo.get("awayTeam", {}).get("name", "Desconhecido")
                    utc = jogo.get("utcDate")
                    data_brt, hora_brt = parse_time_iso_to_brt(utc)
                    jogo_id = str(jogo.get("id"))
                    
                else:  # API-Football
                    home = jogo.get("teams", {}).get("home", {}).get("name", "Desconhecido")
                    away = jogo.get("teams", {}).get("away", {}).get("name", "Desconhecido")
                    data_brt, hora_brt = parse_time_api_football(jogo)
                    jogo_id = str(jogo.get("fixture", {}).get("id"))
                
                # Calcular tendência
                estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)
                
                # Enviar alerta no Telegram
                enviar_alerta_telegram_generico(home, away, data_brt, hora_brt, liga_nome, tendencia, estimativa, confianca)
                
                # Adicionar à lista de top jogos
                total_top_jogos.append({
                    "id": jogo_id,
                    "home": home, 
                    "away": away,
                    "tendencia": tendencia, 
                    "estimativa": estimativa, 
                    "confianca": confianca,
                    "liga": liga_nome,
                    "hora": hora_brt,
                    "fonte": fonte_jogos
                })
                
                # Exibir no Streamlit
                emoji_fonte = "🔵" if fonte_jogos == "FD" else "🟢"
                st.write(f"{emoji_fonte} {hora_brt} | {home} x {away} — {tendencia} ({confianca}%)")

        # Estatísticas de uso das APIs
        st.sidebar.markdown("---")
        st.sidebar.header("📊 Estatísticas API")
        st.sidebar.write(f"Football-Data: {stats_api['FD']}")
        st.sidebar.write(f"API-Football: {stats_api['API_FB']}")
        st.sidebar.write(f"Sem dados: {stats_api['NENHUM']}")

        # Ordenar e exibir top jogos
        if total_top_jogos:
            top_sorted = sorted(total_top_jogos, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:5]
            
            st.markdown("## 🏆 Top 5 Jogos Recomendados")
            mensagem = "📢 *TOP 5 Jogos Consolidados*\n\n"
            
            for i, jogo in enumerate(top_sorted, 1):
                st.success(f"{i}º 🏟️ {jogo['home']} x {jogo['away']} — {jogo['tendencia']} | Conf: {jogo['confianca']}%")
                mensagem += f"{i}º 🏟️ {jogo['liga']}\n🏆 {jogo['home']} x {jogo['away']}\nTendência: {jogo['tendencia']} | Conf.: {jogo['confianca']}%\n\n"
            
            # Enviar top 5 para canal alternativo
            enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)
            st.success("✅ Top 5 jogos enviados para canal alternativo.")
            
            # Salvar alertas
            alertas = carregar_alertas()
            for jogo in total_top_jogos:
                alertas[jogo["id"]] = {
                    "home": jogo["home"],
                    "away": jogo["away"], 
                    "tendencia": jogo["tendencia"],
                    "estimativa": jogo["estimativa"],
                    "confianca": jogo["confianca"],
                    "liga": jogo["liga"],
                    "data": data_str,
                    "hora": jogo["hora"],
                    "fonte": jogo["fonte"],
                    "conferido": False
                }
            salvar_alertas(alertas)
        else:
            st.error("❌ Nenhum jogo encontrado para as ligas selecionadas.")

# =================================================================================
# Conferência de resultados (restante do código mantido similar)
# =================================================================================
if conferir_btn:
    st.info("Conferindo resultados dos alertas salvos...")
    alertas = carregar_alertas()
    
    if not alertas:
        st.info("Nenhum alerta salvo para conferência.")
    else:
        mudou = False
        jogos_para_conferir = {k: v for k, v in alertas.items() if not v.get("conferido", False)}
        
        if not jogos_para_conferir:
            st.info("Todos os alertas já foram conferidos.")
        else:
            for fixture_id, info in jogos_para_conferir.items():
                try:
                    # Tentar buscar pela fonte original
                    fonte = info.get("fonte", "FD")
                    
                    if fonte == "FD":
                        url = f"{BASE_URL_FD}/matches/{fixture_id}"
                        resp = requests.get(url, headers=HEADERS_FD, timeout=10)
                    else:
                        url = f"{BASE_URL_API_FOOTBALL}/fixtures"
                        params = {"id": fixture_id}
                        resp = requests.get(url, headers=HEADERS_API_FOOTBALL, params=params, timeout=10)
                    
                    if resp.status_code == 200:
                        jogo = resp.json()
                        
                        if fonte == "FD":
                            home = jogo.get("homeTeam", {}).get("name", "Desconhecido")
                            away = jogo.get("awayTeam", {}).get("name", "Desconhecido")
                            status = jogo.get("status", "DESCONHECIDO")
                            score = jogo.get("score", {})
                            full_time = score.get("fullTime", {})
                            gols_home = full_time.get("home")
                            gols_away = full_time.get("away")
                        else:
                            jogo_data = jogo.get("response", [{}])[0] if jogo.get("response") else {}
                            home = jogo_data.get("teams", {}).get("home", {}).get("name", "Desconhecido")
                            away = jogo_data.get("teams", {}).get("away", {}).get("name", "Desconhecido")
                            status = jogo_data.get("fixture", {}).get("status", {}).get("short", "DESCONHECIDO")
                            score = jogo_data.get("goals", {})
                            gols_home = score.get("home")
                            gols_away = score.get("away")
                        
                        placar = f"{gols_home} x {gols_away}" if (gols_home is not None and gols_away is not None) else "-"
                        total_gols = (gols_home or 0) + (gols_away or 0)
                        
                        # Determinar resultado
                        tendencia = info.get("tendencia", "")
                        if status in ("FINISHED", "FT", "Match Finished"):
                            if "2.5" in tendencia:
                                resultado = "🟢 GREEN" if total_gols > 2 else "🔴 RED"
                            elif "1.5" in tendencia:
                                resultado = "🟢 GREEN" if total_gols > 1 else "🔴 RED"
                            else:
                                resultado = "Menos 2.5"
                        else:
                            resultado = "⏳ Aguardando"

                        # Exibir resultado
                        bg_color = "#1e4620" if "GREEN" in resultado else "#5a1e1e" if "RED" in resultado else "#2c2c2c"
                        
                        st.markdown(f"""
                        <div style="border:1px solid #444; border-radius:10px; padding:12px; margin-bottom:10px;
                                    background-color:{bg_color}; font-size:15px; color:#f1f1f1;">
                            <b>🏟️ {home} vs {away}</b><br>
                            📌 Status: <b>{status}</b><br>
                            ⚽ Tendência: <b>{tendencia}</b> | Estim.: {info.get('estimativa','-')} | Conf.: {info.get('confianca','-')}%<br>
                            📊 Placar: <b>{placar}</b><br>
                            ✅ Resultado: {resultado}
                        </div>
                        """, unsafe_allow_html=True)

                        # Marcar como conferido se finalizado
                        if status in ("FINISHED", "FT", "Match Finished"):
                            info["conferido"] = True
                            info["resultado"] = resultado
                            info["placar_final"] = placar
                            info["total_gols"] = total_gols
                            mudou = True
                            
                except Exception as e:
                    st.warning(f"Erro ao conferir jogo {fixture_id}: {e}")

            if mudou:
                salvar_alertas(alertas)
                st.success("✅ Status dos alertas atualizados!")

# =================================================================================
# Relatório PDF (código similar ao anterior)
# =================================================================================
# ... (manter o mesmo código do relatório PDF do exemplo anterior)

st.sidebar.markdown("---")
st.sidebar.header("💡 Instruções")
st.sidebar.info("""
1. **Para todas as ligas**: Use API-Football (RapidAPI)
2. **Plano gratuito**: 100 requisições/dia
3. **Cadastro**: rapidapi.com/api-sports/api/api-football/
""")
