import streamlit as st
import requests
import json
import os
import joblib
from collections import deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import time

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CANAL_ID = "-1002796136111"
URL_API = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"

ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CANAL_ID, "text": mensagem}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

def get_vizinhos(numero, total_vizinhos=5):
    idx = ROULETTE_ORDER.index(numero)
    vizinhos = []
    for i in range(-total_vizinhos, total_vizinhos + 1):
        vizinhos.append(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return vizinhos

# === INICIALIZAÇÃO DO APP ===
st.set_page_config(page_title="Roleta Estratégia Terminal", layout="centered")
st.title("🎯 Estratégia Terminal 2 / 6 / 9")

if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=50)
if "timestamps" not in st.session_state:
    st.session_state.timestamps = deque(maxlen=50)
if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None
if "entrada_ativa" not in st.session_state:
    st.session_state.entrada_ativa = None
if "aguardando_resultado" not in st.session_state:
    st.session_state.aguardando_resultado = False
if "entrada_timestamp" not in st.session_state:
    st.session_state.entrada_timestamp = ""

# === AUTOREFRESH ===
st_autorefresh(interval=5000, key="refresh")

# === CAPTURA DA API ===
try:
    response = requests.get(URL_API)
    data = response.json()

    resultado = data.get("data", {}).get("result", {}).get("outcome")

    if resultado and "number" in resultado:
        numero = resultado["number"]
        timestamp = data["data"].get("settledAt", "")

        if numero != st.session_state.ultimo_numero:
            st.session_state.historico.append(numero)
            st.session_state.timestamps.append(timestamp)
            st.session_state.ultimo_numero = numero

            st.success(f"🎲 Último número: **{numero}** às {timestamp}")

            # === VERIFICAÇÃO DO RESULTADO DE UMA ENTRADA ATIVA ===
            if st.session_state.aguardando_resultado and st.session_state.entrada_ativa:
                if numero in st.session_state.entrada_ativa:
                    enviar_telegram("✅ GREEN!\n🎯 Número sorteado dentro da entrada.")
                    st.success("✅ GREEN! Número dentro da entrada.")
                else:
                    enviar_telegram("❌ RED!\n🔻 Número fora da entrada.")
                    st.error("❌ RED! Número fora da entrada.")
                st.session_state.entrada_ativa = None
                st.session_state.aguardando_resultado = False

            # === CHECAR SE DEVE GERAR NOVA ENTRADA ===
            elif numero % 10 in [2, 6, 9]:
                entrada = set()
                for base in [31, 34]:
                    entrada.update(get_vizinhos(base, total_vizinhos=5))
                entrada_ordenada = sorted(entrada)
                st.session_state.entrada_ativa = entrada_ordenada
                st.session_state.aguardando_resultado = True
                st.session_state.entrada_timestamp = timestamp

                mensagem = (
                    "🚨 NOVA ENTRADA DETECTADA\n"
                    "🎯 Estratégia: Terminais 2 / 6 / 9\n"
                    f"🔢 Entrada: {entrada_ordenada}\n"
                    f"🕒 Ativada após número: {numero} ({timestamp})\n"
                    "🎰 Aguardando próximo número para validar (GREEN/RED)"
                )
                enviar_telegram(mensagem)
                st.success("🚨 Entrada gerada e enviada via Telegram")

    else:
        st.warning("⚠️ Resultado ainda não disponível ou incompleto.")
except Exception as e:
    st.error(f"Erro ao acessar API: {e}")

# === EXIBIÇÃO DO HISTÓRICO ===
st.subheader("📋 Histórico (últimos 20):")
st.write(list(st.session_state.historico)[-20:])

# === EXIBIÇÃO DA ENTRADA ATIVA ===
if st.session_state.entrada_ativa:
    st.subheader("🎯 Entrada Ativa")
    st.info(f"🔢 Números: {st.session_state.entrada_ativa}")
    st.info(f"🕒 Ativada em: {st.session_state.entrada_timestamp}")
    st.info("🎰 Aguardando próximo número para validação...")
