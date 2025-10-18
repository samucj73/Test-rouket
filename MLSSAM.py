import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import pandas as pd

# =============================
# Configurações
# =============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-100XXXXXXXXX")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-100XXXXXXXXX")

BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Dicionário de ligas ESPN
# =============================
LIGAS_ESPN = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "Liga MX (México)": "mex.1",
    "Saudi Pro League (Arábia)": "sau.1",
    "Copa Libertadores (América do Sul)": "copa.lib",
    "Copa Sudamericana": "copa.sud"
}

# =============================
# Funções de cache
# =============================
def carregar_json(caminho: str) -> dict:
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_json(caminho: str, dados: dict):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# =============================
# Buscar jogos ESPN por liga e data
# =============================
def obter_jogos_espn(liga_id: str, data: str) -> list:
    cache = carregar_json(CACHE_JOGOS)
    key = f"{liga_id}_{data}"
    if key in cache:
        jogos = cache[key]
        for j in jogos:
            j["hora"] = datetime.fromisoformat(j["hora"])
        return jogos

    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_id}/scoreboard"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        dados = resp.json()
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
                "competition": competicao.get("league", {}).get("displayName", liga_id)
            })

        # Salvar cache
        cache_salvar = []
        for j in jogos:
            j_copy = j.copy()
            j_copy["hora"] = j_copy["hora"].isoformat()
            cache_salvar.append(j_copy)

        cache[key] = cache_salvar
        salvar_json(CACHE_JOGOS, cache)

        return jogos
    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Funções de Telegram e tendência
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

def calcular_tendencia(score_home, score_away):
    total = score_home + score_away
    if total > 2:
        return "Mais 2.5", total
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
    st.set_page_config(page_title="⚽ ESPN Soccer - Elite", layout="wide")
    st.title("⚽ ESPN Soccer - Elite - Alertas Automáticos")

    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)
        top_n = st.selectbox("📊 Top N Jogos", [3,5,10], index=0)
        liga_escolhida = None
        if not todas_ligas:
            liga_escolhida = st.selectbox("📌 Escolha a Liga", list(LIGAS_ESPN.keys()))

    # Data
    data_selecionada = st.date_input("📅 Data dos Jogos", value=datetime.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Botões
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 Buscar Jogos"):
            ligas_busca = LIGAS_ESPN.values() if todas_ligas else [LIGAS_ESPN[liga_escolhida]]
            processar_jogos(data_str, ligas_busca, top_n)
    with col2:
        if st.button("🔄 Atualizar Status"):
            st.success("✅ Status atualizado (simulação)")
    with col3:
        if st.button("🧹 Limpar Cache"):
            for f in [CACHE_JOGOS, ALERTAS_PATH]:
                if os.path.exists(f):
                    os.remove(f)
            st.success("✅ Cache limpo!")

def processar_jogos(data_str, ligas_busca, top_n):
    todos_jogos = []
    for liga in ligas_busca:
        jogos = obter_jogos_espn(liga, data_str)
        todos_jogos.extend(jogos)

    if not todos_jogos:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
        return

    # Mostrar tabela
    tabela = []
    for j in todos_jogos:
        tabela.append({
            "Mandante": j["home"],
            "Visitante": j["away"],
            "Placar": f"{j['score_home']} - {j['score_away']}",
            "Status": j["status"],
            "Horário": j["hora"].strftime("%d/%m %H:%M"),
            "Competição": j["competition"]
        })
    st.dataframe(pd.DataFrame(tabela), use_container_width=True)

    # Top N e enviar Telegram
    jogos_ordenados = sorted(todos_jogos, key=lambda x: x["score_home"]+x["score_away"], reverse=True)[:top_n]
    for j in jogos_ordenados:
        enviar_alerta_jogo(j)
    st.success(f"🚀 Top {top_n} jogos enviados para o Telegram!")

if __name__ == "__main__":
    main()
