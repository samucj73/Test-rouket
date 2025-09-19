import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json

# =============================
# Configurações API
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo 2
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"

# =============================
# Funções de persistência
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg}, timeout=10)
    except Exception as e:
        # não interrompe o app se telegram falhar
        print("Erro ao enviar Telegram:", e)

def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")

    data_iso = fixture["fixture"]["date"]
    data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
    data_jogo_brt = data_jogo - timedelta(hours=3)
    data_formatada = data_jogo_brt.strftime("%d/%m/%Y")
    hora_formatada = data_jogo_brt.strftime("%H:%M")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas()
    fixture_id = str(fixture["fixture"]["id"])

    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0

    # inclui data do jogo no registro do alerta
    data_iso = fixture["fixture"]["date"]
    data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
    data_formatada = data_jogo.strftime("%d/%m/%Y")

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if (
            ultimo.get("home_goals") != home_goals
            or ultimo.get("away_goals") != away_goals
            or ultimo.get("tendencia") != tendencia
            or ultimo.get("data_jogo") != data_formatada
        ):
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia,
            "data_jogo": data_formatada,
            "last_alerted_at": datetime.utcnow().isoformat()
        }
        salvar_alertas(alertas)

# =============================
# Cálculo H2H ponderada
# =============================
def media_gols_confrontos_diretos(home_id, away_id, temporada=None, max_jogos=5):
    try:
        url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"media_gols": 0, "total_jogos": 0}

        jogos = response.json().get("response", [])
        if temporada:
            jogos = [j for j in jogos if j.get("league", {}).get("season") == temporada]
        
        jogos = sorted(jogos, key=lambda x: x["fixture"]["date"], reverse=True)[:max_jogos]

        if not jogos:
            return {"media_gols": 0, "total_jogos": 0}

        total_pontos = 0
        total_peso = 0
        jogos_count = 0
        for idx, j in enumerate(jogos):
            # considerar somente jogos finalizados
            if j.get("fixture", {}).get("status", {}).get("short") != "FT":
                continue
            score = j.get("score", {}).get("fulltime", {})
            home_goals = score.get("home") or 0
            away_goals = score.get("away") or 0
            gols = home_goals + away_goals
            peso = max_jogos - idx
            total_pontos += gols * peso
            total_peso += peso
            jogos_count += 1

        media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
        return {"media_gols": media_ponderada, "total_jogos": jogos_count}
    except Exception as e:
        print("Erro H2H:", e)
        return {"media_gols": 0, "total_jogos": 0}

# =============================
# Estatísticas a partir dos últimos jogos (fallback robusto)
# =============================
def obter_medias_ultimos_jogos(team_id, temporada, max_jogos=10):
    """
    Retorna dicionário com:
      { 'home': {'media_gols_marcados', 'media_gols_sofridos', 'jogos'},
        'away': {...},
        'overall': {...} }
    Caso falhe, retorna valores por padrão.
    """
    try:
        # Tenta buscar os últimos jogos do time
        url = f"{BASE_URL}/fixtures?team={team_id}&last={max_jogos}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            raise Exception("status != 200")
        partidas = response.json().get("response", [])
        # filtrar por temporada se possível
        if temporada:
            partidas = [p for p in partidas if p.get("league", {}).get("season") == temporada]
        # calcular médias
        home_goals_scored = home_goals_conceded = home_count = 0
        away_goals_scored = away_goals_conceded = away_count = 0
        overall_scored = overall_conceded = overall_count = 0

        for p in partidas:
            score = p.get("score", {}).get("fulltime", {})
            home_team = p.get("teams", {}).get("home", {}).get("id")
            away_team = p.get("teams", {}).get("away", {}).get("id")
            home_goals = score.get("home")
            away_goals = score.get("away")
            # se não houver score, pula
            if home_goals is None or away_goals is None:
                continue
            overall_count += 1
            if team_id == home_team:
                home_count += 1
                home_goals_scored += home_goals
                home_goals_conceded += away_goals
            elif team_id == away_team:
                away_count += 1
                away_goals_scored += away_goals
                away_goals_conceded += home_goals

            # overall
            if team_id == home_team:
                overall_scored += home_goals
                overall_conceded += away_goals
            elif team_id == away_team:
                overall_scored += away_goals
                overall_conceded += home_goals

        def avg(a, b):
            return round(a / b, 2) if b else 0.0

        medias = {
            "home": {
                "media_gols_marcados": avg(home_goals_scored, home_count),
                "media_gols_sofridos": avg(home_goals_conceded, home_count),
                "jogos": home_count
            },
            "away": {
                "media_gols_marcados": avg(away_goals_scored, away_count),
                "media_gols_sofridos": avg(away_goals_conceded, away_count),
                "jogos": away_count
            },
            "overall": {
                "media_gols_marcados": avg(overall_scored, overall_count),
                "media_gols_sofridos": avg(overall_conceded, overall_count),
                "jogos": overall_count
            }
        }
        return medias
    except Exception as e:
        print("Erro ao obter médias últimos jogos:", e)
        # fallback seguro
        return {
            "home": {"media_gols_marcados": 1.2, "media_gols_sofridos": 1.1, "jogos": 0},
            "away": {"media_gols_marcados": 1.1, "media_gols_sofridos": 1.3, "jogos": 0},
            "overall": {"media_gols_marcados": 1.15, "media_gols_sofridos": 1.2, "jogos": 0}
        }

def obter_aproveitamento_recente(team_id, max_jogos=5):
    """
    Retorna taxa de vitórias nos últimos max_jogos (0..1).
    """
    try:
        url = f"{BASE_URL}/fixtures?team={team_id}&last={max_jogos}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            raise Exception("status != 200")
        partidas = response.json().get("response", [])
        vitorias = 0
        jogos_validos = 0
        for p in partidas:
            status = p.get("fixture", {}).get("status", {}).get("short")
            if status != "FT":
                continue
            jogos_validos += 1
            score = p.get("score", {}).get("fulltime", {})
            home_team = p.get("teams", {}).get("home", {}).get("id")
            away_team = p.get("teams", {}).get("away", {}).get("id")
            home_goals = score.get("home") or 0
            away_goals = score.get("away") or 0
            if team_id == home_team and home_goals > away_goals:
                vitorias += 1
            elif team_id == away_team and away_goals > home_goals:
                vitorias += 1
        return (vitorias / jogos_validos) if jogos_validos else 0.5
    except Exception as e:
        print("Erro aproveitamento:", e)
        return 0.5

# =============================
# Função de tendência ajustada
# =============================
def calcular_tendencia_confianca_ajustada(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    media_time_casa = media_casa.get("media_gols_marcados", 0) + media_fora.get("media_gols_sofridos", 0)
    media_time_fora = media_fora.get("media_gols_marcados", 0) + media_casa.get("media_gols_sofridos", 0)
    
    estimativa_base = (media_time_casa + media_time_fora) / 2
    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * media_h2h.get("media_gols", 0)

    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa_final - 2.5) * 15)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa_final - 1.5) * 20)
    else:
        tendencia = "Menos 1.5"
        confianca = min(95, 55 + (1.5 - estimativa_final) * 20)

    return estimativa_final, confianca, tendencia

# =============================
# Função para obter odds reais (mantida)
# =============================
def obter_odds(fixture_id):
    try:
        url = f"{BASE_URL}/odds?fixture={fixture_id}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"1.5": None, "2.5": None}

        response_json = response.json().get("response", [])
        odds_15 = None
        odds_25 = None

        if not response_json:
            return {"1.5": None, "2.5": None}

        # Considera apenas a primeira casa de apostas
        bookmakers = response_json[0].get("bookmakers", [])
        if not bookmakers:
            return {"1.5": None, "2.5": None}

        markets = bookmakers[0].get("markets", [])
        for bet in markets:
            label = bet.get("label") or ""
            if "goals over/under" in label.lower():
                for outcome in bet.get("outcomes", []):
                    name = outcome.get("name", "")
                    price = outcome.get("price")
                    if name == "Over 1.5":
                        odds_15 = price
                    elif name == "Over 2.5":
                        odds_25 = price

        return {"1.5": odds_15, "2.5": odds_25}
    except Exception as e:
        print("Erro obter odds:", e)
        return {"1.5": None, "2.5": None}

# =============================
# BTTS estimator
# =============================
def calcular_btts_estimativa(media_casa_stats, media_fora_stats):
    """
    media_casa_stats: dict resultante de obter_medias_ultimos_jogos(team_home)['home'/'overall']
    media_fora_stats: dict resultante de obter_medias_ultimos_jogos(team_away)['away'/'overall']
    Retorna prob (0..1) e confianca (50..95)
    """
    # estimativas simples baseadas em médias
    avg_home_for = media_casa_stats.get("media_gols_marcados", 1.2)
    avg_home_against = media_casa_stats.get("media_gols_sofridos", 1.1)
    avg_away_for = media_fora_stats.get("media_gols_marcados", 1.1)
    avg_away_against = media_fora_stats.get("media_gols_sofridos", 1.2)

    # probabilidade aproximada: se ambos têm médias ofensivas > 1.0 e médias sofridas > 0.9, BTTS sobe
    base = (avg_home_for + avg_away_for) / 4 + (avg_home_against + avg_away_against) / 4
    # normalizar para 0..1 (valores típicos 0.5..2.0)
    prob = min(0.95, max(0.05, (base - 0.5) / 1.5))
    confianca = min(95, max(50, int(50 + prob * 45)))
    return prob, confianca

# =============================
# Calcular favorito por estatísticas
# =============================
def calcular_favorito_por_estatisticas(media_casa_full, media_fora_full, ultima_aproveitamento_casa, ultima_aproveitamento_fora):
    """
    media_casa_full: dict com chaves 'home' e 'overall' para o time da casa (resultado de obter_medias_ultimos_jogos)
    media_fora_full: dict com chaves 'away' e 'overall' para o time de fora
    ultima_aproveitamento_*: valor 0..1 (vitórias nos últimos N jogos)
    """
    # força ofensiva/defensiva aproximada
    # usar média local quando pertinente, senão overall
    casa_for = media_casa_full.get("home", {}).get("media_gols_marcados") or media_casa_full.get("overall", {}).get("media_gols_marcados", 1.2)
    casa_against = media_casa_full.get("home", {}).get("media_gols_sofridos") or media_casa_full.get("overall", {}).get("media_gols_sofridos", 1.1)

    fora_for = media_fora_full.get("away", {}).get("media_gols_marcados") or media_fora_full.get("overall", {}).get("media_gols_marcados", 1.1)
    fora_against = media_fora_full.get("away", {}).get("media_gols_sofridos") or media_fora_full.get("overall", {}).get("media_gols_sofridos", 1.2)

    # pontuação de força (quanto maior, melhor)
    forca_casa = casa_for + (1.5 - fora_against) + ultima_aproveitamento_casa
    forca_fora = fora_for + (1.5 - casa_against) + ultima_aproveitamento_fora

    diff = forca_casa - forca_fora
    if diff > 0:
        favorito = "Casa"
        confianca = min(95, max(50, int(50 + diff * 20)))
    else:
        favorito = "Fora"
        confianca = min(95, max(50, int(50 + (-diff) * 20)))

    # normalizar limites
    return favorito, confianca

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia nas principais ligas e envia alertas de tendência de gols.")

temporada = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

ligas_principais = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Brasileirão Série A": 71,
    "UEFA Champions League": 2,
    "Copa Libertadores": 13
}

if st.button("🔍 Buscar jogos do dia"):
    url = f"{BASE_URL}/fixtures?date={hoje}"
    response = requests.get(url, headers=HEADERS)
    jogos = response.json().get("response", [])

    st.subheader("📝 Jogos retornados pela API")
    st.json(response.json())

    melhores_15 = []
    melhores_25 = []
    melhores_btts = []
    melhores_favoritos = []

    for match in jogos:
        league_id = match.get("league", {}).get("id")
        if league_id not in ligas_principais.values():
            continue

        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        home_id = match["teams"]["home"]["id"]
        away_id = match["teams"]["away"]["id"]
        media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada, max_jogos=5)
        
        # obter médias reais por time (usa últimos jogos como fonte)
        medias_home_full = obter_medias_ultimos_jogos(home_id, temporada, max_jogos=10)
        medias_away_full = obter_medias_ultimos_jogos(away_id, temporada, max_jogos=10)

        # para a tendência de gols usamos:
        media_casa = {
            "media_gols_marcados": medias_home_full.get("home", {}).get("media_gols_marcados", 1.2),
            "media_gols_sofridos": medias_home_full.get("home", {}).get("media_gols_sofridos", 1.1)
        }
        media_fora = {
            "media_gols_marcados": medias_away_full.get("away", {}).get("media_gols_marcados", 1.1),
            "media_gols_sofridos": medias_away_full.get("away", {}).get("media_gols_sofridos", 1.3)
        }

        estimativa, confianca, tendencia = calcular_tendencia_confianca_ajustada(media_h2h, media_casa, media_fora)

        # Hora e competição
        data_iso = match["fixture"]["date"]
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        data_formatada = data_jogo.strftime("%d/%m/%Y")
        hora_formatada = data_jogo.strftime("%H:%M")
        competicao = match.get("league", {}).get("name", "Desconhecido")

        # Obter odds reais (mantido)
        odds = obter_odds(match["fixture"]["id"])

        # Mostrar no Streamlit
        with st.container():
            st.subheader(f"🏟️ {home} vs {away}")
            st.caption(f"📅 {data_formatada} | Liga: {competicao} | Temporada: {temporada}")
            st.write(f"📊 Estimativa de gols: **{estimativa:.2f}**")
            st.write(f"🔥 Tendência: **{tendencia}**")
            st.write(f"✅ Confiança: **{confianca:.0f}%**")
            st.write(f"💰 Odds Over 1.5: {odds['1.5']} | Over 2.5: {odds['2.5']}")

        # Envio individual (mantido)
        verificar_enviar_alerta(match, tendencia, confianca, estimativa)

        # Adicionar ao top 3 com odds reais
        if tendencia == "Mais 1.5":
            melhores_15.append({
                "home": home,
                "away": away,
                "estimativa": estimativa,
                "confianca": confianca,
                "hora": hora_formatada,
                "data": data_formatada,
                "competicao": competicao,
                "odd_15": odds["1.5"]
            })
        elif tendencia == "Mais 2.5":
            melhores_25.append({
                "home": home,
                "away": away,
                "estimativa": estimativa,
                "confianca": confianca,
                "hora": hora_formatada,
                "data": data_formatada,
                "competicao": competicao,
                "odd_25": odds["2.5"]
            })

        # Calcular BTTS usando médias recentes
        prob_btts, conf_btts = calcular_btts_estimativa(
            medias_home_full.get("home", medias_home_full.get("overall")),
            medias_away_full.get("away", medias_away_full.get("overall"))
        )
        # critério para shortlist: probabilidade > 0.55 ou confiança >= 65 (ajustável)
        if prob_btts > 0.55 or conf_btts >= 65:
            melhores_btts.append({
                "home": home,
                "away": away,
                "prob": prob_btts,
                "confianca": conf_btts,
                "hora": hora_formatada,
                "data": data_formatada,
                "competicao": competicao
            })

        # Calcular favorito por estatísticas
        aproveit_home = obter_aproveitamento_recente(home_id, max_jogos=5)
        aproveit_away = obter_aproveitamento_recente(away_id, max_jogos=5)
        favorito_side, conf_fav = calcular_favorito_por_estatisticas(
            medias_home_full, medias_away_full, aproveit_home, aproveit_away
        )
        favorito_nome = home if favorito_side == "Casa" else away
        # critério para shortlist: confiança >= 55
        if conf_fav >= 55:
            melhores_favoritos.append({
                "home": home,
                "away": away,
                "favorito": favorito_nome,
                "confianca": conf_fav,
                "hora": hora_formatada,
                "data": data_formatada,
                "competicao": competicao
            })

    # Ordenar e pegar top 3
    melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
    melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
    melhores_btts = sorted(melhores_btts, key=lambda x: (x["confianca"], x["prob"]), reverse=True)[:3]
    melhores_favoritos = sorted(melhores_favoritos, key=lambda x: x["confianca"], reverse=True)[:3]

    if melhores_15 or melhores_25 or melhores_btts or melhores_favoritos:
        # incluir data do alerta (hoje) no cabeçalho
        msg_alt = f"📢 TOP ENTRADAS - Alerta de {datetime.now().strftime('%d/%m/%Y')}\n\n"

        if melhores_15:
            odd_combinada_15 = 1
            msg_alt += "🔥 Top 3 Jogos para +1.5 Gols\n"
            for j in melhores_15:
                odd_combinada_15 *= float(j.get("odd_15") or 1)
                msg_alt += (
                    f"🏆 {j['competicao']}\n"
                    f"📅 {j['data']} | 🕒 {j['hora']} BRT\n"
                    f"🏟️ {j['home']} vs {j['away']}\n"
                    f"📊 Estimativa: {j['estimativa']:.2f} gols | ✅ Confiança: {j['confianca']:.0f}%\n"
                    f"💰 Odd: {j.get('odd_15', 'N/A')}\n\n"
                )
            msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_15:.2f}\n\n"

        if melhores_25:
            odd_combinada_25 = 1
            msg_alt += "⚡ Top 3 Jogos para +2.5 Gols\n"
            for j in melhores_25:
                odd_combinada_25 *= float(j.get("odd_25") or 1)
                msg_alt += (
                    f"🏆 {j['competicao']}\n"
                    f"📅 {j['data']} | 🕒 {j['hora']} BRT\n"
                    f"🏟️ {j['home']} vs {j['away']}\n"
                    f"📊 Estimativa: {j['estimativa']:.2f} gols | ✅ Confiança: {j['confianca']:.0f}%\n"
                    f"💰 Odd: {j.get('odd_25', 'N/A')}\n\n"
                )
            msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_25:.2f}\n\n"

        if melhores_btts:
            msg_alt += "🤝 Top 3 Jogos para Ambas Marcam (BTTS)\n"
            for j in melhores_btts:
                msg_alt += (
                    f"🏆 {j['competicao']}\n"
                    f"📅 {j['data']} | 🕒 {j['hora']} BRT\n"
                    f"🏟️ {j['home']} vs {j['away']}\n"
                    f"🔮 Prob BTTS: {j['prob']*100:.0f}% | ✅ Confiança: {j['confianca']:.0f}%\n\n"
                )

        if melhores_favoritos:
            msg_alt += "🏅 Top 3 Times Favoritos a Ganhar (base estatística)\n"
            for j in melhores_favoritos:
                msg_alt += (
                    f"🏆 {j['competicao']}\n"
                    f"📅 {j['data']} | 🕒 {j['hora']} BRT\n"
                    f"⚽ {j['home']} vs {j['away']}\n"
                    f"👉 Favorito: {j['favorito']} | ✅ Confiança: {j['confianca']}%\n\n"
                )

        # Enviar alerta consolidado para canal alternativo
        enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
        st.success("🚀 Top jogos enviados para o canal alternativo 2!")
    else:
        st.info("Nenhum jogo com tendência clara de +1.5, +2.5, BTTS ou favorito estatístico encontrado.")
