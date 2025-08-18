import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 5 segundos
WINDOW_SIZE = 100  # janela para RF

# === CONFIGURAÇÕES DE ESTADO ===
try:
    if ESTADO_PATH.exists():
        estado_salvo = joblib.load(ESTADO_PATH)
    else:
        estado_salvo = {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try:
        ESTADO_PATH.unlink()
    except Exception:
        pass
    estado_salvo = {}

# === SESSION STATE ===
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior", "padroes_certos", "ultima_entrada", "modelo_rf", "ultimo_resultado_numero", "ultimo_numero_salvo"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var in ["tipo_entrada_anterior"]:
            st.session_state[var] = ""
        elif var in ["modelo_rf"]:
            st.session_state[var] = None
        else:
            st.session_state[var] = 0

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (RF + Features Avançadas)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=2, max_value=250, value=WINDOW_SIZE)
prob_minima = st.slider("📊 Probabilidade mínima (%)", min_value=10, max_value=100, value=30) / 100.0

# === FUNÇÕES AUXILIARES ===
def enviar_telegram_async(mensagem, delay=0):
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)

    if delay > 0:
        threading.Timer(delay, _send).start()
    else:
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

def salvar_historico_duzia(numero):
    duzia = numero_para_duzia(numero)
    st.session_state.historico.append(duzia)  # sempre salva
    joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

# === FEATURES AVANÇADAS ===
def criar_features_avancadas(historico, window_size):
    if len(historico) < window_size + 5:
        return None, None
    X, y = [], []
    seq = list(historico)

    for i in range(len(seq) - window_size):
        janela = seq[i:i+window_size]
        alvo = seq[i+window_size]
        features = []

        # Sequência direta
        features.extend(janela)

        # Frequências
        contador = Counter(janela)
        for d in [1,2,3]:
            features.append(contador.get(d, 0)/window_size)

        # Frequência ponderada
        pesos = np.array([0.9**i for i in range(window_size-1, -1, -1)])
        for d in [1,2,3]:
            fw = sum(w for val, w in zip(janela, pesos) if val==d)/pesos.sum()
            features.append(fw)

        # Alternância simples e ponderada
        alternancias = sum(1 for j in range(1, window_size) if janela[j] != janela[j-1])
        features.append(alternancias/(window_size-1))
        features.append(sum((janela[j]!=janela[j-1])*0.9**(window_size-1-j) for j in range(1, window_size))/sum(0.9**i for i in range(window_size-1)))

        # Tendência
        tend = [0,0,0]
        for val, w in zip(janela, pesos):
            if val in [1,2,3]:
                tend[val-1] += w
        total = sum(tend) if sum(tend) > 0 else 1
        features.extend([t/total for t in tend])
        features.append(max(tend)-min(tend))
        features.append(janela.count(0)/window_size)

        # Última ocorrência de cada dúzia
        for d in [1,2,3]:
            try:
                idx = window_size - 1 - janela[::-1].index(d)
                features.append(idx/window_size)
            except ValueError:
                features.append(1.0)

        # Frequência últimas 5
        ultimos5 = janela[-5:]
        for d in [1,2,3]:
            features.append(ultimos5.count(d)/5)

        X.append(features)
        y.append(alvo)

    return np.array(X), np.array(y)

# === TREINAMENTO DO MODELO ===
def treinar_modelo_rf():
    X, y = criar_features_avancadas(st.session_state.historico, window_size=tamanho_janela)
    if X is None or len(X) == 0:
        return
    rf = RandomForestClassifier(
        n_estimators=400,
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
        class_weight="balanced_subsample"
    )
    rf.fit(X, y)
    st.session_state.modelo_rf = rf

# === PREVISÃO ===
def prever_duzia_rf():
    janela = list(st.session_state.historico)[-tamanho_janela:]
    features = []

    # Sequência
    features.extend(janela)

    # Frequências
    contador = Counter(janela)
    for d in [1,2,3]:
        features.append(contador.get(d, 0)/tamanho_janela)

    # Frequência ponderada
    pesos = np.array([0.9**i for i in range(tamanho_janela-1, -1, -1)])
    for d in [1,2,3]:
        fw = sum(w for val, w in zip(janela, pesos) if val==d)/pesos.sum()
        features.append(fw)

    # Alternância
    alternancias = sum(1 for j in range(1, tamanho_janela) if janela[j] != janela[j-1])
    features.append(alternancias/(tamanho_janela-1))
    features.append(sum((janela[j]!=janela[j-1])*0.9**(tamanho_janela-1-j) for j in range(1, tamanho_janela))/sum(0.9**i for i in range(tamanho_janela-1)))

    # Tendência
    tend = [0,0,0]
    for val, w in zip(janela, pesos):
        if val in [1,2,3]:
            tend[val-1] += w
    total = sum(tend) if sum(tend) > 0 else 1
    tend_norm = [t/total for t in tend]
    features.extend(tend_norm)
    features.append(max(tend_norm)-min(tend_norm))
    features.append(janela.count(0)/tamanho_janela)

    # === PREVISÃO ===
    features = np.array(features).reshape(1, -1)
    probs = st.session_state.modelo_rf.predict_proba(features)[0]
    classes = st.session_state.modelo_rf.classes_

    # Top 2
    top2_idx = np.argsort(probs)[-2:][::-1]
    top2 = [(classes[i], probs[i]) for i in top2_idx]
    return top2

# === LOOP PRINCIPAL ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico apenas se novo número
if numero_atual != st.session_state.ultimo_numero_salvo:
    duzia_atual = salvar_historico_duzia(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual
    if len(st.session_state.historico) % 10 == 0:
        treinar_modelo_rf()

# === ALERTA DE RESULTADO + PREVISÃO ===
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual  

    # RESULTADO
    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor = numero_para_duzia(numero_atual)
        if valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia) → PREVISTO 🟢", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia) → NÃO PREVISTO 🔴", delay=1)

    # PREVISÃO
    if st.session_state.modelo_rf is not None and len(st.session_state.historico) >= tamanho_janela:
        try:
            top2 = prever_duzia_rf()
            if top2:
                duzias = [d for d, _ in top2]
                st.session_state.ultima_entrada = duzias
                st.session_state.tipo_entrada_anterior = "duzia"
                st.session_state.contador_sem_alerta = 0
                st.session_state.ultima_chave_alerta = f"duzia_{duzias}"

                mensagem_alerta = "📊 <b>ENTRADA DÚZIA RF:</b>\n"
                for d, p in top2:
                    mensagem_alerta += f"- {d}ª dúzia ({p*100:.1f}%)\n"
                enviar_telegram_async(mensagem_alerta, delay=10)
        except Exception as e:
            st.warning(f"Erro na previsão: {e}")

# === INTERFACE ===
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
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "modelo_rf": st.session_state.modelo_rf,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero,
    "ultimo_numero_salvo": st.session_state.ultimo_numero_salvo
}, ESTADO_PATH)

# Auto-refresh
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
