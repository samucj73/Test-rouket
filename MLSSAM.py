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
# Configurações e Tokens
# =============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
BASE_URL_API = "https://test-rouket-nvgsix9abxckpjrnlfz79b.streamlit.app/api"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Funções de Cache
# =============================
def carregar_json(caminho: str) -> dict:
    if os.path.exists(caminho):
        with open(caminho, "r", encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def salvar_json(caminho: str, dados: dict):
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

def carregar_cache_classificacao():
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Comunicação Telegram
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

# =============================
# API Nova - Ligas e Jogos
# =============================
def obter_ligas_disponiveis() -> dict:
    """Retorna {nome_liga: id_liga}"""
    try:
        r = requests.get(f"{BASE_URL_API}/ligas", timeout=10)
        r.raise_for_status()
        dados = r.json()
        return {liga["nome"]: liga["id"] for liga in dados.get("ligas", [])}
    except Exception as e:
        st.error(f"Erro ao buscar ligas: {e}")
        return {}

def obter_jogos_nova_api(liga_id: str, data: str) -> list:
    """Retorna lista de jogos para a liga e data"""
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache and (datetime.now().timestamp() - cache[key].get("_timestamp", 0) < CACHE_TIMEOUT):
        return cache[key]["jogos"]

    try:
        r = requests.get(f"{BASE_URL_API}/jogos?liga={liga_id}&data={data}", timeout=10)
        r.raise_for_status()
        jogos = r.json().get("jogos", [])
        cache[key] = {"_timestamp": datetime.now().timestamp(), "jogos": jogos}
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.error(f"Erro ao buscar jogos: {e}")
        return []

def obter_classificacao_nova_api(liga_id: str) -> dict:
    """Retorna classificação da liga"""
    cache = carregar_cache_classificacao()
    if liga_id in cache and (datetime.now().timestamp() - cache[liga_id].get("_timestamp", 0) < CACHE_TIMEOUT):
        return cache[liga_id]["classificacao"]

    try:
        r = requests.get(f"{BASE_URL_API}/classificacao?liga={liga_id}", timeout=10)
        r.raise_for_status()
        classificacao = r.json().get("classificacao", {})
        cache[liga_id] = {"_timestamp": datetime.now().timestamp(), "classificacao": classificacao}
        salvar_cache_classificacao(cache)
        return classificacao
    except Exception as e:
        st.error(f"Erro ao buscar classificação: {e}")
        return {}

# =============================
# Lógica de Tendência de Gols
# =============================
def calcular_tendencia(home: str, away: str, classificacao: dict) -> tuple[float, float, str]:
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})

    played_home = max(dados_home.get("played", 1), 1)
    played_away = max(dados_away.get("played", 1), 1)

    media_home_feitos = dados_home.get("scored",0)/played_home
    media_home_sofridos = dados_home.get("against",0)/played_home
    media_away_feitos = dados_away.get("scored",0)/played_away
    media_away_sofridos = dados_away.get("against",0)/played_away

    estimativa = ((media_home_feitos + media_away_sofridos)/2 + (media_away_feitos + media_home_sofridos)/2)

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0) * 10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0) * 10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa) * 10)

    return estimativa, confianca, tendencia

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    home = fixture["home"]
    away = fixture["away"]
    data_formatada = fixture.get("data", "Desconhecida")
    hora_formatada = fixture.get("hora", "Desconhecida")
    competicao = fixture.get("liga", "Desconhecida")

    msg = (
        f"⚽ <b>Alerta de Gols!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada}\n"
        f"📈 Tendência: <b>{tendencia}</b>\n"
        f"🎯 Estimativa: <b>{estimativa:.2f} gols</b>\n"
        f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
        f"🏆 Liga: {competicao}"
    )
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    alertas = carregar_alertas()
    fixture_id = str(fixture.get("id"))
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca, "conferido": False}
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols - Nova API", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols (Nova API)")

    ligas_disponiveis = obter_ligas_disponiveis()
    if not ligas_disponiveis:
        st.warning("Nenhuma liga disponível no momento.")
        return

    # Sidebar
    with st.sidebar:
        top_n = st.selectbox("📊 Jogos no Top", [3,5,10], index=0)
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica", list(ligas_disponiveis.keys()))

    # Data
    data_selecionada = st.date_input("📅 Data para análise", value=datetime.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")

    if st.button("🔍 Buscar Partidas"):
        ligas_busca = list(ligas_disponiveis.values()) if todas_ligas else [ligas_disponiveis[liga_selecionada]]
        top_jogos = []
        st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
        progress_bar = st.progress(0)
        total_ligas = len(ligas_busca)

        for i, liga_id in enumerate(ligas_busca):
            classificacao = obter_classificacao_nova_api(liga_id)
            jogos = obter_jogos_nova_api(liga_id, data_str)

            for match in jogos:
                home = match.get("home", "Desconhecido")
                away = match.get("away", "Desconhecido")
                estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)

                verificar_enviar_alerta(match, tendencia, estimativa, confianca)

                hora_jogo = match.get("hora", "00:00")
                top_jogos.append({
                    "id": match.get("id"),
                    "home": home,
                    "away": away,
                    "tendencia": tendencia,
                    "estimativa": estimativa,
                    "confianca": confianca,
                    "liga": match.get("liga", "Desconhecido"),
                    "hora": hora_jogo,
                    "status": match.get("status", "DESCONHECIDO"),
                })

            progress_bar.progress((i+1)/total_ligas)

        # Exibir e enviar top jogos
        if top_jogos:
            enviar_top_jogos(top_jogos, top_n)
            st.success(f"✅ Análise concluída! {len(top_jogos)} jogos processados.")
        else:
            st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")

def enviar_top_jogos(jogos: list, top_n: int):
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    if not jogos_filtrados:
        st.warning("⚠️ Nenhum jogo elegível para o Top Jogos.")
        return

    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]

    msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
    for j in top_jogos_sorted:
        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {j['hora']} | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
            f"💯 Confiança: {j['confianca']:.0f}%\n\n"
        )

    if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2):
        st.success(f"🚀 Top {top_n} jogos enviados para o canal!")
    else:
        st.error("❌ Erro ao enviar top jogos para o Telegram")

# =============================
# Execução
# =============================
if __name__ == "__main__":
    main()
