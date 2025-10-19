# Futebol_Alertas_Unificado.py (versão revisada)
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
from difflib import SequenceMatcher, get_close_matches
import logging

# -----------------------------
# Configurar logging simples
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alertas")

# =============================
# CONFIGURAÇÕES (use st.secrets)
# =============================
# Exemplo de secrets.toml:
# [st.secrets]
# API_KEY_FD = "seu_token_football_data"
# API_KEY_TSD = "seu_token_thesportsdb"
# TELEGRAM_TOKEN = "seu_bot_token"
# TELEGRAM_CHAT_ID = "-1001234567890"
API_KEY_FD = st.secrets.get("API_KEY_FD", "")
HEADERS_FD = {"X-Auth-Token": API_KEY_FD} if API_KEY_FD else {}
BASE_URL_FD = "https://api.football-data.org/v4"

API_KEY_TSD = st.secrets.get("API_KEY_TSD", "")
BASE_URL_TSD = f"https://www.thesportsdb.com/api/v1/json/{API_KEY_TSD}"

TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_ALT2 = st.secrets.get("TELEGRAM_CHAT_ID_ALT2", TELEGRAM_CHAT_ID)
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else None

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

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

# =============================
# Mapeamento TheSportsDB -> Football-Data (comum)
# =============================
TSD_TO_FD = {
    # Ligas Europeias
    "english premier league": 2021,
    "premier league": 2021,
    "la liga": 2014,
    "primera división": 2014,
    "serie a": 2019,
    "bundesliga": 2002,
    "ligue 1": 2015,
    "primeira liga": 2017,
    "uefa champions league": 2001,

    # Ligas Brasileiras
    "brazilian serie a": 2013,
    "campeonato brasileiro série a": 2013,
    "brazilian serie b": 2014,
    "campeonato brasileiro série b": 2014,

    # Outras Ligas Internacionais (IDs estimados/placeholder)
    "major league soccer": 2145,
    "liga mx": 2150,
    "saudi pro league": 2160,
}

# =============================
# Funções de persistência / cache em disco
# =============================
def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Falha ao carregar JSON {caminho}: {e}")
            return {}
    return {}

def salvar_json(caminho, dados):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar JSON {caminho}: {e}")

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
# Utilidades de correspondência de nomes
# =============================
def nome_similar(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def achar_partida_por_nomes(lista_matches, home, away, thresh=0.74):
    """
    Tenta encontrar em lista_matches (matches do FD) um match que corresponda a home/away com tolerância via similarity.
    """
    for m in lista_matches:
        try:
            nome_home_fd = (m.get("homeTeam") or {}).get("name", "")
            nome_away_fd = (m.get("awayTeam") or {}).get("name", "")
            score = (nome_similar(nome_home_fd, home) + nome_similar(nome_away_fd, away)) / 2
            if score >= thresh:
                return m
        except Exception:
            continue
    return None

# =============================
# Envio Telegram (mais robusto)
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    if not BASE_URL_TG:
        logger.warning("Telegram não configurado (TELEGRAM_TOKEN faltando).")
        return False
    try:
        resp = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode":"Markdown"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return True
            else:
                logger.warning(f"Telegram devolveu ok=false: {data}")
                return False
        else:
            logger.warning(f"Telegram status_code={resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Erro ao enviar Telegram: {e}")
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
# Football-Data helpers (com cache em disco)
# =============================
def obter_classificacao_fd(liga_id):
    if not API_KEY_FD:
        logger.info("API_KEY_FD não definida — pulando obter_classificacao_fd.")
        return {}
    cache = carregar_cache_classificacao()
    if str(liga_id) in cache:
        return cache[str(liga_id)]

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
        cache[str(liga_id)] = standings
        salvar_cache_classificacao(cache)
        return standings
    except Exception as e:
        logger.warning(f"Erro obter classificação FD: {e}")
        return {}

def obter_jogos_fd(liga_id, data):
    if not API_KEY_FD:
        logger.info("API_KEY_FD não definida — pulando obter_jogos_fd.")
        return []
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
        logger.warning(f"Erro obter jogos FD: {e}")
        return []

# =============================
# TheSportsDB helpers (cache do Streamlit + requests)
# =============================
@st.cache_data(ttl=300)
def listar_ligas_tsd():
    if not API_KEY_TSD:
        logger.info("API_KEY_TSD não definida — listar_ligas_tsd retorna [].")
        return []
    url = f"{BASE_URL_TSD}/all_leagues.php"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    ligas = [l for l in data.get("leagues", []) if l.get("strSport") == "Soccer"]
    return ligas

@st.cache_data(ttl=120)
def buscar_jogos_tsd(liga_nome, data_evento):
    if not API_KEY_TSD:
        return []
    url = f"{BASE_URL_TSD}/eventsday.php"
    params = {"d": data_evento, "l": liga_nome}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("events") or []

@st.cache_data(ttl=120)
def buscar_eventslast_team_tsd(id_team):
    if not API_KEY_TSD or not id_team:
        return []
    url = f"{BASE_URL_TSD}/eventslast.php"
    params = {"id": id_team}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("results") or []

@st.cache_data(ttl=60)
def buscar_team_by_name_tsd(nome):
    if not API_KEY_TSD or not nome:
        return []
    url = f"{BASE_URL_TSD}/searchteams.php"
    params = {"t": nome}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("teams") or []

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

        # atualmente não temos h2h direto, então peso_h2h aplica pouco — mantemos equilíbrio
        estimativa_final = estimativa_base

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
    except Exception as e:
        logger.warning(f"Erro calcular_tendencia_tsd: {e}")
        return 1.8, 50, "Mais 1.5"

# =============================
# Função para tratar tempo e formatar data/hora (BRT)
# =============================
def parse_time_iso_to_brt(iso_str):
    if not iso_str:
        return "-", "-"
    try:
        # aceita "2025-10-19T18:00:00Z" ou com offset
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # converter UTC -> BRT (UTC-3)
        dt_brt = dt - timedelta(hours=3)
        return dt_brt.strftime("%d/%m/%Y"), dt_brt.strftime("%H:%M")
    except Exception:
        try:
            # fallback: se a string for "YYYY-MM-DD"
            dt = datetime.strptime(iso_str, "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y"), "??:??"
        except Exception:
            return iso_str, ""

# =============================
# Funções de busca principais
# =============================
def buscar_e_analisar_jogos(data_selecionada, ligas_selecionadas, ligas_fd_escolha):
    """Função principal para buscar e analisar jogos"""
    data_str = data_selecionada.strftime("%Y-%m-%d")
    total_jogos = []
    total_top_jogos = []

    # 1) Processar ligas selecionadas via TheSportsDB
    for liga_nome in ligas_selecionadas:
        jogos_tsd = []
        try:
            jogos_tsd = buscar_jogos_tsd(liga_nome, data_str)
        except Exception as e:
            logger.warning(f"Erro buscar_jogos_tsd {liga_nome}: {e}")
            jogos_tsd = []

        if not jogos_tsd:
            continue

        for e in jogos_tsd:
            home = e.get("strHomeTeam") or e.get("homeTeam") or "Desconhecido"
            away = e.get("strAwayTeam") or e.get("awayTeam") or "Desconhecido"
            date_event = e.get("dateEvent") or e.get("dateEventLocal") or data_str
            time_event = e.get("strTime") or e.get("strTimeLocal") or ""

            fd_id = None
            lower_liga = (liga_nome or "").lower()
            for key_name, fd_id_val in TSD_TO_FD.items():
                if key_name in lower_liga or lower_liga in key_name:
                    fd_id = fd_id_val
                    break

            # se temos mapeamento pra FD, tentar buscar match na FD
            if fd_id:
                classificacao = obter_classificacao_fd(fd_id)
                jogos_fd = obter_jogos_fd(fd_id, data_str)
                match_fd = None
                if jogos_fd:
                    match_fd = achar_partida_por_nomes(jogos_fd, home, away, thresh=0.7)
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
                        "data_brt": data_brt
                    }
                    total_jogos.append(jogo_info)
                    continue  # passou pela rota FD

            # Se não mapeado pra FD ou não encontrado, usa análise TSD
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
                "data_brt": data_brt
            }
            total_jogos.append(jogo_info)

    # 2) Processar ligas FD selecionadas manualmente
    for fd_id in ligas_fd_escolha:
        jogos_fd = obter_jogos_fd(fd_id, data_str)
        classificacao = obter_classificacao_fd(fd_id)
        if not jogos_fd:
            continue

        for m in jogos_fd:
            home = m.get("homeTeam", {}).get("name", "Desconhecido")
            away = m.get("awayTeam", {}).get("name", "Desconhecido")
            utc = m.get("utcDate")
            data_brt, hora_brt = parse_time_iso_to_brt(utc)
            estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)

            jogo_info = {
                "id": str(m.get("id")),
                "home": home, "away": away,
                "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                "liga": m.get("competition", {}).get("name","FD"),
                "hora": hora_brt,
                "origem": "FD",
                "data_brt": data_brt
            }
            total_jogos.append(jogo_info)

    # Ordenar por confiança e selecionar top 5
    if total_jogos:
        total_top_jogos = sorted(total_jogos, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:5]

    return total_jogos, total_top_jogos

def enviar_alertas_individualmente(jogos):
    """Envia alertas individuais para cada jogo"""
    alertas_enviados = []
    for jogo in jogos:
        sucesso = enviar_alerta_telegram_generico(
            jogo['home'], jogo['away'], jogo['data_brt'], jogo['hora'],
            jogo['liga'], jogo['tendencia'], jogo['estimativa'], jogo['confianca']
        )
        if sucesso:
            alertas_enviados.append(jogo)
    return alertas_enviados

def enviar_top_consolidado(top_jogos):
    """Envia top jogos consolidado"""
    if not top_jogos:
        return False

    mensagem = "📢 *TOP Jogos Consolidados*\n\n"
    for t in top_jogos:
        mensagem += f"🏟️ {t['liga']}\n🏆 {t['home']} x {t['away']}\nTendência: {t['tendencia']} | Conf.: {t['confianca']}%\n\n"

    return enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)

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
    nomes_ligas = []
    try:
        ligas_tsd = listar_ligas_tsd()
        nomes_ligas = [l["strLeague"] for l in ligas_tsd] if ligas_tsd else []
    except Exception as e:
        logger.warning(f"listar_ligas_tsd falhou: {e}")
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

    # Botão para limpar dados
    if st.sidebar.button("🗑️ Limpar Dados da Sessão"):
        st.session_state.jogos_encontrados = []
        st.session_state.busca_realizada = False
        st.session_state.alertas_enviados = False
        st.session_state.top_jogos = []
        st.session_state.data_ultima_busca = None
        st.session_state.resultados_conferidos = []
        st.success("Dados da sessão limpos!")
        st.experimental_rerun()

    st.markdown("---")
    col1, col2, col3 = st.columns([1,1,1])

    with col1:
        buscar_btn = st.button("🔍 Buscar partidas e analisar", type="primary")

    with col2:
        enviar_alertas_btn = st.button("🚀 Enviar Alertas Individuais",
                                     disabled=not st.session_state.busca_realizada)

    with col3:
        enviar_top_btn = st.button("📊 Enviar Top Consolidado",
                                 disabled=not st.session_state.busca_realizada)

    # =================================================================================
    # BUSCAR PARTIDAS
    # =================================================================================
    if buscar_btn:
        with st.spinner("Buscando partidas e analisando..."):
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
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.write(f"**{jogo['home']}** vs **{jogo['away']}**")
                        st.write(f"🏆 {jogo['liga']} | 🕐 {jogo['hora']} | 📊 {jogo['origem']}")
                    with c2:
                        st.write(f"🎯 {jogo['tendencia']}")
                        st.write(f"📈 Estimativa: {jogo['estimativa']} | ✅ Confiança: {jogo['confianca']}%")
                    with c3:
                        if jogo in st.session_state.top_jogos:
                            st.success("🏆 TOP")
                    st.divider()

            # Exibir top jogos
            if top_jogos:
                st.subheader("🏆 Top 5 Jogos (Maior Confiança)")
                for i, jogo in enumerate(top_jogos, 1):
                    st.info(f"{i}. **{jogo['home']}** vs **{jogo['away']}** - {jogo['tendencia']} ({jogo['confianca']}% confiança)")
        else:
            st.warning("⚠️ Nenhum jogo encontrado para os critérios selecionados.")

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
                st.error("❌ Erro ao enviar alertas (ver logs).")

    # =================================================================================
    # ENVIAR TOP CONSOLIDADO
    # =================================================================================
    if enviar_top_btn and st.session_state.busca_realizada and st.session_state.top_jogos:
        with st.spinner("Enviando top consolidado..."):
            if enviar_top_consolidado(st.session_state.top_jogos):
                st.success("✅ Top consolidado enviado com sucesso!")
            else:
                st.error("❌ Erro ao enviar top consolidado (ver logs).")

    # =================================================================================
    # CONFERÊNCIA DE RESULTADOS (mantida do código original)
    # =================================================================================
    st.markdown("---")
    conferir_btn = st.button("📊 Conferir resultados (usar alertas salvo)")

    if conferir_btn:
        st.info("Conferindo resultados dos alertas salvos...")
        # Implementar lógica adicional de conferência conforme necessário
        # Exemplo: carregar arquivo alertas.json e comparar com resultados oficiais
        alertas_salvos = carregar_alertas() or []
        st.write("Alertas salvos:", alertas_salvos if alertas_salvos else "Nenhum alerta salvo atualmente.")

if __name__ == "__main__":
    main()
