import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# =============================
# Configuração de Logging
# =============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('roleta_ia.log'),
        logging.StreamHandler()
    ]
)

def log_estrategia(mensagem, nivel="info"):
    """Log estruturado para estratégias"""
    log_func = getattr(logging, nivel.lower(), logging.info)
    log_func(f"🎯 {mensagem}")

# =============================
# Classes de Gerenciamento
# =============================
class Estatisticas:
    def __init__(self):
        self.acertos = 0
        self.erros = 0
    
    @property
    def total(self):
        return self.acertos + self.erros
    
    @property
    def taxa_acerto(self):
        return (self.acertos / self.total * 100) if self.total > 0 else 0.0
    
    def registrar_acerto(self):
        self.acertos += 1
        log_estrategia(f"ACERTO registrado - Taxa: {self.taxa_acerto:.1f}%")
    
    def registrar_erro(self):
        self.erros += 1
        log_estrategia(f"ERRO registrado - Taxa: {self.taxa_acerto:.1f}%")

class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=1000)
    
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        log_estrategia(f"Número {numero_dict['number']} adicionado ao histórico")

# =============================
# Funções Auxiliares Otimizadas
# =============================
def criar_mapa_vizinhos(layout, distancia=5):
    """Cria mapa de vizinhos para acesso O(1)"""
    mapa = {}
    n = len(layout)
    for i, numero in enumerate(layout):
        vizinhos = []
        for j in range(1, distancia + 1):
            vizinhos.append(layout[(i - j) % n])
        vizinhos.append(numero)
        for j in range(1, distancia + 1):
            vizinhos.append(layout[(i + j) % n])
        mapa[numero] = vizinhos
    return mapa

# Pré-computar mapa de vizinhos
VIZINHOS_MAP = criar_mapa_vizinhos(ROULETTE_LAYOUT, 5)

def obter_vizinhos_otimizado(numero, distancia=5):
    """Versão otimizada usando mapa pré-computado"""
    return VIZINHOS_MAP.get(numero, [])

def obter_vizinhos_range(numero, antes=2, depois=2):
    """Para casos específicos que precisam de range diferente"""
    vizinhos_completos = obter_vizinhos_otimizado(numero, 5)
    return vizinhos_completos[(5-antes):(6+depois)]

def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
        log_estrategia(f"Mensagem Telegram enviada: {msg[:50]}...")
    except Exception as e:
        log_estrategia(f"Erro ao enviar para Telegram: {e}", "error")

def carregar_historico_otimizado():
    """Carrega histórico com validação robusta"""
    if not os.path.exists(HISTORICO_PATH):
        log_estrategia("Arquivo de histórico não encontrado, criando novo")
        return []
    
    try:
        with open(HISTORICO_PATH, "r", encoding='utf-8') as f:
            historico = json.load(f)
        
        historico_validado = []
        for item in historico:
            if isinstance(item, dict) and 'number' in item:
                # Valida se o número é válido na roleta
                if item['number'] in ROULETTE_LAYOUT + [None]:
                    historico_validado.append(item)
        
        log_estrategia(f"Histórico carregado: {len(historico_validado)} registros válidos")
        return historico_validado[-1000:]  # Mantém só os últimos 1000
    except Exception as e:
        log_estrategia(f"Erro ao carregar histórico: {e}", "error")
        return []

def salvar_historico(historico):
    try:
        with open(HISTORICO_PATH, "w", encoding='utf-8') as f:
            json.dump(list(historico), f, indent=2)
        log_estrategia(f"Histórico salvo: {len(historico)} registros")
    except Exception as e:
        log_estrategia(f"Erro ao salvar histórico: {e}", "error")

@st.cache_data(ttl=10)  # Cache de 10 segundos
def fetch_latest_result_cached():
    return fetch_latest_result()

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        
        log_estrategia(f"Resultado buscado: {number} (timestamp: {timestamp})")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        log_estrategia(f"Erro ao buscar resultado: {e}", "error")
        return None

def processar_conferencia(numero_real, previsao, estrategia_nome):
    """Processa conferência de forma genérica"""
    if not previsao:
        return False, set()
    
    numeros_para_conferir = set()
    
    if estrategia_nome == "recorrencia":
        # Expande com vizinhos para recorrência
        for n in previsao:
            numeros_para_conferir.update(obter_vizinhos_range(n, 2, 2))
    else:
        # Usa lista direta para 31/34
        numeros_para_conferir.update(previsao)
    
    acertou = numero_real in numeros_para_conferir
    log_estrategia(f"Conferência {estrategia_nome}: número {numero_real} {'ESTÁ' if acertou else 'NÃO ESTÁ'} na previsão")
    
    return acertou, numeros_para_conferir

# =============================
# Estratégias
# =============================
class IA_Recorrencia:
    def __init__(self, layout=None, top_n=3):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        log_estrategia("IA Recorrência inicializada")

    def prever(self, historico):
        if not historico:
            log_estrategia("Histórico vazio, sem previsão")
            return []

        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"] if isinstance(historico_lista[-1], dict) else None
        if ultimo_numero is None:
            log_estrategia("Último número inválido, sem previsão")
            return []

        antes, depois = [], []

        # Percorre todas as ocorrências anteriores do último número
        for i, h in enumerate(historico_lista[:-1]):
            if isinstance(h, dict) and h.get("number") == ultimo_numero:
                if i - 1 >= 0 and isinstance(historico_lista[i-1], dict):
                    antes.append(historico_lista[i-1]["number"])
                if i + 1 < len(historico_lista) and isinstance(historico_lista[i+1], dict):
                    depois.append(historico_lista[i+1]["number"])

        if not antes and not depois:
            log_estrategia(f"Nenhum padrão encontrado para número {ultimo_numero}")
            return []

        contagem_antes = Counter(antes)
        contagem_depois = Counter(depois)

        top_antes = [num for num, _ in contagem_antes.most_common(self.top_n)]
        top_depois = [num for num, _ in contagem_depois.most_common(self.top_n)]

        candidatos = list(set(top_antes + top_depois))
        log_estrategia(f"Candidatos recorrência: {candidatos}")

        numeros_previstos = []
        for n in candidatos:
            vizinhos = obter_vizinhos_range(n, 1, 1)
            for v in vizinhos:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        log_estrategia(f"Previsão recorrência final: {sorted(numeros_previstos)}")
        return numeros_previstos

def estrategia_31_34(numero_capturado):
    """
    Dispara a estratégia 31/34 se terminal ∈ {2,6,9}.
    Envia TELEGRAM mostrando apenas "31 34" (como solicitado).
    Retorna a lista completa de entrada usada para conferência (internamente).
    """
    if numero_capturado is None:
        return None
    try:
        terminal = int(str(numero_capturado)[-1])
    except Exception:
        return None

    if terminal not in {2, 6, 9}:
        return None

    # gera vizinhos fixos de 31 e 34 (5 antes + número + 5 depois)
    viz_31 = obter_vizinhos_otimizado(31, 5)
    viz_34 = obter_vizinhos_otimizado(34, 5)

    # monta entrada: 0,26,30 + vizinhos de 31 + vizinhos de 34
    entrada = set([0, 26, 30] + viz_31 + viz_34)

    # enviar ALERTA compacto: só 31 34 (como você pediu)
    msg = (
        "🎯 Estratégia 31/34 disparada!\n"
        f"Número capturado: {numero_capturado} (terminal {terminal})\n"
        "Entrar nos números: 31 34"
    )
    enviar_telegram(msg)
    log_estrategia(f"Estratégia 31/34 disparada - Número: {numero_capturado}, Terminal: {terminal}")

    return list(entrada)

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA de Recorrência (Antes + Depois) Profissional")
st_autorefresh(interval=3000, key="refresh")

# Inicialização segura do session_state
for key, default in {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia(),
    "previsao": [],
    "previsao_31_34": [],
    "estatisticas_recorrencia": Estatisticas(),
    "estatisticas_31_34": Estatisticas(),
    "contador_rodadas": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Carregar histórico existente
historico = carregar_historico_otimizado()
for n in historico:
    st.session_state.estrategia.adicionar_numero(n)

# Captura número
resultado = fetch_latest_result_cached()
ultimo_ts = st.session_state.estrategia.historico[-1]["timestamp"] if st.session_state.estrategia.historico else None

if resultado and resultado.get("timestamp") != ultimo_ts:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    st.session_state.estrategia.adicionar_numero(numero_dict)
    salvar_historico(list(st.session_state.estrategia.historico))

    numero_real = numero_dict["number"]
    
    # -----------------------------
    # Conferência GREEN/RED (Recorrência)
    # -----------------------------
    if st.session_state.previsao:
        acertou, numeros_conferencia = processar_conferencia(
            numero_real, 
            st.session_state.previsao, 
            "recorrencia"
        )
        
        if acertou:
            st.session_state.estatisticas_recorrencia.registrar_acerto()
            st.success(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
        else:
            st.session_state.estatisticas_recorrencia.registrar_erro()
            st.error(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
            enviar_telegram(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")

        st.session_state.previsao = []

    # -----------------------------
    # Conferência GREEN/RED (31/34)
    # -----------------------------
    if st.session_state.previsao_31_34:
        acertou, numeros_conferencia = processar_conferencia(
            numero_real, 
            st.session_state.previsao_31_34, 
            "31_34"
        )
        
        if acertou:
            st.session_state.estatisticas_31_34.registrar_acerto()
            st.success(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
            enviar_telegram(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
        else:
            st.session_state.estatisticas_31_34.registrar_erro()
            st.error(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
            enviar_telegram(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")

        st.session_state.previsao_31_34 = []

    # atualiza contador e decide qual estratégia rodar
    st.session_state.contador_rodadas += 1

    # -----------------------------
    # Previsão a cada 3 rodadas (recorrência)
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros

            # 🔹 Ordena do menor para o maior apenas na exibição
            msg_alerta = "🎯 Próximos números prováveis (Recorrência): " + \
                         " ".join(str(n) for n in sorted(prox_numeros))
            enviar_telegram(msg_alerta)
    else:
        # -----------------------------
        # Estratégia 31/34 (nos intervalos)
        # -----------------------------
        entrada_31_34 = estrategia_31_34(numero_dict["number"])
        if entrada_31_34:
            # salva a lista completa para conferência na próxima rodada
            st.session_state.previsao_31_34 = entrada_31_34

# Histórico
st.subheader("📜 Histórico (últimos 3 números)")
st.write(list(st.session_state.estrategia.historico)[-3:])

# Estatísticas GREEN/RED (Recorrência)
stats_rec = st.session_state.estatisticas_recorrencia
qtd_previstos_rec = len(st.session_state.get("previsao", []))

col1, col2, col3, col7 = st.columns(4)
col1.metric("🟢 GREEN", stats_rec.acertos)
col2.metric("🔴 RED", stats_rec.erros)
col3.metric("✅ Taxa de acerto", f"{stats_rec.taxa_acerto:.1f}%")
col7.metric("🎯 Qtd. previstos Recorrência", qtd_previstos_rec)

# Estatísticas 31/34
stats_31_34 = st.session_state.estatisticas_31_34
qtd_previstos_31_34 = len(st.session_state.get("previsao_31_34", []))

col4, col5, col6, col8 = st.columns(4)
col4.metric("🟢 GREEN 31/34", stats_31_34.acertos)
col5.metric("🔴 RED 31/34", stats_31_34.erros)
col6.metric("✅ Taxa 31/34", f"{stats_31_34.taxa_acerto:.1f}%")
col8.metric("🎯 Qtd. previstos 31/34", qtd_previstos_31_34)

# Estatísticas recorrência
historico_lista = list(st.session_state.estrategia.historico)
historico_total = len(historico_lista)
ultimo_numero = (historico_lista[-1]["number"] if historico_total > 0 and isinstance(historico_lista[-1], dict) else None)

ocorrencias_ultimo = 0
if ultimo_numero is not None:
    ocorrencias_ultimo = sum(
        1 for h in historico_lista[:-1] if isinstance(h, dict) and h.get("number") == ultimo_numero
    )

st.subheader("📊 Estatísticas da Recorrência")
st.write(f"Total de registros no histórico: {historico_total}")
if ultimo_numero is not None:
    st.write(f"Quantidade de ocorrências do último número ({ultimo_numero}) usadas para recorrência: {ocorrencias_ultimo}")

# Log de atividade recente
st.subheader("📋 Log de Atividade")
try:
    with open('roleta_ia.log', 'r') as f:
        logs = f.readlines()[-10:]  # Últimas 10 linhas
    st.text_area("Logs recentes:", "".join(logs), height=150)
except FileNotFoundError:
    st.info("Arquivo de log ainda não criado")
