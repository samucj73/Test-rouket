import requests
import datetime
import time

# =============================
# Configurações API
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Ligas monitoradas (Competition Codes)
# =============================
LIGAS = ["PL", "PD", "BL1", "SA", "FL1", "BSA"]

# =============================
# Funções principais
# =============================

def carregar_estatisticas_liga(codigo_liga: str):
    """Carrega estatísticas dos times de uma liga (gols feitos/sofridos)."""
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/standings"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro ao buscar estatísticas:", resp.status_code, resp.text)
        return {}
    data = resp.json()

    stats = {}
    for table in data.get("standings", []):
        for entry in table.get("table", []):
            team_id = entry["team"]["id"]
            stats[team_id] = {
                "name": entry["team"]["name"],
                "played": entry["playedGames"],
                "gf": entry["goalsFor"],
                "ga": entry["goalsAgainst"]
            }
    return stats


def calcular_gols_estimados(match, stats_liga):
    """Calcula a estimativa de gols de um jogo usando médias da liga."""
    home_id = match["homeTeam"]["id"]
    away_id = match["awayTeam"]["id"]

    home_stats = stats_liga.get(home_id, None)
    away_stats = stats_liga.get(away_id, None)

    if not home_stats or not away_stats:
        return 2.5  # fallback caso não tenha dados

    def media(time):
        if time["played"] > 0:
            return (time["gf"] + time["ga"]) / time["played"]
        return 2.5

    media_home = media(home_stats)
    media_away = media(away_stats)

    return round((media_home + media_away) / 2, 2)


def buscar_jogos_dia(codigo_liga: str, data: str):
    """Busca os jogos de uma liga em uma data."""
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/matches?dateFrom={data}&dateTo={data}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro ao buscar jogos:", resp.status_code, resp.text)
        return []
    return resp.json().get("matches", [])


def selecionar_top3_distintos(partidas_info, max_por_faixa=3):
    """
    Seleciona Top3 para +1.5, +2.5 e +3.5 garantindo:
      - prioridade +2.5 -> +1.5 -> +3.5
      - não repetir fixture_id entre faixas
      - evita repetir times entre faixas quando possível
    """
    usadas = set()
    top_15, top_25, top_35 = [], [], []

    # Ordena partidas por estimativa decrescente
    partidas_info.sort(key=lambda x: x["estimativa"], reverse=True)

    # Seleção Top +2.5
    for jogo in partidas_info:
        if len(top_25) < max_por_faixa and jogo["id"] not in usadas:
            top_25.append(jogo)
            usadas.add(jogo["id"])

    # Seleção Top +1.5
    for jogo in partidas_info:
        if len(top_15) < max_por_faixa and jogo["id"] not in usadas:
            top_15.append(jogo)
            usadas.add(jogo["id"])

    # Seleção Top +3.5
    for jogo in partidas_info:
        if len(top_35) < max_por_faixa and jogo["id"] not in usadas:
            top_35.append(jogo)
            usadas.add(jogo["id"])

    return top_15, top_25, top_35


def conferir_resultados(jogos_previstos):
    """Confere se os jogos bateram a linha prevista."""
    for faixa, jogos in jogos_previstos.items():
        for jogo in jogos:
            url = f"{BASE_URL_FD}/matches/{jogo['id']}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()["match"]

            if data["status"] == "FINISHED":
                gols_home = data["score"]["fullTime"]["home"]
                gols_away = data["score"]["fullTime"]["away"]
                total = gols_home + gols_away

                if faixa == "+1.5":
                    bateu = total > 1.5
                elif faixa == "+2.5":
                    bateu = total > 2.5
                else:
                    bateu = total > 3.5

                status = "🟢 GREEN" if bateu else "🔴 RED"
                print(f"{jogo['home']} vs {jogo['away']} | {faixa} | Resultado: {total} gols → {status}")


# =============================
# Execução principal
# =============================

if __name__ == "__main__":
    hoje = datetime.date.today().strftime("%Y-%m-%d")
    print(f"\n📅 Buscando jogos de {hoje}\n")

    todas_partidas = []
    stats_cache = {}

    # Carrega estatísticas e jogos por liga
    for liga in LIGAS:
        stats_cache[liga] = carregar_estatisticas_liga(liga)
        jogos = buscar_jogos_dia(liga, hoje)
        for j in jogos:
            estimativa = calcular_gols_estimados(j, stats_cache[liga])
            todas_partidas.append({
                "id": j["id"],
                "home": j["homeTeam"]["name"],
                "away": j["awayTeam"]["name"],
                "estimativa": estimativa
            })

    # Seleciona Top3 de cada faixa
    top15, top25, top35 = selecionar_top3_distintos(todas_partidas)

    # Alertas
    print("\n🚨 ALERTAS DO DIA")
    print("\nTop +2.5:")
    for jogo in top25:
        print(f"{jogo['home']} vs {jogo['away']} → Estimativa: {jogo['estimativa']}")

    print("\nTop +1.5:")
    for jogo in top15:
        print(f"{jogo['home']} vs {jogo['away']} → Estimativa: {jogo['estimativa']}")

    print("\nTop +3.5:")
    for jogo in top35:
        print(f"{jogo['home']} vs {jogo['away']} → Estimativa: {jogo['estimativa']}")

    # Conferência automática (pode rodar de tempos em tempos)
    print("\n✅ Conferindo resultados (aguarde rodadas terminarem)...")
    time.sleep(5)
    conferir_resultados({"+1.5": top15, "+2.5": top25, "+3.5": top35})
