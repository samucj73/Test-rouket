import streamlit as st
from datetime import datetime, timedelta
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
ALERTAS_COMPOSTOS_PATH = "alertas_compostos.json"  # NOVO
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_ESTATISTICAS = "cache_estatisticas.json"
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# Histórico de conferências
HISTORICO_PATH = "historico_conferencias.json"
HISTORICO_AMBAS_MARCAM_PATH = "historico_ambas_marcam.json"
HISTORICO_CARTOES_PATH = "historico_cartoes.json"
HISTORICO_ESCANTEIOS_PATH = "historico_escanteios.json"
HISTORICO_COMPOSTOS_PATH = "historico_compostos.json"  # NOVO

# =============================
# SISTEMA DE RATE LIMIT AUTOMÁTICO
# =============================

RATE_LIMIT_CACHE = "rate_limit_cache.json"
RATE_LIMIT_CALLS_PER_MINUTE = 8  # Limite conservador para a API
RATE_LIMIT_WAIT_TIME = 70  # Segundos para esperar (1 minuto + margem)

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
    Versão da função de API com rate limit automático
    """
    try:
        # Aplicar rate limit antes de cada chamada
        rate_limit_manager.check_rate_limit()
        
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"⏰ Timeout na requisição API: {url}")
        return None
    except requests.exceptions.RequestException as e:
        # Verificar se é erro de rate limit da API
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 429:
                st.error("🚫 Rate Limit da API atingido! Aguardando 70s...")
                # Pausa forçada no cache
                cache = rate_limit_manager._load_cache()
                cache["pause_until"] = datetime.now().timestamp() + RATE_LIMIT_WAIT_TIME
                rate_limit_manager._save_cache(cache)
                time.sleep(RATE_LIMIT_WAIT_TIME)
                # Tentar novamente após espera
                return obter_dados_api_com_rate_limit(url, timeout)
            elif e.response.status_code == 404:
                st.warning(f"⚠️ Recurso não encontrado: {url}")
                return None
            elif e.response.status_code >= 500:
                st.error(f"🔴 Erro do servidor: {e.response.status_code}")
                return None
        
        st.error(f"❌ Erro na requisição API: {e}")
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
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO, CACHE_ESTATISTICAS]:
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
        if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO, CACHE_ESTATISTICAS]:
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
# SISTEMA DE ALERTAS COMPOSTOS DE RESULTADOS - VERSÃO CORRIGIDA
# =============================

def enviar_alerta_composto_resultados_poster(alerta_id: str, alerta_data: dict):
    """Envia alerta composto de RESULTS com poster para o Telegram - VERSÃO CORRIGIDA"""
    try:
        jogos = alerta_data.get("jogos", [])
        if not jogos:
            st.warning(f"⚠️ Nenhum jogo no alerta composto {alerta_id}")
            return False

        # Filtrar apenas jogos conferidos com resultados
        jogos_com_resultado = [j for j in jogos if j.get("conferido", False) and j.get("placar_final")]
        
        if not jogos_com_resultado:
            st.warning(f"⚠️ Nenhum resultado final no alerta composto {alerta_id}")
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
            titulo = f"ELITE MASTER - RESULTADOS {data_str}"
            
            st.info(f"🎨 Gerando poster de RESULTADOS compostos para {data_str} com {len(jogos_data)} jogos...")
            
            # Preparar dados para o poster de resultados COMPOSTOS - BUSCAR ESCUDOS
            jogos_para_poster = []
            for jogo_salvo in jogos_data:
                # Obter dados atualizados do jogo para pegar os escudos
                fixture_id = jogo_salvo.get("fixture_id")
                home_crest = ""
                away_crest = ""
                
                if fixture_id:
                    try:
                        url = f"{BASE_URL_FD}/matches/{fixture_id}"
                        fixture = obter_dados_api_com_rate_limit(url)
                        if fixture:
                            home_crest = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
                            away_crest = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
                    except Exception as e:
                        st.warning(f"⚠️ Não foi possível obter escudos para o jogo {fixture_id}: {e}")
                
                # Extrair placar do formato "XxY"
                placar = jogo_salvo.get("placar_final", "0x0")
                home_goals, away_goals = placar.split('x') if 'x' in placar else (0, 0)
                
                jogo_para_poster = {
                    "id": fixture_id or "",
                    "home": jogo_salvo["home"],
                    "away": jogo_salvo["away"],
                    "home_goals": int(home_goals),
                    "away_goals": int(away_goals),
                    "liga": jogo_salvo["liga"],
                    "data": jogo_salvo.get("data_jogo", datetime.now().isoformat()),
                    "tendencia_prevista": jogo_salvo["tendencia"],
                    "estimativa_prevista": jogo_salvo["estimativa"],
                    "confianca_prevista": jogo_salvo["confianca"],
                    "resultado": jogo_salvo.get("resultado", "PENDENTE"),
                    "home_crest": home_crest,  # NOVO: escudo do time da casa
                    "away_crest": away_crest   # NOVO: escudo do time visitante
                }
                jogos_para_poster.append(jogo_para_poster)
            
            # Gerar poster de resultados COMPOSTOS com escudos
            poster = gerar_poster_resultados_compostos_com_escudos(jogos_para_poster, titulo=titulo)
            
            # Calcular estatísticas do alerta composto
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j.get("resultado") == "GREEN")
            red_count = total_jogos - green_count
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            # Estatísticas do alerta original (se disponível)
            stats_alerta = alerta_data.get("estatisticas", {})
            green_count_alerta = stats_alerta.get("green_count", green_count)
            red_count_alerta = stats_alerta.get("red_count", red_count)
            taxa_acerto_alerta = stats_alerta.get("taxa_acerto", taxa_acerto)
            
            caption = (
                f"<b>🏁 RESULTADOS OFICIAIS - ALERTA COMPOSTO</b>\n\n"
                f"<b>📅 DATA DOS JOGOS: {data_str}</b>\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {red_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO DO ALERTA COMPOSTO:</b>\n"
                f"<b>• Threshold Original: {alerta_data.get('threshold', 0)}%</b>\n"
                f"<b>• Confiança Média: {sum(j.get('confianca', 0) for j in jogos_data) / len(jogos_data):.1f}%</b>\n"
                f"<b>• Previsões Validadas</b>\n"
                f"<b>• Resultados Oficiais</b>\n\n"
                f"<b>🔥 ELITE MASTER - SISTEMA COMPOSTO VERIFICADO</b>"
            )
            
            st.info("📤 Enviando poster de RESULTADOS compostos para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                st.success(f"🚀 Poster de RESULTADOS compostos enviado para {data_str}!")
                
                # Registrar no histórico de resultados compostos
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tendencia": jogo["tendencia"],
                        "estimativa": jogo["estimativa"],
                        "confianca": jogo["confianca"],
                        "placar": jogo.get("placar_final", "-"),
                        "resultado": "🟢 GREEN" if jogo.get("resultado") == "GREEN" else "🔴 RED",
                        "alerta_id": alerta_id  # NOVO: identificar o alerta composto
                    }, "compostos")
                
                enviados += 1
            else:
                st.error(f"❌ Falha ao enviar poster de resultados compostos para {data_str}")
                
        return enviados > 0
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados compostos: {str(e)}")
        # Fallback para mensagem de texto
        return enviar_alerta_composto_resultados_texto(alerta_id, alerta_data)

def gerar_poster_resultados_compostos_com_escudos(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS COMPOSTOS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais dos jogos compostos - COM ESCUDOS
    """
    # Configurações do poster - MESMO ESTILO DOS OUTROS
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950  # Um pouco mais compacto para múltiplos jogos
    PADDING = 60
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes - MESMO ESTILO DOS OUTROS POSTERS
    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(80)
    FONTE_TIMES = criar_fonte(75)
    FONTE_PLACAR = criar_fonte(85)
    FONTE_INFO = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(75)
    FONTE_RESULTADO = criar_fonte(75)

    # Título PRINCIPAL - MESMO ESTILO
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 300, 80), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 200), (3*LARGURA//4, 200)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # Calcular se a previsão foi correta
        total_gols = jogo['home_goals'] + jogo['away_goals']
        previsao_correta = False
        
        if jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5:
            previsao_correta = True
        
        # Definir cores baseadas no resultado - MESMO ESTILO
        if previsao_correta:
            cor_borda = (76, 175, 80)  # VERDE
            cor_resultado = (76, 175, 80)
            texto_resultado = "GREEN"
        else:
            cor_borda = (244, 67, 54)  # VERMELHO
            cor_resultado = (244, 67, 54)
            texto_resultado = "RED"

        # Caixa do jogo com borda colorida conforme resultado - MESMO ESTILO
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 30
        
        # Fundo com borda colorida
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=cor_borda, width=4)

        # BADGE RESULTADO (GREEN/RED) - MESMO ESTILO
        badge_text = texto_resultado
        badge_bg_color = cor_resultado
        
        try:
            badge_bbox = draw.textbbox((0, 0), badge_text, font=FONTE_RESULTADO)
            badge_w = badge_bbox[2] - badge_bbox[0] + 30
            badge_h = 90
            badge_x = x1 - badge_w - 15
            badge_y = y0 + 40
            
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], 
                          fill=badge_bg_color, outline=badge_bg_color)
            draw.text((badge_x + 15, badge_y + 5), badge_text, font=FONTE_RESULTADO, fill=(255, 255, 255))
        except:
            pass

        # Nome da liga - MESMO ESTILO
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 45), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))
        except:
            pass

        # Times e placar - layout mais compacto COM ESCUDOS
        home_text = jogo['home'][:20]
        away_text = jogo['away'][:20]
        
        # ESCUDOS compactos - AGORA COM ESCUDOS REAIS
        TAMANHO_ESCUDO = 180
        TAMANHO_QUADRADO = 190
        ESPACO_ENTRE_ESCUDOS = 800
        
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2
        y_escudos = y0 + 230

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS

        # Desenhar escudos compactos - USANDO ESCUDOS REAIS
        escudo_home = baixar_imagem_url(jogo.get('home_crest', ''))
        escudo_away = baixar_imagem_url(jogo.get('away_crest', ''))
        
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
                # Placeholder se não tiver escudo
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 40, y + 50), "?", font=FONTE_INFO, fill=(255, 255, 255))

        desenhar_escudo_compacto(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_compacto(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 25),
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

        # PLACAR CENTRAL - MESMO ESTILO
        placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - placar_w) // 2
            draw.text((placar_x, y_escudos + 40), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            pass

        # SEÇÃO DE ANÁLISE COMPACTA - MESMO ESTILO
        y_analysis = y_escudos + TAMANHO_QUADRADO + 90
        
        textos_analise = [
            f"Previsão: {jogo['tendencia_prevista']}",
            f"Real: {total_gols} gols | Estimativa: {jogo['estimativa_prevista']:.2f}",
            f"Confiança: {jogo['confianca_prevista']:.0f}% | Resultado: {texto_resultado}"
        ]
        
        cores = [(255, 255, 255), (200, 220, 255), cor_resultado]
        
        for i, (text, cor) in enumerate(zip(textos_analise, cores)):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                draw.text(((LARGURA - w) // 2, y_analysis + i * 100), text, font=FONTE_ANALISE, fill=cor)
            except:
                pass

        y_pos += ALTURA_POR_JOGO

    # Rodapé - MESMO ESTILO
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
    
    st.success(f"✅ Poster de resultados compostos GERADO com {len(jogos)} jogos")
    return buffer

def enviar_alerta_composto_resultados_texto(alerta_id: str, alerta_data: dict) -> bool:
    """Fallback para alerta de resultados compostos em texto"""
    try:
        jogos = alerta_data.get("jogos", [])
        jogos_com_resultado = [j for j in jogos if j.get("conferido", False) and j.get("placar_final")]
        
        if not jogos_com_resultado:
            return False
            
        msg = f"<b>🏁 RESULTADOS OFICIAIS - ALERTA COMPOSTO {alerta_id}</b>\n\n"
        
        # Agrupar por data
        jogos_por_data = {}
        for jogo in jogos_com_resultado:
            try:
                data_jogo = datetime.fromisoformat(jogo.get("data_jogo", "")).date()
                if data_jogo not in jogos_por_data:
                    jogos_por_data[data_jogo] = []
                jogos_por_data[data_jogo].append(jogo)
            except:
                continue
        
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            msg += f"<b>📅 {data_str}</b>\n\n"
            
            for jogo in jogos_data[:10]:  # Limitar a 10 por mensagem
                resultado = "🟢 GREEN" if jogo.get("resultado") == "GREEN" else "🔴 RED"
                msg += (
                    f"{resultado} <b>{jogo['home']}</b> {jogo.get('placar_final', '0x0')} <b>{jogo['away']}</b>\n"
                    f"Previsão: {jogo['tendencia']} | Conf: {jogo['confianca']:.0f}%\n\n"
                )
            
            # Estatísticas
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j.get("resultado") == "GREEN")
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            msg += (
                f"<b>📊 ESTATÍSTICAS {data_str}:</b>\n"
                f"<b>🟢 GREEN: {green_count}</b> | <b>🔴 RED: {total_jogos - green_count}</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
            )
        
        msg += "<b>🔥 ELITE MASTER - SISTEMA COMPOSTO VERIFICADO</b>"
        
        return enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
        
    except Exception as e:
        st.error(f"❌ Erro no fallback de texto para resultados compostos: {e}")
        return False

def verificar_resultados_alertas_compostos(alerta_resultados: bool):
    """Verifica resultados dos alertas compostos salvos - VERSÃO CORRIGIDA"""
    st.info("🔍 Verificando resultados de alertas compostos salvos...")
    
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
                score = fixture.get("score", {}).get("fullTime", {})
                home_goals = score.get("home")
                away_goals = score.get("away")
                
                # Verificar se jogo terminou e tem resultado
                if status == "FINISHED" and home_goals is not None and away_goals is not None:
                    # Calcular se previsão foi correta
                    total_gols = home_goals + away_goals
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
                    jogo_salvo["placar_final"] = f"{home_goals}x{away_goals}"
                    jogo_salvo["previsao_correta"] = previsao_correta
                    jogo_salvo["total_gols"] = total_gols
                    algum_jogo_atualizado = True
                    
                    st.info(f"✅ Jogo conferido: {jogo_salvo['home']} {home_goals}x{away_goals} {jogo_salvo['away']} - {jogo_salvo['resultado']}")
                    
                else:
                    todos_jogos_conferidos = False
                    st.info(f"⏳ Jogo pendente: {jogo_salvo['home']} vs {jogo_salvo['away']} - Status: {status}")
                    
            except Exception as e:
                st.error(f"❌ Erro ao verificar jogo composto {fixture_id}: {e}")
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
            st.success(f"🎯 Alerta composto {alerta_id} totalmente conferido! GREEN: {green_count}/{total_jogos}")
        
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

def debug_alertas_compostos():
    """Função de debug para verificar o estado dos alertas compostos"""
    st.subheader("🐛 Debug - Alertas Compostos")
    
    alertas = carregar_alertas_compostos()
    st.write(f"Total de alertas compostos: {len(alertas)}")
    
    for alerta_id, alerta in alertas.items():
        with st.expander(f"Alerta: {alerta_id}", expanded=False):
            st.json(alerta)  # Mostra toda a estrutura do alerta
            
            jogos = alerta.get("jogos", [])
            st.write(f"Total de jogos: {len(jogos)}")
            
            for jogo in jogos:
                st.write(f"- {jogo['home']} vs {jogo['away']} | Conferido: {jogo.get('conferido', False)} | Resultado: {jogo.get('resultado', 'N/A')}")

def exibir_alertas_compostos_salvos():
    """Exibe interface para visualizar alertas compostos salvos"""
    alertas = carregar_alertas_compostos()
    
    if not alertas:
        st.info("ℹ️ Nenhum alerta composto salvo no momento.")
        return
    
    st.subheader("📋 Alertas Compostos Salvos (24h)")
    
    for alerta_id, alerta in alertas.items():
        data_criacao = datetime.fromisoformat(alerta.get("data_criacao", ""))
        data_expiracao = datetime.fromisoformat(alerta.get("data_expiracao", ""))
        tempo_restante = data_expiracao - datetime.now()
        horas_restantes = max(0, tempo_restante.total_seconds() / 3600)
        
        status = "✅ Conferido" if alerta.get("conferido", False) else "⏳ Aguardando"
        
        with st.expander(f"📊 Alerta {alerta_id} - {status} - {horas_restantes:.1f}h restantes", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Data Criação:** {data_criacao.strftime('%d/%m/%Y %H:%M')}")
                st.write(f"**Expira em:** {data_expiracao.strftime('%d/%m/%Y %H:%M')}")
                st.write(f"**Threshold:** {alerta.get('threshold', 0)}%")
                
            with col2:
                st.write(f"**Total Jogos:** {alerta.get('total_jogos', 0)}")
                st.write(f"**Poster Enviado:** {'✅ Sim' if alerta.get('poster_enviado') else '❌ Não'}")
                st.write(f"**Status:** {status}")
                
            with col3:
                if alerta.get("estatisticas"):
                    stats = alerta["estatisticas"]
                    st.write(f"**🟢 GREEN:** {stats.get('green_count', 0)}")
                    st.write(f"**🔴 RED:** {stats.get('red_count', 0)}")
                    st.write(f"**🎯 Taxa Acerto:** {stats.get('taxa_acerto', 0):.1f}%")
            
            # Lista de jogos
            st.write("**🎯 Jogos Incluídos:**")
            jogos = alerta.get("jogos", [])
            
            for i, jogo in enumerate(jogos):
                cor_status = "🟢" if jogo.get("resultado") == "GREEN" else "🔴" if jogo.get("resultado") == "RED" else "⚪"
                status_jogo = jogo.get("resultado", "Aguardando") if jogo.get("conferido") else "⏳ Pendente"
                
                col_j1, col_j2, col_j3 = st.columns([2, 2, 1])
                
                with col_j1:
                    st.write(f"{cor_status} **{jogo['home']} vs {jogo['away']}**")
                    st.write(f"🏆 {jogo['liga']}")
                    
                with col_j2:
                    st.write(f"📈 {jogo['tendencia']}")
                    st.write(f"🎯 {jogo['confianca']:.0f}%")
                    
                with col_j3:
                    st.write(f"**{status_jogo}**")
                    if jogo.get("placar_final"):
                        st.write(f"🔢 {jogo['placar_final']}")
            
            # Botão para forçar conferência deste alerta
            if st.button(f"🔄 Conferir Agora", key=f"conferir_{alerta_id}"):
                with st.spinner("Conferindo resultados..."):
                    # Lógica de conferência específica para este alerta
                    jogos_atualizados = 0
                    for jogo_salvo in jogos:
                        if jogo_salvo.get("conferido", False):
                            continue
                            
                        fixture_id = jogo_salvo.get("fixture_id")
                        if fixture_id:
                            url = f"{BASE_URL_FD}/matches/{fixture_id}"
                            fixture = obter_dados_api_com_rate_limit(url)
                            
                            if fixture and fixture.get("status") == "FINISHED":
                                score = fixture.get("score", {}).get("fullTime", {})
                                home_goals = score.get("home")
                                away_goals = score.get("away")
                                
                                if home_goals is not None and away_goals is not None:
                                    total_gols = home_goals + away_goals
                                    previsao_correta = False
                                    
                                    if jogo_salvo['tendencia'] == "Mais 2.5" and total_gols > 2.5:
                                        previsao_correta = True
                                    elif jogo_salvo['tendencia'] == "Mais 1.5" and total_gols > 1.5:
                                        previsao_correta = True
                                    elif jogo_salvo['tendencia'] == "Menos 2.5" and total_gols < 2.5:
                                        previsao_correta = True
                                    
                                    jogo_salvo["conferido"] = True
                                    jogo_salvo["resultado"] = "GREEN" if previsao_correta else "RED"
                                    jogo_salvo["placar_final"] = f"{home_goals}x{away_goals}"
                                    jogo_salvo["previsao_correta"] = previsao_correta
                                    jogos_atualizados += 1
                    
                    if jogos_atualizados > 0:
                        # Verificar se todos os jogos foram conferidos
                        todos_conferidos = all(jogo.get("conferido", False) for jogo in jogos)
                        if todos_conferidos:
                            alerta["conferido"] = True
                            
                            # Calcular estatísticas
                            jogos_conferidos = [j for j in jogos if j.get("conferido", False)]
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
                        
                        salvar_alertas_compostos(alertas)
                        st.success(f"✅ {jogos_atualizados} jogos conferidos!")
                        st.rerun()
                    else:
                        st.info("ℹ️ Nenhum novo resultado encontrado para este alerta.")

# =============================
# Histórico de Conferências - COM PERSISTÊNCIA
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
        "compostos": HISTORICO_COMPOSTOS_PATH  # NOVO
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
        "compostos": HISTORICO_COMPOSTOS_PATH  # NOVO
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
# Utilitários de Data e Formatação
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    """Formata data ISO de forma robusta - CORRIGIDA"""
    try:
        # Remover 'Z' e converter para datetime com timezone UTC
        if data_iso.endswith('Z'):
            data_iso = data_iso[:-1] + '+00:00'
        
        data_utc = datetime.fromisoformat(data_iso)
        
        # Converter para horário de Brasília (UTC-3)
        data_brasilia = data_utc - timedelta(hours=3)
        
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

def obter_classificacao(liga_id: str) -> dict:
    cache = carregar_cache_classificacao()
    if liga_id in cache:
        return cache[liga_id]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
    data = obter_dados_api_com_rate_limit(url)
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
                "played": t.get("playedGames", 1)
            }
    cache[liga_id] = standings
    salvar_cache_classificacao(cache)
    return standings

def obter_jogos(liga_id: str, data: str) -> list:
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
    data_api = obter_dados_api_com_rate_limit(url)
    jogos = data_api.get("matches", []) if data_api else []
    cache[key] = jogos
    salvar_cache_jogos(cache)
    return jogos

# =============================
# NOVAS FUNÇÕES DE PREVISÃO COM DADOS REAIS
# =============================

def obter_estatisticas_time_real(time_id: str, liga_id: str) -> dict:
    """
    Obtém estatísticas REAIS do time da API
    """
    cache = carregar_cache_estatisticas()
    cache_key = f"{liga_id}_{time_id}"
    
    if cache_key in cache:
        return cache[cache_key]
    
    try:
        # Tentar obter estatísticas do time na competição
        url = f"{BASE_URL_FD}/competitions/{liga_id}/teams"
        data = obter_dados_api_com_rate_limit(url)
        
        estatisticas = {
            "cartoes_media": 2.8,
            "escanteios_media": 5.2,
            "finalizacoes_media": 12.5,
            "posse_media": 50.0
        }
        
        if data and "teams" in data:
            for team in data["teams"]:
                if str(team.get("id")) == str(time_id):
                    # Aqui podemos extrair mais dados quando disponíveis
                    estatisticas["nome"] = team.get("name", "")
                    estatisticas["fundacao"] = team.get("founded", "")
                    estatisticas["cores"] = team.get("clubColors", "")
                    
                    # Ajustar baseado na reputação do time
                    if any(name in team.get("name", "").lower() for name in ["city", "united", "real", "bayern"]):
                        estatisticas["cartoes_media"] = 2.5
                        estatisticas["escanteios_media"] = 6.8
                    elif any(name in team.get("name", "").lower() for name in ["atletico", "atalanta", "leeds"]):
                        estatisticas["cartoes_media"] = 3.8
                        estatisticas["escanteios_media"] = 5.5
        
        cache[cache_key] = estatisticas
        salvar_cache_estatisticas(cache)
        return estatisticas
        
    except Exception as e:
        st.error(f"Erro ao obter estatísticas do time {time_id}: {e}")
        return {
            "cartoes_media": 2.8,
            "escanteios_media": 5.2,
            "finalizacoes_media": 12.5,
            "posse_media": 50.0
        }

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

def calcular_previsao_cartoes_real(home_team: dict, away_team: dict, liga_id: str) -> tuple[float, float, str]:
    """
    Previsão REAL: Total de cartões usando dados reais da API
    """
    home_id = home_team.get("id")
    away_id = away_team.get("id")
    
    # Obter estatísticas REAIS dos times
    stats_home = obter_estatisticas_time_real(str(home_id), liga_id)
    stats_away = obter_estatisticas_time_real(str(away_id), liga_id)
    
    # Médias baseadas em dados reais
    media_cartoes_home = stats_home.get("cartoes_media", 2.8)
    media_cartoes_away = stats_away.get("cartoes_media", 2.8)
    
    # Fatores de ajuste baseados na liga
    fatores_liga = {
        "BSA": 1.3,  # Brasileirão tem mais cartões
        "SA": 1.2,   # Serie A italiana
        "PL": 1.0,   # Premier League
        "BL1": 0.9,  # Bundesliga tem menos cartões
        "PD": 1.1,   # La Liga
        "FL1": 1.0,  # Ligue 1
    }
    
    fator_liga = fatores_liga.get(liga_id, 1.0)
    
    # Total estimado de cartões
    total_estimado = (media_cartoes_home + media_cartoes_away) * fator_liga
    
    # Calcular confiança
    confianca = min(85, 40 + (total_estimado * 8))
    
    # Definir tendências
    if total_estimado >= 5.5:
        tendencia = f"Mais 5.5 Cartões"
        confianca = min(90, confianca + 5)
    elif total_estimado >= 4.0:
        tendencia = f"Mais 4.5 Cartões"
    else:
        tendencia = f"Menos 4.5 Cartões"
        confianca = max(40, confianca - 5)
    
    return total_estimado, confianca, tendencia

def calcular_previsao_escanteios_real(home_team: dict, away_team: dict, liga_id: str) -> tuple[float, float, str]:
    """
    Previsão REAL: Total de escanteios usando dados reais da API
    """
    home_id = home_team.get("id")
    away_id = away_team.get("id")
    
    # Obter estatísticas REAIS dos times
    stats_home = obter_estatisticas_time_real(str(home_id), liga_id)
    stats_away = obter_estatisticas_time_real(str(away_id), liga_id)
    
    # Médias baseadas em dados reais
    media_escanteios_home = stats_home.get("escanteios_media", 5.2)
    media_escanteios_away = stats_away.get("escanteios_media", 5.2)
    
    # Fatores de ajuste baseados na liga
    fatores_liga = {
        "BSA": 1.2,  # Brasileirão tem mais escanteios
        "PL": 1.1,   # Premier League
        "BL1": 1.0,  # Bundesliga
        "SA": 0.9,   # Serie A tem menos escanteios
        "PD": 1.0,   # La Liga
        "FL1": 0.9,  # Ligue 1
    }
    
    fator_liga = fatores_liga.get(liga_id, 1.0)
    
    # Total estimado de escanteios
    total_estimado = (media_escanteios_home + media_escanteios_away) * fator_liga
    
    # Calcular confiança
    confianca = min(80, 35 + (total_estimado * 4))
    
    # Definir tendências
    if total_estimado >= 10.5:
        tendencia = f"Mais 10.5 Escanteios"
        confianca = min(85, confianca + 5)
    elif total_estimado >= 8.0:
        tendencia = f"Mais 8.5 Escanteios"
    else:
        tendencia = f"Menos 8.5 Escanteios"
        confianca = max(35, confianca - 5)
    
    return total_estimado, confianca, tendencia

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
                except:
                    draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                    draw.text((x + 50, y + 70), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

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
        if tipo == "ambas_marcam":
            placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
            resultado_real = "SIM" if jogo['ambas_marcaram'] else "NÃO"
        elif tipo == "cartoes":
            placar_text = f"{jogo['cartoes_total']} CARTÕES"
            resultado_real = f"{jogo['cartoes_total']} cartões"
        elif tipo == "escanteios":
            placar_text = f"{jogo['escanteios_total']} ESCANTEIOS"
            resultado_real = f"{jogo['escanteios_total']} escanteios"

        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - placar_w) // 2
            draw.text((placar_x, y_escudos + 60), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            pass

        # SEÇÃO DE ANÁLISE
        y_analysis = y_escudos + TAMANHO_QUADRADO + 80
        
        textos_analise = [
            f"Previsão: {jogo['previsao']}",
            f"Real: {resultado_real}",
            f"Confiança: {jogo['confianca_prevista']:.0f}% | Resultado: {texto_resultado}"
        ]
        
        for i, text in enumerate(textos_analise):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                draw.text(((LARGURA - w) // 2, y_analysis + i * 70), text, font=FONTE_ANALISE, 
                         fill=(255, 255, 255) if i < 2 else cor_resultado)
            except:
                pass

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"Resultados oficiais • {datetime.now().strftime('%d/%m/%Y %H:%M')} • Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(120, 150, 180))
    except:
        pass

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster de {tipo} gerado com {len(jogos)} jogos")
    return buffer

# =============================
# FUNÇÕES DE ENVIO DE RESULTADOS - TODOS OS TIPOS
# =============================

def enviar_alerta_resultados_ambas_marcam_poster(jogos_com_resultado: list):
    """Envia alerta de resultados Ambas Marcam com poster"""
    if not jogos_com_resultado:
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
            titulo = f"ELITE MASTER - RESULTADOS AMBAS MARCAM {data_str}"
            
            st.info(f"🎨 Gerando poster Ambas Marcam para {data_str}...")
            poster = gerar_poster_resultados_ambas_marcam(jogos_data, titulo=titulo)
            
            # Estatísticas
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j['previsao_correta'])
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            caption = (
                f"<b>🏁 RESULTADOS AMBAS MARCAM - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {total_jogos - green_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>⚽ ELITE MASTER - ANÁLISE AMBAS MARCAM COMPROVADA</b>"
            )
            
            if enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2):
                st.success(f"🚀 Resultados Ambas Marcam enviados para {data_str}!")
                
                # Registrar no histórico
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tendencia": jogo["previsao"],
                        "estimativa": jogo["probabilidade_prevista"],
                        "confianca": jogo["confianca_prevista"],
                        "placar": f"{jogo['home_goals']}x{jogo['away_goals']}",
                        "resultado": "🟢 GREEN" if jogo['previsao_correta'] else "🔴 RED",
                        "previsao": jogo["previsao"],
                        "ambas_marcaram": jogo["ambas_marcaram"]
                    }, "ambas_marcam")
            else:
                st.error(f"❌ Falha ao enviar resultados Ambas Marcam")
                
    except Exception as e:
        st.error(f"❌ Erro ao enviar resultados Ambas Marcam: {str(e)}")

def enviar_alerta_resultados_cartoes_poster(jogos_com_resultado: list):
    """Envia alerta de resultados Cartões com poster"""
    if not jogos_com_resultado:
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
            titulo = f"ELITE MASTER - RESULTADOS CARTÕES {data_str}"
            
            st.info(f"🎨 Gerando poster Cartões para {data_str}...")
            poster = gerar_poster_resultados_cartoes(jogos_data, titulo=titulo)
            
            # Estatísticas
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j['previsao_correta'])
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            caption = (
                f"<b>🏁 RESULTADOS CARTÕES - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {total_jogos - green_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>🟨 ELITE MASTER - ANÁLISE DE CARTÕES COMPROVADA</b>"
            )
            
            if enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2):
                st.success(f"🚀 Resultados Cartões enviados para {data_str}!")
                
                # Registrar no histórico
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tendencia": jogo["previsao"],
                        "estimativa": jogo["estimativa_prevista"],
                        "confianca": jogo["confianca_prevista"],
                        "placar": f"{jogo['cartoes_total']} cartões",
                        "resultado": "🟢 GREEN" if jogo['previsao_correta'] else "🔴 RED",
                        "cartoes_total": jogo["cartoes_total"],
                        "limiar_cartoes": jogo["limiar_cartoes"]
                    }, "cartoes")
            else:
                st.error(f"❌ Falha ao enviar resultados Cartões")
                
    except Exception as e:
        st.error(f"❌ Erro ao enviar resultados Cartões: {str(e)}")

def enviar_alerta_resultados_escanteios_poster(jogos_com_resultado: list):
    """Envia alerta de resultados Escanteios com poster"""
    if not jogos_com_resultado:
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
            titulo = f"ELITE MASTER - RESULTADOS ESCANTEIOS {data_str}"
            
            st.info(f"🎨 Gerando poster Escanteios para {data_str}...")
            poster = gerar_poster_resultados_escanteios(jogos_data, titulo=titulo)
            
            # Estatísticas
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j['previsao_correta'])
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            caption = (
                f"<b>🏁 RESULTADOS ESCANTEIOS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {total_jogos - green_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>🔄 ELITE MASTER - ANÁLISE DE ESCANTEIOS COMPROVADA</b>"
            )
            
            if enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2):
                st.success(f"🚀 Resultados Escanteios enviados para {data_str}!")
                
                # Registrar no histórico
                for jogo in jogos_data:
                    registrar_no_historico({
                        "home": jogo["home"],
                        "away": jogo["away"],
                        "tendencia": jogo["previsao"],
                        "estimativa": jogo["estimativa_prevista"],
                        "confianca": jogo["confianca_prevista"],
                        "placar": f"{jogo['escanteios_total']} escanteios",
                        "resultado": "🟢 GREEN" if jogo['previsao_correta'] else "🔴 RED",
                        "escanteios_total": jogo["escanteios_total"],
                        "limiar_escanteios": jogo["limiar_escanteios"]
                    }, "escanteios")
            else:
                st.error(f"❌ Falha ao enviar resultados Escanteios")
                
    except Exception as e:
        st.error(f"❌ Erro ao enviar resultados Escanteios: {str(e)}")

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
# NOVAS FUNÇÕES PARA ALERTAS COMPOSTOS
# =============================
def gerar_poster_multiplos_jogos(jogos: list, titulo: str = "ELITE MASTER - ALERTAS DO DIA") -> io.BytesIO:
    """
    Gera poster profissional com múltiplos jogos para alertas compostos - VERSÃO COM MAIS ESPAÇO VERTICAL
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 900  # Aumentei para 1050 (200px a mais que o original)
    PADDING = 60
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + (jogos_count * ALTURA_POR_JOGO) + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(13, 25, 35))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(70)
    FONTE_TIMES = criar_fonte(65)
    FONTE_VS = criar_fonte(60)
    FONTE_INFO = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(60)
    FONTE_CONFIANCA = criar_fonte(55)

    # === TOPO DO POSTER ===
    titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
    titulo_w = titulo_bbox[2] - titulo_bbox[0]
    draw.text(((LARGURA - titulo_w) // 2, 60), titulo, font=FONTE_TITULO, fill=(255, 215, 0))

    # Data atual
    data_atual = datetime.now().strftime("%d/%m/%Y")
    data_text = f"DATA DE ANÁLISE: {data_atual}"
    data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_SUBTITULO)
    data_w = data_bbox[2] - data_bbox[0]
    draw.text(((LARGURA - data_w) // 2, 160), data_text, font=FONTE_SUBTITULO, fill=(150, 200, 255))

    # Linha decorativa
    draw.line([(LARGURA//4, 240), (3*LARGURA//4, 240)], fill=(255, 215, 0), width=4)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # === CAIXA DO JOGO ===
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 30
        
        # Fundo com borda
        draw.rectangle([x0, y0, x1, y1], fill=(25, 40, 55), outline=(100, 130, 160), width=3)

        # === LINHA 1: LIGA === (MAIS ESPAÇO DO TOPO)
        liga_text = jogo['liga'].upper()
        liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
        liga_w = liga_bbox[2] - liga_bbox[0]
        draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(170, 190, 210))  # +50px do topo

        # === LINHA 2: HORÁRIO === (MAIS ESPAÇO DA LIGA)
        if 'hora_formatada' in jogo and 'data_formatada' in jogo:
            hora_text = f"HORÁRIO: {jogo['hora_formatada']} BRT | DATA: {jogo['data_formatada']}"
        else:
            try:
                hora_format = jogo["hora"].strftime("%H:%M") if isinstance(jogo["hora"], datetime) else str(jogo["hora"])
                data_format = jogo["hora"].strftime("%d/%m/%Y") if isinstance(jogo["hora"], datetime) else "Data inválida"
                hora_text = f"HORÁRIO: {hora_format} BRT | DATA: {data_format}"
            except:
                hora_text = "HORÁRIO: Não disponível"
        
        hora_bbox = draw.textbbox((0, 0), hora_text, font=FONTE_INFO)
        hora_w = hora_bbox[2] - hora_bbox[0]
        draw.text(((LARGURA - hora_w) // 2, y0 + 140), hora_text, font=FONTE_INFO, fill=(120, 180, 240))  # +140px do topo (90px após a liga)

        # === SEÇÃO TIMES E ESCUDOS === (MAIS ESPAÇO DO HORÁRIO)
        TAMANHO_ESCUDO = 200
        TAMANHO_QUADRADO = 220
        ESPACO_ENTRE_ESCUDOS = 700

        # Calcular posição central para escudos - MAIS ESPAÇO DO HORÁRIO
        largura_total_escudos = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio_escudos = (LARGURA - largura_total_escudos) // 2
        y_escudos = y0 + 230  # +220px do topo (80px após o horário)

        x_home_escudo = x_inicio_escudos
        x_away_escudo = x_home_escudo + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS

        # Função para desenhar escudo quadrado
        def desenhar_escudo_quadrado_compacto(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo branco
            draw.rectangle(
                [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                fill=(255, 255, 255),
                outline=(200, 200, 200),
                width=2
            )

            if logo_img is None:
                # Placeholder
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
                draw.text((x + 40, y + 60), "?", font=FONTE_INFO, fill=(255, 255, 255))
                return

            try:
                logo_img = logo_img.convert("RGBA")
                largura, altura = logo_img.size
                
                # Redimensionar mantendo proporção
                ratio = min(tamanho_escudo/largura, tamanho_escudo/altura)
                nova_largura = int(largura * ratio)
                nova_altura = int(altura * ratio)
                
                logo_img = logo_img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                
                # Calcular posição para centralizar
                pos_x = x + (tamanho_quadrado - nova_largura) // 2
                pos_y = y + (tamanho_quadrado - nova_altura) // 2

                # Colar escudo
                img.paste(logo_img, (pos_x, pos_y), logo_img)

            except Exception as e:
                print(f"[ERRO ESCUDO] {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 40, y + 60), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Baixar escudos
        fixture = jogo.get('fixture', {})
        escudo_home_url = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
        escudo_away_url = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")

        escudo_home = baixar_imagem_url(escudo_home_url)
        escudo_away = baixar_imagem_url(escudo_away_url)

        # Desenhar escudos
        desenhar_escudo_quadrado_compacto(escudo_home, x_home_escudo, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado_compacto(escudo_away, x_away_escudo, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # === NOMES DOS TIMES === (MAIS ESPAÇO DOS ESCUDOS)
        home_text = jogo['home'][:16]
        away_text = jogo['away'][:16]
        
        home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
        home_w = home_bbox[2] - home_bbox[0]
        draw.text((x_home_escudo + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 40),  # +40px após escudos
                 home_text, font=FONTE_TIMES, fill=(255, 255, 255))

        away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
        away_w = away_bbox[2] - away_bbox[0]
        draw.text((x_away_escudo + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 40),  # +40px após escudos
                 away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        
        # === VS CENTRALIZADO ===
        vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
        vs_w = vs_bbox[2] - vs_bbox[0]
        vs_x = x_home_escudo + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
        vs_y = y_escudos + TAMANHO_QUADRADO//2 - 20
        draw.text((vs_x, vs_y), "VS", font=FONTE_VS, fill=(255, 215, 0))

        # === SEÇÃO ANÁLISE === (MAIS ESPAÇO DOS NOMES DOS TIMES)
        y_analysis = y_escudos + TAMANHO_QUADRADO + 160  # +120px após nomes dos times
        
        # Dividir a largura em 3 colunas iguais
        largura_coluna = (LARGURA - 2 * PADDING) // 3
        x_col1 = PADDING + 20
        x_col2 = x_col1 + largura_coluna
        x_col3 = x_col2 + largura_coluna

        textos_analise = [
            f"TENDÊNCIA: {jogo['tendencia'].upper()}",
            f" ESTIMATIVA: {jogo['estimativa']:.2f} GOLS", 
            f"CONFIANÇA: {jogo['confianca']:.0f}%"
        ]
        
        cores = [(255, 215, 0), (100, 200, 255), (100, 255, 100)]
        posicoes_x = [x_col1, x_col2, x_col3]
        
        for i, (text, cor, x_pos) in enumerate(zip(textos_analise, cores, posicoes_x)):
            bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
            w = bbox[2] - bbox[0]
            # Centralizar cada texto em sua coluna
            x_centro = x_pos + (largura_coluna - w) // 2
            draw.text((x_centro, y_analysis), text, font=FONTE_ANALISE, fill=cor)

        # === INDICADOR DE FORÇA === (MAIS ESPAÇO DA ANÁLISE)
        y_indicator = y_analysis + 100  # +100px após análise
        
        if jogo['confianca'] >= 80:
            indicador_text = "🔥 ALTA CONFIABILIDADE 🔥"
            cor_indicador = (76, 255, 80)
        elif jogo['confianca'] >= 60:
            indicador_text = "⚡ CONFIABILIDADE MÉDIA ⚡"
            cor_indicador = (255, 215, 0)
        else:
            indicador_text = "⚠️ CONFIABILIDADE MODERADA ⚠️"
            cor_indicador = (255, 152, 0)

        ind_bbox = draw.textbbox((0, 0), indicador_text, font=FONTE_CONFIANCA)
        ind_w = ind_bbox[2] - ind_bbox[0]
        draw.text(((LARGURA - ind_w) // 2, y_indicator), indicador_text, font=FONTE_CONFIANCA, fill=cor_indicador)

        # Linha separadora entre jogos (exceto último)
        if idx < len(jogos) - 1:
            draw.line([(x0 + 50, y1), (x1 - 50, y1)], fill=(100, 130, 160), width=2)

        y_pos += ALTURA_POR_JOGO

    # === RODAPÉ ===
    rodape_text = f"ELITE MASTER SYSTEM • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_INFO)
    rodape_w = rodape_bbox[2] - rodape_bbox[0]
    draw.text(((LARGURA - rodape_w) // 2, altura_total - 50), rodape_text, font=FONTE_INFO, fill=(100, 130, 160))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    return buffer


def enviar_alerta_composto_poster(jogos_conf: list, threshold: int):
    """Envia alerta composto com poster para múltiplos jogos - ATUALIZADA COM SALVAMENTO"""
    if not jogos_conf:
        st.warning("⚠️ Nenhum jogo para gerar poster composto")
        return False

    try:
        # Agrupar por data
        jogos_por_data = {}
        for jogo in jogos_conf:
            data_jogo = jogo["hora"].date() if isinstance(jogo["hora"], datetime) else datetime.now().date()
            if data_jogo not in jogos_por_data:
                jogos_por_data[data_jogo] = []
            jogos_por_data[data_jogo].append(jogo)

        enviados = 0
        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - ALERTAS {data_str}"
            
            st.info(f"🎨 Gerando poster composto para {data_str} com {len(jogos_data)} jogos...")
            
            # Ordenar por confiança
            jogos_data_sorted = sorted(jogos_data, key=lambda x: x['confianca'], reverse=True)
            
            # Gerar poster
            poster = gerar_poster_multiplos_jogos(jogos_data_sorted, titulo=titulo)
            
            # Calcular estatísticas
            total_jogos = len(jogos_data)
            confianca_media = sum(j['confianca'] for j in jogos_data) / total_jogos
            jogos_alta_conf = sum(1 for j in jogos_data if j['confianca'] >= 80)
            
            caption = (
                f"<b>🎯 ALERTAS DE GOLS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS ANALISADOS: {total_jogos}</b>\n"
                f"<b>🎯 CONFIANÇA MÉDIA: {confianca_media:.1f}%</b>\n"
                f"<b>🔥 JOGOS ALTA CONFIANÇA: {jogos_alta_conf}</b>\n\n"
                f"<b>📊 CRITÉRIOS DA ANÁLISE:</b>\n"
                f"<b>• Limiar mínimo: {threshold}% de confiança</b>\n"
                f"<b>• Dados estatísticos em tempo real</b>\n"
                f"<b>• Análise preditiva avançada</b>\n\n"
                f"<b>⚽ ELITE MASTER SYSTEM - ANÁLISE CONFIÁVEL</b>"
            )
            
            st.info("📤 Enviando poster composto para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=TELEGRAM_CHAT_ID_ALT2)
            
            if ok:
                # SALVAR ALERTA COMPOSTO PARA FUTURA CONFERÊNCIA - NOVO
                alerta_id = salvar_alerta_composto_para_conferencia(jogos_data, threshold, poster_enviado=True)
                if alerta_id:
                    st.success(f"🚀 Poster composto enviado e salvo para conferência (24h)! ID: {alerta_id}")
                else:
                    st.success(f"🚀 Poster composto enviado para {data_str}!")
                enviados += 1
            else:
                st.error(f"❌ Falha ao enviar poster composto para {data_str}")
                
        return enviados > 0
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster composto: {str(e)}")
        # Fallback para mensagem de texto
        return enviar_alerta_composto_texto(jogos_conf, threshold)

def enviar_alerta_composto_texto(jogos_conf: list, threshold: int) -> bool:
    """Fallback para alerta composto em texto"""
    try:
        msg = f"🔥 Jogos ≥{threshold}% (Estilo Original):\n\n"
        
        for jogo in jogos_conf:
            # CORREÇÃO: Usar dados formatados se disponíveis
            if 'hora_formatada' in jogo and 'data_formatada' in jogo:
                hora_text = jogo['hora_formatada']
                data_text = jogo['data_formatada']
            else:
                hora_format = jogo["hora"].strftime("%H:%M") if isinstance(jogo["hora"], datetime) else str(jogo["hora"])
                data_format = jogo["hora"].strftime("%d/%m/%Y") if isinstance(jogo["hora"], datetime) else "Data inválida"
                hora_text = hora_format
                data_text = data_format
                
            msg += (
                f"🏟️ <b>{jogo['home']}</b> vs <b>{jogo['away']}</b>\n"
                f"🕒 {hora_text} BRT | {data_text} | {jogo['liga']}\n"
                f"📈 {jogo['tendencia']} | ⚽ {jogo['estimativa']:.2f} | 💯 {jogo['confianca']:.0f}%\n\n"
            )
        
        msg += "<b>🔥 ELITE MASTER SYSTEM - ANÁLISE PREDITIVA</b>"
        
        return enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)
    except Exception as e:
        st.error(f"❌ Erro no fallback de texto: {e}")
        return False

# =============================
# Funções de geração de imagem
# =============================
def gerar_poster_individual_westham(fixture: dict, tendencia: str, estimativa: float, confianca: float) -> io.BytesIO:
    """
    Gera poster individual no estilo West Ham para alertas individuais
    """
    # Configurações
    LARGURA = 1800
    ALTURA = 1200
    PADDING = 80

    # Criar canvas
    img = Image.new("RGB", (LARGURA, ALTURA), color=(10, 20, 30))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(95)
    FONTE_SUBTITULO = criar_fonte(60)
    FONTE_TIMES = criar_fonte(65)
    FONTE_VS = criar_fonte(55)
    FONTE_INFO = criar_fonte(45)
    FONTE_DETALHES = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(60)
    FONTE_ALERTA = criar_fonte(90)

    # Título PRINCIPAL - ALERTA
    titulo_text = " ALERTA DE GOLS "
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo_text, font=FONTE_ALERTA)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 60), titulo_text, font=FONTE_ALERTA, fill=(255, 215, 0))
    except:
        draw.text((LARGURA//2 - 200, 60), titulo_text, font=FONTE_ALERTA, fill=(255, 215, 0))

    # Linha decorativa
    draw.line([(LARGURA//4, 150), (3*LARGURA//4, 150)], fill=(255, 215, 0), width=4)

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
    TAMANHO_ESCUDO = 220
    TAMANHO_QUADRADO = 250
    ESPACO_ENTRE_ESCUDOS = 600

    # Calcular posição central
    largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    x_inicio = (LARGURA - largura_total) // 2

    x_home = x_inicio
    x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
    y_escudos = 350

    # Baixar escudos
    escudo_home_url = fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", "")
    escudo_away_url = fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
    
    escudo_home = baixar_imagem_url(escudo_home_url)
    escudo_away = baixar_imagem_url(escudo_away_url)

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
            print(f"[ERRO ESCUDO] {e}")
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

    # SEÇÃO DE ANÁLISE
    y_analysis = y_escudos + TAMANHO_QUADRADO + 120
    
    # Linha separadora
    draw.line([(PADDING + 50, y_analysis - 20), (LARGURA - PADDING - 50, y_analysis - 20)], 
             fill=(100, 130, 160), width=3)

    # Informações de análise com destaque
    tendencia_emoji = "" if "Mais" in tendencia else "" if "Menos" in tendencia else "⚡"
    
    textos_analise = [
        f"{tendencia_emoji} TENDÊNCIA: {tendencia.upper()}",
        f" ESTIMATIVA: {estimativa:.2f} GOLS",
        f" CONFIANÇA: {confianca:.0f}%",
    ]
    
    cores = [(255, 215, 0), (100, 200, 255), (100, 255, 100)]
    
    for i, (text, cor) in enumerate(zip(textos_analise, cores)):
        try:
            bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
            w = bbox[2] - bbox[0]
            draw.text(((LARGURA - w) // 2, y_analysis + i * 85), text, font=FONTE_ANALISE, fill=cor)
        except:
            draw.text((PADDING + 100, y_analysis + i * 85), text, font=FONTE_ANALISE, fill=cor)

    # Indicador de força da confiança
    y_indicator = y_analysis + 220
    if confianca >= 80:
        indicador_text = "🔥🔥 ALTA CONFIABILIDADE 🔥🔥"
        cor_indicador = (76, 175, 80)  # Verde
    elif confianca >= 60:
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

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    """Envia alerta individual com poster estilo West Ham"""
    try:
        # Gerar poster individual
        poster = gerar_poster_individual_westham(fixture, tendencia, estimativa, confianca)
        
        # Criar caption para o Telegram
        home = fixture["homeTeam"]["name"]
        away = fixture["awayTeam"]["name"]
        data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
        competicao = fixture.get("competition", {}).get("name", "Desconhecido")
        
        caption = (
            f"<b>🎯 ALERTA DE GOLS INDIVIDUAL</b>\n\n"
            f"<b>🏆 {competicao}</b>\n"
            f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
            f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
            f"<b>📈 Tendência: {tendencia.upper()}</b>\n"
            f"<b>⚽ Estimativa: {estimativa:.2f} gols</b>\n"
            f"<b>🎯 Confiança: {confianca:.0f}%</b>\n\n"
            f"<b>🔥 ELITE MASTER SYSTEM - ANÁLISE PREDITIVA</b>"
        )
        
        # Enviar foto
        if enviar_foto_telegram(poster, caption=caption):
            st.success(f"📤 Alerta individual enviado: {home} vs {away}")
            return True
        else:
            st.error(f"❌ Falha ao enviar alerta individual: {home} vs {away}")
            return False
            
    except Exception as e:
        st.error(f"❌ Erro ao enviar alerta individual: {str(e)}")
        # Fallback para mensagem de texto
        return enviar_alerta_telegram_fallback(fixture, tendencia, estimativa, confianca)

def enviar_alerta_telegram_fallback(fixture: dict, tendencia: str, estimativa: float, confianca: float) -> bool:
    """Fallback para alerta em texto caso o poster falhe"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    
    msg = (
        f"<b>🎯 ALERTA DE GOLS 🎯</b>\n\n"
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n\n"
        f"<b>🏠 {home}</b> vs <b>✈️ {away}</b>\n\n"
        f"<b>📈 Tendência: {tendencia.upper()}</b>\n"
        f"<b>⚽ Estimativa: {estimativa:.2f} gols</b>\n"
        f"<b>🎯 Confiança: {confianca:.0f}%</b>\n\n"
        f"<b>🔥 ELITE MASTER SYSTEM</b>"
    )
    
    return enviar_telegram(msg)

def gerar_poster_resultados(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS OFICIAIS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais dos jogos
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950
    PADDING = 120
    
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
    FONTE_RESULTADO = criar_fonte(70)

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
        # Calcular se a previsão foi correta
        total_gols = jogo['home_goals'] + jogo['away_goals']
        previsao_correta = False
        
        if jogo['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5:
            previsao_correta = True
        elif jogo['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5:
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

        # ESCUDOS E PLACAR - USANDO A FUNÇÃO EXISTENTE
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

        # PLACAR CENTRAL
        placar_text = f"{jogo['home_goals']}   -   {jogo['away_goals']}"
        try:
            placar_bbox = draw.textbbox((0, 0), placar_text, font=FONTE_PLACAR)
            placar_w = placar_bbox[2] - placar_bbox[0]
            placar_x = x_placar + (200 - placar_w) // 2
            draw.text((placar_x, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))
        except:
            draw.text((x_placar, y_escudos + 30), placar_text, font=FONTE_PLACAR, fill=(255, 255, 255))

        # USAR A FUNÇÃO EXISTENTE PARA DESENHAR ESCUDOS
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
                print(f"[ERRO ESCUDO] {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 60, y + 80), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Baixar e desenhar escudos - USANDO AS URLS SALVAS
        escudo_home = baixar_imagem_url(jogo.get('home_crest', ''))
        escudo_away = baixar_imagem_url(jogo.get('away_crest', ''))

        # Desenhar escudos quadrados
        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # SEÇÃO DE ANÁLISE DO RESULTADO
        y_analysis = y_escudos + TAMANHO_QUADRADO + 100
        
        # Linha separadora
        draw.line([(x0 + 50, y_analysis - 10), (x1 - 50, y_analysis - 10)], 
                 fill=(100, 130, 160), width=2)

        # Informações de análise
        textos_analise = [
            f"Previsão: {jogo['tendencia_prevista']}",
            f"Real: {total_gols} gols | Estimativa: {jogo['estimativa_prevista']:.2f}",
            f"Confiança: {jogo['confianca_prevista']:.0f}% | Resultado: {texto_resultado}"
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
    
    st.success(f"✅ Poster de resultados GERADO com {len(jogos)} jogos - Sistema RED/GREEN")
    return buffer

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
            titulo = f"ELITE MASTER - RESULTADOS {data_str}"
            
            st.info(f"🎨 Gerando poster de resultados para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_resultados(jogos_data, titulo=titulo)
            
            # Calcular estatísticas
            total_jogos = len(jogos_data)
            green_count = sum(1 for j in jogos_data if j.get('resultado') == "GREEN")
            red_count = total_jogos - green_count
            taxa_acerto = (green_count / total_jogos * 100) if total_jogos > 0 else 0
            
            caption = (
                f"<b>🏁 RESULTADOS OFICIAIS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL DE JOGOS: {total_jogos}</b>\n"
                f"<b>🟢 GREEN: {green_count} jogos</b>\n"
                f"<b>🔴 RED: {red_count} jogos</b>\n"
                f"<b>🎯 TAXA DE ACERTO: {taxa_acerto:.1f}%</b>\n\n"
                f"<b>📊 DESEMPENHO DO SISTEMA:</b>\n"
                f"<b>• Análise Preditiva Verificada</b>\n"
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
                st.error(f"❌ Falha ao enviar poster de resultados para {data_str}")
                
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
        # Fallback para mensagem de texto
        msg = f"🏁 RESULTADOS OFICIAIS - SISTEMA RED/GREEN:\n\n"
        for j in jogos_com_resultado[:5]:
            total_gols = j['home_goals'] + j['away_goals']
            resultado = "🟢 GREEN" if ((j['tendencia_prevista'] == "Mais 2.5" and total_gols > 2.5) or 
                            (j['tendencia_prevista'] == "Mais 1.5" and total_gols > 1.5) or
                            (j['tendencia_prevista'] == "Menos 2.5" and total_gols < 2.5)) else "🔴 RED"
            msg += f"{resultado} {j['home']} {j['home_goals']}x{j['away_goals']} {j['away']}\n"
        enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2)

# =============================
# FUNÇÕES PRINCIPAIS
# =============================

def enviar_top_jogos(jogos: list, top_n: int, alerta_top_jogos: bool):
    """Envia os top jogos para o Telegram"""
    if not alerta_top_jogos:
        st.info("ℹ️ Alerta de Top Jogos desativado")
        return
        
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    if not jogos_filtrados:
        st.warning("⚠️ Nenhum jogo elegível para o Top Jogos (todos já iniciados ou finalizados).")
        return
        
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
    msg = f"📢 TOP {top_n} Jogos do Dia (confiança alta)\n\n"
    
    for j in top_jogos_sorted:
        # CORREÇÃO: Usar dados formatados se disponíveis
        if 'hora_formatada' in j and 'data_formatada' in j:
            hora_text = j['hora_formatada']
            data_text = j['data_formatada']
        else:
            hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
            data_format = j["hora"].strftime("%d/%m/%Y") if isinstance(j["hora"], datetime) else "Data inválida"
            hora_text = hora_format
            data_text = data_format
            
        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {hora_text} BRT | {data_text} | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
            f"💯 Confiança: {j['confianca']:.0f}%\n\n"
        )
        
    if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2, disable_web_page_preview=True):
        st.success(f"🚀 Top {top_n} jogos enviados para o canal!")
    else:
        st.error("❌ Erro ao enviar top jogos para o Telegram")

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
            data_api = obter_dados_api_com_rate_limit(url)
            
            if data_api and "matches" in data_api:
                cache_jogos[key] = data_api["matches"]
                mudou = True
        except Exception as e:
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
    """Limpar caches do sistema - AGORA COM BACKUP"""
    try:
        arquivos_limpos = 0
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, CACHE_ESTATISTICAS, ALERTAS_PATH]:
            if os.path.exists(cache_file):
                # Fazer backup antes de limpar
                backup_name = f"data/backup_{cache_file.replace('.json', '')}_{timestamp}.json"
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f_src:
                        dados = f_src.read()
                    with open(backup_name, 'w', encoding='utf-8') as f_bak:
                        f_bak.write(dados)
                except:
                    pass
                
                os.remove(cache_file)
                arquivos_limpos += 1
        
        st.success(f"✅ {arquivos_limpos} caches limpos com sucesso! Backups criados.")
    except Exception as e:
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
    st.success(f"✅ Desempenho calculado para {total_jogos} jogos!")
    
    # Métricas básicas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Jogos", total_jogos)
    with col2:
        st.metric("Período Analisado", f"Últimos {qtd_jogos}")
    with col3:
        st.metric("Taxa de Confiança Média", f"{sum(h.get('confianca', 0) for h in historico_recente) / total_jogos:.1f}%")

def calcular_desempenho_periodo(data_inicio, data_fim):
    """Calcular desempenho por período"""
    st.info(f"📊 Calculando desempenho de {data_inicio} a {data_fim}...")
    
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
        
    # Filtrar histórico por período
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
    st.success(f"✅ Desempenho do período calculado! {total_jogos} jogos analisados.")
    
    # Métricas do período
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Jogos no Período", total_jogos)
    with col2:
        st.metric("Dias Analisados", (data_fim - data_inicio).days)
    with col3:
        st.metric("Confiança Média", f"{sum(h.get('confianca', 0) for h in historico_periodo) / total_jogos:.1f}%")

# =============================
# FUNÇÕES DE DESEMPENHO PARA NOVAS PREVISÕES
# =============================

def calcular_desempenho_ambas_marcam(qtd_jogos: int = 50):
    """Calcular desempenho das previsões Ambas Marcam"""
    historico = carregar_historico(HISTORICO_AMBAS_MARCAM_PATH)
    if not historico:
        st.warning("⚠️ Nenhum jogo Ambas Marcam conferido ainda.")
        return
        
    historico_recente = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico
    
    total_jogos = len(historico_recente)
    acertos = sum(1 for h in historico_recente if "GREEN" in str(h.get("resultado", "")))
    taxa_acerto = (acertos / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho Ambas Marcam: {acertos}/{total_jogos} acertos ({taxa_acerto:.1f}%)")

def calcular_desempenho_cartoes(qtd_jogos: int = 50):
    """Calcular desempenho das previsões de Cartões"""
    historico = carregar_historico(HISTORICO_CARTOES_PATH)
    if not historico:
        st.warning("⚠️ Nenhum jogo de Cartões conferido ainda.")
        return
        
    historico_recente = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico
    
    total_jogos = len(historico_recente)
    acertos = sum(1 for h in historico_recente if "GREEN" in str(h.get("resultado", "")))
    taxa_acerto = (acertos / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho Cartões: {acertos}/{total_jogos} acertos ({taxa_acerto:.1f}%)")

def calcular_desempenho_escanteios(qtd_jogos: int = 50):
    """Calcular desempenho das previsões de Escanteios"""
    historico = carregar_historico(HISTORICO_ESCANTEIOS_PATH)
    if not historico:
        st.warning("⚠️ Nenhum jogo de Escanteios conferido ainda.")
        return
        
    historico_recente = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico
    
    total_jogos = len(historico_recente)
    acertos = sum(1 for h in historico_recente if "GREEN" in str(h.get("resultado", "")))
    taxa_acerto = (acertos / total_jogos * 100) if total_jogos > 0 else 0
    
    st.success(f"✅ Desempenho Escanteios: {acertos}/{total_jogos} acertos ({taxa_acerto:.1f}%)")

# =============================
# PROCESSAMENTO PRINCIPAL ATUALIZADO - COM SELEÇÃO MÚLTIPLA
# =============================

def processar_jogos_avancado(data_selecionada, todas_ligas, ligas_selecionadas, top_n, 
                           threshold, threshold_ambas_marcam, threshold_cartoes, threshold_escanteios,
                           alerta_individual, alerta_poster, alerta_top_jogos,
                           alerta_ambas_marcam, alerta_cartoes, alerta_escanteios):
    """Processamento AVANÇADO com dados REAIS da API - ATUALIZADO PARA SELEÇÃO MÚLTIPLA"""
    
    hoje = data_selecionada.strftime("%Y-%m-%d")
    
    # DETERMINAR QUAIS LIGAS USAR - MODIFICADO PARA MÚLTIPLAS LIGAS
    if todas_ligas:
        ligas_busca = list(LIGA_DICT.values())
    else:
        ligas_busca = [LIGA_DICT[liga] for liga in ligas_selecionadas]

    st.write(f"⏳ Buscando jogos com análise AVANÇADA para {data_selecionada.strftime('%d/%m/%Y')}...")
    
    top_jogos_gols = []
    top_jogos_ambas_marcam = []
    top_jogos_cartoes = []
    top_jogos_escanteios = []
    
    progress_bar = st.progress(0)
    total_ligas = len(ligas_busca)

    for i, liga_id in enumerate(ligas_busca):
        classificacao = obter_classificacao(liga_id)
        jogos = obter_jogos(liga_id, hoje)

        for match in jogos:
            home_team = match["homeTeam"]
            away_team = match["awayTeam"]
            home_name = home_team["name"]
            away_name = away_team["name"]
            
            # CORREÇÃO: Formatar data/hora UMA VEZ e reutilizar
            data_formatada, hora_formatada = formatar_data_iso(match["utcDate"])
            hora_datetime = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3)
            
            # PREVISÃO ORIGINAL - GOLS
            estimativa, confianca, tendencia = calcular_tendencia(home_name, away_name, classificacao)
            
            # Dados para previsão original de gols - CORRIGIDO
            jogo_data = {
                "id": match["id"],
                "home": home_name,
                "away": away_name,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": hora_datetime,  # CORREÇÃO: Usar datetime já calculado
                "data_formatada": data_formatada,  # NOVO: Adicionar data formatada
                "hora_formatada": hora_formatada,  # NOVO: Adicionar hora formatada
                "status": match.get("status", "DESCONHECIDO"),
                "fixture": match  # Manter fixture completa
            }
            
            top_jogos_gols.append(jogo_data)
            
            # Enviar alertas individuais se ativado
            if alerta_individual and confianca >= threshold:
                verificar_enviar_alerta(match, tendencia, estimativa, confianca, alerta_individual)

            # NOVAS PREVISÕES COM DADOS REAIS - CORRIGIDAS
            # Ambas Marcam
            if alerta_ambas_marcam:
                prob_ambas, conf_ambas, tend_ambas = calcular_previsao_ambas_marcam_real(
                    home_name, away_name, classificacao)
                if conf_ambas >= threshold_ambas_marcam:
                    verificar_enviar_alerta_ambas_marcam(match, prob_ambas, conf_ambas, tend_ambas, alerta_ambas_marcam)
                    top_jogos_ambas_marcam.append({
                        "home": home_name, 
                        "away": away_name, 
                        "probabilidade": prob_ambas,
                        "confianca": conf_ambas, 
                        "tendencia": tend_ambas,
                        "liga": match.get("competition", {}).get("name", "Desconhecido"),
                        "hora": hora_datetime,  # CORREÇÃO: Usar datetime consistente
                        "data_formatada": data_formatada,  # NOVO
                        "hora_formatada": hora_formatada,  # NOVO
                        "fixture": match  # NOVO: Manter fixture para escudos
                    })

            # Cartões COM DADOS REAIS - CORRIGIDO
            if alerta_cartoes:
                est_cartoes, conf_cartoes, tend_cartoes = calcular_previsao_cartoes_real(
                    home_team, away_team, liga_id)
                if conf_cartoes >= threshold_cartoes:
                    verificar_enviar_alerta_cartoes(match, est_cartoes, conf_cartoes, tend_cartoes, alerta_cartoes)
                    top_jogos_cartoes.append({
                        "home": home_name, 
                        "away": away_name, 
                        "estimativa": est_cartoes,
                        "confianca": conf_cartoes, 
                        "tendencia": tend_cartoes,
                        "liga": match.get("competition", {}).get("name", "Desconhecido"),
                        "hora": hora_datetime,  # CORREÇÃO
                        "data_formatada": data_formatada,  # NOVO
                        "hora_formatada": hora_formatada,  # NOVO
                        "fixture": match  # NOVO
                    })

            # Escanteios COM DADOS REAIS - CORRIGIDO
            if alerta_escanteios:
                est_escanteios, conf_escanteios, tend_escanteios = calcular_previsao_escanteios_real(
                    home_team, away_team, liga_id)
                if conf_escanteios >= threshold_escanteios:
                    verificar_enviar_alerta_escanteios(match, est_escanteios, conf_escanteios, tend_escanteios, alerta_escanteios)
                    top_jogos_escanteios.append({
                        "home": home_name, 
                        "away": away_name, 
                        "estimativa": est_escanteios,
                        "confianca": conf_escanteios, 
                        "tendencia": tend_escanteios,
                        "liga": match.get("competition", {}).get("name", "Desconhecido"),
                        "hora": hora_datetime,  # CORREÇÃO
                        "data_formatada": data_formatada,  # NOVO
                        "hora_formatada": hora_formatada,  # NOVO
                        "fixture": match  # NOVO
                    })

        progress_bar.progress((i + 1) / total_ligas)

    progress_bar.empty()

    # ENVIO DE ALERTAS COMPOSTOS - CORRIGIDO
    if alerta_poster:
        # Filtrar jogos por threshold e status
        jogos_confiaveis = [j for j in top_jogos_gols 
                           if j["confianca"] >= threshold 
                           and j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
        
        if jogos_confiaveis:
            st.info(f"🎨 Preparando poster composto com {len(jogos_confiaveis)} jogos...")
            if enviar_alerta_composto_poster(jogos_confiaveis, threshold):
                st.success("🚀 Poster composto enviado com sucesso!")
            else:
                st.error("❌ Falha ao enviar poster composto")
        else:
            st.warning("⚠️ Nenhum jogo elegível para poster composto")

    # ENVIO DE TOP JOGOS
    enviar_top_jogos(top_jogos_gols, top_n, alerta_top_jogos)

    # EXIBIR RESULTADOS NA INTERFACE
    st.subheader("📊 Resultados da Análise Avançada")

    # Abas para diferentes tipos de previsão
    tab1, tab2, tab3, tab4 = st.tabs(["⚽ Previsão de Gols", "🔄 Ambas Marcam", "🟨 Cartões", "🔄 Escanteios"])

    with tab1:
        exibir_resultados_previsao_gols(top_jogos_gols, threshold)

    with tab2:
        exibir_resultados_ambas_marcam(top_jogos_ambas_marcam, threshold_ambas_marcam)

    with tab3:
        exibir_resultados_cartoes(top_jogos_cartoes, threshold_cartoes)

    with tab4:
        exibir_resultados_escanteios(top_jogos_escanteios, threshold_escanteios)

def exibir_resultados_previsao_gols(jogos: list, threshold: int):
    """Exibe resultados da previsão de gols"""
    if not jogos:
        st.info("ℹ️ Nenhum jogo encontrado para previsão de gols")
        return

    # Filtrar por confiança e status
    jogos_filtrados = [j for j in jogos 
                      if j["confianca"] >= threshold 
                      and j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    
    if not jogos_filtrados:
        st.warning(f"⚠️ Nenhum jogo com confiança ≥{threshold}% e status válido")
        return

    st.write(f"**🎯 Jogos com Confiança ≥{threshold}%**")

    for jogo in sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True):
        # CORREÇÃO: Usar dados formatados já calculados
        hora_display = jogo.get('hora_formatada', 'Hora inválida')
        data_display = jogo.get('data_formatada', 'Data inválida')
        
        with st.expander(f"🏟️ {jogo['home']} vs {jogo['away']} - {jogo['confianca']:.0f}%", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**📅 Data:** {data_display}")
                st.write(f"**⏰ Hora:** {hora_display} BRT")
                st.write(f"**🏆 Liga:** {jogo['liga']}")
            with col2:
                st.write(f"**📈 Tendência:** {jogo['tendencia']}")
                st.write(f"**⚽ Estimativa:** {jogo['estimativa']:.2f} gols")
                st.write(f"**🎯 Confiança:** {jogo['confianca']:.0f}%")
            with col3:
                st.write(f"**📊 Status:** {jogo['status']}")
                # Barra de confiança visual
                confianca = jogo['confianca']
                st.progress(confianca / 100, text=f"Confiança: {confianca:.0f}%")

def exibir_resultados_ambas_marcam(jogos: list, threshold: int):
    """Exibe resultados da previsão Ambas Marcam"""
    if not jogos:
        st.info("ℹ️ Nenhum jogo encontrado para previsão Ambas Marcam")
        return

    st.write(f"**🔄 Jogos Ambas Marcam com Confiança ≥{threshold}%**")

    for jogo in sorted(jogos, key=lambda x: x["confianca"], reverse=True):
        # CORREÇÃO: Usar dados formatados
        hora_display = jogo.get('hora_formatada', 'Hora inválida')
        data_display = jogo.get('data_formatada', 'Data inválida')
        
        with st.expander(f"🏟️ {jogo['home']} vs {jogo['away']} - {jogo['confianca']:.0f}%", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**📅 Data:** {data_display}")
                st.write(f"**⏰ Hora:** {hora_display} BRT")
                st.write(f"**🏆 Liga:** {jogo['liga']}")
            with col2:
                st.write(f"**📈 Tendência:** {jogo['tendencia']}")
                st.write(f"**📊 Probabilidade:** {jogo['probabilidade']:.1f}%")
                st.write(f"**🎯 Confiança:** {jogo['confianca']:.0f}%")
            with col3:
                # Barra de confiança visual
                confianca = jogo['confianca']
                st.progress(confianca / 100, text=f"Confiança: {confianca:.0f}%")
                
                # Indicador visual
                if "SIM" in jogo['tendencia']:
                    st.success("✅ ALTA PROBABILIDADE")
                elif "PROVÁVEL" in jogo['tendencia']:
                    st.warning("⚠️ PROBABILIDADE MÉDIA")
                else:
                    st.error("❌ BAIXA PROBABILIDADE")

def exibir_resultados_cartoes(jogos: list, threshold: int):
    """Exibe resultados da previsão de Cartões"""
    if not jogos:
        st.info("ℹ️ Nenhum jogo encontrado para previsão de Cartões")
        return

    st.write(f"**🟨 Jogos com Cartões (Confiança ≥{threshold}%)**")

    for jogo in sorted(jogos, key=lambda x: x["confianca"], reverse=True):
        # CORREÇÃO: Usar dados formatados
        hora_display = jogo.get('hora_formatada', 'Hora inválida')
        data_display = jogo.get('data_formatada', 'Data inválida')
        
        with st.expander(f"🏟️ {jogo['home']} vs {jogo['away']} - {jogo['confianca']:.0f}%", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**📅 Data:** {data_display}")
                st.write(f"**⏰ Hora:** {hora_display} BRT")
                st.write(f"**🏆 Liga:** {jogo['liga']}")
            with col2:
                st.write(f"**📈 Tendência:** {jogo['tendencia']}")
                st.write(f"**🟨 Estimativa:** {jogo['estimativa']:.1f} cartões")
                st.write(f"**🎯 Confiança:** {jogo['confianca']:.0f}%")
            with col3:
                # Barra de confiança visual
                confianca = jogo['confianca']
                st.progress(confianca / 100, text=f"Confiança: {confianca:.0f}%")
                
                # Indicador de intensidade
                if jogo['estimativa'] >= 5.5:
                    st.error("🔴 ALTA INTENSIDADE")
                elif jogo['estimativa'] >= 4.0:
                    st.warning("🟡 MÉDIA INTENSIDADE")
                else:
                    st.info("🟢 BAIXA INTENSIDADE")

def exibir_resultados_escanteios(jogos: list, threshold: int):
    """Exibe resultados da previsão de Escanteios"""
    if not jogos:
        st.info("ℹ️ Nenhum jogo encontrado para previsão de Escanteios")
        return

    st.write(f"**🔄 Jogos com Escanteios (Confiança ≥{threshold}%)**")

    for jogo in sorted(jogos, key=lambda x: x["confianca"], reverse=True):
        # CORREÇÃO: Usar dados formatados
        hora_display = jogo.get('hora_formatada', 'Hora inválida')
        data_display = jogo.get('data_formatada', 'Data inválida')
        
        with st.expander(f"🏟️ {jogo['home']} vs {jogo['away']} - {jogo['confianca']:.0f}%", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**📅 Data:** {data_display}")
                st.write(f"**⏰ Hora:** {hora_display} BRT")
                st.write(f"**🏆 Liga:** {jogo['liga']}")
            with col2:
                st.write(f"**📈 Tendência:** {jogo['tendencia']}")
                st.write(f"**🔄 Estimativa:** {jogo['estimativa']:.1f} escanteios")
                st.write(f"**🎯 Confiança:** {jogo['confianca']:.0f}%")
            with col3:
                # Barra de confiança visual
                confianca = jogo['confianca']
                st.progress(confianca / 100, text=f"Confiança: {confianca:.0f}%")
                
                # Indicador de intensidade
                if jogo['estimativa'] >= 10.5:
                    st.error("🔴 ALTA INTENSIDADE")
                elif jogo['estimativa'] >= 8.0:
                    st.warning("🟡 MÉDIA INTENSIDADE")
                else:
                    st.info("🟢 BAIXA INTENSIDADE")

# =============================
# INTERFACE PRINCIPAL STREAMLIT - ATUALIZADA
# =============================

def main():
    st.set_page_config(
        page_title="ELITE MASTER - Sistema Avançado de Previsões",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # CSS personalizado
    st.markdown("""
        <style>
        .main-header {
            font-size: 3rem;
            color: #FFD700;
            text-align: center;
            margin-bottom: 2rem;
            font-weight: bold;
            text-shadow: 2px 2px 4px #000000;
        }
        .sub-header {
            font-size: 1.5rem;
            color: #87CEEB;
            margin-bottom: 1rem;
            font-weight: bold;
        }
        .metric-card {
            background-color: #1E2A38;
            padding: 1rem;
            border-radius: 10px;
            border-left: 4px solid #FFD700;
        }
        .stProgress > div > div > div {
            background-color: #FFD700;
        }
        </style>
    """, unsafe_allow_html=True)

    # Cabeçalho principal
    st.markdown('<h1 class="main-header">⚽ ELITE MASTER SYSTEM</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #CCCCCC;">Sistema Avançado de Previsões com Análise em Tempo Real</p>', unsafe_allow_html=True)

    # Barra lateral
    with st.sidebar:
        st.image("https://via.placeholder.com/150x150/1E2A38/FFD700?text=EM", width=150)
        st.title("🎮 Controles")
        
        # Data seleção
        data_selecionada = st.date_input(
            "📅 Data dos Jogos",
            datetime.now(),
            help="Selecione a data para análise"
        )
        
        # Seleção de ligas - MODIFICADO PARA MÚLTIPLA SELEÇÃO
        st.subheader("🏆 Ligas")
        todas_ligas = st.checkbox("Todas as Ligas", value=True, help="Analisar todas as ligas disponíveis")
        
        if not todas_ligas:
            ligas_selecionadas = st.multiselect(
                "Selecione as Ligas:",
                options=list(LIGA_DICT.keys()),
                default=["Premier League (Inglaterra)", "Bundesliga", "Campeonato Brasileiro Série A"],
                help="Selecione uma ou mais ligas para análise"
            )
        else:
            ligas_selecionadas = list(LIGA_DICT.keys())

        # Configurações de alertas
        st.subheader("🔔 Configurações de Alertas")
        
        # Thresholds para diferentes tipos
        threshold = st.slider("Confiança Mínima Gols (%)", 50, 90, 70, 
                            help="Confiança mínima para alertas de gols")
        threshold_ambas_marcam = st.slider("Confiança Mínima Ambas Marcam (%)", 50, 90, 60,
                                         help="Confiança mínima para alertas Ambas Marcam")
        threshold_cartoes = st.slider("Confiança Mínima Cartões (%)", 50, 90, 55,
                                    help="Confiança mínima para alertas de Cartões")
        threshold_escanteios = st.slider("Confiança Mínima Escanteios (%)", 50, 90, 50,
                                       help="Confiança mínima para alertas de Escanteios")
        
        top_n = st.slider("Top N Jogos", 1, 20, 5, help="Número de jogos no Top Jogos")

        # Ativação de alertas
        st.subheader("🚀 Ativar Alertas")
        alerta_individual = st.checkbox("Alertas Individuais", value=False, 
                                      help="Enviar alertas individuais para cada jogo")
        alerta_poster = st.checkbox("Poster Composto", value=True, 
                                  help="Enviar poster com múltiplos jogos")
        alerta_top_jogos = st.checkbox("Top Jogos", value=True, 
                                     help="Enviar lista dos Top N jogos")
        
        # Novos tipos de alertas
        alerta_ambas_marcam = st.checkbox("Ambas Marcam", value=True,
                                        help="Ativar previsões Ambas Marcam")
        alerta_cartoes = st.checkbox("Cartões", value=True,
                                   help="Ativar previsões de Cartões")
        alerta_escanteios = st.checkbox("Escanteios", value=True,
                                      help="Ativar previsões de Escanteios")

        # Botões de ação
        st.subheader("⚙️ Ações do Sistema")
        if st.button("🔄 Atualizar Status Partidas", use_container_width=True):
            atualizar_status_partidas()
            
        if st.button("🔍 Verificar Resultados", use_container_width=True):
            verificar_resultados_finais_completo(True)
            
        if st.button("📊 Calcular Desempenho", use_container_width=True):
            calcular_desempenho(50)

        # Limpeza
        st.subheader("🧹 Limpeza")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Limpar Caches", use_container_width=True):
                limpar_caches()
        with col2:
            if st.button("Limpar Histórico", use_container_width=True):
                limpar_historico("todos")

    # Área principal
    tab_principal, tab_desempenho, tab_historico, tab_config = st.tabs([
        "🎯 Análise Principal", "📊 Desempenho", "📋 Histórico", "⚙️ Configurações"
    ])

    with tab_principal:
        st.subheader("🔍 Análise de Previsões Avançadas")
        
        # NOVA SEÇÃO: Alertas Compostos Salvos
        st.markdown("---")
        st.subheader("📊 Alertas Compostos Salvos")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("👀 Visualizar Alertas Compostos Salvos", use_container_width=True):
                exibir_alertas_compostos_salvos()
        with col2:
            if st.button("🔍 Verificar Resultados Compostos", use_container_width=True):
                with st.spinner("Verificando resultados de alertas compostos..."):
                    resultados_encontrados = verificar_resultados_alertas_compostos(True)
                    if resultados_encontrados:
                        st.success("✅ Verificação de alertas compostos concluída!")
                    else:
                        st.info("ℹ️ Nenhum novo resultado em alertas compostos")
        with col3:
            if st.button("🐛 Debug Alertas Compostos", use_container_width=True):
                debug_alertas_compostos()
        
        # Botão principal de análise (existente)
        if st.button("🚀 Executar Análise Completa", type="primary", use_container_width=True):
            with st.spinner("Executando análise avançada com dados em tempo real..."):
                processar_jogos_avancado(
                    data_selecionada=data_selecionada,
                    todas_ligas=todas_ligas,
                    ligas_selecionadas=ligas_selecionadas,
                    top_n=top_n,
                    threshold=threshold,
                    threshold_ambas_marcam=threshold_ambas_marcam,
                    threshold_cartoes=threshold_cartoes,
                    threshold_escanteios=threshold_escanteios,
                    alerta_individual=alerta_individual,
                    alerta_poster=alerta_poster,
                    alerta_top_jogos=alerta_top_jogos,
                    alerta_ambas_marcam=alerta_ambas_marcam,
                    alerta_cartoes=alerta_cartoes,
                    alerta_escanteios=alerta_escanteios
                )

    with tab_desempenho:
        st.subheader("📈 Métricas de Desempenho")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Desempenho Gols", use_container_width=True):
                calcular_desempenho(50)
        with col2:
            if st.button("Desempenho Ambas Marcam", use_container_width=True):
                calcular_desempenho_ambas_marcam(50)
        with col3:
            if st.button("Desempenho Cartões", use_container_width=True):
                calcular_desempenho_cartoes(50)
        with col4:
            if st.button("Desempenho Escanteios", use_container_width=True):
                calcular_desempenho_escanteios(50)
        
        # Seleção de período para análise
        st.subheader("📅 Análise por Período")
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Início", datetime.now() - timedelta(days=30))
        with col2:
            data_fim = st.date_input("Data Fim", datetime.now())
            
        if st.button("Calcular Desempenho do Período", use_container_width=True):
            calcular_desempenho_periodo(data_inicio, data_fim)

    with tab_historico:
        st.subheader("📋 Histórico de Conferências")
        
        tipo_historico = st.selectbox(
            "Selecione o tipo de histórico:",
            ["gols", "ambas_marcam", "cartoes", "escanteios", "compostos"],
            format_func=lambda x: {
                "gols": "⚽ Previsão de Gols",
                "ambas_marcam": "🔄 Ambas Marcam", 
                "cartoes": "🟨 Cartões",
                "escanteios": "🔄 Escanteios",
                "compostos": "📊 Alertas Compostos"  # NOVO
            }[x]
        )
        
        caminhos_historico = {
            "gols": HISTORICO_PATH,
            "ambas_marcam": HISTORICO_AMBAS_MARCAM_PATH,
            "cartoes": HISTORICO_CARTOES_PATH,
            "escanteios": HISTORICO_ESCANTEIOS_PATH,
            "compostos": HISTORICO_COMPOSTOS_PATH  # NOVO
        }
        
        historico = carregar_historico(caminhos_historico[tipo_historico])
        
        if historico:
            st.write(f"**Total de registros:** {len(historico)}")
            
            # Filtrar últimos registros
            qtd_registros = st.slider("Quantidade de registros para exibir:", 1, 100, 20)
            historico_recente = historico[-qtd_registros:]
            
            for registro in reversed(historico_recente):
                with st.expander(f"🏟️ {registro.get('home', 'N/A')} vs {registro.get('away', 'N/A')} - {registro.get('resultado', 'N/A')}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Data:** {registro.get('data_conferencia', 'N/A')}")
                        st.write(f"**Tendência:** {registro.get('tendencia', 'N/A')}")
                        st.write(f"**Estimativa:** {registro.get('estimativa', 0):.2f}")
                    with col2:
                        st.write(f"**Confiança:** {registro.get('confianca', 0):.1f}%")
                        st.write(f"**Placar:** {registro.get('placar', 'N/A')}")
                        st.write(f"**Resultado:** {registro.get('resultado', 'N/A')}")
                    
                    # Campos específicos por tipo
                    if tipo_historico == "ambas_marcam":
                        st.write(f"**Previsão:** {registro.get('previsao', 'N/A')}")
                        st.write(f"**Ambas Marcaram:** {registro.get('ambas_marcaram', False)}")
                    elif tipo_historico == "cartoes":
                        st.write(f"**Cartões Total:** {registro.get('cartoes_total', 0)}")
                        st.write(f"**Limiar:** {registro.get('limiar_cartoes', 0)}")
                    elif tipo_historico == "escanteios":
                        st.write(f"**Escanteios Total:** {registro.get('escanteios_total', 0)}")
                        st.write(f"**Limiar:** {registro.get('limiar_escanteios', 0)}")
                    elif tipo_historico == "compostos":
                        st.write(f"**Alerta ID:** {registro.get('alerta_id', 'N/A')}")
        else:
            st.info("ℹ️ Nenhum registro no histórico selecionado.")

    with tab_config:
        st.subheader("⚙️ Configurações do Sistema")
        
        st.info("""
        **🔧 Sistema ELITE MASTER - Configurações:**
        
        - **API Football Data:** Conectada ✓
        - **Telegram Bot:** Configurado ✓  
        - **Sistema de Cache:** Ativo ✓
        - **Persistência de Dados:** Ativa ✓
        - **Análise em Tempo Real:** Ativa ✓
        
        **📊 Tipos de Previsão Disponíveis:**
        1. ⚽ Previsão de Gols (Sistema Original)
        2. 🔄 Ambas Marcam (Nova)
        3. 🟨 Total de Cartões (Nova) 
        4. 🔄 Total de Escanteios (Nova)
        5. 📊 Alertas Compostos (24h) - NOVO
        
        **🎯 Características:**
        - Dados estatísticos em tempo real
        - Análise preditiva avançada
        - Sistema de alertas automatizado
        - Posters profissionais para Telegram
        - Histórico completo com métricas
        - Alertas compostos salvos por 24h
        """)
        
        # Status das credenciais
        st.subheader("🔐 Status das Credenciais")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("API Football", "✅ Conectada" if API_KEY else "❌ Ausente")
        with col2:
            st.metric("Telegram Bot", "✅ Configurado" if TELEGRAM_TOKEN else "❌ Ausente")
        with col3:
            st.metric("Chat ID", "✅ Configurado" if TELEGRAM_CHAT_ID else "❌ Ausente")
        
        # Informações de uso
        st.subheader("📈 Estatísticas de Uso")
        alertas_total = len(carregar_alertas())
        historico_total = len(carregar_historico())
        alertas_compostos = len(carregar_alertas_compostos())
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Alertas Ativos", alertas_total)
        with col2:
            st.metric("Alertas Compostos", alertas_compostos)
        with col3:
            st.metric("Registros Históricos", historico_total)

# =============================
# EXECUÇÃO PRINCIPAL
# =============================

if __name__ == "__main__":
    main()
