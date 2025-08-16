import streamlit as st
import requests
import joblib
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
REFRESH_INTERVAL = 5000  # 10 segundos

# === SESSION STATE ===
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
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

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (Feedback Apenas Acertos)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=2, max_value=120, value=8)
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=10, max_value=100, value=30) / 100.0

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
    """Converte número cru em dúzia"""
    if num == 0:
        return 0
    elif 1 <= num <= 12:
        return 1
    elif 13 <= num <= 24:
        return 2
    else:
        return 3

def salvar_historico_duzia(numero):
    """Converte número para dúzia e salva no histórico"""
    duzia = numero_para_duzia(numero)
    if len(st.session_state.historico) == 0 or duzia != st.session_state.historico[-1]:
        st.session_state.historico.append(duzia)
        joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

def calcular_frequencia_duzias(historico, janela=30):
    """Conta quantas vezes cada dúzia apareceu nos últimos N sorteios"""
    ultimos = [h for h in list(historico)[-janela:] if h != 0]
    return Counter(ultimos)

def calcular_alternancia(historico, janela=20):
    """Mede a taxa de alternância entre dúzias consecutivas"""
    duzias = [h for h in list(historico)[-janela:] if h != 0]
    if len(duzias) < 2:
        return 0.5
    alternancias = sum(1 for i in range(1, len(duzias)) if duzias[i] != duzias[i-1])
    return alternancias / (len(duzias)-1)

def calcular_tendencia(historico, peso=0.9, janela=15):
    """Dá mais peso para as dúzias mais recentes"""
    duzias = [h for h in list(historico)[-janela:] if h != 0]
    pesos = [peso**i for i in range(len(duzias)-1, -1, -1)]
    tendencia = {1:0, 2:0, 3:0}
    for d, w in zip(duzias, pesos):
        tendencia[d] += w
    return tendencia

def prever_duzia_com_feedback(min_match=0.2):
    """Prevê a próxima dúzia de forma balanceada usando frequência, alternância e tendência"""
    if len(st.session_state.historico) < tamanho_janela:
        return None, 0.0, (0,0,0)

    # --- Calcula fatores ---
    freq = calcular_frequencia_duzias(st.session_state.historico)
    alt = calcular_alternancia(st.session_state.historico)  # 0 = repetindo muito, 1 = alternando muito
    tend = calcular_tendencia(st.session_state.historico)

    # --- Normaliza fatores ---
    total_freq = sum(freq.values()) if freq else 1
    total_tend = sum(tend.values()) if tend else 1

    freq_norm = {d: freq.get(d,0)/total_freq for d in [1,2,3]}
    tend_norm = {d: tend.get(d,0)/total_tend for d in [1,2,3]}

    # --- Ajuste dinâmico dos pesos ---
    peso_freq = 0.35 + 0.3*(1-alt)   # mais peso se repetindo
    peso_tend = 0.35 + 0.3*alt      # mais peso se alternando
    peso_rep = 1.0 - (peso_freq + peso_tend)
    peso_rep = max(peso_rep, 0.05)  # garante chance mínima

    # --- Calcula scores ---
    scores = {}
    for d in [1,2,3]:
        # score = freq + tendência + alternância
        scores[d] = freq_norm[d]*peso_freq + tend_norm[d]*peso_tend + (1-alt)*peso_rep

    # --- Reforço de acertos anteriores (suavizado) ---
    for padrao in set(st.session_state.padroes_certos):
        scores[padrao] += 0.2  # valor pequeno para não dominar demais

    # --- Ordena e calcula probabilidade ---
    melhor = max(scores.items(), key=lambda x: x[1])
    duzia_prevista, score = melhor
    total_score = sum(scores.values())
    probabilidade = score / total_score if total_score > 0 else 0

    return duzia_prevista, probabilidade, (peso_freq, peso_tend, peso_rep)







# === LOOP PRINCIPAL ===
# === LOOP PRINCIPAL AJUSTADO ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico apenas se novo número
if len(st.session_state.historico) == 0 or numero_para_duzia(numero_atual) != st.session_state.historico[-1]:
    duzia_atual = salvar_historico_duzia(numero_atual)

    # Feedback apenas de acertos
    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor = numero_para_duzia(numero_atual)
        if valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🟢")
            # Armazena padrão que acertou
            st.session_state.padroes_certos.append(valor)
            if len(st.session_state.padroes_certos) > 10:
                st.session_state.padroes_certos.pop(0)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🔴")

# === Previsão da próxima entrada com controle de alertas ===
# === Previsão da próxima entrada com controle de alertas ===
# === Previsão da próxima entrada com controle de alertas ===
# === Previsão da próxima entrada com controle de alertas ===
duzia_prevista, prob, pesos = prever_duzia_com_feedback()

if duzia_prevista is not None:
    # Exibe pesos dinâmicos no painel
    st.write(f"📊 Pesos dinâmicos → Frequência: {pesos[0]:.2f}, Tendência: {pesos[1]:.2f}, Repetição: {pesos[2]:.2f}")

    # Chave é apenas a previsão
    chave_alerta = f"duzia_{duzia_prevista}"

    # Envia alerta apenas se mudou a previsão
    if chave_alerta != st.session_state.ultima_chave_alerta:
        st.session_state.ultima_entrada = [duzia_prevista]
        st.session_state.tipo_entrada_anterior = "duzia"
        st.session_state.contador_sem_alerta = 0
        st.session_state.ultima_chave_alerta = chave_alerta

        enviar_telegram_async(
            f"📊 <b>ENTRADA DÚZIA:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)"
        )
else:
    st.info(f"Nenhum padrão confiável encontrado (prob: {prob*100:.1f}%)")

# Interface limpa
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])
#st.write(f"📊 Pesos dinâmicos → Frequência: {pesos[0]:.2f}, Tendência: {pesos[1]:.2f}, Repetição: {pesos[2]:.2f}")

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


# Auto-refresh
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
