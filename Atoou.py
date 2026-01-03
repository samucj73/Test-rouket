
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
from threading import Lock, Thread
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import asyncio

# Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps

# =============================
# Configurações e Segurança
# =============================

# Versão de teste - manter valores padrão
API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","8351165117:AAFmqb3NrPsmT86_8C360eYzK71Qda1ah_4")
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

# NOVO: Arquivo para salvar alertas TOP
ALERTAS_TOP_PATH = "alertas_top.json"

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
# Sistema de Rate Limiting e Cache (OTIMIZADO)
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

class SmartCacheEnhanced:
    """Cache inteligente aprimorado com estatísticas"""
    def __init__(self, cache_type: str):
        self.cache = {}
        self.timestamps = {}
        self.config = CACHE_CONFIG.get(cache_type, {"ttl": 3600, "max_size": 100})
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.size_history = deque(maxlen=100)
        self.hit_history = deque(maxlen=100)
        
    def get(self, key: str):
        """Obtém valor do cache se ainda for válido"""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
                
            timestamp = self.timestamps.get(key, 0)
            agora = time.time()
            
            if agora - timestamp > self.config["ttl"]:
                # Expirou, remove do cache
                del self.cache[key]
                del self.timestamps[key]
                self.misses += 1
                return None
                
            self.hits += 1
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
            
            # Atualizar histórico
            self.size_history.append(len(self.cache))
            hit_rate = self.hits / max(self.hits + self.misses, 1)
            self.hit_history.append(hit_rate)
    
    def clear(self):
        """Limpa todo o cache"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0
    
    def auto_cleanup(self):
        """Limpeza automática baseada no TTL"""
        with self.lock:
            agora = time.time()
            expired_keys = []
            for key, timestamp in list(self.timestamps.items()):
                if agora - timestamp > self.config["ttl"]:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                del self.timestamps[key]
            
            if expired_keys:
                logging.info(f"🧹 Cache {self.__class__.__name__}: {len(expired_keys)} itens expirados removidos")
    
    def get_stats_enhanced(self):
        """Estatísticas detalhadas do cache"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            
            return {
                "total_requests": total,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "current_size": len(self.cache),
                "max_size": self.config["max_size"],
                "usage_percent": f"{(len(self.cache) / self.config['max_size']) * 100:.1f}%",
                "avg_hit_rate_last_100": f"{sum(self.hit_history)/max(len(self.hit_history),1)*100:.1f}%" if self.hit_history else "0%"
            }

# Inicializar caches aprimorados
jogos_cache = SmartCacheEnhanced("jogos")
classificacao_cache = SmartCacheEnhanced("classificacao")
match_cache = SmartCacheEnhanced("match_details")

# =============================
# Sistema de Monitoramento de Performance (NOVO)
# =============================

class PerformanceMonitor:
    """Monitora performance do sistema completo"""
    
    def __init__(self):
        self.start_time = time.time()
        self.operation_times = {}
        self.operation_counts = {}
        self.errors = []
        self.warnings = []
        self.lock = threading.Lock()
        
    def start_operation(self, operation_name: str):
        """Inicia medição de uma operação"""
        return time.time()
        
    def end_operation(self, operation_name: str, start_time: float):
        """Finaliza medição de uma operação"""
        duration = time.time() - start_time
        
        with self.lock:
            if operation_name not in self.operation_times:
                self.operation_times[operation_name] = []
                self.operation_counts[operation_name] = 0
            
            self.operation_times[operation_name].append(duration)
            self.operation_counts[operation_name] += 1
            
            # Mantém apenas as últimas 1000 medições
            if len(self.operation_times[operation_name]) > 1000:
                self.operation_times[operation_name] = self.operation_times[operation_name][-1000:]
    
    def log_error(self, error_msg: str, operation: str = ""):
        """Registra erro"""
        with self.lock:
            self.errors.append({
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "operation": operation
            })
            if len(self.errors) > 100:
                self.errors = self.errors[-100:]
    
    def log_warning(self, warning_msg: str, operation: str = ""):
        """Registra warning"""
        with self.lock:
            self.warnings.append({
                "timestamp": datetime.now().isoformat(),
                "warning": warning_msg,
                "operation": operation
            })
            if len(self.warnings) > 100:
                self.warnings = self.warnings[-100:]
    
    def get_performance_summary(self):
        """Retorna resumo de performance"""
        with self.lock:
            summary = {
                "uptime_minutes": round((time.time() - self.start_time) / 60, 1),
                "operations": {}
            }
            
            for op_name, times in self.operation_times.items():
                if times:
                    summary["operations"][op_name] = {
                        "count": self.operation_counts[op_name],
                        "avg_ms": round(sum(times) / len(times) * 1000, 2),
                        "p95_ms": round(sorted(times)[int(len(times) * 0.95)] * 1000, 2),
                        "max_ms": round(max(times) * 1000, 2),
                        "min_ms": round(min(times) * 1000, 2)
                    }
            
            summary["errors_count"] = len(self.errors)
            summary["warnings_count"] = len(self.warnings)
            
            return summary
            
    def get_slow_operations(self, threshold_ms: float = 1000):
        """Identifica operações lentas"""
        slow_ops = []
        with self.lock:
            for op_name, times in self.operation_times.items():
                if times and (sum(times) / len(times) * 1000) > threshold_ms:
                    slow_ops.append({
                        "operation": op_name,
                        "avg_ms": round(sum(times) / len(times) * 1000, 2),
                        "count": self.operation_counts[op_name]
                    })
        return slow_ops

# Instância global do monitor de performance
performance_monitor = PerformanceMonitor()

# Decorator para medição automática
def measure_performance(operation_name):
    """Decorator para medir performance de funções"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = performance_monitor.start_operation(operation_name)
            try:
                result = func(*args, **kwargs)
                performance_monitor.end_operation(operation_name, start_time)
                return result
            except Exception as e:
                performance_monitor.log_error(str(e), operation_name)
                performance_monitor.end_operation(operation_name, start_time)
                raise
        return wrapper
    return decorator

# =============================
# Sistema de Fallback Inteligente para API (NOVO)
# =============================

class APIFallbackSystem:
    """Sistema inteligente de fallback para falhas de API"""
    
    def __init__(self):
        self.api_status = {}
        self.fallback_data = {}
        self.failure_count = {}
        self.last_success = {}
        self.lock = threading.Lock()
        
    def register_api_endpoint(self, endpoint: str, fallback_data=None):
        """Registra um endpoint da API"""
        with self.lock:
            self.api_status[endpoint] = "healthy"
            self.failure_count[endpoint] = 0
            self.last_success[endpoint] = time.time()
            if fallback_data:
                self.fallback_data[endpoint] = fallback_data
    
    def report_success(self, endpoint: str):
        """Reporta sucesso na chamada"""
        with self.lock:
            self.api_status[endpoint] = "healthy"
            self.failure_count[endpoint] = 0
            self.last_success[endpoint] = time.time()
    
    def report_failure(self, endpoint: str):
        """Reporta falha na chamada"""
        with self.lock:
            self.failure_count[endpoint] = self.failure_count.get(endpoint, 0) + 1
            
            if self.failure_count[endpoint] > 3:
                self.api_status[endpoint] = "unhealthy"
                logging.warning(f"⚠️ Endpoint {endpoint} marcado como unhealthy")
    
    def should_use_fallback(self, endpoint: str) -> bool:
        """Decide se deve usar fallback"""
        with self.lock:
            if self.api_status.get(endpoint) == "unhealthy":
                return True
            if self.failure_count.get(endpoint, 0) >= 3:
                return True
            return False
    
    def get_fallback_data(self, endpoint: str, func_name: str = None):
        """Obtém dados de fallback"""
        with self.lock:
            if endpoint in self.fallback_data:
                return self.fallback_data[endpoint]
            
            # Fallback inteligente
            if endpoint.startswith("/competitions/") and "standings" in endpoint:
                return {"standings": []}
            elif endpoint.startswith("/competitions/") and "matches" in endpoint:
                return {"matches": []}
            elif endpoint.startswith("/matches/"):
                if func_name == "verificar_resultados_finais":
                    return {"match": {"status": "SCHEDULED"}}
                return {"match": {}}
            
            return {}
    
    def get_status_report(self):
        """Relatório de status dos endpoints"""
        with self.lock:
            report = {
                "healthy_endpoints": 0,
                "unhealthy_endpoints": 0,
                "total_endpoints": len(self.api_status),
                "details": {}
            }
            
            for endpoint, status in self.api_status.items():
                report["details"][endpoint] = {
                    "status": status,
                    "failure_count": self.failure_count.get(endpoint, 0),
                    "last_success": time.time() - self.last_success.get(endpoint, 0) if self.last_success.get(endpoint) else None
                }
                
                if status == "healthy":
                    report["healthy_endpoints"] += 1
                else:
                    report["unhealthy_endpoints"] += 1
            
            return report

# Instância global do sistema de fallback
api_fallback = APIFallbackSystem()

# Registrar endpoints importantes
api_fallback.register_api_endpoint("/competitions/{id}/standings")
api_fallback.register_api_endpoint("/competitions/{id}/matches")
api_fallback.register_api_endpoint("/matches/{id}")

# =============================
# Cache de Imagens Aprimorado (OTIMIZADO)
# =============================

class ImageCacheEnhanced:
    """Cache de imagens aprimorado com compressão e priorização"""
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.max_size = 200
        self.ttl = 86400 * 7  # 7 dias
        self.lock = threading.Lock()
        self.cache_dir = "escudos_cache"
        self.compression_level = 85
        self.priority_queue = {}
        self.access_count = {}
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
    
    def get(self, team_name: str, crest_url: str) -> bytes | None:
        """Obtém escudo do cache com priorização"""
        key = self._generate_key(team_name, crest_url)
        
        # Atualizar contador de acessos
        with self.lock:
            self.access_count[key] = self.access_count.get(key, 0) + 1
        
        cached_img = self._get_from_cache(key)
        
        if cached_img:
            with self.lock:
                self.priority_queue[key] = time.time()
            
            # Aplicar compressão se imagem for muito grande
            if len(cached_img) > 50000:
                try:
                    compressed = self._compress_image(cached_img, key)
                    if compressed and len(compressed) < len(cached_img) * 0.7:
                        with self.lock:
                            self.cache[key] = compressed
                        return compressed
                except Exception as e:
                    logging.debug(f"Erro ao comprimir imagem {key}: {e}")
        
        return cached_img
    
    def _get_from_cache(self, key: str) -> bytes | None:
        """Obtém imagem do cache (método interno)"""
        with self.lock:
            if key in self.cache:
                if time.time() - self.timestamps[key] <= self.ttl:
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.timestamps[key]
                    self.priority_queue.pop(key, None)
                    self.access_count.pop(key, None)
            
            file_path = os.path.join(self.cache_dir, f"{key}.png")
            if os.path.exists(file_path):
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age <= self.ttl:
                    try:
                        with open(file_path, "rb") as f:
                            img_data = f.read()
                        self.cache[key] = img_data
                        self.timestamps[key] = time.time()
                        self.priority_queue[key] = time.time()
                        self.access_count[key] = 1
                        return img_data
                    except Exception:
                        pass
        
        return None
    
    def _compress_image(self, img_bytes: bytes, key: str) -> bytes | None:
        """Comprime imagem se possível"""
        try:
            img = Image.open(io.BytesIO(img_bytes))
            buffer = io.BytesIO()
            
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            img.save(buffer, format='JPEG', quality=self.compression_level, optimize=True)
            return buffer.getvalue()
        except Exception:
            return None
    
    def set(self, team_name: str, crest_url: str, img_bytes: bytes):
        """Armazena escudo no cache com compressão inteligente"""
        key = self._generate_key(team_name, crest_url)
        
        # Tentar comprimir se imagem for grande
        if len(img_bytes) > 100000:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                buffer = io.BytesIO()
                
                if img.mode == 'RGBA':
                    img.save(buffer, format='PNG', optimize=True)
                else:
                    img = img.convert('RGB')
                    img.save(buffer, format='JPEG', quality=self.compression_level, optimize=True)
                
                compressed_bytes = buffer.getvalue()
                if len(compressed_bytes) < len(img_bytes):
                    img_bytes = compressed_bytes
                    
            except Exception as e:
                logging.debug(f"Erro ao comprimir imagem {key}: {e}")
        
        with self.lock:
            # Limpar cache se necessário
            if len(self.cache) >= self.max_size:
                self._cleanup_low_priority()
            
            self.cache[key] = img_bytes
            self.timestamps[key] = time.time()
            self.priority_queue[key] = time.time()
            self.access_count[key] = 1
            
            try:
                file_path = os.path.join(self.cache_dir, f"{key}.png")
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
            except Exception as e:
                logging.warning(f"Erro ao salvar escudo em disco: {e}")
    
    def _cleanup_low_priority(self):
        """Limpa imagens pouco usadas quando o cache está cheio"""
        if len(self.cache) < self.max_size * 0.9:
            return
        
        items_to_clean = []
        for key in list(self.cache.keys()):
            last_access = self.priority_queue.get(key, 0)
            access_count = self.access_count.get(key, 0)
            age = time.time() - last_access
            
            priority_score = age / max(access_count, 1)
            items_to_clean.append((key, priority_score))
        
        items_to_clean.sort(key=lambda x: x[1], reverse=True)
        
        to_remove = max(10, int(len(items_to_clean) * 0.1))
        removed = 0
        
        for key, _ in items_to_clean[:to_remove]:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
                self.priority_queue.pop(key, None)
                self.access_count.pop(key, None)
                
                file_path = os.path.join(self.cache_dir, f"{key}.png")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
                
                removed += 1
        
        if removed > 0:
            logging.info(f"🧹 ImageCache: {removed} imagens de baixa prioridade removidas")
    
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
            self.priority_queue.clear()
            self.access_count.clear()
            
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
    
    def cleanup_low_priority(self):
        """Limpa imagens pouco usadas"""
        self._cleanup_low_priority()

# Instância global do cache de imagens aprimorado
escudos_cache = ImageCacheEnhanced()

# =============================
# Sistema de Pré-busca Inteligente (NOVO)
# =============================

class PrefetchSystem:
    """Sistema de pré-busca inteligente de dados"""
    
    def __init__(self):
        self.prefetch_queue = deque(maxlen=50)
        self.prefetch_thread = None
        self.running = False
        self.lock = threading.Lock()
        self.patterns = {
            "classificacao": r"/competitions/(.+)/standings",
            "jogos_dia": r"/competitions/(.+)/matches",
            "detalhes_partida": r"/matches/(.+)"
        }
        
    def schedule_prefetch(self, endpoint: str, priority: int = 5):
        """Agenda uma pré-busca"""
        with self.lock:
            self.prefetch_queue.append({
                "endpoint": endpoint,
                "priority": priority,
                "timestamp": time.time()
            })
    
    def extract_pattern(self, endpoint: str):
        """Extrai padrão do endpoint"""
        for pattern_name, pattern in self.patterns.items():
            match = re.match(pattern, endpoint)
            if match:
                return pattern_name, match.group(1)
        return None, None
    
    def intelligent_prefetch(self, current_endpoint: str):
        """Decide o que pré-buscar baseado no endpoint atual"""
        pattern, id_value = self.extract_pattern(current_endpoint)
        
        if pattern == "classificacao":
            liga_id = id_value
            hoje = datetime.now().strftime("%Y-%m-%d")
            jogos_endpoint = f"/competitions/{liga_id}/matches?dateFrom={hoje}&dateTo={hoje}"
            self.schedule_prefetch(jogos_endpoint, priority=7)
            
        elif pattern == "jogos_dia":
            liga_id = current_endpoint.split("/")[2]
            key = f"{liga_id}_{datetime.now().strftime('%Y-%m-%d')}"
            cached_jogos = jogos_cache.get(key)
            
            if cached_jogos:
                for match in cached_jogos[:5]:
                    match_id = match.get("id")
                    if match_id:
                        detalhes_endpoint = f"/matches/{match_id}"
                        self.schedule_prefetch(detalhes_endpoint, priority=3)
    
    def worker(self):
        """Thread worker para processar pré-busca"""
        while self.running:
            try:
                time.sleep(2)
                
                with self.lock:
                    if not self.prefetch_queue:
                        continue
                    
                    sorted_queue = sorted(self.prefetch_queue, 
                                        key=lambda x: x["priority"], 
                                        reverse=True)
                    
                    for item in sorted_queue[:3]:
                        endpoint = item["endpoint"]
                        
                        cache_key = endpoint.replace("/", "_").replace("?", "_")
                        cached = match_cache.get(cache_key)
                        
                        if not cached:
                            url = f"{BASE_URL_FD}{endpoint}"
                            try:
                                data = obter_dados_api(url)
                                if data:
                                    match_cache.set(cache_key, data)
                                    logging.debug(f"✅ Pré-busca concluída: {endpoint}")
                            except Exception as e:
                                logging.debug(f"❌ Pré-busca falhou: {endpoint} - {e}")
                        
                        if item in self.prefetch_queue:
                            self.prefetch_queue.remove(item)
                            
            except Exception as e:
                logging.error(f"Erro no worker de pré-busca: {e}")
    
    def start(self):
        """Inicia o sistema de pré-busca"""
        if not self.running:
            self.running = True
            self.prefetch_thread = threading.Thread(target=self.worker, daemon=True)
            self.prefetch_thread.start()
            logging.info("🚀 Sistema de pré-busca iniciado")
    
    def stop(self):
        """Para o sistema de pré-busca"""
        self.running = False
        if self.prefetch_thread:
            self.prefetch_thread.join(timeout=5)
        logging.info("🛑 Sistema de pré-busca parado")

# Instância global do sistema de pré-busca
prefetch_system = PrefetchSystem()

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
    """Carrega JSON"""
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            
            if not dados:
                return {}
                
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
                agora = datetime.now().timestamp()
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                        return {}
                else:
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

def carregar_alertas_top() -> dict:
    """Carrega os alertas TOP que foram gerados"""
    return carregar_json(ALERTAS_TOP_PATH)

def salvar_alertas_top(alertas_top: dict):
    """Salva os alertas TOP para conferência posterior"""
    salvar_json(ALERTAS_TOP_PATH, alertas_top)

def adicionar_alerta_top(jogo: dict, data_busca: str):
    """Adiciona um jogo aos alertas TOP salvos"""
    alertas_top = carregar_alertas_top()
    
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
    
    salvar_alertas_top(alertas_top)

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
# NOVA FUNÇÃO: Enviar alerta quando todos os Top N foram conferidos
# =============================
def enviar_alerta_top_conferidos():
    """Envia alerta quando todos os jogos do Top N foram conferidos"""
    alertas_top = carregar_alertas_top()
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
            )
            
            msg += "<b>🎯 DETALHES DOS JOGOS:</b>\n"
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
            
            if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2):
                for chave_alerta in list(alertas_top.keys()):
                    if alertas_top[chave_alerta].get("data_busca") == data_busca:
                        alertas_top[chave_alerta]["alerta_enviado"] = True
                
                salvar_alertas_top(alertas_top)
                alertas_enviados.append(data_busca)
                st.success(f"📤 Relatório de conferência enviado para {data_formatada}!")
    
    return len(alertas_enviados) > 0

# =============================
# NOVA FUNÇÃO: Conferir resultados dos alertas TOP
# =============================
def conferir_resultados_top():
    """Conferir resultados dos alertas TOP salvos"""
    alertas_top = carregar_alertas_top()
    if not alertas_top:
        st.info("ℹ️ Nenhum alerta TOP para conferir.")
        return
        
    resultados_conferidos = 0
    jogos_com_resultado = []
    
    for chave, alerta in list(alertas_top.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            fixture_id = alerta["id"]
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture_data = obter_dados_api(url)
            
            if not fixture_data:
                continue
                
            match = fixture_data.get('match', fixture_data)
            status = match.get("status", "")
            score = match.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
            if (status == "FINISHED" and 
                home_goals is not None and 
                away_goals is not None):
                
                total_gols = home_goals + away_goals
                previsao_correta = False
                
                if alerta["tendencia"] == "OVER 2.5" and total_gols > 2.5:
                    previsao_correta = True
                elif alerta["tendencia"] == "UNDER 2.5" and total_gols < 2.5:
                    previsao_correta = True
                elif alerta["tendencia"] == "OVER 1.5" and total_gols > 1.5:
                    previsao_correta = True
                elif alerta["tendencia"] == "UNDER 1.5" and total_gols < 1.5:
                    previsao_correta = True
                
                alerta["conferido"] = True
                alerta["resultado"] = "GREEN" if previsao_correta else "RED"
                alerta["placar"] = f"{home_goals}x{away_goals}"
                alerta["total_gols"] = total_gols
                alerta["data_conferencia"] = datetime.now().isoformat()
                
                resultados_conferidos += 1
                jogos_com_resultado.append(alerta)
                
        except Exception as e:
            logging.error(f"Erro ao conferir alerta TOP {chave}: {e}")
            st.error(f"Erro ao conferir alerta TOP {chave}: {e}")
    
    if resultados_conferidos > 0:
        salvar_alertas_top(alertas_top)
        st.success(f"✅ {resultados_conferidos} alertas TOP conferidos!")
        
        calcular_desempenho_alertas_top()
        
        if jogos_com_resultado:
            st.subheader("🎯 Jogos Conferidos Agora:")
            for jogo in jogos_com_resultado:
                resultado_emoji = "🟢" if jogo.get("resultado") == "GREEN" else "🔴"
                tipo_emoji = "📈" if jogo.get("tipo_aposta") == "over" else "📉"
                st.write(f"{resultado_emoji} {tipo_emoji} {jogo['home']} {jogo['placar']} {jogo['away']}")
    else:
        st.info("ℹ️ Nenhum novo resultado para conferir nos alertas TOP.")

# =============================
# NOVA FUNÇÃO: Calcular desempenho dos alertas TOP
# =============================
def calcular_desempenho_alertas_top():
    """Calcula o desempenho dos alertas TOP"""
    alertas_top = carregar_alertas_top()
    if not alertas_top:
        st.warning("⚠️ Nenhum alerta TOP encontrado.")
        return
        
    alertas_conferidos = [a for a in alertas_top.values() if a.get("conferido", False)]
    
    if not alertas_conferidos:
        st.info("ℹ️ Nenhum alerta TOP conferido ainda.")
        return
        
    total_alertas = len(alertas_conferidos)
    green_count = sum(1 for a in alertas_conferidos if a.get("resultado") == "GREEN")
    red_count = total_alertas - green_count
    taxa_acerto = (green_count / total_alertas * 100) if total_alertas > 0 else 0
    
    over_alertas = [a for a in alertas_conferidos if a.get("tipo_aposta") == "over"]
    under_alertas = [a for a in alertas_conferidos if a.get("tipo_aposta") == "under"]
    
    over_green = sum(1 for a in over_alertas if a.get("resultado") == "GREEN")
    under_green = sum(1 for a in under_alertas if a.get("resultado") == "GREEN")
    
    st.success(f"📊 Desempenho dos Alertas TOP:")
    st.write(f"**Total de Alertas Conferidos:** {total_alertas}")
    st.write(f"**🟢 GREEN:** {green_count} ({taxa_acerto:.1f}%)")
    st.write(f"**🔴 RED:** {red_count} ({100 - taxa_acerto:.1f}%)")
    
    if over_alertas:
        taxa_over = (over_green / len(over_alertas) * 100) if len(over_alertas) > 0 else 0
        st.write(f"**📈 OVER:** {over_green}/{len(over_alertas)} ({taxa_over:.1f}%)")
    
    if under_alertas:
        taxa_under = (under_green / len(under_alertas) * 100) if len(under_alertas) > 0 else 0
        st.write(f"**📉 UNDER:** {under_green}/{len(under_alertas)} ({taxa_under:.1f}%)")

# =============================
# NOVA FUNÇÃO: Verificar se há conjuntos completos para reportar
# =============================
def verificar_conjuntos_completos():
    """Verifica se há conjuntos de Top N completos para reportar"""
    alertas_top = carregar_alertas_top()
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
# Utilitários de Data e Formatação
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    """Formata data ISO"""
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

def formatar_data_iso_para_datetime(data_iso: str) -> datetime:
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
        logging.error(f"Erro ao convertir data {data_iso}: {e}")
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
    """Envia uma foto para o Telegram"""
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

@measure_performance("obter_dados_api_com_retry")
def obter_dados_api_com_retry(url: str, timeout: int = 15, max_retries: int = 3) -> dict | None:
    """Obtém dados da API com rate limiting e retry automático"""
    for attempt in range(max_retries):
        try:
            rate_limiter.wait_if_needed()
            
            logging.info(f"🔗 Request {attempt+1}/{max_retries}: {url}")
            
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            
            if response.status_code == 429:
                api_monitor.log_request(False, True)
                retry_after = int(response.headers.get('Retry-After', 60))
                logging.warning(f"⏳ Rate limit da API. Esperando {retry_after} segundos...")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            
            api_monitor.log_request(True)
            
            remaining = response.headers.get('X-Requests-Remaining', 'unknown')
            reset_time = response.headers.get('X-RequestCounter-Reset', 'unknown')
            logging.info(f"✅ Request OK. Restantes: {remaining}, Reset: {reset_time}s")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logging.error(f"⌛ Timeout na tentativa {attempt+1} para {url}")
            api_monitor.log_request(False)
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logging.info(f"⏳ Esperando {wait_time}s antes de retry...")
                time.sleep(wait_time)
                
        except requests.RequestException as e:
            logging.error(f"❌ Erro na tentativa {attempt+1} para {url}: {e}")
            api_monitor.log_request(False)
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
            else:
                st.error(f"❌ Falha após {max_retries} tentativas: {e}")
                return None
                
    return None

def obter_dados_api(url: str, timeout: int = 15) -> dict | None:
    return obter_dados_api_com_retry(url, timeout, max_retries=3)

@measure_performance("obter_classificacao")
def obter_classificacao(liga_id: str) -> dict:
    """Obtém classificação com cache inteligente"""
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

@measure_performance("obter_jogos")
def obter_jogos(liga_id: str, data: str) -> list:
    """Obtém jogos com cache inteligente"""
    key = f"{liga_id}_{data}"
    
    cached = jogos_cache.get(key)
    if cached:
        logging.info(f"⚽ Jogos {key} obtidos do cache")
        return cached
    
    url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
    data_api = obter_dados_api(url)
    jogos = data_api.get("matches", []) if data_api else []
    jogos_cache.set(key, jogos)
    return jogos

@measure_performance("obter_detalhes_partida")
def obter_detalhes_partida(fixture_id: str) -> dict | None:
    """Obtém detalhes de uma partida específica com cache"""
    cached = match_cache.get(fixture_id)
    if cached:
        return cached
    
    url = f"{BASE_URL_FD}/matches/{fixture_id}"
    data = obter_dados_api(url)
    
    if data:
        match_cache.set(fixture_id, data)
    
    return data

@measure_performance("obter_jogos_brasileirao")
def obter_jogos_brasileirao(liga_id: str, data_hoje: str) -> list:
    """Busca jogos do Brasileirão considerando o fuso horário"""
    data_amanha = (datetime.strptime(data_hoje, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    
    jogos_hoje = obter_jogos(liga_id, data_hoje)
    jogos_amanha = obter_jogos(liga_id, data_amanha)
    
    todos_jogos = jogos_hoje + jogos_amanha
    
    jogos_filtrados = []
    for match in todos_jogos:
        if not validar_dados_jogo(match):
            continue
            
        data_utc = match["utcDate"]
        hora_brasilia = formatar_data_iso_para_datetime(data_utc)
        data_brasilia = hora_brasilia.strftime("%Y-%m-%d")
        
        if data_brasilia == data_hoje:
            jogos_filtrados.append(match)
    
    return jogos_filtrados

# =============================
# Funções de Download com Cache
# =============================
@measure_performance("baixar_escudo_com_cache")
def baixar_escudo_com_cache(team_name: str, crest_url: str) -> Image.Image | None:
    """Baixa escudo com cache robusto"""
    if not crest_url or crest_url == "":
        logging.warning(f"URL vazia para {team_name}")
        return None
    
    try:
        cached_img = escudos_cache.get(team_name, crest_url)
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
        
        escudos_cache.set(team_name, crest_url, img_bytes)
        
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

def baixar_imagem_url(url: str, timeout: int = 8) -> Image.Image | None:
    """Tenta baixar uma imagem"""
    if not url or url == "":
        return None
    
    team_name = url.split('/')[-1].replace('.png', '').replace('.svg', '')
    
    cached_img = escudos_cache.get(team_name, url)
    if cached_img:
        return Image.open(io.BytesIO(cached_img)).convert("RGBA")
        
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        
        content_type = resp.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logging.warning(f"URL não é uma imagem: {content_type}")
            return None
            
        img_bytes = resp.content
        
        escudos_cache.set(team_name, url, img_bytes)
        
        img = Image.open(io.BytesIO(img_bytes))
        return img.convert("RGBA")
        
    except Exception as e:
        logging.error(f"Erro ao baixar imagem {url}: {e}")
        return None

# =============================
# Lógica de Análise e Alertas (OTIMIZADA)
# =============================
@measure_performance("calcular_tendencia_otimizada")
def calcular_tendencia_otimizada(home: str, away: str, classificacao: dict) -> dict:
    """
    Versão OTIMIZADA do cálculo de tendência
    """
    
    # 1. CARREGAMENTO DE DADOS
    dados_home = classificacao.get(home, {
        "scored": 0, "against": 0, "played": 1, 
        "wins": 0, "draws": 0, "losses": 0,
        "over_25_rate": 0.5, "under_25_rate": 0.5,
        "over_15_rate": 0.7, "under_15_rate": 0.3
    })
    
    dados_away = classificacao.get(away, {
        "scored": 0, "against": 0, "played": 1,
        "wins": 0, "draws": 0, "losses": 0,
        "over_25_rate": 0.5, "under_25_rate": 0.5,
        "over_15_rate": 0.7, "under_15_rate": 0.3
    })
    
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)
    
    # 2. CÁLCULOS BÁSICOS OTIMIZADOS
    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away
    
    estimativa_home = (media_home_feitos * 0.6) + (media_away_sofridos * 0.4)
    estimativa_away = (media_away_feitos * 0.4) + (media_home_sofridos * 0.6)
    estimativa_total = estimativa_home + estimativa_away
    
    # Ajustes de casa/fora
    fator_casa = 1.15
    fator_fora = 0.85
    
    estimativa_ajustada_home = estimativa_home * fator_casa
    estimativa_ajustada_away = estimativa_away * fator_fora
    estimativa_total_ajustada = estimativa_ajustada_home + estimativa_ajustada_away
    
    # 3. ANÁLISE MULTIVARIADA OTIMIZADA
    home_balance = media_home_feitos - media_home_sofridos
    away_balance = media_away_feitos - media_away_sofridos
    
    home_ofensividade = min(1.0, max(-1.0, home_balance / 2.0))
    away_ofensividade = min(1.0, max(-1.0, away_balance / 2.0))
    
    score_confronto = (home_ofensividade + away_ofensividade) / 2
    
    # 4. PROBABILIDADES BAYESIANAS MELHORADAS
    home_over_25_rate = (dados_home.get("over_25_rate", 0.5) * played_home + 1) / (played_home + 2)
    home_under_25_rate = (dados_home.get("under_25_rate", 0.5) * played_home + 1) / (played_home + 2)
    away_over_25_rate = (dados_away.get("over_25_rate", 0.5) * played_away + 1) / (played_away + 2)
    away_under_25_rate = (dados_away.get("under_25_rate", 0.5) * played_away + 1) / (played_away + 2)
    
    total_played = played_home + played_away
    over_25_prob = ((home_over_25_rate * played_home) + (away_over_25_rate * played_away)) / total_played
    under_25_prob = ((home_under_25_rate * played_home) + (away_under_25_rate * played_away)) / total_played
    
    # 5. MODELO PREDITIVO MULTIVARIADO
    fatores = {
        'estimativa_normalizada': min(1.0, estimativa_total_ajustada / 5.0),
        'score_confronto_normalizado': (score_confronto + 1) / 2,
        'historico_over': over_25_prob,
        'historico_under': under_25_prob,
        'home_attack_strength': min(1.0, media_home_feitos / 3.0),
        'away_defense_weakness': min(1.0, media_away_sofridos / 2.0)
    }
    
    pesos = {
        'over_25': {
            'estimativa': 0.35,
            'confronto': 0.25,
            'historico': 0.30,
            'attack_defense': 0.10
        },
        'under_25': {
            'estimativa': 0.30,
            'confronto': 0.20,
            'historico': 0.40,
            'attack_defense': 0.10
        }
    }
    
    score_over_25 = (
        fatores['estimativa_normalizada'] * pesos['over_25']['estimativa'] +
        fatores['score_confronto_normalizado'] * pesos['over_25']['confronto'] +
        fatores['historico_over'] * pesos['over_25']['historico'] +
        (fatores['home_attack_strength'] * fatores['away_defense_weakness']) * pesos['over_25']['attack_defense']
    )
    
    score_under_25 = (
        (1 - fatores['estimativa_normalizada']) * pesos['under_25']['estimativa'] +
        (1 - fatores['score_confronto_normalizado']) * pesos['under_25']['confronto'] +
        fatores['historico_under'] * pesos['under_25']['historico'] +
        ((1 - fatores['home_attack_strength']) * (1 - fatores['away_defense_weakness'])) * pesos['under_25']['attack_defense']
    )
    
    # Normalizar scores
    total_score = score_over_25 + score_under_25
    if total_score > 0:
        score_over_25 /= total_score
        score_under_25 /= total_score
    
    # 6. DECISÃO INTELIGENTE
    qualidade_dados = min(1.0, (played_home + played_away) / 20)
    limiar_over = 0.55 + (0.10 * qualidade_dados)
    limiar_under = 0.55 + (0.10 * qualidade_dados)
    
    # Decisão principal
    if score_over_25 > limiar_over and estimativa_total_ajustada > 2.5:
        tendencia_principal = "OVER 2.5"
        tipo_aposta = "over"
        probabilidade_base = score_over_25 * 100
        decisao = "OVER_FORTE"
    elif score_under_25 > limiar_under and estimativa_total_ajustada < 2.5:
        tendencia_principal = "UNDER 2.5"
        tipo_aposta = "under"
        probabilidade_base = score_under_25 * 100
        decisao = "UNDER_FORTE"
    elif score_over_25 > 0.50 and estimativa_total_ajustada > 2.0:
        tendencia_principal = "OVER 2.5"
        tipo_aposta = "over"
        probabilidade_base = score_over_25 * 100
        decisao = "OVER_MODERADO"
    elif score_under_25 > 0.50 and estimativa_total_ajustada < 2.0:
        tendencia_principal = "UNDER 2.5"
        tipo_aposta = "under"
        probabilidade_base = score_under_25 * 100
        decisao = "UNDER_MODERADO"
    else:
        if estimativa_total_ajustada > 2.75:
            tendencia_principal = "OVER 2.5"
            tipo_aposta = "over"
            probabilidade_base = 55.0
            decisao = "FALLBACK_ESTIMATIVA_ALTA"
        elif estimativa_total_ajustada < 2.25:
            tendencia_principal = "UNDER 2.5"
            tipo_aposta = "under"
            probabilidade_base = 55.0
            decisao = "FALLBACK_ESTIMATIVA_BAIXA"
        else:
            if score_over_25 >= score_under_25:
                tendencia_principal = "OVER 2.5"
                tipo_aposta = "over"
                probabilidade_base = score_over_25 * 100
                decisao = "EMPATE_OVER"
            else:
                tendencia_principal = "UNDER 2.5"
                tipo_aposta = "under"
                probabilidade_base = score_under_25 * 100
                decisao = "EMPATE_UNDER"
    
    # 7. CÁLCULO DE CONFIANÇA MELHORADO
    sinais_concordantes = 0
    total_sinais = 4
    
    if (tipo_aposta == "over" and estimativa_total_ajustada > 2.5) or \
       (tipo_aposta == "under" and estimativa_total_ajustada < 2.5):
        sinais_concordantes += 1
    
    if ((tipo_aposta == "over" and score_over_25 > 0.55) or \
        (tipo_aposta == "under" and score_under_25 > 0.55)):
        sinais_concordantes += 1
    
    hist_relevante = over_25_prob if tipo_aposta == "over" else under_25_prob
    if hist_relevante > 0.55:
        sinais_concordantes += 1
    
    if (tipo_aposta == "over" and score_confronto > 0.1) or \
       (tipo_aposta == "under" and score_confronto < -0.1):
        sinais_concordantes += 1
    
    concordancia = sinais_concordantes / total_sinais
    score_relevante = score_over_25 if tipo_aposta == "over" else score_under_25
    forca_sinais = min(1.0, abs(score_relevante - 0.5) * 2)
    
    if tipo_aposta == "over":
        distancia = (score_over_25 - 0.5) * 2
    else:
        distancia = (score_under_25 - 0.5) * 2
    distancia_limiar = max(0, min(1.0, distancia))
    
    # Cálculo final da confiança
    confianca_base = 50.0
    confianca_base += concordancia * 20.0
    confianca_base += forca_sinais * 15.0
    confianca_base += qualidade_dados * 10.0
    confianca_base += distancia_limiar * 15.0
    
    if "FALLBACK" in decisao:
        confianca_base *= 0.85
    elif "MODERADO" in decisao:
        confianca_base *= 0.90
    
    probabilidade_final = max(1.0, min(99.0, round(probabilidade_base, 1)))
    confianca_final = max(20.0, min(95.0, round(confianca_base, 1)))
    
    # 8. DETALHES PARA TRANSPARÊNCIA
    detalhes = {
        "over_25_prob": round(score_over_25 * 100, 1),
        "under_25_prob": round(score_under_25 * 100, 1),
        "estimativa_ajustada": round(estimativa_total_ajustada, 2),
        "score_confronto": round(score_confronto, 3),
        "qualidade_dados": round(qualidade_dados * 100, 1),
        "over_25_historico": round(over_25_prob * 100, 1),
        "under_25_historico": round(under_25_prob * 100, 1),
        "analise_detalhada": {
            "home_ofensividade": round(home_ofensividade, 3),
            "away_ofensividade": round(away_ofensividade, 3),
            "sinais_concordantes": sinais_concordantes,
            "decisao": decisao,
            "score_over_raw": round(score_over_25, 3),
            "score_under_raw": round(score_under_25, 3),
            "limiar_over": round(limiar_over, 3),
            "limiar_under": round(limiar_under, 3)
        }
    }
    
    logging.info(
        f"ANÁLISE OTIMIZADA: {home} vs {away} | "
        f"Est: {estimativa_total_ajustada:.2f} | "
        f"Tend: {tendencia_principal} | "
        f"Prob: {probabilidade_final:.1f}% | "
        f"Conf: {confianca_final:.1f}% | "
        f"Sinais: {sinais_concordantes}/{total_sinais} | "
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

@measure_performance("calcular_tendencia_15_otimizada")
def calcular_tendencia_15_otimizada(home: str, away: str, classificacao: dict) -> dict:
    """
    Versão otimizada para Over/Under 1.5
    """
    analise_base = calcular_tendencia_otimizada(home, away, classificacao)
    
    estimativa = analise_base["estimativa"]
    
    if estimativa > 2.5:
        prob_over_15 = min(95.0, 60.0 + (estimativa - 2.5) * 15.0)
        prob_under_15 = 100.0 - prob_over_15
        tendencia = "OVER 1.5"
        tipo_aposta = "over"
    elif estimativa < 1.5:
        prob_under_15 = min(95.0, 60.0 + (1.5 - estimativa) * 15.0)
        prob_over_15 = 100.0 - prob_under_15
        tendencia = "UNDER 1.5"
        tipo_aposta = "under"
    else:
        if estimativa > 2.0:
            prob_over_15 = 65.0
            prob_under_15 = 35.0
            tendencia = "OVER 1.5"
            tipo_aposta = "over"
        else:
            prob_over_15 = 45.0
            prob_under_15 = 55.0
            tendencia = "UNDER 1.5"
            tipo_aposta = "under"
    
    distancia_15 = abs(estimativa - 1.5)
    confianca_ajustada = min(90.0, 50.0 + (distancia_15 * 20.0))
    confianca_final = min(95.0, analise_base["confianca"] * 0.85)
    
    return {
        "tendencia": tendencia,
        "estimativa": estimativa,
        "probabilidade": prob_over_15 if tendencia == "OVER 1.5" else prob_under_15,
        "confianca": confianca_final,
        "tipo_aposta": tipo_aposta,
        "detalhes": {
            "over_15_prob": round(prob_over_15, 1),
            "under_15_prob": round(prob_under_15, 1),
            "distancia_1.5": round(distancia_15, 2),
            "estimativa_base": estimativa
        }
    }

@measure_performance("calcular_tendencia_completa_melhorada")
def calcular_tendencia_completa_melhorada(home: str, away: str, classificacao: dict) -> dict:
    """
    Função unificada que escolhe automaticamente a melhor análise
    """
    analise_base = calcular_tendencia_otimizada(home, away, classificacao)
    
    if analise_base["confianca"] > 80 or analise_base["confianca"] < 40:
        return analise_base
    
    analise_15 = calcular_tendencia_15_otimizada(home, away, classificacao)
    
    estimativa = analise_base["estimativa"]
    
    if estimativa > 3.0:
        if analise_base["confianca"] > 65:
            return analise_base
        else:
            return analise_15
            
    elif estimativa < 1.8:
        if analise_15["confianca"] > analise_base["confianca"]:
            return analise_15
        else:
            return analise_base
            
    elif 2.2 <= estimativa <= 2.8:
        return analise_base
        
    else:
        if analise_15["confianca"] > analise_base["confianca"] + 10:
            return analise_15
        else:
            return analise_base

# =============================
# Funções de Geração de Posters
# =============================
def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
    """Cria fonte com fallback robusto"""
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

def gerar_poster_individual_westham(fixture: dict, analise: dict) -> io.BytesIO:
    """Gera poster individual no estilo West Ham"""
    LARGURA = 1800
    ALTURA = 1200
    PADDING = 80

    img = Image.new("RGB", (LARGURA, ALTURA), color=(10, 20, 30))
    draw = ImageDraw.Draw(img)

    FONTE_TITULO = criar_fonte(80)
    FONTE_SUBTITULO = criar_fonte(60)
    FONTE_TIMES = criar_fonte(55)
    FONTE_VS = criar_fonte(45)
    FONTE_INFO = criar_fonte(40)
    FONTE_DETALHES = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(50)
    FONTE_ALERTA = criar_fonte(70)
    FONTE_ESTATISTICAS = criar_fonte(35)

    tipo_alerta = "🎯 ALERTA " if analise["tipo_aposta"] == "over" else "🛡️ ALERTA UNDER"
    titulo_text = f"{tipo_alerta} DE GOLS"
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_ALERTA)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        cor_titulo = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
        draw.text(((LARGURA - titulo_w) // 2, 60), titulo_text, font=FONTE_ALERTA, fill=cor_titulo)
    except:
        draw.text((LARGURA//2 - 200, 60), titulo_text, font=FONTE_ALERTA, fill=(255, 215, 0))

    cor_linha = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
    draw.line([(LARGURA//4, 150), (3*LARGURA//4, 150)], fill=cor_linha, width=4)

    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    status = fixture.get("status", "DESCONHECIDO")

    try:
        liga_bbox = draw.textbbox((0, 0), competicao.upper(), font=FONTE_SUBTITULO)
        liga_w = liga_bbox[2] - liga_bbox[0]
        draw.text(((LARGURA - liga_w) // 2, 180), competicao.upper(), font=FONTE_SUBTITULO, fill=(200, 200, 200))
    except:
        draw.text((LARGURA//2 - 150, 180), competicao.upper(), font=FONTE_SUBTITULO, fill=(200, 200, 200))

    data_hora_text = f"{data_formatada} • {hora_formatada} BRT • {status}"
    try:
        data_bbox = draw.textbbox((0, 0), data_hora_text, font=FONTE_INFO)
        data_w = data_bbox[2] - data_bbox[0]
        draw.text(((LARGURA - data_w) // 2, 260), data_hora_text, font=FONTE_INFO, fill=(150, 200, 255))
    except:
        draw.text((LARGURA//2 - 150, 260), data_hora_text, font=FONTE_INFO, fill=(150, 200, 255))

    TAMANHO_ESCUDO = 180
    TAMANHO_QUADRADO = 220
    ESPACO_ENTRE_ESCUDOS = 600

    largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    x_inicio = (LARGURA - largura_total) // 2

    x_home = x_inicio
    x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    y_escudos = 350

    escudo_home_url = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
    escudo_away_url = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
    
    escudo_home = baixar_escudo_com_cache(home, escudo_home_url)
    escudo_away = baixar_escudo_com_cache(away, escudo_away_url)

    def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
        draw.rectangle(
            [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
            fill=(255, 255, 255),
            outline=(255, 255, 255)
        )

        if logo_img is None:
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
            draw.text((x + 60, y + 80), "SEM", font=FONTE_INFO, fill=(255, 255, 255))
            return

        try:
            logo_img = logo_img.convert("RGBA")
            largura, altura = logo_img.size
            proporcao = largura / altura

            if proporcao > 1:
                nova_altura = altura
                nova_largura = int(altura)
                offset_x = (largura - nova_largura) // 2
                offset_y = 0
            else:
                nova_largura = largura
                nova_altura = int(largura)
                offset_x = 0
                offset_y = (altura - nova_altura) // 2

            imagem_cortada = logo_img.crop((offset_x, offset_y, offset_x + nova_largura, offset_y + nova_altura))

            imagem_final = imagem_cortada.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)

            pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
            pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2

            img.paste(imagem_final, (pos_x, pos_y), imagem_final)

        except Exception as e:
            logging.error(f"Erro ao processar escudo: {e}")
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
            draw.text((x + 60, y + 80), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

    desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
    desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

    home_text = home[:20]
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

    try:
        vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
        vs_w = vs_bbox[2] - vs_bbox[0]
        vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
        draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 25), 
                 "VS", font=FONTE_VS, fill=(255, 215, 0))
    except:
        vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 25
        draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 25), "VS", font=FONTE_VS, fill=(255, 215, 0))

    y_analysis = y_escudos + TAMANHO_QUADRADO + 120
    
    draw.line([(PADDING + 50, y_analysis - 20), (LARGURA - PADDING - 50, y_analysis - 20)], 
             fill=(100, 130, 160), width=3)

    tendencia_emoji = "" if analise["tipo_aposta"] == "over" else "📉"
    cor_tendencia = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
    
    textos_analise = [
        f"{tendencia_emoji} TENDÊNCIA: {analise['tendencia']}",
        f" ESTIMATIVA: {analise['estimativa']:.2f} GOLS",
        f" PROBABILIDADE: {analise['probabilidade']:.0f}%",
        f" CONFIANÇA: {analise['confianca']:.0f}%"
    ]
    
    cores = [cor_tendencia, (100, 200, 255), (100, 255, 100), (255, 193, 7)]
    
    for i, (text, cor) in enumerate(zip(textos_analise, cores)):
        try:
            bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
            w = bbox[2] - bbox[0]
            draw.text(((LARGURA - w) // 2, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)
        except:
            draw.text((PADDING + 100, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)

    y_estatisticas = y_analysis + 280
    
    stats_title = "📊 ESTATÍSTICAS DETALHADAS"
    try:
        title_bbox = draw.textbbox((0, 0), stats_title, font=FONTE_DETALHES)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((LARGURA - title_w) // 2, y_estatisticas), stats_title, font=FONTE_DETALHES, fill=(200, 200, 200))
    except:
        draw.text((LARGURA//2 - 150, y_estatisticas), stats_title, font=FONTE_DETALHES, fill=(200, 200, 200))

    y_stats = y_estatisticas + 60
    
    col1_stats = [
        f"Over 2.5: {analise['detalhes']['over_25_prob']}% (Conf: {analise['detalhes']['over_25_conf']}%)",
        f"Under 2.5: {analise['detalhes']['under_25_prob']}% (Conf: {analise['detalhes']['under_25_conf']}%)"
    ]
    
    col2_stats = [
        f"Over 1.5: {analise['detalhes']['over_15_prob']}% (Conf: {analise['detalhes']['over_15_conf']}%)",
        f"Under 1.5: {analise['detalhes']['under_15_prob']}% (Conf: {analise['detalhes']['under_15_conf']}%)"
    ]
    
    for i, stat in enumerate(col1_stats):
        draw.text((PADDING + 100, y_stats + i * 45), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
    
    for i, stat in enumerate(col2_stats):
        try:
            bbox = draw.textbbox((0, 0), stat, font=FONTE_ESTATISTICAS)
            w = bbox[2] - bbox[0]
            draw.text((LARGURA - PADDING - 100 - w, y_stats + i * 45), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
        except:
            draw.text((LARGURA - PADDING - 300, y_stats + i * 45), stat, font=FONTE_ESTATISTICas, fill=(180, 220, 255))

    y_indicator = y_estatisticas + 160
    if analise["confianca"] >= 80:
        indicador_text = "🔥🔥 ALTA CONFIABILIDADE 🔥🔥"
        cor_indicador = (76, 175, 80)
    elif analise["confianca"] >= 60:
        indicador_text = "⚡⚡ MÉDIA CONFIABILIDADE ⚡⚡"
        cor_indicador = (255, 193, 7)
    else:
        indicador_text = "⚠️⚠️ CONFIABILIDADE MODERADA ⚠️⚠️"
        cor_indicador = (255, 152, 0)

    try:
        ind_bbox = draw.textbbox((0, 0), indicador_text, font=FONTE_DETALHES)
        ind_w = ind_bbox[2] - ind_bbox[0]
        draw.text(((LARGURA - ind_w) // 2, y_indicator), indicador_text, font=FONTE_DETALHES, fill=cor_indicador)
    except:
        draw.text((LARGURA//2 - 200, y_indicator), indicador_text, font=FONTE_DETALHES, fill=cor_indicador)

    rodape_text = f"ELITE MASTER SYSTEM • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, ALTURA - 60), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 150, ALTURA - 60), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    return buffer

def gerar_poster_top_jogos(top_jogos: list, min_conf: int, max_conf: int, titulo: str = "** TOP JOGOS DO DIA **") -> io.BytesIO:
    """Gera poster profissional para os Top Jogos"""
    LARGURA = 2200
    ALTURA_TOPO = 300
    ALTURA_POR_JOGO = 910
    PADDING = 80
    
    jogos_count = len(top_jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    img = Image.new("RGB", (LARGURA, altura_total), color=(15, 25, 40))
    draw = ImageDraw.Draw(img)

    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(55)
    FONTE_VS = criar_fonte(45)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(55)
    FONTE_RANKING = criar_fonte(70)
    FONTE_ESTATISTICAS = criar_fonte(35)

    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 350, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    subtitulo = f"🎯 Intervalo de Confiança: {min_conf}% - {max_conf}% | 🔥 {len(top_jogos)} Jogos Selecionados"
    try:
        sub_bbox = draw.textbbox((0, 0), subtitulo, font=FONTE_SUBTITULO)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((LARGURA - sub_w) // 2, 180), subtitulo, font=FONTE_SUBTITULO, fill=(150, 200, 255))
    except:
        draw.text((LARGURA//2 - 300, 180), subtitulo, font=FONTE_SUBTITULO, fill=(150, 200, 255))

    draw.line([(LARGURA//4, 250), (3*LARGURA//4, 250)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(top_jogos):
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        cor_borda = (76, 175, 80) if jogo.get('tipo_aposta') == "over" else (255, 87, 34)
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 50), outline=cor_borda, width=3)
        
        rank_text = f"TOP {idx + 1}"
        try:
            rank_bbox = draw.textbbox((0, 0), rank_text, font=FONTE_RANKING)
            rank_w = rank_bbox[2] - rank_bbox[0]
            rank_x = x0 + 30
            rank_y = y0 + 30
            draw.rectangle([rank_x - 20, rank_y, rank_x + rank_w + 20, rank_y + 80], 
                         fill=cor_borda, outline=cor_borda)
            draw.text((rank_x, rank_y), rank_text, font=FONTE_RANKING, fill=(255, 255, 255))
        except:
            pass

        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 50), liga_text, font=FONTE_SUBTITULO, fill=(180, 200, 220))
        except:
            draw.text((LARGURA//2 - 150, y0 + 50), liga_text, font=FONTE_SUBTITULO, fill=(180, 200, 220))

        if isinstance(jogo["hora"], datetime):
            data_text = jogo["hora"].strftime("%d/%m/%Y")
            hora_text = jogo["hora"].strftime("%H:%M") + " BRT"
        else:
            data_text = str(jogo["hora"])
            hora_text = ""
        
        data_hora_text = f"{data_text} • {hora_text}"
        try:
            dh_bbox = draw.textbbox((0, 0), data_hora_text, font=FONTE_INFO)
            dh_w = dh_bbox[2] - dh_bbox[0]
            draw.text(((LARGURA - dh_w) // 2, y0 + 120), data_hora_text, font=FONTE_INFO, fill=(100, 180, 255))
        except:
            draw.text((LARGURA//2 - 150, y0 + 120), data_hora_text, font=FONTE_INFO, fill=(100, 180, 255))

        TAMANHO_ESCUDO = 180
        TAMANHO_QUADRADO = 220
        ESPACO_ENTRE_ESCUDOS = 700

        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        y_escudos = y0 + 180

        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get('escudo_home', ''))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get('escudo_away', ''))

        def desenhar_escudo_quadrado_top(logo_img, x, y, tamanho_quadrado, tamanho_escudo, team_name):
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], 
                         fill=(255, 255, 255), outline=(200, 200, 200), width=2)

            if logo_img is None:
                inicial = team_name[:1].upper()
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 70, 90))
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
                logging.error(f"Erro ao desenhar escudo top: {e}")

        desenhar_escudo_quadrado_top(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
        desenhar_escudo_quadrado_top(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

        home_text = jogo['home'][:15]
        away_text = jogo['away'][:15]

        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 30),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 30),
                     home_text, font=FONTE_TIMes, fill=(255, 255, 255))

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 30),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 30),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))

        try:
            vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
            vs_w = vs_bbox[2] - vs_bbox[0]
            vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 25), 
                     "VS", font=FONTE_VS, fill=(255, 215, 0))
        except:
            vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 25
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 25), "VS", font=FONTE_VS, fill=(255, 215, 0))

        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

        tipo_emoji = "+" if jogo.get('tipo_aposta') == "over" else "-"
        cor_tipo = (76, 175, 80) if jogo.get('tipo_aposta') == "over" else (255, 87, 34)
        
        textos_analise = [
            f"{tipo_emoji} {jogo['tendencia']}",
            f" Estimativa: {jogo['estimativa']:.2f} gols",
            f" Probabilidade: {jogo['probabilidade']:.0f}%",
            f" Confiança: {jogo['confianca']:.0f}%"
        ]
        
        for i, text in enumerate(textos_analise):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                cor = cor_tipo if i == 0 else (200, 220, 255)
                draw.text(((LARGURA - w) // 2, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)
            except:
                draw.text((PADDING + 100, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor_tipo)

        if 'detalhes' in jogo:
            y_stats = y_analysis + 280
            detalhes = jogo['detalhes']
            
            stats_text = [
                f"Over 2.5: {detalhes.get('over_25_prob', 0):.0f}%",
                f"Under 2.5: {detalhes.get('under_25_prob', 0):.0f}%",
                f"Over 1.5: {detalhes.get('over_15_prob', 0):.0f}%",
                f"Under 1.5: {detalhes.get('under_15_prob', 0):.0f}%"
            ]
            
            for i, stat in enumerate(stats_text):
                col = i % 2
                row = i // 2
                x_pos = PADDING + 100 + (col * 300)
                draw.text((x_pos, y_stats + row * 40), stat, font=FONTE_ESTATISTICAS, fill=(180, 200, 220))

        y_pos += ALTURA_POR_JOGO

    rodape_text = f" ELITE MASTER SYSTEM - Análise Preditiva | {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        draw.text((LARGURA//2 - 300, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster TOP {len(top_jogos)} Jogos gerado com sucesso!")
    return buffer

def gerar_poster_westham_style(jogos: list, titulo: str = " ALERTA DE GOLS") -> io.BytesIO:
    """Gera poster no estilo West Ham vs Burnley"""
    LARGURA = 2000
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 1050
    PADDING = 120
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
    draw = ImageDraw.Draw(img)

    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(70)
    FONTE_TIMES = criar_fonte(65)
    FONTE_VS = criar_fonte(55)
    FONTE_INFO = criar_fonte(50)
    FONTE_DETALHES = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(65)
    FONTE_ESTATISTICAS = criar_fonte(40)

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
        
        cor_borda = (255, 215, 0) if jogo.get('tipo_aposta') == "over" else (100, 200, 255)
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

        TAMANHO_ESCUDO = 200
        TAMANHO_QUADRADO = 240
        ESPACO_ENTRE_ESCUDOS = 700

        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        y_escudos = y0 + 250

        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get('escudo_home', ''))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get('escudo_away', ''))

        def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            draw.rectangle(
                [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                fill=(255, 255, 255),
                outline=(255, 255, 255)
            )

            if logo_img is None:
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
                draw.text((x + 70, y + 90), "SEM", font=FONTE_INFO, fill=(255, 255, 255))
                return

            try:
                logo_img = logo_img.convert("RGBA")
                largura, altura = logo_img.size
                proporcao = largura / altura

                if proporcao > 1:
                    nova_altura = altura
                    nova_largura = int(altura)
                    offset_x = (largura - nova_largura) // 2
                    offset_y = 0
                else:
                    nova_largura = largura
                    nova_altura = int(largura)
                    offset_x = 0
                    offset_y = (altura - nova_altura) // 2

                imagem_cortada = logo_img.crop((offset_x, offset_y, offset_x + nova_largura, offset_y + nova_altura))

                imagem_final = imagem_cortada.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)

                pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
                pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2

                img.paste(imagem_final, (pos_x, pos_y), imagem_final)

            except Exception as e:
                logging.error(f"Erro ao processar escudo West Ham: {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 70, y + 90), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

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

        try:
            vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
            vs_w = vs_bbox[2] - vs_bbox[0]
            vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), 
                     "VS", font=FONTE_VS, fill=(255, 215, 0))
        except:
            vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 30
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), "VS", font=FONTE_VS, fill=(255, 215, 0))

        y_analysis = y_escudos + TAMANHO_QUADRADO + 150
        
        draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)

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

        y_stats = y_analysis + 360
        
        stats_title = "📊 Estatísticas Detalhadas:"
        draw.text((x0 + 100, y_stats), stats_title, font=FONTE_DETALHES, fill=(200, 200, 200))
        
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
            
            for i, stat in enumerate(col1_stats):
                draw.text((x0 + 120, y_stats_content + i * 50), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
            
            for i, stat in enumerate(col2_stats):
                draw.text((x0 + 500, y_stats_content + i * 50), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

        y_pos += ALTURA_POR_JOGO

    rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_DETALHES)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 250, altura_total - 70), rodape_text, font=FONTE_DETALHes, fill=(100, 130, 160))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster estilo West Ham GERADO com {len(jogos)} jogos")
    return buffer

def gerar_poster_resultados(jogos: list, titulo: str = " ** RESULTADOS OFICIAIS ** ") -> io.BytesIO:
    """Gera poster profissional com resultados finais"""
    LARGURA = 2200
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 900
    PADDING = 80
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(70)
    FONTE_PLACAR = criar_fonte(100)
    FONTE_VS = criar_fonte(70)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_RESULTADO = criar_fonte(70)

    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    draw.line([(LARGURA//4, 180), (3*LARGURA//4, 180)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        total_gols = jogo['home_goals'] + jogo['away_goals']
        previsao_correta = False
        
        if jogo['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5:
            previsao_correta = True
        
        if previsao_correta:
            cor_borda = (76, 175, 80)
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=6)

        badge_text = texto_resultado
        badge_bg_color = cor_resultado
        badge_text_color = (255, 255, 255)
        
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 40
            badge_h = 90
            badge_x = x1 - badge_w - 20
            badge_y = y0 + 20
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=badge_bg_color, outline=badge_bg_color)
            draw.text((badge_x + 20, badge_y + 10), badge_text, font=FONTE_RESULTADO, fill=badge_text_color)
        except:
            draw.rectangle([x1 - 180, y0 + 20, x1 - 20, y0 + 100], fill=badge_bg_color)
            draw.text((x1 - 160, y0 + 30), badge_text, font=FONTE_RESULTADO, fill=badge_text_color)

        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))

        data_formatada, hora_formatada = formatar_data_iso(jogo["data"])
        data_text = f"{data_formatada} • {hora_formatada} BRT"
        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 110), data_text, font=FONTE_INFO, fill=(120, 180, 240))
        except:
            draw.text((LARGURA//2 - 150, y0 + 110), data_text, font=FONTE_INFO, fill=(120, 180, 240))

        TAMANHO_ESCUDO = 245
        TAMANHO_QUADRADO = 280
        ESPACO_ENTRE_ESCUDOS = 700

        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS 
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_placar = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 100
        x_away = x_placar + 450

        y_escudos = y0 + 180

        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get("escudo_home", ""))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get("escudo_away", ""))

        def desenhar_escudo_quadrado_resultado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
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

        desenhar_escudo_quadrado_resultado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado_resultado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_placar + (200 - placar_w) // 2
            draw.text((placar_x, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            draw.text((x_placar, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))

        home_text = jogo['home'][:15]
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

        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

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

    rodape_text = f"Resultados oficiais • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        draw.text((LARGURA//2 - 300, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados GERADO com {len(jogos)} jogos - Sistema RED/GREEN - FUNDO QUADRADO")
    return buffer

def gerar_poster_resultados_limitado(jogos: list, titulo: str = "- RESULTADOS", max_jogos: int = 3) -> io.BytesIO:
    """Gera poster profissional com resultados finais - VERSÃO COM LIMITE DE JOGOS"""
    jogos_limitados = jogos[:max_jogos]
    
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950
    PADDING = 120
    
    jogos_count = len(jogos_limitados)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(70)
    FONTE_PLACAR = criar_fonte(100)
    FONTE_VS = criar_fonte(70)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_RESULTADO = criar_fonte(70)

    lote_text = f"LOTE {titulo.split('-')[-1].strip()}" if "LOTE" not in titulo else titulo
    try:
        titulo_bbox = draw.textbbox((0, 0), lote_text, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), lote_text, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 80), lote_text, font=FONTE_TITULO, fill=(255, 215, 0))

    draw.line([(LARGURA//4, 180), (3*LARGURA//4, 180)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos_limitados):
        total_gols = jogo['home_goals'] + jogo['away_goals']
        previsao_correta = False
        
        if jogo['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5:
            previsao_correta = True
        
        if previsao_correta:
            cor_borda = (76, 175, 80)
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=6)

        badge_text = texto_resultado
        badge_bg_color = cor_resultado
        badge_text_color = (255, 255, 255)
        
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 40
            badge_h = 90
            badge_x = x1 - badge_w - 20
            badge_y = y0 + 20
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=badge_bg_color, outline=badge_bg_color)
            draw.text((badge_x + 20, badge_y + 10), badge_text, font=FONTE_RESULTADO, fill=badge_text_color)
        except:
            draw.rectangle([x1 - 180, y0 + 20, x1 - 20, y0 + 100], fill=badge_bg_color)
            draw.text((x1 - 160, y0 + 30), badge_text, font=FONTE_RESULTADO, fill=badge_text_color)

        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))

        data_formatada, hora_formatada = formatar_data_iso(jogo["data"])
        data_text = f"{data_formatada} • {hora_formatada} BRT"
        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 110), data_text, font=FONTE_INFO, fill=(120, 180, 240))
        except:
            draw.text((LARGURA//2 - 150, y0 + 110), data_text, font=FONTE_INFO, fill=(120, 180, 240))

        TAMANHO_ESCUDO = 245
        TAMANHO_QUADRADO = 280
        ESPACO_ENTRE_ESCUDOS = 700

        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS 
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_placar = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 100
        x_away = x_placar + 450

        y_escudos = y0 + 180

        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get("escudo_home", ""))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get("escudo_away", ""))

        def desenhar_escudo_quadrado_resultado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
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

        desenhar_escudo_quadrado_resultado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado_resultado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_placar + (200 - placar_w) // 2
            draw.text((placar_x, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            draw.text((x_placar, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))

        home_text = jogo['home'][:15]
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

        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

        tipo_aposta_emoji = "+" if jogo.get('tipo_aposta') == "over" else "-"
        
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

    rodape_text = f"Partidas {len(jogos_limitados)}/{len(jogos)} • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        draw.text((LARGURA//2 - 300, altura_total - 60), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados gerado com {len(jogos_limitados)} jogos (máx: {max_jogos})")
    return buffer

# =============================
# Sistema de Monitoramento da API (original)
# =============================

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
# Funções de Envio de Alertas
# =============================
def enviar_alerta_telegram(fixture: dict, analise: dict):
    """Envia alerta individual com poster estilo West Ham"""
    try:
        poster = gerar_poster_individual_westham(fixture, analise)
        
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
        
        if enviar_foto_telegram(poster, caption=caption):
            st.success(f"📤 Alerta {analise['tipo_aposta']} individual enviado: {home} vs {away}")
            return True
        else:
            st.error(f"❌ Falha ao enviar alerta individual: {home} vs {away}")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao enviar alerta individual: {str(e)}")
        st.error(f"❌ Erro ao enviar alerta individual: {str(e)}")
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
        if alerta_individual:
            enviar_alerta_telegram(fixture, analise)
        salvar_alertas(alertas)

def enviar_alerta_westham_style(jogos_conf: list, min_conf: int, max_conf: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Envia alerta no estilo West Ham"""
    if not jogos_conf:
        st.warning("⚠️ Nenhum jogo para gerar poster")
        return

    try:
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
        msg = f"🔥 Jogos com confiança entre {min_conf}% e {max_conf}% (Erro na imagem):\n"
        for j in jogos_conf[:5]:
            tipo_emoji = "📈" if j.get('tipo_aposta') == "over" else "📉"
            msg += f"{tipo_emoji} {j['home']} vs {j['away']} | {j['tendencia']} | Conf: {j['confianca']:.0f}%\n"
        enviar_telegram(msg, chat_id=chat_id)

def enviar_alerta_resultados_poster(jogos_com_resultado: list, max_jogos_por_alerta: int = 3):
    """Envia alerta de resultados com poster para o Telegram"""
    if not jogos_com_resultado:
        st.warning("⚠️ Nenhum resultado para enviar")
        return

    try:
        jogos_por_data = {}
        for jogo in jogos_com_resultado:
            data_jogo = datetime.fromisoformat(jogo["data"].replace("Z", "+00:00")).date()
            if data_jogo not in jogos_por_data:
                jogos_por_data[data_jogo] = []
            
            total_gols = jogo['home_goals'] + jogo['away_goals']
            previsao_correta = False
            
            if jogo['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5:
                previsao_correta = True
            elif jogo['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5:
                previsao_correta = True
            elif jogo['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5:
                previsao_correta = True
            elif jogo['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5:
                previsao_correta = True
            
            jogo['resultado'] = "GREEN" if previsao_correta else "RED"
            jogos_por_data[data_jogo].append(jogo)

        alertas_enviados = 0
        
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            
            lotes = [jogos_data[i:i + max_jogos_por_alerta] 
                    for i in range(0, len(jogos_data), max_jogos_por_alerta)]
            
            st.info(f"📊 {len(jogos_data)} jogos encontrados para {data_str} - Serão enviados em {len(lotes)} lote(s)")
            
            for lote_idx, lote in enumerate(lotes):
                lote_num = lote_idx + 1
                titulo = f"ELITE MASTER - RESULTADOS {data_str} - LOTE {lote_num}/{len(lotes)}"
                
                st.info(f"🎨 Gerando poster para lote {lote_num} com {len(lote)} jogos...")
                
                poster = gerar_poster_resultados_limitado(lote, titulo=titulo, max_jogos=max_jogos_por_alerta)
                
                total_jogos_lote = len(lote)
                green_count_lote = sum(1 for j in lote if j.get('resultado') == "GREEN")
                red_count_lote = total_jogos_lote - green_count_lote
                taxa_acerto_lote = (green_count_lote / total_jogos_lote * 100) if total_jogos_lote > 0 else 0
                
                over_count_lote = sum(1 for j in lote if j.get('tipo_aposta') == "over")
                under_count_lote = sum(1 for j in lote if j.get('tipo_aposta') == "under")
                over_green_lote = sum(1 for j in lote if j.get('tipo_aposta') == "over" and j.get('resultado') == "GREEN")
                under_green_lote = sum(1 for j in lote if j.get('tipo_aposta') == "under" and j.get('resultado') == "GREEN")
                
                total_jogos_data = len(jogos_data)
                green_count_data = sum(1 for j in jogos_data if j.get('resultado') == "GREEN")
                taxa_acerto_data = (green_count_data / total_jogos_data * 100) if total_jogos_data > 0 else 0
                
                caption = (
                    f"<b>🏁 RESULTADOS OFICIAIS - {data_str}</b>\n"
                    f"<b>📦 LOTE {lote_num}/{len(lotes)}</b>\n\n"
                    
                    f"<b>📋 ESTATÍSTICAS DO LOTE:</b>\n"
                    f"<b>• Jogos: {total_jogos_lote}</b>\n"
                    f"<b>• 🟢 GREEN: {green_count_lote}</b>\n"
                    f"<b>• 🔴 RED: {red_count_lote}</b>\n"
                    f"<b>• 🎯 Acerto: {taxa_acerto_lote:.1f}%</b>\n\n"
                    
                    f"<b>📊 DESEMPENHO POR TIPO (LOTE):</b>\n"
                    f"<b>• 📈 Over: {over_green_lote}/{over_count_lote} " 
                    f"({over_green_lote/max(over_count_lote,1)*100:.0f}%)</b>\n"
                    f"<b>• 📉 Under: {under_green_lote}/{under_count_lote} "
                    f"({under_green_lote/max(under_count_lote,1)*100:.0f}%)</b>\n\n"
                    
                    f"<b>📈 ESTATÍSTICAS TOTAIS ({data_str}):</b>\n"
                    f"<b>• Total de Jogos: {total_jogos_data}</b>\n"
                    f"<b>• 🟢 GREEN: {green_count_data}</b>\n"
                    f"<b>• 🎯 Acerto Total: {taxa_acerto_data:.1f}%</b>\n\n"
                    
                    f"<b>🔥 ELITE MASTER SYSTEM - CONFIABILIDADE COMPROVADA</b>"
                )
                
                st.info(f"📤 Enviando lote {lote_num} para o Telegram...")
                ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
                
                if ok:
                    st.success(f"🚀 Lote {lote_num}/{len(lotes)} enviado para {data_str}!")
                    alertas_enviados += 1
                    
                    for jogo in lote:
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
                    
                    if lote_idx < len(lotes) - 1:
                        time.sleep(2)
                else:
                    st.error(f"❌ Falha ao enviar lote {lote_num} para {data_str}")
        
        if alertas_enviados > 0:
            st.success(f"✅ Total de {alertas_enviados} alertas de resultados enviados com sucesso!")
                
    except Exception as e:
        logging.error(f"Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        enviar_resultados_fallback(jogos_com_resultado)

def enviar_resultados_fallback(jogos_com_resultado: list, max_jogos_por_alerta: int = 5):
    """Fallback para mensagem de texto com limite de jogos por alerta"""
    if not jogos_com_resultado:
        return
        
    jogos_por_data = {}
    for jogo in jogos_com_resultado:
        data_jogo = datetime.fromisoformat(jogo["data"].replace("Z", "+00:00")).date()
        if data_jogo not in jogos_por_data:
            jogos_por_data[data_jogo] = []
        jogos_por_data[data_jogo].append(jogo)
    
    for data, jogos_data in jogos_por_data.items():
        data_str = data.strftime("%d/%m/%Y")
        
        lotes = [jogos_data[i:i + max_jogos_por_alerta] 
                for i in range(0, len(jogos_data), max_jogos_por_alerta)]
        
        for lote_idx, lote in enumerate(lotes):
            lote_num = lote_idx + 1
            
            msg = f"<b>🏁 RESULTADOS OFICIAIS - {data_str}</b>\n"
            msg += f"<b>📦 LOTE {lote_num}/{len(lotes)}</b>\n\n"
            
            for j in lote:
                total_gols = j['home_goals'] + j['away_goals']
                resultado = "🟢 GREEN" if (
                    (j['tendencia_prevista'] == "OVER 2.5" and total_gols > 2.5) or 
                    (j['tendencia_prevista'] == "UNDER 2.5" and total_gols < 2.5) or
                    (j['tendencia_prevista'] == "OVER 1.5" and total_gols > 1.5) or
                    (j['tendencia_prevista'] == "UNDER 1.5" and total_gols < 1.5)
                ) else "🔴 RED"
                tipo_emoji = "📈" if j.get('tipo_aposta') == "over" else "📉"
                msg += f"{resultado} {tipo_emoji} {j['home']} {j['home_goals']}x{j['away_goals']} {j['away']}\n"
            
            total_jogos_lote = len(lote)
            green_count_lote = sum(1 for j in lote if "🟢 GREEN" in str(j.get('resultado', '')))
            taxa_acerto_lote = (green_count_lote / total_jogos_lote * 100) if total_jogos_lote > 0 else 0
            
            msg += f"\n<b>📊 LOTE {lote_num}:</b> {green_count_lote}/{total_jogos_lote} GREEN ({taxa_acerto_lote:.1f}%)\n"
            
            enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if lote_idx < len(lotes) - 1:
                time.sleep(2)
        
        total_jogos_data = len(jogos_data)
        green_count_data = sum(1 for j in jogos_data if "🟢 GREEN" in str(j.get('resultado', '')))
        taxa_acerto_data = (green_count_data / total_jogos_data * 100) if total_jogos_data > 0 else 0
        
        resumo_msg = f"<b>📈 RESUMO FINAL - {data_str}</b>\n"
        resumo_msg += f"<b>Total: {total_jogos_data} jogos</b>\n"
        resumo_msg += f"<b>🟢 GREEN: {green_count_data} ({taxa_acerto_data:.1f}%)</b>\n"
        resumo_msg += f"<b>🔥 ELITE MASTER SYSTEM</b>"
        
        enviar_telegram(resumo_msg, chat_id=TELEGRAM_CHAT_ID_ALT2)

def enviar_alerta_conf_criar_poster(jogos_conf: list, min_conf: int, max_conf: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Função fallback para o estilo original"""
    if not jogos_conf:
        return
        
    try:
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

# =============================
# Função Principal para Top Jogos (ATUALIZADA)
# =============================
def enviar_top_jogos(jogos: list, top_n: int, alerta_top_jogos: bool, min_conf: int, max_conf: int, 
                    formato_top_jogos: str = "Ambos", data_busca: str = None):
    """Envia os top jogos para o Telegram com opção de formato"""
    if not alerta_top_jogos:
        st.info("ℹ️ Alerta de Top Jogos desativado")
        return
    
    if formato_top_jogos not in ["Texto", "Poster", "Ambos"]:
        formato_top_jogos = "Ambos"
    
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    jogos_filtrados = [j for j in jogos_filtrados if min_conf <= j["confianca"] <= max_conf]
    
    if not jogos_filtrados:
        st.warning(f"⚠️ Nenhum jogo elegível para o Top Jogos (confiança entre {min_conf}% e {max_conf}%).")
        return
        
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
    
    for jogo in top_jogos_sorted:
        adicionar_alerta_top(jogo, data_busca or datetime.now().strftime("%Y-%m-%d"))
    
    over_jogos = [j for j in top_jogos_sorted if j.get('tipo_aposta') == "over"]
    under_jogos = [j for j in top_jogos_sorted if j.get('tipo_aposta') == "under"]
    
    st.info(f"📊 Enviando TOP {len(top_jogos_sorted)} jogos - Formato: {formato_top_jogos}")
    st.info(f"💾 Salvando {len(top_jogos_sorted)} alertas TOP para conferência futura")
    
    if formato_top_jogos in ["Texto", "Ambos"]:
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
            st.success(f"📝 Texto dos TOP {top_n} jogos enviado!")
        else:
            st.error("❌ Erro ao enviar texto dos TOP jogos")
    
    if formato_top_jogos in ["Poster", "Ambos"]:
        try:
            st.info(f"🎨 Gerando poster para TOP {len(top_jogos_sorted)} jogos...")
            
            poster = gerar_poster_top_jogos(top_jogos_sorted, min_conf, max_conf)
            
            total_jogos = len(top_jogos_sorted)
            confianca_media = sum(j['confianca'] for j in top_jogos_sorted) / total_jogos
            
            caption = (
                f"<b>🏆 TOP {len(top_jogos_sorted)} JOGOS DO DIA 🏆</b>\n\n"
                f"<b>🎯 Intervalo de Confiança: {min_conf}% - {max_conf}%</b>\n"
                f"<b>📈 Over: {len(over_jogos)} jogos</b>\n"
                f"<b>📉 Under: {len(under_jogos)} jogos</b>\n"
                f"<b>⚽ Confiança Média: {confianca_media:.1f}%</b>\n\n"
                f"<b>🔥 JOGOS COM MAIOR POTENCIAL DO DIA</b>\n"
                f"<b>⭐ Ordenados por nível de confiança</b>\n\n"
                f"<b>🎯 ELITE MASTER SYSTEM - SELEÇÃO INTELIGENTE</b>"
            )
            
            if enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2):
                st.success(f"🖼️ Poster dos TOP {len(top_jogos_sorted)} jogos enviado!")
            else:
                st.error("❌ Erro ao enviar poster dos TOP jogos")
                
        except Exception as e:
            logging.error(f"Erro ao gerar/enviar poster TOP jogos: {e}")
            st.error(f"❌ Erro ao gerar poster: {e}")
            
            if formato_top_jogos == "Poster":
                st.info("🔄 Tentando fallback para texto...")
                enviar_telegram(
                    f"⚠️ Erro ao gerar poster dos TOP jogos. Seguem os {len(top_jogos_sorted)} jogos em texto:\n\n" +
                    "\n".join([f"• {j['home']} vs {j['away']} - {j['tendencia']} ({j['confianca']:.0f}%)" 
                              for j in top_jogos_sorted[:10]]),
                    TELEGRAM_CHAT_ID_ALT2
                )

# =============================
# SISTEMA DE ALERTAS DE RESULTADOS
# =============================
@measure_performance("verificar_resultados_finais")
def verificar_resultados_finais(alerta_resultados: bool):
    """Verifica resultados finais dos jogos e envia alertas"""
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para verificar resultados.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture_data = obter_dados_api(url)
            
            if not fixture_data:
                continue
                
            match = fixture_data.get('match', fixture_data)
            status = match.get("status", "")
            score = match.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
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
    
    if jogos_com_resultado and alerta_resultados:
        enviar_alerta_resultados_poster(jogos_com_resultado, max_jogos_por_alerta=3)
        salvar_alertas(alertas)
        st.success(f"✅ {resultados_enviados} resultados processados e alertas enviados!")
    elif jogos_com_resultado:
        st.info(f"ℹ️ {resultados_enviados} resultados encontrados, mas alerta de resultados desativado")
        salvar_alertas(alertas)
    else:
        st.info("ℹ️ Nenhum novo resultado final encontrado.")

# =============================
# FUNÇÕES PRINCIPAIS (OTIMIZADAS)
# =============================
def debug_jogos_dia(data_selecionada, ligas_selecionadas, todas_ligas=False):
    """Função de debug para verificar os jogos retornados pela API"""
    hoje = data_selecionada.strftime("%Y-%m-%d")
    
    if todas_ligas:
        ligas_busca = list(LIGA_DICT.values())
    else:
        ligas_busca = [LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
    
    st.write("🔍 **DEBUG DETALHADO - JOGOS DA API**")
    
    for liga_id in ligas_busca:
        if liga_id == "BSA":
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
                
                hora_corrigida = formatar_data_iso_para_datetime(data_utc)
                data_br = hora_corrigida.strftime("%d/%m/%Y")
                hora_br = hora_corrigida.strftime("%H:%M")
                
                st.write(f"  {i+1}. {home} vs {away}")
                st.write(f"     UTC: {data_utc}")
                st.write(f"     BR: {data_br} {hora_br} | Status: {status}")
                st.write(f"     Competição: {match.get('competition', {}).get('name', 'Desconhecido')}")
                
            except Exception as e:
                st.write(f"  {i+1}. ERRO ao processar jogo: {e}")

@measure_performance("processar_jogos_otimizada")
def processar_jogos_otimizada(data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf, max_conf, estilo_poster, 
                             alerta_individual: bool, alerta_poster: bool, alerta_top_jogos: bool, 
                             formato_top_jogos: str, tipo_filtro: str):
    """Versão OTIMIZADA da função principal"""
    
    hoje = data_selecionada.strftime("%Y-%m-%d")
    
    if todas_ligas:
        ligas_busca = list(LIGA_DICT.values())
        st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
    else:
        ligas_busca = [LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
        st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

    st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
    
    top_jogos = []
    progress_bar = st.progress(0)
    total_ligas = len(ligas_busca)

    # ============================================================
    # OTIMIZAÇÃO 1: Pré-busca paralela de classificações
    # ============================================================
    
    classificacoes = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_liga = {executor.submit(obter_classificacao, liga_id): liga_id for liga_id in ligas_busca}
        
        for future in as_completed(future_to_liga):
            liga_id = future_to_liga[future]
            try:
                classificacoes[liga_id] = future.result(timeout=10)
            except TimeoutError:
                logging.warning(f"Timeout ao buscar classificação da liga {liga_id}")
                classificacoes[liga_id] = {}
            except Exception as e:
                logging.error(f"Erro ao buscar classificação da liga {liga_id}: {e}")
                classificacoes[liga_id] = {}
    
    # ============================================================
    # OTIMIZAÇÃO 2: Processamento em batch inteligente
    # ============================================================
    
    for i, liga_id in enumerate(ligas_busca):
        classificacao = classificacoes[liga_id]
        
        if liga_id == "BSA":
            jogos = obter_jogos_brasileirao(liga_id, hoje)
        else:
            jogos = obter_jogos(liga_id, hoje)
        
        if not jogos:
            progress_bar.progress((i + 1) / total_ligas)
            continue
        
        # Filtrar jogos ANTES de processar
        jogos_validos = []
        for match in jogos:
            if not validar_dados_jogo(match):
                continue
                
            status = match.get("status", "")
            if status in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]:
                continue
                
            jogos_validos.append(match)
        
        st.write(f"📊 Liga {liga_id}: {len(jogos_validos)}/{len(jogos)} jogos válidos")
        
        # Processamento paralelo por batch
        batch_size = min(10, len(jogos_validos))
        for j in range(0, len(jogos_validos), batch_size):
            batch = jogos_validos[j:j+batch_size]
            batch_results = []
            
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                future_to_match = {}
                for match in batch:
                    home = match["homeTeam"]["name"]
                    away = match["awayTeam"]["name"]
                    
                    future = executor.submit(
                        calcular_tendencia_completa_melhorada,
                        home, away, classificacao
                    )
                    future_to_match[future] = match
                
                for future in as_completed(future_to_match):
                    match = future_to_match[future]
                    try:
                        analise = future.result(timeout=5)
                        batch_results.append((match, analise))
                    except TimeoutError:
                        logging.warning(f"Timeout ao analisar {match['homeTeam']['name']} vs {match['awayTeam']['name']}")
                    except Exception as e:
                        logging.error(f"Erro ao analisar partida: {e}")
            
            # Processar resultados do batch
            for match, analise in batch_results:
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                data_utc = match["utcDate"]
                hora_corrigida = formatar_data_iso_para_datetime(data_utc)
                
                tipo_emoji = "📈" if analise["tipo_aposta"] == "over" else "📉"
                
                st.write(f"   {tipo_emoji} {home} vs {away}")
                st.write(f"      🕒 {hora_corrigida.strftime('%H:%M')} | {analise['tendencia']}")
                st.write(f"      ⚽ {analise['estimativa']:.2f} | 🎯 {analise['probabilidade']:.0f}% | 🔍 {analise['confianca']:.0f}%")
                
                # Verificar se deve enviar alerta individual
                if min_conf <= analise["confianca"] <= max_conf:
                    if tipo_filtro == "Todos" or \
                       (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or \
                       (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                        
                        verificar_enviar_alerta(match, analise, alerta_individual, min_conf, max_conf)
                
                # Extrair escudos
                escudo_home = match.get("homeTeam", {}).get("crest") or match.get("homeTeam", {}).get("logo") or ""
                escudo_away = match.get("awayTeam", {}).get("crest") or match.get("awayTeam", {}).get("logo") or ""
                
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
                    "status": match.get("status", "DESCONHEDIDO"),
                    "escudo_home": escudo_home,
                    "escudo_away": escudo_away,
                    "detalhes": analise.get("detalhes", {})
                })
        
        progress_bar.progress((i + 1) / total_ligas)
    
    # ============================================================
    # OTIMIZAÇÃO 3: Processamento final otimizado
    # ============================================================
    
    # Filtrar por intervalo de confiança e tipo
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
    
    # Estatísticas rápidas
    over_jogos = [j for j in jogos_filtrados if j["tipo_aposta"] == "over"]
    under_jogos = [j for j in jogos_filtrados if j["tipo_aposta"] == "under"]
    
    st.write(f"📊 Total processado: {len(top_jogos)} jogos")
    st.write(f"✅ Após filtros: {len(jogos_filtrados)} jogos")
    st.write(f"📈 Over: {len(over_jogos)} | 📉 Under: {len(under_jogos)}")
    
    # Processar alertas
    if jogos_filtrados:
        # Enviar top jogos
        enviar_top_jogos(jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf, formato_top_jogos, data_busca=hoje)
        
        # Enviar alerta de imagem
        if alerta_poster:
            if estilo_poster == "West Ham (Novo)":
                enviar_alerta_westham_style(jogos_filtrados, min_conf, max_conf)
            else:
                enviar_alerta_conf_criar_poster(jogos_filtrados, min_conf, max_conf)
        
        st.success(f"✅ {len(jogos_filtrados)} jogos com confiança {min_conf}%-{max_conf}% ({tipo_filtro})")
    else:
        st.warning(f"⚠️ Nenhum jogo com confiança entre {min_conf}% e {max_conf}% ({tipo_filtro})")
    
    # ============================================================
    # OTIMIZAÇÃO 4: Log de performance
    # ============================================================
    
    performance_data = performance_monitor.get_performance_summary()
    if "operations" in performance_data:
        process_time = performance_data["operations"].get("processar_jogos_otimizada", {})
        if process_time:
            st.info(f"⏱️ Tempo de processamento: {process_time.get('avg_ms', 0):.0f}ms")
    
    return jogos_filtrados

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
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH, ALERTAS_TOP_PATH]:
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
    
    over_jogos = [h for h in historico_recente if h.get('tipo_aposta') == "over"]
    under_jogos = [h for h in historico_recente if h.get('tipo_aposta') == "under"]
    
    over_green = sum(1 for h in over_jogos if "GREEN" in str(h.get('resultado', '')))
    under_green = sum(1 for h in under_jogos if "GREEN" in str(h.get('resultado', '')))
    
    over_total = len(over_jogos)
    under_total = len(under_jogos)
    
    taxa_over = (over_green / over_total * 100) if over_total > 0 else 0
    taxa_under = (under_green / under_total * 100) if under_total > 0 else 0
    taxa_geral = ((over_green + under_green) / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho calculado para {total_jogos} jogos!")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Jogos", total_jogos)
    with col2:
        st.metric("Taxa de Acerto Geral", f"{taxa_geral:.1f}%")
    with col3:
        st.metric("Confiança Média", f"{sum(h.get('confianca', 0) for h in historico_recente) / total_jogos:.1f}%")
    
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
    
    over_jogos = [h for h in historico_periodo if h.get('tipo_aposta') == "over"]
    under_jogos = [h for h in historico_periodo if h.get('tipo_aposta') == "under"]
    
    over_green = sum(1 for h in over_jogos if "GREEN" in str(h.get('resultado', '')))
    under_green = sum(1 for h in under_jogos if "GREEN" in str(h.get('resultado', '')))
    
    over_total = len(over_jogos)
    under_total = len(under_jogos)
    
    taxa_over = (over_green / over_total * 100) if over_total > 0 else 0
    taxa_under = (under_green / under_total * 100) if under_total > 0 else 0
    taxa_geral = ((over_green + under_green) / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho do período calculado! {total_jogos} jogos analisados.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Jogos no Período", total_jogos)
    with col2:
        st.metric("Dias Analisados", (data_fim - data_inicio).days)
    with col3:
        st.metric("Acerto Geral", f"{taxa_geral:.1f}%")
    
    st.subheader("📊 Desempenho por Tipo")
    col4, col5 = st.columns(2)
    with col4:
        st.metric("📈 Over", f"{over_green}/{over_total}", f"{taxa_over:.1f}%")
    with col5:
        st.metric("📉 Under", f"{under_green}/{under_total}", f"{taxa_under:.1f}%")

# =============================
# Painel de Monitoramento Avançado (NOVO)
# =============================
def mostrar_painel_monitoramento_avancado():
    """Mostra painel de monitoramento avançado"""
    
    st.markdown("---")
    st.subheader("📊 Painel de Monitoramento Avançado")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Performance", "🗂️ Cache", "🔗 API", "⚠️ Alertas"])
    
    with tab1:
        perf_data = performance_monitor.get_performance_summary()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Uptime", f"{perf_data.get('uptime_minutes', 0):.0f} min")
        with col2:
            st.metric("Operações", len(perf_data.get('operations', {})))
        with col3:
            st.metric("Erros", perf_data.get('errors_count', 0))
        
        slow_ops = performance_monitor.get_slow_operations(500)
        if slow_ops:
            st.warning("🐌 Operações Lentas Detectadas:")
            for op in slow_ops:
                st.write(f"  • {op['operation']}: {op['avg_ms']}ms ({op['count']}x)")
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            stats_jogos = jogos_cache.get_stats_enhanced()
            st.write("**Cache de Jogos:**")
            st.write(f"Hit Rate: {stats_jogos.get('hit_rate', '0%')}")
            st.write(f"Uso: {stats_jogos.get('usage_percent', '0%')}")
        
        with col2:
            stats_img = escudos_cache.get_stats()
            st.write("**Cache de Imagens:**")
            st.write(f"Em memória: {stats_img.get('memoria', 0)}")
            st.write(f"Disco: {stats_img.get('disco_mb', 0):.1f}MB")
        
        if st.button("🧹 Limpar Caches", key="clean_caches_tab"):
            jogos_cache.clear()
            classificacao_cache.clear()
            match_cache.clear()
            st.success("Caches limpos!")
    
    with tab3:
        api_status = api_fallback.get_status_report()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Endpoints Saudáveis", api_status.get('healthy_endpoints', 0))
        with col2:
            st.metric("Endpoints Problemáticos", api_status.get('unhealthy_endpoints', 0))
        
        with st.expander("Detalhes dos Endpoints"):
            for endpoint, details in api_status.get('details', {}).items():
                status_emoji = "✅" if details['status'] == 'healthy' else "❌"
                st.write(f"{status_emoji} {endpoint}")
                st.write(f"  Falhas: {details['failure_count']}")
    
    with tab4:
        alertas_top = carregar_alertas_top()
        alertas_ativos = carregar_alertas()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Alertas TOP", len(alertas_top))
        with col2:
            st.metric("Alertas Ativos", len(alertas_ativos))
        
        datas_completas = verificar_conjuntos_completos()
        if datas_completas:
            st.success(f"✅ {len(datas_completas)} conjuntos completos para reportar")
            if st.button("📤 Enviar Relatórios", key="send_reports_tab"):
                enviou = enviar_alerta_top_conferidos()
                if enviou:
                    st.success("Relatórios enviados!")

# =============================
# Inicialização Otimizada do Sistema
# =============================
def inicializar_sistema_otimizado():
    """Inicializa todos os componentes otimizados"""
    
    global performance_monitor
    performance_monitor = PerformanceMonitor()
    
    global jogos_cache, classificacao_cache, match_cache, escudos_cache
    
    jogos_cache = SmartCacheEnhanced("jogos")
    classificacao_cache = SmartCacheEnhanced("classificacao")
    match_cache = SmartCacheEnhanced("match_details")
    escudos_cache = ImageCacheEnhanced()
    
    global api_fallback
    api_fallback = APIFallbackSystem()
    
    global prefetch_system
    prefetch_system = PrefetchSystem()
    prefetch_system.start()
    
    def cleanup_periodico():
        while True:
            time.sleep(3600)
            jogos_cache.auto_cleanup()
            classificacao_cache.auto_cleanup()
            match_cache.auto_cleanup()
            escudos_cache.cleanup_low_priority()
    
    cleanup_thread = threading.Thread(target=cleanup_periodico, daemon=True)
    cleanup_thread.start()
    
    logging.info("🚀 Sistema otimizado inicializado com sucesso!")

# =============================
# Interface Streamlit
# =============================
def main():
    # Inicializar sistema otimizado
    inicializar_sistema_otimizado()
    
    st.set_page_config(page_title="⚽ Alerta de Gols Over/Under", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos Over/Under")

    # Sidebar - CONFIGURAÇÕES DE ALERTAS
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True, 
                                       help="Envia alerta individual para cada jogo com confiança alta")
        
        alerta_poster = st.checkbox("📊 Alertas com Poster", value=True,
                                   help="Envia poster com múltiplos jogos acima do limiar")
        
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True,
                                      help="Envia lista dos top jogos do dia")
        
        alerta_conferencia_auto = st.checkbox("🤖 Alerta Auto Conferência", value=True,
                                             help="Envia alerta automático quando todos os Top N forem conferidos")
        
        formato_top_jogos = st.selectbox(
            "📋 Formato do Top Jogos",
            ["Ambos", "Texto", "Poster"],
            index=0,
            help="Escolha o formato para os alertas de Top Jogos"
        )
        
        alerta_resultados = st.checkbox("🏁 Resultados Finais", value=True,
                                       help="Envia alerta de resultados com sistema RED/GREEN")
        
        st.markdown("----")
        
        st.header("Configurações Gerais")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        
        col_min, col_max = st.columns(2)
        with col_min:
            min_conf = st.slider("Confiança Mínima (%)", 10, 95, 70, 1)
        with col_max:
            max_conf = st.slider("Confiança Máxima (%)", min_conf, 95, 95, 1)
        
        estilo_poster = st.selectbox("🎨 Estilo do Poster", ["West Ham (Novo)", "Elite Master (Original)"], index=0)
        
        tipo_filtro = st.selectbox("🔍 Filtrar por Tipo", ["Todos", "Apenas Over", "Apenas Under"], index=0)
        
        st.markdown("----")
        st.info(f"Intervalo de confiança: {min_conf}% a {max_conf}%")
        st.info(f"Filtro: {tipo_filtro}")
        st.info(f"Formato Top Jogos: {formato_top_jogos}")
        if alerta_conferencia_auto:
            st.info("🤖 Alerta automático: ATIVADO")

    # Controles principais
    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    ligas_selecionadas = []
    if not todas_ligas:
        ligas_selecionadas = st.multiselect(
            "📌 Selecionar ligas (múltipla escolha):",
            options=list(LIGA_DICT.keys()),
            default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"]
        )
        
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga")
        else:
            st.info(f"📋 {len(ligas_selecionadas)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

    # BOTÃO DE DEBUG
    if st.button("🐛 Debug Jogos (API)", type="secondary"):
        if todas_ligas:
            debug_jogos_dia(data_selecionada, [], todas_ligas=True)
        else:
            debug_jogos_dia(data_selecionada, ligas_selecionadas, todas_ligas=False)

    # NOVO: Botão para verificar conjuntos completos
    if st.button("🔍 Verificar Conjuntos Completos", type="secondary"):
        datas_completas = verificar_conjuntos_completos()
        if datas_completas:
            st.success(f"✅ Encontrados {len(datas_completas)} conjuntos completos para reportar:")
            for data in datas_completas:
                data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
                st.write(f"📅 {data_formatada}")
            
            if st.button("📤 Enviar Alertas de Conferência"):
                enviou = enviar_alerta_top_conferidos()
                if enviou:
                    st.success("✅ Alertas de conferência enviados!")
        else:
            st.info("ℹ️ Nenhum conjunto completo para reportar.")

    # Processamento
    if st.button("🔍 Buscar Partidas", type="primary"):
        if not todas_ligas and not ligas_selecionadas:
            st.error("❌ Selecione pelo menos uma liga ou marque 'Todas as ligas'")
        else:
            processar_jogos_otimizada(data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf, max_conf, estilo_poster, 
                           alerta_individual, alerta_poster, alerta_top_jogos, formato_top_jogos, tipo_filtro)

    # Ações
    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        if st.button("🏆 Conferir Alertas TOP", type="primary"):
            conferir_resultados_top()
            if alerta_conferencia_auto:
                enviou = enviar_alerta_top_conferidos()
                if enviou:
                    st.success("🤖 Alerta automático de conferência enviado!")

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

    col_cache1, col_cache2, col_cache3, col_cache4 = st.columns(4)

    with col_cache1:
        stats_jogos = jogos_cache.get_stats_enhanced()
        st.metric("Cache de Jogos", f"{stats_jogos['current_size']}/{stats_jogos['max_size']}", 
                 stats_jogos['hit_rate'])

    with col_cache2:
        stats_class = classificacao_cache.get_stats_enhanced()
        st.metric("Cache de Classificação", f"{stats_class['current_size']}/{stats_class['max_size']}", 
                 stats_class['hit_rate'])

    with col_cache3:
        stats_match = match_cache.get_stats_enhanced()
        st.metric("Cache de Partidas", f"{stats_match['current_size']}/{stats_match['max_size']}", 
                 stats_match['hit_rate'])

    with col_cache4:
        stats_img = escudos_cache.get_stats()
        st.metric("Cache de Imagens", f"{stats_img['memoria']}/{escudos_cache.max_size}", 
                 f"{stats_img['disco_mb']:.1f}MB")

    if st.button("🧹 Limpar Caches Inteligentes"):
        jogos_cache.clear()
        classificacao_cache.clear()
        match_cache.clear()
        escudos_cache.clear()
        st.success("✅ Todos os caches inteligentes limpos!")

    # Painel de monitoramento avançado
    mostrar_painel_monitoramento_avancado()

    # Painel desempenho
    st.markdown("---")
    st.subheader("📊 Painel de Desempenho")
    
    if st.button("📈 Calcular Desempenho Alertas TOP"):
        calcular_desempenho_alertas_top()
    
    usar_periodo = st.checkbox("🔎 Usar período específico", value=False)
    qtd_default = 50
    last_n = st.number_input("Últimos N jogos", 1, 1000, qtd_default, 1)
    colp1, colp2 = st.columns(2)
    with colp1:
        if usar_periodo:
            data_inicio = st.date_input("Data inicial", value=(datetime.today() - timedelta(days=30)).date())
            data_fim = st.date_input("Data final", value=datetime.today().date())
    with colp2:
        if st.button("📈 Calcular Desempenho Histórico"):
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

if __name__ == "__main__":
    main()
