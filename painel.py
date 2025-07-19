import streamlit as st
import json
import requests

TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
CANAL_ID = "-1002796136111"
USUARIOS_JSON = "usuarios_autorizados.json"

def carregar_usuarios():
    try:
        with open(USUARIOS_JSON, "r") as f:
            return json.load(f)
    except:
        return []

st.title("🔐 Painel de Liberação - Canal Sinais VIP")

usuarios = carregar_usuarios()
for uid in usuarios:
    col1, col2 = st.columns([3,1])
    col1.write(f"Usuário `{uid}`")
    if col2.button("Liberar", key=str(uid)):
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/addChatMember",
            json={"chat_id": CANAL_ID, "user_id": int(uid)}
        )
        if resp.ok:
            st.success(f"Acesso concedido a {uid}")
        else:
            st.error(f"Erro com {uid}: {resp.text}")
