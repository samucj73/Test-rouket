# RoletaHybridIA.py - SISTEMA COM ESTRATÉGIA INTELIGENTE REVISADA
import streamlit as st
import json
import os
import time
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import random
import numpy as np

# =============================
# Configurações OTIMIZADAS
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
CICLO_PREVISAO = 1  # MAIS AGRESSIVO: Previsão a cada sorteio
CONFIANCA_MINIMA = 0.60  # 60% de confiança mínima

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# FUNÇÕES UTILITÁRIAS COMPLETAS
# =============================
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

def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_alerta_previsao(numeros, confianca):
    """Envia alerta de PREVISÃO com 10 números e nível de confiança"""
    try:
        if not numeros or len(numeros) != 10:
            logging.error(f"❌ Alerta de previsão precisa de 10 números, recebeu: {len(numeros) if numeros else 0}")
            return
            
        # Ordena os números do menor para o maior
        numeros_ordenados = sorted(numeros)
        
        # Formata com confiança
        numeros_str = ' '.join(map(str, numeros_ordenados))
        mensagem = f"🎯 PREVISÃO {confianca}%: {numeros_str}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de PREVISÃO enviado: 10 números com {confianca}% confiança")
        
    except Exception as e:
        logging.error(f"Erro alerta previsão: {e}")

def enviar_alerta_resultado(acertou, numero_sorteado, previsao_anterior, confianca):
    """Envia alerta de resultado (GREEN/RED) com os 10 números da previsão"""
    try:
        if not previsao_anterior or len(previsao_anterior) != 10:
            logging.error(f"❌ Alerta resultado precisa de 10 números na previsão")
            return
            
        # Ordena os números da previsão anterior
        previsao_ordenada = sorted(previsao_anterior)
        previsao_str = ' '.join(map(str, previsao_ordenada))
        
        if acertou:
            mensagem = f"🟢 GREEN! Acertou {numero_sorteado} | Conf: {confianca}% | Previsão: {previsao_str}"
        else:
            mensagem = f"🔴 RED! Sorteado {numero_sorteado} | Conf: {confianca}% | Previsão: {previsao_str}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de resultado enviado")
        
    except Exception as e:
        logging.error(f"Erro alerta resultado: {e}")

# =============================
# CONTEXT PREDICTOR - ESTRATÉGIA INTELIGENTE REVISADA
# =============================
class Context_Predictor_Inteligente:
    def __init__(self):
        self.context_history = {}
        self.arquivo_contexto = CONTEXTO_PATH
        self.padroes_fortes_cache = []
        self.ultimos_numeros = deque(maxlen=10)
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
                
            else:
                logging.info("🆕 Criando novo contexto histórico")
                self.context_history = {}
        except Exception as e:
            logging.error(f"❌ Erro ao carregar contexto: {e}")
            self.context_history = {}

    def get_total_transicoes(self):
        """Calcula total de transições"""
        return sum(sum(seguintes.values()) for seguintes in self.context_history.values())
    
    def salvar_contexto(self):
        """Salva contexto histórico no arquivo"""
        try:
            with open(self.arquivo_contexto, "w") as f:
                json.dump(self.context_history, f, indent=2)
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
            
            # Atualizar últimos números
            self.ultimos_numeros.append(numero_atual)
            
        except Exception as e:
            logging.error(f"Erro ao atualizar contexto: {e}")

    def prever_com_estrategia_avancada(self, ultimo_numero, top_n=10):
        """ESTRATÉGIA AVANÇADA - Foco em padrões reais e estatísticas sólidas"""
        try:
            previsao_final = set()
            confianca_total = 0
            estrategias_utilizadas = 0
            
            # 1. ANÁLISE DE PADRÕES FORTES (40% de peso)
            padroes_fortes = self.identificar_padroes_fortes(ultimo_numero)
            for padrao in padroes_fortes[:4]:
                if padrao['proximo'] not in previsao_final:
                    previsao_final.add(padrao['proximo'])
                    confianca_total += padrao['probabilidade']
                    estrategias_utilizadas += 1
                    logging.info(f"🎯 PADRÃO FORTE: {ultimo_numero} → {padrao['proximo']} ({padrao['probabilidade']:.1%}, {padrao['ocorrencias']}x)")
            
            # 2. NÚMEROS QUENTES RECENTES (25% de peso)
            numeros_quentes = self.analisar_numeros_quentes(5)
            for num in numeros_quentes[:3]:
                if num not in previsao_final:
                    previsao_final.add(num)
                    confianca_total += 0.15
                    estrategias_utilizadas += 1
            
            # 3. SEQUÊNCIAS DE BAIXA FREQUÊNCIA (20% de peso)
            numeros_frios = self.identificar_numeros_frios(4)
            for num in numeros_frios[:2]:
                if num not in previsao_final:
                    previsao_final.add(num)
                    confianca_total += 0.12
                    estrategias_utilizadas += 1
            
            # 4. VIZINHANÇA ESTRATÉGICA (15% de peso)
            vizinhos_estrategicos = self.obter_vizinhos_estrategicos(ultimo_numero)
            for num in vizinhos_estrategicos[:3]:
                if num not in previsao_final:
                    previsao_final.add(num)
                    confianca_total += 0.10
                    estrategias_utilizadas += 1
            
            # Converter para lista
            resultado = list(previsao_final)
            
            # COMPLETAR COM NÚMEROS ESTRATÉGICOS SE NECESSÁRIO
            if len(resultado) < top_n:
                faltam = top_n - len(resultado)
                complemento = self.get_complemento_estrategico(ultimo_numero, faltam)
                for num in complemento:
                    if num not in resultado:
                        resultado.append(num)
                        confianca_total += 0.05
                        estrategias_utilizadas += 1
            
            # CALCULAR CONFIANÇA REALISTA
            if estrategias_utilizadas > 0:
                confianca_media = (confianca_total / estrategias_utilizadas) * 100
                # Ajustar confiança baseado na força dos padrões
                fator_ajuste = min(1.0, len(padroes_fortes) / 3.0)
                confianca_final = confianca_media * fator_ajuste
            else:
                confianca_final = 25.0
            
            confianca_final = min(confianca_final, 85.0)  # Limite realista
            
            logging.info(f"🎯 ESTRATÉGIA AVANÇADA: {ultimo_numero} → {resultado} | Confiança: {confianca_final:.1f}%")
            return resultado[:top_n], confianca_final
            
        except Exception as e:
            logging.error(f"Erro na estratégia avançada: {e}")
            fallback = self.get_complemento_estrategico(ultimo_numero, top_n)
            return fallback, 30.0

    def identificar_padroes_fortes(self, ultimo_numero):
        """Identifica apenas padrões realmente fortes"""
        padroes_fortes = []
        
        # PADRÕES DIRETOS DO ÚLTIMO NÚMERO
        if ultimo_numero in self.context_history:
            contexto = self.context_history[ultimo_numero]
            total = sum(contexto.values())
            
            for proximo, count in contexto.items():
                probabilidade = count / total
                
                # CRITÉRIOS MAIS RIGOROSOS: prob > 8% E count >= 5
                if probabilidade > 0.08 and count >= 5:
                    score = probabilidade * 100 + min(count, 20)
                    padroes_fortes.append({
                        'anterior': ultimo_numero,
                        'proximo': proximo,
                        'probabilidade': probabilidade,
                        'ocorrencias': count,
                        'score': score
                    })
        
        # PADRÕES GERAIS FORTES (independente do último número)
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                total = sum(seguintes.values())
                for proximo, count in seguintes.items():
                    probabilidade = count / total
                    
                    # Padrões muito fortes (prob > 12% e count >= 8)
                    if probabilidade > 0.12 and count >= 8:
                        score = probabilidade * 100 + min(count, 25)
                        padroes_fortes.append({
                            'anterior': anterior,
                            'proximo': proximo,
                            'probabilidade': probabilidade,
                            'ocorrencias': count,
                            'score': score
                        })
        
        # Ordenar por score
        padroes_fortes.sort(key=lambda x: x['score'], reverse=True)
        return padroes_fortes[:8]

    def analisar_numeros_quentes(self, quantidade):
        """Analisa números que aparecem com frequência recente"""
        if len(self.ultimos_numeros) < 10:
            return self.get_numeros_mais_frequentes_global(quantidade)
        
        # Analisar últimos 50 números para tendências
        frequencia_recente = Counter(list(self.ultimos_numeros)[-50:])
        return [num for num, count in frequencia_recente.most_common(quantidade)]

    def identificar_numeros_frios(self, quantidade):
        """Identifica números que não aparecem há tempo"""
        if len(self.ultimos_numeros) < 20:
            return []
        
        ultimos_50 = list(self.ultimos_numeros)[-50:]
        todos_numeros = set(range(0, 37))
        numeros_recentes = set(ultimos_50)
        
        numeros_frios = list(todos_numeros - numeros_recentes)
        
        if len(numeros_frios) < quantidade:
            # Se não há números frios, pega os que menos apareceram
            frequencia = Counter(ultimos_50)
            numeros_frios = [num for num, count in frequencia.most_common()[-quantidade:]]
        
        return numeros_frios[:quantidade]

    def obter_vizinhos_estrategicos(self, numero):
        """Vizinhos físicos com análise estratégica"""
        vizinhos_base = obter_vizinhos_fisicos(numero)
        
        # Priorizar vizinhos que são quentes
        numeros_quentes = self.analisar_numeros_quentes(10)
        vizinhos_estrategicos = []
        
        for vizinho in vizinhos_base:
            if vizinho in numeros_quentes[:5]:
                vizinhos_estrategicos.append(vizinho)
        
        # Adicionar outros vizinhos se necessário
        for vizinho in vizinhos_base:
            if vizinho not in vizinhos_estrategicos and len(vizinhos_estrategicos) < 5:
                vizinhos_estrategicos.append(vizinho)
        
        return vizinhos_estrategicos

    def get_complemento_estrategico(self, ultimo_numero, quantidade):
        """Complemento inteligente baseado em múltiplas estratégias"""
        numeros_complemento = set()
        
        # 1. Números mais frequentes globalmente
        frequentes_global = self.get_numeros_mais_frequentes_global(quantidade + 3)
        for num in frequentes_global[:quantidade//2]:
            numeros_complemento.add(num)
        
        # 2. Vizinhos físicos
        vizinhos = obter_vizinhos_fisicos(ultimo_numero)
        for vizinho in vizinhos[:quantidade//2]:
            numeros_complemento.add(vizinho)
        
        # 3. Preencher com números aleatórios estratégicos
        if len(numeros_complemento) < quantidade:
            estrategicos = [0, 2, 5, 8, 11, 17, 20, 26, 29, 32, 35]
            for num in estrategicos:
                if num not in numeros_complemento and len(numeros_complemento) < quantidade:
                    numeros_complemento.add(num)
        
        # 4. Preencher com qualquer número se ainda faltar
        if len(numeros_complemento) < quantidade:
            todos_numeros = list(range(0, 37))
            random.shuffle(todos_numeros)
            for num in todos_numeros:
                if num not in numeros_complemento:
                    numeros_complemento.add(num)
                if len(numeros_complemento) >= quantidade:
                    break
        
        return list(numeros_complemento)[:quantidade]

    def get_numeros_mais_frequentes_global(self, quantidade):
        """Retorna números mais frequentes em TODO o contexto"""
        frequencia_global = Counter()
        
        for anterior, seguintes in self.context_history.items():
            for numero, count in seguintes.items():
                frequencia_global[numero] += count
        
        numeros_mais_frequentes = [num for num, count in frequencia_global.most_common(quantidade)]
        
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
        
        frequencia_global = self.get_numeros_mais_frequentes_global(3)
        numeros_mais_frequentes = frequencia_global if frequencia_global else ["Nenhum"]
        
        # Analisar força dos padrões
        padroes_fortes_count = 0
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                total = sum(seguintes.values())
                for count in seguintes.values():
                    if count / total > 0.08 and count >= 5:
                        padroes_fortes_count += 1
        
        return {
            'contextos_ativos': len(self.context_history),
            'total_transicoes': total_transicoes,
            'numeros_mais_frequentes': numeros_mais_frequentes,
            'padroes_fortes_detectados': padroes_fortes_count,
            'tamanho_historico_recente': len(self.ultimos_numeros)
        }

# =============================
# GESTOR PRINCIPAL - ESTRATÉGIA REVISADA
# =============================
class GestorEstrategiaInteligente:
    def __init__(self):
        self.context_predictor = Context_Predictor_Inteligente()
        self.historico = deque(carregar_historico(), maxlen=5000)
        self.previsao_anterior = None
        self.ultimo_numero_processado = None
        self.contador_sorteios = 0
        self.confianca_ultima_previsao = 0
        self.ultima_previsao_enviada = None
        self.acertos_consecutivos = 0
        self.erros_consecutivos = 0
        
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
                    self.context_predictor.ultimos_numeros.append(numeros[i])
                
                if numeros:
                    self.ultimo_numero_processado = numeros[-1]
                
                logging.info(f"🚀 CONTEXTO INICIALIZADO: {transicoes_adicionadas} transições, último número: {self.ultimo_numero_processado}")
                
        except Exception as e:
            logging.error(f"Erro na inicialização do contexto: {e}")

    def adicionar_numero(self, numero_dict):
        """Adiciona número com análise de padrões"""
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            numero_atual = numero_dict['number']
            
            # ATUALIZAR CONTEXTO
            if self.ultimo_numero_processado is not None:
                self.context_predictor.atualizar_contexto(
                    self.ultimo_numero_processado, 
                    numero_atual
                )
            
            self.ultimo_numero_processado = numero_atual
            self.historico.append(numero_dict)
            self.contador_sorteios += 1

    def deve_gerar_previsao(self):
        """Decide se deve gerar nova previsão - ESTRATÉGIA MAIS AGRESSIVA"""
        # Sempre gera na primeira execução
        if self.previsao_anterior is None:
            return True
            
        # Gera a cada CICLO_PREVISAO sorteios (AGORA MAIS FREQUENTE)
        if self.contador_sorteios % CICLO_PREVISAO == 0:
            return True
            
        # Gera se teve muitos erros consecutivos (mudar estratégia)
        if self.erros_consecutivos >= 2:
            logging.info("🔄 MUDANÇA DE ESTRATÉGIA - Muitos erros consecutivos")
            return True
            
        return False

    def gerar_previsao_inteligente(self):
        """Gera previsão usando estratégia avançada"""
        try:
            if self.ultimo_numero_processado is not None:
                previsao, confianca = self.context_predictor.prever_com_estrategia_avancada(
                    self.ultimo_numero_processado, 
                    top_n=10
                )
                
                logging.info(f"🎯 PREVISÃO INTELIGENTE: {self.ultimo_numero_processado} → {len(previsao)} números | Confiança: {confianca:.1f}%")
                return previsao, confianca
            else:
                previsao = self.context_predictor.get_numeros_mais_frequentes_global(10)
                return previsao, 25.0
            
        except Exception as e:
            logging.error(f"Erro na previsão inteligente: {e}")
            return list(range(0, 10)), 20.0

    def registrar_resultado(self, acertou):
        """Registra resultado e ajusta estratégia"""
        if acertou:
            self.acertos_consecutivos += 1
            self.erros_consecutivos = 0
            logging.info(f"✅ ACERTO CONSECUTIVO #{self.acertos_consecutivos}")
        else:
            self.erros_consecutivos += 1
            self.acertos_consecutivos = 0
            logging.info(f"🔴 ERRO CONSECUTIVO #{self.erros_consecutivos}")

    def get_analise_estrategica(self):
        """Análise detalhada da estratégia"""
        estatisticas = self.context_predictor.get_estatisticas_contexto()
        
        previsao_atual = []
        confianca_atual = 0
        if self.ultimo_numero_processado is not None:
            previsao_atual, confianca_atual = self.context_predictor.prever_com_estrategia_avancada(
                self.ultimo_numero_processado, 
                top_n=10
            )
        
        return {
            'contextos_ativos': estatisticas['contextos_ativos'],
            'total_transicoes': estatisticas['total_transicoes'],
            'ultimo_numero': self.ultimo_numero_processado,
            'previsao_estrategia_atual': previsao_atual,
            'confianca_previsao_atual': confianca_atual,
            'numeros_mais_frequentes': estatisticas['numeros_mais_frequentes'],
            'padroes_fortes_detectados': estatisticas['padroes_fortes_detectados'],
            'contador_sorteios': self.contador_sorteios,
            'acertos_consecutivos': self.acertos_consecutivos,
            'erros_consecutivos': self.erros_consecutivos,
            'ciclo_previsao': CICLO_PREVISAO,
            'proxima_previsao_em': CICLO_PREVISAO - (self.contador_sorteios % CICLO_PREVISAO)
        }

# =============================
# STREAMLIT APP - INTERFACE REVISADA
# =============================
st.set_page_config(
    page_title="Roleta - Estratégia Inteligente", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Estratégia Inteligente Revisada")
st.markdown("### **Sistema com análise avançada de padrões fortes**")

st_autorefresh(interval=15000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorEstrategiaInteligente(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
    "confianca_atual": 0,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL REVISADO
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
                st.session_state.gestor.registrar_resultado(True)
                st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
                # ENVIAR ALERTA DE GREEN
                enviar_alerta_resultado(True, numero_real, st.session_state.previsao_atual, st.session_state.confianca_atual)
            else:
                st.session_state.erros += 1
                st.session_state.gestor.registrar_resultado(False)
                st.error(f"🔴 Número {numero_real} não estava na previsão")
                # ENVIAR ALERTA DE RED
                enviar_alerta_resultado(False, numero_real, st.session_state.previsao_atual, st.session_state.confianca_atual)

        # GERAR NOVA PREVISÃO COM ESTRATÉGIA INTELIGENTE
        if st.session_state.gestor.deve_gerar_previsao():
            nova_previsao, confianca = st.session_state.gestor.gerar_previsao_inteligente()
            
            # ACEITA PREVISÕES COM CONFIANÇA RAZOÁVEL
            if confianca >= CONFIANCA_MINIMA * 100:
                st.session_state.previsao_anterior = st.session_state.previsao_atual.copy()
                st.session_state.previsao_atual = validar_previsao(nova_previsao)
                st.session_state.confianca_atual = confianca
                
                # ENVIAR ALERTA TELEGRAM SE CONFIANÇA > 55%
                if st.session_state.previsao_atual and len(st.session_state.previsao_atual) == 10:
                    if confianca >= 55:
                        try:
                            enviar_alerta_previsao(st.session_state.previsao_atual, int(confianca))
                        except Exception as e:
                            logging.error(f"Erro ao enviar alerta de previsão: {e}")
                    else:
                        logging.info(f"📊 Previsão com confiança moderada ({confianca}%) - Sem alerta Telegram")
            else:
                logging.info(f"⏭️ Confiança insuficiente: {confianca:.1f}% < {CONFIANCA_MINIMA*100}%")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    st.session_state.confianca_atual = 25

# =============================
# INTERFACE STREAMLIT REVISADA
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Estratégia", "Inteligente")
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)}")
with col3:
    ultimo_numero = st.session_state.ultimo_numero
    display_numero = ultimo_numero if ultimo_numero is not None else "-"
    st.metric("🎲 Último", display_numero)
with col4:
    analise = st.session_state.gestor.get_analise_estrategica()
    st.metric("🔄 Próxima Previsão", f"em {analise['proxima_previsao_em']}")

# ANÁLISE DA ESTRATÉGIA
st.subheader("🔍 Análise da Estratégia Inteligente")
analise_estrategia = st.session_state.gestor.get_analise_estrategica()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Contextos Ativos", analise_estrategia['contextos_ativos'])
with col2:
    st.metric("📈 Transições", analise_estrategia['total_transicoes'])
with col3:
    st.metric("🔥 Mais Frequentes", f"{analise_estrategia['numeros_mais_frequentes'][0] if analise_estrategia['numeros_mais_frequentes'] else 'N/A'}")
with col4:
    st.metric("🎯 Padrões Fortes", analise_estrategia['padroes_fortes_detectados'])

# PREVISÃO DA ESTRATÉGIA ATUAL
previsao_estrategia = analise_estrategia['previsao_estrategia_atual']
confianca_previsao = analise_estrategia['confianca_previsao_atual']

if previsao_estrategia and analise_estrategia['ultimo_numero'] is not None:
    previsao_unica = []
    numeros_vistos = set()
    for num in previsao_estrategia:
        if num not in numeros_vistos:
            previsao_unica.append(num)
            numeros_vistos.add(num)
    
    if previsao_unica and len(previsao_unica) == 10:
        # Mostrar confiança da previsão atual
        status_confianca = "ALTA" if confianca_previsao >= 70 else "MÉDIA" if confianca_previsao >= 50 else "BAIXA"
        emoji_confianca = "🎯" if confianca_previsao >= 70 else "🔍" if confianca_previsao >= 50 else "🔄"
        
        st.success(f"**📈 10 NÚMEROS MAIS PROVÁVEIS APÓS {analise_estrategia['ultimo_numero']}:**")
        
        # Formatação para 10 números (5+5)
        linha1 = previsao_unica[:5]
        linha2 = previsao_unica[5:10]
        
        linha1_str = " | ".join([f"**{num}**" for num in linha1])
        linha2_str = " | ".join([f"**{num}**" for num in linha2])
        
        st.markdown(f"### {emoji_confianca} {linha1_str}")
        st.markdown(f"### {emoji_confianca} {linha2_str}")
        st.caption(f"💡 **{status_confianca} CONFIANÇA ({confianca_previsao:.1f}%)** - Baseado em {analise_estrategia['total_transicoes']} transições e {analise_estrategia['padroes_fortes_detectados']} padrões fortes")
        
else:
    st.info("🔄 Inicializando estratégia inteligente...")
    
    if analise_estrategia['total_transicoes'] > 0:
        progresso = min(100, analise_estrategia['total_transicoes'] / 500)
        st.progress(progresso / 100)
        st.caption(f"📈 Progresso: {analise_estrategia['total_transicoes']} transições analisadas")

# PREVISÃO ATUAL OFICIAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL OFICIAL - ESTRATÉGIA INTELIGENTE")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida and len(previsao_valida) == 10:
    # Classificar confiança
    if st.session_state.confianca_atual >= 75:
        cor = "🟢"
        status = "MUITO ALTA"
    elif st.session_state.confianca_atual >= 60:
        cor = "🟡" 
        status = "ALTA"
    elif st.session_state.confianca_atual >= 45:
        cor = "🟠"
        status = "MÉDIA"
    else:
        cor = "🔴"
        status = "BAIXA"
    
    st.success(f"**{cor} PREVISÃO ATIVA - {status} CONFIANÇA ({st.session_state.confianca_atual:.1f}%)**")
    
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
    st.warning("⏳ Aguardando próxima previsão da estratégia...")
    st.info(f"📊 Próxima previsão em: {analise_estrategia['proxima_previsao_em']} sorteio(s)")

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

# ESTATÍSTICAS DE CONSECUTIVOS
col1, col2 = st.columns(2)
with col1:
    st.metric("✅ Acertos Consecutivos", analise_estrategia['acertos_consecutivos'])
with col2:
    st.metric("🔴 Erros Consecutivos", analise_estrategia['erros_consecutivos'])

# DETALHES TÉCNICOS
with st.expander("🔧 Detalhes da Estratégia Inteligente"):
    st.write("**🎯 ESTRATÉGIA AVANÇADA:**")
    st.write("- 🔄 Previsões a cada **1 sorteio** (máxima frequência)")
    st.write("- 🎯 Foco em **padrões fortes** (prob > 8% e ocorrências ≥ 5)")
    st.write("- 📊 Análise de **números quentes e frios**")
    st.write("- 🧠 **Vizinhos estratégicos** com números quentes")
    st.write("- 📈 Confiança mínima: **60%**")
    
    st.write("**📊 ESTATÍSTICAS AVANÇADAS:**")
    st.write(f"- Contextos ativos: {analise_estrategia['contextos_ativos']}")
    st.write(f"- Transições analisadas: {analise_estrategia['total_transicoes']}")
    st.write(f"- Números mais frequentes: {', '.join(map(str, analise_estrategia['numeros_mais_frequentes']))}")
    st.write(f"- Padrões fortes detectados: {analise_estrategia['padroes_fortes_detectados']}")
    st.write(f"- Acertos consecutivos: {analise_estrategia['acertos_consecutivos']}")
    st.write(f"- Erros consecutivos: {analise_estrategia['erros_consecutivos']}")
    
    st.write("**📨 SISTEMA DE ALERTAS INTELIGENTE:**")
    st.write("- 🔔 Alerta de PREVISÃO: Apenas se confiança ≥ 55%")
    st.write("- 🟢 Alerta GREEN: Sempre que acertar")
    st.write("- 🔴 Alerta RED: Sempre que errar")

# CONTROLES
st.markdown("---")
st.subheader("⚙️ Controles do Sistema")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Forçar Nova Previsão"):
        nova_previsao, confianca = st.session_state.gestor.gerar_previsao_inteligente()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        st.session_state.confianca_atual = confianca
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
st.markdown("### 🚀 **Estratégia Inteligente Revisada**")
st.markdown("*Sistema com análise avançada de padrões fortes e números quentes/frios*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Estratégia Inteligente v3.0** - *Análise Avançada de Padrões*")
