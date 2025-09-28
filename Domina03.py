# Domina03.py (arquivo completo atualizado e otimizado)
import streamlit as st
import json
import os
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from typing import List, Dict, Any
import time

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_deslocamento.json"
METRICAS_PATH = "historico_metricas.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Canal principal
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# Canal alternativo para Top N Dinâmico
ALT_TELEGRAM_TOKEN = TELEGRAM_TOKEN
ALT_TELEGRAM_CHAT_ID = "-1002979544095"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

WINDOW_SIZE = 18   # janela móvel para Top N dinâmico
MIN_TOP_N = 5      # mínimo de números na Top N
MAX_TOP_N = 10     # máximo de números na Top N
MAX_PREVIEWS = 15   # limite final de previsões para reduzir custo

# =============================
# Configuração de Logging Otimizada
# =============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('roleta_ia.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_estrategia(mensagem: str, nivel: str = "info"):
    """Log estruturado para estratégias"""
    log_func = getattr(logging, nivel.lower(), logging.info)
    log_func(f"🎯 {mensagem}")

# =============================
# Classes de Gerenciamento
# =============================
class Estatisticas:
    """Gerencia estatísticas de forma eficiente"""
    def __init__(self):
        self.acertos = 0
        self.erros = 0
    
    @property
    def total(self):
        return self.acertos + self.erros
    
    @property
    def taxa_acerto(self):
        return (self.acertos / self.total * 100) if self.total > 0 else 0.0
    
    def registrar_acerto(self):
        self.acertos += 1
        log_estrategia(f"ACERTO - Taxa: {self.taxa_acerto:.1f}%")
    
    def registrar_erro(self):
        self.erros += 1
        log_estrategia(f"ERRO - Taxa: {self.taxa_acerto:.1f}%")

class EstrategiaDeslocamento:
    def __init__(self):
        self.historico = deque(maxlen=15000)
    
    def adicionar_numero(self, numero_dict: Dict[str, Any]):
        self.historico.append(numero_dict)
        log_estrategia(f"Número {numero_dict['number']} adicionado ao histórico")

# =============================
# Cache e Pré-computação
# =============================
class CacheManager:
    """Gerencia cache para melhor performance"""
    def __init__(self):
        self._vizinhos_cache = {}
        self._api_cache = None
        self._api_cache_time = 0
        self._cache_duration = 8  # segundos
    
    def get_vizinhos(self, numero: int, antes: int = 2, depois: int = 2):
        """Cache para cálculos de vizinhos"""
        key = (numero, antes, depois)
        if key not in self._vizinhos_cache:
            self._vizinhos_cache[key] = self._calcular_vizinhos(numero, antes, depois)
        return self._vizinhos_cache[key]
    
    def _calcular_vizinhos(self, numero: int, antes: int, depois: int):
        """Calcula vizinhos uma vez e cachea"""
        if numero not in ROULETTE_LAYOUT:
            return [numero]
        
        idx = ROULETTE_LAYOUT.index(numero)
        n = len(ROULETTE_LAYOUT)
        vizinhos = []
        
        for i in range(antes, 0, -1):
            vizinhos.append(ROULETTE_LAYOUT[(idx - i) % n])
        vizinhos.append(numero)
        for i in range(1, depois + 1):
            vizinhos.append(ROULETTE_LAYOUT[(idx + i) % n])
        
        return vizinhos
    
    def get_api_result(self):
        """Cache para resultados da API"""
        current_time = time.time()
        if (self._api_cache is None or 
            current_time - self._api_cache_time > self._cache_duration):
            self._api_cache = fetch_latest_result()
            self._api_cache_time = current_time
        return self._api_cache

# Inicializar cache global
cache_manager = CacheManager()

# =============================
# Funções Utilitárias Otimizadas
# =============================
def enviar_telegram(msg: str, token: str = TELEGRAM_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
    """Envia mensagem para Telegram com tratamento de erro"""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        log_estrategia(f"Telegram enviado: {msg[:80]}...")
    except Exception as e:
        log_estrategia(f"Erro Telegram: {e}", "error")

def enviar_telegram_topN(msg: str):
    """Envia para canal Top N"""
    enviar_telegram(msg, ALT_TELEGRAM_TOKEN, ALT_TELEGRAM_CHAT_ID)

def carregar_historico() -> List[Dict[str, Any]]:
    """Carrega histórico com validação robusta"""
    if not os.path.exists(HISTORICO_PATH):
        log_estrategia("Arquivo de histórico não encontrado")
        return []
    
    try:
        with open(HISTORICO_PATH, "r", encoding='utf-8') as f:
            historico = json.load(f)
        
        historico_validado = []
        for i, h in enumerate(historico):
            if isinstance(h, dict) and "number" in h:
                # Valida se o número existe no layout da roleta
                if h["number"] in ROULETTE_LAYOUT + [None]:
                    historico_validado.append(h)
            else:
                # Converte formato antigo
                historico_validado.append({"number": h, "timestamp": f"manual_{i}"})
        
        log_estrategia(f"Histórico carregado: {len(historico_validado)} registros válidos")
        return historico_validado
    except Exception as e:
        log_estrategia(f"Erro ao carregar histórico: {e}", "error")
        return []

def salvar_historico(historico: List[Dict[str, Any]]):
    """Salva histórico com tratamento de erro"""
    try:
        with open(HISTORICO_PATH, "w", encoding='utf-8') as f:
            json.dump(historico, f, indent=2)
        log_estrategia(f"Histórico salvo: {len(historico)} registros")
    except Exception as e:
        log_estrategia(f"Erro ao salvar histórico: {e}", "error")

def salvar_metricas(metricas: Dict[str, Any]):
    """Salva métricas com append seguro"""
    try:
        historico_metricas = []
        if os.path.exists(METRICAS_PATH):
            try:
                with open(METRICAS_PATH, "r", encoding='utf-8') as f:
                    historico_metricas = json.load(f)
            except Exception:
                historico_metricas = []
        
        historico_metricas.append(metricas)
        
        with open(METRICAS_PATH, "w", encoding='utf-8') as f:
            json.dump(historico_metricas, f, indent=2)
        
        log_estrategia(f"Métricas salvas: {len(historico_metricas)} registros")
    except Exception as e:
        log_estrategia(f"Erro ao salvar métricas: {e}", "error")

def fetch_latest_result() -> Dict[str, Any]:
    """Busca resultado da API com tratamento robusto"""
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=8)
        response.raise_for_status()
        data = response.json()
        
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        
        log_estrategia(f"API resultado: {number} (timestamp: {timestamp})")
        return {"number": number, "timestamp": timestamp}
        
    except requests.exceptions.Timeout:
        log_estrategia("Timeout na requisição da API", "warning")
        return None
    except Exception as e:
        log_estrategia(f"Erro na API: {e}", "error")
        return None

# Funções de vizinhos usando cache
def obter_vizinhos(numero: int, antes: int = 2, depois: int = 2):
    return cache_manager.get_vizinhos(numero, antes, depois)

def obter_vizinhos_fixos(numero: int, antes: int = 5, depois: int = 5):
    return cache_manager.get_vizinhos(numero, antes, depois)

# =============================
# IA Recorrência com RandomForest Otimizada
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=3, window=WINDOW_SIZE):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.window = window
        self.model = None
        self._ultimo_treino = 0
        self._treino_interval = 50  # Treinar a cada 50 rodadas

    def _criar_features_otimizado(self, historico: List[Dict[str, Any]]):
        """Features otimizadas com pré-alocação"""
        if len(historico) < 3:
            return None, None
        
        numeros = [h["number"] for h in historico]
        n_samples = len(numeros) - 2
        
        # Pré-aloca arrays
        X = np.zeros((n_samples, 7), dtype=int)  # 7 features
        y = np.zeros(n_samples, dtype=int)
        
        for i in range(2, len(numeros)):
            idx = i - 2
            last2, last1 = numeros[i-2], numeros[i-1]
            vizinhos = obter_vizinhos(last1, 1, 1)  # 1 antes, 1 depois = 3 números
            
            X[idx, 0] = last2
            X[idx, 1] = last1
            for j, viz in enumerate(vizinhos[:3]):  # Garante 3 features de vizinhos
                X[idx, 2 + j] = viz
            
            y[idx] = numeros[i]
        
        return X, y

    def treinar(self, historico: List[Dict[str, Any]]):
        """Treina modelo apenas quando necessário"""
        if len(historico) < self.window:
            return
        
        # Treina apenas periodicamente para performance
        if len(historico) - self._ultimo_treino < self._treino_interval:
            return
            
        X, y = self._criar_features_otimizado(historico)
        if X is None or len(X) < 10:  # Mínimo de amostras
            return
            
        try:
            self.model = RandomForestClassifier(
                n_estimators=100,  # Reduzido para performance
                max_depth=10,
                random_state=42,
                n_jobs=-1  # Usa todos os cores
            )
            self.model.fit(X, y)
            self._ultimo_treino = len(historico)
            log_estrategia(f"Modelo RF treinado com {len(X)} amostras")
        except Exception as e:
            log_estrategia(f"Erro treinando RF: {e}", "error")
            self.model = None

    def prever(self, historico: List[Dict[str, Any]]) -> List[int]:
        """Previsão otimizada com fallback para método estatístico"""
        if not historico or len(historico) < 2:
            return []

        # Método estatístico original (sempre funciona)
        candidatos = self._previsao_estatistica(historico)
        
        # Adiciona predição ML se disponível
        if self.model is not None and len(historico) >= 3:
            candidatos_ml = self._previsao_ml(historico)
            candidatos.extend(candidatos_ml)
        
        # Remove duplicatas mantendo ordem
        candidatos = list(dict.fromkeys(candidatos))
        
        # Expande para vizinhos
        numeros_previstos = self._expandir_para_vizinhos(candidatos)
        
        # Redução inteligente e limite
        return self._aplicar_limites(numeros_previstos, historico)

    def _previsao_estatistica(self, historico: List[Dict[str, Any]]) -> List[int]:
        """Método estatístico original"""
        historico_lista = list(historico)
        ultimo_numero = historico_lista[-1]["number"]
        
        antes, depois = [], []
        for i, h in enumerate(historico_lista[:-1]):
            if h.get("number") == ultimo_numero:
                if i - 1 >= 0:
                    antes.append(historico_lista[i-1]["number"])
                if i + 1 < len(historico_lista):
                    depois.append(historico_lista[i+1]["number"])

        cont_antes = Counter(antes)
        cont_depois = Counter(depois)
        
        top_antes = [num for num, _ in cont_antes.most_common(self.top_n)]
        top_depois = [num for num, _ in cont_depois.most_common(self.top_n)]
        
        return list(set(top_antes + top_depois))

    def _previsao_ml(self, historico: List[Dict[str, Any]]) -> List[int]:
        """Predição com Machine Learning"""
        try:
            numeros = [h["number"] for h in historico]
            last2, last1 = numeros[-2], numeros[-1]
            vizinhos = obter_vizinhos(last1, 1, 1)
            
            features = [last2, last1] + vizinhos[:3]  # Garante 5 features
            features_array = np.array(features).reshape(1, -1)
            
            probs = self.model.predict_proba(features_array)[0]
            classes = self.model.classes_
            
            # Pega top_n com maiores probabilidades
            idx_top = np.argsort(probs)[-self.top_n:]
            return [int(classes[i]) for i in idx_top]
            
        except Exception as e:
            log_estrategia(f"Erro predição ML: {e}", "warning")
            return []

    def _expandir_para_vizinhos(self, candidatos: List[int]) -> List[int]:
        """Expande candidatos para incluir vizinhos"""
        numeros_previstos = []
        for n in candidatos:
            vizinhos = obter_vizinhos(n, 2, 2)
            for v in vizinhos:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)
        return numeros_previstos

    def _aplicar_limites(self, previsoes: List[int], historico: List[Dict[str, Any]]) -> List[int]:
        """Aplica redução inteligente e limites"""
        if not previsoes:
            return []
            
        # Redução inteligente
        previsoes_reduzidas = reduzir_metade_inteligente(previsoes, historico)
        
        # Limite final
        if len(previsoes_reduzidas) > MAX_PREVIEWS:
            previsoes_reduzidas = previsoes_reduzidas[:MAX_PREVIEWS]
            
        return previsoes_reduzidas

# =============================
# Sistema de Top N Dinâmico Otimizado
# =============================
TOP_N_COOLDOWN = 3
TOP_N_PROB_BASE = 0.3
TOP_N_PROB_MAX = 0.5
TOP_N_PROB_MIN = 0.2
TOP_N_WINDOW = 12

class TopNManager:
    """Gerencia Top N dinâmico de forma eficiente"""
    def __init__(self):
        self.history = deque(maxlen=TOP_N_WINDOW)
        self.reds = {}
        self.greens = {}
    
    def atualizar_cooldown(self):
        """Atualiza cooldowns dos números em RED"""
        novos_reds = {}
        for num, cooldown in self.reds.items():
            if cooldown > 1:
                novos_reds[num] = cooldown - 1
        self.reds = novos_reds
    
    def calcular_probabilidade(self):
        """Calcula probabilidade mínima baseada no histórico"""
        if not self.history:
            return TOP_N_PROB_BASE
        
        taxa_red = list(self.history).count("R") / len(self.history)
        prob_min = TOP_N_PROB_BASE + (taxa_red * (TOP_N_PROB_MAX - TOP_N_PROB_BASE))
        return min(max(prob_min, TOP_N_PROB_MIN), TOP_N_PROB_MAX)
    
    def ajustar_top_n(self, previsoes: List[int]) -> List[int]:
        """Ajusta Top N baseado em probabilidades e cooldowns"""
        if not previsoes:
            return previsoes[:MIN_TOP_N]
        
        self.atualizar_cooldown()
        prob_min = self.calcular_probabilidade()
        
        # Filtra números em cooldown
        filtrados = [num for num in previsoes if num not in self.reds]
        
        # Aplica pesos baseados em greens anteriores
        pesos = {}
        for num in filtrados:
            pesos[num] = 1.0 + self.greens.get(num, 0) * 0.05
        
        # Ordena e seleciona
        ordenados = sorted(pesos.keys(), key=lambda x: pesos[x], reverse=True)
        n = max(MIN_TOP_N, min(MAX_TOP_N, int(len(ordenados) * prob_min) + MIN_TOP_N))
        
        return ordenados[:n]
    
    def registrar_resultado(self, numero_real: int, top_n: List[int]):
        """Registra resultado do Top N"""
        for num in top_n:
            if num == numero_real:
                self.greens[num] = self.greens.get(num, 0) + 1
                self.history.append("G")
                log_estrategia(f"Top N GREEN: {num}")
            else:
                self.reds[num] = TOP_N_COOLDOWN
                self.history.append("R")

# =============================
# Funções de Redução Inteligente
# =============================
def reduzir_metade_inteligente(previsoes: List[int], historico: List[Dict[str, Any]]) -> List[int]:
    """Reduz previsões pela metade de forma inteligente"""
    if len(previsoes) <= 1:
        return previsoes
    
    # Usa janela menor para performance
    window = min(WINDOW_SIZE, len(historico))
    ultimos_numeros = [h["number"] for h in list(historico)[-window:]] if historico else []
    
    contagem_total = Counter(ultimos_numeros)
    topn_greens = st.session_state.get("topn_greens", {})
    
    pontuacoes = {}
    for n in previsoes:
        freq = contagem_total.get(n, 0)
        vizinhos = obter_vizinhos(n, 1, 1)
        redundancia = sum(1 for v in vizinhos if v in previsoes)
        bonus = topn_greens.get(n, 0)
        pontuacoes[n] = freq + (bonus * 0.8) - (0.5 * redundancia)
    
    ordenados = sorted(pontuacoes.keys(), key=lambda x: pontuacoes[x], reverse=True)
    n_reduzidos = max(1, len(ordenados) // 2)
    
    return ordenados[:n_reduzidos]

# =============================
# Estratégia 31/34 Otimizada
# =============================
def estrategia_31_34(numero_capturado: int) -> List[int]:
    """Estratégia 31/34 com cache de vizinhos"""
    if numero_capturado is None:
        return None
    
    try:
        terminal = int(str(numero_capturado)[-1])
    except (ValueError, TypeError):
        return None
    
    if terminal not in {2, 6, 9}:
        return None
    
    # Usa cache para vizinhos
    viz_31 = obter_vizinhos_fixos(31, 5, 5)
    viz_34 = obter_vizinhos_fixos(34, 5, 5)
    
    entrada = set([0, 26, 30] + viz_31 + viz_34)
    
    msg = (
        "🎯 Estratégia 31/34 disparada!\n"
        f"Número capturado: {numero_capturado} (terminal {terminal})\n"
        "Entrar nos números: 31 34"
    )
    enviar_telegram(msg)
    
    return list(entrada)

# =============================
# Streamlit App - Interface Otimizada
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — IA Recorrência (RandomForest) + Redução Inteligente")
st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state otimizada
def inicializar_session_state():
    defaults = {
        "estrategia": EstrategiaDeslocamento(),
        "ia_recorrencia": IA_Recorrencia_RF(layout=ROULETTE_LAYOUT, top_n=5, window=WINDOW_SIZE),
        "topn_manager": TopNManager(),
        "estatisticas_recorrencia": Estatisticas(),
        "estatisticas_topn": Estatisticas(),
        "estatisticas_31_34": Estatisticas(),
        "previsao": [],
        "previsao_topN": [],
        "previsao_31_34": [],
        "contador_rodadas": 0,
    }
    
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

inicializar_session_state()

# Carregar histórico existente
historico = carregar_historico()
for n in historico:
    if (not st.session_state.estrategia.historico or 
        st.session_state.estrategia.historico[-1].get("timestamp") != n.get("timestamp")):
        st.session_state.estrategia.adicionar_numero(n)

# -----------------------------
# Processamento Principal Otimizado
# -----------------------------
def processar_rodada():
    """Processa uma rodada completa de forma otimizada"""
    resultado = cache_manager.get_api_result()
    if not resultado:
        return
    
    # Verifica se é um novo resultado
    ultimo_ts = None
    if st.session_state.estrategia.historico:
        ultimo_item = st.session_state.estrategia.historico[-1]
        ultimo_ts = ultimo_item.get("timestamp")
    
    if resultado.get("timestamp") == ultimo_ts:
        return
    
    # Adiciona novo número
    st.session_state.estrategia.adicionar_numero(resultado)
    salvar_historico(list(st.session_state.estrategia.historico))
    
    numero_real = resultado["number"]
    
    # Processa conferências
    processar_conferencias(numero_real)
    
    # Gera novas previsões
    gerar_previsoes(numero_real)
    
    # Salva métricas
    salvar_metricas_rodada(resultado, numero_real)
    
    st.session_state.contador_rodadas += 1

def processar_conferencias(numero_real: int):
    """Processa todas as conferências de uma vez"""
    # Conferência Recorrência
    if st.session_state.previsao:
        numeros_conferencia = []
        for n in st.session_state.previsao:
            numeros_conferencia.extend(obter_vizinhos(n, 1, 1))
        
        if numero_real in set(numeros_conferencia):
            st.session_state.estatisticas_recorrencia.registrar_acerto()
            st.success(f"🟢 GREEN! Número {numero_real} previsto.")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} previsto pela recorrência.")
        else:
            st.session_state.estatisticas_recorrencia.registrar_erro()
            st.error(f"🔴 RED! Número {numero_real} não previsto.")
        
        st.session_state.previsao = []
    
    # Conferência Top N
    if st.session_state.previsao_topN:
        numeros_topn = []
        for n in st.session_state.previsao_topN:
            numeros_topn.extend(obter_vizinhos(n, 1, 1))
        
        if numero_real in set(numeros_topn):
            st.session_state.estatisticas_topn.registrar_acerto()
            st.session_state.topn_manager.registrar_resultado(numero_real, st.session_state.previsao_topN)
            st.success(f"🟢 GREEN Top N! Número {numero_real}.")
            enviar_telegram_topN(f"🟢 GREEN Top N! Número {numero_real}.")
        else:
            st.session_state.estatisticas_topn.registrar_erro()
            st.session_state.topn_manager.registrar_resultado(numero_real, st.session_state.previsao_topN)
            st.error(f"🔴 RED Top N! Número {numero_real}.")
        
        st.session_state.previsao_topN = []
    
    # Conferência 31/34
    if st.session_state.previsao_31_34:
        if numero_real in st.session_state.previsao_31_34:
            st.session_state.estatisticas_31_34.registrar_acerto()
            st.success(f"🟢 GREEN 31/34! Número {numero_real}.")
            enviar_telegram(f"🟢 GREEN 31/34! Número {numero_real}.")
        else:
            st.session_state.estatisticas_31_34.registrar_erro()
            st.error(f"🔴 RED 31/34! Número {numero_real}.")
        
        st.session_state.previsao_31_34 = []

def gerar_previsoes(numero_real: int):
    """Gera novas previsões baseado no contador de rodadas"""
    if st.session_state.contador_rodadas % 2 == 0:
        # Previsão Recorrência + Top N
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros
            
            # Top N Dinâmico
            entrada_topN = st.session_state.topn_manager.ajustar_top_n(prox_numeros)
            st.session_state.previsao_topN = entrada_topN
            
            # Telegram
            numeros_ordenados = sorted(prox_numeros)
            msg_recorrencia = "🎯 NP: " + " ".join(map(str, numeros_ordenados[:5]))
            if len(numeros_ordenados) > 5:
                msg_recorrencia += "\n" + " ".join(map(str, numeros_ordenados[5:10]))
            
            enviar_telegram(msg_recorrencia)
            enviar_telegram_topN("Top N: " + " ".join(map(str, sorted(entrada_topN))))
    else:
        # Estratégia 31/34
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34

def salvar_metricas_rodada(resultado: Dict[str, Any], numero_real: int):
    """Salva métricas da rodada"""
    metrics = {
        "timestamp": resultado.get("timestamp"),
        "numero_real": numero_real,
        "acertos_recorrencia": st.session_state.estatisticas_recorrencia.acertos,
        "erros_recorrencia": st.session_state.estatisticas_recorrencia.erros,
        "acertos_topn": st.session_state.estatisticas_topn.acertos,
        "erros_topn": st.session_state.estatisticas_topn.erros,
        "acertos_31_34": st.session_state.estatisticas_31_34.acertos,
        "erros_31_34": st.session_state.estatisticas_31_34.erros,
        "contador_rodadas": st.session_state.contador_rodadas
    }
    salvar_metricas(metrics)

# Executa processamento
processar_rodada()

# -----------------------------
# Interface de Exibição
# -----------------------------
st.subheader("📜 Histórico (últimos 3 números)")
ultimos = list(st.session_state.estrategia.historico)[-3:]
st.write(ultimos)

# Função para exibir métricas
def exibir_metricas(estatisticas: Estatisticas, previsao: List[int], titulo: str):
    """Exibe métricas de forma consistente"""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"🟢 GREEN {titulo}", estatisticas.acertos)
    col2.metric(f"🔴 RED {titulo}", estatisticas.erros)
    col3.metric(f"✅ Taxa {titulo}", f"{estatisticas.taxa_acerto:.1f}%")
    col4.metric(f"🎯 Qtd. previstos {titulo}", len(previsao))

# Métricas Recorrência
exibir_metricas(
    st.session_state.estatisticas_recorrencia,
    st.session_state.previsao,
    "Recorrência"
)

# Métricas Top N
exibir_metricas(
    st.session_state.estatisticas_topn,
    st.session_state.previsao_topN,
    "Top N"
)

# Métricas 31/34
exibir_metricas(
    st.session_state.estatisticas_31_34,
    st.session_state.previsao_31_34,
    "31/34"
)

# Informações do sistema
st.subheader("📊 Informações do Sistema")
st.write(f"Total no histórico: **{len(st.session_state.estrategia.historico)}**")
st.write(f"Capacidade máxima: **{st.session_state.estrategia.historico.maxlen}**")
st.write(f"Contador de rodadas: **{st.session_state.contador_rodadas}**")

# Status do modelo
if st.session_state.ia_recorrencia.model is not None:
    st.success("🤖 Modelo RandomForest ativo e treinado")
else:
    st.info("🤖 Modelo RandomForest em inicialização")

# Logs recentes (opcional)
if st.checkbox("Mostrar logs recentes"):
    try:
        with open('roleta_ia.log', 'r', encoding='utf-8') as f:
            logs = f.readlines()[-20:]
        st.text_area("Logs:", "".join(logs), height=200)
    except FileNotFoundError:
        st.info("Arquivo de log não encontrado")
