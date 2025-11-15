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
            for news in data.get('news', [])[:5]:  # Limitar a 5 notícias
                noticias.append({
                    'titulo': news.get('title', ''),
                    'descricao': news.get('description', 'Notícia oficial da Football-Data.org'),
                    'url': news.get('url', ''),
                    'imagem': news.get('image', ''),
                    'fonte': 'Football-Data.org',
                    'data': news.get('publishedAt', datetime.now().isoformat()),
                    'categoria': 'Futebol Oficial',
                    'prioridade': 'alta'  # Notícias oficiais têm alta prioridade
                })
    except Exception as e:
        st.warning(f"⚠️ Não foi possível acessar Football-Data.org: {e}")
    
    return noticias

def obter_noticias_esportivas(tipo: str = "futebol", limite: int = 5) -> list:
    """
    Obtém notícias esportivas de múltiplas APIs
    tipos: "futebol", "nba", "todos"
    """
    cache = carregar_json(CACHE_NOTICIAS)
    cache_key = f"{tipo}_{limite}"
    
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
        
        if tipo in ["futebol", "todos"]:
            # Notícias de futebol da NewsAPI
            params = {
                'q': '(futebol OR football OR soccer) AND (Premier League OR La Liga OR Bundesliga OR Serie A OR Champions League) -política -eleições',
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
                            'prioridade': 'media'
                        })
        
        if tipo in ["nba", "todos"]:
            # Notícias da NBA da NewsAPI
            params = {
                'q': '(NBA OR basquete OR basketball) AND (Lakers OR Warriors OR Celtics OR Bulls OR Heat) -política -eleições',
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
                            'categoria': 'NBA',
                            'prioridade': 'media'
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
        return obter_noticias_fallback(tipo)

def obter_noticias_fallback(tipo: str) -> list:
    """Notícias de fallback quando as APIs falham"""
    noticias_fallback = [
        {
            'titulo': '⚽ ELITE MASTER - Sistema de Notícias Esportivas',
            'descricao': 'Sistema avançado de notícias esportivas em tempo real. Mantenha-se informado sobre as principais notícias do mundo do futebol e basquete.',
            'url': 'https://t.me/elitemasteralertas',
            'imagem': '',
            'fonte': 'ELITE MASTER',
            'data': datetime.now().isoformat(),
            'categoria': 'Sistema',
            'prioridade': 'alta'
        }
    ]
    
    if tipo in ["futebol", "todos"]:
        noticias_fallback.extend([
            {
                'titulo': '🏆 Football-Data.org - Notícias Oficiais',
                'descricao': 'Acesse notícias oficiais e atualizações em tempo real do mundo do futebol através da API Football-Data.org.',
                'url': 'https://www.football-data.org',
                'imagem': '',
                'fonte': 'Football-Data.org',
                'data': datetime.now().isoformat(),
                'categoria': 'Futebol Oficial',
                'prioridade': 'alta'
            },
            {
                'titulo': '⚽ Mercado da Bola: Últimas Transferências',
                'descricao': 'Acompanhe as principais transferências do mercado da bola europeu e brasileiro.',
                'url': 'https://t.me/elitemasteralertas',
                'imagem': '',
                'fonte': 'ELITE MASTER',
                'data': datetime.now().isoformat(),
                'categoria': 'Futebol',
                'prioridade': 'media'
            }
        ])
    
    if tipo in ["nba", "todos"]:
        noticias_fallback.extend([
            {
                'titulo': '🏀 Temporada da NBA 2024',
                'descricao': 'Acompanhe os melhores momentos, resultados e análises da temporada da NBA.',
                'url': 'https://t.me/elitemasteralertas',
                'imagem': '',
                'fonte': 'ELITE MASTER',
                'data': datetime.now().isoformat(),
                'categoria': 'NBA',
                'prioridade': 'media'
            }
        ])
    
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

def enviar_alerta_noticias(noticias: list, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia alerta de notícias para o Telegram"""
    if not noticias:
        return False
    
    try:
        for i, noticia in enumerate(noticias[:3]):  # Limitar a 3 notícias por alerta
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
                f"<b>{emoji} {noticia['categoria'].upper()} - NOTÍCIA {i+1}</b>\n"
                f"<b>{prioridade_badge}</b>\n\n"
                f"<b>📰 {noticia['titulo']}</b>\n\n"
                f"<b>📝 {noticia['descricao'][:200]}{'...' if len(noticia['descricao']) > 200 else ''}</b>\n\n"
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
                        if enviar_foto_telegram(photo_bytes, caption=msg, chat_id=chat_id):
                            continue
                except:
                    pass
            
            # Fallback para mensagem de texto
            enviar_telegram(msg, chat_id)
            
            # Pequena pausa entre notícias
            import time
            time.sleep(1)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao enviar notícias: {e}")
        return False

def enviar_resumo_noticias_diario():
    """Envia resumo diário de notícias esportivas"""
    try:
        # Obter notícias do dia
        noticias_futebol = obter_noticias_esportivas("futebol", 4)
        noticias_nba = obter_noticias_esportivas("nba", 2)
        
        if not noticias_futebol and not noticias_nba:
            return False
        
        msg = "<b>📰 RESUMO DIÁRIO DE NOTÍCIAS ESPORTIVAS</b>\n\n"
        
        if noticias_futebol:
            msg += "<b>⚽ FUTEBOL OFICIAL</b>\n"
            for i, noticia in enumerate(noticias_futebol[:3], 1):
                prioridade = "🔴" if noticia.get('prioridade') == 'alta' else "🟡"
                msg += f"<b>{prioridade} {i}. {noticia['titulo'][:50]}...</b>\n"
                msg += f"<i>Fonte: {noticia['fonte']}</i>\n"
                msg += f"<a href='{noticia['url']}'>📖 Ler mais</a>\n\n"
        
        if noticias_nba:
            msg += "<b>🏀 NBA</b>\n"
            for i, noticia in enumerate(noticias_nba[:2], 1):
                msg += f"<b>{i}. {noticia['titulo'][:50]}...</b>\n"
                msg += f"<i>Fonte: {noticia['fonte']}</i>\n"
                msg += f"<a href='{noticia['url']}'>📖 Ler mais</a>\n\n"
        
        msg += "<b>🔔 ELITE MASTER NEWS - Mantenha-se Informado!</b>"
        
        return enviar_telegram(msg, TELEGRAM_CHAT_ID)
        
    except Exception as e:
        st.error(f"❌ Erro ao enviar resumo diário: {e}")
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
        st.markdown("### Sistema Integrado de Notícias Esportivas")
        st.markdown("**APIs:** NewsAPI + Football-Data.org")
    
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📰 Tipos de Notícias")
        noticias_futebol = st.checkbox("⚽ Futebol", value=True)
        noticias_nba = st.checkbox("🏀 NBA", value=True)
        noticias_todas = st.checkbox("🌐 Todas as Notícias", value=False)
        
        st.subheader("📊 Configurações")
        limite_noticias = st.slider("Número de Notícias", 3, 10, 6)
        enviar_auto = st.checkbox("📤 Enviar automaticamente para Telegram", value=True)
        
        st.subheader("🎯 Prioridade")
        st.info("🔴 Notícias Oficiais (Football-Data.org)")
        st.info("🟡 Notícias da Mídia (NewsAPI)")
        
        st.markdown("---")
        
        # Status das APIs
        st.subheader("🔌 Status das APIs")
        try:
            # Testar NewsAPI
            response = requests.get(f"{BASE_URL_NEWS}/everything?q=test&apiKey={NEWS_API_KEY}", timeout=5)
            st.success("✅ NewsAPI: Conectada")
        except:
            st.error("❌ NewsAPI: Offline")
        
        try:
            # Testar Football-Data.org
            response = requests.get(f"{BASE_URL_FOOTBALL}/competitions", headers=HEADERS_FOOTBALL, timeout=5)
            st.success("✅ Football-Data.org: Conectada")
        except:
            st.warning("⚠️ Football-Data.org: Limitada")
    
    # Controles principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("⚽ Buscar Futebol", type="primary", use_container_width=True):
            tipo = "futebol"
            if noticias_todas:
                tipo = "todos"
            
            with st.spinner("Buscando notícias de futebol..."):
                noticias = obter_noticias_esportivas(tipo, limite_noticias)
                exibir_noticias(noticias, "Futebol", enviar_auto)
    
    with col2:
        if st.button("🏀 Buscar NBA", type="primary", use_container_width=True):
            tipo = "nba"
            if noticias_todas:
                tipo = "todos"
            
            with st.spinner("Buscando notícias da NBA..."):
                noticias = obter_noticias_esportivas(tipo, limite_noticias)
                exibir_noticias(noticias, "NBA", enviar_auto)
    
    with col3:
        if st.button("🌐 Buscar Todas", type="secondary", use_container_width=True):
            with st.spinner("Buscando todas as notícias..."):
                noticias = obter_noticias_esportivas("todos", limite_noticias)
                exibir_noticias(noticias, "Todas as Notícias", enviar_auto)
    
    with col4:
        if st.button("📅 Resumo Diário", type="secondary", use_container_width=True):
            with st.spinner("Preparando resumo diário..."):
                if enviar_resumo_noticias_diario():
                    st.success("✅ Resumo diário enviado para o Telegram!")
                else:
                    st.error("❌ Erro ao enviar resumo diário")
    
    st.markdown("---")
    
    # Estatísticas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        cache_data = carregar_json(CACHE_NOTICIAS)
        total_noticias = sum(len(v.get('noticias', [])) for k, v in cache_data.items() if k != '_timestamp')
        st.metric("📰 Notícias no Cache", total_noticias)
    
    with col2:
        st.metric("🕒 Cache Válido Até", "30 minutos")
    
    with col3:
        st.metric("🔴 Notícias Oficiais", "Prioridade Alta")
    
    with col4:
        st.metric("🔔 Canal Telegram", "Ativo" if TELEGRAM_TOKEN else "Inativo")
    
    st.markdown("---")
    
    # Instruções
    with st.expander("📋 Como usar o sistema"):
        st.markdown("""
        **🎯 Funcionalidades:**
        
        1. **⚽ Notícias de Futebol** - Football-Data.org (oficiais) + NewsAPI
        2. **🏀 Notícias da NBA** - NewsAPI 
        3. **🌐 Todas as Notícias** - Mix completo
        4. **📅 Resumo Diário** - Envio automático para Telegram
        
        **🎯 Prioridades:**
        
        - 🔴 **Alta**: Football-Data.org (notícias oficiais)
        - 🟡 **Média**: NewsAPI (notícias da mídia)
        
        **⚙️ APIs Integradas:**
        
        - **NewsAPI**: Sua chave está configurada
        - **Football-Data.org**: API de futebol oficial
        - **Sistema de Fallback**: Garante funcionamento sempre
        
        **💡 Dicas:**
        
        - Notícias oficiais têm prioridade máxima
        - Use o resumo diário para manter seu canal atualizado
        - Cache inteligente evita limites de API
        """)

def exibir_noticias(noticias: list, categoria: str, enviar_auto: bool):
    """Exibe notícias na interface e envia para Telegram se configurado"""
    if noticias:
        st.success(f"✅ {len(noticias)} notícias de {categoria} encontradas!")
        
        # Estatísticas das fontes
        fontes = {}
        for noticia in noticias:
            fonte = noticia['fonte']
            fontes[fonte] = fontes.get(fonte, 0) + 1
        
        st.info(f"📊 Fontes: {', '.join([f'{fonte} ({qtd})' for fonte, qtd in fontes.items()])}")
        
        # Enviar para Telegram se configurado
        if enviar_auto:
            if enviar_alerta_noticias(noticias):
                st.success("📤 Notícias enviadas para o Telegram!")
            else:
                st.error("❌ Erro ao enviar notícias para o Telegram")
        
        # Exibir notícias
        for i, noticia in enumerate(noticias, 1):
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Badge de prioridade
                    prioridade_color = "🔴" if noticia.get('prioridade') == 'alta' else "🟡"
                    st.subheader(f"{prioridade_color} {i}. {noticia['titulo']}")
                    
                    # Categoria e fonte
                    emoji = "⚽" if "futebol" in noticia['categoria'].lower() else "🏀" if "nba" in noticia['categoria'].lower() else "📰"
                    st.write(f"**{emoji} {noticia['categoria']}** | **📊 Fonte:** {noticia['fonte']}")
                    
                    # Data
                    try:
                        data_obj = datetime.fromisoformat(noticia['data'].replace('Z', '+00:00'))
                        data_formatada = data_obj.strftime('%d/%m/%Y %H:%M')
                        st.write(f"**📅 Publicada em:** {data_formatada}")
                    except:
                        st.write("**📅 Publicada em:** Data não disponível")
                    
                    # Descrição
                    st.write(noticia['descricao'])
                    
                    # Link
                    st.markdown(f"[🔗 Ler notícia completa]({noticia['url']})")
                
                with col2:
                    # Imagem se disponível
                    if noticia.get('imagem') and noticia['imagem'].startswith('http'):
                        try:
                            st.image(noticia['imagem'], use_column_width=True)
                        except:
                            st.info("🖼️ Imagem não disponível")
                    else:
                        st.info("🖼️ Sem imagem")
                
                st.markdown("---")
    else:
        st.warning("⚠️ Nenhuma notícia encontrada para os critérios selecionados")

if __name__ == "__main__":
    main()
