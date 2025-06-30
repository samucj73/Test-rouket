import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from streamlit_autorefresh import st_autorefresh
import base64

HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def tocar_som_moeda():
    som_base64 = "SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjI2LjEwNAAAAAAAAAAAAAAA//tQxAADBQABVAAAAnEAAACcQAAAAAAAAAAAAAAAA..."  # encurtado
    st.markdown(f"""<audio autoplay><source src="data:audio/mp3;base64,{som_base64}" type="audio/mp3"></audio>""", unsafe_allow_html=True)

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
    if n == 0: return 0
    elif 1 <= n <= 12: return 1
    elif 13 <= n <= 24: return 2
    elif 25 <= n <= 36: return 3
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
    return min(get_duzia(ultimos[-1]) + 1, 3) if dif > 0 else max(get_duzia(ultimos[-1]) - 1, 1) if dif < 0 else get_duzia(ultimos[-1])

def estrategia_alternancia(historico, limite=2):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < limite + 1: return None
    duzias = [get_duzia(n) for n in numeros[-(limite + 1):]]
    if duzias.count(duzias[-1]) >= limite:
        return [d for d in [1, 2, 3] if d != duzias[-1]][0]
    return duzias[-1]

def estrategia_duzia_ausente(historico):
    ocorrencias = {1: None, 2: None, 3: None}
    for i in reversed(range(len(historico))):
        d = get_duzia(historico[i]["number"])
        if d in ocorrencias and ocorrencias[d] is None:
            ocorrencias[d] = i
        if all(v is not None for v in ocorrencias.values()): break
    return max(ocorrencias.items(), key=lambda x: x[1])[0] if ocorrencias else None

class ModeloIAHistGB:
    def __init__(self, tipo="duzia", janela=250):
        self.tipo = tipo
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False

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
        lag2 = safe_get_duzia(anteriores[-2]) if len(anteriores) >= 2 else -1
        lag3 = safe_get_duzia(anteriores[-3]) if len(anteriores) >= 3 else -1
        val1 = anteriores[-1] if len(anteriores) >= 1 else 0
        val2 = anteriores[-2] if len(anteriores) >= 2 else 0
        val3 = anteriores[-3] if len(anteriores) >= 3 else 0
        tendencia = 0
        if len(anteriores) >= 3:
            diffs = np.diff(anteriores[-3:])
            tendencia = int(np.mean(diffs) > 0) - int(np.mean(diffs) < 0)
        zeros_50 = numeros[-50:].count(0)
        porc_zeros = zeros_50 / 50
        densidade_20 = freq_20.get(grupo, 0)
        densidade_50 = freq_50.get(grupo, 0)
        rel_freq_grupo = densidade_50 / total_50
        repete_duzia = int(grupo == safe_get_duzia(anteriores[-1])) if anteriores else 0
        return [atual % 2, atual % 3, int(str(atual)[-1]),
                abs(atual - anteriores[-1]) if anteriores else 0,
                int(atual == anteriores[-1]) if anteriores else 0,
                1 if atual > anteriores[-1] else -1 if atual < anteriores[-1] else 0,
                sum(1 for x in anteriores[-3:] if grupo == safe_get_duzia(x)),
                Counter(numeros[-30:]).get(atual, 0),
                int(atual in [n for n, _ in Counter(numeros[-30:]).most_common(5)]),
                int(np.mean(anteriores) < atual),
                int(atual == 0), grupo,
                densidade_20, densidade_50, rel_freq_grupo,
                repete_duzia, tendencia, lag1, lag2, lag3,
                val1, val2, val3, porc_zeros]

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
        self.modelo = HistGradientBoostingClassifier(max_iter=200, max_depth=7, random_state=42)
        self.modelo.fit(X, y)
        self.treinado = True

    def prever(self, historico):
        if not self.treinado: return None
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1: return None
        janela = numeros[-(self.janela + 1):]
        entrada = np.array([self.construir_features(janela)], dtype=np.float32)
        proba = self.modelo.predict_proba(entrada)[0]
        min_conf = st.session_state.config.get("min_confianca_ia", 0.4)
        if max(proba) >= min_conf:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

def plotar_grafico_acertos(previsoes, grupo=10):
    acertos = [1 if p["Acertou"] == "✅" else 0 for p in previsoes]
    blocos = [sum(acertos[i:i+grupo]) for i in range(0, len(acertos), grupo)]
    labels = [f"{i+1}-{i+grupo}" for i in range(0, len(acertos), grupo)]
    fig, ax = plt.subplots()
    ax.bar(labels, blocos, color="green")
    ax.set_title(f"Acertos da IA por blocos de {grupo}")
    ax.set_xlabel("Blocos de sorteios")
    ax.set_ylabel("Acertos")
    plt.xticks(rotation=45)
    st.pyplot(fig)

# Streamlit UI
st.set_page_config(page_title="IA Roleta Dúzia", layout="centered")
st.title("🎯 IA Roleta XXXtreme — Previsão de Dúzia")

# Painel de configurações
with st.expander("⚙️ Configurações Avançadas"):
    janela_ia = st.slider("Tamanho da janela de treino da IA", 50, 500, 250, 10)
    janela_quente = st.slider("Janela para estratégia quente", 10, 300, 130, 10)
    limite_alternancia = st.slider("Limite de alternância", 1, 5, 2)
    min_conf = st.slider("Confiança mínima da IA", 0.1, 1.0, 0.4, 0.05)
    st.markdown("### 🗳️ Pesos de Votação")
    peso_ia = st.slider("Peso IA", 0, 5, 3)
    peso_quente = st.slider("Peso Quente", 0, 5, 1)
    peso_tend = st.slider("Peso Tendência", 0, 5, 1)
    peso_alt = st.slider("Peso Alternância", 0, 5, 1)
    peso_ausente = st.slider("Peso Ausente", 0, 5, 1)

# Estado
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "historico_previsoes" not in st.session_state:
    st.session_state.historico_previsoes = []
if "config" not in st.session_state:
    st.session_state.config = {}
st.session_state.config.update({
    "janela_ia": janela_ia,
    "janela_quente": janela_quente,
    "limite_alternancia": limite_alternancia,
    "min_confianca_ia": min_conf,
    "peso_ia": peso_ia,
    "peso_quente": peso_quente,
    "peso_tendencia": peso_tend,
    "peso_alternancia": peso_alt,
    "peso_ausente": peso_ausente
})
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB(janela=janela_ia)
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "ultimo_treino" not in st.session_state:
    st.session_state.ultimo_treino = 0

def tentar_treinar():
    historico = st.session_state.historico
    modelo = st.session_state.modelo_duzia
    if len(historico) >= modelo.janela:
        if len(historico) > st.session_state.ultimo_treino:
            modelo.treinar(historico)
            st.session_state.ultimo_treino = len(historico)
            st.toast(f"🧠 Modelo treinado com {len(historico)} resultados.")

# Entrada manual
st.subheader("✍️ Inserir Sorteios Manualmente")
entrada = st.text_area("Digite os números (até 100, separados por espaço):", height=100)
if st.button("Adicionar Sorteios"):
    numeros = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
    for n in numeros:
        st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
    salvar_resultado_em_arquivo(st.session_state.historico)
    st.success(f"{len(numeros)} números adicionados.")
    tentar_treinar()

# Atualização automática
st_autorefresh(interval=10000, key="refresh_duzia")
resultado = fetch_latest_result()
ultimo = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado and resultado["timestamp"] != ultimo:
    previsao = st.session_state.modelo_duzia.prever(st.session_state.historico)
    st.session_state.duzia_prevista = previsao
    st.session_state.historico.append(resultado)
    salvar_resultado_em_arquivo(st.session_state.historico)
    tentar_treinar()
    real = get_duzia(resultado["number"])
    if previsao == real:
        st.session_state.duzias_acertadas += 1
        st.toast("✅ Acertou a dúzia!")
        st.balloons()
        tocar_som_moeda()
    st.session_state.historico_previsoes.append({
        "Prevista": previsao, "Real": real,
        "Acertou": "✅" if previsao == real else "❌"
    })

# Estratégias
prev_quente = estrategia_duzia_quente(st.session_state.historico, st.session_state.config["janela_quente"])
prev_tend = estrategia_tendencia(st.session_state.historico)
prev_alt = estrategia_alternancia(st.session_state.historico, st.session_state.config["limite_alternancia"])
prev_aus = estrategia_duzia_ausente(st.session_state.historico)
prev_ia = st.session_state.duzia_prevista

# Votação com pesos
cfg = st.session_state.config
votos = [prev_ia]*cfg["peso_ia"] + [prev_quente]*cfg["peso_quente"] + [prev_tend]*cfg["peso_tendencia"] + [prev_alt]*cfg["peso_alternancia"] + [prev_aus]*cfg["peso_ausente"]
votacao = Counter(votos)
mais_votado, _ = votacao.most_common(1)[0]
st.session_state.duzia_prevista = mais_votado

# Interface
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-10:]))

with open(HISTORICO_PATH, "r") as f:
    st.download_button("📥 Baixar histórico", f.read(), "historico_coluna_duzia.json")

st.subheader("🔮 Previsões por Estratégia")
st.write(f"🧠 IA: {prev_ia}")
st.write(f"🔥 Quente: {prev_quente}")
st.write(f"📈 Tendência: {prev_tend}")
st.write(f"🔁 Alternância: {prev_alt}")
st.write(f"🕳️ Ausente: {prev_aus}")
st.success(f"🎯 Previsão final (votação): Dúzia {mais_votado}")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_duzia.janela
if total > 0:
    taxa = st.session_state.duzias_acertadas / total * 100
    st.success(f"✅ Acertos de dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa:.2f}%)")
    if len(st.session_state.historico_previsoes) >= 10:
        st.subheader("📈 Gráfico de Acertos")
        plotar_grafico_acertos(st.session_state.historico_previsoes, grupo=10)
else:
    st.info("🔎 Aguardando mais dados para avaliar desempenho.")
