import streamlit as st
import requests

TOKEN = "seu_token_aqui"
res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
st.json(res.json())
