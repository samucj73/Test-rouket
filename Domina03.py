import streamlit as st
import json
import os
import requests
from collections import deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import logging

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

MIN_HIST = 21  # mínimo de rodadas para começar a prever
TOP_N = 10      # quantidade de números previstos
TAMANHO_JANELA = 100  # janela histórica para cálculo de ausentesy

# =============================
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

# =============================
# Estratégia Ausentes Inteligente
# =============================
class EstrategiaAusentes:
    def __init__(self, tamanho_janela=TAMANHO_JANELA):
        self.historico = deque(maxlen=1000)
        self.tamanho_janela = tamanho_janela

    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

    def prever(self, qtd=TOP_N):
        if len(self.historico) < MIN_HIST:
            return []

        # Janela: penúltimo até trás
        janela = list(self.historico)[:-1]
        if self.tamanho_janela:
            janela = janela[-self.tamanho_janela:]

        # calcular frequência na janela
        freq = defaultdict(int)
        numeros_na_janela = set()
        for h in janela:
            numeros_na_janela.add(h["number"])
            freq[h["number"]] += 1

        # calcular ausentes apenas com base na janela
        ausentes = {n: (self.tamanho_janela if n not in numeros_na_janela else 0) for n in range(37)}

        max_freq = max(freq.values()) if freq else 1
        max_ausencia = max(ausentes.values()) if ausentes else 1

        scores = {}
        for n in range(37):
            ausencia_norm = ausentes[n] / max_ausencia if max_ausencia > 0 else 0
            freq_norm = freq[n] / max_freq if max_freq > 0 else 0
            score = (ausencia_norm * 0.6) + (freq_norm * 0.4)
            scores[n] = score

        # pegar top N com maior score
        return [num for num, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:qtd]]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta - Estratégia Ausentes", layout="centered")
st.title("🎯 Roleta — Estratégia Números Ausentes Inteligente")
st_autorefresh(interval=3000, key="refresh")

# Inicialização do session_state
for key, default in {
    "estrategia": EstrategiaAusentes(),
    "previsao": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carregar histórico salvo
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)

# Buscar novo resultado
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))

    # -----------------------------
    # Conferência GREEN/RED
    # -----------------------------
    if st.session_state.previsao:
        numero_real = numero_dict["number"]
        if numero_real in st.session_state.previsao:
            st.session_state.acertos += 1
            st.success(f"🟢 GREEN! Número {numero_real} estava entre os ausentes previstos.")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} estava entre os ausentes previstos.")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 RED! Número {numero_real} não estava entre os ausentes previstos.")
            enviar_telegram(f"🔴 RED! Número {numero_real} não estava entre os ausentes previstos.")
        st.session_state.previsao = []

    st.session_state.contador_rodadas += 1

    # -----------------------------
    # Nova previsão a cada rodada
    # -----------------------------
    prox_numeros = st.session_state.estrategia.prever()
    if prox_numeros:
        st.session_state.previsao = prox_numeros
        msg_alerta = "🎯 Números prováveis (ausentes): " + " ".join(str(n) for n in prox_numeros)
        enviar_telegram(msg_alerta)

# =============================
# Dashboard
# =============================
st.subheader("📜 Histórico (últimos 5 números)")
st.write(list(st.session_state.estrategia.historico)[-5:])

# Estatísticas GREEN/RED
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", acertos)
col2.metric("🔴 RED", erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")

# Estatísticas de Ausentes
st.subheader("📊 Estatísticas de Ausentes")
st.write(f"Total de registros no histórico: {len(st.session_state.estrategia.historico)}")
