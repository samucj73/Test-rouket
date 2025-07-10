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
HISTORICO_CSV = "historico.csv"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# Terminais base
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

def gerar_com_vizinhos(lista):
    vizinhos = []
    for num in lista:
        vizinhos += [(num + i) % 37 for i in range(-2, 3)]
    return sorted(set(vizinhos))

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

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

def get_numeros():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = r.json()
        numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        if numero is not None and 0 <= int(numero) <= 36:
            return [int(numero)]
        return []
    except Exception as e:
        st.error(f"Erro ao acessar a API: {e}")
        return []

# Config página
st.set_page_config(page_title="🎯 Estratégia de Terminais com IA e Telegram")
st_autorefresh(interval=10000, key="refresh")

# Estado inicial
if "historico_terminais" not in st.session_state:
    st.session_state.historico_terminais = deque(maxlen=200)
if "historico_numeros_reais" not in st.session_state:
    st.session_state.historico_numeros_reais = deque(maxlen=200)
if "historico_sinais" not in st.session_state:
    st.session_state.historico_sinais = deque(maxlen=50)
if "ultimo_green" not in st.session_state:
    st.session_state.ultimo_green = datetime.min
if "entrada_em_andamento" not in st.session_state:
    st.session_state.entrada_em_andamento = False
if "martingale_ativo" not in st.session_state:
    st.session_state.martingale_ativo = False

# Pega número da API
numeros = get_numeros()
if not numeros:
    st.warning("⏳ Aguardando número da API...")
    st.stop()

numero_atual = numeros[0]
terminal_atual = numero_atual % 10
st.session_state.historico_numeros_reais.append(numero_atual)
st.session_state.historico_terminais.append(terminal_atual)

# Frequência terminal
freq = Counter(st.session_state.historico_terminais)
top_terminal, top_freq = freq.most_common(1)[0]

# IA
modelo = treinar_modelo(list(st.session_state.historico_terminais))
prev_ia = modelo.predict([list(st.session_state.historico_terminais)[-5:]])[0] if modelo else None

# Blacklist com base nos últimos 8 números REAIS sorteados
blacklist = list(st.session_state.historico_numeros_reais)[-8:]
evitar = numero_atual in blacklist

# Lógica de entrada dinâmica
cond_entrada = not evitar and top_freq >= 3
tempo_desde_green = datetime.now() - st.session_state.ultimo_green
aguardando = tempo_desde_green < timedelta(minutes=2)

# Interface
st.title("🎯 Estratégia de Terminais com IA e Telegram")

st.subheader("📥 Último número sorteado")
st.write(f"Número: **{numero_atual}** | Terminal: **{terminal_atual}**")

st.subheader("📊 Frequência dos últimos terminais")
st.write(dict(freq))
st.markdown(f"🔥 Terminal dominante: **{top_terminal}** ({top_freq}x)")
if prev_ia is not None:
    st.markdown(f"🤖 IA prevê próximo terminal provável: **{prev_ia}**")

st.subheader("🛑 Blacklist dinâmica")
st.write(f"Números a evitar: {blacklist}")
if evitar:
    st.error(f"⚠️ Número atual **{numero_atual}** está na blacklist. Evitando entrada.")

# Jogada sugerida
base = TERMINAL_JOGADAS.get(top_terminal, [])
jogadas = gerar_com_vizinhos(base)

if aguardando:
    st.info(f"⏳ Aguardando {120 - tempo_desde_green.seconds}s após GREEN.")
elif cond_entrada:
    if not st.session_state.entrada_em_andamento:
        st.session_state.entrada_em_andamento = True
        enviar_telegram(f"🎯 ENTRADA ATIVADA!\nTerminal {top_terminal} ({top_freq}x)\nJogadas: {jogadas}")
    st.success("✅ ENTRADA ATIVADA!")
    st.write(f"🎰 Jogada sugerida (com vizinhos): `{jogadas}`")
    if st.session_state.martingale_ativo:
        st.warning("⚠️ Martingale 1x em andamento")
else:
    st.warning("⚠️ Sem entrada no momento.")
    st.session_state.entrada_em_andamento = False

# Salvar histórico
salvar_historico(numero_atual, terminal_atual)

# Botões de controle
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

# Gráfico de desempenho
if st.session_state.historico_sinais:
    st.subheader("📈 Desempenho recente")
    resultado_map = {"GREEN": 1, "RED": 0}
    sinais_numericos = [resultado_map[x] for x in st.session_state.historico_sinais]
    st.line_chart(sinais_numericos, height=200)
