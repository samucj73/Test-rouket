import streamlit as st
from datetime import datetime, timedelta, timezone, date
from collections import deque, defaultdict
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import time
from threading import Lock
import threading
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging
import urllib.parse
import math
from dotenv import load_dotenv
import hashlib

# =============================
# CONFIGURAÇÃO DE VARIÁVEIS DE AMBIENTE
# =============================

# Carregar variáveis de ambiente
load_dotenv()

# =============================
# NOVAS CLASSES IMPLEMENTADAS
# =============================

class AlertaNovo:
    """Nova classe de alerta com métricas aprimoradas"""
    def __init__(self, jogo, mercado, odd, data=None):
        self.jogo = jogo  # Objeto Jogo ou string
        self.mercado = mercado
        self.odd = float(odd)
        self.data = data or datetime.now()

        # Métricas do modelo
        self.probabilidade = 0.0   # 0–1
        self.confianca = 0.0       # 0–100

        # Qualidade
        self.ev = 0.0
        self.score = 0.0
        self.qualidade = "DESCARTAR"
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            "jogo": self.jogo.to_dict() if hasattr(self.jogo, 'to_dict') else str(self.jogo),
            "mercado": self.mercado,
            "odd": self.odd,
            "data": self.data.isoformat(),
            "probabilidade": self.probabilidade,
            "confianca": self.confianca,
            "ev": self.ev,
            "score": self.score,
            "qualidade": self.qualidade
        }


class QualidadeDoAlertaV2:
    """Avaliação de qualidade de alerta v2 (Odds + EV)"""
    
    @staticmethod
    def avaliar(alerta: AlertaNovo) -> AlertaNovo:
        """Avalia a qualidade do alerta com base em múltiplas métricas"""
        if alerta.odd <= 1.01:
            alerta.qualidade = "DESCARTAR"
            return alerta

        # Calcular EV (Expected Value)
        alerta.ev = round((alerta.probabilidade * alerta.odd) - 1, 3)

        # Normalizar valores (0-1)
        prob_n = alerta.probabilidade
        conf_n = alerta.confianca / 100
        ev_n = max(0.0, min(alerta.ev / 0.25, 1.0))

        # Calcular score composto
        score = (
            prob_n * 0.40 +  # Peso 40% para probabilidade
            conf_n * 0.30 +  # Peso 30% para confiança
            ev_n * 0.30      # Peso 30% para EV
        )

        # Aplicar penalizações
        penalizacao = 0.0
        if alerta.odd < 1.45:  # Odds muito baixas
            penalizacao += 0.05
        if alerta.odd > 4.5:   # Odds muito altas
            penalizacao += 0.10
        if alerta.confianca < 55:  # Confiança muito baixa
            penalizacao += 0.10

        # Score final com penalizações
        score_final = max(0.0, score - penalizacao)
        alerta.score = round(score_final * 100, 1)

        # Classificar qualidade
        if score_final >= 0.75:
            alerta.qualidade = "A"  # Excelente
        elif score_final >= 0.62:
            alerta.qualidade = "B"  # Bom
        elif score_final >= 0.50:
            alerta.qualidade = "C"  # Razoável
        else:
            alerta.qualidade = "DESCARTAR"

        return alerta


class RankingTop3DoDia:
    """Gerencia ranking dos top 3 alertas do dia"""
    
    def __init__(self):
        self.alertas_por_dia = defaultdict(list)
        self.data_path = "ranking_top3.json"
    
    def adicionar_alerta(self, alerta: AlertaNovo):
        """Adiciona alerta ao ranking do dia"""
        if alerta.qualidade != "A":
            return
        if alerta.ev <= 0:
            return

        dia = alerta.data.date()
        self.alertas_por_dia[dia].append(alerta)
        
        # Salvar automaticamente
        self.salvar_ranking()
    
    def obter_alerta(self, jogo_id: str, data: date = None):
        """Obtém alerta específico"""
        dia = data or date.today()
        for alerta in self.alertas_por_dia.get(dia, []):
            if hasattr(alerta.jogo, 'id') and alerta.jogo.id == jogo_id:
                return alerta
        return None
    
    def gerar_top3(self, dia: date = None):
        """Gera os top 3 alertas do dia"""
        dia = dia or date.today()
        alertas = self.alertas_por_dia.get(dia, [])

        return sorted(
            alertas,
            key=lambda a: (a.score, a.ev),
            reverse=True
        )[:3]
    
    def carregar_ranking(self):
        """Carrega ranking do arquivo"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                
                for dia_str, alertas_dados in dados.items():
                    dia = datetime.fromisoformat(dia_str).date()
                    self.alertas_por_dia[dia] = []
                    
                    for alerta_data in alertas_dados:
                        # Criar alerta básico
                        alerta = AlertaNovo(
                            jogo=alerta_data.get("jogo", {}),
                            mercado=alerta_data.get("mercado", ""),
                            odd=alerta_data.get("odd", 0.0),
                            data=datetime.fromisoformat(alerta_data.get("data", ""))
                        )
                        alerta.probabilidade = alerta_data.get("probabilidade", 0.0)
                        alerta.confianca = alerta_data.get("confianca", 0.0)
                        alerta.ev = alerta_data.get("ev", 0.0)
                        alerta.score = alerta_data.get("score", 0.0)
                        alerta.qualidade = alerta_data.get("qualidade", "DESCARTAR")
                        
                        self.alertas_por_dia[dia].append(alerta)
                
                logging.info(f"✅ Ranking carregado com {sum(len(v) for v in self.alertas_por_dia.values())} alertas")
        except Exception as e:
            logging.error(f"❌ Erro ao carregar ranking: {e}")
    
    def salvar_ranking(self):
        """Salva ranking no arquivo"""
        try:
            dados = {}
            for dia, alertas in self.alertas_por_dia.items():
                dia_str = dia.isoformat()
                dados[dia_str] = [alerta.to_dict() for alerta in alertas]
            
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            
            logging.info(f"💾 Ranking salvo com {len(dados)} dias de alertas")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar ranking: {e}")


class NotificadorTelegram:
    """Notificador via Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id
    
    def enviar(self, mensagem: str):
        """Envia mensagem para o Telegram"""
        payload = {
            "chat_id": self.chat_id,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"[ERRO TELEGRAM] {e}")
            return False


class GerenciadorNotificacoes:
    """Gerencia notificações de alertas"""
    
    def __init__(self, telegram: NotificadorTelegram, somente_top3=False):
        self.telegram = telegram
        self.somente_top3 = somente_top3
        self.notificacoes_enviadas = set()  # Para evitar duplicatas
    
    def notificar_alerta(self, alerta: AlertaNovo, is_top3=False):
        """Envia notificação de alerta"""
        if alerta.qualidade != "A":
            return False
        if alerta.ev <= 0:
            return False
        if self.somente_top3 and not is_top3:
            return False
        
        # Verificar se já foi notificado (evitar duplicatas)
        alerta_key = f"{alerta.jogo.id if hasattr(alerta.jogo, 'id') else str(alerta.jogo)}_{alerta.data.timestamp()}"
        if alerta_key in self.notificacoes_enviadas:
            return False
        
        mensagem = self._formatar(alerta, is_top3)
        sucesso = self.telegram.enviar(mensagem)
        
        if sucesso:
            self.notificacoes_enviadas.add(alerta_key)
        
        return sucesso
    
    def notificar_top3(self, ranking: RankingTop3DoDia):
        """Notifica os top 3 alertas do dia"""
        top3 = ranking.gerar_top3()
        for i, alerta in enumerate(top3):
            self.notificar_alerta(alerta, is_top3=True)
        
        return len(top3)
    
    def _formatar(self, alerta: AlertaNovo, is_top3: bool):
        """Formata mensagem para Telegram"""
        selo = "🏆 <b>TOP 3 DO DIA</b>\n\n" if is_top3 else ""
        
        # Extrair informações do jogo
        if hasattr(alerta.jogo, 'home_team') and hasattr(alerta.jogo, 'away_team'):
            jogo_text = f"{alerta.jogo.home_team} vs {alerta.jogo.away_team}"
            liga_text = f"🏆 {alerta.jogo.competition}" if hasattr(alerta.jogo, 'competition') else ""
            hora_text = alerta.jogo.get_data_hora_brasilia()[1] if hasattr(alerta.jogo, 'get_data_hora_brasilia') else ""
        else:
            jogo_text = str(alerta.jogo)
            liga_text = ""
            hora_text = ""
        
        # Formatador de qualidade com emoji
        qualidade_emoji = {
            "A": "🟢",
            "B": "🟡", 
            "C": "🟠",
            "DESCARTAR": "🔴"
        }.get(alerta.qualidade, "⚪")
        
        return (
            f"{selo}"
            f"⚽ <b>{jogo_text}</b>\n"
            f"{liga_text}\n"
            f"🕒 {hora_text}\n\n"
            f"📌 <b>{alerta.mercado}</b>\n"
            f"💰 Odd: <b>{alerta.odd:.2f}</b>\n\n"
            f"📊 Probabilidade: <b>{int(alerta.probabilidade*100)}%</b>\n"
            f"🎯 Confiança: <b>{alerta.confianca:.1f}%</b>\n"
            f"📈 EV: <b>{alerta.ev:.3f}</b>\n"
            f"⭐ Score: <b>{alerta.score:.1f}</b>\n"
            f"{qualidade_emoji} Qualidade: <b>{alerta.qualidade}</b>\n\n"
            f"🔥 <i>Elite Master System</i>"
        )


class MotorDeAlertas:
    """Motor principal para processar alertas com novo sistema"""
    
    def __init__(self, ranking: RankingTop3DoDia, notificacoes: GerenciadorNotificacoes):
        self.ranking = ranking
        self.notificacoes = notificacoes
        self.alertas_processados = 0
        self.alertas_qualidade_A = 0
    
    def processar_alerta(self, jogo, mercado, odd, probabilidade, confianca):
        """Processa um alerta completo"""
        # Criar alerta
        alerta = AlertaNovo(jogo, mercado, odd)
        alerta.probabilidade = probabilidade
        alerta.confianca = confianca
        
        # Avaliar qualidade
        alerta = QualidadeDoAlertaV2.avaliar(alerta)
        
        # Adicionar ao ranking se for qualidade A
        self.ranking.adicionar_alerta(alerta)
        
        # Notificar se for qualidade A
        if alerta.qualidade == "A":
            self.alertas_qualidade_A += 1
            self.notificacoes.notificar_alerta(alerta, is_top3=False)
        
        self.alertas_processados += 1
        
        return alerta
    
    def processar_alerta_from_odds(self, jogo, odds_data, analise_data):
        """Processa alerta a partir de dados de odds e análise"""
        alertas_gerados = []
        
        # Processar diferentes mercados
        mercados = [
            ("Casa", "home_best", analise_data.get('vitoria', {}).get('home_win', 0) / 100),
            ("Fora", "away_best", analise_data.get('vitoria', {}).get('away_win', 0) / 100),
            ("Empate", "draw_best", analise_data.get('vitoria', {}).get('draw', 0) / 100),
            ("Over 2.5", "over_25_best", analise_data.get('over_25_prob', 0) / 100),
            ("Under 2.5", "under_25_best", analise_data.get('under_25_prob', 0) / 100)
        ]
        
        for mercado_nome, mercado_key, probabilidade in mercados:
            if mercado_key in odds_data.get("melhores_odds", {}):
                odd_data = odds_data["melhores_odds"][mercado_key]
                odd = odd_data.get("odds", 0)
                
                if odd > 1.01 and probabilidade > 0:
                    # Usar confiança da análise principal
                    confianca = analise_data.get('confianca', 0)
                    
                    alerta = self.processar_alerta(
                        jogo=jogo,
                        mercado=mercado_nome,
                        odd=odd,
                        probabilidade=probabilidade,
                        confianca=confianca
                    )
                    
                    if alerta:
                        alertas_gerados.append(alerta)
        
        return alertas_gerados
    
    def enviar_top3_diario(self):
        """Envia notificação dos top 3 alertas do dia"""
        return self.notificacoes.notificar_top3(self.ranking)
    
    def get_stats(self):
        """Retorna estatísticas do motor"""
        return {
            "alertas_processados": self.alertas_processados,
            "alertas_qualidade_A": self.alertas_qualidade_A,
            "taxa_qualidade_A": f"{(self.alertas_qualidade_A / max(self.alertas_processados, 1)) * 100:.1f}%",
            "top3_hoje": len(self.ranking.gerar_top3()),
            "alertas_por_dia": {str(k): len(v) for k, v in self.ranking.alertas_por_dia.items()}
        }


# =============================
# CLASSES PRINCIPAIS - CORE SYSTEM (ATUALIZADAS)
# =============================

class ConfigManager:
    """Gerencia configurações e constantes do sistema"""
    
    # Carregar do .env ou usar valores padrão
    API_KEY = os.getenv("FOOTBALL_API_KEY", "")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "")
    ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
    
    HEADERS = {"X-Auth-Token": API_KEY}
    BASE_URL_FD = "https://api.football-data.org/v4"
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    BASE_URL_ODDS = os.getenv("ODDS_API_URL", "https://api.the-odds-api.com/v4")
    
    # Constantes
    ALERTAS_PATH = "alertas.json"
    ALERTAS_FAVORITOS_PATH = "alertas_favoritos.json"
    ALERTAS_GOLS_HT_PATH = "alertas_gols_ht.json"
    RESULTADOS_PATH = "resultados.json"
    RESULTADOS_FAVORITOS_PATH = "resultados_favoritos.json"
    RESULTADOS_GOLS_HT_PATH = "resultados_gols_ht.json"
    CACHE_JOGOS = "cache_jogos.json"
    CACHE_CLASSIFICACAO = "cache_classificacao.json"
    CACHE_TIMEOUT = 3600
    HISTORICO_PATH = "historico_conferencias.json"
    ALERTAS_TOP_PATH = "alertas_top.json"
    
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
        "match_details": {"ttl": 1800, "max_size": 200},
        "odds": {"ttl": 300, "max_size": 100}
    }
    
    @classmethod
    def get_liga_id(cls, liga_nome):
        """Obtém o ID da liga a partir do nome"""
        return cls.LIGA_DICT.get(liga_nome)
    
    @classmethod
    def validar_configuracao(cls):
        """Valida se todas as configurações necessárias estão presentes"""
        faltantes = []
        
        if not cls.API_KEY or cls.API_KEY == "":
            faltantes.append("FOOTBALL_API_KEY")
        
        if not cls.TELEGRAM_TOKEN or cls.TELEGRAM_TOKEN == "":
            faltantes.append("TELEGRAM_TOKEN")
        
        if not cls.TELEGRAM_CHAT_ID or cls.TELEGRAM_CHAT_ID == "":
            faltantes.append("TELEGRAM_CHAT_ID")
        
        if not cls.ODDS_API_KEY or cls.ODDS_API_KEY == "":
            faltantes.append("ODDS_API_KEY")
        
        return faltantes
    
    @classmethod
    def testar_apis(cls):
        """Testa conexão com as APIs"""
        resultados = {
            "Football Data API": False,
            "Telegram API": False,
            "Odds API": False
        }
        
        # Testar Football Data API
        try:
            response = requests.get(f"{cls.BASE_URL_FD}/areas", headers=cls.HEADERS, timeout=10)
            resultados["Football Data API"] = response.status_code == 200
        except:
            pass
        
        # Testar Telegram API
        try:
            response = requests.get(f"{cls.BASE_URL_TG}/getMe", timeout=10)
            resultados["Telegram API"] = response.status_code == 200
        except:
            pass
        
        # Testar Odds API
        try:
            url = f"{cls.BASE_URL_ODDS}/sports/?apiKey={cls.ODDS_API_KEY}"
            response = requests.get(url, timeout=10)
            resultados["Odds API"] = response.status_code == 200
        except:
            pass
        
        return resultados


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


class ExponentialBackoffRetry:
    """Implementa retry com backoff exponencial"""
    def __init__(self, max_retries=3, base_delay=1, max_delay=60):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def execute(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                
                delay = min(
                    self.base_delay * (2 ** attempt),
                    self.max_delay
                )
                logging.info(f"⏳ Tentativa {attempt + 1} falhou. Esperando {delay}s antes de retry...")
                time.sleep(delay)


class SmartCache:
    """Cache inteligente com TTL e tamanho máximo"""
    def __init__(self, cache_type: str):
        self.cache = {}
        self.timestamps = {}
        self.ttl_values = {}
        self.config = ConfigManager.CACHE_CONFIG.get(cache_type, {"ttl": 3600, "max_size": 100})
        self.lock = threading.Lock()
        
    def get(self, key: str):
        """Obtém valor do cache se ainda for válido"""
        with self.lock:
            if key not in self.cache:
                return None
                
            timestamp = self.timestamps.get(key, 0)
            agora = time.time()
            
            # Usar TTL específico ou padrão
            ttl = self.ttl_values.get(key, self.config["ttl"])
            
            if agora - timestamp > ttl:
                del self.cache[key]
                del self.timestamps[key]
                if key in self.ttl_values:
                    del self.ttl_values[key]
                return None
                
            return self.cache[key]
    
    def set(self, key: str, value, ttl: int = None):
        """Armazena valor no cache com TTL opcional"""
        with self.lock:
            if len(self.cache) >= self.config["max_size"]:
                oldest_key = min(self.timestamps.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
                if oldest_key in self.ttl_values:
                    del self.ttl_values[oldest_key]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
            self.ttl_values[key] = ttl or self.config["ttl"]
    
    def clear(self):
        """Limpa todo o cache"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.ttl_values.clear()
    
    def get_stats(self):
        """Retorna estatísticas do cache"""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.config["max_size"],
                "usage_percentage": (len(self.cache) / self.config["max_size"]) * 100
            }


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
                "disco_mb": round(cache_dir_size / (1024*1024), 2) if cache_dir_size > 0 else 0,
                "hit_rate": f"{(len(self.cache) / max(self.max_size, 1)) * 100:.1f}%"
            }


# =============================
# CLASSE ATUALIZADA: API DE ODDS (COM CORREÇÕES)
# =============================

class APIOddsClient:
    """Cliente especializado para buscar odds de diferentes provedores - CORRIGIDO"""
    
    def __init__(self, rate_limiter: RateLimiter, api_monitor: APIMonitor):
        self.rate_limiter = rate_limiter
        self.api_monitor = api_monitor
        self.config = ConfigManager()
        self.odds_cache = SmartCache("odds")
        self.retry_handler = ExponentialBackoffRetry(max_retries=3)
        
        # Mapeamento CORRIGIDO de ligas para sport keys da Odds API
        self.liga_map_corrigido = {
            "PL": "soccer_epl",                          # Premier League
            "BL1": "soccer_germany_bundesliga",          # Bundesliga
            "SA": "soccer_italy_serie_a",                # Serie A
            "PD": "soccer_spain_la_liga",                # La Liga
            "FL1": "soccer_france_ligue_one",            # Ligue 1
            "BSA": "soccer_brazil_campeonato",           # Brasileirão
            "CL": "soccer_uefa_champs_league",           # Champions League (CORRIGIDO)
            "ELC": "soccer_efl_champ",                   # Championship (CORRIGIDO: soccer_efl_champ)
            "PPL": "soccer_portugal_primeira_liga",      # Primeira Liga
            "DED": "soccer_netherlands_eredivisie",      # Eredivisie
            "WC": "soccer_fifa_world_cup",               # FIFA World Cup
            "EC": "soccer_euro_championship"             # European Championship
        }
    
    def obter_odds_com_retry(self, url: str, timeout: int = 15) -> dict | None:
        """Obtém dados da API de odds com rate limiting e retry"""
        def _make_request():
            self.rate_limiter.wait_if_needed()
            
            logging.info(f"💰 Request odds: {url}")
            
            response = requests.get(url, timeout=timeout)
            
            # Verificar headers da Odds API para quota
            remaining = response.headers.get('x-requests-remaining', 'unknown')
            used = response.headers.get('x-requests-used', 'unknown')
            logging.info(f"📊 Quota Odds API: Restantes={remaining}, Usadas={used}")
            
            if response.status_code == 422:
                # Erro específico - endpoint não suportado
                logging.error(f"❌ Endpoint não suportado: {url}")
                raise Exception("Endpoint não suportado pela Odds API")
                
            if response.status_code == 404:
                # Erro 404 - sport key incorreto
                logging.error(f"❌ Sport key não encontrado (404): {url}")
                raise Exception("Sport key incorreto")
                
            if response.status_code == 429:
                self.api_monitor.log_request(False, True)
                retry_after = int(response.headers.get('Retry-After', 60))
                logging.warning(f"⏳ Rate limit da API de odds. Esperando {retry_after} segundos...")
                time.sleep(retry_after)
                raise Exception("Rate limit atingido")
                
            response.raise_for_status()
            
            self.api_monitor.log_request(True)
            
            return response.json()
        
        try:
            return self.retry_handler.execute(_make_request)
        except Exception as e:
            logging.error(f"❌ Falha após retries para {url}: {e}")
            return None
    
    def obter_odds_ao_vivo(self, liga_id: str = None, mercado: str = "h2h") -> list:
        """Obtém odds ao vivo para jogos específicos - CORRIGIDO"""
        cache_key = f"odds_live_{liga_id}_{mercado}"
        cached = self.odds_cache.get(cache_key)
        if cached:
            logging.info(f"📊 Odds ao vivo obtidas do cache: {cache_key}")
            return cached
        
        try:
            if liga_id and liga_id in self.liga_map_corrigido:
                sport_key = self.liga_map_corrigido[liga_id]
            else:
                # Usar 'upcoming' para todos os jogos
                sport_key = "upcoming"
            
            # Construir URL corretamente
            url = f"{self.config.BASE_URL_ODDS}/sports/{sport_key}/odds"
            
            # Parâmetros OBRIGATÓRIOS da Odds API
            params = {
                'apiKey': self.config.ODDS_API_KEY,
                'regions': 'us,eu',  # REGIÕES OBRIGATÓRIAS
                'markets': mercado,
                'oddsFormat': 'decimal',
                'dateFormat': 'iso'
            }
            
            # Adicionar filtros opcionais se for uma liga específica
            if liga_id and liga_id != "upcoming":
                hoje = datetime.now().strftime("%Y-%m-%d")
                params['commenceTimeFrom'] = f"{hoje}T00:00:00Z"
                params['commenceTimeTo'] = f"{hoje}T23:59:59Z"
            
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            logging.info(f"🔗 Chamando Odds API: {full_url}")
            
            data = self.obter_odds_com_retry(full_url)
            
            if data:
                self.odds_cache.set(cache_key, data, ttl=300)  # Cache de 5 minutos para odds
            
            return data or []
            
        except Exception as e:
            logging.error(f"❌ Erro crítico ao buscar odds: {e}")
            return []
    
    def obter_odds_por_data_liga(self, data: str, liga_id: str = None, mercado: str = "h2h") -> list:
        """Obtém odds para uma data específica - CORRIGIDO"""
        cache_key = f"odds_{data}_{liga_id}_{mercado}"
        cached = self.odds_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Usar mapeamento corrigido ou fallback
            if liga_id and liga_id in self.liga_map_corrigido:
                sport_key = self.liga_map_corrigido[liga_id]
            else:
                sport_key = "upcoming"
            
            url = f"{self.config.BASE_URL_ODDS}/sports/{sport_key}/odds"
            
            params = {
                'apiKey': self.config.ODDS_API_KEY,
                'regions': 'us,eu,uk',
                'markets': mercado,
                'oddsFormat': 'decimal',
                'dateFormat': 'iso'
            }
            
            # Adicionar filtros de data
            if data:
                params['commenceTimeFrom'] = f"{data}T00:00:00Z"
                params['commenceTimeTo'] = f"{data}T23:59:59Z"
            
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            logging.info(f"📅 Buscando odds para {data} (sport_key: {sport_key}): {full_url}")
            
            data_response = self.obter_odds_com_retry(full_url)
            
            if data_response:
                self.odds_cache.set(cache_key, data_response, ttl=600)
            
            return data_response or []
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar odds por data: {e}")
            return []
    
    def obter_odds_por_jogo(self, fixture_id: str, data_jogo: str = None, home_team: str = "", away_team: str = "") -> dict:
        """Obtém odds específicas para um jogo - CORREÇÃO COMPLETA"""
        # A Odds API NÃO suporta buscar por ID de evento específico
        # Em vez disso, buscamos todas as odds da data e filtramos pelo nome dos times
        
        cache_key = f"odds_match_{fixture_id}_{home_team}_{away_team}"
        cached = self.odds_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Se não temos data, usar hoje
            if not data_jogo:
                data_jogo = datetime.now().strftime("%Y-%m-%d")
            
            # Buscar todas as odds da data (sem filtro de liga para maior cobertura)
            todas_odds = self.obter_odds_por_data_liga(data_jogo, None, "h2h,totals,spreads")
            
            if not todas_odds:
                return {}
            
            # Procurar o jogo específico pelos nomes dos times
            for jogo in todas_odds:
                jogo_home = jogo.get('home_team', '').lower()
                jogo_away = jogo.get('away_team', '').lower()
                
                home_lower = home_team.lower()
                away_lower = away_team.lower()
                
                # Verificar correspondência aproximada
                match_found = False
                
                # Verificar correspondência exata ou parcial
                if (home_lower in jogo_home or jogo_home in home_lower) and \
                   (away_lower in jogo_away or jogo_away in away_lower):
                    match_found = True
                
                # Verificar se os times estão invertidos
                elif (home_lower in jogo_away or jogo_away in home_lower) and \
                     (away_lower in jogo_home or jogo_home in away_lower):
                    match_found = True
                
                if match_found and jogo.get('bookmakers'):
                    logging.info(f"✅ Jogo encontrado na Odds API: {jogo_home} vs {jogo_away}")
                    self.odds_cache.set(cache_key, jogo, ttl=300)
                    return jogo
            
            logging.warning(f"⚠️ Jogo não encontrado na Odds API: {home_team} vs {away_team}")
            return {}
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar odds do jogo {fixture_id}: {e}")
            return {}
    
    def buscar_odds_por_event_ids(self, event_ids: list, mercado: str = "h2h") -> list:
        """Busca odds por múltiplos IDs de evento"""
        if not event_ids:
            return []
        
        cache_key = f"odds_events_{hash(frozenset(event_ids))}_{mercado}"
        cached = self.odds_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Usar endpoint upcoming com filtro de event_ids
            url = f"{self.config.BASE_URL_ODDS}/sports/upcoming/odds"
            
            params = {
                'apiKey': self.config.ODDS_API_KEY,
                'regions': 'us,eu,uk',
                'markets': mercado,
                'oddsFormat': 'decimal',
                'dateFormat': 'iso',
                'eventIds': ','.join(event_ids[:50])  # Limitar a 50 eventos
            }
            
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            logging.info(f"🔗 Buscando odds para {len(event_ids)} eventos")
            
            data_response = self.obter_odds_com_retry(full_url)
            
            if data_response:
                self.odds_cache.set(cache_key, data_response, ttl=600)
            
            return data_response or []
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar odds por event_ids: {e}")
            return []
    
    def obter_esportes_disponiveis(self) -> list:
        """Retorna lista de esportes disponíveis na Odds API"""
        try:
            url = f"{self.config.BASE_URL_ODDS}/sports/?apiKey={self.config.ODDS_API_KEY}"
            data = self.obter_odds_com_retry(url)
            
            if isinstance(data, list):
                # Filtrar apenas esportes de futebol/soccer
                esportes_futebol = [s for s in data if s.get('group') == 'Soccer']
                return esportes_futebol
            return []
            
        except Exception as e:
            logging.error(f"❌ Erro ao buscar esportes: {e}")
            return []
    
    def testar_conexao(self) -> bool:
        """Testa a conexão com a Odds API"""
        try:
            # Usar endpoint de esportes que não consome quota
            url = f"{self.config.BASE_URL_ODDS}/sports/?apiKey={self.config.ODDS_API_KEY}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return isinstance(data, list) and len(data) > 0
            elif response.status_code == 401:
                logging.error("❌ API Key inválida ou expirada")
                return False
            else:
                logging.error(f"❌ Erro na conexão: {response.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Erro de conexão: {e}")
            return False
    
    def analisar_valor_aposta(self, odds: float, probabilidade: float) -> dict:
        """Analisa se uma odd tem valor baseado na probabilidade estimada"""
        if odds <= 0 or probabilidade <= 0:
            return {"valor": False, "edge": 0, "recomendacao": "EVITAR"}
        
        # Calcular probabilidade implícita da odd
        probabilidade_implicita = 1 / odds
        
        # Calcular edge (vantagem)
        edge = (probabilidade / 100) - probabilidade_implicita
        
        # Calcular Kelly Criterion (simplificado)
        kelly = ((probabilidade / 100) * (odds - 1) - (1 - (probabilidade / 100))) / (odds - 1)
        kelly = max(0, min(kelly, 0.5))  # Limitar entre 0% e 50%
        
        # Determinar recomendação
        if edge > 0.05:  # Edge maior que 5%
            valor = True
            recomendacao = "ALTO VALOR"
            cor = "🟢"
        elif edge > 0.02:  # Edge entre 2% e 5%
            valor = True
            recomendacao = "VALOR MODERADO"
            cor = "🟡"
        elif edge > 0:
            valor = True
            recomendacao = "PEQUENO VALOR"
            cor = "🟠"
        else:
            valor = False
            recomendacao = "SEM VALOR"
            cor = "🔴"
        
        return {
            "valor": valor,
            "edge": round(edge * 100, 2),  # Em porcentagem
            "kelly": round(kelly * 100, 2),  # Em porcentagem
            "probabilidade_implicita": round(probabilidade_implicita * 100, 2),
            "recomendacao": recomendacao,
            "cor": cor,
            "odd": odds,
            "probabilidade_nossa": probabilidade
        }


# =============================
# CLASSE ATUALIZADA: ODDS MANAGER (COM CORREÇÕES)
# =============================

class OddsManager:
    """Gerencia análise e apresentação de odds"""
    
    def __init__(self, api_client, odds_client: APIOddsClient):
        self.api_client = api_client
        self.odds_client = odds_client
    
    def buscar_odds_com_analise(self, data_selecionada, ligas_selecionadas, todas_ligas):
        """Busca odds com análise de valor - CORRIGIDO"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        if todas_ligas:
            ligas_busca = list(ConfigManager.LIGA_DICT.values())
        else:
            ligas_busca = [ConfigManager.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
        
        resultados = []
        progress_bar = st.progress(0)
        total_ligas = len(ligas_busca)
        
        for i, liga_id in enumerate(ligas_busca):
            # Buscar jogos primeiro da API de futebol
            if liga_id == "BSA":
                jogos_data = self.api_client.obter_jogos_brasileirao(liga_id, hoje)
            else:
                jogos_data = self.api_client.obter_jogos(liga_id, hoje)
            
            if not jogos_data:
                continue
            
            # Buscar classificação para análise
            classificacao = self.api_client.obter_classificacao(liga_id)
            analisador = AnalisadorTendencia(classificacao)
            
            # Coletar informações dos jogos para buscar odds
            jogos_para_buscar = []
            
            for match_data in jogos_data:
                if not self.api_client.validar_dados_jogo(match_data):
                    continue
                
                jogo = Jogo(match_data)
                
                # Obter análise do jogo
                analise = analisador.calcular_tendencia_completa(jogo.home_team, jogo.away_team)
                jogo.set_analise(analise)
                
                # Tentar buscar odds específicas para este jogo
                odds_data = self.odds_client.obter_odds_por_jogo(
                    fixture_id=str(jogo.id),
                    data_jogo=hoje,
                    home_team=jogo.home_team,
                    away_team=jogo.away_team
                )
                
                if odds_data:
                    # Processar odds
                    odds_processadas = self.processar_odds_jogo(odds_data, analise, jogo)
                    
                    if odds_processadas:
                        resultados.append({
                            "jogo": jogo,
                            "analise": analise,
                            "odds": odds_processadas,
                            "liga": jogo.competition
                        })
            
            progress_bar.progress((i + 1) / total_ligas)
        
        return resultados
    
    def buscar_odds_direto_api(self, data_selecionada, ligas_selecionadas, todas_ligas):
        """Busca odds diretamente da API sem depender da API de futebol"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        
        resultados = []
        
        if todas_ligas:
            ligas_busca = list(ConfigManager.LIGA_DICT.values())
        else:
            ligas_busca = [ConfigManager.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
        
        progress_bar = st.progress(0)
        total_ligas = len(ligas_busca)
        
        for i, liga_id in enumerate(ligas_busca):
            # Buscar odds diretamente da Odds API usando o mapeamento corrigido
            odds_data = self.odds_client.obter_odds_por_data_liga(
                hoje, 
                liga_id, 
                "h2h,totals"
            )
            
            if not odds_data:
                continue
            
            # Para cada jogo de odds, tentar obter análise
            for jogo_data in odds_data:
                try:
                    home_team = jogo_data.get('home_team', '')
                    away_team = jogo_data.get('away_team', '')
                    sport_key = jogo_data.get('sport_key', '')
                    
                    if not home_team or not away_team:
                        continue
                    
                    # Criar objeto Jogo básico
                    jogo = Jogo({
                        "id": jogo_data.get('id', ''),
                        "homeTeam": {"name": home_team},
                        "awayTeam": {"name": away_team},
                        "utcDate": jogo_data.get('commence_time', ''),
                        "competition": {"name": self._formatar_nome_liga(sport_key)},
                        "status": "SCHEDULED"
                    })
                    
                    # Tentar obter análise se possível
                    analise = {}
                    liga_nome = self._obter_liga_por_sport_key(sport_key)
                    
                    if liga_nome and liga_nome in ConfigManager.LIGA_DICT:
                        liga_id_analise = ConfigManager.LIGA_DICT[liga_nome]
                        classificacao = self.api_client.obter_classificacao(liga_id_analise)
                        
                        if classificacao:
                            analisador = AnalisadorTendencia(classificacao)
                            analise = analisador.calcular_tendencia_completa(home_team, away_team)
                            jogo.set_analise(analise)
                    
                    # Processar odds
                    odds_processadas = self.processar_odds_jogo(jogo_data, analise, jogo)
                    
                    if odds_processadas:
                        resultados.append({
                            "jogo": jogo,
                            "analise": analise,
                            "odds": odds_processadas,
                            "liga": jogo.competition
                        })
                    
                except Exception as e:
                    logging.error(f"❌ Erro ao processar jogo de odds: {e}")
                    continue
            
            progress_bar.progress((i + 1) / total_ligas)
        
        return resultados
    
    def _formatar_nome_liga(self, sport_key: str) -> str:
        """Formata o sport key para nome de liga amigável"""
        if not sport_key:
            return "Desconhecido"
        
        # Remover prefixo "soccer_"
        nome = sport_key.replace('soccer_', '')
        # Substituir underscores por espaços
        nome = nome.replace('_', ' ')
        # Capitalizar
        nome = ' '.join([word.capitalize() for word in nome.split()])
        
        # Mapeamentos especiais baseados nos sport_keys reais
        mapeamentos = {
            'Epl': 'Premier League',
            'La Liga': 'La Liga',
            'Germany Bundesliga': 'Bundesliga',
            'Italy Serie A': 'Serie A',
            'France Ligue One': 'Ligue 1',
            'Brazil Campeonato': 'Brasileirão',
            'Uefa Champs League': 'Champions League',
            'Efl Champ': 'Championship',  # CORRIGIDO
            'Portugal Primeira Liga': 'Primeira Liga',
            'Netherlands Eredivisie': 'Eredivisie',
            'Fifa World Cup': 'FIFA World Cup',
            'Euro Championship': 'European Championship'
        }
        
        return mapeamentos.get(nome, nome)
    
    def _obter_liga_por_sport_key(self, sport_key: str) -> str | None:
        """Obtém o nome da liga a partir do sport key - CORRIGIDO"""
        mapeamento_inverso = {
            'soccer_epl': 'Premier League (Inglaterra)',
            'soccer_spain_la_liga': 'Primera Division',
            'soccer_germany_bundesliga': 'Bundesliga',
            'soccer_italy_serie_a': 'Serie A (Itália)',
            'soccer_france_ligue_one': 'Ligue 1',
            'soccer_brazil_campeonato': 'Campeonato Brasileiro Série A',
            'soccer_uefa_champs_league': 'UEFA Champions League',  # CORRIGIDO
            'soccer_efl_champ': 'Championship (Inglaterra)',  # CORRIGIDO
            'soccer_portugal_primeira_liga': 'Primeira Liga (Portugal)',
            'soccer_netherlands_eredivisie': 'Eredivisie',
            'soccer_fifa_world_cup': 'FIFA World Cup',
            'soccer_euro_championship': 'European Championship'
        }
        
        return mapeamento_inverso.get(sport_key)
    
    def processar_odds_jogo(self, odds_data: dict, analise: dict, jogo) -> dict:
        """Processa e analisa odds de um jogo"""
        if not odds_data or "bookmakers" not in odds_data:
            return None
        
        bookmakers = odds_data.get("bookmakers", [])
        resultados = {
            "h2h": [],  # Head to Head (1x2)
            "totals": [],  # Over/Under
            "home_odds": [],
            "draw_odds": [],
            "away_odds": [],
            "over_25_odds": [],
            "under_25_odds": [],
            "btts_yes": [],
            "btts_no": [],
            "melhores_odds": {}
        }
        
        for bookmaker in bookmakers:
            bm_name = bookmaker.get("title", "Desconhecido")
            markets = bookmaker.get("markets", [])
            
            for market in markets:
                market_key = market.get("key", "")
                outcomes = market.get("outcomes", [])
                
                if market_key == "h2h":
                    for outcome in outcomes:
                        name = outcome.get("name", "")
                        odds = outcome.get("price", 0)
                        
                        if name == jogo.home_team or name == "Home":
                            resultados["home_odds"].append({"bookmaker": bm_name, "odds": odds})
                        elif name == "Draw":
                            resultados["draw_odds"].append({"bookmaker": bm_name, "odds": odds})
                        elif name == jogo.away_team or name == "Away":
                            resultados["away_odds"].append({"bookmaker": bm_name, "odds": odds})
                
                elif market_key == "totals":
                    for outcome in outcomes:
                        name = outcome.get("name", "")
                        point = outcome.get("point", 0)
                        odds = outcome.get("price", 0)
                        
                        if "Over" in name and point == 2.5:
                            resultados["over_25_odds"].append({"bookmaker": bm_name, "odds": odds, "line": point})
                        elif "Under" in name and point == 2.5:
                            resultados["under_25_odds"].append({"bookmaker": bm_name, "odds": odds, "line": point})
        
        # Calcular melhores odds
        resultados["melhores_odds"] = self.calcular_melhores_odds(resultados)
        
        # Analisar valor das odds
        if analise and "detalhes" in analise and "vitoria" in analise['detalhes']:
            v = analise['detalhes']['vitoria']
            
            if resultados["melhores_odds"].get("home_best"):
                home_analysis = self.odds_client.analisar_valor_aposta(
                    resultados["melhores_odds"]["home_best"]["odds"],
                    v.get("home_win", 0)
                )
                resultados["melhores_odds"]["home_best"]["analise"] = home_analysis
            
            if resultados["melhores_odds"].get("away_best"):
                away_analysis = self.odds_client.analisar_valor_aposta(
                    resultados["melhores_odds"]["away_best"]["odds"],
                    v.get("away_win", 0)
                )
                resultados["melhores_odds"]["away_best"]["analise"] = away_analysis
            
            if resultados["melhores_odds"].get("draw_best"):
                draw_analysis = self.odds_client.analisar_valor_aposta(
                    resultados["melhores_odds"]["draw_best"]["odds"],
                    v.get("draw", 0)
                )
                resultados["melhores_odds"]["draw_best"]["analise"] = draw_analysis
        
        # Analisar Over/Under
        if analise and "detalhes" in analise:
            over_prob = analise['detalhes'].get('over_25_prob', 0)
            under_prob = analise['detalhes'].get('under_25_prob', 0)
            
            if resultados["melhores_odds"].get("over_25_best"):
                over_analysis = self.odds_client.analisar_valor_aposta(
                    resultados["melhores_odds"]["over_25_best"]["odds"],
                    over_prob
                )
                resultados["melhores_odds"]["over_25_best"]["analise"] = over_analysis
            
            if resultados["melhores_odds"].get("under_25_best"):
                under_analysis = self.odds_client.analisar_valor_aposta(
                    resultados["melhores_odds"]["under_25_best"]["odds"],
                    under_prob
                )
                resultados["melhores_odds"]["under_25_best"]["analise"] = under_analysis
        
        return resultados
    
    def calcular_melhores_odds(self, odds_data: dict) -> dict:
        """Calcula as melhores odds disponíveis"""
        melhores = {}
        
        # Home win
        if odds_data["home_odds"]:
            best_home = max(odds_data["home_odds"], key=lambda x: x["odds"])
            melhores["home_best"] = best_home
        
        # Away win
        if odds_data["away_odds"]:
            best_away = max(odds_data["away_odds"], key=lambda x: x["odds"])
            melhores["away_best"] = best_away
        
        # Draw
        if odds_data["draw_odds"]:
            best_draw = max(odds_data["draw_odds"], key=lambda x: x["odds"])
            melhores["draw_best"] = best_draw
        
        # Over 2.5
        if odds_data["over_25_odds"]:
            best_over = max(odds_data["over_25_odds"], key=lambda x: x["odds"])
            melhores["over_25_best"] = best_over
        
        # Under 2.5
        if odds_data["under_25_odds"]:
            best_under = max(odds_data["under_25_odds"], key=lambda x: x["odds"])
            melhores["under_25_best"] = best_under
        
        return melhores
    
    def gerar_relatorio_odds(self, resultados: list) -> str:
        """Gera relatório HTML com odds"""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .jogo { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
                .header { background-color: #f5f5f5; padding: 10px; font-weight: bold; }
                .odds-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                .odds-table th, .odds-table td { border: 1px solid #ddd; padding: 8px; text-align: center; }
                .odds-table th { background-color: #f2f2f2; }
                .valor-alto { background-color: #d4edda !important; }
                .valor-moderado { background-color: #fff3cd !important; }
                .valor-baixo { background-color: #f8d7da !important; }
                .odd-value { font-weight: bold; }
                .bookmaker { font-size: 0.9em; color: #666; }
            </style>
        </head>
        <body>
            <h1>📊 Relatório de Odds - Análise de Valor</h1>
        """
        
        for item in resultados:
            jogo = item["jogo"]
            odds = item["odds"]
            analise = item["analise"]
            
            data_br, hora_br = jogo.get_data_hora_brasilia()
            
            html += f"""
            <div class="jogo">
                <div class="header">
                    🏟️ {jogo.home_team} vs {jogo.away_team} - {jogo.competition}
                </div>
                <div>📅 {data_br} 🕒 {hora_br}</div>
                
                <h3>🎯 Análise do Sistema:</h3>
                <ul>
                    <li>Tendência: {analise['tendencia']}</li>
                    <li>Probabilidade: {analise['probabilidade']:.1f}%</li>
                    <li>Confiança: {analise['confianca']:.1f}%</li>
            """
            
            if "vitoria" in analise['detalhes']:
                v = analise['detalhes']['vitoria']
                html += f"""
                    <li>Favorito: {jogo.home_team if v['favorito']=='home' else jogo.away_team if v['favorito']=='away' else 'EMPATE'}</li>
                    <li>Prob. Casa: {v['home_win']:.1f}% | Fora: {v['away_win']:.1f}% | Empate: {v['draw']:.1f}%</li>
                """
            
            html += """
                </ul>
                
                <h3>💰 Melhores Odds Disponíveis:</h3>
                <table class="odds-table">
                    <tr>
                        <th>Mercado</th>
                        <th>Bookmaker</th>
                        <th>Odds</th>
                        <th>Prob. Implícita</th>
                        <th>Edge</th>
                        <th>Kelly</th>
                        <th>Recomendação</th>
                    </tr>
            """
            
            # Adicionar linhas para cada mercado
            mercados = [
                ("home_best", "Casa", odds.get("melhores_odds", {})),
                ("away_best", "Fora", odds.get("melhores_odds", {})),
                ("draw_best", "Empate", odds.get("melhores_odds", {})),
                ("over_25_best", "Over 2.5", odds.get("melhores_odds", {})),
                ("under_25_best", "Under 2.5", odds.get("melhores_odds", {}))
            ]
            
            for mercado_key, mercado_nome, melhores in mercados:
                if mercado_key in melhores:
                    odd_data = melhores[mercado_key]
                    analise_data = odd_data.get("analise", {})
                    
                    classe_valor = ""
                    if analise_data.get("valor"):
                        if analise_data.get("edge", 0) > 5:
                            classe_valor = "valor-alto"
                        elif analise_data.get("edge", 0) > 2:
                            classe_valor = "valor-moderado"
                        else:
                            classe_valor = "valor-baixo"
                    
                    html += f"""
                    <tr class="{classe_valor}">
                        <td>{mercado_nome}</td>
                        <td><span class="bookmaker">{odd_data.get('bookmaker', 'N/A')}</span></td>
                        <td><span class="odd-value">{odd_data.get('odds', 0):.2f}</span></td>
                        <td>{analise_data.get('probabilidade_implicita', 0):.1f}%</td>
                        <td>{analise_data.get('edge', 0):+.1f}%</td>
                        <td>{analise_data.get('kelly', 0):.1f}%</td>
                        <td>{analise_data.get('cor', '')} {analise_data.get('recomendacao', 'N/A')}</td>
                    </tr>
                    """
            
            html += """
                </table>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html


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
    def carregar_alertas_top() -> dict:
        """Carrega alertas TOP do arquivo"""
        return DataStorage.carregar_json(ConfigManager.ALERTAS_TOP_PATH)
    
    @staticmethod
    def salvar_alertas_top(alertas_top: dict):
        """Salva alertas TOP no arquivo"""
        DataStorage.salvar_json(ConfigManager.ALERTAS_TOP_PATH, alertas_top)
    
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
            "resultado_ht": self.resultado_ht
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
        
        return data_dict


class Alerta:
    """Representa um alerta gerado pelo sistema"""
    
    def __init__(self, jogo: Jogo, data_busca: str, tipo_alerta: str = "over_under"):
        self.jogo = jogo
        self.data_busca = data_busca
        self.data_hora_busca = datetime.now()
        self.tipo_alerta = tipo_alerta  # "over_under", "favorito", "gols_ht"
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
            "alerta_enviado": self.alerta_enviado
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


class AnalisadorTendencia:
    """Analisa tendências de gols em partidas"""

    def __init__(self, classificacao: dict):
        self.classificacao = classificacao

    def calcular_tendencia_completa(self, home: str, away: str) -> dict:
        """Calcula tendências completas com análise refinada"""

        dados_home = self.classificacao.get(home, {})
        dados_away = self.classificacao.get(away, {})

        played_home = max(dados_home.get("played", 1), 1)
        played_away = max(dados_away.get("played", 1), 1)

        media_home_feitos = dados_home.get("scored", 0) / played_home
        media_home_sofridos = dados_home.get("against", 0) / played_home
        media_away_feitos = dados_away.get("scored", 0) / played_away
        media_away_sofridos = dados_away.get("against", 0) / played_away

        estimativa_total = (
            media_home_feitos * 0.55 +
            media_away_feitos * 0.45 +
            media_home_sofridos * 0.35 +
            media_away_sofridos * 0.35
        )

        fator_casa = clamp(1.05 + (media_home_feitos - media_home_sofridos) * 0.1, 1.0, 1.2)
        estimativa_total *= fator_casa

        estimativa_total = clamp(estimativa_total, 0.8, 4.5)

        media_liga = 2.5
        estimativa_total = estimativa_total * 0.75 + media_liga * 0.25

        prob_over_15 = sigmoid((estimativa_total - 1.5) * 1.5)
        prob_over_25 = sigmoid((estimativa_total - 2.5) * 1.4)
        prob_over_35 = sigmoid((estimativa_total - 3.5) * 1.3)

        prob_under_15 = 1 - prob_over_15
        prob_under_25 = 1 - prob_over_25

        if prob_under_15 > 0.65:
            tendencia_principal = "UNDER 1.5"
            tipo_aposta = "under"
            probabilidade_base = prob_under_15
        elif prob_under_25 > 0.60:
            tendencia_principal = "UNDER 2.5"
            tipo_aposta = "under"
            probabilidade_base = prob_under_25
        elif prob_over_35 > 0.55:
            tendencia_principal = "OVER 3.5"
            tipo_aposta = "over"
            probabilidade_base = prob_over_35
        elif prob_over_25 > 0.60:
            tendencia_principal = "OVER 2.5"
            tipo_aposta = "over"
            probabilidade_base = prob_over_25
        else:
            tendencia_principal = "OVER 1.5"
            tipo_aposta = "over"
            probabilidade_base = prob_over_15

        sinais_concordantes = 0
        if tipo_aposta == "over" and estimativa_total > 2.0:
            sinais_concordantes += 1
        if tipo_aposta == "under" and estimativa_total < 2.3:
            sinais_concordantes += 1
        if probabilidade_base > 0.65:
            sinais_concordantes += 1

        confianca = clamp((probabilidade_base * 100) * 0.6 + sinais_concordantes * 15, 45, 92)

        vitoria_analise = AnalisadorEstatistico.calcular_probabilidade_vitoria(
            home, away, self.classificacao
        )
        ht_analise = AnalisadorEstatistico.calcular_probabilidade_gols_ht(
            home, away, self.classificacao
        )

        logging.info(
            f"ANÁLISE COMPLETA: {home} vs {away} | "
            f"Est: {estimativa_total:.2f} | "
            f"Tend: {tendencia_principal} | "
            f"Prob: {probabilidade_base*100:.1f}% | "
            f"Conf: {confianca:.1f}%"
        )

        return {
            "tendencia": tendencia_principal,
            "estimativa": round(estimativa_total, 2),
            "probabilidade": round(probabilidade_base * 100, 1),
            "confianca": round(confianca, 1),
            "tipo_aposta": tipo_aposta,
            "detalhes": {
                "vitoria": vitoria_analise,
                "gols_ht": ht_analise,
                "over_15_prob": round(prob_over_15 * 100, 1),
                "over_25_prob": round(prob_over_25 * 100, 1),
                "over_35_prob": round(prob_over_35 * 100, 1),
                "under_15_prob": round(prob_under_15 * 100, 1),
                "under_25_prob": round(prob_under_25 * 100, 1)
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
        self.retry_handler = ExponentialBackoffRetry(max_retries=3)
    
    def obter_dados_api_com_retry(self, url: str, timeout: int = 15) -> dict | None:
        """Obtém dados da API com rate limiting e retry automático"""
        def _make_request():
            self.rate_limiter.wait_if_needed()
            
            logging.info(f"🔗 Request: {url}")
            
            response = requests.get(url, headers=self.config.HEADERS, timeout=timeout)
            
            if response.status_code == 429:
                self.api_monitor.log_request(False, True)
                retry_after = int(response.headers.get('Retry-After', 60))
                logging.warning(f"⏳ Rate limit da API. Esperando {retry_after} segundos...")
                time.sleep(retry_after)
                raise Exception("Rate limit atingido")
                
            response.raise_for_status()
            
            self.api_monitor.log_request(True)
            
            remaining = response.headers.get('X-Requests-Remaining', 'unknown')
            reset_time = response.headers.get('X-RequestCounter-Reset', 'unknown')
            logging.info(f"✅ Request OK. Restantes: {remaining}, Reset: {reset_time}s")
            
            return response.json()
        
        try:
            return self.retry_handler.execute(_make_request)
        except Exception as e:
            logging.error(f"❌ Falha após retries para {url}: {e}")
            return None
    
    def obter_dados_api(self, url: str, timeout: int = 15) -> dict | None:
        return self.obter_dados_api_com_retry(url, timeout)
    
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
        self.retry_handler = ExponentialBackoffRetry(max_retries=3)
    
    def enviar_mensagem(self, msg: str, chat_id: str = None, disable_web_page_preview: bool = True) -> bool:
        """Envia mensagem para o Telegram"""
        if chat_id is None:
            chat_id = self.config.TELEGRAM_CHAT_ID
        
        def _send():
            params = {
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": str(disable_web_page_preview).lower()
            }
            response = requests.get(f"{self.config.BASE_URL_TG}/sendMessage", params=params, timeout=10)
            return response.status_code == 200
        
        try:
            return self.retry_handler.execute(_send)
        except Exception as e:
            logging.error(f"Erro ao enviar para Telegram: {e}")
            return False
    
    def enviar_foto(self, photo_bytes: io.BytesIO, caption: str = "", chat_id: str = None) -> bool:
        """Envia uma foto (BytesIO) para o Telegram"""
        if chat_id is None:
            chat_id = self.config.TELEGRAM_CHAT_ID_ALT2
        
        def _send():
            photo_bytes.seek(0)
            files = {"photo": ("elite_master.png", photo_bytes, "image/png")}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            resp = requests.post(f"{self.config.BASE_URL_TG}/sendPhoto", data=data, files=files, timeout=15)
            return resp.status_code == 200
        
        try:
            return self.retry_handler.execute(_send)
        except Exception as e:
            logging.error(f"Erro ao enviar foto para Telegram: {e}")
            return False


# =============================
# SISTEMA PRINCIPAL (ATUALIZADO COM AS NOVAS CLASSES)
# =============================

class SistemaAlertasFutebol:
    """Sistema principal de alertas de futebol - ATUALIZADO COM NOVAS CLASSES"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self.config = ConfigManager()
        self.rate_limiter = RateLimiter()
        self.api_monitor = APIMonitor()
        self.api_client = APIClient(self.rate_limiter, self.api_monitor)
        self.odds_client = APIOddsClient(self.rate_limiter, self.api_monitor)
        self.odds_manager = OddsManager(self.api_client, self.odds_client)
        self.telegram_client = TelegramClient()
        self.poster_generator = PosterGenerator(self.api_client)
        self.image_cache = self.api_client.image_cache
        
        # Inicializar novo sistema de alertas
        self.notificador = NotificadorTelegram(self.config.TELEGRAM_TOKEN, self.config.TELEGRAM_CHAT_ID_ALT2)
        self.ranking = RankingTop3DoDia()
        self.gerenciador_notificacoes = GerenciadorNotificacoes(self.notificador, somente_top3=False)
        self.motor_alertas = MotorDeAlertas(self.ranking, self.gerenciador_notificacoes)
        
        # Carregar ranking existente
        self.ranking.carregar_ranking()
        
        # Inicializar logging
        self._setup_logging()
        
        self._initialized = True
    
    def _setup_logging(self):
        """Configura o sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('sistema_alertas.log'),
                logging.StreamHandler()
            ]
        )
    
    def validar_configuracao(self):
        """Valida se todas as configurações necessárias estão presentes"""
        return self.config.validar_configuracao()
    
    def testar_conexoes(self):
        """Testa conexão com todas as APIs"""
        return self.config.testar_apis()
    
    def processar_jogos(self, data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf, 
                       max_conf, estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                       formato_top_jogos, tipo_filtro, tipo_analise, config_analise):
        """Processa jogos e gera alertas - ATUALIZADO COM NOVO SISTEMA"""
        # Validar configuração primeiro
        faltantes = self.validar_configuracao()
        if faltantes:
            st.error(f"❌ Configurações faltando: {', '.join(faltantes)}")
            st.info("ℹ️ Configure as variáveis de ambiente em um arquivo .env")
            return
        
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
        
        alertas_novos = []  # Para coletar alertas do novo sistema
        
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
                    
                    st.write(f"      Status: {jogo.status}")
                    
                    # ============ NOVO SISTEMA: PROCESSAR COM MOTOR DE ALERTAS ============
                    # Processar alertas de over/under
                    if tipo_analise == "Over/Under de Gols" and min_conf <= analise["confianca"] <= max_conf:
                        if tipo_filtro == "Todos" or \
                           (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or \
                           (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                            
                            # Criar alerta do novo sistema
                            prob_mercado = {
                                "OVER 2.5": analise['detalhes'].get('over_25_prob', 0) / 100,
                                "UNDER 2.5": analise['detalhes'].get('under_25_prob', 0) / 100,
                                "OVER 1.5": analise['detalhes'].get('over_15_prob', 0) / 100,
                                "UNDER 1.5": analise['detalhes'].get('under_15_prob', 0) / 100
                            }.get(analise['tendencia'], 0.5)
                            
                            # Tentar obter odds para este jogo
                            odds_data = self.odds_client.obter_odds_por_jogo(
                                fixture_id=str(jogo.id),
                                data_jogo=hoje,
                                home_team=jogo.home_team,
                                away_team=jogo.away_team
                            )
                            
                            if odds_data and 'bookmakers' in odds_data:
                                # Encontrar odd para este mercado
                                odd_encontrada = self._encontrar_odd_para_mercado(odds_data, analise['tendencia'])
                                
                                if odd_encontrada and odd_encontrada > 1.01:
                                    # Processar alerta no novo sistema
                                    alerta_novo = self.motor_alertas.processar_alerta(
                                        jogo=jogo,
                                        mercado=analise['tendencia'],
                                        odd=odd_encontrada,
                                        probabilidade=prob_mercado,
                                        confianca=analise['confianca']
                                    )
                                    
                                    if alerta_novo and alerta_novo.qualidade == "A":
                                        alertas_novos.append(alerta_novo)
                                        st.success(f"   🆕 Alerta Novo Sistema: Qualidade {alerta_novo.qualidade} | Score: {alerta_novo.score:.1f}")
                    
                    # Processar alertas de favoritos
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
                                    
                                    # Tentar obter odds
                                    odds_data = self.odds_client.obter_odds_por_jogo(
                                        fixture_id=str(jogo.id),
                                        data_jogo=hoje,
                                        home_team=jogo.home_team,
                                        away_team=jogo.away_team
                                    )
                                    
                                    if odds_data:
                                        # Determinar mercado e odd
                                        mercado_favorito = "Casa" if v['favorito'] == "home" else "Fora" if v['favorito'] == "away" else "Empate"
                                        odd_encontrada = self._encontrar_odd_favorito(odds_data, v['favorito'])
                                        
                                        if odd_encontrada and odd_encontrada > 1.01:
                                            prob_favorito = {
                                                "home": v['home_win'] / 100,
                                                "away": v['away_win'] / 100,
                                                "draw": v['draw'] / 100
                                            }.get(v['favorito'], 0.5)
                                            
                                            alerta_novo = self.motor_alertas.processar_alerta(
                                                jogo=jogo,
                                                mercado=mercado_favorito,
                                                odd=odd_encontrada,
                                                probabilidade=prob_favorito,
                                                confianca=v['confianca_vitoria']
                                            )
                                            
                                            if alerta_novo and alerta_novo.qualidade == "A":
                                                alertas_novos.append(alerta_novo)
                                                st.success(f"   🏆 Alerta Favorito Novo: Qualidade {alerta_novo.qualidade}")
                    
                    # Sistema antigo (mantido para compatibilidade)
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

                    top_jogos.append(jogo.to_dict())
                
                if j + batch_size < len(jogos_data):
                    time.sleep(0.5)
            
            progress_bar.progress((i + 1) / total_ligas)
        
        # Filtrar por tipo de análise
        jogos_filtrados = self._filtrar_por_tipo_analise(top_jogos, tipo_analise, config_analise)
        
        st.write(f"📊 Total de jogos: {len(top_jogos)}")
        st.write(f"📊 Jogos após filtros: {len(jogos_filtrados)}")
        
        # Mostrar estatísticas do novo sistema
        if alertas_novos:
            st.markdown("---")
            st.subheader("🆕 Novo Sistema de Alertas")
            
            alertas_qualidade_A = [a for a in alertas_novos if a.qualidade == "A"]
            alertas_qualidade_B = [a for a in alertas_novos if a.qualidade == "B"]
            alertas_qualidade_C = [a for a in alertas_novos if a.qualidade == "C"]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🟢 Qualidade A", len(alertas_qualidade_A))
            with col2:
                st.metric("🟡 Qualidade B", len(alertas_qualidade_B))
            with col3:
                st.metric("🟠 Qualidade C", len(alertas_qualidade_C))
            
            # Mostrar alertas de qualidade A
            if alertas_qualidade_A:
                st.write("**🎯 Alertas de Qualidade A (Recomendados):**")
                for alerta in alertas_qualidade_A[:5]:  # Limitar a 5
                    jogo_info = f"{alerta.jogo.home_team} vs {alerta.jogo.away_team}"
                    st.write(f"   • {jogo_info}: {alerta.mercado} @ {alerta.odd:.2f} | Score: {alerta.score:.1f} | EV: {alerta.ev:.3f}")
            
            # Enviar top 3 do dia
            if st.button("🏆 Enviar Top 3 do Dia", key="btn_top3_novo"):
                enviados = self.motor_alertas.enviar_top3_diario()
                st.success(f"✅ Top {enviados} alertas enviados!")
        
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
    
    def _encontrar_odd_para_mercado(self, odds_data: dict, mercado: str) -> float:
        """Encontra odd para um mercado específico"""
        if not odds_data or 'bookmakers' not in odds_data:
            return 0.0
        
        for bookmaker in odds_data['bookmakers']:
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'totals':
                    for outcome in market.get('outcomes', []):
                        point = outcome.get('point', 0)
                        name = outcome.get('name', '')
                        
                        # Verificar correspondência com o mercado
                        if "OVER" in mercado and "Over" in name and point == float(mercado.split()[1]):
                            return float(outcome.get('price', 0))
                        elif "UNDER" in mercado and "Under" in name and point == float(mercado.split()[1]):
                            return float(outcome.get('price', 0))
        
        return 0.0
    
    def _encontrar_odd_favorito(self, odds_data: dict, favorito: str) -> float:
        """Encontra odd para um favorito específico"""
        if not odds_data or 'bookmakers' not in odds_data:
            return 0.0
        
        for bookmaker in odds_data['bookmakers']:
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'h2h':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '')
                        
                        if (favorito == "home" and name in ["Home", "1"]) or \
                           (favorito == "away" and name in ["Away", "2"]) or \
                           (favorito == "draw" and name in ["Draw", "X"]):
                            return float(outcome.get('price', 0))
        
        return 0.0
    
    def processar_odds_com_novo_sistema(self, data_selecionada, ligas_selecionadas, todas_ligas):
        """Processa odds com o novo sistema de alertas"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.info(f"🆕 Processando odds com novo sistema para {hoje}...")
        
        # Buscar odds
        resultados = self.odds_manager.buscar_odds_com_analise(
            data_selecionada, ligas_selecionadas, todas_ligas
        )
        
        alertas_gerados = []
        
        for item in resultados:
            jogo = item["jogo"]
            odds = item["odds"]
            analise = item["analise"]
            
            # Processar com motor de alertas
            alertas_jogo = self.motor_alertas.processar_alerta_from_odds(
                jogo, odds, analise['detalhes']
            )
            
            if alertas_jogo:
                alertas_gerados.extend(alertas_jogo)
        
        # Mostrar estatísticas
        if alertas_gerados:
            st.markdown("---")
            st.subheader("📊 Estatísticas do Novo Sistema")
            
            stats = self.motor_alertas.get_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Alertas Processados", stats["alertas_processados"])
            with col2:
                st.metric("Qualidade A", stats["alertas_qualidade_A"])
            with col3:
                st.metric("Taxa Qualidade A", stats["taxa_qualidade_A"])
            with col4:
                st.metric("Top 3 Hoje", stats["top3_hoje"])
            
            # Mostrar alertas de qualidade A
            alertas_A = [a for a in alertas_gerados if a.qualidade == "A"]
            if alertas_A:
                st.write("**🎯 Alertas de Qualidade A Gerados:**")
                for alerta in alertas_A[:5]:
                    jogo_info = f"{alerta.jogo.home_team} vs {alerta.jogo.away_team}"
                    st.write(f"   • {jogo_info}: {alerta.mercado} @ {alerta.odd:.2f}")
                    st.write(f"     Score: {alerta.score:.1f} | EV: {alerta.ev:.3f} | Prob: {int(alerta.probabilidade*100)}%")
            
            return alertas_gerados
        
        return []
    
    # ==================== MÉTODOS ORIGINAIS (MANTIDOS) ====================
    
    def conferir_resultados(self, data_selecionada):
        """Conferir resultados dos jogos com alertas ativos"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.subheader(f"📊 Conferindo Resultados para {data_selecionada.strftime('%d/%m/%Y')}")
        
        # Conferir resultados para todos os tipos de alerta
        resultados_totais = {
            "over_under": self._conferir_resultados_tipo("over_under", hoje),
            "favorito": self._conferir_resultados_tipo("favorito", hoje),
            "gols_ht": self._conferir_resultados_tipo("gols_ht", hoje)
        }
        
        # Mostrar resumo
        st.markdown("---")
        st.subheader("📈 RESUMO DE RESULTADOS")
        
        col1, col2, col3 = st.columns(3)
        
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
        
        # Enviar alertas de resultados automaticamente em lotes de 3
        if any(resultados_totais.values()):
            st.info("🚨 Enviando alertas de resultados automaticamente...")
            self._enviar_alertas_resultados_automaticos(resultados_totais, data_selecionada)
    
    def buscar_odds_com_analise(self, data_selecionada, ligas_selecionadas, todas_ligas, formato_saida="tabela"):
        """Busca odds com análise de valor - ATUALIZADO"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.info(f"🔍 Buscando odds para {hoje}...")
        
        # Testar conexão primeiro
        if not self.odds_client.testar_conexao():
            st.error("❌ Falha na conexão com a Odds API. Verifique sua API Key.")
            return []
        
        # Opção 1: Buscar odds integradas com análise (pode não encontrar todos os jogos)
        st.info("📊 Buscando odds com análise...")
        resultados_integrados = self.odds_manager.buscar_odds_com_analise(
            data_selecionada, ligas_selecionadas, todas_ligas
        )
        
        # Opção 2: Buscar odds diretamente da API (mais completo)
        st.info("🔗 Buscando odds diretamente da API...")
        resultados_diretos = self.odds_manager.buscar_odds_direto_api(
            data_selecionada, ligas_selecionadas, todas_ligas
        )
        
        # Combinar resultados
        todos_resultados = resultados_integrados + resultados_diretos
        
        # Remover duplicados baseado no ID do jogo
        resultados_unicos = []
        ids_vistos = set()
        
        for resultado in todos_resultados:
            jogo = resultado["jogo"]
            jogo_id = f"{jogo.home_team}_{jogo.away_team}"
            
            if jogo_id not in ids_vistos:
                ids_vistos.add(jogo_id)
                resultados_unicos.append(resultado)
        
        if not resultados_unicos:
            st.warning("⚠️ Nenhuma odd encontrada para os critérios selecionados")
            return []
        
        st.success(f"✅ Encontradas odds para {len(resultados_unicos)} jogos")
        
        if formato_saida == "tabela":
            self._mostrar_odds_tabela(resultados_unicos)
        elif formato_saida == "relatorio":
            self._gerar_relatorio_odds(resultados_unicos)
        elif formato_saida == "valor":
            self._mostrar_odds_com_valor(resultados_unicos)
        
        return resultados_unicos
    
    def _mostrar_odds_tabela(self, resultados: list):
        """Mostra odds em formato de tabela"""
        for item in resultados:
            jogo = item["jogo"]
            odds = item["odds"]
            analise = item["analise"]
            
            data_br, hora_br = jogo.get_data_hora_brasilia()
            
            with st.expander(f"🏟️ {jogo.home_team} vs {jogo.away_team} - {hora_br}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**📊 Análise do Sistema:**")
                    st.write(f"🎯 Tendência: {analise.get('tendencia', 'N/A')}")
                    st.write(f"⚽ Estimativa: {analise.get('estimativa', 0):.2f} gols")
                    st.write(f"📈 Probabilidade: {analise.get('probabilidade', 0):.1f}%")
                    st.write(f"🔍 Confiança: {analise.get('confianca', 0):.1f}%")
                    
                    if "vitoria" in analise.get('detalhes', {}):
                        v = analise['detalhes']['vitoria']
                        st.write(f"🏆 Favorito: {jogo.home_team if v.get('favorito')=='home' else jogo.away_team if v.get('favorito')=='away' else 'EMPATE'}")
                
                with col2:
                    st.write(f"**💰 Melhores Odds:**")
                    
                    melhores = odds.get("melhores_odds", {})
                    
                    if "home_best" in melhores:
                        odd_data = melhores["home_best"]
                        analise_data = odd_data.get("analise", {})
                        cor = analise_data.get("cor", "⚪")
                        st.write(f"{cor} **Casa:** {odd_data['odds']:.2f} ({odd_data['bookmaker']})")
                        if analise_data:
                            st.write(f"   Edge: {analise_data.get('edge', 0):+.1f}% | Kelly: {analise_data.get('kelly', 0):.1f}%")
                    
                    if "away_best" in melhores:
                        odd_data = melhores["away_best"]
                        analise_data = odd_data.get("analise", {})
                        cor = analise_data.get("cor", "⚪")
                        st.write(f"{cor} **Fora:** {odd_data['odds']:.2f} ({odd_data['bookmaker']})")
                        if analise_data:
                            st.write(f"   Edge: {analise_data.get('edge', 0):+.1f}% | Kelly: {analise_data.get('kelly', 0):.1f}%")
                    
                    if "draw_best" in melhores:
                        odd_data = melhores["draw_best"]
                        analise_data = odd_data.get("analise", {})
                        cor = analise_data.get("cor", "⚪")
                        st.write(f"{cor} **Empate:** {odd_data['odds']:.2f} ({odd_data['bookmaker']})")
                        if analise_data:
                            st.write(f"   Edge: {analise_data.get('edge', 0):+.1f}% | Kelly: {analise_data.get('kelly', 0):.1f}%")
                    
                    if "over_25_best" in melhores:
                        odd_data = melhores["over_25_best"]
                        analise_data = odd_data.get("analise", {})
                        cor = analise_data.get("cor", "⚪")
                        st.write(f"{cor} **Over 2.5:** {odd_data['odds']:.2f} ({odd_data['bookmaker']})")
                        if analise_data:
                            st.write(f"   Edge: {analise_data.get('edge', 0):+.1f}% | Kelly: {analise_data.get('kelly', 0):.1f}%")
                    
                    if "under_25_best" in melhores:
                        odd_data = melhores["under_25_best"]
                        analise_data = odd_data.get("analise", {})
                        cor = analise_data.get("cor", "⚪")
                        st.write(f"{cor} **Under 2.5:** {odd_data['odds']:.2f} ({odd_data['bookmaker']})")
                        if analise_data:
                            st.write(f"   Edge: {analise_data.get('edge', 0):+.1f}% | Kelly: {analise_data.get('kelly', 0):.1f}%")
                
                # Mostrar todas as odds disponíveis
                if st.checkbox(f"Mostrar todas as odds para {jogo.home_team} vs {jogo.away_team}", key=f"todas_{jogo.id}"):
                    self._mostrar_todas_odds(odds)
    
    def _mostrar_todas_odds(self, odds_data: dict):
        """Mostra todas as odds disponíveis para um jogo"""
        st.write("**📊 Todas as Odds Disponíveis:**")
        
        # Casa
        if odds_data.get("home_odds"):
            st.write("**Casa:**")
            for odd in sorted(odds_data["home_odds"], key=lambda x: x["odds"], reverse=True):
                st.write(f"  {odd['bookmaker']}: {odd['odds']:.2f}")
        
        # Fora
        if odds_data.get("away_odds"):
            st.write("**Fora:**")
            for odd in sorted(odds_data["away_odds"], key=lambda x: x["odds"], reverse=True):
                st.write(f"  {odd['bookmaker']}: {odd['odds']:.2f}")
        
        # Empate
        if odds_data.get("draw_odds"):
            st.write("**Empate:**")
            for odd in sorted(odds_data["draw_odds"], key=lambda x: x["odds"], reverse=True):
                st.write(f"  {odd['bookmaker']}: {odd['odds']:.2f}")
        
        # Over/Under
        if odds_data.get("over_25_odds"):
            st.write("**Over 2.5:**")
            for odd in sorted(odds_data["over_25_odds"], key=lambda x: x["odds"], reverse=True):
                st.write(f"  {odd['bookmaker']}: {odd['odds']:.2f} (linha: {odd.get('line', 2.5)})")
        
        if odds_data.get("under_25_odds"):
            st.write("**Under 2.5:**")
            for odd in sorted(odds_data["under_25_odds"], key=lambda x: x["odds"], reverse=True):
                st.write(f"  {odd['bookmaker']}: {odd['odds']:.2f} (linha: {odd.get('line', 2.5)})")
    
    def _mostrar_odds_com_valor(self, resultados: list):
        """Mostra apenas odds com valor positivo"""
        st.subheader("🎯 Odds com Valor Positivo (Edge > 0%)")
        
        jogos_com_valor = []
        
        for item in resultados:
            jogo = item["jogo"]
            odds = item["odds"]
            melhores = odds.get("melhores_odds", {})
            
            tem_valor = False
            for mercado in ["home_best", "away_best", "draw_best", "over_25_best", "under_25_best"]:
                if mercado in melhores:
                    analise = melhores[mercado].get("analise", {})
                    if analise.get("valor", False) and analise.get("edge", 0) > 0:
                        tem_valor = True
                        break
            
            if tem_valor:
                jogos_com_valor.append(item)
        
        if not jogos_com_valor:
            st.info("ℹ️ Nenhuma odd com valor positivo encontrada")
            return
        
        for item in jogos_com_valor:
            jogo = item["jogo"]
            odds = item["odds"]
            melhores = odds.get("melhores_odds", {})
            
            data_br, hora_br = jogo.get_data_hora_brasilia()
            
            with st.expander(f"💰 {jogo.home_team} vs {jogo.away_team} - {hora_br}"):
                st.write(f"**📅 {data_br} | 🏆 {jogo.competition}**")
                
                # Mostrar mercados com valor
                for mercado_key, mercado_nome in [
                    ("home_best", "Casa"),
                    ("away_best", "Fora"),
                    ("draw_best", "Empate"),
                    ("over_25_best", "Over 2.5"),
                    ("under_25_best", "Under 2.5")
                ]:
                    if mercado_key in melhores:
                        odd_data = melhores[mercado_key]
                        analise_data = odd_data.get("analise", {})
                        
                        if analise_data.get("valor", False) and analise_data.get("edge", 0) > 0:
                            cor = analise_data.get("cor", "⚪")
                            edge = analise_data.get("edge", 0)
                            kelly = analise_data.get("kelly", 0)
                            
                            st.write(f"{cor} **{mercado_nome}:** {odd_data['odds']:.2f} ({odd_data['bookmaker']})")
                            st.write(f"   📊 Edge: **{edge:+.1f}%** | 🎯 Kelly: **{kelly:.1f}%**")
                            st.write(f"   📈 Nossa Prob: {analise_data.get('probabilidade_nossa', 0):.1f}%")
                            st.write(f"   📉 Prob. Implícita: {analise_data.get('probabilidade_implicita', 0):.1f}%")
                            st.write("---")
    
    def _gerar_relatorio_odds(self, resultados: list):
        """Gera e mostra relatório HTML de odds"""
        html = self.odds_manager.gerar_relatorio_odds(resultados)
        
        # Mostrar preview do HTML
        st.subheader("📄 Preview do Relatório")
        st.components.v1.html(html, height=800, scrolling=True)
        
        # Opção para baixar
        st.download_button(
            label="📥 Baixar Relatório HTML",
            data=html,
            file_name=f"relatorio_odds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html"
        )
        
        # Opção para enviar por Telegram
        if st.button("📤 Enviar Relatório por Telegram"):
            # Converter HTML para texto simplificado para Telegram
            texto = "📊 RELATÓRIO DE ODDS COM ANÁLISE DE VALOR\n\n"
            
            for item in resultados[:10]:  # Limitar a 10 jogos para não exceder limite
                jogo = item["jogo"]
                odds = item["odds"]
                melhores = odds.get("melhores_odds", {})
                
                texto += f"🏟️ {jogo.home_team} vs {jogo.away_team}\n"
                texto += f"🏆 {jogo.competition}\n"
                
                for mercado_key, mercado_nome in [
                    ("home_best", "Casa"),
                    ("away_best", "Fora"),
                    ("draw_best", "Empate")
                ]:
                    if mercado_key in melhores:
                        odd_data = melhores[mercado_key]
                        analise_data = odd_data.get("analise", {})
                        
                        if analise_data.get("valor", False):
                            cor = analise_data.get("cor", "")
                            edge = analise_data.get("edge", 0)
                            texto += f"{cor} {mercado_nome}: {odd_data['odds']:.2f} (Edge: {edge:+.1f}%)\n"
                
                texto += "\n"
            
            if self.telegram_client.enviar_mensagem(texto, self.config.TELEGRAM_CHAT_ID_ALT2):
                st.success("✅ Relatório enviado para Telegram!")
    
    def _conferir_resultados_tipo(self, tipo_alerta: str, data_busca: str) -> dict:
        """Conferir resultados para um tipo específico de alerta"""
        # Carregar alertas do tipo específico
        if tipo_alerta == "over_under":
            alertas = DataStorage.carregar_alertas()
            resultados = DataStorage.carregar_resultados()
        elif tipo_alerta == "favorito":
            alertas = DataStorage.carregar_alertas_favoritos()
            resultados = DataStorage.carregar_resultados_favoritos()
        elif tipo_alerta == "gols_ht":
            alertas = DataStorage.carregar_alertas_gols_ht()
            resultados = DataStorage.carregar_resultados_gols_ht()
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
            
            # Obter detalhes atualizados do jogo
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
                
                # Obter URLs dos escudos
                home_crest = match_data.get("homeTeam", {}).get("crest") or ""
                away_crest = match_data.get("awayTeam", {}).get("crest") or ""
                
                # Criar objeto Jogo com os dados do alerta
                jogo = Jogo({
                    "id": fixture_id,
                    "homeTeam": {"name": alerta.get("home", ""), "crest": home_crest},
                    "awayTeam": {"name": alerta.get("away", ""), "crest": away_crest},
                    "utcDate": alerta.get("hora", ""),
                    "competition": {"name": alerta.get("liga", "")},
                    "status": status
                })
                
                # Definir análise do alerta
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
                                "estimativa_total_ht": alerta.get("estimativa_total_ht", 0.0)
                            }
                        }
                    })
                
                # Definir resultado
                jogo.set_resultado(home_goals, away_goals, ht_home_goals, ht_away_goals)
                
                # Salvar resultado
                resultados[fixture_id] = jogo.to_dict()
                resultados[fixture_id]["data_conferencia"] = datetime.now().isoformat()
                
                # Marcar como conferido
                alertas[fixture_id]["conferido"] = True
                
                # Adicionar à lista
                jogos_com_resultados[fixture_id] = resultados[fixture_id]
                
                # Mostrar resultado
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
            
            progress_bar.progress((idx + 1) / total_alertas)
        
        # Salvar alertas e resultados atualizados
        if tipo_alerta == "over_under":
            DataStorage.salvar_alertas(alertas)
            DataStorage.salvar_resultados(resultados)
        elif tipo_alerta == "favorito":
            DataStorage.salvar_alertas_favoritos(alertas)
            DataStorage.salvar_resultados_favoritos(resultados)
        elif tipo_alerta == "gols_ht":
            DataStorage.salvar_alertas_gols_ht(alertas)
            DataStorage.salvar_resultados_gols_ht(resultados)
        
        return jogos_com_resultados
    
    def _enviar_alertas_resultados_automaticos(self, resultados_totais: dict, data_selecionada):
        """Enviar alertas de resultados automaticamente em lotes de 3"""
        data_str = data_selecionada.strftime("%d/%m/%Y")
        
        for tipo_alerta, resultados in resultados_totais.items():
            if not resultados:
                continue
            
            jogos_lista = list(resultados.values())
            
            # Dividir em lotes de 3 jogos
            batch_size = 3
            for i in range(0, len(jogos_lista), batch_size):
                batch = jogos_lista[i:i+batch_size]
                
                # Gerar poster para o lote
                try:
                    if tipo_alerta == "over_under":
                        titulo = f" RESULTADOS OVER/UNDER - Lote {i//batch_size + 1}"
                    elif tipo_alerta == "favorito":
                        titulo = f" RESULTADOS FAVORITOS - Lote {i//batch_size + 1}"
                    elif tipo_alerta == "gols_ht":
                        titulo = f" RESULTADOS GOLS HT - Lote {i//batch_size + 1}"
                    
                    # Gerar poster
                    poster = self.poster_generator.gerar_poster_resultados(batch, tipo_alerta)
                    
                    # Preparar caption
                    if tipo_alerta == "over_under":
                        greens = sum(1 for j in batch if j.get("resultado") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado") == "RED")
                    elif tipo_alerta == "favorito":
                        greens = sum(1 for j in batch if j.get("resultado_favorito") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado_favorito") == "RED")
                    elif tipo_alerta == "gols_ht":
                        greens = sum(1 for j in batch if j.get("resultado_ht") == "GREEN")
                        reds = sum(1 for j in batch if j.get("resultado_ht") == "RED")
                    
                    total = greens + reds
                    if total > 0:
                        taxa_acerto = (greens / total) * 100
                        caption = f"<b>{titulo}</b>\n\n"
                        caption += f"<b>📊 LOTE {i//batch_size + 1}: {greens}✅ {reds}❌</b>\n"
                        caption += f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                        caption += f"<b>🔥 ELITE MASTER SYSTEM - RESULTADOS CONFIRMADOS</b>"
                    
                    # Enviar poster
                    if self.telegram_client.enviar_foto(poster, caption=caption):
                        st.success(f" Lote {i//batch_size + 1} de resultados {tipo_alerta} enviado ({len(batch)} jogos)")
                    
                    # Esperar 2 segundos entre lotes
                    time.sleep(2)
                    
                except Exception as e:
                    logging.error(f"Erro ao gerar/enviar poster do lote {i//batch_size + 1}: {e}")
                    st.error(f"❌ Erro no lote {i//batch_size + 1}: {e}")
            
            # Após enviar todos os lotes, enviar um resumo final
            if jogos_lista:
                self._enviar_resumo_final(tipo_alerta, jogos_lista, data_str)
    
    def _enviar_resumo_final(self, tipo_alerta: str, jogos_lista: list, data_str: str):
        """Enviar resumo final após todos os lotes"""
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
        """Verifica e envia alerta individual"""
        # Carregar alertas apropriados baseado no tipo
        if tipo_alerta == "over_under":
            alertas = DataStorage.carregar_alertas()
            path = ConfigManager.ALERTAS_PATH
        elif tipo_alerta == "favorito":
            alertas = DataStorage.carregar_alertas_favoritos()
            path = ConfigManager.ALERTAS_FAVORITOS_PATH
        elif tipo_alerta == "gols_ht":
            alertas = DataStorage.carregar_alertas_gols_ht()
            path = ConfigManager.ALERTAS_GOLS_HT_PATH
        else:
            alertas = {}
            path = ""
        
        fixture_id = str(jogo.id)
        
        # Verificar condições específicas do tipo de alerta
        enviar_alerta = False
        
        if tipo_alerta == "over_under":
            enviar_alerta = (min_conf <= analise["confianca"] <= max_conf)
        elif tipo_alerta == "favorito" and 'vitoria' in analise['detalhes']:
            v = analise['detalhes']['vitoria']
            enviar_alerta = (min_conf <= v['confianca_vitoria'] <= max_conf)
        elif tipo_alerta == "gols_ht" and 'gols_ht' in analise['detalhes']:
            ht = analise['detalhes']['gols_ht']
            enviar_alerta = (min_conf <= ht['confianca_ht'] <= max_conf)
        
        if enviar_alerta and fixture_id not in alertas:
            # Salvar alerta
            alertas[fixture_id] = {
                "tendencia": analise["tendencia"] if tipo_alerta == "over_under" else "",
                "favorito": analise['detalhes'].get('vitoria', {}).get('favorito', '') if tipo_alerta == "favorito" else "",
                "tendencia_ht": analise['detalhes'].get('gols_ht', {}).get('tendencia_ht', '') if tipo_alerta == "gols_ht" else "",
                "estimativa": analise["estimativa"] if tipo_alerta == "over_under" else 0.0,
                "probabilidade": analise["probabilidade"] if tipo_alerta == "over_under" else 0.0,
                "confianca": analise["confianca"] if tipo_alerta == "over_under" else 0.0,
                "confianca_vitoria": analise['detalhes'].get('vitoria', {}).get('confianca_vitoria', 0.0) if tipo_alerta == "favorito" else 0.0,
                "confianca_ht": analise['detalhes'].get('gols_ht', {}).get('confianca_ht', 0.0) if tipo_alerta == "gols_ht" else 0.0,
                "tipo_aposta": analise["tipo_aposta"] if tipo_alerta == "over_under" else "",
                "detalhes": analise["detalhes"],
                "conferido": False,
                "tipo_alerta": tipo_alerta,
                "home": jogo.home_team,
                "away": jogo.away_team,
                "liga": jogo.competition,
                "hora": jogo.get_hora_brasilia_datetime().isoformat(),
                "escudo_home": jogo.home_crest,
                "escudo_away": jogo.away_crest
            }
            
            if alerta_individual:
                self._enviar_alerta_individual(match_data, analise, tipo_alerta, min_conf, max_conf)
            
            # Salvar no arquivo apropriado
            if tipo_alerta == "over_under":
                DataStorage.salvar_alertas(alertas)
            elif tipo_alerta == "favorito":
                DataStorage.salvar_alertas_favoritos(alertas)
            elif tipo_alerta == "gols_ht":
                DataStorage.salvar_alertas_gols_ht(alertas)
    
    def _enviar_alerta_individual(self, fixture: dict, analise: dict, tipo_alerta: str, min_conf: int, max_conf: int):
        """Envia alerta individual para o Telegram"""
        home = fixture["homeTeam"]["name"]
        away = fixture["awayTeam"]["name"]
        
        if tipo_alerta == "over_under":
            tipo_emoji = "🎯" if analise["tipo_aposta"] == "over" else "🛡️"
            caption = (
                f"<b>{tipo_emoji} ALERTA {analise['tipo_aposta'].upper()} DE GOLS</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>📈 Tendência: {analise['tendencia']}</b>\n"
                f"<b>⚽ Estimativa: {analise['estimativa']:.2f} gols</b>\n"
                f"<b>🎯 Probabilidade: {analise['probabilidade']:.0f}%</b>\n"
                f"<b>🔍 Confiança: {analise['confianca']:.0f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        elif tipo_alerta == "favorito" and 'vitoria' in analise['detalhes']:
            v = analise['detalhes']['vitoria']
            favorito_emoji = "🏠" if v['favorito'] == "home" else "✈️" if v['favorito'] == "away" else "🤝"
            favorito_text = home if v['favorito'] == "home" else away if v['favorito'] == "away" else "EMPATE"
            
            caption = (
                f"<b>{favorito_emoji} ALERTA DE FAVORITO</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>🏆 Favorito: {favorito_text}</b>\n"
                f"<b>📊 Probabilidade Casa: {v['home_win']:.1f}%</b>\n"
                f"<b>📊 Probabilidade Fora: {v['away_win']:.1f}%</b>\n"
                f"<b>📊 Probabilidade Empate: {v['draw']:.1f}%</b>\n"
                f"<b>🔍 Confiança: {v['confianca_vitoria']:.1f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        elif tipo_alerta == "gols_ht" and 'gols_ht' in analise['detalhes']:
            ht = analise['detalhes']['gols_ht']
            tipo_emoji_ht = "⚡" if "OVER" in ht['tendencia_ht'] else "🛡️"
            
            caption = (
                f"<b>{tipo_emoji_ht} ALERTA DE GOLS HT</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>⏰ Tendência HT: {ht['tendencia_ht']}</b>\n"
                f"<b>⚽ Estimativa HT: {ht['estimativa_total_ht']:.2f} gols</b>\n"
                f"<b>🎯 OVER 0.5 HT: {ht['over_05_ht']:.0f}%</b>\n"
                f"<b>🎯 OVER 1.5 HT: {ht['over_15_ht']:.0f}%</b>\n"
                f"<b>🔍 Confiança HT: {ht['confianca_ht']:.1f}%</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM</b>"
            )
        else:
            return
        
        # Tentar enviar foto (poster simplificado)
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
            
            draw.text((50, 50), tipo_text, font=fonte, fill=cor_titulo)
            draw.text((50, 100), f"{home} vs {away}", font=fonte, fill=(255, 255, 255))
            
            if tipo_alerta == "over_under":
                draw.text((50, 150), f"Tendência: {analise['tendencia']}", font=fonte, fill=(100, 200, 255))
                draw.text((50, 200), f"Confiança: {analise['confianca']:.0f}%", font=fonte, fill=(100, 255, 100))
            elif tipo_alerta == "favorito" and 'vitoria' in analise['detalhes']:
                v = analise['detalhes']['vitoria']
                draw.text((50, 150), f"Favorito: {home if v['favorito']=='home' else away if v['favorito']=='away' else 'EMPATE'}", font=fonte, fill=(255, 193, 7))
                draw.text((50, 200), f"Confiança: {v['confianca_vitoria']:.1f}%", font=fonte, fill=(100, 255, 100))
            elif tipo_alerta == "gols_ht" and 'gols_ht' in analise['detalhes']:
                ht = analise['detalhes']['gols_ht']
                draw.text((50, 150), f"HT: {ht['tendencia_ht']}", font=fonte, fill=(100, 200, 255))
                draw.text((50, 200), f"Confiança: {ht['confianca_ht']:.1f}%", font=fonte, fill=(100, 255, 100))
            
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
        """Filtra jogos baseado no tipo de análise selecionado"""
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
            
            return jogos_filtrados
        
        elif tipo_analise == "Favorito (Vitória)":
            min_conf_vitoria = config.get("min_conf_vitoria", 65)
            filtro_favorito = config.get("filtro_favorito", "Todos")
            
            jogos_filtrados = [
                j for j in jogos
                if j.get("confianca_vitoria", 0) >= min_conf_vitoria and
                j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
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
                j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
            ]
            
            return jogos_filtrados
        
        return jogos
    
    def _enviar_top_jogos(self, jogos_filtrados, top_n, alerta_top_jogos, min_conf, max_conf, formato_top_jogos, data_busca, tipo_alerta="over_under"):
        """Envia os top jogos para o Telegram"""
        if not alerta_top_jogos:
            st.info("ℹ️ Alerta de Top Jogos desativado")
            return
        
        jogos_elegiveis = [j for j in jogos_filtrados if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
        
        # Aplicar filtro de confiança específico para o tipo de alerta
        if tipo_alerta == "over_under":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j["confianca"] <= max_conf]
        elif tipo_alerta == "favorito":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j.get("confianca_vitoria", 0) <= max_conf]
        elif tipo_alerta == "gols_ht":
            jogos_elegiveis = [j for j in jogos_elegiveis if min_conf <= j.get("confianca_ht", 0) <= max_conf]
        
        if not jogos_elegiveis:
            st.warning(f"⚠️ Nenhum jogo elegível para o Top Jogos.")
            return
        
        # Ordenar por métrica apropriada
        if tipo_alerta == "over_under":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x["confianca"], reverse=True)[:top_n]
        elif tipo_alerta == "favorito":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x.get("confianca_vitoria", 0), reverse=True)[:top_n]
        elif tipo_alerta == "gols_ht":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x.get("confianca_ht", 0), reverse=True)[:top_n]
        
        # Salvar alertas TOP
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
            if tipo_alerta == "over_under":
                msg = f"📢 TOP {top_n} Jogos Over/Under (confiança: {min_conf}%-{max_conf}%)\n\n"
            elif tipo_alerta == "favorito":
                msg = f"🏆 TOP {top_n} Jogos Favoritos (confiança: {min_conf}%+)\n\n"
            elif tipo_alerta == "gols_ht":
                msg = f"⏰ TOP {top_n} Jogos Gols HT (confiança: {min_conf}%+)\n\n"
            
            for idx, jogo in enumerate(top_jogos_sorted, 1):
                hora_format = jogo["hora"].strftime("%H:%M") if isinstance(jogo["hora"], datetime) else str(jogo["hora"])
                
                if tipo_alerta == "over_under":
                    tipo_emoji = "📈" if jogo['tipo_aposta'] == "over" else "📉"
                    msg += (
                        f"{idx}. {tipo_emoji} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   {jogo['tendencia']} | ⚽ {jogo['estimativa']:.2f} | "
                        f"🎯 {jogo['probabilidade']:.0f}% | 💯 {jogo['confianca']:.0f}%\n\n"
                    )
                elif tipo_alerta == "favorito":
                    favorito_emoji = "🏠" if jogo.get('favorito') == "home" else "✈️" if jogo.get('favorito') == "away" else "🤝"
                    favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                    msg += (
                        f"{idx}. {favorito_emoji} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   🏆 Favorito: {favorito_text} | "
                        f"💯 {jogo.get('confianca_vitoria', 0):.0f}%\n"
                        f"   📊 Casa: {jogo.get('prob_home_win', 0):.1f}% | "
                        f"Fora: {jogo.get('prob_away_win', 0):.1f}% | "
                        f"Empate: {jogo.get('prob_draw', 0):.1f}%\n\n"
                    )
                elif tipo_alerta == "gols_ht":
                    tipo_emoji_ht = "⚡" if "OVER" in jogo.get('tendencia_ht', '') else "🛡️"
                    msg += (
                        f"{idx}. {tipo_emoji_ht} <b>{jogo['home']} vs {jogo['away']}</b>\n"
                        f"   🕒 {hora_format} BRT | {jogo['liga']}\n"
                        f"   ⏰ {jogo.get('tendencia_ht', 'N/A')} | "
                        f"⚽ {jogo.get('estimativa_total_ht', 0):.2f} gols | "
                        f"💯 {jogo.get('confianca_ht', 0):.0f}%\n"
                        f"   🎯 OVER 0.5: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_05_ht', 0):.0f}% | "
                        f"OVER 1.5: {jogo.get('detalhes', {}).get('gols_ht', {}).get('over_15_ht', 0):.0f}%\n\n"
                    )
            
            if self.telegram_client.enviar_mensagem(msg, self.config.TELEGRAM_CHAT_ID_ALT2):
                st.success(f"📝 Texto dos TOP {len(top_jogos_sorted)} jogos enviado!")
        
        if formato_top_jogos in ["Poster", "Ambos"]:
            try:
                # Definir título baseado no tipo de alerta
                if tipo_alerta == "over_under":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS OVER/UNDER"
                elif tipo_alerta == "favorito":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS FAVORITOS"
                elif tipo_alerta == "gols_ht":
                    titulo = f"TOP {len(top_jogos_sorted)} JOGOS GOLS HT"
                
                poster = self.poster_generator.gerar_poster_westham_style(
                    top_jogos_sorted, 
                    titulo=titulo,
                    tipo_alerta=tipo_alerta
                )
                
                if tipo_alerta == "over_under":
                    caption = f"<b> TOP {len(top_jogos_sorted)} JOGOS OVER/UNDER </b>\n"
                    caption += f"<b> Intervalo de Confiança: {min_conf}% - {max_conf}%</b>\n\n"
                elif tipo_alerta == "favorito":
                    caption = f"<b> TOP {len(top_jogos_sorted)} JOGOS FAVORITOS 🏆</b>\n"
                    caption += f"<b> Confiança Mínima: {min_conf}%</b>\n\n"
                elif tipo_alerta == "gols_ht":
                    caption = f"<b> TOP {len(top_jogos_sorted)} JOGOS GOLS HT ⏰</b>\n"
                    caption += f"<b> Confiança Mínima: {min_conf}%</b>\n\n"
                
                caption += f"<b> ELITE MASTER SYSTEM - JOGOS COM MAIOR POTENCIAL</b>"
                
                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"🖼️ Poster dos TOP {len(top_jogos_sorted)} jogos enviado!")
            except Exception as e:
                logging.error(f"Erro ao gerar poster TOP jogos: {e}")
                st.error(f"❌ Erro ao gerar poster: {e}")
    
    def _salvar_alerta_top(self, alerta: Alerta):
        """Salva alerta TOP no arquivo"""
        alertas_top = DataStorage.carregar_alertas_top()
        chave = f"{alerta.jogo.id}_{alerta.data_busca}_{alerta.tipo_alerta}"
        alertas_top[chave] = alerta.to_dict()
        DataStorage.salvar_alertas_top(alertas_top)
    
    def _enviar_alerta_westham_style(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
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
                
                # Definir título baseado no tipo de análise
                if tipo_analise == "Over/Under de Gols":
                    titulo = f"ELITE MASTER - OVER/UNDER - {data_str}"
                    tipo_alerta = "over_under"
                elif tipo_analise == "Favorito (Vitória)":
                    titulo = f"ELITE MASTER - FAVORITOS - {data_str}"
                    tipo_alerta = "favorito"
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    titulo = f"ELITE MASTER - GOLS HT - {data_str}"
                    tipo_alerta = "gols_ht"
                
                st.info(f"🎨 Gerando poster para {data_str} com {len(jogos_data)} jogos...")
                
                poster = self.poster_generator.gerar_poster_westham_style(jogos_data, titulo=titulo, tipo_alerta=tipo_alerta)
                
                # Criar caption específica
                if tipo_analise == "Over/Under de Gols":
                    over_count = sum(1 for j in jogos_data if j.get('tipo_aposta') == "over")
                    under_count = sum(1 for j in jogos_data if j.get('tipo_aposta') == "under")
                    min_conf = config_analise.get("min_conf", 70)
                    max_conf = config_analise.get("max_conf", 95)
                    
                    caption = (
                        f"<b>🎯 ALERTA OVER/UNDER - {data_str}</b>\n\n"
                        f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                        f"<b>📈 Over: {over_count} jogos</b>\n"
                        f"<b>📉 Under: {under_count} jogos</b>\n"
                        f"<b>⚽ INTERVALO DE CONFIANÇA: {min_conf}% - {max_conf}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE PREDITIVA</b>"
                    )
                elif tipo_analise == "Favorito (Vitória)":
                    min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                    
                    caption = (
                        f"<b>🏆 ALERTA DE FAVORITOS - {data_str}</b>\n\n"
                        f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                        f"<b>🎯 CONFIANÇA MÍNIMA: {min_conf_vitoria}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE DE VITÓRIA</b>"
                    )
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    min_conf_ht = config_analise.get("min_conf_ht", 60)
                    tipo_ht = config_analise.get("tipo_ht", "OVER 0.5 HT")
                    
                    caption = (
                        f"<b>⏰ ALERTA DE GOLS HT - {data_str}</b>\n\n"
                        f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                        f"<b>🎯 TIPO: {tipo_ht}</b>\n"
                        f"<b>🔍 CONFIANÇA MÍNIMA: {min_conf_ht}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE DO PRIMEIRO TEMPO</b>"
                    )
                
                st.info("📤 Enviando para o Telegram...")
                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"🚀 Poster enviado para {data_str}!")
                else:
                    st.error(f"❌ Falha ao enviar poster para {data_str}")
                    
        except Exception as e:
            logging.error(f"Erro crítico ao gerar/enviar poster West Ham: {str(e)}")
            st.error(f"❌ Erro crítico ao gerar/enviar poster: {str(e)}")
            msg = f"🔥 Jogos encontrados (Erro na imagem):\n"
            for j in jogos_conf[:5]:
                if tipo_analise == "Over/Under de Gols":
                    tipo_emoji = "📈" if j.get('tipo_aposta') == "over" else "📉"
                    msg += f"{tipo_emoji} {j['home']} vs {j['away']} | {j['tendencia']} | Conf: {j['confianca']:.0f}%\n"
                elif tipo_analise == "Favorito (Vitória)":
                    favorito_emoji = "🏠" if j.get('favorito') == "home" else "✈️" if j.get('favorito') == "away" else "🤝"
                    msg += f"{favorito_emoji} {j['home']} vs {j['away']} | Favorito: {j['favorito']} | Conf: {j['confianca_vitoria']:.1f}%\n"
                elif tipo_analise == "Gols HT (Primeiro Tempo)":
                    tipo_emoji_ht = "⚡" if "OVER" in j.get('tendencia_ht', '') else "🛡️"
                    msg += f"{tipo_emoji_ht} {j['home']} vs {j['away']} | {j['tendencia_ht']} | Conf: {j['confianca_ht']:.0f}%\n"
            self.telegram_client.enviar_mensagem(msg)
    
    def _enviar_alerta_poster_original(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
        """Envia alerta com poster no estilo original"""
        if not jogos_conf:
            return
        
        try:
            if tipo_analise == "Over/Under de Gols":
                over_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "over"]
                under_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "under"]
                
                msg = f"🔥 Jogos Over/Under (Estilo Original):\n\n"
                
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
            
            elif tipo_analise == "Favorito (Vitória)":
                msg = f"🏆 Jogos Favoritos (Estilo Original):\n\n"
                
                for j in jogos_conf:
                    hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                    favorito_emoji = "🏠" if j.get('favorito') == "home" else "✈️" if j.get('favorito') == "away" else "🤝"
                    favorito_text = j['home'] if j.get('favorito') == "home" else j['away'] if j.get('favorito') == "away" else "EMPATE"
                    
                    msg += (
                        f"{favorito_emoji} {j['home']} vs {j['away']}\n"
                        f"🕒 {hora_format} BRT | {j['liga']}\n"
                        f"🏆 Favorito: {favorito_text} | 💯 {j.get('confianca_vitoria', 0):.1f}%\n"
                        f"📊 Casa: {j.get('prob_home_win', 0):.1f}% | "
                        f"Fora: {j.get('prob_away_win', 0):.1f}% | "
                        f"Empate: {j.get('prob_draw', 0):.1f}%\n\n"
                    )
            
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                msg = f"⏰ Jogos Gols HT (Estilo Original):\n\n"
                
                for j in jogos_conf:
                    hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                    tipo_emoji_ht = "⚡" if "OVER" in j.get('tendencia_ht', '') else "🛡️"
                    
                    msg += (
                        f"{tipo_emoji_ht} {j['home']} vs {j['away']}\n"
                        f"🕒 {hora_format} BRT | {j['liga']}\n"
                        f"⏰ {j.get('tendencia_ht', 'N/A')} | ⚽ {j.get('estimativa_total_ht', 0):.2f} gols | "
                        f"💯 {j.get('confianca_ht', 0):.0f}%\n"
                        f"🎯 OVER 0.5: {j.get('detalhes', {}).get('gols_ht', {}).get('over_05_ht', 0):.0f}% | "
                        f"OVER 1.5: {j.get('detalhes', {}).get('gols_ht', {}).get('over_15_ht', 0):.0f}%\n\n"
                    )
            
            self.telegram_client.enviar_mensagem(msg, self.config.TELEGRAM_CHAT_ID_ALT2)
            st.success("📤 Alerta enviado (formato texto)")
        except Exception as e:
            logging.error(f"Erro no envio de alerta original: {e}")
            st.error(f"Erro no envio: {e}")


# =============================
# CLASSE DE GERAÇÃO DE POSTERS (MANTIDA PARA COMPATIBILIDADE)
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
        ALTURA_TOPO = 350
        ALTURA_POR_JOGO = 1050
        PADDING = 120
        
        jogos_count = len(jogos)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)

        FONTE_TITULO = self.criar_fonte(95)
        FONTE_SUBTITULO = self.criar_fonte(70)
        FONTE_TIMES = self.criar_fonte(65)
        FONTE_VS = self.criar_fonte(55)
        FONTE_INFO = self.criar_fonte(50)
        FONTE_DETALHES = self.criar_fonte(55)
        FONTE_ANALISE = self.criar_fonte(65)
        FONTE_ESTATISTICAS = self.criar_fonte(40)

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
                cor_borda = (255, 87, 34)  # Laranja para favoritos
            elif tipo_alerta == "gols_ht":
                cor_borda = (76, 175, 80)  # Verde para HT
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

            TAMANHO_ESCUDO = 200
            TAMANHO_QUADRADO = 240
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
                    f"Estimativa: {jogo['estimativa']:.2f} gols",
                    f"Probabilidade: {jogo['probabilidade']:.0f}%",
                    f"Confiança: {jogo['confianca']:.0f}%",
                ]
                
                cores = [cor_tendencia, (100, 200, 255), (100, 255, 100), (255, 193, 7)]
                
            elif tipo_alerta == "favorito":
                favorito_emoji = "" if jogo.get('favorito') == "home" else "" if jogo.get('favorito') == "away" else "🤝"
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                
                textos_analise = [
                    f"{favorito_emoji} FAVORITO: {favorito_text}",
                    f"Prob. Casa: {jogo.get('prob_home_win', 0):.1f}%",
                    f"Prob. Fora: {jogo.get('prob_away_win', 0):.1f}%",
                    f"Prob. Empate: {jogo.get('prob_draw', 0):.1f}%",
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
            
            else:
                textos_analise = ["Informação não disponível"]
                cores = [(200, 200, 200)]
            
            for i, (text, cor) in enumerate(zip(textos_analise, cores)):
                try:
                    bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                    w = bbox[2] - bbox[0]
                    draw.text(((LARGURA - w) // 2, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)
                except:
                    draw.text((PADDING + 120, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)

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
        ALTURA_TOPO = 300
        ALTURA_POR_JOGO = 830  # Aumentei um pouco para acomodar o badge GREEN/RED
        PADDING = 120
        
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
        FONTE_RESULTADO_BADGE = self.criar_fonte(65)  # Fonte para o badge GREEN/RED

        # Título baseado no tipo de alerta
        if tipo_alerta == "over_under":
            titulo = " RESULTADOS OVER/UNDER"
        elif tipo_alerta == "favorito":
            titulo = " RESULTADOS FAVORITOS"
        elif tipo_alerta == "gols_ht":
            titulo = " RESULTADOS GOLS HT"
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
            else:
                resultado_text = "PENDENTE"
            
            # Cores baseadas no resultado
            if resultado_text == "GREEN":
                cor_badge = (46, 204, 113)  # Verde vibrante
                cor_borda = (46, 204, 113)
                cor_fundo = (30, 50, 40)  # Fundo verde escuro
                cor_texto = (255, 255, 255)
            elif resultado_text == "RED":
                cor_badge = (231, 76, 60)  # Vermelho vibrante
                cor_borda = (231, 76, 60)
                cor_fundo = (50, 30, 30)  # Fundo vermelho escuro
                cor_texto = (255, 255, 255)
            else:
                cor_badge = (149, 165, 166)  # Cinza
                cor_borda = (149, 165, 166)
                cor_fundo = (35, 35, 35)
                cor_texto = (255, 255, 255)
            
            # Retângulo principal do jogo
            draw.rectangle([x0, y0, x1, y1], fill=cor_fundo, outline=cor_borda, width=4)

            # ================= BADGE GREEN/RED =================
            # Posicionar o badge no canto superior ESQUERDO do retângulo do jogo
            badge_width = 250
            badge_height = 92
            badge_x = x0 + 50  # 50px da borda ESQUERDA
            badge_y = y0 + 50  # 50px do topo
            
            # Desenhar badge com cantos arredondados
            # Retângulo principal do badge
            draw.rectangle([badge_x, badge_y, badge_x + badge_width, badge_y + badge_height], 
                          fill=cor_badge, outline=cor_badge, width=2)
            
            # Texto do badge (GREEN ou RED)
            try:
                badge_bbox = draw.textbbox((0, 0), resultado_text, font=FONTE_RESULTADO_BADGE)
                badge_text_w = badge_bbox[2] - badge_bbox[0]
                badge_text_h = badge_bbox[3] - badge_bbox[1]
                badge_text_x = badge_x + (badge_width - badge_text_w) // 2
                badge_text_y = badge_y + (badge_height - badge_text_h) // 2
                
                # Sombra para destaque
                draw.text((badge_text_x + 2, badge_text_y + 2), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=(0, 0, 0, 128))
                
                # Texto principal
                draw.text((badge_text_x, badge_text_y), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=cor_texto)
                
                # Contorno branco sutil
                draw.rectangle([badge_x-2, badge_y-2, badge_x + badge_width + 2, badge_y + badge_height + 2], 
                              outline=(255, 255, 255), width=1)
                
            except:
                # Fallback se houver erro na fonte
                draw.text((badge_x + 80, badge_y + 25), resultado_text, 
                         font=FONTE_RESULTADO_BADGE, fill=cor_texto)
            # ================= FIM DO BADGE =================

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

            # Nomes dos times
            home_text = jogo['home'][:12]  # Limitar a 12 caracteres
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
                favorito_emoji = "" if jogo.get('favorito') == "home" else "" if jogo.get('favorito') == "away" else ""
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
            # Desenhar placeholder com as iniciais do time
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
                # Imagem mais larga que alta
                nova_altura = tamanho_escudo
                nova_largura = int(tamanho_escudo * proporcao)
                if nova_largura > tamanho_escudo:
                    # Redimensionar mantendo proporção
                    nova_largura = tamanho_escudo
                    nova_altura = int(tamanho_escudo / proporcao)
            else:
                # Imagem mais alta que larga
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
            # Fallback: desenhar placeholder
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
# INTERFACE STREAMLIT (ATUALIZADA COM NOVAS FUNCIONALIDADES)
# =============================

def main():
    st.set_page_config(page_title="⚽ Sistema Completo de Alertas", layout="wide")
    st.title("⚽ Sistema Completo de Alertas de Futebol")
    
    # Inicializar sistema (Singleton)
    sistema = SistemaAlertasFutebol()
    
    # Verificar configuração
    st.sidebar.header("🔧 Configuração")
    if st.sidebar.button("🔄 Validar Configuração"):
        faltantes = sistema.validar_configuracao()
        if faltantes:
            st.sidebar.error(f"❌ Configurações faltando: {', '.join(faltantes)}")
            st.sidebar.info("ℹ️ Crie um arquivo .env com as seguintes variáveis:")
            st.sidebar.code("""
FOOTBALL_API_KEY=sua_chave_aqui
TELEGRAM_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
TELEGRAM_CHAT_ID_ALT2=outro_chat_id_aqui
ODDS_API_KEY=sua_chave_odds_aqui
            """)
        else:
            st.sidebar.success("✅ Todas as configurações estão presentes!")
            
            # Testar conexões
            if st.sidebar.button("🔍 Testar Conexões"):
                resultados = sistema.testar_conexoes()
                for api, status in resultados.items():
                    if status:
                        st.sidebar.success(f"✅ {api}: Conectado")
                    else:
                        st.sidebar.error(f"❌ {api}: Falha na conexão")
    
    # Sidebar principal
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        
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
        
        st.subheader("📨 Tipos de Envio")
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True)
        alerta_poster = st.checkbox("📊 Alertas com Poster", value=True)
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True)
        alerta_conferencia_auto = st.checkbox("🤖 Alerta Auto Conferência", value=True)
        alerta_resultados = st.checkbox("🏁 Alertas de Resultados", value=True)
        
        # NOVA OPÇÃO: Usar novo sistema de alertas
        usar_novo_sistema = st.checkbox("🆕 Usar Novo Sistema de Alertas", value=True)
        
        formato_top_jogos = st.selectbox(
            "📋 Formato do Top Jogos",
            ["Ambos", "Texto", "Poster"],
            index=0
        )
        
        st.markdown("----")
        st.header("💰 Configuração de Odds")
        
        usar_odds_api = st.checkbox("🔓 Usar API de Odds", value=False)
        
        if usar_odds_api:
            st.info("ℹ️ API de Odds ativada")
            # Botão para testar conexão
            if st.button("🔍 Testar Conexão Odds API", type="secondary"):
                if sistema.odds_client.testar_conexao():
                    st.success("✅ Conexão com Odds API OK!")
                else:
                    st.error("❌ Falha na conexão. Verifique sua API Key.")
        else:
            st.warning("⚠️ API de Odds desativada - Configure sua chave no arquivo .env")
        
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
        
        st.info(f"Formato Top Jogos: {formato_top_jogos}")
        if alerta_conferencia_auto:
            st.info("🤖 Alerta automático: ATIVADO")
        if alerta_resultados:
            st.info("🏁 Alertas de resultados: ATIVADO")
        if usar_novo_sistema:
            st.success("🆕 Novo Sistema de Alertas: ATIVADO")
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar Partidas", "📊 Conferir Resultados", "💰 Odds", "🆕 Novo Sistema"])
    
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
                sistema.processar_jogos(data_selecionada, ligas_selecionadas, todas_ligas, top_n, 
                                      config_analise.get("min_conf", 70), 
                                      config_analise.get("max_conf", 95), 
                                      estilo_poster, 
                                      alerta_individual, alerta_poster, alerta_top_jogos, 
                                      formato_top_jogos, tipo_filtro_passar, tipo_analise, config_analise)
    
    with tab2:
        st.subheader("📊 Conferência de Resultados")
        
        col_data, col_btn = st.columns([2, 1])
        with col_data:
            data_resultados = st.date_input("📅 Data para conferência:", value=datetime.today(), key="data_resultados")
        
        with col_btn:
            if st.button("🔄 Conferir Resultados", type="primary", key="btn_conferir"):
                sistema.conferir_resultados(data_resultados)
        
        # Mostrar estatísticas rápidas
        st.markdown("---")
        st.subheader("📈 Estatísticas dos Alertas")
        
        col_ou, col_fav, col_ht = st.columns(3)
        
        with col_ou:
            alertas_ou = DataStorage.carregar_alertas()
            resultados_ou = DataStorage.carregar_resultados()
            
            total_alertas_ou = len(alertas_ou)
            conferidos_ou = sum(1 for a in alertas_ou.values() if a.get("conferido", False))
            greens_ou = sum(1 for r in resultados_ou.values() if r.get("resultado") == "GREEN")
            reds_ou = sum(1 for r in resultados_ou.values() if r.get("resultado") == "RED")
            
            st.metric("⚽ Over/Under", f"{total_alertas_ou} alertas", f"{conferidos_ou} conferidos")
            if greens_ou + reds_ou > 0:
                taxa_ou = (greens_ou / (greens_ou + reds_ou)) * 100
                st.write(f"✅ {greens_ou} | ❌ {reds_ou} | 📊 {taxa_ou:.1f}%")
        
        with col_fav:
            alertas_fav = DataStorage.carregar_alertas_favoritos()
            resultados_fav = DataStorage.carregar_resultados_favoritos()
            
            total_alertas_fav = len(alertas_fav)
            conferidos_fav = sum(1 for a in alertas_fav.values() if a.get("conferido", False))
            greens_fav = sum(1 for r in resultados_fav.values() if r.get("resultado_favorito") == "GREEN")
            reds_fav = sum(1 for r in resultados_fav.values() if r.get("resultado_favorito") == "RED")
            
            st.metric("🏆 Favoritos", f"{total_alertas_fav} alertas", f"{conferidos_fav} conferidos")
            if greens_fav + reds_fav > 0:
                taxa_fav = (greens_fav / (greens_fav + reds_fav)) * 100
                st.write(f"✅ {greens_fav} | ❌ {reds_fav} | 📊 {taxa_fav:.1f}%")
        
        with col_ht:
            alertas_ht = DataStorage.carregar_alertas_gols_ht()
            resultados_ht = DataStorage.carregar_resultados_gols_ht()
            
            total_alertas_ht = len(alertas_ht)
            conferidos_ht = sum(1 for a in alertas_ht.values() if a.get("conferido", False))
            greens_ht = sum(1 for r in resultados_ht.values() if r.get("resultado_ht") == "GREEN")
            reds_ht = sum(1 for r in resultados_ht.values() if r.get("resultado_ht") == "RED")
            
            st.metric("⏰ Gols HT", f"{total_alertas_ht} alertas", f"{conferidos_ht} conferidos")
            if greens_ht + reds_ht > 0:
                taxa_ht = (greens_ht / (greens_ht + reds_ht)) * 100
                st.write(f"✅ {greens_ht} | ❌ {reds_ht} | 📊 {taxa_ht:.1f}%")
    
    with tab3:  # ABA DE ODDS ATUALIZADA
        st.header("💰 Análise de Odds e Valor")
        
        # Informações importantes
        with st.expander("⚠️ Importante: Limitações da Odds API"):
            st.write("""
            **A Odds API tem as seguintes limitações:**
            
            1. **Não busca por ID único** - Só busca por data/liga
            2. **Quota limitada** - Cerca de 500 requests/mês no plano gratuito
            3. **Esportes específicos** - Use mapeamento correto das ligas
            
            **Solução implementada:**
            - Busca por data e liga
            - Filtra jogos pelo nome dos times
            - Cache inteligente para economizar quota
            """)
        
        col1_odds, col2_odds = st.columns([2, 1])
        
        with col1_odds:
            data_odds = st.date_input("📅 Data para análise de odds:", value=datetime.today(), key="data_odds")
        
        with col2_odds:
            todas_ligas_odds = st.checkbox("🌍 Todas as ligas", value=False, key="todas_ligas_odds")
        
        if not todas_ligas_odds:
            ligas_odds = st.multiselect(
                "📌 Selecionar ligas para odds:",
                options=list(ConfigManager.LIGA_DICT.keys()),
                default=["Premier League (Inglaterra)"],
                key="ligas_odds"
            )
        else:
            ligas_odds = []
        
        # Modo de busca
        modo_busca = st.radio(
            "🔍 Modo de busca:",
            ["Automático (recomendado)", "Apenas com análise", "Apenas odds diretas"],
            index=0,
            help="Automático combina ambas as abordagens para melhores resultados"
        )
        
        col_formato, col_filtro = st.columns(2)
        
        with col_formato:
            formato_saida = st.selectbox(
                "📋 Formato de Saída:",
                ["tabela", "relatorio", "valor"],
                format_func=lambda x: {
                    "tabela": "📊 Tabela Completa",
                    "relatorio": "📄 Relatório HTML",
                    "valor": "🎯 Apenas com Valor"
                }[x],
                key="formato_odds"
            )
        
        with col_filtro:
            mercados_filtro = st.multiselect(
                "🎯 Filtrar Mercados:",
                ["Casa", "Fora", "Empate", "Over 2.5", "Under 2.5"],
                default=["Casa", "Fora", "Empate"],
                key="filtro_mercados"
            )
        
        # Botão para testar conexão
        if st.button("🔍 Testar Conexão com Odds API", type="secondary", key="btn_testar_odds"):
            with st.spinner("Testando conexão..."):
                if sistema.odds_client.testar_conexao():
                    # Mostrar estatísticas da API
                    esportes = sistema.odds_client.obter_esportes_disponiveis()
                    st.success(f"✅ Conexão OK! {len(esportes)} esportes disponíveis")
                    
                    # Mostrar esportes de futebol disponíveis
                    if esportes:
                        st.write("**⚽ Esportes de futebol disponíveis:**")
                        for esporte in esportes[:10]:  # Limitar a 10
                            st.write(f"- {esporte.get('title')} (`{esporte.get('key')}`)")
                else:
                    st.error("❌ Falha na conexão. Verifique sua API Key.")
        
        # Botão principal
        if st.button("💰 Buscar Odds e Analisar Valor", type="primary", key="btn_buscar_odds"):
            if not todas_ligas_odds and not ligas_odds:
                st.error("❌ Selecione pelo menos uma liga")
            else:
                with st.spinner("🔍 Buscando odds e analisando valor..."):
                    # Escolher o modo de busca baseado na seleção do usuário
                    if modo_busca == "Apenas com análise":
                        resultados = sistema.odds_manager.buscar_odds_com_analise(
                            data_odds, ligas_odds, todas_ligas_odds
                        )
                    elif modo_busca == "Apenas odds diretas":
                        resultados = sistema.odds_manager.buscar_odds_direto_api(
                            data_odds, ligas_odds, todas_ligas_odds
                        )
                    else:  # Automático (recomendado)
                        resultados = sistema.buscar_odds_com_analise(
                            data_odds, ligas_odds, todas_ligas_odds, formato_saida
                        )
        
        # Seção de estatísticas de odds
        st.markdown("---")
        st.subheader("📈 Estatísticas de Valor")
        
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        
        with col_stats1:
            st.metric("🎯 Edge Médio", "2.5%", "+0.3%")
        
        with col_stats2:
            st.metric("💰 Odds com Valor", "42%", "+5%")
        
        with col_stats3:
            st.metric("📊 Kelly Médio", "3.2%", "-0.1%")
        
        # Dicas rápidas
        with st.expander("💡 Dicas de Análise de Valor"):
            st.write("""
            **📊 Como interpretar as métricas:**
            
            **🎯 Edge (Vantagem):**
            - **> 5%**: Alto valor 🟢
            - **2% - 5%**: Valor moderado 🟡
            - **0% - 2%**: Pequeno valor 🟠
            - **< 0%**: Sem valor 🔴
            
            **💰 Kelly Criterion:**
            - **0%**: Não apostar
            - **1-5%**: Aposta pequena
            - **5-10%**: Aposta moderada
            - **> 10%**: Aposta grande
            
            **📈 Probabilidade Implícita:**
            - Calculada como 1 / odds
            - Comparar com nossa probabilidade estimada
            """)
    
    with tab4:  # NOVA ABA: NOVO SISTEMA
        st.header("🆕 Novo Sistema de Alertas Inteligentes")
        
        st.info("""
        **✨ Funcionalidades do Novo Sistema:**
        
        1. **🎯 Avaliação de Qualidade** - Classifica alertas em A, B, C ou DESCARTAR
        2. **📈 Cálculo de EV (Expected Value)** - Analisa o valor esperado das apostas
        3. **🏆 Ranking Top 3** - Seleciona automaticamente os melhores alertas do dia
        4. **⚡ Notificações Inteligentes** - Envia apenas alertas de qualidade A
        5. **📊 Score Composto** - Combina probabilidade, confiança e EV
        """)
        
        # Estatísticas do novo sistema
        st.markdown("---")
        st.subheader("📊 Estatísticas do Novo Sistema")
        
        stats = sistema.motor_alertas.get_stats()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Alertas Processados", stats["alertas_processados"])
        with col2:
            st.metric("Qualidade A", stats["alertas_qualidade_A"])
        with col3:
            st.metric("Taxa Qualidade A", stats["taxa_qualidade_A"])
        
        # Controles do novo sistema
        st.markdown("---")
        st.subheader("🎮 Controles do Novo Sistema")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔄 Processar Odds com Novo Sistema", type="primary"):
                with st.spinner("Processando odds com novo sistema..."):
                    alertas = sistema.processar_odds_com_novo_sistema(
                        datetime.today(), [], True
                    )
                    
                    if alertas:
                        st.success(f"✅ {len(alertas)} alertas processados com novo sistema!")
        
        with col_btn2:
            if st.button("🏆 Enviar Top 3 do Dia", type="secondary"):
                enviados = sistema.motor_alertas.enviar_top3_diario()
                st.success(f"✅ Top {enviados} alertas enviados!")
        
        # Visualizar top 3 atual
        st.markdown("---")
        st.subheader("👑 Top 3 Alertas do Dia")
        
        top3 = sistema.ranking.gerar_top3()
        
        if top3:
            for i, alerta in enumerate(top3, 1):
                with st.expander(f"🏆 #{i} - {alerta.mercado}"):
                    if hasattr(alerta.jogo, 'home_team'):
                        jogo_text = f"{alerta.jogo.home_team} vs {alerta.jogo.away_team}"
                    else:
                        jogo_text = str(alerta.jogo)
                    
                    col_info1, col_info2 = st.columns(2)
                    
                    with col_info1:
                        st.write(f"**🎯 Jogo:** {jogo_text}")
                        st.write(f"**📌 Mercado:** {alerta.mercado}")
                        st.write(f"**💰 Odd:** {alerta.odd:.2f}")
                    
                    with col_info2:
                        st.write(f"**📊 Score:** {alerta.score:.1f}")
                        st.write(f"**📈 EV:** {alerta.ev:.3f}")
                        st.write(f"**🎯 Probabilidade:** {int(alerta.probabilidade*100)}%")
                        st.write(f"**🔍 Confiança:** {alerta.confianca:.1f}%")
                        st.write(f"**🟢 Qualidade:** {alerta.qualidade}")
        else:
            st.info("ℹ️ Nenhum alerta no top 3 hoje.")
        
        # Configurações do novo sistema
        st.markdown("---")
        st.subheader("⚙️ Configurações do Novo Sistema")
        
        col_set1, col_set2 = st.columns(2)
        
        with col_set1:
            somente_top3 = st.checkbox("📨 Enviar apenas Top 3", value=False)
            if somente_top3:
                sistema.gerenciador_notificacoes.somente_top3 = True
                st.success("✅ Configurado para enviar apenas Top 3")
        
        with col_set2:
            if st.button("🗑️ Limpar Ranking", type="secondary"):
                sistema.ranking.alertas_por_dia.clear()
                sistema.ranking.salvar_ranking()
                st.success("✅ Ranking limpo!")
    
    # Painel de monitoramento
    st.markdown("---")
    st.subheader("📊 Monitoramento do Sistema")
    
    col_mon1, col_mon2, col_mon3, col_mon4 = st.columns(4)
    
    stats_api = sistema.api_monitor.get_stats()
    cache_stats = sistema.image_cache.get_stats()
    
    with col_mon1:
        st.metric("Total Requests", stats_api["total_requests"])
    with col_mon2:
        st.metric("Taxa de Sucesso", f"{stats_api['success_rate']}%")
    with col_mon3:
        st.metric("Cache Hit Rate", cache_stats["hit_rate"])
    with col_mon4:
        st.metric("Cache Disco", f"{cache_stats['disco_mb']} MB")


if __name__ == "__main__":
    main()
