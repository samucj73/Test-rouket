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
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 5 segundos
WINDOW_SIZE = 45  # janela para análise
TREINO_A_CADA = 50  # treinar a cada X rodadas

# === CARREGA ESTADO ===
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try:
        ESTADO_PATH.unlink()
    except Exception:
        pass
    estado_salvo = {}

# === SESSION STATE ===
for var, default in [
    ("ultimo_numero_salvo", None), ("ultima_chave_alerta", None),
    ("historico", deque(maxlen=MAX_HIST_LEN)), ("acertos_top", 0),
    ("total_top", 0), ("contador_sem_alerta", 0), ("tipo_entrada_anterior", ""),
    ("padroes_certos", []), ("ultima_entrada", []), ("modelo_rf_coluna", None),
    ("ultimo_resultado_numero", 0), ("rodadas_desde_treino", 0)
]:
    if var not in st.session_state:
        st.session_state[var] = default

for k, v in estado_salvo.items():
    st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Robô Dinâmico Dúzia + Coluna")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=5, max_value=150, value=WINDOW_SIZE)
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=10, max_value=100, value=30) / 100.0

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

def salvar_historico(numero):
    duzia = numero_para_duzia(numero)
    st.session_state.historico.append(duzia)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

# === FEATURES Coluna ===
def criar_dataset_coluna(historico, tamanho_janela=15):
    X, y = [], []
    if len(historico) <= tamanho_janela:
        return np.empty((0, tamanho_janela)), np.array([])
    for i in range(len(historico) - tamanho_janela):
        janela = historico[i:i+tamanho_janela]
        X.append(janela)
        y.append(numero_para_coluna(historico[i+tamanho_janela]))
    return np.array(X), np.array(y)

# === TREINAMENTO Coluna ===
def treinar_modelo_coluna():
    st.info("⚙️ Treinando modelo Coluna (CatBoost)...")
    Xc, yc = criar_dataset_coluna(list(st.session_state.historico), tamanho_janela)
    if len(yc) > 1 and len(set(yc)) > 1:
        modelo_c = CatBoostClassifier(
            iterations=200,
            depth=6,
            learning_rate=0.1,
            loss_function='MultiClass',
            verbose=False
        )
        modelo_c.fit(Xc, yc)
        st.session_state.modelo_rf_coluna = modelo_c

# === PREVISÃO Dinâmica Dúzia + Coluna ===
def prever_entrada():
    janela = list(st.session_state.historico)[-tamanho_janela:]
    if len(janela) < tamanho_janela:
        return None, None
    # Dúzia: frequência ponderada
    pesos = np.array([0.9**i for i in range(len(janela)-1, -1, -1)])
    freq = Counter()
    for val, w in zip(janela, pesos):
        freq[val] += w
    total = sum(freq.values())
    duzia_prob = {k: v/total for k,v in freq.items() if k!=0}
    duzia = max(duzia_prob, key=duzia_prob.get)
    prob_duzia = duzia_prob[duzia]

    # Coluna
    coluna, prob_coluna = None, None
    if st.session_state.modelo_rf_coluna is not None:
        try:
            features = np.array(janela).reshape(1,-1)
            probs_c = st.session_state.modelo_rf_coluna.predict_proba(features)[0]
            classes_c = st.session_state.modelo_rf_coluna.classes_
            idx_c = np.argmax(probs_c)
            coluna, prob_coluna = classes_c[idx_c], probs_c[idx_c]
        except:
            coluna, prob_coluna = None, None

    return (duzia, prob_duzia, coluna, prob_coluna)

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if numero_atual != st.session_state.ultimo_numero_salvo:
    salvar_historico(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual
    st.session_state.rodadas_desde_treino += 1

    if st.session_state.rodadas_desde_treino >= TREINO_A_CADA:
        treinar_modelo_coluna()
        st.session_state.rodadas_desde_treino = 0

# === ALERTA DE RESULTADO ===
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual
    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor_duzia = numero_para_duzia(numero_atual)
        valor_coluna = numero_para_coluna(numero_atual)
        if valor_duzia == st.session_state.ultima_entrada[0] or valor_coluna == st.session_state.ultima_entrada[1]:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} → 🟢", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} → 🔴", delay=1)

    duzia, prob_d, coluna, prob_c = prever_entrada()
    if duzia is not None and coluna is not None:
        st.session_state.ultima_entrada = (duzia, coluna)
        mensagem_alerta = (
            "📊 ENTRADA\n"
            f"{duzia}ª Dúzia ({prob_d*100:.1f}%) {coluna}ª Coluna ({prob_c*100:.1f}%)"
        )
        enviar_telegram_async(mensagem_alerta, delay=5)

# === INTERFACE ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])

# === SALVA ESTADO ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "ultima_entrada": st.session_state.ultima_entrada,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "modelo_rf_coluna": st.session_state.modelo_rf_coluna,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero,
    "rodadas_desde_treino": st.session_state.rodadas_desde_treino
}, ESTADO_PATH)

# === AUTO REFRESH ===
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
