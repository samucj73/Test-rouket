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
            
            if caminho == CACHE_JOGOS and "_timestamp" in dados:
                if datetime.now().timestamp() - dados["_timestamp"] > CACHE_TIMEOUT:
                    return {}
            return dados
    except Exception as e:
        st.error(f"Erro ao carregar {caminho}: {str(e)}")
    return {}

def salvar_json(caminho: str, dados: dict):
    """Salva dados em arquivo JSON com tratamento de erros"""
    try:
        if caminho == CACHE_JOGOS:
            dados["_timestamp"] = datetime.now().timestamp()
        
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar {caminho}: {str(e)}")

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
        # URL corrigida - algumas ligas usam formato diferente
        if liga_slug in ["ccm", "uefa.champions", "uefa.europa"]:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        else:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        
        params = {
            'dates': data,
            'limit': 100
        }
        
        response = requests.get(
            url, 
            params=params,
            headers=HEADERS,
            timeout=15
        )
        
        # Verifica se a resposta é válida
        if response.status_code == 400:
            st.warning(f"⚠️ API não disponível para {liga_slug} na data {data}")
            return []
            
        response.raise_for_status()
        dados = response.json()
        
        # Verifica se há eventos
        if not dados.get('events'):
            return []
            
        partidas = []

        for evento in dados.get("events", []):
            try:
                # Extrai informações básicas
                hora = evento.get("date", "")
                hora_dt = formatar_hora_brasilia(hora)
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
                st.warning(f"Erro ao processar evento em {liga_slug}: {str(e)}")
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
# Funções de cache
# =============================
def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Função para processar jogos - MELHORADA
# =============================
def processar_jogos(data_str: str, ligas_selecionadas: List[str], top_n: int, linhas_exibir: int):
    """Processa e exibe jogos, com envio para Telegram"""
    
    # Container para progresso
    progress_container = st.container()
    results_container = st.container()
    
    with progress_container:
        st.info(f"⏳ Buscando jogos para {datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')}...")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Verificar cache primeiro
    cache = carregar_cache_jogos()
    cache_key = f"{data_str}_{hash(frozenset(ligas_selecionadas))}"
    
    # Se tem cache válido, usa
    if cache_key in cache and datetime.now().timestamp() - cache[cache_key].get("_timestamp", 0) < CACHE_TIMEOUT:
        status_text.info("📦 Usando dados em cache...")
        todas_partidas = cache[cache_key].get("partidas", [])
    else:
        # Busca dados novos
        todas_partidas = []
        total_ligas = len(ligas_selecionadas)
        
        for i, liga in enumerate(ligas_selecionadas):
            progress = (i + 1) / total_ligas
            progress_bar.progress(progress)
            status_text.info(f"🔍 Buscando {liga}... ({i+1}/{total_ligas})")
            
            liga_slug = LIGAS_ESPN[liga]
            partidas = buscar_jogos_espn(liga_slug, data_str)
            
            if partidas:
                todas_partidas.extend(partidas)
                status_text.success(f"✅ {liga}: {len(partidas)} jogos")
            else:
                status_text.warning(f"⚠️ {liga}: Nenhum jogo encontrado")
            
            # Pequena pausa para não sobrecarregar a API
            time.sleep(1)
    
    if not todas_partidas:
        status_text.error("❌ Nenhum jogo encontrado para os critérios selecionados.")
        return

    # Ordenar por horário
    todas_partidas.sort(key=lambda x: x['hora'] if x['hora'] else datetime.max)

    # Salvar no cache
    cache[cache_key] = {
        "partidas": todas_partidas,
        "_timestamp": datetime.now().timestamp()
    }
    salvar_cache_jogos(cache)

    # Preparar dados para exibição
    with results_container:
        dados_exibicao = []
        for p in todas_partidas:
            dados_exibicao.append({
                "Liga": p['liga'],
                "Casa": p['home'][:20],  # Limita tamanho para display
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
            jogos_hoje = len([p for p in todas_partidas if p['hora'] and p['hora'].date() == datetime.today().date()])
            st.metric("Jogos Hoje", jogos_hoje)

        # Botão para enviar para Telegram
        st.markdown("---")
        st.subheader("📤 Enviar para Telegram")
        
        if st.button(f"🚀 Enviar Top {top_n} Jogos para Telegram", type="primary"):
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
        
        # Agrupar ligas por confiabilidade
        st.caption("**Ligas Principais (Mais Confiáveis)**")
        ligas_principais = [liga for liga in LIGAS_ESPN.keys() if liga not in ["Copa Libertadores", "Champions League", "Europa League"]]
        
        ligas_selecionadas = st.multiselect(
            "Selecione as ligas:",
            options=list(LIGAS_ESPN.keys()),
            default=ligas_principais[:4],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.subheader("🛠️ Utilidades")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Limpar Cache", use_container_width=True):
                for f in [CACHE_JOGOS, ALERTAS_PATH]:
                    if os.path.exists(f):
                        os.remove(f)
                st.success("✅ Cache limpo!")
                time.sleep(1)
                st.rerun()
                
        with col2:
            if st.button("🔄 Testar Conexão", use_container_width=True):
                test_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
                try:
                    response = requests.get(test_url, headers=HEADERS, timeout=10)
                    if response.status_code == 200:
                        st.success("✅ Conexão com API OK!")
                    else:
                        st.error(f"❌ API retornou status {response.status_code}")
                except:
                    st.error("❌ Falha na conexão com API")

    # Conteúdo principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        data_selecionada = st.date_input(
            "📅 Data dos Jogos", 
            value=datetime.today(),
            min_value=datetime.today() - timedelta(days=7),
            max_value=datetime.today() + timedelta(days=30)
        )
    
    with col2:
        st.markdown("### Ações")
        btn_buscar = st.button("🔍 Buscar Jogos", type="primary", use_container_width=True)
        btn_hoje = st.button("🎯 Jogos de Hoje", use_container_width=True)

    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Processar ações
    if btn_buscar or btn_hoje:
        if btn_hoje:
            data_str = datetime.today().strftime("%Y-%m-%d")
            st.info(f"🎯 Buscando jogos de hoje ({datetime.today().strftime('%d/%m/%Y')})")
            
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos(data_str, ligas_selecionadas, top_n, linhas_exibir)

    # Informações de ajuda
    with st.expander("ℹ️ Ajuda e Informações"):
        st.markdown("""
        **Problemas Comuns:**
        - ⚠️ Erro 400: A API da ESPN não tem dados para essa data/liga
        - 🔄 Limpe o cache se os dados estiverem desatualizados
        - 🌐 Verifique sua conexão com a internet
        
        **Ligas Recomendadas:**
        - Premier League, La Liga, Bundesliga - Mais confiáveis
        - MLS, Brasileirão - Boa cobertura
        - Copas internacionais - Podem ter limitações
        """)

if __name__ == "__main__":
    main()
