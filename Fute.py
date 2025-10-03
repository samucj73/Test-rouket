import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json

# ==========================
# Configurações da API
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ==========================
# Configuração da Página
# ==========================
st.set_page_config(
    page_title="Dashboard Futebol Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================
# CSS Personalizado
# ==========================
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .alert-high {
        background-color: #ff4b4b;
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .alert-medium {
        background-color: #ffa500;
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .alert-low {
        background-color: #00cc96;
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .team-logo {
        max-width: 40px;
        max-height: 40px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================
# Sistema de Estado da Sessão
# ==========================
if 'api_status' not in st.session_state:
    st.session_state.api_status = "Não verificado"
if 'ligas_carregadas' not in st.session_state:
    st.session_state.ligas_carregadas = False
if 'dados_estatisticas' not in st.session_state:
    st.session_state.dados_estatisticas = {}
if 'ultima_busca' not in st.session_state:
    st.session_state.ultima_busca = None

# ==========================
# Funções do Sistema
# ==========================

def verificar_status_api():
    """Verifica o status da API e consumo"""
    try:
        url = f"{BASE_URL}/status"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            st.session_state.api_status = {
                "requests_current": data["response"]["requests"]["current"],
                "requests_limit_day": data["response"]["requests"]["limit_day"],
                "requests_remaining": data["response"]["requests"]["limit_day"] - data["response"]["requests"]["current"],
                "online": True
            }
            return True
        else:
            st.session_state.api_status = {"online": False, "error": f"Erro {response.status_code}"}
            return False
    except Exception as e:
        st.session_state.api_status = {"online": False, "error": str(e)}
        return False

@st.cache_data(ttl=3600)
def carregar_ligas():
    """Carrega todas as ligas disponíveis"""
    url = f"{BASE_URL}/leagues"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            ligas = []
            for l in data["response"]:
                liga_info = {
                    "id": l["league"]["id"],
                    "nome": l["league"]["name"],
                    "pais": l["country"]["name"],
                    "tipo": l["league"]["type"],
                    "logo": l["league"].get("logo", ""),
                    "temporada_atual": l["seasons"][0]["year"] if l["seasons"] else None
                }
                ligas.append(liga_info)
            st.session_state.ligas_carregadas = True
            return ligas
        else:
            st.error(f"❌ Erro ao carregar ligas: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"❌ Erro de conexão: {e}")
        return []

@st.cache_data(ttl=1800)
def buscar_estatisticas_liga(liga_id, temporada=None):
    """Busca estatísticas detalhadas da liga"""
    try:
        # Buscar temporada atual se não especificada
        if not temporada:
            url_ligas = f"{BASE_URL}/leagues?id={liga_id}"
            response_ligas = requests.get(url_ligas, headers=HEADERS, timeout=10)
            if response_ligas.status_code == 200:
                liga_data = response_ligas.json()["response"][0]
                temporada = liga_data["seasons"][0]["year"]
        
        # Buscar jogos da temporada
        url_fixtures = f"{BASE_URL}/fixtures?league={liga_id}&season={temporada}"
        response = requests.get(url_fixtures, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"Erro {response.status_code}"}
        
        jogos = response.json()["response"]
        times_stats = {}
        
        for jogo in jogos:
            fixture = jogo["fixture"]
            if fixture["status"]["short"] != "FT":
                continue
            
            home = jogo["teams"]["home"]
            away = jogo["teams"]["away"]
            home_goals = jogo["goals"]["home"]
            away_goals = jogo["goals"]["away"]
            
            # Inicializar times
            for time in [home, away]:
                if time["id"] not in times_stats:
                    times_stats[time["id"]] = {
                        "nome": time["name"],
                        "logo": time["logo"],
                        "jogos": 0,
                        "vitorias": 0,
                        "empates": 0,
                        "derrotas": 0,
                        "gols_marcados": 0,
                        "gols_sofridos": 0,
                        "pontos": 0
                    }
            
            # Atualizar estatísticas
            times_stats[home["id"]]["jogos"] += 1
            times_stats[away["id"]]["jogos"] += 1
            
            times_stats[home["id"]]["gols_marcados"] += home_goals
            times_stats[home["id"]]["gols_sofridos"] += away_goals
            times_stats[away["id"]]["gols_marcados"] += away_goals
            times_stats[away["id"]]["gols_sofridos"] += home_goals
            
            if home_goals > away_goals:
                times_stats[home["id"]]["vitorias"] += 1
                times_stats[home["id"]]["pontos"] += 3
                times_stats[away["id"]]["derrotas"] += 1
            elif home_goals < away_goals:
                times_stats[away["id"]]["vitorias"] += 1
                times_stats[away["id"]]["pontos"] += 3
                times_stats[home["id"]]["derrotas"] += 1
            else:
                times_stats[home["id"]]["empates"] += 1
                times_stats[home["id"]]["pontos"] += 1
                times_stats[away["id"]]["empates"] += 1
                times_stats[away["id"]]["pontos"] += 1
        
        # Calcular médias
        for time_id in times_stats:
            stats = times_stats[time_id]
            stats["media_gols_marcados"] = round(stats["gols_marcados"] / stats["jogos"], 2) if stats["jogos"] > 0 else 0
            stats["media_gols_sofridos"] = round(stats["gols_sofridos"] / stats["jogos"], 2) if stats["jogos"] > 0 else 0
            stats["saldo_gols"] = stats["gols_marcados"] - stats["gols_sofridos"]
        
        return {
            "temporada": temporada,
            "estatisticas": times_stats,
            "total_jogos_analisados": len([j for j in jogos if j["fixture"]["status"]["short"] == "FT"])
        }
        
    except Exception as e:
        return {"error": str(e)}

def buscar_jogos_data(data, liga_id=None):
    """Busca jogos de uma data específica"""
    try:
        url = f"{BASE_URL}/fixtures?date={data}"
        if liga_id:
            url += f"&league={liga_id}"
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()["response"]
        else:
            st.error(f"Erro ao buscar jogos: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return []

def calcular_tendencia(media_casa, media_fora):
    """Calcula tendência baseada nas estatísticas"""
    estimativa = media_casa + media_fora
    
    if estimativa >= 3.0:
        return "🔥 ALTA - Mais 2.5", estimativa, "high"
    elif estimativa >= 2.0:
        return "⚽ MÉDIA - Mais 1.5", estimativa, "medium"
    else:
        return "🛡️ BAIXA - Menos 2.5", estimativa, "low"

# ==========================
# Interface Principal
# ==========================

st.markdown('<h1 class="main-header">⚽ Dashboard Futebol Pro</h1>', unsafe_allow_html=True)

# ==========================
# Sidebar - Controles
# ==========================
with st.sidebar:
    st.header("🎮 Painel de Controle")
    
    # Verificação da API
    st.subheader("🔧 Status do Sistema")
    if st.button("🔄 Verificar Status da API"):
        with st.spinner("Verificando API..."):
            verificar_status_api()
            time.sleep(1)
    
    if st.session_state.api_status != "Não verificado":
        status = st.session_state.api_status
        if status["online"]:
            st.success("✅ API Online")
            st.metric("Requisições Restantes", status["requests_remaining"])
            st.progress(status["requests_remaining"] / status["requests_limit_day"])
        else:
            st.error("❌ API Offline")
    
    st.divider()
    
    # Carregar Ligas
    st.subheader("🏆 Ligas Disponíveis")
    if st.button("📥 Carregar Todas as Ligas"):
        with st.spinner("Carregando catálogo de ligas..."):
            ligas = carregar_ligas()
            st.success(f"✅ {len(ligas)} ligas carregadas")
    
    # Filtros
    st.subheader("🔍 Filtros de Busca")
    data_selecionada = st.date_input(
        "Selecione a data:",
        value=datetime.today(),
        min_value=datetime.today() - timedelta(days=30),
        max_value=datetime.today() + timedelta(days=365)
    )
    
    # Seleção de liga
    ligas = carregar_ligas()
    if ligas:
        nomes_ligas = [f"{l['nome']} ({l['pais']})" for l in ligas]
        liga_selecionada_nome = st.selectbox("Selecione a liga:", options=nomes_ligas)
        liga_index = nomes_ligas.index(liga_selecionada_nome)
        liga_id = ligas[liga_index]["id"]
        liga_info = ligas[liga_index]
    else:
        liga_id = None
        liga_info = None
    
    # Ações
    st.divider()
    st.subheader("🚀 Ações Rápidas")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Buscar Estatísticas", type="primary"):
            if liga_id:
                with st.spinner(f"Analisando estatísticas da liga..."):
                    stats = buscar_estatisticas_liga(liga_id)
                    st.session_state.dados_estatisticas = stats
                    st.session_state.ultima_busca = datetime.now()
            else:
                st.warning("Selecione uma liga primeiro")
    
    with col2:
        if st.button("🧹 Limpar Cache"):
            st.cache_data.clear()
            st.session_state.dados_estatisticas = {}
            st.success("Cache limpo!")

# ==========================
# Painel Principal
# ==========================

# Métricas Gerais
if liga_info:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Liga Selecionada", liga_info["nome"])
    with col2:
        st.metric("País", liga_info["pais"])
    with col3:
        st.metric("Tipo", liga_info["tipo"])
    with col4:
        if st.session_state.dados_estatisticas and "temporada" in st.session_state.dados_estatisticas:
            st.metric("Temporada", st.session_state.dados_estatisticas["temporada"])

# Abas Principais
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Análise de Jogos", "📈 Estatísticas da Liga", "🔍 Monitoramento", "⚙️ Configurações"])

with tab1:
    st.header("🔎 Análise de Jogos do Dia")
    
    if st.button("🔍 Buscar Jogos da Data"):
        with st.spinner("Buscando jogos..."):
            jogos = buscar_jogos_data(data_selecionada.strftime("%Y-%m-%d"), liga_id)
            
            if jogos:
                st.success(f"🎉 Encontrados {len(jogos)} jogos")
                
                for jogo in jogos:
                    fixture = jogo["fixture"]
                    liga = jogo["league"]
                    teams = jogo["teams"]
                    
                    # Buscar estatísticas dos times
                    stats_casa = st.session_state.dados_estatisticas.get("estatisticas", {}).get(teams["home"]["id"], {})
                    stats_fora = st.session_state.dados_estatisticas.get("estatisticas", {}).get(teams["away"]["id"], {})
                    
                    media_casa = stats_casa.get("media_gols_marcados", 0)
                    media_fora = stats_fora.get("media_gols_marcados", 0)
                    
                    tendencia, estimativa, nivel = calcular_tendencia(media_casa, media_fora)
                    
                    # Card do jogo
                    with st.container():
                        col1, col2, col3 = st.columns([2, 1, 2])
                        
                        with col1:
                            st.markdown(f"### {teams['home']['name']}")
                            if stats_casa:
                                st.write(f"⚽ Média: {media_casa} | 🛡️ Sofre: {stats_casa.get('media_gols_sofridos', 0)}")
                                st.write(f"📊 {stats_casa.get('vitorias', 0)}V-{stats_casa.get('empates', 0)}E-{stats_casa.get('derrotas', 0)}D")
                        
                        with col2:
                            st.markdown("**VS**")
                            st.markdown(f"<div class='alert-{nivel}'>{tendencia}</div>", unsafe_allow_html=True)
                            st.write(f"Estimativa: {estimativa:.2f} gols")
                            st.caption(f"Status: {fixture['status']['long']}")
                        
                        with col3:
                            st.markdown(f"### {teams['away']['name']}")
                            if stats_fora:
                                st.write(f"⚽ Média: {media_fora} | 🛡️ Sofre: {stats_fora.get('media_gols_sofridos', 0)}")
                                st.write(f"📊 {stats_fora.get('vitorias', 0)}V-{stats_fora.get('empates', 0)}E-{stats_fora.get('derrotas', 0)}D")
                        
                        st.divider()
            else:
                st.warning("Nenhum jogo encontrado para esta data")

with tab2:
    st.header("📊 Estatísticas Detalhadas da Liga")
    
    if st.session_state.dados_estatisticas and "estatisticas" in st.session_state.dados_estatisticas:
        stats = st.session_state.dados_estatisticas["estatisticas"]
        
        # Converter para DataFrame
        dados_tabela = []
        for time_id, time_stats in stats.items():
            dados_tabela.append({
                "Time": time_stats["nome"],
                "Jogos": time_stats["jogos"],
                "Vitórias": time_stats["vitorias"],
                "Empates": time_stats["empates"],
                "Derrotas": time_stats["derrotas"],
                "Pontos": time_stats["pontos"],
                "Gols Marcados": time_stats["gols_marcados"],
                "Gols Sofridos": time_stats["gols_sofridos"],
                "Saldo": time_stats["saldo_gols"],
                "Média Gols": time_stats["media_gols_marcados"]
            })
        
        df = pd.DataFrame(dados_tabela)
        df = df.sort_values("Pontos", ascending=False)
        
        # Tabela de classificação
        st.subheader("🏆 Tabela de Classificação")
        st.dataframe(df, use_container_width=True)
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de pontos
            fig_pontos = px.bar(
                df.head(10),
                x="Time",
                y="Pontos",
                title="Top 10 Times por Pontos",
                color="Pontos"
            )
            st.plotly_chart(fig_pontos, use_container_width=True)
        
        with col2:
            # Gráfico de gols
            fig_gols = px.scatter(
                df,
                x="Gols Marcados",
                y="Gols Sofridos",
                size="Pontos",
                color="Pontos",
                hover_data=["Time"],
                title="Relação Gols Marcados vs Sofridos"
            )
            st.plotly_chart(fig_gols, use_container_width=True)
    
    else:
        st.info("👆 Clique em 'Buscar Estatísticas' no painel lateral para carregar os dados")

with tab3:
    st.header("🔍 Monitoramento do Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Status da API")
        if st.session_state.api_status != "Não verificado":
            status = st.session_state.api_status
            if status["online"]:
                st.success("✅ Conectado")
                
                # Métricas de uso
                fig_uso = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = status["requests_current"],
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "Requisições Hoje"},
                    delta = {'reference': status["requests_limit_day"]},
                    gauge = {
                        'axis': {'range': [None, status["requests_limit_day"]]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, status["requests_limit_day"] * 0.7], 'color': "lightgray"},
                            {'range': [status["requests_limit_day"] * 0.7, status["requests_limit_day"] * 0.9], 'color': "yellow"},
                            {'range': [status["requests_limit_day"] * 0.9, status["requests_limit_day"]], 'color': "red"}
                        ]
                    }
                ))
                st.plotly_chart(fig_uso, use_container_width=True)
            else:
                st.error("❌ Desconectado")
        else:
            st.warning("⚠️ Status não verificado")
    
    with col2:
        st.subheader("📊 Estatísticas de Busca")
        if st.session_state.ultima_busca:
            st.metric("Última Busca", st.session_state.ultima_busca.strftime("%H:%M:%S"))
        
        if st.session_state.dados_estatisticas:
            stats = st.session_state.dados_estatisticas
            st.metric("Times Analisados", len(stats.get("estatisticas", {})))
            st.metric("Jogos Processados", stats.get("total_jogos_analisados", 0))
            st.metric("Temporada", stats.get("temporada", "N/A"))

with tab4:
    st.header("⚙️ Configurações do Sistema")
    
    st.subheader("🔑 Configurações da API")
    api_key_nova = st.text_input("Chave da API:", value=API_KEY, type="password")
    
    st.subheader("🛠️ Gerenciamento de Cache")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Limpar Todo o Cache", type="secondary"):
            st.cache_data.clear()
            st.session_state.clear()
            st.success("Cache e estado limpos!")
    
    with col2:
        if st.button("📋 Informações do Cache"):
            st.write("Estado atual da sessão:")
            st.json({k: str(v) for k, v in st.session_state.items()})
    
    st.subheader("📁 Exportar Dados")
    if st.session_state.dados_estatisticas:
        if st.button("💾 Exportar Estatísticas (JSON)"):
            data_str = json.dumps(st.session_state.dados_estatisticas, indent=2, ensure_ascii=False)
            st.download_button(
                label="⬇️ Baixar JSON",
                data=data_str,
                file_name=f"estatisticas_futebol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

# ==========================
# Rodapé
# ==========================
st.markdown("---")
st.markdown(
    "🔮 **Dashboard Futebol Pro** | "
    "Desenvolvido com Streamlit | "
    f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"
)
