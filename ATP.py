import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/finished?gameType=roulette"

# === DEFINIÇÕES ===
ROULETTE_NUMBERS = list(range(37))
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
    10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=100)

if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None

if "estado" not in st.session_state:
    st.session_state.estado = "coletando"  # coletando, aguardando_resultado, pós_red

if "entrada" not in st.session_state:
    st.session_state.entrada = []

if "contador_green" not in st.session_state:
    st.session_state.contador_green = 0

# === FUNÇÕES AUXILIARES ===
def terminal(numero):
    return numero % 10

def get_neighbors(n, ordem=ROULETTE_ORDER, antes=2, depois=2):
    idx = ordem.index(n)
    return [ordem[(idx - i) % len(ordem)] for i in range(antes, 0, -1)] + \
           [n] + \
           [ordem[(idx + i) % len(ordem)] for i in range(1, depois + 1)]

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

# === CONSULTA API ===
def consultar_ultimo_numero():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            for item in data["data"]:
                if item["table"]["id"].endswith("0001"):
                    resultado = item["outcome"]["number"]
                    timestamp = item["settledAt"]
                    return int(resultado), timestamp
    except:
        pass
    return None, None

# === PROCESSAMENTO PRINCIPAL ===
numero, timestamp = consultar_ultimo_numero()

if numero is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.ultimo_timestamp = timestamp
    st.session_state.historico.append(numero)

    if st.session_state.estado == "coletando":
        if len(st.session_state.historico) >= 12:
            ultimos_12 = list(st.session_state.historico)[-12:]
            terminais = [terminal(n) for n in ultimos_12]
            contagem = Counter(terminais).most_common(2)

            if len(contagem) == 2 and contagem[0][1] > contagem[1][1]:
                dominantes = [contagem[0][0], contagem[1][0]]
                entrada = []

                for t in dominantes:
                    nums = [n for n in ROULETTE_NUMBERS if terminal(n) == t]
                    for n in nums:
                        entrada.extend(get_neighbors(n))

                st.session_state.entrada = sorted(set(entrada))
                st.session_state.estado = "aguardando_resultado"
                enviar_telegram(f"🎯 Entrada gerada com terminais {dominantes}: {st.session_state.entrada}")

    elif st.session_state.estado == "aguardando_resultado":
        if numero in st.session_state.entrada:
            st.session_state.contador_green += 1
            enviar_telegram(f"🟢 GREEN #{st.session_state.contador_green} - Número: {numero}")
        else:
            enviar_telegram(f"🔴 RED - Número: {numero}")
            st.session_state.contador_green = 0
            st.session_state.estado = "pós_red"

        st.session_state.entrada = []

    elif st.session_state.estado == "pós_red":
        # Aguarda 1 rodada, depois volta a coletar
        st.session_state.estado = "coletando"

# === INTERFACE ===
st.title("🎰 Estratégia de Roleta com IA - Terminais")

st.markdown("### Estado Atual")
st.markdown(f"**Estado:** `{st.session_state.estado}`")

if st.session_state.entrada:
    st.markdown("### 🎯 Entrada Sugerida")
    st.write(sorted(st.session_state.entrada))

st.markdown("### Últimos Números")
st.write(list(st.session_state.historico)[-15:])

# Botão para resetar
if st.button("🔄 Reiniciar Estratégia (limpar tudo)"):
    st.session_state.historico.clear()
    st.session_state.entrada = []
    st.session_state.estado = "coletando"
    st.session_state.contador_green = 0
    st.session_state.ultimo_timestamp = None
    enviar_telegram("♻️ Estratégia reiniciada manualmente.")

# Auto-refresh a cada 7 segundos
st_autorefresh(interval=7000, key="refresh")
