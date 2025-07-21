import streamlit as st
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CANAL_ID = "-1002796136111"
URL_API = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"

ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CANAL_ID, "text": mensagem}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

def get_vizinhos(numero, total_vizinhos=2):
    idx = ROULETTE_ORDER.index(numero)
    vizinhos = []
    for i in range(-total_vizinhos, total_vizinhos + 1):
        vizinhos.append(ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)])
    return vizinhos

def detectar_terminais_dominantes(historico):
    terminais = [n % 10 for n in historico[-12:]]
    contagem = Counter(terminais)
    dominantes = [t for t, c in contagem.items() if c >= 3]
    return dominantes if 1 <= len(dominantes) <= 2 else []

def gerar_entrada_por_terminais(terminais):
    entrada = set()
    for t in terminais:
        for n in range(37):
            if n % 10 == t:
                entrada.update(get_vizinhos(n, 2))
    return sorted(entrada)

# === INICIALIZAÇÃO DO APP ===
st.set_page_config(page_title="Roleta Estratégias Inteligentes", layout="centered")
st.title("🎯 Estratégias Inteligentes de Entrada")

# === INICIALIZAÇÃO DE VARIÁVEIS ===
if "historico" not in st.session_state:
    st.session_state.historico = deque(maxlen=50)
if "timestamps" not in st.session_state:
    st.session_state.timestamps = deque(maxlen=50)
if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None
if "entrada_ativa" not in st.session_state:
    st.session_state.entrada_ativa = None
if "aguardando_resultado" not in st.session_state:
    st.session_state.aguardando_resultado = False
if "entrada_timestamp" not in st.session_state:
    st.session_state.entrada_timestamp = ""
if "green_count" not in st.session_state:
    st.session_state.green_count = 0
if "red_count" not in st.session_state:
    st.session_state.red_count = 0
if "entrada_pendente" not in st.session_state:
    st.session_state.entrada_pendente = None
if "gatilho_detectado" not in st.session_state:
    st.session_state.gatilho_detectado = False

# === AUTOREFRESH ===
st_autorefresh(interval=5000, key="refresh")

# === CAPTURA DA API ===
try:
    response = requests.get(URL_API)
    data = response.json()

    resultado = data.get("data", {}).get("result", {}).get("outcome")
    if resultado and "number" in resultado:
        numero = resultado["number"]
        timestamp = data["data"].get("settledAt", "")

        if numero != st.session_state.ultimo_numero:
            st.session_state.historico.append(numero)
            st.session_state.timestamps.append(timestamp)
            st.session_state.ultimo_numero = numero
            st.success(f"🎲 Último número: **{numero}** às {timestamp}")

            # === Verifica GREEN/RED se houver entrada ativa ===
            if st.session_state.aguardando_resultado and st.session_state.entrada_ativa:
                if numero in st.session_state.entrada_ativa:
                    enviar_telegram("✅ GREEN!\n🎯 Número dentro da entrada.")
                    st.success("✅ GREEN!")
                    st.session_state.green_count += 1
                else:
                    enviar_telegram("❌ RED!\n🔻 Número fora da entrada.")
                    st.error("❌ RED!")
                    st.session_state.red_count += 1
                st.session_state.entrada_ativa = None
                st.session_state.aguardando_resultado = False

            # === Verifica ativação da Estratégia 3 (terminais dominantes) ===
            dominantes = detectar_terminais_dominantes(st.session_state.historico)
            if dominantes:
                entrada = gerar_entrada_por_terminais(dominantes)
                if numero in st.session_state.historico or numero in entrada:
                    # Gatilho detectado → ativa entrada
                    st.session_state.entrada_ativa = entrada
                    st.session_state.aguardando_resultado = True
                    st.session_state.entrada_timestamp = timestamp
                    st.session_state.gatilho_detectado = True
                    enviar_telegram(
                        f"🚨 NOVA ENTRADA DETECTADA\n🎯 Estratégia: Terminais Dominantes\n"
                        f"🔢 Terminais: {dominantes}\n🔢 Entrada: {entrada}\n"
                        f"🕒 Ativada após número: {numero} ({timestamp})\n"
                        "🎰 Aguardando próximo número para validar (GREEN/RED)"
                    )
                    st.success("🚨 Entrada gerada (Terminais Dominantes)")

            # === Estratégia 1: Terminais 2 / 6 / 9 ===
            elif numero % 10 in [2, 6, 9]:
                entrada = set()
                for base in [31, 34]:
                    entrada.update(get_vizinhos(base, 5))
                entrada_ordenada = sorted(entrada)
                st.session_state.entrada_ativa = entrada_ordenada
                st.session_state.aguardando_resultado = True
                st.session_state.entrada_timestamp = timestamp
                enviar_telegram(
                    f"🚨 NOVA ENTRADA DETECTADA\n🎯 Estratégia: Terminais 2/6/9\n"
                    f"🔢 Entrada: {entrada_ordenada}\n"
                    f"🕒 Ativada após número: {numero} ({timestamp})\n"
                    "🎰 Aguardando próximo número para validar (GREEN/RED)"
                )
                st.success("🚨 Entrada gerada (2/6/9)")

            # === Estratégia 2: Números 4 / 14 / 24 / 34 ===
            elif numero in [4, 14, 24, 34]:
                candidatos = set()
                for base in [1, 2]:
                    candidatos.update(get_vizinhos(base, 5))
                freq = {n: list(st.session_state.historico).count(n) for n in candidatos}
                entrada = sorted(freq, key=freq.get, reverse=True)[:10]
                st.session_state.entrada_ativa = entrada
                st.session_state.aguardando_resultado = True
                st.session_state.entrada_timestamp = timestamp
                enviar_telegram(
                    f"🚨 NOVA ENTRADA DETECTADA\n🎯 Estratégia: Após 4/14/24/34\n"
                    "📊 Seleção baseada na frequência recente\n"
                    f"🔢 Entrada: {entrada}\n"
                    f"🕒 Ativada após número: {numero} ({timestamp})\n"
                    "🎰 Aguardando próximo número para validar (GREEN/RED)"
                )
                st.success("🚨 Entrada gerada (4/14/24/34)")

    else:
        st.warning("⚠️ Resultado ainda não disponível.")
except Exception as e:
    st.error(f"Erro ao acessar API: {e}")

# === INTERFACE ===
st.markdown(f"""
### 📈 Resultados
- ✅ GREENs: **{st.session_state.green_count}**
- ❌ REDs: **{st.session_state.red_count}**
""")

st.subheader("📋 Histórico (últimos 2):")
st.write(list(st.session_state.historico)[-2:])

if st.session_state.entrada_ativa:
    st.subheader("🎯 Entrada Ativa")
    st.info(f"🔢 Números: {st.session_state.entrada_ativa}")
    st.info(f"🕒 Ativada em: {st.session_state.entrada_timestamp}")
    st.info("🎰 Aguardando próximo número para validação...")
