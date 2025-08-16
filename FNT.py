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
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
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
st.title("🎯 IA Roleta - Padrões de Dúzia (RF + Features Avançadas)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=2, max_value=120, value=WINDOW_SIZE)
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=10, max_value=100, value=30) / 100.0

# === FUNÇÕES AUXILIARES ===
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

# === FEATURES AVANÇADAS ===
def criar_features_avancadas(historico, window_size):
    if len(historico) < window_size + 1:
        return None, None

    X, y = [], []
    seq = list(historico)

    for i in range(len(seq) - window_size):
        janela = seq[i:i+window_size]
        alvo = seq[i+window_size]

        features = []

        # Sequência direta
        features.extend(janela)

        # Frequência simples
        contador = Counter(janela)
        freq1 = contador.get(1, 0)/window_size
        freq2 = contador.get(2, 0)/window_size
        freq3 = contador.get(3, 0)/window_size
        features.extend([freq1, freq2, freq3])

        # Frequência ponderada
        pesos = np.array([0.9**i for i in range(window_size-1, -1, -1)])
        freq1_w = sum(w for val, w in zip(janela, pesos) if val==1)/pesos.sum()
        freq2_w = sum(w for val, w in zip(janela, pesos) if val==2)/pesos.sum()
        freq3_w = sum(w for val, w in zip(janela, pesos) if val==3)/pesos.sum()
        features.extend([freq1_w, freq2_w, freq3_w])

        # Alternância simples
        alternancias = sum(1 for j in range(1, window_size) if janela[j] != janela[j-1])
        alt_norm = alternancias / (window_size-1)
        features.append(alt_norm)

        # Alternância ponderada
        alt_ponderada = sum((janela[j] != janela[j-1]) * 0.9**(window_size-1-j) for j in range(1, window_size)) / sum(0.9**i for i in range(window_size-1))
        features.append(alt_ponderada)

        # Tendência normalizada
        tend = [0,0,0]
        for val, w in zip(janela, pesos):
            if val in [1,2,3]:
                tend[val-1] += w
        total_tend = sum(tend) if sum(tend) > 0 else 1
        tend_norm = [t/total_tend for t in tend]
        features.extend(tend_norm)

        # Diferença de tendência
        tend_diff = max(tend_norm) - min(tend_norm)
        features.append(tend_diff)

        # Contagem de zeros
        zeros_count = janela.count(0)/window_size
        features.append(zeros_count)

        X.append(features)
        y.append(alvo)

    return np.array(X), np.array(y)

# === TREINAMENTO DO MODELO ===
def treinar_modelo_rf():
    X, y = criar_features_avancadas(st.session_state.historico, window_size=tamanho_janela)
    if X is None or len(X) == 0:
        return
    rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    rf.fit(X, y)
    st.session_state.modelo_rf = rf

# === PREVISÃO ===
def prever_duzia_rf():
    janela = list(st.session_state.historico)[-tamanho_janela:]
    features = []

    # Sequência direta
    features.extend(janela)

    # Frequência simples
    contador = Counter(janela)
    freq1 = contador.get(1, 0)/tamanho_janela
    freq2 = contador.get(2, 0)/tamanho_janela
    freq3 = contador.get(3, 0)/tamanho_janela
    features.extend([freq1, freq2, freq3])

    # Frequência ponderada
    pesos = np.array([0.9**i for i in range(tamanho_janela-1, -1, -1)])
    freq1_w = sum(w for val, w in zip(janela, pesos) if val==1)/pesos.sum()
    freq2_w = sum(w for val, w in zip(janela, pesos) if val==2)/pesos.sum()
    freq3_w = sum(w for val, w in zip(janela, pesos) if val==3)/pesos.sum()
    features.extend([freq1_w, freq2_w, freq3_w])

    # Alternância simples
    alternancias = sum(1 for j in range(1, tamanho_janela) if janela[j] != janela[j-1])
    alt_norm = alternancias / (tamanho_janela-1)
    features.append(alt_norm)

    # Alternância ponderada
    alt_ponderada = sum((janela[j] != janela[j-1]) * 0.9**(tamanho_janela-1-j) for j in range(1, tamanho_janela)) / sum(0.9**i for i in range(tamanho_janela-1))
    features.append(alt_ponderada)

    # Tendência normalizada
    tend = [0,0,0]
    for val, w in zip(janela, pesos):
        if val in [1,2,3]:
            tend[val-1] += w
    total_tend = sum(tend) if sum(tend) > 0 else 1
    tend_norm = [t/total_tend for t in tend]
    features.extend(tend_norm)

    # Diferença de tendência
    tend_diff = max(tend_norm) - min(tend_norm)
    features.append(tend_diff)

    # Contagem de zeros
    zeros_count = janela.count(0)/tamanho_janela
    features.append(zeros_count)

    features = np.array(features).reshape(1, -1)
    probs = st.session_state.modelo_rf.predict_proba(features)[0]
    classes = st.session_state.modelo_rf.classes_
    melhor_idx = np.argmax(probs)

    return classes[melhor_idx], probs[melhor_idx]

# === LOOP PRINCIPAL PROTEGIDO ===
# === LOOP PRINCIPAL PROTEGIDO ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico apenas se novo número
if len(st.session_state.historico) == 0 or numero_para_duzia(numero_atual) != st.session_state.historico[-1]:
    duzia_atual = salvar_historico_duzia(numero_atual)

    # Treina modelo RF se houver histórico suficiente
    if len(st.session_state.historico) >= tamanho_janela:
        treinar_modelo_rf()

    # Feedback de acertos
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

# Previsão segura
duzia_prevista, prob = None, 0.0
if st.session_state.modelo_rf is not None and len(st.session_state.historico) >= tamanho_janela:
    try:
        duzia_prevista, prob = prever_duzia_rf()
    except ValueError as e:
        st.warning(f"Erro de previsão (features incompatíveis): {e}")
        duzia_prevista, prob = None, 0.0

# Envio de alerta
if duzia_prevista is not None:
    chave_alerta = f"duzia_{duzia_prevista}"
    if chave_alerta != st.session_state.ultima_chave_alerta:
        st.session_state.ultima_entrada = [duzia_prevista]
        st.session_state.tipo_entrada_anterior = "duzia"
        st.session_state.contador_sem_alerta = 0
        st.session_state.ultima_chave_alerta = chave_alerta
        # Linha corrigida: emoji seguro e f-string única
        mensagem_alerta = f"📊 <b>ENTRADA DÚZIA RF:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)"
        enviar_telegram_async(mensagem_alerta)

# Interface
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
