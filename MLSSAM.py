import streamlit as st
import requests
import json
import os
import io
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import time

# =============================
# Configurações
# =============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

ALERTAS_PATH = "alertas.json"

# =============================
# Cache de alertas
# =============================
def carregar_alertas() -> dict:
    if os.path.exists(ALERTAS_PATH):
        try:
            with open(ALERTAS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_alertas(alertas: dict):
    with open(ALERTAS_PATH, "w", encoding="utf-8") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

# =============================
# Função para buscar dados da ESPN
# =============================
def buscar_dados_espn():
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dados = response.json()
        partidas = []

        for evento in dados.get("events", []):
            nome = evento.get("name", "")
            status = evento.get("status", {}).get("type", {}).get("description", "")
            hora = evento.get("date", "")
            hora_formatada = (
                datetime.fromisoformat(hora.replace("Z", "+00:00")) - timedelta(hours=3)
            ).strftime("%d/%m/%Y %H:%M") if hora else ""

            competicao = evento.get("competitions", [{}])[0]
            times = competicao.get("competitors", [])

            if len(times) == 2:
                home = times[0]["team"]["displayName"]
                away = times[1]["team"]["displayName"]
                placar_home = int(times[0].get("score") or 0)
                placar_away = int(times[1].get("score") or 0)
            else:
                home = away = placar_home = placar_away = 0

            partidas.append({
                "id": evento.get("id"),
                "home": home,
                "away": away,
                "score_home": placar_home,
                "score_away": placar_away,
                "status": status,
                "hora": hora_formatada,
                "competition": competicao.get("league", {}).get("displayName", "MLS")
            })

        return partidas

    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Função de tendência simples
# =============================
def calcular_tendencia(home, away, score_home, score_away):
    """
    Calcula uma tendência simples baseada em gols marcados.
    """
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
# Envio Telegram
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.get(url, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
        return response.status_code == 200
    except:
        return False

# =============================
# Verifica e envia alertas
# =============================
def verificar_enviar_alerta(jogo):
    alertas = carregar_alertas()
    fixture_id = str(jogo["id"])

    # Calcula tendência
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
        # Envia alerta
        msg = (
            f"⚽ <b>Alerta de Gols!</b>\n"
            f"🏟️ {jogo['home']} vs {jogo['away']}\n"
            f"📅 {jogo['hora']}\n"
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

    atualizacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(f"🕒 **Última atualização:** {atualizacao} | Atualização automática a cada 15 minutos.")

    partidas = buscar_dados_espn()
    if not partidas:
        st.warning("⚠️ Nenhum jogo disponível no momento.")
        return

    # Calcula tendências antes de exibir
    for p in partidas:
        estimativa, confianca, tendencia = calcular_tendencia(
            p["home"], p["away"], p["score_home"], p["score_away"]
        )
        p["estimativa"] = estimativa
        p["confianca"] = confianca
        p["tendencia"] = tendencia
        verificar_enviar_alerta(p)

    df = pd.DataFrame(partidas)
    st.dataframe(df, use_container_width=True)

    st.info("ℹ️ Alertas enviados para Telegram automaticamente.")

    # Atualização automática
    with st.empty():
        while True:
            time.sleep(900)
            st.experimental_rerun()

if __name__ == "__main__":
    main()
