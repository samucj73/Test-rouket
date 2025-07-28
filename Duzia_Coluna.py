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

# Auto atualização da página
st_autorefresh(interval=5000, key="atualizacao")

# === FUNÇÕES AUXILIARES ===

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
        st.error(f"Erro ao enviar mensagem para o Telegram: {e}")

def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0:
            return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    for i in range(40, len(historico)):
        ultimos = historico[i - 40:i]
        entrada = []

        # Frequência de dúzia e coluna nos últimos 10 e 20
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

        # Frequência de cor (R, B, G) nos últimos 20
        cores = {'R': 0, 'B': 0, 'G': 0}
        for n in ultimos[-20:]:
            cores[cor(n)] += 1
        entrada += [cores['R'], cores['B'], cores['G']]

        # Frequência par/ímpar
        par = sum(1 for n in ultimos[-20:] if n != 0 and n % 2 == 0)
        impar = 20 - par
        entrada += [par, impar]

        # Frequência alta (19–36) / baixa (1–18)
        alta = sum(1 for n in ultimos[-20:] if n > 18)
        baixa = sum(1 for n in ultimos[-20:] if 0 < n <= 18)
        entrada += [alta, baixa]

        # Últimos 5 números brutos
        entrada += ultimos[-5:]

        X.append(entrada)

    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 80:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[40:]

    # Targets
    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    # Filtra entradas válidas (exclui 0 do target)
    X_filtrado = []
    y_duzia_filtrado = []
    y_coluna_filtrado = []

    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_filtrado.append(xi)
            y_duzia_filtrado.append(d)
            y_coluna_filtrado.append(c)

    modelo_duzia = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')
    modelo_coluna = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')

    modelo_duzia.fit(X_filtrado, y_duzia_filtrado)
    modelo_coluna.fit(X_filtrado, y_coluna_filtrado)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna


def prever_proxima(modelo, historico, prob_minima=0.60):
    if len(historico) < 80:
        return None, 0.0

    # Extrai apenas a última entrada de features
    X = extrair_features(historico)
    x = X[-1].reshape(1, -1)

    try:
        probas = modelo.predict_proba(x)[0]
        classe = np.argmax(probas) + 1
        probabilidade = probas[classe - 1]

        if probabilidade >= prob_minima:
            return classe, probabilidade
        else:
            return None, probabilidade
    except:
        return None, 0.0



# === CARREGAR HISTÓRICO E MODELOS ===

if Path(HISTORICO_PATH).exists():
    historico = joblib.load(HISTORICO_PATH)
else:
    historico = deque(maxlen=500)

modelo_duzia = joblib.load(MODELO_DUZIA_PATH) if Path(MODELO_DUZIA_PATH).exists() else None
modelo_coluna = joblib.load(MODELO_COLUNA_PATH) if Path(MODELO_COLUNA_PATH).exists() else None

# === OBTÉM ÚLTIMO NÚMERO DA API ===

try:
    response = requests.get(API_URL)
    response.raise_for_status()
    data = response.json()
    numero_atual = int(data["data"]["result"]["outcome"]["number"])
except Exception as e:
    st.error("Erro ao acessar API.")
    st.stop()

# === SE FOR NOVO NÚMERO, ADICIONA AO HISTÓRICO ===

if len(historico) == 0 or numero_atual != historico[-1]:
    historico.append(numero_atual)
    joblib.dump(historico, HISTORICO_PATH)

    # Treina os modelos apenas a cada 10 novas entradas, com mínimo de 80 números
    if len(historico) >= 80 and len(historico) % 10 == 0:
        modelo_duzia, modelo_coluna = treinar_modelos(historico)
        joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
        joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)
    else:
        # Carrega os modelos salvos (se existirem)
        try:
            modelo_duzia = joblib.load(MODELO_DUZIA_PATH)
            modelo_coluna = joblib.load(MODELO_COLUNA_PATH)
        except:
            modelo_duzia = None
            modelo_coluna = None

    # Faz previsões apenas se os modelos estão carregados
    if modelo_duzia is not None and modelo_coluna is not None:
        duzia, prob_duzia = prever_proxima(modelo_duzia, historico)
        coluna, prob_coluna = prever_proxima(modelo_coluna, historico)

        mensagem = f"NA {numero_atual}"
        if duzia is not None:
            mensagem += f" - D {duzia}"
        if coluna is not None:
            mensagem += f" - C {coluna}"

        st.markdown(mensagem, unsafe_allow_html=True)
        enviar_telegram(mensagem)
    else:
        st.warning("Aguardando mais dados ou modelos...")
else:
    st.info("Aguardando novo número...")



# === EXIBIR HISTÓRICO ===
st.markdown("### 🎡 Histórico de Números")
st.write(list(historico))
