# RoletaHybridIA.py - SISTEMA COM DISPOSIÇÃO FÍSICA REAL
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

# DISPOSIÇÃO FÍSICA REAL DA ROLETA (layout da mesa)
ROULETTE_PHYSICAL_LAYOUT = [
    # Coluna 1 (1ª dúzia)
    [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    # Coluna 2 (2ª dúzia)  
    [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
    # Coluna 3 (3ª dúzia)
    [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
]

# Dúzias
PRIMEIRA_DUZIA = list(range(1, 13))
SEGUNDA_DUZIA = list(range(13, 25))
TERCEIRA_DUZIA = list(range(25, 37))

# Colunas (baseadas no layout físico)
COLUNA_1 = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
COLUNA_2 = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]  
COLUNA_3 = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]

# Vizinhos físicos na roda (aproximação)
ROULETTE_WHEEL_NEIGHBORS = {
    0: [32, 15, 19, 4, 21, 2, 25],
    32: [0, 15, 19, 4, 21, 2, 25],
    15: [32, 0, 19, 4, 21, 2, 25],
    19: [15, 32, 0, 4, 21, 2, 25],
    4: [19, 15, 32, 0, 21, 2, 25],
    21: [4, 19, 15, 32, 0, 2, 25],
    2: [21, 4, 19, 15, 32, 0, 25],
    25: [2, 21, 4, 19, 15, 32, 0]
}

# Configurações
MIN_HISTORICO_TREINAMENTO = 350
NUMERO_PREVISOES = 12

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

def obter_vizinhos_fisicos(numero):
    """Retorna vizinhos físicos na mesa (mesma coluna e linhas adjacentes)"""
    if numero == 0:
        return [32, 15, 19, 4, 21, 2, 25]
    
    vizinhos = set()
    
    # Encontrar posição na mesa
    for col_idx, coluna in enumerate(ROULETTE_PHYSICAL_LAYOUT):
        if numero in coluna:
            num_idx = coluna.index(numero)
            
            # Mesma coluna - acima e abaixo
            if num_idx > 0:
                vizinhos.add(coluna[num_idx - 1])  # Acima
            if num_idx < len(coluna) - 1:
                vizinhos.add(coluna[num_idx + 1])  # Abaixo
                
            # Colunas adjacentes - mesma linha
            if col_idx > 0:  # Coluna à esquerda
                if num_idx < len(ROULETTE_PHYSICAL_LAYOUT[col_idx - 1]):
                    vizinhos.add(ROULETTE_PHYSICAL_LAYOUT[col_idx - 1][num_idx])
            if col_idx < 2:  # Coluna à direita
                if num_idx < len(ROULETTE_PHYSICAL_LAYOUT[col_idx + 1]):
                    vizinhos.add(ROULETTE_PHYSICAL_LAYOUT[col_idx + 1][num_idx])
    
    return list(vizinhos)

def obter_vizinhos_estendidos(numero, raio=2):
    """Vizinhos estendidos na disposição física"""
    if numero == 0:
        return ROULETTE_WHEEL_NEIGHBORS.get(0, [])
    
    vizinhos = set()
    
    for col_idx, coluna in enumerate(ROULETTE_PHYSICAL_LAYOUT):
        if numero in coluna:
            num_idx = coluna.index(numero)
            
            # Expandir raio na mesma coluna
            for i in range(max(0, num_idx - raio), min(len(coluna), num_idx + raio + 1)):
                if i != num_idx:
                    vizinhos.add(coluna[i])
            
            # Expandir para colunas adjacentes
            for offset in [-1, 1]:
                adj_col_idx = col_idx + offset
                if 0 <= adj_col_idx <= 2:
                    coluna_adj = ROULETTE_PHYSICAL_LAYOUT[adj_col_idx]
                    # Mesma linha e linhas adjacentes
                    for i in range(max(0, num_idx - 1), min(len(coluna_adj), num_idx + 2)):
                        vizinhos.add(coluna_adj[i])
    
    return list(vizinhos)

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

def analisar_duzias_colunas(historico):
    """Analisa padrões de dúzias e colunas"""
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if not numeros:
        return {"duzias_quentes": [], "colunas_quentes": []}
    
    # Análise das últimas 20 jogadas
    ultimos_20 = numeros[-20:] if len(numeros) >= 20 else numeros
    
    contagem_duzias = {1: 0, 2: 0, 3: 0}
    contagem_colunas = {1: 0, 2: 0, 3: 0}
    
    for num in ultimos_20:
        # Dúzias
        if 1 <= num <= 12:
            contagem_duzias[1] += 1
        elif 13 <= num <= 24:
            contagem_duzias[2] += 1
        elif 25 <= num <= 36:
            contagem_duzias[3] += 1
            
        # Colunas
        if num in COLUNA_1:
            contagem_colunas[1] += 1
        elif num in COLUNA_2:
            contagem_colunas[2] += 1
        elif num in COLUNA_3:
            contagem_colunas[3] += 1
    
    # Identificar dúzias e colunas quentes
    duzia_quente = max(contagem_duzias, key=contagem_duzias.get)
    coluna_quente = max(contagem_colunas, key=contagem_colunas.get)
    
    return {
        "duzias_quentes": [duzia_quente],
        "colunas_quentes": [coluna_quente],
        "contagem_duzias": contagem_duzias,
        "contagem_colunas": contagem_colunas
    }

# =============================
# SISTEMA HÍBRIDO COM DISPOSIÇÃO FÍSICA
# =============================
class Pattern_Analyzer_Fisico:
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.ultimo_padrao_detectado = None
        
    def detectar_padroes_fisicos(self, historico):
        """Detecta padrões baseados na disposição física"""
        try:
            if len(historico) < 10:
                return {"padroes": [], "tendencia": "NEUTRA"}
                
            numeros = [h['number'] for h in historico if h.get('number') is not None][-15:]
            
            padroes_detectados = []
            
            # Padrão de Coluna
            ultima_coluna = None
            sequencia_colunas = 0
            
            for num in numeros[-5:]:
                coluna_atual = None
                for col_idx, coluna in enumerate(ROULETTE_PHYSICAL_LAYOUT, 1):
                    if num in coluna:
                        coluna_atual = col_idx
                        break
                
                if coluna_atual == ultima_coluna and coluna_atual is not None:
                    sequencia_colunas += 1
                else:
                    sequencia_colunas = 1
                    ultima_coluna = coluna_atual
                
                if sequencia_colunas >= 3:
                    padroes_detectados.append(f"COLUNA_{coluna_atual}_SEQUENCIA")
            
            # Padrão de Linha (horizontal)
            for i in range(len(numeros) - 2):
                trio = numeros[i:i+3]
                linhas = []
                for num in trio:
                    for col_idx, coluna in enumerate(ROULETTE_PHYSICAL_LAYOUT):
                        if num in coluna:
                            linhas.append(coluna.index(num))
                            break
                
                if len(set(linhas)) == 1:  # Mesma linha
                    padroes_detectados.append(f"LINHA_{linhas[0]}_HORIZONTAL")
            
            # Tendência baseada em dúzias
            analise = analisar_duzias_colunas(historico)
            tendencia = self.calcular_tendencia_fisica(analise)
            
            return {
                "padroes": padroes_detectados,
                "tendencia": tendencia,
                "duzias_quentes": analise["duzias_quentes"],
                "colunas_quentes": analise["colunas_quentes"]
            }
            
        except Exception as e:
            logging.error(f"Erro na detecção de padrões físicos: {e}")
            return {"padroes": [], "tendencia": "NEUTRA"}
    
    def calcular_tendencia_fisica(self, analise):
        """Calcula tendência baseada na disposição física"""
        contagem_duzias = analise.get("contagem_duzias", {1:0, 2:0, 3:0})
        
        total = sum(contagem_duzias.values())
        if total == 0:
            return "NEUTRA"
        
        # Tendência ALTA se 3ª dúzia dominante, BAIXA se 1ª dúzia dominante
        percent_duzia1 = contagem_duzias[1] / total
        percent_duzia3 = contagem_duzias[3] / total
        
        if percent_duzia3 > 0.4:
            return "ALTA"
        elif percent_duzia1 > 0.4:
            return "BAIXA"
        else:
            return "NEUTRA"

class LSTM_Predictor_Fisico:
    def __init__(self):
        self.ultimo_treinamento = 0
        
    def predict_proba(self, historico):
        if len(historico) < 5:
            return self.previsao_inicial()
            
        numeros = [h['number'] for h in historico]
        probs = {}
        
        # Estratégia baseada em padrões físicos
        analise = analisar_duzias_colunas(historico)
        duzia_quente = analise["duzias_quentes"][0] if analise["duzias_quentes"] else 1
        coluna_quente = analise["colunas_quentes"][0] if analise["colunas_quentes"] else 1
        
        # Focar na dúzia e coluna quentes
        if duzia_quente == 1:
            numeros_foco = PRIMEIRA_DUZIA
        elif duzia_quente == 2:
            numeros_foco = SEGUNDA_DUZIA
        else:
            numeros_foco = TERCEIRA_DUZIA
            
        if coluna_quente == 1:
            coluna_foco = COLUNA_1
        elif coluna_quente == 2:
            coluna_foco = COLUNA_2
        else:
            coluna_foco = COLUNA_3
        
        # Interseção entre dúzia quente e coluna quente
        numeros_estrategicos = [n for n in numeros_foco if n in coluna_foco]
        
        for num in numeros_estrategicos:
            probs[num] = probs.get(num, 0) + 0.3
        
        # Adicionar vizinhos físicos dos últimos números
        for num in numeros[-3:]:
            vizinhos = obter_vizinhos_fisicos(num)
            for vizinho in vizinhos:
                probs[vizinho] = probs.get(vizinho, 0) + 0.2
        
        return probs if probs else self.previsao_inicial()
    
    def previsao_inicial(self):
        # Números estrategicamente distribuídos na mesa
        return {num: 0.1 for num in [1, 8, 13, 19, 25, 30, 36, 5, 16, 22, 28, 33, 0]}

class XGBoost_Predictor_Fisico:
    def __init__(self):
        self.features_importance = {}
        
    def create_features(self, historico):
        if len(historico) < 3:
            return []
            
        numeros = [h['number'] for h in historico]
        features = []
        ultimo_numero = numeros[-1] if numeros else 0
        
        for num in range(37):
            # Features baseadas na disposição física
            feature_vector = [
                # Posição na mesa
                1 if num in PRIMEIRA_DUZIA else 2 if num in SEGUNDA_DUZIA else 3 if num in TERCEIRA_DUZIA else 0,
                1 if num in COLUNA_1 else 2 if num in COLUNA_2 else 3 if num in COLUNA_3 else 0,
                # Vizinhos físicos
                1 if num in obter_vizinhos_fisicos(ultimo_numero) else 0,
                # Características do número
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
        
        for num, feat in features:
            score = 0.0
            
            # Bônus por estar na mesma dúzia/coluna dos últimos números
            if feat[0] != 0:  # Não é zero
                score += 0.2
                
            # Bônus por ser vizinho físico
            if feat[2] == 1:
                score += 0.3
                
            if score > 0:
                probs[num] = score
                
        return probs if probs else {num: 0.05 for num in range(37)}

class Ensemble_Predictor_Fisico:
    def __init__(self):
        self.model_weights = {'lstm': 0.5, 'xgb': 0.5}
        
    def predict(self, lstm_probs, xgb_probs, padroes_fisicos):
        combined_scores = {}
        
        for number in range(37):
            lstm_score = lstm_probs.get(number, 0)
            xgb_score = xgb_probs.get(number, 0)
            
            base_score = (lstm_score * self.model_weights['lstm'] + 
                         xgb_score * self.model_weights['xgb'])
            
            # Bônus por estar em padrões físicos detectados
            pattern_boost = 1.0
            if padroes_fisicos.get("duzias_quentes"):
                duzia_quente = padroes_fisicos["duzias_quentes"][0]
                if (duzia_quente == 1 and number in PRIMEIRA_DUZIA) or \
                   (duzia_quente == 2 and number in SEGUNDA_DUZIA) or \
                   (duzia_quente == 3 and number in TERCEIRA_DUZIA):
                    pattern_boost *= 1.5
            
            combined_scores[number] = base_score * pattern_boost
            
        return combined_scores

class Hybrid_IA_System_Fisico:
    def __init__(self):
        self.lstm_predictor = LSTM_Predictor_Fisico()
        self.xgb_predictor = XGBoost_Predictor_Fisico()
        self.pattern_analyzer = Pattern_Analyzer_Fisico()
        self.ensemble = Ensemble_Predictor_Fisico()
        self.ultima_previsao = None
        
    def estrategia_reativacao_fisica(self, historico):
        """Estratégia baseada na disposição física real"""
        try:
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if len(numeros) < 8:
                return self.estrategia_inicial_fisica()
            
            previsao = set()
            
            # 1. ANÁLISE DE DÚZIAS E COLUNAS QUENTES
            analise = analisar_duzias_colunas(historico)
            duzia_quente = analise["duzias_quentes"][0] if analise["duzias_quentes"] else 1
            coluna_quente = analise["colunas_quentes"][0] if analise["colunas_quentes"] else 1
            
            # Focar na interseção dúzia quente + coluna quente
            if duzia_quente == 1:
                numeros_duzia = PRIMEIRA_DUZIA
            elif duzia_quente == 2:
                numeros_duzia = SEGUNDA_DUZIA
            else:
                numeros_duzia = TERCEIRA_DUZIA
                
            if coluna_quente == 1:
                numeros_coluna = COLUNA_1
            elif coluna_quente == 2:
                numeros_coluna = COLUNA_2
            else:
                numeros_coluna = COLUNA_3
            
            interseção = [n for n in numeros_duzia if n in numeros_coluna]
            previsao.update(interseção[:4])
            
            # 2. VIZINHOS FÍSICOS DOS ÚLTIMOS 3 NÚMEROS
            for num in numeros[-3:]:
                vizinhos = obter_vizinhos_estendidos(num, raio=2)
                previsao.update(vizinhos[:3])
            
            # 3. NÚMEROS MAIS FREQUENTES (últimas 15 jogadas)
            ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
            frequencia = Counter(ultimos_15)
            numeros_quentes = [num for num, count in frequencia.most_common(5) if count >= 2]
            previsao.update(numeros_quentes)
            
            # 4. COMPLEMENTAÇÃO ESTRATÉGICA
            if len(previsao) < NUMERO_PREVISOES:
                # Adicionar números da dúzia quente
                faltantes = NUMERO_PREVISOES - len(previsao)
                complemento = [n for n in numeros_duzia if n not in previsao][:faltantes]
                previsao.update(complemento)
            
            # 5. GARANTIR ZERO
            previsao.add(0)
            
            previsao_final = list(previsao)
            
            logging.info(f"🎯 Reativação Física: Dúzia {duzia_quente}, Coluna {coluna_quente}, {len(previsao_final)} números")
            return validar_previsao(previsao_final)[:NUMERO_PREVISOES]
            
        except Exception as e:
            logging.error(f"Erro na estratégia física: {e}")
            return self.estrategia_intermediaria_fisica(historico)
    
    def estrategia_inicial_fisica(self):
        """Números estrategicamente distribuídos na mesa física"""
        # Uma seleção balanceada cobrindo diferentes áreas da mesa
        numeros_estrategicos = [
            1, 2, 3,        # Topo da mesa
            13, 14, 15,     # Meio
            25, 26, 27,     # Fundo
            34, 35, 36,     # Lateral direita
            0               # Zero
        ]
        return validar_previsao(numeros_estrategicos)[:NUMERO_PREVISOES]
    
    def estrategia_intermediaria_fisica(self, historico):
        try:
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if not numeros:
                return self.estrategia_inicial_fisica()
                
            previsao = set()
            
            # Foco nos padrões físicos recentes
            analise = analisar_duzias_colunas(historico)
            padroes = self.pattern_analyzer.detectar_padroes_fisicos(historico)
            
            # Adicionar números baseados nos padrões detectados
            for padrao in padroes.get("padroes", [])[:3]:
                if "COLUNA" in padrao:
                    coluna_num = int(padrao.split("_")[1])
                    if coluna_num == 1:
                        previsao.update(COLUNA_1[:4])
                    elif coluna_num == 2:
                        previsao.update(COLUNA_2[:4])
                    else:
                        previsao.update(COLUNA_3[:4])
            
            # Vizinhos físicos dos últimos números
            for num in numeros[-4:]:
                vizinhos = obter_vizinhos_fisicos(num)
                previsao.update(vizinhos[:2])
            
            # Garantir cobertura mínima
            if len(previsao) < 10:
                previsao.update([1, 13, 25, 2, 14, 26, 3, 15, 27, 0])
            
            return validar_previsao(list(previsao))[:NUMERO_PREVISOES]
            
        except Exception as e:
            logging.error(f"Erro na estratégia intermediária física: {e}")
            return self.estrategia_inicial_fisica()
    
    def estrategia_avancada_fisica(self, historico):
        try:
            # 1. Predição LSTM física
            lstm_probs = self.lstm_predictor.predict_proba(historico)
            
            # 2. Predição XGBoost física
            xgb_probs = self.xgb_predictor.predict_proba(historico)
            
            # 3. Detecção de padrões físicos
            padroes_fisicos = self.pattern_analyzer.detectar_padroes_fisicos(historico)
            
            # 4. Combinação inteligente
            combined_scores = self.ensemble.predict(lstm_probs, xgb_probs, padroes_fisicos)
            
            # 5. Seleção final com diversificação física
            top_numbers = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:NUMERO_PREVISOES + 5]
            final_selection = [num for num, score in top_numbers]
            
            # 6. Garantir diversificação na mesa
            final_selection = self.diversificar_selecao_fisica(final_selection)
            
            logging.info(f"🎯 IA Física Avançada: {len(final_selection)} números")
            return validar_previsao(final_selection)
            
        except Exception as e:
            logging.error(f"Erro na estratégia avançada física: {e}")
            return self.estrategia_intermediaria_fisica(historico)
    
    def diversificar_selecao_fisica(self, numbers):
        """Garante que a seleção cubra diferentes áreas da mesa"""
        numbers = validar_previsao(numbers)
        
        if len(numbers) < 8:
            return self.estrategia_inicial_fisica()
        
        diversificada = []
        
        # Garantir representação de cada coluna
        for coluna in [COLUNA_1, COLUNA_2, COLUNA_3]:
            for num in numbers:
                if num in coluna and num not in diversificada:
                    diversificada.append(num)
                    break
        
        # Garantir representação de cada dúzia
        for duzia in [PRIMEIRA_DUZIA, SEGUNDA_DUZIA, TERCEIRA_DUZIA]:
            for num in numbers:
                if num in duzia and num not in diversificada:
                    diversificada.append(num)
                    break
        
        # Completar com números originais
        for num in numbers:
            if num not in diversificada and len(diversificada) < NUMERO_PREVISOES:
                diversificada.append(num)
        
        # Garantir zero
        if 0 not in diversificada and len(diversificada) < NUMERO_PREVISOES:
            diversificada.append(0)
        
        return diversificada[:NUMERO_PREVISOES]
    
    def estrategia_emergencia(self):
        return [0, 1, 2, 13, 14, 15, 25, 26, 27, 4, 16, 28, 7, 19, 31]
    
    def predict_hybrid(self, historico):
        """Sistema híbrido com abordagem física"""
        try:
            if not historico:
                return self.estrategia_inicial_fisica()
                
            historico_size = len(historico)
            
            # DECISÃO ESTRATÉGICA BASEADA NA DISPOSIÇÃO FÍSICA
            if historico_size < 10:
                logging.info("🔄 Modo Físico Inicial: Reativação Física")
                return self.estrategia_reativacao_fisica(historico)
            elif historico_size < 25:
                logging.info("🟠 Modo Físico Intermediário")
                return self.estrategia_intermediaria_fisica(historico)
            else:
                logging.info("🟢 Modo Físico Avançado: IA Completa")
                return self.estrategia_avancada_fisica(historico)
                
        except Exception as e:
            logging.error(f"Erro crítico no sistema físico: {e}")
            return self.estrategia_emergencia()

# =============================
# GESTOR PRINCIPAL
# =============================
class GestorHybridIA_Fisico:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_System_Fisico()
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
            return self.hybrid_system.estrategia_emergencia()
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            if historico_size < 10:
                return "🟡 Fase Física Inicial", "Reativação Física"
            elif historico_size < 25:
                return "🟠 Analisando Padrões", "Estratégia Intermediária"
            else:
                return "🟢 IA Física Ativa", "Sistema Físico Completo"
        except:
            return "⚪ Sistema", "Carregando..."
    
    def get_analise_mesa(self):
        """Retorna análise atual da mesa"""
        if not self.historico:
            return {"duzia_quente": "-", "coluna_quente": "-", "tendencia": "-"}
        
        analise = analisar_duzias_colunas(self.historico)
        padroes = self.hybrid_system.pattern_analyzer.detectar_padroes_fisicos(self.historico)
        
        return {
            "duzia_quente": analise["duzias_quentes"][0] if analise["duzias_quentes"] else "-",
            "coluna_quente": analise["colunas_quentes"][0] if analise["colunas_quentes"] else "-",
            "tendencia": padroes.get("tendencia", "NEUTRA"),
            "total_numeros": len(self.historico)
        }

# =============================
# STREAMLIT APP
# =============================
st.set_page_config(
    page_title="Roleta - IA com Disposição Física", 
    page_icon="🎰", 
    layout="centered"
)

st.title("🎰 Hybrid IA System - DISPOSIÇÃO FÍSICA")
st.markdown("### **Análise Baseada na Mesa Real da Roleta**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorHybridIA_Fisico(),
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
                enviar_telegram(f"🟢 GREEN! Sistema Físico acertou {numero_real}!")
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")

        # GERAR NOVA PREVISÃO
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # TELEGRAM
        if st.session_state.previsao_atual and len(st.session_state.gestor.historico) >= 3:
            try:
                analise_mesa = st.session_state.gestor.get_analise_mesa()
                mensagem = f"🎰 **IA COM DISPOSIÇÃO FÍSICA - PREVISÃO**\n"
                mensagem += f"📊 Status: {st.session_state.status_ia}\n"
                mensagem += f"🎯 Estratégia: {st.session_state.estrategia_atual}\n"
                mensagem += f"🔥 Dúzia Quente: {analise_mesa['duzia_quente']}\n"
                mensagem += f"🔥 Coluna Quente: {analise_mesa['coluna_quente']}\n"
                mensagem += f"📈 Tendência: {analise_mesa['tendencia']}\n"
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
    st.session_state.previsao_atual = [0, 1, 2, 13, 14, 15, 25, 26, 27, 4, 16, 28, 7, 19, 31]

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

# ANÁLISE DA MESA
st.subheader("📊 Análise da Mesa Física")
analise_mesa = st.session_state.gestor.get_analise_mesa()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🔥 Dúzia Quente", analise_mesa["duzia_quente"])
with col2:
    st.metric("🔥 Coluna Quente", analise_mesa["coluna_quente"])
with col3:
    st.metric("📈 Tendência", analise_mesa["tendencia"])
with col4:
    st.metric("🔄 Total Análise", analise_mesa["total_numeros"])

# VISUALIZAÇÃO DA MESA FÍSICA
st.subheader("🎰 Disposição Física da Mesa")

# Criar visualização simplificada da mesa
def criar_visualizacao_mesa(previsao):
    html = """
    <style>
    .mesa {
        display: grid;
        grid-template-columns: 60px repeat(3, 40px);
        gap: 2px;
        font-family: Arial, sans-serif;
        font-size: 12px;
    }
    .zero {
        grid-column: 1;
        grid-row: 1 / span 12;
        background-color: green;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
    }
    .numero {
        padding: 5px;
        text-align: center;
        border: 1px solid #ccc;
        font-weight: bold;
    }
    .previsto {
        background-color: #ffeb3b;
        color: black;
    }
    .vermelho {
        background-color: #ff4444;
        color: white;
    }
    .preto {
        background-color: #000000;
        color: white;
    }
    .duzia-label {
        grid-column: 1;
        text-align: center;
        padding: 5px;
        font-weight: bold;
        background-color: #f0f0f0;
    }
    </style>
    
    <div class="mesa">
        <div class="zero">0</div>
    """
    
    # Adicionar números da mesa
    for linha in range(12):
        # Label da linha
        html += f'<div class="duzia-label">{linha+1}ª</div>'
        
        for coluna in range(3):
            numero = ROULETTE_PHYSICAL_LAYOUT[coluna][linha]
            classes = "numero"
            
            if numero in previsao:
                classes += " previsto"
            elif numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                classes += " vermelho"
            else:
                classes += " preto"
                
            html += f'<div class="{classes}">{numero}</div>'
    
    html += "</div>"
    return html

if st.session_state.previsao_atual:
    st.components.v1.html(criar_visualizacao_mesa(st.session_state.previsao_atual), height=400)
else:
    st.info("Aguardando previsão para mostrar disposição da mesa...")

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
st.subheader("🎯 PREVISÃO ATUAL - DISPOSIÇÃO FÍSICA")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    st.success(f"**{len(previsao_valida)} NÚMEROS PREVISTOS**")
    
    # Agrupar por dúzia para melhor visualização
    st.write("**Organização por Dúzia:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**1ª Dúzia (1-12):**")
        nums_duzia1 = [n for n in sorted(previsao_valida) if n in PRIMEIRA_DUZIA]
        for num in nums_duzia1:
            st.write(f"`{num}`")
    
    with col2:
        st.write("**2ª Dúzia (13-24):**")
        nums_duzia2 = [n for n in sorted(previsao_valida) if n in SEGUNDA_DUZIA]
        for num in nums_duzia2:
            st.write(f"`{num}`")
    
    with col3:
        st.write("**3ª Dúzia (25-36) + Zero:**")
        nums_duzia3 = [n for n in sorted(previsao_valida) if n in TERCEIRA_DUZIA]
        for num in nums_duzia3:
            st.write(f"`{num}`")
        if 0 in previsao_valida:
            st.write("`0` 🟢")
    
    st.write(f"**Lista Completa:** {', '.join(map(str, sorted(previsao_valida)))}")
    
else:
    st.warning("⚠️ Gerando previsão inicial...")
    st.session_state.previsao_atual = [0, 1, 2, 13, 14, 15, 25, 26, 27, 4, 16, 28, 7, 19, 31]

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
with st.expander("🔍 Detalhes Técnicos do Sistema Físico"):
    st.write("**🎰 SISTEMA COM DISPOSIÇÃO FÍSICA REAL**")
    st.write("- ✅ **Análise de Dúzias e Colunas**")
    st.write("- ✅ **Vizinhos Físicos na Mesa**")
    st.write("- ✅ **Padrões de Linhas e Colunas**")
    st.write("- ✅ **Estratégia Baseada na Mesa Real**")
    st.write("- ✅ **Otimização por Áreas Quentes**")
    
    if st.session_state.gestor.historico:
        historico_size = len(st.session_state.gestor.historico)
        st.write(f"**📊 Estatísticas do Histórico:** {historico_size} registros")
        
        if historico_size >= 5:
            numeros = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Distribuição por Dúzia:**")
                duzia1 = len([n for n in numeros if n in PRIMEIRA_DUZIA])
                duzia2 = len([n for n in numeros if n in SEGUNDA_DUZIA])
                duzia3 = len([n for n in numeros if n in TERCEIRA_DUZIA])
                zeros = numeros.count(0)
                
                st.write(f"1ª Dúzia: {duzia1}")
                st.write(f"2ª Dúzia: {duzia2}")
                st.write(f"3ª Dúzia: {duzia3}")
                st.write(f"Zeros: {zeros}")
                
            with col2:
                st.write("**Distribuição por Coluna:**")
                col1 = len([n for n in numeros if n in COLUNA_1])
                col2 = len([n for n in numeros if n in COLUNA_2])
                col3 = len([n for n in numeros if n in COLUNA_3])
                
                st.write(f"Coluna 1: {col1}")
                st.write(f"Coluna 2: {col2}")
                st.write(f"Coluna 3: {col3}")

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

st.markdown("---")
st.markdown("### 🎰 **Sistema com Análise de Disposição Física**")
st.markdown("*Baseado na mesa real da roleta - Dúzias, Colunas e Vizinhos Físicos*")

# Rodapé
st.markdown("---")
st.markdown("**🎰 Hybrid IA System v4.0** - *Disposição Física Real*")
