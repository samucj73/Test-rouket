# Domina03.py (com conferência de alertas)
import streamlit as st
import json
import os
import requests
from collections import deque
import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
METRICAS_PATH = "historico_metricas.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18
MIN_TOP_N = 5
MAX_PREVIEWS = 15

# =============================
# Utilitários
# =============================
def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")

def enviar_telegram_unico(msg: str):
    if not st.session_state.get("sending_lock", False):
        st.session_state.sending_lock = True
        try:
            enviar_telegram(msg)
        finally:
            st.session_state.sending_lock = False

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            return json.load(f)
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f, indent=2)

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=6)
        r.raise_for_status()
        data = r.json().get("data", {})
        result = data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = data.get("startedAt")
        if timestamp and number is not None:
            return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro fetch API: {e}")
    return None

def obter_vizinhos(numero, layout, antes=2, depois=2):
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = [layout[(idx - i) % n] for i in range(antes, 0, -1)]
    vizinhos.append(numero)
    vizinhos += [layout[(idx + i) % n] for i in range(1, depois + 1)]
    return vizinhos

# =============================
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=15000)
    def adicionar_numero(self, numero_dict):
        if numero_dict not in self.historico:
            self.historico.append(numero_dict)

# =============================
# IA Recorrência
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=3, window=WINDOW_SIZE):
        self.layout = layout
        self.top_n = top_n
        self.window = window
        self.model = None

    def _criar_features(self, historico):
        numeros = [h["number"] for h in historico]
        if len(numeros) < 3:
            return None, None
        X, y = [], []
        for i in range(2, len(numeros)):
            last2, last1 = numeros[i-2], numeros[i-1]
            feats = [last2, last1] + obter_vizinhos(last1, self.layout, 1,1)
            X.append(feats)
            y.append(numeros[i])
        return np.array(X), np.array(y)

    def treinar(self, historico):
        X, y = self._criar_features(historico)
        if X is None or len(X) == 0:
            self.model = None
            return
        self.model = RandomForestClassifier(n_estimators=200, random_state=42)
        self.model.fit(X, y)

    def prever(self, historico):
        if len(historico) < 2:
            return []
        ultimo = historico[-1]["number"]
        self.treinar(historico[-self.window:])
        candidatos = [ultimo]
        if self.model:
            last2 = historico[-2]["number"]
            feats = [last2, ultimo] + obter_vizinhos(ultimo, self.layout, 1,1)
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                idx_top = np.argsort(probs)[-self.top_n:]
                top_ml = [int(classes[i]) for i in idx_top]
                candidatos += top_ml
            except:
                pass
        numeros_previstos = []
        for n in candidatos:
            for v in obter_vizinhos(n, self.layout, 2,2):
                if v not in numeros_previstos:
                    numeros_previstos.append(v)
        return numeros_previstos[:MAX_PREVIEWS]

# =============================
# Inicialização Streamlit
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência + Conferência")
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()
if "ia_recorrencia" not in st.session_state:
    st.session_state.ia_recorrencia = IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5)
if "previsao_sent_for_timestamp" not in st.session_state:
    st.session_state.previsao_sent_for_timestamp = None
if "aguardando_resultado" not in st.session_state:
    st.session_state.aguardando_resultado = False
if "acertos" not in st.session_state:
    st.session_state.acertos = 0
if "erros" not in st.session_state:
    st.session_state.erros = 0

# Carrega histórico
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)
    st.session_state.ultimo_timestamp = n.get("timestamp")

# -----------------------------
# Captura número da API
# -----------------------------
resultado = fetch_latest_result()
if resultado and resultado.get("timestamp"):
    if st.session_state.ultimo_timestamp != resultado["timestamp"]:
        st.session_state.ultimo_timestamp = resultado["timestamp"]
        st.session_state.estrategia.adicionar_numero(resultado)
        salvar_historico(list(st.session_state.estrategia.historico))
        st.session_state.aguardando_resultado = True

# -----------------------------
# Geração de previsão
# -----------------------------
if st.session_state.aguardando_resultado and st.session_state.ultimo_timestamp != st.session_state.previsao_sent_for_timestamp:
    prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
    if prox_numeros:
        st.session_state.previsao_sent_for_timestamp = st.session_state.ultimo_timestamp
        mensagem = "🎯 PREVISÃO: " + " ".join(map(str, prox_numeros[:5]))
        if len(prox_numeros) > 5:
            mensagem += " ... " + " ".join(map(str, prox_numeros[5:]))
        enviar_telegram_unico(mensagem)

# -----------------------------
# Conferência GREEN/RED
# -----------------------------
ultimo_numero = resultado["number"] if resultado else None
if st.session_state.aguardando_resultado and ultimo_numero:
    topN = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
    topN_vizinhos = []
    for n in topN[:5]:
        topN_vizinhos += obter_vizinhos(n, ROULETTE_LAYOUT, 2,2)
    if ultimo_numero in topN_vizinhos:
        st.session_state.acertos += 1
        enviar_telegram_unico(f"🟢 GREEN! Número: {ultimo_numero}")
    else:
        st.session_state.erros += 1
        enviar_telegram_unico(f"🔴 RED! Número: {ultimo_numero}")
    st.session_state.aguardando_resultado = False

# -----------------------------
# Interface
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
ultimos = list(st.session_state.estrategia.historico)[-3:]
st.write(ultimos)

acertos = st.session_state.acertos
erros = st.session_state.erros
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0
st.metric("🟢 GREEN", acertos)
st.metric("🔴 RED", erros)
st.metric("✅ Taxa de acerto", f"{taxa:.1f}%")
st.write(f"Total no histórico: {len(st.session_state.estrategia.historico)}")
