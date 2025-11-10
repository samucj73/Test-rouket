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
# BUSCA DE JOGOS REAIS
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
# FUNÇÕES DE IMAGEM E ESCUDOS CORRIGIDAS - VERSÃO MELHORADA
# =============================
def baixar_escudo_time(time_nome: str, tamanho: tuple = (120, 120)) -> Image.Image:
    """Baixa e redimensiona o escudo do time com fallbacks robustos"""
    try:
        # URL do logo do time
        logo_url = NBA_LOGOS.get(time_nome, "")
        
        if not logo_url:
            # Fallback: cria escudo padrão com iniciais do time
            return criar_escudo_detalhado(time_nome, tamanho)
        
        # Para logos SVG da NBA, vamos usar uma abordagem diferente
        # Criar escudos detalhados baseados nas cores oficiais dos times
        return criar_escudo_detalhado(time_nome, tamanho)
            
    except Exception as e:
        print(f"Erro ao baixar escudo do {time_nome}: {e}")
        return criar_escudo_detalhado(time_nome, tamanho)

def criar_escudo_detalhado(time_nome: str, tamanho: tuple) -> Image.Image:
    """Cria escudo detalhado com cores e designs baseados nos times reais"""
    largura, altura = tamanho
    img = Image.new('RGBA', tamanho, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Cores e designs detalhados dos times NBA
    designs_times = {
        'Lakers': {
            'cores': [(85, 37, 130), (253, 185, 39)],  # Roxo e dourado
            'design': 'circulo_duplo',
            'texto': 'LA'
        },
        'Warriors': {
            'cores': [(29, 66, 138), (255, 199, 44)],  # Azul e dourado
            'design': 'circulo_ponteado',
            'texto': 'GSW'
        },
        'Celtics': {
            'cores': [(0, 122, 51), (255, 255, 255)],  # Verde e branco
            'design': 'circulo_triplo',
            'texto': 'BOS'
        },
        'Bulls': {
            'cores': [(206, 17, 65), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_duplo',
            'texto': 'CHI'
        },
        'Heat': {
            'cores': [(152, 0, 46), (255, 255, 255)],  # Vermelho e branco
            'design': 'circulo_chamas',
            'texto': 'MIA'
        },
        'Knicks': {
            'cores': [(0, 107, 182), (245, 132, 38)],  # Azul e laranja
            'design': 'circulo_listras',
            'texto': 'NYK'
        },
        'Cavaliers': {
            'cores': [(134, 0, 56), (4, 30, 66)],  # Vinho e azul marinho
            'design': 'circulo_duplo',
            'texto': 'CLE'
        },
        'Spurs': {
            'cores': [(196, 206, 212), (0, 0, 0)],  # Prata e preto
            'design': 'circulo_espinhos',
            'texto': 'SAS'
        },
        'Mavericks': {
            'cores': [(0, 83, 188), (0, 43, 92)],  # Azul
            'design': 'circulo_estrela',
            'texto': 'DAL'
        },
        'Nets': {
            'cores': [(0, 0, 0), (255, 255, 255)],  # Preto e branco
            'design': 'circulo_simples',
            'texto': 'BKN'
        },
        'Raptors': {
            'cores': [(206, 17, 65), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_duplo',
            'texto': 'TOR'
        },
        'Suns': {
            'cores': [(229, 95, 32), (0, 0, 0)],  # Laranja e preto
            'design': 'circulo_raio',
            'texto': 'PHX'
        },
        'Nuggets': {
            'cores': [(13, 34, 64), (255, 198, 39)],  # Azul e amarelo
            'design': 'circulo_montanhas',
            'texto': 'DEN'
        },
        'Bucks': {
            'cores': [(0, 71, 27), (240, 235, 210)],  # Verde e creme
            'design': 'circulo_chifres',
            'texto': 'MIL'
        },
        '76ers': {
            'cores': [(0, 107, 182), (237, 23, 76)],  # Azul e vermelho
            'design': 'circulo_estrelas',
            'texto': 'PHI'
        },
        'Hawks': {
            'cores': [(225, 68, 52), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_duplo',
            'texto': 'ATL'
        },
        'Hornets': {
            'cores': [(29, 17, 96), (0, 120, 140)],  # Azul e turquesa
            'design': 'circulo_listras',
            'texto': 'CHA'
        },
        'Pistons': {
            'cores': [(200, 16, 46), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_simples',
            'texto': 'DET'
        },
        'Rockets': {
            'cores': [(206, 17, 65), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_duplo',
            'texto': 'HOU'
        },
        'Pacers': {
            'cores': [(0, 45, 98), (253, 187, 48)],  # Azul e amarelo
            'design': 'circulo_duplo',
            'texto': 'IND'
        },
        'Clippers': {
            'cores': [(200, 16, 46), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_simples',
            'texto': 'LAC'
        },
        'Grizzlies': {
            'cores': [(93, 118, 169), (0, 0, 0)],  # Azul e preto
            'design': 'circulo_duplo',
            'texto': 'MEM'
        },
        'Timberwolves': {
            'cores': [(0, 80, 48), (120, 190, 32)],  # Verde e azul
            'design': 'circulo_duplo',
            'texto': 'MIN'
        },
        'Pelicans': {
            'cores': [(0, 43, 92), (225, 58, 62)],  # Azul e vermelho
            'design': 'circulo_duplo',
            'texto': 'NOP'
        },
        'Thunder': {
            'cores': [(0, 125, 195), (239, 59, 36)],  # Azul e laranja
            'design': 'circulo_duplo',
            'texto': 'OKC'
        },
        'Magic': {
            'cores': [(0, 125, 197), (196, 206, 212)],  # Azul e prata
            'design': 'circulo_duplo',
            'texto': 'ORL'
        },
        'Trail Blazers': {
            'cores': [(224, 58, 62), (0, 0, 0)],  # Vermelho e preto
            'design': 'circulo_duplo',
            'texto': 'POR'
        },
        'Kings': {
            'cores': [(91, 43, 130), (0, 0, 0)],  # Roxo e preto
            'design': 'circulo_duplo',
            'texto': 'SAC'
        },
        'Jazz': {
            'cores': [(0, 43, 92), (0, 0, 0)],  # Azul e preto
            'design': 'circulo_musica',
            'texto': 'UTA'
        },
        'Wizards': {
            'cores': [(0, 43, 92), (227, 24, 55)],  # Azul e vermelho
            'design': 'circulo_duplo',
            'texto': 'WAS'
        },
        'default': {
            'cores': [(255, 125, 0), (0, 0, 0)],  # Laranja NBA
            'design': 'circulo_simples',
            'texto': ''.join([palavra[0].upper() for palavra in time_nome.split()[:2]]) or time_nome[:2].upper()
        }
    }
    
    # Encontra design do time
    design_time = designs_times['default']
    for nome, design in designs_times.items():
        if nome.lower() in time_nome.lower():
            design_time = design
            break
    
    cores = design_time['cores']
    texto = design_time['texto']
    tipo_design = design_time['design']
    
    # Raio do círculo principal
    raio = min(largura, altura) // 2 - 5
    centro_x, centro_y = largura // 2, altura // 2
    
    # Desenha base do escudo baseado no design
    if tipo_design == 'circulo_duplo':
        # Círculo duplo
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0], outline=cores[1], width=4)
        draw.ellipse([centro_x - raio + 10, centro_y - raio + 10, centro_x + raio - 10, centro_y + raio - 10], 
                    fill=None, outline=cores[1], width=2)
        
    elif tipo_design == 'circulo_triplo':
        # Círculo triplo
        for i in range(3):
            r = raio - i * 8
            cor = cores[i % len(cores)] if i < len(cores) else cores[0]
            draw.ellipse([centro_x - r, centro_y - r, centro_x + r, centro_y + r], 
                        fill=None, outline=cor, width=3)
        
    elif tipo_design == 'circulo_ponteado':
        # Círculo com efeito pontilhado
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Adiciona pontos na borda
        for angulo in range(0, 360, 15):
            rad = math.radians(angulo)
            x1 = centro_x + (raio - 5) * math.cos(rad)
            y1 = centro_y + (raio - 5) * math.sin(rad)
            x2 = centro_x + raio * math.cos(rad)
            y2 = centro_y + raio * math.sin(rad)
            draw.line([x1, y1, x2, y2], fill=cores[1], width=2)
        
    elif tipo_design == 'circulo_raio':
        # Círculo com raios
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        for angulo in range(0, 360, 30):
            rad = math.radians(angulo)
            x = centro_x + raio * math.cos(rad)
            y = centro_y + raio * math.sin(rad)
            draw.line([centro_x, centro_y, x, y], fill=cores[1], width=3)
        
    elif tipo_design == 'circulo_estrela':
        # Círculo com estrela
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Desenha estrela simples
        pontos_estrela = []
        for i in range(5):
            angulo = math.radians(90 + i * 72)
            r = raio * 0.6 if i % 2 == 0 else raio * 0.3
            x = centro_x + r * math.cos(angulo)
            y = centro_y + r * math.sin(angulo)
            pontos_estrela.append((x, y))
        draw.polygon(pontos_estrela, fill=cores[1])
        
    elif tipo_design == 'circulo_listras':
        # Círculo com listras
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        for i in range(0, raio * 2, 8):
            draw.line([centro_x - raio + i, centro_y - raio, centro_x - raio + i, centro_y + raio], 
                     fill=cores[1], width=2)
        
    elif tipo_design == 'circulo_chamas':
        # Círculo com efeito de chamas
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Adiciona "chamas" na parte superior
        for i in range(-20, 20, 5):
            x = centro_x + i
            y = centro_y - raio + 10
            draw.ellipse([x-3, y-5, x+3, y+5], fill=cores[1])
        
    elif tipo_design == 'circulo_espinhos':
        # Círculo com espinhos
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        for angulo in range(0, 360, 45):
            rad = math.radians(angulo)
            x1 = centro_x + (raio - 5) * math.cos(rad)
            y1 = centro_y + (raio - 5) * math.sin(rad)
            x2 = centro_x + (raio + 8) * math.cos(rad)
            y2 = centro_y + (raio + 8) * math.sin(rad)
            draw.line([x1, y1, x2, y2], fill=cores[1], width=3)
        
    elif tipo_design == 'circulo_montanhas':
        # Círculo com montanhas
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Desenha montanhas simples
        draw.polygon([(centro_x - raio//2, centro_y), (centro_x, centro_y - raio//2), (centro_x + raio//2, centro_y)], 
                    fill=cores[1])
        
    elif tipo_design == 'circulo_chifres':
        # Círculo com chifres
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Desenha chifres
        draw.ellipse([centro_x - raio//2, centro_y - raio//2, centro_x - raio//4, centro_y], fill=cores[1])
        draw.ellipse([centro_x + raio//4, centro_y - raio//2, centro_x + raio//2, centro_y], fill=cores[1])
        
    elif tipo_design == 'circulo_estrelas':
        # Círculo com estrelas
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Adiciona estrelas pequenas
        for i in range(5):
            angulo = math.radians(i * 72)
            x = centro_x + (raio * 0.6) * math.cos(angulo)
            y = centro_y + (raio * 0.6) * math.sin(angulo)
            draw.ellipse([x-3, y-3, x+3, y+3], fill=cores[1])
        
    elif tipo_design == 'circulo_musica':
        # Círculo com notas musicais (Jazz)
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0])
        # Notas musicais simples
        draw.ellipse([centro_x - 10, centro_y - 15, centro_x, centro_y - 5], fill=cores[1])
        draw.ellipse([centro_x + 5, centro_y - 10, centro_x + 15, centro_y], fill=cores[1])
        draw.line([centro_x, centro_y - 15, centro_x, centro_y + 10], fill=cores[1], width=3)
        draw.line([centro_x + 15, centro_y, centro_x + 15, centro_y + 15], fill=cores[1], width=3)
        
    else:  # circulo_simples (default)
        draw.ellipse([centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio], 
                    fill=cores[0], outline=cores[1], width=3)
    
    # Adiciona texto centralizado
    try:
        # Tamanho da fonte baseado no tamanho do escudo
        tamanho_fonte = max(14, raio // 3)
        font = ImageFont.truetype("arial.ttf", tamanho_fonte)
    except:
        font = ImageFont.load_default()
    
    # Calcula posição do texto
    bbox = draw.textbbox((0, 0), texto, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = centro_x - text_width // 2
    y = centro_y - text_height // 2
    
    # Cor do texto (contraste)
    cor_texto = (255, 255, 255) if sum(cores[0]) < 384 else (0, 0, 0)  # Branco para cores escuras, preto para claras
    
    draw.text((x, y), texto, fill=cor_texto, font=font)
    
    return img

def criar_imagem_alerta_nba(home_team: str, away_team: str, predictions: dict, data_hora: str = "") -> Image.Image:
    """Cria imagem de alerta estilo NBA com escudos dos times - VERSÃO GRANDE"""
    # Dimensões da imagem MAIORES
    largura, altura = 1000, 600  # Aumentei bastante o tamanho
    img = Image.new('RGB', (largura, altura), color=(13, 17, 23))  # Fundo escuro
    draw = ImageDraw.Draw(img)
    
    try:
        # Tenta carregar fontes (fallback para padrão)
        try:
            font_grande = ImageFont.truetype("arial.ttf", 42)
            font_medio = ImageFont.truetype("arial.ttf", 28)
            font_pequeno = ImageFont.truetype("arial.ttf", 20)
            font_negrito = ImageFont.truetype("arialbd.ttf", 32)
        except:
            # Fallback para fontes padrão
            font_grande = ImageFont.load_default()
            font_medio = ImageFont.load_default()
            font_pequeno = ImageFont.load_default()
            font_negrito = ImageFont.load_default()
        
        # Cabeçalho - NBA (MAIOR)
        draw.rectangle([0, 0, largura, 90], fill=(255, 125, 0))  # Laranja NBA
        draw.text((largura//2, 45), "🏀 NBA ELITE MASTER", fill=(255, 255, 255), 
                 font=font_negrito, anchor="mm")
        
        if data_hora:
            draw.text((largura//2, 75), data_hora, fill=(255, 255, 255), 
                     font=font_pequeno, anchor="mm")
        
        # Posicionamento dos times (MAIS ESPAÇO)
        centro_x = largura // 2
        pos_y = 180  # Mais abaixo para caber escudos maiores
        
        # Busca escudos (AGORA MAIORES)
        home_logo = criar_escudo_detalhado(home_team, (140, 140))  # Escudos maiores
        away_logo = criar_escudo_detalhado(away_team, (140, 140))
        
        # Posiciona escudos e nomes (MAIS ESPAÇO ENTRE ELES)
        espacamento = 280  # Mais espaço entre os times
        
        # Time visitante (esquerda) - MAIOR
        if away_logo:
            img.paste(away_logo, (centro_x - espacamento - 70, pos_y - 70), away_logo)
        draw.text((centro_x - espacamento, pos_y + 80), away_team, 
                 fill=(255, 255, 255), font=font_medio, anchor="mm")
        
        # VS no centro (MAIOR)
        draw.text((centro_x, pos_y), "VS", fill=(255, 125, 0), 
                 font=font_grande, anchor="mm")
        
        # Time da casa (direita) - MAIOR
        if home_logo:
            img.paste(home_logo, (centro_x + espacamento - 70, pos_y - 70), home_logo)
        draw.text((centro_x + espacamento, pos_y + 80), home_team, 
                 fill=(255, 255, 255), font=font_medio, anchor="mm")
        
        # Previsões - ÁREA EXPANDIDA E MAIOR
        pos_y_previsoes = 380
        
        # Total de pontos
        total_pred = predictions.get("total", {})
        if total_pred:
            tendencia = total_pred.get("tendencia", "N/A")
            estimativa = total_pred.get("estimativa", 0)
            confianca = total_pred.get("confianca", 0)
            
            # Cor baseada na confiança
            cor_confianca = (0, 255, 0) if confianca > 70 else (255, 255, 0) if confianca > 50 else (255, 165, 0)
            
            texto_total = f"📊 TOTAL: {tendencia}"
            texto_estimativa = f"Estimativa: {estimativa:.1f} pontos"
            texto_confianca = f"Confiança: {confianca:.0f}%"
            
            draw.text((centro_x, pos_y_previsoes), texto_total, 
                     fill=(0, 255, 0), font=font_medio, anchor="mm")
            draw.text((centro_x, pos_y_previsoes + 35), texto_estimativa, 
                     fill=(200, 200, 200), font=font_pequeno, anchor="mm")
            draw.text((centro_x, pos_y_previsoes + 60), texto_confianca, 
                     fill=cor_confianca, font=font_pequeno, anchor="mm")
        
        # Vencedor
        vencedor_pred = predictions.get("vencedor", {})
        if vencedor_pred:
            vencedor = vencedor_pred.get("vencedor", "N/A")
            confianca_venc = vencedor_pred.get("confianca", 0)
            detalhe = vencedor_pred.get("detalhe", "")
            
            # Cor baseada na confiança
            cor_confianca_venc = (0, 255, 0) if confianca_venc > 70 else (255, 255, 0) if confianca_venc > 50 else (255, 165, 0)
            
            texto_vencedor = f"🎯 VENCEDOR: {vencedor}"
            texto_confianca_venc = f"Confiança: {confianca_venc:.0f}%"
            texto_detalhe = f"{detalhe}"
            
            draw.text((centro_x, pos_y_previsoes + 100), texto_vencedor, 
                     fill=(255, 215, 0), font=font_medio, anchor="mm")
            draw.text((centro_x, pos_y_previsoes + 135), texto_confianca_venc, 
                     fill=cor_confianca_venc, font=font_pequeno, anchor="mm")
            draw.text((centro_x, pos_y_previsoes + 160), texto_detalhe, 
                     fill=(200, 200, 200), font=font_pequeno, anchor="mm")
        
        # Rodapé (MAIOR)
        draw.rectangle([0, altura-50, largura, altura], fill=(30, 30, 30))
        draw.text((centro_x, altura - 25), "ELITE MASTER - Análise com Dados Reais 2024-2025", 
                 fill=(150, 150, 150), font=font_pequeno, anchor="mm")
        
    except Exception as e:
        # Fallback robusto em caso de erro
        print(f"Erro ao criar imagem: {e}")
        draw.rectangle([0, 0, largura, altura], fill=(13, 17, 23))
        draw.text((largura//2, altura//2), f"Erro ao gerar imagem", 
                 fill=(255, 0, 0), font=font_medio, anchor="mm")
        draw.text((largura//2, altura//2 + 40), f"{home_team} vs {away_team}", 
                 fill=(255, 255, 255), font=font_pequeno, anchor="mm")
    
    return img

def imagem_para_base64(imagem: Image.Image) -> str:
    """Converte imagem PIL para base64"""
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()

def enviar_imagem_telegram(imagem: Image.Image, legenda: str = "", chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia imagem para o Telegram - VERSÃO CORRIGIDA"""
    try:
        # Converte imagem para bytes
        buffer = io.BytesIO()
        imagem.save(buffer, format='PNG', quality=95)
        buffer.seek(0)
        
        # Prepara os dados para envio
        files = {'photo': ('alerta_nba.png', buffer, 'image/png')}
        data = {
            'chat_id': chat_id,
            'caption': legenda,
            'parse_mode': 'HTML'
        }
        
        # Envia via API do Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        resposta = requests.post(url, files=files, data=data, timeout=30)
        
        # Verifica se foi bem sucedido
        if resposta.status_code == 200:
            print("✅ Imagem enviada com sucesso para o Telegram")
            return True
        else:
            print(f"❌ Erro ao enviar imagem: {resposta.status_code} - {resposta.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception ao enviar imagem: {e}")
        return False

# =============================
# ALERTAS E TELEGRAM
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
            msg += f"   💪 Confiança: {vencedor_pred.get('confianca', 0):.0f}% | {vencedor_pred.get('detalhe', '')}\n"

        msg += "\n🏆 <b>Elite Master</b> - Análise com Dados Reais 2024-2025"
        return msg
    except Exception as e:
        return f"⚠️ Erro ao formatar: {e}"

# =============================
# FUNÇÃO ATUALIZADA DE ENVIO DE ALERTAS COM IMAGEM
# =============================
def formatar_e_enviar_alerta_completo(game: dict, predictions: dict, enviar_imagem: bool = True) -> bool:
    """Formata e envia alerta completo com imagem e texto - VERSÃO CORRIGIDA"""
    try:
        home_team = game.get("home_team", {}).get("full_name", "Casa")
        away_team = game.get("visitor_team", {}).get("full_name", "Visitante")
        
        # Formata data e hora
        data_hora = game.get("datetime") or game.get("date") or ""
        data_str, hora_str = "-", "-"
        if data_hora:
            try:
                dt = datetime.fromisoformat(data_hora.replace("Z", "+00:00")) - timedelta(hours=3)
                data_str = dt.strftime("%d/%m/%Y")
                hora_str = dt.strftime("%H:%M")
            except:
                data_str, hora_str = "-", "-"
        
        data_hora_formatada = f"{data_str} {hora_str} (BRT)"
        
        # Mensagem textual para Telegram (SEMPRE enviar texto como fallback)
        mensagem_texto = f"🏀 <b>Alerta NBA - {data_hora_formatada}</b>\n"
        mensagem_texto += f"🏟️ <b>{away_team} @ {home_team}</b>\n"
        mensagem_texto += f"📌 Status: {game.get('status', 'SCHEDULED')}\n\n"
        
        total_pred = predictions.get("total", {})
        if total_pred:
            mensagem_texto += f"📈 <b>Total Pontos</b>: {total_pred.get('tendencia', 'N/A')}\n"
            mensagem_texto += f"   📊 Estimativa: <b>{total_pred.get('estimativa', 0):.1f}</b> | Confiança: {total_pred.get('confianca', 0):.0f}%\n\n"
        
        vencedor_pred = predictions.get("vencedor", {})
        if vencedor_pred:
            mensagem_texto += f"🎯 <b>Vencedor</b>: {vencedor_pred.get('vencedor', 'N/A')}\n"
            mensagem_texto += f"   💪 Confiança: {vencedor_pred.get('confianca', 0):.0f}% | {vencedor_pred.get('detalhe', '')}\n"
        
        mensagem_texto += "\n🏆 <b>Elite Master</b> - Análise com Dados Reais 2024-2025"
        
        # DEBUG: Mostra informações no console
        print(f"📤 Tentando enviar alerta: {away_team} @ {home_team}")
        print(f"🖼️ Enviar imagem: {enviar_imagem}")
        
        # Envia para Telegram
        sucesso = False
        
        if enviar_imagem:
            print("🔄 Tentando enviar com imagem...")
            # Tenta enviar com imagem
            imagem_alerta = criar_imagem_alerta_nba(home_team, away_team, predictions, data_hora_formatada)
            sucesso = enviar_imagem_telegram(imagem_alerta, mensagem_texto)
            
            if sucesso:
                print("✅ Alerta com imagem enviado com sucesso!")
            else:
                print("❌ Falha no envio com imagem, tentando apenas texto...")
        
        # Se imagem falhou ou não foi solicitada, envia apenas texto
        if not sucesso:
            print("🔄 Enviando apenas texto...")
            sucesso = enviar_telegram(mensagem_texto)
            
            if sucesso:
                print("✅ Alerta de texto enviado com sucesso!")
            else:
                print("❌ Falha no envio de texto também")
        
        return sucesso
        
    except Exception as e:
        print(f"💥 Erro crítico ao enviar alerta completo: {e}")
        # Fallback final: tenta enviar apenas o texto básico
        try:
            return enviar_telegram(formatar_msg_alerta(game, predictions))
        except:
            return False

# =============================
# FUNÇÃO ATUALIZADA DE VERIFICAÇÃO E ENVIO
# =============================
def verificar_e_enviar_alerta(game: dict, predictions: dict, send_to_telegram: bool = False, com_imagem: bool = True):
    """Versão atualizada com suporte a imagens"""
    alertas = carregar_alertas()
    fid = str(game.get("id"))
    
    if fid not in alertas:
        alertas[fid] = {
            "game_id": fid,
            "game_data": game,
            "predictions": predictions,
            "timestamp": datetime.now().isoformat(),
            "enviado_telegram": send_to_telegram,
            "enviado_com_imagem": com_imagem,  # NOVO: controle de imagem
            "conferido": False,
            "alerta_resultado_enviado": False
        }
        salvar_alertas(alertas)
        
        # Se marcado para enviar ao Telegram, envia
        if send_to_telegram:
            sucesso = formatar_e_enviar_alerta_completo(game, predictions, com_imagem)
            
            if sucesso:
                alertas[fid]["enviado_telegram"] = True
                alertas[fid]["enviado_com_imagem"] = com_imagem
                salvar_alertas(alertas)
                return True
            else:
                return False
        return True
    return False

# =============================
# FUNÇÃO PARA VISUALIZAR IMAGEM DE ALERTA
# =============================
def visualizar_imagem_alerta(game: dict, predictions: dict):
    """Gera e exibe a imagem de alerta no Streamlit - VERSÃO ATUALIZADA"""
    home_team = game.get("home_team", {}).get("full_name", "Casa")
    away_team = game.get("visitor_team", {}).get("full_name", "Visitante")
    
    # Formata data e hora
    data_hora = game.get("datetime") or game.get("date") or ""
    data_str, hora_str = "-", "-"
    if data_hora:
        try:
            dt = datetime.fromisoformat(data_hora.replace("Z", "+00:00")) - timedelta(hours=3)
            data_str = dt.strftime("%d/%m/%Y")
            hora_str = dt.strftime("%H:%M")
        except:
            data_str, hora_str = "-", "-"
    
    data_hora_formatada = f"{data_str} {hora_str} (BRT)"
    
    # Gera imagem COM NOVO TAMANHO
    imagem = criar_imagem_alerta_nba(home_team, away_team, predictions, data_hora_formatada)
    
    # Converte para exibir no Streamlit
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Exibe imagem
    st.image(buffer, caption=f"Preview: {away_team} @ {home_team}", use_column_width=True)
    
    # Botão para baixar imagem
    st.download_button(
        label="📥 Baixar Imagem do Alerta",
        data=buffer.getvalue(),
        file_name=f"alerta_nba_{home_team.replace(' ', '_')}_{away_team.replace(' ', '_')}.png",
        mime="image/png"
    )

# =============================
# FUNÇÃO DE DEBUG PARA TESTAR ENVIO
# =============================
def testar_envio_imagem():
    """Função para testar o envio de imagem"""
    st.header("🧪 Testar Envio de Imagem")
    
    # Dados de teste com vários times para demonstrar os diferentes escudos
    times_teste = [
        ("Los Angeles Lakers", "Golden State Warriors"),
        ("Boston Celtics", "Miami Heat"),
        ("Chicago Bulls", "New York Knicks"),
        ("Dallas Mavericks", "Phoenix Suns")
    ]
    
    for home_team, away_team in times_teste:
        st.subheader(f"{away_team} @ {home_team}")
        
        predictions = {
            "total": {
                "estimativa": 225.5,
                "confianca": 75.0,
                "tendencia": "Mais 225.5"
            },
            "vencedor": {
                "vencedor": "Casa",
                "confianca": 68.0,
                "detalhe": "Ligeira vantagem da casa"
            }
        }
        
        # Cria e exibe imagem
        imagem = criar_imagem_alerta_nba(home_team, away_team, predictions, "01/01/2024 20:00 (BRT)")
        
        # Converte para exibir no Streamlit
        buffer = io.BytesIO()
        imagem.save(buffer, format='PNG')
        buffer.seek(0)
        
        st.image(buffer, caption=f"Preview: {away_team} @ {home_team}", use_column_width=True)
        
        # Botão para testar envio individual
        if st.button(f"🚀 Testar {home_team} vs {away_team}", key=f"test_{home_team}_{away_team}"):
            with st.spinner(f"Enviando imagem de {home_team} vs {away_team}..."):
                mensagem_teste = f"🏀 <b>TESTE - Alerta NBA</b>\n🏟️ <b>{away_team} @ {home_team}</b>\n📌 Status: TESTE"
                
                sucesso = enviar_imagem_telegram(imagem, mensagem_teste)
                
                if sucesso:
                    st.success("✅ Imagem de teste enviada com sucesso!")
                else:
                    st.error("❌ Falha no envio da imagem de teste")
    
    st.markdown("---")
    st.info("**🎨 Escudos Personalizados:** Agora cada time tem um design único baseado em suas cores oficiais!")

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
        
        # Card do jogo
        with st.expander(f"🏀 {home_team} vs {away_team} - {status}", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**📊 Total de Pontos**")
                st.write(f"Tendência: {total_pred.get('tendencia', 'N/A')}")
                st.write(f"Estimativa: {total_pred.get('estimativa', 0):.1f}")
                st.write(f"Confiança: {total_pred.get('confianca', 0):.0f}%")
            
            with col2:
                st.write("**🎯 Vencedor**")
                st.write(f"Previsão: {vencedor_pred.get('vencedor', 'N/A')}")
                st.write(f"Confiança: {vencedor_pred.get('confianca', 0):.0f}%")
                st.write(f"Detalhe: {vencedor_pred.get('detalhe', '')}")
            
            if alerta.get("enviado_telegram", False):
                if alerta.get("enviado_com_imagem", False):
                    st.success("📤 Enviado para Telegram (com imagem)")
                else:
                    st.success("📤 Enviado para Telegram (apenas texto)")
            else:
                st.info("📝 Salvo localmente")
            
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
    
    # NOVO: Botão para enviar alerta de resultados
    with col4:
        if st.button("📤 Alerta Resultados", type="secondary", use_container_width=True):
            with st.spinner("Enviando alerta de resultados conferidos..."):
                jogos_alertados = enviar_alerta_resultados_conferidos()
                if jogos_alertados > 0:
                    st.success(f"✅ Alerta para {jogos_alertados} jogos enviado!")
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
        
        # Exibe card do jogo
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"**{home_team}** vs **{away_team}**")
            st.write(f"📊 **Placar:** {home_score} x {away_score}")
            st.write(f"🏀 **Total:** {total_pontos} pontos")
        
        with col2:
            st.write(f"**Total:** {tendencia_total}")
            st.write(f"**Resultado:** {resultado_total}")
            st.write(f"**Vencedor:** {resultado_vencedor}")
        
        with col3:
            if not alerta.get("conferido", False):
                if st.button("✅ Confirmar", key=f"conf_{alerta_id}"):
                    # Atualiza estatísticas quando confirma
                    if resultado_total in ["🟢 GREEN", "🔴 RED"] and resultado_vencedor in ["🟢 GREEN", "🔴 RED"]:
                        atualizar_estatisticas(resultado_total, resultado_vencedor)
                    
                    alertas[alerta_id]["conferido"] = True
                    
                    # NOVO: Envia alerta individual
                    if enviar_alerta_individual_resultado(alerta_id, alertas[alerta_id]):
                        st.success("✅ Conferido e alerta enviado!")
                    else:
                        st.error("✅ Conferido, mas erro no alerta.")
                    
                    salvar_alertas(alertas)
                    st.rerun()
            else:
                st.success("✅ Conferido")
                # NOVO: Botão para reenviar alerta individual
                if st.button("📤 Reenviar Alerta", key=f"alert_{alerta_id}"):
                    if enviar_alerta_individual_resultado(alerta_id, alerta):
                        st.success("✅ Alerta reenviado!")
                    else:
                        st.error("❌ Erro ao reenviar alerta.")
        
        st.markdown("---")

# =============================
# FUNÇÕES DE ALERTA DE RESULTADOS (FALTANTES)
# =============================
def enviar_alerta_resultados_conferidos():
    """Envia alerta com resumo dos resultados conferidos (Green/Red)"""
    alertas = carregar_alertas()
    
    # Filtra apenas jogos conferidos
    jogos_conferidos = []
    for alerta_id, alerta in alertas.items():
        if alerta.get("conferido", False) and not alerta.get("alerta_resultado_enviado", False):
            jogos_conferidos.append((alerta_id, alerta))
    
    if not jogos_conferidos:
        st.info("ℹ️ Nenhum jogo conferido novo para alerta.")
        return 0
    
    st.info(f"📤 Preparando alerta para {len(jogos_conferidos)} jogos conferidos...")
    
    # Constroi mensagem consolidada
    mensagem = f"🏀 <b>RESULTADOS CONFERIDOS - {datetime.now().strftime('%d/%m/%Y')}</b>\n\n"
    mensagem += "📊 <i>Resumo dos jogos analisados</i>\n\n"
    
    greens_total = 0
    greens_vencedor = 0
    total_jogos = len(jogos_conferidos)
    
    for alerta_id, alerta in jogos_conferidos:
        game_data = alerta.get("game_data", {})
        predictions = alerta.get("predictions", {})
        
        home_team = game_data.get("home_team", {}).get("full_name", "Casa")
        away_team = game_data.get("visitor_team", {}).get("full_name", "Visitante")
        home_score = game_data.get("home_team_score", 0)
        away_score = game_data.get("visitor_team_score", 0)
        
        total_pontos = home_score + away_score
        
        # Determina resultado do Total
        total_pred = predictions.get("total", {})
        tendencia_total = total_pred.get("tendencia", "")
        resultado_total = "⚪ INDEFINIDO"
        
        if "Mais" in tendencia_total:
            try:
                limite = float(tendencia_total.split()[-1])
                resultado_total = "🟢 GREEN" if total_pontos > limite else "🔴 RED"
                if resultado_total == "🟢 GREEN":
                    greens_total += 1
            except:
                resultado_total = "⚪ INDEFINIDO"
        elif "Menos" in tendencia_total:
            try:
                limite = float(tendencia_total.split()[-1])
                resultado_total = "🟢 GREEN" if total_pontos < limite else "🔴 RED"
                if resultado_total == "🟢 GREEN":
                    greens_total += 1
            except:
                resultado_total = "⚪ INDEFINIDO"
        
        # Determina resultado do Vencedor
        vencedor_pred = predictions.get("vencedor", {})
        vencedor_previsto = vencedor_pred.get("vencedor", "")
        resultado_vencedor = "⚪ INDEFINIDO"
        
        if vencedor_previsto == "Casa" and home_score > away_score:
            resultado_vencedor = "🟢 GREEN"
            greens_vencedor += 1
        elif vencedor_previsto == "Visitante" and away_score > home_score:
            resultado_vencedor = "🟢 GREEN"
            greens_vencedor += 1
        elif vencedor_previsto == "Empate" and home_score == away_score:
            resultado_vencedor = "🟢 GREEN"
            greens_vencedor += 1
        elif vencedor_previsto in ["Casa", "Visitante", "Empate"]:
            resultado_vencedor = "🔴 RED"
        
        # Adiciona jogo à mensagem
        mensagem += f"🏟️ <b>{home_team} vs {away_team}</b>\n"
        mensagem += f"   📊 Placar: <b>{home_score} x {away_score}</b>\n"
        mensagem += f"   🏀 Total: {total_pontos} pts | Previsão: {tendencia_total} | <b>{resultado_total}</b>\n"
        mensagem += f"   🎯 Vencedor: Previsão: {vencedor_previsto} | <b>{resultado_vencedor}</b>\n\n"
        
        # Marca como alerta enviado
        alertas[alerta_id]["alerta_resultado_enviado"] = True
    
    # Adiciona resumo final
    mensagem += "📈 <b>RESUMO FINAL</b>\n"
    mensagem += f"✅ <b>Total de Pontos:</b> {greens_total}/{total_jogos} Greens\n"
    mensagem += f"✅ <b>Vencedor:</b> {greens_vencedor}/{total_jogos} Greens\n"
    
    taxa_acerto_total = (greens_total / total_jogos) * 100 if total_jogos > 0 else 0
    taxa_acerto_vencedor = (greens_vencedor / total_jogos) * 100 if total_jogos > 0 else 0
    taxa_geral = ((greens_total + greens_vencedor) / (total_jogos * 2)) * 100 if total_jogos > 0 else 0
    
    mensagem += f"🎯 <b>Taxa de Acerto:</b>\n"
    mensagem += f"   📊 Total: {taxa_acerto_total:.1f}%\n"
    mensagem += f"   🏆 Vencedor: {taxa_acerto_vencedor:.1f}%\n"
    mensagem += f"   ⭐ Geral: {taxa_geral:.1f}%\n\n"
    
    mensagem += "🏆 <b>Elite Master - Resultados Conferidos</b>"
    
    # Envia para o canal alternativo
    if enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2):
        # Salva as alterações nos alertas
        salvar_alertas(alertas)
        st.success(f"✅ Alerta de resultados enviado! {total_jogos} jogos conferidos.")
        return total_jogos
    else:
        st.error("❌ Erro ao enviar alerta de resultados.")
        return 0

def enviar_alerta_individual_resultado(alerta_id: str, alerta: dict):
    """Envia alerta individual para um jogo conferido"""
    game_data = alerta.get("game_data", {})
    predictions = alerta.get("predictions", {})
    
    home_team = game_data.get("home_team", {}).get("full_name", "Casa")
    away_team = game_data.get("visitor_team", {}).get("full_name", "Visitante")
    home_score = game_data.get("home_team_score", 0)
    away_score = game_data.get("visitor_team_score", 0)
    
    total_pontos = home_score + away_score
    
    # Determina resultado do Total
    total_pred = predictions.get("total", {})
    tendencia_total = total_pred.get("tendencia", "")
    resultado_total = "⚪ INDEFINIDO"
    
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
    resultado_vencedor = "⚪ INDEFINIDO"
    
    if vencedor_previsto == "Casa" and home_score > away_score:
        resultado_vencedor = "🟢 GREEN"
    elif vencedor_previsto == "Visitante" and away_score > home_score:
        resultado_vencedor = "🟢 GREEN"
    elif vencedor_previsto == "Empate" and home_score == away_score:
        resultado_vencedor = "🟢 GREEN"
    elif vencedor_previsto in ["Casa", "Visitante", "Empate"]:
        resultado_vencedor = "🔴 RED"
    
    # Constroi mensagem individual
    mensagem = f"🏀 <b>RESULTADO INDIVIDUAL</b>\n\n"
    mensagem += f"🏟️ <b>{home_team} vs {away_team}</b>\n"
    mensagem += f"📊 Placar: <b>{home_score} x {away_score}</b>\n"
    mensagem += f"🏀 Total de Pontos: <b>{total_pontos}</b>\n\n"
    
    mensagem += f"📈 <b>Total de Pontos</b>\n"
    mensagem += f"   Previsão: {tendencia_total}\n"
    mensagem += f"   Resultado: <b>{resultado_total}</b>\n\n"
    
    mensagem += f"🎯 <b>Vencedor</b>\n"
    mensagem += f"   Previsão: {vencedor_previsto}\n"
    mensagem += f"   Resultado: <b>{resultado_vencedor}</b>\n\n"
    
    mensagem += "🏆 <b>Elite Master - Resultado Individual</b>"
    
    # Envia para o canal alternativo
    if enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2):
        return True
    else:
        return False

# =============================
# SISTEMA TOP 4 MELHORES JOGOS
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
# INTERFACE STREAMLIT
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
    
    # NOVO: Botão para limpar estatísticas
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Estatísticas")
    
    if st.sidebar.button("🧹 Limpar Estatísticas", type="secondary"):
        limpar_estatisticas()
        st.sidebar.success("✅ Estatísticas limpas!")
        st.rerun()

    # NOVO: Botão para alertas de resultados na sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 Alertas de Resultados")
    
    if st.sidebar.button("📤 Enviar Alerta de Resultados", type="secondary"):
        with st.spinner("Enviando alerta de resultados conferidos..."):
            jogos_alertados = enviar_alerta_resultados_conferidos()
            if jogos_alertados > 0:
                st.sidebar.success(f"✅ Alerta para {jogos_alertados} jogos!")
            else:
                st.sidebar.info("ℹ️ Nenhum jogo novo para alerta.")
    
    # NOVO: Aba de estatísticas
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 Análise", "📊 Jogos Analisados", "✅ Conferência", "📈 Estatísticas", "🧪 Teste"])
    
    with tab1:
        exibir_aba_analise()
    
    with tab2:
        exibir_jogos_analisados()
    
    with tab3:
        conferir_resultados()
    
    with tab4:
        exibir_estatisticas()
    
    with tab5:
        testar_envio_imagem()

def exibir_aba_analise():
    st.header("🎯 Análise com Dados Reais 2024-2025")
    
    with st.sidebar:
        st.subheader("Controles de Análise")
        top_n = st.slider("Número de jogos para analisar", 1, 15, 5)
        janela = st.slider("Jogos recentes para análise", 2, 20, 15)
        enviar_auto = st.checkbox("Enviar alertas automaticamente para Telegram", value=True)
        com_imagem = st.checkbox("Enviar alertas com imagem", value=True)  # NOVO: opção de imagem
        
        st.markdown("---")
        st.subheader("Gerenciamento")
        if st.button("🧹 Limpar Cache", type="secondary"):
            for f in [CACHE_GAMES, CACHE_STATS, ALERTAS_PATH]:
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
            analisar_jogos_com_dados_2025(data_sel, top_n, janela, enviar_auto, com_imagem)
    with col3:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar Dados", type="secondary"):
            st.rerun()

def analisar_jogos_com_dados_2025(data_sel: date, top_n: int, janela: int, enviar_auto: bool, com_imagem: bool):
    data_str = data_sel.strftime("%Y-%m-%d")
    
    progress_placeholder = st.empty()
    results_placeholder = st.empty()
    
    with progress_placeholder:
        st.info(f"🔍 Buscando dados reais para {data_sel.strftime('%d/%m/%Y')}...")
        st.success("📊 Analisando com dados da temporada 2024-2025")
        if enviar_auto:
            st.warning("📤 Alertas serão enviados para Telegram")
            if com_imagem:
                st.info("🖼️ Alertas incluirão imagens com escudos")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Busca jogos
    jogos = obter_jogos_data(data_str)
    
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
                
                # Exibe preview da imagem
                with st.expander(f"🖼️ Preview Alerta: {away_team} @ {home_team}", expanded=False):
                    visualizar_imagem_alerta(jogo, predictions)
                
                # Envia alerta
                enviado = verificar_e_enviar_alerta(jogo, predictions, enviar_auto, com_imagem)
                if enviado and enviar_auto:
                    alertas_enviados += 1
                
                # Exibe resultado
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{home_team}** vs **{away_team}**")
                    st.write(f"📍 **Status:** {jogo.get('status', 'SCHEDULED')}")
                
                with col2:
                    st.write(f"📊 **Total:** {total_tend}")
                    st.write(f"🎯 **Vencedor:** {vencedor}")
                    st.write(f"💪 **Confiança:** {vencedor_conf}%")
                
                with col3:
                    st.write(f"📈 **Estimativa:** {total_estim:.1f}")
                    st.write(f"🔒 **Confiança:** {total_conf}%")
                    if enviado and enviar_auto:
                        if com_imagem:
                            st.success("✅ Telegram + Imagem")
                        else:
                            st.success("✅ Telegram")
                    else:
                        st.info("💾 Salvo")
                
                st.markdown("---")
                
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
    - 📤 {alertas_enviados} alertas enviados para Telegram
    - 🖼️ {'Com imagens' if com_imagem else 'Apenas texto'}
    - 📈 Estatísticas baseadas na temporada atual
    - 💾 Dados salvos para conferência futura
    """)

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if __name__ == "__main__":
    main()
