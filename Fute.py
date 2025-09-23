# Futebol_Alertas_TheSportsDB.py
import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json
import time

# =============================
# Configurações APIs
# =============================
# TheSportsDB (v1 style) - use '3' para desenvolvimento; substitua pela sua chave quando for pra produção
THE_SPORTSDB_KEY = os.getenv("THE_SPORTSDB_KEY", "3")
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THE_SPORTSDB_KEY}"

# OpenLigaDB (mantido como antes)
OPENLIGA_BASE = "https://api.openligadb.de"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
TOP3_PATH = "top3.json"

# =============================
# Rate limiter simples (reaproveitei do seu código)
# =============================
_MIN_REQUEST_INTERVAL = 0.9
_last_request_time = 0.0

def _safe_get(url, headers=None, timeout=12):
    """requests.get com rate limit simples para evitar 429."""
    global _last_request_time
    now = time.time()
    gap = now - _last_request_time
    if gap < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - gap)
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception:
        return None
    _last_request_time = time.time()
    return resp

# =============================
# Persistência de alertas / Top3
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w", encoding="utf-8") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

def carregar_top3():
    if os.path.exists(TOP3_PATH):
        with open(TOP3_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_top3(lista):
    with open(TOP3_PATH, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)

# =============================
# Envio Telegram (inalterado)
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        st.warning(f"Erro ao enviar mensagem Telegram: {e}")

def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")

    data_iso = fixture["fixture"]["date"]
    # convertendo para BRT (UTC-3) — assumindo data ISO com 'Z'
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
    except Exception:
        # fallback simples: parse dateEvent + time
        try:
            data_jogo = datetime.strptime(data_iso, "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            data_jogo = datetime.utcnow()
    data_jogo_brt = data_jogo - timedelta(hours=3)
    data_formatada = data_jogo_brt.strftime("%d/%m/%Y")
    hora_formatada = data_jogo_brt.strftime("%H:%M")

    msg = (
        f"⚽ *Alerta de Gols!*\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"🔥 Tendência: {tendencia}\n"
        f"📊 Estimativa: {estimativa:.2f} gols\n"
        f"✅ Confiança: {confianca:.0f}%\n"
        f"📌 Status: {status}\n"
        f"🔢 Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas()
    fixture_id = str(fixture["fixture"]["id"])
    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if (ultimo["home_goals"] != home_goals or
            ultimo["away_goals"] != away_goals or
            ultimo["tendencia"] != tendencia):
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia
        }
        salvar_alertas(alertas)

# =============================
# Tendência / estimativa (mantido)
# =============================
def calcular_tendencia_confianca_realista(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    media_casa_marcados = media_casa.get("media_gols_marcados", 1.5)
    media_casa_sofridos = media_casa.get("media_gols_sofridos", 1.2)
    media_fora_marcados = media_fora.get("media_gols_marcados", 1.4)
    media_fora_sofridos = media_fora.get("media_gols_sofridos", 1.1)
    
    media_time_casa = media_casa_marcados + media_fora_sofridos
    media_time_fora = media_fora_marcados + media_casa_sofridos
    estimativa_base = (media_time_casa + media_time_fora) / 2

    h2h_media = media_h2h.get("media_gols", 2.5) if isinstance(media_h2h, dict) and media_h2h.get("total_jogos",0) > 0 else 2.5
    # Caso media_h2h seja um float (em algumas versões podemos retornar número), tratar:
    if isinstance(media_h2h, (int, float)):
        h2h_media = media_h2h

    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * h2h_media

    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa_final - 2.5) * 15)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa_final - 1.5) * 20)
    else:
        tendencia = "Mais 1.5"
        confianca = max(50, min(75, 55 + (estimativa_final - 1.5) * 20))

    return round(estimativa_final, 2), round(confianca, 0), tendencia

# =============================
# H2H (TheSportsDB) - com cache
# =============================
@st.cache_data(ttl=60)
def media_gols_confrontos_diretos(home_id, away_id, temporada=None, max_jogos=5):
    """
    Tenta obter os últimos confrontos entre home_id e away_id usando TheSportsDB.
    Se não conseguir (ids ausentes ou chamadas falharem), retorna média 0.
    home_id/away_id devem ser ids do TheSportsDB quando possível; se forem nomes, tentamos buscar ID pelo nome.
    """
    try:
        # ajuda: transformar em string sem espaços
        def buscar_id_por_nome(nome):
            if not nome:
                return None
            url = f"{TSDB_BASE}/searchteams.php?t={requests.utils.quote(nome)}"
            r = _safe_get(url)
            if not r or r.status_code != 200:
                return None
            j = r.json()
            teams = j.get("teams") or []
            if not teams:
                return None
            return teams[0].get("idTeam")

        def pegar_eventos_ultimos(team_id, limit):
            url = f"{TSDB_BASE}/eventslast.php?id={team_id}"
            r = _safe_get(url)
            if not r or r.status_code != 200:
                return []
            j = r.json()
            # v1 usa 'results' ou 'events' (varia)
            eventos = j.get("results") or j.get("events") or []
            return eventos[:limit]

        # normalizar ids: se numéricos já ok; se forem None ou texto, tentar buscar por nome
        hid = None
        aid = None
        if home_id:
            hid = str(home_id)
            if not hid.isdigit():
                # tentar buscar id por nome
                hid = buscar_id_por_nome(home_id)
        if away_id:
            aid = str(away_id)
            if not aid.isdigit():
                aid = buscar_id_por_nome(away_id)

        if not hid or not aid:
            return {"media_gols": 0, "total_jogos": 0}

        # buscar últimos eventos do time e filtrar por confrontos contra o outro
        eventos = []
        evs_home = pegar_eventos_ultimos(hid, max_jogos * 5)
        for e in evs_home:
            if str(e.get("idHomeTeam")) == str(aid) or str(e.get("idAwayTeam")) == str(aid):
                # precisa conter placar final
                if e.get("intHomeScore") is None and e.get("intAwayScore") is None:
                    continue
                eventos.append(e)

        # também tentar pelos últimos do away (para pegar eventuais partidas não listadas no primeiro pull)
        if len(eventos) < max_jogos:
            evs_away = pegar_eventos_ultimos(aid, max_jogos * 5)
            for e in evs_away:
                if str(e.get("idHomeTeam")) == str(hid) or str(e.get("idAwayTeam")) == str(hid):
                    if e.get("intHomeScore") is None and e.get("intAwayScore") is None:
                        continue
                    # evitar duplicatas por idEvent
                    if not any(ev.get("idEvent") == e.get("idEvent") for ev in eventos):
                        eventos.append(e)

        if not eventos:
            return {"media_gols": 0, "total_jogos": 0}

        # ordenar por data mais recente e limitar
        eventos = sorted(eventos, key=lambda x: x.get("dateEvent") or "", reverse=True)[:max_jogos]

        total_pontos, total_peso = 0, 0
        for idx, j in enumerate(eventos):
            try:
                home_goals = int(j.get("intHomeScore") or 0)
                away_goals = int(j.get("intAwayScore") or 0)
            except Exception:
                home_goals, away_goals = 0, 0
            gols = (home_goals) + (away_goals)
            peso = max_jogos - idx
            total_pontos += gols * peso
            total_peso += peso

        media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
        return {"media_gols": media_ponderada, "total_jogos": len(eventos)}
    except Exception:
        return {"media_gols": 0, "total_jogos": 0}

# =============================
# Funções médias históricas OpenLigaDB (mantidas)
# =============================
@st.cache_data(ttl=300)
def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}"
        r = _safe_get(url, timeout=15)
        if r and r.status_code == 200:
            return r.json()
    except Exception as e:
        st.warning(f"Erro ao obter jogos OpenLigaDB: {e}")
    return []

def calcular_media_gols_times(jogos_hist):
    stats = {}
    for j in jogos_hist:
        home, away = j["team1"]["teamName"], j["team2"]["teamName"]
        placar = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if not placar:
            continue
        stats.setdefault(home, {"marcados": [], "sofridos": []})
        stats.setdefault(away, {"marcados": [], "sofridos": []})
        stats[home]["marcados"].append(placar[0])
        stats[home]["sofridos"].append(placar[1])
        stats[away]["marcados"].append(placar[1])
        stats[away]["sofridos"].append(placar[0])
    medias = {}
    for time, gols in stats.items():
        media_marcados = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 1.5
        media_sofridos = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 1.2
        medias[time] = {"media_gols_marcados": media_marcados, "media_gols_sofridos": media_sofridos}
    return medias

# =============================
# Função dummy para odds (mantida)
# =============================
def obter_odds(fixture_id):
    try:
        fixture_id_int = int(fixture_id)
    except Exception:
        fixture_id_int = 0
    return {"1.5": round(1.2 + fixture_id_int % 2 * 0.3,2), "2.5": round(1.8 + fixture_id_int % 3 * 0.4,2)}

# =============================
# Conferência dos jogos (com cache) - tenta TheSportsDB -> OpenLigaDB
# =============================
@st.cache_data(ttl=60)
def conferir_jogo(fixture_id, tipo):
    """
    Tenta checar resultado: primeiro TheSportsDB (lookupevent), se não, tenta OpenLigaDB (getmatchdata/{id}).
    Retorna dicionário com estrutura compatível ao código original.
    """
    try:
        # 1) TheSportsDB lookup
        url_tsdb = f"{TSDB_BASE}/lookupevent.php?id={fixture_id}"
        resp = _safe_get(url_tsdb, timeout=10)
        if resp and resp.status_code == 200:
            data = resp.json()
            eventos = data.get("events") or data.get("event") or []
            if eventos:
                e = eventos[0]
                home = e.get("strHomeTeam", "Desconhecido")
                away = e.get("strAwayTeam", "Desconhecido")
                try:
                    gols_home = int(e.get("intHomeScore") or 0)
                    gols_away = int(e.get("intAwayScore") or 0)
                except Exception:
                    gols_home, gols_away = 0, 0
                total_gols = gols_home + gols_away
                if tipo == "1.5":
                    green = total_gols >= 2
                else:
                    green = total_gols >= 3
                return {
                    "home": home, "away": away,
                    "total_gols": total_gols,
                    "aposta": f"+{tipo}",
                    "resultado": "🟢 GREEN" if green else "🔴 RED"
                }

        # 2) OpenLigaDB lookup (getmatchdata/{id})
        url_open = f"{OPENLIGA_BASE}/getmatchdata/{fixture_id}"
        resp2 = _safe_get(url_open, timeout=10)
        if resp2 and resp2.status_code == 200:
            dados = resp2.json()
            # getmatchdata/{id} pode retornar um objeto único ou lista; tratar ambos
            j = dados if isinstance(dados, dict) else (dados[0] if isinstance(dados, list) and dados else None)
            if j:
                # estrutura OpenLigaDB: verificar matchResults para placar final
                home = j.get("team1", {}).get("teamName", "Desconhecido")
                away = j.get("team2", {}).get("teamName", "Desconhecido")
                placar = None
                for r in j.get("matchResults", []):
                    if r.get("resultTypeID") == 2:
                        placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                        break
                if placar:
                    total_gols = placar[0] + placar[1]
                else:
                    total_gols = 0
                if tipo == "1.5":
                    green = total_gols >= 2
                else:
                    green = total_gols >= 3
                return {
                    "home": home, "away": away,
                    "total_gols": total_gols,
                    "aposta": f"+{tipo}",
                    "resultado": "🟢 GREEN" if green else "🔴 RED"
                }

        return None
    except Exception:
        return None

# =============================
# Função auxiliar para buscar jogos do dia (agora usando TheSportsDB) - com cache
# =============================
@st.cache_data(ttl=60)
def obter_jogos_dia(data):
    """
    Retorna lista de 'matches' com formato análogo ao que seu código original esperava (similar ao api-football),
    para minimizar mudanças no restante do app.
    Cada match tem:
    {
      "fixture": {"id": int, "date": ISO_string_with_Z, "status": {"short":..., "long":...}},
      "teams": {"home": {"id":..., "name":...}, "away": {...}},
      "goals": {"home": int, "away": int},
      "league": {"id":..., "name": ...},
      ...
    }
    """
    jogos = []

    # 1) TheSportsDB - eventos do dia
    url_tsdb = f"{TSDB_BASE}/eventsday.php?d={data}&s=Soccer"
    r = _safe_get(url_tsdb, timeout=12)
    if r and r.status_code == 200:
        try:
            payload = r.json()
            events = payload.get("events") or payload.get("results") or []
            for e in events:
                # dateEvent, strEventTime or strTime, idEvent, idHomeTeam, idAwayTeam, strLeague etc.
                date_event = e.get("dateEvent") or e.get("dateEventLocal") or data
                time_event = e.get("strTime") or e.get("strEventTime") or "00:00:00"
                iso_date = f"{date_event}T{time_event}Z"
                try:
                    idEvent = int(e.get("idEvent") or 0)
                except Exception:
                    idEvent = 0
                try:
                    league_id = int(e.get("idLeague") or 0)
                except Exception:
                    league_id = 0
                # montar estrutura compatível
                match = {
                    "fixture": {
                        "id": idEvent,
                        "date": iso_date,
                        "status": {
                            "short": "NS" if (e.get("intHomeScore") is None and e.get("intAwayScore") is None) else "FT",
                            "long": e.get("strProgress") or e.get("strStatus") or ""
                        }
                    },
                    "teams": {
                        "home": {"id": int(e.get("idHomeTeam") or 0), "name": e.get("strHomeTeam") or "Desconhecido"},
                        "away": {"id": int(e.get("idAwayTeam") or 0), "name": e.get("strAwayTeam") or "Desconhecido"}
                    },
                    "goals": {
                        "home": int(e.get("intHomeScore") or 0),
                        "away": int(e.get("intAwayScore") or 0)
                    },
                    "league": {
                        "id": league_id,
                        "name": e.get("strLeague") or "Desconhecido"
                    },
                    # guardar raw para debug se precisar
                    "_raw_source": "TheSportsDB",
                    "_raw_event": e
                }
                jogos.append(match)
        except Exception:
            # se parsing falhar, ignorar TSDB
            pass

    # 2) OpenLigaDB - complementa (apenas se precisar / ex: ligas históricas)
    # Opcional: aqui podemos adicionar partidas de OpenLigaDB do dia se desejar. Como seu código já usa OpenLigaDB para históricos, deixei por agora apenas TSDB para o dia.
    # Se quiser incluir partidas OpenLigaDB do dia, eu posso ativar essa parte também.

    return jogos

# =============================
# Helper para filtrar ligas principais por nome (evita depender de IDs da API-Football)
# =============================
def liga_nao_principal(match, ligas_principais_names):
    league_name = (match.get("league") or {}).get("name", "") or ""
    # compara por substrings (ex: "Bundesliga (OpenLigaDB)" deve bater com "Bundesliga")
    for nome in ligas_principais_names:
        if nome.lower() in league_name.lower():
            return False
    return True

# =============================
# Interface Streamlit (mantive sua UI e fluxo, ajustando pequenos pontos para funcionar com TSDB)
# =============================
st.set_page_config(page_title="⚽ Alertas e Jogos Históricos (TheSportsDB)", layout="wide")
st.title("⚽ Sistema de Alertas de Gols + Jogos Históricos (TheSportsDB + OpenLigaDB)")
aba = st.tabs(["⚡ Alertas de Jogos Hoje", "📊 Jogos de Temporadas Passadas", "🎯 Conferência Top 3"])

# ---------- ABA 1: Alertas ----------
with aba[0]:
    st.subheader("📅 Jogos do dia e alertas de tendência")

    temporada_atual = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)
    data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today().date())
    hoje = data_selecionada.strftime("%Y-%m-%d")

    # Ligas principais: agora filtramos por NOME (não por IDs específicos de outra API)
    ligas_principais_names = [
        "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
        "Brasileirão", "UEFA Champions League", "Copa Libertadores"
    ]

    incluir_todas = st.checkbox("🔎 Buscar jogos de todas as ligas do dia (fora filtro principal)", value=False)

    if st.button("🔍 Buscar jogos do dia"):
        with st.spinner("Buscando jogos na TheSportsDB..."):
            jogos = obter_jogos_dia(hoje)

        # Seleção de liga histórica para médias (OpenLigaDB) - mantive a UI
        liga_nome = st.selectbox("🏆 Escolha a liga histórica para médias:", list({
            "Bundesliga (Alemanha)": "bl1",
            "2. Bundesliga (Alemanha)": "bl2",
            "DFB-Pokal (Alemanha)": "dfb",
            "Premier League (Inglaterra)": "pl",
            "La Liga (Espanha)": "pd"
        }.keys()))
        ligas_openliga = {
            "Bundesliga (Alemanha)": "bl1",
            "2. Bundesliga (Alemanha)": "bl2",
            "DFB-Pokal (Alemanha)": "dfb",
            "Premier League (Inglaterra)": "pl",
            "La Liga (Espanha)": "pd"
        }
        liga_id = ligas_openliga[liga_nome]
        temporada_hist = st.selectbox("📅 Temporada histórica:", ["2022", "2023", "2024", "2025"], index=2)

        jogos_hist = obter_jogos_liga_temporada(liga_id, temporada_hist)
        medias_historicas = calcular_media_gols_times(jogos_hist)

        melhores_15, melhores_25 = [], []

        for match in jogos:
            status = match.get("fixture", {}).get("status", {}).get("short")
            if status != "NS":
                continue  # Só jogos que não começaram

            # filtrar por liga principal (por nome)
            if (not incluir_todas) and liga_nao_principal(match, ligas_principais_names):
                continue

            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            home_id = match["teams"]["home"].get("id")
            away_id = match["teams"]["away"].get("id")

            # Tratar retorno dict ou float para H2H (nosso media_gols_confrontos_diretos já lida com nomes ou ids)
            media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada_atual, max_jogos=5)
            if isinstance(media_h2h, dict):
                media_h2h_val = media_h2h.get("media_gols", 2.5)
            else:
                media_h2h_val = media_h2h

            media_casa = medias_historicas.get(home, {"media_gols_marcados": 1.5, "media_gols_sofridos": 1.2})
            media_fora = medias_historicas.get(away, {"media_gols_marcados": 1.4, "media_gols_sofridos": 1.1})

            estimativa, confianca, tendencia = calcular_tendencia_confianca_realista(
                media_h2h=media_h2h_val,
                media_casa=media_casa,
                media_fora=media_fora
            )

            # Ajuste de timezone (assumi que date string tem 'Z')
            data_iso = match["fixture"]["date"]
            try:
                data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
            except Exception:
                # fallback
                data_jogo = datetime.utcnow() - timedelta(hours=3)
            hora_formatada = data_jogo.strftime("%H:%M")
            competicao = (match.get("league") or {}).get("name", "Desconhecido")

            # Odds com fallback
            odds = obter_odds(match["fixture"]["id"]) or {}
            odd_15 = odds.get("1.5", "N/A")
            odd_25 = odds.get("2.5", "N/A")

            with st.container():
                st.subheader(f"🏟️ {home} vs {away}")
                st.caption(f"Liga: {competicao} | Temporada: {temporada_atual}")
                st.write(f"📊 Estimativa de gols: **{estimativa:.2f}**")
                st.write(f"🔥 Tendência: **{tendencia}**")
                st.write(f"✅ Confiança: **{confianca:.0f}%**")
                st.write(f"💰 Odds Over 1.5: {odd_15} | Over 2.5: {odd_25}")

            verificar_enviar_alerta(match, tendencia, confianca, estimativa)

            if tendencia == "Mais 1.5":
                melhores_15.append({
                    "fixture_id": match["fixture"]["id"],
                    "home": home, "away": away,
                    "estimativa": estimativa, "confianca": confianca,
                    "hora": hora_formatada, "competicao": competicao,
                    "odd_15": odd_15
                })
            elif tendencia == "Mais 2.5":
                melhores_25.append({
                    "fixture_id": match["fixture"]["id"],
                    "home": home, "away": away,
                    "estimativa": estimativa, "confianca": confianca,
                    "hora": hora_formatada, "competicao": competicao,
                    "odd_25": odd_25
                })

        # =====================================================
        # 🏆 Ranking final Top 3 (igual ao seu fluxo)
        # =====================================================
        if melhores_15:
            st.markdown("## 🏆 Top 3 Jogos com tendência **+1.5 gols**")
            top15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
            for jogo in top15:
                st.write(
                    f"⚽ {jogo['home']} vs {jogo['away']} "
                    f"({jogo['hora']}, {jogo['competicao']})\n"
                    f"📊 Estimativa: {jogo['estimativa']:.2f} | "
                    f"✅ Confiança: {jogo['confianca']:.0f}% | "
                    f"💰 Odd +1.5: {jogo['odd_15']}"
                )

        if melhores_25:
            st.markdown("## 🏆 Top 3 Jogos com tendência **+2.5 gols**")
            top25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
            for jogo in top25:
                st.write(
                    f"⚽ {jogo['home']} vs {jogo['away']} "
                    f"({jogo['hora']}, {jogo['competicao']})\n"
                    f"📊 Estimativa: {jogo['estimativa']:.2f} | "
                    f"✅ Confiança: {jogo['confianca']:.0f}% | "
                    f"💰 Odd +2.5: {jogo['odd_25']}"
                )

        # Top 3 consolidation + envio
        melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
        melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

        if melhores_15 or melhores_25:
            msg_alt = "📢 *TOP ENTRADAS - Alertas Consolidados*\n\n"
            if melhores_15:
                odd_combinada_15 = 1
                msg_alt += "🔥 Top 3 Jogos para +1.5 Gols\n"
                for j in melhores_15:
                    odd_combinada_15 *= float(j.get("odd_15") or 1)
                    msg_alt += (
                        f"🏆 {j['competicao']}\n"
                        f"🕒 {j['hora']} BRT\n"
                        f"🏟️ {j['home']} vs {j['away']}\n"
                        f"📊 Estimativa: {j['estimativa']:.2f} | ✅ Confiança: {j['confianca']:.0f}%\n"
                        f"💰 Odd: {j.get('odd_15', 'N/A')}\n\n"
                    )
                msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_15:.2f}\n\n"

            if melhores_25:
                odd_combinada_25 = 1
                msg_alt += "⚡ Top 3 Jogos para +2.5 Gols\n"
                for j in melhores_25:
                    odd_combinada_25 *= float(j.get("odd_25") or 1)
                    msg_alt += (
                        f"🏆 {j['competicao']}\n"
                        f"🕒 {j['hora']} BRT\n"
                        f"🏟️ {j['home']} vs {j['away']}\n"
                        f"📊 Estimativa: {j['estimativa']:.2f} | ✅ Confiança: {j['confianca']:.0f}%\n"
                        f"💰 Odd: {j.get('odd_25', 'N/A')}\n\n"
                    )
                msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_25:.2f}\n\n"

            enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
            st.success("🚀 Top jogos enviados para o canal alternativo 2!")

            # Salva o Top3 no histórico (persistência)
            top3_list = carregar_top3()
            novo_top = {
                "data_envio": hoje,
                "hora_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "melhores_15": melhores_15,
                "melhores_25": melhores_25
            }
            top3_list.append(novo_top)
            salvar_top3(top3_list)
        else:
            st.info("Nenhum jogo com tendência clara de +1.5 ou +2.5 gols encontrado.")

# ---------- ABA 2: Jogos históricos ----------
with aba[1]:
    st.subheader("📊 Jogos de Temporadas Passadas (OpenLigaDB)")
    temporada_hist = st.selectbox("📅 Escolha a temporada histórica:", ["2022", "2023", "2024", "2025"], index=2, key="hist")
    liga_nome_hist = st.selectbox("🏆 Escolha a Liga:", list({
        "Bundesliga (Alemanha)": "bl1",
        "2. Bundesliga (Alemanha)": "bl2",
        "DFB Pokal": "dfb",
        "Premier League (Inglaterra)": "pl",
        "La Liga (Espanha)": "pd"
    }.keys()), key="hist_liga")
    ligas_openliga2 = {
        "Bundesliga (Alemanha)": "bl1",
        "2. Bundesliga (Alemanha)": "bl2",
        "DFB Pokal": "dfb",
        "Premier League (Inglaterra)": "pl",
        "La Liga (Espanha)": "pd"
    }
    liga_id_hist = ligas_openliga2[liga_nome_hist]

    if st.button("🔍 Buscar jogos da temporada", key="btn_hist"):
        with st.spinner("Buscando jogos..."):
            jogos_hist = obter_jogos_liga_temporada(liga_id_hist, temporada_hist)
            if not jogos_hist:
                st.info("Nenhum jogo encontrado para essa temporada/liga.")
            else:
                st.success(f"{len(jogos_hist)} jogos encontrados na {liga_nome_hist} ({temporada_hist})")
                for j in jogos_hist[:50]:  # Limite de exibição inicial
                    home = j["team1"]["teamName"]
                    away = j["team2"]["teamName"]
                    placar = "-"
                    for r in j.get("matchResults", []):
                        if r.get("resultTypeID") == 2:
                            placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                            break
                    data = j.get("matchDateTime") or j.get("matchDateTimeUTC") or "Desconhecida"
                    st.write(f"🏟️ {home} vs {away} | 📅 {data} | ⚽ Placar: {placar}")

# ---------- ABA 3: Conferência Top 3 ----------
with aba[2]:
    st.subheader("🎯 Conferência dos Top 3 enviados")
    top3_salvos = carregar_top3()

    if not top3_salvos:
        st.info("Nenhum Top 3 registrado ainda. Gere e envie um Top 3 na aba 'Alertas de Jogos Hoje'.")
    else:
        st.write(f"✅ Total de envios registrados: {len(top3_salvos)}")
        options = [f"{idx+1} - {t['data_envio']} ({t['hora_envio']})" for idx, t in enumerate(top3_salvos)]
        seletor = st.selectbox("Selecione o lote Top3 para conferir:", options, index=len(options)-1)
        idx_selecionado = options.index(seletor)

        lote = top3_salvos[idx_selecionado]
        st.markdown(f"### Lote selecionado — Envio: **{lote['data_envio']}** às **{lote['hora_envio']}**")
        st.markdown("---")

        btn_recheck = st.button("🔄 Rechecar resultados agora")

        def processar_lote(lote):
            resultados = []
            greens, reds = 0, 0
            detalhes = []

            # Processa +1.5
            for j in lote.get("melhores_15", []):
                fixture_id = j.get("fixture_id")
                info = conferir_jogo(fixture_id, "1.5")
                if not info:
                    detalhes.append({
                        "home": j.get("home"),
                        "away": j.get("away"),
                        "aposta": "+1.5",
                        "status": "Não encontrado / API"
                    })
                    continue
                detalhes.append({
                    "home": info["home"],
                    "away": info["away"],
                    "aposta": info["aposta"],
                    "total_gols": info["total_gols"],
                    "resultado": info["resultado"]
                })
                if "GREEN" in info["resultado"]:
                    greens += 1
                else:
                    reds += 1

            # Processa +2.5
            for j in lote.get("melhores_25", []):
                fixture_id = j.get("fixture_id")
                info = conferir_jogo(fixture_id, "2.5")
                if not info:
                    detalhes.append({
                        "home": j.get("home"),
                        "away": j.get("away"),
                        "aposta": "+2.5",
                        "status": "Não encontrado / API"
                    })
                    continue
                detalhes.append({
                    "home": info["home"],
                    "away": info["away"],
                    "aposta": info["aposta"],
                    "total_gols": info["total_gols"],
                    "resultado": info["resultado"]
                })
                if "GREEN" in info["resultado"]:
                    greens += 1
                else:
                    reds += 1

            total = greens + reds
            taxa = (greens / total * 100) if total > 0 else 0
            resumo = {"greens": greens, "reds": reds, "total": total, "taxa": round(taxa, 1)}
            return detalhes, resumo

        with st.spinner("Conferindo resultados..."):
            detalhes, resumo = processar_lote(lote)

        for d in detalhes:
            if d.get("status") == "Não encontrado / API":
                st.warning(f"🏟️ {d['home']} vs {d['away']} — {d['aposta']} — {d['status']}")
            else:
                resultado_text = d["resultado"]
                gols = d.get("total_gols", "-")
                if "GREEN" in resultado_text:
                    st.success(f"🏟️ {d['home']} vs {d['away']} | Gols: {gols} | {d['aposta']} → {resultado_text}")
                else:
                    st.error(f"🏟️ {d['home']} vs {d['away']} | Gols: {gols} | {d['aposta']} → {resultado_text}")

        st.markdown("---")
        st.markdown(f"**Resumo do lote:** 🟢 {resumo['greens']} GREEN | 🔴 {resumo['reds']} RED | Total verificados: {resumo['total']}")
        st.markdown(f"**Taxa de acerto:** {resumo['taxa']}%")

        if st.button("📥 Exportar relatório JSON deste lote"):
            nome_arquivo = f"relatorio_top3_{lote['data_envio'].replace('/','-')}_{lote['hora_envio'].replace(':','-').replace(' ','_')}.json"
            rel = {"lote": lote, "detalhes": detalhes, "resumo": resumo}
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(rel, f, ensure_ascii=False, indent=2)
            st.success(f"Relatório salvo: {nome_arquivo}")

# Fim do arquivo
