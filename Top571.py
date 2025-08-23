import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier
import time

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

TAMANHO_JANELA_DEFAULT = 15
MAX_HISTORICO = 4500
REFRESH_INTERVAL_MS = 5000
TRAIN_EVERY = 2

MODELO_NUM_PATH = Path("modelo_top5_num.pkl")
HIST_PATH_NUMS = Path("historico_numeros.pkl")
ESTADO_PATH = Path("estado.pkl")

# =========================
# ROLETA EUROPEIA
# =========================
RED_SET = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
IDX = {n:i for i,n in enumerate(WHEEL)}

def is_red(n:int)->int:
    return 1 if (n in RED_SET) else 0

# =========================
# CARREGA ESTADO SALVO
# =========================
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception:
    estado_salvo = {}

# =========================
# SESSION STATE INIT
# =========================
# =========================
# SESSION STATE INIT CORRIGIDO
# =========================
if "historico_numeros" not in st.session_state:
    st.session_state.historico_numeros = deque(maxlen=MAX_HISTORICO)
    if HIST_PATH_NUMS.exists():
        hist = joblib.load(HIST_PATH_NUMS)
        st.session_state.historico_numeros.extend(hist)

if "modelo_num" not in st.session_state:
    st.session_state.modelo_num = joblib.load(MODELO_NUM_PATH) if MODELO_NUM_PATH.exists() else None

st.session_state.tamanho_janela = st.session_state.get("tamanho_janela", TAMANHO_JANELA_DEFAULT)
st.session_state.prob_minima = st.session_state.get("prob_minima", 0.30)
st.session_state.ultima_entrada_num = st.session_state.get("ultima_entrada_num", None)
st.session_state.ultimo_numero_salvo = st.session_state.get("ultimo_numero_salvo", None)
st.session_state.acertos_num = st.session_state.get("acertos_num", 0)
st.session_state.total_num = st.session_state.get("total_num", 0)
st.session_state.contador_sem_envio = st.session_state.get("contador_sem_envio", 0)
st.session_state._alerta_enviado_num = st.session_state.get("_alerta_enviado_num", False)

# =========================
# UI
# =========================
st.set_page_config(page_title="IA Roleta - Top 5 Números", page_icon="🎯", layout="centered")
st.title("🎯 IA Roleta - Top 5 Números (com captura automática)")

col1, col2 = st.columns([2,1])
with col1:
    st.session_state.tamanho_janela = st.slider(
        "📏 Tamanho da janela (giros para features)",
        5, 150, st.session_state.tamanho_janela, key="slider_tamanho"
    )
with col2:
    st.session_state.prob_minima = st.slider(
        "📊 Prob mínima (%)", 10, 100, int(st.session_state.prob_minima * 100), key="slider_prob"
    ) / 100.0

# =========================
# AUTO-REFRESH
# =========================
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="autorefresh")

# =========================
# FUNÇÃO PARA SALVAR HISTÓRICO
# =========================
def salvar_historico(numero:int):
    if numero is None:
        return
    if len(st.session_state.historico_numeros) == 0 or st.session_state.historico_numeros[-1] != numero:
        st.session_state.historico_numeros.append(numero)
        try:
            joblib.dump(list(st.session_state.historico_numeros), HIST_PATH_NUMS)
        except:
            pass

# =========================
# FUNÇÃO DE EXTRAÇÃO DE FEATURES
# =========================
def extrair_features_num(janela_numeros):
    feats = []
    L = len(janela_numeros)
    window = st.session_state.tamanho_janela

    # --- Sequência da janela (padding à esquerda) ---
    pad = [0]*(max(0, window - L))
    seq = pad + list(janela_numeros)[-window:]
    feats.extend(seq)

    # --- Último número ---
    if L > 0:
        last = janela_numeros[-1]
        # Paridade
        feats.append(1 if last % 2 == 0 else 0)
        # Cor
        if last == 0:
            feats.append(2)  # verde
        else:
            feats.append(1 if last in RED_SET else 0)
        # Dúzia
        if last == 0:
            feats.append(0)
        elif last <= 12:
            feats.append(1)
        elif last <= 24:
            feats.append(2)
        else:
            feats.append(3)
        # Coluna
        feats.append(0 if last == 0 else ((last - 1) % 3) + 1)
    else:
        feats.extend([0,0,0,0])

    # --- Distância normalizada desde o último zero ---
    last_zero_dist = next((L-i for i,n in enumerate(reversed(janela_numeros)) if n==0), L)
    feats.append(last_zero_dist / max(1,L))

    # --- Vizinhos físicos na roda ---
    if L>0:
        last_idx = IDX.get(janela_numeros[-1],0)
        for offset in [-2,-1,1,2]:
            neighbor_idx = (last_idx + offset) % 37
            feats.append(WHEEL[neighbor_idx])
    else:
        feats.extend([0,0,0,0])

    # --- Frequência relativa dos últimos N ---
    cnt_nums = Counter(janela_numeros)
    for n in range(37):
        feats.append(cnt_nums.get(n,0) / max(1,L))

    # --- Gap (tempo desde última ocorrência) ---
    for n in range(37):
        if n in janela_numeros:
            gap = L - 1 - max(i for i,v in enumerate(janela_numeros) if v==n)
        else:
            gap = L
        feats.append(gap / max(1,L))

    return np.array(feats, dtype=float)
# =========================
# CAPTURA DE NÚMERO PELA API
# =========================
def capturar_numero_api():
    try:
        r = requests.get(API_URL, timeout=4)
        r.raise_for_status()
        data = r.json()
        candidates = []

        if isinstance(data, dict):
            # chaves comuns
            for k in ["winningNumber","number","result","value","outcome"]:
                v = data.get(k)
                if isinstance(v, int) and 0 <= v <= 36:
                    candidates.append(v)
                elif isinstance(v, str) and v.isdigit():
                    vv = int(v)
                    if 0 <= vv <= 36:
                        candidates.append(vv)

            # varredura profunda
            def deep_search(d):
                if isinstance(d, dict):
                    for _, v in d.items():
                        deep_search(v)
                elif isinstance(d, list):
                    for item in d:
                        deep_search(item)
                else:
                    if isinstance(d, int) and 0 <= d <= 36:
                        candidates.append(d)
                    elif isinstance(d, str) and d.isdigit():
                        vv = int(d)
                        if 0 <= vv <= 36:
                            candidates.append(vv)
            deep_search(data)

        for c in candidates:
            if isinstance(c, int) and 0 <= c <= 36:
                return c
    except Exception as e:
        st.warning(f"Erro captura API: {e}")
    return None

# =========================
# TREINAMENTO DO MODELO TOP-5 NÚMEROS
# =========================
def treinar_modelo_num():
    nums = list(st.session_state.historico_numeros)
    n = len(nums)
    window = st.session_state.tamanho_janela
    if n < window + 5:
        return False

    X, y = [], []
    for i in range(n - window):
        janela = nums[i:i+window]
        alvo = nums[i+window]  # próximo número
        feats = extrair_features_num(janela)
        X.append(feats)
        y.append(alvo)

    if len(X) < 10 or len(set(y)) < 2:
        return False

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=int)

    modelo = CatBoostClassifier(
        iterations=400, depth=7, learning_rate=0.07, loss_function='MultiClass', verbose=False
    )
    try:
        modelo.fit(X, y)
        st.session_state.modelo_num = modelo
        try: joblib.dump(modelo, MODELO_NUM_PATH)
        except: pass
        return True
    except Exception as e:
        st.warning(f"Erro ao treinar (num): {e}")
        return False

# =========================
# PREVISÃO TOP-5 NÚMEROS (MAIS PROVÁVEIS)
# =========================
def prever_top5():
    modelo = st.session_state.modelo_num
    if modelo is None or len(st.session_state.historico_numeros) < st.session_state.tamanho_janela:
        return []
    janela = list(st.session_state.historico_numeros)[-st.session_state.tamanho_janela:]
    feats = extrair_features_num(janela).reshape(1,-1)
    try:
        probs = modelo.predict_proba(feats)[0]
        classes = list(modelo.classes_)
        idxs = np.argsort(probs)[-5:][::-1]
        top5_prov = [(int(classes[i]), float(probs[i])) for i in idxs]
        return top5_prov
    except Exception as e:
        st.error(f"⚠️ Erro prever top5: {e}")
        st.exception(e)
        return []

# =========================
# SESSION STATE INIT PARA NÚMEROS
# =========================
if "modelo_num" not in st.session_state:
    st.session_state.modelo_num = joblib.load(MODELO_NUM_PATH) if MODELO_NUM_PATH.exists() else None

if "acertos_num" not in st.session_state: st.session_state.acertos_num = 0
if "total_num" not in st.session_state: st.session_state.total_num = 0
if "ultima_entrada_num" not in st.session_state: st.session_state.ultima_entrada_num = None
if "_alerta_enviado_num" not in st.session_state: st.session_state._alerta_enviado_num = False

# =========================
# FUNÇÃO DE ENVIO TELEGRAM
# =========================
def enviar_telegram_num(msg:str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

# =========================
# FLUXO PRINCIPAL AUTOMÁTICO
# =========================
numero = capturar_numero_api()
if numero is not None and (st.session_state.ultimo_numero_salvo is None or numero != st.session_state.ultimo_numero_salvo):
    st.session_state.ultimo_numero_salvo = numero
    salvar_historico(numero)

    if st.session_state.ultima_entrada_num:
        classes_prev = [c for c,_ in st.session_state.ultima_entrada_num.get("classes",[])]
        acerto = numero in classes_prev
        if acerto:
            st.session_state.acertos_num += 1
            enviar_telegram_num(f"✅ Saiu {numero} — ACERTO! (Top-5 Números)")
        else:
            enviar_telegram_num(f"❌ Saiu {numero} — ERRO. (Top-5 Números)")
        st.session_state.total_num += 1

    if len(st.session_state.historico_numeros) >= st.session_state.tamanho_janela + 5:
        treinar_modelo_num()

    st.session_state._alerta_enviado_num = False

    top5_prov = prever_top5()
    if top5_prov and not st.session_state._alerta_enviado_num:
        chave = "_".join(str(c) for c,_ in top5_prov)
        reenvio_forcado = False

        if st.session_state.ultima_entrada_num and chave == st.session_state.ultima_entrada_num.get("chave"):
            st.session_state.contador_sem_envio += 1
            if st.session_state.contador_sem_envio >= 3:
                reenvio_forcado = True
        else:
            st.session_state.contador_sem_envio = 0

        if (not st.session_state.ultima_entrada_num) or reenvio_forcado or chave != st.session_state.ultima_entrada_num.get("chave"):
            entrada_obj = {"classes": top5_prov, "chave": chave}
            txt = "🔮 <b>Top-5 Números Prováveis</b>: " + ", ".join(f"{c} ({p*100:.1f}%)" for c,p in top5_prov)
            enviar_telegram_num(txt)
            st.session_state.ultima_entrada_num = entrada_obj
            st.session_state._alerta_enviado_num = True
            st.session_state.contador_sem_envio = 0

# =========================
# UI PARA TOP-5 NÚMEROS
# =========================
st.subheader("📊 Estatísticas Top-5 Números")
st.write(f"Acertos: {st.session_state.acertos_num} / {st.session_state.total_num}")

st.subheader("🔮 Última entrada Top-5 Números")
if st.session_state.ultima_entrada_num:
    classes = st.session_state.ultima_entrada_num.get("classes", [])
    st.write(", ".join(f"{c} ({p*100:.1f}%)" for c,p in classes))
else:
    st.write("Nenhuma entrada enviada ainda.")

st.subheader("📌 Previsão Top-5 Números mais prováveis")
top5_display = prever_top5()
if top5_display:
    st.write(", ".join(f"{c} ({p*100:.1f}%)" for c,p in top5_display))
else:
    st.write("Modelo não treinado ou poucos dados.")
