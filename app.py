import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from streamlit_autorefresh import st_autorefresh

HISTORICO_PATH = "historico_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def get_duzia(n):
    if n == 0:
        return 0
    elif 1 <= n <= 12:
        return 1
    elif 13 <= n <= 24:
        return 2
    elif 25 <= n <= 36:
        return 3
    return None

def salvar_resultado_em_arquivo(novo_historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(novo_historico, f, indent=2)

class ModeloDuziaIA:
    def __init__(self, janela=15):
        self.modelo = None
        self.janela = janela
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features(self, janela_numeros):
        features = []
        anteriores = janela_numeros[:-1]
        atual = janela_numeros[-1]

        grupo = get_duzia(atual)
        features.append(atual % 2)                   # par/ímpar
        features.append(grupo)                       # dúzia
        features.append(atual % 3)                   # módulo 3
        features.append(int(str(atual)[-1]))         # terminal
        features.append(int(atual == anteriores[-1]) if anteriores else 0)  # repetição
        features.append(abs(atual - anteriores[-1]) if anteriores else 0)   # variação

        duzia_freq = Counter(get_duzia(n) for n in anteriores)
        features.append(duzia_freq.get(grupo, 0))     # frequência da dúzia
        features.append(get_duzia(anteriores[-1]) if anteriores else 0)  # dúzia anterior

        return features

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela_n = numeros[i - self.janela:i + 1]
            saida = get_duzia(numeros[i])
            if saida is not None:
                entrada = self.construir_features(janela_n)
                X.append(entrada)
                y.append(saida)

        if X:
            X = np.array(X, dtype=np.float32)
            y_enc = self.encoder.fit_transform(y)
            self.modelo = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
            self.modelo.fit(X, y_enc)
            self.treinado = True
            st.write(f"✅ Modelo de dúzias treinado com {len(X)} entradas.")

    def prever(self, historico):
        if not self.treinado: return None
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1: return None
        janela_n = numeros[-(self.janela + 1):]
        entrada = self.construir_features(janela_n)
        proba = self.modelo.predict_proba([entrada])[0]
        duzia_predita = self.encoder.inverse_transform([np.argmax(proba)])[0]
        return duzia_predita

# --- Streamlit App ---
st.set_page_config(page_title="IA Dúzia da Roleta", layout="centered")
st.title("🎯 IA para Previsão de Dúzia da Roleta")

# Sessões
if "historico_duzia" not in st.session_state:
    st.session_state.historico_duzia = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloDuziaIA()
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None

# Entrada manual
st.subheader("✍️ Inserir até 100 Sorteios Manualmente")
input_numbers = st.text_area("Digite os números separados por espaço:", height=100)

if st.button("Adicionar Sorteios Manuais"):
    try:
        nums = [int(n) for n in input_numbers.split() if n.isdigit() and 0 <= int(n) <= 36]
        if len(nums) > 100:
            st.warning("Você só pode inserir até 100 números.")
        else:
            inseridos = 0
            for numero in nums:
                entrada = {
                    "number": numero,
                    "timestamp": f"manual_{len(st.session_state.historico_duzia)}"
                }
                st.session_state.historico_duzia.append(entrada)
                inseridos += 1
            salvar_resultado_em_arquivo(st.session_state.historico_duzia)
            st.success(f"{inseridos} números adicionados.")
    except:
        st.error("Erro ao processar os números inseridos.")

# Autoatualização
st_autorefresh(interval=10000, key="refresh_duzia")

# Captura
resultado = fetch_latest_result()
ultimo = st.session_state.historico_duzia[-1]["timestamp"] if st.session_state.historico_duzia else None

if resultado and resultado["timestamp"] != ultimo:
    st.session_state.historico_duzia.append(resultado)
    salvar_resultado_em_arquivo(st.session_state.historico_duzia)
    st.toast(f"🎲 Novo número: {resultado['number']}")
    if get_duzia(resultado["number"]) == st.session_state.duzia_prevista:
        st.session_state.duzias_acertadas += 1
        st.toast("✅ Acertou a dúzia!")

# Treinamento e previsão
st.session_state.modelo_duzia.treinar(st.session_state.historico_duzia)
duzia = st.session_state.modelo_duzia.prever(st.session_state.historico_duzia)
st.session_state.duzia_prevista = duzia

# Interface
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico_duzia[-10:]))

st.subheader("🔮 Dúzia Prevista")
if duzia == 0:
    st.warning("🟢 Zero pode aparecer!")
elif duzia:
    st.success(f"🧠 Dúzia provável: {duzia}ª")
else:
    st.warning("Aguardando mais dados para prever.")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico_duzia) - st.session_state.modelo_duzia.janela
if total > 0:
    taxa = st.session_state.duzias_acertadas / total * 100
    st.info(f"✅ Acertos de dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa:.2f}%)")
else:
    st.info("🔎 Acertos serão exibidos após mais sorteios.")
