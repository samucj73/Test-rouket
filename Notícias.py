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
        # Tentar obter notícias da API-FOOTBALL
        response = requests.get(f"{BASE_URL_FOOTBALL}/news", headers=HEADERS_FOOTBALL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for news in data.get('news', [])[:8]:  # Aumentar limite para mais opções
                noticias.append({
                    'titulo': news.get('title', ''),
                    'descricao': news.get('description', 'Notícia oficial da Football-Data.org'),
                    'url': news.get('url', ''),
                    'imagem': news.get('image', ''),
                    'fonte': 'Football-Data.org',
                    'data': news.get('publishedAt', datetime.now().isoformat()),
                    'categoria': 'Futebol Oficial',
                    'prioridade': 'alta',  # Notícias oficiais têm alta prioridade
                    'id': f"football_{news.get('id', len(noticias))}"  # ID único
                })
    except Exception as e:
        st.warning(f"⚠️ Não foi possível acessar Football-Data.org: {e}")
    
    return noticias

def obter_noticias_esportivas(ligas_selecionadas: list = None, limite: int = 10) -> list:
    """
    Obtém notícias esportivas filtradas por ligas
    """
    if ligas_selecionadas is None:
        ligas_selecionadas = []
    
    cache = carregar_json(CACHE_NOTICIAS)
    cache_key = f"{'_'.join(ligas_selecionadas)}_{limite}" if ligas_selecionadas else f"todas_{limite}"
    
    # Verificar cache (30 minutos para notícias)
    if cache_key in cache:
        cache_data = cache[cache_key]
        if datetime.now().timestamp() - cache_data.get('_timestamp', 0) < CACHE_TIMEOUT:
            return cache_data.get('noticias', [])
    
    noticias = []
    
    try:
        # SEMPRE obter notícias do Football-Data.org primeiro (mais confiáveis)
        noticias_football = obter_noticias_football_data()
        noticias.extend(noticias_football)
        
        # Se nenhuma liga selecionada, buscar todas as notícias
        if not ligas_selecionadas or "Todas" in ligas_selecionadas:
            # Notícias gerais de futebol
            params = {
                'q': '(futebol OR football OR soccer) -política -eleições',
                'language': 'pt',
                'sortBy': 'publishedAt',
                'pageSize': limite,
                'apiKey': NEWS_API_KEY
            }
            
            response = requests.get(f"{BASE_URL_NEWS}/everything", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for article in data.get('articles', [])[:limite]:
                    if article['title'] != '[Removed]' and article.get('description'):
                        noticias.append({
                            'titulo': article['title'],
                            'descricao': article.get('description', 'Sem descrição disponível'),
                            'url': article['url'],
                            'imagem': article.get('urlToImage', ''),
                            'fonte': article.get('source', {}).get('name', 'NewsAPI'),
                            'data': article.get('publishedAt', ''),
                            'categoria': 'Futebol',
                            'prioridade': 'media',
                            'id': f"newsapi_{len(noticias)}"
                        })
        else:
            # Buscar notícias específicas por liga
            for liga in ligas_selecionadas:
                if liga in LIGAS_DICT:
                    termos_busca = " OR ".join(LIGAS_DICT[liga])
                    params = {
                        'q': f'({termos_busca}) -política -eleições',
                        'language': 'pt',
                        'sortBy': 'publishedAt',
                        'pageSize': max(3, limite // len(ligas_selecionadas)),
                        'apiKey': NEWS_API_KEY
                    }
                    
                    response = requests.get(f"{BASE_URL_NEWS}/everything", params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for article in data.get('articles', []):
                            if article['title'] != '[Removed]' and article.get('description'):
                                noticias.append({
                                    'titulo': article['title'],
                                    'descricao': article.get('description', 'Sem descrição disponível'),
                                    'url': article['url'],
                                    'imagem': article.get('urlToImage', ''),
                                    'fonte': article.get('source', {}).get('name', 'NewsAPI'),
                                    'data': article.get('publishedAt', ''),
                                    'categoria': liga,
                                    'prioridade': 'media',
                                    'id': f"newsapi_{liga}_{len(noticias)}"
                                })
        
        # Remover duplicatas baseado no título
        noticias_unicas = []
        titulos_vistos = set()
        for noticia in noticias:
            titulo_limpo = noticia['titulo'].lower().strip()
            if titulo_limpo not in titulos_vistos:
                noticias_unicas.append(noticia)
                titulos_vistos.add(titulo_limpo)
        
        # Ordenar por prioridade e data (mais recentes primeiro)
        noticias_unicas.sort(key=lambda x: (
            {'alta': 0, 'media': 1}.get(x.get('prioridade', 'media'), 2),
            x['data']
        ), reverse=True)
        
        # Salvar no cache
        cache[cache_key] = {
            'noticias': noticias_unicas[:limite],
            '_timestamp': datetime.now().timestamp()
        }
        salvar_json(CACHE_NOTICIAS, cache)
        
        return noticias_unicas[:limite]
        
    except Exception as e:
        st.error(f"❌ Erro ao obter notícias: {e}")
        # Retornar notícias de fallback
        return obter_noticias_fallback(ligas_selecionadas)

def obter_noticias_fallback(ligas_selecionadas: list = None) -> list:
    """Notícias de fallback quando as APIs falham"""
    if ligas_selecionadas is None:
        ligas_selecionadas = []
    
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
        }
    ]
    
    # Adicionar notícias de fallback baseadas nas ligas selecionadas
    for liga in ligas_selecionadas[:3]:  # Limitar a 3 ligas
        noticias_fallback.append({
            'titulo': f'🏆 {liga} - Notícias e Atualizações',
            'descricao': f'Acompanhe as últimas notícias e atualizações da {liga}.',
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
        return False
    
    try:
        sucessos = 0
        total = len(noticias_selecionadas)
        
        for i, noticia in enumerate(noticias_selecionadas, 1):
            st.info(f"📤 Enviando notícia {i} de {total}: {noticia['titulo'][:50]}...")
            
            if enviar_noticia_individual(noticia, chat_id):
                sucessos += 1
                st.success(f"✅ Notícia {i} enviada com sucesso!")
            else:
                st.error(f"❌ Falha ao enviar notícia {i}")
            
            # Pequena pausa entre notícias
            import time
            time.sleep(1)
        
        st.success(f"🎯 Resumo: {sucessos} de {total} notícias enviadas com sucesso!")
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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("📰 ELITE MASTER NEWS")
        st.markdown("### Sistema de Seleção de Notícias por Liga")
        st.markdown("**Selecione as ligas e escolha quais notícias enviar**")
    
    st.markdown("---")
    
    # Sidebar - Seleção de Ligas
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
        
        st.header("⚙️ Configurações")
        limite_noticias = st.slider("Número de Notícias", 5, 20, 12)
        
        st.markdown("---")
        
        # Status das APIs
        st.subheader("🔌 Status das APIs")
        try:
            response = requests.get(f"{BASE_URL_NEWS}/everything?q=test&apiKey={NEWS_API_KEY}", timeout=5)
            st.success("✅ NewsAPI: Conectada")
        except:
            st.error("❌ NewsAPI: Offline")
        
        try:
            response = requests.get(f"{BASE_URL_FOOTBALL}/competitions", headers=HEADERS_FOOTBALL, timeout=5)
            st.success("✅ Football-Data.org: Conectada")
        except:
            st.warning("⚠️ Football-Data.org: Limitada")
    
    # Controles principais
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Buscar Notícias", type="primary", use_container_width=True):
            if not ligas_selecionadas:
                st.warning("⚠️ Selecione pelo menos uma liga!")
            else:
                st.session_state.ligas_selecionadas = ligas_selecionadas
                st.session_state.limite_noticias = limite_noticias
    
    with col2:
        if st.button("🔄 Limpar Seleção", type="secondary", use_container_width=True):
            if 'noticias_selecionadas' in st.session_state:
                st.session_state.noticias_selecionadas = []
            st.info("Seleção de notícias limpa!")
    
    with col3:
        if st.button("🧹 Limpar Cache", type="secondary", use_container_width=True):
            try:
                if os.path.exists("data/" + CACHE_NOTICIAS):
                    os.remove("data/" + CACHE_NOTICIAS)
                st.success("Cache limpo com sucesso!")
            except:
                st.error("Erro ao limpar cache")
    
    st.markdown("---")
    
    # Buscar e exibir notícias
    if 'ligas_selecionadas' in st.session_state:
        ligas_selecionadas = st.session_state.ligas_selecionadas
        limite_noticias = st.session_state.get('limite_noticias', 12)
        
        with st.spinner(f"Buscando notícias para {', '.join(ligas_selecionadas)}..."):
            noticias = obter_noticias_esportivas(ligas_selecionadas, limite_noticias)
            
            if noticias:
                st.success(f"✅ {len(noticias)} notícias encontradas para {len(ligas_selecionadas)} liga(s)")
                
                # Inicializar session state para notícias selecionadas
                if 'noticias_selecionadas' not in st.session_state:
                    st.session_state.noticias_selecionadas = []
                
                # Estatísticas
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    oficiais = sum(1 for n in noticias if n.get('prioridade') == 'alta')
                    st.metric("🔴 Notícias Oficiais", oficiais)
                with col_stats2:
                    st.metric("📰 Total de Notícias", len(noticias))
                with col_stats3:
                    st.metric("🏆 Ligas Selecionadas", len(ligas_selecionadas))
                
                st.markdown("---")
                
                # Seção de seleção de notícias
                st.subheader("🎯 Selecione as Notícias para Enviar")
                st.info("Marque as notícias que deseja enviar para o Telegram")
                
                # Contador de seleção
                noticias_selecionadas = st.session_state.noticias_selecionadas
                st.write(f"**Notícias selecionadas: {len(noticias_selecionadas)}**")
                
                # Lista de notícias com checkboxes
                for i, noticia in enumerate(noticias):
                    with st.container():
                        col_check, col_content = st.columns([1, 20])
                        
                        with col_check:
                            # Checkbox para seleção
                            selecionada = st.checkbox(
                                "Selecionar", 
                                key=f"check_{noticia['id']}",
                                value=any(n['id'] == noticia['id'] for n in noticias_selecionadas)
                            )
                            
                            if selecionada:
                                # Adicionar à lista se não estiver presente
                                if not any(n['id'] == noticia['id'] for n in noticias_selecionadas):
                                    st.session_state.noticias_selecionadas.append(noticia)
                            else:
                                # Remover da lista se estiver presente
                                st.session_state.noticias_selecionadas = [
                                    n for n in st.session_state.noticias_selecionadas 
                                    if n['id'] != noticia['id']
                                ]
                        
                        with col_content:
                            # Exibir notícia
                            with st.expander(f"{noticia['titulo']}", expanded=False):
                                exibir_detalhes_noticia(noticia)
                
                st.markdown("---")
                
                # Controles de envio
                if st.session_state.noticias_selecionadas:
                    st.subheader("📤 Enviar Notícias Selecionadas")
                    st.write(f"**{len(st.session_state.noticias_selecionadas)} notícias preparadas para envio**")
                    
                    col_send1, col_send2 = st.columns(2)
                    
                    with col_send1:
                        if st.button("🚀 Enviar Todas Selecionadas", type="primary", use_container_width=True):
                            with st.spinner("Enviando notícias selecionadas..."):
                                if enviar_noticias_selecionadas(st.session_state.noticias_selecionadas):
                                    st.balloons()
                                    st.success("🎉 Todas as notícias selecionadas foram enviadas!")
                                else:
                                    st.error("❌ Houve erros no envio das notícias")
                    
                    with col_send2:
                        if st.button("👀 Pré-visualizar Seleção", type="secondary", use_container_width=True):
                            st.subheader("📋 Notícias Selecionadas para Envio")
                            for i, noticia in enumerate(st.session_state.noticias_selecionadas, 1):
                                st.write(f"**{i}. {noticia['titulo']}**")
                                st.write(f"   Fonte: {noticia['fonte']} | Categoria: {noticia['categoria']}")
                else:
                    st.info("ℹ️ Selecione algumas notícias usando as checkboxes para habilitar o envio")
                
            else:
                st.error("❌ Nenhuma notícia encontrada para as ligas selecionadas")
    
    else:
        # Tela inicial
        st.info("🎯 **Como usar:**")
        st.markdown("""
        1. **🏆 Selecione as ligas** na sidebar que você quer acompanhar
        2. **🔍 Clique em 'Buscar Notícias'** para carregar as notícias
        3. **✅ Marque as notícias** que você quer enviar usando as checkboxes
        4. **🚀 Clique em 'Enviar Todas Selecionadas'** para enviar para o Telegram
        
        **💡 Dica:** Você pode selecionar notícias de ligas diferentes e enviar todas de uma vez!
        """)
        
        # Exemplo visual
        col_demo1, col_demo2, col_demo3 = st.columns(3)
        with col_demo1:
            st.metric("🏆 Ligas Disponíveis", len(LIGAS_DICT))
        with col_demo2:
            st.metric("📰 Notícias por Busca", "5-20")
        with col_demo3:
            st.metric("🔴 Fontes Oficiais", "Football-Data.org")

def exibir_detalhes_noticia(noticia: dict):
    """Exibe os detalhes de uma notícia"""
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
