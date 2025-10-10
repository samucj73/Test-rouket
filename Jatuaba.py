import streamlit as st
import requests
import json
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import SGDClassifier
from sklearn.exceptions import NotFittedError

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002932611974"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_incremental.pkl"
HISTORICO_PATH = "historico.pkl"

# === INICIALIZAÇÃO ===
st.set_page_config(layout="wide")
st.title("🎯 Estratégia IA Inteligente - Versão Final (Alertas Simplificados)")

# === VARIÁVEIS DE ESTADO ===
if os.path.exists(HISTORICO_PATH):
    historico_salvo = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(historico_salvo, maxlen=200)
else:
    st.session_state.historico = deque(maxlen=200)

defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": [],
    "entrada_info": None,
    "alertas_enviados": set(),
    "feedbacks_processados": set(),
    "greens": 0,
    "reds": 0,
    "historico_probs": deque(maxlen=30),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# === AUTOREFRESH ===
st_autorefresh(interval=2500, key="refresh")

# === ORDEM FÍSICA ROLETA ===
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

# === CAPTURA DA API ===
try:
    resposta = requests.get(API_URL, timeout=5)
    if resposta.status_code == 200:
        dados = resposta.json()
        try:
            numero = int(dados["data"]["result"]["outcome"]["number"])
            timestamp = dados["data"]["settledAt"]
        except Exception:
            numero = None

        if numero is not None and timestamp != st.session_state.ultimo_timestamp:
            st.session_state.historico.append(numero)
            st.session_state.ultimo_timestamp = timestamp
            joblib.dump(list(st.session_state.historico), HISTORICO_PATH)
            st.success(f"🎯 Novo número: {numero}")
    else:
        st.error("Erro ao acessar a API.")
except Exception as e:
    st.error(f"Erro na requisição: {e}")

# === TREINAMENTO ===
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

# === PREVISÃO E ENTRADA INTELIGENTE ===
historico_numeros = list(st.session_state.historico)

if len(historico_numeros) >= 14:
    janela = historico_numeros[-14:-2]
    X = pd.DataFrame([extrair_features(janela)])

    try:
        probs = modelo.predict_proba(X)[0]
        prob = probs[1] if len(probs) > 1 else 0
    except Exception:
        prob = 0

    st.session_state.historico_probs.append(prob)

    if prob > 0.60 and not st.session_state.entrada_atual:
        terminais = [n % 10 for n in janela]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        historico_recente = list(st.session_state.historico)[-50:]
        contagem_freq = Counter(historico_recente)

        def score_numero(n):
            freq = contagem_freq[n]
            dist = min(abs(ROULETTE_ORDER.index(n) - ROULETTE_ORDER.index(d)) for d in entrada_principal)
            return freq + (1.5 if n in entrada_principal else 0) + (0.5 if dist <= 2 else 0)

        entrada_classificada = sorted(
            entrada_expandida, key=lambda n: score_numero(n), reverse=True
        )

        entrada_inteligente = entrada_classificada[:15]

        chave_alerta = f"{dominantes}-{entrada_inteligente}"
        if chave_alerta not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave_alerta)

            numeros_linha = " ".join(str(n) for n in entrada_inteligente)
            mensagem = f"{numeros_linha}"  # ✅ agora só uma linha
            enviar_telegram(mensagem)

        st.session_state.entrada_atual = entrada_inteligente
        st.session_state.entrada_info = {
            "terminais": dominantes,
            "entrada": entrada_inteligente,
            "probabilidade": round(prob, 3)
        }

# === FEEDBACK (CORRIGIDO E OTIMIZADO) ===
if st.session_state.entrada_atual:
    entrada = st.session_state.entrada_atual
    numero_atual = st.session_state.historico[-1]
    chave_feedback = f"{numero_atual}-{tuple(sorted(entrada))}"

    if chave_feedback not in st.session_state.feedbacks_processados:
        resultado = "✅ GREEN" if numero_atual in entrada else "❌ RED"
        cor = "green" if resultado == "✅ GREEN" else "red"

        # Mensagem mais clara
        st.markdown(
            f"<h3 style='color:{cor}'>{resultado} • Número: {numero_atual}</h3>",
            unsafe_allow_html=True
        )

        # Atualiza contador
        if resultado == "✅ GREEN":
            st.session_state.greens += 1
        else:
            st.session_state.reds += 1

        # Mensagem no Telegram com número
        enviar_telegram(f"{resultado} • Saiu {numero_atual}")

        st.session_state.feedbacks_processados.add(chave_feedback)

        # Aprendizado incremental
        try:
            janela = list(st.session_state.historico)[-14:-2]
            if len(janela) == 12:
                X_novo = pd.DataFrame([extrair_features(janela)])
                y_novo = [1 if numero_atual in entrada else 0]
                modelo.partial_fit(X_novo, y_novo, classes=[0, 1])
                salvar_modelo(modelo)
        except Exception as e:
            st.error(f"Erro no feedback: {e}")

    # Limpa entrada após processar
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = None

# === INTERFACE ===
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("✅ GREENS", st.session_state.greens)
with col2:
    st.metric("❌ REDS", st.session_state.reds)
with col3:
    total = st.session_state.greens + st.session_state.reds
    taxa = (st.session_state.greens / total * 100) if total > 0 else 0
    st.metric("🎯 Taxa de Acerto", f"{taxa:.1f}%")

st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-15:])

# === GRÁFICO DE CONFIANÇA ===
if st.session_state.historico_probs:
    st.subheader("📈 Confiança da IA (últimas previsões)")
    plt.figure(figsize=(6, 3))
    plt.plot(list(st.session_state.historico_probs), marker='o')
    plt.title("Evolução da Probabilidade")
    plt.xlabel("Últimas Rodadas")
    plt.ylabel("Confiança")
    plt.grid(True)
    st.pyplot(plt)
