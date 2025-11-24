import streamlit as st
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import io
import pandas as pd
import time
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps

# =============================
# Configurações e Segurança
# =============================

# Versão de teste - usar apenas variáveis de ambiente
API_KEY = os.getenv("FOOTBALL_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "") 
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "")

# Validar credenciais
if not all([API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    st.error("❌ Credenciais não configuradas. Configure as variáveis de ambiente:")
    st.code("""
    FOOTBALL_API_KEY=sua_api_key_aqui
    TELEGRAM_TOKEN=seu_bot_token_aqui  
    TELEGRAM_CHAT_ID=seu_chat_id_aqui
    TELEGRAM_CHAT_ID_ALT2=seu_chat_id_alternativo_aqui
    """)
    st.stop()

HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Constantes
ALERTAS_PATH = "alertas.json"
ALERTAS_AMBAS_MARCAM_PATH = "alertas_ambas_marcam.json"
ALERTAS_CARTOES_PATH = "alertas_cartoes.json"
ALERTAS_ESCANTEIOS_PATH = "alertas_escanteios.json"
ALERTAS_COMPOSTOS_PATH = "alertas_compostos.json"
ALERTAS_COMPOSTOS_AVANCADOS_PATH = "alertas_compostos_avancados.json"  # NOVO: Alertas compostos avançados
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_ESTATISTICAS = "cache_estatisticas.json"
CACHE_DADOS_HISTORICOS = "cache_dados_historicos.json"  # NOVO: Cache para dados históricos
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# Histórico de conferências
HISTORICO_PATH = "historico_conferencias.json"
HISTORICO_AMBAS_MARCAM_PATH = "historico_ambas_marcam.json"
HISTORICO_CARTOES_PATH = "historico_cartoes.json"
HISTORICO_ESCANTEIOS_PATH = "historico_escanteios.json"
HISTORICO_COMPOSTOS_PATH = "historico_compostos.json"
HISTORICO_COMPOSTOS_AVANCADOS_PATH = "historico_compostos_avancados.json"  # NOVO

# =============================
# SISTEMA DE RATE LIMIT AUTOMÁTICO - ATUALIZADO
# =============================

RATE_LIMIT_CACHE = "rate_limit_cache.json"
RATE_LIMIT_CALLS_PER_MINUTE = 9  # Ajustado para 9 (API permite 10)
RATE_LIMIT_WAIT_TIME = 65  # Segundos para esperar (1 minuto + 5s margem)

class RateLimitManager:
    """Gerenciador de Rate Limit automático para a API"""
    
    def __init__(self):
        self.cache_file = RATE_LIMIT_CACHE
        self.calls_per_minute = RATE_LIMIT_CALLS_PER_MINUTE
        self.wait_time = RATE_LIMIT_WAIT_TIME
        self._ensure_cache()
    
    def _ensure_cache(self):
        """Garante que o cache de rate limit existe"""
        try:
            if not os.path.exists(self.cache_file):
                cache_data = {
                    "last_reset": datetime.now().timestamp(),
                    "call_count": 0,
                    "last_call_time": 0,
                    "pause_until": 0
                }
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_data, f)
        except Exception:
            pass
    
    def _load_cache(self):
        """Carrega o cache de rate limit"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except:
            return {
                "last_reset": datetime.now().timestamp(),
                "call_count": 0,
                "last_call_time": 0,
                "pause_until": 0
            }
    
    def _save_cache(self, cache_data):
        """Salva o cache de rate limit"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception:
            pass
    
    def check_rate_limit(self):
        """Verifica e aplica o rate limit automaticamente"""
        cache = self._load_cache()
        now = datetime.now().timestamp()
        
        # Verificar se estamos em pausa forçada
        if now < cache.get("pause_until", 0):
            wait_remaining = cache["pause_until"] - now
            st.warning(f"⏳ Rate limit: Aguardando {wait_remaining:.1f}s...")
            time.sleep(wait_remaining)
            # Recarregar cache após espera
            cache = self._load_cache()
            now = datetime.now().timestamp()
        
        # Verificar se precisa resetar o contador (a cada minuto)
        if now - cache["last_reset"] > 60:  # Mais de 1 minuto
            cache["last_reset"] = now
            cache["call_count"] = 0
        
        # Verificar se excedeu o limite
        if cache["call_count"] >= self.calls_per_minute:
            time_since_reset = now - cache["last_reset"]
            wait_time = max(60 - time_since_reset + 1, 1)  # Esperar pelo menos 1 segundo
            
            st.warning(f"🚫 Rate limit atingido! Aguardando {wait_time:.1f}s...")
            time.sleep(wait_time)
            
            # Resetar após espera
            cache["last_reset"] = datetime.now().timestamp()
            cache["call_count"] = 0
            now = cache["last_reset"]
        
        # Atualizar contador
        cache["call_count"] += 1
        cache["last_call_time"] = now
        
        self._save_cache(cache)
        
        # Pequena pausa entre chamadas para distribuir melhor
        time.sleep(0.5)
        
        return True

# Instância global do gerenciador de rate limit
rate_limit_manager = RateLimitManager()

def obter_dados_api_com_rate_limit(url: str, timeout: int = 15) -> dict | None:
    """
    Versão MELHORADA da função de API com rate limit automático e melhor tratamento de erro
    """
    try:
        rate_limit_manager.check_rate_limit()
        
        st.info(f"🌐 Fazendo requisição para: {url.split('/')[-1]}")  # Log simplificado
        
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            st.error("🚫 Rate Limit da API atingido! Aguardando 65s...")
            cache = rate_limit_manager._load_cache()
            cache["pause_until"] = datetime.now().timestamp() + 65
            rate_limit_manager._save_cache(cache)
            time.sleep(65)
            return obter_dados_api_com_rate_limit(url, timeout)
        elif response.status_code == 403:
            st.error("🔒 Acesso proibido. Verifique sua API Key.")
            return None
        elif response.status_code == 404:
            st.warning(f"📭 Recurso não encontrado: {url}")
            return None
        else:
            st.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        st.error(f"⏰ Timeout na requisição: {url}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"🌐 Erro de rede: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"📄 Erro ao decodificar JSON: {e}")
        return None

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
# Utilitários de Cache e Persistência - COM PERSISTÊNCIA ROBUSTA
# =============================
def garantir_diretorio():
    """Garante que o diretório de trabalho existe para os arquivos de persistência"""
    try:
        os.makedirs("data", exist_ok=True)
        return "data/"
    except:
        return ""

def carregar_json(caminho: str) -> dict:
    """Carrega JSON com persistência robusta e tratamento de erros"""
    try:
        caminho_completo = garantir_diretorio() + caminho
        
        if os.path.exists(caminho_completo):
            with open(caminho_completo, "r", encoding='utf-8') as f:
                dados = json.load(f)
            
            # Verificar expiração do cache apenas para caches temporários
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO, CACHE_ESTATISTICAS, CACHE_DADOS_HISTORICOS]:
                agora = datetime.now().timestamp()
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                        st.info(f"ℹ️ Cache expirado para {caminho}, recarregando...")
                        return {}
                else:
                    # Se não tem timestamp, verifica pela data de modificação do arquivo
                    if agora - os.path.getmtime(caminho_completo) > CACHE_TIMEOUT:
                        st.info(f"ℹ️ Cache antigo para {caminho}, recarregando...")
                        return {}
            
            return dados
        else:
            # Se o arquivo não existe, cria um dicionário vazio
            dados_vazios = {}
            salvar_json(caminho, dados_vazios)
            return dados_vazios
            
    except (json.JSONDecodeError, IOError) as e:
        st.warning(f"⚠️ Erro ao carregar {caminho}, criando novo: {e}")
        # Se há erro, retorna dicionário vazio e tenta salvar um novo
        dados_vazios = {}
        salvar_json(caminho, dados_vazios)
        return dados_vazios

def salvar_json(caminho: str, dados: dict):
    """Salva JSON com persistência robusta"""
    try:
        caminho_completo = garantir_diretorio() + caminho
        
        # Adicionar timestamp apenas para caches temporários
        if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO, CACHE_ESTATISTICAS, CACHE_DADOS_HISTORICOS]:
            if isinstance(dados, dict):
                dados['_timestamp'] = datetime.now().timestamp()
        
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(caminho_completo) if os.path.dirname(caminho_completo) else ".", exist_ok=True)
        
        with open(caminho_completo, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        
        return True
    except IOError as e:
        st.error(f"❌ Erro crítico ao salvar {caminho}: {e}")
        return False

# Funções para alertas das novas previsões - COM PERSISTÊNCIA
def carregar_alertas_ambas_marcam() -> dict:
    return carregar_json(ALERTAS_AMBAS_MARCAM_PATH)

def salvar_alertas_ambas_marcam(alertas: dict):
    return salvar_json(ALERTAS_AMBAS_MARCAM_PATH, alertas)

def carregar_alertas_cartoes() -> dict:
    return carregar_json(ALERTAS_CARTOES_PATH)

def salvar_alertas_cartoes(alertas: dict):
    return salvar_json(ALERTAS_CARTOES_PATH, alertas)

def carregar_alertas_escanteios() -> dict:
    return carregar_json(ALERTAS_ESCANTEIOS_PATH)

def salvar_alertas_escanteios(alertas: dict):
    return salvar_json(ALERTAS_ESCANTEIOS_PATH, alertas)

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    return salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    return salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao() -> dict:
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados: dict):
    return salvar_json(CACHE_CLASSIFICACAO, dados)

def carregar_cache_estatisticas() -> dict:
    return carregar_json(CACHE_ESTATISTICAS)

def salvar_cache_estatisticas(dados: dict):
    return salvar_json(CACHE_ESTATISTICAS, dados)

def carregar_cache_dados_historicos() -> dict:
    return carregar_json(CACHE_DADOS_HISTORICOS)

def salvar_cache_dados_historicos(dados: dict):
    return salvar_json(CACHE_DADOS_HISTORICOS, dados)

# =============================
# NOVAS FUNÇÕES PARA ALERTAS COMPOSTOS TEMPORÁRIOS
# =============================

def carregar_alertas_compostos() -> dict:
    """Carrega alertas compostos com verificação de expiração (24h)"""
    alertas = carregar_json(ALERTAS_COMPOSTOS_PATH)
    
    # Verificar e remover alertas expirados (mais de 24 horas)
    agora = datetime.now()
    alertas_validos = {}
    
    for alerta_id, alerta in alertas.items():
        data_criacao = datetime.fromisoformat(alerta.get("data_criacao", "2000-01-01T00:00:00"))
        if agora - data_criacao < timedelta(hours=24):
            alertas_validos[alerta_id] = alerta
        else:
            st.info(f"ℹ️ Alerta composto {alerta_id} expirado (24h) e removido")
    
    # Se houve remoção, salvar a versão atualizada
    if len(alertas_validos) != len(alertas):
        salvar_alertas_compostos(alertas_validos)
    
    return alertas_validos

def salvar_alertas_compostos(alertas: dict):
    """Salva alertas compostos com timestamp"""
    return salvar_json(ALERTAS_COMPOSTOS_PATH, alertas)

def salvar_alerta_composto_para_conferencia(jogos_conf: list, threshold: int, poster_enviado: bool = True):
    """Salva um alerta composto para futura conferência (24h) - VERSÃO ATUALIZADA COM ESCUDOS"""
    try:
        alertas = carregar_alertas_compostos()
        
        # Criar ID único baseado no timestamp
        alerta_id = f"composto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Preparar dados dos jogos para conferência - AGORA COM ESCUDOS
        jogos_para_salvar = []
        for jogo in jogos_conf:
            # Obter URLs dos escudos do fixture
            home_crest = ""
            away_crest = ""
            if 'fixture' in jogo:
                fixture = jogo['fixture']
                home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
            
            jogos_para_salvar.append({
                "fixture_id": jogo.get("id", ""),
                "home": jogo["home"],
                "away": jogo["away"],
                "liga": jogo["liga"],
                "tendencia": jogo["tendencia"],
                "estimativa": jogo["estimativa"],
                "confianca": jogo["confianca"],
                "data_jogo": jogo.get("hora").isoformat() if isinstance(jogo.get("hora"), datetime) else datetime.now().isoformat(),
                "conferido": False,
                "resultado": None,
                "placar_final": None,
                "previsao_correta": None,
                "home_crest": home_crest,  # NOVO: salvar escudo home
                "away_crest": away_crest   # NOVO: salvar escudo away
            })
        
        # Salvar alerta composto
        alertas[alerta_id] = {
            "data_criacao": datetime.now().isoformat(),
            "data_expiracao": (datetime.now() + timedelta(hours=24)).isoformat(),
            "total_jogos": len(jogos_para_salvar),
            "threshold": threshold,
            "poster_enviado": poster_enviado,
            "jogos": jogos_para_salvar,
            "conferido": False,
            "estatisticas": None
        }
        
        salvar_alertas_compostos(alertas)
        st.success(f"✅ Alerta composto salvo para conferência (24h). ID: {alerta_id}")
        return alerta_id
        
    except Exception as e:
        st.error(f"❌ Erro ao salvar alerta composto: {e}")
        return None

# =============================
# NOVAS FUNÇÕES PARA ALERTAS COMPOSTOS AVANÇADOS
# =============================

def carregar_alertas_compostos_avancados() -> dict:
    """Carrega alertas compostos avançados com verificação de expiração (24h)"""
    alertas = carregar_json(ALERTAS_COMPOSTOS_AVANCADOS_PATH)
    
    # Verificar e remover alertas expirados (mais de 24 horas)
    agora = datetime.now()
    alertas_validos = {}
    
    for alerta_id, alerta in alertas.items():
        data_criacao = datetime.fromisoformat(alerta.get("data_criacao", "2000-01-01T00:00:00"))
        if agora - data_criacao < timedelta(hours=24):
            alertas_validos[alerta_id] = alerta
        else:
            st.info(f"ℹ️ Alerta composto avançado {alerta_id} expirado (24h) e removido")
    
    # Se houve remoção, salvar a versão atualizada
    if len(alertas_validos) != len(alertas):
        salvar_alertas_compostos_avancados(alertas_validos)
    
    return alertas_validos

def salvar_alertas_compostos_avancados(alertas: dict):
    """Salva alertas compostos avançados com timestamp"""
    return salvar_json(ALERTAS_COMPOSTOS_AVANCADOS_PATH, alertas)

def salvar_alerta_composto_avancado_para_conferencia(jogos_conf: list, threshold_ambas_marcam: int, threshold_cartoes: int, threshold_escanteios: int, poster_enviado: bool = True):
    """Salva um alerta composto avançado para futura conferência (24h)"""
    try:
        alertas = carregar_alertas_compostos_avancados()
        
        # Criar ID único baseado no timestamp
        alerta_id = f"composto_avancado_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Preparar dados dos jogos para conferência
        jogos_para_salvar = []
        for jogo in jogos_conf:
            # Obter URLs dos escudos do fixture
            home_crest = ""
            away_crest = ""
            if 'fixture' in jogo:
                fixture = jogo['fixture']
                home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
            
            jogos_para_salvar.append({
                "fixture_id": jogo.get("id", ""),
                "home": jogo["home"],
                "away": jogo["away"],
                "liga": jogo["liga"],
                "tipo_previsao": jogo["tipo_previsao"],
                "tendencia": jogo["tendencia"],
                "estimativa": jogo["estimativa"],
                "confianca": jogo["confianca"],
                "data_jogo": jogo.get("hora").isoformat() if isinstance(jogo.get("hora"), datetime) else datetime.now().isoformat(),
                "conferido": False,
                "resultado": None,
                "valor_real": None,
                "previsao_correta": None,
                "home_crest": home_crest,
                "away_crest": away_crest
            })
        
        # Salvar alerta composto avançado
        alertas[alerta_id] = {
            "data_criacao": datetime.now().isoformat(),
            "data_expiracao": (datetime.now() + timedelta(hours=24)).isoformat(),
            "total_jogos": len(jogos_para_salvar),
            "threshold_ambas_marcam": threshold_ambas_marcam,
            "threshold_cartoes": threshold_cartoes,
            "threshold_escanteios": threshold_escanteios,
            "poster_enviado": poster_enviado,
            "jogos": jogos_para_salvar,
            "conferido": False,
            "estatisticas": None
        }
        
        salvar_alertas_compostos_avancados(alertas)
        st.success(f"✅ Alerta composto avançado salvo para conferência (24h). ID: {alerta_id}")
        return alerta_id
        
    except Exception as e:
        st.error(f"❌ Erro ao salvar alerta composto avançado: {e}")
        return None

# =============================
# SISTEMA DE COLETA DE DADOS HISTÓRICOS REAIS
# =============================

def coletar_dados_historicos_time(time_id: str, liga_id: str, limite_partidas: int = 10) -> dict:
    """
    Coleta dados históricos REAIS de um time para cartões e escanteios
    """
    try:
        # Buscar partidas recentes do time
        url = f"{BASE_URL_FD}/teams/{time_id}/matches?limit={limite_partidas}&status=FINISHED"
        data = obter_dados_api_com_rate_limit(url)
        
        if not data or "matches" not in data:
            return {"cartoes_media": 2.8, "escanteios_media": 5.2}
        
        partidas = data["matches"]
        total_cartoes = 0
        total_escanteios = 0
        partidas_com_dados = 0
        
        for partida in partidas:
            fixture_id = partida["id"]
            estatisticas = obter_estatisticas_partida(fixture_id)
            
            if estatisticas:
                cartoes_partida = estatisticas.get("cartoes_amarelos", 0) + estatisticas.get("cartoes_vermelhos", 0)
                escanteios_partida = estatisticas.get("escanteios", 0)
                
                total_cartoes += cartoes_partida
                total_escanteios += escanteios_partida
                partidas_com_dados += 1
        
        # Calcular médias se tivermos dados suficientes
        if partidas_com_dados >= 3:  # Mínimo de 3 partidas para ter dados confiáveis
            return {
                "cartoes_media": total_cartoes / partidas_com_dados,
                "escanteios_media": total_escanteios / partidas_com_dados,
                "partidas_analisadas": partidas_com_dados,
                "confiabilidade": min(90, partidas_com_dados * 10)  # 10% por partida, até 90%
            }
        else:
            # Fallback para médias da liga se dados insuficientes
            return obter_medias_liga(liga_id)
            
    except Exception as e:
        st.warning(f"⚠️ Erro ao coletar dados históricos do time {time_id}: {e}")
        return obter_medias_liga(liga_id)

def obter_medias_liga(liga_id: str) -> dict:
    """
    Retorna médias padrão da liga baseadas em estatísticas reais conhecidas
    """
    medias_ligas = {
        "BSA": {"cartoes_media": 4.2, "escanteios_media": 9.8, "confiabilidade": 70},   # Brasileirão: mais cartões e escanteios
        "PL": {"cartoes_media": 3.5, "escanteios_media": 10.2, "confiabilidade": 75},   # Premier League
        "SA": {"cartoes_media": 4.0, "escanteios_media": 9.5, "confiabilidade": 70},    # Serie A
        "BL1": {"cartoes_media": 3.2, "escanteios_media": 9.2, "confiabilidade": 75},   # Bundesliga
        "PD": {"cartoes_media": 3.8, "escanteios_media": 9.0, "confiabilidade": 70},    # La Liga
        "FL1": {"cartoes_media": 3.6, "escanteios_media": 8.8, "confiabilidade": 70},   # Ligue 1
        "PPL": {"cartoes_media": 4.1, "escanteios_media": 9.3, "confiabilidade": 65},   # Portugal
        "ELC": {"cartoes_media": 3.9, "escanteios_media": 10.1, "confiabilidade": 65},  # Championship
    }
    
    return medias_ligas.get(liga_id, {"cartoes_media": 3.8, "escanteios_media": 9.5, "confiabilidade": 60})

def coletar_dados_historicos_time_com_cache(time_id: str, liga_id: str, limite_partidas: int = 10) -> dict:
    """
    Versão com cache da coleta de dados históricos
    """
    cache = carregar_cache_dados_historicos()
    cache_key = f"{liga_id}_{time_id}"
    
    # Verificar se temos dados em cache (válidos por 24 horas)
    if cache_key in cache:
        dados_cache = cache[cache_key]
        timestamp_criacao = dados_cache.get("_timestamp", 0)
        if datetime.now().timestamp() - timestamp_criacao < 86400:  # 24 horas
            return dados_cache
    
    # Coletar dados novos
    dados_novos = coletar_dados_historicos_time(time_id, liga_id, limite_partidas)
    dados_novos["_timestamp"] = datetime.now().timestamp()
    
    # Salvar no cache
    cache[cache_key] = dados_novos
    salvar_cache_dados_historicos(cache)
    
    return dados_novos

# =============================
# FUNÇÕES DE PREVISÃO ATUALIZADAS COM DADOS REAIS
# =============================

def calcular_previsao_cartoes_real(home_team: dict, away_team: dict, liga_id: str) -> tuple[float, float, str]:
    """
    Previsão REAL de cartões usando dados históricos - VERSÃO CORRIGIDA
    """
    try:
        home_id = home_team.get("id")
        away_id = away_team.get("id")
        
        if not home_id or not away_id:
            st.warning(f"⚠️ IDs dos times não encontrados para {home_team.get('name')} vs {away_team.get('name')}")
            return 3.8, 50.0, "Mais 3.5 Cartões"
        
        # Coletar dados históricos REAIS
        stats_home = coletar_dados_historicos_time_com_cache(str(home_id), liga_id)
        stats_away = coletar_dados_historicos_time_com_cache(str(away_id), liga_id)
        
        # Usar médias reais coletadas
        media_cartoes_home = stats_home.get("cartoes_media", 3.8)
        media_cartoes_away = stats_away.get("cartoes_media", 3.8)
        
        # Calcular confiabilidade combinada
        confiabilidade_home = stats_home.get("confiabilidade", 50)
        confiabilidade_away = stats_away.get("confiabilidade", 50)
        confiabilidade_media = (confiabilidade_home + confiabilidade_away) / 2
        
        # Total estimado de cartões (média dos dois times)
        total_estimado = (media_cartoes_home + media_cartoes_away)
        
        # Ajustar por fatores contextuais
        fator_casa = 0.9  # Time da casa tende a levar menos cartões
        fator_visitante = 1.1  # Time visitante tende a levar mais cartões
        
        total_ajustado = (media_cartoes_home * fator_casa) + (media_cartoes_away * fator_visitante)
        
        # Calcular confiança baseada na confiabilidade dos dados
        confianca_base = min(85, 40 + (confiabilidade_media * 0.5))
        
        # Ajustar confiança pelo desvio padrão (se tivermos dados suficientes)
        if stats_home.get("partidas_analisadas", 0) >= 5 and stats_away.get("partidas_analisadas", 0) >= 5:
            confianca_base = min(90, confianca_base + 10)
        
        # Definir tendências com base no total ajustado
        if total_ajustado >= 5.5:
            tendencia = "Mais 5.5 Cartões"
            confianca = min(90, confianca_base + 5)
        elif total_ajustado >= 4.5:
            tendencia = "Mais 4.5 Cartões" 
            confianca = confianca_base
        elif total_ajustado >= 3.5:
            tendencia = "Mais 3.5 Cartões"
            confianca = max(45, confianca_base - 5)
        else:
            tendencia = "Menos 3.5 Cartões"
            confianca = max(40, confianca_base - 10)
        
        st.info(f"📊 Cartões - {home_team['name']}: {media_cartoes_home:.1f} | {away_team['name']}: {media_cartoes_away:.1f} | Total: {total_ajustado:.1f} | Conf: {confianca:.0f}%")
        
        return total_ajustado, confianca, tendencia
        
    except Exception as e:
        st.error(f"❌ Erro na previsão de cartões: {e}")
        return 3.8, 45.0, "Mais 3.5 Cartões"

def calcular_previsao_escanteios_real(home_team: dict, away_team: dict, liga_id: str) -> tuple[float, float, str]:
    """
    Previsão REAL de escanteios usando dados históricos - VERSÃO CORRIGIDA
    """
    try:
        home_id = home_team.get("id")
        away_id = away_team.get("id")
        
        if not home_id or not away_id:
            st.warning(f"⚠️ IDs dos times não encontrados para {home_team.get('name')} vs {away_team.get('name')}")
            return 9.5, 50.0, "Mais 8.5 Escanteios"
        
        # Coletar dados históricos REAIS
        stats_home = coletar_dados_historicos_time_com_cache(str(home_id), liga_id)
        stats_away = coletar_dados_historicos_time_com_cache(str(away_id), liga_id)
        
        # Usar médias reais coletadas
        media_escanteios_home = stats_home.get("escanteios_media", 9.5)
        media_escanteios_away = stats_away.get("escanteios_media", 9.5)
        
        # Calcular confiabilidade combinada
        confiabilidade_home = stats_home.get("confiabilidade", 50)
        confiabilidade_away = stats_away.get("confiabilidade", 50)
        confiabilidade_media = (confiabilidade_home + confiabilidade_away) / 2
        
        # Total estimado de escanteios
        total_estimado = (media_escanteios_home + media_escanteios_away)
        
        # Ajustar por fatores contextuais
        fator_casa = 1.1  # Time da casa tende a ter mais escanteios
        fator_visitante = 0.9  # Time visitante tende a ter menos
        
        total_ajustado = (media_escanteios_home * fator_casa) + (media_escanteios_away * fator_visitante)
        
        # Calcular confiança baseada na confiabilidade dos dados
        confianca_base = min(80, 35 + (confiabilidade_media * 0.5))
        
        # Ajustar confiança pelo desvio padrão (se tivermos dados suficientes)
        if stats_home.get("partidas_analisadas", 0) >= 5 and stats_away.get("partidas_analisadas", 0) >= 5:
            confianca_base = min(85, confianca_base + 10)
        
        # Definir tendências com base no total ajustado
        if total_ajustado >= 11.5:
            tendencia = "Mais 11.5 Escanteios"
            confianca = min(85, confianca_base + 5)
        elif total_ajustado >= 10.5:
            tendencia = "Mais 10.5 Escanteios"
            confianca = confianca_base
        elif total_ajustado >= 9.5:
            tendencia = "Mais 9.5 Escanteios"
            confianca = max(40, confianca_base - 5)
        elif total_ajustado >= 8.5:
            tendencia = "Mais 8.5 Escanteios"
            confianca = max(35, confianca_base - 10)
        else:
            tendencia = "Menos 8.5 Escanteios"
            confianca = max(30, confianca_base - 15)
        
        st.info(f"📊 Escanteios - {home_team['name']}: {media_escanteios_home:.1f} | {away_team['name']}: {media_escanteios_away:.1f} | Total: {total_ajustado:.1f} | Conf: {confianca:.0f}%")
        
        return total_ajustado, confianca, tendencia
        
    except Exception as e:
        st.error(f"❌ Erro na previsão de escanteios: {e}")
        return 9.5, 45.0, "Mais 8.5 Escanteios"

# =============================
# SISTEMA DE ALERTAS PARA NOVAS PREVISÕES
# =============================

def verificar_enviar_alerta_ambas_marcam(fixture: dict, probabilidade: float, confianca: float, tendencia: str, alerta_individual: bool):
    """Sistema de alertas para previsão Ambas Marcam"""
    alertas = carregar_alertas_ambas_marcam()
    fixture_id = str(fixture["id"])
    
    if fixture_id not in alertas and confianca >= 60:  # Limiar para ambas marcam
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "probabilidade": probabilidade,
            "confianca": confianca,
            "conferido": False
        }
        
        if alerta_individual:
            enviar_alerta_telegram_ambas_marcam(fixture, tendencia, probabilidade, confianca)
        
        salvar_alertas_ambas_marcam(alertas)

def verificar_enviar_alerta_cartoes(fixture: dict, estimativa: float, confianca: float, tendencia: str, alerta_individual: bool):
    """Sistema de alertas para previsão de Cartões"""
    alertas = carregar_alertas_cartoes()
    fixture_id = str(fixture["id"])
    
    if fixture_id not in alertas and confianca >= 55:  # Limiar para cartões
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        
        if alerta_individual:
            enviar_alerta_telegram_cartoes(fixture, tendencia, estimativa, confianca)
        
        salvar_alertas_cartoes(alertas)

def verificar_enviar_alerta_escanteios(fixture: dict, estimativa: float, confianca: float, tendencia: str, alerta_individual: bool):
    """Sistema de alertas para previsão de Escanteios"""
    alertas = carregar_alertas_escanteios()
    fixture_id = str(fixture["id"])
    
    if fixture_id not in alertas and confianca >= 50:  # Limiar para escanteios
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        
        if alerta_individual:
            enviar_alerta_telegram_escanteios(fixture, tendencia, estimativa, confianca)
        
        salvar_alertas_escanteios(alertas)

# =============================
# ALERTAS TELEGRAM PARA NOVAS PREVISÕES
# =============================

def enviar_alerta_telegram_ambas_marcam(fixture: dict, tendencia: str, probabilidade: float, confianca: float) -> bool:
    """Envia alerta individual para Ambas Marcam - CORRIGIDA"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    
    # CORREÇÃO: Garantir que a data seja formatada corretamente
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    
    emoji = "✅" if "SIM" in tendencia else "⚠️" if "PROVÁVEL" in tendencia else "❌"
    
    msg = (
        f"<b>🎯 ALERTA AMBAS MARCAM</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>{emoji} Previsão: {tendencia}</b>\n"
        f"<b>📊 Probabilidade: {probabilidade:.1f}%</b>\n"
        f"<b>🎯 Confiança: {confianca:.0f}%</b>\n\n"
        f"<b>⚽ ELITE MASTER - ANÁLISE AMBAS MARCAM</b>"
    )
    
    return enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

def enviar_alerta_telegram_cartoes(fixture: dict, tendencia: str, estimativa: float, confianca: float) -> bool:
    """Envia alerta individual para Cartões - CORRIGIDA"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    
    # CORREÇÃO: Garantir formatação correta da data
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    
    msg = (
        f"<b>🟨 ALERTA TOTAL DE CARTÕES</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>📈 Tendência: {tendencia}</b>\n"
        f"<b>🟨 Estimativa: {estimativa:.1f} cartões</b>\n"
        f"<b>🎯 Confiança: {confianca:.0f}%</b>\n\n"
        f"<b>⚽ ELITE MASTER - ANÁLISE DE CARTÕES</b>"
    )
    
    return enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

def enviar_alerta_telegram_escanteios(fixture: dict, tendencia: str, estimativa: float, confianca: float) -> bool:
    """Envia alerta individual para Escanteios - CORRIGIDA"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    
    # CORREÇÃO: Garantir formatação correta da data
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    
    msg = (
        f"<b>🔄 ALERTA TOTAL DE ESCANTEIOS</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>📈 Tendência: {tendencia}</b>\n"
        f"<b>🔄 Estimativa: {estimativa:.1f} escanteios</b>\n"
        f"<b>🎯 Confiança: {confianca:.0f}%</b>\n\n"
        f"<b>⚽ ELITE MASTER - ANÁLISE DE ESCANTEIOS</b>"
    )
    
    return enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

# =============================
# NOVO: SISTEMA DE ALERTAS COMPOSTOS AVANÇADOS
# =============================

def gerar_poster_composto_avancado(jogos_compostos: list, titulo: str = "ELITE MASTER - PREVISÕES AVANÇADAS") -> io.BytesIO:
    """
    Gera poster profissional com previsões avançadas (Ambas Marcam, Cartões, Escanteios)
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 1100  # Mais espaço para múltiplas previsões
    PADDING = 100
    
    jogos_count = len(jogos_compostos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(60)
    FONTE_TIMES = criar_fonte(55)
    FONTE_VS = criar_fonte(50)
    FONTE_INFO = criar_fonte(40)
    FONTE_PREVISAO = criar_fonte(45)
    FONTE_CONFIANCA = criar_fonte(50)
    FONTE_TIPO = criar_fonte(48)

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Data atual
    data_atual = datetime.now().strftime("%d/%m/%Y")
    data_text = f"DATA DE ANÁLISE: {data_atual}"
    try:
        data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_SUBTITULO)
        data_w = data_bbox[2] - data_bbox[0]
        draw.text(((LARGURA - data_w) // 2, 180), data_text, font=FONTE_SUBTITULO, fill=(150, 200, 255))
    except:
        pass

    # Linha decorativa
    draw.line([(LARGURA//4, 250), (3*LARGURA//4, 250)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos_compostos):
        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=(100, 130, 160), width=4)

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 30), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            pass

        # Data e hora
        hora_display = jogo.get('hora_formatada', 'Hora inválida')
        data_display = jogo.get('data_formatada', 'Data inválida')
        data_hora_text = f"{data_display} • {hora_display} BRT"
        try:
            data_bbox = draw.textbbox((0, 0), data_hora_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 100), data_hora_text, font=FONTE_INFO, fill=(120, 180, 240))
        except:
            pass

        # ESCUDOS DOS TIMES
        TAMANHO_ESCUDO = 140
        TAMANHO_QUADRADO = 160
        ESPACO_ENTRE_ESCUDOS = 600

        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2
        y_escudos = y0 + 160

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS

        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get('home_crest', ''))
        escudo_away = baixar_imagem_url(jogo.get('away_crest', ''))

        # Desenhar escudos
        def desenhar_escudo_compacto(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(255, 255, 255), outline=(200, 200, 200), width=2)
            if logo_img:
                try:
                    logo_img = logo_img.convert("RGBA")
                    ratio = min(tamanho_escudo/logo_img.width, tamanho_escudo/logo_img.height)
                    nova_largura = int(logo_img.width * ratio)
                    nova_altura = int(logo_img.height * ratio)
                    logo_img = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                    pos_x = x + (tamanho_quadrado - nova_largura) // 2
                    pos_y = y + (tamanho_quadrado - nova_altura) // 2
                    img.paste(logo_img, (pos_x, pos_y), logo_img)
                except:
                    draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                    draw.text((x + 40, y + 50), "ERR", font=FONTE_INFO, fill=(255, 255, 255))
            else:
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 40, y + 50), "?", font=FONTE_INFO, fill=(255, 255, 255))

        desenhar_escudo_compacto(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_compacto(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        home_text = jogo['home'][:18]
        away_text = jogo['away'][:18]
        
        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 15),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 15),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        # VS centralizado
        try:
            vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
            vs_w = vs_bbox[2] - vs_bbox[0]
            vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 20), "VS", font=FONTE_VS, fill=(255, 215, 0))
        except:
            pass

        # SEÇÃO DE PREVISÕES
        y_previsoes = y_escudos + TAMANHO_QUADRADO + 80
        
        # Dividir em 3 colunas para as previsões
        largura_coluna = (LARGURA - 2 * PADDING) // 3
        x_col1 = PADDING + 20
        x_col2 = x_col1 + largura_coluna
        x_col3 = x_col2 + largura_coluna

        # Preparar previsões para este jogo
        previsoes_jogo = jogo['previsoes']
        
        tipos_previsao = ["Ambas Marcam", "Cartões", "Escanteios"]
        cores = [(255, 215, 0), (255, 152, 0), (100, 200, 255)]
        icones = ["🔄", "🟨", "🔄"]
        
        for i, (tipo, cor, icone) in enumerate(zip(tipos_previsao, cores, icones)):
            x_pos = [x_col1, x_col2, x_col3][i]
            
            # Cabeçalho do tipo de previsão
            tipo_text = f"{icone} {tipo}"
            try:
                tipo_bbox = draw.textbbox((0, 0), tipo_text, font=FONTE_TIPO)
                tipo_w = tipo_bbox[2] - tipo_bbox[0]
                draw.text((x_pos + (largura_coluna - tipo_w)//2, y_previsoes), tipo_text, font=FONTE_TIPO, fill=cor)
            except:
                pass
            
            # Informações da previsão
            if i < len(previsoes_jogo):
                previsao = previsoes_jogo[i]
                textos = [
                    f"{previsao['tendencia']}",
                    f"Est: {previsao['estimativa']:.1f}",
                    f"Conf: {previsao['confianca']:.0f}%"
                ]
                
                for j, texto in enumerate(textos):
                    try:
                        texto_bbox = draw.textbbox((0, 0), texto, font=FONTE_PREVISAO)
                        texto_w = texto_bbox[2] - texto_bbox[0]
                        draw.text((x_pos + (largura_coluna - texto_w)//2, y_previsoes + 60 + j * 45), 
                                 texto, font=FONTE_PREVISAO, fill=(255, 255, 255))
                    except:
                        pass

        # Linha separadora entre jogos (exceto último)
        if idx < len(jogos_compostos) - 1:
            draw.line([(x0 + 50, y1), (x1 - 50, y1)], fill=(100, 130, 160), width=2)

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • Previsões Avançadas • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        pass

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster composto avançado gerado com {len(jogos_compostos)} jogos")
    return buffer

def enviar_alerta_composto_avancado_poster(jogos_compostos: list, threshold_ambas_marcam: int, threshold_cartoes: int, threshold_escanteios: int):
    """Envia alerta composto avançado com poster para múltiplos jogos"""
    if not jogos_compostos:
        st.warning("⚠️ Nenhum jogo para gerar poster composto avançado")
        return False

    try:
        # Agrupar por data
        jogos_por_data = {}
        for jogo in jogos_compostos:
            data_jogo = jogo["hora"].date() if isinstance(jogo["hora"], datetime) else datetime.now().date()
            if data_jogo not in jogos_por_data:
                jogos_por_data[data_jogo] = []
            jogos_por_data[data_jogo].append(jogo)

        enviados = 0
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - PREVISÕES AVANÇADAS {data_str}"
            
            st.info(f"🎨 Gerando poster composto avançado para {data_str} com {len(jogos_data)} jogos...")
            
            # Ordenar por confiança média
            jogos_data_sorted = sorted(jogos_data, key=lambda x: sum(p['confianca'] for p in x['previsoes'])/len(x['previsoes']), reverse=True)
            
            # Gerar poster
            poster = gerar_poster_composto_avancado(jogos_data_sorted, titulo=titulo)
            
            # Calcular estatísticas
            total_jogos = len(jogos_data)
            total_previsoes = total_jogos * 3  # 3 previsões por jogo
            confianca_media_ambas_marcam = sum(j['previsoes'][0]['confianca'] for j in jogos_data) / total_jogos
            confianca_media_cartoes = sum(j['previsoes'][1]['confianca'] for j in jogos_data) / total_jogos
            confianca_media_escanteios = sum(j['previsoes'][2]['confianca'] for j in jogos_data) / total_jogos
            
            caption = (
                f"<b>🎯 PREVISÕES AVANÇADAS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS ANALISADOS: {total_jogos}</b>\n"
                f"<b>🔄 AMBAS MARCAM: Confiança média {confianca_media_ambas_marcam:.1f}%</b>\n"
                f"<b>🟨 CARTÕES: Confiança média {confianca_media_cartoes:.1f}%</b>\n"
                f"<b>🔄 ESCANTEIOS: Confiança média {confianca_media_escanteios:.1f}%</b>\n\n"
                f"<b>📊 CRITÉRIOS DA ANÁLISE:</b>\n"
                f"<b>• Ambas Marcam: ≥{threshold_ambas_marcam}% de confiança</b>\n"
                f"<b>• Cartões: ≥{threshold_cartoes}% de confiança</b>\n"
                f"<b>• Escanteios: ≥{threshold_escanteios}% de confiança</b>\n\n"
                f"<b>⚽ ELITE MASTER SYSTEM - ANÁLISE AVANÇADA CONFIÁVEL</b>"
            )
            
            st.info("📤 Enviando poster composto avançado para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                # SALVAR ALERTA COMPOSTO AVANÇADO PARA FUTURA CONFERÊNCIA
                alerta_id = salvar_alerta_composto_avancado_para_conferencia(jogos_data, threshold_ambas_marcam, threshold_cartoes, threshold_escanteios, poster_enviado=True)
                if alerta_id:
                    st.success(f"🚀 Poster composto avançado enviado e salvo para conferência (24h)! ID: {alerta_id}")
                else:
                    st.success(f"🚀 Poster composto avançado enviado para {data_str}!")
                enviados += 1
            else:
                st.error(f"❌ Falha ao enviar poster composto avançado para {data_str}")
                
        return enviados > 0
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster composto avançado: {str(e)}")
        # Fallback para mensagem de texto
        return enviar_alerta_composto_avancado_texto(jogos_compostos, threshold_ambas_marcam, threshold_cartoes, threshold_escanteios)

def enviar_alerta_composto_avancado_texto(jogos_compostos: list, threshold_ambas_marcam: int, threshold_cartoes: int, threshold_escanteios: int) -> bool:
    """Fallback para alerta composto avançado em texto"""
    try:
        msg = f"🔥 PREVISÕES AVANÇADAS (Ambas Marcam ≥{threshold_ambas_marcam}%, Cartões ≥{threshold_cartoes}%, Escanteios ≥{threshold_escanteios}%):\n\n"
        
        for jogo in jogos_compostos:
            hora_display = jogo.get('hora_formatada', 'Hora inválida')
            data_display = jogo.get('data_formatada', 'Data inválida')
            
            msg += (
                f"🏟️ <b>{jogo['home']}</b> vs <b>{jogo['away']}</b>\n"
                f"🕒 {hora_display} BRT | {data_display} | {jogo['liga']}\n"
            )
            
            for previsao in jogo['previsoes']:
                tipo = previsao['tipo']
                if tipo == "Ambas Marcam":
                    icone = "🔄"
                elif tipo == "Cartões":
                    icone = "🟨"
                else:
                    icone = "🔄"
                    
                msg += f"{icone} {previsao['tendencia']} | Est: {previsao['estimativa']:.1f} | Conf: {previsao['confianca']:.0f}%\n"
            
            msg += "\n"
        
        msg += "<b>🔥 ELITE MASTER SYSTEM - ANÁLISE AVANÇADA</b>"
        
        return enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
    except Exception as e:
        st.error(f"❌ Erro no fallback de texto para alerta composto avançado: {e}")
        return False

# =============================
# SISTEMA DE CONFERÊNCIA PARA ALERTAS COMPOSTOS AVANÇADOS
# =============================

def verificar_resultados_alertas_compostos_avancados(alerta_resultados: bool):
    """Verifica resultados dos alertas compostos avançados salvos"""
    st.info("🔍 Verificando resultados de alertas compostos avançados...")
    
    alertas = carregar_alertas_compostos_avancados()
    if not alertas:
        st.info("ℹ️ Nenhum alerta composto avançado salvo para verificar.")
        return False
    
    alertas_conferidos = 0
    alertas_com_resultados = []
    
    for alerta_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        jogos_alerta = alerta.get("jogos", [])
        todos_jogos_conferidos = True
        algum_jogo_atualizado = False
        
        for jogo_salvo in jogos_alerta:
            # Se já foi conferido, pular
            if jogo_salvo.get("conferido", False):
                continue
                
            fixture_id = jogo_salvo.get("fixture_id")
            if not fixture_id:
                continue
                
            try:
                url = f"{BASE_URL_FD}/matches/{fixture_id}"
                fixture = obter_dados_api_com_rate_limit(url)
                
                if not fixture:
                    todos_jogos_conferidos = False
                    continue
                    
                status = fixture.get("status", "")
                
                # Verificar se jogo terminou
                if status == "FINISHED":
                    # Obter estatísticas da partida
                    estatisticas = obter_estatisticas_partida(fixture_id)
                    
                    if estatisticas:
                        # Determinar se previsão foi correta baseada no tipo
                        previsao_correta = False
                        valor_real = 0
                        
                        tipo_previsao = jogo_salvo['tipo_previsao']
                        
                        if tipo_previsao == "Ambas Marcam":
                            score = fixture.get("score", {}).get("fullTime", {})
                            home_goals = score.get("home", 0)
                            away_goals = score.get("away", 0)
                            ambas_marcaram = home_goals > 0 and away_goals > 0
                            
                            if "SIM" in jogo_salvo['tendencia'] and ambas_marcaram:
                                previsao_correta = True
                            elif "NÃO" in jogo_salvo['tendencia'] and not ambas_marcaram:
                                previsao_correta = True
                                
                            valor_real = "SIM" if ambas_marcaram else "NÃO"
                            
                        elif tipo_previsao == "Cartões":
                            cartoes_total = estatisticas.get("cartoes_amarelos", 0) + estatisticas.get("cartoes_vermelhos", 0)
                            valor_real = cartoes_total
                            
                            if "Mais" in jogo_salvo['tendencia']:
                                try:
                                    limiar = float(jogo_salvo['tendencia'].split(" ")[1].replace(".5", ""))
                                    previsao_correta = cartoes_total > limiar
                                except:
                                    previsao_correta = cartoes_total > 4.5
                            else:
                                try:
                                    limiar = float(jogo_salvo['tendencia'].split(" ")[1].replace(".5", ""))
                                    previsao_correta = cartoes_total < limiar
                                except:
                                    previsao_correta = cartoes_total < 4.5
                                    
                        elif tipo_previsao == "Escanteios":
                            escanteios_total = estatisticas.get("escanteios", 0)
                            valor_real = escanteios_total
                            
                            if "Mais" in jogo_salvo['tendencia']:
                                try:
                                    limiar = float(jogo_salvo['tendencia'].split(" ")[1].replace(".5", ""))
                                    previsao_correta = escanteios_total > limiar
                                except:
                                    previsao_correta = escanteios_total > 8.5
                            else:
                                try:
                                    limiar = float(jogo_salvo['tendencia'].split(" ")[1].replace(".5", ""))
                                    previsao_correta = escanteios_total < limiar
                                except:
                                    previsao_correta = escanteios_total < 8.5
                        
                        # Atualizar jogo salvo
                        jogo_salvo["conferido"] = True
                        jogo_salvo["resultado"] = "GREEN" if previsao_correta else "RED"
                        jogo_salvo["valor_real"] = valor_real
                        jogo_salvo["previsao_correta"] = previsao_correta
                        algum_jogo_atualizado = True
                        
                        st.info(f"✅ Jogo avançado conferido: {jogo_salvo['home']} vs {jogo_salvo['away']} - {tipo_previsao} - {jogo_salvo['resultado']}")
                        
                    else:
                        todos_jogos_conferidos = False
                        st.info(f"⏳ Aguardando estatísticas para jogo avançado: {jogo_salvo['home']} vs {jogo_salvo['away']}")
                else:
                    todos_jogos_conferidos = False
                    st.info(f"⏳ Jogo avançado pendente: {jogo_salvo['home']} vs {jogo_salvo['away']} - Status: {status}")
                    
            except Exception as e:
                st.error(f"❌ Erro ao verificar jogo composto avançado {fixture_id}: {e}")
                todos_jogos_conferidos = False
        
        # Se todos os jogos deste alerta foram conferidos, marcar o alerta como conferido
        if todos_jogos_conferidos:
            alerta["conferido"] = True
            
            # Calcular estatísticas do alerta
            jogos_conferidos = [j for j in jogos_alerta if j.get("conferido", False)]
            if jogos_conferidos:
                total_previsoes = len(jogos_conferidos)
                green_count = sum(1 for j in jogos_conferidos if j.get("resultado") == "GREEN")
                taxa_acerto = (green_count / total_previsoes * 100) if total_previsoes > 0 else 0
                
                # Estatísticas por tipo
                previsoes_ambas_marcam = [j for j in jogos_conferidos if j.get("tipo_previsao") == "Ambas Marcam"]
                previsoes_cartoes = [j for j in jogos_conferidos if j.get("tipo_previsao") == "Cartões"]
                previsoes_escanteios = [j for j in jogos_conferidos if j.get("tipo_previsao") == "Escanteios"]
                
                alerta["estatisticas"] = {
                    "total_previsoes": total_previsoes,
                    "green_count": green_count,
                    "red_count": total_previsoes - green_count,
                    "taxa_acerto": taxa_acerto,
                    "ambas_marcam_total": len(previsoes_ambas_marcam),
                    "ambas_marcam_green": sum(1 for j in previsoes_ambas_marcam if j.get("resultado") == "GREEN"),
                    "cartoes_total": len(previsoes_cartoes),
                    "cartoes_green": sum(1 for j in previsoes_cartoes if j.get("resultado") == "GREEN"),
                    "escanteios_total": len(previsoes_escanteios),
                    "escanteios_green": sum(1 for j in previsoes_escanteios if j.get("resultado") == "GREEN"),
                    "data_conferencia": datetime.now().isoformat()
                }
            
            alertas_conferidos += 1
            alertas_com_resultados.append((alerta_id, alerta))
            st.success(f"🎯 Alerta composto avançado {alerta_id} totalmente conferido!")
        
        # Se houve algum jogo atualizado, salvar as alterações
        if algum_jogo_atualizado:
            alerta["jogos"] = jogos_alerta
            salvar_alertas_compostos_avancados(alertas)
            st.info(f"💾 Alterações salvas para alerta avançado {alerta_id}")
    
    # ENVIO DE ALERTAS DE RESULTADOS COMPOSTOS AVANÇADOS
    resultados_enviados = 0
    if alertas_com_resultados and alerta_resultados:
        st.info(f"🎯 Enviando {len(alertas_com_resultados)} alertas de resultados compostos avançados...")
        
        for alerta_id, alerta_data in alertas_com_resultados:
            try:
                if enviar_alerta_composto_avancado_resultados_poster(alerta_id, alerta_data):
                    st.success(f"✅ Alerta de resultados compostos avançados enviado: {alerta_id}")
                    resultados_enviados += 1
                else:
                    st.error(f"❌ Falha ao enviar alerta de resultados compostos avançados: {alerta_id}")
            except Exception as e:
                st.error(f"❌ Erro ao enviar alerta avançado {alerta_id}: {e}")
                
        if resultados_enviados > 0:
            st.success(f"🚀 {resultados_enviados} alertas de resultados compostos avançados enviados!")
    
    elif alertas_com_resultados:
        st.info(f"ℹ️ {len(alertas_com_resultados)} alertas compostos avançados prontos para resultados, mas envio desativado")
    
    if alertas_conferidos > 0:
        st.success(f"✅ {alertas_conferidos} alertas compostos avançados totalmente conferidos!")
    
    return resultados_enviados > 0

def enviar_alerta_composto_avancado_resultados_poster(alerta_id: str, alerta_data: dict):
    """Envia alerta composto avançado de RESULTS com poster para o Telegram"""
    try:
        jogos = alerta_data.get("jogos", [])
        if not jogos:
            st.warning(f"⚠️ Nenhum jogo no alerta composto avançado {alerta_id}")
            return False

        # Filtrar apenas jogos conferidos com resultados
        jogos_com_resultado = [j for j in jogos if j.get("conferido", False) and j.get("valor_real") is not None]
        
        if not jogos_com_resultado:
            st.warning(f"⚠️ Nenhum resultado final no alerta composto avançado {alerta_id}")
            return False

        # Agrupar por data do jogo
        jogos_por_data = {}
        for jogo in jogos_com_resultado:
            try:
                # Usar a data do jogo em vez da data do alerta
                data_jogo_str = jogo.get("data_jogo", "")
                if data_jogo_str:
                    data_jogo = datetime.fromisoformat(data_jogo_str).date()
                else:
                    data_jogo = datetime.now().date()
                    
                if data_jogo not in jogos_por_data:
                    jogos_por_data[data_jogo] = []
                jogos_por_data[data_jogo].append(jogo)
            except:
                continue

        enviados = 0
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - RESULTADOS AVANÇADOS {data_str}"
            
            st.info(f"🎨 Gerando poster de RESULTADOS avançados para {data_str} com {len(jogos_data)} previsões...")
            
            # Gerar poster de resultados avançados
            poster = gerar_poster_resultados_avancados(jogos_data, titulo=titulo)
            
            # Calcular estatísticas do alerta composto avançado
            stats_alerta = alerta_data.get("estatisticas", {})
            total_previsoes = stats_alerta.get("total_previsoes", len(jogos_data))
            green_count = stats_alerta.get("green_count", sum(1 for j in jogos_data if j.get("resultado") == "GREEN"))
            taxa_acerto = stats_alerta.get("taxa_acerto", (green_count / total_previsoes * 100) if total_previsoes > 0 else 0)
            
            caption = (
                f"<b>🏁 RESULTADOS OFICIAIS - ALERTA AVANÇADO</b>\n\n"
                f"<b>📅 DATA DOS JOGOS: {data_str}</b>\n"
                f"<b>📋 TOTAL DE PREVISÕES: {total_previsoes}</b>\n"
                f"<b>🟢 GREEN: {green_count} previsões</b>\n"
                f"<b>🔴 RED: {total_previsoes - green_count} previsões</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO POR TIPO:</b>\n"
                f"<b>• Ambas Marcam: {stats_alerta.get('ambas_marcam_green', 0)}/{stats_alerta.get('ambas_marcam_total', 0)}</b>\n"
                f"<b>• Cartões: {stats_alerta.get('cartoes_green', 0)}/{stats_alerta.get('cartoes_total', 0)}</b>\n"
                f"<b>• Escanteios: {stats_alerta.get('escanteios_green', 0)}/{stats_alerta.get('escanteios_total', 0)}</b>\n\n"
                f"<b>🔥 ELITE MASTER - SISTEMA AVANÇADO VERIFICADO</b>"
            )
            
            st.info("📤 Enviando poster de RESULTADOS avançados para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                st.success(f"🚀 Poster de RESULTADOS avançados enviado para {data_str}!")
                
                # Registrar no histórico de resultados avançados
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tipo_previsao": jogo["tipo_previsao"],
                        "tendencia": jogo["tendencia"],
                        "estimativa": jogo["estimativa"],
                        "confianca": jogo["confianca"],
                        "valor_real": jogo.get("valor_real", "-"),
                        "resultado": "🟢 GREEN" if jogo.get("resultado") == "GREEN" else "🔴 RED",
                        "alerta_id": alerta_id
                    }, "compostos_avancados")
                
                enviados += 1
            else:
                st.error(f"❌ Falha ao enviar poster de resultados avançados para {data_str}")
                
        return enviados > 0
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados avançados: {str(e)}")
        return False

def gerar_poster_resultados_avancados(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS AVANÇADOS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais das previsões avançadas
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_PREVISAO = 350  # Menor altura para previsões individuais
    PADDING = 100
    
    previsoes_count = len(jogos)
    altura_total = ALTURA_TOPO + previsoes_count * ALTURA_POR_PREVISAO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(80)
    FONTE_SUBTITULO = criar_fonte(50)
    FONTE_TIMES = criar_fonte(45)
    FONTE_PREVISAO = criar_fonte(40)
    FONTE_RESULTADO = criar_fonte(50)
    FONTE_INFO = criar_fonte(35)

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

    for idx, previsao in enumerate(jogos):
        # Cores baseadas no resultado
        if previsao.get('resultado') == "GREEN":
            cor_borda = (76, 175, 80)  # VERDE
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)  # VERMELHO
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        # Caixa da previsão
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_PREVISAO - 20
        
        # Fundo com borda colorida
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=3)

        # BADGE RESULTADO (GREEN/RED)
        badge_text = texto_resultado
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 20
            badge_h = 50
            badge_x = x1 - badge_w - 10
            badge_y = y0 + 10
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=cor_resultado, outline=cor_resultado)
            draw.text((badge_x + 10, badge_y + 5), badge_text, font=FONTE_RESULTADO, fill=(255, 255, 255))
        except:
            pass

        # Times e tipo de previsão
        home_text = previsao['home'][:15]
        away_text = previsao['away'][:15]
        
        # Tipo de previsão com ícone
        tipo = previsao['tipo_previsao']
        if tipo == "Ambas Marcam":
            icone = "🔄"
            cor_tipo = (255, 215, 0)
        elif tipo == "Cartões":
            icone = "🟨" 
            cor_tipo = (255, 152, 0)
        else:
            icone = "🔄"
            cor_tipo = (100, 200, 255)
            
        tipo_text = f"{icone} {tipo}"
        
        try:
            tipo_bbox = draw.textbbox((0, 0), tipo_text, font=FONTE_SUBTITULO)
            tipo_w = tipo_bbox[2] - tipo_bbox[0]
            draw.text((x0 + 20, y0 + 15), tipo_text, font=FONTE_SUBTITULO, fill=cor_tipo)
        except:
            pass

        # Nomes dos times
        try:
            times_text = f"{home_text} vs {away_text}"
            times_bbox = draw.textbbox((0, 0), times_text, font=FONTE_TIMES)
            times_w = times_bbox[2] - times_bbox[0]
            draw.text((x0 + 20, y0 + 70), times_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        # Previsão vs Real
        y_info = y0 + 120
        
        textos = [
            f"Previsão: {previsao['tendencia']}",
            f"Real: {previsao.get('valor_real', 'N/A')}",
            f"Confiança: {previsao['confianca']:.0f}% | Resultado: {texto_resultado}"
        ]
        
        for i, text in enumerate(textos):
            try:
                text_bbox = draw.textbbox((0, 0), text, font=FONTE_PREVISAO)
                text_w = text_bbox[2] - text_bbox[0]
                draw.text((x0 + 20, y_info + i * 40), text, font=FONTE_PREVISAO, 
                         fill=(255, 255, 255) if i < 2 else cor_resultado)
            except:
                pass

        # Liga
        liga_text = f"Liga: {previsao['liga']}"
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_INFO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text((x1 - liga_w - 20, y1 - 40), liga_text, font=FONTE_INFO, fill=(150, 150, 150))
        except:
            pass

        y_pos += ALTURA_POR_PREVISAO

    # Rodapé
    rodape_text = f"Resultados oficiais • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        pass

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados avançados GERADO com {len(jogos)} previsões")
    return buffer

# =============================
# HISTÓRICO DE CONFERÊNCIAS - COM PERSISTÊNCIA
# =============================
def carregar_historico(caminho: str = HISTORICO_PATH) -> list:
    """Carrega histórico com persistência robusta"""
    dados = carregar_json(caminho)
    if isinstance(dados, list):
        return dados
    elif isinstance(dados, dict):
        # Se por acaso foi salvo como dict, converte para list
        return list(dados.values()) if dados else []
    else:
        return []

def salvar_historico(historico: list, caminho: str = HISTORICO_PATH):
    """Salva histórico mantendo a estrutura de lista"""
    return salvar_json(caminho, historico)

def registrar_no_historico(resultado: dict, tipo: str = "gols"):
    """Registra no histórico específico para cada tipo de previsão com persistência"""
    if not resultado:
        return
        
    caminhos_historico = {
        "gols": HISTORICO_PATH,
        "ambas_marcam": HISTORICO_AMBAS_MARCAM_PATH,
        "cartoes": HISTORICO_CARTOES_PATH,
        "escanteios": HISTORICO_ESCANTEIOS_PATH,
        "compostos": HISTORICO_COMPOSTOS_PATH,
        "compostos_avancados": HISTORICO_COMPOSTOS_AVANCADOS_PATH  # NOVO
    }
    
    caminho = caminhos_historico.get(tipo, HISTORICO_PATH)
    historico = carregar_historico(caminho)
    
    registro = {
        "data_conferencia": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "home": resultado.get("home"),
        "away": resultado.get("away"),
        "tendencia": resultado.get("tendencia"),
        "estimativa": round(resultado.get("estimativa", 0), 2),
        "confianca": round(resultado.get("confianca", 0), 1),
        "placar": resultado.get("placar", "-"),
        "resultado": resultado.get("resultado", "⏳ Aguardando")
    }
    
    # Adicionar campos específicos para cada tipo
    if tipo == "ambas_marcam":
        registro["previsao"] = resultado.get("previsao", "")
        registro["ambas_marcaram"] = resultado.get("ambas_marcaram", False)
    elif tipo == "cartoes":
        registro["cartoes_total"] = resultado.get("cartoes_total", 0)
        registro["limiar_cartoes"] = resultado.get("limiar_cartoes", 0)
    elif tipo == "escanteios":
        registro["escanteios_total"] = resultado.get("escanteios_total", 0)
        registro["limiar_escanteios"] = resultado.get("limiar_escanteios", 0)
    elif tipo == "compostos":
        registro["alerta_id"] = resultado.get("alerta_id", "")
    elif tipo == "compostos_avancados":  # NOVO
        registro["tipo_previsao"] = resultado.get("tipo_previsao", "")
        registro["valor_real"] = resultado.get("valor_real", "")
        registro["alerta_id"] = resultado.get("alerta_id", "")
    
    historico.append(registro)
    
    # Manter apenas os últimos 1000 registros para evitar arquivos muito grandes
    if len(historico) > 1000:
        historico = historico[-1000:]
    
    salvar_historico(historico, caminho)

def limpar_historico(tipo: str = "todos"):
    """Faz backup e limpa histórico específico ou todos com persistência"""
    caminhos = {
        "gols": HISTORICO_PATH,
        "ambas_marcam": HISTORICO_AMBAS_MARCAM_PATH,
        "cartoes": HISTORICO_CARTOES_PATH,
        "escanteios": HISTORICO_ESCANTEIOS_PATH,
        "compostos": HISTORICO_COMPOSTOS_PATH,
        "compostos_avancados": HISTORICO_COMPOSTOS_AVANCADOS_PATH  # NOVO
    }
    
    if tipo == "todos":
        historicos_limpos = 0
        for nome, caminho in caminhos.items():
            historico = carregar_historico(caminho)
            if historico:
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"data/historico_{nome}_backup_{ts}.json"
                    salvar_json(backup_name, historico)
                    
                    # Limpa o histórico atual
                    salvar_historico([], caminho)
                    historicos_limpos += 1
                    st.success(f"✅ Histórico {nome} limpo. Backup: {backup_name}")
                except Exception as e:
                    st.error(f"Erro ao limpar {nome}: {e}")
            else:
                st.info(f"ℹ️ Histórico {nome} já está vazio")
        st.success(f"🧹 Todos os históricos limpos. {historicos_limpos} backups criados.")
    else:
        caminho = caminhos.get(tipo)
        if caminho:
            historico = carregar_historico(caminho)
            if historico:
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"data/historico_{tipo}_backup_{ts}.json"
                    salvar_json(backup_name, historico)
                    
                    # Limpa o histórico atual
                    salvar_historico([], caminho)
                    st.success(f"🧹 Histórico {tipo} limpo. Backup: {backup_name}")
                except Exception as e:
                    st.error(f"Erro ao limpar histórico {tipo}: {e}")
            else:
                st.info(f"⚠️ Histórico {tipo} já está vazio")
        else:
            st.error(f"❌ Tipo de histórico inválido: {tipo}")

# =============================
# Utilitários de Data e Formatação - CORRIGIDOS
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    """Formata data ISO de forma robusta - CORRIGIDA"""
    try:
        # Converter string ISO para datetime com timezone
        if data_iso.endswith('Z'):
            data_utc = datetime.fromisoformat(data_iso[:-1] + '+00:00').replace(tzinfo=timezone.utc)
        else:
            data_utc = datetime.fromisoformat(data_iso)

        # Converter UTC para horário de Brasília (UTC-3)
        brasilia_tz = timezone(timedelta(hours=-3))
        data_brasilia = data_utc.astimezone(brasilia_tz)

        return data_brasilia.strftime("%d/%m/%Y"), data_brasilia.strftime("%H:%M")
    except (ValueError, TypeError) as e:
        st.warning(f"⚠️ Erro ao formatar data {data_iso}: {e}")
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Funções de Imagem e Fonte
# =============================
def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
    """Cria fonte com fallback robusto - CORRIGIDA E MELHORADA"""
    try:
        # Tentar fontes comuns em diferentes sistemas
        font_paths = [
            "arial.ttf", "Arial.ttf", "arialbd.ttf", "Arial_Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf"
        ]
        
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, tamanho)
            except Exception:
                continue
        
        # Tentar fontes do Pillow
        try:
            return ImageFont.truetype("arial", tamanho)
        except:
            try:
                return ImageFont.load_default()
            except:
                # Último fallback - criar fonte básica
                return ImageFont.load_default()
        
    except Exception as e:
        print(f"Erro ao carregar fonte: {e}")
        return ImageFont.load_default()

def baixar_imagem_url(url: str, timeout: int = 8) -> Image.Image | None:
    """Tenta baixar uma imagem e retornar PIL.Image. Retorna None se falhar."""
    if not url or url == "":
        return None
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(url, timeout=timeout, stream=True, headers=headers)
        resp.raise_for_status()
        
        # Verificar se é uma imagem válida
        if 'image' not in resp.headers.get('content-type', ''):
            return None
            
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except Exception as e:
        print(f"Erro ao baixar imagem {url}: {e}")
        return None

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
        st.error(f"Erro ao enviar foto para Telegram: {e}")
        return False

def obter_dados_api(url: str, timeout: int = 10) -> dict | None:
    """Função original mantida para compatibilidade - agora usa rate limit"""
    return obter_dados_api_com_rate_limit(url, timeout)

# =============================
# FUNÇÕES DE API MELHORADAS
# =============================

def obter_classificacao(liga_id: str) -> dict:
    """Obtém classificação com tratamento de erro melhorado"""
    cache = carregar_cache_classificacao()
    if liga_id in cache and cache[liga_id]:  # Só usar cache se não estiver vazio
        return cache[liga_id]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
    data = obter_dados_api_com_rate_limit(url)
    if not data:
        st.error(f"❌ Erro ao obter classificação para {liga_id}")
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
                "played": t.get("playedGames", 1)
            }
    
    # Só salva no cache se obteve dados válidos
    if standings:
        cache[liga_id] = standings
        salvar_cache_classificacao(cache)
    
    return standings

def obter_jogos(liga_id: str, data: str) -> list:
    """Obtém jogos com tratamento de erro melhorado - VERSÃO CORRIGIDA"""
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    
    # Verificar se o cache é válido (não é resultado de erro anterior)
    if key in cache and cache[key]:  # Só usar cache se não estiver vazio
        return cache[key]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
    data_api = obter_dados_api_com_rate_limit(url)
    
    if not data_api:
        st.error(f"❌ Erro ao obter jogos para {liga_id} em {data}")
        return []  # Retorna vazio em caso de erro
    
    if "matches" not in data_api:
        st.warning(f"⚠️ Resposta inesperada da API para {liga_id}: {data_api}")
        return []
    
    jogos = data_api.get("matches", [])
    
    # Só salva no cache se obteve dados válidos
    if jogos:
        cache[key] = jogos
        salvar_cache_jogos(cache)
    
    return jogos

# =============================
# NOVAS FUNÇÕES DE PREVISÃO COM DADOS REAIS
# =============================

def obter_estatisticas_time_real(time_id: str, liga_id: str) -> dict:
    """
    Obtém estatísticas REAIS do time da API - ATUALIZADA PARA USAR DADOS HISTÓRICOS
    """
    return coletar_dados_historicos_time_com_cache(time_id, liga_id)

def obter_estatisticas_partida(fixture_id: str) -> dict:
    """
    Obtém estatísticas REAIS de uma partida específica
    """
    try:
        url = f"{BASE_URL_FD}/matches/{fixture_id}"
        data = obter_dados_api_com_rate_limit(url)
        
        if not data:
            return {}
            
        match = data.get("match", {})
        statistics = match.get("statistics", {})
        
        return {
            "cartoes_amarelos": statistics.get("yellowCards", 0),
            "cartoes_vermelhos": statistics.get("redCards", 0),
            "escanteios": statistics.get("cornerKicks", 0),
            "finalizacoes": statistics.get("totalShots", 0),
            "finalizacoes_gol": statistics.get("shotsOnGoal", 0),
            "posse_bola": statistics.get("ballPossession", 0)
        }
    except Exception as e:
        st.error(f"Erro ao obter estatísticas da partida {fixture_id}: {e}")
        return {}

def calcular_previsao_ambas_marcam_real(home: str, away: str, classificacao: dict) -> tuple[float, float, str]:
    """
    Previsão REAL: Ambas as equipes marcam usando dados reais da API
    """
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
    
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)
    
    # Probabilidade home marcar: média de gols do home + média de gols sofridos do away
    prob_home_marcar = (dados_home["scored"] / played_home + dados_away["against"] / played_away) / 2
    
    # Probabilidade away marcar: média de gols do away + média de gols sofridos do home
    prob_away_marcar = (dados_away["scored"] / played_away + dados_home["against"] / played_home) / 2
    
    # Probabilidade de ambas marcarem
    prob_ambas_marcam = prob_home_marcar * prob_away_marcar
    
    # Ajustar probabilidade base
    probabilidade_base = prob_ambas_marcam * 100
    
    # Calcular confiança baseada na consistência dos times
    consistencia_home = min(1.0, dados_home["scored"] / max(dados_home["against"], 0.1))
    consistencia_away = min(1.0, dados_away["scored"] / max(dados_away["against"], 0.1))
    fator_consistencia = (consistencia_home + consistencia_away) / 2
    
    confianca = min(95, probabilidade_base * fator_consistencia * 1.2)
    
    # Definir tendência
    if probabilidade_base >= 60:
        tendencia = "SIM - Ambas Marcam"
        confianca = min(95, confianca + 10)
    elif probabilidade_base >= 40:
        tendencia = "PROVÁVEL - Ambas Marcam"
    else:
        tendencia = "NÃO - Ambas Marcam"
        confianca = max(30, confianca - 10)
    
    return probabilidade_base, confianca, tendencia

# =============================
# Lógica de Análise e Alertas ORIGINAL
# =============================
def calcular_tendencia(home: str, away: str, classificacao: dict) -> tuple[float, float, str]:
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)

    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0) * 10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0) * 10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa) * 10)

    return estimativa, confianca, tendencia

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float, alerta_individual: bool):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        # Só envia alerta individual se a checkbox estiver ativada
        if alerta_individual:
            enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# SISTEMA DE ALERTAS DE RESULTADOS ORIGINAL
# =============================

def verificar_resultados_finais(alerta_resultados: bool):
    """Verifica resultados finais dos jogos e envia alertas - ATUALIZADA"""
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para verificar resultados.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        # Buscar dados atualizados do jogo
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture = obter_dados_api_com_rate_limit(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            score = fixture.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
            # Verificar se jogo terminou e tem resultado
            if status == "FINISHED" and home_goals is not None and away_goals is not None:
                # Obter URLs dos escudos
                home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
                
                # Preparar dados para o poster
                jogo_resultado = {
                    "id": fixture_id,
                    "home": fixture["homeTeam"]["name"],
                    "away": fixture["awayTeam"]["name"],
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "liga": fixture.get("competition", {}).get("name", "Desconhecido"),
                    "data": fixture["utcDate"],
                    "tendencia_prevista": alerta.get("tendencia", "Desconhecida"),
                    "estimativa_prevista": alerta.get("estimativa", 0),
                    "confianca_prevista": alerta.get("confianca", 0),
                    "home_crest": home_crest,  # NOVO
                    "away_crest": away_crest   # NOVO
                }
                
                jogos_com_resultado.append(jogo_resultado)
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar jogo {fixture_id}: {e}")
    
    # Enviar alertas em lote se houver resultados E a checkbox estiver ativada
    if jogos_com_resultado and alerta_resultados:
        enviar_alerta_resultados_poster(jogos_com_resultado)
        salvar_alertas(alertas)
        st.success(f"✅ {resultados_enviados} resultados processados e alertas enviados!")
    elif jogos_com_resultado:
        st.info(f"ℹ️ {resultados_enviados} resultados encontrados, mas alerta de resultados desativado")
        # Apenas marca como conferido sem enviar alerta
        salvar_alertas(alertas)
    else:
        st.info("ℹ️ Nenhum novo resultado final encontrado.")

# =============================
# SISTEMA DE CONFERÊNCIA PARA ALERTAS COMPOSTOS - NOVO
# =============================

def verificar_resultados_compostos(alerta_resultados: bool):
    """Verifica resultados finais para alertas compostos (poster)"""
    st.info("🔍 Verificando resultados dos alertas compostos...")
    
    # Carregar todos os alertas
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta composto para verificar.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture = obter_dados_api_com_rate_limit(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            score = fixture.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
            # Verificar se jogo terminou e tem resultado
            if status == "FINISHED" and home_goals is not None and away_goals is not None:
                # Obter URLs dos escudos
                home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
                
                # Preparar dados para o poster
                jogo_resultado = {
                    "id": fixture_id,
                    "home": fixture["homeTeam"]["name"],
                    "away": fixture["awayTeam"]["name"],
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "liga": fixture.get("competition", {}).get("name", "Desconhecido"),
                    "data": fixture["utcDate"],
                    "tendencia_prevista": alerta.get("tendencia", "Desconhecida"),
                    "estimativa_prevista": alerta.get("estimativa", 0),
                    "confianca_prevista": alerta.get("confianca", 0),
                    "home_crest": home_crest,
                    "away_crest": away_crest
                }
                
                jogos_com_resultado.append(jogo_resultado)
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar jogo composto {fixture_id}: {e}")
    
    # Enviar alertas em lote se houver resultados E a checkbox estiver ativada
    if jogos_com_resultado and alerta_resultados:
        enviar_alerta_resultados_compostos_poster(jogos_com_resultado)
        salvar_alertas(alertas)
        st.success(f"✅ {resultados_enviados} resultados compostos processados e alertas enviados!")
    elif jogos_com_resultado:
        st.info(f"ℹ️ {resultados_enviados} resultados compostos encontrados, mas alerta de resultados desativado")
        # Apenas marca como conferido sem enviar alerta
        salvar_alertas(alertas)
    else:
        st.info("ℹ️ Nenhum novo resultado composto final encontrado.")

def enviar_alerta_resultados_compostos_poster(jogos_com_resultado: list):
    """Envia alerta de resultados compostos com poster para o Telegram"""
    if not jogos_com_resultado:
        st.warning("⚠️ Nenhum resultado composto para enviar")
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
            
            if jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5:
                previsao_correta = True
            elif jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5:
                previsao_correta = True
            elif jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5:
                previsao_correta = True
            
            jogo['resultado'] = "GREEN" if previsao_correta else "RED"
            jogos_por_data[data_jogo].append(jogo)

        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - RESULTADOS COMPOSTOS {data_str}"
            
            st.info(f"🎨 Gerando poster de resultados compostos para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_resultados_compostos_com_escudos(jogos_data, titulo=titulo)
            
            # Calcular estatísticas
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j.get('resultado') == "GREEN")
            red_count = total_jogos - green_count
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            caption = (
                f"<b>🏁 RESULTADOS COMPOSTOS OFICIAIS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS ANALISADOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {red_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO DO SISTEMA COMPOSTO:</b>\n"
                f"<b>• Análise Preditiva Avançada</b>\n"
                f"<b>• Resultados em Tempo Real</b>\n"
                f"<b>• Precisão Comprovada</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM - CONFIABILIDADE COMPROVADA</b>"
            )
            
            st.info("📤 Enviando resultados compostos para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                st.success(f"🚀 Poster de resultados compostos enviado para {data_str}!")
                
                # Registrar no histórico
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"], 
                        "tendencia": jogo["tendencia_prevista"],
                        "estimativa": jogo["estimativa_prevista"],
                        "confianca": jogo["confianca_prevista"],
                        "placar": f"{jogo['home_goals']}x{jogo['away_goals']}",
                        "resultado": "🟢 GREEN" if jogo.get('resultado') == "GREEN" else "🔴 RED"
                    })
            else:
                st.error(f"❌ Falha ao enviar poster de resultados compostos para {data_str}")
                
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados compostos: {str(e)}")
        # Fallback para mensagem de texto
        enviar_alerta_resultados_compostos_texto(jogos_com_resultado)

def enviar_alerta_resultados_compostos_texto(jogos_com_resultado: list):
    """Fallback para envio de resultados compostos em texto"""
    try:
        msg = "<b>🏁 RESULTADOS COMPOSTOS - SISTEMA RED/GREEN</b>\n\n"
        
        for jogo in jogos_com_resultado[:10]:  # Limitar a 10 jogos para não exceder limite do Telegram
            total_gols = jogo['home_goals'] + jogo['away_goals']
            resultado = "🟢 GREEN" if ((jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5) or 
                            (jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5) or
                            (jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5)) else "🔴 RED"
            
            msg += (
                f"{resultado} <b>{jogo['home']}</b> {jogo['home_goals']}x{jogo['away_goals']} <b>{jogo['away']}</b>\n"
                f"Previsão: {jogo['tendencia_prevista']} | Conf: {jogo['confianca_prevista']:.0f}%\n\n"
            )
        
        msg += "<b>🔥 ELITE MASTER SYSTEM - RESULTADOS COMPOSTOS</b>"
        
        return enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
    except Exception as e:
        st.error(f"❌ Erro no fallback de texto para resultados compostos: {e}")
        return False

# =============================
# SISTEMA DE CONFERÊNCIA PARA NOVAS PREVISÕES - ATUALIZADO
# =============================

def verificar_resultados_finais_completo(alerta_resultados: bool):
    """Verifica resultados finais para TODOS os tipos de previsão - ATUALIZADA"""
    st.info("🔍 Verificando resultados para TODOS os tipos de previsão...")
    
    # Resultados Gols (Original)
    verificar_resultados_finais(alerta_resultados)
    
    # Resultados Compostos (NOVO)
    verificar_resultados_compostos(alerta_resultados)
    
    # Alertas Compostos Salvos (NOVO)
    verificar_resultados_alertas_compostos(alerta_resultados)
    
    # Alertas Compostos Avançados (NOVO)
    verificar_resultados_alertas_compostos_avancados(alerta_resultados)
    
    # Novas previsões
    verificar_resultados_ambas_marcam(alerta_resultados)
    verificar_resultados_cartoes(alerta_resultados) 
    verificar_resultados_escanteios(alerta_resultados)
    
    st.success("✅ Verificação completa de resultados concluída!")

def verificar_resultados_ambas_marcam(alerta_resultados: bool):
    """Verifica resultados para previsão Ambas Marcam - CORRIGIDA"""
    alertas = carregar_alertas_ambas_marcam()
    if not alertas:
        st.info("ℹ️ Nenhum alerta Ambas Marcam para verificar.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture = obter_dados_api_com_rate_limit(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            score = fixture.get("score", {}).get("fullTime", {})
            home_goals = score.get("home", 0)
            away_goals = score.get("away", 0)
            
            if status == "FINISHED" and home_goals is not None and away_goals is not None:
                ambas_marcaram = home_goals > 0 and away_goals > 0
                
                # Determinar se previsão foi correta
                previsao_correta = False
                if "SIM" in alerta["tendencia"] and ambas_marcaram:
                    previsao_correta = True
                elif "NÃO" in alerta["tendencia"] and not ambas_marcaram:
                    previsao_correta = True
                elif "PROVÁVEL" in alerta["tendencia"] and ambas_marcaram:
                    previsao_correta = True
                
                jogo_resultado = {
                    "id": fixture_id,
                    "home": fixture["homeTeam"]["name"],
                    "away": fixture["awayTeam"]["name"],
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "liga": fixture.get("competition", {}).get("name", "Desconhecido"),
                    "data": fixture["utcDate"],
                    "previsao": alerta.get("tendencia", ""),
                    "probabilidade_prevista": alerta.get("probabilidade", 0),
                    "confianca_prevista": alerta.get("confianca", 0),
                    "ambas_marcaram": ambas_marcaram,
                    "previsao_correta": previsao_correta,
                    "home_crest": fixture.get("homeTeam", {}).get("crest", ""),
                    "away_crest": fixture.get("awayTeam", {}).get("crest", "")
                }
                
                jogos_com_resultado.append(jogo_resultado)
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar ambas marcam {fixture_id}: {e}")
    
    if jogos_com_resultado:
        if alerta_resultados:
            enviar_alerta_resultados_ambas_marcam_poster(jogos_com_resultado)
        salvar_alertas_ambas_marcam(alertas)
        st.success(f"✅ {resultados_enviados} resultados Ambas Marcam processados!")
    else:
        st.info("ℹ️ Nenhum novo resultado Ambas Marcam encontrado.")

def verificar_resultados_cartoes(alerta_resultados: bool):
    """Verifica resultados para previsão de Cartões - CORRIGIDA"""
    alertas = carregar_alertas_cartoes()
    if not alertas:
        st.info("ℹ️ Nenhum alerta Cartões para verificar.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            # Obter estatísticas REAIS da partida
            estatisticas = obter_estatisticas_partida(fixture_id)
            
            if estatisticas:
                cartoes_total = estatisticas.get("cartoes_amarelos", 0) + estatisticas.get("cartoes_vermelhos", 0)
                
                # Determinar se a previsão foi correta
                previsao_correta = False
                if "Mais" in alerta["tendencia"]:
                    try:
                        limiar = float(alerta["tendencia"].split(" ")[1].replace(".5", ""))
                        previsao_correta = cartoes_total > limiar
                    except:
                        previsao_correta = cartoes_total > 4.5  # Fallback
                else:
                    try:
                        limiar = float(alerta["tendencia"].split(" ")[1].replace(".5", ""))
                        previsao_correta = cartoes_total < limiar
                    except:
                        previsao_correta = cartoes_total < 4.5  # Fallback
                
                # Obter dados básicos do jogo
                url = f"{BASE_URL_FD}/matches/{fixture_id}"
                fixture = obter_dados_api_com_rate_limit(url)
                
                if fixture:
                    jogo_resultado = {
                        "id": fixture_id,
                        "home": fixture["homeTeam"]["name"],
                        "away": fixture["awayTeam"]["name"],
                        "cartoes_total": cartoes_total,
                        "liga": fixture.get("competition", {}).get("name", "Desconhecido"),
                        "data": fixture["utcDate"],
                        "previsao": alerta.get("tendencia", ""),
                        "estimativa_prevista": alerta.get("estimativa", 0),
                        "confianca_prevista": alerta.get("confianca", 0),
                        "previsao_correta": previsao_correta,
                        "limiar_cartoes": limiar if 'limiar' in locals() else 4.5,
                        "home_crest": fixture.get("homeTeam", {}).get("crest", ""),
                        "away_crest": fixture.get("awayTeam", {}).get("crest", "")
                    }
                    
                    jogos_com_resultado.append(jogo_resultado)
                    alerta["conferido"] = True
                    resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar cartões {fixture_id}: {e}")
    
    if jogos_com_resultado:
        if alerta_resultados:
            enviar_alerta_resultados_cartoes_poster(jogos_com_resultado)
        salvar_alertas_cartoes(alertas)
        st.success(f"✅ {resultados_enviados} resultados Cartões processados!")
    else:
        st.info("ℹ️ Nenhum novo resultado Cartões encontrado.")

def verificar_resultados_escanteios(alerta_resultados: bool):
    """Verifica resultados para previsão de Escanteios - CORRIGIDA"""
    alertas = carregar_alertas_escanteios()
    if not alertas:
        st.info("ℹ️ Nenhum alerta Escanteios para verificar.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            # Obter estatísticas REAIS da partida
            estatisticas = obter_estatisticas_partida(fixture_id)
            
            if estatisticas:
                escanteios_total = estatisticas.get("escanteios", 0)
                
                # Determinar se a previsão foi correta
                previsao_correta = False
                if "Mais" in alerta["tendencia"]:
                    try:
                        limiar = float(alerta["tendencia"].split(" ")[1].replace(".5", ""))
                        previsao_correta = escanteios_total > limiar
                    except:
                        previsao_correta = escanteios_total > 8.5  # Fallback
                else:
                    try:
                        limiar = float(alerta["tendencia"].split(" ")[1].replace(".5", ""))
                        previsao_correta = escanteios_total < limiar
                    except:
                        previsao_correta = escanteios_total < 8.5  # Fallback
                
                # Obter dados básicos do jogo
                url = f"{BASE_URL_FD}/matches/{fixture_id}"
                fixture = obter_dados_api_com_rate_limit(url)
                
                if fixture:
                    jogo_resultado = {
                        "id": fixture_id,
                        "home": fixture["homeTeam"]["name"],
                        "away": fixture["awayTeam"]["name"],
                        "escanteios_total": escanteios_total,
                        "liga": fixture.get("competition", {}).get("name", "Desconhecido"),
                        "data": fixture["utcDate"],
                        "previsao": alerta.get("tendencia", ""),
                        "estimativa_prevista": alerta.get("estimativa", 0),
                        "confianca_prevista": alerta.get("confianca", 0),
                        "previsao_correta": previsao_correta,
                        "limiar_escanteios": limiar if 'limiar' in locals() else 8.5,
                        "home_crest": fixture.get("homeTeam", {}).get("crest", ""),
                        "away_crest": fixture.get("awayTeam", {}).get("crest", "")
                    }
                    
                    jogos_com_resultado.append(jogo_resultado)
                    alerta["conferido"] = True
                    resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar escanteios {fixture_id}: {e}")
    
    if jogos_com_resultado:
        if alerta_resultados:
            enviar_alerta_resultados_escanteios_poster(jogos_com_resultado)
        salvar_alertas_escanteios(alertas)
        st.success(f"✅ {resultados_enviados} resultados Escanteios processados!")
    else:
        st.info("ℹ️ Nenhum novo resultado Escanteios encontrado.")

# =============================
# FUNÇÕES DE POSTER PARA RESULTADOS - TODOS OS TIPOS
# =============================

def gerar_poster_resultados_ambas_marcam(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS AMBAS MARCAM") -> io.BytesIO:
    """Gera poster profissional com resultados Ambas Marcam"""
    return gerar_poster_resultados_generico(jogos, titulo, "ambas_marcam")

def gerar_poster_resultados_cartoes(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS CARTÕES") -> io.BytesIO:
    """Gera poster profissional com resultados de Cartões"""
    return gerar_poster_resultados_generico(jogos, titulo, "cartoes")

def gerar_poster_resultados_escanteios(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS ESCANTEIOS") -> io.BytesIO:
    """Gera poster profissional com resultados de Escanteios"""
    return gerar_poster_resultados_generico(jogos, titulo, "escanteios")

def gerar_poster_resultados_generico(jogos: list, titulo: str, tipo: str) -> io.BytesIO:
    """
    Gera poster profissional genérico para resultados de qualquer tipo
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 900
    PADDING = 80
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(60)
    FONTE_PLACAR = criar_fonte(80)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(55)
    FONTE_RESULTADO = criar_fonte(65)

    # === TOPO DO POSTER ===
    titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
    titulo_w = titulo_bbox[2] - titulo_bbox[0]
    draw.text(((LARGURA - titulo_w) // 2, 60), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 150), (3*LARGURA//4, 150)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # Cores baseadas no resultado
        if jogo['previsao_correta']:
            cor_borda = (76, 175, 80)  # VERDE
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)  # VERMELHO
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda colorida
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=5)

        # BADGE RESULTADO (GREEN/RED)
        badge_text = texto_resultado
        badge_bg_color = cor_resultado
        
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 40
            badge_h = 80
            badge_x = x1 - badge_w - 20
            badge_y = y0 + 20
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=badge_bg_color, outline=badge_bg_color)
            draw.text((badge_x + 20, badge_y + 10), badge_text, font=FONTE_RESULTADO, fill=(255, 255, 255))
        except:
            pass

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 30), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            pass

        # Times e placar
        home_text = jogo['home'][:18]
        away_text = jogo['away'][:18]
        
        # ESCUDOS
        TAMANHO_ESCUDO = 180
        TAMANHO_QUADRADO = 200
        ESPACO_ENTRE_ESCUDOS = 600
        
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2
        y_escudos = y0 + 100

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS

        # Desenhar escudos
        escudo_home = baixar_imagem_url(jogo.get('home_crest', ''))
        escudo_away = baixar_imagem_url(jogo.get('away_crest', ''))
        
        def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(255, 255, 255), outline=(200, 200, 200), width=2)
            if logo_img:
                try:
                    logo_img = logo_img.convert("RGBA")
                    ratio = min(tamanho_escudo/logo_img.width, tamanho_escudo/logo_img.height)
                    nova_largura = int(logo_img.width * ratio)
                    nova_altura = int(logo_img.height * ratio)
                    logo_img = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                    pos_x = x + (tamanho_quadrado - nova_largura) // 2
                    pos_y = y + (tamanho_quadrado - nova_altura) // 2
                    img.paste(logo_img, (pos_x, pos_y), logo_img)
                except Exception as e:
                    print(f"Erro ao processar escudo: {e}")
                    draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                    draw.text((x + 40, y + 50), "ERR", font=FONTE_INFO, fill=(255, 255, 255))
            else:
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 40, y + 50), "?", font=FONTE_INFO, fill=(255, 255, 255))

        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        # PLACAR CENTRAL
        placar_text = f"{jogo['home_goals']}  x  {jogo['away_goals']}" if tipo == "ambas_marcam" else f"{jogo.get('cartoes_total', jogo.get('escanteios_total', 0))}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - placar_w) // 2
            placar_y = y_escudos + TAMANHO_QUADRADO//2 - 30
            draw.text((placar_x, placar_y), placar_text, font=FONTE_PLACAR, fill=(255, 215, 0))
        except:
            pass

        # INFORMAÇÕES DA PREVISÃO
        y_info = y_escudos + TAMANHO_QUADRADO + 120

        # Textos específicos por tipo
        if tipo == "ambas_marcam":
            textos = [
                f"Previsão: {jogo['previsao']}",
                f"Probabilidade: {jogo['probabilidade_prevista']:.1f}%",
                f"Confiança: {jogo['confianca_prevista']:.0f}%",
                f"Ambas Marcaram: {'SIM' if jogo['ambas_marcaram'] else 'NÃO'}"
            ]
        elif tipo == "cartoes":
            textos = [
                f"Previsão: {jogo['previsao']}",
                f"Estimativa: {jogo['estimativa_prevista']:.1f} cartões",
                f"Confiança: {jogo['confianca_prevista']:.0f}%",
                f"Cartões Totais: {jogo['cartoes_total']}"
            ]
        else:  # escanteios
            textos = [
                f"Previsão: {jogo['previsao']}",
                f"Estimativa: {jogo['estimativa_prevista']:.1f} escanteios",
                f"Confiança: {jogo['confianca_prevista']:.0f}%",
                f"Escanteios Totais: {jogo['escanteios_total']}"
            ]

        for i, texto in enumerate(textos):
            try:
                texto_bbox = draw.textbbox((0, 0), texto, font=FONTE_INFO)
                texto_w = texto_bbox[2] - texto_bbox[0]
                draw.text(((LARGURA - texto_w) // 2, y_info + i * 45), texto, font=FONTE_INFO, fill=(255, 255, 255))
            except:
                pass

        # ANÁLISE DO RESULTADO
        y_analise = y_info + len(textos) * 45 + 20
        analise_text = "✅ PREVISÃO CORRETA!" if jogo['previsao_correta'] else "❌ PREVISÃO INCORRETA"
        cor_analise = (76, 175, 80) if jogo['previsao_correta'] else (244, 67, 54)

        try:
            analise_bbox = draw.textbbox((0, 0), analise_text, font=FONTE_ANALISE)
            analise_w = analise_bbox[2] - analise_bbox[0]
            draw.text(((LARGURA - analise_w) // 2, y_analise), analise_text, font=FONTE_ANALISE, fill=cor_analise)
        except:
            pass

        # Linha separadora entre jogos (exceto último)
        if idx < len(jogos) - 1:
            draw.line([(x0 + 50, y1), (x1 - 50, y1)], fill=(100, 130, 160), width=2)

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • Resultados Oficiais • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        pass

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados {tipo} gerado com {len(jogos)} jogos")
    return buffer

# =============================
# SISTEMA DE CONFERÊNCIA PARA ALERTAS COMPOSTOS
# =============================

def verificar_resultados_alertas_compostos(alerta_resultados: bool):
    """Verifica resultados dos alertas compostos salvos"""
    st.info("🔍 Verificando resultados de alertas compostos...")
    
    alertas = carregar_alertas_compostos()
    if not alertas:
        st.info("ℹ️ Nenhum alerta composto salvo para verificar.")
        return False
    
    alertas_conferidos = 0
    alertas_com_resultados = []
    
    for alerta_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        jogos_alerta = alerta.get("jogos", [])
        todos_jogos_conferidos = True
        algum_jogo_atualizado = False
        
        for jogo_salvo in jogos_alerta:
            if jogo_salvo.get("conferido", False):
                continue
                
            fixture_id = jogo_salvo.get("fixture_id")
            if not fixture_id:
                continue
                
            try:
                url = f"{BASE_URL_FD}/matches/{fixture_id}"
                fixture = obter_dados_api_com_rate_limit(url)
                
                if not fixture:
                    todos_jogos_conferidos = False
                    continue
                    
                status = fixture.get("status", "")
                score = fixture.get("score", {}).get("fullTime", {})
                home_goals = score.get("home", 0)
                away_goals = score.get("away", 0)
                
                if status == "FINISHED" and home_goals is not None and away_goals is not None:
                    total_gols = home_goals + away_goals
                    
                    # Determinar se previsão foi correta
                    previsao_correta = False
                    if jogo_salvo['tendencia'] == "Mais 2.5" and total_gols > 2.5:
                        previsao_correta = True
                    elif jogo_salvo['tendencia'] == "Mais 1.5" and total_gols > 1.5:
                        previsao_correta = True
                    elif jogo_salvo['tendencia'] == "Menos 2.5" and total_gols < 2.5:
                        previsao_correta = True
                    
                    # Atualizar jogo salvo
                    jogo_salvo["conferido"] = True
                    jogo_salvo["resultado"] = "GREEN" if previsao_correta else "RED"
                    jogo_salvo["placar_final"] = f"{home_goals}-{away_goals}"
                    jogo_salvo["previsao_correta"] = previsao_correta
                    algum_jogo_atualizado = True
                    
                    st.info(f"✅ Jogo conferido: {jogo_salvo['home']} vs {jogo_salvo['away']} - {jogo_salvo['resultado']}")
                    
                else:
                    todos_jogos_conferidos = False
                    st.info(f"⏳ Jogo pendente: {jogo_salvo['home']} vs {jogo_salvo['away']} - Status: {status}")
                    
            except Exception as e:
                st.error(f"❌ Erro ao verificar jogo {fixture_id}: {e}")
                todos_jogos_conferidos = False
        
        # Se todos os jogos deste alerta foram conferidos, marcar o alerta como conferido
        if todos_jogos_conferidos:
            alerta["conferido"] = True
            
            # Calcular estatísticas do alerta
            jogos_conferidos = [j for j in jogos_alerta if j.get("conferido", False)]
            if jogos_conferidos:
                total_jogos = len(jogos_conferidos)
                green_count = sum(1 for j in jogos_conferidos if j.get("resultado") == "GREEN")
                taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
                
                alerta["estatisticas"] = {
                    "total_jogos": total_jogos,
                    "green_count": green_count,
                    "red_count": total_jogos - green_count,
                    "taxa_acerto": taxa_acerto,
                    "data_conferencia": datetime.now().isoformat()
                }
            
            alertas_conferidos += 1
            alertas_com_resultados.append((alerta_id, alerta))
            st.success(f"🎯 Alerta composto {alerta_id} totalmente conferido!")
        
        # Se houve algum jogo atualizado, salvar as alterações
        if algum_jogo_atualizado:
            alerta["jogos"] = jogos_alerta
            salvar_alertas_compostos(alertas)
            st.info(f"💾 Alterações salvas para alerta {alerta_id}")
    
    # ENVIO DE ALERTAS DE RESULTADOS COMPOSTOS
    resultados_enviados = 0
    if alertas_com_resultados and alerta_resultados:
        st.info(f"🎯 Enviando {len(alertas_com_resultados)} alertas de resultados compostos...")
        
        for alerta_id, alerta_data in alertas_com_resultados:
            try:
                if enviar_alerta_composto_resultados_poster(alerta_id, alerta_data):
                    st.success(f"✅ Alerta de resultados compostos enviado: {alerta_id}")
                    resultados_enviados += 1
                else:
                    st.error(f"❌ Falha ao enviar alerta de resultados compostos: {alerta_id}")
            except Exception as e:
                st.error(f"❌ Erro ao enviar alerta {alerta_id}: {e}")
                
        if resultados_enviados > 0:
            st.success(f"🚀 {resultados_enviados} alertas de resultados compostos enviados!")
    
    elif alertas_com_resultados:
        st.info(f"ℹ️ {len(alertas_com_resultados)} alertas compostos prontos para resultados, mas envio desativado")
    
    if alertas_conferidos > 0:
        st.success(f"✅ {alertas_conferidos} alertas compostos totalmente conferidos!")
    
    return resultados_enviados > 0

def enviar_alerta_composto_resultados_poster(alerta_id: str, alerta_data: dict):
    """Envia alerta composto de RESULTS com poster para o Telegram"""
    try:
        jogos = alerta_data.get("jogos", [])
        if not jogos:
            st.warning(f"⚠️ Nenhum jogo no alerta composto {alerta_id}")
            return False

        # Filtrar apenas jogos conferidos com resultados
        jogos_com_resultado = [j for j in jogos if j.get("conferido", False) and j.get("placar_final") is not None]
        
        if not jogos_com_resultado:
            st.warning(f"⚠️ Nenhum resultado final no alerta composto {alerta_id}")
            return False

        # Agrupar por data do jogo
        jogos_por_data = {}
        for jogo in jogos_com_resultado:
            try:
                data_jogo = datetime.fromisoformat(jogo.get("data_jogo", "")).date()
                if data_jogo not in jogos_por_data:
                    jogos_por_data[data_jogo] = []
                jogos_por_data[data_jogo].append(jogo)
            except:
                continue

        enviados = 0
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - RESULTADOS COMPOSTOS {data_str}"
            
            st.info(f"🎨 Gerando poster de RESULTADOS compostos para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_resultados_compostos_com_escudos(jogos_data, titulo=titulo)
            
            # Calcular estatísticas do alerta composto
            stats_alerta = alerta_data.get("estatisticas", {})
            total_jogos = stats_alerta.get("total_jogos", len(jogos_data))
            green_count = stats_alerta.get("green_count", sum(1 for j in jogos_data if j.get("resultado") == "GREEN"))
            taxa_acerto = stats_alerta.get("taxa_acerto", (green_count / total_jogos * 100) if total_jogos > 0 else 0)
            
            caption = (
                f"<b>🏁 RESULTADOS OFICIAIS - ALERTA COMPOSTO</b>\n\n"
                f"<b>📅 DATA DOS JOGOS: {data_str}</b>\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {total_jogos - green_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO DO SISTEMA COMPOSTO:</b>\n"
                f"<b>• Análise Preditiva Avançada</b>\n"
                f"<b>• Resultados em Tempo Real</b>\n"
                f"<b>• Precisão Comprovada</b>\n\n"
                f"<b>🔥 ELITE MASTER - SISTEMA COMPOSTO VERIFICADO</b>"
            )
            
            st.info("📤 Enviando poster de RESULTADOS compostos para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                st.success(f"🚀 Poster de RESULTADOS compostos enviado para {data_str}!")
                
                # Registrar no histórico de compostos
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tendencia": jogo["tendencia"],
                        "estimativa": jogo["estimativa"],
                        "confianca": jogo["confianca"],
                        "placar": jogo["placar_final"],
                        "resultado": "🟢 GREEN" if jogo.get("resultado") == "GREEN" else "🔴 RED",
                        "alerta_id": alerta_id
                    }, "compostos")
                
                enviados += 1
            else:
                st.error(f"❌ Falha ao enviar poster de resultados compostos para {data_str}")
                
        return enviados > 0
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados compostos: {str(e)}")
        return False

def gerar_poster_resultados_compostos_com_escudos(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS COMPOSTOS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais dos alertas compostos
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 900
    PADDING = 80
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(60)
    FONTE_PLACAR = criar_fonte(80)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(55)
    FONTE_RESULTADO = criar_fonte(65)

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 60), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 60), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 150), (3*LARGURA//4, 150)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # Cores baseadas no resultado
        if jogo.get('resultado') == "GREEN":
            cor_borda = (76, 175, 80)  # VERDE
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)  # VERMELHO
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda colorida
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=5)

        # BADGE RESULTADO (GREEN/RED)
        badge_text = texto_resultado
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 40
            badge_h = 80
            badge_x = x1 - badge_w - 20
            badge_y = y0 + 20
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=cor_resultado, outline=cor_resultado)
            draw.text((badge_x + 20, badge_y + 10), badge_text, font=FONTE_RESULTADO, fill=(255, 255, 255))
        except:
            pass

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 30), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            pass

        # Times e placar
        home_text = jogo['home'][:18]
        away_text = jogo['away'][:18]
        
        # ESCUDOS
        TAMANHO_ESCUDO = 180
        TAMANHO_QUADRADO = 200
        ESPACO_ENTRE_ESCUDOS = 600
        
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2
        y_escudos = y0 + 100

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS

        # Desenhar escudos
        escudo_home = baixar_imagem_url(jogo.get('home_crest', ''))
        escudo_away = baixar_imagem_url(jogo.get('away_crest', ''))
        
        def desenhar_escudo_resultado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(255, 255, 255), outline=(200, 200, 200), width=2)
            if logo_img:
                try:
                    logo_img = logo_img.convert("RGBA")
                    ratio = min(tamanho_escudo/logo_img.width, tamanho_escudo/logo_img.height)
                    nova_largura = int(logo_img.width * ratio)
                    nova_altura = int(logo_img.height * ratio)
                    logo_img = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                    pos_x = x + (tamanho_quadrado - nova_largura) // 2
                    pos_y = y + (tamanho_quadrado - nova_altura) // 2
                    img.paste(logo_img, (pos_x, pos_y), logo_img)
                except Exception as e:
                    print(f"Erro ao processar escudo: {e}")
                    draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                    draw.text((x + 40, y + 50), "ERR", font=FONTE_INFO, fill=(255, 255, 255))
            else:
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 40, y + 50), "?", font=FONTE_INFO, fill=(255, 255, 255))

        desenhar_escudo_resultado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_resultado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        # PLACAR CENTRAL
        placar_text = jogo.get('placar_final', '0-0')
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - placar_w) // 2
            placar_y = y_escudos + TAMANHO_QUADRADO//2 - 30
            draw.text((placar_x, placar_y), placar_text, font=FONTE_PLACAR, fill=(255, 215, 0))
        except:
            pass

        # INFORMAÇÕES DA PREVISÃO
        y_info = y_escudos + TAMANHO_QUADRADO + 120

        textos = [
            f"Previsão: {jogo['tendencia']}",
            f"Estimativa: {jogo['estimativa']:.1f} gols",
            f"Confiança: {jogo['confianca']:.0f}%",
            f"Resultado: {texto_resultado}"
        ]

        for i, texto in enumerate(textos):
            try:
                texto_bbox = draw.textbbox((0, 0), texto, font=FONTE_INFO)
                texto_w = texto_bbox[2] - texto_bbox[0]
                draw.text(((LARGURA - texto_w) // 2, y_info + i * 45), texto, font=FONTE_INFO, fill=(255, 255, 255))
            except:
                pass

        # ANÁLISE DO RESULTADO
        y_analise = y_info + len(textos) * 45 + 20
        analise_text = "✅ PREVISÃO CORRETA!" if jogo.get('previsao_correta') else "❌ PREVISÃO INCORRETA"
        cor_analise = (76, 175, 80) if jogo.get('previsao_correta') else (244, 67, 54)

        try:
            analise_bbox = draw.textbbox((0, 0), analise_text, font=FONTE_ANALISE)
            analise_w = analise_bbox[2] - analise_bbox[0]
            draw.text(((LARGURA - analise_w) // 2, y_analise), analise_text, font=FONTE_ANALISE, fill=cor_analise)
        except:
            pass

        # Linha separadora entre jogos (exceto último)
        if idx < len(jogos) - 1:
            draw.line([(x0 + 50, y1), (x1 - 50, y1)], fill=(100, 130, 160), width=2)

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • Resultados Compostos • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        pass

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados compostos gerado com {len(jogos)} jogos")
    return buffer

# =============================
# FUNÇÕES DE ENVIO DE ALERTAS DE RESULTADOS
# =============================

def enviar_alerta_resultados_poster(jogos_com_resultado: list):
    """Envia alerta de resultados com poster para o Telegram"""
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
            jogos_por_data[data_jogo].append(jogo)

        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - RESULTADOS {data_str}"
            
            st.info(f"🎨 Gerando poster de resultados para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_resultados_com_escudos(jogos_data, titulo=titulo)
            
            # Calcular estatísticas
            total_jogos = len(jogos_data)
            green_count = 0
            for jogo in jogos_data:
                total_gols = jogo['home_goals'] + jogo['away_goals']
                if ((jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5) or 
                    (jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5) or
                    (jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5)):
                    green_count += 1
            
            red_count = total_jogos - green_count
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            caption = (
                f"<b>🏁 RESULTADOS OFICIAIS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {red_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO DO SISTEMA:</b>\n"
                f"<b>• Análise Preditiva Avançada</b>\n"
                f"<b>• Resultados em Tempo Real</b>\n"
                f"<b>• Precisão Comprovada</b>\n\n"
                f"<b>🔥 ELITE MASTER SYSTEM - CONFIABILIDADE COMPROVADA</b>"
            )
            
            st.info("📤 Enviando resultados para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                st.success(f"🚀 Poster de resultados enviado para {data_str}!")
                
                # Registrar no histórico
                for jogo in jogos_data:
                    total_gols = jogo['home_goals'] + jogo['away_goals']
                    resultado = "🟢 GREEN" if ((jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5) or 
                                    (jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5) or
                                    (jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5)) else "🔴 RED"
                    
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tendencia": jogo["tendencia_prevista"],
                        "estimativa": jogo["estimativa_prevista"],
                        "confianca": jogo["confianca_prevista"],
                        "placar": f"{jogo['home_goals']}x{jogo['away_goals']}",
                        "resultado": resultado
                    })
            else:
                st.error(f"❌ Falha ao enviar poster de resultados para {data_str}")
                
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        # Fallback para mensagem de texto
        enviar_alerta_resultados_texto(jogos_com_resultado)

def enviar_alerta_resultados_texto(jogos_com_resultado: list):
    """Fallback para envio de resultados em texto"""
    try:
        msg = "<b>🏁 RESULTADOS OFICIAIS - SISTEMA RED/GREEN</b>\n\n"
        
        for jogo in jogos_com_resultado[:10]:  # Limitar a 10 jogos
            total_gols = jogo['home_goals'] + jogo['away_goals']
            resultado = "🟢 GREEN" if ((jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5) or 
                            (jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5) or
                            (jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5)) else "🔴 RED"
            
            msg += (
                f"{resultado} <b>{jogo['home']}</b> {jogo['home_goals']}x{jogo['away_goals']} <b>{jogo['away']}</b>\n"
                f"Previsão: {jogo['tendencia_prevista']} | Conf: {jogo['confianca_prevista']:.0f}%\n\n"
            )
        
        msg += "<b>🔥 ELITE MASTER SYSTEM - RESULTADOS OFICIAIS</b>"
        
        return enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
    except Exception as e:
        st.error(f"❌ Erro no fallback de texto para resultados: {e}")
        return False

def gerar_poster_resultados_com_escudos(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais (versão com escudos)
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 900
    PADDING = 80
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(90)
    FONTE_SUBTITULO = criar_fonte(65)
    FONTE_TIMES = criar_fonte(60)
    FONTE_PLACAR = criar_fonte(80)
    FONTE_INFO = criar_fonte(45)
    FONTE_ANALISE = criar_fonte(55)
    FONTE_RESULTADO = criar_fonte(65)

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 60), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 60), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 150), (3*LARGURA//4, 150)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        total_gols = jogo['home_goals'] + jogo['away_goals']
        
        # Cores baseadas no resultado
        if ((jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5) or 
            (jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5) or
            (jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5)):
            cor_borda = (76, 175, 80)  # VERDE
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)  # VERMELHO
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda colorida
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=5)

        # BADGE RESULTADO (GREEN/RED)
        badge_text = texto_resultado
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 40
            badge_h = 80
            badge_x = x1 - badge_w - 20
            badge_y = y0 + 20
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=cor_resultado, outline=cor_resultado)
            draw.text((badge_x + 20, badge_y + 10), badge_text, font=FONTE_RESULTADO, fill=(255, 255, 255))
        except:
            pass

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 30), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            pass

        # Times e placar
        home_text = jogo['home'][:18]
        away_text = jogo['away'][:18]
        
        # ESCUDOS
        TAMANHO_ESCUDO = 180
        TAMANHO_QUADRADO = 200
        ESPACO_ENTRE_ESCUDOS = 600
        
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2
        y_escudos = y0 + 100

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS

        # Desenhar escudos
        escudo_home = baixar_imagem_url(jogo.get('home_crest', ''))
        escudo_away = baixar_imagem_url(jogo.get('away_crest', ''))
        
        def desenhar_escudo_poster(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(255, 255, 255), outline=(200, 200, 200), width=2)
            if logo_img:
                try:
                    logo_img = logo_img.convert("RGBA")
                    ratio = min(tamanho_escudo/logo_img.width, tamanho_escudo/logo_img.height)
                    nova_largura = int(logo_img.width * ratio)
                    nova_altura = int(logo_img.height * ratio)
                    logo_img = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                    pos_x = x + (tamanho_quadrado - nova_largura) // 2
                    pos_y = y + (tamanho_quadrado - nova_altura) // 2
                    img.paste(logo_img, (pos_x, pos_y), logo_img)
                except Exception as e:
                    print(f"Erro ao processar escudo: {e}")
                    draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                    draw.text((x + 40, y + 50), "ERR", font=FONTE_INFO, fill=(255, 255, 255))
            else:
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 40, y + 50), "?", font=FONTE_INFO, fill=(255, 255, 255))

        desenhar_escudo_poster(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_poster(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 20),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            pass

        # PLACAR CENTRAL
        placar_text = f"{jogo['home_goals']}  x  {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - placar_w) // 2
            placar_y = y_escudos + TAMANHO_QUADRADO//2 - 30
            draw.text((placar_x, placar_y), placar_text, font=FONTE_PLACAR, fill=(255, 215, 0))
        except:
            pass

        # INFORMAÇÕES DA PREVISÃO
        y_info = y_escudos + TAMANHO_QUADRADO + 120

        textos = [
            f"Previsão: {jogo['tendencia_prevista']}",
            f"Estimativa: {jogo['estimativa_prevista']:.1f} gols",
            f"Confiança: {jogo['confianca_prevista']:.0f}%",
            f"Resultado: {texto_resultado}"
        ]

        for i, texto in enumerate(textos):
            try:
                texto_bbox = draw.textbbox((0, 0), texto, font=FONTE_INFO)
                texto_w = texto_bbox[2] - texto_bbox[0]
                draw.text(((LARGURA - texto_w) // 2, y_info + i * 45), texto, font=FONTE_INFO, fill=(255, 255, 255))
            except:
                pass

        # ANÁLISE DO RESULTADO
        y_analise = y_info + len(textos) * 45 + 20
        analise_text = f"Total de Gols: {total_gols} | Previsão: {jogo['tendencia_prevista']}"
        cor_analise = (255, 215, 0)

        try:
            analise_bbox = draw.textbbox((0, 0), analise_text, font=FONTE_ANALISE)
            analise_w = analise_bbox[2] - analise_bbox[0]
            draw.text(((LARGURA - analise_w) // 2, y_analise), analise_text, font=FONTE_ANALISE, fill=cor_analise)
        except:
            pass

        # Linha separadora entre jogos (exceto último)
        if idx < len(jogos) - 1:
            draw.line([(x0 + 50, y1), (x1 - 50, y1)], fill=(100, 130, 160), width=2)

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"ELITE MASTER SYSTEM • Resultados Oficiais • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        pass

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de resultados gerado com {len(jogos)} jogos")
    return buffer

# =============================
# ALERTAS TELEGRAM ORIGINAIS
# =============================

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float) -> bool:
    """Envia alerta individual para o Telegram - CORRIGIDA"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    
    # CORREÇÃO: Usar a função formatar_data_iso corrigida
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    
    msg = (
        f"<b>🎯 ALERTA ELITE MASTER</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>📈 Tendência: {tendencia}</b>\n"
        f"<b>⚽ Estimativa: {estimativa:.1f} gols</b>\n"
        f"<b>🎯 Confiança: {confianca:.0f}%</b>\n\n"
        f"<b>🔥 ELITE MASTER - ANÁLISE CONFIÁVEL</b>"
    )
    
    return enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

# =============================
# NOVA FUNÇÃO DE DEBUG PARA API
# =============================

def debug_api_connection():
    """Função para debug da conexão com a API"""
    st.header("🔧 Debug da Conexão API")
    
    # Testar conexão básica
    test_url = f"{BASE_URL_FD}/competitions/PL"  # Premier League
    st.write(f"Testando URL: {test_url}")
    
    response = obter_dados_api_com_rate_limit(test_url)
    if response:
        st.success("✅ Conexão com API bem-sucedida!")
        st.json(response.get("name", "Resposta recebida"))
    else:
        st.error("❌ Falha na conexão com API")
        
    # Testar obtenção de jogos
    st.subheader("Teste de Obtenção de Jogos")
    hoje = datetime.now().strftime("%Y-%m-%d")
    jogos_pl = obter_jogos("PL", hoje)
    st.write(f"Jogos encontrados para hoje: {len(jogos_pl)}")
    
    for jogo in jogos_pl[:3]:  # Mostrar apenas os 3 primeiros
        st.write(f"- {jogo.get('homeTeam', {}).get('name', 'N/A')} vs {jogo.get('awayTeam', {}).get('name', 'N/A')}")

# =============================
# INTERFACE PRINCIPAL STREAMLIT
# =============================

def main():
    st.set_page_config(
        page_title="ELITE MASTER - Sistema de Previsão de Futebol",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("⚽ ELITE MASTER - Sistema Avançado de Previsão de Futebol")
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Seleção de data
        data_selecionada = st.date_input("📅 Selecione a data", datetime.now())
        data_str = data_selecionada.strftime("%Y-%m-%d")
        
        # Seleção de ligas
        ligas_selecionadas = st.multiselect(
            "🏆 Selecione as ligas",
            options=list(LIGA_DICT.keys()),
            default=list(LIGA_DICT.keys())[:3]
        )
        
        # Thresholds para alertas
        st.subheader("🎯 Limiares de Confiança")
        threshold_gols = st.slider("Limiar Gols (%)", 50, 90, 65)
        threshold_ambas_marcam = st.slider("Limiar Ambas Marcam (%)", 50, 90, 60)
        threshold_cartoes = st.slider("Limiar Cartões (%)", 50, 90, 55)
        threshold_escanteios = st.slider("Limiar Escanteios (%)", 50, 90, 50)
        
        # Configurações de alertas
        st.subheader("🔔 Configurações de Alertas")
        alerta_individual = st.checkbox("Enviar alertas individuais", value=False)
        alerta_composto = st.checkbox("Enviar alertas compostos", value=True)
        alerta_composto_avancado = st.checkbox("Enviar alertas compostos avançados", value=True)
        alerta_resultados = st.checkbox("Enviar alertas de resultados", value=True)
        
        # Botões de ação
        st.subheader("🛠️ Ações")
        if st.button("🔄 Verificar Resultados Finais"):
            verificar_resultados_finais_completo(alerta_resultados)
        
        if st.button("🧹 Limpar Históricos"):
            limpar_historico("todos")
        
        if st.button("🔄 Limpar Caches"):
            # Limpar caches temporários
            salvar_cache_jogos({})
            salvar_cache_classificacao({})
            salvar_cache_estatisticas({})
            salvar_cache_dados_historicos({})
            st.success("Caches limpos!")

    # Abas principais
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Previsão de Gols", 
        "🔄 Ambas Marcam", 
        "🟨 Cartões",
        "🔄 Escanteios",
        "🎯 Compostos Avançados",
        "📈 Históricos",
        "⚙️ Sistema"
    ])

    # TAB 1: PREVISÃO DE GOLS ORIGINAL
    with tab1:
        st.header("📊 Previsão de Gols - Sistema Original")
        
        if st.button("🎯 Analisar Jogos de Hoje - Gols", key="analisar_gols"):
            with st.spinner("🔍 Analisando jogos e gerando previsões..."):
                jogos_compostos = []
                
                for liga_nome in ligas_selecionadas:
                    liga_id = LIGA_DICT[liga_nome]
                    
                    st.subheader(f"🏆 {liga_nome}")
                    classificacao = obter_classificacao(liga_id)
                    
                    if not classificacao:
                        st.warning(f"⚠️ Não foi possível obter classificação para {liga_nome}")
                        continue
                    
                    jogos = obter_jogos(liga_id, data_str)
                    
                    if not jogos:
                        st.info(f"ℹ️ Nenhum jogo encontrado para {liga_nome} em {data_str}")
                        continue
                    
                    for fixture in jogos:
                        home = fixture["homeTeam"]["name"]
                        away = fixture["awayTeam"]["name"]
                        status = fixture["status"]
                        
                        if status != "SCHEDULED":
                            continue
                        
                        estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)
                        
                        if confianca >= threshold_gols:
                            # Formatar data e hora
                            data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
                            
                            # Coletar URLs dos escudos
                            home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                            away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
                            
                            jogo_info = {
                                "id": fixture["id"],
                                "home": home,
                                "away": away,
                                "liga": liga_nome,
                                "hora": datetime.fromisoformat(fixture["utcDate"].replace("Z", "+00:00")),
                                "data_formatada": data_formatada,
                                "hora_formatada": hora_formatada,
                                "tendencia": tendencia,
                                "estimativa": estimativa,
                                "confianca": confianca,
                                "home_crest": home_crest,
                                "away_crest": away_crest
                            }
                            
                            jogos_compostos.append(jogo_info)
                            
                            # Exibir no Streamlit
                            col1, col2, col3 = st.columns([3, 1, 2])
                            with col1:
                                st.write(f"**{home}** vs **{away}**")
                                st.write(f"🕒 {hora_formatada} BRT | 📅 {data_formatada}")
                            with col2:
                                st.metric("Estimativa", f"{estimativa:.1f}")
                            with col3:
                                st.metric("Confiança", f"{confianca:.0f}%")
                                st.success(f"**{tendencia}**")
                            
                            # Verificar e enviar alerta individual
                            verificar_enviar_alerta(fixture, tendencia, estimativa, confianca, alerta_individual)
                
                # Enviar alerta composto se habilitado
                if alerta_composto and jogos_compostos:
                    if st.button("🚀 Enviar Alerta Composto - Gols", key="enviar_composto_gols"):
                        enviar_alerta_composto_poster(jogos_compostos, threshold_gols)
                elif not jogos_compostos:
                    st.info("ℹ️ Nenhum jogo atingiu o limiar de confiança para alertas compostos de gols.")

    # TAB 2: AMBAS MARCAM
    with tab2:
        st.header("🔄 Previsão - Ambas as Equipes Marcam")
        
        if st.button("🎯 Analisar Ambas Marcam", key="analisar_ambas_marcam"):
            with st.spinner("🔍 Analisando probabilidade de ambas marcarem..."):
                for liga_nome in ligas_selecionadas:
                    liga_id = LIGA_DICT[liga_nome]
                    
                    st.subheader(f"🏆 {liga_nome}")
                    classificacao = obter_classificacao(liga_id)
                    
                    if not classificacao:
                        st.warning(f"⚠️ Não foi possível obter classificação para {liga_nome}")
                        continue
                    
                    jogos = obter_jogos(liga_id, data_str)
                    
                    if not jogos:
                        st.info(f"ℹ️ Nenhum jogo encontrado para {liga_nome} em {data_str}")
                        continue
                    
                    for fixture in jogos:
                        home = fixture["homeTeam"]["name"]
                        away = fixture["awayTeam"]["name"]
                        status = fixture["status"]
                        
                        if status != "SCHEDULED":
                            continue
                        
                        probabilidade, confianca, tendencia = calcular_previsao_ambas_marcam_real(home, away, classificacao)
                        
                        if confianca >= threshold_ambas_marcam:
                            # Formatar data e hora
                            data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
                            
                            col1, col2, col3 = st.columns([3, 1, 2])
                            with col1:
                                st.write(f"**{home}** vs **{away}**")
                                st.write(f"🕒 {hora_formatada} BRT | 📅 {data_formatada}")
                            with col2:
                                st.metric("Probabilidade", f"{probabilidade:.1f}%")
                            with col3:
                                st.metric("Confiança", f"{confianca:.0f}%")
                                st.success(f"**{tendencia}**")
                            
                            # Verificar e enviar alerta individual
                            verificar_enviar_alerta_ambas_marcam(fixture, probabilidade, confianca, tendencia, alerta_individual)

    # TAB 3: CARTÕES
    with tab3:
        st.header("🟨 Previsão - Total de Cartões")
        
        if st.button("🎯 Analisar Total de Cartões", key="analisar_cartoes"):
            with st.spinner("🔍 Analisando estatísticas de cartões..."):
                for liga_nome in ligas_selecionadas:
                    liga_id = LIGA_DICT[liga_nome]
                    
                    st.subheader(f"🏆 {liga_nome}")
                    
                    jogos = obter_jogos(liga_id, data_str)
                    
                    if not jogos:
                        st.info(f"ℹ️ Nenhum jogo encontrado para {liga_nome} em {data_str}")
                        continue
                    
                    for fixture in jogos:
                        home_team = fixture["homeTeam"]
                        away_team = fixture["awayTeam"]
                        status = fixture["status"]
                        
                        if status != "SCHEDULED":
                            continue
                        
                        estimativa, confianca, tendencia = calcular_previsao_cartoes_real(home_team, away_team, liga_id)
                        
                        if confianca >= threshold_cartoes:
                            # Formatar data e hora
                            data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
                            
                            col1, col2, col3 = st.columns([3, 1, 2])
                            with col1:
                                st.write(f"**{home_team['name']}** vs **{away_team['name']}**")
                                st.write(f"🕒 {hora_formatada} BRT | 📅 {data_formatada}")
                            with col2:
                                st.metric("Estimativa", f"{estimativa:.1f}")
                            with col3:
                                st.metric("Confiança", f"{confianca:.0f}%")
                                st.success(f"**{tendencia}**")
                            
                            # Verificar e enviar alerta individual
                            verificar_enviar_alerta_cartoes(fixture, estimativa, confianca, tendencia, alerta_individual)

    # TAB 4: ESCANTEIOS
    with tab4:
        st.header("🔄 Previsão - Total de Escanteios")
        
        if st.button("🎯 Analisar Total de Escanteios", key="analisar_escanteios"):
            with st.spinner("🔍 Analisando estatísticas de escanteios..."):
                for liga_nome in ligas_selecionadas:
                    liga_id = LIGA_DICT[liga_nome]
                    
                    st.subheader(f"🏆 {liga_nome}")
                    
                    jogos = obter_jogos(liga_id, data_str)
                    
                    if not jogos:
                        st.info(f"ℹ️ Nenhum jogo encontrado para {liga_nome} em {data_str}")
                        continue
                    
                    for fixture in jogos:
                        home_team = fixture["homeTeam"]
                        away_team = fixture["awayTeam"]
                        status = fixture["status"]
                        
                        if status != "SCHEDULED":
                            continue
                        
                        estimativa, confianca, tendencia = calcular_previsao_escanteios_real(home_team, away_team, liga_id)
                        
                        if confianca >= threshold_escanteios:
                            # Formatar data e hora
                            data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
                            
                            col1, col2, col3 = st.columns([3, 1, 2])
                            with col1:
                                st.write(f"**{home_team['name']}** vs **{away_team['name']}**")
                                st.write(f"🕒 {hora_formatada} BRT | 📅 {data_formatada}")
                            with col2:
                                st.metric("Estimativa", f"{estimativa:.1f}")
                            with col3:
                                st.metric("Confiança", f"{confianca:.0f}%")
                                st.success(f"**{tendencia}**")
                            
                            # Verificar e enviar alerta individual
                            verificar_enviar_alerta_escanteios(fixture, estimativa, confianca, tendencia, alerta_individual)

    # TAB 5: COMPOSTOS AVANÇADOS
    with tab5:
        st.header("🎯 Sistema de Alertas Compostos Avançados")
        st.info("Sistema que combina múltiplas previsões (Ambas Marcam, Cartões, Escanteios) em um único alerta composto.")
        
        if st.button("🚀 Executar Análise Composta Avançada", key="analise_composta_avancada"):
            with st.spinner("🔍 Executando análise composta avançada..."):
                jogos_compostos_avancados = []
                
                for liga_nome in ligas_selecionadas:
                    liga_id = LIGA_DICT[liga_nome]
                    
                    st.subheader(f"🏆 {liga_nome}")
                    classificacao = obter_classificacao(liga_id)
                    
                    if not classificacao:
                        st.warning(f"⚠️ Não foi possível obter classificação para {liga_nome}")
                        continue
                    
                    jogos = obter_jogos(liga_id, data_str)
                    
                    if not jogos:
                        st.info(f"ℹ️ Nenhum jogo encontrado para {liga_nome} em {data_str}")
                        continue
                    
                    for fixture in jogos:
                        home_team = fixture["homeTeam"]
                        away_team = fixture["awayTeam"]
                        status = fixture["status"]
                        
                        if status != "SCHEDULED":
                            continue
                        
                        home_name = home_team["name"]
                        away_name = away_team["name"]
                        
                        # Coletar todas as previsões para este jogo
                        previsoes_jogo = []
                        
                        # 1. Previsão Ambas Marcam
                        probabilidade_ambas, confianca_ambas, tendencia_ambas = calcular_previsao_ambas_marcam_real(
                            home_name, away_name, classificacao
                        )
                        if confianca_ambas >= threshold_ambas_marcam:
                            previsoes_jogo.append({
                                "tipo": "Ambas Marcam",
                                "tendencia": tendencia_ambas,
                                "estimativa": probabilidade_ambas,
                                "confianca": confianca_ambas
                            })
                        
                        # 2. Previsão Cartões
                        estimativa_cartoes, confianca_cartoes, tendencia_cartoes = calcular_previsao_cartoes_real(
                            home_team, away_team, liga_id
                        )
                        if confianca_cartoes >= threshold_cartoes:
                            previsoes_jogo.append({
                                "tipo": "Cartões",
                                "tendencia": tendencia_cartoes,
                                "estimativa": estimativa_cartoes,
                                "confianca": confianca_cartoes
                            })
                        
                        # 3. Previsão Escanteios
                        estimativa_escanteios, confianca_escanteios, tendencia_escanteios = calcular_previsao_escanteios_real(
                            home_team, away_team, liga_id
                        )
                        if confianca_escanteios >= threshold_escanteios:
                            previsoes_jogo.append({
                                "tipo": "Escanteios",
                                "tendencia": tendencia_escanteios,
                                "estimativa": estimativa_escanteios,
                                "confianca": confianca_escanteios
                            })
                        
                        # Se temos pelo menos 2 previsões com boa confiança, incluir no composto avançado
                        if len(previsoes_jogo) >= 2:
                            # Formatar data e hora
                            data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
                            
                            # Coletar URLs dos escudos
                            home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                            away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
                            
                            jogo_avancado = {
                                "id": fixture["id"],
                                "home": home_name,
                                "away": away_name,
                                "liga": liga_nome,
                                "hora": datetime.fromisoformat(fixture["utcDate"].replace("Z", "+00:00")),
                                "data_formatada": data_formatada,
                                "hora_formatada": hora_formatada,
                                "previsoes": previsoes_jogo,
                                "home_crest": home_crest,
                                "away_crest": away_crest,
                                "fixture": fixture  # Manter fixture completo para referência
                            }
                            
                            jogos_compostos_avancados.append(jogo_avancado)
                            
                            # Exibir no Streamlit
                            st.success(f"🎯 **{home_name} vs {away_name}**")
                            st.write(f"🕒 {hora_formatada} BRT | 📅 {data_formatada}")
                            
                            for previsao in previsoes_jogo:
                                st.write(f"- {previsao['tipo']}: {previsao['tendencia']} (Conf: {previsao['confianca']:.0f}%)")
                
                # Enviar alerta composto avançado se habilitado
                if alerta_composto_avancado and jogos_compostos_avancados:
                    if st.button("🚀 Enviar Alerta Composto Avançado", key="enviar_composto_avancado"):
                        enviar_alerta_composto_avancado_poster(
                            jogos_compostos_avancados, 
                            threshold_ambas_marcam, 
                            threshold_cartoes, 
                            threshold_escanteios
                        )
                elif not jogos_compostos_avancados:
                    st.info("ℹ️ Nenhum jogo com múltiplas previsões de alta confiança encontrado.")

    # TAB 6: HISTÓRICOS
    with tab6:
        st.header("📈 Históricos e Estatísticas")
        
        historico_tipo = st.selectbox(
            "Selecione o tipo de histórico",
            ["gols", "ambas_marcam", "cartoes", "escanteios", "compostos", "compostos_avancados"]
        )
        
        caminhos_historico = {
            "gols": HISTORICO_PATH,
            "ambas_marcam": HISTORICO_AMBAS_MARCAM_PATH,
            "cartoes": HISTORICO_CARTOES_PATH,
            "escanteios": HISTORICO_ESCANTEIOS_PATH,
            "compostos": HISTORICO_COMPOSTOS_PATH,
            "compostos_avancados": HISTORICO_COMPOSTOS_AVANCADOS_PATH
        }
        
        historico = carregar_historico(caminhos_historico[historico_tipo])
        
        if historico:
            # Calcular estatísticas
            df = pd.DataFrame(historico)
            
            # Mostrar estatísticas básicas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de Registros", len(historico))
            
            with col2:
                if 'resultado' in df.columns:
                    green_count = df['resultado'].str.contains('GREEN').sum()
                    st.metric("Taxa de Acerto", f"{(green_count/len(df)*100):.1f}%")
            
            with col3:
                if 'confianca' in df.columns:
                    st.metric("Confiança Média", f"{df['confianca'].mean():.1f}%")
            
            # Mostrar tabela
            st.subheader("Registros Detalhados")
            st.dataframe(df.tail(20))  # Últimos 20 registros
            
            # Botão para limpar histórico específico
            if st.button(f"🧹 Limpar Histórico {historico_tipo}"):
                limpar_historico(historico_tipo)
                st.experimental_rerun()
        else:
            st.info(f"ℹ️ Nenhum registro no histórico de {historico_tipo}")

    # TAB 7: SISTEMA
    with tab7:
        st.header("⚙️ Status do Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Estatísticas do Sistema")
            
            # Verificar caches
            cache_jogos = carregar_cache_jogos()
            cache_classificacao = carregar_cache_classificacao()
            cache_estatisticas = carregar_cache_estatisticas()
            cache_dados_historicos = carregar_cache_dados_historicos()
            
            st.write(f"**Cache de Jogos:** {len(cache_jogos)} entradas")
            st.write(f"**Cache de Classificação:** {len(cache_classificacao)} ligas")
            st.write(f"**Cache de Estatísticas:** {len(cache_estatisticas)} partidas")
            st.write(f"**Cache de Dados Históricos:** {len(cache_dados_historicos)} times")
            
            # Verificar alertas ativos
            alertas_gols = carregar_alertas()
            alertas_ambas_marcam = carregar_alertas_ambas_marcam()
            alertas_cartoes = carregar_alertas_cartoes()
            alertas_escanteios = carregar_alertas_escanteios()
            alertas_compostos = carregar_alertas_compostos()
            alertas_compostos_avancados = carregar_alertas_compostos_avancados()
            
            st.subheader("🔔 Alertas Ativos")
            st.write(f"**Gols:** {len(alertas_gols)} alertas")
            st.write(f"**Ambas Marcam:** {len(alertas_ambas_marcam)} alertas")
            st.write(f"**Cartões:** {len(alertas_cartoes)} alertas")
            st.write(f"**Escanteios:** {len(alertas_escanteios)} alertas")
            st.write(f"**Compostos:** {len(alertas_compostos)} alertas")
            st.write(f"**Compostos Avançados:** {len(alertas_compostos_avancados)} alertas")
        
        with col2:
            st.subheader("🔧 Ferramentas do Sistema")
            
            if st.button("🔄 Forçar Atualização de Caches"):
                salvar_cache_jogos({})
                salvar_cache_classificacao({})
                salvar_cache_estatisticas({})
                salvar_cache_dados_historicos({})
                st.success("Caches forçados a atualizar!")
            
            if st.button("📊 Gerar Relatório de Performance"):
                # Calcular performance geral
                historicos = {}
                for tipo, caminho in caminhos_historico.items():
                    hist = carregar_historico(caminho)
                    if hist:
                        df = pd.DataFrame(hist)
                        if 'resultado' in df.columns:
                            green_count = df['resultado'].str.contains('GREEN').sum()
                            taxa = (green_count/len(df)*100) if len(df) > 0 else 0
                            historicos[tipo] = {
                                'total': len(df),
                                'green': green_count,
                                'taxa': taxa
                            }
                
                # Exibir relatório
                st.subheader("📈 Relatório de Performance")
                for tipo, stats in historicos.items():
                    st.write(f"**{tipo.upper()}:** {stats['total']} previsões | {stats['green']} GREEN | {stats['taxa']:.1f}% acerto")
            
            st.subheader("🐛 Debug do Sistema")
            if st.button("🔧 Testar Conexão com API"):
                debug_api_connection()
            
            if st.button("Verificar Rate Limit"):
                cache = rate_limit_manager._load_cache()
                st.json(cache)

if __name__ == "__main__":
    main()
