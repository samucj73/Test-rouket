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
PROBABILIDADE_MINIMA = 0.50
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
    if modelo is None:
        return []

    X = extrair_features(historico)
    proba = modelo.predict_proba([X[-1]])[0]
    top_indices = np.argsort(proba)[::-1][:2]
    return [(i, proba[i]) for i in top_indices if proba[i] >= PROBABILIDADE_MINIMA]

def prever_numeros_quentes(modelo, historico):
    if modelo is None:
        return []

    X = extrair_features(historico)
    proba = modelo.predict_proba([X[-1]])[0]
    top_indices = np.argsort(proba)[::-1][:5]
    return list(top_indices)

def enviar_telegram(mensagem, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_IA_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem para o Telegram: {e}")

def obter_ultimo_numero():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            numero = int(data["winningNumber"])
            return numero
    except Exception as e:
        st.error(f"Erro ao obter o último número: {e}")
    return None

# === INICIALIZAÇÃO DO APP ===
st.set_page_config(layout="centered", page_title="IA Roleta")
st.title("🎰 IA Roleta")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {"entrada": [], "resultado_enviado": None, "terminais": []})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

numero_atual = obter_ultimo_numero()

if numero_atual is not None:
    if not historico or numero_atual != historico[-1]:
        historico.append(numero_atual)
        salvar(historico, HISTORICO_PATH)

    st.write(f"🎲 Último número: **{numero_atual}**")

    if len(historico) >= 35:
        modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros = treinar_modelo(historico)

        terminais_previstos = prever_terminais(modelo_terminal, historico)
        if terminais_previstos:
            terminais_escolhidos = [t[0] for t in terminais_previstos]
            entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)

            previsao_repetida = (
                set(entrada) == set(ultimo_alerta["entrada"]) and
                set(terminais_escolhidos) == set(ultimo_alerta["terminais"])
            )

            if not previsao_repetida:
                st.success(f"✅ Entrada IA: {entrada} | Terminais: {terminais_escolhidos}")
                mensagem = f"<b>🚨 Nova Entrada IA</b>\n🎯 Terminais: {terminais_escolhidos}\n🎯 Números sugeridos: {entrada}"

                duzia_prev = prever_multiclasse(modelo_duzia, historico)
                coluna_prev = prever_multiclasse(modelo_coluna, historico)

                mensagem += "\n📌 <b>Dúzia com maior chance:</b>\n"
                for d, prob in duzia_prev[:2]:
                    if d > 0:
                        mensagem += f"Dúzia {d} → {prob:.2%}\n"

                mensagem += "\n📌 <b>Coluna com maior chance:</b>\n"
                for c, prob in coluna_prev[:2]:
                    if c > 0:
                        mensagem += f"Coluna {c} → {prob:.2%}\n"

                enviar_telegram(mensagem, TELEGRAM_IA_CHAT_ID)

                ultimo_alerta.update({
                    "entrada": entrada,
                    "resultado_enviado": None,
                    "terminais": terminais_escolhidos
                })
                salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
        else:
            st.warning("⚠️ Aguardando nova previsão com probabilidade suficiente...")

    # Verifica GREEN/RED
    if ultimo_alerta["entrada"] and ultimo_alerta["resultado_enviado"] != numero_atual:
        if numero_atual in ultimo_alerta["entrada"]:
            contadores["green"] += 1
            resultado = "🟢 GREEN"
        else:
            contadores["red"] += 1
            resultado = "🔴 RED"

        salvar(contadores, CONTADORES_PATH)
        st.markdown(f"🎯 Resultado: **{resultado}**")

        enviar_telegram(f"🎯 Resultado: <b>{numero_atual}</b> → <b>{resultado}</b>", TELEGRAM_IA_CHAT_ID)

        ultimo_alerta["resultado_enviado"] = numero_atual
        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

    # 🔥 Números quentes
    if modelo_numeros:
        numeros_quentes = prever_numeros_quentes(modelo_numeros, historico)
        st.write("🔥 Números Quentes:", numeros_quentes)

        if numeros_quentes != ultimo_alerta.get("quentes_enviados"):
            msg_quentes = "<b>🔥 Números Quentes Previstos:</b>\n"
            for n in numeros_quentes:
                msg_quentes += f"{n}\n"
            enviar_telegram(msg_quentes, TELEGRAM_QUENTES_CHAT_ID)
            ultimo_alerta["quentes_enviados"] = numeros_quentes
            salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

# Mostrar contadores
col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
