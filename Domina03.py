import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
from sklearn.ensemble import RandomForestClassifier
import numpy as np

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Canal principal
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# Canal alternativo para Top N Dinâmico
ALT_TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18   # janela móvel para Top N dinâmico
MIN_TOP_N = 5      # mínimo de números na Top N
MAX_TOP_N = 15     # máximo de números na Top N

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar para Telegram: {e}")

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar para Telegram Top N: {e}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            historico = json.load(f)
        historico_padronizado = []
        for h in historico:
            if isinstance(h, dict):
                historico_padronizado.append(h)
            else:
                historico_padronizado.append({"number": h, "timestamp": f"manual_{len(historico_padronizado)}"})
        return historico_padronizado
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f, indent=2)

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def obter_vizinhos(numero, layout, antes=2, depois=2):
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

def obter_vizinhos_fixos(numero, layout, antes=5, depois=5):
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
        self.historico = deque(maxlen=1000)
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA recorrência aprimorada
# =============================
class IA_Recorrencia_Aprimorada:
    def __init__(self, layout=None, top_n=5):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.model = None

    def criar_features(self, historico):
        if len(historico) < 3:
            return None, None
        numeros = [h["number"] if isinstance(h, dict) else h for h in historico]
        X, y = [], []
        for i in range(2, len(numeros)):
            features = []
            # últimos dois números
            features += [numeros[i-2], numeros[i-1]]
            # frequência do último
            features.append(numeros[i-1])
            # vizinhos físicos
            features += obter_vizinhos(numeros[i-1], self.layout, antes=1, depois=1)
            X.append(features)
            y.append(numeros[i])
        return np.array(X), np.array(y)

    def treinar_modelo(self, historico):
        X, y = self.criar_features(historico)
        if X is None or len(X) == 0:
            return
        self.model = RandomForestClassifier(n_estimators=100)
        self.model.fit(X, y)

    def prever(self, historico):
        if not historico:
            return []

        self.treinar_modelo(historico)

        numeros = [h["number"] if isinstance(h, dict) else h for h in historico]
        ultimo_num = numeros[-1]

        # frequência antes/depois
        antes, depois = [], []
        for i, n in enumerate(numeros[:-1]):
            if n == ultimo_num:
                if i-1 >=0: antes.append(numeros[i-1])
                if i+1 < len(numeros): depois.append(numeros[i+1])
        cont_antes = Counter(antes)
        cont_depois = Counter(depois)
        top_antes = [num for num,_ in cont_antes.most_common(self.top_n)]
        top_depois = [num for num,_ in cont_depois.most_common(self.top_n)]

        candidatos = list(set(top_antes + top_depois))

        # previsão via ML
        if self.model:
            features = [numeros[-2] if len(numeros)>1 else 0, numeros[-1]]
            features += [numeros[-1]]
            features += obter_vizinhos(numeros[-1], self.layout, antes=1, depois=1)
            pred_proba = self.model.predict_proba([features])
            classes = self.model.classes_
            probs = pred_proba[0]
            top_ml = [classes[i] for i in np.argsort(probs)[-self.top_n:]]
            candidatos = list(set(candidatos + top_ml))

        # expande vizinhos físicos
        numeros_previstos = []
        for n in candidatos:
            vizinhos = obter_vizinhos(n, self.layout, antes=1, depois=1)
            for v in vizinhos:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        return numeros_previstos

# =============================
# Ajuste Dinâmico Top N
# =============================
TOP_N_COOLDOWN = 2
TOP_N_PROB_BASE = 0.3
TOP_N_PROB_MAX = 0.5
TOP_N_PROB_MIN = 0.2
TOP_N_WINDOW = 18

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

    pesos = {}
    for num in filtrados:
        pesos[num] = 1.0 + st.session_state.topn_greens.get(num, 0) * 0.05

    ordenados = sorted(pesos.keys(), key=lambda x: pesos[x], reverse=True)

    n = max(min_n, min(max_n, int(len(ordenados) * prob_min) + min_n))
    top_n_final = ordenados[:n]

    return top_n_final

def registrar_resultado_topN(numero_real, top_n):
    for num in top_n:
        if num == numero_real:
            st.session_state.topn_greens[num] = st.session_state.topn_greens.get(num, 0) + 1
            st.session_state.topn_history.append("G")
        else:
            st.session_state.topn_reds[num] = TOP_N_COOLDOWN
            st.session_state.topn_history.append("R")

# =============================
# Estratégia 31/34
# =============================
def estrategia_31_34(numero_capturado):
    if numero_capturado is None:
        return None
    try:
        terminal = int(str(numero_capturado)[-1])
    except Exception:
        return None
    if terminal not in {2, 6, 9}:
        return None

    viz_31 = obter_vizinhos_fixos(31, ROULETTE_LAYOUT, antes=5, depois=5)
    viz_34 = obter_vizinhos_fixos(34, ROULETTE_LAYOUT, antes=5, depois=5)
    entrada = set([0, 26, 30] + viz_31 + viz_34)

    msg = (
        "🎯 Estratégia 31/34 disparada!\n"
        f"Número capturado: {numero_capturado} (terminal {terminal})\n"
        "Entrar nos números: 31 34"
    )
    enviar_telegram(msg)
    return list(entrada)

# =============================
# Inicialização do Streamlit
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA de Recorrência Aprimorada")
st_autorefresh(interval=3000, key="refresh")

# Inicializa session_state
for key, default in {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia_Aprimorada(layout=ROULETTE_LAYOUT, top_n=5),
    "previsao": [],
    "previsao_topN": [],
    "previsao_31_34": [],
    "recorrencia_acertos": 0,
    "recorrencia_erros": 0,
    "acertos_topN": 0,
    "erros_topN": 0,
    "acertos_31_34": 0,
    "erros_31_34": 0,
    "contador_rodadas": 0,
    "topn_history": deque(maxlen=WINDOW_SIZE),
    "topn_reds": {},
    "topn_greens": {}
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)

# Aqui você continuaria com a captura do número, conferência e atualização de métricas
# usando os atributos inicializados corretame

# =============================

# -----------------------------
# Captura número
# -----------------------------
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    numero_real = numero_dict["number"]

    # -----------------------------
    # Conferência (primeiro)
    # -----------------------------
    if st.session_state.previsao:
        numeros_com_vizinhos = []
        for n in st.session_state.previsao:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=2, depois=2):
                if v not in numeros_com_vizinhos:
                    numeros_com_vizinhos.append(v)
        if numero_real in numeros_com_vizinhos:
            st.session_state.acertos += 1
            st.success(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
            enviar_telegram(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
        st.session_state.previsao = []

    if st.session_state.previsao_topN:
        topN_com_vizinhos = []
        for n in st.session_state.previsao_topN:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
                if v not in topN_com_vizinhos:
                    topN_com_vizinhos.append(v)
        if numero_real in topN_com_vizinhos:
            st.session_state.acertos_topN += 1
            st.success(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
            enviar_telegram_topN(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
        else:
            st.session_state.erros_topN += 1
            st.error(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
            enviar_telegram_topN(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
        st.session_state.previsao_topN = []

    if st.session_state.previsao_31_34:
        if numero_real in st.session_state.previsao_31_34:
            st.session_state.acertos_31_34 += 1
            st.success(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
            enviar_telegram(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
        else:
            st.session_state.erros_31_34 += 1
            st.error(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
            enviar_telegram(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
        st.session_state.previsao_31_34 = []

    # -----------------------------
    # Previsão (depois)
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros
            entrada_topN = ajustar_top_n(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao_topN = entrada_topN
            enviar_telegram("🎯 NP: " + " ".join(str(n) for n in sorted(prox_numeros)))
            enviar_telegram_topN("Top N : " + " ".join(str(n) for n in sorted(entrada_topN)))
    else:
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34

    st.session_state.contador_rodadas += 1

# -----------------------------
# Histórico e métricas
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
st.write(list(st.session_state.estrategia.historico)[-3:])

# Estatísticas Recorrência
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0

# =============================
# 📊 Métricas no Streamlit
# =============================
# =============================
# 📊 Métricas no Streamlit
# =============================

st.subheader("📊 Métricas de desempenho")

# IA Recorrência
total_rec = st.session_state.recorrencia_acertos + st.session_state.recorrencia_erros
taxa_rec = (st.session_state.recorrencia_acertos / total_rec * 100) if total_rec > 0 else 0

st.write("### IA Recorrência")
st.write(f"🟢 GREEN: {st.session_state.recorrencia_acertos}")
st.write(f"🔴 RED: {st.session_state.recorrencia_erros}")
st.write(f"✅ Taxa de acerto: {taxa_rec:.1f}%")

# Top N
total_topn = st.session_state.topn_acertos + st.session_state.topn_erros
taxa_topn = (st.session_state.topn_acertos / total_topn * 100) if total_topn > 0 else 0

st.write("### Top N")
st.write(f"🟢 GREEN: {st.session_state.topn_acertos}")
st.write(f"🔴 RED: {st.session_state.topn_erros}")
st.write(f"✅ Taxa de acerto: {taxa_topn:.1f}%")

# Estratégia 31/34
total_3134 = st.session_state.estrat_acertos + st.session_state.estrat_erros
taxa_3134 = (st.session_state.estrat_acertos / total_3134 * 100) if total_3134 > 0 else 0

st.write("### Estratégia 31/34")
st.write(f"🟢 GREEN: {st.session_state.estrat_acertos}")
st.write(f"🔴 RED: {st.session_state.estrat_erros}")
st.write(f"✅ Taxa de acerto: {taxa_3134:.1f}%")

# Histórico dos últimos 10
st.subheader("📜 Histórico (últimos 10 números)")
st.write([h["number"] for h in list(st.session_state.estrategia.historico)[-10:]])

