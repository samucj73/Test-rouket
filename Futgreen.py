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

# Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps

# =============================
# Configurações e Segurança
# =============================

# Mover para variáveis de ambiente (CRÍTICO)
API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Constantes
ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# Histórico de conferências
HISTORICO_PATH = "historico_conferencias.json"

# =============================
# Dicionário de Ligas
# =============================
LIGA_DICT = {
    "FIFA World Cup": "WC",
    "UEFA Champions League": "CL",
    "Bundesliga": "BL1",
    "Eredivisie": "DED",
    "Campeonato Brasileiro Série A": "BSA",
    "Primera Division": "PD",
    "Ligue 1": "FL1",
    "Championship (Inglaterra)": "ELC",
    "Primeira Liga (Portugal)": "PPL",
    "European Championship": "EC",
    "Serie A (Itália)": "SA",
    "Premier League (Inglaterra)": "PL"
}

# =============================
# Utilitários de Cache e Persistência
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
                agora = datetime.now().timestamp()
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                        return {}
                else:
                    if agora - os.path.getmtime(caminho) > CACHE_TIMEOUT:
                        return {}
            return dados
    except (json.JSONDecodeError, IOError) as e:
        st.error(f"Erro ao carregar {caminho}: {e}")
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
            if isinstance(dados, dict):
                dados['_timestamp'] = datetime.now().timestamp()
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except IOError as e:
        st.error(f"Erro ao salvar {caminho}: {e}")

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao() -> dict:
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados: dict):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Histórico de Conferências
# =============================
def carregar_historico() -> list:
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_historico(historico: list):
    try:
        with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar histórico: {e}")

def registrar_no_historico(resultado: dict):
    if not resultado:
        return
    historico = carregar_historico()
    registro = {
        "data_conferencia": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "home": resultado.get("home"),
        "away": resultado.get("away"),
        "tendencia": resultado.get("tendencia"),
        "estimativa": round(resultado.get("estimativa", 0), 2),
        "confianca": round(resultado.get("confianca", 0), 1),
        "placar": resultado.get("placar", "-"),
        "resultado": resultado.get("resultado", "⏳ Aguardando")
    }
    historico.append(registro)
    salvar_historico(historico)

def limpar_historico():
    """Faz backup e limpa histórico."""
    if os.path.exists(HISTORICO_PATH):
        try:
            # backup
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"historico_backup_{ts}.json"
            with open(HISTORICO_PATH, "rb") as f_src:
                with open(backup_name, "wb") as f_bak:
                    f_bak.write(f_src.read())
            os.remove(HISTORICO_PATH)
            st.success(f"🧹 Histórico limpo. Backup salvo: {backup_name}")
        except Exception as e:
            st.error(f"Erro ao limpar/hacer backup do histórico: {e}")
    else:
        st.info("⚠️ Nenhum histórico encontrado para limpar.")

# =============================
# Utilitários de Data e Formatação
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except ValueError:
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Comunicação com APIs
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID, disable_web_page_preview: bool = True) -> bool:
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

def enviar_foto_telegram(photo_bytes: io.BytesIO, caption: str = "", chat_id: str = TELEGRAM_CHAT_ID_ALT2) -> bool:
    """Envia uma foto (BytesIO) para o Telegram via sendPhoto."""
    try:
        photo_bytes.seek(0)
        files = {"photo": ("elite_master.png", photo_bytes, "image/png")}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        resp = requests.post(f"{BASE_URL_TG}/sendPhoto", data=data, files=files, timeout=15)
        return resp.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao enviar foto para Telegram: {e}")
        return False

def obter_dados_api(url: str, timeout: int = 10) -> dict | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Erro na requisição API: {e}")
        return None

def obter_classificacao(liga_id: str) -> dict:
    cache = carregar_cache_classificacao()
    if liga_id in cache:
        return cache[liga_id]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
    data = obter_dados_api(url)
    if not data:
        return {}

    standings = {}
    for s in data.get("standings", []):
        if s["type"] != "TOTAL":
            continue
        for t in s["table"]:
            name = t["team"]["name"]
            standings[name] = {
                "scored": t.get("goalsFor", 0),
                "against": t.get("goalsAgainst", 0),
                "played": t.get("playedGames", 1)
            }
    cache[liga_id] = standings
    salvar_cache_classificacao(cache)
    return standings

def obter_jogos(liga_id: str, data: str) -> list:
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
    data_api = obter_dados_api(url)
    jogos = data_api.get("matches", []) if data_api else []
    cache[key] = jogos
    salvar_cache_jogos(cache)
    return jogos

# =============================
# Lógica de Análise e Alertas
# =============================
def calcular_tendencia(home: str, away: str, classificacao: dict) -> tuple[float, float, str]:
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)

    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0) * 10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0) * 10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa) * 10)

    return estimativa, confianca, tendencia

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    status = fixture.get("status", "DESCONHECIDO")
    gols_home = fixture.get("score", {}).get("fullTime", {}).get("home")
    gols_away = fixture.get("score", {}).get("fullTime", {}).get("away")
    placar = f"{gols_home} x {gols_away}" if gols_home is not None and gols_away is not None else None

    # Obter URLs dos escudos
    escudo_home = fixture.get("homeTeam", {}).get("crest", "") or fixture.get("homeTeam", {}).get("logo", "")
    escudo_away = fixture.get("awayTeam", {}).get("crest", "") or fixture.get("awayTeam", {}).get("logo", "")
    
    # Emojis para a tendência
    emoji_tendencia = "📈" if "Mais" in tendencia else "📉" if "Menos" in tendencia else "⚡"
    
    msg = (
        f"<b>🎯 ALERTA DE GOLS 🎯</b>\n\n"
        
        f"<b>🏆 {competicao}</b>\n"
        f"<b>📅 {data_formatada}</b> | <b>⏰ {hora_formatada} BRT</b>\n"
        f"<b>📌 Status:</b> {status}\n"
    )
    
    if placar:
        msg += f"<b>📊 PLACAR ATUAL: {placar}</b>\n\n"
    else:
        msg += "\n"
    
    # Card dos times com escudos - MAIOR E MAIS DESTAQUE
    msg += (
        f"<b>━━━━━━━━━━━━━━ PARTIDA ━━━━━━━━━━━━━━</b>\n\n"
        
        f"<b>🏠 CASA:</b>\n"
        f"<b>🔵 {home}</b>\n"
    )
    
    if escudo_home:
        msg += f"<b>🛡️ ESCUDO:</b> <a href='{escudo_home}'>🔗 CLIQUE AQUI PARA VER ESCUDO</a>\n"
    
    msg += f"\n<b>────────────── 🆚 ──────────────</b>\n\n"
    
    msg += (
        f"<b>✈️ VISITANTE:</b>\n"
        f"<b>🔴 {away}</b>\n"
    )
    
    if escudo_away:
        msg += f"<b>🛡️ ESCUDO:</b> <a href='{escudo_away}'>🔗 CLIQUE AQUI PARA VER ESCUDO</a>\n"
    
    msg += f"\n<b>━━━━━━━━━━━━━━ ANÁLISE ━━━━━━━━━━━━━━</b>\n\n"
    
    # Informações de análise - MAIOR DESTAQUE
    msg += (
        f"<b>{emoji_tendencia} TENDÊNCIA DE GOLS:</b>\n"
        f"<b>🎲 {tendencia.upper()}</b>\n\n"
        
        f"<b>📊 ESTIMATIVA DE GOLS:</b>\n"
        f"<b>⚽ {estimativa:.2f} GOLS</b>\n\n"
        
        f"<b>🎯 NÍVEL DE CONFIANÇA:</b>\n"
        f"<b>💯 {confianca:.0f}%</b>\n\n"
    )
    
    # Indicador visual de força - MAIOR DESTAQUE
    if confianca >= 80:
        msg += f"<b>🔥🔥 ALTA CONFIABILIDADE 🔥🔥</b>\n"
    elif confianca >= 60:
        msg += f"<b>⚡⚡ MÉDIA CONFIABILIDADE ⚡⚡</b>\n"
    else:
        msg += f"<b>⚠️⚠️ CONFIABILIDADE MODERADA ⚠️⚠️</b>\n"
    
    msg += f"\n<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>"
    
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Funções de geração de imagem (Pillow) - LAYOUT COMPLETAMENTE REFEITO
# =============================
def baixar_imagem_url(url: str, timeout: int = 8) -> Image.Image | None:
    """Tenta baixar uma imagem e retornar PIL.Image. Retorna None se falhar."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return img
    except Exception:
        return None

def criar_fonte(tamanho):
    """Tenta criar uma fonte com o tamanho especificado"""
    try:
        # Tenta carregar fontes comuns
        fontes_tentativas = [
            "arial.ttf",
            "Arial.ttf", 
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Arial.ttf"
        ]
        
        for fonte_path in fontes_tentativas:
            try:
                return ImageFont.truetype(fonte_path, tamanho)
            except:
                continue
                
        # Se nenhuma fonte TTF funcionar, cria uma fonte bitmap
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def gerar_poster_elite(jogos: list, titulo: str = "🔥 Jogos de Alta Confiança (Elite Master)") -> io.BytesIO:
    """
    Gera um pôster vertical com a lista de jogos. Retorna BytesIO com PNG.
    LAYOUT COMPLETAMENTE REFEITO - INFORMAÇÕES ABAIXO DOS ESCUDOS
    """
    # CONFIGURAÇÕES GIGANTES
    LARGURA = 2000  # AUMENTADO MASSIVAMENTE
    ALTURA_TOPO = 350 # AUMENTADO MASSIVAMENTE
    ALTURA_POR_JOGO = 900 # AUMENTADO MASSIVAMENTE para caber informações abaixo
    PADDING = 100  # AUMENTADO MASSIVAMENTE
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas gigante
    img = Image.new("RGB", (LARGURA, altura_total), color=(18, 18, 20))
    draw = ImageDraw.Draw(img)

    # FONTES GIGANTES
    st.info("🔄 Carregando fontes com tamanhos MASSIVOS...")
    FONTE_TITULO = criar_fonte(100)  # MASSIVO
    FONTE_SUBTITULO = criar_fonte(60)  # MASSIVO  
    FONTE_TIMES = criar_fonte(65)  # MASSIVO
    FONTE_INFO = criar_fonte(48)  # MASSIVO
    FONTE_DETALHES = criar_fonte(60)  # MASSIVO

    # Título PRINCIPAL
    draw.text((PADDING, 100), titulo, font=FONTE_TITULO, fill=(255, 215, 0))
    
    # Subtítulo
    subtitulo = f"Gerado: {datetime.now().strftime('%Y-%m-%d %H:%M')} - Total: {jogos_count} jogos"
    draw.text((PADDING, 220), subtitulo, font=FONTE_SUBTITULO, fill=(200, 200, 200))

    y_pos = ALTURA_TOPO
    TAMANHO_ESCUDO = 400  # ESCUDOS MASSIVOS

    for idx, jogo in enumerate(jogos):
        # Caixa do jogo - MUITO MAIOR
        x0, y0 = PADDING, y_pos + 30
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 30
        
        # Fundo da caixa do jogo
        draw.rounded_rectangle([x0, y0, x1, y1], radius=25, fill=(28, 28, 30))
        
        # CENTRALIZAR OS ESCUDOS NA PARTE SUPERIOR
        espaco_total = LARGURA - 2 * PADDING
        espaco_entre_escudos = 800
        largura_total_escudos = 2 * TAMANHO_ESCUDO + espaco_entre_escudos
        x_inicio_escudos = PADDING + (espaco_total - largura_total_escudos) // 2
        
        # Posição dos escudos (lado a lado)
        x_escudo_home = x_inicio_escudos
        x_escudo_away = x_escudo_home + TAMANHO_ESCUDO + espaco_entre_escudos
        y_escudos = y0 + 180
        
        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get("escudo_home", ""))
        escudo_away = baixar_imagem_url(jogo.get("escudo_away", ""))
        
        # Função para desenhar escudo redondo
        def desenhar_escudo(imagem, x, y, tamanho):
            if imagem:
                try:
                    # Redimensionar mantendo proporção
                    imagem.thumbnail((tamanho, tamanho), Image.LANCZOS)
                    
                    # Criar máscara circular
                    mask = Image.new("L", (tamanho, tamanho), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, tamanho, tamanho), fill=255)
                    
                    # Calcular offset para centralizar
                    offset_x = (tamanho - imagem.width) // 2
                    offset_y = (tamanho - imagem.height) // 2
                    
                    # Criar imagem de fundo e colar o escudo
                    bg = Image.new("RGBA", (tamanho, tamanho), (255, 255, 255, 0))
                    bg.paste(imagem, (offset_x, offset_y))
                    
                    # Aplicar máscara circular
                    img.paste(bg, (x, y), mask)
                except Exception as e:
                    st.error(f"Erro ao desenhar escudo: {e}")
            else:
                # Placeholder circular
                draw.ellipse([x, y, x + tamanho, y + tamanho], fill=(60, 60, 60))
                iniciais = "TM"
                try:
                    bbox = draw.textbbox((0, 0), iniciais, font=FONTE_TIMES)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                    draw.text((x + (tamanho - w)/2, y + (tamanho - h)/2), iniciais, font=FONTE_TIMES, fill=(255, 255, 255))
                except:
                    draw.text((x + tamanho//3, y + tamanho//3), iniciais, font=FONTE_TIMES, fill=(255, 255, 255))

        # Desenhar escudos (lado a lado)
        desenhar_escudo(escudo_home, x_escudo_home, y_escudos, TAMANHO_ESCUDO)
        desenhar_escudo(escudo_away, x_escudo_away, y_escudos, TAMANHO_ESCUDO)

        # NOME DOS TIMES (CENTRALIZADO ABAIXO DOS ESCUDOS)
        y_nomes = y_escudos + TAMANHO_ESCUDO + 40
        
        # Nome do time da casa (esquerda)
        nome_home = jogo['home']
        try:
            bbox_home = draw.textbbox((0, 0), nome_home, font=FONTE_TIMES)
            w_home = bbox_home[2] - bbox_home[0]
            x_home = x_escudo_home + (TAMANHO_ESCUDO - w_home) // 2
            draw.text((x_home, y_nomes), nome_home, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_escudo_home, y_nomes), nome_home, font=FONTE_TIMES, fill=(255, 255, 255))

        # VS (no centro)
        vs_text = "VS"
        try:
            bbox_vs = draw.textbbox((0, 0), vs_text, font=FONTE_TIMES)
            w_vs = bbox_vs[2] - bbox_vs[0]
            x_vs = (LARGURA - w_vs) // 2
            draw.text((x_vs, y_nomes), vs_text, font=FONTE_TIMES, fill=(255, 215, 0))
        except:
            draw.text((LARGURA // 2 - 50, y_nomes), vs_text, font=FONTE_TIMES, fill=(255, 215, 0))

        # Nome do time visitante (direita)
        nome_away = jogo['away']
        try:
            bbox_away = draw.textbbox((0, 0), nome_away, font=FONTE_TIMES)
            w_away = bbox_away[2] - bbox_away[0]
            x_away = x_escudo_away + (TAMANHO_ESCUDO - w_away) // 2
            draw.text((x_away, y_nomes), nome_away, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_escudo_away, y_nomes), nome_away, font=FONTE_TIMES, fill=(255, 255, 255))

        # INFORMAÇÕES DA ANÁLISE (CENTRALIZADO ABAIXO DOS NOMES)
        y_info = y_nomes + 80
        
        # Liga
        liga_text = f"🏆 {jogo['liga']}"
        try:
            bbox_liga = draw.textbbox((0, 0), liga_text, font=FONTE_INFO)
            w_liga = bbox_liga[2] - bbox_liga[0]
            x_liga = (LARGURA - w_liga) // 2
            draw.text((x_liga, y_info), liga_text, font=FONTE_INFO, fill=(200, 200, 255))
        except:
            draw.text((PADDING + 100, y_info), liga_text, font=FONTE_INFO, fill=(200, 200, 255))

        # Tendência
        y_tendencia = y_info + 60
        tendencia_text = f"📈 {jogo['tendencia']}"
        try:
            bbox_tendencia = draw.textbbox((0, 0), tendencia_text, font=FONTE_INFO)
            w_tendencia = bbox_tendencia[2] - bbox_tendencia[0]
            x_tendencia = (LARGURA - w_tendencia) // 2
            draw.text((x_tendencia, y_tendencia), tendencia_text, font=FONTE_INFO, fill=(255, 215, 0))
        except:
            draw.text((PADDING + 100, y_tendencia), tendencia_text, font=FONTE_INFO, fill=(255, 215, 0))

        # Estimativa e Confiança
        y_est_conf = y_tendencia + 60
        est_conf_text = f"⚽ Estimativa: {jogo['estimativa']:.2f} gols  |  💯 Confiança: {jogo['confianca']:.0f}%"
        try:
            bbox_est_conf = draw.textbbox((0, 0), est_conf_text, font=FONTE_DETALHES)
            w_est_conf = bbox_est_conf[2] - bbox_est_conf[0]
            x_est_conf = (LARGURA - w_est_conf) // 2
            draw.text((x_est_conf, y_est_conf), est_conf_text, font=FONTE_DETALHES, fill=(200, 200, 200))
        except:
            draw.text((PADDING + 100, y_est_conf), est_conf_text, font=FONTE_DETALHES, fill=(200, 200, 200))

        # Hora do jogo (CENTRALIZADO NA PARTE INFERIOR)
        y_hora = y_est_conf + 70
        hora_formatada = jogo["hora"].strftime("%d/%m/%Y %H:%M") if isinstance(jogo["hora"], datetime) else str(jogo["hora"])
        hora_text = f"🕒 {hora_formatada} BRT"
        try:
            bbox_hora = draw.textbbox((0, 0), hora_text, font=FONTE_DETALHES)
            w_hora = bbox_hora[2] - bbox_hora[0]
            x_hora = (LARGURA - w_hora) // 2
            draw.text((x_hora, y_hora), hora_text, font=FONTE_DETALHES, fill=(150, 200, 255))
        except:
            draw.text((PADDING + 100, y_hora), hora_text, font=FONTE_DETALHES, fill=(150, 200, 255))

        y_pos += ALTURA_POR_JOGO

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Pôster gerado com {len(jogos)} jogos - Dimensões: {LARGURA}x{altura_total}")
    st.info("🎯 Layout: Escudos acima, informações abaixo - Tudo MASSIVO!")
    return buffer

# =============================
# Alerta: Jogos com confiança >=threshold (gera pôster e envia)
# =============================
def enviar_alerta_conf_criar_poster(jogos_conf: list, threshold: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Gera pôster com Pillow e envia ao Telegram (uma única imagem com todos os jogos)."""
    if not jogos_conf:
        st.warning("⚠️ Nenhum jogo com confiança suficiente para gerar pôster.")
        return

    # Determinar período (datas dos jogos)
    datas = []
    for j in jogos_conf:
        if isinstance(j.get("hora"), datetime):
            datas.append(j["hora"].date())
    data_inicio = datas[0].strftime("%Y-%m-%d") if datas else "-"
    data_fim = datas[-1].strftime("%Y-%m-%d") if datas else "-"
    titulo = f"🔥 JOGOS DE ALTA CONFIANÇA (≥{threshold}%)"

    st.info(f"🎨 Gerando pôster com {len(jogos_conf)} jogos...")
    
    try:
        poster = gerar_poster_elite(jogos_conf, titulo=titulo)
        caption = (
            f"<b>📅 PERÍODO: {data_inicio} → {data_fim}</b>\n"
            f"<b>📋 TOTAL: {len(jogos_conf)} JOGOS</b>\n"
            f"<b>⚽ CONFIANÇA MÍNIMA: {threshold}%</b>\n\n"
            f"<b>🎯 JOGOS SELECIONADOS PELA INTELIGÊNCIA ARTIFICIAL</b>"
        )
        
        st.info("📤 Enviando pôster para o Telegram...")
        ok = enviar_foto_telegram(poster, caption=caption, chat_id=chat_id)
        
        if ok:
            st.success("🚀 Pôster de alta confiança enviado ao Telegram!")
        else:
            st.error("❌ Falha ao enviar pôster ao Telegram. Tentando enviar mensagem de texto como fallback.")
            # fallback texto
            msg = f"🔥 Jogos ≥{threshold}% (Não foi possível gerar a imagem):\nTotal: {len(jogos_conf)}"
            enviar_telegram(msg, chat_id=chat_id)
    except Exception as e:
        st.error(f"Erro ao gerar/enviar pôster: {e}")
        msg = f"🔥 Jogos ≥{threshold}% (Não foi possível gerar a imagem):\nTotal: {len(jogos_conf)}"
        enviar_telegram(msg, chat_id=chat_id)

# =============================
# Geração de Relatórios (PDF)
# =============================
def gerar_relatorio_pdf(jogos_conferidos: list) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter,
                          rightMargin=20, leftMargin=20,
                          topMargin=20, bottomMargin=20)
    data = [["Jogo", "Tendência", "Estimativa", "Confiança",
             "Placar", "Status", "Resultado", "Hora"]] + jogos_conferidos
    table = Table(data, repeatRows=1,
                 colWidths=[120, 70, 60, 60, 50, 70, 60, 70])
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4B4B4B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F5F5F5")),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ])
    for i in range(1, len(data)):
        bg_color = colors.HexColor("#E0E0E0") if i % 2 == 0 else colors.HexColor("#F5F5F5")
        style.add('BACKGROUND', (0,i), (-1,i), bg_color)
    table.setStyle(style)
    pdf.build([table])
    buffer.seek(0)
    return buffer

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols")

    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Jogos no Top (visualização)", [3, 5, 10], index=0)
        enviar_alerta_70 = st.checkbox("🚨 Enviar alerta com jogos acima do limiar de confiança", value=True)
        threshold = st.slider("Limiar de confiança (%)", min_value=50, max_value=95, value=70, step=1)
        st.markdown("----")
        st.info("Ajuste o limiar para enviar/mostrar apenas jogos acima da confiança selecionada.")

    # Controles principais
    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True, help="Buscar jogos de todas as ligas disponíveis")

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))

    # Processamento
    if st.button("🔍 Buscar Partidas", type="primary"):
        processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, enviar_alerta_70, threshold)

    # Ações
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Atualizar Status"):
            atualizar_status_partidas()
    with col2:
        if st.button("📊 Conferir Resultados"):
            conferir_resultados()
    with col3:
        if st.button("🧹 Limpar Cache"):
            limpar_caches()

    # Painel desempenho
    st.markdown("---")
    st.subheader("📊 Painel de Desempenho (Histórico)")
    usar_periodo = st.checkbox("🔎 Usar período específico", value=False)
    qtd_default = 50
    last_n = st.number_input("Últimos N jogos (se período não for usado)", min_value=1, max_value=1000, value=qtd_default, step=1)
    colp1, colp2 = st.columns(2)
    with colp1:
        if usar_periodo:
            data_inicio = st.date_input("Data inicial", value=(datetime.today() - timedelta(days=30)).date())
            data_fim = st.date_input("Data final", value=datetime.today().date())
            if data_fim < data_inicio:
                st.error("Data final não pode ser anterior à inicial.")
    with colp2:
        if st.button("📈 Calcular Desempenho"):
            if usar_periodo:
                calcular_desempenho_periodo(data_inicio, data_fim)
            else:
                calcular_desempenho(qtd_jogos=last_n)

    if st.button("🧹 Limpar Histórico de Desempenho"):
        limpar_historico()

def processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, enviar_alerta_enabled: bool, threshold: int):
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")
    top_jogos = []
    progress_bar = st.progress(0)
    total_ligas = len(ligas_busca)

    for i, liga_id in enumerate(ligas_busca):
        classificacao = obter_classificacao(liga_id)
        jogos = obter_jogos(liga_id, hoje)

        for match in jogos:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)

            verificar_enviar_alerta(match, tendencia, estimativa, confianca)

            # extrair escudos (crest / logo / vazio)
            escudo_home = ""
            escudo_away = ""
            try:
                escudo_home = match.get("homeTeam", {}).get("crest") or match.get("homeTeam", {}).get("logo") or ""
                escudo_away = match.get("awayTeam", {}).get("crest") or match.get("awayTeam", {}).get("logo") or ""
            except Exception:
                escudo_home = ""
                escudo_away = ""

            top_jogos.append({
                "id": match["id"],
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3),
                "status": match.get("status", "DESCONHECIDO"),
                "escudo_home": escudo_home,
                "escudo_away": escudo_away
            })
        progress_bar.progress((i + 1) / total_ligas)

    # Filtrar por limiar (threshold) e status
    jogos_filtrados_threshold = [
        j for j in top_jogos
        if j["confianca"] >= threshold and j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
    ]

    if jogos_filtrados_threshold:
        enviar_top_jogos(jogos_filtrados_threshold, top_n)
        st.success(f"✅ Análise concluída! {len(jogos_filtrados_threshold)} jogos com confiança ≥{threshold}% processados.")
    else:
        st.warning(f"⚠️ Nenhum jogo com confiança ≥{threshold}% encontrado.")

    # Se habilitado, gerar pôster e enviar ao Telegram com todos os jogos ≥ threshold
    if enviar_alerta_enabled and jogos_filtrados_threshold:
        enviar_alerta_conf_criar_poster(jogos_filtrados_threshold, threshold, chat_id=TELEGRAM_CHAT_ID_ALT2)

def enviar_top_jogos(jogos: list, top_n: int):
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]
    if not jogos_filtrados:
        st.warning("⚠️ Nenhum jogo elegível para o Top Jogos (todos já iniciados ou finalizados).")
        return
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]
    msg = f"📢 TOP {top_n} Jogos do Dia (confiança alta)\n\n"
    for j in top_jogos_sorted:
        hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
            f"💯 Confiança: {j['confianca']:.0f}%\n\n"
        )
    if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2, disable_web_page_preview=True):
        st.success(f"🚀 Top {top_n} jogos enviados para o canal!")
    else:
        st.error("❌ Erro ao enviar top jogos para o Telegram")

def atualizar_status_partidas():
    cache_jogos = carregar_cache_jogos()
    mudou = False
    for key in list(cache_jogos.keys()):
        if key == "_timestamp":
            continue
        liga_id, data = key.split("_", 1)
        try:
            url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
            data_api = obter_dados_api(url)
            if data_api and "matches" in data_api:
                cache_jogos[key] = data_api["matches"]
                mudou = True
        except Exception as e:
            st.error(f"Erro ao atualizar liga {liga_id}: {e}")
    if mudou:
        salvar_cache_jogos(cache_jogos)
        st.success("✅ Status das partidas atualizado!")
    else:
        st.info("ℹ️ Nenhuma atualização disponível.")

def conferir_resultados():
    alertas = carregar_alertas()
    jogos_cache = carregar_cache_jogos()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para conferir.")
        return
    jogos_conferidos = []
    mudou = False
    for fixture_id, info in list(alertas.items()):
        if info.get("conferido"):
            continue
        jogo_dado = None
        for key, jogos in jogos_cache.items():
            if key == "_timestamp":
                continue
            for match in jogos:
                if str(match["id"]) == fixture_id:
                    jogo_dado = match
                    break
            if jogo_dado:
                break
        if not jogo_dado:
            continue
        resultado_info = processar_resultado_jogo(jogo_dado, info)
        if resultado_info:
            exibir_resultado_streamlit(resultado_info)
            if resultado_info["status"] == "FINISHED":
                enviar_resultado_telegram(resultado_info)
                registrar_no_historico(resultado_info)
                info["conferido"] = True
                mudou = True
        jogos_conferidos.append(preparar_dados_pdf(jogo_dado, info, resultado_info))
    if mudou:
        salvar_alertas(alertas)
        st.success("✅ Resultados conferidos e atualizados!")
    if jogos_conferidos:
        gerar_pdf_jogos(jogos_conferidos)

def processar_resultado_jogo(jogo: dict, info: dict) -> dict | None:
    home = jogo["homeTeam"]["name"]
    away = jogo["awayTeam"]["name"]
    status = jogo.get("status", "DESCONHECIDO")
    gols_home = jogo.get("score", {}).get("fullTime", {}).get("home")
    gols_away = jogo.get("score", {}).get("fullTime", {}).get("away")
    placar = f"{gols_home} x {gols_away}" if gols_home is not None and gols_away is not None else "-"
    total_gols = (gols_home or 0) + (gols_away or 0)
    resultado = "⏳ Aguardando"
    if status == "FINISHED":
        tendencia = info["tendencia"]
        if "Mais 2.5" in tendencia:
            resultado = "🟢 GREEN" if total_gols > 2 else "🔴 RED"
        elif "Mais 1.5" in tendencia:
            resultado = "🟢 GREEN" if total_gols > 1 else "🔴 RED"
        elif "Menos 2.5" in tendencia:
            resultado = "🟢 GREEN" if total_gols < 3 else "🔴 RED"
        else:
            resultado = "⚪ INDEFINIDO"
    return {
        "home": home,
        "away": away,
        "status": status,
        "placar": placar,
        "tendencia": info["tendencia"],
        "estimativa": info["estimativa"],
        "confianca": info["confianca"],
        "resultado": resultado,
        "total_gols": total_gols
    }

def exibir_resultado_streamlit(resultado: dict):
    bg_color = "#1e4620" if resultado["resultado"] == "🟢 GREEN" else "#5a1e1e" if resultado["resultado"] == "🔴 RED" else "#2c2c2c"
    st.markdown(f"""
    <div style="border:1px solid #444; border-radius:10px; padding:12px; margin-bottom:10px;
                background-color:{bg_color}; font-size:15px; color:#f1f1f1;">
        <b>🏟️ {resultado['home']} vs {resultado['away']}</b><br>
        📌 Status: <b>{resultado['status']}</b><br>
        ⚽ Tendência: <b>{resultado['tendencia']}</b> | Estim.: {resultado['estimativa']:.2f} | Conf.: {resultado['confianca']:.0f}%<br>
        📊 Placar: <b>{resultado['placar']}</b><br>
        ✅ Resultado: {resultado['resultado']}
    </div>
    """, unsafe_allow_html=True)

def enviar_resultado_telegram(resultado: dict):
    # Emojis para a tendência
    emoji_tendencia = "📈" if "Mais" in resultado['tendencia'] else "📉" if "Menos" in resultado['tendencia'] else "⚡"
    emoji_resultado = "🟢" if "GREEN" in resultado['resultado'] else "🔴" if "RED" in resultado['resultado'] else "⚪"
    
    msg = (
        f"<b>🎯 RESULTADO CONFERIDO 🎯</b>\n\n"
        
        f"<b>━━━━━━━━━━━━━━ PARTIDA ━━━━━━━━━━━━━━</b>\n\n"
        
        f"<b>🏠 CASA:</b>\n"
        f"<b>🔵 {resultado['home']}</b>\n\n"
        
        f"<b>✈️ VISITANTE:</b>\n"
        f"<b>🔴 {resultado['away']}</b>\n\n"
        
        f"<b>━━━━━━━━━━━━━━ RESULTADO ━━━━━━━━━━━━━━</b>\n\n"
        
        f"<b>🎯 PLACAR FINAL:</b>\n"
        f"<b>🏆 {resultado['placar']}</b>\n\n"
        
        f"<b>⚽ TOTAL DE GOLS:</b>\n"
        f"<b>📈 {resultado['total_gols']} GOLS</b>\n\n"
        
        f"<b>━━━━━━━━━━━━━━ ANÁLISE ━━━━━━━━━━━━━━</b>\n\n"
        
        f"<b>{emoji_tendencia} TENDÊNCIA:</b>\n"
        f"<b>🎲 {resultado['tendencia']}</b>\n\n"
        
        f"<b>📊 ESTIMATIVA:</b>\n"
        f"<b>⚽ {resultado['estimativa']:.2f} GOLS</b>\n\n"
        
        f"<b>🎯 CONFIANÇA:</b>\n"
        f"<b>💯 {resultado['confianca']:.0f}%</b>\n\n"
        
        f"<b>━━━━━━━━━━━━━━ VEREDITO ━━━━━━━━━━━━━━</b>\n\n"
        
        f"<b>{emoji_resultado} RESULTADO:</b>\n"
        f"<b>🎯 {resultado['resultado']}</b>\n\n"
        
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

def preparar_dados_pdf(jogo: dict, info: dict, resultado: dict) -> list:
    home = abreviar_nome(jogo["homeTeam"]["name"])
    away = abreviar_nome(jogo["awayTeam"]["name"])
    hora = datetime.fromisoformat(jogo["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3)
    placar = resultado["placar"] if resultado else "-"
    res = resultado["resultado"] if resultado else "⏳ Aguardando"
    return [
        f"{home} vs {away}",
        info["tendencia"],
        f"{info['estimativa']:.2f}",
        f"{info['confianca']:.0f}%",
        placar,
        jogo.get("status", "DESCONHECIDO"),
        res,
        hora.strftime("%d/%m %H:%M")
    ]

def gerar_pdf_jogos(jogos_conferidos: list):
    df_conferidos = pd.DataFrame(jogos_conferidos, columns=[
        "Jogo", "Tendência", "Estimativa", "Confiança",
        "Placar", "Status", "Resultado", "Hora"
    ])
    buffer = gerar_relatorio_pdf(jogos_conferidos)
    st.download_button(
        label="📄 Baixar Relatório PDF",
        data=buffer,
        file_name=f"jogos_conferidos_{datetime.today().strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf"
    )

def limpar_caches():
    try:
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
        st.success("✅ Caches limpos com sucesso!")
    except Exception as e:
        st.error(f"❌ Erro ao limpar caches: {e}")

# =============================
# Cálculo de Desempenho
# =============================
def _parse_date_str(data_str: str) -> datetime | None:
    if not data_str:
        return None
    try:
        return datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(data_str, "%Y-%m-%d")
        except Exception:
            return None

def calcular_desempenho(qtd_jogos: int = 50):
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
    historico_considerado = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico[:]
    datas = []
    for j in historico_considerado:
        d = _parse_date_str(j.get("data_conferencia", ""))
        if d:
            datas.append(d.date())
    data_inicio = datas[0].strftime("%Y-%m-%d") if datas else "-"
    data_fim = datas[-1].strftime("%Y-%m-%d") if datas else "-"
    greens = sum(1 for j in historico_considerado if isinstance(j.get("resultado"), str) and "🟢" in j["resultado"])
    reds = sum(1 for j in historico_considerado if isinstance(j.get("resultado"), str) and "🔴" in j["resultado"])
    total = greens + reds
    taxa_acerto = (greens / total * 100) if total > 0 else 0.0
    st.subheader("📈 Desempenho (Últimos N jogos)")
    st.write(f"📅 Período considerado: {data_inicio} → {data_fim}")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ GREENs", greens)
    c2.metric("❌ REDs", reds)
    c3.metric("🎯 Taxa de Acerto (%)", f"{taxa_acerto:.1f}%")
    st.write(f"📊 Jogos considerados (com resultado): {total} — (analisados: {len(historico_considerado)})")
    df = pd.DataFrame(historico_considerado)
    if not df.empty:
        st.markdown("Registros considerados (mais recentes primeiro):")
        st.dataframe(df.sort_values("data_conferencia", ascending=False).head(200))
    msg = (
        f"📊 <b>DESEMPENHO DAS PREVISÕES</b>\n\n"
        f"📅 Período: {data_inicio} → {data_fim}\n"
        f"📋 Jogos analisados (com resultado): {total}\n"
        f"✅ GREENs: {greens}\n"
        f"❌ REDs: {reds}\n"
        f"🎯 Taxa de Acerto: <b>{taxa_acerto:.1f}%</b>\n\n"
        f"📌 Baseado nos últimos {len(historico_considerado)} registros do histórico."
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
    st.success("📤 Desempenho enviado para o Telegram!")

def calcular_desempenho_periodo(data_inicio: datetime.date, data_fim: datetime.date):
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
    if isinstance(data_inicio, datetime):
        data_inicio = data_inicio.date()
    if isinstance(data_fim, datetime):
        data_fim = data_fim.date()
    consider = []
    for j in historico:
        d = _parse_date_str(j.get("data_conferencia", ""))
        if not d:
            continue
        d_date = d.date()
        if data_inicio <= d_date <= data_fim:
            consider.append(j)
    if not consider:
        st.info("ℹ️ Nenhum registro no histórico para o período selecionado.")
        return
    greens = sum(1 for j in consider if isinstance(j.get("resultado"), str) and "🟢" in j["resultado"])
    reds = sum(1 for j in consider if isinstance(j.get("resultado"), str) and "🔴" in j["resultado"])
    total = greens + reds
    taxa_acerto = (greens / total * 100) if total > 0 else 0.0
    st.subheader("📈 Desempenho (Período selecionado)")
    st.write(f"📅 Período considerado: {data_inicio} → {data_fim}")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ GREENs", greens)
    c2.metric("❌ REDs", reds)
    c3.metric("🎯 Taxa de Acerto (%)", f"{taxa_acerto:.1f}%")
    st.write(f"📊 Jogos considerados (com resultado): {total} — (registros encontrados: {len(consider)})")
    df = pd.DataFrame(consider)
    if not df.empty:
        st.markdown("Registros no período (mais recentes primeiro):")
        st.dataframe(df.sort_values("data_conferencia", ascending=False).head(500))
    msg = (
        f"📊 <b>DESEMPENHO DAS PREVISÕES</b>\n\n"
        f"📅 Período: {data_inicio} → {data_fim}\n"
        f"📋 Jogos analisados (com resultado): {total}\n"
        f"✅ GREENs: {greens}\n"
        f"❌ REDs: {reds}\n"
        f"🎯 Taxa de Acerto: <b>{taxa_acerto:.1f}%</b>\n\n"
        f"📌 Baseado em {len(consider)} registros do histórico no período selecionado."
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
    st.success("📤 Desempenho do período enviado para o Telegram!")

if __name__ == "__main__":
    main()
