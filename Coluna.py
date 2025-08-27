import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import logging
from alertas_coluna import enviar_previsao, enviar_resultado, get_coluna

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
HIST_PATH = Path("historico_coluna_pro.pkl")
MAX_HISTORICO = 500

# =========================
# DISPOSIÇÃO FÍSICA DA ROLETA
# =========================
ROULETTE_ORDER = [
    0,32,15,19,4,21,2,25,17,34,6,27,
    13,36,11,30,8,23,10,5,24,16,33,1,
    20,14,31,9,22,18,29,7,28,12,35,3,26
]

def vizinhos_fisicos(num, n_vizinhos=2):
    if num==0: return [0]*(2*n_vizinhos)
    idx = ROULETTE_ORDER.index(num)
    vizinhos=[]
    for i in range(1,n_vizinhos+1):
        vizinhos.append(ROULETTE_ORDER[(idx-i)%len(ROULETTE_ORDER)])
        vizinhos.append(ROULETTE_ORDER[(idx+i)%len(ROULETTE_ORDER)])
    return vizinhos

def get_tier(num):
    """Terço físico da roleta: 1,2,3"""
    if num==0: return 0
    idx = ROULETTE_ORDER.index(num)
    terco = (idx)//12 + 1
    return terco

# =========================
# FEATURES BASE
# =========================
def get_duzia(num):
    if num==0: return 0
    return (num-1)//12 +1

def get_paridade(num):
    return 2 if num==0 else num%2

VERMELHOS={1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
def get_cor(num):
    if num==0: return 2
    return 0 if num in VERMELHOS else 1

def get_terminal(num):
    return num%10

def get_terminal_dominante(hist):
    ultimos=[get_terminal(n) for n in hist[-10:]]
    return Counter(ultimos).most_common(1)[0][0] if ultimos else 0

def calcular_offlines(hist, n=36):
    """Retorna dict com rodadas desde que cada número saiu"""
    offline={i:0 for i in range(n+1)}
    for i,num in enumerate(hist):
        for key in offline.keys():
            if key!=num:
                offline[key]+=1
            else:
                offline[key]=0
    return offline

# =========================
# CRIAR FEATURES
# =========================
def criar_features(historico):
    hist_list=list(historico)
    X,y=[],[]
    offline=calcular_offlines(hist_list)

    for i in range(len(hist_list)-5):
        janela=hist_list[i:i+5]
        alvo=get_coluna(hist_list[i+5])

        feat=[]
        # últimos números
        feat.extend(janela)
        # colunas
        feat.extend([get_coluna(n) for n in janela])
        # dúzias
        feat.extend([get_duzia(n) for n in janela])
        # pares/ímpares
        feat.extend([get_paridade(n) for n in janela])
        # cores
        feat.extend([get_cor(n) for n in janela])
        # terminal dominante
        feat.append(get_terminal_dominante(hist_list[:i+5]))
        # vizinhos físicos
        for n in janela:
            feat.extend(vizinhos_fisicos(n,2))
        # tiers
        feat.extend([get_tier(n) for n in janela])
        # offlines
        feat.extend([offline[n] for n in janela])
        # zeros (1 se zero na janela)
        feat.append(int(0 in janela))

        X.append(feat)
        y.append(alvo)
    return X,y

# =========================
# TREINAR MODELO
# =========================
def treinar_modelo_coluna(historico):
    X,y=criar_features(historico)
    if len(X)<20: return None
    modelo=RandomForestClassifier(
        n_estimators=500,
        max_depth=20,
        random_state=42,
        class_weight="balanced_subsample"
    )
    modelo.fit(X,y)
    return modelo

# =========================
# API
# =========================
def fetch_latest_result():
    try:
        r=requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        data=r.json()
        numero=data.get("result",{}).get("outcome",{}).get("number")
        return int(numero) if numero is not None else None
    except Exception as e:
        logging.error(f"Erro API: {e}")
        return None

# =========================
# STREAMLIT
# =========================
st.title("🎯 Previsão Coluna PRO — Vizinhos + Offlines + Tiers + Zeros")

st_autorefresh(interval=10000, key="refresh")

# Estado
if "historico" not in st.session_state:
    st.session_state.historico=deque(maxlen=MAX_HISTORICO)
    if HIST_PATH.exists():
        st.session_state.historico.extend(joblib.load(HIST_PATH))
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna=None
if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista=None
if "green_count" not in st.session_state:
    st.session_state.green_count=0
if "red_count" not in st.session_state:
    st.session_state.red_count=0

# Captura novo número
numero=fetch_latest_result()
if numero is not None:
    if not st.session_state.historico or numero!=st.session_state.historico[-1]:
        st.session_state.historico.append(numero)
        joblib.dump(list(st.session_state.historico),HIST_PATH)

        # Treinar modelo
        if len(st.session_state.historico)>50:
            st.session_state.modelo_coluna=treinar_modelo_coluna(st.session_state.historico)

        # Previsão
        if st.session_state.modelo_coluna and len(st.session_state.historico)>=5:
            janela=list(st.session_state.historico)[-5:]
            feat=[]
            feat.extend(janela)
            feat.extend([get_coluna(n) for n in janela])
            feat.extend([get_duzia(n) for n in janela])
            feat.extend([get_paridade(n) for n in janela])
            feat.extend([get_cor(n) for n in janela])
            feat.append(get_terminal_dominante(st.session_state.historico))
            for n in janela:
                feat.extend(vizinhos_fisicos(n,2))
            feat.extend([get_tier(n) for n in janela])
            offline=calcular_offlines(st.session_state.historico)
            feat.extend([offline[n] for n in janela])
            feat.append(int(0 in janela))
            probs=st.session_state.modelo_coluna.predict_proba([feat])[0]
            melhor_coluna=np.argmax(probs)+1

            if st.session_state.coluna_prevista!=melhor_coluna:
                enviar_previsao(melhor_coluna)
                st.session_state.coluna_prevista=melhor_coluna

        # Conferir resultado
        if st.session_state.coluna_prevista is not None:
            coluna_real=get_coluna(numero)
            acertou=coluna_real==st.session_state.coluna_prevista
            if acertou:
                st.session_state.green_count+=1
            else:
                st.session_state.red_count+=1
            enviar_resultado(numero,acertou)

# Status
st.write("📊 Histórico:", list(st.session_state.historico)[-20:])
st.write("🟢 GREENs:", st.session_state.green_count)
st.write("🔴 REDs:", st.session_state.red_count)
