import streamlit as st
import requests
import joblib
import time
import logging
from streamlit_autorefresh import st_autorefresh
from collections import deque, Counter
from pathlib import Path
from alertas import enviar_previsao, enviar_resultado, get_coluna

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
HIST_PATH_NUMS = Path("historico_numeros.pkl")
MAX_HISTORICO = 120

# =========================
# SESSION STATE INIT
# =========================
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=MAX_HISTORICO)
    if HIST_PATH_NUMS.exists():
        hist = joblib.load(HIST_PATH_NUMS)
        st.session_state.historico.extend(hist)

if "modelo_coluna" not in st.session_state:
    try:
        st.session_state.modelo_coluna = joblib.load("modelo_coluna.pkl")
    except:
        st.session_state.modelo_coluna = None

if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = None

if "ultima_previsao_enviada" not in st.session_state:
    st.session_state.ultima_previsao_enviada = None

if "contador_sem_envio" not in st.session_state:
    st.session_state.contador_sem_envio = 0

if "colunas_acertadas" not in st.session_state:
    st.session_state.colunas_acertadas = 0

if "rodada_atual" not in st.session_state:
    st.session_state.rodada_atual = None

if "previsao_enviada" not in st.session_state:
    st.session_state.previsao_enviada = False

# =========================
# FUNÇÕES AUXILIARES
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

def preparar_features(historico):
    ultimos = list(historico)[-10:]
    return [h["number"] for h in ultimos] + [0] * (10 - len(ultimos))

def tentar_treinar():
    if st.session_state.modelo_coluna and len(st.session_state.historico) >= 20:
        X = []
        y = []
        numeros = [h["number"] for h in st.session_state.historico]
        for i in range(10, len(numeros)):
            janela = numeros[i-10:i]
            X.append(janela)
            y.append(get_coluna(numeros[i]))
        st.session_state.modelo_coluna.fit(X, y)

def prever_coluna_final(historico, modelo):
    # --- IA ---
    try:
        X_entrada = preparar_features(historico)
        coluna_ia = modelo.predict([X_entrada])[0]
    except:
        coluna_ia = None

    # --- Tendência ---
    ultimos = [h["number"] for h in historico][-20:]
    contagem = Counter(get_coluna(n) for n in ultimos)
    coluna_tendencia = contagem.most_common(1)[0][0] if contagem else None

    # --- Alternância ---
    if len(historico) >= 3:
        c1, c2, c3 = get_coluna(historico[-1]["number"]), get_coluna(historico[-2]["number"]), get_coluna(historico[-3]["number"])
        if c1 != c2 and c2 == c3:
            coluna_alternancia = c1
        else:
            coluna_alternancia = c1
    else:
        coluna_alternancia = None

    # --- Votação ---
    previsoes = [coluna_ia, coluna_tendencia, coluna_alternancia]
    previsoes = [p for p in previsoes if p is not None]

    if not previsoes:
        return None

    contagem_final = Counter(previsoes).most_common()
    mais_votado, votos = contagem_final[0]

    # Desempate → prioridade IA > tendência > alternância
    if len(contagem_final) > 1 and contagem_final[0][1] == contagem_final[1][1]:
        if coluna_ia in previsoes:
            return coluna_ia
        elif coluna_tendencia in previsoes:
            return coluna_tendencia
        else:
            return coluna_alternancia

    return mais_votado

# =========================
# STREAMLIT APP
# =========================
st.title("IA Roleta XXXtreme — Previsão de Coluna 🎯")

resultado = fetch_latest_result()
ultimo_ts = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado and resultado["timestamp"] != ultimo_ts:
    numero_atual = resultado["number"]

    # reset flags se nova rodada
    if numero_atual != st.session_state.rodada_atual:
        st.session_state.rodada_atual = numero_atual
        st.session_state.previsao_enviada = False

    # adicionar ao histórico
    st.session_state.historico.append(resultado)
    joblib.dump(list(st.session_state.historico), HIST_PATH_NUMS)

    # treinar modelo
    tentar_treinar()

    # previsão coluna
    prev_coluna = prever_coluna_final(st.session_state.historico, st.session_state.modelo_coluna)
    st.session_state.coluna_prevista = prev_coluna

    # enviar alerta apenas uma vez
    if not st.session_state.previsao_enviada and prev_coluna is not None:
        if prev_coluna != st.session_state.ultima_previsao_enviada or st.session_state.contador_sem_envio >= 3:
            enviar_previsao(prev_coluna)
            st.session_state.ultima_previsao_enviada = prev_coluna
            st.session_state.contador_sem_envio = 0
            st.session_state.previsao_enviada = True
        else:
            st.session_state.contador_sem_envio += 1

    # conferir resultado e enviar GREEN/RED
    acertou = get_coluna(numero_atual) == prev_coluna
    time.sleep(4)
    enviar_resultado(numero_atual, acertou)
    if acertou:
        st.session_state.colunas_acertadas += 1

# interface
st.subheader("🔁 Últimos 10 Números")
st.write([h["number"] for h in st.session_state.historico][-10:])

st.subheader("🔮 Previsão de Coluna")
st.write(f"🎯 Coluna prevista: {st.session_state.coluna_prevista}")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico)
if total > 0:
    taxa = st.session_state.colunas_acertadas / total * 100
    st.success(f"✅ Acertos de coluna: {st.session_state.colunas_acertadas}/{total} ({taxa:.2f}%)")
else:
    st.info("🔎 Aguardando mais resultados para avaliar desempenho.")




# Atualiza a cada 3 segundos (3000 ms)
st_autorefresh(interval=3000, key="refresh_coluna")
