import streamlit as st
import json
import os

USUARIOS_FILE = "usuarios.json"
LIBERADOS_FILE = "liberados.json"

st.set_page_config(page_title="Painel de Liberação", layout="wide")
st.title("🔐 Painel de Liberação de Acesso - Canal Sinais VIP")

def carregar_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []

def salvar_json(dados, path):
    with open(path, "w") as f:
        json.dump(dados, f, indent=2)

usuarios = carregar_json(USUARIOS_FILE)
liberados = carregar_json(LIBERADOS_FILE)

usuarios_nao_liberados = [u for u in usuarios if u["id"] not in liberados]

st.subheader("Usuários aguardando liberação")
if not usuarios_nao_liberados:
    st.success("Nenhum usuário aguardando.")
else:
    for usuario in usuarios_nao_liberados:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"👤 {usuario['nome']} (ID: `{usuario['id']}`)")
        with col2:
            if st.button("✅ Liberar", key=usuario["id"]):
                liberados.append(usuario["id"])
                salvar_json(liberados, LIBERADOS_FILE)
                st.success(f"✅ {usuario['nome']} foi liberado.")
