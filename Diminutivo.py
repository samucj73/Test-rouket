import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter, deque
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from alertas import enviar_previsao, enviar_resultado
from streamlit_autorefresh import st_autorefresh
import base64

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# Funções auxiliares
# =============================
def tocar_som_moeda():
    som_base64 = (
        "SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjI2LjEwNAAAAAAAAAAAAAAA//tQxAADBQAB"
        "VAAAAnEAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAA//sQxAADAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
    )
    audio_bytes = base64.b64decode(som_base64)
    st.markdown(
        f"""
        <audio autoplay>
            <source src="data:audio/mp3;base64,{som_base64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
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

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

# =============================
# Modelo IA HistGradientBoosting
# =============================
class ModeloIAHistGB:
    def __init__(self, tipo="duzia", janela=800):
        self.tipo = tipo
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False

    def construir_features(self, numeros):
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]

        def safe_get_duzia(n):
            return -1 if n == 0 else get_duzia(n)

        grupo = safe_get_duzia(atual)
        freq_20 = Counter(safe_get_duzia(n) for n in numeros[-20:])
        freq_50 = Counter(safe_get_duzia(n) for n in numeros[-50:]) if len(numeros) >= 50 else freq_20
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

        return [
            atual % 2, atual % 3, int(str(atual)[-1]),
            abs(atual - anteriores[-1]) if anteriores else 0,
            int(atual == anteriores[-1]) if anteriores else 0,
            1 if atual > anteriores[-1] else -1 if atual < anteriores[-1] else 0,
            sum(1 for x in anteriores[-3:] if grupo == safe_get_duzia(x)),
            Counter(numeros[-30:]).get(atual, 0),
            int(atual in [n for n, _ in Counter(numeros[-30:]).most_common(5)]),
            int(np.mean(anteriores) < atual) if anteriores else 0,
            int(atual == 0),
            grupo,
            densidade_20, densidade_50, rel_freq_grupo,
            repete_duzia, tendencia, lag1, lag2, lag3,
            val1, val2, val3, porc_zeros
        ]

    def treinar(self, historico):
        numeros = [h["number"] for h in historico if 0 <= h["number"] <= 36]
        X, y = [], []
        for i in range(self.janela, len(numeros) - 1):
            janela = numeros[i - self.janela:i + 2]
            target = get_duzia(numeros[i])
            if target is not None:
                X.append(self.construir_features(janela))
                y.append(target)
        if not X:
            return
        X = np.array(X, dtype=np.float32)
        y = self.encoder.fit_transform(np.array(y))
        self.modelo = HistGradientBoostingClassifier(max_iter=400, max_depth=7, random_state=42)
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
        if max(proba) >= 0.3:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

# =============================
# Estratégia de roleta baseada em dominantes
# =============================
class EstrategiaRoleta:
    def __init__(self, janela=12):
        self.janela = janela
        self.historico = deque(maxlen=janela+1)  # 12 + 13º
    
    def extrair_terminal(self, numero):
        return numero % 10

    def adicionar_numero(self, numero):
        self.historico.append(numero)

    def calcular_dominantes(self):
        if len(self.historico) < self.janela:
            return []
        ultimos_12 = list(self.historico)[:self.janela]
        terminais = [self.extrair_terminal(n) for n in ultimos_12]
        contagem = Counter(terminais)
        return [t for t, _ in contagem.most_common(2)]

    def verificar_entrada(self):
        if len(self.historico) < self.janela + 1:
            return None
        ultimos = list(self.historico)
        ultimos_12 = ultimos[:self.janela]
        numero_13 = ultimos[-1]
        dominantes = self.calcular_dominantes()
        if numero_13 in ultimos_12:
            return {
                "entrada": True,
                "numero_13": numero_13,
                "dominantes": dominantes,
                "jogar_nos_terminais": {
                    t: [n for n in range(37) if self.extrair_terminal(n) == t]
                    for t in dominantes
                }
            }
        else:
            return {
                "entrada": False,
                "numero_13": numero_13,
                "dominantes": dominantes
            }

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="IA Roleta Dúzia", layout="centered")
st.title("🎯 IA Roleta XXXtreme — Previsão de Dúzia")

# --- Estado ---
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB()
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaRoleta(janela=12)
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None
if "ultimo_treino" not in st.session_state:
    st.session_state.ultimo_treino = 0
if "rodada_atual" not in st.session_state:
    st.session_state.rodada_atual = None
if "previsao_enviada" not in st.session_state:
    st.session_state.previsao_enviada = False
if "resultado_enviado" not in st.session_state:
    st.session_state.resultado_enviado = False

# --- Função de treino ---
def tentar_treinar():
    historico = st.session_state.historico
    modelo = st.session_state.modelo_duzia
    if len(historico) >= modelo.janela:
        if len(historico) > st.session_state.ultimo_treino:
            modelo.treinar(historico)
            st.session_state.ultimo_treino = len(historico)
            st.toast(f"🧠 Modelo treinado com {len(historico)} resultados.")

# --- Entrada manual ---
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
                st.session_state.estrategia.adicionar_numero(n)
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{len(numeros)} números adicionados.")
            tentar_treinar()
    except Exception as e:
        st.error(f"Erro ao adicionar números: {e}")

# --- Atualização automática ---
st_autorefresh(interval=3000, key="refresh_duzia")
resultado = fetch_latest_result()
ultimo = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado and resultado["timestamp"] != ultimo:
    numero_atual = resultado["number"]

    # reset flags para nova rodada
    if numero_atual != st.session_state.rodada_atual:
        st.session_state.rodada_atual = numero_atual
        st.session_state.previsao_enviada = False
        st.session_state.resultado_enviado = False

        # --- Conferência do resultado anterior ---
        if st.session_state.duzia_prevista is not None:
            duzia_real = get_duzia(numero_atual)
            acertou = duzia_real in st.session_state.duzia_prevista if isinstance(st.session_state.duzia_prevista, list) else duzia_real == st.session_state.duzia_prevista
            if acertou:
                st.session_state.duzias_acertadas += 1
                st.toast("✅ Acertou a dúzia!")
                st.balloons()
                tocar_som_moeda()
            enviar_resultado(numero_atual, acertou)
            st.session_state.resultado_enviado = True

    # Atualiza histórico e estratégia
    st.session_state.historico.append(resultado)
    st.session_state.estrategia.adicionar_numero(numero_atual)
    salvar_resultado_em_arquivo(st.session_state.historico)
    tentar_treinar()

    # --- Verifica entrada pelo 13º número ---
    entrada_info = st.session_state.estrategia.verificar_entrada()
    if entrada_info and entrada_info.get("entrada"):
        dominantes = entrada_info["dominantes"]
        st.session_state.duzia_prevista = dominantes
        if not st.session_state.previsao_enviada:
            enviar_previsao(dominantes)
            st.session_state.previsao_enviada = True

# --- Interface ---
st.subheader("🔁 Últimos 13 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-13:]))

st.subheader("🔮 Previsão de Entrada")
if st.session_state.duzia_prevista:
    st.write(f"🎯 Jogar nos terminais dominantes: {st.session_state.duzia_prevista}")
else:
    st.info("🔎 Aguardando próximo número para calcular dominantes.")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico) - st.session_state.modelo_duzia.janela
if total > 0:
    taxa_d = st.session_state.duzias_acertadas / total * 100
    st.success(f"✅ Acertos de dúzia: {st.session_state.duzias_acertadas} / {total} ({taxa_d:.2f}%)")
else:
    st.info("🔎 Aguardando mais dados para avaliar desempenho.")

# --- Download histórico ---
with open(HISTORICO_PATH, "r") as f:
    conteudo = f.read()
st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_coluna_duzia.json")
