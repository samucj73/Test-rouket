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

# Canal da estratégia física
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002940111195"

# Canal da estratégia recorrência
TELEGRAM_TOKEN_RECORRENCIA = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID_RECORRENCIA = "5121457416"

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

def enviar_telegram_recorrencia(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_RECORRENCIA}/sendMessage"
        payload = {"chat_id": CHAT_ID_RECORRENCIA, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar recorrência: {e}")

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
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

# =============================
# Estratégia recorrência
# =============================
class EstrategiaRecorrencia:
    def __init__(self, top_n=5):
        self.top_n = top_n
        self.ultima_previsao = []
        self.acertos = 0
        self.erros = 0

    def prever(self, historico):
        if len(historico) < 2:
            return []
        ultimo_numero = historico[-1]["number"]
        sequencias = []
        for i in range(len(historico)-1):
            if historico[i]["number"] == ultimo_numero:
                sequencias.append(historico[i+1]["number"])
        if not sequencias:
            return []
        contagem = Counter(sequencias)
        mais_comuns = [n for n, _ in contagem.most_common(self.top_n)]
        self.ultima_previsao = mais_comuns
        return mais_comuns

    def conferir(self, numero_sorteado):
        if not self.ultima_previsao:
            return None
        if numero_sorteado in self.ultima_previsao:
            self.acertos += 1
            return True
        else:
            self.erros += 1
            return False

# =============================
# Estratégia física existente
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

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
        X, y = [], []
        ultimos = [h["number"] for h in list(historico)[-self.janela:]]
        for i in range(len(ultimos)-1):
            pos_anterior = self.layout.index(ultimos[i])
            pos_atual = self.layout.index(ultimos[i+1])
            delta = (pos_atual - pos_anterior) % len(self.layout)
            if delta > len(self.layout)//2:
                delta -= len(self.layout)
            X.append([delta])
            y.append(delta)
        if X:
            self.model.fit(X, y)
            self.treinado = True

    def prever(self, historico):
        if not self.treinado or len(historico) < self.janela:
            return []
        ultimos = [h["number"] for h in list(historico)[-self.janela:]]
        pos_anterior = self.layout.index(ultimos[-2])
        pos_atual = self.layout.index(ultimos[-1])
        delta = (pos_atual - pos_anterior) % len(self.layout)
        if delta > len(self.layout)//2:
            delta -= len(self.layout)
        probs = self.model.predict_proba([[delta]])[0]
        classes = self.model.classes_
        top_indices = np.argsort(probs)[::-1][:self.top_n_deltas]
        top_deltas = [classes[i] for i in top_indices]
        ultimo_numero = ultimos[-1]
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
st.title("🎯 Roleta — IA de Deslocamento + Recorrência")
st_autorefresh(interval=3000, key="refresh")

# Inicialização segura do session_state
for key, default in {
    "estrategia": EstrategiaDeslocamento(),
    "ia": IA_Deslocamento_Fisico_Pro(janela=30),
    "recorrencia": EstrategiaRecorrencia(top_n=5),
    "previsao": [],
    "previsao_enviada": False,
    "resultado_enviado": False,
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)
st.session_state.ia.atualizar_historico(st.session_state.estrategia.historico)

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

    # Incrementa contador de rodadas
    st.session_state.contador_rodadas += 1

    # Conferir resultado anterior da estratégia física
    if st.session_state.previsao:
        if numero_dict["number"] in st.session_state.previsao:
            enviar_msg(f"🟢 GREEN! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.acertos += 1
            tocar_som_moeda()
        else:
            enviar_msg(f"🔴 RED! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.erros += 1

    # Nova previsão a cada 2 rodadas (estratégia física)
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros
            st.session_state.previsao_enviada = True
            msg_alerta = "🎯 Física — Próximos números prováveis: " + " ".join(str(n) for n in prox_numeros)
            enviar_msg(msg_alerta, tipo="previsao")

    # Estratégia recorrência (roda sempre)
    previsao_recorrencia = st.session_state.recorrencia.prever(list(st.session_state.estrategia.historico))
    if previsao_recorrencia:
        enviar_telegram_recorrencia("♻️ Recorrência — Top 5: " + " ".join(str(n) for n in previsao_recorrencia))

    # Conferir resultado recorrência
    resultado_rec = st.session_state.recorrencia.conferir(numero_dict["number"])
    if resultado_rec is True:
        enviar_telegram_recorrencia(f"🟢 GREEN Recorrência! Saiu {numero_dict['number']}")
    elif resultado_rec is False:
        enviar_telegram_recorrencia(f"🔴 RED Recorrência! Saiu {numero_dict['number']}")

# Histórico
st.subheader("📜 Histórico (últimos 20 números)")
st.write(list(st.session_state.estrategia.historico)[-20:])

# Estatísticas
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN (Física)", acertos)
col2.metric("🔴 RED (Física)", erros)
col3.metric("✅ Taxa Física", f"{taxa:.1f}%")

# Estatísticas recorrência
acertos_rec = st.session_state.recorrencia.acertos
erros_rec = st.session_state.recorrencia.erros
total_rec = acertos_rec + erros_rec
taxa_rec = (acertos_rec / total_rec * 100) if total_rec > 0 else 0.0

col4, col5, col6 = st.columns(3)
col4.metric("🟢 GREEN (Recorrência)", acertos_rec)
col5.metric("🔴 RED (Recorrência)", erros_rec)
col6.metric("✅ Taxa Recorrência", f"{taxa_rec:.1f}%")
