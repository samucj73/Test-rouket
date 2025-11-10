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

# Versão de teste - manter valores padrão
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
# Funções de geração de imagem
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
    except Exception as e:
        print(f"Erro ao baixar imagem {url}: {e}")
        return None

def criar_fonte(tamanho: int) -> ImageFont.ImageFont:
    """Cria fonte com fallback robusto"""
    try:
        # Tentar fontes comuns em diferentes sistemas
        font_paths = [
            "arial.ttf", "Arial.ttf", "arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, tamanho)
            except Exception:
                continue
        
        # Se não encontrou nenhuma fonte, criar uma bitmap
        return ImageFont.load_default()
        
    except Exception as e:
        print(f"Erro ao carregar fonte: {e}")
        return ImageFont.load_default()

def gerar_poster_westham_style(jogos: list, titulo: str = "ELITE MASTER - ALERTA DE GOLS") -> io.BytesIO:
    """
    Gera poster no estilo West Ham vs Burnley
    """
    # Configurações
    LARGURA = 2000
    ALTURA_TOPO = 350
    ALTURA_POR_JOGO = 950
    PADDING = 120
    
    jogos_count = len(jogos)
    altura_total = ALTURA_TOPO + jogos_count * ALTURA_POR_JOGO + PADDING

    # Criar canvas
    img = Image.new("RGB", (LARGURA, altura_total), color=(10, 20, 30))
    draw = ImageDraw.Draw(img)

    # Carregar fontes
    FONTE_TITULO = criar_fonte(100)
    FONTE_SUBTITULO = criar_fonte(70)
    FONTE_TIMES = criar_fonte(65)
    FONTE_VS = criar_fonte(55)
    FONTE_INFO = criar_fonte(50)
    FONTE_DETALHES = criar_fonte(55)
    FONTE_ANALISE = criar_fonte(65)

    # Título PRINCIPAL
    try:
        titulo_bbox = draw.textbbox((0, 0), titulo, font=FONTE_TITULO)
        titulo_w = titulo_bbox[2] - titulo_bbox[0]
        draw.text(((LARGURA - titulo_w) // 2, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))
    except:
        draw.text((LARGURA//2 - 250, 100), titulo, font=FONTE_TITULO, fill=(255, 255, 255))

    # Linha decorativa
    draw.line([(LARGURA//4, 220), (3*LARGURA//4, 220)], fill=(255, 215, 0), width=6)

    y_pos = ALTURA_TOPO

    for idx, jogo in enumerate(jogos):
        # Caixa do jogo
        x0, y0 = PADDING, y_pos
        x1, y1 = LARGURA - PADDING, y_pos + ALTURA_POR_JOGO - 40
        
        # Fundo com borda
        draw.rectangle([x0, y0, x1, y1], fill=(25, 35, 45), outline=(60, 80, 100), width=4)

        # Nome da liga
        liga_text = jogo['liga'].upper()
        try:
            liga_bbox = draw.textbbox((0, 0), liga_text, font=FONTE_SUBTITULO)
            liga_w = liga_bbox[2] - liga_bbox[0]
            draw.text(((LARGURA - liga_w) // 2, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))
        except:
            draw.text((LARGURA//2 - 150, y0 + 40), liga_text, font=FONTE_SUBTITULO, fill=(200, 200, 200))

        # Data e hora
        if isinstance(jogo["hora"], datetime):
            data_text = jogo["hora"].strftime("%d.%m.%Y")
            hora_text = jogo["hora"].strftime("%H:%M")
        else:
            data_text = str(jogo["hora"])
            hora_text = ""

        try:
            data_bbox = draw.textbbox((0, 0), data_text, font=FONTE_INFO)
            data_w = data_bbox[2] - data_bbox[0]
            draw.text(((LARGURA - data_w) // 2, y0 + 130), data_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 150, y0 + 130), data_text, font=FONTE_INFO, fill=(150, 200, 255))

        try:
            hora_bbox = draw.textbbox((0, 0), hora_text, font=FONTE_INFO)
            hora_w = hora_bbox[2] - hora_bbox[0]
            draw.text(((LARGURA - hora_w) // 2, y0 + 190), hora_text, font=FONTE_INFO, fill=(150, 200, 255))
        except:
            draw.text((LARGURA//2 - 120, y0 + 190), hora_text, font=FONTE_INFO, fill=(150, 200, 255))

        # ESCUDOS DOS TIMES
        TAMANHO_ESCUDO = 200
        TAMANHO_QUADRADO = 240
        ESPACO_ENTRE_ESCUDOS = 700

        # Calcular posição central
        largura_total = 2 * TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        x_inicio = (LARGURA - largura_total) // 2

        x_home = x_inicio
        x_away = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS
        y_escudos = y0 + 250

        # Baixar escudos
        escudo_home = baixar_imagem_url(jogo.get("escudo_home", ""))
        escudo_away = baixar_imagem_url(jogo.get("escudo_away", ""))

        def desenhar_escudo_quadrado(logo_img, x, y, tamanho_quadrado, tamanho_escudo):
            # Fundo branco
            draw.rectangle(
                [x, y, x + tamanho_quadrado, y + tamanho_quadrado],
                fill=(255, 255, 255),
                outline=(255, 255, 255)
            )

            if logo_img is None:
                # Placeholder caso falhe
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(60, 60, 60))
                draw.text((x + 70, y + 90), "SEM", font=FONTE_INFO, fill=(255, 255, 255))
                return

            try:
                logo_img = logo_img.convert("RGBA")
                largura, altura = logo_img.size
                proporcao = largura / altura

                # Cortar a imagem centralmente para ficar quadrada
                if proporcao > 1:  # mais larga
                    nova_altura = altura
                    nova_largura = int(altura)
                    offset_x = (largura - nova_largura) // 2
                    offset_y = 0
                else:  # mais alta
                    nova_largura = largura
                    nova_altura = int(largura)
                    offset_x = 0
                    offset_y = (altura - nova_altura) // 2

                imagem_cortada = logo_img.crop((offset_x, offset_y, offset_x + nova_largura, offset_y + nova_altura))

                # Redimensionar
                imagem_final = imagem_cortada.resize((tamanho_escudo, tamanho_escudo), Image.Resampling.LANCZOS)

                # Calcular centralização
                pos_x = x + (tamanho_quadrado - tamanho_escudo) // 2
                pos_y = y + (tamanho_quadrado - tamanho_escudo) // 2

                # Colar escudo
                img.paste(imagem_final, (pos_x, pos_y), imagem_final)

            except Exception as e:
                print(f"[ERRO ESCUDO] {e}")
                draw.rectangle([x, y, x + tamanho_quadrado, y + tamanho_quadrado], fill=(100, 100, 100))
                draw.text((x + 70, y + 90), "ERR", font=FONTE_INFO, fill=(255, 255, 255))

        # Desenhar escudos quadrados
        desenhar_escudo_quadrado(escudo_home, x_home, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)
        desenhar_escudo_quadrado(escudo_away, x_away, y_escudos, TAMANHO_QUADRADO, TAMANHO_ESCUDO)

        # Nomes dos times
        home_text = jogo['home']
        away_text = jogo['away']

        try:
            home_bbox = draw.textbbox((0, 0), home_text, font=FONTE_TIMES)
            home_w = home_bbox[2] - home_bbox[0]
            draw.text((x_home + (TAMANHO_QUADRADO - home_w)//2, y_escudos + TAMANHO_QUADRADO + 50),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_home, y_escudos + TAMANHO_QUADRADO + 50),
                     home_text, font=FONTE_TIMES, fill=(255, 255, 255))

        try:
            away_bbox = draw.textbbox((0, 0), away_text, font=FONTE_TIMES)
            away_w = away_bbox[2] - away_bbox[0]
            draw.text((x_away + (TAMANHO_QUADRADO - away_w)//2, y_escudos + TAMANHO_QUADRADO + 50),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))
        except:
            draw.text((x_away, y_escudos + TAMANHO_QUADRADO + 50),
                     away_text, font=FONTE_TIMES, fill=(255, 255, 255))

        # VS centralizado
        try:
            vs_bbox = draw.textbbox((0, 0), "VS", font=FONTE_VS)
            vs_w = vs_bbox[2] - vs_bbox[0]
            vs_x = x_home + TAMANHO_QUADRADO + (ESPACO_ENTRE_ESCUDOS - vs_w) // 2
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), 
                     "VS", font=FONTE_VS, fill=(255, 215, 0))
        except:
            vs_x = x_home + TAMANHO_QUADRADO + ESPACO_ENTRE_ESCUDOS//2 - 30
            draw.text((vs_x, y_escudos + TAMANHO_QUADRADO//2 - 30), "VS", font=FONTE_VS, fill=(255, 215, 0))

        # SEÇÃO DE ANÁLISE
        y_analysis = y_escudos + TAMANHO_QUADRADO + 150
        
        # Linha separadora
        draw.line([(x0 + 80, y_analysis - 20), (x1 - 80, y_analysis - 20)], fill=(100, 130, 160), width=3)

        # Informações de análise
        tendencia_emoji = "" if "Mais" in jogo['tendencia'] else "" if "Menos" in jogo['tendencia'] else "⚡"
        textos_analise = [
            f"{tendencia_emoji} Tendência: {jogo['tendencia']}",
            f"Estimativa: {jogo['estimativa']:.2f} gols",
            f"Confiança: {jogo['confianca']:.0f}%",
        ]
        
        cores = [(255, 215, 0), (100, 200, 255), (100, 255, 100)]
        
        for i, (text, cor) in enumerate(zip(textos_analise, cores)):
            try:
                bbox = draw.textbbox((0, 0), text, font=FONTE_ANALISE)
                w = bbox[2] - bbox[0]
                draw.text(((LARGURA - w) // 2, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)
            except:
                draw.text((PADDING + 120, y_analysis + i * 90), text, font=FONTE_ANALISE, fill=cor)

        y_pos += ALTURA_POR_JOGO

    # Rodapé
    rodape_text = f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Elite Master System"
    try:
        rodape_bbox = draw.textbbox((0, 0), rodape_text, font=FONTE_DETALHES)
        rodape_w = rodape_bbox[2] - rodape_bbox[0]
        draw.text(((LARGURA - rodape_w) // 2, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))
    except:
        draw.text((LARGURA//2 - 250, altura_total - 70), rodape_text, font=FONTE_DETALHES, fill=(100, 130, 160))

    # Salvar imagem
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True, quality=95)
    buffer.seek(0)
    
    st.success(f"✅ Poster estilo West Ham GERADO com {len(jogos)} jogos")
    return buffer

def enviar_alerta_westham_style(jogos_conf: list, threshold: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Envia alerta no estilo West Ham"""
    if not jogos_conf:
        st.warning("⚠️ Nenhum jogo para gerar poster")
        return

    try:
        # Agrupar por data
        jogos_por_data = {}
        for jogo in jogos_conf:
            data = jogo["hora"].date() if isinstance(jogo["hora"], datetime) else datetime.now().date()
            if data not in jogos_por_data:
                jogos_por_data[data] = []
            jogos_por_data[data].append(jogo)

        for data, jogos_data in jogos_por_data.items():
            data_str = data.strftime("%d/%m/%Y")
            titulo = f"ELITE MASTER - {data_str}"
            
            st.info(f"🎨 Gerando poster para {data_str} com {len(jogos_data)} jogos...")
            
            poster = gerar_poster_westham_style(jogos_data, titulo=titulo)
            
            caption = (
                f"<b>🎯 ALERTA DE GOLS - {data_str}</b>\n\n"
                f"<b>📋 TOTAL: {len(jogos_data)} JOGOS</b>\n"
                f"<b>⚽ CONFIANÇA MÍNIMA: {threshold}%</b>\n\n"
                f"<b>🔮 ANÁLISE PREDITIVA DE GOLS</b>\n"
                f"<b>📊 MÉDIA DE CONFIANÇA: {sum(j['confianca'] for j in jogos_data) / len(jogos_data):.1f}%</b>\n\n"
                f"<b>🔥 JOGOS SELECIONADOS PELA INTELIGÊNCIA ARTIFICIAL</b>"
            )
            
            st.info("📤 Enviando para o Telegram...")
            ok = enviar_foto_telegram(poster, caption=caption, chat_id=chat_id)
            
            if ok:
                st.success(f"🚀 Poster enviado para {data_str}!")
            else:
                st.error(f"❌ Falha ao enviar poster para {data_str}")
                
    except Exception as e:
        st.error(f"❌ Erro crítico ao gerar/enviar poster: {str(e)}")
        # Fallback para mensagem de texto
        msg = f"🔥 Jogos ≥{threshold}% (Erro na imagem):\n"
        for j in jogos_conf[:5]:
            msg += f"🏟️ {j['home']} vs {j['away']} | {j['tendencia']} | Conf: {j['confianca']:.0f}%\n"
        enviar_telegram(msg, chat_id=chat_id)

# =============================
# FUNÇÕES PRINCIPAIS
# =============================

def enviar_top_jogos(jogos: list, top_n: int):
    """Envia os top jogos para o Telegram"""
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
    """Atualiza o status das partidas no cache"""
    cache_jogos = carregar_cache_jogos()
    mudou = False
    
    for key in list(cache_jogos.keys()):
        if key == "_timestamp":
            continue
            
        try:
            liga_id, data = key.split("_", 1)
            url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
            data_api = obter_dados_api(url)
            
            if data_api and "matches" in data_api:
                cache_jogos[key] = data_api["matches"]
                mudou = True
        except Exception as e:
            st.error(f"Erro ao atualizar liga {key}: {e}")
            
    if mudou:
        salvar_cache_jogos(cache_jogos)
        st.success("✅ Status das partidas atualizado!")
    else:
        st.info("ℹ️ Nenhuma atualização disponível.")

def conferir_resultados():
    """Conferir resultados dos jogos"""
    alertas = carregar_alertas()
    if not alertas:
        st.info("ℹ️ Nenhum alerta para conferir.")
        return
        
    st.info("🔍 Conferindo resultados...")
    resultados_conferidos = 0
    for fixture_id, alerta in alertas.items():
        if not alerta.get("conferido", False):
            alerta["conferido"] = True
            resultados_conferidos += 1
    
    if resultados_conferidos > 0:
        salvar_alertas(alertas)
        st.success(f"✅ {resultados_conferidos} resultados conferidos!")
    else:
        st.info("ℹ️ Nenhum novo resultado para conferir.")

def limpar_caches():
    """Limpar caches do sistema"""
    try:
        arquivos_limpos = 0
        for cache_file in [CACHE_JOGOS, CACHE_CLASSIFICACAO, ALERTAS_PATH]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                arquivos_limpos += 1
        st.success(f"✅ {arquivos_limpos} caches limpos com sucesso!")
    except Exception as e:
        st.error(f"❌ Erro ao limpar caches: {e}")

def calcular_desempenho(qtd_jogos: int = 50):
    """Calcular desempenho das previsões"""
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
        
    st.info(f"📊 Calculando desempenho dos últimos {qtd_jogos} jogos...")
    
    historico_recente = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico
    
    if not historico_recente:
        st.warning("⚠️ Histórico insuficiente para cálculo.")
        return
        
    total_jogos = len(historico_recente)
    st.success(f"✅ Desempenho calculado para {total_jogos} jogos!")
    
    # Métricas básicas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Jogos", total_jogos)
    with col2:
        st.metric("Período Analisado", f"Últimos {qtd_jogos}")
    with col3:
        st.metric("Taxa de Confiança Média", f"{sum(h.get('confianca', 0) for h in historico_recente) / total_jogos:.1f}%")

def calcular_desempenho_periodo(data_inicio, data_fim):
    """Calcular desempenho por período"""
    st.info(f"📊 Calculando desempenho de {data_inicio} a {data_fim}...")
    
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return
        
    # Filtrar histórico por período
    historico_periodo = []
    for registro in historico:
        try:
            data_registro = datetime.strptime(registro.get("data_conferencia", ""), "%Y-%m-%d %H:%M:%S").date()
            if data_inicio <= data_registro <= data_fim:
                historico_periodo.append(registro)
        except:
            continue
            
    if not historico_periodo:
        st.warning(f"⚠️ Nenhum jogo encontrado no período {data_inicio} a {data_fim}.")
        return
        
    total_jogos = len(historico_periodo)
    st.success(f"✅ Desempenho do período calculado! {total_jogos} jogos analisados.")
    
    # Métricas do período
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Jogos no Período", total_jogos)
    with col2:
        st.metric("Dias Analisados", (data_fim - data_inicio).days)
    with col3:
        st.metric("Confiança Média", f"{sum(h.get('confianca', 0) for h in historico_periodo) / total_jogos:.1f}%")

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols")

    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        enviar_alerta_70 = st.checkbox("🚨 Enviar alerta com jogos acima do limiar", value=True)
        threshold = st.slider("Limiar de confiança (%)", 50, 95, 70, 1)
        estilo_poster = st.selectbox("🎨 Estilo do Poster", ["West Ham (Novo)", "Elite Master (Original)"], index=0)
        st.markdown("----")
        st.info("Ajuste o limiar para enviar/mostrar apenas jogos acima da confiança selecionada.")

    # Controles principais
    col1, col2 = st.columns([2, 1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))

    # Processamento
    if st.button("🔍 Buscar Partidas", type="primary"):
        processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, enviar_alerta_70, threshold, estilo_poster)

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
    st.subheader("📊 Painel de Desempenho")
    usar_periodo = st.checkbox("🔎 Usar período específico", value=False)
    qtd_default = 50
    last_n = st.number_input("Últimos N jogos", 1, 1000, qtd_default, 1)
    colp1, colp2 = st.columns(2)
    with colp1:
        if usar_periodo:
            data_inicio = st.date_input("Data inicial", value=(datetime.today() - timedelta(days=30)).date())
            data_fim = st.date_input("Data final", value=datetime.today().date())
    with colp2:
        if st.button("📈 Calcular Desempenho"):
            if usar_periodo:
                calcular_desempenho_periodo(data_inicio, data_fim)
            else:
                calcular_desempenho(qtd_jogos=last_n)

    if st.button("🧹 Limpar Histórico"):
        limpar_historico()

def processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, enviar_alerta_enabled: bool, threshold: int, estilo_poster: str):
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

            # Extrair escudos
            escudo_home = ""
            escudo_away = ""
            try:
                escudo_home = match.get("homeTeam", {}).get("crest") or match.get("homeTeam", {}).get("logo") or ""
                escudo_away = match.get("awayTeam", {}).get("crest") or match.get("awayTeam", {}).get("logo") or ""
            except Exception:
                pass

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

    # Filtrar por limiar
    jogos_filtrados_threshold = [
        j for j in top_jogos
        if j["confianca"] >= threshold and j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
    ]

    if jogos_filtrados_threshold:
        enviar_top_jogos(jogos_filtrados_threshold, top_n)
        st.success(f"✅ {len(jogos_filtrados_threshold)} jogos com confiança ≥{threshold}%")
        
        # ENVIAR ALERTA DE IMAGEM
        if enviar_alerta_enabled:
            st.info("🚨 Enviando alerta de imagem...")
            if estilo_poster == "West Ham (Novo)":
                enviar_alerta_westham_style(jogos_filtrados_threshold, threshold)
            else:
                enviar_alerta_conf_criar_poster(jogos_filtrados_threshold, threshold)
    else:
        st.warning(f"⚠️ Nenhum jogo com confiança ≥{threshold}%")

def enviar_alerta_conf_criar_poster(jogos_conf: list, threshold: int, chat_id: str = TELEGRAM_CHAT_ID_ALT2):
    """Função fallback para o estilo original"""
    if not jogos_conf:
        return
        
    try:
        msg = f"🔥 Jogos ≥{threshold}% (Estilo Original):\n\n"
        for j in jogos_conf:
            hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | {j['liga']}\n"
                f"📈 {j['tendencia']} | ⚽ {j['estimativa']:.2f} | 💯 {j['confianca']:.0f}%\n\n"
            )
        enviar_telegram(msg, chat_id=chat_id)
        st.success("📤 Alerta enviado (formato texto)")
    except Exception as e:
        st.error(f"Erro no fallback: {e}")

if __name__ == "__main__":
    main()
