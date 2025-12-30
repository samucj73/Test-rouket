
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
# SISTEMA DE VALIDAÇÃO ESTATÍSTICA
# =============================
class SistemaValidacaoEstatistica:
    def __init__(self):
        self.testes_realizados = 0
        self.falsos_positivos = 0
        self.verdadeiros_positivos = 0
        self.confianca_minima = 0.95  # 95% de confiança
        
    def teste_binomial_90porcento(self, acertos, tentativas):
        """
        Teste estatístico para 90% de acerto
        """
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
# SISTEMA DE APRENDIZADO POR REFORÇO
# =============================
class SistemaAprendizadoReforco:
    def __init__(self):
        self.historico_aprendizado = deque(maxlen=1000)
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
                        'sequencia_atual_acertos': 0,
                        'sequencia_atual_erros': 0
                    }
                
                dados = self.melhores_combinacoes[combinacao]
                dados['tentativas'] += 1
                
                if acerto:
                    dados['acertos'] += 1
                    dados['sequencia_atual_acertos'] += 1
                    dados['sequencia_atual_erros'] = 0
                else:
                    dados['sequencia_atual_erros'] += 1
                    dados['sequencia_atual_acertos'] = 0
                
                if dados['tentativas'] > 0:
                    dados['eficiencia'] = (dados['acertos'] / dados['tentativas']) * 100
                    
                    if dados['tentativas'] >= 10 and dados['eficiencia'] < 20:
                        self.piores_combinacoes[combinacao] = dados.copy()
                        
            registro = {
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
            if dados['tentativas'] >= 5 and dados['eficiencia'] >= 50:
                combinacoes_validadas.append({
                    'combinacao': combinacao,
                    'eficiencia': dados['eficiencia'],
                    'tentativas': dados['tentativas'],
                    'sequencia_acertos': dados['sequencia_atual_acertos']
                })
        
        if combinacoes_validadas:
            combinacoes_validadas.sort(key=lambda x: x['eficiencia'], reverse=True)
            melhor = combinacoes_validadas[0]
            recomendacoes['melhor_combinacao'] = melhor['combinacao']
        
        for combinacao, dados in self.piores_combinacoes.items():
            if dados.get('tentativas', 0) >= 5 and dados.get('eficiencia', 0) < 30:
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
        
    def processar_resultado(self, resultado):
        recomendacoes = self.aprendizado.analisar_resultado(resultado)
        self.ultima_recomendacao = recomendacoes
        self.contador_otimizacoes += 1
        return recomendacoes

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

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        if 'sistema' not in st.session_state:
            logging.warning("❌ Sistema não está na sessão")
            return False
            
        sistema = st.session_state.sistema
        
        # CORREÇÃO: Limpar dados inconsistentes antes de salvar
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'alertas_config': st.session_state.get('alertas_config', {
                'alertas_previsao': True,
                'alertas_resultado': True,
                'alertas_rotacao': True,
                'alertas_tendencia': True,
                'alertas_treinamento': True,
                'alertas_erros': True,
                'alertas_acertos': True,
                'alertas_estatisticos': True
            }),
            'sistema_acertos': sistema.acertos,
            'sistema_erros': sistema.erros,
            'sistema_estrategias_contador': sistema.estrategias_contador,
            'sistema_historico_desempenho': sistema.historico_desempenho[-100:] if len(sistema.historico_desempenho) > 0 else [],  # LIMITAR
            'sistema_contador_sorteios_global': sistema.contador_sorteios_global,
            'sistema_sequencia_erros': sistema.sequencia_erros,
            'sistema_ultima_estrategia_erro': sistema.ultima_estrategia_erro,
            'sistema_sequencia_acertos': sistema.sequencia_acertos,
            'sistema_ultima_combinacao_acerto': sistema.ultima_combinacao_acerto,
            'sistema_historico_combinacoes_acerto': sistema.historico_combinacoes_acerto[-50:] if len(sistema.historico_combinacoes_acerto) > 0 else [],  # LIMITAR
            'estrategia_selecionada': sistema.estrategia_selecionada,
            'sistema_historico_combinacoes': {},
            'sistema_combinacoes_quentes': [],
            'sistema_combinacoes_frias': [],
        }
        
        # CORREÇÃO: Limitar e validar dados de combinações
        for combo, dados in sistema.historico_combinacoes.items():
            # Verificar consistência dos dados
            if isinstance(dados, dict) and 'total' in dados:
                if dados['total'] > 0 and dados['total'] >= dados.get('acertos', 0):
                    # Garantir que eficiencia seja calculada corretamente
                    dados['eficiencia'] = (dados['acertos'] / dados['total']) * 100 if dados['total'] > 0 else 0
                    # Limitar sequências a valores realistas
                    if dados.get('sequencia_acertos', 0) > 10:
                        dados['sequencia_acertos'] = 0
                    if dados.get('sequencia_erros', 0) > 10:
                        dados['sequencia_erros'] = 0
                    session_data['sistema_historico_combinacoes'][combo] = dados
        
        # Limitar combinações quentes/frias
        session_data['sistema_combinacoes_quentes'] = sistema.combinacoes_quentes[:10]
        session_data['sistema_combinacoes_frias'] = sistema.combinacoes_frias[:10]
        
        # CORREÇÃO: Não salvar dados de otimização se houver problemas
        try:
            if hasattr(sistema, 'sistema_otimizacao'):
                # Apenas salvar contadores básicos
                session_data['opt_contador_otimizacoes'] = sistema.sistema_otimizacao.contador_otimizacoes
        except:
            pass
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        logging.info(f"✅ Sessão salva com {len(session_data)} itens")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}", exc_info=True)
        return False

def carregar_sessao():
    """Carrega todos os dados da sessão do arquivo"""
    try:
        if not os.path.exists(SESSION_DATA_PATH):
            logging.info("ℹ️  Nenhuma sessão salva encontrada")
            return False
            
        with open(SESSION_DATA_PATH, 'rb') as f:
            session_data = pickle.load(f)
        
        if not isinstance(session_data, dict):
            logging.error("❌ Dados de sessão corrompidos")
            return False
            
        # CORREÇÃO: Inicializar config de alertas primeiro
        inicializar_config_alertas()
        
        # Carregar dados básicos
        st.session_state.historico = session_data.get('historico', [])
        st.session_state.telegram_token = session_data.get('telegram_token', '')
        st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
        
        # CORREÇÃO: Garantir configurações de alertas
        if 'alertas_config' in session_data:
            st.session_state.alertas_config = session_data['alertas_config']
        
        if 'sistema' not in st.session_state:
            st.session_state.sistema = SistemaRoletaCompleto()
            
        sistema = st.session_state.sistema
        
        # CORREÇÃO: Carregar dados do sistema com validação
        sistema.acertos = int(session_data.get('sistema_acertos', 0))
        sistema.erros = int(session_data.get('sistema_erros', 0))
        
        # Validar consistência dos contadores
        if sistema.acertos + sistema.erros > 10000:  # Limite realista
            sistema.acertos = min(sistema.acertos, 5000)
            sistema.erros = min(sistema.erros, 5000)
        
        sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
        sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
        sistema.contador_sorteios_global = int(session_data.get('sistema_contador_sorteios_global', 0))
        
        # CORREÇÃO: Resetar sequências se estiverem infladas
        sistema.sequencia_erros = int(session_data.get('sistema_sequencia_erros', 0))
        sistema.sequencia_acertos = int(session_data.get('sistema_sequencia_acertos', 0))
        
        if sistema.sequencia_erros > 10:
            sistema.sequencia_erros = 0
        if sistema.sequencia_acertos > 10:
            sistema.sequencia_acertos = 0
            
        sistema.ultima_estrategia_erro = session_data.get('sistema_ultima_estrategia_erro', '')
        sistema.ultima_combinacao_acerto = session_data.get('sistema_ultima_combinacao_acerto', [])
        sistema.historico_combinacoes_acerto = session_data.get('sistema_historico_combinacoes_acerto', [])
        sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Zonas')
        
        # CORREÇÃO: Carregar combinações com validação
        sistema.historico_combinacoes = {}
        for combo, dados in session_data.get('sistema_historico_combinacoes', {}).items():
            if isinstance(dados, dict) and 'total' in dados:
                # Validar dados da combinação
                if dados['total'] >= dados.get('acertos', 0) and dados['total'] < 10000:  # Limite realista
                    sistema.historico_combinacoes[combo] = dados
        
        sistema.combinacoes_quentes = session_data.get('sistema_combinacoes_quentes', [])
        sistema.combinacoes_frias = session_data.get('sistema_combinacoes_frias', [])
        
        # CORREÇÃO: Reinicializar sistema de otimização se houver problemas
        if hasattr(sistema, 'sistema_otimizacao'):
            try:
                sistema.sistema_otimizacao = SistemaOtimizacaoDinamica()
                sistema.contador_otimizacoes_aplicadas = 0
            except:
                pass
        
        logging.info(f"✅ Sessão carregada: {sistema.acertos} acertos, {sistema.erros} erros")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}", exc_info=True)
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
        
        st.toast(f"🎯 PREVISÃO CONFIRMADA", icon="🔥")
        
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    try:
        if acerto:
            st.toast("🎲 Resultado", icon="✅")
            st.success(f"✅ Acerto: {numero_real}")
        else:
            st.toast("🎲 Resultado", icon="❌")
            st.error(f"❌ Erro: {numero_real}")
        
        salvar_sessao()
        
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova):
    try:
        mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(mensagem)
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

# =============================
# SISTEMA DE DETECÇÃO DE TENDÊNCIAS
# =============================
class SistemaTendencias:
    def __init__(self):
        self.historico_tendencias = deque(maxlen=50)
        self.tendencia_ativa = None
        self.estado_tendencia = "aguardando"
        self.contador_confirmacoes = 0
        self.contador_erros_tendencia = 0
        self.contador_acertos_tendencia = 0
        self.ultima_zona_dominante = None
        self.historico_zonas_dominantes = deque(maxlen=10)
        self.rodadas_operando = 0
        
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
            
            elif self.estado_tendencia == "formando":
                if acerto_ultima and zona_acertada == self.tendencia_ativa:
                    self.contador_confirmacoes += 1
                    if self.contador_confirmacoes >= 2:
                        self.estado_tendencia = "ativa"
                        return {
                            'estado': 'ativa',
                            'zona_dominante': self.tendencia_ativa,
                            'confianca': 0.8,
                            'acao': 'operar',
                            'mensagem': f'Tendência confirmada - Operar {self.tendencia_ativa}'
                        }
            
            elif self.estado_tendencia == "ativa":
                self.rodadas_operando += 1
                if self.rodadas_operando >= 4:
                    self.estado_tendencia = "enfraquecendo"
                    return {
                        'estado': 'enfraquecendo',
                        'zona_dominante': self.tendencia_ativa,
                        'confianca': 0.3,
                        'acao': 'aguardar',
                        'mensagem': f'Tendência enfraquecendo - Máximo de operações'
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
            score_total = 0
            
            if len(historico) < 3:
                return 0.5
            
            # Frequência recente
            historico_lista = list(historico)
            ultimos_10 = historico_lista[-10:] if len(historico_lista) >= 10 else historico_lista
            freq_recente = sum(1 for n in ultimos_10 if n == numero) / len(ultimos_10) if ultimos_10 else 0
            score_total += freq_recente * 0.5
            
            # Posição na roda
            posicao = self.roleta.get_posicao_race(numero)
            if posicao != -1 and len(historico_lista) >= 2:
                ultimo = historico_lista[-1]
                pos_ultimo = self.roleta.get_posicao_race(ultimo)
                if pos_ultimo != -1:
                    distancia = min(abs(posicao - pos_ultimo), 37 - abs(posicao - pos_ultimo))
                    score_total += (1 - distancia / 18) * 0.3
            
            # Vizinhos recentes
            vizinhos = self.roleta.get_vizinhos_fisicos(numero, raio=2)
            count_vizinhos = sum(1 for n in ultimos_10 if n in vizinhos)
            score_total += (count_vizinhos / len(ultimos_10)) * 0.2 if ultimos_10 else 0
            
            return min(score_total, 1.0)
            
        except Exception as e:
            logging.error(f"Erro ao calcular score: {e}")
            return 0.5

# =============================
# CLASSE PRINCIPAL DA ROLETA
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
# ESTRATÉGIA DAS ZONAS
# =============================
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Zonas Ultra Otimizada v6"
        
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
        
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        
        if len(zonas_rankeadas) >= 2:
            zona1, score1 = zonas_rankeadas[0]
            zona2, score2 = zonas_rankeadas[1]
            
            numeros_combinados = list(set(self.numeros_zonas[zona1] + self.numeros_zonas[zona2]))
            
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
# SISTEMA DE GESTÃO PRINCIPAL
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.estrategia_midas = None
        self.estrategia_ml = None
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
        self.contador_otimizacoes_aplicadas = 0

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def atualizar_desempenho_combinacao(self, zonas_envolvidas, acerto):
        """Atualiza desempenho de combinações - VERSÃO CORRIGIDA"""
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
            
            # CORREÇÃO: Garantir que acertos não excedam total
            if acerto:
                dados['acertos'] += 1
                dados['sequencia_acertos'] += 1
                dados['sequencia_erros'] = 0
            else:
                dados['sequencia_erros'] += 1
                dados['sequencia_acertos'] = 0
            
            # CORREÇÃO: Calcular eficiência corretamente
            if dados['total'] > 0:
                dados['eficiencia'] = (dados['acertos'] / dados['total']) * 100
            
            # CORREÇÃO: Limitar sequências a valores realistas
            if dados['sequencia_acertos'] > 10:
                dados['sequencia_acertos'] = 0
            if dados['sequencia_erros'] > 10:
                dados['sequencia_erros'] = 0
            
            return dados
        
        return None

    def rotacionar_estrategia_automaticamente(self, acerto, nome_estrategia, zonas_envolvidas):
        """ROTAÇÃO AUTOMÁTICA CORRIGIDA - Lógica simplificada"""
        
        # Atualizar sequências globais CORRETAMENTE
        if acerto:
            self.sequencia_acertos += 1
            self.sequencia_erros = 0
        else:
            self.sequencia_erros += 1
            self.sequencia_acertos = 0
        
        # CORREÇÃO: Limitar sequências a valores realistas
        if self.sequencia_acertos > 10:
            self.sequencia_acertos = 0
        if self.sequencia_erros > 10:
            self.sequencia_erros = 0
        
        # Atualizar desempenho da combinação
        if len(zonas_envolvidas) > 1:
            self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
        
        # REGRA: ROTAÇÃO POR 2 ERROS SEGUIDOS
        if not acerto and self.sequencia_erros >= 2:
            if self.estrategia_selecionada == "Zonas":
                self.estrategia_selecionada = "ML"
                self.sequencia_erros = 0
                self.sequencia_acertos = 0
                enviar_rotacao_automatica("Zonas", "ML")
                return True
        
        return False

    def processar_novo_numero(self, numero):
        try:
            if isinstance(numero, dict) and 'number' in numero:
                numero_real = numero['number']
            else:
                numero_real = numero
                
            self.contador_sorteios_global += 1
            
            # CORREÇÃO: Processar resultado da previsão anterior
            if self.previsao_ativa:
                acerto = False
                zonas_acertadas = []
                nome_estrategia = self.previsao_ativa['nome']
                zonas_envolvidas = self.previsao_ativa.get('zonas_envolvidas', [])
                
                # Verificar acerto
                for zona in zonas_envolvidas:
                    if 'Zonas' in nome_estrategia:
                        numeros_zona = self.estrategia_zonas.numeros_zonas[zona]
                        if numero_real in numeros_zona:
                            acerto = True
                            zonas_acertadas.append(zona)
                
                # CORREÇÃO: Atualizar contadores corretamente
                if nome_estrategia not in self.estrategias_contador:
                    self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[nome_estrategia]['total'] += 1
                if acerto:
                    self.estrategias_contador[nome_estrategia]['acertos'] += 1
                    self.acertos += 1
                else:
                    self.erros += 1
                
                # CORREÇÃO: Criar resultado para otimização
                resultado_processado = {
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'zonas_envolvidas': zonas_envolvidas
                }
                
                # Processar com otimização
                try:
                    self.sistema_otimizacao.processar_resultado(resultado_processado)
                except:
                    pass
                
                # Tentar rotação automática
                rotacionou = self.rotacionar_estrategia_automaticamente(acerto, nome_estrategia, zonas_envolvidas)
                
                # Enviar notificação
                zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
                enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str)
                
                # CORREÇÃO: Registrar no histórico limitado
                registro = {
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'rotacionou': rotacionou,
                    'zona_acertada': zona_acertada_str,
                    'zonas_envolvidas': zonas_envolvidas,
                    'sequencia_acertos': self.sequencia_acertos,
                    'sequencia_erros': self.sequencia_erros
                }
                
                self.historico_desempenho.append(registro)
                
                # CORREÇÃO: Limitar histórico de desempenho
                if len(self.historico_desempenho) > 1000:
                    self.historico_desempenho = self.historico_desempenho[-1000:]
                
                self.previsao_ativa = None
            
            # Adicionar número às estratégias
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
        """Zera todas as estatísticas - VERSÃO CORRIGIDA"""
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
        
        self.sistema_tendencias = SistemaTendencias()
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()
        self.contador_otimizacoes_aplicadas = 0
        
        # Zerar histórico da estratégia de zonas
        self.estrategia_zonas.historico.clear()
        
        logging.info("📊 Todas as estatísticas de desempenho foram zeradas")
        salvar_sessao()

    def reset_recente_estatisticas(self):
        """Reset apenas estatísticas recentes - VERSÃO CORRIGIDA"""
        if len(self.historico_desempenho) > 10:
            # Manter apenas últimos 10 resultados
            self.historico_desempenho = self.historico_desempenho[-10:]
            
            # Recalcular contadores baseado nos últimos 10
            self.acertos = sum(1 for resultado in self.historico_desempenho if resultado['acerto'])
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
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            
            # Verificar sequência de erros
            for resultado in reversed(self.historico_desempenho):
                if not resultado['acerto']:
                    self.sequencia_erros += 1
                else:
                    break
            
            # Verificar sequência de acertos
            for resultado in reversed(self.historico_desempenho):
                if resultado['acerto']:
                    self.sequencia_acertos += 1
                else:
                    break
            
            logging.info("🔄 Estatísticas recentes resetadas (mantidos últimos 10 resultados)")
        else:
            logging.info("ℹ️  Histórico muito pequeno para reset recente")
        
        salvar_sessao()

    def get_status_rotacao(self):
        """Status da rotação - VERSÃO CORRIGIDA"""
        status = {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'proxima_rotacao_erros': max(0, 2 - self.sequencia_erros),
            'proxima_rotacao_acertos': max(0, 3 - self.sequencia_acertos),
            'combinacoes_quentes': len(self.combinacoes_quentes),
            'combinacoes_frias': len(self.combinacoes_frias)
        }
        
        return status

# =============================
# APLICAÇÃO STREAMLIT PRINCIPAL
# =============================
st.set_page_config(page_title="IA Roleta — Multi-Estratégias", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias com Aprendizado por Reforço")

# Inicializar config de alertas
inicializar_config_alertas()

# Tentar carregar sessão salva
sessao_carregada = False
if os.path.exists(SESSION_DATA_PATH):
    try:
        sessao_carregada = carregar_sessao()
        if sessao_carregada:
            st.toast("✅ Sessão carregada com sucesso", icon="✅")
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
        sessao_carregada = False

# Inicializar sistema se necessário
if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaCompleto()

if "historico" not in st.session_state:
    st.session_state.historico = []

# Sidebar - Configurações Avançadas
st.sidebar.title("⚙️ Configurações")

# Gerenciamento de Sessão
with st.sidebar.expander("💾 Gerenciamento de Sessão", expanded=False):
    st.write("**Persistência de Dados**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salvar Sessão", use_container_width=True):
            salvar_sessao()
            st.success("✅ Sessão salva!")
            
    with col2:
        if st.button("🔄 Carregar Sessão", use_container_width=True):
            if carregar_sessao():
                st.success("✅ Sessão carregada!")
                st.rerun()
            else:
                st.error("❌ Nenhuma sessão salva encontrada")
    
    st.write("---")
    
    st.write("**📊 Gerenciar Estatísticas**")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Estatísticas recentes resetadas!")
            st.rerun()
            
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
            if st.checkbox("Confirmar zerar TODAS as estatísticas"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.success("🗑️ Todas as estatísticas foram zeradas!")
                st.rerun()

# Configurações dos Alertas
with st.sidebar.expander("🔔 Configuração de Alertas", expanded=False):
    alertas_config = st.session_state.get('alertas_config', {
        'alertas_previsao': True,
        'alertas_resultado': True,
        'alertas_rotacao': True,
        'alertas_tendencia': True,
        'alertas_treinamento': True,
        'alertas_erros': True,
        'alertas_acertos': True,
        'alertas_estatisticos': True
    })
    
    alertas_previsao = st.checkbox("🎯 Previsões", value=alertas_config.get('alertas_previsao', True))
    alertas_resultado = st.checkbox("📊 Resultados", value=alertas_config.get('alertas_resultado', True))
    alertas_rotacao = st.checkbox("🔄 Rotações", value=alertas_config.get('alertas_rotacao', True))
    alertas_acertos = st.checkbox("✅ Acertos", value=alertas_config.get('alertas_acertos', True))
    alertas_erros = st.checkbox("❌ Erros", value=alertas_config.get('alertas_erros', True))
    
    if st.button("💾 Salvar Configurações", use_container_width=True):
        st.session_state.alertas_config = {
            'alertas_previsao': alertas_previsao,
            'alertas_resultado': alertas_resultado,
            'alertas_rotacao': alertas_rotacao,
            'alertas_tendencia': False,
            'alertas_treinamento': False,
            'alertas_erros': alertas_erros,
            'alertas_acertos': alertas_acertos,
            'alertas_estatisticos': False
        }
        salvar_sessao()
        st.success("✅ Configurações de alertas salvas!")

# Seleção de Estratégia
estrategia = st.sidebar.selectbox(
    "🎯 Selecione a Estratégia:",
    ["Zonas"],
    key="estrategia_selecionada"
)

if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)

# Status da Rotação Automática
with st.sidebar.expander("🔄 Rotação Automática", expanded=True):
    status_rotacao = st.session_state.sistema.get_status_rotacao()
    
    st.write("**Sistema de Rotação:**")
    st.write(f"🎯 **Estratégia Atual:** {status_rotacao['estrategia_atual']}")
    st.write(f"✅ **Acertos Seguidos:** {status_rotacao['sequencia_acertos']}/3")
    st.write(f"❌ **Erros Seguidos:** {status_rotacao['sequencia_erros']}/2")
    st.write(f"🎯 **Próxima Rotação:** {status_rotacao['proxima_rotacao_erros']} erros ou {status_rotacao['proxima_rotacao_acertos']} acertos")

# Interface principal
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(numeros_str)
else:
    st.write("Nenhum número registrado")

# Status da Rotação na Interface Principal
status_rotacao = st.session_state.sistema.get_status_rotacao()
col_status1, col_status2, col_status3 = st.columns(3)
with col_status1:
    st.metric("🎯 Estratégia Atual", status_rotacao['estrategia_atual'])
with col_status2:
    st.metric("✅ Acertos Seguidos", f"{status_rotacao['sequencia_acertos']}/3")
with col_status3:
    st.metric("❌ Erros Seguidos", f"{status_rotacao['sequencia_erros']}/2")

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    zonas_envolvidas = previsao.get('zonas_envolvidas', [])
    if len(zonas_envolvidas) > 1:
        zona1 = zonas_envolvidas[0]
        zona2 = zonas_envolvidas[1]
        
        nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
        nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
        
        st.write(f"**📍 Núcleos Combinados:** {nucleo1} + {nucleo2}")
        
        # Mostrar eficiência da combinação
        combinacao = tuple(sorted([zona1, zona2]))
        dados_combinacao = sistema.historico_combinacoes.get(combinacao, {})
        if dados_combinacao:
            eff = dados_combinacao.get('eficiencia', 0)
            total = dados_combinacao.get('total', 0)
            st.info(f"📊 **Estatísticas:** {eff:.1f}% ({dados_combinacao.get('acertos', 0)}/{total})")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    st.write(", ".join(map(str, sorted(previsao['numeros_apostar']))))
    
    st.info("⏳ Aguardando próximo sorteio para conferência...")
else:
    st.info(f"🎲 Analisando padrões ({estrategia})...")

# Desempenho
st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
if total > 0:
    taxa = (sistema.acertos / total * 100)
else:
    taxa = 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

# Botões de gerenciamento de estatísticas
st.write("**Gerenciar Estatísticas:**")
col5, col6 = st.columns(2)

with col5:
    if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
        st.session_state.sistema.reset_recente_estatisticas()
        st.success("✅ Estatísticas recentes resetadas!")
        st.rerun()

with col6:
    if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
        if st.checkbox("Confirmar zerar TODAS as estatísticas"):
            st.session_state.sistema.zerar_estatisticas_desempenho()
            st.success("🗑️ Todas as estatísticas foram zeradas!")
            st.rerun()

# Análise detalhada por estratégia
if sistema.estrategias_contador:
    st.write("**📊 Performance por Estratégia:**")
    for nome, dados in sistema.estrategias_contador.items():
        if isinstance(dados, dict) and 'total' in dados and dados['total'] > 0:
            taxa_estrategia = (dados['acertos'] / dados['total'] * 100)
            cor = "🟢" if taxa_estrategia >= 50 else "🟡" if taxa_estrategia >= 30 else "🔴"
            st.write(f"{cor} {nome}: {dados['acertos']}/{dados['total']} ({taxa_estrategia:.1f}%)")

# Últimas conferências
if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for i, resultado in enumerate(sistema.historico_desempenho[-5:]):
        emoji = "🎉" if resultado['acerto'] else "❌"
        rotacao_emoji = " 🔄" if resultado.get('rotacionou', False) else ""
        zona_info = ""
        if resultado['acerto'] and resultado.get('zona_acertada'):
            zonas = resultado['zona_acertada'].split('+')
            nucleos = []
            for zona in zonas:
                if zona == 'Vermelha':
                    nucleos.append("7")
                elif zona == 'Azul':
                    nucleos.append("10")
                elif zona == 'Amarela':
                    nucleos.append("2")
                else:
                    nucleos.append(zona)
            zona_info = f" (Núcleos {'+'.join(nucleos)})"
                
        st.write(f"{emoji}{rotacao_emoji} {resultado['estrategia']}: Número {resultado['numero']}{zona_info}")

# Entrada manual
st.subheader("✍️ Inserir Sorteios")
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

# Atualização automática
st_autorefresh(interval=3000, key="refresh")

# Salvar sessão
salvar_sessao()
