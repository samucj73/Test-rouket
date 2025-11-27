# Futebol_Alertas_Unificado.py
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
import base64
from PIL import Image
import time

# =============================
# CONFIGURAÇÕES (coloque suas chaves)
# =============================
API_KEY_FD = "9058de85e3324bdb969adc005b5d918a"  # football-data.org
HEADERS_FD = {"X-Auth-Token": API_KEY_FD}
BASE_URL_FD = "https://api.football-data.org/v4"

API_KEY_TSD = "3"  # TheSportsDB - chave pública válida
BASE_URL_TSD = f"https://www.thesportsdb.com/api/v1/json/{API_KEY_TSD}"

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_POSTERS = "cache_posters.json"

# =============================
# Inicialização do Session State
# =============================
def inicializar_session_state():
    """Inicializa todas as variáveis do session_state"""
    if 'jogos_encontrados' not in st.session_state:
        st.session_state.jogos_encontrados = []
    if 'busca_realizada' not in st.session_state:
        st.session_state.busca_realizada = False
    if 'alertas_enviados' not in st.session_state:
        st.session_state.alertas_enviados = False
    if 'top_jogos' not in st.session_state:
        st.session_state.top_jogos = []
    if 'data_ultima_busca' not in st.session_state:
        st.session_state.data_ultima_busca = None
    if 'resultados_conferidos' not in st.session_state:
        st.session_state.resultados_conferidos = []
    if 'posters_cache' not in st.session_state:
        st.session_state.posters_cache = {}
    if 'erros_busca' not in st.session_state:
        st.session_state.erros_busca = []

# =============================
# Mapeamento TheSportsDB -> Football-Data (comum)
# =============================
TSD_TO_FD = {
    # Ligas Europeias
    "English Premier League": 2021,
    "Premier League": 2021,
    "La Liga": 2014,
    "Primera División": 2014,
    "Serie A": 2019,
    "Bundesliga": 2002,
    "Ligue 1": 2015,
    "Primeira Liga": 2017,
    "UEFA Champions League": 2001,

    # Ligas Brasileiras
    "Brazilian Serie A": 2013,
    "Campeonato Brasileiro Série A": 2013,
    "Brazilian Serie B": 2014,
    "Campeonato Brasileiro Série B": 2014,

    # Outras Ligas Internacionais
    "Major League Soccer": 2145,
    "American Major League Soccer": 2145,
    "Liga MX": 2150,
    "Mexican Primera League": 2150,
    "Saudi Pro League": 2160,
    "Saudi-Arabian Pro League": 2160,
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

def carregar_cache_posters():
    return carregar_json(CACHE_POSTERS)

def salvar_cache_posters(dados):
    salvar_json(CACHE_POSTERS, dados)

# =============================
# Funções para Posters
# =============================
def obter_poster_time(nome_time):
    """Obtém poster do time do TheSportsDB"""
    cache = carregar_cache_posters()
    
    if nome_time in cache:
        return cache[nome_time]
    
    try:
        # Buscar time por nome
        url = f"{BASE_URL_TSD}/searchteams.php"
        params = {"t": nome_time}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            teams = r.json().get("teams", [])
            
            if teams:
                poster_url = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo") or ""
                if poster_url:
                    cache[nome_time] = poster_url
                    salvar_cache_posters(cache)
                    return poster_url
    except Exception as e:
        st.warning(f"Erro ao buscar poster para {nome_time}: {e}")
    
    return ""

def obter_poster_liga(nome_liga):
    """Obtém poster da liga do TheSportsDB"""
    cache = carregar_cache_posters()
    cache_key = f"liga_{nome_liga}"
    
    if cache_key in cache:
        return cache[cache_key]
    
    try:
        # Buscar todas as ligas
        url = f"{BASE_URL_TSD}/all_leagues.php"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            ligas = r.json().get("leagues", [])
            
            for liga in ligas:
                if liga.get("strLeague") == nome_liga:
                    poster_url = liga.get("strBadge") or liga.get("strLogo") or ""
                    if poster_url:
                        cache[cache_key] = poster_url
                        salvar_cache_posters(cache)
                        return poster_url
    except Exception as e:
        st.warning(f"Erro ao buscar poster da liga {nome_liga}: {e}")
    
    return ""

def baixar_imagem_url(url):
    """Baixa imagem da URL e converte para base64"""
    try:
        if not url:
            return None
            
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode()
    except Exception:
        pass
    return None

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        response = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode":"Markdown"}, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")
        return False

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
    return enviar_telegram(msg, chat_id)

# =============================
# Football-Data helpers
# =============================
def obter_classificacao_fd(liga_id):
    cache = carregar_cache_classificacao()
    if str(liga_id) in cache:
        return cache[str(liga_id)]

    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
        resp = requests.get(url, headers=HEADERS_FD, timeout=10)
        if resp.status_code == 200:
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
            cache[str(liga_id)] = standings
            salvar_cache_classificacao(cache)
            return standings
        else:
            st.warning(f"Erro HTTP {resp.status_code} ao obter classificação FD para liga {liga_id}")
            return {}
    except Exception as e:
        st.warning(f"Erro obter classificação FD: {e}")
        return {}

def obter_jogos_fd(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"fd_{liga_id}_{data}"
    if key in cache:
        return cache[key]
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        resp = requests.get(url, headers=HEADERS_FD, timeout=10)
        if resp.status_code == 200:
            jogos = resp.json().get("matches", [])
            cache[key] = jogos
            salvar_cache_jogos(cache)
            return jogos
        else:
            st.warning(f"Erro HTTP {resp.status_code} ao obter jogos FD para liga {liga_id}")
            return []
    except Exception as e:
        st.warning(f"Erro obter jogos FD: {e}")
        return []

# =============================
# TheSportsDB helpers (cache do Streamlit + requests)
# =============================
def listar_ligas_tsd():
    """Lista ligas do TheSportsDB com tratamento de erro"""
    try:
        url = f"{BASE_URL_TSD}/all_leagues.php"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            ligas = [l for l in data.get("leagues", []) if l.get("strSport") == "Soccer"]
            return ligas
        else:
            st.warning(f"Erro HTTP {r.status_code} ao listar ligas TSD")
            return []
    except Exception as e:
        st.warning(f"Erro ao listar ligas TSD: {e}")
        return []

def buscar_jogos_tsd(liga_nome, data_evento):
    """Busca jogos do TheSportsDB com tratamento robusto de erros"""
    try:
        url = f"{BASE_URL_TSD}/eventsday.php"
        params = {"d": data_evento, "l": liga_nome}
        r = requests.get(url, params=params, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            return data.get("events") or []
        else:
            # Log do erro sem quebrar a aplicação
            error_msg = f"Erro HTTP {r.status_code} ao buscar jogos TSD para liga {liga_nome}"
            st.session_state.erros_busca.append(error_msg)
            return []
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Erro de conexão ao buscar jogos TSD: {e}"
        st.session_state.erros_busca.append(error_msg)
        return []
    except Exception as e:
        error_msg = f"Erro inesperado ao buscar jogos TSD: {e}"
        st.session_state.erros_busca.append(error_msg)
        return []

def buscar_eventslast_team_tsd(id_team):
    """Busca últimos eventos do time com tratamento de erro"""
    try:
        url = f"{BASE_URL_TSD}/eventslast.php"
        params = {"id": id_team}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("results") or []
        else:
            return []
    except Exception:
        return []

def buscar_team_by_name_tsd(nome):
    """Busca time por nome com tratamento de erro"""
    try:
        url = f"{BASE_URL_TSD}/searchteams.php"
        params = {"t": nome}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("teams") or []
        else:
            return []
    except Exception:
        return []

# =============================
# Tendência (Football-Data original)
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
# Tendência (TheSportsDB)
# =============================
def calcular_tendencia_tsd(evento, max_last=5, peso_h2h=0.3):
    try:
        home = evento.get("strHomeTeam")
        away = evento.get("strAwayTeam")
        id_home = evento.get("idHomeTeam")
        id_away = evento.get("idAwayTeam")

        def media_gols_id(id_team):
            if not id_team:
                return 1.8
            results = buscar_eventslast_team_tsd(id_team)
            if not results:
                return 1.8
            gols = []
            for r in results[:max_last]:
                try:
                    h = int(r.get("intHomeScore") or 0)
                    a = int(r.get("intAwayScore") or 0)
                    gols.append(h + a)
                except Exception:
                    pass
            if not gols:
                return 1.8
            return sum(gols)/len(gols)

        m_home = media_gols_id(id_home)
        m_away = media_gols_id(id_away)
        estimativa_base = (m_home + m_away) / 2
        estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * estimativa_base

        if estimativa_final >= 2.5:
            tendencia = "Mais 2.5"
            confianca = min(90, 60 + (estimativa_final - 2.5) * 12)
        elif estimativa_final >= 1.5:
            tendencia = "Mais 1.5"
            confianca = min(85, 55 + (estimativa_final - 1.5) * 15)
        else:
            tendencia = "Menos 2.5"
            confianca = max(45, min(75, 50 + (estimativa_final - 1.0) * 10))

        return round(estimativa_final, 2), round(confianca, 0), tendencia
    except Exception:
        return 1.8, 50, "Mais 1.5"

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
        try:
            return iso_str, ""
        except:
            return "-", "-"

# =============================
# Funções de busca principais
# =============================
def buscar_e_analisar_jogos(data_selecionada, ligas_selecionadas, ligas_fd_escolha):
    """Função principal para buscar e analisar jogos com tratamento robusto"""
    data_str = data_selecionada.strftime("%Y-%m-%d")
    total_jogos = []
    total_top_jogos = []
    
    # Limpar erros anteriores
    st.session_state.erros_busca = []

    # 1) Processar ligas selecionadas via TheSportsDB
    for liga_nome in ligas_selecionadas:
        try:
            jogos_tsd = buscar_jogos_tsd(liga_nome, data_str)
            if not jogos_tsd:
                continue

            for e in jogos_tsd:
                try:
                    home = e.get("strHomeTeam") or e.get("homeTeam") or "Desconhecido"
                    away = e.get("strAwayTeam") or e.get("awayTeam") or "Desconhecido"
                    date_event = e.get("dateEvent") or e.get("dateEventLocal") or data_str
                    time_event = e.get("strTime") or e.get("strTimeLocal") or ""
                    
                    # Buscar posters (opcional, não quebra se falhar)
                    poster_home = obter_poster_time(home)
                    poster_away = obter_poster_time(away)
                    poster_liga = obter_poster_liga(liga_nome)
                    
                    fd_id = None
                    for key_name, fd_id_val in TSD_TO_FD.items():
                        if key_name.lower() in liga_nome.lower() or liga_nome.lower() in key_name.lower():
                            fd_id = fd_id_val
                            break

                    if fd_id:
                        classificacao = obter_classificacao_fd(fd_id)
                        jogos_fd = obter_jogos_fd(fd_id, data_str)
                        match_fd = None
                        for m in jogos_fd:
                            try:
                                if m.get("homeTeam", {}).get("name") == home and m.get("awayTeam", {}).get("name") == away:
                                    match_fd = m
                                    break
                            except Exception:
                                pass
                        if match_fd:
                            estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
                            data_brt, hora_brt = parse_time_iso_to_brt(match_fd.get("utcDate"))
                            
                            jogo_info = {
                                "id": str(match_fd.get("id")),
                                "home": home, "away": away,
                                "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                                "liga": liga_nome,
                                "hora": hora_brt,
                                "origem": "FD",
                                "data_brt": data_brt,
                                "poster_home": poster_home,
                                "poster_away": poster_away,
                                "poster_liga": poster_liga
                            }
                            total_jogos.append(jogo_info)
                            continue

                    # Se não mapeado pra FD, usa análise TSD
                    estimativa, confianca, tendencia = calcular_tendencia_tsd(e)
                    try:
                        if date_event and time_event:
                            data_brt = date_event
                            hora_brt = time_event
                        else:
                            data_brt, hora_brt = date_event, time_event or "??:??"
                    except:
                        data_brt, hora_brt = date_event, time_event or "??:??"

                    jogo_info = {
                        "id": e.get("idEvent") or f"tsd_{liga_nome}_{home}_{away}",
                        "home": home, "away": away,
                        "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                        "liga": liga_nome,
                        "hora": hora_brt,
                        "origem": "TSD",
                        "data_brt": data_brt,
                        "poster_home": poster_home,
                        "poster_away": poster_away,
                        "poster_liga": poster_liga
                    }
                    total_jogos.append(jogo_info)
                    
                except Exception as e:
                    error_msg = f"Erro ao processar jogo {liga_nome}: {e}"
                    st.session_state.erros_busca.append(error_msg)
                    continue
                    
        except Exception as e:
            error_msg = f"Erro ao processar liga {liga_nome}: {e}"
            st.session_state.erros_busca.append(error_msg)
            continue

    # 2) Processar ligas FD selecionadas manualmente
    for fd_id in ligas_fd_escolha:
        try:
            jogos_fd = obter_jogos_fd(fd_id, data_str)
            classificacao = obter_classificacao_fd(fd_id)
            if not jogos_fd:
                continue

            for m in jogos_fd:
                try:
                    home = m.get("homeTeam", {}).get("name", "Desconhecido")
                    away = m.get("awayTeam", {}).get("name", "Desconhecido")
                    utc = m.get("utcDate")
                    data_brt, hora_brt = parse_time_iso_to_brt(utc)
                    
                    # Buscar posters para times FD
                    poster_home = obter_poster_time(home)
                    poster_away = obter_poster_time(away)
                    poster_liga = obter_poster_liga(m.get("competition", {}).get("name","FD"))
                    
                    estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
                    
                    jogo_info = {
                        "id": str(m.get("id")),
                        "home": home, "away": away,
                        "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                        "liga": m.get("competition", {}).get("name","FD"),
                        "hora": hora_brt,
                        "origem": "FD",
                        "data_brt": data_brt,
                        "poster_home": poster_home,
                        "poster_away": poster_away,
                        "poster_liga": poster_liga
                    }
                    total_jogos.append(jogo_info)
                    
                except Exception as e:
                    error_msg = f"Erro ao processar jogo FD {fd_id}: {e}"
                    st.session_state.erros_busca.append(error_msg)
                    continue
                    
        except Exception as e:
            error_msg = f"Erro ao processar liga FD {fd_id}: {e}"
            st.session_state.erros_busca.append(error_msg)
            continue

    # Ordenar por confiança e selecionar top 5
    if total_jogos:
        total_top_jogos = sorted(total_jogos, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:5]

    return total_jogos, total_top_jogos

def enviar_alertas_individualmente(jogos):
    """Envia alertas individuais para cada jogo"""
    alertas_enviados = []
    for jogo in jogos:
        try:
            sucesso = enviar_alerta_telegram_generico(
                jogo['home'], jogo['away'], jogo['data_brt'], jogo['hora'], 
                jogo['liga'], jogo['tendencia'], jogo['estimativa'], jogo['confianca']
            )
            if sucesso:
                alertas_enviados.append(jogo)
        except Exception as e:
            st.warning(f"Erro ao enviar alerta para {jogo['home']} vs {jogo['away']}: {e}")
    return alertas_enviados

def enviar_top_consolidado(top_jogos):
    """Envia top jogos consolidado com posters"""
    if not top_jogos:
        return False
        
    mensagem = "🏆 *TOP JOGOS CONSOLIDADOS* 🏆\n\n"
    
    for i, jogo in enumerate(top_jogos, 1):
        # Emoji baseado na posição
        emoji_posicao = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1] if i <= 5 else "🔹"
        
        # Emoji para tendência
        emoji_tendencia = "🔥" if jogo['tendencia'] == "Mais 2.5" else "⚡" if jogo['tendencia'] == "Mais 1.5" else "🛡️"
        
        mensagem += (
            f"{emoji_posicao} *{jogo['home']}* 🆚 *{jogo['away']}*\n"
            f"🏆 {jogo['liga']} | 🕐 {jogo['hora']}\n"
            f"{emoji_tendencia} *{jogo['tendencia']}* | 📊 {jogo['estimativa']:.1f} gols | ✅ {jogo['confianca']}%\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )
    
    mensagem += f"\n📅 *Data:* {top_jogos[0]['data_brt'] if top_jogos else 'N/A'}"
    mensagem += f"\n🎯 *Total de jogos analisados:* {len(st.session_state.jogos_encontrados)}"
    
    return enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)

def criar_poster_top_jogos(top_jogos):
    """Cria um poster visual para os top jogos"""
    if not top_jogos:
        return None
        
    try:
        # Criar DataFrame para exibição
        dados = []
        for i, jogo in enumerate(top_jogos, 1):
            dados.append({
                "Pos": f"{i}°",
                "Jogo": f"{jogo['home']} vs {jogo['away']}",
                "Liga": jogo['liga'],
                "Horário": jogo['hora'],
                "Tendência": jogo['tendencia'],
                "Estimativa": f"{jogo['estimativa']:.1f}",
                "Confiança": f"{jogo['confianca']}%"
            })
        
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        st.error(f"Erro ao criar poster: {e}")
        return None

# =============================
# Funções para Conferência de Resultados
# =============================
def buscar_resultados_jogos(data_selecionada):
    """Busca resultados dos jogos para conferência"""
    data_str = data_selecionada.strftime("%Y-%m-%d")
    resultados = []
    
    try:
        # Buscar jogos finalizados do football-data
        for liga_id in [2021, 2014, 2019, 2002, 2015, 2013]:  # Principais ligas
            try:
                url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data_str}&dateTo={data_str}&status=FINISHED"
                resp = requests.get(url, headers=HEADERS_FD, timeout=10)
                if resp.status_code == 200:
                    jogos = resp.json().get("matches", [])
                    for jogo in jogos:
                        if jogo.get("status") == "FINISHED":
                            home_team = jogo.get("homeTeam", {}).get("name", "")
                            away_team = jogo.get("awayTeam", {}).get("name", "")
                            score = jogo.get("score", {})
                            full_time = score.get("fullTime", {})
                            home_goals = full_time.get("home", 0)
                            away_goals = full_time.get("away", 0)
                            total_gols = home_goals + away_goals
                            
                            resultados.append({
                                "home": home_team,
                                "away": away_team,
                                "placar": f"{home_goals}-{away_goals}",
                                "total_gols": total_gols,
                                "tendencia_real": "Mais 2.5" if total_gols > 2.5 else "Menos 2.5",
                                "liga": jogo.get("competition", {}).get("name", "")
                            })
            except Exception:
                continue
    except Exception as e:
        st.warning(f"Erro ao buscar resultados: {e}")
    
    return resultados

def comparar_previsao_real(jogos_previstos, resultados_reais):
    """Compara previsões com resultados reais"""
    comparacao = []
    
    for jogo_prev in jogos_previstos:
        # Buscar resultado correspondente
        resultado_correspondente = None
        for resultado in resultados_reais:
            if (jogo_prev['home'].lower() in resultado['home'].lower() or 
                resultado['home'].lower() in jogo_prev['home'].lower()):
                resultado_correspondente = resultado
                break
        
        if resultado_correspondente:
            acerto = "✅" if jogo_prev['tendencia'] == resultado_correspondente['tendencia_real'] else "❌"
            comparacao.append({
                "Jogo": f"{jogo_prev['home']} x {jogo_prev['away']}",
                "Previsão": jogo_prev['tendencia'],
                "Real": resultado_correspondente['tendencia_real'],
                "Placar": resultado_correspondente['placar'],
                "Resultado": acerto,
                "Confiança": f"{jogo_prev['confianca']}%"
            })
    
    return comparacao

# =============================
# UI e Lógica principal
# =============================
def main():
    st.set_page_config(page_title="⚽ Sistema Unificado de Alertas", layout="wide")
    inicializar_session_state()
    
    st.title("⚽ Sistema Unificado de Alertas (Football-Data + TheSportsDB)")

    # Data
    data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Carregar ligas TheSportsDB
    st.sidebar.header("Opções de Busca")
    ligas_tsd = []
    try:
        ligas_tsd = listar_ligas_tsd()
        nomes_ligas = [l["strLeague"] for l in ligas_tsd]
    except Exception as e:
        st.sidebar.warning(f"Erro ao carregar ligas TSD: {e}")
        nomes_ligas = []

    use_all_tsd = st.sidebar.checkbox("Usar todas ligas TSD", value=False)
    ligas_selecionadas = []
    if use_all_tsd:
        ligas_selecionadas = nomes_ligas
    else:
        ligas_selecionadas = st.sidebar.multiselect("Selecione ligas (TheSportsDB):", nomes_ligas, max_selections=10)

    # Opção de também usar ligas FD fixas
    usar_fd = st.sidebar.checkbox("Incluir ligas fixas (Football-Data) também", value=True)
    ligas_fd_escolha = []
    if usar_fd:
        liga_dict_fd = {
            "Premier League (Inglaterra)": 2021,
            "Championship (Inglaterra)": 2016,
            "Bundesliga (Alemanha)": 2002,
            "La Liga (Espanha)": 2014,
            "Serie A (Itália)": 2019,
            "Ligue 1 (França)": 2015,
            "Primeira Liga (Portugal)": 2017,
            "Campeonato Brasileiro Série A": 2013,
            "UEFA Champions League": 2001,
        }
        adicionar_fd = st.sidebar.multiselect("Adicionar ligas Football-Data (opcional):", list(liga_dict_fd.keys()))
        ligas_fd_escolha = [liga_dict_fd[n] for n in adicionar_fd]

    # Status da sessão
    st.sidebar.header("📊 Status da Sessão")
    st.sidebar.write(f"Busca realizada: {'✅' if st.session_state.busca_realizada else '❌'}")
    st.sidebar.write(f"Alertas enviados: {'✅' if st.session_state.alertas_enviados else '❌'}")
    st.sidebar.write(f"Jogos encontrados: {len(st.session_state.jogos_encontrados)}")
    st.sidebar.write(f"Top jogos: {len(st.session_state.top_jogos)}")
    
    # Mostrar erros se houver
    if st.session_state.erros_busca:
        with st.sidebar.expander("⚠️ Erros na Busca"):
            for erro in st.session_state.erros_busca[-5:]:  # Mostrar últimos 5 erros
                st.error(erro)

    # Botão para limpar dados
    if st.sidebar.button("🗑️ Limpar Dados da Sessão"):
        st.session_state.jogos_encontrados = []
        st.session_state.busca_realizada = False
        st.session_state.alertas_enviados = False
        st.session_state.top_jogos = []
        st.session_state.data_ultima_busca = None
        st.session_state.resultados_conferidos = []
        st.session_state.erros_busca = []
        st.success("Dados da sessão limpos!")
        st.rerun()

    st.markdown("---")
    col1, col2, col3, col4 = st.columns([1,1,1,1])
    
    with col1:
        buscar_btn = st.button("🔍 Buscar partidas e analisar", type="primary")
    
    with col2:
        enviar_alertas_btn = st.button("🚀 Enviar Alertas Individuais", 
                                     disabled=not st.session_state.busca_realizada)
    
    with col3:
        enviar_top_btn = st.button("📊 Enviar Top Consolidado", 
                                 disabled=not st.session_state.busca_realizada)
    
    with col4:
        conferir_btn = st.button("📈 Conferir Resultados")

    # =================================================================================
    # BUSCAR PARTIDAS
    # =================================================================================
    if buscar_btn:
        with st.spinner("Buscando partidas e analisando..."):
            try:
                jogos_encontrados, top_jogos = buscar_e_analisar_jogos(
                    data_selecionada, ligas_selecionadas, ligas_fd_escolha
                )
                
                # Salvar no session state
                st.session_state.jogos_encontrados = jogos_encontrados
                st.session_state.top_jogos = top_jogos
                st.session_state.busca_realizada = True
                st.session_state.data_ultima_busca = data_str
                st.session_state.alertas_enviados = False

                if jogos_encontrados:
                    st.success(f"✅ {len(jogos_encontrados)} jogos encontrados e analisados!")
                    
                    # Exibir jogos encontrados
                    st.subheader("📋 Todos os Jogos Encontrados")
                    for jogo in jogos_encontrados:
                        with st.container():
                            col1, col2, col3 = st.columns([3, 2, 1])
                            with col1:
                                # Exibir posters se disponíveis
                                col_img1, col_img2, col_text = st.columns([1,1,3])
                                with col_img1:
                                    if jogo.get('poster_home'):
                                        st.image(jogo['poster_home'], width=30)
                                with col_img2:
                                    if jogo.get('poster_away'):
                                        st.image(jogo['poster_away'], width=30)
                                with col_text:
                                    st.write(f"**{jogo['home']}** vs **{jogo['away']}**")
                                    st.write(f"🏆 {jogo['liga']} | 🕐 {jogo['hora']} | 📊 {jogo['origem']}")
                            with col2:
                                st.write(f"🎯 {jogo['tendencia']}")
                                st.write(f"📈 Estimativa: {jogo['estimativa']} | ✅ Confiança: {jogo['confianca']}%")
                            with col3:
                                if jogo in st.session_state.top_jogos:
                                    st.success("🏆 TOP")
                            st.divider()
                    
                    # Exibir top jogos com poster
                    if top_jogos:
                        st.subheader("🏆 Top 5 Jogos (Maior Confiança)")
                        
                        # Criar poster visual
                        poster_df = criar_poster_top_jogos(top_jogos)
                        if poster_df is not None:
                            st.dataframe(poster_df, use_container_width=True)
                        
                        # Exibir detalhes dos top jogos
                        for i, jogo in enumerate(top_jogos, 1):
                            emoji_posicao = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
                            
                            with st.expander(f"{emoji_posicao} {jogo['home']} vs {jogo['away']} - {jogo['confianca']}% confiança"):
                                col1, col2, col3 = st.columns([1,2,1])
                                with col1:
                                    if jogo.get('poster_home'):
                                        st.image(jogo['poster_home'], width=80)
                                    st.write(f"**{jogo['home']}**")
                                with col2:
                                    st.write("**VS**")
                                    st.write(f"🏆 **{jogo['liga']}**")
                                    st.write(f"🕐 **{jogo['hora']}**")
                                    st.write(f"🎯 **Tendência:** {jogo['tendencia']}")
                                    st.write(f"📊 **Estimativa:** {jogo['estimativa']} gols")
                                    st.write(f"✅ **Confiança:** {jogo['confianca']}%")
                                with col3:
                                    if jogo.get('poster_away'):
                                        st.image(jogo['poster_away'], width=80)
                                    st.write(f"**{jogo['away']}**")
                else:
                    st.warning("⚠️ Nenhum jogo encontrado para os critérios selecionados.")
                    
            except Exception as e:
                st.error(f"❌ Erro crítico durante a busca: {e}")
                st.info("💡 Tente selecionar menos ligas ou verificar sua conexão com a internet.")

    # =================================================================================
    # ENVIAR ALERTAS INDIVIDUAIS
    # =================================================================================
    if enviar_alertas_btn and st.session_state.busca_realizada:
        with st.spinner("Enviando alertas individuais..."):
            alertas_enviados = enviar_alertas_individualmente(st.session_state.jogos_encontrados)
            
            if alertas_enviados:
                st.session_state.alertas_enviados = True
                st.success(f"✅ {len(alertas_enviados)} alertas enviados com sucesso!")
            else:
                st.error("❌ Erro ao enviar alertas")

    # =================================================================================
    # ENVIAR TOP CONSOLIDADO
    # =================================================================================
    if enviar_top_btn and st.session_state.busca_realizada and st.session_state.top_jogos:
        with st.spinner("Enviando top consolidado..."):
            if enviar_top_consolidado(st.session_state.top_jogos):
                st.success("✅ Top consolidado enviado com sucesso!")
                
                # Mostrar preview da mensagem
                st.subheader("📋 Preview do Top Consolidado")
                poster_df = criar_poster_top_jogos(st.session_state.top_jogos)
                if poster_df is not None:
                    st.dataframe(poster_df, use_container_width=True)
            else:
                st.error("❌ Erro ao enviar top consolidado")

    # =================================================================================
    # CONFERÊNCIA DE RESULTADOS
    # =================================================================================
    if conferir_btn:
        with st.spinner("Buscando resultados para conferência..."):
            # Buscar resultados reais
            resultados_reais = buscar_resultados_jogos(data_selecionada)
            
            if resultados_reais:
                st.success(f"✅ {len(resultados_reais)} resultados encontrados!")
                
                # Comparar com previsões se houver busca anterior
                if st.session_state.busca_realizada:
                    comparacao = comparar_previsao_real(st.session_state.jogos_encontrados, resultados_reais)
                    
                    if comparacao:
                        st.subheader("📊 Comparação: Previsão vs Realidade")
                        
                        # Calcular estatísticas
                        total_jogos = len(comparacao)
                        acertos = sum(1 for item in comparacao if item["Resultado"] == "✅")
                        taxa_acerto = (acertos / total_jogos) * 100 if total_jogos > 0 else 0
                        
                        # Exibir métricas
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total de Jogos", total_jogos)
                        with col2:
                            st.metric("Acertos", acertos)
                        with col3:
                            st.metric("Taxa de Acerto", f"{taxa_acerto:.1f}%")
                        
                        # Exibir tabela de comparação
                        comparacao_df = pd.DataFrame(comparacao)
                        st.dataframe(comparacao_df, use_container_width=True)
                        
                        # Salvar resultados conferidos
                        st.session_state.resultados_conferidos = comparacao
                    else:
                        st.warning("⚠️ Nenhuma correspondência encontrada entre previsões e resultados.")
                
                # Exibir todos os resultados encontrados
                with st.expander("📋 Ver Todos os Resultados Encontrados"):
                    resultados_df = pd.DataFrame(resultados_reais)
                    st.dataframe(resultados_df, use_container_width=True)
            else:
                st.warning("⚠️ Nenhum resultado encontrado para a data selecionada.")

if __name__ == "__main__":
    main()
