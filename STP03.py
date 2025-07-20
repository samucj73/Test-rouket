import streamlit as st
import requests
import json
import os
import joblib
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
MODELO_PATH = "modelo_roleta.pkl"
JANELA = 12
PROB_MINIMA = 0.75

# === CARREGAR MODELO OU CRIAR NOVO ===
if os.path.exists(MODELO_PATH):
    modelo = joblib.load(MODELO_PATH)
else:
    modelo = RandomForestClassifier()
    modelo_treinado = False

# === ESTADOS ===
if "historico" not in st.session_state:
    st.session_state.historico = []
if "ultimos_reds" not in st.session_state:
    st.session_state.ultimos_reds = []
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []

# === FUNÇÕES ===
def capturar_numero_api():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()

        resultado = data.get("data", {}).get("result", {}).get("outcome", {})
        numero = resultado.get("number")
        timestamp = data.get("data", {}).get("settledAt")

        if numero is None or timestamp is None:
            raise ValueError("Número ou timestamp não encontrados.")

        return numero, timestamp
    except Exception as e:
        st.error(f"Erro ao acessar API: {e}")
        return None, None

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Erro ao enviar para o Telegram: {e}")

def treinar_modelo(numeros):
    X = []
    y = []
    for i in range(len(numeros) - JANELA):
        X.append(numeros[i:i + JANELA])
        y.append(numeros[i + JANELA])
    if X and y:
        modelo.fit(X, y)

        # 🔧 Garante que o modelo reconheça todas as classes (0 a 36)
        modelo.classes_ = list(range(37))

        joblib.dump(modelo, MODELO_PATH)

def prever_proximos(numeros):
    try:
        entrada = [numeros[-JANELA:]]
        probs = modelo.predict_proba(entrada)[0]
        return probs
    except NotFittedError:
        return None

def analisar_probabilidades(probs):
    if probs is None or len(probs) < 37:
        st.error(f"Erro: vetor de probabilidades com tamanho incorreto ({len(probs)}). Esperado: 37")
        return []

    indices_ordenados = sorted(range(37), key=lambda i: probs[i], reverse=True)
    top3 = indices_ordenados[:3]
    p_top3 = [probs[i] for i in top3]

    if len(indices_ordenados) >= 4:
        dif = probs[indices_ordenados[3]] - probs[indices_ordenados[2]]
        if dif >= -0.01:
            top3.append(indices_ordenados[3])

    top_filtrado = [n for n in top3 if n not in st.session_state.ultimos_reds]

    return top_filtrado

def obter_vizinhos(numero):
    ordem_fisica = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
        13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
        20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
    ]
    idx = ordem_fisica.index(numero)
    vizinhos = []
    for i in range(-2, 3):
        vizinhos.append(ordem_fisica[(idx + i) % len(ordem_fisica)])
    return vizinhos

# === AUTORREFRESH ===
st_autorefresh(interval=5000, key="refresh")

# === APP ===
st.title("🎯 Estratégia com IA - Roleta")

numero, timestamp = capturar_numero_api()

if numero is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.historico.append(numero)
    st.session_state.ultimo_timestamp = timestamp

    # 🔁 Treinamento com mínimo de dados
    if len(st.session_state.historico) > JANELA + 20:
        treinar_modelo(st.session_state.historico)

        # 🔮 Previsão
        probs = prever_proximos(st.session_state.historico)
        top_numeros = analisar_probabilidades(probs)

        if probs is not None and any(probs[i] > PROB_MINIMA for i in top_numeros):
            entrada_principal = []
            for n in top_numeros:
                entrada_principal += obter_vizinhos(n)
            entrada_principal = sorted(set(entrada_principal))
            st.session_state.entrada_atual = entrada_principal

            enviar_telegram(f"🎯 Entrada IA: {entrada_principal} (base: {top_numeros})")
            st.success(f"🎯 Entrada enviada: {entrada_principal}")

        else:
            st.info("🔎 Aguardando oportunidade com alta probabilidade...")

    # ✅ Verificar resultado anterior
    if st.session_state.entrada_atual:
        if numero in st.session_state.entrada_atual:
            st.success(f"✅ GREEN! Número {numero} estava na entrada.")
            st.session_state.ultimos_reds.clear()
        else:
            st.error(f"❌ RED. Número {numero} fora da entrada.")
            st.session_state.ultimos_reds.extend(top_numeros)
        st.session_state.entrada_atual = []

# === EXIBIÇÃO ===
st.markdown("### 📋 Histórico")
st.write(st.session_state.historico[-20:])
