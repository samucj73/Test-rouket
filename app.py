import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from streamlit_autorefresh import st_autorefresh

HISTORICO_PATH = "historico_coluna_duzia.json"
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

class ModeloIAOtimizada:
    def __init__(self, tipo="coluna", janela=15):
        self.tipo = tipo
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features(self, numeros):
        features = []
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]

        # Features comuns
        features.append(atual % 2)  # par/ímpar
        features.append(int(str(atual)[-1]))  # terminal
        features.append(atual % 3)  # módulo 3
        features.append(abs(atual - anteriores[-1]) if anteriores else 0)  # variação
        features.append(int(atual == anteriores[-1]) if anteriores else 0)  # repetição
        features.append(1 if atual > anteriores[-1] else -1 if atual < anteriores[-1] else 0)  # tendência

        # Frequência em janela recente
        freq_range = numeros[-20:] if len(numeros) >= 20 else numeros
        if self.tipo == "coluna":
            grupo = get_coluna(atual)
            freq = Counter(get_coluna(n) for n in freq_range)
        else:
            grupo = get_duzia(atual)
            freq = Counter(get_duzia(n) for n in freq_range)

        features.append(freq.get(grupo, 0))  # frequência da coluna ou dúzia
        features.append(grupo)  # grupo atual
        features.append(grupo == (get_coluna(anteriores[-1]) if self.tipo == "coluna" else get_duzia(anteriores[-1])))  # repetição grupo

        return features

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            alvo = get_coluna(numeros[i]) if self.tipo == "coluna" else get_duzia(numeros[i])
            if alvo is not None:
                X.append(self.construir_features(janela))
                y.append(alvo)
        if X:
            y_enc = self.encoder.fit_transform(y)
            self.modelo = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, use_label_encoder=False, eval_metric="mlogloss")
            self.modelo.fit(np.array(X), y_enc)
            self.treinado = True

    def prever(self, historico):
        if not self.treinado:
            return None
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1:
            return None
        janela = numeros[-(self.janela + 1):]
        entrada = self.construir_features(janela)
        proba = self.modelo.predict_proba([entrada])[0]
        confianca = max(proba)
        if confianca >= 0.4:
            classe = self.encoder.inverse_transform([np.argmax(proba)])[0]
            return classe
        return None

# --- Streamlit App ---
st.set_page_config(page_title="IA de Roleta Otimizada", layout="centered")
st.title("🎯 IA Otimizada: Coluna + Dúzia (com Zero)")

# Sessões
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = ModeloIAOtimizada("coluna")
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAOtimizada("duzia")
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
st_autorefresh(interval=10000, key="refresh_otimizado")

# Captura de novo sorteio
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

coluna = st.session_state.modelo_coluna.prever(st.session_state.historico)
duzia = st.session_state.modelo_duzia.prever(st.session_state.historico)

st.session_state.coluna_prevista = coluna
st.session_state.duzia_prevista = duzia

# Exibição
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-10:]))

st.subheader("🔮 Previsões")
if coluna:
    st.success(f"🧱 Coluna provável: {coluna}")
if duzia == 0:
    st.warning("🟢 Zero pode aparecer!")
elif duzia:
    st.info(f"🎯 Dúzia provável: {duzia}ª")

st.subheader("📊 Desempenho da IA")
total = len(st.session_state.historico) - st.session_state.modelo_coluna.janela
if total > 0:
    taxa_c = st.session_state.colunas_acertadas / total * 100
    taxa_d = st.session_state.duzias_acertadas / total * 100
    st.success(f"✅ Acertos de coluna: {st.session_state.colunas_acertadas} / {total} ({taxa_c:.2f}%)")
    st.success(f"✅ Acertos de dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa_d:.2f}%)")
else:
    st.info("🔎 Aguardando mais dados para calcular acertos.")
