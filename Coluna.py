import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
import logging

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
HIST_PATH = Path("historico_coluna.pkl")
MAX_HISTORICO = 500
JANELA = 12

# =========================
# FUNÇÕES BASE
# =========================
def get_coluna(n):
    if n == 0: return 0
    if n % 3 == 1: return 1
    if n % 3 == 2: return 2
    return 3

def get_duzia(n):
    if n == 0: return 0
    if 1 <= n <= 12: return 1
    if 13 <= n <= 24: return 2
    if 25 <= n <= 36: return 3
    return 0

def get_terminal(n):
    return n % 10 if n != 0 else 0

def extrair_features(seq):
    """Transforma uma sequência de números em features úteis"""
    feats = []
    terminais = [get_terminal(n) for n in seq if n is not None]
    cont_term = Counter(terminais)
    terminal_dominante = cont_term.most_common(1)[0][0] if cont_term else -1

    for n in seq:
        coluna = get_coluna(n)
        duzia = get_duzia(n)
        paridade = n % 2 if n != 0 else -1
        cor = 0
        if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
            cor = 1  # vermelho
        elif n != 0:
            cor = 2  # preto
        terminal = get_terminal(n)
        feats.extend([n, coluna, duzia, paridade, cor, terminal])

    # Frequência relativa da janela
    colunas = [get_coluna(x) for x in seq if x is not None]
    freq_colunas = [colunas.count(1), colunas.count(2), colunas.count(3)]
    feats.extend(freq_colunas)

    # Terminal dominante
    feats.append(terminal_dominante)

    # Tempo desde último zero
    feats.append(len(seq) - seq[::-1].index(0) if 0 in seq else 99)

    return feats

def treinar_modelo_coluna(historico, janela=12):
    X, y = [], []
    hist_list = list(historico)
    for i in range(len(hist_list) - janela):
        janela_numeros = hist_list[i:i+janela]
        alvo = get_coluna(hist_list[i+janela])
        X.append(extrair_features(janela_numeros))
        y.append(alvo)

    if len(X) < 50:  # precisa de histórico mínimo
        return None

    modelo = RandomForestClassifier(
        n_estimators=800,
        max_depth=12,
        random_state=42,
        class_weight="balanced_subsample"
    )
    modelo.fit(X, y)
    return modelo

# =========================
# API
# =========================
def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =========================
# STREAMLIT
# =========================
st.set_page_config("Previsão Colunas + Terminais", layout="wide")
st_autorefresh(interval=5000, key="refresh")

# Estado
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=MAX_HISTORICO)
    if HIST_PATH.exists():
        hist = joblib.load(HIST_PATH)
        st.session_state.historico.extend(hist)

if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = None

# Busca novo resultado
novo = fetch_latest_result()
if novo and novo["number"] is not None:
    if not st.session_state.historico or st.session_state.historico[-1] != novo["number"]:
        st.session_state.historico.append(novo["number"])
        joblib.dump(list(st.session_state.historico), HIST_PATH)

# Treina se possível
if len(st.session_state.historico) > 50:
    modelo = treinar_modelo_coluna(st.session_state.historico, JANELA)
    st.session_state.modelo_coluna = modelo

# Previsão
st.title("🎲 Previsão de Colunas (com Terminais Dominantes)")
if st.session_state.modelo_coluna and len(st.session_state.historico) >= JANELA:
    ultimos = list(st.session_state.historico)[-JANELA:]
    feats = np.array(extrair_features(ultimos)).reshape(1, -1)
    probs = st.session_state.modelo_coluna.predict_proba(feats)[0]

    colunas = [1, 2, 3]
    previsoes = sorted(zip(colunas, probs), key=lambda x: x[1], reverse=True)

    st.subheader("Previsões:")
    for col, p in previsoes:
        st.write(f"➡️ Coluna {col} → {p*100:.1f}%")

# Histórico
st.subheader("Últimos números")
st.write(list(st.session_state.historico)[-20:])
