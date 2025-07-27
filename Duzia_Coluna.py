import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import Counter, deque
import time
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
PROBABILIDADE_MINIMA = 0.08
MAX_HISTORICO = 100

# === HISTÓRICO E ALERTA ===
historico = deque(maxlen=MAX_HISTORICO)
ultimo_alerta = {
    "entrada": None,
    "resultado_enviado": None
}

# === FUNÇÕES ===

def extrair_features(historico):
    features = []
    for i in range(1, len(historico)):
        amostra = historico[:i+1]
        ultimo = amostra[-1]

        freq_abs = [amostra.count(n) for n in range(37)]
        freq_ult5 = [amostra[-5:].count(n) for n in range(37)] if len(amostra) >= 5 else [0]*37
        freq_ult10 = [amostra[-10:].count(n) for n in range(37)] if len(amostra) >= 10 else [0]*37

        terminais = [n % 10 for n in amostra]
        freq_terminais = [terminais.count(t) for t in range(10)]

        duzias = [((n-1)//12)+1 if n != 0 else 0 for n in amostra]
        colunas = [((n-1)%3)+1 if n != 0 else 0 for n in amostra]
        freq_duzias = [duzias.count(d) for d in range(4)]
        freq_colunas = [colunas.count(c) for c in range(4)]

        vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        pretos = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

        cores = [1 if n in vermelhos else 2 if n in pretos else 0 for n in amostra]
        freq_cores = [cores.count(c) for c in range(3)]

        cor_igual = int(cores[-1] == cores[-2]) if len(cores) >= 2 else 0
        repetido = int(amostra[-1] == amostra[-2]) if len(amostra) >= 2 else 0

        soma = sum(amostra)
        media = np.mean(amostra)

        features.append(freq_abs + freq_ult5 + freq_ult10 + freq_terminais +
                        freq_duzias + freq_colunas + freq_cores +
                        [cor_igual, repetido, soma, media])
    return features

def treinar_modelos(historico):
    if len(historico) < 15:
        return None, None

    X = extrair_features(historico)
    y_duzia = [((n - 1) // 12) + 1 for n in historico[1:] if n != 0]
    y_coluna = [((n - 1) % 3) + 1 for n in historico[1:] if n != 0]

    X = X[-len(y_duzia):]

    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_duzia.fit(X, y_duzia)
    modelo_coluna.fit(X, y_coluna)

    return modelo_duzia, modelo_coluna

def prever_proxima_duzia(modelo, historico):
    if not modelo or len(historico) < 6:
        return None, 0.0

    X = extrair_features(historico)
    entrada = [X[-1]]
    probas = modelo.predict_proba(entrada)[0]
    classe = modelo.classes_[np.argmax(probas)]
    prob = max(probas)
    return classe, prob

def prever_proxima_coluna(modelo, historico):
    if not modelo or len(historico) < 6:
        return None, 0.0

    X = extrair_features(historico)
    entrada = [X[-1]]
    probas = modelo.predict_proba(entrada)[0]
    classe = modelo.classes_[np.argmax(probas)]
    prob = max(probas)
    return classe, prob

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, data=payload)
    except:
        pass

def obter_numero_atual():
    try:
        r = requests.get(API_URL, timeout=5)
        r.raise_for_status()
        data = r.json()
        numero = int(data["data"]["result"]["outcome"]["number"])
        return numero
    except Exception as e:
        st.error(f"Erro ao consultar API: {e}")
        return None

# === STREAMLIT ===
st.set_page_config(page_title="IA Dúzia e Coluna", layout="centered")
st.title("🎯 IA de Roleta - Dúzia e Coluna")

st_autorefresh(interval=5000, key="refresh")

numero_atual = obter_numero_atual()
if numero_atual is not None:
    st.write(f"🎯 Último número: **{numero_atual}**")
    if len(historico) == 0 or numero_atual != historico[-1]:
        historico.append(numero_atual)
        st.write(f"🧠 Tamanho do histórico: {len(historico)}")


        if len(historico) >= 15 and (
            not ultimo_alerta["entrada"]
            or ultimo_alerta["resultado_enviado"] == ultimo_alerta["entrada"]
        ):
            modelo_duzia, modelo_coluna = treinar_modelos(historico)

            duzia, prob_duzia = prever_proxima_duzia(modelo_duzia, historico)
            coluna, prob_coluna = prever_proxima_coluna(modelo_coluna, historico)

            mensagem = ""
            if prob_duzia >= PROBABILIDADE_MINIMA:
                mensagem += f"🎯 <b>Entrada IA - DÚZIA</b>\nDúzia: {duzia}\n"
            if prob_coluna >= PROBABILIDADE_MINIMA:
                mensagem += f"🎯 <b>Entrada IA - COLUNA</b>\nColuna: {coluna}\n"

            if mensagem:
                enviar_telegram(mensagem)
                st.success("✅ Alerta enviado")
                ultimo_alerta["entrada"] = numero_atual
                ultimo_alerta["resultado_enviado"] = None
        else:
            st.warning("⏳ Aguardando próxima entrada")
            st.write(f"🔎 Histórico: {list(historico)}")
st.write(f"📍 último_alerta['entrada']: {ultimo_alerta['entrada']}")
st.write(f"📍 último_alerta['resultado_enviado']: {ultimo_alerta['resultado_enviado']}")
st.write(f"📍 Número atual: {numero_atual}")

        # Resultado do número anterior
        if ultimo_alerta["entrada"] and ultimo_alerta["resultado_enviado"] != numero_atual:
            duzia_resultado = ((numero_atual - 1) // 12) + 1 if numero_atual != 0 else 0
            coluna_resultado = ((numero_atual - 1) % 3) + 1 if numero_atual != 0 else 0

            resultado = ""
            if duzia == duzia_resultado:
                resultado += "🟢 DÚZIA GREEN\n"
            else:
                resultado += "🔴 DÚZIA RED\n"
            if coluna == coluna_resultado:
                resultado += "🟢 COLUNA GREEN\n"
            else:
                resultado += "🔴 COLUNA RED\n"

            enviar_telegram(resultado)
            st.write("🎯 Resultado enviado")
            ultimo_alerta["resultado_enviado"] = numero_atual
else:
    st.error("❌ Não foi possível obter número da API.")
