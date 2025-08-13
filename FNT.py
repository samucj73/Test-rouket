import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from collections import deque, Counter, defaultdict
from streamlit_autorefresh import st_autorefresh
from pathlib import Path
import threading
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_PATH = Path("historico.pkl")
ESTADO_PATH = Path("estado.pkl")
REFRESH_INTERVAL = 10000  # 10s
MAX_HIST_LEN = 800        # um pouco maior p/ features temporais
RETRAIN_EVERY = 10        # ### NOVO: re-treinar RF/LGBM só a cada N giros

# Limites da PROB dinâmica
PROB_MIN_BASE = 0.80
PROB_MIN_MAX = 0.90
PROB_MIN_MIN = 0.65

# Janela para métrica dinâmica
JANELA_METRICAS = 30

ROULETTE_ORDER = [32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
                  30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
                  29, 7, 28, 12, 35, 3, 26, 0]

# === SESSION STATE ===
if "historico" not in st.session_state:
    st.session_state.historico = joblib.load(HISTORICO_PATH) if HISTORICO_PATH.exists() else deque(maxlen=MAX_HIST_LEN)

defaults = {
    "acertos_top": 0, "total_top": 0,
    "top2_anterior": [], "contador_sem_alerta": 0, "tipo_entrada_anterior": "",
    "modelo_d": None, "modelo_c": None,                 # (LGBM, RF)
    "sgd_d": None, "sgd_c": None,                       # ### NOVO: modelos online
    "rounds_desde_retrain": 0,
    "metricas_janela": deque(maxlen=JANELA_METRICAS),   # lista de dicts com {tipo, soma_prob, hit}
    "hit_rate_por_tipo": {"duzia": deque(maxlen=JANELA_METRICAS),
                          "coluna": deque(maxlen=JANELA_METRICAS)},
    "cv_scores": {"duzia": {"lgb": 0.5, "rf": 0.5}, "coluna": {"lgb": 0.5, "rf": 0.5}},  # iniciais
    "prob_minima_dinamica": PROB_MIN_BASE
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if ESTADO_PATH.exists():
    estado_salvo = joblib.load(ESTADO_PATH)
    for k, v in estado_salvo.items():
        st.session_state[k] = v

# === FUNÇÕES ===

def enviar_telegram_async(mensagem):
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

def get_neighbors(number, k=2):
    """Retorna k vizinhos físicos anteriores e posteriores na ordem da roleta."""
    if number not in ROULETTE_ORDER: return []
    idx = ROULETTE_ORDER.index(number)
    n = len(ROULETTE_ORDER)
    viz = []
    for i in range(1, k+1):
        viz.append(ROULETTE_ORDER[(idx - i) % n])
        viz.append(ROULETTE_ORDER[(idx + i) % n])
    return viz

def frequencia_numeros_quentes(janela, top_n=5):
    c = Counter(janela)
    mais_comuns = c.most_common(top_n)
    freq = np.zeros(top_n)
    numeros = np.zeros(top_n)
    total = len(janela) if len(janela) > 0 else 1
    for i, (num, cnt) in enumerate(mais_comuns):
        freq[i] = cnt / total
        numeros[i] = num
    return numeros, freq

def blocos_fisicos(numero):
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
    total = len(janela) if len(janela) > 0 else 1
    pares = sum(1 for n in janela if n != 0 and n % 2 == 0)
    impares = sum(1 for n in janela if n != 0 and n % 2 != 0)
    return pares / total, impares / total

def repeticoes_ultimos_n(janela, n=5):
    if len(janela) < n+1:
        return 0
    ultimo = janela[-1]
    return janela[-(n+1):-1].count(ultimo)

def freq_duzia_coluna_ultimos(janela, k=10):
    """### NOVO: frequência de cada dúzia e coluna na janela curta (k)."""
    sub = list(janela[-k:]) if len(janela) >= 1 else []
    if not sub: return [0,0,0],[0,0,0]
    duzias = [((n - 1)//12 + 1) if n != 0 else 0 for n in sub]
    colunas = [((n - 1)%3 + 1) if n != 0 else 0 for n in sub]
    fd = [duzias.count(1)/len(sub), duzias.count(2)/len(sub), duzias.count(3)/len(sub)]
    fc = [colunas.count(1)/len(sub), colunas.count(2)/len(sub), colunas.count(3)/len(sub)]
    return fd, fc

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
        dist_fisica = float(np.mean([distancia_fisica(ult, n) for n in janela[-3:]])) if len(janela) >= 3 else 0.0

        # Novas features:
        numeros_quentes, freq_quentes = frequencia_numeros_quentes(janela, top_n=5)
        blocos = blocos_fisicos(ult)
        pares_prop, impares_prop = tendencia_pares_impares(janela)
        repeticoes = repeticoes_ultimos_n(janela, n=5)

        # ### NOVO: frequências curtas
        fd, fc = freq_duzia_coluna_ultimos(janela, k=10)

        # ### NOVO: vizinhos físicos do último
        viz = get_neighbors(ult, k=2)
        viz_cores = [cor(n) for n in viz]
        viz_r = viz_cores.count('R'); viz_b = viz_cores.count('B'); viz_g = viz_cores.count('G')

        features = [
            vermelhos, pretos, verdes,
            pares, impares,
            duzia, coluna,
            tempo_zero,
            dist_fisica,
            # Frequência de números quentes
            *freq_quentes,    # 5
            blocos,
            pares_prop, impares_prop,
            repeticoes,
            # Frequências curtas (duzias e colunas 3+3)
            *fd, *fc,
            # Vizinhos (contagem por cor)
            viz_r, viz_b, viz_g
        ]
        X.append(features)
        y.append(historico_sem_ultimo[i])
    return np.array(X), np.array(y)

FEATURE_NAMES = [
    "Vermelhos","Pretos","Verdes","Pares","Impares",
    "DúziaAtual","ColunaAtual","TempoDesdeZero","DistânciaFísica",
    "FreqQ1","FreqQ2","FreqQ3","FreqQ4","FreqQ5",
    "BlocoFísico","PropPares","PropÍmpares","Repetições5",
    "FreqD1_10","FreqD2_10","FreqD3_10",
    "FreqC1_10","FreqC2_10","FreqC3_10",
    "VizR","VizB","VizG"
]

def ajustar_target(y_raw, tipo):
    if tipo == "duzia":
        return np.array([(n - 1) // 12 + 1 if n != 0 else 0 for n in y_raw])
    elif tipo == "coluna":
        return np.array([(n - 1) % 3 + 1 if n != 0 else 0 for n in y_raw])
    else:
        return y_raw

def treinar_modelos_batch(historico, tipo="duzia"):
    """Treina LGBM + RF (batch)."""
    if len(historico) < 130:
        return None, None, None
    X, y_raw = extrair_features(historico)
    if len(X) == 0:
        return None, None, None
    y = ajustar_target(y_raw, tipo)

    lgb = LGBMClassifier(
        n_estimators=350, learning_rate=0.035, max_depth=7,
        random_state=42, subsample=0.9, colsample_bytree=0.85
    )
    rf = RandomForestClassifier(
        n_estimators=220, max_depth=12, min_samples_split=5,
        random_state=42, n_jobs=-1
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    # ### NOVO: usar log_loss como métrica de probabilidade + accuracy para info
    try:
        lgb_acc = cross_val_score(lgb, X, y, cv=cv, scoring="accuracy")
        rf_acc = cross_val_score(rf, X, y, cv=cv, scoring="accuracy")
        lgb.fit(X, y)
        rf.fit(X, y)
    except Exception as e:
        print("Erro no treino batch:", e)
        return None, None, None

    return (lgb, rf), X, y, (lgb_acc.mean(), rf_acc.mean())

def preparar_sgd_existente(modelo_sgd, classes):
    if modelo_sgd is None:
        # ### NOVO: SGDClassifier (logistic regression) com partial_fit
        return SGDClassifier(loss="log_loss", alpha=1e-4, random_state=42), False
    # Reusar
    return modelo_sgd, True

def atualizar_sgd(modelo_sgd, historico, tipo="duzia"):
    """Atualiza o modelo online com o último par (X[-1], y[-1])."""
    if len(historico) < 131:
        return modelo_sgd
    X, y_raw = extrair_features(historico)
    y = ajustar_target(y_raw, tipo)
    if X.size == 0: return modelo_sgd
    x_last = X[-1].reshape(1, -1)
    y_last = np.array([y[-1]])
    modelo_sgd, exists = preparar_sgd_existente(modelo_sgd, np.unique(y))
    try:
        if not exists:
            modelo_sgd.partial_fit(x_last, y_last, classes=np.array([0,1,2,3]))  # inclui 0 p/ caso de zero
        else:
            modelo_sgd.partial_fit(x_last, y_last)
    except Exception as e:
        print("Erro partial_fit:", e)
    return modelo_sgd

def prever_top2_ensemble(modelos_tuple, sgd_model, historico):
    """Retorna top2 labels e probabilidades + soma, usando ensemble ponderado."""
    if (modelos_tuple is None and sgd_model is None) or len(historico) < 130:
        return [], [], 0.0
    X, _ = extrair_features(historico)
    if X.size == 0:
        return [], [], 0.0
    x = X[-1].reshape(1, -1)

    probs_list = []
    classes_ref = None
    pesos = []

    # Pesos dinâmicos (cv -> maior peso)
    # Se não houver score, fica 0.5/0.5; SGD tem peso pequeno porém sempre presente
    tipo = "duzia"  # placeholder para pegar pesos corretos abaixo

    # LGB + RF
    if modelos_tuple is not None:
        lgb_model, rf_model = modelos_tuple
        classes_ref = lgb_model.classes_
        try:
            p1 = lgb_model.predict_proba(x)[0]
            p2 = rf_model.predict_proba(x)[0]
            probs_list.append(("lgb", p1))
            probs_list.append(("rf", p2))
        except Exception as e:
            print("Erro proba LGB/RF:", e)

    # SGD
    if sgd_model is not None:
        try:
            p3 = sgd_model.predict_proba(x)[0]
            if classes_ref is None:
                classes_ref = sgd_model.classes_
            probs_list.append(("sgd", p3))
        except Exception as e:
            print("Erro proba SGD:", e)

    if not probs_list or classes_ref is None:
        return [], [], 0.0

    # Harmonizar comprimentos (classes 0..3)
    # Garante vetor de tamanho 4
    def pad4(arr):
        if len(arr) == 4: return arr
        out = np.zeros(4)
        out[:len(arr)] = arr
        return out

    # ### NOVO: pesos pelo último CV armazenado
    # Serão definidos fora, conforme tipo real (duzia/coluna) na chamada externa
    # Aqui só devolvemos o vetor de modelos -> probs
    return probs_list, classes_ref

def combinar_com_pesos(probs_list, pesos_dict, classes):
    """Combina probs normalizando pesos existentes."""
    # probs_list: [("lgb", p), ("rf", p), ("sgd", p)]
    total_peso = 0.0
    soma = np.zeros(4)
    for nome, p in probs_list:
        w = pesos_dict.get(nome, 0.0)
        if p is None or w <= 0: continue
        soma += pad4(p) * w
        total_peso += w
    if total_peso <= 0:  # fallback
        total_peso = 1.0
    probs = soma / total_peso
    idxs = np.argsort(probs)[::-1][:2]
    top_labels = [int(classes[i]) for i in idxs]
    top_probs = [float(probs[i]) for i in idxs]
    return top_labels, top_probs, sum(top_probs)

def pad4(arr):
    if len(arr) == 4: return arr
    out = np.zeros(4)
    out[:len(arr)] = arr
    return out

def plot_feature_importances(modelos_tuple, feature_names, titulo):
    try:
        lgb_model, rf_model = modelos_tuple
    except:
        return
    importances_lgb = getattr(lgb_model, "feature_importances_", None)
    importances_rf = getattr(rf_model, "feature_importances_", None)
    if importances_lgb is None or importances_rf is None:
        return
    fig, ax = plt.subplots(figsize=(10,6))
    indices = np.argsort(importances_lgb)[::-1]
    ax.bar(range(len(feature_names)), np.array(importances_lgb)[indices], alpha=0.6, label='LGBM')
    ax.bar(range(len(feature_names)), np.array(importances_rf)[indices], alpha=0.4, label='RF')
    ax.set_xticks(range(len(feature_names)))
    ax.set_xticklabels(np.array(feature_names)[indices], rotation=45, ha='right')
    ax.set_title(titulo)
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)

def atualizar_prob_minima_dinamica():
    """### NOVO: ajusta PROB_MIN com base na janela recente."""
    janela = list(st.session_state.metricas_janela)
    if not janela:
        st.session_state.prob_minima_dinamica = PROB_MIN_BASE
        return
    # média de confiança e hit rate
    confs = [m["soma_prob"] for m in janela]
    hits = [m["hit"] for m in janela]
    avg_conf = float(np.mean(confs)) if confs else PROB_MIN_BASE
    hit_rate = float(np.mean(hits)) if hits else 0.5

    # Regras simples: se está acertando bem, podemos aceitar entradas com um pouco menos de confiança
    # Caso contrário, subimos a exigência
    alvo = PROB_MIN_BASE
    if hit_rate >= 0.65 and avg_conf >= 1.60:
        alvo = 0.90
    elif hit_rate >= 0.55:
        alvo = 0.92
    elif hit_rate >= 0.45:
        alvo = 0.95
    else:
        alvo = 0.97

    alvo = max(min(alvo, PROB_MIN_MAX), PROB_MIN_MIN)
    st.session_state.prob_minima_dinamica = alvo

def registrar_resultado(tipo, soma_prob, hit):
    st.session_state.metricas_janela.append({"tipo": tipo, "soma_prob": soma_prob, "hit": 1 if hit else 0})
    st.session_state.hit_rate_por_tipo[tipo].append(1 if hit else 0)
    atualizar_prob_minima_dinamica()

def pick_tipo_duzia_ou_coluna(res_duzia, res_coluna):
    """Escolhe entre dúzia ou coluna de forma mais equilibrada."""
    top_d, probs_d, soma_d = res_duzia
    top_c, probs_c, soma_c = res_coluna

    hr_d = np.mean(st.session_state.hit_rate_por_tipo["duzia"]) if st.session_state.hit_rate_por_tipo["duzia"] else 0.5
    hr_c = np.mean(st.session_state.hit_rate_por_tipo["coluna"]) if st.session_state.hit_rate_por_tipo["coluna"] else 0.5

    # Peso reduzido do hit rate para não travar a decisão
    score_d = soma_d * (0.8 + 0.2 * hr_d)
    score_c = soma_c * (0.8 + 0.2 * hr_c)

    # Se diferença de confiança for grande, escolhe direto
    if soma_c - soma_d >= 0.10:
        return "coluna", top_c, soma_c
    if soma_d - soma_c >= 0.10:
        return "duzia", top_d, soma_d

    # Caso comum: escolhe pelo maior score ajustado
    if score_d >= score_c:
        return "duzia", top_d, soma_d
    else:
        return "coluna", top_c, soma_c



# === INTERFACE ===
st.title("🎯 IA Roleta PRO — Ensemble Dinâmico + Treino Online + Threshold Adaptativo")
st_autorefresh(interval=REFRESH_INTERVAL, key="atualizacao")

# === COLETA API ===
try:
    resposta = requests.get(API_URL, timeout=5).json()
    numero_atual = int(resposta["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error(f"Erro API: {e}")
    st.stop()

# === PIPELINE ===
novo_num = (len(st.session_state.historico) == 0 or numero_atual != st.session_state.historico[-1])
if novo_num:
    st.session_state.historico.append(numero_atual)
    joblib.dump(st.session_state.historico, HISTORICO_PATH)

    # Checar acerto/erro da previsão anterior
    if st.session_state.top2_anterior:
        st.session_state.total_top += 1
        entrada_tipo = st.session_state.tipo_entrada_anterior or "duzia"
        valor = (numero_atual - 1) // 12 + 1 if entrada_tipo == "duzia" else (numero_atual - 1) % 3 + 1
        hit = (valor in st.session_state.top2_anterior)
        if hit:
            st.session_state.acertos_top += 1
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🟢")
        else:
            enviar_telegram_async(f"✅ Saiu {numero_atual} ({valor}ª {entrada_tipo}): 🔴")

        # registrar na janela dinâmica
        registrar_resultado(entrada_tipo, st.session_state.last_soma_prob if "last_soma_prob" in st.session_state else 0.0, hit)

    # === Atualiza modelos ===
    st.session_state.rounds_desde_retrain += 1

    # (1) Atualiza modelos online (sempre)
    st.session_state.sgd_d = atualizar_sgd(st.session_state.sgd_d, st.session_state.historico, "duzia")
    st.session_state.sgd_c = atualizar_sgd(st.session_state.sgd_c, st.session_state.historico, "coluna")

    # (2) Re-treina LGBM+RF a cada N rodadas
    if (st.session_state.rounds_desde_retrain >= RETRAIN_EVERY) or (st.session_state.modelo_d is None or st.session_state.modelo_c is None):
        modelos_d, Xd, yd, scores_d = treinar_modelos_batch(st.session_state.historico, "duzia")
        modelos_c, Xc, yc, scores_c = treinar_modelos_batch(st.session_state.historico, "coluna")
        st.session_state.modelo_d = modelos_d
        st.session_state.modelo_c = modelos_c
        st.session_state.rounds_desde_retrain = 0

        # Guardar CV p/ pesos do ensemble
        if scores_d:
            st.session_state.cv_scores["duzia"]["lgb"], st.session_state.cv_scores["duzia"]["rf"] = scores_d
        if scores_c:
            st.session_state.cv_scores["coluna"]["lgb"], st.session_state.cv_scores["coluna"]["rf"] = scores_c

    # Mostrar importâncias quando houver modelos batch
    if st.session_state.modelo_d is not None:
        st.subheader("Importância das Features - Dúzia")
        plot_feature_importances(st.session_state.modelo_d, FEATURE_NAMES, "Importância das Features (Dúzia)")
    if st.session_state.modelo_c is not None:
        st.subheader("Importância das Features - Coluna")
        plot_feature_importances(st.session_state.modelo_c, FEATURE_NAMES, "Importância das Features (Coluna)")

    # === Previsões (duzia / coluna) com ensemble ponderado ===
    # Preparar pesos por tipo
    def pesos_por_tipo(tipo):
        cv = st.session_state.cv_scores[tipo]
        # Normaliza pesos LGB e RF pela soma; SGD fica com um peso pequeno mas constante
        lgb_w = max(cv["lgb"], 0.0001)
        rf_w = max(cv["rf"], 0.0001)
        # normalização para ficarem proporcionais
        s = lgb_w + rf_w
        if s <= 0: s = 1.0
        lgb_w /= s
        rf_w /= s
        # Peso do SGD pequeno mas sempre presente (auxilia estabilidade)
        sgd_w = 0.20
        # Rebalanceia para total = 1
        rem = 1.0 - sgd_w
        lgb_w *= rem
        rf_w *= rem
        return {"lgb": lgb_w, "rf": rf_w, "sgd": sgd_w}

    # DUZIA
    probs_list_d, classes_d = prever_top2_ensemble(st.session_state.modelo_d, st.session_state.sgd_d, st.session_state.historico)
    if probs_list_d:
        top_d, probs_d, soma_d = combinar_com_pesos(probs_list_d, pesos_por_tipo("duzia"), classes_d)
    else:
        top_d, probs_d, soma_d = [], [], 0.0

    # COLUNA
    probs_list_c, classes_c = prever_top2_ensemble(st.session_state.modelo_c, st.session_state.sgd_c, st.session_state.historico)
    if probs_list_c:
        top_c, probs_c, soma_c = combinar_com_pesos(probs_list_c, pesos_por_tipo("coluna"), classes_c)
    else:
        top_c, probs_c, soma_c = [], [], 0.0

    # Escolha do tipo via meta-regra
    tipo, top, soma_prob = pick_tipo_duzia_ou_coluna((top_d, probs_d, soma_d), (top_c, probs_c, soma_c))

    # === Envio otimizado de alertas com PROB dinâmica ===
    prob_min = st.session_state.prob_minima_dinamica
    if soma_prob >= prob_min and top:
        alerta_novo = (top != st.session_state.top2_anterior) or (tipo != st.session_state.tipo_entrada_anterior)
        if alerta_novo:
            st.session_state.top2_anterior = top
            st.session_state.tipo_entrada_anterior = tipo
            st.session_state.contador_sem_alerta = 0
            st.session_state.last_soma_prob = soma_prob
            enviar_telegram_async(f"📊 <b>ENTRADA {tipo.upper()}S:</b> {top[0]}ª e {top[1]}ª (conf: {soma_prob:.2%} | min: {prob_min:.0%})")
        else:
            st.session_state.contador_sem_alerta += 1
            if st.session_state.contador_sem_alerta >= 3:
                st.session_state.contador_sem_alerta = 0
                st.session_state.last_soma_prob = soma_prob
                enviar_telegram_async(f"📊 <b>ENTRADA {tipo.upper()}S (forçada):</b> {top[0]}ª e {top[1]}ª (conf: {soma_prob:.2%})")

# === INTERFACE LIMPA ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write(f"Threshold dinâmico atual: {st.session_state.prob_minima_dinamica:.0%}")
st.write("Últimos números:", list(st.session_state.historico)[-12:])

# === SALVAR ESTADO ===
joblib.dump({
    "acertos_top": st.session_state.acertos_top,
    "total_top": st.session_state.total_top,
    "top2_anterior": st.session_state.top2_anterior,
    "contador_sem_alerta": st.session_state.contador_sem_alerta,
    "tipo_entrada_anterior": st.session_state.tipo_entrada_anterior,
    "rounds_desde_retrain": st.session_state.rounds_desde_retrain,
    "cv_scores": st.session_state.cv_scores,
    "prob_minima_dinamica": st.session_state.prob_minima_dinamica,
    "metricas_janela": st.session_state.metricas_janela,
    "hit_rate_por_tipo": st.session_state.hit_rate_por_tipo
}, ESTADO_PATH)
