import streamlit as st
import requests
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import os
import joblib

# === CONFIGURAÇÃO ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico.pkl"
ROULETTE_NUMBERS = [
    0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26
]

# === ESTADOS ===
estado = st.session_state.get("estado", "coletando")
entrada_principal = st.session_state.get("entrada_principal", [])
vizinhos_entrada = st.session_state.get("vizinhos_entrada", [])
numero_alvo = st.session_state.get("numero_alvo", None)

# === HISTÓRICO COM JOBLIB ===
if os.path.exists(HISTORICO_PATH):
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=15)

def salvar_historico():
    joblib.dump(historico, HISTORICO_PATH)

def enviar_telegram(mensagem):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": mensagem})

def obter_numero():
    resp = requests.get(API_URL)
    if resp.status_code == 200:
        return resp.json()["data"]["result"]["outcome"]["number"]
    return None

def terminal(n): return n % 10

def vizinhos_fisicos(n):
    idx = ROULETTE_NUMBERS.index(n)
    return [ROULETTE_NUMBERS[(idx+i) % len(ROULETTE_NUMBERS)] for i in (-2, -1, 1, 2)]

# === INTERFACE ===
st.title("🎯 Estratégia de Roleta – Entrada Principal + Vizinhos")

numero = obter_numero()
if numero and (not historico or historico[-1] != numero):
    historico.append(numero)
    salvar_historico()

# Exibição dos últimos números:
st.markdown("### Últimos Números")
def cor(n):
    if n == historico[-1]:
        if estado=="verificando": return "green" if n in vizinhos_entrada else "red"
        return "orange"
    return "white"

for slice_i in range(0, len(historico), 5):
    linha = list(historico)[slice_i : slice_i+5]
    styled = ' &nbsp; - &nbsp; '.join(
        f"<span style='color:{cor(n)}; font-size:22px'><b>{n}</b></span>" for n in linha
    )
    st.markdown(f"<div style='text-align:center'>{styled}</div>", unsafe_allow_html=True)

# === LÓGICA ===
if estado=="coletando" and len(historico)>=12:
    ult12 = list(historico)[-12:]
    tcount = Counter(terminal(n) for n in ult12).most_common(2)
    if len(tcount)==2 and tcount[0][1]>=3 and tcount[1][1]>=3:
        t1, t2 = tcount[0][0], tcount[1][0]
        entrada_principal = [n for n in ult12 if terminal(n) in (t1, t2)]
        vizinhos_set = set()
        for principal in entrada_principal:
            vizinhos_set |= set(vizinhos_fisicos(principal))
        vizinhos_entrada = list(vizinhos_set)
        st.session_state.update({
            "estado": "aguardando13",
            "entrada_principal": entrada_principal,
            "vizinhos_entrada": vizinhos_entrada,
        })
        enviar_telegram(f"⚠️ Entrada possível gerada:\nPrincipais: {entrada_principal}")
elif estado=="aguardando13" and len(historico)>=13:
    num13 = historico[-1]
    ult12 = set(list(historico)[-13:-1])
    if num13 in ult12 or num13 in vizinhos_entrada:
        numero_alvo = num13
        st.session_state["estado"] = "verificando"
        enviar_telegram(f"🎯 ENTRADA ATIVADA! {numero_alvo} está válid* entrada será:* {entrada_principal + vizinhos_entrada}")
    else:
        st.session_state["estado"] = "coletando"
elif estado=="verificando" and len(historico)>=14:
    res = historico[-1]
    if res in entrada_principal + vizinhos_entrada:
        enviar_telegram(f"✅ GREEN ✔ com número {res}")
    else:
        enviar_telegram(f"❌ RED ✘ com número {res}")
    st.session_state.update({
        "estado": "coletando",
        "entrada_principal": [],
        "vizinhos_entrada": [],
        "numero_alvo": None
    })

# Exibir estado e entrada
st.markdown(f"**Estado atual:** {estado.replace('aguardando13','aguardando 13º')}") 
if entrada_principal:
    st.markdown(f"**Entrada principal:** {entrada_principal}")
if vizinhos_entrada:
    st.markdown(f"**Vizinhos:** {vizinhos_entrada}")

st_autorefresh(interval=5000, key="auto")
