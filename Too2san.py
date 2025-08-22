import streamlit as st
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# =========================
# CONFIGURAÇÕES
# =========================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"  # substitua se necessário
TELEGRAM_CHAT_ID = "5121457416"                                   # substitua se necessário

TAMANHO_JANELA_DEFAULT = 15
MAX_HISTORICO = 4500
REFRESH_INTERVAL_MS = 5000   # 5s
TRAIN_EVERY = 15

MODELO_DUZIA_PATH = Path("modelo_duzia.pkl")
MODELO_COLUNA_PATH = Path("modelo_coluna.pkl")
HIST_PATH_NUMS = Path("historico_numeros.pkl")
ESTADO_PATH = Path("estado.pkl")

# =========================
# UTIL (roda europeia)
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

# models
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = joblib.load(MODELO_DUZIA_PATH) if MODELO_DUZIA_PATH.exists() else None
if "modelo_coluna" not in st.session_state:
    st.session_state.modelo_coluna = joblib.load(MODELO_COLUNA_PATH) if MODELO_COLUNA_PATH.exists() else None

# UI params
if "tamanho_janela" not in st.session_state:
    st.session_state.tamanho_janela = TAMANHO_JANELA_DEFAULT
if "prob_minima" not in st.session_state:
    st.session_state.prob_minima = 0.30

# tracking & anti-spam & stats
if "ultima_entrada" not in st.session_state: st.session_state.ultima_entrada = None
if "contador_sem_envio" not in st.session_state: st.session_state.contador_sem_envio = 0
if "ultimo_numero_salvo" not in st.session_state: st.session_state.ultimo_numero_salvo = None
if "acertos_top" not in st.session_state: st.session_state.acertos_top = 0
if "total_top" not in st.session_state: st.session_state.total_top = 0
if "ultimo_resultado_numero" not in st.session_state: st.session_state.ultimo_resultado_numero = None

# restore saved counters if present
for k,v in estado_salvo.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# UI - cabeçalho e controles
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

# botão manual para captura
if st.button("🔄 Capturar último número AGORA"):
    # we'll capture below in main flow (we set a flag)
    st.session_state._manual_capture = True

# =========================
# FUNÇÕES PRINCIPAIS
# =========================

def salvar_historico(numero:int):
    if numero is None:
        return
    # append if new
    if len(st.session_state.historico_numeros) == 0 or st.session_state.historico_numeros[-1] != numero:
        st.session_state.historico_numeros.append(numero)
        # persist
        try:
            joblib.dump(list(st.session_state.historico_numeros), HIST_PATH_NUMS)
        except Exception:
            pass

def extrair_features(janela_numeros):
    """Versão compacta/estável das features necessárias — pode estender mantendo estabilidade dimensional."""
    duzias = [numero_para_duzia(n) for n in janela_numeros]
    feats = []
    L = len(duzias)
    # include last raw numbers (up to janela) padded with zeros if needed
    pad = [0] * (st.session_state.tamanho_janela - L)
    seq = pad + list(janela_numeros)[-st.session_state.tamanho_janela:]
    feats.extend(seq)
    # simple frequencies of dúzias
    cnt = Counter(duzias)
    for d in [1,2,3]:
        feats.append(cnt.get(d,0) / max(1, L))
    # last number properties
    if L>0:
        last = janela_numeros[-1]
        feats.append(isinstance(last,int) and (last%2==0))
        feats.append(is_red(last))
    else:
        feats.extend([0,0])
    # keep dimensionality stable: pad to fixed length (approximate)
    # NOTE: this is a simplified feature extractor — you can replace with your expanded extractor.
    return np.array(feats, dtype=float)

def capturar_numero_api():
    """Captura robusta: tenta encontrar um campo plausível no JSON retornado."""
    try:
        r = requests.get(API_URL, timeout=4)
        r.raise_for_status()
        data = r.json()
        # Tentar vários caminhos comuns
        candidates = []
        if isinstance(data, dict):
            # flatten first-level keys
            candidates.extend([data.get(k) for k in ["winningNumber","number","result","value","outcome"] if k in data])
            # alguns endpoints possuem estruturas aninhadas
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
        # Filtra inteiros plausíveis 0..36
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
        # não polui UI com erro sempre — usado para debug quando necessário
        st.debug(f"Erro captura API: {e}")
    return None

def treinar_modelo(tipo="duzia"):
    """Treina CatBoost para dúzia ou coluna com features básicas (substitua extrair_features por mais completas)."""
    nums = list(st.session_state.historico_numeros)
    n = len(nums)
    window = st.session_state.tamanho_janela
    if n < window + 3:  # exige pelo menos algumas amostras
        return False
    X, y = [], []
    for i in range(n - window):
        janela = nums[i:i+window]
        alvo_num = nums[i+window]
        if tipo == "duzia":
            alvo = numero_para_duzia(alvo_num)
            if alvo == 0:  # ignorar zeros como alvo
                continue
        else:
            alvo = numero_para_coluna(alvo_num)
            if alvo == 0:
                continue
        feats = extrair_features(janela)
        X.append(feats)
        y.append(alvo)
    if len(X) < 10 or len(set(y)) < 2:
        return False
    X = np.array(X, dtype=float)
    y = np.array(y, dtype=int)
    modelo = CatBoostClassifier(iterations=200, depth=6, learning_rate=0.08, loss_function='MultiClass', verbose=False)
    try:
        modelo.fit(X, y)
        if tipo == "duzia":
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

def prever(tipo="duzia"):
    modelo = st.session_state.modelo_duzia if tipo=="duzia" else st.session_state.modelo_coluna
    if modelo is None:
        return [], []
    if len(st.session_state.historico_numeros) < st.session_state.tamanho_janela:
        return [], []
    janela = list(st.session_state.historico_numeros)[-st.session_state.tamanho_janela:]
    feats = extrair_features(janela).reshape(1,-1)
    try:
        probs = modelo.predict_proba(feats)[0]
        # classes may be {1,2,3} but CatBoost returns in label order, ensure mapping:
        classes = list(modelo.classes_)
        idxs = np.argsort(probs)[::-1][:2]
        top = [(int(classes[i]), float(probs[i])) for i in idxs]
        return top
    except Exception as e:
        st.debug(f"Erro prever {tipo}: {e}")
        return [], []

def enviar_telegram(msg:str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

# =========================
# Fluxo principal (sem threads)
# =========================

# Autorefresh do Streamlit (ativa o script repetidas vezes)
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto_refresh_key")

# 1) captura - manual ou automática
manual_flag = st.session_state.pop("_manual_capture", False) if "_manual_capture" in st.session_state else False
numero = None
if manual_flag:
    numero = capturar_numero_api()
else:
    # tentativa automática a cada refresh
    numero = capturar_numero_api()

# 2) se veio número e for novo -> salva e processa
if numero is not None and (st.session_state.ultimo_numero_salvo is None or numero != st.session_state.ultimo_numero_salvo):
    # atualiza último
    st.session_state.ultimo_numero_salvo = numero
    # salva histórico
    salvar_historico(numero)

    # Resultado do último alerta (se existia uma ultima_entrada) -> enviar GREEN/RED
    # ultima_entrada foi salva como string como "Tipo [ (classe,prob),... ]"
    # Precisamos comparar se o valor real caiu dentro da previsão enviada (duzia/coluna)
    if st.session_state.ultima_entrada:
        # ultima_entrada é dict-like string? vamos armazenar como dict no state:
        ent = st.session_state.ultima_entrada  # estrutura: {"tipo":"Dúzia","classes":[(c,p),...]}
        try:
            tipo = ent.get("tipo")
            classes = [c for c,_ in ent.get("classes",[])]
            acerto = False
            if tipo == "Dúzia":
                if numero_para_duzia(numero) in classes:
                    acerto = True
            elif tipo == "Coluna":
                if numero_para_coluna(numero) in classes:
                    acerto = True
            # envia resultado
            if acerto:
                st.session_state.acertos_top += 1
                enviar_telegram(f"✅ Saiu {numero} — ACERTO! ({tipo})")
            else:
                enviar_telegram(f"❌ Saiu {numero} — ERRO. ({tipo})")
            st.session_state.total_top += 1
        except Exception:
            pass

    # Após salvar resultado, geramos nova previsão com os modelos atuais (se existirem)
    # Treinamos modelos de forma conservadora quando houver dados suficientes e a cada TRAIN_EVERY novos giros
    if len(st.session_state.historico_numeros) >= st.session_state.tamanho_janela + 3:
        # treinar a cada TRAIN_EVERY novas inserções
        if len(st.session_state.historico_numeros) % TRAIN_EVERY == 0:
            treinar_modelo("duzia")
            treinar_modelo("coluna")

    # Previsão atual (top-2) para enviar entrada (anti-spam aplicado)
    top_duzia = prever("duzia")  # [(class,prob), ...]
    top_coluna = prever("coluna")

    # Escolha entre dúzia/coluna por soma de probabilidades (simples)
    sum_duzia = sum(p for _,p in top_duzia) if top_duzia else 0.0
    sum_coluna = sum(p for _,p in top_coluna) if top_coluna else 0.0

    chosen = None
    if sum_duzia == 0 and sum_coluna == 0:
        chosen = None
    elif sum_duzia >= sum_coluna:
        chosen = ("Dúzia", top_duzia)
    else:
        chosen = ("Coluna", top_coluna)

    if chosen:
        tipo, classes_probs = chosen
        # filtra por prob_minima
        classes_probs = [(c,p) for c,p in classes_probs if p >= st.session_state.prob_minima]
        if classes_probs:
            # monta estrutura para comparar/armazenar
            entrada_obj = {"tipo": tipo, "classes": classes_probs}
            chave = f"{tipo}_" + "_".join(str(c) for c,_ in classes_probs)
            # anti-spam: novo envio se chave diferente ou contador >= 3
            if chave != st.session_state.ultima_entrada.get("chave") if isinstance(st.session_state.ultima_entrada, dict) else True:
                # enviar
                txt = f"📊 <b>ENTRADA {tipo}</b>: " + ", ".join(f"{c} ({p*100:.1f}%)" for c,p in classes_probs)
                enviar_telegram(txt)
                # salvar última entrada com chave / estrutura
                entrada_obj["chave"] = chave
                st.session_state.ultima_entrada = entrada_obj
                st.session_state.contador_sem_envio = 0
            else:
                # mesma entrada: aumenta contador
                st.session_state.contador_sem_envio += 1
                # se passou 3 rodadas sem envio, força reenvio
                if st.session_state.contador_sem_envio >= 3:
                    txt = f"📊 <b>ENT{tipo}</b>: " + ", ".join(f"{c} ({p*100:.1f}%)" for c,p in classes_probs)
                    enviar_telegram(txt)
                    st.session_state.contador_sem_envio = 0
        # else: nenhuma classe acima da prob_minima -> não envia entrada

    # salva estado parcial (não salva modelos grandes)
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
# EXIBIÇÃO (UI)
# =========================
st.subheader("📌 Últimos números capturados")
if len(st.session_state.historico_numeros) > 0:
    ult = list(st.session_state.historico_numeros)[-20:]
    st.write(ult)
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

# Previsões atuais (exibição)
st.subheader("🔮 Previsões (Top-2) — modelos atuais")
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
