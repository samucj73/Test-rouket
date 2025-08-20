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
WINDOW_SIZE = 35 # janela para RF

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
if "ultimo_numero_salvo" not in st.session_state:
    st.session_state.ultimo_numero_salvo = None
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior",
            "padroes_certos", "ultima_entrada", "modelo_rf_duzia", "modelo_rf_coluna",
            "ultimo_resultado_numero"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        elif var in ["modelo_rf_duzia", "modelo_rf_coluna"]:
            st.session_state[var] = None
        else:
            st.session_state[var] = 0

for k, v in estado_salvo.items():
    st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Dúzia + Coluna (RF + Features Avançadas)")
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

def salvar_historico_duzia(numero):
    duzia = numero_para_duzia(numero)
    st.session_state.historico.append(duzia)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

# === FEATURES ===
def extrair_features(janela):
    features = []
    window_size = len(janela)

    # Sequência direta
    features.extend(janela)

    # Frequência simples
    contador = Counter(janela)
    for d in [1, 2, 3]:
        features.append(contador.get(d, 0) / window_size)

    # Frequência ponderada
    pesos = np.array([0.9**i for i in range(window_size-1, -1, -1)])
    for d in [1, 2, 3]:
        fw = sum(w for val, w in zip(janela, pesos) if val == d) / pesos.sum()
        features.append(fw)

    # Alternância simples e ponderada
    alternancias = sum(1 for j in range(1, window_size) if janela[j] != janela[j-1])
    features.append(alternancias / (window_size-1))
    features.append(sum((janela[j] != janela[j-1]) * 0.9**(window_size-1-j) for j in range(1, window_size)) /
                    sum(0.9**i for i in range(window_size-1)))

    # Tendência normalizada
    tend = [0, 0, 0]
    for val, w in zip(janela, pesos):
        if val in [1, 2, 3]:
            tend[val-1] += w
    total = sum(tend) if sum(tend) > 0 else 1
    features.extend([t/total for t in tend])
    features.append(max(tend) - min(tend))

    # Contagem zeros
    features.append(janela.count(0) / window_size)

    # Última ocorrência de cada dúzia
    for d in [1, 2, 3]:
        try: idx = window_size - 1 - janela[::-1].index(d)
        except ValueError: idx = window_size
        features.append(idx / window_size)

    # Últimas 5 rodadas
    ult5 = janela[-5:]
    for d in [1, 2, 3]:
        features.append(ult5.count(d) / 5)

    return features

# === DATASETS (dúzia e coluna) ===
def criar_dataset_duzia(historico, tamanho_janela=15):
    X, y = [], []
    if len(historico) <= tamanho_janela:
        return np.empty((0, tamanho_janela)), np.array([])

    for i in range(len(historico) - tamanho_janela):
        janela = historico[i:i+tamanho_janela]
        X.append(janela)
        y.append(numero_para_duzia(historico[i+tamanho_janela]))
    return np.array(X), np.array(y)

def criar_dataset_coluna(historico, tamanho_janela=15):
    X, y = [], []
    if len(historico) <= tamanho_janela:
        return np.empty((0, tamanho_janela)), np.array([])

    for i in range(len(historico) - tamanho_janela):
        janela = historico[i:i+tamanho_janela]
        X.append(janela)
        y.append(numero_para_coluna(historico[i+tamanho_janela]))
    return np.array(X), np.array(y)

# === TREINAMENTO (2 modelos) ===
def treinar_modelos_rf():
    # Dúzia
    Xd, yd = criar_dataset_duzia(list(st.session_state.historico), tamanho_janela)
    if len(yd) > 1 and len(set(yd)) > 1:
        modelo_d = CatBoostClassifier(
            iterations=200,
            depth=6,
            learning_rate=0.1,
            loss_function='MultiClass',
            verbose=False
        )
        modelo_d.fit(Xd, yd)
        st.session_state.modelo_rf_duzia = modelo_d

    # Coluna
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

# === PREVISÃO (dúzia + coluna) ===
def prever_duzia_coluna_rf():
    janela = list(st.session_state.historico)[-tamanho_janela:]
    if len(janela) < tamanho_janela:
        return None, None, None, None

    features = np.array(extrair_features(janela)).reshape(1, -1)

    # Dúzia
    duzia, prob_d = None, None
    if st.session_state.modelo_rf_duzia is not None:
        try:
            probs_d = st.session_state.modelo_rf_duzia.predict_proba(features)[0]
            classes_d = st.session_state.modelo_rf_duzia.classes_
            idx_d = np.argmax(probs_d)
            duzia, prob_d = classes_d[idx_d], probs_d[idx_d]
        except Exception as e:
            st.warning(f"Erro previsão dúzia: {e}")

    # Coluna
    coluna, prob_c = None, None
    if st.session_state.modelo_rf_coluna is not None:
        try:
            probs_c = st.session_state.modelo_rf_coluna.predict_proba(features)[0]
            classes_c = st.session_state.modelo_rf_coluna.classes_
            idx_c = np.argmax(probs_c)
            coluna, prob_c = classes_c[idx_c], probs_c[idx_c]
        except Exception as e:
            st.warning(f"Erro previsão coluna: {e}")

    return duzia, prob_d, coluna, prob_c

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if numero_atual != st.session_state.ultimo_numero_salvo:
    duzia_atual = salvar_historico_duzia(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual

    if len(st.session_state.historico) >= tamanho_janela + 2 and len(st.session_state.historico) % 6 == 0:
        treinar_modelos_rf()

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

    if (st.session_state.modelo_rf_duzia is not None or st.session_state.modelo_rf_coluna is not None) \
            and len(st.session_state.historico) >= tamanho_janela:
        try:
            duzia, prob_d, coluna, prob_c = prever_duzia_coluna_rf()
            if duzia is not None and coluna is not None:
                st.session_state.ultima_entrada = (duzia, coluna)
                st.session_state.tipo_entrada_anterior = "duzia_coluna"
                st.session_state.contador_sem_alerta = 0
                st.session_state.ultima_chave_alerta = f"duzia_{duzia}_col_{coluna}"
                mensagem_alerta = (
                    "📊 <b>ENTRADA</b>\n"
                    f"{duzia}ª Dúzia ({prob_d*100:.1f}%) {coluna}ª Coluna ({prob_c*100:.1f}%)"
                )
                enviar_telegram_async(mensagem_alerta, delay=5)
                
        except Exception as e:
            st.warning(f"Erro na previsão: {e}")

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
    "modelo_rf_duzia": st.session_state.modelo_rf_duzia,
    "modelo_rf_coluna": st.session_state.modelo_rf_coluna,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero
}, ESTADO_PATH)

# === AUTO REFRESH ===
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
