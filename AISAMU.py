import streamlit as st
import requests
import joblib
import os
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import numpy as np
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
CAMINHO_MODELO = "modelo_ia_terminal.pkl"
NUM_VIZINHOS = 2
JANELA_HISTORICO = 20

# === ORDEM FÍSICA DOS NÚMEROS DA ROLETA EUROPEIA ===
roleta = [26, 3, 35, 12, 28, 7, 29, 18, 22, 9,
          31, 14, 20, 1, 33, 16, 24, 5, 10, 23,
          8, 30, 11, 36, 13, 27, 6, 34, 17, 25,
          2, 21, 4, 19, 15, 32, 0]

# === FUNÇÕES AUXILIARES ===
def extrair_terminal(numero):
    return numero % 10

def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload)
    except:
        pass

def carregar_modelo():
    if os.path.exists(CAMINHO_MODELO):
        return joblib.load(CAMINHO_MODELO)
    else:
        return RandomForestClassifier(n_estimators=100, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, CAMINHO_MODELO)

def treinar_ou_atualizar_modelo(modelo, historico):
    if len(historico) < JANELA_HISTORICO:
        return modelo
    terminais = [extrair_terminal(n) for n in historico]
    X, y = [], []
    for i in range(len(terminais) - 5):
        X.append(terminais[i:i+5])
        y.append(terminais[i+5])
    modelo.fit(X, y)
    salvar_modelo(modelo)
    return modelo

def prever_terminais(modelo, historico):
    terminais = [extrair_terminal(n) for n in historico]
    entrada = np.array(terminais[-5:]).reshape(1, -1)
    probas = modelo.predict_proba(entrada)[0]
    classes = modelo.classes_
    top_idx = np.argsort(probas)[::-1][:2]
    return [int(classes[i]) for i in top_idx]

def gerar_numeros_terminal(terminal):
    return [n for n in range(37) if extrair_terminal(n) == terminal]

def vizinhos(numero):
    idx = roleta.index(numero)
    return [roleta[(idx + i) % len(roleta)] for i in range(-NUM_VIZINHOS, NUM_VIZINHOS + 1)]

# === STREAMLIT APP ===
st.set_page_config(page_title="IA TERMINAIS", layout="centered")
st_autorefresh(interval=5000, key="refresh")

if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=1000)
if "ultima_entrada" not in st.session_state:
    st.session_state.ultima_entrada = []
if "resultado_anterior" not in st.session_state:
    st.session_state.resultado_anterior = None
if "modelo" not in st.session_state:
    st.session_state.modelo = carregar_modelo()
if "contador" not in st.session_state:
    st.session_state.contador = {"GREEN": 0, "RED": 0}

# === COLETA DA API ===
try:
    res = requests.get(API_URL).json()
    numero = int(res["number"])
    timestamp = res["timestamp"]
except:
    st.error("⚠️ Erro ao acessar API.")
    st.stop()

# Evita processar mesmo número
if st.session_state.resultado_anterior == numero:
    st.info("⏳ Aguardando novo número...")
    st.stop()

st.session_state.resultado_anterior = numero
st.session_state.historico.append(numero)

# === TREINAR MODELO IA ===
if len(st.session_state.historico) >= JANELA_HISTORICO:
    st.session_state.modelo = treinar_ou_atualizar_modelo(
        st.session_state.modelo, list(st.session_state.historico)
    )

    # === PREVISÃO COM IA ===
    terminais_previstos = prever_terminais(st.session_state.modelo, list(st.session_state.historico))
    entrada = []
    for t in terminais_previstos:
        for n in gerar_numeros_terminal(t):
            entrada.extend(vizinhos(n))
    entrada_final = sorted(set(entrada))
    st.session_state.ultima_entrada = entrada_final

    enviar_telegram(f"""🎯 Nova entrada gerada pela IA:

🔢 Terminais previstos: {terminais_previstos}
🎯 Entrada completa: {entrada_final}

🎰 Aguardando resultado...
""")
else:
    st.warning("⚠️ Aguardando dados suficientes para prever...")
    st.stop()

# === VERIFICAÇÃO DE RESULTADO ===
if numero in st.session_state.ultima_entrada:
    st.success(f"✅ GREEN! Número: {numero}")
    st.session_state.contador["GREEN"] += 1
    enviar_telegram(f"🟢 GREEN! Número sorteado: {numero}")
else:
    st.error(f"❌ RED! Número: {numero}")
    st.session_state.contador["RED"] += 1
    enviar_telegram(f"🔴 RED! Número sorteado: {numero}")

# === EXIBIÇÃO NA TELA ===
st.markdown("## 🎰 IA TERMINAIS - PREVISÃO EM TEMPO REAL")
st.markdown(f"**Último número:** `{numero}`")
st.markdown(f"**Entrada atual:** `{st.session_state.ultima_entrada}`")
st.markdown(f"**GREENs:** 🟢 {st.session_state.contador['GREEN']} &nbsp;&nbsp;&nbsp; **REDs:** 🔴 {st.session_state.contador['RED']}")
