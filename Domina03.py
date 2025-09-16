# Deslocamento.py  (arquivo completo)
import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Canal principal
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# Canal alternativo para Top N Dinâmico
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18   # janela móvel para cálculos de frequência
MIN_TOP_N = 5
MAX_TOP_N = 15

# =============================
# Funções auxiliares (Telegram, histórico, API, vizinhos)
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram Top N: {e}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
        except Exception:
            # se arquivo estiver corrompido, retorna vazio
            return []
        historico_padronizado = []
        for i, h in enumerate(historico):
            if isinstance(h, dict) and "number" in h:
                historico_padronizado.append(h)
            else:
                # converte formato simples [num, num, ...] em dict
                historico_padronizado.append({"number": h, "timestamp": f"manual_{i}"})
        return historico_padronizado
    return []

def salvar_historico(historico):
    try:
        with open(HISTORICO_PATH, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=6)
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

def obter_vizinhos(numero, layout, antes=2, depois=2):
    """Retorna vizinhos físicos (antes, numero, depois). Usa wrap-around."""
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

def obter_vizinhos_fixos(numero, layout, antes=5, depois=5):
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

# =============================
# Estratégia - controle do histórico
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA Recorrência (antes + depois) - versão simples compatível com seu histórico
# =============================
class IA_Recorrencia:
    def __init__(self, layout=None, top_n=3):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n

    def prever(self, historico):
        if not historico:
            return []

        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"] if isinstance(historico_lista[-1], dict) else None
        if ultimo_numero is None:
            return []

        antes, depois = [], []

        for i, h in enumerate(historico_lista[:-1]):
            if isinstance(h, dict) and h.get("number") == ultimo_numero:
                if i - 1 >= 0 and isinstance(historico_lista[i-1], dict):
                    antes.append(historico_lista[i-1]["number"])
                if i + 1 < len(historico_lista) and isinstance(historico_lista[i+1], dict):
                    depois.append(historico_lista[i+1]["number"])

        if not antes and not depois:
            return []

        contagem_antes = Counter(antes)
        contagem_depois = Counter(depois)

        top_antes = [num for num, _ in contagem_antes.most_common(self.top_n)]
        top_depois = [num for num, _ in contagem_depois.most_common(self.top_n)]

        candidatos = list(set(top_antes + top_depois))

        numeros_previstos = []
        for n in candidatos:
            vizinhos = obter_vizinhos(n, self.layout, antes=1, depois=1)
            for v in vizinhos:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        return numeros_previstos

# =============================
# Redução inteligente (metade) — pontua e escolhe 50% mais fortes
# =============================
def reduzir_metade_inteligente(previsoes, historico):
    if not previsoes:
        return []

    # últimos WINDOW_SIZE números (apenas os 'number')
    ultimos = [h["number"] for h in historico[-WINDOW_SIZE:]] if historico else []
    contagem_total = Counter(ultimos)

    pontuacoes = {}
    # pega bônus TopN greens se existir
    topn_greens = st.session_state.get("topn_greens", {})

    for n in previsoes:
        freq = contagem_total.get(n, 0)                # frequência recente
        vizinhos = obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1)
        redundancia = sum(1 for v in vizinhos if v in previsoes)  # penaliza agrupamentos
        topN_bonus = topn_greens.get(n, 0)             # histórico de greens no topN
        # pontuação combinada (ajustável)
        pontuacoes[n] = freq + (topN_bonus * 0.8) - (redundancia * 0.6)

    # Ordena pela pontuação (maior primeiro)
    ordenados = sorted(pontuacoes.keys(), key=lambda x: pontuacoes[x], reverse=True)

    # Seleciona metade (inteligente)
    n_reduzidos = max(1, len(ordenados) // 2)
    return ordenados[:n_reduzidos]

# =============================
# Ajuste Top N (simples - baseado em frequência recente filtrada pelos previsoes)
# =============================
def ajustar_top_n(previsoes, historico, min_n=MIN_TOP_N, max_n=MAX_TOP_N):
    if not previsoes:
        return []

    ultimos = [h["number"] for h in historico[-WINDOW_SIZE:]] if historico else []
    contagem = Counter(ultimos)
    # pega os mais frequentes no período (até max_n)
    candidatos = [num for num, _ in contagem.most_common(max_n)]
    # filtra apenas os que estão na lista de previsões (prioriza coerência)
    filtrados = [n for n in candidatos if n in previsoes]
    # garante pelo menos min_n (preenche com os top das previsoes caso falte)
    if len(filtrados) < min_n:
        extras = [n for n in previsoes if n not in filtrados]
        filtrados += extras[:(min_n - len(filtrados))]
    return filtrados[:max_n]

# =============================
# Estratégia 31/34
# =============================
def estrategia_31_34(numero_capturado):
    if numero_capturado is None:
        return None
    try:
        terminal = int(str(numero_capturado)[-1])
    except Exception:
        return None
    # gatilho original: se terminal em {2,6,9}
    if terminal not in {2, 6, 9}:
        return None

    viz_31 = obter_vizinhos_fixos(31, ROULETTE_LAYOUT, antes=5, depois=5)
    viz_34 = obter_vizinhos_fixos(34, ROULETTE_LAYOUT, antes=5, depois=5)
    entrada = set([0, 26, 30] + viz_31 + viz_34)

    # envia alerta compacto
    msg = (
        "🎯 Estratégia 31/34 disparada!\n"
        f"Número capturado: {numero_capturado} (terminal {terminal})\n"
        "Entrar nos números: 31 34"
    )
    enviar_telegram(msg)
    return list(entrada)

# =============================
# Streamlit - inicialização session_state
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência + Redução Inteligente")
st_autorefresh(interval=3000, key="refresh")

# chaves iniciais
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia(),
    "previsao": [],
    "previsao_topN": [],
    "previsao_31_34": [],
    "acertos": 0,
    "erros": 0,
    "acertos_topN": 0,
    "erros_topN": 0,
    "acertos_31_34": 0,
    "erros_31_34": 0,
    "contador_rodadas": 0,
    "topn_greens": {}
}
for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carrega histórico do arquivo
historico = carregar_historico()
for n in historico:
    # evita duplicar caso já esteja no session_state (útil no reload)
    if not st.session_state.estrategia.historico or st.session_state.estrategia.historico[-1].get("timestamp") != n.get("timestamp"):
        st.session_state.estrategia.adicionar_numero(n)

# -----------------------------
# Captura novo número (API)
# -----------------------------
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))
    numero_real = numero_dict["number"]

    # incrementa contador de rodadas (usado para alternar IA / 31_34)
    st.session_state.contador_rodadas += 1

    # -----------------------------
    # Previsão: rodadas pares -> IA recorrência + redução inteligente
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            # redução inteligente pela metade (mantém melhores pontuados)
            prox_numeros = reduzir_metade_inteligente(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao = prox_numeros

            # ajusta Top N
            entrada_topN = ajustar_top_n(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao_topN = entrada_topN

            # envia alertas compactos
            enviar_telegram("🎯 NP: " + " ".join(str(n) for n in sorted(prox_numeros)))
            enviar_telegram_topN("📊 Top N: " + " ".join(str(n) for n in sorted(entrada_topN)))
    # -----------------------------
    # Estratégia 31/34 nas rodadas ímpares
    # -----------------------------
    else:
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34
            enviar_telegram("🎯 Estrat 31/34: " + " ".join(str(n) for n in entrada_31_34))

    # -----------------------------
    # === Conferência e contagem (GREEN/RED) ===
    # -----------------------------
    # Recorrência
    if st.session_state.previsao:
        numeros_com_vizinhos = []
        for n in st.session_state.previsao:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=2, depois=2):
                if v not in numeros_com_vizinhos:
                    numeros_com_vizinhos.append(v)
        if numero_real in numeros_com_vizinhos:
            st.session_state.acertos += 1
            st.success(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
            enviar_telegram(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
        st.session_state.previsao = []

    # Top N
    if st.session_state.previsao_topN:
        topN_com_vizinhos = []
        for n in st.session_state.previsao_topN:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
                if v not in topN_com_vizinhos:
                    topN_com_vizinhos.append(v)
        if numero_real in topN_com_vizinhos:
            st.session_state.acertos_topN += 1
            st.success(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
            enviar_telegram_topN(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
            # registra para usar como bônus na redução inteligente
            st.session_state.topn_greens[numero_real] = st.session_state.topn_greens.get(numero_real, 0) + 1
        else:
            st.session_state.erros_topN += 1
            st.error(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
            enviar_telegram_topN(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
        st.session_state.previsao_topN = []

    # 31/34
    if st.session_state.previsao_31_34:
        if numero_real in st.session_state.previsao_31_34:
            st.session_state.acertos_31_34 += 1
            st.success(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
            enviar_telegram(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
        else:
            st.session_state.erros_31_34 += 1
            st.error(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
            enviar_telegram(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
        st.session_state.previsao_31_34 = []

# =============================
# Exibição no Streamlit (histórico, previsões e métricas)
# =============================
st.subheader("📜 Histórico (últimos 10 números)")
ultimos_display = [h["number"] for h in list(st.session_state.estrategia.historico)[-10:]]
st.write(ultimos_display)

st.subheader("📊 Última previsão IA Recorrência (reduzida inteligentemente)")
st.write(st.session_state.get("previsao", []))

st.subheader("📊 Última previsão Top N")
st.write(st.session_state.get("previsao_topN", []))

st.subheader("📊 Última previsão Estrat 31/34")
st.write(st.session_state.get("previsao_31_34", []))

# =============================
# Métricas finais e indicadores
# =============================
st.subheader("📈 Métricas de Performance")

# Recorrência
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0
qtd_previstos_rec = len(st.session_state.get("previsao", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN", acertos)
col2.metric("🔴 RED", erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")
col4.metric("🎯 Qtd. previstos Recorrência", qtd_previstos_rec)

# Top N
acertos_topN = st.session_state.get("acertos_topN", 0)
erros_topN = st.session_state.get("erros_topN", 0)
total_topN = acertos_topN + erros_topN
taxa_topN = (acertos_topN / total_topN * 100) if total_topN > 0 else 0.0
qtd_previstos_topN = len(st.session_state.get("previsao_topN", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN Top N", acertos_topN)
col2.metric("🔴 RED Top N", erros_topN)
col3.metric("✅ Taxa Top N", f"{taxa_topN:.1f}%")
col4.metric("🎯 Qtd. previstos Top N", qtd_previstos_topN)

# 31/34
acertos_31_34 = st.session_state.get("acertos_31_34", 0)
erros_31_34 = st.session_state.get("erros_31_34", 0)
total_31_34 = acertos_31_34 + erros_31_34
taxa_31_34 = (acertos_31_34 / total_31_34 * 100) if total_31_34 > 0 else 0.0
qtd_previstos_31_34 = len(st.session_state.get("previsao_31_34", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN 31/34", acertos_31_34)
col2.metric("🔴 RED 31/34", erros_31_34)
col3.metric("✅ Taxa 31/34", f"{taxa_31_34:.1f}%")
col4.metric("🎯 Qtd. previstos 31/34", qtd_previstos_31_34)

# =============================
# Salvamento periódico de métricas (opcional)
# =============================
# Se quiser salvar métricas em arquivo (historico_metricas.json), descomente abaixo:
# try:
#     metrics = {
#         "acertos": acertos, "erros": erros,
#         "acertos_topN": acertos_topN, "erros_topN": erros_topN,
#         "acertos_31_34": acertos_31_34, "erros_31_34": erros_31_34
#     }
#     with open("historico_metricas.json", "w") as f:
#         json.dump(metrics, f, indent=2)
# except Exception as e:
#     logging.error(f"Erro ao salvar métricas: {e}")
