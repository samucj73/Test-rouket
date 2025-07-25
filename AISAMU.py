
import streamlit as st
import requests
import os
import joblib
import numpy as np
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/game-events?gameTableId=XxxtremeLigh0001"
TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"
PROB_MIN_TERMINAL = 0.35
PROB_MIN_DUZIA = 0.35
PROB_MIN_COLUNA = 0.35
HISTORICO_PATH = "historico.joblib"
ULTIMO_ALERTA_PATH = "ultimo_alerta.joblib"
st_autorefresh(interval=3000)

# === FUNÇÕES UTILITÁRIAS ===
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def salvar(obj, path):
    joblib.dump(obj, path)

def carregar(path, padrao):
    return joblib.load(path) if os.path.exists(path) else padrao

def obter_cor(numero):
    if numero == 0:
        return 0
    return 1 if numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 2

def extrair_duzia(numero):
    if numero == 0: return 0
    if numero <= 12: return 1
    if numero <= 24: return 2
    return 3

def extrair_coluna(numero):
    if numero == 0: return 0
    if numero % 3 == 1: return 1
    if numero % 3 == 2: return 2
    return 3

# === FEATURE ENGINEERING ===
def extrair_features(historico):
    features = []
    janela = 12
    for i in range(len(historico) - janela):
        janela_atual = list(historico)[i:i+janela]
        terminais = [n % 10 for n in janela_atual]
        term_freq = [terminais.count(t) for t in range(10)]
        duzias = [extrair_duzia(n) for n in janela_atual]
        duzia_freq = [duzias.count(1), duzias.count(2), duzias.count(3)]
        colunas = [extrair_coluna(n) for n in janela_atual]
        coluna_freq = [colunas.count(1), colunas.count(2), colunas.count(3)]
        cores = [obter_cor(n) for n in janela_atual]
        cor_freq = [cores.count(0), cores.count(1), cores.count(2)]
        soma = sum(janela_atual)
        media = np.mean(janela_atual)
        repetido = int(janela_atual[-1] == janela_atual[-2])
        entrada = term_freq + duzia_freq + coluna_freq + cor_freq + [soma, media, repetido]
        features.append(entrada)
    return features

def extrair_features_sem_ult(historico):
    return extrair_features(list(historico)[:-1])

# === MODELO E PREVISÕES ===
def treinar_modelo(historico):
    X_terminal = extrair_features(historico)
    X_limpo = extrair_features_sem_ult(historico)
    alvo = list(historico)[-len(X_terminal):]

    modelo_terminal = RandomForestClassifier(n_estimators=100)
    modelo_duzia = RandomForestClassifier(n_estimators=100)
    modelo_coluna = RandomForestClassifier(n_estimators=100)
    modelo_numeros = RandomForestClassifier(n_estimators=100)

    modelo_terminal.fit(X_terminal, [n % 10 for n in alvo])
    modelo_duzia.fit(X_limpo, [extrair_duzia(n) for n in alvo])
    modelo_coluna.fit(X_limpo, [extrair_coluna(n) for n in alvo])
    modelo_numeros.fit(X_terminal, alvo)

    return modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros

def prever_multiclasse(modelo, historico, prob_min=0.35, usar_limpo=False):
    if len(historico) < 12: return []
    X = extrair_features_sem_ult(historico) if usar_limpo else extrair_features(historico)
    entrada = [X[-1]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted([(i, p) for i, p in enumerate(probas) if p >= prob_min], key=lambda x: -x[1])[:1]

def prever_numeros_quentes(modelo, historico, top_n=3):
    X = extrair_features(historico)
    entrada = [X[-1]]
    probas = modelo.predict_proba(entrada)[0]
    return sorted(enumerate(probas), key=lambda x: -x[1])[:top_n]

# === APP PRINCIPAL ===
historico = carregar(HISTORICO_PATH, deque(maxlen=1000))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {"referencia": None, "entrada": None, "resultado_enviado": None})

try:
    dados = requests.get(API_URL).json()
    ultimos_numeros = [r["value"]["number"] for r in dados if r["type"] == "RouletteWinNumberEvent"]
    for numero in ultimos_numeros:
        if not historico or historico[-1] != numero:
            historico.append(numero)
    salvar(historico, HISTORICO_PATH)
except Exception as e:
    st.error("Erro ao buscar dados da roleta")

if len(historico) >= 15:
    numero_atual = historico[-1]
    if not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual:
        modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros = treinar_modelo(historico)
        terminais_previstos = prever_multiclasse(modelo_terminal, historico, PROB_MIN_TERMINAL)
        duzia_prev = prever_multiclasse(modelo_duzia, historico, PROB_MIN_DUZIA, usar_limpo=True)
        coluna_prev = prever_multiclasse(modelo_coluna, historico, PROB_MIN_COLUNA, usar_limpo=True)
        numeros_quentes = prever_numeros_quentes(modelo_numeros, historico)

        entrada = {
            "terminais": [t[0] for t in terminais_previstos],
            "duzia": duzia_prev[0][0] if duzia_prev else None,
            "coluna": coluna_prev[0][0] if coluna_prev else None,
            "quentes": [n[0] for n in numeros_quentes]
        }

        if entrada != ultimo_alerta["entrada"]:
            mensagem = "🚨 <b>Entrada da IA</b>
"
            if terminais_previstos:
                mensagem += f"🎯 Terminal: <b>{terminais_previstos[0][0]}</b>
"
            if duzia_prev:
                mensagem += f"📊 Dúzia: <b>{duzia_prev[0][0]}</b>
"
            if coluna_prev:
                mensagem += f"📈 Coluna: <b>{coluna_prev[0][0]}</b>
"
            if numeros_quentes:
                quentes_str = ", ".join(str(n[0]) for n in numeros_quentes)
                mensagem += f"🔥 Quentes: <b>{quentes_str}</b>"
            enviar_telegram(mensagem)
            ultimo_alerta.update({"referencia": numero_atual, "entrada": entrada, "resultado_enviado": None})
            salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

    elif numero_atual != ultimo_alerta["resultado_enviado"]:
        entrada = ultimo_alerta["entrada"]
        resultado = "✅ HEAD!" if numero_atual % 10 in entrada["terminais"] else "❌ RED!"
        enviar_telegram(f"🎰 Resultado: <b>{numero_atual}</b>
{resultado}")
        ultimo_alerta["resultado_enviado"] = numero_atual
        salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
else:
    st.info("⏳ Aguardando dados suficientes...")

st.write("Últimos números:", list(historico)[-10:])
