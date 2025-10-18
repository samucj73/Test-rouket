import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import time
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# ⚙️ Configurações gerais
# =============================
st.set_page_config(page_title="⚽ Alerta MLS - ESPN", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos - MLS (ESPN)")

# Telegram
TELEGRAM_TOKEN = "SEU_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
TELEGRAM_CHAT_ID_ALT2 = "SEU_CHAT_ID_SECUNDARIO"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Cache
CACHE_PATH = "cache_espn.json"
ALERTAS_PATH = "alertas_espn.json"
CACHE_TIMEOUT = 900  # 15 minutos

# =============================
# Funções de cache
# =============================
def carregar_json(caminho):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# =============================
# Buscar dados da ESPN
# =============================
def buscar_dados_espn():
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        dados = r.json()
        partidas = []

        for evento in dados.get("events", []):
            nome = evento.get("name", "")
            status = evento.get("status", {}).get("type", {}).get("description", "")
            hora = evento.get("date", "")
            hora_formatada = (
                datetime.fromisoformat(hora.replace("Z", "+00:00")) - timedelta(hours=3)
            ).strftime("%d/%m/%Y %H:%M") if hora else ""

            competicao = evento.get("competitions", [])[0]
            times = competicao.get("competitors", [])

            if len(times) == 2:
                home = times[0]["team"]["displayName"]
                away = times[1]["team"]["displayName"]
                placar_home = int(times[0].get("score", 0) or 0)
                placar_away = int(times[1].get("score", 0) or 0)
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
                "competition": competicao.get("name", "MLS")
            })
        return partidas
    except Exception as e:
        st.error(f"Erro ao buscar dados da ESPN: {e}")
        return []

# =============================
# Enviar Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

# =============================
# Calcular tendência
# =============================
def calcular_tendencia(home, away, score_home, score_away):
    """Simples lógica de tendência: Mais 1.5, Mais 2.5, Menos 2.5"""
    total_gols = score_home + score_away
    if total_gols >= 3:
        return total_gols, 80, "Mais 2.5"
    elif total_gols >= 2:
        return total_gols, 70, "Mais 1.5"
    else:
        return total_gols, 60, "Menos 2.5"

# =============================
# Processar alertas
# =============================
def processar_alertas(partidas):
    alertas = carregar_json(ALERTAS_PATH)
    novas_alertas = []

    for p in partidas:
        pid = str(p["id"])
        estimativa, confianca, tendencia = calcular_tendencia(p["home"], p["away"], p["score_home"], p["score_away"])
        p.update({"estimativa": estimativa, "confianca": confianca, "tendencia": tendencia})

        if pid not in alertas:
            msg = (
                f"⚽ <b>{p['home']} vs {p['away']}</b>\n"
                f"🕒 {p['hora']}\n"
                f"📊 Status: {p['status']}\n"
                f"📌 Placar: {p['score_home']} - {p['score_away']}\n"
                f"📈 Tendência: {tendencia} | Estimativa: {estimativa}\n"
                f"🏆 Liga: {p['competition']}"
            )
            enviar_telegram(msg)
            alertas[pid] = p
            novas_alertas.append(p)

    if novas_alertas:
        salvar_json(ALERTAS_PATH, alertas)

    return novas_alertas

# =============================
# Interface Streamlit
# =============================
def main():
    st.sidebar.header("Configurações")
    top_n = st.sidebar.selectbox("📊 Top N jogos", [3,5,10], index=0)

    atualizacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(f"🕒 Última atualização: {atualizacao}")

    partidas = buscar_dados_espn()
    if partidas:
        df = pd.DataFrame([{
            "Mandante": p["home"],
            "Visitante": p["away"],
            "Placar": f"{p['score_home']} - {p['score_away']}",
            "Status": p["status"],
            "Horário": p["hora"],
            "Tendência": p["tendencia"],
            "Estimativa": p["estimativa"],
            "Confiança": p["confianca"]
        } for p in partidas])
        st.dataframe(df, use_container_width=True)
        novas_alertas = processar_alertas(partidas)

        # Top N jogos
        top_jogos = sorted(novas_alertas, key=lambda x: x["confianca"], reverse=True)[:top_n]
        if top_jogos:
            msg_top = f"📢 TOP {top_n} Jogos MLS do Dia\n\n"
            for j in top_jogos:
                msg_top += (
                    f"🏟️ {j['home']} vs {j['away']}\n"
                    f"🕒 {j['hora']} | Status: {j['status']}\n"
                    f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']} | "
                    f"💯 Confiança: {j['confianca']}\n\n"
                )
            enviar_telegram(msg_top, TELEGRAM_CHAT_ID_ALT2)
            st.success("🚀 Top jogos enviados para o Telegram!")
    else:
        st.warning("⚠️ Nenhum jogo disponível no momento.")

    # Atualização automática a cada 15 minutos
    time.sleep(CACHE_TIMEOUT)
    st.experimental_rerun()

if __name__ == "__main__":
    main()
