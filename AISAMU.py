import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
MODELO_PATH = "modelo_ia_terminals.pkl"

# === FUNÇÕES UTILITÁRIAS ===
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
        requests.post(url, params=params)
    except Exception as e:
        st.error(f"Erro ao enviar alerta: {e}")

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return None

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def get_numero_roleta(api_url):
    try:
        resposta = requests.get(api_url)
        if resposta.status_code == 200:
            dados = resposta.json()
            numero = dados["data"]["result"]["outcome"]["number"]
            timestamp = dados["data"]["settledAt"]
            return numero, timestamp
        else:
            return None, None
    except Exception as e:
        st.warning(f"⚠️ Erro ao acessar API.")
        return None, None

def get_vizinhos(numero):
    ordem_fisica = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
        13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
        20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
    ]
    if numero not in ordem_fisica:
        return []
    idx = ordem_fisica.index(numero)
    vizinhos = []
    for i in range(idx - 2, idx + 3):
        vizinhos.append(ordem_fisica[i % len(ordem_fisica)])
    return vizinhos

def registrar_resultado(acerto):
    if "greens" not in st.session_state:
        st.session_state.greens = 0
    if "reds" not in st.session_state:
        st.session_state.reds = 0
    if acerto:
        st.session_state.greens += 1
    else:
        st.session_state.reds += 1

# === INTERFACE STREAMLIT ===
st.set_page_config(layout="centered", page_title="🎯 Estratégia IA - Roleta")
st.title("🎯 Estratégia IA - Roleta (Terminais + Vizinhos)")
st_autorefresh(interval=5000, limit=None, key="auto")

# === HISTÓRICO E CONTROLE ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=100)

if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None

# === OBTÉM NOVO NÚMERO ===
numero_atual, timestamp = get_numero_roleta(API_URL)
if numero_atual is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.ultimo_timestamp = timestamp
    st.session_state.historico.append(numero_atual)

    # === VERIFICAÇÃO DE RESULTADO ANTERIOR ===
    if "entrada_prevista" in st.session_state and "terminais_previstos" in st.session_state:
        numero_resultado = numero_atual
        if numero_resultado in st.session_state.entrada_prevista:
            resultado = "✅ GREEN"
            registrar_resultado(True)
        else:
            resultado = "❌ RED"
            registrar_resultado(False)

        st.markdown(f"### Resultado anterior: **{resultado}**")
        enviar_telegram(
            f"🎯 Entrada IA: {st.session_state.entrada_prevista}\n"
            f"🔢 Terminais: {st.session_state.terminais_previstos}\n"
            f"🎲 Resultado: {numero_resultado} → {resultado}"
        )

    # === GERA NOVA ENTRADA ===
    historico = list(st.session_state.historico)
    terminais = [n % 10 for n in historico]
    contagem = Counter(terminais)
    mais_comuns = contagem.most_common(2)
    terminais_previstos = [t[0] for t in mais_comuns]

    entrada_principal = []
    for terminal in terminais_previstos:
        numeros_terminal = [n for n in range(37) if n % 10 == terminal]
        for num in numeros_terminal:
            entrada_principal.extend(get_vizinhos(num))
    entrada_final = sorted(set(entrada_principal))

    # Salva previsão para próxima verificação
    st.session_state.entrada_prevista = entrada_final
    st.session_state.terminais_previstos = terminais_previstos

# === EXIBE ENTRADA ATUAL ===
if "entrada_prevista" in st.session_state:
    st.markdown("### 🎰 Entrada atual gerada pela IA")
    st.write("🔢 Terminais dominantes:", st.session_state.terminais_previstos)
    st.write("🎯 Números da entrada:", st.session_state.entrada_prevista)

# === EXIBE HISTÓRICO E PERFORMANCE ===
st.markdown("### 📈 Histórico recente:")
st.write(list(st.session_state.historico))

st.markdown("### 📊 Relatório de Performance")
greens = st.session_state.get("greens", 0)
reds = st.session_state.get("reds", 0)
total = greens + reds
taxa = (greens / total * 100) if total > 0 else 0
st.write(f"✅ Greens: {greens} | ❌ Reds: {reds} | 🎯 Taxa de acerto: **{taxa:.1f}%**")
