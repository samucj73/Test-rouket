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
    
    return enviir_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

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
    # Implementação similar à função acima, buscando dados de cartões da API
    # Por enquanto, placeholder
    pass

def verificar_resultados_escanteios(alerta_resultados: bool):
    """Verifica resultados para previsão de Escanteios"""
    # Implementação similar à função acima, buscando dados de escanteios da API
    # Por enquanto, placeholder
    pass

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
# ATUALIZAÇÃO DA INTERFACE STREAMLIT
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
            estatisticas = obter_estatisticas_time(home, liga_id)  # Placeholder - precisa implementar
            
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
# MANTENHA AS FUNÇÕES ORIGINAIS EXISTENTES (não alteradas)
# =============================

# [Todas as funções originais do seu código permanecem aqui...]
# formatar_data_iso, abreviar_nome, enviar_telegram, enviar_foto_telegram, 
# obter_dados_api, obter_classificacao, obter_jogos, calcular_tendencia,
# gerar_poster_individual_westham, enviar_alerta_telegram, 
# verificar_enviar_alerta, verificar_resultados_finais, gerar_poster_resultados,
# enviar_alerta_resultados_poster, baixar_imagem_url, criar_fonte,
# gerar_poster_westham_style, enviar_alerta_westham_style, enviar_top_jogos,
# atualizar_status_partidas, conferir_resultados, limpar_caches,
# calcular_desempenho, calcular_desempenho_periodo, processar_jogos

# ... [o restante do seu código original permanece inalterado]

if __name__ == "__main__":
    main()
