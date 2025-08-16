import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque, Counter
from pathlib import Path
import threading
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT"
prob_minima = 0.40  # confiança mínima para enviar alerta

# === ESTADO ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=120)
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "ultima_entrada" not in st.session_state:
    st.session_state.ultima_entrada = None
if "tipo_entrada_anterior" not in st.session_state:
    st.session_state.tipo_entrada_anterior = None

# === INICIALIZA MODELO RANDOM FOREST ===
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = RandomForestClassifier(n_estimators=200, random_state=42)
    st.session_state.X_duzia = []
    st.session_state.y_duzia = []
    st.session_state.treinado_duzia = False

# === FUNÇÕES AUXILIARES ===
VERMELHOS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def enviar_telegram_async(msg):
    def _send():
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
        except:
            pass
    threading.Thread(target=_send, daemon=True).start()

def extrair_features(numero_atual, historico):
    duzia = (numero_atual - 1) // 12 if numero_atual != 0 else -1
    coluna = (numero_atual - 1) % 3 if numero_atual != 0 else -1
    cor = 0 if numero_atual == 0 else (1 if numero_atual in VERMELHOS else 2)
    paridade = -1 if numero_atual == 0 else numero_atual % 2

    freq_duzias = [sum(((n - 1) // 12) == i for n in historico if n != 0) for i in range(3)]
    freq_colunas = [sum(((n - 1) % 3) == i for n in historico if n != 0) for i in range(3)]

    ultimos = historico[-5:] if len(historico) >= 5 else historico
    lags = [((n - 1) // 12 if n != 0 else -1) for n in ultimos]

    return [duzia, coluna, cor, paridade, *freq_duzias, *freq_colunas, *lags]

def prever_duzia_com_feedback(numero_atual, historico):
    if len(historico) < 15:
        return None, None

    X = extrair_features(numero_atual, historico[:-1])
    y = (numero_atual - 1) // 12 if numero_atual != 0 else -1

    st.session_state.X_duzia.append(X)
    st.session_state.y_duzia.append(y)

    if len(st.session_state.X_duzia) > 50 and len(st.session_state.X_duzia) % 20 == 0:
        try:
            st.session_state.modelo_duzia.fit(st.session_state.X_duzia, st.session_state.y_duzia)
            st.session_state.treinado_duzia = True
        except Exception as e:
            st.warning(f"Erro treino dúzia: {e}")

    if st.session_state.treinado_duzia:
        X_pred = extrair_features(numero_atual, historico)
        proba = st.session_state.modelo_duzia.predict_proba([X_pred])[0]

        top2 = np.argsort(proba)[-2:][::-1]
        conf = [proba[i] for i in top2]
        return top2, conf

    return None, None

# === LOOP PRINCIPAL ===
st_autorefresh(interval=5000, key="refresh")

try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if not st.session_state.historico or st.session_state.historico[-1] != numero_atual:
    st.session_state.historico.append(numero_atual)

    top_duzias, confiancas = prever_duzia_com_feedback(numero_atual, list(st.session_state.historico))

    if top_duzias is not None:
        chave_alerta = f"duzias_{top_duzias[0]}_{top_duzias[1]}"

        if chave_alerta != st.session_state.ultima_chave_alerta and max(confiancas) >= prob_minima:
            st.session_state.ultima_entrada = list(top_duzias)
            st.session_state.tipo_entrada_anterior = "duzia"
            st.session_state.ultima_chave_alerta = chave_alerta

            enviar_telegram_async(
                f"📊 <b>ENTRADA DÚZIA:</b> {top_duzias[0]+1}ª ({confiancas[0]*100:.1f}%) "
                f"ou {top_duzias[1]+1}ª ({confiancas[1]*100:.1f}%)"
            )

# Interface limpa
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])
#st.write(f"📊 Pesos dinâmicos → Frequência: {pesos[0]:.2f}, Tendência: {pesos[1]:.2f}, Repetição: {pesos[2]:.2f}")

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
