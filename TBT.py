import streamlit as st
import requests
import pandas as pd
from collections import Counter, deque
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import numpy as np
import os

# Configurações
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
NUM_ANALISADOS = 12
HISTORICO_CSV = "historico.csv"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# Terminal -> base
TERMINAL_JOGADAS = {
    0: [10, 20, 30],
    1: [1, 11, 21, 31],
    2: [2, 12, 22, 32],
    3: [3, 13, 23, 33],
    4: [4, 14, 24, 34],
    5: [5, 15, 25, 35],
    6: [6, 16, 26, 36, 30],
    7: [7, 17, 27],
    8: [8, 18, 28],
    9: [9, 19, 29]
}

# 🌀 Função para gerar dois vizinhos por número (com rotação 0–36)
def gerar_com_vizinhos(lista):
    vizinhos = []
    for num in lista:
        vizinhos += [(num + i) % 37 for i in range(-2, 3)]  # -2 a +2 com rotação circular
    return sorted(set(vizinhos))

# Telegram
def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

# IA
def treinar_modelo(sequencia):
    X, y = [], []
    janela = 5
    if len(sequencia) < janela + 1:
        return None
    for i in range(len(sequencia) - janela):
        X.append(sequencia[i:i+janela])
        y.append(sequencia[i+janela])
    modelo = RandomForestClassifier(n_estimators=100)
    modelo.fit(X, y)
    return modelo

# Histórico CSV
def salvar_historico(numero, terminal):
    df = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "numero": numero,
        "terminal": terminal
    }])
    if os.path.exists(HISTORICO_CSV):
        df.to_csv(HISTORICO_CSV, sep=";", index=False, mode="a", header=False)
    else:
        df.to_csv(HISTORICO_CSV, sep=";", index=False)

# Streamlit config
st.set_page_config(page_title="🎯 Terminais com IA + Telegram + Histórico")
st_autorefresh(interval=10000, key="refresh")

# Session state
if "historico_terminais" not in st.session_state:
    st.session_state.historico_terminais = deque(maxlen=200)
if "historico_sinais" not in st.session_state:
    st.session_state.historico_sinais = deque(maxlen=50)
if "ultimo_green" not in st.session_state:
    st.session_state.ultimo_green = datetime.min
if "entrada_em_andamento" not in st.session_state:
    st.session_state.entrada_em_andamento = False
if "martingale_ativo" not in st.session_state:
    st.session_state.martingale_ativo = False

# --- Dados da API ---
def get_numeros():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        return [int(x["value"]) for x in data if x["value"].isdigit()]
    except:
        return []

numeros = get_numeros()
if len(numeros) < NUM_ANALISADOS:
    st.warning("Aguardando dados da API...")
    st.stop()

ultimos = numeros[:NUM_ANALISADOS]
terminais = [n % 10 for n in ultimos]
freq = Counter(terminais)
top_terminal, top_freq = freq.most_common(1)[0]

# Histórico IA
st.session_state.historico_terminais.extend(terminais)

# IA preditiva
modelo = treinar_modelo(list(st.session_state.historico_terminais))
prev_ia = modelo.predict([list(st.session_state.historico_terminais)[-5:]])[0] if modelo else None

# Blacklist
blacklist = {8, 30, 23, 28, 12, 7, 17, 34}
evitar = ultimos[0] in blacklist

# Verifica entrada
cond_entrada = (
    not evitar and
    (
        (top_terminal == 6 and top_freq >= 3) or
        (top_terminal == 4 and top_freq >= 3) or
        (top_terminal in [5, 9] and top_freq >= 2)
    )
)
tempo_desde_green = datetime.now() - st.session_state.ultimo_green
aguardando = tempo_desde_green < timedelta(minutes=2)

# Exibir dados
st.title("🎯 Estratégia de Terminais com IA, Vizinhos e Telegram")
st.subheader("📥 Últimos números")
st.write(ultimos)

st.subheader("📊 Frequência de terminais")
st.write(dict(freq))
st.markdown(f"🧠 Terminal dominante: **{top_terminal}** ({top_freq}x)")
if prev_ia is not None:
    st.markdown(f"🤖 IA prevê próximo terminal provável: **{prev_ia}**")

# Entrada recomendada
base = TERMINAL_JOGADAS.get(top_terminal, [])
jogadas = gerar_com_vizinhos(base)

if aguardando:
    st.info(f"⏳ Aguardando {120 - tempo_desde_green.seconds}s após último GREEN.")
elif cond_entrada:
    if not st.session_state.entrada_em_andamento:
        st.session_state.entrada_em_andamento = True
        enviar_telegram(f"🎯 ENTRADA ATIVADA!\nTerminal {top_terminal} ({top_freq}x)\nJogadas com vizinhos: {jogadas}")
    st.success("✅ ENTRADA ATIVADA!")
    st.write(f"🎰 Jogada sugerida (com vizinhos): `{jogadas}`")
    if st.session_state.martingale_ativo:
        st.warning("⚠️ Martingale 1x em andamento")
else:
    st.warning("⚠️ Sem entrada no momento.")
    st.session_state.entrada_em_andamento = False

# Salvamento do novo número
salvar_historico(ultimos[0], ultimos[0] % 10)

# Botões
col1, col2 = st.columns(2)
with col1:
    if st.button("✅ GREEN"):
        st.session_state.ultimo_green = datetime.now()
        st.session_state.entrada_em_andamento = False
        st.session_state.martingale_ativo = False
        st.session_state.historico_sinais.append("GREEN")
        enviar_telegram("✅ GREEN confirmado! 🟢")
with col2:
    if st.button("❌ RED"):
        st.session_state.martingale_ativo = True
        st.session_state.historico_sinais.append("RED")
        enviar_telegram("❌ RED registrado! 🔴")

# Gráfico de acertos
if st.session_state.historico_sinais:
    st.subheader("📈 Desempenho recente")
    resultado_map = {"GREEN": 1, "RED": 0}
    sinais_numericos = [resultado_map[x] for x in st.session_state.historico_sinais]
    st.line_chart(sinais_numericos, height=200)
