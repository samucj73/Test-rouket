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

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

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
        return [
            h if isinstance(h, dict) else {"number": h, "timestamp": f"manual_{i}"}
            for i, h in enumerate(historico)
        ]
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

def obter_vizinhos(numero, layout, antes=1, depois=1):
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
        self.historico = deque(maxlen=1000)

    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA recorrência com pesos
# =============================
class IA_Recorrencia:
    def __init__(self, layout=None, top_n=5, janela_recente=100):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.janela_recente = janela_recente

    def prever(self, historico):
        if len(historico) < 3:
            return []

        historico_lista = list(historico)
        ultimos2 = (historico_lista[-2]["number"], historico_lista[-1]["number"])

        proximos = []
        pesos = []

        for i in range(len(historico_lista) - 2):
            n1 = historico_lista[i]["number"]
            n2 = historico_lista[i + 1]["number"]
            if (n1, n2) == ultimos2:
                prox = historico_lista[i + 2]["number"]
                proximos.append(prox)

                # Peso maior se estiver dentro da janela recente
                if i >= len(historico_lista) - self.janela_recente:
                    pesos.append(2)  # peso duplo
                else:
                    pesos.append(1)

        if not proximos:
            return []

        # Contagem ponderada
        contagem = Counter()
        for n, p in zip(proximos, pesos):
            contagem[n] += p

        top_numeros = [num for num, _ in contagem.most_common(self.top_n)]

        numeros_previstos = []
        for n in top_numeros:
            for v in obter_vizinhos(n, self.layout, antes=1, depois=1):
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        return numeros_previstos

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA de Recorrência (com pesos)")
st_autorefresh(interval=3000, key="refresh")

# Inicialização segura
for key, default in {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia(),
    "previsao": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)

# Captura número
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))

    # Conferência da previsão anterior
    if st.session_state.previsao:
        numero_real = numero_dict["number"]
        if numero_real in st.session_state.previsao:
            st.session_state.acertos += 1
            msg = f"GREEN! Saiu {numero_real}"
            st.success(msg)
            enviar_telegram(msg)
        else:
            st.session_state.erros += 1
            msg = f"RED! Saiu {numero_real}"
            st.error(msg)
            enviar_telegram(msg)
        st.session_state.previsao = []

    # Incrementa rodadas
    st.session_state.contador_rodadas += 1

    # Gera nova previsão a cada 2 rodadas
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros
            msg_alerta = "Próximos: " + " ".join(str(n) for n in prox_numeros)
            enviar_telegram(msg_alerta)

# Histórico
st.subheader("📜 Últimos números")
st.write(list(st.session_state.estrategia.historico)[-5:])

# Estatísticas
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", acertos)
col2.metric("🔴 RED", erros)
col3.metric("✅ Taxa", f"{taxa:.1f}%")
