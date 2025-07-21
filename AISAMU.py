import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_FILE = "historico_sorteios.pkl"
STATUS_FILE = "status_estrategias.pkl"

ROULETTE_ORDER = [26,3,35,12,28,7,29,18,22,9,31,14,20,1,33,16,24,5,10,
                  23,8,30,11,36,13,27,6,34,17,25,2,21,4,19,15,32,0]

ESTRATEGIAS = {
    "Terminais 2/6/9": True,
    "Gatilho 4/14/24/34": True,
    "Terminais dominantes": True
}

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

def carregar_status():
    if os.path.exists(STATUS_FILE):
        return joblib.load(STATUS_FILE)
    return {}

def salvar_status(status):
    joblib.dump(status, STATUS_FILE)

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
status_estrategias = carregar_status()

# Estado inicial
if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None
if "ultima_entrada" not in st.session_state:
    st.session_state.ultima_entrada = None
if "ultima_estrategia" not in st.session_state:
    st.session_state.ultima_estrategia = None

# === SELETOR DE ESTRATÉGIAS ===
st.sidebar.title("⚙️ Estratégias Ativas")
estrategias_ativas = {}
for nome in ESTRATEGIAS:
    estrategias_ativas[nome] = st.sidebar.checkbox(nome, value=True)

# === CAPTURA DA API ===
try:
    response = requests.get(API_URL, timeout=10)
    data = response.json()
    numero = int(data["data"]["result"]["outcome"]["number"])
    timestamp = data["data"]["settledAt"]

    st.markdown(f"🎲 Último número: **{numero}** às `{timestamp}`")

    if numero != st.session_state.ultimo_numero:
        historico.append(numero)
        salvar_historico(historico)

        entrada = None
        estrategia = None
        mensagem_extra = ""

        # === ESTRATÉGIA 1 ===
        if estrategias_ativas["Terminais 2/6/9"] and str(numero)[-1] in ["2", "6", "9"]:
            base = [31, 34]
            entrada = set()
            for b in base:
                entrada.update(get_vizinhos(b, 5))
            entrada = sorted(list(entrada))[:10]
            estrategia = "Terminais 2/6/9"

        # === ESTRATÉGIA 2 ===
        elif estrategias_ativas["Gatilho 4/14/24/34"] and numero in [4, 14, 24, 34]:
            candidatos = [1, 2]
            scores = {c: historico.count(c) for c in candidatos}
            escolhidos = sorted(scores, key=scores.get, reverse=True)
            entrada = set()
            for e in escolhidos:
                entrada.update(get_vizinhos(e, 5))
            entrada = sorted(list(entrada))[:10]
            estrategia = "Gatilho 4/14/24/34"

        # === ESTRATÉGIA 3 ===
        elif estrategias_ativas["Terminais dominantes"] and len(historico) >= 13:
            ultimos_12 = list(historico)[-13:-1]
            terminais = [str(n)[-1] for n in ultimos_12]
            contagem = Counter(terminais)
            dominantes = [int(t) for t, c in contagem.items() if c > 2]
            if dominantes:
                base = []
                for d in dominantes:
                    base.extend([n for n in range(37) if str(n).endswith(str(d))])
                entrada = set()
                for n in base:
                    entrada.update(get_vizinhos(n, 2))
                entrada = sorted(list(entrada))[:10]
                if numero in ultimos_12 or numero in entrada:
                    estrategia = "Terminais dominantes"
                    mensagem_extra = "(Gatilho validado)"
                else:
                    entrada = None

        # === VERIFICAÇÃO DE GREEN/RED ===
        if st.session_state.ultima_entrada and st.session_state.ultima_estrategia:
            anterior_entrada = st.session_state.ultima_entrada
            anterior_estrategia = st.session_state.ultima_estrategia

            acerto = "GREEN" if numero in anterior_entrada else "RED"
            if anterior_estrategia not in status_estrategias:
                status_estrategias[anterior_estrategia] = {"GREEN": 0, "RED": 0}
            status_estrategias[anterior_estrategia][acerto] += 1
            salvar_status(status_estrategias)

        # === ALERTA ===
        if entrada and estrategia:
            st.session_state.ultima_entrada = entrada
            st.session_state.ultima_estrategia = estrategia
            msg = f"Estratégia: {estrategia}\nEntrada: {sorted(entrada)}\n{mensagem_extra}"
            enviar_telegram(msg)
            st.success("✅ Entrada gerada e enviada ao Telegram!")
            st.markdown(f"**{estrategia}** — Entrada: `{entrada}`")
        else:
            st.session_state.ultima_entrada = None
            st.session_state.ultima_estrategia = None
            st.info("Aguardando condições para nova entrada.")

        st.session_state.ultimo_numero = numero

    else:
        st.warning("⏳ Aguardando novo número...")

except Exception as e:
    st.error(f"Erro ao acessar API: {e}")

# === EXIBIR STATUS GERAL ===
st.markdown("---")
st.header("📊 Desempenho das Estratégias")
for nome, dados in status_estrategias.items():
    g = dados.get("GREEN", 0)
    r = dados.get("RED", 0)
    total = g + r
    taxa = (g / total * 100) if total > 0 else 0
    st.markdown(f"**{nome}** — GREEN: `{g}` | RED: `{r}` | ✅ Taxa: **{taxa:.1f}%**")
