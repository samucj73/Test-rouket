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
HISTORICO_PATH = Path("historico_dados.pkl")
MODELO_DUZIA_PATH = Path("modelo_duzia.pkl")
MODELO_COLUNA_PATH = Path("modelo_coluna.pkl")
prob_min_duzia = 0.55
prob_min_coluna = 0.55

# === FUNÇÕES ===

def enviar_telegram(mensagem):
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                     params={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"})
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def obter_numero_atual():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            return int(response.json().get("number"))
    except:
        pass
    return None

def extrair_features(historico):
    features = []
    for i in range(60, len(historico)):
        janela = list(historico)[i-60:i]

        freq = [janela.count(n) for n in range(37)]
        ultimos = janela[-10:]

        features.append(freq + ultimos)
    return features

def treinar_modelos(historico):
    if len(historico) < 80:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[60:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    X_filtrado, y_duzia_f, y_coluna_f = [], [], []
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

def prever_proxima(modelo, historico, prob_minima=0.55, bloquear_valor=None):
    if not modelo or len(historico) < 80:
        return None, 0.0
    X = extrair_features(historico)
    if not X:
        return None, 0.0

    try:
        probas = modelo.predict_proba([X[-1]])[0]
        classe = np.argmax(probas) + 1
        prob = probas[classe - 1]

        if bloquear_valor and classe == bloquear_valor:
            return None, 0.0

        if prob >= prob_minima:
            return classe, prob
    except:
        pass
    return None, 0.0

# === INICIALIZAÇÃO ===
st.set_page_config(layout="wide")
st_autorefresh(interval=5000, key="auto_refresh")

if HISTORICO_PATH.exists():
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=500)

if MODELO_DUZIA_PATH.exists():
    modelo_duzia = joblib.load(MODELO_DUZIA_PATH)
else:
    modelo_duzia = None

if MODELO_COLUNA_PATH.exists():
    modelo_coluna = joblib.load(MODELO_COLUNA_PATH)
else:
    modelo_coluna = None

if "estado" not in st.session_state:
    st.session_state.estado = {
        "ultimo_alerta": None,
        "green_duzia": 0,
        "green_coluna": 0,
        "total_duzia": 0,
        "total_coluna": 0,
        "previsao_pendente": None,
        "contador_retreino": 0,
    }

estado = st.session_state.estado

# === LOOP PRINCIPAL ===
numero_atual = obter_numero_atual()
if numero_atual is not None and (len(historico) == 0 or numero_atual != historico[-1]):
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    estado["contador_retreino"] += 1

    # Re-treinar a cada 10 sorteios
    if len(historico) >= 80 and estado["contador_retreino"] >= 10:
        modelo_duzia, modelo_coluna = treinar_modelos(historico)
        estado["contador_retreino"] = 0

    # Verifica GREEN/RED anterior
    if estado["previsao_pendente"]:
        previsao, tipo = estado["previsao_pendente"]
        if tipo == "duzia":
            estado["total_duzia"] += 1
            if ((numero_atual - 1) // 12) + 1 == previsao:
                estado["green_duzia"] += 1
                enviar_telegram("✅🟢 GREEN DÚZIA!")
            else:
                enviar_telegram("❌🔴 RED DÚZIA!")
        elif tipo == "coluna":
            estado["total_coluna"] += 1
            if ((numero_atual - 1) % 3) + 1 == previsao:
                estado["green_coluna"] += 1
                enviar_telegram("✅🟢 GREEN COLUNA!")
            else:
                enviar_telegram("❌🔴 RED COLUNA!")
        estado["previsao_pendente"] = None

    # Previsão nova
    bloquear_duzia = ((numero_atual - 1) // 12) + 1 if numero_atual != 0 else None
    bloquear_coluna = ((numero_atual - 1) % 3) + 1 if numero_atual != 0 else None

    duzia, p_d = prever_proxima(modelo_duzia, historico, prob_min_duzia, bloquear_valor=bloquear_duzia)
    coluna, p_c = prever_proxima(modelo_coluna, historico, prob_min_coluna, bloquear_valor=bloquear_coluna)

    if duzia or coluna:
        mensagem = f"🎯 <b>NA:</b> {numero_atual}"
        if duzia:
            mensagem += f"\nD: <b>{duzia}</b> ({p_d:.0%})"
            estado["previsao_pendente"] = (duzia, "duzia")
        if coluna:
            mensagem += f"\nC: <b>{coluna}</b> ({p_c:.0%})"
            estado["previsao_pendente"] = (coluna, "coluna")
        enviar_telegram(mensagem)

# === INTERFACE ===
st.title("🔮 Previsão de Roleta - DÚZIA e COLUNA")
st.metric("Último Número", numero_atual)
st.metric("Dúzia GREEN", f"{estado['green_duzia']}/{estado['total_duzia']}")
st.metric("Coluna GREEN", f"{estado['green_coluna']}/{estado['total_coluna']}")
