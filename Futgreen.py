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
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

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
    """Carrega dados JSON com verificação de timeout."""
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            
            # Verificar se o cache é muito antigo
            if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
                agora = datetime.now().timestamp()
                # se o arquivo inteiro tiver timestamp salvo como chave
                if isinstance(dados, dict) and '_timestamp' in dados:
                    if agora - dados['_timestamp'] > CACHE_TIMEOUT:
                        return {}
                else:
                    # fallback: verificar modificação do arquivo
                    if agora - os.path.getmtime(caminho) > CACHE_TIMEOUT:
                        return {}
            return dados
    except (json.JSONDecodeError, IOError) as e:
        st.error(f"Erro ao carregar {caminho}: {e}")
    return {}

def salvar_json(caminho: str, dados: dict):
    """Salva dados JSON com timestamp."""
    try:
        # Adicionar timestamp para caches temporais
        if caminho in [CACHE_JOGOS, CACHE_CLASSIFICACAO]:
            # preservar estrutura se for dict
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
    """Carrega o histórico completo de jogos conferidos."""
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_historico(historico: list):
    """Salva o histórico atualizado de jogos conferidos."""
    try:
        with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar histórico: {e}")

def registrar_no_historico(resultado: dict):
    """Adiciona jogo conferido ao histórico geral."""
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
    """Limpa completamente o histórico de desempenho."""
    if os.path.exists(HISTORICO_PATH):
        try:
            os.remove(HISTORICO_PATH)
            st.success("🧹 Histórico de desempenho limpo com sucesso!")
        except Exception as e:
            st.error(f"Erro ao remover histórico: {e}")
    else:
        st.info("⚠️ Nenhum histórico encontrado para limpar.")

# =============================
# Utilitários de Data e Formatação
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    """Formata data ISO para data e hora brasileira."""
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except ValueError:
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    """Abrevia nomes longos para exibição."""
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Comunicação com APIs
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID, disable_web_page_preview: bool = True) -> bool:
    """Envia mensagem para o Telegram com tratamento de erro.
    disable_web_page_preview: False -> permite preview de imagens (escudos) quando há URLs na mensagem.
    """
    try:
        params = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": str(disable_web_page_preview).lower()
        }
        response = requests.get(BASE_URL_TG, params=params, timeout=10)
        return response.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao enviar para Telegram: {e}")
        return False

def obter_dados_api(url: str, timeout: int = 10) -> dict | None:
    """Faz requisição genérica à API com tratamento de erro."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Erro na requisição API: {e}")
        return None

def obter_classificacao(liga_id: str) -> dict:
    """Obtém dados de classificação da liga."""
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
    """Obtém jogos da liga para uma data específica."""
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
    """Calcula tendência de gols baseada em estatísticas históricas."""
    dados_home = classificacao.get(home, {"scored": 0, "against": 0, "played": 1})
    dados_away = classificacao.get(away, {"scored": 0, "against": 0, "played": 1})

    # Evitar divisão por zero
    played_home = max(dados_home["played"], 1)
    played_away = max(dados_away["played"], 1)

    media_home_feitos = dados_home["scored"] / played_home
    media_home_sofridos = dados_home["against"] / played_home
    media_away_feitos = dados_away["scored"] / played_away
    media_away_sofridos = dados_away["against"] / played_away

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    # Determinar tendência e confiança
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
    """Envia alerta formatado para o Telegram."""
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")

    status = fixture.get("status", "DESCONHECIDO")
    gols_home = fixture.get("score", {}).get("fullTime", {}).get("home")
    gols_away = fixture.get("score", {}).get("fullTime", {}).get("away")
    
    placar = f"{gols_home} x {gols_away}" if gols_home is not None and gols_away is not None else None

    msg = (
        f"⚽ <b>Alerta de Gols!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"📌 Status: {status}\n"
    )
    
    if placar:
        msg += f"📊 Placar: <b>{placar}</b>\n"
        
    msg += (
        f"📈 Tendência: <b>{tendencia}</b>\n"
        f"🎯 Estimativa: <b>{estimativa:.2f} gols</b>\n"
        f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
        f"🏆 Liga: {competicao}"
    )
    
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    """Verifica e envia alerta se necessário."""
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
# Alerta: Jogos com confiança >=70% (todos)
# =============================
def enviar_alerta_conf70(jogos_conf_70: list):
    """Envia alerta com todos os jogos de confiança >= 70% (inclui escudos se disponível)."""
    if not jogos_conf_70:
        return

    # Ordenar por confiança desc
    jogos_sorted = sorted(jogos_conf_70, key=lambda x: x["confianca"], reverse=True)

    # Determinar período (datas dos jogos) e total
    datas = []
    for j in jogos_sorted:
        if isinstance(j.get("hora"), datetime):
            datas.append(j["hora"].date())
    data_inicio = datas[0].strftime("%Y-%m-%d") if datas else "-"
    data_fim = datas[-1].strftime("%Y-%m-%d") if datas else "-"
    total = len(jogos_sorted)

    # Montar mensagem HTML
    msg = (
        f"🔥 <b>Jogos de Alta Confiança (≥70%)</b>\n\n"
        f"📅 Período: {data_inicio} → {data_fim}\n"
        f"📋 Total: {total} jogos\n\n"
    )

    for j in jogos_sorted:
        hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
        esc_home = j.get("escudo_home", "") or ""
        esc_away = j.get("escudo_away", "") or ""

        # Linha principal com nomes e confiança
        msg += (
            f"<b>{j['home']}</b> vs <b>{j['away']}</b>\n"
            f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | 💯 Conf.: {j['confianca']:.0f}%\n"
        )

        # Se houver escudos, anexar como links (preview ativo)
        # Ex.: clicando no link o Telegram costuma gerar o preview com a imagem do crest
        if esc_home:
            msg += f'🔗 <a href="{esc_home}">Escudo {j["home"]}</a>  '
        if esc_away:
            msg += f'🔗 <a href="{esc_away}">Escudo {j["away"]}</a>'

        msg += "\n\n"

    msg += "⚽ Enviado automaticamente — jogos com confiança ≥ 70%."

    # Enviar com preview habilitado (para mostrar imagens dos escudos quando possível)
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2, disable_web_page_preview=False)

# =============================
# Geração de Relatórios
# =============================
def gerar_relatorio_pdf(jogos_conferidos: list) -> io.BytesIO:
    """Gera relatório PDF dos jogos conferidos."""
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

    # Alternar cores das linhas
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

    # Sidebar para configurações
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Jogos no Top", [3, 5, 10], index=0)
        # Checkbox para enviar alerta dos jogos >=70%
        enviar_alerta_70 = st.checkbox("🚨 Enviar alerta com jogos de confiança ≥ 70%", value=True)
        st.info("Configure as opções de análise")

    # Controles principais
    col1, col2 = st.columns([2, 1])
    
    with col1:
        data_selecionada = st.date_input(
            "📅 Data para análise:", 
            value=datetime.today()
        )
    
    with col2:
        todas_ligas = st.checkbox(
            "🌍 Todas as ligas", 
            value=True,
            help="Buscar jogos de todas as ligas disponíveis"
        )

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox(
            "📌 Liga específica:", 
            list(LIGA_DICT.keys())
        )

    # Processamento de jogos
    if st.button("🔍 Buscar Partidas", type="primary"):
        # passamos o estado do checkbox para a função
        processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, enviar_alerta_70)

    # Botões de ação
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

    # Painel de desempenho com opções (período ou últimos N)
    st.markdown("---")
    st.subheader("📊 Painel de Desempenho (Histórico)")

    # Opções do usuário para analisar histórico
    usar_periodo = st.checkbox("🔎 Usar período específico (em vez dos últimos N jogos)", value=False)
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

    # Botão para limpar histórico de desempenho
    if st.button("🧹 Limpar Histórico de Desempenho"):
        limpar_historico()

def processar_jogos(data_selecionada, todas_ligas, liga_selecionada, top_n, enviar_alerta_70: bool):
    """Processa e analisa os jogos do dia. Filtra e envia apenas jogos com confiança >=70%."""
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

            # tentar extrair escudos/crest de diferentes campos possíveis
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

    # Agora filtramos globalmente apenas jogos com confiança >= 70 e que não estejam em andamento/terminados
    jogos_conf_70_global = [
        j for j in top_jogos
        if j["confianca"] >= 70 and j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]
    ]

    if jogos_conf_70_global:
        # enviar top (Top N entre os >=70) via enviar_top_jogos
        enviar_top_jogos(jogos_conf_70_global, top_n)
        st.success(f"✅ Análise concluída! {len(jogos_conf_70_global)} jogos com confiança ≥70% processados.")
    else:
        st.warning("⚠️ Nenhum jogo com confiança ≥70% encontrado.")

    # Se habilitado, enviar alerta com TODOS os jogos de confiança >= 70% (com escudos e período)
    if enviar_alerta_70:
        if jogos_conf_70_global:
            enviar_alerta_conf70(jogos_conf_70_global)

def enviar_top_jogos(jogos: list, top_n: int):
    """Envia os top N jogos para o Telegram (somente jogos não finalizados)."""
    # 🔎 Filtrar apenas jogos que ainda não começaram
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED", "IN_PLAY", "POSTPONED", "SUSPENDED"]]

    if not jogos_filtrados:
        st.warning("⚠️ Nenhum jogo elegível para o Top Jogos (todos já iniciados ou finalizados).")
        return

    # Ordenar por confiança e pegar top N
    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]

    msg = f"📢 TOP {top_n} Jogos do Dia (confiança ≥ 70%)\n\n"
    for j in top_jogos_sorted:
        hora_format = j["hora"].strftime("%H:%M") if isinstance(j["hora"], datetime) else str(j["hora"])
        esc_home = j.get("escudo_home", "") or ""
        esc_away = j.get("escudo_away", "") or ""

        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
            f"💯 Confiança: {j['confianca']:.0f}%\n"
        )

        if esc_home:
            msg += f'🔗 <a href="{esc_home}">Escudo {j["home"]}</a>  '
        if esc_away:
            msg += f'🔗 <a href="{esc_away}">Escudo {j["away"]}</a>'
        msg += "\n\n"

    # Envio ao Telegram com preview de escudos habilitado
    if enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2, disable_web_page_preview=False):
        st.success(f"🚀 Top {top_n} jogos (confiança ≥ 70%) enviados para o canal!")
    else:
        st.error("❌ Erro ao enviar top jogos para o Telegram")

def atualizar_status_partidas():
    """Atualiza o status das partidas em cache."""
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
    """Conferência de resultados dos jogos alertados."""
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

        # Encontrar jogo no cache
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

        # Processar resultado
        resultado_info = processar_resultado_jogo(jogo_dado, info)
        if resultado_info:
            exibir_resultado_streamlit(resultado_info)
            
            if resultado_info["status"] == "FINISHED":
                enviar_resultado_telegram(resultado_info)
                # Registrar no histórico antes de marcar como conferido
                registrar_no_historico(resultado_info)
                info["conferido"] = True
                mudou = True

        # Coletar dados para PDF (preparar mesmo se resultado_info for None)
        jogos_conferidos.append(preparar_dados_pdf(jogo_dado, info, resultado_info))

    if mudou:
        salvar_alertas(alertas)
        st.success("✅ Resultados conferidos e atualizados!")

    # Gerar PDF se houver jogos
    if jogos_conferidos:
        gerar_pdf_jogos(jogos_conferidos)

def processar_resultado_jogo(jogo: dict, info: dict) -> dict | None:
    """Processa o resultado de um jogo."""
    home = jogo["homeTeam"]["name"]
    away = jogo["awayTeam"]["name"]
    status = jogo.get("status", "DESCONHECIDO")
    gols_home = jogo.get("score", {}).get("fullTime", {}).get("home")
    gols_away = jogo.get("score", {}).get("fullTime", {}).get("away")
    
    placar = f"{gols_home} x {gols_away}" if gols_home is not None and gols_away is not None else "-"
    total_gols = (gols_home or 0) + (gols_away or 0)

    # Determinar resultado da aposta
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
    """Exibe resultado formatado no Streamlit."""
    bg_color = "#1e4620" if resultado["resultado"] == "🟢 GREEN" else \
               "#5a1e1e" if resultado["resultado"] == "🔴 RED" else "#2c2c2c"
    
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
    """Envia resultado para o Telegram."""
    msg = (
        f"📊 <b>Resultado Conferido</b>\n"
        f"🏟️ {resultado['home']} vs {resultado['away']}\n"
        f"⚽ Tendência: {resultado['tendencia']} | Estim.: {resultado['estimativa']:.2f} | Conf.: {resultado['confianca']:.0f}%\n"
        f"📊 Placar Final: <b>{resultado['placar']}</b>\n"
        f"✅ Resultado: <b>{resultado['resultado']}</b>"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

def preparar_dados_pdf(jogo: dict, info: dict, resultado: dict) -> list:
    """Prepara dados para geração do PDF."""
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
    """Gera e disponibiliza PDF dos jogos conferidos."""
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
    """Limpa todos os caches do sistema."""
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
    """Tenta parsear 'YYYY-MM-DD HH:MM:SS' ou 'YYYY-MM-DD' e retorna datetime.date."""
    if not data_str:
        return None
    try:
        # Prefer full datetime
        return datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(data_str, "%Y-%m-%d")
        except Exception:
            return None

def calcular_desempenho(qtd_jogos: int = 50):
    """Calcula desempenho com base nos últimos N jogos do histórico e envia alerta."""
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return

    # selecionar últimos N (preservando ordem cronológica)
    historico_considerado = historico[-qtd_jogos:] if len(historico) > qtd_jogos else historico[:]
    # extrair datas para mostrar período
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

    # Exibir no Streamlit
    st.subheader("📈 Desempenho (Últimos N jogos)")
    st.write(f"📅 Período considerado: {data_inicio} → {data_fim}")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ GREENs", greens)
    c2.metric("❌ REDs", reds)
    c3.metric("🎯 Taxa de Acerto (%)", f"{taxa_acerto:.1f}%")
    st.write(f"📊 Jogos considerados (com resultado): {total} — (analisados: {len(historico_considerado)})")

    # Mostrar tabela com os registros considerados
    df = pd.DataFrame(historico_considerado)
    if not df.empty:
        st.markdown("Registros considerados (mais recentes primeiro):")
        st.dataframe(df.sort_values("data_conferencia", ascending=False).head(200))

    # Mensagem para o Telegram
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
    """Calcula desempenho filtrando histórico entre duas datas (inclusive)."""
    historico = carregar_historico()
    if not historico:
        st.warning("⚠️ Nenhum jogo conferido ainda.")
        return

    # Normalizar data_inicio/data_fim para datetime.date
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

    # Exibir no Streamlit
    st.subheader("📈 Desempenho (Período selecionado)")
    st.write(f"📅 Período considerado: {data_inicio} → {data_fim}")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ GREENs", greens)
    c2.metric("❌ REDs", reds)
    c3.metric("🎯 Taxa de Acerto (%)", f"{taxa_acerto:.1f}%")
    st.write(f"📊 Jogos considerados (com resultado): {total} — (registros encontrados: {len(consider)})")

    # Mostrar tabela
    df = pd.DataFrame(consider)
    if not df.empty:
        st.markdown("Registros no período (mais recentes primeiro):")
        st.dataframe(df.sort_values("data_conferencia", ascending=False).head(500))

    # Mensagem para o Telegram
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
