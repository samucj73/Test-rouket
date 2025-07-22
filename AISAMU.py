import streamlit as st
import requests
import os
import joblib
import random
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
ID_CANAL = "-1002796136111"

# === HISTÓRICO ===
HISTORICO_FILE = "historico.pkl"
MAX_HISTORICO = 20

# === DESEMPENHO IA ===
DESEMPENHO_FILE = "desempenho_ia.pkl"

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ORDEM_ROLETA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8,
    23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

# === Funções utilitárias ===
def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        return joblib.load(HISTORICO_FILE)
    return deque(maxlen=MAX_HISTORICO)

def salvar_historico(historico):
    joblib.dump(historico, HISTORICO_FILE)

def carregar_desempenho():
    if os.path.exists(DESEMPENHO_FILE):
        return joblib.load(DESEMPENHO_FILE)
    return {"green": 0, "red": 0, "total": 0}

def salvar_desempenho(dados):
    joblib.dump(dados, DESEMPENHO_FILE)

def registrar_resultado(acertou: bool):
    desempenho = carregar_desempenho()
    if acertou:
        desempenho["green"] += 1
    else:
        desempenho["red"] += 1
    desempenho["total"] += 1
    salvar_desempenho(desempenho)

def exibir_painel_desempenho():
    desempenho = carregar_desempenho()
    st.markdown("### 📊 Desempenho da IA")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ GREENs", desempenho["green"])
    col2.metric("❌ REDs", desempenho["red"])
    col3.metric("📈 Taxa de Acerto", f'{(desempenho["green"]/desempenho["total"]*100):.1f}%' if desempenho["total"] > 0 else "0%")
    col4.metric("🔢 Total de Sinais", desempenho["total"])

def get_vizinhos(numero):
    idx = ORDEM_ROLETA.index(numero)
    vizinhos = []
    for i in range(-2, 3):
        vizinhos.append(ORDEM_ROLETA[(idx + i) % len(ORDEM_ROLETA)])
    return vizinhos

def obter_ultimo_numero():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            return int(data["data"]["result"]["outcome"]["number"])
    except Exception as e:
        st.warning("⚠️ Erro ao acessar API.")
    return None

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": ID_CANAL, "text": mensagem}
    try:
        requests.post(url, data=payload)
    except:
        st.warning("⚠️ Falha ao enviar mensagem para Telegram.")

# === INICIALIZAÇÃO ===
st.set_page_config(layout="centered")
st_autorefresh(interval=5000, key="refresh")

st.title("🎯 IA Roleta – Estratégia Dominantes + Vizinhos")
exibir_painel_desempenho()

if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()

ultimo_numero = obter_ultimo_numero()
if ultimo_numero is not None:
    if len(st.session_state.historico) == 0 or st.session_state.historico[-1] != ultimo_numero:
        st.session_state.historico.append(ultimo_numero)
        salvar_historico(st.session_state.historico)

        # IA: prevê os 2 terminais mais prováveis
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

        # Mostrar entrada gerada
        st.markdown("### 🎰 Entrada Gerada pela IA")
        st.write("🔢 Terminais dominantes:", terminais_previstos)
        st.write("🎯 Números da entrada:", entrada_final)

        # Verificar acerto
        if len(historico) >= 14:
            numero_resultado = historico[-1]
            if numero_resultado in entrada_final:
                resultado = "✅ GREEN"
                registrar_resultado(True)
            else:
                resultado = "❌ RED"
                registrar_resultado(False)

            st.markdown(f"### Resultado anterior: **{resultado}**")
            enviar_telegram(f"🎯 Entrada IA: {entrada_final}\n🔢 Terminais: {terminais_previstos}\nResultado: {resultado}")
    else:
        st.info("⏳ Aguardando novo número da roleta...")
else:
    st.warning("⚠️ Não foi possível obter o número atual da API.")
