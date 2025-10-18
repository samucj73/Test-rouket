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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-100XXXXXXXXX")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-100XXXXXXXXX")

BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# =============================
# Utilitários de Cache
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Erro ao carregar {caminho}: {e}")
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar {caminho}: {e}")

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Função para buscar jogos MLS da ESPN
# =============================
def obter_jogos_espn(data: str) -> list:
    cache = carregar_cache_jogos()
    if data in cache:
        jogos = cache[data]
        for j in jogos:
            j["hora"] = datetime.fromisoformat(j["hora"])
        return jogos

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
            hora_dt = datetime.fromisoformat(hora.replace("Z", "+00:00")) - timedelta(hours=3)

            jogos.append({
                "id": evento.get("id"),
                "home": home,
                "away": away,
                "score_home": score_home,
                "score_away": score_away,
                "status": status,
                "hora": hora_dt,
                "competition": competicao.get("league", {}).get("displayName", "MLS")
            })

        # Salvar cache (hora como string ISO)
        cache_salvar = []
        for j in jogos:
            j_copy = j.copy()
            j_copy["hora"] = j_copy["hora"].isoformat()
            cache_salvar.append(j_copy)

        cache[data] = cache_salvar
        salvar_cache_jogos(cache)

        return jogos

    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Função de envio Telegram
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    try:
        response = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
        return response.status_code == 200
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")
        return False

# =============================
# Análise simples (Mais/Menos 2.5)
# =============================
def calcular_tendencia(score_home, score_away):
    total = score_home + score_away
    if total > 2:
        return "Mais 2.5", total
    else:
        return "Menos 2.5", total

def enviar_alerta_jogo(jogo):
    tendencia, total = calcular_tendencia(jogo["score_home"], jogo["score_away"])
    msg = (
        f"⚽ <b>{jogo['home']} vs {jogo['away']}</b>\n"
        f"🏆 Liga: {jogo['competition']}\n"
        f"🕒 Horário: {jogo['hora'].strftime('%d/%m %H:%M')}\n"
        f"📈 Tendência: <b>{tendencia}</b> | Total gols: {total}\n"
        f"📌 Status: {jogo['status']}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ MLS - Elite", layout="wide")
    st.title("⚽ MLS - Elite - Alertas Automáticos")

    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Top N Jogos", [3,5,10], index=0)

    # Colunas principais
    col1, col2 = st.columns(2)
    with col1:
        data_selecionada = st.date_input("📅 Data dos Jogos", value=datetime.today())
    with col2:
        st.info("Atualização automática a cada 15 minutos")

    # Botões principais
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 Buscar Jogos"):
            processar_jogos(data_selecionada, top_n)
    with col2:
        if st.button("🔄 Atualizar Status"):
            st.success("✅ Status atualizado (simulação)")
    with col3:
        if st.button("🧹 Limpar Cache"):
            limpar_cache()

def processar_jogos(data_selecionada, top_n):
    data_str = data_selecionada.strftime("%Y-%m-%d")
    jogos = obter_jogos_espn(data_str)
    if not jogos:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
        return

    # Mostrar tabela
    tabela = []
    for j in jogos:
        tabela.append({
            "Mandante": j["home"],
            "Visitante": j["away"],
            "Placar": f"{j['score_home']} - {j['score_away']}",
            "Status": j["status"],
            "Horário": j["hora"].strftime("%d/%m %H:%M"),
            "Competição": j["competition"]
        })
    st.dataframe(pd.DataFrame(tabela), use_container_width=True)

    # Enviar Top N jogos para Telegram
    jogos_ordenados = sorted(jogos, key=lambda x: x["score_home"]+x["score_away"], reverse=True)[:top_n]
    for j in jogos_ordenados:
        enviar_alerta_jogo(j)
    st.success(f"🚀 Top {top_n} jogos enviados para o Telegram!")

def limpar_cache():
    for f in [CACHE_JOGOS, ALERTAS_PATH]:
        if os.path.exists(f):
            os.remove(f)
    st.success("✅ Cache limpo com sucesso!")

if __name__ == "__main__":
    main()
