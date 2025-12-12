
import streamlit as st
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import io
import pandas as pd
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging

# =============================
# Configurações e Segurança
# =============================

# Versão de teste - manter valores padrão
API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
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
APOSTAS_PATH = "apostas_salvas.json"  # NOVO: Caminho para salvar apostas

# Histórico de conferências
HISTORICO_PATH = "historico_conferencias.json"

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
                
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO, APOSTAS_PATH]:
                agora = datetime.now().timestamp()
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT and caminho != APOSTAS_PATH:
                        return {}
                else:
                    # Se não tem timestamp, verificar modificação do arquivo
                    if agora - os.path.getmtime(caminho) > CACHE_TIMEOUT and caminho != APOSTAS_PATH:
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

# =============================
# NOVO: Funções para Apostas
# =============================
def carregar_apostas() -> list:
    """Carrega apostas salvas"""
    apostas = carregar_json(APOSTAS_PATH)
    if isinstance(apostas, list):
        return apostas
    elif isinstance(apostas, dict) and 'apostas' in apostas:
        return apostas['apostas']
    return []

def salvar_apostas(apostas: list):
    """Salva apostas"""
    dados = {
        'apostas': apostas,
        '_timestamp': datetime.now().timestamp(),
        '_ultima_atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    salvar_json(APOSTAS_PATH, dados)

def converter_top_jogos_para_apostas(top_jogos: list, top_n: int = 5):
    """Converte os top jogos em formato de apostas estilo 'Minhas Apostas'"""
    if not top_jogos:
        return []
    
    apostas = []
    
    # Ordenar por confiança e pegar apenas os N melhores
    jogos_ordenados = sorted(top_jogos, key=lambda x: x.get("confianca", 0), reverse=True)
    top_jogos_selecionados = jogos_ordenados[:top_n]
    
    for i, jogo in enumerate(top_jogos_selecionados):
        # Criar odds baseada na confiança (quanto maior a confiança, menor as odds)
        confianca = jogo.get("confianca", 50)
        
        # Fórmula: odds entre 1.20 e 2.00, inversamente proporcional à confiança
        odds_base = 2.0 - (confianca / 100) * 0.8
        odds = round(max(1.20, min(2.00, odds_base)), 2)
        
        # Formatar data
        if isinstance(jogo.get("hora"), datetime):
            data_str = jogo["hora"].strftime("%d/%m/%Y • %H:%M")
        else:
            data_str = datetime.now().strftime("%d/%m/%Y • %H:%M")
        
        # Determinar resultado baseado na tendência (simulação)
        tendencia = jogo.get("tendencia", "")
        resultado = "won" if "Mais" in tendencia else "lost"  # Simplificação
        
        aposta = {
            "id": i + 1,
            "market": "Mais de 2,5 • Total de Gols",
            "odds": odds,
            "teams": f"{jogo.get('home', 'Time A')} - {jogo.get('away', 'Time B')}",
            "date": data_str,
            "result": resultado,
            "selected": True,  # Todos selecionados por padrão
            "liga": jogo.get("liga", "Desconhecido"),
            "confianca_original": confianca,
            "tendencia_original": tendencia,
            "estimativa_original": jogo.get("estimativa", 0)
        }
        apostas.append(aposta)
    
    return apostas

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
        "resultado": resultado.get("resultado", "⏳ Aguardando")
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
# Utilitários de Data e Formatação - CORRIGIDOS
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    """Formata data ISO - VERSÃO CORRIGIDA COM FUSO HORÁRIO"""
    try:
        # Converter para datetime con timezone awareness
        if data_iso.endswith('Z'):
            data_iso = data_iso.replace('Z', '+00:00')
        
        # Crear datetime con timezone UTC
        data_utc = datetime.fromisoformat(data_iso)
        
        # Si no tiene timezone, asumir UTC
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
    """Converte string ISO para datetime con fuso correto - VERSÃO CORRIGIDA"""
    try:
        if data_iso.endswith('Z'):
            data_iso = data_iso.replace('Z', '+00:00')
        
        data_utc = datetime.fromisoformat(data_iso)
        
        # Si no tiene timezone, asumir UTC
        if data_utc.tzinfo is None:
            data_utc = data_utc.replace(tzinfo=timezone.utc)
        
        # Converter para horário de Brasília
        fuso_brasilia = timezone(timedelta(hours=-3))
        return data_utc.astimezone(fuso_brasilia)
        
    except Exception as e:
        logging.error(f"Erro ao converter data {data_iso}: {e}")
        return datetime.now()

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palabras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palabras])
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
# Comunicação con APIs
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

def obter_dados_api(url: str, timeout: int = 15) -> dict | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logging.error(f"Timeout na requisição: {url}")
        return None
    except requests.RequestException as e:
        logging.error(f"Erro na requisição API {url}: {e}")
        st.error(f"Erro na requisição API: {e}")
        return None

def obter_classificacao(liga_id: str) -> dict:
    cache = carregar_cache_classificacao()
    if liga_id in cache:
        return cache[liga_id]

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
    data_api = obter_dados_api(url)
    jogos = data_api.get("matches", []) if data_api else []
    cache[key] = jogos
    salvar_cache_jogos(cache)
    return jogos

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
# Lógica de Análise e Alertas
# =============================
def calcular_tendencia(home: str, away: str, classificacao: dict) -> tuple[float, float, str]:
    """Calcula tendência - VERSÃO CORRIGIDA"""
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
    
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)

    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away

    # Cálculo mais preciso da estimativa
    estimativa_home = (media_home_feitos + media_away_sofridos) / 2
    estimativa_away = (media_away_feitos + media_home_sofridos) / 2
    estimativa_total = estimativa_home + estimativa_away

    # Lógica de tendência corrigida
    if estimativa_total >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa_total - 3.0) * 12)
    elif estimativa_total >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa_total - 2.0) * 10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 50 + (2.5 - estimativa_total) * 15)

    return round(estimativa_total, 2), round(confianca, 1), tendencia

def gerar_poster_individual_westham(fixture: dict, tendencia: str, estimativa: float, confianca: float) -> io.BytesIO:
    """
    Gera poster individual no estilo West Ham para alertas individuais
    """
    # Configurações
    LARGURA = 1800
    ALTURA = 1200
    PADDING = 80

    # Crear canvas
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

    # Título PRINCIPAL - ALERTA
    titulo_text = "🎯 ALERTA DE GOLS 🎯"
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
    TAMANHO_ESCUDO = 180
    TAMANHO_QUADRADO = 220
    ESPACO_ENTRE_ESCUDOS = 500

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

    # SEÇÃO DE ANÁLISE
    y_analysis = y_escudos + TAMANHO_QUADRADO + 120
    
    # Linha separadora
    draw.line([(PADDING + 50, y_analysis - 20), (LARGURA - PADDING - 50, y_analysis - 20)], 
             fill=(100, 130, 160), width=3)

    # Informações de análise con destaque
    tendencia_emoji = "📈" if "Mais" in tendencia else "📉" if "Menos" in tendencia else "⚡"
    
    textos_analise = [
        f"{tendencia_emoji} TENDÊNCIA: {tendencia.upper()}",
        f"⚽ ESTIMATIVA: {estimativa:.2f} GOLS",
        f"🎯 CONFIANÇA: {confianca:.0f}%",
    ]
    
    cores = [(255, 215, 0), (100, 200, 255), (100, 255, 100)]
    
    for i, (text, cor) in enumerate(zip(textos_analise, cores)):
        try:
            bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
            w = bbox[2] - bbox[0]
            draw.text(((LARGURA - w) // 2, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)
        except:
            draw.text((PADDING + 100, y_analysis + i * 70), text, font=FONTE_ANALISE, fill=cor)

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
    """Envia alerta individual con poster estilo West Ham"""
    try:
        # Gerar poster individual
        poster = gerar_poster_individual_westham(fixture, tendencia, estimativa, confianca)
        
        # Crear caption para o Telegram
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
        logging.error(f"Erro ao enviar alerta individual: {str(e)}")
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
# SISTEMA DE ALERTAS DE RESULTADOS CON POSTERS RED/GREEN
# =============================

def verificar_resultados_finais(alerta_resultados: bool):
    """Verifica resultados finais dos jogos e envia alertas - VERSÃO CORRIGIDA"""
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para verificar resultados.")
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        # Pular se já foi conferido
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture_data = obter_dados_api(url)
            
            if not fixture_data:
                continue
                
            match = fixture_data.get('match', fixture_data)  # Algumas APIs usam 'match'
            status = match.get("status", "")
            score = match.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
            # Verificar se jogo terminou e tem resultado válido
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
                    "confianca_prevista": alerta.get("confianca", 0),
                    "escudo_home": match.get("homeTeam", {}).get("crest") or "",
                    "escudo_away": match.get("awayTeam", {}).get("crest") or ""
                }
                
                jogos_com_resultado.append(jogo_resultado)
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            logging.error(f"Erro ao verificar jogo {fixture_id}: {e}")
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

def gerar_poster_resultados(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS OFICIAIS") -> io.BytesIO:
    """
    Gera poster profesional con resultados finais dos jogos - VERSÃO CORRIGIDA CON RED/GREEN
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950  # Ajustado para melhor layout
    PADDING = 120
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Crear canvas
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

        # Caixa do jogo con borda colorida conforme resultado
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo con borda colorida (VERDE ou VERMELHA)
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

        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get("escudo_home", ""))
        escudo_away = baixar_imagem_url(jogo.get("escudo_away", ""))

        def desenhar_escudo_resultado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo circular
            draw.ellipse([x, y, x + tamanho_quadrado, y + tamanho_quadrado], 
                        fill=(255, 255, 255), outline=(220, 220, 220), width=3)

            if logo_img is None:
                draw.ellipse([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(80, 80, 80))
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
                draw.ellipse([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 50, y + 65), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Desenhar escudos circulares
        desenhar_escudo_resultado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_resultado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

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
    
    st.success(f"✅ Poster de resultados GERADO con {len(jogos)} jogos - Sistema RED/GREEN")
    return buffer

def enviar_alerta_resultados_poster(jogos_com_resultado: list):
    """Envia alerta de resultados con poster para o Telegram - VERSÃO ATUALIZADA CON RED/GREEN"""
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
            
            st.info(f"🎨 Gerando poster de resultados para {data_str} con {len(jogos_data)} jogos...")
            
            poster = gerar_poster_resultados(jogos_data, titulo=titulo)
            
            # Calcular estatísticas ATUALIZADAS
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
        logging.error(f"Erro crítico ao gerar/enviar poster de resultados: {str(e)}")
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
# Funções de geração de imagem
# =============================
def baixar_imagem_url(url: str, timeout: int = 8) -> Image.Image | None:
    """Tenta baixar uma imagem - VERSÃO CORRIGIDA"""
    if not url or url == "":
        return None
        
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        
        # Verificar se é realmente uma imagem
        content_type = resp.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logging.warning(f"URL não é uma imagem: {content_type}")
            return None
            
        img = Image.open(io.BytesIO(resp.content))
        return img.convert("RGBA")
        
    except Exception as e:
        logging.error(f"Erro ao baixar imagem {url}: {e}")
        return None

def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
    """Cria fonte con fallback robusto - VERSÃO CORRIGIDA"""
    try:
        # Tentar fontes do sistema
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
        
        # Fallback para fonte padrão do PIL
        return ImageFont.load_default()
        
    except Exception as e:
        logging.error(f"Erro ao carregar fonte: {e}")
        return ImageFont.load_default()

def gerar_poster_westham_style(jogos: list, titulo: str = "ELITE MASTER - ALERTA DE GOLS") -> io.BytesIO:
    """
    Gera poster no estilo West Ham vs Burnley
    """
    # Configurações
    LARGURA = 2000
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 950
    PADDING = 120
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Crear canvas
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
        
        # Fundo con borda
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=(60, 80, 100), width=4)

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

        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get("escudo_home", ""))
        escudo_away = baixar_imagem_url(jogo.get("escudo_away", ""))

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

        # SEÇÃO DE ANÁLISE
        y_analysis = y_escudos + TAMANHO_QUADRADO + 150
        
        # Linha separadora
        draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)

        # Informações de análise
        tendencia_emoji = "" if "Mais" in jogo['tendencia'] else "" if "Menos" in jogo['tendencia'] else "⚡"
        textos_analise = [
            f"{tendencia_emoji} Tendência: {jogo['tendencia']}",
            f"Estimativa: {jogo['estimativa']:.2f} gols",
            f"Confiança: {jogo['confianca']:.0f}%",
        ]
        
        cores = [(255, 215, 0), (100, 200, 255), (100, 255, 100)]
        
        for i, (text, cor) in enumerate(zip(textos_analise, cores)):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                draw.text(((LARGURA - w) // 2, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)
            except:
                draw.text((PADDING + 120, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)

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
    
    st.success(f"✅ Poster estilo West Ham GERADO con {len(jogos)} jogos")
    return buffer

def enviar_alerta_westham_style(jogos_conf: list, threshold: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Envia alerta no estilo West Ham"""
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
            
            st.info(f"🎨 Gerando poster para {data_str} con {len(jogos_data)} jogos...")
            
            poster = gerar_poster_westham_style(jogos_data, titulo=titulo)
            
            caption = (
                f"<b>🎯 ALERTA DE GOLS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                f"<b>⚽ CONFIANÇA MÍNIMA: {threshold}%</b>\n\n"
                f"<b>🔮 ANÁLISE PREDITIVA DE GOLS</b>\n"
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
        msg = f"🔥 Jogos ≥{threshold}% (Erro na imagem):\n"
        for j in jogos_conf[:5]:
            msg += f"🏟️ {j['home']} vs {j['away']} | {j['tendencia']} | Conf: {j['confianca']:.0f}%\n"
        enviar_telegram(msg, chat_id=chat_id)

# =============================
# NOVO: Sistema de Alertas de Apostas - Estilo "Minhas Apostas"
# =============================
def render_bet_alert_css():
    """Renderiza o CSS para o alerta de apostas estilo 'Minhas Apostas'"""
    return """
    <style>
    /* Estilos para o Alerta de Apostas */
    .alert-bet-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        display: none;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        padding: 20px;
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .alert-bet-container.show {
        opacity: 1;
    }
    
    .alert-bet-box {
        width: 100%;
        max-width: 850px;
        background: #0f172a;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        overflow: hidden;
        border: 1px solid #1e293b;
        max-height: 85vh;
        overflow-y: auto;
        transform: scale(0.95);
        transition: transform 0.3s ease;
    }
    
    .alert-bet-container.show .alert-bet-box {
        transform: scale(1);
    }
    
    .alert-bet-header {
        background: #1e293b;
        padding: 20px;
        border-bottom: 2px solid #c2410c;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    
    .alert-bet-title {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .alert-bet-title i {
        color: #f59e0b;
    }
    
    .alert-bet-close {
        background: transparent;
        border: none;
        color: #e0e0e0;
        font-size: 24px;
        cursor: pointer;
        transition: color 0.2s;
    }
    
    .alert-bet-close:hover {
        color: #c2410c;
    }
    
    .alert-bet-body {
        padding: 25px;
    }
    
    /* Estilos dos jogos para apostas - Estilo da imagem */
    .bet-games-list {
        margin-bottom: 30px;
    }
    
    .bet-game-item {
        background: #1e293b;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #3b82f6;
        transition: all 0.3s;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .bet-game-item:hover {
        background: #334155;
        transform: translateY(-2px);
    }
    
    .bet-game-item.selected {
        border-left-color: #10b981;
        background: rgba(16, 185, 129, 0.1);
    }
    
    .bet-game-item.lost {
        border-left-color: #ef4444;
    }
    
    .bet-game-info {
        flex: 1;
    }
    
    .bet-game-market {
        font-weight: 600;
        color: #f59e0b;
        font-size: 14px;
        margin-bottom: 4px;
    }
    
    .bet-game-teams {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 4px;
        color: #ffffff;
    }
    
    .bet-game-date {
        font-size: 12px;
        color: #94a3b8;
    }
    
    .bet-game-odds {
        font-size: 20px;
        font-weight: 700;
        color: #10b981;
        margin-right: 20px;
        min-width: 60px;
        text-align: right;
    }
    
    .bet-game-checkbox {
        width: 20px;
        height: 20px;
        accent-color: #10b981;
        cursor: pointer;
    }
    
    .bet-result-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-top: 6px;
    }
    
    .bet-won {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
    }
    
    .bet-lost {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
    }
    
    /* Controles da aposta */
    .bet-controls-panel {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        margin-top: 20px;
    }
    
    .bet-controls-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 16px;
        color: #ffffff;
        border-bottom: 1px solid #334155;
        padding-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .bet-amount-container {
        display: flex;
        flex-direction: column;
        margin-bottom: 20px;
    }
    
    .bet-amount-label {
        font-size: 14px;
        margin-bottom: 8px;
        color: #e0e0e0;
    }
    
    .bet-amount-input {
        background: #0f172a;
        border: 2px solid #334155;
        border-radius: 8px;
        padding: 12px 12px 12px 40px;
        font-size: 16px;
        color: #ffffff;
        width: 100%;
        transition: border-color 0.3s;
    }
    
    .bet-amount-input:focus {
        outline: none;
        border-color: #10b981;
    }
    
    .bet-summary-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
        margin-top: 16px;
    }
    
    .bet-summary-item {
        background: #0f172a;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    
    .bet-summary-label {
        font-size: 12px;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    
    .bet-summary-value {
        font-size: 20px;
        font-weight: 700;
        color: #f59e0b;
    }
    
    .bet-summary-value.total {
        color: #10b981;
        font-size: 22px;
    }
    
    .bet-actions {
        display: flex;
        justify-content: space-between;
        margin-top: 24px;
        gap: 12px;
    }
    
    .bet-action-btn {
        flex: 1;
        padding: 14px;
        border: none;
        border-radius: 8px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    
    .bet-confirm-btn {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
    }
    
    .bet-cancel-btn {
        background: #334155;
        color: #e0e0e0;
    }
    
    .bet-action-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .bet-confirm-btn:hover {
        background: linear-gradient(90deg, #34d399 0%, #10b981 100%);
    }
    
    .bet-cancel-btn:hover {
        background: #475569;
    }
    
    .currency-prefix {
        position: relative;
        display: inline-block;
        width: 100%;
    }
    
    .currency-prefix::before {
        content: "R$";
        position: absolute;
        left: 12px;
        top: 50%;
        transform: translateY(-50%);
        color: #94a3b8;
        font-weight: 600;
        z-index: 1;
    }
    
    /* Responsividade */
    @media (max-width: 768px) {
        .alert-bet-box {
            max-width: 95%;
        }
        
        .bet-game-item {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }
        
        .bet-game-odds {
            margin-top: 8px;
            margin-right: 0;
            align-self: flex-start;
        }
        
        .bet-game-checkbox {
            align-self: flex-end;
        }
        
        .bet-summary-grid {
            grid-template-columns: 1fr;
        }
        
        .bet-actions {
            flex-direction: column;
        }
    }
    </style>
    """

def render_bet_alert_html():
    """Renderiza o HTML do alerta de apostas estilo 'Minhas Apostas'"""
    return """
    <div class="alert-bet-container" id="betAlertContainer">
        <div class="alert-bet-box">
            <div class="alert-bet-header">
                <div class="alert-bet-title">
                    <i class="fas fa-coins"></i>
                    Minhas Apostas - Top Jogos Selecionados
                </div>
                <button class="alert-bet-close" id="betAlertClose">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="alert-bet-body">
                <div class="bet-games-list" id="betGamesList">
                    <!-- Jogos serão carregados dinamicamente -->
                </div>
                
                <div class="bet-controls-panel">
                    <div class="bet-controls-title">
                        <i class="fas fa-calculator"></i> Controle de Aposta
                    </div>
                    
                    <div class="bet-amount-container">
                        <label class="bet-amount-label">Valor da Aposta</label>
                        <div class="currency-prefix">
                            <input type="number" class="bet-amount-input" id="betAmountInput" min="1" max="10000" value="20.00" step="0.01">
                        </div>
                    </div>
                    
                    <div class="bet-summary-grid">
                        <div class="bet-summary-item">
                            <div class="bet-summary-label">Jogos Selecionados</div>
                            <div class="bet-summary-value" id="selectedCount">0</div>
                        </div>
                        
                        <div class="bet-summary-item">
                            <div class="bet-summary-label">Cota Total</div>
                            <div class="bet-summary-value" id="totalOdds">0.00</div>
                        </div>
                        
                        <div class="bet-summary-item">
                            <div class="bet-summary-label">Valor da Aposta</div>
                            <div class="bet-summary-value">R$ <span id="betAmountDisplay">20.00</span></div>
                        </div>
                        
                        <div class="bet-summary-item">
                            <div class="bet-summary-label">Ganhos Totais</div>
                            <div class="bet-summary-value total">R$ <span id="totalWinnings">0.00</span></div>
                        </div>
                    </div>
                    
                    <div class="bet-actions">
                        <button class="bet-action-btn bet-confirm-btn" id="betConfirm">
                            <i class="fas fa-check-circle"></i> Confirmar Aposta
                        </button>
                        <button class="bet-action-btn bet-cancel-btn" id="betCancel">
                            <i class="fas fa-times-circle"></i> Fechar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

def render_bet_alert_js():
    """Renderiza o JavaScript para o alerta de apostas"""
    return """
    <script>
    // Módulo de Alerta de Apostas
    const BetAlert = {
        games: [],
        betAmount: 20.00,
        
        // Inicializar con dados
        init: function(gamesData) {
            this.games = gamesData || [];
            this.betAmount = 20.00;
            this.setupEventListeners();
            this.renderGames();
            this.updateCalculations();
        },
        
        // Mostrar alerta
        show: function() {
            const container = document.getElementById('betAlertContainer');
            container.style.display = 'flex';
            setTimeout(() => {
                container.classList.add('show');
            }, 10);
        },
        
        // Esconder alerta
        hide: function() {
            const container = document.getElementById('betAlertContainer');
            container.classList.remove('show');
            setTimeout(() => {
                container.style.display = 'none';
            }, 300);
        },
        
        // Configurar event listeners
        setupEventListeners: function() {
            // Fechar alerta
            const closeBtn = document.getElementById('betAlertClose');
            if (closeBtn) {
                closeBtn.onclick = () => this.hide();
            }
            
            // Confirmar aposta
            const confirmBtn = document.getElementById('betConfirm');
            if (confirmBtn) {
                confirmBtn.onclick = () => this.confirmBet();
            }
            
            // Cancelar/Fechar
            const cancelBtn = document.getElementById('betCancel');
            if (cancelBtn) {
                cancelBtn.onclick = () => this.hide();
            }
            
            // Valor da aposta
            const betInput = document.getElementById('betAmountInput');
            if (betInput) {
                betInput.oninput = () => {
                    this.betAmount = parseFloat(betInput.value) || 0;
                    this.updateCalculations();
                };
            }
            
            // Fechar ao clicar no backdrop
            document.getElementById('betAlertContainer').onclick = (e) => {
                if (e.target.id === 'betAlertContainer') {
                    this.hide();
                }
            };
        },
        
        // Renderizar jogos
        renderGames: function() {
            const gamesList = document.getElementById('betGamesList');
            if (!gamesList) return;
            
            gamesList.innerHTML = '';
            
            if (this.games.length === 0) {
                gamesList.innerHTML = '<div style="text-align: center; color: #94a3b8; padding: 20px;">Nenhum jogo disponível para apostas.</div>';
                return;
            }
            
            this.games.forEach(game => {
                const gameItem = document.createElement('div');
                gameItem.className = `bet-game-item ${game.selected ? 'selected' : ''} ${game.result === 'lost' ? 'lost' : ''}`;
                gameItem.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                        <div class="bet-game-info">
                            <div class="bet-game-market">${game.market}</div>
                            <div class="bet-game-teams">${game.teams}</div>
                            <div class="bet-game-date">${game.date}</div>
                            <div class="bet-result-badge ${game.result}">${game.result === 'won' ? 'Ganhas' : 'Perdidas'}</div>
                        </div>
                        <div class="bet-game-odds">${game.odds.toFixed(2)}</div>
                        <input type="checkbox" class="bet-game-checkbox" data-id="${game.id}" ${game.selected ? 'checked' : ''}>
                    </div>
                `;
                gamesList.appendChild(gameItem);
            });
            
            // Adicionar eventos aos checkboxes
            document.querySelectorAll('.bet-game-checkbox').forEach(checkbox => {
                checkbox.onchange = (e) => {
                    const gameId = parseInt(e.target.dataset.id);
                    const game = this.games.find(g => g.id === gameId);
                    if (game) {
                        game.selected = e.target.checked;
                        
                        // Atualizar classe do item
                        const gameItem = e.target.closest('.bet-game-item');
                        if (e.target.checked) {
                            gameItem.classList.add('selected');
                        } else {
                            gameItem.classList.remove('selected');
                        }
                        
                        this.updateCalculations();
                    }
                };
            });
        },
        
        // Atualizar cálculos
        updateCalculations: function() {
            // Contar jogos selecionados
            const selectedGames = this.games.filter(game => game.selected);
            const count = selectedGames.length;
            document.getElementById('selectedCount').textContent = count;
            
            // Calcular cota total
            let oddsTotal = 1;
            selectedGames.forEach(game => {
                oddsTotal *= game.odds;
            });
            
            // Ganhos totais
            const winnings = this.betAmount * oddsTotal;
            
            // Atualizar exibição
            document.getElementById('totalOdds').textContent = oddsTotal.toFixed(2);
            document.getElementById('betAmountDisplay').textContent = this.betAmount.toFixed(2);
            document.getElementById('totalWinnings').textContent = winnings.toFixed(2);
        },
        
        // Confirmar aposta
        confirmBet: function() {
            const selectedGames = this.games.filter(game => game.selected);
            const totalOddsValue = parseFloat(document.getElementById('totalOdds').textContent);
            const totalWinningsValue = parseFloat(document.getElementById('totalWinnings').textContent);
            
            if (selectedGames.length === 0) {
                alert('⚠️ Selecione pelo menos um jogo para apostar!');
                return;
            }
            
            const message = `✅ Aposta confirmada!

📊 Resumo da Aposta:
• Jogos selecionados: ${selectedGames.length}
• Valor da aposta: R$ ${this.betAmount.toFixed(2)}
• Cota total: ${totalOddsValue.toFixed(2)}
• Ganhos potenciais: R$ ${totalWinningsValue.toFixed(2)}

🔥 Boa sorte!`;
            
            alert(message);
            
            // Opcional: Enviar para o backend ou salvar
            this.hide();
        }
    };
    
    // Função para mostrar alerta (chamada pelo Streamlit)
    window.showBetAlert = function(gamesData) {
        BetAlert.init(gamesData);
        BetAlert.show();
    };
    
    // Inicializar quando carregado
    document.addEventListener('DOMContentLoaded', function() {
        // Esconder inicialmente
        document.getElementById('betAlertContainer').style.display = 'none';
    });
    </script>
    """

def show_bet_alert_streamlit(apostas_data):
    """Exibe o alerta de apostas no Streamlit"""
    # Renderizar CSS, HTML e JS
    st.markdown(render_bet_alert_css(), unsafe_allow_html=True)
    st.markdown(render_bet_alert_html(), unsafe_allow_html=True)
    st.markdown(render_bet_alert_js(), unsafe_allow_html=True)
    
    # Usar JavaScript para mostrar o alerta
    js_code = f"""
    <script>
    window.showBetAlert({json.dumps(apostas_data)});
    </script>
    """
    st.components.v1.html(js_code, height=0)

# =============================
# FUNÇÕES PRINCIPAIS
# =============================

def debug_jogos_dia(data_selecionada, todas_ligas, liga_selecionada):
    """Função de debug para verificar os jogos retornados pela API"""
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]
    
    st.write("🔍 **DEBUG DETALHADO - JOGOS DA API**")
    
    for liga_id in ligas_busca:
        if liga_id == "BSA":  # Apenas para o Brasileirão
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
                
                # Converter para horário correto
                hora_corrigida = formatar_data_iso_para_datetime(data_utc)
                data_br = hora_corrigida.strftime("%d/%m/%Y")
                hora_br = hora_corrigida.strftime("%H:%M")
                
                st.write(f"  {i+1}. {home} vs {away}")
                st.write(f"     UTC: {data_utc}")
                st.write(f"     BR: {data_br} {hora_br} | Status: {status}")
                st.write(f"     Competição: {match.get('competition', {}).get('name', 'Desconhecido')}")
                
            except Exception as e:
                st.write(f"  {i+1}. ERRO ao processar jogo: {e}")

def enviar_top_jogos(jogos: list, top_n: int, alerta_top_jogos: bool, show_bet_alert: bool = False):
    """Envia os top jogos para o Telegram e opcionalmente mostra alerta de apostas"""
    if not alerta_top_jogos and not show_bet_alert:
        st.info("ℹ️ Alerta de Top Jogos desativado")
        return
        
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    if not jogos_filtrados:
        st.warning("⚠️ Nenhum jogo elegível para o Top Jogos (todos já iniciados ou finalizados).")
        return
        
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
    
    # Mostrar alerta de apostas se solicitado
    if show_bet_alert and top_jogos_sorted:
        # Converter os top jogos em apostas
        apostas = converter_top_jogos_para_apostas(top_jogos_sorted, top_n)
        
        # Mostrar alerta de apostas
        show_bet_alert_streamlit(apostas)
        
        # Mostrar mensagem no Streamlit
        st.success(f"💰 Mostrando {len(apostas)} apostas dos top {top_n} jogos!")
        
        # Opcional: Salvar as apostas
        salvar_apostas(apostas)
    
    # Enviar para Telegram apenas se a checkbox estiver ativada
    if alerta_top_jogos:
        msg = f"📢 TOP {top_n} Jogos do Dia (confiança alta)\n\n"
        
        for j in top_jogos_sorted:
            hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
                f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
                f"💯 Confiança: {j['confianca']:.0f}%\n\n"
            )
            
        if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2, disable_web_page_preview=True):
            st.success(f"🚀 Top {top_n} jogos enviados para o canal!")
        else:
            st.error("❌ Erro ao enviar top jogos para o Telegram")
    elif show_bet_alert:
        st.info(f"📊 Top {top_n} jogos convertidos em apostas!")

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
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH, APOSTAS_PATH]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                arquivos_limpos += 1
        st.success(f"✅ {arquivos_limpos} caches limpos con sucesso!")
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
# Interface Streamlit
# =============================
# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols")

    # Sidebar - CONFIGURAÇÕES DE ALERTAS
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        
        # Checkboxes para cada tipo de alerta
        alerta_individual = st.checkbox("🎯 Alertas Individuais", value=True, 
                                       help="Envia alerta individual para cada jogo con confiança alta")
        
        alerta_poster = st.checkbox("📊 Alertas con Poster", value=True,
                                   help="Envia poster con múltiplos jogos acima do limiar")
        
        alerta_top_jogos = st.checkbox("🏆 Top Jogos", value=True,
                                      help="Envia lista dos top jogos do dia")
        
        alerta_resultados = st.checkbox("🏁 Resultados Finais", value=True,
                                       help="Envia alerta de resultados con sistema RED/GREEN")
        
        # NOVO: Checkbox para alerta de apostas dos Top Jogos
        alerta_apostas_top = st.checkbox("💰 Apostas dos Top Jogos", value=True,
                                        help="Mostra alerta de apostas com os top jogos do dia")
        
        st.markdown("----")
        
        st.header("Configurações Gerais")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        threshold = st.slider("Limiar de confiança (%)", 50, 95, 70, 1)
        estilo_poster = st.selectbox("🎨 Estilo do Poster", ["West Ham (Novo)", "Elite Master (Original)"], index=0)
        
        st.markdown("----")
        st.info("Ative/desative cada tipo de alerta conforme sua necessidade")

    # Controles principais
    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))

    # BOTÃO DE DEBUG
    if st.button("🐛 Debug Jogos (API)", type="secondary"):
        debug_jogos_dia(data_selecionada, todas_ligas, liga_selecionada)

    # Processamento principal
    if st.button("🔍 Buscar Partidas", type="primary"):
        # Processar jogos e coletar resultados
        top_jogos = processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, threshold, estilo_poster, 
                                   alerta_individual, alerta_poster, alerta_top_jogos, alerta_apostas_top)
        
        # Mostrar alerta de apostas se solicitado
        if alerta_apostas_top and top_jogos:
            # Converter os top jogos em apostas
            apostas = converter_top_jogos_para_apostas(top_jogos, top_n)
            if apostas:
                # Mostrar alerta de apostas
                show_bet_alert_streamlit(apostas)
                st.success(f"💰 {len(apostas)} apostas criadas dos top {top_n} jogos!")

    # Ações
    col1, col2, col3, col4 = st.columns(4)
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

    # Botão para visualizar apostas salvas
    st.markdown("---")
    col_bet1, col_bet2 = st.columns(2)
    with col_bet1:
        if st.button("📋 Ver Apostas Salvas", key="view_saved_bets"):
            apostas = carregar_apostas()
            if apostas:
                st.success(f"📊 {len(apostas)} apostas carregadas!")
                
                # Mostrar resumo
                for aposta in apostas[:5]:
                    with st.expander(f"🎯 {aposta.get('teams', 'Desconhecido')}"):
                        st.write(f"**Mercado:** {aposta.get('market', 'N/A')}")
                        st.write(f"**Odds:** {aposta.get('odds', 0):.2f}")
                        st.write(f"**Data:** {aposta.get('date', 'N/A')}")
                        st.write(f"**Resultado:** {'✅ Ganhas' if aposta.get('result') == 'won' else '❌ Perdidas'}")
                
                # Botão para mostrar alerta com apostas salvas
                if st.button("👁️ Mostrar Alerta de Apostas", key="show_saved_bets_alert"):
                    show_bet_alert_streamlit(apostas)
            else:
                st.info("ℹ️ Nenhuma aposta salva encontrada.")

    # Painel desempenho
    st.markdown("---")
    st.subheader("📊 Painel de Desempenho")
    usar_periodo = st.checkbox("🔎 Usar período específico", value=False, key="use_period")
    qtd_default = 50
    last_n = st.number_input("Últimos N jogos", 1, 1000, qtd_default, 1, key="last_n_games")
    
    colp1, colp2 = st.columns(2)
    with colp1:
        if usar_periodo:
            data_inicio = st.date_input("Data inicial", value=(datetime.today() - timedelta(days=30)).date(), key="start_date")
            data_fim = st.date_input("Data final", value=datetime.today().date(), key="end_date")
    with colp2:
        if st.button("📈 Calcular Desempenho", key="calculate_performance"):
            if usar_periodo:
                calcular_desempenho_periodo(data_inicio, data_fim)
            else:
                calcular_desempenho(qtd_jogos=last_n)

    if st.button("🧹 Limpar Histórico", key="clear_history"):
        limpar_historico()

# =============================
# FUNÇÕES PRINCIPAIS
# =============================

def debug_jogos_dia(data_selecionada, todas_ligas, liga_selecionada):
    """Função de debug para verificar os jogos retornados pela API"""
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]
    
    st.write("🔍 **DEBUG DETALHADO - JOGOS DA API**")
    
    for liga_id in ligas_busca:
        if liga_id == "BSA":  # Apenas para o Brasileirão
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
                
                # Converter para horário correto
                hora_corrigida = formatar_data_iso_para_datetime(data_utc)
                data_br = hora_corrigida.strftime("%d/%m/%Y")
                hora_br = hora_corrigida.strftime("%H:%M")
                
                st.write(f"  {i+1}. {home} vs {away}")
                st.write(f"     UTC: {data_utc}")
                st.write(f"     BR: {data_br} {hora_br} | Status: {status}")
                st.write(f"     Competição: {match.get('competition', {}).get('name', 'Desconhecido')}")
                
            except Exception as e:
                st.write(f"  {i+1}. ERRO ao processar jogo: {e}")

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
        hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
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
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH, APOSTAS_PATH]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                arquivos_limpos += 1
        st.success(f"✅ {arquivos_limpos} caches limpos con sucesso!")
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

def processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, threshold, estilo_poster, 
                   alerta_individual: bool, alerta_poster: bool, alerta_top_jogos: bool, alerta_apostas_top: bool = False):
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
    
    top_jogos = []
    progress_bar = st.progress(0)
    total_ligas = len(ligas_busca)

    for i, liga_id in enumerate(ligas_busca):
        classificacao = obter_classificacao(liga_id)
        
        # CORREÇÃO: Para o Brasileirão usar busca especial que considera fuso horário
        if liga_id == "BSA":  # Campeonato Brasileiro
            jogos = obter_jogos_brasileirao(liga_id, hoje)
            st.write(f"📊 Liga BSA: {len(jogos)} jogos encontrados (con correção de fuso horário)")
        else:
            jogos = obter_jogos(liga_id, hoje)
            st.write(f"📊 Liga {liga_id}: {len(jogos)} jogos encontrados")

        for match in jogos:
            # Validar dados do jogo
            if not validar_dados_jogo(match):
                continue
                
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)

            # DEBUG: Mostrar cada jogo processado
            data_utc = match["utcDate"]
            hora_corrigida = formatar_data_iso_para_datetime(data_utc)
            data_br = hora_corrigida.strftime("%d/%m/%Y")
            hora_br = hora_corrigida.strftime("%H:%M")
            
            st.write(f"   ✅ {home} vs {away}")
            st.write(f"      🕒 {data_br} {hora_br} | Confiança: {confianca:.1f}% | Status: {match.get('status', 'DESCONHECIDO')}")

            # Só envia alerta individual se a checkbox estiver ativada
            verificar_enviar_alerta(match, tendencia, estimativa, confianca, alerta_individual)

            # Extrair escudos
            escudo_home = ""
            escudo_away = ""
            try:
                escudo_home = match.get("homeTeam", {}).get("crest") or match.get("homeTeam", {}).get("logo") or ""
                escudo_away = match.get("awayTeam", {}).get("crest") or match.get("awayTeam", {}).get("logo") or ""
            except Exception:
                pass

            top_jogos.append({
                "id": match["id"],
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": hora_corrigida,
                "status": match.get("status", "DESCONHECIDO"),
                "escudo_home": escudo_home,
                "escudo_away": escudo_away
            })
        progress_bar.progress((i + 1) / total_ligas)

    # DEBUG COMPLETO: Mostrar todos os jogos processados
    st.write("🔍 **DEBUG FINAL - TODOS OS JOGOS PROCESSADOS:**")
    for jogo in top_jogos:
        data_str = jogo["hora"].strftime("%d/%m/%Y")
        hora_str = jogo["hora"].strftime("%H:%M")
        st.write(f"📅 {jogo['home']} vs {jogo['away']}: {data_str} {hora_str} | Conf: {jogo['confianca']:.1f}% | Status: {jogo['status']}")

    # Filtrar por limiar - DEBUG DETALHADO
    st.write("🔍 **DEBUG FILTRO POR LIMIAR:**")
    jogos_filtrados_threshold = [
        j for j in top_jogos
        if j["confianca"] >= threshold and j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
    ]
    
    st.write(f"📊 Total de jogos: {len(top_jogos)}")
    st.write(f"📊 Jogos con confiança ≥{threshold}%: {len(jogos_filtrados_threshold)}")
    
    # Mostrar jogos que passaram no filtro
    if jogos_filtrados_threshold:
        st.write("✅ **Jogos que passaram no filtro:**")
        for jogo in jogos_filtrados_threshold:
            st.write(f"   🟢 {jogo['home']} vs {jogo['away']} - Conf: {jogo['confianca']:.1f}%")
        
        # Envia top jogos para o Telegram
        enviar_top_jogos(jogos_filtrados_threshold, top_n, alerta_top_jogos)
        st.success(f"✅ {len(jogos_filtrados_threshold)} jogos con confiança ≥{threshold}%")
        
        # ENVIAR ALERTA DE IMAGEM apenas se a checkbox estiver ativada
        if alerta_poster:
            st.info("🚨 Enviando alerta de imagem...")
            if estilo_poster == "West Ham (Novo)":
                enviar_alerta_westham_style(jogos_filtrados_threshold, threshold)
            else:
                enviar_alerta_conf_criar_poster(jogos_filtrados_threshold, threshold)
        else:
            st.info("ℹ️ Alerta con Poster desativado")
    else:
        st.warning(f"⚠️ Nenhum jogo con confiança ≥{threshold}%")
        
        # DEBUG: Mostrar por que não há jogos
        if top_jogos:
            st.write("🔍 **Razão para nenhum jogo passar:**")
            for jogo in top_jogos:
                motivo = ""
                if jogo["confianca"] < threshold:
                    motivo = f"Confiança baixa ({jogo['confianca']:.1f}% < {threshold}%)"
                elif jogo["status"] in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]:
                    motivo = f"Status: {jogo['status']}"
                else:
                    motivo = "DEVERIA PASSAR - VERIFICAR"
                
                st.write(f"   ❌ {jogo['home']} vs {jogo['away']}: {motivo}")
    
    return jogos_filtrados_threshold

def enviar_alerta_conf_criar_poster(jogos_conf: list, threshold: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Função fallback para o estilo original"""
    if not jogos_conf:
        return
        
    try:
        msg = f"🔥 Jogos ≥{threshold}% (Estilo Original):\n\n"
        for j in jogos_conf:
            hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | {j['liga']}\n"
                f"📈 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 💯 {j['confianca']:.0f}%\n\n"
            )
        enviar_telegram(msg, chat_id=chat_id)
        st.success("📤 Alerta enviado (formato texto)")
    except Exception as e:
        logging.error(f"Erro no fallback de poster: {e}")
        st.error(f"Erro no fallback: {e}")

if __name__ == "__main__":
    main()
