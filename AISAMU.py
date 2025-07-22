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
HISTORICO_PATH = "historico_terminal.joblib"
MODELO_PATH = "modelo_terminal.joblib"
ENTRADA_ATUAL_PATH = "entrada_atual.joblib"
NUMERO_VIZINHOS = 2
PROBABILIDADE_MINIMA = 0.75
HISTORICO_MAXIMO = 20

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ORDEM_ROLETA = [26, 3, 35, 12, 28, 7, 29, 18, 22, 9, 31, 14, 20, 1, 33, 16, 24, 5,
                10, 23, 8, 30, 11, 36, 13, 27, 6, 34, 17, 25, 2, 21, 4, 19, 15, 32]

# === FUNÇÕES UTILITÁRIAS ===

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, json=payload, timeout=3)
    except:
        pass

def carregar_objeto(caminho):
    if os.path.exists(caminho):
        return joblib.load(caminho)
    return None

def salvar_objeto(caminho, objeto):
    joblib.dump(objeto, caminho)

def extrair_terminal(numero):
    return int(str(numero)[-1])

def gerar_entrada_com_vizinhos(digitos):
    numeros_base = []
    for d in digitos:
        for n in range(37):
            if extrair_terminal(n) == d:
                numeros_base.append(n)

    entrada_completa = set()
    for numero in numeros_base:
        if numero in ORDEM_ROLETA:
            idx = ORDEM_ROLETA.index(numero)
            for i in range(-NUMERO_VIZINHOS, NUMERO_VIZINHOS + 1):
                vizinho = ORDEM_ROLETA[(idx + i) % len(ORDEM_ROLETA)]
                entrada_completa.add(vizinho)
    return list(entrada_completa)

def treinar_modelo(historico):
    if len(historico) < 20:
        return None
    terminais = [extrair_terminal(n) for n in historico[:-1]]
    X = [[t] for t in terminais]
    y = [extrair_terminal(n) for n in historico[1:]]
    from sklearn.ensemble import RandomForestClassifier
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 1:
        return []
    ultimo_terminal = extrair_terminal(historico[-1])
    probas = modelo.predict_proba([[ultimo_terminal]])[0]
    terminal_probabilidades = list(enumerate(probas))
    terminal_probabilidades.sort(key=lambda x: x[1], reverse=True)
    return terminal_probabilidades[:2]

# === INÍCIO DO APP ===

st.set_page_config(page_title="IA Terminal Roleta", layout="centered")
st.title("🎯 Estratégia IA Terminal + Vizinhos")

# Auto refresh
st_autorefresh(interval=5000, key="refresh")

# Estado inicial
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None

# Carregar dados
historico = carregar_objeto(HISTORICO_PATH) or []
modelo = carregar_objeto(MODELO_PATH)
entrada_atual = carregar_objeto(ENTRADA_ATUAL_PATH)

# Obter último número
try:
    resposta = requests.get(API_URL, timeout=5)
    dados = resposta.json()
    numero_atual = int(dados["data"]["result"]["outcome"])
    timestamp = dados["data"]["startedAt"]
except:
    st.warning("⚠️ Erro ao acessar API.")
    st.stop()

st.write(f"🎲 Último número: **{numero_atual}**")
st.write(f"🕒 Timestamp: `{timestamp}`")

# Atualiza histórico e IA
if timestamp != st.session_state.ultimo_timestamp:
    st.session_state.ultimo_timestamp = timestamp
    historico.append(numero_atual)
    historico = historico[-HISTORICO_MAXIMO:]  # Limita a 20
    salvar_objeto(HISTORICO_PATH, historico)

    modelo = treinar_modelo(historico)
    if modelo:
        salvar_objeto(MODELO_PATH, modelo)
        terminais_previstos = prever_terminais(modelo, historico)
        st.write("📊 Terminais previstos (terminal, prob):", terminais_previstos)

        if len(terminais_previstos) >= 1:
            terminais_fortes = [t for t, p in terminais_previstos if p >= PROBABILIDADE_MINIMA]
            if terminais_fortes:
                entrada = gerar_entrada_com_vizinhos(terminais_fortes)
                if entrada:
                    entrada = list(set(entrada))
                    random.shuffle(entrada)
                    entrada = entrada[:10]
                    salvar_objeto(ENTRADA_ATUAL_PATH, {"numeros": entrada, "entrada_timestamp": timestamp})
                    entrada_atual = {"numeros": entrada, "entrada_timestamp": timestamp}
                    enviar_telegram(f"🤖 Estratégia: IA Terminal\n🎯 Entrada: {entrada}")
            else:
                salvar_objeto(ENTRADA_ATUAL_PATH, None)
                entrada_atual = None
                st.write("⚠️ IA decidiu não entrar.")

# Verifica acerto anterior
if entrada_atual and entrada_atual.get("entrada_timestamp") != timestamp:
    if numero_atual in entrada_atual["numeros"]:
        enviar_telegram(f"✅ GREEN! Saiu {numero_atual}")
    else:
        enviar_telegram(f"❌ RED! Saiu {numero_atual}")
    salvar_objeto(ENTRADA_ATUAL_PATH, None)

# Exibir entrada atual
if entrada_atual:
    st.success(f"✅ Entrada ativa: {entrada_atual['numeros']}")
else:
    st.warning("⚠️ Aguardando nova entrada da IA..")
