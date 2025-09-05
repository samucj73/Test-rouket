# Fute.py
import streamlit as st
import requests

# =============================
# Configurações
# =============================
BASE_URL = "https://api.football-data.org/v4"
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"  # sua chave real
HEADERS = {"X-Auth-Token": API_TOKEN}

# =============================
# Funções auxiliares
# =============================
def listar_competicoes():
    url = f"{BASE_URL}/competitions"
    r = requests.get(url, headers=HEADERS)

    # Debug para mostrar o erro da API
    if r.status_code != 200:
        st.error(f"❌ Erro {r.status_code}: {r.text}")
        return []

    data = r.json()
    competicoes = []
    for comp in data.get("competitions", []):
        competicoes.append({
            "id": comp["id"],
            "nome": comp["name"],
            "codigo": comp.get("code", "N/A"),
            "area": comp.get("area", {}).get("name", "N/A"),
        })
    return competicoes

def listar_partidas(codigo):
    url = f"{BASE_URL}/competitions/{codigo}/matches"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        st.error(f"❌ Erro {r.status_code}: {r.text}")
        return []

    data = r.json()
    return data.get("matches", [])

# =============================
# App Streamlit
# =============================
st.title("⚽ Futebol - Dados em Tempo Real")

st.subheader("📋 Competições disponíveis")
competicoes = listar_competicoes()

if competicoes:
    nomes = [f"{c['nome']} ({c['codigo']}) - {c['area']}" for c in competicoes]
    selecao = st.selectbox("Selecione uma competição:", nomes)

    if selecao:
        codigo = selecao.split("(")[1].split(")")[0]
        st.write(f"🔍 Buscando partidas para **{codigo}**...")

        partidas = listar_partidas(codigo)

        if partidas:
            for p in partidas:
                st.write(f"**{p['homeTeam']['name']} vs {p['awayTeam']['name']}**")
                st.write(f"📅 {p['utcDate']}")
                st.write(f"🏆 Status: {p['status']}")
                st.write("---")
        else:
            st.warning("⚠️ Nenhuma partida disponível para esta liga.")
else:
    st.warning("⚠️ Não foi possível carregar as competições. Verifique sua API Key.")
