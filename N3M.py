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
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")

ROULETTE_SEQUENCE = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
                     27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
                     16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
                     7, 28, 12, 35, 3, 26]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=500)

if "acertos_top" not in st.session_state:
    st.session_state.acertos_top = 0
if "total_top" not in st.session_state:
    st.session_state.total_top = 0
if "ultimo_alerta" not in st.session_state:
    st.session_state.ultimo_alerta = []
if "top3_principal" not in st.session_state:
    st.session_state.top3_principal = []
if "top3_com_vizinhos" not in st.session_state:
    st.session_state.top3_com_vizinhos = []

# Inicializa variáveis de estado, se ainda não existirem
if "top3_anterior" not in st.session_state:
    st.session_state.top3_anterior = []

if "contador_sem_alerta" not in st.session_state:
    st.session_state.contador_sem_alerta = 0

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

    historico_sem_ultimo = historico[:-1]

    for i in range(111, len(historico_sem_ultimo)):
        janela = historico_sem_ultimo[i-110:i]
        ult = historico_sem_ultimo[i-1]

        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')
      pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
impares = sum(1 for n in janela if n != 0 and n % 2 != 0)

        

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
    if len(historico) < 17:
        return None
    X, y = extrair_features(historico)
    if len(X) == 0:
        return None
    modelo = RandomForestClassifier(n_estimators=300, max_depth=None, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_top3(modelo, historico):
    if len(historico) < 17:
        return [], []

    X, _ = extrair_features(historico)
    if X.size == 0:
        return [], []

    x = X[-1].reshape(1, -1)
    try:
        probas = modelo.predict_proba(x)[0]
        indices = np.argsort(probas)[::-1][:3]
        top3 = [int(i) for i in indices]

        vizinhos_totais = set()
        for numero in top3:
            vizinhos = get_neighbors(numero, k=2)
            vizinhos_totais.update(vizinhos)

        return top3, sorted(vizinhos_totais)
    except Exception as e:
        print(f"[ERRO PREVISÃO]: {e}")
        return [], []

# === LOOP PRINCIPAL ===
st.title("🎯 IA Roleta Profissional - Top 3 + Vizinhos (Conferência oculta)")
st_autorefresh(interval=5000, key="atualizacao")

try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro ao obter número da API: {e}")
    st.stop()

historico = st.session_state.historico

if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    # Verificação da previsão anterior
    if st.session_state.top3_com_vizinhos:
        st.session_state.total_top += 1
        if numero_atual in st.session_state.top3_com_vizinhos:
            st.session_state.acertos_top += 1
            resultado = f"✅ {numero_atual} estava nos vizinhos: 🟢"
        else:
            resultado = f"✅ {numero_atual} não estava: 🔴"
        time.sleep(4)
        enviar_telegram(resultado)

    # Nova previsão

# Garante que as variáveis existam
if "top3_anterior" not in st.session_state:
    st.session_state.top3_anterior = []
if "contador_sem_alerta" not in st.session_state:
    st.session_state.contador_sem_alerta = 0

modelo = treinar_modelo(historico)
if modelo:
    top3, com_vizinhos = prever_top3(modelo, historico)

    if top3 != st.session_state.top3_anterior:
        # Top3 mudou → envia alerta
        st.session_state.top3_anterior = top3
        st.session_state.contador_sem_alerta = 0
        mensagem = f"📊 <b>TOP 3 NÚMEROS:</b> {top3[0]}, {top3[1]}, {top3[2]}"
        enviar_telegram(mensagem)

    else:
        # Top3 igual ao anterior → incrementa o contador
        st.session_state.contador_sem_alerta += 1

        # Se passaram 3 rodadas e top3 ainda igual → aguarda nova mudança (não envia)
        if st.session_state.contador_sem_alerta >= 3:
            print("⏱ Aguardando novo Top3 após 3 rodadas...")


    
      
      
     
        

# === INTERFACE STREAMLIT ===
st.write("Último número:", numero_atual)
st.write(f"Acertos Top 3 + vizinhos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos números:", list(historico)[-12:])

# === SALVAR ESTADO ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "ultimo_alerta": st.session_state.ultimo_alerta,
    "top3_principal": st.session_state.top3_principal,
    "top3_com_vizinhos": st.session_state.top3_com_vizinhos
}, ESTADO_PATH)
