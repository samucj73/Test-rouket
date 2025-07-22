import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_ENVIO_PATH = "ultimo_envio.pkl"
MAX_HISTORICO = 20
PROBABILIDADE_MINIMA = 0.50
AUTOREFRESH_INTERVAL = 5000  # 5 segundos

# TELEGRAM
TELEGRAM_TOKEN = "7900056631:AAH...v2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

# === ORDEM FÍSICA DA ROLETA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

# === FUNÇÕES UTILITÁRIAS ===
def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        return joblib.load(HISTORICO_PATH)
    return deque(maxlen=MAX_HISTORICO)

def salvar_historico(historico):
    joblib.dump(historico, HISTORICO_PATH)

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return None

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def extrair_terminal(numero):
    return numero % 10

def extrair_features(historico):
    return [[n % 10] for n in historico]

def treinar_modelo(historico):
    if len(historico) < 10:
        return None
    X = extrair_features(historico)
    y = [n % 10 for n in list(historico)[1:]]
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X[:-1], y)
    salvar_modelo(modelo)
    return modelo

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 5:
        return []
    ultima_entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(ultima_entrada)[0]
    terminais_prob = sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])
    return terminais_prob[:2]

def gerar_entrada_com_vizinhos(terminais):
    numeros_base = []
    for t in terminais:
        numeros_base.extend([n for n in range(37) if n % 10 == t])
    entrada_completa = set()
    for numero in numeros_base:
        try:
            idx = ordem_roleta.index(numero)
            vizinhos = [ordem_roleta[(idx + i) % len(ordem_roleta)] for i in range(-2, 3)]
            entrada_completa.update(vizinhos)
        except ValueError:
            pass
    return sorted(entrada_completa)

def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def carregar_ultimo_envio():
    if os.path.exists(ULTIMO_ENVIO_PATH):
        return joblib.load(ULTIMO_ENVIO_PATH)
    return None

def salvar_ultimo_envio(numero):
    joblib.dump(numero, ULTIMO_ENVIO_PATH)

# === INÍCIO DO APP ===
st.set_page_config(page_title="IA Sinais Roleta", layout="centered")
st.title("🎯 IA Sinais de Roleta: Estratégia por Terminais Dominantes + Vizinhos")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar_historico()
ultimo_enviado = carregar_ultimo_envio()

# === CONSULTA A API COM ERROS TRATADOS ===
try:
    response = requests.get(API_URL, timeout=7)
    response.raise_for_status()
    data = response.json()
    numero_atual = data["data"]["result"]["outcome"]["number"]
    timestamp = data["data"]["startedAt"]
except Exception as e:
    st.error(f"⚠️ Erro ao acessar API: {e}")
    st.stop()

# Salva novo número no histórico
if not historico or numero_atual != historico[-1]:
    historico.append(numero_atual)
    salvar_historico(historico)

st.write("🕒 Último número:", numero_atual)

modelo = carregar_modelo()
if not modelo:
    modelo = treinar_modelo(historico)

if modelo and len(historico) >= 10:
    terminais_previstos = prever_terminais(modelo, historico)

    if terminais_previstos:
        st.write("🔍 Probabilidades previstas:", terminais_previstos)
        if terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
            terminais_escolhidos = [t[0] for t in terminais_previstos]
            entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)

            st.success(f"✅ Entrada IA (terminais {terminais_escolhidos}): {entrada}")

            # Enviar alerta caso ainda não tenha sido enviado para esse número
            if numero_atual != ultimo_enviado:
                mensagem = f"🎯 *SINAL IA ROLET* 🎯\n\n📍 Terminais: {terminais_escolhidos}\n🎯 Entrada: {entrada}\n🕒 Número atual: {numero_atual}"
                enviar_alerta_telegram(mensagem)
                salvar_ultimo_envio(numero_atual)
        else:
            st.warning("⚠️ Aguardando nova entrada da IA...")
    else:
        st.warning("⚠️ Não foi possível prever terminais.")
else:
    st.info("⏳ Aguardando dados suficientes para treinar o modelo.")
