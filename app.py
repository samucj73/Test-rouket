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

HISTORICO_PATH = "historico_coluna.json"
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

def salvar_resultado_em_arquivo(novo_historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(novo_historico, f, indent=2)

class ModeloColunaIA:
    def __init__(self, janela=15):
        self.modelo = None
        self.janela = janela
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features_avancadas(self, janela_numeros):
        features = []
        anteriores = janela_numeros[:-1]
        atual = janela_numeros[-1]

        # Features básicas
        for n in janela_numeros:
            grupo = 1 if 1 <= n <= 12 else 2 if 13 <= n <= 24 else 3 if 25 <= n <= 36 else 0
            features.extend([
                n % 2,
                grupo,
                n % 3,
                int(str(n)[-1]),
            ])

        # Features derivadas de coluna e padrão
        col_anteriores = [get_coluna(n) for n in anteriores if n != 0]
        col_atual = get_coluna(atual)

        if anteriores:
            ultimo = anteriores[-1]
            features.append(int(atual == ultimo))  # repetição
            features.append(abs(atual - ultimo))   # variação
        else:
            features.extend([0, 0])

        freq_num = Counter(anteriores)
        freq_col = Counter(col_anteriores)
        terminal_freq = Counter(int(str(n)[-1]) for n in anteriores)

        features.append(freq_num[atual])               # frequência do número
        features.append(freq_col[col_atual])           # frequência da coluna
        features.append(freq_col.get(col_atual, 0))    # coluna quente
        features.append(terminal_freq[int(str(atual)[-1])])  # terminal frequência

        if len(col_anteriores) >= 5:
            features.append(col_anteriores[-1])        # coluna anterior
            moda_5 = Counter(col_anteriores[-5:]).most_common(1)[0][0]
            features.append(moda_5)                    # moda últimos 5
        else:
            features.extend([0, 0])

        return features

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela_n = numeros[i - self.janela:i + 1]
            saida = get_coluna(numeros[i])
            if saida != 0:
                entrada = self.construir_features_avancadas(janela_n)
                X.append(entrada)
                y.append(saida)

        if X:
            X = np.array(X, dtype=np.float32)
            y_enc = self.encoder.fit_transform(y)
            self.modelo = RandomForestClassifier(
                n_estimators=300,
                max_depth=15,
                min_samples_leaf=2,
                random_state=42
            )
            self.modelo.fit(X, y_enc)
            self.treinado = True
            st.write(f"✅ Modelo treinado com {len(X)} entradas.")

    def prever(self, historico):
        if not self.treinado: return None
        numeros = [h["number"] for h in historico if h["number"] is not None and 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1: return None
        janela_n = numeros[-(self.janela + 1):]
        entrada = self.construir_features_avancadas(janela_n)
        proba = self.modelo.predict_proba([entrada])[0]
        coluna_predita = self.encoder.inverse_transform([np.argmax(proba)])[0]
        return coluna_predita

    def coluna_quente(self, historico, ultimos=10):
        numeros = [h["number"] for h in historico if h["number"] is not None and 1 <= h["number"] <= 36]
        colunas = [get_coluna(n) for n in numeros[-ultimos:]]
        if not colunas: return None
        return Counter(colunas).most_common(1)[0][0]

# Interface Streamlit
st.set_page_config(page_title="IA de Coluna Avançada", layout="centered")
st.title("🎯 IA Avançada de Previsão de Coluna - Roleta")

# Sessões
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = ModeloColunaIA()
if "colunas_acertadas" not in st.session_state:
    st.session_state.colunas_acertadas = 0
if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = 0
if "coluna_quente" not in st.session_state:
    st.session_state.coluna_quente = 0

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
                    "timestamp": f"manual_{len(st.session_state.historico)}"
                }
                st.session_state.historico.append(entrada)
                inseridos += 1
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{inseridos} números adicionados.")
    except:
        st.error("Erro ao processar os números inseridos.")

# Autoatualização
st_autorefresh(interval=10000, key="refresh_coluna")

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

# Treinamento e previsão
st.session_state.modelo_coluna.treinar(st.session_state.historico)
coluna = st.session_state.modelo_coluna.prever(st.session_state.historico)
coluna_quente = st.session_state.modelo_coluna.coluna_quente(st.session_state.historico)

st.session_state.coluna_prevista = coluna
st.session_state.coluna_quente = coluna_quente

# Interface
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-10:]))

st.subheader("🔮 Coluna Prevista")
if coluna:
    st.success(f"🧠 IA prevê: Coluna {coluna}")
    st.info(f"🔥 Coluna quente (últimos 10): {coluna_quente}")
    if coluna == coluna_quente:
        st.success("🧠🔥 Alta confiança: IA e padrão quente apontam para a mesma coluna!")
else:
    st.warning("Aguardando mais dados para prever.")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_coluna.janela
if total > 0:
    taxa = st.session_state.colunas_acertadas / total * 100
    st.info(f"✅ Acertos de coluna: {st.session_state.colunas_acertadas} / {total} ({taxa:.2f}%)")
else:
    st.info("🔎 Acertos serão exibidos após mais sorteios.")
