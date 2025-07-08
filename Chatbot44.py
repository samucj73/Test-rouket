import streamlit as st
import requests
import json
import os
import numpy as np
import time
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import resample
from streamlit_autorefresh import st_autorefresh

# 📌 Configurações
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
HISTORICO_PATH = "historico_numeros_top4.json"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
LIMIAR_ALERTA = 0.20  # 20%

st_autorefresh(interval=30_000, limit=None, key="refresh")

# 🧠 Classe IA
class ModeloTopNumerosMelhorado:
    def __init__(self, janela=250, confianca_min=0.1):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_proba = []

    def construir_features(self, numeros):
        if len(numeros) < self.janela + 1:
            return None

        ultimos = numeros[-(self.janela + 1):]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]

        def freq(n, jan): return anteriores[-jan:].count(n) if len(anteriores) >= jan else 0

        freq_10 = freq(atual, 10)
        freq_20 = freq(atual, 20)
        freq_30 = freq(atual, 30)
        freq_50 = freq(atual, 50)
        freq_100 = freq(atual, 100)

        total_100 = max(1, len(anteriores[-100:]))
        rel_freq = freq_100 / total_100

        lag1 = anteriores[-1]
        lag2 = anteriores[-2] if len(anteriores) >= 2 else -1
        lag3 = anteriores[-3] if len(anteriores) >= 3 else -1
        diff_lag = atual - lag1 if lag1 != -1 else 0
        tendencia = int(np.mean(np.diff(anteriores[-5:])) > 0) if len(anteriores) >= 5 else 0

        def get_coluna(n):
            if n == 0: return 0
            elif n % 3 == 1: return 1
            elif n % 3 == 2: return 2
            return 3

        def get_cor(n):
            vermelhos = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
            return 1 if n in vermelhos else 0 if n != 0 else -1

        def get_duzia(n):
            if n == 0: return 0
            elif 1 <= n <= 12: return 1
            elif 13 <= n <= 24: return 2
            return 3

        coluna = get_coluna(atual)
        cor = get_cor(atual)
        duzia = get_duzia(atual)

        coluna_anterior = get_coluna(lag1) if lag1 != -1 else 0
        duzia_anterior = get_duzia(lag1) if lag1 != -1 else 0
        reversao_coluna = int(coluna != coluna_anterior)
        reversao_duzia = int(duzia != duzia_anterior)

        posicoes = [i for i, n in enumerate(reversed(anteriores)) if n == atual]
        dist_ultima_ocorrencia = posicoes[0] if posicoes else len(anteriores)

        top5_freq = [n for n, _ in Counter(anteriores[-50:]).most_common(5)]
        numero_quente = int(atual in top5_freq)
        repetido = int(atual == lag1)
        vizinho = int(abs(atual - lag1) == 1 if lag1 != -1 else 0)

        ultimos_10 = anteriores[-10:]
        media_ultimos = np.mean(ultimos_10) if ultimos_10 else 0
        mediana_ultimos = np.median(ultimos_10) if ultimos_10 else 0
        std_ultimos = np.std(ultimos_10) if ultimos_10 else 0

        return [
            atual, atual % 2, atual % 3, int(str(atual)[-1]),
            freq_10, freq_20, freq_30, freq_50, freq_100,
            rel_freq,
            lag1, lag2, lag3,
            diff_lag, tendencia,
            coluna, duzia, cor,
            coluna_anterior, duzia_anterior,
            reversao_coluna, reversao_duzia,
            dist_ultima_ocorrencia,
            numero_quente, repetido, vizinho,
            media_ultimos, mediana_ultimos, std_ultimos,
            int(atual < 12), int(12 <= atual <= 24), int(atual > 24),
            int(atual in range(1, 19)), int(atual in range(19, 37)),
            int(atual == 0)
        ]

    def treinar(self, historico, max_iter=700, max_depth=14, learning_rate=0.03):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            feat = self.construir_features(janela)
            if feat:
                X.append(feat)
                y.append(numeros[i])
        if not X: return
        X = np.array(X, dtype=np.float32)
        y_enc = self.encoder.fit_transform(y)
        Xb, yb = balancear_amostras(X, y_enc)
        self.modelo = HistGradientBoostingClassifier(
            max_iter=max_iter,
            max_depth=max_depth,
            learning_rate=learning_rate
        )
        self.modelo.fit(Xb, yb)
        self.treinado = True

    def prever_top_n(self, historico, n=4):
        if not self.treinado:
            return []
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1:
            return []
        entrada = self.construir_features(numeros[-(self.janela + 1):])
        if entrada is None:
            return []
        entrada = np.array([entrada], dtype=np.float32)

        if entrada.shape[1] != self.modelo.n_features_in_:
            print(f"❌ Número de features incompatível: esperado {self.modelo.n_features_in_}, recebido {entrada.shape[1]}")
            return []

        proba = self.modelo.predict_proba(entrada)[0]
        self.ultima_proba = proba
        idx_sorted = np.argsort(proba)[::-1]
        top_indices = idx_sorted[:n]
        top_numeros = self.encoder.inverse_transform(top_indices)
        top_probs = proba[top_indices]
        return list(zip(top_numeros, top_probs))


# 📦 Utilitários
def get_duzia(n):
    if n == 0: return None
    elif 1 <= n <= 12: return 1
    elif 13 <= n <= 24: return 2
    return 3

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

def salvar_resultado_em_arquivo(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f)

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH) as f:
            return json.load(f)
    return []

def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        st.warning(f"Erro ao enviar alerta: {e}")

def gerar_hash(historico, janela):
    janela_dados = historico[-janela:] if len(historico) >= janela else historico
    return hash(str(janela_dados))


# 🔄 Atualização
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
                    salvar_resultado_em_arquivo(st.session_state.historico)
                    top4_ant = st.session_state.get("ultimos_top4", [])
                    if numero in top4_ant:
                        st.session_state.acertos_top4 += 1

                    if len(st.session_state.historico) % 5 == 0:
                        novo_hash = gerar_hash(st.session_state.historico, st.session_state.modelo_top4.janela)
                        if novo_hash != st.session_state.get("hash_ultimo_treino"):
                            st.session_state.hash_ultimo_treino = novo_hash
                            st.session_state.modelo_top4.treinar(
                                st.session_state.historico,
                                max_iter=st.session_state.max_iter,
                                max_depth=st.session_state.max_depth,
                                learning_rate=st.session_state.learning_rate
                            )
    except Exception as e:
        st.warning(f"Erro na API: {e}")


# 🚀 Interface
st.set_page_config(page_title="🎯 IA Números Prováveis", layout="centered")
st.title("🔮 IA - Top 4 Números Prováveis")

# 🔧 Config
with st.sidebar:
    st.header("⚙️ IA - Parâmetros")
    janela_ia = st.slider("Janela de Treinamento", 50, 300, 250, step=10)
    confianca_min = st.slider("Confiança Mínima", 0.05, 1.0, 0.1, step=0.05)

    max_iter = st.slider("Max Iterações (épocas)", 100, 1000, 700, step=50)
    max_depth = st.slider("Profundidade Máxima da Árvore", 3, 20, 14)
    learning_rate = st.slider("Taxa de Aprendizado", 0.01, 0.1, 0.03, step=0.01)

    st.session_state.janela_ia = janela_ia
    st.session_state.confianca_min = confianca_min
    st.session_state.max_iter = max_iter
    st.session_state.max_depth = max_depth
    st.session_state.learning_rate = learning_rate

    if st.button("🔁 Re-treinar IA"):
        st.session_state.modelo_top4 = ModeloTopNumerosMelhorado(janela=janela_ia, confianca_min=confianca_min)
        st.session_state.modelo_top4.treinar(
            st.session_state.historico,
            max_iter=max_iter,
            max_depth=max_depth,
            learning_rate=learning_rate
        )
        st.success("IA re-treinada!")

# 🧠 SessionState inicializações
if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()
if "modelo_top4" not in st.session_state:
    janela_ia = st.session_state.get("janela_ia", 250)
    confianca_min = st.session_state.get("confianca_min", 0.1)
    max_iter = st.session_state.get("max_iter", 700)
    max_depth = st.session_state.get("max_depth", 14)
    learning_rate = st.session_state.get("learning_rate", 0.03)
    st.session_state.modelo_top4 = ModeloTopNumerosMelhorado(janela=janela_ia, confianca_min=confianca_min)
    if len(st.session_state.historico) > 260:
        st.session_state.modelo_top4.treinar(
            st.session_state.historico,
            max_iter=max_iter,
            max_depth=max_depth,
            learning_rate=learning_rate
        )
if "acertos_top4" not in st.session_state:
    st.session_state.acertos_top4 = 0
if "ultima_mensagem_enviada_top4" not in st.session_state:
    st.session_state.ultima_mensagem_enviada_top4 = []
if "ultimo_alerta_telegram" not in st.session_state:
    st.session_state.ultimo_alerta_telegram = 0
if "hash_ultimo_treino" not in st.session_state:
    st.session_state.hash_ultimo_treino = None

buscar_novo_numero()

# ✍️ Entrada Manual
with st.expander("✍️ Inserir Manualmente"):
    entrada = st.text_area("Digite números (0 a 36):", height=100)
    if st.button("➕ Adicionar"):
        try:
            nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
            for n in nums:
                st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{len(nums)} números adicionados.")
        except Exception as e:
            st.error(f"Erro: {e}")

# 🎯 Previsão
if st.session_state.modelo_top4.treinado:
    top4 = st.session_state.modelo_top4.prever_top_n(st.session_state.historico)
    st.session_state.ultimos_top4 = [n for n, _ in top4]
    st.subheader("🎯 Números Prováveis (Top 4)")
    if top4:
       col1, col2, col3, col4 = st.columns(4)
       for col, (n, p) in zip([col1, col2, col3, col4], top4):
            with col:
                st.markdown(f"<h1 style='text-align:center; color:#ff4b4b'>{n}</h1>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align:center'>{p:.2%}</p>", unsafe_allow_html=True) 
        
                

        # Enviar alerta apenas se a previsão mudou
        top4_numeros_atuais = [n for n, _ in top4]
        if top4_numeros_atuais != st.session_state.ultima_mensagem_enviada_top4:
            st.session_state.ultima_mensagem_enviada_top4 = top4_numeros_atuais
            linhas_alerta = [f"🎯 {n} com {p:.1%}" for n, p in top4]
            mensagem = "🚨 PREVISÃO TOP 4 NÚMEROS:\n" + "\n".join(linhas_alerta)
            agora = time.time()
            # evita alertas Telegram muito frequentes (ex: 5 minutos)
            if agora - st.session_state.ultimo_alerta_telegram > 300:
                enviar_alerta_telegram(mensagem)
                st.session_state.ultimo_alerta_telegram = agora
    else:
        st.info("Aguardando dados suficientes.")
else:
    st.info("IA ainda não treinada.")

# 📊 Desempenho
with st.expander("📊 Desempenho"):
    total = len(st.session_state.historico) - st.session_state.modelo_top4.janela
    if total > 0:
        taxa = st.session_state.acertos_top4 / total * 100
        st.success(f"🎯 Acertos Top 4: {st.session_state.acertos_top4}/{total} ({taxa:.2f}%)")
    else:
        st.info("Aguardando mais dados para avaliar.")

# 📜 Últimos
with st.expander("📜 Últimos Números"):
    ultimos = [str(h["number"]) for h in st.session_state.historico[-20:]]
    st.code(" | ".join(ultimos), language="text")

# 📥 Download
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH) as f:
        st.download_button("📥 Baixar Histórico", f.read(), file_name="historico_numeros_top4.json")
                                            
