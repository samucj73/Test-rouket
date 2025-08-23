import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier
import time
# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

TAMANHO_JANELA_DEFAULT = 15
MAX_HISTORICO = 4500
REFRESH_INTERVAL_MS = 5000
TRAIN_EVERY = 15

MODELO_DUZIA_PATH = Path("modelo_duzia.pkl")
MODELO_COLUNA_PATH = Path("modelo_coluna.pkl")
HIST_PATH_NUMS = Path("historico_numeros.pkl")
ESTADO_PATH = Path("estado.pkl")

# =========================
# ROUE EUROPEIA
# =========================
RED_SET = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
IDX = {n:i for i,n in enumerate(WHEEL)}

def numero_para_duzia(n:int)->int:
    if n == 0: return 0
    if 1 <= n <= 12: return 1
    if 13 <= n <= 24: return 2
    return 3

def numero_para_coluna(n:int)->int:
    if n == 0: return 0
    return ((n - 1) % 3) + 1

def is_red(n:int)->int:
    return 1 if (n in RED_SET) else 0

# =========================
# CARREGA ESTADO SALVO
# =========================
try:
    estado_salvo = joblib.load(ESTADO_PATH) if ESTADO_PATH.exists() else {}
except Exception:
    estado_salvo = {}

# =========================
# SESSION STATE INIT
# =========================
if "historico_numeros" not in st.session_state:
    if HIST_PATH_NUMS.exists():
        hist = joblib.load(HIST_PATH_NUMS)
        st.session_state.historico_numeros = deque(hist, maxlen=MAX_HISTORICO)
    else:
        st.session_state.historico_numeros = deque(maxlen=MAX_HISTORICO)

if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = joblib.load(MODELO_DUZIA_PATH) if MODELO_DUZIA_PATH.exists() else None
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = joblib.load(MODELO_COLUNA_PATH) if MODELO_COLUNA_PATH.exists() else None

if "tamanho_janela" not in st.session_state:
    st.session_state.tamanho_janela = TAMANHO_JANELA_DEFAULT
if "prob_minima" not in st.session_state:
    st.session_state.prob_minima = 0.30

if "ultima_entrada" not in st.session_state: st.session_state.ultima_entrada = None
if "contador_sem_envio" not in st.session_state: st.session_state.contador_sem_envio = 0
if "ultimo_numero_salvo" not in st.session_state: st.session_state.ultimo_numero_salvo = None
if "acertos_top" not in st.session_state: st.session_state.acertos_top = 0
if "total_top" not in st.session_state: st.session_state.total_top = 0
if "ultimo_resultado_numero" not in st.session_state: st.session_state.ultimo_resultado_numero = None

# restore counters
for k,v in estado_salvo.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# UI
# =========================
st.set_page_config(page_title="IA Roleta - Dúzia & Coluna", page_icon="🎯", layout="centered")
st.title("🎯 IA Roleta - Dúzia & Coluna (sem threads)")

col1, col2 = st.columns([2,1])
with col1:
    st.session_state.tamanho_janela = st.slider(
        "📏 Tamanho da janela (giros para features)",
        5, 150, st.session_state.tamanho_janela, key="slider_tamanho"
    )
with col2:
    st.session_state.prob_minima = st.slider(
        "📊 Prob mínima (%)", 10, 100, int(st.session_state.prob_minima * 100), key="slider_prob"
    ) / 100.0

if st.button("🔄 Capturar último número AGORA"):
    st.session_state._manual_capture = True

# =========================
# FUNÇÕES
# =========================

def salvar_historico(numero:int):
    if numero is None:
        return
    if len(st.session_state.historico_numeros) == 0 or st.session_state.historico_numeros[-1] != numero:
        st.session_state.historico_numeros.append(numero)
        try:
            joblib.dump(list(st.session_state.historico_numeros), HIST_PATH_NUMS)
        except: pass

#.     FEATURES

def extrair_features(janela_numeros):
    feats = []
    L = len(janela_numeros)
    window = st.session_state.tamanho_janela

    # --- Sequência da janela ---
    pad = [0]*(window - L)
    seq = pad + list(janela_numeros)[-window:]
    feats.extend(seq)

    # --- Contagem relativa dúzia e coluna ---
    cnt_duzia = Counter(numero_para_duzia(n) for n in janela_numeros)
    cnt_coluna = Counter(numero_para_coluna(n) for n in janela_numeros)
    for d in [1,2,3]:
        feats.append(cnt_duzia.get(d,0)/max(1,L))
    for c in [1,2,3]:
        feats.append(cnt_coluna.get(c,0)/max(1,L))

    # --- Último número ---
    if L>0:
        last = janela_numeros[-1]
        feats.append(int(last%2==0))  # paridade
        feats.append(is_red(last))    # cor
    else:
        feats.extend([0,0])

    # --- Distância desde o último zero ---
    last_zero_dist = next((L-i for i,n in enumerate(reversed(janela_numeros)) if n==0), L)
    feats.append(last_zero_dist / max(1,L))

    # --- Vizinhos físicos na roleta ---
    if L>0:
        last_idx = IDX.get(janela_numeros[-1],0)
        for offset in [-2,-1,1,2]:
            neighbor = WHEEL[(last_idx+offset)%37]
            feats.append(neighbor)
    else:
        feats.extend([0,0,0,0])

    # --- Gaps importantes ---
    # Gap desde último zero
    last_zero = next((i for i,n in enumerate(reversed(janela_numeros)) if n==0), None)
    feats.append(last_zero if last_zero is not None else L)

    # Gap desde última aparição do mesmo número
    last_num = janela_numeros[-1] if L>0 else None
    last_num_idx = next((i for i,n in enumerate(reversed(janela_numeros)) if n==last_num), None)
    feats.append(last_num_idx if last_num_idx is not None else L)

    # Gap desde última aparição da mesma dúzia
    if L>0:
        last_duz = numero_para_duzia(janela_numeros[-1])
        last_duz_idx = next((i for i,n in enumerate(reversed(janela_numeros)) if numero_para_duzia(n)==last_duz), None)
        feats.append(last_duz_idx if last_duz_idx is not None else L)
    else:
        feats.append(L)

    # Gap desde última aparição da mesma coluna
    if L>0:
        last_col = numero_para_coluna(janela_numeros[-1])
        last_col_idx = next((i for i,n in enumerate(reversed(janela_numeros)) if numero_para_coluna(n)==last_col), None)
        feats.append(last_col_idx if last_col_idx is not None else L)
    else:
        feats.append(L)

    # Gap desde última aparição da mesma cor
    if L>0:
        last_color = is_red(janela_numeros[-1])
        last_color_idx = next((i for i,n in enumerate(reversed(janela_numeros)) if is_red(n)==last_color), None)
        feats.append(last_color_idx if last_color_idx is not None else L)
    else:
        feats.append(L)

    # Gap desde última aparição da mesma paridade
    if L>0:
        last_par = int(janela_numeros[-1]%2==0)
        last_par_idx = next((i for i,n in enumerate(reversed(janela_numeros)) if int(n%2==0)==last_par), None)
        feats.append(last_par_idx if last_par_idx is not None else L)
    else:
        feats.append(L)

    # --- Frequência relativa dos últimos 3 números mais saídos na janela ---
    cnt_nums = Counter(janela_numeros)
    top3 = [c for c,_ in cnt_nums.most_common(3)]
    for n in top3:
        feats.append(cnt_nums.get(n,0)/max(1,L))
    # completa se tiver menos de 3
    while len(top3)<3:
        feats.append(0)
        top3.append(None)

    # --- Delta entre últimas duas saídas ---
    if L>=2:
        delta_num = janela_numeros[-1] - janela_numeros[-2]
        idx1 = IDX[janela_numeros[-2]]
        idx2 = IDX[janela_numeros[-1]]
        delta_phys = idx2 - idx1
        feats.extend([delta_num, delta_phys])
    else:
        feats.extend([0,0])

    # --- Repetições recentes do mesmo número nos últimos X giros ---
    if L>0:
        repeats = sum(1 for n in janela_numeros[-5:] if n==janela_numeros[-1])
        feats.append(repeats)
    else:
        feats.append(0)

    return np.array(feats,dtype=float)


    

def capturar_numero_api():
    try:
        r = requests.get(API_URL, timeout=4)
        r.raise_for_status()
        data = r.json()
        candidates = []
        if isinstance(data, dict):
            candidates.extend([data.get(k) for k in ["winningNumber","number","result","value","outcome"] if k in data])
            def deep_search(d):
                if isinstance(d, dict):
                    for k,v in d.items():
                        if isinstance(v,(dict,list)):
                            deep_search(v)
                        else:
                            if isinstance(v,int) and 0 <= v <= 36:
                                candidates.append(v)
                elif isinstance(d,list):
                    for item in d:
                        deep_search(item)
            deep_search(data)
        for c in candidates:
            try:
                if isinstance(c,int) and 0 <= c <= 36:
                    return c
                if isinstance(c,str) and c.isdigit():
                    v = int(c)
                    if 0 <= v <= 36:
                        return v
            except:
                continue
    except Exception as e:
        st.debug(f"Erro captura API: {e}")
    return None

def treinar_modelo(tipo="duzia"):
    nums = list(st.session_state.historico_numeros)
    n = len(nums)
    window = st.session_state.tamanho_janela
    if n < window + 3:
        return False
    X, y = [], []
    for i in range(n - window):
        janela = nums[i:i+window]
        alvo_num = nums[i+window]
        if tipo == "duzia":
            alvo = numero_para_duzia(alvo_num)
            if alvo == 0: continue
        else:
            alvo = numero_para_coluna(alvo_num)
            if alvo == 0: continue
        feats = extrair_features(janela)
        X.append(feats)
        y.append(alvo)
    if len(X) < 10 or len(set(y)) < 2: return False
    X = np.array(X,dtype=float)
    y = np.array(y,dtype=int)
    modelo = CatBoostClassifier(iterations=300, depth=6, learning_rate=0.08, loss_function='MultiClass', verbose=False)
    try:
        modelo.fit(X, y)
        if tipo=="duzia":
            st.session_state.modelo_duzia = modelo
            try: joblib.dump(modelo, MODELO_DUZIA_PATH)
            except: pass
        else:
            st.session_state.modelo_coluna = modelo
            try: joblib.dump(modelo, MODELO_COLUNA_PATH)
            except: pass
        return True
    except Exception as e:
        st.warning(f"Erro ao treinar ({tipo}): {e}")
        return False

def prever(tipo="duzia", topk=3):
    modelo = st.session_state.modelo_duzia if tipo=="duzia" else st.session_state.modelo_coluna
    if modelo is None or len(st.session_state.historico_numeros) < st.session_state.tamanho_janela:
        return []
    janela = list(st.session_state.historico_numeros)[-st.session_state.tamanho_janela:]
    feats = extrair_features(janela).reshape(1,-1)
    try:
        probs = modelo.predict_proba(feats)[0]
        classes = list(modelo.classes_)
        idxs = np.argsort(probs)[::-1][:topk]
        top = [(int(classes[i]), float(probs[i])) for i in idxs]
        return top
    
    except Exception as e:
        st.error(f"⚠️ Erro prever {tipo}: {e}")
        st.exception(e)   # mostra traceback completo no app
        return [] 
    

def enviar_telegram(msg:str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

# =========================
# FLUXO PRINCIPAL
# =========================
# =========================
# Fluxo principal adaptado (evita múltiplos alertas)
# === AUTORREFRESH (apenas para atualização de tela, não interfere nos alertas) ===
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto_refresh_key")

# Captura manual ou automática
manual_flag = st.session_state.pop("_manual_capture", False) if "_manual_capture" in st.session_state else False
numero = capturar_numero_api() if (manual_flag or True) else None

# Garantir que só processa número novo
if numero is not None and (st.session_state.ultimo_numero_salvo is None or numero != st.session_state.ultimo_numero_salvo):
    st.session_state.ultimo_numero_salvo = numero
    salvar_historico(numero)

    # === Conferência de acerto/erro ===
    if st.session_state.ultima_entrada:
        ent = st.session_state.ultima_entrada
        try:
            tipo = ent.get("tipo")
            classes = [c for c,_ in ent.get("classes",[])]
            acerto = False
            if tipo == "Dúzia" and numero_para_duzia(numero) in classes:
                acerto = True
            if tipo == "Coluna" and numero_para_coluna(numero) in classes:
                acerto = True

            if acerto:
                st.session_state.acertos_top += 1
                enviar_telegram(f"✅ Saiu {numero} — ACERTO! ({tipo})")
            else:
                enviar_telegram(f"❌ Saiu {numero} — ERRO. ({tipo})")

            st.session_state.total_top += 1
        except:
            pass

    # === Re-treino periódico ===
    if len(st.session_state.historico_numeros) >= st.session_state.tamanho_janela + 3:
        if len(st.session_state.historico_numeros) % TRAIN_EVERY == 0:
            treinar_modelo("duzia")
            treinar_modelo("coluna")

    # Reset do flag de alerta a cada número novo
    st.session_state._alerta_enviado_rodada = False

    # === Top-3 previsão e escolha automática ===
    top_duzia = prever("duzia")
    top_coluna = prever("coluna")

    sum_duzia = sum(p for _,p in top_duzia) if top_duzia else 0.0
    sum_coluna = sum(p for _,p in top_coluna) if top_coluna else 0.0

    chosen = None
    if sum_duzia == 0 and sum_coluna == 0:
        chosen = None
    elif sum_duzia >= sum_coluna:
        chosen = ("Dúzia", top_duzia)
    else:
        chosen = ("Coluna", top_coluna)

    if chosen and not st.session_state._alerta_enviado_rodada:
        tipo, classes_probs = chosen
        classes_probs = [(c,p) for c,p in classes_probs if p >= st.session_state.prob_minima]
        if classes_probs:
            chave = f"{tipo}_" + "_".join(str(c) for c,_ in classes_probs)
            reenvio_forcado = False

            if st.session_state.ultima_entrada and chave == st.session_state.ultima_entrada.get("chave"):
                st.session_state.contador_sem_envio += 1
                if st.session_state.contador_sem_envio >= 3:
                    reenvio_forcado = True
            else:
                st.session_state.contador_sem_envio = 0

            if (not st.session_state.ultima_entrada) or reenvio_forcado or chave != st.session_state.ultima_entrada.get("chave"):
                entrada_obj = {"tipo": tipo, "classes": classes_probs, "chave": chave}
                txt = f"📊 <b>ENT {tipo}</b>: " + ", ".join(f"{c} ({p*100:.1f}%)" for c,p in classes_probs)
                #time.sleep(8)  # ⏳ espera 7 segundos antes de enviar
                enviar_telegram(txt)
                st.session_state.ultima_entrada = entrada_obj
                st.session_state.contador_sem_envio = 0
                st.session_state._alerta_enviado_rodada = True

            try:
                joblib.dump({
                    "acertos_top": st.session_state.acertos_top,
                    "total_top": st.session_state.total_top,
                    "ultima_entrada": st.session_state.ultima_entrada,
                    "contador_sem_envio": st.session_state.contador_sem_envio
                }, ESTADO_PATH)
            except:
                pass



# =========================
# UI FINAL
# =========================
st.subheader("📌 Últimos números capturados")
if len(st.session_state.historico_numeros) > 0:
    st.write(list(st.session_state.historico_numeros)[-20:])



else:
    st.info("Nenhum número capturado ainda. Use o botão 'Capturar' ou aguarde o auto-refresh.")

st.subheader("📊 Estatísticas")
st.write(f"Acertos: {st.session_state.acertos_top} / {st.session_state.total_top}")

st.subheader("🎯 Última entrada enviada")
if st.session_state.ultima_entrada:
    typ = st.session_state.ultima_entrada.get("tipo")
    classes = st.session_state.ultima_entrada.get("classes", [])
    st.write(f"{typ}: " + ", ".join(f"{c} ({p*100:.1f}%)" for c,p in classes))
else:
    st.write("Nenhuma entrada enviada ainda.")

st.subheader("🔮 Previsões (Top-3) — modelos atuais")
pd = prever("duzia")
pc = prever("coluna")

if pd:
    st.write("Dúzia:", ", ".join(f"{c} ({p*100:.1f}%)" for c,p in pd))
else:
    st.write("Dúzia: sem previsão (modelo não treinado ou poucos dados).")
if pc:
    st.write("Coluna:", ", ".join(f"{c} ({p*100:.1f}%)" for c,p in pc))
else:
    st.write("Coluna: sem previsão (modelo não treinado ou poucos dados).")
