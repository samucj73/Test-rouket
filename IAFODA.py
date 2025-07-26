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
    janela = 12
    for i in range(len(historico) - janela):
        janela_atual = list(historico)[i:i+janela]
        ult_num = janela_atual[-1]
        penult_num = janela_atual[-2] if len(janela_atual) >= 2 else -1

        # Frequência dos números
        contagem_numeros = Counter(janela_atual)
        top_freq = [contagem_numeros.get(n, 0) for n in range(37)]  # De 0 a 36

        # Frequência dos terminais
        terminais = [n % 10 for n in janela_atual]
        contagem_terminais = Counter(terminais)
        term_freq = [contagem_terminais.get(t, 0) for t in range(10)]

        # Frequência de dúzias
        duzias = [extrair_duzia(n) for n in janela_atual]
        duzia_freq = [duzias.count(1), duzias.count(2), duzias.count(3)]

        # Frequência de colunas
        colunas = [extrair_coluna(n) for n in janela_atual]
        coluna_freq = [colunas.count(1), colunas.count(2), colunas.count(3)]

        # Frequência de cor
        cores = [obter_cor(n) for n in janela_atual]
        cor_freq = [cores.count(0), cores.count(1), cores.count(2)]  # Zero, Vermelho, Preto

        # Soma e média
        soma = sum(janela_atual)
        media = np.mean(janela_atual)

        # Repetição imediata?
        repetido = int(ult_num == penult_num)

        # Feature final
        entrada = (
            [ult_num % 10, extrair_duzia(ult_num), extrair_coluna(ult_num), soma, media, repetido]
            + term_freq
            + duzia_freq
            + coluna_freq
            + cor_freq
        )

        features.append(entrada)
    return features

def treinar_modelo(historico):
    if len(historico) < 50:
        return None, None, None, None

    X = extrair_features(historico)
    
    # Calcular início para alinhar com X
    inicio = len(historico) - len(X) - 1
    historico_alvo = list(historico)[inicio + 1:]

    y_terminal = [n % 10 for n in historico_alvo]
    y_duzia = [extrair_duzia(n) for n in historico_alvo]
    y_coluna = [extrair_coluna(n) for n in historico_alvo]
    y_numeros = historico_alvo

    # Garantir todos com o mesmo tamanho
    min_len = min(len(X), len(y_terminal), len(y_duzia), len(y_coluna), len(y_numeros))
    X = X[:min_len]
    y_terminal = y_terminal[:min_len]
    y_duzia = y_duzia[:min_len]
    y_coluna = y_coluna[:min_len]
    y_numeros = y_numeros[:min_len]

    modelo_terminal = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_duzia = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo_numeros = RandomForestClassifier(n_estimators=100, random_state=42)

    modelo_terminal.fit(X, y_terminal)
    modelo_duzia.fit(X, y_duzia)
    modelo_coluna.fit(X, y_coluna)
    modelo_numeros.fit(X, y_numeros)

    salvar(modelo_terminal, MODELO_PATH)
    return modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros

def prever_terminais(modelo, historico):
    if len(historico) < 12:
        return []

    # Extração de features usando a mesma função do treinamento
    X = extrair_features(historico)
    ultima_entrada = [X[-1]]  # Deve ser uma lista com o último item (shape: [1, n_features])
    
    probas = modelo.predict_proba(ultima_entrada)[0]
    previsoes = [(i, p) for i, p in enumerate(probas)]
    return sorted(previsoes, key=lambda x: -x[1])[:1]

def prever_multiclasse(modelo, historico, prob_minima=0.90):
    if len(historico) < 50:
        return []

    X = extrair_features(historico)
    entrada = [X[-1]]  # última entrada com mesmo número de features usadas no treino

    probas = modelo.predict_proba(entrada)[0]
    previsoes = [(i, p) for i, p in enumerate(probas) if p >= prob_minima]
    return sorted(previsoes, key=lambda x: -x[1])[:1]  # Retorna só a melhor



def prever_numeros_quentes(modelo, historico, prob_minima=0.05):
    if not modelo or len(historico) < 15:
        return []
    
    X = extrair_features(historico)
    entrada = [X[-2]]  # Usa a última entrada com as mesmas features do treinamento
    
    probas = modelo.predict_proba(entrada)[0]
    previsoes_filtradas = [(i, p) for i, p in enumerate(probas) if p >= prob_minima]
    return sorted(previsoes_filtradas, key=lambda x: -x[1])[:10]


    

    












def gerar_entrada_com_vizinhos(terminais):
    numeros_base = []
    for t in terminais:
        numeros_base.extend([n for n in range(37) if n % 10 == t])
    entrada_completa = set()
    for numero in numeros_base:
        try:
            idx = ordem_roleta.index(numero)
            vizinhos = [ordem_roleta[(idx + i) % len(ordem_roleta)] for i in range(-2, 3)]
            entrada_completa.update(vizinhos)
        except ValueError:
            pass
    return sorted(entrada_completa)

def enviar_telegram(mensagem, chat_id=TELEGRAM_IA_CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_IA_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# === INÍCIO DO APP ===
st.set_page_config(page_title="IA Sinais Roleta", layout="centered")
st.title("🎯 IA Sinais de Roleta: Terminais + Dúzia + Coluna + Quentes")
st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="refresh")

historico = carregar(HISTORICO_PATH, deque(maxlen=MAX_HISTORICO))
ultimo_alerta = carregar(ULTIMO_ALERTA_PATH, {
    "referencia": None,
    "entrada": [],
    "terminais": [],
    "resultado_enviado": None,
    "quentes_enviados": [],
    "quentes_referencia": None
})
contadores = carregar(CONTADORES_PATH, {"green": 0, "red": 0})

contadores = carregar(CONTADORES_PATH, {
    "green": 0, "red": 0,
    "quentes_green": 0, "quentes_red": 0
})
for chave in ["quentes_green", "quentes_red"]:
    if chave not in contadores:
        contadores[chave] = 0

# ✅ CORREÇÃO: API JSON CORRETO
try:
    response = requests.get(API_URL, timeout=3)
    response.raise_for_status()
    data = response.json()
    numero_atual = data["data"]["result"]["outcome"]["number"]
except Exception as e:
    st.error(f"⚠️ Erro ao acessar API: {e}")
    st.stop()

if not historico or numero_atual != historico[-1]:
    historico.append(numero_atual)
    salvar(historico, HISTORICO_PATH)

st.write("🎲 Último número:", numero_atual)

# === ENTRADA DA IA ===
# === ENTRADA DA IA ===
if len(historico) >= 15 and (not ultimo_alerta["entrada"] or ultimo_alerta["resultado_enviado"] == numero_atual):
    modelo_terminal, modelo_duzia, modelo_coluna, modelo_numeros = treinar_modelo(historico)
    terminais_previstos = prever_terminais(modelo_terminal, historico)

    if terminais_previstos and terminais_previstos[0][1] >= PROBABILIDADE_MINIMA:
        terminais_escolhidos = [t[0] for t in terminais_previstos]
        entrada = gerar_entrada_com_vizinhos(terminais_escolhidos)  # Ainda usado para verificar hit/red

        st.success(f"✅ Entrada IA: Terminais {terminais_escolhidos}")
        st.write("🔍 Probabilidades:", terminais_previstos)

        previsao_repetida = (
            set(entrada) == set(ultimo_alerta.get("entrada", [])) and
            set(terminais_escolhidos) == set(ultimo_alerta.get("terminais", []))
        )
        ja_enviou_alerta = ultimo_alerta.get("referencia") == numero_atual
       # if not ja_enviou_alerta and not previsao_repetida and ultimo_alerta.get("resultado_enviado") == numero_atual:
        

        if not ja_enviou_alerta and not previsao_repetida:
        
            # === NOVA MENSAGEM SIMPLES ===
            duzia_prev = prever_multiclasse(modelo_duzia, historico, prob_minima=0.35)
            coluna_prev = prever_multiclasse(modelo_coluna, historico, prob_minima=0.35)

            melhor_duzia = next((d for d, p in duzia_prev if d > 0), None)
            melhor_coluna = next((c for c, p in coluna_prev if c > 0), None)

            mensagem = f"🎯 Jogar\nT {terminais_escolhidos[0]}"
            if melhor_duzia:
                mensagem += f" | D {melhor_duzia}"
            if melhor_coluna:
                mensagem += f" | C {melhor_coluna}"

            enviar_telegram(mensagem, TELEGRAM_IA_CHAT_ID)

            ultimo_alerta.update({
                "referencia": numero_atual,
                "entrada": entrada,
                "terminais": terminais_escolhidos,
                "resultado_enviado": None
            })
            salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
    else:
        st.warning("⚠️ Aguardando nova entrada da IA...")
else:
    st.info("⏳ Aguardando dados suficientes para treinar a IA...")

# === RESULTADO IA ===
# === RESULTADO TERMINAL ===
if (
    "terminais" in ultimo_alerta
    and ultimo_alerta["terminais"]
    and ultimo_alerta.get("resultado_terminal_enviado") != numero_atual
):
    terminal_hit = int(str(numero_atual)[-1]) in ultimo_alerta["terminais"]
    mensagem_terminal = f"🎯 Terminal {'🟢' if terminal_hit else '🔴'}: <b>{numero_atual}</b>"

    ultimo_alerta["resultado_terminal_enviado"] = numero_atual
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
    time.sleep(4)  # espera 4 segundos antes de enviar
    enviar_telegram(mensagem_terminal, TELEGRAM_IA_CHAT_ID)

# === RESULTADO DÚZIA ===
if (
    "duzia" in ultimo_alerta
    and ultimo_alerta["duzia"]
    and ultimo_alerta.get("resultado_duzia_enviado") != numero_atual
):
    duzia_hit = numero_atual in ultimo_alerta["duzia"]
    mensagem_duzia = f"📦 Dúzia {'🟢' if duzia_hit else '🔴'}: <b>{numero_atual}</b>"

    ultimo_alerta["resultado_duzia_enviado"] = numero_atual
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
    time.sleep(4)  # espera mais 4 segundos
    enviar_telegram(mensagem_duzia, TELEGRAM_IA_CHAT_ID)

# === RESULTADO COLUNA ===
if (
    "coluna" in ultimo_alerta
    and ultimo_alerta["coluna"]
    and ultimo_alerta.get("resultado_coluna_enviado") != numero_atual
):
    coluna_hit = numero_atual in ultimo_alerta["coluna"]
    mensagem_coluna = f"🏛️ Coluna {'🟢' if coluna_hit else '🔴'}: <b>{numero_atual}</b>"

    ultimo_alerta["resultado_coluna_enviado"] = numero_atual
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)
    time.sleep(4)  # mais 4 segundos de pausa
    enviar_telegram(mensagem_coluna, TELEGRAM_IA_CHAT_ID)





        
            
            



            


            

# === RESULTADO GREEN / RED ===
if ultimo_alerta["entrada"] and ultimo_alerta.get("resultado_enviado") != numero_atual:
    if numero_atual in ultimo_alerta["entrada"]:
        contadores["green"] += 1
        resultado = "🟢 GREEN!"
    else:
        contadores["red"] += 1
        resultado = "🔴 RED!"

    salvar(contadores, CONTADORES_PATH)
    st.markdown(f"📈 Resultado do número {numero_atual}: **{resultado}**")

    # mensagem_resultado = f"🎯 Resultado do número <b>{numero_atual}</b>: <b>{resultado}</b>"
    # enviar_telegram(mensagem_resultado, TELEGRAM_IA_CHAT_ID)

    ultimo_alerta["resultado_enviado"] = numero_atual
    ultimo_alerta["entrada"] = []
    ultimo_alerta["terminais"] = []
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

# === RESULTADO QUENTES GREEN / 
# # === NÚMEROS QUENTES IA ===
st.write("🔥 Números Quentes previstos pela IA")

# Garante que o modelo está carregado
if 'modelo_numeros' not in locals():
    _, _, _, modelo_numeros = treinar_modelo(historico)

# Faz a previsão com probabilidade mínima
numeros_previstos = prever_numeros_quentes(modelo_numeros, historico, prob_minima=0.05)

# Extrai os quentes
quentes = [num for num, _ in numeros_previstos]

# Mostra os quentes na tela
st.write("🔥 Números Quentes previstos pela IA:", quentes)

# Verifica se já enviou alerta de quentes para esse número
if ultimo_alerta.get("quentes_referencia") != numero_atual:
    mensagem_quentes = "🔥 <b>Quentes IA</b>\n"
    for num, prob in numeros_previstos:
        mensagem_quentes += f"{num} → {prob:.2%}\n"

    enviar_telegram(mensagem_quentes, TELEGRAM_QUENTES_CHAT_ID)

    # Atualiza o estado para não repetir alerta nesse número
    ultimo_alerta["quentes_enviados"] = quentes
    ultimo_alerta["quentes_referencia"] = numero_atual
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

# === RESULTADO QUENTES GREEN / RED (com controle de repetição) ===
if (
    "quentes_enviados" in ultimo_alerta
    and ultimo_alerta["quentes_enviados"]
    and ultimo_alerta.get("resultado_quente_enviado") != numero_atual
):
    if numero_atual in ultimo_alerta["quentes_enviados"]:
        contadores["quentes_green"] += 1
        mensagem_quente = f"🔥 Quente 🟢: <b>{numero_atual}</b>"
    else:
        contadores["quentes_red"] += 1
        mensagem_quente = f"🔥 Quente 🔴: <b>{numero_atual}</b>"

    # Marcar que já enviou alerta do resultado quente para esse número
    ultimo_alerta["resultado_quente_enviado"] = numero_atual
    salvar(ultimo_alerta, ULTIMO_ALERTA_PATH)

    salvar(contadores, CONTADORES_PATH)
    enviar_telegram(mensagem_quente, TELEGRAM_QUENTES_CHAT_ID)

# import time  # certifique-se de ter isso no topo do seu script



# === CONTADORES ===
col1, col2 = st.columns(2)
col1.metric("🟢 GREENs", contadores["green"])
col2.metric("🔴 REDs", contadores["red"])
col3, col4 = st.columns(2)
col3.metric("🔥 Quentes GREENs", contadores["quentes_green"])
col4.metric("🔥 Quentes REDs", contadores["quentes_red"])
