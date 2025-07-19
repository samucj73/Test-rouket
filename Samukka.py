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

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
MODELO_PATH = "modelo_ia.pkl"
HISTORICO_MAXIMO = 100
N_JANELA = 12
PROBABILIDADE_LIMIAR = 0.65

# === Funções ===

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erro ao enviar para o Telegram: {e}")

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return RandomForestClassifier()

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def extrair_features(janela):
    terminais = [n % 10 for n in janela]
    contagem_terminais = Counter(terminais)
    top2_terminais = [item[0] for item in contagem_terminais.most_common(2)]

    features = {
        "terminal_mais_comum": top2_terminais[0],
        "terminal_segundo_mais_comum": top2_terminais[1],
        "freq_mais_comum": contagem_terminais[top2_terminais[0]],
        "freq_segundo_mais_comum": contagem_terminais[top2_terminais[1]],
        "soma": sum(janela),
        "media": sum(janela)/len(janela),
        "mod3_freqs": [sum(1 for n in janela if n % 3 == i) for i in range(3)],
        "ultimo": janela[-1],
    }
    return pd.DataFrame([features])

def gerar_entrada(janela):
    contagem = Counter([n % 10 for n in janela])
    dominantes = [item[0] for item in contagem.most_common(2)]
    entrada_principal = [n for n in range(37) if n % 10 in dominantes]
    vizinhos_roleta = {
        0: [26, 32, 15, 19], 1: [33, 20, 14, 31], 2: [4, 21, 25, 17], 3: [12, 26, 35, 11],
        4: [19, 21, 2, 16], 5: [24, 10, 23, 16], 6: [27, 13, 34, 1], 7: [28, 12, 29, 18],
        8: [23, 30, 10, 11], 9: [31, 22, 18, 14], 10: [5, 8, 30, 23], 11: [35, 8, 3, 30],
        12: [3, 7, 26, 35], 13: [6, 27, 36, 33], 14: [1, 20, 9, 22], 15: [19, 32, 0, 26],
        16: [5, 23, 4, 24], 17: [2, 25, 34, 6], 18: [7, 29, 9, 22], 19: [15, 4, 21, 0],
        20: [33, 1, 14, 9], 21: [4, 2, 19, 25], 22: [9, 14, 18, 29], 23: [5, 10, 16, 8],
        24: [16, 5, 36, 10], 25: [2, 21, 17, 34], 26: [15, 3, 12, 0], 27: [6, 13, 36, 1],
        28: [7, 12, 29, 18], 29: [7, 18, 22, 28], 30: [10, 8, 11, 23], 31: [1, 9, 33, 20],
        32: [0, 15, 19, 26], 33: [20, 1, 31, 13], 34: [6, 17, 25, 2], 35: [11, 3, 12, 26],
        36: [13, 24, 27, 5]
    }

    entrada_completa = set(entrada_principal)
    for num in entrada_principal:
        entrada_completa.update(vizinhos_roleta.get(num, []))
    return sorted(entrada_completa)

# === Estado da Aplicação ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=HISTORICO_MAXIMO)
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = None
if "modelo" not in st.session_state:
    st.session_state.modelo = carregar_modelo()

# === Auto-refresh a cada 5s ===
st_autorefresh(interval=5000, key="refresh")

# === CAPTURA DO NÚMERO E TIMESTAMP ===
try:
    resposta = requests.get(API_URL)
    dados = resposta.json()
    numero = dados["data"]["result"]["outcome"]["number"]
    timestamp = dados["data"]["settledAt"]
    st.write(f"🎲 Último número: {numero} às {timestamp}")
except Exception as e:
    st.error(f"Erro ao acessar API: {e}")
    st.stop()

# === EVITA REPETIÇÃO ===
if timestamp == st.session_state.ultimo_timestamp:
    st.stop()
st.session_state.ultimo_timestamp = timestamp
st.session_state.historico.append(numero)

# === IA: Treinamento e Previsão ===
if len(st.session_state.historico) >= N_JANELA + 1:
    janela = list(st.session_state.historico)[-N_JANELA-1:-1]
    X = extrair_features(janela)
    y = int(numero in gerar_entrada(janela))
    modelo = st.session_state.modelo
    try:
        prob = modelo.predict_proba(X)[0][1]
    except NotFittedError:
        prob = 0
    modelo.fit(X, [y])
    salvar_modelo(modelo)

    if prob > PROBABILIDADE_LIMIAR and not st.session_state.entrada_atual:
        entrada = gerar_entrada(janela)
        st.session_state.entrada_atual = {
            "numeros": entrada,
            "referencia": numero,
            "timestamp": timestamp
        }
        msg = f"📢 Entrada gerada (Prob: {prob:.2f})\n🎯 Números: {entrada}"
        st.success(msg)
        enviar_telegram(msg)

# === Verificação de GREEN/RED ===
if st.session_state.entrada_atual:
    entrada = st.session_state.entrada_atual["numeros"]
    if numero in entrada and timestamp != st.session_state.entrada_atual["timestamp"]:
        st.success("✅ GREEN!")
        enviar_telegram("✅ GREEN!")
        st.session_state.entrada_atual = None
    elif timestamp != st.session_state.entrada_atual["timestamp"]:
        st.error("❌ RED!")
        enviar_telegram("❌ RED!")
        st.session_state.entrada_atual = None
