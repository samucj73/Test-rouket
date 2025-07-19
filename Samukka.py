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
import numpy as np
import time

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
API_URL = "https://casino-api.arugula.games/history?limit=1"
MODELO_PATH = "modelo_estrategia.pkl"
HISTORICO_MAX = 100
N_JANELA = 12

# Ordem física da roleta europeia (sentido horário)
roleta_fisica = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16,
    33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28,
    12, 35, 3, 26
]

# === Funções auxiliares ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Erro ao enviar para o Telegram: {e}")

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return RandomForestClassifier()

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def vizinhos_fisicos(numero, distancia=2):
    idx = roleta_fisica.index(numero)
    total = len(roleta_fisica)
    vizinhos = []
    for i in range(-distancia, distancia + 1):
        vizinhos.append(roleta_fisica[(idx + i) % total])
    return vizinhos

def preparar_entrada_terminais(janela):
    terminais = [n % 10 for n in janela]
    contagem = Counter(terminais)
    dominantes = [t for t, _ in contagem.most_common(2)]
    entrada = [n for n in range(37) if n % 10 in dominantes]
    entrada_com_vizinhos = set()
    for num in entrada:
        entrada_com_vizinhos.update(vizinhos_fisicos(num))
    return list(entrada_com_vizinhos), dominantes

def preparar_entrada_mod3(janela):
    grupos = [n % 3 for n in janela]
    contagem = Counter(grupos)
    dominante = contagem.most_common(1)[0][0]
    entrada = [n for n in range(37) if n % 3 == dominante]
    entrada_com_vizinhos = set()
    for num in entrada:
        entrada_com_vizinhos.update(vizinhos_fisicos(num))
    return list(entrada_com_vizinhos), dominante

def preparar_entrada_vizinhos(janela):
    vizinhos_totais = []
    for num in janela:
        vizinhos_totais += vizinhos_fisicos(num)
    contagem = Counter(vizinhos_totais)
    mais_comuns = [n for n, _ in contagem.most_common(12)]
    entrada = set()
    for num in mais_comuns:
        entrada.update(vizinhos_fisicos(num))
    return list(entrada), mais_comuns[:3]

def extrair_features(janela):
    return pd.DataFrame([{
        "media": np.mean(janela),
        "moda": Counter(janela).most_common(1)[0][0],
        "terminal_mais_freq": Counter([n % 10 for n in janela]).most_common(1)[0][0],
        "mod3_mais_freq": Counter([n % 3 for n in janela]).most_common(1)[0][0],
    }])

# === Início da App ===
st_autorefresh(interval=5000, key="auto")

st.title("🎯 Estratégia IA – Escolha automática")
st.write("A IA escolhe entre: Terminais | Vizinhos Físicos | Mod3")

# Estado
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=HISTORICO_MAX)
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None

# Carrega modelo IA
modelo = carregar_modelo()

# Consulta API
try:
    resposta = requests.get(API_URL)
    dados = resposta.json()
    numero = dados[0]["number"]
    timestamp = dados[0]["timestamp"]
    st.write(f"🎲 Último número: {numero} às {timestamp}")
except:
    st.error("Erro ao acessar API")
    st.stop()

# Verifica duplicidade
if timestamp == st.session_state.ultimo_timestamp:
    st.stop()
else:
    st.session_state.ultimo_timestamp = timestamp
    st.session_state.historico.append(numero)

# Só continua se houver dados suficientes
if len(st.session_state.historico) < N_JANELA + 1:
    st.warning("⏳ Aguardando mais dados para IA...")
    st.stop()

# Treinamento (com resultados passados)
historico = list(st.session_state.historico)
X = []
y = []

for i in range(N_JANELA, len(historico)-1):
    janela = historico[i-N_JANELA:i]
    target = historico[i]
    features = extrair_features(janela)
    X.append(features.iloc[0])
    
    entrada, _ = preparar_entrada_terminais(janela)
    y.append(1 if target in entrada else 0)

if len(X) > 10:
    modelo.fit(pd.DataFrame(X), y)
    salvar_modelo(modelo)

# === DECISÃO DA IA ===
janela = historico[-N_JANELA:]

estrategias = {
    "Terminais": preparar_entrada_terminais(janela),
    "Mod3": preparar_entrada_mod3(janela),
    "Vizinhos": preparar_entrada_vizinhos(janela)
}

resultados = []
for nome, (entrada, info) in estrategias.items():
    features = extrair_features(janela)
    try:
        prob = modelo.predict_proba(features)[0][1]
    except NotFittedError:
        prob = 0.0
    resultados.append((nome, entrada, info, prob))

# Seleciona melhor
melhor_estrategia = max(resultados, key=lambda x: x[3])
nome, entrada, info, prob = melhor_estrategia

# Exibe
st.success(f"✅ Estratégia escolhida pela IA: **{nome}** ({round(prob*100, 1)}%)")
st.write(f"Entrada gerada: {sorted(entrada)}")
st.write(f"Base da entrada: {info}")

# Verifica acerto
proximo_numero = numero
if proximo_numero in entrada:
    st.success("🎯 GREEN!")
    resultado = "GREEN"
else:
    st.error("❌ RED")
    resultado = "RED"

# Enviar Telegram
mensagem = f"""🎯 SINAL GERADO (IA)
📊 Estratégia: {nome}
🎲 Entrada: {sorted(entrada)}
📈 Confiança: {round(prob*100,1)}%
🎯 Resultado: {resultado}
"""
enviar_telegram(mensagem)
