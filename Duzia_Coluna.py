#Se você observar no meu código direitinho vai perceber que ele já tem a função de recriar vou enviar o código pra você verificar isso

import streamlit as st
import requests
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from collections import deque
import time
from streamlit_autorefresh import st_autorefresh
from pathlib import Path

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002880411750"
HISTORICO_PATH = "historico_duzia_coluna.pkl"
MODELO_DUZIA_PATH = "modelo_duzia.pkl"
MODELO_COLUNA_PATH = "modelo_coluna.pkl"
ESTADO_PATH = "estado.pkl"

st_autorefresh(interval=5000, key="atualizacao")

# === VARIÁVEIS DE CONTROLE ===
estado = {
    "ultimo_alerta": None,
    "green_duzia": 0,
    "green_coluna": 0,
    "total_duzia": 0,
    "total_coluna": 0,
    "previsao_pendente": None,
    "contador_retreino": 0
}
if Path(ESTADO_PATH).exists():
    estado = joblib.load(ESTADO_PATH)

# === FUNÇÕES ===

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem: {e}")

import numpy as np

def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0:
            return 'G'  # green
        return 'R' if n in [
            1,3,5,7,9,12,14,16,18,
            19,21,23,25,27,30,32,34,36
        ] else 'B'

    janela = 24  # << NOVA JANELA DE CONTEXTO

    for i in range(janela, len(historico)):
        janela_anterior = historico[i-janela:i]

        cores = [cor(n) for n in janela_anterior]
        vermelhos = cores.count('R')
        pretos = cores.count('B')
        verdes = cores.count('G')

        pares = sum(1 for n in janela_anterior if n != 0 and n % 2 == 0)
        impares = sum(1 for n in janela_anterior if n != 0 and n % 2 != 0)

        baixos = sum(1 for n in janela_anterior if 1 <= n <= 18)
        altos = sum(1 for n in janela_anterior if 19 <= n <= 36)

        dezenas = [((n - 1) // 12) + 1 if n != 0 else 0 for n in janela_anterior]
        colunas = [((n - 1) % 3) + 1 if n != 0 else 0 for n in janela_anterior]

        d1 = dezenas.count(1)
        d2 = dezenas.count(2)
        d3 = dezenas.count(3)

        c1 = colunas.count(1)
        c2 = colunas.count(2)
        c3 = colunas.count(3)

        terminais = [n % 10 for n in janela_anterior if n != 0]
        terminais_freq = [terminais.count(t) for t in range(10)]

        features = [
            vermelhos, pretos, verdes,
            pares, impares,
            baixos, altos,
            d1, d2, d3,
            c1, c2, c3,
            *terminais_freq
        ]

        X.append(features)

    return X







def treinar_modelos(historico):
    if len(historico) < 25:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[24:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    X_filtrado = []
    y_duzia_f = []
    y_coluna_f = []
    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_filtrado.append(xi)
            y_duzia_f.append(d)
            y_coluna_f.append(c)

    modelo_duzia = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)

    modelo_duzia.fit(X_filtrado, y_duzia_f)
    modelo_coluna.fit(X_filtrado, y_coluna_f)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico, prob_minima=0.05):
    if len(historico) < 25:
        return None, 0.0

    X = extrair_features(historico)
    x = X[-1].reshape(1, -1)

    try:
        probas = modelo.predict_proba(x)[0]
        classe = np.argmax(probas) + 1
        prob = probas[classe - 1]
        if prob >= prob_minima:
            return classe, prob
        return None, prob
    except Exception as e:
        print(f"Erro previsão: {e}")
        return None, 0.0

# === HISTÓRICO E MODELOS ===
historico = joblib.load(HISTORICO_PATH) if Path(HISTORICO_PATH).exists() else deque(maxlen=500)
modelo_duzia = joblib.load(MODELO_DUZIA_PATH) if Path(MODELO_DUZIA_PATH).exists() else None
modelo_coluna = joblib.load(MODELO_COLUNA_PATH) if Path(MODELO_COLUNA_PATH).exists() else None

# === OBTÉM NOVO NÚMERO ===
try:
    resp = requests.get(API_URL)
    numero_atual = int(resp.json()["data"]["result"]["outcome"]["number"])
except:
    st.error("Erro ao acessar API.")
    st.stop()

# === NOVO NÚMERO DETECTADO ===
if len(historico) == 0 or numero_atual != historico[-1]:
    # Verificar acerto da previsão anterior
    previsao_anterior = estado.get("previsao_pendente")
    if previsao_anterior:
        prev_duzia, prev_coluna = previsao_anterior

        if prev_duzia:
            estado["total_duzia"] += 1
            if ((numero_atual - 1) // 12) + 1 == prev_duzia:
                estado["green_duzia"] += 1

        if prev_coluna:
            estado["total_coluna"] += 1
            if ((numero_atual - 1) % 3) + 1 == prev_coluna:
                estado["green_coluna"] += 1

        estado["previsao_pendente"] = None

    # Atualiza histórico
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    # Re-treina a cada 10
    if len(historico) >= 30 and len(historico) % 10 == 0:
        modelo_duzia, modelo_coluna = treinar_modelos(historico)

    # Faz previsão
    if modelo_duzia and modelo_coluna:
        taxa_duzia = estado["green_duzia"] / estado["total_duzia"] if estado["total_duzia"] else 0
        taxa_coluna = estado["green_coluna"] / estado["total_coluna"] if estado["total_coluna"] else 0
        prob_min_duzia = 0.05 if taxa_duzia < 0.5 else 0.10
        prob_min_coluna = 0.05 if taxa_coluna < 0.5 else 0.10

        duzia, p_d = prever_proxima(modelo_duzia, historico, prob_min_duzia)
        coluna, p_c = prever_proxima(modelo_coluna, historico, prob_min_coluna)

        mensagem = f"🎯 <b>NA:</b> {numero_atual}"
        if duzia:
            mensagem += f" | D: <b>{duzia}</b>"
            
        if coluna:
            mensagem += f" | C: <b>{coluna}</b>"

        
        

        


    

        

        entrada = (duzia, coluna)
        if entrada != estado["ultimo_alerta"]:
            enviar_telegram(mensagem)
            estado["ultimo_alerta"] = entrada
            estado["previsao_pendente"] = entrada  # ← será verificada na próxima rodada

        joblib.dump(estado, ESTADO_PATH)
        st.success(mensagem)
    else:
        st.warning("Aguardando modelo...")
else:
    st.info("Aguardando novo número...")

# === EXIBIÇÃO ===
st.metric("🟢 GREEN Dúzia", estado["green_duzia"])
st.metric("🟢 GREEN Coluna", estado["green_coluna"])
st.metric("🎲 Total Dúzia", estado["total_duzia"])
st.metric("🎲 Total Coluna", estado["total_coluna"])
st.markdown("### Últimos números")
st.write(list(historico))
