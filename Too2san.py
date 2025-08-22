import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
HISTORICO_DUZIAS_PATH = Path("historico.pkl")
HISTORICO_NUMEROS_PATH = Path("historico_numeros.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # ms
WINDOW_SIZE = 15
TRAIN_EVERY = 10

# === MAPAS AUXILIARES (roda europeia) ===
RED_SET = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
IDX = {n:i for i,n in enumerate(WHEEL)}
VOISINS = {22,18,29,7,28,12,35,3,26,0,32,15,19,4,21,2,25}
TIERS   = {27,13,36,11,30,8,23,10,5,24,16,33}
ORPH    = {1,20,14,31,9,17,34,6}

def numero_para_duzia(num:int)->int:
    if num==0: return 0
    if 1<=num<=12: return 1
    if 13<=num<=24: return 2
    return 3

def numero_para_coluna(num:int)->int:
    if num==0: return 0
    r = num%3
    return 3 if r==0 else r

def is_red(num:int)->int:
    return 1 if num in RED_SET else 0 if num!=0 else 0

def is_even(num:int)->int:
    return 1 if (num!=0 and num%2==0) else 0

def is_low(num:int)->int:
    return 1 if (1<=num<=18) else 0

def vizinhos_set(num:int,k:int=2)->set:
    if num not in IDX: return set()
    i = IDX[num]
    L = len(WHEEL)
    indices = [(i+j)%L for j in range(-k,k+1)]
    return {WHEEL[idx] for idx in indices}

# === CARREGA ESTADO ===
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except:
    try: ESTADO_PATH.unlink()
    except: pass
    estado_salvo = {}

# === SESSION STATE ===
if "ultimo_numero_salvo" not in st.session_state: st.session_state.ultimo_numero_salvo=None
if "ultima_chave_alerta" not in st.session_state: st.session_state.ultima_chave_alerta=None
if "historico" not in st.session_state:
    if HISTORICO_DUZIAS_PATH.exists():
        st.session_state.historico=joblib.load(HISTORICO_DUZIAS_PATH)
        if not isinstance(st.session_state.historico,deque):
            st.session_state.historico=deque(st.session_state.historico,maxlen=MAX_HIST_LEN)
    else:
        st.session_state.historico=deque(maxlen=MAX_HIST_LEN)
if "historico_numeros" not in st.session_state:
    if HISTORICO_NUMEROS_PATH.exists():
        hist_num=joblib.load(HISTORICO_NUMEROS_PATH)
        st.session_state.historico_numeros=deque(hist_num,maxlen=MAX_HIST_LEN)
    else:
        st.session_state.historico_numeros=deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top","total_top","contador_sem_alerta","tipo_entrada_anterior",
            "padroes_certos","ultima_entrada","modelo_rf","ultimo_resultado_numero"]:
    if var not in st.session_state:
        if var in ["padroes_certos","ultima_entrada"]:
            st.session_state[var]=[]
        elif var=="tipo_entrada_anterior":
            st.session_state[var]=""
        else:
            st.session_state[var]=0 if "modelo" not in var else None

# Restaura contadores/chaves do estado salvo
for k,v in estado_salvo.items(): st.session_state[k]=v

# === FUNÇÕES ===
def salvar_historico(numero:int):
    duzia = numero_para_duzia(numero)
    st.session_state.historico.append(duzia)
    st.session_state.historico_numeros.append(numero)
    joblib.dump(st.session_state.historico,HISTORICO_DUZIAS_PATH)
    joblib.dump(st.session_state.historico_numeros,HISTORICO_NUMEROS_PATH)
    return duzia

def capturar_ultimo_numero():
    try:
        r=requests.get(API_URL,timeout=3)
        data=r.json()
        numero=int(data.get("result",0))
        return numero
    except: return None

def criar_dataset_features(hist_duzias,hist_numeros,janela_size):
    X,y=[],[]
    duz=list(hist_duzias)
    nums=list(hist_numeros)
    L=min(len(duz),len(nums))
    if L<=janela_size: return np.array(X),np.array(y)
    duz=duz[-L:]
    nums=nums[-L:]
    for i in range(L-janela_size):
        janela_duz=duz[i:i+janela_size]
        janela_num=nums[i:i+janela_size]
        alvo=duz[i+janela_size]
        if alvo in [1,2,3]:
            feats = extrair_features(janela_duz,janela_num)
            X.append(feats)
            y.append(alvo)
    return np.array(X,dtype=float),np.array(y,dtype=int)

def treinar_modelo_rf():
    X,y = criar_dataset_features(st.session_state.historico,st.session_state.historico_numeros,tamanho_janela)
    if len(y)>1 and len(set(y))>1 and len(X)==len(y):
        modelo = CatBoostClassifier(iterations=300,depth=6,learning_rate=0.08,loss_function='MultiClass',verbose=False)
        try:
            modelo.fit(X,y)
            st.session_state.modelo_rf = modelo
            return True
        except: return False
    return False

def prever_duzia_rf():
    duz=list(st.session_state.historico)
    nums=list(st.session_state.historico_numeros)
    if len(duz)<tamanho_janela or st.session_state.modelo_rf is None:
        return None
    janela_duz = duz[-tamanho_janela:]
    janela_num = nums[-tamanho_janela:]
    feat = np.array([extrair_features(janela_duz,janela_num)],dtype=float)
    try:
        probs = st.session_state.modelo_rf.predict_proba(feat)[0]
        preds = {i+1:p for i,p in enumerate(probs)}
        top2 = sorted(preds.items(), key=lambda x:x[1], reverse=True)[:2]
        top2 = [(d,p) for d,p in top2 if p>=prob_minima]
        return top2
    except:
        return None

def enviar_alerta_duzia():
    top = prever_duzia_rf()
    if not top: return
    chave = "_".join(str(d) for d,_ in top)
    if chave==st.session_state.ultima_chave_alerta and st.session_state.contador_sem_alerta<3:
        st.session_state.contador_sem_alerta +=1
        return
    st.session_state.ultima_chave_alerta = chave
    st.session_state.contador_sem_alerta = 0
    msg = "🎯 Previsão Dúzia: " + ", ".join(str(d) for d,_ in top)
    try:
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"}
        requests.post(url,json=payload,timeout=5)
    except: pass

# === INTERFACE ===
st.title("🎯 IA Roleta Profissional - Dúzia")

# Botão manual para atualizar números
if st.button("🔄 Capturar último número da API"):
    numero = capturar_ultimo_numero()
    if numero is not None and numero != st.session_state.ultimo_numero_salvo:
        st.session_state.ultimo_numero_salvo = numero
        salvar_historico(numero)
        enviar_alerta_duzia()
        if len(st.session_state.historico)%TRAIN_EVERY==0:
            treinar_modelo_rf()

# Mostra últimos números
st.subheader("📌 Últimos números")
ult_numeros = list(st.session_state.historico_numeros)[-12:]
st.write(ult_numeros)

# Previsão atual
st.subheader("🎯 Previsão Atual (Top 2 Dúzias)")
top = prever_duzia_rf()
if top:
    st.write(", ".join(f"{d} ({p*100:.1f}%)" for d,p in top))
else:
    st.write("Ainda sem previsão disponível.")

# Estatísticas
st.subheader("📊 Estatísticas de Acerto")
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")

# Autorefresh
st_autorefresh(interval=REFRESH_INTERVAL, key="autoreload")
