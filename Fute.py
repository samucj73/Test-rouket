# Fut_Alertas_TheSportsDB_Full.py
"""
Versão completa:
- TheSportsDB v1 (free) + v2 (livescore, leagues) com fallback
- OpenLigaDB para históricos / fallback
- Cache inteligente (st.cache_data + optional diskcache)
- Rate limiter adaptativo (_safe_get)
- Lógica de tendência: +1.5, +2.5, BTTS
- Persistência: alertas.json, top3.json
- Telegram alerts with duplicate control
- UI muito próximo ao código original do usuário
"""

import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json
import time
import math
from typing import List, Dict, Any

# Optional disk cache for cross-process cache (faster recovery after restart).
try:
    from diskcache import Cache
    DISK_CACHE_AVAILABLE = True
except Exception:
    DISK_CACHE_AVAILABLE = False

# =============================
# CONFIGURAÇÕES (preferência: variáveis de ambiente)
# =============================
THE_SPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "3")   # '3' é a key pública para v1; v2 precisa da sua key
BASE_V1 = f"https://www.thesportsdb.com/api/v1/json/{THE_SPORTSDB_KEY}"
BASE_V2 = "https://www.thesportsdb.com/api/v2/json"
# HEADERS V2 — somente usado se você tiver key real
HEADERS_V2 = {"X-API-KEY": os.getenv("THESPORTSDB_KEY", ""), "Content-Type": "application/json"}

OPENLIGA_BASE = "https://api.openligadb.de"

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "")

# Arquivos de persistência
ALERTAS_PATH = "alertas.json"
TOP3_PATH = "top3.json"

# Rate limiting / retry defaults
_MIN_REQUEST_INTERVAL = 0.8   # mínimo entre requisições
_last_request_time = 0.0
_RATE_BACKOFF_MULT = 1.5      # multiplicador para backoff adaptativo
_MAX_RETRIES = 2

# Disk cache (opcional)
if DISK_CACHE_AVAILABLE:
    disk_cache = Cache("./.diskcache_thesportsdb")

# =============================
# UTILITÁRIOS: cache helpers (st.cache_data + optional diskcache)
# =============================
def diskcache_get(key):
    if DISK_CACHE_AVAILABLE:
        return disk_cache.get(key)
    return None

def diskcache_set(key, value, expire=None):
    if DISK_CACHE_AVAILABLE:
        if expire:
            disk_cache.set(key, value, expire=expire)
        else:
            disk_cache.set(key, value)

# =============================
# RATE-LIMITED GET (adaptive) — usa _safe_get em todo lugar
# =============================
def _safe_get(url: str, headers: Dict[str, str] = None, timeout: int = 10, allow_retry: bool = True):
    """
    Faz GET com rate limiting local simples e backoff adaptativo em caso de falha.
    Retorna requests.Response ou None.
    """
    global _last_request_time
    attempt = 0
    backoff = _MIN_REQUEST_INTERVAL
    while True:
        # throttle to avoid bursts
        now = time.time()
        gap = now - _last_request_time
        if gap < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - gap)

        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            _last_request_time = time.time()
            # 429 or 5xx => consider retry
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                attempt += 1
                if attempt > _MAX_RETRIES or not allow_retry:
                    return resp
                # exponential-ish backoff
                sleep_for = backoff * (_RATE_BACKOFF_MULT ** (attempt - 1))
                time.sleep(sleep_for)
                continue
            return resp
        except requests.exceptions.RequestException:
            attempt += 1
            if attempt > _MAX_RETRIES or not allow_retry:
                return None
            time.sleep(backoff)
            backoff *= _RATE_BACKOFF_MULT

# =============================
# PERSISTÊNCIA — carregar / salvar JSON
# =============================
def carregar_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def salvar_json(path: str, payload):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Erro salvando {path}: {e}")

# alertas / top3 helpers
def carregar_alertas():
    return carregar_json(ALERTAS_PATH, {})

def salvar_alertas(d):
    salvar_json(ALERTAS_PATH, d)

def carregar_top3():
    return carregar_json(TOP3_PATH, [])

def salvar_top3(l):
    salvar_json(TOP3_PATH, l)

# =============================
# TELEGRAM — envio
# =============================
def enviar_telegram_text(msg: str, chat_id: str = None):
    if not chat_id:
        chat_id = TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not chat_id:
        st.warning("Telegram não configurado (TELEGRAM_TOKEN/CHAT_ID faltando).")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        return True
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")
        return False

# =============================
# THE SPORTS DB: helpers (v1 + v2)
# =============================
# Format helpers: vamos padronizar o formato de "match" para preservar lógica antiga
def _format_match_from_tsdb_event(e: dict) -> dict:
    """
    Retorna estrutura compatível com o modelo original:
    {
      "fixture": {"id": int, "date": ISO_Z, "status": {"short": "...", "long": "..."}},
      "teams": {"home": {"id": ..., "name": ...}, "away": {...}},
      "goals": {"home": int, "away": int},
      "league": {"id": ..., "name": ...},
      "_raw_source": "TheSportsDB"
    }
    """
    # dateEvent e strTime podem vir como 'YYYY-MM-DD' + 'HH:MM:SS' (local) — construímos um ISO com Z
    date_event = e.get("dateEvent") or e.get("dateEventLocal") or None
    time_event = e.get("strTime") or e.get("strEventTime") or "00:00:00"
    if date_event:
        iso = f"{date_event}T{time_event}Z"
    else:
        iso = datetime.utcnow().isoformat() + "Z"

    try:
        idEvent = int(e.get("idEvent") or 0)
    except Exception:
        idEvent = 0

    short_status = "NS" if (e.get("intHomeScore") is None and e.get("intAwayScore") is None) else "FT"
    long_status = e.get("strStatus") or ""

    try:
        home_id = int(e.get("idHomeTeam") or 0)
    except Exception:
        home_id = 0
    try:
        away_id = int(e.get("idAwayTeam") or 0)
    except Exception:
        away_id = 0

    match = {
        "fixture": {
            "id": idEvent,
            "date": iso,
            "status": {"short": short_status, "long": long_status}
        },
        "teams": {
            "home": {"id": home_id, "name": e.get("strHomeTeam") or "Desconhecido"},
            "away": {"id": away_id, "name": e.get("strAwayTeam") or "Desconhecido"}
        },
        "goals": {
            "home": int(e.get("intHomeScore") or 0),
            "away": int(e.get("intAwayScore") or 0)
        },
        "league": {
            "id": int(e.get("idLeague") or 0),
            "name": e.get("strLeague") or "Desconhecido"
        },
        "_raw_source": "TheSportsDB",
        "_raw_event": e
    }
    return match

# CACHE: get eventsday (v1) — TTL 15m, cached with st.cache_data and optional diskcache
@st.cache_data(ttl=900)
def _tsdb_eventsday_v1(data: str) -> List[dict]:
    """eventsday.php?d=YYYY-MM-DD&s=Soccer (v1)"""
    url = f"{BASE_V1}/eventsday.php?d={data}&s=Soccer"
    resp = _safe_get(url, timeout=12)
    events = []
    if resp and resp.status_code == 200:
        try:
            js = resp.json()
            events = js.get("events") or []
        except Exception:
            events = []
    # persist to disk cache optionally
    if DISK_CACHE_AVAILABLE:
        diskcache_set(f"tsdb_v1_eventsday_{data}", events, expire=900)
    return events

def _tsdb_eventsday_v1_diskfallback(data: str):
    # helper to read from diskcache if st.cache_data empty/fails
    if DISK_CACHE_AVAILABLE:
        key = f"tsdb_v1_eventsday_{data}"
        return diskcache_get(key) or []
    return []

# V2 livescore endpoint — cached shorter (30s) because is live
@st.cache_data(ttl=30)
def _tsdb_livescore_v2() -> List[dict]:
    """v2 livescore - requires X-API-KEY in headers (if provided). Returns events list."""
    url = f"{BASE_V2}/livescore/soccer"
    headers = HEADERS_V2 if HEADERS_V2.get("X-API-KEY") else None
    resp = _safe_get(url, headers=headers, timeout=10)
    if resp and resp.status_code == 200:
        try:
            js = resp.json()
            # v2 may return {"events": [...]} or similar
            return js.get("events") or js.get("results") or []
        except Exception:
            return []
    return []

# Function to get events by date using v2 then v1 fallback
def obter_jogos_thesportsdb_por_data(data: str) -> List[dict]:
    """
    Retorna lista de matches no formato do app (como _format_match_from_tsdb_event).
    Busca v2 livescore + v1 eventsday; remove duplicados por idEvent.
    """
    events = []
    # 1) try v2 livescore (fast, cached)
    try:
        v2 = _tsdb_livescore_v2()
        for ev in v2:
            # v2 events may include dateEvent
            if ev.get("dateEvent") == data:
                events.append(ev)
    except Exception:
        v2 = []

    # 2) fallback / complement: v1 eventsday
    try:
        v1 = _tsdb_eventsday_v1(data)
        if not v1:
            # try disk fallback
            v1 = _tsdb_eventsday_v1_diskfallback(data)
        for ev in v1:
            # append if not duplicate by idEvent or by (home, away, date)
            events.append(ev)
    except Exception:
        pass

    # normalize and deduplicate by (idEvent if present else home+away+date)
    seen = set()
    matches = []
    for ev in events:
        idEvent = str(ev.get("idEvent") or "")
        key = idEvent
        if not idEvent:
            # fallback key
            key = f"{ev.get('dateEvent')}_{ev.get('strHomeTeam')}_{ev.get('strAwayTeam')}"
        if key in seen:
            continue
        seen.add(key)
        matches.append(_format_match_from_tsdb_event(ev))
    return matches

# =============================
# OPENLIGA: histórico / fallback
# =============================
@st.cache_data(ttl=300)
def obter_jogos_liga_temporada_openliga(liga_id: str, temporada: str):
    """getmatchdata/{liga}/{temporada}"""
    try:
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}"
        r = _safe_get(url, timeout=15)
        if r and r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

# =============================
# Estatísticas da liga (lookuptable.php v1)
# =============================
@st.cache_data(ttl=86400)
def obter_estatisticas_liga_tsdb(liga_id: str, temporada: str) -> Dict[str, dict]:
    """
    Usa lookuptable.php?l={id}&s={season}
    Retorna dict: {teamName: {"media_pro":..., "media_contra":..., "jogos": ...}}
    """
    try:
        url = f"{BASE_V1}/lookuptable.php?l={liga_id}&s={temporada}"
        resp = _safe_get(url, timeout=12)
        if resp and resp.status_code == 200:
            js = resp.json()
            table = js.get("table") or []
            stats = {}
            for row in table:
                name = row.get("strTeam") or row.get("name") or row.get("team")
                try:
                    played = int(row.get("intPlayed") or 0)
                except Exception:
                    played = 0
                try:
                    goals_for = int(row.get("intGoalsFor") or 0)
                    goals_against = int(row.get("intGoalsAgainst") or 0)
                except Exception:
                    goals_for = 0
                    goals_against = 0
                if played > 0:
                    media_pro = goals_for / played
                    media_contra = goals_against / played
                else:
                    media_pro = 1.0
                    media_contra = 1.0
                stats[name] = {
                    "media_pro": round(media_pro, 2),
                    "media_contra": round(media_contra, 2),
                    "media_total": round(media_pro + media_contra, 2),
                    "jogos": played
                }
            # save to diskcache optionally
            if DISK_CACHE_AVAILABLE:
                diskcache_set(f"tsdb_table_{liga_id}_{temporada}", stats, expire=86400)
            return stats
    except Exception:
        pass
    # disk fallback
    if DISK_CACHE_AVAILABLE:
        cached = diskcache_get(f"tsdb_table_{liga_id}_{temporada}")
        if cached:
            return cached
    return {}

# =============================
# H2H média (usando eventslast.php e lookupevent.php)
# =============================
@st.cache_data(ttl=60)
def media_gols_confrontos_diretos_tsdb(home_id, away_id, temporada=None, max_jogos=5):
    """
    Tenta obter confrontos Diretos usando:
    - lookupevent.php?id={event_id} para eventos específicos, ou
    - eventslast.php?id={team_id} para últimos do time e filtrar
    Aceita IDs numéricos ou strings (nome) — tentamos resolver nome->id via searchteams.php
    """
    # helpers
    def buscar_team_id_por_nome(nome: str):
        if not nome:
            return None
        url = f"{BASE_V1}/searchteams.php?t={requests.utils.quote(nome)}"
        r = _safe_get(url, timeout=10)
        if not r or r.status_code != 200:
            return None
        try:
            j = r.json()
            teams = j.get("teams") or []
            if not teams:
                return None
            return teams[0].get("idTeam")
        except Exception:
            return None

    try:
        hid = home_id
        aid = away_id
        # if names passed (strings), try fetch ids
        if isinstance(home_id, str) and not home_id.isdigit():
            hid = buscar_team_id_por_nome(home_id)
        if isinstance(away_id, str) and not away_id.isdigit():
            aid = buscar_team_id_por_nome(away_id)
        if not hid or not aid:
            return {"media_gols": 0, "total_jogos": 0}

        # pegar últimos jogos do home e filtrar contra away
        eventos = []
        url_home_last = f"{BASE_V1}/eventslast.php?id={hid}"
        r = _safe_get(url_home_last, timeout=10)
        if r and r.status_code == 200:
            try:
                j = r.json()
                evs = j.get("results") or j.get("events") or []
                for ev in evs:
                    # comparar idHomeTeam/idAwayTeam com aid
                    if str(ev.get("idHomeTeam")) == str(aid) or str(ev.get("idAwayTeam")) == str(aid):
                        # needs final score
                        if ev.get("intHomeScore") is None and ev.get("intAwayScore") is None:
                            continue
                        eventos.append(ev)
            except Exception:
                pass

        # if not enough, check away last
        if len(eventos) < max_jogos:
            url_away_last = f"{BASE_V1}/eventslast.php?id={aid}"
            r2 = _safe_get(url_away_last, timeout=10)
            if r2 and r2.status_code == 200:
                try:
                    j2 = r2.json()
                    evs2 = j2.get("results") or j2.get("events") or []
                    for ev in evs2:
                        if (str(ev.get("idHomeTeam")) == str(hid) or str(ev.get("idAwayTeam")) == str(hid)):
                            if ev.get("intHomeScore") is None and ev.get("intAwayScore") is None:
                                continue
                            if not any(ev.get("idEvent") == e.get("idEvent") for e in eventos):
                                eventos.append(ev)
                except Exception:
                    pass

        if not eventos:
            return {"media_gols": 0, "total_jogos": 0}

        # sort by dateEvent desc and limit
        eventos_sorted = sorted(eventos, key=lambda x: x.get("dateEvent") or "", reverse=True)[:max_jogos]
        total_p = 0
        total_peso = 0
        for idx, ev in enumerate(eventos_sorted):
            try:
                gh = int(ev.get("intHomeScore") or 0)
                ga = int(ev.get("intAwayScore") or 0)
            except:
                gh, ga = 0, 0
            gols = gh + ga
            peso = max_jogos - idx
            total_p += gols * peso
            total_peso += peso
        media_ponderada = round(total_p / total_peso, 2) if total_peso else 0
        return {"media_gols": media_ponderada, "total_jogos": len(eventos_sorted)}
    except Exception:
        return {"media_gols": 0, "total_jogos": 0}

# =============================
# Conferência de jogo (para verificar Top3) — tenta TSDB -> OpenLigaDB
# =============================
@st.cache_data(ttl=60)
def conferir_jogo_unificado(fixture_id, tipo):
    """
    Recebe fixture_id (idEvent do TheSportsDB ou matchId do OpenLigaDB).
    Primeiro tenta lookupevent.php?id={fixture_id} (TSDB v1), caso não encontre tenta OpenLigaDB getmatchdata/{id}.
    Retorna dict: {home, away, total_gols, aposta, resultado}
    """
    # 1) lookupevent TSDB
    try:
        url_tsdb = f"{BASE_V1}/lookupevent.php?id={fixture_id}"
        r = _safe_get(url_tsdb, timeout=10)
        if r and r.status_code == 200:
            js = r.json()
            evs = js.get("events") or js.get("event") or []
            if evs:
                e = evs[0]
                try:
                    gh = int(e.get("intHomeScore") or 0)
                    ga = int(e.get("intAwayScore") or 0)
                except:
                    gh, ga = 0, 0
                total = gh + ga
                green = (total >= 2) if tipo == "1.5" else (total >= 3)
                return {
                    "home": e.get("strHomeTeam", "Desconhecido"),
                    "away": e.get("strAwayTeam", "Desconhecido"),
                    "total_gols": total,
                    "aposta": f"+{tipo}",
                    "resultado": "🟢 GREEN" if green else "🔴 RED"
                }
    except Exception:
        pass

    # 2) OpenLigaDB fallback
    try:
        url_open = f"{OPENLIGA_BASE}/getmatchdata/{fixture_id}"
        r2 = _safe_get(url_open, timeout=10)
        if r2 and r2.status_code == 200:
            dados = r2.json()
            j = dados if isinstance(dados, dict) else (dados[0] if isinstance(dados, list) and dados else None)
            if j:
                home = j.get("team1", {}).get("teamName", "Desconhecido")
                away = j.get("team2", {}).get("teamName", "Desconhecido")
                placar = None
                for res in j.get("matchResults", []):
                    if res.get("resultTypeID") == 2:
                        placar = (res.get("pointsTeam1", 0), res.get("pointsTeam2", 0))
                        break
                total = sum(placar) if placar else 0
                green = (total >= 2) if tipo == "1.5" else (total >= 3)
                return {
                    "home": home,
                    "away": away,
                    "total_gols": total,
                    "aposta": f"+{tipo}",
                    "resultado": "🟢 GREEN" if green else "🔴 RED"
                }
    except Exception:
        pass
    return None

# =============================
# ANALISE: +1.5, +2.5, BTTS
# =============================
def calcular_tendencia_confianca(media_h2h, media_casa, media_fora, peso_h2h=0.25):
    """
    Versão robusta da sua função anterior: usa medias de casa/fora e h2h se disponível.
    Output: (estimativa_total_gols, confianca_percent, tendencia_string)
    """
    # extrair valores com fallback
    mc_marc = media_casa.get("media_pro", 1.5) if isinstance(media_casa, dict) else 1.5
    mc_sof = media_casa.get("media_contra", 1.2) if isinstance(media_casa, dict) else 1.2
    mf_marc = media_fora.get("media_pro", 1.4) if isinstance(media_fora, dict) else 1.4
    mf_sof = media_fora.get("media_contra", 1.1) if isinstance(media_fora, dict) else 1.1

    media_time_casa = mc_marc + mf_sof
    media_time_fora = mf_marc + mc_sof
    estimativa_base = (media_time_casa + media_time_fora) / 2

    if isinstance(media_h2h, dict):
        h2h_media = media_h2h.get("media_gols", 2.5)
    elif isinstance(media_h2h, (int, float)):
        h2h_media = media_h2h
    else:
        h2h_media = 2.5

    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * h2h_media

    # Map to tendência + confianza
    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(98, 60 + (estimativa_final - 2.5) * 18)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 50 + (estimativa_final - 1.5) * 25)
    else:
        tendencia = "Menos 1.5"
        confianca = max(30, min(70, 40 + (estimativa_final - 1.0) * 20))

    return round(estimativa_final, 2), round(confianca, 0), tendencia

def prever_btts(media_casa, media_fora, threshold=0.9):
    """
    Estimativa simplificada para BTTS: se ambos times têm média_pro > threshold => provável BTTS.
    Retorna probabilidade aproximada (0-1).
    """
    p_home_scores = min(1.0, (media_casa.get("media_pro", 1.0) / 2.0))  # heurística
    p_away_scores = min(1.0, (media_fora.get("media_pro", 1.0) / 2.0))
    prob = p_home_scores * p_away_scores  # independente (heurística)
    return round(prob, 2)

# =============================
# UNIFICAR JOGOS (TSDB + OpenLiga opcional)
# =============================
def obter_jogos_unificados(data: str, incluir_openliga_dia: bool = True) -> List[dict]:
    """
    Retorna lista de matches prontos pra análise (no formato usado por rest do app).
    - TheSportsDB events (v2 livescore + v1 eventsday)
    - se incluir_openliga_dia: tenta obter jogos OpenLiga do dia (pouco usado; serve para ligas suportadas)
    """
    matches = obter_jogos_thesportsdb_por_data(data)

    if incluir_openliga_dia:
        # tentar algumas ligas comuns (pode ser customizado)
        # OpenLigaDB não tem endpoint 'events by date' direto para todas ligas; mas podemos obter por liga id se souber
        # Aqui mantemos a função caso queira ativar manualmente
        pass

    # já chegam no formato compatível com o resto do seu app
    return matches

# =============================
# Função principal para processar e enviar alertas — preserva lógica original
# =============================
def processar_e_enviar_alertas(jogos: List[dict], liga_id_para_estatisticas: str, temporada_hist: str, enviar_para_telegram=True):
    """
    Recebe lista de 'jogos' no formato unificado e avalia cada jogo:
      - calcula medias através de obter_estatisticas_liga_tsdb (cache)
      - calcula média H2H (cache)
      - calcula estimativa/confianca/tendencia
      - monta Top lists (melhores_15, melhores_25)
      - envia alertas unitários e consolidado Top3 (controlando duplicados por arquivo alertas.json)
    """
    medias_historicas = obter_estatisticas_liga_tsdb(liga_id_para_estatisticas, temporada_hist)
    melhores_15, melhores_25 = [], []
    # carregar alertas para controle de duplicados
    alertas_state = carregar_alertas()

    for match in jogos:
        status_short = (match.get("fixture", {}).get("status", {}) or {}).get("short", "NS")
        # consider only not started as candidates for pre-game alerts (same behaviour as original)
        if status_short != "NS":
            # skip matches already started (original script did skip)
            continue

        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        home_id = match["teams"]["home"].get("id")
        away_id = match["teams"]["away"].get("id")

        # Get h2h media
        media_h2h_obj = media_gols_confrontos_diretos_tsdb(home_id, away_id, temporada_hist, max_jogos=5)
        media_h2h_val = media_h2h_obj.get("media_gols", 2.5) if isinstance(media_h2h_obj, dict) else 2.5

        # Get historical team stats (from lookuptable)
        media_casa = medias_historicas.get(home, {"media_pro": 1.2, "media_contra": 1.2, "media_total": 2.4})
        media_fora = medias_historicas.get(away, {"media_pro": 1.2, "media_contra": 1.2, "media_total": 2.4})

        estimativa, confianca, tendencia = calcular_tendencia_confianca(media_h2h_obj, media_casa, media_fora, peso_h2h=0.25)
        # BTTS prob
        prob_btts = prever_btts(media_casa, media_fora)

        # Prepare display date/time
        data_iso = match["fixture"]["date"]
        try:
            data_dt = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)  # BRT offset
        except Exception:
            data_dt = datetime.utcnow() - timedelta(hours=3)
        hora_formatada = data_dt.strftime("%H:%M")
        competicao = (match.get("league") or {}).get("name", "Desconhecido")

        # Odds fallback (user original had dummy function, reuse)
        odd_obj = obter_odds_dummy(match["fixture"]["id"])
        odd_15 = odd_obj.get("1.5", "N/A")
        odd_25 = odd_obj.get("2.5", "N/A")

        # Build single alert text (compact)
        # We'll use fixture unique id (string) to control duplicates
        fixture_uid = str(match["fixture"]["id"])

        # Should send individual alert? follow original rules: send when first found or when status changes
        send_single = False
        ultimo = alertas_state.get(fixture_uid)
        # We'll consider change in 'tendencia' as reason to re-send OR if not exist
        if not ultimo:
            send_single = True
        else:
            if ultimo.get("tendencia") != tendencia:
                send_single = True

        if send_single and enviar_para_telegram:
            # Compose a compact alert (two-line)
            msg = (
                f"⚽ *Alerta* — {competicao}\n"
                f"{home} x {away} — {hora_formatada} (BRT)\n"
                f"🔥 Tendência: *{tendencia}* | ✅ Confiança: *{confianca}%*\n"
                f"📊 Est: *{estimativa}* gols | BTTS prob: *{prob_btts}*\n"
                f"💰 Odds (fict): 1.5:{odd_15} 2.5:{odd_25}"
            )
            enviar_telegram_text(msg, TELEGRAM_CHAT_ID)
            # update state
            alertas_state[fixture_uid] = {"tendencia": tendencia, "home_goals": 0, "away_goals": 0, "last_sent": datetime.utcnow().isoformat()}
            salvar_alertas(alertas_state)

        # Add to potential top lists
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

    # Consolidate Top3 lists and send combined message to alt channel (if any)
    melhores_15_sorted = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
    melhores_25_sorted = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

    if (melhores_15_sorted or melhores_25_sorted) and enviar_para_telegram:
        msg_alt = "📢 *TOP ENTRADAS - Alertas Consolidados*\n\n"
        if melhores_15_sorted:
            msg_alt += "🔥 Top +1.5\n"
            odd_comb_15 = 1.0
            for it in melhores_15_sorted:
                try:
                    odd_comb_15 *= float(it.get("odd_15") or 1)
                except:
                    odd_comb_15 *= 1
                msg_alt += f"🏟 {it['competicao']} — {it['hora']} — {it['home']} x {it['away']} — Est: {it['estimativa']} | Conf: {it['confianca']}% | Odd:{it.get('odd_15','N/A')}\n"
            msg_alt += f"🎯 Odd combinada: {round(odd_comb_15,2)}\n\n"

        if melhores_25_sorted:
            msg_alt += "⚡ Top +2.5\n"
            odd_comb_25 = 1.0
            for it in melhores_25_sorted:
                try:
                    odd_comb_25 *= float(it.get("odd_25") or 1)
                except:
                    odd_comb_25 *= 1
                msg_alt += f"🏟 {it['competicao']} — {it['hora']} — {it['home']} x {it['away']} — Est: {it['estimativa']} | Conf: {it['confianca']}% | Odd:{it.get('odd_25','N/A')}\n"
            msg_alt += f"🎯 Odd combinada: {round(odd_comb_25,2)}\n\n"

        enviar_telegram_text(msg_alt, TELEGRAM_CHAT_ID_ALT2)
        # salvar top3 no histórico
        top3_history = carregar_top3()
        novo_top = {"data_envio": datetime.utcnow().strftime("%Y-%m-%d"), "hora_envio": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "melhores_15": melhores_15_sorted, "melhores_25": melhores_25_sorted}
        top3_history.append(novo_top)
        salvar_top3(top3_history)

    return {"melhores_15": melhores_15_sorted, "melhores_25": melhores_25_sorted}

# =============================
# Dummy odds (como seu código original tinha)
# =============================
def obter_odds_dummy(fixture_id):
    try:
        fid = int(fixture_id)
    except Exception:
        fid = 1
    return {"1.5": round(1.2 + fid % 2 * 0.3, 2), "2.5": round(1.8 + fid % 3 * 0.4, 2)}

# =============================
# Streamlit UI — muito parecido com sua versão original
# =============================
st.set_page_config(page_title="⚽ Alertas (TheSportsDB + OpenLigaDB)", layout="wide")
st.title("⚽ Sistema de Alertas de Gols (TheSportsDB + OpenLigaDB)")
aba = st.tabs(["⚡ Alertas de Jogos Hoje", "📊 Jogos de Temporadas Passadas", "🎯 Conferência Top 3"])

# ---------- ABA 1 ----------
with aba[0]:
    st.subheader("📅 Jogos do dia e alertas de tendência")

    temporada_atual = st.selectbox("📅 Escolha a temporada (para H2H/estatísticas no lookuptable):", ["2022-2023", "2023-2024", "2024-2025"], index=2)
    data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today().date())
    hoje = data_selecionada.strftime("%Y-%m-%d")

    # Lista de ligas principais (por substring) — usado para filtrar por nome de liga
    ligas_principais_names = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Brasileirão", "UEFA Champions League", "Copa Libertadores"]

    incluir_todas = st.checkbox("🔎 Buscar jogos de todas as ligas do dia (fora filtro principal)", value=False)
    incluir_openliga_dia = st.checkbox("📎 Incluir OpenLigaDB (busca adicional de ligas históricas)", value=False)

    if st.button("🔍 Buscar jogos do dia"):
        with st.spinner("Buscando jogos (TheSportsDB + OpenLigaDB onde aplicável)..."):
            jogos = obter_jogos_unificados(hoje, incluir_openliga_dia)

        # Seleção de liga histórica (OpenLigaDB) — mantive para cálculo de medias históricas
        liga_nome = st.selectbox("🏆 Escolha a liga histórica para médias (OpenLigaDB):", list({
            "Bundesliga (Alemanha)": "bl1",
            "2. Bundesliga (Alemanha)": "bl2",
            "DFB-Pokal (Alemanha)": "dfb",
            "Premier League (Inglaterra)": "pl",
            "La Liga (Espanha)": "pd"
        }.keys()))
        ligas_openliga = {"Bundesliga (Alemanha)": "bl1", "2. Bundesliga (Alemanha)": "bl2", "DFB-Pokal (Alemanha)": "dfb", "Premier League (Inglaterra)": "pl", "La Liga (Espanha)": "pd"}
        liga_id_openliga = ligas_openliga[liga_nome]
        temporada_hist = st.selectbox("📅 Temporada histórica (para OpenLigaDB):", ["2022", "2023", "2024", "2025"], index=2)

        # Mostrar resultados
        if not jogos:
            st.info("Nenhum jogo encontrado para esta data.")
        else:
            st.success(f"🔎 {len(jogos)} jogos encontrados para {hoje}")
            melhores_15, melhores_25 = [], []
            # display basic info and compute tendencies
            for match in jogos:
                status = match.get("fixture", {}).get("status", {}).get("short")
                # show only scheduled (original logic) — display all though
                home = match["teams"]["home"]["name"]
                away = match["teams"]["away"]["name"]
                competicao = (match.get("league") or {}).get("name", "Desconhecido")
                # parse time for display
                try:
                    dt = datetime.fromisoformat(match["fixture"]["date"].replace("Z", "+00:00")) - timedelta(hours=3)
                    hora_format = dt.strftime("%H:%M")
                except Exception:
                    hora_format = match["fixture"]["date"]
                with st.container():
                    st.subheader(f"🏟️ {home} vs {away}")
                    st.caption(f"Liga: {competicao}")
                    st.write(f"🕒 {hora_format} BRT | Status: {status}")
                    # compute simple preview stats (using lookuptable for league if possible)
                    # fallback: show goals if present
                    gh = match.get("goals", {}).get("home", 0)
                    ga = match.get("goals", {}).get("away", 0)
                    if gh or ga:
                        st.write(f"🔢 Placar atual: {gh} x {ga}")

            # Agora rodar processo completo (inclui envio de alerts e top3)
            resultado = processar_e_enviar_alertas(jogos, liga_id_para_estatisticas=liga_id_openliga, temporada_hist=temporada_hist, enviar_para_telegram=True)
