# app_nba_elite_master.py
import streamlit as st
from datetime import datetime, timedelta, date
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import time
from PIL import Image, ImageDraw, ImageFont
import base64
import math
import cairosvg

# =============================
# CONFIGURAÇÕES
# =============================
BALLDONTLIE_API_KEY = "7da89f74-317a-45a0-88f9-57cccfef5a00"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"

BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas_nba.json"
CACHE_GAMES = "cache_games_nba.json"
CACHE_TEAMS = "cache_teams_nba.json"
CACHE_STATS = "cache_stats_nba.json"
STATS_PATH = "estatisticas_nba.json"
CACHE_TIMEOUT = 86400  # 24h

HEADERS_BDL = {"Authorization": BALLDONTLIE_API_KEY}

# Rate limiting
REQUEST_TIMEOUT = 10
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 1.2

# =============================
# DICIONÁRIO DE ESCUDOS NBA
# =============================
NBA_LOGOS = {
    "Atlanta Hawks": "https://cdn.nba.com/logos/nba/1610612737/primary/L/logo.svg",
    "Boston Celtics": "https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg",
    "Brooklyn Nets": "https://cdn.nba.com/logos/nba/1610612751/primary/L/logo.svg",
    "Charlotte Hornets": "https://cdn.nba.com/logos/nba/1610612766/primary/L/logo.svg",
    "Chicago Bulls": "https://cdn.nba.com/logos/nba/1610612741/primary/L/logo.svg",
    "Cleveland Cavaliers": "https://cdn.nba.com/logos/nba/1610612739/primary/L/logo.svg",
    "Dallas Mavericks": "https://cdn.nba.com/logos/nba/1610612742/primary/L/logo.svg",
    "Denver Nuggets": "https://cdn.nba.com/logos/nba/1610612743/primary/L/logo.svg",
    "Detroit Pistons": "https://cdn.nba.com/logos/nba/1610612765/primary/L/logo.svg",
    "Golden State Warriors": "https://cdn.nba.com/logos/nba/1610612744/primary/L/logo.svg",
    "Houston Rockets": "https://cdn.nba.com/logos/nba/1610612745/primary/L/logo.svg",
    "Indiana Pacers": "https://cdn.nba.com/logos/nba/1610612754/primary/L/logo.svg",
    "Los Angeles Clippers": "https://cdn.nba.com/logos/nba/1610612746/primary/L/logo.svg",
    "Los Angeles Lakers": "https://cdn.nba.com/logos/nba/1610612747/primary/L/logo.svg",
    "Memphis Grizzlies": "https://cdn.nba.com/logos/nba/1610612763/primary/L/logo.svg",
    "Miami Heat": "https://cdn.nba.com/logos/nba/1610612748/primary/L/logo.svg",
    "Milwaukee Bucks": "https://cdn.nba.com/logos/nba/1610612749/primary/L/logo.svg",
    "Minnesota Timberwolves": "https://cdn.nba.com/logos/nba/1610612750/primary/L/logo.svg",
    "New Orleans Pelicans": "https://cdn.nba.com/logos/nba/1610612740/primary/L/logo.svg",
    "New York Knicks": "https://cdn.nba.com/logos/nba/1610612752/primary/L/logo.svg",
    "Oklahoma City Thunder": "https://cdn.nba.com/logos/nba/1610612760/primary/L/logo.svg",
    "Orlando Magic": "https://cdn.nba.com/logos/nba/1610612753/primary/L/logo.svg",
    "Philadelphia 76ers": "https://cdn.nba.com/logos/nba/1610612755/primary/L/logo.svg",
    "Phoenix Suns": "https://cdn.nba.com/logos/nba/1610612756/primary/L/logo.svg",
    "Portland Trail Blazers": "https://cdn.nba.com/logos/nba/1610612757/primary/L/logo.svg",
    "Sacramento Kings": "https://cdn.nba.com/logos/nba/1610612758/primary/L/logo.svg",
    "San Antonio Spurs": "https://cdn.nba.com/logos/nba/1610612759/primary/L/logo.svg",
    "Toronto Raptors": "https://cdn.nba.com/logos/nba/1610612761/primary/L/logo.svg",
    "Utah Jazz": "https://cdn.nba.com/logos/nba/1610612762/primary/L/logo.svg",
    "Washington Wizards": "https://cdn.nba.com/logos/nba/1610612764/primary/L/logo.svg"
}

# =============================
# FUNÇÕES AUXILIARES PARA DATAS (CORREÇÃO FINAL)
# =============================
def formatar_data_api_para_local(data_utc: str) -> tuple[str, str]:
    """Converte data UTC da API para horário local brasileiro CORRETAMENTE"""
    try:
        # Formato esperado: "2024-11-15T00:30:00.000Z"
        if not data_utc or len(data_utc) < 10:
            return "Data inválida", ""
            
        # Extrai ano, mês, dia e hora diretamente
        ano = data_utc[0:4]
        mes = data_utc[5:7]
        dia = data_utc[8:10]
        hora = data_utc[11:13]
        minuto = data_utc[14:16]
        
        # Converte para inteiros
        dia_int = int(dia)
        hora_int = int(hora)
        
        # CORREÇÃO: Ajuste para fuso horário Brasil (UTC-3)
        # Se o jogo é às 21h no Brasil, na API será 00h do dia seguinte UTC
        # Mas queremos manter o DIA CORRETO do jogo
        hora_brasil = hora_int - 3
        
        # Se a hora ficou negativa, ajusta para o dia anterior
        if hora_brasil < 0:
            hora_brasil += 24
            # ATENÇÃO: NÃO diminuímos o dia aqui porque os jogos da NBA
            # que acontecem à noite nos EUA aparecem como dia seguinte na API UTC
            # mas na realidade são no mesmo dia no horário local
            # dia_int -= 1  # REMOVIDO - mantém o mesmo dia
        
        # Formata de volta para string
        data_str = f"{dia_int:02d}/{mes}/{ano}"
        hora_str = f"{hora_brasil:02d}:{minuto}"
        
        print(f"DEBUG CONVERSÃO: {data_utc} -> {data_str} {hora_str}")
        
        return data_str, hora_str
        
    except Exception as e:
        print(f"Erro na conversão da data {data_utc}: {e}")
        # Fallback: retorna a data como está
        try:
            return data_utc[8:10] + "/" + data_utc[5:7] + "/" + data_utc[0:4], data_utc[11:16]
        except:
            return data_utc[:10], ""

def obter_data_correta_para_api(data: date) -> str:
    """Converte data local para formato correto da API considerando UTC"""
    # A API espera datas em UTC, então precisamos garantir que busca os jogos do dia correto
    data_str = data.strftime("%Y-%m-%d")
    return data_str

# =============================
# CACHE E IO
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            if datetime.now().timestamp() - os.path.getmtime(caminho) > CACHE_TIMEOUT:
                return {}
            return dados
    except Exception:
        return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def carregar_alertas():
    return carregar_json(ALERTAS_PATH) or {}

def salvar_alertas(dados):
    salvar_json(ALERTAS_PATH, dados)

def carregar_cache_games():
    return carregar_json(CACHE_GAMES) or {}

def salvar_cache_games(dados):
    salvar_json(CACHE_GAMES, dados)

def carregar_cache_teams():
    return carregar_json(CACHE_TEAMS) or {}

def salvar_cache_teams(dados):
    salvar_json(CACHE_TEAMS, dados)

def carregar_cache_stats():
    return carregar_json(CACHE_STATS) or {}

def salvar_cache_stats(dados):
    salvar_json(CACHE_STATS, dados)

# =============================
# SISTEMA DE ESTATÍSTICAS
# =============================
def carregar_estatisticas():
    """Carrega as estatísticas de acertos/erros"""
    return carregar_json(STATS_PATH) or {
        "total_pontos": {"acertos": 0, "erros": 0, "total": 0},
        "vencedor": {"acertos": 0, "erros": 0, "total": 0},
        "jogos_analisados": 0,
        "data_ultima_atualizacao": None
    }

def salvar_estatisticas(dados):
    """Salva as estatísticas"""
    salvar_json(STATS_PATH, dados)

def atualizar_estatisticas(resultado_total: str, resultado_vencedor: str):
    """Atualiza as estatísticas baseado nos resultados"""
    stats = carregar_estatisticas()
    
    # Atualiza estatísticas de Total de Pontos
    if resultado_total == "🟢 GREEN":
        stats["total_pontos"]["acertos"] += 1
        stats["total_pontos"]["total"] += 1
    elif resultado_total == "🔴 RED":
        stats["total_pontos"]["erros"] += 1
        stats["total_pontos"]["total"] += 1
    
    # Atualiza estatísticas de Vencedor
    if resultado_vencedor == "🟢 GREEN":
        stats["vencedor"]["acertos"] += 1
        stats["vencedor"]["total"] += 1
    elif resultado_vencedor == "🔴 RED":
        stats["vencedor"]["erros"] += 1
        stats["vencedor"]["total"] += 1
    
    stats["jogos_analisados"] = max(stats["total_pontos"]["total"], stats["vencedor"]["total"])
    stats["data_ultima_atualizacao"] = datetime.now().isoformat()
    
    salvar_estatisticas(stats)
    return stats

def calcular_taxa_acerto(acertos: int, total: int) -> float:
    """Calcula a taxa de acerto em porcentagem"""
    if total == 0:
        return 0.0
    return (acertos / total) * 100

def exibir_estatisticas():
    """Exibe as estatísticas de forma organizada"""
    stats = carregar_estatisticas()
    
    st.header("📊 Estatísticas de Desempenho")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🎯 Total de Pontos",
            value=f"{stats['total_pontos']['acertos']}/{stats['total_pontos']['total']}",
            delta=f"{calcular_taxa_acerto(stats['total_pontos']['acertos'], stats['total_pontos']['total']):.1f}%"
        )
        st.progress(stats['total_pontos']['acertos'] / max(stats['total_pontos']['total'], 1))
    
    with col2:
        st.metric(
            label="🏆 Vencedor",
            value=f"{stats['vencedor']['acertos']}/{stats['vencedor']['total']}",
            delta=f"{calcular_taxa_acerto(stats['vencedor']['acertos'], stats['vencedor']['total']):.1f}%"
        )
        st.progress(stats['vencedor']['acertos'] / max(stats['vencedor']['total'], 1))
    
    with col3:
        st.metric(
            label="📈 Jogos Analisados",
            value=stats["jogos_analisados"],
            delta="Performance"
        )
        taxa_geral = (stats['total_pontos']['acertos'] + stats['vencedor']['acertos']) / max((stats['total_pontos']['total'] + stats['vencedor']['total']), 1) * 100
        st.write(f"**Taxa Geral:** {taxa_geral:.1f}%")
    
    # Estatísticas detalhadas
    st.subheader("📋 Detalhamento por Categoria")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Total de Pontos**")
        st.write(f"✅ Acertos: {stats['total_pontos']['acertos']}")
        st.write(f"❌ Erros: {stats['total_pontos']['erros']}")
        st.write(f"📊 Total: {stats['total_pontos']['total']}")
        st.write(f"🎯 Taxa: {calcular_taxa_acerto(stats['total_pontos']['acertos'], stats['total_pontos']['total']):.1f}%")
    
    with col2:
        st.write("**Vencedor**")
        st.write(f"✅ Acertos: {stats['vencedor']['acertos']}")
        st.write(f"❌ Erros: {stats['vencedor']['erros']}")
        st.write(f"📊 Total: {stats['vencedor']['total']}")
        st.write(f"🎯 Taxa: {calcular_taxa_acerto(stats['vencedor']['acertos'], stats['vencedor']['total']):.1f}%")
    
    # Data da última atualização
    if stats["data_ultima_atualizacao"]:
        try:
            dt = datetime.fromisoformat(stats["data_ultima_atualizacao"])
            st.caption(f"🕒 Última atualização: {dt.strftime('%d/%m/%Y %H:%M')}")
        except:
            pass

def limpar_estatisticas():
    """Limpa todas as estatísticas"""
    stats = {
        "total_pontos": {"acertos": 0, "erros": 0, "total": 0},
        "vencedor": {"acertos": 0, "erros": 0, "total": 0},
        "jogos_analisados": 0,
        "data_ultima_atualizacao": None
    }
    salvar_estatisticas(stats)
    return stats

# =============================
# REQUISIÇÕES À API
# =============================
def balldontlie_get(path: str, params: dict | None = None, timeout: int = REQUEST_TIMEOUT) -> dict | None:
    global LAST_REQUEST_TIME
    
    current_time = time.time()
    time_since_last_request = current_time - LAST_REQUEST_TIME
    if time_since_last_request < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - time_since_last_request)
    
    try:
        url = BALLDONTLIE_BASE.rstrip("/") + "/" + path.lstrip("/")
        resp = requests.get(url, headers=HEADERS_BDL, params=params, timeout=timeout)
        LAST_REQUEST_TIME = time.time()
        
        if resp.status_code == 429:
            st.error("🚨 RATE LIMIT ATINGIDO! Aguardando 60 segundos...")
            time.sleep(60)
            resp = requests.get(url, headers=HEADERS_BDL, params=params, timeout=timeout)
            LAST_REQUEST_TIME = time.time()
        
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        st.error(f"Erro na API: {e}")
        return None

# =============================
# DADOS DOS TIMES
# =============================
def obter_times():
    cache = carregar_cache_teams()
    if "teams" in cache and cache["teams"]:
        return cache["teams"]
    
    st.info("📥 Buscando dados dos times...")
    data = balldontlie_get("teams")
    if not data or "data" not in data:
        return {}
    
    teams = {t["id"]: t for t in data.get("data", [])}
    cache["teams"] = teams
    salvar_cache_teams(cache)
    return teams

# =============================
# BUSCA DE JOGOS REAIS - VERSÃO CORRIGIDA
# =============================
def obter_jogos_data(data_str: str) -> list:
    """BUSCA DE JOGOS REAIS - VERSÃO CORRIGIDA"""
    cache = carregar_cache_games()
    key = f"games_{data_str}"
    
    if key in cache and cache[key]:
        return cache[key]

    st.info(f"📥 Buscando jogos para {data_str}...")
    jogos = []
    page = 1
    max_pages = 2
    
    while page <= max_pages:
        params = {
            "dates[]": data_str, 
            "per_page": 50,
            "page": page
        }
        
        resp = balldontlie_get("games", params=params)
        if not resp or "data" not in resp:
            break
            
        data_chunk = resp["data"]
        if not data_chunk:
            break
            
        # Filtra jogos que realmente pertencem à data solicitada
        jogos_do_dia = []
        for jogo in data_chunk:
            data_jogo = jogo.get("date", "")
            if data_jogo.startswith(data_str):
                jogos_do_dia.append(jogo)
        
        jogos.extend(jogos_do_dia)
        
        meta = resp.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
            
        page += 1

    cache[key] = jogos
    salvar_cache_games(cache)
    
    # Log para debug
    if jogos:
        st.success(f"✅ Encontrados {len(jogos)} jogos para {data_str}")
        for jogo in jogos[:3]:  # Mostra apenas os primeiros 3 para debug
            data_jogo = jogo.get("date", "")
            home_team = jogo.get("home_team", {}).get("full_name", "Casa")
            away_team = jogo.get("visitor_team", {}).get("full_name", "Visitante")
            data_formatada, hora_formatada = formatar_data_api_para_local(data_jogo)
            st.write(f"📅 {home_team} vs {away_team} - {data_formatada} {hora_formatada}")
    else:
        st.warning(f"⚠️ Nenhum jogo encontrado para {data_str}")
    
    return jogos

# =============================
# FUNÇÕES DE IMAGEM E ESCUDOS
# =============================
def baixar_escudo_time(time_nome: str, tamanho: tuple = (120, 120)) -> Image.Image:
    """Baixa e converte escudo SVG para PNG com fallbacks"""
    try:
        # URL do logo do time
        logo_url = NBA_LOGOS.get(time_nome, "")
        
        if not logo_url:
            return criar_escudo_fallback(time_nome, tamanho)
        
        # Baixa o SVG
        resposta = requests.get(logo_url, timeout=10)
        if resposta.status_code != 200:
            return criar_escudo_fallback(time_nome, tamanho)
        
        # Converte SVG para PNG usando cairosvg
        svg_content = resposta.content
        
        # Converte SVG para PNG em memória
        png_data = cairosvg.svg2png(bytestring=svg_content, output_width=tamanho[0], output_height=tamanho[1])
        
        # Converte para PIL Image
        img = Image.open(io.BytesIO(png_data))
        
        # Converte para RGBA se necessário
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        return img
            
    except Exception as e:
        print(f"Erro ao converter SVG para PNG do {time_nome}: {e}")
        # Fallback para escudo personalizado
        return criar_escudo_fallback(time_nome, tamanho)

def criar_escudo_fallback(time_nome: str, tamanho: tuple) -> Image.Image:
    """Cria um escudo fallback com as iniciais do time"""
    img = Image.new('RGBA', tamanho, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Cores baseadas no nome do time
    cores = {
        'Lakers': (85, 37, 130),    # Roxo
        'Warriors': (29, 66, 138),   # Azul
        'Celtics': (0, 122, 51),     # Verde
        'Bulls': (206, 17, 65),      # Vermelho
        'Heat': (152, 0, 46),        # Vermelho
        'Knicks': (0, 107, 182),     # Azul
        'Cavaliers': (134, 0, 56),   # Vinho
        'Spurs': (196, 206, 212),    # Prata
        'Mavericks': (0, 83, 188),   # Azul
        'default': (255, 125, 0)     # Laranja NBA
    }
    
    # Encontra a cor do time
    cor_time = cores['default']
    for nome, cor in cores.items():
        if nome.lower() in time_nome.lower():
            cor_time = cor
            break
    
    # Desenha círculo do escudo
    centro_x, centro_y = tamanho[0] // 2, tamanho[1] // 2
    raio = min(tamanho) // 2 - 10
    
    # Círculo de fundo
    draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                fill=cor_time, outline=(50, 50, 50), width=2)
    
    # Iniciais do time
    try:
        # Pega as 2-3 primeiras letras ou sigla
        palavras = time_nome.split()
        if len(palavras) >= 2:
            iniciais = ''.join([p[0].upper() for p in palavras[:2]])
        else:
            iniciais = time_nome[:3].upper()
        
        # Tenta carregar fonte, fallback para tamanho fixo
        try:
            tamanho_fonte = max(20, raio // 2)
            fonte = ImageFont.truetype("arial.ttf", tamanho_fonte)
        except:
            tamanho_fonte = 30
            fonte = ImageFont.load_default()
        
        # Calcula posição do texto
        bbox = draw.textbbox((0, 0), iniciais, font=fonte)
        texto_largura = bbox[2] - bbox[0]
        texto_altura = bbox[3] - bbox[1]
        
        pos_x = centro_x - texto_largura // 2
        pos_y = centro_y - texto_altura // 2
        
        draw.text((pos_x, pos_y), iniciais, fill="white", font=fonte)
        
    except Exception:
        # Fallback extremo - desenha "NBA"
        draw.text((centro_x-15, centro_y-10), "NBA", fill="white")
    
    return img

def image_to_base64(img: Image.Image) -> str:
    """Converte PIL Image para base64"""
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def exibir_escudo_time(time_nome: str, tamanho: tuple = (80, 80)):
    """Exibe escudo do time no Streamlit"""
    try:
        img = baixar_escudo_time(time_nome, tamanho)
        img_base64 = image_to_base64(img)
        st.image(f"data:image/png;base64,{img_base64}", width=tamanho[0])
    except Exception as e:
        st.error(f"❌ Erro ao carregar escudo: {e}")

# =============================
# ATUALIZAR RESULTADOS DAS PARTIDAS
# =============================
def atualizar_resultados_partidas():
    """Atualiza os resultados das partidas salvas com dados mais recentes da API"""
    alertas = carregar_alertas()
    
    if not alertas:
        st.warning("❌ Nenhuma partida salva para atualizar.")
        return 0
    
    st.info("🔄 Iniciando atualização dos resultados...")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    jogos_atualizados = 0
    total_jogos = len(alertas)
    
    for i, (alerta_id, alerta) in enumerate(alertas.items()):
        progress = (i + 1) / total_jogos
        progress_bar.progress(progress)
        
        game_data = alerta.get("game_data", {})
        game_id = game_data.get("id")
        
        if not game_id:
            continue
        
        # Busca dados atualizados do jogo específico
        status_text.text(f"📡 Buscando dados do jogo {i+1}/{total_jogos}...")
        
        resp = balldontlie_get(f"games/{game_id}")
        if resp and "data" in resp:
            jogo_atualizado = resp["data"]
            
            # Atualiza os dados do jogo no alerta
            alertas[alerta_id]["game_data"] = jogo_atualizado
            
            # Verifica se o status mudou
            status_antigo = game_data.get("status", "")
            status_novo = jogo_atualizado.get("status", "")
            
            if status_antigo != status_novo:
                st.success(f"✅ Jogo {game_id}: {status_antigo} → {status_novo}")
                jogos_atualizados += 1
            else:
                st.write(f"ℹ️ Jogo {game_id}: Status mantido ({status_novo})")
        else:
            st.error(f"❌ Erro ao buscar jogo {game_id}")
        
        # Pequena pausa para evitar rate limit
        time.sleep(0.5)
    
    # Salva os alertas atualizados
    if jogos_atualizados > 0:
        salvar_alertas(alertas)
        st.success(f"🎉 Atualização concluída! {jogos_atualizados} jogos atualizados.")
    else:
        st.info("ℹ️ Nenhum jogo precisou de atualização.")
    
    progress_bar.empty()
    status_text.empty()
    
    return jogos_atualizados

# =============================
# CONFERIR JOGOS FINALIZADOS
# =============================
def conferir_jogos_finalizados():
    """Função específica para conferir jogos finalizados e calcular resultados"""
    alertas = carregar_alertas()
    
    if not alertas:
        st.warning("❌ Nenhum jogo salvo para conferência.")
        return 0
    
    st.info("🔍 Conferindo jogos finalizados...")
    
    jogos_conferidos = 0
    jogos_finalizados = 0
    
    for alerta_id, alerta in alertas.items():
        game_data = alerta.get("game_data", {})
        status = game_data.get("status", "").upper()
        
        # Verifica se o jogo está finalizado
        if status in ["FINAL", "FINAL/OT"]:
            jogos_finalizados += 1
            
            # Se ainda não foi conferido, marca como conferido
            if not alerta.get("conferido", False):
                alertas[alerta_id]["conferido"] = True
                jogos_conferidos += 1
                
                home_team = game_data.get("home_team", {}).get("full_name", "Casa")
                away_team = game_data.get("visitor_team", {}).get("full_name", "Visitante")
                st.success(f"✅ Conferido: {home_team} vs {away_team}")
    
    # Salva as alterações se houver jogos conferidos
    if jogos_conferidos > 0:
        salvar_alertas(alertas)
        st.success(f"🎉 Conferência concluída! {jogos_conferidos} jogos marcados como conferidos.")
    else:
        st.info(f"ℹ️ Nenhum jogo novo para conferir. Total de {jogos_finalizados} jogos finalizados.")
    
    return jogos_conferidos

# =============================
# ESTATÍSTICAS REAIS - TEMPORADA 2024-2025
# =============================
def obter_estatisticas_time_2025(team_id: int, window_games: int = 15) -> dict:
    """Busca estatísticas reais da temporada 2024-2025"""
    cache = carregar_cache_stats()
    key = f"team_{team_id}_2025"
    
    if key in cache:
        cached_data = cache[key]
        if cached_data.get("games", 0) > 0:
            return cached_data

    # Busca jogos da temporada 2024-2025 (season=2024 na API)
    start_date = "2024-10-01"  # Início da temporada 2024-2025
    end_date = "2025-06-30"    # Fim da temporada regular
    
    games = []
    page = 1
    max_pages = 3
    
    st.info(f"📊 Buscando estatísticas 2024-2025 do time {team_id}...")
    
    while page <= max_pages:
        params = {
            "team_ids[]": team_id,
            "per_page": 25,
            "page": page,
            "start_date": start_date,
            "end_date": end_date,
            "seasons[]": 2024  # Temporada 2024-2025
        }
        
        resp = balldontlie_get("games", params=params)
        if not resp or "data" not in resp:
            break
            
        games.extend(resp["data"])
        
        meta = resp.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
            
        page += 1

    # Filtra apenas jogos finalizados com placar válido
    games_validos = []
    for game in games:
        try:
            status = game.get("status", "").upper()
            home_score = game.get("home_team_score")
            visitor_score = game.get("visitor_team_score")
            
            if (status in ("FINAL", "FINAL/OT") and 
                home_score is not None and 
                visitor_score is not None and
                home_score > 0 and visitor_score > 0):
                games_validos.append(game)
        except Exception:
            continue

    # Ordena por data (mais recentes primeiro) e limita pela janela
    try:
        games_validos.sort(key=lambda x: x.get("date", ""), reverse=True)
        games_validos = games_validos[:window_games]
    except Exception:
        games_validos = games_validos[:window_games]

    # Se não encontrou jogos válidos, usa fallback com dados da temporada atual
    if not games_validos:
        # Busca dados dos últimos 90 dias como fallback
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        
        games_fallback = []
        page = 1
        max_pages = 2
        
        while page <= max_pages:
            params = {
                "team_ids[]": team_id,
                "per_page": 25,
                "page": page,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }
            
            resp = balldontlie_get("games", params=params)
            if not resp or "data" not in resp:
                break
                
            games_fallback.extend(resp["data"])
            page += 1
        
        # Filtra jogos válidos do fallback
        for game in games_fallback:
            try:
                status = game.get("status", "").upper()
                home_score = game.get("home_team_score")
                visitor_score = game.get("visitor_team_score")
                
                if (status in ("FINAL", "FINAL/OT") and 
                    home_score is not None and 
                    visitor_score is not None and
                    home_score > 0 and visitor_score > 0):
                    games_validos.append(game)
            except Exception:
                continue
        
        # Ordena e limita novamente
        try:
            games_validos.sort(key=lambda x: x.get("date", ""), reverse=True)
            games_validos = games_validos[:window_games]
        except Exception:
            games_validos = games_validos[:window_games]

    # Calcula estatísticas
    if not games_validos:
        # Fallback para médias gerais da NBA 2024-2025
        stats = {
            "pts_for_avg": 114.5,  # Média atualizada da NBA
            "pts_against_avg": 114.5,
            "games": 0,
            "pts_diff_avg": 0.0,
            "win_rate": 0.5
        }
    else:
        pts_for = 0
        pts_against = 0
        wins = 0
        count = len(games_validos)

        for game in games_validos:
            try:
                home_id = game.get("home_team", {}).get("id")
                home_score = game.get("home_team_score", 0)
                visitor_score = game.get("visitor_team_score", 0)
                
                if home_id == team_id:
                    pts_for += home_score
                    pts_against += visitor_score
                    if home_score > visitor_score:
                        wins += 1
                else:
                    pts_for += visitor_score
                    pts_against += home_score
                    if visitor_score > home_score:
                        wins += 1
                        
            except Exception:
                continue

        if count > 0:
            stats = {
                "pts_for_avg": pts_for / count,
                "pts_against_avg": pts_against / count,
                "games": count,
                "pts_diff_avg": (pts_for - pts_against) / count,
                "win_rate": wins / count
            }
        else:
            stats = {
                "pts_for_avg": 114.5,
                "pts_against_avg": 114.5,
                "games": 0,
                "pts_diff_avg": 0.0,
                "win_rate": 0.5
            }

    cache[key] = stats
    salvar_cache_stats(cache)
    return stats

# =============================
# PREVISÕES COM DADOS REAIS 2024-2025
# =============================
def prever_total_points(home_id: int, away_id: int, window_games: int = 15) -> tuple[float, float, str]:
    """Previsão baseada em dados reais da temporada 2024-2025"""
    home_stats = obter_estatisticas_time_2025(home_id, window_games)
    away_stats = obter_estatisticas_time_2025(away_id, window_games)
    
    # Usa dados reais ou fallback se não houver dados suficientes
    home_avg = home_stats["pts_for_avg"]
    away_avg = away_stats["pts_for_avg"]
    
    # Ajuste para vantagem de casa
    home_advantage = 2.5
    estimativa = home_avg + away_avg + home_advantage
    
    # Calcula confiança baseada na quantidade de dados
    home_games = home_stats["games"]
    away_games = away_stats["games"]
    min_games = min(home_games, away_games)
    
    if min_games >= 10:
        confianca = 75.0
    elif min_games >= 5:
        confianca = 65.0
    elif min_games > 0:
        confianca = 55.0
    else:
        confianca = 45.0  # Dados insuficientes
    
    # Ajusta confiança baseado na consistência dos times
    home_consistency = min(10, home_stats.get("pts_diff_avg", 0) * 0.5)
    away_consistency = min(10, away_stats.get("pts_diff_avg", 0) * 0.5)
    confianca += (home_consistency + away_consistency)
    confianca = min(85.0, max(40.0, confianca))
    
    # Determina tendência baseada em dados reais
    if estimativa >= 235:
        tendencia = "Mais 235.5"
    elif estimativa >= 230:
        tendencia = "Mais 230.5"
    elif estimativa >= 225:
        tendencia = "Mais 225.5"
    elif estimativa >= 220:
        tendencia = "Mais 220.5"
    elif estimativa >= 215:
        tendencia = "Mais 215.5"
    elif estimativa >= 210:
        tendencia = "Mais 210.5"
    else:
        tendencia = "Menos 210.5"
        
    return round(estimativa, 1), round(confianca, 1), tendencia

def prever_vencedor(home_id: int, away_id: int, window_games: int = 15) -> tuple[str, float, str]:
    """Previsão de vencedor baseada em dados reais da temporada 2024-2025"""
    home_stats = obter_estatisticas_time_2025(home_id, window_games)
    away_stats = obter_estatisticas_time_2025(away_id, window_games)
    
    # Calcula vantagem baseada em performance histórica
    home_win_rate = home_stats["win_rate"]
    away_win_rate = away_stats["win_rate"]
    home_pts_diff = home_stats["pts_diff_avg"]
    away_pts_diff = away_stats["pts_diff_avg"]
    
    # Vantagem de jogar em casa (NBA: ~3-4 pontos)
    home_advantage = 0.1  # ~10% de aumento na win rate
    
    # Calcula probabilidade
    home_strength = home_win_rate + home_pts_diff * 0.01
    away_strength = away_win_rate + away_pts_diff * 0.01
    
    home_prob = home_strength / (home_strength + away_strength) + home_advantage
    away_prob = 1 - home_prob
    
    # Determina vencedor e confiança
    if home_prob > 0.6:
        vencedor = "Casa"
        confianca = min(85.0, home_prob * 100)
        detalhe = f"Forte vantagem da casa ({home_win_rate:.1%} win rate)"
    elif away_prob > 0.6:
        vencedor = "Visitante"
        confianca = min(85.0, away_prob * 100)
        detalhe = f"Visitante favorito ({away_win_rate:.1%} win rate)"
    elif home_prob > away_prob:
        vencedor = "Casa"
        confianca = home_prob * 100
        detalhe = f"Ligeira vantagem da casa"
    elif away_prob > home_prob:
        vencedor = "Visitante"
        confianca = away_prob * 100
        detalhe = f"Ligeira vantagem do visitante"
    else:
        vencedor = "Empate"
        confianca = 50.0
        detalhe = "Jogo muito equilibrado"
    
    # Ajusta confiança baseada na quantidade de dados
    min_games = min(home_stats["games"], away_stats["games"])
    if min_games < 5:
        confianca = max(40.0, confianca * 0.8)
    
    return vencedor, round(confianca, 1), detalhe

# =============================
# SISTEMA DE PÔSTERES PARA ALERTAS - VERSÃO MELHORADA
# =============================
def criar_poster_alerta(game: dict, predictions: dict, tipo: str = "previsao") -> Image.Image:
    """Cria um pôster estilizado COM PREVISÕES EM COLUNAS LADO A LADO E DATAS CORRIGIDAS"""
    try:
        # Configurações do pôster
        largura, altura = 600, 630
        img = Image.new('RGB', (largura, altura), color='#0c0c0c')
        draw = ImageDraw.Draw(img)
        
        # Tenta carregar fontes
        try:
            fonte_titulo = ImageFont.truetype("arialbd.ttf", 25)
            fonte_subtitulo = ImageFont.truetype("arial.ttf", 20)
            fonte_texto = ImageFont.truetype("arial.ttf", 20)
            fonte_pequena = ImageFont.truetype("arial.ttf", 18)
            fonte_grande = ImageFont.truetype("arialbd.ttf", 25)
        except:
            fonte_titulo = ImageFont.load_default(size=25)
            fonte_subtitulo = ImageFont.load_default(size=20)
            fonte_texto = ImageFont.load_default(size=20)
            fonte_pequena = ImageFont.load_default(size=18)
            fonte_grande = ImageFont.load_default(size=25)
        
        # Cores do tema
        cor_principal = "#1e3a8a"
        cor_destaque = "#fbbf24"
        cor_texto = "#ffffff"
        cor_verde = "#22c55e"
        cor_cinza = "#6b7280"
        
        y_pos = 20
        
        # HEADER
        draw.rectangle([0, y_pos, largura, y_pos + 60], fill=cor_principal)
        titulo_texto = "ELITE MASTER"
        bbox_titulo = draw.textbbox((0, 0), titulo_texto, font=fonte_titulo)
        largura_titulo = bbox_titulo[2] - bbox_titulo[0]
        draw.text(((largura - largura_titulo) // 2, y_pos + 20), titulo_texto, 
                 fill=cor_destaque, font=fonte_titulo)
        
        # Data de geração
        data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
        data_texto = f"Gerado em {data_geracao} - Elite Master System"
        bbox_data = draw.textbbox((0, 0), data_texto, font=fonte_pequena)
        largura_data = bbox_data[2] - bbox_data[0]
        draw.text(((largura - largura_data) // 2, y_pos + 80), data_texto, 
                 fill=cor_cinza, font=fonte_pequena)
        
        y_pos += 120
        
        # CAMPEONATO E DATA
        campeonato_texto = "NBA - TEMPORADA 2025-2026"
        bbox_camp = draw.textbbox((0, 0), campeonato_texto, font=fonte_subtitulo)
        largura_camp = bbox_camp[2] - bbox_camp[0]
        draw.text(((largura - largura_camp) // 2, y_pos), campeonato_texto, 
                 fill=cor_texto, font=fonte_subtitulo)
        
        # Data do jogo - VERSÃO CORRIGIDA
        data_jogo = game.get("date", "")
        if data_jogo:
            data_str, hora_str = formatar_data_api_para_local(data_jogo)
            data_jogo_texto = f"{data_str} {hora_str}"
        else:
            data_str, hora_str = "Data não definida", "Horário não definido"
            data_jogo_texto = "Data não definida"
        
        bbox_data_jogo = draw.textbbox((0, 0), data_jogo_texto, font=fonte_texto)
        largura_data_jogo = bbox_data_jogo[2] - bbox_data_jogo[0]
        draw.text(((largura - largura_data_jogo) // 2, y_pos + 30), data_jogo_texto, 
                 fill=cor_destaque, font=fonte_texto)
        
        y_pos += 80
        
        # CONFRONTO DOS TIMES - FORMATO HORIZONTAL
        home_team = game.get("home_team", {}).get("full_name", "Casa")
        away_team = game.get("visitor_team", {}).get("full_name", "Visitante")
        
        # Configurações do layout horizontal
        escudo_size = (95, 95)
        espacamento = 70
        largura_total_teams = (escudo_size[0] * 2) + espacamento + 100
        start_x = (largura - largura_total_teams) // 2
        
        # Time visitante (ESQUERDA)
        try:
            escudo_away = baixar_escudo_time(away_team, escudo_size)
            img.paste(escudo_away, (start_x, y_pos), escudo_away)
        except:
            pass
        
        # Nome visitante
        away_text = f"{away_team}"
        bbox_away = draw.textbbox((0, 0), away_text, font=fonte_texto)
        largura_away = bbox_away[2] - bbox_away[0]
        draw.text((start_x + escudo_size[0] // 2, y_pos + escudo_size[1] + 15), away_text, 
                 fill=cor_texto, font=fonte_texto, anchor="mm")
        
        # VS centralizado
        vs_x = start_x + escudo_size[0] + espacamento
        vs_text = "VS"
        bbox_vs = draw.textbbox((0, 0), vs_text, font=fonte_grande)
        draw.text((vs_x + 50 // 2, y_pos + escudo_size[1] // 2), vs_text, 
                 fill=cor_destaque, font=fonte_grande, anchor="mm")
        
        # Time da casa (DIREITA)
        home_x = vs_x + 50 + espacamento
        try:
            escudo_home = baixar_escudo_time(home_team, escudo_size)
            img.paste(escudo_home, (home_x, y_pos), escudo_home)
        except:
            pass
        
        # Nome casa
        home_text = f"{home_team}"
        bbox_home = draw.textbbox((0, 0), home_text, font=fonte_texto)
        largura_home = bbox_home[2] - bbox_home[0]
        draw.text((home_x + escudo_size[0] // 2, y_pos + escudo_size[1] + 15), home_text, 
                 fill=cor_texto, font=fonte_texto, anchor="mm")
        
        y_pos += escudo_size[1] + 50
        
        # Se for resultado, mostrar placar abaixo dos nomes
        if tipo == "resultado":
            home_score = game.get("home_team_score", 0)
            away_score = game.get("visitor_team_score", 0)
            
            # Placar visitante
            placar_away_text = f"{away_score}"
            draw.text((start_x + escudo_size[0] // 2, y_pos), placar_away_text, 
                     fill=cor_destaque, font=fonte_grande, anchor="mm")
            
            # Separador
            separador_text = "×"
            draw.text((vs_x + 50 // 2, y_pos), separador_text, 
                     fill=cor_texto, font=fonte_texto, anchor="mm")
            
            # Placar casa
            placar_home_text = f"{home_score}"
            draw.text((home_x + escudo_size[0] // 2, y_pos), placar_home_text, 
                     fill=cor_destaque, font=fonte_grande, anchor="mm")
            
            y_pos += 40
        
        y_pos += 40
        
        # PREVISÕES EM DUAS COLUNAS LADO A LADO
        if tipo == "previsao":
            # Configuração das colunas
            margem = 40
            largura_coluna = (largura - (margem * 3)) // 2  # 3 margens (esq, meio, dir)
            altura_previsao = 140
            
            # Container principal para as duas previsões
            draw.rectangle([margem, y_pos, largura - margem, y_pos + altura_previsao], 
                          fill="#1f2937", outline=cor_principal, width=2)
            
            # Linha divisória entre as colunas
            meio_x = largura // 2
            draw.line([meio_x, y_pos + 10, meio_x, y_pos + altura_previsao - 10], 
                     fill=cor_principal, width=1)
            
            # COLUNA 1: TOTAL DE PONTOS (ESQUERDA)
            total_pred = predictions.get("total", {})
            if total_pred:
                tendencia = total_pred.get('tendencia', 'N/A')
                estimativa = total_pred.get('estimativa', 0)
                confianca = total_pred.get('confianca', 0)
                
                # Título da coluna
                titulo_total = "TOTAL DE PONTOS"
                bbox_titulo_total = draw.textbbox((0, 0), titulo_total, font=fonte_subtitulo)
                largura_titulo_total = bbox_titulo_total[2] - bbox_titulo_total[0]
                draw.text((margem + largura_coluna // 2, y_pos + 20), titulo_total, 
                         fill=cor_destaque, font=fonte_subtitulo, anchor="mm")
                
                # Tendência
                tendencia_texto = f"Tendência: {tendencia}"
                draw.text((margem + 20, y_pos + 50), tendencia_texto, 
                         fill=cor_texto, font=fonte_texto)
                
                # Estimativa
                estimativa_texto = f"Estimativa: {estimativa:.1f}"
                draw.text((margem + 20, y_pos + 75), estimativa_texto, 
                         fill=cor_texto, font=fonte_texto)
                
                # Confiança
                confianca_texto = f"Confiança: {confianca:.0f}%"
                draw.text((margem + 20, y_pos + 100), confianca_texto, 
                         fill=cor_texto, font=fonte_texto)
            
            # COLUNA 2: VENCEDOR (DIREITA)
            vencedor_pred = predictions.get("vencedor", {})
            if vencedor_pred:
                vencedor = vencedor_pred.get('vencedor', 'N/A')
                confianca_venc = vencedor_pred.get('confianca', 0)
                detalhe = vencedor_pred.get('detalhe', '')
                
                # Título da coluna
                titulo_vencedor = "VENCEDOR"
                bbox_titulo_vencedor = draw.textbbox((0, 0), titulo_vencedor, font=fonte_subtitulo)
                largura_titulo_vencedor = bbox_titulo_vencedor[2] - bbox_titulo_vencedor[0]
                draw.text((meio_x + largura_coluna // 2, y_pos + 20), titulo_vencedor, 
                         fill=cor_destaque, font=fonte_subtitulo, anchor="mm")
                
                # Vencedor
                vencedor_texto = f"Previsão: {vencedor}"
                draw.text((meio_x + 20, y_pos + 50), vencedor_texto, 
                         fill=cor_texto, font=fonte_texto)
                
                # Confiança
                confianca_venc_texto = f"Confiança: {confianca_venc:.0f}%"
                draw.text((meio_x + 20, y_pos + 75), confianca_venc_texto, 
                         fill=cor_texto, font=fonte_texto)
                
                # Detalhe (se couber)
                if detalhe and len(detalhe) < 30:  # Só mostra se for curto
                    detalhe_texto = f"Detalhe: {detalhe}"
                    draw.text((meio_x + 20, y_pos + 100), detalhe_texto, 
                             fill=cor_texto, font=fonte_pequena)
            
            y_pos += altura_previsao + 20
        
        elif tipo == "resultado":
            # RESULTADOS EM DUAS COLUNAS
            home_score = game.get("home_team_score", 0)
            away_score = game.get("visitor_team_score", 0)
            total_pontos = home_score + away_score
            
            # Configuração das colunas para resultados
            margem = 40
            largura_coluna = (largura - (margem * 3)) // 2
            altura_resultado = 120
            
            draw.rectangle([margem, y_pos, largura - margem, y_pos + altura_resultado], 
                          fill="#1f2937", outline=cor_principal, width=2)
            
            # Linha divisória
            meio_x = largura // 2
            draw.line([meio_x, y_pos + 10, meio_x, y_pos + altura_resultado - 10], 
                     fill=cor_principal, width=1)
            
            # COLUNA 1: RESULTADO TOTAL
            total_pred = predictions.get("total", {})
            if total_pred:
                tendencia_total = total_pred.get('tendencia', '')
                resultado_total = calcular_resultado_total(total_pontos, tendencia_total)
                cor_resultado = cor_verde if "GREEN" in resultado_total else "#ef4444"
                
                titulo_total = "TOTAL DE PONTOS"
                bbox_titulo_total = draw.textbbox((0, 0), titulo_total, font=fonte_subtitulo)
                draw.text((margem + largura_coluna // 2, y_pos + 20), titulo_total, 
                         fill=cor_destaque, font=fonte_subtitulo, anchor="mm")
                
                resultado_texto = f"Resultado: {resultado_total}"
                draw.text((margem + 20, y_pos + 50), resultado_texto, 
                         fill=cor_resultado, font=fonte_texto)
                
                pontos_texto = f"Pontos: {total_pontos}"
                draw.text((margem + 20, y_pos + 80), pontos_texto, 
                         fill=cor_texto, font=fonte_texto)
            
            # COLUNA 2: RESULTADO VENCEDOR
            vencedor_pred = predictions.get("vencedor", {})
            if vencedor_pred:
                vencedor_previsto = vencedor_pred.get('vencedor', '')
                resultado_vencedor = calcular_resultado_vencedor(home_score, away_score, vencedor_previsto)
                cor_resultado = cor_verde if "GREEN" in resultado_vencedor else "#ef4444"
                
                titulo_vencedor = "VENCEDOR"
                bbox_titulo_vencedor = draw.textbbox((0, 0), titulo_vencedor, font=fonte_subtitulo)
                draw.text((meio_x + largura_coluna // 2, y_pos + 20), titulo_vencedor, 
                         fill=cor_destaque, font=fonte_subtitulo, anchor="mm")
                
                resultado_texto = f"Resultado: {resultado_vencedor}"
                draw.text((meio_x + 20, y_pos + 50), resultado_texto, 
                         fill=cor_resultado, font=fonte_texto)
                
                placar_texto = f"Placar: {away_score}-{home_score}"
                draw.text((meio_x + 20, y_pos + 80), placar_texto, 
                         fill=cor_texto, font=fonte_texto)
            
            y_pos += altura_resultado + 20
        
        # FOOTER
        footer_y = altura - 40
        draw.rectangle([0, footer_y, largura, altura], fill=cor_principal)
        
        footer_texto = "Sistema de Previsões NBA - Dados 2024-2025"
        bbox_footer = draw.textbbox((0, 0), footer_texto, font=fonte_pequena)
        largura_footer = bbox_footer[2] - bbox_footer[0]
        draw.text(((largura - largura_footer) // 2, footer_y + 12), footer_texto, 
                 fill=cor_texto, font=fonte_pequena)
        
        return img
        
    except Exception as e:
        print(f"Erro ao criar pôster: {e}")
        return criar_poster_fallback_colunas(game, predictions, tipo)

def criar_poster_fallback_colunas(game: dict, predictions: dict, tipo: str) -> Image.Image:
    """Fallback com colunas lado a lado"""
    largura, altura = 600, 500
    img = Image.new('RGB', (largura, altura), color='#0c0c0c')
    draw = ImageDraw.Draw(img)
    
    # Header
    draw.rectangle([0, 0, largura, 60], fill='#1e3a8a')
    draw.text((largura//2, 30), "ELITE MASTER", fill='#fbbf24', anchor="mm")
    
    # Times na horizontal
    home_team = game.get("home_team", {}).get("full_name", "Casa")
    away_team = game.get("visitor_team", {}).get("full_name", "Visitante")
    
    draw.text((150, 120), away_team, fill='white', anchor="mm")
    draw.text((largura//2, 120), "VS", fill='#fbbf24', anchor="mm")
    draw.text((450, 120), home_team, fill='white', anchor="mm")
    
    # Previsões em colunas
    draw.rectangle([50, 180, largura-50, 300], fill='#1f2937', outline='#1e3a8a')
    draw.line([largura//2, 190, largura//2, 290], fill='#1e3a8a')
    
    # Coluna esquerda - Total
    total_pred = predictions.get("total", {})
    if total_pred:
        draw.text((100, 200), "TOTAL", fill='#fbbf24', anchor="mm")
        draw.text((100, 230), f"{total_pred.get('tendencia', 'N/A')}", fill='white', anchor="mm")
        draw.text((100, 260), f"{total_pred.get('confianca', 0)}%", fill='white', anchor="mm")
    
    # Coluna direita - Vencedor
    vencedor_pred = predictions.get("vencedor", {})
    if vencedor_pred:
        draw.text((500, 200), "VENCEDOR", fill='#fbbf24', anchor="mm")
        draw.text((500, 230), f"{vencedor_pred.get('vencedor', 'N/A')}", fill='white', anchor="mm")
        draw.text((500, 260), f"{vencedor_pred.get('confianca', 0)}%", fill='white', anchor="mm")
    
    draw.text((largura//2, 350), "Sistema NBA 2024-2025", fill='white', anchor="mm")
    
    return img

def calcular_resultado_total(total_pontos: int, tendencia: str) -> str:
    """Calcula se a previsão de total foi Green ou Red"""
    if "Mais" in tendencia:
        try:
            limite = float(tendencia.split()[-1])
            return "🟢 GREEN" if total_pontos > limite else "🔴 RED"
        except:
            return "⚪ INDEFINIDO"
    elif "Menos" in tendencia:
        try:
            limite = float(tendencia.split()[-1])
            return "🟢 GREEN" if total_pontos < limite else "🔴 RED"
        except:
            return "⚪ INDEFINIDO"
    return "⚪ INDEFINIDO"

def calcular_resultado_vencedor(home_score: int, away_score: int, vencedor_previsto: str) -> str:
    """Calcula se a previsão de vencedor foi Green ou Red"""
    if vencedor_previsto == "Casa" and home_score > away_score:
        return "🟢 GREEN"
    elif vencedor_previsto == "Visitante" and away_score > home_score:
        return "🟢 GREEN"
    elif vencedor_previsto == "Empate" and home_score == away_score:
        return "🟢 GREEN"
    elif vencedor_previsto in ["Casa", "Visitante", "Empate"]:
        return "🔴 RED"
    return "⚪ INDEFINIDO"

def enviar_poster_telegram(poster_img: Image.Image, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia o pôster como imagem para o Telegram"""
    try:
        # Converte a imagem para bytes
        img_byte_arr = io.BytesIO()
        poster_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # Envia para o Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        files = {'photo': ('poster.png', img_byte_arr, 'image/png')}
        data = {'chat_id': chat_id}
        
        response = requests.post(url, files=files, data=data, timeout=30)
        return response.status_code == 200
        
    except Exception as e:
        print(f"Erro ao enviar pôster: {e}")
        return False

# =============================
# SISTEMA DE ALERTAS APENAS COM PÔSTERES
# =============================

def verificar_e_enviar_alerta(game: dict, predictions: dict, send_to_telegram: bool = False):
    """Sistema de alertas APENAS com pôsteres - versão simplificada"""
    alertas = carregar_alertas()
    fid = str(game.get("id"))
    
    if fid not in alertas:
        alertas[fid] = {
            "game_id": fid,
            "game_data": game,
            "predictions": predictions,
            "timestamp": datetime.now().isoformat(),
            "enviado_telegram": False,
            "conferido": False,
            "alerta_resultado_enviado": False,
            "poster_enviado": False
        }
        salvar_alertas(alertas)
        
        # SEMPRE envia apenas o pôster, não envia mensagem textual
        if send_to_telegram:
            try:
                # Cria e envia pôster de previsão
                poster = criar_poster_alerta(game, predictions, "previsao")
                
                # Envia apenas o pôster
                if enviar_poster_telegram(poster):
                    alertas[fid]["poster_enviado"] = True
                    alertas[fid]["enviado_telegram"] = True
                    salvar_alertas(alertas)
                    return True
                else:
                    return False
                    
            except Exception as e:
                print(f"Erro no sistema de pôster: {e}")
                return False
        return True
    return False

def enviar_alerta_resultado_individual(alerta_id: str, alerta: dict):
    """Envia alerta individual de resultado APENAS com pôster"""
    game_data = alerta.get("game_data", {})
    predictions = alerta.get("predictions", {})
    
    # Cria pôster de resultado
    poster = criar_poster_alerta(game_data, predictions, "resultado")
    
    # Envia APENAS o pôster, sem mensagem textual
    if enviar_poster_telegram(poster, TELEGRAM_CHAT_ID_ALT2):
        return True
    
    return False

def enviar_alerta_resultados_conferidos():
    """Versão atualizada - envia APENAS pôsteres para resultados"""
    alertas = carregar_alertas()
    
    # Filtra apenas jogos conferidos sem alerta de resultado
    jogos_conferidos = []
    for alerta_id, alerta in alertas.items():
        if alerta.get("conferido", False) and not alerta.get("alerta_resultado_enviado", False):
            jogos_conferidos.append((alerta_id, alerta))
    
    if not jogos_conferidos:
        st.info("ℹ️ Nenhum jogo conferido novo para alerta.")
        return 0
    
    st.info(f"📤 Preparando pôsteres para {len(jogos_conferidos)} jogos conferidos...")
    
    alertas_enviados = 0
    
    for alerta_id, alerta in jogos_conferidos:
        # Envia APENAS o pôster individual para cada jogo
        if enviar_alerta_resultado_individual(alerta_id, alerta):
            alertas[alerta_id]["alerta_resultado_enviado"] = True
            alertas_enviados += 1
            st.success(f"✅ Pôster de resultado enviado para jogo {alerta_id}")
        else:
            st.error(f"❌ Erro ao enviar pôster para jogo {alerta_id}")
        
        # Pequena pausa entre envios
        time.sleep(2)
    
    # NÃO envia mensagem consolidada final - apenas os pôsteres individuais
    
    if alertas_enviados > 0:
        salvar_alertas(alertas)
        st.success(f"🎉 {alertas_enviados} pôsteres de resultado enviados!")
        return alertas_enviados
    
    return 0

# =============================
# SISTEMA TOP 4 MELHORES JOGOS - ATUALIZADO COM PÔSTERES
# =============================

def calcular_pontuacao_jogo(jogo: dict, times_stats: dict) -> float:
    """Calcula pontuação para ranking dos melhores jogos"""
    home_team_id = jogo["home_team"]["id"]
    visitor_team_id = jogo["visitor_team"]["id"]
    
    # Obtém estatísticas dos times
    home_stats = times_stats.get(home_team_id, {})
    visitor_stats = times_stats.get(visitor_team_id, {})
    
    if not home_stats or not visitor_stats:
        return 0
    
    # Fatores para cálculo da pontuação:
    # 1. Potencial ofensivo (média de pontos dos dois times)
    ofensiva_total = home_stats.get("pts_for_avg", 0) + visitor_stats.get("pts_for_avg", 0)
    
    # 2. Competitividade (diferença pequena na taxa de vitórias)
    diff_win_rate = abs(home_stats.get("win_rate", 0) - visitor_stats.get("win_rate", 0))
    fator_competitividade = 1.0 - (diff_win_rate * 0.5)  # Times com win_rate similar = jogos mais disputados
    
    # 3. Consistência dos times
    home_consistencia = min(20, abs(home_stats.get("pts_diff_avg", 0)) * 2)
    visitor_consistencia = min(20, abs(visitor_stats.get("pts_diff_avg", 0)) * 2)
    fator_consistencia = (home_consistencia + visitor_consistencia) / 2
    
    # Pontuação final
    pontuacao = (ofensiva_total * 0.3) + (fator_competitividade * 40) + fator_consistencia
    
    return pontuacao

def obter_top4_melhores_jogos(data_str: str) -> list:
    """Retorna os 4 melhores jogos do dia baseado em estatísticas"""
    jogos = obter_jogos_data(data_str)
    
    if not jogos:
        return []
    
    # Obtém estatísticas de todos os times envolvidos
    times_stats = {}
    times_cache = obter_times()
    
    for jogo in jogos:
        for team_type in ["home_team", "visitor_team"]:
            team_id = jogo[team_type]["id"]
            if team_id not in times_stats:
                times_stats[team_id] = obter_estatisticas_time_2025(team_id)
    
    # Calcula pontuação para cada jogo
    jogos_com_pontuacao = []
    for jogo in jogos:
        pontuacao = calcular_pontuacao_jogo(jogo, times_stats)
        
        # Obtém nomes completos dos times
        home_team_name = times_cache.get(jogo["home_team"]["id"], {}).get("full_name", jogo["home_team"]["name"])
        visitor_team_name = times_cache.get(jogo["visitor_team"]["id"], {}).get("full_name", jogo["visitor_team"]["name"])
        
        # Calcula previsões para o jogo
        home_id = jogo["home_team"]["id"]
        visitor_id = jogo["visitor_team"]["id"]
        
        try:
            total_estim, total_conf, total_tend = prever_total_points(home_id, visitor_id)
            vencedor, vencedor_conf, vencedor_detalhe = prever_vencedor(home_id, visitor_id)
            
            predictions = {
                "total": {
                    "estimativa": total_estim,
                    "confianca": total_conf,
                    "tendencia": total_tend
                },
                "vencedor": {
                    "vencedor": vencedor,
                    "confianca": vencedor_conf,
                    "detalhe": vencedor_detalhe
                }
            }
        except Exception as e:
            predictions = {
                "total": {"estimativa": 0, "confianca": 0, "tendencia": "N/A"},
                "vencedor": {"vencedor": "N/A", "confianca": 0, "detalhe": "Erro na previsão"}
            }
        
        jogos_com_pontuacao.append({
            "jogo": jogo,
            "pontuacao": pontuacao,
            "home_team_name": home_team_name,
            "visitor_team_name": visitor_team_name,
            "home_stats": times_stats.get(home_id, {}),
            "visitor_stats": times_stats.get(visitor_id, {}),
            "predictions": predictions
        })
    
    # Ordena por pontuação (decrescente) e pega top 4
    jogos_com_pontuacao.sort(key=lambda x: x["pontuacao"], reverse=True)
    return jogos_com_pontuacao[:4]

# =============================
# SISTEMA DE ALERTA TOP 4 COMPACTO
# =============================

def criar_poster_top4_compacto(jogos_top4: list) -> Image.Image:
    """Cria um pôster compacto com os 4 melhores jogos do dia"""
    try:
        # Configurações do pôster compacto
        largura, altura = 600, 1000
        img = Image.new('RGB', (largura, altura), color='#0c0c0c')
        draw = ImageDraw.Draw(img)
        
        # Tenta carregar fontes
        try:
            fonte_titulo = ImageFont.truetype("arialbd.ttf", 28)
            fonte_subtitulo = ImageFont.truetype("arial.ttf", 18)
            fonte_texto = ImageFont.truetype("arial.ttf", 16)
            fonte_pequena = ImageFont.truetype("arial.ttf", 14)
            fonte_destaque = ImageFont.truetype("arialbd.ttf", 16)
            fonte_cabecalho = ImageFont.truetype("arial.ttf", 15)
        except:
            fonte_titulo = ImageFont.load_default(size=28)
            fonte_subtitulo = ImageFont.load_default(size=18)
            fonte_texto = ImageFont.load_default(size=16)
            fonte_pequena = ImageFont.load_default(size=14)
            fonte_destaque = ImageFont.load_default(size=16)
            fonte_cabecalho = ImageFont.load_default(size=15)
        
        # Cores do tema
        cor_principal = "#1e3a8a"
        cor_destaque = "#fbbf24"
        cor_texto = "#ffffff"
        cor_verde = "#22c55e"
        cor_cinza = "#6b7280"
        cor_fundo_card = "#1f2937"
        cor_info = "#60a5fa"
        
        y_pos = 20
        
        # HEADER PRINCIPAL
        draw.rectangle([0, y_pos, largura, y_pos + 80], fill=cor_principal)
        titulo_texto = "ELITE MASTER - TOP 4 JOGOS DO DIA"
        bbox_titulo = draw.textbbox((0, 0), titulo_texto, font=fonte_titulo)
        largura_titulo = bbox_titulo[2] - bbox_titulo[0]
        draw.text(((largura - largura_titulo) // 2, y_pos + 25), titulo_texto, 
                 fill=cor_destaque, font=fonte_titulo)
        
        # Data de geração
        data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
        data_texto = f"Gerado em {data_geracao} - Sistema Elite Master"
        bbox_data = draw.textbbox((0, 0), data_texto, font=fonte_pequena)
        largura_data = bbox_data[2] - bbox_data[0]
        draw.text(((largura - largura_data) // 2, y_pos + 90), data_texto, 
                 fill=cor_cinza, font=fonte_pequena)
        
        y_pos += 120
        
        # CABEÇALHO INFORMATIVO - DESCRIÇÃO DO ALERTA
        cabecalho_rect_height = 80
        draw.rectangle([20, y_pos, largura-20, y_pos + cabecalho_rect_height], 
                      fill="#1e3a8a", outline=cor_destaque, width=2)
        
        # Textos do cabeçalho informativo
        textos_cabecalho = [
            "🎯 ALERTA TOP 4 JOGOS COMPOSTOS 🎯",
            "Análise baseada em dados estatísticos da temporada 2024-2025",
            "Tendências de apostas: Total de Pontos e Vencedor",
            "Confiança mínima: 60% | Dados atualizados em tempo real"
        ]
        
        for i, texto in enumerate(textos_cabecalho):
            bbox_texto = draw.textbbox((0, 0), texto, font=fonte_cabecalho)
            largura_texto = bbox_texto[2] - bbox_texto[0]
            
            if i == 0:  # Primeira linha (título)
                draw.text(((largura - largura_texto) // 2, y_pos + 15), texto, 
                         fill=cor_destaque, font=fonte_cabecalho)
            else:  # Linhas subsequentes
                draw.text(((largura - largura_texto) // 2, y_pos + 25 + (i * 15)), texto, 
                         fill=cor_texto, font=fonte_cabecalho)
        
        y_pos += cabecalho_rect_height + 20
        
        # LEGENDA DAS INFORMAÇÕES
        info_legenda = [
            "📊 TOTAL PTS: Tendência de pontos totais do jogo",
            "🏆 VENCEDOR: Previsão do time vencedor", 
            "🎯 CONF: Nível de confiança da previsão"
        ]
        
        for i, legenda in enumerate(info_legenda):
            draw.text((50, y_pos + (i * 18)), legenda, 
                     fill=cor_info, font=fonte_pequena)
        
        y_pos += 60
        
        # Para cada jogo no top 4
        altura_jogo = 150
        espacamento = 20
        
        for i, jogo_info in enumerate(jogos_top4):
            if i >= 4:
                break
                
            jogo = jogo_info["jogo"]
            predictions = jogo_info["predictions"]
            
            # Container do jogo
            draw.rectangle([30, y_pos, largura-30, y_pos + altura_jogo], 
                          fill=cor_fundo_card, outline=cor_principal, width=2)
            
            # Número do jogo no ranking
            draw.ellipse([45, y_pos + 15, 75, y_pos + 45], fill=cor_destaque, outline=cor_principal)
            draw.text((60, y_pos + 30), str(i+1), fill=cor_principal, font=fonte_destaque, anchor="mm")
            
            # Times e escudos
            home_team = jogo.get("home_team", {}).get("full_name", "Casa")
            away_team = jogo.get("visitor_team", {}).get("full_name", "Visitante")
            
            # Escudos pequenos
            escudo_size = (40, 40)
            try:
                escudo_away = baixar_escudo_time(away_team, escudo_size)
                img.paste(escudo_away, (85, y_pos + 15), escudo_away)
                
                escudo_home = baixar_escudo_time(home_team, escudo_size)
                img.paste(escudo_home, (largura-85-escudo_size[0], y_pos + 15), escudo_home)
            except:
                pass
            
            # Nomes dos times (abreviados se necessário)
            def abreviar_nome(nome):
                if len(nome) > 15:
                    partes = nome.split()
                    if len(partes) >= 2:
                        return partes[0][0] + ". " + " ".join(partes[1:])
                    return nome[:12] + "..."
                return nome
            
            away_abreviado = abreviar_nome(away_team)
            home_abreviado = abreviar_nome(home_team)
            
            # Nomes dos times
            draw.text((85 + escudo_size[0]//2, y_pos + 60), away_abreviado, 
                     fill=cor_texto, font=fonte_pequena, anchor="mm")
            draw.text((largura-85-escudo_size[0]//2, y_pos + 60), home_abreviado, 
                     fill=cor_texto, font=fonte_pequena, anchor="mm")
            
            # VS no meio
            draw.text((largura//2, y_pos + 30), "VS", 
                     fill=cor_destaque, font=fonte_subtitulo, anchor="mm")
            
            # Previsões em colunas compactas
            coluna_largura = (largura - 180) // 2
            coluna_x1 = 100
            coluna_x2 = coluna_x1 + coluna_largura + 20
            
            # Coluna 1: Total de Pontos
            total_pred = predictions.get("total", {})
            if total_pred:
                tendencia = total_pred.get('tendencia', 'N/A')
                estimativa = total_pred.get('estimativa', 0)
                confianca = total_pred.get('confianca', 0)
                
                draw.text((coluna_x1, y_pos + 80), "TOTAL PTS", 
                         fill=cor_destaque, font=fonte_pequena)
                draw.text((coluna_x1, y_pos + 95), f"{tendencia}", 
                         fill=cor_texto, font=fonte_pequena)
                draw.text((coluna_x1, y_pos + 110), f"Est: {estimativa:.1f} | {confianca:.0f}%", 
                         fill=cor_texto, font=fonte_pequena)
            
            # Coluna 2: Vencedor
            vencedor_pred = predictions.get("vencedor", {})
            if vencedor_pred:
                vencedor = vencedor_pred.get('vencedor', 'N/A')
                confianca_venc = vencedor_pred.get('confianca', 0)
                
                # Abrevia o vencedor se necessário
                if vencedor == "Casa":
                    vencedor_abreviado = "CASA"
                elif vencedor == "Visitante":
                    vencedor_abreviado = "VISIT"
                else:
                    vencedor_abreviado = vencedor[:8]
                
                draw.text((coluna_x2, y_pos + 80), "VENCEDOR", 
                         fill=cor_destaque, font=fonte_pequena)
                draw.text((coluna_x2, y_pos + 95), f"{vencedor_abreviado}", 
                         fill=cor_texto, font=fonte_pequena)
                draw.text((coluna_x2, y_pos + 110), f"Conf: {confianca_venc:.0f}%", 
                         fill=cor_texto, font=fonte_pequena)
            
            # Linha divisória entre jogos (exceto no último)
            if i < min(3, len(jogos_top4)-1):
                draw.line([50, y_pos + altura_jogo - 5, largura-50, y_pos + altura_jogo - 5], 
                         fill=cor_principal, width=1)
            
            y_pos += altura_jogo
        
        # FOOTER
        footer_y = altura - 40
        draw.rectangle([0, footer_y, largura, altura], fill=cor_principal)
        
        footer_texto = "TOP 4 JOGOS NBA - ANÁLISE ESTATÍSTICA - TENDÊNCIAS DE APOSTAS - DADOS 2024-2025"
        bbox_footer = draw.textbbox((0, 0), footer_texto, font=fonte_pequena)
        largura_footer = bbox_footer[2] - bbox_footer[0]
        draw.text(((largura - largura_footer) // 2, footer_y + 12), footer_texto, 
                 fill=cor_texto, font=fonte_pequena)
        
        return img
        
    except Exception as e:
        print(f"Erro ao criar pôster top4 compacto: {e}")
        # Fallback simples
        img = Image.new('RGB', (600, 400), color='#0c0c0c')
        draw = ImageDraw.Draw(img)
        draw.text((300, 200), "Erro ao gerar pôster Top 4", fill='white', anchor="mm")
        return img

def criar_poster_top4_resultado(alerta_top4: dict) -> Image.Image:
    """Cria um pôster de resultado para o Top 4 mostrando Green/Red"""
    try:
        # Configurações do pôster compacto
        largura, altura = 600, 1000
        img = Image.new('RGB', (largura, altura), color='#0c0c0c')
        draw = ImageDraw.Draw(img)
        
        # Tenta carregar fontes
        try:
            fonte_titulo = ImageFont.truetype("arialbd.ttf", 28)
            fonte_subtitulo = ImageFont.truetype("arial.ttf", 18)
            fonte_texto = ImageFont.truetype("arial.ttf", 16)
            fonte_pequena = ImageFont.truetype("arial.ttf", 14)
            fonte_destaque = ImageFont.truetype("arialbd.ttf", 16)
            fonte_cabecalho = ImageFont.truetype("arial.ttf", 15)
        except:
            fonte_titulo = ImageFont.load_default(size=28)
            fonte_subtitulo = ImageFont.load_default(size=18)
            fonte_texto = ImageFont.load_default(size=16)
            fonte_pequena = ImageFont.load_default(size=14)
            fonte_destaque = ImageFont.load_default(size=16)
            fonte_cabecalho = ImageFont.load_default(size=15)
        
        # Cores do tema
        cor_principal = "#1e3a8a"
        cor_destaque = "#fbbf24"
        cor_texto = "#ffffff"
        cor_verde = "#22c55e"
        cor_vermelho = "#ef4444"
        cor_cinza = "#6b7280"
        cor_fundo_card = "#1f2937"
        cor_info = "#60a5fa"
        
        y_pos = 20
        
        # HEADER PRINCIPAL
        draw.rectangle([0, y_pos, largura, y_pos + 80], fill=cor_principal)
        titulo_texto = "ELITE MASTER - RESULTADO TOP 4"
        bbox_titulo = draw.textbbox((0, 0), titulo_texto, font=fonte_titulo)
        largura_titulo = bbox_titulo[2] - bbox_titulo[0]
        draw.text(((largura - largura_titulo) // 2, y_pos + 25), titulo_texto, 
                 fill=cor_destaque, font=fonte_titulo)
        
        # Data dos jogos
        data_jogos = alerta_top4.get("data_jogos", "")
        data_texto = f"Resultados dos jogos do dia {data_jogos}"
        bbox_data = draw.textbbox((0, 0), data_texto, font=fonte_pequena)
        largura_data = bbox_data[2] - bbox_data[0]
        draw.text(((largura - largura_data) // 2, y_pos + 90), data_texto, 
                 fill=cor_cinza, font=fonte_pequena)
        
        y_pos += 120
        
        # CABEÇALHO INFORMATIVO - DESCRIÇÃO DOS RESULTADOS
        cabecalho_rect_height = 80
        draw.rectangle([20, y_pos, largura-20, y_pos + cabecalho_rect_height], 
                      fill="#1e3a8a", outline=cor_destaque, width=2)
        
        # Textos do cabeçalho informativo
        textos_cabecalho = [
            "📊 RESULTADO OFICIAL - TOP 4 JOGOS COMPOSTOS 📊",
            "Conferência baseada nos resultados reais dos jogos",
            "🟢 GREEN: Previsão correta | 🔴 RED: Previsão incorreta",
            "Sistema de análise estatística - Elite Master"
        ]
        
        for i, texto in enumerate(textos_cabecalho):
            bbox_texto = draw.textbbox((0, 0), texto, font=fonte_cabecalho)
            largura_texto = bbox_texto[2] - bbox_texto[0]
            
            if i == 0:  # Primeira linha (título)
                draw.text(((largura - largura_texto) // 2, y_pos + 15), texto, 
                         fill=cor_destaque, font=fonte_cabecalho)
            else:  # Linhas subsequentes
                draw.text(((largura - largura_texto) // 2, y_pos + 25 + (i * 15)), texto, 
                         fill=cor_texto, font=fonte_cabecalho)
        
        y_pos += cabecalho_rect_height + 20
        
        # Para cada jogo no top 4
        altura_jogo = 150
        espacamento = 20
        
        for i, jogo_data in enumerate(alerta_top4["jogos"]):
            if i >= 4:
                break
                
            jogo = jogo_data["jogo"]
            predictions = jogo_data["predictions"]
            resultado_total = jogo_data.get("resultado_total", None)
            resultado_vencedor = jogo_data.get("resultado_vencedor", None)
            
            # Container do jogo
            draw.rectangle([30, y_pos, largura-30, y_pos + altura_jogo], 
                          fill=cor_fundo_card, outline=cor_principal, width=2)
            
            # Número do jogo no ranking
            draw.ellipse([45, y_pos + 15, 75, y_pos + 45], fill=cor_destaque, outline=cor_principal)
            draw.text((60, y_pos + 30), str(i+1), fill=cor_principal, font=fonte_destaque, anchor="mm")
            
            # Times e escudos
            home_team = jogo.get("home_team", {}).get("full_name", "Casa")
            away_team = jogo.get("visitor_team", {}).get("full_name", "Visitante")
            
            # Escudos pequenos
            escudo_size = (40, 40)
            try:
                escudo_away = baixar_escudo_time(away_team, escudo_size)
                img.paste(escudo_away, (85, y_pos + 15), escudo_away)
                
                escudo_home = baixar_escudo_time(home_team, escudo_size)
                img.paste(escudo_home, (largura-85-escudo_size[0], y_pos + 15), escudo_home)
            except:
                pass
            
            # Nomes dos times (abreviados se necessário)
            def abreviar_nome(nome):
                if len(nome) > 15:
                    partes = nome.split()
                    if len(partes) >= 2:
                        return partes[0][0] + ". " + " ".join(partes[1:])
                    return nome[:12] + "..."
                return nome
            
            away_abreviado = abreviar_nome(away_team)
            home_abreviado = abreviar_nome(home_team)
            
            # Nomes dos times
            draw.text((85 + escudo_size[0]//2, y_pos + 60), away_abreviado, 
                     fill=cor_texto, font=fonte_pequena, anchor="mm")
            draw.text((largura-85-escudo_size[0]//2, y_pos + 60), home_abreviado, 
                     fill=cor_texto, font=fonte_pequena, anchor="mm")
            
            # VS no meio
            draw.text((largura//2, y_pos + 30), "VS", 
                     fill=cor_destaque, font=fonte_subtitulo, anchor="mm")
            
            # Previsões em colunas compactas
            coluna_largura = (largura - 180) // 2
            coluna_x1 = 100
            coluna_x2 = coluna_x1 + coluna_largura + 20
            
            # Coluna 1: Total de Pontos
            total_pred = predictions.get("total", {})
            if total_pred:
                tendencia = total_pred.get('tendencia', 'N/A')
                estimativa = total_pred.get('estimativa', 0)
                confianca = total_pred.get('confianca', 0)
                
                draw.text((coluna_x1, y_pos + 80), "TOTAL PTS", 
                         fill=cor_destaque, font=fonte_pequena)
                draw.text((coluna_x1, y_pos + 95), f"{tendencia}", 
                         fill=cor_texto, font=fonte_pequena)
                draw.text((coluna_x1, y_pos + 110), f"Est: {estimativa:.1f} | {confianca:.0f}%", 
                         fill=cor_texto, font=fonte_pequena)
                
                # Resultado (Green/Red)
                if resultado_total == "Green":
                    cor_resultado = cor_verde
                    texto_resultado = "🟢 GREEN"
                elif resultado_total == "Red":
                    cor_resultado = cor_vermelho
                    texto_resultado = "🔴 RED"
                else:
                    cor_resultado = cor_cinza
                    texto_resultado = "⚪ PENDENTE"
                
                draw.text((coluna_x1, y_pos + 125), texto_resultado, 
                         fill=cor_resultado, font=fonte_pequena)
            
            # Coluna 2: Vencedor
            vencedor_pred = predictions.get("vencedor", {})
            if vencedor_pred:
                vencedor = vencedor_pred.get('vencedor', 'N/A')
                confianca_venc = vencedor_pred.get('confianca', 0)
                
                # Abrevia o vencedor se necessário
                if vencedor == "Casa":
                    vencedor_abreviado = "CASA"
                elif vencedor == "Visitante":
                    vencedor_abreviado = "VISIT"
                else:
                    vencedor_abreviado = vencedor[:8]
                
                draw.text((coluna_x2, y_pos + 80), "VENCEDOR", 
                         fill=cor_destaque, font=fonte_pequena)
                draw.text((coluna_x2, y_pos + 95), f"{vencedor_abreviado}", 
                         fill=cor_texto, font=fonte_pequena)
                draw.text((coluna_x2, y_pos + 110), f"Conf: {confianca_venc:.0f}%", 
                         fill=cor_texto, font=fonte_pequena)
                
                # Resultado (Green/Red)
                if resultado_vencedor == "Green":
                    cor_resultado = cor_verde
                    texto_resultado = "🟢 GREEN"
                elif resultado_vencedor == "Red":
                    cor_resultado = cor_vermelho
                    texto_resultado = "🔴 RED"
                else:
                    cor_resultado = cor_cinza
                    texto_resultado = "⚪ PENDENTE"
                
                draw.text((coluna_x2, y_pos + 125), texto_resultado, 
                         fill=cor_resultado, font=fonte_pequena)
            
            # Linha divisória entre jogos (exceto no último)
            if i < min(3, len(alerta_top4["jogos"])-1):
                draw.line([50, y_pos + altura_jogo - 5, largura-50, y_pos + altura_jogo - 5], 
                         fill=cor_principal, width=1)
            
            y_pos += altura_jogo
        
        # FOOTER
        footer_y = altura - 40
        draw.rectangle([0, footer_y, largura, altura], fill=cor_principal)
        
        footer_texto = "RESULTADO TOP 4 - ANÁLISE ESTATÍSTICA - TENDÊNCIAS DE APOSTAS - SISTEMA ELITE MASTER"
        bbox_footer = draw.textbbox((0, 0), footer_texto, font=fonte_pequena)
        largura_footer = bbox_footer[2] - bbox_footer[0]
        draw.text(((largura - largura_footer) // 2, footer_y + 12), footer_texto, 
                 fill=cor_texto, font=fonte_pequena)
        
        return img
        
    except Exception as e:
        print(f"Erro ao criar pôster top4 resultado: {e}")
        # Fallback simples
        img = Image.new('RGB', (600, 400), color='#0c0c0c')
        draw = ImageDraw.Draw(img)
        draw.text((300, 200), "Erro ao gerar pôster Resultado Top 4", fill='white', anchor="mm")
        return img

def salvar_alerta_top4(jogos_top4: list, data_str: str):
    """Salva um alerta Top 4 no arquivo de alertas"""
    alertas = carregar_alertas()
    
    # Gera um ID único para o alerta Top 4
    alerta_id = f"top4_{int(datetime.now().timestamp())}"
    
    # Prepara a estrutura do alerta Top 4
    alerta = {
        "tipo": "top4",
        "timestamp": datetime.now().isoformat(),
        "data_jogos": data_str,
        "jogos": [],
        "enviado_telegram": False,
        "conferido": False
    }
    
    for jogo_info in jogos_top4:
        jogo_data = {
            "jogo": jogo_info["jogo"],
            "predictions": jogo_info["predictions"],
            "resultado_total": None,
            "resultado_vencedor": None,
            "conferido": False
        }
        alerta["jogos"].append(jogo_data)
    
    alertas[alerta_id] = alerta
    salvar_alertas(alertas)
    return alerta_id

def carregar_alertas_top4():
    """Carrega apenas os alertas do tipo Top 4"""
    alertas = carregar_alertas()
    alertas_top4 = {}
    
    for alerta_id, alerta in alertas.items():
        if alerta.get("tipo") == "top4":
            alertas_top4[alerta_id] = alerta
    
    return alertas_top4

def atualizar_alerta_top4(alerta_id: str, alerta_atualizado: dict):
    """Atualiza um alerta Top 4 específico"""
    alertas = carregar_alertas()
    alertas[alerta_id] = alerta_atualizado
    salvar_alertas(alertas)

def enviar_alerta_top4_compacto(data_str: str, jogos_selecionados: list = None):
    """Envia alerta compacto com os 4 melhores jogos em um único pôster e salva o alerta"""
    top4_jogos = obter_top4_melhores_jogos(data_str)
    
    if not top4_jogos:
        # Envia pôster informando que não há jogos
        jogo_vazio = {
            "home_team": {"full_name": "Nenhum jogo"},
            "visitor_team": {"full_name": "encontrado hoje"},
            "date": data_str,
            "status": "NO_GAMES"
        }
        predictions_vazio = {
            "total": {"estimativa": 0, "confianca": 0, "tendencia": "Sem jogos"},
            "vencedor": {"vencedor": "N/A", "confianca": 0, "detalhe": ""}
        }
        
        jogos_fake = [{
            "jogo": jogo_vazio,
            "predictions": predictions_vazio,
            "home_team_name": "Nenhum jogo",
            "visitor_team_name": "encontrado"
        }]
        
        poster = criar_poster_top4_compacto(jogos_fake)
        enviar_poster_telegram(poster, TELEGRAM_CHAT_ID_ALT2)
        return
    
    # Se não foram especificados jogos selecionados, usa todos os 4
    if jogos_selecionados is None:
        jogos_selecionados = top4_jogos
    else:
        # Filtra apenas os jogos selecionados
        jogos_selecionados = [jogo for jogo in top4_jogos if jogo in jogos_selecionados]
    
    # Cria e envia o pôster compacto
    poster = criar_poster_top4_compacto(jogos_selecionados)
    
    if enviar_poster_telegram(poster, TELEGRAM_CHAT_ID_ALT2):
        # Salva o alerta Top 4
        salvar_alerta_top4(jogos_selecionados, data_str)
        st.success(f"✅ Pôster Top 4 compacto enviado com {len(jogos_selecionados)} jogos!")
        return True
    else:
        st.error("❌ Erro ao enviar pôster Top 4 compacto")
        return False

def conferir_alertas_top4():
    """Interface para conferência dos alertas Top 4"""
    st.header("✅ Conferência - Alertas Top 4")
    
    alertas_top4 = carregar_alertas_top4()
    
    if not alertas_top4:
        st.info("Nenhum alerta Top 4 pendente de conferência.")
        return
    
    for alerta_id, alerta in alertas_top4.items():
        st.subheader(f"Alerta Top 4 - {alerta.get('data_jogos', 'Data não especificada')}")
        
        # Verifica se a estrutura do alerta está correta
        if "jogos" not in alerta:
            st.error(f"Estrutura inválida do alerta {alerta_id}")
            continue
            
        # Exibe cada jogo do alerta
        for i, jogo_data in enumerate(alerta["jogos"]):
            if i >= 4:
                break
                
            jogo = jogo_data.get("jogo", {})
            predictions = jogo_data.get("predictions", {})
            
            home_team = jogo.get("home_team", {}).get("full_name", "Casa")
            away_team = jogo.get("visitor_team", {}).get("full_name", "Visitante")
            
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            
            with col1:
                st.write(f"**{away_team}** @ **{home_team}**")
            
            with col2:
                total_pred = predictions.get("total", {})
                st.write(f"**Total:** {total_pred.get('tendencia', 'N/A')}")
                
                # Seleção de resultado para Total
                resultado_total = jogo_data.get("resultado_total", None)
                options_total = ["🟢 GREEN", "🔴 RED", "⚪ PENDENTE"]
                index_total = 2
                if resultado_total == "Green":
                    index_total = 0
                elif resultado_total == "Red":
                    index_total = 1
                
                novo_resultado_total = st.radio(
                    "Resultado Total:",
                    options_total,
                    index=index_total,
                    key=f"total_{alerta_id}_{i}"
                )
                
                # Converte para Green/Red
                if novo_resultado_total == "🟢 GREEN":
                    jogo_data["resultado_total"] = "Green"
                elif novo_resultado_total == "🔴 RED":
                    jogo_data["resultado_total"] = "Red"
                else:
                    jogo_data["resultado_total"] = None
            
            with col3:
                vencedor_pred = predictions.get("vencedor", {})
                st.write(f"**Vencedor:** {vencedor_pred.get('vencedor', 'N/A')}")
                
                # Seleção de resultado para Vencedor
                resultado_vencedor = jogo_data.get("resultado_vencedor", None)
                options_vencedor = ["🟢 GREEN", "🔴 RED", "⚪ PENDENTE"]
                index_vencedor = 2
                if resultado_vencedor == "Green":
                    index_vencedor = 0
                elif resultado_vencedor == "Red":
                    index_vencedor = 1
                
                novo_resultado_vencedor = st.radio(
                    "Resultado Vencedor:",
                    options_vencedor,
                    index=index_vencedor,
                    key=f"vencedor_{alerta_id}_{i}"
                )
                
                # Converte para Green/Red
                if novo_resultado_vencedor == "🟢 GREEN":
                    jogo_data["resultado_vencedor"] = "Green"
                elif novo_resultado_vencedor == "🔴 RED":
                    jogo_data["resultado_vencedor"] = "Red"
                else:
                    jogo_data["resultado_vencedor"] = None
            
            with col4:
                # Marcar jogo como conferido
                jogo_conferido = jogo_data.get("conferido", False)
                if st.checkbox("Conferido", value=jogo_conferido, key=f"conferido_{alerta_id}_{i}"):
                    jogo_data["conferido"] = True
                else:
                    jogo_data["conferido"] = False
        
        # Botões de ação para o alerta inteiro
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("💾 Salvar Conferência", key=f"save_{alerta_id}"):
                # Atualiza o alerta
                atualizar_alerta_top4(alerta_id, alerta)
                st.success("Conferência salva!")
        
        with col_btn2:
            if st.button("🖼️ Visualizar Resultado", key=f"viz_{alerta_id}"):
                try:
                    poster = criar_poster_top4_resultado(alerta)
                    st.image(poster, caption="Pré-visualização do Resultado Top 4", use_column_width=True)
                except Exception as e:
                    st.error(f"Erro ao gerar pré-visualização: {e}")
        
        with col_btn3:
            # Verifica se todos os jogos estão conferidos
            todos_conferidos = all(jogo.get("conferido", False) for jogo in alerta["jogos"])
            if todos_conferidos:
                if st.button("📤 Enviar Resultado", key=f"send_{alerta_id}"):
                    # Envia o pôster de resultado
                    try:
                        poster = criar_poster_top4_resultado(alerta)
                        if enviar_poster_telegram(poster, TELEGRAM_CHAT_ID_ALT2):
                            # Marca o alerta como conferido e enviado
                            alerta["conferido"] = True
                            alerta["enviado_telegram"] = True
                            atualizar_alerta_top4(alerta_id, alerta)
                            st.success("Resultado enviado para o Telegram!")
                        else:
                            st.error("Erro ao enviar resultado.")
                    except Exception as e:
                        st.error(f"Erro ao enviar resultado: {e}")
            else:
                st.warning("Conferir todos os jogos antes de enviar.")
        
        st.markdown("---")

def exibir_interface_top4_compacto(data_str_api: str):
    """Exibe interface para seleção e envio do Top 4 compacto"""
    st.sidebar.subheader("🏆 TOP 4 - Alerta Compacto")
    
    # Busca os top 4 jogos
    top4_jogos = obter_top4_melhores_jogos(data_str_api)
    
    if not top4_jogos:
        st.sidebar.warning("Nenhum jogo encontrado para análise.")
        return
    
    st.sidebar.write("**Selecione os jogos para o alerta:**")
    
    # Checkboxes para seleção individual
    jogos_selecionados = []
    for i, jogo_info in enumerate(top4_jogos):
        home_team = jogo_info["home_team_name"]
        visitor_team = jogo_info["visitor_team_name"]
        
        # Calcula pontuação para exibição
        pontuacao = jogo_info.get("pontuacao", 0)
        
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            if st.sidebar.checkbox(
                f"{visitor_team} @ {home_team}", 
                value=True,
                key=f"top4_{i}"
            ):
                jogos_selecionados.append(jogo_info)
        
        with col2:
            st.sidebar.write(f"`{pontuacao:.1f}`")
    
    # Botões de ação
    col_btn1, col_btn2 = st.sidebar.columns(2)
    
    with col_btn1:
        if st.button("🖼️ Visualizar Pôster", key="viz_top4", use_container_width=True):
            if jogos_selecionados:
                poster = criar_poster_top4_compacto(jogos_selecionados)
                st.image(poster, caption="Pré-visualização do Pôster Top 4", use_column_width=True)
                
                # Opção para baixar
                buf = io.BytesIO()
                poster.save(buf, format='PNG')
                st.download_button(
                    "📥 Baixar Pôster",
                    buf.getvalue(),
                    f"top4_compacto_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "image/png"
                )
            else:
                st.warning("Selecione pelo menos um jogo.")
    
    with col_btn2:
        if st.button("🚀 Enviar Alerta", type="primary", key="env_top4", use_container_width=True):
            if jogos_selecionados:
                with st.spinner("Enviando alerta compacto..."):
                    if enviar_alerta_top4_compacto(data_str_api, jogos_selecionados):
                        st.success("Alerta Top 4 enviado com sucesso!")
                    else:
                        st.error("Erro ao enviar alerta.")
            else:
                st.warning("Selecione pelo menos um jogo.")
    
    # Exibe detalhes dos jogos selecionados
    if jogos_selecionados:
        st.sidebar.markdown("---")
        st.sidebar.write(f"**📋 {len(jogos_selecionados)} jogos selecionados:**")
        
        for jogo_info in jogos_selecionados:
            home_team = jogo_info["home_team_name"]
            visitor_team = jogo_info["visitor_team_name"]
            predictions = jogo_info["predictions"]
            
            total_pred = predictions.get("total", {})
            vencedor_pred = predictions.get("vencedor", {})
            
            st.sidebar.write(f"• **{visitor_team}** @ **{home_team}**")
            st.sidebar.write(f"  📊 {total_pred.get('tendencia', 'N/A')}")
            st.sidebar.write(f"  🏆 {vencedor_pred.get('vencedor', 'N/A')}")
            st.sidebar.write("")

# =============================
# EXIBIÇÃO DOS JOGOS ANALISADOS
# =============================
def exibir_jogos_analisados():
    st.header("📈 Jogos Analisados")
    
    alertas = carregar_alertas()
    if not alertas:
        st.info("Nenhum jogo analisado ainda.")
        return
    
    alertas_ordenados = sorted(
        alertas.items(), 
        key=lambda x: x[1].get("timestamp", ""), 
        reverse=True
    )
    
    st.subheader(f"🎯 {len(alertas_ordenados)} Jogos Analisados")
    
    for alerta_id, alerta in alertas_ordenados:
        game_data = alerta.get("game_data", {})
        predictions = alerta.get("predictions", {})
        
        home_team = game_data.get("home_team", {}).get("full_name", "Casa")
        away_team = game_data.get("visitor_team", {}).get("full_name", "Visitante")
        status = game_data.get("status", "SCHEDULED")
        
        total_pred = predictions.get("total", {})
        vencedor_pred = predictions.get("vencedor", {})
        
        # Card do jogo com escudos
        with st.expander(f"🏀 {home_team} vs {away_team} - {status}", expanded=False):
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                exibir_escudo_time(home_team, (80, 80))
            
            with col2:
                st.write("**📊 Total de Pontos**")
                st.write(f"Tendência: {total_pred.get('tendencia', 'N/A')}")
                st.write(f"Estimativa: {total_pred.get('estimativa', 0):.1f}")
                st.write(f"Confiança: {total_pred.get('confianca', 0):.0f}%")
                
                st.write("**🎯 Vencedor**")
                st.write(f"Previsão: {vencedor_pred.get('vencedor', 'N/A')}")
                st.write(f"Confiança: {vencedor_pred.get('confianca', 0):.0f}%")
                st.write(f"Detalhe: {vencedor_pred.get('detalhe', '')}")
            
            with col3:
                exibir_escudo_time(away_team, (80, 80))
            
            if alerta.get("poster_enviado", False):
                st.success("🖼️ Pôster enviado para Telegram")
            else:
                st.info("💾 Salvo localmente")
            
            timestamp = alerta.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    st.caption(f"Analisado em: {dt.strftime('%d/%m/%Y %H:%M')}")
                except:
                    pass

# =============================
# CONFERÊNCIA DE RESULTADOS
# =============================
def conferir_resultados():
    st.header("📊 Conferência de Resultados")
    
    # Botões de ação para conferência
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        st.subheader("Jogos Finalizados")
    
    with col2:
        if st.button("🔄 Atualizar Resultados", type="primary", use_container_width=True):
            with st.spinner("Atualizando resultados das partidas..."):
                jogos_atualizados = atualizar_resultados_partidas()
                if jogos_atualizados > 0:
                    st.success(f"✅ {jogos_atualizados} jogos atualizados!")
                    st.rerun()
    
    with col3:
        if st.button("✅ Conferir Jogos", type="secondary", use_container_width=True):
            with st.spinner("Conferindo jogos finalizados..."):
                jogos_conferidos = conferir_jogos_finalizados()
                if jogos_conferidos > 0:
                    st.success(f"✅ {jogos_conferidos} jogos conferidos!")
                    st.rerun()
                else:
                    st.info("ℹ️ Nenhum jogo novo para conferir.")
    
    with col4:
        if st.button("📤 Enviar Pôsteres", type="secondary", use_container_width=True):
            with st.spinner("Enviando pôsteres de resultados..."):
                jogos_alertados = enviar_alerta_resultados_conferidos()
                if jogos_alertados > 0:
                    st.success(f"✅ {jogos_alertados} pôsteres enviados!")
                else:
                    st.info("ℹ️ Nenhum jogo novo para alerta.")
    
    alertas = carregar_alertas()
    if not alertas:
        st.info("Nenhum alerta salvo para conferência.")
        return
    
    jogos_para_conferir = []
    for alerta_id, alerta in alertas.items():
        game_data = alerta.get("game_data", {})
        status = game_data.get("status", "").upper()
        
        if status in ["FINAL", "FINAL/OT"]:
            jogos_para_conferir.append((alerta_id, alerta))
    
    if not jogos_para_conferir:
        st.info("Nenhum jogo finalizado para conferência.")
        return
    
    st.subheader(f"🎯 {len(jogos_para_conferir)} Jogos Finalizados")
    
    for alerta_id, alerta in jogos_para_conferir:
        game_data = alerta.get("game_data", {})
        predictions = alerta.get("predictions", {})
        
        home_team = game_data.get("home_team", {}).get("full_name", "Casa")
        away_team = game_data.get("visitor_team", {}).get("full_name", "Visitante")
        home_score = game_data.get("home_team_score", 0)
        away_score = game_data.get("visitor_team_score", 0)
        status = game_data.get("status", "")
        
        total_pontos = home_score + away_score
        
        # Determina resultado do Total
        total_pred = predictions.get("total", {})
        tendencia_total = total_pred.get("tendencia", "")
        resultado_total = "⏳ Aguardando"
        
        if "Mais" in tendencia_total:
            try:
                limite = float(tendencia_total.split()[-1])
                resultado_total = "🟢 GREEN" if total_pontos > limite else "🔴 RED"
            except:
                resultado_total = "⚪ INDEFINIDO"
        elif "Menos" in tendencia_total:
            try:
                limite = float(tendencia_total.split()[-1])
                resultado_total = "🟢 GREEN" if total_pontos < limite else "🔴 RED"
            except:
                resultado_total = "⚪ INDEFINIDO"
        
        # Determina resultado do Vencedor
        vencedor_pred = predictions.get("vencedor", {})
        vencedor_previsto = vencedor_pred.get("vencedor", "")
        resultado_vencedor = "⏳ Aguardando"
        
        if vencedor_previsto == "Casa" and home_score > away_score:
            resultado_vencedor = "🟢 GREEN"
        elif vencedor_previsto == "Visitante" and away_score > home_score:
            resultado_vencedor = "🟢 GREEN"
        elif vencedor_previsto == "Empate" and home_score == away_score:
            resultado_vencedor = "🟢 GREEN"
        elif vencedor_previsto in ["Casa", "Visitante", "Empate"]:
            resultado_vencedor = "🔴 RED"
        else:
            resultado_vencedor = "⚪ INDEFINIDO"
        
        # Exibe card do jogo com escudos
        col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
        
        with col1:
            exibir_escudo_time(home_team, (60, 60))
        
        with col2:
            st.write(f"**{home_team}** vs **{away_team}**")
            st.write(f"📊 **Placar:** {home_score} x {away_score}")
            st.write(f"🏀 **Total:** {total_pontos} pontos")
            st.write(f"**Status:** {status}")
        
        with col3:
            st.write(f"**Total:** {tendencia_total}")
            st.write(f"**Resultado:** {resultado_total}")
            st.write(f"**Vencedor:** {resultado_vencedor}")
        
        with col4:
            exibir_escudo_time(away_team, (60, 60))
        
        # Botões de ação
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if not alerta.get("conferido", False):
                if st.button("✅ Confirmar", key=f"conf_{alerta_id}", use_container_width=True):
                    # Atualiza estatísticas quando confirma
                    if resultado_total in ["🟢 GREEN", "🔴 RED"] and resultado_vencedor in ["🟢 GREEN", "🔴 RED"]:
                        atualizar_estatisticas(resultado_total, resultado_vencedor)
                    
                    alertas[alerta_id]["conferido"] = True
                    
                    # Envia pôster individual
                    if enviar_alerta_resultado_individual(alerta_id, alertas[alerta_id]):
                        st.success("✅ Conferido e pôster enviado!")
                    else:
                        st.error("✅ Conferido, mas erro no pôster.")
                    
                    salvar_alertas(alertas)
                    st.rerun()
            else:
                st.success("✅ Conferido")
        
        with col_btn2:
            if alerta.get("conferido", False):
                if st.button("🖼️ Reenviar Pôster", key=f"poster_{alerta_id}", use_container_width=True):
                    if enviar_alerta_resultado_individual(alerta_id, alerta):
                        st.success("✅ Pôster reenviado!")
                    else:
                        st.error("❌ Erro ao reenviar pôster.")
        
        st.markdown("---")

# =============================
# TESTE DO SISTEMA DE PÔSTERES
# =============================

def testar_sistema_posteres():
    """Função para testar a geração de pôsteres"""
    st.header("🎨 Teste do Sistema de Pôsteres")
    
    # Cria um exemplo de jogo e previsões
    jogo_exemplo = {
        "id": 1,
        "home_team": {"full_name": "Los Angeles Lakers"},
        "visitor_team": {"full_name": "Golden State Warriors"},
        "date": "2024-12-25T20:00:00Z",
        "status": "SCHEDULED"
    }
    
    predictions_exemplo = {
        "total": {
            "estimativa": 228.5,
            "confianca": 72.5,
            "tendencia": "Mais 225.5"
        },
        "vencedor": {
            "vencedor": "Casa",
            "confianca": 68.0,
            "detalhe": "Ligeira vantagem da casa"
        }
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🖼️ Gerar Pôster de Previsão"):
            poster = criar_poster_alerta(jogo_exemplo, predictions_exemplo, "previsao")
            st.image(poster, caption="Pôster de Previsão", use_column_width=True)
            
            # Opção para baixar
            buf = io.BytesIO()
            poster.save(buf, format='PNG')
            st.download_button(
                "📥 Baixar Pôster",
                buf.getvalue(),
                "poster_previsao.png",
                "image/png"
            )
    
    with col2:
        # Exemplo com resultado
        jogo_resultado = jogo_exemplo.copy()
        jogo_resultado["home_team_score"] = 115
        jogo_resultado["visitor_team_score"] = 108
        jogo_resultado["status"] = "FINAL"
        
        if st.button("📊 Gerar Pôster de Resultado"):
            poster = criar_poster_alerta(jogo_resultado, predictions_exemplo, "resultado")
            st.image(poster, caption="Pôster de Resultado", use_column_width=True)
            
            buf = io.BytesIO()
            poster.save(buf, format='PNG')
            st.download_button(
                "📥 Baixar Pôster",
                buf.getvalue(),
                "poster_resultado.png",
                "image/png"
            )
    
    # Teste de envio para Telegram
    st.subheader("📤 Teste de Envio para Telegram")
    
    if st.button("🚀 Enviar Pôster de Teste para Telegram"):
        with st.spinner("Enviando pôster..."):
            poster = criar_poster_alerta(jogo_exemplo, predictions_exemplo, "previsao")
            if enviar_poster_telegram(poster, TELEGRAM_CHAT_ID_ALT2):
                st.success("✅ Pôster enviado com sucesso!")
            else:
                st.error("❌ Erro ao enviar pôster")

# =============================
# INTERFACE STREAMLIT PRINCIPAL
# =============================

def main():
    st.set_page_config(
        page_title="🏀 NBA Elite AI - Sistema de Previsões",
        page_icon="🏀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # CSS customizado
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1e3a8a;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .prediction-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .team-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1e3a8a;
        margin: 0.5rem 0;
    }
    .green-alert {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .red-alert {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">🏀 NBA Elite AI - Sistema de Previsões</h1>', unsafe_allow_html=True)
    
    # Sidebar melhorada
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📅 Data dos Jogos")
        data_jogos = st.date_input(
            "Selecione a data:",
            value=date.today(),
            max_value=date.today() + timedelta(days=7)
        )
        
        # CONVERSÃO CORRETA DA DATA PARA A API
        data_str_api = obter_data_correta_para_api(data_jogos)
        
        st.subheader("🔧 Parâmetros")
        janela_jogos = st.slider(
            "Janela de jogos para análise:",
            min_value=5,
            max_value=30,
            value=15,
            help="Quantidade de jogos anteriores considerados para as estatísticas"
        )
        
        limite_confianca = st.slider(
            "Limite mínimo de confiança (%):",
            min_value=40,
            max_value=80,
            value=60,
            help="Confiança mínima para considerar uma previsão válida"
        )
        
        st.subheader("⭐ Top 4 Jogos")
        
        # NOVA SEÇÃO TOP 4 COMPACTO
        exibir_interface_top4_compacto(data_str_api)
        
        # Botão rápido para enviar todos os 4 jogos
        if st.sidebar.button("🚀 Enviar Top 4 Completo", type="secondary", use_container_width=True):
            with st.spinner("Enviando Top 4 completo..."):
                top4_jogos = obter_top4_melhores_jogos(data_str_api)
                if top4_jogos:
                    if enviar_alerta_top4_compacto(data_str_api, top4_jogos):
                        st.sidebar.success("Top 4 completo enviado!")
                    else:
                        st.sidebar.error("Erro ao enviar Top 4.")
                else:
                    st.sidebar.warning("Nenhum jogo encontrado.")
        
        st.subheader("🔄 Atualizações")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Atualizar Dados", use_container_width=True):
                with st.spinner("Atualizando dados dos jogos..."):
                    atualizar_resultados_partidas()
        
        with col2:
            if st.button("✅ Conferir Jogos", use_container_width=True):
                with st.spinner("Conferindo jogos finalizados..."):
                    conferir_jogos_finalizados()
        
        st.subheader("📤 Alertas")
        if st.button("📤 Enviar Pôsteres Resultados", use_container_width=True):
            with st.spinner("Enviando pôsteres de resultados conferidos..."):
                jogos_alertados = enviar_alerta_resultados_conferidos()
                if jogos_alertados > 0:
                    st.success(f"✅ {jogos_alertados} pôsteres enviados!")
                else:
                    st.info("ℹ️ Nenhum jogo novo para alerta.")
        
        st.subheader("📊 Estatísticas")
        if st.button("🧹 Limpar Estatísticas", use_container_width=True):
            limpar_estatisticas()
            st.success("Estatísticas limpas!")
            st.rerun()
        
        st.subheader("🎨 Testes")
        if st.button("🖼️ Testar Pôsteres", use_container_width=True):
            st.session_state.show_testes = True
        
        st.subheader("🧹 Limpeza")
        if st.button("🗑️ Limpar Cache", type="secondary", use_container_width=True):
            for f in [CACHE_GAMES, CACHE_STATS, ALERTAS_PATH]:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        st.success(f"🗑️ {f} removido")
                except:
                    pass
            st.rerun()

    # Abas principais - ATUALIZADO com nova aba
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎯 Análise do Dia", 
        "📈 Jogos Analisados", 
        "✅ Conferência",
        "📊 Estatísticas",
        "🎨 Testes Pôsteres",
        "🏆 Conferir Top 4"
    ])
    
    with tab1:
        exibir_aba_analise_melhorada(data_jogos, data_str_api, janela_jogos, limite_confianca)
    
    with tab2:
        exibir_jogos_analisados()
    
    with tab3:
        conferir_resultados()
    
    with tab4:
        exibir_estatisticas()
    
    with tab5:
        testar_sistema_posteres()
    
    with tab6:
        conferir_alertas_top4()

def exibir_aba_analise_melhorada(data_sel: date, data_str_api: str, janela: int, limite_confianca: int):
    """Exibe análise dos jogos com interface melhorada"""
    st.header(f"🎯 Análise com Dados Reais 2024-2025 - {data_sel.strftime('%d/%m/%Y')}")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        top_n = st.slider("Número de jogos para analisar", 1, 15, 5)
    with col2:
        st.write("")
        st.write("")
        enviar_auto = st.checkbox("Enviar pôsteres automaticamente", value=True)
    with col3:
        st.write("")
        st.write("")
        if st.button("🚀 ANALISAR JOGOS", type="primary", use_container_width=True):
            analisar_jogos_com_dados_2025_melhorado(data_sel, data_str_api, top_n, janela, enviar_auto, limite_confianca)

def analisar_jogos_com_dados_2025_melhorado(data_sel: date, data_str_api: str, top_n: int, janela: int, enviar_auto: bool, limite_confianca: int):
    """Versão melhorada da análise com interface do primeiro código"""
    progress_placeholder = st.empty()
    results_placeholder = st.empty()
    
    with progress_placeholder:
        st.info(f"🔍 Buscando dados reais para {data_sel.strftime('%d/%m/%Y')}...")
        st.success("📊 Analisando com dados da temporada 2024-2025")
        if enviar_auto:
            st.warning("🖼️ Pôsteres serão enviados para Telegram")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Busca jogos com data corrigida
    jogos = obter_jogos_data(data_str_api)
    
    if not jogos:
        st.error("❌ Nenhum jogo encontrado para esta data")
        return
    
    jogos = jogos[:top_n]
    
    status_text.text(f"📊 Analisando {len(jogos)} jogos com dados 2024-2025...")
    
    resultados = []
    alertas_enviados = 0
    
    with results_placeholder:
        st.subheader(f"🎯 Análise com Dados Reais 2024-2025")
        
        for i, jogo in enumerate(jogos):
            progress = (i + 1) / len(jogos)
            progress_bar.progress(progress)
            
            home_team = jogo['home_team']['full_name']
            away_team = jogo['visitor_team']['full_name']
            status_text.text(f"🔍 Analisando: {home_team} vs {away_team} ({i+1}/{len(jogos)})")
            
            home_id = jogo["home_team"]["id"]
            away_id = jogo["visitor_team"]["id"]
            
            try:
                # Previsões com dados reais 2024-2025
                total_estim, total_conf, total_tend = prever_total_points(home_id, away_id, janela)
                vencedor, vencedor_conf, vencedor_detalhe = prever_vencedor(home_id, away_id, janela)
                
                predictions = {
                    "total": {
                        "estimativa": total_estim, 
                        "confianca": total_conf, 
                        "tendencia": total_tend
                    },
                    "vencedor": {
                        "vencedor": vencedor,
                        "confianca": vencedor_conf,
                        "detalhe": vencedor_detalhe
                    }
                }
                
                # Verifica se atende ao limite de confiança
                alertas_ativos = []
                if total_conf >= limite_confianca:
                    alertas_ativos.append(f"🎯 **Total de Pontos**: {total_tend} (Conf: {total_conf}%)")
                
                if vencedor_conf >= limite_confianca:
                    alertas_ativos.append(f"🏆 **Vencedor**: {vencedor} (Conf: {vencedor_conf}%)")
                
                # Envia pôster se houver alertas ativos
                enviado = False
                if alertas_ativos and enviar_auto:
                    enviado = verificar_e_enviar_alerta(jogo, predictions, True)
                    if enviado:
                        alertas_enviados += 1
                elif alertas_ativos:
                    enviado = verificar_e_enviar_alerta(jogo, predictions, False)
                
                # Exibe resultado com interface melhorada
                st.markdown("---")
                
                # Header do jogo com escudos
                col1, col2, col3 = st.columns([2, 1, 2])
                
                with col1:
                    st.subheader(home_team)
                    exibir_escudo_time(home_team, (100, 100))
                    
                    # Estatísticas do time da casa
                    home_stats = obter_estatisticas_time_2025(home_id, janela)
                    st.caption(f"Win Rate: {home_stats['win_rate']:.1%}")
                    st.caption(f"PPG: {home_stats['pts_for_avg']:.1f}")
                    st.caption(f"Últimos {home_stats['games']} jogos")
                
                with col2:
                    st.markdown("<h2 style='text-align: center;'>VS</h2>", unsafe_allow_html=True)
                    
                    # Status e horário
                    status = jogo.get("status", "Agendado")
                    st.write(f"**Status:** {status}")
                    
                    hora_jogo = jogo.get("date", "")
                    if hora_jogo:
                        data_str, hora_str = formatar_data_api_para_local(hora_jogo)
                        st.write(f"**Horário:** {hora_str}")
                
                with col3:
                    st.subheader(away_team)
                    exibir_escudo_time(away_team, (100, 100))
                    
                    # Estatísticas do time visitante
                    away_stats = obter_estatisticas_time_2025(away_id, janela)
                    st.caption(f"Win Rate: {away_stats['win_rate']:.1%}")
                    st.caption(f"PPG: {away_stats['pts_for_avg']:.1f}")
                    st.caption(f"Últimos {away_stats['games']} jogos")
                
                # Previsões em cards
                col_pred1, col_pred2 = st.columns(2)
                
                with col_pred1:
                    st.markdown(f"""
                    <div class="prediction-card">
                        <h3>📊 Total de Pontos</h3>
                        <p><strong>Estimativa:</strong> {total_estim} pontos</p>
                        <p><strong>Confiança:</strong> {total_conf}%</p>
                        <p><strong>Tendência:</strong> {total_tend}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_pred2:
                    st.markdown(f"""
                    <div class="prediction-card">
                        <h3>🏆 Vencedor</h3>
                        <p><strong>Previsão:</strong> {vencedor}</p>
                        <p><strong>Confiança:</strong> {vencedor_conf}%</p>
                        <p><strong>Detalhe:</strong> {vencedor_detalhe}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Alertas baseados na confiança
                if alertas_ativos:
                    st.markdown("<div class='green-alert'>", unsafe_allow_html=True)
                    st.subheader("🚨 Alertas Ativos")
                    
                    for alerta in alertas_ativos:
                        st.write(f"✅ {alerta}")
                    
                    if not enviado:
                        col_salvar, col_telegram = st.columns(2)
                        
                        with col_salvar:
                            if st.button("💾 Salvar Alerta", key=f"save_{jogo['id']}"):
                                verificar_e_enviar_alerta(jogo, predictions, False)
                                st.success("Alerta salvo com sucesso!")
                        
                        with col_telegram:
                            if st.button("🖼️ Enviar Pôster", key=f"tg_{jogo['id']}"):
                                if verificar_e_enviar_alerta(jogo, predictions, True):
                                    st.success("Pôster enviado para Telegram!")
                                else:
                                    st.error("Erro ao enviar pôster")
                    else:
                        st.success("🖼️ Pôster enviado para Telegram")
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='red-alert'>", unsafe_allow_html=True)
                    st.write("🔍 **Confiança insuficiente** para gerar alertas")
                    st.write(f"Limite requerido: {limite_confianca}%")
                    st.write(f"Total: {total_conf}% | Vencedor: {vencedor_conf}%")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                resultados.append({
                    "jogo": jogo,
                    "predictions": predictions
                })
                
            except Exception as e:
                st.error(f"❌ Erro ao analisar {home_team} vs {away_team}: {e}")
                continue
    
    progress_placeholder.empty()
    
    # Resumo final
    st.success(f"✅ Análise com dados 2024-2025 concluída!")
    st.info(f"""
    **📊 Resumo da Análise:**
    - 🏀 {len(resultados)} jogos analisados com dados 2024-2025
    - 🖼️ {alertas_enviados} pôsteres enviados para Telegram
    - 📈 Estatísticas baseadas na temporada atual
    - 💾 Dados salvos para conferência futura
    """)

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if __name__ == "__main__":
    main()
