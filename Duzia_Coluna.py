# IA DÚZIA + COLUNA - APP STREAMLIT
import streamlit as st
import requests
import os
import joblib
import time
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh

# ========== CONFIG ========== #
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
HISTORICO_PATH = "historico.pkl"
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HIST = 600

# ========== FUNÇÕES ========= #

def enviar_telegram(mensagem):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        )
    except Exception as e:
        print("Erro ao enviar mensagem Telegram:", e)

def extrair_features(historico):
    features = []
    for i in range(len(historico)):
        amostra = historico[:i+1]
        x = []

        contagem = Counter(amostra)
        for n in range(37):
            x.append(contagem.get(n, 0))

        ultimos_5 = amostra[-5:]
        ultimos_10 = amostra[-10:]

        for n in range(37):
            x.append(ultimos_5.count(n))
            x.append(ultimos_10.count(n))

        x.append(sum(amostra) / len(amostra))
        x.append(amostra[-1] if len(amostra) >= 1 else 0)
        x.append(1 if len(amostra) >= 2 and amostra[-1] == amostra[-2] else 0)

        terminal = amostra[-1] % 10 if len(amostra) >= 1 else 0
        x.append(terminal)

        duzia = (amostra[-1] - 1) // 12 + 1 if amostra[-1] != 0 else 0
        x.append(duzia)

        coluna = (amostra[-1] - 1) % 3 + 1 if amostra[-1] != 0 else 0
        x.append(coluna)

        features.append(x)
    return features

def treinar_modelos(historico):
    X = extrair_features(historico)
    y_duzia = [(n - 1) // 12 + 1 if n != 0 else 0 for n in historico]
    y_coluna = [(n - 1) % 3 + 1 if n != 0 else 0 for n in historico]

    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_duzia.fit(X[:-1], y_duzia[:-1])
    modelo_coluna.fit(X[:-1], y_coluna[:-1])

    return modelo_duzia, modelo_coluna

def prever(modelo, historico):
    X = extrair_features(historico)
    entrada = [X[-1]]
    probas = modelo.predict_proba(entrada)[0]
    classe = np.argmax(probas)
    return classe + 1  # Dúzias e colunas começam em 1

# ========== INTERFACE ========= #

st.set_page_config(layout="centered")
st.title("🎯 IA Roleta - Dúzia & Coluna")

st_autorefresh(interval=5000)

if os.path.exists(HISTORICO_PATH):
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=MAX_HIST)

if os.path.exists(ULTIMO_ALERTA_PATH):
    ultimo_alerta = joblib.load(ULTIMO_ALERTA_PATH)
else:
    ultimo_alerta = {"entrada": None, "resultado": None}

if os.path.exists(CONTADORES_PATH):
    contadores = joblib.load(CONTADORES_PATH)
else:
    contadores = {"green": 0, "red": 0}

# ========== API ========= #

try:
    r = requests.get(API_URL, timeout=5)
    r.raise_for_status()
    data = r.json()
    numero_atual = int(data["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro ao consultar API: {e}")
    st.write("Resposta da API:", r.text if 'r' in locals() else "sem resposta")
    st.stop()

st.write(f"Número atual: 🎲 **{numero_atual}**")
historico.append(numero_atual)

# ========== IA ========= #

if len(historico) >= 15 and ultimo_alerta["entrada"] != numero_atual:
    modelo_duzia, modelo_coluna = treinar_modelos(historico)
    previsao_duzia = prever(modelo_duzia, historico)
    previsao_coluna = prever(modelo_coluna, historico)

    mensagem = f"🎯 <b>IA Sugestão</b>\n📦 Dúzia {previsao_duzia}  📍 Coluna {previsao_coluna}"
    enviar_telegram(mensagem)
    ultimo_alerta["entrada"] = numero_atual
    ultimo_alerta["duzia"] = previsao_duzia
    ultimo_alerta["coluna"] = previsao_coluna

# ========== RESULTADO ========= #

if ultimo_alerta.get("entrada") != numero_atual and ultimo_alerta.get("duzia"):
    duzia_atual = (numero_atual - 1) // 12 + 1 if numero_atual != 0 else 0
    coluna_atual = (numero_atual - 1) % 3 + 1 if numero_atual != 0 else 0

    acertou_duzia = duzia_atual == ultimo_alerta.get("duzia")
    acertou_coluna = coluna_atual == ultimo_alerta.get("coluna")

    if acertou_duzia or acertou_coluna:
        enviar_telegram("🟢 <b>GREEN!</b>")
        contadores["green"] += 1
    else:
        enviar_telegram("🔴 <b>RED!</b>")
        contadores["red"] += 1

    ultimo_alerta["resultado"] = numero_atual

# ========== METRICAS ========= #
st.metric("🟢 Greens", contadores["green"])
st.metric("🔴 Reds", contadores["red"])

# ========== SALVAR ========= #
joblib.dump(historico, HISTORICO_PATH)
joblib.dump(ultimo_alerta, ULTIMO_ALERTA_PATH)
joblib.dump(contadores, CONTADORES_PATH)
