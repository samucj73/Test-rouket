# Futebol_Alertas_Ligas_Especificas.py
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

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

# =============================
# LIGAS ESPECÍFICAS (IDs da Football-Data)
# =============================
LIGAS_ESPECIFICAS = {
    "MLS (EUA/Canadá)": 214,           # Major League Soccer
    "Liga MX (México)": 2032,          # Liga MX
    "Série B (Brasil)": 2022,          # Campeonato Brasileiro Série B
    "Liga Árabe (Arábia Saudita)": 2079  # Saudi Professional League
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
# Football-Data helpers
# =============================
def obter_classificacao_fd(liga_id):
    cache = carregar_cache_classificacao()
    cache_key = f"fd_{liga_id}"
    
    if cache_key in cache:
        # Verificar se o cache não está muito antigo (max 6 horas)
        cache_time_str = cache[cache_key].get("cache_time")
        if cache_time_str:
            try:
                cache_time = datetime.fromisoformat(cache_time_str)
                if datetime.now() - cache_time < timedelta(hours=6):
                    return cache[cache_key].get("standings", {})
            except:
                pass
    
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
        resp = requests.get(url, headers=HEADERS_FD, timeout=10)
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
        
        # Salvar no cache com timestamp
        cache[cache_key] = {
            "standings": standings,
            "cache_time": datetime.now().isoformat()
        }
        salvar_cache_classificacao(cache)
        return standings
        
    except Exception as e:
        st.warning(f"Erro obter classificação FD para liga {liga_id}: {e}")
        return {}

def obter_jogos_fd(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"fd_{liga_id}_{data}"
    
    if key in cache:
        return cache[key]
    
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        resp = requests.get(url, headers=HEADERS_FD, timeout=10)
        resp.raise_for_status()
        jogos = resp.json().get("matches", [])
        cache[key] = jogos
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.warning(f"Erro obter jogos FD para liga {liga_id}: {e}")
        return []

# =============================
# Tendência (Football-Data)
# =============================
def calcular_tendencia_fd(home, away, classificacao):
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

# =============================
# UI e Lógica principal
# =============================
st.set_page_config(page_title="⚽ Alertas - MLS, Liga MX, Série B, Liga Árabe", layout="wide")
st.title("⚽ Sistema de Alertas - Ligas Específicas")
st.markdown("**Ligas disponíveis:** MLS (EUA/Canadá), Liga MX (México), Série B (Brasil), Liga Árabe (Arábia Saudita)")

# Data
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Seleção de ligas
st.sidebar.header("Configurações das Ligas")
ligas_selecionadas = st.sidebar.multiselect(
    "Selecione as ligas para análise:",
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
# Buscar partidas
# =================================================================================
if buscar_btn:
    if not ligas_selecionadas:
        st.error("⚠️ Selecione pelo menos uma liga para análise.")
    else:
        st.info(f"Buscando partidas para {data_str} nas ligas selecionadas...")
        total_top_jogos = []

        for liga_nome in ligas_selecionadas:
            liga_id = LIGAS_ESPECIFICAS[liga_nome]
            
            # Obter classificação e jogos
            classificacao = obter_classificacao_fd(liga_id)
            jogos_fd = obter_jogos_fd(liga_id, data_str)
            
            if not jogos_fd:
                st.write(f"⚠️ Nenhum jogo encontrado para *{liga_nome}* em {data_str}")
                continue

            st.header(f"🏆 {liga_nome} ({len(jogos_fd)} jogos)")
            
            for jogo in jogos_fd:
                home = jogo.get("homeTeam", {}).get("name", "Desconhecido")
                away = jogo.get("awayTeam", {}).get("name", "Desconhecido")
                utc = jogo.get("utcDate")
                data_brt, hora_brt = parse_time_iso_to_brt(utc)
                
                # Calcular tendência
                estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
                
                # Enviar alerta no Telegram
                enviar_alerta_telegram_generico(home, away, data_brt, hora_brt, liga_nome, tendencia, estimativa, confianca)
                
                # Adicionar à lista de top jogos
                total_top_jogos.append({
                    "id": str(jogo.get("id")),
                    "home": home, 
                    "away": away,
                    "tendencia": tendencia, 
                    "estimativa": estimativa, 
                    "confianca": confianca,
                    "liga": liga_nome,
                    "hora": hora_brt
                })
                
                # Exibir no Streamlit
                st.write(f"⚽ {hora_brt} | {home} x {away} — {tendencia} ({confianca}%)")

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
                    "conferido": False
                }
            salvar_alertas(alertas)

# =================================================================================
# Conferência de resultados
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
                    # Buscar dados atualizados do jogo
                    url = f"{BASE_URL_FD}/matches/{fixture_id}"
                    resp = requests.get(url, headers=HEADERS_FD, timeout=10)
                    
                    if resp.status_code == 200:
                        jogo = resp.json()
                        
                        home = jogo.get("homeTeam", {}).get("name", "Desconhecido")
                        away = jogo.get("awayTeam", {}).get("name", "Desconhecido")
                        status = jogo.get("status", "DESCONHECIDO")
                        
                        # Obter placar
                        score = jogo.get("score", {})
                        full_time = score.get("fullTime", {})
                        gols_home = full_time.get("home")
                        gols_away = full_time.get("away")
                        
                        placar = f"{gols_home} x {gols_away}" if (gols_home is not None and gols_away is not None) else "-"
                        total_gols = (gols_home or 0) + (gols_away or 0)
                        
                        # Determinar resultado
                        tendencia = info.get("tendencia", "")
                        if status == "FINISHED":
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
                        if status == "FINISHED":
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
# Relatório PDF dos jogos conferidos
# =================================================================================
st.markdown("---")
st.header("📊 Relatório de Jogos Conferidos")

alertas_salvos = carregar_alertas()
jogos_conferidos = []

for fixture_id, info in alertas_salvos.items():
    if info.get("conferido"):
        # Abreviar nomes longos
        def abreviar_nome(nome, max_len=15):
            if not nome or len(nome) <= max_len:
                return nome
            palavras = nome.split()
            abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
            return abreviado[:max_len] + "..." if len(abreviado) > max_len else abreviado

        home = abreviar_nome(info.get("home", ""))
        away = abreviar_nome(info.get("away", ""))
        
        jogos_conferidos.append([
            f"{home} vs {away}",
            info.get("tendencia", "-"),
            f"{info.get('estimativa', 0):.2f}",
            f"{info.get('confianca', 0):.0f}%",
            info.get("placar_final", "-"),
            info.get("resultado", "-"),
            info.get("data", "-")
        ])

if jogos_conferidos:
    df_conferidos = pd.DataFrame(jogos_conferidos, columns=[
        "Jogo", "Tendência", "Estimativa", "Confiança", "Placar", "Resultado", "Data"
    ])

    # Criar PDF
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, 
                          rightMargin=20, leftMargin=20, 
                          topMargin=20, bottomMargin=20)
    
    data_table = [df_conferidos.columns.tolist()] + df_conferidos.values.tolist()
    table = Table(data_table, repeatRows=1, 
                 colWidths=[120, 70, 60, 60, 50, 70, 80])
    
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4B4B4B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F5F5F5")),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ])
    
    # Adicionar cores alternadas
    for i in range(1, len(data_table)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0,i), (-1,i), colors.HexColor("#E0E0E0"))
    
    table.setStyle(style)
    pdf.build([table])
    buffer.seek(0)
    
    st.download_button(
        label="📄 Baixar Relatório em PDF",
        data=buffer,
        file_name=f"relatorio_jogos_{datetime.today().strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf"
    )
    
    # Mostrar tabela resumo
    st.subheader("📈 Resumo dos Jogos Conferidos")
    st.dataframe(df_conferidos)
    
else:
    st.info("Nenhum jogo conferido disponível para relatório.")

# =================================================================================
# Estatísticas
# =================================================================================
st.sidebar.markdown("---")
st.sidebar.header("📈 Estatísticas")

if alertas_salvos:
    total_alertas = len(alertas_salvos)
    conferidos = sum(1 for a in alertas_salvos.values() if a.get("conferido"))
    greens = sum(1 for a in alertas_salvos.values() if a.get("resultado") == "🟢 GREEN")
    reds = sum(1 for a in alertas_salvos.values() if a.get("resultado") == "🔴 RED")
    
    st.sidebar.metric("Total de Alertas", total_alertas)
    st.sidebar.metric("Jogos Conferidos", conferidos)
    
    if conferidos > 0:
        taxa_acerto = (greens / conferidos) * 100
        st.sidebar.metric("Taxa de Acerto", f"{taxa_acerto:.1f}%")
        st.sidebar.metric("Green", greens)
        st.sidebar.metric("Red", reds)
