import streamlit as st
import json
import os
import requests
from collections import deque
from streamlit_autorefresh import st_autorefresh
import logging

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar para Telegram: {e}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            historico = json.load(f)
        historico_padronizado = []
        for h in historico:
            if isinstance(h, dict):
                historico_padronizado.append(h)
            else:
                historico_padronizado.append({"number": h, "timestamp": f"manual_{len(historico_padronizado)}"})
        return historico_padronizado
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f, indent=2)

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

def obter_vizinhos(numero, layout, antes=2, depois=2):
    """Retorna lista [k anteriores..., numero, k posteriores...]"""
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
    """Mesma lógica mas com janela maior (5 antes / 5 depois)."""
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
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)

# =============================
# IA recorrência (antes + depois)
# =============================
class IA_Recorrencia:
    def __init__(self, layout=None, top_n=4):
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

        # Percorre todas as ocorrências anteriores do último número
        for i, h in enumerate(historico_lista[:-1]):
            if isinstance(h, dict) and h.get("number") == ultimo_numero:
                if i - 1 >= 0 and isinstance(historico_lista[i-1], dict):
                    antes.append(historico_lista[i-1]["number"])
                if i + 1 < len(historico_lista) and isinstance(historico_lista[i+1], dict):
                    depois.append(historico_lista[i+1]["number"])

        if not antes and not depois:
            return []

        from collections import Counter
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
# Nova estratégia 31/34
# =============================
def estrategia_31_34(numero_capturado):
    """
    Dispara a estratégia 31/34 se terminal ∈ {2,6,9}.
    Envia TELEGRAM mostrando apenas "31 34" (como solicitado).
    Retorna a lista completa de entrada usada para conferência (internamente).
    """
    if numero_capturado is None:
        return None
    try:
        terminal = int(str(numero_capturado)[-1])
    except Exception:
        return None

    if terminal not in {2, 6, 9}:
        return None

    # gera vizinhos fixos de 31 e 34 (5 antes + número + 5 depois)
    viz_31 = obter_vizinhos_fixos(31, ROULETTE_LAYOUT, antes=5, depois=5)
    viz_34 = obter_vizinhos_fixos(34, ROULETTE_LAYOUT, antes=5, depois=5)

    # monta entrada: 0,26,30 + vizinhos de 31 + vizinhos de 34
    entrada = set([0, 26, 30] + viz_31 + viz_34)

    # enviar ALERTA compacto: só 31 34 (como você pediu)
    msg = (
        "🎯 Estratégia 31/34 disparada!\n"
        f"Número capturado: {numero_capturado} (terminal {terminal})\n"
        "Entrar nos números: 31 34"
    )
    enviar_telegram(msg)

    return list(entrada)

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA de Recorrência (Antes + Depois) Profissional")
st_autorefresh(interval=3000, key="refresh")

# Inicialização segura do session_state
for key, default in {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia(),
    "previsao": [],
    "previsao_31_34": [],
    "acertos": 0,
    "erros": 0,
    "acertos_31_34": 0,
    "erros_31_34": 0,
    "contador_rodadas": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)

# Captura número
resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))

    # -----------------------------
    # Conferência GREEN/RED (Recorrência)
    # -----------------------------
    if st.session_state.previsao:
        numeros_com_vizinhos = []
        for n in st.session_state.previsao:
            vizinhos = obter_vizinhos(n, ROULETTE_LAYOUT, antes=2, depois=2)
            for v in vizinhos:
                if v not in numeros_com_vizinhos:
                    numeros_com_vizinhos.append(v)

        numero_real = numero_dict["number"]
        if numero_real in numeros_com_vizinhos:
            st.session_state.acertos += 1
            st.success(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
            enviar_telegram(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")

        st.session_state.previsao = []

    # -----------------------------
    # Conferência GREEN/RED (31/34)
    # -----------------------------
    if st.session_state.previsao_31_34:
        numero_real = numero_dict["number"]
        # previsao_31_34 guarda a lista completa (com vizinhos e 0,26,30)
        if numero_real in st.session_state.previsao_31_34:
            st.session_state.acertos_31_34 += 1
            st.success(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
            enviar_telegram(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
        else:
            st.session_state.erros_31_34 += 1
            st.error(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
            enviar_telegram(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")

        st.session_state.previsao_31_34 = []

    # atualiza contador e decide qual estratégia rodar
    st.session_state.contador_rodadas += 1

    # -----------------------------
    # Previsão a cada 3 rodadas (recorrência)
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros

            # 🔹 Ordena do menor para o maior apenas na exibição
            msg_alerta = "🎯 Próximos números prováveis (Recorrência): " + \
                         " ".join(str(n) for n in sorted(prox_numeros))
            enviar_telegram(msg_alerta)
    else:
        # -----------------------------
        # Estratégia 31/34 (nos intervalos)
        # -----------------------------
        entrada_31_34 = estrategia_31_34(numero_dict["number"])
        if entrada_31_34:
            # salva a lista completa para conferência na próxima rodada
            st.session_state.previsao_31_34 = entrada_31_34

# Histórico
st.subheader("📜 Histórico (últimos 3 números)")
st.write(list(st.session_state.estrategia.historico)[-3:])

# Estatísticas GREEN/RED (Recorrência)
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

# Quantidade de números previstos na última entrada recorrência
qtd_previstos_rec = len(st.session_state.get("previsao", []))

col1, col2, col3, col7 = st.columns(4)
col1.metric("🟢 GREEN", acertos)
col2.metric("🔴 RED", erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")
col7.metric("🎯 Qtd. previstos Recorrência", qtd_previstos_rec)

# Estatísticas 31/34
acertos_31_34 = st.session_state.get("acertos_31_34", 0)
erros_31_34 = st.session_state.get("erros_31_34", 0)
total_31_34 = acertos_31_34 + erros_31_34
taxa_31_34 = (acertos_31_34 / total_31_34 * 100) if total_31_34 > 0 else 0.0

# Quantidade de números previstos na última entrada 31/34
qtd_previstos_31_34 = len(st.session_state.get("previsao_31_34", []))

col4, col5, col6, col8 = st.columns(4)
col4.metric("🟢 GREEN 31/34", acertos_31_34)
col5.metric("🔴 RED 31/34", erros_31_34)
col6.metric("✅ Taxa 31/34", f"{taxa_31_34:.1f}%")
col8.metric("🎯 Qtd. previstos 31/34", qtd_previstos_31_34)

# Estatísticas recorrência
historico_lista = list(st.session_state.estrategia.historico)
historico_total = len(historico_lista)
ultimo_numero = (historico_lista[-1]["number"] if historico_total > 0 and isinstance(historico_lista[-1], dict) else None)

ocorrencias_ultimo = 0
if ultimo_numero is not None:
    ocorrencias_ultimo = sum(
        1 for h in historico_lista[:-1] if isinstance(h, dict) and h.get("number") == ultimo_numero
    )

st.subheader("📊 Estatísticas da Recorrência")
st.write(f"Total de registros no histórico: {historico_total}")
if ultimo_numero is not None:
    st.write(f"Quantidade de ocorrências do último número ({ultimo_numero}) usadas para recorrência: {ocorrencias_ultimo}")
