# soccer_api.py
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# ===============================
# ⚙️ Configurações gerais
# ===============================
app = FastAPI(title="Soccer API - Elite Master")
CACHE_DIR = "cache"
DIAS_FUTUROS = 2
DIAS_PASSADOS = 7
ANOS_HISTORICOS = range(2005, datetime.utcnow().year + 1)

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# ===============================
# 🔗 Principais ligas
# ===============================
LIGAS = {
    "MLS (EUA)": "usa.1",
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "Primeira Liga (Portugal)": "por.1",
    "Brasileirão Série A": "bra.1",
    "Argentinian Primera División": "arg.1",
    "Campeonato Chileno": "chi.1",
    "Campeonato Colombiano": "col.1",
}

# ===============================
# 💾 Funções de cache
# ===============================
def cache_file(liga_code, ano):
    return os.path.join(CACHE_DIR, f"{liga_code}_{ano}.json")

def salvar_cache(liga_code, ano, dados):
    with open(cache_file(liga_code, ano), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_cache(liga_code, ano):
    caminho = cache_file(liga_code, ano)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ===============================
# 🧠 Buscar dados da ESPN
# ===============================
def buscar_dados(liga_code, data_str):
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={data_str}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        partidas = []

        for event in data.get("events", []):
            comp = event.get("competitions", [{}])[0]
            status = comp.get("status", {}).get("type", {}).get("description", "")
            horario_utc = comp.get("date", "")
            horario_local = (
                datetime.fromisoformat(horario_utc.replace("Z", "+00:00")) - timedelta(hours=3)
            ).strftime("%Y-%m-%d %H:%M")

            teams = comp.get("competitors", [])
            mandante = visitante = placar_m = placar_v = ""
            mandante_logo = visitante_logo = ""

            for team in teams:
                logo = team.get("team", {}).get("logos", [{}])
                logo_url = logo[0].get("href", "") if logo else ""
                if team.get("homeAway") == "home":
                    mandante = team.get("team", {}).get("shortDisplayName", "")
                    placar_m = team.get("score", "-")
                    mandante_logo = logo_url
                else:
                    visitante = team.get("team", {}).get("shortDisplayName", "")
                    placar_v = team.get("score", "-")
                    visitante_logo = logo_url

            partidas.append({
                "liga": liga_code,
                "mandante": mandante,
                "visitante": visitante,
                "placar_m": placar_m,
                "placar_v": placar_v,
                "mandante_logo": mandante_logo,
                "visitante_logo": visitante_logo,
                "status": status,
                "horario": horario_local
            })
        return partidas
    except Exception as e:
        print(f"Erro {liga_code} {data_str}: {e}")
        return []

# ===============================
# 🔁 Atualização de cache
# ===============================
def atualizar_cache_rapida():
    hoje = datetime.utcnow().date()
    datas = [(hoje - timedelta(days=i)).strftime("%Y%m%d") for i in range(DIAS_PASSADOS,0,-1)] + \
            [hoje.strftime("%Y%m%d")] + \
            [(hoje + timedelta(days=i)).strftime("%Y%m%d") for i in range(1, DIAS_FUTUROS+1)]
    total_partidas = 0
    for liga_name, liga_code in LIGAS.items():
        ano = hoje.year
        novas = []
        for d in datas:
            partidas = buscar_dados(liga_code, d)
            if partidas:
                novas.extend(partidas)
        if novas:
            salvar_cache(liga_code, ano, novas)
            total_partidas += len(novas)
    return total_partidas

# ===============================
# 🔁 Carregar todas partidas
# ===============================
def carregar_todas_partidas():
    todas = []
    for liga_name, liga_code in LIGAS.items():
        for ano in ANOS_HISTORICOS:
            dados = carregar_cache(liga_code, ano)
            if dados:
                todas.extend(dados)
    return todas

# ===============================
# 📌 Endpoint: listar ligas
# ===============================
@app.get("/leagues")
def get_leagues():
    return {"count": len(LIGAS), "leagues": list(LIGAS.keys())}

# ===============================
# 📌 Endpoint: listar partidas
# ===============================
@app.get("/matches")
def get_matches(
    liga: str = Query(None),
    data: str = Query(None),
    time: str = Query(None)
):
    dados = carregar_todas_partidas()
    if liga:
        liga_code = LIGAS.get(liga)
        if liga_code:
            dados = [d for d in dados if d["liga"] == liga_code]
    if data:
        dados = [d for d in dados if d["horario"].startswith(data)]
    if time:
        dados = [d for d in dados if time.lower() in d["mandante"].lower() or time.lower() in d["visitante"].lower()]
    return {"count": len(dados), "matches": dados}

# ===============================
# 📌 Endpoint: partidas futuras
# ===============================
@app.get("/upcoming")
def get_upcoming():
    agora = datetime.utcnow()
    dados = carregar_todas_partidas()
    dados = [d for d in dados if datetime.strptime(d["horario"], "%Y-%m-%d %H:%M") >= agora]
    return {"count": len(dados), "matches": dados}

# ===============================
# 📌 Endpoint: partidas passadas
# ===============================
@app.get("/results")
def get_results():
    agora = datetime.utcnow()
    dados = carregar_todas_partidas()
    dados = [d for d in dados if datetime.strptime(d["horario"], "%Y-%m-%d %H:%M") < agora]
    return {"count": len(dados), "matches": dados}

# ===============================
# 📌 Endpoint: atualizar cache
# ===============================
@app.get("/update")
def update_cache():
    total = atualizar_cache_rapida()
    return {"message": f"Cache atualizado com {total} partidas"}
