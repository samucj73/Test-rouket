# RoletaHybridIA.py - SISTEMA COM PROBABILIDADES BASEADAS NA MÉDIA REAL (3.5-4%)
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
# Configurações BASEADAS NA MÉDIA REAL
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
CICLO_PREVISAO = 1
CONFIANCA_MINIMA = 0.03  # 3% de confiança mínima - BASEADA NA MÉDIA REAL

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# FUNÇÕES UTILITÁRIAS (MANTIDAS)
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
# CONTEXT PREDICTOR - BASEADO NA MÉDIA REAL (3.5-4%)
# =============================
class Context_Predictor_Média_Real:
    def __init__(self):
        self.context_history = {}
        self.arquivo_contexto = CONTEXTO_PATH
        self.ultimos_numeros = deque(maxlen=100)
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

    def prever_baseado_na_media_real(self, ultimo_numero, top_n=10):
        """ESTRATÉGIA BASEADA NA MÉDIA REAL - 3.5-4%"""
        try:
            previsao_final = set()
            
            # 1. PADRÕES ACIMA DA MÉDIA (prob > 3.5%)
            padroes_acima_media = self.identificar_padroes_acima_media(ultimo_numero)
            for padrao in padroes_acima_media[:5]:
                if padrao['proximo'] not in previsao_final:
                    previsao_final.add(padrao['proximo'])
                    logging.info(f"📊 PADRÃO ACIMA DA MÉDIA: {ultimo_numero} → {padrao['proximo']} ({padrao['probabilidade']:.1%})")
            
            # 2. NÚMEROS MAIS FREQUENTES (baseado na média)
            numeros_frequentes = self.get_numeros_mais_frequentes_global(4)
            for num in numeros_frequentes:
                if num not in previsao_final:
                    previsao_final.add(num)
            
            # 3. VIZINHANÇA FÍSICA
            vizinhos = obter_vizinhos_fisicos(ultimo_numero)
            for vizinho in vizinhos[:3]:
                if vizinho not in previsao_final:
                    previsao_final.add(vizinho)
            
            # 4. NÚMEROS RECENTES (últimos 20 sorteios)
            numeros_recentes = self.analisar_ultimos_numeros(3)
            for num in numeros_recentes:
                if num not in previsao_final:
                    previsao_final.add(num)
            
            # 5. COMPLETAR ATÉ 10 NÚMEROS
            if len(previsao_final) < top_n:
                complemento = self.get_complemento_estatistico(ultimo_numero, top_n - len(previsao_final))
                for num in complemento:
                    if num not in previsao_final:
                        previsao_final.add(num)
            
            resultado = list(previsao_final)
            
            # CALCULAR CONFIANÇA BASEADA NA MÉDIA REAL (3.5-4%)
            media_padroes = self.calcular_media_padroes()
            confianca_base = max(3.0, min(media_padroes * 1.1, 4.5))  # 10% acima da média, máximo 4.5%
            
            # Ajuste baseado na quantidade de padrões encontrados
            if len(padroes_acima_media) > 2:
                confianca_final = min(confianca_base * 1.2, 5.0)
            else:
                confianca_final = confianca_base
                
            # Garantir range 3.0-4.5%
            confianca_final = max(3.0, min(confianca_final, 4.5))
            
            logging.info(f"🎯 PREVISÃO BASEADA NA MÉDIA: {ultimo_numero} → {resultado} | Confiança: {confianca_final:.1f}% | Média: {media_padroes:.1f}%")
            return resultado[:top_n], confianca_final
            
        except Exception as e:
            logging.error(f"Erro na previsão baseada na média: {e}")
            fallback = self.get_complemento_estatistico(ultimo_numero, top_n)
            media_padroes = self.calcular_media_padroes()
            return fallback, max(3.0, media_padroes)

    def identificar_padroes_acima_media(self, ultimo_numero):
        """Identifica padrões com probabilidade acima da média"""
        padroes_acima_media = []
        media_global = self.calcular_media_padroes() / 100  # Converter para decimal
        
        # PADRÕES DO ÚLTIMO NÚMERO
        if ultimo_numero in self.context_history:
            contexto = self.context_history[ultimo_numero]
            total = sum(contexto.values())
            
            for proximo, count in contexto.items():
                probabilidade = count / total
                
                # CRITÉRIO: prob > média global E count >= 2
                if probabilidade > media_global and count >= 2:
                    score = probabilidade * 100
                    padroes_acima_media.append({
                        'anterior': ultimo_numero,
                        'proximo': proximo,
                        'probabilidade': probabilidade,
                        'ocorrencias': count,
                        'score': score
                    })
        
        # PADRÕES GERAIS ACIMA DA MÉDIA
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                total = sum(seguintes.values())
                for proximo, count in seguintes.items():
                    probabilidade = count / total
                    
                    if probabilidade > media_global and count >= 3:
                        score = probabilidade * 100
                        padroes_acima_media.append({
                            'anterior': anterior,
                            'proximo': proximo,
                            'probabilidade': probabilidade,
                            'ocorrencias': count,
                            'score': score
                        })
        
        # Ordenar por probabilidade
        padroes_acima_media.sort(key=lambda x: x['score'], reverse=True)
        return padroes_acima_media[:8]

    def calcular_media_padroes(self):
        """Calcula a probabilidade média de todos os padrões"""
        probabilidades = []
        
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                total = sum(seguintes.values())
                for count in seguintes.values():
                    probabilidade = count / total
                    probabilidades.append(probabilidade * 100)  # Em percentual
        
        if not probabilidades:
            return 3.5  # Valor padrão se não há dados
        
        return np.mean(probabilidades)

    def analisar_ultimos_numeros(self, quantidade):
        """Analisa os últimos números sorteados"""
        if len(self.ultimos_numeros) < 5:
            return []
        
        # Pegar os últimos 20 números
        ultimos = list(self.ultimos_numeros)[-20:]
        frequencia = Counter(ultimos)
        
        return [num for num, count in frequencia.most_common(quantidade)]

    def get_complemento_estatistico(self, ultimo_numero, quantidade):
        """Complemento baseado em estatísticas reais"""
        numeros_complemento = set()
        
        # Distribuição baseada na frequência real
        todos_numeros = list(range(0, 37))
        
        # Priorizar números que apareceram recentemente
        if len(self.ultimos_numeros) >= 10:
            ultimos_20 = list(self.ultimos_numeros)[-20:]
            frequencia_recente = Counter(ultimos_20)
            
            # Pegar números que apareceram mas não são os mais frequentes
            numeros_medio_frequentes = [num for num, count in frequencia_recente.most_common()[5:15]]
            for num in numeros_medio_frequentes[:quantidade//2]:
                numeros_complemento.add(num)
        
        # Completar com números aleatórios da roleta
        random.shuffle(todos_numeros)
        for num in todos_numeros:
            if num not in numeros_complemento and len(numeros_complemento) < quantidade:
                numeros_complemento.add(num)
        
        return list(numeros_complemento)[:quantidade]

    def get_numeros_mais_frequentes_global(self, quantidade):
        """Retorna números mais frequentes"""
        frequencia_global = Counter()
        
        for anterior, seguintes in self.context_history.items():
            for numero, count in seguintes.items():
                frequencia_global[numero] += 1
        
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
        """Estatísticas baseadas na média real"""
        total_transicoes = self.get_total_transicoes()
        
        frequencia_global = self.get_numeros_mais_frequentes_global(3)
        numeros_mais_frequentes = frequencia_global if frequencia_global else ["Nenhum"]
        
        media_padroes = self.calcular_media_padroes()
        
        # Contar padrões acima da média
        padroes_acima_media_count = 0
        media_decimal = media_padroes / 100
        
        for anterior, seguintes in self.context_history.items():
            if seguintes:
                total = sum(seguintes.values())
                for count in seguintes.values():
                    if count / total > media_decimal:
                        padroes_acima_media_count += 1
        
        return {
            'contextos_ativos': len(self.context_history),
            'total_transicoes': total_transicoes,
            'numeros_mais_frequentes': numeros_mais_frequentes,
            'media_padroes': media_padroes,
            'padroes_acima_media': padroes_acima_media_count,
            'tamanho_historico_recente': len(self.ultimos_numeros)
        }

# =============================
# GESTOR PRINCIPAL - BASEADO NA MÉDIA REAL
# =============================
class GestorEstrategiaMediaReal:
    def __init__(self):
        self.context_predictor = Context_Predictor_Média_Real()
        self.historico = deque(carregar_historico(), maxlen=5000)
        self.previsao_anterior = None
        self.ultimo_numero_processado = None
        self.contador_sorteios = 0
        self.confianca_ultima_previsao = 0
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
                
                media = self.context_predictor.calcular_media_padroes()
                logging.info(f"🚀 CONTEXTO INICIALIZADO: {transicoes_adicionadas} transições | Média: {media:.1f}%")
                
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
        """Sempre gera previsão a cada sorteio"""
        return True

    def gerar_previsao_baseada_media(self):
        """Gera previsão usando média real como base"""
        try:
            if self.ultimo_numero_processado is not None:
                previsao, confianca = self.context_predictor.prever_baseado_na_media_real(
                    self.ultimo_numero_processado, 
                    top_n=10
                )
                
                logging.info(f"🎯 PREVISÃO BASEADA NA MÉDIA: {self.ultimo_numero_processado} → {len(previsao)} números | Confiança: {confianca:.1f}%")
                return previsao, confianca
            else:
                previsao = self.context_predictor.get_numeros_mais_frequentes_global(10)
                media = self.context_predictor.calcular_media_padroes()
                return previsao, max(3.0, media)
            
        except Exception as e:
            logging.error(f"Erro na previsão baseada na média: {e}")
            return list(range(0, 10)), 3.5

    def registrar_resultado(self, acertou):
        """Registra resultado"""
        if acertou:
            self.acertos_consecutivos += 1
            self.erros_consecutivos = 0
        else:
            self.erros_consecutivos += 1
            self.acertos_consecutivos = 0

    def get_analise_media_real(self):
        """Análise baseada na média real"""
        estatisticas = self.context_predictor.get_estatisticas_contexto()
        
        previsao_atual = []
        confianca_atual = 0
        if self.ultimo_numero_processado is not None:
            previsao_atual, confianca_atual = self.context_predictor.prever_baseado_na_media_real(
                self.ultimo_numero_processado, 
                top_n=10
            )
        
        return {
            'contextos_ativos': estatisticas['contextos_ativos'],
            'total_transicoes': estatisticas['total_transicoes'],
            'ultimo_numero': self.ultimo_numero_processado,
            'previsao_atual': previsao_atual,
            'confianca_previsao_atual': confianca_atual,
            'numeros_mais_frequentes': estatisticas['numeros_mais_frequentes'],
            'media_padroes': estatisticas['media_padroes'],
            'padroes_acima_media': estatisticas['padroes_acima_media'],
            'contador_sorteios': self.contador_sorteios,
            'acertos_consecutivos': self.acertos_consecutivos,
            'erros_consecutivos': self.erros_consecutivos
        }

# =============================
# STREAMLIT APP - INTERFACE BASEADA NA MÉDIA
# =============================
st.set_page_config(
    page_title="Roleta - Baseado na Média Real", 
    page_icon="📊", 
    layout="centered"
)

st.title("📊 Sistema Baseado na Média Real")
st.markdown("### **Previsões com 3.5-4% de confiança - Refletindo a realidade estatística**")

st_autorefresh(interval=15000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorEstrategiaMediaReal(),
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
# PROCESSAMENTO PRINCIPAL BASEADO NA MÉDIA
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

        # CONFERÊNCIA
        previsao_valida = validar_previsao(st.session_state.previsao_atual)
        acertou = False
        if previsao_valida and len(previsao_valida) == 10:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.session_state.gestor.registrar_resultado(True)
                st.success(f"🎯 **GREEN!** Número {numero_real} acertado!")
                enviar_alerta_resultado(True, numero_real, st.session_state.previsao_atual, st.session_state.confianca_atual)
            else:
                st.session_state.erros += 1
                st.session_state.gestor.registrar_resultado(False)
                st.error(f"🔴 Número {numero_real} não estava na previsão")
                enviar_alerta_resultado(False, numero_real, st.session_state.previsao_atual, st.session_state.confianca_atual)

        # SEMPRE GERAR NOVA PREVISÃO
        nova_previsao, confianca = st.session_state.gestor.gerar_previsao_baseada_media()
        
        # ACEITA TODAS AS PREVISÕES (já que são baseadas na média real)
        if confianca >= CONFIANCA_MINIMA * 100:
            st.session_state.previsao_anterior = st.session_state.previsao_atual.copy()
            st.session_state.previsao_atual = validar_previsao(nova_previsao)
            st.session_state.confianca_atual = confianca
            
            # ENVIAR ALERTA TELEGRAM PARA TODAS AS PREVISÕES
            if st.session_state.previsao_atual and len(st.session_state.previsao_atual) == 10:
                try:
                    enviar_alerta_previsao(st.session_state.previsao_atual, int(confianca))
                except Exception as e:
                    logging.error(f"Erro ao enviar alerta de previsão: {e}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    st.session_state.confianca_atual = 3.5

# =============================
# INTERFACE STREAMLIT BASEADA NA MÉDIA
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Estratégia", "Média Real")
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)}")
with col3:
    ultimo_numero = st.session_state.ultimo_numero
    display_numero = ultimo_numero if ultimo_numero is not None else "-"
    st.metric("🎲 Último", display_numero)
with col4:
    st.metric("📈 Confiança Alvo", "3.5-4%")

# ANÁLISE BASEADA NA MÉDIA
st.subheader("🔍 Análise Baseada na Média Real")
analise_media = st.session_state.gestor.get_analise_media_real()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Contextos Ativos", analise_media['contextos_ativos'])
with col2:
    st.metric("📊 Transições", analise_media['total_transicoes'])
with col3:
    st.metric("📈 Média Padrões", f"{analise_media['media_padroes']:.1f}%")
with col4:
    st.metric("🔺 Padrões Acima Média", analise_media['padroes_acima_media'])

# PREVISÃO ATUAL DO SISTEMA
previsao_sistema = analise_media['previsao_atual']
confianca_sistema = analise_media['confianca_previsao_atual']

if previsao_sistema and analise_media['ultimo_numero'] is not None:
    previsao_unica = []
    numeros_vistos = set()
    for num in previsao_sistema:
        if num not in numeros_vistos:
            previsao_unica.append(num)
            numeros_vistos.add(num)
    
    if previsao_unica and len(previsao_unica) == 10:
        st.success(f"**📊 ANÁLISE APÓS {analise_media['ultimo_numero']}:**")
        
        # Formatação para 10 números (5+5)
        linha1 = previsao_unica[:5]
        linha2 = previsao_unica[5:10]
        
        linha1_str = " | ".join([f"**{num}**" for num in linha1])
        linha2_str = " | ".join([f"**{num}**" for num in linha2])
        
        st.markdown(f"### 📈 {linha1_str}")
        st.markdown(f"### 📈 {linha2_str}")
        st.caption(f"💡 **CONFIANÇA BASEADA NA MÉDIA ({confianca_sistema:.1f}%)** - Média real dos padrões: {analise_media['media_padroes']:.1f}%")
        
else:
    st.info("🔄 Calculando média real dos padrões...")

# PREVISÃO ATUAL OFICIAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL OFICIAL")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida and len(previsao_valida) == 10:
    # Classificação baseada na média
    if st.session_state.confianca_atual >= 4.0:
        status = "ACIMA DA MÉDIA"
        cor = "🟢"
    elif st.session_state.confianca_atual >= 3.5:
        status = "NA MÉDIA"
        cor = "🟡"
    else:
        status = "ABAIXO DA MÉDIA" 
        cor = "🔴"
    
    st.success(f"**{cor} PREVISÃO ATIVA - {status} ({st.session_state.confianca_atual:.1f}%)**")
    
    # Display organizado
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Linha 1:**")
        for num in sorted(previsao_valida[:5]):
            st.write(f"`{num}`")
    
    with col2:
        st.write("**Linha 2:**")
        for num in sorted(previsao_valida[5:10]):
            st.write(f"`{num}`")
    
    st.write(f"**Lista Completa:** {', '.join(map(str, sorted(previsao_valida)))}")
    
else:
    st.warning("⏳ Calculando próxima previsão baseada na média real...")

# PERFORMANCE
st.markdown("---")
st.subheader("📊 Performance Realista")

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
with st.expander("🔧 Detalhes Baseados na Média Real"):
    st.write("**🎯 ESTRATÉGIA ESTATÍSTICA:**")
    st.write("- 🔄 Previsões a cada **1 sorteio**")
    st.write("- 📊 Confiança baseada na **média real dos padrões**")
    st.write("- 🎯 Foco em **padrões acima da média** (>3.5%)")
    st.write("- 📈 **Transparência total** nas probabilidades")
    st.write("- ⚖️ **Range realista**: 3.0-4.5% de confiança")
    
    st.write("**📊 ESTATÍSTICAS REAIS:**")
    st.write(f"- Contextos ativos: {analise_media['contextos_ativos']}")
    st.write(f"- Transições analisadas: {analise_media['total_transicoes']}")
    st.write(f"- Média real dos padrões: {analise_media['media_padroes']:.1f}%")
    st.write(f"- Padrões acima da média: {analise_media['padroes_acima_media']}")
    st.write(f"- Números mais frequentes: {', '.join(map(str, analise_media['numeros_mais_frequentes']))}")
    
    st.write("**📨 SISTEMA DE ALERTAS:**")
    st.write("- 🔔 Alerta de PREVISÃO: Para todas as previsões")
    st.write("- 🟢 Alerta GREEN: Sempre que acertar")
    st.write("- 🔴 Alerta RED: Sempre que errar")

# CONTROLES
st.markdown("---")
st.subheader("⚙️ Controles do Sistema")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Forçar Nova Previsão"):
        nova_previsao, confianca = st.session_state.gestor.gerar_previsao_baseada_media()
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
st.markdown("### 📊 **Sistema Baseado na Média Real**")
st.markdown("*Previsões transparentes com 3.5-4% de confiança refletindo a realidade estatística*")

# Rodapé
st.markdown("---")
st.markdown("**📊 Estratégia Média Real v5.0** - *Probabilidades 3.5-4%*")
