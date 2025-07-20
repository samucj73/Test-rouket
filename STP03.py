import streamlit as st
import requests
import json
import os
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"  # Canal Sinais VIP
ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
    10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# === ESTADOS ===
if 'historico' not in st.session_state:
    st.session_state.historico = deque(maxlen=300)

if 'ultimo_timestamp' not in st.session_state:
    st.session_state.ultimo_timestamp = None

if 'entrada_atual' not in st.session_state:
    st.session_state.entrada_atual = None

if 'n_entrada' not in st.session_state:
    st.session_state.n_entrada = 0

if 'green_count' not in st.session_state:
    st.session_state.green_count = 0

if 'red_nucleos' not in st.session_state:
    st.session_state.red_nucleos = []

# === FUNÇÕES ===
def get_neighbors(number):
    if number not in ROULETTE_NUMBERS:
        return []
    idx = ROULETTE_NUMBERS.index(number)
    total = len(ROULETTE_NUMBERS)
    neighbors = []
    for i in range(-5, 6):  # 5 anteriores e 5 posteriores
        if i == 0:
            neighbors.append(number)
        else:
            neighbors.append(ROULETTE_NUMBERS[(idx + i) % total])
    return sorted(set(neighbors))

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def atualizar_historico():
    try:
        response = requests.get(API_URL)
        data = response.json()

        if 'outcome' not in data or not data['outcome']:
            return

        novo_numero = int(data['outcome'][0]['value'])
        timestamp = data['timestamp']

        if timestamp != st.session_state.ultimo_timestamp:
            st.session_state.historico.append(novo_numero)
            st.session_state.ultimo_timestamp = timestamp
            return novo_numero
    except Exception as e:
        print("Erro ao acessar API:", e)
    return None

def gerar_entrada():
    historico = list(st.session_state.historico)
    if len(historico) < 14:
        return None

    janela = historico[-13:-1]  # 12 números antes do 13º
    gatilho = historico[-2]     # 13º número
    resultado = historico[-1]   # 14º número

    terminais = [n % 10 for n in janela]
    contagem = Counter(terminais)
    dominantes = [t for t, _ in contagem.most_common(2)]

    candidatos = [n for n in range(1, 37) if n % 10 in dominantes]

    # Frequência relativa (probabilidade)
    freq = Counter([n for n in janela if n in candidatos])
    total = sum(freq.values()) + 1e-6
    probs_numeros = [(n, freq[n] / total) for n in candidatos]

    # Ordena por maior probabilidade
    probs_numeros.sort(key=lambda x: x[1], reverse=True)

    # Verifica proximidade de probabilidade
    if len(probs_numeros) >= 4:
        diff = abs(probs_numeros[0][1] - probs_numeros[3][1])
        top_numeros = probs_numeros[:4] if diff < 0.02 else probs_numeros[:3]
    else:
        top_numeros = probs_numeros[:3]

    # Remove números que deram RED recentemente
    top_numeros = [n for n in top_numeros if n[0] not in st.session_state.red_nucleos]

    if len(top_numeros) < 2:
        return None  # Evita entrada se poucos núcleos confiáveis

    entrada_principal = []
    for numero, prob in top_numeros:
        entrada_principal.extend(get_neighbors(numero))

    entrada_principal = sorted(set(entrada_principal))

    prob_media = sum(p for _, p in top_numeros) / len(top_numeros)

    if prob_media > 0.75:
        return {
            "entrada": entrada_principal,
            "nucleos": [n[0] for n in top_numeros],
            "gatilho": gatilho,
            "resultado": resultado
        }
    return None

# === APP STREAMLIT ===
st.set_page_config(page_title="IA Roleta Estratégica", layout="centered")
st.title("🎯 Estratégia IA • Núcleos Dominantes + Vizinhos")
st_autorefresh(interval=5000, key="refresh")

numero_novo = atualizar_historico()

if numero_novo is not None:
    st.success(f"🎯 Novo número: {numero_novo}")

    # Verifica se houve entrada anterior para validar GREEN / RED
    if st.session_state.entrada_atual:
        if numero_novo in st.session_state.entrada_atual["entrada"]:
            st.session_state.green_count += 1
            st.success("✅ GREEN")
            st.session_state.red_nucleos = []  # limpa lista de REDs
        else:
            st.error("❌ RED")
            st.session_state.green_count = 0
            st.session_state.red_nucleos.extend(st.session_state.entrada_atual["nucleos"])  # salva núcleos que deram RED

        st.session_state.entrada_atual = None

    nova_entrada = gerar_entrada()

    if nova_entrada and numero_novo == nova_entrada["gatilho"]:
        st.session_state.entrada_atual = nova_entrada
        st.session_state.n_entrada += 1

        entrada_texto = ", ".join(str(n) for n in nova_entrada["entrada"])
        nucleos_texto = ", ".join(str(n) for n in nova_entrada["nucleos"])
        estrategia = "Terminais Dominantes + IA Vizinhos"

        mensagem = f"""📢 <b>ENTRADA GERADA</b> #{st.session_state.n_entrada}

🎯 <b>Ordem:</b> {estrategia}
🔢 <b>Núcleos:</b> {nucleos_texto}
🎲 <b>Numeros:</b> {entrada_texto}
🧠 <i>(Baseado em IA)</i>"""

        enviar_telegram(mensagem)

# === HISTÓRICO E STATUS ===
st.subheader("📋 Histórico (últimos 20):")
st.write(list(st.session_state.historico)[-20:])

st.subheader("📊 Status:")
st.write(f"🟢 Greens: {st.session_state.green_count}")
st.write(f"🔁 Entradas geradas: {st.session_state.n_entrada}")
