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
API_URL = "https://immersiverouletteapi.p.rapidapi.com/stats?duration=1"
HEADERS = {
    "x-rapidapi-host": "immersiverouletteapi.p.rapidapi.com",
    "x-rapidapi-key": "ac7aa3be68msha956ea230db77b4p19c2ecjsn6682bedf2461"
}
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
MODELO_DUZIA_PATH = Path("modelo_duzia.pkl")
MODELO_COLUNA_PATH = Path("modelo_coluna.pkl")
HISTORICO_PATH = Path("historico.npy")

# === FUNÇÕES ===
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except:
        pass

def extrair_features(historico):
    historico = list(historico)
    X = []
    for i in range(24, len(historico)):
        entrada = historico[i-24:i]
        features = {
            "ultimo": entrada[-1],
            "media": np.mean(entrada),
            "moda": max(set(entrada), key=entrada.count),
            "max": max(entrada),
            "min": min(entrada),
            "std": np.std(entrada),
        }
        X.append(list(features.values()))
    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 60:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[24:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_duzia.fit(X, y_duzia)
    modelo_coluna.fit(X, y_coluna)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

def carregar_modelos():
    if MODELO_DUZIA_PATH.exists() and MODELO_COLUNA_PATH.exists():
        modelo_duzia = joblib.load(MODELO_DUZIA_PATH)
        modelo_coluna = joblib.load(MODELO_COLUNA_PATH)
        return modelo_duzia, modelo_coluna
    return None, None

def carregar_historico():
    if HISTORICO_PATH.exists():
        return deque(np.load(HISTORICO_PATH).tolist(), maxlen=500)
    return deque(maxlen=500)

def salvar_historico(historico):
    np.save(HISTORICO_PATH, list(historico))

# === INICIALIZAÇÃO ===
st.set_page_config(page_title="IA Roleta - Dúzia & Coluna", layout="centered")
st.title("🎯 IA de Roleta - Previsão Dúzia & Coluna")

st_autorefresh(interval=5000, key="atualizacao")

historico = carregar_historico()
modelo_duzia, modelo_coluna = carregar_modelos()
acertos_duzia = st.session_state.get("acertos_duzia", 0)
erros_duzia = st.session_state.get("erros_duzia", 0)
acertos_coluna = st.session_state.get("acertos_coluna", 0)
erros_coluna = st.session_state.get("erros_coluna", 0)

# === COLETA DE DADOS DA API LIVE ===
try:
    resp = requests.get(API_URL, headers=HEADERS)
        dados = resp.json()
    st.write("🔍 Resposta da API:", dados)  # Mostrar no Streamlit para debug
except Exception as e:
    st.error(f"Erro ao acessar API: {e}")
    st.stop()

st.subheader(f"🟢 Último número: {numero_atual}")

if len(historico) > 0 and numero_atual == historico[-1]:
    st.info("Aguardando novo número...")
    st.stop()

historico.append(numero_atual)
salvar_historico(historico)

# === TREINAMENTO (se necessário) ===
if (len(historico) >= 60) and (modelo_duzia is None or modelo_coluna is None or len(historico) % 10 == 0):
    modelo_duzia, modelo_coluna = treinar_modelos(historico)

# === PREVISÃO ===
if modelo_duzia and modelo_coluna and len(historico) >= 60:
    X_input = extrair_features(historico)[-1].reshape(1, -1)
    duzia_pred = modelo_duzia.predict(X_input)[0]
    coluna_pred = modelo_coluna.predict(X_input)[0]

    st.markdown(f"""
    🔮 <b>Previsão IA:</b><br>
    • Dúzia: <b>{duzia_pred}</b><br>
    • Coluna: <b>{coluna_pred}</b>
    """, unsafe_allow_html=True)

    # === AVALIAÇÃO RESULTADO ===
    duzia_real = ((numero_atual - 1) // 12) + 1 if numero_atual != 0 else 0
    coluna_real = ((numero_atual - 1) % 3) + 1 if numero_atual != 0 else 0

    hit_duzia = duzia_pred == duzia_real
    hit_coluna = coluna_pred == coluna_real

    if hit_duzia:
        acertos_duzia += 1
    else:
        erros_duzia += 1

    if hit_coluna:
        acertos_coluna += 1
    else:
        erros_coluna += 1

    st.session_state["acertos_duzia"] = acertos_duzia
    st.session_state["erros_duzia"] = erros_duzia
    st.session_state["acertos_coluna"] = acertos_coluna
    st.session_state["erros_coluna"] = erros_coluna

    st.success(f"🎯 Resultado Dúzia: {'🟢' if hit_duzia else '🔴'}")
    st.success(f"🎯 Resultado Coluna: {'🟢' if hit_coluna else '🔴'}")

    # === ALERTA TELEGRAM ===
    mensagem = f"<b>🎯 Novo número: {numero_atual}</b>\n"
    mensagem += f"Dúzia prevista: <b>{duzia_pred}</b> ({'🟢' if hit_duzia else '🔴'})\n"
    mensagem += f"Coluna prevista: <b>{coluna_pred}</b> ({'🟢' if hit_coluna else '🔴'})"
    enviar_telegram(mensagem)

# === ESTATÍSTICAS ===
st.subheader("📊 Estatísticas")
st.write(f"✅ Acertos Dúzia: {acertos_duzia} | ❌ Erros: {erros_duzia}")
st.write(f"✅ Acertos Coluna: {acertos_coluna} | ❌ Erros: {erros_coluna}")
