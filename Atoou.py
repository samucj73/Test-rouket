import streamlit as st
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import io
import time
from collections import deque
from threading import Lock
import threading
from PIL import Image, ImageDraw, ImageFont
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple

# =============================
# CLASSES BASE E CONFIGURAÇÕES
# =============================

class Config:
    """Configurações do sistema"""
    # API Keys
    API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8351165117:AAFmqb3NrPsmT86_8C360eYzK71Qda1ah_4")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
    TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
    
    # Paths
    ALERTAS_PATH = "alertas.json"
    CACHE_JOGOS = "cache_jogos.json"
    CACHE_CLASSIFICACAO = "cache_classificacao.json"
    HISTORICO_PATH = "historico_conferencias.json"
    ALERTAS_TOP_PATH = "alertas_top.json"
    
    # Constantes
    CACHE_TIMEOUT = 3600
    BASE_URL_FD = "https://api.football-data.org/v4"
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
    # Ligações
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
    
    # Configurações de cache
    CACHE_CONFIG = {
        "jogos": {"ttl": 3600, "max_size": 100},
        "classificacao": {"ttl": 86400, "max_size": 50},
        "match_details": {"ttl": 1800, "max_size": 200}
    }

class LoggingManager:
    """Gerenciador de logging"""
    @staticmethod
    def setup():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('sistema_alertas.log'),
                logging.StreamHandler()
            ]
        )

# =============================
# CLASSES DE CACHE
# =============================

class Cache:
    """Classe base para cache"""
    def __init__(self, cache_type: str):
        self.cache = {}
        self.timestamps = {}
        self.config = Config.CACHE_CONFIG.get(cache_type, {"ttl": 3600, "max_size": 100})
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache se ainda for válido"""
        with self.lock:
            if key not in self.cache:
                return None
                
            timestamp = self.timestamps.get(key, 0)
            agora = time.time()
            
            if agora - timestamp > self.config["ttl"]:
                del self.cache[key]
                del self.timestamps[key]
                return None
                
            return self.cache[key]
    
    def set(self, key: str, value: Any):
        """Armazena valor no cache"""
        with self.lock:
            if len(self.cache) >= self.config["max_size"]:
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

class ImageCache:
    """Cache especializado para imagens"""
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.max_size = 200
        self.ttl = 86400 * 7
        self.lock = threading.Lock()
        self.cache_dir = "escudos_cache"
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
    
    def get(self, team_name: str, crest_url: str) -> Optional[bytes]:
        """Obtém escudo do cache"""
        key = self._generate_key(team_name, crest_url)
        
        with self.lock:
            if key in self.cache:
                if time.time() - self.timestamps[key] <= self.ttl:
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.timestamps[key]
            
            file_path = os.path.join(self.cache_dir, f"{key}.png")
            if os.path.exists(file_path):
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age <= self.ttl:
                    try:
                        with open(file_path, "rb") as f:
                            img_data = f.read()
                        self.cache[key] = img_data
                        self.timestamps[key] = time.time()
                        return img_data
                    except Exception:
                        pass
        
        return None
    
    def set(self, team_name: str, crest_url: str, img_bytes: bytes):
        """Armazena escudo no cache"""
        key = self._generate_key(team_name, crest_url)
        
        with self.lock:
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.timestamps.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
                
                old_file = os.path.join(self.cache_dir, f"{oldest_key}.png")
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass
            
            self.cache[key] = img_bytes
            self.timestamps[key] = time.time()
            
            try:
                file_path = os.path.join(self.cache_dir, f"{key}.png")
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
            except Exception as e:
                logging.warning(f"Erro ao salvar escudo em disco: {e}")
    
    def _generate_key(self, team_name: str, crest_url: str) -> str:
        """Gera chave única para o cache"""
        combined = f"{team_name}_{crest_url}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def clear(self):
        """Limpa cache"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            try:
                for file in os.listdir(self.cache_dir):
                    try:
                        os.remove(os.path.join(self.cache_dir, file))
                    except:
                        pass
            except:
                pass

# =============================
# CLASSES DE API E COMUNICAÇÃO
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
        self.requests = deque(maxlen=10)
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 6.0
        self.backoff_factor = 1.5
        self.max_retries = 3
        
    def wait_if_needed(self):
        """Espera se necessário para respeitar rate limit"""
        with self.lock:
            now = time.time()
            
            while self.requests and now - self.requests[0] > 60:
                self.requests.popleft()
            
            if len(self.requests) >= 10:
                wait_time = 60 - (now - self.requests[0])
                if wait_time > 0:
                    logging.info(f"⏳ Rate limit atingido. Esperando {wait_time:.1f} segundos...")
                    time.sleep(wait_time + 0.1)
                    now = time.time()
            
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                time.sleep(wait_time)
            
            self.requests.append(now)
            self.last_request_time = now

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
    
    def get_stats(self) -> Dict[str, Any]:
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

class APIClient:
    """Cliente para comunicação com APIs"""
    def __init__(self):
        self.headers = {"X-Auth-Token": Config.API_KEY}
        self.rate_limiter = RateLimiter()
        self.monitor = APIMonitor()
    
    def get_with_retry(self, url: str, timeout: int = 15, max_retries: int = 3) -> Optional[Dict]:
        """Obtém dados da API com rate limiting e retry automático"""
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                
                logging.info(f"🔗 Request {attempt+1}/{max_retries}: {url}")
                
                response = requests.get(url, headers=self.headers, timeout=timeout)
                
                if response.status_code == 429:
                    self.monitor.log_request(False, True)
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logging.warning(f"⏳ Rate limit da API. Esperando {retry_after} segundos...")
                    time.sleep(retry_after)
                    continue
                    
                response.raise_for_status()
                
                self.monitor.log_request(True)
                
                remaining = response.headers.get('X-Requests-Remaining', 'unknown')
                reset_time = response.headers.get('X-RequestCounter-Reset', 'unknown')
                logging.info(f"✅ Request OK. Restantes: {remaining}, Reset: {reset_time}s")
                
                return response.json()
                
            except requests.exceptions.Timeout:
                logging.error(f"⌛ Timeout na tentativa {attempt+1} para {url}")
                self.monitor.log_request(False)
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logging.info(f"⏳ Esperando {wait_time}s antes de retry...")
                    time.sleep(wait_time)
                    
            except requests.RequestException as e:
                logging.error(f"❌ Erro na tentativa {attempt+1} para {url}: {e}")
                self.monitor.log_request(False)
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    st.error(f"❌ Falha após {max_retries} tentativas: {e}")
                    return None
                    
        return None
    
    def get_telegram(self, endpoint: str, params: Dict) -> bool:
        """Envia requisição para Telegram API"""
        try:
            url = f"{Config.BASE_URL_TG}/{endpoint}"
            response = requests.get(url, params=params, timeout=10)
            return response.status_code == 200
        except requests.RequestException as e:
            logging.error(f"Erro ao enviar para Telegram: {e}")
            st.error(f"Erro ao enviar para Telegram: {e}")
            return False
    
    def post_telegram(self, endpoint: str, data: Dict, files: Dict = None) -> bool:
        """Envia POST para Telegram API"""
        try:
            url = f"{Config.BASE_URL_TG}/{endpoint}"
            response = requests.post(url, data=data, files=files, timeout=15)
            return response.status_code == 200
        except requests.RequestException as e:
            logging.error(f"Erro POST para Telegram: {e}")
            st.error(f"Erro POST para Telegram: {e}")
            return False

class ImageDownloader:
    """Gerencia download de imagens"""
    def __init__(self, cache: ImageCache):
        self.cache = cache
    
    def download_image(self, team_name: str, crest_url: str) -> Optional[Image.Image]:
        """Baixa escudo com cache"""
        if not crest_url:
            logging.warning(f"URL vazia para {team_name}")
            return None
        
        try:
            cached_img = self.cache.get(team_name, crest_url)
            if cached_img:
                logging.info(f"🎨 Escudo de {team_name} obtido do cache")
                return Image.open(io.BytesIO(cached_img)).convert("RGBA")
            
            response = requests.get(crest_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                logging.warning(f"URL não é imagem para {team_name}: {content_type}")
                return None
            
            img_bytes = response.content
            self.cache.set(team_name, crest_url, img_bytes)
            
            img = Image.open(io.BytesIO(img_bytes))
            return img.convert("RGBA")
            
        except requests.exceptions.Timeout:
            logging.error(f"⌛ Timeout ao baixar escudo: {team_name}")
            return None
        except requests.RequestException as e:
            logging.error(f"❌ Erro ao baixar escudo {team_name}: {e}")
            return None
        except Exception as e:
            logging.error(f"❌ Erro geral ao processar escudo {team_name}: {e}")
            return None

# =============================
# CLASSES DE DADOS E ANÁLISE
# =============================

class TimeUtils:
    """Utilitários de tempo"""
    
    @staticmethod
    def formatar_data_iso(data_iso: str) -> Tuple[str, str]:
        """Formata data ISO para fuso horário de Brasília"""
        try:
            if data_iso.endswith('Z'):
                data_iso = data_iso.replace('Z', '+00:00')
            
            data_utc = datetime.fromisoformat(data_iso)
            
            if data_utc.tzinfo is None:
                data_utc = data_utc.replace(tzinfo=timezone.utc)
            
            fuso_brasilia = timezone(timedelta(hours=-3))
            data_brasilia = data_utc.astimezone(fuso_brasilia)
            
            return data_brasilia.strftime("%d/%m/%Y"), data_brasilia.strftime("%H:%M")
        except ValueError as e:
            logging.error(f"Erro ao formatar data {data_iso}: {e}")
            return "Data inválida", "Hora inválida"
    
    @staticmethod
    def iso_to_datetime(data_iso: str) -> datetime:
        """Converte string ISO para datetime com fuso correto"""
        try:
            if data_iso.endswith('Z'):
                data_iso = data_iso.replace('Z', '+00:00')
            
            data_utc = datetime.fromisoformat(data_iso)
            
            if data_utc.tzinfo is None:
                data_utc = data_utc.replace(tzinfo=timezone.utc)
            
            fuso_brasilia = timezone(timedelta(hours=-3))
            return data_utc.astimezone(fuso_brasilia)
            
        except Exception as e:
            logging.error(f"Erro ao converter data {data_iso}: {e}")
            return datetime.now()

class Jogo:
    """Representa um jogo de futebol"""
    
    def __init__(self, data_api: Dict):
        self.id = data_api.get("id")
        self.home_team = data_api.get("homeTeam", {}).get("name", "")
        self.away_team = data_api.get("awayTeam", {}).get("name", "")
        self.utc_date = data_api.get("utcDate", "")
        self.status = data_api.get("status", "SCHEDULED")
        self.competition = data_api.get("competition", {}).get("name", "Desconhecido")
        self.home_crest = data_api.get("homeTeam", {}).get("crest", "")
        self.away_crest = data_api.get("awayTeam", {}).get("crest", "")
        self.score = data_api.get("score", {})
        
        data_formatada, hora_formatada = TimeUtils.formatar_data_iso(self.utc_date)
        self.data_formatada = data_formatada
        self.hora_formatada = hora_formatada
        self.hora_datetime = TimeUtils.iso_to_datetime(self.utc_date)
    
    def is_valid(self) -> bool:
        """Verifica se os dados do jogo são válidos"""
        return all([self.id, self.home_team, self.away_team, self.utc_date])
    
    def get_placar(self) -> Tuple[Optional[int], Optional[int]]:
        """Retorna placar do jogo"""
        full_time = self.score.get("fullTime", {})
        return full_time.get("home"), full_time.get("away")

class AnaliseBase(ABC):
    """Classe base para análises"""
    
    @abstractmethod
    def calcular(self, jogo: Jogo, classificacao: Dict) -> Dict:
        """Calcula análise específica"""
        pass

class AnaliseOverUnder(AnaliseBase):
    """Análise de Over/Under de gols"""
    
    def calcular(self, jogo: Jogo, classificacao: Dict) -> Dict:
        """Calcula tendências completas com análise multivariada"""
        home = jogo.home_team
        away = jogo.away_team
        
        dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1, "wins": 0, "draws": 0, "losses": 0})
        dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1, "wins": 0, "draws": 0, "losses": 0})
        
        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)

        # Estatísticas básicas
        media_home_feitos = dados_home["scored"] / played_home
        media_home_sofridos = dados_home["against"] / played_home
        media_away_feitos = dados_away["scored"] / played_away
        media_away_sofridos = dados_away["against"] / played_away

        # Cálculo de estimativa
        estimativa_home = (media_home_feitos * 0.6 + media_away_sofridos * 0.4)
        estimativa_away = (media_away_feitos * 0.4 + media_home_sofridos * 0.6)
        estimativa_total = estimativa_home + estimativa_away
        
        # Análise de equilíbrio ofensivo/defensivo
        home_balance = media_home_feitos - media_home_sofridos
        away_balance = media_away_feitos - media_away_sofridos
        
        home_defensivo = home_balance < -0.3
        away_defensivo = away_balance < -0.3
        home_ofensivo = home_balance > 0.3
        away_ofensivo = away_balance > 0.3
        
        # Fator casa/fora
        fator_casa = 1.15
        fator_fora = 0.85
        
        estimativa_ajustada_home = estimativa_home * fator_casa
        estimativa_ajustada_away = estimativa_away * fator_fora
        estimativa_total_ajustada = estimativa_ajustada_home + estimativa_ajustada_away
        
        # Lógica de decisão simplificada
        if estimativa_total_ajustada < 1.5:
            tendencia = "UNDER 1.5"
            tipo_aposta = "under"
            probabilidade = max(60, min(85, 100 - (estimativa_total_ajustada * 40)))
        elif estimativa_total_ajustada < 2.0:
            tendencia = "OVER 1.5"
            tipo_aposta = "over"
            probabilidade = max(55, min(80, estimativa_total_ajustada * 30))
        elif estimativa_total_ajustada < 2.6:
            tendencia = "UNDER 2.5"
            tipo_aposta = "under"
            probabilidade = max(60, min(85, 100 - (estimativa_total_ajustada * 25)))
        elif estimativa_total_ajustada < 3.2:
            tendencia = "OVER 2.5"
            tipo_aposta = "over"
            probabilidade = max(55, min(80, estimativa_total_ajustada * 20))
        else:
            tendencia = "OVER 3.5"
            tipo_aposta = "over"
            probabilidade = max(50, min(75, estimativa_total_ajustada * 15))
        
        # Cálculo da confiança
        sinais_concordantes = 0
        total_sinais = 4
        
        if ((tipo_aposta == "under" and estimativa_total_ajustada < 2.5) or 
            (tipo_aposta == "over" and estimativa_total_ajustada > 1.5)):
            sinais_concordantes += 1
        
        if ((tipo_aposta == "under" and (home_defensivo or away_defensivo)) or 
            (tipo_aposta == "over" and (home_ofensivo or away_ofensivo))):
            sinais_concordantes += 1
        
        confianca_base = 50 + (sinais_concordantes / total_sinais * 40)
        
        # Ajustar confiança pela probabilidade
        if probabilidade > 75:
            confianca = min(95, confianca_base * 1.2)
        elif probabilidade > 65:
            confianca = min(90, confianca_base * 1.1)
        else:
            confianca = max(40, confianca_base * 0.9)
        
        return {
            "tendencia": tendencia,
            "estimativa": round(estimativa_total_ajustada, 2),
            "probabilidade": round(probabilidade, 1),
            "confianca": round(confianca, 1),
            "tipo_aposta": tipo_aposta,
            "detalhes": {
                "estimativa_ajustada": round(estimativa_total_ajustada, 2),
                "home_defensivo": home_defensivo,
                "away_defensivo": away_defensivo,
                "home_ofensivo": home_ofensivo,
                "away_ofensivo": away_ofensivo,
                "sinais_concordantes": sinais_concordantes
            }
        }

class AnaliseVitoria(AnaliseBase):
    """Análise de probabilidade de vitória"""
    
    def calcular(self, jogo: Jogo, classificacao: Dict) -> Dict:
        """Calcula probabilidade de vitória, empate e derrota"""
        home = jogo.home_team
        away = jogo.away_team
        
        dados_home = classificacao.get(home, {"wins": 0, "draws": 0, "losses": 0, "played": 1})
        dados_away = classificacao.get(away, {"wins": 0, "draws": 0, "losses": 0, "played": 1})
        
        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)
        
        win_rate_home = dados_home["wins"] / played_home
        win_rate_away = dados_away["wins"] / played_away
        draw_rate_home = dados_home["draws"] / played_home
        draw_rate_away = dados_away["draws"] / played_away
        
        fator_casa = 1.2
        fator_fora = 0.8
        
        prob_home = (win_rate_home * fator_casa + (1 - win_rate_away) * fator_fora) / 2 * 100
        prob_away = (win_rate_away * fator_fora + (1 - win_rate_home) * fator_casa) / 2 * 100
        prob_draw = ((draw_rate_home + draw_rate_away) / 2) * 100
        
        # Normalizar
        total = prob_home + prob_away + prob_draw
        if total > 0:
            prob_home = (prob_home / total) * 100
            prob_away = (prob_away / total) * 100
            prob_draw = (prob_draw / total) * 100
        
        prob_home = max(1, min(99, prob_home))
        prob_away = max(1, min(99, prob_away))
        prob_draw = max(1, min(99, prob_draw))
        
        # Determinar favorito
        if prob_home > prob_away and prob_home > prob_draw:
            favorito = "home"
            confianca_vitoria = prob_home
        elif prob_away > prob_home and prob_away > prob_draw:
            favorito = "away"
            confianca_vitoria = prob_away
        else:
            favorito = "draw"
            confianca_vitoria = prob_draw
        
        return {
            "home_win": round(prob_home, 1),
            "away_win": round(prob_away, 1),
            "draw": round(prob_draw, 1),
            "favorito": favorito,
            "confianca_vitoria": round(confianca_vitoria, 1),
            "tendencia": f"VITÓRIA {favorito.upper()}",
            "tipo_aposta": "vitoria"
        }

class AnaliseGolsHT(AnaliseBase):
    """Análise de gols no primeiro tempo"""
    
    def calcular(self, jogo: Jogo, classificacao: Dict) -> Dict:
        """Calcula probabilidade de gols no primeiro tempo"""
        home = jogo.home_team
        away = jogo.away_team
        
        dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
        dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
        
        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)
        
        media_gols_home = dados_home["scored"] / played_home
        media_gols_away = dados_away["scored"] / played_away
        
        fator_ht = 0.45
        
        estimativa_home_ht = (media_gols_home * fator_ht)
        estimativa_away_ht = (media_gols_away * fator_ht)
        estimativa_total_ht = estimativa_home_ht + estimativa_away_ht
        
        prob_over_05_ht = min(95, max(5, (estimativa_total_ht / 0.5) * 30))
        prob_over_15_ht = min(90, max(5, (estimativa_total_ht / 1.5) * 40))
        
        # Determinar tendência HT
        if estimativa_total_ht > 1.2:
            tendencia_ht = "OVER 1.5 HT"
            confianca_ht = min(95, estimativa_total_ht * 25)
        elif estimativa_total_ht > 0.7:
            tendencia_ht = "OVER 0.5 HT"
            confianca_ht = min(95, estimativa_total_ht * 35)
        else:
            tendencia_ht = "UNDER 0.5 HT"
            confianca_ht = min(95, (1 - estimativa_total_ht) * 40)
        
        return {
            "estimativa_total_ht": round(estimativa_total_ht, 2),
            "tendencia_ht": tendencia_ht,
            "confianca_ht": round(confianca_ht, 1),
            "over_05_ht": round(prob_over_05_ht, 1),
            "over_15_ht": round(prob_over_15_ht, 1),
            "tendencia": tendencia_ht,
            "tipo_aposta": "ht"
        }

class AnaliseCompleta:
    """Gerencia todas as análises disponíveis"""
    
    def __init__(self):
        self.analises = {
            "over_under": AnaliseOverUnder(),
            "vitoria": AnaliseVitoria(),
            "gols_ht": AnaliseGolsHT()
        }
    
    def calcular_todas(self, jogo: Jogo, classificacao: Dict) -> Dict:
        """Calcula todas as análises para um jogo"""
        resultados = {}
        
        for nome, analise in self.analises.items():
            resultados[nome] = analise.calcular(jogo, classificacao)
        
        return resultados

# =============================
# CLASSES DE PERSISTÊNCIA
# =============================

class FileManager:
    """Gerencia operações de arquivo"""
    
    @staticmethod
    def carregar_json(caminho: str) -> Dict:
        """Carrega JSON do arquivo"""
        try:
            if os.path.exists(caminho):
                with open(caminho, "r", encoding='utf-8') as f:
                    dados = json.load(f)
                
                if not dados:
                    return {}
                    
                if caminho in [Config.CACHE_JOGOS, Config.CACHE_CLASSIFICACAO]:
                    agora = datetime.now().timestamp()
                    if isinstance(dados, dict) and '_timestamp' in dados:
                        if agora - dados['_timestamp'] > Config.CACHE_TIMEOUT:
                            return {}
                    else:
                        if agora - os.path.getmtime(caminho) > Config.CACHE_TIMEOUT:
                            return {}
                return dados
        except (json.JSONDecodeError, IOError, Exception) as e:
            logging.error(f"Erro ao carregar {caminho}: {e}")
            st.error(f"Erro ao carregar {caminho}: {e}")
        return {}
    
    @staticmethod
    def salvar_json(caminho: str, dados: Dict):
        """Salva dados em arquivo JSON"""
        try:
            if caminho in [Config.CACHE_JOGOS, Config.CACHE_CLASSIFICACAO]:
                if isinstance(dados, dict):
                    dados['_timestamp'] = datetime.now().timestamp()
            with open(caminho, "w", encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logging.error(f"Erro ao salvar {caminho}: {e}")
            st.error(f"Erro ao salvar {caminho}: {e}")

class DataManager:
    """Gerencia dados do sistema"""
    
    def __init__(self):
        self.file_manager = FileManager()
    
    def carregar_alertas(self) -> Dict:
        return self.file_manager.carregar_json(Config.ALERTAS_PATH)
    
    def salvar_alertas(self, alertas: Dict):
        self.file_manager.salvar_json(Config.ALERTAS_PATH, alertas)
    
    def carregar_alertas_top(self) -> Dict:
        return self.file_manager.carregar_json(Config.ALERTAS_TOP_PATH)
    
    def salvar_alertas_top(self, alertas_top: Dict):
        self.file_manager.salvar_json(Config.ALERTAS_TOP_PATH, alertas_top)
    
    def carregar_historico(self) -> List:
        if os.path.exists(Config.HISTORICO_PATH):
            try:
                with open(Config.HISTORICO_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erro ao carregar histórico: {e}")
                return []
        return []
    
    def salvar_historico(self, historico: List):
        try:
            with open(Config.HISTORICO_PATH, "w", encoding="utf-8") as f:
                json.dump(historico, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erro ao salvar histórico: {e}")
            st.error(f"Erro ao salvar histórico: {e}")
    
    def registrar_no_historico(self, resultado: Dict):
        if not resultado:
            return
        historico = self.carregar_historico()
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
        self.salvar_historico(historico)

# =============================
# CLASSES DE ALERTAS E NOTIFICAÇÕES
# =============================

class Notificador:
    """Gerencia notificações"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
    
    def enviar_telegram(self, msg: str, chat_id: str = Config.TELEGRAM_CHAT_ID, 
                       disable_web_page_preview: bool = True) -> bool:
        """Envia mensagem para Telegram"""
        params = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": str(disable_web_page_preview).lower()
        }
        return self.api_client.get_telegram("sendMessage", params)
    
    def enviar_foto_telegram(self, photo_bytes: io.BytesIO, caption: str = "", 
                            chat_id: str = Config.TELEGRAM_CHAT_ID_ALT2) -> bool:
        """Envia foto para Telegram"""
        try:
            photo_bytes.seek(0)
            files = {"photo": ("elite_master.png", photo_bytes, "image/png")}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            return self.api_client.post_telegram("sendPhoto", data, files)
        except Exception as e:
            logging.error(f"Erro ao enviar foto para Telegram: {e}")
            st.error(f"Erro ao enviar foto para Telegram: {e}")
            return False

class AlertaManager:
    """Gerencia alertas do sistema"""
    
    def __init__(self, data_manager: DataManager, notificador: Notificador):
        self.data_manager = data_manager
        self.notificador = notificador
    
    def adicionar_alerta_top(self, jogo: Dict, data_busca: str):
        """Adiciona um jogo aos alertas TOP salvos"""
        alertas_top = self.data_manager.carregar_alertas_top()
        
        chave = f"{jogo['id']}_{data_busca}"
        
        alertas_top[chave] = {
            "id": jogo["id"],
            "home": jogo["home"],
            "away": jogo["away"],
            "tendencia": jogo["tendencia"],
            "estimativa": jogo["estimativa"],
            "probabilidade": jogo["probabilidade"],
            "confianca": jogo["confianca"],
            "tipo_aposta": jogo["tipo_aposta"],
            "liga": jogo["liga"],
            "hora": jogo["hora"].isoformat() if isinstance(jogo["hora"], datetime) else str(jogo["hora"]),
            "data_busca": data_busca,
            "data_hora_busca": datetime.now().isoformat(),
            "conferido": False,
            "resultado": None,
            "alerta_enviado": False
        }
        
        self.data_manager.salvar_alertas_top(alertas_top)
    
    def enviar_alerta_top_conferidos(self) -> bool:
        """Envia alerta quando todos os jogos do Top N foram conferidos"""
        alertas_top = self.data_manager.carregar_alertas_top()
        if not alertas_top:
            return False
        
        alertas_por_data = {}
        for chave, alerta in alertas_top.items():
            data_busca = alerta.get("data_busca")
            if data_busca not in alertas_por_data:
                alertas_por_data[data_busca] = []
            alertas_por_data[data_busca].append(alerta)
        
        alertas_enviados = []
        
        for data_busca, alertas in alertas_por_data.items():
            todos_conferidos = all(a.get("conferido", False) for a in alertas)
            ja_enviado = any(a.get("alerta_enviado", False) for a in alertas)
            
            if todos_conferidos and not ja_enviado and len(alertas) > 0:
                total_alertas = len(alertas)
                green_count = sum(1 for a in alertas if a.get("resultado") == "GREEN")
                red_count = total_alertas - green_count
                taxa_acerto = (green_count / total_alertas * 100) if total_alertas > 0 else 0
                
                over_alertas = [a for a in alertas if a.get("tipo_aposta") == "over"]
                under_alertas = [a for a in alertas if a.get("tipo_aposta") == "under"]
                
                over_green = sum(1 for a in over_alertas if a.get("resultado") == "GREEN")
                under_green = sum(1 for a in under_alertas if a.get("resultado") == "GREEN")
                
                data_formatada = datetime.strptime(data_busca, "%Y-%m-%d").strftime("%d/%m/%Y")
                
                msg = (
                    f"🏁 <b>RELATÓRIO DE CONFERÊNCIA - TOP {total_alertas} JOGOS ({data_formatada})</b>\n\n"
                    f"<b>📊 RESUMO GERAL:</b>\n"
                    f"<b>• Total de Alertas:</b> {total_alertas}\n"
                    f"<b>• 🟢 GREEN:</b> {green_count} ({taxa_acerto:.1f}%)\n"
                    f"<b>• 🔴 RED:</b> {red_count} ({100 - taxa_acerto:.1f}%)\n\n"
                    f"<b>📈 DESEMPENHO OVER:</b>\n"
                    f"<b>• Alertas:</b> {len(over_alertas)}\n"
                    f"<b>• GREEN:</b> {over_green} ({over_green/max(len(over_alertas),1)*100:.0f}%)\n\n"
                    f"<b>📉 DESEMPENHO UNDER:</b>\n"
                    f"<b>• Alertas:</b> {len(under_alertas)}\n"
                    f"<b>• GREEN:</b> {under_green} ({under_green/max(len(under_alertas),1)*100:.0f}%)\n\n"
                    f"<b>🎯 DETALHES DOS JOGOS:</b>\n"
                )
                
                for i, alerta in enumerate(alertas, 1):
                    resultado_emoji = "🟢" if alerta.get("resultado") == "GREEN" else "🔴"
                    tipo_emoji = "📈" if alerta.get("tipo_aposta") == "over" else "📉"
                    placar = alerta.get("placar", "0x0")
                    tendencia = alerta.get("tendencia", "")
                    confianca = alerta.get("confianca", 0)
                    
                    msg += (
                        f"<b>{i}. {resultado_emoji} {tipo_emoji} {alerta['home']} {placar} {alerta['away']}</b>\n"
                        f"   <i>{tendencia} | Conf: {confianca:.0f}%</i>\n"
                    )
                
                msg += "\n<b>🔥 ELITE MASTER SYSTEM - CONFERÊNCIA AUTOMÁTICA</b>"
                
                if self.notificador.enviar_telegram(msg, Config.TELEGRAM_CHAT_ID_ALT2):
                    for chave_alerta in list(alertas_top.keys()):
                        if alertas_top[chave_alerta].get("data_busca") == data_busca:
                            alertas_top[chave_alerta]["alerta_enviado"] = True
                    
                    self.data_manager.salvar_alertas_top(alertas_top)
                    alertas_enviados.append(data_busca)
                    st.success(f"📤 Relatório de conferência enviado para {data_formatada}!")
        
        return len(alertas_enviados) > 0
    
    def verificar_conjuntos_completos(self) -> List[str]:
        """Verifica se há conjuntos de Top N completos para reportar"""
        alertas_top = self.data_manager.carregar_alertas_top()
        if not alertas_top:
            return []
        
        datas_completas = []
        alertas_por_data = {}
        
        for chave, alerta in alertas_top.items():
            data_busca = alerta.get("data_busca")
            if data_busca not in alertas_por_data:
                alertas_por_data[data_busca] = []
            alertas_por_data[data_busca].append(alerta)
        
        for data_busca, alertas in alertas_por_data.items():
            todos_conferidos = all(a.get("conferido", False) for a in alertas)
            ja_enviado = any(a.get("alerta_enviado", False) for a in alertas)
            
            if todos_conferidos and not ja_enviado:
                datas_completas.append(data_busca)
        
        return datas_completas

# =============================
# CLASSES DE POSTER E IMAGENS
# =============================

class PosterGenerator:
    """Gera posters para os alertas"""
    
    def __init__(self, image_downloader: ImageDownloader):
        self.image_downloader = image_downloader
    
    @staticmethod
    def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
        """Cria fonte com fallback"""
        try:
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
            
            return ImageFont.load_default()
            
        except Exception as e:
            logging.error(f"Erro ao carregar fonte: {e}")
            return ImageFont.load_default()
    
    def gerar_poster_favorito(self, jogos_favorito: List[Dict], config: Dict) -> io.BytesIO:
        """Gera poster específico para alertas de Favorito (Vitória)"""
        LARGURA = 2200
        ALTURA_TOPO = 350
        ALTURA_POR_JOGO = 900
        PADDING = 100
        
        jogos_count = len(jogos_favorito[:3])
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING + 50
        
        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 35))
        draw = ImageDraw.Draw(img)
        
        # Gradiente de fundo
        for i in range(altura_total):
            alpha = i / altura_total
            r = int(10 + 15 * alpha)
            g = int(20 + 10 * alpha)
            b = int(35 + 20 * alpha)
            draw.line([(0, i), (LARGURA, i)], fill=(r, g, b))
        
        # Fontes
        FONTE_TITULO = self.criar_fonte(95)
        FONTE_SUBTITULO = self.criar_fonte(70)
        FONTE_TIMES = self.criar_fonte(80)
        FONTE_VS = self.criar_fonte(80)
        FONTE_INFO = self.criar_fonte(48)
        FONTE_ANALISE = self.criar_fonte(85)
        FONTE_RANKING = self.criar_fonte(80)
        FONTE_ESTATISTICAS = self.criar_fonte(40)
        FONTE_EMOJI = self.criar_fonte(70)
        
        # Cabeçalho
        draw.rectangle([0, 0, LARGURA, ALTURA_TOPO - 50], fill=(20, 35, 60), outline=None)
        
        titulo_text = " ALERTA DE FAVORITO "
        try:
            titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_TITULO)
            titulo_w = titulo_bbox[2] - titulo_bbox[0]
            draw.text(((LARGURA - titulo_w) // 2 + 3, 83), titulo_text, font=FONTE_TITULO, fill=(0, 0, 0))
            draw.text(((LARGURA - titulo_w) // 2, 80), titulo_text, font=FONTE_TITULO, fill=(255, 215, 0))
        except:
            draw.text((LARGURA//2 - 350, 80), titulo_text, font=FONTE_TITULO, fill=(255, 215, 0))
        
        min_conf_vitoria = config.get("min_conf_vitoria", 65)
        filtro_favorito = config.get("filtro_favorito", "Todos")
        
        subtitulo = f" Confiança Mínima: {min_conf_vitoria}% |  Filtro: {filtro_favorito}"
        try:
            sub_bbox = draw.textbbox((0, 0), subtitulo, font=FONTE_SUBTITULO)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text(((LARGURA - sub_w) // 2, 180), subtitulo, font=FONTE_SUBTITULO, fill=(180, 220, 255))
        except:
            draw.text((LARGURA//2 - 300, 180), subtitulo, font=FONTE_SUBTITULO, fill=(180, 220, 255))
        
        y_pos = ALTURA_TOPO
        
        for idx, jogo in enumerate(jogos_favorito[:5]):
            x0, y0 = PADDING, y_pos
            x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
            
            # Cor baseada no favorito
            if jogo.get('favorito') == "home":
                cor_borda = (46, 204, 113)
                cor_fundo = (25, 45, 60)
            elif jogo.get('favorito') == "away":
                cor_borda = (52, 152, 219)
                cor_fundo = (30, 40, 65)
            else:
                cor_borda = (241, 196, 15)
                cor_fundo = (40, 35, 55)
            
            draw.rectangle([x0, y0, x1, y1], fill=cor_fundo, outline=cor_borda, width=8)
            
            # Nome da liga
            liga_text = jogo.get('liga', 'Desconhecido').upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 55), liga_text, 
                         font=FONTE_SUBTITULO, fill=(255, 255, 255))
            except:
                draw.text((LARGURA//2 - 150, y0 + 55), liga_text, font=FONTE_SUBTITULO, fill=(255, 255, 255))
            
            # Área dos times e escudos
            TAMANHO_ESCUDO = 280
            TAMANHO_QUADRADO = 320
            ESPACO_ENTRE_ESCUDOS = 650
            
            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2
            
            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 190
            
            escudo_home = self.image_downloader.download_image(jogo.get('home', ''), jogo.get('escudo_home', ''))
            escudo_away = self.image_downloader.download_image(jogo.get('away', ''), jogo.get('escudo_away', ''))
            
            def desenhar_escudo_estilizado(logo_img, x, y, tamanho_quadrado, tamanho_escudo, team_name, is_favorito=False):
                if is_favorito:
                    draw.rounded_rectangle([x-5, y-5, x + tamanho_quadrado + 5, y + tamanho_quadrado + 5],
                                         radius=15, fill=cor_borda, outline=None)
                    draw.rounded_rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                                         radius=10, fill=(255, 255, 255), outline=(230, 230, 230), width=4)
                else:
                    draw.rounded_rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                                         radius=10, fill=(240, 240, 240), outline=(200, 200, 200), width=3)
                
                if logo_img is None:
                    inicial = team_name[:1].upper() if team_name else "T"
                    draw.rounded_rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                                         radius=10, fill=(60, 70, 90))
                    try:
                        bbox = draw.textbbox((0, 0), inicial, font=FONTE_TIMES)
                        w = bbox[2] - bbox[0]
                        h = bbox[3] - bbox[1]
                        draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), 
                                 inicial, font=FONTE_TIMES, fill=(255, 255, 255))
                    except:
                        pass
                    return
                
                try:
                    logo_img = logo_img.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)
                    pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
                    pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2
                    img.paste(logo_img, (pos_x, pos_y), logo_img)
                except Exception as e:
                    logging.error(f"Erro ao desenhar escudo favorito: {e}")
            
            favorito = jogo.get('favorito', '')
            desenhar_escudo_estilizado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, 
                                     jogo.get('home', ''), favorito == "home")
            desenhar_escudo_estilizado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, 
                                     jogo.get('away', ''), favorito == "away")
            
            y_pos += ALTURA_POR_JOGO
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True, quality=95)
        buffer.seek(0)
        
        st.success(f"✅ Poster Favorito gerado com {jogos_count} jogos!")
        return buffer

# =============================
# SISTEMA PRINCIPAL
# =============================

class SistemaAlertas:
    """Sistema principal de alertas"""
    
    def __init__(self):
        # Configurações
        LoggingManager.setup()
        
        # Inicializar componentes
        self.api_client = APIClient()
        self.rate_limiter = RateLimiter()
        self.monitor = APIMonitor()
        
        # Caches
        self.jogos_cache = Cache("jogos")
        self.classificacao_cache = Cache("classificacao")
        self.match_cache = Cache("match_details")
        self.image_cache = ImageCache()
        
        # Gerenciadores
        self.image_downloader = ImageDownloader(self.image_cache)
        self.data_manager = DataManager()
        self.notificador = Notificador(self.api_client)
        self.alerta_manager = AlertaManager(self.data_manager, self.notificador)
        self.poster_generator = PosterGenerator(self.image_downloader)
        
        # Análises
        self.analise_completa = AnaliseCompleta()
        
        # Estado do sistema
        self.jogos_hoje = []
    
    def obter_jogos(self, liga_id: str, data: str) -> List[Dict]:
        """Obtém jogos com cache"""
        key = f"{liga_id}_{data}"
        
        cached = self.jogos_cache.get(key)
        if cached:
            logging.info(f"⚽ Jogos {key} obtidos do cache")
            return cached
        
        url = f"{Config.BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        data_api = self.api_client.get_with_retry(url)
        jogos = data_api.get("matches", []) if data_api else []
        self.jogos_cache.set(key, jogos)
        return jogos
    
    def obter_classificacao(self, liga_id: str) -> Dict:
        """Obtém classificação com cache"""
        cached = self.classificacao_cache.get(liga_id)
        if cached:
            logging.info(f"📊 Classificação da liga {liga_id} obtida do cache")
            return cached
        
        url = f"{Config.BASE_URL_FD}/competitions/{liga_id}/standings"
        data = self.api_client.get_with_retry(url)
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
        self.classificacao_cache.set(liga_id, standings)
        return standings
    
    def processar_jogos(self, data_selecionada, ligas_selecionadas, todas_ligas, 
                       top_n, min_conf, max_conf, estilo_poster, alerta_individual, 
                       alerta_poster, alerta_top_jogos, formato_top_jogos, 
                       tipo_filtro, tipo_analise, config_analise):
        """Processa jogos e gera alertas"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        if todas_ligas:
            ligas_busca = list(Config.LIGA_DICT.values())
            st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
        else:
            ligas_busca = [Config.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
            st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas")
        
        top_jogos = []
        progress_bar = st.progress(0)
        total_ligas = len(ligas_busca)
        
        # Pré-busca classificações
        classificacoes = {}
        for liga_id in ligas_busca:
            classificacoes[liga_id] = self.obter_classificacao(liga_id)
        
        for i, liga_id in enumerate(ligas_busca):
            classificacao = classificacoes[liga_id]
            jogos_api = self.obter_jogos(liga_id, hoje)
            
            for match in jogos_api:
                jogo = Jogo(match)
                if not jogo.is_valid():
                    continue
                
                # Calcular análises
                analises = self.analise_completa.calcular_todas(jogo, classificacao)
                
                # Verificar se deve enviar alerta
                if tipo_analise == "Over/Under de Gols":
                    analise_principal = analises["over_under"]
                    if min_conf <= analise_principal["confianca"] <= max_conf:
                        if tipo_filtro == "Todos" or \
                           (tipo_filtro == "Apenas Over" and analise_principal["tipo_aposta"] == "over") or \
                           (tipo_filtro == "Apenas Under" and analise_principal["tipo_aposta"] == "under"):
                            
                            # Preparar dados do jogo
                            jogo_data = {
                                "id": jogo.id,
                                "home": jogo.home_team,
                                "away": jogo.away_team,
                                "tendencia": analise_principal["tendencia"],
                                "estimativa": analise_principal["estimativa"],
                                "probabilidade": analise_principal["probabilidade"],
                                "confianca": analise_principal["confianca"],
                                "tipo_aposta": analise_principal["tipo_aposta"],
                                "liga": jogo.competition,
                                "hora": jogo.hora_datetime,
                                "status": jogo.status,
                                "escudo_home": jogo.home_crest,
                                "escudo_away": jogo.away_crest,
                                "detalhes": {
                                    "over_under": analise_principal,
                                    "vitoria": analises["vitoria"],
                                    "gols_ht": analises["gols_ht"]
                                }
                            }
                            
                            top_jogos.append(jogo_data)
            
            progress_bar.progress((i + 1) / total_ligas)
        
        # Filtrar por tipo de análise
        jogos_filtrados = self.filtrar_por_tipo_analise(top_jogos, tipo_analise, config_analise)
        
        if jogos_filtrados:
            # Enviar top jogos
            if tipo_analise == "Over/Under de Gols":
                self.enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, 
                                    min_conf, max_conf, formato_top_jogos, data_busca=hoje)
            
            # Enviar poster
            if alerta_poster:
                if tipo_analise == "Over/Under de Gols":
                    if estilo_poster == "West Ham (Novo)":
                        self.enviar_alerta_westham_style(jogos_filtrados, min_conf, max_conf)
                    else:
                        self.enviar_alerta_conf_criar_poster(jogos_filtrados, min_conf, max_conf)
                else:
                    try:
                        poster = self.gerar_poster_por_tipo(jogos_filtrados, tipo_analise, config_analise)
                        caption = self.gerar_caption_poster(jogos_filtrados, tipo_analise, config_analise)
                        if self.notificador.enviar_foto_telegram(poster, caption=caption):
                            st.success(f"✅ Poster de {tipo_analise} enviado!")
                    except Exception as e:
                        logging.error(f"Erro ao gerar poster: {e}")
                        st.error(f"❌ Erro ao gerar poster: {e}")
        
        return jogos_filtrados
    
    def filtrar_por_tipo_analise(self, jogos: List[Dict], tipo_analise: str, config: Dict) -> List[Dict]:
        """Filtra jogos baseado no tipo de análise"""
        if tipo_analise == "Over/Under de Gols":
            min_conf = config.get("min_conf", 70)
            max_conf = config.get("max_conf", 95)
            tipo_filtro = config.get("tipo_filtro", "Todos")
            
            jogos_filtrados = [
                j for j in jogos
                if min_conf <= j["confianca"] <= max_conf and 
                j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
            ]
            
            if tipo_filtro == "Apenas Over":
                jogos_filtrados = [j for j in jogos_filtrados if j["tipo_aposta"] == "over"]
            elif tipo_filtro == "Apenas Under":
                jogos_filtrados = [j for j in jogos_filtrados if j["tipo_aposta"] == "under"]
        
        elif tipo_analise == "Favorito (Vitória)":
            min_conf_vitoria = config.get("min_conf_vitoria", 65)
            filtro_favorito = config.get("filtro_favorito", "Todos")
            
            jogos_filtrados = []
            for jogo in jogos:
                if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
                    vitoria_data = jogo['detalhes']['vitoria']
                    confianca_vitoria = vitoria_data['confianca_vitoria']
                    favorito = vitoria_data['favorito']
                    
                    if confianca_vitoria >= min_conf_vitoria:
                        if (filtro_favorito == "Todos" or
                            (filtro_favorito == "Casa" and favorito == "home") or
                            (filtro_favorito == "Fora" and favorito == "away") or
                            (filtro_favorito == "Empate" and favorito == "draw")):
                            
                            jogo['tipo_alerta'] = 'favorito'
                            jogo['confianca_vitoria'] = confianca_vitoria
                            jogo['favorito'] = favorito
                            jogos_filtrados.append(jogo)
        
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            min_conf_ht = config.get("min_conf_ht", 60)
            tipo_ht = config.get("tipo_ht", "OVER 0.5 HT")
            
            jogos_filtrados = []
            for jogo in jogos:
                if 'detalhes' in jogo and 'gols_ht' in jogo['detalhes']:
                    ht_data = jogo['detalhes']['gols_ht']
                    confianca_ht = ht_data['confianca_ht']
                    tendencia_ht = ht_data['tendencia_ht']
                    
                    if (confianca_ht >= min_conf_ht and 
                        (tipo_ht == "Todos" or tendencia_ht == tipo_ht)):
                        
                        jogo['tipo_alerta'] = 'ht'
                        jogo['confianca_ht'] = confianca_ht
                        jogo['tendencia_ht'] = tendencia_ht
                        jogos_filtrados.append(jogo)
        
        return jogos_filtrados
    
    def enviar_top_jogos(self, jogos: List[Dict], top_n: int, alerta_top_jogos: bool, 
                        min_conf: int, max_conf: int, formato_top_jogos: str, data_busca: str):
        """Envia os top jogos para o Telegram"""
        if not alerta_top_jogos:
            return
        
        jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
        jogos_filtrados = [j for j in jogos_filtrados if min_conf <= j["confianca"] <= max_conf]
        
        if not jogos_filtrados:
            st.warning(f"⚠️ Nenhum jogo elegível para o Top Jogos")
            return
        
        top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
        
        for jogo in top_jogos_sorted:
            self.alerta_manager.adicionar_alerta_top(jogo, data_busca)
        
        if formato_top_jogos in ["Texto", "Ambos"]:
            msg = self.gerar_mensagem_top_jogos(top_jogos_sorted, min_conf, max_conf)
            if self.notificador.enviar_telegram(msg, Config.TELEGRAM_CHAT_ID_ALT2):
                st.success(f"📝 Texto dos TOP {top_n} jogos enviado!")
    
    def gerar_mensagem_top_jogos(self, jogos: List[Dict], min_conf: int, max_conf: int) -> str:
        """Gera mensagem para top jogos"""
        over_jogos = [j for j in jogos if j.get('tipo_aposta') == "over"]
        under_jogos = [j for j in jogos if j.get('tipo_aposta') == "under"]
        
        msg = f"📢 TOP {len(jogos)} Jogos do Dia (confiança: {min_conf}%-{max_conf}%)\n\n"
        
        if over_jogos:
            msg += f"📈 <b>OVER ({len(over_jogos)} jogos):</b>\n"
            for j in over_jogos:
                hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                msg += f"🏟️ {j['home']} vs {j['away']}\n🕒 {hora_format} BRT | {j['liga']}\n"
                msg += f"📈 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}%\n\n"
        
        if under_jogos:
            msg += f"📉 <b>UNDER ({len(under_jogos)} jogos):</b>\n"
            for j in under_jogos:
                hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                msg += f"🏟️ {j['home']} vs {j['away']}\n🕒 {hora_format} BRT | {j['liga']}\n"
                msg += f"📉 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}%\n\n"
        
        return msg
    
    def gerar_poster_por_tipo(self, jogos: List[Dict], tipo_analise: str, config: Dict) -> io.BytesIO:
        """Gera poster específico para cada tipo de análise"""
        if tipo_analise == "Favorito (Vitória)":
            return self.poster_generator.gerar_poster_favorito(jogos, config)
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            return self.gerar_poster_gols_ht(jogos, config)
        else:
            return self.gerar_poster_westham_style(jogos, config)
    
    def gerar_caption_poster(self, jogos: List[Dict], tipo_analise: str, config: Dict) -> str:
        """Gera caption para poster"""
        if tipo_analise == "Favorito (Vitória)":
            return f"<b>🎯 ALERTA DE FAVORITO</b>\n<b>📋 Total: {len(jogos)} jogos</b>"
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            return f"<b>⏰ ALERTA DE GOLS HT</b>\n<b>📋 Total: {len(jogos)} jogos</b>"
        else:
            return f"<b>⚽ ALERTA OVER/UNDER</b>\n<b>📋 Total: {len(jogos)} jogos</b>"

# =============================
# INTERFACE STREAMLIT
# =============================

def main():
    """Função principal da interface"""
    st.set_page_config(page_title="⚽ Alerta de Gols Over/Under", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos Over/Under")
    
    # Inicializar sistema
    sistema = SistemaAlertas()
    
    # Sidebar
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        
        # Tipo de análise
        st.subheader("🎯 Tipo de Análise Principal")
        tipo_analise = st.selectbox(
            "Selecione o tipo de alerta:",
            ["Over/Under de Gols", "Favorito (Vitória)", "Gols HT (Primeiro Tempo)"],
            index=0
        )
        
        config_analise = {}
        
        if tipo_analise == "Over/Under de Gols":
            tipo_filtro = st.selectbox("🔍 Filtrar por Tipo", ["Todos", "Apenas Over", "Apenas Under"], index=0)
            min_conf = st.slider("Confiança Mínima (%)", 10, 95, 70, 1)
            max_conf = st.slider("Confiança Máxima (%)", min_conf, 95, 95, 1)
            config_analise = {"tipo_filtro": tipo_filtro, "min_conf": min_conf, "max_conf": max_conf}
            
        elif tipo_analise == "Favorito (Vitória)":
            min_conf_vitoria = st.slider("Confiança Mínima Vitória (%)", 50, 95, 65, 1)
            filtro_favorito = st.selectbox("Filtrar Favorito:", ["Todos", "Casa", "Fora", "Empate"], index=0)
            config_analise = {"min_conf_vitoria": min_conf_vitoria, "filtro_favorito": filtro_favorito}
            
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            min_conf_ht = st.slider("Confiança Mínima HT (%)", 50, 95, 60, 1)
            tipo_ht = st.selectbox("Tipo de HT:", ["OVER 0.5 HT", "OVER 1.5 HT", "UNDER 0.5 HT", "UNDER 1.5 HT"], index=0)
            config_analise = {"min_conf_ht": min_conf_ht, "tipo_ht": tipo_ht}
        
        # Tipos de envio
        st.subheader("📨 Tipos de Envio")
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True)
        alerta_poster = st.checkbox("📊 Alertas com Poster", value=True)
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True)
        alerta_conferencia_auto = st.checkbox("🤖 Alerta Auto Conferência", value=True)
        alerta_resultados = st.checkbox("🏁 Resultados Finais", value=True)
        
        # Formato do Top Jogos
        formato_top_jogos = st.selectbox("📋 Formato do Top Jogos", ["Ambos", "Texto", "Poster"], index=0)
        
        st.markdown("----")
        st.header("Configurações Gerais")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        estilo_poster = st.selectbox("🎨 Estilo do Poster", ["West Ham (Novo)", "Elite Master (Original)"], index=0)
        
        st.info(f"Tipo de Análise: {tipo_analise}")
    
    # Controles principais
    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)
    
    # Seleção de ligas
    ligas_selecionadas = []
    if not todas_ligas:
        ligas_selecionadas = st.multiselect(
            "📌 Selecionar ligas:",
            options=list(Config.LIGA_DICT.keys()),
            default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"]
        )
    
    # Botão principal
    if st.button("🔍 Buscar Partidas", type="primary"):
        if not todas_ligas and not ligas_selecionadas:
            st.error("❌ Selecione pelo menos uma liga")
        else:
            tipo_filtro_passar = tipo_filtro if tipo_analise == "Over/Under de Gols" else "Todos"
            sistema.processar_jogos(
                data_selecionada, ligas_selecionadas, todas_ligas, top_n,
                config_analise.get("min_conf", 70), 
                config_analise.get("max_conf", 95), 
                estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                formato_top_jogos, tipo_filtro_passar, tipo_analise, config_analise
            )
    
    # Ações secundárias
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🏆 Conferir Alertas TOP", type="primary"):
            # Implementar conferência de alertas TOP
            st.info("Conferindo alertas TOP...")
            if alerta_conferencia_auto:
                sistema.alerta_manager.enviar_alerta_top_conferidos()
    
    with col2:
        if st.button("🔍 Verificar Conjuntos Completos"):
            datas = sistema.alerta_manager.verificar_conjuntos_completos()
            if datas:
                st.success(f"✅ {len(datas)} conjuntos completos encontrados")
    
    with col3:
        if st.button("📊 Calcular Desempenho"):
            # Implementar cálculo de desempenho
            st.info("Calculando desempenho...")
    
    with col4:
        if st.button("🧹 Limpar Caches"):
            sistema.jogos_cache.clear()
            sistema.classificacao_cache.clear()
            sistema.match_cache.clear()
            sistema.image_cache.clear()
            st.success("✅ Caches limpos!")
    
    # Monitoramento
    st.markdown("---")
    st.subheader("📊 Monitoramento")
    
    stats = sistema.monitor.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Requests", stats["total_requests"])
    with col2:
        st.metric("Taxa de Sucesso", f"{stats['success_rate']}%")
    with col3:
        st.metric("Requests/min", stats["requests_per_minute"])
    with col4:
        st.metric("Rate Limit Hits", stats["rate_limit_hits"])

if __name__ == "__main__":
    main()
