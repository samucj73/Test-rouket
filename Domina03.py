import streamlit as st
import json
import os
import requests
from collections import deque
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import numpy as np
import base64
import logging

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# =============================
# Funções de envio de mensagem
# =============================
def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar para Telegram: {e}")

def enviar_msg(msg, tipo="previsao"):
    if tipo == "previsao":
        st.success(msg)
        enviar_telegram(msg)
    else:
        st.info(msg)
        enviar_telegram(msg)

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

# =============================
# Auxiliares de histórico
# =============================
def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            historico = json.load(f)
        # Padronizar: todos como {"number": n, "timestamp": ts}
        historico_padronizado = []
        for h in historico:
            if isinstance(h, dict):
                historico_padronizado.append(h)
            else:
                historico_padronizado.append({"number": h, "timestamp": f"manual_{len(historico_padronizado)}"})
        return historico_padronizado
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f, indent=2)

# =============================
# Captura do resultado mais recente
# =============================
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

# =============================
# Estratégia de Deslocamento
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)
        self.roleta = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
            27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
            16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
            7, 28, 12, 35, 3, 26
        ]

    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA para previsão de deslocamentos
# =============================
class IA_Deslocamento:
    def __init__(self, janela=12):
        self.janela = janela
        self.model = RandomForestClassifier(n_estimators=100)
        self.X = []
        self.y = []
        self.treinado = False

    def atualizar_historico(self, historico):
        ultimos = [h["number"] for h in historico]
        if len(ultimos) <= self.janela:
            return
        self.X = []
        self.y = []
        for i in range(len(ultimos)-self.janela):
            janela_nums = ultimos[i:i+self.janela]
            proximo = ultimos[i+self.janela]
            self.X.append(janela_nums)
            self.y.append(proximo)
        if len(self.X) > 0:
            self.model.fit(self.X, self.y)
            self.treinado = True

    def prever(self, historico, top_n=10):
        if not self.treinado or len(historico) < self.janela:
            return []
        ultimos = [h["number"] for h in list(historico)[-self.janela:]]
        probs = self.model.predict_proba([ultimos])[0]
        classes = self.model.classes_
        top_indices = np.argsort(probs)[::-1][:top_n]
        return [classes[i] for i in top_indices]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Deslocamento", layout="centered")
st.title("🎯 Roleta — IA de Deslocamento Adaptativa")

st_autorefresh(interval=7000, key="refresh")

# Inicialização
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()
    st.session_state.ia = IA_Deslocamento(janela=12)
    historico = carregar_historico()
    for n in historico:
        st.session_state.estrategia.adicionar_numero(n)
    st.session_state.ia.atualizar_historico(st.session_state.estrategia.historico)
    st.session_state.previsao = []
    st.session_state.previsao_enviada = False
    st.session_state.resultado_enviado = False
    st.session_state.acertos = 0
    st.session_state.erros = 0

# Slider da janela
janela = st.slider("📏 Tamanho da janela (nº de sorteios considerados)", min_value=6, max_value=500, value=12, step=1)
st.session_state.ia.janela = janela

# Captura número
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    st.session_state.ia.atualizar_historico(st.session_state.estrategia.historico)

    # Conferir resultado
    if st.session_state.previsao and not st.session_state.resultado_enviado:
        if numero_dict["number"] in st.session_state.previsao:
            enviar_msg(f"🟢 GREEN! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.acertos += 1
            tocar_som_moeda()
        else:
            enviar_msg(f"🔴 RED! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.erros += 1
        st.session_state.resultado_enviado = True
        st.session_state.previsao_enviada = False

    # Nova previsão usando IA
    # Nova previsão usando IA
    prox_numeros = st.session_state.ia.prever(st.session_state.estrategia.historico, top_n=10)
    if prox_numeros and not st.session_state.previsao_enviada:
        st.session_state.previsao = prox_numeros
        st.session_state.previsao_enviada = True
        st.session_state.resultado_enviado = False

        linha1 = " ".join(str(n) for n in prox_numeros[:5])
        linha2 = " ".join(str(n) for n in prox_numeros[5:])
        msg_alerta = f"🎯 Próximos números prováveis:\n{linha1}\n{linha2}"
        enviar_msg(msg_alerta, tipo="previsao")

# --- Histórico ---
st.subheader("📜 Histórico (últimos 20 números)")
st.write(list(st.session_state.estrategia.historico)[-20:])

# --- Estatísticas ---
total = st.session_state.acertos + st.session_state.erros
taxa = (st.session_state.acertos / total * 100) if total > 0 else 0.0
col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", st.session_state.acertos)
col2.metric("🔴 RED", st.session_state.erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")

# --- Inserir sorteios manualmente ---
entrada = st.text_area(
    "Digite números (0–36), separados por espaço — até 100:",
    height=100,
    key="entrada_manual"
)

if st.button("Adicionar Sorteios"):
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        if len(nums) > 100:
            st.warning("Limite de 100 números.")
        else:
            for n in nums:
                numero_dict = {"number": n, "timestamp": f"manual_{len(st.session_state.estrategia.historico)}"}
                st.session_state.estrategia.adicionar_numero(numero_dict)
                salvar_historico(list(st.session_state.estrategia.historico))
                st.session_state.ia.atualizar_historico(st.session_state.estrategia.historico)

                # Conferir resultado manual
                if st.session_state.previsao and not st.session_state.resultado_enviado:
                    if n in st.session_state.previsao:
                        enviar_msg(f"🟢 GREEN! Saiu {n}", tipo="resultado")
                        st.session_state.acertos += 1
                        tocar_som_moeda()
                    else:
                        enviar_msg(f"🔴 RED! Saiu {n}", tipo="resultado")
                        st.session_state.erros += 1
                    st.session_state.resultado_enviado = True
                    st.session_state.previsao_enviada = False

            st.success(f"{len(nums)} números adicionados com sucesso!")

    except Exception as e:
        st.error(f"Erro ao adicionar números: {e}")

