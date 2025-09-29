# Domina03.py (com Autoencoder para detecção de padrões)
import streamlit as st
import json
import os
import time
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from typing import List
import pandas as pd
import io
from datetime import datetime
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense
import warnings
warnings.filterwarnings('ignore')

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
METRICAS_PATH = "historico_metricas.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Canal principal
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# Canal alternativo para Top N Dinâmico
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18   # janela móvel para Top N dinâmico
MIN_TOP_N = 5      # mínimo de números na Top N
MAX_TOP_N = 10     # máximo de números na Top N
MAX_PREVIEWS = 10   # limite final de previsões para reduzir custo

# =============================
# Configurações de Otimização
# =============================
TREINAMENTO_INTERVALO = 5  # Treinar a cada 5 rodadas
MIN_HISTORICO_TREINAMENTO = 50  # Mínimo de registros para treinar

# =============================
# NOVO: Configurações do Autoencoder
# =============================
AUTOENCODER_WINDOW = 50    # Janela para análise de padrões
ANOMALY_THRESHOLD = 0.85   # Percentil para detecção de anomalias (85%)

# =============================
# Utilitários (Telegram, histórico, API, vizinhos)
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_telegram_topN(msg: str, token=ALT_TELEGRAM_TOKEN, chat_id=ALT_TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram TopN enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram Top N: {e}")

def carregar_historico():
    """Carrega histórico persistente do arquivo"""
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            logging.info(f"📁 Histórico carregado: {len(historico)} registros")
            return historico
        except Exception as e:
            logging.error(f"Erro ao carregar histórico: {e}")
            return []
    return []

def salvar_historico(numero_dict):
    """Salva número diretamente da API no arquivo histórico persistente"""
    try:
        # Carrega histórico existente
        historico_existente = []
        if os.path.exists(HISTORICO_PATH):
            try:
                with open(HISTORICO_PATH, "r") as f:
                    historico_existente = json.load(f)
            except Exception as e:
                logging.error(f"Erro ao carregar histórico: {e}")
                historico_existente = []
        
        # Verifica se o número já existe (pelo timestamp)
        timestamp_novo = numero_dict.get("timestamp")
        ja_existe = False
        
        for registro in historico_existente:
            if (isinstance(registro, dict) and 
                registro.get("timestamp") == timestamp_novo):
                ja_existe = True
                break
        
        # Só adiciona se for um novo registro
        if not ja_existe:
            historico_existente.append(numero_dict)
            
            # Salva TODOS os registros no arquivo (sem limite de tamanho)
            with open(HISTORICO_PATH, "w") as f:
                json.dump(historico_existente, f, indent=2)
            
            logging.info(f"✅ Número {numero_dict['number']} salvo no histórico persistente")
            return True
        else:
            logging.info(f"⏳ Número {numero_dict['number']} já existe no histórico")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")
        return False

def salvar_metricas(m):
    try:
        # salva lista de métricas (apenda)
        hist = []
        if os.path.exists(METRICAS_PATH):
            try:
                with open(METRICAS_PATH, "r") as f:
                    hist = json.load(f)
            except Exception:
                hist = []
        hist.append(m)
        with open(METRICAS_PATH, "w") as f:
            json.dump(hist, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar métricas: {e}")

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=6)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def obter_vizinhos(numero, layout, antes=2, depois=2):
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

def obter_vizinhos_fixos(numero, layout, antes=5, depois=5):
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

# =============================
# Estratégia
# =============================
class EstrategiaDeslocamento:
    def __init__(self):
        # Carrega do arquivo persistente
        self.historico = deque(self.carregar_historico_persistente(), maxlen=15000)
    
    def carregar_historico_persistente(self):
        """Carrega histórico completo do arquivo persistente"""
        if os.path.exists(HISTORICO_PATH):
            try:
                with open(HISTORICO_PATH, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erro ao carregar histórico persistente: {e}")
        return []
    
    def adicionar_numero(self, numero_dict):
        # Já está sendo salvo no arquivo pela função salvar_historico
        # Esta função apenas mantém o histórico em memória
        self.historico.append(numero_dict)

# =============================
# NOVO: Autoencoder para Detecção de Padrões Anômalos
# =============================
class Pattern_Analyzer:
    def __init__(self, encoding_dim=8, window_size=AUTOENCODER_WINDOW):
        self.encoding_dim = encoding_dim
        self.window_size = window_size
        self.autoencoder = None
        self.is_trained = False
        
    def build_autoencoder(self, input_dim):
        """Constrói o modelo de autoencoder"""
        try:
            # Input layer
            input_layer = Input(shape=(input_dim,))
            
            # Encoder
            encoded = Dense(32, activation='relu')(input_layer)
            encoded = Dense(16, activation='relu')(encoded)
            encoded = Dense(self.encoding_dim, activation='relu')(encoded)
            
            # Decoder
            decoded = Dense(16, activation='relu')(encoded)
            decoded = Dense(32, activation='relu')(decoded)
            decoded = Dense(input_dim, activation='sigmoid')(decoded)
            
            self.autoencoder = Model(input_layer, decoded)
            self.autoencoder.compile(optimizer='adam', loss='mse', metrics=['mae'])
            
            logging.info("✅ Autoencoder construído com sucesso")
            return True
        except Exception as e:
            logging.error(f"❌ Erro ao construir autoencoder: {e}")
            return False
    
    def prepare_data(self, historico):
        """Prepara os dados para o autoencoder (one-hot encoding)"""
        try:
            if len(historico) < self.window_size:
                return None
                
            # Pega os últimos números
            numeros = [h['number'] for h in list(historico)[-self.window_size:]]
            
            # One-hot encoding (37 números: 0-36)
            encoded_data = np.zeros((len(numeros), 37))
            for i, num in enumerate(numeros):
                if 0 <= num <= 36:
                    encoded_data[i, num] = 1.0
            
            return encoded_data
        except Exception as e:
            logging.error(f"❌ Erro ao preparar dados: {e}")
            return None
    
    def train(self, historico):
        """Treina o autoencoder"""
        try:
            data = self.prepare_data(historico)
            if data is None or len(data) < 10:
                self.is_trained = False
                return False
            
            if self.autoencoder is None:
                if not self.build_autoencoder(37):
                    return False
            
            # Treina o autoencoder
            history = self.autoencoder.fit(
                data, data,
                epochs=100,
                batch_size=8,
                verbose=0,
                shuffle=True,
                validation_split=0.2
            )
            
            self.is_trained = True
            logging.info(f"✅ Autoencoder treinado - Loss final: {history.history['loss'][-1]:.4f}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no treinamento do autoencoder: {e}")
            self.is_trained = False
            return False
    
    def detect_anomalies(self, historico):
        """Detecta números com padrões anômalos (oportunidades)"""
        try:
            if not self.is_trained or self.autoencoder is None:
                return []
            
            data = self.prepare_data(historico)
            if data is None:
                return []
            
            # Faz reconstruções
            reconstructions = self.autoencoder.predict(data, verbose=0)
            
            # Calcula erro de reconstrução para cada amostra
            mse = np.mean(np.power(data - reconstructions, 2), axis=1)
            
            # Identifica anomalias (amostras com alto erro de reconstrução)
            threshold = np.percentile(mse, ANOMALY_THRESHOLD * 100)
            anomaly_indices = np.where(mse > threshold)[0]
            
            # Pega os números correspondentes às anomalias
            numeros = [h['number'] for h in list(historico)[-self.window_size:]]
            anomalias = [numeros[i] for i in anomaly_indices if i < len(numeros)]
            
            # Remove duplicatas e limita a quantidade
            anomalias_unicas = list(dict.fromkeys(anomalias))[:8]  # Máximo 8 anomalias
            
            if anomalias_unicas:
                logging.info(f"🎯 Anomalias detectadas: {anomalias_unicas}")
            
            return anomalias_unicas
            
        except Exception as e:
            logging.error(f"❌ Erro na detecção de anomalias: {e}")
            return []

# =============================
# IA Recorrência com RandomForest (OTIMIZADO)
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=16, window=WINDOW_SIZE):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.window = window
        self.model = None
        self.ultimo_treinamento_size = 0

    def _criar_features_simples(self, historico: List[dict]):
        numeros = [h["number"] for h in historico]
        if len(numeros) < 3:
            return None, None
        X = []
        y = []
        for i in range(2, len(numeros)):
            last2 = numeros[i-2]
            last1 = numeros[i-1]
            nbrs = obter_vizinhos(last1, self.layout, antes=2, depois=2)
            feat = [last2, last1] + nbrs
            X.append(feat)
            y.append(numeros[i])
        return np.array(X), np.array(y)

    def treinar(self, historico):
        if len(historico) < 10:
            self.model = None
            return False
            
        X, y = self._criar_features_simples(historico)
        if X is None or len(X) == 0:
            self.model = None
            return False
        
        try:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_split=5,
                n_jobs=-1,
                random_state=42
            )
            self.model.fit(X, y)
            self.ultimo_treinamento_size = len(historico)
            logging.info(f"✅ Modelo RF treinado com {len(X)} amostras")
            return True
        except Exception as e:
            logging.error(f"Erro treinando RF: {e}")
            self.model = None
            return False

    def precisa_treinar(self, historico_atual):
        if self.model is None:
            return True
        crescimento = len(historico_atual) - self.ultimo_treinamento_size
        return crescimento >= 20

    def prever(self, historico, anomalias=[]):
        """
        Previsão aprimorada com integração de anomalias do autoencoder
        """
        if not historico or len(historico) < 2:
            return []

        # Método original de estatística antes/depois
        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"] if isinstance(historico_lista[-1], dict) else None
        if ultimo_numero is None:
            return []

        antes, depois = [], []
        for i, h in enumerate(historico_lista[:-1]):
            if isinstance(h, dict) and h.get("number") == ultimo_numero:
                if i - 1 >= 0 and isinstance(historico_lista[i-1], dict):
                    antes.append(historico_lista[i-1]["number"])
                if i + 1 < len(historico_lista) and isinstance(historico_lista[i+1], dict):
                    depois.append(historico_lista[i+1]["number"])

        cont_antes = Counter(antes)
        cont_depois = Counter(depois)
        top_antes = [num for num, _ in cont_antes.most_common(self.top_n)]
        top_depois = [num for num, _ in cont_depois.most_common(self.top_n)]
        candidatos = list(set(top_antes + top_depois))

        # **INTEGRAÇÃO DAS ANOMALIAS** - Boost nos números anômalos
        for anomalia in anomalias:
            if anomalia not in candidatos:
                candidatos.append(anomalia)
            # Da boost também nos vizinhos das anomalias
            vizinhos_anomalia = obter_vizinhos(anomalia, self.layout, antes=1, depois=1)
            for vizinho in vizinhos_anomalia:
                if vizinho not in candidatos:
                    candidatos.append(vizinho)

        # Treinamento do RF
        window_hist = historico_lista[-max(len(historico_lista), self.window):]
        if self.precisa_treinar(window_hist):
            self.treinar(window_hist)

        # Predição do RF
        if self.model is not None:
            numeros = [h["number"] for h in historico_lista]
            last2 = numeros[-2] if len(numeros) > 1 else 0
            last1 = numeros[-1]
            feats = [last2, last1] + obter_vizinhos(last1, self.layout, antes=1, depois=1)
            try:
                probs = self.model.predict_proba([feats])[0]
                classes = self.model.classes_
                idx_top = np.argsort(probs)[-self.top_n:]
                top_ml = [int(classes[i]) for i in idx_top]
                candidatos = list(set(candidatos + top_ml))
            except Exception as e:
                logging.error(f"Erro predict_proba RF: {e}")

        # Expandir para vizinhos físicos
        numeros_previstos = []
        for n in candidatos:
            vizs = obter_vizinhos(n, self.layout, antes=2, depois=2)
            for v in vizs:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)

        # **BOOST NAS ANOMALIAS** - Garante que anomalias fiquem nas previsões
        for anomalia in anomalias:
            if anomalia not in numeros_previstos:
                numeros_previstos.append(anomalia)

        # Redução inteligente
        numeros_previstos = reduzir_metade_inteligente(numeros_previstos, historico)

        # Limite final
        if len(numeros_previstos) > MAX_PREVIEWS:
            ultimos = [h["number"] for h in list(historico)[-WINDOW_SIZE:]] if historico else []
            freq = Counter(ultimos)
            topn_greens = st.session_state.get("topn_greens", {})
            scores = {}
            for n in numeros_previstos:
                base_score = freq.get(n, 0) + 0.8 * topn_greens.get(n, 0)
                # **BONUS EXTRA PARA ANOMALIAS**
                if n in anomalias:
                    base_score += 2.0  # Boost significativo para anomalias
                scores[n] = base_score
            numeros_previstos = sorted(numeros_previstos, key=lambda x: scores.get(x, 0), reverse=True)[:MAX_PREVIEWS]

        return numeros_previstos

# =============================
# Redução inteligente (metade) - função reutilizável
# =============================
def reduzir_metade_inteligente(previsoes, historico):
    if not previsoes:
        return []
    ultimos_numeros = [h["number"] for h in list(historico)[-WINDOW_SIZE:]] if historico else []
    contagem_total = Counter(ultimos_numeros)
    topn_greens = st.session_state.get("topn_greens", {})
    pontuacoes = {}
    for n in previsoes:
        freq = contagem_total.get(n, 0)
        vizinhos = obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1)
        redundancia = sum(1 for v in vizinhos if v in previsoes)
        bonus = topn_greens.get(n, 0)
        pontuacoes[n] = freq + (bonus * 0.8) - (0.5 * redundancia)
    ordenados = sorted(pontuacoes.keys(), key=lambda x: pontuacoes[x], reverse=True)
    n_reduzidos = max(1, len(ordenados) // 2)
    return ordenados[:n_reduzidos]

# =============================
# Ajuste Dinâmico Top N
# =============================
TOP_N_COOLDOWN = 3
TOP_N_PROB_BASE = 0.3
TOP_N_PROB_MAX = 0.5
TOP_N_PROB_MIN = 0.2
TOP_N_WINDOW = 12

if "topn_history" not in st.session_state:
    st.session_state.topn_history = deque(maxlen=TOP_N_WINDOW)
if "topn_reds" not in st.session_state:
    st.session_state.topn_reds = {}
if "topn_greens" not in st.session_state:
    st.session_state.topn_greens = {}

def atualizar_cooldown_reds():
    novos_reds = {}
    for num, rodadas in st.session_state.topn_reds.items():
        if rodadas > 1:
            novos_reds[num] = rodadas - 1
    st.session_state.topn_reds = novos_reds

def calcular_prob_min_topN():
    historico = list(st.session_state.topn_history)
    if not historico:
        return TOP_N_PROB_BASE
    taxa_red = historico.count("R") / len(historico)
    prob_min = TOP_N_PROB_BASE + (taxa_red * (TOP_N_PROB_MAX - TOP_N_PROB_BASE))
    return min(max(prob_min, TOP_N_PROB_MIN), TOP_N_PROB_MAX)

def ajustar_top_n(previsoes, historico=None, min_n=MIN_TOP_N, max_n=MAX_TOP_N):
    if not previsoes:
        return previsoes[:min_n]
    atualizar_cooldown_reds()
    prob_min = calcular_prob_min_topN()
    filtrados = [num for num in previsoes if num not in st.session_state.topn_reds]
    pesos = {}
    for num in filtrados:
        pesos[num] = 1.0 + st.session_state.topn_greens.get(num, 0) * 0.05
    ordenados = sorted(pesos.keys(), key=lambda x: pesos[x], reverse=True)
    n = max(min_n, min(max_n, int(len(ordenados) * prob_min) + min_n))
    return ordenados[:n]

def registrar_resultado_topN(numero_real, top_n):
    for num in top_n:
        if num == numero_real:
            st.session_state.topn_greens[num] = st.session_state.topn_greens.get(num, 0) + 1
            st.session_state.topn_history.append("G")
        else:
            st.session_state.topn_reds[num] = TOP_N_COOLDOWN
            st.session_state.topn_history.append("R")

# =============================
# Estratégia 31/34
# =============================
def estrategia_31_34(numero_capturado):
    if numero_capturado is None:
        return None
    try:
        terminal = int(str(numero_capturado)[-1])
    except Exception:
        return None
    if terminal not in {2, 6, 9}:
        return None
    viz_31 = obter_vizinhos_fixos(31, ROULETTE_LAYOUT, antes=5, depois=5)
    viz_34 = obter_vizinhos_fixos(34, ROULETTE_LAYOUT, antes=5, depois=5)
    entrada = set([0, 26, 30] + viz_31 + viz_34)
    msg = (
        "🎯 Estratégia 31/34 disparada!\n"
        f"Número capturado: {numero_capturado} (terminal {terminal})\n"
        "Entrar nos números: 31 34"
    )
    enviar_telegram(msg)
    return list(entrada)

# =============================
# Função para Download do Histórico
# =============================
def gerar_download_historico():
    """Gera arquivo para download do histórico completo"""
    try:
        # Carrega o histórico persistente
        historico = carregar_historico()
        
        if not historico:
            st.warning("Nenhum histórico disponível para download")
            return None
        
        # Converte para DataFrame
        df = pd.DataFrame(historico)
        
        # Cria buffer para o arquivo
        output = io.BytesIO()
        
        # Cria arquivo Excel com múltiplas abas
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Aba com histórico completo
            df.to_excel(writer, sheet_name='Historico_Completo', index=False)
            
            # Aba com estatísticas
            stats_data = {
                'Metrica': [
                    'Total de Registros',
                    'Período Inicial', 
                    'Período Final',
                    'Números Mais Frequentes',
                    'Acertos Recorrência',
                    'Acertos Top N',
                    'Acertos 31/34'
                ],
                'Valor': [
                    len(df),
                    df['timestamp'].min() if 'timestamp' in df.columns else 'N/A',
                    df['timestamp'].max() if 'timestamp' in df.columns else 'N/A',
                    str(dict(Counter(df['number']).most_common(5))) if 'number' in df.columns else 'N/A',
                    st.session_state.get('acertos', 0),
                    st.session_state.get('acertos_topN', 0),
                    st.session_state.get('acertos_31_34', 0)
                ]
            }
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Estatisticas', index=False)
            
            # Aba com últimos 100 registros
            ultimos_100 = df.tail(100)
            ultimos_100.to_excel(writer, sheet_name='Ultimos_100', index=False)
        
        output.seek(0)
        return output
    
    except Exception as e:
        logging.error(f"Erro ao gerar download: {e}")
        return None

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência + Autoencoder (Padrões Anômalos)")
st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state (todas as chaves necessárias)
defaults = {
    "estrategia": EstrategiaDeslocamento(),
    "ia_recorrencia": IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=16, window=WINDOW_SIZE),
    "pattern_analyzer": Pattern_Analyzer(),  # NOVO: Autoencoder
    "previsao": [],
    "previsao_topN": [],
    "previsao_31_34": [],
    "anomalias_detectadas": [],  # NOVO: Lista de anomalias
    "acertos": 0,
    "erros": 0,
    "acertos_topN": 0,
    "erros_topN": 0,
    "acertos_31_34": 0,
    "erros_31_34": 0,
    "contador_rodadas": 0,
    "topn_history": deque(maxlen=TOP_N_WINDOW),
    "topn_reds": {},
    "topn_greens": {},
    "ultimo_timestamp_processado": None,
    "ultima_previsao_enviada": None,
    "aguardando_novo_sorteio": False,
    "ultimo_treinamento_size": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Carregar histórico existente
# -----------------------------
# Captura número (API)
# -----------------------------
resultado = fetch_latest_result()

# Verificação robusta para evitar duplicatas
novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if (st.session_state.ultimo_timestamp_processado is None or 
        resultado.get("timestamp") != st.session_state.ultimo_timestamp_processado):
        novo_sorteio = True
        logging.info(f"🎲 NOVO SORTEIO: {resultado['number']} - {resultado['timestamp']}")
        st.session_state.aguardando_novo_sorteio = False

# Nova rodada detectada
if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    # Salva no histórico persistente
    salvo_com_sucesso = salvar_historico(numero_dict)
    
    if salvo_com_sucesso:
        st.session_state.estrategia.adicionar_numero(numero_dict)
    
    st.session_state.ultimo_timestamp_processado = resultado["timestamp"]
    numero_real = numero_dict["number"]

    # -----------------------------
    # Conferências (mantidas iguais)
    # -----------------------------
    if st.session_state.previsao:
        numeros_com_vizinhos = []
        for n in st.session_state.previsao:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
                if v not in numeros_com_vizinhos:
                    numeros_com_vizinhos.append(v)
        if numero_real in numeros_com_vizinhos:
            st.session_state.acertos += 1
            st.success(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência (incluindo vizinhos).")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
            enviar_telegram(f"🔴 RED! Número {numero_real} não estava na previsão de recorrência nem nos vizinhos.")
        st.session_state.previsao = []

    if st.session_state.previsao_topN:
        topN_com_vizinhos = []
        for n in st.session_state.previsao_topN:
            for v in obter_vizinhos(n, ROULETTE_LAYOUT, antes=1, depois=1):
                if v not in topN_com_vizinhos:
                    topN_com_vizinhos.append(v)
        if numero_real in topN_com_vizinhos:
            st.session_state.acertos_topN += 1
            st.success(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
            enviar_telegram_topN(f"🟢 GREEN Top N! Número {numero_real} estava entre os mais prováveis.")
            st.session_state.topn_greens[numero_real] = st.session_state.topn_greens.get(numero_real, 0) + 1
        else:
            st.session_state.erros_topN += 1
            st.error(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
            enviar_telegram_topN(f"🔴 RED Top N! Número {numero_real} não estava entre os mais prováveis.")
        st.session_state.previsao_topN = []

    if st.session_state.previsao_31_34:
        if numero_real in st.session_state.previsao_31_34:
            st.session_state.acertos_31_34 += 1
            st.success(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
            enviar_telegram(f"🟢 GREEN (31/34)! Número {numero_real} estava na entrada 31/34.")
        else:
            st.session_state.erros_31_34 += 1
            st.error(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
            enviar_telegram(f"🔴 RED (31/34)! Número {numero_real} não estava na entrada 31/34.")
        st.session_state.previsao_31_34 = []

    # -----------------------------
    # NOVO: Detecção de Anomalias com Autoencoder
    # -----------------------------
    historico_size = len(st.session_state.estrategia.historico)
    
    # Treinar autoencoder quando houver dados suficientes
    if historico_size >= AUTOENCODER_WINDOW and st.session_state.contador_rodadas % 10 == 0:
        logging.info("🔄 Treinando Autoencoder para detecção de padrões...")
        sucesso_treinamento = st.session_state.pattern_analyzer.train(st.session_state.estrategia.historico)
        if sucesso_treinamento:
            st.session_state.anomalias_detectadas = st.session_state.pattern_analyzer.detect_anomalies(st.session_state.estrategia.historico)
            if st.session_state.anomalias_detectadas:
                logging.info(f"🎯 Anomalias detectadas: {st.session_state.anomalias_detectadas}")

    # -----------------------------
    # Geração de Previsão com Integração de Anomalias
    # -----------------------------
    if st.session_state.contador_rodadas % 2 == 0 and not st.session_state.aguardando_novo_sorteio:
        # Detectar anomalias se o autoencoder estiver treinado
        anomalias = []
        if st.session_state.pattern_analyzer.is_trained:
            anomalias = st.session_state.pattern_analyzer.detect_anomalies(st.session_state.estrategia.historico)
            st.session_state.anomalias_detectadas = anomalias
        
        # Previsão com integração de anomalias
        prox_numeros = st.session_state.ia_recorrencia.prever(
            st.session_state.estrategia.historico, 
            anomalias=anomalias
        )
        
        if prox_numeros:
            prox_numeros = list(dict.fromkeys(prox_numeros))
            st.session_state.previsao = prox_numeros

            entrada_topN = ajustar_top_n(prox_numeros, st.session_state.estrategia.historico)
            st.session_state.previsao_topN = entrada_topN

            # CONTROLE DE ALERTAS
            previsao_atual = f"{sorted(prox_numeros)}_{sorted(entrada_topN)}"
            
            if previsao_atual != st.session_state.ultima_previsao_enviada:
                st.session_state.ultima_previsao_enviada = previsao_atual
                st.session_state.aguardando_novo_sorteio = True
                
                # Envio Telegram com informações das anomalias
                s = sorted(prox_numeros)
                mensagem_recorrencia = "🎯 NP: " + " ".join(map(str, s[:5]))
                if len(s) > 5:
                    mensagem_recorrencia += "\n" + " ".join(map(str, s[5:10]))
                
                # Adiciona info sobre anomalias se houver
                if anomalias:
                    mensagem_recorrencia += f"\n🔍 Anomalias: {', '.join(map(str, sorted(anomalias)))}"
                
                enviar_telegram(mensagem_recorrencia)
                enviar_telegram_topN("Top N: " + " ".join(map(str, sorted(entrada_topN))))
                
                logging.info("🔔 Novos alertas enviados para Telegram")
            else:
                logging.info("⏳ Previsão idêntica à anterior, alertas não enviados")
    else:
        # Estratégia 31/34
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34

    # Treinamento controlado do RF
    historico_size = len(st.session_state.estrategia.historico)
    if (historico_size >= MIN_HISTORICO_TREINAMENTO and 
        st.session_state.contador_rodadas % TREINAMENTO_INTERVALO == 0 and
        st.session_state.ia_recorrencia.precisa_treinar(st.session_state.estrategia.historico)):
        
        logging.info("🔄 Treinamento programado da IA")
        window_hist = list(st.session_state.estrategia.historico)[-WINDOW_SIZE:]
        sucesso_treinamento = st.session_state.ia_recorrencia.treinar(window_hist)
        if sucesso_treinamento:
            st.session_state.ultimo_treinamento_size = st.session_state.ia_recorrencia.ultimo_treinamento_size

    # Incrementa contador
    st.session_state.contador_rodadas += 1

    # Salvar métricas
    metrics = {
        "timestamp": resultado.get("timestamp"),
        "numero_real": numero_real,
        "acertos": st.session_state.get("acertos", 0),
        "erros": st.session_state.get("erros", 0),
        "acertos_topN": st.session_state.get("acertos_topN", 0),
        "erros_topN": st.session_state.get("erros_topN", 0),
        "acertos_31_34": st.session_state.get("acertos_31_34", 0),
        "erros_31_34": st.session_state.get("erros_31_34", 0),
        "anomalias_detectadas": st.session_state.get("anomalias_detectadas", [])  # NOVO
    }
    salvar_metricas(metrics)

# Exibir informação sobre duplicatas
if resultado and not novo_sorteio:
    st.info(f"⏳ Aguardando novo sorteio... Último processado: {st.session_state.ultimo_timestamp_processado}")

# Status do sistema
if st.session_state.aguardando_novo_sorteio:
    st.warning("🔄 Aguardando próximo sorteio para novos alertas...")

# -----------------------------
# Interface Streamlit Atualizada
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
ultimos = list(st.session_state.estrategia.historico)[-3:]
st.write(ultimos)

# NOVA SEÇÃO: Status do Autoencoder
st.subheader("🤖 Status do Autoencoder (Detecção de Padrões)")
col1, col2, col3 = st.columns(3)

# Status do autoencoder
autoencoder_status = "✅ Treinado" if st.session_state.pattern_analyzer.is_trained else "⏳ Aguardando dados"
col1.metric("🔍 Autoencoder", autoencoder_status)

# Anomalias detectadas
anomalias_count = len(st.session_state.anomalias_detectadas)
col2.metric("🎯 Anomalias Ativas", anomalias_count)

# Próxima análise
proxima_analise = 10 - (st.session_state.contador_rodadas % 10)
col3.metric("🔄 Próxima Análise", f"Rodada {proxima_analise}")

# Exibir anomalias se houver
if st.session_state.anomalias_detectadas:
    st.info(f"**🔍 Padrões Anômalos Detectados:** {', '.join(map(str, sorted(st.session_state.anomalias_detectadas)))}")
    st.caption("💡 Números com padrões incomuns que podem representar oportunidades")

# Estatísticas Recorrência
acertos = st.session_state.get("acertos", 0)
erros = st.session_state.get("erros", 0)
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0
qtd_previstos_rec = len(st.session_state.get("previsao", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN", acertos)
col2.metric("🔴 RED", erros)
col3.metric("✅ Taxa de acerto", f"{taxa:.1f}%")
col4.metric("🎯 Qtd. previstos Recorrência", qtd_previstos_rec)

# Estatísticas Top N Dinâmico
acertos_topN = st.session_state.get("acertos_topN", 0)
erros_topN = st.session_state.get("erros_topN", 0)
total_topN = acertos_topN + erros_topN
taxa_topN = (acertos_topN / total_topN * 100) if total_topN > 0 else 0.0
qtd_previstos_topN = len(st.session_state.get("previsao_topN", []))
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN Top N", acertos_topN)
col2.metric("🔴 RED Top N", erros_topN)
col3.metric("✅ Taxa Top N", f"{taxa_topN:.1f}%")
col4.metric("🎯 Qtd. previstos Top N", qtd_previstos_topN)

# Estatísticas 31/34
acertos_31_34 = st.session_state.get("acertos_31_34", 0)
erros_31_34 = st.session_state.get("erros_31_34", 0)
total_31_34 = acertos_31_34 + erros_31_34
taxa_31_34 = (acertos_31_34 / total_31_34 * 100) if total_31_34 > 0 else 0.0
qtd_previstos_31_34 = len(st.session_state.get("previsao_31_34", []))

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 GREEN 31/34", acertos_31_34)
col2.metric("🔴 RED 31/34", erros_31_34)
col3.metric("✅ Taxa 31/34", f"{taxa_31_34:.1f}%")
col4.metric("🎯 Qtd. previstos 31/34", qtd_previstos_31_34)

# Status da IA
st.subheader("🧠 Status da IA")
col1, col2, col3 = st.columns(3)
ultimo_treinamento = getattr(st.session_state.ia_recorrencia, 'ultimo_treinamento_size', 0)
col1.metric("🔄 Último Treinamento RF", f"{ultimo_treinamento} registros")
col2.metric("📊 Histórico Atual", f"{len(st.session_state.estrategia.historico)} registros")
proximo_treinamento = TREINAMENTO_INTERVALO - (st.session_state.contador_rodadas % TREINAMENTO_INTERVALO)
col3.metric("⚡ Próximo Treinamento", f"Rodada {proximo_treinamento}")

# Informações do Histórico
st.subheader("📊 Informações do Histórico")
st.write(f"Total de números armazenados no histórico: **{len(st.session_state.estrategia.historico)}**")
st.write(f"Capacidade máxima do deque: **{st.session_state.estrategia.historico.maxlen}**")

if st.session_state.ultimo_timestamp_processado:
    st.write(f"Último sorteio processado: **{st.session_state.ultimo_timestamp_processado}**")

# Seção de Download
st.markdown("---")
st.subheader("📥 Exportar Dados")

if st.button("💾 Download Histórico Completo", type="primary"):
    with st.spinner("Gerando arquivo de download..."):
        arquivo = gerar_download_historico()
        
        if arquivo:
            nome_arquivo = f"historico_roleta_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            st.download_button(
                label="⬇️ Baixar Arquivo Excel",
                data=arquivo,
                file_name=nome_arquivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Clique para baixar o histórico completo em formato Excel"
            )
            st.success("✅ Arquivo gerado com sucesso! Clique no botão acima para baixar.")
        else:
            st.error("❌ Erro ao gerar arquivo de download")

st.info("""
**📋 Conteúdo do arquivo:**
- **Historico_Completo**: Todos os números registrados
- **Estatisticas**: Métricas e análises do histórico  
- **Ultimos_100**: Últimos 100 registros para análise recente
""")
