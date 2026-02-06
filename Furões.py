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
import urllib.parse
import re
from difflib import SequenceMatcher


# =============================
# FUNÇÕES DE PERSISTÊNCIA DE SESSÃO
# =============================

def inicializar_sessao():
    """Inicializa as variáveis de sessão com valores padrão"""
    session_defaults = {
        # Configurações de alertas
        'tipo_analise': "Over/Under de Gols",
        'tipo_filtro': "Todos",
        'min_conf': 70,
        'max_conf': 95,
        'min_conf_vitoria': 65,
        'filtro_favorito': "Todos",
        'min_conf_ht': 60,
        'tipo_ht': "OVER 0.5 HT",
        'min_conf_am': 60,
        'filtro_am': "Todos",
        
        # Configurações de envio
        'alerta_individual': True,
        'alerta_poster': True,
        'alerta_top_jogos': True,
        'alerta_conferencia_auto': True,
        'alerta_resultados': True,
        'formato_top_jogos': "Ambos",
        
        # Configurações gerais
        'top_n': 3,
        'estilo_poster': "West Ham (Novo)",
        
        # Abas específicas
        'data_busca': datetime.today(),
        'data_resultados': datetime.today(),
        'data_resultados_top': datetime.today(),
        'data_odds': datetime.today(),
        'todas_ligas': True,
        'ligas_selecionadas': ["Campeonato Brasileiro Série A", "Premier League (Inglaterra)"],
        
        # Configurações de odds
        'metodo_correlacao_odds': "Rápido (Correlação por similaridade)"
    }
    
    # Inicializar cada chave se não existir
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def salvar_configuracao_sessao():
    """Salva configurações atuais da sessão"""
    # Esta função é chamada sempre que há mudanças nas configurações
    # As configurações já estão salvas automaticamente no st.session_state
    pass

def carregar_configuracao_sessao():
    """Carrega configurações da sessão - já feito por inicializar_sessao()"""
    pass

# =============================
# CLASSES PRINCIPAIS - CORE SYSTEM
# =============================

class ConfigManager:
    """Gerencia configurações e constantes do sistema"""
    
    API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","8351165117:AAFmqb3NrPsmT86_8C360eYzK71Qda1ah_4")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
    TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
    ODDS_API_KEY = os.getenv("ODDS_API_KEY", "e85fb0b2c41521a76fad76800a247663")  # Adicionado
    
    HEADERS = {"X-Auth-Token": API_KEY}
    BASE_URL_FD = "https://api.football-data.org/v4"
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    BASE_URL_ODDS = "https://api.the-odds-api.com/v4"  # Adicionado
    
    # Constantes
    ALERTAS_PATH = "alertas.json"
    ALERTAS_FAVORITOS_PATH = "alertas_favoritos.json"
    ALERTAS_GOLS_HT_PATH = "alertas_gols_ht.json"
    ALERTAS_AMBAS_MARCAM_PATH = "alertas_ambas_marcam.json"  # NOVO
    RESULTADOS_PATH = "resultados.json"
    RESULTADOS_FAVORITOS_PATH = "resultados_favoritos.json"
    RESULTADOS_GOLS_HT_PATH = "resultados_gols_ht.json"
    RESULTADOS_AMBAS_MARCAM_PATH = "resultados_ambas_marcam.json"  # NOVO
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
        "match_details": {"ttl": 1800, "max_size": 200},
        "odds": {"ttl": 300, "max_size": 50}  # Adicionado
    }
    
    @classmethod
    def get_liga_id(cls, liga_nome):
        """Obtém o ID da liga a partir do nome"""
        return cls.LIGA_DICT.get(liga_nome)


# =============================
# CLASSE ATUALIZADA: API DE ODDS (COM CORREÇÕES)
# =============================
# =============================
# CLASSE ATUALIZADA: API DE ODDS (COM CORREÇÕES)
# =============================

class APIOddsClient:
    """Cliente especializado para buscar odds de diferentes provedores - CORRIGIDO"""
    
    def __init__(self, rate_limiter, api_monitor):
        self.rate_limiter = rate_limiter
        self.api_monitor = api_monitor
        self.config = ConfigManager()
        self.odds_cache = SmartCache("odds")
        
        # Mapeamento CORRIGIDO de ligas para sport keys da Odds API
        # USANDO OS SPORT_KEYS EXATOS DA RESPOSTA DA API
        self.liga_map_corrigido = {
            "PL": "soccer_epl",                          # Premier League
            "BL1": "soccer_germany_bundesliga",          # Bundesliga
            "SA": "soccer_italy_serie_a",                # Serie A
            "PD": "soccer_spain_la_liga",                # La Liga
            "FL1": "soccer_france_ligue_one",            # Ligue 1
            "BSA": "soccer_brazil_campeonato",           # Brasileirão
            "CL": "soccer_uefa_champions_league",        # Champions League (CORRIGIDO)
            "ELC": "soccer_efl_champ",                   # Championship (CORRIGIDO: soccer_efl_champ)
            "PPL": "soccer_portugal_primeira_liga",      # Primeira Liga
            "DED": "soccer_netherlands_eredivisie",      # Eredivisie
            "WC": "soccer_fifa_world_cup",               # FIFA World Cup
            "EC": "soccer_euro_championship"             # European Championship
        }
    
    def obter_odds_com_retry(self, url: str, timeout: int = 15, max_retries: int = 3) -> dict | None:
        """Obtém dados da API de odds com rate limiting e retry"""
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                
                logging.info(f"💰 Request odds {attempt+1}/{max_retries}: {url}")
                
                response = requests.get(url, timeout=timeout)
                
                # Verificar headers da Odds API para quota
                remaining = response.headers.get('x-requests-remaining', 'unknown')
                used = response.headers.get('x-requests-used', 'unknown')
                logging.info(f"📊 Quota Odds API: Restantes={remaining}, Usadas={used}")
                
                if response.status_code == 422:
                    # Erro específico - endpoint não suportado
                    logging.error(f"❌ Endpoint não suportado: {url}")
                    st.error("⚠️ Esta funcionalidade não é suportada pela Odds API")
                    return None
                    
                if response.status_code == 404:
                    # Erro 404 - sport key incorreto
                    logging.error(f"❌ Sport key não encontrado (404): {url}")
                    st.error(f"⚠️ Sport key incorreto. Verifique o mapeamento.")
                    return None
                    
                if response.status_code == 429:
                    self.api_monitor.log_request(False, True)
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logging.warning(f"⏳ Rate limit da API de odds. Esperando {retry_after} segundos...")
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
            st.error(f"Erro ao buscar odds: {str(e)}")
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
                st.error("❌ API Key inválida ou expirada")
                return False
            else:
                st.error(f"❌ Erro na conexão: {response.status_code}")
                return False
                
        except Exception as e:
            st.error(f"❌ Erro de conexão: {e}")
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
# NOVA CLASSE: Correlacionador de Jogos
# =============================

class JogoCorrelacionador:
    """Classe para correlacionar jogos entre diferentes APIs (Odds API vs Football API)"""
    
    @staticmethod
    def normalizar_nome_time(nome: str) -> str:
        """Normaliza o nome do time para comparação"""
        if not nome:
            return ""
        
        nome = nome.lower()
        nome = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('ASCII')
        
        palavras_remover = [
            'fc','cf','sc','ac','as','us','ss','fk','bk','if','ff',
            'club','football','soccer','association','sports','team',
            'de','do','da','das','dos','the','and','&'
        ]
        
        palavras = nome.split()
        palavras_filtradas = [p for p in palavras if p not in palavras_remover and len(p) > 1]
        
        nome_normalizado = ' '.join(palavras_filtradas)
        nome_normalizado = re.sub(r'[^\w\s]', '', nome_normalizado)
        nome_normalizado = re.sub(r'\d+', '', nome_normalizado)
        
        return nome_normalizado.strip()
    
    @staticmethod
    def similaridade_strings(str1: str, str2: str) -> float:
        """Calcula similaridade entre duas strings (0 a 1)"""
        if not str1 or not str2:
            return 0.0
        
        str1_norm = JogoCorrelacionador.normalizar_nome_time(str1)
        str2_norm = JogoCorrelacionador.normalizar_nome_time(str2)
        
        if not str1_norm or not str2_norm:
            return 0.0
        
        if str1_norm == str2_norm:
            return 1.0
        
        similaridade = SequenceMatcher(None, str1_norm, str2_norm).ratio()
        
        if str1_norm in str2_norm or str2_norm in str1_norm:
            similaridade = max(similaridade, 0.8)
        
        siglas_comuns = {
            'man utd': 'manchester united',
            'man city': 'manchester city',
            'spurs': 'tottenham',
            'rm': 'real madrid',
            'barca': 'barcelona',
            'psg': 'paris saint germain',
            'inter': 'internazionale',
            'milan': 'ac milan',
        }
        
        for sigla, nome_completo in siglas_comuns.items():
            if (str1_norm == sigla and str2_norm == nome_completo) or \
               (str2_norm == sigla and str1_norm == nome_completo):
                return 0.9
        
        return similaridade
    
    @staticmethod
    def correlacionar_jogos(jogo_alerta: dict, odds_data_list: list, threshold: float = 0.7) -> dict:
        """Correlaciona um jogo do alerta com os dados de odds"""
        if not jogo_alerta or not odds_data_list:
            return {}
        
        home_alerta = jogo_alerta.get('home', '')
        away_alerta = jogo_alerta.get('away', '')
        
        melhor_correlacao = 0.0
        melhor_odds_data = {}
        
        for odds_data in odds_data_list:
            home_odds = odds_data.get('home_team', '')
            away_odds = odds_data.get('away_team', '')
            
            sim_normal = (
                JogoCorrelacionador.similaridade_strings(home_alerta, home_odds) +
                JogoCorrelacionador.similaridade_strings(away_alerta, away_odds)
            ) / 2
            
            sim_invertida = (
                JogoCorrelacionador.similaridade_strings(home_alerta, away_odds) +
                JogoCorrelacionador.similaridade_strings(away_alerta, home_odds)
            ) / 2
            
            similaridade_final = max(sim_normal, sim_invertida)
            
            if similaridade_final > melhor_correlacao:
                melhor_correlacao = similaridade_final
                melhor_odds_data = odds_data.copy()
                melhor_odds_data['similaridade'] = similaridade_final
        
        if melhor_correlacao >= threshold:
            return melhor_odds_data
        
        return {}


# =============================
# CLASSE ATUALIZADA: ODDS MANAGER (COM CORREÇÕES)
# =============================

class OddsManager:
    """Gerencia análise e apresentação de odds"""
    
    def __init__(self, api_client, odds_client):
        self.api_client = api_client
        self.odds_client = odds_client
    
    def processar_odds_jogo(self, odds_data: dict, analise: dict, jogo) -> dict:
        """Processa e analisa odds de um jogo"""
        if not odds_data or "bookmakers" not in odds_data:
            return None
        
        resultados = {
            "home_odds": [],
            "draw_odds": [],
            "away_odds": [],
            "over_15_odds": [],
            "over_25_odds": [],
            "over_35_odds": [],
            "under_15_odds": [],
            "under_25_odds": [],
            "under_35_odds": [],
            "melhores_odds": {}
        }
        
        for bookmaker in odds_data.get("bookmakers", []):
            bm_name = bookmaker.get("title", "")
            
            for market in bookmaker.get("markets", []):
                key = market.get("key")
                
                for o in market.get("outcomes", []):
                    odds = o.get("price")
                    if odds is None or odds <= 1.01:
                        continue
                    
                    name = o.get("name", "")
                    name_norm = JogoCorrelacionador.normalizar_nome_time(name)
                    
                    if key == "h2h":
                        if name_norm == JogoCorrelacionador.normalizar_nome_time(jogo.home_team) or name == "Home":
                            resultados["home_odds"].append({"bookmaker": bm_name, "odds": odds})
                        elif name == "Draw":
                            resultados["draw_odds"].append({"bookmaker": bm_name, "odds": odds})
                        elif name_norm == JogoCorrelacionador.normalizar_nome_time(jogo.away_team) or name == "Away":
                            resultados["away_odds"].append({"bookmaker": bm_name, "odds": odds})
                    
                    elif key == "totals":
                        point = o.get("point")
                        
                        if "Over" in name:
                            if point == 1.5:
                                resultados["over_15_odds"].append({"bookmaker": bm_name, "odds": odds})
                            elif point == 2.5:
                                resultados["over_25_odds"].append({"bookmaker": bm_name, "odds": odds})
                            elif point == 3.5:
                                resultados["over_35_odds"].append({"bookmaker": bm_name, "odds": odds})
                        
                        elif "Under" in name:
                            if point == 1.5:
                                resultados["under_15_odds"].append({"bookmaker": bm_name, "odds": odds})
                            elif point == 2.5:
                                resultados["under_25_odds"].append({"bookmaker": bm_name, "odds": odds})
                            elif point == 3.5:
                                resultados["under_35_odds"].append({"bookmaker": bm_name, "odds": odds})
        
        resultados["melhores_odds"] = self.calcular_melhores_odds(resultados)
        return resultados
    
    def calcular_melhores_odds(self, odds_data: dict) -> dict:
        """Calcula as melhores odds disponíveis"""
        melhores = {}
        
        if odds_data["home_odds"]:
            melhores["home_best"] = max(odds_data["home_odds"], key=lambda x: x["odds"])
        if odds_data["away_odds"]:
            melhores["away_best"] = max(odds_data["away_odds"], key=lambda x: x["odds"])
        if odds_data["draw_odds"]:
            melhores["draw_best"] = max(odds_data["draw_odds"], key=lambda x: x["odds"])
        if odds_data["over_15_odds"]:
            melhores["over_15_best"] = max(odds_data["over_15_odds"], key=lambda x: x["odds"])
        if odds_data["over_25_odds"]:
            melhores["over_25_best"] = max(odds_data["over_25_odds"], key=lambda x: x["odds"])
        if odds_data["over_35_odds"]:
            melhores["over_35_best"] = max(odds_data["over_35_odds"], key=lambda x: x["odds"])
        if odds_data["under_15_odds"]:
            melhores["under_15_best"] = max(odds_data["under_15_odds"], key=lambda x: x["odds"])
        if odds_data["under_25_odds"]:
            melhores["under_25_best"] = max(odds_data["under_25_odds"], key=lambda x: x["odds"])
        if odds_data["under_35_odds"]:
            melhores["under_35_best"] = max(odds_data["under_35_odds"], key=lambda x: x["odds"])
        
        return melhores

# =============================
# RESTANTE DO CÓDIGO (INCLUINDO CLASSES EXISTENTES)
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
    def carregar_alertas_top() -> list:
        """Carrega alertas TOP do arquivo"""
        dados = DataStorage.carregar_json(ConfigManager.ALERTAS_TOP_PATH)
        if isinstance(dados, dict):
            # Converter dict para list se necessário
            return list(dados.values())
        elif isinstance(dados, list):
            return dados
        return []
    
    @staticmethod
    def salvar_alertas_top(alertas_top: list):
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
        self.resultado_ambas_marcam = None  # NOVO
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
        self.tendencia_ambas_marcam = ""  # NOVO
        self.confianca_ambas_marcam = 0.0  # NOVO
        self.prob_ambas_marcam_sim = 0.0  # NOVO
        self.prob_ambas_marcam_nao = 0.0  # NOVO
    
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
            logging.error(f"Erro ao convertir data {self.utc_date}: {e}")
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
        
        # Verificar se é OVER
        if "OVER" in self.tendencia.upper():
            # Extrair número da tendência (ex: "OVER 3.5" -> 3.5)
            if "OVER 1.5" in self.tendencia and total_gols > 1.5:
                return "GREEN"
            elif "OVER 2.5" in self.tendencia and total_gols > 2.5:
                return "GREEN"
            elif "OVER 3.5" in self.tendencia and total_gols > 3.5:
                return "GREEN"
            elif "OVER 4.5" in self.tendencia and total_gols > 4.5:
                return "GREEN"
        
        # Verificar se é UNDER
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
            return "GREEN"
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
            "resultado_ambas_marcam": self.resultado_ambas_marcam  # NOVO
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
        self.tipo_alerta = tipo_alerta  # "over_under", "favorito", "gols_ht", "ambas_marcam"
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
        fator_casa = 1.1  # Aumenta chance do time da casa marcar
        prob_home_marca *= fator_casa
        prob_away_marca *= (2.0 - fator_casa) * 0.9  # Reduz um pouco a chance do visitante

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
            # Se estiver próximo, usar a maior probabilidade
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

@staticmethod
def calcular_conflito_over_btts(
    home: str,
    away: str,
    classificacao: dict,
    estimativa_total: float,
    resultado_btts: dict
) -> dict:
    """
    Resolve conflito inteligente entre OVER e BTTS
    Retorna prioridade de mercado e flags de bloqueio
    """

    dados_home = classificacao.get(home, {})
    dados_away = classificacao.get(away, {})

    played_home = max(dados_home.get("played", 1), 1)
    played_away = max(dados_away.get("played", 1), 1)

    media_home = dados_home.get("scored", 0) / played_home
    media_away = dados_away.get("scored", 0) / played_away

    # -----------------------------
    # MÉTRICAS DE DECISÃO
    # -----------------------------
    equilibrio_ofensivo = 1 - abs(media_home - media_away)
    equilibrio_ofensivo = clamp(equilibrio_ofensivo, 0, 1)

    ataque_unilateral = (
        (media_home >= 1.8 and media_away < 1.0) or
        (media_away >= 1.8 and media_home < 1.0)
    )

    prob_btts_sim = resultado_btts.get("sim", 0)
    prob_btts_nao = resultado_btts.get("nao", 0)

    # -----------------------------
    # DECISÃO FINAL
    # -----------------------------
    prioridade = "NEUTRO"
    bloquear_btts = False
    bloquear_over = False
    motivo = "Sem conflito relevante"

    # CASO 1 — OVER forte, BTTS perigoso
    if ataque_unilateral and estimativa_total >= 2.6:
        prioridade = "OVER"
        bloquear_btts = True
        motivo = "Ataque unilateral (OVER sem BTTS)"

    # CASO 2 — BTTS melhor que OVER 2.5
    elif equilibrio_ofensivo >= 0.75 and 2.2 <= estimativa_total <= 2.6:
        prioridade = "BTTS"
        bloquear_over = True
        motivo = "Equilíbrio ofensivo (BTTS prioritário)"

    # CASO 3 — OVER 1.5 vence
    elif equilibrio_ofensivo >= 0.6 and estimativa_total >= 2.0:
        prioridade = "OVER_1.5"
        motivo = "Jogo vivo sem garantia de BTTS"

    # CASO 4 — JOGO TRAVADO
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
def calcular_escore_confianca(
    probabilidade: float,
    confianca: float,
    estimativa_total: float,
    linha_mercado: float,
    conflito: dict
) -> int:
    """
    Calcula o Escore Único de Confiança (0 a 100)
    """

    # -----------------------------
    # NORMALIZAÇÃO BASE
    # -----------------------------
    prob_norm = clamp(probabilidade / 100, 0, 1)
    conf_norm = clamp(confianca / 100, 0, 1)

    base = (prob_norm * 0.6) + (conf_norm * 0.4)

    # -----------------------------
    # DISTÂNCIA DA LINHA
    # -----------------------------
    distancia = estimativa_total - linha_mercado
    bonus_distancia = clamp(distancia / 1.2, 0, 1) * 0.25

    # -----------------------------
    # CONFLITO OVER × BTTS
    # -----------------------------
    penalidade_conflito = 0

    if conflito:
        if conflito.get("bloquear_over") or conflito.get("bloquear_btts"):
            penalidade_conflito += 0.20

        prioridade = conflito.get("prioridade")
        if prioridade in ("EVITAR", "NEUTRO"):
            penalidade_conflito += 0.15

    # -----------------------------
    # CÁLCULO FINAL
    # -----------------------------
    escore = base + bonus_distancia - penalidade_conflito
    escore = clamp(escore, 0, 1)

    return int(round(escore * 100))

#class AnalisadorTendencia:
class AnalisadorTendencia:
    """Analisa tendências de gols em partidas - VERSÃO FINAL PROFISSIONAL"""

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

        # =============================
        # MÉDIAS DE GOLS
        # =============================
        media_home_feitos = dados_home.get("scored", 0) / played_home
        media_home_sofridos = dados_home.get("against", 0) / played_home
        media_away_feitos = dados_away.get("scored", 0) / played_away
        media_away_sofridos = dados_away.get("against", 0) / played_away

        media_home_feitos = clamp(media_home_feitos, 0.6, 3.6)
        media_home_sofridos = clamp(media_home_sofridos, 0.6, 3.2)
        media_away_feitos = clamp(media_away_feitos, 0.6, 3.4)
        media_away_sofridos = clamp(media_away_sofridos, 0.6, 3.2)

        # =============================
        # ESTIMATIVA DE GOLS (VALIDADA)
        # =============================
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

        # =============================
        # ESCOLHA DO MERCADO
        # =============================
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

        # =============================
        # FILTRO FINAL 1 — UNDER PERIGOSO
        # =============================
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

        # =============================
        # FILTRO FINAL 2 — PROMOVER OVER 2.5
        # =============================
        if tipo_aposta == "over" and estimativa_total >= 2.75 and fator_ataque >= 1.2:
            mercado = "OVER 2.5"
            tipo_aposta = "over"
            linha_mercado = 2.5
            probabilidade_base = sigmoid((estimativa_total - 2.5) * 1.15)

        # =============================
        # CONFIANÇA
        # =============================
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

        # =============================
        # FILTRO FINAL 3 — OVER 1.5 CONTROLADO
        # =============================
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
# NOVA CLASSE: ResultadosTopAlertas (CORRIGIDA)
# =============================

class ResultadosTopAlertas:
    """Gerencia resultados dos alertas TOP"""
    
    def __init__(self, sistema_principal):
        self.sistema = sistema_principal
        self.config = ConfigManager()
    
    def conferir_resultados_top_alertas(self, data_selecionada):
        """Conferir resultados apenas dos alertas TOP salvos"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.subheader(f"🏆 Conferindo Resultados TOP Alertas - {data_selecionada.strftime('%d/%m/%Y')}")
        
        # Carregar alertas TOP
        alertas_top = DataStorage.carregar_alertas_top()
        if not alertas_top:
            st.warning("⚠️ Nenhum alerta TOP salvo para conferência")
            return
        
        # Filtrar alertas da data selecionada
        alertas_data = {}
        for alerta in alertas_top:
            if alerta.get("data_busca") == hoje:
                fixture_id = alerta.get("id")
                if fixture_id:
                    alertas_data[fixture_id] = alerta
        
        if not alertas_data:
            st.warning(f"⚠️ Nenhum alerta TOP encontrado para {data_selecionada.strftime('%d/%m/%Y')}")
            return
        
        st.info(f"🔍 Encontrados {len(alertas_data)} alertas TOP para conferência")
        
        # Dividir por tipo de alerta
        resultados_totais = {
            "over_under": {},
            "favorito": {},
            "gols_ht": {},
            "ambas_marcam": {}  # NOVO
        }
        
        # Lista para gerar posters
        jogos_para_poster = {
            "over_under": [],
            "favorito": [],
            "gols_ht": [],
            "ambas_marcam": []  # NOVO
        }
        
        # Conferir cada alerta
        progress_bar = st.progress(0)
        total_alertas = len(alertas_data)
        
        for idx, (fixture_id, alerta) in enumerate(alertas_data.items()):
            tipo_alerta = alerta.get("tipo_alerta", "over_under")
            
            # Obter detalhes atualizados do jogo
            match_data = self.sistema.api_client.obter_detalhes_jogo(fixture_id)
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
                
                # Obter URLs dos escudos - IMPORTANTE: obter dos dados atuais
                home_crest = match_data.get("homeTeam", {}).get("crest") or ""
                away_crest = match_data.get("awayTeam", {}).get("crest") or ""
                
                # Se não tiver escudo nos dados atuais, usar o salvo no alerta
                if not home_crest and alerta.get("escudo_home"):
                    home_crest = alerta["escudo_home"]
                if not away_crest and alerta.get("escudo_away"):
                    away_crest = alerta["escudo_away"]
                
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
                
                # Definir resultado
                jogo.set_resultado(home_goals, away_goals, ht_home_goals, ht_away_goals)
                
                # Marcar como conferido no alerta TOP
                alerta["conferido"] = True
                alerta["home_goals"] = home_goals
                alerta["away_goals"] = away_goals
                alerta["ht_home_goals"] = ht_home_goals
                alerta["ht_away_goals"] = ht_away_goals
                alerta["data_conferencia"] = datetime.now().isoformat()
                alerta["escudo_home"] = home_crest  # Garantir que tem o URL do escudo
                alerta["escudo_away"] = away_crest  # Garantir que tem o URL do escudo
                
                # Calcular resultados
                if tipo_alerta == "over_under":
                    alerta["resultado"] = jogo.resultado
                elif tipo_alerta == "favorito":
                    alerta["resultado_favorito"] = jogo.resultado_favorito
                elif tipo_alerta == "gols_ht":
                    alerta["resultado_ht"] = jogo.resultado_ht
                elif tipo_alerta == "ambas_marcam":
                    alerta["resultado_ambas_marcam"] = jogo.resultado_ambas_marcam
                
                # Adicionar ao tipo correspondente
                resultados_totais[tipo_alerta][fixture_id] = alerta
                
                # Preparar dados para o poster
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
                    "resultado": jogo.resultado if tipo_alerta == "over_under" else None,
                    "resultado_favorito": jogo.resultado_favorito if tipo_alerta == "favorito" else None,
                    "resultado_ht": jogo.resultado_ht if tipo_alerta == "gols_ht" else None,
                    "resultado_ambas_marcam": jogo.resultado_ambas_marcam if tipo_alerta == "ambas_marcam" else None,
                }
                
                # Adicionar dados específicos do tipo
                if tipo_alerta == "over_under":
                    dados_poster.update({
                        "tendencia": alerta.get("tendencia", ""),
                        "estimativa": alerta.get("estimativa", 0.0),
                        "probabilidade": alerta.get("probabilidade", 0.0),
                        "confianca": alerta.get("confianca", 0.0),
                        "tipo_aposta": alerta.get("tipo_aposta", ""),
                    })
                elif tipo_alerta == "favorito":
                    dados_poster.update({
                        "favorito": alerta.get("favorito", ""),
                        "confianca_vitoria": alerta.get("confianca_vitoria", 0.0),
                        "prob_home_win": alerta.get("prob_home_win", 0.0),
                        "prob_away_win": alerta.get("prob_away_win", 0.0),
                        "prob_draw": alerta.get("prob_draw", 0.0),
                    })
                elif tipo_alerta == "gols_ht":
                    dados_poster.update({
                        "tendencia_ht": alerta.get("tendencia_ht", ""),
                        "confianca_ht": alerta.get("confianca_ht", 0.0),
                        "estimativa_total_ht": alerta.get("estimativa_total_ht", 0.0),
                    })
                elif tipo_alerta == "ambas_marcam":
                    dados_poster.update({
                        "tendencia_ambas_marcam": alerta.get("tendencia_ambas_marcam", ""),
                        "confianca_ambas_marcam": alerta.get("confianca_ambas_marcam", 0.0),
                        "prob_ambas_marcam_sim": alerta.get("prob_ambas_marcam_sim", 0.0),
                        "prob_ambas_marcam_nao": alerta.get("prob_ambas_marcam_nao", 0.0),
                    })
                
                jogos_para_poster[tipo_alerta].append(dados_poster)
                
                # Mostrar resultado
                self._mostrar_resultado_alerta_top(alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo)
            
            progress_bar.progress((idx + 1) / total_alertas)
        
        # Salvar alertas TOP atualizados
        DataStorage.salvar_alertas_top(alertas_top)
        
        # Mostrar resumo
        self._mostrar_resumo_resultados_top(resultados_totais)
        
        # Gerar posters de resultados - AGORA COM DADOS COMPLETOS DOS ESCUDOS
        self._gerar_posters_resultados_top(jogos_para_poster, data_selecionada)
    
    def _mostrar_resultado_alerta_top(self, alerta, home_goals, away_goals, ht_home_goals, ht_away_goals, jogo):
        """Mostrar resultado individual do alerta TOP"""
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
    
    def _mostrar_resumo_resultados_top(self, resultados_totais):
        """Mostrar resumo dos resultados TOP"""
        st.markdown("---")
        st.subheader("📈 RESUMO TOP ALERTAS")
        
        col1, col2, col3, col4 = st.columns(4)  # Alterado para 4 colunas
        
        with col1:
            if resultados_totais["over_under"]:
                greens = sum(1 for r in resultados_totais["over_under"].values() if r.get("resultado") == "GREEN")
                reds = sum(1 for r in resultados_totais["over_under"].values() if r.get("resultado") == "RED")
                total = len(resultados_totais["over_under"])
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("⚽ TOP Over/Under", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        with col2:
            if resultados_totais["favorito"]:
                greens = sum(1 for r in resultados_totais["favorito"].values() if r.get("resultado_favorito") == "GREEN")
                reds = sum(1 for r in resultados_totais["favorito"].values() if r.get("resultado_favorito") == "RED")
                total = len(resultados_totais["favorito"])
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("🏆 TOP Favoritos", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        with col3:
            if resultados_totais["gols_ht"]:
                greens = sum(1 for r in resultados_totais["gols_ht"].values() if r.get("resultado_ht") == "GREEN")
                reds = sum(1 for r in resultados_totais["gols_ht"].values() if r.get("resultado_ht") == "RED")
                total = len(resultados_totais["gols_ht"])
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("⏰ TOP Gols HT", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
        
        with col4:
            if resultados_totais["ambas_marcam"]:
                greens = sum(1 for r in resultados_totais["ambas_marcam"].values() if r.get("resultado_ambas_marcam") == "GREEN")
                reds = sum(1 for r in resultados_totais["ambas_marcam"].values() if r.get("resultado_ambas_marcam") == "RED")
                total = len(resultados_totais["ambas_marcam"])
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    st.metric("🤝 TOP Ambas Marcam", f"{greens}✅ {reds}❌", f"{taxa_acerto:.1f}% acerto")
    
    def _gerar_posters_resultados_top(self, jogos_por_tipo: dict, data_selecionada):
        """Gerar posters de resultados para os alertas TOP"""
        data_str = data_selecionada.strftime("%d/%m/%Y")
        
        for tipo_alerta, jogos_lista in jogos_por_tipo.items():
            if not jogos_lista:
                continue
            
            # Gerar poster específico para TOP alertas
            try:
                if tipo_alerta == "over_under":
                    titulo = f"🏆 RESULTADOS TOP OVER/UNDER - {data_str}"
                elif tipo_alerta == "favorito":
                    titulo = f"🏆 RESULTADOS TOP FAVORITOS - {data_str}"
                elif tipo_alerta == "gols_ht":
                    titulo = f"🏆 RESULTADOS TOP GOLS HT - {data_str}"
                elif tipo_alerta == "ambas_marcam":
                    titulo = f"🏆 RESULTADOS TOP AMBAS MARCAM - {data_str}"
                
                # Calcular estatísticas
                if tipo_alerta == "over_under":
                    greens = sum(1 for j in jogos_lista if j.get("resultado") == "GREEN")
                    reds = sum(1 for j in jogos_lista if j.get("resultado") == "RED")
                elif tipo_alerta == "favorito":
                    greens = sum(1 for j in jogos_lista if j.get("resultado_favorito") == "GREEN")
                    reds = sum(1 for j in jogos_lista if j.get("resultado_favorito") == "RED")
                elif tipo_alerta == "gols_ht":
                    greens = sum(1 for j in jogos_lista if j.get("resultado_ht") == "GREEN")
                    reds = sum(1 for j in jogos_lista if j.get("resultado_ht") == "RED")
                elif tipo_alerta == "ambas_marcam":
                    greens = sum(1 for j in jogos_lista if j.get("resultado_ambas_marcam") == "GREEN")
                    reds = sum(1 for j in jogos_lista if j.get("resultado_ambas_marcam") == "RED")
                
                total = greens + reds
                if total > 0:
                    taxa_acerto = (greens / total) * 100
                    
                    # Gerar poster - AGORA COM OS DADOS COMPLETOS DOS ESCUDOS
                    poster = self.sistema.poster_generator.gerar_poster_resultados(jogos_lista, tipo_alerta)
                    
                    caption = f"<b>{titulo}</b>\n\n"
                    caption += f"<b>📊 TOP ALERTAS: {len(jogos_lista)} JOGOS</b>\n"
                    caption += f"<b>✅ GREEN: {greens} jogos</b>\n"
                    caption += f"<b>❌ RED: {reds} jogos</b>\n"
                    caption += f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                    caption += f"<b>🔥 ELITE MASTER SYSTEM - TOP PERFORMANCE</b>"
                    
                    # Enviar poster
                    if self.sistema.telegram_client.enviar_foto(poster, caption=caption):
                        st.success(f"🏆 Poster resultados TOP {tipo_alerta} enviado!")
                    
            except Exception as e:
                logging.error(f"Erro ao gerar poster resultados TOP {tipo_alerta}: {e}")
                st.error(f"❌ Erro no poster TOP {tipo_alerta}: {e}")

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
                cor_borda = (255, 87, 34)  # Laranja para favoritos
            elif tipo_alerta == "gols_ht":
                cor_borda = (76, 175, 80)  # Verde para HT
            elif tipo_alerta == "ambas_marcam":
                cor_borda = (155, 89, 182)  # Roxo para Ambas Marcam
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
        ALTURA_POR_JOGO = 800 # Aumentei um pouco para acomodar o badge GREEN/RED
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
        FONTE_RESULTADO_BADGE = self.criar_fonte(65)  # Fonte para o badge GREEN/RED

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
# SISTEMA PRINCIPAL (ATUALIZADO COM ODDS)
# =============================

# =============================
# SISTEMA PRINCIPAL (ATUALIZADO COM ODDS)
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
        self.resultados_top = ResultadosTopAlertas(self)  # Instância da nova classe
        
        # Inicializar clientes de odds
        self.odds_client = APIOddsClient(self.rate_limiter, self.api_monitor)
        self.odds_manager = OddsManager(self.api_client, self.odds_client)
        self.alerts_odds_manager = AlertsManagerComOdds(self.api_client, self.odds_client)
        
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
                       formato_top_jogos, tipo_filtro, tipo_analise, config_analise):
        """Processa jogos e gera alertas - CORRIGIDO"""
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
                    
                    # Calcular análise de tendência principal (Over/Under)
                    analise = analisador.calcular_tendencia_completa(jogo.home_team, jogo.away_team)
                    
                    # Calcular análises adicionais
                    dados_analise_extra = {}
                    
                    # SEMPRE calcular análises de favorito, HT e ambas marcam
                    if classificacao:
                        # 1. Análise de Favorito (Vitória)
                        vitoria_analise = AnalisadorEstatistico.calcular_probabilidade_vitoria(
                            jogo.home_team, jogo.away_team, classificacao
                        )
                        dados_analise_extra["vitoria"] = vitoria_analise
                        
                        # 2. Análise de Gols HT
                        ht_analise = AnalisadorEstatistico.calcular_probabilidade_gols_ht(
                            jogo.home_team, jogo.away_team, classificacao
                        )
                        dados_analise_extra["gols_ht"] = ht_analise
                        
                        # 3. Análise de Ambas Marcam
                        ambas_marcam_analise = AnalisadorEstatistico.calcular_probabilidade_ambas_marcam(
                            jogo.home_team, jogo.away_team, classificacao
                        )
                        dados_analise_extra["ambas_marcam"] = ambas_marcam_analise
                    
                    # Atualizar análise do jogo com dados extras
                    analise["detalhes"].update(dados_analise_extra)
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
                    
                    # **CORREÇÃO CRÍTICA: Verificar e enviar alertas baseado no tipo de análise selecionado**
                    if tipo_analise == "Over/Under de Gols":
                        # Filtro original para Over/Under
                        if min_conf <= analise["confianca"] <= max_conf:
                            if tipo_filtro == "Todos" or \
                               (tipo_filtro == "Apenas Over" and analise["tipo_aposta"] == "over") or \
                               (tipo_filtro == "Apenas Under" and analise["tipo_aposta"] == "under"):
                                self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, 
                                                             min_conf, max_conf, "over_under")
                    
                    elif tipo_analise == "Favorito (Vitória)":
                        # Configurações específicas para favorito
                        min_conf_vitoria = config_analise.get("min_conf_vitoria", 65)
                        filtro_favorito = config_analise.get("filtro_favorito", "Todos")
                        
                        if 'vitoria' in analise['detalhes']:
                            v = analise['detalhes']['vitoria']
                            
                            # Verificar confiança mínima
                            if v['confianca_vitoria'] >= min_conf_vitoria:
                                # Verificar filtro de favorito
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
                        # Configurações específicas para HT
                        min_conf_ht = config_analise.get("min_conf_ht", 60)
                        tipo_ht = config_analise.get("tipo_ht", "OVER 0.5 HT")
                        
                        if 'gols_ht' in analise['detalhes']:
                            ht = analise['detalhes']['gols_ht']
                            
                            # Verificar confiança mínima e tipo
                            if ht['confianca_ht'] >= min_conf_ht and ht['tendencia_ht'] == tipo_ht:
                                self._verificar_enviar_alerta(jogo, match_data, analise, alerta_individual, 
                                                             min_conf_ht, 100, "gols_ht")
                    
                    elif tipo_analise == "Ambas Marcam (BTTS)":
                        # Configurações específicas para ambas marcam
                        min_conf_am = config_analise.get("min_conf_am", 60)
                        filtro_am = config_analise.get("filtro_am", "Todos")
                        
                        if 'ambas_marcam' in analise['detalhes']:
                            am = analise['detalhes']['ambas_marcam']
                            
                            # Verificar confiança mínima
                            if am['confianca_ambas_marcam'] >= min_conf_am:
                                # Verificar filtro
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
        
        # Filtrar por tipo de análise
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
    
    def conferir_resultados(self, data_selecionada):
        """Conferir resultados dos jogos com alertas ativos"""
        hoje = data_selecionada.strftime("%Y-%m-%d")
        st.subheader(f"📊 Conferindo Resultados para {data_selecionada.strftime('%d/%m/%Y')}")
        
        # Conferir resultados para todos os tipos de alerta
        resultados_totais = {
            "over_under": self._conferir_resultados_tipo("over_under", hoje),
            "favorito": self._conferir_resultados_tipo("favorito", hoje),
            "gols_ht": self._conferir_resultados_tipo("gols_ht", hoje),
            "ambas_marcam": self._conferir_resultados_tipo("ambas_marcam", hoje)  # NOVO
        }
        
        # Mostrar resumo
        st.markdown("---")
        st.subheader("📈 RESUMO DE RESULTADOS")
        
        col1, col2, col3, col4 = st.columns(4)  # Alterado para 4 colunas
        
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
        
        # Enviar alertas de resultados automaticamente em lotes de 3
        if any(resultados_totais.values()):
            st.info("🚨 Enviando alertas de resultados automaticamente...")
            self._enviar_alertas_resultados_automaticos(resultados_totais, data_selecionada)
    
    #def processar_alertas_top_com_odds(self, data_selecionada):
    def processar_alertas_top_com_odds(self, data_selecionada):
        """Processa alertas TOP e adiciona informações de odds com correlação"""
        st.subheader(f"💰 Processando Odds para Alertas TOP - {data_selecionada.strftime('%d/%m/%Y')}")
        
        # Carregar alertas TOP
        alertas_top = DataStorage.carregar_alertas_top()
        if not alertas_top:
            st.warning("⚠️ Nenhum alerta TOP para processar odds")
            return
        
        st.info(f"🔍 Encontrados {len(alertas_top)} alertas TOP")
        
        # Filtrar alertas da data selecionada
        hoje = data_selecionada.strftime("%Y-%m-%d")
        alertas_data = [a for a in alertas_top if a.get('data_busca') == hoje]
        
        if not alertas_data:
            st.warning(f"⚠️ Nenhum alerta TOP para a data {hoje}")
            return
        
        st.info(f"📅 Processando {len(alertas_data)} alertas para {hoje}")
        
        # Método 1: Correlação simples (mais rápida)
        metodo = st.radio("Escolha o método de correlação:", 
                         ["Rápido (Correlação por similaridade)", 
                          "Avançado (Busca por liga específica)"], 
                         index=0)
        
        if metodo == "Rápido (Correlação por similaridade)":
            alertas_com_odds = self.alerts_odds_manager.processar_alertas_top_com_odds(
                alertas_data, 
                data_selecionada
            )
        else:
            alertas_com_odds = self.alerts_odds_manager.processar_alertas_top_com_odds_avancado(
                alertas_data, 
                data_selecionada
            )
        
        # Verificar e corrigir correlações problemáticas
        alertas_com_odds = self.alerts_odds_manager.verificar_e_corrigir_correlacoes(alertas_com_odds)
        
        # Calcular estatísticas
        alertas_com_odds_sucesso = [a for a in alertas_com_odds if a.get('odds_disponiveis', False)]
        alertas_sem_odds = [a for a in alertas_com_odds if not a.get('odds_disponiveis', False)]
        
        # Mostrar estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Alertas", len(alertas_data))
        with col2:
            st.metric("Com Odds", len(alertas_com_odds_sucesso))
        with col3:
            taxa = (len(alertas_com_odds_sucesso)/len(alertas_data)*100) if alertas_data else 0
            st.metric("Taxa Sucesso", f"{taxa:.1f}%")
        
        # Mostrar alertas sem odds
        if alertas_sem_odds:
            with st.expander(f"⚠️ {len(alertas_sem_odds)} Alertas sem Odds"):
                for alerta in alertas_sem_odds:
                    st.write(f"❌ {alerta.get('home')} vs {alerta.get('away')}")
        
        # Calcular múltiplas
        resultado_multiplas = self.alerts_odds_manager.calcular_multiplas_alertas(alertas_com_odds)
        
        if resultado_multiplas and resultado_multiplas['status'] == "SUCESSO":
            st.success(f"✅ {resultado_multiplas['total_jogos']} jogos com odds processados!")
            
            # Mostrar resultado
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Jogos", resultado_multiplas['total_jogos'])
            with col2:
                st.metric("Multipla Acumulada", f"{resultado_multiplas['multipla_acumulada']:.2f}")
            with col3:
                st.metric("Retorno Potencial", f"R$ {resultado_multiplas['retorno_potencial']:.2f}")
            
            # Mostrar detalhes
            self.alerts_odds_manager.gerar_relatorio_multiplas_detalhado(alertas_com_odds, data_selecionada)
            
        else:
            st.warning("⚠️ Não foi possível calcular múltiplas para os alertas TOP")
            if resultado_multiplas:
                st.info(f"Motivo: {resultado_multiplas.get('status', 'Desconhecido')}")
                st.info(f"Odds válidas encontradas: {resultado_multiplas.get('total_jogos', 0)}")   
    
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
                elif tipo_alerta == "ambas_marcam":
                    resultado = jogo.resultado_ambas_marcam
                    cor = "🟢" if resultado == "GREEN" else "🔴"
                    st.write(f"{cor} {alerta.get('home', '')} {home_goals}-{away_goals} {alerta.get('away', '')}")
                    st.write(f"   🤝 {alerta.get('tendencia_ambas_marcam', '')} | Conf: {alerta.get('confianca_ambas_marcam', 0):.0f}%")
                    st.write(f"   🎯 Resultado Ambas Marcam: {resultado}")
            
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
        elif tipo_alerta == "ambas_marcam":
            DataStorage.salvar_alertas_ambas_marcam(alertas)
            DataStorage.salvar_resultados_ambas_marcam(resultados)
        
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
                    elif tipo_alerta == "ambas_marcam":
                        titulo = f" RESULTADOS AMBAS MARCAM - Lote {i//batch_size + 1}"
                    
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
        """Verifica e envia alerta individual - CORRIGIDO"""
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
        elif tipo_alerta == "ambas_marcam":
            alertas = DataStorage.carregar_alertas_ambas_marcam()
            path = ConfigManager.ALERTAS_AMBAS_MARCAM_PATH
        else:
            alertas = {}
            path = ""
        
        fixture_id = str(jogo.id)
        
        # Verificar se já existe alerta para este jogo
        if fixture_id not in alertas:
            # CRIAR alerta_data COM TODOS OS DADOS NECESSÁRIOS
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
            
            # Adicionar dados específicos do tipo
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
            
            # Salvar no arquivo apropriado
            if tipo_alerta == "over_under":
                DataStorage.salvar_alertas(alertas)
            elif tipo_alerta == "favorito":
                DataStorage.salvar_alertas_favoritos(alertas)
            elif tipo_alerta == "gols_ht":
                DataStorage.salvar_alertas_gols_ht(alertas)
            elif tipo_alerta == "ambas_marcam":
                DataStorage.salvar_alertas_ambas_marcam(alertas)
    
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
        elif tipo_alerta == "ambas_marcam" and 'ambas_marcam' in analise['detalhes']:
            am = analise['detalhes']['ambas_marcam']
            tipo_emoji_am = "🤝" if am['tendencia_ambas_marcam'] == "SIM" else "🚫"
            
            caption = (
                f"<b>{tipo_emoji_am} ALERTA AMBAS MARCAM</b>\n\n"
                f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n"
                f"<b>🤝 Tendência: {am['tendencia_ambas_marcam']}</b>\n"
                f"<b>📊 Probabilidade SIM: {am['sim']:.1f}%</b>\n"
                f"<b>📊 Probabilidade NÃO: {am['nao']:.1f}%</b>\n"
                f"<b>🔍 Confiança: {am['confianca_ambas_marcam']:.1f}%</b>\n\n"
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
            elif tipo_alerta == "ambas_marcam":
                tipo_text = "ALERTA AMBAS MARCAM"
                cor_titulo = (155, 89, 182)
            
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
            elif tipo_alerta == "ambas_marcam" and 'ambas_marcam' in analise['detalhes']:
                am = analise['detalhes']['ambas_marcam']
                draw.text((50, 150), f"Tendência: {am['tendencia_ambas_marcam']}", font=fonte, fill=(100, 200, 255))
                draw.text((50, 200), f"Confiança: {am['confianca_ambas_marcam']:.1f}%", font=fonte, fill=(100, 255, 100))
            
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
        """Filtra jogos baseado no tipo de análise selecionado - CORRIGIDO"""
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
        """Envia os top jogos para o Telegram - CORRIGIDO"""
        if not alerta_top_jogos:
            st.info("ℹ️ Alerta de Top Jogos desativado")
            return
        
        jogos_elegiveis = [j for j in jogos_filtrados if j.get("status") not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
        
        # Aplicar filtro de confiança específico para o tipo de alerta
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
        
        # Ordenar por métrica apropriada
        if tipo_alerta == "over_under":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x.get("confianca", 0), reverse=True)[:top_n]
        elif tipo_alerta == "favorito":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x.get("confianca_vitoria", 0), reverse=True)[:top_n]
        elif tipo_alerta == "gols_ht":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x.get("confianca_ht", 0), reverse=True)[:top_n]
        elif tipo_alerta == "ambas_marcam":
            top_jogos_sorted = sorted(jogos_elegiveis, key=lambda x: x.get("confianca_ambas_marcam", 0), reverse=True)[:top_n]
        
        # Salvar alertas TOP
        for jogo in top_jogos_sorted:
            self._salvar_alerta_top(jogo, data_busca, tipo_alerta)
        
        if formato_top_jogos in ["Texto", "Ambos"]:
            self._enviar_top_jogos_texto(top_jogos_sorted, data_busca, tipo_alerta)
        
        if formato_top_jogos in ["Poster", "Ambos"]:
            self._enviar_top_jogos_poster(top_jogos_sorted, data_busca, tipo_alerta)
    
    def _salvar_alerta_top(self, jogo_data, data_busca, tipo_alerta):
        """Salva um alerta na lista de alertas TOP"""
        alertas_top = DataStorage.carregar_alertas_top()
        
        # Criar objeto de alerta top
        alerta_top = {
            "id": jogo_data["id"],
            "home": jogo_data["home"],
            "away": jogo_data["away"],
            "liga": jogo_data["liga"],
            "hora": jogo_data.get("hora", datetime.now().isoformat()),
            "status": jogo_data.get("status", "SCHEDULED"),
            "escudo_home": jogo_data.get("escudo_home", ""),
            "escudo_away": jogo_data.get("escudo_away", ""),
            "tipo_alerta": tipo_alerta,
            "data_busca": data_busca,
            "conferido": False,
            "data_criacao": datetime.now().isoformat()
        }
        
        # Adicionar dados específicos do tipo
        if tipo_alerta == "over_under":
            alerta_top.update({
                "tendencia": jogo_data.get("tendencia", ""),
                "estimativa": jogo_data.get("estimativa", 0.0),
                "probabilidade": jogo_data.get("probabilidade", 0.0),
                "confianca": jogo_data.get("confianca", 0.0),
                "tipo_aposta": jogo_data.get("tipo_aposta", ""),
                "detalhes": jogo_data.get("detalhes", {})
            })
        elif tipo_alerta == "favorito":
            alerta_top.update({
                "favorito": jogo_data.get("favorito", ""),
                "confianca_vitoria": jogo_data.get("confianca_vitoria", 0.0),
                "prob_home_win": jogo_data.get("prob_home_win", 0.0),
                "prob_away_win": jogo_data.get("prob_away_win", 0.0),
                "prob_draw": jogo_data.get("prob_draw", 0.0),
                "detalhes": jogo_data.get("detalhes", {})
            })
        elif tipo_alerta == "gols_ht":
            alerta_top.update({
                "tendencia_ht": jogo_data.get("tendencia_ht", ""),
                "confianca_ht": jogo_data.get("confianca_ht", 0.0),
                "estimativa_total_ht": jogo_data.get("estimativa_total_ht", 0.0),
                "detalhes": jogo_data.get("detalhes", {})
            })
        elif tipo_alerta == "ambas_marcam":
            alerta_top.update({
                "tendencia_ambas_marcam": jogo_data.get("tendencia_ambas_marcam", ""),
                "confianca_ambas_marcam": jogo_data.get("confianca_ambas_marcam", 0.0),
                "prob_ambas_marcam_sim": jogo_data.get("prob_ambas_marcam_sim", 0.0),
                "prob_ambas_marcam_nao": jogo_data.get("prob_ambas_marcam_nao", 0.0),
                "detalhes": jogo_data.get("detalhes", {})
            })
        
        # Verificar se já existe
        existe = False
        for idx, alerta in enumerate(alertas_top):
            if alerta.get("id") == jogo_data["id"] and alerta.get("tipo_alerta") == tipo_alerta:
                alertas_top[idx] = alerta_top
                existe = True
                break
        
        if not existe:
            alertas_top.append(alerta_top)
        
        # Manter apenas os últimos 50 alertas
        if len(alertas_top) > 50:
            alertas_top = alertas_top[-50:]
        
        DataStorage.salvar_alertas_top(alertas_top)
    
    def _enviar_top_jogos_texto(self, top_jogos_sorted, data_busca, tipo_alerta):
        """Envia os top jogos em formato de texto"""
        data_str = datetime.strptime(data_busca, "%Y-%m-%d").strftime("%d/%m/%Y")
        
        if tipo_alerta == "over_under":
            titulo = f"🏆 TOP {len(top_jogos_sorted)} OVER/UNDER - {data_str}"
        elif tipo_alerta == "favorito":
            titulo = f"🏆 TOP {len(top_jogos_sorted)} FAVORITOS - {data_str}"
        elif tipo_alerta == "gols_ht":
            titulo = f"🏆 TOP {len(top_jogos_sorted)} GOLS HT - {data_str}"
        elif tipo_alerta == "ambas_marcam":
            titulo = f"🏆 TOP {len(top_jogos_sorted)} AMBAS MARCAM - {data_str}"
        
        msg = f"<b>{titulo}</b>\n\n"
        
        for idx, jogo in enumerate(top_jogos_sorted, 1):
            if tipo_alerta == "over_under":
                tipo_emoji = "📈" if jogo.get('tipo_aposta') == "over" else "📉"
                info = f"{jogo.get('tendencia', '')} | Conf: {jogo.get('confianca', 0):.0f}%"
            elif tipo_alerta == "favorito":
                tipo_emoji = "🏆"
                favorito = jogo.get('favorito', 'home')
                favorito_text = jogo.get('home', '') if favorito == "home" else jogo.get('away', '') if favorito == "away" else "EMPATE"
                info = f"Favorito: {favorito_text} | Conf: {jogo.get('confianca_vitoria', 0):.0f}%"
            elif tipo_alerta == "gols_ht":
                tipo_emoji = "⏰"
                info = f"{jogo.get('tendencia_ht', '')} | Conf: {jogo.get('confianca_ht', 0):.0f}%"
            elif tipo_alerta == "ambas_marcam":
                tipo_emoji = "🤝"
                info = f"{jogo.get('tendencia_ambas_marcam', '')} | Conf: {jogo.get('confianca_ambas_marcam', 0):.0f}%"
            
            msg += f"<b>{idx}. {tipo_emoji} {jogo.get('home', '')} vs {jogo.get('away', '')}</b>\n"
            msg += f"   📋 {info}\n"
            msg += f"   📅 {data_str}\n\n"
        
        msg += f"<b>🔥 ELITE MASTER SYSTEM - TOP {len(top_jogos_sorted)} JOGOS</b>"
        
        if self.telegram_client.enviar_mensagem(msg, self.config.TELEGRAM_CHAT_ID_ALT2):
            st.success(f"📤 Top {len(top_jogos_sorted)} jogos {tipo_alerta} enviados em texto!")
    
    def _enviar_top_jogos_poster(self, top_jogos_sorted, data_busca, tipo_alerta):
        """Envia os top jogos em formato de poster"""
        try:
            if tipo_alerta == "over_under":
                titulo = f" TOP OVER/UNDER - {datetime.strptime(data_busca, '%Y-%m-%d').strftime('%d/%m/%Y')}"
            elif tipo_alerta == "favorito":
                titulo = f" TOP FAVORITOS - {datetime.strptime(data_busca, '%Y-%m-%d').strftime('%d/%m/%Y')}"
            elif tipo_alerta == "gols_ht":
                titulo = f" TOP GOLS HT - {datetime.strptime(data_busca, '%Y-%m-%d').strftime('%d/%m/%Y')}"
            elif tipo_alerta == "ambas_marcam":
                titulo = f" TOP AMBAS MARCAM - {datetime.strptime(data_busca, '%Y-%m-%d').strftime('%d/%m/%Y')}"
            
            poster = self.poster_generator.gerar_poster_westham_style(top_jogos_sorted, titulo, tipo_alerta)
            
            caption = f"<b>{titulo}</b>\n\n"
            caption += f"<b>🏆 TOP {len(top_jogos_sorted)} JOGOS SELECIONADOS</b>\n\n"
            caption += f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE DE PONTA</b>"
            
            if self.telegram_client.enviar_foto(poster, caption=caption):
                st.success(f"📤 Top {len(top_jogos_sorted)} jogos {tipo_alerta} enviados em poster!")
                
        except Exception as e:
            logging.error(f"Erro ao enviar poster top jogos: {e}")
            st.error(f"❌ Erro ao enviar poster: {e}")
    
    def _enviar_alerta_westham_style(self, jogos_filtrados, tipo_analise, config_analise):
        """Envia alerta no estilo West Ham"""
        try:
            data_str = datetime.now().strftime("%d/%m/%Y")
            
            if tipo_analise == "Over/Under de Gols":
                titulo = f" ALERTA OVER/UNDER - {data_str}"
            elif tipo_analise == "Favorito (Vitória)":
                titulo = f" ALERTA FAVORITOS - {data_str}"
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                titulo = f" ALERTA GOLS HT - {data_str}"
            elif tipo_analise == "Ambas Marcam (BTTS)":
                titulo = f" ALERTA AMBAS MARCAM - {data_str}"
            
            poster = self.poster_generator.gerar_poster_westham_style(jogos_filtrados, titulo, tipo_analise)
            
            caption = f"<b>{titulo}</b>\n\n"
            caption += f"<b>🔔 {len(jogos_filtrados)} ALERTAS ATIVOS</b>\n\n"
            caption += f"<b>🔥 ELITE MASTER SYSTEM - DETECÇÃO AUTOMÁTICA</b>"
            
            if self.telegram_client.enviar_foto(poster, caption=caption):
                st.success(f"📤 Alerta {tipo_analise} enviado em estilo West Ham!")
                
        except Exception as e:
            logging.error(f"Erro ao enviar alerta West Ham: {e}")
            st.error(f"❌ Erro ao enviar alerta: {e}")
    
    def _enviar_alerta_poster_original(self, jogos_filtrados, tipo_analise, config_analise):
        """Envia alerta no estilo original (fallback)"""
        try:
            data_str = datetime.now().strftime("%d/%m/%Y")
            
            if tipo_analise == "Over/Under de Gols":
                titulo = f"ALERTA OVER/UNDER - {data_str}"
                tipo_alerta = "over_under"
            elif tipo_analise == "Favorito (Vitória)":
                titulo = f"ALERTA FAVORITOS - {data_str}"
                tipo_alerta = "favorito"
            elif tipo_analise == "Gols HT (Primeiro Tempo)":
                titulo = f"ALERTA GOLS HT - {data_str}"
                tipo_alerta = "gols_ht"
            elif tipo_analise == "Ambas Marcam (BTTS)":
                titulo = f"ALERTA AMBAS MARCAM - {data_str}"
                tipo_alerta = "ambas_marcam"
            
            # Usar o poster de resultados como fallback
            poster = self.poster_generator.gerar_poster_resultados(jogos_filtrados, tipo_alerta)
            
            caption = f"<b>{titulo}</b>\n\n"
            caption += f"<b>📊 {len(jogos_filtrados)} JOGOS SELECIONADOS</b>\n\n"
            caption += f"<b>🔥 ELITE MASTER SYSTEM</b>"
            
            if self.telegram_client.enviar_foto(poster, caption=caption):
                st.success(f"📤 Alerta {tipo_analise} enviado em estilo original!")
                
        except Exception as e:
            logging.error(f"Erro ao enviar alerta original: {e}")
            st.error(f"❌ Erro ao enviar alerta: {e}")
    
    def _limpar_alertas_top_antigos(self):
        """Limpa alertas TOP com mais de 7 dias"""
        alertas_top = DataStorage.carregar_alertas_top()
        
        if not alertas_top:
            st.info("ℹ️ Nenhum alerta TOP para limpar")
            return
        
        hoje = datetime.now()
        alertas_novos = []
        alertas_removidos = 0
        
        for alerta in alertas_top:
            try:
                # Verificar data de criação
                data_criacao_str = alerta.get("data_criacao", "")
                if data_criacao_str:
                    data_criacao = datetime.fromisoformat(data_criacao_str)
                    diferenca = hoje - data_criacao
                    
                    if diferenca.days <= 7:  # Manter apenas últimos 7 dias
                        alertas_novos.append(alerta)
                    else:
                        alertas_removidos += 1
                else:
                    # Se não tem data, manter por segurança
                    alertas_novos.append(alerta)
            except:
                # Em caso de erro, manter o alerta
                alertas_novos.append(alerta)
        
        DataStorage.salvar_alertas_top(alertas_novos)
        
        if alertas_removidos > 0:
            st.success(f"🗑️ {alertas_removidos} alertas TOP antigos removidos")
            st.info(f"📊 Restaram {len(alertas_novos)} alertas TOP")
        else:
            st.info("ℹ️ Nenhum alerta TOP antigo para remover")


# =============================
# INTERFACE STREAMLIT
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
        if alerta_conferencia_auto:
            st.info("🤖 Alerta automático: ATIVADO")
        if alerta_resultados:
            st.info("🏁 Alertas de resultados: ATIVADO")
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Buscar Partidas", "📊 Conferir Resultados", "🏆 Resultados TOP Alertas", "💰 Odds TOP Alertas"])
    
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
        
        col_ou, col_fav, col_ht, col_am = st.columns(4)  # Alterado para 4 colunas
        
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
        
        with col_am:
            alertas_am = DataStorage.carregar_alertas_ambas_marcam()
            resultados_am = DataStorage.carregar_resultados_ambas_marcam()
            
            total_alertas_am = len(alertas_am)
            conferidos_am = sum(1 for a in alertas_am.values() if a.get("conferido", False))
            greens_am = sum(1 for r in resultados_am.values() if r.get("resultado_ambas_marcam") == "GREEN")
            reds_am = sum(1 for r in resultados_am.values() if r.get("resultado_ambas_marcam") == "RED")
            
            st.metric("🤝 Ambas Marcam", f"{total_alertas_am} alertas", f"{conferidos_am} conferidos")
            if greens_am + reds_am > 0:
                taxa_am = (greens_am / (greens_am + reds_am)) * 100
                st.write(f"✅ {greens_am} | ❌ {reds_am} | 📊 {taxa_am:.1f}%")
    
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
        
        # Mostrar estatísticas dos alertas TOP
        st.markdown("---")
        st.subheader("📊 Estatísticas dos Alertas TOP")
        
        alertas_top = DataStorage.carregar_alertas_top()
        
        if alertas_top:
            # Agrupar por tipo
            top_ou = [a for a in alertas_top if a.get("tipo_alerta") == "over_under"]
            top_fav = [a for a in alertas_top if a.get("tipo_alerta") == "favorito"]
            top_ht = [a for a in alertas_top if a.get("tipo_alerta") == "gols_ht"]
            top_am = [a for a in alertas_top if a.get("tipo_alerta") == "ambas_marcam"]
            
            col_top1, col_top2, col_top3, col_top4 = st.columns(4)
            
            with col_top1:
                st.metric("⚽ TOP Over/Under", len(top_ou))
                if top_ou:
                    greens = sum(1 for a in top_ou if a.get("resultado") == "GREEN")
                    reds = sum(1 for a in top_ou if a.get("resultado") == "RED")
                    conferidos = sum(1 for a in top_ou if a.get("conferido", False))
                    st.write(f"✅ {greens} | ❌ {reds} | 🔍 {conferidos}/{len(top_ou)}")
            
            with col_top2:
                st.metric("🏆 TOP Favoritos", len(top_fav))
                if top_fav:
                    greens = sum(1 for a in top_fav if a.get("resultado_favorito") == "GREEN")
                    reds = sum(1 for a in top_fav if a.get("resultado_favorito") == "RED")
                    conferidos = sum(1 for a in top_fav if a.get("conferido", False))
                    st.write(f"✅ {greens} | ❌ {reds} | 🔍 {conferidos}/{len(top_fav)}")
            
            with col_top3:
                st.metric("⏰ TOP Gols HT", len(top_ht))
                if top_ht:
                    greens = sum(1 for a in top_ht if a.get("resultado_ht") == "GREEN")
                    reds = sum(1 for a in top_ht if a.get("resultado_ht") == "RED")
                    conferidos = sum(1 for a in top_ht if a.get("conferido", False))
                    st.write(f"✅ {greens} | ❌ {reds} | 🔍 {conferidos}/{len(top_ht)}")
            
            with col_top4:
                st.metric("🤝 TOP Ambas Marcam", len(top_am))
                if top_am:
                    greens = sum(1 for a in top_am if a.get("resultado_ambas_marcam") == "GREEN")
                    reds = sum(1 for a in top_am if a.get("resultado_ambas_marcam") == "RED")
                    conferidos = sum(1 for a in top_am if a.get("conferido", False))
                    st.write(f"✅ {greens} | ❌ {reds} | 🔍 {conferidos}/{len(top_am)}")
            
            # Botão para limpar alertas TOP antigos
            if st.button("🗑️ Limpar Alertas TOP Antigos", type="secondary"):
                sistema._limpar_alertas_top_antigos()
        else:
            st.info("ℹ️ Nenhum alerta TOP salvo ainda.")
    
    with tab4:
        st.subheader("💰 Processar Odds para Alertas TOP")
        
        col_data_odds, col_btn_odds = st.columns([2, 1])
        with col_data_odds:
            data_odds = st.date_input(
                "📅 Data para processar odds:", 
                value=datetime.today(), 
                key="data_odds"
            )
        
        with col_btn_odds:
            if st.button("💰 Processar Odds TOP", type="primary", key="btn_processar_odds"):
                sistema.processar_alertas_top_com_odds(data_odds)
    
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
