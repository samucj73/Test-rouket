import streamlit as st
import requests
import joblib
from collections import Counter, deque, defaultdict
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import time
import csv
import os

# ==========================
# ======== v4.2 ===========
# ==========================

# === CONFIGURAÇÕES FIXAS ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico_v35.pkl"
CSV_LOG_PATH = "historico_feedback_v35.csv"

# === CONFIGURAÇÕES ADMIN (barra lateral) ===
st.set_page_config(layout="wide", page_title="IA Elite Master - Roleta v4.2 (Combinatória)")
st.sidebar.title("⚙️ Painel Admin - Combinatória (Elite Master)")

DECAY_HALFLIFE = st.sidebar.slider("Halflife (peso de decaimento)", 80, 5000, 400, step=10)
CANDIDATE_POOL = st.sidebar.slider("Tamanho do pool candidato (top N)", 9, 30, 20)
PENALTY_PROXIMITY = st.sidebar.slider("Penalidade por proximidade física (0-1)", 0.0, 1.0, 0.35, step=0.05)
USE_RECENT_ONLY = st.sidebar.checkbox("Usar todo o histórico salvo", value=True)
RECENT_WINDOW = st.sidebar.number_input("Janela recente (se não usar todo histórico)", 50, 10000, 500, step=50)

# ==========================
# === INICIALIZAÇÃO ===
# ==========================
st.title("🎯 Estratégia Combinatória - Roleta (v4.2)")

if os.path.exists(HISTORICO_PATH):
    hist = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(hist, maxlen=100000)
else:
    st.session_state.historico = deque(maxlen=100000)

defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": None,
    "greens": 0,
    "reds": 0,
    "alertas_enviados": set(),
    "historico_scores": deque(maxlen=500),
    "last_conferencia": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=2500, key="refresh42")

ROULETTE_ORDER = [
    0,32,15,19,4,21,2,25,17,34,6,27,13,36,
    11,30,8,23,10,5,24,16,33,1,20,14,31,9,
    22,18,29,7,28,12,35,3,26
]

def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": msg})
    except Exception:
        pass

def distancia_fisica(a,b):
    ia, ib = ROULETTE_ORDER.index(a), ROULETTE_ORDER.index(b)
    d = abs(ia-ib)
    return min(d, len(ROULETTE_ORDER)-d)

def get_vizinhos(n):
    idx = ROULETTE_ORDER.index(n)
    return [ROULETTE_ORDER[(idx+i)%len(ROULETTE_ORDER)] for i in range(-2,3)]

# === FUNÇÕES DE CÁLCULO ===
def exp_weights(n,halflife):
    if n<=0: return np.array([])
    ages = np.arange(n)[::-1]
    w = 0.5**(ages/halflife)
    return w/w.sum()

def trans_counts(hist):
    t=defaultdict(lambda:defaultdict(int))
    for i in range(len(hist)-1):
        t[hist[i]][hist[i+1]]+=1
    return t

def gerar_scores(hist):
    if not hist: return {n:1 for n in range(37)}
    janela = hist if USE_RECENT_ONLY else hist[-int(RECENT_WINDOW):]
    n=len(janela)
    w=exp_weights(n,DECAY_HALFLIFE)
    freq=defaultdict(float)
    for i,num in enumerate(janela): freq[num]+=w[i]
    mf=max(freq.values()) if freq else 1
    freq_score={n:freq.get(n,0)/mf for n in range(37)}
    trans=trans_counts(janela)
    last=janela[-1]
    denom=sum(trans[last].values()) if last in trans else 0
    cond={n:(trans[last].get(n,0)/denom if denom>0 else freq_score[n]) for n in range(37)}
    viz=set(get_vizinhos(last))
    s={}
    for n in range(37):
        s[n]=0.6*freq_score[n]+0.35*cond[n]+(0.12 if n in viz else 0)
    arr=np.array(list(s.values()))
    if arr.max()>arr.min(): arr=(arr-arr.min())/(arr.max()-arr.min())
    return {n:float(arr[i]) for i,n in enumerate(s.keys())}

def selecionar_comb(scores,k=9):
    cand=sorted(scores,key=lambda x:scores[x],reverse=True)[:CANDIDATE_POOL]
    chosen=[]
    for _ in range(k):
        best=None;bv=-1
        for c in cand:
            if c in chosen: continue
            val=scores[c]
            if chosen:
                pen=np.mean([1/(1+distancia_fisica(c,ch)) for ch in chosen])
                val-=PENALTY_PROXIMITY*pen
            if val>bv: bv=val;best=c
        if best is None:break
        chosen.append(best)
    chosen=sorted(chosen,key=lambda x:scores[x],reverse=True)
    return chosen

def gerar_combinacao(hist):
    sc=gerar_scores(hist)
    comb=selecionar_comb(sc)
    m=np.mean([sc[n] for n in comb])
    s=sum([sc[n] for n in comb])
    est=s/(sum(sc.values()) if sum(sc.values())>0 else 1)
    return {"comb":comb,"media":m,"estim":est,"scores":sc}

# ==========================
# === CAPTURA NOVO NÚMERO ===
# ==========================
novo_num=None
try:
    r=requests.get(API_URL,timeout=5)
    if r.status_code==200:
        d=r.json()
        num=int(d["data"]["result"]["outcome"]["number"])
        ts=d["data"]["settledAt"]
        if ts!=st.session_state.ultimo_timestamp:
            st.session_state.historico.append(num)
            joblib.dump(list(st.session_state.historico),HISTORICO_PATH)
            st.session_state.ultimo_timestamp=ts
            novo_num=num
            st.success(f"🎯 Novo número: {num}")
except Exception:
    pass

# ==========================
# === CONFERÊNCIA (antes da nova previsão) ===
# ==========================
if novo_num is not None and st.session_state.entrada_atual:
    ent=st.session_state.entrada_atual["comb"]
    green=novo_num in ent
    if green: st.session_state.greens+=1
    else: st.session_state.reds+=1
    emoji="🟢" if green else "🔴"
    status="GREEN" if green else "RED"
    msg=(f"{emoji} Resultado Conferido: {status}\n"
         f"Saiu {novo_num}\n"
         f"Combinação: {', '.join(map(str,ent))}")
    enviar_telegram(msg)
    st.session_state.last_conferencia={
        "green":green,"numero":novo_num,"comb":ent,
        "media":round(np.mean([st.session_state.entrada_atual['scores'][n] for n in ent]),3),
        "estim":round(st.session_state.entrada_atual['estim'],4)
    }
    st.session_state.entrada_atual=None

# ==========================
# === GERA NOVA PREVISÃO ===
# ==========================
if novo_num is not None:
    hist=list(st.session_state.historico)
    prev=gerar_combinacao(hist)
    comb=prev["comb"]
    chave=tuple(comb)
    if chave not in st.session_state.alertas_enviados:
        st.session_state.alertas_enviados.add(chave)
        msg=(f"🎯 PREVISÃO 9 NÚMEROS\n{', '.join(map(str,comb))}\n"
             f"⭐ Média scores: {prev['media']:.3f} | Estimativa: {prev['estim']:.4f}")
        enviar_telegram(msg)
        st.session_state.entrada_atual=prev
        st.session_state.historico_scores.append(prev["media"])

# ==========================
# === INTERFACE VISUAL ===
# ==========================
col1,col2,col3=st.columns(3)
tot=st.session_state.greens+st.session_state.reds
col1.metric("✅ GREENS",st.session_state.greens)
col2.metric("❌ REDS",st.session_state.reds)
col3.metric("🎯 Taxa de Acerto",f"{(st.session_state.greens/tot*100 if tot>0 else 0):.1f}%")

st.markdown("---")

if st.session_state.last_conferencia:
    lc=st.session_state.last_conferencia
    color="#d4f8dc" if lc["green"] else "#ffd6d6"
    emoji="🟢" if lc["green"] else "🔴"
    status="GREEN" if lc["green"] else "RED"
    st.markdown(f"""
    <div style="background:{color};padding:14px;border-radius:8px;">
    <h2>{emoji} Resultado conferido: <b>{status}</b></h2>
    <p><b>Saiu {lc['numero']}</b> | Combinação: {', '.join(map(str,lc['comb']))}</p>
    <p>⭐ Média scores: {lc['media']} | Estimativa: {lc['estim']}</p>
    </div>
    """,unsafe_allow_html=True)

st.markdown("---")
if st.session_state.entrada_atual:
    st.subheader("📩 Previsão atual (aguardando próximo número)")
    st.write(", ".join(map(str,st.session_state.entrada_atual["comb"])))

st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-14:])

if st.session_state.historico_scores:
    st.subheader("📈 Evolução das médias de score")
    fig,ax=plt.subplots(figsize=(8,2.5))
    ax.plot(list(st.session_state.historico_scores),marker='o')
    st.pyplot(fig)
