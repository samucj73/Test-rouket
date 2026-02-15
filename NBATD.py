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
# CLASSES PRINCIPAIS - CORE SYSTEM
# =============================

class ConfigManager:
    """Gerencia configurações e constantes do sistema"""
    
    API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","8351165117:AAFmqb3NrPsmT86_8C360eYzK71Qda1ah_4")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
    TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
    
    HEADERS = {"X-Auth-Token": API_KEY}
    BASE_URL_FD = "https://api.football-data.org/v4"
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
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
    
    # Dicionário de Ligas
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
    
    @classmethod
    def get_liga_id(cls, liga_nome):
        """Obtém o ID da liga a partir do nome"""
        return cls.LIGA_DICT.get(liga_nome)

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

class SmartCache:
    """Cache inteligente com TTL e tamanho máximo"""
    def __init__(self, cache_type: str):
        self.cache = {}
        self.timestamps = {}
        self.config = ConfigManager.CACHE_CONFIG.get(cache_type, {"ttl": 3600, "max_size": 100})
        self.lock = threading.Lock()
        
    def get(self, key: str):
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
    
    def set(self, key: str, value):
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

class ImageCache:
    """Cache especializado para imagens (escudos dos times)"""
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
        """Obtém escudo do cache"""
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
        if not crest_url or not img_bytes:
            return
            
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
        import hashlib
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
    
    def get_stats(self):
        """Retorna estatísticas do cache"""
        with self.lock:
            cache_dir_size = 0
            if os.path.exists(self.cache_dir):
                for file in os.listdir(self.cache_dir):
                    try:
                        cache_dir_size += os.path.getsize(os.path.join(self.cache_dir, file))
                    except:
                        pass
            
            return {
                "memoria": len(self.cache),
                "max_memoria": self.max_size,
                "disco_mb": cache_dir_size / (1024*1024) if cache_dir_size > 0 else 0,
                "hit_rate": f"{(len(self.cache) / max(self.max_size, 1)) * 100:.1f}%"
            }

# =============================
# CLASSES DE PERSISTÊNCIA
# =============================

class DataStorage:
    """Gerencia armazenamento e recuperação de dados"""
    
    @staticmethod
    def _serialize_for_json(obj):
        """Converte objetos datetime para strings ISO para serialização JSON"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: DataStorage._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DataStorage._serialize_for_json(item) for item in obj]
        return obj
    
    @staticmethod
    def carregar_json(caminho: str) -> dict:
        """Carrega JSON do arquivo"""
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
                    else:
                        if agora - os.path.getmtime(caminho) > ConfigManager.CACHE_TIMEOUT:
                            return {}
                return dados
        except (json.JSONDecodeError, IOError, Exception) as e:
            logging.error(f"Erro ao carregar {caminho}: {e}")
            st.error(f"Erro ao carregar {caminho}: {e}")
        return {}
    
    @staticmethod
    def salvar_json(caminho: str, dados: dict):
        """Salva dados no arquivo JSON"""
        try:
            dados_serializados = DataStorage._serialize_for_json(dados)
            
            if caminho in [ConfigManager.CACHE_JOGOS, ConfigManager.CACHE_CLASSIFICACAO]:
                if isinstance(dados_serializados, dict):
                    dados_serializados['_timestamp'] = datetime.now().timestamp()
            
            with open(caminho, "w", encoding='utf-8') as f:
                json.dump(dados_serializados, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logging.error(f"Erro ao salvar {caminho}: {e}")
            st.error(f"Erro ao salvar {caminho}: {e}")
    
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
    
    @staticmethod
    def carregar_historico() -> list:
        if os.path.exists(ConfigManager.HISTORICO_PATH):
            try:
                with open(ConfigManager.HISTORICO_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erro ao carregar histórico: {e}")
                return []
        return []
    
    @staticmethod
    def salvar_historico(historico: list):
        try:
            with open(ConfigManager.HISTORICO_PATH, "w", encoding="utf-8") as f:
                json.dump(historico, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erro ao salvar histórico: {e}")
            st.error(f"Erro ao salvar histórico: {e}")

# =============================
# CLASSES DE MODELOS DE DADOS
# =============================

class Jogo:
    """Representa um jogo de futebol com todos os dados relevantes"""
    
    def __init__(self, match_data: dict):
        self.id = match_data.get("id")
        self.home_team = match_data.get("homeTeam", {}).get("name", "")
        self.away_team = match_data.get("awayTeam", {}).get("name", "")
        self.utc_date = match_data.get("utcDate")
        self.status = match_data.get("status", "DESCONHECIDO")
        self.competition = match_data.get("competition", {}).get("name", "Desconhecido")
        
        self.home_crest = match_data.get("homeTeam", {}).get("crest") or match_data.get("homeTeam", {}).get("logo", "")
        self.away_crest = match_data.get("awayTeam", {}).get("crest") or match_data.get("awayTeam", {}).get("logo", "")
        
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
        required_fields = [self.id, self.home_team, self.away_team, self.utc_date]
        return all(required_fields)
    
    def get_data_hora_brasilia(self):
        if not self.utc_date:
            return "Data inválida", "Hora inválida"
        try:
            if self.utc_date.endswith('Z'):
                data_utc = datetime.fromisoformat(self.utc_date.replace('Z', '+00:00'))
            else:
                data_utc = datetime.fromisoformat(self.utc_date)
            if data_utc.tzinfo is None:
                data_utc = data_utc.replace(tzinfo=timezone.utc)
            fuso_brasilia = timezone(timedelta(hours=-3))
            data_brasilia = data_utc.astimezone(fuso_brasilia)
            return data_brasilia.strftime("%d/%m/%Y"), data_brasilia.strftime("%H:%M")
        except ValueError as e:
            logging.error(f"Erro ao formatar data {self.utc_date}: {e}")
            return "Data inválida", "Hora inválida"
    
    def get_hora_brasilia_datetime(self):
        if not self.utc_date:
            return datetime.now()
        try:
            if self.utc_date.endswith('Z'):
                data_utc = datetime.fromisoformat(self.utc_date.replace('Z', '+00:00'))
            else:
                data_utc = datetime.fromisoformat(self.utc_date)
            if data_utc.tzinfo is None:
                data_utc = data_utc.replace(tzinfo=timezone.utc)
            fuso_brasilia = timezone(timedelta(hours=-3))
            return data_utc.astimezone(fuso_brasilia)
        except Exception as e:
            logging.error(f"Erro ao converter data {self.utc_date}: {e}")
            return datetime.now()
    
    def set_analise(self, analise: dict):
        self.tendencia = analise.get("tendencia", "")
        self.estimativa = analise.get("estimativa", 0.0)
        self.probabilidade = analise.get("probabilidade", 0.0)
        self.confianca = analise.get("confianca", 0.0)
        self.tipo_aposta = analise.get("tipo_aposta", "")
        self.detalhes_analise = analise.get("detalhes", {})
        
        if "vitoria" in analise.get("detalhes", {}):
            vitoria_analise = analise["detalhes"]["vitoria"]
            self.favorito = vitoria_analise.get("favorito", "")
            self.confianca_vitoria = vitoria_analise.get("confianca_vitoria", 0.0)
            self.prob_home_win = vitoria_analise.get("home_win", 0.0)
            self.prob_away_win = vitoria_analise.get("away_win", 0.0)
            self.prob_draw = vitoria_analise.get("draw", 0.0)
        
        if "gols_ht" in analise.get("detalhes", {}):
            ht_analise = analise["detalhes"]["gols_ht"]
            self.tendencia_ht = ht_analise.get("tendencia_ht", "")
            self.confianca_ht = ht_analise.get("confianca_ht", 0.0)
            self.estimativa_total_ht = ht_analise.get("estimativa_total_ht", 0.0)
        
        if "ambas_marcam" in analise.get("detalhes", {}):
            ambas_marcam_analise = analise["detalhes"]["ambas_marcam"]
            self.tendencia_ambas_marcam = ambas_marcam_analise.get("tendencia_ambas_marcam", "")
            self.confianca_ambas_marcam = ambas_marcam_analise.get("confianca_ambas_marcam", 0.0)
            self.prob_ambas_marcam_sim = ambas_marcam_analise.get("sim", 0.0)
            self.prob_ambas_marcam_nao = ambas_marcam_analise.get("nao", 0.0)
    
    def set_resultado(self, home_goals: int, away_goals: int, ht_home_goals: int = None, ht_away_goals: int = None):
        self.home_goals = home_goals
        self.away_goals = away_goals
        self.ht_home_goals = ht_home_goals
        self.ht_away_goals = ht_away_goals
        self.conferido = True
        
        total_gols = home_goals + away_goals
        self.resultado = self.calcular_resultado_over_under(total_gols)
        self.resultado_favorito = self.calcular_resultado_favorito(home_goals, away_goals)
        if ht_home_goals is not None and ht_away_goals is not None:
            self.resultado_ht = self.calcular_resultado_gols_ht(ht_home_goals, ht_away_goals)
        self.resultado_ambas_marcam = self.calcular_resultado_ambas_marcam(home_goals, away_goals)
    
    def calcular_resultado_over_under(self, total_gols: float) -> str:
        if "OVER" in self.tendencia.upper():
            if "OVER 1.5" in self.tendencia and total_gols > 1.5:
                return "GREEN"
            elif "OVER 2.5" in self.tendencia and total_gols > 2.5:
                return "GREEN"
            elif "OVER 3.5" in self.tendencia and total_gols > 3.5:
                return "GREEN"
            elif "OVER 4.5" in self.tendencia and total_gols > 4.5:
                return "GREEN"
        elif "UNDER" in self.tendencia.upper():
            if "UNDER 1.5" in self.tendencia and total_gols < 1.5:
                return "GREEN"
            elif "UNDER 2.5" in self.tendencia and total_gols < 2.5:
                return "GREEN"
            elif "UNDER 3.5" in self.tendencia and total_gols < 3.5:
                return "GREEN"
            elif "UNDER 4.5" in self.tendencia and total_gols < 4.5:
                return "GREEN"
        return "RED"
    
    def calcular_resultado_favorito(self, home_goals: int, away_goals: int) -> str:
        if self.favorito == "home" and home_goals > away_goals:
            return "GREEN"
        elif self.favorito == "away" and away_goals > home_goals:
            return "GREEN"
        elif self.favorito == "draw" and home_goals == away_goals:
            return "GREEN"
        return "RED"
    
    def calcular_resultado_gols_ht(self, ht_home_goals: int, ht_away_goals: int) -> str:
        total_gols_ht = ht_home_goals + ht_away_goals
        if self.tendencia_ht == "OVER 0.5 HT" and total_gols_ht > 0.5:
            return "GREEN"
        elif self.tendencia_ht == "UNDER 0.5 HT" and total_gols_ht < 0.5:
            return "GREEN"
        elif self.tendencia_ht == "OVER 1.5 HT" and total_gols_ht > 1.5:
            return "GREEN"
        elif self.tendencia_ht == "UNDER 1.5 HT" and total_gols_ht < 1.5:
            return "RED"
        return "RED"
    
    def calcular_resultado_ambas_marcam(self, home_goals: int, away_goals: int) -> str:
        if self.tendencia_ambas_marcam == "SIM" and home_goals > 0 and away_goals > 0:
            return "GREEN"
        elif self.tendencia_ambas_marcam == "NÃO" and (home_goals == 0 or away_goals == 0):
            return "GREEN"
        return "RED"
    
    def to_dict(self):
        data_dict = {
            "id": self.id,
            "home": self.home_team,
            "away": self.away_team,
            "tendencia": self.tendencia,
            "estimativa": self.estimativa,
            "probabilidade": self.probabilidade,
            "confianca": self.confianca,
            "tipo_aposta": self.tipo_aposta,
            "liga": self.competition,
            "hora": self.get_hora_brasilia_datetime().isoformat(),
            "status": self.status,
            "escudo_home": self.home_crest,
            "escudo_away": self.away_crest,
            "detalhes": self.detalhes_analise,
            "conferido": self.conferido,
            "resultado": self.resultado,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "ht_home_goals": self.ht_home_goals,
            "ht_away_goals": self.ht_away_goals,
            "resultado_favorito": self.resultado_favorito,
            "resultado_ht": self.resultado_ht,
            "resultado_ambas_marcam": self.resultado_ambas_marcam
        }
        if self.favorito:
            data_dict.update({
                "favorito": self.favorito,
                "confianca_vitoria": self.confianca_vitoria,
                "prob_home_win": self.prob_home_win,
                "prob_away_win": self.prob_away_win,
                "prob_draw": self.prob_draw,
            })
        if self.tendencia_ht:
            data_dict.update({
                "tendencia_ht": self.tendencia_ht,
                "confianca_ht": self.confianca_ht,
                "estimativa_total_ht": self.estimativa_total_ht,
            })
        if self.tendencia_ambas_marcam:
            data_dict.update({
                "tendencia_ambas_marcam": self.tendencia_ambas_marcam,
                "confianca_ambas_marcam": self.confianca_ambas_marcam,
                "prob_ambas_marcam_sim": self.prob_ambas_marcam_sim,
                "prob_ambas_marcam_nao": self.prob_ambas_marcam_nao,
            })
        return data_dict

class Alerta:
    def __init__(self, jogo: Jogo, data_busca: str, tipo_alerta: str = "over_under"):
        self.jogo = jogo
        self.data_busca = data_busca
        self.data_hora_busca = datetime.now()
        self.tipo_alerta = tipo_alerta
        self.conferido = False
        self.alerta_enviado = False
    
    def to_dict(self):
        alerta_dict = {
            "id": self.jogo.id,
            "home": self.jogo.home_team,
            "away": self.jogo.away_team,
            "liga": self.jogo.competition,
            "hora": self.jogo.get_hora_brasilia_datetime().isoformat(),
            "data_busca": self.data_busca,
            "data_hora_busca": self.data_hora_busca.isoformat(),
            "tipo_alerta": self.tipo_alerta,
            "conferido": self.conferido,
            "alerta_enviado": self.alerta_enviado,
            "escudo_home": self.jogo.home_crest,
            "escudo_away": self.jogo.away_crest
        }
        if self.tipo_alerta == "over_under":
            alerta_dict.update({
                "tendencia": self.jogo.tendencia,
                "estimativa": self.jogo.estimativa,
                "probabilidade": self.jogo.probabilidade,
                "confianca": self.jogo.confianca,
                "tipo_aposta": self.jogo.tipo_aposta
            })
        elif self.tipo_alerta == "favorito":
            alerta_dict.update({
                "favorito": self.jogo.favorito,
                "confianca_vitoria": self.jogo.confianca_vitoria,
                "prob_home_win": self.jogo.prob_home_win,
                "prob_away_win": self.jogo.prob_away_win,
                "prob_draw": self.jogo.prob_draw
            })
        elif self.tipo_alerta == "gols_ht":
            alerta_dict.update({
                "tendencia_ht": self.jogo.tendencia_ht,
                "confianca_ht": self.jogo.confianca_ht,
                "estimativa_total_ht": self.jogo.estimativa_total_ht
            })
        elif self.tipo_alerta == "ambas_marcam":
            alerta_dict.update({
                "tendencia_ambas_marcam": self.jogo.tendencia_ambas_marcam,
                "confianca_ambas_marcam": self.jogo.confianca_ambas_marcam,
                "prob_ambas_marcam_sim": self.jogo.prob_ambas_marcam_sim,
                "prob_ambas_marcam_nao": self.jogo.prob_ambas_marcam_nao
            })
        return alerta_dict

# =============================
# FUNÇÕES AUXILIARES
# =============================

def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

# =============================
# CLASSES DE ANÁLISE
# =============================

class AnalisadorEstatistico:
    @staticmethod
    def calcular_probabilidade_vitoria(home: str, away: str, classificacao: dict) -> dict:
        dados_home = classificacao.get(home, {
            "wins": 0, "draws": 0, "losses": 0,
            "played": 1, "scored": 0, "against": 0
        })
        dados_away = classificacao.get(away, {
            "wins": 0, "draws": 0, "losses": 0,
            "played": 1, "scored": 0, "against": 0
        })

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

        confianca_vitoria = max(prob_home, prob_away, prob_draw)

        return {
            "home_win": round(prob_home, 1),
            "away_win": round(prob_away, 1),
            "draw": round(prob_draw, 1),
            "favorito": favorito,
            "confianca_vitoria": round(confianca_vitoria, 1)
        }

    @staticmethod
    def calcular_probabilidade_gols_ht(home: str, away: str, classificacao: dict) -> dict:
        dados_home = classificacao.get(home, {"scored": 0, "played": 1})
        dados_away = classificacao.get(away, {"scored": 0, "played": 1})

        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)

        media_home = dados_home["scored"] / played_home
        media_away = dados_away["scored"] / played_away

        estimativa_total_ht = (media_home + media_away) * 0.45
        estimativa_total_ht = clamp(estimativa_total_ht, 0.2, 1.8)

        prob_over_05_ht = sigmoid((estimativa_total_ht - 0.5) * 3) * 100
        prob_over_15_ht = sigmoid((estimativa_total_ht - 1.2) * 3) * 100

        if estimativa_total_ht > 1.1:
            tendencia_ht = "OVER 1.5 HT"
        elif estimativa_total_ht > 0.6:
            tendencia_ht = "OVER 0.5 HT"
        else:
            tendencia_ht = "UNDER 0.5 HT"

        confianca_ht = clamp(max(prob_over_05_ht, prob_over_15_ht) * 0.85, 40, 85)

        return {
            "estimativa_total_ht": round(estimativa_total_ht, 2),
            "tendencia_ht": tendencia_ht,
            "confianca_ht": round(confianca_ht, 1),
            "over_05_ht": round(prob_over_05_ht, 1),
            "over_15_ht": round(prob_over_15_ht, 1)
        }

    @staticmethod
    def calcular_probabilidade_ambas_marcam(home: str, away: str, classificacao: dict) -> dict:
        dados_home = classificacao.get(home, {
            "scored": 0, "against": 0, "played": 1,
            "wins": 0, "draws": 0, "losses": 0
        })
        
        dados_away = classificacao.get(away, {
            "scored": 0, "against": 0, "played": 1,
            "wins": 0, "draws": 0, "losses": 0
        })

        played_home = max(dados_home["played"], 1)
        played_away = max(dados_away["played"], 1)

        taxa_gols_home = dados_home["scored"] / played_home
        taxa_gols_away = dados_away["scored"] / played_away
        
        taxa_sofridos_home = dados_home["against"] / played_home
        taxa_sofridos_away = dados_away["against"] / played_away
        
        taxa_marque_home = 1 / (1 + math.exp(-taxa_gols_home * 0.8))
        taxa_marque_away = 1 / (1 + math.exp(-taxa_gols_away * 0.8))
        
        taxa_sofra_home = 1 / (1 + math.exp(-taxa_sofridos_home * 0.8))
        taxa_sofra_away = 1 / (1 + math.exp(-taxa_sofridos_away * 0.8))

        prob_home_marca = (taxa_marque_home * 0.6 + taxa_sofra_away * 0.4)
        prob_away_marca = (taxa_marque_away * 0.4 + taxa_sofra_home * 0.6)

        fator_casa = 1.1
        prob_home_marca *= fator_casa
        prob_away_marca *= (2.0 - fator_casa) * 0.9

        prob_ambas_marcam = clamp(prob_home_marca * prob_away_marca * 100, 0, 95)
        prob_nao_ambas_marcam = 100 - prob_ambas_marcam

        if prob_ambas_marcam >= 60:
            tendencia_ambas_marcam = "SIM"
        elif prob_nao_ambas_marcam >= 60:
            tendencia_ambas_marcam = "NÃO"
        else:
            if prob_ambas_marcam >= prob_nao_ambas_marcam:
                tendencia_ambas_marcam = "SIM"
            else:
                tendencia_ambas_marcam = "NÃO"

        diferenca = abs(prob_ambas_marcam - prob_nao_ambas_marcam)
        confianca_ambas_marcam = clamp(50 + diferenca * 0.5, 55, 85)

        return {
            "sim": round(prob_ambas_marcam, 1),
            "nao": round(prob_nao_ambas_marcam, 1),
            "tendencia_ambas_marcam": tendencia_ambas_marcam,
            "confianca_ambas_marcam": round(confianca_ambas_marcam, 1),
            "prob_home_marca": round(prob_home_marca * 100, 1),
            "prob_away_marca": round(prob_away_marca * 100, 1),
            "taxa_gols_home": round(taxa_gols_home, 2),
            "taxa_gols_away": round(taxa_gols_away, 2),
            "taxa_sofridos_home": round(taxa_sofridos_home, 2),
            "taxa_sofridos_away": round(taxa_sofridos_away, 2)
        }

class AnalisadorTendencia:
    def __init__(self, classificacao: dict):
        self.classificacao = classificacao

    def calcular_tendencia_completa(self, home: str, away: str) -> dict:
        dados_home = self.classificacao.get(home, {})
        dados_away = self.classificacao.get(away, {})

        played_home = dados_home.get("played", 0)
        played_away = dados_away.get("played", 0)

        if played_home < 3 or played_away < 3:
            return {
                "tendencia": "DADOS INSUFICIENTES",
                "estimativa": 0,
                "probabilidade": 0,
                "confianca": 0,
                "tipo_aposta": "avoid",
                "linha_mercado": 0,
                "detalhes": {
                    "motivo": f"Jogos insuficientes: Home={played_home}, Away={played_away}"
                }
            }

        played_home = max(played_home, 1)
        played_away = max(played_away, 1)

        media_home_feitos = dados_home.get("scored", 0) / played_home
        media_home_sofridos = dados_home.get("against", 0) / played_home
        media_away_feitos = dados_away.get("scored", 0) / played_away
        media_away_sofridos = dados_away.get("against", 0) / played_away

        media_home_feitos = clamp(media_home_feitos, 0.6, 3.6)
        media_home_sofridos = clamp(media_home_sofridos, 0.6, 3.2)
        media_away_feitos = clamp(media_away_feitos, 0.6, 3.4)
        media_away_sofridos = clamp(media_away_sofridos, 0.6, 3.2)

        estimativa_total = (
            media_home_feitos * 0.55 +
            media_away_feitos * 0.55 +
            media_home_sofridos * 0.25 +
            media_away_sofridos * 0.25
        )

        fator_ofensivo_home = media_home_feitos / max(media_away_sofridos, 0.75)
        fator_ofensivo_away = media_away_feitos / max(media_home_sofridos, 0.75)
        fator_ataque = (fator_ofensivo_home + fator_ofensivo_away) / 2

        if fator_ataque >= 1.6:
            estimativa_total *= 1.12
        elif fator_ataque >= 1.35:
            estimativa_total *= 1.08
        elif fator_ataque <= 0.7:
            estimativa_total *= 0.92

        fator_casa = 1.06 + (media_home_feitos - media_home_sofridos) * 0.10
        fator_casa = clamp(fator_casa, 0.95, 1.18)
        estimativa_total *= fator_casa

        estimativa_total = (estimativa_total * 0.75) + (2.5 * 0.25)
        estimativa_total = clamp(estimativa_total, 1.3, 4.2)

        if estimativa_total <= 1.5:
            mercado = "UNDER 2.5"
            tipo_aposta = "under"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((2.5 - estimativa_total) * 1.3)

        elif estimativa_total <= 2.0:
            if fator_ataque < 0.9:
                mercado = "UNDER 2.5"
                tipo_aposta = "under"
                linha_mercado = 2.5
                probabilidade_base = sigmoid((2.5 - estimativa_total) * 1.2)
            else:
                mercado = "OVER 1.5"
                tipo_aposta = "over"
                linha_mercado = 1.5
                probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.5)

        elif estimativa_total >= 3.3:
            mercado = "OVER 3.5"
            tipo_aposta = "over"
            linha_mercado = 3.5
            probabilidade_base = sigmoid((estimativa_total - 3.5) * 1.0)

        elif estimativa_total >= 2.6:
            mercado = "OVER 2.5"
            tipo_aposta = "over"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((estimativa_total - 2.5) * 1.1)

        else:
            mercado = "OVER 1.5"
            tipo_aposta = "over"
            linha_mercado = 1.5
            probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.5)

        if tipo_aposta == "under" and estimativa_total > 1.85:
            return {
                "tendencia": "NÃO APOSTAR",
                "estimativa": round(estimativa_total, 2),
                "probabilidade": round(probabilidade_base * 100, 1),
                "confianca": 0,
                "tipo_aposta": "avoid",
                "linha_mercado": linha_mercado,
                "detalhes": {"motivo": "UNDER perigoso (estimativa alta)"}
            }

        if tipo_aposta == "over" and estimativa_total >= 2.75 and fator_ataque >= 1.2:
            mercado = "OVER 2.5"
            tipo_aposta = "over"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((estimativa_total - 2.5) * 1.15)

        distancia_linha = abs(estimativa_total - linha_mercado)

        base_conf = probabilidade_base * 50
        dist_conf = min(distancia_linha * 25, 30)

        consistencia = 0
        if played_home >= 5 and played_away >= 5:
            consistencia += 10
        if abs(media_home_feitos - media_away_feitos) < 1.0:
            consistencia += 5
        if fator_ataque > 1.3 or fator_ataque < 0.8:
            consistencia += 5

        confianca = clamp(base_conf + dist_conf + consistencia, 35, 75)

        if tipo_aposta == "over" and linha_mercado == 1.5:
            if media_home_feitos < 1.2 and media_away_feitos < 1.2:
                confianca *= 0.85

        if confianca < 45:
            return {
                "tendencia": "NÃO APOSTAR",
                "estimativa": round(estimativa_total, 2),
                "probabilidade": round(probabilidade_base * 100, 1),
                "confianca": round(confianca, 1),
                "tipo_aposta": "avoid",
                "linha_mercado": linha_mercado,
                "detalhes": {"motivo": f"Confiança baixa: {confianca:.1f}%"}
            }

        return {
            "tendencia": mercado,
            "estimativa": round(estimativa_total, 2),
            "probabilidade": round(probabilidade_base * 100, 1),
            "confianca": round(confianca, 1),
            "tipo_aposta": tipo_aposta,
            "linha_mercado": linha_mercado,
            "detalhes": {
                "fator_ataque": round(fator_ataque, 2),
                "distancia_linha": round(distancia_linha, 2),
                "played_home": played_home,
                "played_away": played_away,
                "motivo": "ALERTA CONFIRMADO"
            }
        }

# =============================
# CLASSE ResultadosTopAlertas (resumida por espaço, mas essencial)
# =============================

class ResultadosTopAlertas:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = sistema_principal.config
        self.poster_generator = sistema_principal.poster_generator
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client

    def conferir_resultados_top_alertas(self, data_selecionada):
        # Implementação completa (omitida por brevidade, mas deve ser mantida)
        pass

    def _agrupar_alertas_top_por_data_tipo(self, alertas_top, data_busca):
        # Implementação
        pass

    def _salvar_alertas_top_atualizados(self, alertas_top):
        pass

    def _processar_resultado_alerta(self, alerta, match_data, tipo_alerta):
        pass

    def _gerar_poster_para_grupo(self, jogos_conferidos, tipo_alerta, grupo_id, data_selecionada):
        pass

    def _mostrar_resumo_geral(self, alertas_por_grupo):
        pass

    def _mostrar_resultado_alerta_top(self, alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo):
        pass

    def _verificar_poster_valido(self, poster):
        pass

    def _enviar_resultados_como_texto(self, titulo, jogos_lista, greens, reds, taxa_acerto, tipo_alerta):
        pass

# =============================
# CLASSE AlertaCompleto e GerenciadorAlertasCompletos (resumido)
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
            "tendencia": jogo.tendencia,
            "estimativa": jogo.estimativa,
            "probabilidade": jogo.probabilidade,
            "confianca": jogo.confianca,
            "tipo_aposta": jogo.tipo_aposta
        }
        self.analise_favorito = {
            "favorito": jogo.favorito,
            "confianca_vitoria": jogo.confianca_vitoria,
            "prob_home_win": jogo.prob_home_win,
            "prob_away_win": jogo.prob_away_win,
            "prob_draw": jogo.prob_draw
        }
        self.analise_gols_ht = {
            "tendencia_ht": jogo.tendencia_ht,
            "confianca_ht": jogo.confianca_ht,
            "estimativa_total_ht": jogo.estimativa_total_ht
        }
        self.analise_ambas_marcam = {
            "tendencia_ambas_marcam": jogo.tendencia_ambas_marcam,
            "confianca_ambas_marcam": jogo.confianca_ambas_marcam,
            "prob_ambas_marcam_sim": jogo.prob_ambas_marcam_sim,
            "prob_ambas_marcam_nao": jogo.prob_ambas_marcam_nao
        }
        self.resultados = {
            "over_under": None,
            "favorito": None,
            "gols_ht": None,
            "ambas_marcam": None,
            "home_goals": None,
            "away_goals": None,
            "ht_home_goals": None,
            "ht_away_goals": None
        }

    def to_dict(self):
        return {
            "id": self.jogo.id,
            "home": self.jogo.home_team,
            "away": self.jogo.away_team,
            "liga": self.jogo.competition,
            "hora": self.jogo.get_hora_brasilia_datetime().isoformat(),
            "data_busca": self.data_busca,
            "data_hora_busca": self.data_hora_busca.isoformat(),
            "tipo_alerta": self.tipo_alerta,
            "conferido": self.conferido,
            "alerta_enviado": self.alerta_enviado,
            "escudo_home": self.jogo.home_crest,
            "escudo_away": self.jogo.away_crest,
            "analise_over_under": self.analise_over_under,
            "analise_favorito": self.analise_favorito,
            "analise_gols_ht": self.analise_gols_ht,
            "analise_ambas_marcam": self.analise_ambas_marcam,
            "resultados": self.resultados,
            "detalhes": self.jogo.detalhes_analise
        }

    def set_resultados(self, home_goals: int, away_goals: int, ht_home_goals: int = None, ht_away_goals: int = None):
        self.resultados["home_goals"] = home_goals
        self.resultados["away_goals"] = away_goals
        self.resultados["ht_home_goals"] = ht_home_goals
        self.resultados["ht_away_goals"] = ht_away_goals
        self.conferido = True

        total_gols = home_goals + away_goals
        tendencia = self.analise_over_under.get("tendencia", "")

        if "OVER" in tendencia.upper():
            if "OVER 1.5" in tendencia and total_gols > 1.5:
                self.resultados["over_under"] = "GREEN"
            elif "OVER 2.5" in tendencia and total_gols > 2.5:
                self.resultados["over_under"] = "GREEN"
            elif "OVER 3.5" in tendencia and total_gols > 3.5:
                self.resultados["over_under"] = "GREEN"
            elif "OVER 4.5" in tendencia and total_gols > 4.5:
                self.resultados["over_under"] = "GREEN"
            else:
                self.resultados["over_under"] = "RED"
        elif "UNDER" in tendencia.upper():
            if "UNDER 1.5" in tendencia and total_gols < 1.5:
                self.resultados["over_under"] = "GREEN"
            elif "UNDER 2.5" in tendencia and total_gols < 2.5:
                self.resultados["over_under"] = "GREEN"
            elif "UNDER 3.5" in tendencia and total_gols < 3.5:
                self.resultados["over_under"] = "GREEN"
            elif "UNDER 4.5" in tendencia and total_gols < 4.5:
                self.resultados["over_under"] = "GREEN"
            else:
                self.resultados["over_under"] = "RED"
        else:
            self.resultados["over_under"] = "RED"

        favorito = self.analise_favorito.get("favorito", "")
        if favorito == "home" and home_goals > away_goals:
            self.resultados["favorito"] = "GREEN"
        elif favorito == "away" and away_goals > home_goals:
            self.resultados["favorito"] = "GREEN"
        elif favorito == "draw" and home_goals == away_goals:
            self.resultados["favorito"] = "GREEN"
        else:
            self.resultados["favorito"] = "RED"

        if ht_home_goals is not None and ht_away_goals is not None:
            total_gols_ht = ht_home_goals + ht_away_goals
            tendencia_ht = self.analise_gols_ht.get("tendencia_ht", "")
            if tendencia_ht == "OVER 0.5 HT" and total_gols_ht > 0.5:
                self.resultados["gols_ht"] = "GREEN"
            elif tendencia_ht == "UNDER 0.5 HT" and total_gols_ht < 0.5:
                self.resultados["gols_ht"] = "GREEN"
            elif tendencia_ht == "OVER 1.5 HT" and total_gols_ht > 1.5:
                self.resultados["gols_ht"] = "GREEN"
            elif tendencia_ht == "UNDER 1.5 HT" and total_gols_ht < 1.5:
                self.resultados["gols_ht"] = "RED"
            else:
                self.resultados["gols_ht"] = "RED"

        tendencia_am = self.analise_ambas_marcam.get("tendencia_ambas_marcam", "")
        if tendencia_am == "SIM" and home_goals > 0 and away_goals > 0:
            self.resultados["ambas_marcam"] = "GREEN"
        elif tendencia_am == "NÃO" and (home_goals == 0 or away_goals == 0):
            self.resultados["ambas_marcam"] = "GREEN"
        else:
            self.resultados["ambas_marcam"] = "RED"

class GerenciadorAlertasCompletos:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = sistema_principal.config
        self.poster_generator = sistema_principal.poster_generator
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client
        self.ALERTAS_COMPLETOS_PATH = "alertas_completos.json"
        self.RESULTADOS_COMPLETOS_PATH = "resultados_completos.json"

    def salvar_alerta_completo(self, alerta: AlertaCompleto):
        alertas = self.carregar_alertas()
        chave = f"{alerta.jogo.id}_{alerta.data_busca}"
        alertas[chave] = alerta.to_dict()
        self._salvar_alertas(alertas)

    def carregar_alertas(self) -> dict:
        return DataStorage.carregar_json(self.ALERTAS_COMPLETOS_PATH)

    def _salvar_alertas(self, alertas: dict):
        DataStorage.salvar_json(self.ALERTAS_COMPLETOS_PATH, alertas)

    def carregar_resultados(self) -> dict:
        return DataStorage.carregar_json(self.RESULTADOS_COMPLETOS_PATH)

    def _salvar_resultados(self, resultados: dict):
        DataStorage.salvar_json(self.RESULTADOS_COMPLETOS_PATH, resultados)

    def processar_e_enviar_alertas_completos(self, jogos_analisados: list, data_busca: str):
        if not jogos_analisados:
            return
        alertas_criados = []
        jogos_para_poster = []
        for jogo_dict in jogos_analisados:
            jogo = Jogo({
                "id": jogo_dict["id"],
                "homeTeam": {"name": jogo_dict["home"], "crest": jogo_dict.get("escudo_home", "")},
                "awayTeam": {"name": jogo_dict["away"], "crest": jogo_dict.get("escudo_away", "")},
                "utcDate": jogo_dict.get("hora", ""),
                "competition": {"name": jogo_dict.get("liga", "")},
                "status": jogo_dict.get("status", "")
            })
            analise_completa = {
                "tendencia": jogo_dict.get("tendencia", ""),
                "estimativa": jogo_dict.get("estimativa", 0.0),
                "probabilidade": jogo_dict.get("probabilidade", 0.0),
                "confianca": jogo_dict.get("confianca", 0.0),
                "tipo_aposta": jogo_dict.get("tipo_aposta", ""),
                "detalhes": jogo_dict.get("detalhes", {})
            }
            jogo.set_analise(analise_completa)
            alerta = AlertaCompleto(jogo, data_busca)
            self.salvar_alerta_completo(alerta)
            alertas_criados.append(alerta)
            jogos_para_poster.append({
                "home": jogo.home_team,
                "away": jogo.away_team,
                "liga": jogo.competition,
                "hora": jogo.get_hora_brasilia_datetime(),
                "escudo_home": jogo.home_crest,
                "escudo_away": jogo.away_crest,
                "analise_over_under": alerta.analise_over_under,
                "analise_favorito": alerta.analise_favorito,
                "analise_gols_ht": alerta.analise_gols_ht,
                "analise_ambas_marcam": alerta.analise_ambas_marcam
            })
        if jogos_para_poster:
            poster = self.gerar_poster_completo(jogos_para_poster)
            data_str = datetime.now().strftime("%d/%m/%Y")
            caption = (
                f"<b>⚽ ALERTA COMPLETO - ALL IN ONE - {data_str}</b>\n\n"
                f"<b>📋 TOTAL: {len(jogos_para_poster)} JOGOS</b>\n"
                f"<b>📊 TODAS AS ANÁLISES EM UM ÚNICO POSTER</b>\n\n"
                f"<b>🎯 Over/Under | 🏆 Favorito | ⏰ Gols HT | 🤝 Ambas Marcam</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE COMPLETA</b>"
            )
            if self.telegram_client.enviar_foto(poster, caption=caption):
                for alerta in alertas_criados:
                    alerta.alerta_enviado = True
                    self.salvar_alerta_completo(alerta)
                st.success(f"✅ Poster completo enviado com {len(jogos_para_poster)} jogos!")
                return True
        return False

    def conferir_resultados_completos(self, data_selecionada):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.subheader(f"🏆 Conferindo Resultados Completos - {data_selecionada.strftime('%d/%m/%Y')}")
        alertas = self.carregar_alertas()
        if not alertas:
            st.warning("⚠️ Nenhum alerta completo salvo para conferência")
            return
        alertas_hoje = {k: v for k, v in alertas.items() if v.get("data_busca") == hoje and not v.get("conferido", False)}
        if not alertas_hoje:
            st.info(f"ℹ️ Nenhum alerta pendente para {hoje}")
            return
        st.info(f"🔍 Encontrados {len(alertas_hoje)} alertas completos para conferência")
        jogos_conferidos = []
        progress_bar = st.progress(0)
        for idx, (chave, alerta) in enumerate(alertas_hoje.items()):
            fixture_id = alerta.get("id")
            match_data = self.api_client.obter_detalhes_jogo(fixture_id)
            if not match_data:
                st.warning(f"⚠️ Não foi possível obter dados do jogo {alerta.get('home')} vs {alerta.get('away')}")
                continue
            status = match_data.get("status", "")
            if status == "FINISHED":
                score = match_data.get("score", {})
                full_time = score.get("fullTime", {})
                half_time = score.get("halfTime", {})
                home_goals = full_time.get("home", 0)
                away_goals = full_time.get("away", 0)
                ht_home_goals = half_time.get("home", 0)
                ht_away_goals = half_time.get("away", 0)
                jogo = Jogo({
                    "id": fixture_id,
                    "homeTeam": {"name": alerta.get("home", ""), "crest": alerta.get("escudo_home", "")},
                    "awayTeam": {"name": alerta.get("away", ""), "crest": alerta.get("escudo_away", "")},
                    "utcDate": alerta.get("hora", ""),
                    "competition": {"name": alerta.get("liga", "")},
                    "status": status
                })
                analise_completa = {
                    "tendencia": alerta.get("analise_over_under", {}).get("tendencia", ""),
                    "estimativa": alerta.get("analise_over_under", {}).get("estimativa", 0.0),
                    "probabilidade": alerta.get("analise_over_under", {}).get("probabilidade", 0.0),
                    "confianca": alerta.get("analise_over_under", {}).get("confianca", 0.0),
                    "tipo_aposta": alerta.get("analise_over_under", {}).get("tipo_aposta", ""),
                    "detalhes": alerta.get("detalhes", {})
                }
                jogo.set_analise(analise_completa)
                alerta_completo = AlertaCompleto(jogo, hoje)
                alerta_completo.analise_favorito = alerta.get("analise_favorito", {})
                alerta_completo.analise_gols_ht = alerta.get("analise_gols_ht", {})
                alerta_completo.analise_ambas_marcam = alerta.get("analise_ambas_marcam", {})
                alerta_completo.set_resultados(home_goals, away_goals, ht_home_goals, ht_away_goals)
                alertas[chave]["conferido"] = True
                alertas[chave]["resultados"] = alerta_completo.resultados
                jogos_conferidos.append({
                    "home": alerta.get("home", ""),
                    "away": alerta.get("away", ""),
                    "liga": alerta.get("liga", ""),
                    "hora": alerta.get("hora", ""),
                    "escudo_home": alerta.get("escudo_home", ""),
                    "escudo_away": alerta.get("escudo_away", ""),
                    "resultados": alerta_completo.resultados
                })
                greens = sum(1 for r in alerta_completo.resultados.values() if r == "GREEN")
                reds = sum(1 for r in alerta_completo.resultados.values() if r == "RED")
                st.write(f"🏆 {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
                st.write(f"   ✅ GREEN: {greens} | ❌ RED: {reds}")
            progress_bar.progress((idx + 1) / len(alertas_hoje))
        self._salvar_alertas(alertas)
        if jogos_conferidos:
            st.success(f"✅ {len(jogos_conferidos)} jogos conferidos! Enviando resultados...")
            poster = self.gerar_poster_resultados_completos(jogos_conferidos)
            total_greens = 0
            total_reds = 0
            for jogo in jogos_conferidos:
                resultados = jogo.get("resultados", {})
                for key in ['over_under', 'favorito', 'gols_ht', 'ambas_marcam']:
                    if resultados.get(key) == "GREEN":
                        total_greens += 1
                    elif resultados.get(key) == "RED":
                        total_reds += 1
            total_analises = len(jogos_conferidos) * 4
            taxa_acerto = (total_greens / total_analises * 100) if total_analises > 0 else 0
            caption = (
                f"<b>🏆 RESULTADOS COMPLETOS - {hoje}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {len(jogos_conferidos)}</b>\n"
                f"<b>📊 TOTAL DE ANÁLISES: {total_analises}</b>\n"
                f"<b>✅ GREEN: {total_greens}</b>\n"
                f"<b>❌ RED: {total_reds}</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM - RESULTADOS CONFIRMADOS</b>"
            )
            if self.telegram_client.enviar_foto(poster, caption=caption):
                st.success("📤 Resultados completos enviados!")
            self._mostrar_estatisticas_detalhadas(jogos_conferidos)

    def gerar_poster_completo(self, jogos: list) -> io.BytesIO:
        # Implementação resumida (deve ser igual à original)
        # ...
        return io.BytesIO()

    def gerar_poster_resultados_completos(self, jogos_com_resultados: list) -> io.BytesIO:
        # Implementação resumida
        # ...
        return io.BytesIO()

    def _mostrar_estatisticas_detalhadas(self, jogos_conferidos: list):
        st.markdown("---")
        st.subheader("📊 Estatísticas Detalhadas")
        stats = {
            "over_under": {"GREEN": 0, "RED": 0},
            "favorito": {"GREEN": 0, "RED": 0},
            "gols_ht": {"GREEN": 0, "RED": 0},
            "ambas_marcam": {"GREEN": 0, "RED": 0}
        }
        for jogo in jogos_conferidos:
            resultados = jogo.get("resultados", {})
            for key in stats.keys():
                if resultados.get(key) == "GREEN":
                    stats[key]["GREEN"] += 1
                elif resultados.get(key) == "RED":
                    stats[key]["RED"] += 1
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_ou = stats["over_under"]["GREEN"] + stats["over_under"]["RED"]
            if total_ou > 0:
                taxa_ou = (stats["over_under"]["GREEN"] / total_ou) * 100
                st.metric("⚽ Over/Under", f"{stats['over_under']['GREEN']}✅ {stats['over_under']['RED']}❌", f"{taxa_ou:.1f}%")
        with col2:
            total_fav = stats["favorito"]["GREEN"] + stats["favorito"]["RED"]
            if total_fav > 0:
                taxa_fav = (stats["favorito"]["GREEN"] / total_fav) * 100
                st.metric("🏆 Favoritos", f"{stats['favorito']['GREEN']}✅ {stats['favorito']['RED']}❌", f"{taxa_fav:.1f}%")
        with col3:
            total_ht = stats["gols_ht"]["GREEN"] + stats["gols_ht"]["RED"]
            if total_ht > 0:
                taxa_ht = (stats["gols_ht"]["GREEN"] / total_ht) * 100
                st.metric("⏰ Gols HT", f"{stats['gols_ht']['GREEN']}✅ {stats['gols_ht']['RED']}❌", f"{taxa_ht:.1f}%")
        with col4:
            total_am = stats["ambas_marcam"]["GREEN"] + stats["ambas_marcam"]["RED"]
            if total_am > 0:
                taxa_am = (stats["ambas_marcam"]["GREEN"] / total_am) * 100
                st.metric("🤝 Ambas Marcam", f"{stats['ambas_marcam']['GREEN']}✅ {stats['ambas_marcam']['RED']}❌", f"{taxa_am:.1f}%")

# =============================
# CLASSES DE COMUNICAÇÃO
# =============================

class APIClient:
    def __init__(self, rate_limiter: RateLimiter, api_monitor: APIMonitor):
        self.rate_limiter = rate_limiter
        self.api_monitor = api_monitor
        self.config = ConfigManager()
        self.jogos_cache = SmartCache("jogos")
        self.classificacao_cache = SmartCache("classificacao")
        self.match_cache = SmartCache("match_details")
        self.image_cache = ImageCache()

    def obter_dados_api_com_retry(self, url: str, timeout: int = 15, max_retries: int = 3) -> dict | None:
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                logging.info(f"🔗 Request {attempt+1}/{max_retries}: {url}")
                response = requests.get(url, headers=self.config.HEADERS, timeout=timeout)
                if response.status_code == 429:
                    self.api_monitor.log_request(False, True)
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logging.warning(f"⏳ Rate limit da API. Esperando {retry_after} segundos...")
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                self.api_monitor.log_request(True)
                return response.json()
            except requests.exceptions.Timeout:
                logging.error(f"⌛ Timeout na tentativa {attempt+1} para {url}")
                self.api_monitor.log_request(False)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
            except requests.RequestException as e:
                logging.error(f"❌ Erro na tentativa {attempt+1} para {url}: {e}")
                self.api_monitor.log_request(False)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    st.error(f"❌ Falha após {max_retries} tentativas: {e}")
                    return None
        return None

    def obter_dados_api(self, url: str, timeout: int = 15) -> dict | None:
        return self.obter_dados_api_com_retry(url, timeout, max_retries=3)

    def obter_classificacao(self, liga_id: str) -> dict:
        cached = self.classificacao_cache.get(liga_id)
        if cached:
            return cached
        url = f"{self.config.BASE_URL_FD}/competitions/{liga_id}/standings"
        data = self.obter_dados_api(url)
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

    def obter_jogos(self, liga_id: str, data: str) -> list:
        key = f"{liga_id}_{data}"
        cached = self.jogos_cache.get(key)
        if cached:
            return cached
        url = f"{self.config.BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        data_api = self.obter_dados_api(url)
        jogos = data_api.get("matches", []) if data_api else []
        self.jogos_cache.set(key, jogos)
        return jogos

    def obter_jogos_brasileirao(self, liga_id: str, data_hoje: str) -> list:
        data_amanha = (datetime.strptime(data_hoje, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        jogos_hoje = self.obter_jogos(liga_id, data_hoje)
        jogos_amanha = self.obter_jogos(liga_id, data_amanha)
        todos_jogos = jogos_hoje + jogos_amanha
        jogos_filtrados = []
        for match in todos_jogos:
            if not self.validar_dados_jogo(match):
                continue
            data_utc = match["utcDate"]
            hora_brasilia = self.formatar_data_iso_para_datetime(data_utc)
            data_brasilia = hora_brasilia.strftime("%Y-%m-%d")
            if data_brasilia == data_hoje:
                jogos_filtrados.append(match)
        return jogos_filtrados

    def obter_detalhes_jogo(self, fixture_id: str) -> dict | None:
        cached = self.match_cache.get(fixture_id)
        if cached:
            return cached
        url = f"{self.config.BASE_URL_FD}/matches/{fixture_id}"
        data = self.obter_dados_api(url)
        if data:
            self.match_cache.set(fixture_id, data)
        return data

    def baixar_escudo_time(self, team_name: str, crest_url: str) -> bytes | None:
        if not crest_url:
            return None
        cached = self.image_cache.get(team_name, crest_url)
        if cached:
            return cached
        try:
            response = requests.get(crest_url, timeout=10)
            response.raise_for_status()
            img_bytes = response.content
            self.image_cache.set(team_name, crest_url, img_bytes)
            return img_bytes
        except Exception as e:
            logging.error(f"Erro ao baixar escudo de {team_name}: {e}")
            return None

    @staticmethod
    def validar_dados_jogo(match: dict) -> bool:
        required_fields = ['id', 'homeTeam', 'awayTeam', 'utcDate']
        for field in required_fields:
            if field not in match:
                return False
        if 'name' not in match['homeTeam'] or 'name' not in match['awayTeam']:
            return False
        return True

    @staticmethod
    def formatar_data_iso_para_datetime(data_iso: str) -> datetime:
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
        except requests.RequestException as e:
            logging.error(f"Erro ao enviar para Telegram: {e}")
            st.error(f"Erro ao enviar para Telegram: {e}")
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
        except requests.RequestException as e:
            logging.error(f"Erro ao enviar foto para Telegram: {e}")
            st.error(f"Erro ao enviar foto para Telegram: {e}")
            return False

# =============================
# CLASSES DE GERAÇÃO DE POSTERS
# =============================

class PosterGenerator:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    @staticmethod
    def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
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
        except Exception:
            return ImageFont.load_default()

    def gerar_poster_westham_style(self, jogos: list, titulo: str = " ALERTA DE GOLS", tipo_alerta: str = "over_under") -> io.BytesIO:
        # Implementação completa omitida por brevidade, mas deve ser mantida
        LARGURA = 2000
        ALTURA_TOPO = 270
        ALTURA_POR_JOGO = 830
        PADDING = 80
        jogos_count = len(jogos)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING
        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)
        FONTE_TITULO = self.criar_fonte(90)
        FONTE_SUBTITULO = self.criar_fonte(65)
        FONTE_TIMES = self.criar_fonte(60)
        FONTE_VS = self.criar_fonte(55)
        FONTE_INFO = self.criar_fonte(50)
        FONTE_DETALHES = self.criar_fonte(50)
        FONTE_ANALISE = self.criar_fonte(50)
        try:
            titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
            titulo_w = titulo_bbox[2] - titulo_bbox[0]
            draw.text(((LARGURA - titulo_w) // 2, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
        except:
            draw.text((LARGURA//2 - 250, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
        draw.line([(LARGURA//4, 220), (3*LARGURA//4, 220)], fill=(255, 215, 0), width=6)
        y_pos = ALTURA_TOPO
        for idx, jogo in enumerate(jogos):
            x0, y0 = PADDING, y_pos
            x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
            if tipo_alerta == "over_under":
                cor_borda = (255, 215, 0) if jogo.get('tipo_aposta') == "over" else (100, 200, 255)
            elif tipo_alerta == "favorito":
                cor_borda = (255, 87, 34)
            elif tipo_alerta == "gols_ht":
                cor_borda = (76, 175, 80)
            elif tipo_alerta == "ambas_marcam":
                cor_borda = (155, 89, 182)
            else:
                cor_borda = (255, 215, 0)
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)
            liga_text = jogo['liga'].upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            if isinstance(jogo["hora"], datetime):
                data_text = jogo["hora"].strftime("%d.%m.%Y")
            else:
                data_text = str(jogo["hora"])
            try:
                data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
                data_w = data_bbox[2] - data_bbox[0]
                draw.text(((LARGURA - data_w) // 2, y0 + 130), data_text, font=FONTE_INFO, fill=(150, 200, 255))
            except:
                draw.text((LARGURA//2 - 150, y0 + 130), data_text, font=FONTE_INFO, fill=(150, 200, 255))
            TAMANHO_ESCUDO = 220
            TAMANHO_QUADRADO = 230
            ESPACO_ENTRE_ESCUDOS = 700
            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2
            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 250
            home_crest_url = jogo.get('escudo_home', '')
            away_crest_url = jogo.get('escudo_away', '')
            escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], home_crest_url) if home_crest_url else None
            escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], away_crest_url) if away_crest_url else None
            escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA") if escudo_home_bytes else None
            escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA") if escudo_away_bytes else None
            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])
            try:
                home_bbox = draw.textbbox((0, 0), jogo['home'], font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 50), jogo['home'], font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 50), jogo['home'], font=FONTE_TIMES, fill=(255, 255, 255))
            try:
                away_bbox = draw.textbbox((0, 0), jogo['away'], font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 50), jogo['away'], font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 50), jogo['away'], font=FONTE_TIMES, fill=(255, 255, 255))
            try:
                vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
                vs_w = vs_bbox[2] - vs_bbox[0]
                vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
                draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), "VS", font=FONTE_VS, fill=(255, 215, 0))
            except:
                vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 30
                draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), "VS", font=FONTE_VS, fill=(255, 215, 0))
            y_analysis = y_escudos + TAMANHO_QUADRADO + 150
            draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)
            if tipo_alerta == "over_under":
                textos_analise = [
                    f"{'📈' if jogo.get('tipo_aposta') == 'over' else '📉'} {jogo['tendencia']}",
                    f"Confiança: {jogo['confianca']:.0f}%",
                ]
                cores = [(255, 215, 0) if jogo.get('tipo_aposta') == 'over' else (100, 200, 255), (200, 200, 200)]
            elif tipo_alerta == "favorito":
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                textos_analise = [
                    f"🏆 FAVORITO: {favorito_text}",
                    f"Confiança: {jogo.get('confianca_vitoria', 0):.0f}%",
                ]
                cores = [(255, 87, 34), (200, 200, 200)]
            elif tipo_alerta == "gols_ht":
                textos_analise = [
                    f"⏰ {jogo.get('tendencia_ht', 'N/A')}",
                    f"Estimativa HT: {jogo.get('estimativa_total_ht', 0):.2f} gols",
                    f"Confiança: {jogo.get('confianca_ht', 0):.0f}%",
                ]
                cores = [(76, 175, 80), (200, 200, 200), (200, 200, 200)]
            elif tipo_alerta == "ambas_marcam":
                textos_analise = [
                    f"🤝 AMBAS MARCAM: {jogo.get('tendencia_ambas_marcam', 'N/A')}",
                    f"Confiança: {jogo.get('confianca_ambas_marcam', 0):.0f}%",
                ]
                cores = [(155, 89, 182), (200, 200, 200)]
            else:
                textos_analise = ["Informação não disponível"]
                cores = [(200, 200, 200)]
            for i, (text, cor) in enumerate(zip(textos_analise, cores)):
                try:
                    bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                    w = bbox[2] - bbox[0]
                    draw.text(((LARGURA - w) // 2, y_analysis + i * 80), text, font=FONTE_ANALISE, fill=cor)
                except:
                    draw.text((PADDING + 120, y_analysis + i * 80), text, font=FONTE_ANALISE, fill=cor)
            y_pos += ALTURA_POR_JOGO
        rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Elite Master System"
        try:
            rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_DETALHES)
            rodape_w = rodape_bbox[2] - rodape_bbox[0]
            draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
        except:
            draw.text((LARGURA//2 - 250, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True, quality=95)
        buffer.seek(0)
        return buffer

    def gerar_poster_resultados(self, jogos_com_resultados: list, tipo_alerta: str = "over_under") -> io.BytesIO:
        # Implementação resumida (igual à original)
        LARGURA = 2000
        ALTURA_TOPO = 330
        ALTURA_POR_JOGO = 800
        PADDING = 80
        jogos_count = len(jogos_com_resultados)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING
        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)
        FONTE_TITULO = self.criar_fonte(90)
        FONTE_SUBTITULO = self.criar_fonte(70)
        FONTE_TIMES = self.criar_fonte(65)
        FONTE_VS = self.criar_fonte(55)
        FONTE_INFO = self.criar_fonte(50)
        FONTE_DETALHES = self.criar_fonte(55)
        FONTE_ANALISE = self.criar_fonte(65)
        FONTE_RESULTADO = self.criar_fonte(76)
        FONTE_RESULTADO_BADGE = self.criar_fonte(65)

        if tipo_alerta == "over_under":
            titulo = " RESULTADOS OVER/UNDER"
        elif tipo_alerta == "favorito":
            titulo = " RESULTADOS FAVORITOS"
        elif tipo_alerta == "gols_ht":
            titulo = " RESULTADOS GOLS HT"
        elif tipo_alerta == "ambas_marcam":
            titulo = " RESULTADOS AMBAS MARCAM"
        else:
            titulo = " RESULTADOS"

        try:
            titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
            titulo_w = titulo_bbox[2] - titulo_bbox[0]
            draw.text(((LARGURA - titulo_w) // 2, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
        except:
            draw.text((LARGURA//2 - 250, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
        draw.line([(LARGURA//4, 220), (3*LARGURA//4, 220)], fill=(255, 215, 0), width=6)
        data_geracao = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        try:
            data_bbox = draw.textbbox((0, 0), data_geracao, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, 280), data_geracao, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 200, 280), data_geracao, font=FONTE_INFO, fill=(150, 200, 255))
        y_pos = ALTURA_TOPO
        for idx, jogo in enumerate(jogos_com_resultados):
            x0, y0 = PADDING, y_pos
            x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
            if tipo_alerta == "over_under":
                resultado = jogo.get("resultado", "PENDENTE")
                resultado_text = "GREEN" if resultado == "GREEN" else "RED" if resultado == "RED" else "PENDENTE"
            elif tipo_alerta == "favorito":
                resultado = jogo.get("resultado_favorito", "PENDENTE")
                resultado_text = "GREEN" if resultado == "GREEN" else "RED" if resultado == "RED" else "PENDENTE"
            elif tipo_alerta == "gols_ht":
                resultado = jogo.get("resultado_ht", "PENDENTE")
                resultado_text = "GREEN" if resultado == "GREEN" else "RED" if resultado == "RED" else "PENDENTE"
            elif tipo_alerta == "ambas_marcam":
                resultado = jogo.get("resultado_ambas_marcam", "PENDENTE")
                resultado_text = "GREEN" if resultado == "GREEN" else "RED" if resultado == "RED" else "PENDENTE"
            else:
                resultado_text = "PENDENTE"

            if resultado_text == "GREEN":
                cor_badge = (46, 204, 113)
                cor_borda = (46, 204, 113)
                cor_fundo = (30, 50, 40)
                cor_texto = (255, 255, 255)
            elif resultado_text == "RED":
                cor_badge = (231, 76, 60)
                cor_borda = (231, 76, 60)
                cor_fundo = (50, 30, 30)
                cor_texto = (255, 255, 255)
            else:
                cor_badge = (149, 165, 166)
                cor_borda = (149, 165, 166)
                cor_fundo = (35, 35, 35)
                cor_texto = (255, 255, 255)
            draw.rectangle([x0, y0, x1, y1], fill=cor_fundo, outline=cor_borda, width=4)
            badge_width = 250
            badge_height = 92
            badge_x = x0 + 50
            badge_y = y0 + 50
            draw.rectangle([badge_x, badge_y, badge_x + badge_width, badge_y + badge_height], fill=cor_badge, outline=cor_badge, width=2)
            try:
                badge_bbox = draw.textbbox((0, 0), resultado_text, font=FONTE_RESULTADO_BADGE)
                badge_text_w = badge_bbox[2] - badge_bbox[0]
                badge_text_h = badge_bbox[3] - badge_bbox[1]
                badge_text_x = badge_x + (badge_width - badge_text_w) // 2
                badge_text_y = badge_y + (badge_height - badge_text_h) // 2
                draw.text((badge_text_x, badge_text_y), resultado_text, font=FONTE_RESULTADO_BADGE, fill=cor_texto)
                draw.rectangle([badge_x-2, badge_y-2, badge_x + badge_width + 2, badge_y + badge_height + 2], outline=(255, 255, 255), width=1)
            except:
                draw.text((badge_x + 80, badge_y + 25), resultado_text, font=FONTE_RESULTADO_BADGE, fill=cor_texto)
            liga_text = jogo['liga'].upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            TAMANHO_ESCUDO = 200
            TAMANHO_QUADRADO = 225
            ESPACO_ENTRE_ESCUDOS = 700
            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2
            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 150
            home_crest_url = jogo.get('escudo_home', '')
            away_crest_url = jogo.get('escudo_away', '')
            escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], home_crest_url) if home_crest_url else None
            escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], away_crest_url) if away_crest_url else None
            escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA") if escudo_home_bytes else None
            escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA") if escudo_away_bytes else None
            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])
            home_text = jogo['home'][:12]
            away_text = jogo['away'][:12]
            try:
                home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 30), home_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 30), home_text, font=FONTE_TIMES, fill=(255, 255, 255))
            try:
                away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 30), away_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 30), away_text, font=FONTE_TIMES, fill=(255, 255, 255))
            resultado_text_score = f"{jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}"
            try:
                resultado_bbox = draw.textbbox((0, 0), resultado_text_score, font=FONTE_RESULTADO)
                resultado_w = resultado_bbox[2] - resultado_bbox[0]
                resultado_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - resultado_w) // 2
                draw.text((resultado_x, y_escudos + TAMANHO_QUADRADO//2 - 40), resultado_text_score, font=FONTE_RESULTADO, fill=(255, 255, 255))
            except:
                resultado_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                draw.text((resultado_x, y_escudos + TAMANHO_QUADRADO//2 - 40), resultado_text_score, font=FONTE_RESULTADO, fill=(255, 255, 255))
            if jogo.get('ht_home_goals') is not None and jogo.get('ht_away_goals') is not None:
                ht_text = f"HT: {jogo['ht_home_goals']} - {jogo['ht_away_goals']}"
                try:
                    ht_bbox = draw.textbbox((0, 0), ht_text, font=FONTE_INFO)
                    ht_w = ht_bbox[2] - ht_bbox[0]
                    ht_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - ht_w) // 2
                    draw.text((ht_x, y_escudos + TAMANHO_QUADRADO//2 + 40), ht_text, font=FONTE_INFO, fill=(200, 200, 200))
                except:
                    ht_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                    draw.text((ht_x, y_escudos + TAMANHO_QUADRADO//2 + 40), ht_text, font=FONTE_INFO, fill=(200, 200, 200))
            y_analysis = y_escudos + TAMANHO_QUADRADO + 120
            if tipo_alerta == "over_under":
                textos_analise = [
                    f"{'📈' if jogo.get('tipo_aposta') == 'over' else '📉'} {jogo['tendencia']} {'✅' if resultado == 'GREEN' else '❌' if resultado == 'RED' else ''}",
                    f"Estimativa: {jogo['estimativa']:.2f} gols | Resultado: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                    f"Probabilidade: {jogo['probabilidade']:.0f}% | Confiança: {jogo['confianca']:.0f}%",
                ]
            elif tipo_alerta == "favorito":
                favorito_emoji = "🏠" if jogo.get('favorito') == "home" else "✈️" if jogo.get('favorito') == "away" else "🤝"
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                textos_analise = [
                    f"{favorito_emoji} FAVORITO: {favorito_text} {'✅' if resultado == 'GREEN' else '❌' if resultado == 'RED' else ''}",
                    f"Confiança: {jogo.get('confianca_vitoria', 0):.0f}% | Resultado: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                    f"Prob. Casa: {jogo.get('prob_home_win', 0):.1f}% | Fora: {jogo.get('prob_away_win', 0):.1f}% | Empate: {jogo.get('prob_draw', 0):.1f}%",
                ]
            elif tipo_alerta == "gols_ht":
                textos_analise = [
                    f"⏰ {jogo.get('tendencia_ht', 'N/A')} {'✅' if resultado == 'GREEN' else '❌' if resultado == 'RED' else ''}",
                    f"Estimativa HT: {jogo.get('estimativa_total_ht', 0):.2f} gols | Resultado HT: {jogo.get('ht_home_goals', '?')} - {jogo.get('ht_away_goals', '?')}",
                    f"Confiança HT: {jogo.get('confianca_ht', 0):.0f}% | FT: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                ]
            elif tipo_alerta == "ambas_marcam":
                textos_analise = [
                    f"🤝 AMBAS MARCAM: {jogo.get('tendencia_ambas_marcam', 'N/A')} {'✅' if resultado == 'GREEN' else '❌' if resultado == 'RED' else ''}",
                    f"Probabilidade SIM: {jogo.get('prob_ambas_marcam_sim', 0):.1f}% | NÃO: {jogo.get('prob_ambas_marcam_nao', 0):.1f}%",
                    f"Confiança: {jogo.get('confianca_ambas_marcam', 0):.0f}% | Resultado: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                ]
            else:
                textos_analise = [f"Resultado: {resultado}"]
            for i, text in enumerate(textos_analise):
                try:
                    bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                    w = bbox[2] - bbox[0]
                    draw.text(((LARGURA - w) // 2, y_analysis + i * 80), text, font=FONTE_ANALISE, fill=(255, 255, 255))
                except:
                    draw.text((PADDING + 120, y_analysis + i * 80), text, font=FONTE_ANALISE, fill=(255, 255, 255))
            y_pos += ALTURA_POR_JOGO
        rodape_text = "ELITE MASTER SYSTEM - ANÁLISE PREDITIVA DE RESULTADOS"
        try:
            rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_DETALHES)
            rodape_w = rodape_bbox[2] - rodape_bbox[0]
            draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
        except:
            draw.text((LARGURA//2 - 300, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True, quality=95)
        buffer.seek(0)
        return buffer

    def _desenhar_escudo_quadrado(self, draw, img, logo_img, x, y, tamanho_quadrado, tamanho_escudo, team_name=""):
        draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(255, 255, 255), outline=(255, 255, 255))
        if logo_img is None:
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
            if team_name:
                iniciais = ''.join([palavra[0].upper() for palavra in team_name.split()[:2]])
                if len(iniciais) > 3:
                    iniciais = iniciais[:3]
            else:
                iniciais = "SEM"
            try:
                bbox = draw.textbbox((0, 0), iniciais, font=self.criar_fonte(50))
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))
            except:
                draw.text((x + 70, y + 90), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))
            return
        try:
            logo_img = logo_img.convert("RGBA")
            largura, altura = logo_img.size
            proporcao = largura / altura
            if proporcao > 1:
                nova_altura = tamanho_escudo
                nova_largura = int(tamanho_escudo * proporcao)
                if nova_largura > tamanho_escudo:
                    nova_largura = tamanho_escudo
                    nova_altura = int(tamanho_escudo / proporcao)
            else:
                nova_largura = tamanho_escudo
                nova_altura = int(tamanho_escudo / proporcao)
                if nova_altura > tamanho_escudo:
                    nova_altura = tamanho_escudo
                    nova_largura = int(tamanho_escudo * proporcao)
            imagem_redimensionada = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
            pos_x = x + (tamanho_quadrado - nova_largura) // 2
            pos_y = y + (tamanho_quadrado - nova_altura) // 2
            fundo = Image.new("RGBA", (tamanho_quadrado, tamanho_quadrado), (255, 255, 255, 255))
            fundo.paste(imagem_redimensionada, (pos_x - x, pos_y - y), imagem_redimensionada)
            img.paste(fundo, (x, y), fundo)
        except Exception as e:
            logging.error(f"Erro ao processar escudo de {team_name}: {e}")
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
            if team_name:
                iniciais = ''.join([palavra[0].upper() for palavra in team_name.split()[:2]])
                if len(iniciais) > 3:
                    iniciais = iniciais[:3]
            else:
                iniciais = "ERR"
            try:
                bbox = draw.textbbox((0, 0), iniciais, font=self.criar_fonte(50))
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))
            except:
                draw.text((x + 70, y + 90), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))

# =============================
# SISTEMA PRINCIPAL
# =============================

class SistemaAlertasFutebol:
    def __init__(self):
        self.config = ConfigManager()
        self.rate_limiter = RateLimiter()
        self.api_monitor = APIMonitor()
        self.api_client = APIClient(self.rate_limiter, self.api_monitor)
        self.telegram_client = TelegramClient()
        self.poster_generator = PosterGenerator(self.api_client)
        self.image_cache = self.api_client.image_cache
        self.resultados_top = ResultadosTopAlertas(self)
        self.gerenciador_completo = GerenciadorAlertasCompletos(self)
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('sistema_alertas.log'),
                logging.StreamHandler()
            ]
        )

    def processar_jogos(self, data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf, 
                       max_conf, estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                       formato_top_jogos, tipo_filtro, tipo_analise, config_analise):
        # Implementação completa (omitida por espaço, mas deve ser a original corrigida)
        pass

    def processar_alertas_completos(self, data_selecionada, ligas_selecionadas, todas_ligas):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        if todas_ligas:
            ligas_busca = list(self.config.LIGA_DICT.values())
            st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
        else:
            ligas_busca = [self.config.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
            st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

        st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
        
        jogos_analisados = []
        progress_bar = st.progress(0)
        total_ligas = len(ligas_busca)

        classificacoes = {}
        for liga_id in ligas_busca:
            classificacoes[liga_id] = self.api_client.obter_classificacao(liga_id)
        
        for i, liga_id in enumerate(ligas_busca):
            classificacao = classificacoes[liga_id]
            analisador = AnalisadorTendencia(classificacao)
            
            if liga_id == "BSA":
                jogos_data = self.api_client.obter_jogos_brasileirao(liga_id, hoje)
            else:
                jogos_data = self.api_client.obter_jogos(liga_id, hoje)

            for match_data in jogos_data:
                if not self.api_client.validar_dados_jogo(match_data):
                    continue
                
                jogo = Jogo(match_data)
                if not jogo.validar_dados():
                    continue
                
                analise = analisador.calcular_tendencia_completa(jogo.home_team, jogo.away_team)
                
                if classificacao:
                    vitoria_analise = AnalisadorEstatistico.calcular_probabilidade_vitoria(
                        jogo.home_team, jogo.away_team, classificacao
                    )
                    analise["detalhes"]["vitoria"] = vitoria_analise
                    
                    ht_analise = AnalisadorEstatistico.calcular_probabilidade_gols_ht(
                        jogo.home_team, jogo.away_team, classificacao
                    )
                    analise["detalhes"]["gols_ht"] = ht_analise
                    
                    ambas_marcam_analise = AnalisadorEstatistico.calcular_probabilidade_ambas_marcam(
                        jogo.home_team, jogo.away_team, classificacao
                    )
                    analise["detalhes"]["ambas_marcam"] = ambas_marcam_analise
                
                jogo.set_analise(analise)
                jogos_analisados.append(jogo.to_dict())
            
            progress_bar.progress((i + 1) / total_ligas)
        
        if jogos_analisados:
            st.write(f"📊 Total de jogos analisados: {len(jogos_analisados)}")
            jogos_filtrados = [j for j in jogos_analisados 
                              if j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
            if jogos_filtrados:
                st.write(f"✅ Jogos elegíveis para alerta: {len(jogos_filtrados)}")
                self.gerenciador_completo.processar_e_enviar_alertas_completos(jogos_filtrados, hoje)
            else:
                st.warning("⚠️ Nenhum jogo elegível para alerta completo")
        else:
            st.warning("⚠️ Nenhum jogo encontrado")

    def conferir_resultados(self, data_selecionada):
        # Implementação
        pass

    def _conferir_resultados_tipo(self, tipo_alerta: str, data_busca: str) -> dict:
        # Implementação
        return {}

    def _enviar_alertas_resultados_automaticos(self, resultados_totais: dict, data_selecionada):
        pass

    def _enviar_resumo_final(self, tipo_alerta: str, jogos_lista: list, data_str: str):
        pass

    def _verificar_enviar_alerta(self, jogo: Jogo, match_data: dict, analise: dict, alerta_individual: bool, min_conf: int, max_conf: int, tipo_alerta: str):
        pass

    def _enviar_alerta_individual(self, fixture: dict, analise: dict, tipo_alerta: str, min_conf: int, max_conf: int):
        pass

    def _filtrar_por_tipo_analise(self, jogos, tipo_analise, config):
        return jogos

    def _enviar_top_jogos(self, jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf, formato_top_jogos, data_busca, tipo_alerta="over_under"):
        pass

    def _salvar_alerta_top(self, alerta: Alerta):
        pass

    def _enviar_alerta_westham_style(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
        pass

    def _enviar_alerta_poster_original(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
        pass

    def _limpar_alertas_top_antigos(self):
        alertas_top = DataStorage.carregar_alertas_top()
        agora = datetime.now()
        alertas_filtrados = {}
        for chave, alerta in alertas_top.items():
            if "data_busca" in alerta:
                try:
                    data_alerta = datetime.strptime(alerta["data_busca"], "%Y-%m-%d")
                    dias_diferenca = (agora - data_alerta).days
                    if dias_diferenca <= 7:
                        alertas_filtrados[chave] = alerta
                except:
                    alertas_filtrados[chave] = alerta
            else:
                continue
        DataStorage.salvar_alertas_top(alertas_filtrados)
        st.success(f"✅ Alertas TOP limpos: mantidos {len(alertas_filtrados)} de {len(alertas_top)}")

# =============================
# INTERFACE STREAMLIT
# =============================

def main():
    st.set_page_config(page_title="⚽ Sistema Completo de Alertas", layout="wide")
    st.title("⚽ Sistema Completo de Alertas de Futebol")
    
    sistema = SistemaAlertasFutebol()
    
    # Sidebar (mantida igual)
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        st.subheader("🎯 Tipo de Análise Principal")
        tipo_analise = st.selectbox(
            "Selecione o tipo de alerta:",
            ["Over/Under de Gols", "Favorito (Vitória)", "Gols HT (Primeiro Tempo)", "Ambas Marcam (BTTS)"],
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
        elif tipo_analise == "Ambas Marcam (BTTS)":
            min_conf_am = st.slider("Confiança Mínima Ambas Marcam (%)", 50, 95, 60, 1)
            filtro_am = st.selectbox("Filtrar Ambas Marcam:", ["Todos", "SIM", "NÃO"], index=0)
            config_analise = {"min_conf_am": min_conf_am, "filtro_am": filtro_am}
        
        st.subheader("📨 Tipos de Envio")
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True)
        alerta_poster = st.checkbox("📊 Alertas com Poster", value=True)
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True)
        alerta_conferencia_auto = st.checkbox("🤖 Alerta Auto Conferência", value=True)
        alerta_resultados = st.checkbox("🏁 Alertas de Resultados", value=True)
        formato_top_jogos = st.selectbox("📋 Formato do Top Jogos", ["Ambos", "Texto", "Poster"], index=0)
        st.markdown("----")
        st.header("Configurações Gerais")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        estilo_poster = st.selectbox("🎨 Estilo do Poster", ["West Ham (Novo)", "Elite Master (Original)"], index=0)
        st.markdown("----")
        st.info(f"Tipo de Análise: {tipo_analise}")
        if tipo_analise == "Over/Under de Gols":
            st.info(f"Intervalo de confiança: {min_conf}% a {max_conf}%")
            st.info(f"Filtro: {tipo_filtro}")
        elif tipo_analise == "Favorito (Vitória)":
            st.info(f"Confiança Mínima: {config_analise.get('min_conf_vitoria', 65)}%")
            st.info(f"Filtro Favorito: {config_analise.get('filtro_favorito', 'Todos')}")
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            st.info(f"Confiança Mínima: {config_analise.get('min_conf_ht', 60)}%")
            st.info(f"Tipo HT: {config_analise.get('tipo_ht', 'OVER 0.5 HT')}")
        elif tipo_analise == "Ambas Marcam (BTTS)":
            st.info(f"Confiança Mínima: {config_analise.get('min_conf_am', 60)}%")
            st.info(f"Filtro Ambas Marcam: {config_analise.get('filtro_am', 'Todos')}")
        st.info(f"Formato Top Jogos: {formato_top_jogos}")
        if alerta_conferencia_auto:
            st.info("🤖 Alerta automático: ATIVADO")
        if alerta_resultados:
            st.info("🏁 Alertas de resultados: ATIVADO")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar Partidas", "📊 Conferir Resultados", "🏆 Resultados TOP Alertas", "⚽ Alertas Completos"])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today(), key="data_busca")
        with col2:
            todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_busca")
        ligas_selecionadas = []
        if not todas_ligas:
            ligas_selecionadas = st.multiselect(
                "📌 Selecionar ligas:",
                options=list(ConfigManager.LIGA_DICT.keys()),
                default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"],
                key="ligas_busca"
            )
            if not ligas_selecionadas:
                st.warning("⚠️ Selecione pelo menos uma liga")
        if st.button("🔍 Buscar Partidas", type="primary", key="btn_buscar"):
            if not todas_ligas and not ligas_selecionadas:
                st.error("❌ Selecione pelo menos uma liga ou marque 'Todas as ligas'")
            else:
                sistema.processar_jogos(data_selecionada, ligas_selecionadas, todas_ligas, top_n, 
                                      config_analise.get("min_conf", 70) if tipo_analise == "Over/Under de Gols" else 70,
                                      config_analise.get("max_conf", 95) if tipo_analise == "Over/Under de Gols" else 95,
                                      estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                                      formato_top_jogos, tipo_filtro if tipo_analise == "Over/Under de Gols" else "Todos",
                                      tipo_analise, config_analise)
    
    with tab2:
        st.subheader("📊 Conferência de Resultados")
        col_data, col_btn = st.columns([2, 1])
        with col_data:
            data_resultados = st.date_input("📅 Data para conferência:", value=datetime.today(), key="data_resultados")
        with col_btn:
            if st.button("🔄 Conferir Resultados", type="primary", key="btn_conferir"):
                sistema.conferir_resultados(data_resultados)
        st.markdown("---")
        st.subheader("📈 Estatísticas dos Alertas")
        col_ou, col_fav, col_ht, col_am = st.columns(4)
        with col_ou:
            alertas_ou = DataStorage.carregar_alertas()
            resultados_ou = DataStorage.carregar_resultados()
            st.metric("⚽ Over/Under", f"{len(alertas_ou)} alertas", f"{sum(1 for a in alertas_ou.values() if a.get('conferido', False))} conferidos")
        with col_fav:
            alertas_fav = DataStorage.carregar_alertas_favoritos()
            st.metric("🏆 Favoritos", f"{len(alertas_fav)} alertas", f"{sum(1 for a in alertas_fav.values() if a.get('conferido', False))} conferidos")
        with col_ht:
            alertas_ht = DataStorage.carregar_alertas_gols_ht()
            st.metric("⏰ Gols HT", f"{len(alertas_ht)} alertas", f"{sum(1 for a in alertas_ht.values() if a.get('conferido', False))} conferidos")
        with col_am:
            alertas_am = DataStorage.carregar_alertas_ambas_marcam()
            st.metric("🤝 Ambas Marcam", f"{len(alertas_am)} alertas", f"{sum(1 for a in alertas_am.values() if a.get('conferido', False))} conferidos")
    
    with tab3:
        st.subheader("🏆 Conferência de Resultados TOP Alertas")
        col_data_top, col_btn_top = st.columns([2, 1])
        with col_data_top:
            data_resultados_top = st.date_input("📅 Data para conferência TOP:", value=datetime.today(), key="data_resultados_top")
        with col_btn_top:
            if st.button("🏆 Conferir Resultados TOP", type="primary", key="btn_conferir_top"):
                sistema.resultados_top.conferir_resultados_top_alertas(data_resultados_top)
        st.markdown("---")
        st.subheader("📊 Estatísticas dos Alertas TOP")
        alertas_top = DataStorage.carregar_alertas_top()
        if alertas_top:
            col_top1, col_top2, col_top3, col_top4 = st.columns(4)
            top_ou = [a for a in alertas_top.values() if a.get("tipo_alerta") == "over_under"]
            top_fav = [a for a in alertas_top.values() if a.get("tipo_alerta") == "favorito"]
            top_ht = [a for a in alertas_top.values() if a.get("tipo_alerta") == "gols_ht"]
            top_am = [a for a in alertas_top.values() if a.get("tipo_alerta") == "ambas_marcam"]
            with col_top1:
                st.metric("⚽ TOP Over/Under", len(top_ou))
            with col_top2:
                st.metric("🏆 TOP Favoritos", len(top_fav))
            with col_top3:
                st.metric("⏰ TOP Gols HT", len(top_ht))
            with col_top4:
                st.metric("🤝 TOP Ambas Marcam", len(top_am))
            if st.button("🗑️ Limpar Alertas TOP Antigos", type="secondary"):
                sistema._limpar_alertas_top_antigos()
        else:
            st.info("ℹ️ Nenhum alerta TOP salvo ainda.")
    
    with tab4:
        st.subheader("⚽ Alertas Completos - ALL IN ONE")
        st.info("📊 Todas as análises (Over/Under, Favorito, Gols HT, Ambas Marcam) em um único poster por partida")
        col1, col2 = st.columns([2, 1])
        with col1:
            data_completa = st.date_input("📅 Data para análise completa:", value=datetime.today(), key="data_completa")
        with col2:
            todas_ligas_completa = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_completa")
        ligas_selecionadas_completa = []
        if not todas_ligas_completa:
            ligas_selecionadas_completa = st.multiselect(
                "📌 Selecionar ligas:",
                options=list(ConfigManager.LIGA_DICT.keys()),
                default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"],
                key="ligas_completa"
            )
            if not ligas_selecionadas_completa:
                st.warning("⚠️ Selecione pelo menos uma liga")
        if st.button("⚽ Gerar Alertas Completos", type="primary", key="btn_completo"):
            if not todas_ligas_completa and not ligas_selecionadas_completa:
                st.error("❌ Selecione pelo menos uma liga ou marque 'Todas as ligas'")
            else:
                sistema.processar_alertas_completos(data_completa, ligas_selecionadas_completa, todas_ligas_completa)
        st.markdown("---")
        st.subheader("📊 Conferir Resultados Completos")
        col_data_comp, col_btn_comp = st.columns([2, 1])
        with col_data_comp:
            data_resultados_comp = st.date_input("📅 Data para conferência completa:", value=datetime.today(), key="data_resultados_comp")
        with col_btn_comp:
            if st.button("🔄 Conferir Resultados Completos", type="primary", key="btn_conferir_comp"):
                sistema.gerenciador_completo.conferir_resultados_completos(data_resultados_comp)
        st.markdown("---")
        st.subheader("📊 Estatísticas dos Alertas Completos")
        alertas_comp = sistema.gerenciador_completo.carregar_alertas()
        if alertas_comp:
            col_est1, col_est2, col_est3 = st.columns(3)
            with col_est1:
                st.metric("📋 Total Alertas", len(alertas_comp))
            with col_est2:
                st.metric("✅ Conferidos", sum(1 for a in alertas_comp.values() if a.get("conferido", False)))
            with col_est3:
                st.metric("📤 Enviados", sum(1 for a in alertas_comp.values() if a.get("alerta_enviado", False)))
            with st.expander("📋 Últimos Alertas Completos"):
                for chave, alerta in list(alertas_comp.items())[:5]:
                    st.write(f"⚽ {alerta.get('home', '')} vs {alerta.get('away', '')}")
                    st.write(f"   📅 {alerta.get('data_busca', '')} | 📤 Enviado: {alerta.get('alerta_enviado', False)}")
                    st.write(f"      ⚽ Over/Under: {alerta.get('analise_over_under', {}).get('tendencia', 'N/A')}")
                    st.write(f"      🏆 Favorito: {alerta.get('analise_favorito', {}).get('favorito', 'N/A')}")
                    st.write(f"      ⏰ Gols HT: {alerta.get('analise_gols_ht', {}).get('tendencia_ht', 'N/A')}")
                    st.write(f"      🤝 Ambas Marcam: {alerta.get('analise_ambas_marcam', {}).get('tendencia_ambas_marcam', 'N/A')}")
                    st.write("---")
        else:
            st.info("ℹ️ Nenhum alerta completo salvo ainda.")
    
    st.markdown("---")
    st.subheader("📊 Monitoramento da API")
    col_mon1, col_mon2, col_mon3, col_mon4 = st.columns(4)
    stats = sistema.api_monitor.get_stats()
    with col_mon1:
        st.metric("Total Requests", stats["total_requests"])
    with col_mon2:
        st.metric("Taxa de Sucesso", f"{stats['success_rate']}%")
    with col_mon3:
        st.metric("Requests/min", stats["requests_per_minute"])
    with col_mon4:
        st.metric("Rate Limit Hits", stats["rate_limit_hits"])


if __name__ == "__main__":
    main()
