import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter, deque
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from alertas import enviar_previsao, enviar_resultado
from streamlit_autorefresh import st_autorefresh
import random
import time

# =============================
# CONFIGURAÇÕES
# =============================
HISTORICO_PATH = "historico_coluna_duzia.json"
PESOS_PADRAO = {
    "ia": 3,
    "quente": 2,
    "tendencia": 1.5,
    "alternancia": 1,
    "par_impar": 0.8,
    "salto": 0.8,
    "zero": 1.2
}
MAX_RODADAS_SEM_ALERTA = 3
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# FUNÇÕES AUXILIARES
# =============================
def get_duzia(n):
    if n == 0:
        return 0
    elif 1 <= n <= 12:
        return 1
    elif 13 <= n <= 24:
        return 2
    elif 25 <= n <= 36:
        return 3
    return None

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    with open(caminho, "w") as f:
        json.dump(historico, f, indent=2)

def tocar_som_moeda():
    som_base64 = (
        "SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjI2LjEwNAAAAAAAAAAAAAAA//tQxAADBQAB"
        "VAAAAnEAAACcQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAA//sQxAADAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
        "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC"
    )
    st.markdown(
        f"""
        <audio autoplay>
            <source src="data:audio/mp3;base64,{som_base64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

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

# =============================
# ESTRATÉGIAS
# =============================
def estrategia_duzia_quente(historico, janela=130):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    duzias = [get_duzia(n) for n in numeros]
    mais_comum = Counter(duzias).most_common(1)
    return mais_comum[0][0] if mais_comum else None

def estrategia_tendencia(historico):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < 5:
        return None
    ultimos = numeros[-5:]
    dif = np.mean(np.diff(ultimos))
    if dif > 0:
        return min(get_duzia(ultimos[-1]) + 1, 3)
    elif dif < 0:
        return max(get_duzia(ultimos[-1]) - 1, 1)
    else:
        return get_duzia(ultimos[-1])

def estrategia_alternancia(historico, limite=2):
    numeros = [h["number"] for h in historico if h["number"] > 0]
    if len(numeros) < limite + 1:
        return None
    duzias = [get_duzia(n) for n in numeros[-(limite + 1):]]
    if duzias.count(duzias[-1]) >= limite:
        return [d for d in [1,2,3] if d != duzias[-1]][0]
    return duzias[-1]

def estrategia_par_impar(historico, janela=5):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    if len(numeros) < 2:
        return None
    pares = sum(1 for n in numeros if n % 2 == 0)
    impares = len(numeros) - pares
    ultima_duzia = get_duzia(numeros[-1])
    if pares > impares:
        return random.choice([d for d in [1,2,3] if d != ultima_duzia])
    else:
        return ultima_duzia

def estrategia_salto_grande(historico, janela=5):
    numeros = [h["number"] for h in historico[-janela:] if h["number"] > 0]
    if len(numeros) < 2:
        return None
    diffs = [abs(numeros[i]-numeros[i-1]) for i in range(1,len(numeros))]
    if any(d>=12 for d in diffs):
        media = int(np.mean(numeros))
        return get_duzia(media)
    return None

def estrategia_zero_reset(historico, janela=10):
    if not historico:
        return None
    if historico[-1]["number"] == 0:
        ultimos = [h["number"] for h in historico[-janela:] if h["number"] != 0]
        if not ultimos:
            return None
        freq = Counter(get_duzia(n) for n in ultimos)
        return freq.most_common(1)[0][0]
    return None

# =============================
# MODELO IA
# =============================
class ModeloIAHistGB:
    def __init__(self, tipo="duzia", janela=250):
        self.tipo = tipo
        self.janela = janela
        self.modelo = None
        self.encoder = LabelEncoder()
        self.treinado = False
        self.historico_acertos = deque(maxlen=50)

    def construir_features(self, numeros):
        ultimos = numeros[-self.janela:]
        atual = ultimos[-1]
        anteriores = ultimos[:-1]
        def safe_get_duzia(n):
            return -1 if n==0 else get_duzia(n)
        grupo = safe_get_duzia(atual)
        freq_20 = Counter(safe_get_duzia(n) for n in numeros[-20:])
        freq_50 = Counter(safe_get_duzia(n) for n in numeros[-50:]) if len(numeros)>=50 else freq_20
        total_50 = sum(freq_50.values()) or 1
        lag1 = safe_get_duzia(anteriores[-1]) if len(anteriores)>=1 else -1
        lag2 = safe_get_duzia(anteriores[-2]) if len(anteriores)>=2 else -1
        lag3 = safe_get_duzia(anteriores[-3]) if len(anteriores)>=3 else -1
        val1 = anteriores[-1] if len(anteriores)>=1 else 0
        val2 = anteriores[-2] if len(anteriores)>=2 else 0
        val3 = anteriores[-3] if len(anteriores)>=3 else 0
        tendencia=0
        if len(anteriores)>=3:
            diffs=np.diff(anteriores[-3:])
            tendencia=int(np.mean(diffs)>0)-int(np.mean(diffs)<0)
        zeros_50=numeros[-50:].count(0)
        porc_zeros=zeros_50/50
        densidade_20=freq_20.get(grupo,0)
        densidade_50=freq_50.get(grupo,0)
        rel_freq_grupo=densidade_50/total_50
        repete_duzia=int(grupo==safe_get_duzia(anteriores[-1])) if anteriores else 0
        return [
            atual%2, atual%3, int(str(atual)[-1]),
            abs(atual-anteriores[-1]) if anteriores else 0,
            int(atual==anteriores[-1]) if anteriores else 0,
            1 if anteriores and atual>anteriores[-1] else -1 if anteriores and atual<anteriores[-1] else 0,
            sum(1 for x in anteriores[-3:] if grupo==safe_get_duzia(x)),
            Counter(numeros[-30:]).get(atual,0),
            int(atual in [n for n,_ in Counter(numeros[-30:]).most_common(5)]),
            int(np.mean(anteriores)<atual) if anteriores else 0,
            int(atual==0),
            grupo,
            densidade_20,densidade_50,rel_freq_grupo,
            repete_duzia,tendencia,lag1,lag2,lag3,
            val1,val2,val3,porc_zeros
        ]

    def treinar(self, historico):
        numeros=[h["number"] for h in historico if 0<=h["number"]<=36]
        X,y=[],[]
        for i in range(self.janela,len(numeros)-1):
            janela=numeros[i-self.janela:i+1]
            target=get_duzia(numeros[i])
            if target is not None:
                X.append(self.construir_features(janela))
                y.append(target)
        if not X:
            return
        X=np.array(X,dtype=np.float32)
        y=self.encoder.fit_transform(np.array(y))
        self.modelo=HistGradientBoostingClassifier(max_iter=200,max_depth=7,random_state=42)
        self.modelo.fit(X,y)
        self.treinado=True

    def prever(self, historico, threshold=0.4):
        if not self.treinado:
            return None
        numeros=[h["number"] for h in historico if 0<=h["number"]<=36]
        if len(numeros)<self.janela+1:
            return None
        janela=numeros[-(self.janela+1):]
        entrada=np.array([self.construir_features(janela)],dtype=np.float32)
        proba=self.modelo.predict_proba(entrada)[0]
        max_prob=max(proba)
        if max_prob>=threshold:
            return self.encoder.inverse_transform([np.argmax(proba)])[0]
        return None

# =============================
# STREAMLIT APP
# =============================
st.set_page_config(page_title="IA Roleta Dúzia Profissional", layout="centered")
st.title("🎯 IA Roleta XXXtreme — Versão Profissional")

# =============================
# Estado
# =============================
if "historico" not in st.session_state:
    st.session_state.historico = json.load(open(HISTORICO_PATH)) if os.path.exists(HISTORICO_PATH) else []
if "modelo_duzia" not in st.session_state:
    st.session_state.modelo_duzia = ModeloIAHistGB()
if "duzias_acertadas" not in st.session_state:
    st.session_state.duzias_acertadas = 0
if "duzia_prevista" not in st.session_state:
    st.session_state.duzia_prevista = None
if "ultimo_treino" not in st.session_state:
    st.session_state.ultimo_treino = 0
if "rodada_atual" not in st.session_state:
    st.session_state.rodada_atual = None
if "previsao_enviada" not in st.session_state:
    st.session_state.previsao_enviada = False
if "resultado_enviado" not in st.session_state:
    st.session_state.resultado_enviado = False
if "rodadas_sem_alerta" not in st.session_state:
    st.session_state.rodadas_sem_alerta = 0
if "pesos_estrategias" not in st.session_state:
    st.session_state.pesos_estrategias = PESOS_PADRAO.copy()
if "acertos_por_estrategia" not in st.session_state:
    st.session_state.acertos_por_estrategia = {k:0 for k in PESOS_PADRAO.keys()}

# =============================
# Funções de treino e votação ponderada
# =============================
def tentar_treinar():
    historico=st.session_state.historico
    modelo=st.session_state.modelo_duzia
    if len(historico)>=modelo.janela:
        if len(historico)>st.session_state.ultimo_treino:
            modelo.treinar(historico)
            st.session_state.ultimo_treino=len(historico)
            st.info(f"🧠 Modelo treinado com {len(historico)} resultados.")

def votacao_ponderada(previsoes, pesos):
    counter = Counter()
    for key,val in previsoes.items():
        if val is not None:
            counter[val]+=pesos.get(key,1)
    if not counter:
        return None
    return counter.most_common(1)[0][0]

# =============================
# Entrada manual
# =============================
st.subheader("✍️ Inserir Sorteios Manualmente")
entrada=st.text_area("Digite os números (até 100, separados por espaço):", height=100)
if st.button("Adicionar Sorteios"):
    try:
        numeros=[int(n) for n in entrada.split() if n.isdigit() and 0<=int(n)<=36]
        if len(numeros)>100:
            st.warning("Limite de 100 números.")
        else:
            for n in numeros:
                st.session_state.historico.append({"number":n,"timestamp":f"manual_{len(st.session_state.historico)}"})
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.success(f"{len(numeros)} números adicionados.")
            tentar_treinar()
    except Exception as e:
        st.error(f"Erro ao adicionar números: {e}")

# =============================
# Atualização automática
# =============================
st_autorefresh(interval=3000, key="refresh_duzia")
resultado = fetch_latest_result()
ultimo = st.session_state.historico[-1]["timestamp"] if st.session_state.historico else None

previsoes = {}
mais_votado = None

if resultado and resultado["timestamp"] != ultimo:
    numero_atual = resultado["number"]

    if numero_atual != st.session_state.rodada_atual:
        st.session_state.rodada_atual = numero_atual
        st.session_state.previsao_enviada = False
        st.session_state.resultado_enviado = False

        # Conferência do resultado anterior
        if st.session_state.duzia_prevista is not None:
            duzia_real = get_duzia(numero_atual)
            acertou = duzia_real == st.session_state.duzia_prevista

            if acertou:
                st.session_state.duzias_acertadas += 1
                st.success("✅ Acertou a dúzia!")
                st.balloons()
                tocar_som_moeda()

            enviar_resultado(numero_atual, acertou)
            st.session_state.resultado_enviado = True

            previsoes_atual = {
                "ia": st.session_state.duzia_prevista,
                "quente": estrategia_duzia_quente(st.session_state.historico),
                "tendencia": estrategia_tendencia(st.session_state.historico),
                "alternancia": estrategia_alternancia(st.session_state.historico),
                "par_impar": estrategia_par_impar(st.session_state.historico),
                "salto": estrategia_salto_grande(st.session_state.historico),
                "zero": estrategia_zero_reset(st.session_state.historico)
            }

            for estr, pred in previsoes_atual.items():
                if pred == duzia_real:
                    st.session_state.acertos_por_estrategia[estr] += 1

        st.session_state.historico.append(resultado)
        salvar_resultado_em_arquivo(st.session_state.historico)
        tentar_treinar()

        # Atualiza previsão IA
        st.session_state.duzia_prevista = st.session_state.modelo_duzia.prever(st.session_state.historico)

        # Estratégias e votação ponderada
        previsoes = {
            "ia": st.session_state.duzia_prevista,
            "quente": estrategia_duzia_quente(st.session_state.historico),
            "tendencia": estrategia_tendencia(st.session_state.historico),
            "alternancia": estrategia_alternancia(st.session_state.historico),
            "par_impar": estrategia_par_impar(st.session_state.historico),
            "salto": estrategia_salto_grande(st.session_state.historico),
            "zero": estrategia_zero_reset(st.session_state.historico)
        }

        mais_votado = votacao_ponderada(previsoes, st.session_state.pesos_estrategias)
        st.session_state.duzia_prevista = mais_votado

        # Exibe acertos por estratégia
        for k, v in previsoes.items():
            st.write(f"{k}: {v} (acertos: {st.session_state.acertos_por_estrategia.get(k,0)})")

        # Evita múltiplos alertas
        chave_alerta = f"{numero_atual}_{mais_votado}"
        if "ultima_chave_alerta" not in st.session_state:
            st.session_state.ultima_chave_alerta = None

        if (chave_alerta != st.session_state.ultima_chave_alerta) or (st.session_state.rodadas_sem_alerta >= MAX_RODADAS_SEM_ALERTA):
            if mais_votado is not None:
                enviar_previsao(mais_votado)
                st.session_state.ultima_chave_alerta = chave_alerta
               # st.session_state.previs
                               st.session_state.previsao_enviada = True
                st.session_state.rodadas_sem_alerta = 0
        else:
            st.session_state.rodadas_sem_alerta += 1

# =============================
# Interface Streamlit
# =============================
st.subheader("🔁 Últimos 10 Números")
st.write(" ".join(str(h["number"]) for h in st.session_state.historico[-10:]))

with open(HISTORICO_PATH,"r") as f:
    conteudo=f.read()
st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_coluna_duzia.json")

st.subheader("🔮 Previsões por Estratégia")
if previsoes:
    for k,v in previsoes.items():
        st.write(f"{k}: {v} (acertos: {st.session_state.acertos_por_estrategia.get(k,0)})")
else:
    st.info("🔎 Aguardando novos resultados para gerar previsões.")

st.subheader("🎯 Previsão Final (votação ponderada)")
if mais_votado is not None:
    st.success(f"Dúzia {mais_votado}")
else:
    st.info("🔎 Aguardando IA para gerar previsão final.")

st.subheader("📊 Desempenho")
total = len(st.session_state.historico)
if total>0:
    taxa_d = st.session_state.duzias_acertadas/total*100
    st.success(f"✅ Acertos de dúzia: {st.session_state.duzias_acertadas}/{total} ({taxa_d:.2f}%)")
else:
    st.info("🔎 Aguardando mais dados para avaliar desempenho.")
                
