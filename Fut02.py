import requests
import os
import json
from datetime import datetime

# =============================
# Configurações
# =============================
API_KEY = "SUA_API_KEY"  # Football API key
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {"x-apisports-key": API_KEY}

# Telegram
TELEGRAM_TOKEN = "SEU_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Salvar alertas já enviados
ALERTAS_PATH = "alertas_andamento.json"

# =============================
# Funções Auxiliares
# =============================

def carregar_alertas_andamento():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas_andamento(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")
    goals = fixture.get("goals", {"home": 0, "away": 0})
    home_goals = goals.get("home", 0) or 0
    away_goals = goals.get("away", 0) or 0

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def calcular_tendencia_confianca(media_casa, media_fora):
    estimativa = (media_casa + media_fora) / 2
    if estimativa >= 2.5:
        tendencia = "Mais 2.5 gols 🔥"
        confianca = min(90, 50 + estimativa * 10)
    elif estimativa <= 1.5:
        tendencia = "Menos 1.5 gols ❄️"
        confianca = min(90, 50 + (2 - estimativa) * 20)
    else:
        tendencia = "Equilibrado"
        confianca = 40
    return estimativa, confianca, tendencia

def verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas_andamento()
    fixture_id = str(fixture["fixture"]["id"])
    goals = fixture.get("goals", {"home": 0, "away": 0})
    home_goals = goals.get("home", 0) or 0
    away_goals = goals.get("away", 0) or 0

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if (
            ultimo["home_goals"] != home_goals
            or ultimo["away_goals"] != away_goals
            or ultimo["tendencia"] != tendencia
        ):
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia,
        }
        salvar_alertas_andamento(alertas)

# =============================
# Função para estatísticas reais
# =============================
def media_gols_time(team_id, league_id, season=2023):
    url = f"{BASE_URL}/teams/statistics?league={league_id}&season={season}&team={team_id}"
    r = requests.get(url, headers=HEADERS)
    stats = r.json().get("response", {})
    if not stats:
        return 1.5  # fallback caso API não responda

    jogos = stats["fixtures"]["played"]["total"]
    gols_marcados = stats["goals"]["for"]["total"]["total"]
    gols_sofridos = stats["goals"]["against"]["total"]["total"]

    if jogos == 0:
        return 1.5
    return (gols_marcados + gols_sofridos) / jogos

# =============================
# Principais Ligas
# =============================
ligas_principais = {
    "Premier League": 39,   # Inglaterra
    "La Liga": 140,         # Espanha
    "Serie A": 135,         # Itália
    "Bundesliga": 78,       # Alemanha
    "Ligue 1": 61,          # França
    "Brasileirão Série A": 71  # Brasil
}

# =============================
# Buscar Jogos do Dia
# =============================
hoje = datetime.today().strftime("%Y-%m-%d")
url = f"{BASE_URL}/fixtures?date={hoje}"
response = requests.get(url, headers=HEADERS)
jogos = response.json().get("response", [])

for match in jogos:
    league_id = match.get("league", {}).get("id")
    if league_id not in ligas_principais.values():
        continue  # ignora jogos fora das ligas principais

    home_id = match["teams"]["home"]["id"]
    away_id = match["teams"]["away"]["id"]

    # Estatísticas reais da temporada 2023
    media_casa = media_gols_time(home_id, league_id, season=2023)
    media_fora = media_gols_time(away_id, league_id, season=2023)

    estimativa, confianca, tendencia = calcular_tendencia_confianca(media_casa, media_fora)

    if confianca >= 60 and tendencia != "Equilibrado":
        verificar_e_atualizar_alerta(match, tendencia, confianca, estimativa)
