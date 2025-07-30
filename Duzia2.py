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
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")

# === ESTADO E HISTÓRICO ===
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

# Se existir estado salvo, carrega para o session_state
if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k,v in estado_salvo.items():
        st.session_state[k] = v

# === FUNÇÕES ===

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro Telegram:", e)

def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0: return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    for i in range(60, len(historico)):
        ultimos = historico[i - 60:i]
        entrada = []

        for janela in [10, 20]:
            d_freq = [0, 0, 0]
            c_freq = [0, 0, 0]
            for n in ultimos[-janela:]:
                if n == 0: continue
                d = ((n - 1) // 12)
                c = ((n - 1) % 3)
                d_freq[d] += 1
                c_freq[c] += 1
            entrada += d_freq + c_freq

        cores = {'R': 0, 'B': 0, 'G': 0}
        for n in ultimos[-20:]:
            cores[cor(n)] += 1
        entrada += [cores['R'], cores['B'], cores['G']]

        par = sum(1 for n in ultimos[-20:] if n != 0 and n % 2 == 0)
        impar = 20 - par
        entrada += [par, impar]

        alta = sum(1 for n in ultimos[-20:] if n > 18)
        baixa = sum(1 for n in ultimos[-20:] if 0 < n <= 18)
        entrada += [alta, baixa]

        entrada += ultimos[-5:]

        for j in range(-5, -1):
            entrada.append(ultimos[j] - ultimos[j - 1])

        X.append(entrada)
    return np.array(X, dtype=np.float64)

def treinar_modelos(historico):
    if len(historico) < 80:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[60:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    # Filtrar para evitar classes zero
    X_filtrado = []
    y_duzia_f = []
    y_coluna_f = []
    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_filtrado.append(xi)
            y_duzia_f.append(d)
            y_coluna_f.append(c)

    if not X_filtrado:
        return None, None

    modelo_duzia = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)

    modelo_duzia.fit(X_filtrado, y_duzia_f)
    modelo_coluna.fit(X_filtrado, y_coluna_f)

    joblib.dump(modelo_duzia, "modelo_duzia.pkl")
    joblib.dump(modelo_coluna, "modelo_coluna.pkl")

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico, prob_minima=0.60):
    if len(historico) < 80:
        return None, 0.0

    X = extrair_features(historico)
    if X.size == 0:
        return None, 0.0

    x = np.array(X[-1], dtype=np.float64).reshape(1, -1)

    try:
        probas = modelo.predict_proba(x)[0]
        classe = int(np.argmax(probas) + 1)
        prob = float(probas[classe - 1])
        if prob >= prob_minima:
            return classe, prob
        return None, prob
    except Exception as e:
        print(f"[ERRO DE PREVISÃO]: {e}")
        return None, 0.0

# === LOOP PRINCIPAL / INTERAÇÃO ===
st.title("🎯 IA Roleta - Dúzia & Coluna")

st_autorefresh(interval=5000, key="atualizacao")

# Busca número da API
try:
    resposta = requests.get(API_URL, timeout=10).json()
    numero_atual = int(resposta["number"]) if "number" in resposta else None
    if numero_atual is None:
        st.error("Número não encontrado na resposta da API.")
        st.stop()
except Exception as e:
    st.error(f"Erro ao obter número da API: {e}")
    st.stop()

historico = st.session_state.historico

# Atualiza histórico e modelos se novo número
if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    modelo_duzia, modelo_coluna = treinar_modelos(historico)

    if modelo_duzia and modelo_coluna:
        taxa_duzia = st.session_state.acertos_duzia / st.session_state.total_duzia if st.session_state.total_duzia else 0
        taxa_coluna = st.session_state.acertos_coluna / st.session_state.total_coluna if st.session_state.total_coluna else 0

        prob_min_duzia = 0.60 if taxa_duzia >= 0.5 else 0.55
        prob_min_coluna = 0.60 if taxa_coluna >= 0.5 else 0.55

        duzia, p_d = prever_proxima(modelo_duzia, historico, prob_min_duzia)
        coluna, p_c = prever_proxima(modelo_coluna, historico, prob_min_coluna)

        # Evita previsões iguais à posição atual
        duzia_atual = ((numero_atual - 1) // 12) + 1 if numero_atual != 0 else 0
        coluna_atual = ((numero_atual - 1) % 3) + 1 if numero_atual != 0 else 0
        if duzia == duzia_atual:
            duzia = None
        if coluna == coluna_atual:
            coluna = None

        # Evita alertas repetidos
        if (duzia, coluna) != st.session_state.ultimo_alerta and (duzia or coluna):
            mensagem = f"🎯 <b>NA:</b> {numero_atual}"
            if duzia: mensagem += f" | Dúzia: <b>{duzia}</b>"
            if coluna: mensagem += f" | Coluna: <b>{coluna}</b>"
            enviar_telegram(mensagem)
            st.session_state.ultimo_alerta = (duzia, coluna)

        # Resultado do alerta anterior
        if st.session_state.ultimo_alerta:
            ultima_duzia, ultima_coluna = st.session_state.ultimo_alerta
            resultado_msg = ""
            if ultima_duzia:
                st.session_state.total_duzia += 1
                if duzia_atual == ultima_duzia:
                    st.session_state.acertos_duzia += 1
                    resultado_msg += f"\n✅ Dúzia ({ultima_duzia}): 🟢"
                else:
                    resultado_msg += f"\n✅ Dúzia ({ultima_duzia}): 🔴"
            if ultima_coluna:
                st.session_state.total_coluna += 1
                if coluna_atual == ultima_coluna:
                    st.session_state.acertos_coluna += 1
                    resultado_msg += f"\n✅ Coluna ({ultima_coluna}): 🟢"
                else:
                    resultado_msg += f"\n✅ Coluna ({ultima_coluna}): 🔴"
            time.sleep(4)
            enviar_telegram(resultado_msg)

# === INTERFACE STREAMLIT ===
st.write("Último número:", numero_atual)
st.write(f"Acertos Dúzia: {st.session_state.acertos_duzia} / {st.session_state.total_duzia}")
st.write(f"Acertos Coluna: {st.session_state.acertos_coluna} / {st.session_state.total_coluna}")
st.write("Últimos números:", list(historico))

# Salva estado no disco para persistência
estado_para_salvar = {
    "acertos_duzia": st.session_state.acertos_duzia,
    "total_duzia": st.session_state.total_duzia,
    "acertos_coluna": st.session_state.acertos_coluna,
    "total_coluna": st.session_state.total_coluna,
    "ultimo_alerta": st.session_state.ultimo_alerta
}
joblib.dump(estado_para_salvar, ESTADO_PATH)
