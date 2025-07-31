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
TELEGRAM_CHAT_ID = "-1002880411750"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
CONFIANCA_MINIMA = 0.60  # 70%

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=500)

if "acertos_top" not in st.session_state:
    st.session_state.acertos_top = 0
if "total_top" not in st.session_state:
    st.session_state.total_top = 0
if "top3_anterior" not in st.session_state:
    st.session_state.top3_anterior = []
if "contador_sem_alerta" not in st.session_state:
    st.session_state.contador_sem_alerta = 0
if "ultima_confianca" not in st.session_state:
    st.session_state.ultima_confianca = 0.0

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
        impares = 5 - pares

        terminal = ult % 10
        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0

        bloco = bloco_terco(ult)
        bloco_num = {"terco1": 1, "terco2": 2, "terco3": 3, "zero": 0}[bloco]

        features = [
            vermelhos, pretos, verdes,
            pares, impares,
            terminal, duzia, coluna,
            bloco_num
        ]

        X.append(features)
        y.append(historico_sem_ultimo[i])

    return np.array(X, dtype=np.float64), np.array(y, dtype=int)

def treinar_modelo_duzia(historico):
    if len(historico) < 17:
        return None
    X, y_raw = extrair_features(historico)
    if len(X) == 0:
        return None
    y = [(n - 1) // 12 + 1 if n != 0 else 0 for n in y_raw]
    modelo = RandomForestClassifier(n_estimators=300, max_depth=None, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_duzias(modelo, historico):
    if len(historico) < 17:
        return [], 0.0

    X, _ = extrair_features(historico)
    if X.size == 0:
        return [], 0.0

    x = X[-1].reshape(1, -1)
    try:
        probas = modelo.predict_proba(x)[0]
        indices = np.argsort(probas)[::-1][:2]
        confianca = probas[indices[0]] + probas[indices[1]]
        return [int(i) for i in indices], confianca
    except Exception as e:
        print(f"[ERRO PREVISÃO DÚZIA]: {e}")
        return [], 0.0

# === LOOP PRINCIPAL ===
st.title("🎯 IA Roleta Profissional - 2 Dúzias mais Prováveis")
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

    # Conferência do resultado anterior
    if st.session_state.top3_anterior:
        st.session_state.total_top += 1
        duzia_atual = (numero_atual - 1) // 12 + 1 if numero_atual != 0 else 0
        if duzia_atual in st.session_state.top3_anterior:
            st.session_state.acertos_top += 1
            resultado = f"✅ Saiu {numero_atual} ({duzia_atual}ª dúzia): 🟢"
        else:
            resultado = f"✅ Saiu {numero_atual} ({duzia_atual}ª dúzia): 🔴"
        time.sleep(4)
        enviar_telegram(resultado)

# Previsão das duas dúzias mais prováveis
modelo = treinar_modelo_duzia(historico)
if modelo:
    duzias_previstas, confianca = prever_duzias(modelo, historico)
    st.session_state.ultima_confianca = confianca

    if confianca >= CONFIANCA_MINIMA:
        if duzias_previstas != st.session_state.top3_anterior:
            st.session_state.top3_anterior = duzias_previstas
            st.session_state.contador_sem_alerta = 0
            mensagem = f"📊 <b>ENTRADA DÚZIAS:</b> {duzias_previstas[0]}ª e {duzias_previstas[1]}ª (Confiança: {confianca:.0%})"
            enviar_telegram(mensagem)
        else:
            st.session_state.contador_sem_alerta += 1
            if st.session_state.contador_sem_alerta >= 3:
                print("⏱ Aguardando nova previsão após 3 rodadas...")
    else:
        print(f"🔕 Previsão ignorada (confiança {confianca:.0%} abaixo do mínimo de {CONFIANCA_MINIMA:.0%})")

# === INTERFACE STREAMLIT ===
st.write("Último número:", numero_atual)
st.write(f"Acertos nas Dúzias: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.metric("Confiança da última previsão", f"{st.session_state.ultima_confianca:.1%}")
st.write("Últimos números:", list(historico)[-12:])

# === SALVAR ESTADO ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "top3_anterior": st.session_state.top3_anterior,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "ultima_confianca": st.session_state.ultima_confianca
}, ESTADO_PATH)
