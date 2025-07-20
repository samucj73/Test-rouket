import streamlit as st
import requests
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_rf.pkl"
HISTORICO_PATH = "historico.pkl"

# === INICIALIZAÇÃO ===
st.set_page_config(layout="wide")
st.title("🎯 Estratégia Reativa com IA e Telegram (RandomForest)")

# Carregar histórico
if os.path.exists(HISTORICO_PATH):
    st.session_state.historico = deque(joblib.load(HISTORICO_PATH), maxlen=200)
else:
    st.session_state.historico = deque(maxlen=200)

# Estado persistente
for key, default in {
    "ultimo_timestamp": None,
    "entrada_atual": [],
    "entrada_info": None,
    "alertas_enviados": set(),
    "acertos": 0,
    "erros": 0,
    "avaliar_proximo": False,
    "entrada_prevista_para": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Auto atualização
st_autorefresh(interval=2000, key="refresh")

# Ordem da roleta europeia
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

# --- ALTERAÇÃO: reduzir vizinhos para 1 anterior e 1 posterior (total 3 números)
def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-1, 2)]  # vizinho anterior, atual e posterior

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
    return RandomForestClassifier(n_estimators=100, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

# CAPTURA DO NÚMERO MAIS RECENTE
try:
    resposta = requests.get(API_URL, timeout=5)
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

# TREINAMENTO
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

        # --- ALTERAÇÃO: filtrar os 3 números mais frequentes entre os dominantes, não todos
        numeros_dominantes = [n for n in janela if n % 10 in dominantes]
        contagem_numeros = Counter(numeros_dominantes)
        entrada = [num for num, _ in contagem_numeros.most_common(3)]  # pega top 3 números

        entrada_expandida = expandir_com_vizinhos(entrada)

        X.append(extrair_features(janela))
        y.append(1 if numero_14 in entrada_expandida else 0)

    df_X = pd.DataFrame(X)
    try:
        modelo.fit(df_X, y)
        salvar_modelo(modelo)
        st.info("✅ Modelo RandomForest treinado com sucesso!")
    except Exception as e:
        st.error(f"Erro no treinamento: {e}")

# PREVISÃO E ENTRADA
historico = list(st.session_state.historico)
if len(historico) >= 14:
    janela = historico[-14:-2]
    numero_13 = historico[-2]
    numero_14 = historico[-1]
    X_novo = pd.DataFrame([extrair_features(janela)])

    try:
        prob = modelo.predict_proba(X_novo)[0][1]
    except NotFittedError:
        prob = 0
        st.warning("🔧 Modelo ainda não treinado.")
    except Exception as e:
        prob = 0
        st.error(f"Erro na previsão: {e}")

    if prob > 0.60 and not st.session_state.entrada_atual:
        terminais = [n % 10 for n in janela]
        contagem = Counter(terminais)
        dominantes = [t for t, _ in contagem.most_common(2)]

        numeros_dominantes = [n for n in janela if n % 10 in dominantes]
        contagem_numeros = Counter(numeros_dominantes)
        entrada_principal = [num for num, _ in contagem_numeros.most_common(3)]  # top 3 números

        # --- ALTERAÇÃO: se prob alta (>0.80), aposta só os núcleos (sem vizinhos)
        if prob > 0.80:
            entrada_expandida = entrada_principal
        else:
            entrada_expandida = expandir_com_vizinhos(entrada_principal)

        # --- ALTERAÇÃO: limitar máximo de números na entrada expandida
        entrada_expandida = sorted(entrada_expandida)[:10]

        chave_alerta = f"{numero_13}-{dominantes}-{prob:.2f}"
        if chave_alerta not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave_alerta)
            mensagem = (
                f"🎯 Entrada IA:\n"
                f"Terminais: {dominantes}\n"
                f"Núcleos (top 3): {entrada_principal}\n"
                f"Entrada completa (limitada a 10): {entrada_expandida}\n"
                f"Probabilidade: {prob:.2%}"
            )
            enviar_telegram(mensagem)

        st.session_state.entrada_atual = entrada_expandida
        st.session_state.entrada_info = {
            "terminais": dominantes,
            "nucleos": entrada_principal,
            "entrada": entrada_expandida,
            "probabilidade": prob
        }
        st.session_state.avaliar_proximo = True
        st.session_state.entrada_prevista_para = numero_13

# AVALIAÇÃO GREEN/RED (APÓS novo número)
if st.session_state.avaliar_proximo and st.session_state.entrada_atual:
    entrada = st.session_state.entrada_atual
    numero_atual = st.session_state.historico[-1]

    resultado = "✅ GREEN" if numero_atual in entrada else "❌ RED"
    cor = "green" if resultado == "✅ GREEN" else "red"
    st.markdown(f"<h3 style='color:{cor}'>{resultado} - Último número: {numero_atual}</h3>", unsafe_allow_html=True)

    chave_resultado = f"{numero_atual}-{tuple(sorted(entrada))}"
    if chave_resultado not in st.session_state.alertas_enviados:
        st.session_state.alertas_enviados.add(chave_resultado)
        enviar_telegram(f"{resultado} 🎯\nNúmero: {numero_atual}\nEntrada: {entrada}")

        if resultado == "✅ GREEN":
            st.session_state.acertos += 1
        else:
            st.session_state.erros += 1

    # Limpa para próxima rodada
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = None
    st.session_state.avaliar_proximo = False
    st.session_state.entrada_prevista_para = None

# INTERFACE
st.subheader("📊 Últimos 15 números")
st.write(list(st.session_state.historico)[-15:])

if st.session_state.entrada_info:
    st.subheader("📥 Entrada atual sugerida")
    st.write(st.session_state.entrada_info)

# DESEMPENHO DA IA
total = st.session_state.acertos + st.session_state.erros
if total > 0:
    acuracia = 100 * st.session_state.acertos / total
    st.markdown(f"### 🎯 Desempenho da IA")
    st.markdown(f"**✅ Acertos:** {st.session_state.acertos}")
    st.markdown(f"**❌ Erros:** {st.session_state.erros}")
    st.markdown(f"**📈 Acurácia:** `{acuracia:.2f}%`")
