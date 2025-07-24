import streamlit as st
import requests
import os
import joblib
from collections import deque
from sklearn.ensemble import RandomForestClassifier
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HISTORICO = 300
PROBABILIDADE_MINIMA = 0.02
AUTOREFRESH_INTERVAL = 5000

# === TELEGRAM ===
TELEGRAM_IA_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_IA_CHAT_ID = "-1002796136111"
TELEGRAM_QUENTES_CHAT_ID = "5121457416"

def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_numero(dados):
    data = dados.get("data")
    if isinstance(data, dict):
        return int(data["result"]["outcome"]["number"])
    elif isinstance(data, list) and len(data) > 0:
        return int(data[0]["result"]["outcome"]["number"])
    else:
        return None

def extrair_features(historico):
    return [[n % 10] for n in historico]

def treinar_modelo(historico):
    if len(historico) < 35:
        return None, None
    X = extrair_features(historico[:-1])
    y_terminal = [n % 10 for n in historico[1:]]

    modelo_terminal = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_terminal.fit(X, y_terminal)
    salvar(modelo_terminal, MODELO_PATH)

    modelo_numeros = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_numeros.fit(X, historico[1:])
    return modelo_terminal, modelo_numeros

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 15:
        return []
    entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:2]

def prever_numeros_quentes(modelo, historico):
    if not modelo or len(historico) < 15:
        return []
    entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:5]

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

st.set_page_config(page_title="IA Sinais Roleta", layout="centered")
st.title("🎯 IA Sinais de Roleta: Terminais + Números Quentes")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {"entrada": [], "resultado_enviado": None, "quentes_enviados": []})

try:
    resposta = requests.get(API_URL)
    dados = resposta.json()
    numero_atual = extrair_numero(dados)
    if numero_atual is None:
        raise ValueError("Número atual não encontrado no JSON")
except Exception as e:
    st.error("Erro ao buscar número da roleta.")
    st.write("🔍 Detalhes:", e)
    numero_atual = None

if numero_atual is not None:
    st.write("🎲 Último número:", numero_atual)
    if not historico or historico[-1] != numero_atual:
        historico.append(numero_atual)
        salvar(historico, HISTORICO_PATH)

if len(historico) >= 15 and (not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual):
    modelo_terminal, modelo_numeros = treinar_modelo(historico)

    terminais_previstos = prever_terminais(modelo_terminal, historico)

    if terminais_previstos and terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
        terminais_escolhidos = [t[0] for t in terminais_previstos]

        mensagem = "🚨 <b>Entrada IA</b>\n📊 <b>Terminais previstos:</b>\n"
        for t, p in terminais_previstos:
            numeros_terminal = [n for n in range(37) if n % 10 == t]
            mensagem += f"{t} → {numeros_terminal} ({p:.2%})\n"
        mensagem += "🎯 Aguardando resultado..."

        enviar_telegram(mensagem, TELEGRAM_IA_CHAT_ID)

        ultimo_alerta.update({
            "entrada": terminais_escolhidos,
            "resultado_enviado": None
        })
        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
    else:
        st.warning("⚠️ Aguardando nova entrada da IA...")

if ultimo_alerta["entrada"] and ultimo_alerta.get("resultado_enviado") != numero_atual:
    deu_green = numero_atual % 10 in ultimo_alerta["entrada"]
    if deu_green:
        resultado = f"🟢 GREEN! Número {numero_atual}"
    else:
        resultado = f"🔴 RED! Número {numero_atual}"
    enviar_telegram(f"🎯 {resultado}", TELEGRAM_IA_CHAT_ID)
    st.markdown(resultado.replace("<b>", "**").replace("</b>", "**"))

    ultimo_alerta["resultado_enviado"] = numero_atual
    ultimo_alerta["entrada"] = []
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

if 'modelo_numeros' in locals() and modelo_numeros:
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

st.write("🔄 Última entrada prevista:", ultimo_alerta["entrada"])
st.write("🎯 Resultado já enviado para:", ultimo_alerta["resultado_enviado"])
