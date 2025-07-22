import streamlit as st
import requests
import os
import joblib
from collections import deque
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_SINAL_PATH = "ultimo_sinal.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HISTORICO = 20
PROBABILIDADE_MINIMA = 0.50
AUTOREFRESH_INTERVAL = 5000

# === TELEGRAM ===
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID =  "-1002796136111"

# === ORDEM FÍSICA ROLETA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

# === FUNÇÕES UTILITÁRIAS ===
def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_features(historico):
    return [[n % 10] for n in historico]

def treinar_modelo(historico):
    if len(historico) < 10:
        return None
    X = extrair_features(historico)
    y = [n % 10 for n in list(historico)[1:]]
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X[:-1], y)
    salvar(modelo, MODELO_PATH)
    return modelo

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 5:
        return []
    entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:2]

def gerar_entrada_com_vizinhos(terminais):
    base = [n for t in terminais for n in range(37) if n % 10 == t]
    entrada = set()
    for n in base:
        if n in ordem_roleta:
            i = ordem_roleta.index(n)
            vizinhos = [ordem_roleta[(i + j) % len(ordem_roleta)] for j in range(-2, 3)]
            entrada.update(vizinhos)
    return sorted(entrada)

def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

# === STREAMLIT APP ===
st.set_page_config(page_title="IA Sinais Roleta", layout="centered")
st.title("🎯 IA Sinais Roleta (Terminais + Vizinhos)")

st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_sinal = carregar(ULTIMO_SINAL_PATH, {"entrada": [], "referencia": None})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

# === OBTÉM NÚMERO ATUAL ===
try:
    r = requests.get(API_URL, timeout=7)
    r.raise_for_status()
    data = r.json()
    numero = data["data"]["result"]["outcome"]["number"]
except Exception as e:
    st.error(f"⚠️ Erro ao acessar API: {e}")
    st.stop()

# === ATUALIZA HISTÓRICO ===
if not historico or numero != historico[-1]:
    historico.append(numero)
    salvar(historico, HISTORICO_PATH)

st.write("🕒 Último número:", numero)

# === IA E PREVISÃO ===
modelo = carregar(MODELO_PATH, None)
if not modelo:
    modelo = treinar_modelo(historico)

if modelo and len(historico) >= 10:
    terminais_previstos = prever_terminais(modelo, historico)
    st.write("🔍 Probabilidades previstas:", terminais_previstos)

    if terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
        terminais_escolhidos = [t[0] for t in terminais_previstos]
        entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)

        st.success(f"✅ Entrada IA: {entrada} (Terminais: {terminais_escolhidos})")

        # === VERIFICA SE É NOVO SINAL ===
        if ultimo_sinal["referencia"] != historico[-2]:
            msg = (
                f"🚨 <b>Nova Entrada IA</b>\n"
                f"🎯 Números: <code>{entrada}</code>\n"
                f"📊 Base: Terminais {terminais_escolhidos}"
            )
            enviar_telegram(msg)
            ultimo_sinal = {"entrada": entrada, "referencia": historico[-2]}
            salvar(ultimo_sinal, ULTIMO_SINAL_PATH)

        # === VERIFICA GREEN / RED ===
        if ultimo_sinal["entrada"]:
            if numero in ultimo_sinal["entrada"]:
                contadores["green"] += 1
                resultado = "🟢 GREEN!"
            else:
                contadores["red"] += 1
                resultado = "🔴 RED!"
            salvar(contadores, CONTADORES_PATH)
            salvar(ultimo_sinal, ULTIMO_SINAL_PATH)

            st.markdown(f"📥 Resultado: **{numero}** → {resultado}")
            enviar_telegram(f"📥 Resultado: <b>{numero}</b> → {resultado}")

    else:
        st.warning("⚠️ Aguardando nova entrada da IA...")
else:
    st.info("⏳ Aguardando mais dados para treinar o modelo...")

# === CONTADORES ===
col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
