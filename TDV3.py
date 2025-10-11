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
import csv

# ==========================
# ============ v3.3 ========
# ==========================
# Parâmetros ajustáveis (mude aqui para testar rapidamente)
MODO_AGRESSIVO = True        # True = mais alertas (limiar base menor)
FEATURE_LEN = 14              # tamanho da janela de features
HIST_MAXLEN = 1500            # histórico guardado (aumente para estabilidade)
LIMIAR_BASE_AGRESSIVO = 0.55
LIMIAR_BASE_PADRAO = 0.60
PESO_TERMINAL = 1.2           # aumentei levemente para priorizar terminais
PESO_VIZINHO = 0.5
MOVING_AVG_WINDOW = 5         # média móvel usada para comparar confiança histórica
CSV_LOG_PATH = "historico_feedback_v33.csv"
# ==========================

# === CONFIGURAÇÕES FIXAS ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_incremental_v33.pkl"
HISTORICO_PATH = "historico_v33.pkl"

# === INICIALIZAÇÃO UI ===
st.set_page_config(layout="wide")
st.title("🎯 Estratégia IA Inteligente - v3.3 (foco em terminal)")

# === CARREGA / INICIALIZA SESSÃO ===
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
    "historico_probs": deque(maxlen=500),
    "alert_probs": [],        # probs de todos os alertas (pra média móvel)
    "greens_probs": [],       # probs dos alerts que resultaram em GREEN (análise)
    "nova_entrada": False,
    "tempo_alerta": 0,
    "greens_terminal": 0,
    "greens_vizinho": 0,
    "total_alertas": 0,
    "terminais_quentes": {},  # memória adaptativa de terminais por unidade (0-9)
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

# ===== get_vizinhos dinâmico =====
def get_vizinhos(numero):
    # define alcance com base no desempenho atual dos grees (mais alcance quando terminaiis fracos)
    try:
        term_g = st.session_state.get("greens_terminal", 0)
        viz_g = st.session_state.get("greens_vizinho", 0)
    except Exception:
        term_g, viz_g = 0, 0

    # se não houver dados, alcance padrão 1
    if term_g + viz_g == 0:
        alcance = 1
    else:
        # se terminais estão melhores, mantenha alcance 1, se vizinhos dominam, aumente alcance até 2
        if term_g >= viz_g:
            alcance = 1
        else:
            # proporção vizinho > terminal => aumenta alcance (máx 2)
            proporcao = viz_g / max(1, term_g)
            alcance = 1 if proporcao < 1.5 else 2

    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-alcance, alcance + 1)]

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

# ===== features expandidas (janela variável) =====
def extrair_features(janela):
    # janela: lista de ints length FEATURE_LEN
    features = {f"num_{i}": int(n) for i, n in enumerate(janela)}
    features["media"] = float(sum(janela) / len(janela))
    features["ultimo"] = int(janela[-1])
    most_common = Counter(janela).most_common(1)
    features["moda"] = int(most_common[0][0]) if most_common else int(janela[-1])
    features["qtd_pares"] = int(sum(1 for n in janela if n % 2 == 0))
    features["qtd_baixos"] = int(sum(1 for n in janela if n <= 18))
    unidades = [n % 10 for n in janela]
    for d in range(10):
        features[f"unid_{d}"] = int(unidades.count(d))
    return features

# ===== modelo incremental =====
def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

# === Função utilitária para log CSV ===
def log_csv(row):
    header = ["timestamp", "evento", "numero", "tipo", "prob_alerta", "limiar", "entrada"]
    write_header = not os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)

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

# === TREINAMENTO (sliding window com FEATURE_LEN) ===
modelo = carregar_modelo()
historico = list(st.session_state.historico)
if len(historico) >= FEATURE_LEN + 1:
    X_rows, y_rows, w_rows = [], [], []
    for i in range(len(historico) - FEATURE_LEN):
        janela = historico[i:i + FEATURE_LEN]      # janela de features
        target = historico[i + FEATURE_LEN]       # próximo número real

        unidades = [n % 10 for n in janela]
        contagem = Counter(unidades)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        X_rows.append(extrair_features(janela))
        y = 1 if target in entrada_expandida else 0

        if target in entrada_principal:
            weight = PESO_TERMINAL
        elif target in entrada_expandida:
            weight = PESO_VIZINHO
        else:
            weight = 1.0

        y_rows.append(y)
        w_rows.append(weight)

    if X_rows:
        df_X = pd.DataFrame(X_rows).fillna(0)
        y_arr = np.array(y_rows)
        w_arr = np.array(w_rows)

        try:
            modelo.partial_fit(df_X, y_arr, classes=[0, 1], sample_weight=w_arr)
        except Exception:
            modelo.fit(df_X, y_arr, sample_weight=w_arr)
        salvar_modelo(modelo)

# === PREVISÃO E ALERTA (com limiar adaptativo + média móvel de confiança) ===
historico_numeros = list(st.session_state.historico)
# Inicializa LIMIAR_BASE, limiar_adaptado, media_movel_alerts para evitar NameError na UI
LIMIAR_BASE = LIMIAR_BASE_AGRESSIVO if MODO_AGRESSIVO else LIMIAR_BASE_PADRAO
limiar_adaptado = LIMIAR_BASE
media_movel_alerts = LIMIAR_BASE

if len(historico_numeros) >= FEATURE_LEN:
    janela_pred = historico_numeros[-FEATURE_LEN:]  # as últimas FEATURE_LEN rodadas
    X_pred = pd.DataFrame([extrair_features(janela_pred)]).fillna(0)

    try:
        probs = modelo.predict_proba(X_pred)[0]
        prob = probs[1] if len(probs) > 1 else 0.0
    except Exception:
        prob = 0.0

    st.session_state.historico_probs.append(prob)

    # limiar base dependendo do modo
    LIMIAR_BASE = LIMIAR_BASE_AGRESSIVO if MODO_AGRESSIVO else LIMIAR_BASE_PADRAO

    # ajuste adaptativo baseado na proporção de REDs
    total_feedbacks = st.session_state.greens + st.session_state.reds
    if total_feedbacks == 0:
        ajuste = 0.0
    else:
        prop_red = st.session_state.reds / total_feedbacks
        ajuste = min(0.09, prop_red * 0.12)  # máximo +0.09

    limiar_adaptado = LIMIAR_BASE + ajuste

    # média móvel dos últimos alert_probs (se houver)
    if len(st.session_state.alert_probs) >= MOVING_AVG_WINDOW:
        media_movel_alerts = float(np.mean(st.session_state.alert_probs[-MOVING_AVG_WINDOW:]))
    else:
        media_movel_alerts = LIMIAR_BASE  # fallback

    # condição combinada: prob precisa superar tanto limiar_adaptado quanto a média móvel histórica
    condicao_alerta = prob > max(limiar_adaptado, media_movel_alerts)

    if condicao_alerta and not st.session_state.entrada_atual:
        unidades = [n % 10 for n in janela_pred]
        contagem = Counter(unidades)
        dominantes = [t for t, _ in contagem.most_common(2)]

        entrada_principal = [n for n in range(37) if n % 10 in dominantes]
        entrada_expandida = expandir_com_vizinhos(entrada_principal)

        historico_recente = historico_numeros[-100:]
        contagem_freq = Counter(historico_recente)

        def score_numero(n):
            freq = contagem_freq[n]
            # bonus por terminal quente (memória adaptativa)
            bonus_terminal = st.session_state.terminais_quentes.get(n % 10, 0) * 0.35
            dist = min(abs(ROULETTE_ORDER.index(n) - ROULETTE_ORDER.index(d)) for d in entrada_principal)
            return freq + bonus_terminal + (1.8 if n in entrada_principal else 0) + (0.7 if dist <= 1 else 0)

        entrada_classificada = sorted(entrada_expandida, key=lambda n: score_numero(n), reverse=True)
        entrada_inteligente = sorted(entrada_classificada[:15])

        chave_alerta = f"{dominantes}-{entrada_inteligente}"
        if chave_alerta not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave_alerta)
            numeros_linha = " ".join(str(n) for n in entrada_inteligente)
            enviar_telegram(numeros_linha)
            st.session_state.nova_entrada = True
            st.session_state.tempo_alerta = time.time()
            st.session_state.total_alertas += 1

            # registra info da entrada (para feedback depois)
            st.session_state.entrada_info = {
                "terminais": dominantes,
                "entrada": entrada_inteligente,
                "probabilidade": round(prob, 3),
                "timestamp": time.time()
            }
            # grava prob do alerta para análise e média móvel
            st.session_state.alert_probs.append(prob)

            # log CSV: evento ALERTA
            log_csv([time.time(), "ALERTA", None, None, round(prob,3), round(limiar_adaptado,3), ",".join(map(str, entrada_inteligente))])

        st.session_state.entrada_atual = entrada_inteligente

# === FEEDBACK (avalia se foi GREEN ou RED e atualiza métricas) ===
if st.session_state.entrada_atual:
    entrada = st.session_state.entrada_atual
    numero_atual = st.session_state.historico[-1] if len(st.session_state.historico) > 0 else None
    chave_feedback = f"{numero_atual}-{tuple(sorted(entrada))}"

    if chave_feedback not in st.session_state.feedbacks_processados and numero_atual is not None:
        resultado = "✅ GREEN" if numero_atual in entrada else "❌ RED"
        cor = "green" if resultado == "✅ GREEN" else "red"

        st.markdown(f"<h3 style='color:{cor}'>{resultado} • Número: {numero_atual}</h3>", unsafe_allow_html=True)

        if resultado == "✅ GREEN":
            st.session_state.greens += 1

            # determina se terminal puro ou vizinho
            if st.session_state.entrada_info and "terminais" in st.session_state.entrada_info:
                dominantes = st.session_state.entrada_info["terminais"]
            else:
                unidades = [n % 10 for n in historico_numeros[-FEATURE_LEN:]]
                dominantes = [t for t, _ in Counter(unidades).most_common(2)]

            numeros_terminais = [n for n in range(37) if n % 10 in dominantes]
            vizinhos_terminais = set()
            for n in numeros_terminais:
                vizinhos_terminais.update(get_vizinhos(n))

            if numero_atual in numeros_terminais:
                st.session_state.greens_terminal += 1
                tipo = "terminal"
            elif numero_atual in vizinhos_terminais:
                st.session_state.greens_vizinho += 1
                tipo = "vizinho"
            else:
                tipo = "green_outro"

            # registra confiança do green se existia prob associada
            if st.session_state.entrada_info and "probabilidade" in st.session_state.entrada_info:
                st.session_state.greens_probs.append(st.session_state.entrada_info["probabilidade"])

            # atualiza memoria adaptativa de terminais (por unidade)
            for t in dominantes:
                st.session_state.terminais_quentes[t] = st.session_state.terminais_quentes.get(t, 0) + 1

            # log csv do GREEN
            prob_alert = st.session_state.entrada_info.get("probabilidade") if st.session_state.entrada_info else None
            log_csv([time.time(), "FEEDBACK", numero_atual, tipo, prob_alert, None, ",".join(map(str, entrada))])

        else:
            st.session_state.reds += 1
            tipo = "red"
            prob_alert = st.session_state.entrada_info.get("probabilidade") if st.session_state.entrada_info else None
            log_csv([time.time(), "FEEDBACK", numero_atual, tipo, prob_alert, None, ",".join(map(str, entrada))])

        enviar_telegram(f"{resultado} • Saiu {numero_atual}")
        st.session_state.feedbacks_processados.add(chave_feedback)

        # aprendizado incremental (feedback) com pesos reforçados para terminal
        try:
            janela = list(st.session_state.historico)[-FEATURE_LEN:]
            if len(janela) == FEATURE_LEN:
                X_novo = pd.DataFrame([extrair_features(janela)]).fillna(0)
                # label 1 se caiu dentro da expansão atual, 0 caso contrário
                y_novo = [1 if numero_atual in entrada else 0]

                # define peso de feedback semelhante ao usado no treino
                unidades = [n % 10 for n in janela]
                dominantes = [t for t, _ in Counter(unidades).most_common(2)]
                entrada_principal = [n for n in range(37) if n % 10 in dominantes]
                entrada_expandida = expandir_com_vizinhos(entrada_principal)

                if numero_atual in entrada_principal:
                    weight_novo = np.array([PESO_TERMINAL])
                elif numero_atual in entrada_expandida:
                    weight_novo = np.array([PESO_VIZINHO])
                else:
                    weight_novo = np.array([1.0])

                try:
                    modelo.partial_fit(X_novo, y_novo, classes=[0,1], sample_weight=weight_novo)
                except Exception:
                    modelo.fit(X_novo, y_novo, sample_weight=weight_novo)
                salvar_modelo(modelo)
        except Exception as e:
            st.error(f"Erro no feedback incremental: {e}")

    # reset da entrada para próxima rodada
    st.session_state.entrada_atual = []
    st.session_state.entrada_info = None

# === INTERFACE DE MÉTRICAS ===
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

# distribuição terminal / vizinho
total_greens = st.session_state.greens_terminal + st.session_state.greens_vizinho
if total_greens > 0:
    pct_terminal = (st.session_state.greens_terminal / total_greens) * 100
    pct_vizinho = (st.session_state.greens_vizinho / total_greens) * 100
    st.info(f"💡 Distribuição dos acertos GREEN → Terminal: {pct_terminal:.1f}% | Vizinho: {pct_vizinho:.1f}%")

# gráfico de distribuição Terminal vs Vizinho (matplotlib)
if total_greens > 0:
    fig, ax = plt.subplots(figsize=(4, 2))
    categorias = ["Terminal", "Vizinho"]
    valores = [st.session_state.greens_terminal, st.session_state.greens_vizinho]
    ax.bar(categorias, valores)
    ax.set_title("Distribuição de Acertos GREEN")
    ax.set_ylabel("Contagem")
    st.pyplot(fig)

# confiança média / qualidade
if len(st.session_state.greens_probs) > 0:
    media_conf_greens = sum(st.session_state.greens_probs)/len(st.session_state.greens_probs)
    st.metric("⚡ Confiança média (GREENS)", f"{media_conf_greens:.3f}")
else:
    st.metric("⚡ Confiança média (GREENS)", "—")

# estatísticas extras
st.write(f"Total de alertas disparados: {st.session_state.total_alertas}")
# garante que as variáveis usadas abaixo existam (evita NameError)
try:
    st.write(f"Limiar base: {LIMIAR_BASE:.3f} | Limiar adaptado atual: {limiar_adaptado:.3f} | Média móvel alertas: {media_movel_alerts:.3f}")
except Exception:
    st.write(f"Limiar base: {LIMIAR_BASE:.3f}")

# alerta visual
if st.session_state.nova_entrada and time.time() - st.session_state.tempo_alerta < 5:
    st.markdown("<h3 style='color:orange'>⚙️ Nova entrada IA ativa!</h3>", unsafe_allow_html=True)
else:
    st.session_state.nova_entrada = False

# histórico e entrada atual
st.subheader("📊 Últimos números")
st.write(list(st.session_state.historico)[-20:])

if st.session_state.entrada_info:
    st.subheader("📥 Entrada Atual (ordenada)")
    st.write(st.session_state.entrada_info)

# gráfico de confiança
if st.session_state.historico_probs:
    st.subheader("📈 Confiança da IA (últimas previsões)")
    plt.figure(figsize=(8, 2.5))
    plt.plot(list(st.session_state.historico_probs), marker='o')
    plt.title("Evolução da Probabilidade")
    plt.xlabel("Últimas Rodadas")
    plt.ylabel("Confiança")
    plt.grid(True)
    st.pyplot(plt)
