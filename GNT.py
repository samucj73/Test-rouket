import streamlit as st
import requests
import joblib
import os
import time
from collections import Counter
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES DO TELEGRAM ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

# === ARQUIVOS DE HISTÓRICO ===
HISTORICO_PATH = "/mnt/data/historico.pkl"
PREVISOES_PATH = "/mnt/data/previsoes.pkl"

# === API CONFIG ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"

# === CONFIGURAÇÕES ===
INTERVALO_PREVISAO = 6  # a cada 6 novos sorteios
NUMERO_MINIMO_PARA_PREVER = 60
QUANTIDADE_NUMEROS_PARA_APOSTA = 5

# === FUNÇÕES AUXILIARES ===

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        return joblib.load(HISTORICO_PATH)
    return []

def salvar_historico(historico):
    joblib.dump(historico, HISTORICO_PATH)

def carregar_previsoes():
    if os.path.exists(PREVISOES_PATH):
        return joblib.load(PREVISOES_PATH)
    return []

def salvar_previsoes(previsoes):
    joblib.dump(previsoes, PREVISOES_PATH)

def obter_ultimo_numero():
    try:
        response = requests.get(API_URL, timeout=10)
        data = response.json()
        return data["data"]["result"]["outcome"]["number"]
    except Exception as e:
        st.warning(f"Erro na API: {e}")
        return None

def teoria_grandes_numeros(historico):
    """
    Seleciona os números que mais se aproximam da média esperada (idealmente 1/37 de frequência)
    """
    total = len(historico)
    contagem = Counter(historico)
    media_ideal = total / 37

    # Diferença entre frequência atual e média ideal
    diferencas = {num: abs(contagem.get(num, 0) - media_ideal) for num in range(37)}

    # Seleciona os 5 que mais se aproximam da média
    mais_equilibrados = sorted(diferencas, key=lambda x: diferencas[x])[:QUANTIDADE_NUMEROS_PARA_APOSTA]
    return mais_equilibrados

def enviar_telegram_mensagem(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem no Telegram: {e}")

# === APP STREAMLIT ===

st.set_page_config(page_title="Teoria dos Grandes Números - Roleta", layout="centered")
st.title("🎯 Previsão Roleta com Teoria dos Grandes Números")

# Autorefresh a cada 10s
st_autorefresh(interval=10 * 1000, key="refresh")

historico = carregar_historico()
previsoes = carregar_previsoes()
ultimo_numero = obter_ultimo_numero()

if ultimo_numero is not None:
    if not historico or historico[-1] != ultimo_numero:
        historico.append(ultimo_numero)
        salvar_historico(historico)

        if len(historico) >= NUMERO_MINIMO_PARA_PREVER and len(historico) % INTERVALO_PREVISAO == 0:
            nova_previsao = teoria_grandes_numeros(historico)
            previsoes.append({
                "entrada": nova_previsao,
                "verificar_em": len(historico) + 1,
                "status": "AGUARDANDO"
            })
            salvar_previsoes(previsoes)
            enviar_telegram_mensagem(f"🎯 Nova Previsão (Teoria dos Grandes Números): {nova_previsao}")

# === Verificação dos acertos
for previsao in previsoes:
    if previsao["status"] == "AGUARDANDO" and len(historico) >= previsao["verificar_em"]:
        numero_verificacao = historico[previsao["verificar_em"] - 1]
        if numero_verificacao in previsao["entrada"]:
            previsao["status"] = "✅ GREEN"
        else:
            previsao["status"] = "❌ RED"
        salvar_previsoes(previsoes)

# === EXIBIÇÃO ===
st.subheader("📊 Últimos números:")
st.write(historico[-20:][::-1])

st.subheader("📌 Previsões recentes:")
for previsao in previsoes[-5:][::-1]:
    st.write(f"🎯 Entrada: {previsao['entrada']} | Verificação: sorteio #{previsao['verificar_em']} | Resultado: {previsao['status']}")

total_green = sum(1 for p in previsoes if p["status"] == "✅ GREEN")
total_red = sum(1 for p in previsoes if p["status"] == "❌ RED")

st.success(f"✅ Total GREEN: {total_green}")
st.error(f"❌ Total RED: {total_red}")
