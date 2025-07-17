import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/stream/XxxtremeLigh0001?currency=BRL"

# === INICIALIZAÇÃO ===
st.set_page_config(page_title="Roleta Terminais", layout="centered")
st.title("🎯 Estratégia dos Terminais (com Vizinhos)")
st_autorefresh(interval=5000, key="refresh")

if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=100)
if "ultimo_id" not in st.session_state:
    st.session_state.ultimo_id = None
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []
if "estado" not in st.session_state:
    st.session_state.estado = "coletando"
if "greens" not in st.session_state:
    st.session_state.greens = 0

# === FUNÇÕES ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=payload)
    except:
        pass

def buscar_numero():
    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()
        if "data" in data and "lastNumbers" in data["data"]:
            id_jogo = data["data"]["id"]
            numeros = data["data"]["lastNumbers"]
            if numeros:
                return id_jogo, int(numeros[0])
    except:
        return None, None
    return None, None

def terminal(numero):
    return int(str(numero)[-1])

def gerar_entrada(numeros):
    terminais = [terminal(n) for n in numeros]
    contagem = Counter(terminais)
    dois_mais_comuns = [item[0] for item in contagem.most_common(2)]
    entrada = []

    roleta = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
        27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
        16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
        7, 28, 12, 35, 3, 26
    ]

    for t in dois_mais_comuns:
        numeros_com_terminal = [n for n in range(0, 37) if terminal(n) == t]
        for n in numeros_com_terminal:
            idx = roleta.index(n)
            vizinhos = [roleta[(idx + i) % len(roleta)] for i in [-2, -1, 0, 1, 2]]
            entrada.extend(vizinhos)

    return sorted(set(entrada))

# === EXECUÇÃO PRINCIPAL ===
id_atual, numero = buscar_numero()

if id_atual and id_atual != st.session_state.ultimo_id:
    st.session_state.ultimo_id = id_atual
    st.session_state.historico.appendleft(numero)

    if st.session_state.estado == "pós_red":
        st.session_state.estado = "coletando"

    elif st.session_state.estado == "coletando":
        if len(st.session_state.historico) >= 12:
            ultimos_12 = list(st.session_state.historico)[:12]
            entrada = gerar_entrada(ultimos_12)
            if numero in ultimos_12:
                st.session_state.entrada_atual = entrada
                st.session_state.estado = "aguardando_resultado"
                enviar_telegram(f"🎯 Entrada gerada: {entrada}")

    elif st.session_state.estado == "aguardando_resultado":
        if numero in st.session_state.entrada_atual:
            st.session_state.greens += 1
            enviar_telegram(f"🟢 GREEN! Número: {numero}")
        else:
            enviar_telegram(f"🔴 RED. Número: {numero}")
        st.session_state.entrada_atual = []
        st.session_state.estado = "pós_red"

# === INTERFACE ===
st.markdown("---")
st.subheader(f"🧠 Estado atual: `{st.session_state.estado}`")

st.subheader("🎯 Última entrada:")
if st.session_state.entrada_atual:
    st.write(sorted(st.session_state.entrada_atual))
else:
    st.write("Nenhuma entrada ativa no momento.")

st.subheader("📊 Últimos 15 números:")
cores = []
for i, n in enumerate(list(st.session_state.historico)[:15]):
    if i == 0:
        if st.session_state.estado == "aguardando_resultado":
            if n in st.session_state.entrada_atual:
                cores.append("🟢")
            else:
                cores.append("🔴")
        else:
            cores.append("⚪")
    else:
        cores.append("⚪")

st.write(" ".join(f"{cor} {n}" for cor, n in zip(cores, list(st.session_state.historico)[:15])))

st.subheader("✅ Greens consecutivos:")
st.write(st.session_state.greens)
