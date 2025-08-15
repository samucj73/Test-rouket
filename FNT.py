import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
import threading
from pathlib import Path
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 10000  # 10s

ROULETTE_ORDER = [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
                  30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
                  29, 7, 28, 12, 35, 3, 26, 0]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "top2_anterior", "contador_sem_alerta", "tipo_entrada_anterior"]:
    if var not in st.session_state:
        if var in ["top2_anterior"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        else:
            st.session_state[var] = 0

# Inicializa listas de feedback
for var in ["padroes_errados", "padroes_certos"]:
    if var not in st.session_state:
        st.session_state[var] = []

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia com Feedback")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=3, max_value=250, value=12)
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=30, max_value=100, value=60) / 100.0

# === FUNÇÕES ===
def enviar_telegram_async(mensagem):
    """Envia mensagem para o Telegram sem travar Streamlit"""
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)
    threading.Thread(target=_send, daemon=True).start()

def numero_para_duzia(num):
    if num == 0:
        return 0
    elif 1 <= num <= 12:
        return 1
    elif 13 <= num <= 24:
        return 2
    else:
        return 3

def prever_duzia_com_feedback(min_match=0.8):
    """
    Prevê a dúzia considerando feedback de padrões errados e priorizando padrões certos.
    """
    if len(st.session_state.historico) < tamanho_janela:
        return None, 0.0

    janela_atual = list(st.session_state.historico)[-tamanho_janela:]
    janela_duzias = [numero_para_duzia(n) for n in janela_atual]

    contagem_duzias = Counter()
    hist_list = list(st.session_state.historico)

    for i in range(len(hist_list) - tamanho_janela):
        sublista_duzias = [numero_para_duzia(n) for n in hist_list[i:i + tamanho_janela]]
        acertos = sum(1 for a, b in zip(janela_duzias, sublista_duzias) if a == b)
        proporcao = acertos / tamanho_janela

        if proporcao >= min_match:
            prox_num = hist_list[i + tamanho_janela]
            prox_duzia = numero_para_duzia(prox_num)
            if prox_duzia != 0 and prox_duzia not in st.session_state.padroes_errados:
                contagem_duzias[prox_duzia] += 1

    if not contagem_duzias:
        return None, 0.0

    # Prioriza padrões certos
    for padrao in st.session_state.padroes_certos:
        if padrao in contagem_duzias:
            contagem_duzias[padrao] += 2  # peso maior

    total = sum(contagem_duzias.values())
    duzia_mais_frequente, ocorrencias = contagem_duzias.most_common(1)[0]
    probabilidade = ocorrencias / total

    if probabilidade >= prob_minima:
        return duzia_mais_frequente, probabilidade
    return None, probabilidade

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if len(st.session_state.historico) == 0 or numero_atual != st.session_state.historico[-1]:
    st.session_state.historico.append(numero_atual)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)

    # Atualiza métricas e envia resultado anterior
    if st.session_state.top2_anterior:
        st.session_state.total_top += 1
        valor = (numero_atual - 1) // 12 + 1
        if valor in st.session_state.top2_anterior:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🟢")
            st.session_state.padroes_certos.append(valor)
            if len(st.session_state.padroes_certos) > 10:
                st.session_state.padroes_certos.pop(0)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🔴")
            if st.session_state.top2_anterior:
                st.session_state.padroes_errados.append(st.session_state.top2_anterior[0])
                if len(st.session_state.padroes_errados) > 10:
                    st.session_state.padroes_errados.pop(0)

    # Previsão por janela + feedback
    duzia_prevista, prob = prever_duzia_com_feedback()
    if duzia_prevista is not None:
        alerta_novo = (st.session_state.top2_anterior != [duzia_prevista])
        if alerta_novo or st.session_state.contador_sem_alerta >= 3:
            st.session_state.top2_anterior = [duzia_prevista]
            st.session_state.tipo_entrada_anterior = "duzia"
            st.session_state.contador_sem_alerta = 0
            enviar_telegram_async(f"📊 <b>ENTRADA DÚZIA:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)")
        else:
            st.session_state.contador_sem_alerta += 1
    else:
        st.info(f"Nenhum padrão confiável encontrado (prob: {prob*100:.1f}%)")

# Interface
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos números:", list(st.session_state.historico)[-12:])

# Salva estado
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "top2_anterior": st.session_state.top2_anterior,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "padroes_errados": st.session_state.padroes_errados
}, ESTADO_PATH)

# Auto-refresh
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
