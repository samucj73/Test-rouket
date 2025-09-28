# Domina03.py (versão atualizada — histórico padronizado e correções)
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
import pandas as pd

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

WINDOW_SIZE = 18   # janela móvel para Top N dinâmico
MIN_TOP_N = 5      # mínimo de números na Top N
MAX_TOP_N = 10     # máximo de números na Top N
MAX_PREVIEWS = 15   # limite final de previsões para reduzir custo

# =============================
# Logging
# =============================
logging.basicConfig(level=logging.INFO)

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
    """
    Lê o arquivo de histórico e padroniza cada entrada para:
    {"id": <str>, "number": <int>, "timestamp": <str>}
    Aceita formatos antigos (lista de ints, ou dicts com keys diferentes).
    """
    if not os.path.exists(HISTORICO_PATH):
        return []
    try:
        with open(HISTORICO_PATH, "r") as f:
            raw = json.load(f)
    except Exception as e:
        logging.error(f"Erro lendo histórico: {e}")
        return []

    historico_padronizado = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            # tenta extrair id
            id_val = (item.get("id") or item.get("roundId") or item.get("timestamp") or f"manual_{i}")
            # tenta extrair número
            if "number" in item:
                number = item["number"]
            elif "numero" in item:
                number = item["numero"]
            elif "winningNumber" in item:
                number = item["winningNumber"]
            else:
                # busca primeiro int disponível
                number = None
                for v in item.values():
                    if isinstance(v, int):
                        number = v
                        break
            # tenta extrair timestamp
            timestamp = item.get("timestamp") or item.get("startedAt") or item.get("time") or id_val
            if number is None:
                continue
            historico_padronizado.append({"id": str(id_val), "number": int(number), "timestamp": str(timestamp)})
        else:
            # item é primitivo (ex: int) -> transforma
            try:
                n = int(item)
                historico_padronizado.append({"id": f"manual_{i}", "number": n, "timestamp": f"manual_{i}"})
            except Exception:
                continue
    return historico_padronizado

def salvar_historico(id_sorteio, numero_sorteado, timestamp=None):
    """
    Salva um registro padronizado {"id","number","timestamp"} apenas se id ainda não existir no arquivo.
    Evita gravação repetida por loops; permite mesmo número em sorteios distintos.
    """
    try:
        historico = []
        if os.path.exists(HISTORICO_PATH):
            try:
                with open(HISTORICO_PATH, "r") as f:
                    historico = json.load(f)
            except Exception:
                historico = []

        # padroniza em memória o conteúdo atual (para evitar misturas de formatos)
        normalized = []
        for i, it in enumerate(historico):
            if isinstance(it, dict):
                id_val = it.get("id") or it.get("roundId") or f"old_{i}"
                number = it.get("number") or it.get("numero") or it.get("winningNumber")
                timestamp_val = it.get("timestamp") or it.get("startedAt") or f"old_{i}"
                # se number ainda None, tenta achar um inteiro
                if number is None:
                    for v in it.values():
                        if isinstance(v, int):
                            number = v
                            break
                if number is None:
                    continue
                normalized.append({"id": str(id_val), "number": int(number), "timestamp": str(timestamp_val)})
            else:
                try:
                    n = int(it)
                    normalized.append({"id": f"old_{i}", "number": n, "timestamp": f"old_{i}"})
                except Exception:
                    continue

        # checa se ID já existe
        if any(entry.get("id") == str(id_sorteio) for entry in normalized):
            logging.debug(f"ID {id_sorteio} já registrado — ignorando gravação.")
            return

        ts = timestamp or f"captured_{id_sorteio}"
        normalized.append({"id": str(id_sorteio), "number": int(numero_sorteado), "timestamp": str(ts)})

        with open(HISTORICO_PATH, "w") as f:
            json.dump(normalized, f, indent=2)
        logging.info(f"Histórico salvo: id={id_sorteio}, number={numero_sorteado}")
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
    """
    Tenta extrair roundId/startedAt/number do JSON da API.
    Retorna dict com chaves: {'number', 'timestamp', 'roundId'} ou None.
    """
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=6)
        response.raise_for_status()
        data = response.json() or {}
        game_data = data.get("data", {}) or {}
        result = game_data.get("result", {}) or {}
        outcome = result.get("outcome", {}) or {}

        # extração robusta de number
        number = outcome.get("number")
        if number is None:
            number = outcome.get("winningNumber") or result.get("winningNumber") or data.get("winningNumber") or data.get("number")

        # timestamp/startedAt
        timestamp = game_data.get("startedAt") or game_data.get("time") or data.get("timestamp") or data.get("time")

        # round id
        round_id = game_data.get("roundId") or game_data.get("id") or result.get("roundId") or data.get("roundId")

        if number is None:
            logging.error("fetch_latest_result: número não encontrado na resposta da API")
            return None

        return {
            "number": int(number),
            "timestamp": timestamp or str(round_id) or "",
            "roundId": str(round_id) if round_id is not None else f"r_{timestamp}"
        }
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
        # numero_dict esperado: {"id","number","timestamp"} ou {"number","timestamp"}
        self.historico.append(numero_dict)

# =============================
# IA Recorrência com RandomForest
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
        X = []
        y = []
        for i in range(2, len(numeros)):
            last2 = numeros[i-2]
            last1 = numeros[i-1]
            nbrs = obter_vizinhos(last1, self.layout, antes=2, depois=2)
            feat = [last2, last1] + nbrs  # 2 + 4 = 6 features (pois obter_vizinhos com antes=2,depois=2 retorna 5 incl. número)
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

        if self.model is not None:
            numeros = [h["number"] for h in historico_lista]
            last2 = numeros[-2] if len(numeros) > 1 else 0
            last1 = numeros[-1]
            feats = [last2, last1] + obter_vizinhos(last1, self.layout, antes=1, depois=1)
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                idx_top = np.argsort(probs)[-self.top_n:]
                top_ml = [int(classes[i]) for i in idx_top]
                candidatos = list(set(candidatos + top_ml))
            except Exception as e:
                logging.error(f"Erro predict_proba RF: {e}")

        # Expandir para vizinhos físicos
        numeros_previstos = []
        for n in candidatos:
            vizs = obter_vizinhos(n, self.layout, antes=2, depois=2)
            for v in vizs:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        # Redução inteligente (metade)
        numeros_previstos = reduzir_metade_inteligente(numeros_previstos, historico)

        # Limita a quantidade final para MAX_PREVIEWS
        if len(numeros_previstos) > MAX_PREVIEWS:
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
# Ajuste Dinâmico Top N
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

# Carregar histórico existente (padronizado) e popular deque da estratégia
historico_pad = carregar_historico()
for n in historico_pad:
    # evita duplicar caso já exista: compara pelo id
    if (not st.session_state.estrategia.historico) or (st.session_state.estrategia.historico[-1].get("id") != n.get("id")):
        st.session_state.estrategia.adicionar_numero(n)

# -----------------------------
# Captura número (API)
# -----------------------------
resultado = fetch_latest_result()

# acesso seguro ao último timestamp (comparação por timestamp)
ultimo_ts = None
if st.session_state.estrategia.historico:
    ultimo_item = st.session_state.estrategia.historico[-1]
    if isinstance(ultimo_item, dict) and "timestamp" in ultimo_item:
        ultimo_ts = ultimo_item["timestamp"]
    elif isinstance(ultimo_item, dict) and "id" in ultimo_item:
        ultimo_ts = ultimo_item["id"]

# Nova rodada detectada
if resultado:
    # padroniza valores vindos da API
    round_id = resultado.get("roundId") or resultado.get("timestamp") or f"r_{resultado.get('timestamp')}"
    timestamp_api = resultado.get("timestamp") or round_id
    number_api = resultado.get("number")
    # se número inválido, ignora
    if number_api is None:
        logging.debug("Resultado retornado sem número válido; ignorando.")
        resultado = None

#if resultado and resultado.get("timestamp") != ultimo_ts and (st.session_state.estrategia.historico == [] or round_id != (st.session_state.estrategia.historico[-1].get("id"))):
    if resultado and resultado.get("timestamp") != ultimo_ts:
    if not st.session_state.estrategia.historico or round_id != st.session_state.estrategia.historico[-1].get("id"):
        # sua lógica aqui
    # padroniza o dict salvo em memória
    numero_dict = {"id": str(round_id), "number": int(number_api), "timestamp": str(timestamp_api)}
    st.session_state.estrategia.adicionar_numero(numero_dict)

    # salva no arquivo (evita duplicação por id)
    salvar_historico(round_id, number_api, timestamp=timestamp_api)

    # define numero_real para conferências mais abaixo
    numero_real = int(number_api)

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
    # Salvar métricas após cada rodada (inclui id/timestamp)
    # -----------------------------
    metrics = {
        "timestamp": timestamp_api,
        "roundId": round_id,
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
st.subheader("📜 Histórico (últimos 3 registros)")
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

# =============================
# Botões de Download
# =============================
st.subheader("⬇️ Download dos Arquivos")

# Histórico: JSON + CSV
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        historico_json = f.read()
    st.download_button(
        label="📜 Baixar Histórico (JSON)",
        data=historico_json,
        file_name="historico_deslocamento.json",
        mime="application/json"
    )
    try:
        df_hist = pd.DataFrame(json.loads(historico_json))
        csv_data = df_hist.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📜 Baixar Histórico (CSV)",
            data=csv_data,
            file_name="historico_deslocamento.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.warning(f"Não foi possível converter histórico para CSV: {e}")
else:
    st.info("Nenhum histórico de números encontrado ainda.")

# Métricas: JSON + CSV
if os.path.exists(METRICAS_PATH):
    with open(METRICAS_PATH, "r") as f:
        metricas_json = f.read()
    st.download_button(
        label="📊 Baixar Histórico de Métricas (JSON)",
        data=metricas_json,
        file_name="historico_metricas.json",
        mime="application/json"
    )
    try:
        df_metricas = pd.DataFrame(json.loads(metricas_json))
        csv_data = df_metricas.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📊 Baixar Histórico de Métricas (CSV)",
            data=csv_data,
            file_name="historico_metricas.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.warning(f"Não foi possível converter métricas para CSV: {e}")
else:
    st.info("Nenhuma métrica registrada ainda.")
