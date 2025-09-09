import streamlit as st
import json
import os
import requests
import logging
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# =============================
# =============================
# Função envio Telegram
# =============================
def enviar_msg(msg, tipo="previsao"):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=5)
        print(f"[{tipo.upper()} Enviado]: {msg}")
    except Exception as e:
        print(f"Erro ao enviar {tipo}: {e}")

# =============================
# Salvar histórico
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH, limite=500):
    try:
        if len(historico) > limite:
            historico = historico[-limite:]
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

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

# =============================
# Estratégia baseada em deslocamentos
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=37)
        self.roleta = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
            13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
            1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
            35, 3, 26
        ]

    def adicionar_numero(self, numero):
        self.historico.append(numero)

    def calcular_deslocamentos(self, janela=12):
        if len(self.historico) < janela:
            return None
        ultimos = list(self.historico)[-janela:]
        posicoes = [self.roleta.index(n) for n in ultimos]
        deslocamentos = []
        N = len(self.roleta)
        for i in range(1, len(posicoes)):
            d = (posicoes[i] - posicoes[i-1]) % N
            deslocamentos.append(d)
        return deslocamentos

    def prever_proximos(self, janela=12, top_n=10):
        deslocamentos = self.calcular_deslocamentos(janela)
        if not deslocamentos:
            return []
        freq = Counter(deslocamentos)
        mais_comuns = [d for d, _ in freq.most_common(top_n)]
        ultima_pos = self.roleta.index(self.historico[-1])
        proximos = [(self.roleta[(ultima_pos + d) % len(self.roleta)]) for d in mais_comuns]
        return sorted(set(proximos))[:10]

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="IA Roleta — Deslocamentos", layout="centered")
st.title("🎯 IA Roleta — Estratégia por Deslocamentos")

if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []

if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaDeslocamento()

if "estrategia_inicializada" not in st.session_state:
    for h in st.session_state.historico[-37:]:
        try:
            st.session_state.estrategia.adicionar_numero(int(h["number"]))
        except Exception:
            pass
    st.session_state.estrategia_inicializada = True

for k, v in {
    "previsao": None,
    "previsao_enviada": False,
    "resultado_enviado": False,
    "acertos": 0,
    "erros": 0,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

st_autorefresh(interval=3000, key="refresh_deslocamento")

resultado = fetch_latest_result()
ultimo_ts = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    numero_atual = resultado["number"]
    ts_atual = resultado["timestamp"]

    st.session_state.historico.append(resultado)
    try:
        st.session_state.estrategia.adicionar_numero(int(numero_atual))
    except Exception:
        pass
    salvar_resultado_em_arquivo(st.session_state.historico)

    # Conferir GREEN/RED
    if st.session_state.previsao_enviada and not st.session_state.resultado_enviado:
        green = int(numero_atual) in (st.session_state.previsao or [])
        msg = f"Resultado: {numero_atual} | {'🟢 GREEN' if green else '🔴 RED'}"
        enviar_msg(msg, tipo="resultado")
        st.session_state.resultado_enviado = True
        st.session_state.previsao_enviada = False
        if green:
            st.session_state.acertos += 1
        else:
            st.session_state.erros += 1

    # Nova previsão
    prox_numeros = st.session_state.estrategia.prever_proximos(janela=12, top_n=10)
    if prox_numeros and not st.session_state.previsao_enviada:
        st.session_state.previsao = prox_numeros
        st.session_state.previsao_enviada = True
        st.session_state.resultado_enviado = False

        # formatar em 2 linhas de 5
        linha1 = " ".join(map(str, prox_numeros[:5]))
        linha2 = " ".join(map(str, prox_numeros[5:10]))
        msg_alerta = f"Próximos números prováveis:\n{linha1}\n{linha2}"
        enviar_msg(msg_alerta, tipo="previsao")

# --- Interface ---
st.subheader("🔁 Últimos Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-13:]))

st.subheader("🔮 Previsão Atual")
if st.session_state.previsao:
    linha1 = " ".join(map(str, st.session_state.previsao[:5]))
    linha2 = " ".join(map(str, st.session_state.previsao[5:10]))
    st.write(f"{linha1}\n{linha2}")
else:
    st.info("🔎 Aguardando próximo número para calcular.")

st.subheader("📊 Desempenho")
total = st.session_state.acertos + st.session_state.erros
taxa = (st.session_state.acertos / total * 100) if total > 0 else 0.0
col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", st.session_state.acertos)
col2.metric("🔴 RED", st.session_state.erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")

# --- Download histórico ---
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_deslocamento.json")
