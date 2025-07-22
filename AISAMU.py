import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN_DO_BOT"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
MODELO_PATH = "modelo_terminais_ia.pkl"
HISTORICO_PATH = "historico_terminais.pkl"
ULTIMO_SINAL_PATH = "ultimo_sinal.pkl"
CONTADORES_PATH = "contadores.pkl"
NUM_MAX_HISTORICO = 20

# === ROLETA EUROPEIA ===
roleta_europeia = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

def vizinhos_roleta(numero, n=2):
    if numero not in roleta_europeia:
        return []
    idx = roleta_europeia.index(numero)
    return [roleta_europeia[(idx + i) % len(roleta_europeia)] for i in range(-n, n+1)]

def extrair_terminais(lista):
    return [n % 10 for n in lista]

def salvar(objeto, path):
    joblib.dump(objeto, path)

def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def treinar_modelo(historico):
    X, y = [], []
    for i in range(len(historico) - 3):
        entrada = [n % 10 for n in historico[i:i+3]]
        alvo = historico[i+3] % 10
        X.append(entrada)
        y.append(alvo)
    if len(X) >= 10:
        modelo = RandomForestClassifier(n_estimators=100, random_state=42)
        modelo.fit(X, y)
        salvar(modelo, MODELO_PATH)
        return modelo
    return None

def prever_terminais(modelo, historico):
    entrada = [n % 10 for n in list(historico)[-3:]]
    probs = modelo.predict_proba([entrada])[0]
    terminais = modelo.classes_
    resultado = list(zip(terminais, probs))
    resultado.sort(key=lambda x: x[1], reverse=True)
    return resultado[:2]

def gerar_entrada(dominantes):
    entrada = []
    for t in dominantes:
        nums = [n for n in range(37) if n % 10 == t]
        for n in nums:
            entrada.extend(vizinhos_roleta(n, n=2))
    return sorted(set(entrada))

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# === STREAMLIT APP ===
st.set_page_config(layout="centered")
st_autorefresh(interval=5000, limit=None, key="auto")

st.title("🎯 Estratégia IA Roleta: Terminais + Vizinhos")
st.caption("📡 Rodando com IA, entrada automática e contadores")

# === CARREGAR ESTADOS ===
historico = carregar(HISTORICO_PATH, deque(maxlen=NUM_MAX_HISTORICO))
ultimo_sinal = carregar(ULTIMO_SINAL_PATH, {"entrada": [], "numero_referencia": None})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

# === API ===
try:
    response = requests.get(API_URL, timeout=7)
    response.raise_for_status()
    data = response.json()
    numero = data["data"]["result"]["outcome"]["number"]
    timestamp = data["data"]["startedAt"]
except:
    st.error("⚠️ Erro ao obter dados da API")
    st.stop()

# === ATUALIZA HISTÓRICO ===
if not historico or historico[-1] != numero:
    historico.append(numero)
    salvar(historico, HISTORICO_PATH)

# === TREINAMENTO / PREDIÇÃO ===
if len(historico) >= 6:
    modelo = carregar(MODELO_PATH, None)
    if modelo is None:
        modelo = treinar_modelo(historico)
    
    if modelo:
        terminais_previstos = prever_terminais(modelo, historico)
        terminais = [t[0] for t in terminais_previstos]
        entrada = gerar_entrada(terminais)

        st.write("🧠 Terminais previstos:", terminais_previstos)
        st.success(f"🎯 Entrada IA: {entrada}")

        # === SINAL NOVO? ===
        if ultimo_sinal["numero_referencia"] != historico[-2]:
            mensagem = f"🚨 <b>Entrada IA</b>\n🎯 Números: <code>{entrada}</code>\n📊 Base: terminais {terminais}"
            enviar_telegram(mensagem)
            ultimo_sinal = {
                "entrada": entrada,
                "numero_referencia": historico[-2]  # n anterior
            }
            salvar(ultimo_sinal, ULTIMO_SINAL_PATH)

        # === ACOMPANHA RESULTADO ===
        if ultimo_sinal["entrada"]:
            if numero in ultimo_sinal["entrada"]:
                contadores["green"] += 1
                resultado = "🟢 GREEN!"
            else:
                contadores["red"] += 1
                resultado = "🔴 RED!"
            salvar(contadores, CONTADORES_PATH)
            st.markdown(f"📥 Resultado do número **{numero}**: {resultado}")
    else:
        st.warning("Aguardando dados suficientes para treinar a IA...")
else:
    st.warning("Coletando histórico inicial...")

# === CONTADORES ===
col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
