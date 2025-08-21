import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
HISTORICO_DUZIAS_PATH = Path("historico.pkl")          # legado (dúzias)
HISTORICO_NUMEROS_PATH = Path("historico_numeros.pkl") # números brutos
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # ms
WINDOW_SIZE = 15         # janela de análise base
TRAIN_EVERY = 10         # treinar a cada N novas entradas

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
            "padroes_certos","ultima_entrada","modelo_rf",
            "ultimo_resultado_numero"]:
    if var not in st.session_state:
        if var in ["padroes_certos","ultima_entrada"]:
            st.session_state[var]=[]
        elif var=="tipo_entrada_anterior":
            st.session_state[var]=""
        else:
            st.session_state[var]=0 if "modelo" not in var else None

# Restaura contadores/chaves do estado salvo
for k,v in estado_salvo.items(): st.session_state[k]=v

# === INTERFACE ===

st.title("🎯 IA Roleta - Padrões de Dúzia (CatBoost + Features Avançadas)")

# Últimos números capturados
st.subheader("📌 Últimos números e dúzias")
if len(st.session_state.historico_numeros) > 0:
    ult_numeros = list(st.session_state.historico_numeros)[-12:]
    ult_duzias  = [numero_para_duzia(n) for n in ult_numeros]
    tabela = { "Número": ult_numeros, "Dúzia": ult_duzias }
    st.table(tabela)

# Acertos do modelo
st.subheader("📊 Estatísticas de Acerto")
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")

# Previsão atual
st.subheader("🎯 Previsão Atual (Top 2 Dúzias)")
top = prever_duzia_rf()
if top:
    st.write(", ".join(f"{d} ({p*100:.1f}%)" for d,p in top))
else:
    st.write("Ainda sem previsão disponível.")

# Configurações interativas
tamanho_janela = st.slider("📏 Tamanho da janela de análise", 5, 150, WINDOW_SIZE)
prob_minima    = st.slider("📊 Probabilidade mínima (%)", 10, 100, 30)/100.0



# === TELEGRAM ===
def enviar_telegram_async(msg,delay=0):
    def _send():
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"}
        try: requests.post(url,json=payload,timeout=5)
        except: pass
    if delay>0: threading.Timer(delay,_send).start()
    else: threading.Thread(target=_send,daemon=True).start()

# === HISTÓRICO ===
def salvar_historico(numero:int):
    duzia = numero_para_duzia(numero)
    st.session_state.historico.append(duzia)
    st.session_state.historico_numeros.append(numero)
    joblib.dump(st.session_state.historico,HISTORICO_DUZIAS_PATH)
    joblib.dump(st.session_state.historico_numeros,HISTORICO_NUMEROS_PATH)
    return duzia

# === FEATURES ===
def freq_em_janela(valores,universo,w):
    w = max(1,min(w,len(valores)))
    sub=valores[-w:]
    c=Counter(sub)
    total=float(w)
    return [c.get(u,0)/total for u in universo]

def tempo_desde_ultimo(valores,universo):
    L=len(valores)
    rev=valores[::-1]
    out=[]
    for u in universo:
        try: idx=rev.index(u); out.append(idx/max(1,L-1))
        except: out.append(1.0)
    return out

def matriz_transicoes(valores,universo):
    m={a:{b:0 for b in universo} for a in universo}
    for a,b in zip(valores[:-1],valores[1:]):
        if a in m and b in m[a]: m[a][b]+=1
    total=sum(m[a][b] for a in universo for b in universo)
    if total==0: total=1
    return [m[a][b]/total for a in universo for b in universo]

def extrair_features(janela_duzias,janela_numeros):
    feats=[]
    L=len(janela_duzias)
    feats.extend(janela_duzias)
    contador=Counter(janela_duzias)
    for d in [1,2,3]: feats.append(contador.get(d,0)/max(1,L))
    pesos=np.array([0.9**i for i in range(L-1,-1,-1)],dtype=float)
    s_pesos=float(pesos.sum()) if pesos.size else 1.0
    for d in [1,2,3]:
        feats.append(sum(w for val,w in zip(janela_duzias,pesos) if val==d)/s_pesos)
    if L>1:
        feats.append(sum(1 for j in range(1,L) if janela_duzias[j]!=janela_duzias[j-1])/(L-1))
        den=sum(0.9**i for i in range(L-1)) or 1.0
        feats.append(sum((janela_duzias[j]!=janela_duzias[j-1])*0.9**(L-1-j) for j in range(1,L))/den)
    else: feats.extend([0.0,0.0])
    tend=[0.0,0.0,0.0]
    for val,w in zip(janela_duzias,pesos if L else []):
        if val in [1,2,3]: tend[val-1]+=float(w)
    total=sum(tend) if sum(tend)>0 else 1.0
    feats.extend([t/total for t in tend])
    feats.append((max(tend)-min(tend)) if tend else 0.0)
    feats.append(janela_duzias.count(0)/max(1,L))
    feats.extend(tempo_desde_ultimo(janela_duzias,[1,2,3]))
    k=min(5,L)
    ultk=janela_duzias[-k:] if L else []
    for d in [1,2,3]: feats.append(ultk.count(d)/max(1,k))
    for w in [12,24,36]: feats.extend(freq_em_janela(janela_duzias,[1,2,3],w))
    streak=0
    if L:
        last=janela_duzias[-1]
        for v in reversed(janela_duzias):
            if v==last: streak+=1
            else: break
    feats.append(streak/max(1,L))
    feats.extend(matriz_transicoes(janela_duzias,[1,2,3]))
    # Features números brutos
    Ln=len(janela_numeros)
    if Ln==0: feats.extend([0.0]*26); return feats
    wnum=min(12,Ln)
    ult=janela_numeros[-wnum:]
    feats.append(sum(is_even(n) for n in ult)/wnum)
    feats.append(sum(1-is_even(n) for n in ult)/wnum)
    feats.append(sum(is_red(n) for n in ult)/wnum)
    feats.append(sum(1-is_red(n) for n in ult if n!=0)/max(1,sum(1 for n in ult if n!=0)))
    feats.append(sum(is_low(n) for n in ult)/wnum)
    feats.append(sum(1-is_low(n) for n in ult if n!=0)/max(1,sum(1 for n in ult if n!=0)))
    cols=[numero_para_coluna(n) for n in ult]
    for c in [1,2,3]: feats.append(cols.count(c)/len(ult))
    last_num=janela_numeros[-1]
    viz=vizinhos_set(last_num,2)
    feats.append(sum(1 for n in ult if n in viz)/len(ult))
    feats.append(sum(1 for n in ult if n in VOISINS)/len(ult))
    feats.append(sum(1 for n in ult if n in TIERS)/len(ult))
    feats.append(sum(1 for n in ult if n in ORPH)/len(ult))
    w36=min(36,Ln)
    ult36=janela_numeros[-w36:]
    feats.append(ult36.count(0)/max(1,w36))
    if Ln>=3:
        trip=janela_numeros[-3:]
        Lwheel=len(WHEEL)
        dists=[]
        ok=True
        for a,b in zip(trip[:-1],trip[1:]):
            if a not in IDX or b not in IDX: ok=False; break
            ia,ib=IDX[a],IDX[b]
            cw=(ib-ia)%Lwheel
            ccw=(ia-ib)%Lwheel
            dists.append(min(cw,ccw)/Lwheel)
        feats.append(np.mean(dists) if (dists and ok) else 0.0)
    else: feats.append(0.0)
    last_dz=numero_para_duzia(last_num)
    for d in [1,2,3]: feats.append(1.0 if last_dz==d else 0.0)
    last_col=numero_para_coluna(last_num)
    for c in [1,2,3]: feats.append(1.0 if last_col==c else 0.0)
    k6=min(6,Ln)
    ult6=janela_numeros[-k6:]
    for d in [1,2,3]: feats.append(sum(1 for n in ult6 if numero_para_duzia(n)==d)/max(1,k6))
    return feats

# === DATASET ===
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
            X.append(extrair_features(janela_duz,janela_num))
            y.append(alvo)
    return np.array(X,dtype=float),np.array(y,dtype=int)

# === TREINAMENTO ===
def treinar_modelo_rf():
    X,y=criar_dataset_features(st.session_state.historico,st.session_state.historico_numeros,tamanho_janela)
    if len(y)>1 and len(set(y))>1 and len(X)==len(y):
        modelo=CatBoostClassifier(iterations=300,depth=6,learning_rate=0.08,loss_function='MultiClass',verbose=False)
        try:
            modelo.fit(X,y)
            st.session_state.modelo_rf=modelo
            return True
        except: return False
    return False

# === PREVISÃO ===

def prever_duzia_rf():
    duz=list(st.session_state.historico)
    nums=list(st.session_state.historico_numeros)
    if len(duz)<tamanho_janela or st.session_state.modelo_rf is None:
        return None
    janela_duz=duz[-tamanho_janela:]
    janela_num=nums[-tamanho_janela:]
    feat = np.array([extrair_features(janela_duz,janela_num)],dtype=float)
    try:
        probs=st.session_state.modelo_rf.predict_proba(feat)[0]
        preds={i+1:p for i,p in enumerate(probs)}
        # Seleciona top2 probabilidades acima do mínimo
        top2=sorted(preds.items(), key=lambda x: x[1], reverse=True)[:2]
        top2=[(d,p) for d,p in top2 if p>=prob_minima]
        return top2
    except:
        return None

# === ALERTA TELEGRAM ===
def enviar_alerta_duzia():
    top=prever_duzia_rf()
    if not top: return
    chave="_".join(str(d) for d,_ in top)
    if chave==st.session_state.ultima_chave_alerta and st.session_state.contador_sem_alerta<3:
        st.session_state.contador_sem_alerta+=1
        return
    st.session_state.ultima_chave_alerta=chave
    st.session_state.contador_sem_alerta=0
    msg="🎯 Previsão Dúzia: "+", ".join(str(d) for d,_ in top)
    enviar_telegram_async(msg)

# === CAPTURA API AO VIVO ===
def capturar_ultimo_numero():
    try:
        r=requests.get(API_URL,timeout=3)
        data=r.json()
        numero=int(data.get("result",0))
        return numero
    except: return None

# === LOOP PRINCIPAL ===
def loop_principal():
    while True:
        numero=capturar_ultimo_numero()
        if numero is None: continue
        if numero!=st.session_state.ultimo_numero_salvo:
            st.session_state.ultimo_numero_salvo=numero
            salvar_historico(numero)
            enviar_alerta_duzia()
            # salvar estado
            estado=dict(ultima_chave_alerta=st.session_state.ultima_chave_alerta,
                        contador_sem_alerta=st.session_state.contador_sem_alerta)
            try: joblib.dump(estado,ESTADO_PATH)
            except: pass
            if len(st.session_state.historico)%TRAIN_EVERY==0:
                treinar_modelo_rf()
        import time
        time.sleep(2)

# === INICIALIZAÇÃO ===
if st.session_state.modelo_rf is None:
    treinar_modelo_rf()

# === INTERFACE ATUALIZADA ===


# === AUTORELOAD STREAMLIT ===
st_autorefresh(interval=REFRESH_INTERVAL, key="autoreload")

# === THREAD DE CAPTURA AO VIVO ===
threading.Thread(target=loop_principal,daemon=True).start()
st.info("Sistema de previsão de Dúzia ativo. Alertas Telegram serão enviados automaticamente.")
