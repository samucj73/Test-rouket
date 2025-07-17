import streamlit as st
import requests
import json
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
CAMINHO_HISTORICO = "historico_roleta.json"
CAMINHO_MODELO = "modelo_roleta_ia.pkl"

# === ORDEM DA ROLETA ===
def extrair_features(janela):
    terminais = [n % 10 for n in janela]
    contagem = Counter(terminais)
    mais_comuns = contagem.most_common(3)
    
    features = {}
    for i in range(10):
        features[f"terminal_{i}"] = terminais.count(i)
    features["terminal_top1"] = mais_comuns[0][0] if len(mais_comuns) > 0 else -1
    features["terminal_top2"] = mais_comuns[1][0] if len(mais_comuns) > 1 else -1
    return features

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

def get_numero_api():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        data = r.json()
        numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        timestamp = data.get("data", {}).get("settledAt")
        if numero is not None and timestamp:
            return {"numero": int(numero), "timestamp": timestamp}
    except Exception as e:
        st.error(f"Erro API: {e}")
    return None

def salvar_historico(historico):
    with open(CAMINHO_HISTORICO, "w") as f:
        json.dump(list(historico), f)

def carregar_historico():
    if os.path.exists(CAMINHO_HISTORICO):
        with open(CAMINHO_HISTORICO, "r") as f:
            return deque(json.load(f), maxlen=100)
    return deque(maxlen=100)

def carregar_modelo():
    if os.path.exists(CAMINHO_MODELO):
        return joblib.load(CAMINHO_MODELO)
    return RandomForestClassifier(n_estimators=100, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, CAMINHO_MODELO)

# === STREAMLIT ===
st.set_page_config("🎯 Estratégia IA Roleta")
st.title("🎯 Estratégia com Inteligência Artificial (IA) - Terminais")

if st.button("🔁 Reiniciar"):
    if os.path.exists(CAMINHO_HISTORICO): os.remove(CAMINHO_HISTORICO)
    if os.path.exists(CAMINHO_MODELO): os.remove(CAMINHO_MODELO)
    st.session_state.historico = deque(maxlen=100)
    st.session_state.resultado_sinais = deque(maxlen=100)
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = {}
    st.rerun()

st_autorefresh(interval=10000, key="auto")

# === ESTADO INICIAL ===
if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()
if "resultado_sinais" not in st.session_state:
    st.session_state.resultado_sinais = deque(maxlen=100)
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []
if "entrada_info" not in st.session_state:
    st.session_state.entrada_info = {}

modelo = carregar_modelo()
resultado = get_numero_api()
if resultado is None:
    st.warning("⏳ Aguardando número da API...")
    st.stop()

# === EVITA REPETIÇÃO ===
novo = False
if not st.session_state.historico or resultado["timestamp"] != st.session_state.historico[-1]["timestamp"]:
    st.session_state.historico.append(resultado)
    salvar_historico(st.session_state.historico)
    novo = True

if not novo:
    st.info("⏳ Aguardando novo sorteio...")
    st.stop()

numero = resultado["numero"]
historico_numeros = [h["numero"] for h in st.session_state.historico]

# === INTERFACE ===
st.subheader("🎰 Últimos Números (15):")
st.write(" | ".join(map(str, historico_numeros[-15:])))

# === IA ===
if len(historico_numeros) >= 14:
    janela = historico_numeros[-14:-2]
    numero_13 = historico_numeros[-2]
    numero_14 = historico_numeros[-1]

    # IA decide entrada
    X = pd.DataFrame([extrair_features(janela)])
    prob = modelo.predict_proba(X)[0][1]

    if prob > 0.65 and not st.session_state.entrada_atual:
        terminais = [n % 10 for n in janela]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]
        entrada = sorted([n for n in range(37) if n % 10 in dominantes])
        st.session_state.entrada_atual = entrada
        st.session_state.entrada_info = {
            "dominantes": dominantes,
            "base": janela,
            "gatilho": numero_13
        }
        enviar_telegram(f"🎯 Entrada IA:\nTerminais: {dominantes}\nNúmeros: {entrada}")

    # Avalia resultado
    if st.session_state.entrada_atual:
        if numero_14 in st.session_state.entrada_atual:
            st.success("✅ GREEN IA!")
            st.session_state.resultado_sinais.append("GREEN")
            y = [1]
        else:
            st.error("❌ RED IA!")
            st.session_state.resultado_sinais.append("RED")
            y = [0]

        # Atualiza modelo
        modelo.fit(X, y)
        salvar_modelo(modelo)
        st.session_state.entrada_atual = []

# === STATUS ===
st.subheader("📊 Histórico de Resultados")
st.write(list(st.session_state.resultado_sinais))

if st.session_state.resultado_sinais:
    st.line_chart([1 if r == "GREEN" else 0 for r in st.session_state.resultado_sinais])
