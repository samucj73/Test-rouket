import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
CAMINHO_ARQUIVO = "historico_roleta.json"

ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
    20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# === FUNÇÕES ===
def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

def get_numero_api():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=2)
        data = r.json()
        numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        timestamp = data.get("data", {}).get("settledAt")  # Corrigido aqui!
        if numero is not None and timestamp:
            return {"numero": int(numero), "timestamp": timestamp}
    except Exception as e:
        st.error(f"Erro na API: {e}")
    return None



def gerar_entrada_com_vizinhos(terminais):
    numeros_terminal = [n for n in range(37) if n % 10 in terminais]
    vizinhos = set()
    for n in numeros_terminal:
        idx = ROULETTE_ORDER.index(n)
        for i in range(-2, 3):
            vizinhos.add(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return sorted(vizinhos)

def salvar_historico(historico):
    with open(CAMINHO_ARQUIVO, "w") as f:
        json.dump(list(historico), f)

def carregar_historico():
    if os.path.exists(CAMINHO_ARQUIVO):
        with open(CAMINHO_ARQUIVO, "r") as f:
            dados = json.load(f)
            return deque(dados, maxlen=50)
    return deque(maxlen=50)

# === CONFIGURAÇÃO STREAMLIT ===
st.set_page_config("🎯 Estratégia Automática Terminais")

if st.button("🔄 Reiniciar Estratégia (limpar tudo)"):
    if os.path.exists(CAMINHO_ARQUIVO):
        os.remove(CAMINHO_ARQUIVO)
    st.session_state.historico = deque(maxlen=50)
    st.session_state.estado = "coletando"
    st.session_state.entrada_numeros = []
    st.session_state.dominantes = []
    st.session_state.ultimos_12 = []
    st.session_state.resultado_sinais = deque(maxlen=100)
    st.session_state.telegram_enviado = False
    st.session_state.ciclos_continuacao = 0
    st.rerun()

st_autorefresh(interval=10000, key="refresh")

# === ESTADO INICIAL ===
if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()
if "estado" not in st.session_state:
    st.session_state.estado = "coletando"
if "entrada_numeros" not in st.session_state:
    st.session_state.entrada_numeros = []
if "dominantes" not in st.session_state:
    st.session_state.dominantes = []
if "ultimos_12" not in st.session_state:
    st.session_state.ultimos_12 = []
if "resultado_sinais" not in st.session_state:
    st.session_state.resultado_sinais = deque(maxlen=100)
if "telegram_enviado" not in st.session_state:
    st.session_state.telegram_enviado = False
if "ciclos_continuacao" not in st.session_state:
    st.session_state.ciclos_continuacao = 0

if "contador_pos_red" not in st.session_state:
    st.session_state.contador_pos_red = 0

# === OBTÉM NÚMERO E TIMESTAMP DA API ===
resultado = get_numero_api()
if resultado is None:
    st.warning("⏳ Aguardando número da API...")
    st.stop()

# EVITA REPETIÇÃO COM BASE NO TIMESTAMP
if not st.session_state.historico or resultado["timestamp"] != st.session_state.historico[-1]["timestamp"]:
    st.session_state.historico.append(resultado)
    salvar_historico(st.session_state.historico)

numero = resultado["numero"]
historico = [item["numero"] for item in st.session_state.historico]

# === INTERFACE ===
st.title("🎯 Estratégia de Terminais com Vizinhos (Auto)")
st.subheader("📥 Últimos Números Sorteados (15 mais recentes):")

ultimos_15 = historico[-15:]
linhas = [ultimos_15[i:i+5] for i in range(0, 15, 5)]

for linha in linhas:
    st.write(" | ".join(f"{n:2d}" for n in linha))


# === ESTADO COLETANDO ===
# === ESTADO COLETANDO ===
if st.session_state.estado == "coletando" and len(historico) >= 12:

    # Gera entrada com base nos 12 últimos números
    if not st.session_state.entrada_numeros:
        ultimos_12 = historico[-12:]
        terminais = [n % 10 for n in ultimos_12]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]  # <- Pega os dois terminais mais comuns
        if len(dominantes) == 2:
            entrada = gerar_entrada_com_vizinhos(dominantes)
            st.session_state.entrada_numeros = entrada
            st.session_state.dominantes = dominantes
            st.session_state.ultimos_12 = ultimos_12

    if len(historico) >= 14:
        numero_13 = historico[-2]
        numero_14 = historico[-1]

        # Gatilho: 13º número precisa estar nos últimos 12 ou na entrada
        if numero_13 in st.session_state.ultimos_12 or numero_13 in st.session_state.entrada_numeros:
            if not st.session_state.telegram_enviado:
                linhas = []
                for t in st.session_state.dominantes:
                    numeros_terminal = [n for n in range(37) if n % 10 == t]
                    numeros_terminal.sort()
                    linha = " ".join(map(str, numeros_terminal))
                    linhas.append(linha)
                msg = "Entrada:\n" + "\n".join(linhas)
                enviar_telegram(msg)
                st.session_state.telegram_enviado = True

            st.info("🚨 Entrada gerada! Aguardando resultado do próximo número (14º)...")
            st.write(f"🎰 Entrada: {st.session_state.entrada_numeros}")
            st.write(f"🔥 Terminais dominantes: {st.session_state.dominantes}")
            st.write(f"🧪 Verificando se o número {numero_14} está na entrada...")

            if numero_14 in st.session_state.entrada_numeros:
                st.success("✅ GREEN automático!")
                st.session_state.resultado_sinais.append("GREEN")
                st.session_state.estado = "aguardando_continuacao"
                st.session_state.ciclos_continuacao = 1
                st.session_state.telegram_enviado = False
                enviar_telegram("✅ GREEN confirmado!")
            else:
                st.warning("❌ RED automático!")
                st.session_state.resultado_sinais.append("RED")
                st.session_state.estado = "pos_red"
                st.session_state.telegram_enviado = False
                st.session_state.ciclos_continuacao = 0
                enviar_telegram("❌ RED registrado!")
                # Limpa a entrada após o RED
                st.session_state.entrada_numeros = []
                st.session_state.dominantes = []
                st.session_state.ultimos_12 = []


# === ESTADO AGUARDANDO CONTINUAÇÃO ===
elif st.session_state.estado == "aguardando_continuacao":
    if numero in st.session_state.entrada_numeros:
        st.success(f"✅ GREEN durante continuação! Ciclo {st.session_state.ciclos_continuacao}/3")
        if not st.session_state.telegram_enviado:
            enviar_telegram(f"✅ GREEN durante continuação! Ciclo {st.session_state.ciclos_continuacao}/3")
            st.session_state.telegram_enviado = True
        st.session_state.resultado_sinais.append("GREEN")
        st.session_state.ciclos_continuacao += 1

        if st.session_state.ciclos_continuacao > 3:
            st.warning("🔁 Limite de 3 ciclos atingido. Reiniciando...")
            st.session_state.estado = "coletando"
            st.session_state.entrada_numeros = []
            st.session_state.dominantes = []
            st.session_state.telegram_enviado = False
            st.session_state.ciclos_continuacao = 0
    else:
        st.session_state.estado = "coletando"
        st.session_state.entrada_numeros = []
        st.session_state.dominantes = []
        st.session_state.telegram_enviado = False
        st.session_state.ciclos_continuacao = 0

# === ESTADO PÓS-RED ===
elif st.session_state.estado == "pos_red":
    if numero in st.session_state.ultimos_12:
        entrada = gerar_entrada_com_vizinhos(st.session_state.dominantes)
        st.session_state.entrada_numeros = entrada
        st.session_state.estado = "aguardando_continuacao"
        st.session_state.telegram_enviado = False
        st.session_state.ciclos_continuacao = 1
        st.session_state.contador_pos_red = 0
        enviar_telegram("🎯 REENTRADA após RED! Mesma entrada.")
    else:
        st.session_state.contador_pos_red += 1
        st.warning(f"⏳ Aguardando pós-RED... ({st.session_state.contador_pos_red}/2)")
        if st.session_state.contador_pos_red >= 2:
            st.session_state.estado = "coletando"
            st.session_state.entrada_numeros = []
            st.session_state.dominantes = []
            st.session_state.telegram_enviado = False
            st.session_state.ultimos_12 = []
            st.session_state.contador_pos_red = 0
            st.info("🔄 Voltando ao estado de coleta após RED.")

# === EXIBIÇÃO FINAL ===
st.subheader("📊 Estado Atual")
st.write(f"Estado: **{st.session_state.estado}**")
if st.session_state.entrada_numeros:
    st.write(f"🎰 Entrada: {st.session_state.entrada_numeros}")
    st.write(f"🔥 Terminais dominantes: {st.session_state.dominantes}")
    st.write(f"🔁 Ciclos consecutivos: {st.session_state.ciclos_continuacao}/3")

if st.session_state.resultado_sinais:
    st.subheader("📈 Histórico de Sinais")
    sinais = [1 if x == "GREEN" else 0 for x in st.session_state.resultado_sinais]
    st.line_chart(sinais, height=200)
