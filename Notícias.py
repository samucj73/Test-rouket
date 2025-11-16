import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import feedparser

# =============================
# Configurações
# =============================

# APIs
NEWS_API_KEY = "2bac9541659c4450921136a9c2e9acbe"
FOOTBALL_API_KEY = "9058de85e3324bdb969adc005b5d918a"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

BASE_URL_NEWS = "https://newsapi.org/v2"
BASE_URL_FOOTBALL = "https://api.football-data.org/v4"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

HEADERS_FOOTBALL = {"X-Auth-Token": FOOTBALL_API_KEY}

# Constantes
CACHE_NOTICIAS = "cache_noticias.json"
CACHE_TIMEOUT = 1800

# =============================
# SISTEMA DE MÚLTIPLAS FONTES
# =============================

# Dicionário de Fontes RSS Esportivas
RSS_FEEDS = {
    'UOL Esporte': 'https://rss.uol.com.br/feed/esporte.xml',
    'ESPN Brasil': 'https://www.espn.com.br/espn/rss/news',
    'Terra Esportes': 'https://rss.terra.com.br/0,,EI0,00.xml',
    'R7 Esportes': 'https://www.r7.com/r7/esportes/rss.xml',
    'CB Esportes': 'https://www.correiobraziliense.com.br/rss/editoria/esportes.xml',
    'Gazeta Esportiva': 'https://www.gazetaesportiva.com/feed/',
    'GE Globo Esporte': 'https://ge.globo.com/rss/futebol/futebol-internacional/futebol-ingles/',
    'OneFootball': 'https://onefootball.com/pt-br/feed',
}

# Dicionário de Ligas para Filtro
LIGAS_DICT = {
    "Premier League": ["Premier League", "English Premier League", "EPL", "Manchester", "Liverpool", "Arsenal", "Chelsea"],
    "La Liga": ["La Liga", "LaLiga", "Spanish La Liga", "Barcelona", "Real Madrid", "Atletico"],
    "Bundesliga": ["Bundesliga", "German Bundesliga", "Bayern", "Dortmund"],
    "Serie A": ["Serie A", "Serie A TIM", "Italian Serie A", "Juventus", "Milan", "Inter"],
    "Ligue 1": ["Ligue 1", "French Ligue 1", "PSG", "Messi", "Mbappé"],
    "Champions League": ["Champions League", "UEFA Champions League", "UCL"],
    "Europa League": ["Europa League", "UEFA Europa League"],
    "Campeonato Brasileiro": ["Brasileirão", "Campeonato Brasileiro", "Brasileiro Série A", "Flamengo", "Palmeiras", "Corinthians", "São Paulo"],
    "Libertadores": ["Libertadores", "Copa Libertadores"],
    "Copa do Brasil": ["Copa do Brasil", "Copa do Brasil"],
    "NBA": ["NBA", "National Basketball Association", "Lakers", "Warriors", "LeBron"],
    "Fórmula 1": ["Fórmula 1", "F1", "Formula 1", "Hamilton", "Verstappen"],
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
# FUNÇÕES DE MÚLTIPLAS FONTES
# =============================

def obter_noticias_rss(feed_url: str, fonte: str, limite: int = 5) -> list:
    """Obtém notícias de feeds RSS"""
    noticias = []
    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:limite]:
            # Verificar se é uma notícia esportiva relevante
            if is_noticia_esportiva(entry.title):
                noticias.append({
                    'titulo': entry.title,
                    'descricao': entry.get('summary', entry.get('description', 'Sem descrição disponível')),
                    'url': entry.link,
                    'imagem': obter_imagem_rss(entry),
                    'fonte': fonte,
                    'data': entry.get('published', datetime.now().isoformat()),
                    'categoria': classificar_noticia(entry.title),
                    'prioridade': 'media',
                    'id': f"rss_{hash(entry.link)}"
                })
                
    except Exception as e:
        st.warning(f"⚠️ Erro no RSS {fonte}: {e}")
    
    return noticias

def is_noticia_esportiva(titulo: str) -> bool:
    """Verifica se a notícia é realmente esportiva"""
    if not titulo:
        return False
        
    titulo_lower = titulo.lower()
    
    # Palavras-chave esportivas
    keywords_esportes = [
        'futebol', 'football', 'bola', 'gol', 'jogo', 'time', 'clube',
        'campeonato', 'liga', 'torneio', 'partida', 'estádio',
        'flamengo', 'palmeiras', 'corinthians', 'são paulo', 'santos',
        'brasileirão', 'libertadores', 'copa do brasil',
        'premier league', 'la liga', 'bundesliga', 'serie a',
        'champions league', 'europa league',
        'nba', 'basquete', 'basketball',
        'fórmula 1', 'f1', 'corrida', 'grand prix'
    ]
    
    return any(keyword in titulo_lower for keyword in keywords_esportes)

def classificar_noticia(titulo: str) -> str:
    """Classifica a notícia em uma categoria específica"""
    titulo_lower = titulo.lower()
    
    for liga, keywords in LIGAS_DICT.items():
        if any(keyword.lower() in titulo_lower for keyword in keywords):
            return liga
    
    # Classificação padrão
    if any(time in titulo_lower for time in ['flamengo', 'palmeiras', 'corinthians', 'são paulo']):
        return "Campeonato Brasileiro"
    elif 'nba' in titulo_lower or 'basquete' in titulo_lower:
        return "NBA"
    elif 'fórmula 1' in titulo_lower or 'f1' in titulo_lower:
        return "Fórmula 1"
    
    return "Esportes Gerais"

def obter_imagem_rss(entry) -> str:
    """Extrai imagem do feed RSS"""
    try:
        # Tentar diferentes métodos de extração de imagem
        if hasattr(entry, 'media_content') and entry.media_content:
            return entry.media_content[0]['url']
        elif hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image/'):
                    return link.href
        elif hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.href
    except:
        pass
    
    return ""

def obter_noticias_multifonte(ligas_selecionadas: list, limite_total: int = 15) -> list:
    """Obtém notícias de múltiplas fontes"""
    todas_noticias = []
    
    # 1. Buscar da NewsAPI (prioridade)
    st.info("📡 Conectando com NewsAPI...")
    for liga in ligas_selecionadas[:3]:  # Limitar para não exceder rate limit
        if liga in LIGAS_DICT:
            termo = LIGAS_DICT[liga][0]
            noticias_api = obter_noticias_newsapi(termo, limite=5)
            todas_noticias.extend(noticias_api)
    
    # 2. Buscar de feeds RSS
    st.info("📡 Coletando de feeds RSS...")
    fontes_rss = list(RSS_FEEDS.items())
    
    for i, (fonte, url) in enumerate(fontes_rss):
        noticias_rss = obter_noticias_rss(url, fonte, limite=3)
        todas_noticias.extend(noticias_rss)
    
    # 3. Filtrar e classificar notícias
    noticias_filtradas = filtrar_noticias_por_liga(todas_noticias, ligas_selecionadas)
    
    # 4. Remover duplicatas
    noticias_unicas = remover_duplicatas(noticias_filtradas)
    
    # 5. Ordenar por relevância e data
    noticias_ordenadas = ordenar_noticias(noticias_unicas)
    
    return noticias_ordenadas[:limite_total]

def filtrar_noticias_por_liga(noticias: list, ligas_selecionadas: list) -> list:
    """Filtra notícias baseado nas ligas selecionadas"""
    if not ligas_selecionadas:
        return noticias
    
    noticias_filtradas = []
    
    for noticia in noticias:
        # Se a notícia já tem uma categoria definida que está nas selecionadas
        if noticia['categoria'] in ligas_selecionadas:
            noticias_filtradas.append(noticia)
            continue
        
        # Verificar se o título contém palavras-chave das ligas selecionadas
        titulo_lower = noticia['titulo'].lower()
        for liga in ligas_selecionadas:
            if liga in LIGAS_DICT:
                keywords = [k.lower() for k in LIGAS_DICT[liga]]
                if any(keyword in titulo_lower for keyword in keywords):
                    noticia['categoria'] = liga  # Reclassificar
                    noticias_filtradas.append(noticia)
                    break
    
    return noticias_filtradas

def remover_duplicatas(noticias: list) -> list:
    """Remove notícias duplicadas baseado no título e URL"""
    noticias_unicas = []
    titulos_vistos = set()
    urls_vistos = set()
    
    for noticia in noticias:
        titulo_simplificado = noticia['titulo'].lower().strip()[:100]
        url_simplificado = noticia['url'].split('?')[0]  # Remove parâmetros
        
        if (titulo_simplificado not in titulos_vistos and 
            url_simplificado not in urls_vistos):
            
            noticias_unicas.append(noticia)
            titulos_vistos.add(titulo_simplificado)
            urls_vistos.add(url_simplificado)
    
    return noticias_unicas

def ordenar_noticias(noticias: list) -> list:
    """Ordena notícias por prioridade e data"""
    def peso_prioridade(noticia):
        prioridades = {'alta': 0, 'media': 1, 'baixa': 2}
        return prioridades.get(noticia.get('prioridade', 'media'), 1)
    
    def peso_fonte(noticia):
        fontes_prioritarias = ['NewsAPI', 'ESPN Brasil', 'GE Globo Esporte']
        return 0 if noticia['fonte'] in fontes_prioritarias else 1
    
    # Ordenar por: prioridade > fonte > data
    noticias.sort(key=lambda x: (
        peso_prioridade(x),
        peso_fonte(x),
        x['data']
    ), reverse=True)
    
    return noticias

def filtrar_por_data(noticias: list, data_inicio: str, data_fim: str = None) -> list:
    """Filtra notícias por data de publicação"""
    if not data_inicio:
        return noticias
    
    noticias_filtradas = []
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d') if data_fim else datetime.now()
    
    for noticia in noticias:
        try:
            # Tentar parsear a data da notícia
            if 'T' in noticia['data']:
                data_noticia = datetime.fromisoformat(noticia['data'].replace('Z', '+00:00'))
            else:
                # Tentar outros formatos comuns de RSS
                try:
                    data_noticia = datetime.strptime(noticia['data'], '%a, %d %b %Y %H:%M:%S %z')
                except:
                    try:
                        data_noticia = datetime.strptime(noticia['data'], '%Y-%m-%d %H:%M:%S')
                    except:
                        # Se não conseguir parsear, usar data atual
                        data_noticia = datetime.now()
            
            if data_inicio_obj <= data_noticia.replace(tzinfo=None) <= data_fim_obj:
                noticias_filtradas.append(noticia)
                
        except:
            # Se não conseguir parsear a data, inclui por segurança
            noticias_filtradas.append(noticia)
    
    return noticias_filtradas

# =============================
# Sistema de Notícias Esportivas
# =============================

def obter_noticias_football_data() -> list:
    """Obtém notícias específicas de futebol da API Football-Data.org"""
    noticias = []
    
    try:
        response = requests.get(f"{BASE_URL_FOOTBALL}/competitions", headers=HEADERS_FOOTBALL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            competicoes = data.get('competitions', [])[:5]
            
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
                            'categoria': classificar_noticia(article['title']),
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
    Obtém notícias esportivas de múltiplas fontes
    """
    if ligas_selecionadas is None:
        ligas_selecionadas = []
    
    # Criar chave de cache
    cache_key = f"{'_'.join(ligas_selecionadas)}_{limite}_{data_inicio}_{data_fim}"
    
    cache = carregar_json(CACHE_NOTICIAS)
    
    # Verificar cache
    if cache_key in cache:
        cache_data = cache[cache_key]
        if datetime.now().timestamp() - cache_data.get('_timestamp', 0) < CACHE_TIMEOUT:
            st.success("💾 Usando notícias em cache (30min)")
            return cache_data.get('noticias', [])
    
    # Buscar notícias
    with st.spinner("🔄 Buscando notícias de múltiplas fontes..."):
        noticias = obter_noticias_multifonte(ligas_selecionadas, limite)
        
        # Aplicar filtro de data se necessário
        if data_inicio:
            noticias = filtrar_por_data(noticias, data_inicio, data_fim)
        
        # Se não encontrou notícias, usar fallback
        if not noticias:
            st.warning("⚠️ Nenhuma notícia encontrada, usando conteúdo de fallback")
            noticias = obter_noticias_fallback(ligas_selecionadas)
        
        # Salvar no cache
        cache[cache_key] = {
            'noticias': noticias,
            '_timestamp': datetime.now().timestamp(),
            'total_fontes': len(RSS_FEEDS) + 1
        }
        salvar_json(CACHE_NOTICIAS, cache)
        
        return noticias

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
        
        emoji = "⚽" if "futebol" in noticia['categoria'].lower() else "🏀" if "nba" in noticia['categoria'].lower() else "🏎️" if "fórmula" in noticia['categoria'].lower() else "📰"
        
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
            "Europa League", "Campeonato Brasileiro",
            "Libertadores", "Copa do Brasil"
        ]
        
        ligas_selecionadas = []
        for liga in ligas_futebol:
            if st.checkbox(liga, value=False, key=f"liga_{liga}"):
                ligas_selecionadas.append(liga)
        
        st.subheader("🏀 NBA")
        nba_selecionada = st.checkbox("NBA", value=False, key="liga_nba")
        if nba_selecionada:
            ligas_selecionadas.append("NBA")
            
        st.subheader("🏎️ Fórmula 1")
        f1_selecionada = st.checkbox("Fórmula 1", value=False, key="liga_f1")
        if f1_selecionada:
            ligas_selecionadas.append("Fórmula 1")
        
        st.markdown("---")
        
        st.header("🌐 Fontes de Notícias")
        
        st.info(f"📡 **Fontes ativas:** {len(RSS_FEEDS) + 1}")
        
        with st.expander("Ver todas as fontes"):
            st.write("**APIs:**")
            st.write("• NewsAPI (Internacional)")
            st.write("• Football-Data.org")
            
            st.write("**RSS Brasileiros:**")
            for fonte in RSS_FEEDS.keys():
                st.write(f"• {fonte}")
        
        # Seletor de fontes preferidas (usando session state)
        fontes_preferidas = st.multiselect(
            "Fontes preferidas (opcional):",
            options=list(RSS_FEEDS.keys()),
            default=["ESPN Brasil", "UOL Esporte", "GE Globo Esporte"]
        )
        
        # Usar session state para gerenciar fontes
        if 'fontes_ativas' not in st.session_state:
            st.session_state.fontes_ativas = RSS_FEEDS.copy()
        
        # Atualizar fontes ativas baseado nas preferências
        if fontes_preferidas:
            st.session_state.fontes_ativas = {k: v for k, v in RSS_FEEDS.items() if k in fontes_preferidas}
        else:
            st.session_state.fontes_ativas = RSS_FEEDS.copy()
        
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
            # Usar fontes ativas do session state
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
        2. **🌐 Escolha as fontes preferidas** (opcional)
        3. **📅 Escolha o período** das notícias (Hoje, Últimos 7 dias ou Personalizado)
        4. **🔍 Clique em 'Buscar Notícias'** para carregar as notícias
        5. **✅ Marque as notícias** que você quer enviar usando as checkboxes
        6. **🚀 Clique em 'Enviar Selecionadas'** para enviar para o Telegram
        
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
            emoji = "⚽" if "futebol" in noticia['categoria'].lower() else "🏀" if "nba" in noticia['categoria'].lower() else "🏎️" if "fórmula" in noticia['categoria'].lower() else "📰"
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
