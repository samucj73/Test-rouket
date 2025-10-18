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
# Principais ligas (ESPN + MLS)
# =============================
LIGAS_ESPN = {
    "Brasileirão Série A": "br.1",
    "Brasileirão Série B": "br.2",
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "Liga MX (México)": "mex.1",
    "Saudi Pro League (Arábia)": "sau.1",
    "Copa Libertadores": "sud.1",
    "MLS (Estados Unidos)": "usa.1"
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
            
            # Verifica expiração do cache
            if caminho == CACHE_JOGOS and "_timestamp" in dados:
                if datetime.now().timestamp() - dados["_timestamp"] > CACHE_TIMEOUT:
                    return {}
            return dados
    except (json.JSONDecodeError, IOError, Exception) as e:
        st.error(f"Erro ao carregar {caminho}: {str(e)}")
        return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    """Salva dados em arquivo JSON com tratamento de erros"""
    try:
        # Cria diretório se não existir
        os.makedirs(os.path.dirname(caminho) if os.path.dirname(caminho) else '.', exist_ok=True)
        
        if caminho == CACHE_JOGOS:
            dados["_timestamp"] = datetime.now().timestamp()
        
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar {caminho}: {str(e)}")

def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    """Envia mensagem para o Telegram com tratamento de erros"""
    try:
        response = requests.get(
            BASE_URL_TG, 
            params={
                "chat_id": chat_id, 
                "text": msg, 
                "parse_mode": "HTML"
            }, 
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
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
    except (ValueError, TypeError) as e:
        st.error(f"Erro ao formatar hora {hora_utc}: {str(e)}")
        return None

# =============================
# Função para buscar jogos ESPN
# =============================
def buscar_jogos_espn(liga_slug: str, data: str) -> List[Dict]:
    """Busca jogos da API da ESPN com tratamento robusto de erros"""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        dados = response.json()
        partidas = []

        for evento in dados.get("events", []):
            try:
                hora = evento.get("date", "")
                hora_dt = formatar_hora_brasilia(hora)
                hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "-"
                
                competicao = evento.get("competitions", [{}])[0]
                times = competicao.get("competitors", [])
                
                if len(times) == 2:
                    home = times[0]["team"]["displayName"]
                    away = times[1]["team"]["displayName"]
                    placar_home = times[0].get("score", "0")
                    placar_away = times[1].get("score", "0")
                else:
                    home = away = "Time Desconhecido"
                    placar_home = placar_away = "0"

                partidas.append({
                    "home": home,
                    "away": away,
                    "placar": f"{placar_home} - {placar_away}",
                    "status": evento.get("status", {}).get("type", {}).get("description", "Agendado"),
                    "hora": hora_dt,
                    "hora_formatada": hora_format,
                    "liga": competicao.get("league", {}).get("name", liga_slug)
                })
            except Exception as e:
                st.warning(f"Erro ao processar evento: {str(e)}")
                continue
                
        return partidas
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na requisição para {liga_slug}: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Erro inesperado ao buscar jogos da ESPN: {str(e)}")
        return []

# =============================
# Funções de cache
# =============================
def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Função para processar jogos
# =============================
def processar_jogos(data_str: str, ligas_selecionadas: List[str], top_n: int, linhas_exibir: int):
    """Processa e exibe jogos, com envio para Telegram"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.info(f"⏳ Buscando jogos para {data_str}...")
    
    # Verificar cache primeiro
    cache = carregar_cache_jogos()
    cache_key = f"{data_str}_{'_'.join(ligas_selecionadas)}"
    
    todas_partidas = []
    total_ligas = len(ligas_selecionadas)
    
    for i, liga in enumerate(ligas_selecionadas):
        progress = (i + 1) / total_ligas
        progress_bar.progress(progress)
        status_text.info(f"⏳ Buscando {liga}... ({i+1}/{total_ligas})")
        
        partidas = buscar_jogos_espn(LIGAS_ESPN[liga], data_str)
        todas_partidas.extend(partidas)
        
        # Pequena pausa para não sobrecarregar a API
        time.sleep(0.5)
    
    if not todas_partidas:
        status_text.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
        return

    # Ordenar por horário
    todas_partidas.sort(key=lambda x: x['hora'] if x['hora'] else datetime.max)

    # Salvar cache
    cache[cache_key] = {
        "partidas": todas_partidas,
        "timestamp": datetime.now().timestamp()
    }
    salvar_cache_jogos(cache)

    # Preparar dados para exibição
    dados_exibicao = []
    for p in todas_partidas:
        dados_exibicao.append({
            "Liga": p['liga'],
            "Casa": p['home'],
            "Placar": p['placar'],
            "Visitante": p['away'],
            "Status": p['status'],
            "Horário": p['hora_formatada']
        })

    # Exibir tabela
    df = pd.DataFrame(dados_exibicao)
    if linhas_exibir < len(df):
        df = df.head(linhas_exibir)
    
    status_text.info(f"📊 Exibindo {len(df)} de {len(todas_partidas)} jogos encontrados")
    st.dataframe(df, use_container_width=True)

    # Top N jogos
    if st.button(f"📤 Enviar Top {top_n} para Telegram"):
        top_msg = f"⚽ TOP {top_n} JOGOS DO DIA - {data_str}\n\n"
        
        for i, p in enumerate(todas_partidas[:top_n], 1):
            top_msg += f"{i}. 🏟️ {p['home']} vs {p['away']}\n"
            top_msg += f"   📊 {p['placar']} | 🕒 {p['hora_formatada']} | 📍 {p['status']}\n\n"
        
        if enviar_telegram(top_msg, TELEGRAM_CHAT_ID_ALT2):
            st.success(f"✅ Top {top_n} jogos enviados para o Telegram!")
        else:
            st.error("❌ Erro ao enviar para o Telegram!")

# =============================
# Interface Streamlit
# =============================
def main():
    st.title("⚽ ESPN Soccer - Elite Master")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📊 Exibição")
        top_n = st.selectbox("Top N Jogos", [3, 5, 10], index=0)
        linhas_exibir = st.slider("Linhas na tabela", min_value=1, max_value=50, value=10, step=1)
        
        st.subheader("🏆 Ligas")
        st.markdown("Selecione as ligas para buscar:")
        ligas_selecionadas = st.multiselect(
            "Ligas:",
            list(LIGAS_ESPN.keys()),
            default=list(LIGAS_ESPN.keys())[:3],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.subheader("🛠️ Utilidades")
        if st.button("🧹 Limpar Cache", use_container_width=True):
            for f in [CACHE_JOGOS, ALERTAS_PATH]:
                if os.path.exists(f):
                    os.remove(f)
            st.success("✅ Cache limpo!")
            st.rerun()

    # Conteúdo principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        data_selecionada = st.date_input(
            "📅 Data dos Jogos", 
            value=datetime.today(),
            max_value=datetime.today() + timedelta(days=7)
        )
    
    with col2:
        st.markdown("### Ações")
        btn_buscar = st.button("🔍 Buscar Jogos", use_container_width=True)
        btn_atualizar = st.button("🔄 Atualizar Status", use_container_width=True)

    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Processar ações
    if btn_buscar:
        if not ligas_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma liga.")
        else:
            processar_jogos(data_str, ligas_selecionadas, top_n, linhas_exibir)
    
    if btn_atualizar:
        st.info("🔄 Atualizando status dos jogos...")
        # Aqui você pode adicionar a lógica real de atualização
        time.sleep(1)
        st.success("✅ Status atualizado!")

    # Exibir estatísticas rápidas
    st.markdown("---")
    st.subheader("📈 Estatísticas Rápidas")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Ligas Disponíveis", len(LIGAS_ESPN))
    with col2:
        st.metric("Ligas Selecionadas", len(ligas_selecionadas))
    with col3:
        st.metric("Data Selecionada", data_selecionada.strftime("%d/%m/%Y"))

if __name__ == "__main__":
    main()
