import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io

# =============================
# Configurações
# =============================

# APIs
NEWS_API_KEY = "2bac9541659c4450921136a9c2e9acbe"  # Sua NewsAPI key
FOOTBALL_API_KEY = "9058de85e3324bdb969adc005b5d918a"  # Football-Data.org
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

BASE_URL_NEWS = "https://newsapi.org/v2"
BASE_URL_FOOTBALL = "https://api.football-data.org/v4"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

HEADERS_FOOTBALL = {"X-Auth-Token": FOOTBALL_API_KEY}

# Constantes
CACHE_NOTICIAS = "cache_noticias.json"
CACHE_TIMEOUT = 1800  # 30 minutos em segundos

# Dicionário de Ligas para Filtro
LIGAS_DICT = {
    "Premier League": ["Premier League", "English Premier League", "EPL"],
    "La Liga": ["La Liga", "LaLiga", "Spanish La Liga"],
    "Bundesliga": ["Bundesliga", "German Bundesliga"],
    "Serie A": ["Serie A", "Serie A TIM", "Italian Serie A"],
    "Ligue 1": ["Ligue 1", "French Ligue 1"],
    "Champions League": ["Champions League", "UEFA Champions League", "UCL"],
    "Europa League": ["Europa League", "UEFA Europa League"],
    "Campeonato Brasileiro": ["Brasileirão", "Campeonato Brasileiro", "Brasileiro Série A"],
    "NBA": ["NBA", "National Basketball Association"]
}

# =============================
# Utilitários de Cache
# =============================

def garantir_diretorio():
    """Garante que o diretório de trabalho existe"""
    try:
        os.makedirs("data", exist_ok=True)
        return "data/"
    except:
        return ""

def carregar_json(caminho: str) -> dict:
    """Carrega JSON com cache"""
    try:
        caminho_completo = garantir_diretorio() + caminho
        
        if os.path.exists(caminho_completo):
            with open(caminho_completo, "r", encoding='utf-8') as f:
                dados = json.load(f)
            
            # Verificar expiração do cache
            agora = datetime.now().timestamp()
            if isinstance(dados, dict) and '_timestamp' in dados:
                if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                    return {}
            
            return dados
        else:
            dados_vazios = {}
            salvar_json(caminho, dados_vazios)
            return dados_vazios
            
    except (json.JSONDecodeError, IOError) as e:
        st.warning(f"⚠️ Erro ao carregar {caminho}, criando novo: {e}")
        dados_vazios = {}
        salvar_json(caminho, dados_vazios)
        return dados_vazios

def salvar_json(caminho: str, dados: dict):
    """Salva JSON com timestamp"""
    try:
        caminho_completo = garantir_diretorio() + caminho
        
        # Adicionar timestamp para cache
        if isinstance(dados, dict):
            dados['_timestamp'] = datetime.now().timestamp()
        
        os.makedirs(os.path.dirname(caminho_completo) if os.path.dirname(caminho_completo) else ".", exist_ok=True)
        
        with open(caminho_completo, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        
        return True
    except IOError as e:
        st.error(f"❌ Erro crítico ao salvar {caminho}: {e}")
        return False

# =============================
# Sistema de Notícias Esportivas
# =============================

def obter_noticias_football_data() -> list:
    """Obtém notícias específicas de futebol da API Football-Data.org"""
    noticias = []
    
    try:
        # A API Football-Data.org não tem endpoint de notícias público
        # Vamos usar as competições para criar notícias simuladas
        response = requests.get(f"{BASE_URL_FOOTBALL}/competitions", headers=HEADERS_FOOTBALL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            competicoes = data.get('competitions', [])[:5]  # Pegar 5 competições
            
            for comp in competicoes:
                noticias.append({
                    'titulo': f"🏆 {comp.get('name', 'Competição')} - Atualizações",
                    'descricao': f"Acompanhe as últimas atualizações da {comp.get('name', 'competição')}. Temporada em andamento com os melhores times.",
                    'url': f"https://www.football-data.org/competition/{comp.get('code', '')}",
                    'imagem': '',
                    'fonte': 'Football-Data.org',
                    'data': datetime.now().isoformat(),
                    'categoria': comp.get('name', 'Futebol'),
                    'prioridade': 'alta',
                    'id': f"football_{comp.get('id', len(noticias))}"
                })
    except Exception as e:
        st.warning(f"⚠️ Football-Data.org: {e}")
    
    return noticias

def testar_newsapi():
    """Testa a conexão com a NewsAPI"""
    try:
        # Testar com um termo simples primeiro
        params = {
            'q': 'futebol',
            'language': 'pt',
            'pageSize': 1,
            'apiKey': NEWS_API_KEY
        }
        
        response = requests.get(f"{BASE_URL_NEWS}/everything", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return True, f"✅ NewsAPI funcionando! Total: {data.get('totalResults', 0)} notícias"
        else:
            return False, f"❌ NewsAPI erro {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"❌ NewsAPI erro: {e}"

def obter_noticias_newsapi(termo: str, limite: int = 5, data_inicio: str = None, data_fim: str = None) -> list:
    """Obtém notícias da NewsAPI com um termo específico e filtro de data"""
    noticias = []
    
    try:
        params = {
            'q': termo,
            'language': 'pt',
            'sortBy': 'publishedAt',
            'pageSize': limite,
            'apiKey': NEWS_API_KEY
        }
        
        # Adicionar filtro de data se fornecido
        if data_inicio:
            params['from'] = data_inicio
        if data_fim:
            params['to'] = data_fim
        
        response = requests.get(f"{BASE_URL_NEWS}/everything", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'ok':
                for article in data.get('articles', []):
                    if article.get('title') and article['title'] != '[Removed]':
                        noticias.append({
                            'titulo': article['title'],
                            'descricao': article.get('description', 'Sem descrição disponível') or 'Sem descrição disponível',
                            'url': article.get('url', ''),
                            'imagem': article.get('urlToImage', ''),
                            'fonte': article.get('source', {}).get('name', 'NewsAPI'),
                            'data': article.get('publishedAt', datetime.now().isoformat()),
                            'categoria': 'Futebol',
                            'prioridade': 'media',
                            'id': f"newsapi_{hash(article.get('url', ''))}"
                        })
        else:
            st.warning(f"NewsAPI retornou status {response.status_code}")
            
    except Exception as e:
        st.warning(f"Erro NewsAPI para '{termo}': {e}")
    
    return noticias

def obter_noticias_esportivas(ligas_selecionadas: list = None, limite: int = 10, data_inicio: str = None, data_fim: str = None) -> list:
    """
    Obtém notícias esportivas filtradas por ligas e data
    """
    if ligas_selecionadas is None:
        ligas_selecionadas = []
    
    # Criar chave de cache incluindo as datas
    cache_key_parts = []
    if ligas_selecionadas:
        cache_key_parts.append('_'.join(ligas_selecionadas))
    else:
        cache_key_parts.append('todas')
    
    cache_key_parts.append(str(limite))
    
    if data_inicio:
        cache_key_parts.append(f"de_{data_inicio}")
    if data_fim:
        cache_key_parts.append(f"ate_{data_fim}")
    
    cache_key = '_'.join(cache_key_parts)
    
    cache = carregar_json(CACHE_NOTICIAS)
    
    # Verificar cache (30 minutos para notícias)
    if cache_key in cache:
        cache_data = cache[cache_key]
        if datetime.now().timestamp() - cache_data.get('_timestamp', 0) < CACHE_TIMEOUT:
            return cache_data.get('noticias', [])
    
    noticias = []
    
    try:
        # Testar NewsAPI primeiro
        status, mensagem = testar_newsapi()
        st.sidebar.info(mensagem)
        
        # Obter notícias do Football-Data.org
        noticias_football = obter_noticias_football_data()
        noticias.extend(noticias_football)
        
        # Se nenhuma liga selecionada, buscar notícias gerais
        if not ligas_selecionadas:
            # Notícias gerais de futebol
            noticias_gerais = obter_noticias_newsapi("futebol OR football", limite=8, data_inicio=data_inicio, data_fim=data_fim)
            noticias.extend(noticias_gerais)
        else:
            # Buscar notícias específicas por liga
            for liga in ligas_selecionadas:
                if liga in LIGAS_DICT:
                    # Usar o primeiro termo da lista para busca
                    termo_principal = LIGAS_DICT[liga][0]
                    noticias_liga = obter_noticias_newsapi(termo_principal, limite=4, data_inicio=data_inicio, data_fim=data_fim)
                    
                    # Marcar a categoria correta
                    for noticia in noticias_liga:
                        noticia['categoria'] = liga
                    
                    noticias.extend(noticias_liga)
        
        # Se ainda não temos notícias, usar fallback
        if not noticias:
            st.warning("⚠️ Nenhuma notícia encontrada nas APIs, usando conteúdo de fallback")
            noticias = obter_noticias_fallback(ligas_selecionadas)
        
        # Remover duplicatas baseado no título
        noticias_unicas = []
        titulos_vistos = set()
        for noticia in noticias:
            if noticia['titulo'] and noticia['titulo'] not in titulos_vistos:
                noticias_unicas.append(noticia)
                titulos_vistos.add(noticia['titulo'])
        
        # Ordenar por prioridade e data (mais recentes primeiro)
        noticias_unicas.sort(key=lambda x: (
            {'alta': 0, 'media': 1}.get(x.get('prioridade', 'media'), 2),
            x['data']
        ), reverse=True)
        
        # Limitar ao número solicitado
        noticias_unicas = noticias_unicas[:limite]
        
        # Salvar no cache
        cache[cache_key] = {
            'noticias': noticias_unicas,
            '_timestamp': datetime.now().timestamp()
        }
        salvar_json(CACHE_NOTICIAS, cache)
        
        return noticias_unicas
        
    except Exception as e:
        st.error(f"❌ Erro ao obter notícias: {e}")
        # Retornar notícias de fallback
        return obter_noticias_fallback(ligas_selecionadas)

def obter_noticias_fallback(ligas_selecionadas: list = None) -> list:
    """Notícias de fallback quando as APIs falham"""
    if ligas_selecionadas is None:
        ligas_selecionadas = ["Futebol Geral"]
    
    noticias_fallback = [
        {
            'titulo': '⚽ ELITE MASTER - Sistema de Notícias Esportivas',
            'descricao': 'Sistema avançado de notícias esportivas em tempo real. Mantenha-se informado sobre as principais notícias do mundo do futebol.',
            'url': 'https://t.me/elitemasteralertas',
            'imagem': '',
            'fonte': 'ELITE MASTER',
            'data': datetime.now().isoformat(),
            'categoria': 'Sistema',
            'prioridade': 'alta',
            'id': 'fallback_1'
        },
        {
            'titulo': '📰 Como obter mais notícias',
            'descricao': 'Para mais notícias em tempo real, verifique a configuração da sua API Key da NewsAPI.',
            'url': 'https://newsapi.org',
            'imagem': '',
            'fonte': 'ELITE MASTER',
            'data': datetime.now().isoformat(),
            'categoria': 'Ajuda',
            'prioridade': 'alta',
            'id': 'fallback_2'
        }
    ]
    
    # Adicionar notícias de fallback baseadas nas ligas selecionadas
    for liga in ligas_selecionadas[:3]:
        noticias_fallback.append({
            'titulo': f'🏆 {liga} - Notícias e Atualizações',
            'descricao': f'Acompanhe as últimas notícias e atualizações da {liga}. Em breve mais informações em tempo real.',
            'url': 'https://t.me/elitemasteralertas',
            'imagem': '',
            'fonte': 'ELITE MASTER',
            'data': datetime.now().isoformat(),
            'categoria': liga,
            'prioridade': 'media',
            'id': f'fallback_{liga}'
        })
    
    return noticias_fallback

# =============================
# Comunicação com Telegram
# =============================

def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID, disable_web_page_preview: bool = True) -> bool:
    """Envia mensagem para o Telegram"""
    try:
        params = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": str(disable_web_page_preview).lower()
        }
        response = requests.get(f"{BASE_URL_TG}/sendMessage", params=params, timeout=10)
        return response.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao enviar para Telegram: {e}")
        return False

def enviar_foto_telegram(photo_bytes: io.BytesIO, caption: str = "", chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia uma foto para o Telegram"""
    try:
        photo_bytes.seek(0)
        files = {"photo": ("noticia.png", photo_bytes, "image/png")}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        resp = requests.post(f"{BASE_URL_TG}/sendPhoto", data=data, files=files, timeout=15)
        return resp.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao enviar foto para Telegram: {e}")
        return False

def enviar_noticia_individual(noticia: dict, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia uma notícia individual para o Telegram"""
    try:
        # Formatar data
        try:
            data_obj = datetime.fromisoformat(noticia['data'].replace('Z', '+00:00'))
            data_formatada = data_obj.strftime('%d/%m/%Y %H:%M')
        except:
            data_formatada = "Hoje"
        
        emoji = "⚽" if "futebol" in noticia['categoria'].lower() else "🏀" if "nba" in noticia['categoria'].lower() else "📰"
        
        # Adicionar badge de prioridade
        prioridade_badge = "🔴 OFICIAL" if noticia.get('prioridade') == 'alta' else "🟡 MÍDIA"
        
        msg = (
            f"<b>{emoji} {noticia['categoria'].upper()}</b>\n"
            f"<b>{prioridade_badge}</b>\n\n"
            f"<b>📰 {noticia['titulo']}</b>\n\n"
            f"<b>📝 {noticia['descricao']}</b>\n\n"
            f"<b>📅 {data_formatada}</b>\n"
            f"<b>📊 Fonte: {noticia['fonte']}</b>\n\n"
            f"<a href='{noticia['url']}'>🔗 Ler notícia completa</a>\n\n"
            f"<b>🔥 ELITE MASTER NEWS</b>"
        )
        
        # Se tem imagem, tentar enviar como foto
        if noticia.get('imagem') and noticia['imagem'].startswith('http'):
            try:
                # Baixar imagem
                response = requests.get(noticia['imagem'], timeout=5)
                if response.status_code == 200:
                    photo_bytes = io.BytesIO(response.content)
                    return enviar_foto_telegram(photo_bytes, caption=msg, chat_id=chat_id)
            except:
                pass
        
        # Fallback para mensagem de texto
        return enviar_telegram(msg, chat_id)
        
    except Exception as e:
        st.error(f"❌ Erro ao enviar notícia: {e}")
        return False

def enviar_noticias_selecionadas(noticias_selecionadas: list, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia notícias selecionadas individualmente para o Telegram"""
    if not noticias_selecionadas:
        st.warning("Nenhuma notícia selecionada para enviar")
        return False
    
    try:
        sucessos = 0
        total = len(noticias_selecionadas)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, noticia in enumerate(noticias_selecionadas, 1):
            status_text.text(f"📤 Enviando notícia {i} de {total}: {noticia['titulo'][:50]}...")
            
            if enviar_noticia_individual(noticia, chat_id):
                sucessos += 1
                st.success(f"✅ Notícia {i} enviada com sucesso!")
            else:
                st.error(f"❌ Falha ao enviar notícia {i}")
            
            progress_bar.progress(i / total)
            
            # Pequena pausa entre notícias
            import time
            time.sleep(1)
        
        status_text.empty()
        progress_bar.empty()
        
        if sucessos == total:
            st.balloons()
            st.success(f"🎉 Todas as {sucessos} notícias foram enviadas com sucesso!")
        else:
            st.warning(f"⚠️ {sucessos} de {total} notícias enviadas com sucesso")
        
        return sucessos > 0
        
    except Exception as e:
        st.error(f"❌ Erro ao enviar notícias selecionadas: {e}")
        return False

# =============================
# Interface Streamlit
# =============================

def main():
    st.set_page_config(
        page_title="📰 Elite Master News", 
        page_icon="📰",
        layout="wide"
    )
    
    # Header
    st.title("📰 ELITE MASTER NEWS")
    st.markdown("### Sistema de Seleção de Notícias por Liga e Data")
    st.markdown("**Selecione as ligas, datas e escolha quais notícias enviar**")
    
    st.markdown("---")
    
    # Sidebar - Seleção de Ligas e Data
    with st.sidebar:
        st.header("🏆 Seleção de Ligas")
        
        st.subheader("⚽ Ligas de Futebol")
        ligas_futebol = [
            "Premier League", "La Liga", "Bundesliga", 
            "Serie A", "Ligue 1", "Champions League",
            "Europa League", "Campeonato Brasileiro"
        ]
        
        ligas_selecionadas = []
        for liga in ligas_futebol:
            if st.checkbox(liga, value=False, key=f"liga_{liga}"):
                ligas_selecionadas.append(liga)
        
        st.subheader("🏀 NBA")
        nba_selecionada = st.checkbox("NBA", value=False, key="liga_nba")
        if nba_selecionada:
            ligas_selecionadas.append("NBA")
        
        st.markdown("---")
        
        st.header("📅 Filtro por Data")
        
        # Opções de data
        opcao_data = st.radio(
            "Período das notícias:",
            ["Hoje", "Últimos 7 dias", "Personalizado"],
            index=0
        )
        
        data_inicio = None
        data_fim = None
        
        if opcao_data == "Hoje":
            data_inicio = datetime.now().strftime('%Y-%m-%d')
            data_fim = datetime.now().strftime('%Y-%m-%d')
            st.info(f"🔍 Buscando notícias de: {data_inicio}")
            
        elif opcao_data == "Últimos 7 dias":
            data_inicio = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            data_fim = datetime.now().strftime('%Y-%m-%d')
            st.info(f"🔍 Buscando notícias de: {data_inicio} até {data_fim}")
            
        elif opcao_data == "Personalizado":
            col_data1, col_data2 = st.columns(2)
            with col_data1:
                data_inicio = st.date_input("Data inicial", value=datetime.now() - timedelta(days=7))
            with col_data2:
                data_fim = st.date_input("Data final", value=datetime.now())
            
            data_inicio = data_inicio.strftime('%Y-%m-%d')
            data_fim = data_fim.strftime('%Y-%m-%d')
        
        st.markdown("---")
        
        st.header("⚙️ Configurações")
        limite_noticias = st.slider("Número de Notícias", 5, 20, 10)
        
        # Botão de teste da API
        if st.button("🧪 Testar APIs", type="secondary"):
            with st.spinner("Testando conexões..."):
                status_news, msg_news = testar_newsapi()
                st.sidebar.info(msg_news)
                
                try:
                    response = requests.get(f"{BASE_URL_FOOTBALL}/competitions", headers=HEADERS_FOOTBALL, timeout=5)
                    if response.status_code == 200:
                        st.sidebar.success("✅ Football-Data.org: Conectada")
                    else:
                        st.sidebar.warning(f"⚠️ Football-Data.org: {response.status_code}")
                except Exception as e:
                    st.sidebar.error(f"❌ Football-Data.org: {e}")
    
    # Controles principais
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Buscar Notícias", type="primary", use_container_width=True):
            if not ligas_selecionadas:
                st.warning("⚠️ Selecione pelo menos uma liga!")
            else:
                st.session_state.ligas_selecionadas = ligas_selecionadas
                st.session_state.limite_noticias = limite_noticias
                st.session_state.data_inicio = data_inicio
                st.session_state.data_fim = data_fim
                # Limpar seleções anteriores
                if 'noticias_selecionadas' in st.session_state:
                    st.session_state.noticias_selecionadas = []
    
    with col2:
        if st.button("🔄 Limpar Seleção", type="secondary", use_container_width=True):
            if 'noticias_selecionadas' in st.session_state:
                st.session_state.noticias_selecionadas = []
            st.info("Seleção de notícias limpa!")
    
    with col3:
        if st.button("🧹 Limpar Cache", type="secondary", use_container_width=True):
            try:
                cache_path = "data/" + CACHE_NOTICIAS
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    st.success("✅ Cache limpo com sucesso!")
                else:
                    st.info("ℹ️ Nenhum cache para limpar")
            except Exception as e:
                st.error(f"❌ Erro ao limpar cache: {e}")
    
    st.markdown("---")
    
    # Buscar e exibir notícias
    if 'ligas_selecionadas' in st.session_state:
        ligas_selecionadas = st.session_state.ligas_selecionadas
        limite_noticias = st.session_state.get('limite_noticias', 10)
        data_inicio = st.session_state.get('data_inicio')
        data_fim = st.session_state.get('data_fim')
        
        # Mostrar informações do filtro
        info_filtro = f"para {', '.join(ligas_selecionadas)}"
        if data_inicio and data_fim:
            if data_inicio == data_fim:
                info_filtro += f" no dia {data_inicio}"
            else:
                info_filtro += f" de {data_inicio} até {data_fim}"
        
        with st.spinner(f"🔍 Buscando {limite_noticias} notícias {info_filtro}..."):
            noticias = obter_noticias_esportivas(
                ligas_selecionadas, 
                limite_noticias, 
                data_inicio, 
                data_fim
            )
            
            if noticias:
                st.success(f"✅ {len(noticias)} notícias encontradas {info_filtro}!")
                
                # Inicializar session state para notícias selecionadas
                if 'noticias_selecionadas' not in st.session_state:
                    st.session_state.noticias_selecionadas = []
                
                # Estatísticas
                col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
                with col_stats1:
                    oficiais = sum(1 for n in noticias if n.get('prioridade') == 'alta')
                    st.metric("🔴 Notícias Oficiais", oficiais)
                with col_stats2:
                    st.metric("📰 Total de Notícias", len(noticias))
                with col_stats3:
                    st.metric("🏆 Ligas Selecionadas", len(ligas_selecionadas))
                with col_stats4:
                    # Contar notícias por período
                    if data_inicio:
                        hoje = datetime.now().strftime('%Y-%m-%d')
                        if data_inicio == hoje:
                            st.metric("📅 Período", "Hoje")
                        else:
                            st.metric("📅 Período", f"{data_inicio}")
                
                st.markdown("---")
                
                # Seção de seleção de notícias
                st.subheader("🎯 Selecione as Notícias para Enviar")
                st.info("✅ Marque as notícias que deseja enviar para o Telegram")
                
                # Contador de seleção
                noticias_selecionadas = st.session_state.noticias_selecionadas
                st.write(f"**📋 Notícias selecionadas: {len(noticias_selecionadas)}**")
                
                # Lista de notícias com checkboxes
                for i, noticia in enumerate(noticias):
                    with st.container():
                        col_check, col_content = st.columns([1, 20])
                        
                        with col_check:
                            # Checkbox para seleção
                            is_selected = any(n['id'] == noticia['id'] for n in noticias_selecionadas)
                            selecionada = st.checkbox(
                                "Selecionar", 
                                key=f"check_{noticia['id']}",
                                value=is_selected
                            )
                            
                            if selecionada and not is_selected:
                                # Adicionar à lista se não estiver presente
                                st.session_state.noticias_selecionadas.append(noticia)
                            elif not selecionada and is_selected:
                                # Remover da lista se estiver presente
                                st.session_state.noticias_selecionadas = [
                                    n for n in st.session_state.noticias_selecionadas 
                                    if n['id'] != noticia['id']
                                ]
                        
                        with col_content:
                            # Exibir notícia
                            exibir_detalhes_noticia(noticia, i+1)
                
                st.markdown("---")
                
                # Controles de envio
                if st.session_state.noticias_selecionadas:
                    st.subheader("📤 Enviar Notícias Selecionadas")
                    st.write(f"**🚀 {len(st.session_state.noticias_selecionadas)} notícias preparadas para envio**")
                    
                    # Pré-visualização
                    with st.expander("👀 Ver Notícias Selecionadas"):
                        for i, noticia in enumerate(st.session_state.noticias_selecionadas, 1):
                            st.write(f"**{i}. {noticia['titulo']}**")
                            st.write(f"   📊 Fonte: {noticia['fonte']} | 🏆 Categoria: {noticia['categoria']}")
                    
                    col_send1, col_send2 = st.columns(2)
                    
                    with col_send1:
                        if st.button("🚀 Enviar Selecionadas", type="primary", use_container_width=True):
                            with st.spinner("Enviando notícias selecionadas..."):
                                enviar_noticias_selecionadas(st.session_state.noticias_selecionadas)
                    
                    with col_send2:
                        if st.button("🗑️ Limpar Todas", type="secondary", use_container_width=True):
                            st.session_state.noticias_selecionadas = []
                            st.rerun()
                else:
                    st.info("ℹ️ Selecione algumas notícias usando as checkboxes para habilitar o envio")
                
            else:
                st.error("❌ Nenhuma notícia encontrada para os critérios selecionados")
                st.info("💡 Dica: Tente selecionar diferentes ligas, ajustar as datas ou testar as APIs no menu lateral")
    
    else:
        # Tela inicial
        st.info("🎯 **Como usar:**")
        st.markdown("""
        1. **🏆 Selecione as ligas** na sidebar que você quer acompanhar
        2. **📅 Escolha o período** das notícias (Hoje, Últimos 7 dias ou Personalizado)
        3. **🔍 Clique em 'Buscar Notícias'** para carregar as notícias
        4. **✅ Marque as notícias** que você quer enviar usando as checkboxes
        5. **🚀 Clique em 'Enviar Selecionadas'** para enviar para o Telegram
        
        **💡 Dica:** Use o botão **'Testar APIs'** na sidebar para verificar se as APIs estão funcionando!
        """)

def exibir_detalhes_noticia(noticia: dict, numero: int):
    """Exibe os detalhes de uma notícia"""
    with st.expander(f"{numero}. {noticia['titulo']}", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Badge de prioridade
            prioridade_color = "🔴" if noticia.get('prioridade') == 'alta' else "🟡"
            st.write(f"**Prioridade:** {prioridade_color} {noticia.get('prioridade', 'media').upper()}")
            
            # Categoria e fonte
            emoji = "⚽" if "futebol" in noticia['categoria'].lower() else "🏀" if "nba" in noticia['categoria'].lower() else "📰"
            st.write(f"**Categoria:** {emoji} {noticia['categoria']}")
            st.write(f"**Fonte:** {noticia['fonte']}")
            
            # Data
            try:
                data_obj = datetime.fromisoformat(noticia['data'].replace('Z', '+00:00'))
                data_formatada = data_obj.strftime('%d/%m/%Y %H:%M')
                st.write(f"**Publicada em:** {data_formatada}")
            except:
                st.write("**Publicada em:** Data não disponível")
            
            # Descrição
            st.write("**Descrição:**")
            st.write(noticia['descricao'])
            
            # Link
            st.markdown(f"[🔗 Ler notícia completa]({noticia['url']})")
        
        with col2:
            # Imagem se disponível
            if noticia.get('imagem') and noticia['imagem'].startswith('http'):
                try:
                    st.image(noticia['imagem'], use_column_width=True)
                except:
                    st.info("🖼️ Imagem não carregada")
            else:
                st.info("🖼️ Sem imagem")

if __name__ == "__main__":
    main()
