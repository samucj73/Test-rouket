import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque
import time
from streamlit_autorefresh import st_autorefresh
from pathlib import Path

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002880411750"
PROBABILIDADE_MINIMA = 0.02
MAX_HISTORICO = 1000
CAMINHO_HISTORICO = Path("historico_duzia_coluna.joblib")

# === HISTÓRICO PERSISTENTE ===
if CAMINHO_HISTORICO.exists():
    historico_carregado = joblib.load(CAMINHO_HISTORICO)
else:
    historico_carregado = deque(maxlen=MAX_HISTORICO)

if "historico" not in st.session_state:
    st.session_state.historico = historico_carregado

if "ultimo_alerta" not in st.session_state:
    st.session_state.ultimo_alerta = {"entrada": None, "resultado_enviado": None}

if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None

if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = None

historico = st.session_state.historico
ultimo_alerta = st.session_state.ultimo_alerta

# === FUNÇÕES DE FEATURES ===
ordem_roda = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
    20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# Mapeia número para sua posição na roleta
posicao_roda = {num: i for i, num in enumerate(ordem_roda)}
terco1 = set(ordem_roda[:13])
terco2 = set(ordem_roda[13:26])
terco3 = set(ordem_roda[26:])

def get_vizinhos_fisicos(numero):
    if numero not in posicao_roda:
        return -1, -1
    i = posicao_roda[numero]
    esquerda = ordem_roda[(i - 1) % 37]
    direita = ordem_roda[(i + 1) % 37]
    return esquerda, direita

def get_terco_fisico(numero):
    if numero in terco1:
        return 1
    elif numero in terco2:
        return 2
    elif numero in terco3:
        return 3
    else:
        return 0

def extrair_features(historico):
    features = []
    historico = list(historico)
    for i in range(1, len(historico)):
        amostra = historico[:i]
        freq_abs = [amostra.count(n) for n in range(37)]
        freq_ult5 = [amostra[-5:].count(n) for n in range(37)]
        freq_ult10 = [amostra[-10:].count(n) for n in range(37)]

        terminais = [n % 10 for n in amostra]
        freq_terminais = [terminais.count(t) for t in range(10)]

        duzias = [((n - 1) // 12) + 1 if n != 0 else 0 for n in amostra]
        freq_duzias = [duzias.count(d) for d in range(4)]

        colunas = [((n - 1) % 3) + 1 if n != 0 else 0 for n in amostra]
        freq_colunas = [colunas.count(c) for c in range(4)]

        cores = []
        for n in amostra:
            if n == 0:
                cores.append(0)
            elif n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                cores.append(1)  # vermelho
            else:
                cores.append(2)  # preto

        freq_cores = [cores.count(c) for c in range(3)]

        cor_igual = 1 if len(cores) >= 2 and cores[-1] == cores[-2] else 0
        repetido = 1 if len(amostra) >= 2 and amostra[-1] == amostra[-2] else 0
        soma = sum(amostra[-5:]) if len(amostra) >= 5 else sum(amostra)
        media = soma / min(len(amostra), 5)
        desvio = np.std(amostra[-5:]) if len(amostra) >= 5 else np.std(amostra)

        # === Novas features: Vizinhos físicos e Terço físico ===
        vizinhos_esq = []
        vizinhos_dir = []
        tercos = []

        for n in amostra:
            esq, dir = get_vizinhos_fisicos(n)
            vizinhos_esq.append(esq)
            vizinhos_dir.append(dir)
            tercos.append(get_terco_fisico(n))

        freq_viz_esq = [vizinhos_esq.count(n) for n in range(37)]
        freq_viz_dir = [vizinhos_dir.count(n) for n in range(37)]
        freq_tercos = [tercos.count(t) for t in range(4)]  # 0,1,2,3

        features.append(
            freq_abs + freq_ult5 + freq_ult10 + freq_terminais +
            freq_duzias + freq_colunas + freq_cores +
            [cor_igual, repetido, soma, media, desvio] +
            freq_viz_esq + freq_viz_dir + freq_tercos
        )
    return np.array(features)


# === TREINAMENTO DOS MODELOS ===
@st.cache_resource(show_spinner=False)
def treinar_modelos(historico):
    if len(historico) < 50:
        return None, None
    hist = list(historico)
    X = extrair_features(hist[:-1])
    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in hist[2:]]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in hist[2:]]
    X = X[-len(y_duzia):]

    modelo_duzia = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_split=4, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_split=4, random_state=42)

    modelo_duzia.fit(X, y_duzia)
    modelo_coluna.fit(X, y_coluna)
    return modelo_duzia, modelo_coluna

# === PREVISÕES COM MÉDIA DAS ÚLTIMAS 3 ENTRADAS ===
def prever_proxima_duzia(modelo, historico):
    if not modelo or len(historico) < 50:
        return None, 0.0
    X = extrair_features(historico)
    entradas = X[-3:]
    probas = np.mean([modelo.predict_proba([e])[0] for e in entradas], axis=0)
    classe = modelo.classes_[np.argmax(probas)]
    prob = max(probas)
    return classe, prob

def prever_proxima_coluna(modelo, historico):
    if not modelo or len(historico) < 50:
        return None, 0.0
    X = extrair_features(historico)
    entradas = X[-3:]
    probas = np.mean([modelo.predict_proba([e])[0] for e in entradas], axis=0)
    classe = modelo.classes_[np.argmax(probas)]
    prob = max(probas)
    return classe, prob

# === TELEGRAM ===
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, data=payload)
    except:
        pass

# === API DO NÚMERO ATUAL ===
def obter_numero_atual():
    try:
        r = requests.get(API_URL, timeout=5)
        r.raise_for_status()
        data = r.json()
        return int(data["data"]["result"]["outcome"]["number"])
    except Exception as e:
        st.error(f"Erro ao consultar API: {e}")
        return None

# === INTERFACE ===
st.set_page_config(page_title="IA Dúzia e Coluna", layout="centered")
st.title("🎯 IA de Roleta - Dúzia e Coluna")
st_autorefresh(interval=5000, key="refresh")

numero_atual = obter_numero_atual()

if numero_atual is not None:
    st.write(f"🎯 Último número: **{numero_atual}**")

    if len(historico) == 0 or numero_atual != historico[-1]:
        historico.append(numero_atual)
        joblib.dump(historico, CAMINHO_HISTORICO)
        st.write(f"🧠 Histórico: {len(historico)} números")

        if len(historico) >= 15 and (
            not ultimo_alerta["entrada"]
            or ultimo_alerta["resultado_enviado"] == ultimo_alerta["entrada"]
        ):
            modelo_duzia, modelo_coluna = treinar_modelos(historico)
            duzia, prob_duzia = prever_proxima_duzia(modelo_duzia, historico)
            coluna, prob_coluna = prever_proxima_coluna(modelo_coluna, historico)

            # Salvar as previsões
            st.session_state.duzia_prevista = duzia
            st.session_state.coluna_prevista = coluna

            mensagem = ""
            if prob_duzia >= PROBABILIDADE_MINIMA:
                mensagem += f"<b>D</b>: {duzia}\n"
            if prob_coluna >= PROBABILIDADE_MINIMA:
                mensagem += f"<b>C</b>: {coluna}\n"

            if mensagem:
                enviar_telegram(mensagem)
                st.success("✅ Alerta enviado")
                ultimo_alerta["entrada"] = numero_atual
                ultimo_alerta["resultado_enviado"] = None
        else:
            st.warning("⏳ Aguardando nova entrada")
            st.write(f"🔎 Histórico: {list(historico)}")

        # === Resultado final (GREEN/RED) ===
        if ultimo_alerta["entrada"] and ultimo_alerta["resultado_enviado"] != numero_atual:
            duzia_resultado = ((numero_atual - 1) // 12) + 1 if numero_atual != 0 else 0
            coluna_resultado = ((numero_atual - 1) % 3) + 1 if numero_atual != 0 else 0

            duzia_prevista = st.session_state.get("duzia_prevista")
            coluna_prevista = st.session_state.get("coluna_prevista")

            resultado = ""
            if duzia_prevista == duzia_resultado:
                resultado += "🟢 DÚZIA GREEN\n"
            else:
                resultado += "🔴 DÚZIA RED\n"

            if coluna_prevista == coluna_resultado:
                resultado += "🟢 COLUNA GREEN\n"
            else:
                resultado += "🔴 COLUNA RED\n"

            time.sleep(10)
            enviar_telegram(resultado)
            st.write("📬 Resultado enviado")
            ultimo_alerta["resultado_enviado"] = numero_atual
else:
    st.error("❌ Não foi possível obter número da API.")
