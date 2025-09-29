# Domina03.py (completo - alertas únicos e conferência)
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

# Telegram
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
TOP_N_COOLDOWN = 3
TOP_N_PROB_BASE = 0.3
TOP_N_PROB_MAX = 0.5
TOP_N_PROB_MIN = 0.2
TOP_N_WINDOW = 12

# =============================
# Funções utilitárias
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram Top N: {e}")

def enviar_alerta_unico(msg: str, hash_unico: str, topN=False):
    """Envia alerta apenas se ainda não foi enviado"""
    estado_chave = f"alerta_enviado_{hash_unico}"
    if estado_chave not in st.session_state:
        if topN:
            enviar_telegram_topN(msg)
        else:
            enviar_telegram(msg)
        st.session_state[estado_chave] = True
        logging.info(f"Alerta enviado: {msg}")
    else:
        logging.info(f"Alerta já enviado anteriormente, ignorando: {msg}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            # Remove duplicatas
            timestamps_vistos = set()
            historico_unico = []
            for h in historico:
                if isinstance(h, dict) and "timestamp" in h:
                    if h["timestamp"] not in timestamps_vistos:
                        timestamps_vistos.add(h["timestamp"])
                        historico_unico.append(h)
                else:
                    historico_unico.append(h)
            return historico_unico
        except Exception as e:
            logging.error(f"Erro carregar histórico: {e}")
            return []
    return []

def salvar_historico(historico):
    try:
        timestamps_vistos = set()
        historico_unico = []
        for h in historico:
            if isinstance(h, dict) and "timestamp" in h:
                if h["timestamp"] not in timestamps_vistos:
                    timestamps_vistos.add(h["timestamp"])
                    historico_unico.append(h)
            else:
                historico_unico.append(h)
        with open(HISTORICO_PATH, "w") as f:
            json.dump(historico_unico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro salvar histórico: {e}")

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
        logging.error(f"Erro salvar métricas: {e}")

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=6)
        r.raise_for_status()
        data = r.json()
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
    vizinhos = [layout[(idx - i) % n] for i in range(antes, 0, -1)]
    vizinhos.append(numero)
    vizinhos += [layout[(idx + i) % n] for i in range(1, depois+1)]
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
# IA Recorrência RF
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
            X.append([last2, last1] + nbrs)
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
            logging.error(f"Erro treinar RF: {e}")
            self.model = None

    def prever(self, historico):
        if not historico or len(historico) < 2:
            return []
        historico_lista = list(historico)
        ultimo_num = historico_lista[-1]["number"]
        self.treinar(historico_lista[-WINDOW_SIZE:])
        candidatos = []
        if self.model:
            numeros = [h["number"] for h in historico_lista]
            last2, last1 = numeros[-2], numeros[-1]
            feats = [last2, last1] + obter_vizinhos(last1, self.layout, antes=1, depois=1)
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                idx_top = np.argsort(probs)[-self.top_n:]
                candidatos = [int(classes[i]) for i in idx_top]
            except:
                candidatos = []
        # Adiciona vizinhos
        numeros_previstos = []
        for n in candidatos:
            for v in obter_vizinhos(n, self.layout, antes=2, depois=2):
                if v not in numeros_previstos:
                    numeros_previstos.append(v)
        return numeros_previstos[:MAX_PREVIEWS]

# =============================
# Top N Dinâmico
# =============================
if "topn_history" not in st.session_state:
    st.session_state.topn_history = deque(maxlen=TOP_N_WINDOW)
if "topn_reds" not in st.session_state:
    st.session_state.topn_reds = {}
if "topn_greens" not in st.session_state:
    st.session_state.topn_greens = {}

def atualizar_cooldown_reds():
    novos_reds = {}
    for num, rodadas in st.session_state.topn_reds.items():
        if rodadas > 1:
            novos_reds[num] = rodadas - 1
    st.session_state.topn_reds = novos_reds

def calcular_prob_min_topN():
    historico = list(st.session_state.topn_history)
    if not historico:
        return TOP_N_PROB_BASE
    taxa_red = historico.count("R") / len(historico)
    prob_min = TOP_N_PROB_BASE + (taxa_red * (TOP_N_PROB_MAX - TOP_N_PROB_BASE))
    return min(max(prob_min, TOP_N_PROB_MIN), TOP_N_PROB_MAX)

def ajustar_top_n(previsoes, historico=None, min_n=MIN_TOP_N, max_n=MAX_TOP_N):
    if not previsoes:
        return previsoes[:min_n]
    atualizar_cooldown_reds()
    prob_min = calcular_prob_min_topN()
    filtrados = [num for num in previsoes if num not in st.session_state.topn_reds]
    pesos = {num: 1.0 + st.session_state.topn_greens.get(num, 0)*0.05 for num in filtrados}
    ordenados = sorted(pesos.keys(), key=lambda x: pesos[x], reverse=True)
    n = max(min_n, min(max_n, int(len(ordenados) * prob_min)+min_n))
    return ordenados[:n]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência + Top N")
st_autorefresh(interval=3000, key="refresh")

# Inicializa session_state
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()
if "ia_recorrencia" not in st.session_state:
    st.session_state.ia_recorrencia = IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5, window=WINDOW_SIZE)
for key, default in {
    "previsao_para_conferir": [],
    "previsao_topN_para_conferir": [],
    "aguardando_resultado": False,
    "aguardando_resultado_topN": False,
    "acertos": 0, "erros":0, "acertos_topN":0, "erros_topN":0,
    "contador_rodadas":0, "ultimo_timestamp":None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carrega histórico
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)
    st.session_state.ultimo_timestamp = n.get("timestamp")

# Captura número (API)
resultado = fetch_latest_result()
novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if st.session_state.ultimo_timestamp != resultado["timestamp"]:
        novo_sorteio = True

# Processa novo sorteio
if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    st.session_state.ultimo_timestamp = resultado["timestamp"]
    salvar_historico(list(st.session_state.estrategia.historico))
    
    numero_real = numero_dict["number"]

    # Conferência e envio de alertas
    if st.session_state.aguardando_resultado and st.session_state.previsao_para_conferir:
        numeros_prev = st.session_state.previsao_para_conferir
        numeros_com_viz = []
        for n in numeros_prev:
            numeros_com_viz.extend([v for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1) if v not in numeros_com_viz])
        resultado_hash = f"res_{'_'.join(map(str, numeros_prev))}_{numero_real}"
        if numero_real in numeros_com_viz:
            st.session_state.acertos += 1
            enviar_alerta_unico(f"🟢 GREEN! Número {numero_real} acertou na previsão anterior.", resultado_hash)
        else:
            st.session_state.erros += 1
            enviar_alerta_unico(f"🔴 RED! Número {numero_real} errou na previsão anterior.", resultado_hash)
        st.session_state.previsao_para_conferir = []
        st.session_state.aguardando_resultado = False

    # Conferência Top N
    if st.session_state.aguardando_resultado_topN and st.session_state.previsao_topN_para_conferir:
        topN_prev = st.session_state.previsao_topN_para_conferir
        topN_com_viz = []
        for n in topN_prev:
            topN_com_viz.extend([v for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1) if v not in topN_com_viz])
        resultado_topN_hash = f"topn_{'_'.join(map(str, topN_prev))}_{numero_real}"
        if numero_real in topN_com_viz:
            st.session_state.acertos_topN += 1
            st.session_state.topn_greens[numero_real] = st.session_state.topn_greens.get(numero_real,0)+1
            enviar_alerta_unico(f"🟢 GREEN Top N! Número {numero_real} acertou.", resultado_topN_hash, topN=True)
        else:
            st.session_state.erros_topN += 1
            st.session_state.topn_reds[numero_real] = TOP_N_COOLDOWN
            enviar_alerta_unico(f"🔴 RED Top N! Número {numero_real} errou.", resultado_topN_hash, topN=True)
        st.session_state.previsao_topN_para_conferir = []
        st.session_state.aguardando_resultado_topN = False

# Gera nova previsão
previsoes = st.session_state.ia_recorrencia.prever(list(st.session_state.estrategia.historico))
st.session_state.previsao_para_conferir = previsoes
st.session_state.aguardando_resultado = True
previsao_str = ", ".join(map(str, previsoes))
hash_alerta = f"prev_{'_'.join(map(str, previsoes))}_{st.session_state.ultimo_timestamp}"
enviar_alerta_unico(f"🎯 Previsão da rodada: {previsao_str}", hash_alerta)

# Top N
topN_prev = ajustar_top_n(previsoes)
st.session_state.previsao_topN_para_conferir = topN_prev
st.session_state.aguardando_resultado_topN = True
topN_str = ", ".join(map(str, topN_prev))
hash_alerta_topN = f"topn_{'_'.join(map(str, topN_prev))}_{st.session_state.ultimo_timestamp}"
enviar_alerta_unico(f"🔥 Top N Previsão: {topN_str}", hash_alerta_topN, topN=True)
st.session_state.topn_history.append("R")  # Por padrão marca como RED até conferência

# =============================
# Interface Streamlit
# =============================
st.subheader("📊 Histórico Últimos Números")
ultimos = [h["number"] for h in list(st.session_state.estrategia.historico)[-20:]]
st.write(ultimos)

st.subheader("🎯 Previsões IA Recorrência")
st.write(previsao_str)

st.subheader("🔥 Top N Previsões")
st.write(topN_str)

st.subheader("📈 Métricas de Acerto")
st.write(f"✅ GREEN: {st.session_state.acertos} | 🔴 RED: {st.session_state.erros}")
st.write(f"✅ GREEN Top N: {st.session_state.acertos_topN} | 🔴 RED Top N: {st.session_state.erros_topN}")

# Botão para limpar histórico
if st.button("🗑️ Limpar Histórico"):
    st.session_state.estrategia.historico.clear()
    salvar_historico([])
    st.success("✅ Histórico limpo com sucesso!")

# =============================
# Salva métricas
# =============================
metricas = {
    "acertos": st.session_state.acertos,
    "erros": st.session_state.erros,
    "acertos_topN": st.session_state.acertos_topN,
    "erros_topN": st.session_state.erros_topN,
    "timestamp": st.session_state.ultimo_timestamp
}
salvar_metricas(metricas)
            
