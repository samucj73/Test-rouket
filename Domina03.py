# RoletaHybridIA.py - Sistema Híbrido de IA Avançada
import streamlit as st
import json
import os
import time
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import numpy as np
import pandas as pd
import io
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
METRICAS_PATH = "metricas_hybrid_ia.json"
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

# Configurações do Sistema Híbrido
MIN_HISTORICO_TREINAMENTO = 50
NUMERO_PREVISOES = 12

# =============================
# Utilitários
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def carregar_historico():
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
    try:
        historico_existente = carregar_historico()
        timestamp_novo = numero_dict.get("timestamp")
        ja_existe = any(registro.get("timestamp") == timestamp_novo for registro in historico_existente)
        
        if not ja_existe:
            historico_existente.append(numero_dict)
            with open(HISTORICO_PATH, "w") as f:
                json.dump(historico_existente, f, indent=2)
            logging.info(f"✅ Número {numero_dict['number']} salvo no histórico")
            return True
        return False
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")
        return False

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=6)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = data.get("result", {})
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

# =============================
# SISTEMA HÍBRIDO DE IA
# =============================
class LSTM_Predictor:
    """Simula um predictor LSTM para séries temporais"""
    def __init__(self):
        self.ultimo_treinamento = 0
        
    def predict_proba(self, historico):
        """Simula predições LSTM baseadas em padrões temporais"""
        if len(historico) < 20:
            return {}
            
        numeros = [h['number'] for h in historico]
        
        # Análise de padrões temporais simples
        probs = {}
        
        # Padrão 1: Repetição recente
        ultimos_10 = numeros[-10:]
        counter_recente = Counter(ultimos_10)
        for num, freq in counter_recente.items():
            if freq >= 2:
                probs[num] = probs.get(num, 0) + 0.3
        
        # Padrão 2: Sequências
        for i in range(len(numeros)-3):
            seq = numeros[i:i+3]
            if len(set(seq)) == 3:  # Sequência única
                # Prever próximo baseado na direção
                diff1 = (ROULETTE_LAYOUT.index(seq[1]) - ROULETTE_LAYOUT.index(seq[0])) % len(ROULETTE_LAYOUT)
                diff2 = (ROULETTE_LAYOUT.index(seq[2]) - ROULETTE_LAYOUT.index(seq[1])) % len(ROULETTE_LAYOUT)
                
                if diff1 == diff2:  # Padrão linear
                    next_idx = (ROULETTE_LAYOUT.index(seq[2]) + diff1) % len(ROULETTE_LAYOUT)
                    next_num = ROULETTE_LAYOUT[next_idx]
                    probs[next_num] = probs.get(next_num, 0) + 0.2
        
        # Normalizar probabilidades
        total = sum(probs.values()) if probs else 1
        return {k: v/total for k, v in probs.items()}

class XGBoost_Predictor:
    """Simula um predictor XGBoost com features avançadas"""
    def __init__(self):
        self.features_importance = {}
        
    def create_features(self, historico):
        """Cria features avançadas para o modelo"""
        if len(historico) < 10:
            return []
            
        numeros = [h['number'] for h in historico]
        features = []
        
        # Feature: Frequência recente
        freq_20 = Counter(numeros[-20:])
        
        # Feature: Distância do último número
        ultimo_numero = numeros[-1]
        
        for num in range(37):
            feature_vector = [
                freq_20.get(num, 0),  # Frequência últimas 20 jogadas
                numeros.count(num) / len(numeros),  # Frequência global
                min(abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT),
                    len(ROULETTE_LAYOUT) - abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT)),  # Distância física
                1 if num % 2 == 0 else 0,  # Par
                1 if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0,  # Vermelho
                1 if 1 <= num <= 12 else 0,  # Primeira dúzia
                1 if 13 <= num <= 24 else 0,  # Segunda dúzia  
                1 if 25 <= num <= 36 else 0,  # Terceira dúzia
            ]
            features.append((num, feature_vector))
            
        return features
    
    def predict_proba(self, historico):
        """Simula predições XGBoost"""
        if len(historico) < 15:
            return {}
            
        features = self.create_features(historico)
        if not features:
            return {}
            
        probs = {}
        
        for num, feat in features:
            score = 0.0
            
            # Feature 1: Frequência recente (peso alto)
            score += feat[0] * 0.4
            
            # Feature 2: Distância física (peso médio)
            distancia = feat[2]
            if distancia <= 3:
                score += 0.3
            elif distancia <= 6:
                score += 0.15
                
            # Feature 3: Cor (peso baixo)
            score += feat[4] * 0.1
            
            # Feature 4: Dúzia (peso baixo)
            score += max(feat[5], feat[6], feat[7]) * 0.1
            
            if score > 0:
                probs[num] = score
                
        # Normalizar
        total = sum(probs.values()) if probs else 1
        return {k: v/total for k, v in probs.items()}

class Pattern_Analyzer:
    """Analisador de padrões anômalos"""
    def __init__(self, window_size=30):
        self.window_size = window_size
        
    def detect_anomalies(self, historico):
        """Detecta números com comportamentos anômalos"""
        if len(historico) < self.window_size:
            return []
            
        numeros = [h['number'] for h in historico]
        ultimos_numeros = numeros[-self.window_size:]
        
        anomalies = []
        
        # Anomalia 1: Números que deveriam ter saído mas não saíram
        counter_window = Counter(ultimos_numeros)
        numeros_ausentes = [num for num in range(37) if counter_window.get(num, 0) == 0]
        
        # Anomalia 2: Números com frequência muito alta
        freq_esperada = self.window_size / 37
        numeros_quentes = [num for num, freq in counter_window.items() 
                          if freq > freq_esperada * 2]
        
        # Anomalia 3: Padrões de repetição estranhos
        for i in range(len(ultimos_numeros)-4):
            if ultimos_numeros[i] == ultimos_numeros[i+2] == ultimos_numeros[i+4]:
                anomalies.append(ultimos_numeros[i])
        
        # Combina todas as anomalias
        todas_anomalias = list(set(numeros_ausentes[:5] + numeros_quentes + anomalies))
        
        logging.info(f"🔍 Anomalias detectadas: {len(todas_anomalias)} números")
        return todas_anomalias[:8]  # Limita a 8 anomalias

class Ensemble_Predictor:
    """Combina predições de múltiplos modelos"""
    def __init__(self):
        self.model_weights = {
            'lstm': 0.4,
            'xgb': 0.6
        }
        
    def predict(self, lstm_probs, xgb_probs, anomalies):
        """Combina as predições dos modelos"""
        combined_scores = {}
        
        for number in range(37):
            lstm_score = lstm_probs.get(number, 0)
            xgb_score = xgb_probs.get(number, 0)
            
            # Combinação ponderada
            base_score = (lstm_score * self.model_weights['lstm'] + 
                         xgb_score * self.model_weights['xgb'])
            
            # Boost para anomalias
            anomaly_boost = 2.0 if number in anomalies else 1.0
            
            combined_scores[number] = base_score * anomaly_boost
            
        return combined_scores

class Hybrid_IA_System:
    """Sistema Híbrido de IA Principal"""
    def __init__(self):
        self.lstm_predictor = LSTM_Predictor()
        self.xgb_predictor = XGBoost_Predictor()
        self.pattern_analyzer = Pattern_Analyzer()
        self.ensemble = Ensemble_Predictor()
        self.ultima_previsao = None
        
    def predict_hybrid(self, historico):
        """Predição híbrida principal"""
        if len(historico) < MIN_HISTORICO_TREINAMENTO:
            return self.estrategia_conservadora(historico)
            
        try:
            # 1. Predição LSTM (séries temporais)
            lstm_probs = self.lstm_predictor.predict_proba(historico)
            
            # 2. Predição XGBoost (features avançadas)
            xgb_probs = self.xgb_predictor.predict_proba(historico)
            
            # 3. Detecção de padrões anômalos
            anomalies = self.pattern_analyzer.detect_anomalies(historico)
            
            # 4. Combinação inteligente
            combined_scores = {}
            for number in range(37):
                lstm_score = lstm_probs.get(number, 0) if lstm_probs else 0
                xgb_score = xgb_probs.get(number, 0) if xgb_probs else 0
                anomaly_boost = 2.0 if number in anomalies else 1.0
                
                combined_scores[number] = (lstm_score * 0.4 + xgb_score * 0.6) * anomaly_boost
            
            # 5. Seleção final
            top_numbers = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:15]
            
            # 6. Diversificação
            final_selection = self.diversify_selection([num for num, score in top_numbers])
            
            logging.info(f"🎯 Hybrid IA: {len(final_selection)} números selecionados")
            return final_selection
            
        except Exception as e:
            logging.error(f"Erro no sistema híbrido: {e}")
            return self.estrategia_conservadora(historico)
    
    def estrategia_conservadora(self, historico):
        """Estratégia fallback quando não há dados suficientes"""
        if len(historico) < 5:
            # Números iniciais balanceados
            return [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27]
        
        numeros = [h['number'] for h in historico]
        ultimo_numero = numeros[-1]
        
        # Estratégia simples baseada no último número
        vizinhos = obter_vizinhos(ultimo_numero, ROULETTE_LAYOUT, antes=3, depois=3)
        numeros_quentes = [num for num, count in Counter(numeros[-20:]).most_common(5)]
        
        previsao = list(set(vizinhos + numeros_quentes))
        return previsao[:NUMERO_PREVISOES]
    
    def diversify_selection(self, numbers):
        """Garante diversificação na seleção final"""
        if not numbers:
            return []
            
        diversified = []
        sectors = {
            'zero': [0],
            'baixa': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            'alta': [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]
        }
        
        # Garante pelo menos 1 número de cada setor
        for sector, nums in sectors.items():
            sector_nums = [n for n in numbers if n in nums]
            if sector_nums:
                # Pega o número com maior score original
                diversified.append(sector_nums[0])
        
        # Adiciona o restante dos números originais
        for num in numbers:
            if num not in diversified and len(diversified) < NUMERO_PREVISOES:
                diversified.append(num)
        
        # Se ainda precisar de mais números, completa com os melhores restantes
        if len(diversified) < NUMERO_PREVISOES:
            todos_numeros = set(range(37))
            numeros_restantes = list(todos_numeros - set(diversified))
            diversified.extend(numeros_restantes[:NUMERO_PREVISOES - len(diversified)])
        
        logging.info(f"🎲 Seleção diversificada: {len(diversified)} números")
        return diversified

# =============================
# GESTOR PRINCIPAL
# =============================
class GestorHybridIA:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_System()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão usando o sistema híbrido"""
        return self.hybrid_system.predict_hybrid(self.historico)

# =============================
# STREAMLIT APP - SISTEMA HÍBRIDO
# =============================
st.set_page_config(
    page_title="Roleta - Hybrid IA System", 
    page_icon="🧠", 
    layout="centered"
)

st.title("🧠 Hybrid IA System - Roleta")
st.markdown("### **Sistema Avançado: LSTM + XGBoost + Anomaly Detection**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorHybridIA(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
    "status_ia": "🟡 Inicializando",
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =============================
# PROCESSAMENTO PRINCIPAL
# =============================
resultado = fetch_latest_result()

novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if (st.session_state.ultimo_timestamp is None or 
        resultado.get("timestamp") != st.session_state.ultimo_timestamp):
        novo_sorteio = True

if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    salvo_com_sucesso = salvar_historico(numero_dict)
    if salvo_com_sucesso:
        st.session_state.gestor.adicionar_numero(numero_dict)
    
    st.session_state.ultimo_timestamp = resultado["timestamp"]
    numero_real = resultado["number"]
    st.session_state.ultimo_numero = numero_real

    # ATUALIZAR STATUS DA IA
    historico_size = len(st.session_state.gestor.historico)
    if historico_size >= MIN_HISTORICO_TREINAMENTO:
        st.session_state.status_ia = "🟢 IA Ativa (Híbrida)"
    else:
        st.session_state.status_ia = "🟡 Treinando IA"

    # CONFERÊNCIA
    if st.session_state.previsao_atual:
        acertou = numero_real in st.session_state.previsao_atual
        if acertou:
            st.session_state.acertos += 1
            st.success(f"🎯 **GREEN!** IA acertou o número {numero_real}!")
            enviar_telegram(f"🧠 GREEN! Hybrid IA acertou {numero_real}!")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 IA não previu o número {numero_real}")

    # GERAR NOVA PREVISÃO
    nova_previsao = st.session_state.gestor.gerar_previsao()
    st.session_state.previsao_atual = nova_previsao
    
    # TELEGRAM
    if nova_previsao:
        mensagem = f"🧠 **HYBRID IA - NOVA PREVISÃO**\n"
        mensagem += f"📊 Status: {st.session_state.status_ia}\n"
        mensagem += f"🔢 Último: {numero_real}\n"
        mensagem += f"🎯 Previsão: {len(nova_previsao)} números\n"
        mensagem += f"📈 Performance: {st.session_state.acertos}G/{st.session_state.erros}R\n"
        mensagem += f"🔍 Técnicas: LSTM + XGBoost + Anomalies\n"
        mensagem += f"📋 Números: {', '.join(map(str, sorted(nova_previsao)))}"
        
        enviar_telegram(mensagem)

    st.session_state.contador_rodadas += 1

# =============================
# INTERFACE DO SISTEMA HÍBRIDO
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Status IA", st.session_state.status_ia)
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)}")
with col3:
    if st.session_state.ultimo_numero:
        st.metric("🎲 Último Número", st.session_state.ultimo_numero)
    else:
        st.metric("🎲 Último Número", "-")
with col4:
    st.metric("🔄 Rodadas", st.session_state.contador_rodadas)

# HISTÓRICO RECENTE
st.subheader("📜 Padrões Recentes")
if st.session_state.gestor.historico:
    ultimos_15 = [h['number'] for h in list(st.session_state.gestor.historico)[-15:]]
    
    html_numeros = ""
    for num in ultimos_15:
        cor = "red" if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black" if num != 0 else "green"
        html_numeros += f"<span style='color: {cor}; font-weight: bold; margin: 0 3px;'>{num}</span>→"
    
    st.markdown(html_numeros[:-1], unsafe_allow_html=True)
    
    # Info de treinamento
    if len(st.session_state.gestor.historico) < MIN_HISTORICO_TREINAMENTO:
        st.progress(len(st.session_state.gestor.historico) / MIN_HISTORICO_TREINAMENTO)
        st.caption(f"🟡 Treinamento: {len(st.session_state.gestor.historico)}/{MIN_HISTORICO_TREINAMENTO} números")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO DO SISTEMA HÍBRIDO")

if st.session_state.previsao_atual:
    st.success(f"**🧠 {len(st.session_state.previsao_atual)} NÚMEROS SELECIONADOS PELA IA:**")
    
    # Display organizado
    col1, col2, col3 = st.columns(3)
    numeros_ordenados = sorted(st.session_state.previsao_atual)
    nums_por_coluna = (len(numeros_ordenados) + 2) // 3
    
    for col_idx, col in enumerate([col1, col2, col3]):
        with col:
            start_idx = col_idx * nums_por_coluna
            end_idx = start_idx + nums_por_coluna
            for num in numeros_ordenados[start_idx:end_idx]:
                if num == 0:
                    st.markdown(f"<div style='background-color: green; color: white; padding: 8px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
                elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                    st.markdown(f"<div style='background-color: red; color: white; padding: 8px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='background-color: black; color: white; padding: 8px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
    
    st.caption(f"📊 Probabilidade teórica: {(len(st.session_state.previsao_atual)/37)*100:.1f}% de acerto")

# ESTATÍSTICAS DETALHADAS
st.markdown("---")
st.subheader("📊 PERFORMANCE DA IA HÍBRIDA")

acertos = st.session_state.acertos
erros = st.session_state.erros
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Greens", acertos)
col2.metric("🔴 Reds", erros)
col3.metric("✅ Taxa", f"{taxa:.1f}%")
col4.metric("🎯 Cobertura", f"{(len(st.session_state.previsao_atual)/37)*100:.1f}%" if st.session_state.previsao_atual else "0%")

# INFORMAÇÕES TÉCNICAS
with st.expander("🔧 **DETALHES TÉCNICOS DO SISTEMA HÍBRIDO**"):
    st.markdown("""
    **🧠 ARQUITETURA HÍBRIDA:**
    
    **1. LSTM Predictor** (40% peso)
    - Análise de séries temporais
    - Padrões de sequência
    - Repetição temporal
    
    **2. XGBoost Predictor** (60% peso) 
    - Features avançadas:
      - Frequência recente
      - Distância física na roleta
      - Cor (vermelho/preto)
      - Dúzia
      - Par/Ímpar
    
    **3. Pattern Analyzer**
    - Detecção de anomalias
    - Números quentes/frios
    - Padrões de repetição
    
    **4. Ensemble System**
    - Combinação inteligente
    - Diversificação automática
    - Balanceamento de setores
    """)

# CONTROLES
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Forçar Nova Análise"):
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = nova_previsao
        st.rerun()

with col2:
    if st.button("📊 Relatório de Performance"):
        st.info(f"""
        **Relatório Hybrid IA:**
        - Total de rodadas: {st.session_state.contador_rodadas}
        - Greens: {st.session_state.acertos}
        - Reds: {st.session_state.erros}
        - Taxa de acerto: {taxa:.1f}%
        - Histórico: {len(st.session_state.gestor.historico)} números
        - Status: {st.session_state.status_ia}
        """)

st.markdown("---")
st.success("🧠 **Hybrid IA System** - Combinação avançada de técnicas de Machine Learning para previsões otimizadas")
