import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json
import os

# ==========================
# Configurações da API - AGORA CONFIGURÁVEL
# ==========================
def setup_api_config():
    """Configura as credenciais da API"""
    # Tenta carregar do ambiente primeiro
    api_key = os.getenv('FOOTBALL_API_KEY', 'f07fc89fcff4416db7f079fda478dd61')
    
    # Configuração via session state
    if 'api_config' not in st.session_state:
        st.session_state.api_config = {
            'api_key': api_key,
            'base_url': 'https://v3.football.api-sports.io',
            'headers': {'x-apisports-key': api_key}
        }
    
    return st.session_state.api_config

# Inicializar configuração
API_CONFIG = setup_api_config()
BASE_URL = API_CONFIG['base_url']
HEADERS = API_CONFIG['headers']

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
    .config-section {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .debug-info {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #ffc107;
        font-family: monospace;
        font-size: 0.9rem;
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
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = {}

# ==========================
# Funções do Sistema CORRIGIDAS
# ==========================

def atualizar_config_api(nova_chave=None, nova_url=None):
    """Atualiza a configuração da API"""
    if nova_chave:
        st.session_state.api_config['api_key'] = nova_chave
        st.session_state.api_config['headers']['x-apisports-key'] = nova_chave
    
    if nova_url:
        st.session_state.api_config['base_url'] = nova_url
    
    # Atualizar variáveis globais
    global BASE_URL, HEADERS
    BASE_URL = st.session_state.api_config['base_url']
    HEADERS = st.session_state.api_config['headers']
    
    return st.session_state.api_config

def verificar_status_api_detalhado():
    """Verifica o status da API com tratamento de erro robusto"""
    try:
        url = f"{BASE_URL}/status"
        st.session_state.debug_info['status_url'] = url
        st.session_state.debug_info['status_headers'] = HEADERS
        
        response = requests.get(url, headers=HEADERS, timeout=15)
        st.session_state.debug_info['status_response_code'] = response.status_code
        st.session_state.debug_info['status_response_headers'] = dict(response.headers)
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.debug_info['status_response_data'] = data
            
            # Acesso SEGURO aos dados da resposta
            if "response" in data and isinstance(data["response"], dict):
                response_data = data["response"]
                requests_info = response_data.get("requests", {})
                
                st.session_state.api_status = {
                    "requests_current": requests_info.get("current", 0),
                    "requests_limit_day": requests_info.get("limit_day", 100),
                    "requests_remaining": requests_info.get("limit_day", 100) - requests_info.get("current", 0),
                    "online": True,
                    "message": "✅ API conectada com sucesso",
                    "response_time": response.elapsed.total_seconds()
                }
                return True, "Conexão bem-sucedida"
            else:
                # Estrutura diferente do esperado, mas a API respondeu
                st.session_state.api_status = {
                    "online": True,
                    "message": "✅ API respondeu (estrutura diferente)",
                    "response_time": response.elapsed.total_seconds(),
                    "raw_data": data
                }
                return True, "API respondeu (estrutura diferente do esperado)"
                
        elif response.status_code == 401:
            st.session_state.api_status = {
                "online": False, 
                "error": "Erro 401 - Chave da API inválida ou expirada",
                "details": "Verifique se a chave está correta e se sua assinatura está ativa"
            }
            return False, "Chave API inválida"
            
        elif response.status_code == 403:
            st.session_state.api_status = {
                "online": False, 
                "error": "Erro 403 - Acesso negado",
                "details": "Sua chave não tem permissão para acessar este endpoint"
            }
            return False, "Acesso negado"
            
        elif response.status_code == 429:
            st.session_state.api_status = {
                "online": False, 
                "error": "Erro 429 - Limite de requisições excedido",
                "details": "Você atingiu o limite diário de requisições. Tente novamente amanhã ou faça upgrade do plano."
            }
            return False, "Limite excedido"
            
        elif response.status_code == 500:
            st.session_state.api_status = {
                "online": False, 
                "error": "Erro 500 - Problema no servidor da API",
                "details": "Problema temporário no servidor. Tente novamente em alguns minutos."
            }
            return False, "Erro do servidor"
            
        else:
            st.session_state.api_status = {
                "online": False, 
                "error": f"Erro {response.status_code}",
                "details": f"Resposta da API: {response.text[:200]}..."
            }
            return False, f"Erro HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        st.session_state.api_status = {
            "online": False, 
            "error": "Timeout - A API não respondeu a tempo",
            "details": "A conexão com a API demorou muito. Verifique sua internet ou tente novamente."
        }
        return False, "Timeout na conexão"
        
    except requests.exceptions.ConnectionError:
        st.session_state.api_status = {
            "online": False, 
            "error": "Erro de conexão - Não foi possível conectar à API",
            "details": f"Verifique sua conexão com a internet e se a URL está correta: {BASE_URL}"
        }
        return False, "Erro de conexão"
        
    except Exception as e:
        st.session_state.api_status = {
            "online": False, 
            "error": f"Erro inesperado: {str(e)}",
            "details": "Ocorreu um erro inesperado. Verifique os logs para mais detalhes."
        }
        st.session_state.debug_info['status_exception'] = str(e)
        return False, f"Erro inesperado: {str(e)}"

@st.cache_data(ttl=3600)
def carregar_ligas():
    """Carrega todas as ligas disponíveis com tratamento de erro"""
    try:
        url = f"{BASE_URL}/leagues"
        st.session_state.debug_info['leagues_url'] = url
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        st.session_state.debug_info['leagues_response_code'] = response.status_code
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.debug_info['leagues_response_data'] = data
            
            # Acesso seguro aos dados
            if "response" in data and isinstance(data["response"], list):
                ligas = []
                for l in data["response"]:
                    # Verificar estrutura esperada
                    if isinstance(l, dict) and "league" in l and "country" in l:
                        liga_info = {
                            "id": l["league"].get("id", 0),
                            "nome": l["league"].get("name", "Desconhecido"),
                            "pais": l["country"].get("name", "Desconhecido"),
                            "tipo": l["league"].get("type", "Desconhecido"),
                            "logo": l["league"].get("logo", ""),
                            "temporada_atual": l["seasons"][0].get("year", None) if l.get("seasons") else None
                        }
                        ligas.append(liga_info)
                return ligas
            else:
                st.error("❌ Estrutura de resposta inesperada para ligas")
                return []
        else:
            st.error(f"❌ Erro ao carregar ligas: {response.status_code}")
            st.session_state.debug_info['leagues_error'] = response.text
            return []
    except Exception as e:
        st.error(f"❌ Erro de conexão: {e}")
        st.session_state.debug_info['leagues_exception'] = str(e)
        return []

def testar_endpoint_simples():
    """Testa um endpoint simples para verificar a conectividade"""
    try:
        # Testa um endpoint leve - países
        url = f"{BASE_URL}/countries"
        st.session_state.debug_info['test_url'] = url
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        st.session_state.debug_info['test_response_code'] = response.status_code
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.debug_info['test_response_data'] = data
            return True, response.status_code
        else:
            st.session_state.debug_info['test_error'] = response.text
            return False, response.status_code
    except Exception as e:
        st.session_state.debug_info['test_exception'] = str(e)
        return False, str(e)

def debug_verificar_estrutura_resposta():
    """Função especial para debug da estrutura da resposta"""
    try:
        url = f"{BASE_URL}/status"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        debug_info = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'content_type': response.headers.get('content-type'),
            'text_sample': response.text[:500] if response.text else "Vazio",
        }
        
        if response.status_code == 200:
            try:
                data = response.json()
                debug_info['json_keys'] = list(data.keys()) if isinstance(data, dict) else "Não é dict"
                debug_info['full_structure'] = str(data)
            except Exception as e:
                debug_info['json_error'] = str(e)
        
        return debug_info
    except Exception as e:
        return {'exception': str(e)}

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
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Verificar API", use_container_width=True):
            with st.spinner("Verificando conexão..."):
                sucesso, mensagem = verificar_status_api_detalhado()
                if sucesso:
                    st.success("✅ API Conectada")
                else:
                    st.error(f"❌ {mensagem}")
                time.sleep(1)
    
    with col2:
        if st.button("🧪 Teste Rápido", use_container_width=True):
            with st.spinner("Testando conectividade..."):
                sucesso, status = testar_endpoint_simples()
                if sucesso:
                    st.success("✅ Conexão OK")
                else:
                    st.error(f"❌ Falha: {status}")
    
    # Exibir status atual
    if st.session_state.api_status.get("online"):
        status = st.session_state.api_status
        st.metric("Requisições Restantes", status.get("requests_remaining", "N/A"))
        if "requests_limit_day" in status:
            progresso = status["requests_remaining"] / status["requests_limit_day"]
            st.progress(progresso)
            if progresso < 0.2:
                st.warning("⚠️ Poucas requisições restantes")
    else:
        st.error("❌ API Offline")
        if "error" in st.session_state.api_status:
            st.error(st.session_state.api_status["error"])
    
    st.divider()
    
    # Carregar Ligas
    st.subheader("🏆 Ligas Disponíveis")
    if st.button("📥 Carregar Ligas", use_container_width=True):
        with st.spinner("Carregando catálogo..."):
            ligas = carregar_ligas()
            if ligas:
                st.success(f"✅ {len(ligas)} ligas")
            else:
                st.error("❌ Falha ao carregar ligas")
    
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
    liga_id = None
    liga_info = None
    
    if ligas:
        ligas_principais = [
            "Premier League", "La Liga", "Serie A", "Bundesliga", 
            "Ligue 1", "Primeira Liga", "MLS", "Liga MX", 
            "Brasileiro Série A", "Brasileiro Série B"
        ]
        
        ligas_filtradas = [l for l in ligas if any(nome in l["nome"] for nome in ligas_principais)]
        nomes_ligas = [f"{l['nome']} ({l['pais']})" for l in ligas_filtradas]
        
        if nomes_ligas:
            liga_selecionada_nome = st.selectbox("Selecione a liga:", options=nomes_ligas)
            liga_index = nomes_ligas.index(liga_selecionada_nome)
            liga_id = ligas_filtradas[liga_index]["id"]
            liga_info = ligas_filtradas[liga_index]
        else:
            st.info("Nenhuma liga principal encontrada")
    
    st.divider()
    st.subheader("🚀 Ações Rápidas")
    
    if st.button("📊 Buscar Dados", type="primary", use_container_width=True):
        if liga_id and st.session_state.api_status.get("online"):
            with st.spinner("Buscando dados..."):
                # Simular busca de dados
                time.sleep(2)
                st.session_state.ultima_busca = datetime.now()
                st.success("✅ Dados carregados!")
        else:
            st.warning("⚠️ Configure a API e selecione uma liga")

# ==========================
# Painel Principal - ABAS
# ==========================

# Abas Principais
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Análise", "📊 Estatísticas", "🔧 Configurações", "🐛 Debug"])

with tab1:
    st.header("🔎 Análise de Jogos")
    
    if not st.session_state.api_status.get("online"):
        st.error("""
        ⚠️ **API não conectada**
        
        Para usar a análise de jogos:
        1. Vá para a aba **🔧 Configurações**
        2. Configure sua chave da API
        3. Teste a conexão
        4. Volte para esta aba
        """)
    else:
        st.info("🔍 Selecione uma data e liga no painel lateral para analisar jogos")
        
        # Exemplo de card de jogo (simulado)
        if st.button("🔄 Carregar Jogos de Exemplo"):
            st.success("✅ Dados de exemplo carregados!")
            
            # Card de exemplo
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.markdown("### Time Casa")
                st.write("⚽ Média: 1.8 | 🛡️ Sofre: 1.2")
                st.write("📊 5V-3E-2D")
            
            with col2:
                st.markdown("<div class='alert-high'>🔥 ALTA - Mais 2.5</div>", unsafe_allow_html=True)
                st.write("**Estimativa: 3.2 gols**")
                st.caption("⏰ 20:00 | 🏟️ Estádio")
            
            with col3:
                st.markdown("### Time Fora")
                st.write("⚽ Média: 1.4 | 🛡️ Sofre: 1.6")
                st.write("📊 4V-4E-2D")
            
            st.divider()

with tab2:
    st.header("📊 Estatísticas e Visualizações")
    
    if not st.session_state.api_status.get("online"):
        st.warning("Conecte à API para ver estatísticas em tempo real")
    
    # Gráficos de exemplo
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de exemplo 1
        df_exemplo = pd.DataFrame({
            'Time': ['Time A', 'Time B', 'Time C', 'Time D', 'Time E'],
            'Pontos': [45, 42, 38, 35, 30],
            'Gols': [52, 48, 45, 40, 35]
        })
        
        fig1 = px.bar(df_exemplo, x='Time', y='Pontos', title='Pontuação dos Times')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # Gráfico de exemplo 2
        fig2 = px.scatter(df_exemplo, x='Gols', y='Pontos', size='Pontos', 
                         color='Time', title='Relação Gols x Pontos')
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.header("🔧 Configurações da API")
    
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    st.subheader("🔑 Credenciais da API")
    
    # Configuração da URL da API
    api_url = st.text_input(
        "URL da API:",
        value=BASE_URL,
        help="URL base da API Football"
    )
    
    # Configuração da Chave da API
    api_key = st.text_input(
        "Chave da API:",
        value=API_CONFIG['api_key'],
        type="password",
        help="Sua chave pessoal da API Football"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Salvar Configurações", use_container_width=True):
            novo_config = atualizar_config_api(api_key, api_url)
            st.success("✅ Configurações salvas!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Restaurar Padrão", use_container_width=True):
            default_config = atualizar_config_api('f07fc89fcff4416db7f079fda478dd61', 'https://v3.football.api-sports.io')
            st.success("✅ Configurações padrão restauradas!")
            st.rerun()
    
    with col3:
        if st.button("🔍 Testar Conexão", use_container_width=True):
            with st.spinner("Testando conexão..."):
                # Atualizar configurações primeiro
                atualizar_config_api(api_key, api_url)
                # Testar conexão
                sucesso, mensagem = verificar_status_api_detalhado()
                
                if sucesso:
                    st.success(f"✅ {mensagem}")
                    status = st.session_state.api_status
                    if "response_time" in status:
                        st.metric("Tempo de Resposta", f"{status['response_time']:.2f}s")
                    if "requests_remaining" in status:
                        st.metric("Requisições Restantes", status["requests_remaining"])
                else:
                    st.error(f"❌ {mensagem}")
                    if "details" in st.session_state.api_status:
                        st.error(st.session_state.api_status["details"])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Diagnóstico detalhado
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    st.subheader("🔍 Diagnóstico de Conexão")
    
    if st.button("🩺 Executar Diagnóstico Completo"):
        with st.spinner("Executando diagnósticos..."):
            
            # Teste 1: Conexão básica
            st.write("**1. Teste de conectividade básica...**")
            sucesso, status = testar_endpoint_simples()
            if sucesso:
                st.success("✅ Conectividade básica: OK")
            else:
                st.error(f"❌ Conectividade básica: FALHA - {status}")
            
            # Teste 2: Endpoint de status
            st.write("**2. Teste do endpoint de status...**")
            sucesso, mensagem = verificar_status_api_detalhado()
            if sucesso:
                st.success(f"✅ Endpoint status: OK - {mensagem}")
            else:
                st.error(f"❌ Endpoint status: FALHA - {mensagem}")
            
            # Teste 3: Verificar chave da API
            st.write("**3. Verificação da chave da API...**")
            if api_key and len(api_key) == 32:
                st.success("✅ Formato da chave: VÁLIDO")
            else:
                st.error("❌ Formato da chave: INVÁLIDO - Deve ter 32 caracteres")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Gerenciamento de Cache
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    st.subheader("🗂️ Gerenciamento de Cache")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🧹 Limpar Cache de Dados", use_container_width=True):
            st.cache_data.clear()
            st.success("✅ Cache de dados limpo!")
    
    with col2:
        if st.button("🔄 Resetar Sessão", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ Sessão resetada!")
            st.rerun()
    
    # Informações do sistema
    st.subheader("📊 Informações do Sistema")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Ligas Carregadas", len(ligas) if ligas else 0)
        st.metric("Status API", "Online" if st.session_state.api_status.get("online") else "Offline")
    
    with col2:
        st.metric("Última Busca", 
                 st.session_state.ultima_busca.strftime("%H:%M") if st.session_state.ultima_busca else "Nunca")
        st.metric("Jogos em Cache", len(st.session_state.jogos_do_dia))
    
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.header("🐛 Debug e Logs do Sistema")
    
    st.subheader("🔧 Informações de Debug")
    
    if st.button("🔍 Analisar Estrutura da Resposta"):
        with st.spinner("Analisando resposta da API..."):
            debug_info = debug_verificar_estrutura_resposta()
            
            st.markdown("### 📋 Resposta Bruta da API")
            st.markdown('<div class="debug-info">', unsafe_allow_html=True)
            st.json(debug_info)
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("### 📊 Debug Info da Sessão")
    if st.session_state.debug_info:
        st.markdown('<div class="debug-info">', unsafe_allow_html=True)
        st.json(st.session_state.debug_info)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Nenhuma informação de debug disponível")
    
    st.markdown("### 🗑️ Limpar Debug")
    if st.button("🧹 Limpar Logs de Debug"):
        st.session_state.debug_info = {}
        st.success("Logs de debug limpos!")
        st.rerun()

# ==========================
# Rodapé
# ==========================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "🔮 **Dashboard Futebol Pro** | "
    "Desenvolvido com Streamlit | "
    f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    "</div>", 
    unsafe_allow_html=True
)

# ==========================
# Inicialização Automática
# ==========================
if st.session_state.api_status.get("online") == False and st.session_state.api_status.get("error") == "Não verificado":
    # Tentar verificação automática ao carregar
    verificar_status_api_detalhado()
