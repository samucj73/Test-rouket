import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# === FUNÇÕES ===

def obter_ultimo_numero():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            return data["result"]["outcome"]["number"]
        else:
            st.error("Erro ao acessar a API.")
            return None
    except Exception as e:
        st.error(f"Erro na requisição: {e}")
        return None

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=payload)
    except:
        pass

def vizinhos(numero):
    if numero not in ROULETTE_NUMBERS:
        return []
    idx = ROULETTE_NUMBERS.index(numero)
    total = len(ROULETTE_NUMBERS)
    return [
        ROULETTE_NUMBERS[(idx - 2) % total],
        ROULETTE_NUMBERS[(idx - 1) % total],
        ROULETTE_NUMBERS[(idx + 1) % total],
        ROULETTE_NUMBERS[(idx + 2) % total],
    ]

def obter_numeros_terminal(terminal):
    return [n for n in range(37) if n % 10 == terminal]

# === INTERFACE ===

st.set_page_config(layout="centered", page_title="🎯 Estratégia Terminais Dominantes")
st.title("🎯 Estratégia Terminais + Vizinhos (Roleta)")

st_autorefresh(interval=3000, key="auto")

if "ultimos" not in st.session_state:
    st.session_state.ultimos = deque(maxlen=15)
if "ultimo_processado" not in st.session_state:
    st.session_state.ultimo_processado = None
if "estado" not in st.session_state:
    st.session_state.estado = "coletando"
if "entrada_principal" not in st.session_state:
    st.session_state.entrada_principal = []
if "numeros_usados_para_entrada" not in st.session_state:
    st.session_state.numeros_usados_para_entrada = []

# === LÓGICA PRINCIPAL ===

numero_atual = obter_ultimo_numero()
if numero_atual is not None and numero_atual != st.session_state.ultimo_processado:
    st.session_state.ultimo_processado = numero_atual
    st.session_state.ultimos.appendleft(numero_atual)

    ultimos_12 = list(st.session_state.ultimos)[1:13]

    if st.session_state.estado == "coletando":
        if len(ultimos_12) >= 12:
            terminais = [n % 10 for n in ultimos_12]
            contagem = Counter(terminais)
            dominantes = [t for t, _ in contagem.most_common(2)]

            entrada_total = []
            for t in dominantes:
                nums_terminal = obter_numeros_terminal(t)
                for n in nums_terminal:
                    entrada_total.append(n)
                    entrada_total.extend(vizinhos(n))

            entrada_total = sorted(set(entrada_total))

            st.session_state.estado = "aguardando_13"
            st.session_state.entrada_principal = entrada_total
            st.session_state.vizinhos_entrada = []
            st.session_state.numeros_usados_para_entrada = ultimos_12

            st.success("✅ Entrada gerada! Aguardando confirmação com 13º número...")
            st.write("🎯 Entrada Principal:", entrada_total)

    elif st.session_state.estado == "aguardando_13":
        if numero_atual in st.session_state.numeros_usados_para_entrada:
            st.session_state.estado = "coletando"
            st.warning("⛔ Número repetido nos últimos 12. Entrada cancelada.")
        else:
            st.session_state.estado = "aguardando_14"
            st.session_state.numero_13 = numero_atual
            st.info(f"🔄 13º número recebido: {numero_atual}. Aguardando 14º para verificar GREEN/RED...")

    elif st.session_state.estado == "aguardando_14":
        numero_14 = numero_atual
        entrada = st.session_state.entrada_principal

        if numero_14 in entrada:
            st.success(f"🟢 GREEN! Número {numero_14} estava na entrada.")
            enviar_telegram(f"🟢 GREEN! 🎯 Número {numero_14} estava na entrada: {entrada}")
        else:
            st.error(f"🔴 RED! Número {numero_14} não estava na entrada.")
            enviar_telegram(f"🔴 RED! Número {numero_14} não estava na entrada: {entrada}")

        st.session_state.estado = "coletando"
        st.session_state.entrada_principal = []
        st.session_state.numeros_usados_para_entrada = []

# === EXIBIÇÃO ===

st.subheader("🧾 Últimos Números")
st.write(list(st.session_state.ultimos))

if st.session_state.estado.startswith("aguardando"):
    st.info(f"⏳ Estado atual: {st.session_state.estado}")
else:
    st.write(f"🧠 Estado atual: {st.session_state.estado}")
