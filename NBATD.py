# app_nba_elite_master.py
import streamlit as st
from datetime import datetime, timedelta, date
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import time
from PIL import Image, ImageDraw, ImageFont
import base64

# =============================
# CONFIGURAÇÕES
# =============================
BALLDONTLIE_API_KEY = "7da89f74-317a-45a0-88f9-57cccfef5a00"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"

BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas_nba.json"
CACHE_GAMES = "cache_games_nba.json"
CACHE_TEAMS = "cache_teams_nba.json"
CACHE_STATS = "cache_stats_nba.json"
STATS_PATH = "estatisticas_nba.json"
CACHE_TIMEOUT = 86400  # 24h

HEADERS_BDL = {"Authorization": BALLDONTLIE_API_KEY}

# Rate limiting
REQUEST_TIMEOUT = 10
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 1.2

# =============================
# DICIONÁRIO DE ESCUDOS NBA
# =============================
NBA_LOGOS = {
    "Atlanta Hawks": "https://cdn.nba.com/logos/nba/1610612737/primary/L/logo.svg",
    "Boston Celtics": "https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg",
    "Brooklyn Nets": "https://cdn.nba.com/logos/nba/1610612751/primary/L/logo.svg",
    "Charlotte Hornets": "https://cdn.nba.com/logos/nba/1610612766/primary/L/logo.svg",
    "Chicago Bulls": "https://cdn.nba.com/logos/nba/1610612741/primary/L/logo.svg",
    "Cleveland Cavaliers": "https://cdn.nba.com/logos/nba/1610612739/primary/L/logo.svg",
    "Dallas Mavericks": "https://cdn.nba.com/logos/nba/1610612742/primary/L/logo.svg",
    "Denver Nuggets": "https://cdn.nba.com/logos/nba/1610612743/primary/L/logo.svg",
    "Detroit Pistons": "https://cdn.nba.com/logos/nba/1610612765/primary/L/logo.svg",
    "Golden State Warriors": "https://cdn.nba.com/logos/nba/1610612744/primary/L/logo.svg",
    "Houston Rockets": "https://cdn.nba.com/logos/nba/1610612745/primary/L/logo.svg",
    "Indiana Pacers": "https://cdn.nba.com/logos/nba/1610612754/primary/L/logo.svg",
    "Los Angeles Clippers": "https://cdn.nba.com/logos/nba/1610612746/primary/L/logo.svg",
    "Los Angeles Lakers": "https://cdn.nba.com/logos/nba/1610612747/primary/L/logo.svg",
    "Memphis Grizzlies": "https://cdn.nba.com/logos/nba/1610612763/primary/L/logo.svg",
    "Miami Heat": "https://cdn.nba.com/logos/nba/1610612748/primary/L/logo.svg",
    "Milwaukee Bucks": "https://cdn.nba.com/logos/nba/1610612749/primary/L/logo.svg",
    "Minnesota Timberwolves": "https://cdn.nba.com/logos/nba/1610612750/primary/L/logo.svg",
    "New Orleans Pelicans": "https://cdn.nba.com/logos/nba/1610612740/primary/L/logo.svg",
    "New York Knicks": "https://cdn.nba.com/logos/nba/1610612752/primary/L/logo.svg",
    "Oklahoma City Thunder": "https://cdn.nba.com/logos/nba/1610612760/primary/L/logo.svg",
    "Orlando Magic": "https://cdn.nba.com/logos/nba/1610612753/primary/L/logo.svg",
    "Philadelphia 76ers": "https://cdn.nba.com/logos/nba/1610612755/primary/L/logo.svg",
    "Phoenix Suns": "https://cdn.nba.com/logos/nba/1610612756/primary/L/logo.svg",
    "Portland Trail Blazers": "https://cdn.nba.com/logos/nba/1610612757/primary/L/logo.svg",
    "Sacramento Kings": "https://cdn.nba.com/logos/nba/1610612758/primary/L/logo.svg",
    "San Antonio Spurs": "https://cdn.nba.com/logos/nba/1610612759/primary/L/logo.svg",
    "Toronto Raptors": "https://cdn.nba.com/logos/nba/1610612761/primary/L/logo.svg",
    "Utah Jazz": "https://cdn.nba.com/logos/nba/1610612762/primary/L/logo.svg",
    "Washington Wizards": "https://cdn.nba.com/logos/nba/1610612764/primary/L/logo.svg"
}

# =============================
# FUNÇÕES DE IMAGEM E ESCUDOS
# =============================
def baixar_escudo_time(url: str, tamanho: tuple = (80, 80)) -> Image.Image:
    """Baixa e redimensiona o escudo do time"""
    try:
        resposta = requests.get(url, timeout=10)
        if resposta.status_code == 200:
            # Para SVG, vamos criar uma imagem simples
            if url.endswith('.svg'):
                # Cria uma imagem circular laranja (cor da NBA)
                img = Image.new('RGBA', tamanho, (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse([0, 0, tamanho[0], tamanho[1]], fill=(255, 125, 0, 255))
                return img
            else:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(resposta.content))
                return img.resize(tamanho, Image.Resampling.LANCZOS)
    except Exception:
        # Fallback: cria escudo padrão da NBA
        img = Image.new('RGBA', tamanho, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([0, 0, tamanho[0], tamanho[1]], fill=(255, 125, 0, 255))
        return img

def criar_imagem_alerta_nba(home_team: str, away_team: str, predictions: dict, data_hora: str = "") -> Image.Image:
    """Cria imagem de alerta estilo NBA com escudos dos times"""
    # Dimensões da imagem
    largura, altura = 800, 400
    img = Image.new('RGB', (largura, altura), color=(13, 17, 23))  # Fundo escuro
    draw = ImageDraw.Draw(img)
    
    try:
        # Tenta carregar uma fonte (fallback para padrão se não disponível)
        try:
            font_large = ImageFont.truetype("arial.ttf", 28)
            font_medium = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
            font_bold = ImageFont.truetype("arialbd.ttf", 22)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_bold = ImageFont.load_default()
        
        # Cabeçalho - NBA
        draw.rectangle([0, 0, largura, 60], fill=(255, 125, 0))  # Laranja NBA
        draw.text((largura//2, 30), "🏀 NBA ELITE MASTER", fill=(255, 255, 255), 
                 font=font_bold, anchor="mm")
        
        if data_hora:
            draw.text((largura//2, 55), data_hora, fill=(255, 255, 255), 
                     font=font_small, anchor="mm")
        
        # Posicionamento dos times
        centro_x = largura // 2
        pos_y = 120
        
        # Busca escudos
        home_logo_url = NBA_LOGOS.get(home_team, "")
        away_logo_url = NBA_LOGOS.get(away_team, "")
        
        home_logo = baixar_escudo_time(home_logo_url)
        away_logo = baixar_escudo_time(away_logo_url)
        
        # Posiciona escudos e nomes
        espacamento = 200
        
        # Time visitante (esquerda)
        if away_logo:
            img.paste(away_logo, (centro_x - espacamento - 40, pos_y - 40), away_logo)
        draw.text((centro_x - espacamento, pos_y + 50), away_team, 
                 fill=(255, 255, 255), font=font_medium, anchor="mm")
        
        # VS no centro
        draw.text((centro_x, pos_y), "VS", fill=(255, 125, 0), 
                 font=font_large, anchor="mm")
        
        # Time da casa (direita)
        if home_logo:
            img.paste(home_logo, (centro_x + espacamento - 40, pos_y - 40), home_logo)
        draw.text((centro_x + espacamento, pos_y + 50), home_team, 
                 fill=(255, 255, 255), font=font_medium, anchor="mm")
        
        # Previsões
        pos_y_previsoes = 220
        
        # Total de pontos
        total_pred = predictions.get("total", {})
        if total_pred:
            tendencia = total_pred.get("tendencia", "")
            estimativa = total_pred.get("estimativa", 0)
            confianca = total_pred.get("confianca", 0)
            
            texto_total = f"📊 TOTAL: {tendencia}"
            texto_estimativa = f"Estimativa: {estimativa:.1f} | Confiança: {confianca:.0f}%"
            
            draw.text((centro_x, pos_y_previsoes), texto_total, 
                     fill=(0, 255, 0), font=font_medium, anchor="mm")
            draw.text((centro_x, pos_y_previsoes + 25), texto_estimativa, 
                     fill=(200, 200, 200), font=font_small, anchor="mm")
        
        # Vencedor
        vencedor_pred = predictions.get("vencedor", {})
        if vencedor_pred:
            vencedor = vencedor_pred.get("vencedor", "")
            confianca_venc = vencedor_pred.get("confianca", 0)
            detalhe = vencedor_pred.get("detalhe", "")
            
            texto_vencedor = f"🎯 VENCEDOR: {vencedor}"
            texto_confianca = f"Confiança: {confianca_venc:.0f}% | {detalhe}"
            
            draw.text((centro_x, pos_y_previsoes + 60), texto_vencedor, 
                     fill=(255, 215, 0), font=font_medium, anchor="mm")
            draw.text((centro_x, pos_y_previsoes + 85), texto_confianca, 
                     fill=(200, 200, 200), font=font_small, anchor="mm")
        
        # Rodapé
        draw.text((centro_x, altura - 20), "ELITE MASTER - Dados Reais 2024-2025", 
                 fill=(150, 150, 150), font=font_small, anchor="mm")
        
    except Exception as e:
        # Fallback em caso de erro
        draw.text((largura//2, altura//2), f"Erro ao gerar imagem: {e}", 
                 fill=(255, 0, 0), font=font_medium, anchor="mm")
    
    return img

def imagem_para_base64(imagem: Image.Image) -> str:
    """Converte imagem PIL para base64"""
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()

def enviar_imagem_telegram(imagem: Image.Image, legenda: str = "", chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Envia imagem para o Telegram"""
    try:
        # Converte imagem para base64 temporariamente
        buffer = io.BytesIO()
        imagem.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Envia via API do Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        files = {'photo': buffer}
        data = {'chat_id': chat_id, 'caption': legenda, 'parse_mode': 'HTML'}
        
        resposta = requests.post(url, files=files, data=data, timeout=30)
        return resposta.status_code == 200
        
    except Exception as e:
        st.error(f"Erro ao enviar imagem: {e}")
        return False

# =============================
# FUNÇÃO ATUALIZADA DE ENVIO DE ALERTAS COM IMAGEM
# =============================
def formatar_e_enviar_alerta_completo(game: dict, predictions: dict, enviar_imagem: bool = True) -> bool:
    """Formata e envia alerta completo com imagem e texto"""
    try:
        home_team = game.get("home_team", {}).get("full_name", "Casa")
        away_team = game.get("visitor_team", {}).get("full_name", "Visitante")
        
        # Formata data e hora
        data_hora = game.get("datetime") or game.get("date") or ""
        data_str, hora_str = "-", "-"
        if data_hora:
            try:
                dt = datetime.fromisoformat(data_hora.replace("Z", "+00:00")) - timedelta(hours=3)
                data_str = dt.strftime("%d/%m/%Y")
                hora_str = dt.strftime("%H:%M")
            except:
                data_str, hora_str = "-", "-"
        
        data_hora_formatada = f"{data_str} {hora_str} (BRT)"
        
        # Cria imagem do alerta
        if enviar_imagem:
            imagem_alerta = criar_imagem_alerta_nba(home_team, away_team, predictions, data_hora_formatada)
        
        # Mensagem textual para Telegram
        mensagem_texto = f"🏀 <b>Alerta NBA - {data_hora_formatada}</b>\n"
        mensagem_texto += f"🏟️ {away_team} @ {home_team}\n"
        mensagem_texto += f"📌 Status: {game.get('status', 'SCHEDULED')}\n\n"
        
        total_pred = predictions.get("total", {})
        if total_pred:
            mensagem_texto += f"📈 <b>Total Pontos</b>: {total_pred.get('tendencia', 'N/A')}\n"
            mensagem_texto += f"   📊 Estimativa: <b>{total_pred.get('estimativa', 0):.1f}</b> | Confiança: {total_pred.get('confianca', 0):.0f}%\n\n"
        
        vencedor_pred = predictions.get("vencedor", {})
        if vencedor_pred:
            mensagem_texto += f"🎯 <b>Vencedor</b>: {vencedor_pred.get('vencedor', 'N/A')}\n"
            mensagem_texto += f"   💪 Confiança: {vencedor_pred.get('confianca', 0):.0f}% | {vencedor_pred.get('detalhe', '')}\n"
        
        mensagem_texto += "\n🏆 <b>Elite Master</b> - Análise com Dados Reais 2024-2025"
        
        # Envia para Telegram
        sucesso = False
        
        if enviar_imagem:
            # Tenta enviar com imagem
            sucesso = enviar_imagem_telegram(imagem_alerta, mensagem_texto)
        
        if not sucesso or not enviar_imagem:
            # Fallback: envia apenas texto
            sucesso = enviar_telegram(mensagem_texto)
        
        return sucesso
        
    except Exception as e:
        st.error(f"Erro ao enviar alerta completo: {e}")
        # Fallback para envio simples
        return enviar_telegram(formatar_msg_alerta(game, predictions))

# =============================
# FUNÇÃO ATUALIZADA DE VERIFICAÇÃO E ENVIO
# =============================
def verificar_e_enviar_alerta(game: dict, predictions: dict, send_to_telegram: bool = False, com_imagem: bool = True):
    """Versão atualizada com suporte a imagens"""
    alertas = carregar_alertas()
    fid = str(game.get("id"))
    
    if fid not in alertas:
        alertas[fid] = {
            "game_id": fid,
            "game_data": game,
            "predictions": predictions,
            "timestamp": datetime.now().isoformat(),
            "enviado_telegram": send_to_telegram,
            "enviado_com_imagem": com_imagem,  # NOVO: controle de imagem
            "conferido": False,
            "alerta_resultado_enviado": False
        }
        salvar_alertas(alertas)
        
        # Se marcado para enviar ao Telegram, envia
        if send_to_telegram:
            sucesso = formatar_e_enviar_alerta_completo(game, predictions, com_imagem)
            
            if sucesso:
                alertas[fid]["enviado_telegram"] = True
                alertas[fid]["enviado_com_imagem"] = com_imagem
                salvar_alertas(alertas)
                return True
            else:
                return False
        return True
    return False

# =============================
# FUNÇÃO PARA VISUALIZAR IMAGEM DE ALERTA
# =============================
def visualizar_imagem_alerta(game: dict, predictions: dict):
    """Gera e exibe a imagem de alerta no Streamlit"""
    home_team = game.get("home_team", {}).get("full_name", "Casa")
    away_team = game.get("visitor_team", {}).get("full_name", "Visitante")
    
    # Formata data e hora
    data_hora = game.get("datetime") or game.get("date") or ""
    data_str, hora_str = "-", "-"
    if data_hora:
        try:
            dt = datetime.fromisoformat(data_hora.replace("Z", "+00:00")) - timedelta(hours=3)
            data_str = dt.strftime("%d/%m/%Y")
            hora_str = dt.strftime("%H:%M")
        except:
            data_str, hora_str = "-", "-"
    
    data_hora_formatada = f"{data_str} {hora_str} (BRT)"
    
    # Gera imagem
    imagem = criar_imagem_alerta_nba(home_team, away_team, predictions, data_hora_formatada)
    
    # Converte para exibir no Streamlit
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Exibe imagem
    st.image(buffer, caption=f"Preview: {away_team} @ {home_team}", use_column_width=True)
    
    # Botão para baixar imagem
    st.download_button(
        label="📥 Baixar Imagem do Alerta",
        data=buffer.getvalue(),
        file_name=f"alerta_nba_{home_team.replace(' ', '_')}_{away_team.replace(' ', '_')}.png",
        mime="image/png"
    )

# =============================
# ATUALIZAR A INTERFACE STREAMLIT
# =============================
def exibir_aba_analise():
    st.header("🎯 Análise com Dados Reais 2024-2025")
    
    with st.sidebar:
        st.subheader("Controles de Análise")
        top_n = st.slider("Número de jogos para analisar", 1, 15, 5)
        janela = st.slider("Jogos recentes para análise", 2, 20, 15)
        enviar_auto = st.checkbox("Enviar alertas automaticamente para Telegram", value=True)
        com_imagem = st.checkbox("Enviar alertas com imagem", value=True)  # NOVO: opção de imagem
        
        st.markdown("---")
        st.subheader("Gerenciamento")
        if st.button("🧹 Limpar Cache", type="secondary"):
            for f in [CACHE_GAMES, CACHE_STATS, ALERTAS_PATH]:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        st.success(f"🗑️ {f} removido")
                except:
                    pass
            st.rerun()

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        data_sel = st.date_input("Selecione a data:", value=date.today())
    with col2:
        st.write("")
        st.write("")
        if st.button("🚀 ANALISAR COM DADOS 2024-2025", type="primary", use_container_width=True):
            analisar_jogos_com_dados_2025(data_sel, top_n, janela, enviar_auto, com_imagem)
    with col3:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar Dados", type="secondary"):
            st.rerun()

def analisar_jogos_com_dados_2025(data_sel: date, top_n: int, janela: int, enviar_auto: bool, com_imagem: bool):
    data_str = data_sel.strftime("%Y-%m-%d")
    
    progress_placeholder = st.empty()
    results_placeholder = st.empty()
    
    with progress_placeholder:
        st.info(f"🔍 Buscando dados reais para {data_sel.strftime('%d/%m/%Y')}...")
        st.success("📊 Analisando com dados da temporada 2024-2025")
        if enviar_auto:
            st.warning("📤 Alertas serão enviados para Telegram")
            if com_imagem:
                st.info("🖼️ Alertas incluirão imagens com escudos")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Busca jogos
    jogos = obter_jogos_data(data_str)
    
    if not jogos:
        st.error("❌ Nenhum jogo encontrado para esta data")
        return
    
    jogos = jogos[:top_n]
    
    status_text.text(f"📊 Analisando {len(jogos)} jogos com dados 2024-2025...")
    
    resultados = []
    alertas_enviados = 0
    
    with results_placeholder:
        st.subheader(f"🎯 Análise com Dados Reais 2024-2025")
        
        for i, jogo in enumerate(jogos):
            progress = (i + 1) / len(jogos)
            progress_bar.progress(progress)
            
            home_team = jogo['home_team']['full_name']
            away_team = jogo['visitor_team']['full_name']
            status_text.text(f"🔍 Analisando: {home_team} vs {away_team} ({i+1}/{len(jogos)})")
            
            home_id = jogo["home_team"]["id"]
            away_id = jogo["visitor_team"]["id"]
            
            try:
                # Previsões com dados reais 2024-2025
                total_estim, total_conf, total_tend = prever_total_points(home_id, away_id, janela)
                vencedor, vencedor_conf, vencedor_detalhe = prever_vencedor(home_id, away_id, janela)
                
                predictions = {
                    "total": {
                        "estimativa": total_estim, 
                        "confianca": total_conf, 
                        "tendencia": total_tend
                    },
                    "vencedor": {
                        "vencedor": vencedor,
                        "confianca": vencedor_conf,
                        "detalhe": vencedor_detalhe
                    }
                }
                
                # Exibe preview da imagem
                with st.expander(f"🖼️ Preview Alerta: {away_team} @ {home_team}", expanded=False):
                    visualizar_imagem_alerta(jogo, predictions)
                
                # Envia alerta
                enviado = verificar_e_enviar_alerta(jogo, predictions, enviar_auto, com_imagem)
                if enviado and enviar_auto:
                    alertas_enviados += 1
                
                # Exibe resultado
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{home_team}** vs **{away_team}**")
                    st.write(f"📍 **Status:** {jogo.get('status', 'SCHEDULED')}")
                
                with col2:
                    st.write(f"📊 **Total:** {total_tend}")
                    st.write(f"🎯 **Vencedor:** {vencedor}")
                    st.write(f"💪 **Confiança:** {vencedor_conf}%")
                
                with col3:
                    st.write(f"📈 **Estimativa:** {total_estim:.1f}")
                    st.write(f"🔒 **Confiança:** {total_conf}%")
                    if enviado and enviar_auto:
                        if com_imagem:
                            st.success("✅ Telegram + Imagem")
                        else:
                            st.success("✅ Telegram")
                    else:
                        st.info("💾 Salvo")
                
                st.markdown("---")
                
                resultados.append({
                    "jogo": jogo,
                    "predictions": predictions
                })
                
            except Exception as e:
                st.error(f"❌ Erro ao analisar {home_team} vs {away_team}: {e}")
                continue
    
    progress_placeholder.empty()
    
    # Resumo final
    st.success(f"✅ Análise com dados 2024-2025 concluída!")
    st.info(f"""
    **📊 Resumo da Análise:**
    - 🏀 {len(resultados)} jogos analisados com dados 2024-2025
    - 📤 {alertas_enviados} alertas enviados para Telegram
    - 🖼️ {'Com imagens' if com_imagem else 'Apenas texto'}
    - 📈 Estatísticas baseadas na temporada atual
    - 💾 Dados salvos para conferência futura
    """)

# =============================
# ATUALIZAR A FUNÇÃO MAIN
# =============================
def main():
    st.set_page_config(page_title="🏀 Elite Master - NBA Alerts", layout="wide")
    st.title("🏀 Elite Master — Análise com Dados Reais 2024-2025")
    
    st.sidebar.header("⚙️ Configurações")
    st.sidebar.info("🎯 **Fonte:** Dados Reais da API")
    st.sidebar.success("📊 **Temporada:** 2024-2025")
    
    # Botão para Top 4 Jogos
    st.sidebar.markdown("---")
    st.sidebar.subheader("⭐ Top 4 Jogos")
    
    data_selecionada = st.sidebar.date_input("Data para Top 4:", value=date.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")
    
    if st.sidebar.button("🚀 Enviar Top 4 Melhores Jogos", type="primary"):
        with st.spinner("Buscando melhores jogos e enviando alerta..."):
            enviar_alerta_top4_jogos(data_str)
    
    # Visualização do Top 4
    if st.sidebar.button("👀 Visualizar Top 4 Jogos"):
        top4_jogos = obter_top4_melhores_jogos(data_str)
        
        if top4_jogos:
            st.sidebar.success(f"🎯 Top 4 Jogos para {data_str}:")
            for i, jogo_info in enumerate(top4_jogos, 1):
                home_team = jogo_info["home_team_name"]
                visitor_team = jogo_info["visitor_team_name"]
                pontuacao = jogo_info["pontuacao"]
                st.sidebar.write(f"{i}. {visitor_team} @ {home_team}")
                st.sidebar.write(f"   Pontuação: {pontuacao:.1f}")
        else:
            st.sidebar.warning("Nenhum jogo encontrado para esta data.")
    
    # Botão para atualizar resultados na sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 Atualizações")
    
    if st.sidebar.button("📡 Atualizar Todos os Resultados", type="secondary"):
        with st.spinner("Atualizando resultados de todas as partidas salvas..."):
            jogos_atualizados = atualizar_resultados_partidas()
            if jogos_atualizados > 0:
                st.sidebar.success(f"✅ {jogos_atualizados} jogos atualizados!")
            else:
                st.sidebar.info("ℹ️ Nenhum jogo precisou de atualização.")
    
    # Botão para limpar estatísticas
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Estatísticas")
    
    if st.sidebar.button("🧹 Limpar Estatísticas", type="secondary"):
        limpar_estatisticas()
        st.sidebar.success("✅ Estatísticas limpas!")
        st.rerun()

    # Botão para alertas de resultados na sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 Alertas de Resultados")
    
    if st.sidebar.button("📤 Enviar Alerta de Resultados", type="secondary"):
        with st.spinner("Enviando alerta de resultados conferidos..."):
            jogos_alertados = enviar_alerta_resultados_conferidos()
            if jogos_alertados > 0:
                st.sidebar.success(f"✅ Alerta para {jogos_alertados} jogos!")
            else:
                st.sidebar.info("ℹ️ Nenhum jogo novo para alerta.")
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Análise", "📊 Jogos Analisados", "✅ Conferência", "📈 Estatísticas"])
    
    with tab1:
        exibir_aba_analise()
    
    with tab2:
        exibir_jogos_analisados()
    
    with tab3:
        conferir_resultados()
    
    with tab4:
        exibir_estatisticas()

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if __name__ == "__main__":
    main()
