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
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging
import math

# =============================
# CONFIGURAÇÃO DA API THESPORTSDB
# =============================

class ConfigManager:
    """Gerencia configurações e constantes do sistema"""
    
    # ============= NOVA API THESPORTSDB =============
    API_KEY = os.getenv("SPORTSDB_API_KEY", "123")  # Chave gratuita padrão
    BASE_URL_SPORTSDB = "https://www.thesportsdb.com/api/v1/json"
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","8351165117:AAFmqb3NrPsmT86_8C360eYzK71Qda1ah_4")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
    TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
    HEADERS = {}  # TheSportsDB não requer headers de autenticação
    
    # Constantes
    ALERTAS_PATH = "alertas.json"
    ALERTAS_FAVORITOS_PATH = "alertas_favoritos.json"
    ALERTAS_GOLS_HT_PATH = "alertas_gols_ht.json"
    ALERTAS_AMBAS_MARCAM_PATH = "alertas_ambas_marcam.json"
    RESULTADOS_PATH = "resultados.json"
    RESULTADOS_FAVORITOS_PATH = "resultados_favoritos.json"
    RESULTADOS_GOLS_HT_PATH = "resultados_gols_ht.json"
    RESULTADOS_AMBAS_MARCAM_PATH = "resultados_ambas_marcam.json"
    CACHE_JOGOS = "cache_jogos.json"
    CACHE_CLASSIFICACAO = "cache_classificacao.json"
    CACHE_TIMEOUT = 3600
    HISTORICO_PATH = "historico_conferencias.json"
    ALERTAS_TOP_PATH = "alertas_top.json"
    RESULTADOS_TOP_PATH = "resultados_top.json"
    
    # ============= DICIONÁRIO DE LIGAS (TheSportsDB) =============
    LIGA_DICT = {
        # Europa - Principais Ligas
        "Premier League (Inglaterra)": "4328",
        "La Liga (Espanha)": "4335",
        "Serie A (Itália)": "4332",
        "Bundesliga (Alemanha)": "4331",
        "Ligue 1 (França)": "4334",
        "UEFA Champions League": "4480",
        "UEFA Europa League": "4481",
        "Primeira Liga (Portugal)": "4340",
        "Eredivisie (Holanda)": "4333",
        "Championship (Inglaterra)": "4336",
        "Scottish Premiership": "4341",
        "Belgian Pro League": "4342",
        "Turkish Super Lig": "4343",
        "Russian Premier League": "4337",
        
        # América do Sul
        "Campeonato Brasileiro Série A": "4425",
        "Campeonato Brasileiro Série B": "4426",
        "Copa do Brasil": "4456",
        "Copa do Nordeste": "4805",
        "Campeonato Paulista": "4427",
        "Campeonato Carioca": "4428",
        "Campeonato Mineiro": "4429",
        "Campeonato Gaúcho": "4430",
        "Argentine Primera Division": "4345",
        "Uruguayan Primera Division": "4346",
        "Chilean Primera Division": "4347",
        "Colombian Primera A": "4348",
        "Copa Libertadores": "4482",
        "Copa Sudamericana": "4483",
        
        # América do Norte
        "MLS (EUA)": "4344",
        "Liga MX (México)": "4354",
        "Canadian Premier League": "4485",
        "CONCACAF Champions League": "4487",
        
        # Outras Ligas Relevantes
        "J1 League (Japão)": "4355",
        "K League 1 (Coreia)": "4356",
        "Saudi Pro League": "4359",
    }
    
    # IDs das ligas que possuem tabela de classificação (featured leagues)
    FEATURED_LEAGUES = ["4328", "4335", "4332", "4331", "4334", "4480", "4344", "4425"]
    
    # Configurações de cache
    CACHE_CONFIG = {
        "jogos": {"ttl": 3600, "max_size": 100},
        "classificacao": {"ttl": 86400, "max_size": 50},
        "match_details": {"ttl": 1800, "max_size": 200},
        "teams": {"ttl": 86400, "max_size": 100},
    }
    
    @classmethod
    def get_liga_id(cls, liga_nome):
        return cls.LIGA_DICT.get(liga_nome)
    
    @classmethod
    def is_featured_league(cls, league_id):
        return league_id in cls.FEATURED_LEAGUES


# =============================
# CLASSE RATE LIMITER
# =============================

class RateLimiter:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance
    
    def _init(self):
        self.requests = deque(maxlen=20)
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 1.0
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            while self.requests and now - self.requests[0] > 60:
                self.requests.popleft()
            
            if len(self.requests) >= 20:
                wait_time = 60 - (now - self.requests[0])
                if wait_time > 0:
                    time.sleep(wait_time + 0.1)
                    now = time.time()
            
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_interval:
                time.sleep(self.min_interval - time_since_last)
            
            self.requests.append(now)
            self.last_request_time = now


# =============================
# CLASSE SMART CACHE
# =============================

class SmartCache:
    def __init__(self, cache_type: str):
        self.cache = {}
        self.timestamps = {}
        self.config = ConfigManager.CACHE_CONFIG.get(cache_type, {"ttl": 3600, "max_size": 100})
        self.lock = threading.Lock()
        
    def get(self, key: str):
        with self.lock:
            if key not in self.cache:
                return None
            if time.time() - self.timestamps.get(key, 0) > self.config["ttl"]:
                del self.cache[key]
                del self.timestamps[key]
                return None
            return self.cache[key]
    
    def set(self, key: str, value):
        with self.lock:
            if len(self.cache) >= self.config["max_size"]:
                oldest_key = min(self.timestamps.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()


# =============================
# CLASSE API MONITOR
# =============================

class APIMonitor:
    def __init__(self):
        self.total_requests = 0
        self.failed_requests = 0
        self.rate_limit_hits = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def log_request(self, success: bool, was_rate_limited: bool = False):
        with self.lock:
            self.total_requests += 1
            if not success:
                self.failed_requests += 1
            if was_rate_limited:
                self.rate_limit_hits += 1
    
    def get_stats(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            requests_per_min = (self.total_requests / elapsed * 60) if elapsed > 0 else 0
            return {
                "total_requests": self.total_requests,
                "failed_requests": self.failed_requests,
                "rate_limit_hits": self.rate_limit_hits,
                "requests_per_minute": round(requests_per_min, 2),
                "success_rate": round((1 - self.failed_requests / max(self.total_requests, 1)) * 100, 1),
            }


# =============================
# CLASSE IMAGE CACHE
# =============================

class ImageCache:
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.max_size = 200
        self.ttl = 86400 * 7
        self.lock = threading.Lock()
        self.cache_dir = "escudos_cache"
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
    
    def get(self, team_name: str, crest_url: str) -> bytes | None:
        if not crest_url:
            return None
            
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
                if time.time() - os.path.getmtime(file_path) <= self.ttl:
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
        if not crest_url or not img_bytes:
            return
            
        key = self._generate_key(team_name, crest_url)
        
        with self.lock:
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.timestamps.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            
            self.cache[key] = img_bytes
            self.timestamps[key] = time.time()
            
            try:
                file_path = os.path.join(self.cache_dir, f"{key}.png")
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
            except Exception:
                pass
    
    def _generate_key(self, team_name: str, crest_url: str) -> str:
        import hashlib
        combined = f"{team_name}_{crest_url}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()


# =============================
# CLASSE SPORTSDB CLIENT
# =============================

class SportsDBClient:
    def __init__(self):
        self.api_key = ConfigManager.API_KEY
        self.base_url = f"{ConfigManager.BASE_URL_SPORTSDB}/{self.api_key}"
        self.rate_limiter = None
    
    def set_rate_limiter(self, rate_limiter):
        self.rate_limiter = rate_limiter
    
    def _make_request(self, url: str, timeout: int = 15) -> dict:
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()
        
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Erro na requisição {url}: {e}")
            return {}
    
    def get_events_by_date(self, date: str, sport: str = "Soccer") -> list:
        url = f"{self.base_url}/eventsday.php?d={date}&s={sport}"
        data = self._make_request(url)
        return data.get("events", [])
    
    def lookup_event(self, event_id: str) -> dict:
        url = f"{self.base_url}/lookupevent.php?id={event_id}"
        data = self._make_request(url)
        events = data.get("events", [])
        return events[0] if events else {}
    
    def lookup_league_table(self, league_id: str, season: str = None) -> list:
        url = f"{self.base_url}/lookuptable.php?l={league_id}"
        if season:
            url += f"&s={season}"
        data = self._make_request(url)
        return data.get("table", [])
    
    def lookup_league(self, league_id: str) -> dict:
        url = f"{self.base_url}/lookupleague.php?id={league_id}"
        data = self._make_request(url)
        leagues = data.get("leagues", [])
        return leagues[0] if leagues else {}
    
    def get_league_next_events(self, league_id: str) -> list:
        url = f"{self.base_url}/eventsnextleague.php?id={league_id}"
        data = self._make_request(url)
        return data.get("events", [])
    
    def get_league_past_events(self, league_id: str) -> list:
        url = f"{self.base_url}/eventspastleague.php?id={league_id}"
        data = self._make_request(url)
        return data.get("events", [])
    
    def search_teams(self, team_name: str) -> list:
        url = f"{self.base_url}/searchteams.php?t={team_name.replace(' ', '_')}"
        data = self._make_request(url)
        return data.get("teams", [])
    
    def get_team_players(self, team_id: str) -> list:
        url = f"{self.base_url}/lookup_all_players.php?id={team_id}"
        data = self._make_request(url)
        return data.get("player", [])
    
    def get_all_leagues(self) -> list:
        url = f"{self.base_url}/all_leagues.php"
        data = self._make_request(url)
        return data.get("leagues", [])
    
    def get_leagues_by_country(self, country: str, sport: str = "Soccer") -> list:
        url = f"{self.base_url}/search_all_leagues.php?c={country}&s={sport}"
        data = self._make_request(url)
        return data.get("countries", [])


# =============================
# CLASSE DATA STORAGE
# =============================

class DataStorage:
    @staticmethod
    def _serialize_for_json(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: DataStorage._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DataStorage._serialize_for_json(item) for item in obj]
        return obj
    
    @staticmethod
    def carregar_json(caminho: str) -> dict:
        try:
            if os.path.exists(caminho):
                with open(caminho, "r", encoding='utf-8') as f:
                    dados = json.load(f)
                if not dados:
                    return {}
                if caminho in [ConfigManager.CACHE_JOGOS, ConfigManager.CACHE_CLASSIFICACAO]:
                    agora = datetime.now().timestamp()
                    if isinstance(dados, dict) and '_timestamp' in dados:
                        if agora - dados['_timestamp'] > ConfigManager.CACHE_TIMEOUT:
                            return {}
                return dados
        except Exception:
            pass
        return {}
    
    @staticmethod
    def salvar_json(caminho: str, dados: dict):
        try:
            dados_serializados = DataStorage._serialize_for_json(dados)
            if caminho in [ConfigManager.CACHE_JOGOS, ConfigManager.CACHE_CLASSIFICACAO]:
                if isinstance(dados_serializados, dict):
                    dados_serializados['_timestamp'] = datetime.now().timestamp()
            with open(caminho, "w", encoding='utf-8') as f:
                json.dump(dados_serializados, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    @staticmethod
    def carregar_alertas() -> dict:
        return DataStorage.carregar_json(ConfigManager.ALERTAS_PATH)
    
    @staticmethod
    def salvar_alertas(alertas: dict):
        DataStorage.salvar_json(ConfigManager.ALERTAS_PATH, alertas)
    
    @staticmethod
    def carregar_alertas_favoritos() -> dict:
        return DataStorage.carregar_json(ConfigManager.ALERTAS_FAVORITOS_PATH)
    
    @staticmethod
    def salvar_alertas_favoritos(alertas: dict):
        DataStorage.salvar_json(ConfigManager.ALERTAS_FAVORITOS_PATH, alertas)
    
    @staticmethod
    def carregar_alertas_gols_ht() -> dict:
        return DataStorage.carregar_json(ConfigManager.ALERTAS_GOLS_HT_PATH)
    
    @staticmethod
    def salvar_alertas_gols_ht(alertas: dict):
        DataStorage.salvar_json(ConfigManager.ALERTAS_GOLS_HT_PATH, alertas)
    
    @staticmethod
    def carregar_alertas_ambas_marcam() -> dict:
        return DataStorage.carregar_json(ConfigManager.ALERTAS_AMBAS_MARCAM_PATH)
    
    @staticmethod
    def salvar_alertas_ambas_marcam(alertas: dict):
        DataStorage.salvar_json(ConfigManager.ALERTAS_AMBAS_MARCAM_PATH, alertas)
    
    @staticmethod
    def carregar_resultados() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_PATH)
    
    @staticmethod
    def salvar_resultados(resultados: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_PATH, resultados)
    
    @staticmethod
    def carregar_resultados_favoritos() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_FAVORITOS_PATH)
    
    @staticmethod
    def salvar_resultados_favoritos(resultados: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_FAVORITOS_PATH, resultados)
    
    @staticmethod
    def carregar_resultados_gols_ht() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_GOLS_HT_PATH)
    
    @staticmethod
    def salvar_resultados_gols_ht(resultados: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_GOLS_HT_PATH, resultados)
    
    @staticmethod
    def carregar_resultados_ambas_marcam() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_AMBAS_MARCAM_PATH)
    
    @staticmethod
    def salvar_resultados_ambas_marcam(resultados: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_AMBAS_MARCAM_PATH, resultados)
    
    @staticmethod
    def carregar_alertas_top() -> dict:
        return DataStorage.carregar_json(ConfigManager.ALERTAS_TOP_PATH)
    
    @staticmethod
    def salvar_alertas_top(alertas_top: dict):
        DataStorage.salvar_json(ConfigManager.ALERTAS_TOP_PATH, alertas_top)
    
    @staticmethod
    def carregar_resultados_top() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_TOP_PATH)
    
    @staticmethod
    def salvar_resultados_top(resultados_top: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_TOP_PATH, resultados_top)


# =============================
# CLASSE APICLIENT
# =============================

class APIClient:
    def __init__(self, rate_limiter: RateLimiter, api_monitor: APIMonitor):
        self.rate_limiter = rate_limiter
        self.api_monitor = api_monitor
        self.config = ConfigManager()
        self.sportsdb = SportsDBClient()
        self.sportsdb.set_rate_limiter(rate_limiter)
        
        self.jogos_cache = SmartCache("jogos")
        self.classificacao_cache = SmartCache("classificacao")
        self.match_cache = SmartCache("match_details")
        self.image_cache = ImageCache()
        self.team_ids_cache = {}
    
    def obter_classificacao(self, liga_id: str) -> dict:
        cached = self.classificacao_cache.get(liga_id)
        if cached:
            return cached
        
        if not ConfigManager.is_featured_league(liga_id):
            return {}
        
        table_data = self.sportsdb.lookup_league_table(liga_id)
        if not table_data:
            return {}
        
        standings = {}
        for team in table_data:
            name = team.get("strTeam", "")
            if name:
                standings[name] = {
                    "scored": int(team.get("intGoalsFor", 0) or 0),
                    "against": int(team.get("intGoalsAgainst", 0) or 0),
                    "played": int(team.get("intPlayed", 0) or 0),
                    "wins": int(team.get("intWin", 0) or 0),
                    "draws": int(team.get("intDraw", 0) or 0),
                    "losses": int(team.get("intLoss", 0) or 0)
                }
                team_id = team.get("idTeam", "")
                if team_id:
                    self.team_ids_cache[name] = team_id
        
        self.classificacao_cache.set(liga_id, standings)
        return standings
    
    def obter_jogos(self, liga_id: str, data: str) -> list:
        key = f"{liga_id}_{data}"
        cached = self.jogos_cache.get(key)
        if cached:
            return cached
        
        events = self.sportsdb.get_events_by_date(data, "Soccer")
        
        league_info = self.sportsdb.lookup_league(liga_id)
        league_name = league_info.get("strLeague", "")
        
        filtered_events = []
        for event in events:
            event_league = event.get("strLeague", "")
            if event_league == league_name or liga_id in str(event.get("idLeague", "")):
                filtered_events.append(event)
        
        self.jogos_cache.set(key, filtered_events)
        return filtered_events
    
    def obter_detalhes_jogo(self, fixture_id: str) -> dict | None:
        cached = self.match_cache.get(fixture_id)
        if cached:
            return cached
        
        event = self.sportsdb.lookup_event(fixture_id)
        if event:
            self.match_cache.set(fixture_id, event)
        return event
    
    def baixar_escudo_time(self, team_name: str, crest_url: str) -> bytes | None:
        if not crest_url:
            return None
        
        url = crest_url
        if crest_url.startswith("/"):
            url = f"https://www.thesportsdb.com{crest_url}"
        
        try:
            cached = self.image_cache.get(team_name, url)
            if cached:
                return cached
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            img_bytes = response.content
            self.image_cache.set(team_name, url, img_bytes)
            return img_bytes
            
        except Exception as e:
            logging.error(f"Erro ao baixar escudo de {team_name}: {e}")
            return None
    
    @staticmethod
    def validar_dados_jogo(match: dict) -> bool:
        required_fields = ['idEvent', 'strHomeTeam', 'strAwayTeam', 'dateEvent']
        return all(field in match for field in required_fields)
    
    @staticmethod
    def formatar_data_iso_para_datetime(data_iso: str) -> datetime:
        try:
            if 'T' in data_iso:
                dt = datetime.fromisoformat(data_iso.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(data_iso)
            
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            fuso_brasilia = timezone(timedelta(hours=-3))
            return dt.astimezone(fuso_brasilia)
        except Exception:
            return datetime.now()


# =============================
# CLASSE TELEGRAM CLIENT
# =============================

class TelegramClient:
    def __init__(self):
        self.config = ConfigManager()
    
    def enviar_mensagem(self, msg: str, chat_id: str = None, disable_web_page_preview: bool = True) -> bool:
        if chat_id is None:
            chat_id = self.config.TELEGRAM_CHAT_ID
        
        try:
            params = {
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": str(disable_web_page_preview).lower()
            }
            response = requests.get(f"{self.config.BASE_URL_TG}/sendMessage", params=params, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def enviar_foto(self, photo_bytes: io.BytesIO, caption: str = "", chat_id: str = None) -> bool:
        if chat_id is None:
            chat_id = self.config.TELEGRAM_CHAT_ID_ALT2
        
        try:
            photo_bytes.seek(0)
            files = {"photo": ("elite_master.png", photo_bytes, "image/png")}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            resp = requests.post(f"{self.config.BASE_URL_TG}/sendPhoto", data=data, files=files, timeout=15)
            return resp.status_code == 200
        except Exception:
            return False


# =============================
# FUNÇÕES AUXILIARES
# =============================

def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))

def sigmoid(x):
    return 1 / (1 + math.exp(-x))


# =============================
# CLASSE JOGO
# =============================

class Jogo:
    def __init__(self, match_data: dict):
        self.id = match_data.get("idEvent") or match_data.get("id")
        self.home_team = match_data.get("strHomeTeam") or match_data.get("homeTeam", {}).get("name", "")
        self.away_team = match_data.get("strAwayTeam") or match_data.get("awayTeam", {}).get("name", "")
        
        date_event = match_data.get("dateEvent", "")
        time_event = match_data.get("strTime", "")
        if date_event:
            if time_event:
                self.utc_date = f"{date_event}T{time_event}:00"
            else:
                self.utc_date = date_event
        else:
            self.utc_date = match_data.get("utcDate", "")
        
        status_map = {
            "Match Finished": "FINISHED",
            "Not Started": "SCHEDULED",
            "In Progress": "IN_PLAY",
            "Halftime": "IN_PLAY",
            "Postponed": "POSTPONED",
        }
        raw_status = match_data.get("strStatus", "")
        self.status = status_map.get(raw_status, "SCHEDULED")
        
        self.competition = match_data.get("strLeague") or match_data.get("competition", {}).get("name", "Desconhecido")
        self.home_crest = match_data.get("strHomeTeamBadge") or ""
        self.away_crest = match_data.get("strAwayTeamBadge") or ""
        
        self.tendencia = ""
        self.estimativa = 0.0
        self.probabilidade = 0.0
        self.confianca = 0.0
        self.tipo_aposta = ""
        self.detalhes_analise = {}
        
        self.home_goals = None
        self.away_goals = None
        self.ht_home_goals = None
        self.ht_away_goals = None
        self.resultado = None
        self.resultado_favorito = None
        self.resultado_ht = None
        self.resultado_ambas_marcam = None
        self.conferido = False
        
        self.favorito = ""
        self.confianca_vitoria = 0.0
        self.prob_home_win = 0.0
        self.prob_away_win = 0.0
        self.prob_draw = 0.0
        self.tendencia_ht = ""
        self.confianca_ht = 0.0
        self.estimativa_total_ht = 0.0
        self.tendencia_ambas_marcam = ""
        self.confianca_ambas_marcam = 0.0
        self.prob_ambas_marcam_sim = 0.0
        self.prob_ambas_marcam_nao = 0.0
    
    def validar_dados(self) -> bool:
        return all([self.id, self.home_team, self.away_team, self.utc_date])
    
    def get_data_hora_brasilia(self):
        if not self.utc_date:
            return "Data inválida", "Hora inválida"
        try:
            if 'T' in self.utc_date:
                dt = datetime.fromisoformat(self.utc_date.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(self.utc_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            fuso_brasilia = timezone(timedelta(hours=-3))
            dt_brasilia = dt.astimezone(fuso_brasilia)
            return dt_brasilia.strftime("%d/%m/%Y"), dt_brasilia.strftime("%H:%M")
        except Exception:
            return "Data inválida", "Hora inválida"
    
    def get_hora_brasilia_datetime(self):
        if not self.utc_date:
            return datetime.now()
        try:
            if 'T' in self.utc_date:
                dt = datetime.fromisoformat(self.utc_date.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(self.utc_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            fuso_brasilia = timezone(timedelta(hours=-3))
            return dt.astimezone(fuso_brasilia)
        except Exception:
            return datetime.now()
    
    def set_analise(self, analise: dict):
        self.tendencia = analise.get("tendencia", "")
        self.estimativa = analise.get("estimativa", 0.0)
        self.probabilidade = analise.get("probabilidade", 0.0)
        self.confianca = analise.get("confianca", 0.0)
        self.tipo_aposta = analise.get("tipo_aposta", "")
        self.detalhes_analise = analise.get("detalhes", {})
        
        if "vitoria" in analise.get("detalhes", {}):
            v = analise["detalhes"]["vitoria"]
            self.favorito = v.get("favorito", "")
            self.confianca_vitoria = v.get("confianca_vitoria", 0.0)
            self.prob_home_win = v.get("home_win", 0.0)
            self.prob_away_win = v.get("away_win", 0.0)
            self.prob_draw = v.get("draw", 0.0)
        
        if "gols_ht" in analise.get("detalhes", {}):
            ht = analise["detalhes"]["gols_ht"]
            self.tendencia_ht = ht.get("tendencia_ht", "")
            self.confianca_ht = ht.get("confianca_ht", 0.0)
            self.estimativa_total_ht = ht.get("estimativa_total_ht", 0.0)
        
        if "ambas_marcam" in analise.get("detalhes", {}):
            am = analise["detalhes"]["ambas_marcam"]
            self.tendencia_ambas_marcam = am.get("tendencia_ambas_marcam", "")
            self.confianca_ambas_marcam = am.get("confianca_ambas_marcam", 0.0)
            self.prob_ambas_marcam_sim = am.get("sim", 0.0)
            self.prob_ambas_marcam_nao = am.get("nao", 0.0)
    
    def set_resultado(self, home_goals: int, away_goals: int, ht_home_goals: int = None, ht_away_goals: int = None):
        self.home_goals = home_goals
        self.away_goals = away_goals
        self.ht_home_goals = ht_home_goals
        self.ht_away_goals = ht_away_goals
        self.conferido = True
        
        total_gols = home_goals + away_goals
        self.resultado = self._calc_over_under(total_gols)
        self.resultado_favorito = self._calc_favorito(home_goals, away_goals)
        
        if ht_home_goals is not None and ht_away_goals is not None:
            self.resultado_ht = self._calc_gols_ht(ht_home_goals + ht_away_goals)
        
        self.resultado_ambas_marcam = self._calc_ambas_marcam(home_goals, away_goals)
    
    def _calc_over_under(self, total_gols: float) -> str:
        if "OVER" in self.tendencia.upper():
            if "OVER 1.5" in self.tendencia and total_gols > 1.5:
                return "GREEN"
            if "OVER 2.5" in self.tendencia and total_gols > 2.5:
                return "GREEN"
            if "OVER 3.5" in self.tendencia and total_gols > 3.5:
                return "GREEN"
        elif "UNDER" in self.tendencia.upper():
            if "UNDER 1.5" in self.tendencia and total_gols < 1.5:
                return "GREEN"
            if "UNDER 2.5" in self.tendencia and total_gols < 2.5:
                return "GREEN"
            if "UNDER 3.5" in self.tendencia and total_gols < 3.5:
                return "GREEN"
        return "RED"
    
    def _calc_favorito(self, home_goals: int, away_goals: int) -> str:
        if self.favorito == "home" and home_goals > away_goals:
            return "GREEN"
        if self.favorito == "away" and away_goals > home_goals:
            return "GREEN"
        if self.favorito == "draw" and home_goals == away_goals:
            return "GREEN"
        return "RED"
    
    def _calc_gols_ht(self, total_gols_ht: int) -> str:
        if self.tendencia_ht == "OVER 0.5 HT" and total_gols_ht > 0.5:
            return "GREEN"
        if self.tendencia_ht == "UNDER 0.5 HT" and total_gols_ht < 0.5:
            return "GREEN"
        if self.tendencia_ht == "OVER 1.5 HT" and total_gols_ht > 1.5:
            return "GREEN"
        return "RED"
    
    def _calc_ambas_marcam(self, home_goals: int, away_goals: int) -> str:
        if self.tendencia_ambas_marcam == "SIM" and home_goals > 0 and away_goals > 0:
            return "GREEN"
        if self.tendencia_ambas_marcam == "NÃO" and (home_goals == 0 or away_goals == 0):
            return "GREEN"
        return "RED"
    
    def to_dict(self):
        d = {
            "id": self.id, "home": self.home_team, "away": self.away_team,
            "tendencia": self.tendencia, "estimativa": self.estimativa,
            "probabilidade": self.probabilidade, "confianca": self.confianca,
            "tipo_aposta": self.tipo_aposta, "liga": self.competition,
            "hora": self.get_hora_brasilia_datetime().isoformat(),
            "status": self.status, "escudo_home": self.home_crest,
            "escudo_away": self.away_crest, "detalhes": self.detalhes_analise,
            "conferido": self.conferido, "resultado": self.resultado,
            "home_goals": self.home_goals, "away_goals": self.away_goals,
            "ht_home_goals": self.ht_home_goals, "ht_away_goals": self.ht_away_goals,
            "resultado_favorito": self.resultado_favorito,
            "resultado_ht": self.resultado_ht,
            "resultado_ambas_marcam": self.resultado_ambas_marcam
        }
        if self.favorito:
            d.update({"favorito": self.favorito, "confianca_vitoria": self.confianca_vitoria,
                     "prob_home_win": self.prob_home_win, "prob_away_win": self.prob_away_win,
                     "prob_draw": self.prob_draw})
        if self.tendencia_ht:
            d.update({"tendencia_ht": self.tendencia_ht, "confianca_ht": self.confianca_ht,
                     "estimativa_total_ht": self.estimativa_total_ht})
        if self.tendencia_ambas_marcam:
            d.update({"tendencia_ambas_marcam": self.tendencia_ambas_marcam,
                     "confianca_ambas_marcam": self.confianca_ambas_marcam,
                     "prob_ambas_marcam_sim": self.prob_ambas_marcam_sim,
                     "prob_ambas_marcam_nao": self.prob_ambas_marcam_nao})
        return d


# =============================
# CLASSE ALERTA
# =============================

class Alerta:
    def __init__(self, jogo: Jogo, data_busca: str, tipo_alerta: str = "over_under"):
        self.jogo = jogo
        self.data_busca = data_busca
        self.data_hora_busca = datetime.now()
        self.tipo_alerta = tipo_alerta
        self.conferido = False
        self.alerta_enviado = False
    
    def to_dict(self):
        d = {
            "id": self.jogo.id, "home": self.jogo.home_team, "away": self.jogo.away_team,
            "liga": self.jogo.competition, "hora": self.jogo.get_hora_brasilia_datetime().isoformat(),
            "data_busca": self.data_busca, "data_hora_busca": self.data_hora_busca.isoformat(),
            "tipo_alerta": self.tipo_alerta, "conferido": self.conferido,
            "alerta_enviado": self.alerta_enviado, "escudo_home": self.jogo.home_crest,
            "escudo_away": self.jogo.away_crest
        }
        if self.tipo_alerta == "over_under":
            d.update({"tendencia": self.jogo.tendencia, "estimativa": self.jogo.estimativa,
                     "probabilidade": self.jogo.probabilidade, "confianca": self.jogo.confianca,
                     "tipo_aposta": self.jogo.tipo_aposta})
        elif self.tipo_alerta == "favorito":
            d.update({"favorito": self.jogo.favorito, "confianca_vitoria": self.jogo.confianca_vitoria,
                     "prob_home_win": self.jogo.prob_home_win, "prob_away_win": self.jogo.prob_away_win,
                     "prob_draw": self.jogo.prob_draw})
        elif self.tipo_alerta == "gols_ht":
            d.update({"tendencia_ht": self.jogo.tendencia_ht, "confianca_ht": self.jogo.confianca_ht,
                     "estimativa_total_ht": self.jogo.estimativa_total_ht})
        elif self.tipo_alerta == "ambas_marcam":
            d.update({"tendencia_ambas_marcam": self.jogo.tendencia_ambas_marcam,
                     "confianca_ambas_marcam": self.jogo.confianca_ambas_marcam,
                     "prob_ambas_marcam_sim": self.jogo.prob_ambas_marcam_sim,
                     "prob_ambas_marcam_nao": self.jogo.prob_ambas_marcam_nao})
        return d


# =============================
# CLASSES DE ANÁLISE
# =============================

class AnalisadorEstatistico:
    @staticmethod
    def calcular_probabilidade_vitoria(home: str, away: str, classificacao: dict) -> dict:
        dados_home = classificacao.get(home, {"wins": 0, "draws": 0, "losses": 0, "played": 1, "scored": 0, "against": 0})
        dados_away = classificacao.get(away, {"wins": 0, "draws": 0, "losses": 0, "played": 1, "scored": 0, "against": 0})
        
        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)
        
        win_rate_home = dados_home["wins"] / played_home
        win_rate_away = dados_away["wins"] / played_away
        draw_rate_home = dados_home["draws"] / played_home
        draw_rate_away = dados_away["draws"] / played_away
        
        saldo_home = (dados_home["scored"] - dados_home["against"]) / played_home
        saldo_away = (dados_away["scored"] - dados_away["against"]) / played_away
        
        fator_casa = clamp(1.05 + saldo_home * 0.1, 1.0, 1.2)
        fator_fora = 2.0 - fator_casa
        
        prob_home = (win_rate_home * fator_casa + (1 - win_rate_away) * fator_fora) * 50
        prob_away = (win_rate_away * fator_fora + (1 - win_rate_home) * fator_casa) * 50
        prob_draw = ((draw_rate_home + draw_rate_away) / 2) * 100
        
        if abs(prob_home - prob_away) < 5:
            prob_draw *= 0.85
        
        total = prob_home + prob_away + prob_draw
        if total > 0:
            prob_home = (prob_home / total) * 100
            prob_away = (prob_away / total) * 100
            prob_draw = (prob_draw / total) * 100
        
        prob_home = clamp(prob_home, 5, 90)
        prob_away = clamp(prob_away, 5, 90)
        prob_draw = clamp(prob_draw, 5, 90)
        
        if prob_home > prob_away and prob_home > prob_draw:
            favorito = "home"
        elif prob_away > prob_home and prob_away > prob_draw:
            favorito = "away"
        else:
            favorito = "draw"
        
        return {"home_win": round(prob_home, 1), "away_win": round(prob_away, 1),
                "draw": round(prob_draw, 1), "favorito": favorito,
                "confianca_vitoria": round(max(prob_home, prob_away, prob_draw), 1)}
    
    @staticmethod
    def calcular_probabilidade_gols_ht(home: str, away: str, classificacao: dict) -> dict:
        dados_home = classificacao.get(home, {"scored": 0, "played": 1})
        dados_away = classificacao.get(away, {"scored": 0, "played": 1})
        
        media_home = dados_home["scored"] / max(dados_home["played"], 1)
        media_away = dados_away["scored"] / max(dados_away["played"], 1)
        
        estimativa = (media_home + media_away) * 0.45
        estimativa = clamp(estimativa, 0.2, 1.8)
        
        if estimativa > 1.1:
            tendencia = "OVER 1.5 HT"
        elif estimativa > 0.6:
            tendencia = "OVER 0.5 HT"
        else:
            tendencia = "UNDER 0.5 HT"
        
        confianca = clamp(max(sigmoid((estimativa - 0.5) * 3), sigmoid((estimativa - 1.2) * 3)) * 85, 40, 85)
        
        return {"estimativa_total_ht": round(estimativa, 2), "tendencia_ht": tendencia,
                "confianca_ht": round(confianca, 1)}
    
    @staticmethod
    def calcular_probabilidade_ambas_marcam(home: str, away: str, classificacao: dict) -> dict:
        dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
        dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
        
        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)
        
        taxa_gols_home = dados_home["scored"] / played_home
        taxa_gols_away = dados_away["scored"] / played_away
        taxa_sofridos_home = dados_home["against"] / played_home
        taxa_sofridos_away = dados_away["against"] / played_away
        
        prob_home_marca = (1 / (1 + math.exp(-taxa_gols_home * 0.8))) * 0.6 + (1 / (1 + math.exp(-taxa_sofridos_away * 0.8))) * 0.4
        prob_away_marca = (1 / (1 + math.exp(-taxa_gols_away * 0.8))) * 0.4 + (1 / (1 + math.exp(-taxa_sofridos_home * 0.8))) * 0.6
        
        prob_ambas = clamp(prob_home_marca * prob_away_marca * 100, 0, 95)
        prob_nao = 100 - prob_ambas
        
        if prob_ambas >= 60:
            tendencia = "SIM"
        elif prob_nao >= 60:
            tendencia = "NÃO"
        else:
            tendencia = "SIM" if prob_ambas >= prob_nao else "NÃO"
        
        confianca = clamp(50 + abs(prob_ambas - prob_nao) * 0.5, 55, 85)
        
        return {"sim": round(prob_ambas, 1), "nao": round(prob_nao, 1),
                "tendencia_ambas_marcam": tendencia, "confianca_ambas_marcam": round(confianca, 1)}


class AnalisadorTendencia:
    def __init__(self, classificacao: dict):
        self.classificacao = classificacao
    
    def calcular_tendencia_completa(self, home: str, away: str) -> dict:
        dados_home = self.classificacao.get(home, {})
        dados_away = self.classificacao.get(away, {})
        
        played_home = dados_home.get("played", 0)
        played_away = dados_away.get("played", 0)
        
        if played_home < 3 or played_away < 3:
            return {"tendencia": "DADOS INSUFICIENTES", "estimativa": 0, "probabilidade": 0,
                    "confianca": 0, "tipo_aposta": "avoid", "linha_mercado": 0,
                    "detalhes": {"motivo": f"Jogos insuficientes: Home={played_home}, Away={played_away}"}}
        
        media_home_feitos = dados_home.get("scored", 0) / max(played_home, 1)
        media_home_sofridos = dados_home.get("against", 0) / max(played_home, 1)
        media_away_feitos = dados_away.get("scored", 0) / max(played_away, 1)
        media_away_sofridos = dados_away.get("against", 0) / max(played_away, 1)
        
        media_home_feitos = clamp(media_home_feitos, 0.6, 3.6)
        media_home_sofridos = clamp(media_home_sofridos, 0.6, 3.2)
        media_away_feitos = clamp(media_away_feitos, 0.6, 3.4)
        media_away_sofridos = clamp(media_away_sofridos, 0.6, 3.2)
        
        estimativa = (media_home_feitos * 0.55 + media_away_feitos * 0.55 +
                     media_home_sofridos * 0.25 + media_away_sofridos * 0.25)
        
        fator_ataque = (media_home_feitos / max(media_away_sofridos, 0.75) +
                        media_away_feitos / max(media_home_sofridos, 0.75)) / 2
        
        if fator_ataque >= 1.6:
            estimativa *= 1.12
        elif fator_ataque >= 1.35:
            estimativa *= 1.08
        elif fator_ataque <= 0.7:
            estimativa *= 0.92
        
        fator_casa = clamp(1.06 + (media_home_feitos - media_home_sofridos) * 0.10, 0.95, 1.18)
        estimativa *= fator_casa
        estimativa = clamp((estimativa * 0.75) + (2.5 * 0.25), 1.3, 4.2)
        
        if estimativa <= 1.5:
            mercado = "UNDER 2.5"
            tipo = "under"
            linha = 2.5
            prob_base = sigmoid((2.5 - estimativa) * 1.3)
        elif estimativa <= 2.0:
            if fator_ataque < 0.9:
                mercado = "UNDER 2.5"
                tipo = "under"
                linha = 2.5
                prob_base = sigmoid((2.5 - estimativa) * 1.2)
            else:
                mercado = "OVER 1.5"
                tipo = "over"
                linha = 1.5
                prob_base = sigmoid((estimativa - 1.5) * 1.5)
        elif estimativa >= 3.3:
            mercado = "OVER 3.5"
            tipo = "over"
            linha = 3.5
            prob_base = sigmoid((estimativa - 3.5) * 1.0)
        elif estimativa >= 2.6:
            mercado = "OVER 2.5"
            tipo = "over"
            linha = 2.5
            prob_base = sigmoid((estimativa - 2.5) * 1.1)
        else:
            mercado = "OVER 1.5"
            tipo = "over"
            linha = 1.5
            prob_base = sigmoid((estimativa - 1.5) * 1.5)
        
        if tipo == "under" and estimativa > 1.85:
            return {"tendencia": "NÃO APOSTAR", "estimativa": round(estimativa, 2),
                    "probabilidade": round(prob_base * 100, 1), "confianca": 0,
                    "tipo_aposta": "avoid", "linha_mercado": linha,
                    "detalhes": {"motivo": "UNDER perigoso"}}
        
        confianca = clamp(prob_base * 50 + min(abs(estimativa - linha) * 25, 30) +
                         (10 if played_home >= 5 and played_away >= 5 else 0) +
                         (5 if abs(media_home_feitos - media_away_feitos) < 1.0 else 0) +
                         (5 if fator_ataque > 1.3 or fator_ataque < 0.8 else 0), 35, 75)
        
        if confianca < 45:
            return {"tendencia": "NÃO APOSTAR", "estimativa": round(estimativa, 2),
                    "probabilidade": round(prob_base * 100, 1), "confianca": round(confianca, 1),
                    "tipo_aposta": "avoid", "linha_mercado": linha,
                    "detalhes": {"motivo": f"Confiança baixa: {confianca:.1f}%"}}
        
        return {"tendencia": mercado, "estimativa": round(estimativa, 2),
                "probabilidade": round(prob_base * 100, 1), "confianca": round(confianca, 1),
                "tipo_aposta": tipo, "linha_mercado": linha,
                "detalhes": {"fator_ataque": round(fator_ataque, 2),
                             "distancia_linha": round(abs(estimativa - linha), 2),
                             "played_home": played_home, "played_away": played_away}}


# =============================
# CLASSE ALERTA COMPLETO (DEFINIDA ANTES DE GERENCIADOR)
# =============================

class AlertaCompleto:
    def __init__(self, jogo: Jogo, data_busca: str):
        self.jogo = jogo
        self.data_busca = data_busca
        self.data_hora_busca = datetime.now()
        self.tipo_alerta = "completo"
        self.conferido = False
        self.alerta_enviado = False
        
        self.analise_over_under = {
            "tendencia": jogo.tendencia, "estimativa": jogo.estimativa,
            "probabilidade": jogo.probabilidade, "confianca": jogo.confianca,
            "tipo_aposta": jogo.tipo_aposta
        }
        self.analise_favorito = {
            "favorito": jogo.favorito, "confianca_vitoria": jogo.confianca_vitoria,
            "prob_home_win": jogo.prob_home_win, "prob_away_win": jogo.prob_away_win,
            "prob_draw": jogo.prob_draw
        }
        self.analise_gols_ht = {
            "tendencia_ht": jogo.tendencia_ht, "confianca_ht": jogo.confianca_ht,
            "estimativa_total_ht": jogo.estimativa_total_ht
        }
        self.analise_ambas_marcam = {
            "tendencia_ambas_marcam": jogo.tendencia_ambas_marcam,
            "confianca_ambas_marcam": jogo.confianca_ambas_marcam,
            "prob_ambas_marcam_sim": jogo.prob_ambas_marcam_sim,
            "prob_ambas_marcam_nao": jogo.prob_ambas_marcam_nao
        }
        self.resultados = {
            "over_under": None, "favorito": None, "gols_ht": None,
            "ambas_marcam": None, "home_goals": None, "away_goals": None,
            "ht_home_goals": None, "ht_away_goals": None
        }
    
    def to_dict(self):
        return {
            "id": self.jogo.id, "home": self.jogo.home_team, "away": self.jogo.away_team,
            "liga": self.jogo.competition, "hora": self.jogo.get_hora_brasilia_datetime().isoformat(),
            "data_busca": self.data_busca, "data_hora_busca": self.data_hora_busca.isoformat(),
            "tipo_alerta": self.tipo_alerta, "conferido": self.conferido,
            "alerta_enviado": self.alerta_enviado, "escudo_home": self.jogo.home_crest,
            "escudo_away": self.jogo.away_crest, "analise_over_under": self.analise_over_under,
            "analise_favorito": self.analise_favorito, "analise_gols_ht": self.analise_gols_ht,
            "analise_ambas_marcam": self.analise_ambas_marcam, "resultados": self.resultados,
            "detalhes": self.jogo.detalhes_analise
        }
    
    def set_resultados(self, home_goals: int, away_goals: int, ht_home_goals: int = None, ht_away_goals: int = None):
        self.resultados.update({"home_goals": home_goals, "away_goals": away_goals,
                                "ht_home_goals": ht_home_goals, "ht_away_goals": ht_away_goals})
        self.conferido = True
        
        total = home_goals + away_goals
        tendencia = self.analise_over_under.get("tendencia", "")
        if "OVER" in tendencia.upper():
            if ("OVER 1.5" in tendencia and total > 1.5) or ("OVER 2.5" in tendencia and total > 2.5):
                self.resultados["over_under"] = "GREEN"
            else:
                self.resultados["over_under"] = "RED"
        elif "UNDER" in tendencia.upper():
            if ("UNDER 1.5" in tendencia and total < 1.5) or ("UNDER 2.5" in tendencia and total < 2.5):
                self.resultados["over_under"] = "GREEN"
            else:
                self.resultados["over_under"] = "RED"
        
        fav = self.analise_favorito.get("favorito", "")
        if (fav == "home" and home_goals > away_goals) or (fav == "away" and away_goals > home_goals) or (fav == "draw" and home_goals == away_goals):
            self.resultados["favorito"] = "GREEN"
        else:
            self.resultados["favorito"] = "RED"
        
        if ht_home_goals is not None:
            total_ht = ht_home_goals + ht_away_goals
            ht_tend = self.analise_gols_ht.get("tendencia_ht", "")
            if (ht_tend == "OVER 0.5 HT" and total_ht > 0.5) or (ht_tend == "OVER 1.5 HT" and total_ht > 1.5):
                self.resultados["gols_ht"] = "GREEN"
            elif ht_tend == "UNDER 0.5 HT" and total_ht < 0.5:
                self.resultados["gols_ht"] = "GREEN"
            else:
                self.resultados["gols_ht"] = "RED"
        
        am_tend = self.analise_ambas_marcam.get("tendencia_ambas_marcam", "")
        if (am_tend == "SIM" and home_goals > 0 and away_goals > 0) or (am_tend == "NÃO" and (home_goals == 0 or away_goals == 0)):
            self.resultados["ambas_marcam"] = "GREEN"
        else:
            self.resultados["ambas_marcam"] = "RED"


# =============================
# CLASSE GERENCIADOR ALERTAS COMPLETOS
# =============================

class GerenciadorAlertasCompletos:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = sistema_principal.config
        self.poster_generator = sistema_principal.poster_generator
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client
        self.ALERTAS_COMPLETOS_PATH = "alertas_completos.json"
    
    def salvar_alerta_completo(self, alerta: AlertaCompleto):
        alertas = self.carregar_alertas()
        alertas[f"{alerta.jogo.id}_{alerta.data_busca}"] = alerta.to_dict()
        DataStorage.salvar_json(self.ALERTAS_COMPLETOS_PATH, alertas)
    
    def carregar_alertas(self) -> dict:
        return DataStorage.carregar_json(self.ALERTAS_COMPLETOS_PATH)
    
    def filtrar_melhores_jogos(self, jogos_analisados: list, limiares: dict = None) -> list:
        if limiares is None:
            limiares = {'over_under': 60, 'favorito': 50, 'gols_ht': 30, 'ambas_marcam': 30}
        
        return [j for j in jogos_analisados
                if (j.get('confianca', 0) >= limiares['over_under'] and
                    j.get('confianca_vitoria', 0) >= limiares['favorito'] and
                    j.get('confianca_ht', 0) >= limiares['gols_ht'] and
                    j.get('confianca_ambas_marcam', 0) >= limiares['ambas_marcam'])]
    
    def processar_e_enviar_alertas_completos(self, jogos_analisados: list, data_busca: str, filtrar_melhores: bool = True):
        if not jogos_analisados:
            return False
        
        jogos_para = self.filtrar_melhores_jogos(jogos_analisados) if filtrar_melhores else jogos_analisados
        if not jogos_para:
            st.info("⚠️ Nenhum jogo atende aos critérios.")
            return False
        
        jogos_poster = []
        for j in jogos_para:
            jogo = Jogo({"idEvent": j["id"], "strHomeTeam": j["home"], "strAwayTeam": j["away"],
                        "strHomeTeamBadge": j.get("escudo_home", ""), "strAwayTeamBadge": j.get("escudo_away", ""),
                        "dateEvent": j.get("hora", ""), "strLeague": j.get("liga", ""), "strStatus": j.get("status", "")})
            jogo.set_analise({"tendencia": j.get("tendencia", ""), "estimativa": j.get("estimativa", 0),
                              "probabilidade": j.get("probabilidade", 0), "confianca": j.get("confianca", 0),
                              "tipo_aposta": j.get("tipo_aposta", ""), "detalhes": j.get("detalhes", {})})
            self.salvar_alerta_completo(AlertaCompleto(jogo, data_busca))
            jogos_poster.append({"home": jogo.home_team, "away": jogo.away_team, "liga": jogo.competition,
                                 "hora": jogo.get_hora_brasilia_datetime(), "escudo_home": jogo.home_crest,
                                 "escudo_away": jogo.away_crest,
                                 "analise_over_under": {"tendencia": jogo.tendencia, "confianca": jogo.confianca},
                                 "analise_favorito": {"favorito": jogo.favorito, "confianca_vitoria": jogo.confianca_vitoria},
                                 "analise_gols_ht": {"tendencia_ht": jogo.tendencia_ht, "confianca_ht": jogo.confianca_ht},
                                 "analise_ambas_marcam": {"tendencia_ambas_marcam": jogo.tendencia_ambas_marcam,
                                                          "confianca_ambas_marcam": jogo.confianca_ambas_marcam}})
        
        if jogos_poster:
            poster = self._gerar_poster_completo(jogos_poster)
            caption = f"<b>⚽ ALERTA COMPLETO - ALL IN ONE</b>\n<b>📋 {len(jogos_poster)} JOGOS</b>\n\n<b>🎯 Over/Under | 🏆 Favorito | ⏰ Gols HT | 🤝 Ambas Marcam</b>"
            return self.telegram_client.enviar_foto(poster, caption=caption)
        return False
    
    def _gerar_poster_completo(self, jogos: list) -> io.BytesIO:
        LARGURA, PADDING = 2000, 80
        ALTURA_POR_JOGO, ALTURA_TOPO = 800, 270
        img = Image.new("RGB", (LARGURA, ALTURA_TOPO + len(jogos) * ALTURA_POR_JOGO), (10, 20, 30))
        draw = ImageDraw.Draw(img)
        fonte_titulo = self.poster_generator.criar_fonte(70)
        draw.text((LARGURA//2 - 200, 80), "ALERTA COMPLETO - ALL IN ONE", font=fonte_titulo, fill=(255, 255, 255))
        y = ALTURA_TOPO
        for j in jogos:
            draw.rectangle([PADDING, y, LARGURA - PADDING, y + ALTURA_POR_JOGO - 40], fill=(25, 35, 45), outline=(255, 215, 0), width=3)
            draw.text((LARGURA//2 - 100, y + 30), j["liga"][:30], font=self.poster_generator.criar_fonte(45), fill=(200, 200, 200))
            draw.text((LARGURA//2 - 80, y + 450), f"{j['home']} vs {j['away']}", font=self.poster_generator.criar_fonte(50), fill=(255, 255, 255))
            draw.text((PADDING + 50, y + 550), f"OVER/UNDER: {j['analise_over_under']['tendencia']} ({j['analise_over_under']['confianca']:.0f}%)", font=self.poster_generator.criar_fonte(40), fill=(255, 215, 0))
            draw.text((PADDING + 50, y + 600), f"FAVORITO: {j['analise_favorito']['favorito']} ({j['analise_favorito']['confianca_vitoria']:.0f}%)", font=self.poster_generator.criar_fonte(40), fill=(100, 200, 255))
            draw.text((PADDING + 50, y + 650), f"GOLS HT: {j['analise_gols_ht']['tendencia_ht']} ({j['analise_gols_ht']['confianca_ht']:.0f}%)", font=self.poster_generator.criar_fonte(40), fill=(100, 255, 100))
            draw.text((PADDING + 50, y + 700), f"AMBAS MARCAM: {j['analise_ambas_marcam']['tendencia_ambas_marcam']} ({j['analise_ambas_marcam']['confianca_ambas_marcam']:.0f}%)", font=self.poster_generator.criar_fonte(40), fill=(155, 89, 182))
            y += ALTURA_POR_JOGO
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf


# =============================
# CLASSE POSTER GENERATOR
# =============================

class PosterGenerator:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
    
    @staticmethod
    def criar_fonte(tamanho: int):
        try:
            fontes = ["arial.ttf", "DejaVuSans.ttf", "/System/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]
            for f in fontes:
                if os.path.exists(f):
                    return ImageFont.truetype(f, tamanho)
        except:
            pass
        return ImageFont.load_default()
    
    def gerar_poster_westham_style(self, jogos: list, titulo: str = "ALERTA", tipo_alerta: str = "over_under") -> io.BytesIO:
        LARGURA, PADDING = 2000, 80
        ALTURA_POR_JOGO, ALTURA_TOPO = 750, 270
        img = Image.new("RGB", (LARGURA, ALTURA_TOPO + len(jogos) * ALTURA_POR_JOGO), (10, 20, 30))
        draw = ImageDraw.Draw(img)
        fonte_titulo = self.criar_fonte(80)
        draw.text((LARGURA//2 - 250, 80), titulo[:40], font=fonte_titulo, fill=(255, 255, 255))
        y = ALTURA_TOPO
        for j in jogos:
            draw.rectangle([PADDING, y, LARGURA - PADDING, y + ALTURA_POR_JOGO - 40], fill=(25, 35, 45), outline=(255, 215, 0), width=3)
            draw.text((LARGURA//2 - 100, y + 30), j.get("liga", "")[:30], font=self.criar_fonte(45), fill=(200, 200, 200))
            draw.text((LARGURA//2 - 80, y + 450), f"{j.get('home', '')[:20]} vs {j.get('away', '')[:20]}", font=self.criar_fonte(50), fill=(255, 255, 255))
            if tipo_alerta == "over_under":
                draw.text((PADDING + 50, y + 550), f"{j.get('tendencia', 'N/A')} | Conf: {j.get('confianca', 0):.0f}%", font=self.criar_fonte(45), fill=(255, 215, 0))
            elif tipo_alerta == "favorito":
                fav = j.get('favorito', '')
                fav_text = j.get('home', '') if fav == "home" else j.get('away', '') if fav == "away" else "EMPATE"
                draw.text((PADDING + 50, y + 550), f"FAVORITO: {fav_text} | Conf: {j.get('confianca_vitoria', 0):.0f}%", font=self.criar_fonte(45), fill=(255, 215, 0))
            y += ALTURA_POR_JOGO
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    def gerar_poster_resultados(self, jogos: list, tipo_alerta: str) -> io.BytesIO:
        LARGURA, PADDING = 2000, 80
        ALTURA_POR_JOGO, ALTURA_TOPO = 750, 270
        img = Image.new("RGB", (LARGURA, ALTURA_TOPO + len(jogos) * ALTURA_POR_JOGO), (10, 20, 30))
        draw = ImageDraw.Draw(img)
        draw.text((LARGURA//2 - 300, 80), f"RESULTADOS - {tipo_alerta.upper()}", font=self.criar_fonte(80), fill=(255, 255, 255))
        y = ALTURA_TOPO
        for j in jogos:
            draw.rectangle([PADDING, y, LARGURA - PADDING, y + ALTURA_POR_JOGO - 40], fill=(25, 35, 45), outline=(46, 204, 113) if j.get("resultado") == "GREEN" else (231, 76, 60), width=3)
            draw.text((PADDING + 50, y + 30), f"{j.get('home', '')} vs {j.get('away', '')}", font=self.criar_fonte(50), fill=(255, 255, 255))
            draw.text((PADDING + 50, y + 100), f"Placar: {j.get('home_goals', '?')} - {j.get('away_goals', '?')}", font=self.criar_fonte(45), fill=(255, 215, 0))
            draw.text((PADDING + 50, y + 170), f"Resultado: {j.get('resultado', 'PENDENTE')}", font=self.criar_fonte(55), fill=(46, 204, 113) if j.get("resultado") == "GREEN" else (231, 76, 60))
            y += ALTURA_POR_JOGO
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf


# =============================
# CLASSE RESULTADOS TOP ALERTAS
# =============================

class ResultadosTopAlertas:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client
        self.poster_generator = sistema_principal.poster_generator
    
    def conferir_resultados_top_alertas(self, data_selecionada):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.subheader(f"🏆 Conferindo Resultados TOP Alertas - {data_selecionada.strftime('%d/%m/%Y')}")
        
        alertas_top = DataStorage.carregar_alertas_top()
        if not alertas_top:
            st.warning("⚠️ Nenhum alerta TOP salvo")
            return
        
        alertas_hoje = {k: v for k, v in alertas_top.items() if v.get("data_busca") == hoje and not v.get("enviado", False)}
        if not alertas_hoje:
            st.info("ℹ️ Nenhum alerta pendente")
            return
        
        grupos = {}
        for chave, alerta in alertas_hoje.items():
            tipo = alerta.get("tipo_alerta", "over_under")
            if tipo not in grupos:
                grupos[tipo] = {}
            hora = alerta.get("data_hora_busca", "")[:16] if alerta.get("data_hora_busca") else "default"
            if hora not in grupos[tipo]:
                grupos[tipo][hora] = []
            grupos[tipo][hora].append(alerta)
        
        for tipo, horarios in grupos.items():
            for hora, alertas_grupo in horarios.items():
                todos_finished = True
                conferidos = []
                for a in alertas_grupo:
                    match = self.api_client.obter_detalhes_jogo(a.get("id"))
                    if not match:
                        todos_finished = False
                        continue
                    status = match.get("strStatus", "")
                    if status == "Match Finished":
                        home_g = int(match.get("intHomeScore", 0) or 0)
                        away_g = int(match.get("intAwayScore", 0) or 0)
                        a["conferido"] = True
                        a["home_goals"] = home_g
                        a["away_goals"] = away_g
                        if tipo == "over_under":
                            total = home_g + away_g
                            tend = a.get("tendencia", "")
                            a["resultado"] = "GREEN" if (("OVER" in tend and total > 2.5) or ("UNDER" in tend and total < 2.5)) else "RED"
                        conferidos.append(a)
                    else:
                        todos_finished = False
                
                if todos_finished and conferidos:
                    self._enviar_grupo_resultados(conferidos, tipo, data_selecionada)
        
        DataStorage.salvar_alertas_top(alertas_top)
    
    def _enviar_grupo_resultados(self, alertas: list, tipo: str, data: datetime):
        greens = sum(1 for a in alertas if a.get("resultado") == "GREEN")
        reds = len(alertas) - greens
        taxa = (greens / len(alertas) * 100) if alertas else 0
        
        titulo = f"🏆 RESULTADOS TOP - {tipo.upper()}"
        poster = self.poster_generator.gerar_poster_resultados(alertas, tipo)
        caption = f"<b>{titulo}</b>\n<b>📊 {len(alertas)} JOGOS</b>\n<b>✅ {greens} | ❌ {reds} | 🎯 {taxa:.1f}%</b>"
        
        if poster and self.telegram_client.enviar_foto(poster, caption=caption):
            for a in alertas:
                a["enviado"] = True
                a["data_envio"] = datetime.now().isoformat()
            st.success(f"✅ Grupo {tipo} enviado!")


# =============================
# CLASSE SISTEMA PRINCIPAL
# =============================

class SistemaAlertasFutebol:
    def __init__(self):
        self.config = ConfigManager()
        self.rate_limiter = RateLimiter()
        self.api_monitor = APIMonitor()
        self.api_client = APIClient(self.rate_limiter, self.api_monitor)
        self.telegram_client = TelegramClient()
        self.poster_generator = PosterGenerator(self.api_client)
        self.resultados_top = ResultadosTopAlertas(self)
        self.gerenciador_completo = GerenciadorAlertasCompletos(self)
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    def processar_jogos(self, data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf,
                        max_conf, estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                        formato_top_jogos, tipo_filtro, tipo_analise, config_analise):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        if todas_ligas:
            ligas_busca = list(self.config.LIGA_DICT.values())
        else:
            ligas_busca = [self.config.LIGA_DICT[n] for n in ligas_selecionadas]
        
        st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
        
        top_jogos = []
        for i, liga_id in enumerate(ligas_busca):
            classificacao = self.api_client.obter_classificacao(liga_id)
            analisador = AnalisadorTendencia(classificacao)
            jogos_data = self.api_client.obter_jogos(liga_id, hoje)
            
            for match in jogos_data:
                if not self.api_client.validar_dados_jogo(match):
                    continue
                jogo = Jogo(match)
                if not jogo.validar_dados():
                    continue
                
                analise = analisador.calcular_tendencia_completa(jogo.home_team, jogo.away_team)
                
                if classificacao:
                    analise["detalhes"]["vitoria"] = AnalisadorEstatistico.calcular_probabilidade_vitoria(
                        jogo.home_team, jogo.away_team, classificacao)
                    analise["detalhes"]["gols_ht"] = AnalisadorEstatistico.calcular_probabilidade_gols_ht(
                        jogo.home_team, jogo.away_team, classificacao)
                    analise["detalhes"]["ambas_marcam"] = AnalisadorEstatistico.calcular_probabilidade_ambas_marcam(
                        jogo.home_team, jogo.away_team, classificacao)
                
                jogo.set_analise(analise)
                
                if tipo_analise == "Over/Under de Gols" and min_conf <= analise["confianca"] <= max_conf:
                    if tipo_filtro == "Todos" or (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                        self._verificar_enviar_alerta(jogo, match, analise, alerta_individual, min_conf, max_conf, "over_under")
                elif tipo_analise == "Favorito (Vitória)" and analise.get("detalhes", {}).get("vitoria", {}).get("confianca_vitoria", 0) >= config_analise.get("min_conf_vitoria", 65):
                    self._verificar_enviar_alerta(jogo, match, analise, alerta_individual, 65, 100, "favorito")
                elif tipo_analise == "Gols HT (Primeiro Tempo)" and analise.get("detalhes", {}).get("gols_ht", {}).get("confianca_ht", 0) >= config_analise.get("min_conf_ht", 60):
                    self._verificar_enviar_alerta(jogo, match, analise, alerta_individual, 60, 100, "gols_ht")
                elif tipo_analise == "Ambas Marcam (BTTS)" and analise.get("detalhes", {}).get("ambas_marcam", {}).get("confianca_ambas_marcam", 0) >= config_analise.get("min_conf_am", 60):
                    self._verificar_enviar_alerta(jogo, match, analise, alerta_individual, 60, 100, "ambas_marcam")
                
                top_jogos.append(jogo.to_dict())
        
        jogos_filtrados = self._filtrar_por_tipo_analise(top_jogos, tipo_analise, config_analise)
        
        if jogos_filtrados:
            self._enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf, formato_top_jogos, hoje, 
                                   "over_under" if tipo_analise == "Over/Under de Gols" else "favorito")
            if alerta_poster:
                self._enviar_alerta_poster(jogos_filtrados, tipo_analise, config_analise, estilo_poster)
    
    def _verificar_enviar_alerta(self, jogo: Jogo, match_data: dict, analise: dict, alerta_individual: bool, min_conf: int, max_conf: int, tipo_alerta: str):
        alertas = DataStorage.carregar_alertas() if tipo_alerta == "over_under" else \
                  DataStorage.carregar_alertas_favoritos() if tipo_alerta == "favorito" else \
                  DataStorage.carregar_alertas_gols_ht() if tipo_alerta == "gols_ht" else \
                  DataStorage.carregar_alertas_ambas_marcam()
        
        if str(jogo.id) not in alertas:
            alerta = Alerta(jogo, datetime.now().strftime("%Y-%m-%d"), tipo_alerta)
            alertas[str(jogo.id)] = alerta.to_dict()
            
            if alerta_individual:
                self._enviar_alerta_individual(jogo, analise, tipo_alerta)
            
            if tipo_alerta == "over_under":
                DataStorage.salvar_alertas(alertas)
            elif tipo_alerta == "favorito":
                DataStorage.salvar_alertas_favoritos(alertas)
            elif tipo_alerta == "gols_ht":
                DataStorage.salvar_alertas_gols_ht(alertas)
            else:
                DataStorage.salvar_alertas_ambas_marcam(alertas)
    
    def _enviar_alerta_individual(self, jogo: Jogo, analise: dict, tipo: str):
        msg = f"<b>🚨 ALERTA {tipo.upper()}</b>\n\n<b>{jogo.home_team} vs {jogo.away_team}</b>\n"
        if tipo == "over_under":
            msg += f"📈 {analise['tendencia']} | ⚽ {analise['estimativa']:.2f} | 💯 {analise['confianca']:.0f}%"
        elif tipo == "favorito":
            v = analise.get('detalhes', {}).get('vitoria', {})
            msg += f"🏆 Favorito: {jogo.home_team if v.get('favorito')=='home' else jogo.away_team} | 💯 {v.get('confianca_vitoria', 0):.0f}%"
        self.telegram_client.enviar_mensagem(msg)
    
    def _filtrar_por_tipo_analise(self, jogos, tipo_analise, config):
        if tipo_analise == "Over/Under de Gols":
            return [j for j in jogos if config.get("min_conf", 70) <= j.get("confianca", 0) <= config.get("max_conf", 95)
                    and j.get("status") not in ["FINISHED", "IN_PLAY"]]
        elif tipo_analise == "Favorito (Vitória)":
            return [j for j in jogos if j.get("confianca_vitoria", 0) >= config.get("min_conf_vitoria", 65)
                    and j.get("status") not in ["FINISHED", "IN_PLAY"]]
        return jogos
    
    def _enviar_top_jogos(self, jogos, top_n, ativo, min_conf, max_conf, formato, data, tipo):
        if not ativo or not jogos:
            return
        top = sorted(jogos, key=lambda x: x.get("confianca", 0), reverse=True)[:top_n]
        if formato in ["Texto", "Ambos"]:
            msg = f"📢 TOP {len(top)} JOGOS\n\n"
            for i, j in enumerate(top, 1):
                msg += f"{i}. {j['home']} vs {j['away']}\n   {j.get('tendencia', 'N/A')} | 💯 {j.get('confianca', 0):.0f}%\n"
            self.telegram_client.enviar_mensagem(msg)
    
    def _enviar_alerta_poster(self, jogos, tipo_analise, config, estilo):
        if not jogos:
            return
        poster = self.poster_generator.gerar_poster_westham_style(jogos, f"ALERTA - {tipo_analise[:20]}", "over_under")
        caption = f"<b>📊 {len(jogos)} JOGOS - {tipo_analise}</b>"
        self.telegram_client.enviar_foto(poster, caption=caption)
    
    def processar_alertas_completos(self, data, ligas, todas):
        hoje = data.strftime("%Y-%m-%d")
        ligas_busca = list(self.config.LIGA_DICT.values()) if todas else [self.config.LIGA_DICT[l] for l in ligas]
        jogos = []
        for liga_id in ligas_busca:
            classificacao = self.api_client.obter_classificacao(liga_id)
            analisador = AnalisadorTendencia(classificacao)
            for match in self.api_client.obter_jogos(liga_id, hoje):
                if not self.api_client.validar_dados_jogo(match):
                    continue
                jogo = Jogo(match)
                analise = analisador.calcular_tendencia_completa(jogo.home_team, jogo.away_team)
                if classificacao:
                    analise["detalhes"]["vitoria"] = AnalisadorEstatistico.calcular_probabilidade_vitoria(
                        jogo.home_team, jogo.away_team, classificacao)
                    analise["detalhes"]["gols_ht"] = AnalisadorEstatistico.calcular_probabilidade_gols_ht(
                        jogo.home_team, jogo.away_team, classificacao)
                    analise["detalhes"]["ambas_marcam"] = AnalisadorEstatistico.calcular_probabilidade_ambas_marcam(
                        jogo.home_team, jogo.away_team, classificacao)
                jogo.set_analise(analise)
                if jogo.status not in ["FINISHED", "IN_PLAY"]:
                    jogos.append(jogo.to_dict())
        if jogos:
            self.gerenciador_completo.processar_e_enviar_alertas_completos(jogos, hoje)
    
    def conferir_resultados(self, data):
        hoje = data.strftime("%Y-%m-%d")
        for tipo, path in [("over_under", ConfigManager.ALERTAS_PATH), ("favorito", ConfigManager.ALERTAS_FAVORITOS_PATH),
                           ("gols_ht", ConfigManager.ALERTAS_GOLS_HT_PATH), ("ambas_marcam", ConfigManager.ALERTAS_AMBAS_MARCAM_PATH)]:
            alertas = DataStorage.carregar_json(path)
            for fid, a in alertas.items():
                if a.get("data_busca") == hoje and not a.get("conferido", False):
                    match = self.api_client.obter_detalhes_jogo(fid)
                    if match and match.get("strStatus") == "Match Finished":
                        a["conferido"] = True
                        a["home_goals"] = int(match.get("intHomeScore", 0) or 0)
                        a["away_goals"] = int(match.get("intAwayScore", 0) or 0)
            DataStorage.salvar_json(path, alertas)


# =============================
# INTERFACE STREAMLIT
# =============================

def main():
    st.set_page_config(page_title="⚽ Sistema de Alertas", layout="wide")
    st.title("⚽ Sistema de Alertas de Futebol")
    
    sistema = SistemaAlertasFutebol()
    
    with st.sidebar:
        st.header("🔔 Configurações")
        tipo_analise = st.selectbox("Tipo de Análise", ["Over/Under de Gols", "Favorito (Vitória)", "Gols HT", "Ambas Marcam"])
        
        config = {}
        if tipo_analise == "Over/Under de Gols":
            config = {"min_conf": st.slider("Confiança Mínima", 50, 95, 70), "tipo_filtro": st.selectbox("Filtro", ["Todos", "Apenas Over", "Apenas Under"])}
        elif tipo_analise == "Favorito (Vitória)":
            config = {"min_conf_vitoria": st.slider("Confiança Mínima", 50, 95, 65)}
        
        alerta_individual = st.checkbox("Alertas Individuais", True)
        alerta_poster = st.checkbox("Alertas com Poster", True)
        alerta_top = st.checkbox("Top Jogos", True)
        top_n = st.selectbox("Quantidade", [3, 5, 10])
        formato = st.selectbox("Formato", ["Ambos", "Texto", "Poster"])
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar", "📊 Resultados", "🏆 TOP", "⚽ Completos"])
    
    with tab1:
        data = st.date_input("Data", datetime.today())
        todas = st.checkbox("Todas as ligas", True)
        if not todas:
            ligas = st.multiselect("Ligas", list(ConfigManager.LIGA_DICT.keys()))
        if st.button("Buscar"):
            sistema.processar_jogos(data, ligas if not todas else [], todas, top_n, config.get("min_conf", 70),
                                    config.get("max_conf", 95), "West Ham", alerta_individual, alerta_poster,
                                    alerta_top, formato, "Todos", tipo_analise, config)
    
    with tab2:
        data_res = st.date_input("Data para conferência", datetime.today())
        if st.button("Conferir"):
            sistema.conferir_resultados(data_res)
    
    with tab3:
        data_top = st.date_input("Data TOP", datetime.today())
        if st.button("Conferir TOP"):
            sistema.resultados_top.conferir_resultados_top_alertas(data_top)
    
    with tab4:
        data_comp = st.date_input("Data Completa", datetime.today())
        todas_comp = st.checkbox("Todas as ligas", True, key="comp_todas")
        if not todas_comp:
            ligas_comp = st.multiselect("Ligas", list(ConfigManager.LIGA_DICT.keys()), key="comp_ligas")
        if st.button("Gerar Alertas Completos"):
            sistema.processar_alertas_completos(data_comp, ligas_comp if not todas_comp else [], todas_comp)


if __name__ == "__main__":
    main()
