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
import time

# =============================
# Configurações e Segurança
# =============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Cache
# =============================
def carregar_json(caminho: str) -> dict:
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Comunicação com Telegram
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

# =============================
# Obter jogos da ESPN
# =============================
def obter_jogos_espn(data: str) -> list:
    """
    Retorna os jogos da MLS (ESPN) filtrados pela data (YYYY-MM-DD)
    """
    cache = carregar_cache_jogos()
    if data in cache:
        return cache[data]

    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dados = response.json()
        jogos = []

        for evento in dados.get("events", []):
            hora = evento.get("date")
            if not hora:
                continue
            # Filtrar pela data
            data_jogo = datetime.fromisoformat(hora.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            if data_jogo != data:
                continue

            competicao = evento.get("competitions", [{}])[0]
            times = competicao.get("competitors", [])
            if len(times) != 2:
                continue

            home = times[0]["team"]["displayName"]
            away = times[1]["team"]["displayName"]
            score_home = int(times[0].get("score") or 0)
            score_away = int(times[1].get("score") or 0)
            status = evento.get("status", {}).get("type", {}).get("description", "SCHEDULED")

            jogos.append({
                "id": evento.get("id"),
                "home": home,
                "away": away,
                "score_home": score_home,
                "score_away": score_away,
                "status": status,
                "hora": datetime.fromisoformat(hora.replace("Z", "+00:00")) - timedelta(hours=3),
                "competition": competicao.get("league", {}).get("displayName", "MLS")
            })

        cache[data] = jogos
        salvar_cache_jogos(cache)
        return jogos

    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Lógica de tendência
# =============================
def calcular_tendencia(home, away, score_home, score_away):
    total_gols = score_home + score_away
    if total_gols >= 3:
        tendencia = "Mais 2.5"
    elif total_gols >= 2:
        tendencia = "Mais 1.5"
    else:
        tendencia = "Menos 2.5"
    confianca = min(95, 60 + total_gols*10)
    estimativa = total_gols if total_gols > 0 else 1.5
    return estimativa, confianca, tendencia

# =============================
# Verificar e enviar alerta
# =============================
def verificar_enviar_alerta(jogo):
    alertas = carregar_alertas()
    fixture_id = str(jogo["id"])

    estimativa, confianca, tendencia = calcular_tendencia(
        jogo["home"], jogo["away"], jogo["score_home"], jogo["score_away"]
    )
    jogo["estimativa"] = estimativa
    jogo["confianca"] = confianca
    jogo["tendencia"] = tendencia

    if fixture_id not in alertas:
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        msg = (
            f"⚽ <b>Alerta de Gols!</b>\n"
            f"🏟️ {jogo['home']} vs {jogo['away']}\n"
            f"📅 {jogo['hora'].strftime('%d/%m/%Y %H:%M')}\n"
            f"📈 Tendência: <b>{tendencia}</b>\n"
            f"🎯 Estimativa: <b>{estimativa:.2f}</b>\n"
            f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
            f"🏆 Liga: {jogo['competition']}"
        )
        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
        salvar_alertas(alertas)

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ MLS Alerts", layout="wide")
    st.title("⚽ Sistema de Alertas MLS - ESPN")

    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)

    if st.button("🔍 Buscar Partidas"):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        jogos = obter_jogos_espn(hoje)

        if not jogos:
            st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
            return

        # Calcular tendência e enviar alertas
        for jogo in jogos:
            verificar_enviar_alerta(jogo)

        # Ordenar por confiança
        top_jogos = sorted(jogos, key=lambda x: x["confianca"], reverse=True)[:top_n]
        df = pd.DataFrame(top_jogos)
        st.dataframe(df, use_container_width=True)
        st.success(f"✅ {len(jogos)} jogos processados e alertas enviados!")

    if st.button("🧹 Limpar Cache"):
        for arquivo in [CACHE_JOGOS, ALERTAS_PATH]:
            if os.path.exists(arquivo):
                os.remove(arquivo)
        st.success("✅ Cache limpo!")

if __name__ == "__main__":
    main()
