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
HISTORICO_DUZIAS_PATH = Path("historico.pkl")          # legado (dúzias)
HISTORICO_NUMEROS_PATH = Path("historico_numeros.pkl") # novo (números brutos)
ESTADO_PATH = Path("estado.pkl")
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  # ms
WINDOW_SIZE = 15         # janela para features base
TRAIN_EVERY = 10         # treinar a cada N novas entradas

# === MAPAS AUXILIARES (roda europeia 0) ===
RED_SET = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
IDX = {n:i for i,n in enumerate(WHEEL)}

def numero_para_duzia(num:int)->int:
    if num == 0: return 0
    if 1 <= num <= 12: return 1
    if 13 <= num <= 24: return 2
    return 3

def numero_para_coluna(num:int)->int:
    if num == 0: return 0
    r = num % 3
    return 3 if r == 0 else r  # 1->col1, 2->col2, 0->col3

def is_red(num:int)->int:
    return 1 if num in RED_SET else 0 if num != 0 else 0

def is_even(num:int)->int:
    return 1 if (num != 0 and num % 2 == 0) else 0

def is_low(num:int)->int:
    return 1 if (1 <= num <= 18) else 0

def vizinhos_set(num:int, k:int=2)->set:
    if num not in IDX: return set()
    i = IDX[num]
    L = len(WHEEL)
    indices = [(i + j) % L for j in range(-k, k+1)]
    return { WHEEL[idx] for idx in indices }

VOISINS = {22,18,29,7,28,12,35,3,26,0,32,15,19,4,21,2,25}
TIERS   = {27,13,36,11,30,8,23,10,5,24,16,33}
ORPH    = {1,20,14,31,9,17,34,6}

# === CARREGA ESTADO ===
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception as e:
    st.warning(f"⚠️ Estado corrompido, reiniciando: {e}")
    try: ESTADO_PATH.unlink()
    except Exception: pass
    estado_salvo = {}

# === SESSION STATE ===
if "ultimo_numero_salvo" not in st.session_state:
    st.session_state.ultimo_numero_salvo = None
if "ultima_chave_alerta" not in st.session_state:
    st.session_state.ultima_chave_alerta = None

# histórico de dúzias (legado)
if "historico" not in st.session_state:
    if HISTORICO_DUZIAS_PATH.exists():
        st.session_state.historico = joblib.load(HISTORICO_DUZIAS_PATH)
        if not isinstance(st.session_state.historico, deque):
            st.session_state.historico = deque(st.session_state.historico, maxlen=MAX_HIST_LEN)
    else:
        st.session_state.historico = deque(maxlen=MAX_HIST_LEN)

# histórico de números (novo)
if "historico_numeros" not in st.session_state:
    if HISTORICO_NUMEROS_PATH.exists():
        hist_num = joblib.load(HISTORICO_NUMEROS_PATH)
        st.session_state.historico_numeros = deque(hist_num, maxlen=MAX_HIST_LEN)
    else:
        st.session_state.historico_numeros = deque(maxlen=MAX_HIST_LEN)

for var in ["acertos_top","total_top","contador_sem_alerta","tipo_entrada_anterior",
            "padroes_certos","ultima_entrada","modelo_rf","ultimo_resultado_numero"]:
    if var not in st.session_state:
        if var in ["padroes_certos","ultima_entrada"]:
            st.session_state[var] = []
        elif var == "tipo_entrada_anterior":
            st.session_state[var] = ""
        elif var == "modelo_rf":
            st.session_state[var] = None
        else:
            st.session_state[var] = 0

# Restaura contadores/chaves do estado salvo (nunca carrega modelo do disco)
for k, v in estado_salvo.items():
    st.session_state[k] = v

# === INTERFACE ===
st.title("🎯 IA Roleta - Padrões de Dúzia (CatBoost + Features Avançadas)")
tamanho_janela = st.slider("📏 Tamanho da janela de análise", 5, 150, WINDOW_SIZE)
prob_minima = st.slider("📊 Probabilidade mínima (%)", 10, 100, 30) / 100.0

# === TELEGRAM ===
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

# === HISTÓRICO ===
def salvar_historico(numero:int):
    """Salva número bruto e sua dúzia, persistindo ambos os históricos."""
    duzia = numero_para_duzia(numero)
    if not isinstance(st.session_state.historico, deque):
        st.session_state.historico = deque(st.session_state.historico, maxlen=MAX_HIST_LEN)
    if not isinstance(st.session_state.historico_numeros, deque):
        st.session_state.historico_numeros = deque(st.session_state.historico_numeros, maxlen=MAX_HIST_LEN)

    st.session_state.historico.append(duzia)
    st.session_state.historico_numeros.append(numero)

    joblib.dump(st.session_state.historico, HISTORICO_DUZIAS_PATH)
    joblib.dump(st.session_state.historico_numeros, HISTORICO_NUMEROS_PATH)
    return duzia

# (compat): mantém nome antigo caso usem em outro lugar
def salvar_historico_duzia(numero:int):
    return salvar_historico(numero)

# === FEATURES ===
def freq_em_janela(valores, universo, w):
    """Frequência relativa de cada item de universo nos últimos w valores."""
    w = max(1, min(w, len(valores)))
    sub = valores[-w:]
    c = Counter(sub)
    total = float(w)
    return [c.get(u, 0)/total for u in universo]

def tempo_desde_ultimo(valores, universo):
    """Distância normalizada até a última ocorrência de cada item em universo."""
    L = len(valores)
    out = []
    rev = valores[::-1]
    for u in universo:
        try:
            idx = rev.index(u)  # 0 é o último elemento
            out.append(idx / max(1, L-1))
        except ValueError:
            out.append(1.0)  # nunca visto na janela
    return out

def matriz_transicoes(valores, universo):
    """Matriz 3x3 de transições normalizada por total de passos."""
    m = {a:{b:0 for b in universo} for a in universo}
    for a, b in zip(valores[:-1], valores[1:]):
        if a in m and b in m[a]:
            m[a][b] += 1
    total = sum(m[a][b] for a in universo for b in universo)
    if total == 0: total = 1
    return [m[a][b]/total for a in universo for b in universo]

def extrair_features(janela_duzias, janela_numeros):
    """Features combinando dúzias e números brutos (roda física e propriedades)."""
    feats = []
    L = len(janela_duzias)

    # 1) Sequência crua de dúzias
    feats.extend(janela_duzias)

    # 2) Frequência simples e ponderada (decay) das dúzias
    contador = Counter(janela_duzias)
    for d in [1,2,3]:
        feats.append(contador.get(d, 0) / max(1, L))
    pesos = np.array([0.9**i for i in range(L-1, -1, -1)], dtype=float)
    s_pesos = float(pesos.sum()) if pesos.size else 1.0
    for d in [1,2,3]:
        fw = sum(w for val, w in zip(janela_duzias, pesos) if val == d) / s_pesos
        feats.append(fw)

    # 3) Alternância (simples & ponderada)
    if L > 1:
        altern = sum(1 for j in range(1, L) if janela_duzias[j] != janela_duzias[j-1])
        feats.append(altern / (L-1))
        den = sum(0.9**i for i in range(L-1)) or 1.0
        feats.append(sum((janela_duzias[j] != janela_duzias[j-1]) * 0.9**(L-1-j)
                         for j in range(1, L)) / den)
    else:
        feats.extend([0.0, 0.0])

    # 4) Tendência normalizada das dúzias
    tend = [0.0,0.0,0.0]
    for val, w in zip(janela_duzias, pesos if L else []):
        if val in [1,2,3]: tend[val-1] += float(w)
    total = sum(tend) if sum(tend) > 0 else 1.0
    feats.extend([t/total for t in tend])
    feats.append((max(tend)-min(tend)) if tend else 0.0)

    # 5) Zero-rate na janela
    feats.append(janela_duzias.count(0) / max(1, L))

    # 6) Última ocorrência (distância normalizada) por dúzia
    feats.extend(tempo_desde_ultimo(janela_duzias, [1,2,3]))

    # 7) Últimas k (k=5) contagens normalizadas por dúzia
    k = min(5, L)
    ultk = janela_duzias[-k:] if L else []
    for d in [1,2,3]:
        feats.append(ultk.count(d) / max(1, k))

    # 8) Frequências por janelas múltiplas (12, 24, 36) – recortadas ao tamanho L
    for w in [12,24,36]:
        feats.extend(freq_em_janela(janela_duzias, [1,2,3], w))

    # 9) Streak atual (comprimento da sequência final da mesma dúzia, normalizado)
    streak = 0
    if L:
        last = janela_duzias[-1]
        for v in reversed(janela_duzias):
            if v == last: streak += 1
            else: break
    feats.append(streak / max(1, L))

    # 10) Matriz de transições 3x3 entre dúzias
    feats.extend(matriz_transicoes(janela_duzias, [1,2,3]))

    # ======= Features baseadas nos NÚMEROS brutos =======
    Ln = len(janela_numeros)
    if Ln == 0:
        # reserva espaço para manter dimensionalidade estável (26 features abaixo)
        feats.extend([0.0]*26)
        return feats

    # 10a) Par/Ímpar, Vermelho/Preto, Baixo/Alto nas últimas janelas (12)
    wnum = min(12, Ln)
    ult = janela_numeros[-wnum:]
    if wnum == 0: wnum = 1
    feats.append(sum(is_even(n) for n in ult)/wnum)
    feats.append(sum(1-is_even(n) for n in ult)/wnum)
    feats.append(sum(is_red(n) for n in ult)/wnum)
    feats.append(sum(1-is_red(n) for n in ult if n!=0)/max(1, sum(1 for n in ult if n!=0)))  # preto
    feats.append(sum(is_low(n) for n in ult)/wnum)
    feats.append(sum(1-is_low(n) for n in ult if n!=0)/max(1, sum(1 for n in ult if n!=0)))  # alto

    # 10b) Colunas 1/2/3 nas últimas janelas
    cols = [numero_para_coluna(n) for n in ult]
    for c in [1,2,3]:
        feats.append(cols.count(c) / len(ult))

    # 10c) Vizinhos físicos do último número (±2) – proporção de hits nos últimos 12
    last_num = janela_numeros[-1]
    viz = vizinhos_set(last_num, k=2)
    feats.append(sum(1 for n in ult if n in viz) / len(ult))

    # 10d) Setores clássicos (Voisins, Tiers, Orphelins) – proporção nos últimos 12
    feats.append(sum(1 for n in ult if n in VOISINS) / len(ult))
    feats.append(sum(1 for n in ult if n in TIERS) / len(ult))
    feats.append(sum(1 for n in ult if n in ORPH) / len(ult))

    # 10e) Frequência do ZERO nas últimas 36 (sinaliza tendência a travar padrão)
    w36 = min(36, Ln)
    ult36 = janela_numeros[-w36:]
    feats.append(ult36.count(0) / max(1, w36))

    # 10f) Distâncias na roda entre os últimos 3 números (média normalizada)
    if Ln >= 3:
        trip = janela_numeros[-3:]
        Lwheel = len(WHEEL)
        dists = []
        ok = True
        for a,b in zip(trip[:-1], trip[1:]):
            if a not in IDX or b not in IDX:
                ok = False; break
            ia, ib = IDX[a], IDX[b]
            cw = (ib - ia) % Lwheel
            ccw = (ia - ib) % Lwheel
            dists.append(min(cw, ccw)/Lwheel)
        feats.append(np.mean(dists) if (dists and ok) else 0.0)
    else:
        feats.append(0.0)

    # 10g) Qual dúzia do último número (one-hot), ajuda o modelo a entender regime
    last_dz = numero_para_duzia(last_num)
    for d in [1,2,3]:
        feats.append(1.0 if last_dz == d else 0.0)

    # 10h) Qual coluna do último número (one-hot)
    last_col = numero_para_coluna(last_num)
    for c in [1,2,3]:
        feats.append(1.0 if last_col == c else 0.0)

    # 10i) Últimos 6 números (one-hot compacta por dúzia)
    k6 = min(6, Ln)
    ult6 = janela_numeros[-k6:]
    for d in [1,2,3]:
        feats.append(sum(1 for n in ult6 if numero_para_duzia(n)==d)/max(1,k6))

    return feats

# === DATASET (X, y) ===
def criar_dataset_features(hist_duzias, hist_numeros, janela_size):
    X, y = [], []
    duz = list(hist_duzias)
    nums = list(hist_numeros)
    L = min(len(duz), len(nums))
    if L <= janela_size: 
        return np.array(X), np.array(y)

    # alinhar pelas mesmas posições
    duz = duz[-L:]
    nums = nums[-L:]

    for i in range(L - janela_size):
        janela_duz = duz[i:i+janela_size]
        janela_num = nums[i:i+janela_size]
        alvo = duz[i + janela_size]  # próxima dúzia
        if alvo in [1,2,3]:  # ignora zero como target
            X.append(extrair_features(janela_duz, janela_num))
            y.append(alvo)
    return np.array(X, dtype=float), np.array(y, dtype=int)

# === TREINAMENTO ===
def treinar_modelo_rf():
    X, y = criar_dataset_features(st.session_state.historico, st.session_state.historico_numeros, tamanho_janela)
    if len(y) > 1 and len(set(y)) > 1 and len(X) == len(y):
        modelo = CatBoostClassifier(
            iterations=300,
            depth=6,
            learning_rate=0.08,
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
    duz = list(st.session_state.historico)
    nums = list(st.session_state.historico_numeros)
    L = min(len(duz), len(nums))
    if L < tamanho_janela or st.session_state.modelo_rf is None:
        return None, None

    janela_duz = duz[-tamanho_janela:]
    janela_num = nums[-tamanho_janela:]
    feats = np.array(extrair_features(janela_duz, janela_num)).reshape(1, -1)

    try:
        probs = st.session_state.modelo_rf.predict_proba(feats)[0]
        classes = st.session_state.modelo_rf.classes_
    except Exception as e:
        st.warning(f"Erro na predição: {e}")
        return None, None

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
if numero_atual != st.session_state.ultimo_numero_salvo:
    duzia_atual = salvar_historico(numero_atual)
    st.session_state.ultimo_numero_salvo = numero_atual

    # treina a cada TRAIN_EVERY inserções
    Lmin = min(len(st.session_state.historico), len(st.session_state.historico_numeros))
    if Lmin >= tamanho_janela + 2 and (Lmin % TRAIN_EVERY == 0):
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
    if st.session_state.modelo_rf is not None:
        try:
            duzias_previstas, probs = prever_duzia_rf()
            if duzias_previstas is not None and len(duzias_previstas) == 2:
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
                        st.session_state.contador_sem_alerta += 1
                else:
                    st.session_state.contador_sem_alerta += 1
        except Exception as e:
            st.warning(f"Erro na previsão: {e}")

# === INTERFACE ===
st.write("Último número:", numero_atual)
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")
st.write("Últimos registros (dúzias):", list(st.session_state.historico)[-12:])
st.write("Últimos números:", list(st.session_state.historico_numeros)[-12:])

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
