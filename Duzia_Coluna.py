import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque
import time
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import os

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# === HISTÓRICO ===
HISTORICO_PATH = "historico_duzia_coluna.pkl"
MAX_HISTORICO = 200
historico = deque(maxlen=MAX_HISTORICO)

# === AUTORELOAD ===
st_autorefresh(interval=5000, key="atualizacao")

# === Função para extrair features ===
def extrair_features(historico):
    historico = list(historico)
    features = []
    for i in range(1, len(historico)):
        prev = historico[i - 1]
        atual = historico[i]

        duzia = ((prev - 1) // 12) + 1 if prev != 0 else 0
        coluna = ((prev - 1) % 3) + 1 if prev != 0 else 0
        par = 1 if prev % 2 == 0 else 0
        vermelho = 1 if prev in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0

        features.append([duzia, coluna, par, vermelho])
    return np.array(features)

# === Treinar os modelos ===
def treinar_modelos(historico):
    if len(historico) < 50:
        return None, None

    X = extrair_features(historico)
    y_duzia = [((n - 1) // 12) + 1 for n in list(historico)[1:] if n != 0]
    y_coluna = [((n - 1) % 3) + 1 for n in list(historico)[1:] if n != 0]

    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_duzia.fit(X, y_duzia)
    modelo_coluna.fit(X, y_coluna)

    joblib.dump(modelo_duzia, "modelo_duzia.pkl")
    joblib.dump(modelo_coluna, "modelo_coluna.pkl")

    return modelo_duzia, modelo_coluna

# === Carregar histórico ===
if Path(HISTORICO_PATH).exists():
    historico = joblib.load(HISTORICO_PATH)

# === Carregar ou treinar modelo ===
if Path("modelo_duzia.pkl").exists() and Path("modelo_coluna.pkl").exists():
    modelo_duzia = joblib.load("modelo_duzia.pkl")
    modelo_coluna = joblib.load("modelo_coluna.pkl")
else:
    modelo_duzia, modelo_coluna = treinar_modelos(historico)

# === Função para obter número da API ===
def obter_numero_api():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        numero = int(data.get("data", {}).get("result", {}).get("outcome", {}).get("number", -1))
        return numero if 0 <= numero <= 36 else None
    except Exception as e:
        st.error("Erro ao acessar API.")
        st.text(f"Detalhe: {e}")
        return None

# === Função para prever próxima jogada ===
def prever_proxima(modelo, historico):
    if len(historico) < 2:
        return None, 0.0
    X = extrair_features(historico)
    x_entrada = X[-1].reshape(1, -1)
    probas = modelo.predict_proba(x_entrada)[0]
    classe = modelo.classes_[np.argmax(probas)]
    confianca = np.max(probas)
    return classe, confianca

# === Função para enviar mensagem ao Telegram ===
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        st.warning(f"Falha ao enviar para Telegram: {e}")

# === MAIN ===
numero_atual = obter_numero_api()

if numero_atual is not None and (len(historico) == 0 or numero_atual != historico[-1]):
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)
    modelo_duzia, modelo_coluna = treinar_modelos(historico)

    duzia, prob_duzia = prever_proxima(modelo_duzia, historico)
    coluna, prob_coluna = prever_proxima(modelo_coluna, historico)

    mensagem = f"🎯 <b>Previsão IA</b>\n🎲 Último número: <b>{numero_atual}</b>\n"
    if duzia: mensagem += f"📦 Dúzia prevista: <b>{duzia}</b> ({prob_duzia:.0%})\n"
    if coluna: mensagem += f"📍 Coluna prevista: <b>{coluna}</b> ({prob_coluna:.0%})"

    st.markdown(mensagem, unsafe_allow_html=True)
    enviar_telegram(mensagem)
else:
    st.info("Aguardando novo número...")
