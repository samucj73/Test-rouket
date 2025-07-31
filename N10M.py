import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque
import time
from streamlit_autorefresh import st_autorefresh
from pathlib import Path

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
#TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
#TELEGRAM_CHAT_ID = "-1002880411750"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")

ROULETTE_SEQUENCE = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
                     27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
                     16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
                     7, 28, 12, 35, 3, 26]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=500)

if "acertos_top10" not in st.session_state:
    st.session_state.acertos_top10 = 0
if "total_top10" not in st.session_state:
    st.session_state.total_top10 = 0
if "ultimo_alerta" not in st.session_state:
    st.session_state.ultimo_alerta = []
if "top10_anterior" not in st.session_state:
    st.session_state.top10_anterior = []

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === FUNÇÕES ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro Telegram:", e)

def get_neighbors(n, k=2):
    if n not in ROULETTE_SEQUENCE:
        return []
    idx = ROULETTE_SEQUENCE.index(n)
    return [ROULETTE_SEQUENCE[(idx + i) % len(ROULETTE_SEQUENCE)] for i in range(-k, k + 1)]

def bloco_terco(numero):
    if numero == 0: return "zero"
    if numero in [27,13,36,11,30,8,23,10,5,24,16,33]: return "terco2"
    if numero in [32,15,19,4,21,2,25,17,34,6,27,13]: return "terco1"
    return "terco3"

def extrair_features(historico):
    historico = list(historico)
    X, y = [], []

    def cor(n):
        if n == 0: return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    # Ignora o último número (não usar o sorteio atual como base)
    historico_sem_ultimo = historico[:-1]

    for i in range(11, len(historico_sem_ultimo)):
        janela = historico_sem_ultimo[i-10:i]
        ult = historico_sem_ultimo[i-1]

        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')

        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = 5 - pares

        terminal = ult % 10
        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0

        vizinhos = get_neighbors(ult, k=2)
        viz_media = np.mean(vizinhos)

        bloco = bloco_terco(ult)
        bloco_num = {"terco1": 1, "terco2": 2, "terco3": 3, "zero": 0}[bloco]

        features = [
            vermelhos, pretos, verdes,
            pares, impares,
            terminal, duzia, coluna,
            viz_media, bloco_num
        ]

        X.append(features)
        y.append(historico_sem_ultimo[i])

    return np.array(X, dtype=np.float64), np.array(y, dtype=int)

def treinar_modelo(historico):
    if len(historico) < 40:
        return None

    X, y = extrair_features(historico)
    if len(X) == 0:
        return None

    modelo = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)
    modelo.fit(X, y)
    joblib.dump(modelo, "modelo_top10.pkl")
    return modelo

def prever_top10(modelo, historico):
    if len(historico) < 40:
        return []

    X, _ = extrair_features(historico)
    if X.size == 0:
        return []

    # Usar o penúltimo vetor de features, baseado nos 5 números antes do último
    x = X[-1].reshape(1, -1)

    try:
        probas = modelo.predict_proba(x)[0]
        indices = np.argsort(probas)[::-1][:10]
        top10 = [int(i) for i in indices]
        return top10
    except Exception as e:
        print(f"[ERRO PREVISÃO]: {e}")
        return []



# === LOOP PRINCIPAL ===
st.title("🎯 IA Roleta Profissional - Top 10 Números")
st_autorefresh(interval=5000, key="atualizacao")

try:
    resposta = requests.get(API_URL, timeout=10).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro ao obter número da API: {e}")
    st.stop()

historico = st.session_state.historico

if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)


    # === VERIFICAÇÃO DE ACERTO DO SORTEIO ANTERIOR ===
    if "top10_anterior" in st.session_state and st.session_state.top10_anterior:
        st.session_state.total_top10 += 1
        if numero_atual in st.session_state.top10_anterior:
            st.session_state.acertos_top10 += 1
            resultado = f"✅ {numero_atual} estava na previsão: 🟢"
        else:
            resultado = f"✅ {numero_atual} não estava: 🔴"
        time.sleep(4)
        enviar_telegram(resultado)

    # === GERA NOVA PREVISÃO PARA O PRÓXIMO SORTEIO ===
    modelo = treinar_modelo(historico)
    if modelo:
        nova_previsao = prever_top10(modelo, historico)
        if nova_previsao != st.session_state.ultimo_alerta and len(nova_previsao) == 10:
            msg = "🎯 <b>Top 10:</b> " + ", ".join(str(n) for n in nova_previsao)
            enviar_telegram(msg)
            st.session_state.ultimo_alerta = nova_previsao
            st.session_state.top10_anterior = nova_previsao  # salva para conferir no próximo ciclo

# === UI STREAMLIT ===
st.write("Último número:", numero_atual)
st.write(f"Acertos Top 10: {st.session_state.acertos_top10} / {st.session_state.total_top10}")
st.write("Últimos números:", list(historico)[-20:])

# Salvar estado
joblib.dump({
    "acertos_top10": st.session_state.acertos_top10,
    "total_top10": st.session_state.total_top10,
    "ultimo_alerta": st.session_state.ultimo_alerta
}, ESTADO_PATH)
