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

HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

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

def get_baixo_alto_zero(n):
    # 0 é zero
    if n == 0:
        return 0
    # baixo: 1 a 18
    elif 1 <= n <= 18:
        return 1
    # alto: 19 a 36
    elif 19 <= n <= 36:
        return 2
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
    if len(numeros) < 5:
        return None
    ultimos = numeros[-5:]
    dif = np.mean(np.diff(ultimos))
    if dif > 0:
        return min(get_duzia(ultimos[-1]) + 1, 3)
    elif dif < 0:
        return max(get_duzia(ultimos[-1]) - 1, 1)
    else:
        return get_duzia(ultimos[-1])

def estrategia_alternancia(historico, limite=2):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < limite + 1:
        return None
    duzias = [get_duzia(n) for n in numeros[-(limite + 1):]]
    if duzias.count(duzias[-1]) >= limite:
        return [d for d in [1, 2, 3] if d != duzias[-1]][0]
    return duzias[-1]

def estrategia_duzia_ausente(historico, janela=150):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    duzias = [get_duzia(n) for n in numeros]
    contagem = Counter(duzias)
    ausente = [d for d in [1, 2, 3] if d not in contagem]
    if ausente:
        return ausente[0]
    menos_frequente = sorted(contagem.items(), key=lambda x: x[1])[0][0]
    return menos_frequente

def estrategia_maior_alternancia(historico, janela=30):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    duzias = [get_duzia(n) for n in numeros]
    alternancias = [abs(duzias[i] - duzias[i-1]) for i in range(1, len(duzias))]
    if not alternancias:
        return None
    return get_duzia(numeros[-1]) if alternancias[-1] > 0 else None

def balancear_amostras(X, y):
    X = np.array(X)
    y = np.array(y)
    classes = np.unique(y)
    max_len = max([np.sum(y == c) for c in classes])
    X_bal, y_bal = [], []
    for c in classes:
        X_c = X[y == c]
        y_c = y[y == c]
        X_res, y_res = resample(X_c, y_c, replace=True, n_samples=max_len, random_state=42)
        X_bal.append(X_res)
        y_bal.append(y_res)
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

        # Padrão humano - subida ou descida entre colunas
        coluna_atual = get_duzia(atual)
        coluna_anterior = get_duzia(val1) if val1 else -1
        subida_coluna = int(coluna_atual == coluna_anterior + 1) if coluna_anterior > 0 else 0
        descida_coluna = int(coluna_atual == coluna_anterior - 1) if coluna_anterior > 0 else 0

        # Padrão humano - repetição do número anterior ou vizinho imediato
        repeticao_ou_vizinho = int((atual == val1) or (abs(atual - val1) == 1)) if val1 else 0

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
            repeticao_ou_vizinho
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
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))
        X, y = balancear_amostras(X, y)
        self.modelo = HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=10,
            learning_rate=0.05,
            random_state=42
        )
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
        self.ultima_confianca = max(proba)
        if self.ultima_confianca >= self.confianca_min:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

class ModeloAltoBaixoZero:
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
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))
        X, y = balancear_amostras(X, y)
        self.modelo = HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=10,
            learning_rate=0.05,
            random_state=42
        )
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
        self.ultima_confianca = max(proba)
        if self.ultima_confianca >= self.confianca_min:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

# ⬇️ Interface Streamlit ⬇️
st.set_page_config(page_title="IA Roleta Dúzia & Baixo/Alto/Zero", layout="centered")
st.title("🎯 IA Roleta XXXtreme — Previsão de Dúzia e Baixo/Alto/Zero")

# Estado
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB()
if "modelo_baz" not in st.session_state:
    st.session_state.modelo_baz = ModeloAltoBaixoZero()
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "baz_acertados" not in st.session_state:
    st.session_state.baz_acertados = 0
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None
if "baz_previsto" not in st.session_state:
    st.session_state.baz_previsto = None
if "acertos_estrategias" not in st.session_state:
    st.session_state.acertos_estrategias = {
        "ia": 0, "quente": 0, "tendencia": 0, "alternancia": 0, "ausente": 0, "maior_alt": 0
    }

# Sidebar de configuração
st.sidebar.header("⚙️ Configurações")
janela_ia = st.sidebar.slider("Tamanho da janela IA", 50, 300, 250, step=10)
confianca_min = st.sidebar.slider("Confiança mínima da IA", 0.1, 0.9, 0.4, step=0.05)

# Entrada manual
st.subheader("✍️ Inserir Sorteios Manualmente")
entrada = st.text_area("Digite os números (até 300, separados por espaço):", height=300)
if st.button("Adicionar Sorteios"):
    try:
        numeros = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        if len(numeros) > 300:
            st.warning("Limite de 300 números.")
        else:
            for n in numeros:
                st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{len(numeros)} números adicionados.")
    except:
        st.error("Erro ao processar os números.")

# Treinar IAs com novos parâmetros
st.session_state.modelo_duzia = ModeloIAHistGB(janela=janela_ia, confianca_min=confianca_min)
st.session_state.modelo_duzia.treinar(st.session_state.historico)

st.session_state.modelo_baz = ModeloAltoBaixoZero(janela=janela_ia, confianca_min=confianca_min)
st.session_state.modelo_baz.treinar(st.session_state.historico)

# Estratégias dúzia
prev_ia = st.session_state.modelo_duzia.prever(st.session_state.historico)
prev_quente = estrategia_duzia_quente(st.session_state.historico)
prev_tendencia = estrategia_tendencia(st.session_state.historico)
prev_alternancia = estrategia_alternancia(st.session_state.historico)
prev_ausente = estrategia_duzia_ausente(st.session_state.historico)
prev_maior_alt = estrategia_maior_alternancia(st.session_state.historico)

# Previsão Baixo/Alto/Zero
prev_baz = st.session_state.modelo_baz.prever(st.session_state.historico)
st.session_state.baz_previsto = prev_baz

# Votação para dúzia final (3 estratégias)
votacao = Counter()
if prev_quente is not None:
    votacao[prev_quente] += 1
if prev_tendencia is not None:
    votacao[prev_tendencia] += 1
if prev_alternancia is not None:
    votacao[prev_alternancia] += 1
mais_votado = votacao.most_common(1)[0][0] if votacao else None
st.session_state.duzia_prevista = mais_votado

# Captura da API
resultado = None
try:
    response = requests.get(API_URL, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()
    game_data = data.get("data", {})
    result = game_data.get("result", {})
    outcome = result.get("outcome", {})
    numero_atual = outcome.get("number")
    timestamp_atual = game_data.get("startedAt")
    resultado = {"number": numero_atual, "timestamp": timestamp_atual}
except Exception as e:
    logging.error(f"Erro ao buscar resultado: {e}")

ultimo_timestamp = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

# Verificar se novo número chegou
if resultado and resultado["timestamp"] != ultimo_timestamp:
    st.toast(f"🎲 Novo número: {resultado['number']}")
    duzia_real = get_duzia(resultado["number"])
    baz_real = get_baixo_alto_zero(resultado["number"])

    # Acertos por estratégia dúzia
    if duzia_real == prev_ia:
        st.session_state.acertos_estrategias["ia"] += 1
    if duzia_real == prev_quente:
        st.session_state.acertos_estrategias["quente"] += 1
    if duzia_real == prev_tendencia:
        st.session_state.acertos_estrategias["tendencia"] += 1
    if duzia_real == prev_alternancia:
        st.session_state.acertos_estrategias["alternancia"] += 1
    if duzia_real == prev_ausente:
        st.session_state.acertos_estrategias["ausente"] += 1
    if duzia_real == prev_maior_alt:
        st.session_state.acertos_estrategias["maior_alt"] += 1

    # Acertos dúzia final
    if duzia_real == st.session_state.duzia_prevista:
        st.session_state.duzias_acertadas += 1
        st.toast("✅ Acertou a dúzia!")
        st.balloons()

    # Acertos Baixo/Alto/Zero
    if baz_real == st.session_state.baz_previsto:
        st.session_state.baz_acertados += 1
        st.toast("✅ Acertou Baixo/Alto/Zero!")

    st.session_state.historico.append(resultado)
    salvar_resultado_em_arquivo(st.session_state.historico)

# Exibição dos últimos números
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-10:]))

# Download do histórico
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_coluna_duzia.json")

# Previsões exibidas (dúzia)
st.subheader("🔮 Previsões de Dúzia")
st.write(f"🧠 IA: {prev_ia} (Confiança: {st.session_state.modelo_duzia.ultima_confianca:.2f})")
st.write(f"🔥 Quente: {prev_quente}")
st.write(f"📈 Tendência: {prev_tendencia}")
st.write(f"🔁 Alternância: {prev_alternancia}")
st.write(f"⏳ Dúzia Ausente: {prev_ausente}")
st.write(f"⚡ Alternância Maior: {prev_maior_alt}")
st.success(f"🎯 Previsão final (votação entre 3 estratégias): Dúzia {mais_votado}")

# Previsão Baixo/Alto/Zero
st.subheader("🔮 Previsão Baixo / Alto / Zero")
map_baz = {0: "Zero", 1: "Baixo (1-18)", 2: "Alto (19-36)"}
st.write(f"🧠 IA B/A/Z: {map_baz.get(prev_baz, 'N/A')} (Confiança: {st.session_state.modelo_baz.ultima_confianca:.2f})")

# Desempenho geral
st.subheader("📊 Desempenho Geral")
total = len(st.session_state.historico) - st.session_state.modelo_duzia.janela
if total > 0:
    taxa_geral = st.session_state.duzias_acertadas / total * 100
    taxa_baz = st.session_state.baz_acertados / total * 100
    st.success(f"✅ Acertos da Previsão Dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa_geral:.2f}%)")
    st.success(f"✅ Acertos da Previsão Baixo/Alto/Zero: {st.session_state.baz_acertados} / {total} ({taxa_baz:.2f}%)")
else:
    st.info("🔎 Aguardando mais dados para avaliar desempenho.")

# Acertos por estratégia dúzia
st.subheader("📌 Acertos por Estratégia Dúzia")
for nome, acertos in st.session_state.acertos_estrategias.items():
    taxa = acertos / total * 100 if total > 0 else 0
    st.write(f"✔️ {nome.capitalize()}: {acertos} ({taxa:.1f}%)")

# Atualização automática
st_autorefresh(interval=10000, key="refresh_roleta")
