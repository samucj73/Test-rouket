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
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
PROB_MINIMA = 0.75  # filtro para entradas

# === DADOS DA ROULETA FÍSICA ===
ROULETTE_ORDER = [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
                  30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
                  29, 7, 28, 12, 35, 3, 26, 0]  # ordem física europeia

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=500)

if "acertos_top" not in st.session_state:
    st.session_state.acertos_top = 0
if "total_top" not in st.session_state:
    st.session_state.total_top = 0
if "top3_anterior" not in st.session_state:
    st.session_state.top3_anterior = []
if "contador_sem_alerta" not in st.session_state:
    st.session_state.contador_sem_alerta = 0
if "tipo_entrada_anterior" not in st.session_state:
    st.session_state.tipo_entrada_anterior = ""

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === FUNÇÕES ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro Telegram:", e)

def bloco_terco(numero):
    if numero == 0: return "zero"
    if numero in [27,13,36,11,30,8,23,10,5,24,16,33]: return "terco2"
    if numero in [32,15,19,4,21,2,25,17,34,6,27,13]: return "terco1"
    return "terco3"

def cor(numero):
    if numero == 0: return 'G'
    return 'R' if numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

def freq_valor(lista, valor):
    return lista.count(valor) / len(lista)

def distancia_fisica(n1, n2):
    """Distância mínima na ordem física da roleta"""
    if n1 not in ROULETTE_ORDER or n2 not in ROULETTE_ORDER:
        return 0
    idx1 = ROULETTE_ORDER.index(n1)
    idx2 = ROULETTE_ORDER.index(n2)
    diff = abs(idx1 - idx2)
    return min(diff, len(ROULETTE_ORDER) - diff)

def extrair_features(historico):
    historico = list(historico)
    X, y = [], []
    historico_sem_ultimo = historico[:-1]

    for i in range(111, len(historico_sem_ultimo)):
        janela = historico_sem_ultimo[i-110:i]
        ult = historico_sem_ultimo[i-1]

        # contagem de cores
        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')

        # pares / ímpares
        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = sum(1 for n in janela if n != 0 and n % 2 != 0)

        # info do último número
        terminal = ult % 10
        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0
        bloco = bloco_terco(ult)
        bloco_num = {"terco1": 1, "terco2": 2, "terco3": 3, "zero": 0}[bloco]

        # frequências recentes
        freq_d10 = [freq_valor([(n - 1)//12 + 1 if n != 0 else 0 for n in janela[-10:]], x) for x in range(4)]
        freq_d20 = [freq_valor([(n - 1)//12 + 1 if n != 0 else 0 for n in janela[-20:]], x) for x in range(4)]
        freq_d50 = [freq_valor([(n - 1)//12 + 1 if n != 0 else 0 for n in janela[-50:]], x) for x in range(4)]

        freq_c10 = [freq_valor([(n - 1)%3 + 1 if n != 0 else 0 for n in janela[-10:]], x) for x in range(4)]
        freq_c20 = [freq_valor([(n - 1)%3 + 1 if n != 0 else 0 for n in janela[-20:]], x) for x in range(4)]
        freq_c50 = [freq_valor([(n - 1)%3 + 1 if n != 0 else 0 for n in janela[-50:]], x) for x in range(4)]

        # tempo desde último zero
        tempo_zero = next((idx for idx, val in enumerate(reversed(janela), 1) if val == 0), len(janela))

        # sequência de mesma dúzia / coluna
        seq_duzia = 1
        seq_coluna = 1
        for n in reversed(janela[:-1]):
            if ((n - 1)//12 + 1 if n != 0 else 0) == duzia:
                seq_duzia += 1
            else:
                break
        for n in reversed(janela[:-1]):
            if ((n - 1)%3 + 1 if n != 0 else 0) == coluna:
                seq_coluna += 1
            else:
                break

        # repetição
        numero_repetiu = 1 if ult in janela[-5:-1] else 0
        duzia_repetiu = 1 if duzia in [(n - 1)//12 + 1 if n != 0 else 0 for n in janela[-5:-1]] else 0
        coluna_repetiu = 1 if coluna in [(n - 1)%3 + 1 if n != 0 else 0 for n in janela[-5:-1]] else 0

        # distância física média últimos 3 números
        dist_fisica = np.mean([distancia_fisica(ult, n) for n in janela[-3:]])

        features = [
            vermelhos, pretos, verdes,
            pares, impares,
            terminal, duzia, coluna, bloco_num,
            *freq_d10, *freq_d20, *freq_d50,
            *freq_c10, *freq_c20, *freq_c50,
            tempo_zero, seq_duzia, seq_coluna,
            numero_repetiu, duzia_repetiu, coluna_repetiu,
            dist_fisica
        ]

        X.append(features)
        y.append(historico_sem_ultimo[i])

    return np.array(X, dtype=np.float64), np.array(y, dtype=int)

def treinar_modelo(historico, tipo="duzia"):
    if len(historico) < 120:
        return None
    X, y_raw = extrair_features(historico)
    if len(X) == 0:
        return None
    if tipo == "duzia":
        y = [(n - 1) // 12 + 1 if n != 0 else 0 for n in y_raw]
    else:
        y = [(n - 1) % 3 + 1 if n != 0 else 0 for n in y_raw]
    modelo = RandomForestClassifier(n_estimators=400, max_depth=None, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_top2(modelo, historico):
    if len(historico) < 120:
        return [], [], 0
    X, _ = extrair_features(historico)
    if X.size == 0:
        return [], [], 0
    x = X[-1].reshape(1, -1)
    try:
        probas = modelo.predict_proba(x)[0]
        indices = np.argsort(probas)[::-1][:2]
        return [int(i) for i in indices], [probas[i] for i in indices], sum(probas[indices])
    except Exception as e:
        print(f"[ERRO PREVISÃO]: {e}")
        return [], [], 0

# === LOOP PRINCIPAL ===
st.title("🎯 IA Roleta Profissional - Dúzia ou Coluna mais provável")
st_autorefresh(interval=5000, key="atualizacao")

try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro ao obter número da API: {e}")
    st.stop()

historico = st.session_state.historico

if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    if st.session_state.top3_anterior:
        st.session_state.total_top += 1
        entrada_tipo = st.session_state.tipo_entrada_anterior
        if entrada_tipo == "duzia":
            valor = (numero_atual - 1) // 12 + 1 if numero_atual != 0 else 0
        else:
            valor = (numero_atual - 1) % 3 + 1 if numero_atual != 0 else 0

        if valor in st.session_state.top3_anterior:
            st.session_state.acertos_top += 1
            resultado = f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🟢"
        else:
            resultado = f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🔴"
        time.sleep(15)
        enviar_telegram(resultado)

modelo_d = treinar_modelo(historico, "duzia")
modelo_c = treinar_modelo(historico, "coluna")

if modelo_d and modelo_c:
    top_d, prob_d, soma_d = prever_top2(modelo_d, historico)
    top_c, prob_c, soma_c = prever_top2(modelo_c, historico)

    if soma_d >= soma_c:
        tipo = "duzia"
        top = top_d
        soma_prob = soma_d
    else:
        tipo = "coluna"
        top = top_c
        soma_prob = soma_c

    if soma_prob >= PROB_MINIMA:
        if top != st.session_state.top3_anterior or tipo != st.session_state.tipo_entrada_anterior:
            st.session_state.top3_anterior = top
            st.session_state.tipo_entrada_anterior = tipo
            st.session_state.contador_sem_alerta = 0
            mensagem = f"📊 <b>ENTRADA {tipo.upper()}S:</b> {top[0]}ª e {top[1]}ª (conf: {soma_prob:.2%})"
            enviar_telegram(mensagem)
        else:
            st.session_state.contador_sem_alerta += 1
            if st.session_state.contador_sem_alerta >= 3:
                st.session_state.top3_anterior = top
                st.session_state.tipo_entrada_anterior = tipo
                mensagem = f"📊 <b>ENTRADA {tipo.upper()}S (forçada):</b> {top[0]}ª e {top[1]}ª"
                enviar_telegram(mensagem)
                st.session_state.contador_sem_alerta = 0

# === INTERFACE STREAMLIT ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos números:", list(historico)[-12:])

# === SALVAR ESTADO ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "top3_anterior": st.session_state.top3_anterior,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior
}, ESTADO_PATH)

# Criar conteúdo do TXT com 20 números por linha
linhas = []
numeros = list(historico)
for i in range(0, len(numeros), 20):
    linha = " ".join(map(str, numeros[i:i+20]))
    linhas.append(linha)

conteudo_txt = "\n".join(linhas)

# Botão para baixar histórico como TXT
st.download_button(
    label="📥 Baixar histórico (.txt)",
    data=conteudo_txt,
    file_name="historico_roleta.txt",
    mime="text/plain"
)
