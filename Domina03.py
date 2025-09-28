# Domina03.py (corrigido para timeline fiel dos sorteios)
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
import hashlib

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

WINDOW_SIZE = 18
MIN_TOP_N = 5
MAX_TOP_N = 10
MAX_PREVIEWS = 15

# =============================
# Configuração de Logging
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
    log_func = getattr(logging, nivel.lower(), logging.info)
    log_func(f"🎯 {mensagem}")

# =============================
# Sistema de Timeline Fiel
# =============================
class TimelineManager:
    """Gerencia a timeline fiel dos sorteios sem duplicações"""
    
    def __init__(self, historico_path: str):
        self.historico_path = historico_path
        self._ultimo_hash = None
        
    def gerar_hash_sorteio(self, numero_dict: Dict[str, Any]) -> str:
        """Gera hash único para cada sorteio baseado em timestamp + número"""
        if not numero_dict or 'timestamp' not in numero_dict:
            return None
            
        content = f"{numero_dict['timestamp']}_{numero_dict.get('number', '')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def carregar_timeline(self) -> List[Dict[str, Any]]:
        """Carrega timeline garantindo ordenação correta e sem duplicatas"""
        if not os.path.exists(self.historico_path):
            return []
            
        try:
            with open(self.historico_path, "r", encoding='utf-8') as f:
                historico = json.load(f)
            
            # Remove duplicatas e garante ordenação
            timeline_limpa = self._remover_duplicatas(historico)
            log_estrategia(f"Timeline carregada: {len(timeline_limpa)} sorteios únicos")
            return timeline_limpa
            
        except Exception as e:
            log_estrategia(f"Erro ao carregar timeline: {e}", "error")
            return []
    
    def _remover_duplicatas(self, historico: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove entradas duplicadas baseado no hash"""
        seen_hashes = set()
        timeline_limpa = []
        
        for sorteio in historico:
            hash_sorteio = self.gerar_hash_sorteio(sorteio)
            if hash_sorteio and hash_sorteio not in seen_hashes:
                seen_hashes.add(hash_sorteio)
                timeline_limpa.append(sorteio)
        
        # Ordena por timestamp (mais recente primeiro)
        timeline_limpa.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return timeline_limpa
    
    def adicionar_sorteio(self, numero_dict: Dict[str, Any]) -> bool:
        """Adiciona sorteio apenas se for novo, retorna True se adicionado"""
        if not numero_dict or 'timestamp' not in numero_dict:
            return False
            
        hash_novo = self.gerar_hash_sorteio(numero_dict)
        if not hash_novo:
            return False
            
        # Carrega timeline atual
        timeline_atual = self.carregar_timeline()
        
        # Verifica se já existe
        for sorteio_existente in timeline_atual:
            if self.gerar_hash_sorteio(sorteio_existente) == hash_novo:
                log_estrategia(f"Sorteio duplicado ignorado: {numero_dict}")
                return False
        
        # Adiciona novo sorteio no início (mais recente primeiro)
        timeline_atual.insert(0, numero_dict)
        
        # Mantém apenas os últimos 15000 sorteios
        if len(timeline_atual) > 15000:
            timeline_atual = timeline_atual[:15000]
        
        # Salva timeline atualizada
        try:
            with open(self.historico_path, "w", encoding='utf-8') as f:
                json.dump(timeline_atual, f, indent=2)
            log_estrategia(f"Novo sorteio adicionado: {numero_dict}")
            return True
        except Exception as e:
            log_estrategia(f"Erro ao salvar timeline: {e}", "error")
            return False

# Inicializar Timeline Manager
timeline_manager = TimelineManager(HISTORICO_PATH)

# =============================
# Classes de Gerenciamento
# =============================
class Estatisticas:
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
        # Só adiciona se for realmente novo (verificação adicional)
        if self.historico:
            ultimo = self.historico[-1]
            if (ultimo.get('timestamp') == numero_dict.get('timestamp') and 
                ultimo.get('number') == numero_dict.get('number')):
                return  # Ignora duplicata
        
        self.historico.append(numero_dict)
        log_estrategia(f"Número {numero_dict['number']} adicionado ao histórico")

# =============================
# Cache e API
# =============================
class CacheManager:
    def __init__(self):
        self._vizinhos_cache = {}
        self._api_cache = None
        self._api_cache_time = 0
        self._cache_duration = 8
    
    def get_vizinhos(self, numero: int, antes: int = 2, depois: int = 2):
        key = (numero, antes, depois)
        if key not in self._vizinhos_cache:
            self._vizinhos_cache[key] = self._calcular_vizinhos(numero, antes, depois)
        return self._vizinhos_cache[key]
    
    def _calcular_vizinhos(self, numero: int, antes: int, depois: int):
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
        current_time = time.time()
        if (self._api_cache is None or 
            current_time - self._api_cache_time > self._cache_duration):
            self._api_cache = self._fetch_latest_result()
            self._api_cache_time = current_time
        return self._api_cache

    def _fetch_latest_result(self):
        try:
            response = requests.get(API_URL, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            game_data = data.get("data", {})
            result = game_data.get("result", {})
            outcome = result.get("outcome", {})
            number = outcome.get("number")
            timestamp = game_data.get("startedAt")
            
            if timestamp and number is not None:
                log_estrategia(f"API - Novo resultado: {number} em {timestamp}")
                return {"number": number, "timestamp": timestamp}
            else:
                log_estrategia("API - Dados incompletos recebidos", "warning")
                return None
                
        except requests.exceptions.Timeout:
            log_estrategia("Timeout na API", "warning")
            return None
        except Exception as e:
            log_estrategia(f"Erro na API: {e}", "error")
            return None

cache_manager = CacheManager()

# =============================
# Funções Utilitárias
# =============================
def enviar_telegram(msg: str, token: str = TELEGRAM_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        log_estrategia(f"Telegram: {msg[:80]}...")
    except Exception as e:
        log_estrategia(f"Erro Telegram: {e}", "error")

def enviar_telegram_topN(msg: str):
    enviar_telegram(msg, ALT_TELEGRAM_TOKEN, ALT_TELEGRAM_CHAT_ID)

def salvar_metricas(metricas: Dict[str, Any]):
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
        
        log_estrategia(f"Métricas salvas")
    except Exception as e:
        log_estrategia(f"Erro ao salvar métricas: {e}", "error")

def obter_vizinhos(numero: int, antes: int = 2, depois: int = 2):
    return cache_manager.get_vizinhos(numero, antes, depois)

def obter_vizinhos_fixos(numero: int, antes: int = 5, depois: int = 5):
    return cache_manager.get_vizinhos(numero, antes, depois)

# =============================
# IA Recorrência (versão simplificada para exemplo)
# =============================
class IA_Recorrencia_RF:
    def __init__(self, layout=None, top_n=3, window=WINDOW_SIZE):
        self.layout = layout or ROULETTE_LAYOUT
        self.top_n = top_n
        self.window = window
        self.model = None
        self._model_treinado = False

    def prever(self, historico: List[Dict[str, Any]]) -> List[int]:
        if not historico or len(historico) < 2:
            return []

        # Método estatístico simples
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
        
        candidatos = list(set(top_antes + top_depois))
        
        # Expande para vizinhos
        numeros_previstos = []
        for n in candidatos:
            vizinhos = obter_vizinhos(n, 2, 2)
            for v in vizinhos:
                if v not in numeros_previstos:
                    numeros_previstos.append(v)
        
        return numeros_previstos[:MAX_PREVIEWS]

# =============================
# Sistema de Top N Dinâmico
# =============================
TOP_N_COOLDOWN = 3
TOP_N_PROB_BASE = 0.3
TOP_N_PROB_MAX = 0.5
TOP_N_PROB_MIN = 0.2
TOP_N_WINDOW = 12

class TopNManager:
    def __init__(self):
        self.history = deque(maxlen=TOP_N_WINDOW)
        self.reds = {}
        self.greens = {}
    
    def atualizar_cooldown(self):
        novos_reds = {}
        for num, cooldown in self.reds.items():
            if cooldown > 1:
                novos_reds[num] = cooldown - 1
        self.reds = novos_reds
    
    def calcular_probabilidade(self):
        if not self.history:
            return TOP_N_PROB_BASE
        
        taxa_red = list(self.history).count("R") / len(self.history)
        prob_min = TOP_N_PROB_BASE + (taxa_red * (TOP_N_PROB_MAX - TOP_N_PROB_BASE))
        return min(max(prob_min, TOP_N_PROB_MIN), TOP_N_PROB_MAX)
    
    def ajustar_top_n(self, previsoes: List[int]) -> List[int]:
        if not previsoes:
            return previsoes[:MIN_TOP_N]
        
        self.atualizar_cooldown()
        prob_min = self.calcular_probabilidade()
        
        filtrados = [num for num in previsoes if num not in self.reds]
        
        pesos = {}
        for num in filtrados:
            pesos[num] = 1.0 + self.greens.get(num, 0) * 0.05
        
        ordenados = sorted(pesos.keys(), key=lambda x: pesos[x], reverse=True)
        n = max(MIN_TOP_N, min(MAX_TOP_N, int(len(ordenados) * prob_min) + MIN_TOP_N))
        
        return ordenados[:n]
    
    def registrar_resultado(self, numero_real: int, top_n: List[int]):
        for num in top_n:
            if num == numero_real:
                self.greens[num] = self.greens.get(num, 0) + 1
                self.history.append("G")
                log_estrategia(f"Top N GREEN: {num}")
            else:
                self.reds[num] = TOP_N_COOLDOWN
                self.history.append("R")

# =============================
# Estratégia 31/34
# =============================
def estrategia_31_34(numero_capturado: int) -> List[int]:
    if numero_capturado is None:
        return None
    
    try:
        terminal = int(str(numero_capturado)[-1])
    except (ValueError, TypeError):
        return None
    
    if terminal not in {2, 6, 9}:
        return None
    
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
# Streamlit App
# =============================
st.set_page_config(page_title="Roleta IA Profissional", layout="centered")
st.title("🎯 Roleta — Timeline Fiel dos Sorteios")
st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
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
        "ultimo_sorteio_processado": None,
    }
    
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

inicializar_session_state()

# Carregar timeline existente
timeline_existente = timeline_manager.carregar_timeline()
for sorteio in timeline_existente:
    if (not st.session_state.estrategia.historico or 
        st.session_state.estrategia.historico[-1].get("timestamp") != sorteio.get("timestamp")):
        st.session_state.estrategia.adicionar_numero(sorteio)

# -----------------------------
# Processamento Principal CORRIGIDO
# -----------------------------
def processar_rodada():
    """Processa uma rodada garantindo timeline fiel"""
    resultado = cache_manager.get_api_result()
    
    if not resultado or 'timestamp' not in resultado:
        log_estrategia("Resultado inválido da API", "warning")
        return
    
    # Verifica se é um sorteio NOVO usando o TimelineManager
    novo_sorteio_adicionado = timeline_manager.adicionar_sorteio(resultado)
    
    if not novo_sorteio_adicionado:
        # Sorteio já existe ou é inválido
        return
    
    # Só processa se for realmente um novo sorteio
    log_estrategia(f"🎲 NOVO SORTEIO PROCESSADO: {resultado['number']}")
    
    # Atualiza histórico em memória
    st.session_state.estrategia.adicionar_numero(resultado)
    
    numero_real = resultado["number"]
    
    # Processa conferências
    processar_conferencias(numero_real)
    
    # Gera novas previsões
    gerar_previsoes(numero_real)
    
    # Salva métricas
    salvar_metricas_rodada(resultado, numero_real)
    
    st.session_state.contador_rodadas += 1
    st.session_state.ultimo_sorteio_processado = resultado['timestamp']

def processar_conferencias(numero_real: int):
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
    if st.session_state.contador_rodadas % 2 == 0:
        prox_numeros = st.session_state.ia_recorrencia.prever(st.session_state.estrategia.historico)
        if prox_numeros:
            st.session_state.previsao = prox_numeros
            
            entrada_topN = st.session_state.topn_manager.ajustar_top_n(prox_numeros)
            st.session_state.previsao_topN = entrada_topN
            
            numeros_ordenados = sorted(prox_numeros)
            msg_recorrencia = "🎯 NP: " + " ".join(map(str, numeros_ordenados[:5]))
            if len(numeros_ordenados) > 5:
                msg_recorrencia += "\n" + " ".join(map(str, numeros_ordenados[5:10]))
            
            enviar_telegram(msg_recorrencia)
            enviar_telegram_topN("Top N: " + " ".join(map(str, sorted(entrada_topN))))
    else:
        entrada_31_34 = estrategia_31_34(numero_real)
        if entrada_31_34:
            st.session_state.previsao_31_34 = entrada_31_34

def salvar_metricas_rodada(resultado: Dict[str, Any], numero_real: int):
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
# Interface
# -----------------------------
st.subheader("📜 Timeline dos Sorteios (últimos 5)")
ultimos = list(st.session_state.estrategia.historico)[-5:]
if ultimos:
    for i, sorteio in enumerate(ultimos):
        st.write(f"{i+1}. Número: {sorteio['number']} - Timestamp: {sorteio['timestamp']}")
else:
    st.write("Nenhum sorteio registrado ainda")

# Estatísticas
def exibir_metricas(estatisticas: Estatisticas, previsao: List[int], titulo: str):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"🟢 GREEN {titulo}", estatisticas.acertos)
    col2.metric(f"🔴 RED {titulo}", estatisticas.erros)
    col3.metric(f"✅ Taxa {titulo}", f"{estatisticas.taxa_acerto:.1f}%")
    col4.metric(f"🎯 Qtd. previstos {titulo}", len(previsao))

exibir_metricas(st.session_state.estatisticas_recorrencia, st.session_state.previsao, "Recorrência")
exibir_metricas(st.session_state.estatisticas_topn, st.session_state.previsao_topN, "Top N")
exibir_metricas(st.session_state.estatisticas_31_34, st.session_state.previsao_31_34, "31/34")

# Informações do sistema
st.subheader("📊 Informações do Sistema")
st.write(f"Total na timeline: **{len(st.session_state.estrategia.historico)}**")
st.write(f"Contador de rodadas: **{st.session_state.contador_rodadas}**")

if st.session_state.ultimo_sorteio_processado:
    st.write(f"Último sorteio processado: **{st.session_state.ultimo_sorteio_processado}**")

# Status da timeline
st.success("✅ Timeline fiel ativa - Sem duplicatas")
