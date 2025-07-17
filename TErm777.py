import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/api/results?limit=1"

# === MAPA DA ROLETA EUROPEIA ===
ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# === SESSION STATE ===
if 'historico' not in st.session_state:
    st.session_state.historico = deque(maxlen=100)
if 'ultimo_timestamp' not in st.session_state:
    st.session_state.ultimo_timestamp = None
if 'estado' not in st.session_state:
    st.session_state.estado = "coletando"
if 'entrada_numeros' not in st.session_state:
    st.session_state.entrada_numeros = []
if 'resultado_sinais' not in st.session_state:
    st.session_state.resultado_sinais = []
if 'telegram_enviado' not in st.session_state:
    st.session_state.telegram_enviado = False
if 'ciclos_continuacao' not in st.session_state:
    st.session_state.ciclos_continuacao = 0

# === FUNÇÕES AUXILIARES ===
def get_neighbors(number):
    idx = ROULETTE_NUMBERS.index(number)
    return [
        ROULETTE_NUMBERS[(idx - 2) % len(ROULETTE_NUMBERS)],
        ROULETTE_NUMBERS[(idx - 1) % len(ROULETTE_NUMBERS)],
        number,
        ROULETTE_NUMBERS[(idx + 1) % len(ROULETTE_NUMBERS)],
        ROULETTE_NUMBERS[(idx + 2) % len(ROULETTE_NUMBERS)],
    ]

def gerar_entrada_com_vizinhos(dominantes):
    entrada = set()
    for t in dominantes:
        numeros_terminal = [n for n in range(37) if n % 10 == t]
        for num in numeros_terminal:
            entrada.update(get_neighbors(num))
    return sorted(entrada)

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensagem}
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem: {e}")

# === LOOP DE ATUALIZAÇÃO ===
st_autorefresh(interval=5000, key="auto_refresh")

# === OBTÉM NOVO NÚMERO ===
try:
    response = requests.get(API_URL)
    data = response.json()
    novo_numero = data[0]["value"]
    timestamp = data[0]["timestamp"]

    if timestamp != st.session_state.ultimo_timestamp:
        st.session_state.historico.append(novo_numero)
        st.session_state.ultimo_timestamp = timestamp
        numero = novo_numero
    else:
        numero = None

except Exception as e:
    st.error(f"Erro ao obter número: {e}")
    numero = None

# === EXIBE HISTÓRICO ===
st.write("🧾 Últimos números:", list(st.session_state.historico))

# === LÓGICA PRINCIPAL ===

# === ESTADO COLETANDO ===
if st.session_state.estado == "coletando" and len(st.session_state.historico) >= 14:
    ultimos_12 = list(st.session_state.historico)[-13:-1]
    numero_13 = st.session_state.historico[-2]
    numero_14 = st.session_state.historico[-1]

    terminais = [n % 10 for n in ultimos_12]
    contagem = Counter(terminais)
    dominantes = [t for t, c in contagem.items() if c >= 2]

    if len(dominantes) == 2:
        entrada = gerar_entrada_com_vizinhos(dominantes)

        if numero_13 in ultimos_12 or numero_13 in entrada:
            if not st.session_state.telegram_enviado:
                linhas = []
                for t in dominantes:
                    numeros_terminal = [n for n in range(37) if n % 10 == t]
                    numeros_terminal.sort()
                    linha = " ".join(map(str, numeros_terminal))
                    linhas.append(linha)
                msg = "🎯 Entrada:\n" + "\n".join(linhas)
                enviar_telegram(msg)
                st.session_state.telegram_enviado = True

            st.write(f"🎰 Entrada: {entrada}")
            if numero_14 in entrada:
                st.success("✅ GREEN automático!")
                enviar_telegram("✅ GREEN confirmado!")
                st.session_state.resultado_sinais.append("GREEN")
                st.session_state.estado = "aguardando_continuacao"
                st.session_state.entrada_numeros = entrada
                st.session_state.ciclos_continuacao = 1
                st.session_state.telegram_enviado = False
            else:
                st.warning("❌ RED automático!")
                enviar_telegram("❌ RED registrado!")
                st.session_state.resultado_sinais.append("RED")
                st.session_state.estado = "coletando"
                st.session_state.entrada_numeros = []
                st.session_state.ciclos_continuacao = 0
                st.session_state.telegram_enviado = False

# === ESTADO AGUARDANDO CONTINUAÇÃO ===
elif st.session_state.estado == "aguardando_continuacao" and numero is not None:
    if numero in st.session_state.entrada_numeros:
        st.success(f"✅ GREEN durante continuação! Ciclo {st.session_state.ciclos_continuacao}/3")
        if not st.session_state.telegram_enviado:
            enviar_telegram(f"✅ GREEN durante continuação! Ciclo {st.session_state.ciclos_continuacao}/3")
            st.session_state.telegram_enviado = True
        st.session_state.resultado_sinais.append("GREEN")
        st.session_state.ciclos_continuacao += 1

        if st.session_state.ciclos_continuacao == 3:
            st.warning("✅ 3 GREENs atingidos! Verificando se o próximo número também está na entrada...")
        elif st.session_state.ciclos_continuacao > 3:
            if numero in st.session_state.entrada_numeros:
                st.success("🔁 GREEN após 3 ciclos — novo ciclo iniciado!")
                enviar_telegram("🔁 GREEN após 3 ciclos — novo ciclo iniciado!")
                st.session_state.ciclos_continuacao = 1
                st.session_state.telegram_enviado = False
            else:
                st.warning("⛔ GREENs encerrados. Reiniciando...")
                enviar_telegram("⛔ Fim do ciclo. Reinício.")
                st.session_state.estado = "coletando"
                st.session_state.entrada_numeros = []
                st.session_state.telegram_enviado = False
                st.session_state.ciclos_continuacao = 0
    else:
        st.warning("❌ Número fora da entrada. Estratégia reiniciada.")
        st.session_state.estado = "coletando"
        st.session_state.entrada_numeros = []
        st.session_state.telegram_enviado = False
        st.session_state.ciclos_continuacao = 0

# === RESULTADOS ===
st.write("📊 Resultados:", st.session_state.resultado_sinais)
