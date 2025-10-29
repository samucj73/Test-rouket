# v5.0 - Estratégia Combinatória Pura (9 números)
import streamlit as st
import requests
import joblib
from collections import defaultdict, Counter, deque
import itertools
import numpy as np
import time
import csv
import os

# ==========================
# ======== v5.0 ===========
# ==========================

# CONFIGURAÇÕES FIXAS
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico_v35.pkl"
CSV_LOG_PATH = "historico_feedback_v35.csv"

# UI / parâmetros
st.set_page_config(layout="wide", page_title="IA Elite Master - Combinatória v5.0")
st.title("🎯 Estratégia Combinatória Pura — 9 Números (v5.0)")

st.sidebar.title("⚙️ Parâmetros Combinatória")
DECAY_HALFLIFE = st.sidebar.slider("Halflife (giros) - peso de decaimento", 20, 2000, 400, step=10)
TOP_N = st.sidebar.slider("Pool candidato (top N) — cuidado: C(N,9) cresce rápido", 9, 24, 20, step=1)
PENALTY_PROXIMITY = st.sidebar.slider("Penalidade por proximidade física (0-1)", 0.0, 1.0, 0.3, step=0.05)
BONUS_DIVERSITY = st.sidebar.slider("Bônus por diversidade física (0-1)", 0.0, 1.0, 0.35, step=0.05)
USE_FULL_HISTORY = st.sidebar.checkbox("Usar todo histórico salvo (marque = sim)", value=True)
RECENT_WINDOW = st.sidebar.number_input("Janela recente (se NÃO usar todo histórico)", 50, 10000, 500, step=50)
MAX_COMBO_LOOP = 250_000  # segurança: se combos > isto, não executa exaustivo automaticamente

st.sidebar.markdown("---")
st.sidebar.info("Aumente TOP_N com cuidado — combinações crescem rápido.")

# inicializa histórico
HIST_MAXLEN = 200000
if os.path.exists(HISTORICO_PATH):
    arr = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(arr, maxlen=HIST_MAXLEN)
else:
    st.session_state.historico = deque(maxlen=HIST_MAXLEN)

# estado
defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": None,          # dict: {'comb', 'scores', 'index_feedback', 'meta'}
    "alertas_enviados": set(),
    "feedbacks_processados": set(),
    "greens": 0,
    "reds": 0,
    "historico_comb_scores": deque(maxlen=500),
    "last_conferencia": None,
    "total_alertas": 0
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# auto refresh (para rodar em ambiente Streamlit)
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=2500, key="autorefr_v50")

# ordem física da roleta (mesma que você usava)
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

def distancia_fisica(a, b):
    ia = ROULETTE_ORDER.index(a)
    ib = ROULETTE_ORDER.index(b)
    d = abs(ia - ib)
    return min(d, len(ROULETTE_ORDER) - d)

def get_vizinhos(n):
    idx = ROULETTE_ORDER.index(n)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-2, 3)]

def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": msg})
    except Exception:
        pass

def log_csv(row):
    header = ["timestamp", "evento", "numero", "tipo", "metric", "entrada"]
    write_header = not os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if write_header: w.writerow(header)
        w.writerow(row)

# --- pesos exponenciais (mais peso para mais recentes)
def exponential_weights(n, halflife):
    if n <= 0:
        return np.array([])
    # age_from_end: newest index has age 0
    ages = np.arange(n)[::-1]
    w = 0.5 ** (ages / halflife)
    return w / w.sum()

# --- construir transições simples (pares consecutivos)
def build_transitions(hist):
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(hist)-1):
        a = hist[i]; b = hist[i+1]
        trans[a][b] += 1
    return trans

# --- gerar score por número (0..36) baseado em frequência ponderada + condicional + vizinhança
def gerar_scores_numeros(hist):
    if len(hist) == 0:
        return {n: 1.0 for n in range(37)}
    janela = list(hist) if USE_FULL_HISTORY else list(hist[-int(RECENT_WINDOW):])
    n = len(janela)
    w = exponential_weights(n, DECAY_HALFLIFE)

    freq = defaultdict(float)
    for i, num in enumerate(janela):
        freq[num] += w[i]
    maxf = max(freq.values()) if freq else 1.0
    freq_score = {num: (freq.get(num, 0.0) / maxf) for num in range(37)}

    trans = build_transitions(janela)
    last = janela[-1]
    denom = sum(trans[last].values()) if last in trans else 0
    cond = {}
    if denom > 0:
        for num in range(37):
            cond[num] = trans[last].get(num, 0) / denom
    else:
        cond = {num: freq_score.get(num, 0.0) for num in range(37)}

    vizinhos_last = set(get_vizinhos(last))

    # combinação linear (pode ajustar pesos se quiser)
    scores = {}
    for num in range(37):
        s = 0.6 * freq_score.get(num, 0.0) + 0.35 * cond.get(num, 0.0) + (0.12 if num in vizinhos_last else 0.0)
        scores[num] = float(s)

    # normalizar 0..1
    arr = np.array(list(scores.values()))
    if arr.max() > arr.min():
        arrn = (arr - arr.min()) / (arr.max() - arr.min())
    else:
        arrn = arr
    return {n: float(arrn[i]) for i, n in enumerate(scores.keys())}

# --- score da combinação: soma(scores individuais) + bônus de diversidade física
def score_combinacao(comb, scores):
    s_sum = sum(scores[n] for n in comb)
    # média das distâncias físicas entre cada par (quanto maior, mais diverso)
    pairs = list(itertools.combinations(comb, 2))
    if not pairs:
        avg_dist = 0.0
    else:
        d_sum = sum(distancia_fisica(a, b) for a, b in pairs)
        avg_dist = d_sum / len(pairs)
        # normaliza avg_dist para 0..1 (roleta tem 37 posições; max distância é floor(37/2)=18)
        avg_dist = avg_dist / 18.0
    bonus = BONUS_DIVERSITY * avg_dist
    # penalidade por proximidade interna (opcional): quanto menor média das distâncias, menor o bônus
    return s_sum + bonus

# --- função principal: gera a melhor combinação de 9 números a partir do top N candidatos
def gerar_melhor_combinacao(hist, k=9, top_n=TOP_N):
    scores = gerar_scores_numeros(hist)
    # ordena por score e pega top_n candidatos
    ordered = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    candidates = ordered[:top_n]

    n_cand = len(candidates)
    total_combos = 0
    # C(top_n, k)
    try:
        total_combos = math.comb(n_cand, k)
    except Exception:
        # fallback
        total_combos = len(list(itertools.combinations(candidates, k)))

    # segurança: se combos maiores que MAX_COMBO_LOOP, não tenta exaustivo
    if total_combos > MAX_COMBO_LOOP:
        # fallback guloso caso muito grande: selecione por heurística gulosa (como antes)
        chosen = []
        chosen_set = set()
        while len(chosen) < k:
            best = None; best_val = -1e9
            for c in candidates:
                if c in chosen_set: continue
                base = scores[c]
                if chosen:
                    prox_pen = np.mean([1.0/(1+distancia_fisica(c,ch)) for ch in chosen])
                    val = base - PENALTY_PROXIMITY * prox_pen
                else:
                    val = base
                if val > best_val:
                    best_val = val; best = c
            if best is None:
                break
            chosen.append(best); chosen_set.add(best)
        chosen = sorted(chosen, key=lambda x:scores[x], reverse=True)
        method = "greedy_fallback"
        combo_score = score_combinacao(chosen, scores)
        return {"comb": chosen, "score": combo_score, "method": method, "scores": scores, "total_combos": total_combos}

    # exaustivo: calcular todas as combinações e escolher a melhor
    best_comb = None
    best_score = -1e12
    for comb in itertools.combinations(candidates, k):
        sc = score_combinacao(comb, scores)
        if sc > best_score:
            best_score = sc
            best_comb = comb

    return {"comb": list(best_comb), "score": float(best_score), "method": "exhaustive", "scores": scores, "total_combos": total_combos}

# ==========================
# === captura novo número ===
# ==========================
novo_num = None
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
            novo_num = numero
            st.success(f"🎯 Novo número recebido: {numero}")
except Exception:
    # não travar app se API cair
    pass

# ==========================
# === CONFERÊNCIA (primeiro, com o novo número) ===
# ==========================
if novo_num is not None and st.session_state.entrada_atual:
    ent = st.session_state.entrada_atual["comb"]
    idx_fb = st.session_state.entrada_atual.get("index_feedback", None)
    # o index_feedback foi salvo como o len(hist) no momento da previsão anterior; 
    # agora len(hist) > idx_fb porque já adicionamos novo_num ao histórico
    # Conferência simples: se novo_num estiver na combinação anterior -> GREEN
    green = novo_num in ent
    # evita duplicatas de processamento (chave com numero + comb)
    chave_fb = f"{novo_num}-{','.join(map(str,sorted(ent)))}"
    if chave_fb not in st.session_state.feedbacks_processados:
        st.session_state.feedbacks_processados.add(chave_fb)
        if green:
            st.session_state.greens += 1
        else:
            st.session_state.reds += 1

        emoji = "🟢" if green else "🔴"
        status = "GREEN" if green else "RED"
        comb_str = ", ".join(map(str, ent))
        msg_conf = (f"{emoji} Resultado Conferido: {status}\n"
                    f"Saiu {novo_num}\n"
                    f"Combinação: {comb_str}")
        enviar_telegram(msg_conf)

        # registrar última conferência para UI
        media_scores = round(np.mean([st.session_state.entrada_atual["scores"].get(n,0.0) for n in ent]), 3)
        estim = round(sum([st.session_state.entrada_atual["scores"].get(n,0.0) for n in ent]) / (sum(st.session_state.entrada_atual["scores"].values()) if sum(st.session_state.entrada_atual["scores"].values())>0 else 1.0), 4)
        st.session_state.last_conferencia = {"green": green, "numero": novo_num, "comb": ent, "media_scores": media_scores, "estimativa": estim, "timestamp": time.time()}

        log_csv([time.time(), "CONFERENCIA", novo_num, status, media_scores, comb_str])

        # limpa entrada atual (para criar nova previsão logo em seguida)
        st.session_state.entrada_atual = None

# ==========================
# === GERAÇÃO NOVA PREVISÃO (após conferência) ===
# ==========================
if novo_num is not None:
    hist_list = list(st.session_state.historico)
    # Gera melhor combinação de 9 números com base em análise combinatória pura
    # CUIDADO: se TOP_N < 9, não há combos válidos
    if TOP_N < 9:
        st.error("TOP_N deve ser >= 9.")
    else:
        # calcula combos possíveis
        import math
        try:
            total_possible = math.comb(TOP_N, 9)
        except Exception:
            total_possible = None

        if total_possible is None or (total_possible is not None and total_possible > MAX_COMBO_LOOP):
            st.warning(f"Pool top {TOP_N} -> combos = {total_possible}. O app vai usar seleção gulosa (mais rápida).")
        result = gerar_melhor_combinacao(hist_list, k=9, top_n=TOP_N)

        comb = result["comb"]
        comb_str = ", ".join(map(str, comb))
        score = result["score"]
        method = result["method"]
        st.session_state.total_alertas += 1

        # evita alertas duplicados
        chave = ",".join(map(str, comb))
        if chave not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave)
            # enviar telegram com a combinação e métricas
            msg = (f"🎯 PREVISÃO 9 NÚMEROS (combinatória)\n"
                   f"{comb_str}\n"
                   f"⭐ Score combinado: {score:.4f} | Método: {method} | PoolTop: {TOP_N}")
            enviar_telegram(msg)

            # salvar entrada atual para futura conferência (o index_feedback aponta para o índice do próximo número)
            st.session_state.entrada_atual = {
                "comb": comb,
                "scores": result["scores"],
                "index_feedback": len(hist_list),  # o próximo número terá índice len(hist_list)
                "meta": {"score": score, "method": method, "top_n": TOP_N, "total_combos": result.get("total_combos", None)}
            }
            st.session_state.historico_comb_scores.append(score)
            log_csv([time.time(), "ALERTA_COMBINATORIA", None, None, round(score, 6), comb_str])

# ==========================
# === INTERFACE VISUAL ===
# ==========================
col1, col2, col3, col4 = st.columns(4)
col1.metric("✅ GREENS", st.session_state.greens)
col2.metric("❌ REDS", st.session_state.reds)
tot = st.session_state.greens + st.session_state.reds
col3.metric("🎯 Taxa de Acerto", f"{(st.session_state.greens / tot * 100 if tot > 0 else 0):.1f}%")
col4.metric("🔁 Total Alertas", st.session_state.total_alertas)

st.markdown("---")

# Painel Resultado Conferido (grande)
if st.session_state.last_conferencia:
    lc = st.session_state.last_conferencia
    color = "#d4f8dc" if lc["green"] else "#ffd6d6"
    emoji = "🟢" if lc["green"] else "🔴"
    status = "GREEN" if lc["green"] else "RED"
    st.markdown(f"""
    <div style="background:{color}; padding:14px; border-radius:8px;">
        <h2 style="margin:0">{emoji} Resultado conferido: <strong style="color:#111">{status}</strong></h2>
        <p style="font-size:18px; margin:6px 0"><strong>Saiu {lc['numero']}</strong> | Combinação: <strong>{', '.join(map(str, lc['comb']))}</strong></p>
        <p style="margin:0">⭐ Média scores: <strong>{lc['media_scores']}</strong> | Estimativa: <strong>{lc['estimativa']}</strong></p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("🔎 Ainda sem resultado conferido — aguarde o próximo sorteio para conferência automática.")

st.markdown("---")

# Exibir previsão atual (aguardando próximo número)
if st.session_state.entrada_atual:
    st.subheader("📩 Previsão atual (aguardando próximo número)")
    st.write(", ".join(map(str, st.session_state.entrada_atual["comb"])))
    st.write(f"Meta: {st.session_state.entrada_atual.get('meta')}")

else:
    st.write("Nenhuma previsão pendente (aguardando nova previsão).")

# Últimos números
st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-20:])

# Histórico de scores
if st.session_state.historico_comb_scores:
    st.subheader("📈 Evolução do score da combinação (últimas previsões)")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 2.5))
    ax.plot(list(st.session_state.historico_comb_scores), marker='o')
    ax.set_title("Score combinado por previsão")
    ax.grid(True)
    st.pyplot(fig)

st.markdown("---")
st.caption("v5.0 — Estratégia combinatória pura (exhaustive dentro do pool top N quando viável).")
