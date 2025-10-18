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
# Configurações e Segurança
# =============================
API_KEY = os.getenv("FOOTBALL_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "")

BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
BASE_URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Dicionário de Ligas (ESPN slugs)
# =============================
LIGA_DICT = {
    "FIFA World Cup": "worldcup",
    "UEFA Champions League": "champions-league",
    "Bundesliga": "bundesliga",
    "Eredivisie": "eredivisie",
    "Campeonato Brasileiro Série A": "brasileirao-serie-a",
    "Primera Division": "primera-division",
    "Ligue 1": "ligue-1",
    "Championship (Inglaterra)": "championship",
    "Primeira Liga (Portugal)": "primeira-liga",
    "European Championship": "uefa-euro",
    "Serie A (Itália)": "serie-a",
    "Premier League (Inglaterra)": "premier-league"
}

# =============================
# Funções de Cache
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            if caminho == CACHE_JOGOS and '_timestamp' in dados:
                agora = datetime.now().timestamp()
                if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                    return {}
            return dados
    except:
        return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    if caminho == CACHE_JOGOS:
        dados['_timestamp'] = datetime.now().timestamp()
    with open(caminho, "w", encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_alertas():
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos():
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Formatação e utilitários
# =============================
def formatar_data_iso(data_iso: str):
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except:
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15):
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Comunicação com Telegram
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    try:
        response = requests.get(
            BASE_URL_TG, 
            params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

# =============================
# Obter jogos da ESPN
# =============================
def obter_jogos_espn(liga_slug: str, data: str):
    cache = carregar_cache_jogos()
    key = f"{liga_slug}_{data}"
    if key in cache:
        return cache[key]["matches"]

    url = f"{BASE_URL_ESPN}/{liga_slug}/scoreboard?dates={data.replace('-', '')}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data_json = resp.json()
        partidas = data_json.get("events", [])
        jogos = []
        for p in partidas:
            comp = p.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue
            home_team = competitors[0]["team"]["displayName"]
            away_team = competitors[1]["team"]["displayName"]
            score_home = competitors[0].get("score")
            score_away = competitors[1].get("score")
            jogos.append({
                "id": p.get("id"),
                "homeTeam": {"name": home_team},
                "awayTeam": {"name": away_team},
                "utcDate": p.get("date"),
                "status": p.get("status", {}).get("type", {}).get("name", "SCHEDULED"),
                "competition": {"name": comp.get("league", {}).get("name", liga_slug)},
                "score": {"fullTime": {"home": int(score_home) if score_home else None,
                                       "away": int(score_away) if score_away else None}}
            })
        cache[key] = {"matches": jogos, "_timestamp": datetime.now().timestamp()}
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Cálculo de tendência simples
# =============================
def calcular_tendencia(home, away, classificacao=None):
    # Simplificado: random para demo (ou usar estatísticas reais)
    estimativa = 2.1
    confianca = 70
    tendencia = "Mais 1.5"
    return estimativa, confianca, tendencia

def enviar_alerta_telegram(fixture, tendencia, estimativa, confianca):
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    gols_home = fixture.get("score", {}).get("fullTime", {}).get("home")
    gols_away = fixture.get("score", {}).get("fullTime", {}).get("away")
    placar = f"{gols_home} x {gols_away}" if gols_home is not None and gols_away is not None else None

    msg = (
        f"⚽ <b>Alerta de Gols!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"📌 Status: {fixture.get('status','SCHEDULED')}\n"
    )
    if placar:
        msg += f"📊 Placar: <b>{placar}</b>\n"
    msg += (
        f"📈 Tendência: <b>{tendencia}</b>\n"
        f"🎯 Estimativa: <b>{estimativa:.2f} gols</b>\n"
        f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
        f"🏆 Liga: {competicao}"
    )
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca, "conferido": False}
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Streamlit Interface
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols - ESPN", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos (ESPN)")

    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Top jogos", [3, 5, 10], index=0)

    data_selecionada = st.date_input("📅 Data para análise:", datetime.today())
    todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)
    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))

    if st.button("🔍 Buscar Partidas"):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]
        top_jogos = []
        for liga_slug in ligas_busca:
            jogos = obter_jogos_espn(liga_slug, hoje)
            for match in jogos:
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                estimativa, confianca, tendencia = calcular_tendencia(home, away)
                
                verificar_enviar_alerta(match, tendencia, estimativa, confianca)
                
                top_jogos.append({
                    "id": match["id"],
                    "home": home,
                    "away": away,
                    "tendencia": tendencia,
                    "estimativa": estimativa,
                    "confianca": confianca,
                    "liga": match.get("competition", {}).get("name", liga_slug),
                    "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3),
                    "status": match.get("status", "SCHEDULED")
                })
        
        # Enviar Top N jogos
        if top_jogos:
            enviar_top_jogos(top_jogos, top_n)
            st.success(f"✅ {len(top_jogos)} jogos processados e alertas enviados.")
        else:
            st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")

def enviar_top_jogos(jogos: list, top_n: int):
    # Filtrar apenas jogos não finalizados
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINAL", "IN_PROGRESS", "POSTPONED"]]
    if not jogos_filtrados:
        st.warning("⚠️ Todos os jogos já iniciados ou finalizados.")
        return
    # Ordenar por confiança
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
    
    msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
    for j in top_jogos_sorted:
        hora_format = j["hora"].strftime("%H:%M")
        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
            f"💯 Confiança: {j['confianca']:.0f}%\n\n"
        )
    if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2):
        st.success(f"🚀 Top {top_n} jogos enviados ao Telegram!")
    else:
        st.error("❌ Erro ao enviar Top jogos para o Telegram.")

if __name__ == "__main__":
    main()
