# RoletaHybridIA.py - SISTEMA 100% BASEADO EM HISTÓRICO COM XGBOOST
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
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# =============================
# CONFIGURAÇÃO XGBOOST
# =============================
try:
    import xgboost as xgb
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    import joblib
    XGBOOST_DISPONIVEL = True
except ImportError as e:
    XGBOOST_DISPONIVEL = False
    logging.warning(f"XGBoost não disponível: {e} - usando métodos tradicionais")

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
METRICAS_PATH = "metricas_hybrid_ia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# CONFIGURAÇÃO XGBOOST
XGB_MODEL_PATH = "xgboost_roleta_model.json"
FEATURE_ENGINEER_PATH = "feature_engineer.pkl"

# TELEGRAM - CANAL PRINCIPAL
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# TELEGRAM - CANAL ALTERNATIVO (ALERTAS ESTRATÉGICOS)
TELEGRAM_TOKEN_ALTERNATIVO = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID_ALTERNATIVO = "-1002940111195"

# DISPOSIÇÃO FÍSICA REAL DA ROLETA
ROULETTE_PHYSICAL_LAYOUT = [
    [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
    [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
]

PRIMEIRA_DUZIA = list(range(1, 13))
SEGUNDA_DUZIA = list(range(13, 25))
TERCEIRA_DUZIA = list(range(25, 37))

COLUNA_1 = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
COLUNA_2 = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]  
COLUNA_3 = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]

# =============================
# CONFIGURAÇÃO ESPECIALISTA - ESTRATÉGIA 100% BASEADA EM HISTÓRICO
# =============================
MIN_HISTORICO_TREINAMENTO = 695
NUMERO_PREVISOES = 15 # SEMPRE 8 NÚMEROS BASEADOS NO HISTÓRICO

# Fases do sistema
FASE_INICIAL = 30
FASE_INTERMEDIARIA = 80  
FASE_AVANCADA = 120
FASE_ESPECIALISTA = 150

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# SISTEMA XGBOOST COMPLETO
# =============================

class XGBoostRoletaIA:
    def __init__(self):
        self.model = None
        self.treinado = False
        self.ultima_previsao = []
        self.performance = {"acertos": 0, "erros": 0}
        self.feature_names = []

SISTEMA XGBOOST COMPLETO
# =============================

class XGBoostRoletaIA:
    def __init__(self):
        self.model = None
        self.treinado = False
        self.ultima_previsao = []
        self.performance = {"acertos": 0, "erros": 0}
        self.feature_names = []
        
    def criar_features_avancadas(self, historico):
        """Cria features avançadas para treinamento do XGBoost"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 500:
            return [], []
            
        features = []
        targets = []
        
        for i in range(500, len(numeros) - 1):
            feature_row = []
            janela = numeros[i-10:i]
            
            # Features básicas
            feature_row.append(np.mean(janela))
            feature_row.append(np.std(janela))
            feature_row.append(np.median(janela))
            
            # Últimos números
            feature_row.append(janela[-1])
            feature_row.append(janela[-2] if len(janela) > 1 else 0)
            feature_row.append(janela[-3] if len(janela) > 2 else 0)
            
            # Diferenças
            if len(janela) > 1:
                feature_row.append(janela[-1] - janela[-2])
            else:
                feature_row.append(0)
                
            # Características do último número
            ultimo_num = janela[-1]
            feature_row.append(ultimo_num % 2)  # Par/Ímpar
            feature_row.append(1 if ultimo_num == 0 else 0)  # Zero
            
            # Posicionamento
            feature_row.append(1 if ultimo_num in PRIMEIRA_DUZIA else 0)
            feature_row.append(1 if ultimo_num in SEGUNDA_DUZIA else 0)
            feature_row.append(1 if ultimo_num in TERCEIRA_DUZIA else 0)
            feature_row.append(1 if ultimo_num in COLUNA_1 else 0)
            feature_row.append(1 if ultimo_num in COLUNA_2 else 0)
            feature_row.append(1 if ultimo_num in COLUNA_3 else 0)
            
            # Cores
            vermelhos = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
            feature_row.append(1 if ultimo_num in vermelhos else 0)
            
            # Frequência recente
            contagem_10 = Counter(janela[-10:] if len(janela) >= 10 else janela)
            feature_row.append(contagem_10.get(ultimo_num, 0))
            
            # Padrões de repetição
            repeticoes = 0
            for j in range(1, min(4, len(janela))):
                if janela[-j] == ultimo_num:
                    repeticoes += 1
            feature_row.append(repeticoes)
            
            # Vizinhança
            vizinhos = obter_vizinhos_fisicos(ultimo_num)
            feature_row.append(len(set(vizinhos) & set(janela[-5:])))
            
            features.append(feature_row)
            targets.append(numeros[i])
        
        self.feature_names = [
            'media', 'std', 'mediana', 'ultimo', 'penultimo', 'ante_penultimo',
            'diff_ultimos', 'eh_par', 'eh_zero', 'na_duzia1', 'na_duzia2', 'na_duzia3',
            'na_coluna1', 'na_coluna2', 'na_coluna3', 'eh_vermelho', 'freq_ultimo',
            'repeticoes', 'vizinhos_recentes'
        ]
        
        logging.info(f"📊 XGBoost: Geradas {len(features)} amostras com {len(feature_row)} features")
        return np.array(features), np.array(targets)
    
    def treinar_modelo(self, historico, force_retrain=False):
        """Treina o modelo XGBoost"""
        if not XGBOOST_DISPONIVEL:
            logging.warning("XGBoost não disponível - pulando treinamento")
            return False
            
        try:
            if len(historico) < 50 and not force_retrain:
                logging.info("📊 Histórico insuficiente para treinar XGBoost")
                return False
                
            logging.info("🤖 Iniciando treinamento do XGBoost...")
            
            # Criar features e targets
            features, targets = self.criar_features_avancadas(historico)
            
            if len(features) < 30:
                logging.warning("📊 Dados insuficientes para treinamento")
                return False
            
            # Dividir dados
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=0.2, random_state=42
            )
            
            # Configurar modelo
            self.model = xgb.XGBClassifier(
                n_estimators=150,
                max_depth=8,
                learning_rate=0.1,
                random_state=42,
                objective='multi:softprob',
                num_class=37,
                n_jobs=-1
            )
            
            # Treinar
            self.model.fit(X_train, y_train)
            
            # Avaliar
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            logging.info(f"🎯 XGBoost treinado! Acurácia: {accuracy:.2%}")
            
            # Salvar modelo
            self.model.save_model(XGB_MODEL_PATH)
            self.treinado = True
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no treinamento XGBoost: {e}")
            return False

    def prever_proximos_numeros(self, historico, top_n=8):
        """Faz previsão usando XGBoost"""
        if not XGBOOST_DISPONIVEL or not self.treinado:
            return self._previsao_fallback(historico)
            
        try:
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            if len(numeros) < 15:
                return self._previsao_fallback(historico)
            
            # Criar features para previsão
            features, _ = self.criar_features_avancadas(historico)
            if len(features) == 0:
                return self._previsao_fallback(historico)
            
            ultimas_features = features[-1].reshape(1, -1)
            probabilidades = self.model.predict_proba(ultimas_features)[0]
            
            # Pegar os números mais prováveis
            indices_mais_provaveis = np.argsort(probabilidades)[::-1]
            previsao = []
            
            for idx in indices_mais_provaveis:
                if len(previsao) >= top_n:
                    break
                num = int(idx)
                if 0 <= num <= 36 and num not in previsao:
                    previsao.append(num)
            
            # Garantir diversidade
            previsao_final = self._garantir_diversidade(previsao, historico, top_n)
            
            self.ultima_previsao = previsao_final
            logging.info(f"🎯 XGBoost previu: {self.ultima_previsao}")
            
            return self.ultima_previsao
            
        except Exception as e:
            logging.error(f"❌ Erro na previsão XGBoost: {e}")
            return self._previsao_fallback(historico)
    
    def _garantir_diversidade(self, previsao, historico, top_n):
        """Garante que a previsão tenha números diversificados"""
        if len(previsao) >= top_n:
            return previsao[:top_n]
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        diversificados = set(previsao)
        
        # Adicionar números de diferentes características
        caracteristicas = [
            [n for n in range(1, 37) if n % 2 == 0],  # Pares
            [n for n in range(1, 37) if n % 2 == 1],  # Ímpares
            PRIMEIRA_DUZIA, SEGUNDA_DUZIA, TERCEIRA_DUZIA,
            COLUNA_1, COLUNA_2, COLUNA_3
        ]
        
        for caracteristica in caracteristicas:
            for num in caracteristica:
                if len(diversificados) < top_n and num not in diversificados:
                    diversificados.add(num)
                if len(diversificados) >= top_n:
                    break
            if len(diversificados) >= top_n:
                break
        
        return list(diversificados)[:top_n]

    def _previsao_fallback(self, historico):
        """Previsão fallback quando XGBoost não está disponível"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        if len(numeros) >= NUMERO_PREVISOES:
            previsao_unica = []
            for num in numeros[-NUMERO_PREVISOES:]:
                if num not in previsao_unica:
                    previsao_unica.append(num)
                if len(previsao_unica) >= NUMERO_PREVISOES:
                    break
            return previsao_unica
        return [2, 5, 8, 11, 14, 17, 20, 23]
    
    def verificar_acerto(self, numero_sorteado):
        """Verifica se acertou a previsão"""
        if not self.ultima_previsao or numero_sorteado is None:
            return None
        
        acertou = numero_sorteado in self.ultima_previsao
        if acertou:
            self.performance["acertos"] += 1
        else:
            self.performance["erros"] += 1
        
        return acertou
    
    def get_performance(self):
        total = self.performance["acertos"] + self.performance["erros"]
        taxa = (self.performance["acertos"] / total * 100) if total > 0 else 0
        return {
            "acertos": self.performance["acertos"],
            "erros": self.performance["erros"],
            "taxa_acerto": f"{taxa:.1f}%",
            "treinado": self.treinado
        }

    def carregar_modelo(self):
        """Carrega modelo salvo"""
        try:
            if os.path.exists(XGB_MODEL_PATH):
                self.model = xgb.XGBClassifier()
                self.model.load_model(XGB_MODEL_PATH)
                self.treinado = True
                logging.info("✅ XGBoost carregado do arquivo")
                return True
        except Exception as e:
            logging.error(f"❌ Erro ao carregar XGBoost: {e}")
        return False





        
    

# =============================
# ESTRATÉGIAS DINÂMICAS BASEADAS NO HISTÓRICO
# =============================

def analisar_padroes_dinamicos(historico):
    """Analisa padrões reais do histórico sem números fixos"""
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 10:
        return None
    
    padroes = {
        'quentes': [],
        'frios': [], 
        'repetidos': [],
        'vizinhos_quentes': [],
        'ciclos': []
    }
    
    # 🎯 ANÁLISE DE NÚMEROS QUENTES (últimas 15 rodadas)
    ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
    contagem_15 = Counter(ultimos_15)
    padroes['quentes'] = [num for num, count in contagem_15.most_common(10) if count >= 2]
    
    # 🎯 ANÁLISE DE NÚMEROS FRIOS (ausentes nas últimas rodadas)
    todos_numeros = set(range(37))
    numeros_recentes = set(ultimos_15)
    padroes['frios'] = list(todos_numeros - numeros_recentes)
    
    # 🎯 PADRÕES DE REPETIÇÃO (análise temporal)
    repeticoes_recentes = []
    for i in range(1, min(8, len(numeros))):
        if numeros[-i] == numeros[-(i+1)]:
            repeticoes_recentes.append(numeros[-i])
    padroes['repetidos'] = repeticoes_recentes
    
    # 🎯 VIZINHANÇA INTELIGENTE (apenas de números quentes)
    vizinhos_estrategicos = set()
    for num in padroes['quentes'][:5]:  # Top 5 números quentes
        vizinhos = obter_vizinhos_fisicos(num)
        # Priorizar vizinhos que também são quentes
        for vizinho in vizinhos:
            if vizinho in padroes['quentes']:
                vizinhos_estrategicos.add(vizinho)
    padroes['vizinhos_quentes'] = list(vizinhos_estrategicos)
    
    return padroes

def gerar_estrategia_recuperacao_dinamica(historico, sequencia_negativa):
    """Gera estratégia 100% baseada no histórico real"""
    padroes = analisar_padroes_dinamicos(historico)
    
    if not padroes:
        return None
    
    estrategia_numeros = set()
    
    # 🚨 ESTRATÉGIA PARA SEQUÊNCIAS LONGAS (5+)
    if sequencia_negativa >= 5:
        # FOCO MÁXIMO EM NÚMEROS SUPER QUENTES
        if padroes['quentes']:
            estrategia_numeros.update(padroes['quentes'][:4])
        
        # REPETIÇÕES RECENTES (padrão mais forte)
        if padroes['repetidos']:
            estrategia_numeros.update(padroes['repetidos'][:3])
        
        # VIZINHANÇA DE NÚMEROS QUENTES
        if padroes['vizinhos_quentes']:
            estrategia_numeros.update(padroes['vizinhos_quentes'][:3])
    
    # 🔥 ESTRATÉGIA CRÍTICA (8+ erros)
    elif sequencia_negativa >= 8:
        # FOCO ABSOLUTO NOS PADRÕES MAIS FORTES
        estrategia_numeros.update(padroes['quentes'][:3])
        estrategia_numeros.update(padroes['repetidos'][:2])
        
        # ADICIONAR ALGUNS FRIOS ESTRATÉGICOS (virada de ciclo)
        if padroes['frios'] and len(estrategia_numeros) < 6:
            estrategia_numeros.update(padroes['frios'][:2])
    
    # 🔄 ESTRATÉGIA PREVENTIVA (3-4 erros)
    elif sequencia_negativa >= 3:
        # ESTRATÉGIA BALANCEADA
        if padroes['quentes']:
            estrategia_numeros.update(padroes['quentes'][:3])
        if padroes['vizinhos_quentes']:
            estrategia_numeros.update(padroes['vizinhos_quentes'][:2])
    
    # Converter para lista e limitar
    estrategia_lista = list(estrategia_numeros)
    return estrategia_lista[:8] if estrategia_lista else None

# =============================
# ESTRATÉGIA DE RECUPERAÇÃO AVANÇADA
# =============================

def ativar_modo_recuperacao_avancado(gestor, sequencia_negativa):
    """Ativa estratégias especiais para recuperação de sequências negativas"""
    estrategias = {
        3: "🔄 Modo Recuperação Leve - Reduzindo exposição",
        5: "⚠️ Modo Recuperação Moderado - Estratégia conservadora", 
        7: "🚨 Modo Recuperação Agressivo - Foco em números quentes",
        8: "🔥 MODO CRÍTICO - Estratégia máxima de recuperação"
    }
    
    estrategia = estrategias.get(sequencia_negativa, "⚡ Modo Normal")
    logging.info(f"{estrategia} (Sequência: {sequencia_negativa})")
    
    # Aplicar estratégias baseadas na sequência
    if sequencia_negativa >= 5:
        return aplicar_estrategia_recuperacao(gestor, sequencia_negativa)
    
    return None

def aplicar_estrategia_recuperacao(gestor, sequencia_negativa):
    """Aplica estratégias específicas de recuperação baseadas no histórico"""
    numeros = [h['number'] for h in gestor.historico if h.get('number') is not None]
    
    if len(numeros) < 10:
        return None
    
    estrategia_numeros = set()
    
    # ESTRATÉGIA PARA SEQUÊNCIAS LONGAS (5+)
    if sequencia_negativa >= 5:
        # Foco em números MUITO QUENTES (últimas 8 rodadas)
        ultimos_8 = numeros[-8:] if len(numeros) >= 8 else numeros
        contagem_8 = Counter(ultimos_8)
        numeros_muito_quentes = [num for num, count in contagem_8.most_common(6) if count >= 2]
        estrategia_numeros.update(numeros_muito_quentes)
        
        # Vizinhança dos últimos 3 números
        for num in numeros[-3:]:
            estrategia_numeros.update(obter_vizinhos_fisicos(num)[:2])
        
        # Padrões de repetição forte
        for i in range(1, min(4, len(numeros))):
            if numeros[-i] == numeros[-(i+1)]:
                estrategia_numeros.add(numeros[-i])
    
    # ESTRATÉGIA CRÍTICA (8+ erros)
    if sequencia_negativa >= 8:
        # Foco máximo em números RECENTES do histórico
        estrategia_numeros.update(numeros[-4:])
        
        # Adicionar números de alta probabilidade baseados no histórico
        if len(numeros) > 30:
            frequentes = Counter(numeros).most_common(8)
            estrategia_numeros.update([num for num, count in frequentes[:4]])
    
    # Limitar a 6 números para foco máximo
    estrategia_lista = list(estrategia_numeros)
    return estrategia_lista[:6] if len(estrategia_lista) >= 6 else None

# =============================
# SISTEMAS DE SUPORTE OTIMIZADOS
# =============================

class SistemaConfianca:
    def __init__(self):
        self.confianca = 0.6  # Iniciar mais conservador
        self.tendencia = "NEUTRA"
        self.historico_confianca = deque(maxlen=15)
        self.acertos_consecutivos = 0
        self.erros_consecutivos = 0
    
    def atualizar_confianca(self, acerto):
        if acerto:
            self.acertos_consecutivos += 1
            self.erros_consecutivos = 0
            
            # Bônus por acertos consecutivos
            bonus = min(0.25, self.acertos_consecutivos * 0.08)
            self.confianca = min(0.95, self.confianca + 0.12 + bonus)
            
            logging.info(f"✅ Acerto consecutivo #{self.acertos_consecutivos} - Confiança: {self.confianca:.2f}")
        else:
            self.erros_consecutivos += 1
            self.acertos_consecutivos = 0
            
            # Penalidade progressiva por erros consecutivos
            penalidade = min(0.3, self.erros_consecutivos * 0.1)
            self.confianca = max(0.2, self.confianca - 0.15 - penalidade)
            
            logging.info(f"❌ Erro consecutivo #{self.erros_consecutivos} - Confiança: {self.confianca:.2f}")
        
        self.historico_confianca.append(self.confianca)
        
        # Atualizar tendência
        if len(self.historico_confianca) >= 3:
            ultimos_3 = list(self.historico_confianca)[-3:]
            if all(c > 0.7 for c in ultimos_3):
                self.tendencia = "MUITO ALTA"
            elif all(c > 0.5 for c in ultimos_3):
                self.tendencia = "ALTA"
            elif all(c < 0.3 for c in ultimos_3):
                self.tendencia = "MUITO BAIXA"
            elif all(c < 0.4 for c in ultimos_3):
                self.tendencia = "BAIXA"
            else:
                self.tendencia = "NEUTRA"
    
    def get_confianca_categoria(self):
        if self.confianca > 0.75:
            return "MUITO ALTA"
        elif self.confianca > 0.6:
            return "ALTA"
        elif self.confianca > 0.4:
            return "MODERADA"
        elif self.confianca > 0.25:
            return "BAIXA"
        else:
            return "MUITO BAIXA"

class SistemaGestaoRisco:
    def __init__(self):
        self.entradas_recentes = deque(maxlen=8)
        self.resultados_recentes = deque(maxlen=8)
        self.sequencia_atual = 0
        self.max_sequencia_negativa = 0
        self.taxa_acerto_recente = 0.5
    
    def deve_entrar(self, analise_risco, confianca, historico_size, sequencia_negativa=None):
        """CRITÉRIOS SUPER OTIMIZADOS - COM RECUPERAÇÃO INTELIGENTE"""
        
        # Atualizar taxa de acerto recente
        if len(self.resultados_recentes) > 0:
            self.taxa_acerto_recente = self.resultados_recentes.count("GREEN") / len(self.resultados_recentes)
        
        # 🔴 NÃO ENTRAR EM CONDIÇÕES CRÍTICAS
        if self.sequencia_atual >= 8:
            logging.warning("⛔ SEQUÊNCIA CRÍTICA - Não entrar até recuperação")
            return False
            
        if confianca < 0.2:
            logging.warning("⛔ Confiança extremamente baixa - não entrar")
            return False
            
        if self.taxa_acerto_recente < 0.15 and len(self.resultados_recentes) >= 6:
            logging.warning("⛔ Performance recente catastrófica - não entrar")
            return False
        
        # 🟡 MODERAÇÃO PARA SEQUÊNCIAS NEGATIVAS
        if self.sequencia_atual >= 5:
            # Apenas entradas de ALTA qualidade
            if not (analise_risco == "RISCO_BAIXO" and confianca > 0.6):
                logging.warning("🟡 Sequência negativa - apenas entradas premium")
                return False
        
        # 🟢 CONDIÇÕES IDEAIS
        if analise_risco == "RISCO_BAIXO" and confianca > 0.5:
            return True
            
        if analise_risco == "RISCO_MODERADO" and confianca > 0.65:
            return True
            
        if self.taxa_acerto_recente > 0.45 and confianca > 0.4:
            return True
        
        # 🔄 MODO RECUPERAÇÃO CONTROLADO
        if self.sequencia_atual >= 3 and confianca > 0.35 and analise_risco != "RISCO_ALTO":
            logging.info("🔄 Entrada em modo recuperação controlada")
            return True
            
        return False
    
    def calcular_tamanho_aposta(self, confianca, saldo=1000):
        base = saldo * 0.015  # Reduzido base para 1.5%
        
        # Ajustar base pela sequência atual
        if self.sequencia_atual >= 3:
            base *= 0.7  # Reduzir após 3 erros consecutivos
        
        if confianca > 0.75:
            return base * 1.8
        elif confianca > 0.6:
            return base * 1.4
        elif confianca > 0.45:
            return base
        elif confianca > 0.3:
            return base * 0.8
        else:
            return base * 0.6
    
    def atualizar_sequencia(self, resultado):
        if resultado == "GREEN":
            self.sequencia_atual = 0
            self.resultados_recentes.append("GREEN")
        else:
            self.sequencia_atual += 1
            self.max_sequencia_negativa = max(self.max_sequencia_negativa, self.sequencia_atual)
            self.resultados_recentes.append("RED")

# =============================
# SISTEMA DE PREVISÃO SEQUENCIAL MELHORADO
# =============================

class SistemaPrevisaoSequencial:
    def __init__(self):
        self.historico_sequencias = {}
        self.performance_sequencial = {"acertos": 0, "erros": 0}
        self.ultima_previsao = []
        
    def analisar_sequencias_historicas(self, historico, numero_atual):
        """Análise MAIS AGRESSIVA e INTELIGENTE de sequências"""
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 15:
            return []
        
        sequencias_encontradas = []
        
        # ESTRATÉGIA 1: Próximos números APÓS o número atual
        for i in range(len(numeros) - 1):
            if numeros[i] == numero_atual:
                for j in range(1, min(9, len(numeros) - i)):
                    sequencias_encontradas.append(numeros[i + j])
        
        # ESTRATÉGIA 2: Padrões de repetição em intervalos específicos
        padroes_intervalo = []
        for i in range(len(numeros) - 8):
            if numeros[i] == numero_atual:
                if i + 2 < len(numeros):
                    padroes_intervalo.append(numeros[i + 2])
                if i + 3 < len(numeros):
                    padroes_intervalo.append(numeros[i + 3])
        
        # ESTRATÉGIA 3: Números que são VIZINHOS dos que saem após
        vizinhos_sequencia = []
        for num in sequencias_encontradas[:15]:
            vizinhos_sequencia.extend(obter_vizinhos_fisicos(num))
        
        # COMBINAR TODAS AS ESTRATÉGIAS
        todas_sequencias = sequencias_encontradas + padroes_intervalo + vizinhos_sequencia
        
        if not todas_sequencias:
            return []
        
        # Contar frequência COM PESOS
        contador = Counter(todas_sequencias)
        
        # Dar peso extra para sequências diretas
        for num in sequencias_encontradas:
            contador[num] += 2
        
        # Pegar os 12 números mais frequentes
        numeros_mais_frequentes = [num for num, count in contador.most_common(12)]
        
        logging.info(f"🔍 Sequência histórica APÓS {numero_atual}: {len(sequencias_encontradas)} ocorrências, tops: {numeros_mais_frequentes[:6]}")
        
        return numeros_mais_frequentes
    
    def gerar_previsao_sequencial(self, historico, ultimo_numero):
        """Gera previsão MAIS INTELIGENTE baseada em múltiplos fatores - CORREÇÃO: SEM DUPLICATAS"""
        
        if not historico or ultimo_numero is None:
            return []
        
        previsao_sequencial = self.analisar_sequencias_historicas(historico, ultimo_numero)
        
        if len(previsao_sequencial) < 6:
            previsao_sequencial = self.estrategia_fallback_agressiva(historico, ultimo_numero)
        
        # CORREÇÃO: REMOVER DUPLICATAS E LIMITAR A 8 NÚMEROS ÚNICOS
        previsao_unica = []
        for num in previsao_sequencial:
            if num not in previsao_unica and len(previsao_unica) < NUMERO_PREVISOES:
                previsao_unica.append(num)
        
        self.ultima_previsao = previsao_unica
        logging.info(f"🎯 Previsão Sequencial GERADA: {len(previsao_unica)} números ÚNICOS: {previsao_unica}")
        return previsao_unica
    
    def estrategia_fallback_agressiva(self, historico, ultimo_numero):
        """Estratégia alternativa AGRESSIVA - CORREÇÃO: SEM DUPLICATAS"""
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return []
        
        previsao = set()
        
        # ESTRATÉGIA 1: VIZINHOS DO ÚLTIMO NÚMERO
        previsao.update(obter_vizinhos_fisicos(ultimo_numero))
        
        # ESTRATÉGIA 2: NÚMEROS QUENTES (últimas 15 rodadas)
        ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
        contagem_recente = Counter(ultimos_15)
        numeros_quentes = [num for num, count in contagem_recente.most_common(8) if count >= 2]
        previsao.update(numeros_quentes)
        
        # ESTRATÉGIA 3: NÚMEROS DA MESMA CARACTERÍSTICA
        if ultimo_numero != 0:
            if ultimo_numero % 2 == 0:
                previsao.update([n for n in range(1, 37) if n % 2 == 0 and n != ultimo_numero][:3])
            else:
                previsao.update([n for n in range(1, 37) if n % 2 == 1 and n != ultimo_numero][:3])
        
        # ESTRATÉGIA 4: COMPLETAR COM FREQUENTES ÚNICOS
        if len(previsao) < NUMERO_PREVISOES:
            frequentes = Counter(numeros).most_common(15)  # Aumentado para 15
            for num, count in frequentes:
                if len(previsao) < NUMERO_PREVISOES and num not in previsao:
                    previsao.add(num)
        
        return list(previsao)
    
    def verificar_acerto_sequencial(self, numero_sorteado):
        """Verifica se a ÚLTIMA previsão sequencial acertou"""
        if not self.ultima_previsao or numero_sorteado is None:
            return None
        
        acertou = numero_sorteado in self.ultima_previsao
        if acertou:
            self.performance_sequencial["acertos"] += 1
            logging.info(f"✅ ACERTO SEQUENCIAL! {numero_sorteado} estava em {self.ultima_previsao}")
        else:
            self.performance_sequencial["erros"] += 1
            logging.info(f"❌ ERRO SEQUENCIAL: {numero_sorteado} não estava em {self.ultima_previsao}")
        
        return acertou
    
    def get_performance_sequencial(self):
        """Retorna performance do sistema sequencial"""
        total = self.performance_sequencial["acertos"] + self.performance_sequencial["erros"]
        taxa = (self.performance_sequencial["acertos"] / total * 100) if total > 0 else 0
        return {
            "acertos": self.performance_sequencial["acertos"],
            "erros": self.performance_sequencial["erros"],
            "taxa_acerto": f"{taxa:.1f}%",
            "total_analises": total
        }

# =============================
# UTILITÁRIOS
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": msg,
            "parse_mode": "Markdown"
        }
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
    """Retorna vizinhos físicos na mesa baseado no histórico de disposição"""
    if numero == 0:
        return [32, 15, 19, 4, 21, 2, 25]
    
    vizinhos = set()
    
    for col_idx, coluna in enumerate(ROULETTE_PHYSICAL_LAYOUT):
        if numero in coluna:
            num_idx = coluna.index(numero)
            
            if num_idx > 0:
                vizinhos.add(coluna[num_idx - 1])
            if num_idx < len(coluna) - 1:
                vizinhos.add(coluna[num_idx + 1])
                
            if col_idx > 0:
                if num_idx < len(ROULETTE_PHYSICAL_LAYOUT[col_idx - 1]):
                    vizinhos.add(ROULETTE_PHYSICAL_LAYOUT[col_idx - 1][num_idx])
            if col_idx < 2:
                if num_idx < len(ROULETTE_PHYSICAL_LAYOUT[col_idx + 1]):
                    vizinhos.add(ROULETTE_PHYSICAL_LAYOUT[col_idx + 1][num_idx])
    
    return list(vizinhos)

def validar_previsao(previsao):
    """Valida e remove duplicatas da previsão"""
    if not previsao or not isinstance(previsao, list):
        return []
    
    # CORREÇÃO: REMOVER DUPLICATAS E FILTRAR VÁLIDOS
    previsao_limpa = []
    vistos = set()
    
    for num in previsao:
        if (num is not None and 
            isinstance(num, (int, float)) and 
            0 <= num <= 36 and 
            num not in vistos):
            
            previsao_limpa.append(int(num))
            vistos.add(num)
    
    return previsao_limpa

# =============================
# SISTEMA ESPECIALISTA 100% BASEADO EM HISTÓRICO COM XGBOOST
# =============================
class IA_Assertiva:
    def __init__(self):
        self.historico_analises = deque(maxlen=50)
        self.previsao_sequencial = SistemaPrevisaoSequencial()
        self.xgboost_ia = XGBoostRoletaIA()
        self.modo_xgboost_ativo = False
        
        # Tentar carregar modelo XGBoost existente
        if XGBOOST_DISPONIVEL:
            self.xgboost_ia.carregar_modelo()
            if self.xgboost_ia.treinado:
                self.modo_xgboost_ativo = True
                logging.info("✅ XGBoost carregado e ativo")
        
    def prever_com_alta_assertividade(self, historico, ultimo_numero=None):
        """Sistema PRINCIPAL - VERSÃO OTIMIZADA PARA MAIOR ASSERTIVIDADE"""
        
        # PRIORIDADE 1: XGBOOST SE ESTIVER TREINADO
        if self.xgboost_ia.treinado and XGBOOST_DISPONIVEL:
            self.modo_xgboost_ativo = True
            try:
                previsao_xgb = self.xgboost_ia.prever_proximos_numeros(historico, NUMERO_PREVISOES)
                if previsao_xgb and len(previsao_xgb) >= 6:
                    logging.info("🎯 XGBOOST ATIVO - Previsão via Machine Learning")
                    return previsao_xgb
            except Exception as e:
                logging.error(f"❌ Erro no XGBoost: {e}")
                self.modo_xgboost_ativo = False
        
        # PRIORIDADE 2: TREINAR XGBOOST SE TIVER DADOS SUFICIENTES
        if not self.xgboost_ia.treinado and len(historico) >= 50 and XGBOOST_DISPONIVEL:
            logging.info("🤖 Tentando treinar XGBoost automaticamente...")
            try:
                if self.xgboost_ia.treinar_modelo(historico):
                    self.modo_xgboost_ativo = True
                    previsao_xgb = self.xgboost_ia.prever_proximos_numeros(historico, NUMERO_PREVISOES)
                    if previsao_xgb and len(previsao_xgb) >= 6:
                        return previsao_xgb
            except Exception as e:
                logging.error(f"❌ Treinamento automático falhou: {e}")
        
        # PRIORIDADE 3: PREVISÃO SEQUENCIAL INTELIGENTE
        self.modo_xgboost_ativo = False
        if ultimo_numero is not None and len(historico) >= 10:
            previsao_seq = self.previsao_sequencial.gerar_previsao_sequencial(historico, ultimo_numero)
            if previsao_seq and len(previsao_seq) >= 6:
                logging.info(f"🔄 PREVISÃO SEQUENCIAL para {ultimo_numero}")
                return previsao_seq
        
        # PRIORIDADE 4: ESTRATÉGIA AGRESSIVA OTIMIZADA
        logging.info("📊 Usando estratégia alternativa OTIMIZADA")
        return self.estrategia_alternativa_otimizada(historico, ultimo_numero)

    def gerar_previsao_recuperacao(self, historico, sequencia_negativa):
        """Gera previsão OTIMIZADA para recuperação de sequências negativas"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 8:
            return None
        
        previsao_recuperacao = set()
        
        # 🎯 ESTRATÉGIA 1: NÚMEROS SUPER QUENTES
        ultimos_10 = numeros[-10:] if len(numeros) >= 10 else numeros
        contagem_10 = Counter(ultimos_10)
        super_quentes = [num for num, count in contagem_10.most_common(8) if count >= 2]
        previsao_recuperacao.update(super_quentes[:4])  # Top 4 mais quentes
        
        # 🎯 ESTRATÉGIA 2: PADRÕES FORTES DE REPETIÇÃO
        padroes_fortes = []
        for i in range(1, min(6, len(numeros))):
            if numeros[-i] == numeros[-(i+1)]:
                padroes_fortes.append(numeros[-i])
                if len(padroes_fortes) >= 2:
                    break
        
        previsao_recuperacao.update(padroes_fortes)
        
        # 🎯 ESTRATÉGIA 3: VIZINHANÇA INTELIGENTE
        vizinhos_estrategicos = set()
        for num in numeros[-3:]:
            vizinhos = obter_vizinhos_fisicos(num)
            # Priorizar vizinhos que também são quentes
            vizinhos_quentes = [v for v in vizinhos if v in super_quentes]
            vizinhos_estrategicos.update(vizinhos_quentes[:2])
        
        previsao_recuperacao.update(vizinhos_estrategicos)
        
        # 🎯 ESTRATÉGIA 4: NÚMEROS DE ALTA FREQUÊNCIA HISTÓRICA
        if len(numeros) > 30:
            frequentes_historico = Counter(numeros).most_common(8)
            for num, count in frequentes_historico[:3]:
                if num not in previsao_recuperacao:
                    previsao_recuperacao.add(num)
                    break
        
        previsao_lista = list(previsao_recuperacao)
        return previsao_lista[:8] if len(previsao_lista) >= 6 else None
    
    def estrategia_alternativa_otimizada(self, historico, ultimo_numero=None):
        """Estratégia OTIMIZADA baseada em múltiplos fatores de alta probabilidade"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 8:
            return [2, 5, 8, 11, 14, 17, 20, 23]
        
        previsao = set()
        
        # FATOR 1: ÚLTIMOS NÚMEROS (alta probabilidade de repetição)
        previsao.update(numeros[-4:])  # Aumentado para 4 últimos
        
        # FATOR 2: VIZINHOS DOS ÚLTIMOS 2 NÚMEROS
        if ultimo_numero is not None:
            previsao.update(obter_vizinhos_fisicos(ultimo_numero))
            if len(numeros) >= 2:
                previsao.update(obter_vizinhos_fisicos(numeros[-2]))
        
        # FATOR 3: NÚMEROS QUENTES (últimas 12 rodadas)
        ultimos_12 = numeros[-12:] if len(numeros) >= 12 else numeros
        contagem_recente = Counter(ultimos_12)
        numeros_quentes = [num for num, count in contagem_recente.most_common(8) if count >= 1]  # Reduzido threshold
        previsao.update(numeros_quentes)
        
        # FATOR 4: PADRÕES DE REPETIÇÃO
        for i in range(1, min(5, len(numeros))):
            if numeros[-i] == numeros[-(i+1)]:
                previsao.add(numeros[-i])
        
        # FATOR 5: NÚMEROS COM ATRASO (não saem há mais de 8 rodadas)
        if len(numeros) > 15:
            for num in range(0, 37):
                if num in numeros:
                    ultima_ocorrencia = len(numeros) - 1 - numeros[::-1].index(num)
                    atraso = len(numeros) - ultima_ocorrencia
                    if atraso > 8 and len(previsao) < NUMERO_PREVISOES:
                        previsao.add(num)
        
        # FATOR 6: COMPLETAR COM CARACTERÍSTICAS DO ÚLTIMO NÚMERO
        if ultimo_numero is not None and ultimo_numero != 0:
            # Mesma paridade
            if ultimo_numero % 2 == 0:
                pares = [n for n in range(2, 37, 2) if n not in previsao]
                previsao.update(pares[:2])
            else:
                impares = [n for n in range(1, 36, 2) if n not in previsao]
                previsao.update(impares[:2])
            
            # Mesma dúzia
            if ultimo_numero in PRIMEIRA_DUZIA:
                previsao.update([n for n in PRIMEIRA_DUZIA if n not in previsao][:1])
            elif ultimo_numero in SEGUNDA_DUZIA:
                previsao.update([n for n in SEGUNDA_DUZIA if n not in previsao][:1])
            else:
                previsao.update([n for n in TERCEIRA_DUZIA if n not in previsao][:1])
        
        # GARANTIR EXATAMENTE 8 NÚMEROS DIVERSIFICADOS
        previsao_lista = list(previsao)
        if len(previsao_lista) > NUMERO_PREVISOES:
            # Priorizar números mais recentes e quentes
            priorizados = []
            for num in previsao_lista:
                score = 0
                if num in numeros[-3:]: score += 3
                if num in numeros_quentes: score += 2
                if num in ultimos_12: score += 1
                priorizados.append((num, score))
            
            priorizados.sort(key=lambda x: x[1], reverse=True)
            return [num for num, score in priorizados[:NUMERO_PREVISOES]]
        
        # COMPLETAR SE NECESSÁRIO
        if len(previsao_lista) < NUMERO_PREVISOES:
            for i in range(0, 37):
                if len(previsao_lista) < NUMERO_PREVISOES and i not in previsao_lista:
                    previsao_lista.append(i)
        
        return previsao_lista[:NUMERO_PREVISOES]
    
    def get_performance_sequencial(self):
        """Retorna performance do sistema sequencial"""
        return self.previsao_sequencial.get_performance_sequencial()
    
    def get_status_xgboost(self):
        """Retorna status do XGBoost"""
        return {
            "treinado": self.xgboost_ia.treinado,
            "ativo": self.modo_xgboost_ativo,
            "performance": self.xgboost_ia.get_performance()
        }
    
    def treinar_xgboost(self, historico, force_retrain=False):
        """Treina o XGBoost"""
        return self.xgboost_ia.treinar_modelo(historico, force_retrain)

# =============================
# GESTOR PRINCIPAL 100% BASEADO EM HISTÓRICO COM XGBOOST
# =============================
class GestorAssertivo:
    def __init__(self):
        self.ia_assertiva = IA_Assertiva()
        self.historico = deque(carregar_historico(), maxlen=5000)
        
    def adicionar_numero(self, numero_dict):
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
    def treinar_xgboost(self, force_retrain=False):
        """Método para treinar XGBoost"""
        return self.ia_assertiva.treinar_xgboost(self.historico, force_retrain)
    
    def get_status_xgboost(self):
        """Retorna status do XGBoost"""
        return self.ia_assertiva.get_status_xgboost()
        
    def gerar_previsao_assertiva(self, ultimo_numero=None):
        try:
            previsao = self.ia_assertiva.prever_com_alta_assertividade(self.historico, ultimo_numero)
            previsao_validada = validar_previsao(previsao)
            
            # GARANTIR SEMPRE 8 NÚMEROS BASEADOS NO HISTÓRICO
            if len(previsao_validada) < NUMERO_PREVISOES:
                logging.warning(f"⚠️ Previsão com {len(previsao_validada)} números. Completando com histórico...")
                previsao_validada = self.completar_com_historico(previsao_validada)
            
            logging.info(f"✅ Previsão ASSERTIVA gerada: {len(previsao_validada)} números ÚNICOS")
            return previsao_validada
            
        except Exception as e:
            logging.error(f"Erro ao gerar previsão: {e}")
            # Em caso de erro, usar os últimos números do histórico
            numeros = [h['number'] for h in self.historico if h.get('number') is not None]
            # CORREÇÃO: REMOVER DUPLICATAS
            numeros_unicos = []
            for num in numeros[-NUMERO_PREVISOES*2:]:
                if num not in numeros_unicos:
                    numeros_unicos.append(num)
                if len(numeros_unicos) >= NUMERO_PREVISOES:
                    break
            return numeros_unicos[:NUMERO_PREVISOES]
    
    def completar_com_historico(self, previsao):
        """Completa sempre para 8 números USANDO APENAS HISTÓRICO - CORREÇÃO: SEM DUPLICATAS"""
        if len(previsao) >= NUMERO_PREVISOES:
            # CORREÇÃO: REMOVER DUPLICATAS MESMO SE JÁ TEMOS 8+
            previsao_unica = list(set(previsao))
            return previsao_unica[:NUMERO_PREVISOES]
        
        numeros_completos = set(previsao)  # CORREÇÃO: USAR SET PARA EVITAR DUPLICATAS
        numeros_historico = [h['number'] for h in self.historico if h.get('number') is not None]
        
        # COMPLETAR COM NÚMEROS DO HISTÓRICO EM ORDEM DE PRIORIDADE:
        
        # 1. Últimos números sorteados (ÚNICOS)
        for num in reversed(numeros_historico):
            if len(numeros_completos) < NUMERO_PREVISOES and num not in numeros_completos:
                numeros_completos.add(num)
        
        # 2. Números mais frequentes no histórico (ÚNICOS)
        if len(numeros_completos) < NUMERO_PREVISOES:
            frequentes = Counter(numeros_historico).most_common(25)  # Aumentado para 25
            for num, count in frequentes:
                if len(numeros_completos) < NUMERO_PREVISOES and num not in numeros_completos:
                    numeros_completos.add(num)
        
        # 3. Números que são vizinhos de números recentes (ÚNICOS)
        if len(numeros_completos) < NUMERO_PREVISOES:
            for num_recente in numeros_historico[-3:]:
                vizinhos = obter_vizinhos_fisicos(num_recente)
                for vizinho in vizinhos:
                    if len(numeros_completos) < NUMERO_PREVISOES and vizinho not in numeros_completos:
                        numeros_completos.add(vizinho)
        
        # 4. ÚLTIMO RECURSO: números sequenciais únicos
        if len(numeros_completos) < NUMERO_PREVISOES:
            for i in range(0, 37):
                if len(numeros_completos) < NUMERO_PREVISOES and i not in numeros_completos:
                    numeros_completos.add(i)
        
        return list(numeros_completos)[:NUMERO_PREVISOES]
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            
            if historico_size < FASE_INICIAL:
                return "🟡 Iniciando", "Baseado em Histórico"
            elif historico_size < FASE_INTERMEDIARIA:
                return "🟠 Desenvolvendo", "Padrões Históricos"
            elif historico_size < FASE_AVANCADA:
                return "🟢 IA Ativa", "Tendências Históricas"
            else:
                return "🎯 ASSERTIVO", "Alta Probabilidade Histórica"
                
        except:
            return "⚪ Sistema", "Carregando..."
    
    def get_analise_detalhada(self):
        """Análise simplificada mas efetiva BASEADA NO HISTÓRICO"""
        if not self.historico:
            return {
                "modo_assertivo": False,
                "historico_total": 0,
                "confianca": "Baixa",
                "estrategia_ativa": "Inicial"
            }
        
        historico_size = len(self.historico)
        modo_assertivo = historico_size >= FASE_AVANCADA
        
        analise = analisar_padroes_dinamicos(self.historico)
        
        return {
            "modo_assertivo": modo_assertivo,
            "historico_total": historico_size,
            "confianca": "Alta" if historico_size > 100 else "Média" if historico_size > 50 else "Baixa",
            "estrategia_ativa": "Núcleo Histórico",
            "numeros_quentes": analise.get("numeros_quentes", []) if analise else [],
            "padrao_detectado": len(analise.get("padroes_repeticao", [])) > 0 if analise else False
        }
    
    def get_performance_sequencial(self):
        """Retorna performance do sistema sequencial"""
        return self.ia_assertiva.get_performance_sequencial()

# =============================
# STREAMLIT APP 100% BASEADO EM HISTÓRICO COM XGBOOST
# =============================
st.set_page_config(
    page_title="Roleta - IA Baseada em Histórico", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 SISTEMA 100% BASEADO EM HISTÓRICO COM XGBOOST")
st.markdown("### **Estratégia com 8 Números Baseada Exclusivamente no Histórico + Machine Learning Avançado**")

st_autorefresh(interval=3000, key="refresh")

# =============================
# INICIALIZAÇÃO CORRIGIDA DO session_state
# =============================

# Inicialização SEGURA do session_state
if 'gestor' not in st.session_state:
    st.session_state.gestor = GestorAssertivo()

if 'previsao_atual' not in st.session_state:
    st.session_state.previsao_atual = []

if 'acertos' not in st.session_state:
    st.session_state.acertos = 0

if 'erros' not in st.session_state:
    st.session_state.erros = 0

if 'contador_rodadas' not in st.session_state:
    st.session_state.contador_rodadas = 0

if 'ultimo_timestamp' not in st.session_state:
    st.session_state.ultimo_timestamp = None

if 'ultimo_numero' not in st.session_state:
    st.session_state.ultimo_numero = None

if 'status_ia' not in st.session_state:
    st.session_state.status_ia = "🟡 Inicializando"

if 'estrategia_atual' not in st.session_state:
    st.session_state.estrategia_atual = "Aguardando dados"

if 'ultima_entrada_estrategica' not in st.session_state:
    st.session_state.ultima_entrada_estrategica = []

if 'resultado_entrada_anterior' not in st.session_state:
    st.session_state.resultado_entrada_anterior = None

if 'sistema_confianca' not in st.session_state:
    st.session_state.sistema_confianca = SistemaConfianca()

if 'gestor_risco' not in st.session_state:
    st.session_state.gestor_risco = SistemaGestaoRisco()

if 'ultimos_resultados' not in st.session_state:
    st.session_state.ultimos_resultados = []

# Validar previsão atual
st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL 100% BASEADO EM HISTÓRICO - VERSÃO CORRIGIDA
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

        # VERIFICAR ENTRADA ANTERIOR
        entrada_anterior = st.session_state.get('ultima_entrada_estrategica', [])
        if entrada_anterior and numero_real is not None:
            acertou = numero_real in entrada_anterior
            st.session_state.sistema_confianca.atualizar_confianca(acertou)
            st.session_state.gestor_risco.atualizar_sequencia("GREEN" if acertou else "RED")
            
            if acertou:
                st.session_state.acertos += 1
                st.session_state.resultado_entrada_anterior = "GREEN"
                mensagem_green = f"✅ **GREEN!** Acertamos {numero_real}!"
                enviar_telegram(mensagem_green, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
            else:
                st.session_state.erros += 1
                st.session_state.resultado_entrada_anterior = "RED"
                mensagem_red = f"❌ **RED** {numero_real} não estava"
                enviar_telegram(mensagem_red, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)

        # ATUALIZAR HISTÓRICO DE RESULTADOS
        if st.session_state.resultado_entrada_anterior:
            st.session_state.ultimos_resultados.append(st.session_state.resultado_entrada_anterior)
            if len(st.session_state.ultimos_resultados) > 10:
                st.session_state.ultimos_resultados.pop(0)

        # VERIFICAR ACERTO DA PREVISÃO SEQUENCIAL
        if st.session_state.ultimo_numero:
            st.session_state.gestor.ia_assertiva.previsao_sequencial.verificar_acerto_sequencial(numero_real)

        # VERIFICAR ACERTO DO XGBOOST
        if st.session_state.ultimo_numero:
            st.session_state.gestor.ia_assertiva.xgboost_ia.verificar_acerto(numero_real)

        # VERIFICAR SEQUÊNCIA NEGATIVA E ATIVAR RECUPERAÇÃO
        sequencia_negativa = st.session_state.gestor_risco.sequencia_atual
        modo_recuperacao_avancado = sequencia_negativa >= 5

        if modo_recuperacao_avancado:
            logging.warning(f"🚨 SEQUÊNCIA NEGATIVA: {sequencia_negativa} - Ativando modo recuperação...")
            
            # Gerar previsão especial de recuperação
            previsao_recuperacao = st.session_state.gestor.ia_assertiva.gerar_previsao_recuperacao(
                list(st.session_state.gestor.historico), 
                sequencia_negativa
            )
            
            if previsao_recuperacao and len(previsao_recuperacao) >= 6:
                st.session_state.previsao_atual = validar_previsao(previsao_recuperacao)
                st.warning(f"🔧 MODO RECUPERAÇÃO ATIVO - Sequência: {sequencia_negativa}")
            else:
                # Estratégia de recuperação alternativa
                estrategia_recuperacao = aplicar_estrategia_recuperacao(
                    st.session_state.gestor, 
                    sequencia_negativa
                )
                if estrategia_recuperacao:
                    st.session_state.previsao_atual = validar_previsao(estrategia_recuperacao)

        # GERAR NOVA PREVISÃO BASEADA NO HISTÓRICO (se não em recuperação)
        if not modo_recuperacao_avancado or len(st.session_state.previsao_atual) < 6:
            nova_previsao = st.session_state.gestor.gerar_previsao_assertiva(st.session_state.ultimo_numero)
            st.session_state.previsao_atual = validar_previsao(nova_previsao)

        # GERAR ENTRADA ULTRA ASSERTIVA (usar previsão diretamente)
        entrada_assertiva = st.session_state.previsao_atual
        
        # Calcular performance
        total = st.session_state.acertos + st.session_state.erros
        taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
        performance = {
            'acertos': st.session_state.acertos,
            'erros': st.session_state.erros,
            'taxa_acerto': f"{taxa_acerto:.1f}%"
        }
        
        # LÓGICA DE DECISÃO COM GESTÃO DE RISCO
        confianca_atual = st.session_state.sistema_confianca.confianca
        
        # Análise de risco baseada no histórico
        def analisar_risco_entrada(historico, entrada_proposta):
            if len(historico) < 5:
                return "RISCO_MODERADO"
            
            numeros = [h['number'] for h in historico]
            ultimos_8 = numeros[-8:] if len(numeros) >= 8 else numeros
            
            # Verificar quantos dos números propostos saíram recentemente
            acertos_previstos = len(set(ultimos_8) & set(entrada_proposta))
            
            if acertos_previstos >= 2:
                return "RISCO_BAIXO"
            elif acertos_previstos >= 1:
                return "RISCO_MODERADO"
            else:
                return "RISCO_ALTO"

        risco_entrada = analisar_risco_entrada(
            list(st.session_state.gestor.historico), 
            entrada_assertiva
        )
        
        # DECISÃO FINAL DE ENTRADA
        deve_entrar = st.session_state.gestor_risco.deve_entrar(
            risco_entrada, 
            confianca_atual,
            len(st.session_state.gestor.historico),
            sequencia_negativa
        )
        
        # ENVIAR ALERTA ASSERTIVO
        if deve_entrar and entrada_assertiva:
            # Função simplificada de envio
            def enviar_alerta_inteligente(entrada_estrategica, confianca, performance):
                numeros_ordenados = sorted(entrada_estrategica)
                primeira_linha = '   '.join(map(str, numeros_ordenados[:4]))
                segunda_linha = '   '.join(map(str, numeros_ordenados[4:]))
                mensagem = f"{primeira_linha}\n{segunda_linha}"
                enviar_telegram(mensagem, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)

            enviar_alerta_inteligente(entrada_assertiva, confianca_atual, performance)
            st.session_state.ultima_entrada_estrategica = entrada_assertiva
            logging.info(f"✅ Entrada enviada - Risco: {risco_entrada}, Confiança: {confianca_atual:.2f}")
        else:
            logging.warning(f"⏹️ Entrada não enviada - Risco: {risco_entrada}, Confiança: {confianca_atual:.2f}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro no processamento: {e}")
    st.error("🔴 Erro no processamento - usando fallback...")
    # Em caso de erro, usar os últimos números do histórico
    numeros = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
    numeros_unicos = []
    for num in numeros[-NUMERO_PREVISOES*2:]:
        if num not in numeros_unicos:
            numeros_unicos.append(num)
        if len(numeros_unicos) >= NUMERO_PREVISOES:
            break
    st.session_state.previsao_atual = numeros_unicos[:NUMERO_PREVISOES]

# =============================
# INTERFACE STREAMLIT ATUALIZADA
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

# RESULTADO ENTRADA ANTERIOR
if st.session_state.resultado_entrada_anterior:
    if st.session_state.resultado_entrada_anterior == "GREEN":
        st.success(f"✅ **ENTRADA ANTERIOR: GREEN!** Acertamos {st.session_state.ultimo_numero}!")
    else:
        st.error(f"❌ **ENTRADA ANTERIOR: RED** {st.session_state.ultimo_numero} não estava")

# SEÇÃO: XGBOOST - MACHINE LEARNING
st.markdown("---")
st.subheader("🤖 IA XGBoost - Machine Learning")

xgboost_status = st.session_state.gestor.get_status_xgboost()

col1, col2, col3, col4 = st.columns(4)
with col1:
    status_icon = "✅" if xgboost_status["treinado"] else "🔄"
    st.metric("XGBoost Status", f"{status_icon} {'Treinado' if xgboost_status['treinado'] else 'Treinando'}")
with col2:
    modo_icon = "🎯" if xgboost_status["ativo"] else "📊"
    st.metric("Modo Ativo", f"{modo_icon} {'XGBoost' if xgboost_status['ativo'] else 'Sequencial'}")
with col3:
    st.metric("Acertos ML", xgboost_status["performance"]["acertos"])
with col4:
    st.metric("Assertividade ML", xgboost_status["performance"]["taxa_acerto"])

# Controles XGBoost
if XGBOOST_DISPONIVEL:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🤖 Treinar XGBoost Agora"):
            with st.spinner("Treinando modelo de Machine Learning..."):
                sucesso = st.session_state.gestor.treinar_xgboost()
                if sucesso:
                    st.success("✅ XGBoost treinado com sucesso!")
                else:
                    st.error("❌ Falha no treinamento. Mais dados necessários")
    with col2:
        if st.button("🔄 Forçar Re-treinamento"):
            with st.spinner("Re-treinando modelo..."):
                sucesso = st.session_state.gestor.treinar_xgboost(force_retrain=True)
                if sucesso:
                    st.success("✅ XGBoost re-treinado!")
                else:
                    st.warning("⚠️ Verifique se tem dados suficientes")
else:
    st.warning("⚠️ XGBoost não disponível - usando métodos tradicionais")

# SEÇÃO: STATUS DE RECUPERAÇÃO
st.markdown("---")
st.subheader("🔄 Status de Recuperação")

sequencia_atual = st.session_state.gestor_risco.sequencia_atual
confianca_atual = st.session_state.sistema_confianca.confianca

col1, col2, col3 = st.columns(3)

with col1:
    if sequencia_atual == 0:
        st.success("✅ **Sequência:** Normal")
    elif sequencia_atual <= 2:
        st.info(f"🔸 **Sequência:** {sequencia_atual}")
    elif sequencia_atual <= 4:
        st.warning(f"⚠️ **Sequência:** {sequencia_atual}")
    else:
        st.error(f"🚨 **Sequência:** {sequencia_atual}")

with col2:
    if confianca_atual > 0.6:
        st.success(f"💪 **Confiança:** {confianca_atual:.1%}")
    elif confianca_atual > 0.4:
        st.info(f"📊 **Confiança:** {confianca_atual:.1%}")
    elif confianca_atual > 0.25:
        st.warning(f"🔻 **Confiança:** {confianca_atual:.1%}")
    else:
        st.error(f"⛔ **Confiança:** {confianca_atual:.1%}")

with col3:
    taxa_recente = st.session_state.gestor_risco.taxa_acerto_recente
    if taxa_recente > 0.4:
        st.success(f"📈 **Taxa Recente:** {taxa_recente:.1%}")
    elif taxa_recente > 0.25:
        st.info(f"📊 **Taxa Recente:** {taxa_recente:.1%}")
    else:
        st.warning(f"🔻 **Taxa Recente:** {taxa_recente:.1%}")

# Botão de recuperação emergencial
if sequencia_atual >= 5:
    st.markdown("---")
    st.error("🚨 **MODO RECUPERAÇÃO NECESSÁRIO**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Ativar Recuperação Emergencial"):
            with st.spinner("Ativando estratégia de recuperação..."):
                # Reiniciar com estratégia conservadora
                st.session_state.sistema_confianca.confianca = 0.5
                st.session_state.gestor_risco.sequencia_atual = 0
                st.session_state.ultimos_resultados = st.session_state.ultimos_resultados[-3:]  # Manter apenas últimos 3
                
                st.success("""
                ✅ **Recuperação Ativada!**
                - Confiança resetada para 50%
                - Sequência zerada
                - Estratégia conservadora ativada
                """)
    
    with col2:
        if st.button("🎯 Gerar Previsão Recuperação"):
            previsao_rec = st.session_state.gestor.ia_assertiva.gerar_previsao_recuperacao(
                list(st.session_state.gestor.historico),
                sequencia_atual
            )
            if previsao_rec:
                st.session_state.previsao_atual = validar_previsao(previsao_rec)
                st.success(f"🎯 Previsão Recuperação: {sorted(previsao_rec)}")
                st.rerun()

# ANÁLISE DO SISTEMA
st.markdown("---")
st.subheader("🔍 Análise Baseada em Histórico")
analise = st.session_state.gestor.get_analise_detalhada()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🚀 Modo", "ASSERTIVO" if analise["modo_assertivo"] else "EVOLUINDO")
with col2:
    st.metric("💪 Confiança", analise["confianca"])
with col3:
    st.metric("📈 Padrão", "✅" if analise["padrao_detectado"] else "⏳")

# SEÇÃO: ANÁLISE DOS PADRÕES ATUAIS
st.markdown("---")
st.subheader("🔍 Análise dos Padrões Atuais")

historico_size = len([h for h in st.session_state.gestor.historico if h.get('number') is not None])
if historico_size >= 10:
    padroes = analisar_padroes_dinamicos(st.session_state.gestor.historico)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🔥 Números Quentes:**")
        if padroes and padroes['quentes']:
            # CORREÇÃO: Evitar acesso a índices negativos
            historico_lista = list(st.session_state.gestor.historico)
            if len(historico_lista) >= 15:
                ultimos_15 = historico_lista[-15:]
            else:
                ultimos_15 = historico_lista
                
            numeros_ultimos_15 = [h['number'] for h in ultimos_15 if h.get('number') is not None]
            if numeros_ultimos_15:
                contador_15 = Counter(numeros_ultimos_15)
                quentes_formatados = []
                for num in padroes['quentes'][:5]:
                    count = contador_15.get(num, 0)
                    quentes_formatados.append(f"{num} ({count}×)")
                st.write(", ".join(quentes_formatados))
            else:
                st.write(", ".join(map(str, padroes['quentes'][:5])))
        else:
            st.write("Padrão não identificado")
        
        st.write("**🔄 Repetições Recentes:**")
        if padroes and padroes['repetidos']:
            st.write(", ".join(map(str, padroes['repetidos'][:3])))
        else:
            st.write("Nenhuma repetição forte")
    
    with col2:
        st.write("**❄️ Números Frios:**")
        if padroes and padroes['frios']:
            st.write(f"{len(padroes['frios'])} números ausentes")
            if len(padroes['frios']) <= 10:
                st.write(", ".join(map(str, sorted(padroes['frios'][:8]))))
        else:
            st.write("Todos números apareceram")
        
        st.write("**🎯 Vizinhança Quente:**")
        if padroes and padroes['vizinhos_quentes']:
            st.write(", ".join(map(str, padroes['vizinhos_quentes'][:4])))
        else:
            st.write("Sem vizinhança estratégica")
else:
    st.info("📊 Coletando dados para análise de padrões...")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO BASEADA EM HISTÓRICO")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    xgboost_status = st.session_state.gestor.get_status_xgboost()
    origem = "XGBoost ML" if xgboost_status["ativo"] else "Sequencial"
    st.success(f"**🔥 PREVISÃO VIA {origem.upper()} - {len(previsao_valida)} NÚMEROS ÚNICOS**")
    
    # Display IMPACTANTE
    st.markdown(f"### **{'  •  '.join(map(str, sorted(previsao_valida)))}**")
    
    st.write(f"**Estratégia:** {analise['estrategia_ativa']}")
    
    if analise['numeros_quentes']:
        st.write(f"**Números Quentes:** {', '.join(map(str, analise['numeros_quentes']))}")
    
else:
    st.warning("⚠️ Coletando dados históricos...")

# PERFORMANCE COM ANÁLISE DETALHADA
st.markdown("---")
st.subheader("📊 Performance do Sistema")

total = st.session_state.acertos + st.session_state.erros
taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("✅ Acertos", st.session_state.acertos)
with col2:
    st.metric("❌ Erros", st.session_state.erros)
with col3:
    st.metric("📈 Assertividade", f"{taxa_acerto:.1f}%")
with col4:
    st.metric("🛡️ Máx Sequência", st.session_state.gestor_risco.max_sequencia_negativa)

# ANÁLISE DE PERFORMANCE
st.write("### 📈 Análise de Tendência")

if total >= 10:  # Apenas mostrar análise se tiver dados suficientes
    if taxa_acerto >= 40:
        st.success("🎉 **Performance Excelente!** Continue com a estratégia atual.")
    elif taxa_acerto >= 30:
        st.info("📊 **Performance Boa.** Pequenos ajustes podem melhorar ainda mais.")
    elif taxa_acerto >= 20:
        st.warning("🔧 **Performance Moderada.** Considere usar as estratégias de recuperação.")
    else:
        st.error("🚨 **Performance Baixa.** Ative o modo recuperação imediatamente.")
    
    # Recomendações baseadas na sequência atual
    sequencia_atual = st.session_state.gestor_risco.sequencia_atual
    if sequencia_atual >= 5:
        st.error(f"🔴 **ALERTA:** Sequência negativa de {sequencia_atual}. Use recuperação emergencial.")
    elif sequencia_atual >= 3:
        st.warning(f"🟡 **ATENÇÃO:** Sequência negativa de {sequencia_atual}. Modere entradas.")

# CONTROLES
st.markdown("---")
st.subheader("⚙️ Controles")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔄 Nova Previsão"):
        nova_previsao = st.session_state.gestor.gerar_previsao_assertiva(st.session_state.ultimo_numero)
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        st.rerun()

with col2:
    if st.button("🗑️ Reiniciar Tudo"):
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        if os.path.exists(XGB_MODEL_PATH):
            os.remove(XGB_MODEL_PATH)
        if os.path.exists(FEATURE_ENGINEER_PATH):
            os.remove(FEATURE_ENGINEER_PATH)
        st.session_state.gestor.historico.clear()
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.session_state.ultima_entrada_estrategica = []
        st.session_state.sistema_confianca = SistemaConfianca()
        st.session_state.gestor_risco = SistemaGestaoRisco()
        st.session_state.ultimos_resultados = []
        st.rerun()

with col3:
    if st.button("📊 Análise Detalhada"):
        # Mostrar análise avançada baseada em histórico
        numeros = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
        if numeros:
            # CORREÇÃO: Evitar índices negativos
            if len(numeros) >= 10:
                st.info(f"🔍 Últimos 10 números: {numeros[-10:]}")
            else:
                st.info(f"🔍 Todos os números: {numeros}")
                
            st.info(f"📊 Números mais frequentes: {Counter(numeros).most_common(5)}")
            
            # Mostrar análise de padrões
            analise = analisar_padroes_dinamicos(st.session_state.gestor.historico)
            if analise:
                st.info(f"🎯 Números quentes: {analise.get('numeros_quentes', [])}")
                st.info(f"🔄 Padrões repetição: {analise.get('padroes_repeticao', [])}")
            
            # Mostrar status XGBoost detalhado
            xgboost_status = st.session_state.gestor.get_status_xgboost()
            st.info(f"🤖 XGBoost - Treinado: {xgboost_status['treinado']}, Ativo: {xgboost_status['ativo']}")

st.markdown("---")
st.markdown("### 🚀 **SISTEMA 100% BASEADO EM HISTÓRICO + XGBOOST ML ATIVADO**")
st.markdown("*Estratégia de 8 números baseada exclusivamente no histórico de sorteios com Machine Learning*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Sistema Baseado em Histórico v17.0** - *XGBoost Machine Learning + Recuperação Avançada + Performance Otimizada*")
