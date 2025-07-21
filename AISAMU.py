
import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_FILE = "historico_sorteios.pkl"
ROULETTE_ORDER = [26,3,35,12,28,7,29,18,22,9,31,14,20,1,33,16,24,5,10,23,8,30,11,36,13,27,6,34,17,25,2,21,4,19,15,32,0]

# === FUNÇÕES AUXILIARES ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        return joblib.load(HISTORICO_FILE)
    return deque(maxlen=300)

def salvar_historico(historico):
    joblib.dump(historico, HISTORICO_FILE)

def extrair_numero(resultado):
    try:
        return int(resultado["outcome"]["number"])
    except:
        return None

def get_vizinhos(numero, n=2):
    vizinhos = []
    if numero not in ROULETTE_ORDER:
        return vizinhos
    idx = ROULETTE_ORDER.index(numero)
    for i in range(-n, n+1):
        vizinhos.append(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return vizinhos

# === STREAMLIT CONFIG ===
st.set_page_config(page_title="IA Estratégia Roleta", layout="centered")
st.title("🎯 Estratégia IA - Roleta")

# Auto refresh a cada 10s
st_autorefresh(interval=10 * 1000, key="refresh")

# === HISTÓRICO ===
historico = carregar_historico()
ultimo_timestamp = st.session_state.get("ultimo_timestamp")

# === CAPTURA DA API ===
try:
    response = requests.get(API_URL, timeout=10)
    resultado = response.json()
    numero = extrair_numero(resultado)
    timestamp = resultado["startedAt"]
except Exception as e:
    st.error(f"Erro ao acessar API: {e}")
    st.stop()

if timestamp != ultimo_timestamp:
    historico.append(numero)
    salvar_historico(historico)
    st.session_state.ultimo_timestamp = timestamp

st.markdown(f"🎲 Último número: **{numero}**")
st.markdown(f"🕒 Timestamp: `{timestamp}`")
st.markdown(f"📋 Histórico ({len(historico)}): {list(historico)}")

# === ESCOLHA DE ESTRATÉGIA DINÂMICA ===
entrada = None
estrategia = None
mensagem_extra = ""

# Estratégia 1 - Terminais fixos 2, 6, 9
if numero is not None and str(numero)[-1] in ["2", "6", "9"]:
    entrada_base = [31, 34]
    entrada = []
    for n in entrada_base:
        entrada.extend(get_vizinhos(n, 5))
    entrada = list(set(entrada))[:10]
    estrategia = "Terminais 2/6/9"

# Estratégia 2 - Número 4, 14, 24, 34 ativa fixos 1 e 2 com maior probabilidade
elif numero in [4,14,24,34]:
    candidatos = [1,2]
    scores = {}
    for c in candidatos:
        scores[c] = historico.count(c)
    escolhidos = sorted(scores, key=scores.get, reverse=True)
    entrada = []
    for n in escolhidos:
        entrada.extend(get_vizinhos(n, 5))
    entrada = list(set(entrada))[:10]
    estrategia = "Gatilho 4/14/24/34 (1 e 2)"

# Estratégia 3 - Terminais dominantes
elif len(historico) >= 13:
    ultimos_12 = list(historico)[-13:-1]
    terminais = [str(n)[-1] for n in ultimos_12]
    contagem = Counter(terminais)
    dominantes = [int(t) for t, c in contagem.items() if c > 2]
    if dominantes:
        base = []
        for d in dominantes:
            base += [n for n in range(37) if str(n).endswith(str(d))]
        entrada = []
        for n in base:
            entrada.extend(get_vizinhos(n, 2))
        entrada = list(set(entrada))[:10]
        if numero in ultimos_12 or numero in entrada:
            estrategia = "Terminais dominantes"
            mensagem_extra = "(Gatilho validado)"
        else:
            entrada = None

# # === ALERTA ===
if entrada and estrategia:
    msg = f"Estratégia: {estrategia}\nEntrada: {sorted(entrada)}\n{mensagem_extra}"
    enviar_telegram(msg)
    st.success("✅ Entrada gerada e enviada ao Telegram!")
    st.markdown(f"**{estrategia}** — Entrada enviada: `{sorted(entrada)}`")
else:
    st.info("Aguardando condições para gerar nova entrada.")
