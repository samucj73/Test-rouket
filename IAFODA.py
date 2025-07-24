import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette"
TELEGRAM_BOT_TOKEN = "TOKEN"
TELEGRAM_CHAT_ID = "CHAT_ID"
TELEGRAM_QUENTES_CHAT_ID = "CHAT_ID"
PROBABILIDADE_MINIMA = 0.02
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"

# === FUNÇÕES UTILITÁRIAS ===
def enviar_telegram(mensagem, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    dados = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}
    requests.post(url, data=dados)

def carregar(path):
    if os.path.exists(path):
        return joblib.load(path)
    return {"entrada": [], "resultado_enviado": None, "quentes_enviados": []}

def salvar(objeto, path):
    joblib.dump(objeto, path)

def treinar_modelo(historico):
    X = [[n % 10] for n in historico[:-1]]
    y_terminal = [n % 10 for n in historico[1:]]
    y_numero = [n for n in historico[1:]]
    modelo_terminal = RandomForestClassifier().fit(X, y_terminal)
    modelo_numeros = RandomForestClassifier().fit(X, y_numero)
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

# === INICIALIZAÇÕES ===
st_autorefresh(interval=5000, key="atualizacao")
historico = st.session_state.get("historico", deque(maxlen=100))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH)

# === BUSCA NÚMERO ATUAL DA RODA ===
try:
    resposta = requests.get(API_URL)
    dados = resposta.json()
    numero_atual = int(dados["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error("Erro ao buscar número da roleta.")
    st.write("🔍 Detalhes:", e)
    numero_atual = None

# === EXIBE HISTÓRICO ===
if numero_atual is not None:
    st.write("🔢 Número atual:", numero_atual)

    if not historico or historico[-1] != numero_atual:
        historico.append(numero_atual)
        st.session_state["historico"] = historico

# === TREINA MODELOS ===
if len(historico) >= 15:
    modelo_terminal, modelo_numeros = treinar_modelo(historico)

    # === PREVISÃO TERMINAIS ===
    if not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual:
        terminais_previstos = prever_terminais(modelo_terminal, historico)
        st.write("📊 Terminais previstos:", terminais_previstos)

        if terminais_previstos:
            st.write("📉 Maior probabilidade:", terminais_previstos[0][1])
            if terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
                entrada = [t[0] for t in terminais_previstos]
                mensagem = "🚨 <b>Entrada IA</b>\n"
                mensagem += "\n".join([f"Terminal {e} → {p:.2%}" for e, p in terminais_previstos])
                enviar_telegram(mensagem, TELEGRAM_CHAT_ID)
                ultimo_alerta["entrada"] = entrada
                ultimo_alerta["resultado_enviado"] = None
                salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
            else:
                st.warning("📉 Nenhuma previsão com probabilidade suficiente.")
        else:
            st.warning("❌ Modelo não retornou terminais.")
    else:
        st.warning("⚠️ Aguardando novo resultado antes de nova previsão.")

    # === VERIFICA SE DEU GREEN ===
    if ultimo_alerta["entrada"] and ultimo_alerta["resultado_enviado"] != numero_atual:
        terminal_resultado = numero_atual % 10
        if terminal_resultado in ultimo_alerta["entrada"]:
            resultado = f"🟢 Green! Número {numero_atual} (terminal {terminal_resultado})"
        else:
            resultado = f"🔴 Red. Número {numero_atual} (terminal {terminal_resultado})"
        enviar_telegram(resultado, TELEGRAM_CHAT_ID)
        ultimo_alerta["resultado_enviado"] = numero_atual
        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

    # === PREVISÃO DE NÚMEROS QUENTES ===
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
else:
    st.warning("⏳ Aguardando mais dados para treinar a IA...")

# === EXIBIÇÕES ===
st.write("📜 Histórico:", list(historico))
st.write("🔄 Última entrada prevista:", ultimo_alerta["entrada"])
if ultimo_alerta["resultado_enviado"]:
    st.write("🎯 Resultado já enviado para:", ultimo_alerta["resultado_enviado"])
