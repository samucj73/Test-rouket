# RoletaHybridIA.py - SISTEMA ESPECIALISTA APENAS COM CONTEXTO HISTÓRICO
import streamlit as st
import json
import os
import time
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import random

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
CONTEXTO_PATH = "contexto_historico.json"
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

NUMERO_PREVISOES = 10

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# UTILITÁRIOS
# =============================
def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_alerta_previsao(numeros):
    """Envia alerta de PREVISÃO com 10 números em formato simples"""
    try:
        if not numeros or len(numeros) != 10:
            logging.error(f"❌ Alerta de previsão precisa de 10 números, recebeu: {len(numeros) if numeros else 0}")
            return
            
        # Ordena os números do menor para o maior
        numeros_ordenados = sorted(numeros)
        
        # Formata em UMA LINHA para a notificação do Telegram
        numeros_str = ' '.join(map(str, numeros_ordenados))
        mensagem = f"🎯 PREVISÃO: {numeros_str}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de PREVISÃO enviado: 10 números")
        
    except Exception as e:
        logging.error(f"Erro alerta previsão: {e}")

def enviar_alerta_resultado(acertou, numero_sorteado, previsao_anterior):
    """Envia alerta de resultado (GREEN/RED) com os 10 números da previsão"""
    try:
        if not previsao_anterior or len(previsao_anterior) != 10:
            logging.error(f"❌ Alerta resultado precisa de 10 números na previsão")
            return
            
        # Ordena os números da previsão anterior
        previsao_ordenada = sorted(previsao_anterior)
        previsao_str = ' '.join(map(str, previsao_ordenada))
        
        if acertou:
            mensagem = f"🟢 GREEN! Acertou {numero_sorteado} | Previsão: {previsao_str}"
        else:
            mensagem = f"🔴 RED! Sorteado {numero_sorteado} | Previsão: {previsao_str}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de resultado enviado")
        
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

# =============================
# CONTEXT PREDICTOR - ESTRATÉGIA PRINCIPAL ATUALIZADA
# =============================
class Context_Predictor_Persistente:
    def __init__(self):
        self.context_history = {}
        self.min_occurrences = 1
        self.arquivo_contexto = CONTEXTO_PATH
        self.padroes_fortes_cache = []  # Cache de padrões fortes
        self.carregar_contexto()
        
    def carregar_contexto(self):
        """Carrega contexto histórico"""
        try:
            if os.path.exists(self.arquivo_contexto):
                with open(self.arquivo_contexto, "r") as f:
                    dados = json.load(f)
                    
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
    
    def atualizar_contexto(self, numero_anterior, numero_atual):
        """Atualização de contexto"""
        try:
            if numero_anterior is None or numero_atual is None:
                return
                
            if numero_anterior not in self.context_history:
                self.context_history[numero_anterior] = {}
            
            self.context_history[numero_anterior][numero_atual] = \
                self.context_history[numero_anterior].get(numero_atual, 0) + 1
            
            self.salvar_contexto()
            
            logging.debug(f"🔄 Contexto atualizado: {numero_anterior} → {numero_atual}")
            
        except Exception as e:
            logging.error(f"Erro ao atualizar contexto: {e}")

    def prever_por_contexto_forte(self, ultimo_numero, top_n=10):
        """Previsão FORTE - com prioridade para padrões detectados"""
        try:
            previsao_final = set()
            
            # 1. PRIMEIRA PRIORIDADE: Padrões diretos do último número (40%)
            if ultimo_numero in self.context_history:
                contexto = self.context_history[ultimo_numero]
                
                if contexto:
                    total_ocorrencias = sum(contexto.values())
                    
                    # CRITÉRIOS MAIS INTELIGENTES
                    padroes_fortes = []
                    for num, count in contexto.items():
                        prob = count / total_ocorrencias
                        
                        # CRITÉRIOS MAIS FLEXÍVEIS PARA CAPTURAR PADRÕES
                        if (prob > 0.10 and count >= 2) or (prob > 0.05 and count >= 3) or count >= 4:
                            score = prob * 100 + min(count, 15)  # Bônus maior para ocorrências
                            padroes_fortes.append((num, count, prob, score))
                    
                    # Ordenar por score personalizado
                    padroes_fortes.sort(key=lambda x: x[3], reverse=True)
                    
                    for num, count, prob, score in padroes_fortes[:6]:  # Pegar até 6 dos melhores
                        previsao_final.add(num)
                        logging.info(f"🎯 PADRÃO INCLUÍDO: {ultimo_numero} → {num} ({prob:.1%}, {count}x)")
            
            # 2. SEGUNDA PRIORIDADE: Padrões detectados recentemente (30%)
            padroes_recentes = self.analisar_padroes_recentes_ativos()
            for padrao in padroes_recentes[:4]:  # Top 4 padrões recentes
                previsao_final.add(padrao['proximo'])
                logging.info(f"🔍 PADRÃO RECENTE INCLUÍDO: {padrao['anterior']} → {padrao['proximo']} ({padrao['probabilidade']:.1%})")
            
            # 3. TERCEIRA PRIORIDADE: Números quentes globais (20%)
            numeros_quentes = self.get_numeros_mais_frequentes_global(4)
            for num in numeros_quentes:
                previsao_final.add(num)
            
            # 4. QUARTA PRIORIDADE: Vizinhança física (10%)
            vizinhos = obter_vizinhos_fisicos(ultimo_numero)
            for vizinho in vizinhos[:2]:
                previsao_final.add(vizinho)
            
            # Converter para lista e completar se necessário
            resultado = list(previsao_final)
            
            if len(resultado) < top_n:
                # Completar com fallback inteligente
                faltam = top_n - len(resultado)
                complemento = self.get_fallback_inteligente(ultimo_numero, faltam)
                for num in complemento:
                    if num not in resultado:
                        resultado.append(num)
            
            logging.info(f"🎯 PREVISÃO FINAL: {ultimo_numero} → {resultado}")
            return resultado[:top_n]
            
        except Exception as e:
            logging.error(f"Erro na previsão por contexto forte: {e}")
            return self.get_fallback_inteligente(ultimo_numero, top_n)

    def analisar_padroes_recentes_ativos(self):
        """Analisa e retorna os padrões mais fortes e recentes"""
        padroes_fortes = []
        
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                total_transicoes = sum(seguintes.values())
                for proximo, count in seguintes.items():
                    probabilidade = count / total_transicoes
                    
                    # CRITÉRIOS PARA PADRÕES FORTES
                    if probabilidade > 0.03 and count >= 3:  # Mais flexível para capturar padrões
                        padroes_fortes.append({
                            'anterior': anterior,
                            'proximo': proximo,
                            'probabilidade': probabilidade,
                            'ocorrencias': count,
                            'score': probabilidade * 100 + min(count, 20)
                        })
        
        # Ordenar por score (probabilidade + ocorrências)
        padroes_fortes.sort(key=lambda x: x['score'], reverse=True)
        
        # Atualizar cache
        self.padroes_fortes_cache = padroes_fortes[:10]  # Manter top 10
        
        return padroes_fortes[:8]  # Retornar top 8 para uso imediato

    def get_padroes_fortes_para_previsao(self, ultimo_numero):
        """Retorna padrões fortes que podem ser relevantes para a previsão atual"""
        padroes_relevantes = []
        
        for padrao in self.padroes_fortes_cache:
            # Incluir padrões onde o anterior é o último número OU onde o próximo é frequente
            if padrao['anterior'] == ultimo_numero or padrao['ocorrencias'] >= 5:
                padroes_relevantes.append(padrao)
        
        return padroes_relevantes[:5]  # Top 5 mais relevantes

    def get_fallback_inteligente(self, ultimo_numero, quantidade):
        """Fallback mais inteligente baseado em múltiplos fatores"""
        numeros_fallback = set()
        
        # 1. VIZINHOS FÍSICOS (25% de peso)
        vizinhos = obter_vizinhos_fisicos(ultimo_numero)
        for vizinho in vizinhos[:4]:  # Top 4 vizinhos
            numeros_fallback.add(vizinho)
        
        # 2. NÚMEROS MAIS FREQUENTES GLOBALMENTE (35% de peso)
        frequencia_global = Counter()
        for anterior, seguintes in self.context_history.items():
            for numero, count in seguintes.items():
                frequencia_global[numero] += count
        
        for num, count in frequencia_global.most_common(5):
            numeros_fallback.add(num)
        
        # 3. PADRÕES RECORRENTES (25% de peso)
        padroes_recurrentes = self.detectar_padroes_recorrentes()
        for num in padroes_recurrentes[:4]:
            numeros_fallback.add(num)
        
        # 4. NÚMEROS ESTRATÉGICOS (15% de peso)
        estrategicos = [0, 2, 5, 8, 11, 17, 20, 26, 29, 32, 35]
        for num in estrategicos[:3]:
            numeros_fallback.add(num)
        
        # Converter para lista e completar se necessário
        resultado = list(numeros_fallback)
        
        if len(resultado) < quantidade:
            # Completar com números quentes recentes
            todos_numeros = list(range(0, 37))
            random.shuffle(todos_numeros)
            for num in todos_numeros:
                if num not in resultado:
                    resultado.append(num)
                if len(resultado) >= quantidade:
                    break
        
        return resultado[:quantidade]

    def detectar_padroes_recorrentes(self):
        """Detecta números que aparecem em múltiplos contextos"""
        aparicoes = Counter()
        
        for contexto_num, transicoes in self.context_history.items():
            for numero, count in transicoes.items():
                # Peso maior para números que aparecem em múltiplos contextos
                if count >= 2:
                    aparicoes[numero] += 1
        
        return [num for num, count in aparicoes.most_common(12)]

    def get_numeros_mais_frequentes_global(self, quantidade):
        """Retorna números mais frequentes em TODO o contexto"""
        frequencia_global = Counter()
        
        for anterior, seguintes in self.context_history.items():
            for numero, count in seguintes.items():
                frequencia_global[numero] += count
        
        numeros_mais_frequentes = [num for num, count in frequencia_global.most_common(quantidade)]
        
        # Se não há números suficientes, completar aleatoriamente
        if len(numeros_mais_frequentes) < quantidade:
            todos_numeros = list(range(0, 37))
            random.shuffle(todos_numeros)
            for num in todos_numeros:
                if num not in numeros_mais_frequentes:
                    numeros_mais_frequentes.append(num)
                if len(numeros_mais_frequentes) >= quantidade:
                    break
        
        return numeros_mais_frequentes[:quantidade]

    def get_estatisticas_contexto(self):
        """Estatísticas do contexto"""
        total_transicoes = self.get_total_transicoes()
        
        frequencia_global = self.get_numeros_mais_frequentes_global(1)
        numero_mais_frequente = frequencia_global[0] if frequencia_global else "Nenhum"
        
        return {
            'contextos_ativos': len(self.context_history),
            'total_transicoes': total_transicoes,
            'numero_mais_frequente': numero_mais_frequente
        }

# =============================
# GESTOR PRINCIPAL ATUALIZADO
# =============================
class GestorContextoHistorico:
    def __init__(self):
        self.context_predictor = Context_Predictor_Persistente()
        self.historico = deque(carregar_historico(), maxlen=1000)
        self.previsao_anterior = None
        self.ultimo_numero_processado = None
        self.padroes_detectados = []
        
        self.inicializar_contexto_com_historico()

    def inicializar_contexto_com_historico(self):
        """Inicialização do contexto com histórico existente"""
        try:
            if len(self.historico) > 1:
                numeros = [h['number'] for h in self.historico if h.get('number') is not None]
                transicoes_adicionadas = 0
                
                for i in range(1, len(numeros)):
                    self.context_predictor.atualizar_contexto(numeros[i-1], numeros[i])
                    transicoes_adicionadas += 1
                
                logging.info(f"🚀 CONTEXTO INICIALIZADO: {transicoes_adicionadas} transições")
                
        except Exception as e:
            logging.error(f"Erro na inicialização do contexto: {e}")

    def adicionar_numero(self, numero_dict):
        """Adiciona número com análise de padrões"""
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            numero_atual = numero_dict['number']
            
            # ANALISAR PADRÃO ANTES DE ATUALIZAR
            if self.ultimo_numero_processado is not None:
                self.analisar_padrao_em_tempo_real(self.ultimo_numero_processado, numero_atual)
                
                # ATUALIZAR CONTEXTO
                self.context_predictor.atualizar_contexto(
                    self.ultimo_numero_processado, 
                    numero_atual
                )
            
            self.ultimo_numero_processado = numero_atual
            self.historico.append(numero_dict)

    def analisar_padrao_em_tempo_real(self, anterior, atual):
        """Analisa padrões em tempo real e os inclui na previsão"""
        if anterior in self.context_predictor.context_history:
            transicoes = self.context_predictor.context_history[anterior]
            if atual in transicoes:
                count = transicoes[atual]
                total = sum(transicoes.values())
                probabilidade = count / total if total > 0 else 0
                
                # LOGAR E REGISTRAR PADRÕES FORTES
                if probabilidade > 0.03 and count >= 2:  # Critério mais sensível
                    logging.info(f"🎯 PADRÃO DETECTADO: {anterior} → {atual} ({probabilidade:.1%}, {count}x)")
                    
                    padrao = {
                        'anterior': anterior,
                        'atual': atual,
                        'probabilidade': probabilidade,
                        'ocorrencias': count,
                        'timestamp': time.time()
                    }
                    self.padroes_detectados.append(padrao)
                    
                    # Manter apenas os padrões mais recentes e fortes
                    self.padroes_detectados = sorted(
                        self.padroes_detectados, 
                        key=lambda x: (x['probabilidade'], x['ocorrencias']), 
                        reverse=True
                    )[:15]

    def gerar_previsao_contextual(self):
        """Gera previsão com foco em incluir padrões detectados"""
        try:
            if self.ultimo_numero_processado is not None:
                # ATUALIZAR ANÁLISE DE PADRÕES ANTES DE PREVER
                self.context_predictor.analisar_padroes_recentes_ativos()
                
                previsao = self.context_predictor.prever_por_contexto_forte(
                    self.ultimo_numero_processado, 
                    top_n=10
                )
                
                # GARANTIR que padrões muito fortes sejam incluídos
                previsao_melhorada = self.aplicar_refinamento_padroes(previsao)
                
                logging.info(f"🎯 PREVISÃO CONTEXTUAL: {self.ultimo_numero_processado} → {len(previsao_melhorada)} números")
                return previsao_melhorada
            else:
                return self.context_predictor.get_numeros_mais_frequentes_global(10)
            
        except Exception as e:
            logging.error(f"Erro na previsão contextual: {e}")
            return list(range(0, 10))

    def aplicar_refinamento_padroes(self, previsao_base):
        """Aplica refinamento para incluir padrões fortes que possam estar faltando"""
        previsao_melhorada = set(previsao_base)
        
        # 1. INCLUIR PADRÕES RECENTES MUITO FORTES
        padroes_recentes_fortes = [
            p for p in self.padroes_detectados 
            if p['probabilidade'] > 0.05 and p['ocorrencias'] >= 3
        ]
        
        for padrao in padroes_recentes_fortes[:3]:  # Top 3 padrões mais fortes
            if padrao['atual'] not in previsao_melhorada:
                previsao_melhorada.add(padrao['atual'])
                logging.info(f"🔧 REFINAMENTO: Adicionado {padrao['atual']} do padrão {padrao['anterior']}→{padrao['atual']}")
        
        # 2. SE A PREVISÃO AINDA NÃO TEM 10 NÚMEROS, COMPLETAR
        if len(previsao_melhorada) < 10:
            faltam = 10 - len(previsao_melhorada)
            complemento = self.context_predictor.get_fallback_inteligente(
                self.ultimo_numero_processado, 
                faltam
            )
            for num in complemento:
                if num not in previsao_melhorada:
                    previsao_melhorada.add(num)
        
        return list(previsao_melhorada)[:10]

    def get_analise_contexto_detalhada(self):
        """Análise detalhada dos padrões de contexto"""
        estatisticas = self.context_predictor.get_estatisticas_contexto()
        
        previsao_atual = []
        if self.ultimo_numero_processado is not None:
            previsao_atual = self.context_predictor.prever_por_contexto_forte(
                self.ultimo_numero_processado, 
                top_n=10
            )
        
        # Padrões recentes ordenados por força
        padroes_recentes = sorted(
            self.padroes_detectados[-8:], 
            key=lambda x: (x['probabilidade'], x['ocorrencias']), 
            reverse=True
        )
        
        return {
            'contextos_ativos': estatisticas['contextos_ativos'],
            'total_transicoes': estatisticas['total_transicoes'],
            'ultimo_numero': self.ultimo_numero_processado,
            'previsao_contexto_atual': previsao_atual,
            'padroes_recentes': padroes_recentes,
            'numero_mais_frequente': estatisticas['numero_mais_frequente'],
            'total_padroes_detectados': len(self.padroes_detectados)
        }

    def calcular_diferencas(self, previsao_atual):
        """Calcula diferenças com a previsão anterior"""
        if not self.previsao_anterior or len(self.previsao_anterior) != 10 or len(previsao_atual) != 10:
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

# =============================
# STREAMLIT APP SIMPLIFICADO
# =============================
st.set_page_config(
    page_title="Roleta - Contexto Histórico", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Sistema de Contexto Histórico - 10 NÚMEROS")
st.markdown("### **Sistema que Captura Padrões Óbvios - Inclui Padrões na Previsão**")

st_autorefresh(interval=15000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorContextoHistorico(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
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

        # CONFERÊNCIA - SEMPRE com 10 números
        previsao_valida = validar_previsao(st.session_state.previsao_atual)
        acertou = False
        if previsao_valida and len(previsao_valida) == 10:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
                # ENVIAR ALERTA DE GREEN COM 10 NÚMEROS
                enviar_alerta_resultado(True, numero_real, st.session_state.previsao_atual)
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")
                # ENVIAR ALERTA DE RED COM 10 NÚMEROS
                enviar_alerta_resultado(False, numero_real, st.session_state.previsao_atual)
        else:
            logging.warning(f"Previsão inválida para conferência: {previsao_valida}")

        # GERAR NOVA PREVISÃO COM CONTEXTO - SEMPRE 10 NÚMEROS
        nova_previsao = st.session_state.gestor.gerar_previsao_contextual()
        
        # CALCULAR MUDANÇAS
        diferencas = st.session_state.gestor.calcular_diferencas(nova_previsao)
        st.session_state.previsao_anterior = st.session_state.previsao_atual.copy()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # ENVIAR ALERTA TELEGRAM - PREVISÃO COM 10 NÚMEROS
        if st.session_state.previsao_atual and len(st.session_state.previsao_atual) == 10:
            try:
                enviar_alerta_previsao(st.session_state.previsao_atual)
            except Exception as e:
                logging.error(f"Erro ao enviar alerta de previsão: {e}")
        else:
            logging.error(f"Previsão inválida para alerta: {st.session_state.previsao_atual}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# =============================
# INTERFACE STREAMLIT
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Estratégia", "Contexto Histórico")
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)}")
with col3:
    ultimo_numero = st.session_state.ultimo_numero
    display_numero = ultimo_numero if ultimo_numero is not None else "-"
    st.metric("🎲 Último", display_numero)
with col4:
    total_transicoes = st.session_state.gestor.context_predictor.get_total_transicoes()
    st.metric("🔄 Transições", total_transicoes)

# ANÁLISE DO CONTEXTO
st.subheader("🔍 Análise do Contexto Histórico")
analise_contexto = st.session_state.gestor.get_analise_contexto_detalhada()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Contextos Ativos", analise_contexto['contextos_ativos'])
with col2:
    st.metric("📈 Transições", analise_contexto['total_transicoes'])
with col3:
    st.metric("🔥 Mais Frequente", analise_contexto['numero_mais_frequente'])
with col4:
    st.metric("🎯 Padrões Detectados", analise_contexto['total_padroes_detectados'])

# PREVISÃO CONTEXTUAL ATUAL
previsao_contexto = analise_contexto['previsao_contexto_atual']
if previsao_contexto and analise_contexto['ultimo_numero'] is not None:
    previsao_unica = []
    numeros_vistos = set()
    for num in previsao_contexto:
        if num not in numeros_vistos:
            previsao_unica.append(num)
            numeros_vistos.add(num)
    
    if previsao_unica and len(previsao_unica) == 10:
        st.success(f"**📈 10 NÚMEROS MAIS PROVÁVEIS APÓS {analise_contexto['ultimo_numero']}:**")
        
        if len(previsao_unica) >= 8:
            emoji = "🎯"
            força = "ALTA"
        elif len(previsao_unica) >= 6:
            emoji = "🔍" 
            força = "MÉDIA"
        else:
            emoji = "🔄"
            força = "BAIXA"
        
        # Formatação para 10 números (5+5)
        linha1 = previsao_unica[:5]
        linha2 = previsao_unica[5:10]
        
        linha1_str = " | ".join([f"**{num}**" for num in linha1])
        linha2_str = " | ".join([f"**{num}**" for num in linha2])
        
        st.markdown(f"### {emoji} {linha1_str}")
        st.markdown(f"### {emoji} {linha2_str}")
        st.caption(f"💡 **{força} CONFIANÇA** - Baseado em {analise_contexto['total_transicoes']} transições históricas")
        
        # MOSTRAR PADRÕES DETECTADOS
        padroes_recentes = analise_contexto.get('padroes_recentes', [])
        if padroes_recentes:
            st.info("**🎯 PADRÕES DETECTADOS RECENTEMENTE:**")
            for padrao in padroes_recentes:
                st.write(f"`{padrao['anterior']} → {padrao['atual']}` ({padrao['probabilidade']:.1%}, {padrao['ocorrencias']}x)")
        
else:
    st.info("🔄 Coletando dados contextuais... O sistema está aprendendo padrões.")
    
    if analise_contexto['total_transicoes'] > 0:
        st.progress(min(100, analise_contexto['total_transicoes'] / 100))
        st.caption(f"📈 Progresso: {analise_contexto['total_transicoes']} transições analisadas")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL - 10 NÚMEROS")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

# MOSTRAR MUDANÇAS
if st.session_state.previsao_anterior and len(st.session_state.previsao_anterior) == 10:
    diferencas = st.session_state.gestor.calcular_diferencas(st.session_state.previsao_atual)
    if diferencas:
        st.info(f"**🔄 Mudanças:** Removidos: {', '.join(map(str, diferencas['removidos']))} | Adicionados: {', '.join(map(str, diferencas['adicionados']))}")

if previsao_valida and len(previsao_valida) == 10:
    st.success(f"**📊 10 NÚMEROS PREVISTOS**")
    
    # Display organizado em 2 linhas de 5
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Linha 1:**")
        for num in sorted(previsao_valida[:5]):
            st.write(f"`{num}`")
    
    with col2:
        st.write("**Linha 2:**")
        for num in sorted(previsao_valida[5:10]):
            st.write(f"`{num}`")
    
    st.write(f"**Lista Completa (10 números):** {', '.join(map(str, sorted(previsao_valida)))}")
    
else:
    st.warning("⚠️ Inicializando sistema...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

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
with st.expander("🔧 Detalhes Técnicos do Sistema"):
    st.write("**🎯 ESTRATÉGIA DE CONTEXTO HISTÓRICO ATUALIZADA:**")
    st.write("- 🔍 Captura padrões óbvios de transição entre números")
    st.write("- 🎯 INCLUI AUTOMATICAMENTE padrões detectados na previsão")
    st.write("- 📊 Critérios inteligentes: probabilidade >3% + 2+ ocorrências")
    st.write("- ⚡ Análise em tempo real com refinamento automático")
    st.write("- 💾 Persistência de contexto entre execuções")
    st.write("- 🔧 Sistema de refinamento para incluir padrões fortes")
    st.write("- 🔢 Sistema otimizado para 10 números")
    
    st.write("**📊 ESTATÍSTICAS ATUAIS:**")
    st.write(f"- Contextos ativos: {analise_contexto['contextos_ativos']}")
    st.write(f"- Transições analisadas: {analise_contexto['total_transicoes']}")
    st.write(f"- Número mais frequente: {analise_contexto['numero_mais_frequente']}")
    st.write(f"- Padrões detectados: {analise_contexto['total_padroes_detectados']}")
    
    st.write("**📨 SISTEMA DE ALERTAS (10 NÚMEROS):**")
    st.write("- 🔔 Alerta de PREVISÃO: '🎯 PREVISÃO: 1 2 3 4 5 6 7 8 9 10'")
    st.write("- 🟢 Alerta GREEN: '🟢 GREEN! Acertou X | Previsão: 1 2 3 4 5 6 7 8 9 10'")
    st.write("- 🔴 Alerta RED: '🔴 RED! Sorteado X | Previsão: 1 2 3 4 5 6 7 8 9 10'")

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
st.markdown("### 🚀 **Sistema de Contexto Histórico - 10 Números**")
st.markdown("*Agora inclui automaticamente os padrões detectados na previsão!*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Contexto Histórico v4.0** - *Sistema com Inclusão Automática de Padrões*")
