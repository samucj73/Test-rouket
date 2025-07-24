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
MAX_HISTORICO = 300
PROBABILIDADE_MINIMA = 0.20
AUTOREFRESH_INTERVAL = 5000

# === TELEGRAM ===
TELEGRAM_IA_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_IA_CHAT_ID = "-1002796136111"
TELEGRAM_QUENTES_CHAT_ID = "5121457416"

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_terminal(numero):
    return numero % 10

def extrair_duzia(numero):
    if numero == 0:
        return -1
    elif numero <= 12:
        return 1
    elif numero <= 24:
        return 2
    else:
        return 3

def extrair_coluna(numero):
    if numero == 0:
        return -1
    elif numero % 3 == 1:
        return 1
    elif numero % 3 == 2:
        return 2
    else:
        return 3

def extrair_features(historico):
    return [[n % 10] for n in historico]

def treinar_modelo(historico):
    if len(historico) < 35:
        return None, None, None, None

    X = extrair_features(historico)
    y_terminal = [n % 10 for n in list(historico)[1:]]
    y_duzia = [extrair_duzia(n) for n in list(historico)[1:]]
    y_coluna = [extrair_coluna(n) for n in list(historico)[1:]]
    y_numeros = list(historico)[1:]

    modelo_terminal = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_numeros = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_terminal.fit(X[:-1], y_terminal)
    modelo_duzia.fit(X[:-1], y_duzia)
    modelo_coluna.fit(X[:-1], y_coluna)
    modelo_numeros.fit(X[:-1], y_numeros)

    salvar(modelo_terminal, MODELO_PATH)
    return modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 15:
        return []
    ultima_entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(ultima_entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:2]

def prever_multiclasse(modelo, historico):
    if not modelo or len(historico) < 5:
        return []
    entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])

def prever_numeros_quentes(modelo, historico):
    if not modelo or len(historico) < 5:
        return []
    entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:5]

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

def enviar_telegram(mensagem, chat_id=TELEGRAM_IA_CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_IA_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# === INÍCIO DO APP ===
st.set_page_config(page_title="IA Sinais Roleta", layout="centered")
st.title("🎯 IA Sinais de Roleta: Terminais + Dúzia + Coluna + Quentes")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {
    "referencia": None,
    "entrada": [],
    "terminais": [],
    "resultado_enviado": None,
    "quentes_enviados": []
})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

try:
    response = requests.get(API_URL, timeout=3)
    response.raise_for_status()
    data = response.json()
    numero_atual = data["data"]["result"]["outcome"]["number"]
except Exception as e:
    st.error(f"⚠️ Erro ao acessar API: {e}")
    st.stop()

if not historico or numero_atual != historico[-1]:
    historico.append(numero_atual)
    salvar(historico, HISTORICO_PATH)

st.write("🎲 Último número:", numero_atual)

if len(historico) >= 15 and (not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual):
    modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros = treinar_modelo(historico)
    terminais_previstos = prever_terminais(modelo_terminal, historico)

    if terminais_previstos and terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
        terminais_escolhidos = [t[0] for t in terminais_previstos]
        entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)

        st.success(f"✅ Entrada IA: {entrada} | Terminais: {terminais_escolhidos}")
        st.write("🔍 Probabilidades:", terminais_previstos)

        ja_enviou_alerta = ultimo_alerta.get("referencia") == numero_atual
        previsao_repetida = (
            set(entrada) == set(ultimo_alerta.get("entrada", [])) and
            set(terminais_escolhidos) == set(ultimo_alerta.get("terminais", []))
        )

        if not ja_enviou_alerta and not previsao_repetida:
            mensagem = "🚨 <b>Entrada IA</b>\n📊 <b>Terminais previstos:</b>\n"
            for t in terminais_escolhidos:
                numeros_terminal = [n for n in range(37) if n % 10 == t]
                mensagem += f"{t} → {numeros_terminal}\n"
            mensagem += "🎯 Aguardando resultado..."

            duzia_prev = prever_multiclasse(modelo_duzia, historico)
            coluna_prev = prever_multiclasse(modelo_coluna, historico)

            mensagem += "\n📌 <b>Dúzia com maior chance:</b>\n"
            for d, prob in duzia_prev[:2]:
                if d != -1:
                    mensagem += f"Dúzia {d} → {prob:.2%}\n"

            mensagem += "\n📌 <b>Coluna com maior chance:</b>\n"
            for c, prob in coluna_prev[:2]:
                if c != -1:
                    mensagem += f"Coluna {c} → {prob:.2%}\n"

            enviar_telegram(mensagem, TELEGRAM_IA_CHAT_ID)

            ultimo_alerta.update({
                "referencia": numero_atual,
                "entrada": entrada,
                "terminais": terminais_escolhidos,
                "resultado_enviado": None
            })
            salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
    else:
        st.warning("⚠️ Aguardando nova entrada da IA...")
else:
    st.info("⏳ Aguardando dados suficientes para treinar a IA...")

if ultimo_alerta["entrada"] and ultimo_alerta.get("resultado_enviado") != numero_atual:
    deu_green = numero_atual in ultimo_alerta["entrada"]
    deu_quente = numero_atual in quentes

    if deu_green:
        contadores["green"] += 1
        resultado = "🟢 GREEN!"
    else:
        contadores["red"] += 1
        resultado = "🔴 RED!"

    salvar(contadores, CONTADORES_PATH)

    resultado_msg = f"📈 Resultado do número <b>{numero_atual}</b>: <b>{resultado}</b>"
    if deu_quente:
        resultado_msg += "\n🔥 Esse número estava entre os <b>quentes previstos</b> pela IA!"

    st.markdown(resultado_msg.replace("<b>", "**").replace("</b>", "**"))

    enviar_telegram(f"🎯 {resultado_msg}", TELEGRAM_IA_CHAT_ID)

    ultimo_alerta["resultado_enviado"] = numero_atual
    ultimo_alerta["entrada"] = []
    ultimo_alerta["terminais"] = []
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)



# 🔥 Números Quentes previstos pela IA
numeros_previstos = prever_numeros_quentes(modelo_numeros, historico)
quentes = [num for num, _ in numeros_previstos]
st.write("🔥 Números Quentes previstos pela IA:", quentes)

if ultimo_alerta.get("quentes_enviados") != quentes:
    mensagem_quentes = "🔥 <b>Números Quentes Previstos pela IA</b>\n"
    for num, prob in numeros_previstos:
        mensagem_quentes += f"{num} → {prob:.2%}\n"
    enviar_telegram(mensagem_quentes, TELEGRAM_QUENTES_CHAT_ID)
    ultimo_alerta["quentes_enviados"] = quentes
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
