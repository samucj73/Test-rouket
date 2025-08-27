import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import time

# =========================
# IMPORTAÇÕES DO ALERTAS
# =========================
from alertas_coluna import enviar_previsao, enviar_resultado, get_coluna

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HIST_PATH = Path("historico_coluna.pkl")
MAX_HISTORICO = 200
RETRAIN_INTERVAL = 10

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

if "rodadas_desde_treino" not in st.session_state:
    st.session_state.rodadas_desde_treino = 0

if "ultima_previsao" not in st.session_state:
    st.session_state.ultima_previsao = None

# =========================
# FUNÇÃO API
# =========================
def obter_ultimo_numero():
    try:
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        return int(data["winningNumber"])
    except Exception as e:
        st.error(f"[ERRO API] {e}")
        return None

# =========================
# FEATURES
# =========================
def extrair_features(seq):
    features = []
    for n in seq:
        coluna = get_coluna(n)
        paridade = 0 if n % 2 == 0 else 1
        features.append([n, coluna, paridade])
    return np.array(features)

# =========================
# TREINAMENTO
# =========================
def treinar_modelo(historico):
    X, y = [], []
    for i in range(len(historico) - 5):
        seq = list(historico)[i:i+5]
        alvo = get_coluna(historico[i+5])
        X.append(seq)
        y.append(alvo)
    if not X:
        return None
    X = extrair_features([n for seq in X for n in seq]).reshape(len(X), -1)
    modelo = RandomForestClassifier(n_estimators=200, random_state=42)
    modelo.fit(X, y)
    return modelo

# =========================
# PREVISÃO
# =========================
def prever_coluna(modelo, historico):
    if len(historico) < 5:
        return None
    seq = list(historico)[-5:]
    X = extrair_features(seq).reshape(1, -1)
    try:
        probs = modelo.predict_proba(X)[0]
        coluna_prevista = np.argmax(probs)
        return coluna_prevista
    except Exception:
        return None

# =========================
# LOOP PRINCIPAL
# =========================
def main():
    st.title("🎰 Previsão de Colunas - Roleta")

    # autorefresh a cada 5s
    st_autorefresh(interval=5000, key="refresh")

    numero = obter_ultimo_numero()
    if numero is None:
        return

    if not st.session_state.historico or numero != st.session_state.historico[-1]:
        st.session_state.historico.append(numero)
        joblib.dump(list(st.session_state.historico), HIST_PATH)

        st.session_state.rodadas_desde_treino += 1

        # treina a cada intervalo
        if (
            st.session_state.modelo_coluna is None
            or st.session_state.rodadas_desde_treino >= RETRAIN_INTERVAL
        ):
            modelo = treinar_modelo(st.session_state.historico)
            if modelo:
                st.session_state.modelo_coluna = modelo
                st.session_state.rodadas_desde_treino = 0

        # faz previsão
        if st.session_state.modelo_coluna:
            previsao = prever_coluna(st.session_state.modelo_coluna, st.session_state.historico)
            if previsao and previsao != st.session_state.ultima_previsao:
                enviar_previsao(previsao)
                st.session_state.ultima_previsao = previsao

        # confere acerto/erro
        if st.session_state.ultima_previsao is not None:
            coluna_real = get_coluna(numero)
            acertou = coluna_real == st.session_state.ultima_previsao
            enviar_resultado(numero, acertou)

    st.write("Histórico:", list(st.session_state.historico))

if __name__ == "__main__":
    main()
