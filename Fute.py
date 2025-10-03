# Futebol_Alertas_Ligas_Especificas_Funcional.py
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

# =============================
# CONFIGURAÇÕES
# =============================
# API-Football (RapidAPI) - OBRIGATÓRIA
API_FOOTBALL_KEY = st.secrets.get("API_FOOTBALL_KEY", "SUA_CHAVE_AQUI")  # Coloque sua chave REAL
HEADERS_API_FOOTBALL = {
    "X-RapidAPI-Key": API_FOOTBALL_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}
BASE_URL_API_FOOTBALL = "https://api-football-v1.p.rapidapi.com/v3"

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

# =============================
# LIGAS ESPECÍFICAS (IDs API-Football)
# =============================
LIGAS_ESPECIFICAS = {
    "MLS (EUA/Canadá)": 253,           # MLS
    "Liga MX (México)": 262,           # Liga MX
    "Série B (Brasil)": 73,            # Brazilian Serie B
    "Liga Árabe (Arábia Saudita)": 307 # Saudi Pro League
}

# =============================
# Funções de Cache
# =============================
def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_alertas():
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos():
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao():
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        response = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode":"Markdown"})
        if response.status_code != 200:
            st.warning(f"Erro Telegram: {response.status_code}")
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")

def enviar_alerta_telegram(home, away, data_str, hora_str, liga, tendencia, estimativa, confianca):
    msg = (
        f"⚽ *Alerta de Gols!*\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_str} ⏰ {hora_str} (BRT)\n"
        f"🔥 Tendência: {tendencia}\n"
        f"📊 Estimativa: {estimativa:.2f} gols\n"
        f"✅ Confiança: {confianca:.0f}%\n"
        f"📌 Liga: {liga}"
    )
    enviar_telegram(msg)

# =============================
# API-Football Functions
# =============================
def verificar_chave_api():
    """Verifica se a chave da API é válida"""
    if API_FOOTBALL_KEY == "SUA_CHAVE_AQUI" or not API_FOOTBALL_KEY:
        return False, "❌ Chave da API não configurada"
    
    try:
        url = f"{BASE_URL_API_FOOTBALL}/leagues"
        params = {"id": 253}  # Testa com MLS
        response = requests.get(url, headers=HEADERS_API_FOOTBALL, params=params, timeout=10)
        
        if response.status_code == 401:
            return False, "❌ Chave da API inválida"
        elif response.status_code == 429:
            return False, "❌ Limite de requisições excedido"
        elif response.status_code == 403:
            return False, "❌ Acesso proibido - verifique sua assinatura"
        elif response.status_code == 200:
            return True, "✅ Chave válida"
        else:
            return False, f"❌ Erro desconhecido: {response.status_code}"
            
    except Exception as e:
        return False, f"❌ Erro de conexão: {e}"

def obter_classificacao(liga_id):
    """Obtém classificação com cache inteligente"""
    cache = carregar_cache_classificacao()
    cache_key = f"class_{liga_id}"
    
    # Verificar se o cache é recente (menos de 2 horas)
    if cache_key in cache:
        cache_data = cache[cache_key]
        cache_time = datetime.fromisoformat(cache_data.get("timestamp", "2000-01-01"))
        if datetime.now() - cache_time < timedelta(hours=2):
            return cache_data.get("data", {})
    
    try:
        url = f"{BASE_URL_API_FOOTBALL}/standings"
        params = {"season": "2024", "league": liga_id}
        response = requests.get(url, headers=HEADERS_API_FOOTBALL, params=params, timeout=15)
        
        if response.status_code != 200:
            st.warning(f"Erro ao buscar classificação: {response.status_code}")
            return {}
        
        data = response.json()
        standings = {}
        
        if data.get("response"):
            for competition in data["response"]:
                league_standings = competition.get("league", {}).get("standings", [])
                for standing_group in league_standings:
                    for team in standing_group:
                        team_name = team.get("team", {}).get("name")
                        if team_name:
                            all_stats = team.get("all", {})
                            standings[team_name] = {
                                "scored": all_stats.get("goals", {}).get("for", 0),
                                "against": all_stats.get("goals", {}).get("against", 0),
                                "played": all_stats.get("played", 1)
                            }
        
        # Salvar no cache
        cache[cache_key] = {
            "data": standings,
            "timestamp": datetime.now().isoformat()
        }
        salvar_cache_classificacao(cache)
        
        return standings
        
    except Exception as e:
        st.warning(f"Erro obter classificação: {e}")
        return {}

def obter_jogos_do_dia(liga_id, data):
    """Obtém jogos do dia específico"""
    cache = carregar_cache_jogos()
    cache_key = f"jogos_{liga_id}_{data}"
    
    # Verificar cache (1 hora)
    if cache_key in cache:
        cache_data = cache[cache_key]
        cache_time = datetime.fromisoformat(cache_data.get("timestamp", "2000-01-01"))
        if datetime.now() - cache_time < timedelta(hours=1):
            return cache_data.get("data", [])
    
    try:
        url = f"{BASE_URL_API_FOOTBALL}/fixtures"
        params = {
            "date": data,
            "league": liga_id,
            "season": "2024",
            "timezone": "America/Sao_Paulo"
        }
        
        response = requests.get(url, headers=HEADERS_API_FOOTBALL, params=params, timeout=15)
        
        if response.status_code == 429:
            st.error("📊 Limite de requisições da API excedido. Aguarde 24h ou faça upgrade do plano.")
            return []
        elif response.status_code != 200:
            st.warning(f"Erro ao buscar jogos: {response.status_code}")
            return []
        
        data_json = response.json()
        jogos = data_json.get("response", [])
        
        # Salvar no cache
        cache[cache_key] = {
            "data": jogos,
            "timestamp": datetime.now().isoformat()
        }
        salvar_cache_jogos(cache)
        
        return jogos
        
    except Exception as e:
        st.warning(f"Erro ao obter jogos: {e}")
        return []

# =============================
# Cálculo de Tendência
# =============================
def calcular_tendencia(home, away, classificacao):
    """Calcula tendência de gols baseado na classificação"""
    if not classificacao:
        # Fallback quando não há dados
        return 2.5, 65, "Mais 2.5"
    
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})

    # Prevenir divisão por zero
    played_home = max(1, dados_home["played"])
    played_away = max(1, dados_away["played"])

    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away

    # Média ponderada
    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    # Ajustar confiança baseado na quantidade de jogos
    min_jogos = min(played_home, played_away)
    fator_confianca = min(1.0, min_jogos / 10)  # Máximo confiança após 10 jogos

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0) * 10) * fator_confianca
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0) * 10) * fator_confianca
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa) * 10) * fator_confianca

    return round(estimativa, 2), round(confianca), tendencia

# =============================
# Processamento de Jogos
# =============================
def processar_jogo(jogo, classificacao, liga_nome):
    """Processa um jogo individual e retorna dados"""
    fixture = jogo.get("fixture", {})
    teams = jogo.get("teams", {})
    home = teams.get("home", {}).get("name", "Desconhecido")
    away = teams.get("away", {}).get("name", "Desconhecido")
    
    # Converter data/hora para BRT
    try:
        date_utc = fixture.get("date", "")
        if date_utc:
            dt = datetime.fromisoformat(date_utc.replace('Z', '+00:00'))
            dt_brt = dt - timedelta(hours=3)
            data_str = dt_brt.strftime("%d/%m/%Y")
            hora_str = dt_brt.strftime("%H:%M")
        else:
            data_str, hora_str = "-", "-"
    except:
        data_str, hora_str = "-", "-"
    
    # Calcular tendência
    estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)
    
    return {
        "id": fixture.get("id"),
        "home": home,
        "away": away,
        "data": data_str,
        "hora": hora_str,
        "estimativa": estimativa,
        "confianca": confianca,
        "tendencia": tendencia,
        "liga": liga_nome,
        "status": fixture.get("status", {}).get("short", "NS")
    }

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alertas - MLS, Liga MX, Série B, Liga Árabe", layout="wide")
st.title("⚽ Sistema de Alertas - Ligas Específicas")

# Sidebar - Configuração
st.sidebar.header("🔧 Configuração")

# Verificar chave da API
st.sidebar.subheader("Verificação da API")
if st.sidebar.button("🔑 Verificar Chave da API"):
    status, mensagem = verificar_chave_api()
    st.sidebar.info(mensagem)

# Data seleção
data_selecionada = st.sidebar.date_input(
    "📅 Data dos Jogos:",
    value=datetime.today(),
    min_value=datetime.today() - timedelta(days=7),
    max_value=datetime.today() + timedelta(days=30)
)
data_str = data_selecionada.strftime("%Y-%m-%d")

# Seleção de ligas
st.sidebar.subheader("🏆 Ligas para Análise")
ligas_selecionadas = st.sidebar.multiselect(
    "Selecione as ligas:",
    options=list(LIGAS_ESPECIFICAS.keys()),
    default=list(LIGAS_ESPECIFICAS.keys())
)

# Botão principal
st.markdown("---")
if st.button("🚀 Buscar Partidas e Analisar", type="primary"):
    if not ligas_selecionadas:
        st.error("⚠️ Selecione pelo menos uma liga para análise.")
    elif API_FOOTBALL_KEY == "SUA_CHAVE_AQUI" or not API_FOOTBALL_KEY:
        st.error("""
        ❌ **Chave da API não configurada!**
        
        **Siga estes passos:**
        1. Acesse: https://rapidapi.com/api-sports/api/api-football/
        2. Cadastre-se e faça login
        3. Inscreva-se no plano **Basic (FREE)**
        4. Copie sua **X-RapidAPI-Key**
        5. Substitua `SUA_CHAVE_AQUI` pela sua chave real
        """)
    else:
        # Verificar chave primeiro
        status, mensagem = verificar_chave_api()
        if not status:
            st.error(f"""
            {mensagem}
            
            **Soluções:**
            - Verifique se copiou a chave corretamente
            - Confirme que se inscreveu no plano Basic
            - Aguarde 24h se excedeu o limite
            """)
        else:
            st.success("✅ Chave da API válida! Buscando dados...")
            
            total_jogos_processados = []
            
            for liga_nome in ligas_selecionadas:
                liga_id = LIGAS_ESPECIFICAS[liga_nome]
                
                with st.spinner(f"Buscando dados da {liga_nome}..."):
                    # Obter classificação
                    classificacao = obter_classificacao(liga_id)
                    
                    # Obter jogos do dia
                    jogos = obter_jogos_do_dia(liga_id, data_str)
                    
                    if not jogos:
                        st.warning(f"⏭️ Nenhum jogo encontrado para **{liga_nome}** em {data_str}")
                        continue
                    
                    st.subheader(f"🏆 {liga_nome} - {len(jogos)} jogos")
                    
                    # Processar cada jogo
                    for jogo in jogos:
                        jogo_data = processar_jogo(jogo, classificacao, liga_nome)
                        total_jogos_processados.append(jogo_data)
                        
                        # Exibir jogo
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.write(f"**{jogo_data['home']}** vs **{jogo_data['away']}**")
                            st.write(f"⏰ {jogo_data['hora']} | 🏆 {jogo_data['liga']}")
                        with col2:
                            st.write(f"🎯 {jogo_data['tendencia']}")
                            st.write(f"📊 {jogo_data['estimativa']} gols estimados")
                        with col3:
                            st.metric("Confiança", f"{jogo_data['confianca']}%")
                        
                        # Enviar alerta no Telegram
                        if jogo_data['confianca'] >= 60:  # Só envia alertas com boa confiança
                            enviar_alerta_telegram(
                                jogo_data['home'], jogo_data['away'],
                                jogo_data['data'], jogo_data['hora'],
                                jogo_data['liga'], jogo_data['tendencia'],
                                jogo_data['estimativa'], jogo_data['confianca']
                            )
                        
                        st.markdown("---")
            
            # Exibir resumo
            if total_jogos_processados:
                # Ordenar por confiança
                top_jogos = sorted(total_jogos_processados, key=lambda x: x['confianca'], reverse=True)[:5]
                
                st.success(f"✅ **{len(total_jogos_processados)}** jogos processados!")
                
                # Top 3 jogos
                st.subheader("🎯 Top 3 Jogos (Maior Confiança)")
                for i, jogo in enumerate(top_jogos[:3], 1):
                    st.info(
                        f"**{i}º** 🏟️ **{jogo['home']} vs {jogo['away']}** | "
                        f"🎯 {jogo['tendencia']} | "
                        f"✅ {jogo['confianca']}% | "
                        f"⏰ {jogo['hora']}"
                    )
                
                # Salvar alertas
                alertas = carregar_alertas()
                for jogo in total_jogos_processados:
                    alertas[str(jogo['id'])] = {
                        **jogo,
                        "conferido": False,
                        "timestamp": datetime.now().isoformat()
                    }
                salvar_alertas(alertas)
                
            else:
                st.error("❌ Nenhum jogo encontrado para as datas e ligas selecionadas.")

# Seção de instruções
st.sidebar.markdown("---")
st.sidebar.header("💡 Instruções")
st.sidebar.info("""
**Para funcionar:**
1. **Cadastre-se em:** rapidapi.com/api-sports/api/api-football/
2. **Plano Basic:** FREE (100 req/dia)
3. **Copie a chave** X-RapidAPI-Key
4. **Cole no código** (substitua SUA_CHAVE_AQUI)
5. **Selecione ligas** e data
6. **Clique em buscar**
""")

# Estatísticas
st.sidebar.header("📊 Estatísticas")
alertas = carregar_alertas()
if alertas:
    total = len(alertas)
    conferidos = sum(1 for a in alertas.values() if a.get('conferido'))
    st.sidebar.metric("Alertas Totais", total)
    st.sidebar.metric("Conferidos", conferidos)
