import streamlit as st
import requests
import json
import os
import numpy as np
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import resample
from streamlit_autorefresh import st_autorefresh

# Configurações
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
HISTORICO_PATH = "historico_numeros_top4.json"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# --- Modelo Top 4 Números ---

class ModeloTopNumerosMelhorado:
    def __init__(self, janela=100, confianca_min=0.1):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_proba = []

    def construir_features(self, numeros, modo_treinamento=True):
        if len(numeros) < self.janela + (1 if modo_treinamento else 0):
            return None

        anteriores = numeros[:-1] if modo_treinamento else numeros
        atual = numeros[-1] if modo_treinamento else None

        def get_coluna(n): return 0 if n == 0 else (1 if n % 3 == 1 else (2 if n % 3 == 2 else 3))
        def get_cor(n): return 1 if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0 if n != 0 else -1
        def get_duzia(n): return 0 if n == 0 else (1 if n <= 12 else 2 if n <= 24 else 3)

        freq_10 = freq_20 = freq_30 = freq_50 = freq_100 = rel_freq = diff_lag = 0
        coluna = duzia = cor = coluna_anterior = duzia_anterior = reversao_coluna = reversao_duzia = 0
        dist_ultima_ocorrencia = numero_quente = repetido = vizinho = 0
        classe_baixa = classe_media = classe_alta = classe_baixo18 = classe_alto18 = classe_zero = 0

        if modo_treinamento:
            freq_10 = anteriores[-10:].count(atual)
            freq_20 = anteriores[-20:].count(atual)
            freq_30 = anteriores[-30:].count(atual)
            freq_50 = anteriores[-50:].count(atual)
            freq_100 = anteriores[-100:].count(atual)
            rel_freq = freq_100 / max(1, len(anteriores[-100:]))
            diff_lag = atual - anteriores[-1] if anteriores else 0
            coluna = get_coluna(atual)
            duzia = get_duzia(atual)
            cor = get_cor(atual)
            coluna_anterior = get_coluna(anteriores[-1]) if anteriores else 0
            duzia_anterior = get_duzia(anteriores[-1]) if anteriores else 0
            reversao_coluna = int(coluna != coluna_anterior)
            reversao_duzia = int(duzia != duzia_anterior)
            posicoes = [i for i, n in enumerate(reversed(anteriores)) if n == atual]
            dist_ultima_ocorrencia = posicoes[0] if posicoes else len(anteriores)
            top5_freq = [n for n, _ in Counter(anteriores[-50:]).most_common(5)]
            numero_quente = int(atual in top5_freq)
            repetido = int(atual == anteriores[-1])
            vizinho = int(abs(atual - anteriores[-1]) == 1)
            classe_baixa = int(atual < 12)
            classe_media = int(12 <= atual <= 24)
            classe_alta = int(atual > 24)
            classe_baixo18 = int(atual in range(1, 19))
            classe_alto18 = int(atual in range(19, 37))
            classe_zero = int(atual == 0)

        lag1 = anteriores[-1]
        lag2 = anteriores[-2] if len(anteriores) >= 2 else -1
        lag3 = anteriores[-3] if len(anteriores) >= 3 else -1
        tendencia = int(np.mean(np.diff(anteriores[-5:])) > 0) if len(anteriores) >= 5 else 0
        ultimos_10 = anteriores[-10:]
        media_ultimos = np.mean(ultimos_10) if ultimos_10 else 0
        mediana_ultimos = np.median(ultimos_10) if ultimos_10 else 0
        std_ultimos = np.std(ultimos_10) if ultimos_10 else 0

        return [
            0, 0, 0, 0,
            freq_10, freq_20, freq_30, freq_50, freq_100,
            rel_freq, lag1, lag2, lag3, diff_lag, tendencia,
            coluna, duzia, cor, coluna_anterior, duzia_anterior,
            reversao_coluna, reversao_duzia, dist_ultima_ocorrencia,
            numero_quente, repetido, vizinho,
            media_ultimos, mediana_ultimos, std_ultimos,
            classe_baixa, classe_media, classe_alta,
            classe_baixo18, classe_alto18, classe_zero
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            feat = self.construir_features(janela, modo_treinamento=True)
            if feat:
                X.append(feat)
                y.append(numeros[i])
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y_enc = self.encoder.fit_transform(y)
        Xb, yb = balancear_amostras(X, y_enc)
        self.modelo = HistGradientBoostingClassifier(max_iter=700, max_depth=14, learning_rate=0.03)
        self.modelo.fit(Xb, yb)
        self.treinado = True

    def prever_top_n(self, historico, n=4):
        if not self.treinado:
            return []

        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela:
            return []

        anteriores = numeros[-self.janela:]
        entrada = self.construir_features(anteriores, modo_treinamento=False)
        if entrada is None:
            return []

        entrada = np.array([entrada], dtype=np.float32)
        if entrada.shape[1] != self.modelo.n_features_in_:
            return []

        try:
            proba = self.modelo.predict_proba(entrada)[0]
        except Exception:
            return []

        self.ultima_proba = proba
        idx_sorted = np.argsort(proba)[::-1]
        top_indices = idx_sorted[:n]

        valid_indices = [i for i in top_indices if i < len(self.encoder.classes_)]
        if not valid_indices:
            return []

        top_numeros = self.encoder.inverse_transform(valid_indices)
        top_probs = proba[valid_indices]
        return list(zip(top_numeros, top_probs))


    

  # --- Modelo Alto/Baixo/Zero ---

from sklearn.ensemble import RandomForestClassifier

class ModeloAltoBaixoZero:
    def __init__(self, janela=100):
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features(self, numeros, modo_treinamento=True):
        if len(numeros) < self.janela + (1 if modo_treinamento else 0):
            return None

        anteriores = numeros[:-1] if modo_treinamento else numeros
        atual = numeros[-1] if modo_treinamento else None

        def classe_abz(n):
            if n == 0:
                return 0
            elif 1 <= n <= 18:
                return 1
            else:
                return 2

        classes = [classe_abz(x) for x in anteriores]

        # Frequência das classes
        freq_0 = classes.count(0) / self.janela
        freq_baixo = classes.count(1) / self.janela
        freq_alto = classes.count(2) / self.janela

        # Últimos
        lag1 = classes[-1]
        lag2 = classes[-2] if len(classes) >= 2 else -1

        # Tendência
        tendencia = int(np.mean(np.diff(classes[-5:])) > 0) if len(classes) >= 5 else 0

        # Média, mediana, desvio padrão
        media = np.mean(anteriores)
        mediana = np.median(anteriores)
        desvio = np.std(anteriores)

        # Classe atual
        classe_atual = classe_abz(atual) if modo_treinamento else -1

        # Frequência da mesma classe nos últimos 20 e 50
        freq20 = sum(1 for x in anteriores[-20:] if classe_abz(x) == classe_atual) / 20 if modo_treinamento else 0
        freq50 = sum(1 for x in anteriores[-50:] if classe_abz(x) == classe_atual) / 50 if modo_treinamento else 0

        # Distância até última ocorrência da mesma classe
        dist = 100
        if modo_treinamento:
            for i in range(len(anteriores)-1, -1, -1):
                if classe_abz(anteriores[i]) == classe_atual:
                    dist = len(anteriores) - 1 - i
                    break

        # Número de trocas de classe nos últimos 10
        trocas = sum(1 for i in range(-10, -1) if i > -len(classes) and classes[i] != classes[i+1])

        # Repetições consecutivas da mesma classe
        repeticoes = 1
        for i in range(len(classes)-2, -1, -1):
            if classes[i] == classes[i+1]:
                repeticoes += 1
            else:
                break

        return [
            classe_atual,
            freq_0, freq_baixo, freq_alto,
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
                X.append(feat[1:])  # Features
                y.append(feat[0])   # Classe (label)
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y_enc = self.encoder.fit_transform(y)
        Xb, yb = balancear_amostras(X, y_enc)

        self.modelo = RandomForestClassifier(n_estimators=300, max_depth=12, random_state=42)
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

    try:
        proba = self.modelo.predict_proba(entrada)[0]
    except Exception:
        return "", 0.0

    idx = np.argmax(proba)
    if idx >= len(self.encoder.classes_):
        return "", 0.0

    classe = self.encoder.inverse_transform([idx])[0]
    mapeamento = {0: "zero", 1: "baixo", 2: "alto"}
    return mapeamento.get(classe, ""), proba[idx]

    


# --- Funções auxiliares ---
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
    except:
        pass

def numero_abz_class(n):
    if n == 0:
        return "zero"
    elif 1 <= n <= 18:
        return "baixo"
    else:
        return "alto"

  # ---------- Streamlit Configuração ----------
st.set_page_config("🎯 IA Números Prováveis e ABZ", layout="centered")
st_autorefresh(interval=5_000, limit=None, key="refresh")
st.title("🔮 IA - Top 4 Números Prováveis + Previsão Alto/Baixo/Zero")

# ---------- Estado inicial ----------
if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()

if "modelo_top4" not in st.session_state:
    st.session_state.modelo_top4 = ModeloTopNumerosMelhorado(janela=250, confianca_min=0.1)
    if len(st.session_state.historico) > 260:
        st.session_state.modelo_top4.treinar(st.session_state.historico)

if "modelo_abz" not in st.session_state:
    st.session_state.modelo_abz = ModeloAltoBaixoZero(janela=250)
    if len(st.session_state.historico) > 260:
        st.session_state.modelo_abz.treinar(st.session_state.historico)

if "acertos_top4" not in st.session_state:
    st.session_state.acertos_top4 = 0

if "acertos_abz" not in st.session_state:
    st.session_state.acertos_abz = 0

if "ultimos_top4" not in st.session_state:
    st.session_state.ultimos_top4 = []

if "top4_atual" not in st.session_state:
    st.session_state.top4_atual = []

if "ultima_previsao_abz" not in st.session_state:
    st.session_state.ultima_previsao_abz = ""

if "ultima_mensagem_enviada_top4" not in st.session_state:
    st.session_state.ultima_mensagem_enviada_top4 = []

if "ultima_mensagem_enviada_abz" not in st.session_state:
    st.session_state.ultima_mensagem_enviada_abz = ""

if "novo_numero_capturado" not in st.session_state:
    st.session_state.novo_numero_capturado = False

# ---------- Gerar previsões ANTES da chegada do novo número ----------
if st.session_state.modelo_top4.treinado:
    top4 = st.session_state.modelo_top4.prever_top_n(st.session_state.historico)
    st.session_state.ultimos_top4 = [n for n, _ in top4]
    st.session_state.top4_atual = top4
    top4_numeros = [n for n, _ in top4]
    if top4_numeros != st.session_state.ultima_mensagem_enviada_top4:
        st.session_state.ultima_mensagem_enviada_top4 = top4_numeros
        enviar_alerta_telegram("🎯 Top 4 Números: " + " ".join(str(n) for n in top4_numeros))

if st.session_state.modelo_abz.treinado:
    abz_label, abz_conf = st.session_state.modelo_abz.prever(st.session_state.historico)
    st.session_state.ultima_previsao_abz = (abz_label, abz_conf)
    if abz_label != st.session_state.ultima_mensagem_enviada_abz:
        st.session_state.ultima_mensagem_enviada_abz = abz_label
        enviar_alerta_telegram(f"⚡ Previsão ABZ: {abz_label} ({abz_conf:.2%})")

# ---------- Captura novo número da API ----------

def buscar_novo_numero():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
            timestamp = data.get("data", {}).get("startedAt")
            if numero is not None and timestamp:
                # Se for número novo
                if all(h["timestamp"] != timestamp for h in st.session_state.historico):
                    st.session_state.historico.append({"number": numero, "timestamp": timestamp})
                    salvar_resultado_em_arquivo(st.session_state.historico)

                    # ✅ Verificar acertos das previsões anteriores
                    if numero in st.session_state.ultimos_top4:
                        st.session_state.acertos_top4 += 1

                    abz_esperado = numero_abz_class(numero)
                    if isinstance(st.session_state.ultima_previsao_abz, (list, tuple)):
                        if abz_esperado == st.session_state.ultima_previsao_abz[0]:
                            st.session_state.acertos_abz += 1

                    st.session_state.novo_numero_capturado = True

                    # ✅ Re-treinar modelos com o histórico atualizado
                    if len(st.session_state.historico) > st.session_state.modelo_top4.janela:
                        st.session_state.modelo_top4.treinar(st.session_state.historico)
                    if incluir_abz and len(st.session_state.historico) > st.session_state.modelo_abz.janela:
                        st.session_state.modelo_abz.treinar(st.session_state.historico)

    except Exception as e:
        st.warning(f"Erro ao buscar novo número: {e}")

buscar_novo_numero()

# ---------- Inserção manual ----------
with st.expander("✍️ Inserir Manualmente"):
    entrada = st.text_area("Digite números (0 a 36):", height=100)
    if st.button("➕ Adicionar"):
        try:
            nums = [int(n) for n in entrada.split() if 0 <= int(n) <= 36]
            for n in nums:
                st.session_state.historico.append({
                    "number": n,
                    "timestamp": f"manual_{len(st.session_state.historico)}"
                })
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.session_state.novo_numero_capturado = True
            st.success(f"{len(nums)} números adicionados.")
        except:
            st.error("Erro na entrada.")

# ---------- Configurações na sidebar ----------
with st.sidebar:
    st.header("⚙️ IA - Parâmetros")
    janela_ia = st.slider("Janela de Treinamento", 50, 300, 250, step=10)
    confianca_min = st.slider("Confiança Mínima", 0.05, 1.0, 0.1, step=0.05)
    incluir_abz = st.checkbox("Incluir Previsão Alto/Baixo/Zero (ABZ)", value=True)
    if st.button("🔁 Re-treinar IA"):
        st.session_state.modelo_top4 = ModeloTopNumerosMelhorado(janela=janela_ia, confianca_min=confianca_min)
        st.session_state.modelo_top4.treinar(st.session_state.historico)
        if incluir_abz:
            st.session_state.modelo_abz = ModeloAltoBaixoZero(janela=janela_ia)
            st.session_state.modelo_abz.treinar(st.session_state.historico)
        st.success("IA re-treinada!")

# ---------- Exibição Top 4 ----------
st.subheader("🎯 Números Prováveis (Top 4)")
if st.session_state.top4_atual:
    col1, col2, col3, col4 = st.columns(4)
    for col, (n, p) in zip([col1, col2, col3, col4], st.session_state.top4_atual):
        with col:
            st.markdown(f"<h1 style='text-align:center; color:#ff4b4b'>{n}</h1>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align:center'>Confiança: {p:.2%}</p>", unsafe_allow_html=True)
else:
    st.info("⚠️ Aguardando dados suficientes para prever os Top 4.")

# ---------- Exibição Previsão ABZ ----------
if incluir_abz:
    st.subheader("⚡ Previsão Alto / Baixo / Zero (ABZ)")
    abz_range = {"alto": "19–36", "baixo": "1–18", "zero": "0"}

    abz_label, abz_conf = "", 0.0
    if isinstance(st.session_state.ultima_previsao_abz, (tuple, list)) and len(st.session_state.ultima_previsao_abz) == 2:
        abz_label, abz_conf = st.session_state.ultima_previsao_abz

    if abz_label:
        st.markdown(
            f"<h2 style='text-align:center; color:#008000'>{abz_label.title()} "
            f"({abz_range.get(abz_label, '')})</h2>"
            f"<p style='text-align:center'>Confiança: {abz_conf:.2%}</p>",
            unsafe_allow_html=True
        )
    else:
        st.info("⚠️ Aguardando dados suficientes para previsão ABZ.")

# ---------- Desempenho ----------
with st.expander("📊 Desempenho"):
    total_top4 = len(st.session_state.historico) - st.session_state.modelo_top4.janela
    if total_top4 > 0:
        taxa_top4 = st.session_state.acertos_top4 / total_top4 * 100
        st.success(f"🎯 Acertos Top 4: {st.session_state.acertos_top4}/{total_top4} ({taxa_top4:.2f}%)")
    else:
        st.info("Aguardando mais dados para avaliar Top 4.")

    if incluir_abz:
        total_abz = len(st.session_state.historico) - st.session_state.modelo_abz.janela
        if total_abz > 0:
            taxa_abz = st.session_state.acertos_abz / total_abz * 100
            st.success(f"⚡ Acertos ABZ: {st.session_state.acertos_abz}/{total_abz} ({taxa_abz:.2f}%)")
        else:
            st.info("Aguardando mais dados para avaliar ABZ.")

# ---------- Histórico ----------
with st.expander("📜 Últimos Números"):
    ultimos = [str(h["number"]) for h in st.session_state.historico[-5:]]
    st.code(" | ".join(ultimos), language="text")

# ---------- Download ----------
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH) as f:
        st.download_button("📥 Baixar Histórico", f.read(), file_name="historico_numeros_top4.json")

  
