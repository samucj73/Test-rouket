import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
import time

from alertas_coluna import enviar_previsao, enviar_resultado, get_coluna

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HIST_PATH = Path("historico_coluna.pkl")
MAX_HISTORICO = 200

# =========================
# SESSION STATE INIT
# =========================
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=MAX_HISTORICO)
    if HIST_PATH.exists():
        hist = joblib.load(HIST_PATH)
        st.session_state.historico.extend(hist)

if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = None

if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = None

if "green_count" not in st.session_state:
    st.session_state.green_count = 0

if "red_count" not in st.session_state:
    st.session_state.red_count = 0


# =========================
# FUNÇÃO API - NOVA (casinoscores)
# =========================
def obter_ultimo_numero():
    try:
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        data = r.json()

        numero = data["data"]["result"]["outcome"]["number"]
        return int(numero)
    except Exception as e:
        st.error(f"[ERRO API] {e}")
        return None


# =========================
# TREINAMENTO MODELO
# =========================
from sklearn.ensemble import RandomForestClassifier

def treinar_modelo_coluna(historico):
    X, y = [], []
    hist_list = list(historico)
    for i in range(len(hist_list) - 5):
        janela = hist_list[i:i+5]
        alvo = get_coluna(hist_list[i+5])
        X.append(janela)
        y.append(alvo)

    if len(X) < 10:
        return None

    modelo = RandomForestClassifier(n_estimators=300, max_depth=6, random_state=42)
    modelo.fit(X, y)
    return modelo


# =========================
# LOOP PRINCIPAL
# =========================
st.title("🎯 Previsão de Coluna - Roleta")

# autorefresh a cada 10 segundos
st_autorefresh(interval=10000, key="refresh")

numero = obter_ultimo_numero()
if numero is not None:
    if len(st.session_state.historico) == 0 or numero != st.session_state.historico[-1]:
        st.session_state.historico.append(numero)
        joblib.dump(list(st.session_state.historico), HIST_PATH)

        # treino do modelo
        if len(st.session_state.historico) > 30:
            st.session_state.modelo_coluna = treinar_modelo_coluna(st.session_state.historico)

        # previsão
        if st.session_state.modelo_coluna is not None and len(st.session_state.historico) >= 5:
            entrada = [list(st.session_state.historico)[-5:]]
            probs = st.session_state.modelo_coluna.predict_proba(entrada)[0]
            melhor_coluna = np.argmax(probs) + 1

            # envia previsão se mudou
            if st.session_state.coluna_prevista != melhor_coluna:
                enviar_previsao(melhor_coluna)
                st.session_state.coluna_prevista = melhor_coluna

        # conferir resultado da rodada anterior
        if st.session_state.coluna_prevista is not None:
            coluna_real = get_coluna(numero)
            acertou = coluna_real == st.session_state.coluna_prevista

            if acertou:
                st.session_state.green_count += 1
            else:
                st.session_state.red_count += 1

            enviar_resultado(numero, acertou)


# =========================
# STATUS
# =========================
st.write("📊 Histórico:", list(st.session_state.historico)[-15:])
st.write("🟢 GREENs:", st.session_state.green_count)
st.write("🔴 REDs:", st.session_state.red_count)
