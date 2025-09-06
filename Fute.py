import streamlit as st
import requests
from datetime import datetime

st.title("Teste rápido da API Football")

API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# Seleção da data
data_selecionada = st.date_input("Escolha a data para testar a API", value=datetime.today())
data_formatada = data_selecionada.strftime("%Y-%m-%d")

if st.button("Testar API"):
    url = f"{BASE_URL}/fixtures?date={data_formatada}"
    response = requests.get(url, headers=HEADERS)

    st.write("Status code:", response.status_code)

    if response.status_code == 200:
        data = response.json()
        st.write("Chaves principais do JSON:", list(data.keys()))
        if data["response"]:
            st.write("Exemplo de 1ª partida retornada:")
            st.json(data["response"][0])
        else:
            st.info("Nenhum jogo encontrado para esta data.")
    else:
        st.error(f"Erro: {response.text}")
