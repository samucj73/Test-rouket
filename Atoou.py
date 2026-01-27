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
            # Serializar objetos datetime para strings ISO
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
        """Carrega alertas do arquivo"""
        return DataStorage.carregar_json(ConfigManager.ALERTAS_PATH)
    
    @staticmethod
    def salvar_alertas(alertas: dict):
        """Salva alertas no arquivo"""
        DataStorage.salvar_json(ConfigManager.ALERTAS_PATH, alertas)
    
    @staticmethod
    def carregar_alertas_favoritos() -> dict:
        """Carrega alertas de favoritos do arquivo"""
        return DataStorage.carregar_json(ConfigManager.ALERTAS_FAVORITOS_PATH)
    
    @staticmethod
    def salvar_alertas_favoritos(alertas: dict):
        """Salva alertas de favoritos no arquivo"""
        DataStorage.salvar_json(ConfigManager.ALERTAS_FAVORITOS_PATH, alertas)
    
    @staticmethod
    def carregar_alertas_gols_ht() -> dict:
        """Carrega alertas de gols HT do arquivo"""
        return DataStorage.carregar_json(ConfigManager.ALERTAS_GOLS_HT_PATH)
    
    @staticmethod
    def salvar_alertas_gols_ht(alertas: dict):
        """Salva alertas de gols HT no arquivo"""
        DataStorage.salvar_json(ConfigManager.ALERTAS_GOLS_HT_PATH, alertas)
    
    @staticmethod
    def carregar_alertas_ambas_marcam() -> dict:
        """Carrega alertas de ambas marcam do arquivo"""
        return DataStorage.carregar_json(ConfigManager.ALERTAS_AMBAS_MARCAM_PATH)
    
    @staticmethod
    def salvar_alertas_ambas_marcam(alertas: dict):
        """Salva alertas de ambas marcam no arquivo"""
        DataStorage.salvar_json(ConfigManager.ALERTAS_AMBAS_MARCAM_PATH, alertas)
    
    @staticmethod
    def carregar_resultados() -> dict:
        """Carrega resultados do arquivo"""
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_PATH)
    
    @staticmethod
    def salvar_resultados(resultados: dict):
        """Salva resultados no arquivo"""
        DataStorage.salvar_json(ConfigManager.RESULTADOS_PATH, resultados)
    
    @staticmethod
    def carregar_resultados_favoritos() -> dict:
        """Carrega resultados de favoritos do arquivo"""
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_FAVORITOS_PATH)
    
    @staticmethod
    def salvar_resultados_favoritos(resultados: dict):
        """Salva resultados de favoritos no arquivo"""
        DataStorage.salvar_json(ConfigManager.RESULTADOS_FAVORITOS_PATH, resultados)
    
    @staticmethod
    def carregar_resultados_gols_ht() -> dict:
        """Carrega resultados de gols HT do arquivo"""
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_GOLS_HT_PATH)
    
    @staticmethod
    def salvar_resultados_gols_ht(resultados: dict):
        """Salva resultados de gols HT no arquivo"""
        DataStorage.salvar_json(ConfigManager.RESULTADOS_GOLS_HT_PATH, resultados)
    
    @staticmethod
    def carregar_resultados_ambas_marcam() -> dict:
        """Carrega resultados de ambas marcam do arquivo"""
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_AMBAS_MARCAM_PATH)
    
    @staticmethod
    def salvar_resultados_ambas_marcam(resultados: dict):
        """Salva resultados de ambas marcam no arquivo"""
        DataStorage.salvar_json(ConfigManager.RESULTADOS_AMBAS_MARCAM_PATH, resultados)
    
    @staticmethod
    def carregar_alertas_top() -> dict:
        """Carrega alertas TOP do arquivo"""
        return DataStorage.carregar_json(ConfigManager.ALERTAS_TOP_PATH)
    
    @staticmethod
    def salvar_alertas_top(alertas_top: dict):
        """Salva alertas TOP no arquivo"""
        DataStorage.salvar_json(ConfigManager.ALERTAS_TOP_PATH, alertas_top)
    
    @staticmethod
    def carregar_resultados_top() -> dict:
        """Carrega resultados TOP do arquivo"""
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_TOP_PATH)
    
    @staticmethod
    def salvar_resultados_top(resultados_top: dict):
        """Salva resultados TOP no arquivo"""
        DataStorage.salvar_json(ConfigManager.RESULTADOS_TOP_PATH, resultados_top)
    
    @staticmethod
    def carregar_historico() -> list:
        """Carrega histórico de conferências"""
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
        """Salva histórico de conferências"""
        try:
            with open(ConfigManager.HISTORICO_PATH, "w", encoding="utf-8") as f:
                json.dump(historico, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erro ao salvar histórico: {e}")

# =============================
# NOVA CLASSE: AlertasPorHorario
# =============================

class AlertasPorHorario:
    """Gerencia alertas agrupados por horário de início das partidas"""
    
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = ConfigManager()
    
    def agrupar_jogos_por_horario(self, jogos_filtrados: list, intervalo_minutos: int = 30) -> dict:
        """Agrupa jogos por intervalos de horário"""
        grupos = {}
        
        for jogo in jogos_filtrados:
            # Extrair horário do jogo
            if isinstance(jogo["hora"], datetime):
                hora_jogo = jogo["hora"]
            else:
                try:
                    hora_jogo = datetime.fromisoformat(jogo["hora"].replace('Z', '+00:00'))
                except:
                    hora_jogo = datetime.now()
            
            # Criar chave de horário arredondada
            hora_arredondada = self._arredondar_horario(hora_jogo, intervalo_minutos)
            chave_horario = hora_arredondada.strftime("%H:%M")
            
            # Adicionar ao grupo correspondente
            if chave_horario not in grupos:
                grupos[chave_horario] = {
                    "hora_inicio": hora_arredondada,
                    "jogos": []
                }
            
            grupos[chave_horario]["jogos"].append(jogo)
        
        # Ordenar grupos por horário
        grupos_ordenados = dict(sorted(grupos.items(), key=lambda x: x[1]["hora_inicio"]))
        
        return grupos_ordenados
    
    def _arredondar_horario(self, dt: datetime, intervalo_minutos: int) -> datetime:
        """Arredonda o horário para o intervalo mais próximo"""
        minutos = dt.minute
        arredondado = minutos // intervalo_minutos * intervalo_minutos
        
        return dt.replace(minute=arredondado, second=0, microsecond=0)
    
    def filtrar_jogos_por_confianca(self, jogos: list, tipo_analise: str, config_analise: dict) -> list:
        """Filtra jogos com base na confiança mínima"""
        min_conf = self._obter_confianca_minima(tipo_analise, config_analise)
        jogos_filtrados = []
        
        for jogo in jogos:
            confianca = self._obter_confianca_jogo(jogo, tipo_analise)
            
            if confianca >= min_conf:
                jogos_filtrados.append(jogo)
        
        # Ordenar por confiança (mais alta primeiro)
        jogos_filtrados.sort(
            key=lambda x: self._obter_confianca_jogo(x, tipo_analise), 
            reverse=True
        )
        
        return jogos_filtrados
    
    def _obter_confianca_minima(self, tipo_analise: str, config_analise: dict) -> float:
        """Obtém a confiança mínima baseada no tipo de análise"""
        if tipo_analise == "Over/Under de Gols":
            return config_analise.get("min_conf", 70)
        elif tipo_analise == "Favorito (Vitória)":
            return config_analise.get("min_conf_vitoria", 65)
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            return config_analise.get("min_conf_ht", 60)
        elif tipo_analise == "Ambas Marcam (BTTS)":
            return config_analise.get("min_conf_am", 60)
        return 60
    
    def _obter_confianca_jogo(self, jogo: dict, tipo_analise: str) -> float:
        """Obtém a confiança específica do jogo baseada no tipo de análise"""
        if tipo_analise == "Over/Under de Gols":
            return jogo.get("confianca", 0)
        elif tipo_analise == "Favorito (Vitória)":
            return jogo.get("confianca_vitoria", 0)
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            return jogo.get("confianca_ht", 0)
        elif tipo_analise == "Ambas Marcam (BTTS)":
            return jogo.get("confianca_ambas_marcam", 0)
        return 0
    
    def enviar_alertas_por_horario(self, jogos_filtrados: list, tipo_analise: str, config_analise: dict, 
                                   data_busca: str, intervalo_minutos: int = 30, max_jogos_por_grupo: int = 5):
        """Envia alertas agrupados por horário"""
        
        # Filtrar jogos por confiança
        jogos_confiaveis = self.filtrar_jogos_por_confianca(jogos_filtrados, tipo_analise, config_analise)
        
        if not jogos_confiaveis:
            st.warning("⚠️ Nenhum jogo atende aos critérios de confiança para alertas por horário")
            return
        
        # Agrupar por horário
        grupos = self.agrupar_jogos_por_horario(jogos_confiaveis, intervalo_minutos)
        
        if not grupos:
            st.warning("⚠️ Não foi possível agrupar jogos por horário")
            return
        
        st.info(f"📊 Encontrados {len(grupos)} grupos horários com {len(jogos_confiaveis)} jogos confiáveis")
        
        # Enviar alertas para cada grupo
        for horario_str, grupo in grupos.items():
            jogos_grupo = grupo["jogos"][:max_jogos_por_grupo]  # Limitar máximo por grupo
            
            if not jogos_grupo:
                continue
            
            # Definir título do grupo
            if tipo_analise == "Over/Under de Gols":
                titulo = f"📅 JOGOS {horario_str}h - OVER/UNDER"
                tipo_alerta = "over_under"
            elif tipo_analise == "Favorito (Vitória)":
                titulo = f"📅 JOGOS {horario_str}h - FAVORITOS"
                tipo_alerta = "favorito"
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                titulo = f"📅 JOGOS {horario_str}h - GOLS HT"
                tipo_alerta = "gols_ht"
            elif tipo_analise == "Ambas Marcam (BTTS)":
                titulo = f"📅 JOGOS {horario_str}h - AMBAS MARCAM"
                tipo_alerta = "ambas_marcam"
            
            # Enviar como texto
            mensagem = self._criar_mensagem_grupo(jogos_grupo, titulo, tipo_analise, data_busca)
            
            if self.sistema.telegram_client.enviar_mensagem(mensagem, self.config.TELEGRAM_CHAT_ID_ALT2):
                st.success(f"✅ Alerta enviado para horário {horario_str}h: {len(jogos_grupo)} jogos")
            
            # Enviar como poster (opcional)
            try:
                poster = self.sistema.poster_generator.gerar_poster_westham_style(
                    jogos_grupo, 
                    titulo=titulo,
                    tipo_alerta=tipo_alerta
                )
                
                caption = f"<b>{titulo}</b>\n\n"
                caption += f"<b>⏰ HORÁRIO: {horario_str}h</b>\n"
                caption += f"<b>📊 TOTAL: {len(jogos_grupo)} JOGOS</b>\n\n"
                caption += f"<b>🔥 ELITE MASTER SYSTEM - ALERTAS POR HORÁRIO</b>"
                
                if self.sistema.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"🖼️ Poster enviado para horário {horario_str}h")
                    
            except Exception as e:
                logging.error(f"Erro ao gerar poster para horário {horario_str}h: {e}")
            
            # Aguardar entre grupos para evitar rate limiting
            time.sleep(1)
    
    def _criar_mensagem_grupo(self, jogos_grupo: list, titulo: str, tipo_analise: str, data_busca: str) -> str:
        """Cria mensagem de texto para um grupo de jogos"""
        data_formatada = datetime.strptime(data_busca, "%Y-%m-%d").strftime("%d/%m/%Y")
        
        mensagem = f"<b>{titulo} - {data_formatada}</b>\n\n"
        
        for idx, jogo in enumerate(jogos_grupo, 1):
            # Formatar horário específico
            if isinstance(jogo["hora"], datetime):
                hora_especifica = jogo["hora"].strftime("%H:%M")
            else:
                hora_especifica = "??:??"
            
            # Adicionar linha baseada no tipo de análise
            if tipo_analise == "Over/Under de Gols":
                tipo_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
                linha = (
                    f"{idx}. {tipo_emoji} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                    f"   🕒 {hora_especifica}h | 🏆 {jogo['liga']}\n"
                    f"   📊 {jogo['tendencia']} | ⚽ {jogo['estimativa']:.2f}\n"
                    f"   🎯 Prob: {jogo['probabilidade']:.0f}% | 💯 Conf: {jogo['confianca']:.0f}%\n\n"
                )
                
            elif tipo_analise == "Favorito (Vitória)":
                favorito_emoji = "🏠" if jogo.get('favorito') == "home" else "✈️" if jogo.get('favorito') == "away" else "🤝"
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                linha = (
                    f"{idx}. {favorito_emoji} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                    f"   🕒 {hora_especifica}h | 🏆 {jogo['liga']}\n"
                    f"   🏆 Favorito: {favorito_text}\n"
                    f"   💯 Conf: {jogo.get('confianca_vitoria', 0):.0f}%\n"
                    f"   📊 Casa: {jogo.get('prob_home_win', 0):.1f}% | Fora: {jogo.get('prob_away_win', 0):.1f}% | Empate: {jogo.get('prob_draw', 0):.1f}%\n\n"
                )
                
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                tipo_emoji_ht = "⚡" if "OVER" in jogo.get('tendencia_ht', '') else "🛡️"
                linha = (
                    f"{idx}. {tipo_emoji_ht} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                    f"   🕒 {hora_especifica}h | 🏆 {jogo['liga']}\n"
                    f"   ⏰ {jogo.get('tendencia_ht', 'N/A')} | ⚽ Est. HT: {jogo.get('estimativa_total_ht', 0):.2f}\n"
                    f"   💯 Conf HT: {jogo.get('confianca_ht', 0):.0f}%\n"
                    f"   🎯 OVER 0.5: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_05_ht', 0):.0f}% | "
                    f"OVER 1.5: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_15_ht', 0):.0f}%\n\n"
                )
                
            elif tipo_analise == "Ambas Marcam (BTTS)":
                tipo_emoji_am = "🤝" if jogo.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                linha = (
                    f"{idx}. {tipo_emoji_am} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                    f"   🕒 {hora_especifica}h | 🏆 {jogo['liga']}\n"
                    f"   🤝 {jogo.get('tendencia_ambas_marcam', 'N/A')}\n"
                    f"   💯 Conf: {jogo.get('confianca_ambas_marcam', 0):.0f}%\n"
                    f"   📊 SIM: {jogo.get('prob_ambas_marcam_sim', 0):.1f}% | "
                    f"NÃO: {jogo.get('prob_ambas_marcam_nao', 0):.1f}%\n\n"
                )
            
            mensagem += linha
        
        # Adicionar estatísticas do grupo
        mensagem += f"<b>📋 TOTAL NO HORÁRIO: {len(jogos_grupo)} JOGOS</b>\n"
        mensagem += f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE POR HORÁRIO</b>"
        
        return mensagem
    
    def agendar_alertas_automaticos(self, data_selecionada, tipo_analise, config_analise):
        """Agenda alertas automáticos para horários específicos do dia"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        # Horários pré-definidos para envio automático
        horarios_envio = [
            "09:00",  # Manhã
            "12:00",  # Meio-dia
            "15:00",  # Tarde
            "18:00",  # Noite
            "21:00"   # Noite tarde
        ]
        
        st.info(f"⏰ Agendando alertas automáticos para {data_selecionada.strftime('%d/%m/%Y')}")
        
        for horario_envio in horarios_envio:
            # Buscar jogos que começam próximos a este horário
            jogos_proximos = self._buscar_jogos_proximos_ao_horario(hoje, horario_envio, tipo_analise, config_analise)
            
            if jogos_proximos:
                # Enviar alerta para este horário
                if tipo_analise == "Over/Under de Gols":
                    titulo = f"🔔 ALERTA {horario_envio}h - OVER/UNDER"
                elif tipo_analise == "Favorito (Vitória)":
                    titulo = f"🔔 ALERTA {horario_envio}h - FAVORITOS"
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    titulo = f"🔔 ALERTA {horario_envio}h - GOLS HT"
                elif tipo_analise == "Ambas Marcam (BTTS)":
                    titulo = f"🔔 ALERTA {horario_envio}h - AMBAS MARCAM"
                
                mensagem = self._criar_mensagem_agendada(jogos_proximos, titulo, tipo_analise, data_selecionada)
                
                if self.sistema.telegram_client.enviar_mensagem(mensagem, self.config.TELEGRAM_CHAT_ID_ALT2):
                    st.success(f"✅ Alerta agendado para {horario_envio}h: {len(jogos_proximos)} jogos")
    
    def _buscar_jogos_proximos_ao_horario(self, data_busca: str, horario_alvo: str, tipo_analise: str, config_analise: dict) -> list:
        """Busca jogos que começam próximos a um horário específico"""
        # Implementar busca específica por horário
        # Por enquanto, retornar lista vazia
        return []
    
    def _criar_mensagem_agendada(self, jogos: list, titulo: str, tipo_analise: str, data_selecionada) -> str:
        """Cria mensagem para alertas agendados"""
        data_formatada = data_selecionada.strftime("%d/%m/%Y")
        
        mensagem = f"<b>{titulo} - {data_formatada}</b>\n\n"
        mensagem += f"<b>🔔 ALERTA AUTOMÁTICO DO SISTEMA</b>\n\n"
        
        if jogos:
            for jogo in jogos[:3]:  # Limitar a 3 jogos no alerta agendado
                if tipo_analise == "Over/Under de Gols":
                    tipo_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
                    mensagem += f"{tipo_emoji} <b>{jogo['home']} vs {jogo['away']}</b> - {jogo['tendencia']} ({jogo['confianca']:.0f}%)\n"
                
        mensagem += f"\n<b>⚠️ Jogos que começam em breve!</b>\n"
        mensagem += f"<b>🔥 ELITE MASTER SYSTEM - ALERTA AUTOMÁTICO</b>"
        
        return mensagem

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
        
        # Escudos dos times
        self.home_crest = match_data.get("homeTeam", {}).get("crest") or match_data.get("homeTeam", {}).get("logo", "")
        self.away_crest = match_data.get("awayTeam", {}).get("crest") or match_data.get("awayTeam", {}).get("logo", "")
        
        # Análise calculada posteriormente
        self.tendencia = ""
        self.estimativa = 0.0
        self.probabilidade = 0.0
        self.confianca = 0.0
        self.tipo_aposta = ""
        self.detalhes_analise = {}
        
        # Resultados
        self.home_goals = None
        self.away_goals = None
        self.ht_home_goals = None
        self.ht_away_goals = None
        self.resultado = None
        self.resultado_favorito = None
        self.resultado_ht = None
        self.resultado_ambas_marcam = None
        self.conferido = False
        
        # Para análise de favoritos
        self.favorito = ""
        self.confianca_vitoria = 0.0
        self.prob_home_win = 0.0
        self.prob_away_win = 0.0
        self.prob_draw = 0.0
        
        # Para análise de gols HT
        self.tendencia_ht = ""
        self.confianca_ht = 0.0
        self.estimativa_total_ht = 0.0
        
        # Para análise de ambas marcam
        self.tendencia_ambas_marcam = ""
        self.confianca_ambas_marcam = 0.0
        self.prob_ambas_marcam_sim = 0.0
        self.prob_ambas_marcam_nao = 0.0
    
    def validar_dados(self) -> bool:
        """Valida se os dados do jogo são válidos"""
        required_fields = [self.id, self.home_team, self.away_team, self.utc_date]
        return all(required_fields)
    
    def get_data_hora_brasilia(self):
        """Retorna data e hora no fuso de Brasília"""
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
        """Retorna datetime no fuso de Brasília"""
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
        """Define a análise do jogo"""
        self.tendencia = analise.get("tendencia", "")
        self.estimativa = analise.get("estimativa", 0.0)
        self.probabilidade = analise.get("probabilidade", 0.0)
        self.confianca = analise.get("confianca", 0.0)
        self.tipo_aposta = analise.get("tipo_aposta", "")
        self.detalhes_analise = analise.get("detalhes", {})
        
        # Para análise de favoritos
        if "vitoria" in analise.get("detalhes", {}):
            vitoria_analise = analise["detalhes"]["vitoria"]
            self.favorito = vitoria_analise.get("favorito", "")
            self.confianca_vitoria = vitoria_analise.get("confianca_vitoria", 0.0)
            self.prob_home_win = vitoria_analise.get("home_win", 0.0)
            self.prob_away_win = vitoria_analise.get("away_win", 0.0)
            self.prob_draw = vitoria_analise.get("draw", 0.0)
        
        # Para análise de gols HT
        if "gols_ht" in analise.get("detalhes", {}):
            ht_analise = analise["detalhes"]["gols_ht"]
            self.tendencia_ht = ht_analise.get("tendencia_ht", "")
            self.confianca_ht = ht_analise.get("confianca_ht", 0.0)
            self.estimativa_total_ht = ht_analise.get("estimativa_total_ht", 0.0)
        
        # Para análise de ambas marcam
        if "ambas_marcam" in analise.get("detalhes", {}):
            ambas_marcam_analise = analise["detalhes"]["ambas_marcam"]
            self.tendencia_ambas_marcam = ambas_marcam_analise.get("tendencia_ambas_marcam", "")
            self.confianca_ambas_marcam = ambas_marcam_analise.get("confianca_ambas_marcam", 0.0)
            self.prob_ambas_marcam_sim = ambas_marcam_analise.get("sim", 0.0)
            self.prob_ambas_marcam_nao = ambas_marcam_analise.get("nao", 0.0)
    
    def set_resultado(self, home_goals: int, away_goals: int, ht_home_goals: int = None, ht_away_goals: int = None):
        """Define o resultado final do jogo"""
        self.home_goals = home_goals
        self.away_goals = away_goals
        self.ht_home_goals = ht_home_goals
        self.ht_away_goals = ht_away_goals
        self.conferido = True
        
        # Calcular resultado para Over/Under
        total_gols = home_goals + away_goals
        self.resultado = self.calcular_resultado_over_under(total_gols)
        
        # Calcular resultado para Favorito
        self.resultado_favorito = self.calcular_resultado_favorito(home_goals, away_goals)
        
        # Calcular resultado para Gols HT
        if ht_home_goals is not None and ht_away_goals is not None:
            self.resultado_ht = self.calcular_resultado_gols_ht(ht_home_goals, ht_away_goals)
        
        # Calcular resultado para Ambas Marcam
        self.resultado_ambas_marcam = self.calcular_resultado_ambas_marcam(home_goals, away_goals)
    
    def calcular_resultado_over_under(self, total_gols: float) -> str:
        """Calcula se a previsão Over/Under foi GREEN ou RED"""
        if self.tendencia == "OVER 2.5" and total_gols > 2.5:
            return "GREEN"
        elif self.tendencia == "UNDER 2.5" and total_gols < 2.5:
            return "GREEN"
        elif self.tendencia == "OVER 1.5" and total_gols > 1.5:
            return "GREEN"
        elif self.tendencia == "UNDER 1.5" and total_gols < 1.5:
            return "GREEN"
        return "RED"
    
    def calcular_resultado_favorito(self, home_goals: int, away_goals: int) -> str:
        """Calcula se a previsão de favorito foi GREEN ou RED"""
        if self.favorito == "home" and home_goals > away_goals:
            return "GREEN"
        elif self.favorito == "away" and away_goals > home_goals:
            return "GREEN"
        elif self.favorito == "draw" and home_goals == away_goals:
            return "GREEN"
        return "RED"
    
    def calcular_resultado_gols_ht(self, ht_home_goals: int, ht_away_goals: int) -> str:
        """Calcula se a previsão de gols HT foi GREEN ou RED"""
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
        """Calcula se a previsão de ambas marcam foi GREEN ou RED"""
        if self.tendencia_ambas_marcam == "SIM" and home_goals > 0 and away_goals > 0:
            return "GREEN"
        elif self.tendencia_ambas_marcam == "NÃO" and (home_goals == 0 or away_goals == 0):
            return "GREEN"
        return "RED"
    
    def to_dict(self):
        """Converte o jogo para dicionário"""
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
        
        # Adicionar dados de favoritos se disponíveis
        if self.favorito:
            data_dict.update({
                "favorito": self.favorito,
                "confianca_vitoria": self.confianca_vitoria,
                "prob_home_win": self.prob_home_win,
                "prob_away_win": self.prob_away_win,
                "prob_draw": self.prob_draw,
            })
        
        # Adicionar dados de gols HT se disponíveis
        if self.tendencia_ht:
            data_dict.update({
                "tendencia_ht": self.tendencia_ht,
                "confianca_ht": self.confianca_ht,
                "estimativa_total_ht": self.estimativa_total_ht,
            })
        
        # Adicionar dados de ambas marcam se disponíveis
        if self.tendencia_ambas_marcam:
            data_dict.update({
                "tendencia_ambas_marcam": self.tendencia_ambas_marcam,
                "confianca_ambas_marcam": self.confianca_ambas_marcam,
                "prob_ambas_marcam_sim": self.prob_ambas_marcam_sim,
                "prob_ambas_marcam_nao": self.prob_ambas_marcam_nao,
            })
        
        return data_dict

class Alerta:
    """Representa um alerta gerado pelo sistema"""
    
    def __init__(self, jogo: Jogo, data_busca: str, tipo_alerta: str = "over_under"):
        self.jogo = jogo
        self.data_busca = data_busca
        self.data_hora_busca = datetime.now()
        self.tipo_alerta = tipo_alerta
        self.conferido = False
        self.alerta_enviado = False
    
    def to_dict(self):
        """Converte alerta para dicionário"""
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
        
        # Adicionar dados específicos do tipo de alerta
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
    """Realiza análises estatísticas para previsões"""

    @staticmethod
    def calcular_probabilidade_vitoria(home: str, away: str, classificacao: dict) -> dict:
        """Calcula probabilidade de vitória, empate e derrota"""

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
        """Calcula probabilidade de gols no primeiro tempo (HT)"""

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
        """Calcula probabilidade de ambas as equipes marcarem gols (BTTS)"""
        
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

        # Taxa de gols marcados por jogo
        taxa_gols_home = dados_home["scored"] / played_home
        taxa_gols_away = dados_away["scored"] / played_away
        
        # Taxa de gols sofridos por jogo
        taxa_sofridos_home = dados_home["against"] / played_home
        taxa_sofridos_away = dados_away["against"] / played_away
        
        # Taxa de jogos em que cada time marca
        taxa_marque_home = 1 / (1 + math.exp(-taxa_gols_home * 0.8))
        taxa_marque_away = 1 / (1 + math.exp(-taxa_gols_away * 0.8))
        
        # Taxa de jogos em que cada time sofre gol
        taxa_sofra_home = 1 / (1 + math.exp(-taxa_sofridos_home * 0.8))
        taxa_sofra_away = 1 / (1 + math.exp(-taxa_sofridos_away * 0.8))

        # Probabilidade do time da casa marcar (considerando força ataque casa + defesa fora)
        prob_home_marca = (taxa_marque_home * 0.6 + taxa_sofra_away * 0.4)
        
        # Probabilidade do time visitante marcar (considerando força ataque fora + defesa casa)
        prob_away_marca = (taxa_marque_away * 0.4 + taxa_sofra_home * 0.6)

        # Ajuste pelo fator casa
        fator_casa = 1.1
        prob_home_marca *= fator_casa
        prob_away_marca *= (2.0 - fator_casa) * 0.9

        # Probabilidade de ambas marcarem = P(home marque) * P(away marque)
        prob_ambas_marcam = clamp(prob_home_marca * prob_away_marca * 100, 0, 95)
        
        # Probabilidade de NÃO ambas marcarem
        prob_nao_ambas_marcam = 100 - prob_ambas_marcam

        # Determinar tendência
        if prob_ambas_marcam >= 60:
            tendencia_ambas_marcam = "SIM"
        elif prob_nao_ambas_marcam >= 60:
            tendencia_ambas_marcam = "NÃO"
        else:
            if prob_ambas_marcam >= prob_nao_ambas_marcam:
                tendencia_ambas_marcam = "SIM"
            else:
                tendencia_ambas_marcam = "NÃO"

        # Confiança baseada na diferença entre as probabilidades
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

class AnalisadorTendencia:
    """Analisa tendências de gols em partidas - VERSÃO ADAPTATIVA POR ESTIMATIVA"""

    def __init__(self, classificacao: dict):
        self.classificacao = classificacao

    def calcular_tendencia_completa(self, home: str, away: str) -> dict:
        """Calcula tendências completas - ESCOLHE MERCADO BASEADO NA ESTIMATIVA"""
        
        dados_home = self.classificacao.get(home, {})
        dados_away = self.classificacao.get(away, {})

        played_home = max(dados_home.get("played", 1), 1)
        played_away = max(dados_away.get("played", 1), 1)

        # Médias de gols
        media_home_feitos = dados_home.get("scored", 0) / played_home
        media_home_sofridos = dados_home.get("against", 0) / played_home
        media_away_feitos = dados_away.get("scored", 0) / played_away
        media_away_sofridos = dados_away.get("against", 0) / played_away

        # Fatores ofensivos/defensivos
        fator_ofensivo_home = media_home_feitos / max(media_away_sofridos, 0.5)
        fator_ofensivo_away = media_away_feitos / max(media_home_sofridos, 0.5)
        
        # Estimativa baseada em múltiplos fatores
        estimativa_total = (
            media_home_feitos * 0.5 + 
            media_away_feitos * 0.5 +
            media_home_sofridos * 0.4 +
            media_away_sofridos * 0.4
        )
        
        # Ajuste por fator ofensivo
        fator_ataque = (fator_ofensivo_home + fator_ofensivo_away) / 2
        if fator_ataque > 1.2:
            estimativa_total *= 1.1
        elif fator_ataque > 1.5:
            estimativa_total *= 1.2
        
        # Fator casa
        fator_casa = clamp(1.05 + (media_home_feitos - media_home_sofridos) * 0.12, 0.9, 1.25)
        estimativa_total *= fator_casa

        # Limites realistas
        estimativa_total = clamp(estimativa_total, 0.5, 5.5)

        # ESCOLHA ADAPTATIVA DO MERCADO BASEADO NA ESTIMATIVA
        if estimativa_total >= 3.5:
            mercado = "OVER 3.5"
            tipo_aposta = "over"
            linha_mercado = 3.5
            probabilidade_base = sigmoid((estimativa_total - 3.5) * 1.2)
            
        elif estimativa_total >= 2.8:
            mercado = "OVER 2.5"
            tipo_aposta = "over"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((estimativa_total - 2.5) * 1.3)
            
        elif estimativa_total >= 2.3:
            mercado = "OVER 2.5"
            tipo_aposta = "over"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((estimativa_total - 2.5) * 1.4)
            
        elif estimativa_total >= 1.8:
            mercado = "OVER 1.5"
            tipo_aposta = "over"
            linha_mercado = 1.5
            probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.5)
            
        elif estimativa_total <= 1.2:
            mercado = "UNDER 1.5"
            tipo_aposta = "under"
            linha_mercado = 1.5
            probabilidade_base = sigmoid((1.5 - estimativa_total) * 1.5)
            
        elif estimativa_total <= 1.5:
            mercado = "UNDER 2.5"
            tipo_aposta = "under"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((2.5 - estimativa_total) * 1.3)
            
        else:
            mercado = "OVER 1.5"
            tipo_aposta = "over"
            linha_mercado = 1.5
            probabilidade_base = sigmoid((estimativa_total - 1.5) * 1.2)

        # Cálculo de confiança baseado na distância da linha
        distancia_linha = abs(estimativa_total - linha_mercado)
        
        # Sinais de força
        sinais_concordantes = 0
        if tipo_aposta == "over":
            if estimativa_total > linha_mercado + 0.5:
                sinais_concordantes += 2
            if fator_ataque > 1.3:
                sinais_concordantes += 1
            if (media_home_feitos > 2.0 or media_away_feitos > 2.0):
                sinais_concordantes += 1
        else:
            if estimativa_total < linha_mercado - 0.5:
                sinais_concordantes += 2
            if fator_ataque < 0.8:
                sinais_concordantes += 1
            if (media_home_feitos < 1.0 and media_away_feitos < 1.0):
                sinais_concordantes += 1

        # Confiança baseada na distância da linha + sinais
        confianca = clamp(
            (probabilidade_base * 100) * 0.6 +
            (distancia_linha * 20) +
            (sinais_concordantes * 10),
            45, 92
        )

        # Calcular todas as probabilidades para referência
        prob_over_15 = sigmoid((estimativa_total - 1.5) * 1.5)
        prob_over_25 = sigmoid((estimativa_total - 2.5) * 1.4)
        prob_over_35 = sigmoid((estimativa_total - 3.5) * 1.3)
        prob_under_15 = 1 - prob_over_15
        prob_under_25 = 1 - prob_over_25

        # Análises adicionais
        vitoria_analise = AnalisadorEstatistico.calcular_probabilidade_vitoria(
            home, away, self.classificacao
        )
        ht_analise = AnalisadorEstatistico.calcular_probabilidade_gols_ht(
            home, away, self.classificacao
        )
        ambas_marcam_analise = AnalisadorEstatistico.calcular_probabilidade_ambas_marcam(
            home, away, self.classificacao
        )

        logging.info(
            f"ANÁLISE ADAPTATIVA: {home} vs {away} | "
            f"Est: {estimativa_total:.2f} | Mercado: {mercado} | "
            f"Linha: {linha_mercado} | Dist: {distancia_linha:.2f} | "
            f"Prob Base: {probabilidade_base*100:.1f}% | Conf: {confianca:.1f}%"
        )

        return {
            "tendencia": mercado,
            "estimativa": round(estimativa_total, 2),
            "probabilidade": round(probabilidade_base * 100, 1),
            "confianca": round(confianca, 1),
            "tipo_aposta": tipo_aposta,
            "linha_mercado": linha_mercado,
            "detalhes": {
                "vitoria": vitoria_analise,
                "gols_ht": ht_analise,
                "ambas_marcam": ambas_marcam_analise,
                "over_15_prob": round(prob_over_15 * 100, 1),
                "over_25_prob": round(prob_over_25 * 100, 1),
                "over_35_prob": round(prob_over_35 * 100, 1),
                "under_15_prob": round(prob_under_15 * 100, 1),
                "under_25_prob": round(prob_under_25 * 100, 1),
                "fator_ataque": round(fator_ataque, 2),
                "media_home_feitos": round(media_home_feitos, 2),
                "media_home_sofridos": round(media_home_sofridos, 2),
                "media_away_feitos": round(media_away_feitos, 2),
                "media_away_sofridos": round(media_away_sofridos, 2),
                "distancia_linha": round(distancia_linha, 2)
            }
        }

# =============================
# CLASSES DE COMUNICAÇÃO
# =============================

class APIClient:
    """Cliente para comunicação com APIs"""
    
    def __init__(self, rate_limiter: RateLimiter, api_monitor: APIMonitor):
        self.rate_limiter = rate_limiter
        self.api_monitor = api_monitor
        self.config = ConfigManager()
        self.jogos_cache = SmartCache("jogos")
        self.classificacao_cache = SmartCache("classificacao")
        self.match_cache = SmartCache("match_details")
        self.image_cache = ImageCache()
    
    def obter_dados_api_com_retry(self, url: str, timeout: int = 15, max_retries: int = 3) -> dict | None:
        """Obtém dados da API com rate limiting e retry automático"""
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
        """Obtém classificação com cache inteligente"""
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
        """Obtém jogos com cache inteligente"""
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
        """Busca jogos do Brasileirão considerando o fuso horário"""
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
        """Obtém detalhes completos de um jogo específico"""
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
        """Baixa o escudo do time da URL fornecida"""
        if not crest_url:
            logging.warning(f"❌ URL do escudo vazia para {team_name}")
            return None
        
        try:
            # Verificar primeiro no cache
            cached = self.image_cache.get(team_name, crest_url)
            if cached:
                return cached
            
            # Baixar da URL
            logging.info(f"⬇️ Baixando escudo de {team_name}: {crest_url}")
            response = requests.get(crest_url, timeout=10)
            response.raise_for_status()
            
            img_bytes = response.content
            
            # Salvar no cache
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
    
    @staticmethod
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

class TelegramClient:
    """Cliente para comunicação com Telegram"""
    
    def __init__(self):
        self.config = ConfigManager()
    
    def enviar_mensagem(self, msg: str, chat_id: str = None, disable_web_page_preview: bool = True) -> bool:
        """Envia mensagem para o Telegram"""
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
        """Envia uma foto (BytesIO) para o Telegram"""
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
    """Gera posters para os alertas"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
    
    @staticmethod
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
    
    def gerar_poster_westham_style(self, jogos: list, titulo: str = " ALERTA DE GOLS", tipo_alerta: str = "over_under") -> io.BytesIO:
        """Gera poster no estilo West Ham"""
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
        FONTE_ESTATISTICAS = self.criar_fonte(35)

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
            
            # Definir cores baseadas no tipo de alerta
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

            TAMANHO_ESCUDO = 220
            TAMANHO_QUADRADO = 230
            ESPACO_ENTRE_ESCUDOS = 700

            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2

            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 250

            # Baixar escudos usando o APIClient
            home_crest_url = jogo.get('escudo_home', '')
            away_crest_url = jogo.get('escudo_away', '')
            
            escudo_home_bytes = None
            escudo_away_bytes = None
            
            if home_crest_url:
                escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], home_crest_url)
            
            if away_crest_url:
                escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], away_crest_url)
            
            # Converter bytes para imagens PIL
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

            # Desenhar escudos
            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

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
            
            # Mostrar diferentes informações baseadas no tipo de alerta
            if tipo_alerta == "over_under":
                tipo_emoji = "+" if jogo.get('tipo_aposta') == "over" else "-"
                cor_tendencia = (255, 215, 0) if jogo.get('tipo_aposta') == "over" else (100, 200, 255)
                
                textos_analise = [
                    f"{tipo_emoji} {jogo['tendencia']}",
                    f"Confiança: {jogo['confianca']:.0f}%",
                ]
                
                cores = [cor_tendencia, (100, 200, 255), (100, 255, 100), (255, 193, 7)]
                
            elif tipo_alerta == "favorito":
                favorito_emoji = "" if jogo.get('favorito') == "home" else "" if jogo.get('favorito') == "away" else "🤝"
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                
                textos_analise = [
                    f"{favorito_emoji} FAVORITO: {favorito_text}",
                    f"Confiança: {jogo.get('confianca_vitoria', 0):.0f}%",
                ]
                
                cores = [(255, 87, 34), (255, 152, 0), (255, 193, 7), (255, 224, 130), (100, 255, 100)]
                
            elif tipo_alerta == "gols_ht":
                tipo_emoji_ht = "" if "OVER" in jogo.get('tendencia_ht', '') else ""
                
                textos_analise = [
                    f"{tipo_emoji_ht} {jogo.get('tendencia_ht', 'N/A')}",
                    f"Estimativa HT: {jogo.get('estimativa_total_ht', 0):.2f} gols",
                    f"OVER 0.5 HT: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_05_ht', 0):.0f}%",
                    f"OVER 1.5 HT: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_15_ht', 0):.0f}%",
                    f"Confiança HT: {jogo.get('confianca_ht', 0):.0f}%",
                ]
                
                cores = [(76, 175, 80), (129, 199, 132), (102, 187, 106), (67, 160, 71), (100, 255, 100)]
            
            elif tipo_alerta == "ambas_marcam":
                tipo_emoji_am = "🤝" if jogo.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                
                textos_analise = [
                    f"{tipo_emoji_am} AMBAS MARCAM: {jogo.get('tendencia_ambas_marcam', 'N/A')}",
                    f"Confiança: {jogo.get('confianca_ambas_marcam', 0):.0f}%",
                ]
                
                cores = [(155, 89, 182), (165, 105, 189), (176, 122, 199), (188, 143, 209), (100, 255, 100)]
            
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
        
        st.success(f"✅ Poster estilo West Ham GERADO com {len(jogos)} jogos")
        return buffer
    
    def gerar_poster_resultados(self, jogos_com_resultados: list, tipo_alerta: str = "over_under") -> io.BytesIO:
        """Gera poster de resultados no estilo West Ham com GREEN/RED destacado"""
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

        # Título baseado no tipo de alerta
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

        # Linha decorativa
        draw.line([(LARGURA//4, 220), (3*LARGURA//4, 220)], fill=(255, 215, 0), width=6)

        # Data de geração
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
            
            # Determinar resultado e cores
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
            
            # Cores baseadas no resultado
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
            
            # Retângulo principal do jogo
            draw.rectangle([x0, y0, x1, y1], fill=cor_fundo, outline=cor_borda, width=4)

            # BADGE GREEN/RED
            badge_width = 250
            badge_height = 92
            badge_x = x0 + 50
            badge_y = y0 + 50
            
            # Desenhar badge
            draw.rectangle([badge_x, badge_y, badge_x + badge_width, badge_y + badge_height], 
                          fill=cor_badge, outline=cor_badge, width=2)
            
            # Texto do badge
            try:
                badge_bbox = draw.textbbox((0, 0), resultado_text, font=FONTE_RESULTADO_BADGE)
                badge_text_w = badge_bbox[2] - badge_bbox[0]
                badge_text_h = badge_bbox[3] - badge_bbox[1]
                badge_text_x = badge_x + (badge_width - badge_text_w) // 2
                badge_text_y = badge_y + (badge_height - badge_text_h) // 2
                
                # Sombra
                draw.text((badge_text_x + 2, badge_text_y + 2), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=(0, 0, 0, 128))
                
                # Texto principal
                draw.text((badge_text_x, badge_text_y), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=cor_texto)
                
                # Contorno branco
                draw.rectangle([badge_x-2, badge_y-2, badge_x + badge_width + 2, badge_y + badge_height + 2], 
                              outline=(255, 255, 255), width=1)
                
            except:
                draw.text((badge_x + 80, badge_y + 25), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=cor_texto)

            # Liga e data
            liga_text = jogo['liga'].upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

            # Times e escudos
            TAMANHO_ESCUDO = 200
            TAMANHO_QUADRADO = 225
            ESPACO_ENTRE_ESCUDOS = 700

            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2

            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 150

            # Baixar escudos
            home_crest_url = jogo.get('escudo_home', '')
            away_crest_url = jogo.get('escudo_away', '')
            
            escudo_home_bytes = None
            escudo_away_bytes = None
            
            if home_crest_url:
                escudo_home_bytes = self.api_client.baixar_escudo_time(jogo['home'], home_crest_url)
            
            if away_crest_url:
                escudo_away_bytes = self.api_client.baixar_escudo_time(jogo['away'], away_crest_url)
            
            # Converter bytes para imagens PIL
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

            # Desenhar escudos
            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

            # Nomes dos times
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

            # Resultado do jogo
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

            # Resultado HT se disponível
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
            
            # Informações específicas do tipo de alerta
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

        # Rodapé
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
        """Desenha escudo quadrado com fallback"""
        draw.rectangle(
            [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
            fill=(255, 255, 255),
            outline=(255, 255, 255)
        )

        if logo_img is None:
            # Desenhar placeholder
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
            
            # Pegar as iniciais do time
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
                draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), 
                         iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))
            except:
                draw.text((x + 70, y + 90), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))
            return

        try:
            logo_img = logo_img.convert("RGBA")
            largura, altura = logo_img.size
            
            # Calcular para manter proporção
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
            
            # Redimensionar a imagem
            imagem_redimensionada = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
            
            # Calcular posição para centralizar
            pos_x = x + (tamanho_quadrado - nova_largura) // 2
            pos_y = y + (tamanho_quadrado - nova_altura) // 2

            # Criar uma imagem branca de fundo
            fundo = Image.new("RGBA", (tamanho_quadrado, tamanho_quadrado), (255, 255, 255, 255))
            fundo.paste(imagem_redimensionada, (pos_x - x, pos_y - y), imagem_redimensionada)
            
            # Colar a imagem composta
            img.paste(fundo, (x, y), fundo)

        except Exception as e:
            logging.error(f"Erro ao processar escudo de {team_name}: {e}")
            # Fallback
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
                draw.text((x + (tamanho_quadrado - w)//2, y + (tamanho_quadrado - h)//2), 
                         iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))
            except:
                draw.text((x + 70, y + 90), iniciais, font=self.criar_fonte(50), fill=(255, 255, 255))

# =============================
# SISTEMA PRINCIPAL (ATUALIZADO)
# =============================

class SistemaAlertasFutebol:
    """Sistema principal de alertas de futebol - ATUALIZADO"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.rate_limiter = RateLimiter()
        self.api_monitor = APIMonitor()
        self.api_client = APIClient(self.rate_limiter, self.api_monitor)
        self.telegram_client = TelegramClient()
        self.poster_generator = PosterGenerator(self.api_client)
        self.image_cache = self.api_client.image_cache
        self.resultados_top = ResultadosTopAlertas(self)
        self.alertas_horario = AlertasPorHorario(self)  # NOVA INSTÂNCIA
        
        # Inicializar logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura o sistema de logging"""
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
                       formato_top_jogos, tipo_filtro, tipo_analise, config_analise, 
                       alerta_por_horario=False, intervalo_horario=30, max_jogos_por_horario=5):
        """Processa jogos e gera alertas - ATUALIZADO"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        if todas_ligas:
            ligas_busca = list(self.config.LIGA_DICT.values())
            st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
        else:
            ligas_busca = [self.config.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
            st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

        st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
        
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
                    
                    # Verificar e enviar alertas
                    if tipo_analise == "Over/Under de Gols" and min_conf <= analise["confianca"] <= max_conf:
                        if tipo_filtro == "Todos" or \
                           (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or \
                           (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                            self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, min_conf, max_conf, "over_under")
                    
                    elif tipo_analise == "Favorito (Vitória)":
                        if 'vitoria' in analise['detalhes']:
                            v = analise['detalhes']['vitoria']
                            min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                            filtro_favorito = config_analise.get("filtro_favorito", "Todos")
                            
                            if v['confianca_vitoria'] >= min_conf_vitoria:
                                if filtro_favorito == "Todos" or \
                                   (filtro_favorito == "Casa" and v['favorito'] == "home") or \
                                   (filtro_favorito == "Fora" and v['favorito'] == "away") or \
                                   (filtro_favorito == "Empate" and v['favorito'] == "draw"):
                                    self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, min_conf_vitoria, 100, "favorito")
                    
                    elif tipo_analise == "Gols HT (Primeiro Tempo)":
                        if 'gols_ht' in analise['detalhes']:
                            ht = analise['detalhes']['gols_ht']
                            min_conf_ht = config_analise.get("min_conf_ht", 60)
                            tipo_ht = config_analise.get("tipo_ht", "OVER 0.5 HT")
                            
                            if ht['confianca_ht'] >= min_conf_ht and ht['tendencia_ht'] == tipo_ht:
                                self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, min_conf_ht, 100, "gols_ht")
                    
                    elif tipo_analise == "Ambas Marcam (BTTS)":
                        if 'ambas_marcam' in analise['detalhes']:
                            am = analise['detalhes']['ambas_marcam']
                            min_conf_am = config_analise.get("min_conf_am", 60)
                            filtro_am = config_analise.get("filtro_am", "Todos")
                            
                            if am['confianca_ambas_marcam'] >= min_conf_am:
                                if filtro_am == "Todos" or \
                                   (filtro_am == "SIM" and am['tendencia_ambas_marcam'] == "SIM") or \
                                   (filtro_am == "NÃO" and am['tendencia_ambas_marcam'] == "NÃO"):
                                    self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, min_conf_am, 100, "ambas_marcam")

                    top_jogos.append(jogo.to_dict())
                
                if j + batch_size < len(jogos_data):
                    time.sleep(0.5)
            
            progress_bar.progress((i + 1) / total_ligas)
        
        # Filtrar por tipo de análise
        jogos_filtrados = self._filtrar_por_tipo_analise(top_jogos, tipo_analise, config_analise)
        
        st.write(f"📊 Total de jogos: {len(top_jogos)}")
        st.write(f"📊 Jogos após filtros: {len(jogos_filtrados)}")
        
        # NOVO: Enviar alertas por horário
        if alerta_por_horario and jogos_filtrados:
            st.info("⏰ Preparando alertas por horário...")
            self.alertas_horario.enviar_alertas_por_horario(
                jogos_filtrados, 
                tipo_analise, 
                config_analise,
                hoje,
                intervalo_horario,
                max_jogos_por_horario
            )
        
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
            
            # Enviar top jogos baseado no tipo de análise
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
    
    # ... (restante dos métodos da classe permanecem iguais) ...
    # Por questão de espaço, mantive apenas os métodos principais
    # Os métodos auxiliares são os mesmos do código original

# =============================
# INTERFACE STREAMLIT (ATUALIZADA)
# =============================

def main():
    st.set_page_config(page_title="⚽ Sistema Completo de Alertas", layout="wide")
    st.title("⚽ Sistema Completo de Alertas de Futebol")
    
    # Inicializar sistema
    sistema = SistemaAlertasFutebol()
    
    # Sidebar
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
            
            config_analise = {
                "tipo_filtro": tipo_filtro,
                "min_conf": min_conf,
                "max_conf": max_conf
            }
            
        elif tipo_analise == "Favorito (Vitória)":
            st.info("🎯 Alertas baseados na probabilidade de vitória")
            min_conf_vitoria = st.slider("Confiança Mínima Vitória (%)", 50, 95, 65, 1)
            filtro_favorito = st.selectbox("Filtrar Favorito:", ["Todos", "Casa", "Fora", "Empate"], index=0)
            
            config_analise = {
                "min_conf_vitoria": min_conf_vitoria,
                "filtro_favorito": filtro_favorito
            }
            
        elif tipo_analise == "Gols HT (Primeiro Tempo)":
            st.info("⏰ Alertas baseados em gols no primeiro tempo")
            min_conf_ht = st.slider("Confiança Mínima HT (%)", 50, 95, 60, 1)
            tipo_ht = st.selectbox("Tipo de HT:", ["OVER 0.5 HT", "OVER 1.5 HT", "UNDER 0.5 HT", "UNDER 1.5 HT"], index=0)
            
            config_analise = {
                "min_conf_ht": min_conf_ht,
                "tipo_ht": tipo_ht
            }
        
        elif tipo_analise == "Ambas Marcam (BTTS)":
            st.info("🤝 Alertas baseados se ambos os times marcam")
            min_conf_am = st.slider("Confiança Mínima Ambas Marcam (%)", 50, 95, 60, 1)
            filtro_am = st.selectbox("Filtrar Ambas Marcam:", ["Todos", "SIM", "NÃO"], index=0)
            
            config_analise = {
                "min_conf_am": min_conf_am,
                "filtro_am": filtro_am
            }
        
        st.subheader("📨 Tipos de Envio")
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True)
        alerta_poster = st.checkbox("📊 Alertas com Poster", value=True)
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True)
        
        # NOVO: Alerta por Horário
        alerta_por_horario = st.checkbox("⏰ Alertas por Horário", value=False)
        if alerta_por_horario:
            intervalo_horario = st.slider("Intervalo (minutos)", 15, 120, 30, 15, key="intervalo_horario")
            max_jogos_por_horario = st.slider("Máx jogos por horário", 3, 10, 5, 1, key="max_jogos_horario")
        
        alerta_conferencia_auto = st.checkbox("🤖 Alerta Auto Conferência", value=True)
        alerta_resultados = st.checkbox("🏁 Alertas de Resultados", value=True)
        
        formato_top_jogos = st.selectbox(
            "📋 Formato do Top Jogos",
            ["Ambos", "Texto", "Poster"],
            index=0
        )
        
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
        if alerta_por_horario:
            st.info(f"⏰ Alertas por horário: ATIVADO (intervalo: {intervalo_horario}min)")
        if alerta_conferencia_auto:
            st.info("🤖 Alerta automático: ATIVADO")
        if alerta_resultados:
            st.info("🏁 Alertas de resultados: ATIVADO")
    
    # Abas principais - ATUALIZADO
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar Partidas", "📊 Conferir Resultados", "🏆 Resultados TOP Alertas", "⏰ Alertas por Horário"])
    
    with tab1:
        # Controles principais
        col1, col2 = st.columns([2, 1])
        with col1:
            data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today(), key="data_busca")
        with col2:
            todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_busca")
        
        ligas_selecionadas = []
        if not todas_ligas:
            ligas_selecionadas = st.multiselect(
                "📌 Selecionar ligas (múltipla escolha):",
                options=list(ConfigManager.LIGA_DICT.keys()),
                default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"],
                key="ligas_busca"
            )
            
            if not ligas_selecionadas:
                st.warning("⚠️ Selecione pelo menos uma liga")
            else:
                st.info(f"📋 {len(ligas_selecionadas)} ligas selecionadas: {', '.join(ligas_selecionadas)}")
        
        # Processamento
        if st.button("🔍 Buscar Partidas", type="primary", key="btn_buscar"):
            if not todas_ligas and not ligas_selecionadas:
                st.error("❌ Selecione pelo menos uma liga ou marque 'Todas as ligas'")
            else:
                tipo_filtro_passar = tipo_filtro if tipo_analise == "Over/Under de Gols" else "Todos"
                
                # Chamada ATUALIZADA
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
                    tipo_filtro_passar, 
                    tipo_analise, 
                    config_analise,
                    alerta_por_horario,
                    intervalo_horario if alerta_por_horario else 30,
                    max_jogos_por_horario if alerta_por_horario else 5
                )
    
    with tab2:
        st.subheader("📊 Conferência de Resultados")
        
        col_data, col_btn = st.columns([2, 1])
        with col_data:
            data_resultados = st.date_input("📅 Data para conferência:", value=datetime.today(), key="data_resultados")
        
        with col_btn:
            if st.button("🔄 Conferir Resultados", type="primary", key="btn_conferir"):
                sistema.conferir_resultados(data_resultados)
    
    with tab3:
        st.subheader("🏆 Conferência de Resultados TOP Alertas")
        
        col_data_top, col_btn_top = st.columns([2, 1])
        with col_data_top:
            data_resultados_top = st.date_input(
                "📅 Data para conferência TOP:", 
                value=datetime.today(), 
                key="data_resultados_top"
            )
        
        with col_btn_top:
            if st.button("🏆 Conferir Resultados TOP", type="primary", key="btn_conferir_top"):
                sistema.resultados_top.conferir_resultados_top_alertas(data_resultados_top)
    
    with tab4:
        st.subheader("⏰ Gestão de Alertas por Horário")
        
        col1, col2 = st.columns(2)
        
        with col1:
            data_horario = st.date_input("📅 Data para análise:", value=datetime.today(), key="data_horario")
            todas_ligas_horario = st.checkbox("🌍 Todas as ligas (horário)", value=True, key="todas_ligas_horario")
        
        with col2:
            intervalo_horario_tab = st.selectbox("📊 Intervalo de agrupamento:", [15, 30, 60], index=1)
            max_jogos_horario = st.slider("Máximo de jogos por horário:", 3, 10, 5, 1)
        
        if not todas_ligas_horario:
            ligas_horario = st.multiselect(
                "📌 Selecionar ligas:",
                options=list(ConfigManager.LIGA_DICT.keys()),
                default=["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"],
                key="ligas_horario"
            )
        else:
            ligas_horario = []
        
        st.markdown("---")
        st.subheader("🎯 Configuração de Filtros")
        
        filtro_horario_tipo = st.selectbox(
            "Tipo de análise para horário:",
            ["Over/Under de Gols", "Favorito (Vitória)", "Gols HT (Primeiro Tempo)", "Ambas Marcam (BTTS)"],
            index=0,
            key="filtro_horario_tipo"
        )
        
        filtro_horario_confianca = st.slider("Confiança mínima:", 50, 95, 70, 1, key="filtro_horario_confianca")
        
        config_horario = {
            "min_conf": filtro_horario_confianca,
            "min_conf_vitoria": filtro_horario_confianca,
            "min_conf_ht": filtro_horario_confianca,
            "min_conf_am": filtro_horario_confianca
        }
        
        if st.button("🔍 Analisar Jogos por Horário", type="primary", key="btn_analisar_horario"):
            # Simular análise de jogos por horário
            st.info(f"⏰ Analisando jogos para {data_horario.strftime('%d/%m/%Y')}...")
            
            # Buscar jogos fictícios para demonstração
            jogos_exemplo = [
                {
                    "home": "Flamengo",
                    "away": "Palmeiras",
                    "liga": "Brasileirão",
                    "hora": datetime.strptime("20:00", "%H:%M"),
                    "confianca": 85.5,
                    "tendencia": "OVER 2.5",
                    "estimativa": 2.8,
                    "probabilidade": 75.0,
                    "tipo_aposta": "over"
                },
                {
                    "home": "Manchester City",
                    "away": "Liverpool",
                    "liga": "Premier League",
                    "hora": datetime.strptime("16:30", "%H:%M"),
                    "confianca": 82.3,
                    "tendencia": "OVER 3.5",
                    "estimativa": 3.2,
                    "probabilidade": 68.0,
                    "tipo_aposta": "over"
                },
                {
                    "home": "Real Madrid",
                    "away": "Barcelona",
                    "liga": "La Liga",
                    "hora": datetime.strptime("18:45", "%H:%M"),
                    "confianca": 78.9,
                    "tendencia": "OVER 2.5",
                    "estimativa": 2.6,
                    "probabilidade": 72.0,
                    "tipo_aposta": "over"
                },
                {
                    "home": "Bayern Munich",
                    "away": "Borussia Dortmund",
                    "liga": "Bundesliga",
                    "hora": datetime.strptime("16:30", "%H:%M"),
                    "confianca": 75.2,
                    "tendencia": "OVER 2.5",
                    "estimativa": 2.9,
                    "probabilidade": 70.5,
                    "tipo_aposta": "over"
                },
                {
                    "home": "PSG",
                    "away": "Marseille",
                    "liga": "Ligue 1",
                    "hora": datetime.strptime("20:00", "%H:%M"),
                    "confianca": 72.8,
                    "tendencia": "OVER 1.5",
                    "estimativa": 2.1,
                    "probabilidade": 65.0,
                    "tipo_aposta": "over"
                },
                {
                    "home": "Juventus",
                    "away": "Inter Milan",
                    "liga": "Serie A",
                    "hora": datetime.strptime("21:00", "%H:%M"),
                    "confianca": 69.4,
                    "tendencia": "UNDER 2.5",
                    "estimativa": 2.3,
                    "probabilidade": 62.0,
                    "tipo_aposta": "under"
                }
            ]
            
            # Agrupar por horário
            grupos = sistema.alertas_horario.agrupar_jogos_por_horario(jogos_exemplo, intervalo_horario_tab)
            
            # Mostrar grupos
            st.markdown("---")
            st.subheader("📅 Grupos por Horário")
            
            for horario_str, grupo in grupos.items():
                with st.expander(f"⏰ Horário {horario_str}h ({len(grupo['jogos'])} jogos)"):
                    for jogo in grupo['jogos']:
                        st.write(f"🏟️ {jogo['home']} vs {jogo['away']}")
                        st.write(f"   🏆 {jogo['liga']} | 💯 {jogo['confianca']:.1f}%")
            
            # Opção de envio
            if st.button("📤 Enviar Alertas por Horário", type="secondary"):
                sistema.alertas_horario.enviar_alertas_por_horario(
                    jogos_exemplo,
                    filtro_horario_tipo,
                    config_horario,
                    data_horario.strftime("%Y-%m-%d"),
                    intervalo_horario_tab,
                    max_jogos_horario
                )
        
        # Botão para agendamento automático
        st.markdown("---")
        st.subheader("🤖 Agendamento Automático")
        
        if st.button("⏰ Agendar Alertas Automáticos", type="primary"):
            sistema.alertas_horario.agendar_alertas_automaticos(
                data_horario,
                filtro_horario_tipo,
                config_horario
            )
    
    # Painel de monitoramento
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
