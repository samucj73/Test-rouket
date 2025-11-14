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
import base64
from io import BytesIO

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
ESCUDOS_CACHE_PATH = "escudos_cache.json"
CACHE_TIMEOUT = 86400  # 24h

HEADERS_BDL = {"Authorization": BALLDONTLIE_API_KEY}

# Rate limiting
REQUEST_TIMEOUT = 10
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 1.2

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

def carregar_cache_escudos():
    """Carrega o cache de escudos convertidos"""
    return carregar_json(ESCUDOS_CACHE_PATH) or {}

def salvar_cache_escudos(dados):
    """Salva o cache de escudos"""
    salvar_json(ESCUDOS_CACHE_PATH, dados)

# =============================
# SISTEMA DE CONVERSÃO SVG PARA PNG
# =============================
def obter_url_escudo_time(nome_time):
    """Obtém a URL do escudo do time da NBA"""
    time_abbreviations = {
        "Los Angeles Lakers": "LAL",
        "Golden State Warriors": "GSW", 
        "Boston Celtics": "BOS",
        "Chicago Bulls": "CHI",
        "Miami Heat": "MIA",
        "Philadelphia 76ers": "PHI",
        "Milwaukee Bucks": "MIL",
        "Denver Nuggets": "DEN",
        "Phoenix Suns": "PHX",
        "Dallas Mavericks": "DAL",
        "Brooklyn Nets": "BKN",
        "New York Knicks": "NYK",
        "Atlanta Hawks": "ATL",
        "Toronto Raptors": "TOR",
        "Utah Jazz": "UTA",
        "Portland Trail Blazers": "POR",
        "Memphis Grizzlies": "MEM",
        "New Orleans Pelicans": "NOP",
        "San Antonio Spurs": "SAS",
        "Houston Rockets": "HOU",
        "Oklahoma City Thunder": "OKC",
        "Sacramento Kings": "SAC",
        "Minnesota Timberwolves": "MIN",
        "Los Angeles Clippers": "LAC",
        "Charlotte Hornets": "CHA",
        "Detroit Pistons": "DET",
        "Orlando Magic": "ORL",
        "Indiana Pacers": "IND",
        "Cleveland Cavaliers": "CLE",
        "Washington Wizards": "WAS"
    }
    
    abbr = time_abbreviations.get(nome_time)
    if abbr:
        # URL dos escudos da NBA (formato SVG)
        return f"https://cdn.nba.com/logos/nba/{abbr}/primary/L/logo.svg"
    
    return None

def converter_svg_para_png(svg_url, width=80, height=80):
    """Converte SVG para PNG em base64 para exibição no Streamlit"""
    try:
        # Baixa o SVG
        response = requests.get(svg_url, timeout=10)
        if response.status_code != 200:
            return None
            
        svg_content = response.content
        
        # Tenta usar cairosvg se disponível, senão usa fallback
        try:
            import cairosvg
            png_data = cairosvg.svg2png(
                bytestring=svg_content,
                output_width=width,
                output_height=height
            )
        except ImportError:
            # Fallback: usa emoji se cairosvg não estiver disponível
            st.warning("📦 Instale: pip install cairosvg para escudos reais")
            return None
        
        # Converte para base64 para exibição no HTML
        png_base64 = base64.b64encode(png_data).decode('utf-8')
        return f"data:image/png;base64,{png_base64}"
        
    except Exception as e:
        print(f"Erro ao converter SVG: {e}")
        return None

def obter_escudo_com_cache(nome_time, width=100, height=100):
    """Obtém escudo com cache para melhor performance"""
    cache = carregar_cache_escudos()
    cache_key = f"{nome_time}_{width}x{height}"
    
    if cache_key in cache:
        return cache[cache_key]
    
    # Se não está em cache, converte e salva
    escudo_url = obter_url_escudo_time(nome_time)
    if escudo_url:
        escudo_base64 = converter_svg_para_png(escudo_url, width, height)
        if escudo_base64:
            cache[cache_key] = escudo_base64
            salvar_cache_escudos(cache)
        return escudo_base64
    
    return None

# =============================
# SISTEMA DE ALERTAS POSTER
# =============================
def criar_alerta_poster(game_data, predictions, resultado_total=None, resultado_vencedor=None, resultado_quarto=None):
    """Cria um alerta no estilo Poster com design profissional"""
    
    home_team = game_data.get("home_team", {}).get("full_name", "Casa")
    away_team = game_data.get("visitor_team", {}).get("full_name", "Visitante")
    status = game_data.get("status", "SCHEDULED")
    
    home_score = game_data.get("home_team_score")
    away_score = game_data.get("visitor_team_score")
    
    total_pred = predictions.get("total", {})
    vencedor_pred = predictions.get("vencedor", {})
    primeiro_quarto_pred = predictions.get("primeiro_quarto", {})
    
    # Obtém escudos convertidos para PNG
    escudo_home = obter_escudo_com_cache(home_team, 100, 100)
    escudo_away = obter_escudo_com_cache(away_team, 100, 100)
    
    # Define cores baseadas no status
    if status in ["FINAL", "FINAL/OT"]:
        if resultado_total == "🟢 GREEN" or resultado_vencedor == "🟢 GREEN":
            border_color = "#28a745"  # Verde para GREEN
            bg_color = "#d4edda"
            status_color = "🟢"
            status_text = "GREEN"
        elif resultado_total == "🔴 RED" or resultado_vencedor == "🔴 RED":
            border_color = "#dc3545"  # Vermelho para RED
            bg_color = "#f8d7da"
            status_color = "🔴"
            status_text = "RED"
        else:
            border_color = "#6c757d"  # Cinza para finalizado sem resultado
            bg_color = "#e9ecef"
            status_color = "⚫"
            status_text = "FINALIZADO"
    else:
        border_color = "#ffc107"  # Amarelo para agendados
        bg_color = "#fff3cd"
        status_color = "⏰"
        status_text = "AGENDADO"
    
    # Card principal estilo Poster
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {bg_color}, #ffffff); 
                padding: 25px; 
                border-radius: 20px; 
                border-left: 10px solid {border_color};
                box-shadow: 0 6px 20px rgba(0,0,0,0.15);
                margin: 20px 0;
                font-family: 'Arial', sans-serif;">
        
        <!-- Cabeçalho do Poster -->
        <div style="text-align: center; margin-bottom: 25px; border-bottom: 2px solid #dee2e6; padding-bottom: 15px;">
            <h2 style="margin: 0; color: #2c3e50; font-size: 28px; font-weight: bold;">🏀 ALERTA NBA ELITE MASTER</h2>
            <p style="margin: 8px 0; color: #7f8c8d; font-size: 16px; font-weight: 500;">Análise com Dados Reais 2024-2025 | {status_color} {status_text}</p>
        </div>
        
        <!-- Confronto dos Times com Escudos PNG -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <!-- Time Visitante -->
            <div style="text-align: center; flex: 1;">
                <div style="height: 100px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px;">
                    {'<img src="' + escudo_away + '" style="max-height: 80px; max-width: 80px;" alt="' + away_team + '">' if escudo_away else '<div style="font-size: 48px; color: #7f8c8d;">🏀</div>'}
                </div>
                <h3 style="margin: 0; color: #2c3e50; font-size: 18px; font-weight: bold;">{away_team}</h3>
                {f'<div style="font-size: 24px; font-weight: bold; color: #e74c3c; margin-top: 8px;">{away_score}</div>' if away_score is not None else ''}
            </div>
            
            <!-- VS e Placar -->
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 36px; font-weight: bold; color: #34495e; margin: 15px 0;">VS</div>
                {f'<div style="font-size: 32px; font-weight: bold; color: #2c3e50; background: rgba(52, 152, 219, 0.1); padding: 10px 20px; border-radius: 10px; display: inline-block;">{away_score or "?"} - {home_score or "?"}</div>' if home_score is not None or away_score is not None else ''}
            </div>
            
            <!-- Time da Casa -->
            <div style="text-align: center; flex: 1;">
                <div style="height: 100px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px;">
                    {'<img src="' + escudo_home + '" style="max-height: 80px; max-width: 80px;" alt="' + home_team + '">' if escudo_home else '<div style="font-size: 48px; color: #7f8c8d;">🏀</div>'}
                </div>
                <h3 style="margin: 0; color: #2c3e50; font-size: 18px; font-weight: bold;">{home_team}</h3>
                {f'<div style="font-size: 24px; font-weight: bold; color: #e74c3c; margin-top: 8px;">{home_score}</div>' if home_score is not None else ''}
            </div>
        </div>
        
        <!-- Previsões -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 25px;">
            
            <!-- Total de Pontos -->
            <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 12px 0; color: #2c3e50; font-size: 16px; font-weight: bold;">📊 TOTAL PONTOS</h4>
                <div style="font-size: 18px; font-weight: bold; color: #3498db; margin-bottom: 8px;">{total_pred.get('tendencia', 'N/A')}</div>
                <div style="font-size: 14px; color: #7f8c8d;">Est: {total_pred.get('estimativa', 0):.1f}</div>
                <div style="font-size: 14px; color: #7f8c8d;">Conf: {total_pred.get('confianca', 0):.0f}%</div>
                {f'<div style="margin-top: 8px; font-size: 16px; font-weight: bold; color: {"#27ae60" if resultado_total == "🟢 GREEN" else "#e74c3c"};">{resultado_total}</div>' if resultado_total else ''}
            </div>
            
            <!-- Vencedor -->
            <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 12px 0; color: #2c3e50; font-size: 16px; font-weight: bold;">🎯 VENCEDOR</h4>
                <div style="font-size: 18px; font-weight: bold; color: #e67e22; margin-bottom: 8px;">{vencedor_pred.get('vencedor', 'N/A')}</div>
                <div style="font-size: 14px; color: #7f8c8d;">Conf: {vencedor_pred.get('confianca', 0):.0f}%</div>
                <div style="font-size: 12px; color: #95a5a6; margin-top: 5px;">{vencedor_pred.get('detalhe', '')[:25]}...</div>
                {f'<div style="margin-top: 8px; font-size: 16px; font-weight: bold; color: {"#27ae60" if resultado_vencedor == "🟢 GREEN" else "#e74c3c"};">{resultado_vencedor}</div>' if resultado_vencedor else ''}
            </div>
            
            <!-- 1º Quarto -->
            <div style="background: rgba(255,255,255,0.9); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 12px 0; color: #2c3e50; font-size: 16px; font-weight: bold;">⏱️ 1º QUARTO</h4>
                <div style="font-size: 18px; font-weight: bold; color: #9b59b6; margin-bottom: 8px;">{primeiro_quarto_pred.get('tendencia', 'N/A')}</div>
                <div style="font-size: 14px; color: #7f8c8d;">Est: {primeiro_quarto_pred.get('estimativa', 0):.1f}</div>
                <div style="font-size: 14px; color: #7f8c8d;">Conf: {primeiro_quarto_pred.get('confianca', 0):.0f}%</div>
                {f'<div style="margin-top: 8px; font-size: 16px; font-weight: bold; color: {"#27ae60" if resultado_quarto == "🟢 GREEN" else "#e74c3c"};">{resultado_quarto}</div>' if resultado_quarto else ''}
            </div>
        </div>
        
        <!-- Rodapé -->
        <div style="text-align: center; border-top: 1px solid #dee2e6; padding-top: 15px;">
            <p style="margin: 0; color: #7f8c8d; font-size: 12px;">
                🏆 Elite Master | 📅 {datetime.now().strftime("%d/%m/%Y %H:%M")} | 🔄 Dados em Tempo Real
            </p>
        </div>
        
    </div>
    """, unsafe_allow_html=True)

def limpar_cache_escudos():
    """Limpa o cache de escudos"""
    try:
        if os.path.exists(ESCUDOS_CACHE_PATH):
            os.remove(ESCUDOS_CACHE_PATH)
            st.success("✅ Cache de escudos limpo!")
        else:
            st.info("ℹ️ Nenhum cache de escudos encontrado.")
    except Exception as e:
        st.error(f"❌ Erro ao limpar cache: {e}")

# =============================
# SISTEMA DE ESTATÍSTICAS (MANTIDO)
# =============================
def carregar_estatisticas():
    """Carrega as estatísticas de acertos/erros"""
    return carregar_json(STATS_PATH) or {
        "total_pontos": {"acertos": 0, "erros": 0, "total": 0},
        "vencedor": {"acertos": 0, "erros": 0, "total": 0},
        "primeiro_quarto": {"acertos": 0, "erros": 0, "total": 0},
        "jogos_analisados": 0,
        "data_ultima_atualizacao": None
    }

def salvar_estatisticas(dados):
    """Salva as estatísticas"""
    salvar_json(STATS_PATH, dados)

def atualizar_estatisticas(resultado_total: str, resultado_vencedor: str, resultado_quarto: str = None):
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
    
    # Atualiza estatísticas de Primeiro Quarto (se disponível)
    if resultado_quarto and resultado_quarto in ["🟢 GREEN", "🔴 RED"]:
        if resultado_quarto == "🟢 GREEN":
            stats["primeiro_quarto"]["acertos"] += 1
            stats["primeiro_quarto"]["total"] += 1
        elif resultado_quarto == "🔴 RED":
            stats["primeiro_quarto"]["erros"] += 1
            stats["primeiro_quarto"]["total"] += 1
    
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
    
    col1, col2, col3, col4 = st.columns(4)
    
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
            label="⏱️ 1º Quarto",
            value=f"{stats['primeiro_quarto']['acertos']}/{stats['primeiro_quarto']['total']}",
            delta=f"{calcular_taxa_acerto(stats['primeiro_quarto']['acertos'], stats['primeiro_quarto']['total']):.1f}%"
        )
        st.progress(stats['primeiro_quarto']['acertos'] / max(stats['primeiro_quarto']['total'], 1))
    
    with col4:
        st.metric(
            label="📈 Jogos Analisados",
            value=stats["jogos_analisados"],
            delta="Performance"
        )
        taxa_geral = (stats['total_pontos']['acertos'] + stats['vencedor']['acertos']) / max((stats['total_pontos']['total'] + stats['vencedor']['total']), 1) * 100
        st.write(f"**Taxa Geral:** {taxa_geral:.1f}%")
    
    # Estatísticas detalhadas
    st.subheader("📋 Detalhamento por Categoria")
    
    col1, col2, col3 = st.columns(3)
    
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
    
    with col3:
        st.write("**1º Quarto**")
        st.write(f"✅ Acertos: {stats['primeiro_quarto']['acertos']}")
        st.write(f"❌ Erros: {stats['primeiro_quarto']['erros']}")
        st.write(f"📊 Total: {stats['primeiro_quarto']['total']}")
        st.write(f"🎯 Taxa: {calcular_taxa_acerto(stats['primeiro_quarto']['acertos'], stats['primeiro_quarto']['total']):.1f}%")
    
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
        "primeiro_quarto": {"acertos": 0, "erros": 0, "total": 0},
        "jogos_analisados": 0,
        "data_ultima_atualizacao": None
    }
    salvar_estatisticas(stats)
    return stats

# =============================
# REQUISIÇÕES À API (MANTIDO)
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
# DADOS DOS TIMES (MANTIDO)
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
# BUSCA DE JOGOS REAIS (MANTIDO)
# =============================
def obter_jogos_data(data_str: str) -> list:
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
            
        jogos.extend(data_chunk)
        
        meta = resp.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
            
        page += 1

    cache[key] = jogos
    salvar_cache_games(cache)
    return jogos

# =============================
# ATUALIZAR RESULTADOS DAS PARTIDAS (MANTIDO)
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
# CONFERIR JOGOS FINALIZADOS (MANTIDO)
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
# ESTATÍSTICAS REAIS - TEMPORADA 2024-2025 (MANTIDO)
# =============================
def obter_estatisticas_time_2025(team_id: int, window_games: int = 15) -> dict:
    """Busca estatísticas reais da temporada 2024-2025 - CORRIGIDA"""
    cache = carregar_cache_stats()
    key = f"team_{team_id}_2025"
    
    if key in cache:
        cached_data = cache[key]
        if cached_data.get("games", 0) > 0:
            return cached_data

    # Busca jogos da temporada 2024-2025
    start_date = "2024-10-01"
    end_date = "2025-06-30"
    
    games = []
    page = 1
    max_pages = 3
    
    while page <= max_pages:
        params = {
            "team_ids[]": team_id,
            "per_page": 25,
            "page": page,
            "start_date": start_date,
            "end_date": end_date,
            "seasons[]": 2024
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

    # Se não encontrou jogos válidos, usa fallback
    if not games_validos:
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
        
        try:
            games_validos.sort(key=lambda x: x.get("date", ""), reverse=True)
            games_validos = games_validos[:window_games]
        except Exception:
            games_validos = games_validos[:window_games]

    # CORREÇÃO PRINCIPAL: Cálculo correto das estatísticas
    if not games_validos:
        stats = {
            "pts_for_avg": 114.5,
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
                
                # CORREÇÃO: Identificação correta se o time é home ou visitor
                if home_id == team_id:
                    # Time é o home team
                    pts_for += home_score
                    pts_against += visitor_score
                    if home_score > visitor_score:
                        wins += 1
                else:
                    # Time é o visitor team  
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
# PREVISÕES COM DADOS REAIS 2024-2025 (MANTIDO)
# =============================
def prever_total_points(home_id: int, away_id: int, window_games: int = 15) -> tuple[float, float, str]:
    """Previsão baseada em dados reais da temporada 2024-2025 - CORRIGIDA"""
    # CORREÇÃO: Obtém estatísticas corretamente identificadas
    home_stats = obter_estatisticas_time_2025(home_id, window_games)
    away_stats = obter_estatisticas_time_2025(away_id, window_games)
    
    # CORREÇÃO: Usa médias de pontos FEITOS (pts_for_avg) para cada time
    home_avg = home_stats["pts_for_avg"]  # Pontos que o time da casa faz
    away_avg = away_stats["pts_for_avg"]  # Pontos que o time visitante faz
    
    # Ajuste para vantagem de casa - time da casa tende a fazer mais pontos
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
        confianca = 45.0
    
    # Ajusta confiança baseado na consistência dos times
    home_consistency = min(10, abs(home_stats.get("pts_diff_avg", 0)) * 0.5)
    away_consistency = min(10, abs(away_stats.get("pts_diff_avg", 0)) * 0.5)
    confianca += (home_consistency + away_consistency)
    confianca = min(85.0, max(40.0, confianca))
    
    # Determina tendência
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
    """Previsão de vencedor baseada em dados reais - CORRIGIDA"""
    # CORREÇÃO: Obtém estatísticas corretamente identificadas
    home_stats = obter_estatisticas_time_2025(home_id, window_games)
    away_stats = obter_estatisticas_time_2025(away_id, window_games)
    
    # CORREÇÃO: Usa win_rate correta de cada time
    home_win_rate = home_stats["win_rate"]
    away_win_rate = away_stats["win_rate"]
    home_pts_diff = home_stats["pts_diff_avg"]
    away_pts_diff = away_stats["pts_diff_avg"]
    
    # Vantagem de jogar em casa
    home_advantage = 0.1
    
    # Calcula probabilidade CORRETAMENTE
    home_strength = home_win_rate + home_pts_diff * 0.01
    away_strength = away_win_rate + away_pts_diff * 0.01
    
    # CORREÇÃO: Cálculo correto das probabilidades
    total_strength = home_strength + away_strength
    if total_strength > 0:
        home_prob = (home_strength / total_strength) + home_advantage
        away_prob = 1 - home_prob
    else:
        home_prob = 0.5 + home_advantage
        away_prob = 0.5 - home_advantage
    
    # Garante que as probabilidades estejam entre 0 e 1
    home_prob = max(0.0, min(1.0, home_prob))
    away_prob = max(0.0, min(1.0, away_prob))
    
    # Normaliza se necessário
    total_prob = home_prob + away_prob
    if total_prob > 0:
        home_prob = home_prob / total_prob
        away_prob = away_prob / total_prob
    
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
# PREVISÃO DE PONTOS POR QUARTO (MANTIDO)
# =============================
def prever_pontos_quarto(home_id: int, away_id: int, window_games: int = 15) -> tuple[float, float, str]:
    """Previsão de pontos no 1º quarto - CORRIGIDA"""
    # CORREÇÃO: Obtém estatísticas corretamente identificadas
    home_stats = obter_estatisticas_time_2025(home_id, window_games)
    away_stats = obter_estatisticas_time_2025(away_id, window_games)
    
    # CORREÇÃO: Usa médias corretas de pontos
    home_q1_avg = home_stats.get("pts_for_avg", 114.5) * 0.24
    away_q1_avg = away_stats.get("pts_for_avg", 114.5) * 0.24
    
    home_advantage = 1.0
    estimativa = home_q1_avg + away_q1_avg + home_advantage
    
    # Calcula confiança baseada na quantidade de dados
    home_games = home_stats["games"]
    away_games = away_stats["games"]
    min_games = min(home_games, away_games)
    
    if min_games >= 10:
        confianca = 65.0
    elif min_games >= 5:
        confianca = 55.0
    elif min_games > 0:
        confianca = 45.0
    else:
        confianca = 35.0
    
    home_consistency = min(8, abs(home_stats.get("pts_diff_avg", 0)) * 0.3)
    away_consistency = min(8, abs(away_stats.get("pts_diff_avg", 0)) * 0.3)
    confianca += (home_consistency + away_consistency)
    confianca = min(75.0, max(30.0, confianca))
    
    # Determina tendência baseada em dados reais
    if estimativa >= 58:
        tendencia = "Mais 58.5"
    elif estimativa >= 56:
        tendencia = "Mais 56.5"
    elif estimativa >= 54:
        tendencia = "Mais 54.5"
    elif estimativa >= 52:
        tendencia = "Mais 52.5"
    elif estimativa >= 50:
        tendencia = "Mais 50.5"
    else:
        tendencia = "Menos 50.5"
        
    return round(estimativa, 1), round(confianca, 1), tendencia

# =============================
# ALERTAS E TELEGRAM (MANTIDO)
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        resp = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False

def formatar_msg_alerta(game: dict, predictions: dict) -> str:
    try:
        home = game.get("home_team", {}).get("full_name", "Casa")
        away = game.get("visitor_team", {}).get("full_name", "Visitante")
        
        data_hora = game.get("datetime") or game.get("date") or ""
        if data_hora:
            try:
                dt = datetime.fromisoformat(data_hora.replace("Z", "+00:00")) - timedelta(hours=3)
                data_str = dt.strftime("%d/%m/%Y")
                hora_str = dt.strftime("%H:%M")
            except:
                data_str, hora_str = "-", "-"
        else:
            data_str, hora_str = "-", "-"

        msg = f"🏀 <b>Alerta NBA - {data_str} {hora_str} (BRT)</b>\n"
        msg += f"🏟️ {home} vs {away}\n"
        msg += f"📌 Status: {game.get('status', 'SCHEDULED')}\n\n"

        total_pred = predictions.get("total", {})
        if total_pred:
            msg += f"📈 <b>Total Pontos</b>: {total_pred.get('tendencia', 'N/A')}\n"
            msg += f"   📊 Estimativa: <b>{total_pred.get('estimativa', 0):.1f}</b> | Confiança: {total_pred.get('confianca', 0):.0f}%\n\n"

        vencedor_pred = predictions.get("vencedor", {})
        if vencedor_pred:
            msg += f"🎯 <b>Vencedor</b>: {vencedor_pred.get('vencedor', 'N/A')}\n"
            msg += f"   💪 Confiança: {vencedor_pred.get('confianca', 0):.0f}% | {vencedor_pred.get('detalhe', '')}\n\n"

        # NOVO: Previsão do 1º Quarto
        primeiro_quarto_pred = predictions.get("primeiro_quarto", {})
        if primeiro_quarto_pred:
            msg += f"⏱️ <b>1º Quarto</b>: {primeiro_quarto_pred.get('tendencia', 'N/A')}\n"
            msg += f"   📊 Estimativa: <b>{primeiro_quarto_pred.get('estimativa', 0):.1f}</b> | Confiança: {primeiro_quarto_pred.get('confianca', 0):.0f}%\n\n"

        msg += "\n🏆 <b>Elite Master</b> - Análise com Dados Reais 2024-2025"
        return msg
    except Exception as e:
        return f"⚠️ Erro ao formatar: {e}"

def verificar_e_enviar_alerta(game: dict, predictions: dict, send_to_telegram: bool = False):
    alertas = carregar_alertas()
    fid = str(game.get("id"))
    
    if fid not in alertas:
        alertas[fid] = {
            "game_id": fid,
            "game_data": game,
            "predictions": predictions,
            "timestamp": datetime.now().isoformat(),
            "enviado_telegram": send_to_telegram,
            "conferido": False
        }
        salvar_alertas(alertas)
        
        msg = formatar_msg_alerta(game, predictions)
        
        # Se marcado para enviar ao Telegram, envia
        if send_to_telegram:
            if enviar_telegram(msg):
                alertas[fid]["enviado_telegram"] = True
                salvar_alertas(alertas)
                return True
            else:
                return False
        return True
    return False

# =============================
# SISTEMA TOP 4 MELHORES JOGOS (MANTIDO)
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
    
    # 3. Potencial de pontos totais (over/under implícito)
    pontos_totais_esperados = home_stats.get("pts_for_avg", 0) + visitor_stats.get("pts_for_avg", 0)
    
    # Pontuação final
    pontuacao = (ofensiva_total * 0.4) + (fator_competitividade * 30) + (pontos_totais_esperados * 0.3)
    
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
        
        jogos_com_pontuacao.append({
            "jogo": jogo,
            "pontuacao": pontuacao,
            "home_team_name": home_team_name,
            "visitor_team_name": visitor_team_name,
            "home_stats": times_stats.get(jogo["home_team"]["id"], {}),
            "visitor_stats": times_stats.get(jogo["visitor_team"]["id"], {})
        })
    
    # Ordena por pontuação (decrescente) e pega top 4
    jogos_com_pontuacao.sort(key=lambda x: x["pontuacao"], reverse=True)
    return jogos_com_pontuacao[:4]

def enviar_alerta_top4_jogos(data_str: str):
    """Envia alerta com os 4 melhores jogos do dia para o canal alternativo"""
    top4_jogos = obter_top4_melhores_jogos(data_str)
    
    if not top4_jogos:
        mensagem = f"🏀 <b>TOP 4 JOGOS - {data_str}</b>\n\n"
        mensagem += "⚠️ Nenhum jogo encontrado para hoje."
        enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)
        return
    
    # Constroi mensagem formatada
    mensagem = f"🏀 <b>TOP 4 MELHORES JOGOS - {data_str}</b>\n\n"
    mensagem += "⭐ <i>Jogos mais promissores do dia</i> ⭐\n\n"
    
    for i, jogo_info in enumerate(top4_jogos, 1):
        home_team = jogo_info["home_team_name"]
        visitor_team = jogo_info["visitor_team_name"]
        home_stats = jogo_info["home_stats"]
        visitor_stats = jogo_info["visitor_stats"]
        
        # Emojis para ranking
        emojis = ["🥇", "🥈", "🥉", "4️⃣"]
        
        mensagem += f"{emojis[i-1]} <b>{visitor_team} @ {home_team}</b>\n"
        
        # Adiciona estatísticas relevantes
        if home_stats and visitor_stats:
            total_esperado = home_stats.get("pts_for_avg", 0) + visitor_stats.get("pts_for_avg", 0)
            mensagem += f"   📊 Total Esperado: <b>{total_esperado:.1f} pts</b>\n"
            mensagem += f"   🏆 Competitividade: <b>{(1 - abs(home_stats.get('win_rate',0) - visitor_stats.get('win_rate',0)))*100:.0f}%</b>\n"
        
        mensagem += "\n"
    
    mensagem += "📈 <i>Baseado em estatísticas ofensivas e competitividade</i>\n"
    mensagem += "#Top4Jogos #NBA"
    
    # Envia para o canal alternativo
    enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)
    st.success("✅ Alerta Top 4 Jogos enviado para canal alternativo!")

# =============================
# EXIBIÇÃO DOS JOGOS ANALISADOS (ATUALIZADO COM POSTER)
# =============================
def exibir_jogos_analisados():
    st.header("📈 Jogos Analisados - Sistema Poster")
    
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
        
        # Usa a nova função de alerta poster
        criar_alerta_poster(game_data, predictions)
        
        # Informações adicionais abaixo do card
        col1, col2 = st.columns(2)
        
        with col1:
            if alerta.get("enviado_telegram", False):
                st.success("📤 Enviado para Telegram")
            else:
                st.info("📝 Salvo localmente")
        
        with col2:
            timestamp = alerta.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    st.caption(f"🕒 Analisado em: {dt.strftime('%d/%m/%Y %H:%M')}")
                except:
                    pass
        
        st.markdown("---")

# =============================
# CONFERÊNCIA DE RESULTADOS (ATUALIZADO COM POSTER)
# =============================
def conferir_resultados():
    st.header("📊 Conferência de Resultados - Sistema Poster")
    
    # Botões de ação para conferência
    col1, col2, col3 = st.columns([2, 1, 1])
    
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
        
        total_pontos = home_score + away_score
        
        # Determina resultados
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
        
        # Usa o alerta poster para exibir
        criar_alerta_poster(
            game_data, 
            predictions, 
            resultado_total, 
            resultado_vencedor, 
            None  # resultado_quarto não disponível
        )
        
        # Botão de confirmação
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col3:
            if not alerta.get("conferido", False):
                if st.button("✅ Confirmar Resultado", key=f"conf_{alerta_id}"):
                    # Atualiza estatísticas quando confirma
                    if resultado_total in ["🟢 GREEN", "🔴 RED"] and resultado_vencedor in ["🟢 GREEN", "🔴 RED"]:
                        atualizar_estatisticas(resultado_total, resultado_vencedor, None)
                    
                    alertas[alerta_id]["conferido"] = True
                    salvar_alertas(alertas)
                    st.rerun()
            else:
                st.success("✅ Conferido")
        
        st.markdown("---")

# =============================
# INTERFACE STREAMLIT (ATUALIZADA)
# =============================
def main():
    st.set_page_config(page_title="🏀 Elite Master - NBA Alerts", layout="wide")
    st.title("🏀 Elite Master — Análise com Dados Reais 2024-2025")
    
    st.sidebar.header("⚙️ Configurações")
    st.sidebar.info("🎯 **Fonte:** Dados Reais da API")
    st.sidebar.success("📊 **Temporada:** 2024-2025")
    
    # Botão para Top 4 Jogos
    st.sidebar.markdown("---")
    st.sidebar.subheader("⭐ Top 4 Jogos")
    
    data_selecionada = st.sidebar.date_input("Data para Top 4:", value=date.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")
    
    if st.sidebar.button("🚀 Enviar Top 4 Melhores Jogos", type="primary"):
        with st.spinner("Buscando melhores jogos e enviando alerta..."):
            enviar_alerta_top4_jogos(data_str)
    
    # Visualização do Top 4
    if st.sidebar.button("👀 Visualizar Top 4 Jogos"):
        top4_jogos = obter_top4_melhores_jogos(data_str)
        
        if top4_jogos:
            st.sidebar.success(f"🎯 Top 4 Jogos para {data_str}:")
            for i, jogo_info in enumerate(top4_jogos, 1):
                home_team = jogo_info["home_team_name"]
                visitor_team = jogo_info["visitor_team_name"]
                pontuacao = jogo_info["pontuacao"]
                st.sidebar.write(f"{i}. {visitor_team} @ {home_team}")
                st.sidebar.write(f"   Pontuação: {pontuacao:.1f}")
        else:
            st.sidebar.warning("Nenhum jogo encontrado para esta data.")
    
    # Botão para atualizar resultados na sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 Atualizações")
    
    if st.sidebar.button("📡 Atualizar Todos os Resultados", type="secondary"):
        with st.spinner("Atualizando resultados de todas as partidas salvas..."):
            jogos_atualizados = atualizar_resultados_partidas()
            if jogos_atualizados > 0:
                st.sidebar.success(f"✅ {jogos_atualizados} jogos atualizados!")
            else:
                st.sidebar.info("ℹ️ Nenhum jogo precisou de atualização.")
    
    # Botão para gerenciar escudos
    st.sidebar.markdown("---")
    st.sidebar.subheader("🖼️ Gerenciar Escudos")
    
    if st.sidebar.button("🗑️ Limpar Cache de Escudos", type="secondary"):
        limpar_cache_escudos()
        st.rerun()
    
    # Botão para limpar estatísticas
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Estatísticas")
    
    if st.sidebar.button("🧹 Limpar Estatísticas", type="secondary"):
        limpar_estatisticas()
        st.sidebar.success("✅ Estatísticas limpas!")
        st.rerun()
    
    # Aba de estatísticas
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Análise", "📊 Jogos Analisados", "✅ Conferência", "📈 Estatísticas"])
    
    with tab1:
        exibir_aba_analise()
    
    with tab2:
        exibir_jogos_analisados()
    
    with tab3:
        conferir_resultados()
    
    with tab4:
        exibir_estatisticas()

def exibir_aba_analise():
    st.header("🎯 Análise com Dados Reais 2024-2025")
    
    with st.sidebar:
        st.subheader("Controles de Análise")
        top_n = st.slider("Número de jogos para analisar", 1, 20, 10)
        janela = st.slider("Jogos recentes para análise", 8, 20, 15)
        enviar_auto = st.checkbox("Enviar alertas automaticamente para Telegram", value=True)
        
        st.markdown("---")
        st.subheader("Gerenciamento")
        if st.button("🧹 Limpar Cache", type="secondary"):
            for f in [CACHE_GAMES, CACHE_STATS, ALERTAS_PATH, ESCUDOS_CACHE_PATH]:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        st.success(f"🗑️ {f} removido")
                except:
                    pass
            st.rerun()

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        data_sel = st.date_input("Selecione a data:", value=date.today())
    with col2:
        st.write("")
        st.write("")
        if st.button("🚀 ANALISAR COM DADOS 2024-2025", type="primary", use_container_width=True):
            analisar_jogos_com_dados_2025(data_sel, top_n, janela, enviar_auto)
    with col3:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar Dados", type="secondary"):
            st.rerun()

def analisar_jogos_com_dados_2025(data_sel: date, top_n: int, janela: int, enviar_auto: bool):
    data_str = data_sel.strftime("%Y-%m-%d")
    
    progress_placeholder = st.empty()
    results_placeholder = st.empty()
    
    with progress_placeholder:
        st.info(f"🔍 Buscando dados reais para {data_sel.strftime('%d/%m/%Y')}...")
        st.success("📊 Analisando com dados da temporada 2024-2025")
        if enviar_auto:
            st.warning("📤 Alertas serão enviados para Telegram")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Busca jogos
    jogos = obter_jogos_data(data_str)
    
    if not jogos:
        st.error("❌ Nenhum jogo encontrado para esta data")
        return
    
    # CORREÇÃO: Mostrar todos os jogos disponíveis
    st.info(f"📋 Encontrados {len(jogos)} jogos para {data_sel.strftime('%d/%m/%Y')}")
    
    # Mostra lista de jogos encontrados
    st.subheader("🏀 Jogos Encontrados na API")
    for i, jogo in enumerate(jogos):
        home_team = jogo['home_team']['full_name']
        away_team = jogo['visitor_team']['full_name']
        status = jogo.get('status', 'SCHEDULED')
        st.write(f"{i+1}. {away_team} @ {home_team} - {status}")
    
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
            status_text.text(f"🔍 Analisando: {away_team} @ {home_team} ({i+1}/{len(jogos)})")
            
            home_id = jogo["home_team"]["id"]
            away_id = jogo["visitor_team"]["id"]
            
            try:
                # Previsões com dados reais 2024-2025 (CORRIGIDAS)
                total_estim, total_conf, total_tend = prever_total_points(home_id, away_id, janela)
                vencedor, vencedor_conf, vencedor_detalhe = prever_vencedor(home_id, away_id, janela)
                # NOVO: Previsão do 1º Quarto (CORRIGIDA)
                q1_estim, q1_conf, q1_tend = prever_pontos_quarto(home_id, away_id, janela)
                
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
                    },
                    # NOVO: Previsão do 1º Quarto
                    "primeiro_quarto": {
                        "estimativa": q1_estim,
                        "confianca": q1_conf,
                        "tendencia": q1_tend
                    }
                }
                
                # Envia alerta
                enviado = verificar_e_enviar_alerta(jogo, predictions, enviar_auto)
                if enviado and enviar_auto:
                    alertas_enviados += 1
                
                # Exibe resultado com alerta poster
                criar_alerta_poster(jogo, predictions)
                
                # Status do envio
                col1, col2 = st.columns(2)
                with col1:
                    if enviado and enviar_auto:
                        st.success("✅ Telegram: Alerta enviado")
                    else:
                        st.info("💾 Salvo: Alerta armazenado localmente")
                
                with col2:
                    st.caption(f"🕒 Analisado em: {datetime.now().strftime('%H:%M')}")
                
                st.markdown("---")
                
                resultados.append({
                    "jogo": jogo,
                    "predictions": predictions
                })
                
            except Exception as e:
                st.error(f"❌ Erro ao analisar {away_team} @ {home_team}: {e}")
                continue
    
    progress_placeholder.empty()
    
    # Resumo final
    st.success(f"✅ Análise com dados 2024-2025 concluída!")
    st.info(f"""
    **📊 Resumo da Análise:**
    - 🏀 {len(resultados)} jogos analisados com dados 2024-2025
    - 📤 {alertas_enviados} alertas enviados para Telegram
    - 📈 Estatísticas baseadas na temporada atual
    - ⏱️ Previsões de 1º Quarto incluídas
    - 💾 Dados salvos para conferência futura
    - 🎨 Alertas no estilo Poster com escudos reais
    """)

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if __name__ == "__main__":
    main()
