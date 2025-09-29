# Domina03.py (corrigido - problema de duplicação no histórico)
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

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram Top N: {e}")

def carregar_historico():
    """Carrega histórico garantindo que não haja duplicatas"""
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            
            # Remove duplicatas baseado no timestamp
            historico_sem_duplicatas = []
            timestamps_vistos = set()
            
            for h in historico:
                if isinstance(h, dict) and "timestamp" in h:
                    if h["timestamp"] not in timestamps_vistos:
                        timestamps_vistos.add(h["timestamp"])
                        historico_sem_duplicatas.append(h)
                else:
                    # Para registros antigos sem timestamp
                    historico_sem_duplicatas.append(h)
            
            logging.info(f"Histórico carregado: {len(historico_sem_duplicatas)} registros únicos")
            return historico_sem_duplicatas
        except Exception as e:
            logging.error(f"Erro ao carregar histórico: {e}")
            return []
    return []

def salvar_historico(historico):
    """Salva histórico garantindo que não haja duplicatas"""
    try:
        # Remove duplicatas antes de salvar
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
        
        logging.info(f"Histórico salvo: {len(historico_sem_duplicatas)} registros únicos")
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
            logging.info(f"API retornou: número {number}, timestamp {timestamp}")
            return {"number": number, "timestamp": timestamp}
        else:
            logging.warning("API retornou dados incompletos")
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
        """Adiciona número apenas se não for duplicado"""
        if not numero_dict or "timestamp" not in numero_dict:
            return
            
        # Verifica se já existe no histórico
        for existing in self.historico:
            if (isinstance(existing, dict) and 
                existing.get("timestamp") == numero_dict.get("timestamp")):
                logging.info(f"Sorteio duplicado ignorado: {numero_dict}")
                return
        
        self.historico.append(numero_dict)
        logging.info(f"Novo sorteio adicionado: {numero_dict}")

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

        numeros_previstos = []
        for n in candidatos:
            vizs = obter_vizinhos(n, self.layout, antes=2, depois=2)
            for v in vizs:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        numeros_previstos = reduzir_metade_inteligente(numeros_previstos, historico)

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
# Redução inteligente
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
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência (RandomForest) + Redução Inteligente")
st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
# Inicialização session_state

# Inicialização session_state
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5, window=WINDOW_SIZE),
    "previsao_anterior": [],  # Previsões para conferir no próximo sorteio
    "previsao_topN_anterior": [],  # Previsões TopN para conferir no próximo sorteio
    "acertos": 0,
    "erros": 0,
    "acertos_topN": 0,
    "erros_topN": 0,
    "contador_rodadas": 0,
    "topn_history": deque(maxlen=TOP_N_WINDOW),
    "topn_reds": {},
    "topn_greens": {},
    "ultimo_timestamp": None,  # CRÍTICO: controla duplicatas
    "ultimo_alerta_numero": None,  # NOVO: último número que gerou alerta
    "ultimo_alerta_topN_numero": None,  # NOVO: último número que gerou alerta TopN
    "ultima_previsao_hash": None,  # NOVO: hash da última previsão enviada
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    if not st.session_state.estrategia.historico or st.session_state.estrategia.historico[-1].get("timestamp") != n.get("timestamp"):
        st.session_state.estrategia.adicionar_numero(n)
        st.session_state.ultimo_timestamp = n.get("timestamp")

# -----------------------------
# Captura número (API) - CORREÇÃO PRINCIPAL
# -----------------------------
# Captura número (API) - CORREÇÃO PRINCIPAL
# -----------------------------
resultado = fetch_latest_result()

# VERIFICAÇÃO ROBUSTA CONTRA DUPLICATAS
novo_sorteio = False
if resultado and resultado.get("timestamp"):
    # Se é o primeiro sorteio OU se o timestamp é DIFERENTE do último
    if st.session_state.ultimo_timestamp is None:
        novo_sorteio = True
        logging.info("🎲 PRIMEIRO SORTEIO DETECTADO")
    elif resultado["timestamp"] != st.session_state.ultimo_timestamp:
        novo_sorteio = True
        logging.info(f"🎲 NOVO SORTEIO: {resultado['number']} (anterior: {st.session_state.ultimo_timestamp})")
    else:
        logging.info(f"⏳ Sorteio duplicado ignorado: {resultado['timestamp']}")

# Processa APENAS se for realmente um novo sorteio
if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    # ATUALIZA imediatamente o último timestamp
    st.session_state.ultimo_timestamp = resultado["timestamp"]
    
    # Adiciona ao histórico
    st.session_state.estrategia.adicionar_numero(numero_dict)
    
    # Salva histórico (já com remoção de duplicatas)
    salvar_historico(list(st.session_state.estrategia.historico))
    
    numero_real = numero_dict["number"]

    # -----------------------------
    # CONFERÊNCIA com previsões ANTERIORES (do último sorteio)
    # -----------------------------
    # Conferência Recorrência (previsão do sorteio anterior)
    if st.session_state.previsao_anterior:
        numeros_com_vizinhos = []
        for n in st.session_state.previsao_anterior:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
                if v not in numeros_com_vizinhos:
                    numeros_com_vizinhos.append(v)
        
        if numero_real in numeros_com_vizinhos:
            st.session_state.acertos += 1
            st.success(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
            # Envia alerta APENAS se for um GREEN e se ainda não foi enviado para este número
            if st.session_state.ultimo_alerta_numero != numero_real:
                enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
                st.session_state.ultimo_alerta_numero = numero_real
        else:
            st.session_state.erros += 1
            st.error(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
        # Limpa a previsão anterior após conferir
        st.session_state.previsao_anterior = []

    # Conferência TopN (previsão do sorteio anterior)
    if st.session_state.previsao_topN_anterior:
        topN_com_vizinhos = []
        for n in st.session_state.previsao_topN_anterior:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
                if v not in topN_com_vizinhos:
                    topN_com_vizinhos.append(v)
        
        if numero_real in topN_com_vizinhos:
            st.session_state.acertos_topN += 1
            st.success(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
            # Envia alerta APENAS se for um GREEN e se ainda não foi enviado para este número
            if st.session_state.ultimo_alerta_topN_numero != numero_real:
                enviar_telegram_topN(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
                st.session_state.ultimo_alerta_topN_numero = numero_real
            st.session_state.topn_greens[numero_real] = st.session_state.topn_greens.get(numero_real, 0) + 1
        else:
            st.session_state.erros_topN += 1
            st.error(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
        # Limpa a previsão anterior após conferir
        st.session_state.previsao_topN_anterior = []

    # -----------------------------
    # GERAR NOVAS PREVISÕES para o PRÓXIMO sorteio
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            prox_numeros = list(dict.fromkeys(prox_numeros))
            
            # Salva como previsões ANTERIORES para conferir no próximo sorteio
            st.session_state.previsao_anterior = prox_numeros

            entrada_topN = ajustar_top_n(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao_topN_anterior = entrada_topN

            # Envia previsões APENAS UMA VEZ por ciclo de previsão
            # Verifica se já não foram enviadas para este conjunto de números
            previsao_hash = hash(tuple(sorted(prox_numeros)))
            if st.session_state.ultima_previsao_hash != previsao_hash:
                s = sorted(prox_numeros)
                mensagem_previsao = "🎯 NP: " + " ".join(map(str, s[:5]))
                if len(s) > 5:
                    mensagem_previsao += "\n" + " ".join(map(str, s[5:]))
                
                enviar_telegram(mensagem_previsao)
                
                # Envia apenas UMA mensagem para o canal Top N
                if entrada_topN:
                    enviar_telegram_topN("Top N: " + " ".join(map(str, sorted(entrada_topN))))
                
                # MARCA que estas previsões já foram enviadas
                st.session_state.ultima_previsao_hash = previsao_hash

    st.session_state.contador_rodadas += 1

    metrics = {
        "timestamp": resultado.get("timestamp"),
        "numero_real": numero_real,
        "acertos": st.session_state.get("acertos", 0),
        "erros": st.session_state.get("erros", 0),
        "acertos_topN": st.session_state.get("acertos_topN", 0),
        "erros_topN": st.session_state.get("erros_topN", 0),
    }
    salvar_metricas(metrics)




# Status do último sorteio
if st.session_state.ultimo_timestamp:
    st.info(f"⏳ Último sorteio processado: {st.session_state.ultimo_timestamp}")
else:
    st.info("⏳ Aguardando primeiro sorteio...")

# -----------------------------
# Interface
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
ultimos = list(st.session_state.estrategia.historico)[-3:]
st.write(ultimos)

# Estatísticas (mantido igual)
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

st.subheader("📊 Informações do Histórico")
st.write(f"Total de números armazenados no histórico: **{len(st.session_state.estrategia.historico)}**")
st.write(f"Capacidade máxima do deque: **{st.session_state.estrategia.historico.maxlen}**")
