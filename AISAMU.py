import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import pandas as pd

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_FILE = "historico_sorteios.pkl"
ENTRADAS_FILE = "entradas_resultados.pkl"
ROULETTE_ORDER = [26,3,35,12,28,7,29,18,22,9,31,14,20,1,33,16,24,5,10,
                  23,8,30,11,36,13,27,6,34,17,25,2,21,4,19,15,32,0]

# === FUNÇÕES ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        return joblib.load(HISTORICO_FILE)
    return deque(maxlen=300)

def salvar_historico(historico):
    joblib.dump(historico, HISTORICO_FILE)

def carregar_entradas_resultados():
    if os.path.exists(ENTRADAS_FILE):
        return joblib.load(ENTRADAS_FILE)
    return deque(maxlen=50)

def salvar_entradas_resultados(dados):
    joblib.dump(dados, ENTRADAS_FILE)

def get_vizinhos(numero, n=2):
    if numero not in ROULETTE_ORDER:
        return []
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-n, n+1)]

# === INTERFACE STREAMLIT ===
st.set_page_config(page_title="IA Estratégia Roleta", layout="centered")
st.title("🎯 Estratégia IA - Roleta")

# === SELETOR DE ESTRATÉGIAS ===
estrategias_disponiveis = [
    "Terminais 2/6/9",
    "Gatilho 4/14/24/34 (1 e 2)",
    "Terminais dominantes"
]

estrategias_ativas = st.multiselect(
    "🎯 Selecione as estratégias que deseja ativar:",
    estrategias_disponiveis,
    default=estrategias_disponiveis  # todas ativas por padrão
)

st_autorefresh(interval=10 * 1000, key="refresh")
historico = carregar_historico()

# === ESTADO GLOBAL ===
if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None
if "entrada_ativa" not in st.session_state:
    st.session_state.entrada_ativa = None
if "estrategia_ativa" not in st.session_state:
    st.session_state.estrategia_ativa = None
if "timestamp_ativo" not in st.session_state:
    st.session_state.timestamp_ativo = None
if "entradas_resultados" not in st.session_state:
    st.session_state.entradas_resultados = carregar_entradas_resultados()

# === CAPTURA DA API ===
try:
    response = requests.get(API_URL, timeout=10)
    data = response.json()
    numero = int(data["data"]["result"]["outcome"]["number"])
    timestamp = data["data"]["settledAt"]

    if numero != st.session_state.ultimo_numero:
        # Avaliar acerto da entrada anterior
        if st.session_state.entrada_ativa and st.session_state.estrategia_ativa:
            resultado = "✅ GREEN" if numero in st.session_state.entrada_ativa else "❌ RED"
            st.session_state.entradas_resultados.appendleft({
                "numero": numero,
                "entrada": sorted(st.session_state.entrada_ativa),
                "estrategia": st.session_state.estrategia_ativa,
                "resultado": resultado
            })
            salvar_entradas_resultados(st.session_state.entradas_resultados)

        historico.append(numero)
        salvar_historico(historico)
        st.session_state.ultimo_numero = numero
        st.success(f"🎲 Último número: **{numero}** às {timestamp}")

        entrada = None
        estrategia = None
        mensagem_extra = ""

        # Estratégia 1: Terminais 2, 6, 9
        if "Terminais 2/6/9" in estrategias_ativas and str(numero)[-1] in ["2", "6", "9"]:
            base = [31, 34]
            entrada = []
            for b in base:
                entrada.extend(get_vizinhos(b, 5))
            entrada = list(set(entrada))[:10]
            estrategia = "Terminais 2/6/9"

        # Estratégia 2: Número 4, 14, 24, 34 ativa 1 e 2
        elif "Gatilho 4/14/24/34 (1 e 2)" in estrategias_ativas and numero in [4, 14, 24, 34]:
            candidatos = [1, 2]
            scores = {c: historico.count(c) for c in candidatos}
            escolhidos = sorted(scores, key=scores.get, reverse=True)
            entrada = []
            for e in escolhidos:
                entrada.extend(get_vizinhos(e, 5))
            entrada = list(set(entrada))[:10]
            estrategia = "Gatilho 4/14/24/34 (1 e 2)"

        # Estratégia 3: Terminais dominantes
        elif "Terminais dominantes" in estrategias_ativas and len(historico) >= 13:
            ultimos_12 = list(historico)[-13:-1]
            terminais = [str(n)[-1] for n in ultimos_12]
            contagem = Counter(terminais)
            dominantes = [int(t) for t, c in contagem.items() if c > 2]
            if dominantes:
                base = []
                for d in dominantes:
                    base.extend([n for n in range(37) if str(n).endswith(str(d))])
                entrada = []
                for n in base:
                    entrada.extend(get_vizinhos(n, 2))
                entrada = list(set(entrada))[:10]
                if numero in ultimos_12 or numero in entrada:
                    estrategia = "Terminais dominantes"
                    mensagem_extra = "(Gatilho validado)"
                else:
                    entrada = None

        # === ALERTA ===
        if entrada and estrategia:
            msg = f"Estratégia: {estrategia}\nEntrada: {sorted(entrada)}\n{mensagem_extra}"
            enviar_telegram(msg)
            st.success("✅ Nova entrada gerada e enviada ao Telegram!")
            st.markdown(f"**{estrategia}** — Entrada: `{sorted(entrada)}`")

            # Armazena como entrada ativa
            st.session_state.entrada_ativa = entrada
            st.session_state.estrategia_ativa = estrategia
            st.session_state.timestamp_ativo = timestamp
        else:
            # Limpa entrada ativa
            st.session_state.entrada_ativa = None
            st.session_state.estrategia_ativa = None
            st.session_state.timestamp_ativo = None

    else:
        st.warning("⏳ Aguardando novo número...")

        if st.session_state.entrada_ativa and st.session_state.estrategia_ativa:
            st.info(f"📌 Entrada ativa (ainda válida):\n**{st.session_state.estrategia_ativa}** — Entrada: `{sorted(st.session_state.entrada_ativa)}`\n(Sorteio em: {st.session_state.timestamp_ativo})")

except Exception as e:
    st.error(f"Erro ao acessar API: {e}")

# === HISTÓRICO DE RESULTADOS ===
st.markdown("---")
st.subheader("📊 Histórico de Previsões")

if st.session_state.entradas_resultados:
    df = pd.DataFrame(list(st.session_state.entradas_resultados))
    st.dataframe(df, use_container_width=True)
else:
    st.info("Ainda não há previsões avaliadas.")

# === CONTADOR DE ACERTOS ===
green_count = sum(1 for r in st.session_state.entradas_resultados if r["resultado"] == "✅ GREEN")
total_count = len(st.session_state.entradas_resultados)
taxa_acerto = (green_count / total_count * 100) if total_count > 0 else 0

st.markdown("---")
st.subheader("✅ Desempenho Geral")
st.markdown(f"**Total de previsões:** {total_count}")
st.markdown(f"**Total de GREENs:** {green_count}")
st.markdown(f"**Taxa de acerto:** `{taxa_acerto:.1f}%`")
