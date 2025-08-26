import streamlit as st
import joblib
import time
from collections import deque, Counter
from pathlib import Path
from alertas import enviar_previsao, enviar_resultado, get_duzia, get_coluna

# =========================
# CONFIGURAÇÕES
# =========================
HIST_PATH_NUMS = Path("historico_numeros.pkl")

# =========================
# SESSION STATE INIT
# =========================
if "historico_numeros" not in st.session_state:
    st.session_state.historico_numeros = deque(maxlen=120)
    if HIST_PATH_NUMS.exists():
        hist = joblib.load(HIST_PATH_NUMS)
        st.session_state.historico_numeros.extend(hist)

# Modelos
if "modelo_duzia" not in st.session_state:
    try:
        st.session_state.modelo_duzia = joblib.load("modelo_duzia.pkl")
    except:
        st.session_state.modelo_duzia = None

if "modelo_coluna" not in st.session_state:
    try:
        st.session_state.modelo_coluna = joblib.load("modelo_coluna.pkl")
    except:
        st.session_state.modelo_coluna = None

# Estados
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None

if "coluna_prevista" not in st.session_state:
    st.session_state.coluna_prevista = None

if "ultima_previsao_enviada" not in st.session_state:
    st.session_state.ultima_previsao_enviada = None

if "contador_sem_envio" not in st.session_state:
    st.session_state.contador_sem_envio = 0


# =========================
# FEATURES
# =========================
def preparar_features(historico):
    ultimos = list(historico)[-10:]
    return [n for n in ultimos] + [0] * (10 - len(ultimos))


# =========================
# PREVISÃO COMBINADA (IA + Tendência + Alternância + Votação)
# =========================
def prever_final(historico, modelo, funcao_classificacao):
    # Estratégia 1: IA
    try:
        X_entrada = preparar_features(historico)
        prev_ia = modelo.predict([X_entrada])[0]
    except:
        prev_ia = None

    # Estratégia 2: Tendência (últimas 20 jogadas)
    ultimos = list(historico)[-20:]
    contagem = Counter(funcao_classificacao(n) for n in ultimos if n is not None)
    prev_tendencia = contagem.most_common(1)[0][0] if contagem else None

    # Estratégia 3: Alternância
    if len(historico) >= 3:
        c1, c2, c3 = funcao_classificacao(historico[-1]), funcao_classificacao(historico[-2]), funcao_classificacao(historico[-3])
        if c1 != c2 and c2 == c3:
            prev_alternancia = c1
        else:
            prev_alternancia = c1
    else:
        prev_alternancia = None

    # Votação
    previsoes = [prev_ia, prev_tendencia, prev_alternancia]
    previsoes = [p for p in previsoes if p is not None]

    if not previsoes:
        return None

    contagem_final = Counter(previsoes).most_common()
    mais_votado, votos = contagem_final[0]

    # Desempate → prioridade IA > tendência > alternância
    if len(contagem_final) > 1 and contagem_final[0][1] == contagem_final[1][1]:
        if prev_ia in previsoes:
            return prev_ia
        elif prev_tendencia in previsoes:
            return prev_tendencia
        else:
            return prev_alternancia

    return mais_votado


# =========================
# LÓGICA PRINCIPAL
# =========================
st.title("IA de Previsão de Roleta 🎰")

# Input manual de número sorteado
numero = st.number_input("Digite o número sorteado", min_value=0, max_value=36, step=1)

if st.button("Registrar número"):
    st.session_state.historico_numeros.append(numero)
    joblib.dump(list(st.session_state.historico_numeros), HIST_PATH_NUMS)

    # --- Previsão de Dúzia ---
    st.session_state.duzia_prevista = prever_final(
        st.session_state.historico_numeros,
        st.session_state.modelo_duzia,
        get_duzia
    )

    # --- Previsão de Coluna ---
    st.session_state.coluna_prevista = prever_final(
        st.session_state.historico_numeros,
        st.session_state.modelo_coluna,
        get_coluna
    )

    # Decisão: enviar a previsão mais forte (dúzia OU coluna)
    previsao_atual = ("Dúzia", st.session_state.duzia_prevista) if st.session_state.duzia_prevista is not None else None
    if st.session_state.coluna_prevista is not None:
        previsao_atual = ("Coluna", st.session_state.coluna_prevista)

    # Enviar alerta só se for diferente da última ou se passaram 3 rodadas sem envio
    if previsao_atual is not None:
        if (
            previsao_atual != st.session_state.ultima_previsao_enviada
            or st.session_state.contador_sem_envio >= 3
        ):
            enviar_previsao(previsao_atual)
            st.session_state.ultima_previsao_enviada = previsao_atual
            st.session_state.contador_sem_envio = 0
        else:
            st.session_state.contador_sem_envio += 1

    # Conferir resultado e enviar alerta GREEN/RED
    if previsao_atual is not None:
        tipo, valor = previsao_atual
        if tipo == "Dúzia":
            acertou = get_duzia(numero) == valor
        else:
            acertou = get_coluna(numero) == valor

        time.sleep(4)  # intervalo antes do resultado
        enviar_resultado(numero, acertou)

st.write("Histórico de números:", list(st.session_state.historico_numeros))
st.write("Última previsão de dúzia:", st.session_state.duzia_prevista)
st.write("Última previsão de coluna:", st.session_state.coluna_prevista)
