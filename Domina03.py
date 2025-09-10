import streamlit as st
import json
import os
import requests
from collections import deque, Counter
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

COLOR_MAP = {0:"green",1:"red",2:"black",3:"red",4:"black",5:"red",6:"black",
             7:"red",8:"black",9:"red",10:"black",11:"black",12:"red",13:"black",
             14:"red",15:"black",16:"red",17:"black",18:"red",19:"red",20:"black",
             21:"red",22:"black",23:"red",24:"black",25:"red",26:"black",27:"red",
             28:"black",29:"black",30:"red",31:"black",32:"red",33:"black",34:"red",
             35:"black",36:"red"}

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

def obter_vizinhos(numero, layout, antes=2, depois=2):
    """Retorna o número + vizinhos físicos na roleta"""
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

def setor_fisico(numero):
    idx = ROULETTE_LAYOUT.index(numero)
    n = len(ROULETTE_LAYOUT)
    terco = n // 3
    if idx < terco:
        return 0
    elif idx < 2*terco:
        return 1
    else:
        return 2

def extrair_features(historico, janela=30):
    """Extrai features avançadas para IA"""
    ultimos = [h["number"] for h in list(historico)[-janela:]]
    features = []
    for i in range(len(ultimos)-1):
        atual = ultimos[i]
        prox = ultimos[i+1]
        delta = (ROULETTE_LAYOUT.index(prox) - ROULETTE_LAYOUT.index(atual)) % len(ROULETTE_LAYOUT)
        if delta > len(ROULETTE_LAYOUT)//2:
            delta -= len(ROULETTE_LAYOUT)
        features.append([
            delta,
            COLOR_MAP[atual],
            atual % 2,          # par/ímpar
            setor_fisico(atual),
            ultimos[max(0,i-2):i+1].count(atual)  # frequência recente
        ])
    X = [f[:-1] for f in features]
    y = [f[-1] for f in features]
    return X, y

# =============================
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)

    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA otimizada profissional
# =============================
class IA_Deslocamento_Fisico_Pro:
    def __init__(self, layout=None, janela=30, top_n_deltas=3):
        self.layout = layout or ROULETTE_LAYOUT
        self.janela = janela
        self.top_n_deltas = top_n_deltas
        self.model = RandomForestClassifier(n_estimators=600)
        self.treinado = False

    def atualizar_historico(self, historico):
        if len(historico) < self.janela:
            return
        X, y = extrair_features(historico, self.janela)
        if X:
            self.model.fit(X, y)
            self.treinado = True

    def prever(self, historico):
        if not self.treinado or len(historico) < self.janela:
            return []
        X, _ = extrair_features(historico, self.janela)
        probs = self.model.predict_proba([X[-1]])[0]
        classes = self.model.classes_
        top_indices = np.argsort(probs)[::-1][:self.top_n_deltas]
        top_deltas = [classes[i] for i in top_indices]
        ultimo_numero = [h["number"] for h in list(historico)[-1:]][0]
        pos_atual = self.layout.index(ultimo_numero)
        numeros_previstos = []
        for delta in top_deltas:
            n = self.layout[(pos_atual + delta) % len(self.layout)]
            vizinhos = obter_vizinhos(n, self.layout, antes=2, depois=2)
            for v in vizinhos:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)
        return numeros_previstos[:self.top_n_deltas*5]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA de Deslocamento Físico Profissional")
st_autorefresh(interval=3000, key="refresh")

# Inicialização
if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()
    st.session_state.ia = IA_Deslocamento_Fisico_Pro(janela=30)
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
janela = st.slider("📏 Tamanho da janela (nº de sorteios considerados)", min_value=6, max_value=50, value=30, step=1)
st.session_state.ia.janela = janela

# Captura número
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    st.session_state.ia.atualizar_historico(st.session_state.estrategia.historico)

    # Conferir resultado anterior
    if st.session_state.previsao:
        if numero_dict["number"] in st.session_state.previsao:
            enviar_msg(f"🟢 GREEN! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.acertos += 1
            tocar_som_moeda()
        else:
            enviar_msg(f"🔴 RED! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.erros += 1

    # Nova previsão
    prox_numeros = st.session_state.ia.prever(st.session_state.estrategia.historico)
    if prox_numeros:
        st.session_state.previsao = prox_numeros
        st.session_state.previsao_enviada = True
        msg_alerta = "🎯 Próximos números prováveis: " + " ".join(str(n) for n in prox_numeros)
        enviar_msg(msg_alerta, tipo="previsao")

# Histórico
st.subheader("📜 Histórico (últimos 20 números)")
st.write(list(st.session_state.estrategia.historico)[-20:])

# Estatísticas
total = st.session_state.acertos + st.session_state.erros
taxa = (st.session_state.acertos / total * 100) if total > 0 else 0.0
col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", st.session_state.acertos)
col2.metric("🔴 RED", st.session_state.erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")
