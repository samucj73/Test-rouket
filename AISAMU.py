import streamlit as st
import requests
import joblib
import os
import random
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = "historico_ia.pkl"
ENTRADA_ATUAL_PATH = "entrada_ia.pkl"
MODELO_PATH = "modelo_rf.pkl"
HISTORICO_LIMITE = 20
PROBABILIDADE_MINIMA = 0.75

# === VIZINHANÇA ORDEM FÍSICA ROLETA EUROPEIA ===
ORDEM_FISICA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
                13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
                20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]

def get_vizinhos(numero, n=2):
    vizinhos = []
    if numero not in ORDEM_FISICA:
        return vizinhos
    idx = ORDEM_FISICA.index(numero)
    for i in range(-n, n+1):
        vizinhos.append(ORDEM_FISICA[(idx + i) % len(ORDEM_FISICA)])
    return vizinhos

def extrair_terminais(lista):
    return [str(n)[-1] for n in lista]

def treinar_modelo(historico):
    if len(historico) < 21:
        return None

    X, y = [], []
    historico_list = list(historico)
    for i in range(len(historico_list) - 20):
        janela = historico_list[i:i+20]
        alvo = historico_list[i + 20]
        contagem = Counter(extrair_terminais(janela))
        vetor = [contagem.get(str(i), 0) for i in range(10)]
        X.append(vetor)
        y.append(str(alvo)[-1])  # terminal como string

    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_terminais(modelo, historico):
    contagem = Counter(extrair_terminais(list(historico)[-20:]))
    vetor = [[contagem.get(str(i), 0) for i in range(10)]]
    probas = modelo.predict_proba(vetor)[0]
    classes = modelo.classes_
    previsoes = list(zip(classes, probas))
    previsoes.sort(key=lambda x: x[1], reverse=True)
    top2 = [p for p in previsoes if p[1] >= PROBABILIDADE_MINIMA][:2]
    return top2

def gerar_entrada_com_vizinhos(terminais):
    entrada = set()
    for t in terminais:
        nums = [n for n in range(37) if str(n)[-1] == t]
        for n in nums:
            entrada.update(get_vizinhos(n, n=2))
    return list(entrada)

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=payload)
    except:
        pass

def carregar_objeto(path, padrao):
    if os.path.exists(path):
        return joblib.load(path)
    return padrao

def salvar_objeto(path, objeto):
    joblib.dump(objeto, path)

def obter_ultimo_numero():
    try:
        resposta = requests.get(API_URL, timeout=10)
        if resposta.status_code == 200:
            dados = resposta.json()
            numero = int(dados['data']['outcome']['number'])
            timestamp = dados['data']['startedAt']
            return numero, timestamp
    except:
        return None, None
    return None, None

# === INICIALIZAÇÃO ===
st.set_page_config(layout="centered", page_title="IA Roleta - Terminal", page_icon="🎯")
st_autorefresh(interval=5000, key="auto")

st.title("🎯 IA Roleta - Terminais Inteligentes")

historico = carregar_objeto(HISTORICO_PATH, deque(maxlen=HISTORICO_LIMITE + 1))
entrada_atual = carregar_objeto(ENTRADA_ATUAL_PATH, None)

numero_atual, timestamp = obter_ultimo_numero()
if numero_atual is not None:
    if not hasattr(st.session_state, "ultimo_timestamp"):
        st.session_state.ultimo_timestamp = ""

    if timestamp != st.session_state.ultimo_timestamp:
        st.session_state.ultimo_timestamp = timestamp
        historico.append(numero_atual)
        salvar_objeto(HISTORICO_PATH, historico)

      modelo = treinar_modelo(historico)
      if modelo:
          salvar_objeto(MODELO_PATH, modelo)
          terminais_previstos = prever_terminais(modelo, historico)
          st.write("Probabilidades previstas (terminal, prob):", terminais_previstos)
          
            if len(terminais_previstos) >= 1:
                digitos = [t[0] for t in terminais_previstos]
                entrada = gerar_entrada_com_vizinhos(digitos)
                if entrada:
                    entrada = list(set(entrada))
                    random.shuffle(entrada)
                    entrada = entrada[:10]
                    salvar_objeto(ENTRADA_ATUAL_PATH, {"numeros": entrada, "entrada_timestamp": timestamp})
                    enviar_telegram(f"🎯 Entrada IA Terminal ({digitos})\n🎰 Números: {entrada}")
                    entrada_atual = {"numeros": entrada, "entrada_timestamp": timestamp}

        # Verifica acerto do número anterior
        if entrada_atual and entrada_atual.get("entrada_timestamp") != timestamp:
            if numero_atual in entrada_atual["numeros"]:
                enviar_telegram(f"✅ GREEN! Saiu {numero_atual}")
            else:
                enviar_telegram(f"❌ RED! Saiu {numero_atual}")
            salvar_objeto(ENTRADA_ATUAL_PATH, None)

# === INTERFACE STREAMLIT ===
st.markdown("### Últimos números:")
st.write(list(historico))

if entrada_atual:
    st.markdown("### 🎯 Entrada gerada:")
    st.write(entrada_atual["numeros"])
else:
    st.info("⚠️ Aguardando nova entrada da IA...")
