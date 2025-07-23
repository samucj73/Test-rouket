import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HISTORICO = 30
PROBABILIDADE_MINIMA = 0.55
AUTOREFRESH_INTERVAL = 5000

# === TELEGRAM ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

# === FUNÇÕES ===
def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_terminal(numero):
    return numero % 10

def extrair_features(historico):
    return [[n % 10] for n in historico]

def treinar_modelo(historico):
    if len(historico) < 15:
        return None
    X = extrair_features(historico)
    y = [n % 10 for n in list(historico)[1:]]
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X[:-1], y)
    salvar(modelo, MODELO_PATH)
    return modelo

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 5:
        return []
    ultima_entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(ultima_entrada)[0]
    terminais_prob = sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])
    return terminais_prob[:2]

def gerar_entrada_com_vizinhos(terminais):
    numeros_base = []
    for t in terminais:
        numeros_base.extend([n for n in range(37) if n % 10 == t])
    entrada_completa = set()
    for numero in numeros_base:
        try:
            idx = ordem_roleta.index(numero)
            vizinhos = [ordem_roleta[(idx + i) % len(ordem_roleta)] for i in range(-2, 3)]
            entrada_completa.update(vizinhos)
        except ValueError:
            pass
    return sorted(entrada_completa)

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# === INÍCIO DO APP ===
st.set_page_config(page_title="IA Sinais Roleta", layout="centered")
st.title("🎯 IA Sinais de Roleta: Estratégia por Terminais Dominantes + Vizinhos")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

# === ESTADOS ===
historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {"referencia": None, "entrada": []})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

# === CONSULTA API ===
try:
    response = requests.get(API_URL, timeout=3)
    response.raise_for_status()
    data = response.json()
    numero_atual = data["data"]["result"]["outcome"]["number"]
    timestamp = data["data"]["startedAt"]
except Exception as e:
    st.error(f"⚠️ Erro ao acessar API: {e}")
    st.stop()

# === ATUALIZA HISTÓRICO ===
if not historico or numero_atual != historico[-1]:
    historico.append(numero_atual)
    salvar(historico, HISTORICO_PATH)

st.write("🎲 Último número:", numero_atual)

# === IA: TREINAMENTO / PREVISÃO ===
if len(historico) >= 15:
    modelo = treinar_modelo(historico)
    terminais_previstos = prever_terminais(modelo, historico)

    if terminais_previstos and terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
        terminais_escolhidos = [t[0] for t in terminais_previstos]
        entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)

        st.success(f"✅ Entrada IA: {entrada} | Terminais: {terminais_escolhidos}")
        st.write("🔍 Probabilidades:", terminais_previstos)

        # === ALERTA SE NOVA BASE ===
        if ultimo_alerta["referencia"] != historico[-2]:
            mensagem = "🚨 <b>Entrada IA</b>\n📊 <b>Terminais previstos:</b>\n"
            for t in terminais_escolhidos:
                numeros_terminal = [n for n in range(37) if n % 10 == t]
                mensagem += f"{t} → {numeros_terminal}\n"
            mensagem += "🎯 Aguardando resultado..."

            enviar_telegram(mensagem)
            ultimo_alerta = {
                "referencia": historico[-2],
                "entrada": entrada
            }
            salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

        # === RESULTADO (GREEN / RED) ===
        if ultimo_alerta["entrada"]:
            if numero_atual in ultimo_alerta["entrada"]:
                contadores["green"] += 1
                resultado = "🟢 GREEN!"
            else:
                contadores["red"] += 1
                resultado = "🔴 RED!"
            salvar(contadores, CONTADORES_PATH)
            st.markdown(f"📈 Resultado do número {numero_atual}: **{resultado}**")
    else:
        st.warning("⚠️ Aguardando nova entrada da IA...")
else:
    st.info("⏳ Aguardando dados suficientes para treinar a IA...")
    
# === RESULTADO (GREEN / RED) ===
# === RESULTADO (GREEN / RED) ===
if ultimo_alerta["entrada"] and ultimo_alerta.get("resultado_enviado") != numero_atual:
    if numero_atual in ultimo_alerta["entrada"]:
        contadores["green"] += 1
        resultado = "🟢 GREEN!"
    else:
        contadores["red"] += 1
        resultado = "🔴 RED!"
    salvar(contadores, CONTADORES_PATH)
    st.markdown(f"📈 Resultado do número {numero_atual}: **{resultado}**")

    # Enviar resultado para o Telegram
    mensagem_resultado = f"🎯 Resultado do número <b>{numero_atual}</b>: <b>{resultado}</b>"
    enviar_telegram(mensagem_resultado)

    # Marcar como resultado já enviado e limpar entrada
    ultimo_alerta["resultado_enviado"] = numero_atual
    ultimo_alerta["entrada"] = []
    ultimo_alerta["referencia"] = None  # zera base para permitir novo alerta
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)


#
# === CONTADORES ===
col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
