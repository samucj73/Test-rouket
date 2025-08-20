import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
from catboost import CatBoostClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 5 segundos
WINDOW_SIZE = 15  # janela para RF

# === CARREGA ESTADO ===
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try:
        ESTADO_PATH.unlink()
    except Exception:
        pass
    estado_salvo = {}

# === SESSION STATE ===

if "ultimo_numero_salvo" not in st.session_state:
    st.session_state.ultimo_numero_salvo = None
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior",
            "padroes_certos", "ultima_entrada", "modelo_rf", "ultimo_resultado_numero"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        elif var == "modelo_rf":
            st.session_state[var] = None
        else:
            st.session_state[var] = 0

for k, v in estado_salvo.items():
    st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (RF + Features Avançadas)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=5, max_value=150, value=WINDOW_SIZE)
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=10, max_value=100, value=30) / 100.0

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

def numero_para_duzia(num):
    if num == 0: return 0
    elif 1 <= num <= 12: return 1
    elif 13 <= num <= 24: return 2
    else: return 3

def salvar_historico_duzia(numero):
    duzia = numero_para_duzia(numero)
    st.session_state.historico.append(duzia)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

# === FEATURES (única função para treino e previsão) ===
def extrair_features(janela):
    """
    Extrai features a partir de uma janela de números crus (0–36).
    Inclui:
        - Estatísticas básicas
        - Dúzia, coluna
        - Par/ímpar, cor
        - Terminais, alternância
        - Blocos, streaks
        - Layout físico da roda (vizinhos, distâncias, setores)
        - Entropia, diferenças, lags
        - Tempo desde o último zero
        - Tendências multi-horizontes
        - Novas features: metades/quadrantes, rolling variance, hot/cold, decayed frequency, vida útil, opostos físicos
    """
    window_size = len(janela)
    if window_size == 0:
        return [0.0] * 300  # padding seguro (número de features aproximado)

    features = []

    # --- Constantes ---
    vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    pretos = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
    roleta = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,
              33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]  # ordem física europeia
    pos = {n:i for i,n in enumerate(roleta)}
    s1 = set(roleta[0:12])
    s2 = set(roleta[12:24])
    s3 = set(roleta[24:37])

    def cor(n):
        if n == 0: return 0
        return 1 if n in vermelhos else 2  # 1=vermelho, 2=preto

    def streaks(seq):
        if not seq: return 0, 0
        atual = maxs = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[i-1] and seq[i] != 0:
                atual += 1
                maxs = max(maxs, atual)
            else:
                atual = 1
        return atual, maxs

    # ===========================
    # 1) Estatísticas básicas
    # ===========================
    features.append(float(np.mean(janela)))
    features.append(float(np.std(janela)))
    features.append(float(janela[-1]))
    features.append(float(len(set(janela))))

    contagem = Counter(janela)
    for n in range(37):
        features.append(contagem.get(n,0)/window_size)

    ult5 = [-1]*5
    for i,n in enumerate(janela[-5:]):
        ult5[i] = n
    features.extend(ult5)

    # ===========================
    # 2) Dúzia / Coluna
    # ===========================
    duzias = [numero_para_duzia(n) for n in janela]
    cont_dz = Counter(duzias)
    for d in range(4):
        features.append(cont_dz.get(d,0)/window_size)

    colunas = [numero_para_coluna(n) for n in janela]
    cont_col = Counter(colunas)
    for c in range(4):
        features.append(cont_col.get(c,0)/window_size)

    # ===========================
    # 3) Par/ímpar e Cor
    # ===========================
    pares = sum(1 for n in janela if n>0 and n%2==0)
    impares = sum(1 for n in janela if n>0 and n%2==1)
    features.append(pares/window_size)
    features.append(impares/window_size)

    v_count = sum(1 for n in janela if n in vermelhos)
    p_count = sum(1 for n in janela if n in pretos)
    features.append(v_count/window_size)
    features.append(p_count/window_size)

    # ===========================
    # 4) Terminais + Alternância
    # ===========================
    terminais = [n%10 for n in janela if n>0]
    cont_term = Counter(terminais)
    top_terms = [t for t,_ in cont_term.most_common(2)]
    while len(top_terms)<2:
        top_terms.append(-1)
    features.extend(top_terms)

    altern = sum((janela[i]%2)!=(janela[i-1]%2) for i in range(1,window_size) if janela[i]>0 and janela[i-1]>0)
    features.append(altern/max(1,window_size-1))

    # ===========================
    # 5) Zero, Repetição, Blocos
    # ===========================
    features.append(contagem.get(0,0)/window_size)
    repet_last = sum(1 for i in range(1,window_size) if janela[i]==janela[i-1])
    features.append(repet_last/max(1,window_size-1))

    blocos = [(1,12),(13,24),(25,36)]
    for lo,hi in blocos:
        features.append(sum(1 for n in janela if lo<=n<=hi)/window_size)

    # ===========================
    # 6) Layout físico da roda
    # ===========================
    vizinhos = 0
    distancias = []
    for i in range(1,window_size):
        a,b = janela[i-1], janela[i]
        if a in pos and b in pos:
            d = abs(pos[a]-pos[b])
            d = min(d, len(roleta)-d)
            distancias.append(d)
            if d<=2: vizinhos+=1
    features.append(vizinhos/max(1,window_size-1))

    if distancias:
        features.append(float(np.mean(distancias)))
        features.append(float(np.std(distancias)))
        features.append(sum(1 for d in distancias if d>=10)/len(distancias))
    else:
        features.extend([0.0,0.0,0.0])

    s1c = sum(1 for n in janela if n in s1)/window_size
    s2c = sum(1 for n in janela if n in s2)/window_size
    s3c = sum(1 for n in janela if n in s3)/window_size
    features.extend([s1c,s2c,s3c])

    # ===========================
    # 7) Entropia e diferenças
    # ===========================
    freqs = np.array([c/window_size for c in contagem.values()])
    entropia = -np.sum(freqs*np.log2(freqs+1e-9))
    features.append(entropia)

    diffs = [abs(janela[i]-janela[i-1]) for i in range(1,window_size)]
    features.append(np.mean(diffs) if diffs else 0.0)

    # ===========================
    # 8) Streaks
    # ===========================
    cores = [cor(n) for n in janela]
    paridade = [0 if n==0 else (1 if n%2==0 else 2) for n in janela]

    cur_cor,max_cor = streaks(cores)
    cur_par,max_par = streaks(paridade)
    cur_dz,max_dz = streaks(duzias)
    cur_co,max_co = streaks(colunas)
    features.extend([cur_cor,max_cor,cur_par,max_par,cur_dz,max_dz,cur_co,max_co])

    # ===========================
    # 9) Tempo desde o último zero
    # ===========================
    try:
        last_zero_idx_from_end = next(i for i in range(window_size-1,-1,-1) if janela[i]==0)
        tempo_desde_zero = window_size-1 - last_zero_idx_from_end
    except StopIteration:
        tempo_desde_zero = window_size
    features.append(tempo_desde_zero/max(1,window_size))

    # ===========================
    # 10) Tendências multi-horizontes
    # ===========================
    for L in (min(12,window_size), min(36,window_size), min(72,window_size)):
        sub = janela[-L:]
        dz_sub = [numero_para_duzia(n) for n in sub]
        co_sub = [numero_para_coluna(n) for n in sub]
        c_dz = Counter(dz_sub); c_co = Counter(co_sub)
        for d in range(4): features.append(c_dz.get(d,0)/L)
        for c in range(4): features.append(c_co.get(c,0)/L)

    # ===========================
    # 11) Novas features adicionais
    # ===========================
    # a) Metades / Quadrantes
    for lo,hi in [(1,18),(19,36)]:
        features.append(sum(1 for n in janela if lo<=n<=hi)/window_size)
    for lo,hi in [(1,9),(10,18),(19,27),(28,36)]:
        features.append(sum(1 for n in janela if lo<=n<=hi)/window_size)

    # b) Rolling variance curto/médio/longo
    for L in (6,12,24):
        sub = janela[-min(L,window_size):]
        features.append(float(np.var(sub)) if sub else 0.0)

    # c) Vida útil últimos 5 números
    for n in janela[-5:]:
        try:
            idx = next(i for i in range(window_size-2,-1,-1) if janela[i]==n)
            life = (window_size-1) - idx
        except StopIteration:
            life = window_size
        features.append(life/window_size)

    # d) Decay frequency
    decay = np.exp(-np.linspace(0,3,window_size))
    for n in range(37):
        weighted = sum(decay[i] for i,v in enumerate(janela[::-1]) if v==n)
        features.append(weighted/np.sum(decay))

    # e) Números opostos físicos
    opostos = 0
    for i in range(1,window_size):
        a,b = janela[i-1], janela[i]
        if a in pos and b in pos:
            d = abs(pos[a]-pos[b])
            d = min(d,len(roleta)-d)
            if 15<=d<=18: opostos+=1
    features.append(opostos/max(1,window_size-1))

    # f) Hot/Cold score
    mais_comum = contagem.most_common(1)[0][1] if contagem else 0
    menos_comum = contagem.most_common()[-1][1] if contagem else 0
    features.append((mais_comum - menos_comum)/max(1,window_size))

    # g) Lag features 2,3,4
    for lag in [2,3,4]:
        diffs_lag = [abs(janela[i]-janela[i-lag]) for i in range(lag, window_size)]
        features.append(np.mean(diffs_lag) if diffs_lag else 0.0)

    # ===========================
    return features

def criar_dataset(historico, tamanho_janela=15):
    X, y = [], []
    if len(historico) <= tamanho_janela:
        return np.empty((0, tamanho_janela)), np.array([])  # evita erro

    for i in range(len(historico) - tamanho_janela):
        X.append(historico[i:i+tamanho_janela])
        y.append(historico[i+tamanho_janela])

    return np.array(X), np.array(y)





# === TREINAMENTO ===

def treinar_modelo_rf():
    X, y = criar_dataset(st.session_state.historico, tamanho_janela)
    if len(y) > 1 and len(set(y)) > 1:  # precisa de mais de uma amostra e pelo menos 2 classes
        from catboost import CatBoostClassifier
        modelo = CatBoostClassifier(
            iterations=200,
            depth=6,
            learning_rate=0.1,
            loss_function='MultiClass',
            verbose=False
        )
        modelo.fit(X, y)
        st.session_state.modelo_rf = modelo







# === PREVISÃO ===
def prever_duzia_rf():
    janela = list(st.session_state.historico)[-tamanho_janela:]
    if len(janela) < tamanho_janela:
        return None, None
    features = np.array(extrair_features(janela)).reshape(1, -1)
    try:
        probs = st.session_state.modelo_rf.predict_proba(features)[0]
        classes = st.session_state.modelo_rf.classes_
    except Exception as e:
        st.warning(f"Erro na predição RF: {e}")
        return None, None

    top_idxs = np.argsort(probs)[-2:][::-1]
    top_duzias = classes[top_idxs]
    top_probs = probs[top_idxs]

    return list(top_duzias), list(top_probs)

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if numero_atual != st.session_state.ultimo_numero_salvo:
    duzia_atual = salvar_historico_duzia(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual

    if len(st.session_state.historico) >= tamanho_janela + 2 and len(st.session_state.historico) % 2 == 0:
        treinar_modelo_rf()

# === ALERTA DE RESULTADO === (SEM ALTERAÇÃO)
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual

    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor = numero_para_duzia(numero_atual)
        if valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🟢", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🔴", delay=1)

    if st.session_state.modelo_rf is not None and len(st.session_state.historico) >= tamanho_janela:
        try:
            duzias_previstas, probs = prever_duzia_rf()
            if duzias_previstas is not None:
                st.session_state.ultima_entrada = duzias_previstas
                st.session_state.tipo_entrada_anterior = "duzia"
                st.session_state.contador_sem_alerta = 0
                st.session_state.ultima_chave_alerta = f"duzia_{duzias_previstas[0]}_{duzias_previstas[1]}"
                mensagem_alerta = (
                    f"📊 <b>ENT DÚZIA:</b> {duzias_previstas[0]} / {duzias_previstas[1]}"
                    f" (conf: {probs[0]*100:.1f}% / {probs[1]*100:.1f}%)"
                )
                enviar_telegram_async(mensagem_alerta, delay=5)
        except Exception as e:
            st.warning(f"Erro na previsão: {e}")

# === INTERFACE ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])

# === SALVA ESTADO ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "ultima_entrada": st.session_state.ultima_entrada,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "modelo_rf": st.session_state.modelo_rf,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero
}, ESTADO_PATH)

# === AUTO REFRESH ===
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
