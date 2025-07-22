import streamlit as st
import requests
import os
import joblib
from collections import deque
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_SINAL_PATH = "ultimo_sinal.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HISTORICO = 20
PROBABILIDADE_MINIMA = 0.50
AUTOREFRESH_INTERVAL = 5000  # 5 segundos

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

# === FUNÇÕES DE UTILIDADE ===
def carregar(caminho, default):
    return joblib.load(caminho) if os.path.exists(caminho) else default

def salvar(objeto, caminho):
    joblib.dump(objeto, caminho)

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
    salvar(modelo, MODELO_PATH)
    return modelo

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 5:
        return []
    ultima_entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(ultima_entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:2]

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

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML"
        }, timeout=5)
    except Exception as e:
        st.warning(f"Erro ao enviar para Telegram: {e}")

# === INTERFACE STREAMLIT ===
st.set_page_config(page_title="IA Roleta", layout="centered")
st.title("🎯 IA Sinais de Roleta: Terminais + Vizinhos")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

# === CARREGAR ESTADOS ===
historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_sinal = carregar(ULTIMO_SINAL_PATH, {"entrada": [], "referencia": None, "numero_enviado": None})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

# === CONSULTA API ===
try:
    response = requests.get(API_URL, timeout=7)
    response.raise_for_status()
    data = response.json()
    numero = data["data"]["result"]["outcome"]["number"]
    timestamp = data["data"]["startedAt"]
except Exception as e:
    st.error(f"⚠️ Erro na API: {e}")
    st.stop()

# === ATUALIZA HISTÓRICO ===
if not historico or numero != historico[-1]:
    historico.append(numero)
    salvar(historico, HISTORICO_PATH)

st.write("🎲 Último número:", numero)

# === TREINAMENTO E PREVISÃO ===
modelo = carregar(MODELO_PATH)
if not modelo:
    modelo = treinar_modelo(historico)

if modelo and len(historico) >= 10:
    terminais_previstos = prever_terminais(modelo, historico)
    if terminais_previstos:
        st.write("📊 Previsão IA (terminal, prob):", terminais_previstos)
        if terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
            terminais_escolhidos = [t[0] for t in terminais_previstos]
            entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)
            st.success(f"✅ Entrada IA: {entrada}")

            # === ENVIA ALERTA APENAS UMA VEZ POR NÚMERO ===
            if len(historico) >= 2 and ultimo_sinal["numero_enviado"] != historico[-2]:
                msg = (
                    f"🚨 <b>Nova Entrada IA</b>\n"
                    f"🎯 Números: <code>{entrada}</code>\n"
                    f"📊 Base: Terminais {terminais_escolhidos}"
                )
                enviar_telegram(msg)
                ultimo_sinal = {
                    "entrada": entrada,
                    "referencia": historico[-2],
                    "numero_enviado": historico[-2]
                }
                salvar(ultimo_sinal, ULTIMO_SINAL_PATH)
        else:
            st.warning("⚠️ Aguardando nova entrada da IA...")
    else:
        st.warning("⚠️ Não foi possível prever terminais.")
else:
    st.info("⏳ Aguardando dados suficientes...")

# === VERIFICAÇÃO DE GREEN OU RED ===
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

# === EXIBE CONTADORES ===
st.markdown(f"🟢 Greens: **{contadores['green']}** &nbsp;&nbsp;&nbsp; 🔴 Reds: **{contadores['red']}**")
