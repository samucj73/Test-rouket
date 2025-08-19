import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

HIST_NUM_PATH = Path("historico_numeros.pkl")
ESTADO_PATH = Path("estado.pkl")

MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # ms
WINDOW_SIZE_DEFAULT = 16

# =========================
# CARREGAR ESTADO / SESSION
# =========================
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try: ESTADO_PATH.unlink()
    except Exception: pass
    estado_salvo = {}

if "historico_numeros" not in st.session_state:
    st.session_state.historico_numeros = joblib.load(HIST_NUM_PATH) if HIST_NUM_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

defaults = {
    "ultimo_numero_salvo": None,
    "ultimo_resultado_numero": None,
    "acertos_top": 0,
    "total_top": 0,
    "contador_sem_alerta": 0,
    "ultima_entrada": [],
    "tipo_entrada_anterior": "",
    "ultima_chave_alerta": None,
    "ultima_chave_resultado": None,
    "modelo_cat_duzia": None,
    "modelo_cat_coluna": None,
}

for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v

for k,v in estado_salvo.items():
    st.session_state[k] = v

# =========================
# INTERFACE
# =========================
st.title("🎯 IA Roleta — Auto (2 Dúzias OU 2 Colunas) com CatBoost + Features Avançadas")
tamanho_janela = st.slider("📏 Tamanho da janela (features)", 20, 150, value=WINDOW_SIZE_DEFAULT, step=2)
prob_minima = st.slider("📊 Probabilidade mínima para alertar (%)", 0, 100, value=0) / 100.0
st.caption("Obs.: O app escolherá automaticamente entre Dúzias ou Colunas com base na maior **soma das 2 probabilidades**.")

# =========================
# FUNÇÕES BASE
# =========================
def enviar_telegram_async(mensagem, delay=0):
    def _send():
        if delay>0: import time; time.sleep(delay)
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload={"chat_id":TELEGRAM_CHAT_ID,"text":mensagem,"parse_mode":"HTML"}
        try: requests.post(url,json=payload,timeout=5)
        except Exception as e: print("Erro Telegram:",e)
    threading.Thread(target=_send,daemon=True).start()

def numero_para_duzia(n:int)->int:
    if n==0: return 0
    if 1<=n<=12: return 1
    if 13<=n<=24: return 2
    return 3

def numero_para_coluna(n:int)->int:
    if n==0: return 0
    r = n%3
    if r==1: return 1
    if r==2: return 2
    return 3

def salvar_numero(numero:int):
    st.session_state.historico_numeros.append(numero)
    joblib.dump(st.session_state.historico_numeros,HIST_NUM_PATH)

# =========================
# FEATURES
# =========================
def criar_features_de_seq(seq_labels, window_size):
    if len(seq_labels)<window_size+5: return None,None
    X,y=[],[]
    S=list(seq_labels)
    for i in range(len(S)-window_size):
        janela=S[i:i+window_size]
        alvo=S[i+window_size]
        feats=[]
        feats.extend(janela)
        contador=Counter(janela)
        for d in [1,2,3]: feats.append(contador.get(d,0)/window_size)
        pesos=np.array([0.9**k for k in range(window_size-1,-1,-1)])
        pesos_sum=pesos.sum()
        for d in [1,2,3]: feats.append(sum(w for val,w in zip(janela,pesos) if val==d)/pesos_sum)
        ult=janela[-20:] if window_size>=20 else janela
        pesos20=np.array([0.9**k for k in range(len(ult)-1,-1,-1)])
        s20=pesos20.sum() if pesos20.sum()!=0 else 1.0
        for d in [1,2,3]: feats.append(sum(w for val,w in zip(ult,pesos20) if val==d)/s20)
        if window_size>1:
            alt_simples=sum(1 for j in range(1,window_size) if janela[j]!=janela[j-1])/(window_size-1)
            denom=sum(0.9**k for k in range(window_size-1))
            alt_pond=sum((janela[j]!=janela[j-1])*(0.9**(window_size-1-j)) for j in range(1,window_size))/(denom if denom!=0 else 1)
        else: alt_simples,alt_pond=0.0,0.0
        feats.extend([alt_simples,alt_pond])
        tend=[0.0,0.0,0.0]
        for val,w in zip(janela,pesos):
            if val in [1,2,3]: tend[val-1]+=w
        total_tend=sum(tend) if sum(tend)>0 else 1.0
        feats.extend([t/total_tend for t in tend])
        feats.append(max(tend)-min(tend))
        feats.append(janela.count(0)/window_size)
        for d in [1,2,3]:
            try: idx=window_size-1-janela[::-1].index(d); feats.append(idx/window_size)
            except ValueError: feats.append(1.0)
        ult5=janela[-5:] if window_size>=5 else janela
        for d in [1,2,3]: feats.append(ult5.count(d)/(len(ult5) if len(ult5) else 1))
        X.append(feats)
        y.append(alvo)
    return np.array(X,dtype=np.float32),np.array(y)

def montar_seq(labels_func,numeros):
    return [labels_func(n) for n in numeros]

# =========================
# TREINAMENTO
# =========================
# =========================
# TREINAMENTO COM CATBOOST
# =========================
def treinar_modelos_catboost():
    numeros = list(st.session_state.historico_numeros)
    if len(numeros) < tamanho_janela + 10:
        st.write("⚠️ Histórico curto, não treinar")
        return

    # --- Dúzia ---
    seq_duzia = montar_seq(numero_para_duzia, numeros)
    Xd, yd = criar_features_de_seq(seq_duzia, tamanho_janela)
    if Xd is not None and len(Xd) > 0:
        yd_classes = set(yd)
        if len(yd_classes) > 1:
            modelo_duzia = CatBoostClassifier(
                iterations=500,
                depth=8,
                learning_rate=0.1,
                loss_function='MultiClass',
                verbose=0,
                random_state=42
            )
            modelo_duzia.fit(np.array(Xd, dtype=float), yd)
            st.session_state.modelo_rf_duzia = modelo_duzia
            st.write("✅ Modelo Dúzia treinado")
        else:
            st.write(f"⚠️ Modelo Dúzia NÃO treinado: pouca diversidade de classes ({yd_classes})")
    else:
        st.write("⚠️ Modelo Dúzia NÃO treinado: features insuficientes")

    # --- Coluna ---
    seq_col = montar_seq(numero_para_coluna, numeros)
    Xc, yc = criar_features_de_seq(seq_col, tamanho_janela)
    if Xc is not None and len(Xc) > 0:
        yc_classes = set(yc)
        if len(yc_classes) > 1:
            modelo_col = CatBoostClassifier(
                iterations=500,
                depth=8,
                learning_rate=0.1,
                loss_function='MultiClass',
                verbose=0,
                random_state=42
            )
            modelo_col.fit(np.array(Xc, dtype=float), yc)
            st.session_state.modelo_rf_coluna = modelo_col
            st.write("✅ Modelo Coluna treinado")
        else:
            st.write(f"⚠️ Modelo Coluna NÃO treinado: pouca diversidade de classes ({yc_classes})")
    else:
        st.write("⚠️ Modelo Coluna NÃO treinado: features insuficientes")


# =========================
# PREVISÃO COM FALBACK
# =========================
def prever_top2_cat(seq_labels, modelo_cat):
    if modelo_cat is None:
        return None, None
    # Cria features da janela atual
    feats = _features_atual(seq_labels, tamanho_janela)
    if feats is None:
        return None, None
    try:
        probs = modelo_cat.predict_proba(feats)[0]
        classes = modelo_cat.classes_
    except:
        return None, None

    # Mapeia classes para probabilidades
    mapa = {int(c): float(p) for c, p in zip(classes, probs)}

    # Opcional: desconsidera zero
    if 0 in mapa:
        mapa[0] = -1.0

    # Ordena e pega top 2
    ordenado = sorted(mapa.items(), key=lambda kv: kv[1], reverse=True)
    top = ordenado[:2]
    return [t[0] for t in top], [max(0.0, t[1]) for t in top]

def prever_top2_cat(seq_labels, modelo):
    if modelo is None:
        # fallback: pegar últimas 2 classes mais frequentes
        cont = Counter(seq_labels[-tamanho_janela:])
        mais_freq = [k for k,_ in cont.most_common(2)]
        probs = [cont[mais_freq[0]]/tamanho_janela, cont[mais_freq[1]]/tamanho_janela] if len(mais_freq)>1 else [1.0, 0.0]
        return mais_freq, probs

    feats = _features_atual(seq_labels, tamanho_janela)
    if feats is None:
        st.write("⚠️ Features insuficientes para previsão")
        return None, None

    try:
        probs_array = modelo.predict_proba(feats)[0]
        classes = modelo.classes_
        mapa = {int(c): float(p) for c, p in zip(classes, probs_array)}
        for zero_key in [0]:
            if zero_key in mapa:
                mapa[zero_key] = -1.0
        ordenado = sorted(mapa.items(), key=lambda kv: kv[1], reverse=True)
        top = ordenado[:2]
        return [t[0] for t in top], [max(0.0, t[1]) for t in top]
    except Exception as e:
        st.write("⚠️ Erro na previsão:", e)
        return None, None

# =========================
# LOOP PRINCIPAL
# =========================
try:
    resposta=requests.get(API_URL,timeout=5).json()
    numero_atual=int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if numero_atual != st.session_state.ultimo_numero_salvo:
    salvar_numero(numero_atual)
    st.session_state.ultimo_numero_salvo=numero_atual
    if len(st.session_state.historico_numeros)>=tamanho_janela+10:
        treinar_modelos_catboost()

# =========================
# ALERTA DE RESULTADO
# =========================
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual
    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        tipo = st.session_state.tipo_entrada_anterior
        valor = numero_para_duzia(numero_atual) if tipo=="duzia" else numero_para_coluna(numero_atual)
        chave_resultado=f"{tipo}_{valor}_{st.session_state.ultima_chave_alerta}"
        if st.session_state.ultima_chave_resultado != chave_resultado:
            st.session_state.ultima_chave_resultado=chave_resultado
            if valor in st.session_state.ultima_entrada:
                st.session_state.acertos_top+=1
                enviar_telegram_async(f"✅ Saiu {numero_atual} ({tipo.capitalize()} {valor}) — 🟢 GREEN",delay=1)
            else:
                enviar_telegram_async(f"✅ Saiu {numero_atual} ({tipo.capitalize()} {valor}) — 🔴 RED",delay=1)

# =========================
# ALERTA DE PREVISÃO
# =========================
nums=list(st.session_state.historico_numeros)
if len(nums)>=tamanho_janela and (st.session_state.modelo_cat_duzia or st.session_state.modelo_cat_coluna):
    seq_duzia=montar_seq(numero_para_duzia,nums)
    seq_coluna=montar_seq(numero_para_coluna,nums)
    top_d,prob_d=prever_top2(seq_duzia,st.session_state.modelo_cat_duzia)
    top_c,prob_c=prever_top2(seq_coluna,st.session_state.modelo_cat_coluna)
    soma_d=sum(prob_d) if prob_d else -1.0
    soma_c=sum(prob_c) if prob_c else -1.0
    tipo_escolhido="duzia" if soma_d>=soma_c else "coluna"
    classes,probs=(top_d,prob_d) if tipo_escolhido=="duzia" else (top_c,prob_c)
    pode_alertar=classes is not None and len(classes)==2 and (max(probs)>=prob_minima or prob_minima<=0)
    if pode_alertar:
        chave_atual=f"{tipo_escolhido}_{classes[0]}_{classes[1]}"
        enviar=False
        if st.session_state.ultima_chave_alerta != chave_atual:
            enviar=True
            st.session_state.contador_sem_alerta=0
        elif st.session_state.contador_sem_alerta>=3:
            enviar=True
            st.session_state.contador_sem_alerta=0
        else:
            st.session_state.contador_sem_alerta+=1
        if enviar:
            st.session_state.ultima_entrada=classes
            st.session_state.tipo_entrada_anterior=tipo_escolhido
            st.session_state.ultima_chave_alerta=chave_atual
            msg=(
                f"📊 <b>ENTRADA ({tipo_escolhido.upper()})</b>\n"
                f"➡️ {classes[0]}ª ({probs[0]*100:.1f}%)\n"
                f"➡️ {classes[1]}ª ({probs[1]*100:.1f}%)"
            )
            enviar_telegram_async(msg,delay=2)

# =========================
# STATUS
# =========================
st.write("🎰 Último número:", numero_atual)
st.write(f"✅ Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
ult_duzias=[numero_para_duzia(n) for n in list(st.session_state.historico_numeros)[-12:]]
ult_colunas=[numero_para_coluna(n) for n in list(st.session_state.historico_numeros)[-12:]]
st.write("🧾 Últimos (números):",list(st.session_state.historico_numeros)[-12:])
st.write("📌 Últimos (dúzias):",ult_duzias)
st.write("📌 Últimos (colunas):",ult_colunas)

# =========================
# SALVAR ESTADO
# =========================
joblib.dump({
    "ultimo_numero_salvo": st.session_state.ultimo_numero_salvo,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero,
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "ultima_entrada": st.session_state.ultima_entrada,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "ultima_chave_resultado": st.session_state.ultima_chave_resultado,
    "modelo_cat_duzia": st.session_state.modelo_cat_duzia,
    "modelo_cat_coluna": st.session_state.modelo_cat_coluna,
}, ESTADO_PATH)

# =========================
# AUTO-REFRESH
# =========================
st_autorefresh(interval=REFRESH_INTERVAL,key="atualizacao")
