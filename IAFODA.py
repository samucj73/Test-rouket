
import streamlit as st
import requests
import os
import joblib
from collections import deque
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"
CONTADORES_PATH = "contadores.pkl"
AUTOREFRESH_INTERVAL = 5000
MAX_HISTORICO = 30
PROBABILIDADE_MINIMA = 0.35

# === TELEGRAM ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
TELEGRAM_CHAT_ID_QUENTES = "5121457416"

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

# === FUNÇÕES UTILITÁRIAS ===
def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_features(historico):
    features = []
    for i in range(1, len(historico)):
        atual = historico[i]
        anterior = historico[i - 1]
        terminal = atual % 10
        coluna = 1 if atual in range(1, 37, 3) else 2 if atual in range(2, 37, 3) else 3 if atual in range(3, 37, 3) else 0
        duzia = 1 if 1 <= atual <= 12 else 2 if 13 <= atual <= 24 else 3 if 25 <= atual <= 36 else 0
        paridade = 0 if atual != 0 and atual % 2 == 0 else 1 if atual != 0 else -1
        intervalo = abs(atual - anterior)
        features.append([terminal, coluna, duzia, paridade, intervalo])
    return features

def treinar_modelo(historico):
    if len(historico) < 13:
        return None
    X = extrair_features(historico)
    y_terminal = [n % 10 for n in list(historico)[2:]]
    y_duzia = [1 if 1 <= n <= 12 else 2 if 13 <= n <= 24 else 3 if 25 <= n <= 36 else 0 for n in list(historico)[2:]]
    y_coluna = [1 if n in range(1, 37, 3) else 2 if n in range(2, 37, 3) else 3 if n in range(3, 37, 3) else 0 for n in list(historico)[2:]]

    modelo_terminal = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_terminal.fit(X[:-1], y_terminal)
    modelo_duzia.fit(X[:-1], y_duzia)
    modelo_coluna.fit(X[:-1], y_coluna)

    salvar((modelo_terminal, modelo_duzia, modelo_coluna), MODELO_PATH)
    return modelo_terminal, modelo_duzia, modelo_coluna

def prever_multiclasse(modelos, historico):
    if not modelos or len(historico) < 5:
        return [], None, None
    modelo_terminal, modelo_duzia, modelo_coluna = modelos
    entrada = extrair_features(historico)[-1:]
    terminais_proba = modelo_terminal.predict_proba(entrada)[0]
    duzia_proba = modelo_duzia.predict_proba(entrada)[0]
    coluna_proba = modelo_coluna.predict_proba(entrada)[0]
    top_terminais = sorted([(i, p) for i, p in enumerate(terminais_proba)], key=lambda x: -x[1])[:2]
    duzia_prevista = np.argmax(duzia_proba) + 1
    coluna_prevista = np.argmax(coluna_proba) + 1
    return top_terminais, duzia_prevista, coluna_prevista

def prever_numeros_quentes(modelo_terminal, historico):
    if not modelo_terminal or len(historico) < 5:
        return []
    entrada = extrair_features(historico)[-1:]
    probas = modelo_terminal.predict_proba(entrada)[0]
    candidatos = []
    for terminal, prob in enumerate(probas):
        numeros_terminal = [n for n in range(37) if n % 10 == terminal]
        for n in numeros_terminal:
            candidatos.append((n, prob))
    candidatos_ordenados = sorted(candidatos, key=lambda x: -x[1])
    numeros_quentes = sorted(set([n for n, _ in candidatos_ordenados]), key=lambda n: -next(p for num, p in candidatos_ordenados if num == n))
    return numeros_quentes[:5]

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

def enviar_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# === APP ===
st.set_page_config(page_title="IA Roleta", layout="centered")
st.title("🎯 IA Roleta: Terminais + Dúzia + Coluna + Quentes")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {"referencia": None, "entrada": [], "terminais": [], "resultado_enviado": None})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

try:
    numero_atual = requests.get(API_URL, timeout=3).json()["data"]["result"]["outcome"]["number"]
except Exception as e:
    st.error(f"Erro na API: {e}")
    st.stop()

if not historico or numero_atual != historico[-1]:
    historico.append(numero_atual)
    salvar(historico, HISTORICO_PATH)

st.write("🎲 Último número:", numero_atual)

if len(historico) >= 15 and (not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual):
    modelos = treinar_modelo(historico)
    terminais_previstos, duzia_prevista, coluna_prevista = prever_multiclasse(modelos, historico)
    if terminais_previstos and terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
        terminais_escolhidos = [t[0] for t in terminais_previstos]
        entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)
        st.success(f"✅ Entrada IA: {entrada} | Terminais: {terminais_escolhidos}")
        st.write("🔍 Probabilidades:", terminais_previstos)
        st.write(f"🔢 Dúzia provável: {duzia_prevista}ª")
        st.write(f"📐 Coluna provável: {coluna_prevista}ª")

        if ultimo_alerta.get("referencia") != numero_atual:
            mensagem = "🚨 <b>Entrada IA</b>
📊 <b>Terminais previstos:</b>
"
            for t in terminais_escolhidos:
                mensagem += f"{t} → {[n for n in range(37) if n % 10 == t]}
"
            mensagem += f"
🔢 <b>Dúzia provável:</b> {duzia_prevista}ª"
            mensagem += f"
📐 <b>Coluna provável:</b> {coluna_prevista}ª"
            mensagem += "
🎯 Aguardando resultado..."
            enviar_telegram(TELEGRAM_CHAT_ID, mensagem)
            ultimo_alerta = {"referencia": numero_atual, "entrada": entrada, "terminais": terminais_escolhidos, "resultado_enviado": None}
            salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

# === QUENTES ===
numeros_quentes = prever_numeros_quentes(modelos[0], historico)
st.write("🔥 Números quentes:", numeros_quentes)
quentes_alertado = carregar("quentes_alertado.pkl", {"numero_referencia": None})
if quentes_alertado.get("numero_referencia") != numero_atual:
    msg_quentes = f"🔥 <b>NÚMEROS QUENTES</b>
📊 Mais prováveis: {numeros_quentes}
🎰 Último: {numero_atual}"
    enviar_telegram(TELEGRAM_CHAT_ID_QUENTES, msg_quentes)
    salvar({"numero_referencia": numero_atual}, "quentes_alertado.pkl")

# === RESULTADO GREEN/RED ===
if ultimo_alerta["entrada"] and ultimo_alerta.get("resultado_enviado") != numero_atual:
    if numero_atual in ultimo_alerta["entrada"]:
        contadores["green"] += 1
        resultado = "🟢 GREEN!"
    else:
        contadores["red"] += 1
        resultado = "🔴 RED!"
    salvar(contadores, CONTADORES_PATH)
    st.markdown(f"📈 Resultado do número {numero_atual}: **{resultado}**")
    enviar_telegram(TELEGRAM_CHAT_ID, f"🎯 Resultado: <b>{numero_atual}</b> → <b>{resultado}</b>")
    ultimo_alerta["resultado_enviado"] = numero_atual
    ultimo_alerta["entrada"] = []
    ultimo_alerta["terminais"] = []
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
