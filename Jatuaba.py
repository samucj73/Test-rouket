import streamlit as st
import requests
import json
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import SGDClassifier
import time
import numpy as np

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_incremental.pkl"
HISTORICO_PATH = "historico.pkl"

# === INICIALIZAÇÃO ===
st.set_page_config(layout="wide")
st.title("🎯 Estratégia IA Inteligente - Alertas v3.1 (otimizado)")

# === VARIÁVEIS DE ESTADO (inicializa / carrega) ===
HIST_MAXLEN = 1000  # aumentado para maior estabilidade
if os.path.exists(HISTORICO_PATH):
    historico_salvo = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(historico_salvo, maxlen=HIST_MAXLEN)
else:
    st.session_state.historico = deque(maxlen=HIST_MAXLEN)

defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": [],
    "entrada_info": None,
    "alertas_enviados": set(),
    "feedbacks_processados": set(),
    "greens": 0,
    "reds": 0,
    "historico_probs": deque(maxlen=200),
    "nova_entrada": False,
    "tempo_alerta": 0,
    "greens_terminal": 0,
    "greens_vizinho": 0,
    "greens_probs": [],  # lista para confiança dos greens
    "total_alertas": 0
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# === AUTOREFRESH ===
st_autorefresh(interval=2500, key="refresh")

# === ORDEM FÍSICA ROLETA ===
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

# ===== Ajuste: vizinhos reduzidos para 1 de cada lado (mais precisão nos terminais) =====
def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-1, 2)]

def expandir_com_vizinhos(numeros):
    entrada = set()
    for numero in numeros:
        entrada.update(get_vizinhos(numero))
    return sorted(entrada)

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        st.error(f"Erro ao enviar para Telegram: {e}")

# ===== Features mais ricas =====
def extrair_features(janela):
    # janela é lista de inteiros (ex: 12 elementos)
    features = {f"num_{i}": int(n) for i, n in enumerate(janela)}
    features["media"] = float(sum(janela) / len(janela))
    features["ultimo"] = int(janela[-1])
    most_common = Counter(janela).most_common(1)
    features["moda"] = int(most_common[0][0]) if most_common else int(janela[-1])
    features["qtd_pares"] = int(sum(1 for n in janela if n % 2 == 0))
    features["qtd_baixos"] = int(sum(1 for n in janela if n <= 18))
    # terminal (unidade) distribution
    unidades = [n % 10 for n in janela]
    for d in range(10):
        features[f"unid_{d}"] = int(unidades.count(d))
    return features

# ===== Modelo (incremental) =====
def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    # SGDClassifier com probabilidade via log loss
    return SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

# === CAPTURA DA API ===
try:
    resposta = requests.get(API_URL, timeout=5)
    if resposta.status_code == 200:
        dados = resposta.json()
        try:
            numero = int(dados["data"]["result"]["outcome"]["number"])
            timestamp = dados["data"]["settledAt"]
        except Exception:
            numero = None
            timestamp = None

        if numero is not None and timestamp != st.session_state.ultimo_timestamp:
            st.session_state.historico.append(numero)
            st.session_state.ultimo_timestamp = timestamp
            joblib.dump(list(st.session_state.historico), HISTORICO_PATH)
            st.success(f"🎯 Novo número: {numero}")
    else:
        st.error("Erro ao acessar a API.")
except Exception as e:
    st.error(f"Erro na requisição: {e}")

# === TREINAMENTO (com sample_weight para priorizar terminais) ===
modelo = carregar_modelo()
historico = list(st.session_state.historico)
if len(historico) >= 14:
    X_rows, y_rows, w_rows = [], [], []
    for i in range(len(historico) - 13):
        janela = historico[i:i + 12]           # 12 usados como features
        numero_13 = historico[i + 12]         # posição 13
        numero_14 = historico[i + 13]         # target real

        # dominantes por unidades (terminais)
        unidades = [n % 10 for n in janela]
        contagem = Counter(unidades)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        X_rows.append(extrair_features(janela))

        # label: 1 se caiu dentro da expansão (terminal ou vizinho), 0 caso contrário
        y = 1 if numero_14 in entrada_expandida else 0

        # peso: 1.0 para terminal puro, 0.5 para vizinho, 1.0 para negativo (manter equilíbrio)
        if numero_14 in entrada_principal:
            weight = 1.0
        elif numero_14 in entrada_expandida:
            weight = 0.5
        else:
            weight = 1.0

        y_rows.append(y)
        w_rows.append(weight)

    if X_rows:
        df_X = pd.DataFrame(X_rows).fillna(0)
        y_arr = np.array(y_rows)
        w_arr = np.array(w_rows)

        try:
            # partial_fit com sample_weight
            modelo.partial_fit(df_X, y_arr, classes=[0, 1], sample_weight=w_arr)
        except Exception:
            modelo.fit(df_X, y_arr, sample_weight=w_arr)
        salvar_modelo(modelo)

# === PREVISÃO E ENTRADA INTELIGENTE (com limiar adaptativo) ===
historico_numeros = list(st.session_state.historico)
if len(historico_numeros) >= 14:
    janela = historico_numeros[-14:-2]  # 12 elementos
    X_pred = pd.DataFrame([extrair_features(janela)]).fillna(0)

    try:
        probs = modelo.predict_proba(X_pred)[0]
        prob = probs[1] if len(probs) > 1 else 0.0
    except Exception:
        prob = 0.0

    st.session_state.historico_probs.append(prob)

    # === Limiar adaptativo: sobe se houver muitos REDs relativos aos GREENS ===
    total_feedbacks = st.session_state.greens + st.session_state.reds
    if total_feedbacks == 0:
        ajuste = 0.0
    else:
        # proporção de REDs: quanto maior, maior o ajuste
        prop_red = st.session_state.reds / total_feedbacks
        ajuste = min(0.10, prop_red * 0.15)  # ajusta até +0.10 no máximo

    LIMIAR_BASE = 0.60
    limiar = LIMIAR_BASE + ajuste

    if prob > limiar and not st.session_state.entrada_atual:
        unidades = [n % 10 for n in janela]
        contagem = Counter(unidades)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        historico_recente = historico_numeros[-50:]
        contagem_freq = Counter(historico_recente)

        def score_numero(n):
            freq = contagem_freq[n]
            dist = min(abs(ROULETTE_ORDER.index(n) - ROULETTE_ORDER.index(d)) for d in entrada_principal)
            return freq + (1.5 if n in entrada_principal else 0) + (0.5 if dist <= 1 else 0)

        entrada_classificada = sorted(entrada_expandida, key=lambda n: score_numero(n), reverse=True)
        entrada_inteligente = sorted(entrada_classificada[:15])  # ordenado do menor para o maior

        chave_alerta = f"{dominantes}-{entrada_inteligente}"
        if chave_alerta not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave_alerta)
            numeros_linha = " ".join(str(n) for n in entrada_inteligente)
            enviar_telegram(numeros_linha)
            st.session_state.nova_entrada = True
            st.session_state.tempo_alerta = time.time()
            st.session_state.total_alertas += 1
            # registra probabilidade dessa entrada para análise posterior
            st.session_state.entrada_info = {
                "terminais": dominantes,
                "entrada": entrada_inteligente,
                "probabilidade": round(prob, 3),
                "timestamp": time.time()
            }
            # grava prob do alerta (mesmo que seja posteriormente RED/GREEN)
            st.session_state.greens_probs.append(prob)  # usamos esta lista como "probs de alertas" (filtraremos depois)

        st.session_state.entrada_atual = entrada_inteligente

# === FEEDBACK (avalia se foi GREEN ou RED e atualiza métricas detalhadas) ===
if st.session_state.entrada_atual:
    entrada = st.session_state.entrada_atual
    if len(st.session_state.historico) == 0:
        numero_atual = None
    else:
        numero_atual = st.session_state.historico[-1]
    chave_feedback = f"{numero_atual}-{tuple(sorted(entrada))}"

    if chave_feedback not in st.session_state.feedbacks_processados and numero_atual is not None:
        resultado = "✅ GREEN" if numero_atual in entrada else "❌ RED"
        cor = "green" if resultado == "✅ GREEN" else "red"

        st.markdown(
            f"<h3 style='color:{cor}'>{resultado} • Número: {numero_atual}</h3>",
            unsafe_allow_html=True
        )

        if resultado == "✅ GREEN":
            st.session_state.greens += 1

            # ===== Verifica se o green foi terminal puro ou vizinho =====
            # usa os terminais estimados da entrada_info (se disponível)
            if st.session_state.entrada_info and "terminais" in st.session_state.entrada_info:
                dominantes = st.session_state.entrada_info["terminais"]
            else:
                unidades = [n % 10 for n in historico_numeros[-14:-2]]
                dominantes = [t for t, _ in Counter(unidades).most_common(2)]

            numeros_terminais = [n for n in range(37) if n % 10 in dominantes]
            vizinhos_terminais = set()
            for n in numeros_terminais:
                vizinhos_terminais.update(get_vizinhos(n))

            if numero_atual in numeros_terminais:
                st.session_state.greens_terminal += 1
            elif numero_atual in vizinhos_terminais:
                st.session_state.greens_vizinho += 1

            # registra confiança do green (se tivemos uma prob associada à entrada_info)
            if st.session_state.entrada_info and "probabilidade" in st.session_state.entrada_info:
                st.session_state.greens_probs.append(st.session_state.entrada_info["probabilidade"])

        else:
            st.session_state.reds += 1

        enviar_telegram(f"{resultado} • Saiu {numero_atual}")
        st.session_state.feedbacks_processados.add(chave_feedback)

        # feedback incremental para o modelo (aprendizado online)
        try:
            janela = list(st.session_state.historico)[-14:-2]
            if len(janela) == 12:
                X_novo = pd.DataFrame([extrair_features(janela)]).fillna(0)
                y_novo = [1 if numero_atual in entrada else 0]
                # define peso de feedback semelhante ao usado no treino
                unidades = [n % 10 for n in janela]
                dominantes = [t for t, _ in Counter(unidades).most_common(2)]
                entrada_principal = [n for n in range(37) if n % 10 in dominantes]
                entrada_expandida = expandir_com_vizinhos(entrada_principal)
                if numero_atual in entrada_principal:
                    weight_novo = np.array([1.0])
                elif numero_atual in entrada_expandida:
                    weight_novo = np.array([0.5])
                else:
                    weight_novo = np.array([1.0])

                try:
                    modelo.partial_fit(X_novo, y_novo, classes=[0,1], sample_weight=weight_novo)
                except Exception:
                    modelo.fit(X_novo, y_novo, sample_weight=weight_novo)
                salvar_modelo(modelo)
        except Exception as e:
            st.error(f"Erro no feedback: {e}")

    # reset da entrada atual para aguardar próxima rodada
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = None

# === INTERFACE DE MÉTRICAS (painel expandido) ===
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("✅ GREENS", st.session_state.greens)
with col2:
    st.metric("❌ REDS", st.session_state.reds)
with col3:
    total = st.session_state.greens + st.session_state.reds
    taxa = (st.session_state.greens / total * 100) if total > 0 else 0
    st.metric("🎯 Taxa de Acerto", f"{taxa:.1f}%")
with col4:
    st.metric("🎯 GREEN Terminal", st.session_state.greens_terminal)
with col5:
    st.metric("🎯 GREEN Vizinho", st.session_state.greens_vizinho)

# proporção terminal/vizinho
total_greens = st.session_state.greens_terminal + st.session_state.greens_vizinho
if total_greens > 0:
    pct_terminal = (st.session_state.greens_terminal / total_greens) * 100
    pct_vizinho = (st.session_state.greens_vizinho / total_greens) * 100
    st.info(f"💡 Distribuição dos acertos GREEN → Terminal: {pct_terminal:.1f}% | Vizinho: {pct_vizinho:.1f}%")

# confiança média dos greens / qualidade dos alertas
if len(st.session_state.greens_probs) > 0:
    media_conf_greens = sum(st.session_state.greens_probs)/len(st.session_state.greens_probs)
    st.metric("⚡ Confiança média (GREENS/alertas)", f"{media_conf_greens:.3f}")
else:
    st.metric("⚡ Confiança média (GREENS/alertas)", "—")

st.write(f"Total de alertas disparados: {st.session_state.total_alertas}")
st.write(f"Limiar atual de alerta: {limiar:.3f} (base {0.60} + ajuste {ajuste:.3f})")

# === ALERTA VISUAL DE NOVA ENTRADA ===
if st.session_state.nova_entrada and time.time() - st.session_state.tempo_alerta < 5:
    st.markdown("<h3 style='color:orange'>⚙️ Nova entrada IA ativa!</h3>", unsafe_allow_html=True)
else:
    st.session_state.nova_entrada = False

# === HISTÓRICO E INFORMAÇÕES ===
st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-15:])

if st.session_state.entrada_info:
    st.subheader("📥 Entrada Atual (ordenada)")
    st.write(st.session_state.entrada_info)

# === GRÁFICO DE CONFIANÇA ===
if st.session_state.historico_probs:
    st.subheader("📈 Confiança da IA (últimas previsões)")
    plt.figure(figsize=(8, 2.5))
    plt.plot(list(st.session_state.historico_probs), marker='o')
    plt.title("Evolução da Probabilidade")
    plt.xlabel("Últimas Rodadas")
    plt.ylabel("Confiança")
    plt.grid(True)
    st.pyplot(plt)
