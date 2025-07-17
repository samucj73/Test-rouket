import streamlit as st
import requests
import json
import os
from collections import Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico.json"
ULTIMO_TIMESTAMP_PATH = "ultimo_timestamp.txt"

ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
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
            data = resp.json()
            if (
                "data" in data and
                "result" in data["data"] and
                "outcome" in data["data"]["result"] and
                "number" in data["data"]["result"]["outcome"] and
                "settledAt" in data["data"]
            ):
                numero = data["data"]["result"]["outcome"]["number"]
                timestamp = data["data"]["settledAt"]
                return numero, timestamp
            else:
                st.warning("⚠️ Estrutura inesperada da API. Verifique o conteúdo retornado.")
                return None, None
        else:
            st.error(f"❌ Erro ao acessar a API. Código: {resp.status_code}")
            return None, None
    except Exception as e:
        st.error(f"❌ Erro na requisição: {e}")
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
st.title("🎯 Estratégia de Roleta – Terminais Dominantes com Controle de Timestamp")

# st_autorefresh(interval=85000, key="datarefresh")

historico = carregar_historico()
ultimo_timestamp = carregar_timestamp()

numero, timestamp = obter_numero_e_timestamp()

# Só processa se timestamp for novo e número válido
if numero is None or timestamp == ultimo_timestamp:
    st.info("⏳ Aguardando novo sorteio...")
    st.stop()

# Evita duplicatas consecutivas no histórico
if len(historico) > 0 and historico[-1] == numero:
    st.info("⏳ Número repetido no histórico, aguardando próximo...")
    st.stop()

historico.append(numero)
if len(historico) > 100:
    historico = historico[-100:]

salvar_historico(historico)
salvar_timestamp(timestamp)
st.experimental_rerun()

# Inicializar variáveis estado
if "estado" not in st.session_state:
    st.session_state.estado = "coletando"
if "entrada_principal" not in st.session_state:
    st.session_state.entrada_principal = []
if "numeros_usados_para_entrada" not in st.session_state:
    st.session_state.numeros_usados_para_entrada = []
if "numero_13_confirmado" not in st.session_state:
    st.session_state.numero_13_confirmado = None

estado = st.session_state.estado
entrada_principal = st.session_state.entrada_principal
numeros_usados_para_entrada = st.session_state.numeros_usados_para_entrada

# Exibir últimos 15 números
st.subheader("📊 Últimos Números")
ultimos_15 = historico[-15:]

def cor_numero(n):
    if estado == "aguardando_resultado" and n == st.session_state.numero_13_confirmado:
        return "green"
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
    dominantes = [t for t, _ in contagem.most_common(2)]

    entrada_total = []
    for t in dominantes:
        nums_terminal = obter_numeros_terminal(t)
        for n in nums_terminal:
            entrada_total.append(n)
            entrada_total.extend(vizinhos(n))

    entrada_total = sorted(set(entrada_total))

    st.session_state.estado = "aguardando_13"
    st.session_state.entrada_principal = entrada_total
    st.session_state.numeros_usados_para_entrada = ultimos_12

    st.success("✅ Entrada gerada! Aguardando confirmação com 13º número...")
    st.write("🎯 Entrada Principal:", entrada_total)

elif estado == "aguardando_13" and len(historico) >= 13:
    numero_13 = historico[-1]
    if (
        numero_13 in numeros_usados_para_entrada
        or numero_13 in st.session_state.entrada_principal  # incluir vizinhos no total
    ):
        enviar_telegram(f"🎯 ENTRADA CONFIRMADA: {entrada_principal}")
        st.success(f"🎯 ENTRADA CONFIRMADA: {entrada_principal}")
        st.session_state.estado = "aguardando_resultado"
        st.session_state.numero_13_confirmado = numero_13
        st.write(f"⏳ Aguardando resultado com o próximo número após {numero_13}...")
    else:
        st.warning("❌ 13º número não confirmou a entrada. Voltando para coleta...")
        st.session_state.estado = "coletando"
        st.session_state.entrada_principal = []
        st.session_state.numeros_usados_para_entrada = []
        st.session_state.numero_13_confirmado = None

elif estado == "aguardando_resultado" and len(historico) >= 14:
    numero_14 = historico[-1]

    if numero_14 in entrada_principal:
        st.success(f"🟢 GREEN! Número {numero_14} está na entrada.")
        enviar_telegram(f"🟢 GREEN! Número {numero_14} está na entrada.")
    else:
        st.error(f"🔴 RED! Número {numero_14} não está na entrada.")
        enviar_telegram(f"🔴 RED! Número {numero_14} não está na entrada.")

    # Resetar ciclo
    st.session_state.estado = "coletando"
    st.session_state.entrada_principal = []
    st.session_state.numeros_usados_para_entrada = []
    st.session_state.numero_13_confirmado = None

else:
    st.info("⏳ Aguardando números suficientes para gerar entrada...")
