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
import matplotlib.pyplot as plt

# Caminho para o histórico local
HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Funções de mapeamento
def get_duzia(n):
    if n == 0: return 0
    elif 1 <= n <= 12: return 1
    elif 13 <= n <= 24: return 2
    elif 25 <= n <= 36: return 3
    return None

def get_baixo_alto_zero(n):
    if n == 0: return 0
    elif 1 <= n <= 18: return 1
    elif 19 <= n <= 36: return 2
    return None

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

# Remove duplicações ou resultados inválidos
def limpar_historico(historico):
    vistos = set()
    novo_historico = []
    for item in historico:
        chave = (item["timestamp"], item["number"])
        if chave not in vistos and 0 <= item["number"] <= 36:
            novo_historico.append(item)
            vistos.add(chave)
    return novo_historico

# Estratégias baseadas em padrões simples
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

# Balanceamento das classes para evitar viés
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

# Cache de treino para evitar treinar repetidamente
class TreinoCache:
    def __init__(self):
        self.ultima_tamanho = 0
        self.ultima_chave = None

    def deve_treinar(self, historico):
        chave = tuple((h["number"], h["timestamp"]) for h in historico[-5:])
        if len(historico) != self.ultima_tamanho or chave != self.ultima_chave:
            self.ultima_tamanho = len(historico)
            self.ultima_chave = chave
            return True
        return False

class ModeloIAHistGB:
    def __init__(self, janela=250, confianca_min=0.4):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_confianca = 0.0
        self.cache_treino = TreinoCache()

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

        features = [
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

        return features

    def treinar(self, historico):
        # Treinar apenas se houver novos dados relevantes, usando cache
        if not self.cache_treino.deve_treinar(historico):
            return  # evita treinar desnecessariamente

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

        # Modelo otimizado para treino mais rápido e maior profundidade
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

    def exibir_features_ultimo(self, historico):
        # Para debug: retorna as features da última previsão
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1:
            return None
        janela = numeros[-(self.janela + 1):]
        return self.construir_features(janela)

class TreinoCache:
    """
    Classe simples para controlar se deve treinar a IA novamente.
    Armazena timestamp do último item do histórico para evitar re-treinos sem novos dados.
    """
    def __init__(self):
        self.ultimo_timestamp = None

    def deve_treinar(self, historico):
        if not historico:
            return False
        atual = historico[-1]["timestamp"]
        if atual != self.ultimo_timestamp:
            self.ultimo_timestamp = atual
            return True
        return False


class ModeloAltoBaixoZero:
    def __init__(self, janela=250, confianca_min=0.4):
        self.janela = janela
        self.confianca_min = confianca_min
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.ultima_confianca = 0.0
        self.cache_treino = TreinoCache()

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

        features = [
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
        return features

    def treinar(self, historico):
        if not self.cache_treino.deve_treinar(historico):
            return
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

    def exibir_features_ultimo(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        if len(numeros) < self.janela + 1:
            return None
        janela = numeros[-(self.janela + 1):]
        return self.construir_features(janela)

import matplotlib.pyplot as plt

# --- Inicialização do cache de treino (fora do estado) ---
if "cache_treino_duzia" not in st.session_state:
    st.session_state.cache_treino_duzia = TreinoCache()
if "cache_treino_baz" not in st.session_state:
    st.session_state.cache_treino_baz = TreinoCache()

# --- Função para verificar e adicionar novo resultado evitando duplicação ---
def adicionar_resultado_se_novo(novo_resultado):
    if not novo_resultado:
        return False
    if not st.session_state.historico:
        st.session_state.historico.append(novo_resultado)
        return True
    if novo_resultado["timestamp"] != st.session_state.historico[-1]["timestamp"]:
        st.session_state.historico.append(novo_resultado)
        return True
    return False

# --- Captura da API ---
resultado_api = None
try:
    response = requests.get(API_URL, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()
    game_data = data.get("data", {})
    result = game_data.get("result", {})
    outcome = result.get("outcome", {})
    numero_atual = outcome.get("number")
    timestamp_atual = game_data.get("startedAt")
    resultado_api = {"number": numero_atual, "timestamp": timestamp_atual}
except Exception as e:
    logging.error(f"Erro ao buscar resultado: {e}")

# --- Adiciona novo resultado se válido e não duplicado ---
if resultado_api and adicionar_resultado_se_novo(resultado_api):
    st.toast(f"🎲 Novo número: {resultado_api['number']}")
    salvar_resultado_em_arquivo(st.session_state.historico)

# --- Treinamento dos modelos só se houver novo dado (usa cache) ---
if st.session_state.cache_treino_duzia.deve_treinar(st.session_state.historico):
    st.session_state.modelo_duzia.treinar(st.session_state.historico)
if st.session_state.cache_treino_baz.deve_treinar(st.session_state.historico):
    st.session_state.modelo_baz.treinar(st.session_state.historico)

# --- Obter previsões atuais ---
prev_ia = st.session_state.modelo_duzia.prever(st.session_state.historico)
prev_quente = estrategia_duzia_quente(st.session_state.historico)
prev_tendencia = estrategia_tendencia(st.session_state.historico)
prev_alternancia = estrategia_alternancia(st.session_state.historico)

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

# --- Se tiver novo resultado, atualiza acertos ---
if resultado_api and resultado_api["timestamp"] == st.session_state.historico[-1]["timestamp"]:
    duzia_real = get_duzia(resultado_api["number"])
    baz_real = get_baixo_alto_zero(resultado_api["number"])

    # Acertos estratégias dúzia
    if duzia_real == prev_ia:
        st.session_state.acertos_estrategias["ia"] += 1
    if duzia_real == prev_quente:
        st.session_state.acertos_estrategias["quente"] += 1
    if duzia_real == prev_tendencia:
        st.session_state.acertos_estrategias["tendencia"] += 1
    if duzia_real == prev_alternancia:
        st.session_state.acertos_estrategias["alternancia"] += 1

    # Acertos dúzia final
    if duzia_real == st.session_state.duzia_prevista:
        st.session_state.duzias_acertadas += 1
        st.toast("✅ Acertou a dúzia!")
        st.balloons()

    # Acertos Baixo/Alto/Zero
    if baz_real == st.session_state.baz_previsto:
        st.session_state.baz_acertados += 1
        st.toast("✅ Acertou Baixo/Alto/Zero!")

# --- Exibição das features da última previsão para debug ---
st.subheader("🧩 Features da última previsão (IA Baixo/Alto/Zero)")
features_debug = st.session_state.modelo_baz.exibir_features_ultimo(st.session_state.historico)
if features_debug:
    st.write(features_debug)
else:
    st.info("Sem features para mostrar (dados insuficientes).")

# --- Gráficos de desempenho por blocos ---
def desempenho_por_blocos(historico, acertos, bloco_tamanho=50):
    blocos = []
    taxas = []
    for i in range(0, len(historico), bloco_tamanho):
        bloco = historico[i:i+bloco_tamanho]
        if len(bloco) < bloco_tamanho:
            break
        total = bloco_tamanho
        acertos_bloco = sum(1 for idx in range(i, i+bloco_tamanho) if idx < len(historico) and acertos[idx] if idx < len(acertos) else False)
        taxa = (acertos_bloco / total) * 100 if total > 0 else 0
        blocos.append(f"{i+1}-{i+bloco_tamanho}")
        taxas.append(taxa)
    return blocos, taxas

# Construir lista booleana de acertos por índice para dúzia e baz
total_len = len(st.session_state.historico)
acertos_ia_bool = [False]*total_len
acertos_baz_bool = [False]*total_len

# Simples: vamos atualizar listas marcando índices onde houve acerto
for i, entry in enumerate(st.session_state.historico):
    n = entry["number"]
    duz = get_duzia(n)
    baz = get_baixo_alto_zero(n)
    if duz == prev_ia:
        acertos_ia_bool[i] = True
    if baz == st.session_state.baz_previsto:
        acertos_baz_bool[i] = True

blocos, taxas_duzia = desempenho_por_blocos(st.session_state.historico, acertos_ia_bool)
_, taxas_baz = desempenho_por_blocos(st.session_state.historico, acertos_baz_bool)

st.subheader("📈 Desempenho por blocos de 50 resultados")
fig, ax = plt.subplots()
ax.plot(blocos, taxas_duzia, label="Dúzia IA (%)")
ax.plot(blocos, taxas_baz, label="Baixo/Alto/Zero IA (%)")
ax.set_xlabel("Bloco")
ax.set_ylabel("Taxa de Acerto (%)")
ax.legend()
ax.grid(True)
st.pyplot(fig)

import base64

# --- Função para tocar som embutido base64 ---
def tocar_som_acerto():
    som_base64 = (
        "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU2LjI0LjEwNQAAAAAAAAAAAAAA//tQxAADB"
        "AAAAPoPABAAEAAAAAEAAQAAAAgAAAAAAABAAEAAEAAgACAAACgAAFAAAABAAAAGhAAACQ"
        "wAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAA//sQxAADAAAAAEA=="
    )
    audio_bytes = base64.b64decode(som_base64)
    st.audio(audio_bytes, format="audio/wav")

# --- Feedback sonoro ao acertar ---
if resultado_api and resultado_api["timestamp"] == st.session_state.historico[-1]["timestamp"]:
    baz_real = get_baixo_alto_zero(resultado_api["number"])
    if baz_real == st.session_state.baz_previsto:
        # Tocar som de acerto (pode ajustar para outras situações)
        tocar_som_acerto()

# --- Exibição do histórico completo ---
st.subheader("📜 Histórico Completo de Números")
if st.button("Mostrar Histórico Completo"):
    st.write(st.session_state.historico)

# --- Download histórico atualizado ---
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico atualizado", data=conteudo, file_name="historico_coluna_duzia.json")

# --- Organização e manutenção futura ---
"""
- Classes ModeloIAHistGB e ModeloAltoBaixoZero com funções bem encapsuladas
- Funções auxiliares para estratégias
- Cache de treino para evitar re-treinamentos desnecessários
- Funções específicas para manipulação do histórico
- Interface clara com separação de blocos de código (configuração, entrada, treino, previsão, visualização, métricas)
- Comentários detalhados para fácil entendimento e futuras melhorias
"""

# --- Refresh automático para atualização dos dados ---
st_autorefresh(interval=10000, key="refresh_roleta_final")
