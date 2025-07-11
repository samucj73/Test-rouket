import streamlit as st
import requests
from collections import Counter, deque
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# Telegram
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# API
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"

# Ordem física da roleta europeia
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
    20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# Funções
def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

def get_numero_api():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = r.json()
        numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        if numero is not None and 0 <= int(numero) <= 36:
            return int(numero)
    except:
        pass
    return None

def gerar_entrada_com_vizinhos(terminais):
    numeros_terminal = [n for n in range(37) if n % 10 in terminais]
    vizinhos = set()
    for n in numeros_terminal:
        idx = ROULETTE_ORDER.index(n)
        for i in range(-2, 3):
            vizinhos.add(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return sorted(vizinhos)

# Configuração do app
st.set_page_config("🎯 Estratégia Automática Terminais")
st_autorefresh(interval=10000, key="refresh")

# Estado inicial
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=50)
if "estado" not in st.session_state:
    st.session_state.estado = "coletando"
if "entrada_numeros" not in st.session_state:
    st.session_state.entrada_numeros = []
if "dominantes" not in st.session_state:
    st.session_state.dominantes = []
if "ultimos_12" not in st.session_state:
    st.session_state.ultimos_12 = []
if "numero_previsto" not in st.session_state:
    st.session_state.numero_previsto = None
if "resultado_sinais" not in st.session_state:
    st.session_state.resultado_sinais = deque(maxlen=100)

# Número novo da API
numero = get_numero_api()
if numero is None:
    st.warning("⏳ Aguardando número da API...")
    st.stop()

# Evita repetição
if not st.session_state.historico or numero != st.session_state.historico[-1]:
    st.session_state.historico.append(numero)

# Interface
st.title("🎯 Estratégia de Terminais com Vizinhos (Auto)")
st.subheader("📥 Últimos Números Sorteados:")
st.write(list(st.session_state.historico)[-20:])

# Lógica principal
historico = list(st.session_state.historico)

# Coleta + Ativação de entrada
if st.session_state.estado == "coletando" and len(historico) >= 14:
    ultimos_12 = historico[-14:-2]   # últimos 12 sorteios
    numero_13 = historico[-2]        # 13º número
    numero_14 = historico[-1]        # 14º número

    terminais = [n % 10 for n in ultimos_12]
    contagem = Counter(terminais)
    dominantes = [t for t, c in contagem.items() if c >= 3]  # Dominantes com 3 ou mais ocorrências

    entrada = gerar_entrada_com_vizinhos(dominantes)

    if len(dominantes) == 2 and (numero_13 in ultimos_12 or numero_13 in entrada):
        st.session_state.estado = "verificando_resultado"
        st.session_state.entrada_numeros = entrada
        st.session_state.dominantes = dominantes
        st.session_state.ultimos_12 = ultimos_12
        st.session_state.numero_previsto = numero_14

        # Alerta visual para entrada antecipada
        if numero_13 in entrada and numero_13 not in ultimos_12:
            st.info("🔁 Entrada ativada por número entre os vizinhos (antecipada)")

        enviar_telegram(f"🎯 ENTRADA ATIVADA\nTerminais: {dominantes}\nEntrada: {entrada}\nAguardando número: {numero_14}")

# Verificação de resultado com o 14º número
elif st.session_state.estado == "verificando_resultado":
    if numero == st.session_state.numero_previsto:
        if numero in st.session_state.entrada_numeros:
            st.success("✅ GREEN automático!")
            st.session_state.resultado_sinais.append("GREEN")
            enviar_telegram("✅ GREEN confirmado!")
        else:
            st.warning("❌ RED automático!")
            st.session_state.resultado_sinais.append("RED")
            st.session_state.estado = "pos_red"
            enviar_telegram("❌ RED registrado!")
        st.session_state.entrada_numeros = []
        st.session_state.numero_previsto = None

# Pós-RED → Reentrada com os mesmos dominantes
elif st.session_state.estado == "pos_red":
    if numero in st.session_state.ultimos_12:
        entrada = gerar_entrada_com_vizinhos(st.session_state.dominantes)
        st.session_state.entrada_numeros = entrada
        st.session_state.numero_previsto = numero
        st.session_state.estado = "verificando_resultado"
        enviar_telegram("🎯 REENTRADA após RED! Mesma entrada.")

# Exibição
st.subheader("📊 Estado Atual")
st.write(f"Estado: **{st.session_state.estado}**")
if st.session_state.entrada_numeros:
    st.write(f"🎰 Entrada: {st.session_state.entrada_numeros}")
    st.write(f"🔥 Terminais dominantes: {st.session_state.dominantes}")

# Gráfico de sinais
if st.session_state.resultado_sinais:
    st.subheader("📈 Histórico de Sinais")
    sinais = [1 if x == "GREEN" else 0 for x in st.session_state.resultado_sinais]
    st.line_chart(sinais, height=200)
