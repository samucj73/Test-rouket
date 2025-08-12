import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
import threading

# === CONFIG ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2f9RY"
TELEGRAM_CHAT_ID = "-1002880411750"

HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")

MAX_HIST = 5000
MIN_TREINO = 120
REFRESH_INTERVAL = 10_000
BASE_PROB_MIN = 0.95
FORCE_AFTER = 3

ROULETTE_ORDER = [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
                  30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
                  29, 7, 28, 12, 35, 3, 26, 0]

# === SESSION STATE INIT ===
if "historico" not in st.session_state:
    if HISTORICO_PATH.exists():
        st.session_state.historico = joblib.load(HISTORICO_PATH)
        if not isinstance(st.session_state.historico, deque):
            st.session_state.historico = deque(st.session_state.historico, maxlen=MAX_HIST)
    else:
        st.session_state.historico = deque(maxlen=MAX_HIST)

for k, default in [
    ("acertos_top", 0),
    ("total_top", 0),
    ("ultimo_numero", None),
    ("entrada_anterior", []),
    ("tipo_entrada_anterior", None),
    ("contador_sem_alerta", 0),
    ("modelo_duzia", None),
    ("modelo_coluna", None),
    ("modelo_terco", None),
    ("modelo_quentes", None),
    ("historico_metrics", {"last_probs": deque(maxlen=50)}),
]:
    if k not in st.session_state:
        st.session_state[k] = default

if ESTADO_PATH.exists():
    try:
        saved = joblib.load(ESTADO_PATH)
        for k, v in saved.items():
            st.session_state[k] = v
    except Exception:
        pass

# === UTIL ===
def enviar_telegram_async(msg):
    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
        except:
            pass
    threading.Thread(target=_send, daemon=True).start()

def cor(n):
    if n == 0: return 'G'
    reds = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    return 'R' if n in reds else 'B'

def distancia_fisica(n1, n2):
    if n1 not in ROULETTE_ORDER or n2 not in ROULETTE_ORDER:
        return 0
    i1, i2 = ROULETTE_ORDER.index(n1), ROULETTE_ORDER.index(n2)
    diff = abs(i1 - i2)
    return min(diff, len(ROULETTE_ORDER) - diff)

# === FEATURES ===
def build_features(historico_list):
    h = historico_list
    if len(h) < 12: return None
    windows = [12, 25, 50, 110]
    feats = []
    last = h[-1]

    for w in windows:
        win = h[-w:] if len(h) >= w else h[:]
        cnt = Counter(win)
        feats.append(cnt.get(0,0)/max(1,len(win)))
        for d in (1,2,3):
            feats.append(sum(1 for n in win if n!=0 and ((n-1)//12 + 1)==d)/max(1,len(win)))
        for c in (1,2,3):
            feats.append(sum(1 for n in win if n!=0 and ((n-1)%3 + 1)==c)/max(1,len(win)))
        feats.append(sum(1 for n in win if cor(n)=='R')/len(win))
        feats.append(sum(1 for n in win if cor(n)=='B')/len(win))
        feats.append(sum(1 for n in win if n!=0 and n%2==0)/len(win))
        feats.append(sum(1 for n in win if n!=0 and n%2==1)/len(win))

    for k in (3,5):
        lastk = h[-k:]
        feats.append(sum(1 for n in lastk if n!=0 and ((n-1)//12 + 1)==((h[-1]-1)//12 + 1))/k if h[-1]!=0 else 0)
        feats.append(sum(1 for n in lastk if n!=0 and ((n-1)%3 + 1)==((h[-1]-1)%3 + 1))/k if h[-1]!=0 else 0)
        feats.append(sum(1 for n in lastk if n==h[-1])/k)

    rev = list(reversed(h[:-1]))
    tz = next((i for i, v in enumerate(rev, start=1) if v==0), len(h))
    feats.append(tz)

    for k in (3,5):
        tail = h[-k-1:-1] if len(h) > k else h[:-1]
        if len(tail)==0:
            feats.append(0)
        else:
            feats.append(np.mean([distancia_fisica(h[-1], v) for v in tail]))

    last_duzia = (h[-1]-1)//12 + 1 if h[-1]!=0 else 0
    last_coluna = (h[-1]-1)%3 + 1 if h[-1]!=0 else 0
    feats.append(last_duzia)
    feats.append(last_coluna)
    return np.array(feats, dtype=float).reshape(1, -1)

def build_training_dataset(historico_list, target="quentes"):
    h = list(historico_list)
    X, y = [], []
    start = 110
    if len(h) <= start:
        return np.array([]), np.array([])
    if target == "quentes":
        for i in range(start, len(h)):
            sub = h[:i+1]
            f = build_features(sub)
            if f is None: continue
            X.append(f.flatten())
            y.append(h[i])
        return np.array(X), np.array(y)
    elif target == "duzia":
        Xf, yf = extrair_features_duzia_coluna(h)
        return Xf, yf[0]
    elif target == "coluna":
        Xf, yf = extrair_features_duzia_coluna(h)
        return Xf, yf[1]
    elif target == "terco":
        Xf, yf = extrair_features_tercos(h)
        return Xf, yf
    else:
        return np.array([]), np.array([])

def extrair_features_duzia_coluna(historico):
    historico = list(historico)
    X, y_duzia, y_coluna = [], [], []
    for i in range(111, len(historico)):
        janela = historico[i-110:i]
        ult = historico[i-1]
        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')
        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = sum(1 for n in janela if n != 0 and n % 2 != 0)
        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0
        tempo_zero = next((idx for idx, val in enumerate(reversed(janela), 1) if val == 0), len(janela))
        dist_fisica = float(np.mean([distancia_fisica(ult, n) for n in janela[-3:]]))
        features = [vermelhos, pretos, verdes, pares, impares, duzia, coluna, tempo_zero, dist_fisica]
        X.append(features)
        y_duzia.append(duzia)
        y_coluna.append(coluna)
    return np.array(X), (np.array(y_duzia), np.array(y_coluna))

def extrair_features_tercos(historico):
    historico = list(historico)
    X, y_terco = [], []
    for i in range(111, len(historico)):
        janela = historico[i-110:i]
        ult = historico[i-1]
        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')
        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = sum(1 for n in janela if n != 0 and n % 2 != 0)
        tempo_zero = next((idx for idx, val in enumerate(reversed(janela), 1) if val == 0), len(janela))
        dist_fisica = float(np.mean([distancia_fisica(ult, n) for n in janela[-3:]]))
        # Terço: 1 se posição no ROULETTE_ORDER < 12, 2 se entre 12 e 23, 3 se >= 24
        if ult == 0:
            terco = 0
        else:
            idx = ROULETTE_ORDER.index(ult)
            if idx < 12:
                terco = 1
            elif idx < 24:
                terco = 2
            else:
                terco = 3
        features = [vermelhos, pretos, verdes, pares, impares, tempo_zero, dist_fisica]
        X.append(features)
        y_terco.append(terco)
    return np.array(X), np.array(y_terco)

def train_ensemble(X, y, params_lgb=None, params_rf=None):
    if X.shape[0] < MIN_TREINO: return None
    params_lgb = params_lgb or {"n_estimators":300, "learning_rate":0.05}
    params_rf = params_rf or {"n_estimators":150}
    lgb = LGBMClassifier(**params_lgb)
    rf = RandomForestClassifier(**params_rf)
    lgb.fit(X, y)
    rf.fit(X, y)
    return (lgb, rf)

def predict_ensemble(models_tuple, x, top_n=2):
    try:
        lgb, rf = models_tuple
        classes = lgb.classes_
        p1 = lgb.predict_proba(x)[0]
        p2 = rf.predict_proba(x)[0]
        probs = (p1 + p2) / 2
        idxs = np.argsort(probs)[::-1][:top_n]
        top_labels = [int(classes[i]) for i in idxs]
        top_probs = [float(probs[i]) for i in idxs]
        return top_labels, top_probs, sum(top_probs)
    except:
        return [], [], 0.0

def full_train_if_needed():
    h = list(st.session_state.historico)
    # Quentes
    Xq, yq = build_training_dataset(h, "quentes")
    if Xq.size == 0:
        st.session_state.modelo_quentes = None
    else:
        st.session_state.modelo_quentes = train_ensemble(Xq, yq)

    # Dúzia e Coluna
    Xdc, (yd, yc) = extrair_features_duzia_coluna(h)
    st.session_state.modelo_duzia = train_ensemble(Xdc, yd)
    st.session_state.modelo_coluna = train_ensemble(Xdc, yc)

    # Terços
    Xt, yt = extrair_features_tercos(h)
    st.session_state.modelo_terco = train_ensemble(Xt, yt)

def adaptive_threshold():
    last_probs = st.session_state.historico_metrics.get("last_probs", deque(maxlen=50))
    if len(last_probs) < 6:
        return BASE_PROB_MIN
    arr = np.array(last_probs)
    mean = arr.mean()
    std = arr.std()
    if mean > 0.7 and std < 0.05:
        return max(0.88, BASE_PROB_MIN - 0.03)
    if std > 0.12:
        return min(0.99, BASE_PROB_MIN + 0.02)
    return BASE_PROB_MIN

# === MAIN ===
st.title("🎯 IA Roleta - Top 2 Números Quentes + Dúzia, Coluna e Terços")

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=REFRESH_INTERVAL, key="ref")

numero_atual = None
try:
    resp = requests.get(API_URL, timeout=5)
    resp.raise_for_status()
    numero_atual = int(resp.json()["data"]["result"]["outcome"]["number"])
except:
    st.error("Erro ao obter número atual")

if numero_atual is not None:
    st.write("Último número:", numero_atual)

    if st.session_state.ultimo_numero is None or numero_atual != st.session_state.ultimo_numero:
        st.session_state.ultimo_numero = numero_atual
        st.session_state.historico.append(numero_atual)
        try:
            joblib.dump(deque(list(st.session_state.historico)[-MAX_HIST:], maxlen=MAX_HIST), HISTORICO_PATH)
        except:
            pass

        # Avaliar acerto da previsão anterior
        if st.session_state.entrada_anterior and st.session_state.tipo_entrada_anterior:
            tipo_prev = st.session_state.tipo_entrada_anterior
            top_prev = st.session_state.entrada_anterior
            val = None
            hit = False
            if tipo_prev == "quentes":
                hit = numero_atual in top_prev
                val = numero_atual
            elif tipo_prev == "duzia":
                val = (numero_atual - 1)//12 + 1 if numero_atual!=0 else 0
                hit = val in top_prev
            elif tipo_prev == "coluna":
                val = (numero_atual - 1)%3 + 1 if numero_atual!=0 else 0
                hit = val in top_prev
            elif tipo_prev == "terco":
                if numero_atual==0:
                    val = 0
                else:
                    idx = ROULETTE_ORDER.index(numero_atual)
                    if idx < 12:
                        val = 1
                    elif idx < 24:
                        val = 2
                    else:
                        val = 3
                hit = val in top_prev

            st.session_state.total_top += 1
            if hit:
                st.session_state.acertos_top += 1
                enviar_telegram_async(f"✅ Saiu {numero_atual} ({val} {tipo_prev}): 🟢")
            else:
                enviar_telegram_async(f"✅ Saiu {numero_atual} ({val} {tipo_prev}): 🔴")

        # Treinamento incremental
        if len(st.session_state.historico) >= MIN_TREINO:
            full_train_if_needed()

        # Previsões
        X_latest = build_features(list(st.session_state.historico))
        results = {}

        if X_latest is not None:
            for tipo in ["quentes", "duzia", "coluna", "terco"]:
                modelo = st.session_state.get(f"modelo_{tipo}")
                if modelo is not None:
                    top, probs, soma = predict_ensemble(modelo, X_latest, top_n=2)
                    results[tipo] = {"top": top, "probs": probs, "sum": soma}

        if results:
            best_tipo = max(results.items(), key=lambda kv: kv[1]["sum"])[0]
            best = results[best_tipo]
            tipo_escolhido = best_tipo
            top_labels = best["top"]
            soma_prob = best["sum"]
            st.session_state.historico_metrics.setdefault("last_probs", deque(maxlen=50)).append(soma_prob)
        else:
            tipo_escolhido = None
            top_labels = []
            soma_prob = 0.0

        limiar = adaptive_threshold()
        send_alert = False

        if soma_prob >= limiar and top_labels:
            if top_labels != st.session_state.entrada_anterior or tipo_escolhido != st.session_state.tipo_entrada_anterior:
                send_alert = True
            else:
                st.session_state.contador_sem_alerta += 1
                if st.session_state.contador_sem_alerta >= FORCE_AFTER:
                    send_alert = True
                    st.session_state.contador_sem_alerta = 0
        else:
            st.session_state.contador_sem_alerta += 1

        if send_alert and top_labels:
            st.session_state.entrada_anterior = top_labels
            st.session_state.tipo_entrada_anterior = tipo_escolhido
            st.session_state.contador_sem_alerta = 0

            if tipo_escolhido == "quentes":
                texto_top = ", ".join(str(n) for n in top_labels)
            elif tipo_escolhido in ("duzia", "coluna"):
                texto_top = f"{top_labels[0]}ª e {top_labels[1]}ª" if len(top_labels) >= 2 else f"{top_labels[0]}ª"
                        elif tipo_escolhido == "terco":
                texto_top = f"{top_labels[0]}º e {top_labels[1]}º terço" if len(top_labels) >= 2 else f"{top_labels[0]}º terço"
            else:
                texto_top = ", ".join(str(n) for n in top_labels)

            msg = (f"📊 <b>ENTRADA {tipo_escolhido.upper()}S:</b> {texto_top} "
                   f"(confiança: {soma_prob:.2%})")
            enviar_telegram_async(msg)

# Mostra interface Streamlit
st.write(f"Último número: {st.session_state.ultimo_numero}")
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos números:", list(st.session_state.historico)[-12:])

# Salva estado e histórico
try:
    joblib.dump({
        "acertos_top": st.session_state.acertos_top,
        "total_top": st.session_state.total_top,
        "entrada_anterior": st.session_state.entrada_anterior,
        "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
        "contador_sem_alerta": st.session_state.contador_sem_alerta,
        "ultimo_numero": st.session_state.ultimo_numero,
        "historico_metrics": st.session_state.historico_metrics
    }, ESTADO_PATH)
    joblib.dump(deque(list(st.session_state.historico)[-MAX_HIST:], maxlen=MAX_HIST), HISTORICO_PATH)
except Exception as e:
    st.error(f"Erro ao salvar estado: {e}")
