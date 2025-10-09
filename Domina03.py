# RoletaHybridIA.py - SISTEMA ESPECIALISTA COM XGBOOST 50+ FEATURES
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
# NOVAS DEPENDÊNCIAS XGBOOST
# =============================
try:
    import xgboost as xgb
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    import joblib
    XGBOOST_DISPONIVEL = True
except ImportError:
    XGBOOST_DISPONIVEL = False
    logging.warning("XGBoost não disponível - usando métodos tradicionais")

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
NUMERO_PREVISOES = 12  # SEMPRE 8 NÚMEROS BASEADOS NO HISTÓRICO

# Fases do sistema
FASE_INICIAL = 30
FASE_INTERMEDIARIA = 80  
FASE_AVANCADA = 120
FASE_ESPECIALISTA = 150

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# ENGINEERING DE FEATURES AVANÇADO - 50+ FEATURES (VERSÃO CORRIGIDA)
# =============================
class FeatureEngineer:
    def __init__(self):
        self.label_encoders = {}
        self.feature_names = []
        
    def criar_features_avancadas(self, historico, window_sizes=[5, 10, 15]):
        """Cria 50+ features avançadas para treinamento do XGBoost - VERSÃO CORRIGIDA"""
        if len(historico) < max(window_sizes) + 5:
            return [], []
            
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        features = []
        targets = []
        
        for i in range(max(window_sizes), len(numeros) - 1):
            feature_row = []
            proximo_numero = numeros[i]
            
            # === FEATURES TEMPORAIS MULTI-JANELA ===
            for window_size in window_sizes:
                janela = numeros[i-window_size:i]
                
                # 1. Estatísticas Básicas
                feature_row.append(np.mean(janela))
                feature_row.append(np.std(janela))
                feature_row.append(np.median(janela))
                feature_row.append(np.var(janela))
                feature_row.append(len(set(janela)) / len(janela))  # Taxa de unicidade
                
                # 2. Estatísticas de Ordem
                feature_row.append(janela[-1])  # Último
                feature_row.append(janela[-2] if len(janela) > 1 else 0)
                feature_row.append(janela[-3] if len(janela) > 2 else 0)
                feature_row.append(janela[-1] - janela[-2] if len(janela) > 1 else 0)
                feature_row.append(janela[-2] - janela[-3] if len(janela) > 2 else 0)
            
            # === FEATURES DE POSIÇÃO E CARACTERÍSTICAS ===
            ultimo_num = numeros[i-1]
            
            # 3. Características do Último Número
            feature_row.append(ultimo_num % 2)  # Par/Ímpar
            feature_row.append(1 if ultimo_num == 0 else 0)  # Zero
            feature_row.append(ultimo_num)  # Valor absoluto
            
            # 4. Posicionamento na Roleta
            feature_row.append(1 if ultimo_num in PRIMEIRA_DUZIA else 0)
            feature_row.append(1 if ultimo_num in SEGUNDA_DUZIA else 0)
            feature_row.append(1 if ultimo_num in TERCEIRA_DUZIA else 0)
            feature_row.append(1 if ultimo_num in COLUNA_1 else 0)
            feature_row.append(1 if ultimo_num in COLUNA_2 else 0)
            feature_row.append(1 if ultimo_num in COLUNA_3 else 0)
            
            # 5. Características de Cor (European Roulette)
            vermelhos = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
            feature_row.append(1 if ultimo_num in vermelhos else 0)
            feature_row.append(1 if ultimo_num in [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35] else 0)
            
            # === FEATURES DE PADRÕES COMPLEXOS ===
            janela_15 = numeros[i-15:i] if i >= 15 else numeros[:i]
            
            # 6. Padrões de Repetição - CORREÇÃO APLICADA
            repeticoes = 0
            for j in range(1, min(5, len(janela_15))):
                if janela_15[-j] == ultimo_num:
                    repeticoes += 1
            feature_row.append(repeticoes)
            
            # 7. Frequências Relativas
            contador_15 = Counter(janela_15)
            feature_row.append(contador_15.get(ultimo_num, 0))
            feature_row.append(contador_15.get(numeros[i-2], 0) if i >= 2 else 0)
            feature_row.append(contador_15.get(numeros[i-3], 0) if i >= 3 else 0)
            
            # 8. Estatísticas de Pares/Ímpares
            count_pares = len([n for n in janela_15 if n % 2 == 0 and n != 0])
            count_impares = len([n for n in janela_15 if n % 2 == 1])
            feature_row.append(count_pares)
            feature_row.append(count_impares)
            feature_row.append(count_pares / len(janela_15) if janela_15 else 0)
            feature_row.append(count_impares / len(janela_15) if janela_15 else 0)
            
            # 9. Estatísticas de Baixa/Alta (1-18 vs 19-36)
            count_baixa = len([n for n in janela_15 if 1 <= n <= 18])
            count_alta = len([n for n in janela_15 if 19 <= n <= 36])
            feature_row.append(count_baixa)
            feature_row.append(count_alta)
            feature_row.append(count_baixa / len(janela_15) if janela_15 else 0)
            feature_row.append(count_alta / len(janela_15) if janela_15 else 0)
            
            # === FEATURES DE VIZINHANÇA E PROXIMIDADE ===
            # 10. Vizinhança Física
            vizinhos = obter_vizinhos_fisicos(ultimo_num)
            feature_row.append(len(set(vizinhos) & set(janela_15[-10:])))
            
            # 11. Distância Numérica
            if len(janela_15) > 1:
                distancias = [abs(janela_15[j] - janela_15[j-1]) for j in range(1, len(janela_15))]
                feature_row.append(np.mean(distancias) if distancias else 0)
                feature_row.append(np.std(distancias) if distancias else 0)
            else:
                feature_row.extend([0, 0])
            
            # 12. Padrões de Série - CORREÇÃO APLICADA
            series_par_impar = 0
            for j in range(1, min(6, len(janela_15))):
                if j < len(janela_15) and janela_15[-j] % 2 == janela_15[-(j+1)] % 2:
                    series_par_impar += 1
                else:
                    break
            feature_row.append(series_par_impar)
            
            # === FEATURES DE TENDÊNCIA ===
            # 13. Tendência de Direção
            if len(janela_15) > 5:
                ultimos_5 = janela_15[-5:]
                tendencia = 0
                for j in range(1, len(ultimos_5)):
                    if ultimos_5[j] > ultimos_5[j-1]:
                        tendencia += 1
                    else:
                        tendencia -= 1
                feature_row.append(tendencia)
            else:
                feature_row.append(0)
            
            # 14. Volatilidade
            if len(janela_15) > 2:
                volatilidade = np.std(janela_15[-10:]) if len(janela_15) >= 10 else np.std(janela_15)
                feature_row.append(volatilidade)
            else:
                feature_row.append(0)
            
            # === FEATURES DE ATRASO ===
            # 15. Atraso de Números Populares
            numeros_populares = [num for num, count in Counter(numeros[:i]).most_common(5)]
            for num_pop in numeros_populares[:3]:
                if num_pop in numeros[:i]:
                    ultima_pos = len(numeros[:i]) - 1 - numeros[:i][::-1].index(num_pop)
                    atraso = i - ultima_pos
                    feature_row.append(min(atraso, 20))  # Limitar a 20
                else:
                    feature_row.append(99)  # Nunca saiu
            
            # === FEATURES DE SAZONALIDADE ===
            # 16. Padrões Cíclicos (simulados)
            feature_row.append(i % 10)  # Ciclo a cada 10 rodadas
            feature_row.append(i % 20)  # Ciclo a cada 20 rodadas
            
            # === FEATURES DE INTERAÇÃO ===
            # 17. Interação entre características
            feature_row.append(1 if (ultimo_num % 2 == 0 and ultimo_num in PRIMEIRA_DUZIA) else 0)
            feature_row.append(1 if (ultimo_num % 2 == 1 and ultimo_num in TERCEIRA_DUZIA) else 0)
            feature_row.append(1 if (ultimo_num in vermelhos and ultimo_num in COLUNA_2) else 0)
            
            features.append(feature_row)
            targets.append(proximo_numero)
        
        # Nomear as features para debug
        self.feature_names = self._gerar_nomes_features(len(feature_row))
        
        logging.info(f"🎯 Geradas {len(feature_row)} features para {len(features)} amostras")
        return np.array(features), np.array(targets)
    
    def _gerar_nomes_features(self, total_features):
        """Gera nomes descritivos para todas as features"""
        nomes = []
        
        # Features temporais
        janelas = [5, 10, 15]
        for janela in janelas:
            nomes.extend([
                f'media_{janela}', f'std_{janela}', f'mediana_{janela}', 
                f'var_{janela}', f'taxa_unicos_{janela}',
                f'ultimo_{janela}', f'penultimo_{janela}', f'ante_penultimo_{janela}',
                f'diff_ultimos_{janela}', f'diff_anteriores_{janela}'
            ])
        
        # Características básicas
        nomes.extend([
            'eh_par', 'eh_zero', 'valor_absoluto',
            'na_duzia1', 'na_duzia2', 'na_duzia3',
            'na_coluna1', 'na_coluna2', 'na_coluna3',
            'eh_vermelho', 'eh_preto'
        ])
        
        # Padrões complexos
        nomes.extend([
            'repeticoes_sequencia', 'freq_ultimo_15', 'freq_penultimo_15', 'freq_ante_penultimo_15',
            'count_pares_15', 'count_impares_15', 'taxa_pares_15', 'taxa_impares_15',
            'count_baixa_15', 'count_alta_15', 'taxa_baixa_15', 'taxa_alta_15',
            'vizinhos_recentes', 'media_distancias', 'std_distancias',
            'serie_par_impar', 'tendencia_direcao', 'volatilidade'
        ])
        
        # Atrasos
        nomes.extend(['atraso_popular1', 'atraso_popular2', 'atraso_popular3'])
        
        # Sazonalidade
        nomes.extend(['ciclo_10', 'ciclo_20'])
        
        # Interações
        nomes.extend(['interacao_par_duzia1', 'interacao_impar_duzia3', 'interacao_vermelho_coluna2'])
        
        # Garantir que temos nomes para todas as features
        while len(nomes) < total_features:
            nomes.append(f'feature_extra_{len(nomes)}')
        
        return nomes[:total_features]
    
    def salvar_engineer(self):
        """Salva o feature engineer"""
        if XGBOOST_DISPONIVEL:
            joblib.dump(self, FEATURE_ENGINEER_PATH)
    
    @staticmethod
    def carregar_engineer():
        """Carrega o feature engineer"""
        try:
            if XGBOOST_DISPONIVEL:
                return joblib.load(FEATURE_ENGINEER_PATH)
        except:
            return FeatureEngineer()

# =============================
# XGBOOST OTIMIZADO PARA +50 FEATURES
# =============================
class XGBoostPredictor:
    def __init__(self):
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.ultima_previsao = []
        self.performance = {"acertos": 0, "erros": 0}
        self.treinado = False
        
    def treinar_modelo(self, historico, force_retrain=False):
        """Treina o modelo XGBoost com features expandidas"""
        if not XGBOOST_DISPONIVEL:
            logging.warning("XGBoost não disponível - pulando treinamento")
            return False
            
        try:
            if len(historico) < 150 and not force_retrain:  # Aumentado mínimo
                logging.info("📊 Histórico insuficiente para treinar XGBoost com muitas features")
                return False
                
            logging.info("🤖 Iniciando treinamento do XGBoost com features expandidas...")
            
            # Criar features e targets
            features, targets = self.feature_engineer.criar_features_avancadas(historico)
            
            if len(features) < 80:  # Aumentado mínimo
                logging.warning("📊 Dados insuficientes para treinamento com muitas features")
                return False
            
            # Dividir dados
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=0.15, random_state=42  # Menos dados de teste
            )
            
            # Configurar modelo OTIMIZADO para muitas features
            self.model = xgb.XGBClassifier(
                n_estimators=300,  # Aumentado
                max_depth=10,      # Aumentado
                learning_rate=0.08, # Reduzido
                subsample=0.8,     # Adicionado
                colsample_bytree=0.8, # Adicionado
                random_state=42,
                objective='multi:softprob',
                num_class=37,
                n_jobs=-1  # Usar todos os cores
            )
            
            # Treinar com early stopping
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                early_stopping_rounds=20,
                verbose=False
            )
            
            # Avaliar
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            # Feature importance
            importancia = self.model.feature_importances_
            top_features = np.argsort(importancia)[-5:][::-1]
            
            logging.info(f"🎯 XGBoost treinado! Acurácia: {accuracy:.2%}")
            logging.info(f"📊 Top 5 features: {[self.feature_engineer.feature_names[i] for i in top_features]}")
            
            # Salvar modelo
            self.model.save_model(XGB_MODEL_PATH)
            self.feature_engineer.salvar_engineer()
            self.treinado = True
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no treinamento XGBoost: {e}")
            return False

    def prever_proximos_numeros(self, historico, top_n=8):
        """Faz previsão usando XGBoost com features expandidas"""
        if not XGBOOST_DISPONIVEL or not self.treinado:
            return self._previsao_fallback(historico)
            
        try:
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            if len(numeros) < 20:  # Aumentado mínimo
                return self._previsao_fallback(historico)
            
            # Criar features para previsão
            features, _ = self.feature_engineer.criar_features_avancadas(historico)
            if len(features) == 0:
                return self._previsao_fallback(historico)
            
            # Usar última linha para previsão
            ultimas_features = features[-1].reshape(1, -1)
            
            # Obter probabilidades com calibração
            probabilidades = self.model.predict_proba(ultimas_features)[0]
            
            # Aplicar pesos baseados na importância das features
            importancia = self.model.feature_importances_
            prob_ponderadas = probabilidades * (1 + importancia.mean())  # Pequeno boost
            
            # Pegar top N números mais prováveis
            indices_mais_provaveis = np.argsort(prob_ponderadas)[::-1][:top_n*3]
            
            previsao = []
            for idx in indices_mais_provaveis:
                if len(previsao) >= top_n:
                    break
                if 0 <= idx <= 36:
                    previsao.append(int(idx))
            
            # Garantir diversidade na previsão
            previsao_final = self._garantir_diversidade(previsao, historico, top_n)
            
            self.ultima_previsao = previsao_final
            logging.info(f"🎯 XGBoost com {len(ultimas_features[0])} features previu: {self.ultima_previsao}")
            
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
            return numeros[-NUMERO_PREVISOES:]
        return [2, 5, 8, 11, 14, 17, 20, 23]
    
    def _completar_previsao(self, previsao, historico, top_n):
        """Completa previsão com números do histórico"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        completar = []
        
        # Adicionar números recentes
        for num in reversed(numeros[-10:]):
            if len(completar) + len(previsao) < top_n and num not in previsao:
                completar.append(num)
        
        # Adicionar números frequentes
        if len(completar) + len(previsao) < top_n:
            frequentes = Counter(numeros).most_common(10)
            for num, _ in frequentes:
                if len(completar) + len(previsao) < top_n and num not in previsao:
                    completar.append(num)
        
        return completar
    
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

# =============================
# SISTEMAS DE SUPORTE
# =============================

class SistemaConfianca:
    def __init__(self):
        self.confianca = 0.7
        self.tendencia = "NEUTRA"
        self.historico_confianca = deque(maxlen=20)
    
    def atualizar_confianca(self, acerto):
        if acerto:
            self.confianca = min(0.95, self.confianca + 0.15)
        else:
            self.confianca = max(0.3, self.confianca - 0.08)
        
        self.historico_confianca.append(self.confianca)
        
        if self.confianca > 0.6:
            self.tendencia = "ALTA"
        elif self.confianca < 0.4:
            self.tendencia = "BAIXA"
        else:
            self.tendencia = "NEUTRA"
    
    def get_confianca_categoria(self):
        if self.confianca > 0.75:
            return "MUITO ALTA"
        elif self.confianca > 0.55:
            return "ALTA"
        elif self.confianca > 0.35:
            return "MODERADA"
        else:
            return "BAIXA"

class SistemaGestaoRisco:
    def __init__(self):
        self.entradas_recentes = deque(maxlen=10)
        self.resultados_recentes = deque(maxlen=10)
        self.sequencia_atual = 0
        self.max_sequencia_negativa = 0
    
    def deve_entrar(self, analise_risco, confianca, historico_size):
        """CRITÉRIOS SUPER AGRESSIVOS"""
        
        if analise_risco in ["RISCO_BAIXO", "RISCO_MODERADO"]:
            return True
            
        if analise_risco == "RISCO_ALTO" and confianca > 0.4 and historico_size > 30:
            return True
            
        if self.sequencia_atual >= 6:
            return False
            
        return True
    
    def calcular_tamanho_aposta(self, confianca, saldo=1000):
        base = saldo * 0.02
        if confianca > 0.7:
            return base * 2.0
        elif confianca > 0.5:
            return base * 1.5
        elif confianca > 0.3:
            return base
        else:
            return base * 0.8
    
    def atualizar_sequencia(self, resultado):
        if resultado == "GREEN":
            self.sequencia_atual = 0
        else:
            self.sequencia_atual += 1
            self.max_sequencia_negativa = max(self.max_sequencia_negativa, self.sequencia_atual)

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
        """Gera previsão MAIS INTELIGENTE baseada em múltiplos fatores"""
        
        if not historico or ultimo_numero is None:
            return []
        
        # ANALISAR SEQUÊNCIAS HISTÓRICAS
        previsao_sequencial = self.analisar_sequencias_historicas(historico, ultimo_numero)
        
        # SE NÃO ENCONTROU PADRÕES FORTES, USAR ESTRATÉGIA ALTERNATIVA
        if len(previsao_sequencial) < 6:
            previsao_sequencial = self.estrategia_fallback_agressiva(historico, ultimo_numero)
        
        # FILTRAR E LIMITAR A 8 NÚMEROS
        previsao_filtrada = previsao_sequencial[:NUMERO_PREVISOES]
        self.ultima_previsao = previsao_filtrada
        
        logging.info(f"🎯 Previsão Sequencial GERADA: {previsao_filtrada}")
        return previsao_filtrada
    
    def estrategia_fallback_agressiva(self, historico, ultimo_numero):
        """Estratégia alternativa AGRESSIVA quando não há padrões claros"""
        
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
        
        # ESTRATÉGIA 3: NÚMEROS DA MESMA CARACTERÍSTICA (par/ímpar, cor, etc)
        if ultimo_numero != 0:
            if ultimo_numero % 2 == 0:
                previsao.update([n for n in range(1, 37) if n % 2 == 0 and n != ultimo_numero][:3])
            else:
                previsao.update([n for n in range(1, 37) if n % 2 == 1 and n != ultimo_numero][:3])
        
        # ESTRATÉGIA 4: COMPLETAR COM FREQUENTES
        if len(previsao) < 6:
            frequentes = Counter(numeros).most_common(10)
            for num, count in frequentes:
                if len(previsao) < 8 and num not in previsao:
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
# ALERTA SIMPLIFICADO PARA TELEGRAM
# =============================
def enviar_alerta_inteligente(entrada_estrategica, confianca, performance):
    """Envia alerta SUPER SIMPLES apenas com números"""
    
    # Ordenar os números
    numeros_ordenados = sorted(entrada_estrategica)
    
    # Dividir em duas linhas (4 números por linha)
    primeira_linha = '   '.join(map(str, numeros_ordenados[:4]))
    segunda_linha = '   '.join(map(str, numeros_ordenados[4:]))
    
    # Mensagem SUPER SIMPLES - apenas números
    mensagem = f"{primeira_linha}\n{segunda_linha}"
    
    enviar_telegram(mensagem, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)

# =============================
# ESTRATÉGIA 100% BASEADA EM HISTÓRICO - VERSÃO CORRIGIDA
# =============================

def gerar_entrada_ultra_assertiva(previsao_completa, historico):
    """CORREÇÃO: Garantir que a entrada seja EXATAMENTE a previsão"""
    
    # SIMPLESMENTE RETORNAR A PREVISÃO - SEM FILTROS EXTRAS
    previsao_valida = validar_previsao(previsao_completa)
    
    if len(previsao_valida) >= 6:
        return previsao_valida[:NUMERO_PREVISOES]
    
    # FALLBACK: usar últimos números do histórico
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    if numeros:
        return numeros[-NUMERO_PREVISOES:] if len(numeros) >= NUMERO_PREVISOES else numeros
    
    return [2, 5, 8, 11, 14, 17, 20, 23]

def enviar_alerta_assertivo(entrada_estrategica, ultimo_numero, historico, performance):
    """Envia alerta ULTRA SIMPLES para Telegram"""
    
    try:
        if not entrada_estrategica:
            return
        
        # Usar sistema de confiança para alerta inteligente
        confianca = st.session_state.sistema_confianca.confianca
        enviar_alerta_inteligente(entrada_estrategica, confianca, performance)
        
        # Salvar entrada atual
        st.session_state.ultima_entrada_estrategica = entrada_estrategica
        
        logging.info(f"📤 Alerta SIMPLES enviado: {len(entrada_estrategica)} números")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta: {e}")

def verificar_resultado_entrada_anterior(numero_sorteado):
    """Verificação RÁPIDA de resultado BASEADO NO HISTÓRICO"""
    
    entrada_anterior = st.session_state.get('ultima_entrada_estrategica', [])
    
    if not entrada_anterior or numero_sorteado is None:
        return None
    
    # Atualizar sistema de confiança
    acertou = numero_sorteado in entrada_anterior
    st.session_state.sistema_confianca.atualizar_confianca(acertou)
    
    # Atualizar gestão de risco
    st.session_state.gestor_risco.atualizar_sequencia("GREEN" if acertou else "RED")
    
    if acertou:
        mensagem_green = f"✅ **GREEN!** Acertamos {numero_sorteado}!"
        enviar_telegram(mensagem_green, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        return "GREEN"
    else:
        mensagem_red = f"❌ **RED** {numero_sorteado} não estava"
        enviar_telegram(mensagem_red, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        return "RED"

# =============================
# SISTEMA DE RECUPERAÇÃO E RESET
# =============================
def verificar_estrategia_recuperacao(historico, ultimos_resultados):
    """Verifica se devemos ativar estratégia de recuperação"""
    
    if len(ultimos_resultados) < 3:
        return False
    
    # Ativar recuperação se tivermos 3 REDs consecutivos
    if ultimos_resultados[-3:] == ["RED", "RED", "RED"]:
        return True
    
    # Ativar recuperação se taxa de acerto estiver abaixo de 25%
    total = len(ultimos_resultados)
    acertos = ultimos_resultados.count("GREEN")
    taxa = acertos / total if total > 0 else 0
    
    return taxa < 0.25

def verificar_reset_sistema(acertos, erros, performance_sequencial):
    """Reinicia o sistema se performance for catastrófica"""
    total_geral = acertos + erros
    total_sequencial = performance_sequencial["acertos"] + performance_sequencial["erros"]
    
    if total_geral > 20:
        taxa_geral = acertos / total_geral
        taxa_sequencial = performance_sequencial["acertos"] / total_sequencial if total_sequencial > 0 else 0
        
        # Se ambas as taxas forem abaixo de 10%, resetar
        if taxa_geral < 0.1 and taxa_sequencial < 0.1:
            logging.warning("🔄 PERFORMANCE CATASTRÓFICA - Reiniciando sistema...")
            return True
    
    return False

# =============================
# ANÁLISES 100% BASEADAS EM HISTÓRICO - VERSÃO MAIS AGRESSIVA
# =============================

def analisar_padroes_assertivos(historico):
    """Análise AGGRESSIVA focada em padrões de alta probabilidade BASEADA NO HISTÓRICO"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 5:
        return {"numeros_quentes": [], "padrao_atual": "inicial"}
    
    # ANÁLISE DE PADRÕES DE REPETIÇÃO IMEDIATA (baseado no histórico)
    padroes_repeticao = []
    for i in range(1, len(numeros)):
        if numeros[i] == numeros[i-1]:
            padroes_repeticao.append(numeros[i])
    
    # ANÁLISE DE SEQUÊNCIAS DE VIZINHANÇA (baseado no histórico)
    sequencias_vizinhanca = []
    for i in range(1, min(6, len(numeros))):
        vizinhos_anteriores = obter_vizinhos_fisicos(numeros[-i])
        if numeros[-1] in vizinhos_anteriores:
            sequencias_vizinhanca.extend(vizinhos_anteriores)
    
    # NÚMEROS QUENTES (últimas 12 rodadas) - baseado no histórico
    ultimos_12 = numeros[-12:] if len(numeros) >= 12 else numeros
    contagem_recente = Counter(ultimos_12)
    numeros_quentes = [num for num, count in contagem_recente.most_common(6) if count >= 2]
    
    # NÚMEROS COM ATRASO (não saem há mais de 6 rodadas) - baseado no histórico
    numeros_atrasados = []
    for num in range(0, 37):
        if num in numeros:
            ultima_ocorrencia = len(numeros) - 1 - numeros[::-1].index(num)
            atraso = len(numeros) - ultima_ocorrencia
            if atraso > 6:
                numeros_atrasados.append(num)
        else:
            # Se nunca saiu, é um atrasado extremo
            numeros_atrasados.append(num)
    
    # PADRÃO DE ALTERNÂNCIA DE CORES (baseado no histórico)
    cores_alternadas = []
    if len(numeros) >= 2:
        ultima_cor = "preto" if numeros[-1] in [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35] else "vermelho" if numeros[-1] in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "zero"
        penultima_cor = "preto" if numeros[-2] in [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35] else "vermelho" if numeros[-2] in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "zero"
        
        if ultima_cor == penultima_cor:
            # Tendência de mudança de cor
            if ultima_cor == "vermelho":
                cores_alternadas = [n for n in range(1,37) if n in [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]]
            else:
                cores_alternadas = [n for n in range(1,37) if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]]
    
    return {
        "numeros_quentes": numeros_quentes[:4],
        "padroes_repeticao": list(set(padroes_repeticao))[:3],
        "sequencias_vizinhanca": list(set(sequencias_vizinhanca))[:4],
        "numeros_atrasados": numeros_atrasados[:4],
        "cores_alternadas": cores_alternadas[:3],
        "ultima_cor": ultima_cor if len(numeros) >= 1 else "indefinido",
        "total_analisado": len(numeros)
    }

def identificar_nucleo_assertivo(historico):
    """Versão MAIS AGRESSIVA do núcleo assertivo"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 3:
        return numeros
    
    analise = analisar_padroes_assertivos(historico)
    
    nucleo = set()
    
    # PRIORIDADE MÁXIMA: Números que saíram nas últimas 3 rodadas
    nucleo.update(numeros[-3:])
    
    # ADICIONAR MAIS NÚMEROS QUENTES
    nucleo.update(analise["numeros_quentes"])
    
    # ADICIONAR TODOS OS PADRÕES DE REPETIÇÃO
    nucleo.update(analise["padroes_repeticao"])
    
    # ADICIONAR MAIS SEQUÊNCIAS DE VIZINHANÇA
    nucleo.update(analise["sequencias_vizinhanca"])
    
    # ADICIONAR MAIS NÚMEROS ATRASADOS
    if analise["numeros_atrasados"]:
        nucleo.update(analise["numeros_atrasados"][:3])
    
    # SE AINDA PRECISAR DE MAIS NÚMEROS, USAR MAIS HISTÓRICO
    if len(nucleo) < NUMERO_PREVISOES:
        nucleo.update(numeros[-10:])
    
    # GARANTIR QUE SEMPRE TENHAMOS PELO MENOS 5 NÚMEROS
    if len(nucleo) < 5:
        frequentes_geral = Counter(numeros).most_common(10)
        for num, freq in frequentes_geral:
            if len(nucleo) < 8 and num not in nucleo:
                nucleo.add(num)
    
    return list(nucleo)[:NUMERO_PREVISOES]

def filtrar_por_confirmacao_rapida(historico, numeros_candidatos):
    """Filtro RÁPIDO baseado em confirmações imediatas DO HISTÓRICO"""
    
    if len(numeros_candidatos) <= NUMERO_PREVISOES:
        return numeros_candidatos
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    scores = {}
    
    for numero in numeros_candidatos:
        score = 0
        
        # CONFIRMAÇÃO 1: É UM DOS ÚLTIMOS 3 NÚMEROS? (histórico)
        if numero in numeros[-3:]:
            score += 3
        
        # CONFIRMAÇÃO 2: É VIZINHO DOS ÚLTIMOS 2 NÚMEROS? (histórico)
        for recente in numeros[-2:]:
            if numero in obter_vizinhos_fisicos(recente):
                score += 2
                break
        
        # CONFIRMAÇÃO 3: TEVE REPETIÇÃO RECENTE (últimas 10 rodadas - histórico)
        if numeros[-10:].count(numero) >= 2:
            score += 2
        
        # CONFIRMAÇÃO 4: ESTÁ NA MESMA COLUNA DOS ÚLTIMOS NÚMEROS? (histórico)
        ultimas_colunas = []
        for num in numeros[-3:]:
            if num in COLUNA_1: 
                ultimas_colunas.append(1)
            elif num in COLUNA_2: 
                ultimas_colunas.append(2)
            elif num in COLUNA_3: 
                ultimas_colunas.append(3)
        
        if ultimas_colunas:
            coluna_mais_comum = Counter(ultimas_colunas).most_common(1)[0][0]
            if (coluna_mais_comum == 1 and numero in COLUNA_1) or \
               (coluna_mais_comum == 2 and numero in COLUNA_2) or \
               (coluna_mais_comum == 3 and numero in COLUNA_3):
                score += 1
        
        # CONFIRMAÇÃO 5: É UM NÚMERO QUENTE? (histórico)
        ultimos_12 = numeros[-12:] if len(numeros) >= 12 else numeros
        if ultimos_12.count(numero) >= 2:
            score += 1
        
        scores[numero] = score
    
    # SELECIONAR OS COM MAIOR SCORE (baseado no histórico)
    melhores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [num for num, score in melhores][:NUMERO_PREVISOES]

def analisar_risco_entrada(historico, entrada_proposta):
    """Analisa o risco de forma MAIS OTIMISTA"""
    if len(historico) < 5:
        return "RISCO_MODERADO"
    
    numeros = [h['number'] for h in historico]
    ultimos_8 = numeros[-8:]
    
    # Verificar quantos dos números propostos saíram recentemente
    acertos_previstos = len(set(ultimos_8) & set(entrada_proposta))
    
    if acertos_previstos >= 2:
        return "RISCO_BAIXO"
    elif acertos_previstos >= 1:
        return "RISCO_MODERADO"
    else:
        return "RISCO_ALTO"

# =============================
# SISTEMA ESPECIALISTA 100% BASEADO EM HISTÓRICO COM XGBOOST
# =============================
class IA_Assertiva:
    def __init__(self):
        self.historico_analises = deque(maxlen=50)
        self.previsao_sequencial = SistemaPrevisaoSequencial()
        self.xgboost_predictor = XGBoostPredictor()
        self.modo_xgboost_ativo = False
        
    def prever_com_alta_assertividade(self, historico, ultimo_numero=None):
        """Sistema PRINCIPAL agora com XGBoost"""
        
        # Tentar XGBoost primeiro se tiver histórico suficiente
        if len(historico) >= 150:  # Aumentado mínimo para features expandidas
            if not self.xgboost_predictor.treinado:
                self.xgboost_predictor.carregar_modelo()
                
            if self.xgboost_predictor.treinado:
                self.modo_xgboost_ativo = True
                previsao_xgb = self.xgboost_predictor.prever_proximos_numeros(historico, NUMERO_PREVISOES)
                if previsao_xgb and len(previsao_xgb) >= 6:
                    logging.info("🎯 USANDO XGBOOST para previsão")
                    return previsao_xgb
        
        # Fallback para previsão sequencial
        self.modo_xgboost_ativo = False
        if ultimo_numero is not None and len(historico) >= 15:
            previsao_seq = self.previsao_sequencial.gerar_previsao_sequencial(historico, ultimo_numero)
            if previsao_seq and len(previsao_seq) >= 6:
                logging.info(f"🔄 Usando PREVISÃO SEQUENCIAL para {ultimo_numero}")
                return previsao_seq
        
        # Fallback final
        logging.info("📊 Usando estratégia alternativa")
        return self.estrategia_alternativa_agressiva(historico)
    
    def estrategia_alternativa_agressiva(self, historico):
        """Estratégia alternativa SUPER AGRESSIVA"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 8:
            return [2, 5, 8, 11, 14, 17, 20, 23]
        
        previsao = set()
        
        # ESTRATÉGIA 1: ÚLTIMOS 5 NÚMEROS
        previsao.update(numeros[-5:])
        
        # ESTRATÉGIA 2: VIZINHOS DOS ÚLTIMOS 3
        for num in numeros[-3:]:
            previsao.update(obter_vizinhos_fisicos(num)[:3])
        
        # ESTRATÉGIA 3: NÚMEROS QUENTES (últimas 20 rodadas)
        ultimos_20 = numeros[-20:] if len(numeros) >= 20 else numeros
        contagem_recente = Counter(ultimos_20)
        numeros_quentes = [num for num, count in contagem_recente.most_common(10) if count >= 2]
        previsao.update(numeros_quentes)
        
        # ESTRATÉGIA 4: COMPLETAR COM MAIS FREQUENTES
        if len(previsao) < NUMERO_PREVISOES:
            frequentes = Counter(numeros).most_common(15)
            for num, count in frequentes:
                if len(previsao) < NUMERO_PREVISOES and num not in previsao:
                    previsao.add(num)
        
        return list(previsao)[:NUMERO_PREVISOES]
    
    def get_performance_sequencial(self):
        """Retorna performance do sistema sequencial"""
        return self.previsao_sequencial.get_performance_sequencial()

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
        return self.ia_assertiva.xgboost_predictor.treinar_modelo(self.historico, force_retrain)
    
    def get_status_xgboost(self):
        """Retorna status do XGBoost"""
        return {
            "treinado": self.ia_assertiva.xgboost_predictor.treinado,
            "ativo": self.ia_assertiva.modo_xgboost_ativo,
            "performance": self.ia_assertiva.xgboost_predictor.get_performance()
        }
        
    def gerar_previsao_assertiva(self, ultimo_numero=None):
        try:
            previsao = self.ia_assertiva.prever_com_alta_assertividade(self.historico, ultimo_numero)
            previsao_validada = validar_previsao(previsao)
            
            # GARANTIR SEMPRE 8 NÚMEROS BASEADOS NO HISTÓRICO
            if len(previsao_validada) < NUMERO_PREVISOES:
                logging.warning(f"⚠️ Previsão com {len(previsao_validada)} números. Completando com histórico...")
                previsao_validada = self.completar_com_historico(previsao_validada)
            
            logging.info(f"✅ Previsão ASSERTIVA gerada: {len(previsao_validada)} números")
            return previsao_validada
            
        except Exception as e:
            logging.error(f"Erro ao gerar previsão: {e}")
            # Em caso de erro, usar os últimos números do histórico
            numeros = [h['number'] for h in self.historico if h.get('number') is not None]
            return numeros[-NUMERO_PREVISOES:] if len(numeros) >= NUMERO_PREVISOES else numeros
    
    def completar_com_historico(self, previsao):
        """Completa sempre para 8 números USANDO APENAS HISTÓRICO"""
        if len(previsao) >= NUMERO_PREVISOES:
            return previsao[:NUMERO_PREVISOES]
        
        numeros_completos = set(previsao)
        numeros_historico = [h['number'] for h in self.historico if h.get('number') is not None]
        
        # COMPLETAR COM NÚMEROS DO HISTÓRICO EM ORDEM DE PRIORIDADE:
        
        # 1. Últimos números sorteados
        for num in reversed(numeros_historico):
            if len(numeros_completos) < NUMERO_PREVISOES and num not in numeros_completos:
                numeros_completos.add(num)
        
        # 2. Números mais frequentes no histórico
        if len(numeros_completos) < NUMERO_PREVISOES:
            frequentes = Counter(numeros_historico).most_common(20)
            for num, count in frequentes:
                if len(numeros_completos) < NUMERO_PREVISOES and num not in numeros_completos:
                    numeros_completos.add(num)
        
        # 3. Números que são vizinhos de números recentes
        if len(numeros_completos) < NUMERO_PREVISOES:
            for num_recente in numeros_historico[-3:]:
                vizinhos = obter_vizinhos_fisicos(num_recente)
                for vizinho in vizinhos:
                    if len(numeros_completos) < NUMERO_PREVISOES and vizinho not in numeros_completos:
                        numeros_completos.add(vizinho)
        
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
        
        analise = analisar_padroes_assertivos(self.historico)
        
        return {
            "modo_assertivo": modo_assertivo,
            "historico_total": historico_size,
            "confianca": "Alta" if historico_size > 100 else "Média" if historico_size > 50 else "Baixa",
            "estrategia_ativa": "Núcleo Histórico",
            "numeros_quentes": analise.get("numeros_quentes", []),
            "padrao_detectado": len(analise.get("padroes_repeticao", [])) > 0
        }
    
    def get_performance_sequencial(self):
        """Retorna performance do sistema sequencial"""
        return self.ia_assertiva.get_performance_sequencial()

# =============================
# STREAMLIT APP 100% BASEADO EM HISTÓRICO COM XGBOOST 50+ FEATURES
# =============================
st.set_page_config(
    page_title="Roleta - IA Baseada em Histórico", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 SISTEMA 100% BASEADO EM HISTÓRICO COM XGBOOST 50+ FEATURES")
st.markdown("### **Estratégia com 8 Números Baseada Exclusivamente no Histórico + Machine Learning Avançado**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorAssertivo(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
    "status_ia": "🟡 Inicializando",
    "estrategia_atual": "Aguardando dados",
    "ultima_entrada_estrategica": [],
    "resultado_entrada_anterior": None,
    "sistema_confianca": SistemaConfianca(),
    "gestor_risco": SistemaGestaoRisco(),
    "ultimos_resultados": []
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

        # VERIFICAR RESET DO SISTEMA (CORREÇÃO CRÍTICA)
        if verificar_reset_sistema(st.session_state.acertos, st.session_state.erros, 
                                  st.session_state.gestor.get_performance_sequencial()):
            st.session_state.acertos = 0
            st.session_state.erros = 0
            st.session_state.sistema_confianca = SistemaConfianca()
            st.session_state.gestor_risco = SistemaGestaoRisco()
            st.session_state.ultimos_resultados = []
            logging.info("✅ Sistema reiniciado devido à performance baixa")

        # ATUALIZAR STATUS
        st.session_state.status_ia, st.session_state.estrategia_atual = st.session_state.gestor.get_status_sistema()

        # VERIFICAR ENTRADA ANTERIOR
        st.session_state.resultado_entrada_anterior = verificar_resultado_entrada_anterior(numero_real)

        # ATUALIZAR HISTÓRICO DE RESULTADOS
        if st.session_state.resultado_entrada_anterior:
            st.session_state.ultimos_resultados.append(st.session_state.resultado_entrada_anterior)
            if len(st.session_state.ultimos_resultados) > 10:
                st.session_state.ultimos_resultados.pop(0)

        # CONFERIR PREVISÃO ANTERIOR
        previsao_valida = validar_previsao(st.session_state.previsao_atual)
        if previsao_valida:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.success(f"🎯 **ACERTOU!** Número {numero_real} estava na previsão!")
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava")

        # VERIFICAR ACERTO DA PREVISÃO SEQUENCIAL (CORREÇÃO SIMPLIFICADA)
        if st.session_state.ultimo_numero:
            st.session_state.gestor.ia_assertiva.previsao_sequencial.verificar_acerto_sequencial(numero_real)

        # VERIFICAR ACERTO DO XGBOOST
        if st.session_state.ultimo_numero and st.session_state.gestor.ia_assertiva.xgboost_predictor.ultima_previsao:
            st.session_state.gestor.ia_assertiva.xgboost_predictor.verificar_acerto(numero_real)

        # GERAR NOVA PREVISÃO BASEADA NO HISTÓRICO
        nova_previsao = st.session_state.gestor.gerar_previsao_assertiva(st.session_state.ultimo_numero)
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # GERAR ENTRADA ULTRA ASSERTIVA (CORREÇÃO CRÍTICA: USAR PREVISÃO DIRETAMENTE)
        entrada_assertiva = st.session_state.previsao_atual
        
        # Calcular performance
        total = st.session_state.acertos + st.session_state.erros
        taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
        performance = {
            'acertos': st.session_state.acertos,
            'erros': st.session_state.erros,
            'taxa_acerto': f"{taxa_acerto:.1f}%"
        }
        
        # LÓGICA SUPER AGRESSIVA DE DECISÃO (CORREÇÃO CRÍTICA)
        confianca_atual = st.session_state.sistema_confianca.confianca
        risco_entrada = analisar_risco_entrada(
            list(st.session_state.gestor.historico), 
            entrada_assertiva
        )
        
        # VERIFICAR SE DEVEMOS ATIVAR MODO RECUPERAÇÃO
        modo_recuperacao = verificar_estrategia_recuperacao(
            list(st.session_state.gestor.historico), 
            st.session_state.ultimos_resultados
        )
        
        # DECISÃO FINAL DE ENTRADA - CRITÉRIOS SUPER AGRESSIVOS (CORREÇÃO)
        deve_entrar = st.session_state.gestor_risco.deve_entrar(
            risco_entrada, 
            confianca_atual,
            len(st.session_state.gestor.historico)
        )
        
        # CORREÇÃO FINAL: SEMPRE ENTRAR EM CONDIÇÕES NORMAIS
        if not deve_entrar:
            # APENAS NÃO ENTRAR EM CONDIÇÕES EXTREMAS
            if risco_entrada == "RISCO_ALTO" and confianca_atual < 0.3 and len(st.session_state.gestor.historico) < 20:
                deve_entrar = False
                logging.warning("⏹️ Condições extremas - não entrar")
            elif len(entrada_assertiva) < 6:
                deve_entrar = False
                logging.warning("⏹️ Previsão insuficiente - não entrar")
            else:
                deve_entrar = True
                logging.info("🔥 Entrada forçada - Critérios normais")
        
        # ENVIAR ALERTA ASSERTIVO
        if deve_entrar and entrada_assertiva:
            enviar_alerta_assertivo(
                entrada_assertiva, 
                numero_real, 
                list(st.session_state.gestor.historico),
                performance
            )
            logging.info(f"✅ Entrada enviada - Risco: {risco_entrada}, Confiança: {confianca_atual:.2f}")
        else:
            logging.warning(f"⏹️ Entrada não enviada - Risco: {risco_entrada}, Confiança: {confianca_atual:.2f}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro no processamento: {e}")
    st.error("🔴 Reiniciando sistema...")
    # Em caso de erro, usar os últimos números do histórico
    numeros = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
    st.session_state.previsao_atual = numeros[-NUMERO_PREVISOES:] if len(numeros) >= NUMERO_PREVISOES else numeros

# =============================
# INTERFACE STREAMLIT 100% BASEADA EM HISTÓRICO COM XGBOOST 50+ FEATURES
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

# ANÁLISE DO SISTEMA
st.subheader("🔍 Análise Baseada em Histórico")
analise = st.session_state.gestor.get_analise_detalhada()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🚀 Modo", "ASSERTIVO" if analise["modo_assertivo"] else "EVOLUINDO")
with col2:
    st.metric("💪 Confiança", analise["confianca"])
with col3:
    st.metric("📈 Padrão", "✅" if analise["padrao_detectado"] else "⏳")

# NOVA SEÇÃO: XGBOOST - MACHINE LEARNING AVANÇADO
st.markdown("---")
st.subheader("🤖 IA XGBoost - Machine Learning Avançado (50+ Features)")

# Status do XGBoost
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
            with st.spinner("Treinando modelo de Machine Learning com 50+ features..."):
                sucesso = st.session_state.gestor.treinar_xgboost()
                if sucesso:
                    st.success("✅ XGBoost treinado com sucesso! (50+ features)")
                else:
                    st.error("❌ Falha no treinamento. Mais dados necessários (150+ registros)")
    with col2:
        if st.button("🔄 Forçar Re-treinamento"):
            with st.spinner("Re-treinando modelo com features expandidas..."):
                sucesso = st.session_state.gestor.treinar_xgboost(force_retrain=True)
                if sucesso:
                    st.success("✅ XGBoost re-treinado com features expandidas!")
                else:
                    st.warning("⚠️ Verifique se tem dados suficientes (150+ registros)")
else:
    st.warning("⚠️ XGBoost não disponível - usando métodos tradicionais")

# Informações do modelo
if xgboost_status["treinado"]:
    st.success("""
    **🎯 XGBoost Avançado Ativo:**
    - **50+ Features** expandidas
    - **Multi-janela temporal** (5, 10, 15 rodadas)
    - **Padrões complexos** capturados
    - **Feature importance** analisada
    - **Early stopping** para evitar overfitting
    """)
else:
    st.warning("""
    **📊 Coletando dados para XGBoost Avançado:**
    - **Necessário**: 150+ registros no histórico
    - **Features**: 50+ características analisadas
    - **Treinamento**: Automático quando dados suficientes
    - **Fallback**: Estratégia sequencial ativa
    """)

# SEÇÃO: PREVISÃO SEQUENCIAL
st.markdown("---")
st.subheader("🔄 PREVISÃO SEQUENCIAL")

performance_sequencial = st.session_state.gestor.get_performance_sequencial()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Acertos Seq", performance_sequencial["acertos"])
with col2:
    st.metric("❌ Erros Seq", performance_sequencial["erros"])
with col3:
    st.metric("📈 Assertividade Seq", performance_sequencial["taxa_acerto"])
with col4:
    st.metric("🔍 Análises", performance_sequencial["total_analises"])

# Mostrar análise sequencial atual
if st.session_state.ultimo_numero is not None and len(st.session_state.gestor.historico) > 10:
    # Analisar sequências para o último número
    sequencias = st.session_state.gestor.ia_assertiva.previsao_sequencial.analisar_sequencias_historicas(
        list(st.session_state.gestor.historico), 
        st.session_state.ultimo_numero
    )
    
    if sequencias:
        st.info(f"🔍 **Análise Sequencial para {st.session_state.ultimo_numero}:**")
        st.write(f"📊 Números que costumam sair após **{st.session_state.ultimo_numero}**: {', '.join(map(str, sequencias[:8]))}")

# DASHBOARD DE RISCO E CONFIANÇA
st.markdown("---")
st.subheader("📈 Análise de Risco e Confiança")

confianca = st.session_state.sistema_confianca.confianca
tendencia = st.session_state.sistema_confianca.tendencia
categoria_confianca = st.session_state.sistema_confianca.get_confianca_categoria()

risco = analisar_risco_entrada(
    list(st.session_state.gestor.historico), 
    st.session_state.previsao_atual
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Confiança", f"{confianca*100:.1f}%")
with col2:
    st.metric("📊 Categoria", categoria_confianca)
with col3:
    st.metric("⚠️ Risco Atual", risco)
with col4:
    st.metric("🔁 Sequência", f"{st.session_state.gestor_risco.sequencia_atual}")

st.progress(confianca)

# Verificar modo recuperação
modo_recuperacao = verificar_estrategia_recuperacao(
    list(st.session_state.gestor.historico), 
    st.session_state.ultimos_resultados
)

if modo_recuperacao:
    st.warning("🔄 **MODO RECUPERAÇÃO ATIVO** - Estratégia mais agressiva")
elif confianca > 0.7 and risco in ["RISCO_BAIXO", "RISCO_MODERADO"]:
    st.success("🔥 **CONDIÇÕES IDEAIS** - Entrada recomendada!")
elif confianca > 0.5 and risco != "RISCO_ALTO":
    st.info("💡 **CONDIÇÕES BOAS** - Entrada pode ser considerada")
else:
    st.warning("⚡ **CONDIÇÕES CAUTELOSAS** - Aguardar melhores oportunidades")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO BASEADA EM HISTÓRICO")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    origem = "XGBoost 50+ Features" if xgboost_status["ativo"] else "Sequencial"
    st.success(f"**🔥 PREVISÃO VIA {origem.upper()} - {len(previsao_valida)} NÚMEROS **")
    
    # Display IMPACTANTE
    st.markdown(f"### **{'  •  '.join(map(str, sorted(previsao_valida)))}**")
    
    st.write(f"**Estratégia:** {analise['estrategia_ativa']}")
    
    if analise['numeros_quentes']:
        st.write(f"**Números Quentes:** {', '.join(map(str, analise['numeros_quentes']))}")
    
else:
    st.warning("⚠️ Coletando dados históricos...")

# ENTRADA ASSERTIVA BASEADA EM HISTÓRICO
st.markdown("---")
st.subheader("🎯 ENTRADA PARA TELEGRAM (Baseada em Histórico)")

# CORREÇÃO: USAR A PREVISÃO ATUAL DIRETAMENTE
entrada_assertiva = st.session_state.previsao_atual

if entrada_assertiva:
    # Verificar condições antes de recomendar entrada
    risco_entrada = analisar_risco_entrada(list(st.session_state.gestor.historico), entrada_assertiva)
    confianca_atual = st.session_state.sistema_confianca.confianca
    modo_recuperacao = verificar_estrategia_recuperacao(
        list(st.session_state.gestor.historico), 
        st.session_state.ultimos_resultados
    )
    
    # LÓGICA SUPER FLEXÍVEL PARA RECOMENDAÇÃO NA INTERFACE
    deve_recomendar = (
        risco_entrada in ["RISCO_BAIXO", "RISCO_MODERADO"] or 
        confianca_atual > 0.4 or
        modo_recuperacao or
        len(entrada_assertiva) >= 6
    )
    
    if deve_recomendar:
        st.success(f"**🔔 {len(entrada_assertiva)} NÚMEROS CONFIRMADOS DO HISTÓRICO**")
        
        # Mostrar mensagem do Telegram
        numeros_ordenados = sorted(entrada_assertiva)
        primeira_linha = '   '.join(map(str, numeros_ordenados[:4]))
        segunda_linha = '   '.join(map(str, numeros_ordenados[4:]))
        mensagem_telegram = f"{primeira_linha}\n{segunda_linha}"
        
        st.code(mensagem_telegram, language=None)
        
        # Botão de envio
        if st.button("📤 Enviar Alerta Baseado em Histórico"):
            performance = {
                'acertos': st.session_state.acertos,
                'erros': st.session_state.erros,
                'taxa_acerto': f"{(st.session_state.acertos/(st.session_state.acertos+st.session_state.erros)*100):.1f}%" if (st.session_state.acertos+st.session_state.erros) > 0 else "0%"
            }
            
            enviar_alerta_assertivo(
                entrada_assertiva, 
                st.session_state.ultimo_numero, 
                list(st.session_state.gestor.historico),
                performance
            )
            st.success("✅ Alerta BASEADO EM HISTÓRICO enviado!")
    else:
        st.warning(f"⏹️ Entrada não recomendada - Risco: {risco_entrada}, Confiança: {categoria_confianca}")
else:
    st.warning("⏳ Gerando entrada baseada em histórico...")

# PERFORMANCE
st.markdown("---")
st.subheader("📊 Performance do Sistema")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("✅ Acertos", st.session_state.acertos)
with col2:
    st.metric("❌ Erros", st.session_state.erros)
with col3:
    total = st.session_state.acertos + st.session_state.erros
    taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
    st.metric("📈 Assertividade", f"{taxa_acerto:.1f}%")
with col4:
    st.metric("🛡️ Máx Sequência", st.session_state.gestor_risco.max_sequencia_negativa)

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
            st.info(f"🔍 Últimos 10 números: {numeros[-10:]}")
            st.info(f"📊 Números mais frequentes: {Counter(numeros).most_common(5)}")
            
            # Mostrar análise de padrões
            analise = analisar_padroes_assertivos(st.session_state.gestor.historico)
            st.info(f"🎯 Números quentes: {analise.get('numeros_quentes', [])}")
            st.info(f"🔄 Padrões repetição: {analise.get('padroes_repeticao', [])}")
            
            # Mostrar análise sequencial detalhada
            if st.session_state.ultimo_numero:
                sequencias = st.session_state.gestor.ia_assertiva.previsao_sequencial.analisar_sequencias_historicas(
                    list(st.session_state.gestor.historico), 
                    st.session_state.ultimo_numero
                )
                if sequencias:
                    st.info(f"🔢 Sequências após {st.session_state.ultimo_numero}: {sequencias}")
                    
            # Mostrar status XGBoost detalhado
            xgboost_status = st.session_state.gestor.get_status_xgboost()
            st.info(f"🤖 XGBoost - Treinado: {xgboost_status['treinado']}, Ativo: {xgboost_status['ativo']}")
            
            # Mostrar informações das features
            if xgboost_status["treinado"]:
                st.info(f"📈 Features geradas: {len(st.session_state.gestor.ia_assertiva.xgboost_predictor.feature_engineer.feature_names)}")
        else:
            st.info("📊 Histórico ainda vazio")

st.markdown("---")
st.markdown("### 🚀 **SISTEMA 100% BASEADO EM HISTÓRICO + XGBOOST 50+ FEATURES ATIVADO**")
st.markdown("*Estratégia de 8 números baseada exclusivamente no histórico de sorteios com Machine Learning Avançado*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Sistema Baseado em Histórico v14.0** - *XGBoost 50+ Features + Previsão Sequencial + Correções Críticas*")
