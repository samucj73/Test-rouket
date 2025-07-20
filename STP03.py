import streamlit as st
import requests
import json
import os
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import pandas as pd

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
NUM_VIZINHOS = 2
JANELA_ANALISE = 12
PROBABILIDADE_MINIMA = 0.75

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ordem_roleta = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
                11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
                22, 18, 29, 7, 28, 12, 35, 3, 26]

# === FUNÇÃO PARA ENVIAR ALERTA TELEGRAM ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    requests.post(url, json=payload)

# === FUNÇÃO PARA PEGAR VIZINHOS FÍSICOS NA ROLETA ===
def pegar_vizinhos(numero, n=2):
    vizinhos = []
    if numero in ordem_roleta:
        idx = ordem_roleta.index(numero)
        total = len(ordem_roleta)
        for i in range(-n, n+1):
            vizinhos.append(ordem_roleta[(idx + i) % total])
    return vizinhos

# === FUNÇÃO PARA TREINAR IA ===
def treinar_modelo(dados):
    X = []
    y = []
    for i in range(len(dados) - JANELA_ANALISE - 1):
        janela = dados[i:i + JANELA_ANALISE]
        alvo = dados[i + JANELA_ANALISE]
        contagem = Counter([n % 10 for n in janela])
        linha = [contagem.get(i, 0) for i in range(10)]
        X.append(linha)
        y.append(alvo)
    modelo = RandomForestClassifier()
    modelo.fit(X, y)
    return modelo

# === CONTROLE DE ESTADO STREAMLIT ===
if "historico" not in st.session_state:
    st.session_state.historico = []
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = ""
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = None
if "red_nucleos" not in st.session_state:
    st.session_state.red_nucleos = set()

# === AUTOREFRESH A CADA 5 SEGUNDOS ===
st_autorefresh(interval=5000, key="atualizacao")

# === CAPTURA DADOS DA API ===
try:
    response = requests.get(API_URL)
    data = response.json()

    numero = data["data"]["result"]["outcome"]["number"]
    timestamp = data["data"]["settledAt"]

    if timestamp != st.session_state.ultimo_timestamp:
        st.session_state.ultimo_timestamp = timestamp
        st.session_state.historico.append(numero)
        st.success(f"Número capturado: {numero}")
    else:
        st.warning("⏳ Aguardando novo número...")

except Exception as e:
    st.error(f"Erro ao acessar API: {e}")
    st.stop()

# === EXIBE HISTÓRICO ===
st.subheader("📋 Histórico")
st.write(st.session_state.historico[-30:])

# === GERA ENTRADA COM IA ===
historico = st.session_state.historico

if len(historico) >= 100:
    modelo = treinar_modelo(historico)
    janela = historico[-JANELA_ANALISE:]
    contagem = Counter([n % 10 for n in janela])
    linha = [[contagem.get(i, 0) for i in range(10)]]
    probs = modelo.predict_proba(linha)[0]
    indices_ordenados = sorted(range(37), key=lambda i: probs[i], reverse=True)

    top4 = indices_ordenados[:4]
    p1, p4 = probs[top4[0]], probs[top4[3]]

    # Se os 4 primeiros estão próximos, usa os 4
    if p1 - p4 < 0.02:
        nucleos = top4
    else:
        nucleos = indices_ordenados[:3]

    # Remove REDs recentes
    nucleos = [n for n in nucleos if n not in st.session_state.red_nucleos]

    if not nucleos:
        st.warning("❌ Nucleos recentes deram RED. Aguardando nova análise.")
        st.stop()

    prob_media = sum([probs[n] for n in nucleos]) / len(nucleos)

    if prob_media >= PROBABILIDADE_MINIMA and not st.session_state.entrada_atual:
        entrada = set()
        for n in nucleos:
            entrada.update(pegar_vizinhos(n, n=NUM_VIZINHOS))
        entrada = sorted(entrada)
        st.session_state.entrada_atual = {
            "entrada": entrada,
            "timestamp": timestamp,
            "nucleos": nucleos
        }
        enviar_telegram(f"🎯 Entrada gerada com IA:\n👉 Números: {entrada}\n🎲 Núcleos: {nucleos}")
        st.success("✅ Entrada enviada!")
    else:
        st.info("⏳ Aguardando condições ideais para nova entrada.")

# === VERIFICA SE DEU GREEN OU RED ===
entrada_atual = st.session_state.entrada_atual
if entrada_atual and entrada_atual["timestamp"] != timestamp:
    numero_atual = historico[-1]
    if numero_atual in entrada_atual["entrada"]:
        enviar_telegram("🟢 GREEN!\n🎯 Número sorteado: " + str(numero_atual))
        st.success("🟢 GREEN!")
        st.session_state.red_nucleos.clear()
    else:
        enviar_telegram("🔴 RED\nNúmero sorteado: " + str(numero_atual))
        st.error("🔴 RED")
        st.session_state.red_nucleos.update(entrada_atual["nucleos"])

    st.session_state.entrada_atual = None
