import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh
import auto_ping

auto_ping.manter_app_ativo()

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_RESULTADO_CHAT_ID = os.getenv("TELEGRAM_RESULTADO_CHAT_ID")
TELEGRAM_QUENTES_CHAT_ID = os.getenv("TELEGRAM_QUENTES_CHAT_ID")

MAX_HISTORICO = 100
PROBABILIDADE_MINIMA = 0.01  # Reduzido para teste

HISTORICO_PATH = "historico.joblib"
ULTIMO_ALERTA_PATH = "ultimo_alerta.joblib"
CONTADORES_PATH = "contadores.joblib"

def salvar(objeto, caminho):
    joblib.dump(objeto, caminho)

def carregar(caminho, padrao):
    return joblib.load(caminho) if os.path.exists(caminho) else padrao

# === Funções de Previsão ===
def treinar_modelo(historico):
    X = np.array([n % 10 for n in historico[:-1]]).reshape(-1, 1)
    y_terminal = np.array([n % 10 for n in historico[1:]])
    y_numeros = np.array(historico[1:])

    modelo_terminal = RandomForestClassifier(n_estimators=100)
    modelo_terminal.fit(X, y_terminal)

    modelo_numeros = RandomForestClassifier(n_estimators=100)
    modelo_numeros.fit(X, y_numeros)

    return modelo_terminal, modelo_numeros

def prever_terminais(modelo, historico):
    if not modelo or len(historico) < 15:
        return []
    ultima_entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(ultima_entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:2]

def prever_numeros_quentes(modelo, historico):
    if not modelo or len(historico) < 15:
        return []
    ultima_entrada = [[historico[-1] % 10]]
    probas = modelo.predict_proba(ultima_entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas)], key=lambda x: -x[1])[:5]

# === Telegram ===
def enviar_telegram(mensagem, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar para o Telegram: {e}")

# === INÍCIO DO APP ===
st.set_page_config(layout="centered", page_title="IA FODA")
st.title("🎰 IA FODA - Previsão de Roleta")
st_autorefresh(interval=5000, key="atualizacao")

# Carregar dados salvos
historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {
    "referencia": None,
    "entrada": [],
    "terminais": [],
    "resultado_enviado": None,
    "quentes_enviados": []
})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

# Buscar novo número
try:
    resposta = requests.get(API_URL)
    dados = resposta.json()
    numero_atual = int(dados["game_results"][0]["value"])
except Exception as e:
    st.error("Erro ao buscar dados da roleta.")
    numero_atual = None

if numero_atual is not None:
    st.write("🔄 Última entrada prevista:", ultimo_alerta["entrada"])
    st.write("🎯 Resultado já enviado para:", ultimo_alerta["resultado_enviado"])
    st.write("🔢 Número atual:", numero_atual)

    if not historico or numero_atual != historico[-1]:
        historico.append(numero_atual)
        salvar(historico, HISTORICO_PATH)

        # === TREINAMENTO ===
        if len(historico) >= 15:
            modelo_terminal, modelo_numeros = treinar_modelo(historico)

            # === GERA NOVA PREVISÃO SE NÃO HÁ ALERTA ATIVO ===
            if not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual:
                terminais_previstos = prever_terminais(modelo_terminal, historico)
                st.write("📊 Terminais previstos:", terminais_previstos)

                if terminais_previstos:
                    st.write("📉 Maior probabilidade:", terminais_previstos[0][1])

                    if terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
                        entrada = [n for n, _ in terminais_previstos]
                        ultimo_alerta["entrada"] = entrada
                        ultimo_alerta["referencia"] = numero_atual
                        ultimo_alerta["resultado_enviado"] = None
                        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

                        mensagem = "🚨 <b>Entrada IA</b>\n"
                        for terminal, prob in terminais_previstos:
                            mensagem += f"Terminal {terminal} → {prob:.2%}\n"
                        enviar_telegram(mensagem, TELEGRAM_CHAT_ID)
                        st.success("🚨 Alerta de entrada enviado!")
                    else:
                        st.warning("⚠️ Probabilidade insuficiente para entrada.")
                else:
                    st.warning("❌ Nenhum terminal previsto.")
            else:
                st.info("⏳ Aguardando novo número após entrada anterior...")
        else:
            st.warning("⏳ Aguardando mais histórico para treinar a IA.")
    else:
        st.info("⏳ Aguardando novo número...")

    # === VERIFICAÇÃO DE RESULTADO ===
    if ultimo_alerta["entrada"] and ultimo_alerta["resultado_enviado"] != numero_atual:
        if numero_atual % 10 in ultimo_alerta["entrada"]:
            mensagem = f"✅ <b>GREEN</b>\nTerminal: {numero_atual % 10}"
            contadores["green"] += 1
        else:
            mensagem = f"❌ <b>RED</b>\nTerminal: {numero_atual % 10}"
            contadores["red"] += 1

        enviar_telegram(mensagem, TELEGRAM_RESULTADO_CHAT_ID)
        ultimo_alerta["resultado_enviado"] = numero_atual
        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
        salvar(contadores, CONTADORES_PATH)

    # === NÚMEROS QUENTES ===
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
        st.warning("⚠️ Modelo de números quentes ainda não treinado.")

# === MOSTRAR CONTADORES ===
st.subheader("🎯 Resultados")
st.metric("✅ Green", contadores["green"])
st.metric("❌ Red", contadores["red"])
