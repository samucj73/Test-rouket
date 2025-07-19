import streamlit as st
import requests
import json
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError

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

def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    vizinhos = []
    for i in range(-2, 3):
        vizinhos.append(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return vizinhos

def gerar_entrada_estrategia_1(janela):
    terminais = [n % 10 for n in janela]
    contagem = Counter(terminais)
    dominantes = [t for t, _ in contagem.most_common(2)]
    entrada_principal = [n for n in range(37) if n % 10 in dominantes]
    entrada_completa = set()
    for n in entrada_principal:
        entrada_completa.update(get_vizinhos(n))
    return list(entrada_completa)

def gerar_entrada_estrategia_8(janela):
    grupos = [n % 3 for n in janela]
    contagem = Counter(grupos)
    dominantes = [g for g, _ in contagem.most_common(2)]
    entrada_principal = [n for n in range(37) if n % 3 in dominantes]
    entrada_completa = set()
    for n in entrada_principal:
        entrada_completa.update(get_vizinhos(n))
    return list(entrada_completa)

def calcular_probabilidade(entrada, ultimos_numeros):
    acertos = sum([1 for n in ultimos_numeros if n in entrada])
    return acertos / len(ultimos_numeros) if ultimos_numeros else 0

# === INICIALIZAÇÃO ===
st.set_page_config(page_title="Roleta IA Estratégica", layout="centered")
st.title("🎯 Estratégia com IA - Roleta")

if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=50)
if "timestamps" not in st.session_state:
    st.session_state.timestamps = deque(maxlen=50)
if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None
if "ultima_entrada" not in st.session_state:
    st.session_state.ultima_entrada = None

# === AUTOREFRESH ===
st_autorefresh(interval=5000, key="refresh")

# === CAPTURA DA API COM TRATAMENTO DE ERRO ===
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
    else:
        st.warning("⚠️ Resultado ainda não disponível ou incompleto.")
except Exception as e:
    st.error(f"Erro ao acessar API: {e}")

# === EXIBIR HISTÓRICO ===
st.subheader("📋 Histórico (últimos 20):")
st.write(list(st.session_state.historico)[-20:])

# === IA DECIDE MELHOR ESTRATÉGIA ===
if len(st.session_state.historico) >= 15:
    janela = list(st.session_state.historico)[-12:]
    ultimos3 = list(st.session_state.historico)[-3:]

    entrada1 = gerar_entrada_estrategia_1(janela)
    entrada8 = gerar_entrada_estrategia_8(janela)

    prob1 = calcular_probabilidade(entrada1, ultimos3)
    prob8 = calcular_probabilidade(entrada8, ultimos3)

    if prob1 > prob8:
        entrada_escolhida = entrada1
        estrategia = "1 - Vizinhos físicos"
        prob = prob1
    else:
        entrada_escolhida = entrada8
        estrategia = "8 - Grupos mod 3"
        prob = prob8

    if entrada_escolhida != st.session_state.ultima_entrada and prob >= 0.5:
        st.session_state.ultima_entrada = entrada_escolhida
        mensagem = f"🎯 ENTRADA GERADA\n🎲 Números: {sorted(entrada_escolhida)}\n📊 Estratégia: {estrategia}\n📈 Probabilidade: {prob:.2%}"
        enviar_telegram(mensagem)
        st.success("✅ Entrada enviada via Telegram")
    else:
        st.info(f"🤖 Aguardando melhor probabilidade (Atual: {prob:.2%})")
