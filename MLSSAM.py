# ================================================
# ⚽ ESPN Soccer - Elite Master
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
st.set_page_config(page_title="⚽ ESPN Soccer - Elite", layout="wide")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Principais ligas (ESPN) - ATUALIZADO
# =============================
LIGAS_ESPN = {
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1", 
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "MLS (Estados Unidos)": "usa.1",
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Liga MX (México)": "mex.1",
    "Copa Libertadores": "ccm",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa"
}

# Cores e emojis para status
STATUS_CONFIG = {
    "Agendado": {"emoji": "⏰", "color": "#4A90E2"},
    "Ao Vivo": {"emoji": "🔴", "color": "#E74C3C"},
    "Halftime": {"emoji": "⏸️", "color": "#F39C12"},
    "Finalizado": {"emoji": "✅", "color": "#27AE60"},
    "Adiado": {"emoji": "🚫", "color": "#95A5A6"},
    "Cancelado": {"emoji": "❌", "color": "#7F8C8D"}
}

# Headers para simular navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Referer': 'https://www.espn.com.br/',
    'Origin': 'https://www.espn.com.br'
}

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
        
        if hora_utc.endswith('Z'):
            hora_utc = hora_utc[:-1] + '+00:00'
        
        hora_dt = datetime.fromisoformat(hora_utc)
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
    return {"emoji": "⚫", "color": "#95A5A6"}

# =============================
# Componentes de UI Melhorados
# =============================
def criar_card_partida(partida: Dict):
    """Cria um card visual para cada partida"""
    status_config = get_status_config(partida['status'])
    
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
            if partida['hora'] and partida['hora'] > datetime.now():
                tempo_restante = partida['hora'] - datetime.now()
                horas = int(tempo_restante.total_seconds() // 3600)
                minutos = int((tempo_restante.total_seconds() % 3600) // 60)
                if horas > 0:
                    st.caption(f"⏳ {horas}h {minutos}min")
                else:
                    st.caption(f"⏳ {minutos}min")
        
        st.markdown("---")

def exibir_partidas_por_liga(partidas: List[Dict]):
    """Exibe partidas agrupadas por liga com visual melhorado"""
    # Agrupa partidas por liga
    partidas_por_liga = {}
    for partida in partidas:
        liga = partida['liga']
        if liga not in partidas_por_liga:
            partidas_por_liga[liga] = []
        partidas_por_liga[liga].append(partida)
    
    # Ordena ligas por número de partidas (mais partidas primeiro)
    ligas_ordenadas = sorted(partidas_por_liga.keys(), 
                           key=lambda x: len(partidas_por_liga[x]), reverse=True)
    
    for liga in ligas_ordenadas:
        partidas_liga = partidas_por_liga[liga]
        
        # Container da liga
        with st.container():
            st.markdown(f"### 🏆 {liga}")
            st.markdown(f"**{len(partidas_liga)} partida(s) encontrada(s)**")
            
            # Filtros para a liga
            col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
            with col_filtro1:
                filtrar_status = st.selectbox(
                    f"Status - {liga}",
                    ["Todos", "Agendado", "Ao Vivo", "Finalizado"],
                    key=f"status_{liga}"
                )
            with col_filtro2:
                filtrar_time = st.text_input(f"Buscar time - {liga}", key=f"time_{liga}")
            with col_filtro3:
                if st.button(f"🎯 Top 3 - {liga}", key=f"top3_{liga}"):
                    partidas_liga = partidas_liga[:3]
            
            # Aplica filtros
            if filtrar_status != "Todos":
                partidas_liga = [p for p in partidas_liga if filtrar_status.lower() in p['status'].lower()]
            
            if filtrar_time:
                partidas_liga = [p for p in partidas_liga 
                               if filtrar_time.lower() in p['home'].lower() 
                               or filtrar_time.lower() in p['away'].lower()]
            
            # Exibe partidas
            if partidas_liga:
                for partida in partidas_liga:
                    criar_card_partida(partida)
            else:
                st.info(f"ℹ️ Nenhuma partida encontrada para os filtros em {liga}")
            
            st.markdown("<br>", unsafe_allow_html=True)

def exibir_estatisticas(partidas: List[Dict]):
    """Exibe estatísticas visuais das partidas"""
    total_partidas = len(partidas)
    ligas_unicas = len(set(p['liga'] for p in partidas))
    
    # Contagem por status
    status_count = {}
    for partida in partidas:
        status = partida['status']
        status_count[status] = status_count.get(status, 0) + 1
    
    # Partidas ao vivo
    partidas_ao_vivo = len([p for p in partidas if any(x in p['status'].lower() for x in ['vivo', 'live', 'andamento'])])
    
    # Próximas partidas (nas próximas 3 horas)
    agora = datetime.now()
    proximas_3h = [p for p in partidas if p['hora'] and agora <= p['hora'] <= agora + timedelta(hours=3)]
    
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
    
    # Gráfico de status simples
    if status_count:
        st.markdown("### 📈 Distribuição por Status")
        status_df = pd.DataFrame(list(status_count.items()), columns=['Status', 'Quantidade'])
        st.bar_chart(status_df.set_index('Status'))

# =============================
# Função para buscar jogos ESPN
# =============================
def buscar_jogos_espn(liga_slug: str, data: str) -> List[Dict]:
    """Busca jogos da API da ESPN com tratamento robusto de erros"""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 400:
            return []
        elif response.status_code == 404:
            return []
            
        response.raise_for_status()
        dados = response.json()
        
        if not dados.get('events'):
            return []
            
        partidas = []
        data_alvo = datetime.strptime(data, "%Y-%m-%d").date()

        for evento in dados.get("events", []):
            try:
                hora = evento.get("date", "")
                hora_dt = formatar_hora_brasilia(hora)
                
                if hora_dt and data != "all":
                    if hora_dt.date() != data_alvo:
                        continue
                
                hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "A definir"
                
                competicoes = evento.get("competitions", [{}])
                competicao = competicoes[0] if competicoes else {}
                times = competicao.get("competitors", [])
                
                if len(times) >= 2:
                    home_team = times[0].get("team", {})
                    away_team = times[1].get("team", {})
                    
                    home = home_team.get("displayName", "Time Casa")
                    away = away_team.get("displayName", "Time Visitante")
                    placar_home = times[0].get("score", "0")
                    placar_away = times[1].get("score", "0")
                else:
                    home = "Time Casa"
                    away = "Time Visitante" 
                    placar_home = placar_away = "0"

                status_info = evento.get("status", {})
                status_type = status_info.get("type", {})
                status_desc = status_type.get("description", "Agendado")
                
                liga_nome = competicao.get("league", {}).get("name", liga_slug)

                partidas.append({
                    "home": home,
                    "away": away,
                    "placar": f"{placar_home} - {placar_away}",
                    "status": status_desc,
                    "hora": hora_dt,
                    "hora_formatada": hora_format,
                    "liga": liga_nome,
                    "liga_slug": liga_slug
                })
                
            except Exception as e:
                continue
                
        return partidas
        
    except Exception as e:
        return []

def buscar_jogos_hoje(liga_slug: str) -> List[Dict]:
    """Busca jogos de hoje especificamente"""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return []
            
        dados = response.json()
        partidas = []
        hoje = datetime.now().date()

        for evento in dados.get("events", []):
            try:
                hora = evento.get("date", "")
                hora_dt = formatar_hora_brasilia(hora)
                
                if not hora_dt or hora_dt.date() != hoje:
                    continue
                
                hora_format = hora_dt.strftime("%H:%M")
                
                competicoes = evento.get("competitions", [{}])
                competicao = competicoes[0] if competicoes else {}
                times = competicao.get("competitors", [])
                
                if len(times) >= 2:
                    home_team = times[0].get("team", {})
                    away_team = times[1].get("team", {})
                    
                    home = home_team.get("displayName", "Time Casa")
                    away = away_team.get("displayName", "Time Visitante")
                    placar_home = times[0].get("score", "0")
                    placar_away = times[1].get("score", "0")
                else:
                    continue

                status_info = evento.get("status", {})
                status_type = status_info.get("type", {})
                status_desc = status_type.get("description", "Agendado")
                
                liga_nome = competicao.get("league", {}).get("name", liga_slug)

                partidas.append({
                    "home": home,
                    "away": away,
                    "placar": f"{placar_home} - {placar_away}",
                    "status": status_desc,
                    "hora": hora_dt,
                    "hora_formatada": hora_format,
                    "liga": liga_nome,
                    "liga_slug": liga_slug
                })
                
            except Exception:
                continue
                
        return partidas
        
    except Exception:
        return []

# =============================
# Função principal de processamento
# =============================
def processar_jogos(data_str: str, ligas_selecionadas: List[str], top_n: int, modo_exibicao: str, buscar_hoje: bool = False):
    """Processa e exibe jogos com interface melhorada"""
    
    progress_container = st.container()
    
    with progress_container:
        if buscar_hoje:
            st.info("🎯 Buscando jogos de HOJE...")
        else:
            st.info(f"⏳ Buscando jogos para {datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')}...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Busca dados
    todas_partidas = []
    total_ligas = len(ligas_selecionadas)
    
    for i, liga in enumerate(ligas_selecionadas):
        progress = (i + 1) / total_ligas
        progress_bar.progress(progress)
        status_text.info(f"🔍 Buscando {liga}... ({i+1}/{total_ligas})")
        
        liga_slug = LIGAS_ESPN[liga]
        
        if buscar_hoje:
            partidas = buscar_jogos_hoje(liga_slug)
        else:
            partidas = buscar_jogos_espn(liga_slug, data_str)
        
        if partidas:
            todas_partidas.extend(partidas)
            status_text.success(f"✅ {liga}: {len(partidas)} jogos")
        else:
            status_text.warning(f"⚠️ {liga}: Nenhum jogo encontrado")
        
        time.sleep(0.5)
    
    if not todas_partidas:
        status_text.error("❌ Nenhum jogo encontrado para os critérios selecionados.")
        return

    # Ordenar por horário
    todas_partidas.sort(key=lambda x: x['hora'] if x['hora'] else datetime.max)
    
    # Limpa a barra de progresso
    progress_bar.empty()
    status_text.empty()

    # Exibe estatísticas
    st.markdown("---")
    exibir_estatisticas(todas_partidas)
    
    # Seletor de modo de exibição
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

    # Modo de exibição
    modo = st.session_state.get('modo_exibicao', 'liga')
    
    if modo == "liga":
        st.markdown("## 🏆 Partidas por Liga")
        exibir_partidas_por_liga(todas_partidas)
        
    elif modo == "lista":
        st.markdown("## 📋 Todas as Partidas")
        # Lista compacta
        for i, partida in enumerate(todas_partidas):
            status_config = get_status_config(partida['status'])
            with st.expander(f"{status_config['emoji']} {partida['home']} vs {partida['away']} - {partida['placar']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Casa:** {partida['home']}")
                    st.write(f"**Visitante:** {partida['away']}")
                with col2:
                    st.write(f"**Status:** {partida['status']}")
                    st.write(f"**Horário:** {partida['hora_formatada']}")
                    st.write(f"**Liga:** {partida['liga']}")
    
    elif modo == "top":
        st.markdown(f"## 🎯 Top {top_n} Partidas")
        partidas_top = todas_partidas[:top_n]
        for partida in partidas_top:
            criar_card_partida(partida)

    # Botão para enviar para Telegram
    st.markdown("---")
    st.subheader("📤 Enviar para Telegram")
    
    col_tg1, col_tg2 = st.columns([1, 2])
    with col_tg1:
        if st.button(f"🚀 Enviar Top {top_n} para Telegram", type="primary", use_container_width=True):
            if buscar_hoje:
                top_msg = f"⚽ TOP {top_n} JOGOS DE HOJE - {datetime.now().strftime('%d/%m/%Y')}\n\n"
            else:
                top_msg = f"⚽ TOP {top_n} JOGOS - {datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')}\n\n"
            
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
        st.info("💡 As partidas serão enviadas no formato compacto para o Telegram")

# =============================
# Interface Streamlight
# =============================
def main():
    st.title("⚽ ESPN Soccer - Elite Master")
    st.markdown("### Sistema Avançado de Monitoramento de Futebol")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📊 Exibição")
        top_n = st.selectbox("Top N Jogos", [3, 5, 10], index=0)
        
        st.subheader("🏆 Ligas")
        st.markdown("Selecione as ligas para buscar:")
        
        ligas_selecionadas = st.multiselect(
            "Selecione as ligas:",
            options=list(LIGAS_ESPN.keys()),
            default=list(LIGAS_ESPN.keys())[:4],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.subheader("🎨 Personalização")
        
        # Tema de cores
        tema = st.selectbox("Tema de Cores", ["Padrão", "Escuro", "Colorido"])
        
        st.markdown("---")
        st.subheader("🛠️ Utilidades")
        
        if st.button("🧹 Limpar Cache", use_container_width=True):
            if os.path.exists(CACHE_JOGOS):
                os.remove(CACHE_JOGOS)
            if os.path.exists(ALERTAS_PATH):
                os.remove(ALERTAS_PATH)
            st.success("✅ Cache limpo!")
            time.sleep(1)
            st.rerun()

    # Conteúdo principal
    st.subheader("🎯 Buscar Jogos")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        data_selecionada = st.date_input(
            "Selecione a data:", 
            value=datetime.today(),
            max_value=datetime.today() + timedelta(days=7)
        )
    
    with col2:
        st.markdown("### ")
        btn_buscar = st.button("🔍 Buscar por Data", type="primary", use_container_width=True)
    
    with col3:
        st.markdown("### ")
        btn_hoje = st.button("🎯 Jogos de Hoje", use_container_width=True, 
                           help="Busca apenas jogos acontecendo hoje")

    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Processar ações
    if btn_buscar:
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos(data_str, ligas_selecionadas, top_n, "liga", buscar_hoje=False)

    if btn_hoje:
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos("", ligas_selecionadas, top_n, "liga", buscar_hoje=True)

    # Informações de ajuda
    with st.expander("🎮 Guia Rápido", expanded=True):
        col_help1, col_help2 = st.columns(2)
        
        with col_help1:
            st.markdown("""
            **📊 Modos de Visualização:**
            - **Por Liga**: Partidas agrupadas por campeonato
            - **Lista Compacta**: Todas em lista expansível  
            - **Top Partidas**: Apenas as mais relevantes
            
            **🎯 Funcionalidades:**
            - Filtros por status e time
            - Estatísticas em tempo real
            - Cards visuais coloridos
            - Envio para Telegram
            """)
        
        with col_help2:
            st.markdown("""
            **🔧 Dicas:**
            - Use **Jogos de Hoje** para resultados atuais
            - Clique em **Top 3** para ver os principais de cada liga
            - Filtre por time para encontrar partidas específicas
            - Monitore jogos **ao vivo** com o status colorido
            """)

if __name__ == "__main__":
    main()
