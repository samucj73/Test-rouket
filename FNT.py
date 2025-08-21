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
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000   # 5s
WINDOW_SIZE = 15          # janela p/ features
RETRAIN_EVERY = 2         # re-treina a cada N giros novos
TOP_K_NUMEROS = 3         # números top

# === CARREGA ESTADO ===
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try: ESTADO_PATH.unlink()
    except Exception: pass
    estado_salvo = {}

# === SESSION STATE ===
for var in [
    "ultimo_numero_salvo","ultima_chave_alerta","historico","acertos_top",
    "total_top","contador_sem_alerta","tipo_entrada_anterior","padroes_certos",
    "ultima_entrada","modelo_numero","modelo_duzia","modelo_coluna",
    "ultimo_resultado_numero","spins_desde_treino"
]:
    if var not in st.session_state:
        if var == "historico":
            st.session_state[var] = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)
        elif var in ["padroes_certos"]:
            st.session_state[var] = []
        elif var == "ultima_entrada":
            st.session_state[var] = None
        elif var in ["modelo_numero","modelo_duzia","modelo_coluna"]:
            st.session_state[var] = None
        elif var == "spins_desde_treino":
            st.session_state[var] = 0
        else:
            st.session_state[var] = 0

# restaurar chaves salvas (ignora modelos)
for k,v in estado_salvo.items():
    if k not in ["modelo_numero","modelo_duzia","modelo_coluna"]:
        st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Números + Dúzia + Coluna (CatBoost + Fallback)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=5, max_value=150, value=WINDOW_SIZE)
prob_minima = st.slider("📊 Probabilidade mínima para alertar (%)", min_value=10, max_value=100, value=30) / 100.0
top_k_numeros = st.slider("🔥 Quantos números no Top (1–5)", min_value=1, max_value=5, value=TOP_K_NUMEROS)

# === FUNÇÕES AUXILIARES ===
def enviar_telegram_async(mensagem, delay=0):
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)
    if delay > 0:
        threading.Timer(delay, _send).start()
    else:
        threading.Thread(target=_send, daemon=True).start()

def numero_para_duzia(n):
    if n == 0: return 0
    if 1 <= n <= 12: return 1
    if 13 <= n <= 24: return 2
    return 3

def numero_para_coluna(n):
    if n == 0: return 0
    return (n-1)%3 + 1

def salvar_historico_numero(numero):
    st.session_state.historico.append(numero)
    joblib.dump(st.session_state.historico,HISTORICO_PATH)
    return numero

# === FUNÇÃO extrair_features revisada ===
def extrair_features(janela):
    """
    Função revisada, entropia corrigida e simplificada.
    Retorna lista de features numéricas.
    """
    window_size = len(janela)
    if window_size == 0:
        return [0.0]*200

    features = []

    vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    pretos = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
    roleta = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,
              33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
    pos = {n:i for i,n in enumerate(roleta)}

    def cor(n):
        if n==0: return 0
        return 1 if n in vermelhos else 2

    contagem = Counter(janela)
    features.append(np.mean(janela))
    features.append(np.std(janela))
    features.append(janela[-1])
    features.append(len(set(janela)))

    # frequência de cada número
    for n in range(37):
        features.append(contagem.get(n,0)/window_size)

    # últimas 5 posições
    ult5 = [-1]*5
    for i,n in enumerate(janela[-5:]):
        ult5[i]=n
    features.extend(ult5)

    # dúzia / coluna
    duzias = [numero_para_duzia(n) for n in janela]
    colunas = [numero_para_coluna(n) for n in janela]
    cont_dz = Counter(duzias)
    cont_col = Counter(colunas)
    for i in range(4):
        features.append(cont_dz.get(i,0)/window_size)
        features.append(cont_col.get(i,0)/window_size)

    # par/impar e cor
    pares = sum(1 for n in janela if n>0 and n%2==0)
    impares = sum(1 for n in janela if n>0 and n%2==1)
    features.append(pares/window_size)
    features.append(impares/window_size)
    v_count = sum(1 for n in janela if n in vermelhos)
    p_count = sum(1 for n in janela if n in pretos)
    features.append(v_count/window_size)
    features.append(p_count/window_size)

    # terminais e alternância
    terminais = [n%10 for n in janela if n>0]
    cont_term = Counter(terminais)
    top_terms = [t for t,_ in cont_term.most_common(2)]
    while len(top_terms)<2:
        top_terms.append(-1)
    features.extend(top_terms)
    altern = sum((janela[i]%2)!=(janela[i-1]%2) for i in range(1,window_size) if janela[i]>0 and janela[i-1]>0)
    features.append(altern/max(1,window_size-1))

    # zero e repetições
    features.append(contagem.get(0,0)/window_size)
    repet_last = sum(1 for i in range(1,window_size) if janela[i]==janela[i-1])
    features.append(repet_last/max(1,window_size-1))

    # layout físico
    vizinhos=0; distancias=[]
    for i in range(1,window_size):
        a,b = janela[i-1], janela[i]
        if a in pos and b in pos:
            d = abs(pos[a]-pos[b])
            d=min(d,len(roleta)-d)
            distancias.append(d)
            if d<=2: vizinhos+=1
    features.append(vizinhos/max(1,window_size-1))
    if distancias:
        features.append(np.mean(distancias))
        features.append(np.std(distancias))
        features.append(sum(1 for d in distancias if d>=10)/len(distancias))
    else:
        features.extend([0.0,0.0,0.0])

    # entropia
    freqs = np.array(list(contagem.values()))/window_size
    entropia = -np.sum(freqs*np.log2(freqs+1e-9))
    features.append(entropia)

    # streaks
    def streaks(seq):
        if not seq: return 0,0
        atual=maxs=1
        for i in range(1,len(seq)):
            if seq[i]==seq[i-1] and seq[i]!=0:
                atual+=1
                maxs=max(maxs,atual)
            else:
                atual=1
        return atual,maxs
    cores = [cor(n) for n in janela]
    cur_cor,max_cor = streaks(cores)
    cur_par,max_par = streaks([0 if n==0 else 1 if n%2==0 else 2 for n in janela])
    cur_dz,max_dz = streaks(duzias)
    cur_co,max_co = streaks(colunas)
    features.extend([cur_cor,max_cor,cur_par,max_par,cur_dz,max_dz,cur_co,max_co])

    # tempo desde último zero
    try:
        last_zero_idx = next(i for i in range(window_size-1,-1,-1) if janela[i]==0)
        tempo_zero = window_size-1 - last_zero_idx
    except StopIteration:
        tempo_zero = window_size
    features.append(tempo_zero/max(1,window_size))

    return features

# === CRIAR DATASET ===
def criar_dataset(historico, window):
    if len(historico)<window+1:
        return np.empty((0,1)),np.array([]),np.array([]),np.array([])
    X,y_num,y_dz,y_col=[],[],[],[]
    hist=list(historico)
    for i in range(window,len(hist)):
        janela = hist[i-window:i]
        X.append(extrair_features(janela))
        alvo = hist[i]
        y_num.append(alvo)
        y_dz.append(numero_para_duzia(alvo))
        y_col.append(numero_para_coluna(alvo))
    return np.array(X),np.array(y_num),np.array(y_dz),np.array(y_col)

# === TREINAMENTO MODELOS ===
def treinar_modelos():
    X,y_num,y_dz,y_col = criar_dataset(st.session_state.historico,tamanho_janela)
    if X.shape[0]==0: return

    # NÚMERO
    if len(set(y_num))>1:
        try:
            m_num = CatBoostClassifier(iterations=200,depth=6,learning_rate=0.1,loss_function='MultiClass',verbose=False)
            m_num.fit(X,y_num)
            st.session_state.modelo_numero=m_num
        except Exception as e:
            st.warning(f"Erro treino NÚMERO: {e}")

    # DÚZIA
    if len(set(y_dz))>1:
        try:
            m_dz = CatBoostClassifier(iterations=200,depth=6,learning_rate=0.1,loss_function='MultiClass',verbose=False)
            m_dz.fit(X,y_dz)
            st.session_state.modelo_duzia=m_dz
        except Exception as e:
            st.warning(f"Erro treino DÚZIA: {e}")

    # COLUNA
    if len(set(y_col))>1:
        try:
            m_col = CatBoostClassifier(iterations=200,depth=6,learning_rate=0.1,loss_function='MultiClass',verbose=False)
            m_col.fit(X,y_col)
            st.session_state.modelo_coluna=m_col
        except Exception as e:
            st.warning(f"Erro treino COLUNA: {e}")

# === PREVISÃO + FALLBACK ===
def prever_tudo(top_k=3):
    janela = list(st.session_state.historico)[-tamanho_janela:]
    if len(janela)==0: return None
    feats = np.array(extrair_features(janela)).reshape(1,-1)

    # NÚMEROS
    if st.session_state.modelo_numero:
        try:
            probs_num = st.session_state.modelo_numero.predict_proba(feats)[0]
            idx_ord = np.argsort(probs_num)[::-1]
            top_idx = idx_ord[:top_k]
            top_nums = top_idx.tolist()
        except:
            cont = Counter(janela)
            top = [x for x,_ in cont.most_common(top_k)]
            top_nums = top + [None]*(top_k-len(top))
    else:
        cont = Counter(janela)
        top = [x for x,_ in cont.most_common(top_k)]
        top_nums = top + [None]*(top_k-len(top))

    # DÚZIA
    if st.session_state.modelo_duzia:
        try:
            probs_dz = st.session_state.modelo_duzia.predict_proba(feats)[0]
            dz_classe = int(np.argmax(probs_dz))
            dz_prob = float(np.max(probs_dz))
        except:
            dzs = [numero_para_duzia(n) for n in janela]
            cont_dz = Counter(dzs)
            dz_classe,dz_prob = cont_dz.most_common(1)[0]
            dz_prob/=len(dzs)
    else:
        dzs = [numero_para_duzia(n) for n in janela]
        cont_dz = Counter(dzs)
        dz_classe,dz_prob = cont_dz.most_common(1)[0]
        dz_prob/=len(dzs)

    # COLUNA
    if st.session_state.modelo_coluna:
        try:
            probs_col = st.session_state.modelo_coluna.predict_proba(feats)[0]
            col_classe = int(np.argmax(probs_col))
            col_prob = float(np.max(probs_col))
        except:
            cols = [numero_para_coluna(n) for n in janela]
            cont_col = Counter(cols)
            col_classe,col_prob = cont_col.most_common(1)[0]
            col_prob/=len(cols)
    else:
        cols = [numero_para_coluna(n) for n in janela]
        cont_col = Counter(cols)
        col_classe,col_prob = cont_col.most_common(1)[0]
        col_prob/=len(cols)

    return {"numeros":top_nums,"duzia":dz_classe,"prob_duzia":dz_prob,"coluna":col_classe,"prob_coluna":col_prob}

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL,timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if numero_atual != st.session_state.ultimo_numero_salvo:
    salvar_historico_numero(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual
    st.session_state.spins_desde_treino +=1

    if (st.session_state.spins_desde_treino>=RETRAIN_EVERY) or \
       (st.session_state.modelo_numero is None and st.session_state.modelo_duzia is None and st.session_state.modelo_coluna is None):
        treinar_modelos()
        st.session_state.spins_desde_treino=0

# === ALERTA DE RESULTADO + NOVA PREVISÃO ===
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual

    if st.session_state.ultima_entrada:
        st.session_state.total_top+=1
        acertou=False

        if numero_atual in (st.session_state.ultima_entrada.get("numeros") or []):
            acertou=True
        if numero_para_duzia(numero_atual)==st.session_state.ultima_entrada.get("duzia"):
            acertou=True
        if numero_para_coluna(numero_atual)==st.session_state.ultima_entrada.get("coluna"):
            acertou=True

        if acertou:
            st.session_state.acertos_top+=1
            enviar_telegram_async(f"✅ Saiu {numero_atual} → 🟢", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} → 🔴", delay=1)

    prev = prever_tudo(top_k=top_k_numeros)
    if prev:
        st.session_state.ultima_entrada = prev
        if (prev["prob_duzia"]>=prob_minima) or (prev["prob_coluna"]>=prob_minima):
            numeros_fmt = ", ".join(str(n) for n in prev["numeros"] if n is not None)
            msg = (
                f"📊 <b>ENTRADA</b>\n"
                f"🔥 Números: {numeros_fmt}\n"
                f"🎯 Dúzia: {prev['duzia']} ({prev['prob_duzia']*100:.1f}%)\n"
                f"📈 Coluna: {prev['coluna']} ({prev['prob_coluna']*100:.1f}%)"
            )
            enviar_telegram_async(msg, delay=4)

# === INTERFACE ===
st.write("Último número:",numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
ultimos_n = list(st.session_state.historico)[-min(20,len(st.session_state.historico)):]
st.write("Últimos registros (números):",ultimos_n)
if st.session_state.ultima_entrada:
        st.subheader("🧠 Última previsão")
    nums_fmt = ", ".join(str(n) for n in st.session_state.ultima_entrada["numeros"] if n is not None)
    st.write(f"Números: {nums_fmt}")
    st.write(f"Dúzia: {st.session_state.ultima_entrada['duzia']} "
             f"({st.session_state.ultima_entrada['prob_duzia']*100:.1f}%)")
    st.write(f"Coluna: {st.session_state.ultima_entrada['coluna']} "
             f"({st.session_state.ultima_entrada['prob_coluna']*100:.1f}%)")

# === AUTOREFRESH ===
st_autorefresh(interval=REFRESH_INTERVAL, key="refresh")

# === SALVA ESTADO ATUAL ===
estado_para_salvar = {
    "ultimo_numero_salvo": st.session_state.ultimo_numero_salvo,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "historico": st.session_state.historico,
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "ultima_entrada": st.session_state.ultima_entrada,
    "spins_desde_treino": st.session_state.spins_desde_treino
}
joblib.dump(estado_para_salvar, ESTADO_PATH)
    
