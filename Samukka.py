import streamlit as st
import requests
import json
import os
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import numpy as np

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
MAX_HISTORICO = 200

# Ordem física da roleta europeia
ORDEM_ROLETA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
    20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# === ESTADO ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=MAX_HISTORICO)
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = None
if "modelo_1" not in st.session_state:
    st.session_state.modelo_1 = RandomForestClassifier()
if "modelo_8" not in st.session_state:
    st.session_state.modelo_8 = RandomForestClassifier()

# === FUNÇÕES ===

def obter_numero_api():
    try:
        resposta = requests.get(API_URL)
        if resposta.status_code == 200:
            data = resposta.json()
            numero = int(data["outcome"]["number"])
            timestamp = data["settledAt"]
            return numero, timestamp
    except Exception as e:
        st.error(f"Erro ao acessar API: {e}")
    return None, None

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=payload)
    except:
        st.warning("Erro ao enviar mensagem para o Telegram.")

def extrair_features_ordem_fisica(lista):
    return [ORDEM_ROLETA.index(n) for n in lista]

def extrair_features_mod3(lista):
    return [n % 3 for n in lista]

def gerar_entrada_ordem_fisica(historico):
    terminais = [ORDEM_ROLETA.index(n) for n in historico[-12:]]
    contagem = Counter(terminais)
    top = [k for k, _ in contagem.most_common(2)]
    entrada = set()
    for idx in top:
        for offset in [-2, -1, 0, 1, 2]:
            vizinho = ORDEM_ROLETA[(idx + offset) % len(ORDEM_ROLETA)]
            entrada.add(vizinho)
    return sorted(list(entrada))

def gerar_entrada_mod3(historico):
    grupos = [n % 3 for n in historico[-12:]]
    contagem = Counter(grupos)
    top = [k for k, _ in contagem.most_common(2)]
    entrada = [n for n in range(37) if n % 3 in top]
    return sorted(entrada)

def treinar_modelo(modelo, X, y):
    if len(X) >= 20:
        modelo.fit(X, y)

# === EXECUÇÃO ===

st_autorefresh(interval=5000, key="refresh")
numero, timestamp = obter_numero_api()

if numero is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.ultimo_timestamp = timestamp
    st.session_state.historico.append(numero)

    st.write(f"🎲 Último número: {numero} às {timestamp}")

    if len(st.session_state.historico) >= 14:
        hist = list(st.session_state.historico)

        # Estratégia 1 - Ordem Física
        X1 = []
        y1 = []
        for i in range(12, len(hist) - 1):
            features = extrair_features_ordem_fisica(hist[i - 12:i])
            alvo = 1 if hist[i + 1] in gerar_entrada_ordem_fisica(hist[i - 12:i]) else 0
            X1.append(features)
            y1.append(alvo)
        treinar_modelo(st.session_state.modelo_1, X1, y1)
        prob1 = st.session_state.modelo_1.predict_proba([extrair_features_ordem_fisica(hist[-12:])])[0][1]

        # Estratégia 8 - Mod 3
        X8 = []
        y8 = []
        for i in range(12, len(hist) - 1):
            features = extrair_features_mod3(hist[i - 12:i])
            alvo = 1 if hist[i + 1] in gerar_entrada_mod3(hist[i - 12:i]) else 0
            X8.append(features)
            y8.append(alvo)
        treinar_modelo(st.session_state.modelo_8, X8, y8)
        prob8 = st.session_state.modelo_8.predict_proba([extrair_features_mod3(hist[-12:])])[0][1]

        st.write(f"📊 Probabilidade estratégia 1 (Ordem Física): {prob1:.2f}")
        st.write(f"📊 Probabilidade estratégia 8 (Mod 3): {prob8:.2f}")

        if prob1 > prob8:
            entrada = gerar_entrada_ordem_fisica(hist)
            estrategia = "Ordem Física"
        else:
            entrada = gerar_entrada_mod3(hist)
            estrategia = "Mod 3"

        if not st.session_state.entrada_atual:
            st.session_state.entrada_atual = entrada
            mensagem = f"🎯 ENTRADA GERADA ({estrategia}):\n{entrada}"
            enviar_telegram(mensagem)
            st.success(mensagem)

# === EXIBIÇÃO ===

st.write("---")
st.write(f"📋 Histórico ({len(st.session_state.historico)}): {list(st.session_state.historico)}")
