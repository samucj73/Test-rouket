import streamlit as st
from datetime import datetime, timedelta
import requests

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

def enviar_telegram(msg, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

# =============================
# Configurações API (exemplo Football-Data.org)
# =============================
API_KEY = "SUA_API_KEY"
BASE_URL = "https://api.football-data.org/v4/matches"
HEADERS = {"X-Auth-Token": API_KEY}

# =============================
# Ligas disponíveis (exemplo)
# =============================
liga_dict = {
    "English Premier League": 2021,
    "Spanish La Liga": 2014,
    "Bundesliga (Alemanha)": 2002
}

# =============================
# Funções de API e processamento
# =============================
def obter_jogos(liga_id, data):
    """Busca jogos de uma liga em uma data específica"""
    url = f"{BASE_URL}?competitions={liga_id}&dateFrom={data}&dateTo={data}"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except Exception as e:
        st.error(f"Erro ao obter jogos: {e}")
        return []

def calcular_tendencia(home, away, classificacao):
    """Retorna estimativa, confiança e tendência"""
    # Exemplo fictício - substituir com lógica real
    estimativa = 1.5
    confianca = 70
    tendencia = "Mais de 1.5 gols"
    return estimativa, confianca, tendencia

def verificar_enviar_alerta(match, tendencia, estimativa, confianca):
    """Função para alertar via Telegram"""
    msg = (
        f"🏟️ {match['homeTeam']['name']} vs {match['awayTeam']['name']}\n"
        f"Tendência: {tendencia} | Estimativa: {estimativa:.2f} | Confiança: {confianca}%"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

# =============================
# Streamlit App
# =============================
st.title("📊 Alertas de Jogos e Estimativas de Gols")

# Seleção de data
data_selecionada = st.date_input("Escolha a data dos jogos:", value=datetime.today())

# Seleção de liga
liga_selecionada = st.selectbox("Escolha a liga:", list(liga_dict.keys()))

# Botão para buscar partidas
if st.button("🔍 Buscar partidas"):
    liga_id = liga_dict[liga_selecionada]
    hoje = data_selecionada.strftime("%Y-%m-%d")
    jogos = obter_jogos(liga_id, hoje)

    if not jogos:
        st.warning(f"⚠️ Não há jogos registrados para {liga_selecionada} no dia {data_selecionada}")

        # Sugere próximos dias com jogos
        proxima_data = data_selecionada
        for _ in range(7):
            proxima_data += timedelta(days=1)
            jogos_prox = obter_jogos(liga_id, proxima_data.strftime("%Y-%m-%d"))
            if jogos_prox:
                st.info(f"ℹ️ Próximos jogos da {liga_selecionada} disponíveis em {proxima_data}")
                break
    else:
        st.success(f"✅ {len(jogos)} jogos encontrados para {liga_selecionada} em {data_selecionada}")
        top_jogos = []
        for match in jogos:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away, None)

            # Cálculo de lucro com imposto
            lucro_estimado = estimativa * (confianca/100)
            imposto = 0.30 * lucro_estimado
            lucro_liquido = lucro_estimado - imposto

            # Mostra na tela
            st.write(f"🏟️ {home} vs {away}")
            st.write(f"Tendência: {tendencia}")
            st.write(f"Estimativa: {estimativa:.2f} | Confiança: {confianca}%")
            st.write(f"Lucro bruto: {lucro_estimado:.2f} | Imposto 30%: {imposto:.2f} | Lucro líquido: {lucro_liquido:.2f}")

            verificar_enviar_alerta(match, tendencia, estimativa, confianca)
