import streamlit as st
import requests
import os
import joblib
import random
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_FILE = "historico_sorteios.pkl"
ACERTOS_FILE = "contador_acertos.pkl"
ROULETTE_ORDER = [26,3,35,12,28,7,29,18,22,9,31,14,20,1,33,16,24,5,10,
                  23,8,30,11,36,13,27,6,34,17,25,2,21,4,19,15,32,0]

# === FUNÇÕES ===
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

def carregar_acertos():
    if os.path.exists(ACERTOS_FILE):
        return joblib.load(ACERTOS_FILE)
    return 0

def salvar_acertos(valor):
    joblib.dump(valor, ACERTOS_FILE)

def get_vizinhos(numero, n=2):
    if numero not in ROULETTE_ORDER:
        return []
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-n, n+1)]

# === INTERFACE STREAMLIT ===
st.set_page_config(page_title="IA Estratégia Roleta", layout="centered")
st.title("🎯 Estratégia IA - Roleta")

st_autorefresh(interval=10 * 1000, key="refresh")
historico = carregar_historico()
acertos = carregar_acertos()

# Estado do número anterior
if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None

# Seletor de estratégias
st.sidebar.header("🎛️ Estratégias Ativadas")
usar_estrategia_1 = st.sidebar.checkbox("Terminais 2/6/9", value=True)
usar_estrategia_2 = st.sidebar.checkbox("Gatilho 4/14/24/34", value=True)
usar_estrategia_3 = st.sidebar.checkbox("Terminais Dominantes", value=True)
st.sidebar.markdown(f"✅ **Total de GREENs:** `{acertos}`")

# === CAPTURA DA API ===
try:
    response = requests.get(API_URL, timeout=10)
    data = response.json()
    numero = int(data["data"]["result"]["outcome"]["number"])
    timestamp = data["data"]["settledAt"]

    if numero != st.session_state.ultimo_numero:
        historico.append(numero)
        salvar_historico(historico)
        st.session_state.ultimo_numero = numero
        st.success(f"🎲 Último número: **{numero}** às {timestamp}")

        entrada = None
        estrategia = None
        mensagem_extra = ""

        # Estratégia 1: Terminais 2, 6, 9
        if usar_estrategia_1 and str(numero)[-1] in ["2", "6", "9"]:
            base = [31, 34]
            entrada = []
            for b in base:
                entrada.extend(get_vizinhos(b, 5))
            entrada = list(set(entrada))
            random.shuffle(entrada)
            entrada = entrada[:10]
            estrategia = "Terminais 2/6/9"

        # Estratégia 2: Número 4, 14, 24, 34 ativa 1 e 2
        elif usar_estrategia_2 and numero in [4, 14, 24, 34]:
            candidatos = [1, 2]
            scores = {c: historico.count(c) for c in candidatos}
            escolhidos = sorted(scores, key=scores.get, reverse=True)
            entrada = []
            for e in escolhidos:
                entrada.extend(get_vizinhos(e, 5))
            entrada = list(set(entrada))
            random.shuffle(entrada)
            entrada = entrada[:10]
            estrategia = "Gatilho 4/14/24/34 (1 e 2)"

        # Estratégia 3: Terminais dominantes
        elif usar_estrategia_3 and len(historico) >= 13:
            ultimos_12 = list(historico)[-13:-1]
            terminais = [str(n)[-1] for n in ultimos_12]
            contagem = Counter(terminais)
            dominantes = [int(t) for t, c in contagem.items() if c > 2]
            if dominantes:
                base = []
                for d in dominantes:
                    base.extend([n for n in range(37) if str(n).endswith(str(d))])
                entrada = []
                for n in base:
                    entrada.extend(get_vizinhos(n, 2))
                entrada = list(set(entrada))
                random.shuffle(entrada)
                entrada = entrada[:10]
                if numero in ultimos_12 or numero in entrada:
                    estrategia = "Terminais dominantes"
                    mensagem_extra = "(Gatilho validado)"
                else:
                    entrada = None

        # === ALERTA E CHECAGEM DE GREEN ===
        if entrada and estrategia:
            msg = f"🎯 Estratégia: {estrategia}\n🎲 Entrada: {sorted(entrada)}\n{mensagem_extra}"
            enviar_telegram(msg)
            st.success("✅ Entrada gerada e enviada ao Telegram!")
            st.markdown(f"**{estrategia}** — Entrada: `{sorted(entrada)}`")

            # Verifica se o número atual está na entrada anterior (GREEN)
            if numero in entrada:
                acertos += 1
                salvar_acertos(acertos)
                st.balloons()
                st.success("🎉 GREEN confirmado!")
        else:
            st.info("Aguardando condições para gerar nova entrada.")
    else:
        st.warning("⏳ Aguardando novo número...")

except Exception as e:
    st.error(f"Erro ao acessar API: {e}")
