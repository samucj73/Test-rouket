import streamlit as st
import json
import os
import requests
from collections import deque
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import numpy as np
import logging

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002940111195"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# =============================
# Funções auxiliares
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
    )
    st.markdown(
        f"""
        <audio autoplay>
            <source src="data:audio/mp3;base64,{som_base64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            historico = json.load(f)
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
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)

    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA de deslocamento físico profissional
# =============================
class IA_Deslocamento_Fisico_Pro:
    def __init__(self, layout=None, janela=12, top_n_deltas=3, max_numeros=7):
        self.layout = layout or ROULETTE_LAYOUT
        self.janela = janela
        self.top_n_deltas = top_n_deltas
        self.max_numeros = max_numeros
        self.model = RandomForestClassifier(n_estimators=400)
        self.X = []
        self.y = []
        self.treinado = False

    def _calcular_deslocamentos(self, numeros):
        deltas = []
        n = len(self.layout)
        for i in range(1, len(numeros)):
            pos_anterior = self.layout.index(numeros[i-1])
            pos_atual = self.layout.index(numeros[i])
            
            # diferença circular (0 → n-1)
            delta = (pos_atual - pos_anterior) % n
            
            # ajusta para o menor deslocamento possível
            if delta > n // 2:
                delta -= n   
            deltas.append(delta)
        return deltas

    

    def atualizar_historico(self, historico):
        ultimos = [h["number"] for h in historico]
        if len(ultimos) <= self.janela:
            return
        self.X = []
        self.y = []
        deltas = self._calcular_deslocamentos(ultimos)
        for i in range(len(deltas) - self.janela + 1):
            janela_deltas = deltas[i:i+self.janela-1]
            proximo_delta = deltas[i+self.janela-1]
            self.X.append(janela_deltas)
            self.y.append(proximo_delta)
        if self.X:
            self.model.fit(self.X, self.y)
            self.treinado = True

    def prever(self, historico):
        if not self.treinado or len(historico) < self.janela:
            return []

        ultimos = [h["number"] for h in list(historico)[-self.janela:]]
        ultimos_deltas = self._calcular_deslocamentos(ultimos)
        probs = self.model.predict_proba([ultimos_deltas])[0]
        classes = self.model.classes_

        top_indices = np.argsort(probs)[::-1][:self.top_n_deltas]
        top_deltas = [classes[i] for i in top_indices]

        ultimo_numero = ultimos[-1]
        pos_atual = self.layout.index(ultimo_numero)

        numeros_previstos = []
        for delta in top_deltas:
            n = self.layout[(pos_atual + delta) % len(self.layout)]
            numeros_previstos.append(n)
            idx = self.layout.index(n)

            # Inclui vizinhos e vizinhos dos vizinhos
            vizinhos = [
                self.layout[(idx - 1) % len(self.layout)],
                self.layout[(idx + 1) % len(self.layout)],
                self.layout[(idx - 2) % len(self.layout)],
                self.layout[(idx + 2) % len(self.layout)]
            ]
            numeros_previstos.extend(vizinhos)

        # Remove duplicados e limita a quantidade final
        numeros_previstos = list(dict.fromkeys(numeros_previstos))[:self.max_numeros]
        return numeros_previstos

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA de Deslocamento Físico Profissional")

st_autorefresh(interval=3000, key="refresh")

# Inicialização
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()
    st.session_state.ia = IA_Deslocamento_Fisico_Pro(janela=12)
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
janela = st.slider("📏 Tamanho da janela (nº de sorteios considerados)", min_value=6, max_value=50, value=12, step=1)
st.session_state.ia.janela = janela

# Captura número
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    st.session_state.ia.atualizar_historico(st.session_state.estrategia.historico)

    # --- Conferir resultado da previsão anterior ---
    if st.session_state.previsao:
        if numero_dict["number"] in st.session_state.previsao:
            enviar_msg(f"🟢 GREEN! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.acertos += 1
        else:
            enviar_msg(f"🔴 RED! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.erros += 1

    # --- Nova previsão para o próximo número ---
    prox_numeros = st.session_state.ia.prever(st.session_state.estrategia.historico)
    if prox_numeros:
        st.session_state.previsao = prox_numeros
        st.session_state.previsao_enviada = True
        msg_alerta = "🎯 Próximos números prováveis: " + " ".join(str(n) for n in prox_numeros)
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
