import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
import threading
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 5 segundos
WINDOW_SIZE = 8  # janela para RF

# === SESSION STATE ===
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior", "padroes_certos", "ultima_entrada", "modelo_rf"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        elif var == "modelo_rf":
            st.session_state[var] = None
        else:
            st.session_state[var] = 0

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (RF + Feedback Acertos)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=2, max_value=120, value=8)
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

def criar_features_avancadas(historico):
    if len(historico) < WINDOW_SIZE + 1:
        return None, None
    X, y = [], []
    seq = list(historico)
    for i in range(len(seq) - WINDOW_SIZE):
        janela = seq[i:i+WINDOW_SIZE]
        alvo = seq[i+WINDOW_SIZE]

        # Sequência simples
        features = list(janela)

        # Frequência das dúzias na janela
        contador = Counter(janela)
        freq1 = contador.get(1,0)/WINDOW_SIZE
        freq2 = contador.get(2,0)/WINDOW_SIZE
        freq3 = contador.get(3,0)/WINDOW_SIZE
        features.extend([freq1, freq2, freq3])

        # Alternância
        alternancias = sum(1 for j in range(1,len(janela)) if janela[j] != janela[j-1])
        alt_norm = alternancias / (WINDOW_SIZE-1)
        features.append(alt_norm)

        # Tendência ponderada
        pesos = [0.9**i for i in range(WINDOW_SIZE-1,-1,-1)]
        tend = [0,0,0]
        for val, w in zip(janela, pesos):
            if val != 0:
                tend[val-1] += w
        total_tend = sum(tend) if sum(tend)>0 else 1
        tend_norm = [t/total_tend for t in tend]
        features.extend(tend_norm)

        X.append(features)
        y.append(alvo)
    return np.array(X), np.array(y)

def treinar_modelo_rf():
    X, y = criar_features_avancadas(st.session_state.historico)
    if X is not None and len(X) > 0:
        modelo = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
        modelo.fit(X, y)
        st.session_state.modelo_rf = modelo

def prever_duzia_rf():
    if st.session_state.modelo_rf is None or len(st.session_state.historico) < WINDOW_SIZE:
        return None, 0.0
    janela = list(st.session_state.historico)[-WINDOW_SIZE:]
    features = list(janela)
    contador = Counter(janela)
    freq1 = contador.get(1,0)/WINDOW_SIZE
    freq2 = contador.get(2,0)/WINDOW_SIZE
    freq3 = contador.get(3,0)/WINDOW_SIZE
    features.extend([freq1, freq2, freq3])
    alternancias = sum(1 for j in range(1,len(janela)) if janela[j] != janela[j-1])
    alt_norm = alternancias / (WINDOW_SIZE-1)
    features.append(alt_norm)
    pesos = [0.9**i for i in range(WINDOW_SIZE-1,-1,-1)]
    tend = [0,0,0]
    for val, w in zip(janela, pesos):
        if val != 0:
            tend[val-1] += w
    total_tend = sum(tend) if sum(tend)>0 else 1
    tend_norm = [t/total_tend for t in tend]
    features.extend(tend_norm)
    features = np.array(features).reshape(1,-1)
    probs = st.session_state.modelo_rf.predict_proba(features)[0]
    classes = st.session_state.modelo_rf.classes_
    melhor_idx = np.argmax(probs)
    return classes[melhor_idx], probs[melhor_idx]

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico apenas se novo número
if len(st.session_state.historico) == 0 or numero_para_duzia(numero_atual) != st.session_state.historico[-1]:
    duzia_atual = salvar_historico_duzia(numero_atual)

    # Treina modelo RF a cada novo número
    treinar_modelo_rf()

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

# Previsão RF
duzia_prevista, prob = prever_duzia_rf()

if duzia_prevista is not None:
    chave_alerta = f"duzia_{duzia_prevista}"
    if chave_alerta != st.session_state.ultima_chave_alerta:
        st.session_state.ultima_entrada = [duzia_prevista]
        st.session_state.tipo_entrada_anterior = "duzia"
        st.session_state.contador_sem_alerta = 0
        st.session_state.ultima_chave_alerta = chave_alerta
        enviar_telegram_async(f"📊 <b>ENTRADA DÚZIA RF:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)")

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
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "modelo_rf": st.session_state.modelo_rf
}, ESTADO_PATH)

# Auto-refresh
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
