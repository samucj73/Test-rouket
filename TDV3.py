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
import math

# ==========================
# ======== v4.0 ===========
# ==========================

# === CONFIGURAÇÕES FIXAS ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico_v35.pkl"  # mantém seu arquivo de histórico
CSV_LOG_PATH = "historico_feedback_v35.csv"

# === CONFIGURAÇÕES ADMIN (barra lateral) ===
st.set_page_config(layout="wide", page_title="IA Elite Master - Roleta v4.0 (Combinatória)")
st.sidebar.title("⚙️ Painel Admin - Combinatória (Elite Master)")

# Parâmetros do método combinatório
DECAY_HALFLIFE = st.sidebar.slider("Halflife (em giros) — peso de decaimento", 80, 5_000, 400, step=10)
CANDIDATE_POOL = st.sidebar.slider("Tamanho do pool candidato (top N)", 9, 30, 20)
PENALTY_PROXIMITY = st.sidebar.slider("Penalidade por proximidade física (0-1)", 0.0, 1.0, 0.35, step=0.05)
USE_RECENT_ONLY = st.sidebar.checkbox("Usar todo o histórico salvo (desmarque para somente janela)", value=True)
RECENT_WINDOW = st.sidebar.number_input("Janela recente (se não usar todo histórico)", 50, 10000, 500, step=50)

st.sidebar.markdown("---")
st.sidebar.info("Estratégia: análise combinatória — combina 9 números distintos por rodada")

# ==========================
# === INICIALIZAÇÃO UI ====
# ==========================
st.title("🎯 Estratégia Combinatória - Roleta (v4.0)")

# Histórico
HIST_MAXLEN = 100000
if os.path.exists(HISTORICO_PATH):
    historico_salvo = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(historico_salvo, maxlen=HIST_MAXLEN)
else:
    st.session_state.historico = deque(maxlen=HIST_MAXLEN)

# Estado padrão
defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": None,   # será dict com 'entrada' (list) e 'index_feedback'
    "alertas_enviados": set(),
    "feedbacks_processados": set(),
    "greens": 0,
    "reds": 0,
    "historico_scores": deque(maxlen=500),
    "alert_probs": [],
    "nova_entrada": False,
    "tempo_alerta": 0,
    "total_alertas": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Auto-refresh
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=2500, key="refresh_comb")

# Ordem física da roleta
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-2, 3)]

# Util: distância física mínima na roleta
def distancia_fisica(a, b):
    ia = ROULETTE_ORDER.index(a)
    ib = ROULETTE_ORDER.index(b)
    d = abs(ia - ib)
    return min(d, len(ROULETTE_ORDER) - d)

# Enviar telegram simples (mensagem de texto)
def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
    except Exception:
        pass

def log_csv(row):
    header = ["timestamp", "evento", "numero", "tipo", "metric_score", "entrada"]
    write_header = not os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if write_header: w.writerow(header)
        w.writerow(row)

# ==========================
# === FUNÇÕES COMBINATÓRIAS ===
# ==========================
def exponential_weights(n, halflife):
    # retorna lista de pesos para n elementos, mais recente tem maior peso (último index = n-1)
    # weight for age a (0 = oldest, n-1 = newest): w = 0.5^(age/halflife)
    ages = np.arange(n-1, -1, -1)  # newest age 0? invert: we want newest highest -> age = 0 for newest
    ages = np.arange(n-1, -1, -1)  # but we'll compute as age_from_end
    # Let's compute age_from_end: newest has age 0
    age_from_end = np.arange(n)[::-1]
    weights = 0.5 ** (age_from_end / halflife)
    return weights / weights.sum()

def build_transition_counts(hist):
    # Retorna dict: trans[a][b] = count de a->b
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(hist)-1):
        a = hist[i]
        b = hist[i+1]
        trans[a][b] += 1
    return trans

def gerar_scores(hist):
    # hist: lista de ints (0-36)
    if len(hist) == 0:
        return {n: 1.0 for n in range(37)}  # sem dados, scores iguais

    # Decide janela: se usuario optou por usar todo historico, usa tudo; senao usa RECENT_WINDOW
    if USE_RECENT_ONLY:
        janela = list(hist)
    else:
        janela = list(hist[-int(RECENT_WINDOW):])

    n = len(janela)
    weights = exponential_weights(n, DECAY_HALFLIFE)  # aligned with janela oldest->newest mapping
    # frequencies ponderadas
    freq = defaultdict(float)
    for i, num in enumerate(janela):
        freq[num] += weights[i]

    # normalize frequency scores to [0,1]
    maxf = max(freq.values()) if freq else 1.0
    freq_score = {n: (freq.get(n,0.0) / maxf) for n in range(37)}

    # transitions (para condicional P(n | last))
    trans = build_transition_counts(janela)
    last = janela[-1]
    # conditional probabilities from last
    cond = {}
    denom = sum(trans[last].values()) if last in trans else 0
    if denom > 0:
        for n in range(37):
            cond[n] = trans[last].get(n, 0) / denom
    else:
        # sem transição conhecida, usa frequência normalizada
        cond = {n: freq_score.get(n,0.0) for n in range(37)}

    # Bônus vizinhança: números na vizinhança física do último número ganham pequeno bônus
    vizinhos_last = set(get_vizinhos(last))

    # Combina para gerar score final
    scores = {}
    for n in range(37):
        s_freq = freq_score.get(n, 0.0)
        s_cond = cond.get(n, 0.0)
        bonus_viz = 0.12 if n in vizinhos_last else 0.0
        # combinação linear (pesos ajustáveis)
        score = 0.6 * s_freq + 0.35 * s_cond + bonus_viz
        scores[n] = float(score)

    # normalize scores into [0,1]
    arr = np.array(list(scores.values()))
    if arr.max() > arr.min():
        arrn = (arr - arr.min()) / (arr.max() - arr.min())
    else:
        arrn = arr
    for i, n in enumerate(scores.keys()):
        scores[n] = float(arrn[i])

    return scores

def selecionar_combinação(scores, k=9, pool_top=CANDIDATE_POOL, penalty_prox=PENALTY_PROXIMITY):
    # Seleciona uma combinação de k números distintos a partir dos scores fornecidos
    # 1) escolhe top pool_top candidatos por score
    candidates = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:pool_top]
    chosen = []
    chosen_set = set()

    # seleção gulosa com penalidade por proximidade física (para diversificar)
    for _ in range(min(k, len(candidates))):
        best = None
        best_val = -1e9
        for c in candidates:
            if c in chosen_set:
                continue
            base = scores[c]
            # penalidade por proximidade com os já escolhidos
            if chosen:
                prox_pen = 0.0
                for ch in chosen:
                    d = distancia_fisica(c, ch)
                    # closer -> maior penalidade (usamos inverso da distância)
                    prox_pen += (1.0 / (1 + d))
                prox_pen = prox_pen / len(chosen)
                val = base - penalty_prox * prox_pen
            else:
                val = base
            if val > best_val:
                best_val = val
                best = c
        if best is None:
            break
        chosen.append(best)
        chosen_set.add(best)

    # se faltou por algum motivo, preenche com próximos melhores sem penalidade
    if len(chosen) < k:
        for c in candidates:
            if c not in chosen_set:
                chosen.append(c); chosen_set.add(c)
            if len(chosen) >= k:
                break

    # garantia de tamanho k: complementa por números que nunca saíram (se necessário)
    if len(chosen) < k:
        for n in range(37):
            if n not in chosen_set:
                chosen.append(n); chosen_set.add(n)
            if len(chosen) >= k:
                break

    # ordena por score decrescente para consistência
    chosen = sorted(chosen, key=lambda x: scores.get(x,0.0), reverse=True)
    return chosen

def gerar_combinacao_9_numeros(hist):
    scores = gerar_scores(hist)
    comb = selecionar_combinação(scores, k=9)
    # métricas: freq média ponderada dos 9 e soma dos scores normalizada
    media_scores = float(np.mean([scores.get(n,0.0) for n in comb]))
    soma_scores = float(sum([scores.get(n,0.0) for n in comb]))
    # estimativa simples de "probabilidade combinada" (heurística)
    estimativa = float(soma_scores / (sum(scores.values()) if sum(scores.values())>0 else 1.0))
    return {
        "comb": comb,
        "media_scores": media_scores,
        "soma_scores": soma_scores,
        "estimativa": estimativa,
        "scores_detail": {n: scores.get(n,0.0) for n in comb}
    }

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
# === GERAÇÃO DA PREVISÃO (a cada novo número) ===
# ==========================
hist = list(st.session_state.historico)
if hist:
    previsao = gerar_combinacao_9_numeros(hist)
    entrada_final = previsao["comb"]
    # Chave para evitar alertas duplicados idênticos
    chave = ",".join(map(str, entrada_final))
    if chave not in st.session_state.alertas_enviados:
        st.session_state.alertas_enviados.add(chave)
        # Mensagem compacta para Telegram (combinação + métricas)
        msg = (f"🎯 PREVISÃO 9 NÚMEROS\n"
               f"{', '.join(map(str, entrada_final))}\n"
               f"⭐ Média scores: {previsao['media_scores']:.3f} | Estimativa: {previsao['estimativa']:.4f}")
        enviar_telegram(msg)
        st.session_state.nova_entrada = True
        st.session_state.tempo_alerta = time.time()
        st.session_state.total_alertas += 1
        # Guarda entrada atual para feedback (o index_feedback aponta para o índice do próximo número)
        st.session_state.entrada_atual = {
            "entrada": entrada_final,
            "scores": previsao["scores_detail"],
            "index_feedback": len(hist)
        }
        log_csv([time.time(), "ALERTA_COMBINATORIA", None, None, round(previsao["soma_scores"],4), ",".join(map(str,entrada_final))])
        st.session_state.historico_scores.append(previsao["media_scores"])

# ==========================
# === FEEDBACK (confere apenas o próximo número) ===
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
        else:
            st.session_state.reds += 1
        enviar_telegram(f"{'✅ GREEN' if green else '❌ RED'} • Saiu {numero_sorteado}")
        st.session_state.entrada_atual = None

# ==========================
# === MÉTRICAS & GRÁFICOS ===
# ==========================
col1,col2,col3,col4 = st.columns(4)
col1.metric("✅ GREENS", st.session_state.greens)
col2.metric("❌ REDS", st.session_state.reds)
tot = st.session_state.greens + st.session_state.reds
col3.metric("🎯 Taxa de Acerto", f"{(st.session_state.greens/tot*100 if tot>0 else 0):.1f}%")
col4.metric("🔁 Total Alertas", st.session_state.total_alertas)

# Últimos números
st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-14:])

# Entrada atual (se existir)
if st.session_state.entrada_atual:
    st.subheader("📥 Entrada Atual (ordenada)")
    st.write(st.session_state.entrada_atual)

# Histórico de scores (visual)
if st.session_state.historico_scores:
    st.subheader("📈 Média de Scores (últimas previsões)")
    fig, ax = plt.subplots(figsize=(8,2.5))
    ax.plot(list(st.session_state.historico_scores), marker='o')
    ax.set_title("Evolução da média de scores")
    ax.grid(True)
    st.pyplot(fig)
