import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import pandas as pd
from collections import Counter, deque
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.utils import resample
import joblib
from streamlit_autorefresh import st_autorefresh
import pickle
import warnings
import math
from scipy.stats import binomtest, chi2_contingency
import random
warnings.filterwarnings('ignore')

# =============================
# CONFIGURAÇÕES DE LOGGING
# =============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"
ML_MODEL_PATH = "ml_roleta_model.pkl"
SCALER_PATH = "ml_scaler.pkl"
META_PATH = "ml_meta.pkl"
RL_MODEL_PATH = "rl_model.pkl"

# =============================
# CONFIGURAÇÕES DA API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# SISTEMA DE VALIDAÇÃO ESTATÍSTICA
# =============================
class SistemaValidacaoEstatistica:
    def __init__(self):
        self.testes_realizados = 0
        self.falsos_positivos = 0
        self.verdadeiros_positivos = 0
        self.confianca_minima = 0.95
        
    def teste_binomial_90porcento(self, acertos, tentativas):
        if tentativas < 30:
            return {
                'confianca': 0,
                'p_value': 1.0,
                'mensagem': f"Amostra muito pequena (n={tentativas})"
            }
        
        resultado = binomtest(
            k=acertos,
            n=tentativas,
            p=0.90,
            alternative='greater'
        )
        
        confianca = 1 - resultado.pvalue
        
        return {
            'confianca': confianca,
            'p_value': resultado.pvalue,
            'mensagem': f"Confiança estatística: {confianca:.1%}",
            'rejeita_h0': resultado.pvalue < 0.05
        }
    
    def calcular_intervalo_confianca(self, acertos, tentativas):
        if tentativas == 0:
            return (0, 0, 0)
        
        p = acertos / tentativas
        z = 1.96
        margem = z * math.sqrt((p * (1 - p)) / tentativas)
        
        return (p - margem, p, p + margem)

# =============================
# SISTEMA DE APRENDIZADO POR REFORÇO SIMPLIFICADO
# =============================
class SistemaAprendizadoReforco:
    def __init__(self):
        self.historico_aprendizado = deque(maxlen=500)
        self.melhores_combinacoes = {}
        self.piores_combinacoes = {}
        self.contador_analise = 0
        
    def analisar_resultado(self, resultado):
        try:
            self.contador_analise += 1
            
            acerto = resultado['acerto']
            estrategia = resultado['estrategia']
            zonas_envolvidas = resultado.get('zonas_envolvidas', [])
            
            if len(zonas_envolvidas) > 1:
                combinacao = tuple(sorted(zonas_envolvidas))
                
                if combinacao not in self.melhores_combinacoes:
                    self.melhores_combinacoes[combinacao] = {
                        'acertos': 0,
                        'tentativas': 0,
                        'eficiencia': 0.0,
                        'sequencia_atual_acertos': 0,
                        'sequencia_atual_erros': 0,
                        'ultimos_resultados': deque(maxlen=10)
                    }
                
                dados = self.melhores_combinacoes[combinacao]
                dados['tentativas'] += 1
                dados['ultimos_resultados'].append(acerto)
                
                if acerto:
                    dados['acertos'] += 1
                    dados['sequencia_atual_acertos'] += 1
                    dados['sequencia_atual_erros'] = 0
                else:
                    dados['sequencia_atual_erros'] += 1
                    dados['sequencia_atual_acertos'] = 0
                
                # Limitar sequências
                if dados['sequencia_atual_acertos'] > 10:
                    dados['sequencia_atual_acertos'] = 0
                if dados['sequencia_atual_erros'] > 10:
                    dados['sequencia_atual_erros'] = 0
                
                # Calcular eficiência
                if dados['tentativas'] > 0:
                    dados['eficiencia'] = (dados['acertos'] / dados['tentativas']) * 100
                
                # Se performance ruim, mover para piores
                if (dados['tentativas'] >= 5 and 
                    dados['eficiencia'] < 30 and
                    dados['sequencia_atual_erros'] >= 2):
                    
                    if combinacao not in self.piores_combinacoes:
                        self.piores_combinacoes[combinacao] = dados.copy()
            
            registro = {
                'numero': resultado['numero'],
                'acerto': acerto,
                'estrategia': estrategia,
                'zonas': resultado.get('zonas_envolvidas', []),
                'timestamp': len(self.historico_aprendizado)
            }
            
            self.historico_aprendizado.append(registro)
            
            return self.gerar_recomendacoes()
            
        except Exception as e:
            logging.error(f"Erro no sistema de aprendizado: {e}")
            return {}
    
    def gerar_recomendacoes(self):
        recomendacoes = {
            'melhor_combinacao': None,
            'evitar_combinacao': None
        }
        
        combinacoes_validadas = []
        for combinacao, dados in self.melhores_combinacoes.items():
            if dados['tentativas'] >= 3 and dados['eficiencia'] >= 40:
                score = dados['eficiencia']
                if dados['sequencia_atual_acertos'] >= 2:
                    score *= 1.1
                
                combinacoes_validadas.append({
                    'combinacao': combinacao,
                    'score': score,
                    'eficiencia': dados['eficiencia'],
                    'tentativas': dados['tentativas'],
                    'sequencia_acertos': dados['sequencia_atual_acertos']
                })
        
        if combinacoes_validadas:
            combinacoes_validadas.sort(key=lambda x: x['score'], reverse=True)
            melhor = combinacoes_validadas[0]
            recomendacoes['melhor_combinacao'] = melhor['combinacao']
        
        for combinacao, dados in self.piores_combinacoes.items():
            if dados.get('tentativas', 0) >= 3 and dados.get('eficiencia', 0) < 30:
                recomendacoes['evitar_combinacao'] = combinacao
                break
        
        return recomendacoes

# =============================
# SISTEMA DE OTIMIZAÇÃO DINÂMICA
# =============================
class SistemaOtimizacaoDinamica:
    def __init__(self):
        self.aprendizado = SistemaAprendizadoReforco()
        self.ultima_recomendacao = None
        self.contador_otimizacoes = 0
        self.performance_historica = deque(maxlen=50)
        
    def processar_resultado(self, resultado):
        try:
            recomendacoes = self.aprendizado.analisar_resultado(resultado)
            
            self.performance_historica.append({
                'timestamp': len(self.performance_historica),
                'acerto': resultado['acerto']
            })
            
            self.ultima_recomendacao = recomendacoes
            self.contador_otimizacoes += 1
            
            return recomendacoes
            
        except Exception as e:
            logging.error(f"Erro no sistema de otimização: {e}")
            return None

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================
def inicializar_config_alertas():
    if 'alertas_config' not in st.session_state:
        st.session_state.alertas_config = {
            'alertas_previsao': True,
            'alertas_resultado': True,
            'alertas_rotacao': True,
            'alertas_tendencia': True,
            'alertas_treinamento': True,
            'alertas_erros': True,
            'alertas_acertos': True,
            'alertas_estatisticos': True
        }

inicializar_config_alertas()

# =============================
# FUNÇÕES DE PERSISTÊNCIA CORRIGIDAS
# =============================
def verificar_consistencia_sistema(sistema):
    """Verifica e corrige inconsistências nos dados"""
    try:
        # Verificar contadores básicos
        total_historico = len(sistema.historico_desempenho)
        
        if total_historico > 0:
            # Recalcular acertos reais
            acertos_reais = sum(1 for r in sistema.historico_desempenho if r.get('acerto', False))
            erros_reais = total_historico - acertos_reais
            
            # Corrigir se discrepância grande
            if abs(sistema.acertos - acertos_reais) > 100:
                logging.warning(f"Corrigindo acertos: {sistema.acertos} -> {acertos_reais}")
                sistema.acertos = acertos_reais
            
            if abs(sistema.erros - erros_reais) > 100:
                logging.warning(f"Corrigindo erros: {sistema.erros} -> {erros_reais}")
                sistema.erros = erros_reais
        
        # Limitar sequências
        if sistema.sequencia_acertos > 10:
            sistema.sequencia_acertos = 0
        if sistema.sequencia_erros > 10:
            sistema.sequencia_erros = 0
        
        # Limitar histórico
        if len(sistema.historico_desempenho) > 1000:
            sistema.historico_desempenho = sistema.historico_desempenho[-500:]
        
        return True
        
    except Exception as e:
        logging.error(f"Erro na verificação de consistência: {e}")
        return False

def salvar_sessao():
    """Salva dados da sessão com verificação"""
    try:
        if 'sistema' not in st.session_state:
            return False
            
        sistema = st.session_state.sistema
        
        # Verificar consistência antes de salvar
        verificar_consistencia_sistema(sistema)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'alertas_config': st.session_state.get('alertas_config', {}),
            
            # Dados do sistema
            'sistema_acertos': sistema.acertos,
            'sistema_erros': sistema.erros,
            'sistema_estrategias_contador': sistema.estrategias_contador,
            'sistema_historico_desempenho': sistema.historico_desempenho[-200:] if len(sistema.historico_desempenho) > 0 else [],
            'sistema_contador_sorteios_global': sistema.contador_sorteios_global,
            'sistema_sequencia_erros': min(sistema.sequencia_erros, 10),
            'sistema_sequencia_acertos': min(sistema.sequencia_acertos, 10),
            'estrategia_selecionada': sistema.estrategia_selecionada,
            
            # Combinações
            'sistema_historico_combinacoes': {},
            'sistema_combinacoes_quentes': [],
            'sistema_combinacoes_frias': [],
        }
        
        # Salvar combinações válidas
        for combo, dados in sistema.historico_combinacoes.items():
            if isinstance(dados, dict) and dados.get('total', 0) > 0:
                if dados['total'] >= dados.get('acertos', 0):
                    session_data['sistema_historico_combinacoes'][combo] = dados
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info(f"Sessão salva: {sistema.acertos} acertos, {sistema.erros} erros")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao salvar sessão: {e}")
        return False

def carregar_sessao():
    """Carrega dados da sessão com validação"""
    try:
        if not os.path.exists(SESSION_DATA_PATH):
            return False
            
        with open(SESSION_DATA_PATH, 'rb') as f:
            session_data = pickle.load(f)
        
        if not isinstance(session_data, dict):
            return False
        
        # Carregar dados básicos
        st.session_state.historico = session_data.get('historico', [])
        st.session_state.telegram_token = session_data.get('telegram_token', '')
        st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
        
        if 'alertas_config' in session_data:
            st.session_state.alertas_config = session_data['alertas_config']
        else:
            inicializar_config_alertas()
        
        # Inicializar sistema se necessário
        if 'sistema' not in st.session_state:
            st.session_state.sistema = SistemaRoletaCompleto()
        
        sistema = st.session_state.sistema
        
        # Carregar dados do sistema
        sistema.acertos = int(session_data.get('sistema_acertos', 0))
        sistema.erros = int(session_data.get('sistema_erros', 0))
        sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
        sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
        sistema.contador_sorteios_global = int(session_data.get('sistema_contador_sorteios_global', 0))
        sistema.sequencia_erros = int(session_data.get('sistema_sequencia_erros', 0))
        sistema.sequencia_acertos = int(session_data.get('sistema_sequencia_acertos', 0))
        sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Zonas')
        
        # Carregar combinações
        sistema.historico_combinacoes = session_data.get('sistema_historico_combinacoes', {})
        sistema.combinacoes_quentes = session_data.get('sistema_combinacoes_quentes', [])
        sistema.combinacoes_frias = session_data.get('sistema_combinacoes_frias', [])
        
        # Verificar consistência
        verificar_consistencia_sistema(sistema)
        
        logging.info(f"Sessão carregada: {sistema.acertos} acertos, {sistema.erros} erros")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao carregar sessão: {e}")
        return False

# =============================
# FUNÇÕES DE NOTIFICAÇÃO
# =============================
def enviar_previsao_super_simplificada(previsao):
    try:
        if not previsao:
            return
            
        nome_estrategia = previsao.get('nome', 'Desconhecida')
        numeros_apostar = previsao.get('numeros_apostar', [])
        
        if not numeros_apostar:
            return
        
        st.toast(f"🎯 PREVISÃO CONFIRMADA - {nome_estrategia}", icon="🔥")
        
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    try:
        if acerto:
            st.toast(f"✅ Acerto! Número {numero_real}", icon="✅")
        else:
            st.toast(f"❌ Erro! Número {numero_real}", icon="❌")
        
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova):
    try:
        mensagem = f"🔄 Rotação: {estrategia_anterior} → {estrategia_nova}"
        st.toast(mensagem, icon="🔄")
        
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

# =============================
# SISTEMA DE DETECÇÃO DE TENDÊNCIAS
# =============================
class SistemaTendencias:
    def __init__(self):
        self.historico_tendencias = deque(maxlen=20)
        self.tendencia_ativa = None
        self.estado_tendencia = "aguardando"
        self.contador_confirmacoes = 0
        self.contador_acertos_tendencia = 0
        self.contador_erros_tendencia = 0
        
    def analisar_tendencia(self, zonas_rankeadas, acerto_ultima=False, zona_acertada=None):
        if not zonas_rankeadas:
            return {
                'estado': 'aguardando',
                'zona_dominante': None,
                'confianca': 0.1,
                'acao': 'aguardar',
                'mensagem': 'Sem dados suficientes'
            }
        
        try:
            zona_top1 = zonas_rankeadas[0][0] if zonas_rankeadas else None
            
            if self.estado_tendencia == "aguardando":
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                return {
                    'estado': 'formando',
                    'zona_dominante': zona_top1,
                    'confianca': 0.4,
                    'acao': 'aguardar',
                    'mensagem': f'Tendência se formando - {zona_top1}'
                }
            
            return {
                'estado': self.estado_tendencia,
                'zona_dominante': self.tendencia_ativa,
                'confianca': 0.5,
                'acao': 'aguardar',
                'mensagem': f'Estado: {self.estado_tendencia}'
            }
            
        except Exception as e:
            logging.error(f"Erro na análise de tendência: {e}")
            return {
                'estado': 'aguardando',
                'zona_dominante': None,
                'confianca': 0.1,
                'acao': 'aguardar',
                'mensagem': 'Erro na análise'
            }

# =============================
# SISTEMA DE SELEÇÃO INTELIGENTE
# =============================
class SistemaSelecaoInteligente:
    def __init__(self):
        self.roleta = RoletaInteligente()
        
    def selecionar_melhores_10_numeros(self, numeros_candidatos, historico, estrategia_tipo="Zonas"):
        if len(numeros_candidatos) <= 10:
            return numeros_candidatos
            
        scores = {}
        for numero in numeros_candidatos:
            scores[numero] = self.calcular_score_numero(numero, historico)
        
        numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhores_10 = [num for num, score in numeros_ordenados[:10]]
        
        return melhores_10
    
    def calcular_score_numero(self, numero, historico):
        try:
            if len(historico) < 5:
                return 0.5
            
            # Frequência recente
            historico_lista = list(historico)
            ultimos_10 = historico_lista[-10:] if len(historico_lista) >= 10 else historico_lista
            freq_recente = sum(1 for n in ultimos_10 if n == numero) / len(ultimos_10) if ultimos_10 else 0
            
            # Posição na roda
            posicao = self.roleta.get_posicao_race(numero)
            score_posicao = 0.5
            
            if posicao != -1 and len(historico_lista) >= 2:
                ultimo = historico_lista[-1]
                pos_ultimo = self.roleta.get_posicao_race(ultimo)
                if pos_ultimo != -1:
                    distancia = min(abs(posicao - pos_ultimo), 37 - abs(posicao - pos_ultimo))
                    score_posicao = 1 - (distancia / 18)
            
            # Score final
            score_total = (freq_recente * 0.6) + (score_posicao * 0.4)
            return min(score_total, 1.0)
            
        except Exception as e:
            logging.error(f"Erro ao calcular score: {e}")
            return 0.5

# =============================
# CLASSE DA ROLETA
# =============================
class RoletaInteligente:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_zona(self, numero_central, quantidade=6):
        if numero_central not in self.race:
            return []
        
        posicao = self.race.index(numero_central)
        vizinhos = []
        
        for offset in range(-quantidade, quantidade + 1):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        return list(set(vizinhos))

    def get_posicao_race(self, numero):
        try:
            if numero in self.race:
                return self.race.index(numero)
            return -1
        except:
            return -1

    def get_vizinhos_fisicos(self, numero, raio=3):
        if numero not in self.race:
            return []
        
        posicao = self.race.index(numero)
        vizinhos = []
        
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinho = self.race[(posicao + offset) % len(self.race)]
                vizinhos.append(vizinho)
        
        return vizinhos

# =============================
# ESTRATÉGIA DAS ZONAS SIMPLIFICADA
# =============================
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=50)
        self.nome = "Zonas Otimizada"
        
        self.zonas = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.numeros_zonas = {}
        for nome, central in self.zonas.items():
            self.numeros_zonas[nome] = self.roleta.get_vizinhos_zona(central, 6)

        self.sistema_selecao = SistemaSelecaoInteligente()

    def adicionar_numero(self, numero):
        self.historico.append(numero)

    def analisar_zonas_com_inversao(self):
        if len(self.historico) < 10:
            return None
            
        # Calcular frequências
        zonas_score = {}
        for zona, numeros in self.numeros_zonas.items():
            freq_recente = sum(1 for n in list(self.historico)[-10:] if n in numeros)
            zonas_score[zona] = freq_recente
        
        if not zonas_score:
            return None
        
        # Ordenar zonas
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        
        if len(zonas_rankeadas) >= 2:
            zona1, score1 = zonas_rankeadas[0]
            zona2, score2 = zonas_rankeadas[1]
            
            # Combinar números das duas melhores zonas
            numeros_combinados = list(set(self.numeros_zonas[zona1] + self.numeros_zonas[zona2]))
            
            # Selecionar melhores 10
            if len(numeros_combinados) > 10:
                numeros_combinados = self.sistema_selecao.selecionar_melhores_10_numeros(
                    numeros_combinados, self.historico, "Zonas"
                )
            
            return {
                'nome': f'Zonas Duplas - {zona1} + {zona2}',
                'numeros_apostar': numeros_combinados,
                'zonas_envolvidas': [zona1, zona2],
                'tipo': 'dupla',
                'selecao_inteligente': True
            }
        
        return None

    def analisar_zonas(self):
        return self.analisar_zonas_com_inversao()

# =============================
# SISTEMA PRINCIPAL CORRIGIDO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Zonas"
        self.contador_sorteios_global = 0
        
        self.sequencia_erros = 0
        self.sequencia_acertos = 0
        
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        self.sistema_tendencias = SistemaTendencias()
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def atualizar_desempenho_combinacao(self, zonas_envolvidas, acerto):
        """Atualiza desempenho de combinações"""
        if len(zonas_envolvidas) > 1:
            combinacao = tuple(sorted(zonas_envolvidas))
            
            if combinacao not in self.historico_combinacoes:
                self.historico_combinacoes[combinacao] = {
                    'acertos': 0, 
                    'total': 0, 
                    'eficiencia': 0.0,
                    'sequencia_acertos': 0,
                    'sequencia_erros': 0
                }
            
            dados = self.historico_combinacoes[combinacao]
            dados['total'] += 1
            
            if acerto:
                dados['acertos'] += 1
                dados['sequencia_acertos'] += 1
                dados['sequencia_erros'] = 0
            else:
                dados['sequencia_erros'] += 1
                dados['sequencia_acertos'] = 0
            
            # Limitar sequências
            if dados['sequencia_acertos'] > 5:
                dados['sequencia_acertos'] = 0
            if dados['sequencia_erros'] > 5:
                dados['sequencia_erros'] = 0
            
            # Calcular eficiência
            if dados['total'] > 0:
                dados['eficiencia'] = (dados['acertos'] / dados['total']) * 100
            
            return dados
        
        return None

    def processar_novo_numero(self, numero):
        """Processa novo número - VERSÃO CORRIGIDA"""
        try:
            if isinstance(numero, dict) and 'number' in numero:
                numero_real = numero['number']
            else:
                numero_real = numero
                
            self.contador_sorteios_global += 1
            
            # Processar resultado da previsão anterior
            if self.previsao_ativa:
                acerto = False
                zonas_acertadas = []
                nome_estrategia = self.previsao_ativa['nome']
                zonas_envolvidas = self.previsao_ativa.get('zonas_envolvidas', [])
                
                # Verificar acerto
                for zona in zonas_envolvidas:
                    numeros_zona = self.estrategia_zonas.numeros_zonas[zona]
                    if numero_real in numeros_zona:
                        acerto = True
                        zonas_acertadas.append(zona)
                
                # Atualizar sequências
                if acerto:
                    self.sequencia_acertos += 1
                    self.sequencia_erros = 0
                else:
                    self.sequencia_erros += 1
                    self.sequencia_acertos = 0
                
                # Limitar sequências
                if self.sequencia_acertos > 10:
                    self.sequencia_acertos = 0
                if self.sequencia_erros > 10:
                    self.sequencia_erros = 0
                
                # Atualizar contadores da estratégia
                if nome_estrategia not in self.estrategias_contador:
                    self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[nome_estrategia]['total'] += 1
                if acerto:
                    self.estrategias_contador[nome_estrategia]['acertos'] += 1
                    self.acertos += 1
                else:
                    self.erros += 1
                
                # Atualizar combinação
                self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
                
                # Otimização
                resultado_processado = {
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'zonas_envolvidas': zonas_envolvidas
                }
                
                try:
                    self.sistema_otimizacao.processar_resultado(resultado_processado)
                except:
                    pass
                
                # Notificação
                zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
                enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str)
                
                # Registrar histórico
                registro = {
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'zona_acertada': zona_acertada_str,
                    'zonas_envolvidas': zonas_envolvidas,
                    'sequencia_acertos': self.sequencia_acertos,
                    'sequencia_erros': self.sequencia_erros
                }
                
                self.historico_desempenho.append(registro)
                
                # Limitar histórico
                if len(self.historico_desempenho) > 200:
                    self.historico_desempenho = self.historico_desempenho[-100:]
                
                self.previsao_ativa = None
            
            # Adicionar número à estratégia
            self.estrategia_zonas.adicionar_numero(numero_real)
            
            # Gerar nova previsão
            if self.estrategia_selecionada == "Zonas":
                nova_estrategia = self.estrategia_zonas.analisar_zonas()
            else:
                nova_estrategia = None
            
            if nova_estrategia:
                self.previsao_ativa = nova_estrategia
                enviar_previsao_super_simplificada(nova_estrategia)
                
        except Exception as e:
            logging.error(f"Erro ao processar novo número: {e}")

    def zerar_estatisticas_desempenho(self):
        """Zera todas as estatísticas"""
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.sequencia_acertos = 0
        
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        # Zerar estratégia
        self.estrategia_zonas.historico.clear()
        
        # Reiniciar sistemas
        self.sistema_tendencias = SistemaTendencias()
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()
        
        logging.info("Estatísticas zeradas")
        salvar_sessao()

    def reset_recente_estatisticas(self):
        """Reseta estatísticas recentes"""
        if len(self.historico_desempenho) > 10:
            # Manter últimos 10
            self.historico_desempenho = self.historico_desempenho[-10:]
            
            # Recalcular
            self.acertos = sum(1 for r in self.historico_desempenho if r['acerto'])
            self.erros = len(self.historico_desempenho) - self.acertos
            
            # Recalcular contadores por estratégia
            self.estrategias_contador = {}
            for resultado in self.historico_desempenho:
                estrategia = resultado['estrategia']
                if estrategia not in self.estrategias_contador:
                    self.estrategias_contador[estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[estrategia]['total'] += 1
                if resultado['acerto']:
                    self.estrategias_contador[estrategia]['acertos'] += 1
            
            # Recalcular sequências
            self.sequencia_acertos = 0
            self.sequencia_erros = 0
            
            for resultado in reversed(self.historico_desempenho):
                if resultado['acerto']:
                    self.sequencia_acertos += 1
                else:
                    break
            
            for resultado in reversed(self.historico_desempenho):
                if not resultado['acerto']:
                    self.sequencia_erros += 1
                else:
                    break
            
            logging.info("Estatísticas recentes resetadas")
        
        salvar_sessao()

    def get_status_rotacao(self):
        """Status da rotação"""
        return {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'proxima_rotacao_erros': max(0, 2 - self.sequencia_erros),
            'proxima_rotacao_acertos': max(0, 3 - self.sequencia_acertos)
        }

# =============================
# FUNÇÕES DA API
# =============================
def fetch_latest_result():
    """Busca o último resultado da API"""
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado da API: {e}")
        return None

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    """Salva histórico em arquivo JSON"""
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="IA Roleta — Sistema Multi-Estratégias", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias")

# Inicializar configurações
inicializar_config_alertas()

# Carregar ou criar sessão
sessao_carregada = False
if os.path.exists(SESSION_DATA_PATH):
    try:
        sessao_carregada = carregar_sessao()
        if sessao_carregada:
            st.toast("✅ Sessão carregada", icon="✅")
    except:
        sessao_carregada = False

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaCompleto()

if "historico" not in st.session_state:
    st.session_state.historico = []

if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = ""

# Sidebar
st.sidebar.title("⚙️ Configurações")

# Gerenciamento de Sessão
with st.sidebar.expander("💾 Gerenciamento de Sessão"):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Salvar", use_container_width=True):
            if salvar_sessao():
                st.success("Sessão salva!")
            else:
                st.error("Erro ao salvar")
    with col2:
        if st.button("🔄 Carregar", use_container_width=True):
            if carregar_sessao():
                st.success("Sessão carregada!")
                st.rerun()
            else:
                st.error("Nenhuma sessão salva")
    
    st.write("---")
    
    col3, col4 = st.columns(2)
    with col3:
        if st.button("🔄 Reset Recente", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("Estatísticas recentes resetadas!")
            st.rerun()
    with col4:
        if st.button("🗑️ Zerar Tudo", use_container_width=True, type="secondary"):
            if st.checkbox("Confirmar"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.success("Todas as estatísticas zeradas!")
                st.rerun()

# Configurações de Alertas
with st.sidebar.expander("🔔 Configuração de Alertas"):
    alertas_config = st.session_state.get('alertas_config', {})
    
    alertas_previsao = st.checkbox("🎯 Previsões", value=alertas_config.get('alertas_previsao', True))
    alertas_resultado = st.checkbox("📊 Resultados", value=alertas_config.get('alertas_resultado', True))
    alertas_acertos = st.checkbox("✅ Acertos", value=alertas_config.get('alertas_acertos', True))
    alertas_erros = st.checkbox("❌ Erros", value=alertas_config.get('alertas_erros', True))
    
    if st.button("Salvar Configurações"):
        st.session_state.alertas_config = {
            'alertas_previsao': alertas_previsao,
            'alertas_resultado': alertas_resultado,
            'alertas_rotacao': True,
            'alertas_tendencia': False,
            'alertas_treinamento': False,
            'alertas_erros': alertas_erros,
            'alertas_acertos': alertas_acertos,
            'alertas_estatisticos': False
        }
        salvar_sessao()
        st.success("Configurações salvas!")

# Telegram
with st.sidebar.expander("📱 Telegram"):
    telegram_token = st.text_input("Bot Token:", value=st.session_state.telegram_token, type="password")
    telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    
    if st.button("Salvar Telegram"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("Configurações do Telegram salvas!")

# Seleção de Estratégia
estrategia = st.sidebar.selectbox(
    "🎯 Estratégia:",
    ["Zonas"],
    key="estrategia_selecionada"
)

if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)
    st.toast(f"Estratégia alterada para: {estrategia}")

# Status da Rotação
with st.sidebar.expander("🔄 Status da Rotação"):
    status = st.session_state.sistema.get_status_rotacao()
    st.write(f"**Estratégia:** {status['estrategia_atual']}")
    st.write(f"**Acertos seguidos:** {status['sequencia_acertos']}")
    st.write(f"**Erros seguidos:** {status['sequencia_erros']}")
    st.write(f"**Próxima rotação:** {status['proxima_rotacao_erros']} erros ou {status['proxima_rotacao_acertos']} acertos")

# Interface Principal
st.subheader("🔁 Últimos Números")

# Verificar API e processar resultados
resultado_api = fetch_latest_result()
if resultado_api and resultado_api.get("number") is not None:
    # Verificar se é um novo resultado
    ultimo_historico = st.session_state.historico[-1] if st.session_state.historico else None
    novo_numero = (
        not ultimo_historico or 
        (isinstance(ultimo_historico, dict) and ultimo_historico.get('number') != resultado_api['number']) or
        (not isinstance(ultimo_historico, dict) and ultimo_historico != resultado_api['number'])
    )
    
    if novo_numero:
        st.session_state.historico.append(resultado_api)
        st.session_state.sistema.processar_novo_numero(resultado_api)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

# Mostrar últimos números
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(f"`{numeros_str}`")
else:
    st.write("Nenhum número registrado")

# Métricas
st.subheader("📈 Desempenho")
sistema = st.session_state.sistema

total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🟢 Acertos", sistema.acertos)
with col2:
    st.metric("🔴 Erros", sistema.erros)
with col3:
    st.metric("📊 Total", total)
with col4:
    st.metric("✅ Taxa", f"{taxa:.1f}%")

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if previsao.get('selecao_inteligente', False):
        st.info("🎯 Seleção Inteligente Ativa")
    
    zonas_envolvidas = previsao.get('zonas_envolvidas', [])
    if len(zonas_envolvidas) > 1:
        zona1 = zonas_envolvidas[0]
        zona2 = zonas_envolvidas[1]
        
        nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
        nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
        
        st.write(f"**Núcleos:** {nucleo1} + {nucleo2}")
        
        # Mostrar estatísticas da combinação
        combinacao = tuple(sorted([zona1, zona2]))
        dados = sistema.historico_combinacoes.get(combinacao, {})
        if dados:
            eff = dados.get('eficiencia', 0)
            total_combo = dados.get('total', 0)
            st.info(f"**Estatísticas:** {eff:.1f}% ({dados.get('acertos', 0)}/{total_combo})")
    
    st.write(f"**Números ({len(previsao['numeros_apostar'])}):**")
    st.write(f"`{', '.join(map(str, sorted(previsao['numeros_apostar'])))}`")
    
    st.info("⏳ Aguardando próximo sorteio...")
else:
    st.info("🎲 Analisando padrões...")

# Performance por Estratégia
if sistema.estrategias_contador:
    st.subheader("📊 Performance por Estratégia")
    for nome, dados in sistema.estrategias_contador.items():
        if isinstance(dados, dict) and dados['total'] > 0:
            taxa_estrategia = (dados['acertos'] / dados['total'] * 100)
            st.write(f"**{nome}:** {dados['acertos']}/{dados['total']} ({taxa_estrategia:.1f}%)")

# Últimos Resultados
if sistema.historico_desempenho:
    st.subheader("🔍 Últimas 5 Conferências")
    for i, resultado in enumerate(sistema.historico_desempenho[-5:]):
        emoji = "✅" if resultado['acerto'] else "❌"
        st.write(f"{emoji} **{resultado['estrategia']}:** Número {resultado['numero']}")

# Entrada Manual
st.subheader("✍️ Inserir Sorteios Manualmente")
entrada = st.text_input("Digite números (0-36) separados por espaço:")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(n)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# Atualização Automática
st_autorefresh(interval=3000, key="refresh")

# Salvar sessão ao final
salvar_sessao()
