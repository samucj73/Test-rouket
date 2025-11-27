# Futebol_Alertas_OpenLiga_Top3.py
import streamlit as st
from datetime import datetime, timedelta, date
import requests
import os
import json
import math
from PIL import Image, ImageDraw, ImageFont
import io
import base64

# =============================
# Configurações OpenLigaDB + Telegram
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"
ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb"
}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
BASE_URL_TG_PHOTO = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"

ALERTAS_PATH = "alertas.json"
TOP3_PATH = "top3.json"

# =============================
# Persistência
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w", encoding="utf-8") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

def carregar_top3():
    if os.path.exists(TOP3_PATH):
        with open(TOP3_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_top3(lista):
    with open(TOP3_PATH, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")

def enviar_imagem_telegram(image_bytes, caption, chat_id=TELEGRAM_CHAT_ID):
    try:
        files = {'photo': image_bytes}
        data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
        response = requests.post(BASE_URL_TG_PHOTO, files=files, data=data, timeout=15)
        return response.status_code == 200
    except Exception as e:
        st.warning(f"Erro ao enviar imagem Telegram: {e}")
        return False

# =============================
# Geração de Imagens - SISTEMA CORRIGIDO
# =============================
def obter_escudo_time(nome_time, liga_id, temporada):
    """Obtém o escudo do time da API do OpenLigaDB - Versão Corrigida"""
    try:
        # Primeiro, busca todos os times disponíveis para a liga/temporada
        times_url = f"{OPENLIGA_BASE}/getavailableteams/{liga_id}/{temporada}"
        response = requests.get(times_url, timeout=10)
        
        if response.status_code == 200:
            times = response.json()
            
            # Procura pelo time com correspondência exata ou parcial
            time_encontrado = None
            for time in times:
                team_name = time.get('teamName', '')
                
                # Verifica correspondência exata
                if nome_time.lower() == team_name.lower():
                    time_encontrado = time
                    break
                # Verifica correspondência parcial
                elif nome_time.lower() in team_name.lower():
                    time_encontrado = time
                    # Continua procurando por correspondência exata
                
            if time_encontrado:
                icon_url = time_encontrado.get('teamIconUrl')
                if icon_url:
                    # Baixa a imagem
                    img_response = requests.get(icon_url, timeout=10)
                    if img_response.status_code == 200:
                        return Image.open(io.BytesIO(img_response.content)).convert("RGBA")
        
        # Fallback: tenta buscar da temporada atual
        times_url_current = f"{OPENLIGA_BASE}/getavailableteams/{liga_id}/2024"
        response_current = requests.get(times_url_current, timeout=10)
        
        if response_current.status_code == 200:
            times = response_current.json()
            for time in times:
                if nome_time.lower() in time.get('teamName', '').lower():
                    icon_url = time.get('teamIconUrl')
                    if icon_url:
                        img_response = requests.get(icon_url, timeout=10)
                        if img_response.status_code == 200:
                            return Image.open(io.BytesIO(img_response.content)).convert("RGBA")
        
        return None
        
    except Exception as e:
        st.error(f"Erro ao buscar escudo para {nome_time}: {str(e)}")
        return None

def criar_escudo_generico(nome_time):
    """Cria um escudo genérico com as iniciais do time"""
    # Cores baseadas no nome do time (hash simples)
    cores = {
        'red': ['#dc2626', '#ef4444', '#fecaca'],
        'blue': ['#1d4ed8', '#3b82f6', '#dbeafe'],
        'green': ['#16a34a', '#22c55e', '#dcfce7'],
        'yellow': ['#ca8a04', '#eab308', '#fef9c3'],
        'purple': ['#7e22ce', '#a855f7', '#f3e8ff']
    }
    
    # Seleciona cor base baseada no nome
    cor_chave = list(cores.keys())[hash(nome_time) % len(cores)]
    paleta = cores[cor_chave]
    
    # Cria imagem do escudo
    tamanho = 120
    imagem = Image.new('RGBA', (tamanho, tamanho), (0, 0, 0, 0))
    draw = ImageDraw.Draw(imagem)
    
    # Desenha círculo do escudo
    draw.ellipse([0, 0, tamanho, tamanho], fill=paleta[0], outline=paleta[1], width=3)
    
    # Adiciona iniciais
    try:
        fonte = ImageFont.truetype("arial.ttf", 40)
    except:
        fonte = ImageFont.load_default()
    
    iniciais = ''.join([palavra[0].upper() for palavra in nome_time.split()[:2]])
    if not iniciais:
        iniciais = nome_time[:2].upper()
    
    # Centraliza as iniciais
    bbox = draw.textbbox((0, 0), iniciais, font=fonte)
    texto_largura = bbox[2] - bbox[0]
    texto_altura = bbox[3] - bbox[1]
    x = (tamanho - texto_largura) / 2
    y = (tamanho - texto_altura) / 2
    
    draw.text((x, y), iniciais, fill='white', font=fonte)
    
    return imagem

def obter_escudo_time_com_fallback(nome_time, liga_id, temporada):
    """Versão com fallback para escudos genéricos baseados em cores"""
    try:
        # Tenta a busca normal primeiro
        escudo = obter_escudo_time(nome_time, liga_id, temporada)
        if escudo:
            return escudo
        
        # Fallback: cria um escudo genérico com as iniciais do time
        return criar_escudo_generico(nome_time)
        
    except Exception as e:
        st.error(f"Erro no fallback: {e}")
        return criar_escudo_generico(nome_time)

def criar_fonte(tamanho):
    """Tenta carregar fonte, fallback para padrão"""
    try:
        return ImageFont.truetype("arial.ttf", tamanho)
    except:
        try:
            return ImageFont.truetype("arialbd.ttf", tamanho)
        except:
            # Fallback para fonte padrão do PIL (pode ser pequena, mas funciona)
            return ImageFont.load_default()

def criar_imagem_alerta_partida(jogo):
    """Cria imagem de alerta UMA PARTIDA com todas as probabilidades"""
    largura, altura = 1000, 600  # Aumentado para caber mais informações
    
    # Cor de fundo base - azul escuro profissional
    cor_fundo = "#1e3a8a"
    
    # Cria imagem base
    imagem = Image.new('RGB', (largura, altura), color=cor_fundo)
    draw = ImageDraw.Draw(imagem)
    
    # Fontes MAIORES
    fonte_titulo = criar_fonte(42)
    fonte_time = criar_fonte(36)
    fonte_detalhes = criar_fonte(28)
    fonte_probabilidades = criar_fonte(32)
    fonte_confianca = criar_fonte(26)
    
    # Título PRINCIPAL
    titulo = f"⚽ ALERTA DE JOGO - {jogo['competicao']}"
    draw.text((largura//2, 50), titulo, fill='white', font=fonte_titulo, anchor='mm')
    
    # Linha divisória
    draw.line([(50, 100), (largura-50, 100)], fill='white', width=3)
    
    # Times e Escudos - COM FALLBACK
    home_escudo = obter_escudo_time_com_fallback(jogo['home'], jogo['liga_id'], jogo['temporada'])
    away_escudo = obter_escudo_time_com_fallback(jogo['away'], jogo['liga_id'], jogo['temporada'])
    
    # Posicionamento dos escudos (MAIORES)
    escudo_size = 120
    y_pos = 220
    
    # Home (esquerda)
    if home_escudo:
        home_escudo = home_escudo.resize((escudo_size, escudo_size))
        # Cria fundo branco para o escudo
        escudo_bg = Image.new('RGB', (escudo_size, escudo_size), 'white')
        escudo_bg.paste(home_escudo, (0, 0), home_escudo)
        imagem.paste(escudo_bg, (200, y_pos-60))
    
    draw.text((200, y_pos+70), jogo['home'][:20], fill='white', font=fonte_time, anchor='mm')
    
    # VS (maior)
    draw.text((largura//2, y_pos), "VS", fill='white', font=fonte_titulo, anchor='mm')
    
    # Away (direita)
    if away_escudo:
        away_escudo = away_escudo.resize((escudo_size, escudo_size))
        escudo_bg = Image.new('RGB', (escudo_size, escudo_size), 'white')
        escudo_bg.paste(away_escudo, (0, 0), away_escudo)
        imagem.paste(escudo_bg, (largura-200, y_pos-60))
    
    draw.text((largura-200, y_pos+70), jogo['away'][:20], fill='white', font=fonte_time, anchor='mm')
    
    # Informações do jogo
    info_y = 350
    info_lines = [
        f"🏆 {jogo['competicao']}",
        f"⏰ {jogo['hora']} BRT | 📅 {datetime.now().strftime('%d/%m/%Y')}",
        f"📊 Estatística: {jogo['estimativa']:.2f} gols totais esperados"
    ]
    
    for i, line in enumerate(info_lines):
        draw.text((largura//2, info_y + i*40), line, fill='white', font=fonte_detalhes, anchor='mm')
    
    # Probabilidades por faixa - LAYOUT HORIZONTAL
    prob_y = 480
    col_width = largura // 3
    
    # +1.5 Gols
    draw.rectangle([50, prob_y-30, col_width-50, prob_y+80], fill='#1f77b4', outline='white', width=2)
    draw.text((col_width//2, prob_y), "+1.5 GOLS", fill='white', font=fonte_probabilidades, anchor='mm')
    draw.text((col_width//2, prob_y+30), f"{jogo['prob_1_5']:.1f}%", fill='white', font=fonte_probabilidades, anchor='mm')
    draw.text((col_width//2, prob_y+55), f"Conf: {jogo['conf_1_5']:.0f}%", fill='white', font=fonte_confianca, anchor='mm')
    
    # +2.5 Gols  
    draw.rectangle([col_width+50, prob_y-30, 2*col_width-50, prob_y+80], fill='#ff7f0e', outline='white', width=2)
    draw.text((col_width + col_width//2, prob_y), "+2.5 GOLS", fill='white', font=fonte_probabilidades, anchor='mm')
    draw.text((col_width + col_width//2, prob_y+30), f"{jogo['prob_2_5']:.1f}%", fill='white', font=fonte_probabilidades, anchor='mm')
    draw.text((col_width + col_width//2, prob_y+55), f"Conf: {jogo['conf_2_5']:.0f}%", fill='white', font=fonte_confianca, anchor='mm')
    
    # +3.5 Gols
    draw.rectangle([2*col_width+50, prob_y-30, largura-50, prob_y+80], fill='#2ca02c', outline='white', width=2)
    draw.text((2*col_width + col_width//2, prob_y), "+3.5 GOLS", fill='white', font=fonte_probabilidades, anchor='mm')
    draw.text((2*col_width + col_width//2, prob_y+30), f"{jogo['prob_3_5']:.1f}%", fill='white', font=fonte_probabilidades, anchor='mm')
    draw.text((2*col_width + col_width//2, prob_y+55), f"Conf: {jogo['conf_3_5']:.0f}%", fill='white', font=fonte_confianca, anchor='mm')
    
    # Rodapé
    draw.text((largura//2, altura-30), "🔔 ALERTA AUTOMÁTICO - ANÁLISE ESTATÍSTICA", 
              fill='white', font=fonte_confianca, anchor='mm')
    
    return imagem

def criar_imagem_resultado_partida(jogo, resultado_info):
    """Cria imagem de resultado para UMA PARTIDA"""
    largura, altura = 900, 500
    
    # Define cor baseada no resultado
    if "GREEN" in resultado_info.get('resultado', ''):
        cor_fundo = '#15803d'  # Verde mais escuro
    else:
        cor_fundo = '#dc2626'  # Vermelho mais escuro
    
    imagem = Image.new('RGB', (largura, altura), color=cor_fundo)
    draw = ImageDraw.Draw(imagem)
    
    # Fontes MAIORES
    fonte_titulo = criar_fonte(38)
    fonte_time = criar_fonte(32)
    fonte_resultado = criar_fonte(48)
    fonte_detalhes = criar_fonte(26)
    
    # Título
    titulo = f"✅ RESULTADO CONFIRMADO"
    draw.text((largura//2, 40), titulo, fill='white', font=fonte_titulo, anchor='mm')
    
    # Times e escudos - COM FALLBACK
    home_escudo = obter_escudo_time_com_fallback(resultado_info['home'], jogo['liga_id'], jogo['temporada'])
    away_escudo = obter_escudo_time_com_fallback(resultado_info['away'], jogo['liga_id'], jogo['temporada'])
    
    escudo_size = 100
    y_pos = 140
    
    # Home
    if home_escudo:
        home_escudo = home_escudo.resize((escudo_size, escudo_size))
        escudo_bg = Image.new('RGB', (escudo_size, escudo_size), 'white')
        escudo_bg.paste(home_escudo, (0, 0), home_escudo)
        imagem.paste(escudo_bg, (200, y_pos-50))
    draw.text((200, y_pos+60), resultado_info['home'][:15], fill='white', font=fonte_time, anchor='mm')
    
    # Placar (MAIOR)
    score = resultado_info.get('score', '? x ?')
    draw.text((largura//2, y_pos), score, fill='white', font=fonte_resultado, anchor='mm')
    
    # Away
    if away_escudo:
        away_escudo = away_escudo.resize((escudo_size, escudo_size))
        escudo_bg = Image.new('RGB', (escudo_size, escudo_size), 'white')
        escudo_bg.paste(away_escudo, (0, 0), away_escudo)
        imagem.paste(escudo_bg, (largura-200, y_pos-50))
    draw.text((largura-200, y_pos+60), resultado_info['away'][:15], fill='white', font=fonte_time, anchor='mm')
    
    # Resultado da aposta
    resultado_y = 250
    draw.text((largura//2, resultado_y), resultado_info['resultado'], fill='white', font=fonte_titulo, anchor='mm')
    
    # Detalhes da aposta
    detalhes_y = 320
    faixa_aposta = resultado_info['aposta'].replace('+', '')
    total_gols = resultado_info.get('total_gols', '?')
    
    detalhes = [
        f"🎯 Aposta: +{faixa_aposta} gols | Total Marcado: {total_gols} gols",
        f"🏆 {jogo['competicao']}",
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ]
    
    for i, line in enumerate(detalhes):
        draw.text((largura//2, detalhes_y + i*35), line, fill='white', font=fonte_detalhes, anchor='mm')
    
    return imagem

# =============================
# OpenLigaDB helpers
# =============================
def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        r = requests.get(f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}", timeout=15)
        if r.status_code == 200:
            return r.json()
        else:
            return []
    except Exception as e:
        st.warning(f"Erro OpenLigaDB {liga_id}/{temporada}: {e}")
        return []

def calcular_media_gols_times(jogos_hist):
    stats = {}
    for j in jogos_hist:
        home = j.get("team1", {}).get("teamName")
        away = j.get("team2", {}).get("teamName")
        placar = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if not placar:
            continue
        stats.setdefault(home, {"marcados": [], "sofridos": []})
        stats.setdefault(away, {"marcados": [], "sofridos": []})
        stats[home]["marcados"].append(placar[0])
        stats[home]["sofridos"].append(placar[1])
        stats[away]["marcados"].append(placar[1])
        stats[away]["sofridos"].append(placar[0])

    medias = {}
    for time, gols in stats.items():
        media_marcados = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 1.5
        media_sofridos = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 1.2
        medias[time] = {"media_gols_marcados": round(media_marcados, 2), "media_gols_sofridos": round(media_sofridos, 2)}
    return medias

def media_gols_confrontos_diretos_openliga(home, away, jogos_hist, max_jogos=5):
    confrontos = []
    for j in jogos_hist:
        t1 = j.get("team1", {}).get("teamName")
        t2 = j.get("team2", {}).get("teamName")
        if {t1, t2} == {home, away}:
            for r in j.get("matchResults", []):
                if r.get("resultTypeID") == 2:
                    gols = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                    total = gols[0] + gols[1]
                    data_str = j.get("matchDateTimeUTC") or j.get("matchDateTime")
                    confrontos.append((data_str, total))
                    break
    if not confrontos:
        return {"media_gols": 0, "total_jogos": 0}
    confrontos = sorted(confrontos, key=lambda x: x[0] or "", reverse=True)[:max_jogos]
    total_pontos, total_peso = 0, 0
    for idx, (_, total) in enumerate(confrontos):
        peso = max_jogos - idx
        total_pontos += total * peso
        total_peso += peso
    media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
    return {"media_gols": media_ponderada, "total_jogos": len(confrontos)}

def parse_data_openliga_to_datetime(s):
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s2 = s.replace("Z", "+00:00")
        else:
            s2 = s
        return datetime.fromisoformat(s2)
    except Exception:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None

def filtrar_jogos_por_data(jogos_all, data_obj: date):
    out = []
    for j in jogos_all:
        date_str = j.get("matchDateTimeUTC") or j.get("matchDateTime")
        dt = parse_data_openliga_to_datetime(date_str)
        if not dt:
            continue
        if dt.date() == data_obj:
            out.append(j)
    return out

# =============================
# Estatística / Poisson
# =============================
def calcular_estimativa_consolidada(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    media_casa_marcados = media_casa.get("media_gols_marcados", 1.5)
    media_casa_sofridos = media_casa.get("media_gols_sofridos", 1.2)
    media_fora_marcados = media_fora.get("media_gols_marcados", 1.4)
    media_fora_sofridos = media_fora.get("media_gols_sofridos", 1.1)
    media_time_casa = media_casa_marcados + media_fora_sofridos
    media_time_fora = media_fora_marcados + media_casa_sofridos
    estimativa_base = (media_time_casa + media_time_fora) / 2
    h2h_media = media_h2h.get("media_gols", estimativa_base) if media_h2h.get("total_jogos", 0) > 0 else estimativa_base
    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * h2h_media
    return round(estimativa_final, 2)

def poisson_cdf(k, lam):
    s = 0.0
    for i in range(0, k+1):
        s += (lam**i) / math.factorial(i)
    return math.exp(-lam) * s

def prob_over_k(estimativa, threshold): 
    if threshold == 1.5:
        k = 1
    elif threshold == 2.5:
        k = 2
    elif threshold == 3.5:
        k = 3
    else:
        k = int(math.floor(threshold))
    p = 1 - poisson_cdf(k, estimativa)
    return max(0.0, min(1.0, p))

def confidence_from_prob(prob):
    conf = 50 + (prob - 0.5) * 100
    conf = max(30, min(95, conf))
    return round(conf, 0)

# =============================
# Conferência via OpenLigaDB (reconsulta)
# =============================
def conferir_jogo_openliga(fixture_id, liga_id, temporada, tipo_threshold):
    try:
        jogos = obter_jogos_liga_temporada(liga_id, temporada)
        match = None
        for j in jogos:
            if str(j.get("matchID")) == str(fixture_id):
                match = j
                break
        if not match:
            return None
        home = match.get("team1", {}).get("teamName")
        away = match.get("team2", {}).get("teamName")
        final = None
        for r in match.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if final is None:
            return {
                "home": home,
                "away": away,
                "total_gols": None,
                "aposta": f"+{tipo_threshold}",
                "resultado": "Em andamento / sem resultado",
                "score": "? x ?"
            }
        total = final[0] + final[1]
        if tipo_threshold == "1.5":
            green = total >= 2
        elif tipo_threshold == "2.5":
            green = total >= 3
        else:
            green = total >= 4
        return {
            "home": home,
            "away": away,
            "total_gols": total,
            "aposta": f"+{tipo_threshold}",
            "resultado": "🟢 GREEN" if green else "🔴 RED",
            "score": f"{final[0]} x {final[1]}"
        }
    except Exception as e:
        return None

# =============================
# Helpers para selecionar Top3 distintos entre faixas
# =============================
def selecionar_top3_distintos(partidas_info, max_por_faixa=3, prefer_best_fit=True):
    if not partidas_info:
        return [], [], []

    base = list(partidas_info)

    def get_num(d, k):
        v = d.get(k, 0)
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def sort_key(match, prob_key):
        prob = get_num(match, prob_key)
        conf = get_num(match, prob_key.replace("prob", "conf"))
        est = get_num(match, "estimativa")
        return (prob, conf, est)

    selected_ids = set()
    selected_teams = set()

    def safe_team_names(m):
        return str(m.get("home", "")).strip(), str(m.get("away", "")).strip()

    def allocate(prefix, other_prefixes):
        nonlocal base, selected_ids, selected_teams
        prob_key = f"prob_{prefix}"
        conf_key = f"conf_{prefix}"

        candidatos = [m for m in base if str(m.get("fixture_id")) not in selected_ids]

        preferred = []
        if prefer_best_fit:
            for m in candidatos:
                cur = get_num(m, prob_key)
                others = [get_num(m, f"prob_{o}") for o in other_prefixes]
                if cur >= max(others):
                    preferred.append(m)

        preferred_sorted = sorted(preferred, key=lambda x: sort_key(x, prob_key), reverse=True)
        remaining = [m for m in candidatos if m not in preferred_sorted]
        remaining_sorted = sorted(remaining, key=lambda x: sort_key(x, prob_key), reverse=True)

        chosen = []

        def try_add_list(lst, respect_teams=True):
            nonlocal chosen, selected_ids, selected_teams
            for m in lst:
                if len(chosen) >= max_por_faixa:
                    break
                fid = str(m.get("fixture_id"))
                if fid in selected_ids:
                    continue
                home, away = safe_team_names(m)
                if respect_teams and (home in selected_teams or away in selected_teams):
                    continue
                chosen.append(m)
                selected_ids.add(fid)
                selected_teams.add(home)
                selected_teams.add(away)

        try_add_list(preferred_sorted, respect_teams=True)
        if len(chosen) < max_por_faixa:
            try_add_list(remaining_sorted, respect_teams=True)
        if len(chosen) < max_por_faixa:
            try_add_list(preferred_sorted + remaining_sorted, respect_teams=False)

        return chosen

    top_25 = allocate("2_5", other_prefixes=["1_5", "3_5"])
    top_15 = allocate("1_5", other_prefixes=["2_5", "3_5"])
    top_35 = allocate("3_5", other_prefixes=["2_5", "1_5"])

    return top_15, top_25, top_35

# =============================
# UI Streamlit
# =============================
st.set_page_config(page_title="⚽ Alertas Top3 (OpenLigaDB) - Alemanha", layout="wide")
st.title("⚽ Alertas Top3 por Faixa (+1.5 / +2.5 / +3.5) — OpenLigaDB (Alemanha)")

aba = st.tabs(["⚡ Gerar & Enviar Top3 (pré-jogo)", "📊 Jogos Históricos", "🎯 Conferência Top3 (pós-jogo)", "🖼️ Alertas com Imagens", "🔍 Depuração Escudos"])

# ---------- ABA 1: Gerar & Enviar Top3 ----------
with aba[0]:
    st.subheader("🔎 Buscar jogos do dia nas ligas da Alemanha e enviar Top3 por faixa")
    temporada_hist = st.selectbox("📅 Temporada (para médias):", ["2022", "2023", "2024", "2025"], index=2)
    data_selecionada = st.date_input("📅 Data dos jogos:", value=datetime.today().date())
    hoje_str = data_selecionada.strftime("%Y-%m-%d")
    
    enviar_imagens = st.checkbox("📸 Enviar alertas com imagens (UM POR PARTIDA)", value=True)
    st.markdown("**🆕 NOVO: Agora cada partida tem sua própria imagem com TODAS as probabilidades!**")

    st.markdown("**Obs:** as listas são agora *distintas*: um jogo/time selecionado em +1.5 não será repetido em +2.5 ou +3.5 (prioridade: +1.5 → +2.5 → +3.5).")

    if st.button("🔍 Buscar jogos do dia e enviar Top3 (cada faixa uma mensagem)"):
        with st.spinner("Buscando jogos e calculando probabilidades..."):
            jogos_por_liga = {}
            medias_por_liga = {}
            for liga_nome, liga_id in ligas_openliga.items():
                jogos_hist = obter_jogos_liga_temporada(liga_id, temporada_hist)
                jogos_por_liga[liga_id] = jogos_hist
                medias_por_liga[liga_id] = calcular_media_gols_times(jogos_hist)

            jogos_do_dia = []
            for liga_nome, liga_id in ligas_openliga.items():
                jogos_hist = jogos_por_liga.get(liga_id, [])
                filtrados = filtrar_jogos_por_data(jogos_hist, data_selecionada)
                for j in filtrados:
                    j["_liga_id"] = liga_id
                    j["_liga_nome"] = liga_nome
                    j["_temporada"] = temporada_hist
                    jogos_do_dia.append(j)

            if not jogos_do_dia:
                st.info("Nenhum jogo encontrado para essa data nas ligas selecionadas.")
            else:
                partidas_info = []
                for match in jogos_do_dia:
                    home = match.get("team1", {}).get("teamName")
                    away = match.get("team2", {}).get("teamName")
                    hora_dt = parse_data_openliga_to_datetime(match.get("matchDateTimeUTC") or match.get("matchDateTime"))
                    hora_formatada = hora_dt.strftime("%H:%M") if hora_dt else "??:??"
                    liga_id = match.get("_liga_id")
                    jogos_hist_liga = jogos_por_liga.get(liga_id, [])
                    medias_liga = medias_por_liga.get(liga_id, {})

                    media_h2h = media_gols_confrontos_diretos_openliga(home, away, jogos_hist_liga, max_jogos=5)
                    media_casa = medias_liga.get(home, {"media_gols_marcados":1.5, "media_gols_sofridos":1.2})
                    media_fora = medias_liga.get(away, {"media_gols_marcados":1.4, "media_gols_sofridos":1.1})

                    estimativa = calcular_estimativa_consolidada(media_h2h, media_casa, media_fora, peso_h2h=0.3)

                    p15 = prob_over_k(estimativa, 1.5)
                    p25 = prob_over_k(estimativa, 2.5)
                    p35 = prob_over_k(estimativa, 3.5)
                    c15 = confidence_from_prob(p15)
                    c25 = confidence_from_prob(p25)
                    c35 = confidence_from_prob(p35)

                    partidas_info.append({
                        "fixture_id": match.get("matchID"),
                        "home": home, "away": away,
                        "hora": hora_formatada,
                        "competicao": match.get("_liga_nome"),
                        "estimativa": estimativa,
                        "prob_1_5": round(p15*100,1),
                        "prob_2_5": round(p25*100,1),
                        "prob_3_5": round(p35*100,1),
                        "conf_1_5": c15,
                        "conf_2_5": c25,
                        "conf_3_5": c35,
                        "liga_id": liga_id,
                        "temporada": match.get("_temporada")
                    })

                top_15, top_25, top_35 = selecionar_top3_distintos(partidas_info, max_por_faixa=3)

                # --- Envia 3 mensagens separadas (uma por faixa) ---
                if top_15:
                    msg = f"🔔 *TOP 3 +1.5 GOLS — {hoje_str}*\n\n"
                    for idx, j in enumerate(top_15, start=1):
                        msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                f"   • Est: {j['estimativa']:.2f} gols | P(+1.5): *{j['prob_1_5']:.1f}%* | Conf: *{j['conf_1_5']:.0f}%*\n")
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
                    
                    # Envia imagens se habilitado - AGORA UMA IMAGEM POR PARTIDA
                    if enviar_imagens:
                        for j in top_15:
                            imagem = criar_imagem_alerta_partida(j)
                            img_bytes = io.BytesIO()
                            imagem.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            caption = f"⚡ *ALERTA +1.5 GOLS*\n*{j['home']} x {j['away']}*\n⏰ {j['hora']} BRT | P(+1.5): {j['prob_1_5']:.1f}%"
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID)
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID_ALT2)

                if top_25:
                    msg = f"🔔 *TOP 3 +2.5 GOLS — {hoje_str}*\n\n"
                    for idx, j in enumerate(top_25, start=1):
                        msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                f"   • Est: {j['estimativa']:.2f} gols | P(+2.5): *{j['prob_2_5']:.1f}%* | Conf: *{j['conf_2_5']:.0f}%*\n")
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
                    
                    if enviar_imagens:
                        for j in top_25:
                            imagem = criar_imagem_alerta_partida(j)
                            img_bytes = io.BytesIO()
                            imagem.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            caption = f"⚡ *ALERTA +2.5 GOLS*\n*{j['home']} x {j['away']}*\n⏰ {j['hora']} BRT | P(+2.5): {j['prob_2_5']:.1f}%"
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID)
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID_ALT2)

                if top_35:
                    msg = f"🔔 *TOP 3 +3.5 GOLS — {hoje_str}*\n\n"
                    for idx, j in enumerate(top_35, start=1):
                        msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                f"   • Est: {j['estimativa']:.2f} gols | P(+3.5): *{j['prob_3_5']:.1f}%* | Conf: *{j['conf_3_5']:.0f}%*\n")
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
                    
                    if enviar_imagens:
                        for j in top_35:
                            imagem = criar_imagem_alerta_partida(j)
                            img_bytes = io.BytesIO()
                            imagem.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            caption = f"⚡ *ALERTA +3.5 GOLS*\n*{j['home']} x {j['away']}*\n⏰ {j['hora']} BRT | P(+3.5): {j['prob_3_5']:.1f}%"
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID)
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID_ALT2)

                top3_list = carregar_top3()
                novo_top = {
                    "data_envio": hoje_str,
                    "hora_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "temporada": temporada_hist,
                    "top_1_5": top_15,
                    "top_2_5": top_25,
                    "top_3_5": top_35
                }
                top3_list.append(novo_top)
                salvar_top3(top3_list)

                st.success("✅ Top3 gerados e enviados (uma mensagem por faixa).")
                st.write("### Top 3 +1.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P(+1.5)": f"{t['prob_1_5']}%", "Conf": f"{t['conf_1_5']}%"} for t in top_15])
                st.write("### Top 3 +2.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P(+2.5)": f"{t['prob_2_5']}%", "Conf": f"{t['conf_2_5']}%"} for t in top_25])
                st.write("### Top 3 +3.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P(+3.5)": f"{t['prob_3_5']}%", "Conf": f"{t['conf_3_5']}%"} for t in top_35])

# ---------- ABA 2: Jogos históricos ----------
with aba[1]:
    st.subheader("📊 Jogos de Temporadas Passadas (OpenLigaDB) — Ligas da Alemanha")
    temporada_hist2 = st.selectbox("📅 Temporada histórica:", ["2022", "2023", "2024", "2025"], index=2, key="hist2")
    liga_nome_hist = st.selectbox("🏆 Escolha a Liga:", list(ligas_openliga.keys()), key="hist_liga")
    liga_id_hist = ligas_openliga[liga_nome_hist]

    if st.button("🔍 Buscar jogos da temporada", key="btn_hist"):
        with st.spinner("Buscando jogos..."):
            jogos_hist = obter_jogos_liga_temporada(liga_id_hist, temporada_hist2)
            if not jogos_hist:
                st.info("Nenhum jogo encontrado para essa temporada/liga.")
            else:
                st.success(f"{len(jogos_hist)} jogos encontrados na {liga_nome_hist} ({temporada_hist2})")
                for j in jogos_hist[:50]:
                    home = j.get("team1", {}).get("teamName")
                    away = j.get("team2", {}).get("teamName")
                    placar = "-"
                    for r in j.get("matchResults", []):
                        if r.get("resultTypeID") == 2:
                            placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                            break
                    data = j.get("matchDateTimeUTC") or j.get("matchDateTime") or "Desconhecida"
                    st.write(f"🏟️ {home} vs {away} | 📅 {data} | ⚽ Placar: {placar}")

# ---------- ABA 3: Conferência Top 3 ----------
with aba[2]:
    st.subheader("🎯 Conferência dos Top 3 enviados — enviar conferência por faixa (cada faixa uma mensagem)")
    top3_salvos = carregar_top3()
    enviar_imagens_resultados = st.checkbox("📸 Enviar imagens de resultados", value=True, key="resultados_img")

    if not top3_salvos:
        st.info("Nenhum Top 3 registrado ainda. Gere e envie um Top 3 na aba 'Gerar & Enviar Top3'.")
    else:
        st.write(f"✅ Total de envios registrados: {len(top3_salvos)}")
        options = [f"{idx+1} - {t['data_envio']} ({t['hora_envio']})" for idx, t in enumerate(top3_salvos)]
        seletor = st.selectbox("Selecione o lote Top3 para conferir:", options, index=len(options)-1)
        idx_selecionado = options.index(seletor)
        lote = top3_salvos[idx_selecionado]
        st.markdown(f"### Lote selecionado — Envio: **{lote['data_envio']}** às **{lote['hora_envio']}**")
        st.markdown("---")

        if st.button("🔄 Rechecar resultados agora e enviar conferência (uma mensagem por faixa)"):
            with st.spinner("Conferindo resultados e enviando mensagens..."):
                # função auxiliar para processar uma lista e retornar mensagem e resumo
                def processar_lista_e_mandar(lista_top, threshold_label):
                    detalhes_local = []
                    greens = reds = 0
                    lines_for_msg = []
                    for j in lista_top:
                        fixture_id = j.get("fixture_id")
                        liga_id = j.get("liga_id")
                        temporada = j.get("temporada")
                        info = conferir_jogo_openliga(fixture_id, liga_id, temporada, threshold_label)
                        if not info:
                            detalhes_local.append({
                                "home": j.get("home"),
                                "away": j.get("away"),
                                "aposta": f"+{threshold_label}",
                                "status": "Não encontrado / sem resultado"
                            })
                            lines_for_msg.append(f"🏟️ {j.get('home')} x {j.get('away')} — _sem resultado disponível_")
                            continue
                        if info.get("total_gols") is None:
                            lines_for_msg.append(f"🏟️ {info['home']} {info.get('score','')} — _Em andamento / sem resultado_")
                            detalhes_local.append({
                                "home": info["home"],
                                "away": info["away"],
                                "aposta": info["aposta"],
                                "status": "Em andamento"
                            })
                            continue
                        resultado_text = info["resultado"]
                        score = info.get("score", "")
                        lines_for_msg.append(f"🏟️ {info['home']} {score} {info['away']} — {info['aposta']} → {resultado_text}")
                        detalhes_local.append({
                            "home": info["home"],
                            "away": info["away"],
                            "aposta": info["aposta"],
                            "total_gols": info["total_gols"],
                            "resultado": resultado_text,
                            "score": score
                        })
                        
                        # Envia imagem de resultado se habilitado - AGORA UMA IMAGEM POR PARTIDA
                        if enviar_imagens_resultados and info.get("total_gols") is not None:
                            imagem = criar_imagem_resultado_partida(j, info)
                            img_bytes = io.BytesIO()
                            imagem.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            caption = f"✅ *RESULTADO +{threshold_label}*\n*{info['home']} {score} {info['away']}*\n{resultado_text}"
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID)
                            enviar_imagem_telegram(img_bytes, caption, TELEGRAM_CHAT_ID_ALT2)
                        
                        if "GREEN" in resultado_text:
                            greens += 1
                        else:
                            reds += 1
                    # construir e enviar mensagem separada por faixa
                    header = f"✅ RESULTADOS - CONFERÊNCIA +{threshold_label}\n(Lote: {lote['data_envio']})\n\n"
                    if lines_for_msg:
                        body = "\n".join(lines_for_msg)
                    else:
                        body = "_Nenhum jogo para conferir nesta faixa no lote selecionado._"
                    resumo = f"\n\nResumo: 🟢 {greens} GREEN | 🔴 {reds} RED"
                    msg = header + body + resumo
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
                    return detalhes_local, {"greens": greens, "reds": reds}

                detalhes_1_5, resumo_1_5 = processar_lista_e_mandar(lote.get("top_1_5", []), "1.5")
                detalhes_2_5, resumo_2_5 = processar_lista_e_mandar(lote.get("top_2_5", []), "2.5")
                detalhes_3_5, resumo_3_5 = processar_lista_e_mandar(lote.get("top_3_5", []), "3.5")

                st.success("✅ Mensagens de conferência enviadas (uma por faixa).")
                st.markdown("**Resumo das conferências enviadas:**")
                st.write(f"+1.5 → 🟢 {resumo_1_5['greens']} | 🔴 {resumo_1_5['reds']}")
                st.write(f"+2.5 → 🟢 {resumo_2_5['greens']} | 🔴 {resumo_2_5['reds']}")
                st.write(f"+3.5 → 🟢 {resumo_3_5['greens']} | 🔴 {resumo_3_5['reds']}")

        # também manter a opção de simplesmente re-checar (sem enviar telegram)
        if st.button("🔎 Rechecar resultados aqui (sem enviar Telegram)"):
            with st.spinner("Conferindo resultados localmente..."):
                for label, lista in [("1.5", lote.get("top_1_5", [])), ("2.5", lote.get("top_2_5", [])), ("3.5", lote.get("top_3_5", []))]:
                    st.write(f"### Conferência +{label}")
                    for j in lista:
                        info = conferir_jogo_openliga(j.get("fixture_id"), j.get("liga_id"), j.get("temporada"), label)
                        if not info:
                            st.warning(f"🏟️ {j.get('home')} x {j.get('away')} — Resultado não encontrado / sem atualização")
                            continue
                        if info.get("total_gols") is None:
                            st.info(f"🏟️ {info['home']} — Em andamento / sem resultado")
                            continue
                        if "GREEN" in info["resultado"]:
                            st.success(f"🏟️ {info['home']} {info.get('score','')} {info['away']} → {info['resultado']}")
                        else:
                            st.error(f"🏟️ {info['home']} {info.get('score','')} {info['away']} → {info['resultado']}")

        # opção de exportar lote
        if st.button("📥 Exportar lote selecionado (.json)"):
            nome_arquivo = f"relatorio_top3_{lote['data_envio'].replace('/','-')}_{lote['hora_envio'].replace(':','-').replace(' ','_')}.json"
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(lote, f, ensure_ascii=False, indent=2)
            st.success(f"Lote exportado: {nome_arquivo}")

# ---------- ABA 4: Alertas com Imagens ----------
with aba[3]:
    st.subheader("🖼️ Visualizar Alertas com Imagens - NOVO FORMATO")
    st.markdown("**🆕 AGORA: Cada partida tem sua própria imagem com TODAS as probabilidades!**")
    
    # Criar exemplo de jogo para demonstração
    exemplo_jogo = {
        "home": "Bayern Munich",
        "away": "Borussia Dortmund", 
        "competicao": "Bundesliga (Alemanha)",
        "hora": "17:30",
        "estimativa": 3.2,
        "prob_1_5": 85.4,
        "prob_2_5": 67.8, 
        "prob_3_5": 45.2,
        "conf_1_5": 78,
        "conf_2_5": 65,
        "conf_3_5": 52,
        "liga_id": "bl1",
        "temporada": "2024"
    }
    
    st.write("### 📸 Exemplo de Alerta por Partida (NOVO):")
    
    # Criar e mostrar imagem de exemplo
    imagem_exemplo = criar_imagem_alerta_partida(exemplo_jogo)
    st.image(imagem_exemplo, use_column_width=True, caption="🎯 ALERTA POR PARTIDA - Todas as probabilidades em uma imagem")
    
    st.write("### 🎨 Características do Novo Formato:")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        **📊 Todas as Faixas**
        - +1.5 Gols
        - +2.5 Gols  
        - +3.5 Gols
        """)
        
    with col2:
        st.success("""
        **👥 Escudos dos Times**
        - Busca automática na API
        - Fallback robusto
        - Visual profissional
        """)
        
    with col3:
        st.warning("""
        **📈 Informações Completas**
        - Probabilidades
        - Confiança
        - Estatísticas
        - Horário
        """)
    
    # Exemplo de resultado
    st.write("### ✅ Exemplo de Resultado por Partida:")
    
    resultado_exemplo = {
        "home": "Bayern Munich",
        "away": "Borussia Dortmund",
        "resultado": "🟢 GREEN", 
        "score": "3 x 2",
        "total_gols": 5,
        "aposta": "+2.5"
    }
    
    imagem_resultado = criar_imagem_resultado_partida(exemplo_jogo, resultado_exemplo)
    st.image(imagem_resultado, use_column_width=True, caption="✅ RESULTADO POR PARTIDA - Confirmação visual do resultado")

# ---------- ABA 5: Depuração de Escudos ----------
with aba[4]:
    st.subheader("🔍 Depuração - Busca de Escudos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        time_teste = st.text_input("Time para teste:", "Bayern Munich")
        liga_teste = st.selectbox("Liga para teste:", list(ligas_openliga.keys()))
        liga_id_teste = ligas_openliga[liga_teste]
        temporada_teste = st.selectbox("Temporada:", ["2022", "2023", "2024", "2025"], index=2)
    
    with col2:
        st.write("### 🎯 Teste Rápido")
        if st.button("🔍 Testar Busca de Escudo"):
            with st.spinner("Buscando escudo..."):
                escudo = obter_escudo_time(time_teste, liga_id_teste, temporada_teste)
                
                if escudo:
                    st.success("✅ Escudo encontrado via API!")
                    st.image(escudo, caption=f"Escudo do {time_teste}", width=150)
                    
                    # Mostra informações da imagem
                    st.write(f"**Formato:** {escudo.format}")
                    st.write(f"**Tamanho:** {escudo.size}")
                    st.write(f"**Modo:** {escudo.mode}")
                else:
                    st.error("❌ Escudo não encontrado na API")
                    st.info("🔄 Criando escudo genérico...")
                    escudo_generico = criar_escudo_generico(time_teste)
                    st.image(escudo_generico, caption=f"Escudo Genérico - {time_teste}", width=150)
        
        if st.button("🔄 Testar com Fallback"):
            escudo_fallback = obter_escudo_time_com_fallback(time_teste, liga_id_teste, temporada_teste)
            st.image(escudo_fallback, caption=f"Escudo com Fallback - {time_teste}", width=150)
            st.success("✅ Escudo com fallback criado!")

    # Testa a API diretamente
    st.markdown("---")
    st.subheader("📡 Teste Direto da API OpenLigaDB")
    
    if st.button("🌐 Consultar API de Times"):
        try:
            times_url = f"{OPENLIGA_BASE}/getavailableteams/{liga_id_teste}/{temporada_teste}"
            st.write(f"**URL da API:** `{times_url}`")
            
            response = requests.get(times_url, timeout=10)
            
            if response.status_code == 200:
                times = response.json()
                st.success(f"✅ API respondeu! Total de times: {len(times)}")
                
                # Filtra times que correspondem ao nome pesquisado
                times_correspondentes = [t for t in times if time_teste.lower() in t.get('teamName', '').lower()]
                
                if times_correspondentes:
                    st.write(f"**Times correspondentes a '{time_teste}':**")
                    for time in times_correspondentes:
                        st.write(f"- **{time.get('teamName')}**")
                        st.write(f"  - ID: {time.get('teamId')}")
                        st.write(f"  - Escudo: {time.get('teamIconUrl', 'N/A')}")
                        if time.get('teamIconUrl'):
                            st.image(time.get('teamIconUrl'), width=50, caption="Escudo")
                else:
                    st.warning(f"❌ Nenhum time encontrado com '{time_teste}'")
                
                # Lista todos os times disponíveis (primeiros 10)
                st.write("**Todos os times disponíveis (primeiros 10):**")
                for time in times[:10]:
                    st.write(f"- {time.get('teamName')}")
                    
            else:
                st.error(f"❌ Erro na API: {response.status_code}")
                
        except Exception as e:
            st.error(f"💥 Erro no teste da API: {e}")

# Fim do arquivo
