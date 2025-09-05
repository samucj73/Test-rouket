import requests
from datetime import datetime
import json

# =============================
# Configurações
# =============================
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"
BASE_URL = "https://api.football-data.org/v4"
COMPETITIONS = ["PL", "CL", "SA"]  # Exemplo: Premier League, Champions League, Serie A
MIN_GOLS = 1.5  # Probabilidade mínima de gols

headers = {
    "X-Auth-Token": API_TOKEN
}

# =============================
# Funções
# =============================
def buscar_partidas_dia(competicoes):
    """Busca partidas do dia nas competições selecionadas"""
    hoje = datetime.today().strftime("%Y-%m-%d")
    partidas_dia = []

    for comp in competicoes:
        url = f"{BASE_URL}/competitions/{comp}/matches?dateFrom={hoje}&dateTo={hoje}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            dados = response.json()
            partidas_dia.extend(dados.get("matches", []))
        else:
            print(f"Erro ao buscar {comp}: {response.status_code}")
    return partidas_dia

def filtrar_partidas_mais_1_5(partidas):
    """Filtra partidas com probabilidade de mais de 1.5 gols"""
    partidas_filtradas = []
    for partida in partidas:
        # Aqui usamos probabilidades se disponíveis (exemplo: odds de mais de 1.5 gols)
        # Se não houver odds, podemos usar heurística simples ou apenas listar todas
        odds = partida.get("odds")
        if odds and "over_1_5_goals" in odds:
            if odds["over_1_5_goals"] > 1.5:  # Exemplo simples
                partidas_filtradas.append(partida)
        else:
            # Caso não haja odds, só adiciona como informação
            partidas_filtradas.append(partida)
    return partidas_filtradas

def mostrar_partidas(partidas):
    """Exibe partidas de forma legível"""
    if not partidas:
        print("Nenhuma partida encontrada hoje com critérios de gols.")
        return
    for p in partidas:
        data = p["utcDate"][:10]
        casa = p["homeTeam"]["name"]
        fora = p["awayTeam"]["name"]
        print(f"{data}: {casa} x {fora}")

# =============================
# Execução
# =============================
if __name__ == "__main__":
    partidas_hoje = buscar_partidas_dia(COMPETITIONS)
    partidas_filtradas = filtrar_partidas_mais_1_5(partidas_hoje)
    mostrar_partidas(partidas_filtradas)
