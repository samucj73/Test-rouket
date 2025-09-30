# RoletaHybridIA.py - SISTEMA COMPLETO ATUALIZADO
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
MIN_HISTORICO_TREINAMENTO = 50
NUMERO_PREVISOES = 15

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
    try:
        if os.path.exists(HISTORICO_PATH):
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            historico_valido = [h for h in historico if isinstance(h, dict) and 'number' in h and h['number'] is not None]
            logging.info(f"📁 Histórico carregado: {len(historico_valido)} registros válidos")
            return historico_valido
        return []
    except Exception as e:
        logging.error(f"Erro ao carregar histórico: {e}")
        return []

def salvar_historico(numero_dict):
    try:
        if not isinstance(numero_dict, dict) or numero_dict.get('number') is None:
            logging.error("❌ Tentativa de salvar número inválido")
            return False
            
        historico_existente = carregar_historico()
        timestamp_novo = numero_dict.get("timestamp")
        
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
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
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
    if not previsao or not isinstance(previsao, list):
        return []
    
    previsao_limpa = [
        num for num in previsao 
        if num is not None 
        and isinstance(num, (int, float))
        and 0 <= num <= 36
    ]
    
    return previsao_limpa

# =============================
# SISTEMA HÍBRIDO ATUALIZADO
# =============================
class Pattern_Analyzer_Atualizado:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.ultimo_padrao_detectado = None
        
    def detectar_mudanca_padrao(self, historico):
        """Detecta mudanças bruscas nos padrões da roleta"""
        try:
            if len(historico) < 40:
                return False
                
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if len(numeros) < 40:
                return False
            
            # Últimos 20 números vs 20 números anteriores
            ultimos_20 = numeros[-20:]
            anteriores_20 = numeros[-40:-20]
            
            # Calcula estatísticas comparativas
            media_ultimos = np.mean(ultimos_20)
            media_anteriores = np.mean(anteriores_20)
            
            std_ultimos = np.std(ultimos_20)
            std_anteriores = np.std(anteriores_20)
            
            # Análise de distribuição por setores
            def analisar_setores(numeros_lista):
                setores = {
                    'baixa': [n for n in numeros_lista if 1 <= n <= 18],
                    'alta': [n for n in numeros_lista if 19 <= n <= 36],
                    'zero': [n for n in numeros_lista if n == 0]
                }
                return {k: len(v) for k, v in setores.items()}
            
            setores_ultimos = analisar_setores(ultimos_20)
            setores_anteriores = analisar_setores(anteriores_20)
            
            # Critérios para detectar mudança
            mudanca_detectada = False
            
            # 1. Mudança na média (mudança de faixa de números)
            if abs(media_ultimos - media_anteriores) > 8:
                mudanca_detectada = True
                logging.info(f"📊 Mudança de média detectada: {media_anteriores:.1f} → {media_ultimos:.1f}")
            
            # 2. Mudança na distribuição por setores
            diff_baixa = abs(setores_ultimos['baixa'] - setores_anteriores['baixa'])
            diff_alta = abs(setores_ultimos['alta'] - setores_anteriores['alta'])
            
            if diff_baixa > 6 or diff_alta > 6:
                mudanca_detectada = True
                logging.info(f"🎯 Mudança de setores detectada: Baixa {setores_anteriores['baixa']}→{setores_ultimos['baixa']}, Alta {setores_anteriores['alta']}→{setores_ultimos['alta']}")
            
            # 3. Mudança na volatilidade
            if abs(std_ultimos - std_anteriores) > 5:
                mudanca_detectada = True
                logging.info(f"🎲 Mudança de volatilidade detectada: {std_anteriores:.1f} → {std_ultimos:.1f}")
            
            if mudanca_detectada:
                self.ultimo_padrao_detectado = {
                    'media_ultimos': media_ultimos,
                    'media_anteriores': media_anteriores,
                    'tendencia': 'ALTA' if media_ultimos > 18 else 'BAIXA',
                    'timestamp': datetime.now()
                }
                
            return mudanca_detectada
            
        except Exception as e:
            logging.error(f"Erro na detecção de mudança de padrão: {e}")
            return False
    
    def get_tendencia_atual(self, historico):
        """Retorna a tendência atual baseada nos últimos números"""
        try:
            if len(historico) < 10:
                return "NEUTRA"
                
            numeros = [h['number'] for h in historico if h.get('number') is not None][-15:]
            media = np.mean(numeros)
            
            if media > 20:
                return "ALTA"
            elif media < 16:
                return "BAIXA"
            else:
                return "NEUTRA"
                
        except Exception as e:
            logging.error(f"Erro ao calcular tendência: {e}")
            return "NEUTRA"

class LSTM_Predictor:
    def __init__(self):
        self.ultimo_treinamento = 0
        
    def predict_proba(self, historico):
        if len(historico) < 5:
            return self.previsao_inicial()
            
        numeros = [h['number'] for h in historico]
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
            
            idx_ultimo = ROULETTE_LAYOUT.index(ultimo)
            idx_penultimo = ROULETTE_LAYOUT.index(penultimo)
            
            direcao = (idx_ultimo - idx_penultimo) % len(ROULETTE_LAYOUT)
            if direcao > len(ROULETTE_LAYOUT)//2:
                direcao -= len(ROULETTE_LAYOUT)
            
            next_idx = (idx_ultimo + direcao) % len(ROULETTE_LAYOUT)
            next_num = ROULETTE_LAYOUT[next_idx]
            probs[next_num] = probs.get(next_num, 0) + 0.3
        
        return probs if probs else self.previsao_inicial()
    
    def previsao_inicial(self):
        return {num: 0.1 for num in [0, 7, 13, 22, 29, 32]}

class XGBoost_Predictor:
    def __init__(self):
        self.features_importance = {}
        
    def create_features(self, historico):
        if len(historico) < 3:
            return []
            
        numeros = [h['number'] for h in historico]
        features = []
        ultimo_numero = numeros[-1] if numeros else 0
        
        for num in range(37):
            feature_vector = [
                numeros.count(num),
                1 if num == ultimo_numero else 0,
                min(abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT),
                    len(ROULETTE_LAYOUT) - abs(ROULETTE_LAYOUT.index(num) - ROULETTE_LAYOUT.index(ultimo_numero)) % len(ROULETTE_LAYOUT)),
                1 if num % 2 == 0 else 0,
                1 if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 0,
            ]
            features.append((num, feature_vector))
            
        return features
    
    def predict_proba(self, historico):
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

class Ensemble_Predictor:
    def __init__(self):
        self.model_weights = {'lstm': 0.4, 'xgb': 0.6}
        
    def predict(self, lstm_probs, xgb_probs, anomalies):
        combined_scores = {}
        
        for number in range(37):
            lstm_score = lstm_probs.get(number, 0)
            xgb_score = xgb_probs.get(number, 0)
            
            base_score = (lstm_score * self.model_weights['lstm'] + 
                         xgb_score * self.model_weights['xgb'])
            
            anomaly_boost = 2.0 if number in anomalies else 1.0
            
            combined_scores[number] = base_score * anomaly_boost
            
        return combined_scores

class Hybrid_IA_System:
    def __init__(self):
        self.lstm_predictor = LSTM_Predictor()
        self.xgb_predictor = XGBoost_Predictor()
        self.pattern_analyzer = Pattern_Analyzer_Atualizado()  # ATUALIZADO
        self.ensemble = Ensemble_Predictor()
        self.ultima_previsao = None
        
    def estrategia_reativacao_rapida(self, historico):
        """Estratégia agressiva para se adaptar rapidamente a mudanças"""
        try:
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if len(numeros) < 10:
                return self.estrategia_inicial_agressiva()
            
            # Foco TOTAL nos últimos 15 números
            ultimos_15 = numeros[-15:]
            frequencia = Counter(ultimos_15)
            
            previsao = set()
            
            # 1. NÚMEROS MAIS QUENTES (últimas 15 jogadas)
            numeros_quentes = [num for num, count in frequencia.most_common(8) if count >= 1]
            previsao.update(numeros_quentes)
            
            # 2. VIZINHOS ESTRATÉGICOS (foco nos últimos 5 números)
            for num in ultimos_15[-5:]:
                vizinhos = obter_vizinhos(num, ROULETTE_LAYOUT, antes=2, depois=2)
                previsao.update(vizinhos)
            
            # 3. TENDÊNCIA ATUAL (foco na área quente atual)
            tendencia = self.pattern_analyzer.get_tendencia_atual(historico)
            
            if tendencia == "ALTA" and len(previsao) < 15:
                # Adiciona números altos estratégicos
                numeros_altos = [n for n in range(19, 37) if n not in previsao]
                previsao.update(numeros_altos[:8])
            elif tendencia == "BAIXA" and len(previsao) < 15:
                # Adiciona números baixos estratégicos
                numeros_baixos = [n for n in range(1, 19) if n not in previsao]
                previsao.update(numeros_baixos[:8])
            
            # 4. GARANTIR ZERO
            previsao.add(0)
            
            previsao_final = list(previsao)
            
            # Ordenar por proximidade aos números quentes
            def ordenar_por_proximidade(numeros_lista, numeros_referencia):
                def distancia_minima(num):
                    distancias = []
                    for ref in numeros_referencia:
                        if ref in ROULETTE_LAYOUT and num in ROULETTE_LAYOUT:
                            idx_ref = ROULETTE_LAYOUT.index(ref)
                            idx_num = ROULETTE_LAYOUT.index(num)
                            distancia = min(abs(idx_num - idx_ref), 
                                          len(ROULETTE_LAYOUT) - abs(idx_num - idx_ref))
                            distancias.append(distancia)
                    return min(distancias) if distancias else 99
                return sorted(numeros_lista, key=distancia_minima)
            
            if numeros_quentes:
                previsao_final = ordenar_por_proximidade(previsao_final, numeros_quentes[:3])
            
            logging.info(f"🔄 Reativação Rápida: {len(previsao_final)} números (Tendência: {tendencia})")
            return previsao_final[:15]
            
        except Exception as e:
            logging.error(f"Erro na estratégia de reativação rápida: {e}")
            return self.estrategia_intermediaria(historico)
    
    def estrategia_inicial_agressiva(self):
        numeros_base = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36]
        return validar_previsao(numeros_base[:NUMERO_PREVISOES])
    
    def estrategia_intermediaria(self, historico):
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
        try:
            # 1. Predição LSTM
            lstm_probs = self.lstm_predictor.predict_proba(historico)
            
            # 2. Predição XGBoost
            xgb_probs = self.xgb_predictor.predict_proba(historico)
            
            # 3. Detecção de anomalias
            anomalies = self.pattern_analyzer.detectar_mudanca_padrao(historico)
            
            # 4. Combinação inteligente
            combined_scores = self.ensemble.predict(lstm_probs, xgb_probs, anomalies)
            
            # 5. Seleção final
            top_numbers = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:NUMERO_PREVISOES]
            final_selection = [num for num, score in top_numbers]
            
            # 6. Diversificação
            final_selection = self.diversify_selection(final_selection)
            
            logging.info(f"🎯 Hybrid IA Avançada: {len(final_selection)} números")
            return validar_previsao(final_selection)
            
        except Exception as e:
            logging.error(f"Erro na estratégia avançada: {e}")
            return self.estrategia_intermediaria(historico)
    
    def estrategia_emergencia(self):
        return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    
    def diversify_selection(self, numbers):
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
            
        except Exception as e:
            logging.error(f"Erro na diversificação: {e}")
            return self.estrategia_emergencia()
    
    def predict_hybrid(self, historico):
        """Sistema híbrido atualizado com detecção de mudanças"""
        try:
            if not historico:
                return self.estrategia_inicial_agressiva()
                
            historico_size = len(historico)
            
            # Verificar se há mudança de padrão detectada
            mudanca_detectada = self.pattern_analyzer.detectar_mudanca_padrao(historico)
            tendencia_atual = self.pattern_analyzer.get_tendencia_atual(historico)
            
            logging.info(f"🎯 Status: Histórico={historico_size}, Mudança={mudanca_detectada}, Tendência={tendencia_atual}")
            
            # DECISÃO ESTRATÉGICA
            if mudanca_detectada or historico_size < 10:
                # MUDANÇA DETECTADA ou POUCOS DADOS - Reativação Rápida
                logging.info("🔄 Ativando modo de reativação rápida")
                return self.estrategia_reativacao_rapida(historico)
                
            elif historico_size < 25:
                # FASE INTERMEDIÁRIA - Estratégia balanceada
                return self.estrategia_intermediaria(historico)
                
            else:
                # FASE AVANÇADA - IA Híbrida Completa
                return self.estrategia_avancada(historico)
                
        except Exception as e:
            logging.error(f"Erro crítico no sistema híbrido atualizado: {e}")
            return self.estrategia_emergencia()

# =============================
# GESTOR PRINCIPAL
# =============================
class GestorHybridIA:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_System()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        try:
            previsao = self.hybrid_system.predict_hybrid(self.historico)
            return validar_previsao(previsao)
        except Exception as e:
            logging.error(f"Erro crítico ao gerar previsão: {e}")
            return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            if historico_size < 5:
                return "🟡 Fase Inicial", "Reativação Rápida"
            elif historico_size < 20:
                return "🟠 Coletando Dados", "Estratégia Intermediária"
            else:
                return "🟢 IA Ativa", "Sistema Híbrido Completo"
        except:
            return "⚪ Sistema", "Carregando..."

# =============================
# STREAMLIT APP
# =============================
st.set_page_config(
    page_title="Roleta - Hybrid IA (Atualizado)", 
    page_icon="🧠", 
    layout="centered"
)

st.title("🧠 Hybrid IA System - ATUALIZADO")
st.markdown("### **Com Detecção de Mudanças e Reativação Rápida**")

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

# Garante que previsao_atual é uma lista válida
if not isinstance(st.session_state.previsao_atual, list):
    st.session_state.previsao_atual = []

st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL
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

        # CONFERÊNCIA
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
        
        # TELEGRAM
        if st.session_state.previsao_atual and len(st.session_state.gestor.historico) >= 3:
            try:
                mensagem = f"🧠 **HYBRID IA ATUALIZADO - PREVISÃO**\n"
                mensagem += f"📊 Status: {st.session_state.status_ia}\n"
                mensagem += f"🎯 Estratégia: {st.session_state.estrategia_atual}\n"
                mensagem += f"🔢 Último: {numero_real}\n"
                mensagem += f"📈 Performance: {st.session_state.acertos}G/{st.session_state.erros}R\n"
                mensagem += f"🔄 Sistema: Com Detecção de Mudanças\n"
                mensagem += f"📋 Números: {', '.join(map(str, sorted(st.session_state.previsao_atual)))}"
                
                enviar_telegram(mensagem)
            except Exception as e:
                logging.error(f"Erro ao enviar Telegram: {e}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

# =============================
# INTERFACE
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
    st.caption("🟡 Fase Inicial: Reativação Rápida Ativa")
elif historico_size < 20:
    progresso = historico_size / 20
    st.progress(progresso)
    st.caption("🟠 Coletando Dados: Desenvolvendo padrões...")
else:
    st.progress(1.0)
    st.caption("🟢 Sistema Completo: IA Híbrida com Detecção de Mudanças!")

# HISTÓRICO VISUAL
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

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    st.success(f"**{len(previsao_valida)} NÚMEROS PREVISTOS**")
    
    # Display em grid
    col1, col2, col3 = st.columns(3)
    
    try:
        numeros_ordenados = sorted(previsao_valida)
    except:
        numeros_ordenados = previsao_valida
    
    for i, num in enumerate(numeros_ordenados):
        if i < 15:
            col = [col1, col2, col3][i % 3]
            with col:
                if num == 0:
                    st.markdown(f"<div style='background-color: green; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
                #elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                    #st.markdown(f"<div style
                elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                    st.markdown(f"<div style='background-color: red; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='background-color: black; color: white; padding: 10px; margin: 2px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
else:
    st.warning("⚠️ Gerando previsão inicial...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

# PERFORMANCE
st.markdown("---")
st.subheader("📊 Performance")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("✅ Acertos", st.session_state.acertos)
with col2:
    st.metric("❌ Erros", st.session_state.erros)
with col3:
    total = st.session_state.acertos + st.session_state.erros
    taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
    st.metric("📈 Taxa Acerto", f"{taxa_acerto:.1f}%")

# DETALHES TÉCNICOS
with st.expander("🔍 Detalhes Técnicos do Sistema"):
    st.write("**🧠 HYBRID IA SYSTEM - ATUALIZADO**")
    st.write("- ✅ **Detecção de Mudanças de Padrão**")
    st.write("- ✅ **Reativação Rápida Automática**")
    st.write("- ✅ **LSTM + XGBoost Ensemble**")
    st.write("- ✅ **Análise de Tendências em Tempo Real**")
    st.write("- ✅ **Gestão Inteligente de Estratégias**")
    
    if st.session_state.gestor.historico:
        historico_size = len(st.session_state.gestor.historico)
        st.write(f"**📊 Estatísticas do Histórico:** {historico_size} registros")
        
        if historico_size >= 5:
            numeros = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
            media = np.mean(numeros)
            std = np.std(numeros)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Média:** {media:.2f}")
                st.write(f"**Desvio Padrão:** {std:.2f}")
            with col2:
                tendencia = st.session_state.gestor.hybrid_system.pattern_analyzer.get_tendencia_atual(st.session_state.gestor.historico)
                st.write(f"**Tendência:** {tendencia}")

# CONTROLES
st.markdown("---")
st.subheader("⚙️ Controles")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Forçar Nova Previsão"):
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        st.rerun()

with col2:
    if st.button("🗑️ Limpar Histórico"):
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        st.session_state.gestor.historico.clear()
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.rerun()

# LOGS
with st.expander("📋 Logs do Sistema"):
    st.write("**Últimas Ações:**")
    if st.session_state.gestor.historico:
        ultimos_5 = list(st.session_state.gestor.historico)[-5:]
        for registro in reversed(ultimos_5):
            numero = registro.get('number', 'N/A')
            timestamp = registro.get('timestamp', 'N/A')
            st.write(f"- Número {numero} | {timestamp}")

st.markdown("---")
st.markdown("### 🎯 **Sistema Atualizado com Detecção de Mudanças**")
st.markdown("*Capaz de se adaptar rapidamente a mudanças de padrões*")

# Rodapé
st.markdown("---")
st.markdown("**🧠 Hybrid IA System v2.0** - *Com Reativação Rápida*")    
