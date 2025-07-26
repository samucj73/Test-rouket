import streamlit as st
import requests
import os
import joblib
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from streamlit_autorefresh import st_autorefresh
import html
import time

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_terminal.pkl"
HISTORICO_PATH = "historico.pkl"
ULTIMO_ALERTA_PATH = "ultimo_alerta.pkl"
CONTADORES_PATH = "contadores.pkl"
MAX_HISTORICO = 600
PROBABILIDADE_MINIMA = 0.45
AUTOREFRESH_INTERVAL = 5000

# === TELEGRAM ===
TELEGRAM_IA_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_IA_CHAT_ID = "-1002796136111"
TELEGRAM_QUENTES_CHAT_ID = "5121457416"

# === ORDEM FÍSICA DA ROLETA EUROPEIA ===
ordem_roleta = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33,
    1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12,
    35, 3, 26
]

def carregar(path, default):
    return joblib.load(path) if os.path.exists(path) else default

def salvar(obj, path):
    joblib.dump(obj, path)

def extrair_terminal(numero):
    return numero % 10

def extrair_duzia(numero):
    if numero == 0:
        return -1
    elif numero <= 12:
        return 1
    elif numero <= 24:
        return 2
    else:
        return 3

def extrair_coluna(numero):
    if numero == 0:
        return -1
    elif numero % 3 == 1:
        return 1
    elif numero % 3 == 2:
        return 2
    else:
        return 3

def extrair_duzia(numero):
    if 1 <= numero <= 12:
        return 1
    elif 13 <= numero <= 24:
        return 2
    elif 25 <= numero <= 36:
        return 3
    return 0  # Para o zero

def extrair_coluna(numero):
    if numero == 0:
        return 0
    elif numero % 3 == 1:
        return 1
    elif numero % 3 == 2:
        return 2
    else:
        return 3

def obter_cor(numero):
    if numero == 0:
        return 0  # Verde
    vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    return 1 if numero in vermelhos else 2  # 1 = vermelho, 2 = preto

def extrair_features(historico):
    features = []
    janela = 30
    for i in range(len(historico) - janela):
        janela_atual = list(historico)[i:i+janela]
        ult_num = janela_atual[-1]
        penult_num = janela_atual[-2] if len(janela_atual) >= 2 else -1

        # Frequência absoluta
        contagem_numeros = Counter(janela_atual)
        freq_numeros = [contagem_numeros.get(n, 0) for n in range(37)]

        # Frequência ponderada (quanto mais recente, mais peso)
        peso = list(range(1, len(janela_atual)+1))  # Ex: [1, 2, ..., 12]
        freq_ponderada = [0]*37
        for idx, n in enumerate(janela_atual):
            freq_ponderada[n] += peso[idx]

        # Frequência dos terminais
        terminais = [n % 10 for n in janela_atual]
        contagem_terminais = Counter(terminais)
        freq_terminais = [contagem_terminais.get(t, 0) for t in range(10)]

        # Frequência de dúzias
        duzias = [extrair_duzia(n) for n in janela_atual]
        duzia_freq = [duzias.count(1), duzias.count(2), duzias.count(3)]

        # Frequência de colunas
        colunas = [extrair_coluna(n) for n in janela_atual]
        coluna_freq = [colunas.count(1), colunas.count(2), colunas.count(3)]

        # Frequência de cor
        cores = [obter_cor(n) for n in janela_atual]
        cor_freq = [cores.count(0), cores.count(1), cores.count(2)]  # Verde, vermelho, preto

        # Frequência últimos 5 e 10
        ult5 = janela_atual[-5:]
        ult10 = janela_atual[-10:]
        freq_ult5 = [ult5.count(n) for n in range(37)]
        freq_ult10 = [ult10.count(n) for n in range(37)]

        # Mudança de cor entre penúltimo e último
        cor_ult = obter_cor(ult_num)
        cor_penult = obter_cor(penult_num) if penult_num != -1 else cor_ult
        mudou_cor = int(cor_ult != cor_penult)

        # Soma e média
        soma = sum(janela_atual)
        media = np.mean(janela_atual)

        # Repetição imediata?
        repetido = int(ult_num == penult_num)

        entrada = (
            [ult_num % 10, extrair_duzia(ult_num), extrair_coluna(ult_num), soma, media, repetido, mudou_cor]
            + freq_numeros
            + freq_ponderada
            + freq_ult5
            + freq_ult10
            + freq_terminais
            + duzia_freq
            + coluna_freq
            + cor_freq
        )

        features.append(entrada)

    return features
