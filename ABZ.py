import streamlit as st
import requests
import json
import os
import numpy as np
from collections import Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import resample
from streamlit_autorefresh import st_autorefresh

# Configurações
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
HISTORICO_PATH = "historico_abz.json"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# ---------- Classe Modelo ABZ ----------

from sklearn.ensemble import RandomForestClassifier

class ModeloAltoBaixoZero:
    def __init__(self, janela=15):
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False

    def classe_abz(self, n):
        return 0 if n == 0 else 1 if 1 <= n <= 18 else 2

    def construir_features(self, numeros, modo_treinamento=True):
        if len(numeros) < self.janela + (1 if modo_treinamento else 0):
            return None

        anteriores = numeros[:-1] if modo_treinamento else numeros
        atual = numeros[-1] if modo_treinamento else None
        classes = [self.classe_abz(x) for x in anteriores]

        def freq_classe(c, ultimos):
            return ultimos.count(c) / len(ultimos) if ultimos else 0

        freq_0 = freq_classe(0, classes[-self.janela:])
        freq_baixo = freq_classe(1, classes[-self.janela:])
        freq_alto = freq_classe(2, classes[-self.janela:])

        freq5 = [freq_classe(i, classes[-5:]) for i in range(3)]
        freq10 = [freq_classe(i, classes[-10:]) for i in range(3)]
        freq30 = [freq_classe(i, classes[-30:]) for i in range(3)]

        lag1 = classes[-1]
        lag2 = classes[-2] if len(classes) >= 2 else -1
        tendencia = int(np.mean(np.diff(classes[-5:])) > 0) if len(classes) >= 5 else 0

        media = np.mean(anteriores)
        mediana = np.median(anteriores)
        desvio = np.std(anteriores)

        classe_atual = self.classe_abz(atual) if modo_treinamento else -1

        freq20 = sum(1 for x in anteriores[-20:] if self.classe_abz(x) == classe_atual) / 20 if modo_treinamento else 0
        freq50 = sum(1 for x in anteriores[-50:] if self.classe_abz(x) == classe_atual) / 50 if modo_treinamento else 0

        dist = 10
        if modo_treinamento:
            for i in range(len(anteriores) - 1, -1, -1):
                if self.classe_abz(anteriores[i]) == classe_atual:
                    dist = len(anteriores) - 1 - i
                    break

        trocas = sum(1 for i in range(-10, -1) if i > -len(classes) and classes[i] != classes[i + 1])
        repeticoes = 1
        for i in range(len(classes) - 2, -1, -1):
            if classes[i] == classes[i + 1]:
                repeticoes += 1
            else:
                break

        return [
            classe_atual,
            freq_0, freq_baixo, freq_alto,
            *freq5, *freq10, *freq30,
            lag1, lag2, tendencia,
            media, mediana, desvio,
            freq20, freq50, dist,
            trocas, repeticoes
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            feat = self.construir_features(janela, modo_treinamento=True)
            if feat:
                X.append(feat[1:])
                y.append(feat[0])
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y_enc = self.encoder.fit_transform(y)
        Xb, yb = balancear_amostras(X, y_enc)
        self.modelo = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
        self.modelo.fit(Xb, yb)
        self.treinado = True

    def prever(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela:
            return "", 0.0

        anteriores = numeros[-self.janela:]
        entrada = self.construir_features(anteriores, modo_treinamento=False)
        if entrada is None:
            return "", 0.0

        entrada = np.array([entrada[1:]], dtype=np.float32)
        if entrada.shape[1] != self.modelo.n_features_in_:
            return "", 0.0

        proba = self.modelo.predict_proba(entrada)[0]
        idx = np.argmax(proba)
        if idx >= len(self.encoder.classes_):
            return "", 0.0

        classe = self.encoder.inverse_transform([idx])[0]
        mapeamento = {0: "zero", 1: "baixo", 2: "alto"}
        return mapeamento.get(classe, ""), proba[idx]


# ---------- Funções auxiliares ----------
def balancear_amostras(X, y):
    classes = np.unique(y)
    n_max = max([np.sum(y == c) for c in classes])
    Xb, yb = [], []
    for c in classes:
        idx = np.where(y == c)[0]
        X_c, y_c = X[idx], y[idx]
        Xr, yr = resample(X_c, y_c, replace=True, n_samples=n_max, random_state=42)
        Xb.append(Xr)
        yb.append(yr)
    return np.vstack(Xb), np.hstack(yb)

def salvar_resultado(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f)

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH) as f:
            return json.load(f)
    return []

def numero_abz_class(n):
    if n == 0:
        return "zero"
    elif 1 <= n <= 18:
        return "baixo"
    else:
        return "alto"

# ---------- Streamlit App ----------
st.set_page_config("⚡ Previsão ABZ", layout="centered")
st_autorefresh(interval=5000, key="refresh")

st.title("⚡ Previsão Alto / Baixo / Zero (ABZ)")

if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()

if "modelo_abz" not in st.session_state:
    st.session_state.modelo_abz = ModeloAltoBaixoZero(janela=10)
    if len(st.session_state.historico) > 15:
        st.session_state.modelo_abz.treinar(st.session_state.historico)

if "acertos_abz" not in st.session_state:
    st.session_state.acertos_abz = 0

if "ultima_previsao_abz" not in st.session_state:
    st.session_state.ultima_previsao_abz = ("", 0.0)

# ---------- Buscar novo número da API ----------
def buscar_novo_numero():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
            timestamp = data.get("data", {}).get("startedAt")
            if numero is not None and timestamp:
                if all(h["timestamp"] != timestamp for h in st.session_state.historico):
                    st.session_state.historico.append({"number": numero, "timestamp": timestamp})
                    salvar_resultado(st.session_state.historico)

                    esperado = numero_abz_class(numero)
                    previsao = st.session_state.ultima_previsao_abz
                    if isinstance(previsao, (tuple, list)) and len(previsao) == 2:
                        if esperado == previsao[0]:
                            st.session_state.acertos_abz += 1

                    if len(st.session_state.historico) > st.session_state.modelo_abz.janela:
                        st.session_state.modelo_abz.treinar(st.session_state.historico)

    except Exception as e:
        st.warning(f"Erro: {e}")

buscar_novo_numero()

# ---------- Prever ABZ ----------
if st.session_state.modelo_abz.treinado:
    label, conf = st.session_state.modelo_abz.prever(st.session_state.historico)
    st.session_state.ultima_previsao_abz = (label, conf)

    if label:
        st.markdown(f"<h2 style='text-align:center'>{label.upper()}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center'>Confiança: {conf:.2%}</p>", unsafe_allow_html=True)
    else:
        st.info("⚠️ Aguardando dados suficientes para previsão ABZ.")
else:
    st.info("⚠️ Modelo ainda não treinado.")

# ---------- Desempenho ----------
with st.expander("📊 Desempenho"):
    total_abz = len(st.session_state.historico) - st.session_state.modelo_abz.janela
    if total_abz > 0:
        taxa = st.session_state.acertos_abz / total_abz * 100
        st.success(f"Acertos ABZ: {st.session_state.acertos_abz}/{total_abz} ({taxa:.2f}%)")
    else:
        st.info("Aguardando mais dados...")

# ---------- Histórico ----------
with st.expander("📜 Últimos Números"):
    ultimos = [str(h["number"]) for h in st.session_state.historico[-5:]]
    st.code(" | ".join(ultimos))

# ---------- Inserção manual ----------
with st.expander("✍️ Inserir Números Manualmente"):
    entrada = st.text_area("Digite números de 0 a 36 separados por espaço:")
    if st.button("➕ Adicionar"):
        try:
            nums = [int(n) for n in entrada.split() if 0 <= int(n) <= 36]
            for n in nums:
                st.session_state.historico.append({
                    "number": n,
                    "timestamp": f"manual_{len(st.session_state.historico)}"
                })
            salvar_resultado(st.session_state.historico)
            st.success(f"{len(nums)} números adicionados.")
        except:
            st.error("Erro na entrada.")

# ---------- Baixar histórico ----------
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH) as f:
        st.download_button("📥 Baixar Histórico", f.read(), file_name="historico_abz.json")



