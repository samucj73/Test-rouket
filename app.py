import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from streamlit_autorefresh import st_autorefresh

# --- Configurações ---
HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- Funções auxiliares ---
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

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

# --- Classe de IA usando HistGradientBoosting ---
class ModeloIAHistGB:
    def __init__(self, tipo="coluna", janela=15):
        self.tipo = tipo
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features(self, numeros):
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]
        features = [
            atual % 2,
            int(str(atual)[-1]),
            atual % 3,
            abs(atual - anteriores[-1]) if anteriores else 0,
            int(atual == anteriores[-1]) if anteriores else 0,
            1 if atual > anteriores[-1] else -1 if atual < anteriores[-1] else 0,
        ]

        freq_range = numeros[-20:] if len(numeros) >= 20 else numeros
        grupo = get_coluna(atual) if self.tipo == "coluna" else get_duzia(atual)
        freq = Counter(get_coluna(n) if self.tipo == "coluna" else get_duzia(n) for n in freq_range)
        features.append(freq.get(grupo, 0))
        features.append(grupo)
        features.append(1 if anteriores and grupo == (get_coluna(anteriores[-1]) if self.tipo == "coluna" else get_duzia(anteriores[-1])) else 0)

        return features

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            target = get_coluna(numeros[i]) if self.tipo == "coluna" else get_duzia(numeros[i])
            if target is not None:
                X.append(self.construir_features(janela))
                y.append(target)
        if X:
            X = np.array(X, dtype=np.float32)
            y = self.encoder.fit_transform(y)
            self.modelo = HistGradientBoostingClassifier(max_iter=200, max_depth=5, random_state=42)
            self.modelo.fit(X, y)
            self.treinado = True

    def prever(self, historico):
        if not self.treinado:
            return None
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1:
            return None
        janela = numeros[-(self.janela + 1):]
        entrada = np.array([self.construir_features(janela)], dtype=np.float32)
        proba = self.modelo.predict_proba(entrada)[0]
        if max(proba) >= 0.4:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

# --- Streamlit App ---
st.set_page_config(page_title="IA Roleta (HistGB)", layout="centered")
st.title("🎯 IA Roleta com HistGradientBoosting")

# Sessões
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = ModeloIAHistGB("coluna")
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB("duzia")
if "colunas_acertadas" not in st.session_state:
    st.session_state.colunas_acertadas = 0
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = None
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None

# Entrada manual
st.subheader("✍️ Inserir até 100 Sorteios Manualmente")
entrada = st.text_area("Digite os números separados por espaço:", height=100)
if st.button("Adicionar Sorteios Manuais"):
    try:
        numeros = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        if len(numeros) > 100:
            st.warning("Limite de 100 números.")
        else:
            for n in numeros:
                st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{len(numeros)} números adicionados.")
    except:
        st.error("Erro ao processar os números.")

# Atualização automática
st_autorefresh(interval=10000, key="refresh_histgb")

# Captura automática
resultado = fetch_latest_result()
ultimo = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None
if resultado and resultado["timestamp"] != ultimo:
    st.session_state.historico.append(resultado)
    salvar_resultado_em_arquivo(st.session_state.historico)
    st.toast(f"🎲 Novo número: {resultado['number']}")
    if get_coluna(resultado["number"]) == st.session_state.coluna_prevista:
        st.session_state.colunas_acertadas += 1
        st.toast("✅ Acertou a coluna!")
    if get_duzia(resultado["number"]) == st.session_state.duzia_prevista:
        st.session_state.duzias_acertadas += 1
        st.toast("✅ Acertou a dúzia!")

# Treinamento e previsão
st.session_state.modelo_coluna.treinar(st.session_state.historico)
st.session_state.modelo_duzia.treinar(st.session_state.historico)

st.session_state.coluna_prevista = st.session_state.modelo_coluna.prever(st.session_state.historico)
st.session_state.duzia_prevista = st.session_state.modelo_duzia.prever(st.session_state.historico)

# Interface
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-10:]))

st.subheader("🔮 Previsões")
if st.session_state.coluna_prevista:
    st.success(f"🧱 Coluna provável: {st.session_state.coluna_prevista}")
if st.session_state.duzia_prevista == 0:
    st.warning("🟢 Zero pode aparecer!")
elif st.session_state.duzia_prevista:
    st.info(f"🎯 Dúzia provável: {st.session_state.duzia_prevista}ª")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_coluna.janela
if total > 0:
    taxa_c = st.session_state.colunas_acertadas / total * 100
    taxa_d = st.session_state.duzias_acertadas / total * 100
    st.success(f"✅ Acertos de coluna: {st.session_state.colunas_acertadas} / {total} ({taxa_c:.2f}%)")
    st.success(f"✅ Acertos de dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa_d:.2f}%)")
else:
    st.info("🔎 Aguardando mais dados para avaliar desempenho.")
