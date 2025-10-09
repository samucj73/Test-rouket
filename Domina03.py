# RoletaHybridIA.py - SISTEMA ESPECIALISTA 100% BASEADO EM HISTÓRICO
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
# Configurações
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
METRICAS_PATH = "metricas_hybrid_ia.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

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
MIN_HISTORICO_TREINAMENTO = 475
NUMERO_PREVISOES = 8  # SEMPRE 8 NÚMEROS BASEADOS NO HISTÓRICO

# Fases do sistema
FASE_INICIAL = 30
FASE_INTERMEDIARIA = 80  
FASE_AVANCADA = 120
FASE_ESPECIALISTA = 150

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# SISTEMAS DE SUPORTE MAIS AGRESSIVOS
# =============================

class SistemaConfianca:
    def __init__(self):
        self.confianca = 0.6  # Iniciar com confiança mais alta
        self.tendencia = "NEUTRA"
        self.historico_confianca = deque(maxlen=20)
    
    def atualizar_confianca(self, acerto):
        if acerto:
            self.confianca = min(0.95, self.confianca + 0.08)  # Aumento maior nos acertos
        else:
            self.confianca = max(0.2, self.confianca - 0.05)   # Redução menor nos erros
        
        self.historico_confianca.append(self.confianca)
        
        if self.confianca > 0.6:  # Reduzido de 0.7 para 0.6
            self.tendencia = "ALTA"
        elif self.confianca < 0.4:  # Ajustado de 0.3 para 0.4
            self.tendencia = "BAIXA"
        else:
            self.tendencia = "NEUTRA"
    
    def get_confianca_categoria(self):
        if self.confianca > 0.7:  # Reduzido de 0.8 para 0.7
            return "MUITO ALTA"
        elif self.confianca > 0.5:  # Reduzido de 0.6 para 0.5
            return "ALTA"
        elif self.confianca > 0.3:  # Reduzido de 0.4 para 0.3
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
        """Critérios MAIS FLEXÍVEIS para entrada"""
        
        # SEMPRE ENTRAR se risco for BAIXO, independente da confiança
        if analise_risco == "RISCO_BAIXO":
            return True
            
        # Entrar com risco MODERADO mesmo com confiança baixa se histórico for grande
        if analise_risco == "RISCO_MODERADO" and historico_size > 50:
            return True
            
        # Não entrar apenas em risco ALTO com confiança muito baixa
        if analise_risco == "RISCO_ALTO" and confianca < 0.3:
            return False
            
        # Limite mais flexível para sequência negativa
        if self.sequencia_atual >= 4:  # Aumentado de 3 para 4
            return False
            
        return True
    
    def calcular_tamanho_aposta(self, confianca, saldo=1000):
        base = saldo * 0.02
        if confianca > 0.7:  # Reduzido de 0.8 para 0.7
            return base * 1.5
        elif confianca > 0.4:  # Reduzido de 0.6 para 0.4
            return base
        else:
            return base * 0.7  # Reduzido de 0.5 para 0.7
    
    def atualizar_sequencia(self, resultado):
        if resultado == "GREEN":
            self.sequencia_atual = 0
        else:
            self.sequencia_atual += 1
            self.max_sequencia_negativa = max(self.max_sequencia_negativa, self.sequencia_atual)

# =============================
# NOVO SISTEMA DE PREVISÃO POR SEQUÊNCIA HISTÓRICA
# =============================

class SistemaPrevisaoSequencial:
    def __init__(self):
        self.historico_sequencias = {}
        self.performance_sequencial = {"acertos": 0, "erros": 0}
        
    def analisar_sequencias_historicas(self, historico, numero_atual):
        """Analisa quais números costumam sair APÓS o número atual no histórico"""
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return []
        
        sequencias_encontradas = []
        
        # Procurar todas as ocorrências do número atual no histórico
        for i in range(len(numeros) - 1):
            if numeros[i] == numero_atual:
                # Pegar os PRÓXIMOS 3 números que saíram após este número
                if i + 1 < len(numeros):
                    sequencias_encontradas.append(numeros[i + 1])
                if i + 2 < len(numeros):
                    sequencias_encontradas.append(numeros[i + 2])
                if i + 3 < len(numeros):
                    sequencias_encontradas.append(numeros[i + 3])
        
        # Contar frequência dos números que aparecem após o número atual
        contador_sequencias = Counter(sequencias_encontradas)
        
        # Pegar os 10 números mais frequentes
        numeros_mais_frequentes = [num for num, count in contador_sequencias.most_common(10)]
        
        logging.info(f"🔍 Sequência histórica: Após {numero_atual} saíram {len(sequencias_encontradas)} números, tops: {numeros_mais_frequentes[:5]}")
        
        return numeros_mais_frequentes
    
    def gerar_previsao_sequencial(self, historico, ultimo_numero):
        """Gera previsão baseada no que costuma sair após o último número"""
        
        if not historico or ultimo_numero is None:
            return []
        
        # Analisar sequências históricas
        previsao_sequencial = self.analisar_sequencias_historicas(historico, ultimo_numero)
        
        # Se não encontrou sequências suficientes, usar fallback
        if len(previsao_sequencial) < 5:
            # Fallback: usar números quentes recentes
            numeros = [h['number'] for h in historico if h.get('number') is not None]
            if len(numeros) >= 10:
                contagem_recente = Counter(numeros[-10:])
                previsao_sequencial = [num for num, count in contagem_recente.most_common(8)]
        
        return previsao_sequencial[:NUMERO_PREVISOES]
    
    def verificar_acerto_sequencial(self, previsao_sequencial, numero_sorteado):
        """Verifica se a previsão sequencial acertou"""
        if not previsao_sequencial or numero_sorteado is None:
            return None
        
        acertou = numero_sorteado in previsao_sequencial
        if acertou:
            self.performance_sequencial["acertos"] += 1
        else:
            self.performance_sequencial["erros"] += 1
        
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
# ANÁLISES 100% BASEADAS EM HISTÓRICO - VERSÃO MAIS AGRESSIVA
# =============================

def analisar_padroes_assertivos(historico):
    """Análise AGGRESSIVA focada em padrões de alta probabilidade BASEADA NO HISTÓRICO"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 5:  # Reduzido de 10 para 5
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
    
    # NÚMEROS QUENTES (últimas 12 rodadas - reduzido de 15) - baseado no histórico
    ultimos_12 = numeros[-12:] if len(numeros) >= 12 else numeros
    contagem_recente = Counter(ultimos_12)
    numeros_quentes = [num for num, count in contagem_recente.most_common(6) if count >= 2]  # Aumentado para 6
    
    # NÚMEROS COM ATRASO (não saem há mais de 6 rodadas - reduzido de 8) - baseado no histórico
    numeros_atrasados = []
    for num in range(0, 37):
        if num in numeros:
            ultima_ocorrencia = len(numeros) - 1 - numeros[::-1].index(num)
            atraso = len(numeros) - ultima_ocorrencia
            if atraso > 6:  # Reduzido de 8 para 6
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
        "numeros_quentes": numeros_quentes[:4],  # Aumentado de 3 para 4
        "padroes_repeticao": list(set(padroes_repeticao))[:3],  # Aumentado de 2 para 3
        "sequencias_vizinhanca": list(set(sequencias_vizinhanca))[:4],  # Aumentado de 3 para 4
        "numeros_atrasados": numeros_atrasados[:4],  # Aumentado de 3 para 4
        "cores_alternadas": cores_alternadas[:3],  # Aumentado de 2 para 3
        "ultima_cor": ultima_cor if len(numeros) >= 1 else "indefinido",
        "total_analisado": len(numeros)
    }

def identificar_nucleo_assertivo(historico):
    """Versão MAIS AGRESSIVA do núcleo assertivo"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 3:  # Reduzido de 5 para 3
        return numeros
    
    analise = analisar_padroes_assertivos(historico)
    
    nucleo = set()
    
    # PRIORIDADE MÁXIMA: Números que saíram nas últimas 3 rodadas
    nucleo.update(numeros[-3:])
    
    # ADICIONAR MAIS NÚMEROS QUENTES
    nucleo.update(analise["numeros_quentes"])
    
    # ADICIONAR TODOS OS PADRÕES DE REPETIÇÃO (não limitar a 2)
    nucleo.update(analise["padroes_repeticao"])
    
    # ADICIONAR MAIS SEQUÊNCIAS DE VIZINHANÇA
    nucleo.update(analise["sequencias_vizinhanca"])
    
    # ADICIONAR MAIS NÚMEROS ATRASADOS
    if analise["numeros_atrasados"]:
        nucleo.update(analise["numeros_atrasados"][:3])  # Aumentado de 2 para 3
    
    # SE AINDA PRECISAR DE MAIS NÚMEROS, USAR MAIS HISTÓRICO
    if len(nucleo) < NUMERO_PREVISOES:
        # Usar números dos últimos 10 sorteios
        nucleo.update(numeros[-10:])
    
    # GARANTIR QUE SEMPRE TENHAMOS PELO MENOS 5 NÚMEROS
    if len(nucleo) < 5:
        # Completar com números mais frequentes
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
    if len(historico) < 5:  # Reduzido de 10 para 5
        return "RISCO_MODERADO"
    
    numeros = [h['number'] for h in historico]
    ultimos_8 = numeros[-8:]  # Reduzido de 10 para 8
    
    # Verificar quantos dos números propostos saíram recentemente
    acertos_previstos = len(set(ultimos_8) & set(entrada_proposta))
    
    if acertos_previstos >= 2:  # Reduzido de 3 para 2
        return "RISCO_BAIXO"
    elif acertos_previstos >= 1:
        return "RISCO_MODERADO"
    else:
        return "RISCO_ALTO"

def enviar_alerta_inteligente(entrada_estrategica, confianca, performance):
    """Envia alertas com base no nível de confiança BASEADO NO HISTÓRICO"""
    
    if confianca > 0.8:
        emoji = "🔥🔥"
        mensagem_tipo = "OPORTUNIDADE ALTA"
    elif confianca > 0.6:
        emoji = "🔥"
        mensagem_tipo = "BOA OPORTUNIDADE"
    else:
        emoji = "⚠️"
        mensagem_tipo = "OPORTUNIDADE MODERADA"
    
    mensagem = f"{emoji} **{mensagem_tipo}** {emoji}\n\n"
    mensagem += f"🎯 {' • '.join(map(str, sorted(entrada_estrategica)))}\n\n"
    mensagem += f"📊 Assertividade: {performance['taxa_acerto']}\n"
    mensagem += f"💪 Confiança: {int(confianca*100)}%"
    
    enviar_telegram(mensagem, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)

# =============================
# ESTRATÉGIA 100% BASEADA EM HISTÓRICO - VERSÃO MAIS AGRESSIVA
# =============================

def gerar_entrada_ultra_assertiva(previsao_completa, historico):
    """Estratégia MAIS AGRESSIVA - Sempre gerar entrada quando possível"""
    
    if not historico:
        return []
    
    # USAR APENAS O NÚCLEO ASSERTIVO BASEADO NO HISTÓRICO
    nucleo_assertivo = identificar_nucleo_assertivo(historico)
    
    # SEMPRE APLICAR FILTRO DE CONFIRMAÇÃO
    entrada_filtrada = filtrar_por_confirmacao_rapida(historico, nucleo_assertivo)
    
    # SE A ENTRADA ESTIVER VAZIA, USAR OS ÚLTIMOS NÚMEROS
    if not entrada_filtrada:
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        if numeros:
            entrada_filtrada = numeros[-NUMERO_PREVISOES:] if len(numeros) >= NUMERO_PREVISOES else numeros
    
    return entrada_filtrada[:NUMERO_PREVISOES]

def enviar_alerta_assertivo(entrada_estrategica, ultimo_numero, historico, performance):
    """Envia alerta ULTRA ASSERTIVO para Telegram BASEADO NO HISTÓRICO"""
    
    try:
        if not entrada_estrategica:
            return
        
        # Usar sistema de confiança para alerta inteligente
        confianca = st.session_state.sistema_confianca.confianca
        enviar_alerta_inteligente(entrada_estrategica, confianca, performance)
        
        # Salvar entrada atual
        st.session_state.ultima_entrada_estrategica = entrada_estrategica
        
        logging.info(f"📤 Alerta ASSERTIVO enviado: {len(entrada_estrategica)} números")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta assertivo: {e}")

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
# SISTEMA DE RECUPERAÇÃO
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

# =============================
# SISTEMA ESPECIALISTA 100% BASEADO EM HISTÓRICO
# =============================
class IA_Assertiva:
    def __init__(self):
        self.historico_analises = deque(maxlen=50)
        self.previsao_sequencial = SistemaPrevisaoSequencial()
        
    def prever_com_alta_assertividade(self, historico, ultimo_numero=None):
        """Sistema PRINCIPAL de previsão assertiva 100% BASEADO EM HISTÓRICO"""
        
        historico_size = len(historico)
        
        # SEMPRE USAR PREVISÃO SEQUENCIAL SE TIVER ÚLTIMO NÚMERO
        if ultimo_numero is not None and historico_size >= 10:
            previsao_seq = self.previsao_sequencial.gerar_previsao_sequencial(historico, ultimo_numero)
            if previsao_seq:
                logging.info(f"🎯 Previsão sequencial ativada para {ultimo_numero}")
                return previsao_seq
        
        # Fallback para o sistema original
        if historico_size >= FASE_ESPECIALISTA:
            logging.info(f"🚀 MODO ASSERTIVO ATIVO - {historico_size} registros")
            return self.modo_assertivo_avancado(historico)
        elif historico_size >= FASE_AVANCADA:
            return self.modo_assertivo_intermediario(historico)
        else:
            return self.modo_assertivo_basico(historico)
    
    def modo_assertivo_avancado(self, historico):
        """Modo AVANÇADO com análise complexa BASEADO NO HISTÓRICO"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # ANÁLISE DE PADRÕES COMPLEXOS BASEADO NO HISTÓRICO
        analise = analisar_padroes_assertivos(historico)
        
        # COMBINAÇÃO ESTRATÉGICA BASEADA NO HISTÓRICO
        previsao_final = set()
        
        # 1. NÚCLEO PRINCIPAL (histórico)
        previsao_final.update(analise["numeros_quentes"])
        previsao_final.update(analise["padroes_repeticao"])
        previsao_final.update(analise["sequencias_vizinhanca"])
        
        # 2. ANÁLISE DE TENDÊNCIAS (histórico)
        tendencias = self.analisar_tendencias_avancadas(numeros)
        previsao_final.update(tendencias[:3])
        
        # 3. PADRÕES TEMPORAIS (histórico)
        padroes_temporais = self.detectar_padroes_temporais(historico)
        previsao_final.update(padroes_temporais[:2])
        
        # 4. COMPLETAR COM NÚMEROS RECENTES (histórico)
        if len(previsao_final) < NUMERO_PREVISOES:
            previsao_final.update(numeros[-5:])
        
        # GARANTIR TAMANHO MÁXIMO
        return self.otimizar_previsao_assertiva(list(previsao_final), historico)
    
    def modo_assertivo_intermediario(self, historico):
        """Modo INTERMEDIÁRIO otimizado BASEADO NO HISTÓRICO"""
        nucleo = identificar_nucleo_assertivo(historico)
        return self.otimizar_distribuicao_apostas(nucleo, historico)
    
    def modo_assertivo_basico(self, historico):
        """Modo BÁSICO para histórico pequeno BASEADO NO HISTÓRICO"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 5:
            # No início, usar apenas os números que já saíram
            return numeros[-NUMERO_PREVISOES:] if len(numeros) >= NUMERO_PREVISOES else numeros
        
        # ESTRATÉGIA SIMPLES MAS EFETIVA BASEADA NO HISTÓRICO
        previsao = set()
        
        # Últimos números (histórico)
        previsao.update(numeros[-3:])
        
        # Vizinhos dos últimos (histórico)
        for num in numeros[-2:]:
            previsao.update(obter_vizinhos_fisicos(num)[:2])
        
        # Números quentes (histórico)
        ultimos_10 = numeros[-10:] if len(numeros) >= 10 else numeros
        contagem_recente = Counter(ultimos_10)
        numeros_quentes = [num for num, count in contagem_recente.most_common(4) if count >= 2]
        previsao.update(numeros_quentes)
        
        # Completar com números mais frequentes (histórico)
        if len(previsao) < NUMERO_PREVISOES:
            frequentes_geral = Counter(numeros).most_common(10)
            for num, freq in frequentes_geral:
                if len(previsao) < NUMERO_PREVISOES and num not in previsao:
                    previsao.add(num)
        
        return list(previsao)[:NUMERO_PREVISOES]
    
    def analisar_tendencias_avancadas(self, numeros):
        """Análise de tendências complexas BASEADA NO HISTÓRICO"""
        if len(numeros) < 10:
            return []
        
        tendencias = []
        
        # Tendência de repetição em ciclos curtos (histórico)
        for i in range(len(numeros) - 4):
            if numeros[i] == numeros[i+2]:
                tendencias.append(numeros[i])
        
        # Tendência de alternância (histórico)
        for i in range(len(numeros) - 3):
            if (numeros[i] in PRIMEIRA_DUZIA and numeros[i+1] in TERCEIRA_DUZIA and 
                numeros[i+2] in PRIMEIRA_DUZIA):
                tendencias.extend([n for n in PRIMEIRA_DUZIA if n not in tendencias][:2])
            elif (numeros[i] in TERCEIRA_DUZIA and numeros[i+1] in PRIMEIRA_DUZIA and 
                  numeros[i+2] in TERCEIRA_DUZIA):
                tendencias.extend([n for n in TERCEIRA_DUZIA if n not in tendencias][:2])
        
        return list(set(tendencias))[:5]
    
    def detectar_padroes_temporais(self, historico):
        """Detecta padrões baseados em tempo BASEADO NO HISTÓRICO"""
        try:
            padroes = []
            
            # Agrupar por minutos (padrões de horário) - histórico
            for registro in historico[-20:]:
                if 'timestamp' in registro:
                    try:
                        hora = datetime.fromisoformat(registro['timestamp'].replace('Z', '+00:00')).minute
                        # Padrão: números que saem em minutos específicos
                        if hora % 5 == 0:  # Minutos múltiplos de 5
                            padroes.append(registro['number'])
                    except:
                        continue
            
            return list(set(padroes))[:3]
        except:
            return []
    
    def otimizar_distribuicao_apostas(self, nucleo_assertivo, historico):
        """Otimiza a distribuição dos 8 números estrategicamente BASEADO NO HISTÓRICO"""
        
        if len(nucleo_assertivo) >= NUMERO_PREVISOES:
            return nucleo_assertivo[:NUMERO_PREVISOES]
        
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # Completar com números baseados no histórico
        complementar = []
        
        # 1. Últimos números sorteados
        complementar.extend([num for num in numeros[-10:] if num not in nucleo_assertivo])
        
        # 2. Números quentes recentes
        ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
        contagem_recente = Counter(ultimos_15)
        numeros_quentes = [num for num, count in contagem_recente.most_common(10) 
                          if count >= 2 and num not in nucleo_assertivo]
        complementar.extend(numeros_quentes)
        
        # 3. Números com melhor frequência histórica
        frequentes_geral = Counter(numeros).most_common(15)
        for num, freq in frequentes_geral:
            if num not in nucleo_assertivo and num not in complementar:
                complementar.append(num)
                if len(nucleo_assertivo) + len(complementar) >= NUMERO_PREVISOES:
                    break
        
        # Combinar e retornar
        resultado = list(nucleo_assertivo) + complementar
        return resultado[:NUMERO_PREVISOES]
    
    def otimizar_previsao_assertiva(self, previsao, historico):
        """Otimização FINAL da previsão BASEADA NO HISTÓRICO"""
        if len(previsao) <= NUMERO_PREVISOES:
            return previsao
        
        # FILTRAR PELA ESTRATÉGIA DE CONFIRMAÇÃO BASEADA NO HISTÓRICO
        return filtrar_por_confirmacao_rapida(historico, previsao)
    
    def get_performance_sequencial(self):
        """Retorna performance do sistema sequencial"""
        return self.previsao_sequencial.get_performance_sequencial()

# =============================
# GESTOR PRINCIPAL 100% BASEADO EM HISTÓRICO
# =============================
class GestorAssertivo:
    def __init__(self):
        self.ia_assertiva = IA_Assertiva()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
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
# STREAMLIT APP 100% BASEADO EM HISTÓRICO
# =============================
st.set_page_config(
    page_title="Roleta - IA Baseada em Histórico", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 SISTEMA 100% BASEADO EM HISTÓRICO")
st.markdown("### **Estratégia com 8 Números Baseada Exclusivamente no Histórico**")

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
# PROCESSAMENTO PRINCIPAL 100% BASEADO EM HISTÓRICO - VERSÃO MAIS AGRESSIVA
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

        # VERIFICAR ACERTO DA PREVISÃO SEQUENCIAL ANTERIOR
        if st.session_state.ultimo_numero and len(st.session_state.gestor.historico) > 1:
            # Usar o penúltimo número para verificar a previsão sequencial
            numeros_historico = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
            if len(numeros_historico) >= 2:
                penultimo_numero = numeros_historico[-2]
                # Verificar se a previsão sequencial anterior acertou
                st.session_state.gestor.ia_assertiva.previsao_sequencial.verificar_acerto_sequencial(
                    st.session_state.previsao_atual, numero_real
                )

        # GERAR NOVA PREVISÃO BASEADA NO HISTÓRICO - AGORA COM PREVISÃO SEQUENCIAL
        nova_previsao = st.session_state.gestor.gerar_previsao_assertiva(st.session_state.ultimo_numero)
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # GERAR ENTRADA ULTRA ASSERTIVA BASEADA NO HISTÓRICO
        entrada_assertiva = gerar_entrada_ultra_assertiva(
            st.session_state.previsao_atual, 
            list(st.session_state.gestor.historico)
        )
        
        # Calcular performance
        total = st.session_state.acertos + st.session_state.erros
        taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
        performance = {
            'acertos': st.session_state.acertos,
            'erros': st.session_state.erros,
            'taxa_acerto': f"{taxa_acerto:.1f}%"
        }
        
        # LÓGICA MAIS AGRESSIVA DE DECISÃO
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
        
        # DECISÃO FINAL DE ENTRADA - CRITÉRIOS MAIS FLEXÍVEIS
        deve_entrar = st.session_state.gestor_risco.deve_entrar(
            risco_entrada, 
            confianca_atual,
            len(st.session_state.gestor.historico)
        )
        
        # FORÇAR ENTRADA EM CONDIÇÕES ESPECÍFICAS
        if not deve_entrar:
            # FORÇAR ENTRADA se risco for BAIXO mesmo com confiança baixa
            if risco_entrada == "RISCO_BAIXO":
                deve_entrar = True
                logging.info("🔥 Entrada forçada - Risco BAIXO detectado")
            
            # FORÇAR ENTRADA se temos um padrão muito forte detectado
            analise = analisar_padroes_assertivos(list(st.session_state.gestor.historico))
            if len(analise.get("padroes_repeticao", [])) >= 2:
                deve_entrar = True
                logging.info("🔥 Entrada forçada - Padrão forte detectado")
            
            # FORÇAR ENTRADA em modo recuperação
            if modo_recuperacao and risco_entrada in ["RISCO_BAIXO", "RISCO_MODERADO"]:
                deve_entrar = True
                logging.info("🔄 Entrada forçada - Modo recuperação ativo")
        
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
# INTERFACE STREAMLIT 100% BASEADA EM HISTÓRICO
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

# NOVA SEÇÃO: PREVISÃO SEQUENCIAL
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
    numeros_historico = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
    
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
    st.success(f"**🔥 {len(previsao_valida)} NÚMEROS SELECIONADOS DO HISTÓRICO **")
    
    # Display IMPACTANTE
    st.markdown(f"### **{'  •  '.join(map(str, sorted(previsao_valida)))}**")
    
    st.write(f"**Estratégia:** {analise['estrategia_ativa']}")
    
    if analise['numeros_quentes']:
        st.write(f"**Números Quentes:** {', '.join(map(str, analise['numeros_quentes']))}")
    
else:
    st.warning("⚠️ Coletando dados históricos...")
    # Usar últimos números do histórico como fallback
    numeros = [h['number'] for h in st.session_state.gestor.historico if h.get('number') is not None]
    st.session_state.previsao_atual = numeros[-NUMERO_PREVISOES:] if len(numeros) >= NUMERO_PREVISOES else numeros

# ENTRADA ASSERTIVA BASEADA EM HISTÓRICO
st.markdown("---")
st.subheader("🎯 ENTRADA PARA TELEGRAM (Baseada em Histórico)")

entrada_assertiva = gerar_entrada_ultra_assertiva(
    st.session_state.previsao_atual, 
    list(st.session_state.gestor.historico)
)

if entrada_assertiva:
    # Verificar condições antes de recomendar entrada
    risco_entrada = analisar_risco_entrada(list(st.session_state.gestor.historico), entrada_assertiva)
    confianca_atual = st.session_state.sistema_confianca.confianca
    modo_recuperacao = verificar_estrategia_recuperacao(
        list(st.session_state.gestor.historico), 
        st.session_state.ultimos_resultados
    )
    
    # LÓGICA MAIS FLEXÍVEL PARA RECOMENDAÇÃO NA INTERFACE
    deve_recomendar = (
        risco_entrada == "RISCO_BAIXO" or 
        (risco_entrada == "RISCO_MODERADO" and confianca_atual > 0.4) or
        modo_recuperacao
    )
    
    if deve_recomendar:
        st.success(f"**🔔 {len(entrada_assertiva)} NÚMEROS CONFIRMADOS DO HISTÓRICO**")
        
        # Mostrar mensagem do Telegram
        numeros_ordenados = sorted(entrada_assertiva)
        mensagem_telegram = f"🎯 ENTRADA BASEADA EM HISTÓRICO 🎯\n\n🔥 {' • '.join(map(str, numeros_ordenados))} 🔥"
        
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
    if st.button("🗑️ Reiniciar"):
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        st.session_state.gestor.historico.clear()
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.session_state.ultima_entrada_estrategica = []
        st.session_state.sistema_confianca = SistemaConfianca()
        st.session_state.gestor_risco = SistemaGestaoRisco()
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
        else:
            st.info("📊 Histórico ainda vazio")

st.markdown("---")
st.markdown("### 🚀 **SISTEMA 100% BASEADO EM HISTÓRICO ATIVADO**")
st.markdown("*Estratégia de 8 números baseada exclusivamente no histórico de sorteios*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Sistema Baseado em Histórico v11.0** - *Previsão Sequencial + Zero números fixos*")
