import streamlit as st
import requests
import json
import os
from collections import Counter
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
            data = resp.json().get("data", {})
            resultado = data.get("result", {})
            outcome = resultado.get("outcome", {})
            numero = outcome.get("number", None)
            timestamp = data.get("settledAt", None)  # corrigido para usar settledAt
            if numero is not None and timestamp is not None:
                return numero, timestamp
    except Exception as e:
        pass
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

# === INÍCIO DO APP ===

st.set_page_config(layout="centered")
st.title("🎯 Estratégia de Roleta – Terminais Dominantes")

# Autorefresh a cada 5 segundos
st_autorefresh(interval=5000, key="datarefresh")

# Carregar histórico e timestamp armazenados
historico = carregar_historico()
ultimo_timestamp = carregar_timestamp()

# Inicializar variáveis de estado do Streamlit se não existirem
if "estado" not in st.session_state:
    st.session_state.estado = "coletando"
if "entrada_principal" not in st.session_state:
    st.session_state.entrada_principal = []
if "vizinhos_entrada" not in st.session_state:
    st.session_state.vizinhos_entrada = []
if "numeros_usados_para_entrada" not in st.session_state:
    st.session_state.numeros_usados_para_entrada = []
if "numero_13_confirmado" not in st.session_state:
    st.session_state.numero_13_confirmado = None

estado = st.session_state.estado
entrada_principal = st.session_state.entrada_principal
vizinhos_entrada = st.session_state.vizinhos_entrada
numeros_usados_para_entrada = st.session_state.numeros_usados_para_entrada

# Obter novo número e timestamp da API
numero, timestamp = obter_numero_e_timestamp()

if numero is not None and timestamp != ultimo_timestamp:
    historico.append(numero)
    salvar_historico(historico)
    salvar_timestamp(timestamp)

# Exibição dos últimos 15 números com cores
st.subheader("📊 Últimos Números")
ultimos_15 = historico[-15:]

def cor_numero(n):
    if estado == "aguardando_resultado" and n == st.session_state.numero_13_confirmado:
        return "green"  # 13º número confirmado
    if estado == "aguardando_resultado" and n == numero:
        return "white"
    if n in entrada_principal:
        return "green"
    return "white"

linhas = [ultimos_15[i:i+5] for i in range(0, len(ultimos_15), 5)]
for linha in linhas:
    st.markdown(
        "<div style='font-size: 22px; margin-bottom: 5px;'>"
        + " - ".join(
            f"<span style='color:{cor_numero(n)};'>{n:02d}</span>"
            for n in linha
        )
        + "</div>",
        unsafe_allow_html=True
    )

# Lógica da estratégia
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
        st.session_state.estado = "aguardando_resultado"
        st.session_state.numero_13_confirmado = numero_13
        st.write(f"⏳ Aguardando resultado com o próximo número após {numero_13}...")
    else:
        st.warning("❌ 13º número não confirmou a entrada. Continuando coleta...")
        st.session_state.estado = "coletando"
        st.session_state.entrada_principal = []
        st.session_state.vizinhos_entrada = []
        st.session_state.numeros_usados_para_entrada = []
        st.session_state.numero_13_confirmado = None

elif estado == "aguardando_resultado" and len(historico) >= 14:
    numero_14 = historico[-1]
    entrada = st.session_state.entrada_principal

    if numero_14 in entrada:
        st.success(f"🟢 GREEN! Número {numero_14} está na entrada.")
        enviar_telegram(f"🟢 GREEN! Número {numero_14} está na entrada.")
    else:
        st.error(f"🔴 RED! Número {numero_14} não está na entrada.")
        enviar_telegram(f"🔴 RED! Número {numero_14} não está na entrada.")

    # Reinicia o ciclo
    st.session_state.estado = "coletando"
    st.session_state.entrada_principal = []
    st.session_state.vizinhos_entrada = []
    st.session_state.numeros_usados_para_entrada = []
    st.session_state.numero_13_confirmado = None

else:
    st.info("⏳ Aguardando números suficientes para gerar entrada...")
