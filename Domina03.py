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
CONTEXTO_PATH = "contexto_historico.json"
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
MIN_HISTORICO_TREINAMENTO = 210
NUMERO_PREVISOES = 12

# Fases do sistema
FASE_INICIAL = 50
FASE_INTERMEDIARIA = 150  
FASE_AVANCADA = 300
FASE_ESPECIALISTA = 950

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

def enviar_alerta_contextual(numeros):
    """Envia alerta contextual no formato: 2 linhas (4 + 4 números) ordenados"""
    try:
        if not numeros or len(numeros) != 8:
            return
            
        # Ordena os números do menor para o maior
        numeros_ordenados = sorted(numeros)
        
        # Divide em 2 linhas: 4 números na primeira, 4 na segunda
        linha1 = ' '.join(map(str, numeros_ordenados[0:4]))
        linha2 = ' '.join(map(str, numeros_ordenados[4:8]))
        
        # Formata EXATAMENTE como você quer - 2 LINHAS
        mensagem = f"C {linha1}\n{linha2}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta CONTEXTUAL enviado: 8 números")
        
    except Exception as e:
        logging.error(f"Erro alerta contextual: {e}")

def enviar_alerta_resultado(acertou, numero_sorteado, previsao_anterior):
    """Envia alerta de resultado (GREEN/RED)"""
    try:
        if acertou:
            mensagem = f"🟢 GREEN! Número {numero_sorteado} acertado na previsão!"
            emoji = "🟢"
        else:
            mensagem = f"🔴 RED! Número {numero_sorteado} não estava na previsão anterior."
            emoji = "🔴"
        
        # Adiciona informações extras
        mensagem += f"\n🎯 Previsão anterior: {', '.join(map(str, sorted(previsao_anterior)))}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de RESULTADO enviado: {emoji}")
        
    except Exception as e:
        logging.error(f"Erro alerta resultado: {e}")

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

def analisar_padroes_ultimos_20(historico):
    """Analisa padrões específicos dos últimos 20 números"""
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    if len(numeros) < 20:
        return {}
    
    ultimos_20 = numeros[-20:]
    
    # Padrão: números que se repetem em intervalos curtos
    padroes = {
        'repetidos_3_rodadas': [],
        'sequencias_vizinhas': [],
        'alternancia_cores': 0
    }
    
    # Encontrar números que se repetem a cada 3-4 rodadas
    for i in range(len(ultimos_20) - 4):
        if ultimos_20[i] == ultimos_20[i+3] or ultimos_20[i] == ultimos_20[i+4]:
            if ultimos_20[i] not in padroes['repetidos_3_rodadas']:
                padroes['repetidos_3_rodadas'].append(ultimos_20[i])
    
    # Analisar alternância de cores
    mudancas_cor = 0
    for i in range(1, len(ultimos_20)):
        cor_atual = 'vermelho' if ultimos_20[i] in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'preto'
        cor_anterior = 'vermelho' if ultimos_20[i-1] in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'preto'
        if cor_atual != cor_anterior:
            mudancas_cor += 1
    
    padroes['alternancia_cores'] = mudancas_cor / len(ultimos_20)
    
    return padroes

# =============================
# CONTEXT PREDICTOR CORRIGIDO - CAPTURA PADRÕES ÓBVIOS
# =============================
class Context_Predictor_Persistente_Corrigido:
    def __init__(self):
        self.context_history = {}
        self.min_occurrences = 1
        self.arquivo_contexto = CONTEXTO_PATH
        self.carregar_contexto()
        
    def carregar_contexto(self):
        """Carrega contexto histórico - CORREÇÃO CRÍTICA"""
        try:
            if os.path.exists(self.arquivo_contexto):
                with open(self.arquivo_contexto, "r") as f:
                    dados = json.load(f)
                    
                # CONVERSÃO MAIS ROBUSTA
                contexto_convertido = {}
                for key_str, valor in dados.items():
                    try:
                        key_int = int(key_str)
                        valor_convertido = {}
                        for k_str, v in valor.items():
                            try:
                                k_int = int(k_str)
                                valor_convertido[k_int] = v
                            except (ValueError, TypeError):
                                continue
                        contexto_convertido[key_int] = valor_convertido
                    except (ValueError, TypeError):
                        continue
                
                self.context_history = contexto_convertido
                logging.info(f"📂 CONTEXTO CARREGADO: {len(self.context_history)} contextos, {self.get_total_transicoes()} transições")
                
                # ANALISAR PADRÕES ÓBVIOS AO CARREGAR
                self.analisar_padroes_obvios()
                
            else:
                logging.info("🆕 Criando novo contexto histórico")
                self.context_history = {}
        except Exception as e:
            logging.error(f"❌ Erro ao carregar contexto: {e}")
            self.context_history = {}

    def analisar_padroes_obvios(self):
        """Identifica padrões óbvios que se repetem frequentemente"""
        padroes_fortes = []
        
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                # Encontrar transições que ocorrem MUITO frequentemente
                total_transicoes = sum(seguintes.values())
                for numero, count in seguintes.items():
                    probabilidade = count / total_transicoes
                    
                    # PADRÕES ÓBVIOS: probabilidade > 30% ou ocorrências > 10
                    if probabilidade > 0.3 or count > 10:
                        padroes_fortes.append({
                            'anterior': anterior,
                            'proximo': numero,
                            'probabilidade': probabilidade,
                            'ocorrencias': count
                        })
        
        if padroes_fortes:
            logging.info(f"🎯 PADRÕES ÓBVIOS DETECTADOS: {len(padroes_fortes)}")
            for padrao in sorted(padroes_fortes, key=lambda x: x['probabilidade'], reverse=True)[:5]:
                logging.info(f"   {padrao['anterior']} → {padrao['proximo']} ({padrao['probabilidade']:.1%}, {padrao['ocorrencias']}x)")

    def get_total_transicoes(self):
        """Calcula total de transições"""
        return sum(sum(seguintes.values()) for seguintes in self.context_history.values())
    
    def salvar_contexto(self):
        """Salva contexto histórico no arquivo"""
        try:
            with open(self.arquivo_contexto, "w") as f:
                json.dump(self.context_history, f, indent=2)
            logging.info(f"💾 CONTEXTO SALVO: {len(self.context_history)} contextos, {self.get_total_transicoes()} transições")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar contexto: {e}")
    
    def atualizar_contexto_aprendizado_ativo(self, numero_anterior, numero_atual):
        """Atualização de contexto com aprendizado ativo"""
        try:
            if numero_anterior is None or numero_atual is None:
                return
                
            # ATUALIZAR CONTEXTO
            if numero_anterior not in self.context_history:
                self.context_history[numero_anterior] = {}
            
            self.context_history[numero_anterior][numero_atual] = \
                self.context_history[numero_anterior].get(numero_atual, 0) + 1
            
            # APRENDIZADO ATIVO: Reforçar padrões quando detectados
            self.reforcar_padroes_detectados(numero_anterior, numero_atual)
            
            # SALVAR CONTEXTO
            self.salvar_contexto()
            
            logging.debug(f"🔄 Contexto atualizado: {numero_anterior} → {numero_atual}")
            
        except Exception as e:
            logging.error(f"Erro ao atualizar contexto: {e}")

    def reforcar_padroes_detectados(self, anterior, atual):
        """Reforça padrões quando detecta repetição"""
        # Se esta transição já existe, aumentar peso
        if anterior in self.context_history and atual in self.context_history[anterior]:
            count_atual = self.context_history[anterior][atual]
            
            # Reforçar se é um padrão que está se formando
            if count_atual >= 3:
                # Aumentar um pouco mais para padrões emergentes
                self.context_history[anterior][atual] += 1
                logging.info(f"🎯 REFORÇANDO PADRÃO: {anterior} → {atual} ({count_atual + 1}x)")

    def prever_por_contexto_forte(self, ultimo_numero, top_n=8):
        """Previsão FORTE - foca nos padrões óbvios"""
        try:
            if ultimo_numero in self.context_history:
                contexto = self.context_history[ultimo_numero]
                
                if contexto:
                    total_ocorrencias = sum(contexto.values())
                    
                    # FILTRAR APENAS PADRÕES FORTES
                    padroes_fortes = []
                    for num, count in contexto.items():
                        prob = count / total_ocorrencias
                        # CRITÉRIOS MAIS RIGOROSOS PARA PADRÕES FORTES
                        if prob > 0.2 or count >= 5:  # 20%+ de probabilidade OU 5+ ocorrências
                            padroes_fortes.append((num, count, prob))
                    
                    # Ordenar por probabilidade (mais importante que frequência absoluta)
                    padroes_fortes.sort(key=lambda x: (x[2], x[1]), reverse=True)
                    
                    previsao = []
                    for num, count, prob in padroes_fortes[:top_n]:
                        previsao.append(num)
                    
                    if previsao:
                        logging.info(f"🎯 CONTEXTO FORTE: {ultimo_numero} → {previsao} (prob: {prob:.1%})")
                        return previsao
            
            # FALLBACK: usar padrões gerais se não há contexto forte
            return self.get_previsao_inteligente_fallback(ultimo_numero, top_n)
            
        except Exception as e:
            logging.error(f"Erro na previsão por contexto forte: {e}")
            return self.get_previsao_inteligente_fallback(ultimo_numero, top_n)

    def get_previsao_inteligente_fallback(self, numero, quantidade):
        """Fallback INTELIGENTE baseado em múltiplas estratégias"""
        previsao = set()
        
        # ESTRATÉGIA 1: NÚMEROS MAIS FREQUENTES NO CONTEXTO GERAL
        numeros_mais_frequentes = self.get_numeros_mais_frequentes_global()
        for num in numeros_mais_frequentes[:quantidade//2]:
            previsao.add(num)
        
        # ESTRATÉGIA 2: VIZINHOS FÍSICOS FORTES
        vizinhos_fortes = self.get_vizinhos_fortes(numero)
        for vizinho in vizinhos_fortes[:quantidade//3]:
            previsao.add(vizinho)
        
        # ESTRATÉGIA 3: PADRÕES DE SEQUÊNCIA DETECTADOS
        padroes_sequencia = self.detectar_padroes_sequencia(numero)
        for num in padroes_sequencia[:quantidade//4]:
            previsao.add(num)
        
        # Completar se necessário
        if len(previsao) < quantidade:
            todos_numeros = list(range(0, 37))
            random.shuffle(todos_numeros)
            for num in todos_numeros:
                if len(previsao) < quantidade:
                    previsao.add(num)
        
        return list(previsao)[:quantidade]

    def get_numeros_mais_frequentes_global(self):
        """Retorna números mais frequentes em TODO o contexto"""
        frequencia_global = Counter()
        
        for anterior, seguintes in self.context_history.items():
            for numero, count in seguintes.items():
                frequencia_global[numero] += count
        
        return [num for num, count in frequencia_global.most_common(15)]

    def get_vizinhos_fortes(self, numero):
        """Retorna vizinhos físicos que têm histórico forte"""
        vizinhos = obter_vizinhos_fisicos(numero)
        vizinhos_fortes = []
        
        for vizinho in vizinhos:
            # Verificar se este vizinho tem padrões fortes no contexto
            if vizinho in self.context_history:
                contexto_vizinho = self.context_history[vizinho]
                if contexto_vizinho:
                    total = sum(contexto_vizinho.values())
                    # Considerar forte se tem alguma transição com > 15% de probabilidade
                    for num, count in contexto_vizinho.items():
                        if count / total > 0.15:
                            vizinhos_fortes.append(vizinho)
                            break
        
        return vizinhos_fortes if vizinhos_fortes else vizinhos

    def detectar_padroes_sequencia(self, numero):
        """Detecta padrões de sequência no contexto"""
        padroes = []
        
        # Procurar sequências do tipo: A → B → C
        for contexto_anterior, transicoes in self.context_history.items():
            if numero in transicoes and contexto_anterior in self.context_history:
                # Se temos A → B (contexto_anterior → numero) e B → C (numero → ?)
                transicoes_de_numero = self.context_history.get(numero, {})
                for proximo, count in transicoes_de_numero.items():
                    prob = count / sum(transicoes_de_numero.values()) if transicoes_de_numero else 0
                    if prob > 0.2:  # Sequência forte
                        padroes.append(proximo)
        
        return padroes

    def get_estatisticas_contexto(self):
        """Estatísticas do contexto"""
        total_transicoes = self.get_total_transicoes()
        
        # Número mais frequente globalmente
        frequencia_global = self.get_numeros_mais_frequentes_global()
        numero_mais_frequente = frequencia_global[0] if frequencia_global else "Nenhum"
        
        # Exemplo de previsão
        previsao_exemplo = self.get_exemplo_previsao_corrigido()
        
        return {
            'contextos_ativos': len(self.context_history),
            'total_transicoes': total_transicoes,
            'min_occurrences': self.min_occurrences,
            'numero_mais_frequente': numero_mais_frequente,
            'previsao_exemplo': previsao_exemplo
        }
    
    def get_exemplo_previsao_corrigido(self):
        """Exemplo de previsão"""
        if not self.context_history:
            return "Aguardando dados..."
        
        # Pegar um contexto que tenha previsões
        for contexto_num in list(self.context_history.keys())[-5:]:
            if self.context_history[contexto_num]:
                previsao = self.prever_por_contexto_forte(contexto_num, 8)
                if previsao:
                    return f"Após {contexto_num} → {previsao}"
        
        return "Sem padrões suficientes"

# =============================
# SISTEMA DE ROTAÇÃO DINÂMICA CONSERVADOR
# =============================
class Dynamic_Rotator_Conservador:
    def __init__(self):
        self.ultimas_previsoes = deque(maxlen=10)
        self.contador_estabilidade = 0
        
    def aplicar_rotacao_estrategica(self, previsao_base, historico):
        """Aplica rotação dinâmica MAIS CONSERVADORA"""
        try:
            if len(previsao_base) != 15:
                return previsao_base
                
            # Verificar se precisa de variação (MAIS CONSERVADOR)
            if self.deve_aplicar_rotacao(previsao_base):
                return self.rotacionar_previsao_conservador(previsao_base, historico)
            else:
                return previsao_base
                
        except Exception as e:
            logging.error(f"Erro na rotação dinâmica: {e}")
            return previsao_base
    
    def deve_aplicar_rotacao(self, previsao_atual):
        """Decide se deve rotacionar - MAIS CONSERVADOR"""
        if not self.ultimas_previsoes:
            self.ultimas_previsoes.append(previsao_atual)
            return False
            
        # Verificar similaridade com previsões anteriores
        similaridade = self.calcular_similaridade(previsao_atual, self.ultimas_previsoes[-1])
        
        # Aumentar limite para 85% e exigir 3 rodadas estáveis
        if similaridade > 0.85:
            self.contador_estabilidade += 1
        else:
            self.contador_estabilidade = 0
            
        # Rotacionar apenas se estável por 3 rodadas ou mais
        deve_rotacionar = self.contador_estabilidade >= 3
        
        self.ultimas_previsoes.append(previsao_atual)
        return deve_rotacionar
    
    def calcular_similaridade(self, previsao1, previsao2):
        """Calcula similaridade entre duas previsões"""
        set1 = set(previsao1)
        set2 = set(previsao2)
        return len(set1 & set2) / len(set1 | set2)
    
    def rotacionar_previsao_conservador(self, previsao_base, historico):
        """Aplica rotação MAIS CONSERVADORA na previsão"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return previsao_base
            
        # Estratégias de rotação MAIS CONSERVADORAS
        nova_previsao = self.rotacao_por_frequencia_conservador(previsao_base, numeros)
        nova_previsao = self.rotacao_por_vizinhanca_conservador(nova_previsao, numeros)
        
        logging.info(f"🔄 ROTAÇÃO CONSERVADORA APLICADA")
        return nova_previsao
    
    def rotacao_por_frequencia_conservador(self, previsao_base, numeros):
        """Rotaciona baseado na frequência recente - MAIS CONSERVADOR"""
        # Analisar frequência dos últimos 30 números
        freq_recente = Counter(numeros[-30:])
        
        # Encontrar números frequentes não presentes na previsão
        numeros_quentes = [num for num, count in freq_recente.most_common(8) 
                          if num not in previsao_base and count >= 2]
        
        if numeros_quentes:
            # Substituir apenas 1 número de menor frequência na previsão
            freq_na_previsao = {num: freq_recente.get(num, 0) for num in previsao_base}
            para_remover = sorted(freq_na_previsao.items(), key=lambda x: x[1])[:1]
            
            nova_previsao = previsao_base.copy()
            for num_remover, _ in para_remover:
                if numeros_quentes and num_remover in nova_previsao:
                    nova_previsao.remove(num_remover)
                    novo_num = numeros_quentes[0]
                    nova_previsao.append(novo_num)
            
            return nova_previsao
        
        return previsao_base
    
    def rotacao_por_vizinhanca_conservador(self, previsao_base, numeros):
        """Rotaciona baseado em vizinhança física - MAIS CONSERVADOR"""
        # Focar nos últimos 3 números sorteados
        ultimos_numeros = numeros[-3:]
        
        vizinhos_estrategicos = set()
        for num in ultimos_numeros:
            vizinhos = obter_vizinhos_fisicos(num)
            vizinhos_estrategicos.update(vizinhos)
        
        # Filtrar vizinhos não presentes na previsão
        vizinhos_novos = [v for v in vizinhos_estrategicos if v not in previsao_base]
        
        if vizinhos_novos:
            # Substituir apenas 1 número por um vizinho estratégico
            nova_previsao = previsao_base.copy()
            
            # Remover um número menos promissor (que não é zero e não está nos últimos)
            numeros_para_remover = [num for num in nova_previsao 
                                  if num not in ultimos_numeros and num != 0]
            
            if numeros_para_remover:
                num_remover = numeros_para_remover[0]
                nova_previsao.remove(num_remover)
                nova_previsao.append(vizinhos_novos[0])
                
            return nova_previsao
        
        return previsao_base

# =============================
# SISTEMA ESPECIALISTA 450+ COM ROTAÇÃO CONSERVADORA
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
            if len(numeros) >= tamanho * 3:
                ciclos_detectados = []
                
                for i in range(len(numeros) - tamanho * 2):
                    ciclo1 = numeros[i:i+tamanho]
                    ciclo2 = numeros[i+tamanho:i+tamanho*2]
                    
                    # Similaridade mais sofisticada
                    similaridade = self.calcular_similaridade_avancada(ciclo1, ciclo2)
                    
                    if similaridade > 0.35:
                        proximo_ciclo = numeros[i+tamanho*2:i+tamanho*3] if i+tamanho*3 <= len(numeros) else []
                        
                        ciclos_detectados.append({
                            'posicao_inicial': i,
                            'similaridade': similaridade,
                            'tamanho': tamanho,
                            'proximo_ciclo': proximo_ciclo[:5] if proximo_ciclo else [],
                            'numeros_comuns': list(set(ciclo1) & set(ciclo2))[:8]
                        })
                
                if ciclos_detectados:
                    ciclos[f'ciclo_{tamanho}'] = ciclos_detectados[:3]
        
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
            if count >= len(numeros) * 0.02:
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
                if len(numeros) >= 10:
                    contagem = Counter(numeros)
                    mais_comum, freq = contagem.most_common(1)[0]
                    if freq >= len(numeros) * 0.3:
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
            if len(resultados) >= 5:
                contagem = Counter(resultados)
                mais_comum, freq = contagem.most_common(1)[0]
                if freq >= len(resultados) * 0.4:
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
        self.dynamic_rotator = Dynamic_Rotator_Conservador()
        self.ultima_previsao_base = None
        
    def prever_com_historio_longo(self, historico):
        """Sistema especializado com rotação dinâmica CONSERVADORA"""
        historico_size = len(historico)
        
        if historico_size >= MIN_HISTORICO_TREINAMENTO:
            logging.info(f"🚀 ATIVANDO MODO ESPECIALISTA - {historico_size} REGISTROS")
            
            # 1. Análise profunda de padrões
            analise_profunda = self.pattern_analyzer.analisar_padroes_profundos(historico)
            
            # 2. Predição especializada
            probs_xgb = self.xgb_especialista.predict_com_450_plus(historico)
            
            # 3. Combinação inteligente
            previsao_base = self.combinar_previsoes_especialistas_corrigida(analise_profunda, probs_xgb, historico)
            
            # 4. APLICAR ROTAÇÃO DINÂMICA CONSERVADORA
            previsao_final = self.dynamic_rotator.aplicar_rotacao_estrategica(previsao_base, historico)
            self.ultima_previsao_base = previsao_base
            
            logging.info(f"🎯 ESPECIALISTA + ROTAÇÃO CONSERVADORA: {analise_profunda['total_padroes']} padrões → {len(previsao_final)} números")
            return previsao_final
        else:
            return self.prever_com_historio_normal_melhorado(historico)

    def combinar_previsoes_especialistas_corrigida(self, analise_profunda, probs_xgb, historico):
        """Combinação CORRIGIDA - MAIS CONSERVADORA E FOCADA"""
        scores_finais = {}
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # ESTRATÉGIA PRINCIPAL: NÚMEROS RECENTES E FREQUENTES (60% de peso)
        ultimos_30 = numeros[-30:] if len(numeros) >= 30 else numeros
        freq_recente = Counter(ultimos_30)
        
        for num, count in freq_recente.items():
            if count >= 2:
                scores_finais[num] = count * 0.3
        
        # ESTRATÉGIA SECUNDÁRIA: VIZINHANÇA FÍSICA (25% de peso)
        ultimos_5 = numeros[-5:] if len(numeros) >= 5 else numeros
        vizinhos_estrategicos = set()
        
        for num in ultimos_5:
            vizinhos = obter_vizinhos_fisicos(num)
            vizinhos_estrategicos.update(vizinhos)
        
        for vizinho in vizinhos_estrategicos:
            scores_finais[vizinho] = scores_finais.get(vizinho, 0) + 0.15
        
        # ESTRATÉGIA TERCIÁRIA: CORRELAÇÕES FORTES (15% de peso)
        correlacoes = analise_profunda.get('correlacoes', {})
        for par, info in correlacoes.items():
            if info['probabilidade'] > 0.1:
                for num in par:
                    scores_finais[num] = scores_finais.get(num, 0) + info['probabilidade'] * 0.1
        
        # GARANTIR SELECÃO DE ALTA QUALIDADE
        return self.selecionar_melhores_numeros(scores_finais, historico)

    def selecionar_melhores_numeros(self, scores_finais, historico):
        """Seleção MAIS INTELIGENTE dos melhores números"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # Ordenar por score
        top_numeros = sorted(scores_finais.items(), key=lambda x: x[1], reverse=True)
        
        # FASE 1: Pegar os 10 melhores por score
        selecao = [num for num, score in top_numeros[:10]]
        
        # FASE 2: Adicionar 3 números estratégicos
        analise = analisar_duzias_colunas(historico)
        selecao.extend(self.adicionar_numeros_estrategicos(analise, selecao))
        
        # FASE 3: Adicionar 2 números de fallback inteligente
        selecao.extend(self.adicionar_fallback_inteligente(numeros, selecao))
        
        # Garantir zero se não estiver presente
        if 0 not in selecao and len(selecao) < NUMERO_PREVISOES:
            selecao.append(0)
        
        # FASE 4: APLICAR BALANCEAMENTO FINAL
        selecao_balanceada = self.otimizar_balanceamento_final(selecao)
        
        return selecao_balanceada[:NUMERO_PREVISOES]

    def otimizar_balanceamento_final(self, selecao):
        """Otimização FINAL para melhor distribuição entre dúzias"""
        if len(selecao) != NUMERO_PREVISOES:
            return selecao
        
        # Contar distribuição atual
        contagem_duzias = {1: 0, 2: 0, 3: 0}
        for num in selecao:
            if 1 <= num <= 12:
                contagem_duzias[1] += 1
            elif 13 <= num <= 24:
                contagem_duzias[2] += 1
            elif 25 <= num <= 36:
                contagem_duzias[3] += 1
        
        # Meta ideal: 5 números por dúzia + zero
        meta_por_duzia = 5
        
        selecao_balanceada = selecao.copy()
        
        # Ajustar 2ª Dúzia (13-24) se necessário
        if contagem_duzias[2] < 4:
            numeros_faltantes_2 = [n for n in SEGUNDA_DUZIA if n not in selecao_balanceada]
            necessarios = min(meta_por_duzia - contagem_duzias[2], len(numeros_faltantes_2))
            for i in range(necessarios):
                if numeros_faltantes_2:
                    # Remover um excesso da 1ª dúzia se possível
                    excesso_1 = [n for n in selecao_balanceada if n in PRIMEIRA_DUZIA and n not in [0]]
                    if excesso_1 and contagem_duzias[1] > meta_por_duzia:
                        num_remover = excesso_1[0]
                        selecao_balanceada.remove(num_remover)
                        contagem_duzias[1] -= 1
                    
                    # Adicionar da 2ª dúzia
                    num_adicionar = numeros_faltantes_2[i]
                    selecao_balanceada.append(num_adicionar)
                    contagem_duzias[2] += 1
        
        # Ajustar 3ª Dúzia (25-36) se necessário
        if contagem_duzias[3] < 4:
            numeros_faltantes_3 = [n for n in TERCEIRA_DUZIA if n not in selecao_balanceada]
            necessarios = min(meta_por_duzia - contagem_duzias[3], len(numeros_faltantes_3))
            for i in range(necessarios):
                if numeros_faltantes_3:
                    # Remover um excesso da 1ª dúzia se possível
                    excesso_1 = [n for n in selecao_balanceada if n in PRIMEIRA_DUZIA and n not in [0]]
                    if excesso_1 and contagem_duzias[1] > meta_por_duzia:
                        num_remover = excesso_1[0]
                        selecao_balanceada.remove(num_remover)
                        contagem_duzias[1] -= 1
                    
                    # Adicionar da 3ª dúzia
                    num_adicionar = numeros_faltantes_3[i]
                    selecao_balanceada.append(num_adicionar)
                    contagem_duzias[3] += 1
        
        # Garantir zero
        if 0 not in selecao_balanceada:
            # Remover um número menos estratégico (excesso da 1ª dúzia)
            excesso_1 = [n for n in selecao_balanceada if n in PRIMEIRA_DUZIA and n not in [0]]
            if excesso_1:
                selecao_balanceada.remove(excesso_1[0])
            selecao_balanceada.append(0)
        
        return selecao_balanceada[:NUMERO_PREVISOES]

    def adicionar_numeros_estrategicos(self, analise, selecao_atual):
        """Adiciona números baseado em análise de dúzias/colunas"""
        estrategicos = []
        
        duzias_quentes = analise.get("duzias_quentes", [])
        colunas_quentes = analise.get("colunas_quentes", [])
        
        # Focar em balancear as dúzias que estão faltando
        contagem_atual = {1: 0, 2: 0, 3: 0}
        for num in selecao_atual:
            if 1 <= num <= 12:
                contagem_atual[1] += 1
            elif 13 <= num <= 24:
                contagem_atual[2] += 1
            elif 25 <= num <= 36:
                contagem_atual[3] += 1
        
        # Priorizar dúzias que estão com menos representação
        duzias_prioritarias = sorted([1, 2, 3], key=lambda d: contagem_atual[d])
        
        for duzia in duzias_prioritarias[:2]:
            if duzia == 1:
                numeros_duzia = PRIMEIRA_DUZIA
            elif duzia == 2:
                numeros_duzia = SEGUNDA_DUZIA
            else:
                numeros_duzia = TERCEIRA_DUZIA
            
            # Adicionar números centrais da dúzia
            numeros_centrais = numeros_duzia[3:9]
            for num in numeros_centrais:
                if num not in selecao_atual and num not in estrategicos:
                    estrategicos.append(num)
                    if len(estrategicos) >= 3:
                        return estrategicos
                    break
        
        return estrategicos[:3]

    def adicionar_fallback_inteligente(self, numeros, selecao_atual):
        """Fallback inteligente baseado em padrões dos últimos 20 números"""
        fallback = []
        
        if len(numeros) < 10:
            return fallback
        
        # Analisar padrões recentes
        padroes = analisar_padroes_ultimos_20([{'number': n} for n in numeros])
        
        # 1. Adicionar números que se repetem em padrão de 3-4 rodadas
        for num in padroes.get('repetidos_3_rodadas', [])[:2]:
            if num not in selecao_atual and num not in fallback:
                fallback.append(num)
                if len(fallback) >= 2:
                    return fallback
        
        # 2. Se há alta alternância de cores, adicionar números da cor oposta ao último
        if padroes.get('alternancia_cores', 0) > 0.6 and numeros:
            ultimo_numero = numeros[-1]
            ultima_cor_vermelha = ultimo_numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
            
            # Adicionar 1 número da cor oposta
            if ultima_cor_vermelha:
                # Adicionar preto
                pretos = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
                for preto in pretos:
                    if preto not in selecao_atual and preto not in fallback:
                        fallback.append(preto)
                        break
            else:
                # Adicionar vermelho
                vermelhos = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
                for vermelho in vermelhos:
                    if vermelho not in selecao_atual and vermelho not in fallback:
                        fallback.append(vermelho)
                        break
        
        return fallback[:2]

    def prever_com_historio_normal_melhorado(self, historico):
        """Estratégia MELHORADA para histórico menor"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 15:
            return self.estrategia_conservadora_inicial()
        
        # ESTRATÉGIA SIMPLES MAS EFETIVA
        previsao = set()
        
        # 1. Números mais frequentes nos últimos 20 (40%)
        freq_20 = Counter(numeros[-20:])
        for num, count in freq_20.most_common(6):
            if count >= 2:
                previsao.add(num)
        
        # 2. Últimos 5 números (30%)
        previsao.update(numeros[-5:])
        
        # 3. Vizinhança dos últimos 3 números (20%)
        for num in numeros[-3:]:
            vizinhos = obter_vizinhos_fisicos(num)
            previsao.update(vizinhos[:2])
        
        # 4. Números estratégicos (10%)
        estrategicos = [0, 2, 5, 8, 11, 17, 20, 26, 29, 32, 35]
        for num in estrategicos:
            if len(previsao) < NUMERO_PREVISOES:
                previsao.add(num)
        
        return list(previsao)[:NUMERO_PREVISOES]

    def estrategia_conservadora_inicial(self):
        """Estratégia inicial MAIS CONSERVADORA"""
        # Números estrategicamente distribuídos na roleta
        numeros_estrategicos = [
            # Centro das três dúzias + zero
            5, 6, 7, 8,				# 1ª dúzia
            17, 18, 19, 20,		# 2ª dúzia  
            29, 30, 31, 32,		# 3ª dúzia
            0, 2, 11				# Zero + bordas estratégicas
        ]
        return validar_previsao(numeros_estrategicos)[:NUMERO_PREVISOES]

# =============================
# GESTOR PRINCIPAL CORRIGIDO - CAPTURA PADRÕES ÓBVIOS
# =============================
class GestorHybridIA_Especialista_Corrigido:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_450_Plus_Corrigido()
        self.context_predictor = Context_Predictor_Persistente_Corrigido()  # USAR VERSÃO CORRIGIDA
        self.historico = deque(carregar_historico(), maxlen=1000)
        self.previsao_anterior = None
        self.ultimo_numero_processado = None
        self.padroes_detectados = []  # RASTREAR PADRÕES DETECTADOS
        
        self.inicializar_contexto_com_historico()

    def inicializar_contexto_com_historico(self):
        """Inicialização MAIS INTELIGENTE do contexto"""
        try:
            if len(self.historico) > 1:
                numeros = [h['number'] for h in self.historico if h.get('number') is not None]
                transicoes_adicionadas = 0
                
                for i in range(1, len(numeros)):
                    self.context_predictor.atualizar_contexto_aprendizado_ativo(numeros[i-1], numeros[i])
                    transicoes_adicionadas += 1
                
                logging.info(f"🚀 CONTEXTO INICIALIZADO: {transicoes_adicionadas} transições")
                
        except Exception as e:
            logging.error(f"Erro na inicialização do contexto: {e}")

    def adicionar_numero(self, numero_dict):
        """Adiciona número com análise de padrões em tempo real"""
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            numero_atual = numero_dict['number']
            
            # ANALISAR PADRÃO ANTES DE ATUALIZAR
            if self.ultimo_numero_processado is not None:
                self.analisar_padrao_em_tempo_real(self.ultimo_numero_processado, numero_atual)
                
                # ATUALIZAR CONTEXTO
                self.context_predictor.atualizar_contexto_aprendizado_ativo(
                    self.ultimo_numero_processado, 
                    numero_atual
                )
            
            self.ultimo_numero_processado = numero_atual
            self.historico.append(numero_dict)

    def analisar_padrao_em_tempo_real(self, anterior, atual):
        """Analisa padrões em tempo real para detecção imediata"""
        # Verificar se é um padrão que já foi visto
        if anterior in self.context_predictor.context_history:
            transicoes = self.context_predictor.context_history[anterior]
            if atual in transicoes:
                count = transicoes[atual]
                total = sum(transicoes.values())
                probabilidade = count / total if total > 0 else 0
                
                # LOGAR PADRÕES FORTES
                if probabilidade > 0.25 or count >= 3:
                    logging.info(f"🎯 PADRÃO CONFIRMADO: {anterior} → {atual} ({probabilidade:.1%}, {count}x)")
                    
                    # Adicionar à lista de padrões detectados
                    padrao = {
                        'anterior': anterior,
                        'atual': atual,
                        'probabilidade': probabilidade,
                        'ocorrencias': count
                    }
                    self.padroes_detectados.append(padrao)
                    
                    # Manter apenas os últimos 20 padrões
                    self.padroes_detectados = self.padroes_detectados[-20:]

    def gerar_previsao_contextual_forte(self):
        """Gera previsão com FOCO NOS PADRÕES FORTES"""
        try:
            # 1. PRIMEIRO: PREVISÃO POR CONTEXTO FORTE
            previsao_contexto = []
            if self.ultimo_numero_processado is not None:
                previsao_contexto = self.context_predictor.prever_por_contexto_forte(
                    self.ultimo_numero_processado, 
                    top_n=10
                )
            
            # 2. SEGUNDO: PREVISÃO DA IA (como complemento)
            previsao_ia = self.hybrid_system.prever_com_historio_longo(self.historico)
            
            # 3. COMBINAÇÃO PRIORIZANDO CONTEXTO FORTE
            previsao_combinada = self.combinar_previsoes_focada_contexto(
                previsao_ia, 
                previsao_contexto
            )
            
            # 4. APLICAR ROTAÇÃO (mais conservadora)
            previsao_final = self.hybrid_system.dynamic_rotator.aplicar_rotacao_estrategica(
                previsao_combinada, 
                self.historico
            )
            
            logging.info(f"🎯 PREVISÃO CONTEXTUAL FORTE: Contexto({len(previsao_contexto)}) + IA({len(previsao_ia)}) → {len(previsao_final)} números")
            
            return previsao_final
            
        except Exception as e:
            logging.error(f"Erro na previsão contextual forte: {e}")
            return self.hybrid_system.prever_com_historio_longo(self.historico)

    def combinar_previsoes_focada_contexto(self, previsao_ia, previsao_contexto):
        """Combinação que PRIORIZA O CONTEXTO quando forte"""
        combinada = set()
        
        # SE CONTEXTO É FORTE, USAR COMO BASE
        if previsao_contexto and len(previsao_contexto) >= 6:
            logging.info("🎯 USANDO CONTEXTO COMO BASE (forte detectado)")
            for num in previsao_contexto:
                if len(combinada) < NUMERO_PREVISOES:
                    combinada.add(num)
        else:
            logging.info("🔄 Contexto fraco, usando IA como base")
            # Usar IA como base se contexto é fraco
            for num in previsao_ia[:10]:
                if len(combinada) < NUMERO_PREVISOES:
                    combinada.add(num)
        
        # COMPLETAR COM IA (se necessário)
        if len(combinada) < NUMERO_PREVISOES:
            for num in previsao_ia:
                if len(combinada) < NUMERO_PREVISOES:
                    combinada.add(num)
        
        # COMPLETAR COM ESTRATÉGIA CONSERVADORA
        return self.completar_para_15_inteligente(list(combinada))

    def completar_para_15_inteligente(self, previsao):
        """Completar usando padrões detectados"""
        if len(previsao) >= NUMERO_PREVISOES:
            return previsao[:NUMERO_PREVISOES]
        
        numeros_completos = set(previsao)
        
        # PRIMEIRO: Usar padrões detectados recentemente
        for padrao in self.padroes_detectados[-5:]:
            if padrao['probabilidade'] > 0.3:
                if padrao['atual'] not in numeros_completos:
                    numeros_completos.add(padrao['atual'])
                    if len(numeros_completos) >= NUMERO_PREVISOES:
                        break
        
        # SEGUNDO: Números estratégicos
        if len(numeros_completos) < NUMERO_PREVISOES:
            estrategicos = [0, 2, 5, 8, 11, 17, 20, 26, 29, 32, 35]
            for num in estrategicos:
                if num not in numeros_completos:
                    numeros_completos.add(num)
                    if len(numeros_completos) >= NUMERO_PREVISOES:
                        break
        
        return list(numeros_completos)[:NUMERO_PREVISOES]
    
    def get_analise_contexto_detalhada(self):
        """Análise detalhada dos padrões de contexto"""
        estatisticas = self.context_predictor.get_estatisticas_contexto()
        
        # Previsão contextual atual
        previsao_atual = []
        if self.ultimo_numero_processado is not None:
            previsao_atual = self.context_predictor.prever_por_contexto_forte(
                self.ultimo_numero_processado, 
                top_n=8
            )
        
        # Padrões detectados recentemente
        padroes_recentes = self.padroes_detectados[-5:] if self.padroes_detectados else []
        
        return {
            'contextos_ativos': estatisticas['contextos_ativos'],
            'total_transicoes': estatisticas['total_transicoes'],
            'ultimo_numero': self.ultimo_numero_processado,
            'previsao_contexto_atual': previsao_atual,
            'padroes_recentes': padroes_recentes,
            'numero_mais_frequente': estatisticas['numero_mais_frequente'],
            'previsao_exemplo': estatisticas['previsao_exemplo']
        }

    def gerar_previsao(self):
        """Método legado"""
        return self.gerar_previsao_contextual_forte()
        
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
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            
            if historico_size < FASE_INICIAL:
                return "🟡 Coletando Dados", "Estratégia Conservadora"
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

st.title("🎯 Hybrid IA System - ESPECIALISTA COM DETECÇÃO DE PADRÕES")
st.markdown("### **Sistema que Captura Padrões Óbvios do Contexto Histórico**")

st_autorefresh(interval=15000, key="refresh")

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
        acertou = False
        if previsao_valida:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
                # ENVIAR ALERTA DE GREEN
                enviar_alerta_resultado(True, numero_real, st.session_state.previsao_atual)
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")
                # ENVIAR ALERTA DE RED
                enviar_alerta_resultado(False, numero_real, st.session_state.previsao_atual)

        # GERAR NOVA PREVISÃO COM CONTEXTO FORTE
        nova_previsao = st.session_state.gestor.gerar_previsao_contextual_forte()
        
        # CALCULAR MUDANÇAS
        diferencas = st.session_state.gestor.calcular_diferencas(nova_previsao)
        st.session_state.previsao_anterior = st.session_state.previsao_atual.copy()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # ENVIAR ALERTA TELEGRAM - PREVISÃO PRINCIPAL
        if st.session_state.previsao_atual and len(st.session_state.previsao_atual) == 15:
            try:
                enviar_alerta_rapido(st.session_state.previsao_atual)
            except Exception as e:
                logging.error(f"Erro ao enviar alerta principal: {e}")

        # ENVIAR ALERTA TELEGRAM - PREVISÃO CONTEXTUAL (8 NÚMEROS)
        analise_contexto = st.session_state.gestor.get_analise_contexto_detalhada()
        previsao_contexto = analise_contexto.get('previsao_contexto_atual', [])
        if previsao_contexto and len(previsao_contexto) == 8:
            try:
                enviar_alerta_contextual(previsao_contexto)
            except Exception as e:
                logging.error(f"Erro ao enviar alerta contextual: {e}")

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

# NOVA SEÇÃO - PREVISÃO POR CONTEXTO HISTÓRICO COM PADRÕES
st.markdown("---")
st.subheader("🔮 PREVISÃO POR CONTEXTO HISTÓRICO - CAPTURA PADRÕES ÓBVIOS")

analise_contexto = st.session_state.gestor.get_analise_contexto_detalhada()

col1, col2, col3, col4 = st.columns(4)

with col1:
    ultimo_num = analise_contexto['ultimo_numero'] 
    st.metric("🎯 Último Número", ultimo_num if ultimo_num is not None else "-")

with col2:
    st.metric("📊 Contextos", analise_contexto['contextos_ativos'])

with col3:
    st.metric("🔄 Transições", analise_contexto['total_transicoes'])

with col4:
    st.metric("🔥 Mais Frequente", analise_contexto['numero_mais_frequente'])

# MOSTRAR PREVISÃO CONTEXTUAL ATUAL
previsao_contexto = analise_contexto['previsao_contexto_atual']
if previsao_contexto and analise_contexto['ultimo_numero'] is not None:
    previsao_unica = []
    numeros_vistos = set()
    for num in previsao_contexto:
        if num not in numeros_vistos:
            previsao_unica.append(num)
            numeros_vistos.add(num)
    
    if previsao_unica:
        st.success(f"**📈 8 NÚMEROS MAIS PROVÁVEIS APÓS {analise_contexto['ultimo_numero']}:**")
        
        # Mostrar com indicação de força
        if len(previsao_unica) >= 6:
            emoji = "🎯"
            força = "ALTA"
        elif len(previsao_unica) >= 4:
            emoji = "🔍" 
            força = "MÉDIA"
        else:
            emoji = "🔄"
            força = "BAIXA"
        
        # Dividir em 2 linhas de 4 números cada
        linha1 = previsao_unica[:4]
        linha2 = previsao_unica[4:8]
        
        linha1_str = " | ".join([f"**{num}**" for num in linha1])
        linha2_str = " | ".join([f"**{num}**" for num in linha2])
        
        st.markdown(f"### {emoji} {linha1_str}")
        st.markdown(f"### {emoji} {linha2_str}")
        st.caption(f"💡 **{força} CONFIANÇA** - Baseado em {analise_contexto['total_transicoes']} transições históricas")
        
        # MOSTRAR PADRÕES DETECTADOS RECENTEMENTE
        padroes_recentes = analise_contexto.get('padroes_recentes', [])
        if padroes_recentes:
            st.info("**🎯 PADRÕES DETECTADOS RECENTEMENTE:**")
            for padrao in padroes_recentes:
                st.write(f"`{padrao['anterior']} → {padrao['atual']}` ({padrao['probabilidade']:.1%}, {padrao['ocorrencias']}x)")

        # Exemplo de previsão de outro contexto
        if analise_contexto.get('previsao_exemplo'):
            st.info(f"**Exemplo de padrão:** {analise_contexto['previsao_exemplo']}")
        
        # Estatísticas rápidas
        with st.expander("📊 Estatísticas do Contexto"):
            st.write(f"**Contextos Ativos:** {analise_contexto['contextos_ativos']}")
            st.write(f"**Total de Transições:** {analise_contexto['total_transicoes']}")
            st.write(f"**Número Mais Frequente:** {analise_contexto['numero_mais_frequente']}")
            
else:
    st.info("🔄 Coletando dados contextuais... O sistema está aprendendo padrões.")
    
    # Mostrar progresso
    if analise_contexto['total_transicoes'] > 0:
        st.progress(min(100, analise_contexto['total_transicoes'] / 100))
        st.caption(f"📈 Progresso: {analise_contexto['total_transicoes']} transições analisadas")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL - SISTEMA COM DETECÇÃO DE PADRÕES")

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
with st.expander("🔧 Detalhes Técnicos do Sistema com Detecção de Padrões"):
    st.write("**🎯 ARQUITETURA COM DETECÇÃO ATIVA DE PADRÕES:**")
    
    if analise["modo_especialista"]:
        st.write("✅ **MODO ESPECIALISTA ATIVO**")
        st.write("- 🔍 Análise de Ciclos Complexos")
        st.write("- 📈 Correlações entre Números") 
        st.write("- 🕒 Padrões Temporais Avançados")
        st.write("- 🔄 Sequências de Alta Ordem")
        st.write("**🎯 DETECÇÃO DE PADRÕES ÓBVIOS:**")
        st.write("- 🔍 Identificação automática de padrões fortes")
        st.write("- 📊 Critérios rigorosos: >20% probabilidade ou 5+ ocorrências")
        st.write("- ⚡ Análise em tempo real")
        st.write("- 💪 Reforço de aprendizado ativo")
        st.write("**🔄 SISTEMA DE ROTAÇÃO CONSERVADOR:**")
        st.write("- 🎯 Rotação apenas após 3 rodadas estáveis")
        st.write("- 📍 Similaridade mínima de 85% para rotacionar")
        st.write("- ⚖️ Substituição máxima de 1-2 números")
    else:
        st.write("⏳ **AGUARDANDO DADOS SUFICIENTES**")
        st.write(f"- 📈 Progresso: {historico_atual}/{MIN_HISTORICO_TREINAMENTO}")
        st.write("- 🎯 Ativação automática em 450 registros")
        st.write("- 🔄 Coletando dados para análise profunda")
    
    # SEÇÃO DE CONTEXTO
    st.write("**🔮 SISTEMA DE CONTEXTO HISTÓRICO INTELIGENTE:**")
    st.write(f"- Contextos ativos: {analise_contexto['contextos_ativos']}")
    st.write(f"- Transições analisadas: {analise_contexto['total_transicoes']}")
    st.write(f"- Número mais frequente: {analise_contexto['numero_mais_frequente']}")
    
    if analise_contexto['previsao_contexto_atual']:
        st.write(f"- Previsão atual (8 números): {analise_contexto['previsao_contexto_atual']}")
    
    # Padrões detectados
    padroes_recentes = analise_contexto.get('padroes_recentes', [])
    if padroes_recentes:
        st.write("**🎯 PADRÕES RECENTES DETECTADOS:**")
        for padrao in padroes_recentes:
            st.write(f"   {padrao['anterior']} → {padrao['atual']} ({padrao['probabilidade']:.1%}, {padrao['ocorrencias']}x)")
    
    st.write("**📨 SISTEMA DE ALERTAS TELEGRAM:**")
    st.write("- 🔔 Alerta Principal: 15 números (formato 8+7)")
    st.write("- 🔔 Alerta Contextual: 8 números (formato 4+4)") 
    st.write("- 🟢 Alerta GREEN: Quando acerta o número")
    st.write("- 🔴 Alerta RED: Quando erra o número")
    
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
        nova_previsao = st.session_state.gestor.gerar_previsao_contextual_forte()
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
st.markdown("### 🚀 **Sistema Especialista com Detecção de Padrões Óbvios**")
st.markdown("*Captura padrões históricos que se repetem frequentemente*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Hybrid IA System v14.0** - *Especialista com Detecção Ativa de Padrões, Contexto Inteligente e Sistema Completo de Alertas*")
