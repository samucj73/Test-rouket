import streamlit as st
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import time
from collections import deque
from threading import Lock
import threading

# Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging

# =============================
# Configurações e Segurança
# =============================

# Versão de teste - manter valores padrão
API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Constantes
ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# Histórico de conferências
HISTORICO_PATH = "historico_conferencias.json"

# =============================
# Dicionário de Ligas
# =============================
LIGA_DICT = {
    "FIFA World Cup": "WC",
    "UEFA Champions League": "CL",
    "Bundesliga": "BL1",
    "Eredivisie": "DED",
    "Campeonato Brasileiro Série A": "BSA",
    "Primera Division": "PD",
    "Ligue 1": "FL1",
    "Championship (Inglaterra)": "ELC",
    "Primeira Liga (Portugal)": "PPL",
    "European Championship": "EC",
    "Serie A (Itália)": "SA",
    "Premier League (Inglaterra)": "PL"
}

# =============================
# Sistema de Rate Limiting e Cache
# =============================

class RateLimiter:
    """Controla rate limiting para a API"""
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance
    
    def _init(self):
        self.requests = deque(maxlen=10)  # 10 requests por minuto
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 6.0  # 6 segundos entre requests (10/min)
        self.backoff_factor = 1.5
        self.max_retries = 3
        
    def wait_if_needed(self):
        """Espera se necessário para respeitar rate limit"""
        with self.lock:
            now = time.time()
            
            # Remove requests antigos (mais de 1 minuto)
            while self.requests and now - self.requests[0] > 60:
                self.requests.popleft()
            
            # Se já temos 10 requests no último minuto, espera
            if len(self.requests) >= 10:
                wait_time = 60 - (now - self.requests[0])
                if wait_time > 0:
                    logging.info(f"⏳ Rate limit atingido. Esperando {wait_time:.1f} segundos...")
                    time.sleep(wait_time + 0.1)
                    now = time.time()
            
            # Verifica intervalo mínimo entre requests
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                time.sleep(wait_time)
            
            self.requests.append(now)
            self.last_request_time = now

# Instância global do rate limiter
rate_limiter = RateLimiter()

# Configurações de cache inteligente
CACHE_CONFIG = {
    "jogos": {
        "ttl": 3600,  # 1 hora para jogos
        "max_size": 100  # Máximo de 100 entradas
    },
    "classificacao": {
        "ttl": 86400,  # 24 horas para classificação
        "max_size": 50  # Máximo de 50 ligas
    },
    "match_details": {
        "ttl": 1800,  # 30 minutos para detalhes de partida
        "max_size": 200  # Máximo de 200 partidas
    }
}

class SmartCache:
    """Cache inteligente com TTL e tamanho máximo"""
    def __init__(self, cache_type: str):
        self.cache = {}
        self.timestamps = {}
        self.config = CACHE_CONFIG.get(cache_type, {"ttl": 3600, "max_size": 100})
        self.lock = threading.Lock()
        
    def get(self, key: str):
        """Obtém valor do cache se ainda for válido"""
        with self.lock:
            if key not in self.cache:
                return None
                
            timestamp = self.timestamps.get(key, 0)
            agora = time.time()
            
            if agora - timestamp > self.config["ttl"]:
                # Expirou, remove do cache
                del self.cache[key]
                del self.timestamps[key]
                return None
                
            return self.cache[key]
    
    def set(self, key: str, value):
        """Armazena valor no cache"""
        with self.lock:
            # Limpa cache se exceder tamanho máximo
            if len(self.cache) >= self.config["max_size"]:
                # Remove o mais antigo
                oldest_key = min(self.timestamps.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear(self):
        """Limpa todo o cache"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()

# Inicializar caches
jogos_cache = SmartCache("jogos")
classificacao_cache = SmartCache("classificacao")
match_cache = SmartCache("match_details")

class APIMonitor:
    """Monitora uso da API"""
    def __init__(self):
        self.total_requests = 0
        self.failed_requests = 0
        self.rate_limit_hits = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def log_request(self, success: bool, was_rate_limited: bool = False):
        """Registra uma requisição"""
        with self.lock:
            self.total_requests += 1
            if not success:
                self.failed_requests += 1
            if was_rate_limited:
                self.rate_limit_hits += 1
    
    def get_stats(self):
        """Retorna estatísticas"""
        with self.lock:
            elapsed = time.time() - self.start_time
            requests_per_min = (self.total_requests / elapsed * 60) if elapsed > 0 else 0
            
            return {
                "total_requests": self.total_requests,
                "failed_requests": self.failed_requests,
                "rate_limit_hits": self.rate_limit_hits,
                "requests_per_minute": round(requests_per_min, 2),
                "success_rate": round((1 - self.failed_requests / max(self.total_requests, 1)) * 100, 1),
                "uptime_minutes": round(elapsed / 60, 1)
            }
    
    def reset(self):
        """Reseta estatísticas"""
        with self.lock:
            self.total_requests = 0
            self.failed_requests = 0
            self.rate_limit_hits = 0
            self.start_time = time.time()

# Instância global do monitor
api_monitor = APIMonitor()

# =============================
# Configuração de Logging
# =============================
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('sistema_alertas.log'),
            logging.StreamHandler()
        ]
    )

setup_logging()

# =============================
# Utilitários de Cache e Persistência
# =============================
def carregar_json(caminho: str) -> dict:
    """Carrega JSON - VERSÃO CORRIGIDA"""
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            
            # Verificar se não está vazio
            if not dados:
                return {}
                
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
                agora = datetime.now().timestamp()
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                        return {}
                else:
                    # Se não tem timestamp, verificar modificação do arquivo
                    if agora - os.path.getmtime(caminho) > CACHE_TIMEOUT:
                        return {}
            return dados
    except (json.JSONDecodeError, IOError, Exception) as e:
        logging.error(f"Erro ao carregar {caminho}: {e}")
        st.error(f"Erro ao carregar {caminho}: {e}")
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
            if isinstance(dados, dict):
                dados['_timestamp'] = datetime.now().timestamp()
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logging.error(f"Erro ao salvar {caminho}: {e}")
        st.error(f"Erro ao salvar {caminho}: {e}")

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao() -> dict:
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados: dict):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Histórico de Conferências
# =============================
def carregar_historico() -> list:
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Erro ao carregar histórico: {e}")
            return []
    return []

def salvar_historico(historico: list):
    try:
        with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")
        st.error(f"Erro ao salvar histórico: {e}")

def registrar_no_historico(resultado: dict):
    if not resultado:
        return
    historico = carregar_historico()
    registro = {
        "data_conferencia": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "home": resultado.get("home"),
        "away": resultado.get("away"),
        "tendencia": resultado.get("tendencia"),
        "estimativa": round(resultado.get("estimativa", 0), 2),
        "confianca": round(resultado.get("confianca", 0), 1),
        "placar": resultado.get("placar", "-"),
        "resultado": resultado.get("resultado", "⏳ Aguardando"),
        "tipo_aposta": resultado.get("tipo_aposta", "DESCONHECIDO")
    }
    historico.append(registro)
    salvar_historico(historico)

def limpar_historico():
    """Faz backup e limpa histórico."""
    if os.path.exists(HISTORICO_PATH):
        try:
            # backup
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"historico_backup_{ts}.json"
            with open(HISTORICO_PATH, "rb") as f_src:
                with open(backup_name, "wb") as f_bak:
                    f_bak.write(f_src.read())
            os.remove(HISTORICO_PATH)
            st.success(f"🧹 Histórico limpo. Backup salvo: {backup_name}")
        except Exception as e:
            logging.error(f"Erro ao limpar/hacer backup do histórico: {e}")
            st.error(f"Erro ao limpar/hacer backup do histórico: {e}")
    else:
        st.info("⚠️ Nenhum histórico encontrado para limpar.")

# =============================
# Utilitários de Data e Formatação - CORRIGIDOS
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    """Formata data ISO - VERSÃO CORRIGIDA COM FUSO HORÁRIO"""
    try:
        # Converter para datetime com timezone awareness
        if data_iso.endswith('Z'):
            data_iso = data_iso.replace('Z', '+00:00')
        
        # Criar datetime com timezone UTC
        data_utc = datetime.fromisoformat(data_iso)
        
        # Se não tem timezone, assumir UTC
        if data_utc.tzinfo is None:
            data_utc = data_utc.replace(tzinfo=timezone.utc)
        
        # Converter para horário de Brasília (UTC-3)
        fuso_brasilia = timezone(timedelta(hours=-3))
        data_brasilia = data_utc.astimezone(fuso_brasilia)
        
        return data_brasilia.strftime("%d/%m/%Y"), data_brasilia.strftime("%H:%M")
    except ValueError as e:
        logging.error(f"Erro ao formatar data {data_iso}: {e}")
        return "Data inválida", "Hora inválida"

def formatar_data_iso_para_datetime(data_iso: str) -> datetime:
    """Converte string ISO para datetime com fuso correto - VERSÃO CORRIGIDA"""
    try:
        if data_iso.endswith('Z'):
            data_iso = data_iso.replace('Z', '+00:00')
        
        data_utc = datetime.fromisoformat(data_iso)
        
        # Se não tem timezone, assumir UTC
        if data_utc.tzinfo is None:
            data_utc = data_utc.replace(tzinfo=timezone.utc)
        
        # Converter para horário de Brasília
        fuso_brasilia = timezone(timedelta(hours=-3))
        return data_utc.astimezone(fuso_brasilia)
        
    except Exception as e:
        logging.error(f"Erro ao converter data {data_iso}: {e}")
        return datetime.now()

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Validação de Dados
# =============================
def validar_dados_jogo(match: dict) -> bool:
    """Valida se os dados do jogo são válidos"""
    required_fields = ['id', 'homeTeam', 'awayTeam', 'utcDate']
    
    for field in required_fields:
        if field not in match:
            logging.warning(f"Campo {field} faltando no jogo")
            return False
            
    if 'name' not in match['homeTeam'] or 'name' not in match['awayTeam']:
        logging.warning("Nomes dos times faltando")
        return False
        
    return True

# =============================
# Comunicação com APIs
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID, disable_web_page_preview: bool = True) -> bool:
    try:
        params = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": str(disable_web_page_preview).lower()
        }
        response = requests.get(f"{BASE_URL_TG}/sendMessage", params=params, timeout=10)
        return response.status_code == 200
    except requests.RequestException as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")
        st.error(f"Erro ao enviar para Telegram: {e}")
        return False

def enviar_foto_telegram(photo_bytes: io.BytesIO, caption: str = "", chat_id: str = TELEGRAM_CHAT_ID_ALT2) -> bool:
    """Envia uma foto (BytesIO) para o Telegram via sendPhoto."""
    try:
        photo_bytes.seek(0)
        files = {"photo": ("elite_master.png", photo_bytes, "image/png")}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        resp = requests.post(f"{BASE_URL_TG}/sendPhoto", data=data, files=files, timeout=15)
        return resp.status_code == 200
    except requests.RequestException as e:
        logging.error(f"Erro ao enviar foto para Telegram: {e}")
        st.error(f"Erro ao enviar foto para Telegram: {e}")
        return False

def obter_dados_api_com_retry(url: str, timeout: int = 15, max_retries: int = 3) -> dict | None:
    """Obtém dados da API com rate limiting e retry automático"""
    for attempt in range(max_retries):
        try:
            # Aplica rate limiting antes de cada request
            rate_limiter.wait_if_needed()
            
            logging.info(f"🔗 Request {attempt+1}/{max_retries}: {url}")
            
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            
            # Verifica rate limit na resposta
            if response.status_code == 429:  # Too Many Requests
                api_monitor.log_request(False, True)
                retry_after = int(response.headers.get('Retry-After', 60))
                logging.warning(f"⏳ Rate limit da API. Esperando {retry_after} segundos...")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            
            # Log de sucesso
            api_monitor.log_request(True)
            
            # Verifica se temos requests restantes
            remaining = response.headers.get('X-Requests-Remaining', 'unknown')
            reset_time = response.headers.get('X-RequestCounter-Reset', 'unknown')
            logging.info(f"✅ Request OK. Restantes: {remaining}, Reset: {reset_time}s")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logging.error(f"⌛ Timeout na tentativa {attempt+1} para {url}")
            api_monitor.log_request(False)
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logging.info(f"⏳ Esperando {wait_time}s antes de retry...")
                time.sleep(wait_time)
                
        except requests.RequestException as e:
            logging.error(f"❌ Erro na tentativa {attempt+1} para {url}: {e}")
            api_monitor.log_request(False)
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)
            else:
                st.error(f"❌ Falha após {max_retries} tentativas: {e}")
                return None
                
    return None

def obter_dados_api(url: str, timeout: int = 15) -> dict | None:
    return obter_dados_api_com_retry(url, timeout, max_retries=3)

def obter_classificacao(liga_id: str) -> dict:
    """Obtém classificação com cache inteligente"""
    # Verifica cache primeiro
    cached = classificacao_cache.get(liga_id)
    if cached:
        logging.info(f"📊 Classificação da liga {liga_id} obtida do cache")
        return cached
    
    url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
    data = obter_dados_api(url)
    if not data:
        return {}

    standings = {}
    for s in data.get("standings", []):
        if s["type"] != "TOTAL":
            continue
        for t in s["table"]:
            name = t["team"]["name"]
            standings[name] = {
                "scored": t.get("goalsFor", 0),
                "against": t.get("goalsAgainst", 0),
                "played": t.get("playedGames", 1),
                "wins": t.get("won", 0),
                "draws": t.get("draw", 0),
                "losses": t.get("lost", 0)
            }
    classificacao_cache.set(liga_id, standings)
    return standings

def obter_jogos(liga_id: str, data: str) -> list:
    """Obtém jogos com cache inteligente"""
    key = f"{liga_id}_{data}"
    
    # Verifica cache primeiro
    cached = jogos_cache.get(key)
    if cached:
        logging.info(f"⚽ Jogos {key} obtidos do cache")
        return cached
    
    url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
    data_api = obter_dados_api(url)
    jogos = data_api.get("matches", []) if data_api else []
    jogos_cache.set(key, jogos)
    return jogos

def obter_detalhes_partida(fixture_id: str) -> dict | None:
    """Obtém detalhes de uma partida específica com cache"""
    # Verifica cache primeiro
    cached = match_cache.get(fixture_id)
    if cached:
        return cached
    
    url = f"{BASE_URL_FD}/matches/{fixture_id}"
    data = obter_dados_api(url)
    
    if data:
        match_cache.set(fixture_id, data)
    
    return data

def obter_jogos_brasileirao(liga_id: str, data_hoje: str) -> list:
    """Busca jogos do Brasileirão considerando o fuso horário"""
    # Buscar jogos do dia atual E do dia seguinte (para pegar jogos que viram a meia-noite no UTC)
    data_amanha = (datetime.strptime(data_hoje, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    
    jogos_hoje = obter_jogos(liga_id, data_hoje)
    jogos_amanha = obter_jogos(liga_id, data_amanha)
    
    todos_jogos = jogos_hoje + jogos_amanha
    
    # Filtrar apenas os jogos que são realmente do dia de hoje no horário de Brasília
    jogos_filtrados = []
    for match in todos_jogos:
        if not validar_dados_jogo(match):
            continue
            
        data_utc = match["utcDate"]
        hora_brasilia = formatar_data_iso_para_datetime(data_utc)
        data_brasilia = hora_brasilia.strftime("%Y-%m-%d")
        
        # Manter apenas jogos do dia de hoje no horário de Brasília
        if data_brasilia == data_hoje:
            jogos_filtrados.append(match)
    
    return jogos_filtrados

# =============================
# Lógica de Análise e Alertas - ATUALIZADA COM NOVA LÓGICA INTELIGENTE
# =============================
def calcular_tendencia_completa(home: str, away: str, classificacao: dict) -> dict:
    """Calcula tendências completas com análise multivariada - VERSÃO INTELIGENTE COMPLETA"""
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1, "wins": 0, "draws": 0, "losses": 0})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1, "wins": 0, "draws": 0, "losses": 0})
    
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)

    # Estatísticas básicas
    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away

    # Cálculo de estimativa mais inteligente
    estimativa_home = (media_home_feitos * 0.6 + media_away_sofridos * 0.4)  # 60% do ataque, 40% da defesa adversária
    estimativa_away = (media_away_feitos * 0.4 + media_home_sofridos * 0.6)  # 40% do ataque, 60% da defesa adversária
    estimativa_total = estimativa_home + estimativa_away
    
    # ============================================================
    # ANÁLISE MULTIVARIADA PARA DEFINIR TENDÊNCIA
    # ============================================================
    
    # 1. ANÁLISE DE EQUILÍBRIO OFENSIVO/DEFENSIVO
    home_balance = media_home_feitos - media_home_sofridos
    away_balance = media_away_feitos - media_away_sofridos
    
    # Classificação dos times
    home_defensivo = home_balance < -0.3
    away_defensivo = away_balance < -0.3
    home_ofensivo = home_balance > 0.3
    away_ofensivo = away_balance > 0.3
    home_equilibrado = not home_defensivo and not home_ofensivo
    away_equilibrado = not away_defensivo and not away_ofensivo
    
    # 2. ANÁLISE DE CONFRONTO
    # Jogo entre dois times defensivos
    if home_defensivo and away_defensivo:
        ajuste_defensivo = 0.8  # Muito defensivo
        tipo_confronto = "DEFENSIVO_DEFENSIVO"
    # Jogo entre dois times ofensivos
    elif home_ofensivo and away_ofensivo:
        ajuste_defensivo = 0.2  # Muito ofensivo
        tipo_confronto = "OFENSIVO_OFENSIVO"
    # Jogo misto
    else:
        ajuste_defensivo = 0.5
        tipo_confronto = "MISTO"
    
    # 3. ANÁLISE DE RENDIMENTO EM CASA/FORA
    fator_casa = 1.15  # Time da casa tem vantagem
    fator_fora = 0.85  # Time visitante tem desvantagem
    
    estimativa_ajustada_home = estimativa_home * fator_casa
    estimativa_ajustada_away = estimativa_away * fator_fora
    estimativa_total_ajustada = estimativa_ajustada_home + estimativa_ajustada_away
    
    # 4. ANÁLISE DE TENDÊNCIA HISTÓRICA (se disponível)
    home_under_25_rate = dados_home.get("under_25_rate", 0.5)
    away_under_25_rate = dados_away.get("under_25_rate", 0.5)
    media_under_25 = (home_under_25_rate + away_under_25_rate) / 2
    
    home_under_15_rate = dados_home.get("under_15_rate", 0.3)
    away_under_15_rate = dados_away.get("under_15_rate", 0.3)
    media_under_15 = (home_under_15_rate + away_under_15_rate) / 2
    
    home_over_15_rate = dados_home.get("over_15_rate", 0.7)
    away_over_15_rate = dados_away.get("over_15_rate", 0.7)
    media_over_15 = (home_over_15_rate + away_over_15_rate) / 2
    
    # ============================================================
    # CÁLCULO DE SCORES PARA TODAS AS OPÇÕES
    # ============================================================
    
    # FATOR 1: Estimativa de gols ajustada
    fator_estimativa = min(2.0, estimativa_total_ajustada / 3.0)  # Normalizado para 0-2
    
    # FATOR 2: Estilo dos times (defensivo/ofensivo)
    fator_estilo = 1.0 - ajuste_defensivo  # Valores mais altos favorecem OVER
    
    # FATOR 3: Histórico de Under/Over
    fator_historico_under = (media_under_25 * 0.5 + media_under_15 * 0.5)
    fator_historico_over = (media_over_15 * 0.7 + (1 - media_under_25) * 0.3)
    
    # FATOR 4: Confronto direto de características
    fator_confronto = 1.0
    if tipo_confronto == "DEFENSIVO_DEFENSIVO":
        fator_confronto = 0.6  # Forte tendência UNDER
    elif tipo_confronto == "OFENSIVO_OFENSIVO":
        fator_confronto = 1.4  # Forte tendência OVER
    elif (home_defensivo and away_ofensivo) or (home_ofensivo and away_defensivo):
        fator_confronto = 1.0  # Equilíbrio
    
    # CÁLCULO DOS SCORES (0-1 scale)
    # Over 3.5: precisa de sinais MUITO fortes
    score_over_35 = max(0.05, (
        fator_estimativa * 0.6 + 
        fator_estilo * 0.2 + 
        (1 - fator_historico_under) * 0.1 + 
        max(0, fator_confronto - 1.0) * 0.1
    ) - 0.3)
    
    # Over 2.5: precisa de sinais fortes
    score_over_25 = (
        fator_estimativa * 0.4 + 
        fator_estilo * 0.3 + 
        (1 - fator_historico_under) * 0.2 + 
        max(0, fator_confronto - 1.0) * 0.1
    )
    
    # Over 1.5: mais comum, menos restritivo
    score_over_15 = min(0.95, (
        fator_estimativa * 0.5 + 
        fator_estilo * 0.2 + 
        fator_historico_over * 0.2 + 
        min(1.2, fator_confronto) * 0.1
    ))
    
    # Under 2.5: oposto do Over 2.5
    score_under_25 = 1.0 - score_over_25
    
    # Under 1.5: oposto do Over 1.5
    score_under_15 = 1.0 - score_over_15
    
    # ============================================================
    # LÓGICA DECISÓRIA INTELIGENTE COM TODAS AS OPÇÕES
    # ============================================================
    
    # Definir limiares ajustados
    limiar_under_15 = 0.65  # 65% de chance para UNDER 1.5
    limiar_under_25 = 0.60  # 60% de chance para UNDER 2.5
    limiar_over_15 = 0.70   # 70% de chance para OVER 1.5
    limiar_over_25 = 0.60   # 60% de chance para OVER 2.5
    limiar_over_35 = 0.55   # 55% de chance para OVER 3.5
    
    # DECISÃO 1: UNDER 1.5 (prioridade máxima se sinais fortes)
    if (score_under_15 > limiar_under_15 or 
        media_under_15 > 0.7 or 
        (home_defensivo and away_defensivo and estimativa_total_ajustada < 1.8) or
        estimativa_total_ajustada < 1.6):
        tendencia_principal = "UNDER 1.5"
        tipo_aposta = "under"
        probabilidade_base = score_under_15 * 100
        decisao = "DEFENSIVO_EXTREMO_OU_ESTIMATIVA_BAIXA"
        
    # DECISÃO 2: UNDER 2.5
    elif (score_under_25 > limiar_under_25 or
          media_under_25 > 0.65 or
          estimativa_total_ajustada < 2.3):
        tendencia_principal = "UNDER 2.5"
        tipo_aposta = "under"
        probabilidade_base = score_under_25 * 100
        decisao = "TENDENCIA_UNDER_FORTE"
        
    # DECISÃO 3: OVER 3.5 (apenas se sinais MUITO fortes)
    elif (score_over_35 > limiar_over_35 and
          estimativa_total_ajustada > 3.4 and
          (home_ofensivo or away_ofensivo) and
          tipo_confronto == "OFENSIVO_OFENSIVO"):
        tendencia_principal = "OVER 3.5"
        tipo_aposta = "over"
        probabilidade_base = score_over_35 * 100
        decisao = "OFENSIVO_EXTREMO"
        
    # DECISÃO 4: OVER 2.5
    elif (score_over_25 > limiar_over_25 or
          estimativa_total_ajustada > 2.8):
        tendencia_principal = "OVER 2.5"
        tipo_aposta = "over"
        probabilidade_base = score_over_25 * 100
        decisao = "TENDENCIA_OVER_FORTE"
        
    # DECISÃO 5: OVER 1.5 (jogos com estimativa moderada)
    elif (score_over_15 > limiar_over_15 or
          media_over_15 > 0.75 or
          estimativa_total_ajustada > 1.9):
        tendencia_principal = "OVER 1.5"
        tipo_aposta = "over"
        probabilidade_base = score_over_15 * 100
        decisao = "TENDENCIA_OVER_MODERADA"
        
    # DECISÃO 6: FALLBACK para a estimativa pura
    else:
        # Lógica baseada apenas na estimativa ajustada
        if estimativa_total_ajustada < 1.5:
            tendencia_principal = "UNDER 1.5"
            tipo_aposta = "under"
            probabilidade_base = 65.0
            decisao = "FALLBACK_ESTIMATIVA_BAIXISSIMA"
        elif estimativa_total_ajustada < 2.0:
            tendencia_principal = "OVER 1.5"
            tipo_aposta = "over"
            probabilidade_base = 60.0
            decisao = "FALLBACK_ESTIMATIVA_BAIXA"
        elif estimativa_total_ajustada < 2.6:
            tendencia_principal = "UNDER 2.5"
            tipo_aposta = "under"
            probabilidade_base = 62.0
            decisao = "FALLBACK_ESTIMATIVA_MODERADA_UNDER"
        elif estimativa_total_ajustada < 3.2:
            tendencia_principal = "OVER 2.5"
            tipo_aposta = "over"
            probabilidade_base = 65.0
            decisao = "FALLBACK_ESTIMATIVA_MODERADA_OVER"
        else:
            tendencia_principal = "OVER 3.5"
            tipo_aposta = "over"
            probabilidade_base = 58.0
            decisao = "FALLBACK_ESTIMATIVA_ALTA"
    
    # ============================================================
    # CÁLCULO DA CONFIANÇA BASEADA NA CONCORDÂNCIA
    # ============================================================
    
    # Verificar concordância entre sinais
    sinais = []
    
    # Sinal 1: Estimativa
    if (tipo_aposta == "under" and estimativa_total_ajustada < 2.5) or \
       (tipo_aposta == "over" and estimativa_total_ajustada > 1.5):
        sinais.append("ESTIMATIVA")
    
    # Sinal 2: Estilo dos times
    if (tipo_aposta == "under" and ajuste_defensivo > 0.6) or \
       (tipo_aposta == "over" and ajuste_defensivo < 0.4):
        sinais.append("ESTILO")
    
    # Sinal 3: Histórico
    if tipo_aposta == "under":
        hist_relevante = max(media_under_15, media_under_25)
        if hist_relevante > 0.6:
            sinais.append("HISTORICO")
    else:  # over
        hist_relevante = media_over_15 if tendencia_principal == "OVER 1.5" else (1 - media_under_25)
        if hist_relevante > 0.6:
            sinais.append("HISTORICO")
    
    # Sinal 4: Tipo de confronto
    if (tipo_aposta == "under" and tipo_confronto == "DEFENSIVO_DEFENSIVO") or \
       (tipo_aposta == "over" and tipo_confronto == "OFENSIVO_OFENSIVO"):
        sinais.append("CONFRONTO")
    
    # Calcular confiança baseada na concordância
    total_sinais_possiveis = 4
    sinais_concordantes = len(sinais)
    concordancia_percent = sinais_concordantes / total_sinais_possiveis
    
    # Confiança base
    confianca_base = 50 + (concordancia_percent * 40)  # 50-90%
    
    # Ajustar pela força da probabilidade
    if probabilidade_base > 80:
        confianca_ajustada = min(95, confianca_base * 1.2)
    elif probabilidade_base > 70:
        confianca_ajustada = min(90, confianca_base * 1.1)
    elif probabilidade_base > 60:
        confianca_ajustada = confianca_base
    else:
        confianca_ajustada = max(40, confianca_base * 0.9)
    
    # Ajustar pela distância do limiar decisivo
    if "FALLBACK" in decisao:
        confianca_ajustada = confianca_ajustada * 0.8  # Reduz confiança no fallback
    
    # Limites finais
    probabilidade_final = max(1, min(99, round(probabilidade_base, 1)))
    confianca_final = max(20, min(95, round(confianca_ajustada, 1)))
    
    # ============================================================
    # DETALHES COMPLETOS PARA DEBUG E TRANSPARÊNCIA
    # ============================================================
    
    detalhes = {
        # Probabilidades de cada opção
        "over_35_prob": round(score_over_35 * 100, 1),
        "over_25_prob": round(score_over_25 * 100, 1),
        "over_15_prob": round(score_over_15 * 100, 1),
        "under_25_prob": round(score_under_25 * 100, 1),
        "under_15_prob": round(score_under_15 * 100, 1),
        
        # Confianças de cada opção
        "over_35_conf": round(confianca_final * score_over_35, 1),
        "over_25_conf": round(confianca_final * score_over_25, 1),
        "over_15_conf": round(confianca_final * score_over_15, 1),
        "under_25_conf": round(confianca_final * score_under_25, 1),
        "under_15_conf": round(confianca_final * score_under_15, 1),
        
        # Análise detalhada para debug
        "analise_detalhada": {
            "estimativa_ajustada": round(estimativa_total_ajustada, 2),
            "estimativa_crua": round(estimativa_total, 2),
            "home_defensivo": home_defensivo,
            "away_defensivo": away_defensivo,
            "home_ofensivo": home_ofensivo,
            "away_ofensivo": away_ofensivo,
            "tipo_confronto": tipo_confronto,
            "media_under_15": round(media_under_15, 3),
            "media_under_25": round(media_under_25, 3),
            "media_over_15": round(media_over_15, 3),
            "sinais_concordantes": sinais_concordantes,
            "sinais": sinais,
            "decisao": decisao,
            "score_over_15": round(score_over_15, 3),
            "score_over_25": round(score_over_25, 3),
            "score_over_35": round(score_over_35, 3),
            "score_under_15": round(score_under_15, 3),
            "score_under_25": round(score_under_25, 3),
        }
    }
    
    # Log para debugging
    logging.info(
        f"ANÁLISE INTELIGENTE: {home} vs {away} | "
        f"Est: {estimativa_total_ajustada:.2f} | "
        f"Tend: {tendencia_principal} | "
        f"Prob: {probabilidade_final:.1f}% | "
        f"Conf: {confianca_final:.1f}% | "
        f"Sinais: {sinais_concordantes}/4 | "
        f"Decisão: {decisao}"
    )
    
    return {
        "tendencia": tendencia_principal,
        "estimativa": round(estimativa_total_ajustada, 2),
        "probabilidade": probabilidade_final,
        "confianca": confianca_final,
        "tipo_aposta": tipo_aposta,
        "detalhes": detalhes
    }

def gerar_poster_individual_westham(fixture: dict, analise: dict) -> io.BytesIO:
    """
    Gera poster individual no estilo West Ham para alertas individuais
    """
    # Configurações
    LARGURA = 1800
    ALTURA = 1200
    PADDING = 80

    # Criar canvas
    img = Image.new("RGB", (LARGURA, ALTURA), color=(10, 20, 30))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(80)
    FONTE_SUBTITULO = criar_fonte(60)
    FONTE_TIMES = criar_fonte(55)
    FONTE_VS = criar_fonte(45)
    FONTE_INFO = criar_fonte(40)
    FONTE_DETALHES = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(50)
    FONTE_ALERTA = criar_fonte(70)
    FONTE_ESTATISTICAS = criar_fonte(35)

    # Título PRINCIPAL - ALERTA
    tipo_alerta = "🎯 ALERTA OVER" if analise["tipo_aposta"] == "over" else "🛡️ ALERTA UNDER"
    titulo_text = f"{tipo_alerta} DE GOLS"
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_ALERTA)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        cor_titulo = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
        draw.text(((LARGURA - titulo_w) // 2, 60), titulo_text, font=FONTE_ALERTA, fill=cor_titulo)
    except:
        draw.text((LARGURA//2 - 200, 60), titulo_text, font=FONTE_ALERTA, fill=(255, 215, 0))

    # Linha decorativa
    cor_linha = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
    draw.line([(LARGURA//4, 150), (3*LARGURA//4, 150)], fill=cor_linha, width=4)

    # Informações da partida
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    status = fixture.get("status", "DESCONHECIDO")

    # Nome da liga
    try:
        liga_bbox = draw.textbbox((0, 0), competicao.upper(), font=FONTE_SUBTITULO)
        liga_w = liga_bbox[2] - liga_bbox[0]
        draw.text(((LARGURA - liga_w) // 2, 180), competicao.upper(), font=FONTE_SUBTITULO, fill=(200, 200, 200))
    except:
        draw.text((LARGURA//2 - 150, 180), competicao.upper(), font=FONTE_SUBTITULO, fill=(200, 200, 200))

    # Data e hora
    data_hora_text = f"{data_formatada} • {hora_formatada} BRT • {status}"
    try:
        data_bbox = draw.textbbox((0, 0), data_hora_text, font=FONTE_INFO)
        data_w = data_bbox[2] - data_bbox[0]
        draw.text(((LARGURA - data_w) // 2, 260), data_hora_text, font=FONTE_INFO, fill=(150, 200, 255))
    except:
        draw.text((LARGURA//2 - 150, 260), data_hora_text, font=FONTE_INFO, fill=(150, 200, 255))

    # ESCUDOS DOS TIMES
    TAMANHO_ESCUDO = 180
    TAMANHO_QUADRADO = 220
    ESPACO_ENTRE_ESCUDOS = 500

    # Calcular posição central
    largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    x_inicio = (LARGURA - largura_total) // 2

    x_home = x_inicio
    x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    y_escudos = 350

    # Baixar escudos
    escudo_home_url = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
    escudo_away_url = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
    
    escudo_home = baixar_imagem_url(escudo_home_url)
    escudo_away = baixar_imagem_url(escudo_away_url)

    def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
        # Fundo branco
        draw.rectangle(
            [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
            fill=(255, 255, 255),
            outline=(255, 255, 255)
        )

        if logo_img is None:
            # Placeholder caso falhe
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
            draw.text((x + 60, y + 80), "SEM", font=FONTE_INFO, fill=(255, 255, 255))
            return

        try:
            logo_img = logo_img.convert("RGBA")
            largura, altura = logo_img.size
            proporcao = largura / altura

            # Cortar a imagem centralmente para ficar quadrada
            if proporcao > 1:  # mais larga
                nova_altura = altura
                nova_largura = int(altura)
                offset_x = (largura - nova_largura) // 2
                offset_y = 0
            else:  # mais alta
                nova_largura = largura
                nova_altura = int(largura)
                offset_x = 0
                offset_y = (altura - nova_altura) // 2

            imagem_cortada = logo_img.crop((offset_x, offset_y, offset_x + nova_largura, offset_y + nova_altura))

            # Redimensionar
            imagem_final = imagem_cortada.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)

            # Calcular centralização
            pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
            pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2

            # Colar escudo
            img.paste(imagem_final, (pos_x, pos_y), imagem_final)

        except Exception as e:
            logging.error(f"Erro ao processar escudo: {e}")
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
            draw.text((x + 60, y + 80), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

    # Desenhar escudos quadrados
    desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
    desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

    # Nomes dos times
    home_text = home[:20]  # Limitar tamanho
    away_text = away[:20]

    try:
        home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
        home_w = home_bbox[2] - home_bbox[0]
        draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 40),
                 home_text, font=FONTE_TIMES, fill=(255, 255, 255))
    except:
        draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 40),
                 home_text, font=FONTE_TIMES, fill=(255, 255, 255))

    try:
        away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
        away_w = away_bbox[2] - away_bbox[0]
        draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 40),
                 away_text, font=FONTE_TIMES, fill=(255, 255, 255))
    except:
        draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 40),
                 away_text, font=FONTE_TIMES, fill=(255, 255, 255))

    # VS centralizado
    try:
        vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
        vs_w = vs_bbox[2] - vs_bbox[0]
        vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
        draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 25), 
                 "VS", font=FONTE_VS, fill=(255, 215, 0))
    except:
        vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 25
        draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 25), "VS", font=FONTE_VS, fill=(255, 215, 0))

    # SEÇÃO DE ANÁLISE PRINCIPAL
    y_analysis = y_escudos + TAMANHO_QUADRADO + 120
    
    # Linha separadora
    draw.line([(PADDING + 50, y_analysis - 20), (LARGURA - PADDING - 50, y_analysis - 20)], 
             fill=(100, 130, 160), width=3)

    # Tendência principal com destaque
    tendencia_emoji = "📈" if analise["tipo_aposta"] == "over" else "📉"
    cor_tendencia = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
    
    textos_analise = [
        f"{tendencia_emoji} TENDÊNCIA: {analise['tendencia']}",
        f"⚽ ESTIMATIVA: {analise['estimativa']:.2f} GOLS",
        f"🎯 PROBABILIDADE: {analise['probabilidade']:.0f}%",
        f"🔍 CONFIANÇA: {analise['confianca']:.0f}%"
    ]
    
    cores = [cor_tendencia, (100, 200, 255), (100, 255, 100), (255, 193, 7)]
    
    for i, (text, cor) in enumerate(zip(textos_analise, cores)):
        try:
            bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
            w = bbox[2] - bbox[0]
            draw.text(((LARGURA - w) // 2, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)
        except:
            draw.text((PADDING + 100, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)

    # ESTATÍSTICAS DETALHADAS
    y_estatisticas = y_analysis + 280
    
    # Título estatísticas
    stats_title = "📊 ESTATÍSTICAS DETALHADAS"
    try:
        title_bbox = draw.textbbox((0, 0), stats_title, font=FONTE_DETALHES)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((LARGURA - title_w) // 2, y_estatisticas), stats_title, font=FONTE_DETALHES, fill=(200, 200, 200))
    except:
        draw.text((LARGURA//2 - 150, y_estatisticas), stats_title, font=FONTE_DETALHES, fill=(200, 200, 200))

    # Estatísticas em duas colunas
    y_stats = y_estatisticas + 60
    
    col1_stats = [
        f"Over 2.5: {analise['detalhes']['over_25_prob']}% (Conf: {analise['detalhes']['over_25_conf']}%)",
        f"Under 2.5: {analise['detalhes']['under_25_prob']}% (Conf: {analise['detalhes']['under_25_conf']}%)"
    ]
    
    col2_stats = [
        f"Over 1.5: {analise['detalhes']['over_15_prob']}% (Conf: {analise['detalhes']['over_15_conf']}%)",
        f"Under 1.5: {analise['detalhes']['under_15_prob']}% (Conf: {analise['detalhes']['under_15_conf']}%)"
    ]
    
    # Coluna 1
    for i, stat in enumerate(col1_stats):
        draw.text((PADDING + 100, y_stats + i * 45), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
    
    # Coluna 2
    for i, stat in enumerate(col2_stats):
        try:
            bbox = draw.textbbox((0, 0), stat, font=FONTE_ESTATISTICAS)
            w = bbox[2] - bbox[0]
            draw.text((LARGURA - PADDING - 100 - w, y_stats + i * 45), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
        except:
            draw.text((LARGURA - PADDING - 300, y_stats + i * 45), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

    # Indicador de força da confiança
    y_indicator = y_estatisticas + 160
    if analise["confianca"] >= 80:
        indicador_text = "🔥🔥 ALTA CONFIABILIDADE 🔥🔥"
        cor_indicador = (76, 175, 80)  # Verde
    elif analise["confianca"] >= 60:
        indicador_text = "⚡⚡ MÉDIA CONFIABILIDADE ⚡⚡"
        cor_indicador = (255, 193, 7)   # Amarelo
    else:
        indicador_text = "⚠️⚠️ CONFIABILIDADE MODERADA ⚠️⚠️"
        cor_indicador = (255, 152, 0)   # Laranja

    try:
        ind_bbox = draw.textbbox((0, 0), indicador_text, font=FONTE_DETALHES)
        ind_w = ind_bbox[2] - ind_bbox[0]
        draw.text(((LARGURA - ind_w) // 2, y_indicator), indicador_text, font=FONTE_DETALHES, fill=cor_indicador)
    except:
        draw.text((LARGURA//2 - 200, y_indicator), indicador_text, font=FONTE_DETALHES, fill=cor_indicador)

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, ALTURA - 60), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 150, ALTURA - 60), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    return buffer

def enviar_alerta_telegram(fixture: dict, analise: dict):
    """Envia alerta individual com poster estilo West Ham"""
    try:
        # Gerar poster individual
        poster = gerar_poster_individual_westham(fixture, analise)
        
        # Criar caption para o Telegram
        home = fixture["homeTeam"]["name"]
        away = fixture["awayTeam"]["name"]
        data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
        competicao = fixture.get("competition", {}).get("name", "Desconhecido")
        
        tipo_emoji = "🎯" if analise["tipo_aposta"] == "over" else "🛡️"
        
        caption = (
            f"<b>{tipo_emoji} ALERTA {analise['tipo_aposta'].upper()} DE GOLS</b>\n\n"
            f"<b>🏆 {competicao}</b>\n"
            f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
            f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
            f"<b>📈 Tendência Principal: {analise['tendencia']}</b>\n"
            f"<b>⚽ Estimativa: {analise['estimativa']:.2f} gols</b>\n"
            f"<b>🎯 Probabilidade: {analise['probabilidade']:.0f}%</b>\n"
            f"<b>🔍 Confiança: {analise['confianca']:.0f}%</b>\n\n"
            f"<b>📊 Estatísticas Detalhadas:</b>\n"
            f"<b>• Over 2.5: {analise['detalhes']['over_25_prob']}%</b>\n"
            f"<b>• Under 2.5: {analise['detalhes']['under_25_prob']}%</b>\n"
            f"<b>• Over 1.5: {analise['detalhes']['over_15_prob']}%</b>\n"
            f"<b>• Under 1.5: {analise['detalhes']['under_15_prob']}%</b>\n\n"
            f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE PREDITIVA COMPLETA</b>"
        )
        
        # Enviar foto
        if enviar_foto_telegram(poster, caption=caption):
            st.success(f"📤 Alerta {analise['tipo_aposta']} individual enviado: {home} vs {away}")
            return True
        else:
            st.error(f"❌ Falha ao enviar alerta individual: {home} vs {away}")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao enviar alerta individual: {str(e)}")
        st.error(f"❌ Erro ao enviar alerta individual: {str(e)}")
        # Fallback para mensagem de texto
        return enviar_alerta_telegram_fallback(fixture, analise)

def enviar_alerta_telegram_fallback(fixture: dict, analise: dict) -> bool:
    """Fallback para alerta em texto caso o poster falhe"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    
    tipo_emoji = "🎯" if analise["tipo_aposta"] == "over" else "🛡️"
    
    msg = (
        f"<b>{tipo_emoji} ALERTA {analise['tipo_aposta'].upper()} DE GOLS</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>📈 Tendência: {analise['tendencia']}</b>\n"
        f"<b>⚽ Estimativa: {analise['estimativa']:.2f} gols</b>\n"
        f"<b>🎯 Probabilidade: {analise['probabilidade']:.0f}%</b>\n"
        f"<b>🔍 Confiança: {analise['confianca']:.0f}%</b>\n\n"
        f"<b>🔥 ELITE MASTER SYSTEM</b>"
    )
    
    return enviar_telegram(msg)

def verificar_enviar_alerta(fixture: dict, analise: dict, alerta_individual: bool, min_conf: int, max_conf: int):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    
    # Verificar se a confiança está dentro do intervalo configurado
    if min_conf <= analise["confianca"] <= max_conf and fixture_id not in alertas:
        alertas[fixture_id] = {
            "tendencia": analise["tendencia"],
            "estimativa": analise["estimativa"],
            "probabilidade": analise["probabilidade"],
            "confianca": analise["confianca"],
            "tipo_aposta": analise["tipo_aposta"],
            "detalhes": analise["detalhes"],
            "conferido": False
        }
        # Só envia alerta individual se a checkbox estiver ativada
        if alerta_individual:
            enviar_alerta_telegram(fixture, analise)
        salvar_alertas(alertas)

# =============================
# SISTEMA DE ALERTAS DE RESULTADOS COM POSTERS RED/GREEN
# =============================

def verificar_resultados_finais(alerta_resultados: bool):
    """Verifica resultados finais dos jogos e envia alertas - VERSÃO CORRIGIDA"""
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para verificar resultados.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        # Pular se já foi conferido
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture_data = obter_dados_api(url)
            
            if not fixture_data:
                continue
                
            match = fixture_data.get('match', fixture_data)  # Algumas APIs usam 'match'
            status = match.get("status", "")
            score = match.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
            # Verificar se jogo terminou e tem resultado válido
            if (status == "FINISHED" and 
                home_goals is not None and 
                away_goals is not None):
                
                jogo_resultado = {
                    "id": fixture_id,
                    "home": match["homeTeam"]["name"],
                    "away": match["awayTeam"]["name"],
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "liga": match.get("competition", {}).get("name", "Desconhecido"),
                    "data": match["utcDate"],
                    "tendencia_prevista": alerta.get("tendencia", "Desconhecida"),
                    "estimativa_prevista": alerta.get("estimativa", 0),
                    "probabilidade_prevista": alerta.get("probabilidade", 0),
                    "confianca_prevista": alerta.get("confianca", 0),
                    "tipo_aposta": alerta.get("tipo_aposta", "desconhecido"),
                    "escudo_home": match.get("homeTeam", {}).get("crest") or "",
                    "escudo_away": match.get("awayTeam", {}).get("crest") or ""
                }
                
                jogos_com_resultado.append(jogo_resultado)
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            logging.error(f"Erro ao verificar jogo {fixture_id}: {e}")
            st.error(f"Erro ao verificar jogo {fixture_id}: {e}")
    
    # Enviar alertas em lote se houver resultados E a checkbox estiver ativada
    if jogos_com_resultado and alerta_resultados:
        enviar_alerta_resultados_poster(jogos_com_resultado)
        salvar_alertas(alertas)
        st.success(f"✅ {resultados_enviados} resultados processados e alertas enviados!")
    elif jogos_com_resultado:
        st.info(f"ℹ️ {resultados_enviados} resultados encontrados, mas alerta de resultados desativado")
        # Apenas marca como conferido sem enviar alerta
        salvar_alertas(alertas)
    else:
        st.info("ℹ️ Nenhum novo resultado final encontrado.")

def gerar_poster_resultados(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS OFICIAIS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais dos jogos - VERSÃO ATUALIZADA COM FUNDO QUADRADO
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950  # Ajustado para melhor layout
    PADDING = 120
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(70)
    FONTE_PLACAR = criar_fonte(100)
    FONTE_VS = criar_fonte(70)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_RESULTADO = criar_fonte(70)  # Fonte maior para RED/GREEN

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 180), (3*LARGURA//4, 180)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # Calcular se a previsão foi correta ANTES de desenhar
        total_gols = jogo['home_goals'] + jogo['away_goals']
        previsao_correta = False
        
        # Verificar para Over 2.5
        if jogo['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5:
            previsao_correta = True
        # Verificar para Under 2.5
        elif jogo['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5:
            previsao_correta = True
        # Verificar para Over 1.5
        elif jogo['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5:
            previsao_correta = True
        # Verificar para Under 1.5
        elif jogo['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5:
            previsao_correta = True
        
        # Definir cores baseadas no resultado
        if previsao_correta:
            cor_borda = (76, 175, 80)  # VERDE
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)  # VERMELHO
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        # Caixa do jogo com borda colorida conforme resultado
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda colorida (VERDE ou VERMELHA)
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=6)

        # BADGE RESULTADO (GREEN/RED) - NO CANTO SUPERIOR DIREITO
        badge_text = texto_resultado
        badge_bg_color = cor_resultado
        badge_text_color = (255, 255, 255)
        
        # Calcular tamanho do badge
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 40
            badge_h = 90
            badge_x = x1 - badge_w - 20
            badge_y = y0 + 20
            
            # Desenhar badge
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=badge_bg_color, outline=badge_bg_color)
            draw.text((badge_x + 20, badge_y + 10), badge_text, font=FONTE_RESULTADO, fill=badge_text_color)
        except:
            # Fallback se der erro no cálculo
            draw.rectangle([x1 - 180, y0 + 20, x1 - 20, y0 + 100], fill=badge_bg_color)
            draw.text((x1 - 160, y0 + 30), badge_text, font=FONTE_RESULTADO, fill=badge_text_color)

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))

        # Data do jogo
        data_formatada, hora_formatada = formatar_data_iso(jogo["data"])
        data_text = f"{data_formatada} • {hora_formatada} BRT"
        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 110), data_text, font=FONTE_INFO, fill=(120, 180, 240))
        except:
            draw.text((LARGURA//2 - 150, y0 + 110), data_text, font=FONTE_INFO, fill=(120, 180, 240))

        # ESCUDOS E PLACAR - AGORA COM FUNDO QUADRADO (NÃO REDONDO)
        TAMANHO_ESCUDO = 245
        TAMANHO_QUADRADO = 280  # Tamanho do fundo QUADRADO
        ESPACO_ENTRE_ESCUDOS = 700

        # Calcular posição central
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS 
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_placar = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 100
        x_away = x_placar + 450

        y_escudos = y0 + 180

        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get("escudo_home", ""))
        escudo_away = baixar_imagem_url(jogo.get("escudo_away", ""))

        def desenhar_escudo_quadrado_resultado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo QUADRADO BRANCO (ao invés de redondo)
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], 
                         fill=(255, 255, 255), outline=(220, 220, 220), width=3)

            if logo_img is None:
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(80, 80, 80))
                draw.text((x + 50, y + 65), "SEM", font=FONTE_INFO, fill=(255, 255, 255))
                return

            try:
                logo_img = logo_img.convert("RGBA")
                logo_img = logo_img.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)
                
                pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
                pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2

                img.paste(logo_img, (pos_x, pos_y), logo_img)

            except Exception as e:
                logging.error(f"Erro ao desenhar escudo resultado: {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 50, y + 65), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Desenhar escudos com fundo QUADRADO
        desenhar_escudo_quadrado_resultado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado_resultado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # PLACAR CENTRAL - GRANDE E EM DESTAQUE
        placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_placar + (200 - placar_w) // 2
            draw.text((placar_x, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            draw.text((x_placar, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))

        # Nomes dos times
        home_text = jogo['home'][:15]  # Limitar tamanho do nome
        away_text = jogo['away'][:15]

        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 20),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 20),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))

        # SEÇÃO DE ANÁLISE DO RESULTADO
        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        # Linha separadora
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

        # Informações de análise
        tipo_aposta_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
        
        textos_analise = [
            f"{tipo_aposta_emoji} {jogo['tendencia_prevista']}",
            f"Real: {total_gols} gols | Estimativa: {jogo['estimativa_prevista']:.2f}",
            f"Prob: {jogo['probabilidade_prevista']:.0f}% | Conf: {jogo['confianca_prevista']:.0f}% | Resultado: {texto_resultado}"
        ]
        
        cores = [(255, 255, 255), (200, 220, 255), cor_resultado]
        
        for i, (text, cor) in enumerate(zip(textos_analise, cores)):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                draw.text(((LARGURA - w) // 2, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)
            except:
                draw.text((PADDING + 100, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"Resultados oficiais • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        draw.text((LARGURA//2 - 300, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados GERADO com {len(jogos)} jogos - Sistema RED/GREEN - FUNDO QUADRADO")
    return buffer

def enviar_alerta_resultados_poster(jogos_com_resultado: list):
    """Envia alerta de resultados com poster para o Telegram - VERSÃO ATUALIZADA COM RED/GREEN"""
    if not jogos_com_resultado:
        st.warning("⚠️ Nenhum resultado para enviar")
        return

    try:
        # Agrupar por data
        jogos_por_data = {}
        for jogo in jogos_com_resultado:
            data_jogo = datetime.fromisoformat(jogo["data"].replace("Z", "+00:00")).date()
            if data_jogo not in jogos_por_data:
                jogos_por_data[data_jogo] = []
            
            # Calcular RED/GREEN para cada jogo
            total_gols = jogo['home_goals'] + jogo['away_goals']
            previsao_correta = False
            
            # Verificar para Over 2.5
            if jogo['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5:
                previsao_correta = True
            # Verificar para Under 2.5
            elif jogo['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5:
                previsao_correta = True
            # Verificar para Over 1.5
            elif jogo['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5:
                previsao_correta = True
            # Verificar para Under 1.5
            elif jogo['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5:
                previsao_correta = True
            
            jogo['resultado'] = "GREEN" if previsao_correta else "RED"
            jogos_por_data[data_jogo].append(jogo)

        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - RESULTADOS {data_str}"
            
            st.info(f"🎨 Gerando poster de resultados para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_resultados(jogos_data, titulo=titulo)
            
            # Calcular estatísticas ATUALIZADAS
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j.get('resultado') == "GREEN")
            red_count = total_jogos - green_count
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            # Separar Over e Under
            over_count = sum(1 for j in jogos_data if j.get('tipo_aposta') == "over")
            under_count = sum(1 for j in jogos_data if j.get('tipo_aposta') == "under")
            over_green = sum(1 for j in jogos_data if j.get('tipo_aposta') == "over" and j.get('resultado') == "GREEN")
            under_green = sum(1 for j in jogos_data if j.get('tipo_aposta') == "under" and j.get('resultado') == "GREEN")
            
            caption = (
                f"<b>🏁 RESULTADOS OFICIAIS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {red_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO POR TIPO:</b>\n"
                f"<b>📈 Over: {over_green}/{over_count} ({over_green/max(over_count,1)*100:.0f}%)</b>\n"
                f"<b>📉 Under: {under_green}/{under_count} ({under_green/max(under_count,1)*100:.0f}%)</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM - CONFIABILIDADE COMPROVADA</b>"
            )
            
            st.info("📤 Enviando resultados para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                st.success(f"🚀 Poster de resultados enviado para {data_str}!")
                
                # Registrar no histórico
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"], 
                        "tendencia": jogo["tendencia_prevista"],
                        "estimativa": jogo["estimativa_prevista"],
                        "confianca": jogo["confianca_prevista"],
                        "probabilidade": jogo["probabilidade_prevista"],
                        "placar": f"{jogo['home_goals']}x{jogo['away_goals']}",
                        "resultado": "🟢 GREEN" if jogo.get('resultado') == "GREEN" else "🔴 RED",
                        "tipo_aposta": jogo.get("tipo_aposta", "desconhecido")
                    })
            else:
                st.error(f"❌ Falha ao enviar poster de resultados para {data_str}")
                
    except Exception as e:
        logging.error(f"Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        # Fallback para mensagem de texto
        msg = f"🏁 RESULTADOS OFICIAIS - SISTEMA RED/GREEN:\n\n"
        for j in jogos_com_resultado[:5]:
            total_gols = j['home_goals'] + j['away_goals']
            resultado = "🟢 GREEN" if (
                (j['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5) or 
                (j['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5) or
                (j['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5) or
                (j['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5)
            ) else "🔴 RED"
            tipo_emoji = "📈" if j.get('tipo_aposta') == "over" else "📉"
            msg += f"{resultado} {tipo_emoji} {j['home']} {j['home_goals']}x{j['away_goals']} {j['away']}\n"
        enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)

# =============================
# Funções de geração de imagem
# =============================
def baixar_imagem_url(url: str, timeout: int = 8) -> Image.Image | None:
    """Tenta baixar uma imagem - VERSÃO CORRIGIDA"""
    if not url or url == "":
        return None
        
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        
        # Verificar se é realmente uma imagem
        content_type = resp.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logging.warning(f"URL não é uma imagem: {content_type}")
            return None
            
        img = Image.open(io.BytesIO(resp.content))
        return img.convert("RGBA")
        
    except Exception as e:
        logging.error(f"Erro ao baixar imagem {url}: {e}")
        return None

def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
    """Cria fonte com fallback robusto - VERSÃO CORRIGIDA"""
    try:
        # Tentar fontes do sistema
        font_paths = [
            "arial.ttf", "Arial.ttf", "arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, tamanho)
            except Exception:
                continue
        
        # Fallback para fonte padrão do PIL
        return ImageFont.load_default()
        
    except Exception as e:
        logging.error(f"Erro ao carregar fonte: {e}")
        return ImageFont.load_default()

def gerar_poster_westham_style(jogos: list, titulo: str = "ELITE MASTER - ALERTA DE GOLS") -> io.BytesIO:
    """
    Gera poster no estilo West Ham vs Burnley
    """
    # Configurações
    LARGURA = 2000
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 1050  # Aumentado para incluir mais estatísticas
    PADDING = 120
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(70)
    FONTE_TIMES = criar_fonte(65)
    FONTE_VS = criar_fonte(55)
    FONTE_INFO = criar_fonte(50)
    FONTE_DETALHES = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(65)
    FONTE_ESTATISTICAS = criar_fonte(40)

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
    except:
        draw.text((LARGURA//2 - 250, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))

    # Linha decorativa
    draw.line([(LARGURA//4, 220), (3*LARGURA//4, 220)], fill=(255, 215, 0), width=6)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda
        cor_borda = (255, 215, 0) if jogo.get('tipo_aposta') == "over" else (100, 200, 255)
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

        # Data e hora
        if isinstance(jogo["hora"], datetime):
            data_text = jogo["hora"].strftime("%d.%m.%Y")
            hora_text = jogo["hora"].strftime("%H:%M")
        else:
            data_text = str(jogo["hora"])
            hora_text = ""

        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 130), data_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 150, y0 + 130), data_text, font=FONTE_INFO, fill=(150, 200, 255))

        try:
            hora_bbox = draw.textbbox((0, 0), hora_text, font=FONTE_INFO)
            hora_w = hora_bbox[2] - hora_bbox[0]
            draw.text(((LARGURA - hora_w) // 2, y0 + 190), hora_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 120, y0 + 190), hora_text, font=FONTE_INFO, fill=(150, 200, 255))

        # ESCUDOS DOS TIMES
        TAMANHO_ESCUDO = 200
        TAMANHO_QUADRADO = 240
        ESPACO_ENTRE_ESCUDOS = 700

        # Calcular posição central
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        y_escudos = y0 + 250

        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get("escudo_home", ""))
        escudo_away = baixar_imagem_url(jogo.get("escudo_away", ""))

        def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo branco
            draw.rectangle(
                [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                fill=(255, 255, 255),
                outline=(255, 255, 255)
            )

            if logo_img is None:
                # Placeholder caso falhe
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
                draw.text((x + 70, y + 90), "SEM", font=FONTE_INFO, fill=(255, 255, 255))
                return

            try:
                logo_img = logo_img.convert("RGBA")
                largura, altura = logo_img.size
                proporcao = largura / altura

                # Cortar a imagem centralmente para ficar quadrada
                if proporcao > 1:  # mais larga
                    nova_altura = altura
                    nova_largura = int(altura)
                    offset_x = (largura - nova_largura) // 2
                    offset_y = 0
                else:  # mais alta
                    nova_largura = largura
                    nova_altura = int(largura)
                    offset_x = 0
                    offset_y = (altura - nova_altura) // 2

                imagem_cortada = logo_img.crop((offset_x, offset_y, offset_x + nova_largura, offset_y + nova_altura))

                # Redimensionar
                imagem_final = imagem_cortada.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)

                # Calcular centralização
                pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
                pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2

                # Colar escudo
                img.paste(imagem_final, (pos_x, pos_y), imagem_final)

            except Exception as e:
                logging.error(f"Erro ao processar escudo West Ham: {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 70, y + 90), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Desenhar escudos quadrados
        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        home_text = jogo['home']
        away_text = jogo['away']

        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 50),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 50),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 50),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 50),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))

        # VS centralizado
        try:
            vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
            vs_w = vs_bbox[2] - vs_bbox[0]
            vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), 
                     "VS", font=FONTE_VS, fill=(255, 215, 0))
        except:
            vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 30
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), "VS", font=FONTE_VS, fill=(255, 215, 0))

        # SEÇÃO DE ANÁLISE PRINCIPAL
        y_analysis = y_escudos + TAMANHO_QUADRADO + 150
        
        # Linha separadora
        draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)

        # Informações de análise principal
        tipo_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
        cor_tendencia = (255, 215, 0) if jogo.get('tipo_aposta') == "over" else (100, 200, 255)
        
        textos_analise = [
            f"{tipo_emoji} {jogo['tendencia']}",
            f"Estimativa: {jogo['estimativa']:.2f} gols",
            f"Probabilidade: {jogo['probabilidade']:.0f}%",
            f"Confiança: {jogo['confianca']:.0f}%",
        ]
        
        cores = [cor_tendencia, (100, 200, 255), (100, 255, 100), (255, 193, 7)]
        
        for i, (text, cor) in enumerate(zip(textos_analise, cores)):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                draw.text(((LARGURA - w) // 2, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)
            except:
                draw.text((PADDING + 120, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)

        # ESTATÍSTICAS DETALHADAS
        y_stats = y_analysis + 360
        
        # Título estatísticas
        stats_title = "📊 Estatísticas Detalhadas:"
        draw.text((x0 + 100, y_stats), stats_title, font=FONTE_DETALHES, fill=(200, 200, 200))
        
        # Estatísticas em duas colunas
        y_stats_content = y_stats + 60
        
        if 'detalhes' in jogo:
            detalhes = jogo['detalhes']
            
            col1_stats = [
                f"Over 2.5: {detalhes.get('over_25_prob', 0):.0f}%",
                f"Under 2.5: {detalhes.get('under_25_prob', 0):.0f}%"
            ]
            
            col2_stats = [
                f"Over 1.5: {detalhes.get('over_15_prob', 0):.0f}%",
                f"Under 1.5: {detalhes.get('under_15_prob', 0):.0f}%"
            ]
            
            # Coluna 1
            for i, stat in enumerate(col1_stats):
                draw.text((x0 + 120, y_stats_content + i * 50), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
            
            # Coluna 2
            for i, stat in enumerate(col2_stats):
                draw.text((x0 + 500, y_stats_content + i * 50), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_DETALHES)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 250, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster estilo West Ham GERADO com {len(jogos)} jogos")
    return buffer

def enviar_alerta_westham_style(jogos_conf: list, min_conf: int, max_conf: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Envia alerta no estilo West Ham"""
    if not jogos_conf:
        st.warning("⚠️ Nenhum jogo para gerar poster")
        return

    try:
        # Agrupar por data
        jogos_por_data = {}
        for jogo in jogos_conf:
            data = jogo["hora"].date() if isinstance(jogo["hora"], datetime) else datetime.now().date()
            if data not in jogos_por_data:
                jogos_por_data[data] = []
            jogos_por_data[data].append(jogo)

        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - {data_str}"
            
            st.info(f"🎨 Gerando poster para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_westham_style(jogos_data, titulo=titulo)
            
            # Calcular estatísticas
            over_count = sum(1 for j in jogos_data if j.get('tipo_aposta') == "over")
            under_count = sum(1 for j in jogos_data if j.get('tipo_aposta') == "under")
            
            caption = (
                f"<b>🎯 ALERTA DE GOLS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                f"<b>📈 Over: {over_count} jogos</b>\n"
                f"<b>📉 Under: {under_count} jogos</b>\n"
                f"<b>⚽ INTERVALO DE CONFIANÇA: {min_conf}% - {max_conf}%</b>\n\n"
                f"<b>🔮 ANÁLISE PREDITIVA DE GOLS (OVER/UNDER)</b>\n"
                f"<b>📊 MÉDIA DE CONFIANÇA: {sum(j['confianca'] for j in jogos_data) / len(jogos_data):.1f}%</b>\n\n"
                f"<b>🔥 JOGOS SELECIONADOS PELA INTELIGÊNCIA ARTIFICIAL</b>"
            )
            
            st.info("📤 Enviando para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=chat_id)
            
            if ok:
                st.success(f"🚀 Poster enviado para {data_str}!")
            else:
                st.error(f"❌ Falha ao enviar poster para {data_str}")
                
    except Exception as e:
        logging.error(f"Erro crítico ao gerar/enviar poster West Ham: {str(e)}")
        st.error(f"❌ Erro crítico ao gerar/enviar poster: {str(e)}")
        # Fallback para mensagem de texto
        msg = f"🔥 Jogos com confiança entre {min_conf}% e {max_conf}% (Erro na imagem):\n"
        for j in jogos_conf[:5]:
            tipo_emoji = "📈" if j.get('tipo_aposta') == "over" else "📉"
            msg += f"{tipo_emoji} {j['home']} vs {j['away']} | {j['tendencia']} | Conf: {j['confianca']:.0f}%\n"
        enviar_telegram(msg, chat_id=chat_id)

# =============================
# FUNÇÕES PRINCIPAIS
# =============================

def debug_jogos_dia(data_selecionada, todas_ligas, liga_selecionada):
    """Função de debug para verificar os jogos retornados pela API"""
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]
    
    st.write("🔍 **DEBUG DETALHADO - JOGOS DA API**")
    
    for liga_id in ligas_busca:
        if liga_id == "BSA":  # Apenas para o Brasileirão
            jogos = obter_jogos_brasileirao(liga_id, hoje)
        else:
            jogos = obter_jogos(liga_id, hoje)
            
        st.write(f"**Liga {liga_id}:** {len(jogos)} jogos encontrados")
        
        for i, match in enumerate(jogos):
            try:
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                data_utc = match["utcDate"]
                status = match.get("status", "DESCONHECIDO")
                
                # Converter para horário correto
                hora_corrigida = formatar_data_iso_para_datetime(data_utc)
                data_br = hora_corrigida.strftime("%d/%m/%Y")
                hora_br = hora_corrigida.strftime("%H:%M")
                
                st.write(f"  {i+1}. {home} vs {away}")
                st.write(f"     UTC: {data_utc}")
                st.write(f"     BR: {data_br} {hora_br} | Status: {status}")
                st.write(f"     Competição: {match.get('competition', {}).get('name', 'Desconhecido')}")
                
            except Exception as e:
                st.write(f"  {i+1}. ERRO ao processar jogo: {e}")

def enviar_top_jogos(jogos: list, top_n: int, alerta_top_jogos: bool, min_conf: int, max_conf: int):
    """Envia os top jogos para o Telegram"""
    if not alerta_top_jogos:
        st.info("ℹ️ Alerta de Top Jogos desativado")
        return
        
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    jogos_filtrados = [j for j in jogos_filtrados if min_conf <= j["confianca"] <= max_conf]
    
    if not jogos_filtrados:
        st.warning(f"⚠️ Nenhum jogo elegível para o Top Jogos (confiança entre {min_conf}% e {max_conf}%).")
        return
        
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
    
    # Separar Over e Under
    over_jogos = [j for j in top_jogos_sorted if j.get('tipo_aposta') == "over"]
    under_jogos = [j for j in top_jogos_sorted if j.get('tipo_aposta') == "under"]
    
    msg = f"📢 TOP {top_n} Jogos do Dia (confiança: {min_conf}%-{max_conf}%)\n\n"
    
    if over_jogos:
        msg += f"📈 <b>OVER ({len(over_jogos)} jogos):</b>\n"
        for j in over_jogos:
            hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
                f"📈 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | "
                f"🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}%\n\n"
            )
    
    if under_jogos:
        msg += f"📉 <b>UNDER ({len(under_jogos)} jogos):</b>\n"
        for j in under_jogos:
            hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
                f"📉 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | "
                f"🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}%\n\n"
            )
        
    if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2, disable_web_page_preview=True):
        st.success(f"🚀 Top {top_n} jogos enviados para o canal!")
    else:
        st.error("❌ Erro ao enviar top jogos para o Telegram")

def atualizar_status_partidas():
    """Atualiza o status das partidas no cache"""
    cache_jogos = carregar_cache_jogos()
    mudou = False
    
    for key in list(cache_jogos.keys()):
        if key == "_timestamp":
            continue
            
        try:
            liga_id, data = key.split("_", 1)
            url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
            data_api = obter_dados_api(url)
            
            if data_api and "matches" in data_api:
                cache_jogos[key] = data_api["matches"]
                mudou = True
        except Exception as e:
            logging.error(f"Erro ao atualizar liga {key}: {e}")
            st.error(f"Erro ao atualizar liga {key}: {e}")
            
    if mudou:
        salvar_cache_jogos(cache_jogos)
        st.success("✅ Status das partidas atualizado!")
    else:
        st.info("ℹ️ Nenhuma atualização disponível.")

def conferir_resultados():
    """Conferir resultados dos jogos"""
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para conferir.")
        return
        
    st.info("🔍 Conferindo resultados...")
    resultados_conferidos = 0
    for fixture_id, alerta in alertas.items():
        if not alerta.get("conferido", False):
            alerta["conferido"] = True
            resultados_conferidos += 1
    
    if resultados_conferidos > 0:
        salvar_alertas(alertas)
        st.success(f"✅ {resultados_conferidos} resultados conferidos!")
    else:
        st.info("ℹ️ Nenhum novo resultado para conferir.")

def limpar_caches():
    """Limpar caches do sistema"""
    try:
        arquivos_limpos = 0
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                arquivos_limpos += 1
        st.success(f"✅ {arquivos_limpos} caches limpos com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao limpar caches: {e}")
        st.error(f"❌ Erro ao limpar caches: {e}")

def calcular_desempenho(qtd_jogos: int = 50):
    """Calcular desempenho das previsões"""
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
        
    st.info(f"📊 Calculando desempenho dos últimos {qtd_jogos} jogos...")
    
    historico_recente = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico
    
    if not historico_recente:
        st.warning("⚠️ Histórico insuficiente para cálculo.")
        return
        
    total_jogos = len(historico_recente)
    
    # Separar Over e Under
    over_jogos = [h for h in historico_recente if h.get('tipo_aposta') == "over"]
    under_jogos = [h for h in historico_recente if h.get('tipo_aposta') == "under"]
    
    # Calcular acertos
    over_green = sum(1 for h in over_jogos if "GREEN" in str(h.get('resultado', '')))
    under_green = sum(1 for h in under_jogos if "GREEN" in str(h.get('resultado', '')))
    
    over_total = len(over_jogos)
    under_total = len(under_jogos)
    
    taxa_over = (over_green / over_total * 100) if over_total > 0 else 0
    taxa_under = (under_green / under_total * 100) if under_total > 0 else 0
    taxa_geral = ((over_green + under_green) / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho calculado para {total_jogos} jogos!")
    
    # Métricas básicas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Jogos", total_jogos)
    with col2:
        st.metric("Taxa de Acerto Geral", f"{taxa_geral:.1f}%")
    with col3:
        st.metric("Confiança Média", f"{sum(h.get('confianca', 0) for h in historico_recente) / total_jogos:.1f}%")
    
    # Métricas por tipo
    st.subheader("📊 Desempenho por Tipo")
    col4, col5 = st.columns(2)
    with col4:
        st.metric("📈 Over", f"{over_green}/{over_total}", f"{taxa_over:.1f}%")
    with col5:
        st.metric("📉 Under", f"{under_green}/{under_total}", f"{taxa_under:.1f}%")

def calcular_desempenho_periodo(data_inicio, data_fim):
    """Calcular desempenho por período"""
    st.info(f"📊 Calculando desempenho de {data_inicio} a {data_fim}...")
    
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
        
    # Filtrar histórico por período
    historico_periodo = []
    for registro in historico:
        try:
            data_registro = datetime.strptime(registro.get("data_conferencia", ""), "%Y-%m-%d %H:%M:%S").date()
            if data_inicio <= data_registro <= data_fim:
                historico_periodo.append(registro)
        except:
            continue
            
    if not historico_periodo:
        st.warning(f"⚠️ Nenhum jogo encontrado no período {data_inicio} a {data_fim}.")
        return
        
    total_jogos = len(historico_periodo)
    
    # Separar Over e Under
    over_jogos = [h for h in historico_periodo if h.get('tipo_aposta') == "over"]
    under_jogos = [h for h in historico_periodo if h.get('tipo_aposta') == "under"]
    
    # Calcular acertos
    over_green = sum(1 for h in over_jogos if "GREEN" in str(h.get('resultado', '')))
    under_green = sum(1 for h in under_jogos if "GREEN" in str(h.get('resultado', '')))
    
    over_total = len(over_jogos)
    under_total = len(under_jogos)
    
    taxa_over = (over_green / over_total * 100) if over_total > 0 else 0
    taxa_under = (under_green / under_total * 100) if under_total > 0 else 0
    taxa_geral = ((over_green + under_green) / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho do período calculado! {total_jogos} jogos analisados.")
    
    # Métricas do período
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Jogos no Período", total_jogos)
    with col2:
        st.metric("Dias Analisados", (data_fim - data_inicio).days)
    with col3:
        st.metric("Acerto Geral", f"{taxa_geral:.1f}%")
    
    # Métricas por tipo
    st.subheader("📊 Desempenho por Tipo")
    col4, col5 = st.columns(2)
    with col4:
        st.metric("📈 Over", f"{over_green}/{over_total}", f"{taxa_over:.1f}%")
    with col5:
        st.metric("📉 Under", f"{under_green}/{under_total}", f"{taxa_under:.1f}%")

# =============================
# Interface Streamlit com Monitoramento
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols Over/Under", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos Over/Under")

    # Sidebar - CONFIGURAÇÕES DE ALERTAS
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        
        # Checkboxes para cada tipo de alerta
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True, 
                                       help="Envia alerta individual para cada jogo com confiança alta")
        
        alerta_poster = st.checkbox("📊 Alertas com Poster", value=True,
                                   help="Envia poster com múltiplos jogos acima do limiar")
        
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True,
                                      help="Envia lista dos top jogos do dia")
        
        alerta_resultados = st.checkbox("🏁 Resultados Finais", value=True,
                                       help="Envia alerta de resultados com sistema RED/GREEN")
        
        st.markdown("----")
        
        st.header("Configurações Gerais")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        
        # Dois cursores para intervalo de confiança
        col_min, col_max = st.columns(2)
        with col_min:
            min_conf = st.slider("Confiança Mínima (%)", 10, 95, 70, 1)
        with col_max:
            max_conf = st.slider("Confiança Máxima (%)", min_conf, 95, 95, 1)
        
        estilo_poster = st.selectbox("🎨 Estilo do Poster", ["West Ham (Novo)", "Elite Master (Original)"], index=0)
        
        # Filtro por tipo de aposta
        tipo_filtro = st.selectbox("🔍 Filtrar por Tipo", ["Todos", "Apenas Over", "Apenas Under"], index=0)
        
        st.markdown("----")
        st.info(f"Intervalo de confiança: {min_conf}% a {max_conf}%")
        st.info(f"Filtro: {tipo_filtro}")

    # Controles principais
    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))

    # BOTÃO DE DEBUG
    if st.button("🐛 Debug Jogos (API)", type="secondary"):
        debug_jogos_dia(data_selecionada, todas_ligas, liga_selecionada)

    # Processamento
    if st.button("🔍 Buscar Partidas", type="primary"):
        processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, min_conf, max_conf, estilo_poster, 
                       alerta_individual, alerta_poster, alerta_top_jogos, tipo_filtro)

    # Ações
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔄 Atualizar Status"):
            atualizar_status_partidas()
    with col2:
        if st.button("📊 Conferir Resultados"):
            conferir_resultados()
    with col3:
        if st.button("🏁 Verificar Resultados Finais", type="secondary"):
            verificar_resultados_finais(alerta_resultados)
    with col4:
        if st.button("🧹 Limpar Cache"):
            limpar_caches()

    # Painel de monitoramento da API
    st.markdown("---")
    st.subheader("📊 Monitoramento da API")

    col_mon1, col_mon2, col_mon3, col_mon4 = st.columns(4)

    stats = api_monitor.get_stats()
    with col_mon1:
        st.metric("Total Requests", stats["total_requests"])
    with col_mon2:
        st.metric("Taxa de Sucesso", f"{stats['success_rate']}%")
    with col_mon3:
        st.metric("Requests/min", stats["requests_per_minute"])
    with col_mon4:
        st.metric("Rate Limit Hits", stats["rate_limit_hits"])

    if st.button("🔄 Resetar Monitor"):
        api_monitor.reset()
        st.success("✅ Monitor resetado!")

    # Painel de cache
    st.subheader("🗂️ Status do Cache")

    col_cache1, col_cache2, col_cache3 = st.columns(3)

    with col_cache1:
        cache_jogos_size = len(jogos_cache.cache)
        st.metric("Cache de Jogos", f"{cache_jogos_size}/{jogos_cache.config['max_size']}")

    with col_cache2:
        cache_class_size = len(classificacao_cache.cache)
        st.metric("Cache de Classificação", f"{cache_class_size}/{classificacao_cache.config['max_size']}")

    with col_cache3:
        cache_match_size = len(match_cache.cache)
        st.metric("Cache de Partidas", f"{cache_match_size}/{match_cache.config['max_size']}")

    if st.button("🧹 Limpar Caches Inteligentes"):
        jogos_cache.clear()
        classificacao_cache.clear()
        match_cache.clear()
        st.success("✅ Todos os caches inteligentes limpos!")

    # Painel desempenho
    st.markdown("---")
    st.subheader("📊 Painel de Desempenho")
    usar_periodo = st.checkbox("🔎 Usar período específico", value=False)
    qtd_default = 50
    last_n = st.number_input("Últimos N jogos", 1, 1000, qtd_default, 1)
    colp1, colp2 = st.columns(2)
    with colp1:
        if usar_periodo:
            data_inicio = st.date_input("Data inicial", value=(datetime.today() - timedelta(days=30)).date())
            data_fim = st.date_input("Data final", value=datetime.today().date())
    with colp2:
        if st.button("📈 Calcular Desempenho"):
            if usar_periodo:
                calcular_desempenho_periodo(data_inicio, data_fim)
            else:
                calcular_desempenho(qtd_jogos=last_n)

    if st.button("🧹 Limpar Histórico"):
        limpar_historico()

    # Adicionar dicas de uso
    with st.expander("💡 Dicas para evitar rate limit"):
        st.markdown("""
        1. **Use o cache**: O sistema armazena dados por 1-24 horas
        2. **Evite buscas frequentes**: Não atualize mais que 1x por minuto
        3. **Use datas específicas**: Evite buscar intervalos muito grandes
        4. **Monitore os limites**: Fique atento ao contador de requests
        5. **Priorize ligas**: Analise uma liga por vez quando possível
        6. **Use o filtro por confiança**: Reduz a quantidade de jogos analisados
        """)

def processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, min_conf, max_conf, estilo_poster, 
                   alerta_individual: bool, alerta_poster: bool, alerta_top_jogos: bool, tipo_filtro: str):
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
    
    top_jogos = []
    progress_bar = st.progress(0)
    total_ligas = len(ligas_busca)

    # Pré-busca todas as classificações primeiro (uma por liga)
    classificacoes = {}
    for liga_id in ligas_busca:
        classificacoes[liga_id] = obter_classificacao(liga_id)
    
    for i, liga_id in enumerate(ligas_busca):
        classificacao = classificacoes[liga_id]
        
        # CORREÇÃO: Para o Brasileirão usar busca especial que considera fuso horário
        if liga_id == "BSA":  # Campeonato Brasileiro
            jogos = obter_jogos_brasileirao(liga_id, hoje)
            st.write(f"📊 Liga BSA: {len(jogos)} jogos encontrados (com correção de fuso horário)")
        else:
            jogos = obter_jogos(liga_id, hoje)
            st.write(f"📊 Liga {liga_id}: {len(jogos)} jogos encontrados")

        # Processa em batch para evitar muitos requests seguidos
        batch_size = 5
        for j in range(0, len(jogos), batch_size):
            batch = jogos[j:j+batch_size]
            
            for match in batch:
                # Validar dados do jogo
                if not validar_dados_jogo(match):
                    continue
                    
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                
                # Usar nova função de análise completa
                analise = calcular_tendencia_completa(home, away, classificacao)

                # DEBUG: Mostrar cada jogo processado
                data_utc = match["utcDate"]
                hora_corrigida = formatar_data_iso_para_datetime(data_utc)
                data_br = hora_corrigida.strftime("%d/%m/%Y")
                hora_br = hora_corrigida.strftime("%H:%M")
                
                tipo_emoji = "📈" if analise["tipo_aposta"] == "over" else "📉"
                
                st.write(f"   {tipo_emoji} {home} vs {away}")
                st.write(f"      🕒 {data_br} {hora_br} | {analise['tendencia']}")
                st.write(f"      ⚽ Estimativa: {analise['estimativa']:.2f} | 🎯 Prob: {analise['probabilidade']:.0f}% | 🔍 Conf: {analise['confianca']:.0f}%")
                st.write(f"      Status: {match.get('status', 'DESCONHECIDO')}")

                # Só envia alerta individual se a checkbox estiver ativada E se estiver no intervalo
                if min_conf <= analise["confianca"] <= max_conf:
                    # Aplicar filtro por tipo
                    if tipo_filtro == "Todos" or \
                       (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or \
                       (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                        
                        verificar_enviar_alerta(match, analise, alerta_individual, min_conf, max_conf)

                # Extrair escudos
                escudo_home = ""
                escudo_away = ""
                try:
                    escudo_home = match.get("homeTeam", {}).get("crest") or match.get("homeTeam", {}).get("logo") or ""
                    escudo_away = match.get("awayTeam", {}).get("crest") or match.get("awayTeam", {}).get("logo") or ""
                except Exception:
                    pass

                top_jogos.append({
                    "id": match["id"],
                    "home": home,
                    "away": away,
                    "tendencia": analise["tendencia"],
                    "estimativa": analise["estimativa"],
                    "probabilidade": analise["probabilidade"],
                    "confianca": analise["confianca"],
                    "tipo_aposta": analise["tipo_aposta"],
                    "liga": match.get("competition", {}).get("name", "Desconhecido"),
                    "hora": hora_corrigida,
                    "status": match.get("status", "DESCONHECIDO"),
                    "escudo_home": escudo_home,
                    "escudo_away": escudo_away,
                    "detalhes": analise["detalhes"]
                })
            
            # Pequena pausa entre batches para respeitar rate limit
            if j + batch_size < len(jogos):
                time.sleep(0.5)
        
        progress_bar.progress((i + 1) / total_ligas)

    # DEBUG COMPLETO: Mostrar todos os jogos processados
    st.write("🔍 **DEBUG FINAL - TODOS OS JOGOS PROCESSADOS:**")
    for jogo in top_jogos:
        data_str = jogo["hora"].strftime("%d/%m/%Y")
        hora_str = jogo["hora"].strftime("%H:%M")
        tipo_emoji = "📈" if jogo['tipo_aposta'] == "over" else "📉"
        st.write(f"{tipo_emoji} {jogo['home']} vs {jogo['away']}: {data_str} {hora_str} | {jogo['tendencia']} | Conf: {jogo['confianca']:.1f}% | Status: {jogo['status']}")

    # Filtrar por intervalo de confiança e tipo - DEBUG DETALHADO
    st.write(f"🔍 **DEBUG FILTRO POR INTERVALO ({min_conf}% - {max_conf}%) e TIPO ({tipo_filtro}):**")
    
    # Aplicar filtros
    jogos_filtrados = [
        j for j in top_jogos
        if min_conf <= j["confianca"] <= max_conf and 
           j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
    ]
    
    # Aplicar filtro por tipo
    if tipo_filtro == "Apenas Over":
        jogos_filtrados = [j for j in jogos_filtrados if j["tipo_aposta"] == "over"]
    elif tipo_filtro == "Apenas Under":
        jogos_filtrados = [j for j in jogos_filtrados if j["tipo_aposta"] == "under"]
    
    st.write(f"📊 Total de jogos: {len(top_jogos)}")
    st.write(f"📊 Jogos após filtros: {len(jogos_filtrados)}")
    
    # Separar Over e Under para estatísticas
    over_jogos = [j for j in jogos_filtrados if j["tipo_aposta"] == "over"]
    under_jogos = [j for j in jogos_filtrados if j["tipo_aposta"] == "under"]
    
    st.write(f"📈 Over: {len(over_jogos)} jogos")
    st.write(f"📉 Under: {len(under_jogos)} jogos")
    
    # Mostrar jogos que passaram no filtro
    if jogos_filtrados:
        st.write(f"✅ **Jogos no intervalo {min_conf}%-{max_conf}% ({tipo_filtro}):**")
        for jogo in jogos_filtrados:
            tipo_emoji = "📈" if jogo['tipo_aposta'] == "over" else "📉"
            st.write(f"   {tipo_emoji} {jogo['home']} vs {jogo['away']} - {jogo['tendencia']} - Conf: {jogo['confianca']:.1f}%")
        
        # Envia top jogos apenas se a checkbox estiver ativada
        enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf)
        st.success(f"✅ {len(jogos_filtrados)} jogos com confiança entre {min_conf}% e {max_conf}% ({tipo_filtro})")
        
        # ENVIAR ALERTA DE IMAGEM apenas se a checkbox estiver ativada
        if alerta_poster:
            st.info("🚨 Enviando alerta de imagem...")
            if estilo_poster == "West Ham (Novo)":
                enviar_alerta_westham_style(jogos_filtrados, min_conf, max_conf)
            else:
                enviar_alerta_conf_criar_poster(jogos_filtrados, min_conf, max_conf)
        else:
            st.info("ℹ️ Alerta com Poster desativado")
    else:
        st.warning(f"⚠️ Nenhum jogo com confiança entre {min_conf}% e {max_conf}% ({tipo_filtro})")
        
        # DEBUG: Mostrar por que não há jogos
        if top_jogos:
            st.write("🔍 **Razão para nenhum jogo passar:**")
            for jogo in top_jogos:
                motivo = ""
                if jogo["confianca"] < min_conf:
                    motivo = f"Confiança baixa ({jogo['confianca']:.1f}% < {min_conf}%)"
                elif jogo["confianca"] > max_conf:
                    motivo = f"Confiança alta demais ({jogo['confianca']:.1f}% > {max_conf}%)"
                elif jogo["status"] in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]:
                    motivo = f"Status: {jogo['status']}"
                elif tipo_filtro == "Apenas Over" and jogo["tipo_aposta"] != "over":
                    motivo = f"Tipo errado ({jogo['tipo_aposta']} != over)"
                elif tipo_filtro == "Apenas Under" and jogo["tipo_aposta"] != "under":
                    motivo = f"Tipo errado ({jogo['tipo_aposta']} != under)"
                else:
                    motivo = "DEVERIA PASSAR - VERIFICAR"
                
                tipo_emoji = "📈" if jogo['tipo_aposta'] == "over" else "📉"
                st.write(f"   ❌ {tipo_emoji} {jogo['home']} vs {jogo['away']}: {motivo}")

def enviar_alerta_conf_criar_poster(jogos_conf: list, min_conf: int, max_conf: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Função fallback para o estilo original"""
    if not jogos_conf:
        return
        
    try:
        # Separar Over e Under
        over_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "over"]
        under_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "under"]
        
        msg = f"🔥 Jogos com confiança {min_conf}%-{max_conf}% (Estilo Original):\n\n"
        
        if over_jogos:
            msg += f"📈 <b>OVER ({len(over_jogos)} jogos):</b>\n\n"
            for j in over_jogos:
                hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                msg += (
                    f"🏟️ {j['home']} vs {j['away']}\n"
                    f"🕒 {hora_format} BRT | {j['liga']}\n"
                    f"📈 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}%\n\n"
                )
        
        if under_jogos:
            msg += f"📉 <b>UNDER ({len(under_jogos)} jogos):</b>\n\n"
            for j in under_jogos:
                hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                msg += (
                    f"🏟️ {j['home']} vs {j['away']}\n"
                    f"🕒 {hora_format} BRT | {j['liga']}\n"
                    f"📉 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}%\n\n"
                )
        
        enviar_telegram(msg, chat_id=chat_id)
        st.success("📤 Alerta enviado (formato texto)")
    except Exception as e:
        logging.error(f"Erro no fallback de poster: {e}")
        st.error(f"Erro no fallback: {e}")

if __name__ == "__main__":
    main()
     #Analise o código acima e coloque persistência e Cache para evitar chamadas desnecessárias a ApI
