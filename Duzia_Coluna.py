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
#TELEGRAM_TOKEN = "SEU_TOKEN"
#TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")

# === DISPOSIÇÃO FÍSICA DA ROLETA ===
ROULETTE_SEQUENCE = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
                     27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
                     16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
                     7, 28, 12, 35, 3, 26]

# === SESSION STATE ===
if "historico" not in st.session_state:
    if HISTORICO_PATH.exists():
        st.session_state.historico = joblib.load(HISTORICO_PATH)
    else:
        st.session_state.historico = deque(maxlen=500)

if "acertos_duzia" not in st.session_state:
    st.session_state.acertos_duzia = 0
if "total_duzia" not in st.session_state:
    st.session_state.total_duzia = 0
if "acertos_coluna" not in st.session_state:
    st.session_state.acertos_coluna = 0
if "total_coluna" not in st.session_state:
    st.session_state.total_coluna = 0
if "ultimo_alerta" not in st.session_state:
    st.session_state.ultimo_alerta = None

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
    vizinhos = []
    for i in range(-k, k + 1):
        vizinhos.append(ROULETTE_SEQUENCE[(idx + i) % len(ROULETTE_SEQUENCE)])
    return vizinhos

def bloco_terco(numero):
    if numero == 0: return "zero"
    if numero in [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]:
        return "terco2"
    elif numero in [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13]:
        return "terco1"
    else:
        return "terco3"

def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0: return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    for i in range(11, len(historico)):
        janela = historico[i-10:i]
        ult = historico[i-1]

        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')

        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = 10 - pares

        terminal = ult % 10
        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0

        vizinhos = get_neighbors(ult, k=2)
        viz_media = np.mean(vizinhos)

        bloco = bloco_terco(ult)
        bloco_num = {"terco1": 1, "terco2": 2, "terco3": 3, "zero": 0}[bloco]

        linha = [
            vermelhos, pretos, verdes,
            pares, impares,
            terminal, duzia, coluna,
            viz_media,
            bloco_num
        ]
        X.append(linha)
    return np.array(X, dtype=np.float64)

def treinar_modelos(historico):
    if len(historico) < 30:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[10:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    X_f, y_d_f, y_c_f = [], [], []
    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_f.append(xi)
            y_d_f.append(d)
            y_c_f.append(c)

    if not X_f:
        return None, None

    modelo_duzia = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)

    modelo_duzia.fit(X_f, y_d_f)
    modelo_coluna.fit(X_f, y_c_f)

    joblib.dump(modelo_duzia, "modelo_duzia.pkl")
    joblib.dump(modelo_coluna, "modelo_coluna.pkl")

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico, prob_minima=0.60):
    if len(historico) < 30:
        return None, 0.0

    X = extrair_features(historico)
    if X.size == 0:
        return None, 0.0

    x = np.array(X[-1]).reshape(1, -1)
    try:
        probas = modelo.predict_proba(x)[0]
        classe = int(np.argmax(probas) + 1)
        prob = float(probas[classe - 1])
        if prob >= prob_minima:
            return classe, prob
        return None, prob
    except Exception as e:
        print(f"[ERRO PREVISÃO]: {e}")
        return None, 0.0

# === LOOP PRINCIPAL ===
st.title("🎯 IA Roleta Profissional - Dúzia & Coluna")
st_autorefresh(interval=5000, key="atualizacao")

try:
    resposta = requests.get(API_URL, timeout=10).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro ao obter número da API: {e}")
    st.stop()





except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

historico = st.session_state.historico

if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    modelo_duzia, modelo_coluna = treinar_modelos(historico)

    if modelo_duzia and modelo_coluna:
        taxa_d = st.session_state.acertos_duzia / st.session_state.total_duzia if st.session_state.total_duzia else 0
        taxa_c = st.session_state.acertos_coluna / st.session_state.total_coluna if st.session_state.total_coluna else 0

        prob_d = 0.60 if taxa_d >= 0.5 else 0.55
        prob_c = 0.60 if taxa_c >= 0.5 else 0.55

        duzia, _ = prever_proxima(modelo_duzia, historico, prob_d)
        coluna, _ = prever_proxima(modelo_coluna, historico, prob_c)

        atual_d = ((numero_atual - 1) // 12 + 1) if numero_atual != 0 else 0
        atual_c = ((numero_atual - 1) % 3 + 1) if numero_atual != 0 else 0
        if duzia == atual_d: duzia = None
        if coluna == atual_c: coluna = None

        if (duzia, coluna) != st.session_state.ultimo_alerta and (duzia or coluna):
            msg = f"🎯 <b>NA:</b> {numero_atual}"
            if duzia: msg += f" | D: <b>{duzia}</b>"
            if coluna: msg += f" | C: <b>{coluna}</b>"
            enviar_telegram(msg)
            st.session_state.ultimo_alerta = (duzia, coluna)

        # Resultado da rodada anterior
        if st.session_state.ultimo_alerta:
            ud, uc = st.session_state.ultimo_alerta
            res = ""
            if ud:
                st.session_state.total_duzia += 1
                if atual_d == ud:
                    st.session_state.acertos_duzia += 1
                    res += f"\n✅ Dúzia ({ud}): 🟢"
                else:
                    res += f"\n✅ Dúzia ({ud}): 🔴"
            if uc:
                st.session_state.total_coluna += 1
                if atual_c == uc:
                    st.session_state.acertos_coluna += 1
                    res += f"\n✅ Coluna ({uc}): 🟢"
                else:
                    res += f"\n✅ Coluna ({uc}): 🔴"
            time.sleep(4)
            enviar_telegram(res)

# === UI STREAMLIT ===
st.write("Último número:", numero_atual)
st.write(f"Acertos Dúzia: {st.session_state.acertos_duzia} / {st.session_state.total_duzia}")
st.write(f"Acertos Coluna: {st.session_state.acertos_coluna} / {st.session_state.total_coluna}")
st.write("Últimos números:", list(historico))

joblib.dump({
    "acertos_duzia": st.session_state.acertos_duzia,
    "total_duzia": st.session_state.total_duzia,
    "acertos_coluna": st.session_state.acertos_coluna,
    "total_coluna": st.session_state.total_coluna,
    "ultimo_alerta": st.session_state.ultimo_alerta
}, ESTADO_PATH)
