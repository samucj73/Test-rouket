import streamlit as st
import requests
from datetime import date

BASE_URL = "https://api.football-data.org/v4"
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_TOKEN}

# =============================
# Funções auxiliares com CACHE
# =============================
@st.cache_data(ttl=60)
def listar_competicoes():
    url = f"{BASE_URL}/competitions"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return {"erro": f"Erro {r.status_code}: {r.text}"}
    return r.json()

@st.cache_data(ttl=60)
def listar_partidas(codigo, data_escolhida=None, status=None):
    url = f"{BASE_URL}/competitions/{codigo}/matches"
    params = {}
    if data_escolhida:
        params["dateFrom"] = data_escolhida
        params["dateTo"] = data_escolhida
    if status:
        params["status"] = status
    r = requests.get(url, headers=HEADERS, params=params)
    if r.status_code != 200:
        return {"erro": f"Erro {r.status_code}: {r.text}"}
    return r.json().get("matches", [])

@st.cache_data(ttl=60)
def historico_time(time_id, limite=10):
    url = f"{BASE_URL}/teams/{time_id}/matches?status=FINISHED&limit={limite}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return {"erro": f"Erro {r.status_code}: {r.text}"}
    return r.json().get("matches", [])

def calcular_mais_menos_gols_avancado(home_id, away_id, linha_gols=2.5, limite=10):
    home_historico = historico_time(home_id, limite)
    away_historico = historico_time(away_id, limite)

    if not home_historico or not away_historico:
        return "Não foi possível calcular"

    def media_gols(matches, time_id):
        gols_marcados = 0
        gols_sofridos = 0
        for m in matches:
            ht_id = m["homeTeam"]["id"]
            at_id = m["awayTeam"]["id"]
            score = m["score"]["fullTime"]
            if ht_id == time_id:  # time jogou em casa
                gols_marcados += score["home"]
                gols_sofridos += score["away"]
            elif at_id == time_id:  # time jogou fora
                gols_marcados += score["away"]
                gols_sofridos += score["home"]
        n = max(1, len(matches))
        return gols_marcados/n, gols_sofridos/n

    home_marcados, home_sofridos = media_gols(home_historico, home_id)
    away_marcados, away_sofridos = media_gols(away_historico, away_id)

    gols_esperados = (home_marcados + away_sofridos + away_marcados + home_sofridos)/2

    if gols_esperados > linha_gols:
        return f"Mais de {linha_gols} gols 🟢 (esperado: {gols_esperados:.1f})"
    else:
        return f"Menos de {linha_gols} gols 🔴 (esperado: {gols_esperados:.1f})"

# =============================
# App Streamlit
# =============================
st.set_page_config(page_title="Futebol - Mais/Menos Gols", layout="centered")
st.title("⚽ Futebol - Mais/Menos Gols (Robusto)")

# Seleção de data
data_escolhida = st.date_input("Escolha a data:", value=date.today())
data_formatada = data_escolhida.strftime("%Y-%m-%d")

# Seleção de status
status_selecionado = st.selectbox("Status da partida:", ["SCHEDULED", "LIVE", "FINISHED"], index=0)

# Listar competições que têm partidas nessa data
dados_comp = listar_competicoes()
competicoes_disponiveis = []

if "erro" in dados_comp:
    st.error(f"❌ {dados_comp['erro']}")
else:
    for c in dados_comp.get("competitions", []):
        matches = listar_partidas(c.get("code",""), data_formatada, status_selecionado)
        if matches:  # só adiciona se houver partidas
            competicoes_disponiveis.append({"nome": c["name"], "codigo": c.get("code","")})

if not competicoes_disponiveis:
    st.warning("⚠️ Nenhuma competição com partidas disponíveis nessa data.")
else:
    nomes = [f"{c['nome']} ({c['codigo']})" for c in competicoes_disponiveis]
    selecao = st.selectbox("Selecione uma competição:", nomes)

    if selecao:
        codigo = selecao.split("(")[1].split(")")[0]

        # Linha de gols
        linha_gols = st.number_input("Linha de gols (ex: 2.5):", min_value=0.0, max_value=10.0,
                                     value=2.5, step=0.1)

        # Buscar partidas filtradas
        partidas = listar_partidas(codigo, data_formatada, status_selecionado)
        if not partidas:
            st.warning("⚠️ Nenhum jogo encontrado para os filtros selecionados.")
        else:
            for p in partidas:
                home_id = p["homeTeam"]["id"]
                away_id = p["awayTeam"]["id"]
                sugestao = calcular_mais_menos_gols_avancado(home_id, away_id, linha_gols)

                st.write(f"**{p['homeTeam']['name']} vs {p['awayTeam']['name']}**")
                st.write(f"📅 {p['utcDate']}")
                st.write(f"🏆 Status: {p['status']}")
                st.write(f"💡 Sugestão: {sugestao}")
                st.write("---")
