import streamlit as st
import requests
import joblib
from collections import Counter, deque
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import SGDClassifier
import numpy as np
import time
import csv
import os

# ==========================
# ======== v3.5 ===========
# ==========================

# === CONFIGURAÇÕES FIXAS ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
#CHAT_ID = "-1002979544095"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
MODELO_PATH = "modelo_incremental_v35.pkl"
HISTORICO_PATH = "historico_v35.pkl"
CSV_LOG_PATH = "historico_feedback_v35.csv"

# === CONFIGURAÇÕES ADMIN (barra lateral) ===
st.set_page_config(layout="wide", page_title="IA Elite Master - Roleta v3.5")
st.sidebar.title("⚙️ Painel Administrativo - Elite Master")

MODO_AGRESSIVO = st.sidebar.toggle("Modo Agressivo (mais alertas)", value=False)
FEATURE_LEN = st.sidebar.slider("Tamanho da janela de features", 10, 25, 14)
HIST_MAXLEN = st.sidebar.slider("Tamanho máximo do histórico", 500, 3000, 1500)
LIMIAR_BASE_PADRAO = st.sidebar.number_input("Limiar Base (Padrão)", 0.4, 0.9, 0.60, step=0.01)
LIMIAR_BASE_AGRESSIVO = st.sidebar.number_input("Limiar Base (Agressivo)", 0.4, 0.9, 0.55, step=0.01)
PESO_TERMINAL = st.sidebar.slider("Peso Terminal", 1.0, 3.0, 1.2, step=0.1)
PESO_VIZINHO = st.sidebar.slider("Peso Vizinho", 0.2, 2.0, 0.5, step=0.1)
MOVING_AVG_WINDOW = st.sidebar.slider("Janela da média móvel (alertas)", 5, 25, 10)

# NOVA CONFIGURAÇÃO: Quantidade de números na previsão
QTD_NUMEROS_PREVISAO = st.sidebar.selectbox("Quantidade de números na previsão", [6, 8, 12], index=0)

# Configuração da nova estratégia
ATIVAR_ESTRATEGIA_7_RODADAS = st.sidebar.toggle("Ativar Estratégia 7 Rodadas", value=True)

st.sidebar.markdown("---")
st.sidebar.info(f"📢 Modo atual: {'Agressivo' if MODO_AGRESSIVO else 'Padrão'}")
st.sidebar.info(f"🔢 Números na previsão: {QTD_NUMEROS_PREVISAO}")
st.sidebar.info(f"🎯 Estratégia 7 Rodadas: {'Ativa' if ATIVAR_ESTRATEGIA_7_RODADAS else 'Inativa'}")

# ==========================
# === INICIALIZAÇÃO UI ====
# ==========================
st.title("🎯 Estratégia IA Inteligente - v3.5 (Elite Master)")

# Histórico
if os.path.exists(HISTORICO_PATH):
    historico_salvo = joblib.load(HISTORICO_PATH)
    st.session_state.historico = deque(historico_salvo, maxlen=HIST_MAXLEN)
else:
    st.session_state.historico = deque(maxlen=HIST_MAXLEN)

# Estado padrão
defaults = {
    "ultimo_timestamp": None,
    "entrada_atual": None,
    "alertas_enviados": set(),
    "feedbacks_processados": set(),
    "greens": 0,
    "reds": 0,
    "greens_terminal": 0,
    "greens_vizinho": 0,
    "historico_probs": deque(maxlen=500),
    "alert_probs": [],
    "nova_entrada": False,
    "tempo_alerta": 0,
    "total_alertas": 0,
    "terminais_quentes": {},
    "probabilidades_numeros": {},
    "estrategia_7_entradas": [],  # NOVO: armazena entradas da estratégia das 7 rodadas
    "historico_estrategia_7": deque(maxlen=50),  # NOVO: histórico da estratégia
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "greens_probs" not in st.session_state:
    st.session_state.greens_probs = []

# Auto-refresh
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=2500, key="refresh")

# Ordem da roleta
ROULETTE_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

# ==========================
# === FUNÇÕES UTILITÁRIAS ===
# ==========================
def get_vizinhos(numero):
    idx = ROULETTE_ORDER.index(numero)
    return [ROULETTE_ORDER[(idx + i) % len(ROULETTE_ORDER)] for i in range(-2, 3)]

def expandir_com_vizinhos(nums):
    entrada = set()
    for n in nums:
        entrada.update(get_vizinhos(n))
    return sorted(entrada)

def extrair_features(janela):
    f = {f"num_{i}": int(n) for i, n in enumerate(janela)}
    f["media"] = float(sum(janela) / len(janela))
    f["ultimo"] = int(janela[-1])
    moda = Counter(janela).most_common(1)
    f["moda"] = int(moda[0][0]) if moda else int(janela[-1])
    f["qtd_pares"] = int(sum(1 for n in janela if n % 2 == 0))
    f["qtd_baixos"] = int(sum(1 for n in janela if n <= 18))
    unidades = [n % 10 for n in janela]
    for d in range(10):
        f[f"unid_{d}"] = int(unidades.count(d))
    return f

def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
    except Exception:
        pass

def carregar_modelo():
    if os.path.exists(MODELO_PATH):
        return joblib.load(MODELO_PATH)
    return SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

def salvar_modelo(modelo):
    joblib.dump(modelo, MODELO_PATH)

def log_csv(row):
    header = ["timestamp", "evento", "numero", "tipo", "prob_alerta", "limiar", "entrada"]
    write_header = not os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if write_header: w.writerow(header)
        w.writerow(row)

# FUNÇÃO CORRIGIDA: Estratégia das 7 Rodadas (ANÁLISE REVERSA)
def estrategia_7_rodadas(historico):
    """
    Estratégia corrigida (ANÁLISE REVERSA):
    - Do último número sorteado, volta 7 posições para trás
    - Pega os terminais da 6ª e 7ª rodadas anteriores (mais antigas)
    - Compara com os 5 terminais das rodadas mais recentes
    - Usa os terminais que apareceram MENOS ou NÃO apareceram nos recentes
    """
    if len(historico) < 7:
        return []
    
    entradas_estrategia = []
    
    # Pega os últimos 7 números (do mais recente para o mais antigo)
    ultimos_7 = list(historico)[-7:]
    
    # Estrutura do grupo (do mais recente para o mais antigo):
    # [0] = Mais recente (último sorteado)
    # [1] = 2º mais recente
    # [2] = 3º mais recente
    # [3] = 4º mais recente
    # [4] = 5º mais recente
    # [5] = 6º mais recente (6ª anterior)
    # [6] = 7º mais recente (7ª anterior)
    
    # 5 rodadas mais RECENTES (posições 0 a 4)
    cinco_recentes = ultimos_7[0:5]
    terminais_recentes = [num % 10 for num in cinco_recentes]
    
    # 6ª e 7ª rodadas ANTERIORES (mais antigas - posições 5 e 6)
    sexta_anterior = ultimos_7[5]  # 6ª anterior
    setima_anterior = ultimos_7[6]  # 7ª anterior
    
    terminais_anteriores = [sexta_anterior % 10, setima_anterior % 10]
    
    # Contar frequência dos terminais nos RECENTES
    freq_recentes = Counter(terminais_recentes)
    
    # Analisar cada terminal anterior
    for terminal in terminais_anteriores:
        freq_terminal = freq_recentes.get(terminal, 0)
        
        # Se o terminal não apareceu ou apareceu apenas 1 vez nos 5 recentes
        if freq_terminal <= 1:
            # Todos os números com esse terminal são a entrada
            entrada = [num for num in range(37) if num % 10 == terminal]
            entradas_estrategia.extend(entrada)
    
    return list(set(entradas_estrategia))  # Remove duplicatas

# ==========================
# === CAPTURA DA API ===
# ==========================
try:
    r = requests.get(API_URL, timeout=5)
    if r.status_code == 200:
        d = r.json()
        numero = int(d["data"]["result"]["outcome"]["number"])
        ts = d["data"]["settledAt"]
        if ts != st.session_state.ultimo_timestamp:
            st.session_state.historico.append(numero)
            st.session_state.ultimo_timestamp = ts
            joblib.dump(list(st.session_state.historico), HISTORICO_PATH)
            st.success(f"🎯 Novo número: {numero}")
            
            # NOVO: Executar estratégia das 7 rodadas a cada novo número
            if ATIVAR_ESTRATEGIA_7_RODADAS and len(st.session_state.historico) >= 7:
                entrada_estrategia = estrategia_7_rodadas(list(st.session_state.historico))
                if entrada_estrategia:
                    st.session_state.estrategia_7_entradas = entrada_estrategia
                    # Registrar no histórico da estratégia
                    st.session_state.historico_estrategia_7.append({
                        "timestamp": time.time(),
                        "entrada": entrada_estrategia,
                        "terminais_ativos": list(set([n % 10 for n in entrada_estrategia])),
                        "numero_analisado": numero,
                        "analise": f"6ª anterior: {st.session_state.historico[-6] % 10}, 7ª anterior: {st.session_state.historico[-7] % 10}"
                    })
except Exception:
    pass

# ==========================
# === TREINAMENTO INCREMENTAL ===
# ==========================
modelo = carregar_modelo()
hist = list(st.session_state.historico)

if len(hist) >= FEATURE_LEN + 1:
    X, y, w = [], [], []
    for i in range(len(hist) - FEATURE_LEN):
        janela = hist[i:i + FEATURE_LEN]
        target = hist[i + FEATURE_LEN]
        u = [n % 10 for n in janela]
        dom = [t for t, _ in Counter(u).most_common(2)]
        entrada_p = [n for n in range(37) if n % 10 in dom]
        entrada_v = expandir_com_vizinhos(entrada_p)
        X.append(extrair_features(janela))
        y_val = 1 if target in entrada_v else 0
        peso = PESO_TERMINAL if target in entrada_p else PESO_VIZINHO if target in entrada_v else 1.0
        y.append(y_val); w.append(peso)
    df = pd.DataFrame(X).fillna(0)
    y_arr, w_arr = np.array(y), np.array(w)
    try:
        modelo.partial_fit(df, y_arr, classes=[0, 1], sample_weight=w_arr)
    except Exception:
        modelo.fit(df, y_arr, sample_weight=w_arr)
    salvar_modelo(modelo)

# ==========================
# === PREVISÃO + ALERTA ===
# ==========================
LIMIAR_BASE = LIMIAR_BASE_AGRESSIVO if MODO_AGRESSIVO else LIMIAR_BASE_PADRAO
limiar_adaptado, media_movel_alerts = LIMIAR_BASE, LIMIAR_BASE

entrada_final_combinada = []

if len(hist) >= FEATURE_LEN:
    Xp = pd.DataFrame([extrair_features(hist[-FEATURE_LEN:])]).fillna(0)
    try:
        prob = modelo.predict_proba(Xp)[0][1]
    except Exception:
        prob = 0.0
    st.session_state.historico_probs.append(prob)

    # Ajuste dinâmico de limiar
    total_fb = st.session_state.greens + st.session_state.reds
    prop_red = (st.session_state.reds / total_fb) if total_fb > 0 else 0
    ajuste = min(0.09, prop_red * 0.12)
    limiar_adaptado = LIMIAR_BASE + ajuste
    if len(st.session_state.alert_probs) >= MOVING_AVG_WINDOW:
        media_movel_alerts = float(np.mean(st.session_state.alert_probs[-MOVING_AVG_WINDOW:]))

    cond_alerta = prob > max(limiar_adaptado, media_movel_alerts)

    if cond_alerta and not st.session_state.entrada_atual:
        u = [n % 10 for n in hist[-FEATURE_LEN:]]
        dom = [t for t, _ in Counter(u).most_common(2)]
        entrada_p = [n for n in range(37) if n % 10 in dom]
        entrada_v = expandir_com_vizinhos(entrada_p)

        # LÓGICA ORIGINAL: Calcular probabilidades individuais para cada número
        probabilidades_numeros = {}
        hist_r = hist[-100:]
        freq = Counter(hist_r)
        
        for numero_candidato in entrada_v:
            score = 0
            
            # Frequência recente
            score += freq.get(numero_candidato, 0) * 0.8
            
            # Bônus para terminais quentes
            terminal = numero_candidato % 10
            score += st.session_state.terminais_quentes.get(terminal, 0) * 0.35
            
            # Bônus por proximidade com números terminais
            if numero_candidato in entrada_p:
                score += 1.8  # Bônus máximo para números terminais
            else:
                # Calcular distância para o terminal mais próximo
                dist_minima = min(abs(ROULETTE_ORDER.index(numero_candidato) - 
                                    ROULETTE_ORDER.index(terminal_num)) 
                                for terminal_num in entrada_p)
                if dist_minima <= 1:
                    score += 0.7  # Bônus para vizinhos próximos
                elif dist_minima <= 2:
                    score += 0.3  # Bônus menor para vizinhos mais distantes
            
            probabilidades_numeros[numero_candidato] = score

        # Ordenar números por probabilidade (maior para menor)
        numeros_ordenados = sorted(probabilidades_numeros.items(), 
                                 key=lambda x: x[1], reverse=True)
        
        # Selecionar apenas a quantidade configurada de números
        entrada_original = [num for num, prob in numeros_ordenados[:QTD_NUMEROS_PREVISAO]]
        
        # NOVO: Combinar com estratégia das 7 rodadas se ativa
        if ATIVAR_ESTRATEGIA_7_RODADAS and st.session_state.estrategia_7_entradas:
            # Combinar entradas (união das duas estratégias)
            entrada_combinada = list(set(entrada_original + st.session_state.estrategia_7_entradas))
            
            # Recalcular probabilidades para os números combinados
            probabilidades_combinadas = {}
            for num in entrada_combinada:
                if num in probabilidades_numeros:
                    probabilidades_combinadas[num] = probabilidades_numeros[num]
                else:
                    # Para números da estratégia 7, dar uma probabilidade base
                    terminal = num % 10
                    freq_num = freq.get(num, 0)
                    bonus_terminal = st.session_state.terminais_quentes.get(terminal, 0) * 0.35
                    probabilidades_combinadas[num] = freq_num * 0.8 + bonus_terminal + 1.0  # Bonus por ser da estratégia 7
            
            # Ordenar a entrada combinada
            entrada_combinada_ordenada = sorted(probabilidades_combinadas.items(), 
                                              key=lambda x: x[1], reverse=True)
            entrada_final_combinada = [num for num, prob in entrada_combinada_ordenada[:QTD_NUMEROS_PREVISAO]]
            st.session_state.probabilidades_numeros = dict(entrada_combinada_ordenada[:QTD_NUMEROS_PREVISAO])
        else:
            entrada_final_combinada = entrada_original
            st.session_state.probabilidades_numeros = dict(numeros_ordenados[:QTD_NUMEROS_PREVISAO])

        chave = f"{dom}-{entrada_final_combinada}"
        if chave not in st.session_state.alertas_enviados:
            st.session_state.alertas_enviados.add(chave)
            
            # Enviar apenas os números
            mensagem = " ".join(str(num) for num in entrada_final_combinada)
            enviar_telegram(mensagem)
            
            st.session_state.nova_entrada = True
            st.session_state.tempo_alerta = time.time()
            st.session_state.total_alertas += 1

            # ⚡ guarda índice do próximo número para conferência
            st.session_state.entrada_atual = {
                "entrada": entrada_final_combinada,
                "terminais": dom,
                "probabilidade": round(prob,3),
                "probabilidades_individual": st.session_state.probabilidades_numeros,
                "estrategia_7_ativa": ATIVAR_ESTRATEGIA_7_RODADAS and bool(st.session_state.estrategia_7_entradas),
                "index_feedback": len(hist)
            }
            st.session_state.alert_probs.append(prob)
            log_csv([time.time(), "ALERTA", None, None, round(prob,3), round(limiar_adaptado,3), ",".join(map(str,entrada_final_combinada))])

# ==========================
# === FEEDBACK (confere apenas próximo número) ===
# ==========================
if st.session_state.entrada_atual:
    ent = st.session_state.entrada_atual["entrada"]
    idx_fb = st.session_state.entrada_atual["index_feedback"]

    if len(st.session_state.historico) > idx_fb:
        numero_sorteado = st.session_state.historico[idx_fb]

        green = numero_sorteado in ent
        st.session_state.feedbacks_processados.add(f"{numero_sorteado}-{tuple(sorted(ent))}")

        if green:
            st.session_state.greens += 1
            dom = st.session_state.entrada_atual.get("terminais", [])
            term = [n for n in range(37) if n % 10 in dom]
            viz = set(v for n in term for v in get_vizinhos(n))
            if numero_sorteado in term:
                st.session_state.greens_terminal += 1
            elif numero_sorteado in viz:
                st.session_state.greens_vizinho += 1
            st.session_state.greens_probs.append(st.session_state.entrada_atual["probabilidade"])
            for t in dom: st.session_state.terminais_quentes[t] = st.session_state.terminais_quentes.get(t,0)+1
        else:
            st.session_state.reds += 1

        enviar_telegram(f"{'✅ GREEN' if green else '❌ RED'} • Saiu {numero_sorteado}")
        st.session_state.entrada_atual = None

# ==========================
# === MÉTRICAS & GRÁFICOS ===
# ==========================
col1,col2,col3,col4,col5 = st.columns(5)
col1.metric("✅ GREENS", st.session_state.greens)
col2.metric("❌ REDS", st.session_state.reds)
tot = st.session_state.greens + st.session_state.reds
col3.metric("🎯 Taxa de Acerto", f"{(st.session_state.greens/tot*100 if tot>0 else 0):.1f}%")
col4.metric("🎯 GREEN Terminal", st.session_state.greens_terminal)
col5.metric("🎯 GREEN Vizinho", st.session_state.greens_vizinho)

# NOVA MÉTRICA: Estratégia 7 Rodadas
if ATIVAR_ESTRATEGIA_7_RODADAS:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Estratégia 7 Rodadas")
    st.sidebar.write(f"Entradas ativas: {len(st.session_state.estrategia_7_entradas)}")
    if st.session_state.estrategia_7_entradas:
        terminais_ativos = list(set([n % 10 for n in st.session_state.estrategia_7_entradas]))
        st.sidebar.write(f"Terminais: {terminais_ativos}")

# Distribuição Terminal / Vizinho
total_g = st.session_state.greens_terminal + st.session_state.greens_vizinho
if total_g>0:
    pt = st.session_state.greens_terminal/total_g*100
    pv = st.session_state.greens_vizinho/total_g*100
    st.info(f"💡 Distribuição GREEN → Terminal: {pt:.1f}% | Vizinho: {pv:.1f}%")
    fig, ax = plt.subplots(figsize=(4,2))
    ax.bar(["Terminal","Vizinho"],[st.session_state.greens_terminal, st.session_state.greens_vizinho])
    ax.set_title("Distribuição de Acertos GREEN")
    st.pyplot(fig)

# Confiança média
if st.session_state.greens_probs:
    mc = np.mean(st.session_state.greens_probs)
    st.metric("⚡ Confiança média (GREENS)", f"{mc:.3f}")

st.write(f"Total de alertas: {st.session_state.total_alertas}")
st.write(f"Limiar base: {LIMIAR_BASE:.3f} | Limiar adaptado: {limiar_adaptado:.3f} | Média móvel alertas: {np.mean(st.session_state.alert_probs[-MOVING_AVG_WINDOW:]) if st.session_state.alert_probs else 0:.3f}")

# Nova entrada visual
if st.session_state.nova_entrada and time.time()-st.session_state.tempo_alerta<5:
    st.markdown("<h3 style='color:orange'>⚙️ Nova entrada IA ativa!</h3>", unsafe_allow_html=True)
    if st.session_state.entrada_atual and st.session_state.entrada_atual.get("estrategia_7_ativa"):
        st.markdown("<p style='color:green'>🎯 Estratégia 7 Rodadas Ativa</p>", unsafe_allow_html=True)

# Últimos números com ANÁLISE DA ESTRATÉGIA
st.subheader("📊 Últimos números (Análise Estratégia 7 Rodadas)")
ultimos_numeros = list(st.session_state.historico)[-14:]
if len(ultimos_numeros) >= 7:
    st.write("Últimos 7 números (do mais recente para o mais antigo):")
    analise_df = pd.DataFrame({
        "Posição": ["Mais Recente", "2º", "3º", "4º", "5º", "6ª Anterior", "7ª Anterior"],
        "Número": ultimos_numeros[-7:],
        "Terminal": [n % 10 for n in ultimos_numeros[-7:]]
    })
    st.dataframe(analise_df, use_container_width=True)
else:
    st.write(ultimos_numeros)

# Entrada atual com probabilidades ordenadas
if st.session_state.entrada_atual:
    st.subheader("📥 Entrada Atual (Ordenada por Probabilidade)")
    
    # Criar DataFrame para exibição ordenada
    prob_df = pd.DataFrame([
        {"Número": num, "Probabilidade": prob} 
        for num, prob in st.session_state.entrada_atual["probabilidades_individual"].items()
    ])
    prob_df = prob_df.sort_values("Probabilidade", ascending=False)
    prob_df["Rank"] = range(1, len(prob_df) + 1)
    prob_df = prob_df[["Rank", "Número", "Probabilidade"]]
    
    st.dataframe(prob_df, use_container_width=True)
    
    # Mostrar estratégias ativas
    if st.session_state.entrada_atual.get("estrategia_7_ativa"):
        st.info("🎯 Estratégia 7 Rodadas contribuindo para esta entrada")
    
    # Também mostrar como lista simples
    st.write("Lista de entrada:", st.session_state.entrada_atual["entrada"])

# NOVA SEÇÃO: Histórico da Estratégia 7 Rodadas
if ATIVAR_ESTRATEGIA_7_RODADAS and st.session_state.historico_estrategia_7:
    st.subheader("📈 Histórico Estratégia 7 Rodadas")
    historico_df = pd.DataFrame(list(st.session_state.historico_estrategia_7)[-10:])
    if not historico_df.empty:
        st.dataframe(historico_df[["timestamp", "terminais_ativos", "analise"]], use_container_width=True)

# Histórico de confiança
if st.session_state.historico_probs:
    st.subheader("📈 Confiança da IA (últimas previsões)")
    plt.figure(figsize=(8,2.5))
    plt.plot(list(st.session_state.historico_probs), marker='o')
    plt.title("Evolução da Probabilidade")
    plt.grid(True)
    st.pyplot(plt)
