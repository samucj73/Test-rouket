import streamlit as st
import requests
import joblib
from collections import Counter, deque
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import SGDClassifier
import numpy as np
import time
import csv
import os

# ==========================
# ======== v3.5 ===========
# ==========================

# === CONFIGURAÇÕES FIXAS ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_incremental_v35.pkl"
HISTORICO_PATH = "historico_v35.pkl"
CSV_LOG_PATH = "historico_feedback_v35.csv"

# === CONFIGURAÇÕES ADMIN (barra lateral) ===
st.set_page_config(layout="wide", page_title="IA Elite Master - Roleta v3.5")
st.sidebar.title("⚙️ Painel Administrativo - Elite Master")

MODO_AGRESSIVO = st.sidebar.toggle("Modo Agressivo (mais alertas)", value=False)
FEATURE_LEN = st.sidebar.slider("Tamanho da janela de features", 10, 25, 14)
HIST_MAXLEN = st.sidebar.slider("Tamanho máximo do histórico", 500, 3000, 1500)
LIMIAR_BASE_PADRAO = st.sidebar.number_input("Limiar Base (Padrão)", 0.4, 0.9, 0.60, step=0.01)
LIMIAR_BASE_AGRESSIVO = st.sidebar.number_input("Limiar Base (Agressivo)", 0.4, 0.9, 0.55, step=0.01)
PESO_TERMINAL = st.sidebar.slider("Peso Terminal", 1.0, 3.0, 1.2, step=0.1)
PESO_VIZINHO = st.sidebar.slider("Peso Vizinho", 0.2, 2.0, 0.5, step=0.1)
MOVING_AVG_WINDOW = st.sidebar.slider("Janela da média móvel (alertas)", 5, 25, 10)

st.sidebar.markdown("---")
st.sidebar.info(f"📢 Modo atual: {'Agressivo' if MODO_AGRESSIVO else 'Padrão'}")

# ==========================
# === INICIALIZAÇÃO UI ====
# ==========================
st.title("🎯 Estratégia IA Inteligente - v3.5 (Elite Master)")

# Histórico
if os.path.exists(HISTORICO_PATH):
    historico_salvo = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(historico_salvo, maxlen=HIST_MAXLEN)
else:
    st.session_state.historico = deque(maxlen=HIST_MAXLEN)

# Estado padrão
defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": None,  # Agora é dict
    "alertas_enviados": set(),
    "feedbacks_processados": set(),
    "greens": 0,
    "reds": 0,
    "greens_terminal": 0,
    "greens_vizinho": 0,
    "historico_probs": deque(maxlen=500),
    "alert_probs": [],
    "nova_entrada": False,
    "tempo_alerta": 0,
    "total_alertas": 0,
    "terminais_quentes": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "greens_probs" not in st.session_state:
    st.session_state.greens_probs = []

# Auto-refresh
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=2500, key="refresh")

# Ordem da roleta
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

# ==========================
# === FUNÇÕES UTILITÁRIAS ===
# ==========================
def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-2, 3)]

def expandir_com_vizinhos(nums):
    entrada = set()
    for n in nums:
        entrada.update(get_vizinhos(n))
    return sorted(entrada)

def extrair_features(janela):
    f = {f"num_{i}": int(n) for i, n in enumerate(janela)}
    f["media"] = float(sum(janela) / len(janela))
    f["ultimo"] = int(janela[-1])
    moda = Counter(janela).most_common(1)
    f["moda"] = int(moda[0][0]) if moda else int(janela[-1])
    f["qtd_pares"] = int(sum(1 for n in janela if n % 2 == 0))
    f["qtd_baixos"] = int(sum(1 for n in janela if n <= 18))
    unidades = [n % 10 for n in janela]
    for d in range(10):
        f[f"unid_{d}"] = int(unidades.count(d))
    return f

def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
    except Exception:
        pass

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def log_csv(row):
    header = ["timestamp", "evento", "numero", "tipo", "prob_alerta", "limiar", "entrada"]
    write_header = not os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if write_header: w.writerow(header)
        w.writerow(row)

# ==========================
# === CAPTURA DA API ===
# ==========================
try:
    r = requests.get(API_URL, timeout=5)
    if r.status_code == 200:
        d = r.json()
        numero = int(d["data"]["result"]["outcome"]["number"])
        ts = d["data"]["settledAt"]
        if ts != st.session_state.ultimo_timestamp:
            st.session_state.historico.append(numero)
            st.session_state.ultimo_timestamp = ts
            joblib.dump(list(st.session_state.historico), HISTORICO_PATH)
            st.success(f"🎯 Novo número: {numero}")
except Exception:
    pass

# ==========================
# === TREINAMENTO INCREMENTAL ===
# ==========================
modelo = carregar_modelo()
hist = list(st.session_state.historico)

if len(hist) >= FEATURE_LEN + 1:
    X, y, w = [], [], []
    for i in range(len(hist) - FEATURE_LEN):
        janela = hist[i:i + FEATURE_LEN]
        target = hist[i + FEATURE_LEN]
        u = [n % 10 for n in janela]
        dom = [t for t, _ in Counter(u).most_common(2)]
        entrada_p = [n for n in range(37) if n % 10 in dom]
        entrada_v = expandir_com_vizinhos(entrada_p)
        X.append(extrair_features(janela))
        y_val = 1 if target in entrada_v else 0
        peso = PESO_TERMINAL if target in entrada_p else PESO_VIZINHO if target in entrada_v else 1.0
        y.append(y_val); w.append(peso)
    df = pd.DataFrame(X).fillna(0)
    y_arr, w_arr = np.array(y), np.array(w)
    try:
        modelo.partial_fit(df, y_arr, classes=[0, 1], sample_weight=w_arr)
    except Exception:
        modelo.fit(df, y_arr, sample_weight=w_arr)
    salvar_modelo(modelo)

# ==========================
# === PREVISÃO + ALERTA ===
# ==========================
LIMIAR_BASE = LIMIAR_BASE_AGRESSIVO if MODO_AGRESSIVO else LIMIAR_BASE_PADRAO
limiar_adaptado, media_movel_alerts = LIMIAR_BASE, LIMIAR_BASE

if len(hist) >= FEATURE_LEN:
    Xp = pd.DataFrame([extrair_features(hist[-FEATURE_LEN:])]).fillna(0)
    try:
        prob = modelo.predict_proba(Xp)[0][1]
    except Exception:
        prob = 0.0
    st.session_state.historico_probs.append(prob)

    # Ajuste dinâmico de limiar
    total_fb = st.session_state.greens + st.session_state.reds
    prop_red = (st.session_state.reds / total_fb) if total_fb > 0 else 0
    ajuste = min(0.09, prop_red * 0.12)
    limiar_adaptado = LIMIAR_BASE + ajuste
    if len(st.session_state.alert_probs) >= MOVING_AVG_WINDOW:
        media_movel_alerts = float(np.mean(st.session_state.alert_probs[-MOVING_AVG_WINDOW:]))

    cond_alerta = prob > max(limiar_adaptado, media_movel_alerts)

    if cond_alerta and not st.session_state.entrada_atual:
        u = [n % 10 for n in hist[-FEATURE_LEN:]]
        dom = [t for t, _ in Counter(u).most_common(2)]
        entrada_p = [n for n in range(37) if n % 10 in dom]
        entrada_v = expandir_com_vizinhos(entrada_p)

        # Score
        hist_r = hist[-100:]
        freq = Counter(hist_r)
        def score_numero(n):
            bonus = st.session_state.terminais_quentes.get(n % 10, 0) * 0.35
            dist = min(abs(ROULETTE_ORDER.index(n) - ROULETTE_ORDER.index(d)) for d in entrada_p)
            return freq[n] + bonus + (1.8 if n in entrada_p else 0) + (0.7 if dist <= 1 else 0)
        entrada_final = sorted(sorted(entrada_v, key=lambda n: score_numero(n), reverse=True)[:15])

        chave = f"{dom}-{entrada_final}"
        if chave not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave)
            enviar_telegram(" ".join(str(n) for n in entrada_final))
            st.session_state.nova_entrada = True
            st.session_state.tempo_alerta = time.time()
            st.session_state.total_alertas += 1

            # ⚡ guarda índice do próximo número para conferência
            st.session_state.entrada_atual = {
                "entrada": entrada_final,
                "terminais": dom,
                "probabilidade": round(prob,3),
                "index_feedback": len(hist)
            }
            st.session_state.alert_probs.append(prob)
            log_csv([time.time(), "ALERTA", None, None, round(prob,3), round(limiar_adaptado,3), ",".join(map(str,entrada_final))])

# ==========================
# === FEEDBACK (confere apenas próximo número) ===
# ==========================
if st.session_state.entrada_atual:
    ent = st.session_state.entrada_atual["entrada"]
    idx_fb = st.session_state.entrada_atual["index_feedback"]

    if len(st.session_state.historico) > idx_fb:
        numero_sorteado = st.session_state.historico[idx_fb]

        green = numero_sorteado in ent
        st.session_state.feedbacks_processados.add(f"{numero_sorteado}-{tuple(sorted(ent))}")

        if green:
            st.session_state.greens += 1
            dom = st.session_state.entrada_atual.get("terminais", [])
            term = [n for n in range(37) if n % 10 in dom]
            viz = set(v for n in term for v in get_vizinhos(n))
            if numero_sorteado in term:
                st.session_state.greens_terminal += 1
            elif numero_sorteado in viz:
                st.session_state.greens_vizinho += 1
            st.session_state.greens_probs.append(st.session_state.entrada_atual["probabilidade"])
            for t in dom: st.session_state.terminais_quentes[t] = st.session_state.terminais_quentes.get(t,0)+1
        else:
            st.session_state.reds += 1

        enviar_telegram(f"{'✅ GREEN' if green else '❌ RED'} • Saiu {numero_sorteado}")
        st.session_state.entrada_atual = None

# ==========================
# === MÉTRICAS & GRÁFICOS ===
# ==========================
col1,col2,col3,col4,col5 = st.columns(5)
col1.metric("✅ GREENS", st.session_state.greens)
col2.metric("❌ REDS", st.session_state.reds)
tot = st.session_state.greens + st.session_state.reds
col3.metric("🎯 Taxa de Acerto", f"{(st.session_state.greens/tot*100 if tot>0 else 0):.1f}%")
col4.metric("🎯 GREEN Terminal", st.session_state.greens_terminal)
col5.metric("🎯 GREEN Vizinho", st.session_state.greens_vizinho)

# Distribuição Terminal / Vizinho
total_g = st.session_state.greens_terminal + st.session_state.greens_vizinho
if total_g>0:
    pt = st.session_state.greens_terminal/total_g*100
    pv = st.session_state.greens_vizinho/total_g*100
    st.info(f"💡 Distribuição GREEN → Terminal: {pt:.1f}% | Vizinho: {pv:.1f}%")
    fig, ax = plt.subplots(figsize=(4,2))
    ax.bar(["Terminal","Vizinho"],[st.session_state.greens_terminal, st.session_state.greens_vizinho])
    ax.set_title("Distribuição de Acertos GREEN")
    st.pyplot(fig)

# Confiança média
if st.session_state.greens_probs:
    mc = np.mean(st.session_state.greens_probs)
    st.metric("⚡ Confiança média (GREENS)", f"{mc:.3f}")

st.write(f"Total de alertas: {st.session_state.total_alertas}")
st.write(f"Limiar base: {LIMIAR_BASE:.3f} | Limiar adaptado: {limiar_adaptado:.3f} | Média móvel alertas: {np.mean(st.session_state.alert_probs[-MOVING_AVG_WINDOW:]) if st.session_state.alert_probs else 0:.3f}")

# Nova entrada visual
if st.session_state.nova_entrada and time.time()-st.session_state.tempo_alerta<5:
    st.markdown("<h3 style='color:orange'>⚙️ Nova entrada IA ativa!</h3>", unsafe_allow_html=True)

# Últimos números
st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-14:])

# Entrada atual
if st.session_state.entrada_atual:
    st.subheader("📥 Entrada Atual (ordenada)")
    st.write(st.session_state.entrada_atual)

# Histórico de confiança
if st.session_state.historico_probs:
    st.subheader("📈 Confiança da IA (últimas previsões)")
    plt.figure(figsize=(8,2.5))
    plt.plot(list(st.session_state.historico_probs), marker='o')
    plt.title("Evolução da Probabilidade")
    plt.grid(True)
    st.pyplot(plt)
