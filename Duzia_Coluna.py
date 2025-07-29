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
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

HISTORICO_PATH = Path("historico_dados.pkl")
MODELO_DUZIA_PATH = Path("modelo_duzia.pkl")
MODELO_COLUNA_PATH = Path("modelo_coluna.pkl")

# === INICIALIZAÇÕES ===
st.set_page_config(page_title="IA Roleta", layout="centered")
st_autorefresh(interval=5000, key="refresh")

if HISTORICO_PATH.exists():
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=500)

estado = st.session_state
if "ultimo_numero" not in estado:
    estado.ultimo_numero = None
if "modelo_duzia" not in estado:
    estado.modelo_duzia = None
if "modelo_coluna" not in estado:
    estado.modelo_coluna = None
if "contador_retreino" not in estado:
    estado.contador_retreino = 0

# === FUNÇÕES ===
def obter_numero():
    try:
        r = requests.get(API_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return int(data["winningNumber"]["value"])
    except:
        return None

def extrair_features(historico):
    X = []
    hist = list(historico)
    for i in range(60, len(hist)):
        janela = hist[i-60:i]
        features = []

        # Frequência absoluta
        contador = [0] * 37
        for num in janela:
            contador[num] += 1
        features.extend(contador)

        # Últimos 5 números
        features.extend(janela[-5:])

        # Frequência de dúzia
        duzias = [((n - 1) // 12) + 1 if n != 0 else 0 for n in janela]
        for d in [1, 2, 3]:
            features.append(duzias.count(d))

        # Frequência de colunas
        colunas = [((n - 1) % 3) + 1 if n != 0 else 0 for n in janela]
        for c in [1, 2, 3]:
            features.append(colunas.count(c))

        X.append(features)
    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 80:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[60:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    X_filtrado = []
    y_duzia_f = []
    y_coluna_f = []
    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_filtrado.append(xi)
            y_duzia_f.append(d)
            y_coluna_f.append(c)

    modelo_duzia = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)

    modelo_duzia.fit(X_filtrado, y_duzia_f)
    modelo_coluna.fit(X_filtrado, y_coluna_f)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico, prob_minima=0.55):
    if len(historico) < 81:
        return None, 0.0

    X = extrair_features(historico)
    if len(X) < 2:
        return None, 0.0

    x = X[-2].reshape(1, -1)  # ← CORRIGIDO: usa penúltimo

    try:
        probas = modelo.predict_proba(x)[0]
        classe = np.argmax(probas) + 1
        prob = probas[classe - 1]
        if prob >= prob_minima:
            return classe, prob
        return None, prob
    except Exception as e:
        print(f"Erro previsão: {e}")
        return None, 0.0

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=10)
    except:
        pass

# === LOOP PRINCIPAL ===
numero_atual = obter_numero()

if numero_atual is not None and numero_atual != estado.ultimo_numero:
    estado.ultimo_numero = numero_atual

    if len(historico) == 0 or numero_atual != historico[-1]:
        historico.append(numero_atual)
        joblib.dump(historico, HISTORICO_PATH)

        # Re-treina a cada 3 sorteios
        estado.contador_retreino += 1
        if estado.contador_retreino >= 3:
            if len(historico) >= 80:
                estado.modelo_duzia, estado.modelo_coluna = treinar_modelos(historico)
            estado.contador_retreino = 0

        # Previsões com histórico SEM o número atual
        historico_prev = deque(historico, maxlen=500)
        historico_prev.pop()

        prob_min_duzia = 0.60
        prob_min_coluna = 0.60

        duzia, p_d = prever_proxima(estado.modelo_duzia, historico_prev, prob_min_duzia)
        coluna, p_c = prever_proxima(estado.modelo_coluna, historico_prev, prob_min_coluna)

        mensagem = f"🎯 <b>NA:</b> {numero_atual}"
        if duzia:
            mensagem += f" | D: <b>{duzia}</b>"
        if coluna:
            mensagem += f" | C: <b>{coluna}</b>"

        enviar_telegram(mensagem)

# === EXIBIÇÃO STREAMLIT ===
st.title("🎰 IA Roleta - Previsão de Dúzia e Coluna")
st.markdown(f"**Último número:** 🎯 {estado.ultimo_numero}")
st.markdown(f"**Total no histórico:** {len(historico)}")
