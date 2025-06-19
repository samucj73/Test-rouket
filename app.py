import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
from streamlit_autorefresh import st_autorefresh

# --- Configurações
HISTORICO_PATH = "historico_coluna.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- Funções utilitárias
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

def get_coluna(n):
    return (n - 1) % 3 + 1 if n != 0 else 0

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

def construir_features(janela):
    features = []
    for n in janela:
        features.extend([
            n % 2,
            1 if 1 <= n <= 12 else 2 if 13 <= n <= 24 else 3 if 25 <= n <= 36 else 0,
            n % 3,
            int(str(n)[-1])
        ])
    return features

# --- Modelo IA
class ModeloColunaIA:
    def __init__(self, janela=15):
        self.modelo = None
        self.janela = janela
        self.encoder = LabelEncoder()
        self.treinado = False

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            entrada = construir_features(numeros[i - self.janela:i])
            saida = get_coluna(numeros[i])
            X.append(entrada)
            y.append(saida)
        if X:
            y_enc = self.encoder.fit_transform(y)
            self.modelo = xgb.XGBClassifier(n_estimators=100, use_label_encoder=False, eval_metric="mlogloss")
            self.modelo.fit(np.array(X), y_enc)
            self.treinado = True

    def prever(self, historico):
        if not self.treinado:
            return None
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        if len(numeros) < self.janela:
            return None
        entrada = construir_features(numeros[-self.janela:])
        proba = self.modelo.predict_proba([entrada])[0]
        coluna_predita = self.encoder.inverse_transform([np.argmax(proba)])[0]
        return coluna_predita


# --- Interface Streamlit ---
st.set_page_config(page_title="IA de Coluna - Roleta", layout="centered")
st.title("🎯 Previsão de Coluna da Roleta")

# --- Autorefresh a cada 40 segundos
st_autorefresh(interval=40000, key="auto_refresh")

# --- Sessões
if "historico" not in st.session_state:
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            st.session_state.historico = json.load(f)
    else:
        st.session_state.historico = []

if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = ModeloColunaIA()

if "colunas_acertadas" not in st.session_state:
    st.session_state.colunas_acertadas = 0

if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = 0

# --- Inserção manual
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
                entrada = {"number": numero, "timestamp": f"manual_{len(st.session_state.historico)}"}
                st.session_state.historico.append(entrada)
                inseridos += 1
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{inseridos} números adicionados.")
    except:
        st.error("Erro ao processar os números inseridos.")

# --- Captura novo sorteio automaticamente
resultado = fetch_latest_result()
ultimo = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado and resultado["timestamp"] != ultimo:
    st.session_state.historico.append(resultado)
    salvar_resultado_em_arquivo(st.session_state.historico)
    st.toast(f"🎲 Novo número: {resultado['number']}")
    if get_coluna(resultado["number"]) == st.session_state.coluna_prevista:
        st.session_state.colunas_acertadas += 1
        st.toast("✅ Acertou a coluna!")
    st.stop()  # Atualiza e interrompe execução

# --- Treinamento e previsão
st.session_state.modelo_coluna.treinar(st.session_state.historico)
coluna = st.session_state.modelo_coluna.prever(st.session_state.historico)
st.session_state.coluna_prevista = coluna

# --- Exibição
st.subheader("🔁 Últimos 10 Números")
ultimos = [h["number"] for h in st.session_state.historico[-10:] if h.get("number") is not None]
if ultimos:
    st.write("🎲 " + " ".join(str(n) for n in ultimos))
else:
    st.info("Ainda sem números registrados.")

st.subheader("🔮 Coluna Prevista")
if coluna is not None:
    st.success(f"🧱 Coluna provável: {coluna}")
else:
    st.warning("Aguardando mais dados para prever.")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_coluna.janela
if total > 0:
    taxa = st.session_state.colunas_acertadas / total * 100
    st.info(f"✅ Acertos de coluna: {st.session_state.colunas_acertadas} / {total} ({taxa:.2f}%)")
else:
    st.info("🔎 Acertos serão exibidos após mais sorteios.")
