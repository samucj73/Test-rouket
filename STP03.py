import streamlit as st
import requests
import json
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_MAXIMO = 200
JANELA_ANALISE = 12
PROB_MINIMA = 0.75

# === FUNÇÕES AUXILIARES ===
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    else:
        return RandomForestClassifier()

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def extrair_numero_api():
    try:
        response = requests.get(API_URL)
        data = response.json()
        return data["result"]["outcome"]["number"], data["settledAt"]
    except Exception as e:
        st.error(f"Erro ao acessar API: {e}")
        return None, None

def obter_vizinhos(numero):
    ordem_fisica = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
        27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16,
        33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28,
        12, 35, 3, 26
    ]
    idx = ordem_fisica.index(numero)
    vizinhos = []
    for i in range(-5, 6):
        if i == 0:
            continue
        vizinhos.append(ordem_fisica[(idx + i) % len(ordem_fisica)])
    return vizinhos

# === ESTADO DO APP ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=HISTORICO_MAXIMO)
if "timestamps" not in st.session_state:
    st.session_state.timestamps = set()
if "modelo" not in st.session_state:
    st.session_state.modelo = carregar_modelo()
if "reds_recentes" not in st.session_state:
    st.session_state.reds_recentes = set()
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []

# === ATUALIZAÇÃO AUTOMÁTICA ===
st_autorefresh(interval=5000, key="atualizar")

# === CAPTURA DE NOVO NÚMERO ===
numero, timestamp = extrair_numero_api()
if numero is not None and timestamp not in st.session_state.timestamps:
    st.session_state.timestamps.add(timestamp)
    st.session_state.historico.append(numero)

    st.write(f"🎯 Último número: **{numero}** às {timestamp}")
    st.write(f"📋 Histórico ({len(st.session_state.historico)}): {list(st.session_state.historico)}")

    # === TREINAMENTO DA IA ===
    if len(st.session_state.historico) >= JANELA_ANALISE + 1:
        X = []
        y = []
        historico = list(st.session_state.historico)
        for i in range(len(historico) - JANELA_ANALISE):
            entrada = [n % 10 for n in historico[i:i + JANELA_ANALISE]]
            saida = historico[i + JANELA_ANALISE] % 10
            X.append(entrada)
            y.append(saida)
        df_X = pd.DataFrame(X, columns=[f"n{i}" for i in range(JANELA_ANALISE)])
        st.session_state.modelo.fit(df_X, y)
        salvar_modelo(st.session_state.modelo)

        # === PREDIÇÃO COM IA ===
        terminais = [n % 10 for n in historico[-JANELA_ANALISE:]]
        df_pred = pd.DataFrame([terminais], columns=[f"n{i}" for i in range(JANELA_ANALISE)])

        try:
            probs = st.session_state.modelo.predict_proba(df_pred)[0]
            if probs is not None and len(probs) == 10:
                contagem = Counter(terminais)
                dominantes = [t for t, _ in contagem.most_common(2)]

                probs_numeros = [(i, probs[i % 10]) for i in range(37) if i % 10 in dominantes]
                probs_numeros = [pn for pn in probs_numeros if pn[0] not in st.session_state.reds_recentes]

                # Ordena por probabilidade
                probs_numeros.sort(key=lambda x: x[1], reverse=True)

                top_numeros = probs_numeros[:3]

                # Se 4 primeiros tiverem probabilidade muito próxima, pega 4
                if len(probs_numeros) > 3:
                    delta = probs_numeros[0][1] - probs_numeros[3][1]
                    if delta < 0.05:
                        top_numeros = probs_numeros[:4]

                if top_numeros and top_numeros[0][1] >= PROB_MINIMA:
                    entrada = set()
                    for n, _ in top_numeros:
                        entrada.add(n)
                        entrada.update(obter_vizinhos(n))
                    entrada = sorted(entrada)

                    mensagem = f"""
🎯 *SINAL GERADO!*
Núcleos: {[n for n, _ in top_numeros]}
Entrada: {entrada}
Probabilidade: {top_numeros[0][1]:.2%}
                    """
                    enviar_telegram(mensagem)
                    st.success(mensagem)
                    st.session_state.entrada_atual = entrada
                else:
                    st.session_state.entrada_atual = []
                    st.info("⚠️ Nenhuma entrada gerada (probabilidade abaixo do mínimo ou sem dados confiáveis).")
        except Exception as e:
            st.warning(f"Erro na previsão: {e}")

    # === VERIFICAÇÃO DE GREEN/RED ===
    if st.session_state.entrada_atual:
        if numero in st.session_state.entrada_atual:
            enviar_telegram(f"✅ GREEN! Número: {numero}")
            st.success(f"✅ GREEN! Número {numero} estava na entrada.")
            st.session_state.entrada_atual = []
        else:
            enviar_telegram(f"❌ RED! Número: {numero}")
            st.error(f"❌ RED! Número {numero} não estava na entrada.")
            st.session_state.reds_recentes.add(numero)

    # Limita tamanho do set de REDs recentes
    if len(st.session_state.reds_recentes) > 20:
        st.session_state.reds_recentes = set(list(st.session_state.reds_recentes)[-20:])
