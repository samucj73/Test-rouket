# Domina03.py (versão final — previsão inicial imediata + controle de 1 alerta por rodada)
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
MAX_TOP_N = 10
MAX_PREVIEWS = 15

# =============================
# Utilitários
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_telegram_unico(msg: str):
    if "sending_lock" not in st.session_state:
        st.session_state.sending_lock = False
    if st.session_state.sending_lock:
        logging.warning("Envio ignorado: lock ativo")
        return
    st.session_state.sending_lock = True
    try:
        enviar_telegram(msg)
    finally:
        st.session_state.sending_lock = False

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            historico_sem_duplicatas = []
            timestamps_vistos = set()
            for h in historico:
                if isinstance(h, dict) and "timestamp" in h:
                    if h["timestamp"] not in timestamps_vistos:
                        timestamps_vistos.add(h["timestamp"])
                        historico_sem_duplicatas.append(h)
                else:
                    historico_sem_duplicatas.append(h)
            return historico_sem_duplicatas
        except Exception as e:
            logging.error(f"Erro ao carregar histórico: {e}")
            return []
    return []

def salvar_historico(historico):
    try:
        historico_sem_duplicatas = []
        timestamps_vistos = set()
        for h in historico:
            if isinstance(h, dict) and "timestamp" in h:
                if h["timestamp"] not in timestamps_vistos:
                    timestamps_vistos.add(h["timestamp"])
                    historico_sem_duplicatas.append(h)
            else:
                historico_sem_duplicatas.append(h)
        with open(HISTORICO_PATH, "w") as f:
            json.dump(historico_sem_duplicatas, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def salvar_metricas(m):
    try:
        hist = []
        if os.path.exists(METRICAS_PATH):
            try:
                with open(METRICAS_PATH, "r") as f:
                    hist = json.load(f)
            except Exception:
                hist = []
        hist.append(m)
        with open(METRICAS_PATH, "w") as f:
            json.dump(hist, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar métricas: {e}")

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=6)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        if timestamp and number is not None:
            return {"number": number, "timestamp": timestamp}
        else:
            return None
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def obter_vizinhos(numero, layout, antes=2, depois=2):
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

# =============================
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=15000)
    
    def adicionar_numero(self, numero_dict):
        if not numero_dict or "timestamp" not in numero_dict:
            return
        for existing in self.historico:
            if isinstance(existing, dict) and existing.get("timestamp") == numero_dict.get("timestamp"):
                return
        self.historico.append(numero_dict)

# =============================
# IA Recorrência
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=3, window=WINDOW_SIZE):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.window = window
        self.model = None

    def _criar_features_simples(self, historico: List[dict]):
        numeros = [h["number"] for h in historico]
        if len(numeros) < 3:
            return None, None
        X, y = [], []
        for i in range(2, len(numeros)):
            last2, last1 = numeros[i-2], numeros[i-1]
            nbrs = obter_vizinhos(last1, self.layout, antes=2, depois=2)
            feat = [last2, last1] + nbrs
            X.append(feat)
            y.append(numeros[i])
        return np.array(X), np.array(y)

    def treinar(self, historico):
        X, y = self._criar_features_simples(historico)
        if X is None or len(X) == 0:
            self.model = None
            return
        try:
            self.model = RandomForestClassifier(n_estimators=200, random_state=42)
            self.model.fit(X, y)
        except Exception as e:
            logging.error(f"Erro treinando RF: {e}")
            self.model = None

    def prever(self, historico):
        if not historico or len(historico) < 2:
            return []
        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"]
        self.treinar(historico_lista[-self.window:])
        candidatos = [ultimo_numero]
        if self.model is not None:
            last2 = historico_lista[-2]["number"]
            feats = [last2, ultimo_numero] + obter_vizinhos(ultimo_numero, self.layout, antes=1, depois=1)
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
            for v in obter_vizinhos(n, self.layout, antes=2, depois=2):
                if v not in numeros_previstos:
                    numeros_previstos.append(v)
        return numeros_previstos[:MAX_PREVIEWS]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência (RandomForest) + Redução Inteligente")
st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5, window=WINDOW_SIZE),
    "previsao_para_conferir": [],
    "previsao_topN_para_conferir": [],
    "acertos": 0,
    "erros": 0,
    "acertos_topN": 0,
    "erros_topN": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "aguardando_resultado": False,
    "ultima_previsao": None,
    "previsao_sent_for_timestamp": None,
    "ultimo_numero_recebido": None,
    "sending_lock": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Carregar histórico
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)
    st.session_state.ultimo_timestamp = n.get("timestamp")
    
# -----------------------------
# Captura número da API
# -----------------------------
resultado = fetch_latest_result()
novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if st.session_state.ultimo_timestamp != resultado["timestamp"]:
        novo_sorteio = True
        st.session_state.ultimo_timestamp = resultado["timestamp"]
        st.session_state.estrategia.adicionar_numero(resultado)
        salvar_historico(list(st.session_state.estrategia.historico))

# -----------------------------
# Geração de nova previsão (corrigido: primeira previsão mesmo sem novo sorteio)
# -----------------------------
if not st.session_state.aguardando_resultado:
    ultimo_num_timestamp = st.session_state.ultimo_timestamp
    if ultimo_num_timestamp and (st.session_state.previsao_sent_for_timestamp != ultimo_num_timestamp):
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao_para_conferir = prox_numeros
            st.session_state.previsao_topN_para_conferir = prox_numeros[:MIN_TOP_N]
            st.session_state.ultima_previsao = {"previsao": prox_numeros, "topN": prox_numeros[:MIN_TOP_N]}
            s = sorted(prox_numeros)
            mensagem_parts = ["🎯 PREVISÃO: " + " ".join(map(str, s[:5]))]
            if len(s) > 5:
                mensagem_parts.append("... " + " ".join(map(str, s[5:])))
            mensagem_previsao = "\n".join(mensagem_parts)
            enviar_telegram_unico(mensagem_previsao)
            st.session_state.previsao_sent_for_timestamp = ultimo_num_timestamp
            st.session_state.aguardando_resultado = True

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
