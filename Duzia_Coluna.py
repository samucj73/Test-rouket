# --- SEU CÓDIGO, AGORA COM AS CORREÇÕES APLICADAS ---
# Manteve estrutura original e corrigiu apenas o necessário

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
    "previsao_pendente": None
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
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectFromModel

MODELO_DUZIA_PATH = "modelo_duzia.pkl"
MODELO_COLUNA_PATH = "modelo_coluna.pkl"

def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0:
            return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    for i in range(250, len(historico)):
        ultimos = historico[i - 250:i]
        entrada = []

        for janela in [10, 20]:
            d_freq = [0, 0, 0]
            c_freq = [0, 0, 0]
            for n in ultimos[-janela:]:
                if n == 0:
                    continue
                d = ((n - 1) // 12)
                c = ((n - 1) % 3)
                d_freq[d] += 1
                c_freq[c] += 1
            entrada += d_freq + c_freq

        cores = {'R': 0, 'B': 0, 'G': 0}
        for n in ultimos[-6:]:
            cores[cor(n)] += 1
        entrada += [cores['R'], cores['B'], cores['G']]

        par = sum(1 for n in ultimos[-20:] if n != 0 and n % 2 == 0)
        impar = 20 - par
        entrada += [par, impar]

        alta = sum(1 for n in ultimos[-6:] if n > 18)
        baixa = sum(1 for n in ultimos[-6:] if 0 < n <= 18)
        entrada += [alta, baixa]

        entrada += ultimos[-250:]
        entrada += [ultimos[i] - ultimos[i - 1] for i in range(1, len(ultimos))]

        X.append(entrada)
    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 250:
        return None, None

    historico = list(historico)
    X = extrair_features(historico)
    y = historico[250:]

    y_duzia = [((n - 1) // 12) + 1 for n in y if n != 0]
    y_coluna = [((n - 1) % 3) + 1 for n in y if n != 0]

    # Ajusta X para tamanho válido de y
    X = X[-len(y_duzia):]

    # Treina RF base para dúzia (feature selection)
    rf_fs_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_fs_duzia.fit(X, y_duzia)
    selector_duzia = SelectFromModel(rf_fs_duzia, prefit=True, threshold='median')
    X_duzia_sel = selector_duzia.transform(X)

    # Treina RF base para coluna (feature selection)
    rf_fs_coluna = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_fs_coluna.fit(X, y_coluna)
    selector_coluna = SelectFromModel(rf_fs_coluna, prefit=True, threshold='median')
    X_coluna_sel = selector_coluna.transform(X)

    # Treina modelos finais com features selecionadas
    modelo_duzia = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)

    modelo_duzia.fit(X_duzia_sel, y_duzia)
    modelo_coluna.fit(X_coluna_sel, y_coluna)

    # Salva modelo + seletor juntos
    joblib.dump((modelo_duzia, selector_duzia), MODELO_DUZIA_PATH)
    joblib.dump((modelo_coluna, selector_coluna), MODELO_COLUNA_PATH)

    return (modelo_duzia, selector_duzia), (modelo_coluna, selector_coluna)

def prever_proxima(modelo_e_selector, historico, prob_minima=0.05):
    if len(historico) < 250:
        return None, 0.0

    modelo, selector = modelo_e_selector
    X = extrair_features(historico)
    x = X[-1].reshape(1, -1)
    x_sel = selector.transform(x)

    try:
        probas = modelo.predict_proba(x_sel)[0]
        classe = np.argmax(probas) + 1
        prob = probas[classe - 1]
        return (classe, prob) if prob >= prob_minima else (None, 0.0)
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

    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    if len(historico) >= 80 and len(historico) % 10 == 0:
        modelo_duzia, modelo_coluna = treinar_modelos(historico)

    if modelo_duzia and modelo_coluna:
        taxa_duzia = estado["green_duzia"] / estado["total_duzia"] if estado["total_duzia"] else 0
        taxa_coluna = estado["green_coluna"] / estado["total_coluna"] if estado["total_coluna"] else 0
        prob_min_duzia = 0.55 if taxa_duzia < 0.5 else 0.60
        prob_min_coluna = 0.55 if taxa_coluna < 0.5 else 0.60

        duzia, p_d = prever_proxima(modelo_duzia, historico, prob_min_duzia)
        coluna, p_c = prever_proxima(modelo_coluna, historico, prob_min_coluna)

        entrada = (duzia, coluna)

        if entrada != estado["ultimo_alerta"]:
            mensagem = f"<b>🎯 Número Atual:</b> {numero_atual}"
            if duzia:
                mensagem += f"\n<b>Dúzia:</b> {duzia}"
            if coluna:
                mensagem += f"\n<b>Coluna:</b> {coluna}"

            enviar_telegram(mensagem)
            estado["ultimo_alerta"] = entrada
            estado["previsao_pendente"] = entrada

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
