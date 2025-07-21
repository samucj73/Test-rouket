import streamlit as st
import requests
import time
import os
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = "historico.txt"

# === REMOVER DUPLICATAS MANTENDO ORDEM ===
def remover_duplicatas_mantendo_ordem(lista):
    seen = set()
    return [x for x in lista if not (x in seen or seen.add(x))]

# === ORDEM FÍSICA DA ROLETA ===
ordem_fisica = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8,
    23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28,
    12, 35, 3, 26
]

def get_vizinhos(numero, qtd=2):
    if numero not in ordem_fisica:
        return []
    idx = ordem_fisica.index(numero)
    total = len(ordem_fisica)
    vizinhos = []
    for i in range(-qtd, qtd+1):
        vizinhos.append(ordem_fisica[(idx + i) % total])
    return vizinhos

def enviar_telegram(mensagem):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
        )
    except:
        pass

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            return deque([int(x) for x in f.read().split(",") if x], maxlen=500)
    return deque(maxlen=500)

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        f.write(",".join(str(x) for x in historico))

# === STREAMLIT ===
st.set_page_config(layout="wide")
st.title("🎯 Estratégias Inteligentes - Roleta Europeia")

# Autorefresh a cada 7 segundos
st_autorefresh(interval=7000, key="refresh")

# Sessão
if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()

if "ultimo_id" not in st.session_state:
    st.session_state.ultimo_id = None

if "acertos" not in st.session_state:
    st.session_state.acertos = 0

# Seleção de estratégias
estrategias_disponiveis = [
    "Terminais 2/6/9",
    "Gatilho 4/14/24/34 (1 e 2)",
    "Terminais dominantes"
]
estrategias_ativas = st.multiselect("🎯 Escolha as estratégias ativas:", estrategias_disponiveis, default=estrategias_disponiveis)

# Coleta o número atual
try:
    r = requests.get(API_URL).json()
    numero = int(r["data"]["outcome"]["number"])
    ts = r["data"]["settledAt"]
    id_unico = r["data"]["id"]
except:
    st.warning("Erro ao acessar a API.")
    st.stop()

# Verifica se é novo
if id_unico != st.session_state.ultimo_id:
    st.session_state.ultimo_id = id_unico
    st.session_state.historico.append(numero)
    salvar_historico(st.session_state.historico)

    historico = st.session_state.historico
    entrada = None
    estrategia = None
    mensagem_extra = ""

    # Estratégia 1 - Terminais 2/6/9
    if "Terminais 2/6/9" in estrategias_ativas and str(numero)[-1] in ["2", "6", "9"]:
        base = [31, 34]
        entrada = []
        for b in base:
            entrada.extend(get_vizinhos(b, 5))
        entrada = remover_duplicatas_mantendo_ordem(entrada)[:10]
        estrategia = "Terminais 2/6/9"

    # Estratégia 2 - Gatilho 4/14/24/34
    elif "Gatilho 4/14/24/34 (1 e 2)" in estrategias_ativas and numero in [4, 14, 24, 34]:
        candidatos = [1, 2]
        scores = {c: historico.count(c) for c in candidatos}
        escolhidos = sorted(scores, key=scores.get, reverse=True)
        entrada = []
        for e in escolhidos:
            entrada.extend(get_vizinhos(e, 5))
        entrada = remover_duplicatas_mantendo_ordem(entrada)[:10]
        estrategia = "Gatilho 4/14/24/34 (1 e 2)"

    # Estratégia 3 - Terminais dominantes
    elif "Terminais dominantes" in estrategias_ativas and len(historico) >= 13:
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
            entrada = remover_duplicatas_mantendo_ordem(entrada)[:10]
            if numero in ultimos_12 or numero in entrada:
                estrategia = "Terminais dominantes"
                mensagem_extra = "(Gatilho validado)"
            else:
                entrada = None

    # Checagem de acerto
    if entrada:
        status = "✅ GREEN!" if numero in entrada else "❌ RED"
        if numero in entrada:
            st.session_state.acertos += 1

        mensagem = (
            f"🎯 Estratégia: {estrategia} {mensagem_extra}\n"
            f"🎲 Último número: {numero}\n"
            f"🎯 Entrada sugerida: {entrada}\n"
            f"{status}\n"
            f"🔥 Acertos totais: {st.session_state.acertos}"
        )
        enviar_telegram(mensagem)
        st.success(mensagem)
    else:
        st.info(f"Número: {numero} | Estratégia ignorada ou sem gatilho.")
else:
    st.info("⏳ Aguardando novo número...")

# Exibe histórico
st.subheader("📜 Últimos 30 números")
st.write(list(st.session_state.historico)[-30:])
