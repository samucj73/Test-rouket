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

# =============================
# CONFIGURAÇÕES (coloque suas chaves)
# =============================
API_KEY_FD = "9058de85e3324bdb969adc005b5d918a"  # football-data.org
HEADERS_FD = {"X-Auth-Token": API_KEY_FD}
BASE_URL_FD = "https://api.football-data.org/v4"

API_KEY_TSD = "123"  # TheSportsDB (ex: 123)
BASE_URL_TSD = f"https://www.thesportsdb.com/api/v1/json/{API_KEY_TSD}"

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

# =============================
# Mapeamento TheSportsDB -> Football-Data (comum)
# Adapte/complete conforme necessidade
# =============================
TSD_TO_FD = {
    "English Premier League": 2021,
    "Premier League": 2021,
    "La Liga": 2014,
    "Primera División": 2014,
    "Serie A": 2019,
    "Bundesliga": 2002,
    "Ligue 1": 2015,
    "Primeira Liga": 2017,
    "Brazilian Serie A": 2013,
    "Campeonato Brasileiro Série A": 2013,
    "UEFA Champions League": 2001,
    # adicione outros mapeamentos necessários aqui
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
# Football-Data helpers (sua lógica original)
# =============================
def obter_classificacao_fd(liga_id):
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
        resp.raise_for_status()
        jogos = resp.json().get("matches", [])
        cache[key] = jogos
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.warning(f"Erro obter jogos FD: {e}")
        return []

# =============================
# TheSportsDB helpers (cache do Streamlit + requests)
# =============================
@st.cache_data(ttl=300)
def listar_ligas_tsd():
    url = f"{BASE_URL_TSD}/all_leagues.php"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    ligas = [l for l in data.get("leagues", []) if l.get("strSport") == "Soccer"]
    # retornar lista única de nomes
    return ligas

BASE_URL = "https://www.thesportsdb.com/api/v1/json/1"  # ou sua API Key

@st.cache_data(ttl=3600)
def buscar_jogos_tsd(liga_nome, data):
    url = f"{BASE_URL}/eventsday.php?d={data}&l={liga_nome}"
    st.write("🔎 URL chamada:", url)  # ajuda a debugar
    try:
        r = requests.get(url)
        if r.status_code != 200:
            st.warning(f"⚠️ Erro na API TheSportsDB ({r.status_code}): {r.text}")
            return []
        data_json = r.json()
        return data_json.get("events", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a TheSportsDB: {e}")
        return []

@st.cache_data(ttl=120)
def buscar_eventslast_team_tsd(id_team):
    url = f"{BASE_URL_TSD}/eventslast.php"
    params = {"id": id_team}
    r = requests.get(f"{BASE_URL_TSD}/eventslast.php?id={id_team}", timeout=10)
    r.raise_for_status()
    return r.json().get("results") or []

@st.cache_data(ttl=60)
def buscar_team_by_name_tsd(nome):
    url = f"{BASE_URL_TSD}/searchteams.php"
    params = {"t": nome}
    r = requests.get(f"{BASE_URL_TSD}/searchteams.php?t={nome}", timeout=10)
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
# Tendência (TheSportsDB — quando FD não disponível)
# usamos eventos recentes do time para calcular média de gols
# =============================
def calcular_tendencia_tsd(evento, max_last=5, peso_h2h=0.3):
    """
    evento: dicionário do TheSportsDB com chaves como strHomeTeam, strAwayTeam, dateEvent, idHomeTeam, idAwayTeam
    Retorna: estimativa, confianca, tendencia
    """
    try:
        home = evento.get("strHomeTeam")
        away = evento.get("strAwayTeam")
        # pega últimos jogos de cada time
        id_home = evento.get("idHomeTeam")
        id_away = evento.get("idAwayTeam")

        def media_gols_id(id_team):
            if not id_team:
                return 1.8  # fallback
            results = buscar_eventslast_team_tsd(id_team)
            if not results:
                return 1.8
            gols = []
            for r in results[:max_last]:
                # r tem keys: intHomeScore, intAwayScore, strHomeTeam, strAwayTeam
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

        # small weighting (no h2h available reliable)
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
        # TheSportsDB tem dateEvent + strTime
        try:
            return iso_str, ""
        except:
            return "-", "-"

# =============================
# UI e Lógica principal
# =============================
st.set_page_config(page_title="⚽ Sistema Unificado de Alertas", layout="wide")
st.title("⚽ Sistema Unificado de Alertas (Football-Data + TheSportsDB)")

# Data
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Carregar ligas TheSportsDB para escolha pelo usuário
st.sidebar.header("Opções de Busca")
st.sidebar.markdown("Escolha ligas provenientes da TheSportsDB (catálogo) ou use as ligas fixas do Football-Data.")

# listar ligas via TSD (cache)
ligas_tsd = []
try:
    ligas_tsd = listar_ligas_tsd()
    nomes_ligas = [l["strLeague"] for l in ligas_tsd]
except Exception:
    nomes_ligas = []

use_all_tsd = st.sidebar.checkbox("Usar todas ligas TSD", value=False)
ligas_selecionadas = []
if use_all_tsd:
    ligas_selecionadas = nomes_ligas
else:
    ligas_selecionadas = st.sidebar.multiselect("Selecione ligas (TheSportsDB):", nomes_ligas, max_selections=10)

# Opção de também usar ligas FD fixas (para análise completa)
usar_fd = st.sidebar.checkbox("Incluir ligas fixas (Football-Data) também", value=True)
ligas_fd_escolha = []
if usar_fd:
    # lista amigável das ligas FD (a partir do seu dicionário original)
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

# Botões principais
st.markdown("---")
col1, col2 = st.columns([1,1])
with col1:
    buscar_btn = st.button("🔍 Buscar partidas e analisar")
with col2:
    conferir_btn = st.button("📊 Conferir resultados (usar alertas salvo)")

# =================================================================================
# Quando buscar: varre ligas TSD selecionadas + ligas FD selecionadas
# =================================================================================
if buscar_btn:
    st.info(f"Buscando partidas para {data_str}...")
    total_top_jogos = []

    # 1) Processar ligas selecionadas via TheSportsDB
    for liga_nome in ligas_selecionadas:
        jogos_tsd = buscar_jogos_tsd(liga_nome, data_str)
        if not jogos_tsd:
            st.write(f"⚠️ Nenhum jogo para *{liga_nome}* em {data_str}")
            continue

        st.header(f"🏆 {liga_nome} — TheSportsDB ({len(jogos_tsd)} jogos)")
        for e in jogos_tsd:
            # campos diferentes dependendo do retorno
            home = e.get("strHomeTeam") or e.get("homeTeam") or "Desconhecido"
            away = e.get("strAwayTeam") or e.get("awayTeam") or "Desconhecido"
            date_event = e.get("dateEvent") or e.get("dateEventLocal") or data_str
            time_event = e.get("strTime") or e.get("strTimeLocal") or ""
            # tenta mapear para FD se possível
            fd_id = None
            for key_name, fd_id_val in TSD_TO_FD.items():
                # comparação simplificada
                if key_name.lower() in liga_nome.lower() or liga_nome.lower() in key_name.lower():
                    fd_id = fd_id_val
                    break

            # se tiver mapeamento fd_id então usar FD para classificação/jogos (mais confiável)
            if fd_id:
                classificacao = obter_classificacao_fd(fd_id)
                jogos_fd = obter_jogos_fd(fd_id, data_str)
                # procurar match correspondente pelo nome dos times
                match_fd = None
                for m in jogos_fd:
                    try:
                        if m.get("homeTeam", {}).get("name") == home and m.get("awayTeam", {}).get("name") == away:
                            match_fd = m
                            break
                    except Exception:
                        pass
                if match_fd:
                    # usar cálculo FD
                    estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
                    # preparar mensagem e enviar
                    data_brt, hora_brt = parse_time_iso_to_brt(match_fd.get("utcDate"))
                    enviar_alerta_telegram_generico(home, away, data_brt, hora_brt, liga_nome, tendencia, estimativa, confianca)
                    # salvar no top_jogos
                    total_top_jogos.append({
                        "id": str(match_fd.get("id")),
                        "home": home, "away": away,
                        "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                        "liga": liga_nome,
                        "hora": hora_brt,
                        "origem": "FD"
                    })
                    st.write(f"⚽ {hora_brt} | {home} x {away} — {tendencia} ({confianca}%) — [FD]")
                    continue  # próximo evento

            # se não mapeado pra FD, usa análise TSD
            estimativa, confianca, tendencia = calcular_tendencia_tsd(e)
            # formatar data/hora (use dateEvent + strTime)
            try:
                dt_brt = None
                if date_event and time_event:
                    # montar naive parse
                    dt_str = f"{date_event} {time_event}"
                    # TheSportsDB time may be local; não confiamos no timezone — apenas exibe
                    data_brt = date_event
                    hora_brt = time_event
                else:
                    data_brt, hora_brt = date_event, time_event or "??:??"
            except:
                data_brt, hora_brt = date_event, time_event or "??:??"

            enviar_alerta_telegram_generico(home, away, data_brt, hora_brt, liga_nome, tendencia, estimativa, confianca)
            total_top_jogos.append({
                "id": e.get("idEvent") or f"tsd_{liga_nome}_{home}_{away}",
                "home": home, "away": away,
                "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                "liga": liga_nome,
                "hora": hora_brt,
                "origem": "TSD"
            })
            st.write(f"⚽ {hora_brt} | {home} x {away} — {tendencia} ({confianca}%) — [TSD]")

    # 2) Processar ligas FD selecionadas manualmente (se houver)
    for fd_id in ligas_fd_escolha:
        jogos_fd = obter_jogos_fd(fd_id, data_str)
        classificacao = obter_classificacao_fd(fd_id)
        if not jogos_fd:
            st.write(f"⚠️ Nenhum jogo FD (id={fd_id}) em {data_str}")
            continue
        # exibe por competição
        for m in jogos_fd:
            home = m.get("homeTeam", {}).get("name", "Desconhecido")
            away = m.get("awayTeam", {}).get("name", "Desconhecido")
            utc = m.get("utcDate")
            data_brt, hora_brt = parse_time_iso_to_brt(utc)
            estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
            enviar_alerta_telegram_generico(home, away, data_brt, hora_brt, m.get("competition", {}).get("name","FD"), tendencia, estimativa, confianca)
            total_top_jogos.append({
                "id": str(m.get("id")),
                "home": home, "away": away,
                "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                "liga": m.get("competition", {}).get("name","FD"),
                "hora": hora_brt,
                "origem": "FD"
            })
            st.write(f"⚽ {hora_brt} | {home} x {away} — {tendencia} ({confianca}%) — [FD]")

    # Ordenar top por confiança e exibir enviar consolidado
    if total_top_jogos:
        top_sorted = sorted(total_top_jogos, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:5]
        st.markdown("## 🏆 Top jogos recomendados (por confiança)")
        mensagem = "📢 *TOP Jogos Consolidados*\n\n"
        odd_dummy = 1.0
        for t in top_sorted:
            st.write(f"🏟️ {t['home']} x {t['away']} — {t['tendencia']} | Conf: {t['confianca']}% | Origem: {t['origem']}")
            mensagem += f"🏟️ {t['liga']}\n🏆 {t['home']} x {t['away']}\nTendência: {t['tendencia']} | Conf.: {t['confianca']}%\n\n"
        enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)
        st.success("✅ Top jogos enviados para canal alternativo.")

# =================================================================================
# Conferência de resultados (usa alertas.json + cache_jogos.json)
# =================================================================================
if conferir_btn:
    st.info("Conferindo resultados dos alertas salvos...")
    alertas = carregar_alertas()
    cache_jogos = carregar_cache_jogos()
    mudou = False
    if not alertas:
        st.info("Nenhum alerta salvo.")
    else:
        for fixture_id, info in alertas.items():
            if info.get("conferido"):
                continue
            # procurar nos caches (pode ter FD ou TSD)
            jogo_dado = None
            # procurar chave FD
            for key, jogos in cache_jogos.items():
                # cache pode ter FD ou TSD keys; cada 'jogos' é lista
                for m in jogos:
                    # m pode ser FD match (tem 'id') ou TSD event (tem 'idEvent')
                    mid = m.get("id") or m.get("idEvent")
                    if str(mid) == str(fixture_id):
                        jogo_dado = m
                        break
                if jogo_dado:
                    break
            if not jogo_dado:
                # não achou no cache -> tenta buscar via FD se for ID numérico
                try:
                    if str(fixture_id).isdigit():
                        # tenta buscar match específico (football-data)
                        # endpoint: /matches/{id}
                        url = f"{BASE_URL_FD}/matches/{fixture_id}"
                        r = requests.get(url, headers=HEADERS_FD, timeout=8)
                        if r.status_code == 200:
                            jogo_dado = r.json().get("match")
                except Exception:
                    pass
            if not jogo_dado:
                st.warning(f"Não foi possível recuperar dados do jogo {fixture_id}.")
                continue

            # extrair dados (compatibilidade FD / TSD)
            # FD:
            if "homeTeam" in jogo_dado and "awayTeam" in jogo_dado:
                home = jogo_dado["homeTeam"]["name"]
                away = jogo_dado["awayTeam"]["name"]
                status = jogo_dado.get("status", jogo_dado.get("fixture", {}).get("status", "DESCONHECIDO"))
                gols_home = None
                gols_away = None
                if jogo_dado.get("score"):
                    ft = jogo_dado.get("score", {}).get("fullTime", {})
                    gols_home = ft.get("home")
                    gols_away = ft.get("away")
                elif jogo_dado.get("fullTime"):
                    ft = jogo_dado.get("fullTime", {})
                    gols_home = ft.get("homeTeam")
                    gols_away = ft.get("awayTeam")
            else:
                # TSD
                home = jogo_dado.get("strHomeTeam") or jogo_dado.get("homeTeam") or "Desconhecido"
                away = jogo_dado.get("strAwayTeam") or jogo_dado.get("awayTeam") or "Desconhecido"
                status = jogo_dado.get("strStatus") or jogo_dado.get("status") or "DESCONHECIDO"
                gols_home = jogo_dado.get("intHomeScore")
                gols_away = jogo_dado.get("intAwayScore")

            placar = f"{gols_home} x {gols_away}" if (gols_home is not None and gols_away is not None) else "-"
            total_gols = (gols_home or 0) + (gols_away or 0)
            tendencia = info.get("tendencia", "")
            if status in ("FINISHED", "Match Finished", "Finished"):
                if "2.5" in tendencia:
                    resultado = "🟢 GREEN" if total_gols > 2 else "🔴 RED"
                elif "1.5" in tendencia:
                    resultado = "🟢 GREEN" if total_gols > 1 else "🔴 RED"
                else:
                    resultado = "-"
            else:
                resultado = "⏳ Aguardando"

            # exibir no Streamlit
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

            if status in ("FINISHED", "Match Finished", "Finished"):
                info["conferido"] = True
                mudou = True

        if mudou:
            salvar_alertas(alertas)
            st.success("Atualizado status dos alertas conferidos.")

# =================================================================================
# Relatório PDF (mesma lógica do seu app)
# =================================================================================
# Prepara lista de jogos conferidos para download (igual à sua rotina)
alertas_salvos = carregar_alertas()
cache_jogos = carregar_cache_jogos()
jogos_conferidos = []

for fixture_id, info in alertas_salvos.items():
    if info.get("conferido"):
        # buscar no cache_jogos
        jogo_dado = None
        for key, jogos in cache_jogos.items():
            for match in jogos:
                mid = match.get("id") or match.get("idEvent")
                if str(mid) == str(fixture_id):
                    jogo_dado = match
                    break
            if jogo_dado:
                break
        if not jogo_dado:
            continue

        # extrair campos com abreviação
        def abreviar_nome(nome, max_len=15):
            if not nome: return nome
            if len(nome) <= max_len:
                return nome
            palavras = nome.split()
            abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
            if len(abreviado) > max_len:
                abreviado = abreviado[:max_len-3] + "..."
            return abreviado

        # extrair nomes e placar
        if "homeTeam" in jogo_dado:
            home = abreviar_nome(jogo_dado["homeTeam"]["name"])
            away = abreviar_nome(jogo_dado["awayTeam"]["name"])
            gols_home = jogo_dado.get("score", {}).get("fullTime", {}).get("home")
            gols_away = jogo_dado.get("score", {}).get("fullTime", {}).get("away")
            status = jogo_dado.get("status", "DESCONHECIDO")
            utc = jogo_dado.get("utcDate")
        else:
            home = abreviar_nome(jogo_dado.get("strHomeTeam"))
            away = abreviar_nome(jogo_dado.get("strAwayTeam"))
            gols_home = jogo_dado.get("intHomeScore")
            gols_away = jogo_dado.get("intAwayScore")
            status = jogo_dado.get("strStatus") or "DESCONHECIDO"
            utc = jogo_dado.get("dateEvent") or ""

        placar = f"{gols_home} x {gols_away}" if (gols_home is not None and gols_away is not None) else "-"
        total_gols = (gols_home or 0) + (gols_away or 0)
        if status in ("FINISHED", "Match Finished", "Finished"):
            if "2.5" in info.get("tendencia",""):
                resultado = "🟢 GREEN" if total_gols > 2 else "🔴 RED"
            elif "1.5" in info.get("tendencia",""):
                resultado = "🟢 GREEN" if total_gols > 1 else "🔴 RED"
            else:
                resultado = "-"
        else:
            resultado = "⏳ Aguardando"

        # hora para exibir
        try:
            hora = datetime.fromisoformat(utc.replace("Z","+00:00")) - timedelta(hours=3)
            hora_format = hora.strftime("%d/%m %H:%M")
        except:
            hora_format = utc or "-"

        jogos_conferidos.append([
            f"{home} vs {away}",
            info.get("tendencia","-"),
            f"{info.get('estimativa',0):.2f}",
            f"{info.get('confianca',0):.0f}%",
            placar,
            status,
            resultado,
            hora_format
        ])

if jogos_conferidos:
    df_conferidos = pd.DataFrame(jogos_conferidos, columns=[
        "Jogo","Tendência","Estimativa","Confiança","Placar","Status","Resultado","Hora"
    ])

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    data_table = [df_conferidos.columns.tolist()] + df_conferidos.values.tolist()
    table = Table(data_table, repeatRows=1, colWidths=[120, 70, 60, 60, 50, 70, 60, 70])
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
    for i in range(1, len(data_table)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0,i), (-1,i), colors.HexColor("#E0E0E0"))
    table.setStyle(style)
    pdf.build([table])
    buffer.seek(0)
    st.download_button(
        label="📄 Baixar Jogos Conferidos em PDF (Tabela Estilo Matriz)",
        data=buffer,
        file_name=f"jogos_conferidos_matriz_{datetime.today().strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf"
    )
else:
    st.info("Nenhum jogo conferido disponível para gerar PDF.")
