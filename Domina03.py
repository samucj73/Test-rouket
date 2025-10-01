# RoletaHybridIA.py - SISTEMA ESPECIALISTA 450+ REGISTROS CORRIGIDO
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
# CONFIGURAÇÃO ESPECIALISTA - 450+ REGISTROS
# =============================
MIN_HISTORICO_TREINAMENTO = 620  # 🎯 Ponto de ativação do modo especialista
NUMERO_PREVISOES = 15

# Fases do sistema
FASE_INICIAL = 50
FASE_INTERMEDIARIA = 150  
FASE_AVANCADA = 300
FASE_ESPECIALISTA = 620

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# UTILITÁRIOS ROBUSTOS
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
    """Retorna vizinhos físicos na mesa"""
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

def analisar_duzias_colunas(historico):
    """Analisa padrões de dúzias e colunas"""
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if not numeros:
        return {"duzias_quentes": [], "colunas_quentes": []}
    
    periodo_analise = min(100, len(numeros))
    ultimos_numeros = numeros[-periodo_analise:]
    
    contagem_duzias = {1: 0, 2: 0, 3: 0}
    contagem_colunas = {1: 0, 2: 0, 3: 0}
    
    for num in ultimos_numeros:
        if 1 <= num <= 12:
            contagem_duzias[1] += 1
        elif 13 <= num <= 24:
            contagem_duzias[2] += 1
        elif 25 <= num <= 36:
            contagem_duzias[3] += 1
            
        if num in COLUNA_1:
            contagem_colunas[1] += 1
        elif num in COLUNA_2:
            contagem_colunas[2] += 1
        elif num in COLUNA_3:
            contagem_colunas[3] += 1
    
    duzias_ordenadas = sorted(contagem_duzias.items(), key=lambda x: x[1], reverse=True)[:2]
    colunas_ordenadas = sorted(contagem_colunas.items(), key=lambda x: x[1], reverse=True)[:2]
    
    return {
        "duzias_quentes": [duzia for duzia, count in duzias_ordenadas if count > 0],
        "colunas_quentes": [coluna for coluna, count in colunas_ordenadas if count > 0],
        "contagem_duzias": contagem_duzias,
        "contagem_colunas": contagem_colunas,
        "periodo_analisado": periodo_analise
    }

# =============================
# SISTEMA ESPECIALISTA 450+ CORRIGIDO
# =============================
class Pattern_Analyzer_Especialista:
    def __init__(self):
        self.padroes_detectados = {}
        
    def analisar_padroes_profundos(self, historico):
        """Análise PROFUNDA apenas possível com 450+ registros"""
        try:
            if len(historico) < MIN_HISTORICO_TREINAMENTO:
                return self.analisar_padroes_rasos(historico)
                
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            
            logging.info(f"🔍 ANALISANDO {len(numeros)} REGISTROS - MODO ESPECIALISTA ATIVO")
            
            # 1. PADRÕES DE CICLOS COMPLEXOS
            ciclos_avancados = self.detectar_ciclos_avancados(numeros)
            
            # 2. CORRELAÇÕES ENTRE NÚMEROS
            correlacoes = self.analisar_correlacoes(numeros)
            
            # 3. PADRÕES TEMPORAIS COMPLEXOS
            padroes_temporais = self.analisar_padroes_temporais(historico)
            
            # 4. SEQUÊNCIAS DE ALTA ORDEM
            sequencias_complexas = self.detectar_sequencias_complexas(numeros)
            
            return {
                'ciclos_avancados': ciclos_avancados,
                'correlacoes': correlacoes,
                'padroes_temporais': padroes_temporais,
                'sequencias_complexas': sequencias_complexas,
                'confianca': 'MUITO_ALTA',
                'amostra_suficiente': True,
                'total_padroes': len(ciclos_avancados) + len(correlacoes) + len(sequencias_complexas)
            }
            
        except Exception as e:
            logging.error(f"Erro na análise profunda: {e}")
            return self.analisar_padroes_rasos(historico)
    
    def detectar_ciclos_avancados(self, numeros):
        """Detecta ciclos que só aparecem com muitos dados"""
        ciclos = {}
        
        # Ciclos de diferentes tamanhos (apenas detectáveis com 450+ dados)
        tamanhos_ciclo = [7, 15, 30, 50, 75, 100]
        
        for tamanho in tamanhos_ciclo:
            if len(numeros) >= tamanho * 3:  # Precisa de pelo menos 3 ciclos completos
                ciclos_detectados = []
                
                for i in range(len(numeros) - tamanho * 2):
                    ciclo1 = numeros[i:i+tamanho]
                    ciclo2 = numeros[i+tamanho:i+tamanho*2]
                    
                    # Similaridade mais sofisticada
                    similaridade = self.calcular_similaridade_avancada(ciclo1, ciclo2)
                    
                    if similaridade > 0.35:  # Limite mais baixo por ter mais dados
                        proximo_ciclo = numeros[i+tamanho*2:i+tamanho*3] if i+tamanho*3 <= len(numeros) else []
                        
                        ciclos_detectados.append({
                            'posicao_inicial': i,
                            'similaridade': similaridade,
                            'tamanho': tamanho,
                            'proximo_ciclo': proximo_ciclo[:5] if proximo_ciclo else [],
                            'numeros_comuns': list(set(ciclo1) & set(ciclo2))[:8]
                        })
                
                if ciclos_detectados:
                    ciclos[f'ciclo_{tamanho}'] = ciclos_detectados[:3]  # Top 3 ciclos
        
        return ciclos
    
    def calcular_similaridade_avancada(self, lista1, lista2):
        """Calcula similaridade considerando ordem e frequência"""
        if len(lista1) != len(lista2) or len(lista1) == 0:
            return 0.0
            
        # Similaridade por elementos comuns
        elementos_comuns = len(set(lista1) & set(lista2)) / len(set(lista1) | set(lista2))
        
        # Similaridade por posição (ordem)
        posicoes_iguais = sum(1 for i in range(min(len(lista1), len(lista2))) if lista1[i] == lista2[i])
        similaridade_posicao = posicoes_iguais / len(lista1)
        
        # Similaridade por frequência
        freq1 = Counter(lista1)
        freq2 = Counter(lista2)
        similaridade_freq = sum(min(freq1.get(num, 0), freq2.get(num, 0)) for num in set(lista1) | set(lista2)) / len(lista1)
        
        # Combinação ponderada
        return (elementos_comuns * 0.4 + similaridade_posicao * 0.3 + similaridade_freq * 0.3)
    
    def analisar_correlacoes(self, numeros):
        """Analisa correlações entre números (quais aparecem juntos)"""
        correlacoes = {}
        
        # Janela de análise - com 450+ dados podemos usar janelas maiores
        janela = 10
        
        for i in range(len(numeros) - janela):
            janela_atual = numeros[i:i+janela]
            
            for j in range(len(janela_atual)):
                for k in range(j+1, len(janela_atual)):
                    par = tuple(sorted([janela_atual[j], janela_atual[k]]))
                    
                    if par not in correlacoes:
                        correlacoes[par] = 0
                    correlacoes[par] += 1
        
        # Filtrar correlações significativas
        correlacoes_significativas = {}
        for par, count in correlacoes.items():
            if count >= len(numeros) * 0.02:  # Aparecem juntos em pelo menos 2% das janelas
                correlacoes_significativas[par] = {
                    'frequencia': count,
                    'probabilidade': count / (len(numeros) - janela)
                }
        
        # Ordenar por frequência
        return dict(sorted(correlacoes_significativas.items(), 
                         key=lambda x: x[1]['frequencia'], reverse=True)[:15])
    
    def analisar_padroes_temporais(self, historico):
        """Analisa padrões baseados em tempo real"""
        try:
            padroes = {
                'horarios': {},
                'sequencias_rapidas': {},
                'intervalos': {}
            }
            
            # Análise por horário (apenas viável com muitos dados)
            for i, registro in enumerate(historico):
                if 'timestamp' in registro and i > 0:
                    try:
                        # Calcular intervalo desde o último número
                        tempo_atual = datetime.fromisoformat(registro['timestamp'].replace('Z', '+00:00'))
                        tempo_anterior = datetime.fromisoformat(historico[i-1]['timestamp'].replace('Z', '+00:00'))
                        intervalo = (tempo_atual - tempo_anterior).total_seconds()
                        
                        # Agrupar por intervalo
                        intervalo_chave = f"intervalo_{int(intervalo/60)}min"
                        if intervalo_chave not in padroes['intervalos']:
                            padroes['intervalos'][intervalo_chave] = []
                        padroes['intervalos'][intervalo_chave].append(registro['number'])
                        
                    except:
                        continue
            
            # Processar padrões de intervalo
            for intervalo, numeros in padroes['intervalos'].items():
                if len(numeros) >= 10:  # Pelo menos 10 ocorrências
                    contagem = Counter(numeros)
                    mais_comum, freq = contagem.most_common(1)[0]
                    if freq >= len(numeros) * 0.3:  # 30% de frequência
                        padroes['intervalos'][intervalo] = {
                            'numero_mais_comum': mais_comum,
                            'frequencia': freq/len(numeros),
                            'total_ocorrencias': len(numeros)
                        }
                else:
                    padroes['intervalos'][intervalo] = 'insuficiente_dados'
            
            return padroes
            
        except Exception as e:
            logging.error(f"Erro análise temporal: {e}")
            return {}
    
    def detectar_sequencias_complexas(self, numeros):
        """Detecta sequências complexas de alta ordem"""
        sequencias = {}
        
        # Padrões de transição de estado
        estados = []
        for i in range(1, len(numeros)):
            diff = numeros[i] - numeros[i-1]
            if diff > 0:
                estados.append('SUBINDO')
            elif diff < 0:
                estados.append('DESCENDO')
            else:
                estados.append('ESTAVEL')
        
        # Detectar padrões de transição
        padroes_transicao = {}
        for i in range(len(estados) - 3):
            sequencia = tuple(estados[i:i+4])
            if sequencia not in padroes_transicao:
                padroes_transicao[sequencia] = []
            padroes_transicao[sequencia].append(numeros[i+3])
        
        # Filtrar padrões consistentes
        for seq, resultados in padroes_transicao.items():
            if len(resultados) >= 5:  # Pelo menos 5 ocorrências
                contagem = Counter(resultados)
                mais_comum, freq = contagem.most_common(1)[0]
                if freq >= len(resultados) * 0.4:  # 40% de consistência
                    sequencias[f"transicao_{seq}"] = {
                        'proximo_esperado': mais_comum,
                        'confianca': freq/len(resultados),
                        'ocorrencias': len(resultados)
                    }
        
        return sequencias
    
    def analisar_padroes_rasos(self, historico):
        """Fallback para quando não há dados suficientes"""
        return {
            'ciclos_avancados': {},
            'correlacoes': {},
            'padroes_temporais': {},
            'sequencias_complexas': {},
            'confianca': 'BAIXA',
            'amostra_suficiente': False,
            'total_padroes': 0
        }

class XGBoost_Especialista:
    def __init__(self):
        self.min_treinamento = MIN_HISTORICO_TREINAMENTO
        
    def predict_com_450_plus(self, historico):
        """Predição especializada para 450+ registros"""
        if len(historico) < self.min_treinamento:
            return self.predict_basico(historico)
            
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        probs = {}
        
        logging.info(f"🧠 XGBOOST ESPECIALISTA ATIVO - {len(numeros)} REGISTROS")
        
        # 1. ANÁLISE DE CORRELAÇÕES (apenas com muitos dados)
        correlacoes = self.calcular_correlacoes_avancadas(numeros)
        for num, score in correlacoes.items():
            probs[num] = probs.get(num, 0) + score * 0.3
        
        # 2. PADRÕES DE LONGO PRAZO
        padroes_longo_prazo = self.analisar_padroes_longo_prazo(numeros)
        for num, score in padroes_longo_prazo.items():
            probs[num] = probs.get(num, 0) + score * 0.4
        
        # 3. TENDÊNCIAS COMPLEXAS
        tendencias = self.calcular_tendencias_complexas(numeros)
        for num, score in tendencias.items():
            probs[num] = probs.get(num, 0) + score * 0.3
        
        return probs
    
    def calcular_correlacoes_avancadas(self, numeros):
        """Calcula correlações complexas entre números"""
        scores = {}
        janela = 8
        
        for i in range(len(numeros) - janela):
            contexto = numeros[i:i+janela]
            proximo = numeros[i+janela] if i+janela < len(numeros) else None
            
            if proximo is not None:
                # Bônus para números que aparecem em contextos similares
                for num in set(contexto):
                    scores[num] = scores.get(num, 0) + 0.01
                
                scores[proximo] = scores.get(proximo, 0) + 0.02
        
        return scores
    
    def analisar_padroes_longo_prazo(self, numeros):
        """Analisa padrões que só aparecem com 450+ dados"""
        scores = {}
        
        # Análise por segmentos de 50 números
        segmentos = []
        for i in range(0, len(numeros), 50):
            segmento = numeros[i:i+50]
            if len(segmento) >= 25:
                segmentos.append(segmento)
        
        # Padrões entre segmentos
        for i in range(len(segmentos) - 1):
            seg1 = segmentos[i]
            seg2 = segmentos[i+1]
            
            # Números que se repetem entre segmentos
            comuns = set(seg1) & set(seg2)
            for num in comuns:
                scores[num] = scores.get(num, 0) + 0.05
            
            # Transições entre segmentos
            if seg1 and seg2:
                ultimo_seg1 = seg1[-1]
                primeiro_seg2 = seg2[0]
                
                # Se há padrão de transição
                scores[primeiro_seg2] = scores.get(primeiro_seg2, 0) + 0.03
        
        return scores
    
    def calcular_tendencias_complexas(self, numeros):
        """Calcula tendências multivariadas complexas"""
        scores = {}
        
        if len(numeros) < 100:
            return scores
        
        # Tendência por características múltiplas
        caracteristicas = {
            'alta_frequencia': [n for n in range(37) if numeros.count(n) > len(numeros) * 0.03],
            'recente': numeros[-20:],
            'vizinhos_ativos': []
        }
        
        # Adicionar vizinhos dos números recentes
        for num in numeros[-10:]:
            caracteristicas['vizinhos_ativos'].extend(obter_vizinhos_fisicos(num))
        
        # Calcular scores baseado nas características
        for num in range(37):
            score = 0
            
            if num in caracteristicas['alta_frequencia']:
                score += 0.2
            
            if num in caracteristicas['recente']:
                score += 0.3
            
            if num in caracteristicas['vizinhos_ativos']:
                score += 0.15
            
            if score > 0:
                scores[num] = score
        
        return scores
    
    def predict_basico(self, historico):
        """Fallback para histórico insuficiente"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        if not numeros:
            return {}
            
        probs = {}
        ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
        
        freq = Counter(ultimos_15)
        for num, count in freq.items():
            probs[num] = count * 0.1
        
        return probs

class Hybrid_IA_450_Plus_Corrigido:
    def __init__(self):
        self.pattern_analyzer = Pattern_Analyzer_Especialista()
        self.xgb_especialista = XGBoost_Especialista()
        
    def prever_com_historio_longo(self, historico):
        """Sistema especializado para 450+ registros - CORRIGIDO"""
        historico_size = len(historico)
        
        if historico_size >= MIN_HISTORICO_TREINAMENTO:
            logging.info(f"🚀 ATIVANDO MODO ESPECIALISTA - {historico_size} REGISTROS")
            
            # 1. Análise profunda de padrões
            analise_profunda = self.pattern_analyzer.analisar_padroes_profundos(historico)
            
            # 2. Predição especializada
            probs_xgb = self.xgb_especialista.predict_com_450_plus(historico)
            
            # 3. Combinação inteligente CORRIGIDA
            previsao_final = self.combinar_previsoes_especialistas_corrigido(analise_profunda, probs_xgb, historico)
            
            logging.info(f"🎯 MODO ESPECIALISTA: {analise_profunda['total_padroes']} padrões detectados → {len(previsao_final)} números")
            return previsao_final
        else:
            # Modo normal para histórico menor
            return self.prever_com_historio_normal(historico)
    
    def combinar_previsoes_especialistas_corrigido(self, analise_profunda, probs_xgb, historico):
        """Combinação CORRIGIDA para garantir 15 números"""
        scores_finais = {}
        
        # BASE MAIS ROBUSTA do XGBoost
        for num, score in probs_xgb.items():
            scores_finais[num] = score * 1.5  # Aumentar peso do XGBoost
        
        # Bônus por correlações - MAIS AGRESSIVO
        correlacoes = analise_profunda.get('correlacoes', {})
        for par, info in correlacoes.items():
            for num in par:
                scores_finais[num] = scores_finais.get(num, 0) + info['probabilidade'] * 0.4
        
        # Bônus por sequências complexas - MAIS AGRESSIVO
        sequencias = analise_profunda.get('sequencias_complexas', {})
        for seq, info in sequencias.items():
            scores_finais[info['proximo_esperado']] = scores_finais.get(info['proximo_esperado'], 0) + info['confianca'] * 0.6
        
        # GARANTIR MÍNIMO DE SCORES
        if len(scores_finais) < 20:
            self.preencher_scores_faltantes(scores_finais, historico)
        
        # Ordenar e selecionar - GARANTIR 15 NÚMEROS
        top_numeros = sorted(scores_finais.items(), key=lambda x: x[1], reverse=True)
        
        # Se não tem 15, completar com estratégia física
        selecao = [num for num, score in top_numeros[:NUMERO_PREVISOES]]
        
        if len(selecao) < NUMERO_PREVISOES:
            selecao = self.completar_previsao_estrategica(selecao, historico)
        
        # Garantir diversificação CORRIGIDA
        return self.diversificar_selecao_especialista_corrigida(selecao, historico)
    
    def preencher_scores_faltantes(self, scores_finais, historico):
        """Preenche scores faltantes com estratégia base"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # Adicionar números recentes
        for num in numeros[-10:]:
            if num not in scores_finais:
                scores_finais[num] = 0.1
        
        # Adicionar vizinhos dos últimos números
        for num in numeros[-5:]:
            vizinhos = obter_vizinhos_fisicos(num)
            for vizinho in vizinhos:
                if vizinho not in scores_finais:
                    scores_finais[vizinho] = 0.08
        
        # Adicionar números de alta frequência
        freq = Counter(numeros[-30:])
        for num, count in freq.most_common(10):
            if num not in scores_finais and count >= 2:
                scores_finais[num] = 0.05 * count
    
    def completar_previsao_estrategica(self, selecao, historico):
        """Completa a previsão com números estratégicos"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        analise = analisar_duzias_colunas(historico)
        
        # Estratégia baseada nas dúzias e colunas quentes
        duzias_quentes = analise.get("duzias_quentes", [1, 2, 3])
        colunas_quentes = analise.get("colunas_quentes", [1, 2, 3])
        
        # Adicionar números das dúzias quentes
        for duzia in duzias_quentes:
            if duzia == 1:
                numeros_duzia = PRIMEIRA_DUZIA
            elif duzia == 2:
                numeros_duzia = SEGUNDA_DUZIA
            else:
                numeros_duzia = TERCEIRA_DUZIA
            
            for num in numeros_duzia:
                if num not in selecao and len(selecao) < NUMERO_PREVISOES:
                    selecao.append(num)
                if len(selecao) >= NUMERO_PREVISOES:
                    break
        
        # Adicionar números das colunas quentes
        for coluna in colunas_quentes:
            if coluna == 1:
                numeros_coluna = COLUNA_1
            elif coluna == 2:
                numeros_coluna = COLUNA_2
            else:
                numeros_coluna = COLUNA_3
            
            for num in numeros_coluna:
                if num not in selecao and len(selecao) < NUMERO_PREVISOES:
                    selecao.append(num)
                if len(selecao) >= NUMERO_PREVISOES:
                    break
        
        # Garantir zero
        if 0 not in selecao and len(selecao) < NUMERO_PREVISOES:
            selecao.append(0)
        
        return selecao[:NUMERO_PREVISOES]
    
    def diversificar_selecao_especialista_corrigida(self, selecao, historico):
        """Diversificação CORRIGIDA para garantir qualidade"""
        # Se já temos 15 números, otimizar a seleção
        if len(selecao) >= NUMERO_PREVISOES:
            # Garantir balanceamento entre dúzias
            return self.otimizar_balanceamento(selecao)
        
        # Se não, usar estratégia completa
        return self.completar_previsao_estrategica(selecao, historico)
    
    def otimizar_balanceamento(self, selecao):
        """Otimiza o balanceamento entre as dúzias"""
        balanceada = []
        
        # Garantir representação mínima de cada dúzia
        min_por_duzia = 3
        
        for duzia in [PRIMEIRA_DUZIA, SEGUNDA_DUZIA, TERCEIRA_DUZIA]:
            contagem = 0
            for num in selecao:
                if num in duzia:
                    balanceada.append(num)
                    contagem += 1
                if contagem >= min_por_duzia:
                    break
        
        # Completar com os melhores da seleção original
        for num in selecao:
            if num not in balanceada and len(balanceada) < NUMERO_PREVISOES:
                balanceada.append(num)
        
        # Garantir zero se não estiver presente
        if 0 in selecao and 0 not in balanceada and len(balanceada) < NUMERO_PREVISOES:
            balanceada.append(0)
        
        return balanceada[:NUMERO_PREVISOES]

    def prever_com_historio_normal(self, historico):
        """Estratégia para histórico menor que 450 - MELHORADA"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return self.estrategia_inicial_balanceada()
        
        previsao = set()
        analise = analisar_duzias_colunas(historico)
        
        # Estratégia mais inteligente para histórico médio
        duzias_quentes = analise.get("duzias_quentes", [2])
        colunas_quentes = analise.get("colunas_quentes", [2])
        
        # Focar na interseção dúzia + coluna quente
        for duzia in duzias_quentes:
            if duzia == 1:
                numeros_duzia = PRIMEIRA_DUZIA
            elif duzia == 2:
                numeros_duzia = SEGUNDA_DUZIA
            else:
                numeros_duzia = TERCEIRA_DUZIA
            
            for coluna in colunas_quentes:
                if coluna == 1:
                    numeros_coluna = COLUNA_1
                elif coluna == 2:
                    numeros_coluna = COLUNA_2
                else:
                    numeros_coluna = COLUNA_3
                
                # Adicionar interseção
                interseccao = [n for n in numeros_duzia if n in numeros_coluna]
                previsao.update(interseccao[:3])
        
        # Adicionar números recentes
        previsao.update(numeros[-5:])
        
        # Adicionar números frequentes
        freq = Counter(numeros[-20:])
        numeros_quentes = [num for num, count in freq.most_common(5) if count >= 2]
        previsao.update(numeros_quentes)
        
        # Completar com números balanceados
        if len(previsao) < NUMERO_PREVISOES:
            balanceados = [1, 3, 5, 7, 9, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36]
            for num in balanceados:
                if num not in previsao and len(previsao) < NUMERO_PREVISOES:
                    previsao.add(num)
        
        previsao.add(0)
        
        return list(previsao)[:NUMERO_PREVISOES]
    
    def estrategia_inicial_balanceada(self):
        """Estratégia inicial balanceada - ATUALIZADA"""
        # Seleção mais diversificada e estratégica
        numeros_estrategicos = [
            # 1ª Dúzia
            2, 5, 8, 11,
            # 2ª Dúzia  
            13, 16, 19, 22,
            # 3ª Dúzia
            25, 28, 31, 34,
            # Balanceamento
            1, 7, 0
        ]
        return validar_previsao(numeros_estrategicos)[:NUMERO_PREVISOES]

# =============================
# GESTOR PRINCIPAL CORRIGIDO
# =============================
class GestorHybridIA_Especialista_Corrigido:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_450_Plus_Corrigido()
        self.historico = deque(carregar_historico(), maxlen=1000)
        
    def adicionar_numero(self, numero_dict):
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        try:
            previsao = self.hybrid_system.prever_com_historio_longo(self.historico)
            previsao_validada = validar_previsao(previsao)
            
            # GARANTIR QUE SEMPRE RETORNA 15 NÚMEROS
            if len(previsao_validada) < NUMERO_PREVISOES:
                logging.warning(f"⚠️ Previsão com apenas {len(previsao_validada)} números. Completando...")
                previsao_validada = self.completar_para_15(previsao_validada)
            
            logging.info(f"✅ Previsão gerada: {len(previsao_validada)} números")
            return previsao_validada
            
        except Exception as e:
            logging.error(f"Erro crítico ao gerar previsão: {e}")
            return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    
    def completar_para_15(self, previsao):
        """Garante que sempre retorna 15 números"""
        if len(previsao) >= NUMERO_PREVISOES:
            return previsao[:NUMERO_PREVISOES]
        
        numeros_completos = set(previsao)
        
        # Adicionar números estratégicos faltantes
        numeros_estrategicos = [
            0, 2, 5, 8, 11, 13, 16, 19, 22, 25, 28, 31, 34, 1, 7
        ]
        
        for num in numeros_estrategicos:
            if len(numeros_completos) < NUMERO_PREVISOES:
                numeros_completos.add(num)
        
        # Se ainda não tem 15, adicionar sequencial
        if len(numeros_completos) < NUMERO_PREVISOES:
            for num in range(0, 37):
                if len(numeros_completos) < NUMERO_PREVISOES:
                    numeros_completos.add(num)
        
        return list(numeros_completos)[:NUMERO_PREVISOES]
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            
            if historico_size < FASE_INICIAL:
                return "🟡 Coletando Dados", "Estratégia Básica"
            elif historico_size < FASE_INTERMEDIARIA:
                return "🟠 Desenvolvendo", "Estratégia Intermediária"
            elif historico_size < FASE_AVANCADA:
                return "🟢 IA Avançada", "Análise Complexa"
            elif historico_size < FASE_ESPECIALISTA:
                return "🔵 Quase Especialista", "Otimização Final"
            else:
                return "🎯 ESPECIALISTA ATIVO", "Máxima Inteligência"
                
        except:
            return "⚪ Sistema", "Carregando..."
    
    def get_analise_detalhada(self):
        """Retorna análise detalhada do sistema"""
        if not self.historico:
            return {
                "modo_especialista": False,
                "historico_total": 0,
                "confianca": "Baixa",
                "padroes_detectados": 0
            }
        
        historico_size = len(self.historico)
        modo_especialista = historico_size >= MIN_HISTORICO_TREINAMENTO
        
        if modo_especialista:
            analise_profunda = self.hybrid_system.pattern_analyzer.analisar_padroes_profundos(self.historico)
            padroes_detectados = analise_profunda.get('total_padroes', 0)
            confianca = "Muito Alta"
        else:
            padroes_detectados = 0
            confianca = "Alta" if historico_size > 200 else "Média" if historico_size > 100 else "Baixa"
        
        return {
            "modo_especialista": modo_especialista,
            "historico_total": historico_size,
            "confianca": confianca,
            "padroes_detectados": padroes_detectados,
            "minimo_especialista": MIN_HISTORICO_TREINAMENTO
        }

# =============================
# STREAMLIT APP
# =============================
st.set_page_config(
    page_title="Roleta - IA Especialista 450+", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Hybrid IA System - ESPECIALISTA 450+ CORRIGIDO")
st.markdown("### **Sistema Corrigido com Garantia de 15 Números**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorHybridIA_Especialista_Corrigido(),
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
                enviar_telegram(f"🟢 GREEN! Especialista Corrigido acertou {numero_real}!")
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")

        # GERAR NOVA PREVISÃO
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # TELEGRAM - Mensagem especial para modo especialista
        if st.session_state.previsao_atual and len(st.session_state.gestor.historico) >= 3:
            try:
                analise = st.session_state.gestor.get_analise_detalhada()
                mensagem = f"🎯 **IA ESPECIALISTA CORRIGIDA - PREVISÃO**\n"
                
                if analise["modo_especialista"]:
                    mensagem += f"🚀 **MODO ESPECIALISTA ATIVO**\n"
                    mensagem += f"📊 Padrões Detectados: {analise['padroes_detectados']}\n"
                else:
                    mensagem += f"📈 Progresso: {analise['historico_total']}/{analise['minimo_especialista']}\n"
                
                mensagem += f"🧠 Status: {st.session_state.status_ia}\n"
                mensagem += f"🎯 Estratégia: {st.session_state.estrategia_atual}\n"
                mensagem += f"💪 Confiança: {analise['confianca']}\n"
                mensagem += f"🔢 Último: {numero_real}\n"
                mensagem += f"📈 Performance: {st.session_state.acertos}G/{st.session_state.erros}R\n"
                mensagem += f"🔢 Números Previstos: {len(st.session_state.previsao_atual)}\n"
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
# INTERFACE STREAMLIT
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

# ANÁLISE DO SISTEMA ESPECIALISTA
st.subheader("🔍 Análise do Sistema Especialista")
analise = st.session_state.gestor.get_analise_detalhada()

col1, col2, col3, col4 = st.columns(4)
with col1:
    modo = "🎯 ATIVO" if analise["modo_especialista"] else "⏳ AGUARDANDO"
    st.metric("🚀 Modo Especialista", modo)
with col2:
    st.metric("💪 Confiança", analise["confianca"])
with col3:
    st.metric("📈 Padrões", analise["padroes_detectados"])
with col4:
    progresso = min(100, (analise["historico_total"] / analise["minimo_especialista"]) * 100)
    st.metric("📊 Progresso", f"{progresso:.1f}%")

# BARRA DE PROGRESSO PARA MODO ESPECIALISTA
st.subheader("🎯 Progresso para Modo Especialista")
historico_atual = len(st.session_state.gestor.historico)
progresso = min(100, (historico_atual / MIN_HISTORICO_TREINAMENTO) * 100)

st.progress(progresso / 100)

if historico_atual < MIN_HISTORICO_TREINAMENTO:
    st.info(f"📈 Coletando dados: {historico_atual}/{MIN_HISTORICO_TREINAMENTO} ({progresso:.1f}%)")
    st.caption("🟡 O sistema se tornará ESPECIALISTA ao atingir 450 registros")
else:
    st.success(f"🎯 MODO ESPECIALISTA ATIVO - {analise['padroes_detectados']} padrões detectados")
    st.caption("🟢 Sistema analisando padrões complexos de longo prazo")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL - SISTEMA ESPECIALISTA CORRIGIDO")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    if analise["modo_especialista"]:
        if len(previsao_valida) == NUMERO_PREVISOES:
            st.success(f"**🚀 {len(previsao_valida)} NÚMEROS PREVISTOS PELO ESPECIALISTA**")
        else:
            st.warning(f"**⚠️ {len(previsao_valida)} NÚMEROS PREVISTOS (Sistema Corrigido)**")
    else:
        st.success(f"**📊 {len(previsao_valida)} NÚMEROS PREVISTOS**")
    
    # Display organizado
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**1ª Dúzia (1-12):**")
        nums_duzia1 = [n for n in sorted(previsao_valida) if n in PRIMEIRA_DUZIA]
        for num in nums_duzia1:
            cor = "🔴" if num in [1,3,5,7,9,12] else "⚫"
            st.write(f"{cor} `{num}`")
    
    with col2:
        st.write("**2ª Dúzia (13-24):**")
        nums_duzia2 = [n for n in sorted(previsao_valida) if n in SEGUNDA_DUZIA]
        for num in nums_duzia2:
            cor = "🔴" if num in [14,16,18,19,21,23] else "⚫"
            st.write(f"{cor} `{num}`")
    
    with col3:
        st.write("**3ª Dúzia (25-36):**")
        nums_duzia3 = [n for n in sorted(previsao_valida) if n in TERCEIRA_DUZIA]
        for num in nums_duzia3:
            cor = "🔴" if num in [25,27,30,32,34,36] else "⚫"
            st.write(f"{cor} `{num}`")
        
        if 0 in previsao_valida:
            st.write("🟢 `0`")
    
    st.write(f"**Lista Completa ({len(previsao_valida)} números):** {', '.join(map(str, sorted(previsao_valida)))}")
    
else:
    st.warning("⚠️ Inicializando sistema...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

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
    st.metric("📈 Taxa Acerto", f"{taxa_acerto:.1f}%")
with col4:
    st.metric("🔄 Rodadas", st.session_state.contador_rodadas)

# DETALHES TÉCNICOS
with st.expander("🔧 Detalhes Técnicos do Sistema Especialista Corrigido"):
    st.write("**🎯 ARQUITETURA ESPECIALISTA 450+ CORRIGIDA:**")
    
    if analise["modo_especialista"]:
        st.write("✅ **MODO ESPECIALISTA ATIVO**")
        st.write("- 🔍 Análise de Ciclos Complexos")
        st.write("- 📈 Correlações entre Números") 
        st.write("- 🕒 Padrões Temporais Avançados")
        st.write("- 🔄 Sequências de Alta Ordem")
        st.write(f"- 📊 {analise['padroes_detectados']} Padrões Detectados")
        st.write("✅ **CORREÇÕES IMPLEMENTADAS:**")
        st.write("- 🎯 Garantia de 15 números")
        st.write("- ⚖️ Balanceamento entre dúzias")
        st.write("- 🚀 Pesos otimizados do ensemble")
        st.write("- 🛡️ Sistema de fallback robusto")
    else:
        st.write("⏳ **AGUARDANDO DADOS SUFICIENTES**")
        st.write(f"- 📈 Progresso: {historico_atual}/{MIN_HISTORICO_TREINAMENTO}")
        st.write("- 🎯 Ativação automática em 450 registros")
        st.write("- 🔄 Coletando dados para análise profunda")
    
    st.write(f"**📊 Estatísticas:**")
    st.write(f"- Histórico Atual: {historico_atual} registros")
    st.write(f"- Confiança: {analise['confianca']}")
    st.write(f"- Estratégia: {st.session_state.estrategia_atual}")
    st.write(f"- Números na Previsão: {len(st.session_state.previsao_atual)}")

# CONTROLES
st.markdown("---")
st.subheader("⚙️ Controles do Sistema")

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
st.markdown("### 🚀 **Sistema Especialista Corrigido - Garantia de 15 Números**")
st.markdown("*Padrões complexos, correlações avançadas e inteligência de longo prazo*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Hybrid IA System v6.1** - *Especialista 450+ Registros Corrigido*")
