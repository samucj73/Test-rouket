import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import time
import os

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
MODELO_DUZIA_PATH = "modelo_duzia.pkl"
MODELO_COLUNA_PATH = "modelo_coluna.pkl"
HISTORICO_MAX = 200

# === HISTÓRICO ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=HISTORICO_MAX)

# === MAPAS DE FEATURES FÍSICAS ===
ROULETTE_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8,
                  23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28,
                  12, 35, 3, 26]

def numero_vizinho(n):
    if n not in ROULETTE_ORDER:
        return -1
    i = ROULETTE_ORDER.index(n)
    return ROULETTE_ORDER[(i + 1) % len(ROULETTE_ORDER)]

def setor_roleta(n):
    if n in [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25]:
        return 1  # Voisins
    elif n in [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]:
        return 2  # Tiers
    elif n in [1, 20, 14, 31, 9, 6, 17, 34]:
        return 3  # Orphelins
    return 0

# === FEATURE ENGINEERING ===
@st.cache_data
def extrair_features(historico):
    features = []
    h = list(historico)
    for i in range(1, len(h)):
        atual = h[i]
        anterior = h[i - 1]
        duzia = ((anterior - 1) // 12) + 1 if anterior != 0 else 0
        coluna = ((anterior - 1) % 3) + 1 if anterior != 0 else 0
        par = 1 if anterior % 2 == 0 else 0
        vermelho = int(anterior in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36])
        vizinho = numero_vizinho(anterior)
        setor = setor_roleta(anterior)
        features.append([
            anterior, duzia, coluna, par, vermelho,
            vizinho, setor
        ])
    return np.array(features)

# === TREINAMENTO ===
def treinar_modelo(y):
    X = extrair_features(st.session_state.historico)
    y = y[-len(X):]
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    return modelo

def treinar_modelos():
    hist = list(st.session_state.historico)
    if len(hist) < 50: return None, None

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in hist[1:]]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in hist[1:]]

    modelo_duzia = treinar_modelo(y_duzia)
    modelo_coluna = treinar_modelo(y_coluna)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

# === PREDIÇÃO ===
def prever(modelo):
    X = extrair_features(st.session_state.historico)
    if len(X) == 0: return None, 0
    probas = modelo.predict_proba([X[-1]])[0]
    classe = np.argmax(probas) + 1
    prob = probas[classe - 1]
    return classe, prob

# === TELEGRAM ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
    try: requests.post(url, data=payload)
    except: pass

# === APP STREAMLIT ===
st.set_page_config(layout="wide")
st.title("🎯 IA Roleta: Previsão Dúzia e Coluna")

st_autorefresh(interval=5000, key="refresh")

# === API E HISTÓRICO ===
try:
    response = requests.get(API_URL)
    data = response.json()
    ultimo_numero = int(data["winningNumber"])
except:
    st.error("Erro ao acessar API.")
    st.stop()

if len(st.session_state.historico) == 0 or st.session_state.historico[-1] != ultimo_numero:
    st.session_state.historico.append(ultimo_numero)

# === MODELOS ===
if Path(MODELO_DUZIA_PATH).exists() and Path(MODELO_COLUNA_PATH).exists():
    modelo_duzia = joblib.load(MODELO_DUZIA_PATH)
    modelo_coluna = joblib.load(MODELO_COLUNA_PATH)
else:
    modelo_duzia, modelo_coluna = treinar_modelos()

# === PREVISÃO E ALERTAS ===
duzia, prob_duzia = prever(modelo_duzia)
coluna, prob_coluna = prever(modelo_coluna)

if duzia and prob_duzia > 0.5:
    mensagem = f"🎯 <b>Dúzia IA:</b> {duzia} (confiança: {prob_duzia:.0%})"
    enviar_telegram(mensagem)
    st.success(mensagem)

if coluna and prob_coluna > 0.5:
    mensagem = f"🎯 <b>Coluna IA:</b> {coluna} (confiança: {prob_coluna:.0%})"
    enviar_telegram(mensagem)
    st.success(mensagem)

# === HISTÓRICO VISUAL ===
st.markdown("### Últimos Números:")
st.write(list(st.session_state.historico)[-10:])
