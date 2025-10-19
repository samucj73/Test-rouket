# ================================================
# ⚽ Soccer Elite Master - TheSportsDB API
# ================================================
import streamlit as st
import requests
import json
import os
import io
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import time
from typing import List, Dict, Optional
import re

# =============================
# Configurações e Constantes
# =============================
st.set_page_config(page_title="⚽ Soccer Elite Master", layout="wide")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Configurações TheSportsDB API
# =============================
THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "3")  # Chave premium ou 1,2,3 para free
THESPORTSDB_BASE_URL_V1 = "https://www.thesportsdb.com/api/v1/json"
THESPORTSDB_BASE_URL_V2 = "https://www.thesportsdb.com/api/v2/json"

# =============================
# Principais ligas (TheSportsDB)
# =============================
LIGAS_THESPORTSDB = {
    "Premier League (Inglaterra)": "4328",
    "La Liga (Espanha)": "4335", 
    "Serie A (Itália)": "4332",
    "Bundesliga (Alemanha)": "4331",
    "Ligue 1 (França)": "4334",
    "MLS (Estados Unidos)": "4346",
    "Brasileirão Série A": "4375",
    "Brasileirão Série B": "4376",
    "Liga MX (México)": "4347",
    "Copa Libertadores": "4480",
    "Champions League": "4480",
    "Europa League": "4481"
}

# Nomes das ligas para busca
LIGA_NAMES = {
    "4328": "English Premier League",
    "4335": "Spanish La Liga",
    "4332": "Italian Serie A",
    "4331": "German Bundesliga",
    "4334": "French Ligue 1",
    "4346": "MLS",
    "4375": "Campeonato Brasileiro Série A",
    "4376": "Campeonato Brasileiro Série B",
    "4347": "Liga MX",
    "4480": "UEFA Champions League",
    "4481": "UEFA Europa League"
}

# Cores e emojis para status
STATUS_CONFIG = {
    "Not Started": {"emoji": "⏰", "color": "#4A90E2", "desc": "Agendado"},
    "Live": {"emoji": "🔴", "color": "#E74C3C", "desc": "Ao Vivo"},
    "Half Time": {"emoji": "⏸️", "color": "#F39C12", "desc": "Intervalo"},
    "Finished": {"emoji": "✅", "color": "#27AE60", "desc": "Finalizado"},
    "Postponed": {"emoji": "🚫", "color": "#95A5A6", "desc": "Adiado"},
    "Cancelled": {"emoji": "❌", "color": "#7F8C8D", "desc": "Cancelado"},
    "Delayed": {"emoji": "⏳", "color": "#F39C12", "desc": "Atrasado"}
}

# =============================
# Inicialização do Session State
# =============================
def inicializar_session_state():
    """Inicializa todas as variáveis do session state"""
    if 'dados_carregados' not in st.session_state:
        st.session_state.dados_carregados = False
    if 'todas_partidas' not in st.session_state:
        st.session_state.todas_partidas = []
    if 'modo_exibicao' not in st.session_state:
        st.session_state.modo_exibicao = "liga"
    if 'ultima_busca' not in st.session_state:
        st.session_state.ultima_busca = None
    if 'ultimas_ligas' not in st.session_state:
        st.session_state.ultimas_ligas = []
    if 'busca_hoje' not in st.session_state:
        st.session_state.busca_hoje = False
    if 'data_ultima_busca' not in st.session_state:
        st.session_state.data_ultima_busca = None
    if 'filtros_liga' not in st.session_state:
        st.session_state.filtros_liga = {}
    if 'top_n' not in st.session_state:
        st.session_state.top_n = 5

# =============================
# Funções utilitárias
# =============================
def carregar_json(caminho: str) -> dict:
    """Carrega dados de arquivo JSON com tratamento de erros robusto"""
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            return dados
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Arquivo {caminho} corrompido. Criando novo.")
        try:
            if os.path.exists(caminho):
                backup_name = f"{caminho}.backup_{int(time.time())}"
                os.rename(caminho, backup_name)
        except:
            pass
        return {}
    except Exception as e:
        st.error(f"Erro ao carregar {caminho}: {str(e)}")
    return {}

def salvar_json(caminho: str, dados: dict):
    """Salva dados em arquivo JSON com tratamento de erros"""
    try:
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar {caminho}: {str(e)}")
        return False

def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    """Envia mensagem para o Telegram com tratamento de erros"""
    try:
        response = requests.post(
            BASE_URL_TG,
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Erro ao enviar para Telegram: {str(e)}")
        return False

def formatar_hora_brasilia(hora_utc: str) -> Optional[datetime]:
    """Converte hora UTC para horário de Brasília"""
    try:
        if not hora_utc:
            return None
        
        # TheSportsDB usa formato: 2024-01-15T19:30:00+00:00
        if 'T' in hora_utc:
            hora_dt = datetime.fromisoformat(hora_utc.replace('Z', '+00:00'))
        else:
            hora_dt = datetime.strptime(hora_utc, "%Y-%m-%d %H:%M:%S")
        
        hora_brasilia = hora_dt - timedelta(hours=3)
        return hora_brasilia
    except Exception:
        return None

def get_status_config(status: str) -> Dict:
    """Retorna configuração de cor e emoji para o status"""
    status_lower = status.lower()
    for key, config in STATUS_CONFIG.items():
        if key.lower() in status_lower:
            return config
    return {"emoji": "⚫", "color": "#95A5A6", "desc": status}

def is_datetime_valid(dt: Optional[datetime]) -> bool:
    """Verifica se um datetime é válido e não é muito antigo/futuro"""
    if not dt:
        return False
    try:
        return 1900 <= dt.year <= 2100
    except:
        return False

def safe_datetime_compare(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    """Comparação segura entre datetimes"""
    if not is_datetime_valid(dt1) or not is_datetime_valid(dt2):
        return False
    try:
        dt1_naive = dt1.replace(tzinfo=None) if dt1.tzinfo else dt1
        dt2_naive = dt2.replace(tzinfo=None) if dt2.tzinfo else dt2
        return dt1_naive > dt2_naive
    except:
        return False

def safe_datetime_range(dt: Optional[datetime], start: datetime, end: datetime) -> bool:
    """Verifica se um datetime está dentro de um range de forma segura"""
    if not is_datetime_valid(dt):
        return False
    try:
        dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
        start_naive = start.replace(tzinfo=None) if start.tzinfo else start
        end_naive = end.replace(tzinfo=None) if end.tzinfo else end
        return start_naive <= dt_naive <= end_naive
    except:
        return False

# =============================
# Funções TheSportsDB API
# =============================
def buscar_jogos_thesportsdb(liga_id: str, data: str) -> List[Dict]:
    """Busca jogos da API TheSportsDB por data específica"""
    try:
        # Formatar data para o padrão TheSportsDB (YYYY-MM-DD)
        if data != "all":
            data_formatada = data
        else:
            data_formatada = datetime.now().strftime("%Y-%m-%d")
        
        # Endpoint para buscar eventos por dia
        url = f"{THESPORTSDB_BASE_URL_V1}/{THESPORTSDB_API_KEY}/eventsday.php"
        params = {
            'd': data_formatada,
            'l': liga_id  # Filtro por liga
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 400:
            st.warning(f"⚠️ Requisição inválida para liga {liga_id}")
            return []
        elif response.status_code == 404:
            st.warning(f"🔍 Liga {liga_id} não encontrada")
            return []
        elif response.status_code == 429:
            st.warning("⏰ Limite de requisições excedido. Aguarde um momento.")
            time.sleep(2)  # Espera 2 segundos antes de continuar
            return []
            
        response.raise_for_status()
        dados = response.json()
        
        partidas = []
        
        # Processar eventos da resposta
        eventos = dados.get('events', [])
        
        for evento in eventos:
            try:
                # Informações básicas do evento
                hora = evento.get('strTimestamp', '')
                hora_dt = formatar_hora_brasilia(hora)
                
                hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "A definir"
                
                # Times
                home_team = evento.get('strHomeTeam', 'Time Casa')
                away_team = evento.get('strAwayTeam', 'Time Visitante')
                
                # Placar
                home_score = evento.get('intHomeScore', '')
                away_score = evento.get('intAwayScore', '')
                
                if home_score is None or home_score == '':
                    placar = "0 - 0"
                else:
                    placar = f"{home_score} - {away_score}"
                
                # Status
                status = evento.get('strStatus', 'Not Started')
                status_config = get_status_config(status)
                
                # Liga
                liga_nome = evento.get('strLeague', LIGA_NAMES.get(liga_id, f"Liga {liga_id}"))
                
                # Informações adicionais
                venue = evento.get('strVenue', '')
                thumb = evento.get('strThumb', '')
                
                partidas.append({
                    "home": home_team,
                    "away": away_team,
                    "placar": placar,
                    "status": status_config['desc'],
                    "hora": hora_dt,
                    "hora_formatada": hora_format,
                    "liga": liga_nome,
                    "liga_id": liga_id,
                    "status_original": status,
                    "venue": venue,
                    "thumb": thumb,
                    "event_id": evento.get('idEvent'),
                    "home_score": home_score,
                    "away_score": away_score
                })
                
            except Exception as e:
                st.warning(f"Erro ao processar evento: {str(e)}")
                continue
                
        return partidas
        
    except requests.exceptions.RequestException as e:
        st.error(f"🌐 Erro de rede na TheSportsDB API: {str(e)}")
        return []
    except Exception as e:
        st.error(f"❌ Erro inesperado na TheSportsDB API: {str(e)}")
        return []

def buscar_jogos_hoje_thesportsdb(liga_id: str) -> List[Dict]:
    """Busca jogos de hoje especificamente na TheSportsDB"""
    try:
        data_hoje = datetime.now().strftime("%Y-%m-%d")
        return buscar_jogos_thesportsdb(liga_id, data_hoje)
        
    except Exception:
        return []

def buscar_proximos_jogos_liga(liga_id: str) -> List[Dict]:
    """Busca próximos jogos de uma liga"""
    try:
        url = f"{THESPORTSDB_BASE_URL_V1}/{THESPORTSDB_API_KEY}/eventsnextleague.php"
        params = {
            'id': liga_id
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
            
        dados = response.json()
        partidas = []
        
        eventos = dados.get('events', [])
        
        for evento in eventos:
            try:
                hora = evento.get('strTimestamp', '')
                hora_dt = formatar_hora_brasilia(hora)
                
                hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "A definir"
                
                home_team = evento.get('strHomeTeam', 'Time Casa')
                away_team = evento.get('strAwayTeam', 'Time Visitante')
                
                status = evento.get('strStatus', 'Not Started')
                status_config = get_status_config(status)
                
                liga_nome = evento.get('strLeague', LIGA_NAMES.get(liga_id, f"Liga {liga_id}"))
                
                partidas.append({
                    "home": home_team,
                    "away": away_team,
                    "placar": "0 - 0",  # Jogos futuros
                    "status": status_config['desc'],
                    "hora": hora_dt,
                    "hora_formatada": hora_format,
                    "liga": liga_nome,
                    "liga_id": liga_id,
                    "status_original": status,
                    "venue": evento.get('strVenue', ''),
                    "thumb": evento.get('strThumb', ''),
                    "event_id": evento.get('idEvent')
                })
                
            except Exception:
                continue
                
        return partidas
        
    except Exception:
        return []

def buscar_ultimos_jogos_liga(liga_id: str) -> List[Dict]:
    """Busca últimos jogos de uma liga"""
    try:
        url = f"{THESPORTSDB_BASE_URL_V1}/{THESPORTSDB_API_KEY}/eventspastleague.php"
        params = {
            'id': liga_id
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
            
        dados = response.json()
        partidas = []
        
        eventos = dados.get('events', [])
        
        for evento in eventos:
            try:
                hora = evento.get('strTimestamp', '')
                hora_dt = formatar_hora_brasilia(hora)
                
                hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "A definir"
                
                home_team = evento.get('strHomeTeam', 'Time Casa')
                away_team = evento.get('strAwayTeam', 'Time Visitante')
                
                home_score = evento.get('intHomeScore', '0')
                away_score = evento.get('intAwayScore', '0')
                
                placar = f"{home_score} - {away_score}"
                
                status = evento.get('strStatus', 'Finished')
                status_config = get_status_config(status)
                
                liga_nome = evento.get('strLeague', LIGA_NAMES.get(liga_id, f"Liga {liga_id}"))
                
                partidas.append({
                    "home": home_team,
                    "away": away_team,
                    "placar": placar,
                    "status": status_config['desc'],
                    "hora": hora_dt,
                    "hora_formatada": hora_format,
                    "liga": liga_nome,
                    "liga_id": liga_id,
                    "status_original": status,
                    "venue": evento.get('strVenue', ''),
                    "thumb": evento.get('strThumb', ''),
                    "event_id": evento.get('idEvent'),
                    "home_score": home_score,
                    "away_score": away_score
                })
                
            except Exception:
                continue
                
        return partidas
        
    except Exception:
        return []

def buscar_livescores() -> List[Dict]:
    """Busca jogos ao vivo de todas as ligas"""
    try:
        # Para V2 (premium) - usando V1 como fallback
        if THESPORTSDB_API_KEY in ['1', '2', '3']:
            # Para free, buscar eventos do dia atual
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            url = f"{THESPORTSDB_BASE_URL_V1}/{THESPORTSDB_API_KEY}/eventsday.php"
            params = {'d': data_hoje}
        else:
            # Para premium, usar V2 livescores
            url = f"{THESPORTSDB_BASE_URL_V2}/{THESPORTSDB_API_KEY}/livescore/all"
            params = {}
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
            
        dados = response.json()
        partidas = []
        
        eventos = dados.get('events', [])
        
        for evento in eventos:
            try:
                status = evento.get('strStatus', '')
                
                # Filtrar apenas jogos ao vivo
                if 'Live' in status or 'Half Time' in status:
                    hora = evento.get('strTimestamp', '')
                    hora_dt = formatar_hora_brasilia(hora)
                    
                    hora_format = hora_dt.strftime("%H:%M") if hora_dt else "Ao Vivo"
                    
                    home_team = evento.get('strHomeTeam', 'Time Casa')
                    away_team = evento.get('strAwayTeam', 'Time Visitante')
                    
                    home_score = evento.get('intHomeScore', '0')
                    away_score = evento.get('intAwayScore', '0')
                    
                    placar = f"{home_score} - {away_score}"
                    
                    status_config = get_status_config(status)
                    liga_nome = evento.get('strLeague', '')
                    
                    partidas.append({
                        "home": home_team,
                        "away": away_team,
                        "placar": placar,
                        "status": status_config['desc'],
                        "hora": hora_dt,
                        "hora_formatada": hora_format,
                        "liga": liga_nome,
                        "liga_id": evento.get('idLeague', ''),
                        "status_original": status,
                        "venue": evento.get('strVenue', ''),
                        "thumb": evento.get('strThumb', ''),
                        "event_id": evento.get('idEvent'),
                        "home_score": home_score,
                        "away_score": away_score
                    })
                
            except Exception:
                continue
                
        return partidas
        
    except Exception:
        return []

# =============================
# Componentes de UI Melhorados
# =============================
def criar_card_partida(partida: Dict):
    """Cria um card visual para cada partida"""
    status_config = get_status_config(partida['status_original'])
    
    # Determina se o placar deve ser destacado
    placar = partida['placar']
    if placar != "0 - 0" and partida['status'] != 'Agendado':
        placar_style = "font-size: 24px; font-weight: bold; color: #E74C3C;"
    else:
        placar_style = "font-size: 20px; font-weight: normal; color: #7F8C8D;"
    
    with st.container():
        col1, col2, col3, col4 = st.columns([3, 2, 3, 2])
        
        with col1:
            st.markdown(f"**{partida['home']}**")
        
        with col2:
            st.markdown(f"<div style='text-align: center; {placar_style}'>{placar}</div>", 
                       unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"**{partida['away']}**")
        
        with col4:
            status_color = status_config['color']
            st.markdown(
                f"<div style='background-color: {status_color}; color: white; padding: 4px 8px; "
                f"border-radius: 12px; text-align: center; font-size: 12px;'>"
                f"{status_config['emoji']} {partida['status']}</div>", 
                unsafe_allow_html=True
            )
        
        # Linha inferior com informações adicionais
        col_info1, col_info2, col_info3 = st.columns([1, 1, 1])
        with col_info1:
            st.caption(f"🕒 {partida['hora_formatada']}")
        with col_info2:
            st.caption(f"🏆 {partida['liga']}")
        with col_info3:
            hora_partida = partida['hora']
            agora = datetime.now()
            if is_datetime_valid(hora_partida) and safe_datetime_compare(hora_partida, agora):
                try:
                    hora_partida_naive = hora_partida.replace(tzinfo=None) if hora_partida.tzinfo else hora_partida
                    agora_naive = agora.replace(tzinfo=None) if agora.tzinfo else agora
                    tempo_restante = hora_partida_naive - agora_naive
                    
                    horas = int(tempo_restante.total_seconds() // 3600)
                    minutos = int((tempo_restante.total_seconds() % 3600) // 60)
                    if horas > 0:
                        st.caption(f"⏳ {horas}h {minutos}min")
                    elif minutos > 0:
                        st.caption(f"⏳ {minutos}min")
                    else:
                        st.caption("⏳ Agora!")
                except:
                    st.caption("⏳ --")
        
        st.markdown("---")

def exibir_partidas_por_liga(partidas: List[Dict]):
    """Exibe partidas agrupadas por liga com visual melhorado"""
    partidas_por_liga = {}
    for partida in partidas:
        liga = partida['liga']
        if liga not in partidas_por_liga:
            partidas_por_liga[liga] = []
        partidas_por_liga[liga].append(partida)
    
    ligas_ordenadas = sorted(partidas_por_liga.keys(), 
                           key=lambda x: len(partidas_por_liga[x]), reverse=True)
    
    for liga_index, liga in enumerate(ligas_ordenadas):
        partidas_liga = partidas_por_liga[liga]
        
        with st.container():
            st.markdown(f"### 🏆 {liga}")
            st.markdown(f"**{len(partidas_liga)} partida(s) encontrada(s)**")
            
            liga_key = f"filtro_{liga}"
            if liga_key not in st.session_state.filtros_liga:
                st.session_state.filtros_liga[liga_key] = {
                    'status': "Todos",
                    'time': ""
                }
            
            col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
            with col_filtro1:
                novo_status = st.selectbox(
                    f"Status - {liga}",
                    ["Todos", "Agendado", "Ao Vivo", "Finalizado"],
                    index=["Todos", "Agendado", "Ao Vivo", "Finalizado"].index(
                        st.session_state.filtros_liga[liga_key]['status']
                    )
                )
                st.session_state.filtros_liga[liga_key]['status'] = novo_status
            
            with col_filtro2:
                novo_time = st.text_input(
                    f"Buscar time - {liga}", 
                    value=st.session_state.filtros_liga[liga_key]['time']
                )
                st.session_state.filtros_liga[liga_key]['time'] = novo_time
            
            with col_filtro3:
                if st.button(f"🎯 Top 3 - {liga}"):
                    partidas_liga = partidas_liga[:3]
            
            partidas_filtradas = partidas_liga.copy()
            filtro_atual = st.session_state.filtros_liga[liga_key]
            
            if filtro_atual['status'] != "Todos":
                partidas_filtradas = [p for p in partidas_filtradas if filtro_atual['status'].lower() in p['status'].lower()]
            
            if filtro_atual['time']:
                partidas_filtradas = [p for p in partidas_filtradas 
                               if filtro_atual['time'].lower() in p['home'].lower() 
                               or filtro_atual['time'].lower() in p['away'].lower()]
            
            if partidas_filtradas:
                for partida in partidas_filtradas:
                    criar_card_partida(partida)
            else:
                st.info(f"ℹ️ Nenhuma partida encontrada para os filtros em {liga}")
            
            st.markdown("<br>", unsafe_allow_html=True)

def exibir_estatisticas(partidas: List[Dict]):
    """Exibe estatísticas visuais das partidas"""
    total_partidas = len(partidas)
    ligas_unicas = len(set(p['liga'] for p in partidas))
    
    status_count = {}
    for partida in partidas:
        status = partida['status']
        status_count[status] = status_count.get(status, 0) + 1
    
    partidas_ao_vivo = len([p for p in partidas if any(x in p['status'].lower() for x in ['vivo', 'live', 'andamento', 'halftime'])])
    
    agora = datetime.now()
    limite_3h = agora + timedelta(hours=3)
    proximas_3h = []
    
    for partida in partidas:
        hora_partida = partida['hora']
        if safe_datetime_range(hora_partida, agora, limite_3h):
            proximas_3h.append(partida)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total de Partidas", total_partidas)
    
    with col2:
        st.metric("🏆 Ligas", ligas_unicas)
    
    with col3:
        st.metric("🔴 Ao Vivo", partidas_ao_vivo, 
                 delta=partidas_ao_vivo if partidas_ao_vivo > 0 else None)
    
    with col4:
        st.metric("⏰ Próximas 3h", len(proximas_3h),
                 delta=len(proximas_3h) if len(proximas_3h) > 0 else None)
    
    if status_count:
        st.markdown("### 📈 Distribuição por Status")
        status_df = pd.DataFrame(list(status_count.items()), columns=['Status', 'Quantidade'])
        st.bar_chart(status_df.set_index('Status'))

# =============================
# Função principal de processamento
# =============================
def processar_jogos(data_str: str, ligas_selecionadas: List[str], top_n: int, buscar_hoje: bool = False):
    """Processa e exibe jogos com interface melhorada"""
    
    progress_container = st.container()
    
    with progress_container:
        if buscar_hoje:
            st.info("🎯 Buscando jogos de HOJE...")
        else:
            st.info(f"⏳ Buscando jogos para {datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')}...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    todas_partidas = []
    total_ligas = len(ligas_selecionadas)
    
    for i, liga in enumerate(ligas_selecionadas):
        progress = (i + 1) / total_ligas
        progress_bar.progress(progress)
        status_text.info(f"🔍 Buscando {liga}... ({i+1}/{total_ligas})")
        
        liga_id = LIGAS_THESPORTSDB[liga]
        
        if buscar_hoje:
            partidas = buscar_jogos_hoje_thesportsdb(liga_id)
        else:
            partidas = buscar_jogos_thesportsdb(liga_id, data_str)
        
        if partidas:
            todas_partidas.extend(partidas)
            status_text.success(f"✅ {liga}: {len(partidas)} jogos")
        else:
            status_text.warning(f"⚠️ {liga}: Nenhum jogo encontrado")
        
        time.sleep(0.5)  # Respeitar limites da API
    
    if not todas_partidas:
        status_text.error("❌ Nenhum jogo encontrado para os critérios selecionados.")
        st.session_state.dados_carregados = False
        return

    todas_partidas.sort(key=lambda x: x['hora'] if is_datetime_valid(x['hora']) else datetime.max)
    
    st.session_state.todas_partidas = todas_partidas
    st.session_state.dados_carregados = True
    st.session_state.ultima_busca = datetime.now()
    st.session_state.ultimas_ligas = ligas_selecionadas
    st.session_state.busca_hoje = buscar_hoje
    st.session_state.data_ultima_busca = data_str
    st.session_state.top_n = top_n
    
    progress_bar.empty()
    status_text.empty()

    exibir_dados_salvos()

def exibir_dados_salvos():
    """Exibe os dados salvos no session state"""
    if not st.session_state.dados_carregados:
        return
    
    todas_partidas = st.session_state.todas_partidas
    top_n = st.session_state.top_n
    
    st.markdown("---")
    exibir_estatisticas(todas_partidas)
    
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        if st.session_state.busca_hoje:
            st.info("🎯 **Última busca:** Jogos de Hoje")
        else:
            st.info(f"📅 **Última busca:** {datetime.strptime(st.session_state.data_ultima_busca, '%Y-%m-%d').strftime('%d/%m/%Y')}")
    with col_info2:
        st.info(f"🏆 **Ligas:** {len(st.session_state.ultimas_ligas)} selecionadas")
    with col_info3:
        if st.session_state.ultima_busca:
            tempo_passado = datetime.now() - st.session_state.ultima_busca
            minutos = int(tempo_passado.total_seconds() // 60)
            st.info(f"⏰ **Atualizado:** {minutos} min atrás")
    
    st.markdown("---")
    col_view1, col_view2, col_view3 = st.columns(3)
    with col_view1:
        if st.button("📊 Visualização por Liga", use_container_width=True):
            st.session_state.modo_exibicao = "liga"
    with col_view2:
        if st.button("📋 Lista Compacta", use_container_width=True):
            st.session_state.modo_exibicao = "lista"
    with col_view3:
        if st.button("🎯 Top Partidas", use_container_width=True):
            st.session_state.modo_exibicao = "top"

    modo = st.session_state.modo_exibicao
    
    if modo == "liga":
        st.markdown("## 🏆 Partidas por Liga")
        exibir_partidas_por_liga(todas_partidas)
    
    st.markdown("---")
    st.subheader("📤 Enviar para Telegram")
    
    col_tg1, col_tg2 = st.columns([1, 2])
    with col_tg1:
        if st.button(f"🚀 Enviar Top {top_n} para Telegram", type="primary", use_container_width=True):
            if st.session_state.busca_hoje:
                top_msg = f"⚽ TOP {top_n} JOGOS DE HOJE - {datetime.now().strftime('%d/%m/%Y')}\n\n"
            else:
                top_msg = f"⚽ TOP {top_n} JOGOS - {datetime.strptime(st.session_state.data_ultima_busca, '%Y-%m-%d').strftime('%d/%m/%Y')}\n\n"
            
            for i, p in enumerate(todas_partidas[:top_n], 1):
                emoji = "🔥" if i == 1 else "⭐" if i <= 3 else "⚽"
                top_msg += f"{emoji} {i}. {p['home']} vs {p['away']}\n"
                top_msg += f"   📊 {p['placar']} | 🕒 {p['hora_formatada']} | 📍 {p['status']}\n"
                top_msg += f"   🏆 {p['liga']}\n\n"
            
            if enviar_telegram(top_msg, TELEGRAM_CHAT_ID_ALT2):
                st.success(f"✅ Top {top_n} jogos enviados para o Telegram!")
            else:
                st.error("❌ Falha ao enviar para o Telegram!")
    
    with col_tg2:
        st.info("💡 Agora com dados da TheSportsDB API")
        
    st.markdown("---")
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        st.rerun()

# =============================
# Interface Streamlit
# =============================
def main():
    st.title("⚽ Soccer Elite Master - TheSportsDB API")
    st.markdown("### Sistema Completo com Dados Gratuitos")
    st.markdown("---")
    
    inicializar_session_state()
    
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📊 Exibição")
        top_n = st.selectbox("Top N Jogos", [3, 5, 10], index=1)
        st.session_state.top_n = top_n
        
        st.subheader("🏆 Ligas")
        st.markdown("Selecione as ligas para buscar:")
        
        ligas_selecionadas = st.multiselect(
            "Selecione as ligas:",
            options=list(LIGAS_THESPORTSDB.keys()),
            default=st.session_state.ultimas_ligas if st.session_state.ultimas_ligas else list(LIGAS_THESPORTSDB.keys())[:4],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.subheader("🎯 Buscas Especiais")
        
        col_esp1, col_esp2 = st.columns(2)
        with col_esp1:
            if st.button("🔴 Jogos Ao Vivo", use_container_width=True):
                partidas_live = buscar_livescores()
                if partidas_live:
                    st.session_state.todas_partidas = partidas_live
                    st.session_state.dados_carregados = True
                    st.session_state.busca_hoje = True
                    st.session_state.ultima_busca = datetime.now()
                    st.rerun()
                else:
                    st.warning("ℹ️ Nenhum jogo ao vivo encontrado")
        
        with col_esp2:
            if st.button("📅 Próximos Jogos", use_container_width=True):
                todas_partidas = []
                for liga in ligas_selecionadas:
                    liga_id = LIGAS_THESPORTSDB[liga]
                    partidas = buscar_proximos_jogos_liga(liga_id)
                    todas_partidas.extend(partidas)
                
                if todas_partidas:
                    st.session_state.todas_partidas = todas_partidas
                    st.session_state.dados_carregados = True
                    st.session_state.busca_hoje = False
                    st.session_state.ultima_busca = datetime.now()
                    st.rerun()
                else:
                    st.warning("ℹ️ Nenhum próximo jogo encontrado")
        
        st.markdown("---")
        st.subheader("🛠️ Utilidades")
        
        col_util1, col_util2 = st.columns(2)
        with col_util1:
            if st.button("🧹 Limpar Cache", use_container_width=True):
                if os.path.exists(CACHE_JOGOS):
                    os.remove(CACHE_JOGOS)
                if os.path.exists(ALERTAS_PATH):
                    os.remove(ALERTAS_PATH)
                st.success("✅ Cache limpo!")
                time.sleep(1)
                st.rerun()
                
        with col_util2:
            if st.button("🔄 Atualizar", use_container_width=True):
                if st.session_state.dados_carregados:
                    if st.session_state.busca_hoje:
                        processar_jogos("", st.session_state.ultimas_ligas, st.session_state.top_n, buscar_hoje=True)
                    else:
                        processar_jogos(st.session_state.data_ultima_busca, st.session_state.ultimas_ligas, st.session_state.top_n, buscar_hoje=False)
                else:
                    st.warning("ℹ️ Nenhum dado para atualizar. Faça uma busca primeiro.")

    st.subheader("🎯 Buscar Jogos")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        data_selecionada = st.date_input(
            "Selecione a data:", 
            value=datetime.today(),
            max_value=datetime.today() + timedelta(days=365)  # TheSportsDB permite buscar até 1 ano
        )
    
    with col2:
        st.markdown("### ")
        btn_buscar = st.button("🔍 Buscar por Data", type="primary", use_container_width=True)
    
    with col3:
        st.markdown("### ")
        btn_hoje = st.button("🎯 Jogos de Hoje", use_container_width=True, 
                           help="Busca apenas jogos acontecendo hoje")

    data_str = data_selecionada.strftime("%Y-%m-%d")

    if btn_buscar:
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos(data_str, ligas_selecionadas, top_n, buscar_hoje=False)

    if btn_hoje:
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos("", ligas_selecionadas, top_n, buscar_hoje=True)

    if st.session_state.dados_carregados:
        exibir_dados_salvos()
    else:
        st.info("""
        🎯 **Bem-vindo ao Soccer Elite Master com TheSportsDB API!**
        
        **🚀 Vantagens TheSportsDB:**
        - ✅ **Completamente GRATUITA** (chaves: 1, 2, 3)
        - ✅ **Dados de jogos futuros** (até 1 ano)
        - ✅ **Jogos passados** com históricos completos
        - ✅ **Livescores em tempo real**
        - ✅ **Cobertura global** de ligas
        - ✅ **Imagens e thumbnails** dos eventos
        
        **🎯 Funcionalidades:**
        - Busca por data específica
        - Jogos de hoje
        - Jogos ao vivo
        - Próximos jogos
        - Histórico de partidas
        
        **Para começar:**
        1. **Selecione as ligas** que deseja monitorar
        2. **Escolha uma data** ou clique em **"Jogos de Hoje"**
        3. Use **"Jogos Ao Vivo"** para partidas em andamento
        
        ⚡ **Dica:** API 100% gratuita com limites generosos!
        """)

    with st.expander("🎮 Guia Rápido - TheSportsDB", expanded=False):
        col_help1, col_help2 = st.columns(2)
        
        with col_help1:
            st.markdown("""
            **🔑 Chaves API Gratuitas:**
            - **1, 2, 3** - Chaves free com 30 req/min
            - **Premium** - 100 req/min (opcional)
            - Configure: `THESPORTSDB_API_KEY=1`
            
            **📊 Endpoints Principais:**
            - `eventsday.php` - Jogos por data
            - `eventsnextleague.php` - Próximos jogos
            - `eventspastleague.php` - Jogos passados
            - Livescores - Jogos ao vivo
            
            **🏆 Ligas Suportadas:**
            - Premier League, La Liga, Serie A
            - Bundesliga, Ligue 1, MLS
            - Brasileirão A e B
            - Libertadores, Champions, Europa
            """)
        
        with col_help2:
            st.markdown("""
            **🎯 Como Usar:**
            1. **Busca por Data**: Selecione qualquer data futura
            2. **Jogos de Hoje**: Partidas do dia atual
            3. **Jogos Ao Vivo**: Partidas em andamento
            4. **Próximos Jogos**: Próximas partidas agendadas
            
            **📈 Próximos Passos:**
            - Estatísticas avançadas
            - Histórico de confrontos
            - Previsões baseadas em dados
            - Análise de performance
            """)

if __name__ == "__main__":
    main()
