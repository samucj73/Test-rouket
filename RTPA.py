import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"

# Ordem física da roleta europeia
ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# === FUNÇÕES ===

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.warning(f"Erro ao enviar alerta Telegram: {e}")

def expandir_com_vizinhos(numeros):
    entrada_expandida = set(numeros)
    for numero in numeros:
        if numero in ROULETTE_NUMBERS:
            idx = ROULETTE_NUMBERS.index(numero)
            for i in range(-2, 3):
                vizinho = ROULETTE_NUMBERS[(idx + i) % len(ROULETTE_NUMBERS)]
                entrada_expandida.add(vizinho)
    return sorted(entrada_expandida)

def obter_numero_e_timestamp():
    try:
        response = requests.get(API_URL)
        data = response.json()
        numero = int(data["data"]["outcome"]["number"])
        timestamp = data["data"]["startedAt"]
        return numero, timestamp
    except Exception as e:
        st.error(f"Erro ao obter número da roleta: {e}")
        return None, None

# === INICIALIZAÇÃO DE ESTADO ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=20)

if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []

if "entrada_info" not in st.session_state:
    st.session_state.entrada_info = {}

if "ultimo_alerta" not in st.session_state:
    st.session_state.ultimo_alerta = None

# === INTERFACE ===
st.title("🎯 Estratégia de Roleta - IA com Terminais + Vizinhos")
st_autorefresh(interval=5000, key="auto-refresh")

numero, timestamp = obter_numero_e_timestamp()

if numero is not None:
    st.metric("🎲 Último número", numero)
    st.text(f"⏱️ Timestamp: {timestamp}")

    # Verifica duplicidade pelo timestamp
    if not st.session_state.historico or st.session_state.historico[-1][1] != timestamp:
        st.session_state.historico.append((numero, timestamp))

    numeros_hist = [n for n, _ in st.session_state.historico]
    st.write("🧾 Histórico:", numeros_hist)

    # === IA Lógica ===
    if len(numeros_hist) >= 14:
        janela = numeros_hist[-13:-1]     # 12 números
        numero_13 = numeros_hist[-2]      # Gatilho (13º)
        numero_14 = numeros_hist[-1]      # Número de verificação (14º)

        terminais = [n % 10 for n in janela]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]
        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        # === IA - Probabilidade baseada em dominância ===
        prob = sum([contagem[t] for t in dominantes]) / len(janela)

        if prob > 0.65 and not st.session_state.entrada_atual:
            chave_alerta = f"{numero_13}-{dominantes}"

            if st.session_state.ultimo_alerta != chave_alerta:
                st.session_state.entrada_atual = entrada_expandida
                st.session_state.entrada_info = {
                    "dominantes": dominantes,
                    "base": janela,
                    "gatilho": numero_13
                }
                st.session_state.ultimo_alerta = chave_alerta

                enviar_telegram(
                    f"🎯 Entrada IA:\nTerminais: {dominantes}\nNúcleos: {entrada_principal}\nEntrada completa: {entrada_expandida}"
                )

    # === VERIFICAÇÃO DE GREEN/RED ===
    if st.session_state.entrada_atual:
        if numero in st.session_state.entrada_atual:
            st.success("🟢 GREEN! Número dentro da entrada.")
        else:
            st.error("🔴 RED! Número fora da entrada.")
        st.write("🎯 Entrada atual:", st.session_state.entrada_atual)
        st.write("📌 Info:", st.session_state.entrada_info)
