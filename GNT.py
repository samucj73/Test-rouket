import streamlit as st
import requests
import pandas as pd
import joblib
import os
from collections import deque, Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
from streamlit_autorefresh import st_autorefresh
import numpy as np

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_grandes_numeros.pkl"
MAX_HISTORICO = 300
FREQ_ESPERADA = 1 / 37
N_PREDITOS = 10
PREVER_CADA = 1

# === TELEGRAM CONFIG ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

# === INICIALIZA SESSION STATE ===
if 'historico' not in st.session_state:
    st.session_state.historico = deque(maxlen=MAX_HISTORICO)
if 'ultimo_timestamp' not in st.session_state:
    st.session_state.ultimo_timestamp = None
if 'contador_sorteios' not in st.session_state:
    st.session_state.contador_sorteios = 0
if 'ultima_previsao' not in st.session_state:
    st.session_state.ultima_previsao = []
if 'registro_previsoes' not in st.session_state:
    st.session_state.registro_previsoes = []
if 'aguardando_resultado' not in st.session_state:
    st.session_state.aguardando_resultado = False
if 'entrada_ativa' not in st.session_state:
    st.session_state.entrada_ativa = []

# === API ===
def obter_ultimo_numero():
    try:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()
        data = response.json().get("data", {})
        resultado = data.get("result", {}).get("outcome", {})
        numero = resultado.get("number")
        timestamp = data.get("settledAt")
        if numero is None or timestamp is None:
            return None, None
        return int(numero), timestamp
    except Exception as e:
        st.error(f"Erro ao acessar API: {e}")
        return None, None

# === FEATURES ===
def calcular_features(historico):
    total = len(historico)
    contagem = Counter(historico)
    features = []
    for n in range(37):
        freq = contagem[n] / total if total > 0 else 0
        erro_convergencia = FREQ_ESPERADA - freq
        ultima_ocorrencia = (
            total - list(historico)[::-1].index(n)
            if n in historico else MAX_HISTORICO
        )
        par = 1 if n % 2 == 0 else 0
        duzia = 0 if n == 0 else (n - 1) // 12 + 1
        coluna = 0 if n == 0 else ((n - 1) % 3) + 1
        grupo_mod3 = n % 3

        features.append([
            n, freq, erro_convergencia, ultima_ocorrencia, par, duzia, coluna, grupo_mod3
        ])

    return pd.DataFrame(features, columns=[
        "numero", "frequencia", "erro", "ultima_ocorrencia", "par", "duzia", "coluna", "mod3"
    ])

def gerar_dataset_para_treinamento(historico):
    dataset = []
    for i in range(12, len(historico) - 1):
        jan = list(historico)[i - 12:i]
        features = calcular_features(jan)
        proximo = historico[i]
        for _, row in features.iterrows():
            amostra = row.copy()
            amostra["alvo"] = 1 if row["numero"] == proximo else 0
            dataset.append(amostra)
    return pd.DataFrame(dataset)

# === MODELO ===
def carregar_ou_treinar_modelo(historico):
    modelo = None
    if os.path.exists(MODELO_PATH):
        modelo = joblib.load(MODELO_PATH)
    else:
        modelo = RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight='balanced',
            warm_start=True
        )

    try:
        modelo.predict([[0] * 8])
    except NotFittedError:
        if len(historico) >= 13:
            df = gerar_dataset_para_treinamento(historico)
            X = df.drop(columns=["alvo", "numero"])
            y = df["alvo"]
            modelo.fit(X, y)
            joblib.dump(modelo, MODELO_PATH)

    return modelo

# === CAPTURA NÚMERO ATUAL ===
numero, timestamp = obter_ultimo_numero()
if numero is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.historico.append(numero)
    st.session_state.ultimo_timestamp = timestamp
    st.session_state.contador_sorteios += 1

    if st.session_state.aguardando_resultado and st.session_state.entrada_ativa:
        acerto = "GREEN" if numero in st.session_state.entrada_ativa else "RED"
        st.session_state.registro_previsoes.append({
            "previstos": st.session_state.entrada_ativa.copy(),
            "sorteado": numero,
            "resultado": acerto
        })
        st.session_state.aguardando_resultado = False
        st.session_state.entrada_ativa = []

# === PREVISÃO A CADA N SORTEIOS ===
nova_previsao = False
top5 = pd.DataFrame()

if st.session_state.contador_sorteios >= PREVER_CADA and len(st.session_state.historico) >= 13:
    modelo = carregar_ou_treinar_modelo(st.session_state.historico)
    features_atuais = calcular_features(st.session_state.historico)
    X_atual = features_atuais.drop(columns=["numero"])
    probs = modelo.predict_proba(X_atual)[:, 1]
    features_atuais["probabilidade"] = probs
    top5 = features_atuais.sort_values(by="probabilidade", ascending=False).head(N_PREDITOS)

    novos_numeros = top5["numero"].tolist()
    if novos_numeros != st.session_state.ultima_previsao:
        st.session_state.ultima_previsao = novos_numeros
        nova_previsao = True
        mensagem = "🎯 *Nova Previsão (IA - Teoria dos Grandes Números)*\n\n"
        mensagem += "\n".join([f"➡️ Número `{n}`" for n in novos_numeros])
        enviar_telegram(mensagem)

    st.session_state.entrada_ativa = novos_numeros
    st.session_state.aguardando_resultado = True
    st.session_state.contador_sorteios = 0

# === INTERFACE STREAMLIT ===
st.title("🎲 IA Roleta - Teoria dos Grandes Números (com Telegram + Acertos)")
st.write(f"📍 Último número capturado: `{numero}` — Total: `{len(st.session_state.historico)}`")
st.write(f"📡 Nova previsão gerada a cada `{PREVER_CADA}` sorteios")

if not top5.empty:
    st.subheader("🔮 Números previstos:")
    for i, row in top5.iterrows():
        st.markdown(f"**{int(row['numero'])}** — Probabilidade: `{row['probabilidade']:.3f}`")

    st.subheader("📊 Probabilidades (Top 5):")
    chart_data = top5.set_index("numero")[["probabilidade"]].sort_index()
    st.bar_chart(chart_data)

# === DASHBOARD DE ACERTOS ===
st.subheader("📊 Histórico de Resultados (GREEN / RED)")
if st.session_state.registro_previsoes:
    df_resultados = pd.DataFrame(st.session_state.registro_previsoes)
    df_resultados["previstos"] = df_resultados["previstos"].apply(lambda x: ", ".join(map(str, x)))
    df_resultados["ícone"] = df_resultados["resultado"].apply(
        lambda r: "🟢 GREEN" if r == "GREEN" else "🔴 RED"
    )
    st.dataframe(df_resultados[["previstos", "sorteado", "ícone"]].iloc[::-1], use_container_width=True)

    total_green = sum(1 for r in st.session_state.registro_previsoes if r["resultado"] == "GREEN")
    total_red = sum(1 for r in st.session_state.registro_previsoes if r["resultado"] == "RED")

    st.success(f"✅ Total de GREENs: {total_green}")
    st.error(f"❌ Total de REDs: {total_red}")
else:
    st.info("Nenhuma previsão concluída ainda.")

# === IMPORTÂNCIA DAS FEATURES ===
if len(st.session_state.historico) >= 130:
    modelo = carregar_ou_treinar_modelo(st.session_state.historico)
    df = gerar_dataset_para_treinamento(st.session_state.historico)
    X = df.drop(columns=["alvo", "numero"])
    try:
        importancias = modelo.feature_importances_
        st.subheader("🧠 Importância das Features no Modelo")
        importance_df = pd.DataFrame({
            "Feature": X.columns,
            "Importância": importancias
        }).sort_values(by="Importância", ascending=False)
        st.bar_chart(importance_df.set_index("Feature"))
    except Exception as e:
        st.warning(f"Não foi possível exibir a importância das features: {e}")

# === REFRESH ===
st_autorefresh(interval=5000, key="refresh")
