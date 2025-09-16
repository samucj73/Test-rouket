import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging

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
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18   # janela móvel para Top N dinâmico

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar Telegram TopN: {e}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            historico = json.load(f)
        return [h if isinstance(h, dict) else {"number": h, "timestamp": f"manual_{i}"} for i, h in enumerate(historico)]
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f, indent=2)

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        data = r.json()
        game = data.get("data", {})
        result = game.get("result", {})
        number = result.get("outcome", {}).get("number")
        timestamp = game.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro API: {e}")
        return None

def obter_vizinhos(numero, layout, antes=2, depois=2):
    idx = layout.index(numero)
    n = len(layout)
    return [layout[(idx - i) % n] for i in range(antes, 0, -1)] + [numero] + [layout[(idx + i) % n] for i in range(1, depois + 1)]

# =============================
# Estratégia de deslocamento
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA recorrência
# =============================
class IA_Recorrencia:
    def __init__(self, layout=None, top_n=3):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n

    def prever(self, historico):
        if not historico:
            return []
        lista = list(historico)
        ultimo = lista[-1]["number"] if isinstance(lista[-1], dict) else None
        if ultimo is None:
            return []
        antes, depois = [], []
        for i, h in enumerate(lista[:-1]):
            if isinstance(h, dict) and h.get("number") == ultimo:
                if i - 1 >= 0 and isinstance(lista[i-1], dict):
                    antes.append(lista[i-1]["number"])
                if i + 1 < len(lista) and isinstance(lista[i+1], dict):
                    depois.append(lista[i+1]["number"])
        if not antes and not depois:
            return []
        top_antes = [n for n, _ in Counter(antes).most_common(self.top_n)]
        top_depois = [n for n, _ in Counter(depois).most_common(self.top_n)]
        candidatos = list(set(top_antes + top_depois))
        previsoes = []
        for n in candidatos:
            for v in obter_vizinhos(n, self.layout, antes=1, depois=1):
                if v not in previsoes:
                    previsoes.append(v)
        return previsoes

# =============================
# Redução inteligente (metade)
# =============================
def reduzir_metade_inteligente(previsoes, historico):
    if not previsoes:
        return []
    ultimos = [h["number"] for h in historico[-WINDOW_SIZE:]] if historico else []
    contagem_total = Counter(ultimos)
    pontuacoes = {}
    for n in previsoes:
        freq = contagem_total.get(n, 0)                # frequência
        vizinhos = obter_vizinhos(n, ROULETTE_LAYOUT, 1, 1)
        redundancia = sum(1 for v in vizinhos if v in previsoes)
        topN_bonus = st.session_state.topn_greens.get(n, 0) if "topn_greens" in st.session_state else 0
        pontuacoes[n] = freq + topN_bonus - redundancia*0.5
    ordenados = sorted(pontuacoes.keys(), key=lambda x: pontuacoes[x], reverse=True)
    return ordenados[:max(1, len(ordenados)//2)]

# =============================
# Estratégia 31/34
# =============================
def estrategia_31_34(numero):
    if numero in [31, 34]:
        return obter_vizinhos(numero, ROULETTE_LAYOUT, antes=2, depois=2)
    return []

# =============================
# Ajuste dinâmico do Top N
# =============================
def ajustar_top_n(previsoes, historico):
    ultimos = [h["number"] for h in historico[-WINDOW_SIZE:]] if historico else []
    contagem = Counter(ultimos)
    candidatos = contagem.most_common(15)
    base = [num for num, _ in candidatos]
    filtrados = [n for n in base if n in previsoes]
    return filtrados[:max(5, len(filtrados))]

# =============================
# Inicialização do Streamlit
# =============================
st.set_page_config(page_title="IA Roleta", layout="wide")

if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()
if "ia_recorrencia" not in st.session_state:
    st.session_state.ia_recorrencia = IA_Recorrencia()
if "previsao" not in st.session_state:
    st.session_state.previsao = []
if "previsao_topN" not in st.session_state:
    st.session_state.previsao_topN = []
if "previsao_31_34" not in st.session_state:
    st.session_state.previsao_31_34 = []
if "contador_rodadas" not in st.session_state:
    st.session_state.contador_rodadas = 0
if "topn_greens" not in st.session_state:
    st.session_state.topn_greens = {}

# =============================
# Auto Refresh
# =============================
st_autorefresh(interval=5000, key="atualizar")

# =============================
# Busca novo número
# =============================
novo = fetch_latest_result()
if novo and (not st.session_state.estrategia.historico or novo["timestamp"] != st.session_state.estrategia.historico[-1]["timestamp"]):
    st.session_state.estrategia.adicionar_numero(novo)
    salvar_historico(list(st.session_state.estrategia.historico))
    numero_real = novo["number"]
    st.session_state.contador_rodadas += 1

    # =============================
    # IA Recorrência (rodadas pares)
    # =============================
    if st.session_state.contador_rodadas % 2 == 0:
        previsoes = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if previsoes:
            # aplica redução inteligente
            previsoes = reduzir_metade_inteligente(previsoes, st.session_state.estrategia.historico)
            st.session_state.previsao = previsoes

            # gera Top N
            topN = ajustar_top_n(previsoes, st.session_state.estrategia.historico)
            st.session_state.previsao_topN = topN

            # envia alertas
            enviar_telegram("🎯 NP: " + " ".join(str(n) for n in sorted(previsoes)))
            enviar_telegram_topN("📊 Top N: " + " ".join(str(n) for n in sorted(topN)))

    # =============================
    # Estratégia 31/34 (rodadas ímpares)
    # =============================
    else:
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34
            enviar_telegram("🎯 Estrat 31/34: " + " ".join(str(n) for n in entrada_31_34))

    # =============================
    # Conferência GREEN/RED
    # =============================
    if st.session_state.previsao:
        if numero_real in st.session_state.previsao:
            enviar_telegram("🟢 GREEN IA Recorrência")
        else:
            enviar_telegram("🔴 RED IA Recorrência")

    if st.session_state.previsao_topN:
        if numero_real in st.session_state.previsao_topN:
            enviar_telegram_topN("🟢 GREEN Top N")
            st.session_state.topn_greens[numero_real] = st.session_state.topn_greens.get(numero_real, 0) + 1
        else:
            enviar_telegram_topN("🔴 RED Top N")

    if st.session_state.previsao_31_34:
        if numero_real in st.session_state.previsao_31_34:
            enviar_telegram("🟢 GREEN Estrat 31/34")
        else:
            enviar_telegram("🔴 RED Estrat 31/34")

# =============================
# Exibição no Streamlit
# =============================
st.title("🎰 IA de Roleta - Recorrência + Top N + 31/34")
st.subheader("Últimos números")
st.write([h["number"] for h in list(st.session_state.estrategia.historico)[-10:]])

st.subheader("📊 Última previsão IA Recorrência (reduzida)")
st.write(st.session_state.previsao)

st.subheader("📊 Última previsão Top N")
st.write(st.session_state.previsao_topN)

st.subheader("📊 Última previsão Estrat 31/34")
st.write(st.session_state.previsao_31_34)
