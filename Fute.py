import streamlit as st
import requests

API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.title("Teste API-Football")

url = f"{BASE_URL}/leagues"
response = requests.get(url, headers=HEADERS)

st.write("Status code:", response.status_code)
st.write("JSON retornado:", response.json())
