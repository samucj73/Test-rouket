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
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

# =============================
# Estratégia baseada em terminais dominantes
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
        ultimos_12 = ultimos[:-1]   # 12 primeiros
        numero_13 = ultimos[-1]     # 13º
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
st.title("🎯 IA Roleta XXXtreme — Estratégia dos Terminais Dominantes")

# --- Estado ---
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaRoleta(janela=12)
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None
if "rodada_atual" not in st.session_state:
    st.session_state.rodada_atual = None
if "previsao_enviada" not in st.session_state:
    st.session_state.previsao_enviada = False
if "resultado_enviado" not in st.session_state:
    st.session_state.resultado_enviado = False

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

    # Atualiza histórico e estratégia
    st.session_state.historico.append(resultado)
    st.session_state.estrategia.adicionar_numero(numero_atual)
    salvar_resultado_em_arquivo(st.session_state.historico)

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

# --- Download histórico ---
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_coluna_duzia.json")
