import streamlit as st
import requests
import joblib
from collections import deque, Counter
import threading
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MODEL_PATH = Path("modelo_duzia.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 10 segundos
WINDOW_SIZE = 12  # tamanho da sequência de entrada para o modelo

# === SESSION STATE ===
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior", "padroes_certos", "ultima_entrada"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        else:
            st.session_state[var] = 0

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (RandomForest)")
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=10, max_value=100, value=30) / 100.0

# === FUNÇÕES ===
def enviar_telegram_async(mensagem):
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)
    threading.Thread(target=_send, daemon=True).start()

def numero_para_duzia(num):
    if num == 0:
        return 0
    elif 1 <= num <= 12:
        return 1
    elif 13 <= num <= 24:
        return 2
    else:
        return 3

def salvar_historico_duzia(numero):
    duzia = numero_para_duzia(numero)
    if len(st.session_state.historico) == 0 or duzia != st.session_state.historico[-1]:
        st.session_state.historico.append(duzia)
        joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

def criar_features(historico):
    """Gera features para o modelo usando os últimos WINDOW_SIZE resultados"""
    if len(historico) < WINDOW_SIZE:
        return None
    seq = list(historico)[-WINDOW_SIZE:]
    X = np.array(seq).reshape(1, -1)
    return X

def prever_duzia_rf():
    """Prevê a próxima dúzia usando RandomForest"""
    if not MODEL_PATH.exists() or len(st.session_state.historico) < WINDOW_SIZE:
        return None, 0.0

    modelo = joblib.load(MODEL_PATH)
    X = criar_features(st.session_state.historico)
    if X is None:
        return None, 0.0

    try:
        probs = modelo.predict_proba(X)[0]
        classes = modelo.classes_
        # pega a classe de maior probabilidade
        idx = np.argmax(probs)
        duzia_prevista = classes[idx]
        probabilidade = probs[idx]
        return duzia_prevista, probabilidade
    except Exception as e:
        print("Erro predição RF:", e)
        return None, 0.0

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico
if len(st.session_state.historico) == 0 or numero_para_duzia(numero_atual) != st.session_state.historico[-1]:
    duzia_atual = salvar_historico_duzia(numero_atual)

    # Feedback apenas de acertos
    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor = numero_para_duzia(numero_atual)
        if valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🟢")
            st.session_state.padroes_certos.append(valor)
            if len(st.session_state.padroes_certos) > 10:
                st.session_state.padroes_certos.pop(0)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🔴")

# Previsão RandomForest
duzia_prevista, prob = prever_duzia_rf()

if duzia_prevista is not None and prob >= prob_minima:
    st.write(f"📊 Previsão RF → {duzia_prevista}ª dúzia (conf: {prob*100:.1f}%)")
    chave_alerta = f"duzia_{duzia_prevista}"
    st.session_state.ultima_entrada = [duzia_prevista]
    st.session_state.tipo_entrada_anterior = "duzia"
    st.session_state.ultima_chave_alerta = chave_alerta

    enviar_telegram_async(f"📊 <b>ENTRADA DÚZIA RF:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)")
else:
    st.info("Nenhum padrão confiável encontrado ou probabilidade abaixo do mínimo.")

# Interface limpa
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])

# Salva estado
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "ultima_entrada": st.session_state.ultima_entrada,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta
}, ESTADO_PATH)

# Auto-refresh
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
