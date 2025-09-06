import streamlit as st
import requests

API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.title("Ligas da API-Football")

# Busca ligas
url = f"{BASE_URL}/leagues"
response = requests.get(url, headers=HEADERS)

if response.status_code == 200:
    data = response.json()["response"]
    # Cria uma lista com ID e nome da liga
    ligas = [{"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]} for l in data]
    st.write(f"Total de ligas: {len(ligas)}")
    st.dataframe(ligas)
else:
    st.error(f"Erro {response.status_code}: {response.text}")
