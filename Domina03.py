# Domina03.py (arquivo completo atualizado)
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
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# Canal alternativo para Top N Dinâmico
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 250   # janela móvel para Top N dinâmico
MIN_TOP_N = 5      # mínimo de números na Top N
MAX_TOP_N = 10     # máximo de números na Top N
MAX_PREVIEWS = 6   # limite final de previsões para reduzir custo

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

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram Top N: {e}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
        except Exception:
            return []
        historico_padronizado = []
        for i, h in enumerate(historico):
            if isinstance(h, dict) and "number" in h:
                historico_padronizado.append(h)
            else:
                historico_padronizado.append({"number": h, "timestamp": f"manual_{i}"})
        return historico_padronizado
    return []

def salvar_historico(historico):
    try:
        with open(HISTORICO_PATH, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def salvar_metricas(m):
    try:
        # salva lista de métricas (apenda)
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
        return {"number": number, "timestamp": timestamp}
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

def obter_vizinhos_fixos(numero, layout, antes=5, depois=5):
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
        self.historico.append(numero_dict)

# =============================
# IA Recorrência com RandomForest
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=5, window=WINDOW_SIZE):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.window = window
        self.model = None

    def _criar_features_simples(self, historico: List[dict]):
        """
        Features simples:
        - último número (categorical -> numeric as index)
        - penúltimo número
        - vizinhos do último (1 antes, 1 depois)
        Output X (n_samples x n_features), y (n_samples,)
        """
        numeros = [h["number"] for h in historico]
        if len(numeros) < 3:
            return None, None
        X = []
        y = []
        for i in range(2, len(numeros)):
            last2 = numeros[i-2]
            last1 = numeros[i-1]
            nbrs = obter_vizinhos(last1, self.layout, antes=1, depois=1)
            feat = [last2, last1] + nbrs  # 2 + 3 = 5 features
            X.append(feat)
            y.append(numeros[i])
        return np.array(X), np.array(y)

    def treinar(self, historico):
        X, y = self._criar_features_simples(historico)
        if X is None or len(X) == 0:
            self.model = None
            return
        try:
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.model.fit(X, y)
        except Exception as e:
            logging.error(f"Erro treinando RF: {e}")
            self.model = None

    def prever(self, historico):
        """
        Combina:
         - estatística antes/depois (como já existia)
         - predição do RandomForest (probabilidades)
        Depois expande para vizinhos e aplica redução inteligente + limite (MAX_PREVIEWS)
        """
        if not historico or len(historico) < 2:
            return []

        # estatística antes/depois (seu método original)
        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"] if isinstance(historico_lista[-1], dict) else None
        if ultimo_numero is None:
            return []

        antes, depois = [], []
        for i, h in enumerate(historico_lista[:-1]):
            if isinstance(h, dict) and h.get("number") == ultimo_numero:
                if i - 1 >= 0 and isinstance(historico_lista[i-1], dict):
                    antes.append(historico_lista[i-1]["number"])
                if i + 1 < len(historico_lista) and isinstance(historico_lista[i+1], dict):
                    depois.append(historico_lista[i+1]["number"])

        cont_antes = Counter(antes)
        cont_depois = Counter(depois)
        top_antes = [num for num, _ in cont_antes.most_common(self.top_n)]
        top_depois = [num for num, _ in cont_depois.most_common(self.top_n)]
        candidatos = list(set(top_antes + top_depois))

        # Treina o RF usando todo o histórico recente (janela)
        window_hist = historico_lista[-max(len(historico_lista), self.window):]
        self.treinar(window_hist)

        # Se tivermos modelo, pegamos top classes por probabilidade
        if self.model is not None:
            # build features for current last
            numeros = [h["number"] for h in historico_lista]
            last2 = numeros[-2] if len(numeros) > 1 else 0
            last1 = numeros[-1]
            feats = [last2, last1] + obter_vizinhos(last1, self.layout, antes=1, depois=1)
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                # pega top_n com maiores probabilidades
                idx_top = np.argsort(probs)[-self.top_n:]
                top_ml = [int(classes[i]) for i in idx_top]
                candidatos = list(set(candidatos + top_ml))
            except Exception as e:
                logging.error(f"Erro predict_proba RF: {e}")

        # Expandir para vizinhos físicos
        numeros_previstos = []
        for n in candidatos:
            vizs = obter_vizinhos(n, self.layout, antes=1, depois=1)
            for v in vizs:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        # Redução inteligente (metade), pontuando por frequência + topn_greens + penaliza redundância
        numeros_previstos = reduzir_metade_inteligente(numeros_previstos, historico)

        # Limita a quantidade final para MAX_PREVIEWS (escolhe os mais pontuados)
        if len(numeros_previstos) > MAX_PREVIEWS:
            # recalcula pontuações rápidas
            ultimos = [h["number"] for h in list(historico)[-WINDOW_SIZE:]] if historico else []
            freq = Counter(ultimos)
            topn_greens = st.session_state.get("topn_greens", {})
            scores = {}
            for n in numeros_previstos:
                scores[n] = freq.get(n, 0) + 0.8 * topn_greens.get(n, 0)
            numeros_previstos = sorted(numeros_previstos, key=lambda x: scores.get(x, 0), reverse=True)[:MAX_PREVIEWS]

        return numeros_previstos

# =============================
# Redução inteligente (metade) - função reutilizável
# =============================
def reduzir_metade_inteligente(previsoes, historico):
    if not previsoes:
        return []
    ultimos_numeros = [h["number"] for h in list(historico)[-WINDOW_SIZE:]] if historico else []
    contagem_total = Counter(ultimos_numeros)
    topn_greens = st.session_state.get("topn_greens", {})
    pontuacoes = {}
    for n in previsoes:
        freq = contagem_total.get(n, 0)
        vizinhos = obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1)
        redundancia = sum(1 for v in vizinhos if v in previsoes)
        bonus = topn_greens.get(n, 0)
        pontuacoes[n] = freq + (bonus * 0.8) - (0.5 * redundancia)
    ordenados = sorted(pontuacoes.keys(), key=lambda x: pontuacoes[x], reverse=True)
    n_reduzidos = max(1, len(ordenados) // 2)
    return ordenados[:n_reduzidos]

# =============================
# Ajuste Dinâmico Top N (mantive a sua lógica)
# =============================
TOP_N_COOLDOWN = 3
TOP_N_PROB_BASE = 0.3
TOP_N_PROB_MAX = 0.5
TOP_N_PROB_MIN = 0.2
TOP_N_WINDOW = 12

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
    return ordenados[:n]

def registrar_resultado_topN(numero_real, top_n):
    for num in top_n:
        if num == numero_real:
            st.session_state.topn_greens[num] = st.session_state.topn_greens.get(num, 0) + 1
            st.session_state.topn_history.append("G")
        else:
            st.session_state.topn_reds[num] = TOP_N_COOLDOWN
            st.session_state.topn_history.append("R")

# =============================
# Estratégia 31/34 (mantive sua lógica)
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
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência (RandomForest) + Redução Inteligente")
st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state (todas as chaves necessárias)
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5, window=WINDOW_SIZE),
    "previsao": [],
    "previsao_topN": [],
    "previsao_31_34": [],
    "acertos": 0,
    "erros": 0,
    "acertos_topN": 0,
    "erros_topN": 0,
    "acertos_31_34": 0,
    "erros_31_34": 0,
    "contador_rodadas": 0,
    "topn_history": deque(maxlen=TOP_N_WINDOW),
    "topn_reds": {},
    "topn_greens": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    # evita duplicar caso já exista
    if not st.session_state.estrategia.historico or st.session_state.estrategia.historico[-1].get("timestamp") != n.get("timestamp"):
        st.session_state.estrategia.adicionar_numero(n)

# -----------------------------
# -----------------------------
# Captura número (API)
# -----------------------------
resultado = fetch_latest_result()

# acesso seguro ao último timestamp
ultimo_ts = None
if st.session_state.estrategia.historico:
    ultimo_item = st.session_state.estrategia.historico[-1]
    if isinstance(ultimo_item, dict) and "timestamp" in ultimo_item:
        ultimo_ts = ultimo_item["timestamp"]

# Nova rodada detectada
if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    numero_real = numero_dict["number"]

    # -----------------------------
    # Conferência Recorrência
    # -----------------------------
    if st.session_state.previsao:
        numeros_com_vizinhos = []
        for n in st.session_state.previsao:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
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

    # -----------------------------
    # Conferência TopN
    # -----------------------------
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
            st.session_state.topn_greens[numero_real] = st.session_state.topn_greens.get(numero_real, 0) + 1
        else:
            st.session_state.erros_topN += 1
            st.error(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
            enviar_telegram_topN(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
        st.session_state.previsao_topN = []

    # -----------------------------
    # Conferência 31/34
    # -----------------------------
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
    # Gerar próxima previsão
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0:
        # Usa IA Recorrência RandomForest
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            prox_numeros = list(dict.fromkeys(prox_numeros))  # garante unicidade
            st.session_state.previsao = prox_numeros

            entrada_topN = ajustar_top_n(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao_topN = entrada_topN

            # Envio Telegram
            s = sorted(prox_numeros)
            enviar_telegram("🎯 NP: " + " ".join(map(str, s[:5])) +
                            ("\n" + " ".join(map(str, s[5:])) if len(s) > 5 else ""))
            enviar_telegram_topN("Top N: " + " ".join(map(str, sorted(entrada_topN))))
    else:
        # Estratégia 31/34
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34

    # -----------------------------
    # Incrementa contador de rodadas
    # -----------------------------
    st.session_state.contador_rodadas += 1

    # -----------------------------
    # Salvar métricas após cada rodada
    # -----------------------------
    metrics = {
        "timestamp": resultado.get("timestamp"),
        "numero_real": numero_real,
        "acertos": st.session_state.get("acertos", 0),
        "erros": st.session_state.get("erros", 0),
        "acertos_topN": st.session_state.get("acertos_topN", 0),
        "erros_topN": st.session_state.get("erros_topN", 0),
        "acertos_31_34": st.session_state.get("acertos_31_34", 0),
        "erros_31_34": st.session_state.get("erros_31_34", 0)
    }
    salvar_metricas(metrics)


# -----------------------------
# Histórico e métricas (exibição)
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
ultimos = list(st.session_state.estrategia.historico)[-3:]
st.write(ultimos)

# Estatísticas Recorrência
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0
qtd_previstos_rec = len(st.session_state.get("previsao", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN", acertos)
col2.metric("🔴 RED", erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")
col4.metric("🎯 Qtd. previstos Recorrência", qtd_previstos_rec)

# Estatísticas Top N Dinâmico
acertos_topN = st.session_state.get("acertos_topN", 0)
erros_topN = st.session_state.get("erros_topN", 0)
total_topN = acertos_topN + erros_topN
taxa_topN = (acertos_topN / total_topN * 100) if total_topN > 0 else 0.0
qtd_previstos_topN = len(st.session_state.get("previsao_topN", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN Top N", acertos_topN)
col2.metric("🔴 RED Top N", erros_topN)
col3.metric("✅ Taxa Top N", f"{taxa_topN:.1f}%")
col4.metric("🎯 Qtd. previstos Top N", qtd_previstos_topN)

# Estatísticas 31/34
acertos_31_34 = st.session_state.get("acertos_31_34", 0)
erros_31_34 = st.session_state.get("erros_31_34", 0)
total_31_34 = acertos_31_34 + erros_31_34
taxa_31_34 = (acertos_31_34 / total_31_34 * 100) if total_31_34 > 0 else 0.0
qtd_previstos_31_34 = len(st.session_state.get("previsao_31_34", []))

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN 31/34", acertos_31_34)
col2.metric("🔴 RED 31/34", erros_31_34)
col3.metric("✅ Taxa 31/34", f"{taxa_31_34:.1f}%")
col4.metric("🎯 Qtd. previstos 31/34", qtd_previstos_31_34)
# -----------------------------
# Exibir tamanho do histórico
# -----------------------------
st.subheader("📊 Informações do Histórico")
st.write(f"Total de números armazenados no histórico: **{len(st.session_state.estrategia.historico)}**")
st.write(f"Capacidade máxima do deque: **{st.session_state.estrategia.historico.maxlen}**")
