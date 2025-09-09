import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import base64

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_coluna_duzia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

# =============================
# Função unificada de envio (Telegram)
# =============================
def enviar_msg(msg, tipo="previsao"):
    try:
        if not isinstance(msg, str):
            msg = str(msg)
        msg = msg.encode('utf-8', errors='ignore').decode('utf-8')

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=5)

        print(f"[{tipo.upper()} Enviado]: {msg}")
    except Exception as e:
        print(f"Erro ao enviar {tipo}: {e}")

# =============================
# Funções auxiliares
# =============================
def tocar_som_moeda():
    som_base64 = (
        "SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjI2LjEwNAAAAAAAAAAAAAAA//tQxAADBQAB"
        "VAAAAnEAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAA//sQxAADAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
    )
    st.markdown(
        f"""
        <audio autoplay>
            <source src="data:audio/mp3;base64,{som_base64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

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
# Estratégia da Roleta
# =============================
class EstrategiaRoleta:
    ROLETAS_EUROPEIA = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
        13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
        1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
        35, 3, 26
    ]

    def __init__(self, janela=12):
        self.janela = janela
        self.historico = deque(maxlen=janela + 1)

    def extrair_terminal(self, numero):
        return numero % 10

    def adicionar_numero(self, numero):
        self.historico.append(numero)

    def calcular_dominante(self):
        if len(self.historico) < self.janela:
            return None
        ultimos = list(self.historico)[:-1]
        terminais = [self.extrair_terminal(n) for n in ultimos]
        contagem = Counter(terminais)
        dominante = contagem.most_common(1)
        return dominante[0][0] if dominante else None

    def vizinhos_fisicos(self, numero, n=1):
        """Retorna vizinhos físicos usando a roleta europeia real."""
        idx = self.ROLETAS_EUROPEIA.index(numero)
        viz = []
        for i in range(1, n+1):
            viz.append(self.ROLETAS_EUROPEIA[(idx - i) % len(self.ROLETAS_EUROPEIA)])  # esquerda
            viz.append(self.ROLETAS_EUROPEIA[(idx + i) % len(self.ROLETAS_EUROPEIA)])  # direita
        return viz

    def selecionar_numeros_mais_fortes(self, terminal, limite=5, incluir_vizinhos=False):
        if terminal is None:
            return []

        base = [n for n in range(37) if n % 10 == terminal]
        ultimos = list(self.historico)[-50:]
        freq = Counter([n for n in ultimos if n in base])
        mais_fortes = [n for n, _ in freq.most_common(limite)]
        if not mais_fortes:
            mais_fortes = base[:limite]

        numeros_final = set(mais_fortes)
        if incluir_vizinhos:
            for n in mais_fortes:
                numeros_final.update(self.vizinhos_fisicos(n, n=1))

        return sorted(numeros_final)

    def verificar_entrada(self):
        if len(self.historico) < self.janela + 1:
            return None

        ultimos = list(self.historico)
        ultimos_12 = ultimos[:-1]
        numero_13 = ultimos[-1]
        terminal_13 = self.extrair_terminal(numero_13)
        dominante = self.calcular_dominante()

        if dominante is None:
            return None

        condicao_a = numero_13 in ultimos_12
        condicao_b = terminal_13 in [self.extrair_terminal(n) for n in ultimos_12]
        condicao_c = not condicao_a and not condicao_b

        if condicao_a:
            criterio = "A"
        elif condicao_b:
            criterio = "B"
        else:
            criterio = "C"

        return {
            "entrada": condicao_a or condicao_b,
            "criterio": criterio,
            "numero_13": numero_13,
            "dominante": dominante
        }

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="IA Roleta — Números Certeiros", layout="centered")
st.title("🎯 IA Roleta XXXtreme — Estratégia Híbrida")

# --- Inicialização ---
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []

if "estrategia" not in st.session_state:
    st.session_state.estrategia = EstrategiaRoleta(janela=12)

if "estrategia_inicializada" not in st.session_state:
    for h in st.session_state.historico[-13:]:
        try:
            st.session_state.estrategia.adicionar_numero(int(h["number"]))
        except Exception:
            pass
    st.session_state.estrategia_inicializada = True

# --- Contadores ---
for crit in ["A", "B", "C", "D"]:
    if f"acertos_hibrido_{crit}" not in st.session_state:
        st.session_state[f"acertos_hibrido_{crit}"] = 0
    if f"erros_hibrido_{crit}" not in st.session_state:
        st.session_state[f"erros_hibrido_{crit}"] = 0

# Contadores padrão
for k, v in {
    "numeros_previstos": None,
    "criterio": None,
    "previsao_enviada": False,
    "resultado_enviado": False,
    "acertos": 0,
    "erros": 0,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

st_autorefresh(interval=3000, key="refresh_certeiros")

# =============================
# Loop principal
# =============================
resultado = fetch_latest_result()
ultimo_ts = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_atual = resultado["number"]
    ts_atual = resultado["timestamp"]

    st.session_state.historico.append(resultado)
    st.session_state.estrategia.adicionar_numero(numero_atual)
    salvar_resultado_em_arquivo(st.session_state.historico)

    # Verifica resultado
    if st.session_state.previsao_enviada and not st.session_state.resultado_enviado:
        numeros_validos = set(st.session_state.numeros_previstos or [])
        green = numero_atual in numeros_validos
        msg = f"Resultado: {numero_atual} | {'🟢 GREEN' if green else '🔴 RED'}"
        enviar_msg(msg, tipo="resultado")
        st.session_state.resultado_enviado = True
        st.session_state.previsao_enviada = False

        # Atualiza contadores padrão
        if green:
            st.session_state.acertos += 1
            tocar_som_moeda()
        else:
            st.session_state.erros += 1

        # Atualiza contadores híbridos
        crit = st.session_state.criterio
        if crit:
            if green:
                st.session_state[f"acertos_hibrido_{crit}"] += 1
            else:
                st.session_state[f"erros_hibrido_{crit}"] += 1

    # Verifica entrada
    entrada_info = st.session_state.estrategia.verificar_entrada()
    if entrada_info and not st.session_state.previsao_enviada:
        crit = entrada_info["criterio"]

        # Calcula assertividade híbrida
        acertos = st.session_state[f"acertos_hibrido_{crit}"]
        erros = st.session_state[f"erros_hibrido_{crit}"]
        total = acertos + erros
        taxa = (acertos / total) if total > 0 else 1.0

        # Se assertividade < 0.4 → inclui vizinhos
        incluir_viz = taxa < 0.4
        numeros_previstos = st.session_state.estrategia.selecionar_numeros_mais_fortes(
            terminal=entrada_info["dominante"],
            limite=5,
            incluir_vizinhos=incluir_viz
        )

        st.session_state.numeros_previstos = numeros_previstos
        st.session_state.criterio = crit
        st.session_state.previsao_enviada = True
        st.session_state.resultado_enviado = False

        estrategia_txt = "Terminais + Vizinhos" if incluir_viz else "Terminais"
        msg_alerta = (
            f"🎯 Critério {crit} | Terminal {entrada_info['dominante']}\n"
            f"Estratégia: {estrategia_txt}\n"
            f"Números certeiros: {', '.join(map(str, numeros_previstos))}"
        )
        enviar_msg(msg_alerta, tipo="previsao")

# =============================
# Interface
# =============================
st.subheader("🔁 Últimos 13 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-13:]))

st.subheader("🔮 Previsão Atual")
if st.session_state.numeros_previstos:
    st.write(f"🎯 Números certeiros ({st.session_state.criterio}): {st.session_state.numeros_previstos}")
else:
    st.info("🔎 Aguardando próximo número para calcular.")

st.subheader("📊 Desempenho")
total = st.session_state.acertos + st.session_state.erros
taxa = (st.session_state.acertos / total * 100) if total > 0 else 0.0
col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", st.session_state.acertos)
col2.metric("🔴 RED", st.session_state.erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")

st.subheader("📊 Desempenho Híbrido por Critério")
for crit in ["A", "B", "C", "D"]:
    ac = st.session_state[f"acertos_hibrido_{crit}"]
    er = st.session_state[f"erros_hibrido_{crit}"]
    tot = ac + er
    tx = (ac / tot * 100) if tot > 0 else 0.0
    st.write(f"Critério {crit} — 🟢 {ac} | 🔴 {er} | ✅ {tx:.1f}%")

# --- Download histórico ---
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_coluna_duzia.json")
