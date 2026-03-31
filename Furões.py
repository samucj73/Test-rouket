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
import shutil
import hashlib
import random

# =============================
# [NOVA] FUNÇÕES DO SISTEMA AUTÔNOMO PRO
# =============================

class SistemaApostasPro:
    """Sistema profissional de classificação e filtragem de apostas"""
    
    def __init__(self, alerts):
        self.alerts = alerts

    def calcular_score(self, alerta):
        prob = alerta['probabilidade']
        conf = alerta['confianca']
        return (prob * 0.6) + (conf * 0.4)

    def classificar_mercado(self, alerta):
        est = alerta['estimativa']
        prob = alerta['probabilidade']

        if est >= 2.5 and prob >= 65:
            return "OVER 2.5", 1.90
        elif est >= 2.1:
            return "OVER 1.5", 1.35
        elif est >= 1.8:
            return "UNDER 2.5", 1.55
        else:
            return "UNDER 1.5", 1.80

    def filtro_armadilha(self, alerta):
        prob = alerta['probabilidade']
        est = alerta['estimativa']

        if prob >= 75 and est < 2.1:
            return "UNDER 2.5"
        return None

    def processar_alertas(self):
        selecionados = []

        for alerta in self.alerts:
            score = self.calcular_score(alerta)

            if score < 70:
                continue

            mercado, odd = self.classificar_mercado(alerta)

            ajuste = self.filtro_armadilha(alerta)
            if ajuste:
                mercado = ajuste

            selecionados.append({
                "jogo": alerta['jogo'],
                "mercado": mercado,
                "odd": odd,
                "score": round(score, 2),
                "liga": alerta.get('liga', ''),
                "hora": alerta.get('hora', ''),
                "escudo_home": alerta.get('escudo_home', ''),
                "escudo_away": alerta.get('escudo_away', ''),
                "tendencia": alerta.get('tendencia', ''),
                "tipo_aposta": alerta.get('tipo_aposta', '')
            })

        return selecionados


def separar_por_nivel(jogos):
    elite = []
    bons = []
    risco = []

    for j in jogos:
        if j['score'] >= 85:
            elite.append(j)
        elif j['score'] >= 75:
            bons.append(j)
        else:
            risco.append(j)

    return elite, bons, risco


def gerar_multiplas(elite, bons, risco):
    multiplas = []

    if len(elite) >= 3:
        segura = random.sample(elite, min(4, len(elite)))
        multiplas.append(("SEGURA", segura))

    if len(elite) >= 2 and len(bons) >= 2:
        balanceada = random.sample(elite, 2) + random.sample(bons, 2)
        multiplas.append(("BALANCEADA", balanceada))

    pool = elite + bons + risco
    if len(pool) >= 5:
        agressiva = random.sample(pool, 5)
        multiplas.append(("AGRESSIVA", agressiva))

    return multiplas


def calcular_odd_total(multipla):
    total = 1.0
    for jogo in multipla:
        total *= jogo['odd']
    return round(total, 2)


class ConfigManager:
    """Gerencia configurações e constantes do sistema"""
    
    API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","8351165117:AAFmqb3NrPsmT86_8C360eYzK71Qda1ah_4")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
    TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
    
    HEADERS = {"X-Auth-Token": API_KEY}
    BASE_URL_FD = "https://api.football-data.org/v4"
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
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
    MULTIPLAS_PATH = "multiplas.json"
    RESULTADOS_MULTIPLAS_PATH = "resultados_multiplas.json"
    
    MODELO_PERFORMANCE_PATH = "modelo_performance.json"
    
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
    
    CACHE_CONFIG = {
        "jogos": {"ttl": 3600, "max_size": 100},
        "classificacao": {"ttl": 86400, "max_size": 50},
        "match_details": {"ttl": 1800, "max_size": 200}
    }
    
    @classmethod
    def get_liga_id(cls, liga_nome):
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
                "uptime_minutes": round(elapsed / 60, 1)
            }
    
    def reset(self):
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
        combined = f"{team_name}_{crest_url}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            try:
                if os.path.exists(self.cache_dir):
                    shutil.rmtree(self.cache_dir)
                    os.makedirs(self.cache_dir, exist_ok=True)
            except:
                pass
    
    def get_stats(self):
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


class GeradorMultiplasProfissional:
    """GERADOR DE MÚLTIPLAS 3.0 - ELITE MASTER"""
    
    LIGAS_OVER_RECOMMENDED = ["Bundesliga", "Eredivisie", "Premier League"]
    LIGAS_OVER_WITH_FILTER = ["Ligue 1", "Serie A"]
    LIGAS_OVER_AVOID = ["Campeonato Brasileiro Série A", "Primera Division"]
    
    def __init__(self):
        self.analisador_performance = None
    
    def classificar_jogo(self, jogo: dict) -> dict:
        liga = jogo.get("liga", "")
        estimativa = jogo.get("estimativa", 0.0)
        confianca = jogo.get("confianca", 0.0)
        tipo_aposta = jogo.get("tipo_aposta", "")
        tendencia = jogo.get("tendencia", "")
        ambas_marcam = jogo.get("tendencia_ambas_marcam", "")
        confianca_am = jogo.get("confianca_ambas_marcam", 0.0)
        
        nivel_a = False
        if "OVER" in tendencia.upper() and "1.5" in tendencia:
            if estimativa >= 2.2 and confianca >= 75:
                nivel_a = True
        
        nivel_b = False
        if "OVER" in tendencia.upper() and "2.5" in tendencia:
            if estimativa >= 2.7 and ambas_marcam == "SIM" and confianca_am >= 60:
                nivel_b = True
        
        nivel_c = False
        motivo_c = ""
        
        tendencia_ht = jogo.get("tendencia_ht", "")
        if tendencia_ht and "HT" in tendencia_ht:
            nivel_c = True
            motivo_c = "Gols HT"
        
        favorito = jogo.get("favorito", "")
        if favorito and favorito != "":
            nivel_c = True
            motivo_c = "Favorito"
        
        if estimativa < 2.0 and "OVER" in tendencia.upper():
            nivel_c = True
            motivo_c = f"Estimativa baixa ({estimativa:.2f})"
        
        liga_base = liga.split("(")[0].strip() if "(" in liga else liga
        
        if liga_base in self.LIGAS_OVER_AVOID:
            if "OVER" in tendencia.upper():
                nivel_c = True
                motivo_c = f"Liga evitar Over ({liga_base})"
        
        if nivel_c:
            return {
                "nivel": "C",
                "cor": "🔴",
                "motivo": motivo_c,
                "recomendacao": "EXCLUIR",
                "tipo": "perigo",
                "estimativa": estimativa,
                "confianca": confianca
            }
        elif nivel_b:
            return {
                "nivel": "B",
                "cor": "🟡",
                "motivo": "Over 2.5 com ambas marcam",
                "recomendacao": "VALOR",
                "tipo": "over_2.5",
                "estimativa": estimativa,
                "confianca": confianca,
                "confianca_am": confianca_am
            }
        elif nivel_a:
            return {
                "nivel": "A",
                "cor": "🟢",
                "motivo": "Over 1.5 seguro",
                "recomendacao": "SEGURO",
                "tipo": "over_1.5",
                "estimativa": estimativa,
                "confianca": confianca
            }
        else:
            return {
                "nivel": "D",
                "cor": "⚪",
                "motivo": "Não se enquadra nos critérios",
                "recomendacao": "DESCARTAR",
                "tipo": "descartar",
                "estimativa": estimativa,
                "confianca": confianca
            }
    
    def gerar_multipla(self, jogos_classificados: list, modelo: str = "hibrido") -> dict:
        nivel_a = [j for j in jogos_classificados if j.get("classificacao", {}).get("nivel") == "A"]
        nivel_b = [j for j in jogos_classificados if j.get("classificacao", {}).get("nivel") == "B"]
        
        if modelo == "conservador":
            if len(nivel_a) < 3:
                return self._gerar_multipla_fallback(jogos_classificados, "conservador")
            
            jogos_selecionados = nivel_a[:3]
            odd_total = self._calcular_odd_total(jogos_selecionados)
            
            return {
                "modelo": "🟢 CONSERVADOR",
                "jogos": jogos_selecionados,
                "total_jogos": len(jogos_selecionados),
                "over_1.5_count": len([j for j in jogos_selecionados if j.get("classificacao", {}).get("tipo") == "over_1.5"]),
                "over_2.5_count": 0,
                "odd_total": odd_total,
                "odd_media": odd_total / len(jogos_selecionados) if jogos_selecionados else 0,
                "risco": "BAIXO",
                "taxa_acerto_esperada": "MUITO ALTA",
                "recomendacao": "Ideal para consistência diária"
            }
        
        elif modelo == "hibrido":
            if len(nivel_a) < 3 or len(nivel_b) < 1:
                return self._gerar_multipla_fallback(jogos_classificados, "hibrido")
            
            jogos_selecionados = nivel_a[:3] + nivel_b[:1]
            odd_total = self._calcular_odd_total(jogos_selecionados)
            
            return {
                "modelo": "🔥 HÍBRIDO (PROFISSIONAL)",
                "jogos": jogos_selecionados,
                "total_jogos": len(jogos_selecionados),
                "over_1.5_count": 3,
                "over_2.5_count": 1,
                "odd_total": odd_total,
                "odd_media": odd_total / len(jogos_selecionados) if jogos_selecionados else 0,
                "risco": "MÉDIO",
                "taxa_acerto_esperada": "ALTA",
                "recomendacao": "ESTRATÉGIA PRINCIPAL - Melhor equilíbrio risco/retorno"
            }
        
        elif modelo == "agressivo":
            if len(nivel_a) < 3 or len(nivel_b) < 2:
                return self._gerar_multipla_fallback(jogos_classificados, "agressivo")
            
            jogos_selecionados = nivel_a[:3] + nivel_b[:2]
            odd_total = self._calcular_odd_total(jogos_selecionados)
            
            return {
                "modelo": "💣 AGRESSIVO",
                "jogos": jogos_selecionados,
                "total_jogos": len(jogos_selecionados),
                "over_1.5_count": 3,
                "over_2.5_count": 2,
                "odd_total": odd_total,
                "odd_media": odd_total / len(jogos_selecionados) if jogos_selecionados else 0,
                "risco": "ALTO",
                "taxa_acerto_esperada": "MODERADA",
                "recomendacao": "Usar só com seleção TOP de jogos"
            }
        
        else:
            return self._gerar_multipla_fallback(jogos_classificados, "hibrido")
    
    def _gerar_multipla_fallback(self, jogos_classificados: list, modelo: str) -> dict:
        jogos_ordenados = sorted(
            jogos_classificados,
            key=lambda x: (
                x.get("classificacao", {}).get("nivel") == "A",
                x.get("classificacao", {}).get("nivel") == "B",
                x.get("confianca", 0)
            ),
            reverse=True
        )
        
        total_jogos = 3 if modelo == "conservador" else 4 if modelo == "hibrido" else 5
        jogos_selecionados = jogos_ordenados[:min(total_jogos, len(jogos_ordenados))]
        
        if len(jogos_selecionados) < 3:
            return None
        
        over_1_5 = sum(1 for j in jogos_selecionados if j.get("classificacao", {}).get("tipo") == "over_1.5")
        over_2_5 = sum(1 for j in jogos_selecionados if j.get("classificacao", {}).get("tipo") == "over_2.5")
        
        odd_total = self._calcular_odd_total(jogos_selecionados)
        
        return {
            "modelo": f"⚠️ FALLBACK ({modelo.upper()})",
            "jogos": jogos_selecionados,
            "total_jogos": len(jogos_selecionados),
            "over_1.5_count": over_1_5,
            "over_2.5_count": over_2_5,
            "odd_total": odd_total,
            "odd_media": odd_total / len(jogos_selecionados) if jogos_selecionados else 0,
            "risco": "VARIÁVEL",
            "taxa_acerto_esperada": "MODERADA",
            "recomendacao": "Múltipla gerada com jogos disponíveis"
        }
    
    def _calcular_odd_total(self, jogos: list) -> float:
        odd_total = 1.0
        
        for jogo in jogos:
            classificacao = jogo.get("classificacao", {})
            tipo = classificacao.get("tipo", "over_1.5")
            
            if tipo == "over_1.5":
                prob = jogo.get("probabilidade", 65)
            elif tipo == "over_2.5":
                prob = jogo.get("probabilidade", 55)
            else:
                prob = jogo.get("confianca", 60)
            
            odd_jogo = 100 / max(prob, 10)
            odd_total *= odd_jogo
        
        return round(odd_total, 2)
    
    def gerar_todas_multiplas(self, jogos_classificados: list) -> list:
        multiplas = []
        
        cons = self.gerar_multipla(jogos_classificados, "conservador")
        if cons:
            multiplas.append(cons)
        
        hib = self.gerar_multipla(jogos_classificados, "hibrido")
        if hib:
            multiplas.append(hib)
        
        agr = self.gerar_multipla(jogos_classificados, "agressivo")
        if agr:
            multiplas.append(agr)
        
        return multiplas
    
    def gerar_texto_multipla(self, multipla: dict) -> str:
        texto = f"💣 **{multipla['modelo']}**\n"
        texto += f"🎯 **Odds Total:** {multipla['odd_total']:.2f}\n"
        texto += f"📊 **Composição:** {multipla['over_1.5_count']}x Over 1.5 + {multipla['over_2.5_count']}x Over 2.5\n"
        texto += f"⚠️ **Risco:** {multipla['risco']} | 📈 **Taxa Esperada:** {multipla['taxa_acerto_esperada']}\n\n"
        
        for i, jogo in enumerate(multipla["jogos"], 1):
            classificacao = jogo.get("classificacao", {})
            tipo = classificacao.get("tipo", "over_1.5")
            tendencia = jogo.get("tendencia", "Over 1.5")
            
            if tipo == "over_1.5":
                emoji = "🟢"
                texto_tendencia = f"Over 1.5 ({tendencia})"
            else:
                emoji = "🟡"
                texto_tendencia = f"Over 2.5 ({tendencia})"
            
            odd_jogo = 100 / max(jogo.get("probabilidade", 65), 10)
            
            texto += f"{i}. {emoji} **{jogo['home']} vs {jogo['away']}**\n"
            texto += f"   📊 {texto_tendencia}\n"
            texto += f"   ⚽ Estimativa: {classificacao.get('estimativa', 0):.2f} | 🔍 Conf: {classificacao.get('confianca', 0):.0f}%\n"
            texto += f"   💰 Odd: {odd_jogo:.2f}\n"
            texto += f"   🏷️ Liga: {jogo.get('liga', 'Desconhecida')}\n\n"
        
        texto += f"📌 **Recomendação:** {multipla['recomendacao']}\n"
        
        return texto


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
        dados = DataStorage.carregar_json(ConfigManager.ALERTAS_TOP_PATH)
        if not isinstance(dados, dict):
            return {}
        return dados
    
    @staticmethod
    def salvar_alertas_top(alertas_top: dict):
        if not isinstance(alertas_top, dict):
            alertas_top = {}
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
    def carregar_multiplas() -> dict:
        return DataStorage.carregar_json(ConfigManager.MULTIPLAS_PATH)
    
    @staticmethod
    def salvar_multiplas(multiplas: dict):
        DataStorage.salvar_json(ConfigManager.MULTIPLAS_PATH, multiplas)
    
    @staticmethod
    def carregar_resultados_multiplas() -> dict:
        return DataStorage.carregar_json(ConfigManager.RESULTADOS_MULTIPLAS_PATH)
    
    @staticmethod
    def salvar_resultados_multiplas(resultados: dict):
        DataStorage.salvar_json(ConfigManager.RESULTADOS_MULTIPLAS_PATH, resultados)
    
    @staticmethod
    def carregar_historico() -> list:
        if os.path.exists(ConfigManager.HISTORICO_PATH):
            try:
                with open(ConfigManager.HISTORICO_PATH, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    return dados if isinstance(dados, list) else []
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


def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))

def sigmoid(x):
    return 1 / (1 + math.exp(-x))


class AnalisadorPerformance:
    def __init__(self):
        self.historico = self._carregar_historico()
        
    def _carregar_historico(self) -> dict:
        return DataStorage.carregar_performance_modelo()
    
    def _salvar_historico(self):
        DataStorage.salvar_performance_modelo(self.historico)
    
    def registrar_resultado(self, alerta: dict, tipo_alerta: str, resultado: str, metadata: dict):
        chave = f"{tipo_alerta}_{datetime.now().strftime('%Y%m')}"
        
        if chave not in self.historico:
            self.historico[chave] = {
                "total": 0,
                "greens": 0,
                "reds": 0,
                "por_liga": {},
                "por_faixa_confianca": {},
                "por_tipo": {},
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
        if liga not in hist["por_liga"]:
            hist["por_liga"][liga] = {"total": 0, "greens": 0}
        hist["por_liga"][liga]["total"] += 1
        if resultado == "GREEN":
            hist["por_liga"][liga]["greens"] += 1
        
        confianca = alerta.get("confianca", 0)
        faixa = f"{int(confianca // 10 * 10)}-{int(confianca // 10 * 10 + 9)}"
        if faixa not in hist["por_faixa_confianca"]:
            hist["por_faixa_confianca"][faixa] = {"total": 0, "greens": 0}
        hist["por_faixa_confianca"][faixa]["total"] += 1
        if resultado == "GREEN":
            hist["por_faixa_confianca"][faixa]["greens"] += 1
        
        tipo_aposta = alerta.get("tipo_aposta", "unknown")
        if tipo_aposta not in hist["por_tipo"]:
            hist["por_tipo"][tipo_aposta] = {"total": 0, "greens": 0}
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


class AnalisadorEstatistico:
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


class SistemaAutonomoApostas:
    def __init__(self):
        self.config = ConfigManager()
        
        self.LIGAS_CONFIG = {
            "Eredivisie": {"over": 1.2, "btts": 1.1, "ht": 1.0, "favorito": 1.0},
            "Bundesliga": {"over": 1.2, "btts": 1.2, "ht": 1.1, "favorito": 1.0},
            "Championship": {"over": 0.9, "btts": 1.3, "ht": 0.9, "favorito": 1.0},
            "Premier League": {"over": 1.0, "btts": 1.0, "ht": 0.9, "favorito": 0.9},
            "Primera Division": {"over": 0.9, "btts": 0.8, "ht": 0.8, "favorito": 1.0},
            "Ligue 1": {"over": 0.8, "btts": 0.7, "ht": 0.7, "favorito": 1.0},
            "Primeira Liga": {"over": 0.7, "btts": 1.0, "ht": 0.5, "favorito": 1.0},
            "Serie A": {"over": 1.0, "btts": 0.9, "ht": 0.8, "favorito": 1.0},
            "Campeonato Brasileiro Série A": {"over": 0.8, "btts": 0.8, "ht": 0.7, "favorito": 1.1}
        }
        
        self.ligas_identificacao = {
            "Eredivisie": "Eredivisie",
            "Bundesliga": "Bundesliga",
            "Championship": "Championship",
            "Premier League": "Premier League",
            "Primera Division": "Primera Division",
            "Ligue 1": "Ligue 1",
            "Primeira Liga": "Primeira Liga",
            "Serie A": "Serie A",
            "Campeonato Brasileiro Série A": "Campeonato Brasileiro Série A"
        }
    
    def _identificar_liga(self, liga_nome: str) -> str:
        for key in self.ligas_identificacao:
            if key in liga_nome:
                return key
        return "Premier League"
    
    def _ajustar_confianca(self, confianca_base: float, liga: str, mercado: str) -> float:
        peso = self.LIGAS_CONFIG.get(liga, {}).get(mercado, 1.0)
        conf_ajustada = confianca_base * peso
        conf_ajustada = clamp(conf_ajustada, 0, 1)
        return conf_ajustada
    
    def _validar_aposta(self, liga: str, mercado: str, confianca_ajustada: float) -> tuple:
        if mercado == "ht":
            if liga in ["Primeira Liga", "Ligue 1"]:
                return False, f"❌ HT bloqueado na liga {liga} (baixa performance)"
            if confianca_ajustada < 0.75:
                return False, f"❌ Confiança HT baixa: {confianca_ajustada*100:.0f}% < 75%"
        
        if mercado == "favorito":
            if confianca_ajustada < 0.55:
                return False, f"❌ Confiança favorito baixa: {confianca_ajustada*100:.0f}% < 55%"
        
        if mercado == "over":
            if liga == "Primeira Liga" and confianca_ajustada < 0.80:
                return False, f"❌ OVER em Portugal requer confiança ≥ 80%"
        
        if mercado == "btts":
            if liga == "Ligue 1":
                return False, f"❌ BTTS bloqueado na Ligue 1 (baixa performance)"
        
        return True, "Aprovado"
    
    def _extrair_confiancas(self, jogo_dict: dict) -> dict:
        return {
            "over": jogo_dict.get("confianca", 0) / 100,
            "btts": jogo_dict.get("confianca_ambas_marcam", 0) / 100,
            "ht": jogo_dict.get("confianca_ht", 0) / 100,
            "favorito": jogo_dict.get("confianca_vitoria", 0) / 100
        }
    
    def escolher_melhor_mercado(self, jogo_dict: dict) -> dict:
        liga = self._identificar_liga(jogo_dict.get("liga", ""))
        confiancas = self._extrair_confiancas(jogo_dict)
        
        melhores = []
        
        for mercado, conf_base in confiancas.items():
            if conf_base < 0.30:
                continue
                
            conf_ajustada = self._ajustar_confianca(conf_base, liga, mercado)
            aprovado, motivo = self._validar_aposta(liga, mercado, conf_ajustada)
            
            if aprovado:
                melhores.append({
                    "mercado": mercado,
                    "confianca_original": conf_base,
                    "confianca_ajustada": conf_ajustada,
                    "aprovado": True,
                    "motivo": motivo
                })
        
        if not melhores:
            return {
                "mercado": None,
                "confianca_original": 0,
                "confianca_ajustada": 0,
                "aprovado": False,
                "motivo": "❌ Nenhum mercado aprovado",
                "nivel": "❌ DESCARTADO"
            }
        
        melhores.sort(key=lambda x: x["confianca_ajustada"], reverse=True)
        melhor = melhores[0]
        
        if melhor["confianca_ajustada"] >= 0.80:
            nivel = "🔥 ELITE"
        elif melhor["confianca_ajustada"] >= 0.70:
            nivel = "💎 PREMIUM"
        elif melhor["confianca_ajustada"] >= 0.60:
            nivel = "⚠️ MODERADO"
        else:
            nivel = "📊 BAIXO"
        
        melhor["nivel"] = nivel
        melhor["liga"] = liga
        
        return melhor
    
    def processar_jogos_autonomo(self, jogos_analisados: list, tipos_analise_selecionados: dict, score_minimo: int = 6) -> dict:
        aprovados = []
        reprovados = []
        estatisticas_mercados = defaultdict(int)
        
        for jogo_dict in jogos_analisados:
            jogo_completo = self.extrair_dados_para_analise(jogo_dict)
            
            decisao = self.escolher_melhor_mercado(jogo_completo)
            
            if not decisao["aprovado"]:
                reprovados.append({
                    "jogo": jogo_dict,
                    "motivo": decisao["motivo"],
                    "decisao": decisao
                })
                continue
            
            jogo_completo["decisao_autonomo"] = decisao
            jogo_completo["mercado_escolhido"] = decisao["mercado"]
            jogo_completo["confianca_final"] = decisao["confianca_ajustada"] * 100
            
            if decisao["mercado"] == "over":
                jogo_completo["tendencia"] = jogo_dict.get("tendencia", "OVER")
                jogo_completo["confianca"] = decisao["confianca_ajustada"] * 100
            elif decisao["mercado"] == "btts":
                jogo_completo["tendencia_ambas_marcam"] = jogo_dict.get("tendencia_ambas_marcam", "SIM")
                jogo_completo["confianca_ambas_marcam"] = decisao["confianca_ajustada"] * 100
            elif decisao["mercado"] == "ht":
                jogo_completo["tendencia_ht"] = jogo_dict.get("tendencia_ht", "OVER 0.5 HT")
                jogo_completo["confianca_ht"] = decisao["confianca_ajustada"] * 100
            elif decisao["mercado"] == "favorito":
                jogo_completo["favorito"] = jogo_dict.get("favorito", "home")
                jogo_completo["confianca_vitoria"] = decisao["confianca_ajustada"] * 100
            
            jogo_completo["odd_sugerida"] = self.calcular_odd_sugerida(jogo_completo, decisao["mercado"])
            
            jogo_completo["analise_profissional"] = self.calcular_score_profissional_v2(jogo_completo, decisao)
            
            if jogo_completo["analise_profissional"]["score"] >= score_minimo:
                aprovados.append(jogo_completo)
                estatisticas_mercados[decisao["mercado"]] += 1
            else:
                reprovados.append({
                    "jogo": jogo_dict,
                    "motivo": f"Score baixo: {jogo_completo['analise_profissional']['score']} - {jogo_completo['analise_profissional']['nivel']}",
                    "decisao": decisao
                })
        
        aprovados.sort(key=lambda x: x["analise_profissional"]["score"], reverse=True)
        
        multiplas = self.gerar_multiplas_inteligentes_v2(aprovados)
        
        stats = {
            "total_analisados": len(jogos_analisados),
            "total_aprovados": len(aprovados),
            "total_reprovados": len(reprovados),
            "taxa_aprovacao": (len(aprovados) / len(jogos_analisados) * 100) if jogos_analisados else 0,
            "media_score_aprovados": sum(j["analise_profissional"]["score"] for j in aprovados) / len(aprovados) if aprovados else 0,
            "premium_count": sum(1 for j in aprovados if j["analise_profissional"]["score"] >= 12),
            "forte_count": sum(1 for j in aprovados if 9 <= j["analise_profissional"]["score"] < 12),
            "medio_count": sum(1 for j in aprovados if 6 <= j["analise_profissional"]["score"] < 9),
            "mercados": dict(estatisticas_mercados)
        }
        
        return {
            "aprovados": aprovados,
            "reprovados": reprovados,
            "multiplas": multiplas,
            "estatisticas": stats
        }
    
    def calcular_score_profissional_v2(self, jogo_dict: dict, decisao: dict) -> dict:
        score = 0
        detalhes = {
            "mercado_bonus": 0,
            "confianca_bonus": 0,
            "liga_bonus": 0,
            "odd_bonus": 0
        }
        
        mercado = decisao["mercado"]
        if mercado == "over":
            score += 3
            detalhes["mercado_bonus"] = 3
        elif mercado == "btts":
            score += 2
            detalhes["mercado_bonus"] = 2
        elif mercado == "ht":
            score += 1
            detalhes["mercado_bonus"] = 1
        elif mercado == "favorito":
            score += 2
            detalhes["mercado_bonus"] = 2
        
        conf_ajustada = decisao["confianca_ajustada"] * 100
        if conf_ajustada >= 80:
            score += 4
            detalhes["confianca_bonus"] = 4
        elif conf_ajustada >= 70:
            score += 3
            detalhes["confianca_bonus"] = 3
        elif conf_ajustada >= 60:
            score += 2
            detalhes["confianca_bonus"] = 2
        elif conf_ajustada >= 50:
            score += 1
            detalhes["confianca_bonus"] = 1
        
        liga = decisao.get("liga", "")
        if liga == "Eredivisie":
            score += 2
            detalhes["liga_bonus"] = 2
        elif liga in ["Bundesliga", "Premier League"]:
            score += 1
            detalhes["liga_bonus"] = 1
        
        odd = jogo_dict.get("odd_sugerida", 2.0)
        if 1.40 <= odd <= 2.20:
            score += 2
            detalhes["odd_bonus"] = 2
        elif 1.20 <= odd <= 2.50:
            score += 1
            detalhes["odd_bonus"] = 1
        
        if score >= 12:
            nivel = "🔥 ELITE (ALTÍSSIMA CONFIANÇA)"
            cor = "#FFD700"
            emoji = "💎"
        elif score >= 9:
            nivel = "✅ PREMIUM (ALTA PROBABILIDADE)"
            cor = "#4CAF50"
            emoji = "🎯"
        elif score >= 6:
            nivel = "⚠️ MODERADO (ANALISAR COM CUIDADO)"
            cor = "#FF9800"
            emoji = "⚡"
        elif score >= 3:
            nivel = "📊 BAIXO (APOSTA DE RISCO)"
            cor = "#F44336"
            emoji = "⚠️"
        else:
            nivel = "❌ DESCARTAR (NÃO RECOMENDADO)"
            cor = "#9E9E9E"
            emoji = "🚫"
        
        return {
            "score": score,
            "nivel": nivel,
            "cor": cor,
            "emoji": emoji,
            "detalhes": detalhes
        }
    
    def gerar_multiplas_inteligentes_v2(self, jogos_aprovados: list, max_por_multipla: int = 3) -> list:
        if len(jogos_aprovados) < 2:
            return []
        
        multiplas = []
        
        elite = [j for j in jogos_aprovados if j["analise_profissional"]["score"] >= 12]
        premium = [j for j in jogos_aprovados if 9 <= j["analise_profissional"]["score"] < 12]
        
        for i in range(0, len(elite), max_por_multipla):
            bloco = elite[i:i+max_por_multipla]
            if len(bloco) >= 2:
                odd_total = sum(j.get("odd_sugerida", 2.0) for j in bloco)
                multipla_id = f"elite_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                multiplas.append({
                    "id": multipla_id,
                    "tipo": "🔥 ELITE",
                    "jogos": bloco,
                    "score_total": sum(j["analise_profissional"]["score"] for j in bloco),
                    "odd_total": round(odd_total, 2),
                    "risco": "BAIXO",
                    "data_criacao": datetime.now().isoformat(),
                    "jogos_conferidos": [],
                    "enviada": False
                })
        
        for i in range(0, len(premium), max_por_multipla):
            bloco = premium[i:i+max_por_multipla]
            if len(bloco) >= 2:
                odd_total = sum(j.get("odd_sugerida", 2.0) for j in bloco)
                multipla_id = f"premium_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                multiplas.append({
                    "id": multipla_id,
                    "tipo": "💎 PREMIUM",
                    "jogos": bloco,
                    "score_total": sum(j["analise_profissional"]["score"] for j in bloco),
                    "odd_total": round(odd_total, 2),
                    "risco": "MÉDIO",
                    "data_criacao": datetime.now().isoformat(),
                    "jogos_conferidos": [],
                    "enviada": False
                })
        
        holanda_jogos = [j for j in jogos_aprovados if "Eredivisie" in j.get("liga", "")]
        if holanda_jogos:
            melhor_holanda = max(holanda_jogos, key=lambda x: x["analise_profissional"]["score"])
            outros_melhores = [j for j in jogos_aprovados if j != melhor_holanda][:2]
            if outros_melhores:
                bloco = [melhor_holanda] + outros_melhores
                odd_total = sum(j.get("odd_sugerida", 2.0) for j in bloco)
                multipla_id = f"holanda_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                multiplas.append({
                    "id": multipla_id,
                    "tipo": "🇳🇱 HOLANDA OBRIGATÓRIA",
                    "jogos": bloco,
                    "score_total": sum(j["analise_profissional"]["score"] for j in bloco),
                    "odd_total": round(odd_total, 2),
                    "risco": "BAIXO/MÉDIO",
                    "data_criacao": datetime.now().isoformat(),
                    "jogos_conferidos": [],
                    "enviada": False
                })
        
        multiplas.sort(key=lambda x: x["score_total"], reverse=True)
        return multiplas[:5]
    
    def calcular_odd_sugerida(self, jogo_dict: dict, mercado: str) -> float:
        if mercado == "over":
            prob = jogo_dict.get("probabilidade", 50)
            odd = round(100 / prob, 2) if prob > 0 else 2.0
        elif mercado == "btts":
            prob = jogo_dict.get("prob_ambas_marcam_sim", 50)
            odd = round(100 / prob, 2) if prob > 0 else 2.0
        elif mercado == "ht":
            prob = jogo_dict.get("confianca_ht", 50)
            odd = round(100 / prob, 2) if prob > 0 else 2.0
        elif mercado == "favorito":
            prob = jogo_dict.get("confianca_vitoria", 50)
            odd = round(100 / prob, 2) if prob > 0 else 2.0
        else:
            odd = 2.0
        
        return round(odd, 2)
    
    def extrair_dados_para_analise(self, jogo_dict: dict) -> dict:
        dados = jogo_dict.copy()
        
        dados["gols_casa"] = jogo_dict.get("estimativa", 1.5) * 0.55
        dados["gols_fora"] = jogo_dict.get("estimativa", 1.5) * 0.45
        dados["media_total"] = jogo_dict.get("estimativa", 1.5)
        
        return dados
    
    def gerar_texto_multipla(self, multipla: dict) -> str:
        texto = f"💣 **{multipla['tipo']}**\n"
        texto += f"🎯 **Odds Total:** {multipla['odd_total']:.2f}\n"
        texto += f"⚠️ **Risco:** {multipla['risco']}\n\n"
        
        for i, jogo in enumerate(multipla["jogos"], 1):
            analise = jogo["analise_profissional"]
            decisao = jogo.get("decisao_autonomo", {})
            mercado = decisao.get("mercado", "unknown")
            
            texto += f"{i}. **{jogo['home']} vs {jogo['away']}**\n"
            texto += f"   📊 {analise['emoji']} {analise['nivel']}\n"
            texto += f"   🎯 Score: {analise['score']} pontos\n"
            
            if mercado == "over":
                texto += f"   ⚽ Mercado: OVER {jogo.get('tendencia', '')}\n"
            elif mercado == "btts":
                texto += f"   🤝 Mercado: AMBAS MARCAM ({jogo.get('tendencia_ambas_marcam', 'SIM')})\n"
            elif mercado == "ht":
                texto += f"   ⏰ Mercado: GOLS HT ({jogo.get('tendencia_ht', 'OVER 0.5 HT')})\n"
            elif mercado == "favorito":
                favorito_text = jogo['home'] if jogo.get('favorito') == "home" else jogo['away'] if jogo.get('favorito') == "away" else "EMPATE"
                texto += f"   🏆 Mercado: FAVORITO ({favorito_text})\n"
            
            texto += f"   💰 Odd sugerida: {jogo.get('odd_sugerida', 2.0):.2f}\n"
            texto += f"   🔍 Confiança Ajustada: {jogo.get('confianca_final', 0):.0f}%\n"
            texto += f"   🏷️ Liga: {decisao.get('liga', 'Desconhecida')}\n\n"
        
        return texto


class AlertaCompleto:
    def __init__(self, jogo: Jogo, data_busca: str, tipos_analise_selecionados: dict):
        self.jogo = jogo
        self.data_busca = data_busca
        self.data_hora_busca = datetime.now()
        self.tipo_alerta = "completo"
        self.conferido = False
        self.alerta_enviado = False
        self.tipos_analise_selecionados = tipos_analise_selecionados
        
        self.analise_over_under = None
        self.analise_favorito = None
        self.analise_gols_ht = None
        self.analise_ambas_marcam = None
        self.analise_profissional = None
        self.decisao_autonomo = None
        
        if tipos_analise_selecionados.get("over_under", False):
            self.analise_over_under = {
                "tendencia": jogo.tendencia,
                "estimativa": jogo.estimativa,
                "probabilidade": jogo.probabilidade,
                "confianca": jogo.confianca,
                "tipo_aposta": jogo.tipo_aposta
            }
        
        if tipos_analise_selecionados.get("favorito", False):
            self.analise_favorito = {
                "favorito": jogo.favorito,
                "confianca_vitoria": jogo.confianca_vitoria,
                "prob_home_win": jogo.prob_home_win,
                "prob_away_win": jogo.prob_away_win,
                "prob_draw": jogo.prob_draw
            }
        
        if tipos_analise_selecionados.get("gols_ht", False):
            self.analise_gols_ht = {
                "tendencia_ht": jogo.tendencia_ht,
                "confianca_ht": jogo.confianca_ht,
                "estimativa_total_ht": jogo.estimativa_total_ht,
                "over_05_ht": jogo.over_05_ht,
                "over_15_ht": jogo.over_15_ht
            }
        
        if tipos_analise_selecionados.get("ambas_marcam", False):
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
            "escudo_away": self.jogo.away_crest,
            "tipos_analise_selecionados": self.tipos_analise_selecionados,
            "resultados": self.resultados,
            "detalhes": self.jogo.detalhes_analise
        }
        
        if self.analise_over_under is not None:
            alerta_dict["analise_over_under"] = self.analise_over_under
        if self.analise_favorito is not None:
            alerta_dict["analise_favorito"] = self.analise_favorito
        if self.analise_gols_ht is not None:
            alerta_dict["analise_gols_ht"] = self.analise_gols_ht
        if self.analise_ambas_marcam is not None:
            alerta_dict["analise_ambas_marcam"] = self.analise_ambas_marcam
        if self.analise_profissional is not None:
            alerta_dict["analise_profissional"] = self.analise_profissional
        if self.decisao_autonomo is not None:
            alerta_dict["decisao_autonomo"] = self.decisao_autonomo
            
        return alerta_dict
    
    def set_resultados(self, home_goals: int, away_goals: int, ht_home_goals: int = None, ht_away_goals: int = None):
        self.resultados["home_goals"] = home_goals
        self.resultados["away_goals"] = away_goals
        self.resultados["ht_home_goals"] = ht_home_goals
        self.resultados["ht_away_goals"] = ht_away_goals
        self.conferido = True
        
        total_gols = home_goals + away_goals
        
        if self.analise_over_under is not None:
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
        
        if self.analise_favorito is not None:
            favorito = self.analise_favorito.get("favorito", "")
            if favorito == "home" and home_goals > away_goals:
                self.resultados["favorito"] = "GREEN"
            elif favorito == "away" and away_goals > home_goals:
                self.resultados["favorito"] = "GREEN"
            elif favorito == "draw" and home_goals == away_goals:
                self.resultados["favorito"] = "GREEN"
            else:
                self.resultados["favorito"] = "RED"
        
        if self.analise_gols_ht is not None and ht_home_goals is not None and ht_away_goals is not None:
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
        
        if self.analise_ambas_marcam is not None:
            tendencia_am = self.analise_ambas_marcam.get("tendencia_ambas_marcam", "")
            if tendencia_am == "SIM" and home_goals > 0 and away_goals > 0:
                self.resultados["ambas_marcam"] = "GREEN"
            elif tendencia_am == "NÃO" and (home_goals == 0 or away_goals == 0):
                self.resultados["ambas_marcam"] = "GREEN"
            else:
                self.resultados["ambas_marcam"] = "RED"


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
    
    def gerar_poster_multipla(self, multipla: dict, titulo: str = "💣 MÚLTIPLA PROFISSIONAL") -> io.BytesIO:
        """Gera pôster estilo West Ham para múltiplas"""
        LARGURA = 2000
        ALTURA_TOPO = 350
        ALTURA_POR_JOGO = 550
        PADDING = 80
        
        jogos = multipla["jogos"]
        jogos_count = len(jogos)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)

        FONTE_TITULO = self.criar_fonte(90)
        FONTE_SUBTITULO = self.criar_fonte(65)
        FONTE_TIMES = self.criar_fonte(55)
        FONTE_VS = self.criar_fonte(50)
        FONTE_INFO = self.criar_fonte(45)
        FONTE_ANALISE = self.criar_fonte(42)
        FONTE_ODD = self.criar_fonte(60)
        FONTE_TOTAL = self.criar_fonte(70)
        FONTE_DETALHES = self.criar_fonte(40)

        # Título principal
        titulo_text = f"{titulo} - {multipla['modelo']}"
        try:
            titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_TITULO)
            titulo_w = titulo_bbox[2] - titulo_bbox[0]
            draw.text(((LARGURA - titulo_w) // 2, 80), titulo_text, font=FONTE_TITULO, fill=(255, 215, 0))
        except:
            draw.text((LARGURA//2 - 300, 80), titulo_text, font=FONTE_TITULO, fill=(255, 215, 0))

        # Composição da múltipla
        composicao = f"{multipla['over_1.5_count']}x Over 1.5 + {multipla['over_2.5_count']}x Over 2.5"
        try:
            comp_bbox = draw.textbbox((0, 0), composicao, font=FONTE_SUBTITULO)
            comp_w = comp_bbox[2] - comp_bbox[0]
            draw.text(((LARGURA - comp_w) // 2, 180), composicao, font=FONTE_SUBTITULO, fill=(200, 200, 200))
        except:
            draw.text((LARGURA//2 - 250, 180), composicao, font=FONTE_SUBTITULO, fill=(200, 200, 200))

        # Odd Total
        odd_total = multipla['odd_total']
        odd_text = f"ODDS TOTAL: {odd_total:.2f}"
        try:
            odd_bbox = draw.textbbox((0, 0), odd_text, font=FONTE_TOTAL)
            odd_w = odd_bbox[2] - odd_bbox[0]
            draw.text(((LARGURA - odd_w) // 2, 260), odd_text, font=FONTE_TOTAL, fill=(100, 255, 100))
        except:
            draw.text((LARGURA//2 - 200, 260), odd_text, font=FONTE_TOTAL, fill=(100, 255, 100))

        # Risco e taxa esperada
        info_text = f"⚠️ Risco: {multipla['risco']} | 📈 Taxa Esperada: {multipla['taxa_acerto_esperada']}"
        try:
            info_bbox = draw.textbbox((0, 0), info_text, font=FONTE_INFO)
            info_w = info_bbox[2] - info_bbox[0]
            draw.text(((LARGURA - info_w) // 2, 320), info_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 250, 320), info_text, font=FONTE_INFO, fill=(150, 200, 255))

        draw.line([(LARGURA//4, 360), (3*LARGURA//4, 360)], fill=(255, 215, 0), width=4)

        y_pos = ALTURA_TOPO

        for idx, jogo in enumerate(jogos):
            x0, y0 = PADDING, y_pos
            x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
            
            classificacao = jogo.get("classificacao", {})
            tipo = classificacao.get("tipo", "over_1.5")
            cor_borda = (255, 215, 0) if tipo == "over_1.5" else (255, 193, 7) if tipo == "over_2.5" else (100, 200, 255)
            
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)

            # Odd do jogo
            odd_jogo = 100 / max(jogo.get("probabilidade", 65), 10)
            odd_text = f"{odd_jogo:.2f}"
            
            try:
                odd_bbox = draw.textbbox((0, 0), odd_text, font=FONTE_ODD)
                odd_w = odd_bbox[2] - odd_bbox[0]
                odd_h = odd_bbox[3] - odd_bbox[1]
                
                odd_x = x1 - odd_w - 40
                odd_y = y0 + 40
                
                fundo_x0 = odd_x - 15
                fundo_y0 = odd_y - 10
                fundo_x1 = odd_x + odd_w + 15
                fundo_y1 = odd_y + odd_h + 10
                
                overlay = Image.new('RGBA', img.size, (0,0,0,0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rectangle([fundo_x0, fundo_y0, fundo_x1, fundo_y1], fill=(0, 0, 0, 200))
                img.paste(overlay, (0,0), overlay)
                
                draw.rectangle([fundo_x0, fundo_y0, fundo_x1, fundo_y1], outline=cor_borda, width=3)
                draw.text((odd_x, odd_y), odd_text, font=FONTE_ODD, fill=cor_borda)
                
            except Exception as e:
                logging.error(f"Erro ao desenhar odd: {e}")
                odd_x = x1 - 150
                odd_y = y0 + 40
                draw.text((odd_x, odd_y), odd_text, font=FONTE_ODD, fill=cor_borda)

            # Liga
            liga_text = jogo.get('liga', 'LIGA').upper()
            try:
                liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_INFO)
                liga_w = liga_bbox[2] - liga_bbox[0]
                draw.text(((LARGURA - liga_w) // 2, y0 + 35), liga_text, font=FONTE_INFO, fill=(200, 200, 200))
            except:
                draw.text((LARGURA//2 - 150, y0 + 35), liga_text, font=FONTE_INFO, fill=(200, 200, 200))

            # Escudos e times
            TAMANHO_ESCUDO = 140
            TAMANHO_QUADRADO = 160
            ESPACO_ENTRE_ESCUDOS = 600

            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2

            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 100

            escudo_home_bytes = self.api_client.baixar_escudo_time(jogo.get('home', ''), jogo.get('escudo_home', ''))
            escudo_away_bytes = self.api_client.baixar_escudo_time(jogo.get('away', ''), jogo.get('escudo_away', ''))
            
            escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA") if escudo_home_bytes else None
            escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA") if escudo_away_bytes else None

            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo.get('home', ''))
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo.get('away', ''))

            home_text = jogo.get('home', 'TIME CASA')[:15]
            away_text = jogo.get('away', 'TIME FORA')[:15]

            try:
                home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 25),
                         home_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 25), home_text, font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 25),
                         away_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 25), away_text, font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
                vs_w = vs_bbox[2] - vs_bbox[0]
                vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
                draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 20), "VS", font=FONTE_VS, fill=(255, 215, 0))
            except:
                vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 30
                draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 20), "VS", font=FONTE_VS, fill=(255, 215, 0))

            # Informações da aposta
            y_analysis = y_escudos + TAMANHO_QUADRADO + 110
            draw.line([(x0 + 80, y_analysis - 15), (x1 - 80, y_analysis - 15)], fill=(100, 130, 160), width=2)
            
            if tipo == "over_1.5":
                tendencia = jogo.get("tendencia", "Over 1.5")
                emoji = "🟢"
                cor_texto = (100, 255, 100)
            else:
                tendencia = jogo.get("tendencia", "Over 2.5")
                emoji = "🟡"
                cor_texto = (255, 215, 0)
            
            text_analise = f"{emoji} {tendencia}"
            try:
                analise_bbox = draw.textbbox((0, 0), text_analise, font=FONTE_ANALISE)
                analise_w = analise_bbox[2] - analise_bbox[0]
                draw.text(((LARGURA - analise_w) // 2, y_analysis + 10), text_analise, font=FONTE_ANALISE, fill=cor_texto)
            except:
                draw.text((LARGURA//2 - 150, y_analysis + 10), text_analise, font=FONTE_ANALISE, fill=cor_texto)
            
            info_jogo = f"Estimativa: {classificacao.get('estimativa', 0):.2f} gols | Confiança: {classificacao.get('confianca', 0):.0f}%"
            try:
                info_bbox = draw.textbbox((0, 0), info_jogo, font=FONTE_INFO)
                info_w = info_bbox[2] - info_bbox[0]
                draw.text(((LARGURA - info_w) // 2, y_analysis + 60), info_jogo, font=FONTE_INFO, fill=(150, 200, 255))
            except:
                draw.text((LARGURA//2 - 200, y_analysis + 60), info_jogo, font=FONTE_INFO, fill=(150, 200, 255))

            y_pos += ALTURA_POR_JOGO

        # Rodapé
        rodape_text = f"GERADO EM {datetime.now().strftime('%d/%m/%Y %H:%M')} | ELITE MASTER 3.0 - MÚLTIPLAS"
        try:
            rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_DETALHES)
            rodape_w = rodape_bbox[2] - rodape_bbox[0]
            draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
        except:
            draw.text((LARGURA//2 - 350, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))

        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True, quality=95)
        buffer.seek(0)
        
        return buffer
    
    def gerar_poster_resultado_multipla(self, multipla: dict, data_br: str) -> io.BytesIO:
        """Gera pôster para resultado de múltipla"""
        LARGURA = 2000
        ALTURA_TOPO = 320
        ALTURA_POR_JOGO = 520
        PADDING = 80
        
        jogos_conferidos = multipla.get("jogos_conferidos", [])
        jogos_count = len(jogos_conferidos)
        altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

        img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
        draw = ImageDraw.Draw(img)

        FONTE_TITULO = self.criar_fonte(85)
        FONTE_SUBTITULO = self.criar_fonte(60)
        FONTE_TIMES = self.criar_fonte(55)
        FONTE_VS = self.criar_fonte(50)
        FONTE_INFO = self.criar_fonte(45)
        FONTE_RESULTADO = self.criar_fonte(70)
        FONTE_TOTAL = self.criar_fonte(65)
        FONTE_DETALHES = self.criar_fonte(40)

        acertada = multipla.get("acertada", False)
        odd_total = multipla.get("odd_total", 0)
        modelo = multipla.get("modelo", "MÚLTIPLA")
        
        titulo = f"📊 RESULTADO MÚLTIPLA - {data_br}"
        try:
            titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
            titulo_w = titulo_bbox[2] - titulo_bbox[0]
            draw.text(((LARGURA - titulo_w) // 2, 70), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
        except:
            draw.text((LARGURA//2 - 300, 70), titulo, font=FONTE_TITULO, fill=(255, 255, 255))

        # Badge de resultado
        if acertada:
            cor_badge = (46, 204, 113)
            resultado_text = "✅ ACERTOU!"
            badge_bg = (30, 70, 40)
        else:
            cor_badge = (231, 76, 60)
            resultado_text = "❌ ERROU!"
            badge_bg = (70, 40, 40)
        
        badge_width = 400
        badge_height = 100
        badge_x = (LARGURA - badge_width) // 2
        badge_y = 170
        
        draw.rectangle([badge_x, badge_y, badge_x + badge_width, badge_y + badge_height], 
                      fill=badge_bg, outline=cor_badge, width=4)
        
        try:
            badge_bbox = draw.textbbox((0, 0), resultado_text, font=FONTE_TITULO)
            badge_w = badge_bbox[2] - badge_bbox[0]
            badge_h = badge_bbox[3] - badge_bbox[1]
            badge_x_center = badge_x + (badge_width - badge_w) // 2
            badge_y_center = badge_y + (badge_height - badge_h) // 2
            draw.text((badge_x_center, badge_y_center), resultado_text, font=FONTE_TITULO, fill=cor_badge)
        except:
            draw.text((badge_x + 100, badge_y + 25), resultado_text, font=FONTE_TITULO, fill=cor_badge)
        
        # Informações da múltipla
        info_text = f"{modelo} | Odds Total: {odd_total:.2f}"
        try:
            info_bbox = draw.textbbox((0, 0), info_text, font=FONTE_SUBTITULO)
            info_w = info_bbox[2] - info_bbox[0]
            draw.text(((LARGURA - info_w) // 2, 290), info_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
        except:
            draw.text((LARGURA//2 - 250, 290), info_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

        draw.line([(LARGURA//4, 340), (3*LARGURA//4, 340)], fill=(255, 215, 0), width=4)

        y_pos = ALTURA_TOPO + 50

        for idx, jogo in enumerate(jogos_conferidos):
            x0, y0 = PADDING, y_pos
            x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
            
            resultado = jogo.get("resultado", "RED")
            cor_borda = (46, 204, 113) if resultado == "GREEN" else (231, 76, 60)
            
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)

            # Badge de resultado do jogo
            badge_jogo_width = 150
            badge_jogo_height = 60
            badge_jogo_x = x1 - badge_jogo_width - 40
            badge_jogo_y = y0 + 30
            
            resultado_jogo = "✅" if resultado == "GREEN" else "❌"
            cor_jogo = (46, 204, 113) if resultado == "GREEN" else (231, 76, 60)
            
            draw.rectangle([badge_jogo_x, badge_jogo_y, badge_jogo_x + badge_jogo_width, badge_jogo_y + badge_jogo_height], 
                          fill=cor_jogo, outline=(255, 255, 255), width=2)
            
            try:
                badge_bbox = draw.textbbox((0, 0), resultado_jogo, font=FONTE_INFO)
                badge_w = badge_bbox[2] - badge_bbox[0]
                badge_x_center = badge_jogo_x + (badge_jogo_width - badge_w) // 2
                draw.text((badge_x_center, badge_jogo_y + 15), resultado_jogo, font=FONTE_INFO, fill=(255, 255, 255))
            except:
                draw.text((badge_jogo_x + 65, badge_jogo_y + 15), resultado_jogo, font=FONTE_INFO, fill=(255, 255, 255))

            # Times
            TAMANHO_ESCUDO = 120
            TAMANHO_QUADRADO = 140
            ESPACO_ENTRE_ESCUDOS = 500

            largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            x_inicio = (LARGURA - largura_total) // 2

            x_home = x_inicio
            x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
            y_escudos = y0 + 70

            home_crest_url = jogo.get('escudo_home', '')
            away_crest_url = jogo.get('escudo_away', '')
            
            escudo_home_bytes = self.api_client.baixar_escudo_time(jogo.get('home', ''), home_crest_url)
            escudo_away_bytes = self.api_client.baixar_escudo_time(jogo.get('away', ''), away_crest_url)
            
            escudo_home_img = Image.open(io.BytesIO(escudo_home_bytes)).convert("RGBA") if escudo_home_bytes else None
            escudo_away_img = Image.open(io.BytesIO(escudo_away_bytes)).convert("RGBA") if escudo_away_bytes else None

            self._desenhar_escudo_quadrado(draw, img, escudo_home_img, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo.get('home', ''))
            self._desenhar_escudo_quadrado(draw, img, escudo_away_img, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO, jogo.get('away', ''))

            home_text = jogo.get('home', '')[:12]
            away_text = jogo.get('away', '')[:12]

            try:
                home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
                home_w = home_bbox[2] - home_bbox[0]
                draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                         home_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 20), home_text, font=FONTE_TIMES, fill=(255, 255, 255))

            try:
                away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
                away_w = away_bbox[2] - away_bbox[0]
                draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                         away_text, font=FONTE_TIMES, fill=(255, 255, 255))
            except:
                draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 20), away_text, font=FONTE_TIMES, fill=(255, 255, 255))

            # Placar
            resultado_score = f"{jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}"
            try:
                score_bbox = draw.textbbox((0, 0), resultado_score, font=FONTE_RESULTADO)
                score_w = score_bbox[2] - score_bbox[0]
                score_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - score_w) // 2
                draw.text((score_x, y_escudos + TAMANHO_QUADRADO//2 - 25), 
                         resultado_score, font=FONTE_RESULTADO, fill=(255, 255, 255))
            except:
                score_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 60
                draw.text((score_x, y_escudos + TAMANHO_QUADRADO//2 - 25), 
                         resultado_score, font=FONTE_RESULTADO, fill=(255, 255, 255))

            # Tipo de aposta
            tipo_aposta = jogo.get("tipo", "over_1.5")
            tipo_text = "Over 1.5" if tipo_aposta == "over_1.5" else "Over 2.5"
            emoji_tipo = "🟢" if tipo_aposta == "over_1.5" else "🟡"
            
            try:
                tipo_bbox = draw.textbbox((0, 0), f"{emoji_tipo} {tipo_text}", font=FONTE_INFO)
                tipo_w = tipo_bbox[2] - tipo_bbox[0]
                draw.text(((LARGURA - tipo_w) // 2, y_escudos + TAMANHO_QUADRADO + 80), 
                         f"{emoji_tipo} {tipo_text}", font=FONTE_INFO, fill=(150, 200, 255))
            except:
                draw.text((LARGURA//2 - 100, y_escudos + TAMANHO_QUADRADO + 80), 
                         f"{emoji_tipo} {tipo_text}", font=FONTE_INFO, fill=(150, 200, 255))

            y_pos += ALTURA_POR_JOGO

        # Rodapé
        rodape_text = f"CONFERIDO EM {datetime.now().strftime('%d/%m/%Y %H:%M')} | ELITE MASTER 3.0"
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

        rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - ELITE MASTER SYSTEM 3.0"
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

        rodape_text = "ELITE MASTER SYSTEM 3.0 - ANÁLISE PREDITIVA DE RESULTADOS"
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


class ResultadosTopAlertas:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = sistema_principal.config
        self.poster_generator = sistema_principal.poster_generator
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client
        self.gerador_multiplas = GeradorMultiplasProfissional()
    
    def conferir_resultados_top_alertas(self, data_selecionada):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        st.subheader(f"🏆 Conferindo Resultados TOP Alertas - {data_br}")
        
        alertas_top = DataStorage.carregar_alertas_top()
        if not alertas_top:
            st.warning("⚠️ Nenhum alerta TOP salvo para conferência")
            return
        
        alertas_hoje = {}
        for chave, alerta in alertas_top.items():
            if alerta.get("data_busca") == hoje and not alerta.get("conferido", False):
                alertas_hoje[chave] = alerta
        
        if not alertas_hoje:
            st.info(f"ℹ️ Nenhum alerta TOP pendente para {data_br}")
            return
        
        st.info(f"🔍 Encontrados {len(alertas_hoje)} alertas TOP pendentes")
        
        alertas_por_tipo = defaultdict(list)
        for alerta in alertas_hoje.values():
            tipo = alerta.get("tipo_alerta", "over_under")
            alertas_por_tipo[tipo].append(alerta)
        
        jogos_conferidos_por_tipo = {}
        progress_bar = st.progress(0)
        total_alertas = len(alertas_hoje)
        idx = 0
        
        for tipo_alerta, alertas_lista in alertas_por_tipo.items():
            jogos_conferidos = []
            for alerta in alertas_lista:
                fixture_id = alerta.get("id")
                
                match_data = self.api_client.obter_detalhes_jogo(fixture_id)
                if not match_data:
                    st.warning(f"⚠️ Não foi possível obter dados do jogo {fixture_id}")
                    continue
                
                status = match_data.get("status", "")
                
                if status == "FINISHED":
                    jogo_conferido = self._processar_resultado_alerta(alerta, match_data, tipo_alerta)
                    if jogo_conferido:
                        jogos_conferidos.append(jogo_conferido)
                        alerta["conferido"] = True
                        alerta["data_conferencia"] = datetime.now().isoformat()
                        alerta["home_goals"] = jogo_conferido.get("home_goals")
                        alerta["away_goals"] = jogo_conferido.get("away_goals")
                        if tipo_alerta == "over_under":
                            alerta["resultado"] = jogo_conferido.get("resultado")
                        elif tipo_alerta == "favorito":
                            alerta["resultado_favorito"] = jogo_conferido.get("resultado_favorito")
                        elif tipo_alerta == "gols_ht":
                            alerta["resultado_ht"] = jogo_conferido.get("resultado_ht")
                        elif tipo_alerta == "ambas_marcam":
                            alerta["resultado_ambas_marcam"] = jogo_conferido.get("resultado_ambas_marcam")
                elif status in ["IN_PLAY", "PAUSED"]:
                    st.write(f"⏳ Jogo em andamento: {alerta.get('home')} vs {alerta.get('away')}")
                elif status in ["SCHEDULED", "TIMED"]:
                    st.write(f"⏰ Jogo agendado: {alerta.get('home')} vs {alerta.get('away')}")
                else:
                    st.write(f"❓ Status {status}: {alerta.get('home')} vs {alerta.get('away')}")
                
                idx += 1
                progress_bar.progress(idx / total_alertas)
            
            if jogos_conferidos:
                jogos_conferidos_por_tipo[tipo_alerta] = jogos_conferidos
        
        if jogos_conferidos_por_tipo:
            self._salvar_alertas_top_atualizados(alertas_top)
            st.success(f"✅ {sum(len(j) for j in jogos_conferidos_por_tipo.values())} jogos conferidos!")
            
            for tipo_alerta, jogos in jogos_conferidos_por_tipo.items():
                self._gerar_poster_para_grupo(jogos, tipo_alerta, data_selecionada)
        else:
            st.info("⏳ Nenhum jogo conferido ainda. Aguardando jogos encerrarem...")
        
        self._mostrar_resumo_geral(alertas_hoje)
    
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
            
            self._mostrar_resultado_alerta_top(alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo, tipo_alerta)
            
            return dados_poster
            
        except Exception as e:
            logging.error(f"Erro ao processar resultado do alerta {alerta.get('id')}: {e}")
            st.error(f"❌ Erro ao processar {alerta.get('home')} vs {alerta.get('away')}: {e}")
            return None
    
    def _gerar_poster_para_grupo(self, jogos_conferidos, tipo_alerta, data_selecionada):
        data_str = data_selecionada.strftime("%d/%m/%Y")
        
        try:
            if tipo_alerta == "over_under":
                titulo = f"🏆 RESULTADOS TOP OVER/UNDER - {data_str}"
                greens = sum(1 for j in jogos_conferidos if j.get("resultado") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado") == "RED")
            elif tipo_alerta == "favorito":
                titulo = f"🏆 RESULTADOS TOP FAVORITOS - {data_str}"
                greens = sum(1 for j in jogos_conferidos if j.get("resultado_favorito") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado_favorito") == "RED")
            elif tipo_alerta == "gols_ht":
                titulo = f"🏆 RESULTADOS TOP GOLS HT - {data_str}"
                greens = sum(1 for j in jogos_conferidos if j.get("resultado_ht") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado_ht") == "RED")
            elif tipo_alerta == "ambas_marcam":
                titulo = f"🏆 RESULTADOS TOP AMBAS MARCAM - {data_str}"
                greens = sum(1 for j in jogos_conferidos if j.get("resultado_ambas_marcam") == "GREEN")
                reds = sum(1 for j in jogos_conferidos if j.get("resultado_ambas_marcam") == "RED")
            else:
                return
            
            total = greens + reds
            if total > 0:
                taxa_acerto = (greens / total) * 100
                
                poster = self.poster_generator.gerar_poster_resultados(jogos_conferidos, tipo_alerta)
                
                if poster and self._verificar_poster_valido(poster):
                    caption = (
                        f"<b>{titulo}</b>\n\n"
                        f"<b>📊 {len(jogos_conferidos)} JOGOS</b>\n"
                        f"<b>✅ {greens} GREEN  •  ❌ {reds} RED</b>\n"
                        f"<b>🎯 ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                        f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
                    )
                    
                    if self.telegram_client.enviar_foto(poster, caption=caption):
                        st.success(f"🏆 Poster resultados TOP {tipo_alerta} enviado!")
                        return True
                    else:
                        st.warning(f"⚠️ Não foi possível enviar o poster. Enviando como texto...")
                        return self._enviar_resultados_como_texto(titulo, jogos_conferidos, greens, reds, taxa_acerto, tipo_alerta)
                else:
                    st.warning(f"⚠️ Poster não gerado corretamente. Enviando como texto...")
                    return self._enviar_resultados_como_texto(titulo, jogos_conferidos, greens, reds, taxa_acerto, tipo_alerta)
            
            return False
                    
        except Exception as e:
            logging.error(f"Erro ao gerar poster para grupo - {tipo_alerta}: {e}")
            st.error(f"❌ Erro no poster: {e}")
            return False
    
    def _mostrar_resumo_geral(self, alertas):
        st.markdown("---")
        st.subheader("📈 RESUMO GERAL TOP ALERTAS")
        
        totais = {
            "over_under": {"total": 0, "conferidos": 0, "greens": 0, "reds": 0},
            "favorito": {"total": 0, "conferidos": 0, "greens": 0, "reds": 0},
            "gols_ht": {"total": 0, "conferidos": 0, "greens": 0, "reds": 0},
            "ambas_marcam": {"total": 0, "conferidos": 0, "greens": 0, "reds": 0}
        }
        
        for alerta in alertas.values():
            tipo = alerta.get("tipo_alerta", "over_under")
            totais[tipo]["total"] += 1
            if alerta.get("conferido", False):
                totais[tipo]["conferidos"] += 1
                if tipo == "over_under" and alerta.get("resultado") == "GREEN":
                    totais[tipo]["greens"] += 1
                elif tipo == "over_under" and alerta.get("resultado") == "RED":
                    totais[tipo]["reds"] += 1
                elif tipo == "favorito" and alerta.get("resultado_favorito") == "GREEN":
                    totais[tipo]["greens"] += 1
                elif tipo == "favorito" and alerta.get("resultado_favorito") == "RED":
                    totais[tipo]["reds"] += 1
                elif tipo == "gols_ht" and alerta.get("resultado_ht") == "GREEN":
                    totais[tipo]["greens"] += 1
                elif tipo == "gols_ht" and alerta.get("resultado_ht") == "RED":
                    totais[tipo]["reds"] += 1
                elif tipo == "ambas_marcam" and alerta.get("resultado_ambas_marcam") == "GREEN":
                    totais[tipo]["greens"] += 1
                elif tipo == "ambas_marcam" and alerta.get("resultado_ambas_marcam") == "RED":
                    totais[tipo]["reds"] += 1
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            t = totais["over_under"]
            st.metric("⚽ TOP Over/Under", f"{t['total']} jogos")
            if t["conferidos"] > 0:
                taxa = (t["greens"] / t["conferidos"]) * 100 if t["conferidos"] > 0 else 0
                st.write(f"✅ {t['greens']} | ❌ {t['reds']} | 📊 {taxa:.1f}%")
        
        with col2:
            t = totais["favorito"]
            st.metric("🏆 TOP Favoritos", f"{t['total']} jogos")
            if t["conferidos"] > 0:
                taxa = (t["greens"] / t["conferidos"]) * 100 if t["conferidos"] > 0 else 0
                st.write(f"✅ {t['greens']} | ❌ {t['reds']} | 📊 {taxa:.1f}%")
        
        with col3:
            t = totais["gols_ht"]
            st.metric("⏰ TOP Gols HT", f"{t['total']} jogos")
            if t["conferidos"] > 0:
                taxa = (t["greens"] / t["conferidos"]) * 100 if t["conferidos"] > 0 else 0
                st.write(f"✅ {t['greens']} | ❌ {t['reds']} | 📊 {taxa:.1f}%")
        
        with col4:
            t = totais["ambas_marcam"]
            st.metric("🤝 TOP Ambas Marcam", f"{t['total']} jogos")
            if t["conferidos"] > 0:
                taxa = (t["greens"] / t["conferidos"]) * 100 if t["conferidos"] > 0 else 0
                st.write(f"✅ {t['greens']} | ❌ {t['reds']} | 📊 {taxa:.1f}%")
    
    def _mostrar_resultado_alerta_top(self, alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo, tipo_alerta):
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
        
        texto_fallback += "\n🔥 ELITE MASTER SYSTEM 3.0 - TOP PERFORMANCE"
        
        if self.telegram_client.enviar_mensagem(f"<b>{texto_fallback}</b>", self.config.TELEGRAM_CHAT_ID_ALT2):
            st.success(f"📤 Resultados enviados como texto!")
            return True
        else:
            st.error(f"❌ Falha ao enviar resultados como texto!")
            return False


class GerenciadorAlertasCompletos:
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = sistema_principal.config
        self.poster_generator = sistema_principal.poster_generator
        self.telegram_client = sistema_principal.telegram_client
        self.api_client = sistema_principal.api_client
        self.sistema_autonomo = SistemaAutonomoApostas()
        self.gerador_multiplas = GeradorMultiplasProfissional()
        
        self.ALERTAS_COMPLETOS_PATH = ConfigManager.ALERTAS_COMPLETOS_PATH
        self.RESULTADOS_COMPLETOS_PATH = ConfigManager.RESULTADOS_COMPLETOS_PATH
        self.MULTIPLAS_PATH = ConfigManager.MULTIPLAS_PATH
        self.RESULTADOS_MULTIPLAS_PATH = ConfigManager.RESULTADOS_MULTIPLAS_PATH
    
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
    
    def carregar_multiplas(self) -> dict:
        return DataStorage.carregar_multiplas()
    
    def _salvar_multiplas(self, multiplas: dict):
        DataStorage.salvar_multiplas(multiplas)
    
    def carregar_resultados_multiplas(self) -> dict:
        return DataStorage.carregar_resultados_multiplas()
    
    def _salvar_resultados_multiplas(self, resultados: dict):
        DataStorage.salvar_resultados_multiplas(resultados)
    
    def processar_e_enviar_alertas_completos(self, jogos_analisados: list, data_busca: str, 
                                             tipos_analise_selecionados: dict, 
                                             filtrar_melhores: bool = True, 
                                             limiares: dict = None,
                                             score_minimo: int = 6,
                                             mostrar_estatisticas: bool = True):
        """
        Processa os jogos com o SISTEMA AUTÔNOMO DE APOSTAS 2.0 + GERADOR DE MÚLTIPLAS 3.0
        Com opção de enviar múltiplas como texto ou pôster
        """
        if not jogos_analisados:
            return False

        st.markdown("### 🤖 SISTEMA AUTÔNOMO DE APOSTAS 3.0 + GERADOR DE MÚLTIPLAS")
        st.markdown("**Decisão automática por mercado** com classificação A/B/C e geração profissional de múltiplas")
        
        # Opção de envio para múltiplas
        st.markdown("### 📨 Opções de Envio de Múltiplas")
        col1, col2 = st.columns(2)
        with col1:
            enviar_multiplas = st.checkbox("📤 Enviar Múltiplas", value=True, key="enviar_multiplas_opcao")
        with col2:
            formato_multipla = st.selectbox(
                "Formato da Múltipla",
                ["Pôster West Ham", "Texto", "Ambos"],
                key="formato_multipla"
            )
        
        # Opção para aliviar envios (evitar spam)
        aliviar_envios = st.checkbox(
            "🌙 Modo Aliviado (enviar apenas múltipla principal - HÍBRIDO)", 
            value=False,
            help="Ative para enviar apenas a múltipla HÍBRIDA (principal) em vez de todas as 3 múltiplas"
        )
        
        jogos_por_tipo = []
        for jogo_dict in jogos_analisados:
            tem_analise = False
            
            if tipos_analise_selecionados.get("over_under", False) and jogo_dict.get('confianca', 0) >= 30:
                tem_analise = True
            if tipos_analise_selecionados.get("favorito", False) and jogo_dict.get('confianca_vitoria', 0) >= 30:
                tem_analise = True
            if tipos_analise_selecionados.get("gols_ht", False) and jogo_dict.get('confianca_ht', 0) >= 30:
                tem_analise = True
            if tipos_analise_selecionados.get("ambas_marcam", False) and jogo_dict.get('confianca_ambas_marcam', 0) >= 30:
                tem_analise = True
            
            if tem_analise:
                jogos_por_tipo.append(jogo_dict)
        
        if not jogos_por_tipo:
            st.warning("⚠️ Nenhum jogo com análises válidas para os tipos selecionados.")
            return False
        
        with st.spinner("🔍 Classificando jogos (Níveis A/B/C) e gerando alertas TOP..."):
            jogos_classificados = self._classificar_e_gerar_alertas_top(jogos_por_tipo, data_busca, tipos_analise_selecionados)
        
        if not jogos_classificados:
            st.warning("⚠️ Nenhum jogo aprovado após classificação A/B/C.")
            return False
        
        self._mostrar_classificacao_jogos(jogos_classificados)
        
        with st.spinner("💣 Gerando múltiplas profissionais..."):
            multiplas = self.gerador_multiplas.gerar_todas_multiplas(jogos_classificados)
        
        if multiplas:
            st.success(f"🎯 {len(multiplas)} MÚLTIPLAS GERADAS!")
            
            multiplas_dict = {}
            for idx, multipla in enumerate(multiplas):
                multipla_id = f"multipla_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                multipla["id"] = multipla_id
                multipla["data_criacao"] = datetime.now().isoformat()
                multipla["jogos_conferidos"] = []
                multipla["enviada"] = False
                multiplas_dict[multipla_id] = multipla
            
            self._salvar_multiplas(multiplas_dict)
            
            if enviar_multiplas:
                multiplas_para_enviar = []
                
                if aliviar_envios:
                    # Enviar apenas a múltipla HÍBRIDA (principal)
                    multipla_hibrida = next((m for m in multiplas if m["modelo"] == "🔥 HÍBRIDO (PROFISSIONAL)"), None)
                    if multipla_hibrida:
                        multiplas_para_enviar.append(multipla_hibrida)
                        st.info("🌙 Modo Aliviado ativado - Enviando apenas a múltipla HÍBRIDA (principal)")
                    else:
                        # Se não encontrar híbrida, envia a primeira disponível
                        multiplas_para_enviar.append(multiplas[0])
                        st.info("🌙 Modo Aliviado ativado - Enviando a primeira múltipla disponível")
                else:
                    multiplas_para_enviar = multiplas
                
                for idx, multipla in enumerate(multiplas_para_enviar, 1):
                    with st.expander(f"💣 MÚLTIPLA {idx} - {multipla['modelo']} (Odds: {multipla['odd_total']:.2f})"):
                        st.markdown(self.gerador_multiplas.gerar_texto_multipla(multipla))
                    
                    self._enviar_multipla_telegram_v2(multipla, data_busca, formato_multipla)
                    time.sleep(2)  # Pequena pausa entre envios
            else:
                for idx, multipla in enumerate(multiplas, 1):
                    with st.expander(f"💣 MÚLTIPLA {idx} - {multipla['modelo']} (Odds: {multipla['odd_total']:.2f})"):
                        st.markdown(self.gerador_multiplas.gerar_texto_multipla(multipla))
        else:
            st.warning("⚠️ Não foi possível gerar múltiplas com os jogos disponíveis.")
        
        return True
    
    def _enviar_multipla_telegram_v2(self, multipla: dict, data_busca: str, formato: str):
        """Envia a múltipla para o Telegram com formato escolhido (texto ou pôster)"""
        try:
            data_br = datetime.strptime(data_busca, "%Y-%m-%d").strftime("%d/%m/%Y")
            
            if formato in ["Texto", "Ambos"]:
                texto = self.gerador_multiplas.gerar_texto_multipla(multipla)
                texto = f"📅 {data_br}\n" + texto
                if self.telegram_client.enviar_mensagem(texto, self.config.TELEGRAM_CHAT_ID_ALT2):
                    st.success(f"📤 Múltipla {multipla['modelo']} enviada como texto!")
                else:
                    st.warning(f"⚠️ Falha ao enviar múltipla como texto")
            
            if formato in ["Pôster West Ham", "Ambos"]:
                poster = self.poster_generator.gerar_poster_multipla(multipla, titulo=f"📅 {data_br}")
                caption = f"<b>💣 MÚLTIPLA PROFISSIONAL - {multipla['modelo']}</b>\n"
                caption += f"<b>📅 {data_br}</b>\n"
                caption += f"<b>🎯 Odds Total: {multipla['odd_total']:.2f}</b>\n\n"
                caption += f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
                
                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"📤 Múltipla {multipla['modelo']} enviada como pôster!")
                else:
                    st.warning(f"⚠️ Falha ao enviar múltipla como pôster")
            
            return True
                
        except Exception as e:
            logging.error(f"Erro ao enviar múltipla: {e}")
            st.error(f"❌ Erro ao enviar múltipla: {e}")
            return False
    
    def _classificar_e_gerar_alertas_top(self, jogos: list, data_busca: str, tipos_analise_selecionados: dict) -> list:
        jogos_classificados = []
        alertas_top = DataStorage.carregar_alertas_top()
        
        for jogo_dict in jogos:
            classificacao = self.gerador_multiplas.classificar_jogo(jogo_dict)
            jogo_dict["classificacao"] = classificacao
            
            if classificacao["nivel"] == "C":
                continue
            
            fixture_id = str(jogo_dict.get("id"))
            chave_alerta = f"{fixture_id}_{data_busca}"
            
            if chave_alerta not in alertas_top:
                alerta_top = {
                    "id": fixture_id,
                    "home": jogo_dict.get("home", ""),
                    "away": jogo_dict.get("away", ""),
                    "liga": jogo_dict.get("liga", ""),
                    "hora": jogo_dict.get("hora", ""),
                    "data_busca": data_busca,
                    "tipo_alerta": "over_under",
                    "conferido": False,
                    "alerta_enviado": False,
                    "classificacao": classificacao,
                    "escudo_home": jogo_dict.get("escudo_home", ""),
                    "escudo_away": jogo_dict.get("escudo_away", ""),
                    "tendencia": jogo_dict.get("tendencia", ""),
                    "estimativa": jogo_dict.get("estimativa", 0.0),
                    "probabilidade": jogo_dict.get("probabilidade", 0.0),
                    "confianca": jogo_dict.get("confianca", 0.0),
                    "tipo_aposta": jogo_dict.get("tipo_aposta", ""),
                    "tendencia_ambas_marcam": jogo_dict.get("tendencia_ambas_marcam", ""),
                    "confianca_ambas_marcam": jogo_dict.get("confianca_ambas_marcam", 0.0),
                    "prob_ambas_marcam_sim": jogo_dict.get("prob_ambas_marcam_sim", 0.0),
                    "prob_ambas_marcam_nao": jogo_dict.get("prob_ambas_marcam_nao", 0.0),
                    "detalhes": jogo_dict.get("detalhes", {})
                }
                alertas_top[chave_alerta] = alerta_top
            
            jogos_classificados.append(jogo_dict)
        
        DataStorage.salvar_alertas_top(alertas_top)
        
        return jogos_classificados
    
    def _mostrar_classificacao_jogos(self, jogos_classificados: list):
        st.markdown("### 📊 CLASSIFICAÇÃO DOS JOGOS (NÍVEIS A/B/C)")
        
        nivel_a = [j for j in jogos_classificados if j.get("classificacao", {}).get("nivel") == "A"]
        nivel_b = [j for j in jogos_classificados if j.get("classificacao", {}).get("nivel") == "B"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"🟢 **NÍVEL A (SEGURO):** {len(nivel_a)} jogos")
            st.caption("Over 1.5 | Estimativa ≥ 2.2 | Confiança ≥ 75%")
        with col2:
            st.markdown(f"🟡 **NÍVEL B (VALOR):** {len(nivel_b)} jogos")
            st.caption("Over 2.5 | Estimativa ≥ 2.7 | Ambas Marcam = SIM")
        
        st.markdown("---")
        
        with st.expander("📋 Ver todos os jogos classificados"):
            for jogo in jogos_classificados:
                classif = jogo.get("classificacao", {})
                cor = classif.get("cor", "⚪")
                nivel = classif.get("nivel", "D")
                motivo = classif.get("motivo", "")
                estimativa = classif.get("estimativa", 0)
                confianca = classif.get("confianca", 0)
                
                st.write(f"{cor} **{jogo.get('home')} vs {jogo.get('away')}**")
                st.write(f"   🏷️ {jogo.get('liga', 'Desconhecida')}")
                st.write(f"   📊 Nível {nivel}: {motivo}")
                st.write(f"   ⚽ Estimativa: {estimativa:.2f} | 🔍 Confiança: {confianca:.0f}%")
                st.write("---")
    
    def conferir_resultados_completos(self, data_selecionada):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        data_br = data_selecionada.strftime("%d/%m/%Y")
        st.subheader(f"🏆 Conferindo Resultados Completos - {data_br}")

        alertas = self.carregar_alertas()
        if alertas:
            alertas_hoje = {k: v for k, v in alertas.items() if v.get("data_busca") == hoje and not v.get("conferido", False)}
            
            if alertas_hoje:
                st.info(f"🔍 Encontrados {len(alertas_hoje)} alertas pendentes")
                self._conferir_alertas_individuais(alertas_hoje, hoje)
            else:
                st.info(f"ℹ️ Nenhum alerta individual pendente para {data_br}")
        
        multiplas = self.carregar_multiplas()
        if multiplas:
            multiplas_hoje = {k: v for k, v in multiplas.items() if v.get("data_criacao", "").startswith(hoje) and not v.get("enviada", False)}
            
            if multiplas_hoje:
                st.info(f"🔍 Conferindo {len(multiplas_hoje)} múltiplas pendentes...")
                self._conferir_multiplas(multiplas_hoje, hoje)
            else:
                st.info(f"ℹ️ Nenhuma múltipla pendente para {data_br}")
        
        self._mostrar_resumo_completos()
    
    def _conferir_alertas_individuais(self, alertas, hoje):
        jogos_conferidos = []
        progress_bar = st.progress(0)
        total = len(alertas)
        idx = 0
        
        for chave, alerta in alertas.items():
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
                    "tendencia": alerta.get("analise_over_under", {}).get("tendencia", "") if alerta.get("analise_over_under") else "",
                    "estimativa": alerta.get("analise_over_under", {}).get("estimativa", 0.0) if alerta.get("analise_over_under") else 0.0,
                    "probabilidade": alerta.get("analise_over_under", {}).get("probabilidade", 0.0) if alerta.get("analise_over_under") else 0.0,
                    "confianca": alerta.get("analise_over_under", {}).get("confianca", 0.0) if alerta.get("analise_over_under") else 0.0,
                    "tipo_aposta": alerta.get("analise_over_under", {}).get("tipo_aposta", "") if alerta.get("analise_over_under") else "",
                    "detalhes": alerta.get("detalhes", {})
                }
                jogo.set_analise(analise_completa)
                
                alerta_completo = AlertaCompleto(jogo, alerta.get("data_busca"), alerta.get("tipos_analise_selecionados", {}))
                
                if alerta.get("analise_favorito"):
                    alerta_completo.analise_favorito = alerta.get("analise_favorito", {})
                if alerta.get("analise_gols_ht"):
                    alerta_completo.analise_gols_ht = alerta.get("analise_gols_ht", {})
                if alerta.get("analise_ambas_marcam"):
                    alerta_completo.analise_ambas_marcam = alerta.get("analise_ambas_marcam", {})
                if alerta.get("analise_profissional"):
                    alerta_completo.analise_profissional = alerta.get("analise_profissional", {})
                if alerta.get("decisao_autonomo"):
                    alerta_completo.decisao_autonomo = alerta.get("decisao_autonomo", {})
                
                alerta_completo.set_resultados(home_goals, away_goals, ht_home_goals, ht_away_goals)
                
                alertas[chave]["conferido"] = True
                alertas[chave]["resultados"] = alerta_completo.resultados
                
                jogo_conferido = {
                    "home": alerta.get("home"),
                    "away": alerta.get("away"),
                    "liga": alerta.get("liga"),
                    "escudo_home": alerta.get("escudo_home"),
                    "escudo_away": alerta.get("escudo_away"),
                    "hora": jogo.get_hora_brasilia_datetime(),
                    "tipos_analise_selecionados": alerta.get("tipos_analise_selecionados", {}),
                    "resultados": alerta_completo.resultados,
                    "decisao_autonomo": alerta.get("decisao_autonomo", {}),
                    "analise_profissional": alerta.get("analise_profissional", {})
                }
                jogos_conferidos.append(jogo_conferido)
                
                decisao = alerta_completo.decisao_autonomo
                mercado_escolhido = decisao.get("mercado", "unknown")
                resultado_mercado = None
                
                if mercado_escolhido == "over":
                    resultado_mercado = alerta_completo.resultados.get("over_under", "RED")
                elif mercado_escolhido == "btts":
                    resultado_mercado = alerta_completo.resultados.get("ambas_marcam", "RED")
                elif mercado_escolhido == "ht":
                    resultado_mercado = alerta_completo.resultados.get("gols_ht", "RED")
                elif mercado_escolhido == "favorito":
                    resultado_mercado = alerta_completo.resultados.get("favorito", "RED")
                
                emoji = "✅" if resultado_mercado == "GREEN" else "❌" if resultado_mercado == "RED" else "⏳"
                st.write(f"{emoji} {alerta.get('home')} {home_goals}-{away_goals} {alerta.get('away')}")
                st.write(f"   🎯 Decisão: {mercado_escolhido.upper()} | Resultado: {resultado_mercado}")
            
            idx += 1
            progress_bar.progress(idx / total)
        
        self._salvar_alertas(alertas)
        
        if jogos_conferidos:
            st.success(f"✅ {len(jogos_conferidos)} jogos conferidos!")
            
            lotes = [jogos_conferidos[i:i+3] for i in range(0, len(jogos_conferidos), 3)]
            for idx_lote, lote in enumerate(lotes, 1):
                poster = self.poster_generator.gerar_poster_resultados_completos_v2(lote, {})
                caption = (
                    f"<b>🏆 RESULTADOS COMPLETOS - {hoje}</b>\n"
                    f"<b>📋 LOTE {idx_lote}/{len(lotes)} - {len(lote)} JOGOS</b>\n"
                    f"<b>📊 Decisão Autônoma por Mercado</b>\n\n"
                    f"<b>🔥 ELITE MASTER SYSTEM 3.0 - RESULTADOS CONFIRMADOS</b>"
                )
                
                if self.telegram_client.enviar_foto(poster, caption=caption):
                    st.success(f"📤 Lote {idx_lote}/{len(lotes)} enviado!")
                else:
                    st.error(f"❌ Falha ao enviar lote {idx_lote}/{len(lotes)}")
    
    def _conferir_multiplas(self, multiplas, hoje):
        multiplas_para_enviar = []
        
        for multipla_id, multipla in multiplas.items():
            st.write(f"📋 Conferindo múltipla: {multipla['modelo']} (Odds: {multipla['odd_total']:.2f})")
            
            todos_finalizados = True
            jogos_conferidos = []
            resultados_jogos = []
            
            for jogo in multipla["jogos"]:
                fixture_id = jogo.get("id")
                
                match_data = self.api_client.obter_detalhes_jogo(fixture_id)
                if not match_data:
                    st.warning(f"⚠️ Não foi possível obter dados do jogo {jogo.get('home')} vs {jogo.get('away')}")
                    todos_finalizados = False
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
                    
                    total_gols = home_goals + away_goals
                    classificacao = jogo.get("classificacao", {})
                    tipo = classificacao.get("tipo", "over_1.5")
                    
                    resultado_mercado = "RED"
                    if tipo == "over_1.5" and total_gols > 1.5:
                        resultado_mercado = "GREEN"
                    elif tipo == "over_2.5" and total_gols > 2.5:
                        resultado_mercado = "GREEN"
                    
                    jogo_conferido = {
                        "home": jogo.get("home"),
                        "away": jogo.get("away"),
                        "liga": jogo.get("liga"),
                        "escudo_home": jogo.get("escudo_home"),
                        "escudo_away": jogo.get("escudo_away"),
                        "home_goals": home_goals,
                        "away_goals": away_goals,
                        "ht_home_goals": ht_home_goals,
                        "ht_away_goals": ht_away_goals,
                        "tipo": tipo,
                        "resultado": resultado_mercado,
                        "odd": 100 / max(jogo.get("probabilidade", 65), 10)
                    }
                    jogos_conferidos.append(jogo_conferido)
                    resultados_jogos.append(resultado_mercado == "GREEN")
                    
                    st.write(f"   {jogo.get('home')} {home_goals}-{away_goals} {jogo.get('away')} - {tipo}: {resultado_mercado}")
                    
                elif status in ["IN_PLAY", "PAUSED"]:
                    st.write(f"   ⏳ {jogo.get('home')} vs {jogo.get('away')} - Em andamento")
                    todos_finalizados = False
                elif status in ["SCHEDULED", "TIMED"]:
                    st.write(f"   ⏰ {jogo.get('home')} vs {jogo.get('away')} - Agendado")
                    todos_finalizados = False
                else:
                    st.write(f"   ❓ {jogo.get('home')} vs {jogo.get('away')} - Status: {status}")
                    todos_finalizados = False
            
            if todos_finalizados and jogos_conferidos:
                multipla_acertada = all(resultados_jogos)
                multipla["jogos_conferidos"] = jogos_conferidos
                multipla["acertada"] = multipla_acertada
                multipla["data_conferencia"] = datetime.now().isoformat()
                multiplas_para_enviar.append(multipla)
        
        multiplas_atualizadas = self.carregar_multiplas()
        for multipla in multiplas_para_enviar:
            multipla_id = multipla["id"]
            multiplas_atualizadas[multipla_id] = multipla
            multiplas_atualizadas[multipla_id]["enviada"] = True
            self._enviar_resultado_multipla_v2(multipla)
        
        self._salvar_multiplas(multiplas_atualizadas)
        
        if multiplas_para_enviar:
            st.success(f"✅ {len(multiplas_para_enviar)} múltiplas finalizadas e enviadas!")
        else:
            st.info("⏳ Nenhuma múltipla completamente finalizada ainda.")
    
    def _enviar_resultado_multipla_v2(self, multipla: dict):
        """Envia o resultado da múltipla com pôster West Ham"""
        try:
            jogos = multipla["jogos_conferidos"]
            acertada = multipla.get("acertada", False)
            modelo = multipla["modelo"]
            odd_total = multipla["odd_total"]
            data_br = datetime.now().strftime("%d/%m/%Y")
            
            # Gerar pôster para resultado da múltipla
            poster = self.poster_generator.gerar_poster_resultado_multipla(multipla, data_br)
            
            if acertada:
                titulo = f"🎯 MÚLTIPLA {modelo.upper()} - ACERTOU! 🎯"
                emoji = "✅"
            else:
                titulo = f"❌ MÚLTIPLA {modelo.upper()} - ERRADA ❌"
                emoji = "❌"
            
            caption = (
                f"<b>{titulo}</b>\n\n"
                f"{emoji} <b>RESULTADO:</b> {'Acertou' if acertada else 'Errou'}\n"
                f"📊 <b>JOGOS:</b> {len(jogos)}\n"
                f"🎯 <b>ODDS TOTAL:</b> {odd_total:.2f}\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM 3.0 - MÚLTIPLAS</b>"
            )
            
            if self.telegram_client.enviar_foto(poster, caption=caption):
                st.success(f"📤 Resultado da múltipla {modelo} enviado com pôster!")
                return True
            else:
                # Fallback para texto
                texto = f"<b>{titulo}</b>\n\n"
                texto += f"{emoji} <b>RESULTADO:</b> {'Acertou' if acertada else 'Errou'}\n"
                texto += f"📊 <b>JOGOS:</b> {len(jogos)}\n"
                texto += f"🎯 <b>ODDS TOTAL:</b> {odd_total:.2f}\n\n"
                
                for i, jogo in enumerate(jogos, 1):
                    resultado_emoji = "✅" if jogo["resultado"] == "GREEN" else "❌"
                    texto += f"{i}. {jogo['home']} {jogo['home_goals']}-{jogo['away_goals']} {jogo['away']}\n"
                    texto += f"   🎯 {jogo['tipo'].upper()} | {resultado_emoji} {jogo['resultado']}\n\n"
                
                texto += f"<b>🔥 ELITE MASTER SYSTEM 3.0 - MÚLTIPLAS</b>"
                
                if self.telegram_client.enviar_mensagem(texto, self.config.TELEGRAM_CHAT_ID_ALT2):
                    st.success(f"📤 Resultado da múltipla {modelo} enviado como texto!")
                    return True
                return False
                
        except Exception as e:
            logging.error(f"Erro ao enviar resultado da múltipla: {e}")
            return False
    
    def _mostrar_resumo_completos(self):
        alertas = self.carregar_alertas()
        multiplas = self.carregar_multiplas()
        
        st.markdown("---")
        st.subheader("📊 RESUMO GERAL COMPLETOS")
        
        if alertas:
            total_alertas = len(alertas)
            conferidos = sum(1 for a in alertas.values() if a.get("conferido", False))
            enviados = sum(1 for a in alertas.values() if a.get("alerta_enviado", False))
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📋 Alertas", total_alertas)
            col2.metric("✅ Conferidos", conferidos)
            col3.metric("📤 Enviados", enviados)
        
        if multiplas:
            total_multiplas = len(multiplas)
            enviadas = sum(1 for m in multiplas.values() if m.get("enviada", False))
            acertadas = sum(1 for m in multiplas.values() if m.get("acertada", False))
            
            st.markdown("### 💣 Múltiplas")
            col1, col2, col3 = st.columns(3)
            col1.metric("📋 Total", total_multiplas)
            col2.metric("✅ Enviadas", enviadas)
            col3.metric("🎯 Acertadas", acertadas)
            
            if total_multiplas > 0:
                taxa_acerto = (acertadas / total_multiplas) * 100
                st.metric("📊 Taxa de Acerto", f"{taxa_acerto:.1f}%")
    
    def gerar_poster_resultados_completos_v2(self, jogos_com_resultados: list, tipos_analise_selecionados: dict) -> io.BytesIO:
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

        titulo = " RESULTADOS COMPLETOS - ELITE MASTER 3.0"
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
            
            resultados = jogo.get("resultados", {})
            decisao = jogo.get("decisao_autonomo", {})
            mercado_escolhido = decisao.get("mercado", "unknown")
            conf_ajustada = decisao.get("confianca_ajustada", 0) * 100
            
            home_goals = resultados.get("home_goals", '?')
            away_goals = resultados.get("away_goals", '?')
            
            resultado_mercado = None
            if mercado_escolhido == "over":
                resultado_mercado = resultados.get("over_under", "N/A")
            elif mercado_escolhido == "btts":
                resultado_mercado = resultados.get("ambas_marcam", "N/A")
            elif mercado_escolhido == "ht":
                resultado_mercado = resultados.get("gols_ht", "N/A")
            elif mercado_escolhido == "favorito":
                resultado_mercado = resultados.get("favorito", "N/A")
            
            if resultado_mercado == "GREEN":
                cor_borda = (46, 204, 113)
            elif resultado_mercado == "RED":
                cor_borda = (231, 76, 60)
            else:
                cor_borda = (149, 165, 166)
            
            draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=cor_borda, width=4)

            badge_text = f"{mercado_escolhido.upper()} | {conf_ajustada:.0f}%"
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
            
            draw.text((x0 + 80, y_results), "📊 RESULTADO DA DECISÃO AUTÔNOMA", font=FONTE_ANALISE_TITULO, fill=(255, 215, 0))
            
            resultado_emoji = "✅" if resultado_mercado == "GREEN" else "❌" if resultado_mercado == "RED" else "⏳"
            cor_resultado = (46, 204, 113) if resultado_mercado == "GREEN" else (231, 76, 60) if resultado_mercado == "RED" else (149, 165, 166)
            
            draw.text((x0 + 80, y_results + 60), 
                     f" {resultado_emoji} MERCADO ESCOLHIDO: {mercado_escolhido.upper()} - {resultado_mercado}", 
                     font=FONTE_ANALISE, fill=cor_resultado)

            y_pos += ALTURA_POR_JOGO

        rodape_text = "ELITE MASTER SYSTEM 3.0 - RESULTADOS CONFIRMADOS"
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


class SistemaAlertasFutebol:
    def __init__(self):
        self.config = ConfigManager()
        self.rate_limiter = RateLimiter()
        self.api_monitor = APIMonitor()
        self.api_client = APIClient(self.rate_limiter, self.api_monitor)
        self.telegram_client = TelegramClient()
        self.poster_generator = PosterGenerator(self.api_client)
        self.image_cache = self.api_client.image_cache
        self.analisador_performance = AnalisadorPerformance()
        self.gerenciador_completo = GerenciadorAlertasCompletos(self)
        self.resultados_top = ResultadosTopAlertas(self)
        self.sistema_autonomo = SistemaAutonomoApostas()
        self.gerador_multiplas = GeradorMultiplasProfissional()
        
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
    
    def processar_jogos(self, data_selecionada, ligas_selecionadas, todas_ligas, top_n, min_conf, max_conf, estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos, formato_top_jogos, tipo_filtro, tipo_analise, config_analise):
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
        
        if jogos_filtrados:
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
    
    def processar_alertas_completos(self, data_selecionada, ligas_selecionadas, todas_ligas, tipos_analise_selecionados):
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
                st.write(f"✅ Jogos elegíveis: {len(jogos_filtrados)}")
                
                self.gerenciador_completo.processar_e_enviar_alertas_completos(
                    jogos_filtrados, hoje, tipos_analise_selecionados, False, None
                )
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
                        caption += f"<b>🔥 ELITE MASTER SYSTEM 3.0 - RESULTADOS CONFIRMADOS</b>"
                    
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
            msg += f"<b>🔥 ELITE MASTER SYSTEM 3.0 - ANÁLISE CONFIRMADA</b>"
            
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
                f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
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
                f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
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
                f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
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
                f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
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
    
    def _enviar_alerta_westham_style(self, jogos_conf: list, tipo_analise: str, config_analise: dict):
        if not jogos_conf:
            st.warning("⚠️ Nenhum jogo para gerar poster")
            return
        
        jogos_para_fallback = jogos_conf.copy()
        
        try:
            jogos_por_data = {}
            for jogo in jogos_conf:
                data = jogo["hora"].date() if isinstance(jogo["hora"], datetime) else datetime.now().date()
                if data not in jogos_por_data:
                    jogos_por_data[data] = []
                jogos_por_data[data].append(jogo)

            for data, jogos_data in jogos_por_data.items():
                data_br = data.strftime("%d/%m/%Y")
                jogos_ordenados = sorted(jogos_data, key=lambda x: x["hora"] if isinstance(x["hora"], datetime) else datetime.now())
                lotes = [jogos_ordenados[i:i+3] for i in range(0, len(jogos_ordenados), 3)]
                total_lotes = len(lotes)
                
                st.info(f"📦 Dividindo {len(jogos_ordenados)} jogos em {total_lotes} lotes de até 3 jogos cada (ordenados por horário)")
                
                for idx, lote in enumerate(lotes, 1):
                    if tipo_analise == "Over/Under de Gols":
                        titulo = f"- OVER/UNDER - {data_br} (Lote {idx}/{total_lotes})"
                        tipo_alerta = "over_under"
                    elif tipo_analise == "Favorito (Vitória)":
                        titulo = f"- FAVORITOS - {data_br} (Lote {idx}/{total_lotes})"
                        tipo_alerta = "favorito"
                    elif tipo_analise == "Gols HT (Primeiro Tempo)":
                        titulo = f"- GOLS HT - {data_br} (Lote {idx}/{total_lotes})"
                        tipo_alerta = "gols_ht"
                    elif tipo_analise == "Ambas Marcam (BTTS)":
                        titulo = f"- AMBAS MARCAM - {data_br} (Lote {idx}/{total_lotes})"
                        tipo_alerta = "ambas_marcam"
                    else:
                        titulo = f"- ALERTAS - {data_br} (Lote {idx}/{total_lotes})"
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
                            f"<b>🔥 ELITE MASTER SYSTEM 3.0 - ANÁLISE PREDITIVA</b>"
                        )
                    elif tipo_analise == "Favorito (Vitória)":
                        min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                        
                        caption = (
                            f"<b>🏆 ALERTA DE FAVORITOS - {data_br}</b>\n\n"
                            f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                            f"<b>🎯 CONFIANÇA MÍNIMA: {min_conf_vitoria}%</b>\n\n"
                            f"<b>🔥 ELITE MASTER SYSTEM 3.0 - ANÁLISE DE VITÓRIA</b>"
                        )
                    elif tipo_analise == "Gols HT (Primeiro Tempo)":
                        min_conf_ht = config_analise.get("min_conf_ht", 60)
                        tipo_ht = config_analise.get("tipo_ht", "OVER 0.5 HT")
                        
                        caption = (
                            f"<b>⏰ ALERTA DE GOLS HT - {data_br}</b>\n\n"
                            f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                            f"<b>🎯 TIPO: {tipo_ht}</b>\n"
                            f"<b>🔍 CONFIANÇA MÍNIMA: {min_conf_ht}%</b>\n\n"
                            f"<b>🔥 ELITE MASTER SYSTEM 3.0 - ANÁLISE DO PRIMEIRO TEMPO</b>"
                        )
                    elif tipo_analise == "Ambas Marcam (BTTS)":
                        min_conf_am = config_analise.get("min_conf_am", 60)
                        filtro_am = config_analise.get("filtro_am", "Todos")
                        
                        caption = (
                            f"<b>🤝 ALERTA AMBAS MARCAM - {data_br}</b>\n\n"
                            f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n"
                            f"<b>🎯 FILTRO: {filtro_am}</b>\n"
                            f"<b>🔍 CONFIANÇA MÍNIMA: {min_conf_am}%</b>\n\n"
                            f"<b>🔥 ELITE MASTER SYSTEM 3.0 - ANÁLISE BTTS</b>"
                        )
                    else:
                        caption = (
                            f"<b>⚽ ALERTA DE JOGOS - {data_br}</b>\n\n"
                            f"<b>📋 LOTE {idx}/{total_lotes}: {len(lote)} JOGOS</b>\n\n"
                            f"<b>🔥 ELITE MASTER SYSTEM 3.0</b>"
                        )
                    
                    st.info(f"📤 Enviando lote {idx}/{total_lotes} para o Telegram...")
                    if self.telegram_client.enviar_foto(poster, caption=caption):
                        st.success(f"🚀 Poster lote {idx}/{total_lotes} enviado para {data_br}!")
                    else:
                        st.error(f"❌ Falha ao enviar poster lote {idx}/{total_lotes} para {data_br}")
                    
                    if idx < total_lotes:
                        time.sleep(2)
                        
        except Exception as e:
            logging.error(f"Erro crítico ao gerar/enviar poster West Ham: {str(e)}")
            st.error(f"❌ Erro crítico ao gerar/enviar poster: {str(e)}")
            
            jogos_fallback = jogos_para_fallback
            
            if jogos_fallback and len(jogos_fallback) > 0:
                primeiro_jogo = jogos_fallback[0]
                if isinstance(primeiro_jogo.get("hora"), datetime):
                    data_br_fallback = primeiro_jogo["hora"].strftime("%d/%m/%Y")
                else:
                    data_br_fallback = datetime.now().strftime("%d/%m/%Y")
            else:
                data_br_fallback = datetime.now().strftime("%d/%m/%Y")
            
            st.info(f"📝 Enviando alertas como texto em lotes para {data_br_fallback}...")
            
            lotes_texto = [jogos_fallback[i:i+5] for i in range(0, len(jogos_fallback), 5)]
            
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
                        hora_formatada = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                        msg_lote += f"   🕒 {hora_formatada} BRT | {j.get('liga', '')}\n\n"
                    elif tipo_analise == "Favorito (Vitória)":
                        favorito_emoji = "🏠" if j.get('favorito') == "home" else "✈️" if j.get('favorito') == "away" else "🤝"
                        prob_fav = j.get('confianca_vitoria', 50)
                        odd = round(100 / prob_fav, 2) if prob_fav > 0 else 2.0
                        favorito_text = j['home'] if j.get('favorito') == "home" else j['away'] if j.get('favorito') == "away" else "EMPATE"
                        msg_lote += f"{favorito_emoji} <b>{j['home']} vs {j['away']}</b>\n"
                        msg_lote += f"   🏆 Favorito: {favorito_text} | Conf: {j['confianca_vitoria']:.1f}% | Odds: {odd:.2f}\n"
                        hora_formatada = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                        msg_lote += f"   🕒 {hora_formatada} BRT | {j.get('liga', '')}\n\n"
                    elif tipo_analise == "Gols HT (Primeiro Tempo)":
                        tipo_emoji_ht = "⚡" if "OVER" in j.get('tendencia_ht', '') else "🛡️"
                        prob_ht = j.get('confianca_ht', 50)
                        odd = round(100 / prob_ht, 2) if prob_ht > 0 else 2.0
                        msg_lote += f"{tipo_emoji_ht} <b>{j['home']} vs {j['away']}</b>\n"
                        msg_lote += f"   ⏰ {j['tendencia_ht']} | Conf: {j['confianca_ht']:.0f}% | Odds: {odd:.2f}\n"
                        hora_formatada = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                        msg_lote += f"   🕒 {hora_formatada} BRT | {j.get('liga', '')}\n\n"
                    elif tipo_analise == "Ambas Marcam (BTTS)":
                        tipo_emoji_am = "🤝" if j.get('tendencia_ambas_marcam') == "SIM" else "🚫"
                        prob_am = j.get('confianca_ambas_marcam', 50)
                        odd = round(100 / prob_am, 2) if prob_am > 0 else 2.0
                        msg_lote += f"{tipo_emoji_am} <b>{j['home']} vs {j['away']}</b>\n"
                        msg_lote += f"   🤝 {j['tendencia_ambas_marcam']} | Conf: {j['confianca_ambas_marcam']:.1f}% | Odds: {odd:.2f}\n"
                        hora_formatada = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
                        msg_lote += f"   🕒 {hora_formatada} BRT | {j.get('liga', '')}\n\n"
                
                msg_lote += f"<b>🔥 ELITE MASTER SYSTEM 3.0 - LOTE {idx}/{len(lotes_texto)}</b>"
                
                if self.telegram_client.enviar_mensagem(msg_lote, self.config.TELEGRAM_CHAT_ID_ALT2):
                    st.info(f"📤 Lote {idx}/{len(lotes_texto)} enviado como texto")
                else:
                    st.error(f"❌ Falha ao enviar lote {idx}/{len(lotes_texto)} como texto")
                
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
    
    def exportar_resultados_para_texto(self) -> dict:
        relatorio = self.gerar_relatorio_resultados_completo()
        
        data_export = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        conteudo_total = []
        conteudo_total.append("=" * 100)
        conteudo_total.append("📊 RELATÓRIO COMPLETO DE RESULTADOS - ELITE MASTER SYSTEM 3.0")
        conteudo_total.append("=" * 100)
        conteudo_total.append(f"📅 Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        conteudo_total.append(f"📋 Total de Ligas: {len(relatorio)}")
        conteudo_total.append("")
        
        total_jogos = sum(len(jogos) for jogos in relatorio.values())
        total_greens_ou = 0
        total_reds_ou = 0
        total_greens_fav = 0
        total_reds_fav = 0
        total_greens_ht = 0
        total_reds_ht = 0
        total_greens_am = 0
        total_reds_am = 0
        
        for liga, jogos in relatorio.items():
            for jogo in jogos:
                if jogo.get("resultado_ou") == "GREEN":
                    total_greens_ou += 1
                elif jogo.get("resultado_ou") == "RED":
                    total_reds_ou += 1
                
                if jogo.get("resultado_fav") == "GREEN":
                    total_greens_fav += 1
                elif jogo.get("resultado_fav") == "RED":
                    total_reds_fav += 1
                
                if jogo.get("resultado_ht") == "GREEN":
                    total_greens_ht += 1
                elif jogo.get("resultado_ht") == "RED":
                    total_reds_ht += 1
                
                if jogo.get("resultado_am") == "GREEN":
                    total_greens_am += 1
                elif jogo.get("resultado_am") == "RED":
                    total_reds_am += 1
        
        conteudo_total.append("📈 RESUMO GLOBAL")
        conteudo_total.append("-" * 50)
        conteudo_total.append(f"🎯 Total de Jogos: {total_jogos}")
        conteudo_total.append("")
        conteudo_total.append("⚽ OVER/UNDER:")
        conteudo_total.append(f"   ✅ GREEN: {total_greens_ou}")
        conteudo_total.append(f"   ❌ RED: {total_reds_ou}")
        if total_greens_ou + total_reds_ou > 0:
            taxa_ou = (total_greens_ou / (total_greens_ou + total_reds_ou)) * 100
            conteudo_total.append(f"   📊 Taxa de Acerto: {taxa_ou:.1f}%")
        
        conteudo_total.append("")
        conteudo_total.append("🏆 FAVORITOS:")
        conteudo_total.append(f"   ✅ GREEN: {total_greens_fav}")
        conteudo_total.append(f"   ❌ RED: {total_reds_fav}")
        if total_greens_fav + total_reds_fav > 0:
            taxa_fav = (total_greens_fav / (total_greens_fav + total_reds_fav)) * 100
            conteudo_total.append(f"   📊 Taxa de Acerto: {taxa_fav:.1f}%")
        
        conteudo_total.append("")
        conteudo_total.append("⏰ GOLS HT:")
        conteudo_total.append(f"   ✅ GREEN: {total_greens_ht}")
        conteudo_total.append(f"   ❌ RED: {total_reds_ht}")
        if total_greens_ht + total_reds_ht > 0:
            taxa_ht = (total_greens_ht / (total_greens_ht + total_reds_ht)) * 100
            conteudo_total.append(f"   📊 Taxa de Acerto: {taxa_ht:.1f}%")
        
        conteudo_total.append("")
        conteudo_total.append("🤝 AMBAS MARCAM:")
        conteudo_total.append(f"   ✅ GREEN: {total_greens_am}")
        conteudo_total.append(f"   ❌ RED: {total_reds_am}")
        if total_greens_am + total_reds_am > 0:
            taxa_am = (total_greens_am / (total_greens_am + total_reds_am)) * 100
            conteudo_total.append(f"   📊 Taxa de Acerto: {taxa_am:.1f}%")
        
        conteudo_total.append("")
        conteudo_total.append("=" * 100)
        
        arquivos_gerados = {}
        
        for liga, jogos in relatorio.items():
            if not jogos:
                continue
            
            conteudo_liga = []
            nome_arquivo = f"resultados_{liga.replace(' ', '_')}_{data_export}.txt"
            
            conteudo_liga.append("=" * 100)
            conteudo_liga.append(f"🏆 LIGA: {liga.upper()}")
            conteudo_liga.append("=" * 100)
            conteudo_liga.append(f"📅 Data Exportação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            conteudo_liga.append(f"📋 Total de Jogos: {len(jogos)}")
            conteudo_liga.append("")
            
            greens_ou = sum(1 for j in jogos if j.get("resultado_ou") == "GREEN")
            reds_ou = sum(1 for j in jogos if j.get("resultado_ou") == "RED")
            greens_fav = sum(1 for j in jogos if j.get("resultado_fav") == "GREEN")
            reds_fav = sum(1 for j in jogos if j.get("resultado_fav") == "RED")
            greens_ht = sum(1 for j in jogos if j.get("resultado_ht") == "GREEN")
            reds_ht = sum(1 for j in jogos if j.get("resultado_ht") == "RED")
            greens_am = sum(1 for j in jogos if j.get("resultado_am") == "GREEN")
            reds_am = sum(1 for j in jogos if j.get("resultado_am") == "RED")
            
            conteudo_liga.append("📊 ESTATÍSTICAS DA LIGA")
            conteudo_liga.append("-" * 50)
            conteudo_liga.append(f"⚽ Over/Under: {greens_ou}✅ | {reds_ou}❌")
            if greens_ou + reds_ou > 0:
                taxa_ou = (greens_ou / (greens_ou + reds_ou)) * 100
                conteudo_liga.append(f"   Taxa: {taxa_ou:.1f}%")
            
            conteudo_liga.append(f"🏆 Favoritos: {greens_fav}✅ | {reds_fav}❌")
            if greens_fav + reds_fav > 0:
                taxa_fav = (greens_fav / (greens_fav + reds_fav)) * 100
                conteudo_liga.append(f"   Taxa: {taxa_fav:.1f}%")
            
            conteudo_liga.append(f"⏰ Gols HT: {greens_ht}✅ | {reds_ht}❌")
            if greens_ht + reds_ht > 0:
                taxa_ht = (greens_ht / (greens_ht + reds_ht)) * 100
                conteudo_liga.append(f"   Taxa: {taxa_ht:.1f}%")
            
            conteudo_liga.append(f"🤝 Ambas Marcam: {greens_am}✅ | {reds_am}❌")
            if greens_am + reds_am > 0:
                taxa_am = (greens_am / (greens_am + reds_am)) * 100
                conteudo_liga.append(f"   Taxa: {taxa_am:.1f}%")
            
            conteudo_liga.append("")
            conteudo_liga.append("=" * 100)
            conteudo_liga.append("📋 JOGOS")
            conteudo_liga.append("-" * 100)
            
            for idx, jogo in enumerate(jogos, 1):
                conteudo_liga.append(f"\n{idx}. {jogo.get('home', '?')} vs {jogo.get('away', '?')}")
                conteudo_liga.append(f"   📅 Data: {jogo.get('data', 'N/A')}")
                conteudo_liga.append(f"   🏁 RESULTADO FINAL: {jogo.get('home_goals', '?')} - {jogo.get('away_goals', '?')}")
                if jogo.get('ht_home_goals') != "?" and jogo.get('ht_away_goals') != "?":
                    conteudo_liga.append(f"   ⏱️ HT: {jogo.get('ht_home_goals', '?')} - {jogo.get('ht_away_goals', '?')}")
                conteudo_liga.append("")
                
                if jogo.get('tendencia_ou') != "N/A":
                    resultado_ou = jogo.get('resultado_ou', 'N/A')
                    emoji_ou = "✅" if resultado_ou == "GREEN" else "❌" if resultado_ou == "RED" else "⏳"
                    conteudo_liga.append(f"   ⚽ OVER/UNDER {emoji_ou}")
                    conteudo_liga.append(f"      Tendência: {jogo.get('tendencia_ou', 'N/A')}")
                    if jogo.get('estimativa_ou', 0) > 0:
                        conteudo_liga.append(f"      Estimativa: {jogo.get('estimativa_ou', 0):.2f} gols")
                    if jogo.get('confianca_ou', 0) > 0:
                        conteudo_liga.append(f"      Confiança: {jogo.get('confianca_ou', 0):.1f}%")
                    conteudo_liga.append(f"      Resultado: {resultado_ou}")
                    conteudo_liga.append("")
                
                if jogo.get('favorito') != "N/A":
                    resultado_fav = jogo.get('resultado_fav', 'N/A')
                    emoji_fav = "✅" if resultado_fav == "GREEN" else "❌" if resultado_fav == "RED" else "⏳"
                    favorito_text = jogo.get('home') if jogo.get('favorito') == "home" else jogo.get('away') if jogo.get('favorito') == "away" else "EMPATE"
                    conteudo_liga.append(f"   🏆 FAVORITO {emoji_fav}")
                    conteudo_liga.append(f"      Favorito: {favorito_text}")
                    if jogo.get('confianca_fav', 0) > 0:
                        conteudo_liga.append(f"      Confiança: {jogo.get('confianca_fav', 0):.1f}%")
                    conteudo_liga.append(f"      Resultado: {resultado_fav}")
                    conteudo_liga.append("")
                
                if jogo.get('tendencia_ht') != "N/A":
                    resultado_ht = jogo.get('resultado_ht', 'N/A')
                    emoji_ht = "✅" if resultado_ht == "GREEN" else "❌" if resultado_ht == "RED" else "⏳"
                    conteudo_liga.append(f"   ⏰ GOLS HT {emoji_ht}")
                    conteudo_liga.append(f"      Tendência HT: {jogo.get('tendencia_ht', 'N/A')}")
                    if jogo.get('confianca_ht', 0) > 0:
                        conteudo_liga.append(f"      Confiança HT: {jogo.get('confianca_ht', 0):.1f}%")
                    conteudo_liga.append(f"      Resultado HT: {resultado_ht}")
                    conteudo_liga.append("")
                
                if jogo.get('tendencia_am') != "N/A":
                    resultado_am = jogo.get('resultado_am', 'N/A')
                    emoji_am = "✅" if resultado_am == "GREEN" else "❌" if resultado_am == "RED" else "⏳"
                    conteudo_liga.append(f"   🤝 AMBAS MARCAM {emoji_am}")
                    conteudo_liga.append(f"      Tendência: {jogo.get('tendencia_am', 'N/A')}")
                    if jogo.get('confianca_am', 0) > 0:
                        conteudo_liga.append(f"      Confiança: {jogo.get('confianca_am', 0):.1f}%")
                    conteudo_liga.append(f"      Resultado: {resultado_am}")
                    conteudo_liga.append("")
                
                conteudo_liga.append("-" * 80)
            
            conteudo_liga_str = "\n".join(conteudo_liga)
            arquivos_gerados[nome_arquivo] = conteudo_liga_str
            
            conteudo_total.append("")
            conteudo_total.extend(conteudo_liga)
        
        nome_consolidado = f"resultados_COMPLETO_{data_export}.txt"
        arquivos_gerados[nome_consolidado] = "\n".join(conteudo_total)
        
        return arquivos_gerados
    
    def gerar_relatorio_resultados_completo(self) -> dict:
        resultados = {
            "over_under": DataStorage.carregar_resultados(),
            "favorito": DataStorage.carregar_resultados_favoritos(),
            "gols_ht": DataStorage.carregar_resultados_gols_ht(),
            "ambas_marcam": DataStorage.carregar_resultados_ambas_marcam(),
        }
        
        alertas = {
            "over_under": DataStorage.carregar_alertas(),
            "favorito": DataStorage.carregar_alertas_favoritos(),
            "gols_ht": DataStorage.carregar_alertas_gols_ht(),
            "ambas_marcam": DataStorage.carregar_alertas_ambas_marcam(),
        }
        
        relatorio_por_liga = defaultdict(list)
        jogos_processados = set()
        
        for fixture_id, jogo in resultados["over_under"].items():
            if fixture_id in jogos_processados:
                continue
                
            liga = jogo.get("liga", "Desconhecida")
            alerta_original = alertas["over_under"].get(fixture_id, {})
            
            registro = {
                "id": fixture_id,
                "data": jogo.get("hora", "").split("T")[0] if "T" in jogo.get("hora", "") else jogo.get("hora", ""),
                "horario": jogo.get("hora", ""),
                "home": jogo.get("home", ""),
                "away": jogo.get("away", ""),
                "home_goals": jogo.get("home_goals", "?"),
                "away_goals": jogo.get("away_goals", "?"),
                "ht_home_goals": jogo.get("ht_home_goals", "?"),
                "ht_away_goals": jogo.get("ht_away_goals", "?"),
                "tendencia_ou": alerta_original.get("tendencia", jogo.get("tendencia", "N/A")),
                "estimativa_ou": alerta_original.get("estimativa", jogo.get("estimativa", 0)),
                "confianca_ou": alerta_original.get("confianca", jogo.get("confianca", 0)),
                "resultado_ou": jogo.get("resultado", "N/A"),
                "favorito": alerta_original.get("favorito", jogo.get("favorito", "N/A")),
                "confianca_fav": alerta_original.get("confianca_vitoria", jogo.get("confianca_vitoria", 0)),
                "resultado_fav": jogo.get("resultado_favorito", "N/A"),
                "tendencia_ht": alerta_original.get("tendencia_ht", jogo.get("tendencia_ht", "N/A")),
                "confianca_ht": alerta_original.get("confianca_ht", jogo.get("confianca_ht", 0)),
                "resultado_ht": jogo.get("resultado_ht", "N/A"),
                "tendencia_am": alerta_original.get("tendencia_ambas_marcam", jogo.get("tendencia_ambas_marcam", "N/A")),
                "confianca_am": alerta_original.get("confianca_ambas_marcam", jogo.get("confianca_ambas_marcam", 0)),
                "resultado_am": jogo.get("resultado_ambas_marcam", "N/A"),
                "data_conferencia": jogo.get("data_conferencia", ""),
                "status": "FINALIZADO"
            }
            
            relatorio_por_liga[liga].append(registro)
            jogos_processados.add(fixture_id)
        
        for fixture_id, jogo in resultados["favorito"].items():
            if fixture_id in jogos_processados:
                continue
                
            liga = jogo.get("liga", "Desconhecida")
            alerta_original = alertas["favorito"].get(fixture_id, {})
            
            registro = {
                "id": fixture_id,
                "data": jogo.get("hora", "").split("T")[0] if "T" in jogo.get("hora", "") else jogo.get("hora", ""),
                "horario": jogo.get("hora", ""),
                "home": jogo.get("home", ""),
                "away": jogo.get("away", ""),
                "home_goals": jogo.get("home_goals", "?"),
                "away_goals": jogo.get("away_goals", "?"),
                "ht_home_goals": jogo.get("ht_home_goals", "?"),
                "ht_away_goals": jogo.get("ht_away_goals", "?"),
                "tendencia_ou": "N/A",
                "estimativa_ou": 0,
                "confianca_ou": 0,
                "resultado_ou": "N/A",
                "favorito": alerta_original.get("favorito", jogo.get("favorito", "N/A")),
                "confianca_fav": alerta_original.get("confianca_vitoria", jogo.get("confianca_vitoria", 0)),
                "resultado_fav": jogo.get("resultado_favorito", "N/A"),
                "tendencia_ht": "N/A",
                "confianca_ht": 0,
                "resultado_ht": "N/A",
                "tendencia_am": "N/A",
                "confianca_am": 0,
                "resultado_am": "N/A",
                "data_conferencia": jogo.get("data_conferencia", ""),
                "status": "FINALIZADO"
            }
            
            relatorio_por_liga[liga].append(registro)
            jogos_processados.add(fixture_id)
        
        for fixture_id, jogo in resultados["gols_ht"].items():
            if fixture_id in jogos_processados:
                continue
                
            liga = jogo.get("liga", "Desconhecida")
            alerta_original = alertas["gols_ht"].get(fixture_id, {})
            
            registro = {
                "id": fixture_id,
                "data": jogo.get("hora", "").split("T")[0] if "T" in jogo.get("hora", "") else jogo.get("hora", ""),
                "horario": jogo.get("hora", ""),
                "home": jogo.get("home", ""),
                "away": jogo.get("away", ""),
                "home_goals": jogo.get("home_goals", "?"),
                "away_goals": jogo.get("away_goals", "?"),
                "ht_home_goals": jogo.get("ht_home_goals", "?"),
                "ht_away_goals": jogo.get("ht_away_goals", "?"),
                "tendencia_ou": "N/A",
                "estimativa_ou": 0,
                "confianca_ou": 0,
                "resultado_ou": "N/A",
                "favorito": "N/A",
                "confianca_fav": 0,
                "resultado_fav": "N/A",
                "tendencia_ht": alerta_original.get("tendencia_ht", jogo.get("tendencia_ht", "N/A")),
                "confianca_ht": alerta_original.get("confianca_ht", jogo.get("confianca_ht", 0)),
                "resultado_ht": jogo.get("resultado_ht", "N/A"),
                "tendencia_am": "N/A",
                "confianca_am": 0,
                "resultado_am": "N/A",
                "data_conferencia": jogo.get("data_conferencia", ""),
                "status": "FINALIZADO"
            }
            
            relatorio_por_liga[liga].append(registro)
            jogos_processados.add(fixture_id)
        
        for fixture_id, jogo in resultados["ambas_marcam"].items():
            if fixture_id in jogos_processados:
                continue
                
            liga = jogo.get("liga", "Desconhecida")
            alerta_original = alertas["ambas_marcam"].get(fixture_id, {})
            
            registro = {
                "id": fixture_id,
                "data": jogo.get("hora", "").split("T")[0] if "T" in jogo.get("hora", "") else jogo.get("hora", ""),
                "horario": jogo.get("hora", ""),
                "home": jogo.get("home", ""),
                "away": jogo.get("away", ""),
                "home_goals": jogo.get("home_goals", "?"),
                "away_goals": jogo.get("away_goals", "?"),
                "ht_home_goals": jogo.get("ht_home_goals", "?"),
                "ht_away_goals": jogo.get("ht_away_goals", "?"),
                "tendencia_ou": "N/A",
                "estimativa_ou": 0,
                "confianca_ou": 0,
                "resultado_ou": "N/A",
                "favorito": "N/A",
                "confianca_fav": 0,
                "resultado_fav": "N/A",
                "tendencia_ht": "N/A",
                "confianca_ht": 0,
                "resultado_ht": "N/A",
                "tendencia_am": alerta_original.get("tendencia_ambas_marcam", jogo.get("tendencia_ambas_marcam", "N/A")),
                "confianca_am": alerta_original.get("confianca_ambas_marcam", jogo.get("confianca_ambas_marcam", 0)),
                "resultado_am": jogo.get("resultado_ambas_marcam", "N/A"),
                "data_conferencia": jogo.get("data_conferencia", ""),
                "status": "FINALIZADO"
            }
            
            relatorio_por_liga[liga].append(registro)
            jogos_processados.add(fixture_id)
        
        for liga in relatorio_por_liga:
            relatorio_por_liga[liga].sort(key=lambda x: x.get("horario", ""))
        
        return relatorio_por_liga
    
    def reset_total_sistema(self):
        arquivos_para_limpar = [
            ConfigManager.ALERTAS_PATH,
            ConfigManager.ALERTAS_FAVORITOS_PATH,
            ConfigManager.ALERTAS_GOLS_HT_PATH,
            ConfigManager.ALERTAS_AMBAS_MARCAM_PATH,
            ConfigManager.RESULTADOS_PATH,
            ConfigManager.RESULTADOS_FAVORITOS_PATH,
            ConfigManager.RESULTADOS_GOLS_HT_PATH,
            ConfigManager.RESULTADOS_AMBAS_MARCAM_PATH,
            ConfigManager.ALERTAS_TOP_PATH,
            ConfigManager.RESULTADOS_TOP_PATH,
            ConfigManager.ALERTAS_COMPLETOS_PATH,
            ConfigManager.RESULTADOS_COMPLETOS_PATH,
            ConfigManager.MULTIPLAS_PATH,
            ConfigManager.RESULTADOS_MULTIPLAS_PATH,
            ConfigManager.HISTORICO_PATH,
            ConfigManager.MODELO_PERFORMANCE_PATH,
            ConfigManager.CACHE_JOGOS,
            ConfigManager.CACHE_CLASSIFICACAO
        ]
        
        arquivos_removidos = 0
        for arquivo in arquivos_para_limpar:
            try:
                if os.path.exists(arquivo):
                    with open(arquivo, 'w', encoding='utf-8') as f:
                        if arquivo in [ConfigManager.HISTORICO_PATH]:
                            json.dump([], f)
                        else:
                            json.dump({}, f)
                    arquivos_removidos += 1
                    logging.info(f"✅ Limpo: {arquivo}")
            except Exception as e:
                logging.error(f"❌ Erro ao limpar {arquivo}: {e}")
        
        try:
            if hasattr(self, 'image_cache') and self.image_cache:
                self.image_cache.clear()
                logging.info("✅ Cache de imagens em memória limpo")
            
            cache_dir = "escudos_cache"
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir, exist_ok=True)
                logging.info(f"✅ Pasta {cache_dir} limpa")
        except Exception as e:
            logging.error(f"❌ Erro ao limpar cache de imagens: {e}")
        
        try:
            if hasattr(self.api_client, 'jogos_cache'):
                self.api_client.jogos_cache.clear()
            if hasattr(self.api_client, 'classificacao_cache'):
                self.api_client.classificacao_cache.clear()
            if hasattr(self.api_client, 'match_cache'):
                self.api_client.match_cache.clear()
            logging.info("✅ Caches de dados limpos")
        except Exception as e:
            logging.error(f"❌ Erro ao limpar caches: {e}")
        
        try:
            if hasattr(self, 'api_monitor'):
                self.api_monitor.reset()
            logging.info("✅ Monitoramento resetado")
        except Exception as e:
            logging.error(f"❌ Erro ao resetar monitoramento: {e}")
        
        try:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            logging.info("✅ Sessão Streamlit limpa")
        except Exception as e:
            logging.error(f"❌ Erro ao limpar sessão: {e}")
        
        return arquivos_removidos


#def render_tab_multiplas_pro(sistema):
def render_tab_multiplas_pro(sistema):
    st.subheader("🧠 MÚLTIPLAS PRO - SISTEMA AUTÔNOMO")
    st.caption("Gera múltiplas inteligentes com score de qualidade, filtro anti-armadilha e balanceamento de risco.")

    data_selecionada = st.date_input(
        "📅 Data para análise",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_multiplas_pro"
    )

    todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_multiplas_pro")
    ligas_selecionadas = []
    if not todas_ligas:
        ligas_selecionadas = st.multiselect(
            "📌 Selecionar ligas",
            options=list(ConfigManager.LIGA_DICT.keys()),
            default=["Premier League (Inglaterra)", "Bundesliga", "Eredivisie"],
            key="ligas_multiplas_pro"
        )

    st.markdown("### 🎯 Configurações de Qualidade")
    col1, col2 = st.columns(2)
    with col1:
        score_minimo = st.slider(
            "Score Mínimo por Jogo",
            min_value=0,
            max_value=100,
            value=70,
            step=5,
            help="Jogos com score abaixo deste valor serão descartados."
        )
    with col2:
        usar_anti_armadilha = st.checkbox("🛡️ Ativar Filtro Anti-Armadilha", value=True)

    # Opção de formato para múltiplas
    st.markdown("### 📨 Opções de Envio")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        enviar_multiplas_tg = st.checkbox("📤 Enviar Múltiplas para Telegram", value=True, key="enviar_multiplas_tg_pro")
    with col_f2:
        formato_multipla = st.selectbox(
            "Formato da Múltipla",
            ["Pôster West Ham", "Texto", "Ambos"],
            key="formato_multipla_pro"
        )

    if st.button("🧠 GERAR MÚLTIPLAS PROFISSIONAIS", type="primary", use_container_width=True):
        if not todas_ligas and not ligas_selecionadas:
            st.error("❌ Selecione pelo menos uma liga")
            return

        with st.spinner("🔍 Analisando jogos e gerando múltiplas..."):
            hoje = data_selecionada.strftime("%Y-%m-%d")
            data_br = data_selecionada.strftime("%d/%m/%Y")

            if todas_ligas:
                ligas_busca = list(sistema.config.LIGA_DICT.values())
                st.write(f"🌍 Analisando TODAS as {len(ligas_busca)} ligas disponíveis")
            else:
                ligas_busca = [sistema.config.LIGA_DICT[liga_nome] for liga_nome in ligas_selecionadas]
                st.write(f"📌 Analisando {len(ligas_busca)} ligas selecionadas: {', '.join(ligas_selecionadas)}")

            st.write(f"⏳ Buscando jogos para {data_br}...")

            classificacoes = {}
            for liga_id in ligas_busca:
                classificacoes[liga_id] = sistema.api_client.obter_classificacao(liga_id)

            jogos_analisados = []

            for liga_id in ligas_busca:
                classificacao = classificacoes[liga_id]
                analisador = AnalisadorTendencia(classificacao)

                if liga_id == "BSA":
                    jogos_data = sistema.api_client.obter_jogos_brasileirao(liga_id, hoje)
                else:
                    jogos_data = sistema.api_client.obter_jogos(liga_id, hoje)

                for match_data in jogos_data:
                    if not sistema.api_client.validar_dados_jogo(match_data):
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
                    jogos_analisados.append(jogo)

            jogos_filtrados = [j for j in jogos_analisados if j.status not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]

            if not jogos_filtrados:
                st.warning("⚠️ Nenhum jogo futuro encontrado para a data selecionada.")
                return

            st.write(f"✅ {len(jogos_filtrados)} jogos elegíveis encontrados.")

            alerts = []
            for jogo in jogos_filtrados:
                if jogo.estimativa > 0 and jogo.confianca > 0:
                    alerts.append({
                        "jogo": f"{jogo.home_team} vs {jogo.away_team}",
                        "probabilidade": jogo.probabilidade,
                        "confianca": jogo.confianca,
                        "estimativa": jogo.estimativa,
                        "liga": jogo.competition,
                        "hora": jogo.get_hora_brasilia_datetime(),
                        "escudo_home": jogo.home_crest,
                        "escudo_away": jogo.away_crest,
                        "tendencia": jogo.tendencia,
                        "tipo_aposta": jogo.tipo_aposta,
                        "jogo_obj": jogo
                    })

            if not alerts:
                st.warning("⚠️ Nenhum alerta com Over/Under válido encontrado.")
                return

            sistema_apostas = SistemaApostasPro(alerts)

            jogos_selecionados = sistema_apostas.processar_alertas()

            if not jogos_selecionados:
                st.warning("⚠️ Nenhum jogo aprovado após filtros de score.")
                return

            jogos_finais = [j for j in jogos_selecionados if j['score'] >= score_minimo]

            if not jogos_finais:
                st.warning(f"⚠️ Nenhum jogo com score >= {score_minimo}.")
                return

            st.success(f"🎯 {len(jogos_finais)} jogos aprovados (Score ≥ {score_minimo})!")

            st.markdown("### 📊 Jogos Aprovados por Score")
            for j in jogos_finais:
                st.write(f"**{j['jogo']}** → {j['mercado']} (Odd: {j['odd']:.2f}) | **Score: {j['score']}**")

            elite, bons, risco = separar_por_nivel(jogos_finais)

            st.markdown("### 📈 Níveis de Jogos")
            col1, col2, col3 = st.columns(3)
            col1.metric("🔥 ELITE (Score ≥ 85)", len(elite))
            col2.metric("💎 BONS (75 ≤ Score < 85)", len(bons))
            col3.metric("⚠️ RISCO (Score < 75)", len(risco))

            multiplas = gerar_multiplas(elite, bons, risco)

            if not multiplas:
                st.warning("⚠️ Não foi possível gerar múltiplas com os jogos disponíveis.")
                return

            st.markdown("### 💣 MÚLTIPLAS GERADAS")
            for idx, (tipo, jogos_mult) in enumerate(multiplas):
                odd_total = calcular_odd_total(jogos_mult)
                with st.expander(f"{tipo} (Odds Total: {odd_total:.2f})"):
                    for j in jogos_mult:
                        st.write(f"   {j['jogo']} → {j['mercado']} ({j['odd']:.2f}) | Score: {j['score']}")

                if enviar_multiplas_tg:
                    data_br_str = data_selecionada.strftime("%d/%m/%Y")
                    
                    if formato_multipla in ["Texto", "Ambos"]:
                        msg = f"💣 **{tipo}**\n📅 {data_br_str}\n"
                        msg += f"🎯 **Odds Total:** {odd_total:.2f}\n\n"
                        for j in jogos_mult:
                            msg += f"⚽ {j['jogo']}\n"
                            msg += f"   📊 {j['mercado']} ({j['odd']:.2f}) | Score: {j['score']}\n\n"
                        msg += f"🔥 **ELITE MASTER PRO - MÚLTIPLAS AUTÔNOMAS**"

                        if sistema.telegram_client.enviar_mensagem(msg, sistema.config.TELEGRAM_CHAT_ID_ALT2):
                            st.success(f"📤 Múltipla {tipo} enviada como texto!")
                    
                    if formato_multipla in ["Pôster West Ham", "Ambos"]:
                        # CORREÇÃO: Usar o método correto gerar_poster_multipla
                        poster = sistema.poster_generator.gerar_poster_multipla(
                            {"modelo": tipo, "odd_total": odd_total, "jogos": jogos_mult},
                            titulo=f"📅 {data_br_str}"
                        )
                        caption = f"<b>💣 MÚLTIPLA PROFISSIONAL - {tipo}</b>\n"
                        caption += f"<b>📅 {data_br_str}</b>\n"
                        caption += f"<b>🎯 Odds Total: {odd_total:.2f}</b>\n\n"
                        caption += f"<b>🔥 ELITE MASTER PRO</b>"
                        
                        if sistema.telegram_client.enviar_foto(poster, caption=caption):
                            st.success(f"📤 Múltipla {tipo} enviada como pôster!")

            st.success("✅ Processamento concluído!")
    


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
    st.subheader("🤖 ELITE MASTER 3.0 - GERADOR DE MÚLTIPLAS")
    st.caption("Sistema com classificação A/B/C e geração profissional de múltiplas (Over 1.5 + Over 2.5)")
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a2a3a 0%, #0f1a24 100%); padding: 1rem; border-radius: 15px; margin-bottom: 1.5rem; border-left: 4px solid #ffd700;">
        <h4 style="color: #ffd700; margin: 0 0 0.5rem 0;">🎯 GERADOR DE MÚLTIPLAS 3.0 - ELITE MASTER</h4>
        <p style="color: #aaccff; margin: 0; font-size: 0.9rem;">
            🚀 <strong>SISTEMA PROFISSIONAL DE MÚLTIPLAS:</strong>
        </p>
        <ul style="color: #aaccff; font-size: 0.85rem; margin: 0.5rem 0 0 1.5rem;">
            <li>✅ <strong>Classificação NÍVEL A (SEGURO):</strong> Over 1.5 | Estimativa ≥ 2.2 | Confiança ≥ 75%</li>
            <li>✅ <strong>Classificação NÍVEL B (VALOR):</strong> Over 2.5 | Estimativa ≥ 2.7 | Ambas Marcam = SIM</li>
            <li>✅ <strong>Classificação NÍVEL C (PERIGO):</strong> Gols HT | Favorito | Estimativa &lt; 2.0 → EXCLUÍDO</li>
            <li>✅ <strong>Modelo CONSERVADOR:</strong> 3 jogos Over 1.5 (odd média 2.0~3.0) - Alta taxa</li>
            <li>✅ <strong>Modelo HÍBRIDO:</strong> 3x Over 1.5 + 1x Over 2.5 (odd 4.0~6.0) - Estratégia principal</li>
            <li>✅ <strong>Modelo AGRESSIVO:</strong> 3x Over 1.5 + 2x Over 2.5 (odd 8.0+) - Seleção TOP</li>
            <li>✅ <strong>Filtros por liga:</strong> Bundesliga, Eredivisie, Premier League (ENTRAR), Ligue 1, Serie A (FILTRO), Brasileirão, La Liga (EVITAR)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    data_completa = st.date_input(
        "📅 Data para análise",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_completa_autonoma"
    )
    
    st.markdown("### 📊 Tipos de Análise (Fonte de Dados)")
    st.caption("Selecione quais análises o sistema deve considerar como base para decisão")
    
    col1, col2 = st.columns(2)
    with col1:
        incluir_over_under = st.checkbox("⚽ Over/Under de Gols", value=True, key="incluir_ou_auto")
        incluir_favorito = st.checkbox("🏆 Favorito (Vitória)", value=False, key="incluir_fav_auto")
    
    with col2:
        incluir_gols_ht = st.checkbox("⏰ Gols HT (Primeiro Tempo)", value=False, key="incluir_ht_auto")
        incluir_ambas_marcam = st.checkbox("🤝 Ambas Marcam (BTTS)", value=True, key="incluir_am_auto")
    
    tipos_analise_selecionados = {
        "over_under": incluir_over_under,
        "favorito": incluir_favorito,
        "gols_ht": incluir_gols_ht,
        "ambas_marcam": incluir_ambas_marcam
    }
    
    if not any(tipos_analise_selecionados.values()):
        st.warning("⚠️ Selecione pelo menos um tipo de análise para gerar os alertas!")
    
    st.markdown("### 🌍 Seleção de Ligas")
    
    todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, key="todas_ligas_auto")
    
    ligas_selecionadas = []
    if not todas_ligas:
        ligas_selecionadas = st.multiselect(
            "📌 Selecionar ligas",
            options=list(ConfigManager.LIGA_DICT.keys()),
            default=["Premier League (Inglaterra)", "Bundesliga", "Eredivisie"],
            key="ligas_auto"
        )
    
    st.markdown("### ⚙️ Configurações Avançadas")
    
    col1, col2 = st.columns(2)
    with col1:
        score_minimo = st.slider(
            "🎯 Score Mínimo para Aprovação",
            min_value=3,
            max_value=15,
            value=6,
            help="Jogos com score abaixo deste valor serão descartados (recomendado: 6)"
        )
    
    with col2:
        aliviar_envios = st.checkbox(
            "🌙 Modo Aliviado (enviar apenas múltipla principal)",
            value=False,
            help="Ative para enviar apenas a múltipla HÍBRIDA em vez de todas as 3 múltiplas"
        )
    
    st.session_state.enviar_multiplas = True
    st.session_state.aliviar_envios = aliviar_envios
    
    if st.button("🤖 GERAR MÚLTIPLAS PROFISSIONAIS 3.0", type="primary", use_container_width=True):
        if not todas_ligas and not ligas_selecionadas:
            st.error("❌ Selecione pelo menos uma liga")
        elif not any(tipos_analise_selecionados.values()):
            st.error("❌ Selecione pelo menos um tipo de análise")
        else:
            with st.spinner("🔍 Classificando jogos (Níveis A/B/C) e gerando múltiplas..."):
                sistema.processar_alertas_completos(
                    data_completa, 
                    ligas_selecionadas, 
                    todas_ligas, 
                    tipos_analise_selecionados
                )
    
    st.markdown("---")
    st.subheader("📊 Conferir Resultados Completos 3.0")
    st.caption("Confere os resultados dos alertas individuais e das múltiplas. As múltiplas são enviadas apenas quando todos os jogos estiverem finalizados.")
    
    data_resultados_comp = st.date_input(
        "📅 Data para conferência completa",
        value=datetime.today(),
        format="DD/MM/YYYY",
        key="data_resultados_comp"
    )
    
    if st.button("🔄 CONFERIR RESULTADOS COMPLETOS 3.0", use_container_width=True):
        with st.spinner("Conferindo resultados individuais e múltiplas..."):
            sistema.gerenciador_completo.conferir_resultados_completos(data_resultados_comp)
    
    st.markdown("### 📊 Estatísticas Completos")
    
    alertas_comp = sistema.gerenciador_completo.carregar_alertas()
    
    if alertas_comp:
        total = len(alertas_comp)
        conferidos = sum(1 for a in alertas_comp.values() if a.get("conferido", False))
        enviados = sum(1 for a in alertas_comp.values() if a.get("alerta_enviado", False))
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📋 Alertas", total)
        col2.metric("✅ Conferidos", conferidos)
        col3.metric("📤 Enviados", enviados)
        
        mercados_dist = {}
        for alerta in alertas_comp.values():
            decisao = alerta.get("decisao_autonomo", {})
            mercado = decisao.get("mercado", "unknown")
            mercados_dist[mercado] = mercados_dist.get(mercado, 0) + 1
        
        if mercados_dist:
            st.markdown("**🎯 Distribuição de Mercados:**")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("⚽ OVER", mercados_dist.get("over", 0))
            with col_m2:
                st.metric("🤝 BTTS", mercados_dist.get("btts", 0))
            with col_m3:
                st.metric("⏰ HT", mercados_dist.get("ht", 0))
            with col_m4:
                st.metric("🏆 FAV", mercados_dist.get("favorito", 0))
        
        with st.expander("📋 Últimos Alertas"):
            for chave, alerta in list(alertas_comp.items())[:3]:
                decisao = alerta.get("decisao_autonomo", {})
                mercado = decisao.get("mercado", "N/A")
                conf_ajustada = decisao.get("confianca_ajustada", 0) * 100
                st.write(f"**{alerta.get('home')} vs {alerta.get('away')}**")
                st.write(f"📅 {alerta.get('data_busca')} | 🎯 {mercado.upper()} | 🔍 {conf_ajustada:.0f}%")
                if alerta.get("analise_profissional"):
                    analise = alerta["analise_profissional"]
                    st.write(f"🎯 Score: {analise.get('score', 0)} | {analise.get('nivel', 'N/A')}")
                st.write("---")
    else:
        st.info("ℹ️ Nenhum alerta completo salvo ainda.")
    
    multiplas = sistema.gerenciador_completo.carregar_multiplas()
    if multiplas:
        st.markdown("### 💣 Estatísticas de Múltiplas")
        total_multiplas = len(multiplas)
        enviadas = sum(1 for m in multiplas.values() if m.get("enviada", False))
        acertadas = sum(1 for m in multiplas.values() if m.get("acertada", False))
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📋 Total Múltiplas", total_multiplas)
        col2.metric("✅ Enviadas", enviadas)
        col3.metric("🎯 Acertadas", acertadas)
        
        if total_multiplas > 0:
            taxa_acerto = (acertadas / total_multiplas) * 100
            st.metric("📊 Taxa de Acerto", f"{taxa_acerto:.1f}%")


def render_tab_exportar(sistema):
    st.subheader("📥 Exportar Resultados")
    st.caption("Baixe relatórios completos de todos os jogos finalizados")
    
    st.markdown("""
    <div style="background-color: #1a2c1a; padding: 1rem; border-radius: 10px; border: 1px solid #4caf50; margin-bottom: 1.5rem;">
        <h4 style="color: #4caf50; margin-top: 0;">📊 RELATÓRIO COMPLETO 3.0</h4>
        <p style="color: #a5d6a5;">
            Esta ferramenta gera um relatório detalhado com TODOS os jogos finalizados, incluindo:
        </p>
        <ul style="color: #a5d6a5;">
            <li>✅ Resultados de Over/Under com análise completa</li>
            <li>✅ Resultados de Favoritos (Casa/Fora/Empate)</li>
            <li>✅ Resultados de Gols no Primeiro Tempo (HT)</li>
            <li>✅ Resultados de Ambas Marcam (BTTS)</li>
            <li>✅ Estatísticas por liga e consolidadas</li>
            <li>✅ Placar final e placar do intervalo</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📥 GERAR RELATÓRIO COMPLETO", type="primary", use_container_width=True):
            with st.spinner("🔄 Gerando relatórios..."):
                arquivos = sistema.exportar_resultados_para_texto()
                
                if arquivos:
                    st.success(f"✅ {len(arquivos)} relatórios gerados com sucesso!")
                    
                    st.markdown("### 📊 Prévia dos Dados")
                    
                    total_jogos = 0
                    total_greens = 0
                    total_reds = 0
                    
                    for nome, conteudo in arquivos.items():
                        if "COMPLETO" in nome:
                            linhas = conteudo.split('\n')
                            for linha in linhas:
                                if "Total de Jogos:" in linha:
                                    try:
                                        total_jogos = int(linha.split(':')[1].strip())
                                    except:
                                        pass
                                if "✅ GREEN:" in linha:
                                    try:
                                        greens = int(linha.split(':')[1].split('|')[0].strip())
                                        total_greens += greens
                                    except:
                                        pass
                                if "❌ RED:" in linha:
                                    try:
                                        reds = int(linha.split(':')[1].strip())
                                        total_reds += reds
                                    except:
                                        pass
                    
                    col_meta1, col_meta2, col_meta3 = st.columns(3)
                    with col_meta1:
                        st.metric("📋 Total Jogos", total_jogos)
                    with col_meta2:
                        st.metric("✅ Total GREEN", total_greens)
                    with col_meta3:
                        st.metric("❌ Total RED", total_reds)
                    
                    if total_greens + total_reds > 0:
                        taxa_global = (total_greens / (total_greens + total_reds)) * 100
                        st.metric("🎯 Taxa Global", f"{taxa_global:.1f}%")
                    
                    st.markdown("### 📁 Arquivos Disponíveis")
                    
                    for nome_arquivo, conteudo in arquivos.items():
                        tipo = "📋 Consolidado" if "COMPLETO" in nome_arquivo else "🏆 Liga"
                        
                        with st.expander(f"{tipo}: {nome_arquivo}"):
                            st.download_button(
                                label=f"⬇️ Baixar {nome_arquivo}",
                                data=conteudo,
                                file_name=nome_arquivo,
                                mime="text/plain",
                                use_container_width=True
                            )
                            
                            st.text("📄 Primeiras linhas:")
                            linhas_previa = conteudo.split('\n')[:15]
                            st.code("\n".join(linhas_previa), language="text")
                else:
                    st.warning("⚠️ Nenhum resultado encontrado para exportar.")


def render_tab_admin(sistema):
    st.subheader("⚙️ Administração do Sistema 3.0")
    
    with st.expander("📊 Monitoramento", expanded=False):
        stats = sistema.api_monitor.get_stats()
        cache_stats = sistema.image_cache.get_stats()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Requests", stats['total_requests'])
        col2.metric("Sucesso", f"{stats['success_rate']}%")
        col3.metric("Cache Memória", f"{cache_stats['memoria']} img")
        
        col4, col5, col6 = st.columns(3)
        col4.metric("Rate Limit Hits", stats['rate_limit_hits'])
        col5.metric("Requests/min", stats['requests_per_minute'])
        col6.metric("Cache Disco", f"{cache_stats['disco_mb']:.1f} MB")
        
        if st.button("🔄 Resetar Monitoramento", use_container_width=True):
            sistema.api_monitor.reset()
            st.rerun()
    
    with st.expander("🗑️ Limpeza de Cache", expanded=False):
        st.info("Limpa apenas os caches temporários, mantendo os alertas e resultados.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Limpar Cache de Imagens", use_container_width=True):
                with st.spinner("Limpando cache de imagens..."):
                    sistema.image_cache.clear()
                    st.success("✅ Cache de imagens limpo!")
                    time.sleep(1)
                    st.rerun()
        
        with col2:
            if st.button("🧹 Limpar Cache de Dados", use_container_width=True):
                with st.spinner("Limpando caches de dados..."):
                    sistema.api_client.jogos_cache.clear()
                    sistema.api_client.classificacao_cache.clear()
                    sistema.api_client.match_cache.clear()
                    st.success("✅ Caches de dados limpos!")
                    time.sleep(1)
                    st.rerun()
    
    with st.expander("⚠️ ZONA DE PERIGO - RESET TOTAL", expanded=False):
        st.markdown("""
        <div style="background-color: #2c1a1a; padding: 1rem; border-radius: 10px; border: 1px solid #ff4444;">
            <h4 style="color: #ff4444; margin-top: 0;">⚠️ ATENÇÃO - AÇÃO IRREVERSÍVEL</h4>
            <p style="color: #ff9999; font-size: 0.9rem;">
                Esta ação irá APAGAR TODOS OS DADOS do sistema:
            </p>
            <ul style="color: #ff9999; font-size: 0.9rem;">
                <li>✅ Todos os alertas (Over/Under, Favoritos, Gols HT, Ambas Marcam)</li>
                <li>✅ Todos os resultados salvos</li>
                <li>✅ Alertas TOP e Completos</li>
                <li>✅ Múltiplas geradas e seus resultados</li>
                <li>✅ Cache de imagens e escudos</li>
                <li>✅ Histórico de conferências</li>
                <li>✅ Estatísticas de performance</li>
                <li>✅ Sessão do Streamlit</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if 'confirmar_reset' not in st.session_state:
                st.session_state.confirmar_reset = False
            
            if not st.session_state.confirmar_reset:
                if st.button("🗑️ RESETAR SISTEMA COMPLETO", type="primary", use_container_width=True):
                    st.session_state.confirmar_reset = True
                    st.rerun()
            else:
                st.warning("⚠️ **CONFIRMAÇÃO FINAL:** Tem certeza? Esta ação é **IRREVERSÍVEL**!")
                
                col_confirm1, col_confirm2 = st.columns(2)
                with col_confirm1:
                    if st.button("✅ SIM, RESETAR TUDO", use_container_width=True):
                        with st.spinner("🧹 Limpando todo o sistema..."):
                            arquivos = sistema.reset_total_sistema()
                            st.session_state.confirmar_reset = False
                            st.success(f"✅ Sistema completamente resetado! {arquivos} arquivos limpos.")
                            time.sleep(2)
                            st.rerun()
                with col_confirm2:
                    if st.button("❌ CANCELAR", use_container_width=True):
                        st.session_state.confirmar_reset = False
                        st.rerun()


def main():
    st.set_page_config(
        page_title="⚽ Elite Master 3.0",
        page_icon="⚽",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
    <style>
        .stApp {
            background-color: #0a0c10;
        }
        
        .main > div {
            padding: 0.5rem 1rem;
        }
        
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
        
        .stCheckbox {
            background: #1a1f2c;
            padding: 0.5rem;
            border-radius: 12px;
            margin: 0.2rem 0;
        }
        
        .stSlider div[data-baseweb="slider"] {
            padding-top: 1rem;
        }
        
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
        
        .version-badge {
            display: inline-block;
            background: linear-gradient(135deg, #ffd700, #ffa500);
            color: #0a0c10;
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: bold;
            margin-left: 10px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="title-container">
        <div class="main-title">
            <span class="title-icon left">⚽</span>
            <div class="title-text">
                <div class="title-futebol">FUTEBOL</div>
                <div class="title-elite">ELITE MASTER <span class="version-badge">3.0</span></div>
                <div class="title-master">GERADOR DE MÚLTIPLAS</div>
            </div>
            <span class="title-icon right">🏆</span>
        </div>
        <div class="title-decoration"></div>
    </div>
    """, unsafe_allow_html=True)
    
    sistema = SistemaAlertasFutebol()
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["🔍 Buscar", "📊 Resultados", "🏆 TOP", "⚽ Completos 3.0", "🧠 Múltiplas Pro", "📥 Exportar", "⚙️ Admin"])
    
    with tab1:
        render_tab_busca(sistema)
    
    with tab2:
        render_tab_resultados(sistema)
    
    with tab3:
        render_tab_top_alertas(sistema)
    
    with tab4:
        render_tab_completos(sistema)
    
    with tab5:
        render_tab_multiplas_pro(sistema)
    
    with tab6:
        render_tab_exportar(sistema)
    
    with tab7:
        render_tab_admin(sistema)


if __name__ == "__main__":
    main()


st.markdown("""
<style>
.footer-premium{
    width:100%;
    text-align:center;
    padding:22px 10px;
    margin-top:40px;
    background:linear-gradient(180deg,#0b0b0b,#050505);
    color:#ffffff;
    font-family:Arial, Helvetica, sans-serif;
    border-top:1px solid #222;
    position:relative;
}

.footer-premium::before{
    content:"";
    position:absolute;
    top:0;
    left:0;
    width:100%;
    height:2px;
    background:linear-gradient(90deg,#00ffcc,#00aaff,#00ffcc);
    box-shadow:0 0 10px #00ffcc;
}

.footer-title{
    font-size:16px;
    font-weight:800;
    letter-spacing:3px;
    text-transform:uppercase;
    text-shadow:0 0 6px rgba(0,255,200,0.6);
}

.footer-sub{
    font-size:11px;
    color:#bfbfbf;
    margin-top:4px;
    letter-spacing:1.5px;
}
</style>

<div class="footer-premium">
    <div class="footer-title">ELITE MASTER SYSTEM 3.0</div>
    <div class="footer-sub">GERADOR DE MÚLTIPLAS • CLASSIFICAÇÃO A/B/C • SAMUCJ TECNOLOGIA © 2026</div>
</div>
""", unsafe_allow_html=True)
