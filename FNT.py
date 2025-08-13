import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import SGDClassifier
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import threading
import warnings

warnings.filterwarnings("ignore")

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
REFRESH_INTERVAL = 10000
MAX_HIST_LEN = 800
RETRAIN_EVERY = 10
PROB_MIN_BASE = 0.80
JANELA_METRICAS = 30

ROULETTE_ORDER = [32,15,19,4,21,2,25,17,34,6,27,13,36,11,
                  30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,
                  29,7,28,12,35,3,26,0]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

defaults = {
    "acertos_top":0,"total_top":0,
    "top2_anterior":[],"contador_sem_alerta":0,"tipo_entrada_anterior":"",
    "modelo_d":None,"modelo_c":None,"sgd_d":None,"sgd_c":None,
    "rounds_desde_retrain":0,
    "metricas_janela":deque(maxlen=JANELA_METRICAS),
    "hit_rate_por_tipo":{"duzia":deque(maxlen=JANELA_METRICAS),"coluna":deque(maxlen=JANELA_METRICAS)},
    "cv_scores":{"duzia":{"lgb":0.5,"rf":0.5},"coluna":{"lgb":0.5,"rf":0.5}},
    "prob_minima_dinamica":PROB_MIN_BASE,
    "estado":{}
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=v
if ESTADO_PATH.exists():
    st.session_state.estado.update(joblib.load(ESTADO_PATH))

# === FUNÇÕES ===
def enviar_telegram_async(mensagem):
    def _send():
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload={"chat_id":TELEGRAM_CHAT_ID,"text":mensagem,"parse_mode":"HTML"}
        try: requests.post(url,json=payload,timeout=5)
        except: pass
    threading.Thread(target=_send,daemon=True).start()

def cor(numero):
    if numero==0: return 'G'
    return 'R' if numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

def distancia_fisica(n1,n2):
    if n1 not in ROULETTE_ORDER or n2 not in ROULETTE_ORDER: return 0
    idx1,idx2=ROULETTE_ORDER.index(n1),ROULETTE_ORDER.index(n2)
    diff=abs(idx1-idx2)
    return min(diff,len(ROULETTE_ORDER)-diff)

def get_neighbors(number,k=2):
    if number not in ROULETTE_ORDER: return []
    idx=ROULETTE_ORDER.index(number);n=len(ROULETTE_ORDER)
    return [ROULETTE_ORDER[(idx-i)%n] for i in range(1,k+1)]+[ROULETTE_ORDER[(idx+i)%n] for i in range(1,k+1)]

def frequencia_numeros_quentes(janela,top_n=5):
    c=Counter(janela)
    mais_comuns=c.most_common(top_n)
    freq=np.zeros(top_n); numeros=np.zeros(top_n)
    total=len(janela) if len(janela)>0 else 1
    for i,(num,cnt) in enumerate(mais_comuns):
        freq[i]=cnt/total
        numeros[i]=num
    return numeros,freq

def blocos_fisicos(numero):
    if numero not in ROULETTE_ORDER: return 0
    idx=ROULETTE_ORDER.index(numero)
    if idx<12: return 1
    elif idx<24: return 2
    else: return 3

def tendencia_pares_impares(janela):
    total=len(janela) if len(janela)>0 else 1
    pares=sum(1 for n in janela if n!=0 and n%2==0)
    impares=sum(1 for n in janela if n!=0 and n%2!=0)
    return pares/total,impares/total

def repeticoes_ultimos_n(janela,n=5):
    if len(janela)<n+1: return 0
    ultimo=janela[-1]
    return janela[-(n+1):-1].count(ultimo)

def freq_duzia_coluna_ultimos(janela,k=10):
    sub=list(janela[-k:]) if len(janela)>=1 else []
    if not sub: return [0,0,0],[0,0,0]
    duzias=[((n-1)//12+1) if n!=0 else 0 for n in sub]
    colunas=[((n-1)%3+1) if n!=0 else 0 for n in sub]
    fd=[duzias.count(1)/len(sub),duzias.count(2)/len(sub),duzias.count(3)/len(sub)]
    fc=[colunas.count(1)/len(sub),colunas.count(2)/len(sub),colunas.count(3)/len(sub)]
    return fd,fc

def extrair_features(historico):
    historico=list(historico)
    X,y=[],[]
    historico_sem_ultimo=historico[:-1]
    for i in range(120,len(historico_sem_ultimo)):
        janela=historico_sem_ultimo[i-120:i]
        ult=historico_sem_ultimo[i-1]
        cores=[cor(n) for n in janela]
        vermelhos=cores.count('R');pretos=cores.count('B');verdes=cores.count('G')
        pares=sum(1 for n in janela if n!=0 and n%2==0)
        impares=sum(1 for n in janela if n!=0 and n%2!=0)
        duzia=(ult-1)//12+1 if ult!=0 else 0
        coluna=(ult-1)%3+1 if ult!=0 else 0
        tempo_zero=next((idx for idx,val in enumerate(reversed(janela),1) if val==0),len(janela))
        dist_fisica=float(np.mean([distancia_fisica(ult,n) for n in janela[-3:]])) if len(janela)>=3 else 0.0
        numeros_quentes,freq_quentes=frequencia_numeros_quentes(janela,top_n=5)
        blocos=blocos_fisicos(ult)
        pares_prop,impares_prop=tendencia_pares_impares(janela)
        repeticoes=repeticoes_ultimos_n(janela,n=5)
        fd,fc=freq_duzia_coluna_ultimos(janela,k=10)
        viz=get_neighbors(ult,k=2)
        viz_cores=[cor(n) for n in viz]
        viz_r=viz_cores.count('R');viz_b=viz_cores.count('B');viz_g=viz_cores.count('G')
        features=[vermelhos,pretos,verdes,pares,impares,duzia,coluna,
                  tempo_zero,dist_fisica,*freq_quentes,blocos,pares_prop,impares_prop,
                  repeticoes,*fd,*fc,viz_r,viz_b,viz_g]
        X.append(features);y.append(historico_sem_ultimo[i])
    return np.array(X),np.array(y)

# === STREAMLIT INTERFACE ===
st.title("🎯 IA Roleta PRO — Ensemble Dinâmico + SGD Online + Top2 Alertas")
st_autorefresh(interval=REFRESH_INTERVAL,key="atualizacao")

try:
    resposta=requests.get(API_URL,timeout=5).json()
    numero_atual=int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

novo_num=(len(st.session_state.historico)==0 or numero_atual!=st.session_state.historico[-1])
if novo_num:
    st.session_state.historico.append(numero_atual)
    joblib.dump(st.session_state.historico,HISTORICO_PATH)

    # Conferir acerto anterior
    if st.session_state.top2_anterior:
        st.session_state.total_top+=1
        tipo=st.session_state.tipo_entrada_anterior or "duzia"
        valor=(numero_atual-1)//12+1 if tipo=="duzia" else (numero_atual-1)%3+1
        hit=valor in st.session_state.top2_anterior
        if hit: enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {tipo}): 🟢")
        else: enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {tipo}): 🔴")
        st.session_state.acertos_top+=int(hit)
        st.session_state.metricas_janela.append({"tipo":tipo,"hit":int(hit)})

st.write("Último número:",numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top}/{st.session_state.total_top}")
st.write("Últimos números:",list(st.session_state.historico)[-12:])

# Salvar estado
joblib.dump(st.session_state.estado,ESTADO_PATH)
