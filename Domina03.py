# RoletaHybridIA.py - SISTEMA ESPECIALISTA COM XGBOOST 50+ FEATURES SEM DUPLICADOS
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
# FUNÇÕES AUXILIARES
# =============================

def obter_vizinhos_fisicos(numero):
    """Retorna vizinhos físicos na roleta"""
    vizinhos = []
    for linha in ROULETTE_PHYSICAL_LAYOUT:
        if numero in linha:
            idx = linha.index(numero)
            if idx > 0:
                vizinhos.append(linha[idx-1])
            if idx < len(linha) - 1:
                vizinhos.append(linha[idx+1])
    return list(set(vizinhos))

def carregar_historico():
    """Carrega histórico do arquivo"""
    try:
        if os.path.exists(HISTORICO_PATH):
            with open(HISTORICO_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar histórico: {e}")
    return []

def salvar_historico(historico):
    """Salva histórico no arquivo"""
    try:
        with open(HISTORICO_PATH, 'w', encoding='utf-8') as f:
            json.dump(historico, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def carregar_metricas():
    """Carrega métricas do arquivo"""
    try:
        if os.path.exists(METRICAS_PATH):
            with open(METRICAS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar métricas: {e}")
    return {"acertos": 0, "erros": 0, "sequencia_atual": 0, "max_sequencia": 0}

def salvar_metricas(metricas):
    """Salva métricas no arquivo"""
    try:
        with open(METRICAS_PATH, 'w', encoding='utf-8') as f:
            json.dump(metricas, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Erro ao salvar métricas: {e}")

def enviar_telegram(mensagem, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    """Envia mensagem para o Telegram"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")
        return False

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
            
            # Garantir diversidade na previsão - SEM DUPLICADOS
            previsao_final = self._garantir_diversidade(previsao, historico, top_n)
            
            self.ultima_previsao = previsao_final
            logging.info(f"🎯 XGBoost com {len(ultimas_features[0])} features previu: {self.ultima_previsao}")
            
            return self.ultima_previsao
            
        except Exception as e:
            logging.error(f"❌ Erro na previsão XGBoost: {e}")
            return self._previsao_fallback(historico)
    
    def _garantir_diversidade(self, previsao, historico, top_n):
        """Garante que a previsão tenha números diversificados - SEM DUPLICADOS"""
        if len(previsao) >= top_n:
            # Remover duplicados mantendo a ordem
            previsao_sem_duplicados = []
            for num in previsao:
                if num not in previsao_sem_duplicados:
                    previsao_sem_duplicados.append(num)
            return previsao_sem_duplicados[:top_n]
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        diversificados = set(previsao)  # Começar com set para evitar duplicados
        
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
        
        # Se ainda não tiver números suficientes, completar com números únicos
        if len(diversificados) < top_n:
            for num in range(0, 37):
                if len(diversificados) < top_n and num not in diversificados:
                    diversificados.add(num)
        
        return list(diversificados)[:top_n]

    def _previsao_fallback(self, historico):
        """Previsão fallback quando XGBoost não está disponível"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        if len(numeros) >= NUMERO_PREVISOES:
            # Remover duplicados
            numeros_unicos = []
            for num in numeros[-NUMERO_PREVISOES*2:]:
                if num not in numeros_unicos:
                    numeros_unicos.append(num)
            return numeros_unicos[:NUMERO_PREVISOES]
        return [2, 5, 8, 11, 14, 17, 20, 23]  # Já são únicos
    
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
# SISTEMA DE PREVISÃO SEQUENCIAL MELHORADO - SEM DUPLICADOS
# =============================

class SistemaPrevisaoSequencial:
    def __init__(self):
        self.historico_sequencias = {}
        self.performance_sequencial = {"acertos": 0, "erros": 0}
        self.ultima_previsao = []
        
    def analisar_sequencias_historicas(self, historico, numero_atual):
        """Análise MAIS AGRESSIVA e INTELIGENTE de sequências - SEM DUPLICADOS"""
        
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
        
        # Pegar os números mais frequentes SEM DUPLICADOS
        numeros_mais_frequentes = []
        for num, count in contador.most_common(20):  # Pegar mais para filtrar
            if num not in numeros_mais_frequentes:
                numeros_mais_frequentes.append(num)
            if len(numeros_mais_frequentes) >= 12:  # Limitar a 12
                break
        
        logging.info(f"🔍 Sequência histórica APÓS {numero_atual}: {len(sequencias_encontradas)} ocorrências, tops: {numeros_mais_frequentes[:6]}")
        
        return numeros_mais_frequentes
    
    def gerar_previsao_sequencial(self, historico, ultimo_numero):
        """Gera previsão MAIS INTELIGENTE baseada em múltiplos fatores - SEM DUPLICADOS"""
        
        if not historico or ultimo_numero is None:
            return []
        
        # ANALISAR SEQUÊNCIAS HISTÓRICAS
        previsao_sequencial = self.analisar_sequencias_historicas(historico, ultimo_numero)
        
        # SE NÃO ENCONTROU PADRÕES FORTES, USAR ESTRATÉGIA ALTERNATIVA
        if len(previsao_sequencial) < 6:
            previsao_sequencial = self.estrategia_fallback_agressiva(historico, ultimo_numero)
        
        # FILTRAR E LIMITAR A 8 NÚMEROS - SEM DUPLICADOS
        previsao_filtrada = []
        for num in previsao_sequencial:
            if num not in previsao_filtrada:
                previsao_filtrada.append(num)
            if len(previsao_filtrada) >= NUMERO_PREVISOES:
                break
        
        self.ultima_previsao = previsao_filtrada
        
        logging.info(f"🎯 Previsão Sequencial GERADA: {self.ultima_previsao}")
        return self.ultima_previsao
    
    def estrategia_fallback_agressiva(self, historico, ultimo_numero):
        """Estratégia alternativa AGRESSIVA quando não há padrões claros - SEM DUPLICADOS"""
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return []
        
        previsao = set()  # Usar set para evitar duplicados
        
        # ESTRATÉGIA 1: VIZINHOS DO ÚLTIMO NÚMERO
        previsao.update(obter_vizinhos_fisicos(ultimo_numero))
        
        # ESTRATÉGIA 2: NÚMEROS QUENTES (últimas 15 rodadas)
        ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
        numeros_quentes = [num for num, count in Counter(ultimos_15).most_common(8)]
        previsao.update(numeros_quentes)
        
        # ESTRATÉGIA 3: NÚMEROS FRIOS (maior atraso)
        todos_numeros = set(range(0, 37))
        numeros_frios = []
        for num in todos_numeros:
            if num in numeros:
                ultima_pos = len(numeros) - 1 - numeros[::-1].index(num)
                atraso = len(numeros) - ultima_pos
            else:
                atraso = len(numeros)
            numeros_frios.append((num, atraso))
        
        numeros_frios.sort(key=lambda x: x[1], reverse=True)
        previsao.update([num for num, atraso in numeros_frios[:5]])
        
        # ESTRATÉGIA 4: NÚMEROS POR CARACTERÍSTICAS DIVERSAS
        caracteristicas = [
            [n for n in range(1, 37) if n % 2 == 0][:3],  # Pares
            [n for n in range(1, 37) if n % 2 == 1][:3],  # Ímpares
            PRIMEIRA_DUZIA[:2], SEGUNDA_DUZIA[:2], TERCEIRA_DUZIA[:2],
            COLUNA_1[:2], COLUNA_2[:2], COLUNA_3[:2]
        ]
        
        for grupo in caracteristicas:
            previsao.update(grupo)
        
        return list(previsao)
    
    def verificar_acerto(self, numero_sorteado):
        """Verifica se acertou a previsão sequencial"""
        if not self.ultima_previsao or numero_sorteado is None:
            return None
        
        acertou = numero_sorteado in self.ultima_previsao
        if acertou:
            self.performance_sequencial["acertos"] += 1
        else:
            self.performance_sequencial["erros"] += 1
        
        return acertou
    
    def get_performance(self):
        total = self.performance_sequencial["acertos"] + self.performance_sequencial["erros"]
        taxa = (self.performance_sequencial["acertos"] / total * 100) if total > 0 else 0
        return {
            "acertos": self.performance_sequencial["acertos"],
            "erros": self.performance_sequencial["erros"],
            "taxa_acerto": f"{taxa:.1f}%"
        }

# =============================
# SISTEMA PRINCIPAL HYBRID IA
# =============================

class RoletaHybridIA:
    def __init__(self):
        self.historico = carregar_historico()
        self.metricas = carregar_metricas()
        self.xgb_predictor = XGBoostPredictor()
        self.sequencial_predictor = SistemaPrevisaoSequencial()
        self.sistema_confianca = SistemaConfianca()
        self.gestao_risco = SistemaGestaoRisco()
        self.ultima_atualizacao = None
        self.ultimo_numero_sorteado = None
        self.previsao_atual = []
        self.analise_risco_atual = "RISCO_MODERADO"
        
        # Carregar modelo XGBoost se existir
        self._carregar_modelo_existente()
    
    def _carregar_modelo_existente(self):
        """Carrega modelo XGBoost pré-existente"""
        try:
            if XGBOOST_DISPONIVEL and os.path.exists(XGB_MODEL_PATH):
                self.xgb_predictor.model = xgb.XGBClassifier()
                self.xgb_predictor.model.load_model(XGB_MODEL_PATH)
                self.xgb_predictor.feature_engineer = FeatureEngineer.carregar_engineer()
                self.xgb_predictor.treinado = True
                logging.info("🤖 Modelo XGBoost carregado com sucesso!")
        except Exception as e:
            logging.error(f"❌ Erro ao carregar modelo XGBoost: {e}")
    
    def buscar_dados_api(self):
        """Busca dados mais recentes da API"""
        try:
            response = requests.get(API_URL, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                dados = response.json()
                
                # Extrair número sorteado
                numero_sorteado = None
                if 'results' in dados and len(dados['results']) > 0:
                    numero_sorteado = dados['results'][0].get('card')
                
                if numero_sorteado is not None:
                    self._processar_novo_numero(numero_sorteado)
                    return True
                    
            return False
        except Exception as e:
            logging.error(f"❌ Erro ao buscar dados da API: {e}")
            return False
    
    def _processar_novo_numero(self, numero_sorteado):
        """Processa novo número sorteado"""
        if self.ultimo_numero_sorteado == numero_sorteado:
            return  # Número já processado
        
        self.ultimo_numero_sorteado = numero_sorteado
        timestamp = datetime.now().isoformat()
        
        # Adicionar ao histórico
        novo_registro = {
            'number': numero_sorteado,
            'timestamp': timestamp,
            'previsao_acertou': None
        }
        
        # Verificar se acertou a previsão anterior
        if self.previsao_atual:
            acertou = numero_sorteado in self.previsao_atual
            novo_registro['previsao_acertou'] = acertou
            
            # Atualizar métricas
            if acertou:
                self.metricas["acertos"] += 1
                self.gestao_risco.atualizar_sequencia("GREEN")
            else:
                self.metricas["erros"] += 1
                self.gestao_risco.atualizar_sequencia("RED")
            
            # Atualizar confiança
            self.sistema_confianca.atualizar_confianca(acertou)
            
            # Enviar alerta Telegram se acertou
            if acertou:
                mensagem = f"🎯 ACERTOU! Número {numero_sorteado} estava na previsão!\n"
                mensagem += f"📊 Sequência atual: {self.gestao_risco.sequencia_atual}\n"
                mensagem += f"💯 Confiança: {self.sistema_confianca.get_confianca_categoria()}"
                enviar_telegram(mensagem)
        
        self.historico.append(novo_registro)
        
        # Manter histórico limitado
        if len(self.historico) > 1000:
            self.historico = self.historico[-800:]
        
        # Salvar dados
        salvar_historico(self.historico)
        salvar_metricas(self.metricas)
        
        # Treinar XGBoost periodicamente
        if len(self.historico) % 50 == 0 and len(self.historico) >= 150:
            self.xgb_predictor.treinar_modelo(self.historico)
        
        logging.info(f"🔢 Novo número processado: {numero_sorteado}")
    
    def gerar_previsao_hibrida(self):
        """Gera previsão híbrida combinando XGBoost e análise sequencial"""
        if len(self.historico) < 10:
            return []
        
        ultimo_numero = self.historico[-1]['number'] if self.historico else None
        
        # Gerar previsões de ambos os sistemas
        previsao_xgb = self.xgb_predictor.prever_proximos_numeros(self.historico, NUMERO_PREVISOES)
        previsao_seq = self.sequencial_predictor.gerar_previsao_sequencial(self.historico, ultimo_numero)
        
        # COMBINAR PREVISÕES - SEM DUPLICADOS
        previsao_combinada = []
        
        # Priorizar números que aparecem em ambas as previsões
        comuns = set(previsao_xgb) & set(previsao_seq)
        for num in comuns:
            if num not in previsao_combinada:
                previsao_combinada.append(num)
        
        # Adicionar do XGBoost
        for num in previsao_xgb:
            if len(previsao_combinada) < NUMERO_PREVISOES and num not in previsao_combinada:
                previsao_combinada.append(num)
        
        # Completar com análise sequencial se necessário
        for num in previsao_seq:
            if len(previsao_combinada) < NUMERO_PREVISOES and num not in previsao_combinada:
                previsao_combinada.append(num)
        
        # Garantir que temos NUMERO_PREVISOES números únicos
        if len(previsao_combinada) < NUMERO_PREVISOES:
            previsao_combinada = self._completar_previsao(previsao_combinada)
        
        self.previsao_atual = previsao_combinada
        self._analisar_risco()
        
        logging.info(f"🎯 PREVISÃO HÍBRIDA GERADA: {self.previsao_atual}")
        return self.previsao_atual
    
    def _completar_previsao(self, previsao):
        """Completa previsão com números diversificados - SEM DUPLICADOS"""
        completos = set(previsao)
        
        # Adicionar números por características
        grupos = [
            list(range(0, 37)),  # Todos os números
            [n for n in range(1, 37) if n % 2 == 0],  # Pares
            [n for n in range(1, 37) if n % 2 == 1],  # Ímpares
            PRIMEIRA_DUZIA, SEGUNDA_DUZIA, TERCEIRA_DUZIA,
            COLUNA_1, COLUNA_2, COLUNA_3
        ]
        
        for grupo in grupos:
            for num in grupo:
                if len(completos) < NUMERO_PREVISOES and num not in completos:
                    completos.add(num)
                if len(completos) >= NUMERO_PREVISOES:
                    break
            if len(completos) >= NUMERO_PREVISOES:
                break
        
        return list(completos)[:NUMERO_PREVISOES]
    
    def _analisar_risco(self):
        """Analisa risco da previsão atual"""
        if not self.previsao_atual or len(self.historico) < 20:
            self.analise_risco_atual = "RISCO_MODERADO"
            return
        
        numeros = [h['number'] for h in self.historico if h.get('number') is not None]
        ultimos_10 = numeros[-10:] if len(numeros) >= 10 else numeros
        
        # Calcular métricas de risco
        acertos_recentes = sum(1 for h in self.historico[-10:] if h.get('previsao_acertou'))
        confianca = self.sistema_confianca.confianca
        
        if acertos_recentes >= 4 and confianca > 0.6:
            self.analise_risco_atual = "RISCO_BAIXO"
        elif acertos_recentes >= 2 or confianca > 0.4:
            self.analise_risco_atual = "RISCO_MODERADO"
        else:
            self.analise_risco_atual = "RISCO_ALTO"
    
    def get_estatisticas(self):
        """Retorna estatísticas completas do sistema"""
        total_previsoes = self.metricas["acertos"] + self.metricas["erros"]
        taxa_acerto = (self.metricas["acertos"] / total_previsoes * 100) if total_previsoes > 0 else 0
        
        performance_xgb = self.xgb_predictor.get_performance()
        performance_seq = self.sequencial_predictor.get_performance()
        
        return {
            "historico_total": len(self.historico),
            "acertos_totais": self.metricas["acertos"],
            "erros_totais": self.metricas["erros"],
            "taxa_acerto_geral": f"{taxa_acerto:.1f}%",
            "sequencia_atual": self.gestao_risco.sequencia_atual,
            "max_sequencia": self.gestao_risco.max_sequencia_negativa,
            "confianca": self.sistema_confianca.get_confianca_categoria(),
            "nivel_risco": self.analise_risco_atual,
            "xgb_treinado": self.xgb_predictor.treinado,
            "performance_xgb": performance_xgb,
            "performance_sequencial": performance_seq,
            "ultima_previsao": self.previsao_atual,
            "ultimo_numero": self.ultimo_numero_sorteado
        }

# =============================
# INTERFACE STREAMLIT
# =============================

def main():
    st.set_page_config(
        page_title="Roleta Hybrid IA - Sistema Especialista",
        page_icon="🎰",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🎰 Roleta Hybrid IA - Sistema Especialista com XGBoost")
    st.markdown("---")
    
    # Inicializar sistema
    if 'roleta_ia' not in st.session_state:
        st.session_state.roleta_ia = RoletaHybridIA()
        st.session_state.ultima_atualizacao = datetime.now()
    
    roleta_ia = st.session_state.roleta_ia
    
    # Sidebar
    with st.sidebar:
        st.header("🔄 Controle")
        
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            with st.spinner("Buscando dados atualizados..."):
                if roleta_ia.buscar_dados_api():
                    st.success("Dados atualizados!")
                    st.session_state.ultima_atualizacao = datetime.now()
                else:
                    st.error("Erro ao buscar dados")
        
        if st.button("🎯 Gerar Nova Previsão", use_container_width=True):
            with st.spinner("Gerando previsão híbrida..."):
                previsao = roleta_ia.gerar_previsao_hibrida()
                if previsao:
                    st.success("Previsão gerada!")
                    
                    # Enviar previsão para Telegram
                    mensagem = f"🎯 NOVA PREVISÃO GERADA:\n"
                    mensagem += f"🔢 Números: {previsao}\n"
                    mensagem += f"📊 Risco: {roleta_ia.analise_risco_atual}\n"
                    mensagem += f"💯 Confiança: {roleta_ia.sistema_confianca.get_confianca_categoria()}\n"
                    mensagem += f"🕒 {datetime.now().strftime('%H:%M:%S')}"
                    enviar_telegram(mensagem, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
                else:
                    st.error("Erro ao gerar previsão")
        
        if st.button("🤖 Treinar XGBoost", use_container_width=True) and XGBOOST_DISPONIVEL:
            with st.spinner("Treinando modelo XGBoost..."):
                if roleta_ia.xgb_predictor.treinar_modelo(roleta_ia.historico, force_retrain=True):
                    st.success("Modelo treinado com sucesso!")
                else:
                    st.warning("Modelo não pôde ser treinado (dados insuficientes)")
        
        st.markdown("---")
        st.header("📊 Status do Sistema")
        
        estatisticas = roleta_ia.get_estatisticas()
        
        st.metric("Histórico Total", estatisticas["historico_total"])
        st.metric("Acertos", estatisticas["acertos_totais"])
        st.metric("Taxa de Acerto", estatisticas["taxa_acerto_geral"])
        st.metric("Sequência Atual", estatisticas["sequencia_atual"])
        st.metric("Nível de Confiança", estatisticas["confianca"])
        st.metric("Nível de Risco", estatisticas["nivel_risco"])
        
        if estatisticas["xgb_treinado"]:
            st.success("🤖 XGBoost Treinado")
        else:
            st.warning("🤖 XGBoost Não Treinado")
    
    # Layout principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎯 Previsão Atual")
        
        if roleta_ia.previsao_atual:
            # Mostrar números previstos
            st.subheader(f"🎯 {len(roleta_ia.previsao_atual)} Números Previstos:")
            
            # Layout organizado dos números
            cols = st.columns(4)
            for i, numero in enumerate(roleta_ia.previsao_atual):
                with cols[i % 4]:
                    cor = "🟢" if numero % 2 == 0 else "🔴"
                    st.metric(f"{cor} Número {numero}", numero)
            
            # Análise de risco
            risco_cor = {
                "RISCO_BAIXO": "🟢",
                "RISCO_MODERADO": "🟡", 
                "RISCO_ALTO": "🔴"
            }
            
            st.info(f"""
            **Análise de Risco:** {risco_cor.get(roleta_ia.analise_risco_atual, "⚪")} {roleta_ia.analise_risco_atual}
            **Confiança do Sistema:** {roleta_ia.sistema_confianca.get_confianca_categoria()}
            **Recomendação:** {'✅ ENTRAR FORTE' if roleta_ia.analise_risco_atual == 'RISCO_BAIXO' else '⚠️ ENTRAR COM CAUTELA' if roleta_ia.analise_risco_atual == 'RISCO_MODERADO' else '🔴 AGUARDAR'}
            """)
        else:
            st.warning("⚠️ Nenhuma previsão gerada. Clique em 'Gerar Nova Previsão'")
    
    with col2:
        st.header("📈 Performance")
        
        # Métricas de performance
        perf_xgb = roleta_ia.xgb_predictor.get_performance()
        perf_seq = roleta_ia.sequencial_predictor.get_performance()
        
        st.metric("XGBoost - Taxa Acerto", perf_xgb["taxa_acerto"])
        st.metric("Sequencial - Taxa Acerto", perf_seq["taxa_acerto"])
        
        # Último número
        if roleta_ia.ultimo_numero_sorteado is not None:
            st.metric("Último Número Sorteado", roleta_ia.ultimo_numero_sorteado)
        
        # Gestão de risco
        st.subheader("💰 Gestão de Risco")
        aposta_recomendada = roleta_ia.gestao_risco.calcular_tamanho_aposta(
            roleta_ia.sistema_confianca.confianca
        )
        st.metric("Aposta Recomendada", f"R$ {aposta_recomendada:.2f}")
    
    # Histórico recente
    st.header("📋 Histórico Recente")
    
    if roleta_ia.historico:
        # Últimos 20 resultados
        historico_recente = roleta_ia.historico[-20:]
        
        # Criar DataFrame para display
        dados_tabela = []
        for registro in historico_recente:
            dados_tabela.append({
                "Número": registro['number'],
                "Acertou": "✅" if registro.get('previsao_acertou') else "❌" if registro.get('previsao_acertou') is False else "➖",
                "Timestamp": registro['timestamp']
            })
        
        df = pd.DataFrame(dados_tabela)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📊 Nenhum dado histórico disponível")
    
    # Informações do sistema
    with st.expander("🔧 Informações Técnicas do Sistema"):
        st.write(f"**XGBoost Disponível:** {XGBOOST_DISPONIVEL}")
        st.write(f"**Modelo Treinado:** {roleta_ia.xgb_predictor.treinado}")
        st.write(f"**Tamanho do Histórico:** {len(roleta_ia.historico)}")
        st.write(f"**Última Atualização:** {st.session_state.ultima_atualizacao}")
        
        if roleta_ia.xgb_predictor.treinado and roleta_ia.xgb_predictor.feature_engineer.feature_names:
            st.write(f"**Total de Features:** {len(roleta_ia.xgb_predictor.feature_engineer.feature_names)}")
    
    # Auto-refresh
    st_autorefresh(interval=30000, key="auto_refresh")

if __name__ == "__main__":
    main()
