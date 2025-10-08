# RoletaHybridIA.py - SISTEMA ESPECIALISTA 450+ COM ALERTAS SIMPLES - VERSÃO OTIMIZADA
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
# CONFIGURAÇÃO ESPECIALISTA - 450+ REGISTROS
# =============================
MIN_HISTORICO_TREINAMENTO = 200
NUMERO_PREVISOES = 12  # REDUZIDO DE 15 PARA 12

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

def analisar_duzias_colunas_otimizado(historico):
    """Análise OTIMIZADA com foco em tendências fortes"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 20:
        return {"duzias_quentes": [2], "colunas_quentes": [2]}
    
    # Analisar últimos 30 números para tendências mais atuais
    ultimos_numeros = numeros[-30:]
    
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
    
    # Apenas considerar como "quente" se tiver pelo menos 30% mais que a média
    total = len(ultimos_numeros)
    media_esperada_duzia = total / 3
    media_esperada_coluna = total / 3
    
    duzias_quentes = []
    colunas_quentes = []
    
    for duzia, count in contagem_duzias.items():
        if count > media_esperada_duzia * 1.3:  # 30% acima da média
            duzias_quentes.append(duzia)
    
    for coluna, count in contagem_colunas.items():
        if count > media_esperada_coluna * 1.3:  # 30% acima da média
            colunas_quentes.append(coluna)
    
    # Fallback se nenhuma estiver quente
    if not duzias_quentes:
        duzias_quentes = [max(contagem_duzias.items(), key=lambda x: x[1])[0]]
    if not colunas_quentes:
        colunas_quentes = [max(contagem_colunas.items(), key=lambda x: x[1])[0]]
    
    return {
        "duzias_quentes": duzias_quentes,
        "colunas_quentes": colunas_quentes,
        "contagem_duzias": contagem_duzias,
        "contagem_colunas": contagem_colunas
    }

# =============================
# ESTRATÉGIA DE ALERTAS TELEGRAM OTIMIZADA
# =============================
def identificar_melhores_numeros_otimizado(previsao, historico):
    """Estratégia OTIMIZADA para selecionar os números mais promissores"""
    
    if not historico:
        return previsao[:8]  # Reduzir para números mais confidentes
    
    numeros_historico = [h['number'] for h in historico if h.get('number') is not None]
    
    # PESOS MAIS BEM CALIBRADOS
    scores = {}
    
    for numero in previsao:
        score = 0
        
        # Fator 1: FREQUÊNCIA RECENTE (últimos 15 sorteios) - MAIS PESO
        freq_recente = numeros_historico[-15:].count(numero)
        score += freq_recente * 0.5  # Aumentado de 0.3 para 0.5
        
        # Fator 2: ATRASO - números que não saem há mais tempo
        if numero in numeros_historico:
            ultima_posicao = len(numeros_historico) - 1 - numeros_historico[::-1].index(numero)
            atraso = len(numeros_historico) - ultima_posicao
            if atraso > 10:  # Se não sai há mais de 10 rodadas
                score += min(atraso * 0.1, 2.0)  # Bônus progressivo
        
        # Fator 3: PADRÕES DE VIZINHANÇA FORTE
        for num_recente in numeros_historico[-3:]:  # Apenas últimos 3
            vizinhos = obter_vizinhos_fisicos(num_recente)
            if numero in vizinhos:
                score += 0.25  # Aumentado de 0.15 para 0.25
        
        # Fator 4: POSIÇÃO NA PREVISÃO ORIGINAL (menos peso)
        try:
            posicao = previsao.index(numero)
            score += (len(previsao) - posicao) * 0.1  # Reduzido de 0.2 para 0.1
        except:
            pass
        
        scores[numero] = score
    
    # SELECIONAR APENAS OS TOP 8 COM SCORE MÍNIMO
    melhores = [num for num, score in sorted(scores.items(), key=lambda x: x[1], reverse=True) 
                if score > 0.3][:8]
    
    return melhores if melhores else previsao[:8]

def balancear_entrada_otimizada(entrada):
    """Balanceamento OTIMIZADO - Foco em qualidade"""
    
    if not entrada:
        return []
    
    entrada_balanceada = []
    numeros_por_duzia = {1: 0, 2: 0, 3: 0}
    
    # Garantir representação equilibrada mas priorizando os melhores
    for num in entrada:
        if num in PRIMEIRA_DUZIA and numeros_por_duzia[1] < 4:
            entrada_balanceada.append(num)
            numeros_por_duzia[1] += 1
        elif num in SEGUNDA_DUZIA and numeros_por_duzia[2] < 4:
            entrada_balanceada.append(num)
            numeros_por_duzia[2] += 1
        elif num in TERCEIRA_DUZIA and numeros_por_duzia[3] < 4:
            entrada_balanceada.append(num)
            numeros_por_duzia[3] += 1
    
    # Adicionar zero estrategicamente
    if 0 in entrada and 0 not in entrada_balanceada and len(entrada_balanceada) < 12:
        entrada_balanceada.append(0)
    
    # Completar com melhores da entrada original se necessário
    if len(entrada_balanceada) < 10:
        for num in entrada:
            if num not in entrada_balanceada and len(entrada_balanceada) < 12:
                entrada_balanceada.append(num)
    
    return entrada_balanceada

def verificar_padroes_confirmados(historico, previsao):
    """Verifica se os padrões estão confirmados por múltiplas análises"""
    
    if len(historico) < 30:
        return previsao
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    # Análise de confirmação múltipla
    previsao_filtrada = []
    
    for numero in previsao:
        confirmacoes = 0
        
        # Confirmação 1: Frequência recente
        if numeros[-20:].count(numero) >= 1:
            confirmacoes += 1
        
        # Confirmação 2: Padrão de vizinhança
        ultimos_5 = numeros[-5:]
        for num_recente in ultimos_5:
            if numero in obter_vizinhos_fisicos(num_recente):
                confirmacoes += 1
                break
        
        # Confirmação 3: Tendência de duzia/coluna
        analise = analisar_duzias_colunas_otimizado(historico)
        duzias_quentes = analise.get("duzias_quentes", [])
        colunas_quentes = analise.get("colunas_quentes", [])
        
        if (numero in PRIMEIRA_DUZIA and 1 in duzias_quentes) or \
           (numero in SEGUNDA_DUZIA and 2 in duzias_quentes) or \
           (numero in TERCEIRA_DUZIA and 3 in duzias_quentes):
            confirmacoes += 1
        
        if (numero in COLUNA_1 and 1 in colunas_quentes) or \
           (numero in COLUNA_2 and 2 in colunas_quentes) or \
           (numero in COLUNA_3 and 3 in colunas_quentes):
            confirmacoes += 1
        
        # Apenas incluir números com pelo menos 2 confirmações
        if confirmacoes >= 2:
            previsao_filtrada.append(numero)
    
    return previsao_filtrada if previsao_filtrada else previsao[:8]

def gerar_entrada_estrategica_otimizada(previsao_completa, historico):
    """Estratégia OTIMIZADA - Menos números, mais qualidade"""
    
    if not previsao_completa:
        return []
    
    # 1. IDENTIFICAR OS 8 MELHORES (reduzido de 15)
    oito_melhores = identificar_melhores_numeros_otimizado(previsao_completa, historico)
    
    # 2. ADICIONAR VIZINHOS ESTRATÉGICOS (apenas 1 vizinho por número)
    entrada_final = set()
    
    for numero in oito_melhores:
        entrada_final.add(numero)
        
        # Apenas 1 vizinho mais promissor
        vizinhos = obter_vizinhos_fisicos(numero)
        if vizinhos:
            # Escolher vizinho baseado em frequência recente
            numeros_recentes = [h['number'] for h in historico[-20:]] if historico else []
            vizinho_scores = {}
            
            for vizinho in vizinhos[:3]:  # Apenas primeiros 3 vizinhos
                score = numeros_recentes.count(vizinho) * 0.2
                vizinho_scores[vizinho] = score
            
            if vizinho_scores:
                melhor_vizinho = max(vizinho_scores.items(), key=lambda x: x[1])[0]
                entrada_final.add(melhor_vizinho)
    
    # 3. LIMITAR A 12 NÚMEROS NO MÁXIMO (reduzido de 15)
    entrada_balanceada = balancear_entrada_otimizada(list(entrada_final))
    
    # 4. APLICAR FILTRO DE CONFIRMAÇÃO
    entrada_filtrada = verificar_padroes_confirmados(historico, entrada_balanceada)
    
    return entrada_filtrada[:12]

def enviar_alerta_canal_alternativo(entrada_estrategica, ultimo_numero, historico, performance):
    """Envia alerta SIMPLES e ORDENADO para o canal alternativo do Telegram"""
    
    try:
        if not entrada_estrategica:
            return
        
        # MENSAGEM SIMPLES COM EMOJIS E NÚMEROS ORDENADOS
        mensagem = "🎯 **PREVISÃO ESTRATÉGICA**\n\n"
        
        # Ordenar números do menor para o maior
        numeros_ordenados = sorted(entrada_estrategica)
        metade = len(numeros_ordenados) // 2
        
        linha1 = numeros_ordenados[:metade]
        linha2 = numeros_ordenados[metade:]
        
        # Formatar primeira linha
        mensagem += "🔢 "
        mensagem += " - ".join(map(str, linha1))
        
        # Segunda linha (se houver)
        if linha2:
            mensagem += "\n🔢 "
            mensagem += " - ".join(map(str, linha2))
        
        # Adicionar performance
        mensagem += f"\n\n📊 Performance: {performance['taxa_acerto']}"
        
        # ENVIAR PARA TELEGRAM
        enviar_telegram(mensagem, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        
        # Salvar entrada atual para verificação futura
        st.session_state.ultima_entrada_estrategica = entrada_estrategica
        
        logging.info(f"📤 Alerta otimizado enviado: {len(entrada_estrategica)} números confirmados")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta otimizado: {e}")

def verificar_resultado_entrada_anterior(numero_sorteado):
    """Verifica se o número sorteado estava na entrada anterior - MENSAGEM SIMPLES"""
    
    entrada_anterior = st.session_state.get('ultima_entrada_estrategica', [])
    
    if not entrada_anterior or numero_sorteado is None:
        return None
    
    if numero_sorteado in entrada_anterior:
        # GREEN - mensagem simples
        mensagem_green = f"✅ **GREEN!** {numero_sorteado}"
        enviar_telegram(mensagem_green, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        return "GREEN"
    else:
        # RED - mensagem simples
        mensagem_red = f"❌ **RED** {numero_sorteado}"
        enviar_telegram(mensagem_red, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        return "RED"

# =============================
# SISTEMA ESPECIALISTA 450+ OTIMIZADO
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

class Hybrid_IA_450_Plus_Otimizado:
    def __init__(self):
        self.pattern_analyzer = Pattern_Analyzer_Especialista()
        self.xgb_especialista = XGBoost_Especialista()
        
    def prever_com_historio_longo(self, historico):
        """Sistema especializado para 450+ registros - OTIMIZADO"""
        historico_size = len(historico)
        
        if historico_size >= MIN_HISTORICO_TREINAMENTO:
            logging.info(f"🚀 ATIVANDO MODO ESPECIALISTA - {historico_size} REGISTROS")
            
            # 1. Análise profunda de padrões
            analise_profunda = self.pattern_analyzer.analisar_padroes_profundos(historico)
            
            # 2. Predição especializada
            probs_xgb = self.xgb_especialista.predict_com_450_plus(historico)
            
            # 3. Combinação inteligente OTIMIZADA
            previsao_final = self.combinar_previsoes_especialistas_otimizado(analise_profunda, probs_xgb, historico)
            
            logging.info(f"🎯 MODO ESPECIALISTA: {analise_profunda['total_padroes']} padrões detectados → {len(previsao_final)} números")
            return previsao_final
        else:
            # Modo normal para histórico menor
            return self.prever_com_historio_normal(historico)
    
    def combinar_previsoes_especialistas_otimizado(self, analise_profunda, probs_xgb, historico):
        """Combinação OTIMIZADA para garantir qualidade"""
        scores_finais = {}
        
        # BASE MAIS ROBUSTA do XGBoost
        for num, score in probs_xgb.items():
            scores_finais[num] = score * 1.5  # Aumentar peso do XGBoost
        
        # Bônus por correlações - MAIS SELETIVO
        correlacoes = analise_profunda.get('correlacoes', {})
        for par, info in correlacoes.items():
            if info['probabilidade'] > 0.05:  # Apenas correlações fortes
                for num in par:
                    scores_finais[num] = scores_finais.get(num, 0) + info['probabilidade'] * 0.4
        
        # Bônus por sequências complexas - MAIS SELETIVO
        sequencias = analise_profunda.get('sequencias_complexas', {})
        for seq, info in sequencias.items():
            if info['confianca'] > 0.5:  # Apenas sequências muito confiantes
                scores_finais[info['proximo_esperado']] = scores_finais.get(info['proximo_esperado'], 0) + info['confianca'] * 0.6
        
        # GARANTIR MÍNIMO DE SCORES
        if len(scores_finais) < 15:
            self.preencher_scores_faltantes(scores_finais, historico)
        
        # Ordenar e selecionar - GARANTIR 12 NÚMEROS
        top_numeros = sorted(scores_finais.items(), key=lambda x: x[1], reverse=True)
        
        # Selecionar apenas números com score significativo
        selecao = [num for num, score in top_numeros if score > 0.1][:NUMERO_PREVISOES]
        
        if len(selecao) < NUMERO_PREVISOES:
            selecao = self.completar_previsao_estrategica(selecao, historico)
        
        # Aplicar filtro de confirmação final
        return verificar_padroes_confirmados(historico, selecao)
    
    def preencher_scores_faltantes(self, scores_finais, historico):
        """Preenche scores faltantes com estratégia base"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # Adicionar números recentes
        for num in numeros[-8:]:  # Reduzido de 10 para 8
            if num not in scores_finais:
                scores_finais[num] = 0.1
        
        # Adicionar vizinhos dos últimos números
        for num in numeros[-4:]:  # Reduzido de 5 para 4
            vizinhos = obter_vizinhos_fisicos(num)
            for vizinho in vizinhos[:2]:  # Apenas 2 vizinhos
                if vizinho not in scores_finais:
                    scores_finais[vizinho] = 0.08
        
        # Adicionar números de alta frequência
        freq = Counter(numeros[-25:])  # Reduzido de 30 para 25
        for num, count in freq.most_common(8):  # Reduzido de 10 para 8
            if num not in scores_finais and count >= 2:
                scores_finais[num] = 0.05 * count
    
    def completar_previsao_estrategica(self, selecao, historico):
        """Completa a previsão com números estratégicos"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        analise = analisar_duzias_colunas_otimizado(historico)
        
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
    
    def prever_com_historio_normal(self, historico):
        """Estratégia para histórico menor que 450 - OTIMIZADA"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 10:
            return self.estrategia_inicial_balanceada()
        
        previsao = set()
        analise = analisar_duzias_colunas_otimizado(historico)
        
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
                previsao.update(interseccao[:2])  # Reduzido de 3 para 2
        
        # Adicionar números recentes
        previsao.update(numeros[-4:])  # Reduzido de 5 para 4
        
        # Adicionar números frequentes
        freq = Counter(numeros[-15:])  # Reduzido de 20 para 15
        numeros_quentes = [num for num, count in freq.most_common(4) if count >= 2]  # Reduzido de 5 para 4
        previsao.update(numeros_quentes)
        
        # Completar com números balanceados
        if len(previsao) < NUMERO_PREVISOES:
            balanceados = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]  # Foco na coluna do meio
            for num in balanceados:
                if num not in previsao and len(previsao) < NUMERO_PREVISOES:
                    previsao.add(num)
        
        previsao.add(0)
        
        # Aplicar filtro de confirmação
        previsao_filtrada = verificar_padroes_confirmados(historico, list(previsao))
        
        return previsao_filtrada[:NUMERO_PREVISOES]
    
    def estrategia_inicial_balanceada(self):
        """Estratégia inicial balanceada - OTIMIZADA"""
        # Seleção mais conservadora e estratégica
        numeros_estrategicos = [
            # Coluna do meio (mais equilibrada)
            2, 5, 8, 11, 14, 17, 20, 23,
            # Zero e alguns números chave
            0, 7, 13, 19, 25
        ]
        return validar_previsao(numeros_estrategicos)[:NUMERO_PREVISOES]

# =============================
# GESTOR PRINCIPAL OTIMIZADO
# =============================
class GestorHybridIA_Especialista_Otimizado:
    def __init__(self):
        self.hybrid_system = Hybrid_IA_450_Plus_Otimizado()
        self.historico = deque(carregar_historico(), maxlen=1000)
        
    def adicionar_numero(self, numero_dict):
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        try:
            previsao = self.hybrid_system.prever_com_historio_longo(self.historico)
            previsao_validada = validar_previsao(previsao)
            
            # GARANTIR QUE SEMPRE RETORNA 12 NÚMEROS
            if len(previsao_validada) < NUMERO_PREVISOES:
                logging.warning(f"⚠️ Previsão com apenas {len(previsao_validada)} números. Completando...")
                previsao_validada = self.completar_para_12(previsao_validada)
            
            logging.info(f"✅ Previsão otimizada gerada: {len(previsao_validada)} números")
            return previsao_validada
            
        except Exception as e:
            logging.error(f"Erro crítico ao gerar previsão: {e}")
            return [0, 2, 5, 7, 8, 11, 13, 14, 17, 19, 23, 25]
    
    def completar_para_12(self, previsao):
        """Garante que sempre retorna 12 números"""
        if len(previsao) >= NUMERO_PREVISOES:
            return previsao[:NUMERO_PREVISOES]
        
        numeros_completos = set(previsao)
        
        # Adicionar números estratégicos faltantes
        numeros_estrategicos = [
            0, 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35
        ]
        
        for num in numeros_estrategicos:
            if len(numeros_completos) < NUMERO_PREVISOES:
                numeros_completos.add(num)
        
        # Se ainda não tem 12, adicionar sequencial
        if len(numeros_completos) < NUMERO_PREVISOES:
            for num in range(0, 37):
                if len(numeros_completos) < NUMERO_PREVISOES:
                    numeros_completos.add(num)
        
        return list(numeros_completos)[:NUMERO_PREVISOES]
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            
            if historico_size < FASE_INICIAL:
                return "🟡 Coletando Dados", "Estratégia Conservadora"
            elif historico_size < FASE_INTERMEDIARIA:
                return "🟠 Desenvolvendo", "Análise Seletiva"
            elif historico_size < FASE_AVANCADA:
                return "🟢 IA Avançada", "Padrões Confirmados"
            elif historico_size < FASE_ESPECIALISTA:
                return "🔵 Quase Especialista", "Otimização Final"
            else:
                return "🎯 ESPECIALISTA ATIVO", "Máxima Assertividade"
                
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
# STREAMLIT APP OTIMIZADO
# =============================
st.set_page_config(
    page_title="Roleta - IA Especialista 450+ OTIMIZADO", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Hybrid IA System - ESPECIALISTA 450+ OTIMIZADO")
st.markdown("### **Sistema com Estratégia Conservadora para Maior Assertividade**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorHybridIA_Especialista_Otimizado(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
    "status_ia": "🟡 Inicializando",
    "estrategia_atual": "Aguardando dados",
    "ultima_entrada_estrategica": [],
    "resultado_entrada_anterior": None
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL OTIMIZADO
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

        # VERIFICAR ENTRADA ANTERIOR (GREEN/RED)
        st.session_state.resultado_entrada_anterior = verificar_resultado_entrada_anterior(numero_real)

        # CONFERÊNCIA DA PREVISÃO COMPLETA
        previsao_valida = validar_previsao(st.session_state.previsao_atual)
        if previsao_valida:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
            else:
                st.session_state.erros += 1
                st.error(f"🔴 Número {numero_real} não estava na previsão")

        # GERAR NOVA PREVISÃO COMPLETA
        nova_previsao = st.session_state.gestor.gerar_previsao()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # GERAR E ENVIAR ENTRADA ESTRATÉGICA OTIMIZADA
        entrada_estrategica = gerar_entrada_estrategica_otimizada(
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
        
        # ENVIAR ALERTA OTIMIZADO PARA CANAL ALTERNATIVO
        enviar_alerta_canal_alternativo(
            entrada_estrategica, 
            numero_real, 
            list(st.session_state.gestor.historico),
            performance
        )

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    st.session_state.previsao_atual = [0, 2, 5, 7, 8, 11, 13, 14, 17, 19, 23, 25]

# =============================
# INTERFACE STREAMLIT OTIMIZADA
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
        st.success(f"✅ **ENTRADA ANTERIOR: GREEN!** Número {st.session_state.ultimo_numero} acertado!")
    else:
        st.error(f"❌ **ENTRADA ANTERIOR: RED** Número {st.session_state.ultimo_numero} não estava na entrada")

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
    st.caption("🟢 Sistema analisando padrões complexos com filtro de confirmação")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL - SISTEMA OTIMIZADO")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    if analise["modo_especialista"]:
        if len(previsao_valida) == NUMERO_PREVISOES:
            st.success(f"**🚀 {len(previsao_valida)} NÚMEROS PREVISTOS PELO ESPECIALISTA**")
        else:
            st.warning(f"**⚠️ {len(previsao_valida)} NÚMEROS PREVISTOS (Sistema Conservador)**")
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
    st.session_state.previsao_atual = [0, 2, 5, 7, 8, 11, 13, 14, 17, 19, 23, 25]

# ENTRADA ESTRATÉGICA OTIMIZADA
st.markdown("---")
st.subheader("🎯 ENTRADA ESTRATÉGICA OTIMIZADA")

entrada_estrategica = gerar_entrada_estrategica_otimizada(
    st.session_state.previsao_atual, 
    list(st.session_state.gestor.historico)
)

if entrada_estrategica:
    st.success(f"**🔔 {len(entrada_estrategica)} NÚMEROS CONFIRMADOS PARA TELEGRAM**")
    
    # Mostrar como será enviado para o Telegram
    numeros_ordenados = sorted(entrada_estrategica)
    metade = len(numeros_ordenados) // 2
    
    linha1 = numeros_ordenados[:metade]
    linha2 = numeros_ordenados[metade:]
    
    st.write("**📤 Como será enviado para Telegram:**")
    st.code(f"🎯 PREVISÃO ESTRATÉGICA\n\n🔢 {' - '.join(map(str, linha1))}\n🔢 {' - '.join(map(str, linha2))}\n\n📊 Performance: {((st.session_state.acertos/(st.session_state.acertos+st.session_state.erros)*100) if (st.session_state.acertos+st.session_state.erros) > 0 else 0):.1f}%", language=None)
    
    # Botão para forçar envio
    if st.button("📤 Enviar Alerta para Telegram"):
        performance = {
            'acertos': st.session_state.acertos,
            'erros': st.session_state.erros,
            'taxa_acerto': f"{(st.session_state.acertos/(st.session_state.acertos+st.session_state.erros)*100):.1f}%" if (st.session_state.acertos+st.session_state.erros) > 0 else "0%"
        }
        
        enviar_alerta_canal_alternativo(
            entrada_estrategica, 
            st.session_state.ultimo_numero, 
            list(st.session_state.gestor.historico),
            performance
        )
        st.success("✅ Alerta otimizado enviado para Telegram!")
else:
    st.warning("⏳ Gerando entrada estratégica otimizada...")

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
        st.session_state.ultima_entrada_estrategica = []
        st.rerun()

st.markdown("---")
st.markdown("### 🚀 **Sistema Especialista Otimizado - Estratégia Conservadora**")
st.markdown("*Menos números, mais qualidade - Foco em padrões confirmados*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Hybrid IA System v8.0** - *Especialista 450+ Otimizado para Maior Assertividade*")
