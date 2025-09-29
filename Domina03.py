# Domina03.py (versão final — controle de 1 alerta por rodada + lock de envio corrigido)
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
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

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
# Utilitários (Telegram, histórico, API, vizinhos)
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_telegram_unico(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    if "sending_lock" not in st.session_state:
        st.session_state.sending_lock = False
    if st.session_state.sending_lock:
        return
    st.session_state.sending_lock = True
    try:
        enviar_telegram(msg, token=token, chat_id=chat_id)
    except Exception as e:
        logging.error(f"Erro enviar_telegram_unico: {e}")
    finally:
        st.session_state.sending_lock = False

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            # Remove duplicatas
            seen = set()
            hist_clean = []
            for h in historico:
                ts = h.get("timestamp")
                if ts not in seen:
                    seen.add(ts)
                    hist_clean.append(h)
            return hist_clean
        except:
            return []
    return []

def salvar_historico(historico):
    try:
        seen = set()
        hist_clean = []
        for h in historico:
            ts = h.get("timestamp")
            if ts not in seen:
                seen.add(ts)
                hist_clean.append(h)
        with open(HISTORICO_PATH, "w") as f:
            json.dump(hist_clean, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def salvar_metricas(m):
    try:
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
        return None
    except Exception as e:
        logging.error(f"Erro fetch_latest_result: {e}")
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
            if existing.get("timestamp") == numero_dict.get("timestamp"):
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
        if len(numeros) < 3: return None, None
        X, y = [], []
        for i in range(2, len(numeros)):
            last2 = numeros[i-2]
            last1 = numeros[i-1]
            nbrs = obter_vizinhos(last1, self.layout, antes=2, depois=2)
            feat = [last2, last1] + nbrs
            X.append(feat)
            y.append(numeros[i])
        return np.array(X), np.array(y)

    def treinar(self, historico):
        X, y = self._criar_features_simples(historico)
        if X is None or len(X)==0:
            self.model = None
            return
        try:
            self.model = RandomForestClassifier(n_estimators=200, random_state=42)
            self.model.fit(X, y)
        except:
            self.model = None

    def prever(self, historico):
        if not historico or len(historico) < 2: return []
        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"]
        candidatos = []

        window_hist = historico_lista[-max(len(historico_lista), self.window):]
        self.treinar(window_hist)

        if self.model:
            numeros = [h["number"] for h in historico_lista]
            last2 = numeros[-2] if len(numeros)>1 else 0
            last1 = numeros[-1]
            feats = [last2,last1]+obter_vizinhos(last1,self.layout,1,1)
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                idx_top = np.argsort(probs)[-self.top_n:]
                candidatos = [int(classes[i]) for i in idx_top]
            except:
                pass

        numeros_previstos = []
        for n in candidatos:
            for v in obter_vizinhos(n,self.layout,2,2):
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        return numeros_previstos[:MAX_PREVIEWS]

# =============================
# Redução inteligente Top N
# =============================
def ajustar_top_n(previsoes, historico=None, min_n=MIN_TOP_N, max_n=MAX_TOP_N):
    if not previsoes: return previsoes[:min_n]
    pesos = {n:1.0 for n in previsoes}
    ordenados = sorted(pesos.keys(), key=lambda x: pesos[x], reverse=True)
    n = max(min_n, min(max_n, len(ordenados)))
    return ordenados[:n]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência (RandomForest) + Redução Inteligente")
st_autorefresh(interval=3000, key="refresh")

# Session state
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5, window=WINDOW_SIZE),
    "previsao_para_conferir": [],
    "previsao_topN_para_conferir": [],
    "acertos":0,"erros":0,"acertos_topN":0,"erros_topN":0,
    "contador_rodadas":0,"ultimo_timestamp":None,
    "aguardando_resultado":False,
    "ultima_previsao":None,
    "previsao_sent_for_timestamp":None,
    "sending_lock":False,
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v

# Carrega histórico
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)
    st.session_state.ultimo_timestamp = n.get("timestamp")

# -----------------------------
# Captura número
# -----------------------------
resultado = fetch_latest_result()
novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if st.session_state.ultimo_timestamp != resultado["timestamp"]:
        novo_sorteio = True

# Processa novo sorteio
if resultado and novo_sorteio:
    numero_dict = {"number":resultado["number"],"timestamp":resultado["timestamp"]}
    st.session_state.ultimo_timestamp = resultado["timestamp"]
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    numero_real = numero_dict["number"]

    # -----------------------------
    # Conferência do resultado (apenas 1 alerta)
    # -----------------------------
    if st.session_state.aguardando_resultado and st.session_state.ultima_previsao:
        if st.session_state.previsao_sent_for_timestamp != resultado["timestamp"]:
            # Recorrência
            numeros_com_vizinhos = []
            for n in st.session_state.previsao_para_conferir:
                for v in obter_vizinhos(n, ROULETTE_LAYOUT,1,1):
                    if v not in numeros_com_vizinhos:
                        numeros_com_vizinhos.append(v)
            hit_rec = numero_real in numeros_com_vizinhos

            # TopN
            topN_com_vizinhos = []
            for n in st.session_state.previsao_topN_para_conferir:
                for v in obter_vizinhos(n, ROULETTE_LAYOUT,1,1):
                    if v not in topN_com_vizinhos:
                        topN_com_vizinhos.append(v)
            hit_topn = numero_real in topN_com_vizinhos

            if hit_rec: st.session_state.acertos+=1
            else: st.session_state.erros+=1
            if hit_topn: st.session_state.acertos_topN+=1
            else: st.session_state.erros_topN+=1

            partes = [
                f"{'🟢 GREEN' if hit_rec else '🔴 RED'} (Recorrência) — Número sorteado: {numero_real}",
                f"{'🟢 GREEN' if hit_topn else '🔴 RED'} (TopN) — Número {'entre os mais prováveis' if hit_topn else 'não previsto'}"
            ]
            enviar_telegram_unico("\n".join(partes))

            st.session_state.aguardando_resultado=False
            st.session_state.ultima_previsao=None
            st.session_state.previsao_sent_for_timestamp=resultado["timestamp"]

# -----------------------------
# Geração nova previsão (apenas 1 alerta)
# -----------------------------
if not st.session_state.aguardando_resultado:
    if st.session_state.ultimo_timestamp is not None and st.session_state.previsao_sent_for_timestamp != st.session_state.ultimo_timestamp:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            prox_numeros = list(dict.fromkeys(prox_numeros))
            st.session_state.previsao_para_conferir=prox_numeros
            entrada_topN=ajustar_top_n(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao_topN_para_conferir=entrada_topN
            st.session_state.ultima_previsao={
                "previsao": prox_numeros,
                "topN": entrada_topN,
                "for_timestamp": st.session_state.ultimo_timestamp
            }
            s = sorted(prox_numeros)
            msg_parts=[ "🎯 PREVISÃO (Recorrência): "+ " ".join(map(str,s[:5])) ]
            if len(s)>5:
                msg_parts.append("... "+ " ".join(map(str,s[5:])))
            if entrada_topN:
                msg_parts.append("🔝 TOP N: "+ " ".join(map(str,sorted(entrada_topN))))
            mensagem_previsao="\n".join(msg_parts)
            enviar_telegram_unico(mensagem_previsao)
            st.session_state.previsao_sent_for_timestamp=st.session_state.ultimo_timestamp
            st.session_state.aguardando_resultado=True

# -----------------------------
# Interface Streamlit
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
ultimos = list(st.session_state.estrategia.historico)[-3:]
st.write(ultimos)

acertos = st.session_state.acertos
erros = st.session_state.erros
total = acertos+erros
taxa = (acertos/total*100) if total>0 else 0.0
qtd_previstos_rec = len(st.session_state.previsao_para_conferir or [])
col1,col2,col3,col4=st.columns(4)
col1.metric("🟢 GREEN",acertos)
col2.metric("🔴 RED",erros)
col3.metric("✅ Taxa de acerto",f"{taxa:.1f}%")
col4.metric("🎯 Qtd. previstos Recorrência",qtd_previstos_rec)

acertos_topN = st.session_state.acertos_topN
erros_topN = st.session_state.erros_topN
total_topN = acertos_topN+erros_topN
taxa_topN = (acertos_topN/total_topN*100) if total_topN>0 else 0.0
qtd_previstos_topN = len(st.session_state.previsao_topN_para_conferir or [])
col1,col2,col3,col4=st.columns(4)
col1.metric("🟢 GREEN Top N",acertos_topN)
col2.metric("🔴 RED Top N",erros_topN)
col3.metric("✅ Taxa Top N",f
