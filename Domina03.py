# Domina_IA_Pro_v2.py  -- versão melhorada (treino + previsão)
import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from sklearn.ensemble import RandomForestClassifier
from catboost import CatBoostClassifier, Pool
import numpy as np
import logging
import joblib
import pandas as pd
from typing import List, Dict, Any, Tuple
import time
from sklearn.model_selection import train_test_split

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
DATASET_PATH = "dataset_deslocamento.csv"
MODEL_CAT_PATH = "model_catboost.joblib"
MODEL_RF_PATH = "model_rf.joblib"
META_PATH = "meta_deslocamento.json"

API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}
# Recomendo mover TOKEN e CHAT_ID para variáveis de ambiente no deploy
#TELEGRAM_TOKEN = os.environ.get("ROULETTE_TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
#CHAT_ID = os.environ.get("ROULETTE_CHAT_ID", "-1002940111195")
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# Hyperparameters (ajustáveis)
WINDOW = 120                 # janela de deltas usada para features (maior histórico)
BATCH_TREINO = 50            # quantidade mínima de novas amostras para acionar re-treino incremental
MIN_TRAIN_SAMPLES = 200      # exigir ao menos 200 amostras no dataset para treinar (sua sugestão)
TOP_K = 3                    # top K deltas / números previstos (para seleção inicial)
MAX_NUMEROS_APOSTA = 14      # limite final de números previstos
RANDOM_SEED = 42
N_FEATURES_SEL = 80          # número de features a manter após seleção por importance

# =============================
# Utilitários
# =============================
def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_msg(msg, tipo="previsao"):
    if tipo == "previsao":
        st.success(msg)
        enviar_telegram(msg)
    else:
        st.info(msg)
        enviar_telegram(msg)

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            historico = json.load(f)
        historico_padronizado = []
        for h in historico:
            if isinstance(h, dict):
                historico_padronizado.append(h)
            else:
                historico_padronizado.append({"number": h, "timestamp": f"manual_{len(historico_padronizado)}"})
        return historico_padronizado
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f, indent=2)

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def numero_para_cor(num: int) -> str:
    vermelho = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    if num == 0:
        return "green"
    if num in vermelho:
        return "red"
    return "black"

def numero_para_duzia(num: int) -> int:
    if num == 0:
        return 0
    return (((num-1)//12) + 1)

def numero_para_coluna(num: int) -> int:
    if num == 0:
        return 0
    if num % 3 == 1:
        return 1
    if num % 3 == 2:
        return 2
    return 3

def terminal(num: int) -> int:
    return num % 10

def par_impar(num:int) -> int:
    if num==0: return -1
    return num %2

def distancia_minima_layout(a:int,b:int,layout=ROULETTE_LAYOUT) -> int:
    la = layout.index(a)
    lb = layout.index(b)
    N = len(layout)
    d = abs(lb - la)
    return min(d, N - d)

def vizinhos_fisicos(num:int, k:int=2, layout=ROULETTE_LAYOUT) -> List[int]:
    idx = layout.index(num)
    res=[]
    for i in range(1,k+1):
        res.append(layout[(idx - i) % len(layout)])
    for i in range(1,k+1):
        res.append(layout[(idx + i) % len(layout)])
    return res

# =============================
# Feature engineering e dataset
# =============================
def calcular_deltas(numeros: List[int], layout=ROULETTE_LAYOUT) -> List[int]:
    deltas=[]
    for i in range(1,len(numeros)):
        pos_anterior = layout.index(numeros[i-1])
        pos_atual = layout.index(numeros[i])
        delta = (pos_atual - pos_anterior) % len(layout)
        deltas.append(delta)
    return deltas

def extrair_features_janela(historico_nums: List[int], janela: int = WINDOW) -> Dict[str, Any]:
    features = {}
    n = len(historico_nums)
    ultimo = historico_nums[-1]
    features['last_number'] = ultimo
    features['last_terminal'] = terminal(ultimo)
    features['last_duzia'] = numero_para_duzia(ultimo)
    features['last_coluna'] = numero_para_coluna(ultimo)
    features['last_color'] = numero_para_cor(ultimo)
    features['last_par_impar'] = par_impar(ultimo)

    cnt = Counter(historico_nums[-janela:])
    for num in range(37):
        features[f'cnt_num_{num}'] = cnt.get(num, 0)

    cnt_duzia = Counter([numero_para_duzia(x) for x in historico_nums[-janela:]])
    cnt_coluna = Counter([numero_para_coluna(x) for x in historico_nums[-janela:]])
    cnt_terminal = Counter([terminal(x) for x in historico_nums[-janela:]])
    for d in range(0,4):
        features[f'cnt_duzia_{d}'] = cnt_duzia.get(d,0)
    for c in range(0,4):
        features[f'cnt_coluna_{c}'] = cnt_coluna.get(c,0)
    for t in range(0,10):
        features[f'cnt_term_{t}'] = cnt_terminal.get(t,0)

    deltas = calcular_deltas(historico_nums[-(janela+1):])
    for i in range(janela):
        features[f'delta_{i}'] = deltas[i] if i < len(deltas) else -1

    dists = []
    for x in historico_nums[-(janela+1):-1]:
        dists.append(distancia_minima_layout(x, ultimo))
    if dists:
        features['dist_mean'] = float(np.mean(dists))
        features['dist_std'] = float(np.std(dists))
    else:
        features['dist_mean'] = 0.0
        features['dist_std'] = 0.0

    last_pos = {}
    for i, num in enumerate(reversed(historico_nums)):
        if num not in last_pos:
            last_pos[num] = i
    for num in range(37):
        features[f'last_seen_{num}'] = last_pos.get(num, -1)

    return features

def construir_dataset_completo(historico: List[Dict[str,Any]], janela:int=WINDOW) -> pd.DataFrame:
    nums = [h['number'] for h in historico]
    rows=[]
    for i in range(janela, len(nums)):
        contexto = nums[i-janela:i+1]
        features = extrair_features_janela(contexto[:-1], janela=janela)
        label = contexto[-1]
        features['label'] = int(label)
        rows.append(features)
    if len(rows)==0:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df

# =============================
# Modelo Ensemble: CatBoost + RandomForest (melhorias)
# =============================
class IA_Deslocamento_Pro_v2:
    def __init__(self, layout=None, janela=WINDOW, top_k=TOP_K, max_numeros=MAX_NUMEROS_APOSTA):
        self.layout = layout or ROULETTE_LAYOUT
        self.janela = janela
        self.top_k = top_k
        self.max_numeros = max_numeros

        self.model_cat = None
        self.model_rf = None
        self.treinado = False

        self.meta = {
            "trained_on": 0,
            "last_trained_at": None,
            "selected_features": None,
            "model_scores": {}
        }
        self._carregar_modelos_e_meta()

    def _carregar_modelos_e_meta(self):
        if os.path.exists(MODEL_CAT_PATH) and os.path.exists(MODEL_RF_PATH):
            try:
                self.model_cat = joblib.load(MODEL_CAT_PATH)
                self.model_rf = joblib.load(MODEL_RF_PATH)
                self.treinado = True
            except Exception as e:
                logging.error(f"Falha ao carregar modelos: {e}")
                self.model_cat = None
                self.model_rf = None
                self.treinado = False
        if os.path.exists(META_PATH):
            try:
                with open(META_PATH, "r") as f:
                    self.meta.update(json.load(f))
            except Exception as e:
                logging.error(f"Erro ao carregar meta: {e}")

    def _salvar_modelos_e_meta(self):
        try:
            if self.model_cat is not None:
                joblib.dump(self.model_cat, MODEL_CAT_PATH)
            if self.model_rf is not None:
                joblib.dump(self.model_rf, MODEL_RF_PATH)
            with open(META_PATH, "w") as f:
                json.dump(self.meta, f, indent=2)
        except Exception as e:
            logging.error(f"Erro ao salvar modelos/meta: {e}")

    def precisa_treinar(self, historico: List[Dict[str,Any]]) -> bool:
        df = construir_dataset_completo(historico, janela=self.janela)
        n = len(df)
        if n == 0:
            return False
        # treina apenas se dataset >= MIN_TRAIN_SAMPLES e houver crescimento suficiente
        if n < MIN_TRAIN_SAMPLES:
            return False
        if n - self.meta.get("trained_on", 0) >= BATCH_TREINO:
            return True
        return False

    def treinar(self, historico: List[Dict[str,Any]]):
        df = construir_dataset_completo(historico, janela=self.janela)
        if df.empty or len(df) < MIN_TRAIN_SAMPLES:
            logging.info("Dataset insuficiente para treinar (precisa de MIN_TRAIN_SAMPLES).")
            return False

        # shuffle/split
        df = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
        X = df.drop(columns=['label'])
        y = df['label'].astype(int)

        # one-hot para cores (se existir)
        color_cols = [c for c in X.columns if c.endswith('_color')]
        if color_cols:
            X_proc = pd.get_dummies(X, columns=color_cols, dummy_na=True)
        else:
            X_proc = X.copy()

        # salvar dataset (apenas para auditoria)
        try:
            X_proc['label'] = y
            X_proc.to_csv(DATASET_PATH, index=False)
        except Exception as e:
            logging.error(f"Falha salvar dataset: {e}")

        # divisão treino/val rápida para avaliar pesos do ensemble
        X_train, X_val, y_train, y_val = train_test_split(X_proc, y, test_size=0.18, random_state=RANDOM_SEED, stratify=y if len(y.unique())>1 else None)

        # Treinar RandomForest
        rf_score = 0.0
        try:
            rf = RandomForestClassifier(
                n_estimators=200,
                max_depth=12,
                random_state=RANDOM_SEED,
                n_jobs=-1,
                class_weight=None
            )
            rf.fit(X_train.drop(columns=['label'], errors='ignore'), y_train)
            # validação rf
            try:
                rf_score = rf.score(X_val.drop(columns=['label'], errors='ignore'), y_val)
            except Exception:
                rf_score = 0.0
            self.model_rf = rf
        except Exception as e:
            logging.error(f"Erro treinando RandomForest: {e}")
            self.model_rf = None

        # Treinar CatBoost com early stopping (economiza tempo)
        cb_score = 0.0
        try:
            cb = CatBoostClassifier(
                iterations=600,
                depth=6,
                learning_rate=0.05,
                l2_leaf_reg=3,
                loss_function="MultiClass",
                random_seed=RANDOM_SEED,
                verbose=0
            )
            # se muitas classes / poucas amostras, preparar Pool
            pool_train = Pool(X_train.drop(columns=['label'], errors='ignore'), y_train)
            pool_val = Pool(X_val.drop(columns=['label'], errors='ignore'), y_val)
            cb.fit(pool_train, eval_set=pool_val, early_stopping_rounds=40, use_best_model=True, verbose=False)
            try:
                cb_score = cb.score(X_val.drop(columns=['label'], errors='ignore'), y_val)
            except Exception:
                cb_score = 0.0
            self.model_cat = cb
        except Exception as e:
            logging.error(f"Erro treinando CatBoost: {e}")
            self.model_cat = None

        # Seleção de features usando importances do RF (se existir), senão usar todas
        selected = None
        try:
            if self.model_rf is not None:
                importances = self.model_rf.feature_importances_
                cols = X_train.drop(columns=['label'], errors='ignore').columns.tolist()
                pairs = list(zip(cols, importances))
                pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
                selected = [p[0] for p in pairs_sorted[:N_FEATURES_SEL]]
            else:
                selected = X_train.drop(columns=['label'], errors='ignore').columns.tolist()[:N_FEATURES_SEL]
        except Exception as e:
            logging.error(f"Erro selecionando features: {e}")
            selected = X_train.drop(columns=['label'], errors='ignore').columns.tolist()[:N_FEATURES_SEL]

        # atualizar meta
        self.meta['trained_on'] = len(df)
        self.meta['last_trained_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.meta['selected_features'] = selected
        self.meta['model_scores'] = {
            "rf_val_score": float(rf_score),
            "cb_val_score": float(cb_score)
        }
        self.treinado = (self.model_cat is not None or self.model_rf is not None)
        self._salvar_modelos_e_meta()
        return self.treinado

    def _preparar_features_entrada(self, historico: List[Dict[str,Any]]):
        nums = [h['number'] for h in historico]
        if len(nums) < self.janela:
            return None, None
        contexto = nums[-self.janela:]
        feat = extrair_features_janela(contexto, janela=self.janela)
        X = pd.DataFrame([feat])
        # aplicar mesmo one-hot do treino (cores) se houver
        color_cols = [c for c in X.columns if c.endswith('_color')]
        if color_cols:
            X_proc = pd.get_dummies(X, columns=color_cols, dummy_na=True)
        else:
            X_proc = X.copy()

        # alinhar com selected_features salvo na meta (se houver)
        sel = self.meta.get('selected_features')
        if sel:
            for c in sel:
                if c not in X_proc.columns:
                    X_proc[c] = 0
            # descartar extras
            for c in list(X_proc.columns):
                if c not in sel:
                    X_proc.drop(columns=[c], inplace=True)
            X_proc = X_proc[sel]
        else:
            # se não há seleção, manter todas colunas atuais
            pass

        return X_proc, feat

    def prever(self, historico: List[Dict[str,Any]]) -> List[int]:
        if not self.treinado:
            return []

        X_proc, feat_raw = self._preparar_features_entrada(historico)
        if X_proc is None:
            return []

        probs_agg = None
        classes = None
        model_weights = []

        # obter scores para ponderar (se disponíveis)
        meta_scores = self.meta.get('model_scores', {})
        cb_score = meta_scores.get('cb_val_score', 0.0)
        rf_score = meta_scores.get('rf_val_score', 0.0)
        # normalizar pesos
        total = max(cb_score + rf_score, 1e-6)
        weight_cb = cb_score / total if cb_score>0 else 0.5
        weight_rf = rf_score / total if rf_score>0 else 0.5

        # CatBoost predict_proba (com fallback)
        try:
            if self.model_cat is not None:
                try:
                    proba_cb = np.array(self.model_cat.predict_proba(X_proc))
                except Exception:
                    # fallback usa predict
                    pred_cb = int(self.model_cat.predict(X_proc)[0])
                    proba_cb = np.zeros((1, 37))
                    proba_cb[0, pred_cb] = 0.9
                classes_cb = np.array(self.model_cat.classes_, dtype=int)
                probs_agg = proba_cb * weight_cb
                classes = classes_cb
                model_weights.append(('cb', weight_cb))
        except Exception as e:
            logging.error(f"Erro predict_proba CatBoost: {e}")

        # RandomForest predict_proba (com fallback)
        try:
            if self.model_rf is not None:
                try:
                    proba_rf = np.array(self.model_rf.predict_proba(X_proc))
                except Exception:
                    pred_rf = int(self.model_rf.predict(X_proc)[0])
                    proba_rf = np.zeros((1, 37))
                    proba_rf[0, pred_rf] = 0.9
                classes_rf = np.array(self.model_rf.classes_, dtype=int)
                if classes is None:
                    probs_agg = proba_rf * weight_rf
                    classes = classes_rf
                else:
                    # union das classes
                    union_classes = np.union1d(classes, classes_rf)
                    probs_sum = np.zeros((1, len(union_classes)))
                    # map cb
                    for i,c in enumerate(classes):
                        idx = int(np.where(union_classes == c)[0][0])
                        probs_sum[0, idx] += (probs_agg[0,i] if probs_agg is not None else 0)
                    # map rf
                    for i,c in enumerate(classes_rf):
                        idx = int(np.where(union_classes == c)[0][0])
                        probs_sum[0, idx] += proba_rf[0,i] * weight_rf / weight_cb if weight_cb>0 else proba_rf[0,i]
                    # média ponderada (normalizando pelos pesos aproximados)
                    probs_agg = probs_sum / 2.0
                    classes = union_classes
                model_weights.append(('rf', weight_rf))
        except Exception as e:
            logging.error(f"Erro predict_proba RF: {e}")

        if probs_agg is None or classes is None:
            return []

        probs = probs_agg[0]
        # ordenar e pegar top_k
        top_idx = np.argsort(probs)[::-1]
        top_classes = [int(classes[i]) for i in top_idx if classes.size>0]

        # retirar o último número como prioridade trivial (evita repetir o último como previsão)
        ultimo_num = feat_raw['last_number']
        filtered_top = [c for c in top_classes if c != ultimo_num]
        if len(filtered_top) < self.top_k:
            # se removido demais, permite colocar o ultimo de volta no final
            filtered_top = top_classes[:self.top_k]

        chosen = filtered_top[:self.top_k]

        # Construir lista final com vizinhos (1 lado primeiro, depois expandir)
        numeros_previstos = []
        for num in chosen:
            if num not in numeros_previstos:
                numeros_previstos.append(num)
            idx = self.layout.index(num)
            left = self.layout[(idx-1) % len(self.layout)]
            right = self.layout[(idx+1) % len(self.layout)]
            for v in (left, right):
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        # expandir até max com vizinhos secundários
        if len(numeros_previstos) < self.max_numeros:
            for num in chosen:
                extra = vizinhos_fisicos(num, k=2, layout=self.layout)
                for v in extra:
                    if v not in numeros_previstos:
                        numeros_previstos.append(v)
                    if len(numeros_previstos) >= self.max_numeros:
                        break
                if len(numeros_previstos) >= self.max_numeros:
                    break

        numeros_previstos = numeros_previstos[:self.max_numeros]
        return numeros_previstos

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional v2", layout="centered")
st.title("🎯 Roleta — IA de Deslocamento Físico Profissional (v2)")

st_autorefresh(interval=3000, key="refresh_v2")

if "estrategia" not in st.session_state:
    st.session_state.estrategia = deque(maxlen=10000)
    historico = carregar_historico()
    for h in historico:
        st.session_state.estrategia.append(h)
    st.session_state.ia = IA_Deslocamento_Pro_v2(janela=WINDOW)
    st.session_state.previsao = []
    st.session_state.acertos = 0
    st.session_state.erros = 0
    st.session_state.last_alert = None
    st.session_state.rounds_since_alert = 0
    st.session_state.samples_since_train = 0

# UI
col1, col2, col3 = st.columns([1,1,1])
with col1:
    janela = st.slider("📏 Tamanho da janela (janela)", min_value=30, max_value=240, value=WINDOW, step=1)
with col2:
    top_k = st.slider("🔝 Top K (números mais prováveis)", min_value=1, max_value=6, value=TOP_K, step=1)
with col3:
    max_nums = st.slider("🎯 Máx. números na aposta", min_value=6, max_value=20, value=MAX_NUMEROS_APOSTA, step=1)

st.session_state.ia.janela = janela
st.session_state.ia.top_k = top_k
st.session_state.ia.max_numeros = max_nums

resultado = fetch_latest_result()
ultimo_ts = st.session_state.estrategia[-1]["timestamp"] if st.session_state.estrategia else None

if resultado and resultado.get("timestamp") and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": int(resultado["number"]), "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.append(numero_dict)
    salvar_historico(list(st.session_state.estrategia))
    st.session_state.samples_since_train += 1

    # conferir se previsao anterior acertou
    if st.session_state.previsao:
        if numero_dict["number"] in st.session_state.previsao:
            enviar_msg(f"🟢 GREEN! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.acertos += 1
        else:
            enviar_msg(f"🔴 RED! Saiu {numero_dict['number']}", tipo="resultado")
            st.session_state.erros += 1

    # decidir se treinar
    try:
        if st.session_state.ia.precisa_treinar(list(st.session_state.estrategia)):
            treinou = st.session_state.ia.treinar(list(st.session_state.estrategia))
            if treinou:
                enviar_msg(f"✅ Modelo treinado em {st.session_state.ia.meta.get('trained_on')} amostras", tipo="previsao")
                st.session_state.samples_since_train = 0
            else:
                logging.info("Tentativa de treino não produziu modelo")
    except Exception as e:
        logging.error(f"Erro na rotina de treino: {e}")

    # nova previsão
    prox_numeros = st.session_state.ia.prever(list(st.session_state.estrategia))
    if prox_numeros:
        enviar = False
        if st.session_state.last_alert is None:
            enviar = True
        else:
            if set(prox_numeros[:top_k]) != set(st.session_state.last_alert[:top_k]):
                enviar = True
            else:
                st.session_state.rounds_since_alert += 1
                if st.session_state.rounds_since_alert >= 3:
                    enviar = True
        if enviar:
            st.session_state.previsao = prox_numeros
            st.session_state.last_alert = prox_numeros.copy()
            st.session_state.rounds_since_alert = 0
            msg_alerta = "🎯 Próximos números prováveis: " + " ".join(str(n) for n in prox_numeros)
            enviar_msg(msg_alerta, tipo="previsao")
        else:
            logging.info("Previsão igual à anterior — não enviando alerta")

# --- Histórico ---
st.subheader("📜 Histórico (últimos 30 números)")
st.write(list(st.session_state.estrategia)[-30:])

# --- Estatísticas ---
total = st.session_state.acertos + st.session_state.erros
taxa = (st.session_state.acertos / total * 100) if total > 0 else 0.0
st.subheader("📊 Estatísticas")
col1, col2, col3 = st.columns(3)
col1.metric("🟢 GREEN", st.session_state.acertos)
col2.metric("🔴 RED", st.session_state.erros)
col3.metric("✅ Taxa de acerto (exato)", f"{taxa:.1f}%")

st.write("Modelo treinado:", "Sim" if st.session_state.ia.treinado else "Não")
st.write("Meta (amostras treinadas):", st.session_state.ia.meta.get("trained_on"))
st.write("Último treino:", st.session_state.ia.meta.get("last_trained_at"))
st.write("Selected features (len):", len(st.session_state.ia.meta.get("selected_features") or []))

with st.expander("⚙️ Ferramentas avançadas"):
    st.write("Dataset salvo:", os.path.exists(DATASET_PATH))
    if os.path.exists(DATASET_PATH):
        df = pd.read_csv(DATASET_PATH)
        st.write("Amostras no dataset:", len(df))
        if st.button("📥 Baixar dataset CSV"):
            st.download_button("Download dataset", data=open(DATASET_PATH, "rb").read(), file_name="dataset_deslocamento.csv")
    if st.button("🔁 Forçar re-treinamento agora"):
        try:
            ok = st.session_state.ia.treinar(list(st.session_state.estrategia))
            if ok:
                st.success("Treino forçado concluído.")
            else:
                st.warning("Treino forçado não produziu modelo (dataset insuficiente).")
        except Exception as e:
            st.error(f"Erro no treino forçado: {e}")

    if st.button("🧹 Reset modelos (apagar arquivos)"):
        for p in (MODEL_CAT_PATH, MODEL_RF_PATH, DATASET_PATH, META_PATH):
            if os.path.exists(p):
                os.remove(p)
        st.session_state.ia = IA_Deslocamento_Pro_v2(janela=janela)
        st.success("Modelos apagados e IA reinicializada.")

st.markdown("""
**Notas rápidas**
- Treino automático exige ao menos `MIN_TRAIN_SAMPLES` amostras (evita treinar com pouco histórico).
- Após o treino, seleciono as features mais importantes (reduz ruído). Isso melhora estabilidade da predição.
- Ensemble usa pesos baseados em validação interna (em vez de média simples).
- Mova o token do Telegram para variável de ambiente `ROULETTE_TELEGRAM_TOKEN` por segurança.
""")
