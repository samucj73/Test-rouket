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
        text-align: center;
    }
    .alert-medium {
        background-color: #ffa500;
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
    }
    .alert-low {
        background-color: #00cc96;
        color: white;
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
    }
    .team-card {
        background-color: white;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 1rem;
    }
    .status-live {
        color: #ff4b4b;
        font-weight: bold;
    }
    .status-finished {
        color: #00cc96;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==========================
# Sistema de Estado da Sessão
# ==========================
if 'api_status' not in st.session_state:
    st.session_state.api_status = {"online": False, "error": "Não verificado"}
if 'ligas_carregadas' not in st.session_state:
    st.session_state.ligas_carregadas = False
if 'dados_estatisticas' not in st.session_state:
    st.session_state.dados_estatisticas = {}
if 'ultima_busca' not in st.session_state:
    st.session_state.ultima_busca = None
if 'jogos_do_dia' not in st.session_state:
    st.session_state.jogos_do_dia = []

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
            return ligas
        else:
            st.error(f"❌ Erro ao carregar ligas: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"❌ Erro de conexão: {e}")
        return []

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
        
        # Buscar standings (classificação) - mais eficiente
        url_standings = f"{BASE_URL}/standings?league={liga_id}&season={temporada}"
        response = requests.get(url_standings, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return {"error": f"Erro {response.status_code}"}
        
        data = response.json()
        times_stats = {}
        
        if data["response"]:
            standings = data["response"][0]["league"]["standings"][0]
            
            for team in standings:
                time_info = {
                    "nome": team["team"]["name"],
                    "logo": team["team"]["logo"],
                    "jogos": team["all"]["played"],
                    "vitorias": team["all"]["win"],
                    "empates": team["all"]["draw"],
                    "derrotas": team["all"]["lose"],
                    "gols_marcados": team["all"]["goals"]["for"],
                    "gols_sofridos": team["all"]["goals"]["against"],
                    "pontos": team["points"],
                    "media_gols_marcados": round(team["all"]["goals"]["for"] / max(team["all"]["played"], 1), 2),
                    "media_gols_sofridos": round(team["all"]["goals"]["against"] / max(team["all"]["played"], 1), 2),
                    "saldo_gols": team["all"]["goals"]["for"] - team["all"]["goals"]["against"]
                }
                times_stats[team["team"]["id"]] = time_info
        
        return {
            "temporada": temporada,
            "estatisticas": times_stats,
            "total_times": len(times_stats)
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

def calcular_tendencia(media_casa, media_fora, media_sofridos_casa, media_sofridos_fora):
    """Calcula tendência baseada nas estatísticas"""
    # Estimativa considerando ataque de um e defesa do outro
    estimativa_casa = (media_casa + media_sofridos_fora) / 2
    estimativa_fora = (media_fora + media_sofridos_casa) / 2
    estimativa_total = estimativa_casa + estimativa_fora
    
    if estimativa_total >= 3.2:
        return "🔥 ALTA - Mais 2.5", estimativa_total, "high", estimativa_casa, estimativa_fora
    elif estimativa_total >= 2.3:
        return "⚽ MÉDIA - Mais 1.5", estimativa_total, "medium", estimativa_casa, estimativa_fora
    else:
        return "🛡️ BAIXA - Menos 2.5", estimativa_total, "low", estimativa_casa, estimativa_fora

def formatar_data_hora(data_utc):
    """Formata data UTC para horário local"""
    try:
        dt = datetime.fromisoformat(data_utc.replace('Z', '+00:00'))
        dt_local = dt - timedelta(hours=3)  # Ajuste para BRT
        return dt_local.strftime("%d/%m %H:%M")
    except:
        return data_utc

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
    if st.button("🔄 Verificar Status da API", use_container_width=True):
        with st.spinner("Verificando API..."):
            if verificar_status_api():
                st.success("✅ API Conectada")
            else:
                st.error("❌ API Offline")
            time.sleep(1)
            st.rerun()
    
    if st.session_state.api_status["online"]:
        status = st.session_state.api_status
        st.metric("Requisições Restantes", status["requests_remaining"])
        st.progress(status["requests_remaining"] / status["requests_limit_day"])
    else:
        st.error("❌ API Offline")
    
    st.divider()
    
    # Carregar Ligas
    st.subheader("🏆 Ligas Disponíveis")
    if st.button("📥 Carregar Todas as Ligas", use_container_width=True):
        with st.spinner("Carregando catálogo de ligas..."):
            ligas = carregar_ligas()
            if ligas:
                st.success(f"✅ {len(ligas)} ligas carregadas")
            st.rerun()
    
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
        # Filtrar ligas principais
        ligas_principais = [
            "Premier League", "La Liga", "Serie A", "Bundesliga", 
            "Ligue 1", "Primeira Liga", "Serie A", "MLS",
            "Liga MX", "Brasileiro Série A", "Brasileiro Série B"
        ]
        
        ligas_filtradas = [l for l in ligas if any(nome in l["nome"] for nome in ligas_principais)]
        nomes_ligas = [f"{l['nome']} ({l['pais']})" for l in ligas_filtradas]
        
        liga_selecionada_nome = st.selectbox("Selecione a liga:", options=nomes_ligas)
        liga_index = nomes_ligas.index(liga_selecionada_nome)
        liga_id = ligas_filtradas[liga_index]["id"]
        liga_info = ligas_filtradas[liga_index]
    else:
        liga_id = None
        liga_info = None
    
    # Ações
    st.divider()
    st.subheader("🚀 Ações Rápidas")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Buscar Estatísticas", type="primary", use_container_width=True):
            if liga_id:
                with st.spinner(f"Analisando estatísticas da liga..."):
                    stats = buscar_estatisticas_liga(liga_id)
                    st.session_state.dados_estatisticas = stats
                    st.session_state.ultima_busca = datetime.now()
                    st.success("✅ Estatísticas carregadas!")
                    st.rerun()
            else:
                st.warning("Selecione uma liga primeiro")
    
    with col2:
        if st.button("🔍 Buscar Jogos", use_container_width=True):
            if liga_id:
                with st.spinner("Buscando jogos..."):
                    jogos = buscar_jogos_data(data_selecionada.strftime("%Y-%m-%d"), liga_id)
                    st.session_state.jogos_do_dia = jogos
                    st.success(f"✅ {len(jogos)} jogos encontrados!")
                    st.rerun()
            else:
                st.warning("Selecione uma liga primeiro")
    
    if st.button("🧹 Limpar Cache", use_container_width=True):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Cache limpo!")
        st.rerun()

# ==========================
# Painel Principal
# ==========================

# Verificação inicial da API
if st.session_state.api_status["online"] == False and st.session_state.api_status["error"] == "Não verificado":
    verificar_status_api()

# Métricas Gerais
col1, col2, col3, col4 = st.columns(4)
with col1:
    if liga_info:
        st.metric("Liga Selecionada", liga_info["nome"])
    else:
        st.metric("Liga", "Não selecionada")

with col2:
    if liga_info:
        st.metric("País", liga_info["pais"])
    else:
        st.metric("País", "-")

with col3:
    if st.session_state.dados_estatisticas and "temporada" in st.session_state.dados_estatisticas:
        st.metric("Temporada", st.session_state.dados_estatisticas["temporada"])
    else:
        st.metric("Temporada", "-")

with col4:
    if st.session_state.ultima_busca:
        st.metric("Última Atualização", st.session_state.ultima_busca.strftime("%H:%M"))
    else:
        st.metric("Status", "Aguardando dados")

# Abas Principais
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Análise de Jogos", "📈 Estatísticas da Liga", "🔍 Monitoramento", "⚙️ Configurações"])

with tab1:
    st.header("🔎 Análise de Jogos do Dia")
    
    if st.session_state.jogos_do_dia:
        st.success(f"🎉 {len(st.session_state.jogos_do_dia)} jogos encontrados para {data_selecionada.strftime('%d/%m/%Y')}")
        
        for jogo in st.session_state.jogos_do_dia:
            fixture = jogo["fixture"]
            liga = jogo["league"]
            teams = jogo["teams"]
            goals = jogo["goals"]
            
            # Buscar estatísticas dos times
            stats_casa = st.session_state.dados_estatisticas.get("estatisticas", {}).get(teams["home"]["id"], {})
            stats_fora = st.session_state.dados_estatisticas.get("estatisticas", {}).get(teams["away"]["id"], {})
            
            media_casa = stats_casa.get("media_gols_marcados", 1.5)  # Fallback
            media_fora = stats_fora.get("media_gols_marcados", 1.5)
            media_sofridos_casa = stats_casa.get("media_gols_sofridos", 1.5)
            media_sofridos_fora = stats_fora.get("media_gols_sofridos", 1.5)
            
            tendencia, estimativa_total, nivel, estimativa_casa, estimativa_fora = calcular_tendencia(
                media_casa, media_fora, media_sofridos_casa, media_sofridos_fora
            )
            
            # Card do jogo
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 2])
                
                with col1:
                    st.markdown(f"### {teams['home']['name']}")
                    if stats_casa:
                        st.write(f"⚽ Ataque: {media_casa} | 🛡️ Defesa: {media_sofridos_casa}")
                        st.write(f"📊 {stats_casa.get('vitorias', 0)}V-{stats_casa.get('empates', 0)}E-{stats_casa.get('derrotas', 0)}D")
                    st.write(f"🎯 Esperado: {estimativa_casa:.2f} gols")
                
                with col2:
                    # Placar atual se o jogo estiver em andamento ou finalizado
                    status_class = "status-live" if fixture["status"]["short"] in ["1H", "2H", "HT", "ET"] else "status-finished"
                    placar = f"{goals['home']} - {goals['away']}" if goals['home'] is not None else "VS"
                    
                    st.markdown(f"<div style='text-align: center;'><h2>{placar}</h2></div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='alert-{nivel}'>{tendencia}</div>", unsafe_allow_html=True)
                    st.write(f"**Total esperado: {estimativa_total:.2f} gols**")
                    
                    # Informações do jogo
                    st.caption(f"⏰ {formatar_data_hora(fixture['date'])}")
                    st.caption(f"🏟️ {fixture['venue']['name']}" if fixture['venue'] else "📍 Local não informado")
                    st.markdown(f"<div class='{status_class}'>Status: {fixture['status']['long']}</div>", unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"### {teams['away']['name']}")
                    if stats_fora:
                        st.write(f"⚽ Ataque: {media_fora} | 🛡️ Defesa: {media_sofridos_fora}")
                        st.write(f"📊 {stats_fora.get('vitorias', 0)}V-{stats_fora.get('empates', 0)}E-{stats_fora.get('derrotas', 0)}D")
                    st.write(f"🎯 Esperado: {estimativa_fora:.2f} gols")
                
                st.divider()
    else:
        st.info("👆 Clique em 'Buscar Jogos' no painel lateral para carregar os jogos do dia")

with tab2:
    st.header("📊 Estatísticas Detalhadas da Liga")
    
    if st.session_state.dados_estatisticas and "estatisticas" in st.session_state.dados_estatisticas:
        stats = st.session_state.dados_estatisticas["estatisticas"]
        
        # Converter para DataFrame
        dados_tabela = []
        for time_id, time_stats in stats.items():
            dados_tabela.append({
                "Posição": len(dados_tabela) + 1,
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
        df["Posição"] = range(1, len(df) + 1)
        
        # Tabela de classificação
        st.subheader("🏆 Tabela de Classificação")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de pontos
            fig_pontos = px.bar(
                df.head(10),
                x="Time",
                y="Pontos",
                title="Top 10 Times por Pontos",
                color="Pontos",
                color_continuous_scale="viridis"
            )
            fig_pontos.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_pontos, use_container_width=True)
        
        with col2:
            # Gráfico de eficiência ofensiva/defensiva
            fig_eficiencia = px.scatter(
                df,
                x="Média Gols",
                y="Gols Sofridos",
                size="Pontos",
                color="Pontos",
                hover_data=["Time"],
                title="Eficiência: Ataque vs Defesa",
                color_continuous_scale="reds"
            )
            st.plotly_chart(fig_eficiencia, use_container_width=True)
    
    else:
        st.info("👆 Clique em 'Buscar Estatísticas' no painel lateral para carregar os dados da liga")

with tab3:
    st.header("🔍 Monitoramento do Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Status da API")
        if st.session_state.api_status["online"]:
            status = st.session_state.api_status
            
            # Gráfico de uso
            fig_uso = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = status["requests_current"],
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Requisições Hoje"},
                delta = {'reference': status["requests_limit_day"], 'decreasing': {'color': "green"}},
                gauge = {
                    'axis': {'range': [None, status["requests_limit_day"]]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, status["requests_limit_day"] * 0.7], 'color': "lightgray"},
                        {'range': [status["requests_limit_day"] * 0.7, status["requests_limit_day"] * 0.9], 'color': "yellow"},
                        {'range': [status["requests_limit_day"] * 0.9, status["requests_limit_day"]], 'color': "red"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': status["requests_limit_day"] * 0.9
                    }
                }
            ))
            fig_uso.update_layout(height=300)
            st.plotly_chart(fig_uso, use_container_width=True)
            
            st.metric("Requisições Usadas", status["requests_current"])
            st.metric("Limite Diário", status["requests_limit_day"])
            st.metric("Disponível", status["requests_remaining"])
            
        else:
            st.error("❌ API Offline")
            st.write(f"Erro: {st.session_state.api_status['error']}")
    
    with col2:
        st.subheader("📊 Estatísticas de Busca")
        
        if st.session_state.ultima_busca:
            st.metric("Última Busca", st.session_state.ultima_busca.strftime("%d/%m %H:%M"))
        
        if st.session_state.dados_estatisticas:
            stats = st.session_state.dados_estatisticas
            st.metric("Times na Liga", len(stats.get("estatisticas", {})))
            st.metric("Temporada", stats.get("temporada", "N/A"))
        
        if st.session_state.jogos_do_dia:
            st.metric("Jogos Hoje", len(st.session_state.jogos_do_dia))
        
        # Informações do cache
        st.subheader("💾 Cache do Sistema")
        st.metric("Ligas Carregadas", len(ligas) if ligas else 0)
        st.metric("Estado da Sessão", "Ativa" if st.session_state else "Inativa")

with tab4:
    st.header("⚙️ Configurações do Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔑 Configurações da API")
        st.info(f"API Base: {BASE_URL}")
        st.code(f"Chave: {API_KEY[:10]}...", language="text")
        
        # Teste de conexão
        if st.button("🧪 Testar Conexão API"):
            with st.spinner("Testando conexão..."):
                if verificar_status_api():
                    st.success("✅ Conexão estabelecida com sucesso!")
                else:
                    st.error("❌ Falha na conexão")
    
    with col2:
        st.subheader("🛠️ Gerenciamento de Cache")
        
        if st.button("🗑️ Limpar Todo o Cache", type="secondary", use_container_width=True):
            st.cache_data.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ Cache e estado limpos!")
            time.sleep(1)
            st.rerun()
        
        if st.button("📋 Estado do Sistema", use_container_width=True):
            st.write("**Estado atual da sessão:**")
            estado_limpo = {}
            for k, v in st.session_state.items():
                if k == 'dados_estatisticas':
                    estado_limpo[k] = f"Dados com {len(v.get('estatisticas', {}))} times" if v else "Vazio"
                elif k == 'jogos_do_dia':
                    estado_limpo[k] = f"{len(v)} jogos"
                else:
                    estado_limpo[k] = str(v)
            st.json(estado_limpo)
    
    st.subheader("📁 Exportar Dados")
    if st.session_state.dados_estatisticas:
        # Criar JSON para download
        dados_export = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "liga": liga_info["nome"] if liga_info else "N/A",
                "temporada": st.session_state.dados_estatisticas.get("temporada", "N/A")
            },
            "estatisticas": st.session_state.dados_estatisticas.get("estatisticas", {})
        }
        
        json_str = json.dumps(dados_export, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="💾 Baixar Estatísticas (JSON)",
            data=json_str,
            file_name=f"estatisticas_futebol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    else:
        st.warning("Nenhum dado disponível para exportar")

# ==========================
# Rodapé
# ==========================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown(
        "<div style='text-align: center;'>"
        "🔮 **Dashboard Futebol Pro** | "
        "Desenvolvido com Streamlit | "
        f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"
        "</div>", 
        unsafe_allow_html=True
    )
