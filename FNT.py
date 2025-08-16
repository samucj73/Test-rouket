from collections import Counter
import threading
import requests
import joblib
import streamlit as st

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 10 segundos

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior", "padroes_certos", "ultima_entrada"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        else:
            st.session_state[var] = 0

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === Funções auxiliares ===
def calcular_frequencia_duzias(historico, janela=30):
    ultimos = [h for h in list(historico)[-janela:] if h != 0]
    return Counter(ultimos)

def calcular_alternancia(historico, janela=20):
    duzias = [h for h in list(historico)[-janela:] if h != 0]
    if len(duzias) < 2:
        return 0.5
    alternancias = sum(1 for i in range(1, len(duzias)) if duzias[i] != duzias[i-1])
    return alternancias / (len(duzias)-1)

def calcular_tendencia(historico, peso=0.9, janela=15):
    duzias = [h for h in list(historico)[-janela:] if h != 0]
    pesos = [peso**i for i in range(len(duzias)-1, -1, -1)]
    tendencia = {1:0, 2:0, 3:0}
    for d, w in zip(duzias, pesos):
        tendencia[d] += w
    return tendencia

# === Previsão dinâmica de dúzia ===
def prever_duzia_com_feedback(min_match=0.2):
    if len(st.session_state.historico) < tamanho_janela:
        return None, 0.0, (0,0,0)

    freq = calcular_frequencia_duzias(st.session_state.historico)
    alt = calcular_alternancia(st.session_state.historico)
    tend = calcular_tendencia(st.session_state.historico)

    peso_freq = 0.3 + (0.4 * (1 - alt))
    peso_tend = 0.3 + (0.4 * alt)
    peso_rep = 1.0 - (peso_freq + peso_tend)

    if freq:
        mais_frequente = max(freq.values())
        soma_freq = sum(freq.values())
        if soma_freq > 0 and (mais_frequente / soma_freq) > 0.5:
            peso_freq += 0.1
            peso_tend -= 0.1 if peso_tend > 0.2 else 0

    # Normaliza pesos
    total_peso = peso_freq + peso_tend + peso_rep
    peso_freq /= total_peso
    peso_tend /= total_peso
    peso_rep /= total_peso

    scores = {}
    for d in [1,2,3]:
        scores[d] = freq.get(d,0) * peso_freq + tend.get(d,0) * peso_tend + (1-alt) * peso_rep

    # Reforço de padrões que acertaram
    for padrao in st.session_state.padroes_certos:
        scores[padrao] = scores.get(padrao,0) + 1

    melhor = max(scores.items(), key=lambda x: x[1])
    duzia_prevista, score = melhor
    total = sum(scores.values())
    probabilidade = score / total if total > 0 else 0

    if probabilidade >= prob_minima:
        return duzia_prevista, probabilidade, (peso_freq, peso_tend, peso_rep)
    return None, probabilidade, (peso_freq, peso_tend, peso_rep)

# === Loop principal ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico apenas se novo número
if len(st.session_state.historico) == 0 or numero_para_duzia(numero_atual) != st.session_state.historico[-1]:
    duzia_atual = salvar_historico_duzia(numero_atual)

    # Feedback de acertos
    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor = numero_para_duzia(numero_atual)
        if valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🟢")
            st.session_state.padroes_certos.append(valor)
            if len(st.session_state.padroes_certos) > 10:
                st.session_state.padroes_certos.pop(0)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🔴")

    # Previsão da próxima dúzia
    duzia_prevista, prob, pesos = prever_duzia_com_feedback()

    if duzia_prevista is not None:
        # Exibe pesos dinâmicos no painel
        st.write(f"📊 Pesos dinâmicos → Frequência: {pesos[0]:.2f}, Tendência: {pesos[1]:.2f}, Repetição: {pesos[2]:.2f}")

        chave_alerta = f"{duzia_prevista}_{st.session_state.historico[-1]}"
        if "ultima_chave_alerta" not in st.session_state:
            st.session_state.ultima_chave_alerta = ""

        if chave_alerta != st.session_state.ultima_chave_alerta or st.session_state.contador_sem_alerta >= 3:
            st.session_state.ultima_entrada = [duzia_prevista]
            st.session_state.tipo_entrada_anterior = "duzia"
            st.session_state.contador_sem_alerta = 0
            st.session_state.ultima_chave_alerta = chave_alerta
            enviar_telegram_async(f"📊 <b>ENTRADA DÚZIA:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)")
        else:
            st.session_state.contador_sem_alerta += 1
    else:
        st.info(f"Nenhum padrão confiável encontrado (prob: {prob*100:.1f}%)")

# Exibição
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])

# Salva estado
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "ultima_entrada": st.session_state.ultima_entrada,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta
}, ESTADO_PATH)
