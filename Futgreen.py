import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
ALERTAS_AMBAS_MARCAM_PATH = "alertas_ambas_marcam.json"
ALERTAS_CARTOES_PATH = "alertas_cartoes.json"
ALERTAS_ESCANTEIOS_PATH = "alertas_escanteios.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# Histórico de conferências
HISTORICO_PATH = "historico_conferencias.json"
HISTORICO_AMBAS_MARCAM_PATH = "historico_ambas_marcam.json"
HISTORICO_CARTOES_PATH = "historico_cartoes.json"
HISTORICO_ESCANTEIOS_PATH = "historico_escanteios.json"

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
# Utilitários de Cache e Persistência - EXPANDIDOS
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
                agora = datetime.now().timestamp()
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                        return {}
                else:
                    if agora - os.path.getmtime(caminho) > CACHE_TIMEOUT:
                        return {}
            return dados
    except (json.JSONDecodeError, IOError) as e:
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
        st.error(f"Erro ao salvar {caminho}: {e}")

# Funções para alertas das novas previsões
def carregar_alertas_ambas_marcam() -> dict:
    return carregar_json(ALERTAS_AMBAS_MARCAM_PATH)

def salvar_alertas_ambas_marcam(alertas: dict):
    salvar_json(ALERTAS_AMBAS_MARCAM_PATH, alertas)

def carregar_alertas_cartoes() -> dict:
    return carregar_json(ALERTAS_CARTOES_PATH)

def salvar_alertas_cartoes(alertas: dict):
    salvar_json(ALERTAS_CARTOES_PATH, alertas)

def carregar_alertas_escanteios() -> dict:
    return carregar_json(ALERTAS_ESCANTEIOS_PATH)

def salvar_alertas_escanteios(alertas: dict):
    salvar_json(ALERTAS_ESCANTEIOS_PATH, alertas)

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
# Histórico de Conferências - EXPANDIDO
# =============================
def carregar_historico(caminho: str = HISTORICO_PATH) -> list:
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_historico(historico: list, caminho: str = HISTORICO_PATH):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar histórico {caminho}: {e}")

def registrar_no_historico(resultado: dict, tipo: str = "gols"):
    """Registra no histórico específico para cada tipo de previsão"""
    if not resultado:
        return
        
    caminhos_historico = {
        "gols": HISTORICO_PATH,
        "ambas_marcam": HISTORICO_AMBAS_MARCAM_PATH,
        "cartoes": HISTORICO_CARTOES_PATH,
        "escanteios": HISTORICO_ESCANTEIOS_PATH
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
    
    historico.append(registro)
    salvar_historico(historico, caminho)

def limpar_historico(tipo: str = "todos"):
    """Faz backup e limpa histórico específico ou todos"""
    caminhos = {
        "gols": HISTORICO_PATH,
        "ambas_marcam": HISTORICO_AMBAS_MARCAM_PATH,
        "cartoes": HISTORICO_CARTOES_PATH,
        "escanteios": HISTORICO_ESCANTEIOS_PATH
    }
    
    if tipo == "todos":
        historicos_limpos = 0
        for nome, caminho in caminhos.items():
            if os.path.exists(caminho):
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"historico_{nome}_backup_{ts}.json"
                    with open(caminho, "rb") as f_src:
                        with open(backup_name, "wb") as f_bak:
                            f_bak.write(f_src.read())
                    os.remove(caminho)
                    historicos_limpos += 1
                except Exception as e:
                    st.error(f"Erro ao limpar {nome}: {e}")
        st.success(f"🧹 Todos os históricos limpos. {historicos_limpos} backups criados.")
    else:
        caminho = caminhos.get(tipo)
        if caminho and os.path.exists(caminho):
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"historico_{tipo}_backup_{ts}.json"
                with open(caminho, "rb") as f_src:
                    with open(backup_name, "wb") as f_bak:
                        f_bak.write(f_src.read())
                os.remove(caminho)
                st.success(f"🧹 Histórico {tipo} limpo. Backup: {backup_name}")
            except Exception as e:
                st.error(f"Erro ao limpar histórico {tipo}: {e}")
        else:
            st.info(f"⚠️ Nenhum histórico encontrado para {tipo}")

# =============================
# Utilitários de Data e Formatação
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except ValueError:
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

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
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
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

# =============================
# NOVAS FUNÇÕES DE PREVISÃO
# =============================

def calcular_previsao_ambas_marcam(home: str, away: str, classificacao: dict, estatisticas_time: dict) -> tuple[float, float, str]:
    """
    Previsão: Ambas as equipes marcam
    Base: histórico de gols feitos/sofridos e força ofensiva
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

def calcular_previsao_cartoes(home: str, away: str, estatisticas_time: dict) -> tuple[float, float, str]:
    """
    Previsão: Total de cartões no jogo
    Base: histórico de cartões dos times e natureza do confronto
    """
    # Em uma implementação real, usaria estatísticas de cartões por time
    # Por enquanto, uso uma simulação baseada no desempenho ofensivo/defensivo
    
    dados_home = estatisticas_time.get(home, {"cartoes_media": 2.5, "cartoes_var": 1.2})
    dados_away = estatisticas_time.get(away, {"cartoes_media": 2.3, "cartoes_var": 1.1})
    
    media_cartoes_home = dados_home.get("cartoes_media", 2.5)
    media_cartoes_away = dados_away.get("cartoes_media", 2.3)
    
    # Total estimado de cartões
    total_estimado = media_cartoes_home + media_cartoes_away
    
    # Fator de intensidade do jogo (derbys, jogos decisivos têm mais cartões)
    fator_intensidade = 1.0  # Base, poderia ser ajustado por tipo de competição
    
    total_ajustado = total_estimado * fator_intensidade
    
    # Calcular confiança baseada na variabilidade
    var_home = dados_home.get("cartoes_var", 1.2)
    var_away = dados_away.get("cartoes_var", 1.1)
    consistencia = 1.0 - ((var_home + var_away) / 10)  # Quanto menor variância, maior confiança
    
    confianca = min(90, 50 + (total_ajustado * 5 * consistencia))
    
    # Definir tendências
    if total_ajustado >= 5.5:
        tendencia = f"Mais {int(total_ajustado)}.5 Cartões"
        confianca = min(95, confianca + 5)
    elif total_ajustado >= 4.0:
        tendencia = f"Mais {int(total_ajustado)}.5 Cartões"
    else:
        tendencia = f"Menos {int(total_ajustado) + 1}.5 Cartões"
        confianca = max(40, confianca - 5)
    
    return total_ajustado, confianca, tendencia

def calcular_previsao_escanteios(home: str, away: str, estatisticas_time: dict) -> tuple[float, float, str]:
    """
    Previsão: Total de escanteios no jogo
    Base: histórico de escanteios e estilo de jogo ofensivo
    """
    dados_home = estatisticas_time.get(home, {"escanteios_media": 5.5, "escanteios_var": 2.1})
    dados_away = estatisticas_time.get(away, {"escanteios_media": 5.0, "escanteios_var": 1.8})
    
    media_escanteios_home = dados_home.get("escanteios_media", 5.5)
    media_escanteios_away = dados_away.get("escanteios_media", 5.0)
    
    # Total estimado de escanteios
    total_estimado = media_escanteios_home + media_escanteios_away
    
    # Fator ofensivo (times que atacam mais têm mais escanteios)
    fator_ofensivo = 1.1  # Poderia ser calculado baseado em finalizações/gols
    
    total_ajustado = total_estimado * fator_ofensivo
    
    # Calcular confiança
    var_home = dados_home.get("escanteios_var", 2.1)
    var_away = dados_away.get("escanteios_var", 1.8)
    consistencia = 1.0 - ((var_home + var_away) / 15)
    
    confianca = min(85, 45 + (total_ajustado * 4 * consistencia))
    
    # Definir tendências
    if total_ajustado >= 9.5:
        tendencia = f"Mais {int(total_ajustado)}.5 Escanteios"
        confianca = min(90, confianca + 5)
    elif total_ajustado >= 7.0:
        tendencia = f"Mais {int(total_ajustado)}.5 Escanteios"
    else:
        tendencia = f"Menos {int(total_ajustado) + 1}.5 Escanteios"
        confianca = max(35, confianca - 5)
    
    return total_ajustado, confianca, tendencia

def obter_estatisticas_time(time: str, liga_id: str) -> dict:
    """
    Obtém estatísticas detalhadas do time (cartões, escanteios, etc.)
    Em produção, isso viria da API com estatísticas detalhadas
    """
    # Placeholder - em implementação real, buscar da API
    return {
        "cartoes_media": 2.5 + (hash(time) % 100) / 100,  # Simulação
        "cartoes_var": 1.0 + (hash(time) % 50) / 100,
        "escanteios_media": 5.0 + (hash(time) % 150) / 100,
        "escanteios_var": 1.5 + (hash(time) % 80) / 100
    }

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
    """Envia alerta individual para Ambas Marcam"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
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
    """Envia alerta individual para Cartões"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
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
    """Envia alerta individual para Escanteios"""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
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
# SISTEMA DE CONFERÊNCIA PARA NOVAS PREVISÕES
# =============================

def verificar_resultados_ambas_marcam(alerta_resultados: bool):
    """Verifica resultados para previsão Ambas Marcam"""
    alertas = carregar_alertas_ambas_marcam()
    if not alertas:
        return
    
    resultados_enviados = 0
    jogos_com_resultado = []
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture = obter_dados_api(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            score = fixture.get("score", {}).get("fullTime", {})
            home_goals = score.get("home", 0)
            away_goals = score.get("away", 0)
            
            if status == "FINISHED" and home_goals is not None and away_goals is not None:
                ambas_marcaram = home_goals > 0 and away_goals > 0
                previsao_correta = ("SIM" in alerta["tendencia"] and ambas_marcaram) or ("NÃO" in alerta["tendencia"] and not ambas_marcaram)
                
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
                    "escudo_home": fixture.get("homeTeam", {}).get("crest", ""),
                    "escudo_away": fixture.get("awayTeam", {}).get("crest", "")
                }
                
                jogos_com_resultado.append(jogo_resultado)
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar ambas marcam {fixture_id}: {e}")
    
    if jogos_com_resultado and alerta_resultados:
        enviar_alerta_resultados_ambas_marcam(jogos_com_resultado)
        salvar_alertas_ambas_marcam(alertas)
        st.success(f"✅ {resultados_enviados} resultados Ambas Marcam processados!")

def verificar_resultados_cartoes(alerta_resultados: bool):
    """Verifica resultados para previsão de Cartões"""
    alertas = carregar_alertas_cartoes()
    if not alertas:
        return
    
    resultados_enviados = 0
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture = obter_dados_api(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            
            if status == "FINISHED":
                # Em implementação real, buscar dados de cartões da API
                # Por enquanto, simulamos um resultado
                cartoes_total = 4  # Simulação
                limiar = float(alerta["tendencia"].split(" ")[1].replace(".5", ""))
                
                if "Mais" in alerta["tendencia"]:
                    previsao_correta = cartoes_total > limiar
                else:
                    previsao_correta = cartoes_total < limiar
                
                # Registrar no histórico
                registrar_no_historico({
                    "home": fixture["homeTeam"]["name"],
                    "away": fixture["awayTeam"]["name"],
                    "tendencia": alerta["tendencia"],
                    "estimativa": alerta["estimativa"],
                    "confianca": alerta["confianca"],
                    "placar": "Conferido",
                    "resultado": "🟢 GREEN" if previsao_correta else "🔴 RED",
                    "cartoes_total": cartoes_total,
                    "limiar_cartoes": limiar
                }, "cartoes")
                
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar cartões {fixture_id}: {e}")
    
    if resultados_enviados > 0:
        salvar_alertas_cartoes(alertas)
        st.success(f"✅ {resultados_enviados} resultados Cartões processados!")

def verificar_resultados_escanteios(alerta_resultados: bool):
    """Verifica resultados para previsão de Escanteios"""
    alertas = carregar_alertas_escanteios()
    if not alertas:
        return
    
    resultados_enviados = 0
    
    for fixture_id, alerta in list(alertas.items()):
        if alerta.get("conferido", False):
            continue
            
        try:
            url = f"{BASE_URL_FD}/matches/{fixture_id}"
            fixture = obter_dados_api(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            
            if status == "FINISHED":
                # Em implementação real, buscar dados de escanteios da API
                # Por enquanto, simulamos um resultado
                escanteios_total = 8  # Simulação
                limiar = float(alerta["tendencia"].split(" ")[1].replace(".5", ""))
                
                if "Mais" in alerta["tendencia"]:
                    previsao_correta = escanteios_total > limiar
                else:
                    previsao_correta = escanteios_total < limiar
                
                # Registrar no histórico
                registrar_no_historico({
                    "home": fixture["homeTeam"]["name"],
                    "away": fixture["awayTeam"]["name"],
                    "tendencia": alerta["tendencia"],
                    "estimativa": alerta["estimativa"],
                    "confianca": alerta["confianca"],
                    "placar": "Conferido",
                    "resultado": "🟢 GREEN" if previsao_correta else "🔴 RED",
                    "escanteios_total": escanteios_total,
                    "limiar_escanteios": limiar
                }, "escanteios")
                
                alerta["conferido"] = True
                resultados_enviados += 1
                
        except Exception as e:
            st.error(f"Erro ao verificar escanteios {fixture_id}: {e}")
    
    if resultados_enviados > 0:
        salvar_alertas_escanteios(alertas)
        st.success(f"✅ {resultados_enviados} resultados Escanteios processados!")

def enviar_alerta_resultados_ambas_marcam(jogos_com_resultado: list):
    """Envia alerta de resultados para Ambas Marcam"""
    if not jogos_com_resultado:
        return
        
    try:
        msg = "<b>🏁 RESULTADOS AMBAS MARCAM</b>\n\n"
        
        for jogo in jogos_com_resultado:
            resultado = "🟢 GREEN" if jogo["previsao_correta"] else "🔴 RED"
            ambas_text = "SIM" if jogo["ambas_marcaram"] else "NÃO"
            
            msg += (
                f"<b>{resultado}</b> {jogo['home']} {jogo['home_goals']}x{jogo['away_goals']} {jogo['away']}\n"
                f"Previsão: {jogo['previsao']} | Real: {ambas_text}\n"
                f"Conf: {jogo['confianca_prevista']:.0f}%\n\n"
            )
        
        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
        
        # Registrar no histórico
        for jogo in jogos_com_resultado:
            registrar_no_historico({
                "home": jogo["home"],
                "away": jogo["away"],
                "tendencia": jogo["previsao"],
                "estimativa": jogo["probabilidade_prevista"],
                "confianca": jogo["confianca_prevista"],
                "placar": f"{jogo['home_goals']}x{jogo['away_goals']}",
                "resultado": "🟢 GREEN" if jogo["previsao_correta"] else "🔴 RED",
                "previsao": jogo["previsao"],
                "ambas_marcaram": jogo["ambas_marcaram"]
            }, "ambas_marcam")
            
    except Exception as e:
        st.error(f"Erro ao enviar resultados ambas marcam: {e}")

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
# SISTEMA DE ALERTAS DE RESULTADOS COM POSTERS RED/GREEN
# =============================

def verificar_resultados_finais(alerta_resultados: bool):
    """Verifica resultados finais dos jogos e envia alertas"""
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
            fixture = obter_dados_api(url)
            
            if not fixture:
                continue
                
            status = fixture.get("status", "")
            score = fixture.get("score", {}).get("fullTime", {})
            home_goals = score.get("home")
            away_goals = score.get("away")
            
            # Verificar se jogo terminou e tem resultado
            if status == "FINISHED" and home_goals is not None and away_goals is not None:
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
                    "escudo_home": fixture.get("homeTeam", {}).get("crest") or fixture.get("homeTeam", {}).get("logo", ""),
                    "escudo_away": fixture.get("awayTeam", {}).get("crest") or fixture.get("awayTeam", {}).get("logo", "")
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

def gerar_poster_resultados(jogos: list, titulo: str = "ELITE MASTER - RESULTADOS OFICIAIS") -> io.BytesIO:
    """
    Gera poster profissional com resultados finais dos jogos - VERSÃO CORRIGIDA COM RED/GREEN
    """
    # Configurações do poster
    LARGURA = 2400
    ALTURA_TOPO = 400
    ALTURA_POR_JOGO = 950  # Ajustado para melhor layout
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
    
    st.success(f"✅ Poster de resultados GERADO com {len(jogos)} jogos - Sistema RED/GREEN")
    return buffer

def enviar_alerta_resultados_poster(jogos_com_resultado: list):
    """Envia alerta de resultados com poster para o Telegram - VERSÃO ATUALIZADA COM RED/GREEN"""
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
    """Tenta baixar uma imagem e retornar PIL.Image. Retorna None se falhar."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except Exception as e:
        print(f"Erro ao baixar imagem {url}: {e}")
        return None

def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
    """Cria fonte com fallback robusto"""
    try:
        # Tentar fontes comuns em diferentes sistemas
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
        
        # Se não encontrou nenhuma fonte, criar uma bitmap
        return ImageFont.load_default()
        
    except Exception as e:
        print(f"Erro ao carregar fonte: {e}")
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
                print(f"[ERRO ESCUDO] {e}")
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
    
    st.success(f"✅ Poster estilo West Ham GERADO com {len(jogos)} jogos")
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
            
            st.info(f"🎨 Gerando poster para {data_str} com {len(jogos_data)} jogos...")
            
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
        st.error(f"❌ Erro crítico ao gerar/enviar poster: {str(e)}")
        # Fallback para mensagem de texto
        msg = f"🔥 Jogos ≥{threshold}% (Erro na imagem):\n"
        for j in jogos_conf[:5]:
            msg += f"🏟️ {j['home']} vs {j['away']} | {j['tendencia']} | Conf: {j['confianca']:.0f}%\n"
        enviar_telegram(msg, chat_id=chat_id)

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
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                arquivos_limpos += 1
        st.success(f"✅ {arquivos_limpos} caches limpos com sucesso!")
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
# Interface Streamlit ATUALIZADA
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols")

    # Sidebar - CONFIGURAÇÕES DE ALERTAS EXPANDIDAS
    with st.sidebar:
        st.header("🔔 Configurações de Alertas")
        
        # Checkboxes para cada tipo de alerta - ORIGINAIS
        alerta_individual = st.checkbox("🎯 Alertas Individuais Gols", value=True)
        alerta_poster = st.checkbox("📊 Alertas com Poster Gols", value=True)
        alerta_top_jogos = st.checkbox("🏆 Top Jogos Gols", value=True)
        alerta_resultados = st.checkbox("🏁 Resultados Finais Gols", value=True)
        
        st.markdown("---")
        st.subheader("🆕 Novas Previsões")
        
        # Checkboxes para NOVAS PREVISÕES
        alerta_ambas_marcam = st.checkbox("⚽ Ambas Marcam", value=True,
                                         help="Alertas para previsão Ambas Marcam")
        alerta_cartoes = st.checkbox("🟨 Total de Cartões", value=True,
                                    help="Alertas para previsão de Cartões")
        alerta_escanteios = st.checkbox("🔄 Total de Escanteios", value=True,
                                       help="Alertas para previsão de Escanteios")
        
        alerta_resultados_ambas_marcam = st.checkbox("🏁 Resultados Ambas Marcam", value=True)
        alerta_resultados_cartoes = st.checkbox("🏁 Resultados Cartões", value=True)
        alerta_resultados_escanteios = st.checkbox("🏁 Resultados Escanteios", value=True)
        
        st.markdown("----")
        
        st.header("Configurações Gerais")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        threshold = st.slider("Limiar confiança Gols (%)", 50, 95, 70, 1)
        threshold_ambas_marcam = st.slider("Limiar Ambas Marcam (%)", 50, 95, 60, 1)
        threshold_cartoes = st.slider("Limiar Cartões (%)", 45, 90, 55, 1)
        threshold_escanteios = st.slider("Limiar Escanteios (%)", 40, 85, 50, 1)
        
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

    # Processamento
    if st.button("🔍 Buscar Partidas", type="primary"):
        processar_jogos_completo(data_selecionada, todas_ligas, liga_selecionada, top_n, 
                               threshold, threshold_ambas_marcam, threshold_cartoes, threshold_escanteios,
                               estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                               alerta_ambas_marcam, alerta_cartoes, alerta_escanteios)

    # Ações - EXPANDIDAS COM NOVAS PREVISÕES
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔄 Atualizar Status"):
            atualizar_status_partidas()
    with col2:
        if st.button("📊 Conferir Resultados"):
            conferir_resultados()
    with col3:
        if st.button("🏁 Verificar Todos Resultados", type="secondary"):
            verificar_resultados_finais(alerta_resultados)
            if alerta_resultados_ambas_marcam:
                verificar_resultados_ambas_marcam(alerta_resultados_ambas_marcam)
            if alerta_resultados_cartoes:
                verificar_resultados_cartoes(alerta_resultados_cartoes)
            if alerta_resultados_escanteios:
                verificar_resultados_escanteios(alerta_resultados_escanteios)
    with col4:
        if st.button("🧹 Limpar Cache"):
            limpar_caches()

    # Painel desempenho EXPANDIDO
    st.markdown("---")
    st.subheader("📊 Painel de Desempenho Completo")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        if st.button("📈 Desempenho Gols"):
            calcular_desempenho()
    with col_d2:
        if st.button("📈 Desempenho Ambas Marcam"):
            calcular_desempenho_ambas_marcam()
    with col_d3:
        if st.button("📈 Desempenho Cartões"):
            calcular_desempenho_cartoes()
    
    col_d4, col_d5, col_d6 = st.columns(3)
    with col_d4:
        if st.button("📈 Desempenho Escanteios"):
            calcular_desempenho_escanteios()
    with col_d5:
        if st.button("🧹 Limpar Histórico Gols"):
            limpar_historico("gols")
    with col_d6:
        if st.button("🧹 Limpar Todos Históricos"):
            limpar_historico("todos")

def processar_jogos_completo(data_selecionada, todas_ligas, liga_selecionada, top_n, 
                           threshold, threshold_ambas_marcam, threshold_cartoes, threshold_escanteios,
                           estilo_poster, alerta_individual, alerta_poster, alerta_top_jogos,
                           alerta_ambas_marcam, alerta_cartoes, alerta_escanteios):
    """Processamento completo incluindo todas as previsões"""
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
    
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
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            
            # PREVISÃO ORIGINAL - GOLS
            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)
            verificar_enviar_alerta(match, tendencia, estimativa, confianca, alerta_individual)

            # NOVAS PREVISÕES
            estatisticas = obter_estatisticas_time(home, liga_id)
            
            # Ambas Marcam
            if alerta_ambas_marcam:
                prob_ambas, conf_ambas, tend_ambas = calcular_previsao_ambas_marcam(home, away, classificacao, estatisticas)
                if conf_ambas >= threshold_ambas_marcam:
                    verificar_enviar_alerta_ambas_marcam(match, prob_ambas, conf_ambas, tend_ambas, alerta_ambas_marcam)
                    top_jogos_ambas_marcam.append({
                        "home": home, "away": away, "probabilidade": prob_ambas,
                        "confianca": conf_ambas, "tendencia": tend_ambas,
                        "liga": match.get("competition", {}).get("name", "Desconhecido"),
                        "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3)
                    })

            # Cartões
            if alerta_cartoes:
                est_cartoes, conf_cartoes, tend_cartoes = calcular_previsao_cartoes(home, away, estatisticas)
                if conf_cartoes >= threshold_cartoes:
                    verificar_enviar_alerta_cartoes(match, est_cartoes, conf_cartoes, tend_cartoes, alerta_cartoes)
                    top_jogos_cartoes.append({
                        "home": home, "away": away, "estimativa": est_cartoes,
                        "confianca": conf_cartoes, "tendencia": tend_cartoes,
                        "liga": match.get("competition", {}).get("name", "Desconhecido"),
                        "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3)
                    })

            # Escanteios
            if alerta_escanteios:
                est_escanteios, conf_escanteios, tend_escanteios = calcular_previsao_escanteios(home, away, estatisticas)
                if conf_escanteios >= threshold_escanteios:
                    verificar_enviar_alerta_escanteios(match, est_escanteios, conf_escanteios, tend_escanteios, alerta_escanteios)
                    top_jogos_escanteios.append({
                        "home": home, "away": away, "estimativa": est_escanteios,
                        "confianca": conf_escanteios, "tendencia": tend_escanteios,
                        "liga": match.get("competition", {}).get("name", "Desconhecido"),
                        "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3)
                    })

            # Dados para previsão original de gols
            escudo_home = match.get("homeTeam", {}).get("crest", "")
            escudo_away = match.get("awayTeam", {}).get("crest", "")
            
            top_jogos_gols.append({
                "id": match["id"],
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3),
                "status": match.get("status", "DESCONHECIDO"),
                "escudo_home": escudo_home,
                "escudo_away": escudo_away
            })
        
        progress_bar.progress((i + 1) / total_ligas)

    # Resultados
    st.success("✅ Processamento completo concluído!")
    
    # Mostrar estatísticas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Jogos Gols", len([j for j in top_jogos_gols if j["confianca"] >= threshold]))
    with col2:
        st.metric("Jogos Ambas Marcam", len(top_jogos_ambas_marcam))
    with col3:
        st.metric("Jogos Cartões", len(top_jogos_cartoes))
    with col4:
        st.metric("Jogos Escanteios", len(top_jogos_escanteios))

    # Enviar alertas específicos
    if alerta_top_jogos and top_jogos_gols:
        enviar_top_jogos([j for j in top_jogos_gols if j["confianca"] >= threshold], top_n, alerta_top_jogos)

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
        st.error(f"Erro no fallback: {e}")

if __name__ == "__main__":
    main()
