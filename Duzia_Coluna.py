# IA DÚZIA + COLUNA - APP STREAMLIT

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
HISTORICO_PATH = "historico.pkl"
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HISTORICO = 600
PROBABILIDADE_MINIMA = 0.35
AUTOREFRESH_INTERVAL = 5000

TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

# === FUNÇÕES DE SUPORTE ===

def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_duzia(numero):
    if 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    elif 25 <= numero <= 36: return 3
    return 0

def extrair_coluna(numero):
    if numero == 0: return 0
    elif numero % 3 == 1: return 1
    elif numero % 3 == 2: return 2
    return 3

def extrair_features(historico):
    features = []
    janela = 100
    for i in range(len(historico) - janela):
        janela_atual = list(historico)[i:i+janela]
        ult_num = janela_atual[-1]
        freq = Counter(janela_atual)
        freq_nums = [freq.get(n, 0) for n in range(37)]
        duzias = [extrair_duzia(n) for n in janela_atual]
        colunas = [extrair_coluna(n) for n in janela_atual]
        entrada = [
            ult_num,
            extrair_duzia(ult_num),
            extrair_coluna(ult_num),
            sum(janela_atual),
            np.mean(janela_atual),
        ] + freq_nums + [duzias.count(1), duzias.count(2), duzias.count(3)] + \
            [colunas.count(1), colunas.count(2), colunas.count(3)]
        features.append(entrada)
    return features

def treinar_modelo(historico):
    if len(historico) < 120:
        return None, None
    X = extrair_features(historico)
    inicio = len(historico) - len(X) - 1
    historico_alvo = list(historico)[inicio + 1:]
    y_duzia = [extrair_duzia(n) for n in historico_alvo]
    y_coluna = [extrair_coluna(n) for n in historico_alvo]
    min_len = min(len(X), len(y_duzia), len(y_coluna))
    X = X[:min_len]
    y_duzia = y_duzia[:min_len]
    y_coluna = y_coluna[:min_len]
    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_duzia.fit(X, y_duzia)
    modelo_coluna.fit(X, y_coluna)
    return modelo_duzia, modelo_coluna

def prever_melhor(modelo, historico):
    if len(historico) < 120:
        return []
    X = extrair_features(historico)
    entrada = [X[-1]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas) if i > 0 and p >= PROBABILIDADE_MINIMA],
                  key=lambda x: -x[1])[:1]

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML"
        }, timeout=3)
    except:
        pass

# === INTERFACE STREAMLIT ===

st.set_page_config(page_title="IA Dúzia e Coluna", layout="centered")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")
st.title("🎯 IA Roleta - Dúzia + Coluna")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {
    "referencia": None,
    "duzia": None,
    "coluna": None,
    "resultado_enviado": None
})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

# === API CASINOSCORES ===
try:
    resp = requests.get(API_URL, timeout=3)
    resp.raise_for_status()
    numero_atual = resp.json()["data"]["result"]["outcome"]["number"]
except Exception as e:
    st.error("Erro ao acessar API")
    st.stop()

st.write("🎲 Último número:", numero_atual)

if not historico or numero_atual != historico[-1]:
    historico.append(numero_atual)
    salvar(historico, HISTORICO_PATH)

# === IA: PREVISÃO DÚZIA + COLUNA ===

if len(historico) >= 120 and (not ultimo_alerta["referencia"] or ultimo_alerta["resultado_enviado"] == numero_atual):
    modelo_duzia, modelo_coluna = treinar_modelo(historico)
    duzia = prever_melhor(modelo_duzia, historico)
    coluna = prever_melhor(modelo_coluna, historico)

    melhor_duzia = duzia[0][0] if duzia else None
    melhor_coluna = coluna[0][0] if coluna else None

    if melhor_duzia or melhor_coluna:
        mensagem = "🎯 <b>IA Sugestão</b>:\n"
        if melhor_duzia:
            mensagem += f"📦 Dúzia {melhor_duzia}  "
        if melhor_coluna:
            mensagem += f"📍 Coluna {melhor_coluna}"
        enviar_telegram(mensagem)

        ultimo_alerta.update({
            "referencia": numero_atual,
            "duzia": melhor_duzia,
            "coluna": melhor_coluna,
            "resultado_enviado": None
        })
        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

# === RESULTADO IA ===

if ultimo_alerta["referencia"] and ultimo_alerta["resultado_enviado"] != numero_atual:
    duzia_certa = extrair_duzia(numero_atual)
    coluna_certa = extrair_coluna(numero_atual)
    hit = (
        duzia_certa == ultimo_alerta.get("duzia") or
        coluna_certa == ultimo_alerta.get("coluna")
    )
    resultado = "🟢 GREEN!" if hit else "🔴 RED!"
    st.markdown(f"📈 Resultado: <b>{resultado}</b>", unsafe_allow_html=True)

    if hit:
        contadores["green"] += 1
    else:
        contadores["red"] += 1

    salvar(contadores, CONTADORES_PATH)
    ultimo_alerta["resultado_enviado"] = numero_atual
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

# === MÉTRICAS ===
col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
