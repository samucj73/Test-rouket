import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import base64
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import resample
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from streamlit_autorefresh import st_autorefresh

if "acertos_gerais" not in st.session_state:
    st.session_state.acertos_gerais = {
        "ia": 0, "quente": 0, "tendencia": 0, "alternancia": 0, "altobx": 0
    }

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

def get_baixo_alto_zero(n):
    if n == 0: return "zero"
    return "baixo" if n <= 18 else "alto"

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
        self.historico_confs = []

    def construir_features(self, numeros):
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]

        def safe_get_duzia(n):
            return -1 if n == 0 else get_duzia(n)

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

        dist_ultimo_zero = next((i for i, n in enumerate(reversed(numeros)) if n == 0), len(numeros))
        mudanca_duzia = int(safe_get_duzia(atual) != safe_get_duzia(val1)) if len(anteriores) >= 1 else 0

        repeticoes_duzia = 0
        for n in reversed(anteriores):
            if safe_get_duzia(n) == grupo:
                repeticoes_duzia += 1
            else:
                break

        ultimos_10 = [n for n in numeros[-10:] if n > 0]
        quente_10 = Counter(safe_get_duzia(n) for n in ultimos_10).most_common(1)
        duzia_quente_10 = quente_10[0][0] if quente_10 else -1

        repetiu_numero = int(atual == val1) if len(anteriores) >= 1 else 0
        vizinho = int(abs(atual - val1) <= 2) if len(anteriores) >= 1 else 0

        if atual in range(1, 10): quadrante_roleta = 0
        elif atual in range(10, 19): quadrante_roleta = 1
        elif atual in range(19, 28): quadrante_roleta = 2
        elif atual in range(28, 37): quadrante_roleta = 3
        else: quadrante_roleta = -1

        top5_freq = [n for n, _ in Counter(numeros).most_common(5)]
        numero_frequente = int(atual in top5_freq)

        grupos_seis = [range(1,7), range(7,13), range(13,19), range(19,25), range(25,31), range(31,37)]
        densidade_por_faixa = [sum(1 for n in numeros[-20:] if n in faixa) for faixa in grupos_seis]

        reversao_tendencia = 0
        if len(anteriores) >= 4:
            diffs1 = np.mean(np.diff(anteriores[-4:-1]))
            diffs2 = atual - val1
            reversao_tendencia = int((diffs1 > 0 and diffs2 < 0) or (diffs1 < 0 and diffs2 > 0))

        coluna_atual = get_duzia(atual)
        coluna_anterior = get_duzia(val1) if val1 else -1
        subida_coluna = int(coluna_atual == coluna_anterior + 1) if coluna_anterior > 0 else 0
        descida_coluna = int(coluna_atual == coluna_anterior - 1) if coluna_anterior > 0 else 0
        repeticao_ou_vizinho = int((atual == val1) or (abs(atual - val1) == 1)) if val1 else 0

        par = int(atual % 2 == 0)
        vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        cor = int(atual in vermelhos)

        return [
            atual % 2, atual % 3, int(str(atual)[-1]),
            abs(atual - val1) if anteriores else 0,
            int(atual == val1) if anteriores else 0,
            1 if atual > val1 else -1 if atual < val1 else 0,
            sum(1 for x in anteriores[-3:] if grupo == safe_get_duzia(x)),
            Counter(numeros[-30:]).get(atual, 0),
            int(atual in [n for n, _ in Counter(numeros[-30:]).most_common(5)]),
            int(np.mean(anteriores) < atual),
            int(atual == 0),
            grupo,
            densidade_20, densidade_50, rel_freq_grupo,
            repete_duzia, tendencia, lag1, lag2, lag3,
            val1, val2, val3, porc_zeros,
            dist_ultimo_zero, mudanca_duzia, repeticoes_duzia,
            duzia_quente_10, repetiu_numero, vizinho,
            quadrante_roleta, numero_frequente,
            *densidade_por_faixa,
            reversao_tendencia,
            subida_coluna,
            descida_coluna,
            repeticao_ou_vizinho,
            par,
            cor
        ]
        class ModeloIAHistGB:
            def __init__(self, janela=100, confianca_min=0.5):
                self.janela = janela
                self.confianca_min = confianca_min
        self.modelo = HistGradientBoostingClassifier()
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features(self, janela):
        features = []
        ultimos = janela[-self.janela:]

        # Exemplo de features simples (você pode expandir com mais de 40 depois)
        media = np.mean(ultimos)
        desvio = np.std(ultimos)
        zeros = ultimos.count(0)
        ult = ultimos[-1]

        features.extend([media, desvio, zeros, ult])
        return features

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []

        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            target = get_duzia(numeros[i])
            if target is not None:
                X.append(self.construir_features(janela))
                y.append(target)

        if not X or len(set(y)) < 2:
            print("❌ Dados insuficientes ou apenas uma classe em y.")
            return

        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))

        # Função externa para balancear classes
        X, y = balancear_amostras(X, y)

        if len(X) < 10:
            print("❌ Muito poucos dados após balanceamento. Treinamento cancelado.")
            return

        self.modelo.fit(X, y)
        self.treinado = True

    def prever(self, janela):
        if not self.treinado:
            return None

        features = self.construir_features(janela)
        X = np.array([features], dtype=np.float32)
        probs = self.modelo.predict_proba(X)[0]
        pred = self.modelo.predict(X)[0]
        conf = max(probs)

        if conf < self.confianca_min:
            return None

        return self.encoder.inverse_transform([pred])[0], conf
        

class ModeloAltoBaixoZero:
    def __init__(self, janela=250, confianca_min=0.4):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_confianca = 0.0
        self.historico_confs = []

    def construir_features(self, numeros):
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]

        def safe_get_baz(n):
            return -1 if n == 0 else get_baixo_alto_zero(n)

        grupo = safe_get_baz(atual)
        freq_20 = Counter(safe_get_baz(n) for n in numeros[-20:])
        freq_50 = Counter(safe_get_baz(n) for n in numeros[-50:]) if len(numeros) >= 150 else freq_20
        total_50 = sum(freq_50.values()) or 1

        lag1 = safe_get_baz(anteriores[-1]) if len(anteriores) >= 1 else -1
        lag2 = safe_get_baz(anteriores[-2]) if len(anteriores) >= 2 else -1
        lag3 = safe_get_baz(anteriores[-3]) if len(anteriores) >= 3 else -1

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
        repete_baz = int(grupo == safe_get_baz(anteriores[-1])) if anteriores else 0

        dist_ultimo_zero = next((i for i, n in enumerate(reversed(numeros)) if n == 0), len(numeros))
        mudanca_baz = int(safe_get_baz(atual) != safe_get_baz(val1)) if len(anteriores) >= 1 else 0

        repeticoes_baz = 0
        for n in reversed(anteriores):
            if safe_get_baz(n) == grupo:
                repeticoes_baz += 1
            else:
                break

        ultimos_10 = [n for n in numeros[-10:] if n > 0]
        quente_10 = Counter(safe_get_baz(n) for n in ultimos_10).most_common(1)
        baz_quente_10 = quente_10[0][0] if quente_10 else -1

        repetiu_numero = int(atual == val1) if len(anteriores) >= 1 else 0
        vizinho = int(abs(atual - val1) <= 2) if len(anteriores) >= 1 else 0

        reversao_tendencia = 0
        if len(anteriores) >= 4:
            diffs1 = np.mean(np.diff(anteriores[-4:-1]))
            diffs2 = atual - val1
            reversao_tendencia = int((diffs1 > 0 and diffs2 < 0) or (diffs1 < 0 and diffs2 > 0))

        coluna_atual = get_duzia(atual)
        coluna_anterior = get_duzia(val1) if val1 else -1
        subida_coluna = int(coluna_atual == coluna_anterior + 1) if coluna_anterior > 0 else 0
        descida_coluna = int(coluna_atual == coluna_anterior - 1) if coluna_anterior > 0 else 0
        repeticao_ou_vizinho = int((atual == val1) or (abs(atual - val1) == 1)) if val1 else 0

        par = int(atual % 2 == 0)
        vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        cor = int(atual in vermelhos)

        return [
            atual % 2, atual % 3, int(str(atual)[-1]),
            abs(atual - val1) if anteriores else 0,
            int(atual == val1) if anteriores else 0,
            1 if atual > val1 else -1 if atual < val1 else 0,
            sum(1 for x in anteriores[-3:] if grupo == safe_get_baz(x)),
            Counter(numeros[-30:]).get(atual, 0),
            int(atual in [n for n, _ in Counter(numeros[-30:]).most_common(5)]),
            int(np.mean(anteriores) < atual),
            int(atual == 0),
            grupo,
            densidade_20, densidade_50, rel_freq_grupo,
            repete_baz, tendencia, lag1, lag2, lag3,
            val1, val2, val3, porc_zeros,
            dist_ultimo_zero, mudanca_baz, repeticoes_baz,
            baz_quente_10, repetiu_numero, vizinho,
            reversao_tendencia,
            subida_coluna,
            descida_coluna,
            repeticao_ou_vizinho,
            par,
            cor
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []

    for i in range(self.janela, len(numeros) - 1):
        janela = numeros[i - self.janela:i + 1]
        target = get_baixo_alto_zero(numeros[i])
        if target is not None:
            X.append(self.construir_features(janela))
            y.append(target)

    if not X or len(set(y)) < 2:
        print("❌ Dados insuficientes ou apenas uma classe em y.")
        return

    X = np.array(X, dtype=np.float32)
    y = self.encoder.fit_transform(np.array(y))
    X, y = balancear_amostras(X, y)

    if len(X) < 10:
        print("❌ Muito poucos dados após balanceamento. Treinamento cancelado.")
        return

    self.modelo.fit(X, y)
    self.treinado = True


    # Modelos
    gb = HistGradientBoostingClassifier(
        early_stopping=True,
        validation_fraction=0.2,
        n_iter_no_change=10,
        max_depth=6,
        learning_rate=0.05,
        random_state=42
    )
    calibrated_gb = CalibratedClassifierCV(gb, cv=3)
    rf = RandomForestClassifier(n_estimators=100, random_state=42)

    # Ensemble
    self.modelo = VotingClassifier(
        estimators=[('gb', calibrated_gb), ('rf', rf)],
        voting='soft'
    )

    self.modelo.fit(X, y)
    self.treinado = True
    print("✅ Treinamento da IA (baixo/alto/zero) concluído.")

    def ajustar_threshold(self):
        if len(self.historico_confs) < 30:
            return self.confianca_min
        return np.percentile(self.historico_confs, 70)

    def prever(self, historico):
        if not self.treinado:
            return None
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1:
            return None
        janela = numeros[-(self.janela + 1):]
        entrada = np.array([self.construir_features(janela)], dtype=np.float32)
        proba = self.modelo.predict_proba(entrada)[0]
        self.ultima_confianca = max(proba)
        self.historico_confs.append(self.ultima_confianca)
        if self.ultima_confianca >= self.ajustar_threshold():
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
    st.session_state.acertos_gerais = {
        "ia": 0, "quente": 0, "tendencia": 0, "alternancia": 0, "altobx": 0
    }

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

# 🧮 Votação (entre estratégias humanas)
votacao = Counter()
for pred in [prev_quente, prev_tendencia, prev_alternancia]:
    if pred is not None:
        votacao[pred] += 1
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

# 📊 Desempenho geral
st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_duzia.janela
if total > 0:
    taxa = st.session_state.duzias_acertadas / total * 100
    st.metric("✅ Acertos da Previsão Final", f"{st.session_state.duzias_acertadas} / {total}", f"{taxa:.1f}%")
else:
    st.info("⏳ Aguarde mais dados para estatísticas.")

# 📌 Melhor estratégia por confiança atual
confiancas = {
    "ia": st.session_state.modelo_duzia.ultima_confianca,
    "altobx": st.session_state.modelo_altobx.ultima_confianca,
}
melhor_confianca = max(confiancas.items(), key=lambda x: x[1])
melhor_conf_nome, melhor_conf_val = melhor_confianca

if melhor_conf_nome == "ia":
    valor_conf = prev_ia
elif melhor_conf_nome == "altobx":
    valor_conf = prev_altobx

# 📌 Melhor estratégia por acertos acumulados
acertos = st.session_state.acertos_gerais
melhor_acerto_nome = max(acertos, key=lambda k: acertos[k])
melhor_acerto_val = None
conf_acerto = 0.0

if melhor_acerto_nome == "ia":
    melhor_acerto_val = prev_ia
    conf_acerto = st.session_state.modelo_duzia.ultima_confianca
elif melhor_acerto_nome == "altobx":
    melhor_acerto_val = prev_altobx
    conf_acerto = st.session_state.modelo_altobx.ultima_confianca
elif melhor_acerto_nome == "quente":
    melhor_acerto_val = prev_quente
elif melhor_acerto_nome == "tendencia":
    melhor_acerto_val = prev_tendencia
elif melhor_acerto_nome == "alternancia":
    melhor_acerto_val = prev_alternancia

# 🎯 Exibição das 2 melhores estratégias
st.subheader("🎯 Melhores Estratégias Agora")

col1, col2 = st.columns(2)

with col1:
    st.metric("🚀 Mais Confiável Agora", f"{melhor_conf_nome.upper()} ➜ {valor_conf}", f"{melhor_conf_val:.2f}")

with col2:
    st.metric("🏆 Mais Assertiva Até Agora", f"{melhor_acerto_nome.upper()} ➜ {melhor_acerto_val}", f"{conf_acerto:.2f}" if conf_acerto else "")

# 🔍 Expandir para ver todas as previsões
with st.expander("🔎 Ver todas as previsões"):
    st.write(f"🧠 IA Dúzia: {prev_ia} (confiança: {st.session_state.modelo_duzia.ultima_confianca:.2f})")
    st.write(f"🎯 Final por votação (quente/tendência/alternância): Dúzia {st.session_state.duzia_prevista}")
    st.write(f"🔥 Quente: {prev_quente} | 📈 Tendência: {prev_tendencia} | 🔁 Alternância: {prev_alternancia}")
    st.write(f"⚖️ IA Alto/Baixo/Zero: {prev_altobx} (confiança: {st.session_state.modelo_altobx.ultima_confianca:.2f})")

# 📌 Expandir para acertos por estratégia
with st.expander("📌 Acertos por Estratégia"):
    for nome, acertos in st.session_state.acertos_gerais.items():
        pct = acertos / total * 100 if total > 0 else 0
        st.write(f"✔️ {nome.upper()}: {acertos} acertos ({pct:.1f}%)")
