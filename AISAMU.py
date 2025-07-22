import streamlit as st
import requests
import joblib
import os
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
import numpy as np
from streamlit_autorefresh import st_autorefresh
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
MODELO_PATH = "modelo_ia.pkl"
HISTORICO_MAX = 100
JANELA_ANALISE = 12

# === LISTA DA ROLETA FÍSICA EUROPEIA ===
roleta = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
          11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31,
          9, 22, 18, 29, 7, 28, 12, 35, 3, 26]

# === INICIALIZA HISTÓRICO E ESTADO ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=HISTORICO_MAX)
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None
if "placar" not in st.session_state:
    st.session_state.placar = {"GREEN": 0, "RED": 0}

# === FUNÇÕES UTILITÁRIAS ===
def extrair_terminal(numero):
    return int(str(numero)[-1])

def vizinhos_roleta(numero):
    idx = roleta.index(numero)
    vizinhos = [roleta[(idx + i) % len(roleta)] for i in [-2, -1, 1, 2]]
    return vizinhos

def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=data)
    except:
        pass

def carregar_ou_treinar_modelo(historico):
    if len(historico) < 6:
        return None
    X, y = [], []
    for i in range(len(historico) - 5):
        X.append([extrair_terminal(n) for n in list(historico)[i:i+5]])
        y.append(extrair_terminal(list(historico)[i+5]))
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_proximos_terminais(modelo, historico):
    if len(historico) < 5:
        return []
    entrada = [extrair_terminal(n) for n in list(historico)[-5:]]
    probs = modelo.predict_proba([entrada])[0]
    indices_ordenados = np.argsort(probs)[::-1]
    melhores = indices_ordenados[:2]
    return list(melhores)

def montar_entrada(dominantes):
    entrada = []
    for terminal in dominantes:
        numeros_terminal = [n for n in range(37) if extrair_terminal(n) == terminal]
        for n in numeros_terminal:
            entrada.append(n)
            entrada.extend(vizinhos_roleta(n))
    return sorted(set(entrada))

# === LOOP PRINCIPAL ===
st_autorefresh(interval=5000, key="atualizacao")

st.title("🎯 Estratégia IA com Vizinhos Físicos")
try:
    res = requests.get(API_URL, timeout=10).json()
    numero = int(res["data"]["result"]["outcome"]["number"])
    timestamp = res["data"]["settledAt"]
except Exception as e:
    st.warning("⚠️ Erro ao acessar API.")
    st.stop()

# Evita processar o mesmo número
if timestamp == st.session_state.ultimo_timestamp:
    st.info("⏳ Aguardando novo sorteio...")
    st.stop()

st.session_state.ultimo_timestamp = timestamp
st.session_state.historico.append(numero)

st.write(f"🎲 Último número: **{numero}**")
modelo = carregar_ou_treinar_modelo(st.session_state.historico)

if modelo:
    terminais_previstos = prever_proximos_terminais(modelo, st.session_state.historico)
    if terminais_previstos:
        entrada = montar_entrada(terminais_previstos)
        st.success(f"📈 Entrada sugerida: {entrada}")
        st.write(f"🔢 Terminais previstos: {terminais_previstos}")

        if numero in entrada:
            st.success("✅ GREEN!")
            st.session_state.placar["GREEN"] += 1
            enviar_telegram(f"✅ GREEN! Número {numero} estava na entrada.")
        else:
            st.error("❌ RED.")
            st.session_state.placar["RED"] += 1
            enviar_telegram(f"❌ RED. Número {numero} não estava na entrada.")

        enviar_telegram(f"🎯 Nova entrada IA: {entrada}\n🔢 Terminais: {terminais_previstos}")
    else:
        st.warning("⚠️ Aguardando nova entrada da IA...")
else:
    st.info("⏳ Aguardando mais dados para treinar o modelo...")

# === PLACAR FINAL ===
total = st.session_state.placar["GREEN"] + st.session_state.placar["RED"]
taxa_green = (st.session_state.placar["GREEN"] / total * 100) if total > 0 else 0

st.subheader("📊 Placar")
st.write(f"✅ GREENs: {st.session_state.placar['GREEN']}")
st.write(f"❌ REDs: {st.session_state.placar['RED']}")
st.write(f"📈 Taxa de acerto: **{taxa_green:.2f}%**")
