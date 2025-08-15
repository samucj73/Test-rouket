import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import threading
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
REFRESH_INTERVAL = 5000
MAX_HIST_LEN = 4800
RETRAIN_EVERY = 25
PROB_MIN_BASE = 0.80
PROB_MIN_MAX = 0.90
PROB_MIN_MIN = 0.65
JANELA_METRICAS = 130
ROULETTE_ORDER = [32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,
                  24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26,0]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

defaults = {
    "acertos_top":0, "total_top":0,
    "top2_anterior":[], "contador_sem_alerta":0, "tipo_entrada_anterior":"",
    "contador_mesmo_tipo":0,
    "modelo_d":None, "modelo_c":None,
    "sgd_d":None, "sgd_c":None,
    "rounds_desde_retrain":0,
    "metricas_janela":deque(maxlen=JANELA_METRICAS),
    "hit_rate_por_tipo":{"duzia":deque(maxlen=JANELA_METRICAS),
                         "coluna":deque(maxlen=JANELA_METRICAS)},
    "cv_scores":{"duzia":{"lgb":0.5,"rf":0.5}, "coluna":{"lgb":0.5,"rf":0.5}},
    "prob_minima_dinamica":PROB_MIN_BASE,
    "last_soma_prob":0.0
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k]=v

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k,v in estado_salvo.items():
        if k in ["metricas_janela","hit_rate_por_tipo"]:
            if k=="metricas_janela": st.session_state[k]=deque(v,maxlen=JANELA_METRICAS)
            else: st.session_state[k]={tipo:deque(lst,maxlen=JANELA_METRICAS) for tipo,lst in v.items()}
        else:
            st.session_state[k]=v

# === FUNÇÕES ===
def enviar_telegram_async(msg):
    def _send():
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                          json={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"},timeout=5)
        except: pass
    threading.Thread(target=_send,daemon=True).start()

def cor(n): return 'G' if n==0 else 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'
def distancia_fisica(n1,n2):
    if n1 not in ROULETTE_ORDER or n2 not in ROULETTE_ORDER: return 0
    idx1,idx2=ROULETTE_ORDER.index(n1),ROULETTE_ORDER.index(n2)
    d=abs(idx1-idx2)
    return min(d,len(ROULETTE_ORDER)-d)
def get_neighbors(n,k=2):
    if n not in ROULETTE_ORDER: return []
    idx,n_len=ROULETTE_ORDER.index(n),len(ROULETTE_ORDER)
    return [ROULETTE_ORDER[(idx-i)%n_len] for i in range(1,k+1)] + [ROULETTE_ORDER[(idx+i)%n_len] for i in range(1,k+1)]
def frequencia_numeros_quentes(janela,top_n=5):
    c=Counter(janela)
    mais_comuns=c.most_common(top_n)
    numeros=np.zeros(top_n); freq=np.zeros(top_n)
    total=len(janela) if janela else 1
    for i,(num,cnt) in enumerate(mais_comuns):
        numeros[i]=num; freq[i]=cnt/total
    return numeros,freq
def blocos_fisicos(n):
    if n not in ROULETTE_ORDER: return 0
    idx=ROULETTE_ORDER.index(n)
    return 1 if idx<12 else 2 if idx<24 else 3
def tendencia_pares_impares(janela):
    total=len(janela) if janela else 1
    pares=sum(1 for n in janela if n!=0 and n%2==0)
    impares=sum(1 for n in janela if n!=0 and n%2!=0)
    return pares/total,impares/total
def repeticoes_ultimos_n(janela, n=5):
    if len(janela) < n + 1:
        return 0
    ultimo = janela[-1]
    return janela[-(n + 1):-1].count(ultimo)
def freq_duzia_coluna_ultimos(janela,k=10):
    sub=list(janela[-k:]) if len(janela)>=1 else []
    if not sub: return [0,0,0],[0,0,0]
    duzias=[((n-1)//12+1) if n!=0 else 0 for n in sub]
    colunas=[((n-1)%3+1) if n!=0 else 0 for n in sub]
    fd=[duzias.count(1)/len(sub),duzias.count(2)/len(sub),duzias.count(3)/len(sub)]
    fc=[colunas.count(1)/len(sub),colunas.count(2)/len(sub),colunas.count(3)/len(sub)]
    return fd,fc

def extrair_features(historico):
    if len(historico) < 121:
        return np.zeros((0, 25)), np.zeros(0)
    janela = list(historico)[-121:-1]
    ult = historico[-2]
    cores = [cor(n) for n in janela]
    vermelhos = cores.count('R')
    pretos = cores.count('B')
    verdes = cores.count('G')
    pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
    impares = sum(1 for n in janela if n != 0 and n % 2 != 0)
    duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
    coluna = (ult - 1) % 3 + 1 if ult != 0 else 0
    tempo_zero = next((idx for idx, val in enumerate(reversed(janela), 1) if val == 0), len(janela))
    dist_fisica = float(np.mean([distancia_fisica(ult, n) for n in janela[-3:]])) if len(janela) >= 3 else 0.0
    numeros_quentes, freq_quentes = frequencia_numeros_quentes(janela, top_n=5)
    blocos = blocos_fisicos(ult)
    pares_prop, impares_prop = tendencia_pares_impares(janela)
    repeticoes = repeticoes_ultimos_n(janela, n=5)
    fd, fc = freq_duzia_coluna_ultimos(janela, k=10)
    viz = get_neighbors(ult, 2)
    viz_cores = [cor(n) for n in viz]
    viz_r, viz_b, viz_g = viz_cores.count('R'), viz_cores.count('B'), viz_cores.count('G')
    features = [
        vermelhos, pretos, verdes,
        pares, impares,
        duzia, coluna,
        tempo_zero,
        dist_fisica,
        *freq_quentes,
        blocos,
        pares_prop, impares_prop,
        repeticoes,
        *fd, *fc,
        viz_r, viz_b, viz_g
    ]
    return np.array(features).reshape(1, -1), np.array([historico[-1]])

def ajustar_target(y_raw,tipo):
    if tipo=="duzia": return np.array([(n-1)//12+1 if n!=0 else 0 for n in y_raw])
    elif tipo=="coluna": return np.array([(n-1)%3+1 if n!=0 else 0 for n in y_raw])
    else: return y_raw

def treinar_modelos_batch(historico,tipo="duzia"):
    if len(historico)<130: return None,None,None,None
    X,_=extrair_features(historico)
    y=ajustar_target(list(historico)[-len(X):],tipo)
    lgb=LGBMClassifier(n_estimators=350,learning_rate=0.035,max_depth=7,
                       random_state=42,subsample=0.9,colsample_bytree=0.85)
    rf=RandomForestClassifier(n_estimators=220,max_depth=12,min_samples_split=5,
                              random_state=42,n_jobs=-1)
    cv=StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
    try:
        lgb_acc=cross_val_score(lgb,X,y,cv=cv,scoring="accuracy")
        rf_acc=cross_val_score(rf,X,y,cv=cv,scoring="accuracy")
        lgb.fit(X,y); rf.fit(X,y)
    except: return None,None,None,None
    return (lgb,rf), X, y, (lgb_acc.mean(),rf_acc.mean())

def preparar_sgd_existente(modelo_sgd,classes): 
    if modelo_sgd is None: return SGDClassifier(loss="log_loss",alpha=1e-4,random_state=42),False
    return modelo_sgd,True

def atualizar_sgd(modelo_sgd,historico,tipo="duzia"):
    if len(historico)<131: return modelo_sgd
    X,y=extrair_features(historico)
    y=ajustar_target(y,tipo)
    if X.size==0: return modelo_sgd
    x_last=X[-1].reshape(1,-1); y_last=np.array([y[-1]])
    modelo_sgd,exists=preparar_sgd_existente(modelo_sgd,np.unique(y))
    classes_tipo=np.array([0,1,2,3]) if tipo=="duzia" else np.array([1,2,3])
    try:
        if not exists: modelo_sgd.partial_fit(x_last,y_last,classes=classes_tipo)
        else: modelo_sgd.partial_fit(x_last,y_last)
    except: pass
    return modelo_sgd

def prever_top2_ensemble(modelos_tuple,sgd_model,historico):
    if (modelos_tuple is None and sgd_model is None) or len(historico)<130: return [],[],0.0
    x,_=extrair_features(historico)
    if x.size==0: return [],[],0.0
    probs_list=[]; classes_ref=None
    if modelos_tuple is not None:
        lgb_model,rf_model=modelos_tuple
        classes_ref=lgb_model.classes_
        try: probs_list.append(("lgb",lgb_model.predict_proba(x)[0])); probs_list.append(("rf",rf_model.predict_proba(x)[0]))
        except: pass
    if sgd_model is not None:
        try: p_sgd=sgd_model.predict_proba(x)[0]; classes_ref=classes_ref or sgd_model.classes_; probs_list.append(("sgd",p_sgd))
        except: pass
    return probs_list,classes_ref

def combinar_com_pesos(probs_list,pesos_dict,classes):
    if not probs_list or classes is None: return [],[],0.0
    soma=np.zeros(len(classes)); total_peso=0.0
    for nome,p in probs_list:
        w=pesos_dict.get(nome,0.0)
        if p is None or w<=0: continue
        p_full=np.zeros(len(classes)); p_full[:len(p)]=p
        soma+=p_full*w; total_peso+=w
    if total_peso<=0: total_peso=1.0
    probs=soma/total_peso
    idxs=np.argsort(probs)[::-1][:2]
    top_labels=[int(classes[i]) for i in idxs]
    top_probs=[float(probs[i]) for i in idxs]
    return top_labels,top_probs,sum(top_probs)

def atualizar_prob_minima_dinamica():
    janela=list(st.session_state.metricas_janela)
    if not janela: st.session_state.prob_minima_dinamica=PROB_MIN_BASE; return
    confs=[m["soma_prob"] for m in janela]; hits=[m["hit"] for m in janela]
    avg_conf=np.mean(confs) if confs else PROB_MIN_BASE; hit_rate=np.mean(hits) if hits else 0.5
    alvo=PROB_MIN_BASE + (hit_rate-0.5)*0.3
    st.session_state.prob_minima_dinamica=max(min(alvo,PROB_MIN_MAX),PROB_MIN_MIN)

def registrar_resultado(tipo, soma_prob, hit):
    if tipo not in ["duzia","coluna"]: tipo="duzia"
    if soma_prob is None: soma_prob=0.0
    if "metricas_janela" not in st.session_state:
        st.session_state.metricas_janela=deque(maxlen=JANELA_METRICAS)
    if "hit_rate_por_tipo" not in st.session_state:
        st.session_state.hit_rate_por_tipo={"duzia":deque(maxlen=JANELA_METRICAS),"coluna":deque(maxlen=JANELA_METRICAS)}
    st.session_state.metricas_janela.append({"tipo":tipo,"soma_prob":soma_prob,"hit":1 if hit else 0})
    st.session_state.hit_rate_por_tipo[tipo].append(1 if hit else 0)
    atualizar_prob_minima_dinamica()

# === INTERFACE / PIPELINE ===

  # === INTERFACE / PIPELINE ===
st.title("🎯 IA Roleta PRO — Dúzia + Coluna")

st_autorefresh(interval=REFRESH_INTERVAL,key="atualizacao")

try:
    numero_atual=int(requests.get(API_URL,timeout=5).json()["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# --- Atualização de rodada ---
novo_num = numero_atual != st.session_state.ultimo_numero_api
if novo_num:
    st.session_state.ultimo_numero_api = numero_atual
    st.session_state.historico.append(numero_atual)
    joblib.dump(st.session_state.historico,HISTORICO_PATH)

    # Conferir acerto da rodada anterior
    if st.session_state.top2_anterior:
        st.session_state.total_top+=1
        valor_duzia = (numero_atual-1)//12+1
        valor_coluna = (numero_atual-1)%3+1
        hit = (valor_duzia==st.session_state.top2_anterior[0]) and (valor_coluna==st.session_state.top2_anterior[1])
        st.session_state.acertos_top+=hit
        enviar_telegram_async(f"✅ Saiu {numero_atual} (Dúzia {valor_duzia}, Coluna {valor_coluna}): {'🟢' if hit else '🔴'}")

    # Atualizar SGD
    st.session_state.sgd_d = atualizar_sgd(st.session_state.sgd_d, st.session_state.historico, "duzia")
    st.session_state.sgd_c = atualizar_sgd(st.session_state.sgd_c, st.session_state.historico, "coluna")
    st.session_state.rounds_desde_retrain += 1

    # Re-treino batch
    if (st.session_state.rounds_desde_retrain >= RETRAIN_EVERY or
        st.session_state.modelo_d is None or st.session_state.modelo_c is None):
        modelos_d, Xd, yd, scores_d = treinar_modelos_batch(st.session_state.historico, "duzia")
        modelos_c, Xc, yc, scores_c = treinar_modelos_batch(st.session_state.historico, "coluna")
        if modelos_d: st.session_state.modelo_d = modelos_d
        if modelos_c: st.session_state.modelo_c = modelos_c
        if scores_d:
            st.session_state.cv_scores["duzia"]["lgb"] = scores_d[0]
            st.session_state.cv_scores["duzia"]["rf"] = scores_d[1]
        if scores_c:
            st.session_state.cv_scores["coluna"]["lgb"] = scores_c[0]
            st.session_state.cv_scores["coluna"]["rf"] = scores_c[1]
        st.session_state.rounds_desde_retrain = 0

    # --- PREVISÃO DÚZIA + COLUNA ---
    pesos_d = {"lgb": st.session_state.cv_scores["duzia"]["lgb"],
               "rf": st.session_state.cv_scores["duzia"]["rf"],
               "sgd": 0.3}
    pesos_c = {"lgb": st.session_state.cv_scores["coluna"]["lgb"],
               "rf": st.session_state.cv_scores["coluna"]["rf"],
               "sgd": 0.3}

    probs_d, classes_d = prever_top2_ensemble(st.session_state.modelo_d, st.session_state.sgd_d, st.session_state.historico)
    probs_c, classes_c = prever_top2_ensemble(st.session_state.modelo_c, st.session_state.sgd_c, st.session_state.historico)

    top_d, probs_d_vals, soma_prob_d = combinar_com_pesos(probs_d, pesos_d, classes_d)
    top_c, probs_c_vals, soma_prob_c = combinar_com_pesos(probs_c, pesos_c, classes_c)

    # Garantir previsão de uma dúzia e uma coluna
    top2 = [top_d[0] if top_d else 0, top_c[0] if top_c else 0]
    soma_prob = soma_prob_d + soma_prob_c

    enviar_alerta = False
    if top2 != st.session_state.top2_anterior:
        enviar_alerta = True
        st.session_state.contador_sem_alerta = 0
    else:
        st.session_state.contador_sem_alerta += 1
        if st.session_state.contador_sem_alerta >= 3:
            enviar_alerta = True
            st.session_state.contador_sem_alerta = 0

    if enviar_alerta:
        st.session_state.top2_anterior = top2
        st.session_state.tipo_entrada_anterior = "duzia+coluna"
        st.session_state.last_soma_prob = soma_prob
        enviar_telegram_async(f"🎯 Previsão Dúzia+Coluna: Dúzia {top2[0]}, Coluna {top2[1]} | Probabilidade {soma_prob:.2f}")

    # Salvar estado
    estado = {k: st.session_state[k] for k in ["top2_anterior", "tipo_entrada_anterior",
                                               "contador_sem_alerta", "modelo_d", "modelo_c",
                                               "sgd_d", "sgd_c", "rounds_desde_retrain",
                                               "metricas_janela", "hit_rate_por_tipo",
                                               "cv_scores", "last_soma_prob", "prob_minima_dinamica"]}
    joblib.dump(estado, ESTADO_PATH)


    
    

    # --- PREVISÃO DÚZIA + COLUNA ---
   # --- PREVISÃO DÚZIA + COLUNA ---
pesos_d = {
    "lgb": st.session_state.cv_scores["duzia"]["lgb"],
    "rf": st.session_state.cv_scores["duzia"]["rf"],
    "sgd": 0.3
}
pesos_c = {
    "lgb": st.session_state.cv_scores["coluna"]["lgb"],
    "rf": st.session_state.cv_scores["coluna"]["rf"],
    "sgd": 0.3
}

probs_d, classes_d = prever_top2_ensemble(st.session_state.modelo_d, st.session_state.sgd_d, st.session_state.historico)
probs_c, classes_c = prever_top2_ensemble(st.session_state.modelo_c, st.session_state.sgd_c, st.session_state.historico)

top_d, probs_d_vals, soma_prob_d = combinar_com_pesos(probs_d, pesos_d, classes_d)
top_c, probs_c_vals, soma_prob_c = combinar_com_pesos(probs_c, pesos_c, classes_c)

# Garantir previsão de uma dúzia e uma coluna
top2 = [top_d[0] if top_d else 0, top_c[0] if top_c else 0]
soma_prob = soma_prob_d + soma_prob_c

enviar_alerta = False
if top2 != st.session_state.top2_anterior:
    enviar_alerta = True
    st.session_state.contador_sem_alerta = 0
else:
    st.session_state.contador_sem_alerta += 1
    if st.session_state.contador_sem_alerta >= 3:
        enviar_alerta = True
        st.session_state.contador_sem_alerta = 0

if enviar_alerta:
    st.session_state.top2_anterior = top2
    st.session_state.tipo_entrada_anterior = "duzia+coluna"
    st.session_state.last_soma_prob = soma_prob
    enviar_telegram_async(f"🎯 Previsão Dúzia+Coluna: Dúzia {top2[0]}, Coluna {top2[1]} | Probabilidade {soma_prob:.2f}")

# Salvar estado
estado = {k: st.session_state[k] for k in ["top2_anterior","tipo_entrada_anterior",
                                           "contador_sem_alerta","modelo_d","modelo_c",
                                           "sgd_d","sgd_c","rounds_desde_retrain",
                                           "metricas_janela","hit_rate_por_tipo",
                                           "cv_scores","last_soma_prob","prob_minima_dinamica"]}
joblib.dump(estado, ESTADO_PATH)

# === DASHBOARD METRICS ===
st.subheader("📊 Métricas Recentes")
st.write(f"Top2 Acertos: {st.session_state.acertos_top}/{st.session_state.total_top} ({(st.session_state.acertos_top/st.session_state.total_top*100 if st.session_state.total_top>0 else 0):.2f}%)")
hit_rate_duzia = np.mean(st.session_state.hit_rate_por_tipo["duzia"]) if st.session_state.hit_rate_por_tipo["duzia"] else 0
hit_rate_coluna = np.mean(st.session_state.hit_rate_por_tipo["coluna"]) if st.session_state.hit_rate_por_tipo["coluna"] else 0
st.write(f"Hit rate Janela (Dúzia): {hit_rate_duzia:.2f} | (Coluna): {hit_rate_coluna:.2f}")
st.write(f"Prob. mínima dinâmica atual: {st.session_state.prob_minima_dinamica:.2f}")

# Plot histórico de acertos
fig, ax = plt.subplots()
janela_hits = [m["hit"] for m in st.session_state.metricas_janela]
ax.plot(janela_hits, marker='o', linestyle='-', color='green')
ax.set_title("Histórico de Hits Recentes (1=acerto, 0=erro)")
st.pyplot(fig) 
