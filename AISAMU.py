import streamlit as st
import requests
import os
import joblib
import random
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"
HISTORICO_FILE = "historico_ia.pkl"
ENTRADAS_FILE = "entradas_ia.pkl"
ACERTOS_FILE = "acertos_ia.pkl"
ROULETTE_ORDER = [26,3,35,12,28,7,29,18,22,9,31,14,20,1,33,16,24,5,10,
                  23,8,30,11,36,13,27,6,34,17,25,2,21,4,19,15,32,0]

# === FUNÇÕES ===
def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

def carregar_objeto(nome, default):
    if os.path.exists(nome):
        return joblib.load(nome)
    return default

def salvar_objeto(nome, valor):
    joblib.dump(valor, nome)

def get_vizinhos(numero, n=2):
    if numero not in ROULETTE_ORDER:
        return []
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-n, n+1)]

def extrair_terminais(numeros):
    return [str(n)[-1] for n in numeros]

def treinar_modelo(historico):
    if len(historico) < 21:
        return None

    X = []
    y = []

    for i in range(len(historico) - 1):
        janela = list(historico)[i:i+20]
        alvo = historico[i + 20]
        contagem = Counter(extrair_terminais(janela))
        vetor = [contagem.get(str(i), 0) for i in range(10)]
        X.append(vetor)
        y.append(str(alvo)[-1])  # terminal como string

    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    return modelo

def prever_terminais(modelo, historico):
    janela = list(historico)[-20:]
    contagem = Counter(extrair_terminais(janela))
    vetor = [contagem.get(str(i), 0) for i in range(10)]
    probs = modelo.predict_proba([vetor])[0]
    terminais_provaveis = [(str(i), p) for i, p in enumerate(probs) if p >= 0.75]
    terminais_ordenados = sorted(terminais_provaveis, key=lambda x: x[1], reverse=True)
    return [t[0] for t in terminais_ordenados[:2]]  # até 2 terminais com probabilidade alta

# === INTERFACE STREAMLIT ===
st.set_page_config(page_title="IA Estratégia Roleta", layout="centered")
st.title("🎯 Estratégia IA - Roleta (Somente IA)")

st_autorefresh(interval=10 * 1000, key="refresh")

# Carregamento
historico = carregar_objeto(HISTORICO_FILE, deque(maxlen=300))
entradas_realizadas = carregar_objeto(ENTRADAS_FILE, [])
acertos = carregar_objeto(ACERTOS_FILE, 0)

if "ultimo_numero" not in st.session_state:
    st.session_state.ultimo_numero = None

# === CAPTURA DO NÚMERO NOVO ===
try:
    response = requests.get(API_URL, timeout=10)
    data = response.json()
    numero = int(data["data"]["result"]["outcome"]["number"])
    timestamp = data["data"]["settledAt"]

    if numero != st.session_state.ultimo_numero:
        historico.append(numero)
        salvar_objeto(HISTORICO_FILE, historico)
        st.session_state.ultimo_numero = numero
        st.success(f"🎲 Último número: **{numero}** às {timestamp}")

        entrada = []
        estrategia = "IA Terminais + Vizinhos"
        terminais_previstos = []

        # === Lógica IA ===
        modelo = treinar_modelo(historico)
        if modelo:
            terminais_previstos = prever_terminais(modelo, historico)

            if terminais_previstos:
                base = []
                for t in terminais_previstos:
                    base.extend([n for n in range(37) if str(n).endswith(t)])

                entrada_final = []
                for n in base:
                    entrada_final.extend(get_vizinhos(n, 2))

                entrada_final = list(set(entrada_final))
                random.shuffle(entrada_final)
                entrada = entrada_final[:10]

                # === Sinal gerado
                msg = f"🤖 Estratégia IA Ativada\n🎯 Terminais previstos: {terminais_previstos}\n🎲 Entrada: {sorted(entrada)}"
                enviar_telegram(msg)
                st.markdown(f"**{estrategia}** — Entrada: `{sorted(entrada)}`")

                green = numero in entrada
                icone = "🟢 GREEN" if green else "🔴 RED"

                entradas_realizadas.append({
                    "estrategia": estrategia,
                    "previstos": sorted(entrada),
                    "sorteado": numero,
                    "icone": icone
                })

                if green:
                    acertos += 1
                    salvar_objeto(ACERTOS_FILE, acertos)
                    st.success("🎉 GREEN confirmado!")
                    st.balloons()

                salvar_objeto(ENTRADAS_FILE, entradas_realizadas)

            else:
                st.info("🧠 IA não encontrou terminais com confiança suficiente.")
        else:
            st.info("⏳ Aguardando histórico mínimo para treinar a IA.")

    else:
        st.warning("⏳ Aguardando novo número...")

except Exception as e:
    st.error(f"Erro ao acessar API: {e}")

# === TABELA DE HISTÓRICO ===
if entradas_realizadas:
    st.markdown("---")
    st.subheader("📊 Histórico de Entradas")
    dados = []
    for i, entrada in enumerate(entradas_realizadas[::-1], 1):
        dados.append({
            "id": len(entradas_realizadas) - i + 1,
            "estratégia": entrada["estrategia"],
            "previstos": ", ".join(map(str, entrada["previstos"])),
            "sorteado": entrada["sorteado"],
            "ícone": entrada["icone"]
        })
    df = pd.DataFrame(dados)
    st.dataframe(df, use_container_width=True)

    st.success(f"✅ Total de GREENs: {acertos}")
    st.error(f"❌ Total de REDs: {len(entradas_realizadas) - acertos}")
