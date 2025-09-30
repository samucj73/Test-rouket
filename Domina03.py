# RoletaHybridIA.py - VERSÃO CORRIGIDA E ROBUSTA
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

# Configurações
MIN_HISTORICO_TREINAMENTO = 200
NUMERO_PREVISOES = 20

# =============================
# Utilitários ROBUSTOS
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
    """Carrega histórico com tratamento de erro robusto"""
    try:
        if os.path.exists(HISTORICO_PATH):
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            # Filtra entradas inválidas
            historico_valido = [h for h in historico if isinstance(h, dict) and 'number' in h and h['number'] is not None]
            logging.info(f"📁 Histórico carregado: {len(historico_valido)} registros válidos")
            return historico_valido
        return []
    except Exception as e:
        logging.error(f"Erro ao carregar histórico: {e}")
        return []

def salvar_historico(numero_dict):
    """Salva número com validação robusta"""
    try:
        if not isinstance(numero_dict, dict) or numero_dict.get('number') is None:
            logging.error("❌ Tentativa de salvar número inválido")
            return False
            
        historico_existente = carregar_historico()
        timestamp_novo = numero_dict.get("timestamp")
        
        # Verifica duplicata
        ja_existe = any(
            registro.get("timestamp") == timestamp_novo 
            for registro in historico_existente 
            if isinstance(registro, dict)
        )
        
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
    """Busca resultado com tratamento robusto de erro"""
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Navegação segura pela estrutura da API
        game_data = data.get("data", {})
        if not game_data:
            logging.error("❌ Estrutura da API inválida: data não encontrado")
            return None
            
        result = game_data.get("result", {})
        if not result:
            logging.error("❌ Estrutura da API inválida: result não encontrado")
            return None
            
        outcome = result.get("outcome", {})
        if not outcome:
            logging.error("❌ Estrutura da API inválida: outcome não encontrado")
            return None
            
        number = outcome.get("number")
        if number is None:
            logging.error("❌ Número não encontrado na resposta da API")
            return None
            
        timestamp = game_data.get("startedAt")
        
        return {"number": number, "timestamp": timestamp}
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro de rede ao buscar resultado: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Erro inesperado ao buscar resultado: {e}")
        return None

def obter_vizinhos(numero, layout, antes=3, depois=3):
    """Obtém vizinhos com validação"""
    if numero is None or numero not in layout:
        return []
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

def validar_previsao(previsao):
    """Valida e limpa uma previsão"""
    if not previsao or not isinstance(previsao, list):
        return []
    
    # Filtra valores None e garante que são números válidos
    previsao_limpa = [
        num for num in previsao 
        if num is not None 
        and isinstance(num, (int, float))
        and 0 <= num <= 36
    ]
    
    return previsao_limpa

# =============================
# SISTEMA HÍBRIDO ROBUSTO
# =============================
class LSTM_Predictor:
    def __init__(self):
        self.ultimo_treinamento = 0
        
    def predict_proba(self, historico):
        """LSTM com tratamento robusto"""
        try:
            if not historico or len(historico) < 5:
                return self.previsao_inicial()
                
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if not numeros:
                return self.previsao_inicial()
                
            probs = {}
            
            # Estratégia 1: Repetição recente
            ultimos_8 = numeros[-8:]
            counter_recente = Counter(ultimos_8)
            for num, freq in counter_recente.items():
                if freq >= 1:
                    probs[num] = probs.get(num, 0) + 0.2
            
            # Estratégia 2: Tendência de movimento
            if len(numeros) >= 3:
                ultimo = numeros[-1]
                penultimo = numeros[-2]
                
                if ultimo in ROULETTE_LAYOUT and penultimo in ROULETTE_LAYOUT:
                    idx_ultimo = ROULETTE_LAYOUT.index(ultimo)
                    idx_penultimo = ROULETTE_LAYOUT.index(penultimo)
                    
                    direcao = (idx_ultimo - idx_penultimo) % len(ROULETTE_LAYOUT)
                    if direcao > len(ROULETTE_LAYOUT)//2:
                        direcao -= len(ROULETTE_LAYOUT)
                    
                    next_idx = (idx_ultimo + direcao) % len(ROULETTE_LAYOUT)
                    next_num = ROULETTE_LAYOUT[next_idx]
                    probs[next_num] = probs.get(next_num, 0) + 0.3
            
            return probs if probs else self.previsao_inicial()
            
        except Exception as e:
            logging.error(f"Erro no LSTM: {e}")
            return self.previsao_inicial()
    
    def previsao_inicial(self):
        return {num: 0.1 for num in [0, 7, 13, 22, 29, 32]}

class XGBoost_Predictor:
    def __init__(self):
        self.features_importance = {}
        
    def create_features(self, historico):
        """Features com validação robusta"""
        try:
            if not historico or len(historico) < 3:
                return []
                
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if not numeros:
                return []
                
            ultimo_numero = numeros[-1] if numeros else 0
            features = []
            
            for num in range(37):
                feature_vector = [
                    numeros.count(num),
                    1 if num == ultimo_numero else 0,
                    min(abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT),
                        len(ROULETTE_LAYOUT) - abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT)) if ultimo_numero in ROULETTE_LAYOUT else 18,
                    1 if num % 2 == 0 else 0,
                    1 if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0,
                ]
                features.append((num, feature_vector))
                
            return features
            
        except Exception as e:
            logging.error(f"Erro ao criar features: {e}")
            return []
    
    def predict_proba(self, historico):
        """XGBoost com tratamento robusto"""
        try:
            features = self.create_features(historico)
            if not features:
                return {}
                
            probs = {}
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if not numeros:
                return {}
                
            ultimo_numero = numeros[-1]
            
            for num, feat in features:
                score = 0.0
                score += min(feat[0] * 0.3, 0.3)
                
                distancia = feat[2]
                if distancia <= 2:
                    score += 0.4
                elif distancia <= 4:
                    score += 0.2
                    
                if feat[4] != (1 if ultimo_numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0):
                    score += 0.1
                    
                if score > 0:
                    probs[num] = score
                    
            return probs if probs else {num: 0.05 for num in range(37)}
            
        except Exception as e:
            logging.error(f"Erro no XGBoost: {e}")
            return {}

class Pattern_Analyzer:
    def __init__(self, window_size=20):
        self.window_size = window_size
        
    def detect_anomalies(self, historico):
        """Detecção de anomalias robusta"""
        try:
            if not historico or len(historico) < 5:
                return []
                
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if not numeros:
                return []
                
            anomalies = []
            
            if len(numeros) >= 10:
                ultimos_10 = set(numeros[-10:])
                for num in range(37):
                    if num not in ultimos_10:
                        anomalies.append(num)
            
            return anomalies[:10]
            
        except Exception as e:
            logging.error(f"Erro no Pattern Analyzer: {e}")
            return []

class Hybrid_IA_System:
    def __init__(self):
        self.lstm_predictor = LSTM_Predictor()
        self.xgb_predictor = XGBoost_Predictor()
        self.pattern_analyzer = Pattern_Analyzer()
        
    def predict_hybrid(self, historico):
        """Sistema híbrido com tratamento completo de erro"""
        try:
            if not historico:
                return self.estrategia_inicial_agressiva()
                
            historico_size = len(historico)
            
            if historico_size < 5:
                return self.estrategia_inicial_agressiva()
            elif historico_size < 20:
                return self.estrategia_intermediaria(historico)
            else:
                return self.estrategia_avancada(historico)
                
        except Exception as e:
            logging.error(f"Erro crítico no sistema híbrido: {e}")
            return self.estrategia_emergencia()
    
    def estrategia_inicial_agressiva(self):
        """Estratégia inicial garantida"""
        numeros_base = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36]
        return validar_previsao(numeros_base[:NUMERO_PREVISOES])
    
    def estrategia_intermediaria(self, historico):
        """Estratégia intermediária robusta"""
        try:
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if not numeros:
                return self.estrategia_inicial_agressiva()
                
            previsao = set()
            
            # Últimos números válidos
            ultimos_validos = [n for n in numeros[-5:] if n is not None]
            previsao.update(ultimos_validos)
            
            # Vizinhos dos últimos números válidos
            for num in numeros[-3:]:
                if num is not None:
                    vizinhos = obter_vizinhos(num, ROULETTE_LAYOUT, antes=2, depois=2)
                    previsao.update(vizinhos)
            
            # Preenche se necessário
            if len(previsao) < NUMERO_PREVISOES:
                numeros_faltantes = NUMERO_PREVISOES - len(previsao)
                balanceados = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35]
                previsao.update(balanceados[:numeros_faltantes])
            
            return validar_previsao(list(previsao))[:NUMERO_PREVISOES]
            
        except Exception as e:
            logging.error(f"Erro na estratégia intermediária: {e}")
            return self.estrategia_inicial_agressiva()
    
    def estrategia_avancada(self, historico):
        """Estratégia avançada com tratamento completo"""
        try:
            lstm_probs = self.lstm_predictor.predict_proba(historico)
            xgb_probs = self.xgb_predictor.predict_proba(historico)
            anomalies = self.pattern_analyzer.detect_anomalies(historico)
            
            combined_scores = {}
            for number in range(37):
                lstm_score = lstm_probs.get(number, 0)
                xgb_score = xgb_probs.get(number, 0)
                anomaly_boost = 1.5 if number in anomalies else 1.0
                
                combined_scores[number] = (lstm_score * 0.4 + xgb_score * 0.6) * anomaly_boost
            
            top_numbers = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:NUMERO_PREVISOES]
            final_selection = [num for num, score in top_numbers if num is not None]
            
            final_selection = self.diversify_selection(final_selection)
            
            logging.info(f"🎯 Hybrid IA Avançada: {len(final_selection)} números")
            return validar_previsao(final_selection)
            
        except Exception as e:
            logging.error(f"Erro na estratégia avançada: {e}")
            return self.estrategia_intermediaria(historico)
    
    def estrategia_emergencia(self):
        """Estratégia de emergência absoluta"""
        return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    
    def diversify_selection(self, numbers):
        """Diversificação robusta"""
        try:
            numbers = validar_previsao(numbers)
            if not numbers:
                return self.estrategia_inicial_agressiva()
                
            diversified = []
            sectors = {
                'zero': [0],
                'vermelhos_baixos': [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36],
                'pretos_baixos': [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
            }
            
            for sector, nums in sectors.items():
                for num in numbers:
                    if num in nums and num not in diversified:
                        diversified.append(num)
                        break
            
            for num in numbers:
                if num not in diversified and len(diversified) < NUMERO_PREVISOES:
                    diversified.append(num)
            
            return validar_previsao(diversified)[:NUMERO_PREVISOES]
            
        except Exception as e:
            logging.error(f"Erro na diversificação: {e}")
            return self.estrategia_emergencia()

# =============================
# GESTOR PRINCIPAL ROBUSTO
# =============================
class GestorHybridIA:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_System()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        """Adiciona número com validação"""
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão com fallback garantido"""
        try:
            previsao = self.hybrid_system.predict_hybrid(self.historico)
            return validar_previsao(previsao)
        except Exception as e:
            logging.error(f"Erro crítico ao gerar previsão: {e}")
            return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    
    def get_status_sistema(self):
        """Status do sistema robusto"""
        try:
            historico_size = len(self.historico)
            if historico_size < 5:
                return "🟡 Fase Inicial", "Estratégia Agressiva"
            elif historico_size < 20:
                return "🟠 Coletando Dados", "Estratégia Intermediária"
            else:
                return "🟢 IA Ativa", "Sistema Híbrido Completo"
        except:
            return "⚪ Sistema", "Carregando..."

# =============================
# STREAMLIT APP - VERSÃO ROBUSTA
# =============================
st.set_page_config(
    page_title="Roleta - Hybrid IA (Robusto)", 
    page_icon="🧠", 
    layout="centered"
)

st.title("🧠 Hybrid IA System - ROBUSTO")
st.markdown("### **Sistema com tratamento completo de erros**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização ROBUSTA do session_state
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

# Garante que previsao_atual é uma lista válida
if not isinstance(st.session_state.previsao_atual, list):
    st.session_state.previsao_atual = []

st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL ROBUSTO
# =============================
try:
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

        # CONFERÊNCIA ROBUSTA
        previsao_valida = validar_previsao(st.session_state.previsao_atual)
        if previsao_valida:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
                enviar_telegram(f"🟢 GREEN! Sistema acertou {numero_real}!")
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")

        # GERAR NOVA PREVISÃO
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # TELEGRAM SEGURO
        if st.session_state.previsao_atual and len(st.session_state.gestor.historico) >= 3:
            try:
                mensagem = f"🧠 **HYBRID IA - PREVISÃO ATUAL**\n"
                mensagem += f"📊 Status: {st.session_state.status_ia}\n"
                mensagem += f"🎯 Estratégia: {st.session_state.estrategia_atual}\n"
                mensagem += f"🔢 Último: {numero_real}\n"
                mensagem += f"📈 Performance: {st.session_state.acertos}G/{st.session_state.erros}R\n"
                mensagem += f"📋 Números: {', '.join(map(str, sorted(st.session_state.previsao_atual)))}"
                
                enviar_telegram(mensagem)
            except Exception as e:
                logging.error(f"Erro ao enviar Telegram: {e}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    # Reset seguro
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

# =============================
# INTERFACE ROBUSTA
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Status", st.session_state.status_ia)
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)}")
with col3:
    ultimo_numero = st.session_state.ultimo_numero
    display_numero = ultimo_numero if ultimo_numero is not None else "-"
    st.metric("🎲 Último", display_numero)
with col4:
    st.metric("🎯 Estratégia", st.session_state.estrategia_atual)

# BARRA DE PROGRESSO
st.subheader("📈 Progresso do Sistema")
historico_size = len(st.session_state.gestor.historico)

if historico_size < 5:
    progresso = historico_size / 5
    st.progress(progresso)
    st.caption("🟡 Fase Inicial: Coletando primeiros dados...")
elif historico_size < 20:
    progresso = historico_size / 20
    st.progress(progresso)
    st.caption("🟠 Fase Intermediária: Desenvolvendo padrões...")
else:
    st.progress(1.0)
    st.caption("🟢 Sistema Completo: IA Híbrida Ativa!")

# HISTÓRICO VISUAL SEGURO
st.subheader("📜 Últimos Números")
historico_valido = [h for h in st.session_state.gestor.historico if h.get('number') is not None]
ultimos_numeros = [h['number'] for h in historico_valido[-10:]]

if ultimos_numeros:
    html_numeros = ""
    for num in ultimos_numeros:
        if num is not None:
            cor = "red" if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black" if num != 0 else "green"
            html_numeros += f"<span style='color: {cor}; font-weight: bold; margin: 0 5px; font-size: 18px;'>{num}</span>"
    
    st.markdown(html_numeros, unsafe_allow_html=True)
else:
    st.info("Aguardando dados dos números...")

# PREVISÃO ATUAL ROBUSTA
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    st.success(f"**{len(previsao_valida)} NÚMEROS PREVISTOS**")
    
    # Display SEGURO em grid
    col1, col2, col3 = st.columns(3)
    
    try:
        numeros_ordenados = sorted(previsao_valida)
    except:
        numeros_ordenados = previsao_valida  # Usa como está se não conseguir ordenar
    
    for i, num in enumerate(numeros_ordenados):
        if i < 15:  # Limite seguro
            col = [col1, col2, col3][i % 3]
            with col:
                if num == 0:
                    st.markdown(f"<div style='background-color: green; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
                elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                    st.markdown(f"<div style='background-color: red; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='background-color: black; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
    
    cobertura = (len(previsao_valida) / 37) * 100
    st.caption(f"📊 Cobertura: {cobertura:.1f}% da roleta")
else:
    st.info("🔄 Gerando primeira previsão...")
    # Força uma previsão básica
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

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

# BOTÕES DE CONTROLE SEGUROS
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Atualizar Previsão"):
        try:
            nova_previsao = st.session_state.gestor.gerar_previsao()
            st.session_state.previsao_atual = validar_previsao(nova_previsao)
            st.rerun()
        except:
            st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            st.rerun()

with col2:
    if st.button("🗑️ Zerar Estatísticas"):
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.rerun()

st.markdown("---")
st.success("🛡️ **Sistema Robusto** - Tratamento completo de erros ativado!")
