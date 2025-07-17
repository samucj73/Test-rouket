import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import json
import joblib

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico.pkl"
ROULETTE_NUMBERS = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
    10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# === ESTADOS ===
estado = st.session_state.get("estado", "coletando")
entrada_atual = st.session_state.get("entrada_atual", [])
numero_alvo = st.session_state.get("numero_alvo", None)
terminais_dominantes = st.session_state.get("terminais_dominantes", [])

# === HISTÓRICO COM JOBLIB ===
if os.path.exists(HISTORICO_PATH):
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=15)

# === FUNÇÕES ===
def salvar_historico():
    joblib.dump(historico, HISTORICO_PATH)

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": mensagem}
        requests.post(url, data=data)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

def obter_numero():
    try:
        resposta = requests.get(API_URL)
        if resposta.status_code == 200:
            data = resposta.json()
            return data["data"]["result"]["outcome"]["number"]
    except Exception as e:
        st.error(f"Erro ao obter número: {e}")
    return None

def terminal(numero):
    return numero % 10

def vizinhos_fisicos(numero):
    if numero not in ROULETTE_NUMBERS:
        return []
    idx = ROULETTE_NUMBERS.index(numero)
    vizinhos = []
    for i in range(-2, 3):
        vizinhos.append(ROULETTE_NUMBERS[(idx + i) % len(ROULETTE_NUMBERS)])
    return vizinhos

# === INTERFACE ===
st.title("🎯 Estratégia de Roleta - Terminais Dominantes")

numero = obter_numero()
if numero is not None and (not historico or numero != historico[-1]):
    historico.append(numero)
    salvar_historico()

# Exibir últimos 15 números em 3 linhas
# Exibir últimos 15 números no layout: 3 linhas de 5, com cores
st.markdown("### Últimos Números")

ultimos_15 = list(historico)[-15:]
faltando = 15 - len(ultimos_15)
ultimos_15 = ['-'] * faltando + ultimos_15  # Preencher à esquerda com "-"

linhas = [ultimos_15[i:i+5] for i in range(0, 15, 5)]

for linha in linhas:
    linha_formatada = ""
    for n in linha:
        if n == '-':
            cor = "gray"
        elif n == historico[-1]:
            if estado == "verificando":
                cor = "green" if n in entrada_atual else "red"
            else:
                cor = "orange"
        else:
            cor = "black"
        linha_formatada += f"<span style='color:{cor}; font-size:22px'><b>{n}</b></span> &nbsp; - &nbsp; "
    linha_formatada = linha_formatada.rstrip(" &nbsp; - &nbsp; ")  # remove final extra
    st.markdown(f"<div style='text-align:center'>{linha_formatada}</div>", unsafe_allow_html=True)


# Exibir terminais dominantes se houver
if terminais_dominantes:
    st.markdown(f"**Terminais Dominantes:** {terminais_dominantes}")

# === LÓGICA PRINCIPAL ===
if estado == "coletando" and len(historico) >= 12:
    ultimos_12 = list(historico)[-12:]
    terminais = [terminal(n) for n in ultimos_12]
    contagem = Counter(terminais).most_common(2)

    if len(contagem) >= 2 and contagem[0][1] >= 3 and contagem[1][1] >= 3:
        dominantes = [contagem[0][0], contagem[1][0]]
        candidatos = [n for n in ultimos_12 if terminal(n) in dominantes]
        entrada = set()
        for c in candidatos:
            entrada.update(vizinhos_fisicos(c))
        entrada_atual = list(sorted(set(entrada)))
        numero_alvo = historico[-1]  # 13º número

        # Salvar no estado
        st.session_state["entrada_atual"] = entrada_atual
        st.session_state["numero_alvo"] = numero_alvo
        st.session_state["estado"] = "verificando"
        st.session_state["terminais_dominantes"] = dominantes

        mensagem = f"""🎯 ENTRADA IDENTIFICADA
Dominantes: {dominantes}
Entrada: {entrada_atual}"""
        enviar_telegram(mensagem)

elif estado == "verificando":
    if len(historico) >= 1 and historico[-1] != numero_alvo:
        resultado = historico[-1]
        if resultado in entrada_atual:
            enviar_telegram(f"✅ GREEN com número {resultado}")
        else:
            enviar_telegram(f"❌ RED com número {resultado}")
            st.session_state["estado"] = "pós_red"
        # Resetar
        st.session_state["estado"] = "coletando"
        st.session_state["entrada_atual"] = []
        st.session_state["numero_alvo"] = None
        st.session_state["terminais_dominantes"] = []

# === STATUS ===
estado_atual = st.session_state.get("estado", "coletando")
if estado_atual == "pós_red":
    st.warning("🟡 Estado: PÓS_RED")
elif estado_atual == "verificando":
    st.info("🔍 Estado: VERIFICANDO")
else:
    st.success("📥 Estado: COLETANDO")

# Atualiza a cada 5 segundos
st_autorefresh(interval=5000, key="atualizacao")
