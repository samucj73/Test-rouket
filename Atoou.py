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
# Cache de Imagens (Escudos)
# =============================
class ImageCache:
    """Cache especializado para imagens (escudos dos times)"""
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.max_size = 200
        self.ttl = 86400 * 7  # 7 dias
        self.lock = threading.Lock()
        self.cache_dir = "escudos_cache"
        
        # Criar diretório de cache se não existir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
    
    def get(self, team_name: str, crest_url: str) -> bytes | None:
        """Obtém escudo do cache"""
        key = self._generate_key(team_name, crest_url)
        
        with self.lock:
            # Verificar cache em memória
            if key in self.cache:
                if time.time() - self.timestamps[key] <= self.ttl:
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.timestamps[key]
            
            # Verificar cache em disco
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
            # Limpar cache se necessário
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.timestamps.items(), key=lambda x: x[1])[0]
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
                
                # Remover do disco também
                old_file = os.path.join(self.cache_dir, f"{oldest_key}.png")
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass
            
            # Armazenar em memória
            self.cache[key] = img_bytes
            self.timestamps[key] = time.time()
            
            # Armazenar em disco
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
            # Limpar diretório de cache
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

# Instância global do cache de imagens
escudos_cache = ImageCache()

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

# NOVA FUNÇÃO: Carregar alertas TOP
def carregar_alertas_top() -> dict:
    """Carrega os alertas TOP que foram gerados"""
    return carregar_json(ALERTAS_TOP_PATH)

# NOVA FUNÇÃO: Salvar alertas TOP
def salvar_alertas_top(alertas_top: dict):
    """Salva os alertas TOP para conferência posterior"""
    salvar_json(ALERTAS_TOP_PATH, alertas_top)

# NOVA FUNÇÃO: Adicionar alerta TOP
def adicionar_alerta_top(jogo: dict, data_busca: str):
    """Adiciona um jogo aos alertas TOP salvos"""
    alertas_top = carregar_alertas_top()
    
    # Criar chave única
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
        "alerta_enviado": False  # NOVO: Flag para controlar se alerta foi enviado
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
# NOVA FUNÇÃO: Enviar alerta quando todos os Top N foram conferidos
# =============================
def enviar_alerta_top_conferidos():
    """Envia alerta quando todos os jogos do Top N foram conferidos"""
    alertas_top = carregar_alertas_top()
    if not alertas_top:
        return False
    
    # Separar alertas por data de busca
    alertas_por_data = {}
    for chave, alerta in alertas_top.items():
        data_busca = alerta.get("data_busca")
        if data_busca not in alertas_por_data:
            alertas_por_data[data_busca] = []
        alertas_por_data[data_busca].append(alerta)
    
    alertas_enviados = []
    
    for data_busca, alertas in alertas_por_data.items():
        # Verificar se todos os alertas desta data foram conferidos
        todos_conferidos = all(a.get("conferido", False) for a in alertas)
        ja_enviado = any(a.get("alerta_enviado", False) for a in alertas)
        
        if todos_conferidos and not ja_enviado and len(alertas) > 0:
            # Calcular estatísticas
            total_alertas = len(alertas)
            green_count = sum(1 for a in alertas if a.get("resultado") == "GREEN")
            red_count = total_alertas - green_count
            taxa_acerto = (green_count / total_alertas * 100) if total_alertas > 0 else 0
            
            # Separar Over e Under
            over_alertas = [a for a in alertas if a.get("tipo_aposta") == "over"]
            under_alertas = [a for a in alertas if a.get("tipo_aposta") == "under"]
            
            over_green = sum(1 for a in over_alertas if a.get("resultado") == "GREEN")
            under_green = sum(1 for a in under_alertas if a.get("resultado") == "GREEN")
            
            # Criar mensagem
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
            
            # Adicionar detalhes dos jogos
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
            
            # Enviar para Telegram
            if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2):
                # Marcar como alerta enviado
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
        # Pular se já foi conferido
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
            
            # Verificar se jogo terminou e tem resultado válido
            if (status == "FINISHED" and 
                home_goals is not None and 
                away_goals is not None):
                
                # Calcular resultado (GREEN/RED)
                total_gols = home_goals + away_goals
                previsao_correta = False
                
                # Verificar para Over 2.5
                if alerta["tendencia"] == "OVER 2.5" and total_gols > 2.5:
                    previsao_correta = True
                # Verificar para Under 2.5
                elif alerta["tendencia"] == "UNDER 2.5" and total_gols < 2.5:
                    previsao_correta = True
                # Verificar para Over 1.5
                elif alerta["tendencia"] == "OVER 1.5" and total_gols > 1.5:
                    previsao_correta = True
                # Verificar para Under 1.5
                elif alerta["tendencia"] == "UNDER 1.5" and total_gols < 1.5:
                    previsao_correta = True
                
                # Atualizar alerta
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
        
        # Mostrar estatísticas
        calcular_desempenho_alertas_top()
        
        # Mostrar detalhes dos jogos conferidos
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
        
    # Filtrar apenas os que foram conferidos
    alertas_conferidos = [a for a in alertas_top.values() if a.get("conferido", False)]
    
    if not alertas_conferidos:
        st.info("ℹ️ Nenhum alerta TOP conferido ainda.")
        return
        
    total_alertas = len(alertas_conferidos)
    green_count = sum(1 for a in alertas_conferidos if a.get("resultado") == "GREEN")
    red_count = total_alertas - green_count
    taxa_acerto = (green_count / total_alertas * 100) if total_alertas > 0 else 0
    
    # Separar Over e Under
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
    
    # Agrupar por data de busca
    datas_completas = []
    alertas_por_data = {}
    
    for chave, alerta in alertas_top.items():
        data_busca = alerta.get("data_busca")
        if data_busca not in alertas_por_data:
            alertas_por_data[data_busca] = []
        alertas_por_data[data_busca].append(alerta)
    
    for data_busca, alertas in alertas_por_data.items():
        # Verificar se todos foram conferidos mas alerta ainda não foi enviado
        todos_conferidos = all(a.get("conferido", False) for a in alertas)
        ja_enviado = any(a.get("alerta_enviado", False) for a in alertas)
        
        if todos_conferidos and not ja_enviado:
            datas_completas.append(data_busca)
    
    return datas_completas

# =============================
# NOVAS FUNÇÕES DE ANÁLISE DE VITÓRIA E GOLS HT
# =============================

def calcular_probabilidade_vitoria(home: str, away: str, classificacao: dict) -> dict:
    """Calcula probabilidade de vitória, empate e derrota"""
    dados_home = classificacao.get(home, {"wins": 0, "draws": 0, "losses": 0, "played": 1, "scored": 0, "against": 0})
    dados_away = classificacao.get(away, {"wins": 0, "draws": 0, "losses": 0, "played": 1, "scored": 0, "against": 0})
    
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)
    
    # Estatísticas básicas
    win_rate_home = dados_home["wins"] / played_home
    win_rate_away = dados_away["wins"] / played_away
    draw_rate_home = dados_home["draws"] / played_home
    draw_rate_away = dados_away["draws"] / played_away
    
    # Fator casa/fora
    fator_casa = 1.2  # Time da casa tem vantagem
    fator_fora = 0.8  # Time visitante tem desvantagem
    
    # Cálculo base
    prob_home = (win_rate_home * fator_casa + (1 - win_rate_away) * fator_fora) / 2 * 100
    prob_away = (win_rate_away * fator_fora + (1 - win_rate_home) * fator_casa) / 2 * 100
    prob_draw = ((draw_rate_home + draw_rate_away) / 2) * 100
    
    # Considerar diferença de gols
    media_gols_home = dados_home["scored"] / played_home
    media_gols_against_home = dados_home["against"] / played_home
    media_gols_away = dados_away["scored"] / played_away
    media_gols_against_away = dados_away["against"] / played_away
    
    # Ajustar com base na força ofensiva/defensiva
    forca_home = (media_gols_home - media_gols_against_home) * 5
    forca_away = (media_gols_away - media_gols_against_away) * 5
    
    prob_home += forca_home
    prob_away += forca_away
    
    # Normalizar para somar 100%
    total = prob_home + prob_away + prob_draw
    if total > 0:
        prob_home = (prob_home / total) * 100
        prob_away = (prob_away / total) * 100
        prob_draw = (prob_draw / total) * 100
    
    # Garantir limites
    prob_home = max(1, min(99, prob_home))
    prob_away = max(1, min(99, prob_away))
    prob_draw = max(1, min(99, prob_draw))
    
    # Determinar favorito
    if prob_home > prob_away and prob_home > prob_draw:
        favorito = "home"
    elif prob_away > prob_home and prob_away > prob_draw:
        favorito = "away"
    else:
        favorito = "draw"
    
    return {
        "home_win": round(prob_home, 1),
        "away_win": round(prob_away, 1),
        "draw": round(prob_draw, 1),
        "favorito": favorito,
        "confianca_vitoria": round(max(prob_home, prob_away, prob_draw), 1)
    }

def calcular_probabilidade_gols_ht(home: str, away: str, classificacao: dict) -> dict:
    """Calcula probabilidade de gols no primeiro tempo (HT)"""
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
    
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)
    
    # Estatísticas básicas
    media_gols_home = dados_home["scored"] / played_home
    media_gols_away = dados_away["scored"] / played_away
    media_gols_against_home = dados_home["against"] / played_home
    media_gols_against_away = dados_away["against"] / played_away
    
    # Estimativa de gols no primeiro tempo (aproximadamente 45% dos gols totais)
    fator_ht = 0.45
    
    estimativa_home_ht = (media_gols_home * fator_ht)
    estimativa_away_ht = (media_gols_away * fator_ht)
    estimativa_total_ht = estimativa_home_ht + estimativa_away_ht
    
    # Probabilidades de gols HT
    prob_over_05_ht = min(95, max(5, (estimativa_total_ht / 0.5) * 30))
    prob_over_15_ht = min(90, max(5, (estimativa_total_ht / 1.5) * 40))
    prob_btts_ht = min(85, max(5, ((media_gols_home * media_gols_away) * 60)))
    
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
        "btts_ht": round(prob_btts_ht, 1),
        "home_gols_ht": round(estimativa_home_ht, 2),
        "away_gols_ht": round(estimativa_away_ht, 2)
    }

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
# Funções de Download com Cache
# =============================
def baixar_escudo_com_cache(team_name: str, crest_url: str) -> Image.Image | None:
    """Baixa escudo com cache robusto - VERSÃO OTIMIZADA"""
    if not crest_url or crest_url == "":
        logging.warning(f"URL vazia para {team_name}")
        return None
    
    try:
        # Tentar cache primeiro
        cached_img = escudos_cache.get(team_name, crest_url)
        if cached_img:
            logging.info(f"🎨 Escudo de {team_name} obtido do cache")
            return Image.open(io.BytesIO(cached_img)).convert("RGBA")
        
        # Baixar da internet
        response = requests.get(crest_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Verificar se é imagem
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            logging.warning(f"URL não é imagem para {team_name}: {content_type}")
            return None
        
        img_bytes = response.content
        
        # Armazenar no cache
        escudos_cache.set(team_name, crest_url, img_bytes)
        
        # Converter para objeto Image
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
    """Tenta baixar uma imagem - VERSÃO CORRIGIDA (com fallback para cache)"""
    if not url or url == "":
        return None
    
    # Extrair nome do time da URL (se possível) para usar no cache
    team_name = url.split('/')[-1].replace('.png', '').replace('.svg', '')
    
    # Usar cache se disponível
    cached_img = escudos_cache.get(team_name, url)
    if cached_img:
        return Image.open(io.BytesIO(cached_img)).convert("RGBA")
        
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        
        # Verificar se é realmente uma imagem
        content_type = resp.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logging.warning(f"URL não é uma imagem: {content_type}")
            return None
            
        img_bytes = resp.content
        
        # Armazenar no cache
        escudos_cache.set(team_name, url, img_bytes)
        
        img = Image.open(io.BytesIO(img_bytes))
        return img.convert("RGBA")
        
    except Exception as e:
        logging.error(f"Erro ao baixar imagem {url}: {e}")
        return None

# =============================
# Lógica de Análise e Alertas - VERSÃO ATUALIZADA COM NOVAS ANÁLISES
# =============================
def calcular_tendencia_completa(home: str, away: str, classificacao: dict) -> dict:
    """Calcula tendências completas com análise multivariada - VERSÃO ATUALIZADA COM VITÓRIA E HT"""
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
    # ADICIONAR ANÁLISES DE VITÓRIA E GOLS HT
    # ============================================================
    
    # Calcular probabilidade de vitória
    vitoria_analise = calcular_probabilidade_vitoria(home, away, classificacao)
    
    # Calcular probabilidade de gols HT
    ht_analise = calcular_probabilidade_gols_ht(home, away, classificacao)
    
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
        
        # Análise de vitória
        "vitoria": vitoria_analise,
        
        # Análise de gols HT
        "gols_ht": ht_analise,
        
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
        f"ANÁLISE COMPLETA: {home} vs {away} | "
        f"Est: {estimativa_total_ajustada:.2f} | "
        f"Tend: {tendencia_principal} | "
        f"Prob: {probabilidade_final:.1f}% | "
        f"Conf: {confianca_final:.1f}% | "
        f"Vitória: {vitoria_analise['favorito']} ({vitoria_analise['confianca_vitoria']:.1f}%) | "
        f"HT: {ht_analise['tendencia_ht']} ({ht_analise['confianca_ht']:.1f}%)"
    )
    
    return {
        "tendencia": tendencia_principal,
        "estimativa": round(estimativa_total_ajustada, 2),
        "probabilidade": probabilidade_final,
        "confianca": confianca_final,
        "tipo_aposta": tipo_aposta,
        "detalhes": detalhes
    }

# =============================
# NOVAS FUNÇÕES: Processamento específico por tipo de análise
# =============================

def filtrar_por_tipo_analise(jogos, tipo_analise, config):
    """Filtra jogos baseado no tipo de análise selecionado"""
    jogos_filtrados = []
    
    if tipo_analise == "Over/Under de Gols":
        min_conf = config.get("min_conf", 70)
        max_conf = config.get("max_conf", 95)
        tipo_filtro = config.get("tipo_filtro", "Todos")
        
        # Filtrar por intervalo de confiança e tipo
        jogos_filtrados = [
            j for j in jogos
            if min_conf <= j["confianca"] <= max_conf and 
            j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
        ]
        
        # Aplicar filtro por tipo
        if tipo_filtro == "Apenas Over":
            jogos_filtrados = [j for j in jogos_filtrados if j["tipo_aposta"] == "over"]
        elif tipo_filtro == "Apenas Under":
            jogos_filtrados = [j for j in jogos_filtrados if j["tipo_aposta"] == "under"]
    
    elif tipo_analise == "Favorito (Vitória)":
        min_conf_vitoria = config.get("min_conf_vitoria", 65)
        filtro_favorito = config.get("filtro_favorito", "Todos")
        
        for jogo in jogos:
            if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
                vitoria_data = jogo['detalhes']['vitoria']
                confianca_vitoria = vitoria_data['confianca_vitoria']
                favorito = vitoria_data['favorito']
                
                # Verificar confiança mínima
                if confianca_vitoria >= min_conf_vitoria:
                    # Aplicar filtro de favorito
                    if (filtro_favorito == "Todos" or
                        (filtro_favorito == "Casa" and favorito == "home") or
                        (filtro_favorito == "Fora" and favorito == "away") or
                        (filtro_favorito == "Empate" and favorito == "draw")):
                        
                        # Adicionar informações específicas de favorito
                        jogo['tipo_alerta'] = 'favorito'
                        jogo['confianca_vitoria'] = confianca_vitoria
                        jogo['favorito'] = favorito
                        jogo['prob_vitoria'] = vitoria_data[f'{favorito}_win'] if favorito != 'draw' else vitoria_data['draw']
                        
                        jogos_filtrados.append(jogo)
    
    elif tipo_analise == "Gols HT (Primeiro Tempo)":
        min_conf_ht = config.get("min_conf_ht", 60)
        tipo_ht = config.get("tipo_ht", "OVER 0.5 HT")
        
        for jogo in jogos:
            if 'detalhes' in jogo and 'gols_ht' in jogo['detalhes']:
                ht_data = jogo['detalhes']['gols_ht']
                confianca_ht = ht_data['confianca_ht']
                tendencia_ht = ht_data['tendencia_ht']
                
                # Verificar se a tendência HT corresponde ao tipo selecionado
                if (confianca_ht >= min_conf_ht and 
                    (tipo_ht == "Todos" or tendencia_ht == tipo_ht)):
                    
                    # Adicionar informações específicas de HT
                    jogo['tipo_alerta'] = 'ht'
                    jogo['confianca_ht'] = confianca_ht
                    jogo['tendencia_ht'] = tendencia_ht
                    jogo['estimativa_ht'] = ht_data['estimativa_total_ht']
                    
                    jogos_filtrados.append(jogo)
    
    return jogos_filtrados

# =============================
# Funções de criação de fontes
# =============================
def criar_fonte(tamanho: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Tenta criar uma fonte, fallback para padrão se falhar"""
    try:
        # Tenta carregar fonte do sistema
        return ImageFont.truetype("arial.ttf", tamanho)
    except:
        try:
            # Tenta fonte alternativa
            return ImageFont.truetype("arialbd.ttf", tamanho)
        except:
            # Fallback para fonte padrão
            return ImageFont.load_default()

# =============================
# NOVA FUNÇÃO: Gerar poster por tipo de análise
# =============================
def gerar_poster_por_tipo(jogos_filtrados, tipo_analise, config_analise):
    """Gera poster específico para cada tipo de análise"""
    if tipo_analise == "Favorito (Vitória)":
        return gerar_poster_favorito(jogos_filtrados, config_analise)
    elif tipo_analise == "Gols HT (Primeiro Tempo)":
        return gerar_poster_gols_ht(jogos_filtrados, config_analise)
    else:
        # Fallback para poster West Ham padrão
        return gerar_poster_westham_style(jogos_filtrados, "ALERTA DE GOLS")

# =============================
# NOVAS FUNÇÕES: Geradores de poster específicos (VERSÃO ATUALIZADA)
# =============================

def gerar_poster_favorito(jogos_favorito, config):
    """Gera poster específico para alertas de Favorito (Vitória) - VERSÃO PROFISSIONAL"""
    # Configurações
    LARGURA = 2200
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 1000
    PADDING = 120
    
    jogos_count = min(len(jogos_favorito), 5)  # Limitar a 5 jogos
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(15, 25, 40))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(70)
    FONTE_VS = criar_fonte(70)
    FONTE_INFO = criar_fonte(45)
    FONTE_DETALHES = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_ALERTA = criar_fonte(100)
    FONTE_ESTATISTICAS = criar_fonte(40)
    FONTE_SECTION = criar_fonte(65)

    # Título PRINCIPAL - ALERTA DE FAVORITO
    titulo_text = "🏆 ALERTA DE FAVORITO (VITÓRIA)"
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_ALERTA)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo_text, font=FONTE_ALERTA, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 250, 80), titulo_text, font=FONTE_ALERTA, fill=(255, 215, 0))

    # Informações gerais
    min_conf_vitoria = config.get("min_conf_vitoria", 65)
    filtro_favorito = config.get("filtro_favorito", "Todos")
    
    subtitulo = f"Confiança Mínima: {min_conf_vitoria}% | Filtro: {filtro_favorito}"
    try:
        sub_bbox = draw.textbbox((0, 0), subtitulo, font=FONTE_SUBTITULO)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((LARGURA - sub_w) // 2, 180), subtitulo, font=FONTE_SUBTITULO, fill=(150, 200, 255))
    except:
        draw.text((LARGURA//2 - 200, 180), subtitulo, font=FONTE_SUBTITULO, fill=(150, 200, 255))

    # Linha decorativa
    draw.line([(LARGURA//4, 250), (3*LARGURA//4, 250)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos_favorito[:5]):  # Máximo 5 jogos
        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Cor baseada no favorito
        if jogo.get('favorito') == "home":
            cor_borda = (76, 175, 80)  # Verde para casa
            cor_principal = (76, 175, 80)
        elif jogo.get('favorito') == "away":
            cor_borda = (33, 150, 243)  # Azul para fora
            cor_principal = (33, 150, 243)
        else:
            cor_borda = (255, 193, 7)  # Amarelo para empate
            cor_principal = (255, 193, 7)
        
        # Caixa do jogo com borda
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 50), outline=cor_borda, width=6)
        
        # Nome da liga
        liga_text = jogo.get('liga', 'Desconhecido')[:30].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SECTION)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SECTION, fill=(200, 200, 200))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SECTION, fill=(200, 200, 200))

        # Data e hora
        if isinstance(jogo.get("hora"), datetime):
            data_text = jogo["hora"].strftime("%d.%m.%Y")
            hora_text = jogo["hora"].strftime("%H:%M")
        else:
            data_text = str(jogo.get("hora", ""))
            hora_text = ""

        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 120), data_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 150, y0 + 120), data_text, font=FONTE_INFO, fill=(150, 200, 255))

        try:
            hora_bbox = draw.textbbox((0, 0), hora_text, font=FONTE_INFO)
            hora_w = hora_bbox[2] - hora_bbox[0]
            draw.text(((LARGURA - hora_w) // 2, y0 + 170), hora_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 120, y0 + 170), hora_text, font=FONTE_INFO, fill=(150, 200, 255))

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

        # Baixar escudos COM CACHE
        escudo_home = baixar_escudo_com_cache(jogo.get('home', ''), jogo.get('escudo_home', ''))
        escudo_away = baixar_escudo_com_cache(jogo.get('away', ''), jogo.get('escudo_away', ''))

        def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo branco quadrado
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
                logging.error(f"Erro ao processar escudo favorito: {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 70, y + 90), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Desenhar escudos quadrados
        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        home_text = jogo.get('home', '')[:20]
        away_text = jogo.get('away', '')[:20]

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

        # SEÇÃO DE ANÁLISE - FAVORITO
        y_analysis = y_escudos + TAMANHO_QUADRADO + 150
        
        # Linha separadora
        draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)

        # Determinar favorito
        favorito = jogo.get('favorito', '')
        prob_vitoria = jogo.get('prob_vitoria', 0)
        confianca_vitoria = jogo.get('confianca_vitoria', 0)
        
        if favorito == "home":
            favorito_text = f"🏠 {jogo.get('home', '')} ({prob_vitoria:.1f}%)"
        elif favorito == "away":
            favorito_text = f"✈️ {jogo.get('away', '')} ({prob_vitoria:.1f}%)"
        else:
            favorito_text = f"🤝 EMPATE ({prob_vitoria:.1f}%)"

        # Texto principal do favorito
        try:
            fav_bbox = draw.textbbox((0, 0), favorito_text, font=FONTE_ANALISE)
            fav_w = fav_bbox[2] - fav_bbox[0]
            draw.text(((LARGURA - fav_w) // 2, y_analysis), favorito_text, font=FONTE_ANALISE, fill=cor_principal)
        except:
            draw.text((PADDING + 100, y_analysis), favorito_text, font=FONTE_ANALISE, fill=cor_principal)

        # Confiança
        conf_text = f"Confiança: {confianca_vitoria:.1f}%"
        try:
            conf_bbox = draw.textbbox((0, 0), conf_text, font=FONTE_DETALHES)
            conf_w = conf_bbox[2] - conf_bbox[0]
            draw.text(((LARGURA - conf_w) // 2, y_analysis + 90), conf_text, font=FONTE_DETALHES, fill=(100, 200, 255))
        except:
            draw.text((PADDING + 100, y_analysis + 90), conf_text, font=FONTE_DETALHES, fill=(100, 200, 255))

        # Probabilidades detalhadas
        y_stats = y_analysis + 180
        
        if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
            vitoria = jogo['detalhes']['vitoria']
            
            # Criar três colunas para as probabilidades
            col1_text = f"🏠 Casa: {vitoria.get('home_win', 0):.1f}%"
            col2_text = f"🤝 Empate: {vitoria.get('draw', 0):.1f}%"
            col3_text = f"✈️ Fora: {vitoria.get('away_win', 0):.1f}%"
            
            # Desenhar as colunas
            try:
                # Coluna 1
                col1_bbox = draw.textbbox((0, 0), col1_text, font=FONTE_ESTATISTICAS)
                col1_w = col1_bbox[2] - col1_bbox[0]
                col1_x = (LARGURA // 2) - 400
                draw.text((col1_x, y_stats), col1_text, font=FONTE_ESTATISTICAS, 
                         fill=(76, 175, 80) if favorito == "home" else (180, 180, 180))
                
                # Coluna 2
                col2_bbox = draw.textbbox((0, 0), col2_text, font=FONTE_ESTATISTICAS)
                col2_w = col2_bbox[2] - col2_bbox[0]
                col2_x = (LARGURA - col2_w) // 2
                draw.text((col2_x, y_stats), col2_text, font=FONTE_ESTATISTICAS,
                         fill=(255, 193, 7) if favorito == "draw" else (180, 180, 180))
                
                # Coluna 3
                col3_bbox = draw.textbbox((0, 0), col3_text, font=FONTE_ESTATISTICAS)
                col3_w = col3_bbox[2] - col3_bbox[0]
                col3_x = (LARGURA // 2) + 400 - col3_w
                draw.text((col3_x, y_stats), col3_text, font=FONTE_ESTATISTICAS,
                         fill=(33, 150, 243) if favorito == "away" else (180, 180, 180))
            except:
                # Fallback se der erro
                draw.text((PADDING + 100, y_stats), col1_text, font=FONTE_ESTATISTICAS, 
                         fill=(76, 175, 80) if favorito == "home" else (180, 180, 180))
                draw.text((PADDING + 400, y_stats), col2_text, font=FONTE_ESTATISTICAS,
                         fill=(255, 193, 7) if favorito == "draw" else (180, 180, 180))
                draw.text((PADDING + 700, y_stats), col3_text, font=FONTE_ESTATISTICAS,
                         fill=(33, 150, 243) if favorito == "away" else (180, 180, 180))

        # Adicionar análise de Over/Under se disponível
        y_extra = y_stats + 50
        if 'detalhes' in jogo and 'over_25_prob' in jogo['detalhes']:
            over_25 = jogo['detalhes'].get('over_25_prob', 0)
            under_25 = jogo['detalhes'].get('under_25_prob', 0)
            
            ou_text = f"📊 Over 2.5: {over_25:.1f}% | Under 2.5: {under_25:.1f}%"
            try:
                ou_bbox = draw.textbbox((0, 0), ou_text, font=FONTE_ESTATISTICAS)
                ou_w = ou_bbox[2] - ou_bbox[0]
                draw.text(((LARGURA - ou_w) // 2, y_extra), ou_text, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
            except:
                draw.text((PADDING + 100, y_extra), ou_text, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • Análise de Favoritos • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 250, altura_total - 70), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster Favorito GERADO com {min(len(jogos_favorito), 5)} jogos")
    return buffer


def gerar_poster_gols_ht(jogos_ht, config):
    """Gera poster específico para alertas de Gols HT (Primeiro Tempo) - VERSÃO PROFISSIONAL"""
    # Configurações
    LARGURA = 2200
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 1000
    PADDING = 120
    
    jogos_count = min(len(jogos_ht), 5)  # Limitar a 5 jogos
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(15, 25, 40))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(70)
    FONTE_VS = criar_fonte(70)
    FONTE_INFO = criar_fonte(45)
    FONTE_DETALHES = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_ALERTA = criar_fonte(100)
    FONTE_ESTATISTICAS = criar_fonte(40)
    FONTE_SECTION = criar_fonte(65)

    # Título PRINCIPAL - ALERTA DE GOLS HT
    titulo_text = "⏰ ALERTA DE GOLS NO PRIMEIRO TEMPO (HT)"
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_ALERTA)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo_text, font=FONTE_ALERTA, fill=(100, 200, 255))
    except:
        draw.text((LARGURA//2 - 300, 80), titulo_text, font=FONTE_ALERTA, fill=(100, 200, 255))

    # Informações gerais
    min_conf_ht = config.get("min_conf_ht", 60)
    tipo_ht = config.get("tipo_ht", "OVER 0.5 HT")
    
    subtitulo = f"Confiança Mínima: {min_conf_ht}% | Tipo: {tipo_ht}"
    try:
        sub_bbox = draw.textbbox((0, 0), subtitulo, font=FONTE_SUBTITULO)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((LARGURA - sub_w) // 2, 180), subtitulo, font=FONTE_SUBTITULO, fill=(180, 200, 220))
    except:
        draw.text((LARGURA//2 - 200, 180), subtitulo, font=FONTE_SUBTITULO, fill=(180, 200, 220))

    # Linha decorativa
    draw.line([(LARGURA//4, 250), (3*LARGURA//4, 250)], fill=(100, 200, 255), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos_ht[:5]):  # Máximo 5 jogos
        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Cor baseada no tipo de HT
        if "OVER" in jogo.get('tendencia_ht', ''):
            cor_borda = (76, 175, 80)  # Verde para OVER
            cor_principal = (76, 175, 80)
        else:
            cor_borda = (255, 87, 34)  # Laranja para UNDER
            cor_principal = (255, 87, 34)
        
        # Caixa do jogo com borda
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 50), outline=cor_borda, width=6)
        
        # Nome da liga
        liga_text = jogo.get('liga', 'Desconhecido')[:30].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SECTION)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SECTION, fill=(200, 200, 200))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SECTION, fill=(200, 200, 200))

        # Data e hora
        if isinstance(jogo.get("hora"), datetime):
            data_text = jogo["hora"].strftime("%d.%m.%Y")
            hora_text = jogo["hora"].strftime("%H:%M")
        else:
            data_text = str(jogo.get("hora", ""))
            hora_text = ""

        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 120), data_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 150, y0 + 120), data_text, font=FONTE_INFO, fill=(150, 200, 255))

        try:
            hora_bbox = draw.textbbox((0, 0), hora_text, font=FONTE_INFO)
            hora_w = hora_bbox[2] - hora_bbox[0]
            draw.text(((LARGURA - hora_w) // 2, y0 + 170), hora_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 120, y0 + 170), hora_text, font=FONTE_INFO, fill=(150, 200, 255))

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

        # Baixar escudos COM CACHE
        escudo_home = baixar_escudo_com_cache(jogo.get('home', ''), jogo.get('escudo_home', ''))
        escudo_away = baixar_escudo_com_cache(jogo.get('away', ''), jogo.get('escudo_away', ''))

        def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo branco quadrado
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
                logging.error(f"Erro ao processar escudo HT: {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 70, y + 90), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Desenhar escudos quadrados
        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        home_text = jogo.get('home', '')[:20]
        away_text = jogo.get('away', '')[:20]

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

        # SEÇÃO DE ANÁLISE - GOLS HT
        y_analysis = y_escudos + TAMANHO_QUADRADO + 150
        
        # Linha separadora
        draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)

        # Tendência HT principal
        tendencia_ht = jogo.get('tendencia_ht', '')
        confianca_ht = jogo.get('confianca_ht', 0)
        estimativa_ht = jogo.get('estimativa_ht', 0)
        
        if "OVER" in tendencia_ht:
            ht_emoji = "📈"
        else:
            ht_emoji = "📉"
            
        ht_main_text = f"{ht_emoji} {tendencia_ht}"

        try:
            ht_bbox = draw.textbbox((0, 0), ht_main_text, font=FONTE_ANALISE)
            ht_w = ht_bbox[2] - ht_bbox[0]
            draw.text(((LARGURA - ht_w) // 2, y_analysis), ht_main_text, font=FONTE_ANALISE, fill=cor_principal)
        except:
            draw.text((PADDING + 100, y_analysis), ht_main_text, font=FONTE_ANALISE, fill=cor_principal)

        # Estatísticas HT
        stats_text = f"Estimativa: {estimativa_ht:.2f} gols | Confiança: {confianca_ht:.1f}%"
        try:
            stats_bbox = draw.textbbox((0, 0), stats_text, font=FONTE_DETALHES)
            stats_w = stats_bbox[2] - stats_bbox[0]
            draw.text(((LARGURA - stats_w) // 2, y_analysis + 90), stats_text, font=FONTE_DETALHES, fill=(100, 200, 255))
        except:
            draw.text((PADDING + 100, y_analysis + 90), stats_text, font=FONTE_DETALHES, fill=(100, 200, 255))

        # Probabilidades detalhadas HT
        y_stats = y_analysis + 180
        
        if 'detalhes' in jogo and 'gols_ht' in jogo['detalhes']:
            ht_data = jogo['detalhes']['gols_ht']
            
            # Criar três colunas para as probabilidades HT
            col1_text = f"Over 0.5 HT: {ht_data.get('over_05_ht', 0):.1f}%"
            col2_text = f"Over 1.5 HT: {ht_data.get('over_15_ht', 0):.1f}%"
            col3_text = f"Ambos HT: {ht_data.get('btts_ht', 0):.1f}%"
            
            # Desenhar as colunas
            try:
                # Coluna 1
                col1_bbox = draw.textbbox((0, 0), col1_text, font=FONTE_ESTATISTICAS)
                col1_w = col1_bbox[2] - col1_bbox[0]
                col1_x = (LARGURA // 2) - 400
                draw.text((col1_x, y_stats), col1_text, font=FONTE_ESTATISTICAS, 
                         fill=(76, 175, 80) if "OVER" in tendencia_ht else (180, 220, 255))
                
                # Coluna 2
                col2_bbox = draw.textbbox((0, 0), col2_text, font=FONTE_ESTATISTICAS)
                col2_w = col2_bbox[2] - col2_bbox[0]
                col2_x = (LARGURA - col2_w) // 2
                draw.text((col2_x, y_stats), col2_text, font=FONTE_ESTATISTICAS,
                         fill=(100, 200, 255))
                
                # Coluna 3
                col3_bbox = draw.textbbox((0, 0), col3_text, font=FONTE_ESTATISTICAS)
                col3_w = col3_bbox[2] - col3_bbox[0]
                col3_x = (LARGURA // 2) + 400 - col3_w
                draw.text((col3_x, y_stats), col3_text, font=FONTE_ESTATISTICAS,
                         fill=(255, 193, 7))
            except:
                # Fallback se der erro
                draw.text((PADDING + 100, y_stats), col1_text, font=FONTE_ESTATISTICAS, 
                         fill=(76, 175, 80) if "OVER" in tendencia_ht else (180, 220, 255))
                draw.text((PADDING + 400, y_stats), col2_text, font=FONTE_ESTATISTICAS,
                         fill=(100, 200, 255))
                draw.text((PADDING + 700, y_stats), col3_text, font=FONTE_ESTATISTICAS,
                         fill=(255, 193, 7))

        # Adicionar análise de Over/Under se disponível
        y_extra = y_stats + 50
        if 'detalhes' in jogo and 'over_25_prob' in jogo['detalhes']:
            over_25 = jogo['detalhes'].get('over_25_prob', 0)
            under_25 = jogo['detalhes'].get('under_25_prob', 0)
            
            ou_text = f"📊 Over 2.5: {over_25:.1f}% | Under 2.5: {under_25:.1f}%"
            try:
                ou_bbox = draw.textbbox((0, 0), ou_text, font=FONTE_ESTATISTICAS)
                ou_w = ou_bbox[2] - ou_bbox[0]
                draw.text(((LARGURA - ou_w) // 2, y_extra), ou_text, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
            except:
                draw.text((PADDING + 100, y_extra), ou_text, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

        # Adicionar análise de vitória se disponível
        y_extra2 = y_extra + 40
        if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
            vitoria = jogo['detalhes']['vitoria']
            favorito = vitoria.get('favorito', '')
            
            if favorito == "home":
                fav_text = f"🏆 Favorito: {jogo.get('home', '')} ({vitoria.get('home_win', 0):.1f}%)"
            elif favorito == "away":
                fav_text = f"🏆 Favorito: {jogo.get('away', '')} ({vitoria.get('away_win', 0):.1f}%)"
            else:
                fav_text = f"🏆 Favorito: EMPATE ({vitoria.get('draw', 0):.1f}%)"
                
            draw.text((PADDING + 100, y_extra2), fav_text, font=FONTE_ESTATISTICAS, fill=(255, 215, 0))

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • Análise de Gols HT • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 250, altura_total - 70), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster Gols HT GERADO com {min(len(jogos_ht), 5)} jogos")
    return buffer

# =============================
# Funções de Geração de Posters - VERSÃO ATUALIZADA COM NOVAS ANÁLISES
# =============================


def gerar_poster_individual_westham(fixture: dict, analise: dict) -> io.BytesIO:
    """
    Gera poster individual no estilo West Ham com análises completas
    """
    # Configurações
    LARGURA = 1800
    ALTURA = 1350  # Aumentada para incluir mais análises
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
    FONTE_SECTION = criar_fonte(55)  # Nova fonte para seções

    # Título PRINCIPAL - ALERTA
    tipo_alerta = "🎯 ALERTA " if analise["tipo_aposta"] == "over" else "🛡️ ALERTA UNDER"
    titulo_text = f"{tipo_alerta} DE GOLS"
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_ALERTA)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        cor_titulo = (255, 215, 0) if analise["tipo_aposta"] == "over" else (100, 200, 255)
        draw.text(((LARGURA - titulo_w) // 2, 60), titulo_text, font=FONTE_ALERTA, fill=cor_titulo)
    except:
        draw.text((LARGURA//2 - 200, 60), titulo_text, font=FONTE_ALERTA, fill=cor_titulo)

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
    ESPACO_ENTRE_ESCUDOS = 600

    # Calcular posição central
    largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    x_inicio = (LARGURA - largura_total) // 2

    x_home = x_inicio
    x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    y_escudos = 320

    # Baixar escudos COM CACHE
    escudo_home_url = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
    escudo_away_url = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
    
    escudo_home = baixar_escudo_com_cache(home, escudo_home_url)
    escudo_away = baixar_escudo_com_cache(away, escudo_away_url)

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

    # NOVA SEÇÃO: ANÁLISE DE VITÓRIA
    y_vitoria = y_analysis + 280
    
    # Título seção vitória
    vitoria_title = "🏆 PROBABILIDADE DE VITÓRIA"
    try:
        title_bbox = draw.textbbox((0, 0), vitoria_title, font=FONTE_SECTION)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((LARGURA - title_w) // 2, y_vitoria), vitoria_title, font=FONTE_SECTION, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 200, y_vitoria), vitoria_title, font=FONTE_SECTION, fill=(255, 215, 0))
    
    # Dados de vitória
    vitoria_data = analise['detalhes']['vitoria']
    home_win = vitoria_data['home_win']
    away_win = vitoria_data['away_win']
    draw_prob = vitoria_data['draw']
    favorito = vitoria_data['favorito']
    
    # Determinar cores
    cor_home = (76, 175, 80) if favorito == "home" else (180, 180, 180)
    cor_away = (76, 175, 80) if favorito == "away" else (180, 180, 180)
    cor_draw = (76, 175, 80) if favorito == "draw" else (180, 180, 180)
    
    y_vitoria_content = y_vitoria + 70
    
    # Home win
    home_text = f"🏠 {home}: {home_win}%"
    try:
        home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_DETALHES)
        home_w = home_bbox[2] - home_bbox[0]
        draw.text(((LARGURA - home_w) // 2 - 300, y_vitoria_content), home_text, font=FONTE_DETALHES, fill=cor_home)
    except:
        draw.text((PADDING + 100, y_vitoria_content), home_text, font=FONTE_DETALHES, fill=cor_home)
    
    # Draw
    draw_text = f"🤝 EMPATE: {draw_prob}%"
    try:
        draw_bbox = draw.textbbox((0, 0), draw_text, font=FONTE_DETALHES)
        draw_w = draw_bbox[2] - draw_bbox[0]
        draw.text(((LARGURA - draw_w) // 2, y_vitoria_content), draw_text, font=FONTE_DETALHES, fill=cor_draw)
    except:
        draw.text((LARGURA//2 - 100, y_vitoria_content), draw_text, font=FONTE_DETALHES, fill=cor_draw)
    
    # Away win
    away_text = f"✈️ {away}: {away_win}%"
    try:
        away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_DETALHES)
        away_w = away_bbox[2] - away_bbox[0]
        draw.text(((LARGURA - away_w) // 2 + 300, y_vitoria_content), away_text, font=FONTE_DETALHES, fill=cor_away)
    except:
        draw.text((LARGURA - PADDING - 400, y_vitoria_content), away_text, font=FONTE_DETALHES, fill=cor_away)

    # NOVA SEÇÃO: ANÁLISE DE GOLS HT
    y_ht = y_vitoria + 140
    
    # Título seção HT
    ht_title = "⏰ PROBABILIDADE DE GOLS NO PRIMEIRO TEMPO"
    try:
        ht_bbox = draw.textbbox((0, 0), ht_title, font=FONTE_SECTION)
        ht_w = ht_bbox[2] - ht_bbox[0]
        draw.text(((LARGURA - ht_w) // 2, y_ht), ht_title, font=FONTE_SECTION, fill=(100, 200, 255))
    except:
        draw.text((LARGURA//2 - 250, y_ht), ht_title, font=FONTE_SECTION, fill=(100, 200, 255))
    
    # Dados HT
    ht_data = analise['detalhes']['gols_ht']
    tendencia_ht = ht_data['tendencia_ht']
    confianca_ht = ht_data['confianca_ht']
    over_05_ht = ht_data['over_05_ht']
    over_15_ht = ht_data['over_15_ht']
    btts_ht = ht_data['btts_ht']
    
    y_ht_content = y_ht + 70
    
    # Tendência HT principal
    ht_main_text = f"{tendencia_ht} - {confianca_ht}%"
    try:
        ht_main_bbox = draw.textbbox((0, 0), ht_main_text, font=FONTE_DETALHES)
        ht_main_w = ht_main_bbox[2] - ht_main_bbox[0]
        draw.text(((LARGURA - ht_main_w) // 2, y_ht_content), ht_main_text, font=FONTE_DETALHES, fill=(255, 193, 7))
    except:
        draw.text((LARGURA//2 - 150, y_ht_content), ht_main_text, font=FONTE_DETALHES, fill=(255, 193, 7))
    
    # Estatísticas HT detalhadas
    y_ht_stats = y_ht_content + 50
    
    ht_stats_texts = [
        f"Over 0.5 HT: {over_05_ht}%",
        f"Over 1.5 HT: {over_15_ht}%",
        f"Ambos marcam HT: {btts_ht}%"
    ]
    
    # Distribuir em três colunas
    for i, text in enumerate(ht_stats_texts):
        try:
            bbox = draw.textbbox((0, 0), text, font=FONTE_ESTATISTICAS)
            w = bbox[2] - bbox[0]
            x_pos = PADDING + 200 + i * 500
            draw.text((x_pos, y_ht_stats), text, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))
        except:
            x_pos = PADDING + 200 + i * 500
            draw.text((x_pos, y_ht_stats), text, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

    # ESTATÍSTICAS DETALHADAS (OVER/UNDER)
    y_estatisticas = y_ht_stats + 50
    
    # Título estatísticas
    stats_title = "📊 ESTATÍSTICAS OVER/UNDER"
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

def gerar_poster_top_jogos(top_jogos: list, min_conf: int, max_conf: int, titulo: str = "** TOP JOGOS DO DIA **") -> io.BytesIO:
    """
    Gera poster profissional para os Top Jogos com escudos e estatísticas COMPLETAS
    """
    # Configurações
    LARGURA = 2200
    ALTURA_TOPO = 300
    ALTURA_POR_JOGO = 1000  # Aumentado para incluir mais análises
    PADDING = 80
    
    jogos_count = len(top_jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(15, 25, 40))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(55)
    FONTE_VS = criar_fonte(45)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(55)
    FONTE_RANKING = criar_fonte(70)
    FONTE_ESTATISTICAS = criar_fonte(35)
    FONTE_SMALL = criar_fonte(30)  # Nova fonte menor para mais detalhes

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 350, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Subtítulo com intervalo de confiança
    subtitulo = f"🎯 Intervalo de Confiança: {min_conf}% - {max_conf}% | 🔥 {len(top_jogos)} Jogos Selecionados"
    try:
        sub_bbox = draw.textbbox((0, 0), subtitulo, font=FONTE_SUBTITULO)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((LARGURA - sub_w) // 2, 180), subtitulo, font=FONTE_SUBTITULO, fill=(150, 200, 255))
    except:
        draw.text((LARGURA//2 - 300, 180), subtitulo, font=FONTE_SUBTITULO, fill=(150, 200, 255))

    # Linha decorativa
    draw.line([(LARGURA//4, 250), (3*LARGURA//4, 250)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(top_jogos):
        # Caixa do jogo com ranking
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Cor baseada no tipo de aposta
        cor_borda = (76, 175, 80) if jogo.get('tipo_aposta') == "over" else (255, 87, 34)
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 50), outline=cor_borda, width=3)
        
        # Número do ranking (TOP 1, TOP 2, etc.)
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

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 50), liga_text, font=FONTE_SUBTITULO, fill=(180, 200, 220))
        except:
            draw.text((LARGURA//2 - 150, y0 + 50), liga_text, font=FONTE_SUBTITULO, fill=(180, 200, 220))

        # Data e hora
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

        # ESCUDOS DOS TIMES (COM CACHE)
        TAMANHO_ESCUDO = 180
        TAMANHO_QUADRADO = 220
        ESPACO_ENTRE_ESCUDOS = 700

        # Calcular posição central
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        y_escudos = y0 + 180

        # Baixar escudos COM CACHE
        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get('escudo_home', ''))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get('escudo_away', ''))

        def desenhar_escudo_quadrado_top(logo_img, x, y, tamanho_quadrado, tamanho_escudo, team_name):
            # Fundo branco quadrado
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], 
                         fill=(255, 255, 255), outline=(200, 200, 200), width=2)

            if logo_img is None:
                # Placeholder com inicial do time
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

        # Desenhar escudos
        desenhar_escudo_quadrado_top(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['home'])
        desenhar_escudo_quadrado_top(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo['away'])

        # Nomes dos times
        home_text = jogo['home'][:15]
        away_text = jogo['away'][:15]

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

        # SEÇÃO DE ANÁLISE
        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        # Linha separadora
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

        # Tipo de aposta com emoji
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

        # NOVA SEÇÃO: ANÁLISE DE VITÓRIA RESUMIDA
        y_vitoria = y_analysis + 280
        
        if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
            vitoria_data = jogo['detalhes']['vitoria']
            
            # Determinar favorito
            favorito = vitoria_data['favorito']
            if favorito == "home":
                vitoria_text = f"🏆 FAVORITO: {jogo['home']} ({vitoria_data['home_win']}%)"
                cor_vitoria = (76, 175, 80)
            elif favorito == "away":
                vitoria_text = f"🏆 FAVORITO: {jogo['away']} ({vitoria_data['away_win']}%)"
                cor_vitoria = (76, 175, 80)
            else:
                vitoria_text = f"🏆 FAVORITO: EMPATE ({vitoria_data['draw']}%)"
                cor_vitoria = (255, 193, 7)
            
            draw.text((x0 + 100, y_vitoria), vitoria_text, font=FONTE_ESTATISTICAS, fill=cor_vitoria)
            
            # Probabilidades de vitória
            vitoria_stats = [
                f"🏠 {vitoria_data['home_win']}%",
                f"🤝 {vitoria_data['draw']}%", 
                f"✈️ {vitoria_data['away_win']}%"
            ]
            
            for i, stat in enumerate(vitoria_stats):
                draw.text((x0 + 150 + i * 300, y_vitoria + 40), stat, font=FONTE_SMALL, fill=(200, 220, 255))

        # NOVA SEÇÃO: GOLS HT RESUMIDO
        y_ht = y_vitoria + 80
        
        if 'detalhes' in jogo and 'gols_ht' in jogo['detalhes']:
            ht_data = jogo['detalhes']['gols_ht']
            ht_text = f"⏰ {ht_data['tendencia_ht']} ({ht_data['confianca_ht']}%)"
            draw.text((x0 + 100, y_ht), ht_text, font=FONTE_ESTATISTICAS, fill=(100, 200, 255))
            
            # Estatísticas HT
            ht_stats = [
                f"Over 0.5 HT: {ht_data['over_05_ht']}%",
                f"Over 1.5 HT: {ht_data['over_15_ht']}%"
            ]
            
            for i, stat in enumerate(ht_stats):
                draw.text((x0 + 150 + i * 400, y_ht + 40), stat, font=FONTE_SMALL, fill=(180, 220, 255))

        # Estatísticas detalhadas (se disponíveis)
        if 'detalhes' in jogo:
            y_stats = y_ht + 80
            detalhes = jogo['detalhes']
            
            stats_text = [
                f"Over 2.5: {detalhes.get('over_25_prob', 0):.0f}%",
                f"Under 2.5: {detalhes.get('under_25_prob', 0):.0f}%",
                f"Over 1.5: {detalhes.get('over_15_prob', 0):.0f}%",
                f"Under 1.5: {detalhes.get('under_15_prob', 0):.0f}%"
            ]
            
            # Distribuir em duas colunas
            for i, stat in enumerate(stats_text):
                col = i % 2
                row = i // 2
                x_pos = PADDING + 100 + (col * 300)
                draw.text((x_pos, y_stats + row * 40), stat, font=FONTE_ESTATISTICAS, fill=(180, 200, 220))

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f" ELITE MASTER SYSTEM - Análise Preditiva | {datetime.now().strftime('%d/%m/%Y %H:%M')}"
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
    
    st.success(f"✅ Poster TOP {len(top_jogos)} Jogos gerado com sucesso!")
    return buffer

def gerar_poster_westham_style(jogos: list, titulo: str = " ALERTA DE GOLS") -> io.BytesIO:
    """
    Gera poster no estilo West Ham vs Burnley
    """
    # Configurações
    LARGURA = 2000
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 1150  # Aumentado para incluir mais estatísticas
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

        # Baixar escudos COM CACHE
        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get('escudo_home', ''))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get('escudo_away', ''))

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

        # NOVA SEÇÃO: ANÁLISE DE VITÓRIA
        y_vitoria = y_analysis + 360
        
        if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
            vitoria_data = jogo['detalhes']['vitoria']
            
            # Título vitória
            vitoria_title = "🏆 Probabilidade de Vitória:"
            draw.text((x0 + 100, y_vitoria), vitoria_title, font=FONTE_DETALHES, fill=(200, 200, 200))
            
            # Dados vitória
            y_vitoria_content = y_vitoria + 60
            
            home_text = f"🏠 {jogo['home']}: {vitoria_data['home_win']}%"
            draw_text = f"🤝 Empate: {vitoria_data['draw']}%"
            away_text = f"✈️ {jogo['away']}: {vitoria_data['away_win']}%"
            
            # Destacar favorito
            favorito = vitoria_data['favorito']
            cor_home = (76, 175, 80) if favorito == "home" else (180, 180, 180)
            cor_draw = (76, 175, 80) if favorito == "draw" else (180, 180, 180)
            cor_away = (76, 175, 80) if favorito == "away" else (180, 180, 180)
            
            draw.text((x0 + 120, y_vitoria_content), home_text, font=FONTE_ESTATISTICAS, fill=cor_home)
            draw.text((x0 + 500, y_vitoria_content), draw_text, font=FONTE_ESTATISTICAS, fill=cor_draw)
            draw.text((x0 + 880, y_vitoria_content), away_text, font=FONTE_ESTATISTICAS, fill=cor_away)

        # NOVA SEÇÃO: ANÁLISE DE GOLS HT
        y_ht = y_vitoria + 100
        
        if 'detalhes' in jogo and 'gols_ht' in jogo['detalhes']:
            ht_data = jogo['detalhes']['gols_ht']
            
            # Título HT
            ht_title = "⏰ Primeiro Tempo:"
            draw.text((x0 + 100, y_ht), ht_title, font=FONTE_DETALHES, fill=(200, 200, 200))
            
            # Dados HT
            y_ht_content = y_ht + 60
            
            ht_main = f"{ht_data['tendencia_ht']} ({ht_data['confianca_ht']}%)"
            draw.text((x0 + 120, y_ht_content), ht_main, font=FONTE_ESTATISTICAS, fill=(100, 200, 255))
            
            # Estatísticas HT
            ht_stats = [
                f"Over 0.5 HT: {ht_data['over_05_ht']}%",
                f"Over 1.5 HT: {ht_data['over_15_ht']}%",
                f"Ambos HT: {ht_data['btts_ht']}%"
            ]
            
            for i, stat in enumerate(ht_stats):
                draw.text((x0 + 400 + i * 350, y_ht_content), stat, font=FONTE_ESTATISTICAS, fill=(180, 220, 255))

        # ESTATÍSTICAS DETALHADAS (OVER/UNDER)
        y_stats = y_ht + 100
        
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

def gerar_poster_resultados(jogos: list, titulo: str = " ** RESULTADOS OFICIAIS ** ") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais dos jogos - VERSÃO ATUALIZADA COM FUNDO QUADRADO
    """
    # Configurações do poster
    LARGURA = 2200
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950  # Ajustado para melhor layout
    PADDING = 80
    
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

        # Baixar escudos COM CACHE
        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get("escudo_home", ""))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get("escudo_away", ""))

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

# =============================
# FUNÇÃO AUXILIAR: Gerar poster de resultados com limite de jogos
# =============================
def gerar_poster_resultados_limitado(jogos: list, titulo: str = "- RESULTADOS", max_jogos: int = 3) -> io.BytesIO:
    """
    Gera poster profissional com resultados finais - VERSÃO COM LIMITE DE JOGOS
    """
    # Limitar o número de jogos
    jogos_limitados = jogos[:max_jogos]
    
    # Configurações do poster (igual à versão original, mas com altura ajustável)
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950
    PADDING = 120
    
    jogos_count = len(jogos_limitados)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(70)
    FONTE_PLACAR = criar_fonte(100)
    FONTE_VS = criar_fonte(70)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_RESULTADO = criar_fonte(70)

    # Título PRINCIPAL com indicação de lote
    lote_text = f"LOTE {titulo.split('-')[-1].strip()}" if "LOTE" not in titulo else titulo
    try:
        titulo_bbox = draw.textbbox((0, 0), lote_text, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), lote_text, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 80), lote_text, font=FONTE_TITULO, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 180), (3*LARGURA//4, 180)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos_limitados):
        # Calcular se a previsão foi correta
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
        
        # Fundo com borda colorida
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=6)

        # BADGE RESULTADO (GREEN/RED)
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

        # ESCUDOS E PLACAR
        TAMANHO_ESCUDO = 245
        TAMANHO_QUADRADO = 280
        ESPACO_ENTRE_ESCUDOS = 700

        # Calcular posição central
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS 
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_placar = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 100
        x_away = x_placar + 450

        y_escudos = y0 + 180

        # Baixar escudos COM CACHE
        escudo_home = baixar_escudo_com_cache(jogo['home'], jogo.get("escudo_home", ""))
        escudo_away = baixar_escudo_com_cache(jogo['away'], jogo.get("escudo_away", ""))

        def desenhar_escudo_quadrado_resultado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo QUADRADO BRANCO
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

        # PLACAR CENTRAL
        placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_placar + (200 - placar_w) // 2
            draw.text((placar_x, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            draw.text((x_placar, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))

        # Nomes dos times
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

        # SEÇÃO DE ANÁLISE DO RESULTADO
        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        # Linha separadora
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

        # Informações de análise
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

    # Rodapé com indicador de lote
    rodape_text = f"Partidas {len(jogos_limitados)}/{len(jogos)} • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • Elite Master System"
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
    
    st.success(f"✅ Poster de resultados gerado com {len(jogos_limitados)} jogos (máx: {max_jogos})")
    return buffer

# =============================
# Funções de Envio de Alertas - VERSÃO ATUALIZADA COM NOVAS ANÁLISES
# =============================
def enviar_alerta_telegram(fixture: dict, analise: dict):
    """Envia alerta individual com poster estilo West Ham e análises completas"""
    try:
        # Gerar poster individual com análises completas
        poster = gerar_poster_individual_westham(fixture, analise)
        
        # Criar caption para o Telegram com todas as análises
        home = fixture["homeTeam"]["name"]
        away = fixture["awayTeam"]["name"]
        data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
        competicao = fixture.get("competition", {}).get("name", "Desconhecido")
        
        tipo_emoji = "🎯" if analise["tipo_aposta"] == "over" else "🛡️"
        
        # Caption principal
        caption = (
            f"<b>{tipo_emoji} ALERTA {analise['tipo_aposta'].upper()} DE GOLS</b>\n\n"
            f"<b>🏆 {competicao}</b>\n"
            f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
            f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
            f"<b>📈 Tendência Principal: {analise['tendencia']}</b>\n"
            f"<b>⚽ Estimativa: {analise['estimativa']:.2f} gols</b>\n"
            f"<b>🎯 Probabilidade: {analise['probabilidade']:.0f}%</b>\n"
            f"<b>🔍 Confiança: {analise['confianca']:.0f}%</b>\n\n"
        )
        
        # Adicionar análise de vitória se disponível
        if 'vitoria' in analise['detalhes']:
            vitoria = analise['detalhes']['vitoria']
            favorito = vitoria['favorito']
            if favorito == "home":
                fav_text = f"{home} ({vitoria['home_win']}%)"
            elif favorito == "away":
                fav_text = f"{away} ({vitoria['away_win']}%)"
            else:
                fav_text = f"EMPATE ({vitoria['draw']}%)"
            
            caption += (
                f"<b>🏆 PROBABILIDADE DE VITÓRIA</b>\n"
                f"<b>• Favorito: {fav_text}</b>\n"
                f"<b>• {home}: {vitoria['home_win']}%</b>\n"
                f"<b>• Empate: {vitoria['draw']}%</b>\n"
                f"<b>• {away}: {vitoria['away_win']}%</b>\n\n"
            )
        
        # Adicionar análise de gols HT se disponível
        if 'gols_ht' in analise['detalhes']:
            ht = analise['detalhes']['gols_ht']
            caption += (
                f"<b>⏰ PRIMEIRO TEMPO (HT)</b>\n"
                f"<b>• Tendência: {ht['tendencia_ht']} ({ht['confianca_ht']}%)</b>\n"
                f"<b>• Over 0.5 HT: {ht['over_05_ht']}%</b>\n"
                f"<b>• Over 1.5 HT: {ht['over_15_ht']}%</b>\n"
                f"<b>• Ambos marcam HT: {ht['btts_ht']}%</b>\n\n"
            )
        
        # Adicionar estatísticas detalhadas
        caption += (
            f"<b>📊 ESTATÍSTICAS DETALHADAS:</b>\n"
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
    
    # Mensagem base
    msg = (
        f"<b>{tipo_emoji} ALERTA {analise['tipo_aposta'].upper()} DE GOLS</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>📈 Tendência: {analise['tendencia']}</b>\n"
        f"<b>⚽ Estimativa: {analise['estimativa']:.2f} gols</b>\n"
        f"<b>🎯 Probabilidade: {analise['probabilidade']:.0f}%</b>\n"
        f"<b>🔍 Confiança: {analise['confianca']:.0f}%</b>\n\n"
    )
    
    # Adicionar análise de vitória se disponível
    if 'vitoria' in analise['detalhes']:
        vitoria = analise['detalhes']['vitoria']
        msg += (
            f"<b>🏆 VITÓRIA:</b>\n"
            f"<b>• {home}: {vitoria['home_win']}%</b>\n"
            f"<b>• Empate: {vitoria['draw']}%</b>\n"
            f"<b>• {away}: {vitoria['away_win']}%</b>\n\n"
        )
    
    # Adicionar análise de gols HT se disponível
    if 'gols_ht' in analise['detalhes']:
        ht = analise['detalhes']['gols_ht']
        msg += (
            f"<b>⏰ PRIMEIRO TEMPO:</b>\n"
            f"<b>• {ht['tendencia_ht']} ({ht['confianca_ht']}%)</b>\n"
            f"<b>• Over 0.5 HT: {ht['over_05_ht']}%</b>\n"
            f"<b>• Over 1.5 HT: {ht['over_15_ht']}%</b>\n\n"
        )
    
    msg += f"<b>🔥 ELITE MASTER SYSTEM</b>"
    
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

def enviar_alerta_westham_style(jogos_conf: list, min_conf: int, max_conf: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Envia alerta no estilo West Ham com análises completas"""
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
            
            # Calcular estatísticas de vitória
            home_fav_count = sum(1 for j in jogos_data if 'detalhes' in j and 'vitoria' in j['detalhes'] and j['detalhes']['vitoria']['favorito'] == "home")
            away_fav_count = sum(1 for j in jogos_data if 'detalhes' in j and 'vitoria' in j['detalhes'] and j['detalhes']['vitoria']['favorito'] == "away")
            draw_fav_count = sum(1 for j in jogos_data if 'detalhes' in j and 'vitoria' in j['detalhes'] and j['detalhes']['vitoria']['favorito'] == "draw")
            
            # Calcular estatísticas HT
            ht_over_count = sum(1 for j in jogos_data if 'detalhes' in j and 'gols_ht' in j['detalhes'] and "OVER" in j['detalhes']['gols_ht']['tendencia_ht'])
            ht_under_count = sum(1 for j in jogos_data if 'detalhes' in j and 'gols_ht' in j['detalhes'] and "UNDER" in j['detalhes']['gols_ht']['tendencia_ht'])
            
            caption = (
                f"<b>🎯 ALERTA DE GOLS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                f"<b>📈 Over: {over_count} jogos</b>\n"
                f"<b>📉 Under: {under_count} jogos</b>\n"
                f"<b>⚽ INTERVALO DE CONFIANÇA: {min_conf}% - {max_conf}%</b>\n\n"
                
                f"<b>🏆 ANÁLISE DE VITÓRIA</b>\n"
                f"<b>• Casa favorita: {home_fav_count} jogos</b>\n"
                f"<b>• Fora favorita: {away_fav_count} jogos</b>\n"
                f"<b>• Empate favorito: {draw_fav_count} jogos</b>\n\n"
                
                f"<b>⏰ PRIMEIRO TEMPO (HT)</b>\n"
                f"<b>• Tendência Over HT: {ht_over_count} jogos</b>\n"
                f"<b>• Tendência Under HT: {ht_under_count} jogos</b>\n\n"
                
                f"<b>🔮 ANÁLISE PREDITIVA COMPLETA</b>\n"
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
# FUNÇÃO MODIFICADA: Enviar alerta de resultados com limite de partidas
# =============================
def enviar_alerta_resultados_poster(jogos_com_resultado: list, max_jogos_por_alerta: int = 3):
    """Envia alerta de resultados com poster para o Telegram - VERSÃO COM LIMITE DE PARTIDAS"""
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

        # Contador de alertas enviados
        alertas_enviados = 0
        
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            
            # Dividir jogos em lotes de no máximo max_jogos_por_alerta
            lotes = [jogos_data[i:i + max_jogos_por_alerta] 
                    for i in range(0, len(jogos_data), max_jogos_por_alerta)]
            
            st.info(f"📊 {len(jogos_data)} jogos encontrados para {data_str} - Serão enviados em {len(lotes)} lote(s)")
            
            for lote_idx, lote in enumerate(lotes):
                lote_num = lote_idx + 1
                titulo = f"ELITE MASTER - RESULTADOS {data_str} - LOTE {lote_num}/{len(lotes)}"
                
                st.info(f"🎨 Gerando poster para lote {lote_num} com {len(lote)} jogos...")
                
                # Gerar poster com limite de jogos
                poster = gerar_poster_resultados_limitado(lote, titulo=titulo, max_jogos=max_jogos_por_alerta)
                
                # Calcular estatísticas APENAS para este lote
                total_jogos_lote = len(lote)
                green_count_lote = sum(1 for j in lote if j.get('resultado') == "GREEN")
                red_count_lote = total_jogos_lote - green_count_lote
                taxa_acerto_lote = (green_count_lote / total_jogos_lote * 100) if total_jogos_lote > 0 else 0
                
                # Separar Over e Under no lote
                over_count_lote = sum(1 for j in lote if j.get('tipo_aposta') == "over")
                under_count_lote = sum(1 for j in lote if j.get('tipo_aposta') == "under")
                over_green_lote = sum(1 for j in lote if j.get('tipo_aposta') == "over" and j.get('resultado') == "GREEN")
                under_green_lote = sum(1 for j in lote if j.get('tipo_aposta') == "under" and j.get('resultado') == "GREEN")
                
                # Calcular estatísticas totais (todos os lotes desta data)
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
                    
                    # Registrar no histórico
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
                    
                    # Pequena pausa entre lotes para evitar sobrecarga
                    if lote_idx < len(lotes) - 1:
                        time.sleep(2)
                else:
                    st.error(f"❌ Falha ao enviar lote {lote_num} para {data_str}")
        
        if alertas_enviados > 0:
            st.success(f"✅ Total de {alertas_enviados} alertas de resultados enviados com sucesso!")
                
    except Exception as e:
        logging.error(f"Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        # Fallback para mensagem de texto
        enviar_resultados_fallback(jogos_com_resultado)

# =============================
# FUNÇÃO FALLBACK modificada para resultados
# =============================
def enviar_resultados_fallback(jogos_com_resultado: list, max_jogos_por_alerta: int = 5):
    """Fallback para mensagem de texto com limite de jogos por alerta"""
    if not jogos_com_resultado:
        return
        
    # Agrupar por data
    jogos_por_data = {}
    for jogo in jogos_com_resultado:
        data_jogo = datetime.fromisoformat(jogo["data"].replace("Z", "+00:00")).date()
        if data_jogo not in jogos_por_data:
            jogos_por_data[data_jogo] = []
        jogos_por_data[data_jogo].append(jogo)
    
    for data, jogos_data in jogos_por_data.items():
        data_str = data.strftime("%d/%m/%Y")
        
        # Dividir em lotes
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
            
            # Adicionar estatísticas do lote
            total_jogos_lote = len(lote)
            green_count_lote = sum(1 for j in lote if "🟢 GREEN" in str(j.get('resultado', '')))
            taxa_acerto_lote = (green_count_lote / total_jogos_lote * 100) if total_jogos_lote > 0 else 0
            
            msg += f"\n<b>📊 LOTE {lote_num}:</b> {green_count_lote}/{total_jogos_lote} GREEN ({taxa_acerto_lote:.1f}%)\n"
            
            enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            # Pausa entre lotes
            if lote_idx < len(lotes) - 1:
                time.sleep(2)
        
        # Enviar resumo final da data
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
        # Separar Over e Under
        over_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "over"]
        under_jogos = [j for j in jogos_conf if j.get('tipo_aposta') == "under"]
        
        msg = f"🔥 Jogos com confiança {min_conf}%-{max_conf}% (Estilo Original):\n\n"
        
        if over_jogos:
            msg += f"📈 <b>OVER ({len(over_jogos)} jogos):</b>\n\n"
            for j in over_jogos:
                hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                
                # Adicionar análises extras se disponíveis
                analise_extras = ""
                if 'detalhes' in j and 'vitoria' in j['detalhes']:
                    v = j['detalhes']['vitoria']
                    analise_extras += f"🏆 Favorito: {j['home'] if v['favorito']=='home' else j['away'] if v['favorito']=='away' else 'EMPATE'} ({max(v['home_win'], v['away_win'], v['draw'])}%) | "
                if 'detalhes' in j and 'gols_ht' in j['detalhes']:
                    ht = j['detalhes']['gols_ht']
                    analise_extras += f"⏰ HT: {ht['tendencia_ht']} ({ht['confianca_ht']}%)"
                
                msg += f"• {hora_format} - {j['home']} vs {j['away']}\n"
                msg += f"  {j['tendencia']} | Est: {j['estimativa']:.2f} | Prob: {j['probabilidade']:.0f}% | Conf: {j['confianca']:.0f}%\n"
                if analise_extras:
                    msg += f"  {analise_extras}\n"
                msg += f"  {j['liga']}\n\n"
        
        if under_jogos:
            msg += f"📉 <b>UNDER ({len(under_jogos)} jogos):</b>\n\n"
            for j in under_jogos:
                hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                
                # Adicionar análises extras se disponíveis
                analise_extras = ""
                if 'detalhes' in j and 'vitoria' in j['detalhes']:
                    v = j['detalhes']['vitoria']
                    analise_extras += f"🏆 Favorito: {j['home'] if v['favorito']=='home' else j['away'] if v['favorito']=='away' else 'EMPATE'} ({max(v['home_win'], v['away_win'], v['draw'])}%) | "
                
                if 'detalhes' in j and 'gols_ht' in j['detalhes']:
                    ht = j['detalhes']['gols_ht']
                    analise_extras += f"⏰ HT: {ht['tendencia_ht']} ({ht['confianca_ht']}%)"
                
                msg += f"• {hora_format} - {j['home']} vs {j['away']}\n"
                msg += f"  {j['tendencia']} | Est: {j['estimativa']:.2f} | Prob: {j['probabilidade']:.0f}% | Conf: {j['confianca']:.0f}%\n"
                if analise_extras:
                    msg += f"  {analise_extras}\n"
                msg += f"  {j['liga']}\n\n"
        
        # Enviar mensagem longa dividida em partes se necessário
        if len(msg) > 4000:
            partes = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for parte in partes:
                enviar_telegram(parte, chat_id=chat_id)
                time.sleep(1)
        else:
            enviar_telegram(msg, chat_id=chat_id)
            
    except Exception as e:
        st.error(f"Erro ao enviar alerta estilo original: {e}")

# =============================
# Funções de Processamento Principal
# =============================

def processar_ligas_com_criar_poster(dias: int = 0, min_conf: int = 70, max_conf: int = 95, alerta_individual: bool = True, tipo_analise: str = "Over/Under de Gols", config_analise: dict = None):
    """Processa todas as ligas e envia alertas - VERSÃO ATUALIZADA COM NOVAS ANÁLISES"""
    data_hoje = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    
    st.info(f"📅 Data de análise: {data_hoje}")
    st.info(f"🎯 Intervalo de confiança: {min_conf}% - {max_conf}%")
    
    total_jogos_analisados = 0
    jogos_confiaveis = []
    jogos_com_analise = []
    
    with st.spinner("🔄 Analisando ligas..."):
        for liga_nome, liga_id in LIGA_DICT.items():
            try:
                st.write(f"🔍 Analisando {liga_nome} ({liga_id})...")
                
                # Obter classificação
                classificacao = obter_classificacao(liga_id)
                if not classificacao:
                    st.warning(f"⚠️ Sem dados de classificação para {liga_nome}")
                    continue
                
                # Obter jogos
                jogos = obter_jogos(liga_id, data_hoje)
                if not jogos:
                    continue
                
                st.write(f"⚽ {len(jogos)} jogos encontrados")
                
                for match in jogos:
                    if not validar_dados_jogo(match):
                        continue
                    
                    total_jogos_analisados += 1
                    home = match["homeTeam"]["name"]
                    away = match["awayTeam"]["name"]
                    
                    # Analisar tendência COMPLETA (com vitória e gols HT)
                    analise = calcular_tendencia_completa(home, away, classificacao)
                    
                    if analise and "tendencia" in analise:
                        hora_jogo = formatar_data_iso_para_datetime(match["utcDate"])
                        
                        # Obter URLs dos escudos
                        escudo_home = match.get("homeTeam", {}).get("crest") or match.get("homeTeam", {}).get("logo", "")
                        escudo_away = match.get("awayTeam", {}).get("crest") or match.get("awayTeam", {}).get("logo", "")
                        
                        jogo_info = {
                            "id": match["id"],
                            "home": home,
                            "away": away,
                            "tendencia": analise["tendencia"],
                            "estimativa": analise["estimativa"],
                            "probabilidade": analise["probabilidade"],
                            "confianca": analise["confianca"],
                            "tipo_aposta": analise["tipo_aposta"],
                            "detalhes": analise.get("detalhes", {}),
                            "liga": liga_nome,
                            "hora": hora_jogo,
                            "status": match.get("status", "SCHEDULED"),
                            "escudo_home": escudo_home,
                            "escudo_away": escudo_away
                        }
                        
                        jogos_com_analise.append(jogo_info)
                        
                        # Verificar se está dentro do intervalo de confiança
                        if min_conf <= analise["confianca"] <= max_conf:
                            jogos_confiaveis.append(jogo_info)
                            
                            # Enviar alerta individual se configurado
                            if alerta_individual:
                                verificar_enviar_alerta(match, analise, alerta_individual, min_conf, max_conf)
                
            except Exception as e:
                st.error(f"❌ Erro ao processar {liga_nome}: {e}")
                continue
    
    return {
        "data": data_hoje,
        "total_jogos": total_jogos_analisados,
        "jogos_analisados": jogos_com_analise,
        "jogos_confiaveis": jogos_confiaveis,
        "tipo_analise": tipo_analise
    }

# =============================
# Função Principal do Streamlit
# =============================

def main():
    st.set_page_config(
        page_title="Elite Master System - Análise Preditiva",
        page_icon="⚽",
        layout="wide"
    )
    
    # CSS personalizado
    st.markdown("""
    <style>
    .stButton > button {
        background: linear-gradient(45deg, #FF6B6B, #FFD93D);
        color: black;
        font-weight: bold;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        margin: 5px;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(45deg, #FFD93D, #FF6B6B);
        color: white;
    }
    .css-1d391kg {
        background-color: #0E1117;
    }
    .stAlert {
        border-radius: 10px;
        padding: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Título principal
    st.title("⚽ ELITE MASTER SYSTEM - ANÁLISE PREDITIVA COMPLETA")
    st.markdown("### 🔮 Sistema Inteligente de Análise de Jogos")
    
    # Sidebar com configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Data de análise
        dias_offset = st.number_input("📅 Dias a frente para análise", 
                                     min_value=0, max_value=7, value=0)
        
        # Tipo de análise
        tipo_analise = st.selectbox(
            "🎯 Tipo de Análise",
            ["Over/Under de Gols", "Favorito (Vitória)", "Gols HT (Primeiro Tempo)"]
        )
        
        # Configurações específicas por tipo
        config_analise = {}
        
        if tipo_analise == "Over/Under de Gols":
            min_conf = st.slider("🎯 Confiança mínima", 50, 95, 70)
            max_conf = st.slider("🎯 Confiança máxima", min_conf, 95, 95)
            config_analise = {
                "min_conf": min_conf,
                "max_conf": max_conf,
                "tipo_filtro": st.selectbox(
                    "📊 Filtro por tipo",
                    ["Todos", "Apenas Over", "Apenas Under"]
                )
            }
            
        elif tipo_analise == "Favorito (Vitória)":
            min_conf_vitoria = st.slider("🏆 Confiança mínima para vitória", 50, 95, 65)
            config_analise = {
                "min_conf_vitoria": min_conf_vitoria,
                "filtro_favorito": st.selectbox(
                    "🎯 Filtro de favorito",
                    ["Todos", "Casa", "Fora", "Empate"]
                )
            }
            
        else:  # Gols HT
            min_conf_ht = st.slider("⏰ Confiança mínima HT", 50, 95, 60)
            config_analise = {
                "min_conf_ht": min_conf_ht,
                "tipo_ht": st.selectbox(
                    "🎯 Tipo HT",
                    ["Todos", "OVER 0.5 HT", "OVER 1.5 HT", "UNDER 0.5 HT"]
                )
            }
        
        # Alertas individuais
        alerta_individual = st.checkbox("🔔 Enviar alertas individuais", value=False)
        
        # Botão de processamento
        if st.button("🚀 PROCESSAR LIGAS", type="primary"):
            with st.spinner("Analisando todas as ligas..."):
                resultados = processar_ligas_com_criar_poster(
                    dias=dias_offset,
                    min_conf=config_analise.get("min_conf", 70),
                    max_conf=config_analise.get("max_conf", 95),
                    alerta_individual=alerta_individual,
                    tipo_analise=tipo_analise,
                    config_analise=config_analise
                )
                
                st.session_state.resultados = resultados
        
        st.divider()
        
        # Seção de configurações avançadas
        st.subheader("⚡ Configurações Avançadas")
        
        # Configurações de cache
        if st.button("🧹 Limpar caches"):
            jogos_cache.clear()
            classificacao_cache.clear()
            match_cache.clear()
            escudos_cache.clear()
            st.success("✅ Caches limpos!")
        
        # Limpar histórico
        if st.button("🗑️ Limpar histórico"):
            limpar_historico()
        
        # Estatísticas da API
        if st.button("📊 Ver estatísticas API"):
            stats = api_monitor.get_stats()
            st.json(stats)
        
        # Configurações do Telegram
        st.divider()
        st.subheader("🤖 Configurações Telegram")
        
        chat_id_alt2 = st.text_input("📱 Chat ID Alternativo 2", value=TELEGRAM_CHAT_ID_ALT2)
        
        # Testar conexão
        if st.button("📡 Testar conexão Telegram"):
            if enviar_telegram("🔔 Teste de conexão - Elite Master System", chat_id=chat_id_alt2):
                st.success("✅ Conexão OK!")
            else:
                st.error("❌ Falha na conexão")
    
    # Conteúdo principal
    if "resultados" in st.session_state:
        resultados = st.session_state.resultados
        
        st.header(f"📊 Resultados da Análise - {resultados['data']}")
        
        # Estatísticas gerais
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Jogos", resultados["total_jogos"])
        with col2:
            st.metric("Jogos Analisados", len(resultados["jogos_analisados"]))
        with col3:
            st.metric("Jogos Confiáveis", len(resultados["jogos_confiaveis"]))
        
        # Filtragem por tipo de análise
        jogos_filtrados = filtrar_por_tipo_analise(
            resultados["jogos_confiaveis"], 
            resultados["tipo_analise"], 
            config_analise
        )
        
        if jogos_filtrados:
            st.success(f"✅ {len(jogos_filtrados)} jogos encontrados com os critérios especificados!")
            
            # Gerar poster específico
            if st.button("🎨 GERAR POSTER ESPECÍFICO"):
                poster = gerar_poster_por_tipo(jogos_filtrados, tipo_analise, config_analise)
                st.image(poster, use_column_width=True)
                
                # Opção para enviar
                if st.button("📤 ENVIAR POSTER PARA TELEGRAM"):
                    if tipo_analise == "Favorito (Vitória)":
                        titulo = f"🎯 ALERTA DE FAVORITOS - {resultados['data']}"
                        caption = f"<b>{titulo}</b>\n\nAnálise de probabilidade de vitória"
                    elif tipo_analise == "Gols HT (Primeiro Tempo)":
                        titulo = f"⏰ ALERTA GOLS HT - {resultados['data']}"
                        caption = f"<b>{titulo}</b>\n\nAnálise de gols no primeiro tempo"
                    else:
                        titulo = f"⚽ ALERTA OVER/UNDER - {resultados['data']}"
                        caption = f"<b>{titulo}</b>\n\nAnálise de gols totais"
                    
                    if enviar_foto_telegram(poster, caption=caption):
                        st.success("✅ Poster enviado!")
                    else:
                        st.error("❌ Falha ao enviar poster")
            
            # Tabela detalhada
            st.subheader("📋 Jogos Filtrados")
            for idx, jogo in enumerate(jogos_filtrados):
                with st.expander(f"{jogo['home']} vs {jogo['away']} - {jogo['liga']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Data/Hora:** {jogo['hora']}")
                        st.write(f"**Tendência:** {jogo['tendencia']}")
                        st.write(f"**Estimativa:** {jogo['estimativa']} gols")
                        st.write(f"**Probabilidade:** {jogo['probabilidade']}%")
                        st.write(f"**Confiança:** {jogo['confianca']}%")
                        st.write(f"**Tipo:** {jogo['tipo_aposta']}")
                    
                    with col2:
                        # Mostrar análise de vitória se disponível
                        if 'detalhes' in jogo and 'vitoria' in jogo['detalhes']:
                            v = jogo['detalhes']['vitoria']
                            st.write("**🏆 Análise de Vitória:**")
                            st.write(f"• Casa: {v['home_win']}%")
                            st.write(f"• Empate: {v['draw']}%")
                            st.write(f"• Fora: {v['away_win']}%")
                            st.write(f"• Favorito: {v['favorito']} ({v['confianca_vitoria']}%)")
                        
                        # Mostrar análise HT se disponível
                        if 'detalhes' in jogo and 'gols_ht' in jogo['detalhes']:
                            ht = jogo['detalhes']['gols_ht']
                            st.write("**⏰ Análise HT:**")
                            st.write(f"• Tendência: {ht['tendencia_ht']}")
                            st.write(f"• Confiança: {ht['confianca_ht']}%")
                            st.write(f"• Estimativa: {ht['estimativa_total_ht']} gols")
        else:
            st.warning("⚠️ Nenhum jogo encontrado com os critérios especificados")
    
    # Seção de Top N Jogos
    st.divider()
    st.header("🏆 TOP N JOGOS DO DIA")
    
    col1, col2 = st.columns(2)
    with col1:
        top_n = st.number_input("Número de jogos Top", min_value=1, max_value=20, value=5)
    with col2:
        min_conf_top = st.slider("Confiança mínima Top", 50, 95, 75)
    
    if st.button("🎯 GERAR TOP N JOGOS"):
        if "resultados" in st.session_state:
            # Filtrar jogos por confiança e ordenar
            jogos_conf = st.session_state.resultados.get("jogos_confiaveis", [])
            jogos_filtrados = [j for j in jogos_conf if j["confianca"] >= min_conf_top]
            jogos_ordenados = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)
            top_jogos = jogos_ordenados[:top_n]
            
            if top_jogos:
                # Gerar poster
                poster = gerar_poster_top_jogos(
                    top_jogos, 
                    min_conf=min_conf_top, 
                    max_conf=100,
                    titulo=f"🔥 TOP {len(top_jogos)} JOGOS"
                )
                st.image(poster, use_column_width=True)
                
                # Salvar como alertas TOP
                for jogo in top_jogos:
                    adicionar_alerta_top(jogo, st.session_state.resultados["data"])
                
                # Opção para enviar
                if st.button("📤 ENVIAR TOP N PARA TELEGRAM"):
                    caption = (
                        f"<b>🔥 TOP {len(top_jogos)} JOGOS DO DIA</b>\n\n"
                        f"<b>🎯 Selecionados pela IA com confiança ≥ {min_conf_top}%</b>\n\n"
                        f"<b>📊 Estatísticas:</b>\n"
                        f"<b>• Over: {sum(1 for j in top_jogos if j['tipo_aposta'] == 'over')} jogos</b>\n"
                        f"<b>• Under: {sum(1 for j in top_jogos if j['tipo_aposta'] == 'under')} jogos</b>\n"
                        f"<b>• Confiança média: {sum(j['confianca'] for j in top_jogos) / len(top_jogos):.1f}%</b>\n\n"
                        f"<b>🏆 ELITE MASTER SYSTEM - SELEÇÃO DE ALTA CONFIANÇA</b>"
                    )
                    
                    if enviar_foto_telegram(poster, caption=caption):
                        st.success("✅ Top N enviado!")
                    else:
                        st.error("❌ Falha ao enviar Top N")
            else:
                st.warning("⚠️ Nenhum jogo encontrado com confiança suficiente")
    
    # Seção de conferência de resultados
    st.divider()
    st.header("🏁 CONFERÊNCIA DE RESULTADOS")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 CONFERIR ALERTAS TOP"):
            conferir_resultados_top()
            
            # Verificar se há conjuntos completos para reportar
            conjuntos_completos = verificar_conjuntos_completos()
            if conjuntos_completos:
                st.info(f"📅 {len(conjuntos_completos)} conjunto(s) completo(s) para reportar")
                if st.button("📊 GERAR RELATÓRIO DE CONFERÊNCIA"):
                    enviar_alerta_top_conferidos()
    
    with col2:
        max_jogos = st.number_input("Máx jogos por alerta", min_value=1, max_value=10, value=3)
    
    with col3:
        if st.button("📊 VER DESEMPENHO TOP"):
            calcular_desempenho_alertas_top()
    
    # Histórico de conferências
    st.divider()
    st.header("📜 HISTÓRICO DE CONFERÊNCIAS")
    
    historico = carregar_historico()
    if historico:
        # Converter para DataFrame
        df = pd.DataFrame(historico[-50:])  # Últimas 50 entradas
        st.dataframe(df)
    else:
        st.info("📭 Nenhuma conferência registrada ainda")

# =============================
# Execução principal
# =============================
if __name__ == "__main__":
    main()    
