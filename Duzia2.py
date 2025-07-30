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
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
HISTORICO_PATH = "historico_duzia_coluna.pkl"
MODELO_DUZIA_PATH = "modelo_duzia.pkl"
MODELO_COLUNA_PATH = "modelo_coluna.pkl"
ESTADO_PATH = "estado.pkl"

st_autorefresh(interval=5000, key="atualizacao")

# === VARIÁVEIS DE CONTROLE ===
estado = {
    "ultimo_alerta": None,
    "green_duzia": 0,
    "green_coluna": 0,
    "total_duzia": 0,
    "total_coluna": 0
}
if Path(ESTADO_PATH).exists():
    estado = joblib.load(ESTADO_PATH)

# === FUNÇÕES ===

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem: {e}")

def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0:
            return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    for i in range(60, len(historico)):
        ultimos = historico[i - 60:i]
        entrada = []

        # Frequência de dúzia e coluna (últimos 10 e 20)
        for janela in [10, 20]:
            d_freq = [0, 0, 0]
            c_freq = [0, 0, 0]
            for n in ultimos[-janela:]:
                if n == 0:
                    continue
                d = ((n - 1) // 12)
                c = ((n - 1) % 3)
                d_freq[d] += 1
                c_freq[c] += 1
            entrada += d_freq + c_freq

        # Frequência cor (R, B, G)
        cores = {'R': 0, 'B': 0, 'G': 0}
        for n in ultimos[-20:]:
            cores[cor(n)] += 1
        entrada += [cores['R'], cores['B'], cores['G']]

        # Par / ímpar
        par = sum(1 for n in ultimos[-20:] if n != 0 and n % 2 == 0)
        impar = 20 - par
        entrada += [par, impar]

        # Alta / baixa
        alta = sum(1 for n in ultimos[-20:] if n > 18)
        baixa = sum(1 for n in ultimos[-20:] if 0 < n <= 18)
        entrada += [alta, baixa]

        # Últimos 5 números brutos
        entrada += ultimos[-5:]

        # Diferenças entre últimos números
        for j in range(-5, -1):
            entrada.append(ultimos[j] - ultimos[j - 1])

        X.append(entrada)
    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 80:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[60:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    X_filtrado = []
    y_duzia_f = []
    y_coluna_f = []
    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_filtrado.append(xi)
            y_duzia_f.append(d)
            y_coluna_f.append(c)

    modelo_duzia = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)

    modelo_duzia.fit(X_filtrado, y_duzia_f)
    modelo_coluna.fit(X_filtrado, y_coluna_f)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico, prob_minima=0.60):
    if len(historico) < 80:
        return None, 0.0

    X = extrair_features(historico)
    if len(X) == 0:
        return None, 0.0

    x = np.array(X[-1]).reshape(1, -1)

    try:
        probas = modelo.predict_proba(x)[0]
        classe = np.argmax(probas) + 1
        prob = probas[classe - 1]
        if prob >= prob_minima:
            return classe, prob
        return None, prob
    except Exception as e:
        print(f"Erro previsão: {e}")
        return None, 0.0



# === HISTÓRICO E MODELOS ===
historico = joblib.load(HISTORICO_PATH) if Path(HISTORICO_PATH).exists() else deque(maxlen=500)
modelo_duzia = joblib.load(MODELO_DUZIA_PATH) if Path(MODELO_DUZIA_PATH).exists() else None
modelo_coluna = joblib.load(MODELO_COLUNA_PATH) if Path(MODELO_COLUNA_PATH).exists() else None

# === OBTÉM NOVO NÚMERO ===
try:
    resp = requests.get(API_URL)
    numero_atual = int(resp.json()["data"]["result"]["outcome"]["number"])
except:
    st.error("Erro ao acessar API.")
    st.stop()

# === NOVO NÚMERO DETECTADO ===
if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    # Re-treinar modelos a cada 10
    if len(historico) >= 80 and len(historico) % 10 == 0:
        modelo_duzia, modelo_coluna = treinar_modelos(historico)

    # Fazer previsões
    if modelo_duzia and modelo_coluna:
        # Ajuste dinâmico da probabilidade mínima
        taxa_duzia = estado["green_duzia"] / estado["total_duzia"] if estado["total_duzia"] else 0
        taxa_coluna = estado["green_coluna"] / estado["total_coluna"] if estado["total_coluna"] else 0
        prob_min_duzia = 0.55 if taxa_duzia < 0.5 else 0.60
        prob_min_coluna = 0.55 if taxa_coluna < 0.5 else 0.60

        duzia, p_d = prever_proxima(modelo_duzia, historico, prob_min_duzia)
        coluna, p_c = prever_proxima(modelo_coluna, historico, prob_min_coluna)

        mensagem = f"🎯 <b>NA:</b> {numero_atual}"
        if duzia:
            mensagem += f"\n🎯 Dúzia Prevista: <b>{duzia}</b>"
        if coluna:
            mensagem += f"\n🎯 Coluna Prevista: <b>{coluna}</b>"

        entrada = (duzia, coluna)
        if entrada != estado["ultimo_alerta"]:
            enviar_telegram(mensagem)
            estado["ultimo_alerta"] = entrada

        # Verifica se foi GREEN
        if duzia:
            estado["total_duzia"] += 1
            if ((numero_atual - 1) // 12) + 1 == duzia:
                estado["green_duzia"] += 1
        if coluna:
            estado["total_coluna"] += 1
            if ((numero_atual - 1) % 3) + 1 == coluna:
                estado["green_coluna"] += 1

        joblib.dump(estado, ESTADO_PATH)

        st.success(mensagem)
    else:
        st.warning("Aguardando modelo...")
else:
    st.info("Aguardando novo número...")

# === EXIBIÇÃO ===
st.metric("🎯 GREEN Dúzia", estado["green_duzia"])
st.metric("🎯 GREEN Coluna", estado["green_coluna"])
st.metric("🎲 Total Dúzia", estado["total_duzia"])
st.metric("🎲 Total Coluna", estado["total_coluna"])
st.markdown("### Últimos números")
st.write(list(historico))
