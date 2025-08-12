import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from streamlit_autorefresh import st_autorefresh
import base64
import time

# Configurações
HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# -------- Funções de som --------
def tocar_som_moeda():
    som_base64 = (
        "SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjI2LjEwNAAAAAAAAAAAAAAA//tQxAADBQAB"
        "VAAAAnEAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAA//sQxAADAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
    )
    audio_bytes = base64.b64decode(som_base64)
    st.audio(audio_bytes, format="audio/mp3")

# -------- Utilitários --------
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
    if n == 0:
        return 0
    elif 1 <= n <= 12:
        return 1
    elif 13 <= n <= 24:
        return 2
    elif 25 <= n <= 36:
        return 3
    return None

def get_coluna(n):
    if n == 0:
        return 0
    elif n % 3 == 1:
        return 1
    elif n % 3 == 2:
        return 2
    elif n % 3 == 0:
        return 3
    return None

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code != 200:
            logging.warning(f"Falha ao enviar Telegram: {resp.text}")
    except Exception as e:
        logging.error(f"Erro no envio Telegram: {e}")

# -------- Estratégias auxiliares --------
def estrategia_quente(historico, tipo="duzia", janela=130):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    if tipo == "duzia":
        grupos = [get_duzia(n) for n in numeros]
    else:
        grupos = [get_coluna(n) for n in numeros]
    mais_comum = Counter(grupos).most_common(1)
    return mais_comum[0][0] if mais_comum else None

def estrategia_tendencia(historico, tipo="duzia"):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < 5:
        return None
    ultimos = numeros[-5:]
    if tipo == "duzia":
        ultimos_grupo = [get_duzia(n) for n in ultimos]
    else:
        ultimos_grupo = [get_coluna(n) for n in ultimos]
    dif = np.mean(np.diff(ultimos_grupo))
    ultimo = ultimos_grupo[-1]
    if dif > 0:
        return min(ultimo + 1, 3)
    elif dif < 0:
        return max(ultimo - 1, 1)
    else:
        return ultimo

def estrategia_alternancia(historico, tipo="duzia", limite=2):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < limite + 1:
        return None
    if tipo == "duzia":
        duzias = [get_duzia(n) for n in numeros[-(limite + 1):]]
        atual = duzias[-1]
        if duzias.count(atual) >= limite:
            return [d for d in [1, 2, 3] if d != atual][0]
        return atual
    else:
        colunas = [get_coluna(n) for n in numeros[-(limite + 1):]]
        atual = colunas[-1]
        if colunas.count(atual) >= limite:
            return [c for c in [1, 2, 3] if c != atual][0]
        return atual

# -------- Modelo IA --------
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

        def safe_get_grupo(n):
            if self.tipo == "duzia":
                return -1 if n == 0 else get_duzia(n)
            else:
                return -1 if n == 0 else get_coluna(n)

        grupo = safe_get_grupo(atual)
        freq_20 = Counter(safe_get_grupo(n) for n in numeros[-20:])
        freq_50 = Counter(safe_get_grupo(n) for n in numeros[-50:]) if len(numeros) >= 150 else freq_20
        total_50 = sum(freq_50.values()) or 1

        lag1 = safe_get_grupo(anteriores[-1]) if len(anteriores) >= 1 else -1
        lag2 = safe_get_grupo(anteriores[-2]) if len(anteriores) >= 2 else -1
        lag3 = safe_get_grupo(anteriores[-3]) if len(anteriores) >= 3 else -1

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
        repete_grupo = int(grupo == safe_get_grupo(anteriores[-1])) if anteriores else 0

        return [
            atual % 2, atual % 3, int(str(atual)[-1]),
            abs(atual - anteriores[-1]) if anteriores else 0,
            int(atual == anteriores[-1]) if anteriores else 0,
            1 if atual > anteriores[-1] else -1 if atual < anteriores[-1] else 0,
            sum(1 for x in anteriores[-3:] if grupo == safe_get_grupo(x)),
            Counter(numeros[-30:]).get(atual, 0),
            int(atual in [n for n, _ in Counter(numeros[-30:]).most_common(5)]),
            int(np.mean(anteriores) < atual),
            int(atual == 0),
            grupo,
            densidade_20, densidade_50, rel_freq_grupo,
            repete_grupo, tendencia, lag1, lag2, lag3,
            val1, val2, val3, porc_zeros
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 1]
            if self.tipo == "duzia":
                target = get_duzia(numeros[i])
            else:
                target = get_coluna(numeros[i])
            if target is not None:
                X.append(self.construir_features(janela))
                y.append(target)
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))
        self.modelo = HistGradientBoostingClassifier(max_iter=200, max_depth=7, random_state=42)
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
        max_prob = max(proba)
        if max_prob >= 0.4:
            pred = self.encoder.inverse_transform([np.argmax(proba)])[0]
            return pred, max_prob
        return None, 0

# -------- Controle de alertas para evitar repetição --------
class ControleAlertas:
    def __init__(self):
        self.ultima_prev = None
        self.rodadas_sem_alerta = 0
        self.ultimo_resultado_duzia = None
        self.ultimo_resultado_coluna = None

    def deve_enviar(self, prev_nova):
        if self.ultima_prev != prev_nova:
            self.ultima_prev = prev_nova
            self.rodadas_sem_alerta = 0
            return True
        else:
            self.rodadas_sem_alerta += 1
            if self.rodadas_sem_alerta >= 3:
                self.rodadas_sem_alerta = 0
                return True
        return False

controle_alertas = ControleAlertas()

# -------- Streamlit Interface --------
st.set_page_config(page_title="IA Roleta Dúzia e Coluna", layout="centered")
st.title("🎯 IA Roleta XXXtreme — Previsão de Dúzia e Coluna")

# Estado inicial
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB(tipo="duzia")
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = ModeloIAHistGB(tipo="coluna")
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "colunas_acertadas" not in st.session_state:
    st.session_state.colunas_acertadas = 0
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None
if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = None
if "ultima_prev" not in st.session_state:
    st.session_state.ultima_prev = None
if "rodadas_sem_alerta" not in st.session_state:
    st.session_state.rodadas_sem_alerta = 0

# Entrada manual
st.subheader("✍️ Inserir Sorteios Manualmente")
entrada = st.text_area("Digite os números (até 100, separados por espaço):", height=100)
if st.button("Adicionar Sorteios"):
    try:
        numeros = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        if len(numeros) > 100:
            st.warning("Limite de 100 números.")
        else:
            for n in numeros:
                st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{len(numeros)} números adicionados.")
    except:
        st.error("Erro ao processar os números.")

# Autoatualização e captura
st_autorefresh(interval=10000, key="refresh")

resultado = fetch_latest_result()
ultimo_timestamp = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None
if resultado and resultado["timestamp"] != ultimo_timestamp:
    st.session_state.historico.append(resultado)
    salvar_resultado_em_arquivo(st.session_state.historico)
    st.toast(f"🎲 Novo número: {resultado['number']}")

    # Checar acertos do resultado anterior (se temos previsão)
    if st.session_state.duzia_prevista is not None:
        atual_duzia = get_duzia(resultado["number"])
        if atual_duzia == st.session_state.duzia_prevista:
            st.session_state.duzias_acertadas += 1
            st.toast("✅ Acertou a dúzia!")
            st.balloons()
            tocar_som_moeda()
            enviar_telegram(f"✅ 🟢 GREEN! Acertou a dúzia {atual_duzia}!")
        else:
            enviar_telegram(f"🔴 RED! Dúzia prevista {st.session_state.duzia_prevista}, saiu {atual_duzia}")

    if st.session_state.coluna_prevista is not None:
        atual_coluna = get_coluna(resultado["number"])
        if atual_coluna == st.session_state.coluna_prevista:
            st.session_state.colunas_acertadas += 1
            st.toast("✅ Acertou a coluna!")
            st.balloons()
            tocar_som_moeda()
            enviar_telegram(f"✅ 🟢 GREEN! Acertou a coluna {atual_coluna}!")
        else:
            enviar_telegram(f"🔴 RED! Coluna prevista {st.session_state.coluna_prevista}, saiu {atual_coluna}")

# Treinar modelos IA
st.session_state.modelo_duzia.treinar(st.session_state.historico)
st.session_state.modelo_coluna.treinar(st.session_state.historico)

# Previsão IA + estratégias
def prever_tudo(tipo):
    if tipo == "duzia":
        modelo = st.session_state.modelo_duzia
    else:
        modelo = st.session_state.modelo_coluna

    prev_ia, prob_ia = modelo.prever(st.session_state.historico)
    prev_quente = estrategia_quente(st.session_state.historico, tipo)
    prev_tendencia = estrategia_tendencia(st.session_state.historico, tipo)
    prev_alternancia = estrategia_alternancia(st.session_state.historico, tipo)

    candidatos = [c for c in [prev_ia, prev_quente, prev_tendencia, prev_alternancia] if c is not None]
    if not candidatos:
        return None, 0

    votos = Counter(candidatos)
    mais_votado, votos_count = votos.most_common(1)[0]

    # Usar prob IA se disponível para ponderar confiança
    confianca = prob_ia if prev_ia == mais_votado else 0.4
    return mais_votado, confianca

prev_duzia, prob_duzia = prever_tudo("duzia")
prev_coluna, prob_coluna = prever_tudo("coluna")

# Definir qual previsão enviar
if prev_duzia is not None and prev_coluna is not None:
    if prob_duzia >= prob_coluna:
        previs
