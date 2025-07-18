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
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
CAMINHO_HISTORICO = "historico_roleta.json"
CAMINHO_MODELO = "modelo_roleta_ia.pkl"

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ORDEM_ROLETA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
    10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# === FUNÇÕES ===
def extrair_features(janela):
    terminais = [n % 10 for n in janela]
    contagem = Counter(terminais)
    mais_comuns = contagem.most_common(3)
    features = {f"terminal_{i}": terminais.count(i) for i in range(10)}
    features["terminal_top1"] = mais_comuns[0][0] if len(mais_comuns) > 0 else -1
    features["terminal_top2"] = mais_comuns[1][0] if len(mais_comuns) > 1 else -1
    return features

def expandir_com_vizinhos(entrada):
    posicoes = {n: i for i, n in enumerate(ORDEM_ROLETA)}
    resultado = set(entrada)
    for num in entrada:
        if num not in posicoes:
            continue
        i = posicoes[num]
        vizinhos = [
            ORDEM_ROLETA[(i - 2) % 37],
            ORDEM_ROLETA[(i - 1) % 37],
            ORDEM_ROLETA[(i + 1) % 37],
            ORDEM_ROLETA[(i + 2) % 37],
        ]
        resultado.update(vizinhos)
    return sorted(resultado)

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except:
        pass

def get_numero_api():
    try:
        r = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        data = r.json()
        numero = data.get("data", {}).get("result", {}).get("outcome", {}).get("number")
        timestamp = data.get("data", {}).get("settledAt")
        if numero is not None and timestamp:
            return {"numero": int(numero), "timestamp": timestamp}
    except Exception as e:
        st.error(f"Erro API: {e}")
    return None

def salvar_historico(historico):
    with open(CAMINHO_HISTORICO, "w") as f:
        json.dump(list(historico), f)

def carregar_historico():
    if os.path.exists(CAMINHO_HISTORICO):
        with open(CAMINHO_HISTORICO, "r") as f:
            return deque(json.load(f), maxlen=100)
    return deque(maxlen=100)

def carregar_modelo():
    if os.path.exists(CAMINHO_MODELO):
        return joblib.load(CAMINHO_MODELO)
    return RandomForestClassifier(n_estimators=100, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, CAMINHO_MODELO)

# === INTERFACE STREAMLIT ===
st.set_page_config("🎯 Estratégia IA Roleta")
st.title("🎯 Estratégia com Inteligência Artificial (IA) - Terminais")

if st.button("🔁 Reiniciar"):
    if os.path.exists(CAMINHO_HISTORICO): os.remove(CAMINHO_HISTORICO)
    if os.path.exists(CAMINHO_MODELO): os.remove(CAMINHO_MODELO)
    st.session_state.historico = deque(maxlen=100)
    st.session_state.resultado_sinais = deque(maxlen=100)
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = {}
    st.rerun()
    if "alertas_enviados" not in st.session_state:
        st.session_state.alertas_enviados = set()

st_autorefresh(interval=5000, key="auto")

# === ESTADO INICIAL ===
if "historico" not in st.session_state:
    st.session_state.historico = carregar_historico()
if "resultado_sinais" not in st.session_state:
    st.session_state.resultado_sinais = deque(maxlen=100)
if "entrada_atual" not in st.session_state:
    st.session_state.entrada_atual = []
if "entrada_info" not in st.session_state:
    st.session_state.entrada_info = {}

modelo = carregar_modelo()
resultado = get_numero_api()

bloco_status = st.empty()
bloco_numero = st.empty()

if resultado is None:
    bloco_status.markdown("<i>⏳ Aguardando número da API...</i>", unsafe_allow_html=True)
    numero = None
    timestamp = None
else:
    numero = resultado["numero"]
    timestamp = resultado["timestamp"]

    novo = False
    if not st.session_state.historico or timestamp != st.session_state.historico[-1]["timestamp"]:
        st.session_state.historico.append(resultado)
        salvar_historico(st.session_state.historico)
        novo = True

    if novo:
        bloco_numero.markdown(f"""
        <div style='padding:20px; background-color:#111; color:#FFD700; font-size:48px; text-align:center; border-radius:12px;'>
        🎯 Número Atual: <b>{numero}</b>
        </div>
        <p style='text-align:center; font-size:14px;'>🕒 Sorteio registrado em: <code>{timestamp}</code></p>
        """, unsafe_allow_html=True)
    else:
        bloco_status.markdown("<i>⏳ Aguardando novo sorteio...</i>", unsafe_allow_html=True)
        numero = None

historico_numeros = [h["numero"] for h in st.session_state.historico]

# === TREINAMENTO RETROATIVO AUTOMÁTICO ===
if len(historico_numeros) >= 16 and not os.path.exists(CAMINHO_MODELO):
    X_treino = []
    y_treino = []
    for i in range(14, len(historico_numeros) - 1):
        janela = historico_numeros[i - 14:i - 2]
        numero_entrada = historico_numeros[i - 2]
        numero_resultado = historico_numeros[i - 1]
        features = extrair_features(janela)
        terminais = [n % 10 for n in janela]
        dominantes = [t for t, _ in Counter(terminais).most_common(2)]
        entrada = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada)
        X_treino.append(features)
        y_treino.append(1 if numero_resultado in entrada_expandida else 0)

    y_counter = Counter(y_treino)
    if len(y_counter) >= 2:
        modelo.fit(pd.DataFrame(X_treino), y_treino)
        salvar_modelo(modelo)
        st.success("🤖 Modelo treinado com base no histórico!")
    else:
        st.warning("⚠️ Dados insuficientes para treinar a IA com diversidade de classes.")

# === INTERFACE VISUAL ===
st.subheader("🎰 Últimos Números (15):")
ultimos_html = " | ".join(f"<b>{n}</b>" for n in historico_numeros[-15:])
st.markdown(f"<div style='font-size:20px; color:#fff; background:#222; padding:10px; border-radius:8px'>{ultimos_html}</div>", unsafe_allow_html=True)

# === IA - PREVISÃO E AVALIAÇÃO ===
if len(historico_numeros) >= 14:
    janela = historico_numeros[-14:-2]
    numero_13 = historico_numeros[-2]
    numero_14 = historico_numeros[-1]
    X = pd.DataFrame([extrair_features(janela)])

    try:
        probs = modelo.predict_proba(X)[0]
        if len(probs) == 1:
            prob = probs[0] if modelo.classes_[0] == 1 else 0
        else:
            prob = probs[1]
    except NotFittedError:
        st.warning("🔧 IA ainda não treinada. Aguardando mais dados...")
        prob = 0
    except Exception as e:
        st.error(f"Erro na previsão: {e}")
        prob = 0

if prob > 0.65 and not st.session_state.entrada_atual:
    terminais = [n % 10 for n in janela]
    contagem = Counter(terminais)
    dominantes = [t for t, _ in contagem.most_common(2)]
    entrada_principal = [n for n in range(37) if n % 10 in dominantes]
    entrada_expandida = expandir_com_vizinhos(entrada_principal)

    # === GERAR CHAVE ÚNICA PARA A ENTRADA
    chave_alerta = f"{tuple(sorted(dominantes))}_{numero_13}"

    if chave_alerta not in st.session_state.alertas_enviados:
        st.session_state.entrada_atual = entrada_expandida
        st.session_state.entrada_info = {
            "dominantes": dominantes,
            "base": janela,
            "gatilho": numero_13
        }

        enviar_telegram(
            f"🎯 Entrada IA:\nTerminais: {dominantes}\nNúcleos: {entrada_principal}\nEntrada completa: {entrada_expandida}"
        )
        st.session_state.alertas_enviados.add(chave_alerta)

    

# === STATUS VISUAL ===
st.subheader("📊 Histórico de Resultados")
st.write(list(st.session_state.resultado_sinais))

if st.session_state.resultado_sinais:
    st.line_chart([1 if r == "GREEN" else 0 for r in st.session_state.resultado_sinais])
