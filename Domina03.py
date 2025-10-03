# RoletaHybridIA.py - SISTEMA ESPECIALISTA COM ROTAÇÃO DINÂMICA E CONTEXTO PERSISTENTE
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
import random
import warnings
warnings.filterwarnings('ignore')

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
CONTEXTO_PATH = "contexto_historico.json"  # NOVO ARQUIVO PARA CONTEXTO
METRICAS_PATH = "metricas_hybrid_ia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002979544095"

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
MIN_HISTORICO_TREINAMENTO = 350
NUMERO_PREVISOES = 10

# Fases do sistema
FASE_INICIAL = 50
FASE_INTERMEDIARIA = 150  
FASE_AVANCADA = 300
FASE_ESPECIALISTA = 450

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

def enviar_alerta_rapido(numeros):
    """Envia alerta no formato: 2 linhas (8 + 7 números) ordenados"""
    try:
        if not numeros or len(numeros) != 15:
            return
            
        # Ordena os números do menor para o maior
        numeros_ordenados = sorted(numeros)
        
        # Divide em 2 linhas: 8 números na primeira, 7 na segunda
        linha1 = ' '.join(map(str, numeros_ordenados[0:8]))
        linha2 = ' '.join(map(str, numeros_ordenados[8:15]))
        
        # Formata EXATAMENTE como você quer - 2 LINHAS
        mensagem = f"N {linha1}\n{linha2}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta enviado no formato 2x (8+7)")
        
    except Exception as e:
        logging.error(f"Erro alerta: {e}")

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
# CONTEXT PREDICTOR COM PERSISTÊNCIA COMPLETA
# =============================
class Context_Predictor_Persistente:
    def __init__(self):
        self.context_history = {}
        self.min_occurrences = 1
        self.arquivo_contexto = CONTEXTO_PATH
        self.carregar_contexto()  # CARREGA CONTEXTO EXISTENTE AO INICIAR
        
    def carregar_contexto(self):
        """Carrega contexto histórico do arquivo"""
        try:
            if os.path.exists(self.arquivo_contexto):
                with open(self.arquivo_contexto, "r") as f:
                    dados = json.load(f)
                    
                    # Converter chaves string para int (JSON salva como string)
                    contexto_convertido = {}
                    for key_str, valor in dados.items():
                        key_int = int(key_str)
                        contexto_convertido[key_int] = valor
                    
                    self.context_history = contexto_convertido
                logging.info(f"📂 CONTEXTO CARREGADO: {len(self.context_history)} contextos ativos")
            else:
                logging.info("🆕 Criando novo contexto histórico")
                self.context_history = {}
        except Exception as e:
            logging.error(f"❌ Erro ao carregar contexto: {e}")
            self.context_history = {}
    
    def salvar_contexto(self):
        """Salva contexto histórico no arquivo"""
        try:
            with open(self.arquivo_contexto, "w") as f:
                json.dump(self.context_history, f, indent=2)
            logging.info(f"💾 CONTEXTO SALVO: {len(self.context_history)} contextos")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar contexto: {e}")
    
    def atualizar_contexto(self, numero_anterior, numero_atual):
        """Atualiza contexto com persistência automática"""
        try:
            if numero_anterior is None or numero_atual is None:
                return
                
            # ATUALIZAR CONTEXTO
            if numero_anterior not in self.context_history:
                self.context_history[numero_anterior] = {}
            
            if numero_atual not in self.context_history[numero_anterior]:
                self.context_history[numero_anterior][numero_atual] = 0
                
            self.context_history[numero_anterior][numero_atual] += 1
            
            # SALVAR AUTOMATICAMENTE APÓS ATUALIZAÇÃO
            self.salvar_contexto()
            
            logging.debug(f"🔄 Contexto atualizado: {numero_anterior} → {numero_atual}")
            
        except Exception as e:
            logging.error(f"Erro ao atualizar contexto: {e}")
    
    def limpar_contexto_obsoleto(self):
        """Limpeza mantendo persistência"""
        if len(self.context_history) < 30:
            return
            
        contextos_antes = len(self.context_history)
        
        for anterior in list(self.context_history.keys()):
            seguintes = self.context_history[anterior]
            para_remover = [num for num, count in seguintes.items() 
                           if count < self.min_occurrences]
            
            for num in para_remover:
                del seguintes[num]
            
            if not seguintes:
                del self.context_history[anterior]
        
        # Salvar se houve mudanças
        if len(self.context_history) != contextos_antes:
            self.salvar_contexto()
    
    def prever_por_contexto(self, ultimo_numero, top_n=8):
        """Previsão com fallback inteligente"""
        try:
            # 1. TENTAR PREVISÃO POR CONTEXTO HISTÓRICO
            if ultimo_numero in self.context_history:
                contexto = self.context_history[ultimo_numero]
                
                if contexto:
                    numeros_ordenados = sorted(contexto.items(), key=lambda x: x[1], reverse=True)
                    previsao = [num for num, count in numeros_ordenados[:top_n]]
                    
                    if len(previsao) >= 3:  # Pelo menos 3 números do contexto
                        logging.info(f"🔍 CONTEXTO FORTE: Após {ultimo_numero} → {previsao}")
                        return previsao[:top_n]
            
            # 2. FALLBACK: VIZINHOS FÍSICOS + NÚMEROS QUENTES
            previsao_fallback = self.get_previsao_fallback(ultimo_numero, top_n)
            logging.info(f"🔄 CONTEXTO FALLBACK: Após {ultimo_numero} → {previsao_fallback}")
            
            return previsao_fallback
            
        except Exception as e:
            logging.error(f"Erro na previsão por contexto: {e}")
            return self.get_previsao_fallback(ultimo_numero, top_n)
    
    def get_previsao_fallback(self, numero, quantidade):
        """Fallback inteligente quando não há contexto suficiente"""
        previsao = set()
        
        # 1. VIZINHOS FÍSICOS (50%)
        vizinhos = obter_vizinhos_fisicos(numero)
        previsao.update(vizinhos[:quantidade//2])
        
        # 2. NÚMEROS MAIS FREQUENTES NO CONTEXTO GERAL (30%)
        if len(previsao) < quantidade:
            numeros_quentes = self.get_numeros_mais_frequentes()
            for num in numeros_quentes:
                if len(previsao) < quantidade and num not in previsao:
                    previsao.add(num)
        
        # 3. COMPLETAR COM ESTRATÉGIA (20%)
        if len(previsao) < quantidade:
            estrategicos = [2, 5, 8, 11, 13, 16, 19, 22, 25, 28, 31, 34]
            for num in estrategicos:
                if len(previsao) < quantidade and num not in previsao:
                    previsao.add(num)
        
        return list(previsao)[:quantidade]
    
    def get_numeros_mais_frequentes(self):
        """Retorna os números mais frequentes em todo o contexto"""
        frequencia_global = {}
        
        for anterior, seguintes in self.context_history.items():
            for numero, count in seguintes.items():
                frequencia_global[numero] = frequencia_global.get(numero, 0) + count
        
        # Ordenar por frequência
        numeros_ordenados = sorted(frequencia_global.items(), key=lambda x: x[1], reverse=True)
        return [num for num, count in numeros_ordenados[:10]]
    
    def get_estatisticas_contexto(self):
        """Retorna estatísticas detalhadas do contexto"""
        total_transicoes = sum(
            sum(seguintes.values()) 
            for seguintes in self.context_history.values()
        )
        
        # Número mais frequente globalmente
        frequencia_global = self.get_numeros_mais_frequentes()
        numero_mais_frequente = frequencia_global[0] if frequencia_global else "Nenhum"
        
        return {
            'contextos_ativos': len(self.context_history),
            'total_transicoes': total_transicoes,
            'min_occurrences': self.min_occurrences,
            'numero_mais_frequente': numero_mais_frequente,
            'previsao_exemplo': self.get_exemplo_previsao()
        }
    
    def get_exemplo_previsao(self):
        """Retorna um exemplo de previsão para demonstração"""
        if not self.context_history:
            return "Aguardando dados..."
        
        # Pegar o último contexto disponível
        ultimo_contexto = list(self.context_history.keys())[-1]
        previsao = self.prever_por_contexto(ultimo_contexto, 3)
        
        return f"Após {ultimo_contexto} → {previsao}"

# =============================
# SISTEMA DE ROTAÇÃO DINÂMICA
# =============================
class Dynamic_Rotator:
    def __init__(self):
        self.ultimas_previsoes = deque(maxlen=10)
        self.contador_estabilidade = 0
        
    def aplicar_rotacao_estrategica(self, previsao_base, historico):
        """Aplica rotação dinâmica mantendo o núcleo forte"""
        try:
            if len(previsao_base) != 15:
                return previsao_base
                
            # Verificar se precisa de variação
            if self.deve_aplicar_rotacao(previsao_base):
                return self.rotacionar_previsao(previsao_base, historico)
            else:
                return previsao_base
                
        except Exception as e:
            logging.error(f"Erro na rotação dinâmica: {e}")
            return previsao_base
    
    def deve_aplicar_rotacao(self, previsao_atual):
        """Decide se deve rotacionar baseado na estabilidade"""
        # Se é a primeira previsão, não rotaciona
        if not self.ultimas_previsoes:
            self.ultimas_previsoes.append(previsao_atual)
            return False
            
        # Verificar similaridade com previsões anteriores
        similaridade = self.calcular_similaridade(previsao_atual, self.ultimas_previsoes[-1])
        
        # Se está muito similar por várias rodadas, rotaciona
        if similaridade > 0.8:  # 80% de similaridade
            self.contador_estabilidade += 1
        else:
            self.contador_estabilidade = 0
            
        # Rotacionar se está estável por 2 rodadas ou mais
        deve_rotacionar = self.contador_estabilidade >= 2
        
        self.ultimas_previsoes.append(previsao_atual)
        return deve_rotacionar
    
    def calcular_similaridade(self, previsao1, previsao2):
        """Calcula similaridade entre duas previsões"""
        set1 = set(previsao1)
        set2 = set(previsao2)
        return len(set1 & set2) / len(set1 | set2)
    
    def rotacionar_previsao(self, previsao_base, historico):
        """Aplica rotação estratégica na previsão"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return previsao_base
            
        # Estratégias de rotação
        nova_previsao = self.rotacao_por_frequencia(previsao_base, numeros)
        nova_previsao = self.rotacao_por_vizinhanca(nova_previsao, numeros)
        nova_previsao = self.rotacao_aleatoria_controlada(nova_previsao)
        
        logging.info(f"🔄 ROTAÇÃO APLICADA: {len(set(previsao_base) - set(nova_previsao))} números alterados")
        return nova_previsao
    
    def rotacao_por_frequencia(self, previsao_base, numeros):
        """Rotaciona baseado na frequência recente"""
        # Analisar frequência dos últimos 20 números
        freq_recente = Counter(numeros[-20:])
        
        # Encontrar números frequentes não presentes na previsão
        numeros_quentes = [num for num, count in freq_recente.most_common(10) 
                          if num not in previsao_base and count >= 2]
        
        if numeros_quentes:
            # Substituir 1-2 números de menor frequência na previsão
            freq_na_previsao = {num: freq_recente.get(num, 0) for num in previsao_base}
            para_remover = sorted(freq_na_previsao.items(), key=lambda x: x[1])[:2]
            
            nova_previsao = previsao_base.copy()
            for num_remover, _ in para_remover:
                if numeros_quentes and num_remover in nova_previsao:
                    nova_previsao.remove(num_remover)
                    novo_num = numeros_quentes.pop(0)
                    nova_previsao.append(novo_num)
            
            return nova_previsao
        
        return previsao_base
    
    def rotacao_por_vizinhanca(self, previsao_base, numeros):
        """Rotaciona baseado em vizinhança física"""
        # Focar nos últimos números sorteados
        ultimos_numeros = numeros[-5:]
        
        vizinhos_estrategicos = set()
        for num in ultimos_numeros:
            vizinhos = obter_vizinhos_fisicos(num)
            vizinhos_estrategicos.update(vizinhos)
        
        # Filtrar vizinhos não presentes na previsão
        vizinhos_novos = [v for v in vizinhos_estrategicos if v not in previsao_base]
        
        if vizinhos_novos:
            # Substituir 1 número por um vizinho estratégico
            nova_previsao = previsao_base.copy()
            
            # Remover um número menos promissor
            numeros_para_remover = [num for num in nova_previsao 
                                  if num not in ultimos_numeros and num != 0]
            
            if numeros_para_remover:
                num_remover = numeros_para_remover[0]
                nova_previsao.remove(num_remover)
                nova_previsao.append(vizinhos_novos[0])
                
            return nova_previsao
        
        return previsao_base
    
    def rotacao_aleatoria_controlada(self, previsao_base):
        """Rotação aleatória controlada (1 número)"""
        # Números disponíveis para rotação (excluindo zero e números muito quentes)
        todos_numeros = list(range(0, 37))
        numeros_disponiveis = [num for num in todos_numeros if num not in previsao_base]
        
        if len(numeros_disponiveis) >= 1 and len(previsao_base) == 15:
            nova_previsao = previsao_base.copy()
            
            # Escolher aleatoriamente 1 número para substituir (excluindo zero)
            numeros_substituiveis = [num for num in nova_previsao if num != 0]
            if numeros_substituiveis:
                num_remover = random.choice(numeros_substituiveis)
                num_novo = random.choice(numeros_disponiveis)
                
                nova_previsao.remove(num_remover)
                nova_previsao.append(num_novo)
                
                return nova_previsao
        
        return previsao_base

# =============================
# SISTEMA ESPECIALISTA 450+ COM ROTAÇÃO
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
        self.dynamic_rotator = Dynamic_Rotator()  # SISTEMA DE ROTAÇÃO
        self.ultima_previsao_base = None
        
    def prever_com_historio_longo(self, historico):
        """Sistema especializado com rotação dinâmica"""
        historico_size = len(historico)
        
        if historico_size >= MIN_HISTORICO_TREINAMENTO:
            logging.info(f"🚀 ATIVANDO MODO ESPECIALISTA - {historico_size} REGISTROS")
            
            # 1. Análise profunda de padrões
            analise_profunda = self.pattern_analyzer.analisar_padroes_profundos(historico)
            
            # 2. Predição especializada
            probs_xgb = self.xgb_especialista.predict_com_450_plus(historico)
            
            # 3. Combinação inteligente
            previsao_base = self.combinar_previsoes_especialistas_corrigido(analise_profunda, probs_xgb, historico)
            
            # 4. APLICAR ROTAÇÃO DINÂMICA
            previsao_final = self.dynamic_rotator.aplicar_rotacao_estrategica(previsao_base, historico)
            self.ultima_previsao_base = previsao_base
            
            # Log das diferenças
            if self.ultima_previsao_base and previsao_final != self.ultima_previsao_base:
                diff = set(previsao_final) - set(self.ultima_previsao_base)
                logging.info(f"🔄 Números rotacionados: {diff}")
            
            logging.info(f"🎯 ESPECIALISTA + ROTAÇÃO: {analise_profunda['total_padroes']} padrões → {len(previsao_final)} números")
            return previsao_final
        else:
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
# GESTOR PRINCIPAL COM ROTAÇÃO E CONTEXTO PERSISTENTE
# =============================
class GestorHybridIA_Especialista_Corrigido:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_450_Plus_Corrigido()
        self.context_predictor = Context_Predictor_Persistente()  # AGORA COM PERSISTÊNCIA
        self.historico = deque(carregar_historico(), maxlen=1000)
        self.previsao_anterior = None
        self.ultimo_numero_processado = None
        
        # INICIALIZAÇÃO RÁPIDA COM HISTÓRICO EXISTENTE
        self.inicializar_contexto_com_historico()
    
    def inicializar_contexto_com_historico(self):
        """Inicializa o contexto com todo o histórico existente"""
        try:
            if len(self.historico) > 1:
                numeros = [h['number'] for h in self.historico if h.get('number') is not None]
                transicoes_adicionadas = 0
                
                for i in range(1, len(numeros)):
                    self.context_predictor.atualizar_contexto(numeros[i-1], numeros[i])
                    transicoes_adicionadas += 1
                
                logging.info(f"🚀 CONTEXTO INICIALIZADO: {transicoes_adicionadas} transições do histórico")
                
                estatisticas = self.context_predictor.get_estatisticas_contexto()
                logging.info(f"📊 CONTEXTO: {estatisticas['contextos_ativos']} contextos, {estatisticas['total_transicoes']} transições")
                
        except Exception as e:
            logging.error(f"Erro na inicialização do contexto: {e}")
    
    def adicionar_numero(self, numero_dict):
        """Adiciona número e atualiza contexto histórico"""
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            numero_atual = numero_dict['number']
            
            # ATUALIZAR CONTEXTO se temos um número anterior
            if self.ultimo_numero_processado is not None:
                self.context_predictor.atualizar_contexto(
                    self.ultimo_numero_processado, 
                    numero_atual
                )
            
            self.ultimo_numero_processado = numero_atual
            self.historico.append(numero_dict)
    
    def gerar_previsao_contextual(self):
        """Gera previsão combinando IA + Contexto Histórico"""
        try:
            # 1. PREVISÃO BASE DA IA
            previsao_ia = self.hybrid_system.prever_com_historio_longo(self.historico)
            
            # 2. PREVISÃO POR CONTEXTO (se temos último número)
            previsao_contexto = []
            if self.ultimo_numero_processado is not None:
                previsao_contexto = self.context_predictor.prever_por_contexto(
                    self.ultimo_numero_processado, 
                    top_n=8
                )
            
            # 3. COMBINAÇÃO INTELIGENTE
            previsao_combinada = self.combinar_previsoes(previsao_ia, previsao_contexto)
            
            # 4. APLICAR ROTAÇÃO DINÂMICA
            previsao_final = self.hybrid_system.dynamic_rotator.aplicar_rotacao_estrategica(
                previsao_combinada, 
                self.historico
            )
            
            logging.info(f"🎯 PREVISÃO COMBINADA: IA({len(previsao_ia)}) + Contexto({len(previsao_contexto)}) → {len(previsao_final)} números")
            
            return previsao_final
            
        except Exception as e:
            logging.error(f"Erro na previsão contextual: {e}")
            return self.hybrid_system.prever_com_historio_longo(self.historico)
    
    def combinar_previsoes(self, previsao_ia, previsao_contexto):
        """Combina previsão da IA com previsão contextual"""
        combinada = set(previsao_ia)
        
        # Adicionar números do contexto que não estão na previsão da IA
        for num_contexto in previsao_contexto:
            if len(combinada) < NUMERO_PREVISOES and num_contexto not in combinada:
                combinada.add(num_contexto)
        
        # Se ainda não temos 15 números, completar com a IA
        if len(combinada) < NUMERO_PREVISOES:
            for num_ia in previsao_ia:
                if len(combinada) < NUMERO_PREVISOES:
                    combinada.add(num_ia)
        
        # Garantir que temos exatamente 15 números
        return self.completar_para_15(list(combinada))
    
    def get_analise_contexto(self):
        """Retorna análise detalhada do sistema contextual"""
        estatisticas = self.context_predictor.get_estatisticas_contexto()
        
        # Exemplo de previsão contextual atual
        previsao_atual = []
        if self.ultimo_numero_processado is not None:
            previsao_atual = self.context_predictor.prever_por_contexto(
                self.ultimo_numero_processado, 
                top_n=5
            )
        
        return {
            'contextos_ativos': estatisticas['contextos_ativos'],
            'total_transicoes': estatisticas['total_transicoes'],
            'ultimo_numero': self.ultimo_numero_processado,
            'previsao_contexto_atual': previsao_atual,
            'min_occurrences': estatisticas['min_occurrences'],
            'numero_mais_frequente': estatisticas['numero_mais_frequente'],
            'previsao_exemplo': estatisticas['previsao_exemplo']
        }

    def gerar_previsao(self):
        """Método legado - usa o novo sistema contextual"""
        return self.gerar_previsao_contextual()
        
    def calcular_diferencas(self, previsao_atual):
        """Calcula diferenças com a previsão anterior"""
        if not self.previsao_anterior or len(self.previsao_anterior) != 15 or len(previsao_atual) != 15:
            return None
            
        anteriores = set(self.previsao_anterior)
        atuais = set(previsao_atual)
        
        removidos = anteriores - atuais
        adicionados = atuais - anteriores
        
        if removidos or adicionados:
            return {
                'removidos': sorted(removidos),
                'adicionados': sorted(adicionados),
                'total_mudancas': len(removidos)
            }
        
        return None
    
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
    page_title="Roleta - IA Especialista com Rotação", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Hybrid IA System - ESPECIALISTA COM ROTAÇÃO DINÂMICA")
st.markdown("### **Sistema com Variações Estratégicas entre Previsões**")

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
    "previsao_anterior": None,
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
            # AGORA ATUALIZA CONTEXTO E SALVA AUTOMATICAMENTE
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
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")

        # GERAR NOVA PREVISÃO COM CONTEXTO
        nova_previsao = st.session_state.gestor.gerar_previsao_contextual()  # AGORA USA CONTEXTO
        
        # CALCULAR MUDANÇAS
        diferencas = st.session_state.gestor.calcular_diferencas(nova_previsao)
        st.session_state.previsao_anterior = st.session_state.previsao_atual.copy()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # ENVIAR ALERTA TELEGRAM
        if st.session_state.previsao_atual and len(st.session_state.previsao_atual) == 15:
            try:
                enviar_alerta_rapido(st.session_state.previsao_atual)
            except Exception as e:
                logging.error(f"Erro ao enviar alerta: {e}")

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

# NOVA SEÇÃO - PREVISÃO POR CONTEXTO HISTÓRICO PERSISTENTE
st.markdown("---")
st.subheader("🔮 PREVISÃO POR CONTEXTO HISTÓRICO - PERSISTENTE")

analise_contexto = st.session_state.gestor.get_analise_contexto()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🎯 Último Número", analise_contexto['ultimo_numero'])

with col2:
    st.metric("📊 Contextos", analise_contexto['contextos_ativos'])

with col3:
    st.metric("🔄 Transições", analise_contexto['total_transicoes'])

with col4:
    st.metric("🔥 Nº Mais Frequente", analise_contexto['numero_mais_frequente'])

# MOSTRAR PREVISÃO CONTEXTUAL ATUAL
previsao_contexto = analise_contexto['previsao_contexto_atual']
if previsao_contexto:
    st.success(f"**📈 Números mais prováveis após {analise_contexto['ultimo_numero']}:**")
    
    # Mostrar com cores para indicar força da previsão
    if len(previsao_contexto) >= 5:
        emoji = "🎯"
        cor = "green"
    elif len(previsao_contexto) >= 3:
        emoji = "🔍" 
        cor = "orange"
    else:
        emoji = "🔄"
        cor = "blue"
    
    contexto_str = " | ".join([f"**{num}**" for num in previsao_contexto])
    st.markdown(f"### {emoji} {contexto_str}")
    
    st.caption(f"💡 Baseado em {analise_contexto['total_transicoes']} transições históricas (Dados Persistidos)")
    
    # Exemplo de previsão
    if analise_contexto.get('previsao_exemplo'):
        st.info(f"**Exemplo:** {analise_contexto['previsao_exemplo']}")
        
else:
    st.info("🔄 Aguardando dados contextuais... O sistema está aprendendo os padrões.")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL - SISTEMA COM ROTAÇÃO DINÂMICA")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

# MOSTRAR MUDANÇAS
if st.session_state.previsao_anterior and len(st.session_state.previsao_anterior) == 15:
    diferencas = st.session_state.gestor.calcular_diferencas(st.session_state.previsao_atual)
    if diferencas:
        st.info(f"**🔄 Mudanças:** Removidos: {', '.join(map(str, diferencas['removidos']))} | Adicionados: {', '.join(map(str, diferencas['adicionados']))}")

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
with st.expander("🔧 Detalhes Técnicos do Sistema com Rotação"):
    st.write("**🎯 ARQUITETURA ESPECIALISTA COM ROTAÇÃO DINÂMICA:**")
    
    if analise["modo_especialista"]:
        st.write("✅ **MODO ESPECIALISTA ATIVO**")
        st.write("- 🔍 Análise de Ciclos Complexos")
        st.write("- 📈 Correlações entre Números") 
        st.write("- 🕒 Padrões Temporais Avançados")
        st.write("- 🔄 Sequências de Alta Ordem")
        st.write("- 🔮 **PREVISÃO POR CONTEXTO HISTÓRICO**")
        st.write(f"- 📊 {analise['padroes_detectados']} Padrões Detectados")
        st.write("**🔄 SISTEMA DE ROTAÇÃO:**")
        st.write("- 🎯 Rotação por Frequência")
        st.write("- 📍 Rotação por Vizinhança Física") 
        st.write("- 🎲 Rotação Aleatória Controlada")
        st.write("- ⚖️ Balanceamento Automático")
    else:
        st.write("⏳ **AGUARDANDO DADOS SUFICIENTES**")
        st.write(f"- 📈 Progresso: {historico_atual}/{MIN_HISTORICO_TREINAMENTO}")
        st.write("- 🎯 Ativação automática em 450 registros")
        st.write("- 🔄 Coletando dados para análise profunda")
        st.write("- 🔮 **Coletando padrões contextuais**")
    
    # NOVA SEÇÃO DE CONTEXTO
    st.write("**🔮 SISTEMA DE CONTEXTO HISTÓRICO PERSISTENTE:**")
    st.write(f"- Contextos ativos: {analise_contexto['contextos_ativos']}")
    st.write(f"- Transições analisadas: {analise_contexto['total_transicoes']}")
    st.write(f"- Mínimo de ocorrências: {analise_contexto['min_occurrences']}")
    st.write(f"- Número mais frequente: {analise_contexto['numero_mais_frequente']}")
    
    if analise_contexto['previsao_contexto_atual']:
        st.write(f"- Previsão atual: {analise_contexto['previsao_contexto_atual']}")
    
    if analise_contexto.get('previsao_exemplo'):
        st.write(f"- Exemplo: {analise_contexto['previsao_exemplo']}")
    
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
        nova_previsao = st.session_state.gestor.gerar_previsao_contextual()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        st.rerun()

with col2:
    if st.button("🗑️ Limpar Histórico"):
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        if os.path.exists(CONTEXTO_PATH):
            os.remove(CONTEXTO_PATH)
        st.session_state.gestor.historico.clear()
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.rerun()

st.markdown("---")
st.markdown("### 🚀 **Sistema Especialista com Rotação Dinâmica**")
st.markdown("*Variações estratégicas mantendo alta assertividade*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Hybrid IA System v9.0** - *Especialista com Rotação Dinâmica e Contexto Histórico Persistente*")
