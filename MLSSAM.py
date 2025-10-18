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
        # Tenta recuperar o arquivo ou cria um novo
        try:
            # Backup do arquivo corrompido
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
        
        # Remove o Z e adiciona o offset UTC
        if hora_utc.endswith('Z'):
            hora_utc = hora_utc[:-1] + '+00:00'
        
        hora_dt = datetime.fromisoformat(hora_utc)
        # Converte para Brasília (UTC-3)
        hora_brasilia = hora_dt - timedelta(hours=3)
        return hora_brasilia
    except Exception:
        return None

# =============================
# Função para buscar jogos ESPN - CORRIGIDA
# =============================
def buscar_jogos_espn(liga_slug: str, data: str) -> List[Dict]:
    """Busca jogos da API da ESPN com tratamento robusto de erros"""
    try:
        # URL da API - sem parâmetros de data para buscar jogos atuais
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        
        response = requests.get(
            url, 
            headers=HEADERS,
            timeout=15
        )
        
        # Verifica se a resposta é válida
        if response.status_code == 400:
            st.warning(f"⚠️ API não disponível para {liga_slug}")
            return []
        elif response.status_code == 404:
            st.warning(f"🔍 Liga {liga_slug} não encontrada")
            return []
            
        response.raise_for_status()
        dados = response.json()
        
        # Verifica se há eventos
        if not dados.get('events'):
            return []
            
        partidas = []
        data_alvo = datetime.strptime(data, "%Y-%m-%d").date()

        for evento in dados.get("events", []):
            try:
                # Extrai informações básicas
                hora = evento.get("date", "")
                hora_dt = formatar_hora_brasilia(hora)
                
                # Filtra por data se especificada
                if hora_dt and data != "all":
                    if hora_dt.date() != data_alvo:
                        continue
                
                hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "A definir"
                
                competicoes = evento.get("competitions", [{}])
                competicao = competicoes[0] if competicoes else {}
                times = competicao.get("competitors", [])
                
                # Processa times e placar
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

                # Status do jogo
                status_info = evento.get("status", {})
                status_type = status_info.get("type", {})
                status_desc = status_type.get("description", "Agendado")
                
                # Nome da liga
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
        
    except requests.exceptions.RequestException as e:
        if "404" in str(e):
            st.warning(f"🔍 Liga {liga_slug} não encontrada na API")
        elif "400" in str(e):
            st.warning(f"⚠️ Requisição inválida para {liga_slug}")
        else:
            st.error(f"🌐 Erro de rede para {liga_slug}: {str(e)}")
        return []
    except Exception as e:
        st.error(f"❌ Erro inesperado em {liga_slug}: {str(e)}")
        return []

# =============================
# Função para buscar jogos de hoje - NOVA
# =============================
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
                
                # Filtra apenas jogos de hoje
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
# Funções de cache
# =============================
def carregar_cache_jogos() -> dict:
    cache = carregar_json(CACHE_JOGOS)
    # Limpa cache expirado
    if cache and "_timestamp" in cache:
        if time.time() - cache["_timestamp"] > CACHE_TIMEOUT:
            return {}
    return cache

def salvar_cache_jogos(dados: dict):
    dados["_timestamp"] = time.time()
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Função para processar jogos - MELHORADA
# =============================
def processar_jogos(data_str: str, ligas_selecionadas: List[str], top_n: int, linhas_exibir: int, buscar_hoje: bool = False):
    """Processa e exibe jogos, com envio para Telegram"""
    
    progress_container = st.container()
    results_container = st.container()
    
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
        
        # Pequena pausa para não sobrecarregar a API
        time.sleep(0.5)
    
    if not todas_partidas:
        status_text.error("❌ Nenhum jogo encontrado para os critérios selecionados.")
        
        # Sugestões
        with st.expander("💡 Sugestões"):
            st.markdown("""
            **Por que não encontrou jogos?**
            - 🎯 Tente buscar **Jogos de Hoje** (botão abaixo)
            - 📅 Muitas ligas não têm jogos em datas futuras
            - 🌐 A API da ESPN pode estar temporariamente indisponível
            - 🔄 Tente limpar o cache e buscar novamente
            
            **Ligas que geralmente têm jogos:**
            - Premier League, La Liga, Bundesliga
            - MLS (Estados Unidos)
            - Brasileirão Série A/B (temporada)
            """)
        return

    # Ordenar por horário
    todas_partidas.sort(key=lambda x: x['hora'] if x['hora'] else datetime.max)

    # Preparar dados para exibição
    with results_container:
        dados_exibicao = []
        for p in todas_partidas:
            dados_exibicao.append({
                "Liga": p['liga'],
                "Casa": p['home'][:20],
                "Placar": p['placar'],
                "Visitante": p['away'][:20],
                "Status": p['status'][:15],
                "Horário": p['hora_formatada']
            })

        # Exibir tabela
        df = pd.DataFrame(dados_exibicao)
        if linhas_exibir < len(df):
            df_display = df.head(linhas_exibir)
            st.info(f"📊 Exibindo {linhas_exibir} de {len(todas_partidas)} jogos encontrados")
        else:
            df_display = df
            st.success(f"📊 Exibindo todos os {len(todas_partidas)} jogos encontrados")
        
        st.dataframe(df_display, use_container_width=True)

        # Estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Jogos", len(todas_partidas))
        with col2:
            st.metric("Ligas com Jogos", len(set(p['liga'] for p in todas_partidas)))
        with col3:
            jogos_ao_vivo = len([p for p in todas_partidas if p['status'] not in ['Agendado', 'Finalizado']])
            st.metric("Jogos ao Vivo", jogos_ao_vivo)

        # Botão para enviar para Telegram
        st.markdown("---")
        st.subheader("📤 Enviar para Telegram")
        
        if st.button(f"🚀 Enviar Top {top_n} Jogos para Telegram", type="primary"):
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

# =============================
# Interface Streamlit
# =============================
def main():
    st.title("⚽ ESPN Soccer - Elite Master")
    st.markdown("Sistema avançado de monitoramento de partidas de futebol")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📊 Exibição")
        top_n = st.selectbox("Top N Jogos", [3, 5, 10], index=0)
        linhas_exibir = st.slider("Linhas na tabela", 1, 50, 10)
        
        st.subheader("🏆 Ligas")
        st.markdown("Selecione as ligas para buscar:")
        
        ligas_selecionadas = st.multiselect(
            "Selecione as ligas:",
            options=list(LIGAS_ESPN.keys()),
            default=list(LIGAS_ESPN.keys())[:4],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.subheader("🛠️ Utilidades")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Limpar Cache", use_container_width=True):
                if os.path.exists(CACHE_JOGOS):
                    os.remove(CACHE_JOGOS)
                if os.path.exists(ALERTAS_PATH):
                    os.remove(ALERTAS_PATH)
                st.success("✅ Cache limpo!")
                time.sleep(1)
                st.rerun()
                
        with col2:
            if st.button("🔄 Testar API", use_container_width=True):
                test_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
                try:
                    response = requests.get(test_url, headers=HEADERS, timeout=10)
                    if response.status_code == 200:
                        st.success("✅ API ESPN funcionando!")
                    else:
                        st.error(f"❌ API retornou status {response.status_code}")
                except:
                    st.error("❌ Falha na conexão com API")

    # Conteúdo principal
    st.subheader("📅 Buscar Jogos")
    
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
            processar_jogos(data_str, ligas_selecionadas, top_n, linhas_exibir, buscar_hoje=False)

    if btn_hoje:
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos("", ligas_selecionadas, top_n, linhas_exibir, buscar_hoje=True)

    # Informações de ajuda
    with st.expander("ℹ️ Ajuda e Informações", expanded=True):
        st.markdown("""
        **📌 Como usar:**
        1. **Selecione as ligas** no menu lateral
        2. **Clique em "Jogos de Hoje"** para ver partidas atuais
        3. **Ou selecione uma data** e clique em "Buscar por Data"
        
        **🔧 Problemas Comuns:**
        - ⚠️ **API não disponível**: A ESPN limita dados futuros
        - 🎯 **Solução**: Use "Jogos de Hoje" para resultados imediatos
        - 🔄 **Cache corrompido**: Use "Limpar Cache" no menu lateral
        
        **🏆 Ligas Recomendadas para Teste:**
        - Premier League (eng.1) - Sempre tem jogos
        - MLS (usa.1) - Temporada longa
        - Liga MX (mex.1) - Boa cobertura
        """)

if __name__ == "__main__":
    main()
