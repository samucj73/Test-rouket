# Domina03.py (versão final — controle de 1 alerta por rodada + lock de envio)
import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from typing import List

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
METRICAS_PATH = "historico_metricas.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Canal principal
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

# Canal alternativo (opcional)
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "SEU_CHAT_ID_ALT"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18
MIN_TOP_N = 5
MAX_TOP_N = 10
MAX_PREVIEWS = 15

# =============================
# Telegram
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg}, timeout=10)
    except Exception as e:
        logging.error(f"Erro Telegram: {e}")

def enviar_telegram_unico(msg: str):
    if "sending_lock" not in st.session_state:
        st.session_state.sending_lock = False
    if st.session_state.sending_lock:
        return
    st.session_state.sending_lock = True
    try:
        enviar_telegram(msg)
    finally:
        st.session_state.sending_lock = False

# =============================
# Histórico
# =============================
def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            visto, filtrado = set(), []
            for h in historico:
                ts = h.get("timestamp")
                if ts not in visto:
                    visto.add(ts)
                    filtrado.append(h)
            return filtrado
        except:
            return []
    return []

def salvar_historico(historico):
    visto, filtrado = set(), []
    for h in historico:
        ts = h.get("timestamp")
        if ts not in visto:
            visto.add(ts)
            filtrado.append(h)
    with open(HISTORICO_PATH, "w") as f:
        json.dump(filtrado, f, indent=2)

def salvar_metricas(m):
    hist = []
    if os.path.exists(METRICAS_PATH):
        try:
            with open(METRICAS_PATH, "r") as f:
                hist = json.load(f)
        except:
            hist = []
    hist.append(m)
    with open(METRICAS_PATH, "w") as f:
        json.dump(hist, f, indent=2)

# =============================
# API & Vizinhos
# =============================
def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=6).json()
        number = r.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        ts = r.get("data", {}).get("startedAt")
        if ts and number is not None:
            return {"number": number, "timestamp": ts}
    except Exception as e:
        logging.error(f"API error: {e}")
    return None

def obter_vizinhos(num, layout, antes=2, depois=2):
    if num not in layout: return [num]
    idx, n = layout.index(num), len(layout)
    viz = [layout[(idx - i) % n] for i in range(antes, 0, -1)] + [num] + [layout[(idx + i) % n] for i in range(1, depois+1)]
    return viz

# =============================
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self): self.historico = deque(maxlen=15000)
    def adicionar_numero(self, nd): 
        if not nd or "timestamp" not in nd: return
        if any(h.get("timestamp") == nd["timestamp"] for h in self.historico): return
        self.historico.append(nd)

# =============================
# IA Recorrência
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=3, window=WINDOW_SIZE):
        self.layout, self.top_n, self.window, self.model = layout or ROULETTE_LAYOUT, top_n, window, None

    def _criar_features_simples(self, hist):
        nums = [h["number"] for h in hist]
        if len(nums) < 3: return None, None
        X, y = [], []
        for i in range(2, len(nums)):
            f = [nums[i-2], nums[i-1]] + obter_vizinhos(nums[i-1], self.layout, 2, 2)
            X.append(f); y.append(nums[i])
        return np.array(X), np.array(y)

    def treinar(self, hist):
        X, y = self._criar_features_simples(hist)
        if X is None: return
        self.model = RandomForestClassifier(n_estimators=200, random_state=42).fit(X, y)

    def prever(self, hist):
        if len(hist) < 2: return []
        nums = [h["number"] for h in hist]
        last2, last1 = nums[-2], nums[-1]
        feats = [last2, last1] + obter_vizinhos(last1, self.layout, 1, 1)
        self.treinar(hist[-self.window:])
        candidatos = []
        if self.model:
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                idx_top = np.argsort(probs)[-self.top_n:]
                candidatos = [int(classes[i]) for i in idx_top]
            except: pass
        prevs = []
        for n in candidatos:
            for v in obter_vizinhos(n, self.layout, 2, 2):
                if v not in prevs: prevs.append(v)
        return prevs[:MAX_PREVIEWS]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA", layout="centered")
st.title("🎯 Roleta — IA Profissional")
st_autorefresh(interval=3000, key="refresh")

# Estado inicial
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia": IA_Recorrencia_RF(),
    "aguardando_resultado": False,
    "ultima_previsao": None,
    "ultimo_timestamp": None,
    "acertos": 0, "erros": 0,
    "acertos_topN": 0, "erros_topN": 0,
    "sending_lock": False,
}
for k,v in defaults.items(): st.session_state.setdefault(k,v)

# Carregar histórico
for n in carregar_historico():
    st.session_state.estrategia.adicionar_numero(n)
    st.session_state.ultimo_timestamp = n.get("timestamp")

# Captura API
res = fetch_latest_result()
novo = res and res["timestamp"] != st.session_state.ultimo_timestamp
if res and novo:
    num = res["number"]; ts = res["timestamp"]
    st.session_state.ultimo_timestamp = ts
    st.session_state.estrategia.adicionar_numero(res)
    salvar_historico(list(st.session_state.estrategia.historico))

    # Conferência
    if st.session_state.aguardando_resultado and st.session_state.ultima_previsao:
        hit = num in st.session_state.ultima_previsao
        if hit: st.session_state.acertos += 1; msg = f"🟢 GREEN — {num}"
        else: st.session_state.erros += 1; msg = f"🔴 RED — {num}"
        enviar_telegram_unico(msg)
        st.session_state.aguardando_resultado = False

    # Nova previsão
    prev = st.session_state.ia.prever(st.session_state.estrategia.historico)
    if prev:
        st.session_state.ultima_previsao = prev
        st.session_state.aguardando_resultado = True
        enviar_telegram_unico("🎯 PREVISÃO: " + " ".join(map(str, prev)))

# UI
st.subheader("📜 Histórico")
st.write(list(st.session_state.estrategia.historico)[-5:])
