import streamlit as st
import requests
import json
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from sklearn.linear_model import SGDClassifier
from sklearn.exceptions import NotFittedError

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_incremental.pkl"
HISTORICO_PATH = "historico.pkl"

# === INICIALIZAÇÃO ===
st.set_page_config(layout="wide")
st.title("🎯 Estratégia Reativa com IA e Telegram")

# Carrega histórico salvo
if os.path.exists(HISTORICO_PATH):
    historico_salvo = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(historico_salvo, maxlen=200)
else:
    st.session_state.historico = deque(maxlen=200)

if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []
if "entrada_info" not in st.session_state:
    st.session_state.entrada_info = None
if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# === AUTOREFRESH ===
st_autorefresh(interval=5000, key="refresh")

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-2, 3)]

def expandir_com_vizinhos(numeros):
    entrada = set()
    for numero in numeros:
        entrada.update(get_vizinhos(numero))
    return sorted(entrada)

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        st.error(f"Erro ao enviar para Telegram: {e}")

def extrair_features(janela):
    return {f"num_{i}": n for i, n in enumerate(janela)}

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

# === CAPTURA DO NÚMERO MAIS RECENTE ===
try:
    resposta = requests.get(API_URL, timeout=10)
    if resposta.status_code == 200:
        dados = resposta.json()
        try:
            numero = int(dados["data"]["result"]["outcome"]["number"])
            timestamp = dados["data"]["settledAt"]
        except Exception as e:
            st.error(f"Erro ao extrair número da API: {e}")
            numero = None

        if numero is not None and timestamp != st.session_state.ultimo_timestamp:
            st.session_state.historico.append(numero)
            st.session_state.ultimo_timestamp = timestamp
            st.success(f"🎯 Novo número: {numero} - {timestamp}")

            joblib.dump(list(st.session_state.historico), HISTORICO_PATH)
    else:
        st.error("Erro ao acessar a API.")
except Exception as e:
    st.error(f"Erro na requisição: {e}")

# === TREINAMENTO INICIAL ===
modelo = carregar_modelo()

if len(st.session_state.historico) >= 14:
    X, y = [], []
    historico = list(st.session_state.historico)
    for i in range(len(historico) - 13):
        janela = historico[i:i + 12]
        numero_13 = historico[i + 12]
        numero_14 = historico[i + 13]

        terminais = [n % 10 for n in janela]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada = [n for n in range(37) if n % 10 in dominantes]
        entrada_com_vizinhos = expandir_com_vizinhos(entrada)

        X.append(extrair_features(janela))
        y.append(1 if numero_14 in entrada_com_vizinhos else 0)

    df_X = pd.DataFrame(X)
    try:
        modelo.partial_fit(df_X, y, classes=[0, 1])
    except:
        modelo.fit(df_X, y)

    salvar_modelo(modelo)
    st.info("✅ Modelo treinado inicialmente com os últimos dados!")

# === PREVISÃO E ENTRADA ===
historico_numeros = list(st.session_state.historico)

if len(historico_numeros) >= 14:
    janela = historico_numeros[-14:-2]
    numero_13 = historico_numeros[-2]
    numero_14 = historico_numeros[-1]
    X = pd.DataFrame([extrair_features(janela)])

    try:
        probs = modelo.predict_proba(X)[0]
        prob = probs[1] if len(probs) > 1 else 0
    except NotFittedError:
        st.warning("🔧 IA ainda não treinada.")
        prob = 0
    except Exception as e:
        st.error(f"Erro na previsão: {e}")
        prob = 0

    if prob > 0.70 and not st.session_state.entrada_atual:
        terminais = [n % 10 for n in janela]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        chave_alerta = f"{numero_13}-{dominantes}"
        if chave_alerta not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave_alerta)

            mensagem = (
                f"🎯 Entrada IA:\n"
                f"Terminais: {dominantes}\n"
                f"Núcleos: {entrada_principal}\n"
                f"Entrada completa: {entrada_expandida}"
            )
            enviar_telegram(mensagem)

        st.session_state.entrada_atual = entrada_expandida
        st.session_state.entrada_info = {
            "terminais": dominantes,
            "nucleos": entrada_principal,
            "entrada": entrada_expandida,
            "janela": janela
        }

        st.session_state.entrada_info = {
            "terminais": dominantes,
            "nucleos": entrada_principal,
            "entrada": entrada_expandida
        }

# === FEEDBACK COM APRENDIZADO CONTÍNUO ===
# === FEEDBACK E AVALIAÇÃO ===
if st.session_state.entrada_atual:
    entrada = st.session_state.entrada_atual
    numero_atual = st.session_state.historico[-1]

    resultado = "✅ GREEN" if numero_atual in entrada else "❌ RED"
    cor = "green" if resultado == "✅ GREEN" else "red"
    st.markdown(f"<h3 style='color:{cor}'>{resultado} - Último número: {numero_atual}</h3>", unsafe_allow_html=True)

    # Enviar alerta de GREEN/RED somente se ainda não foi enviado para este número
    chave_resultado = f"{numero_atual}-{tuple(sorted(entrada))}"
    if chave_resultado not in st.session_state.alertas_enviados:
        st.session_state.alertas_enviados.add(chave_resultado)

        mensagem_resultado = f"{resultado} 🎯\nNúmero: {numero_atual}\nEntrada: {entrada}"
        enviar_telegram(mensagem_resultado)

        # Treinar IA com o novo feedback
        try:
            janela = list(st.session_state.historico)[-14:-2]  # Últimos 12 números antes do número_13
            if len(janela) == 12:
                X_novo = pd.DataFrame([extrair_features(janela)])
                y_novo = [1 if numero_atual in entrada else 0]
            if len(set(y_novo)) > 1:
                modelo.fit(X_novo, y_novo)
                salvar_modelo(modelo)
                st.success("🔄 IA atualizada com novo feedback!")
            else:
                st.warning("⚠️ Dados insuficientes para treinar: apenas uma classe presente.")

                
        except Exception as e:
            st.error(f"Erro no feedback de aprendizado: {e}")

    # Limpar entrada após avaliação
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = None




# === INTERFACE ===
st.subheader("📊 Histórico dos últimos números")
st.write(list(st.session_state.historico)[-15:])

if st.session_state.entrada_info:
    st.subheader("📥 Entrada atual sugerida pela IA")
    st.write(st.session_state.entrada_info)
