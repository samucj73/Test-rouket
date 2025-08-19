import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000
WINDOW_SIZE = 15

# === FUNÇÕES AUXILIARES ===
def enviar_telegram_async(mensagem, delay=0):
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)

    if delay > 0:
        threading.Timer(delay, _send).start()
    else:
        threading.Thread(target=_send, daemon=True).start()

def numero_para_duzia(num):
    if num == 0: return 0
    elif 1 <= num <= 12: return 1
    elif 13 <= num <= 24: return 2
    else: return 3

def numero_para_coluna(num):
    if num == 0: return 0
    elif num % 3 == 1: return 1
    elif num % 3 == 2: return 2
    else: return 3

# === SESSION STATE ===
if "historico_duzia" not in st.session_state:
    st.session_state.historico_duzia = deque(maxlen=MAX_HIST_LEN)
if "historico_coluna" not in st.session_state:
    st.session_state.historico_coluna = deque(maxlen=MAX_HIST_LEN)
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = None
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = None
if "ultimo_numero_salvo" not in st.session_state:
    st.session_state.ultimo_numero_salvo = None
if "ultima_entrada" not in st.session_state:
    st.session_state.ultima_entrada = None
if "acertos_top" not in st.session_state:
    st.session_state.acertos_top = 0
if "total_top" not in st.session_state:
    st.session_state.total_top = 0
if "ultimo_resultado_numero" not in st.session_state:
    st.session_state.ultimo_resultado_numero = None

# === FEATURES ===
def extrair_features(janela):
    features = []
    window_size = len(janela)
    features.extend(janela)
    contador = Counter(janela)
    for c in [1, 2, 3]:
        features.append(contador.get(c, 0) / window_size)
    return features

def criar_dataset(historico, tamanho_janela=15):
    X, y = [], []
    if len(historico) <= tamanho_janela:
        return np.empty((0, tamanho_janela)), np.array([])
    for i in range(len(historico) - tamanho_janela):
        X.append(historico[i:i+tamanho_janela])
        y.append(historico[i+tamanho_janela])
    return np.array(X), np.array(y)

# === TREINAMENTO ===
def treinar_modelos():
    # Dúzia
    Xd, yd = criar_dataset(st.session_state.historico_duzia, WINDOW_SIZE)
    if len(yd) > 1 and len(set(yd)) > 1:
        modelo_d = CatBoostClassifier(iterations=200, depth=6, learning_rate=0.1,
                                      loss_function='MultiClass', verbose=False)
        modelo_d.fit(Xd, yd)
        st.session_state.modelo_duzia = modelo_d

    # Coluna
    Xc, yc = criar_dataset(st.session_state.historico_coluna, WINDOW_SIZE)
    if len(yc) > 1 and len(set(yc)) > 1:
        modelo_c = CatBoostClassifier(iterations=200, depth=6, learning_rate=0.1,
                                      loss_function='MultiClass', verbose=False)
        modelo_c.fit(Xc, yc)
        st.session_state.modelo_coluna = modelo_c

# === PREVISÃO ===
def prever_duzia():
    janela = list(st.session_state.historico_duzia)[-WINDOW_SIZE:]
    if len(janela) < WINDOW_SIZE or st.session_state.modelo_duzia is None:
        return None, None
    features = np.array(extrair_features(janela)).reshape(1, -1)
    probs = st.session_state.modelo_duzia.predict_proba(features)[0]
    classes = st.session_state.modelo_duzia.classes_
    idx = np.argmax(probs)
    return classes[idx], probs[idx]

def prever_coluna():
    janela = list(st.session_state.historico_coluna)[-WINDOW_SIZE:]
    if len(janela) < WINDOW_SIZE or st.session_state.modelo_coluna is None:
        return None, None
    features = np.array(extrair_features(janela)).reshape(1, -1)
    probs = st.session_state.modelo_coluna.predict_proba(features)[0]
    classes = st.session_state.modelo_coluna.classes_
    idx = np.argmax(probs)
    return classes[idx], probs[idx]

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if numero_atual != st.session_state.ultimo_numero_salvo:
    duzia_atual = numero_para_duzia(numero_atual)
    coluna_atual = numero_para_coluna(numero_atual)

    st.session_state.historico_duzia.append(duzia_atual)
    st.session_state.historico_coluna.append(coluna_atual)
    st.session_state.ultimo_numero_salvo = numero_atual

    if len(st.session_state.historico_duzia) >= WINDOW_SIZE + 2 and len(st.session_state.historico_duzia) % 2 == 0:
        treinar_modelos()

# === ALERTA DE RESULTADO + NOVA PREVISÃO ===
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual

    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        duzia_real = numero_para_duzia(numero_atual)
        coluna_real = numero_para_coluna(numero_atual)

        if (duzia_real == st.session_state.ultima_entrada["duzia"] and
            coluna_real == st.session_state.ultima_entrada["coluna"]):
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual}: 🟢 (acerto dúzia+coluna)", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual}: 🔴 (erro dúzia+coluna)", delay=1)

    duzia_prev, prob_d = prever_duzia()
    coluna_prev, prob_c = prever_coluna()

    if duzia_prev is not None and coluna_prev is not None:
        st.session_state.ultima_entrada = {"duzia": duzia_prev, "coluna": coluna_prev}
        msg = (f"📊 <b>ENTRADA:</b> Dúzia {duzia_prev} (conf {prob_d*100:.1f}%) | "
               f"Coluna {coluna_prev} (conf {prob_c*100:.1f}%)")
        enviar_telegram_async(msg, delay=5)

# === INTERFACE ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzia):", list(st.session_state.historico_duzia)[-12:])
st.write("Últimos registros (coluna):", list(st.session_state.historico_coluna)[-12:])

# === AUTO REFRESH ===
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
