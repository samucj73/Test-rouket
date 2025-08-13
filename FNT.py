import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import threading
import matplotlib.pyplot as plt

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
PROB_MINIMA = 0.95
REFRESH_INTERVAL = 10000  # 10 segundos
MAX_HIST_LEN = 500

ROULETTE_ORDER = [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
                  30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
                  29, 7, 28, 12, 35, 3, 26, 0]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top", "total_top", "top2_anterior", "contador_sem_alerta", "tipo_entrada_anterior", "modelo_d", "modelo_c"]:
    if var not in st.session_state:
        # top2_anterior and tipo_entrada_anterior should be list or str, others int
        if var in ["top2_anterior"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        else:
            st.session_state[var] = 0

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === FUNÇÕES ===

def enviar_telegram_async(mensagem):
    """Envia mensagem para o Telegram sem travar Streamlit"""
    def _send():
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)
    threading.Thread(target=_send, daemon=True).start()

def cor(numero):
    if numero == 0: return 'G'
    return 'R' if numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

def distancia_fisica(n1, n2):
    if n1 not in ROULETTE_ORDER or n2 not in ROULETTE_ORDER:
        return 0
    idx1, idx2 = ROULETTE_ORDER.index(n1), ROULETTE_ORDER.index(n2)
    diff = abs(idx1 - idx2)
    return min(diff, len(ROULETTE_ORDER) - diff)

def frequencia_numeros_quentes(janela, top_n=5):
    c = Counter(janela)
    mais_comuns = c.most_common(top_n)
    freq = np.zeros(top_n)
    numeros = np.zeros(top_n)
    total = len(janela)
    for i, (num, cnt) in enumerate(mais_comuns):
        freq[i] = cnt / total
        numeros[i] = num
    return numeros, freq

def blocos_fisicos(numero):
    # Divide a roleta em 3 blocos de 12 números consecutivos na ordem da roleta
    if numero not in ROULETTE_ORDER:
        return 0
    idx = ROULETTE_ORDER.index(numero)
    if idx < 12:
        return 1
    elif idx < 24:
        return 2
    else:
        return 3

def tendencia_pares_impares(janela):
    pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
    impares = sum(1 for n in janela if n != 0 and n % 2 != 0)
    total = len(janela)
    return pares / total, impares / total

def repeticoes_ultimos_n(janela, n=5):
    # Quantas vezes o último número se repetiu nos últimos n elementos
    if len(janela) < n+1:
        return 0
    ultimo = janela[-1]
    return janela[-(n+1):-1].count(ultimo)

def extrair_features(historico):
    historico = list(historico)
    X, y = [], []
    historico_sem_ultimo = historico[:-1]

    for i in range(120, len(historico_sem_ultimo)):
        janela = historico_sem_ultimo[i-120:i]
        ult = historico_sem_ultimo[i-1]

        cores = [cor(n) for n in janela]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')
        pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
        impares = sum(1 for n in janela if n != 0 and n % 2 != 0)

        duzia = (ult - 1) // 12 + 1 if ult != 0 else 0
        coluna = (ult - 1) % 3 + 1 if ult != 0 else 0

        tempo_zero = next((idx for idx, val in enumerate(reversed(janela), 1) if val == 0), len(janela))

        dist_fisica = float(np.mean([distancia_fisica(ult, n) for n in janela[-3:]]))

        # Novas features:
        numeros_quentes, freq_quentes = frequencia_numeros_quentes(janela, top_n=5)
        blocos = blocos_fisicos(ult)
        pares_prop, impares_prop = tendencia_pares_impares(janela)
        repeticoes = repeticoes_ultimos_n(janela, n=5)

        # Construindo vetor de features
        features = [
            vermelhos, pretos, verdes,
            pares, impares,
            duzia, coluna,
            tempo_zero,
            dist_fisica,
            # Novas
            *freq_quentes,    # 5 freq dos top números
            blocos,
            pares_prop,
            impares_prop,
            repeticoes,
        ]
        X.append(features)
        y.append(historico_sem_ultimo[i])
    return np.array(X), np.array(y)

def ajustar_target(y_raw, tipo):
    if tipo == "duzia":
        return np.array([(n - 1) // 12 + 1 if n != 0 else 0 for n in y_raw])
    elif tipo == "coluna":
        return np.array([(n - 1) % 3 + 1 if n != 0 else 0 for n in y_raw])
    else:
        return y_raw

def treinar_modelo_cv(historico, tipo="duzia"):
    if len(historico) < 130:
        return None, None
    X, y_raw = extrair_features(historico)
    if len(X) == 0:
        return None, None
    y = ajustar_target(y_raw, tipo)

    # Ajuste fino de modelos (hiperparâmetros)
    lgb = LGBMClassifier(
        n_estimators=400,
        learning_rate=0.03,
        max_depth=7,
        random_state=42,
        subsample=0.8,
        colsample_bytree=0.8,
    )
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )

    # Validação cruzada para avaliar performance
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    lgb_scores = cross_val_score(lgb, X, y, cv=cv, scoring="accuracy")
    rf_scores = cross_val_score(rf, X, y, cv=cv, scoring="accuracy")

    st.write(f"Validação Cruzada ({tipo}) LGBM Accuracy: {lgb_scores.mean():.4f} ± {lgb_scores.std():.4f}")
    st.write(f"Validação Cruzada ({tipo}) RF Accuracy: {rf_scores.mean():.4f} ± {rf_scores.std():.4f}")

    # Treinar modelo completo depois da validação
    lgb.fit(X, y)
    rf.fit(X, y)
    return (lgb, rf), X, y

def prever_top2(modelos_tuple, historico):
    if modelos_tuple is None or len(historico) < 130:
        return [], [], 0
    X, _ = extrair_features(historico)
    if X.size == 0:
        return [], [], 0
    x = X[-1].reshape(1, -1)
    lgb_model, rf_model = modelos_tuple
    classes = lgb_model.classes_
    try:
        p1 = lgb_model.predict_proba(x)[0]
        p2 = rf_model.predict_proba(x)[0]
        probs = (p1 + p2) / 2
        idxs = np.argsort(probs)[::-1][:2]
        top_labels = [int(classes[i]) for i in idxs]
        top_probs = [float(probs[i]) for i in idxs]
        return top_labels, top_probs, sum(top_probs)
    except Exception as e:
        print("Erro na previsão:", e)
        return [], [], 0

def plot_feature_importances(modelos_tuple, feature_names):
    lgb_model, rf_model = modelos_tuple
    importances_lgb = lgb_model.feature_importances_
    importances_rf = rf_model.feature_importances_

    fig, ax = plt.subplots(figsize=(10,6))
    indices = np.argsort(importances_lgb)[::-1]
    ax.bar(range(len(feature_names)), importances_lgb[indices], alpha=0.6, label='LGBM')
    ax.bar(range(len(feature_names)), importances_rf[indices], alpha=0.4, label='RF')
    ax.set_xticks(range(len(feature_names)))
    ax.set_xticklabels(np.array(feature_names)[indices], rotation=45, ha='right')
    ax.set_title("Importância das Features (LGBM e RF)")
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)

# === INTERFACE ===
st.title("🎯 IA Roleta Avançada - Ensemble LGBM + RF com Validação e Novas Features")
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")

try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

if len(st.session_state.historico) == 0 or numero_atual != st.session_state.historico[-1]:
    st.session_state.historico.append(numero_atual)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)

    # Atualiza métricas e envia resultado anterior
    if st.session_state.top2_anterior:
        st.session_state.total_top += 1
        entrada_tipo = st.session_state.tipo_entrada_anterior
        valor = (numero_atual - 1) // 12 + 1 if entrada_tipo == "duzia" else (numero_atual - 1) % 3 + 1
        if valor in st.session_state.top2_anterior:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🟢")
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🔴")

    # Treina modelos com validação cruzada e exibe métricas
    modelos_d, Xd, yd = treinar_modelo_cv(st.session_state.historico, "duzia")
    modelos_c, Xc, yc = treinar_modelo_cv(st.session_state.historico, "coluna")

    st.session_state.modelo_d = modelos_d
    st.session_state.modelo_c = modelos_c

    # Mostra gráfico importância das features, se possível
    feature_names = [
        "Vermelhos", "Pretos", "Verdes",
        "Pares", "Impares",
        "Dúzia", "Coluna",
        "TempoDesdeZero",
        "Distância Física",
        "Freq Q1", "Freq Q2", "Freq Q3", "Freq Q4", "Freq Q5",
        "Bloco Físico",
        "Prop Pares", "Prop Ímpares",
        "Repetições Últ 5"
    ]
    if modelos_d is not None:
        st.subheader("Importância das Features - Dúzia")
        plot_feature_importances(modelos_d, feature_names)

    if modelos_c is not None:
        st.subheader("Importância das Features - Coluna")
        plot_feature_importances(modelos_c, feature_names)

    # Faz previsão e decide qual enviar
    if modelos_d and modelos_c:
        top_d, probs_d, soma_d = prever_top2(modelos_d, st.session_state.historico)
        top_c, probs_c, soma_c = prever_top2(modelos_c, st.session_state.historico)
        if soma_d >= soma_c:
            tipo, top, soma_prob = "duzia", top_d, soma_d
        else:
            tipo, top, soma_prob = "coluna", top_c, soma_c

        # Envio otimizado de alertas
        if soma_prob >= PROB_MINIMA:
            alerta_novo = (top != st.session_state.top2_anterior) or (tipo != st.session_state.tipo_entrada_anterior)
            if alerta_novo:
                st.session_state.top2_anterior = top
                st.session_state.tipo_entrada_anterior = tipo
                st.session_state.contador_sem_alerta = 0
                enviar_telegram_async(f"📊 <b>ENTRADA {tipo.upper()}S:</b> {top[0]}ª e {top[1]}ª (conf: {soma_prob:.2%})")
            else:
                st.session_state.contador_sem_alerta += 1
                if st.session_state.contador_sem_alerta >= 3:
                    st.session_state.contador_sem_alerta = 0
                    enviar_telegram_async(f"📊 <b>ENTRADA {tipo.upper()}S (forçada):</b> {top[0]}ª e {top[1]}ª")

# Interface limpa
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos números:", list(st.session_state.historico)[-12:])

# Salva estado
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "top2_anterior": st.session_state.top2_anterior,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior
}, ESTADO_PATH)
