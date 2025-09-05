import streamlit as st
import requests
import pandas as pd

# =============================
# Configuração da API
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
BASE_URL = "https://api.football-data.org/v4"
headers = {"X-Auth-Token": API_KEY}

# =============================
# Função para buscar competições
# =============================
def listar_competicoes():
    url = f"{BASE_URL}/competitions"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        comps = []
        for comp in data.get("competitions", []):
            plan = comp.get("plan")
            # Verifica se plan existe e é dict antes de acessar "name"
            if isinstance(plan, dict):
                plan_name = plan.get("name", "N/A")
            else:
                plan_name = "N/A"
            comps.append({
                "Nome": comp.get("name", "N/A"),
                "Código": comp.get("code", "N/A"),
                "ID": comp.get("id", "N/A"),
                "Nível": plan_name
            })
        return comps
    else:
        st.error(f"Erro ao buscar competições: {r.status_code}")
        return []

# =============================
# Estilo visual (CSS)
# =============================
st.markdown("""
    <style>
    .block-container {
        max-width: 900px;
        margin: auto;
        padding-top: 2rem;
        background-color: #0e1117;
        color: white;
    }
    h1 { text-align: center; color: #1DB954; }
    table { color: white; }
    </style>
""", unsafe_allow_html=True)

# =============================
# Interface Streamlit
# =============================
st.title("⚽ Ligas Disponíveis - Football-Data.org")

competicoes = listar_competicoes()
if competicoes:
    df = pd.DataFrame(competicoes)
    st.subheader("✅ Competições que você pode usar")
    st.dataframe(df, use_container_width=True)
else:
    st.info("Nenhuma competição encontrada.")
