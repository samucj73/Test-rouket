import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # 5 segundos
WINDOW_SIZE = 15         # janela para features
TRAIN_EVERY = 10         # treinar a cada N rodadas novas

# === CARREGA ESTADO ===
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try:
        ESTADO_PATH.unlink()
    except Exception:
        pass
    estado_salvo = {}

# === SESSION STATE ===
if "ultimo_numero_salvo" not in st.session_state:
    st.session_state.ultimo_numero_salvo = None
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "contador_sem_alerta", "tipo_entrada_anterior",
            "padroes_certos", "ultima_entrada", "modelo_rf", "ultimo_resultado_numero"]:
    if var not in st.session_state:
        if var in ["padroes_certos", "ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        elif var == "modelo_rf":
            st.session_state[var] = None
        else:
            st.session_state[var] = 0

# Restaura contadores e chaves do estado salvo (sem carregar modelo do disco)
for k, v in estado_salvo.items():
    st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (CatBoost + Features Avançadas)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", min_value=5, max_value=150, value=WINDOW_SIZE)
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
    # garante deque com maxlen
    if not isinstance(st.session_state.historico, deque):
        st.session_state.historico = deque(st.session_state.historico, maxlen=MAX_HIST_LEN)
    st.session_state.historico.append(duzia)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)
    return duzia

# === FEATURES ===
def extrair_features(janela):
    features = []
    window_size = len(janela)

    # Sequência direta (codificação barata)
    features.extend(janela)

    # Frequência simples
    contador = Counter(janela)
    for d in [1, 2, 3]:
        features.append(contador.get(d, 0) / window_size)

    # Frequência ponderada (decay 0.9)
    pesos = np.array([0.9**i for i in range(window_size-1, -1, -1)])
    s_pesos = float(pesos.sum()) if pesos.sum() > 0 else 1.0
    for d in [1, 2, 3]:
        fw = sum(w for val, w in zip(janela, pesos) if val == d) / s_pesos
        features.append(fw)

    # Alternância simples e ponderada
    if window_size > 1:
        alternancias = sum(1 for j in range(1, window_size) if janela[j] != janela[j-1])
        features.append(alternancias / (window_size - 1))
        den = sum(0.9**i for i in range(window_size - 1)) or 1.0
        features.append(sum((janela[j] != janela[j-1]) * 0.9**(window_size - 1 - j)
                            for j in range(1, window_size)) / den)
    else:
        features.extend([0.0, 0.0])

    # Tendência normalizada
    tend = [0.0, 0.0, 0.0]
    for val, w in zip(janela, pesos):
        if val in [1, 2, 3]:
            tend[val - 1] += float(w)
    total = sum(tend) if sum(tend) > 0 else 1.0
    features.extend([t / total for t in tend])
    features.append((max(tend) - min(tend)) if tend else 0.0)

    # Contagem de zeros
    features.append(janela.count(0) / window_size)

    # Última ocorrência de cada dúzia
    for d in [1, 2, 3]:
        try:
            idx = window_size - 1 - janela[::-1].index(d)
        except ValueError:
            idx = window_size
        features.append(idx / window_size)

    # Últimas 5 rodadas (ou menos, normalizado)
    k = min(5, window_size)
    ultk = janela[-k:]
    for d in [1, 2, 3]:
        features.append(ultk.count(d) / k)

    return features

# === DATASET (X, y) ===
def criar_dataset_features(historico, janela_size):
    X, y = [], []
    hist = list(historico)
    if len(hist) <= janela_size:
        return np.array(X), np.array(y)
    for i in range(len(hist) - janela_size):
        janela = hist[i:i + janela_size]
        alvo = hist[i + janela_size]  # próxima dúzia
        if alvo in [1, 2, 3]:  # ignora zeros como alvo
            X.append(extrair_features(janela))
            y.append(alvo)
    return np.array(X), np.array(y)

# === TREINAMENTO ===
def treinar_modelo_rf():
    X, y = criar_dataset_features(st.session_state.historico, tamanho_janela)
    if len(y) > 1 and len(set(y)) > 1 and len(X) == len(y):
        modelo = CatBoostClassifier(
            iterations=200,
            depth=6,
            learning_rate=0.1,
            loss_function='MultiClass',
            verbose=False
        )
        try:
            modelo.fit(X, y)
            st.session_state.modelo_rf = modelo
            return True
        except Exception as e:
            st.warning(f"Erro ao treinar modelo: {e}")
            return False
    return False

# === PREVISÃO ===
def prever_duzia_rf():
    janela = list(st.session_state.historico)[-tamanho_janela:]
    if len(janela) < tamanho_janela or st.session_state.modelo_rf is None:
        return None, None
    features = np.array(extrair_features(janela)).reshape(1, -1)
    try:
        probs = st.session_state.modelo_rf.predict_proba(features)[0]
        classes = st.session_state.modelo_rf.classes_
    except Exception as e:
        st.warning(f"Erro na predição: {e}")
        return None, None

    # Ordena top-2
    top_idxs = np.argsort(probs)[-2:][::-1]
    top_duzias = list(classes[top_idxs])
    top_probs = list(probs[top_idxs])
    return top_duzias, top_probs

# === LOOP PRINCIPAL (API) ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# Atualiza histórico e (eventualmente) re-treina
historico_len_antes = len(st.session_state.historico)
if numero_atual != st.session_state.ultimo_numero_salvo:
    duzia_atual = salvar_historico_duzia(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual

    # treina a cada TRAIN_EVERY inserções novas
    if len(st.session_state.historico) >= tamanho_janela + 2 and (len(st.session_state.historico) % TRAIN_EVERY == 0):
        treinar_modelo_rf()

# === ALERTA DE RESULTADO (com emojis) ===
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual

    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        valor = numero_para_duzia(numero_atual)
        if valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🟢", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª dúzia): 🔴", delay=1)

    # === PREVISÃO + ANTI-SPAM + PROB MÍNIMA (entrada sem emojis) ===
    if st.session_state.modelo_rf is not None and len(st.session_state.historico) >= tamanho_janela:
        try:
            duzias_previstas, probs = prever_duzia_rf()
            if duzias_previstas is not None and len(duzias_previstas) == 2:
                # aplica prob mínima: só se alguma das duas >= limiar
                if max(probs) >= prob_minima:
                    chave_atual = f"duzia_{duzias_previstas[0]}_{duzias_previstas[1]}"

                    if (chave_atual != st.session_state.ultima_chave_alerta) or (st.session_state.contador_sem_alerta >= 3):
                        st.session_state.ultima_entrada = duzias_previstas
                        st.session_state.tipo_entrada_anterior = "duzia"
                        st.session_state.contador_sem_alerta = 0
                        st.session_state.ultima_chave_alerta = chave_atual

                        mensagem_alerta = (
                            f"📊 <b>ENT DÚZIA:</b> {duzias_previstas[0]} / {duzias_previstas[1]}"
                            f" (conf: {probs[0]*100:.1f}% / {probs[1]*100:.1f}%)"
                        )
                        enviar_telegram_async(mensagem_alerta, delay=5)
                    else:
                        # mesma entrada repetida -> não envia agora
                        st.session_state.contador_sem_alerta += 1
                else:
                    # prob abaixo do limiar -> não envia
                    st.session_state.contador_sem_alerta += 1
        except Exception as e:
            st.warning(f"Erro na previsão: {e}")

# === INTERFACE ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])

# === SALVA ESTADO (NÃO salva o modelo!) ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "ultima_entrada": st.session_state.ultima_entrada,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "padroes_certos": st.session_state.padroes_certos,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero
}, ESTADO_PATH)

# === AUTO REFRESH ===
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
