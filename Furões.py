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
import statistics
from collections import defaultdict


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
    ALERTAS_COMPLETOS_PATH = "alertas_completos.json"
    RESULTADOS_COMPLETOS_PATH = "resultados_completos.json"
    
    MODELO_PERFORMANCE_PATH = "modelo_performance.json"
    
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
    def carregar_performance_modelo() -> dict:
        return DataStorage.carregar_json(ConfigManager.MODELO_PERFORMANCE_PATH)
    
    @staticmethod
    def salvar_performance_modelo(performance: dict):
        DataStorage.salvar_json(ConfigManager.MODELO_PERFORMANCE_PATH, performance)

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
    def carregar_alertas_completos() -> dict:
        return DataStorage.carregar_json(ConfigManager.ALERTAS_COMPLETOS_PATH)
    
    @staticmethod
    def salvar_alertas_completos(alertas: dict):
        DataStorage.salvar_json(ConfigManager.ALERTAS_COMPLETOS_PATH, alertas)
    
    @staticmethod
    def carregar_resultados_completos() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_COMPLETOS_PATH)
    
    @staticmethod
    def salvar_resultados_completos(resultados: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_COMPLETOS_PATH, resultados)
    
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
        self.over_05_ht = 0.0
        self.over_15_ht = 0.0
        
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
    
    def get_data_brasilia_str(self):
        if not self.utc_date:
            return "Data inválida"
        
        try:
            if self.utc_date.endswith('Z'):
                data_utc = datetime.fromisoformat(self.utc_date.replace('Z', '+00:00'))
            else:
                data_utc = datetime.fromisoformat(self.utc_date)
            
            if data_utc.tzinfo is None:
                data_utc = data_utc.replace(tzinfo=timezone.utc)
            
            fuso_brasilia = timezone(timedelta(hours=-3))
            data_brasilia = data_utc.astimezone(fuso_brasilia)
            
            return data_brasilia.strftime("%d/%m/%Y")
        except Exception as e:
            logging.error(f"Erro ao converter data {self.utc_date}: {e}")
            return "Data inválida"
    
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
            self.over_05_ht = ht_analise.get("over_05_ht", 0.0)
            self.over_15_ht = ht_analise.get("over_15_ht", 0.0)
        
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
            return "GREEN"
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
                "over_05_ht": self.over_05_ht,
                "over_15_ht": self.over_15_ht
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
                "estimativa_total_ht": self.jogo.estimativa_total_ht,
                "over_05_ht": self.jogo.over_05_ht,
                "over_15_ht": self.jogo.over_15_ht
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
# [MELHORIA] NOVA CLASSE: AnalisadorPerformance
# =============================
class AnalisadorPerformance:
    """Analisa a performance histórica do modelo para autoajuste"""
    
    def __init__(self):
        self.historico = self._carregar_historico()
        
    def _carregar_historico(self) -> dict:
        """Carrega o histórico de performance"""
        return DataStorage.carregar_performance_modelo()
    
    def _salvar_historico(self):
        """Salva o histórico de performance"""
        DataStorage.salvar_performance_modelo(self.historico)
    
    def registrar_resultado(self, alerta: dict, tipo_alerta: str, resultado: str, metadata: dict):
        """Registra o resultado de um alerta para análise futura"""
        chave = f"{tipo_alerta}_{datetime.now().strftime('%Y%m')}"
        
        if chave not in self.historico:
            self.historico[chave] = {
                "total": 0,
                "greens": 0,
                "reds": 0,
                "por_liga": defaultdict(lambda: {"total": 0, "greens": 0}),
                "por_faixa_confianca": defaultdict(lambda: {"total": 0, "greens": 0}),
                "por_tipo": defaultdict(lambda: {"total": 0, "greens": 0}),
                "erros": []
            }
        
        hist = self.historico[chave]
        hist["total"] += 1
        if resultado == "GREEN":
            hist["greens"] += 1
        else:
            hist["reds"] += 1
            if len(hist["erros"]) < 100:
                hist["erros"].append({
                    "alerta": alerta,
                    "metadata": metadata,
                    "resultado_esperado": alerta.get("tendencia", ""),
                    "resultado_real": f"{metadata.get('home_goals', '?')}-{metadata.get('away_goals', '?')}"
                })
        
        liga = alerta.get("liga", "Desconhecida")
        hist["por_liga"][liga]["total"] += 1
        if resultado == "GREEN":
            hist["por_liga"][liga]["greens"] += 1
        
        confianca = alerta.get("confianca", 0)
        faixa = f"{int(confianca // 10 * 10)}-{int(confianca // 10 * 10 + 9)}"
        hist["por_faixa_confianca"][faixa]["total"] += 1
        if resultado == "GREEN":
            hist["por_faixa_confianca"][faixa]["greens"] += 1
        
        tipo_aposta = alerta.get("tipo_aposta", "unknown")
        hist["por_tipo"][tipo_aposta]["total"] += 1
        if resultado == "GREEN":
            hist["por_tipo"][tipo_aposta]["greens"] += 1
        
        self._salvar_historico()
    
    def obter_acuracia_por_liga(self, liga: str, tipo_alerta: str = "over_under") -> float:
        chave = f"{tipo_alerta}_{datetime.now().strftime('%Y%m')}"
        if chave not in self.historico:
            return 0.5
        
        dados_liga = self.historico[chave]["por_liga"].get(liga, {})
        total = dados_liga.get("total", 0)
        if total == 0:
            return 0.5
        return dados_liga.get("greens", 0) / total
    
    def obter_acuracia_por_faixa_confianca(self, confianca: float, tipo_alerta: str = "over_under") -> float:
        chave = f"{tipo_alerta}_{datetime.now().strftime('%Y%m')}"
        if chave not in self.historico:
            return 0.5
        
        faixa = f"{int(confianca // 10 * 10)}-{int(confianca // 10 * 10 + 9)}"
        dados_faixa = self.historico[chave]["por_faixa_confianca"].get(faixa, {})
        total = dados_faixa.get("total", 0)
        if total == 0:
            return 0.5
        return dados_faixa.get("greens", 0) / total
    
    def ajustar_limiar_confianca(self, tipo_alerta: str = "over_under") -> float:
        chave = f"{tipo_alerta}_{datetime.now().strftime('%Y%m')}"
        if chave not in self.historico:
            return 70.0
        
        dados = self.historico[chave]
        
        melhor_faixa = 70.0
        melhor_score = 0.0
        
        for faixa, stats in dados["por_faixa_confianca"].items():
            if stats["total"] < 5:
                continue
            
            acuracia = stats["greens"] / stats["total"] if stats["total"] > 0 else 0
            score = acuracia * (stats["total"] ** 0.5)
            
            if score > melhor_score:
                melhor_score = score
                try:
                    melhor_faixa = float(faixa.split('-')[0])
                except:
                    melhor_faixa = 70.0
        
        return max(60.0, min(85.0, melhor_faixa))


# =============================
# CLASSES DE ANÁLISE
# =============================

class AnalisadorEstatistico:
    """Realiza análises estatísticas para previsões"""
    
    def __init__(self):
        self.analisador_performance = AnalisadorPerformance()

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

        logging.info(f"AMBAS MARCAM: {home} vs {away} | SIM: {prob_ambas_marcam:.1f}% | NÃO: {prob_nao_ambas_marcam:.1f}% | Tendência: {tendencia_ambas_marcam} | Conf: {confianca_ambas_marcam:.1f}%")

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

    @staticmethod
    def calcular_conflito_over_btts(home: str, away: str, classificacao: dict, estimativa_total: float, resultado_btts: dict) -> dict:
        dados_home = classificacao.get(home, {})
        dados_away = classificacao.get(away, {})

        played_home = max(dados_home.get("played", 1), 1)
        played_away = max(dados_away.get("played", 1), 1)

        media_home = dados_home.get("scored", 0) / played_home
        media_away = dados_away.get("scored", 0) / played_away

        equilibrio_ofensivo = 1 - abs(media_home - media_away)
        equilibrio_ofensivo = clamp(equilibrio_ofensivo, 0, 1)

        ataque_unilateral = (
            (media_home >= 1.8 and media_away < 1.0) or
            (media_away >= 1.8 and media_home < 1.0)
        )

        prob_btts_sim = resultado_btts.get("sim", 0)
        prob_btts_nao = resultado_btts.get("nao", 0)

        prioridade = "NEUTRO"
        bloquear_btts = False
        bloquear_over = False
        motivo = "Sem conflito relevante"

        if ataque_unilateral and estimativa_total >= 2.6:
            prioridade = "OVER"
            bloquear_btts = True
            motivo = "Ataque unilateral (OVER sem BTTS)"
        elif equilibrio_ofensivo >= 0.75 and 2.2 <= estimativa_total <= 2.6:
            prioridade = "BTTS"
            bloquear_over = True
            motivo = "Equilíbrio ofensivo (BTTS prioritário)"
        elif equilibrio_ofensivo >= 0.6 and estimativa_total >= 2.0:
            prioridade = "OVER_1.5"
            motivo = "Jogo vivo sem garantia de BTTS"
        elif estimativa_total < 2.0 and equilibrio_ofensivo < 0.55:
            prioridade = "EVITAR"
            bloquear_btts = True
            bloquear_over = True
            motivo = "Jogo travado e desequilibrado"

        return {
            "prioridade": prioridade,
            "bloquear_btts": bloquear_btts,
            "bloquear_over": bloquear_over,
            "equilibrio_ofensivo": round(equilibrio_ofensivo, 2),
            "ataque_unilateral": ataque_unilateral,
            "motivo": motivo,
            "prob_btts_sim": prob_btts_sim,
            "prob_btts_nao": prob_btts_nao
        }

    @staticmethod
    def calcular_escore_confianca(probabilidade: float, confianca: float, estimativa_total: float, linha_mercado: float, conflito: dict) -> int:
        prob_norm = clamp(probabilidade / 100, 0, 1)
        conf_norm = clamp(confianca / 100, 0, 1)

        base = (prob_norm * 0.6) + (conf_norm * 0.4)

        distancia = estimativa_total - linha_mercado
        bonus_distancia = clamp(distancia / 1.2, 0, 1) * 0.25

        penalidade_conflito = 0

        if conflito:
            if conflito.get("bloquear_over") or conflito.get("bloquear_btts"):
                penalidade_conflito += 0.20

            prioridade = conflito.get("prioridade")
            if prioridade in ("EVITAR", "NEUTRO"):
                penalidade_conflito += 0.15

        escore = base + bonus_distancia - penalidade_conflito
        escore = clamp(escore, 0, 1)

        return int(round(escore * 100))


class AnalisadorTendencia:
    """Analisa tendências de gols em partidas - VERSÃO FINAL PROFISSIONAL COM MELHORIAS"""

    def __init__(self, classificacao: dict):
        self.classificacao = classificacao
        self.analisador_performance = AnalisadorPerformance()

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
            estimativa_total *= 1.08
        elif fator_ataque >= 1.35:
            estimativa_total *= 1.05
        elif fator_ataque <= 0.7:
            estimativa_total *= 0.95

        fator_casa = 1.05 + (media_home_feitos - media_home_sofridos) * 0.08
        fator_casa = clamp(fator_casa, 0.96, 1.15)
        estimativa_total *= fator_casa

        estimativa_total = (estimativa_total * 0.85) + (2.5 * 0.15)

        estimativa_total = clamp(estimativa_total, 1.4, 4.0)

        if estimativa_total <= 1.6:
            mercado = "UNDER 2.5"
            tipo_aposta = "under"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((2.5 - estimativa_total) * 1.4)

        elif estimativa_total <= 2.1:
            if fator_ataque < 0.95:
                mercado = "UNDER 2.5"
                tipo_aposta = "under"
                linha_mercado = 2.5
                probabilidade_base = sigmoid((2.5 - estimativa_total) * 1.3)
            else:
                mercado = "OVER 1.5"
                tipo_aposta = "over"
                linha_mercado = 1.5
                probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.6)

        elif estimativa_total >= 3.4:
            mercado = "OVER 3.5"
            tipo_aposta = "over"
            linha_mercado = 3.5
            probabilidade_base = sigmoid((estimativa_total - 3.5) * 1.1)

        elif estimativa_total >= 2.8:
            if fator_ataque >= 1.3:
                mercado = "OVER 2.5"
                tipo_aposta = "over"
                linha_mercado = 2.5
                probabilidade_base = sigmoid((estimativa_total - 2.5) * 1.2)
            else:
                mercado = "OVER 1.5"
                tipo_aposta = "over"
                linha_mercado = 1.5
                probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.5)

        else:
            mercado = "OVER 1.5"
            tipo_aposta = "over"
            linha_mercado = 1.5
            probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.6)

        if tipo_aposta == "under" and estimativa_total > 1.8:
            return {
                "tendencia": "NÃO APOSTAR",
                "estimativa": round(estimativa_total, 2),
                "probabilidade": round(probabilidade_base * 100, 1),
                "confianca": 0,
                "tipo_aposta": "avoid",
                "linha_mercado": linha_mercado,
                "detalhes": {"motivo": f"UNDER perigoso (estimativa alta: {estimativa_total:.2f})"}
            }

        if tipo_aposta == "over" and linha_mercado == 2.5 and estimativa_total < 2.6:
            return {
                "tendencia": "NÃO APOSTAR",
                "estimativa": round(estimativa_total, 2),
                "probabilidade": round(probabilidade_base * 100, 1),
                "confianca": 0,
                "tipo_aposta": "avoid",
                "linha_mercado": linha_mercado,
                "detalhes": {"motivo": f"OVER 2.5 sem força (estimativa: {estimativa_total:.2f})"}
            }

        distancia_linha = abs(estimativa_total - linha_mercado)

        if tipo_aposta == "over":
            base_conf = probabilidade_base * 55
            dist_conf = min(distancia_linha * 28, 32)
        else:
            base_conf = probabilidade_base * 45
            dist_conf = min(distancia_linha * 22, 28)

        consistencia = 0
        if played_home >= 6 and played_away >= 6:
            consistencia += 12
        if abs(media_home_feitos - media_away_feitos) < 1.0:
            consistencia += 6
        if fator_ataque > 1.4 or fator_ataque < 0.7:
            consistencia += 8

        confianca = clamp(base_conf + dist_conf + consistencia, 35, 78)

        if tipo_aposta == "over" and linha_mercado == 1.5:
            if media_home_feitos < 1.2 and media_away_feitos < 1.2:
                confianca *= 0.8

        if media_home_sofridos < 0.8 and media_away_sofridos < 0.8:
            confianca *= 0.9

        if confianca < 48:
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


class ResultadosTopAlertas:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = sistema_principal.config
        self.poster_generator = sistema_principal.poster_generator
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client
    
    def conferir_resultados_top_alertas(self, data_selecionada):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        st.subheader(f"🏆 Conferindo Resultados TOP Alertas - {data_br}")
        
        alertas_top = DataStorage.carregar_alertas_top()
        if not alertas_top:
            st.warning("⚠️ Nenhum alerta TOP salvo para conferência")
            return
        
        alertas_por_grupo = self._agrupar_alertas_top_por_data_tipo(alertas_top, hoje)
        
        if not alertas_por_grupo:
            st.warning(f"⚠️ Nenhum alerta TOP encontrado para {data_br}")
            return
        
        total_grupos = sum(len(grupos) for grupos in alertas_por_grupo.values())
        st.info(f"🔍 Encontrados {total_grupos} grupos de alertas TOP para conferência")
        
        grupos_para_enviar = []
        grupos_ja_enviados = 0
        
        for tipo_alerta, grupos in alertas_por_grupo.items():
            for grupo_id, alertas_grupo in grupos.items():
                
                grupo_ja_enviado = all(alerta.get("enviado", False) for alerta in alertas_grupo)
                
                if grupo_ja_enviado:
                    st.info(f"📤 Grupo {grupo_id} - {tipo_alerta} já foi enviado anteriormente. Pulando...")
                    grupos_ja_enviados += 1
                    continue
                
                st.write(f"📋 Processando grupo {grupo_id} - {tipo_alerta} ({len(alertas_grupo)} jogos)")
                
                jogos_conferidos = []
                jogos_pendentes = []
                jogos_em_andamento = []
                
                for alerta in alertas_grupo:
                    fixture_id = alerta.get("id")
                    
                    match_data = self.api_client.obter_detalhes_jogo(fixture_id)
                    if not match_data:
                        st.warning(f"⚠️ Não foi possível obter dados do jogo {fixture_id}")
                        jogos_pendentes.append(alerta)
                        continue
                    
                    status = match_data.get("status", "")
                    
                    if status == "FINISHED":
                        jogo_conferido = self._processar_resultado_alerta(alerta, match_data, tipo_alerta)
                        if jogo_conferido:
                            jogos_conferidos.append(jogo_conferido)
                            alerta["conferido"] = True
                            alerta["data_conferencia"] = datetime.now().isoformat()
                    
                    elif status in ["IN_PLAY", "PAUSED"]:
                        st.write(f"⏳ Jogo em andamento: {alerta.get('home')} vs {alerta.get('away')}")
                        jogos_em_andamento.append(alerta)
                    elif status in ["SCHEDULED", "TIMED"]:
                        st.write(f"⏰ Jogo agendado: {alerta.get('home')} vs {alerta.get('away')}")
                        jogos_pendentes.append(alerta)
                    else:
                        st.write(f"❓ Status {status}: {alerta.get('home')} vs {alerta.get('away')}")
                        jogos_pendentes.append(alerta)
                
                if len(jogos_pendentes) == 0 and len(jogos_em_andamento) == 0:
                    if jogos_conferidos:
                        st.success(f"✅ TODOS OS {len(jogos_conferidos)} JOGOS ENCERRARAM! Preparando para envio...")
                        grupos_para_enviar.append({
                            "tipo_alerta": tipo_alerta,
                            "grupo_id": grupo_id,
                            "jogos_conferidos": jogos_conferidos,
                            "alertas_originais": alertas_grupo,
                            "data_selecionada": data_selecionada
                        })
                    else:
                        st.warning(f"⚠️ Grupo {grupo_id} sem jogos conferidos, mesmo com todos encerrados?")
                else:
                    pendentes = len(jogos_pendentes) + len(jogos_em_andamento)
                    st.info(f"⏳ Aguardando {pendentes} jogos encerrarem para enviar o grupo {grupo_id}")
                    
                    if jogos_em_andamento:
                        st.write("   🏃 Jogos em andamento:")
                        for j in jogos_em_andamento:
                            st.write(f"      ⏱️ {j.get('home')} vs {j.get('away')}")
                    
                    if jogos_pendentes:
                        st.write("   📅 Jogos pendentes:")
                        for j in jogos_pendentes:
                            st.write(f"      ⏰ {j.get('home')} vs {j.get('away')}")
        
        if grupos_para_enviar:
            st.success(f"🏆 {len(grupos_para_enviar)} grupos completos prontos para envio!")
            
            for grupo in grupos_para_enviar:
                envio_sucesso = self._gerar_poster_para_grupo(
                    grupo["jogos_conferidos"], 
                    grupo["tipo_alerta"], 
                    grupo["grupo_id"], 
                    grupo["data_selecionada"]
                )
                
                if envio_sucesso:
                    for alerta in grupo["alertas_originais"]:
                        alerta["enviado"] = True
                        alerta["data_envio"] = datetime.now().isoformat()
                    st.success(f"✅ Grupo {grupo['grupo_id']} marcado como ENVIADO!")
            
            self._salvar_alertas_top_atualizados(alertas_top)
        else:
            if grupos_ja_enviados > 0:
                st.info(f"📤 {grupos_ja_enviados} grupos já foram enviados anteriormente.")
            st.info("⏳ Nenhum grupo novo completo ainda. Aguardando jogos encerrarem...")
        
        self._salvar_alertas_top_atualizados(alertas_top)
        self._mostrar_resumo_geral(alertas_por_grupo)
    
    def _agrupar_alertas_top_por_data_tipo(self, alertas_top, data_busca):
        alertas_por_grupo = {
            "over_under": {},
            "favorito": {},
            "gols_ht": {},
            "ambas_marcam": {}
        }
        
        alertas_lista = []
        if isinstance(alertas_top, dict):
            alertas_lista = list(alertas_top.values())
        elif isinstance(alertas_top, list):
            alertas_lista = alertas_top
        else:
            st.error(f"❌ Estrutura inesperada de alertas_top: {type(alertas_top)}")
            return {}
        
        logging.info(f"Total de alertas TOP carregados: {len(alertas_lista)}")
        
        for alerta in alertas_lista:
            if not isinstance(alerta, dict):
                logging.warning(f"Alerta não é um dicionário: {type(alerta)}")
                continue
            
            if "data_busca" not in alerta:
                logging.warning(f"Alerta sem data_busca: {alerta.get('id', 'sem_id')}")
                continue
                
            if alerta["data_busca"] != data_busca:
                continue
            
            tipo_alerta = alerta.get("tipo_alerta", "over_under")
            if tipo_alerta not in alertas_por_grupo:
                logging.warning(f"Tipo de alerta desconhecido: {tipo_alerta}")
                continue
            
            data_agrupamento = alerta.get("data_hora_busca") or alerta.get("data_criacao") or alerta.get("data_busca", "")
            grupo_key = "default"
            
            if data_agrupamento:
                try:
                    if isinstance(data_agrupamento, str):
                        dt_agrupamento = datetime.fromisoformat(data_agrupamento.replace('Z', '+00:00'))
                    else:
                        dt_agrupamento = data_agrupamento
                    
                    grupo_key = dt_agrupamento.strftime("%H:%M")
                except Exception as e:
                    logging.warning(f"Erro ao converter data para agrupamento {data_agrupamento}: {e}")
                    grupo_key = datetime.now().strftime("%H:%M")
            
            if grupo_key not in alertas_por_grupo[tipo_alerta]:
                alertas_por_grupo[tipo_alerta][grupo_key] = []
            
            alertas_por_grupo[tipo_alerta][grupo_key].append(alerta)
        
        for tipo, grupos in alertas_por_grupo.items():
            if grupos:
                total_grupos = len(grupos)
                total_jogos = sum(len(g) for g in grupos.values())
                logging.info(f"Tipo {tipo}: {total_grupos} grupos, {total_jogos} jogos")
        
        for tipo in list(alertas_por_grupo.keys()):
            if not alertas_por_grupo[tipo]:
                del alertas_por_grupo[tipo]
        
        return alertas_por_grupo
    
    def _salvar_alertas_top_atualizados(self, alertas_top):
        try:
            DataStorage.salvar_alertas_top(alertas_top)
            logging.info(f"✅ Alertas TOP salvos com sucesso")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar alertas TOP: {e}")
    
    def _processar_resultado_alerta(self, alerta, match_data, tipo_alerta):
        try:
            fixture_id = alerta.get("id")
            score = match_data.get("score", {})
            full_time = score.get("fullTime", {})
            half_time = score.get("halfTime", {})
            
            home_goals = full_time.get("home", 0)
            away_goals = full_time.get("away", 0)
            ht_home_goals = half_time.get("home", 0)
            ht_away_goals = half_time.get("away", 0)
            
            home_crest = match_data.get("homeTeam", {}).get("crest") or alerta.get("escudo_home", "")
            away_crest = match_data.get("awayTeam", {}).get("crest") or alerta.get("escudo_away", "")
            
            jogo = Jogo({
                "id": fixture_id,
                "homeTeam": {"name": alerta.get("home", ""), "crest": home_crest},
                "awayTeam": {"name": alerta.get("away", ""), "crest": away_crest},
                "utcDate": alerta.get("hora", ""),
                "competition": {"name": alerta.get("liga", "")},
                "status": "FINISHED"
            })
            
            if tipo_alerta == "over_under":
                jogo.set_analise({
                    "tendencia": alerta.get("tendencia", ""),
                    "estimativa": alerta.get("estimativa", 0.0),
                    "probabilidade": alerta.get("probabilidade", 0.0),
                    "confianca": alerta.get("confianca", 0.0),
                    "tipo_aposta": alerta.get("tipo_aposta", ""),
                    "detalhes": alerta.get("detalhes", {})
                })
            elif tipo_alerta == "favorito":
                jogo.set_analise({
                    "detalhes": {
                        "vitoria": {
                            "favorito": alerta.get("favorito", ""),
                            "confianca_vitoria": alerta.get("confianca_vitoria", 0.0),
                            "home_win": alerta.get("prob_home_win", 0.0),
                            "away_win": alerta.get("prob_away_win", 0.0),
                            "draw": alerta.get("prob_draw", 0.0)
                        }
                    }
                })
            elif tipo_alerta == "gols_ht":
                jogo.set_analise({
                    "detalhes": {
                        "gols_ht": {
                            "tendencia_ht": alerta.get("tendencia_ht", ""),
                            "confianca_ht": alerta.get("confianca_ht", 0.0),
                            "estimativa_total_ht": alerta.get("estimativa_total_ht", 0.0),
                            "over_05_ht": alerta.get("over_05_ht", 0.0),
                            "over_15_ht": alerta.get("over_15_ht", 0.0)
                        }
                    }
                })
            elif tipo_alerta == "ambas_marcam":
                jogo.set_analise({
                    "detalhes": {
                        "ambas_marcam": {
                            "tendencia_ambas_marcam": alerta.get("tendencia_ambas_marcam", ""),
                            "confianca_ambas_marcam": alerta.get("confianca_ambas_marcam", 0.0),
                            "sim": alerta.get("prob_ambas_marcam_sim", 0.0),
                            "nao": alerta.get("prob_ambas_marcam_nao", 0.0)
                        }
                    }
                })
            
            jogo.set_resultado(home_goals, away_goals, ht_home_goals, ht_away_goals)
            
            alerta["conferido"] = True
            alerta["home_goals"] = home_goals
            alerta["away_goals"] = away_goals
            alerta["ht_home_goals"] = ht_home_goals
            alerta["ht_away_goals"] = ht_away_goals
            alerta["data_conferencia"] = datetime.now().isoformat()
            alerta["escudo_home"] = home_crest
            alerta["escudo_away"] = away_crest
            
            if tipo_alerta == "over_under":
                alerta["resultado"] = jogo.resultado
            elif tipo_alerta == "favorito":
                alerta["resultado_favorito"] = jogo.resultado_favorito
            elif tipo_alerta == "gols_ht":
                alerta["resultado_ht"] = jogo.resultado_ht
            elif tipo_alerta == "ambas_marcam":
                alerta["resultado_ambas_marcam"] = jogo.resultado_ambas_marcam
            
            self._mostrar_resultado_alerta_top(alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo)
            
            dados_poster = {
                "home": alerta.get("home", ""),
                "away": alerta.get("away", ""),
                "liga": alerta.get("liga", ""),
                "hora": jogo.get_hora_brasilia_datetime(),
                "escudo_home": home_crest,
                "escudo_away": away_crest,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "ht_home_goals": ht_home_goals,
                "ht_away_goals": ht_away_goals,
            }
            
            if tipo_alerta == "over_under":
                dados_poster.update({
                    "tendencia": alerta.get("tendencia", ""),
                    "estimativa": alerta.get("estimativa", 0.0),
                    "probabilidade": alerta.get("probabilidade", 0.0),
                    "confianca": alerta.get("confianca", 0.0),
                    "tipo_aposta": alerta.get("tipo_aposta", ""),
                    "resultado": jogo.resultado
                })
            elif tipo_alerta == "favorito":
                dados_poster.update({
                    "favorito": alerta.get("favorito", ""),
                    "confianca_vitoria": alerta.get("confianca_vitoria", 0.0),
                    "prob_home_win": alerta.get("prob_home_win", 0.0),
                    "prob_away_win": alerta.get("prob_away_win", 0.0),
                    "prob_draw": alerta.get("prob_draw", 0.0),
                    "resultado_favorito": jogo.resultado_favorito
                })
            elif tipo_alerta == "gols_ht":
                dados_poster.update({
                    "tendencia_ht": alerta.get("tendencia_ht", ""),
                    "confianca_ht": alerta.get("confianca_ht", 0.0),
                    "estimativa_total_ht": alerta.get("estimativa_total_ht", 0.0),
                    "over_05_ht": alerta.get("over_05_ht", 0.0),
                    "over_15_ht": alerta.get("over_15_ht", 0.0),
                    "resultado_ht": jogo.resultado_ht
                })
            elif tipo_alerta == "ambas_marcam":
                dados_poster.update({
                    "tendencia_ambas_marcam": alerta.get("tendencia_ambas_marcam", ""),
                    "confianca_ambas_marcam": alerta.get("confianca_ambas_marcam", 0.0),
                    "prob_ambas_marcam_sim": alerta.get("prob_ambas_marcam_sim", 0.0),
                    "prob_ambas_marcam_nao": alerta.get("prob_ambas_marcam_nao", 0.0),
                    "resultado_ambas_marcam": jogo.resultado_ambas_marcam
                })
            
            return dados_poster
            
        except Exception as e:
            logging.error(f"Erro ao processar resultado do alerta {alerta.get('id')}: {e}")
            st.error(f"❌ Erro ao processar {alerta.get('home')} vs {alerta.get('away')}: {e}")
            return None
    
    def _gerar_poster_para_grupo(self, jogos_conferidos, tipo_alerta, grupo_id, data_selecionada):
        data_str = data_selecionada.strftime("%d/%m/%Y")
        
        try:
            if tipo_alerta == "over_under":
                titulo = f"🏆 RESULTADOS TOP OVER/UNDER - {data_str}"
            elif tipo_alerta == "favorito":
                titulo = f"🏆 RESULTADOS TOP FAVORITOS - {data_str}"
            elif tipo_alerta == "gols_ht":
                titulo = f"🏆 RESULTADOS TOP GOLS HT - {data_str}"
            elif tipo_alerta == "ambas_marcam":
                titulo = f"🏆 RESULTADOS TOP AMBAS MARCAM - {data_str}"
            
            if tipo_alerta == "over_under":
                greens = sum(1 for j in jogos_conferidos if j.get("resultado") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado") == "RED")
            elif tipo_alerta == "favorito":
                greens = sum(1 for j in jogos_conferidos if j.get("resultado_favorito") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado_favorito") == "RED")
            elif tipo_alerta == "gols_ht":
                greens = sum(1 for j in jogos_conferidos if j.get("resultado_ht") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado_ht") == "RED")
            elif tipo_alerta == "ambas_marcam":
                greens = sum(1 for j in jogos_conferidos if j.get("resultado_ambas_marcam") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado_ambas_marcam") == "RED")
            
            total = greens + reds
            if total > 0:
                taxa_acerto = (greens / total) * 100
                
                if grupo_id != "default":
                    titulo += f" (Grupo {grupo_id})"
                
                poster = self.poster_generator.gerar_poster_resultados(jogos_conferidos, tipo_alerta)
                
                if poster and self._verificar_poster_valido(poster):
                    caption = (
                        f"<b>{titulo}</b>\n\n"
                        f"<b>📊 {len(jogos_conferidos)} JOGOS</b>\n"
                        f"<b>✅ {greens} GREEN  •  ❌ {reds} RED</b>\n"
                        f"<b>🎯 ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM</b>"
                    )
                    
                    if self.telegram_client.enviar_foto(poster, caption=caption):
                        st.success(f"🏆 Poster resultados TOP {tipo_alerta} (Grupo {grupo_id}) enviado!")
                        return True
                    else:
                        st.warning(f"⚠️ Não foi possível enviar o poster. Enviando como texto...")
                        return self._enviar_resultados_como_texto(titulo, jogos_conferidos, greens, reds, taxa_acerto, tipo_alerta)
                else:
                    st.warning(f"⚠️ Poster não gerado corretamente. Enviando como texto...")
                    return self._enviar_resultados_como_texto(titulo, jogos_conferidos, greens, reds, taxa_acerto, tipo_alerta)
            
            return False
                    
        except Exception as e:
            logging.error(f"Erro ao gerar poster para grupo {grupo_id} - {tipo_alerta}: {e}")
            st.error(f"❌ Erro no poster: {e}")
            
            try:
                error_msg = f"<b>❌ ERRO NO POSTER - {tipo_alerta.upper()}</b>\n\n"
                error_msg += f"<b>Grupo: {grupo_id}</b>\n"
                error_msg += f"<b>Data: {data_str}</b>\n"
                error_msg += f"<b>Jogos: {len(jogos_conferidos)}</b>\n"
                error_msg += f"<b>Erro: {str(e)[:100]}...</b>"
                return self.telegram_client.enviar_mensagem(error_msg, self.config.TELEGRAM_CHAT_ID_ALT2)
            except Exception as e2:
                logging.error(f"Erro ao enviar mensagem de erro: {e2}")
                return False
    
    def _mostrar_resumo_geral(self, alertas_por_grupo):
        st.markdown("---")
        st.subheader("📈 RESUMO GERAL TOP ALERTAS")
        
        col1, col2, col3, col4 = st.columns(4)
        
        totais = {
            "over_under": {"greens": 0, "reds": 0, "total": 0, "pendentes": 0, "conferidos": 0, "enviados": 0},
            "favorito": {"greens": 0, "reds": 0, "total": 0, "pendentes": 0, "conferidos": 0, "enviados": 0},
            "gols_ht": {"greens": 0, "reds": 0, "total": 0, "pendentes": 0, "conferidos": 0, "enviados": 0},
            "ambas_marcam": {"greens": 0, "reds": 0, "total": 0, "pendentes": 0, "conferidos": 0, "enviados": 0}
        }
        
        for tipo_alerta, grupos in alertas_por_grupo.items():
            for grupo_id, alertas_grupo in grupos.items():
                for alerta in alertas_grupo:
                    totais[tipo_alerta]["total"] += 1
                    
                    if alerta.get("enviado", False):
                        totais[tipo_alerta]["enviados"] += 1
                    
                    if alerta.get("conferido", False):
                        totais[tipo_alerta]["conferidos"] += 1
                        
                        if tipo_alerta == "over_under" and alerta.get("resultado") == "GREEN":
                            totais[tipo_alerta]["greens"] += 1
                        elif tipo_alerta == "over_under" and alerta.get("resultado") == "RED":
                            totais[tipo_alerta]["reds"] += 1
                        elif tipo_alerta == "favorito" and alerta.get("resultado_favorito") == "GREEN":
                            totais[tipo_alerta]["greens"] += 1
                        elif tipo_alerta == "favorito" and alerta.get("resultado_favorito") == "RED":
                            totais[tipo_alerta]["reds"] += 1
                        elif tipo_alerta == "gols_ht" and alerta.get("resultado_ht") == "GREEN":
                            totais[tipo_alerta]["greens"] += 1
                        elif tipo_alerta == "gols_ht" and alerta.get("resultado_ht") == "RED":
                            totais[tipo_alerta]["reds"] += 1
                        elif tipo_alerta == "ambas_marcam" and alerta.get("resultado_ambas_marcam") == "GREEN":
                            totais[tipo_alerta]["greens"] += 1
                        elif tipo_alerta == "ambas_marcam" and alerta.get("resultado_ambas_marcam") == "RED":
                            totais[tipo_alerta]["reds"] += 1
                    else:
                        totais[tipo_alerta]["pendentes"] += 1
        
        with col1:
            total = totais["over_under"]["total"]
            conferidos = totais["over_under"]["conferidos"]
            enviados = totais["over_under"]["enviados"]
            pendentes = totais["over_under"]["pendentes"]
            greens = totais["over_under"]["greens"]
            reds = totais["over_under"]["reds"]
            
            st.metric("⚽ TOP Over/Under", f"{total} jogos", f"{enviados} enviados")
            if conferidos > 0:
                taxa_acerto = (greens / conferidos) * 100 if conferidos > 0 else 0
                st.write(f"✅ {greens} | ❌ {reds} | 📊 {taxa_acerto:.1f}%")
            if pendentes > 0:
                st.write(f"⏳ {pendentes} pendentes")
        
        with col2:
            total = totais["favorito"]["total"]
            conferidos = totais["favorito"]["conferidos"]
            enviados = totais["favorito"]["enviados"]
            pendentes = totais["favorito"]["pendentes"]
            greens = totais["favorito"]["greens"]
            reds = totais["favorito"]["reds"]
            
            st.metric("🏆 TOP Favoritos", f"{total} jogos", f"{enviados} enviados")
            if conferidos > 0:
                taxa_acerto = (greens / conferidos) * 100 if conferidos > 0 else 0
                st.write(f"✅ {greens} | ❌ {reds} | 📊 {taxa_acerto:.1f}%")
            if pendentes > 0:
                st.write(f"⏳ {pendentes} pendentes")
        
        with col3:
            total = totais["gols_ht"]["total"]
            conferidos = totais["gols_ht"]["conferidos"]
            enviados = totais["gols_ht"]["enviados"]
            pendentes = totais["gols_ht"]["pendentes"]
            greens = totais["gols_ht"]["greens"]
            reds = totais["gols_ht"]["reds"]
            
            st.metric("⏰ TOP Gols HT", f"{total} jogos", f"{enviados} enviados")
            if conferidos > 0:
                taxa_acerto = (greens / conferidos) * 100 if conferidos > 0 else 0
                st.write(f"✅ {greens} | ❌ {reds} | 📊 {taxa_acerto:.1f}%")
            if pendentes > 0:
                st.write(f"⏳ {pendentes} pendentes")
        
        with col4:
            total = totais["ambas_marcam"]["total"]
            conferidos = totais["ambas_marcam"]["conferidos"]
            enviados = totais["ambas_marcam"]["enviados"]
            pendentes = totais["ambas_marcam"]["pendentes"]
            greens = totais["ambas_marcam"]["greens"]
            reds = totais["ambas_marcam"]["reds"]
            
            st.metric("🤝 TOP Ambas Marcam", f"{total} jogos", f"{enviados} enviados")
            if conferidos > 0:
                taxa_acerto = (greens / conferidos) * 100 if conferidos > 0 else 0
                st.write(f"✅ {greens} | ❌ {reds} | 📊 {taxa_acerto:.1f}%")
            if pendentes > 0:
                st.write(f"⏳ {pendentes} pendentes")
    
    def _mostrar_resultado_alerta_top(self, alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo):
        tipo_alerta = alerta.get("tipo_alerta", "over_under")
        
        if tipo_alerta == "over_under":
            resultado = jogo.resultado
            cor = "🟢" if resultado == "GREEN" else "🔴"
            st.write(f"{cor} 🏆 {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
            st.write(f"   📊 {alerta.get('tendencia', '')} | Est: {alerta.get('estimativa', 0):.2f} | Conf: {alerta.get('confianca', 0):.0f}%")
            st.write(f"   🎯 Resultado: {resultado}")
        elif tipo_alerta == "favorito":
            resultado = jogo.resultado_favorito
            cor = "🟢" if resultado == "GREEN" else "🔴"
            favorito = alerta.get('favorito', '')
            favorito_text = alerta.get('home', '') if favorito == "home" else alerta.get('away', '') if favorito == "away" else "EMPATE"
            st.write(f"{cor} 🏆 {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
            st.write(f"   🏆 Favorito: {favorito_text} | Conf: {alerta.get('confianca_vitoria', 0):.0f}%")
            st.write(f"   🎯 Resultado: {resultado}")
        elif tipo_alerta == "gols_ht":
            resultado = jogo.resultado_ht
            cor = "🟢" if resultado == "GREEN" else "🔴"
            st.write(f"{cor} 🏆 {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
            st.write(f"   ⏰ {alerta.get('tendencia_ht', '')} | Est HT: {alerta.get('estimativa_total_ht', 0):.2f} | Conf HT: {alerta.get('confianca_ht', 0):.0f}%")
            st.write(f"   🎯 Resultado HT: {resultado} (HT: {ht_home_goals}-{ht_away_goals})")
        elif tipo_alerta == "ambas_marcam":
            resultado = jogo.resultado_ambas_marcam
            cor = "🟢" if resultado == "GREEN" else "🔴"
            st.write(f"{cor} 🏆 {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
            st.write(f"   🤝 {alerta.get('tendencia_ambas_marcam', '')} | Conf: {alerta.get('confianca_ambas_marcam', 0):.0f}%")
            st.write(f"   🎯 Resultado Ambas Marcam: {resultado}")
    
    def _verificar_poster_valido(self, poster: io.BytesIO) -> bool:
        try:
            if not poster:
                return False
            
            poster.seek(0)
            img = Image.open(poster)
            width, height = img.size
            
            if width < 100 or height < 100:
                logging.warning(f"Poster com dimensões inválidas: {width}x{height}")
                return False
            
            if img.format != "PNG":
                logging.warning(f"Poster com formato inválido: {img.format}")
                return False
            
            poster.seek(0, 2)
            file_size = poster.tell()
            poster.seek(0)
            
            if file_size < 1024:
                logging.warning(f"Poster muito pequeno: {file_size} bytes")
                return False
            
            logging.info(f"Poster válido: {width}x{height}, formato: {img.format}, tamanho: {file_size} bytes")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao verificar poster: {e}")
            return False
    
    def _enviar_resultados_como_texto(self, titulo, jogos_lista, greens, reds, taxa_acerto, tipo_alerta):
        texto_fallback = f"{titulo}\n\n"
        texto_fallback += f"📊 {len(jogos_lista)} JOGOS\n"
        texto_fallback += f"✅ GREEN: {greens}\n"
        texto_fallback += f"❌ RED: {reds}\n"
        texto_fallback += f"🎯 TAXA: {taxa_acerto:.1f}%\n\n"
        
        for i, jogo in enumerate(jogos_lista[:10], 1):
            if tipo_alerta == "over_under":
                resultado_texto = "✅" if jogo.get("resultado") == "GREEN" else "❌"
                texto_fallback += f"{i}. {jogo['home']} {jogo.get('home_goals', '?')}-{jogo.get('away_goals', '?')} {jogo['away']} {resultado_texto}\n"
        
        texto_fallback += "\n🔥 ELITE MASTER SYSTEM - TOP PERFORMANCE"
        
        if self.telegram_client.enviar_mensagem(f"<b>{texto_fallback}</b>", self.config.TELEGRAM_CHAT_ID_ALT2):
            st.success(f"📤 Resultados enviados como texto!")
            return True
        else:
            st.error(f"❌ Falha ao enviar resultados como texto!")
            return False


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
            "estimativa_total_ht": jogo.estimativa_total_ht,
            "over_05_ht": jogo.over_05_ht,
            "over_15_ht": jogo.over_15_ht
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
                self.resultados["gols_ht"] = "GREEN"
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
        
        self.ALERTAS_COMPLETOS_PATH = ConfigManager.ALERTAS_COMPLETOS_PATH
        self.RESULTADOS_COMPLETOS_PATH = ConfigManager.RESULTADOS_COMPLETOS_PATH
    
    def salvar_alerta_completo(self, alerta: AlertaCompleto):
        alertas = self.carregar_alertas()
        chave = f"{alerta.jogo.id}_{alerta.data_busca}"
        alertas[chave] = alerta.to_dict()
        self._salvar_alertas(alertas)
    
    def carregar_alertas(self) -> dict:
        return DataStorage.carregar_alertas_completos()
    
    def _salvar_alertas(self, alertas: dict):
        DataStorage.salvar_alertas_completos(alertas)
    
    def carregar_resultados(self) -> dict:
        return DataStorage.carregar_resultados_completos()
    
    def _salvar_resultados(self, resultados: dict):
        DataStorage.salvar_resultados_completos(resultados)
    
    def filtrar_melhores_jogos(self, jogos_analisados: list, limiares: dict = None) -> list:
        if limiares is None:
            limiares = {
                'over_under': 60,
                'favorito': 50,
                'gols_ht': 30,
                'ambas_marcam': 30,
            }
        
        melhores = []
        for jogo_dict in jogos_analisados:
            conf_over = jogo_dict.get('confianca', 0)
            conf_fav = jogo_dict.get('confianca_vitoria', 0)
            conf_ht = jogo_dict.get('confianca_ht', 0)
            conf_am = jogo_dict.get('confianca_ambas_marcam', 0)
            
            if (conf_over >= limiares['over_under'] and
                conf_fav >= limiares['favorito'] and
                conf_ht >= limiares['gols_ht'] and
                conf_am >= limiares['ambas_marcam']):
                melhores.append(jogo_dict)
        
        return melhores
    
    def gerar_poster_completo(self, jogos: list) -> io.BytesIO:
        LARGURA = 2000
        ALTURA_TOPO = 270
        ALTURA_POR_JOGO = 900
        PADDING = 80
        
        jogos_count = len(jogos)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)

        FONTE_TITULO = self.poster_generator.criar_fonte(90)
        FONTE_SUBTITULO = self.poster_generator.criar_fonte(65)
        FONTE_TIMES = self.poster_generator.criar_fonte(60)
        FONTE_VS = self.poster_generator.criar_fonte(55)
        FONTE_INFO = self.poster_generator.criar_fonte(45)
        FONTE_ANALISE = self.poster_generator.criar_fonte(50)
        FONTE_ANALISE_TITULO = self.poster_generator.criar_fonte(50)
        FONTE_DETALHES = self.poster_generator.criar_fonte(35)

        titulo = "⚽ ALERTA COMPLETO - ALL IN ONE"
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
            
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=(255, 215, 0), width=4)

            liga_text = jogo['liga'].upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

            if isinstance(jogo["hora"], datetime):
                data_text = jogo["hora"].strftime("%d/%m/%Y")
                hora_text = jogo["hora"].strftime("%H:%M")
                data_hora_text = f"{data_text} {hora_text}"
            else:
                data_hora_text = str(jogo["hora"])

            try:
                data_bbox = draw.textbbox((0, 0), data_hora_text, font=FONTE_INFO)
                data_w = data_bbox[2] - data_bbox[0]
                draw.text(((LARGURA - data_w) // 2, y0 + 130), data_hora_text, font=FONTE_INFO, fill=(150, 200, 255))
            except:
                draw.text((LARGURA//2 - 150, y0 + 130), data_hora_text, font=FONTE_INFO, fill=(150, 200, 255))

            TAMANHO_ESCUDO = 180
            TAMANHO_QUADRADO = 200
            ESPACO_ENTRE_ESCUDOS = 700

            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2

            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 180

            escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], jogo.get('escudo_home', ''))
            escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], jogo.get('escudo_away', ''))
            
            escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA") if escudo_home_bytes else None
            escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA") if escudo_away_bytes else None

            self.poster_generator._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self.poster_generator._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

            try:
                home_bbox = draw.textbbox((0, 0), jogo['home'], font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 40),
                         jogo['home'], font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 40), jogo['home'], font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                away_bbox = draw.textbbox((0, 0), jogo['away'], font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 40),
                         jogo['away'], font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 40), jogo['away'], font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
                vs_w = vs_bbox[2] - vs_bbox[0]
                vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
                draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), 
                         "VS", font=FONTE_VS, fill=(255, 215, 0))
            except:
                vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 30
                draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), "VS", font=FONTE_VS, fill=(255, 215, 0))

            y_analysis = y_escudos + TAMANHO_QUADRADO + 120
            
            analise_ou = jogo.get('analise_over_under', {})
            tendencia = analise_ou.get('tendencia', 'N/A')
            conf_ou = analise_ou.get('confianca', 0)
            tipo_aposta = analise_ou.get('tipo_aposta', '')
            cor_ou = (255, 215, 0) if tipo_aposta == "over" else (100, 200, 255)
            
            prob_ou = analise_ou.get('probabilidade', 50)
            odd_ou = round(100 / prob_ou, 2) if prob_ou > 0 else 2.0
            
            draw.text((x0 + 80, y_analysis + 50), 
                     f" OVER/UNDER: {tendencia} | Conf: {conf_ou:.0f}% | Odds: {odd_ou:.2f}", 
                     font=FONTE_ANALISE, fill=cor_ou)
            
            analise_fav = jogo.get('analise_favorito', {})
            favorito = analise_fav.get('favorito', '')
            conf_fav = analise_fav.get('confianca_vitoria', 0)
            favorito_text = jogo['home'] if favorito == "home" else jogo['away'] if favorito == "away" else "EMPATE"
            cor_fav = (255, 87, 34) if favorito == "home" else (33, 150, 243) if favorito == "away" else (255, 193, 7)
            
            prob_fav = conf_fav
            odd_fav = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
            
            draw.text((x0 + 80, y_analysis + 100), 
                     f" FAVORITO: {favorito_text} | Conf: {conf_fav:.0f}% | Odds: {odd_fav:.2f}", 
                     font=FONTE_ANALISE, fill=cor_fav)
            
            analise_ht = jogo.get('analise_gols_ht', {})
            tendencia_ht = analise_ht.get('tendencia_ht', 'N/A')
            conf_ht = analise_ht.get('confianca_ht', 0)
            cor_ht = (76, 175, 80) if "OVER" in tendencia_ht else (244, 67, 54)
            
            prob_ht = conf_ht
            odd_ht = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
            
            draw.text((x0 + 80, y_analysis + 150), 
                     f" GOLS HT: {tendencia_ht} | Conf: {conf_ht:.0f}% | Odds: {odd_ht:.2f}", 
                     font=FONTE_ANALISE, fill=cor_ht)
            
            analise_am = jogo.get('analise_ambas_marcam', {})
            tendencia_am = analise_am.get('tendencia_ambas_marcam', 'N/A')
            conf_am = analise_am.get('confianca_ambas_marcam', 0)
            cor_am = (155, 89, 182)
            
            prob_am = conf_am
            odd_am = round(100 / prob_am, 2) if prob_am > 0 else 2.0
            
            draw.text((x0 + 80, y_analysis + 200), 
                     f" AMBAS MARCAM: {tendencia_am} | Conf: {conf_am:.0f}% | Odds: {odd_am:.2f}", 
                     font=FONTE_ANALISE, fill=cor_am)
            
            draw.line([(x0 + 80, y_analysis + 290), (x1 - 80, y_analysis + 290)], fill=(100, 130, 160), width=2)

            y_pos += ALTURA_POR_JOGO

        rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - ELITE MASTER SYSTEM - ALL IN ONE"
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
    
    def gerar_poster_resultados_completos(self, jogos_com_resultados: list) -> io.BytesIO:
        LARGURA = 2000
        ALTURA_TOPO = 330
        ALTURA_POR_JOGO = 850
        PADDING = 80
        
        jogos_count = len(jogos_com_resultados)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)

        FONTE_TITULO = self.poster_generator.criar_fonte(90)
        FONTE_SUBTITULO = self.poster_generator.criar_fonte(70)
        FONTE_TIMES = self.poster_generator.criar_fonte(65)
        FONTE_RESULTADO = self.poster_generator.criar_fonte(76)
        FONTE_INFO = self.poster_generator.criar_fonte(45)
        FONTE_ANALISE = self.poster_generator.criar_fonte(40)
        FONTE_ANALISE_TITULO = self.poster_generator.criar_fonte(45)
        FONTE_DETALHES = self.poster_generator.criar_fonte(35)

        titulo = " RESULTADOS COMPLETOS - ALL IN ONE"
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
            
            resultados = jogo.get('resultados', {})
            home_goals = resultados.get('home_goals', '?')
            away_goals = resultados.get('away_goals', '?')
            
            greens = sum(1 for k in ['over_under', 'favorito', 'gols_ht', 'ambas_marcam'] 
                        if resultados.get(k) == "GREEN")
            reds = sum(1 for k in ['over_under', 'favorito', 'gols_ht', 'ambas_marcam'] 
                      if resultados.get(k) == "RED")
            
            if greens == 4:
                cor_borda = (46, 204, 113)
            elif greens >= 3:
                cor_borda = (52, 152, 219)
            elif reds >= 3:
                cor_borda = (231, 76, 60)
            else:
                cor_borda = (149, 165, 166)
            
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)

            badge_text = f" {greens}✅ {reds}❌"
            badge_width = 300
            badge_height = 60
            badge_x = x0 + 50
            badge_y = y0 + 50
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_width, badge_y + badge_height], 
                          fill=cor_borda, outline=(255, 255, 255), width=2)
            
            try:
                badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_INFO)
                badge_w = badge_bbox[2] - badge_bbox[0]
                badge_x_center = badge_x + (badge_width - badge_w) // 2
                draw.text((badge_x_center, badge_y + 15), badge_text, font=FONTE_INFO, fill=(255, 255, 255))
            except:
                draw.text((badge_x + 50, badge_y + 15), badge_text, font=FONTE_INFO, fill=(255, 255, 255))

            liga_text = jogo['liga'].upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

            TAMANHO_ESCUDO = 200
            TAMANHO_QUADRADO = 220
            ESPACO_ENTRE_ESCUDOS = 700

            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2

            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 130

            escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], jogo.get('escudo_home', ''))
            escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], jogo.get('escudo_away', ''))
            
            escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA") if escudo_home_bytes else None
            escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA") if escudo_away_bytes else None

            self.poster_generator._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self.poster_generator._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

            resultado_text = f"{home_goals} - {away_goals}"
            try:
                resultado_bbox = draw.textbbox((0, 0), resultado_text, font=FONTE_RESULTADO)
                resultado_w = resultado_bbox[2] - resultado_bbox[0]
                resultado_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - resultado_w) // 2
                draw.text((resultado_x, y_escudos + TAMANHO_QUADRADO//2 - 30), 
                         resultado_text, font=FONTE_RESULTADO, fill=(255, 255, 255))
            except:
                resultado_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                draw.text((resultado_x, y_escudos + TAMANHO_QUADRADO//2 - 30), 
                         resultado_text, font=FONTE_RESULTADO, fill=(255, 255, 255))

            if resultados.get('ht_home_goals') is not None:
                ht_text = f"HT: {resultados['ht_home_goals']} - {resultados['ht_away_goals']}"
                try:
                    ht_bbox = draw.textbbox((0, 0), ht_text, font=FONTE_INFO)
                    ht_w = ht_bbox[2] - ht_bbox[0]
                    ht_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - ht_w) // 2
                    draw.text((ht_x, y_escudos + TAMANHO_QUADRADO//2 + 40), 
                             ht_text, font=FONTE_INFO, fill=(200, 200, 200))
                except:
                    ht_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                    draw.text((ht_x, y_escudos + TAMANHO_QUADRADO//2 + 40), 
                             ht_text, font=FONTE_INFO, fill=(200, 200, 200))

            y_results = y_escudos + TAMANHO_QUADRADO + 150
            
            draw.text((x0 + 80, y_results), "📊 RESULTADOS DAS ANÁLISES", font=FONTE_ANALISE_TITULO, fill=(255, 215, 0))
            
            res_ou = resultados.get('over_under', 'N/A')
            cor_ou = (46, 204, 113) if res_ou == "GREEN" else (231, 76, 60) if res_ou == "RED" else (149, 165, 166)
            draw.text((x0 + 80, y_results + 50), 
                     f" OVER/UNDER: {res_ou}", 
                     font=FONTE_ANALISE, fill=cor_ou)
            
            res_fav = resultados.get('favorito', 'N/A')
            cor_fav = (46, 204, 113) if res_fav == "GREEN" else (231, 76, 60) if res_fav == "RED" else (149, 165, 166)
            draw.text((x0 + 80, y_results + 90), 
                     f" FAVORITO: {res_fav}", 
                     font=FONTE_ANALISE, fill=cor_fav)
            
            res_ht = resultados.get('gols_ht', 'N/A')
            cor_ht = (46, 204, 113) if res_ht == "GREEN" else (231, 76, 60) if res_ht == "RED" else (149, 165, 166)
            draw.text((x0 + 80, y_results + 130), 
                     f" GOLS HT: {res_ht}", 
                     font=FONTE_ANALISE, fill=cor_ht)
            
            res_am = resultados.get('ambas_marcam', 'N/A')
            cor_am = (46, 204, 113) if res_am == "GREEN" else (231, 76, 60) if res_am == "RED" else (149, 165, 166)
            draw.text((x0 + 80, y_results + 170), 
                     f" AMBAS MARCAM: {res_am}", 
                     font=FONTE_ANALISE, fill=cor_am)

            y_pos += ALTURA_POR_JOGO

        rodape_text = "ELITE MASTER SYSTEM - RESULTADOS COMPLETOS"
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
    
    def processar_e_enviar_alertas_completos(self, jogos_analisados: list, data_busca: str, filtrar_melhores: bool = True, limiares: dict = None):
        if not jogos_analisados:
            return False

        if filtrar_melhores:
            jogos_para_processar = self.filtrar_melhores_jogos(jogos_analisados, limiares)
            if not jogos_para_processar:
                st.info("⚠️ Nenhum jogo atende aos critérios de qualidade. Nada será enviado.")
                return False
            st.info(f"✅ {len(jogos_para_processar)} jogos selecionados como melhores de um total de {len(jogos_analisados)}.")
        else:
            jogos_para_processar = jogos_analisados

        alertas_criados = []
        jogos_para_poster = []

        for jogo_dict in jogos_para_processar:
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

        if not jogos_para_poster:
            return False

        lotes = [jogos_para_poster[i:i+3] for i in range(0, len(jogos_para_poster), 3)]
        total_lotes = len(lotes)
        enviados_com_sucesso = 0

        for idx, lote in enumerate(lotes, 1):
            poster = self.gerar_poster_completo(lote)
            data_str = datetime.now().strftime("%d/%m/%Y")

            caption = (
                f"<b>⚽ ALERTA COMPLETO - ALL IN ONE - {data_str}</b>\n"
                f"<b>📋 LOTE {idx}/{total_lotes} - {len(lote)} JOGOS</b>\n\n"
                f"<b>🎯 Over/Under | 🏆 Favorito | ⏰ Gols HT | 🤝 Ambas Marcam</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE COMPLETA</b>"
            )

            if self.telegram_client.enviar_foto(poster, caption=caption):
                enviados_com_sucesso += 1
                for jogo_lote in lote:
                    for alerta in alertas_criados:
                        if (alerta.jogo.home_team == jogo_lote["home"] and 
                            alerta.jogo.away_team == jogo_lote["away"] and
                            alerta.jogo.get_hora_brasilia_datetime() == jogo_lote["hora"]):
                            alerta.alerta_enviado = True
                            self.salvar_alerta_completo(alerta)
                            break

        if enviados_com_sucesso == total_lotes:
            st.success(f"✅ Todos os {total_lotes} lotes de alertas completos foram enviados!")
            return True
        else:
            st.warning(f"⚠️ Apenas {enviados_com_sucesso} de {total_lotes} lotes foram enviados.")
            return False
    
    def conferir_resultados_completos(self, data_selecionada):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        st.subheader(f"🏆 Conferindo Resultados Completos - {data_br}")

        alertas = self.carregar_alertas()
        if not alertas:
            st.warning("⚠️ Nenhum alerta completo salvo para conferência")
            return

        alertas_hoje = {k: v for k, v in alertas.items() if v.get("data_busca") == hoje and not v.get("conferido", False)}

        if not alertas_hoje:
            st.info(f"ℹ️ Nenhum alerta pendente para {data_br}")
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
            st.success(f"✅ {len(jogos_conferidos)} jogos conferidos! Enviando resultados em lotes...")

            lotes = [jogos_conferidos[i:i+3] for i in range(0, len(jogos_conferidos), 3)]
            total_lotes = len(lotes)

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
            taxa_acerto_global = (total_greens / total_analises * 100) if total_analises > 0 else 0

            for idx, lote in enumerate(lotes, 1):
                poster = self.gerar_poster_resultados_completos(lote)

                greens_lote = 0
                reds_lote = 0
                for jogo in lote:
                    resultados = jogo.get("resultados", {})
                    for key in ['over_under', 'favorito', 'gols_ht', 'ambas_marcam']:
                        if resultados.get(key) == "GREEN":
                            greens_lote += 1
                        elif resultados.get(key) == "RED":
                            reds_lote += 1
                analises_lote = len(lote) * 4
                taxa_lote = (greens_lote / analises_lote * 100) if analises_lote > 0 else 0

                caption = (
                    f"<b>🏆 RESULTADOS COMPLETOS - {hoje}</b>\n"
                    f"<b>📋 LOTE {idx}/{total_lotes} - {len(lote)} JOGOS</b>\n\n"
                    f"<b>✅ GREEN: {greens_lote}</b>\n"
                    f"<b>❌ RED: {reds_lote}</b>\n"
                    f"<b>🎯 TAXA DO LOTE: {taxa_lote:.1f}%</b>\n\n"
                    f"<b>🔥 ELITE MASTER SYSTEM - RESULTADOS CONFIRMADOS</b>"
                )

                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"📤 Lote {idx}/{total_lotes} enviado!")
                else:
                    st.error(f"❌ Falha ao enviar lote {idx}/{total_lotes}")

            st.markdown("---")
            st.subheader("📊 Estatísticas Globais")
            st.metric("Total de Jogos", len(jogos_conferidos))
            st.metric("Total de Análises", total_analises)
            st.metric("Total GREEN", total_greens)
            st.metric("Total RED", total_reds)
            st.metric("Taxa de Acerto Global", f"{taxa_acerto_global:.1f}%")

            self._mostrar_estatisticas_detalhadas(jogos_conferidos)
    
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
                st.metric("⚽ Over/Under", 
                         f"{stats['over_under']['GREEN']}✅ {stats['over_under']['RED']}❌",
                         f"{taxa_ou:.1f}%")
        
        with col2:
            total_fav = stats["favorito"]["GREEN"] + stats["favorito"]["RED"]
            if total_fav > 0:
                taxa_fav = (stats["favorito"]["GREEN"] / total_fav) * 100
                st.metric("🏆 Favoritos", 
                         f"{stats['favorito']['GREEN']}✅ {stats['favorito']['RED']}❌",
                         f"{taxa_fav:.1f}%")
        
        with col3:
            total_ht = stats["gols_ht"]["GREEN"] + stats["gols_ht"]["RED"]
            if total_ht > 0:
                taxa_ht = (stats["gols_ht"]["GREEN"] / total_ht) * 100
                st.metric("⏰ Gols HT", 
                         f"{stats['gols_ht']['GREEN']}✅ {stats['gols_ht']['RED']}❌",
                         f"{taxa_ht:.1f}%")
        
        with col4:
            total_am = stats["ambas_marcam"]["GREEN"] + stats["ambas_marcam"]["RED"]
            if total_am > 0:
                taxa_am = (stats["ambas_marcam"]["GREEN"] / total_am) * 100
                st.metric("🤝 Ambas Marcam", 
                         f"{stats['ambas_marcam']['GREEN']}✅ {stats['ambas_marcam']['RED']}❌",
                         f"{taxa_am:.1f}%")


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
                
                remaining = response.headers.get('X-Requests-Remaining', 'unknown')
                reset_time = response.headers.get('X-RequestCounter-Reset', 'unknown')
                logging.info(f"✅ Request OK. Restantes: {remaining}, Reset: {reset_time}s")
                
                return response.json()
                
            except requests.exceptions.Timeout:
                logging.error(f"⌛ Timeout na tentativa {attempt+1} para {url}")
                self.api_monitor.log_request(False)
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logging.info(f"⏳ Esperando {wait_time}s antes de retry...")
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
            logging.info(f"📊 Classificação da liga {liga_id} obtida do cache")
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
            logging.info(f"⚽ Jogos {key} obtidos do cache")
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
        if not fixture_id:
            return None
            
        cached = self.match_cache.get(fixture_id)
        if cached:
            logging.info(f"📋 Detalhes do jogo {fixture_id} obtidos do cache")
            return cached
        
        url = f"{self.config.BASE_URL_FD}/matches/{fixture_id}"
        data = self.obter_dados_api(url)
        if data:
            self.match_cache.set(fixture_id, data)
        return data
    
    def baixar_escudo_time(self, team_name: str, crest_url: str) -> bytes | None:
        if not crest_url:
            logging.warning(f"❌ URL do escudo vazia para {team_name}")
            return None
        
        try:
            cached = self.image_cache.get(team_name, crest_url)
            if cached:
                return cached
            
            logging.info(f"⬇️ Baixando escudo de {team_name}: {crest_url}")
            response = requests.get(crest_url, timeout=10)
            response.raise_for_status()
            
            img_bytes = response.content
            
            self.image_cache.set(team_name, crest_url, img_bytes)
            
            logging.info(f"✅ Escudo de {team_name} baixado e armazenado no cache")
            return img_bytes
            
        except requests.RequestException as e:
            logging.error(f"❌ Erro ao baixar escudo de {team_name}: {e}")
            return None
        except Exception as e:
            logging.error(f"❌ Erro inesperado ao baixar escudo de {team_name}: {e}")
            return None
    
    @staticmethod
    def validar_dados_jogo(match: dict) -> bool:
        required_fields = ['id', 'homeTeam', 'awayTeam', 'utcDate']
        
        for field in required_fields:
            if field not in match:
                logging.warning(f"Campo {field} faltando no jogo")
                return False
                
        if 'name' not in match['homeTeam'] or 'name' not in match['awayTeam']:
            logging.warning("Nomes dos times faltando")
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
            logging.error(f"Erro ao convertir data {data_iso}: {e}")
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
            
        except Exception as e:
            logging.error(f"Erro ao carregar fonte: {e}")
            return ImageFont.load_default()
    
    def gerar_poster_westham_style(self, jogos: list, titulo: str = "⚽ ALERTA DE GOLS", tipo_alerta: str = "over_under") -> io.BytesIO:
        LARGURA = 2000
        ALTURA_TOPO = 270
        ALTURA_POR_JOGO = 830
        PADDING = 80
        
        jogos_count = len(jogos)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)

        FONTE_TITULO = self.criar_fonte(85)
        FONTE_SUBTITULO = self.criar_fonte(65)
        FONTE_TIMES = self.criar_fonte(60)
        FONTE_VS = self.criar_fonte(55)
        FONTE_INFO = self.criar_fonte(50)
        FONTE_DETALHES = self.criar_fonte(45)
        FONTE_ANALISE = self.criar_fonte(50)
        FONTE_ODD = self.criar_fonte(65)

        try:
            titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
            titulo_w = titulo_bbox[2] - titulo_bbox[0]
            draw.text(((LARGURA - titulo_w) // 2, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
        except:
            draw.text((LARGURA//2 - 250, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))

        draw.line([(LARGURA//4, 220), (3*LARGURA//4, 220)], fill=(255, 215, 0), width=6)

        y_pos = ALTURA_TOPO

        for idx, jogo_dict in enumerate(jogos):
            x0, y0 = PADDING, y_pos
            x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
            
            if tipo_alerta == "over_under":
                cor_borda = (255, 215, 0) if jogo_dict.get('tipo_aposta') == "over" else (100, 200, 255)
            elif tipo_alerta == "favorito":
                cor_borda = (255, 87, 34)
            elif tipo_alerta == "gols_ht":
                cor_borda = (76, 175, 80)
            elif tipo_alerta == "ambas_marcam":
                cor_borda = (155, 89, 182)
            else:
                cor_borda = (255, 215, 0)
            
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)

            if tipo_alerta == "over_under":
                prob = jogo_dict.get('probabilidade', 50)
                odd_principal = round(100 / prob, 2) if prob > 0 else 2.0
                cor_odd = (255, 215, 0) if jogo_dict.get('tipo_aposta') == "over" else (100, 200, 255)
                
            elif tipo_alerta == "favorito":
                prob_fav = jogo_dict.get('confianca_vitoria', 50)
                odd_principal = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
                cor_odd = (255, 87, 34)
                
            elif tipo_alerta == "gols_ht":
                prob_ht = jogo_dict.get('confianca_ht', 50)
                odd_principal = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
                cor_odd = (76, 175, 80)
                
            elif tipo_alerta == "ambas_marcam":
                prob_am = jogo_dict.get('confianca_ambas_marcam', 50)
                odd_principal = round(100 / prob_am, 2) if prob_am > 0 else 2.0
                cor_odd = (155, 89, 182)
            
            else:
                odd_principal = 2.0
                cor_odd = (255, 215, 0)
            
            odd_text = f"{odd_principal:.2f}"
            
            try:
                odd_bbox = draw.textbbox((0, 0), odd_text, font=FONTE_ODD)
                odd_w = odd_bbox[2] - odd_bbox[0]
                odd_h = odd_bbox[3] - odd_bbox[1]
                
                margem_direita = 40
                margem_topo = 40
                
                odd_x = x1 - odd_w - margem_direita
                odd_y = y0 + margem_topo
                
                fundo_x0 = odd_x - 15
                fundo_y0 = odd_y - 10
                fundo_x1 = odd_x + odd_w + 15
                fundo_y1 = odd_y + odd_h + 10
                
                overlay = Image.new('RGBA', img.size, (0,0,0,0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rectangle([fundo_x0, fundo_y0, fundo_x1, fundo_y1], fill=(0, 0, 0, 200))
                img.paste(overlay, (0,0), overlay)
                
                draw.rectangle([fundo_x0, fundo_y0, fundo_x1, fundo_y1], outline=(255, 215, 0), width=3)
                
                draw.text((odd_x, odd_y), odd_text, font=FONTE_ODD, fill=cor_odd)
                
            except Exception as e:
                logging.error(f"Erro ao desenhar odd: {e}")
                odd_x = x1 - 200
                odd_y = y0 + 40
                draw.text((odd_x, odd_y), odd_text, font=FONTE_ODD, fill=cor_odd)

            liga_text = jogo_dict.get('liga', 'LIGA').upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

            if isinstance(jogo_dict.get("hora"), datetime):
                data_text = jogo_dict["hora"].strftime("%d/%m/%Y %H:%M")
            else:
                data_text = str(jogo_dict.get("hora", "Data desconhecida"))

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

            home_crest_url = jogo_dict.get('escudo_home', '')
            away_crest_url = jogo_dict.get('escudo_away', '')
            
            escudo_home_bytes = None
            escudo_away_bytes = None
            
            if home_crest_url:
                escudo_home_bytes = self.api_client.baixar_escudo_time(jogo_dict.get('home', ''), home_crest_url)
            
            if away_crest_url:
                escudo_away_bytes = self.api_client.baixar_escudo_time(jogo_dict.get('away', ''), away_crest_url)
            
            escudo_home_img = None
            escudo_away_img = None
            
            if escudo_home_bytes:
                try:
                    escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA")
                except Exception as e:
                    logging.error(f"Erro ao abrir escudo do {jogo_dict.get('home', '')}: {e}")
            
            if escudo_away_bytes:
                try:
                    escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA")
                except Exception as e:
                    logging.error(f"Erro ao abrir escudo do {jogo_dict.get('away', '')}: {e}")

            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo_dict.get('home', ''))
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo_dict.get('away', ''))

            home_text = jogo_dict.get('home', 'TIME CASA')[:15]
            away_text = jogo_dict.get('away', 'TIME FORA')[:15]

            try:
                home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 50),
                         home_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 50), home_text, font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 50),
                         away_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 50), away_text, font=FONTE_TIMES, fill=(255, 255, 255))

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
                    f"○ {jogo_dict.get('tendencia', 'N/A')}",
                    f"Confiança: {jogo_dict.get('confianca', 0):.0f}% | Odds: {odd_principal:.2f}",
                ]
                cores = [(200, 200, 200), (100, 255, 100)]
                
            elif tipo_alerta == "favorito":
                favorito = jogo_dict.get('favorito', '')
                if favorito == "home":
                    favorito_text = jogo_dict.get('home', 'CASA')
                elif favorito == "away":
                    favorito_text = jogo_dict.get('away', 'FORA')
                else:
                    favorito_text = "EMPATE"
                
                textos_analise = [
                    f"○ Favorito → {favorito_text}",
                    f"Confiança: {jogo_dict.get('confianca_vitoria', 0):.0f}% | Odds: {odd_principal:.2f}",
                ]
                cores = [(255, 152, 0), (100, 255, 100)]
                
            elif tipo_alerta == "gols_ht":
                textos_analise = [
                    f"○ {jogo_dict.get('tendencia_ht', 'N/A')}",
                    f"Confiança: {jogo_dict.get('confianca_ht', 0):.0f}% | Odds: {odd_principal:.2f}",
                ]
                cores = [(129, 199, 132), (100, 255, 100)]
            
            elif tipo_alerta == "ambas_marcam":
                textos_analise = [
                    f"○ {jogo_dict.get('tendencia_ambas_marcam', 'N/A')}",
                    f"Confiança: {jogo_dict.get('confianca_ambas_marcam', 0):.0f}% | Odds: {odd_principal:.2f}",
                ]
                cores = [(165, 105, 189), (100, 255, 100)]
            
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

        rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - ELITE MASTER SYSTEM"
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
    
    def gerar_poster_resultados(self, jogos_com_resultados: list, tipo_alerta: str = "over_under") -> io.BytesIO:
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
        FONTE_ESTATISTICAS = self.criar_fonte(40)
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
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_width, badge_y + badge_height], 
                          fill=cor_badge, outline=cor_badge, width=2)
            
            try:
                badge_bbox = draw.textbbox((0, 0), resultado_text, font=FONTE_RESULTADO_BADGE)
                badge_text_w = badge_bbox[2] - badge_bbox[0]
                badge_text_h = badge_bbox[3] - badge_bbox[1]
                badge_text_x = badge_x + (badge_width - badge_text_w) // 2
                badge_text_y = badge_y + (badge_height - badge_text_h) // 2
                
                draw.text((badge_text_x + 2, badge_text_y + 2), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=(0, 0, 0, 128))
                
                draw.text((badge_text_x, badge_text_y), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=cor_texto)
                
                draw.rectangle([badge_x-2, badge_y-2, badge_x + badge_width + 2, badge_y + badge_height + 2], 
                              outline=(255, 255, 255), width=1)
                
            except:
                draw.text((badge_x + 80, badge_y + 25), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=cor_texto)

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
            
            escudo_home_bytes = None
            escudo_away_bytes = None
            
            if home_crest_url:
                escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], home_crest_url)
            
            if away_crest_url:
                escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], away_crest_url)
            
            escudo_home_img = None
            escudo_away_img = None
            
            if escudo_home_bytes:
                try:
                    escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA")
                except Exception as e:
                    logging.error(f"Erro ao abrir escudo do {jogo['home']}: {e}")
            
            if escudo_away_bytes:
                try:
                    escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA")
                except Exception as e:
                    logging.error(f"Erro ao abrir escudo do {jogo['away']}: {e}")

            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

            home_text = jogo['home'][:12]
            away_text = jogo['away'][:12]

            try:
                home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 30),
                         home_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 30),
                         home_text, font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 30),
                         away_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 30),
                         away_text, font=FONTE_TIMES, fill=(255, 255, 255))

            resultado_text_score = f"{jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}"
            try:
                resultado_bbox = draw.textbbox((0, 0), resultado_text_score, font=FONTE_RESULTADO)
                resultado_w = resultado_bbox[2] - resultado_bbox[0]
                resultado_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - resultado_w) // 2
                draw.text((resultado_x, y_escudos + TAMANHO_QUADRADO//2 - 40), 
                         resultado_text_score, font=FONTE_RESULTADO, fill=(255, 255, 255))
            except:
                resultado_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                draw.text((resultado_x, y_escudos + TAMANHO_QUADRADO//2 - 40), resultado_text_score, font=FONTE_RESULTADO, fill=(255, 255, 255))

            if jogo.get('ht_home_goals') is not None and jogo.get('ht_away_goals') is not None:
                ht_text = f"HT: {jogo['ht_home_goals']} - {jogo['ht_away_goals']}"
                try:
                    ht_bbox = draw.textbbox((0, 0), ht_text, font=FONTE_INFO)
                    ht_w = ht_bbox[2] - ht_bbox[0]
                    ht_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - ht_w) // 2
                    draw.text((ht_x, y_escudos + TAMANHO_QUADRADO//2 + 40), 
                             ht_text, font=FONTE_INFO, fill=(200, 200, 200))
                except:
                    ht_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                    draw.text((ht_x, y_escudos + TAMANHO_QUADRADO//2 + 40), ht_text, font=FONTE_INFO, fill=(200, 200, 200))

            y_analysis = y_escudos + TAMANHO_QUADRADO + 120
            
            if tipo_alerta == "over_under":
                tipo_emoji = "+" if jogo.get('tipo_aposta') == "over" else "-"
                resultado_emoji = "" if resultado == "GREEN" else "❌" if resultado == "RED" else ""
                
                textos_analise = [
                    f"{tipo_emoji} {jogo['tendencia']} {resultado_emoji}",
                    f"Estimativa: {jogo['estimativa']:.2f} gols | Resultado: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                    f"Probabilidade: {jogo['probabilidade']:.0f}% | Confiança: {jogo['confianca']:.0f}%",
                ]
                
                cores = [(255, 255, 255), (200, 200, 200), (200, 200, 200)]
                
            elif tipo_alerta == "favorito":
                favorito_emoji = "" if jogo.get('favorito') == "home" else "" if jogo.get('favorito') == "away" else "🤝"
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                resultado_emoji = "" if resultado == "GREEN" else "❌" if resultado == "RED" else ""
                
                textos_analise = [
                    f"{favorito_emoji} FAVORITO: {favorito_text} {resultado_emoji}",
                    f"Confiança: {jogo.get('confianca_vitoria', 0):.0f}% | Resultado: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                    f"Prob. Casa: {jogo.get('prob_home_win', 0):.1f}% | Fora: {jogo.get('prob_away_win', 0):.1f}% | Empate: {jogo.get('prob_draw', 0):.1f}%",
                ]
                
                cores = [(255, 255, 255), (200, 200, 200), (200, 200, 200)]
                
            elif tipo_alerta == "gols_ht":
                tipo_emoji_ht = "" if "OVER" in jogo.get('tendencia_ht', '') else ""
                resultado_emoji = "" if resultado == "GREEN" else "❌" if resultado == "RED" else ""
                ht_resultado = f"{jogo.get('ht_home_goals', '?')} - {jogo.get('ht_away_goals', '?')}"
                
                textos_analise = [
                    f"{tipo_emoji_ht} {jogo.get('tendencia_ht', 'N/A')} {resultado_emoji}",
                    f"Estimativa HT: {jogo.get('estimativa_total_ht', 0):.2f} gols | Resultado HT: {ht_resultado}",
                    f"Confiança HT: {jogo.get('confianca_ht', 0):.0f}% | FT: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                ]
                
                cores = [(255, 255, 255), (200, 200, 200), (200, 200, 200)]
            
            elif tipo_alerta == "ambas_marcam":
                tipo_emoji_am = "🤝" if jogo.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                resultado_emoji = "" if resultado == "GREEN" else "❌" if resultado == "RED" else ""
                
                textos_analise = [
                    f"{tipo_emoji_am} AMBAS MARCAM: {jogo.get('tendencia_ambas_marcam', 'N/A')} {resultado_emoji}",
                    f"Probabilidade SIM: {jogo.get('prob_ambas_marcam_sim', 0):.1f}% | NÃO: {jogo.get('prob_ambas_marcam_nao', 0):.1f}%",
                    f"Confiança: {jogo.get('confianca_ambas_marcam', 0):.0f}% | Resultado: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}",
                ]
                
                cores = [(255, 255, 255), (200, 200, 200), (200, 200, 200)]
            
            else:
                textos_analise = [f"Resultado: {resultado}"]
                cores = [(200, 200, 200)]
            
            for i, (text, cor) in enumerate(zip(textos_analise, cores)):
                try:
                    bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                    w = bbox[2] - bbox[0]
                    draw.text(((LARGURA - w) // 2, y_analysis + i * 80), text, font=FONTE_ANALISE, fill=cor)
                except:
                    draw.text((PADDING + 120, y_analysis + i * 80), text, font=FONTE_ANALISE, fill=cor)

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
        
        st.success(f"✅ Poster de resultados GERADO com {len(jogos_com_resultados)} jogos")
        return buffer
    
    def _desenhar_escudo_quadrado(self, draw, img, logo_img, x, y, tamanho_quadrado, tamanho_escudo, team_name=""):
        draw.rectangle(
            [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
            fill=(255, 255, 255),
            outline=(255, 255, 255)
        )

        if logo_img is None:
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
            
            if team_name:
                iniciais = ''.join([palavra[0].upper() for palavra in team_name.split()[:2]])
                if len(iniciais) > 3:
                    iniciais = iniciais[:3]
            else:
                iniciais = "SEM"
            
            try:
                fonte = self.criar_fonte(50)
                bbox = draw.textbbox((0, 0), iniciais, font=fonte)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), 
                         iniciais, font=fonte, fill=(255, 255, 255))
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
                fonte = self.criar_fonte(50)
                bbox = draw.textbbox((0, 0), iniciais, font=fonte)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), 
                         iniciais, font=fonte, fill=(255, 255, 255))
            except:
                draw.text((x + 70, y + 90), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))


# =============================
# SISTEMA PRINCIPAL (COM MELHORIAS)
# =============================

class SistemaAlertasFutebol:
    """Sistema principal de alertas de futebol"""
    
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
        self.analisador_performance = AnalisadorPerformance()
        
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
    
    # =============================
    # [MELHORIA] NOVOS MÉTODOS DE FILTRO PROFISSIONAL
    # =============================
    
    def _calcular_score_profissional(self, probabilidade: float, confianca: float) -> float:
        """Calcula um score combinado para ranquear as apostas."""
        return (probabilidade * 0.7) + (confianca * 0.3)
    
    def _aplicar_filtro_profissional(self, jogos_df: pd.DataFrame, 
                                      prob_min: float = 70.0, 
                                      conf_min: float = 65.0, 
                                      max_apostas: int = 5) -> pd.DataFrame:
        """
        Aplica o filtro profissional a um DataFrame de jogos.
        - Filtra por probabilidade e confiança mínimas.
        - Remove mercados duplicados para o mesmo jogo.
        - Calcula e ordena por score.
        - Limita o número de apostas.
        """
        if jogos_df.empty:
            return jogos_df

        df_filtrado = jogos_df.copy()

        # 1. Filtros de Probabilidade e Confiança
        df_filtrado = df_filtrado[
            (df_filtrado['probabilidade'] >= prob_min) & 
            (df_filtrado['confianca'] >= conf_min)
        ]

        if df_filtrado.empty:
            return df_filtrado

        # 2. Calcular o Score
        df_filtrado['score'] = df_filtrado.apply(
            lambda x: self._calcular_score_profissional(x['probabilidade'], x['confianca']), 
            axis=1
        )

        # 3. Ordenar por Score (do maior para o menor)
        df_filtrado = df_filtrado.sort_values(by='score', ascending=False)

        # 4. Manter apenas o melhor mercado para cada jogo
        if 'jogo_id' not in df_filtrado.columns:
            df_filtrado['jogo_id'] = df_filtrado['home'] + ' vs ' + df_filtrado['away']

        df_filtrado = df_filtrado.drop_duplicates(subset=['jogo_id'], keep='first')

        # 5. Limitar o número de apostas
        df_filtrado = df_filtrado.head(max_apostas)

        return df_filtrado
    
    def processar_jogos(self, data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf, 
                       max_conf, estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                       formato_top_jogos, tipo_filtro, tipo_analise, config_analise):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        
        if todas_ligas:
            ligas_busca = list(self.config.LIGA_DICT.values())
            st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
        else:
            ligas_busca = [self.config.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
            st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

        st.write(f"⏳ Buscando jogos para {data_br}...")
        
        top_jogos = []
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
                st.write(f"📊 Liga BSA: {len(jogos_data)} jogos encontrados")
            else:
                jogos_data = self.api_client.obter_jogos(liga_id, hoje)
                st.write(f"📊 Liga {liga_id}: {len(jogos_data)} jogos encontrados")

            batch_size = 5
            for j in range(0, len(jogos_data), batch_size):
                batch = jogos_data[j:j+batch_size]
                
                for match_data in batch:
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
                    
                    data_br, hora_br = jogo.get_data_hora_brasilia()
                    tipo_emoji = "📈" if analise["tipo_aposta"] == "over" else "📉"
                    
                    st.write(f"   {tipo_emoji} {jogo.home_team} vs {jogo.away_team}")
                    st.write(f"      🕒 {data_br} {hora_br} | {analise['tendencia']}")
                    st.write(f"      ⚽ Estimativa: {analise['estimativa']:.2f} | 🎯 Prob: {analise['probabilidade']:.0f}% | 🔍 Conf: {analise['confianca']:.0f}%")
                    
                    if 'vitoria' in analise['detalhes']:
                        v = analise['detalhes']['vitoria']
                        st.write(f"      🏆 Favorito: {jogo.home_team if v['favorito']=='home' else jogo.away_team if v['favorito']=='away' else 'EMPATE'} ({v['confianca_vitoria']:.1f}%)")
                    
                    if 'gols_ht' in analise['detalhes']:
                        ht = analise['detalhes']['gols_ht']
                        st.write(f"      ⏰ HT: {ht['tendencia_ht']} ({ht['confianca_ht']:.1f}%)")
                    
                    if 'ambas_marcam' in analise['detalhes']:
                        am = analise['detalhes']['ambas_marcam']
                        st.write(f"      🤝 Ambas Marcam: {am['tendencia_ambas_marcam']} ({am['confianca_ambas_marcam']:.1f}%)")
                    
                    st.write(f"      Status: {jogo.status}")
                    
                    if tipo_analise == "Over/Under de Gols":
                        if min_conf <= analise["confianca"] <= max_conf:
                            if tipo_filtro == "Todos" or \
                               (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or \
                               (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                                self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, 
                                                             min_conf, max_conf, "over_under")
                    
                    elif tipo_analise == "Favorito (Vitória)":
                        min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                        filtro_favorito = config_analise.get("filtro_favorito", "Todos")
                        
                        if 'vitoria' in analise['detalhes']:
                            v = analise['detalhes']['vitoria']
                            
                            if v['confianca_vitoria'] >= min_conf_vitoria:
                                send_alert = False
                                if filtro_favorito == "Todos":
                                    send_alert = True
                                elif filtro_favorito == "Casa" and v['favorito'] == "home":
                                    send_alert = True
                                elif filtro_favorito == "Fora" and v['favorito'] == "away":
                                    send_alert = True
                                elif filtro_favorito == "Empate" and v['favorito'] == "draw":
                                    send_alert = True
                                
                                if send_alert:
                                    self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, 
                                                                 min_conf_vitoria, 100, "favorito")
                    
                    elif tipo_analise == "Gols HT (Primeiro Tempo)":
                        min_conf_ht = config_analise.get("min_conf_ht", 60)
                        tipo_ht = config_analise.get("tipo_ht", "OVER 0.5 HT")
                        
                        if 'gols_ht' in analise['detalhes']:
                            ht = analise['detalhes']['gols_ht']
                            
                            if ht['confianca_ht'] >= min_conf_ht and ht['tendencia_ht'] == tipo_ht:
                                self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, 
                                                             min_conf_ht, 100, "gols_ht")
                    
                    elif tipo_analise == "Ambas Marcam (BTTS)":
                        min_conf_am = config_analise.get("min_conf_am", 60)
                        filtro_am = config_analise.get("filtro_am", "Todos")
                        
                        if 'ambas_marcam' in analise['detalhes']:
                            am = analise['detalhes']['ambas_marcam']
                            
                            if am['confianca_ambas_marcam'] >= min_conf_am:
                                send_alert = False
                                if filtro_am == "Todos":
                                    send_alert = True
                                elif filtro_am == "SIM" and am['tendencia_ambas_marcam'] == "SIM":
                                    send_alert = True
                                elif filtro_am == "NÃO" and am['tendencia_ambas_marcam'] == "NÃO":
                                    send_alert = True
                                
                                if send_alert:
                                    self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, 
                                                                 min_conf_am, 100, "ambas_marcam")

                    top_jogos.append(jogo.to_dict())
                
                if j + batch_size < len(jogos_data):
                    time.sleep(0.5)
            
            progress_bar.progress((i + 1) / total_ligas)
        
        jogos_filtrados = self._filtrar_por_tipo_analise(top_jogos, tipo_analise, config_analise)
        
        st.write(f"📊 Total de jogos: {len(top_jogos)}")
        st.write(f"📊 Jogos após filtros: {len(jogos_filtrados)}")
        
        if tipo_analise == "Over/Under de Gols":
            over_jogos = [j for j in jogos_filtrados if j.get("tipo_aposta") == "over"]
            under_jogos = [j for j in jogos_filtrados if j.get("tipo_aposta") == "under"]
            st.write(f"📈 Over: {len(over_jogos)} jogos")
            st.write(f"📉 Under: {len(under_jogos)} jogos")
        elif tipo_analise == "Favorito (Vitória)":
            home_favoritos = [j for j in jogos_filtrados if j.get("favorito") == "home"]
            away_favoritos = [j for j in jogos_filtrados if j.get("favorito") == "away"]
            draw_favoritos = [j for j in jogos_filtrados if j.get("favorito") == "draw"]
            st.write(f"🏠 Favorito Casa: {len(home_favoritos)} jogos")
            st.write(f"✈️ Favorito Fora: {len(away_favoritos)} jogos")
            st.write(f"🤝 Favorito Empate: {len(draw_favoritos)} jogos")
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            ht_over_05 = [j for j in jogos_filtrados if j.get("tendencia_ht") == "OVER 0.5 HT"]
            ht_over_15 = [j for j in jogos_filtrados if j.get("tendencia_ht") == "OVER 1.5 HT"]
            ht_under_05 = [j for j in jogos_filtrados if j.get("tendencia_ht") == "UNDER 0.5 HT"]
            ht_under_15 = [j for j in jogos_filtrados if j.get("tendencia_ht") == "UNDER 1.5 HT"]
            st.write(f"⚡ OVER 0.5 HT: {len(ht_over_05)} jogos")
            st.write(f"⚡ OVER 1.5 HT: {len(ht_over_15)} jogos")
            st.write(f"🛡️ UNDER 0.5 HT: {len(ht_under_05)} jogos")
            st.write(f"🛡️ UNDER 1.5 HT: {len(ht_under_15)} jogos")
        elif tipo_analise == "Ambas Marcam (BTTS)":
            am_sim = [j for j in jogos_filtrados if j.get("tendencia_ambas_marcam") == "SIM"]
            am_nao = [j for j in jogos_filtrados if j.get("tendencia_ambas_marcam") == "NÃO"]
            st.write(f"🤝 SIM (Ambas Marcam): {len(am_sim)} jogos")
            st.write(f"🚫 NÃO (Não Ambas Marcam): {len(am_nao)} jogos")
        
        if jogos_filtrados:
            st.write(f"✅ **Jogos filtrados por {tipo_analise}:**")
            for jogo in jogos_filtrados:
                if tipo_analise == "Over/Under de Gols":
                    tipo_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
                    info_line = f"   {tipo_emoji} {jogo['home']} vs {jogo['away']} - {jogo.get('tendencia', 'N/A')}"
                    info_line += f" | Conf: {jogo.get('confianca', 0):.1f}%"
                elif tipo_analise == "Favorito (Vitória)":
                    favorito_emoji = "🏠" if jogo.get('favorito') == "home" else "✈️" if jogo.get('favorito') == "away" else "🤝"
                    info_line = f"   {favorito_emoji} {jogo['home']} vs {jogo['away']}"
                    info_line += f" | 🏆 Favorito: {jogo['favorito']} ({jogo['confianca_vitoria']:.1f}%)"
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    tipo_emoji_ht = "⚡" if "OVER" in jogo.get('tendencia_ht', '') else "🛡️"
                    info_line = f"   {tipo_emoji_ht} {jogo['home']} vs {jogo['away']}"
                    info_line += f" | ⏰ {jogo['tendencia_ht']} ({jogo.get('confianca_ht', 0):.1f}%)"
                elif tipo_analise == "Ambas Marcam (BTTS)":
                    tipo_emoji_am = "🤝" if jogo.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                    info_line = f"   {tipo_emoji_am} {jogo['home']} vs {jogo['away']}"
                    info_line += f" | {jogo['tendencia_ambas_marcam']} ({jogo.get('confianca_ambas_marcam', 0):.1f}%)"
                
                st.write(info_line)
            
            if tipo_analise == "Over/Under de Gols":
                self._enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf, formato_top_jogos, hoje, "over_under")
            elif tipo_analise == "Favorito (Vitória)":
                min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                self._enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf_vitoria, 100, formato_top_jogos, hoje, "favorito")
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                min_conf_ht = config_analise.get("min_conf_ht", 60)
                self._enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf_ht, 100, formato_top_jogos, hoje, "gols_ht")
            elif tipo_analise == "Ambas Marcam (BTTS)":
                min_conf_am = config_analise.get("min_conf_am", 60)
                self._enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf_am, 100, formato_top_jogos, hoje, "ambas_marcam")
            
            st.success(f"✅ {len(jogos_filtrados)} jogos filtrados por {tipo_analise}")
            
            if alerta_poster:
                st.info("🚨 Enviando alerta de imagem...")
                if estilo_poster == "West Ham (Novo)":
                    self._enviar_alerta_westham_style(jogos_filtrados, tipo_analise, config_analise)
                else:
                    self._enviar_alerta_poster_original(jogos_filtrados, tipo_analise, config_analise)
            else:
                st.info("ℹ️ Alerta com Poster desativado")
        else:
            st.warning(f"⚠️ Nenhum jogo encontrado para {tipo_analise}")
    
    def processar_alertas_completos(self, data_selecionada, ligas_selecionadas, todas_ligas):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        
        if todas_ligas:
            ligas_busca = list(self.config.LIGA_DICT.values())
            st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
        else:
            ligas_busca = [self.config.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
            st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

        st.write(f"⏳ Buscando jogos para {data_br}...")
        
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
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        st.subheader(f"📊 Conferindo Resultados para {data_br}")
        
        resultados_totais = {
            "over_under": self._conferir_resultados_tipo("over_under", hoje),
            "favorito": self._conferir_resultados_tipo("favorito", hoje),
            "gols_ht": self._conferir_resultados_tipo("gols_ht", hoje),
            "ambas_marcam": self._conferir_resultados_tipo("ambas_marcam", hoje)
        }
        
        st.markdown("---")
        st.subheader("📈 RESUMO DE RESULTADOS")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            resultado_ou = resultados_totais["over_under"]
            if resultado_ou:
                greens = sum(1 for r in resultado_ou.values() if r.get("resultado") == "GREEN")
                reds = sum(1 for r in resultado_ou.values() if r.get("resultado") == "RED")
                total = len(resultado_ou)
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("⚽ Over/Under", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        with col2:
            resultado_fav = resultados_totais["favorito"]
            if resultado_fav:
                greens = sum(1 for r in resultado_fav.values() if r.get("resultado_favorito") == "GREEN")
                reds = sum(1 for r in resultado_fav.values() if r.get("resultado_favorito") == "RED")
                total = len(resultado_fav)
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("🏆 Favoritos", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        with col3:
            resultado_ht = resultados_totais["gols_ht"]
            if resultado_ht:
                greens = sum(1 for r in resultado_ht.values() if r.get("resultado_ht") == "GREEN")
                reds = sum(1 for r in resultado_ht.values() if r.get("resultado_ht") == "RED")
                total = len(resultado_ht)
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("⏰ Gols HT", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        with col4:
            resultado_am = resultados_totais["ambas_marcam"]
            if resultado_am:
                greens = sum(1 for r in resultado_am.values() if r.get("resultado_ambas_marcam") == "GREEN")
                reds = sum(1 for r in resultado_am.values() if r.get("resultado_ambas_marcam") == "RED")
                total = len(resultado_am)
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("🤝 Ambas Marcam", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        if any(resultados_totais.values()):
            st.info("🚨 Enviando alertas de resultados automaticamente...")
            self._enviar_alertas_resultados_automaticos(resultados_totais, data_selecionada)
    
    def _conferir_resultados_tipo(self, tipo_alerta: str, data_busca: str) -> dict:
        if tipo_alerta == "over_under":
            alertas = DataStorage.carregar_alertas()
            resultados = DataStorage.carregar_resultados()
        elif tipo_alerta == "favorito":
            alertas = DataStorage.carregar_alertas_favoritos()
            resultados = DataStorage.carregar_resultados_favoritos()
        elif tipo_alerta == "gols_ht":
            alertas = DataStorage.carregar_alertas_gols_ht()
            resultados = DataStorage.carregar_resultados_gols_ht()
        elif tipo_alerta == "ambas_marcam":
            alertas = DataStorage.carregar_alertas_ambas_marcam()
            resultados = DataStorage.carregar_resultados_ambas_marcam()
        else:
            return {}
        
        jogos_com_resultados = {}
        progress_bar = st.progress(0)
        total_alertas = len(alertas)
        
        if total_alertas == 0:
            st.info(f"ℹ️ Nenhum alerta ativo do tipo {tipo_alerta}")
            return {}
        
        st.write(f"🔍 Conferindo {total_alertas} alertas do tipo {tipo_alerta}...")
        
        for idx, (fixture_id, alerta) in enumerate(alertas.items()):
            if alerta.get("conferido", False):
                continue
            
            match_data = self.api_client.obter_detalhes_jogo(fixture_id)
            if not match_data:
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
                
                home_crest = match_data.get("homeTeam", {}).get("crest") or ""
                away_crest = match_data.get("awayTeam", {}).get("crest") or ""
                
                jogo = Jogo({
                    "id": fixture_id,
                    "homeTeam": {"name": alerta.get("home", ""), "crest": home_crest},
                    "awayTeam": {"name": alerta.get("away", ""), "crest": away_crest},
                    "utcDate": alerta.get("hora", ""),
                    "competition": {"name": alerta.get("liga", "")},
                    "status": status
                })
                
                if tipo_alerta == "over_under":
                    jogo.set_analise({
                        "tendencia": alerta.get("tendencia", ""),
                        "estimativa": alerta.get("estimativa", 0.0),
                        "probabilidade": alerta.get("probabilidade", 0.0),
                        "confianca": alerta.get("confianca", 0.0),
                        "tipo_aposta": alerta.get("tipo_aposta", ""),
                        "detalhes": alerta.get("detalhes", {})
                    })
                elif tipo_alerta == "favorito":
                    jogo.set_analise({
                        "detalhes": {
                            "vitoria": {
                                "favorito": alerta.get("favorito", ""),
                                "confianca_vitoria": alerta.get("confianca_vitoria", 0.0),
                                "home_win": alerta.get("prob_home_win", 0.0),
                                "away_win": alerta.get("prob_away_win", 0.0),
                                "draw": alerta.get("prob_draw", 0.0)
                            }
                        }
                    })
                elif tipo_alerta == "gols_ht":
                    jogo.set_analise({
                        "detalhes": {
                            "gols_ht": {
                                "tendencia_ht": alerta.get("tendencia_ht", ""),
                                "confianca_ht": alerta.get("confianca_ht", 0.0),
                                "estimativa_total_ht": alerta.get("estimativa_total_ht", 0.0),
                                "over_05_ht": alerta.get("over_05_ht", 0.0),
                                "over_15_ht": alerta.get("over_15_ht", 0.0)
                            }
                        }
                    })
                elif tipo_alerta == "ambas_marcam":
                    jogo.set_analise({
                        "detalhes": {
                            "ambas_marcam": {
                                "tendencia_ambas_marcam": alerta.get("tendencia_ambas_marcam", ""),
                                "confianca_ambas_marcam": alerta.get("confianca_ambas_marcam", 0.0),
                                "sim": alerta.get("prob_ambas_marcam_sim", 0.0),
                                "nao": alerta.get("prob_ambas_marcam_nao", 0.0)
                            }
                        }
                    })
                
                jogo.set_resultado(home_goals, away_goals, ht_home_goals, ht_away_goals)
                
                if tipo_alerta == "over_under":
                    resultado_analise = jogo.resultado
                elif tipo_alerta == "favorito":
                    resultado_analise = jogo.resultado_favorito
                elif tipo_alerta == "gols_ht":
                    resultado_analise = jogo.resultado_ht
                elif tipo_alerta == "ambas_marcam":
                    resultado_analise = jogo.resultado_ambas_marcam
                else:
                    resultado_analise = "UNKNOWN"
                
                self.analisador_performance.registrar_resultado(
                    alerta, 
                    tipo_alerta, 
                    resultado_analise,
                    {
                        "home_goals": home_goals,
                        "away_goals": away_goals,
                        "ht_home_goals": ht_home_goals,
                        "ht_away_goals": ht_away_goals
                    }
                )
                
                resultados[fixture_id] = jogo.to_dict()
                resultados[fixture_id]["data_conferencia"] = datetime.now().isoformat()
                
                alertas[fixture_id]["conferido"] = True
                
                jogos_com_resultados[fixture_id] = resultados[fixture_id]
                
                if tipo_alerta == "over_under":
                    resultado = jogo.resultado
                    cor = "🟢" if resultado == "GREEN" else "🔴"
                    st.write(f"{cor} {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
                    st.write(f"   📊 {alerta.get('tendencia', '')} | Est: {alerta.get('estimativa', 0):.2f} | Prob: {alerta.get('probabilidade', 0):.0f}% | Conf: {alerta.get('confianca', 0):.0f}%")
                    st.write(f"   🎯 Resultado: {resultado}")
                elif tipo_alerta == "favorito":
                    resultado = jogo.resultado_favorito
                    cor = "🟢" if resultado == "GREEN" else "🔴"
                    favorito = alerta.get('favorito', '')
                    favorito_text = alerta.get('home', '') if favorito == "home" else alerta.get('away', '') if favorito == "away" else "EMPATE"
                    st.write(f"{cor} {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
                    st.write(f"   🏆 Favorito: {favorito_text} | Conf: {alerta.get('confianca_vitoria', 0):.0f}%")
                    st.write(f"   🎯 Resultado: {resultado}")
                elif tipo_alerta == "gols_ht":
                    resultado = jogo.resultado_ht
                    cor = "🟢" if resultado == "GREEN" else "🔴"
                    st.write(f"{cor} {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
                    st.write(f"   ⏰ {alerta.get('tendencia_ht', '')} | Est HT: {alerta.get('estimativa_total_ht', 0):.2f} | Conf HT: {alerta.get('confianca_ht', 0):.0f}%")
                    st.write(f"   🎯 Resultado HT: {resultado} (HT: {ht_home_goals}-{ht_away_goals})")
                elif tipo_alerta == "ambas_marcam":
                    resultado = jogo.resultado_ambas_marcam
                    cor = "🟢" if resultado == "GREEN" else "🔴"
                    st.write(f"{cor} {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
                    st.write(f"   🤝 {alerta.get('tendencia_ambas_marcam', '')} | Conf: {alerta.get('confianca_ambas_marcam', 0):.0f}%")
                    st.write(f"   🎯 Resultado Ambas Marcam: {resultado}")
            
            progress_bar.progress((idx + 1) / total_alertas)
        
        if tipo_alerta == "over_under":
            DataStorage.salvar_alertas(alertas)
            DataStorage.salvar_resultados(resultados)
        elif tipo_alerta == "favorito":
            DataStorage.salvar_alertas_favoritos(alertas)
            DataStorage.salvar_resultados_favoritos(resultados)
        elif tipo_alerta == "gols_ht":
            DataStorage.salvar_alertas_gols_ht(alertas)
            DataStorage.salvar_resultados_gols_ht(resultados)
        elif tipo_alerta == "ambas_marcam":
            DataStorage.salvar_alertas_ambas_marcam(alertas)
            DataStorage.salvar_resultados_ambas_marcam(resultados)
        
        return jogos_com_resultados
    
    def _enviar_alertas_resultados_automaticos(self, resultados_totais: dict, data_selecionada):
        data_str = data_selecionada.strftime("%d/%m/%Y")
        
        for tipo_alerta, resultados in resultados_totais.items():
            if not resultados:
                continue
            
            jogos_lista = list(resultados.values())
            
            batch_size = 3
            for i in range(0, len(jogos_lista), batch_size):
                batch = jogos_lista[i:i+batch_size]
                
                try:
                    if tipo_alerta == "over_under":
                        titulo = f"📊 RESULTADOS OVER/UNDER - Lote {i//batch_size + 1}"
                    elif tipo_alerta == "favorito":
                        titulo = f"🏆 RESULTADOS FAVORITOS - Lote {i//batch_size + 1}"
                    elif tipo_alerta == "gols_ht":
                        titulo = f"⏰ RESULTADOS GOLS HT - Lote {i//batch_size + 1}"
                    elif tipo_alerta == "ambas_marcam":
                        titulo = f"🤝 RESULTADOS AMBAS MARCAM - Lote {i//batch_size + 1}"
                    
                    poster = self.poster_generator.gerar_poster_resultados(batch, tipo_alerta)
                    
                    if tipo_alerta == "over_under":
                        greens = sum(1 for j in batch if j.get("resultado") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado") == "RED")
                    elif tipo_alerta == "favorito":
                        greens = sum(1 for j in batch if j.get("resultado_favorito") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado_favorito") == "RED")
                    elif tipo_alerta == "gols_ht":
                        greens = sum(1 for j in batch if j.get("resultado_ht") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado_ht") == "RED")
                    elif tipo_alerta == "ambas_marcam":
                        greens = sum(1 for j in batch if j.get("resultado_ambas_marcam") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado_ambas_marcam") == "RED")
                    
                    total = greens + reds
                    if total > 0:
                        taxa_acerto = (greens / total) * 100
                        caption = f"<b>{titulo}</b>\n\n"
                        caption += f"<b>📊 LOTE {i//batch_size + 1}: {greens}✅ {reds}❌</b>\n"
                        caption += f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                        caption += f"<b>🔥 ELITE MASTER SYSTEM - RESULTADOS CONFIRMADOS</b>"
                    
                    if self.telegram_client.enviar_foto(poster, caption=caption):
                        st.success(f"📤 Lote {i//batch_size + 1} de resultados {tipo_alerta} enviado ({len(batch)} jogos)")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logging.error(f"Erro ao gerar/enviar poster do lote {i//batch_size + 1}: {e}")
                    st.error(f"❌ Erro no lote {i//batch_size + 1}: {e}")
            
            if jogos_lista:
                self._enviar_resumo_final(tipo_alerta, jogos_lista, data_str)
    
    def _enviar_resumo_final(self, tipo_alerta: str, jogos_lista: list, data_str: str):
        if tipo_alerta == "over_under":
            titulo = f"📊 RESUMO FINAL OVER/UNDER - {data_str}"
            greens = sum(1 for j in jogos_lista if j.get("resultado") == "GREEN")
            reds = sum(1 for j in jogos_lista if j.get("resultado") == "RED")
        elif tipo_alerta == "favorito":
            titulo = f"🏆 RESUMO FINAL FAVORITOS - {data_str}"
            greens = sum(1 for j in jogos_lista if j.get("resultado_favorito") == "GREEN")
            reds = sum(1 for j in jogos_lista if j.get("resultado_favorito") == "RED")
        elif tipo_alerta == "gols_ht":
            titulo = f"⏰ RESUMO FINAL GOLS HT - {data_str}"
            greens = sum(1 for j in jogos_lista if j.get("resultado_ht") == "GREEN")
            reds = sum(1 for j in jogos_lista if j.get("resultado_ht") == "RED")
        elif tipo_alerta == "ambas_marcam":
            titulo = f"🤝 RESUMO FINAL AMBAS MARCAM - {data_str}"
            greens = sum(1 for j in jogos_lista if j.get("resultado_ambas_marcam") == "GREEN")
            reds = sum(1 for j in jogos_lista if j.get("resultado_ambas_marcam") == "RED")
        
        total = greens + reds
        if total > 0:
            taxa_acerto = (greens / total) * 100
            
            msg = f"<b>{titulo}</b>\n\n"
            msg += f"<b>📋 TOTAL DE JOGOS: {len(jogos_lista)}</b>\n"
            msg += f"<b>✅ GREEN: {greens} jogos</b>\n"
            msg += f"<b>❌ RED: {reds} jogos</b>\n"
            msg += f"<b>🎯 TAXA DE ACERTO FINAL: {taxa_acerto:.1f}%</b>\n\n"
            msg += f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE CONFIRMADA</b>"
            
            if self.telegram_client.enviar_mensagem(msg, self.config.TELEGRAM_CHAT_ID_ALT2):
                st.success(f"📊 Resumo final {tipo_alerta} enviado!")
    
    def _verificar_enviar_alerta(self, jogo: Jogo, match_data: dict, analise: dict, alerta_individual: bool, min_conf: int, max_conf: int, tipo_alerta: str):
        if tipo_alerta == "over_under":
            alertas = DataStorage.carregar_alertas()
        elif tipo_alerta == "favorito":
            alertas = DataStorage.carregar_alertas_favoritos()
        elif tipo_alerta == "gols_ht":
            alertas = DataStorage.carregar_alertas_gols_ht()
        elif tipo_alerta == "ambas_marcam":
            alertas = DataStorage.carregar_alertas_ambas_marcam()
        else:
            alertas = {}
        
        fixture_id = str(jogo.id)
        
        if fixture_id not in alertas:
            alerta_data = {
                "id": fixture_id,
                "home": jogo.home_team,
                "away": jogo.away_team,
                "liga": jogo.competition,
                "hora": jogo.get_hora_brasilia_datetime().isoformat(),
                "status": jogo.status,
                "escudo_home": jogo.home_crest,
                "escudo_away": jogo.away_crest,
                "tipo_alerta": tipo_alerta,
                "conferido": False,
                "data_busca": datetime.now().strftime("%Y-%m-%d")
            }
            
            if tipo_alerta == "over_under":
                alerta_data.update({
                    "tendencia": analise.get("tendencia", ""),
                    "estimativa": analise.get("estimativa", 0.0),
                    "probabilidade": analise.get("probabilidade", 0.0),
                    "confianca": analise.get("confianca", 0.0),
                    "tipo_aposta": analise.get("tipo_aposta", ""),
                    "detalhes": analise.get("detalhes", {})
                })
            elif tipo_alerta == "favorito":
                if 'vitoria' in analise.get('detalhes', {}):
                    v = analise['detalhes']['vitoria']
                    alerta_data.update({
                        "favorito": v.get("favorito", ""),
                        "confianca_vitoria": v.get("confianca_vitoria", 0.0),
                        "prob_home_win": v.get("home_win", 0.0),
                        "prob_away_win": v.get("away_win", 0.0),
                        "prob_draw": v.get("draw", 0.0),
                        "detalhes": analise.get("detalhes", {})
                    })
            elif tipo_alerta == "gols_ht":
                if 'gols_ht' in analise.get('detalhes', {}):
                    ht = analise['detalhes']['gols_ht']
                    alerta_data.update({
                        "tendencia_ht": ht.get("tendencia_ht", ""),
                        "confianca_ht": ht.get("confianca_ht", 0.0),
                        "estimativa_total_ht": ht.get("estimativa_total_ht", 0.0),
                        "over_05_ht": ht.get("over_05_ht", 0.0),
                        "over_15_ht": ht.get("over_15_ht", 0.0),
                        "detalhes": analise.get("detalhes", {})
                    })
            elif tipo_alerta == "ambas_marcam":
                if 'ambas_marcam' in analise.get('detalhes', {}):
                    am = analise['detalhes']['ambas_marcam']
                    alerta_data.update({
                        "tendencia_ambas_marcam": am.get("tendencia_ambas_marcam", ""),
                        "confianca_ambas_marcam": am.get("confianca_ambas_marcam", 0.0),
                        "prob_ambas_marcam_sim": am.get("sim", 0.0),
                        "prob_ambas_marcam_nao": am.get("nao", 0.0),
                        "detalhes": analise.get("detalhes", {})
                    })
            
            alertas[fixture_id] = alerta_data
            
            if alerta_individual:
                self._enviar_alerta_individual(match_data, analise, tipo_alerta, min_conf, max_conf)
            
            if tipo_alerta == "over_under":
                DataStorage.salvar_alertas(alertas)
            elif tipo_alerta == "favorito":
                DataStorage.salvar_alertas_favoritos(alertas)
            elif tipo_alerta == "gols_ht":
                DataStorage.salvar_alertas_gols_ht(alertas)
            elif tipo_alerta == "ambas_marcam":
                DataStorage.salvar_alertas_ambas_marcam(alertas)
    
    def _enviar_alerta_individual(self, fixture: dict, analise: dict, tipo_alerta: str, min_conf: int, max_conf: int):
        home = fixture["homeTeam"]["name"]
        away = fixture["awayTeam"]["name"]
        
        if tipo_alerta == "over_under":
            prob = analise.get("probabilidade", 50)
            odd = round(100 / prob, 2) if prob > 0 else 2.0
            tipo_emoji = "🎯" if analise["tipo_aposta"] == "over" else "🛡️"
            caption = (
                f"<b>{tipo_emoji} ALERTA {analise['tipo_aposta'].upper()} DE GOLS</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>📈 Tendência: {analise['tendencia']}</b>\n"
                f"<b>⚽ Estimativa: {analise['estimativa']:.2f} gols</b>\n"
                f"<b>🎯 Probabilidade: {analise['probabilidade']:.0f}%</b>\n"
                f"<b>💰 Odds: {odd:.2f}</b>\n"
                f"<b>🔍 Confiança: {analise['confianca']:.0f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        elif tipo_alerta == "favorito" and 'vitoria' in analise['detalhes']:
            v = analise['detalhes']['vitoria']
            prob_fav = v['confianca_vitoria']
            odd = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
            favorito_emoji = "🏠" if v['favorito'] == "home" else "✈️" if v['favorito'] == "away" else "🤝"
            favorito_text = home if v['favorito'] == "home" else away if v['favorito'] == "away" else "EMPATE"
            
            caption = (
                f"<b>{favorito_emoji} ALERTA DE FAVORITO</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>🏆 Favorito: {favorito_text}</b>\n"
                f"<b>📊 Probabilidade Casa: {v['home_win']:.1f}%</b>\n"
                f"<b>📊 Probabilidade Fora: {v['away_win']:.1f}%</b>\n"
                f"<b>📊 Probabilidade Empate: {v['draw']:.1f}%</b>\n"
                f"<b>💰 Odds: {odd:.2f}</b>\n"
                f"<b>🔍 Confiança: {v['confianca_vitoria']:.1f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        elif tipo_alerta == "gols_ht" and 'gols_ht' in analise['detalhes']:
            ht = analise['detalhes']['gols_ht']
            prob_ht = ht['confianca_ht']
            odd = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
            tipo_emoji_ht = "⚡" if "OVER" in ht['tendencia_ht'] else "🛡️"
            
            caption = (
                f"<b>{tipo_emoji_ht} ALERTA DE GOLS HT</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>⏰ Tendência HT: {ht['tendencia_ht']}</b>\n"
                f"<b>⚽ Estimativa HT: {ht['estimativa_total_ht']:.2f} gols</b>\n"
                f"<b>🎯 OVER 0.5 HT: {ht['over_05_ht']:.0f}%</b>\n"
                f"<b>🎯 OVER 1.5 HT: {ht['over_15_ht']:.0f}%</b>\n"
                f"<b>💰 Odds: {odd:.2f}</b>\n"
                f"<b>🔍 Confiança HT: {ht['confianca_ht']:.1f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        elif tipo_alerta == "ambas_marcam" and 'ambas_marcam' in analise['detalhes']:
            am = analise['detalhes']['ambas_marcam']
            prob_am = am['confianca_ambas_marcam']
            odd = round(100 / prob_am, 2) if prob_am > 0 else 2.0
            tipo_emoji_am = "🤝" if am['tendencia_ambas_marcam'] == "SIM" else "🚫"
            
            caption = (
                f"<b>{tipo_emoji_am} ALERTA AMBAS MARCAM</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>🤝 Tendência: {am['tendencia_ambas_marcam']}</b>\n"
                f"<b>📊 Probabilidade SIM: {am['sim']:.1f}%</b>\n"
                f"<b>📊 Probabilidade NÃO: {am['nao']:.1f}%</b>\n"
                f"<b>💰 Odds: {odd:.2f}</b>\n"
                f"<b>🔍 Confiança: {am['confianca_ambas_marcam']:.1f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        else:
            return
        
        try:
            img = Image.new("RGB", (800, 400), color=(10, 20, 30))
            draw = ImageDraw.Draw(img)
            fonte = self.poster_generator.criar_fonte(30)
            
            if tipo_alerta == "over_under":
                tipo_text = f"ALERTA {analise['tipo_aposta'].upper()}"
                cor_titulo = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
            elif tipo_alerta == "favorito":
                tipo_text = "ALERTA FAVORITO"
                cor_titulo = (255, 87, 34)
            elif tipo_alerta == "gols_ht":
                tipo_text = "ALERTA GOLS HT"
                cor_titulo = (76, 175, 80)
            elif tipo_alerta == "ambas_marcam":
                tipo_text = "ALERTA AMBAS MARCAM"
                cor_titulo = (155, 89, 182)
            
            draw.text((50, 50), tipo_text, font=fonte, fill=cor_titulo)
            draw.text((50, 100), f"{home} vs {away}", font=fonte, fill=(255, 255, 255))
            
            if tipo_alerta == "over_under":
                draw.text((50, 150), f"Tendência: {analise['tendencia']}", font=fonte, fill=(100, 200, 255))
                draw.text((50, 200), f"Confiança: {analise['confianca']:.0f}% | Odds: {odd:.2f}", font=fonte, fill=(100, 255, 100))
            elif tipo_alerta == "favorito" and 'vitoria' in analise['detalhes']:
                v = analise['detalhes']['vitoria']
                draw.text((50, 150), f"Favorito: {home if v['favorito']=='home' else away if v['favorito']=='away' else 'EMPATE'}", font=fonte, fill=(255, 193, 7))
                draw.text((50, 200), f"Confiança: {v['confianca_vitoria']:.1f}% | Odds: {odd:.2f}", font=fonte, fill=(100, 255, 100))
            elif tipo_alerta == "gols_ht" and 'gols_ht' in analise['detalhes']:
                ht = analise['detalhes']['gols_ht']
                draw.text((50, 150), f"HT: {ht['tendencia_ht']}", font=fonte, fill=(100, 200, 255))
                draw.text((50, 200), f"Confiança: {ht['confianca_ht']:.1f}% | Odds: {odd:.2f}", font=fonte, fill=(100, 255, 100))
            elif tipo_alerta == "ambas_marcam" and 'ambas_marcam' in analise['detalhes']:
                am = analise['detalhes']['ambas_marcam']
                draw.text((50, 150), f"Tendência: {am['tendencia_ambas_marcam']}", font=fonte, fill=(100, 200, 255))
                draw.text((50, 200), f"Confiança: {am['confianca_ambas_marcam']:.1f}% | Odds: {odd:.2f}", font=fonte, fill=(100, 255, 100))
            
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            if self.telegram_client.enviar_foto(buffer, caption=caption):
                st.success(f"📤 Alerta {tipo_alerta} individual enviado: {home} vs {away}")
            else:
                self.telegram_client.enviar_mensagem(caption, self.config.TELEGRAM_CHAT_ID_ALT2)
                st.success(f"📤 Alerta {tipo_alerta} individual (texto) enviado: {home} vs {away}")
        except Exception as e:
            logging.error(f"Erro ao enviar alerta individual: {e}")
            self.telegram_client.enviar_mensagem(caption, self.config.TELEGRAM_CHAT_ID_ALT2)
    
    def _filtrar_por_tipo_analise(self, jogos, tipo_analise, config):
        if tipo_analise == "Over/Under de Gols":
            min_conf = config.get("min_conf", 70)
            max_conf = config.get("max_conf", 95)
            tipo_filtro = config.get("tipo_filtro", "Todos")
            
            jogos_filtrados = [
                j for j in jogos
                if min_conf <= j.get("confianca", 0) <= max_conf and 
                j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
            ]
            
            if tipo_filtro == "Apenas Over":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("tipo_aposta") == "over"]
            elif tipo_filtro == "Apenas Under":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("tipo_aposta") == "under"]
            
            return jogos_filtrados
        
        elif tipo_analise == "Favorito (Vitória)":
            min_conf_vitoria = config.get("min_conf_vitoria", 65)
            filtro_favorito = config.get("filtro_favorito", "Todos")
            
            jogos_filtrados = [
                j for j in jogos
                if j.get("confianca_vitoria", 0) >= min_conf_vitoria and
                j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
            ]
            
            if filtro_favorito == "Casa":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("favorito") == "home"]
            elif filtro_favorito == "Fora":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("favorito") == "away"]
            elif filtro_favorito == "Empate":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("favorito") == "draw"]
            
            return jogos_filtrados
        
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            min_conf_ht = config.get("min_conf_ht", 60)
            tipo_ht = config.get("tipo_ht", "OVER 0.5 HT")
            
            jogos_filtrados = [
                j for j in jogos
                if j.get("confianca_ht", 0) >= min_conf_ht and
                j.get("tendencia_ht") == tipo_ht and
                j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
            ]
            
            return jogos_filtrados
        
        elif tipo_analise == "Ambas Marcam (BTTS)":
            min_conf_am = config.get("min_conf_am", 60)
            filtro_am = config.get("filtro_am", "Todos")
            
            jogos_filtrados = [
                j for j in jogos
                if j.get("confianca_ambas_marcam", 0) >= min_conf_am and
                j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
            ]
            
            if filtro_am == "SIM":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("tendencia_ambas_marcam") == "SIM"]
            elif filtro_am == "NÃO":
                jogos_filtrados = [j for j in jogos_filtrados if j.get("tendencia_ambas_marcam") == "NÃO"]
            
            return jogos_filtrados
        
        return jogos
    
    def _enviar_top_jogos(self, jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf, formato_top_jogos, data_busca, tipo_alerta="over_under"):
        if not alerta_top_jogos:
            st.info("ℹ️ Alerta de Top Jogos desativado")
            return
        
        jogos_elegiveis = [j for j in jogos_filtrados if j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
        
        if tipo_alerta == "over_under":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j.get("confianca", 0) <= max_conf]
        elif tipo_alerta == "favorito":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j.get("confianca_vitoria", 0) <= max_conf]
        elif tipo_alerta == "gols_ht":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j.get("confianca_ht", 0) <= max_conf]
        elif tipo_alerta == "ambas_marcam":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j.get("confianca_ambas_marcam", 0) <= max_conf]
        
        if not jogos_elegiveis:
            st.warning(f"⚠️ Nenhum jogo elegível para o Top Jogos.")
            return
        
        # [MELHORIA] APLICAR FILTRO PROFISSIONAL
        import pandas as pd
        df_jogos = pd.DataFrame(jogos_elegiveis)

        # Garantir que as colunas necessárias existem
        if 'probabilidade' not in df_jogos.columns:
            df_jogos['probabilidade'] = 0.0
        if 'confianca' not in df_jogos.columns:
            df_jogos['confianca'] = 0.0

        # Aplicar o filtro profissional
        PROBABILIDADE_MINIMA_PARA_TOP = 70.0 
        
        df_top_filtrado = self._aplicar_filtro_profissional(
            df_jogos, 
            prob_min=PROBABILIDADE_MINIMA_PARA_TOP, 
            conf_min=min_conf,
            max_apostas=top_n
        )

        if df_top_filtrado.empty:
            st.warning(f"⚠️ Nenhum jogo passou no filtro profissional com confiança >={min_conf}% e probabilidade >={PROBABILIDADE_MINIMA_PARA_TOP}%.")
            return

        top_jogos_sorted = df_top_filtrado.to_dict('records')
        # FIM DA MELHORIA

        for jogo in top_jogos_sorted:
            alerta = Alerta(Jogo({
                "id": jogo["id"],
                "homeTeam": {"name": jogo["home"]},
                "awayTeam": {"name": jogo["away"]},
                "utcDate": jogo["hora"].isoformat() if isinstance(jogo["hora"], datetime) else "",
                "competition": {"name": jogo["liga"]},
                "status": jogo["status"]
            }), data_busca, tipo_alerta)
            
            alerta.jogo.set_analise({
                "tendencia": jogo.get("tendencia", ""),
                "estimativa": jogo.get("estimativa", 0.0),
                "probabilidade": jogo.get("probabilidade", 0.0),
                "confianca": jogo.get("confianca", 0.0),
                "tipo_aposta": jogo.get("tipo_aposta", ""),
                "detalhes": jogo.get("detalhes", {})
            })
            
            self._salvar_alerta_top(alerta)
        
        if formato_top_jogos in ["Texto", "Ambos"]:
            data_br = datetime.now().strftime("%d/%m/%Y")
            
            if tipo_alerta == "over_under":
                msg = f"📢 TOP {top_n} Jogos Over/Under (confiança: {min_conf}%-{max_conf}%) - {data_br}\n\n"
            elif tipo_alerta == "favorito":
                msg = f"🏆 TOP {top_n} Jogos Favoritos (confiança: {min_conf}%+) - {data_br}\n\n"
            elif tipo_alerta == "gols_ht":
                msg = f"⏰ TOP {top_n} Jogos Gols HT (confiança: {min_conf}%+) - {data_br}\n\n"
            elif tipo_alerta == "ambas_marcam":
                msg = f"🤝 TOP {top_n} Jogos Ambas Marcam (confiança: {min_conf}%+) - {data_br}\n\n"
            
            for idx, jogo in enumerate(top_jogos_sorted, 1):
                hora_format = jogo["hora"].strftime("%H:%M") if isinstance(jogo["hora"], datetime) else str(jogo["hora"])
                
                if tipo_alerta == "over_under":
                    tipo_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
                    prob = jogo.get('probabilidade', 50)
                    odd = round(100 / prob, 2) if prob > 0 else 2.0
                    msg += (
                        f"{idx}. {tipo_emoji} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   {jogo['tendencia']} | ⚽ {jogo['estimativa']:.2f} | "
                        f"🎯 {jogo['probabilidade']:.0f}% | 💯 {jogo['confianca']:.0f}% | 💰 {odd:.2f}\n\n"
                    )
                elif tipo_alerta == "favorito":
                    favorito_emoji = "🏠" if jogo.get('favorito') == "home" else "✈️" if jogo.get('favorito') == "away" else "🤝"
                    favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                    prob_fav = jogo.get('confianca_vitoria', 50)
                    odd = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
                    msg += (
                        f"{idx}. {favorito_emoji} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   🏆 Favorito: {favorito_text} | "
                        f"💯 {jogo.get('confianca_vitoria', 0):.0f}% | 💰 {odd:.2f}\n"
                        f"   📊 Casa: {jogo.get('prob_home_win', 0):.1f}% | "
                        f"Fora: {jogo.get('prob_away_win', 0):.1f}% | "
                        f"Empate: {jogo.get('prob_draw', 0):.1f}%\n\n"
                    )
                elif tipo_alerta == "gols_ht":
                    tipo_emoji_ht = "⚡" if "OVER" in jogo.get('tendencia_ht', '') else "🛡️"
                    prob_ht = jogo.get('confianca_ht', 50)
                    odd = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
                    msg += (
                        f"{idx}. {tipo_emoji_ht} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   ⏰ {jogo.get('tendencia_ht', 'N/A')} | "
                        f"⚽ {jogo.get('estimativa_total_ht', 0):.2f} gols | "
                        f"💯 {jogo.get('confianca_ht', 0):.0f}% | 💰 {odd:.2f}\n"
                        f"   🎯 OVER 0.5: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_05_ht', 0):.0f}% | "
                        f"OVER 1.5: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_15_ht', 0):.0f}%\n\n"
                    )
                elif tipo_alerta == "ambas_marcam":
                    tipo_emoji_am = "🤝" if jogo.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                    prob_am = jogo.get('confianca_ambas_marcam', 50)
                    odd = round(100 / prob_am, 2) if prob_am > 0 else 2.0
                    msg += (
                        f"{idx}. {tipo_emoji_am} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   🤝 {jogo.get('tendencia_ambas_marcam', 'N/A')} | "
                        f"💯 {jogo.get('confianca_ambas_marcam', 0):.0f}% | 💰 {odd:.2f}\n"
                        f"   📊 SIM: {jogo.get('prob_ambas_marcam_sim', 0):.1f}% | "
                        f"NÃO: {jogo.get('prob_ambas_marcam_nao', 0):.1f}%\n\n"
                    )
            
            if self.telegram_client.enviar_mensagem(msg, self.config.TELEGRAM_CHAT_ID_ALT2):
                st.success(f"📝 Texto dos TOP {len(top_jogos_sorted)} jogos enviado!")
        
        if formato_top_jogos in ["Poster", "Ambos"]:
            try:
                data_br = datetime.now().strftime("%d/%m/%Y")
                
                if tipo_alerta == "over_under":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS OVER/UNDER - {data_br}"
                elif tipo_alerta == "favorito":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS FAVORITOS - {data_br}"
                elif tipo_alerta == "gols_ht":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS GOLS HT - {data_br}"
                elif tipo_alerta == "ambas_marcam":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS AMBAS MARCAM - {data_br}"
                
                poster = self.poster_generator.gerar_poster_westham_style(
                    top_jogos_sorted, 
                    titulo=titulo,
                    tipo_alerta=tipo_alerta
                )
                
                if tipo_alerta == "over_under":
                    caption = f"<b>📊 TOP {len(top_jogos_sorted)} JOGOS OVER/UNDER - {data_br}</b>\n"
                    caption += f"<b> Intervalo de Confiança: {min_conf}% - {max_conf}%</b>\n\n"
                elif tipo_alerta == "favorito":
                    caption = f"<b>🏆 TOP {len(top_jogos_sorted)} JOGOS FAVORITOS - {data_br}</b>\n"
                    caption += f"<b> Confiança Mínima: {min_conf}%</b>\n\n"
                elif tipo_alerta == "gols_ht":
                    caption = f"<b>⏰ TOP {len(top_jogos_sorted)} JOGOS GOLS HT - {data_br}</b>\n"
                    caption += f"<b> Confiança Mínima: {min_conf}%</b>\n\n"
                elif tipo_alerta == "ambas_marcam":
                    caption = f"<b>🤝 TOP {len(top_jogos_sorted)} JOGOS AMBAS MARCAM - {data_br}</b>\n"
                    caption += f"<b> Confiança Mínima: {min_conf}%</b>\n\n"
                
                caption += f"<b>🔥 ELITE MASTER SYSTEM - JOGOS COM MAIOR POTENCIAL</b>"
                
                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"🖼️ Poster dos TOP {len(top_jogos_sorted)} jogos enviado!")
            except Exception as e:
                logging.error(f"Erro ao gerar poster TOP jogos: {e}")
                st.error(f"❌ Erro ao gerar poster: {e}")
    
    def _salvar_alerta_top(self, alerta: Alerta):
        alertas_top = DataStorage.carregar_alertas_top()
        chave = f"{alerta.jogo.id}_{alerta.data_busca}_{alerta.tipo_alerta}"
        alertas_top[chave] = alerta.to_dict()
        DataStorage.salvar_alertas_top(alertas_top)
    
    #def _enviar_alerta_westham_style(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
    def _enviar_alerta_westham_style(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
        if not jogos_conf:
            st.warning("⚠️ Nenhum jogo para gerar poster")
        return
    
    try:
        # Agrupar jogos por data
        jogos_por_data = {}
        for jogo in jogos_conf:
            data = jogo["hora"].date() if isinstance(jogo["hora"], datetime) else datetime.now().date()
            if data not in jogos_por_data:
                jogos_por_data[data] = []
            jogos_por_data[data].append(jogo)

        for data, jogos_data in jogos_por_data.items():
            data_br = data.strftime("%d/%m/%Y")
            
            # Dividir em lotes de 3 jogos
            lotes = [jogos_data[i:i+3] for i in range(0, len(jogos_data), 3)]
            total_lotes = len(lotes)
            
            st.info(f"📦 Dividindo {len(jogos_data)} jogos em {total_lotes} lotes de até 3 jogos cada")
            
            for idx, lote in enumerate(lotes, 1):
                if tipo_analise == "Over/Under de Gols":
                    titulo = f"ELITE MASTER - OVER/UNDER - {data_br} (Lote {idx}/{total_lotes})"
                    tipo_alerta = "over_under"
                elif tipo_analise == "Favorito (Vitória)":
                    titulo = f"ELITE MASTER - FAVORITOS - {data_br} (Lote {idx}/{total_lotes})"
                    tipo_alerta = "favorito"
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    titulo = f"ELITE MASTER - GOLS HT - {data_br} (Lote {idx}/{total_lotes})"
                    tipo_alerta = "gols_ht"
                elif tipo_analise == "Ambas Marcam (BTTS)":
                    titulo = f"ELITE MASTER - AMBAS MARCAM - {data_br} (Lote {idx}/{total_lotes})"
                    tipo_alerta = "ambas_marcam"
                else:
                    titulo = f"ELITE MASTER - ALERTAS - {data_br} (Lote {idx}/{total_lotes})"
                    tipo_alerta = "over_under"
                
                st.info(f"🎨 Gerando poster lote {idx}/{total_lotes} com {len(lote)} jogos...")
                
                poster = self.poster_generator.gerar_poster_westham_style(lote, titulo=titulo, tipo_alerta=tipo_alerta)
                
                if tipo_analise == "Over/Under de Gols":
                    over_count = sum(1 for j in lote if j.get('tipo_aposta') == "over")
                    under_count = sum(1 for j in lote if j.get('tipo_aposta') == "under")
                    min_conf = config_analise.get("min_conf", 70)
                    max_conf = config_analise.get("max_conf", 95)
                    
                    caption = (
                        f"<b>🎯 ALERTA OVER/UNDER - {data_br}</b>\n\n"
                        f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                        f"<b>📈 Over: {over_count} jogos</b>\n"
                        f"<b>📉 Under: {under_count} jogos</b>\n"
                        f"<b>⚽ INTERVALO DE CONFIANÇA: {min_conf}% - {max_conf}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE PREDITIVA</b>"
                    )
                elif tipo_analise == "Favorito (Vitória)":
                    min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                    
                    caption = (
                        f"<b>🏆 ALERTA DE FAVORITOS - {data_br}</b>\n\n"
                        f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                        f"<b>🎯 CONFIANÇA MÍNIMA: {min_conf_vitoria}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE DE VITÓRIA</b>"
                    )
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    min_conf_ht = config_analise.get("min_conf_ht", 60)
                    tipo_ht = config_analise.get("tipo_ht", "OVER 0.5 HT")
                    
                    caption = (
                        f"<b>⏰ ALERTA DE GOLS HT - {data_br}</b>\n\n"
                        f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                        f"<b>🎯 TIPO: {tipo_ht}</b>\n"
                        f"<b>🔍 CONFIANÇA MÍNIMA: {min_conf_ht}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE DO PRIMEIRO TEMPO</b>"
                    )
                elif tipo_analise == "Ambas Marcam (BTTS)":
                    min_conf_am = config_analise.get("min_conf_am", 60)
                    filtro_am = config_analise.get("filtro_am", "Todos")
                    
                    caption = (
                        f"<b>🤝 ALERTA AMBAS MARCAM - {data_br}</b>\n\n"
                        f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                        f"<b>🎯 FILTRO: {filtro_am}</b>\n"
                        f"<b>🔍 CONFIANÇA MÍNIMA: {min_conf_am}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE BTTS</b>"
                    )
                else:
                    caption = (
                        f"<b>⚽ ALERTA DE JOGOS - {data_br}</b>\n\n"
                        f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM</b>"
                    )
                
                st.info(f"📤 Enviando lote {idx}/{total_lotes} para o Telegram...")
                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"🚀 Poster lote {idx}/{total_lotes} enviado para {data_br}!")
                else:
                    st.error(f"❌ Falha ao enviar poster lote {idx}/{total_lotes} para {data_br}")
                
                # Pequena pausa entre envios para não sobrecarregar
                if idx < total_lotes:
                    time.sleep(2)
                    
    except Exception as e:
        logging.error(f"Erro crítico ao gerar/enviar poster West Ham: {str(e)}")
        st.error(f"❌ Erro crítico ao gerar/enviar poster: {str(e)}")
        
        # Obter a data do primeiro jogo ou usar data atual
        if jogos_conf and len(jogos_conf) > 0:
            primeiro_jogo = jogos_conf[0]
            if isinstance(primeiro_jogo.get("hora"), datetime):
                data_br_fallback = primeiro_jogo["hora"].strftime("%d/%m/%Y")
            else:
                data_br_fallback = datetime.now().strftime("%d/%m/%Y")
        else:
            data_br_fallback = datetime.now().strftime("%d/%m/%Y")
        
        # Fallback: enviar como texto em lotes
        st.info(f"📝 Enviando alertas como texto em lotes para {data_br_fallback}...")
        
        # Dividir em lotes de 5 para texto
        lotes_texto = [jogos_conf[i:i+5] for i in range(0, len(jogos_conf), 5)]
        
        for idx, lote in enumerate(lotes_texto, 1):
            if tipo_analise == "Over/Under de Gols":
                msg_lote = f"<b>📊 ALERTA OVER/UNDER - {data_br_fallback} (Lote {idx}/{len(lotes_texto)})</b>\n\n"
            elif tipo_analise == "Favorito (Vitória)":
                msg_lote = f"<b>🏆 ALERTA FAVORITOS - {data_br_fallback} (Lote {idx}/{len(lotes_texto)})</b>\n\n"
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                msg_lote = f"<b>⏰ ALERTA GOLS HT - {data_br_fallback} (Lote {idx}/{len(lotes_texto)})</b>\n\n"
            elif tipo_analise == "Ambas Marcam (BTTS)":
                msg_lote = f"<b>🤝 ALERTA AMBAS MARCAM - {data_br_fallback} (Lote {idx}/{len(lotes_texto)})</b>\n\n"
            else:
                msg_lote = f"<b>⚽ ALERTA DE JOGOS - {data_br_fallback} (Lote {idx}/{len(lotes_texto)})</b>\n\n"
            
            for j in lote:
                if tipo_analise == "Over/Under de Gols":
                    tipo_emoji = "📈" if j.get('tipo_aposta') == "over" else "📉"
                    prob = j.get('probabilidade', 50)
                    odd = round(100 / prob, 2) if prob > 0 else 2.0
                    msg_lote += f"{tipo_emoji} <b>{j['home']} vs {j['away']}</b>\n"
                    msg_lote += f"   📊 {j['tendencia']} | Conf: {j['confianca']:.0f}% | Odds: {odd:.2f}\n"
                    msg_lote += f"   🕒 {j.get('hora', '').strftime('%H:%M') if isinstance(j.get('hora'), datetime) else j.get('hora', '')} BRT | {j.get('liga', '')}\n\n"
                elif tipo_analise == "Favorito (Vitória)":
                    favorito_emoji = "🏠" if j.get('favorito') == "home" else "✈️" if j.get('favorito') == "away" else "🤝"
                    prob_fav = j.get('confianca_vitoria', 50)
                    odd = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
                    favorito_text = j['home'] if j.get('favorito') == "home" else j['away'] if j.get('favorito') == "away" else "EMPATE"
                    msg_lote += f"{favorito_emoji} <b>{j['home']} vs {j['away']}</b>\n"
                    msg_lote += f"   🏆 Favorito: {favorito_text} | Conf: {j['confianca_vitoria']:.1f}% | Odds: {odd:.2f}\n"
                    msg_lote += f"   🕒 {j.get('hora', '').strftime('%H:%M') if isinstance(j.get('hora'), datetime) else j.get('hora', '')} BRT | {j.get('liga', '')}\n\n"
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    tipo_emoji_ht = "⚡" if "OVER" in j.get('tendencia_ht', '') else "🛡️"
                    prob_ht = j.get('confianca_ht', 50)
                    odd = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
                    msg_lote += f"{tipo_emoji_ht} <b>{j['home']} vs {j['away']}</b>\n"
                    msg_lote += f"   ⏰ {j['tendencia_ht']} | Conf: {j['confianca_ht']:.0f}% | Odds: {odd:.2f}\n"
                    msg_lote += f"   🕒 {j.get('hora', '').strftime('%H:%M') if isinstance(j.get('hora'), datetime) else j.get('hora', '')} BRT | {j.get('liga', '')}\n\n"
                elif tipo_analise == "Ambas Marcam (BTTS)":
                    tipo_emoji_am = "🤝" if j.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                    prob_am = j.get('confianca_ambas_marcam', 50)
                    odd = round(100 / prob_am, 2) if prob_am > 0 else 2.0
                    msg_lote += f"{tipo_emoji_am} <b>{j['home']} vs {j['away']}</b>\n"
                    msg_lote += f"   🤝 {j['tendencia_ambas_marcam']} | Conf: {j['confianca_ambas_marcam']:.1f}% | Odds: {odd:.2f}\n"
                    msg_lote += f"   🕒 {j.get('hora', '').strftime('%H:%M') if isinstance(j.get('hora'), datetime) else j.get('hora', '')} BRT | {j.get('liga', '')}\n\n"
            
            msg_lote += f"<b>🔥 ELITE MASTER SYSTEM - LOTE {idx}/{len(lotes_texto)}</b>"
            
            self.telegram_client.enviar_mensagem(msg_lote, self.config.TELEGRAM_CHAT_ID_ALT2)
            st.info(f"📤 Lote {idx}/{len(lotes_texto)} enviado como texto")
            time.sleep(1)
    
        
    
    def _enviar_alerta_poster_original(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
        if not jogos_conf:
            return
        
        try:
            data_br = datetime.now().strftime("%d/%m/%Y")
            
            if tipo_analise == "Over/Under de Gols":
                over_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "over"]
                under_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "under"]
                
                msg = f"🔥 Jogos Over/Under (Estilo Original) - {data_br}:\n\n"
                
                if over_jogos:
                    msg += f"📈 <b>OVER ({len(over_jogos)} jogos):</b>\n\n"
                    for j in over_jogos:
                        hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                        prob = j.get('probabilidade', 50)
                        odd = round(100 / prob, 2) if prob > 0 else 2.0
                        msg += (
                            f"🏟️ {j['home']} vs {j['away']}\n"
                            f"🕒 {hora_format} BRT | {j['liga']}\n"
                            f"📈 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}% | 💰 {odd:.2f}\n\n"
                        )
                
                if under_jogos:
                    msg += f"📉 <b>UNDER ({len(under_jogos)} jogos):</b>\n\n"
                    for j in under_jogos:
                        hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                        prob = j.get('probabilidade', 50)
                        odd = round(100 / prob, 2) if prob > 0 else 2.0
                        msg += (
                            f"🏟️ {j['home']} vs {j['away']}\n"
                            f"🕒 {hora_format} BRT | {j['liga']}\n"
                            f"📉 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 🎯 {j['probabilidade']:.0f}% | 💯 {j['confianca']:.0f}% | 💰 {odd:.2f}\n\n"
                        )
            
            elif tipo_analise == "Favorito (Vitória)":
                msg = f"🏆 Jogos Favoritos (Estilo Original) - {data_br}:\n\n"
                
                for j in jogos_conf:
                    hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                    favorito_emoji = "🏠" if j.get('favorito') == "home" else "✈️" if j.get('favorito') == "away" else "🤝"
                    favorito_text = j['home'] if j.get('favorito') == "home" else j['away'] if j.get('favorito') == "away" else "EMPATE"
                    prob_fav = j.get('confianca_vitoria', 50)
                    odd = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
                    
                    msg += (
                        f"{favorito_emoji} {j['home']} vs {j['away']}\n"
                        f"🕒 {hora_format} BRT | {j['liga']}\n"
                        f"🏆 Favorito: {favorito_text} | 💯 {j.get('confianca_vitoria', 0):.1f}% | 💰 {odd:.2f}\n"
                        f"📊 Casa: {j.get('prob_home_win', 0):.1f}% | "
                        f"Fora: {j.get('prob_away_win', 0):.1f}% | "
                        f"Empate: {j.get('prob_draw', 0):.1f}%\n\n"
                    )
            
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                msg = f"⏰ Jogos Gols HT (Estilo Original) - {data_br}:\n\n"
                
                for j in jogos_conf:
                    hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                    tipo_emoji_ht = "⚡" if "OVER" in j.get('tendencia_ht', '') else "🛡️"
                    prob_ht = j.get('confianca_ht', 50)
                    odd = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
                    
                    msg += (
                        f"{tipo_emoji_ht} {j['home']} vs {j['away']}\n"
                        f"🕒 {hora_format} BRT | {j['liga']}\n"
                        f"⏰ {j.get('tendencia_ht', 'N/A')} | ⚽ {j.get('estimativa_total_ht', 0):.2f} gols | "
                        f"💯 {j.get('confianca_ht', 0):.0f}% | 💰 {odd:.2f}\n"
                        f"🎯 OVER 0.5: {j.get('detalhes', {}).get('gols_ht', {}).get('over_05_ht', 0):.0f}% | "
                        f"OVER 1.5: {j.get('detalhes', {}).get('gols_ht', {}).get('over_15_ht', 0):.0f}%\n\n"
                    )
            
            elif tipo_analise == "Ambas Marcam (BTTS)":
                msg = f"🤝 Jogos Ambas Marcam (Estilo Original) - {data_br}:\n\n"
                
                for j in jogos_conf:
                    hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                    tipo_emoji_am = "🤝" if j.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                    prob_am = j.get('confianca_ambas_marcam', 50)
                    odd = round(100 / prob_am, 2) if prob_am > 0 else 2.0
                    
                    msg += (
                        f"{tipo_emoji_am} {j['home']} vs {j['away']}\n"
                        f"🕒 {hora_format} BRT | {j['liga']}\n"
                        f"🤝 {j.get('tendencia_ambas_marcam', 'N/A')} | "
                        f"💯 {j.get('confianca_ambas_marcam', 0):.0f}% | 💰 {odd:.2f}\n"
                        f"📊 SIM: {j.get('prob_ambas_marcam_sim', 0):.1f}% | "
                        f"NÃO: {j.get('prob_ambas_marcam_nao', 0):.1f}%\n\n"
                    )
            
            self.telegram_client.enviar_mensagem(msg, self.config.TELEGRAM_CHAT_ID_ALT2)
            st.success("📤 Alerta enviado (formato texto)")
        except Exception as e:
            logging.error(f"Erro no envio de alerta original: {e}")
            st.error(f"Erro no envio: {e}")
    
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
    st.set_page_config(
        page_title="⚽ Elite Master",
        page_icon="⚽",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
    <style>
        /* Reset e ajustes mobile */
        .stApp {
            background-color: #0a0c10;
        }
        
        .main > div {
            padding: 0.5rem 1rem;
        }
        
        /* TÍTULO PRINCIPAL - ESTILO PREMIUM */
        .title-container {
            text-align: center;
            margin: 1.5rem 0 2rem 0;
            padding: 0.5rem;
            background: linear-gradient(180deg, rgba(255,215,0,0.05) 0%, transparent 100%);
            border-radius: 30px;
        }
        
        .main-title {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-bottom: 5px;
        }
        
        .title-icon {
            font-size: 3rem;
            filter: drop-shadow(0 8px 16px rgba(255,215,0,0.3));
            animation: float 3s ease-in-out infinite;
        }
        
        .title-icon.left {
            transform: scaleX(-1);
        }
        
        @keyframes float {
            0% { transform: translateY(0px) scaleX(-1); }
            50% { transform: translateY(-5px) scaleX(-1); }
            100% { transform: translateY(0px) scaleX(-1); }
        }
        
        @keyframes float-right {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-5px); }
            100% { transform: translateY(0px); }
        }
        
        .title-icon.right {
            animation: float-right 3s ease-in-out infinite;
        }
        
        .title-text {
            text-align: center;
        }
        
        .title-futebol {
            font-size: 2.2rem;
            font-weight: 900;
            background: linear-gradient(135deg, #FFD700 0%, #FFA500 50%, #FFD700 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 4px;
            text-shadow: 0 4px 12px rgba(255,215,0,0.3);
            line-height: 1.2;
        }
        
        .title-elite {
            font-size: 1.4rem;
            font-weight: 800;
            background: linear-gradient(135deg, #FFFFFF 0%, #E0E0E0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 3px;
            margin-top: -5px;
            text-shadow: 0 2px 8px rgba(255,255,255,0.2);
        }
        
        .title-master {
            font-size: 1rem;
            font-weight: 600;
            color: #8E9AAB;
            letter-spacing: 6px;
            margin-top: -5px;
            text-transform: uppercase;
        }
        
        .title-decoration {
            width: 150px;
            height: 3px;
            background: linear-gradient(90deg, transparent, #FFD700, #FFA500, #FFD700, transparent);
            margin: 15px auto 0 auto;
            border-radius: 3px;
        }
        
        /* Cards de jogo */
        .mobile-card {
            background: linear-gradient(145deg, #1a1f2c 0%, #151a26 100%);
            border-radius: 16px;
            padding: 1rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(255,215,0,0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.8rem;
            font-size: 0.8rem;
            color: #8e9aab;
        }
        
        .liga-badge {
            background: rgba(255,215,0,0.1);
            color: #ffd700;
            padding: 0.2rem 0.8rem;
            border-radius: 12px;
            font-weight: 600;
        }
        
        .times-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 0.8rem 0;
        }
        
        .time-box {
            text-align: center;
            flex: 1;
        }
        
        .time-nome {
            color: white;
            font-weight: 600;
            font-size: 0.9rem;
            margin-top: 0.3rem;
        }
        
        .placar-box {
            text-align: center;
            padding: 0 1rem;
        }
        
        .placar {
            font-size: 1.8rem;
            font-weight: 800;
            color: #ffd700;
        }
        
        .analise-row {
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            padding: 0.8rem;
            margin-top: 0.8rem;
            font-size: 0.9rem;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
            margin-top: 0.8rem;
        }
        
        .info-item {
            text-align: center;
            background: rgba(255,215,0,0.05);
            padding: 0.5rem;
            border-radius: 8px;
        }
        
        .info-label {
            color: #8e9aab;
            font-size: 0.7rem;
        }
        
        .info-value {
            color: white;
            font-weight: 700;
            font-size: 1rem;
        }
        
        .green-text { color: #4caf50; }
        .red-text { color: #f44336; }
        .gold-text { color: #ffd700; }
        
        /* Abas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            background: #1a1f2c;
            padding: 0.3rem;
            border-radius: 30px;
        }
        
        .stTabs [data-baseweb="tab"] {
            border-radius: 30px;
            padding: 0.5rem 1rem;
            font-size: 0.8rem;
        }
        
        /* Métricas */
        .metric-card {
            background: #1a1f2c;
            border-radius: 12px;
            padding: 1rem;
            text-align: center;
            border: 1px solid rgba(255,215,0,0.1);
        }
        
        .metric-value {
            font-size: 1.5rem;
            font-weight: 800;
            color: #ffd700;
        }
        
        .metric-label {
            color: #8e9aab;
            font-size: 0.8rem;
        }
        
        /* Botões */
        .stButton button {
            width: 100%;
            border-radius: 30px;
            background: linear-gradient(135deg, #ffd700 0%, #ffa500 100%);
            color: #0a0c10;
            font-weight: 700;
            border: none;
            padding: 0.6rem 1rem;
        }
        
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(255,215,0,0.2);
        }
        
        /* Inputs */
        .stDateInput input {
            background: #1a1f2c;
            border: 1px solid rgba(255,215,0,0.2);
            border-radius: 30px;
            color: white;
        }
        
        .stSelectbox div[data-baseweb="select"] {
            background: #1a1f2c;
            border-radius: 30px;
        }
        
        /* Checkboxes */
        .stCheckbox {
            background: #1a1f2c;
            padding: 0.5rem;
            border-radius: 12px;
            margin: 0.2rem 0;
        }
        
        /* Sliders */
        .stSlider div[data-baseweb="slider"] {
            padding-top: 1rem;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: #1a1f2c;
            border-radius: 12px;
            color: white;
        }
        
        .streamlit-expanderContent {
            background: #1a1f2c;
            border-radius: 0 0 12px 12px;
            padding: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="title-container">
        <div class="main-title">
            <span class="title-icon left">⚽</span>
            <div class="title-text">
                <div class="title-futebol">FUTEBOL</div>
                <div class="title-elite">ELITE MASTER</div>
                <div class="title-master">PREMIUM</div>
            </div>
            <span class="title-icon right">🏆</span>
        </div>
        <div class="title-decoration"></div>
    </div>
    """, unsafe_allow_html=True)
    
    sistema = SistemaAlertasFutebol()
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar", "📊 Resultados", "🏆 TOP", "⚽ Completos"])
    
    with tab1:
        render_tab_busca(sistema)
    
    with tab2:
        render_tab_resultados(sistema)
    
    with tab3:
        render_tab_top_alertas(sistema)
    
    with tab4:
        render_tab_completos(sistema)
    
    with st.expander("📊 Monitoramento", expanded=False):
        stats = sistema.api_monitor.get_stats()
        cache_stats = sistema.image_cache.get_stats()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Requests", stats['total_requests'])
        col2.metric("Sucesso", f"{stats['success_rate']}%")
        col3.metric("Cache", f"{cache_stats['memoria']} img")


def render_tab_busca(sistema):
    st.subheader("🔍 Buscar Partidas")
    
    data_selecionada = st.date_input(
        "📅 Data para análise",
        value=datetime.today(),
        format="DD/MM/YYYY"
    )
    
    tipo_analise = st.selectbox(
        "🎯 Tipo de Análise",
        ["Over/Under de Gols", "Favorito (Vitória)", "Gols HT (Primeiro Tempo)", "Ambas Marcam (BTTS)"],
        key="tipo_analise_busca"
    )
    
    config_analise = {}
    
    if tipo_analise == "Over/Under de Gols":
        col1, col2 = st.columns(2)
        with col1:
            min_conf = st.slider("Conf. Mínima %", 10, 95, 70, key="min_conf_ou")
        with col2:
            max_conf = st.slider("Conf. Máxima %", min_conf, 95, 95, key="max_conf_ou")
        
        tipo_filtro = st.selectbox(
            "Filtrar por Tipo",
            ["Todos", "Apenas Over", "Apenas Under"],
            key="filtro_ou"
        )
        
        config_analise = {
            "tipo_filtro": tipo_filtro,
            "min_conf": min_conf,
            "max_conf": max_conf
        }
    
    elif tipo_analise == "Favorito (Vitória)":
        min_conf_vitoria = st.slider("Confiança Mínima %", 50, 95, 65, key="min_conf_fav")
        filtro_favorito = st.selectbox(
            "Filtrar Favorito",
            ["Todos", "Casa", "Fora", "Empate"],
            key="filtro_fav"
        )
        
        config_analise = {
            "min_conf_vitoria": min_conf_vitoria,
            "filtro_favorito": filtro_favorito
        }
    
    elif tipo_analise == "Gols HT (Primeiro Tempo)":
        min_conf_ht = st.slider("Confiança Mínima %", 50, 95, 60, key="min_conf_ht")
        tipo_ht = st.selectbox(
            "Tipo de HT",
            ["OVER 0.5 HT", "OVER 1.5 HT", "UNDER 0.5 HT", "UNDER 1.5 HT"],
            key="tipo_ht"
        )
        
        config_analise = {
            "min_conf_ht": min_conf_ht,
            "tipo_ht": tipo_ht
        }
    
    elif tipo_analise == "Ambas Marcam (BTTS)":
        min_conf_am = st.slider("Confiança Mínima %", 50, 95, 60, key="min_conf_am")
        filtro_am = st.selectbox(
            "Filtrar",
            ["Todos", "SIM", "NÃO"],
            key="filtro_am"
        )
        
        config_analise = {
            "min_conf_am": min_conf_am,
            "filtro_am": filtro_am
        }
    
    st.markdown("### 📨 Tipos de Envio")
    
    col1, col2 = st.columns(2)
    with col1:
        alerta_individual = st.checkbox("🎯 Individuais", value=True, key="ind_busca")
        alerta_poster = st.checkbox("📊 Poster", value=True, key="poster_busca")
    
    with col2:
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True, key="top_busca")
    
    formato_top_jogos = st.selectbox(
        "📋 Formato Top Jogos",
        ["Ambos", "Texto", "Poster"],
        key="formato_top"
    )
    
    estilo_poster = st.selectbox(
        "🎨 Estilo do Poster",
        ["West Ham (Novo)", "Elite Master (Original)"],
        key="estilo_poster"
    )
    
    todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_busca")
    
    ligas_selecionadas = []
    if not todas_ligas:
        ligas_selecionadas = st.multiselect(
            "📌 Selecionar ligas",
            options=list(ConfigManager.LIGA_DICT.keys()),
            default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"]
        )
    
    top_n = st.selectbox("📊 Quantidade no Top", [3, 5, 10], index=1, key="top_n")
    
    if st.button("🔍 BUSCAR PARTIDAS", type="primary", use_container_width=True):
        if not todas_ligas and not ligas_selecionadas:
            st.error("❌ Selecione pelo menos uma liga")
        else:
            with st.spinner("Analisando partidas..."):
                sistema.processar_jogos(
                    data_selecionada,
                    ligas_selecionadas,
                    todas_ligas,
                    top_n,
                    config_analise.get("min_conf", 70),
                    config_analise.get("max_conf", 95),
                    estilo_poster,
                    alerta_individual,
                    alerta_poster,
                    alerta_top_jogos,
                    formato_top_jogos,
                    config_analise.get("tipo_filtro", "Todos"),
                    tipo_analise,
                    config_analise
                )


def render_tab_resultados(sistema):
    st.subheader("📊 Conferir Resultados")
    
    data_resultados = st.date_input(
        "📅 Data para conferência",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_resultados_conf"
    )
    
    if st.button("🔄 CONFERIR RESULTADOS", type="primary", use_container_width=True):
        with st.spinner("Conferindo resultados..."):
            sistema.conferir_resultados(data_resultados)
    
    st.markdown("### 📈 Estatísticas dos Alertas")
    
    alertas_ou = DataStorage.carregar_alertas()
    alertas_fav = DataStorage.carregar_alertas_favoritos()
    alertas_ht = DataStorage.carregar_alertas_gols_ht()
    alertas_am = DataStorage.carregar_alertas_ambas_marcam()
    
    resultados_ou = DataStorage.carregar_resultados()
    resultados_fav = DataStorage.carregar_resultados_favoritos()
    resultados_ht = DataStorage.carregar_resultados_gols_ht()
    resultados_am = DataStorage.carregar_resultados_ambas_marcam()
    
    col1, col2 = st.columns(2)
    
    with col1:
        total_ou = len(alertas_ou)
        conferidos_ou = sum(1 for a in alertas_ou.values() if a.get("conferido", False))
        greens_ou = sum(1 for r in resultados_ou.values() if r.get("resultado") == "GREEN")
        reds_ou = sum(1 for r in resultados_ou.values() if r.get("resultado") == "RED")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">⚽ {total_ou}</div>
            <div class="metric-label">Over/Under</div>
            <div style="font-size:0.8rem; margin-top:0.3rem;">
                <span class="green-text">✅ {greens_ou}</span> | 
                <span class="red-text">❌ {reds_ou}</span> | 
                <span>📊 {conferidos_ou}/{total_ou}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_fav = len(alertas_fav)
        conferidos_fav = sum(1 for a in alertas_fav.values() if a.get("conferido", False))
        greens_fav = sum(1 for r in resultados_fav.values() if r.get("resultado_favorito") == "GREEN")
        reds_fav = sum(1 for r in resultados_fav.values() if r.get("resultado_favorito") == "RED")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">🏆 {total_fav}</div>
            <div class="metric-label">Favoritos</div>
            <div style="font-size:0.8rem; margin-top:0.3rem;">
                <span class="green-text">✅ {greens_fav}</span> | 
                <span class="red-text">❌ {reds_fav}</span> | 
                <span>📊 {conferidos_fav}/{total_fav}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    col3, col4 = st.columns(2)
    
    with col3:
        total_ht = len(alertas_ht)
        conferidos_ht = sum(1 for a in alertas_ht.values() if a.get("conferido", False))
        greens_ht = sum(1 for r in resultados_ht.values() if r.get("resultado_ht") == "GREEN")
        reds_ht = sum(1 for r in resultados_ht.values() if r.get("resultado_ht") == "RED")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">⏰ {total_ht}</div>
            <div class="metric-label">Gols HT</div>
            <div style="font-size:0.8rem; margin-top:0.3rem;">
                <span class="green-text">✅ {greens_ht}</span> | 
                <span class="red-text">❌ {reds_ht}</span> | 
                <span>📊 {conferidos_ht}/{total_ht}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        total_am = len(alertas_am)
        conferidos_am = sum(1 for a in alertas_am.values() if a.get("conferido", False))
        greens_am = sum(1 for r in resultados_am.values() if r.get("resultado_ambas_marcam") == "GREEN")
        reds_am = sum(1 for r in resultados_am.values() if r.get("resultado_ambas_marcam") == "RED")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">🤝 {total_am}</div>
            <div class="metric-label">Ambas Marcam</div>
            <div style="font-size:0.8rem; margin-top:0.3rem;">
                <span class="green-text">✅ {greens_am}</span> | 
                <span class="red-text">❌ {reds_am}</span> | 
                <span>📊 {conferidos_am}/{total_am}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_tab_top_alertas(sistema):
    st.subheader("🏆 Resultados TOP Alertas")
    
    data_top = st.date_input(
        "📅 Data para conferência TOP",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_top"
    )
    
    if st.button("🏆 CONFERIR RESULTADOS TOP", type="primary", use_container_width=True):
        with st.spinner("Conferindo TOP alertas..."):
            sistema.resultados_top.conferir_resultados_top_alertas(data_top)
    
    st.markdown("### 📊 Estatísticas TOP Alertas")
    
    alertas_top = DataStorage.carregar_alertas_top()
    
    if alertas_top:
        top_ou = [a for a in alertas_top.values() if a.get("tipo_alerta") == "over_under"]
        top_fav = [a for a in alertas_top.values() if a.get("tipo_alerta") == "favorito"]
        top_ht = [a for a in alertas_top.values() if a.get("tipo_alerta") == "gols_ht"]
        top_am = [a for a in alertas_top.values() if a.get("tipo_alerta") == "ambas_marcam"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">⚽ {len(top_ou)}</div>
                <div class="metric-label">TOP Over/Under</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">⏰ {len(top_ht)}</div>
                <div class="metric-label">TOP Gols HT</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">🏆 {len(top_fav)}</div>
                <div class="metric-label">TOP Favoritos</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">🤝 {len(top_am)}</div>
                <div class="metric-label">TOP Ambas Marcam</div>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("🗑️ Limpar Alertas TOP Antigos", use_container_width=True):
            sistema._limpar_alertas_top_antigos()
            st.rerun()
    else:
        st.info("ℹ️ Nenhum alerta TOP salvo ainda.")


def render_tab_completos(sistema):
    st.subheader("⚽ Alertas Completos - ALL IN ONE")
    st.caption("Todas as análises em um único poster")
    
    data_completa = st.date_input(
        "📅 Data para análise completa",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_completa"
    )
    
    todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_completa")
    
    ligas_selecionadas = []
    if not todas_ligas:
        ligas_selecionadas = st.multiselect(
            "📌 Selecionar ligas",
            options=list(ConfigManager.LIGA_DICT.keys()),
            default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"],
            key="ligas_completa"
        )
    
    if st.button("⚽ GERAR ALERTAS COMPLETOS", type="primary", use_container_width=True):
        if not todas_ligas and not ligas_selecionadas:
            st.error("❌ Selecione pelo menos uma liga")
        else:
            with st.spinner("Gerando alertas completos..."):
                sistema.processar_alertas_completos(data_completa, ligas_selecionadas, todas_ligas)
    
    st.markdown("---")
    
    st.subheader("📊 Conferir Resultados Completos")
    
    data_resultados_comp = st.date_input(
        "📅 Data para conferência completa",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_resultados_comp"
    )
    
    if st.button("🔄 CONFERIR RESULTADOS COMPLETOS", use_container_width=True):
        with st.spinner("Conferindo resultados..."):
            sistema.gerenciador_completo.conferir_resultados_completos(data_resultados_comp)
    
    st.markdown("### 📊 Estatísticas Completos")
    
    alertas_comp = sistema.gerenciador_completo.carregar_alertas()
    
    if alertas_comp:
        total = len(alertas_comp)
        conferidos = sum(1 for a in alertas_comp.values() if a.get("conferido", False))
        enviados = sum(1 for a in alertas_comp.values() if a.get("alerta_enviado", False))
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📋 Total", total)
        col2.metric("✅ Conferidos", conferidos)
        col3.metric("📤 Enviados", enviados)
        
        with st.expander("📋 Últimos Alertas"):
            for chave, alerta in list(alertas_comp.items())[:3]:
                st.write(f"**{alerta.get('home')} vs {alerta.get('away')}**")
                st.write(f"📅 {alerta.get('data_busca')} | 📤 {alerta.get('alerta_enviado', False)}")
                st.write("---")
    else:
        st.info("ℹ️ Nenhum alerta completo salvo ainda.")


if __name__ == "__main__":
    main()
