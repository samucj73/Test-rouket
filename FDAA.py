import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from collections import deque
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import threading

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002880411750"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
PROB_MINIMA = 0.98
REFRESH_INTERVAL = 10000  # 10 segundos

ROULETTE_ORDER = [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
                  30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
                  29, 7, 28, 12, 35, 3, 26, 0]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=500)

for var in ["acertos_top", "total_top", "top3_anterior", "contador_sem_alerta", "tipo_entrada_anterior", "modelo_d", "modelo_c"]:
    if var not in st.session_state:
        st.session_state[var] = 0 if "acertos" in var or "total" in var or "contador" in var else []

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === FUNÇÕES ===
def enviar_telegram_async(mensagem):
    """Envia mensagem para o Telegram sem travar Streamlit"""
    def _send():
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)
    threading.Thread(target=_send, daemon=True).start()

def cor(numero):
    if numero == 0: return 'G'
    return 'R' if numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

def freq_valor(lista, valor):
    return lista.count(valor) / max(1, len(lista))

def distancia_fisica(n1, n2):
    if n1 not in ROULETTE_ORDER or n2 not in ROULETTE_ORDER:
        return 0
    idx1, idx2 = ROULETTE_ORDER.index(n1), ROULETTE_ORDER.index(n2)
    diff = abs(idx1 - idx2)
    return min(diff, len(ROULETTE_ORDER) - diff)

def extrair_features(historico):
    historico = list(historico)
    X, y = [], []
    historico_sem_ultimo = historico[:-1]
    for i in range(111, len(historico_sem_ultimo)):
        janela = historico_sem_ultimo[i-110:i]
        ult = historico_sem_ultimo[i-1]

        cores = [cor(n) for n in janela]
        vermelhos, pretos, verdes = cores.count('R'), cores.count('B'), cores.count('G')
        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = sum(1 for n in janela if n != 0 and n % 2 != 0)

        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0

        tempo_zero = next((idx for idx, val in enumerate(reversed(janela), 1) if val == 0), len(janela))
        dist_fisica = float(np.mean([distancia_fisica(ult, n) for n in janela[-3:]]))

        features = [vermelhos, pretos, verdes, pares, impares, duzia, coluna, tempo_zero, dist_fisica]
        X.append(features)
        y.append(historico_sem_ultimo[i])
    return np.array(X), np.array(y)

def treinar_modelo(historico, tipo="duzia"):
    if len(historico) < 120: return None
    X, y_raw = extrair_features(historico)
    if len(X) == 0: return None
    if tipo == "duzia":
        y = np.array([(n - 1) // 12 + 1 if n != 0 else 0 for n in y_raw])
    else:
        y = np.array([(n - 1) % 3 + 1 if n != 0 else 0 for n in y_raw])
    lgb = LGBMClassifier(n_estimators=300, learning_rate=0.05)
    rf = RandomForestClassifier(n_estimators=150)
    lgb.fit(X, y)
    rf.fit(X, y)
    return (lgb, rf)

def prever_top2(modelos_tuple, historico):
    if modelos_tuple is None or len(historico) < 120: return [], [], 0
    X, _ = extrair_features(historico)
    if X.size == 0: return [], [], 0
    x = X[-1].reshape(1, -1)
    lgb_model, rf_model = modelos_tuple
    classes = lgb_model.classes_
    try:
        p1 = lgb_model.predict_proba(x)[0]
        p2 = rf_model.predict_proba(x)[0]
        probs = (p1 + p2) / 2
        idxs = np.argsort(probs)[::-1][:2]
        top_labels = [int(classes[i]) for i in idxs]
        top_probs = [float(probs[i]) for i in idxs]
        return top_labels, top_probs, sum(top_probs)
    except:
        return [], [], 0

# === INTERFACE ===
st.title("🎯 IA Roleta Avançada - Ensemble LGBM + RF")
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")

try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Se chegou número novo
if len(st.session_state.historico) == 0 or numero_atual != st.session_state.historico[-1]:
    st.session_state.historico.append(numero_atual)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)

    # Atualiza métricas
    if st.session_state.top3_anterior:
        st.session_state.total_top += 1
        entrada_tipo = st.session_state.tipo_entrada_anterior
        valor = (numero_atual - 1) // 12 + 1 if entrada_tipo == "duzia" else (numero_atual - 1) % 3 + 1
        if valor in st.session_state.top3_anterior:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🟢")
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🔴")

    # Treina modelos só quando chega dado novo
    st.session_state.modelo_d = treinar_modelo(st.session_state.historico, "duzia")
    st.session_state.modelo_c = treinar_modelo(st.session_state.historico, "coluna")

    # Faz previsão
    if st.session_state.modelo_d and st.session_state.modelo_c:
        top_d, _, soma_d = prever_top2(st.session_state.modelo_d, st.session_state.historico)
        top_c, _, soma_c = prever_top2(st.session_state.modelo_c, st.session_state.historico)
        if soma_d >= soma_c:
            tipo, top, soma_prob = "duzia", top_d, soma_d
        else:
            tipo, top, soma_prob = "coluna", top_c, soma_c
        if soma_prob >= PROB_MINIMA:
            if top != st.session_state.top3_anterior or tipo != st.session_state.tipo_entrada_anterior:
                st.session_state.top3_anterior = top
                st.session_state.tipo_entrada_anterior = tipo
                st.session_state.contador_sem_alerta = 0
                enviar_telegram_async(f"📊 <b>ENTRADA {tipo.upper()}S:</b> {top[0]}ª e {top[1]}ª (conf: {soma_prob:.2%})")
            else:
                st.session_state.contador_sem_alerta += 1
                if st.session_state.contador_sem_alerta >= 3:
                    st.session_state.top3_anterior = top
                    st.session_state.tipo_entrada_anterior = tipo
                    st.session_state.contador_sem_alerta = 0
                    enviar_telegram_async(f"📊 <b>ENTRADA {tipo.upper()}S (forçada):</b> {top[0]}ª e {top[1]}ª")

# Interface limpa
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos números:", list(st.session_state.historico)[-12:])

# Salva estado
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "top3_anterior": st.session_state.top3_anterior,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior
}, ESTADO_PATH)
