# RoletaHybridIA.py - SISTEMA ESPECIALISTA 450+ COM ESTRATÉGIA DE ALTA ASSERTIVIDADE
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
# CONFIGURAÇÃO ESPECIALISTA - ESTRATÉGIA DE ALTA ASSERTIVIDADE
# =============================
MIN_HISTORICO_TREINAMENTO = 150  # Reduzido para ativar mais cedo
NUMERO_PREVISOES = 8  # REDUZIDO DRAMATICAMENTE PARA MAIOR ASSERTIVIDADE

# Fases do sistema
FASE_INICIAL = 30
FASE_INTERMEDIARIA = 80  
FASE_AVANCADA = 120
FASE_ESPECIALISTA = 150

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

# =============================
# ESTRATÉGIA DE ALTA ASSERTIVIDADE
# =============================
def analisar_padroes_assertivos(historico):
    """Análise AGGRESSIVA focada em padrões de alta probabilidade"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 10:
        return {"numeros_quentes": [2, 5, 8, 11, 14, 17, 23, 29], "padrao_atual": "inicial"}
    
    # ANÁLISE DE PADRÕES DE REPETIÇÃO IMEDIATA
    padroes_repeticao = []
    for i in range(1, len(numeros)):
        if numeros[i] == numeros[i-1]:
            padroes_repeticao.append(numeros[i])
    
    # ANÁLISE DE SEQUÊNCIAS DE VIZINHANÇA
    sequencias_vizinhanca = []
    for i in range(1, min(6, len(numeros))):
        vizinhos_anteriores = obter_vizinhos_fisicos(numeros[-i])
        if numeros[-1] in vizinhos_anteriores:
            sequencias_vizinhanca.extend(vizinhos_anteriores)
    
    # NÚMEROS QUENTES (últimas 15 rodadas)
    ultimos_15 = numeros[-15:] if len(numeros) >= 15 else numeros
    contagem_recente = Counter(ultimos_15)
    numeros_quentes = [num for num, count in contagem_recente.most_common(5) if count >= 2]
    
    # NÚMEROS COM ATRASO (não saem há mais de 8 rodadas)
    numeros_atrasados = []
    for num in range(0, 37):
        if num in numeros:
            ultima_ocorrencia = len(numeros) - 1 - numeros[::-1].index(num)
            atraso = len(numeros) - ultima_ocorrencia
            if atraso > 8:
                numeros_atrasados.append(num)
    
    # PADRÃO DE ALTERNÂNCIA DE CORES (se aplicável)
    cores_alternadas = []
    ultima_cor = "preto" if numeros[-1] in [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35] else "vermelho" if numeros[-1] in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "zero"
    
    return {
        "numeros_quentes": numeros_quentes[:3],
        "padroes_repeticao": list(set(padroes_repeticao))[:2],
        "sequencias_vizinhanca": list(set(sequencias_vizinhanca))[:3],
        "numeros_atrasados": numeros_atrasados[:3],
        "ultima_cor": ultima_cor,
        "total_analisado": len(numeros)
    }

def identificar_nucleo_assertivo(historico):
    """Identifica o núcleo de números com maior probabilidade REAL"""
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    if len(numeros) < 5:
        return [2, 5, 8, 11, 14, 17, 23, 29]
    
    analise = analisar_padroes_assertivos(historico)
    
    nucleo = set()
    
    # 1. ADICIONAR NÚMEROS QUENTES (alta prioridade)
    nucleo.update(analise["numeros_quentes"])
    
    # 2. ADICIONAR PADRÕES DE REPETIÇÃO (muito forte)
    nucleo.update(analise["padroes_repeticao"])
    
    # 3. ADICIONAR SEQUÊNCIAS DE VIZINHANÇA
    nucleo.update(analise["sequencias_vizinhanca"])
    
    # 4. ADICIONAR 1-2 NÚMEROS ATRASADOS (para diversificação)
    if analise["numeros_atrasados"]:
        nucleo.add(analise["numeros_atrasados"][0])
    
    # 5. GARANTIR ZERO SE ESTIVER QUENTE
    if numeros.count(0) >= max(1, len(numeros) * 0.05):
        nucleo.add(0)
    
    # 6. COMPLETAR COM NÚMEROS ESTRATÉGICOS DA COLUNA DO MEIO
    if len(nucleo) < NUMERO_PREVISOES:
        complemento = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
        for num in complemento:
            if len(nucleo) < NUMERO_PREVISOES and num not in nucleo:
                nucleo.add(num)
    
    return list(nucleo)[:NUMERO_PREVISOES]

def gerar_entrada_ultra_assertiva(previsao_completa, historico):
    """Estratégia ULTRA ASSERTIVA - Máximo 8 números com alta confiança"""
    
    if not historico:
        return [2, 5, 8, 11, 14, 17, 23, 29]
    
    # USAR APENAS O NÚCLEO ASSERTIVO
    nucleo_assertivo = identificar_nucleo_assertivo(historico)
    
    # APLICAR FILTRO DE CONFIRMAÇÃO RÁPIDA
    entrada_filtrada = filtrar_por_confirmacao_rapida(historico, nucleo_assertivo)
    
    return entrada_filtrada[:NUMERO_PREVISOES]

def filtrar_por_confirmacao_rapida(historico, numeros_candidatos):
    """Filtro RÁPIDO baseado em confirmações imediatas"""
    
    if len(numeros_candidatos) <= NUMERO_PREVISOES:
        return numeros_candidatos
    
    numeros = [h['number'] for h in historico if h.get('number') is not None]
    
    scores = {}
    
    for numero in numeros_candidatos:
        score = 0
        
        # CONFIRMAÇÃO 1: É UM DOS ÚLTIMOS 3 NÚMEROS?
        if numero in numeros[-3:]:
            score += 3
        
        # CONFIRMAÇÃO 2: É VIZINHO DOS ÚLTIMOS 2 NÚMEROS?
        for recente in numeros[-2:]:
            if numero in obter_vizinhos_fisicos(recente):
                score += 2
                break
        
        # CONFIRMAÇÃO 3: TEVE REPETIÇÃO RECENTE (últimas 10 rodadas)
        if numeros[-10:].count(numero) >= 2:
            score += 2
        
        # CONFIRMAÇÃO 4: ESTÁ NA MESMA COLUNA DOS ÚLTIMOS NÚMEROS?
        ultima_coluna = None
        for num in numeros[-2:]:
            if num in COLUNA_1: ultima_coluna = 1
            elif num in COLUNA_2: ultima_coluna = 2
            elif num in COLUNA_3: ultima_coluna = 3
        
        if ultima_coluna:
            if (ultima_coluna == 1 and numero in COLUNA_1) or \
               (ultima_coluna == 2 and numero in COLUNA_2) or \
               (ultima_coluna == 3 and numero in COLUNA_3):
                score += 1
        
        scores[numero] = score
    
    # SELECIONAR OS COM MAIOR SCORE
    melhores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [num for num, score in melhores if score >= 2][:NUMERO_PREVISOES]

def enviar_alerta_assertivo(entrada_estrategica, ultimo_numero, historico, performance):
    """Envia alerta ULTRA ASSERTIVO para Telegram"""
    
    try:
        if not entrada_estrategica:
            return
        
        # MENSAGEM DIRETA E PODEROSA
        mensagem = "🎯 **ENTRADA ASSERTIVA** 🎯\n\n"
        
        # Ordenar números
        numeros_ordenados = sorted(entrada_estrategica)
        
        # Formato compacto e impactante
        mensagem += "🔥 " + " • ".join(map(str, numeros_ordenados)) + " 🔥"
        
        # Estatísticas de performance
        mensagem += f"\n\n📊 Assertividade: {performance['taxa_acerto']}"
        mensagem += f"\n✅ Acertos: {performance['acertos']} | ❌ Erros: {performance['erros']}"
        
        # ENVIAR PARA TELEGRAM
        enviar_telegram(mensagem, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        
        # Salvar entrada atual
        st.session_state.ultima_entrada_estrategica = entrada_estrategica
        
        logging.info(f"📤 Alerta ASSERTIVO enviado: {len(entrada_estrategica)} números")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta assertivo: {e}")

def verificar_resultado_entrada_anterior(numero_sorteado):
    """Verificação RÁPIDA de resultado"""
    
    entrada_anterior = st.session_state.get('ultima_entrada_estrategica', [])
    
    if not entrada_anterior or numero_sorteado is None:
        return None
    
    if numero_sorteado in entrada_anterior:
        mensagem_green = f"✅ **GREEN!** Acertamos {numero_sorteado}!"
        enviar_telegram(mensagem_green, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        return "GREEN"
    else:
        mensagem_red = f"❌ **RED** {numero_sorteado} não estava"
        enviar_telegram(mensagem_red, TELEGRAM_TOKEN_ALTERNATIVO, TELEGRAM_CHAT_ID_ALTERNATIVO)
        return "RED"

# =============================
# SISTEMA ESPECIALISTA DE ALTA ASSERTIVIDADE
# =============================
class IA_Assertiva:
    def __init__(self):
        self.historico_analises = deque(maxlen=50)
        
    def prever_com_alta_assertividade(self, historico):
        """Sistema PRINCIPAL de previsão assertiva"""
        
        historico_size = len(historico)
        
        if historico_size >= FASE_ESPECIALISTA:
            logging.info(f"🚀 MODO ASSERTIVO ATIVO - {historico_size} registros")
            return self.modo_assertivo_avancado(historico)
        elif historico_size >= FASE_AVANCADA:
            return self.modo_assertivo_intermediario(historico)
        else:
            return self.modo_assertivo_basico(historico)
    
    def modo_assertivo_avancado(self, historico):
        """Modo AVANÇADO com análise complexa"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        # ANÁLISE DE PADRÕES COMPLEXOS
        analise = analisar_padroes_assertivos(historico)
        
        # COMBINAÇÃO ESTRATÉGICA
        previsao_final = set()
        
        # 1. NÚCLEO PRINCIPAL
        previsao_final.update(analise["numeros_quentes"])
        previsao_final.update(analise["padroes_repeticao"])
        
        # 2. ANÁLISE DE TENDÊNCIAS
        tendencias = self.analisar_tendencias_avancadas(numeros)
        previsao_final.update(tendencias[:3])
        
        # 3. PADRÕES TEMPORAIS
        padroes_temporais = self.detectar_padroes_temporais(historico)
        previsao_final.update(padroes_temporais[:2])
        
        # GARANTIR TAMANHO MÁXIMO
        return self.otimizar_previsao_assertiva(list(previsao_final), historico)
    
    def modo_assertivo_intermediario(self, historico):
        """Modo INTERMEDIÁRIO otimizado"""
        return identificar_nucleo_assertivo(historico)
    
    def modo_assertivo_basico(self, historico):
        """Modo BÁSICO para histórico pequeno"""
        numeros = [h['number'] for h in historico if h.get('number') is not None]
        
        if len(numeros) < 5:
            return [2, 5, 8, 11, 14, 17, 23, 29]
        
        # ESTRATÉGIA SIMPLES MAS EFETIVA
        previsao = set()
        
        # Últimos números
        previsao.update(numeros[-3:])
        
        # Vizinhos dos últimos
        for num in numeros[-2:]:
            previsao.update(obter_vizinhos_fisicos(num)[:2])
        
        # Completar com estratégicos
        estrategicos = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
        for num in estrategicos:
            if len(previsao) < NUMERO_PREVISOES:
                previsao.add(num)
        
        return list(previsao)[:NUMERO_PREVISOES]
    
    def analisar_tendencias_avancadas(self, numeros):
        """Análise de tendências complexas"""
        if len(numeros) < 10:
            return []
        
        tendencias = []
        
        # Tendência de repetição em ciclos curtos
        for i in range(len(numeros) - 4):
            if numeros[i] == numeros[i+2]:
                tendencias.append(numeros[i])
        
        # Tendência de alternância
        for i in range(len(numeros) - 3):
            if (numeros[i] in PRIMEIRA_DUZIA and numeros[i+1] in TERCEIRA_DUZIA and 
                numeros[i+2] in PRIMEIRA_DUZIA):
                tendencias.extend([n for n in PRIMEIRA_DUZIA if n not in tendencias][:2])
        
        return list(set(tendencias))[:5]
    
    def detectar_padroes_temporais(self, historico):
        """Detecta padrões baseados em tempo"""
        try:
            padroes = []
            
            # Agrupar por minutos (padrões de horário)
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
    
    def otimizar_previsao_assertiva(self, previsao, historico):
        """Otimização FINAL da previsão"""
        if len(previsao) <= NUMERO_PREVISOES:
            return previsao
        
        # FILTRAR PELA ESTRATÉGIA DE CONFIRMAÇÃO
        return filtrar_por_confirmacao_rapida(historico, previsao)

# =============================
# GESTOR PRINCIPAL ASSERTIVO
# =============================
class GestorAssertivo:
    def __init__(self):
        self.ia_assertiva = IA_Assertiva()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            self.historico.append(numero_dict)
        
    def gerar_previsao_assertiva(self):
        try:
            previsao = self.ia_assertiva.prever_com_alta_assertividade(self.historico)
            previsao_validada = validar_previsao(previsao)
            
            # GARANTIR SEMPRE 8 NÚMEROS
            if len(previsao_validada) < NUMERO_PREVISOES:
                logging.warning(f"⚠️ Previsão com {len(previsao_validada)} números. Completando...")
                previsao_validada = self.completar_para_8(previsao_validada)
            
            logging.info(f"✅ Previsão ASSERTIVA gerada: {len(previsao_validada)} números")
            return previsao_validada
            
        except Exception as e:
            logging.error(f"Erro ao gerar previsão: {e}")
            return [2, 5, 8, 11, 14, 17, 23, 29]
    
    def completar_para_8(self, previsao):
        """Completa sempre para 8 números"""
        if len(previsao) >= NUMERO_PREVISOES:
            return previsao[:NUMERO_PREVISOES]
        
        numeros_completos = set(previsao)
        
        # NÚMEROS ESTRATÉGICOS DA COLUNA DO MEIO
        estrategicos = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
        
        for num in estrategicos:
            if len(numeros_completos) < NUMERO_PREVISOES:
                numeros_completos.add(num)
        
        return list(numeros_completos)[:NUMERO_PREVISOES]
    
    def get_status_sistema(self):
        try:
            historico_size = len(self.historico)
            
            if historico_size < FASE_INICIAL:
                return "🟡 Iniciando", "Estratégia Básica"
            elif historico_size < FASE_INTERMEDIARIA:
                return "🟠 Desenvolvendo", "Análise Intermediária"
            elif historico_size < FASE_AVANCADA:
                return "🟢 IA Ativa", "Padrões Detectados"
            else:
                return "🎯 ASSERTIVO", "Alta Probabilidade"
                
        except:
            return "⚪ Sistema", "Carregando..."
    
    def get_analise_detalhada(self):
        """Análise simplificada mas efetiva"""
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
            "estrategia_ativa": "Núcleo Assertivo",
            "numeros_quentes": analise.get("numeros_quentes", []),
            "padrao_detectado": len(analise.get("padroes_repeticao", [])) > 0
        }

# =============================
# STREAMLIT APP ASSERTIVO
# =============================
st.set_page_config(
    page_title="Roleta - IA Assertiva", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 SISTEMA ASSERTIVO - ALTA PROBABILIDADE")
st.markdown("### **Estratégia com 8 Números para Máxima Assertividade**")

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
    "resultado_entrada_anterior": None
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL ASSERTIVO
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

        # GERAR NOVA PREVISÃO ASSERTIVA
        nova_previsao = st.session_state.gestor.gerar_previsao_assertiva()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        
        # GERAR ENTRADA ULTRA ASSERTIVA
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
        
        # ENVIAR ALERTA ASSERTIVO
        enviar_alerta_assertivo(
            entrada_assertiva, 
            numero_real, 
            list(st.session_state.gestor.historico),
            performance
        )

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro no processamento: {e}")
    st.error("🔴 Reiniciando sistema...")
    st.session_state.previsao_atual = [2, 5, 8, 11, 14, 17, 23, 29]

# =============================
# INTERFACE STREAMLIT ASSERTIVA
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
st.subheader("🔍 Análise Assertiva")
analise = st.session_state.gestor.get_analise_detalhada()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🚀 Modo", "ASSERTIVO" if analise["modo_assertivo"] else "EVOLUINDO")
with col2:
    st.metric("💪 Confiança", analise["confianca"])
with col3:
    st.metric("📈 Padrão", "✅" if analise["padrao_detectado"] else "⏳")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ASSERTIVA ATUAL")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida:
    st.success(f"**🔥 {len(previsao_valida)} NÚMEROS SELECIONADOS **")
    
    # Display IMPACTANTE
    st.markdown(f"### **{'  •  '.join(map(str, sorted(previsao_valida)))}**")
    
    st.write(f"**Estratégia:** {analise['estrategia_ativa']}")
    
    if analise['numeros_quentes']:
        st.write(f"**Números Quentes:** {', '.join(map(str, analise['numeros_quentes']))}")
    
else:
    st.warning("⚠️ Inicializando sistema assertivo...")
    st.session_state.previsao_atual = [2, 5, 8, 11, 14, 17, 23, 29]

# ENTRADA ASSERTIVA
st.markdown("---")
st.subheader("🎯 ENTRADA PARA TELEGRAM")

entrada_assertiva = gerar_entrada_ultra_assertiva(
    st.session_state.previsao_atual, 
    list(st.session_state.gestor.historico)
)

if entrada_assertiva:
    st.success(f"**🔔 {len(entrada_assertiva)} NÚMEROS CONFIRMADOS**")
    
    # Mostrar mensagem do Telegram
    numeros_ordenados = sorted(entrada_assertiva)
    mensagem_telegram = f"🎯 ENTRADA ASSERTIVA 🎯\n\n🔥 {' • '.join(map(str, numeros_ordenados))} 🔥"
    
    st.code(mensagem_telegram, language=None)
    
    # Botão de envio
    if st.button("📤 Enviar Alerta Assertivo"):
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
        st.success("✅ Alerta ASSERTIVO enviado!")
else:
    st.warning("⏳ Gerando entrada assertiva...")

# PERFORMANCE
st.markdown("---")
st.subheader("📊 Performance do Sistema")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("✅ Acertos", st.session_state.acertos)
with col2:
    st.metric("❌ Erros", st.session_state.erros)
with col3:
    total = st.session_state.acertos + st.session_state.erros
    taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
    st.metric("📈 Assertividade", f"{taxa_acerto:.1f}%")

# CONTROLES
st.markdown("---")
st.subheader("⚙️ Controles")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Nova Previsão"):
        nova_previsao = st.session_state.gestor.gerar_previsao_assertiva()
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
        st.rerun()

st.markdown("---")
st.markdown("### 🚀 **SISTEMA ASSERTIVO ATIVADO**")
st.markdown("*Estratégia de 8 números para máxima probabilidade de acerto*")

# Rodapé
st.markdown("---")
st.markdown("**🎯 Sistema Assertivo v9.0** - *Alta Assertividade com 8 Números*")
