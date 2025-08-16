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
    """Prevê a próxima dúzia com pesos dinâmicos baseados em alternância e dominância"""
    if len(st.session_state.historico) < tamanho_janela:
        return None, 0.0, (0,0,0)

    # === Novos fatores ===
    freq = calcular_frequencia_duzias(st.session_state.historico)
    alt = calcular_alternancia(st.session_state.historico)  # 0 = repetindo muito, 1 = alternando muito
    tend = calcular_tendencia(st.session_state.historico)

    # === Ajuste dinâmico dos pesos ===
    peso_freq = 0.3 + (0.4 * (1 - alt))   # até 70% se estiver repetindo
    peso_tend = 0.3 + (0.4 * alt)         # até 70% se estiver alternando
    peso_rep = 1.0 - (peso_freq + peso_tend)

    if freq:
        mais_frequente = max(freq.values())
        soma_freq = sum(freq.values())
        if soma_freq > 0 and (mais_frequente / soma_freq) > 0.5:
            peso_freq += 0.1
            peso_tend -= 0.1 if peso_tend > 0.2 else 0

    # Normaliza
    total_peso = peso_freq + peso_tend + peso_rep
    peso_freq /= total_peso
    peso_tend /= total_peso
    peso_rep /= total_peso

    # === Cálculo dos scores ===
    scores = {}
    for d in [1,2,3]:
        scores[d] = (
            freq.get(d,0) * peso_freq +
            tend.get(d,0) * peso_tend +
            (1-alt) * peso_rep
        )

    # === Reforço de acertos anteriores ===
    for padrao in st.session_state.padroes_certos:
        scores[padrao] = scores.get(padrao, 0) + 1

    # Ordena pelo score
    melhor = max(scores.items(), key=lambda x: x[1])
    duzia_prevista, score = melhor

    total = sum(scores.values())
    probabilidade = score / total if total > 0 else 0

    if probabilidade >= prob_minima:
        return duzia_prevista, probabilidade, (peso_freq, peso_tend, peso_rep)
    return None, probabilidade, (peso_freq, peso_tend, peso_rep)







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
duzia_prevista, prob, pesos = prever_duzia_com_feedback()

if duzia_prevista is not None:
    # Exibe pesos dinâmicos no painel
    st.write(f"📊 Pesos dinâmicos → Frequência: {pesos[0]:.2f}, Tendência: {pesos[1]:.2f}, Repetição: {pesos[2]:.2f}")

    # Cria chave única para o alerta
    chave_alerta = f"{duzia_prevista}_{st.session_state.historico[-1]}"

    # Inicializa ultima_chave_alerta se necessário
    if "ultima_chave_alerta" not in st.session_state or st.session_state.ultima_chave_alerta is None:
        st.session_state.ultima_chave_alerta = ""

    # Envia alerta apenas se for nova previsão ou se passaram 3 rodadas sem envio
    if chave_alerta != st.session_state.ultima_chave_alerta or st.session_state.contador_sem_alerta >= 3:
        st.session_state.ultima_entrada = [duzia_prevista]
        st.session_state.tipo_entrada_anterior = "duzia"
        st.session_state.contador_sem_alerta = 0
        st.session_state.ultima_chave_alerta = chave_alerta
        enviar_telegram_async(f"📊 <b>ENTRADA DÚZIA:</b> {duzia_prevista}ª (conf: {prob*100:.1f}%)")
    else:
        # Incrementa contador de rodadas sem alerta
        st.session_state.contador_sem_alerta += 1
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
