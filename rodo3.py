import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import resample
from streamlit_autorefresh import st_autorefresh
import base64

# 🔊 Som de moedas embutido
som_moedas_base64 = "data:audio/mp3;base64,//uQxAA..."

HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_duzia(n):
    if n == 0: return 0
    if 1 <= n <= 12: return 1
    if 13 <= n <= 24: return 2
    if 25 <= n <= 36: return 3
    return None

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

def estrategia_duzia_quente(historico, janela=130):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    duzias = [get_duzia(n) for n in numeros]
    mais_comum = Counter(duzias).most_common(1)
    return mais_comum[0][0] if mais_comum else None

def estrategia_tendencia(historico):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < 5: return None
    ultimos = numeros[-5:]
    dif = np.mean(np.diff(ultimos))
    if dif > 0: return min(get_duzia(ultimos[-1]) + 1, 3)
    elif dif < 0: return max(get_duzia(ultimos[-1]) - 1, 1)
    else: return get_duzia(ultimos[-1])

def estrategia_alternancia(historico, limite=2):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < limite + 1: return None
    duzias = [get_duzia(n) for n in numeros[-(limite + 1):]]
    if duzias.count(duzias[-1]) >= limite:
        return [d for d in [1, 2, 3] if d != duzias[-1]][0]
    return duzias[-1]

def balancear_amostras(X, y):
    X = np.array(X); y = np.array(y)
    classes = np.unique(y)
    max_len = max([np.sum(y == c) for c in classes])
    X_bal, y_bal = [], []
    for c in classes:
        X_c = X[y == c]; y_c = y[y == c]
        X_res, y_res = resample(X_c, y_c, replace=True, n_samples=max_len, random_state=42)
        X_bal.append(X_res); y_bal.append(y_res)
    return np.concatenate(X_bal), np.concatenate(y_bal)

class ModeloIAHistGB:
    def __init__(self, janela=250, confianca_min=0.4):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_confianca = 0.0

    def construir_features(self, numeros):
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]
        def safe_get_duzia(n): return -1 if n == 0 else get_duzia(n)
        grupo = safe_get_duzia(atual)
        freq_20 = Counter(safe_get_duzia(n) for n in numeros[-20:])
        freq_50 = Counter(safe_get_duzia(n) for n in numeros[-50:]) if len(numeros) >= 150 else freq_20
        total_50 = sum(freq_50.values()) or 1
        lag1 = safe_get_duzia(anteriores[-1]) if len(anteriores) >= 1 else -1
        val1 = anteriores[-1] if len(anteriores) >= 1 else 0
        tendencia = 0
        if len(anteriores) >= 3:
            diffs = np.diff(anteriores[-3:])
            tendencia = int(np.mean(diffs) > 0) - int(np.mean(diffs) < 0)
        zeros_50 = numeros[-50:].count(0)
        porc_zeros = zeros_50 / 50
        densidade_20 = freq_20.get(grupo, 0)
        densidade_50 = freq_50.get(grupo, 0)
        rel_freq_grupo = densidade_50 / total_50
        dist_ultimo_zero = next((i for i, n in enumerate(reversed(numeros)) if n == 0), len(numeros))
        return [
            atual % 2, atual % 3,
            abs(atual - val1), int(atual == val1),
            1 if atual > val1 else -1 if atual < val1 else 0,
            grupo, densidade_20, densidade_50, rel_freq_grupo,
            tendencia, lag1, val1, porc_zeros, dist_ultimo_zero
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            target = get_duzia(numeros[i])
            if target is not None:
                X.append(self.construir_features(janela))
                y.append(target)
        if not X: return
        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))
        X, y = balancear_amostras(X, y)
        self.modelo = HistGradientBoostingClassifier(max_iter=300, max_depth=10, learning_rate=0.05, random_state=42)
        self.modelo.fit(X, y)
        self.treinado = True

    def prever(self, historico):
        if not self.treinado: return None
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1: return None
        janela = numeros[-(self.janela + 1):]
        entrada = np.array([self.construir_features(janela)], dtype=np.float32)
        proba = self.modelo.predict_proba(entrada)[0]
        self.ultima_confianca = max(proba)
        if self.ultima_confianca >= self.confianca_min:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

class ModeloAltoBaixoZero:
    def __init__(self, janela=100, confianca_min=0.4):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_confianca = 0.0

    def _mapear_target(self, n):
        if n == 0: return "zero"
        elif 1 <= n <= 18: return "baixo"
        elif 19 <= n <= 36: return "alto"
        return None

    def _features(self, janela):
        atual = janela[-1]
        anteriores = janela[:-1]
        freq = Counter(janela)
        return [
            atual % 2,
            int(atual in [n for n, _ in freq.most_common(5)]),
            sum(1 for x in anteriores[-5:] if x <= 18) / 5,
            sum(1 for x in anteriores[-5:] if x > 18) / 5,
            anteriores[-1] if len(anteriores) >= 1 else 0
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 10: return
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            jan = numeros[i - self.janela:i + 1]
            target = self._mapear_target(numeros[i])
            if target:
                X.append(self._features(jan))
                y.append(target)
        if not X: return
        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))
        X, y = resample(X, y, random_state=42)
        self.modelo = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.07, random_state=42)
        self.modelo.fit(X, y)
        self.treinado = True

    def prever(self, historico):
        if not self.treinado: return None
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1: return None
        janela = numeros[-(self.janela + 1):]
        entrada = np.array([self._features(janela)], dtype=np.float32)
        proba = self.modelo.predict_proba(entrada)[0]
        self.ultima_confianca = max(proba)
        if self.ultima_confianca >= self.confianca_min:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

  # 🔧 Interface Streamlit
st.set_page_config(page_title="IA Roleta", layout="centered")
st.title("🎯 IA Roleta — Previsão de Dúzia e Alto/Baixo/Zero")

# 🔁 Estados iniciais
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []

if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB()

if "modelo_altobx" not in st.session_state:
    st.session_state.modelo_altobx = ModeloAltoBaixoZero()

if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0

if "acertos_gerais" not in st.session_state:
    st.session_state.acertos_gerais = {"ia": 0, "quente": 0, "tendencia": 0, "alternancia": 0, "altobx": 0}

# ⚙️ Configurações
st.sidebar.header("⚙️ Configurações IA")
janela_ia = st.sidebar.slider("Janela IA Dúzia", 50, 300, 250, step=10)
confianca_min = st.sidebar.slider("Confiança mínima IA", 0.1, 0.9, 0.4, step=0.05)

# 🧠 Treinar IA
st.session_state.modelo_duzia = ModeloIAHistGB(janela=janela_ia, confianca_min=confianca_min)
st.session_state.modelo_duzia.treinar(st.session_state.historico)

st.session_state.modelo_altobx = ModeloAltoBaixoZero(janela=janela_ia, confianca_min=confianca_min)
st.session_state.modelo_altobx.treinar(st.session_state.historico)

# 🔮 Previsões
prev_ia = st.session_state.modelo_duzia.prever(st.session_state.historico)
prev_altobx = st.session_state.modelo_altobx.prever(st.session_state.historico)
prev_quente = estrategia_duzia_quente(st.session_state.historico)
prev_tendencia = estrategia_tendencia(st.session_state.historico)
prev_alternancia = estrategia_alternancia(st.session_state.historico)

# 🧮 Votação para previsão final
votacao = Counter()
for pred in [prev_quente, prev_tendencia, prev_alternancia]:
    if pred is not None: votacao[pred] += 1
mais_votado = votacao.most_common(1)[0][0] if votacao else None
st.session_state.duzia_prevista = mais_votado

# 🛰️ Buscar novo número da API
try:
    response = requests.get(API_URL, headers=HEADERS, timeout=10)
    data = response.json()
    resultado_api = {
        "number": data.get("data", {}).get("result", {}).get("outcome", {}).get("number"),
        "timestamp": data.get("data", {}).get("startedAt")
    }
except Exception as e:
    resultado_api = None
    logging.warning(f"Erro na API: {e}")

# ✅ Novo número detectado
ultimo_timestamp = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado_api and resultado_api["timestamp"] != ultimo_timestamp:
    novo_num = resultado_api["number"]
    st.toast(f"🎲 Novo número: {novo_num}")
    duzia_real = get_duzia(novo_num)

    # ✔️ Verificar acertos
    if duzia_real == prev_ia:
        st.session_state.acertos_gerais["ia"] += 1
    if duzia_real == prev_quente:
        st.session_state.acertos_gerais["quente"] += 1
    if duzia_real == prev_tendencia:
        st.session_state.acertos_gerais["tendencia"] += 1
    if duzia_real == prev_alternancia:
        st.session_state.acertos_gerais["alternancia"] += 1

    faixa_real = "zero" if novo_num == 0 else "baixo" if novo_num <= 18 else "alto"
    if faixa_real == prev_altobx:
        st.session_state.acertos_gerais["altobx"] += 1

    if duzia_real == st.session_state.duzia_prevista:
        st.session_state.duzias_acertadas += 1
        st.balloons()
        st.audio(som_moedas_base64, format="audio/mp3", autoplay=True)

    st.session_state.historico.append(resultado_api)
    salvar_resultado_em_arquivo(st.session_state.historico)

# ✍️ Entrada manual
st.subheader("✍️ Inserir Números Manualmente")
entrada = st.text_area("Números entre 0-36 separados por espaço:", height=100)
if st.button("Adicionar Sorteios"):
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
        salvar_resultado_em_arquivo(st.session_state.historico)
        st.success(f"{len(nums)} números adicionados.")
    except:
        st.error("Erro ao processar entrada.")

# 🔁 Últimos sorteios
st.subheader("🔢 Últimos 10 Números")
ultimos = [str(h["number"]) for h in st.session_state.historico[-10:]]
st.write(" ".join(ultimos))

# 🔮 Previsões
st.subheader("🔮 Previsões Atuais")
st.write(f"🧠 IA Dúzia: {prev_ia} (confiança: {st.session_state.modelo_duzia.ultima_confianca:.2f})")
st.write(f"🎯 Final por votação (quente/tendência/alternância): Dúzia {mais_votado}")
st.write(f"🔥 Quente: {prev_quente} | 📈 Tendência: {prev_tendencia} | 🔁 Alternância: {prev_alternancia}")
st.write(f"⚖️ IA Alto/Baixo/Zero: {prev_altobx} (confiança: {st.session_state.modelo_altobx.ultima_confianca:.2f})")

# 📊 Desempenho
st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_duzia.janela
if total > 0:
    taxa = st.session_state.duzias_acertadas / total * 100
    st.success(f"✅ Acertos da Previsão Final: {st.session_state.duzias_acertadas} / {total} ({taxa:.1f}%)")
else:
    st.info("⏳ Aguarde mais dados para estatísticas.")

# 📌 Acertos por estratégia
st.subheader("📌 Acertos por Estratégia")
for nome, acertos in st.session_state.acertos_gerais.items():
    pct = acertos / total * 100 if total > 0 else 0
    st.write(f"✔️ {nome.upper()}: {acertos} acertos ({pct:.1f}%)")

# ⬇️ Download histórico
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH) as f:
        st.download_button("📥 Baixar Histórico", f.read(), file_name="historico_coluna_duzia.json")

# 🔄 Auto refresh
st_autorefresh(interval=10000, key="refresh")
