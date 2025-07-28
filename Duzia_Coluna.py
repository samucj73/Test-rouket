import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque
import time
from streamlit_autorefresh import st_autorefresh
from pathlib import Path

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002880411750"
HISTORICO_PATH = "historico_duzia_coluna.pkl"
MODELO_DUZIA_PATH = "modelo_duzia.pkl"
MODELO_COLUNA_PATH = "modelo_coluna.pkl"

# Auto atualização da página
st_autorefresh(interval=5000, key="atualizacao")

# === FUNÇÕES AUXILIARES ===

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem para o Telegram: {e}")

def extrair_features(historico):
    X = []
    historico = list(historico)
    for i in range(len(historico)-1):
        entrada = [
            historico[i],
            historico[i-1] if i >= 1 else 0,
            historico[i-2] if i >= 2 else 0,
            historico[i-3] if i >= 3 else 0,
        ]
        X.append(entrada)
    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 25:
        return None, None

    X = extrair_features(historico)
    y_duzia = [((n - 1) // 12) + 1 for n in list(historico)[1:] if n != 0]
    y_coluna = [((n - 1) % 3) + 1 for n in list(historico)[1:] if n != 0]

    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_duzia.fit(X[:len(y_duzia)], y_duzia)
    modelo_coluna.fit(X[:len(y_coluna)], y_coluna)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico):
    if len(historico) < 4:
        return None, 0.0
    entrada = [
        historico[-1],
        historico[-2],
        historico[-3],
        historico[-4]
    ]
    x = np.array(entrada).reshape(1, -1)
    try:
        probas = modelo.predict_proba(x)[0]
        classe = np.argmax(probas) + 1
        return classe, probas[classe - 1]
    except:
        return None, 0.0

# === CARREGAR HISTÓRICO E MODELOS ===

if Path(HISTORICO_PATH).exists():
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=100)

modelo_duzia = joblib.load(MODELO_DUZIA_PATH) if Path(MODELO_DUZIA_PATH).exists() else None
modelo_coluna = joblib.load(MODELO_COLUNA_PATH) if Path(MODELO_COLUNA_PATH).exists() else None

# === OBTÉM ÚLTIMO NÚMERO DA API ===

try:
    response = requests.get(API_URL)
    response.raise_for_status()
    data = response.json()
    numero_atual = int(data["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error("Erro ao acessar API.")
    st.stop()

# === SE FOR NOVO NÚMERO, ADICIONA AO HISTÓRICO ===

if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    # Treina os modelos caso histórico seja suficiente
    modelo_duzia, modelo_coluna = treinar_modelos(historico)

    # Faz previsões apenas se os modelos estão prontos
    if modelo_duzia is not None and modelo_coluna is not None:
        duzia, prob_duzia = prever_proxima(modelo_duzia, historico)
        coluna, prob_coluna = prever_proxima(modelo_coluna, historico)

        mensagem = f"NA {numero_atual}"
if duzia is not None:
    mensagem += f" - D {duzia}"
if coluna is not None:
    mensagem += f" - C {coluna}"
st.markdown(mensagem, unsafe_allow_html=True)
enviar_telegram(mensagem)
else:
st.warning("Aguardando mais dados para treinar os modelos...")
else:
st.info("Aguardando novo número...")

# === EXIBIR HISTÓRICO ===

st.markdown("### 🎡 Histórico de Números")
st.write(list(historico))
