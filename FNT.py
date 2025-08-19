import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

HIST_NUM_PATH = Path("historico_numeros.pkl")  # salvamos números crus
ESTADO_PATH   = Path("estado.pkl")

MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # ms (5s)
WINDOW_SIZE_DEFAULT = 100

# =========================
# CARREGAR ESTADO / SESSION
# =========================
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try:
        ESTADO_PATH.unlink()
    except Exception:
        pass
    estado_salvo = {}

if "historico_numeros" not in st.session_state:
    st.session_state.historico_numeros = joblib.load(HIST_NUM_PATH) if HIST_NUM_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

# variáveis de controle
defaults = {
    "ultimo_numero_salvo": None,
    "ultimo_resultado_numero": None,
    "acertos_top": 0,
    "total_top": 0,
    "contador_sem_alerta": 0,
    "ultima_entrada": [],                 # lista de classes (ex.: [1,3])
    "tipo_entrada_anterior": "",          # "duzia" ou "coluna"
    "ultima_chave_alerta": None,
    "modelo_rf_duzia": None,
    "modelo_rf_coluna": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# rehidrata estado salvo
for k, v in estado_salvo.items():
    st.session_state[k] = v

# =========================
# INTERFACE
# =========================
st.title("🎯 IA Roleta — Auto (2 Dúzias OU 2 Colunas) com RF + Features Avançadas")
tamanho_janela = st.slider("📏 Tamanho da janela (features)", 20, 150, value=WINDOW_SIZE_DEFAULT, step=2)
prob_minima = st.slider("📊 Probabilidade mínima para alertar (%)", 0, 100, value=0) / 100.0
st.caption("Obs.: O app escolherá automaticamente entre Dúzias ou Colunas com base na maior **soma das 2 probabilidades**.")

# =========================
# FUNÇÕES BASE
# =========================
def enviar_telegram_async(mensagem, delay=0):
    def _send():
        if delay > 0:
            import time; time.sleep(delay)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Erro Telegram:", e)
    threading.Thread(target=_send, daemon=True).start()

def numero_para_duzia(n: int) -> int:
    if n == 0: return 0
    if 1 <= n <= 12: return 1
    if 13 <= n <= 24: return 2
    return 3

def numero_para_coluna(n: int) -> int:
    if n == 0: return 0
    r = n % 3
    if r == 1: return 1  # 1ª coluna: 1,4,7,...,34
    if r == 2: return 2  # 2ª coluna: 2,5,8,...,35
    return 3              # 3ª coluna: 3,6,9,...,36

def salvar_numero(numero: int):
    st.session_state.historico_numeros.append(numero)
    joblib.dump(st.session_state.historico_numeros, HIST_NUM_PATH)

# =========================
# FEATURES GENÉRICAS
# =========================
def criar_features_de_seq(seq_labels, window_size):
    """
    Gera (X, y) a partir de uma sequência de rótulos (1..3, com 0 possível).
    Usa features avançadas, consistente entre treino e predição.
    """
    if len(seq_labels) < window_size + 5:
        return None, None

    X, y = [], []
    S = list(seq_labels)

    for i in range(len(S) - window_size):
        janela = S[i:i+window_size]
        alvo = S[i+window_size]

        feats = []

        # 1) Sequência direta (os próprios rótulos da janela)
        feats.extend(janela)

        # 2) Frequências simples de 1,2,3 (ignora 0)
        contador = Counter(janela)
        for d in [1,2,3]:
            feats.append(contador.get(d, 0) / window_size)

        # 3) Frequência ponderada na janela inteira
        pesos = np.array([0.9**k for k in range(window_size-1, -1, -1)])
        pesos_sum = pesos.sum()
        for d in [1,2,3]:
            fw = sum(w for val, w in zip(janela, pesos) if val == d) / pesos_sum
            feats.append(fw)

        # 4) Frequência ponderada nas últimas 20 (ou menor se a janela tiver menos)
        ult = janela[-20:] if window_size >= 20 else janela
        if len(ult) == 0:
            ult = janela
        pesos20 = np.array([0.9**k for k in range(len(ult)-1, -1, -1)])
        s20 = pesos20.sum() if pesos20.sum() != 0 else 1.0
        for d in [1,2,3]:
            feats.append(sum(w for val, w in zip(ult, pesos20) if val == d) / s20)

        # 5) Alternâncias simples e ponderadas
        if window_size > 1:
            alt_simples = sum(1 for j in range(1, window_size) if janela[j] != janela[j-1]) / (window_size - 1)
            denom = sum(0.9**k for k in range(window_size-1))
            alt_pond = sum((janela[j] != janela[j-1]) * (0.9**(window_size-1-j)) for j in range(1, window_size)) / (denom if denom != 0 else 1)
        else:
            alt_simples, alt_pond = 0.0, 0.0
        feats.extend([alt_simples, alt_pond])

        # 6) Tendência normalizada + spread
        tend = [0.0, 0.0, 0.0]
        for val, w in zip(janela, pesos):
            if val in [1,2,3]:
                tend[val-1] += w
        total_tend = sum(tend) if sum(tend) > 0 else 1.0
        feats.extend([t/total_tend for t in tend])
        feats.append((max(tend) - min(tend)) if len(tend) else 0.0)

        # 7) Proporção de zeros (0 não pertence)
        feats.append(janela.count(0) / window_size)

        # 8) Última ocorrência normalizada de cada classe (1..3)
        for d in [1,2,3]:
            try:
                idx = window_size - 1 - janela[::-1].index(d)
                feats.append(idx / window_size)
            except ValueError:
                feats.append(1.0)

        # 9) Frequência nas últimas 5
        ult5 = janela[-5:] if window_size >= 5 else janela
        for d in [1,2,3]:
            feats.append(ult5.count(d) / (len(ult5) if len(ult5) else 1))

        X.append(feats)
        y.append(alvo)

    return np.array(X), np.array(y)


def montar_seq(labels_func, numeros):
    """Converte a lista de números crus em rótulos (dúzia ou coluna)"""
    return [labels_func(n) for n in numeros]

# =========================
# TREINAMENTO
# =========================
def treinar_modelos_rf():
    numeros = list(st.session_state.historico_numeros)
    if len(numeros) < tamanho_janela + 10:
        return

    # Dúzia
    seq_duzia = montar_seq(numero_para_duzia, numeros)
    Xd, yd = criar_features_de_seq(seq_duzia, tamanho_janela)
    if Xd is not None and len(Xd) > 0:
        rf_d = RandomForestClassifier(
            n_estimators=700,
            max_depth=14,
            min_samples_leaf=1,
            max_features="sqrt",
            random_state=42,
            class_weight="balanced_subsample",
            n_jobs=-1
        )
        rf_d.fit(Xd, yd)
        st.session_state.modelo_rf_duzia = rf_d

    # Coluna
    seq_col = montar_seq(numero_para_coluna, numeros)
    Xc, yc = criar_features_de_seq(seq_col, tamanho_janela)
    if Xc is not None and len(Xc) > 0:
        rf_c = RandomForestClassifier(
            n_estimators=700,
            max_depth=14,
            min_samples_leaf=1,
            max_features="sqrt",
            random_state=42,
            class_weight="balanced_subsample",
            n_jobs=-1
        )
        rf_c.fit(Xc, yc)
        st.session_state.modelo_rf_coluna = rf_c

# =========================
# PREVISÃO (TOP-2)
# =========================
def _features_atual(seq_labels, window_size):
    """Gera o vetor de features para a janela corrente."""
    janela = seq_labels[-window_size:]
    if len(janela) < window_size:
        return None

    feats = []
    # 1) sequência direta
    feats.extend(janela)

    # 2) frequência simples
    cont = Counter(janela)
    for d in [1,2,3]:
        feats.append(cont.get(d, 0)/window_size)

    # 3) ponderada janela inteira
    pesos = np.array([0.9**k for k in range(window_size-1, -1, -1)])
    s = pesos.sum()
    for d in [1,2,3]:
        feats.append(sum(w for val, w in zip(janela, pesos) if val == d) / (s if s != 0 else 1))

    # 4) ponderada últimas 20
    ult = janela[-20:] if window_size >= 20 else janela
    pesos20 = np.array([0.9**k for k in range(len(ult)-1,-1,-1)])
    s20 = pesos20.sum() if pesos20.sum() != 0 else 1.0
    for d in [1,2,3]:
        feats.append(sum(w for val, w in zip(ult, pesos20) if val == d) / s20)

    # 5) alternâncias
    if window_size > 1:
        alt_s = sum(1 for j in range(1, window_size) if janela[j] != janela[j-1])/(window_size-1)
        denom = sum(0.9**k for k in range(window_size-1))
        alt_p = sum((janela[j]!=janela[j-1])*(0.9**(window_size-1-j)) for j in range(1,window_size)) / (denom if denom!=0 else 1)
    else:
        alt_s, alt_p = 0.0, 0.0
    feats.extend([alt_s, alt_p])

    # 6) tendência + spread
    tend = [0.0,0.0,0.0]
    for val,w in zip(janela, pesos):
        if val in [1,2,3]:
            tend[val-1]+=w
    total_t = sum(tend) if sum(tend)>0 else 1.0
    feats.extend([t/total_t for t in tend])
    feats.append((max(tend)-min(tend)) if len(tend) else 0.0)

    # 7) zeros
    feats.append(janela.count(0)/window_size)

    # 8) última ocorrência
    for d in [1,2,3]:
        try:
            idx = window_size - 1 - janela[::-1].index(d)
            feats.append(idx/window_size)
        except ValueError:
            feats.append(1.0)

    # 9) últimas 5
    ult5 = janela[-5:] if window_size >= 5 else janela
    for d in [1,2,3]:
        feats.append(ult5.count(d)/(len(ult5) if len(ult5) else 1))

    return np.array(feats).reshape(1, -1)

def prever_top2(seq_labels, modelo_rf):
    """
    Retorna (classes_top2:list[int], probs_top2:list[float]) filtrando 0 (se existir).
    """
    if modelo_rf is None:
        return None, None
    feats = _features_atual(seq_labels, tamanho_janela)
    if feats is None:
        return None, None
    try:
        probs = modelo_rf.predict_proba(feats)[0]
        classes = modelo_rf.classes_
    except Exception as e:
        st.warning(f"Erro na predição RF: {e}")
        return None, None

    # mapeia classe->prob
    mapa = {int(c): float(p) for c, p in zip(classes, probs)}
    # remove classe 0 (zero) do ranqueamento de aposta
    for zero_key in [0]:
        if zero_key in mapa:
            mapa[zero_key] = -1.0

    if len(mapa) == 0:
        return None, None

    ordenado = sorted(mapa.items(), key=lambda kv: kv[1], reverse=True)
    top = ordenado[:2]
    top_classes = [t[0] for t in top]
    top_probs = [max(0.0, t[1]) for t in top]  # garante não-negativo após filtro do 0
    return top_classes, top_probs

# =========================
# LOOP PRINCIPAL
# =========================
# 1) Puxa número da API
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# 2) Atualiza histórico uma vez por número novo
if numero_atual != st.session_state.ultimo_numero_salvo:
    salvar_numero(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual

    # Re-treina a cada 10 novas entradas (quando há histórico suficiente)
    if len(st.session_state.historico_numeros) >= tamanho_janela + 10 and (len(st.session_state.historico_numeros) % 10 == 0):
        treinar_modelos_rf()

# 3) ALERTA DE RESULTADO (GREEN/RED) — 1x por rodada
if st.session_state.ultimo_resultado_numero != numero_atual:
    st.session_state.ultimo_resultado_numero = numero_atual

    if st.session_state.ultima_entrada:
        st.session_state.total_top += 1
        tipo = st.session_state.tipo_entrada_anterior

        if tipo == "duzia":
            valor = numero_para_duzia(numero_atual)
        elif tipo == "coluna":
            valor = numero_para_coluna(numero_atual)
        else:
            valor = None

        if valor is not None and valor in st.session_state.ultima_entrada:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({tipo.capitalize()} {valor}) — 🟢 GREEN", delay=1)
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({tipo.capitalize()} {valor}) — 🔴 RED", delay=1)

# 4) PREVISÃO (apenas se modelos prontos e janela suficiente)
nums = list(st.session_state.historico_numeros)
if len(nums) >= tamanho_janela and (st.session_state.modelo_rf_duzia or st.session_state.modelo_rf_coluna):

    seq_duzia = montar_seq(numero_para_duzia, nums)
    seq_coluna = montar_seq(numero_para_coluna, nums)

    # Top-2 de cada categoria
    top_d, prob_d = prever_top2(seq_duzia, st.session_state.modelo_rf_duzia)
    top_c, prob_c = prever_top2(seq_coluna, st.session_state.modelo_rf_coluna)

    # Soma de probabilidades (se alguma for None, trata como -inf para não escolher)
    soma_d = sum(prob_d) if prob_d else -1.0
    soma_c = sum(prob_c) if prob_c else -1.0

    # Escolha automática: maior soma
    if soma_d >= soma_c:
        tipo_escolhido = "duzia"
        classes = top_d
        probs = prob_d
    else:
        tipo_escolhido = "coluna"
        classes = top_c
        probs = prob_c

    # Validação de existência e limiar
    pode_alertar = (classes is not None) and (len(classes) == 2)
    if pode_alertar and (max(probs) >= prob_minima or prob_minima <= 0):

        chave_atual = f"{tipo_escolhido}_{classes[0]}_{classes[1]}"

        # Regra: só manda se for diferente do último OU após 3 rodadas sem alertar
        if (st.session_state.ultima_chave_alerta != chave_atual) or (st.session_state.contador_sem_alerta >= 3):
            st.session_state.ultima_entrada = classes
            st.session_state.tipo_entrada_anterior = tipo_escolhido
            st.session_state.ultima_chave_alerta = chave_atual
            st.session_state.contador_sem_alerta = 0

            if tipo_escolhido == "duzia":
                msg = (
                    f"📊 <b>ENTRADA (DÚZIA)</b>\n"
                    f"➡️ {classes[0]}ª ({probs[0]*100:.1f}%)\n"
                    f"➡️ {classes[1]}ª ({probs[1]*100:.1f}%)"
                )
            else:
                msg = (
                    f"📊 <b>ENTRADA (COLUNA)</b>\n"
                    f"➡️ {classes[0]}ª ({probs[0]*100:.1f}%)\n"
                    f"➡️ {classes[1]}ª ({probs[1]*100:.1f}%)"
                )

            # Envia previsão com pequeno delay para separar do resultado
            enviar_telegram_async(msg, delay=10)
        else:
            st.session_state.contador_sem_alerta += 1

# =========================
# INTERFACE (STATUS)
# =========================
st.write("🎰 Último número:", numero_atual)
st.write(f"✅ Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
ult_duzias = [numero_para_duzia(n) for n in list(st.session_state.historico_numeros)[-12:]]
ult_colunas = [numero_para_coluna(n) for n in list(st.session_state.historico_numeros)[-12:]]
st.write("🧾 Últimos (números):", list(st.session_state.historico_numeros)[-12:])
st.write("📌 Últimos (dúzias):", ult_duzias)
st.write("📌 Últimos (colunas):", ult_colunas)

# =========================
# SALVAR ESTADO
# =========================
joblib.dump({
    "ultimo_numero_salvo": st.session_state.ultimo_numero_salvo,
    "ultimo_resultado_numero": st.session_state.ultimo_resultado_numero,
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "ultima_entrada": st.session_state.ultima_entrada,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "ultima_chave_alerta": st.session_state.ultima_chave_alerta,
    "modelo_rf_duzia": st.session_state.modelo_rf_duzia,
    "modelo_rf_coluna": st.session_state.modelo_rf_coluna,
}, ESTADO_PATH)

# =========================
# AUTO-REFRESH
# =========================
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")
