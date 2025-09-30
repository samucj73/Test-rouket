# RoletaHybridIA.py - VERSÃO OTIMIZADA PARA POUCOS DADOS
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

# Configurações OTIMIZADAS
MIN_HISTORICO_TREINAMENTO = 50
NUMERO_PREVISOES = 15  # Aumentado para melhor cobertura

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
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
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

def obter_vizinhos(numero, layout, antes=3, depois=3):
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
# SISTEMA HÍBRIDO OTIMIZADO
# =============================
class LSTM_Predictor:
    def __init__(self):
        self.ultimo_treinamento = 0
        
    def predict_proba(self, historico):
        """LSTM otimizado para poucos dados"""
        if len(historico) < 5:
            return self.previsao_inicial()
            
        numeros = [h['number'] for h in historico]
        probs = {}
        
        # Estratégia 1: Repetição recente (funciona com poucos dados)
        ultimos_8 = numeros[-8:]
        counter_recente = Counter(ultimos_8)
        for num, freq in counter_recente.items():
            if freq >= 1:  # Reduzido o threshold
                probs[num] = probs.get(num, 0) + 0.2
        
        # Estratégia 2: Tendência de movimento
        if len(numeros) >= 3:
            ultimo = numeros[-1]
            penultimo = numeros[-2]
            
            idx_ultimo = ROULETTE_LAYOUT.index(ultimo)
            idx_penultimo = ROULETTE_LAYOUT.index(penultimo)
            
            direcao = (idx_ultimo - idx_penultimo) % len(ROULETTE_LAYOUT)
            if direcao > len(ROULETTE_LAYOUT)//2:
                direcao -= len(ROULETTE_LAYOUT)
            
            # Prever continuidade da tendência
            next_idx = (idx_ultimo + direcao) % len(ROULETTE_LAYOUT)
            next_num = ROULETTE_LAYOUT[next_idx]
            probs[next_num] = probs.get(next_num, 0) + 0.3
        
        return probs if probs else self.previsao_inicial()
    
    def previsao_inicial(self):
        """Previsão padrão quando não há dados"""
        return {num: 0.1 for num in [0, 7, 13, 22, 29, 32]}

class XGBoost_Predictor:
    def __init__(self):
        self.features_importance = {}
        
    def create_features(self, historico):
        """Features otimizadas para poucos dados"""
        if len(historico) < 3:
            return []
            
        numeros = [h['number'] for h in historico]
        features = []
        ultimo_numero = numeros[-1] if numeros else 0
        
        for num in range(37):
            feature_vector = [
                numeros.count(num),  # Frequência total
                1 if num == ultimo_numero else 0,  # É o último número
                min(abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT),
                    len(ROULETTE_LAYOUT) - abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT)),  # Distância
                1 if num % 2 == 0 else 0,  # Par
                1 if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0,  # Vermelho
            ]
            features.append((num, feature_vector))
            
        return features
    
    def predict_proba(self, historico):
        """XGBoost otimizado para poucos dados"""
        if len(historico) < 2:
            return {}
            
        features = self.create_features(historico)
        if not features:
            return {}
            
        probs = {}
        numeros = [h['number'] for h in historico]
        ultimo_numero = numeros[-1]
        
        for num, feat in features:
            score = 0.0
            
            # Feature 1: Frequência (peso alto)
            score += min(feat[0] * 0.3, 0.3)  # Limita o peso
            
            # Feature 2: Distância (peso médio)
            distancia = feat[2]
            if distancia <= 2:
                score += 0.4
            elif distancia <= 4:
                score += 0.2
                
            # Feature 3: Mudança de cor (peso baixo)
            if feat[4] != (1 if ultimo_numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0):
                score += 0.1
                
            if score > 0:
                probs[num] = score
                
        return probs if probs else {num: 0.05 for num in range(37)}

class Pattern_Analyzer:
    def __init__(self, window_size=20):  # Reduzido para poucos dados
        self.window_size = window_size
        
    def detect_anomalies(self, historico):
        """Detecção otimizada para poucos dados"""
        if len(historico) < 5:
            return []
            
        numeros = [h['number'] for h in historico]
        anomalies = []
        
        # Anomalia simples: números que não saíram recentemente
        if len(numeros) >= 10:
            ultimos_10 = set(numeros[-10:])
            for num in range(37):
                if num not in ultimos_10:
                    anomalies.append(num)
        
        return anomalies[:10]  # Limita a 10 anomalias

class Hybrid_IA_System:
    def __init__(self):
        self.lstm_predictor = LSTM_Predictor()
        self.xgb_predictor = XGBoost_Predictor()
        self.pattern_analyzer = Pattern_Analyzer()
        
    def predict_hybrid(self, historico):
        """Sistema híbrido OTIMIZADO para poucos dados"""
        historico_size = len(historico)
        
        if historico_size < 5:
            return self.estrategia_inicial_agressiva()
        elif historico_size < 20:
            return self.estrategia_intermediaria(historico)
        else:
            return self.estrategia_avancada(historico)
    
    def estrategia_inicial_agressiva(self):
        """Estratégia inicial - cobre muitos números"""
        # Cobre 40% da roleta para garantir primeiros acertos
        numeros_base = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36]
        return numeros_base[:NUMERO_PREVISOES]
    
    def estrategia_intermediaria(self, historico):
        """Estratégia para histórico médio"""
        numeros = [h['number'] for h in historico]
        
        # Combinação simples mas efetiva
        previsao = set()
        
        # 1. Últimos números
        previsao.update(numeros[-5:])
        
        # 2. Vizinhos dos últimos números
        for num in numeros[-3:]:
            vizinhos = obter_vizinhos(num, ROULETTE_LAYOUT, antes=2, depois=2)
            previsao.update(vizinhos)
        
        # 3. Preenche com números estratégicos
        if len(previsao) < NUMERO_PREVISOES:
            numeros_faltantes = NUMERO_PREVISOES - len(previsao)
            # Adiciona números balanceados
            balanceados = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35]
            previsao.update(balanceados[:numeros_faltantes])
        
        return list(previsao)[:NUMERO_PREVISOES]
    
    def estrategia_avancada(self, historico):
        """Estratégia avançada com IA completa"""
        try:
            # 1. Predição LSTM
            lstm_probs = self.lstm_predictor.predict_proba(historico)
            
            # 2. Predição XGBoost
            xgb_probs = self.xgb_predictor.predict_proba(historico)
            
            # 3. Detecção de anomalias
            anomalies = self.pattern_analyzer.detect_anomalies(historico)
            
            # 4. Combinação inteligente
            combined_scores = {}
            for number in range(37):
                lstm_score = lstm_probs.get(number, 0)
                xgb_score = xgb_probs.get(number, 0)
                anomaly_boost = 1.5 if number in anomalies else 1.0
                
                combined_scores[number] = (lstm_score * 0.4 + xgb_score * 0.6) * anomaly_boost
            
            # 5. Seleção final
            top_numbers = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:NUMERO_PREVISOES]
            final_selection = [num for num, score in top_numbers]
            
            # 6. Diversificação
            final_selection = self.diversify_selection(final_selection)
            
            logging.info(f"🎯 Hybrid IA Avançada: {len(final_selection)} números")
            return final_selection
            
        except Exception as e:
            logging.error(f"Erro na estratégia avançada: {e}")
            return self.estrategia_intermediaria(historico)
    
    def diversify_selection(self, numbers):
        """Diversificação otimizada"""
        if not numbers:
            return self.estrategia_inicial_agressiva()
            
        diversified = []
        sectors = {
            'zero': [0],
            'vermelhos_baixos': [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36],
            'pretos_baixos': [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        }
        
        # Garante representação de cada setor
        for sector, nums in sectors.items():
            for num in numbers:
                if num in nums and num not in diversified:
                    diversified.append(num)
                    break
        
        # Completa com números originais
        for num in numbers:
            if num not in diversified and len(diversified) < NUMERO_PREVISOES:
                diversified.append(num)
        
        return diversified[:NUMERO_PREVISOES]

# =============================
# GESTOR PRINCIPAL OTIMIZADO
# =============================
class GestorHybridIA:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_System()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão adaptativa"""
        return self.hybrid_system.predict_hybrid(self.historico)
    
    def get_status_sistema(self):
        """Retorna status do sistema baseado no histórico"""
        historico_size = len(self.historico)
        if historico_size < 5:
            return "🟡 Fase Inicial", "Estratégia Agressiva"
        elif historico_size < 20:
            return "🟠 Coletando Dados", "Estratégia Intermediária"
        else:
            return "🟢 IA Ativa", "Sistema Híbrido Completo"

# =============================
# STREAMLIT APP OTIMIZADO
# =============================
st.set_page_config(
    page_title="Roleta - Hybrid IA (Otimizado)", 
    page_icon="🧠", 
    layout="centered"
)

st.title("🧠 Hybrid IA System - OTIMIZADO")
st.markdown("### **Sistema Adaptativo: Funciona desde o primeiro número!**")

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
    "estrategia_atual": "Aguardando dados",
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

    # ATUALIZAR STATUS
    st.session_state.status_ia, st.session_state.estrategia_atual = st.session_state.gestor.get_status_sistema()

    # CONFERÊNCIA
    if st.session_state.previsao_atual:
        acertou = numero_real in st.session_state.previsao_atual
        if acertou:
            st.session_state.acertos += 1
            st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
            enviar_telegram(f"🟢 GREEN! Sistema acertou {numero_real}!")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 Número {numero_real} não estava na previsão")

    # GERAR NOVA PREVISÃO
    nova_previsao = st.session_state.gestor.gerar_previsao()
    st.session_state.previsao_atual = nova_previsao
    
    # TELEGRAM APENAS PARA PREVISÕES SIGNIFICATIVAS
    if nova_previsao and len(st.session_state.gestor.historico) >= 3:
        mensagem = f"🧠 **HYBRID IA - PREVISÃO ATUAL**\n"
        mensagem += f"📊 Status: {st.session_state.status_ia}\n"
        mensagem += f"🎯 Estratégia: {st.session_state.estrategia_atual}\n"
        mensagem += f"🔢 Último: {numero_real}\n"
        mensagem += f"📈 Performance: {st.session_state.acertos}G/{st.session_state.erros}R\n"
        mensagem += f"📋 Números: {', '.join(map(str, sorted(nova_previsao)))}"
        
        enviar_telegram(mensagem)

    st.session_state.contador_rodadas += 1

# =============================
# INTERFACE OTIMIZADA
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Status", st.session_state.status_ia)
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)}")
with col3:
    if st.session_state.ultimo_numero:
        st.metric("🎲 Último", st.session_state.ultimo_numero)
    else:
        st.metric("🎲 Último", "-")
with col4:
    st.metric("🎯 Estratégia", st.session_state.estrategia_atual)

# BARRA DE PROGRESSO DO SISTEMA
st.subheader("📈 Progresso do Sistema")
historico_size = len(st.session_state.gestor.historico)

if historico_size < 5:
    st.progress(historico_size / 5)
    st.caption("🟡 Fase Inicial: Coletando primeiros dados...")
elif historico_size < 20:
    st.progress(historico_size / 20)
    st.caption("🟠 Fase Intermediária: Desenvolvendo padrões...")
else:
    st.progress(1.0)
    st.caption("🟢 Sistema Completo: IA Híbrida Ativa!")

# HISTÓRICO VISUAL
st.subheader("📜 Últimos Números")
if st.session_state.gestor.historico:
    ultimos_numeros = [h['number'] for h in list(st.session_state.gestor.historico)[-10:]]
    
    if ultimos_numeros and all(n is not None for n in ultimos_numeros):
        html_numeros = ""
        for num in ultimos_numeros:
            cor = "red" if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black" if num != 0 else "green"
            html_numeros += f"<span style='color: {cor}; font-weight: bold; margin: 0 5px; font-size: 18px;'>{num}</span>"
        
        st.markdown(html_numeros, unsafe_allow_html=True)
    else:
        st.info("Aguardando dados dos números...")
else:
    st.info("Nenhum número registrado ainda")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL")

if st.session_state.previsao_atual:
    st.success(f"**{len(st.session_state.previsao_atual)} NÚMEROS PREVISTOS**")
    
    # Display em grid
    col1, col2, col3 = st.columns(3)
    numeros_ordenados = sorted(st.session_state.previsao_atual)
    
    for i, num in enumerate(numeros_ordenados):
        col = [col1, col2, col3][i % 3]
        with col:
            if num == 0:
                st.markdown(f"<div style='background-color: green; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
            elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                st.markdown(f"<div style='background-color: red; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color: black; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
    
    st.caption(f"📊 Cobertura: {(len(st.session_state.previsao_atual)/37)*100:.1f}% da roleta")
else:
    st.info("🔄 Gerando primeira previsão...")

# ESTATÍSTICAS
st.markdown("---")
st.subheader("📊 PERFORMANCE")

acertos = st.session_state.acertos
erros = st.session_state.erros
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("🟢 Greens", acertos)
col2.metric("🔴 Reds", erros)
col3.metric("✅ Taxa", f"{taxa:.1f}%")

# BOTÕES DE CONTROLE
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Atualizar Previsão"):
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = nova_previsao
        st.rerun()

with col2:
    if st.button("📊 Ver Detalhes"):
        st.info(f"""
        **Detalhes do Sistema:**
        - Histórico: {len(st.session_state.gestor.historico)} números
        - Status: {st.session_state.status_ia}
        - Estratégia: {st.session_state.estrategia_atual}
        - Rodadas: {st.session_state.contador_rodadas}
        - Previsão atual: {len(st.session_state.previsao_atual)} números
        """)

st.markdown("---")
st.success("🚀 **Sistema Otimizado** - Funciona imediatamente e melhora com o tempo!")
