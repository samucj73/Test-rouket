# Fute.py
import streamlit as st
import requests
from datetime import date

# =============================
# Configurações
# =============================
BASE_URL = "https://api.football-data.org/v4"
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"  # sua chave real
HEADERS = {"X-Auth-Token": API_TOKEN}

# =============================
# Funções auxiliares com CACHE
# =============================
@st.cache_data(ttl=60)  # mantém o cache por 60s
def listar_competicoes():
    url = f"{BASE_URL}/competitions"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return {"erro": f"Erro {r.status_code}: {r.text}"}
    return r.json()

@st.cache_data(ttl=60)
def listar_partidas(codigo, data_escolhida=None):
    url = f"{BASE_URL}/competitions/{codigo}/matches"
    if data_escolhida:
        url += f"?dateFrom={data_escolhida}&dateTo={data_escolhida}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return {"erro": f"Erro {r.status_code}: {r.text}"}
    return r.json()

# =============================
# App Streamlit
# =============================
st.title("⚽ Futebol - Dados em Tempo Real")

st.subheader("📋 Competições disponíveis")
dados_comp = listar_competicoes()

if "erro" in dados_comp:
    st.error(f"❌ {dados_comp['erro']}")
else:
    competicoes = []
    for comp in dados_comp.get("competitions", []):
        competicoes.append({
            "id": comp["id"],
            "nome": comp["name"],
            "codigo": comp.get("code", "N/A"),
            "area": comp.get("area", {}).get("name", "N/A"),
        })

    if competicoes:
        nomes = [f"{c['nome']} ({c['codigo']}) - {c['area']}" for c in competicoes]
        selecao = st.selectbox("Selecione uma competição:", nomes)

        if selecao:
            codigo = selecao.split("(")[1].split(")")[0]

            # Escolher data
            data_escolhida = st.date_input("Escolha a data:", value=date.today())
            data_formatada = data_escolhida.strftime("%Y-%m-%d")

            st.write(f"🔍 Buscando partidas para **{codigo}** em {data_formatada}...")

            dados_partidas = listar_partidas(codigo, data_formatada)

            if "erro" in dados_partidas:
                st.error(f"❌ {dados_partidas['erro']}")
            else:
                partidas = dados_partidas.get("matches", [])
                if partidas:
                    for p in partidas:
                        st.write(f"**{p['homeTeam']['name']} vs {p['awayTeam']['name']}**")
                        st.write(f"📅 {p['utcDate']}")
                        st.write(f"🏆 Status: {p['status']}")
                        st.write("---")
                else:
                    st.warning("⚠️ Nenhum jogo encontrado nessa data.")
    else:
        st.warning("⚠️ Nenhuma competição encontrada.")
