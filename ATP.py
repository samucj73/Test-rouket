import streamlit as st
import requests
import json
import os
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico.json"
ULTIMO_TIMESTAMP_PATH = "ultimo_timestamp.txt"

# === ROTAÇÃO DA ROLETA EUROPEIA ===
ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30,
    8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7,
    28, 12, 35, 3, 26
]

# === FUNÇÕES AUXILIARES ===

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data)
    except:
        pass

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            return json.load(f)
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f)

def carregar_timestamp():
    if os.path.exists(ULTIMO_TIMESTAMP_PATH):
        with open(ULTIMO_TIMESTAMP_PATH, "r") as f:
            return f.read().strip()
    return ""

def salvar_timestamp(ts):
    with open(ULTIMO_TIMESTAMP_PATH, "w") as f:
        f.write(ts)

def obter_numero_e_timestamp():
    try:
        resp = requests.get(API_URL)
        if resp.status_code == 200:
            dados = resp.json()["data"]["result"]["outcome"]
            numero = dados["number"]
            timestamp = resp.json()["data"]["createdDate"]
            return numero, timestamp
    except:
        return None, None
    return None, None

def obter_terminal(numero):
    return numero % 10

def obter_numeros_terminal(terminal):
    return [n for n in range(37) if n % 10 == terminal]

def vizinhos(numero):
    idx = ROULETTE_NUMBERS.index(numero)
    return [
        ROULETTE_NUMBERS[(idx - 2) % len(ROULETTE_NUMBERS)],
        ROULETTE_NUMBERS[(idx - 1) % len(ROULETTE_NUMBERS)],
        ROULETTE_NUMBERS[(idx + 1) % len(ROULETTE_NUMBERS)],
        ROULETTE_NUMBERS[(idx + 2) % len(ROULETTE_NUMBERS)],
    ]

def formatar_linhas(numeros):
    linhas = [numeros[i:i+5] for i in range(0, len(numeros), 5)]
    return "\n".join(" - ".join(str(n) for n in linha) for linha in linhas)

# === INÍCIO DO APP ===

st.set_page_config(layout="centered")
st.title("🎯 Estratégia de Roleta – Terminais Dominantes")

# Autorefresh a cada 5 segundos
st_autorefresh(interval=5000, key="datarefresh")

# Histórico e controle
historico = carregar_historico()
ultimo_timestamp = carregar_timestamp()

# Estado da estratégia
estado = st.session_state.get("estado", "coletando")
entrada_principal = st.session_state.get("entrada_principal", [])
vizinhos_entrada = st.session_state.get("vizinhos_entrada", [])
numeros_usados_para_entrada = st.session_state.get("numeros_usados_para_entrada", [])

# Obter novo número
numero, timestamp = obter_numero_e_timestamp()
if numero and timestamp != ultimo_timestamp:
    historico.append(numero)
    salvar_historico(historico)
    salvar_timestamp(timestamp)

# Exibição dos últimos 15
st.subheader("📊 Últimos Números")
ultimos_15 = historico[-15:]
cores = {num: "green" if num in entrada_principal else "white" for num in ultimos_15}

linhas = [ultimos_15[i:i+5] for i in range(0, len(ultimos_15), 5)]
for linha in linhas:
    st.markdown(
        "<div style='font-size: 22px; margin-bottom: 5px;'>"
        + " - ".join(
            f"<span style='color:{'green' if n in entrada_principal else 'white'};'>{n:02d}</span>"
            for n in linha
        )
        + "</div>",
        unsafe_allow_html=True
    )

# Estratégia
if estado == "coletando" and len(historico) >= 12:
    ultimos_12 = historico[-12:]
    terminais = [obter_terminal(n) for n in ultimos_12]
    contagem = Counter(terminais)
    dominantes = [t for t, c in contagem.most_common(2)]

    if len(dominantes) == 2:
        entrada_principal = []
        vizinhos_entrada = []
        for t in dominantes:
            nums = obter_numeros_terminal(t)
            entrada_principal.extend(nums)
            for n in nums:
                vizinhos_entrada.extend(vizinhos(n))
        entrada_principal = sorted(set(entrada_principal))
        vizinhos_entrada = sorted(set(vizinhos_entrada))

        # Salva estado
        st.session_state.estado = "aguardando_13"
        st.session_state.entrada_principal = entrada_principal
        st.session_state.vizinhos_entrada = vizinhos_entrada
        st.session_state.numeros_usados_para_entrada = ultimos_12

        st.success("✅ Entrada gerada! Aguardando confirmação com 13º número...")
        st.write("🎯 Entrada Principal:", entrada_principal)

elif estado == "aguardando_13" and len(historico) >= 13:
    numero_13 = historico[-1]
    if (
        numero_13 in numeros_usados_para_entrada
        or numero_13 in vizinhos_entrada
    ):
        enviar_telegram(f"🎯 ENTRADA CONFIRMADA: {entrada_principal}")
        st.success(f"🎯 ENTRADA CONFIRMADA: {entrada_principal}")
        st.session_state.estado = "coletando"
        st.session_state.entrada_principal = []
        st.session_state.vizinhos_entrada = []
        st.session_state.numeros_usados_para_entrada = []
    else:
        st.warning("❌ 13º número não confirmou a entrada. Aguardando novo sorteio...")
