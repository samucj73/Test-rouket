import streamlit as st
import requests
import pandas as pd
import joblib
import os
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
from streamlit_autorefresh import st_autorefresh
import numpy as np

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_grandes_numeros.pkl"
MAX_HISTORICO = 300
FREQ_ESPERADA = 1 / 37
N_PREDITOS = 5
PREVER_CADA = 2  # A cada 2 sorteios

# === TELEGRAM CONFIG ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

# === INICIALIZA SESSION STATE ===
if 'historico' not in st.session_state:
    st.session_state.historico = deque(maxlen=MAX_HISTORICO)
if 'ultimo_timestamp' not in st.session_state:
    st.session_state.ultimo_timestamp = None
if 'contador_sorteios' not in st.session_state:
    st.session_state.contador_sorteios = 0
if 'ultima_previsao' not in st.session_state:
    st.session_state.ultima_previsao = []

# === API ===
def obter_ultimo_numero():
    try:
        r = requests.get(API_URL, timeout=5)
        r.raise_for_status()
        data = r.json()['data']
        numero = int(data['outcome']['number'])
        timestamp = data['settledAt']
        return numero, timestamp
    except Exception as e:
        st.error(f"Erro na API: {e}")
        return None, None

# === FEATURE ENGINEERING ===
def calcular_features(historico):
    total = len(historico)
    contagem = Counter(historico)
    features = []
    for n in range(37):
        freq = contagem[n] / total if total > 0 else 0
        erro_convergencia = FREQ_ESPERADA - freq
        ultima_ocorrencia = (
            total - list(historico)[::-1].index(n)
            if n in historico else MAX_HISTORICO
        )
        features.append([n, freq, erro_convergencia, ultima_ocorrencia])
    return pd.DataFrame(features, columns=["numero", "frequencia", "erro", "ultima_ocorrencia"])

def gerar_dataset_para_treinamento(historico):
    dataset = []
    for i in range(30, len(historico) - 1):
        jan = list(historico)[i - 30:i]
        features = calcular_features(jan)
        proximo = historico[i]
        for _, row in features.iterrows():
            amostra = row.copy()
            amostra["alvo"] = 1 if row["numero"] == proximo else 0
            dataset.append(amostra)
    return pd.DataFrame(dataset)

# === MODELO ===
def carregar_ou_treinar_modelo(historico):
    if os.path.exists(MODELO_PATH):
        modelo = joblib.load(MODELO_PATH)
    else:
        modelo = RandomForestClassifier(n_estimators=200, random_state=42)

    try:
        modelo.predict([[0, 0.027, 0, 50]])
    except NotFittedError:
        if len(historico) >= 60:
            df = gerar_dataset_para_treinamento(historico)
            X = df[["numero", "frequencia", "erro", "ultima_ocorrencia"]]
            y = df["alvo"]
            modelo.fit(X, y)
            joblib.dump(modelo, MODELO_PATH)

    return modelo

# === CAPTURA NÚMERO ===
numero, timestamp = obter_ultimo_numero()
if numero is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.historico.append(numero)
    st.session_state.ultimo_timestamp = timestamp
    st.session_state.contador_sorteios += 1

# === PREVISÃO A CADA 2 SORTEIOS ===
nova_previsao = False
top5 = pd.DataFrame()

if st.session_state.contador_sorteios >= PREVER_CADA and len(st.session_state.historico) >= 60:
    modelo = carregar_ou_treinar_modelo(st.session_state.historico)
    features_atuais = calcular_features(st.session_state.historico)
    X_atual = features_atuais[["numero", "frequencia", "erro", "ultima_ocorrencia"]]
    probs = modelo.predict_proba(X_atual)[:, 1]
    features_atuais["probabilidade"] = probs
    top5 = features_atuais.sort_values(by="probabilidade", ascending=False).head(N_PREDITOS)

    # Verifica se é diferente da previsão anterior
    novos_numeros = top5["numero"].tolist()
    if novos_numeros != st.session_state.ultima_previsao:
        st.session_state.ultima_previsao = novos_numeros
        nova_previsao = True
        mensagem = "🎯 *Nova Previsão de Números pela IA (Teoria dos Grandes Números)*:\n"
        mensagem += "\n".join([f"➡️ Número {n}" for n in novos_numeros])
        enviar_telegram(mensagem)

    st.session_state.contador_sorteios = 0

# === INTERFACE STREAMLIT ===
st.title("🎲 IA Roleta - Teoria dos Grandes Números (com Telegram)")
st.write(f"📍 Último número: `{numero}` — Total capturados: `{len(st.session_state.historico)}`")
st.write(f"📡 Nova previsão a cada `{PREVER_CADA}` sorteios")

if not top5.empty:
    st.subheader("🔮 Números previstos:")
    for i, row in top5.iterrows():
        st.markdown(f"**{int(row['numero'])}** — Prob: `{row['probabilidade']:.3f}`")

    st.subheader("📊 Probabilidades estimadas:")
    chart_data = top5.set_index("numero")[["probabilidade"]].sort_index()
    st.bar_chart(chart_data)

# Auto-refresh
st_autorefresh(interval=5000, key="refresh")
