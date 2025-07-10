import streamlit as st
import requests
import pandas as pd
from collections import Counter, deque
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import os

# API da roleta
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# Ordem física da roleta europeia
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
    20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

def get_numero_api():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = r.json()
        numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        if numero is not None and 0 <= int(numero) <= 36:
            return int(numero)
        return None
    except:
        return None

def terminal(n):
    return n % 10

def obter_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    vizinhos = []
    for i in range(-2, 3):
        vizinhos.append(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return vizinhos

# Streamlit setup
st.set_page_config(page_title="🎯 Estratégia Terminais com Vizinhos")
st_autorefresh(interval=10000, key="auto-refresh")

# Estado
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=50)
if "ultimo_ciclo" not in st.session_state:
    st.session_state.ultimo_ciclo = []
if "entrada_ativa" not in st.session_state:
    st.session_state.entrada_ativa = False
if "entrada_numeros" not in st.session_state:
    st.session_state.entrada_numeros = []
if "historico_sinais" not in st.session_state:
    st.session_state.historico_sinais = deque(maxlen=50)
if "ultimo_green" not in st.session_state:
    st.session_state.ultimo_green = datetime.min

# Captura novo número
numero_atual = get_numero_api()
if numero_atual is None:
    st.warning("Aguardando número da roleta...")
    st.stop()

# Atualiza histórico
if not st.session_state.historico or numero_atual != st.session_state.historico[-1]:
    st.session_state.historico.append(numero_atual)

# Exibe últimos sorteios
st.title("🎯 Estratégia de Terminais + Vizinhos (Roleta Europeia)")
st.subheader("📥 Últimos números:")
st.write(list(st.session_state.historico)[-20:])

# Estratégia: após 12 números capturados
if len(st.session_state.historico) >= 13:
    ultimos_12 = list(st.session_state.historico)[-13:-1]
    numero_13 = st.session_state.historico[-1]

    # Frequência dos terminais
    terminais = [terminal(n) for n in ultimos_12]
    contagem = Counter(terminais)
    dominantes = [t for t, _ in contagem.most_common(2)]

    # Todos os números da roleta com os terminais dominantes
    candidatos = [n for n in range(37) if terminal(n) in dominantes]

    # Para cada número, pegar vizinhos
    numeros_entrada = []
    for n in candidatos:
        numeros_entrada += obter_vizinhos(n)
    numeros_entrada = sorted(set(numeros_entrada))

    # Verifica se entrada deve ser feita
    if numero_13 in ultimos_12 and not st.session_state.entrada_ativa:
        st.session_state.entrada_ativa = True
        st.session_state.entrada_numeros = numeros_entrada
        msg = f"""🎯 ENTRADA ATIVADA!
Terminais dominantes: {dominantes}
Números de entrada (com vizinhos): {numeros_entrada}
"""
        enviar_telegram(msg)

# Exibição
if st.session_state.entrada_ativa:
    st.success("✅ ENTRADA ATIVA!")
    st.write(f"Números sugeridos: {st.session_state.entrada_numeros}")
else:
    st.info("⏳ Aguardando condição de entrada...")

# Botões controle
col1, col2 = st.columns(2)
with col1:
    if st.button("✅ GREEN"):
        st.session_state.ultimo_green = datetime.now()
        st.session_state.entrada_ativa = False
        st.session_state.entrada_numeros = []
        st.session_state.historico_sinais.append("GREEN")
        enviar_telegram("✅ GREEN confirmado! 🟢")
with col2:
    if st.button("❌ RED"):
        st.session_state.historico_sinais.append("RED")
        st.session_state.entrada_ativa = False
        st.session_state.entrada_numeros = []
        enviar_telegram("❌ RED registrado! 🔴")

# Gráfico desempenho
if st.session_state.historico_sinais:
    st.subheader("📈 Desempenho recente")
    resultado_map = {"GREEN": 1, "RED": 0}
    sinais_numericos = [resultado_map[x] for x in st.session_state.historico_sinais]
    st.line_chart(sinais_numericos, height=200)
