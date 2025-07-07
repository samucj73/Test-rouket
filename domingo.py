import streamlit as st
import json
import os
import requests
import numpy as np
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import resample
from streamlit_autorefresh import st_autorefresh

# Caminho do histórico
HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def buscar_numero_api():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            numero = int(data.get("winningNumber", -1))
            if 0 <= numero <= 36:
                ultimo = st.session_state.historico[-1]["number"] if st.session_state.historico else None
                if numero != ultimo:
                    st.session_state.historico.append({"number": numero, "timestamp": data.get("timestamp", "api")})
                    salvar_resultado_em_arquivo(st.session_state.historico)
                    st.toast(f"🎲 Novo número: {numero}")
    except Exception as e:
        st.warning(f"Erro ao buscar número da API: {e}")

# Funções utilitárias
def get_duzia(n):
    if n == 0: return 0
    if 1 <= n <= 12: return 1
    if 13 <= n <= 24: return 2
    if 25 <= n <= 36: return 3
    return None

def get_baixo_alto_zero(n):
    if n == 0: return 0
    elif 1 <= n <= 18: return 1
    elif 19 <= n <= 36: return 2
    return None

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

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

# Inicializa o estado da sessão
if "historico" not in st.session_state:
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            st.session_state.historico = json.load(f)
    else:
        st.session_state.historico = []

if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "baz_acertados" not in st.session_state:
    st.session_state.baz_acertados = 0
if "acertos_estrategias" not in st.session_state:
    st.session_state.acertos_estrategias = {
        "ia": 0,
        "quente": 0,
        "tendencia": 0,
        "alternancia": 0,
        "ausente": 0,
        "maior_alt": 0
    }

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

def estrategia_maior_alternancia(historico):
    """Retorna a dúzia oposta à anterior (para detectar alternância forte)."""
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < 2:
        return None
    duzias = [get_duzia(n) for n in numeros[-2:]]
    if duzias[0] != duzias[1]:
        return [d for d in [1, 2, 3] if d != duzias[1]][0]
    return duzias[1]
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

        coluna_atual = get_duzia(atual)
        coluna_anterior = get_duzia(val1) if val1 else -1
        subida_coluna = int(coluna_atual == coluna_anterior + 1) if coluna_anterior > 0 else 0
        descida_coluna = int(coluna_atual == coluna_anterior - 1) if coluna_anterior > 0 else 0

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

import streamlit as st
import json
import os
import numpy as np
from collections import Counter
from streamlit_autorefresh import st_autorefresh

HISTORICO_PATH = "historico_coluna_duzia.json"

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

def estrategia_maior_alternancia(historico):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < 4:
        return None
    duzias = [get_duzia(n) for n in numeros]
    alt = 0
    max_alt = 0
    melhor = duzias[-1]
    for i in range(1, len(duzias)):
        if duzias[i] != duzias[i - 1]:
            alt += 1
            if alt > max_alt:
                max_alt = alt
                melhor = duzias[i]
        else:
            alt = 0
    return melhor

# Configuração da página
st.set_page_config(page_title="🎲 IA Roleta XXXtreme", layout="centered")
st.title("🎰 IA Roleta XXXtreme")
st.caption("Previsão de **Dúzia** e **Baixo/Alto/Zero** com estratégias inteligentes + IA")

# Inicialização do estado da sessão
if "historico" not in st.session_state:
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            st.session_state.historico = json.load(f)
    else:
        st.session_state.historico = []

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
        "ia": 0,
        "quente": 0,
        "tendencia": 0,
        "alternancia": 0,
        "ausente": 0,
        "maior_alt": 0
    }

# 🔧 Configurações
with st.sidebar:
    st.header("⚙️ Configurações")
    janela_ia = st.slider("Tamanho da Janela da IA", 50, 300, 250, step=10)
    confianca_min = st.slider("Confiança Mínima da IA", 0.1, 0.9, 0.4, step=0.05)
    if st.button("🔁 Re-Treinar IAs"):
        st.session_state.modelo_duzia = ModeloIAHistGB(janela=janela_ia, confianca_min=confianca_min)
        st.session_state.modelo_duzia.treinar(st.session_state.historico)
        st.session_state.modelo_baz = ModeloAltoBaixoZero(janela=janela_ia, confianca_min=confianca_min)
        st.session_state.modelo_baz.treinar(st.session_state.historico)
        st.success("Modelos treinados novamente!")

# 📝 Entrada Manual
with st.expander("✍️ Inserir Números Manualmente"):
    entrada = st.text_area("Digite os números (0 a 36, separados por espaço):", height=100)
    if st.button("📩 Adicionar Sorteios"):
        try:
            numeros = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
            if numeros:
                for n in numeros:
                    st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
                salvar_resultado_em_arquivo(st.session_state.historico)
                st.success(f"{len(numeros)} números adicionados com sucesso!")
            else:
                st.warning("Nenhum número válido encontrado.")
        except:
            st.error("Erro ao processar os números.")

with st.expander("🕘 Últimos Números", expanded=True):
    ultimos = [str(h["number"]) for h in st.session_state.historico[-10:]]
    st.code(" | ".join(ultimos), language="text")

# 🔮 Previsões
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔮 Previsão de Dúzia")
    prev_ia = st.session_state.modelo_duzia.prever(st.session_state.historico)
    prev_quente = estrategia_duzia_quente(st.session_state.historico)
    prev_tendencia = estrategia_tendencia(st.session_state.historico)
    prev_alternancia = estrategia_alternancia(st.session_state.historico)
    prev_ausente = estrategia_duzia_ausente(st.session_state.historico)
    prev_maior_alt = estrategia_maior_alternancia(st.session_state.historico)

    votacao = Counter()
    for p in [prev_quente, prev_tendencia, prev_alternancia]:
        if p is not None:
            votacao[p] += 1
    final_duzia = votacao.most_common(1)[0][0] if votacao else None
    st.session_state.duzia_prevista = final_duzia

    st.metric("🧠 IA", str(prev_ia), f"{st.session_state.modelo_duzia.ultima_confianca:.2f}")
    st.metric("🔥 Quente", str(prev_quente))
    st.metric("📈 Tendência", str(prev_tendencia))
    st.metric("🔁 Alternância", str(prev_alternancia))
    st.metric("⏳ Ausente", str(prev_ausente))
    st.metric("⚡ Maior Alternância", str(prev_maior_alt))
    st.success(f"🎯 Final: Dúzia {final_duzia}")

with col2:
    st.subheader("🔮 Previsão Baixo/Alto/Zero")
    prev_baz = st.session_state.modelo_baz.prever(st.session_state.historico)
    st.session_state.baz_previsto = prev_baz
    map_baz = {0: "Zero", 1: "Baixo (1-18)", 2: "Alto (19-36)"}
    st.metric("🧠 IA B/A/Z", map_baz.get(prev_baz, "N/A"), f"{st.session_state.modelo_baz.ultima_confianca:.2f}")

# 📊 Desempenho
with st.expander("📊 Desempenho"):
    total = len(st.session_state.historico) - st.session_state.modelo_duzia.janela
    if total > 0:
        taxa_duzia = st.session_state.duzias_acertadas / total * 100
        taxa_baz = st.session_state.baz_acertados / total * 100
        st.success(f"🎯 Dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa_duzia:.2f}%)")
        st.success(f"🎯 Baixo/Alto/Zero: {st.session_state.baz_acertados} / {total} ({taxa_baz:.2f}%)")
        st.markdown("### ✅ Acertos por Estratégia Dúzia")
        for nome, acertos in st.session_state.acertos_estrategias.items():
            taxa = acertos / total * 100
            st.write(f"• **{nome.capitalize()}**: {acertos} ({taxa:.1f}%)")
    else:
        st.info("Aguardando mais dados para calcular o desempenho.")

# 📥 Download histórico
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar Histórico", data=conteudo, file_name="historico_coluna_duzia.json")

# 🔁 Auto-refresh
st_autorefresh(interval=10000, key="refresh_roleta")
buscar_numero_api()
