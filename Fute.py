# Fute.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações API TheSportsDB
# =============================
API_KEY = "123"  # substitua pela sua chave real
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# =============================
# Função para buscar eventos por data
# =============================
def buscar_eventos_por_data(data, esporte="Soccer"):
    url = f"{BASE_URL}/eventsday.php"
    params = {"d": data, "s": esporte}
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        dados = resp.json()
        return dados.get("events", [])
    except Exception as e:
        st.error(f"Erro ao buscar eventos: {e}")
        return []

# =============================
# Interface Streamlit
# =============================
st.title("⚽ Alertas de Jogos - TheSportsDB")
st.markdown("Selecione a data para ver os jogos de futebol:")

# Seleção de data
data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Buscar eventos
eventos = buscar_eventos_por_data(data_str, esporte="Soccer")

if not eventos:
    st.warning(f"Não há jogos registrados para {data_str}.")
else:
    st.success(f"🔎 Foram encontrados {len(eventos)} eventos para {data_str}:")
    for e in eventos:
        # Garantindo fallback para evitar erro
        home = e.get("strHomeTeam") or e.get("homeTeam") or "Desconhecido"
        away = e.get("strAwayTeam") or e.get("awayTeam") or "Desconhecido"
        hora = e.get("strTime") or e.get("strTimestamp") or "??:??"
        competicao = e.get("strLeague") or e.get("strCompetition") or "Competição desconhecida"
        logo_home = e.get("strHomeTeamBadge") or ""
        logo_away = e.get("strAwayTeamBadge") or ""

        # Layout bonitinho com colunas
        cols = st.columns([1,3,1])
        with cols[0]:
            if logo_home:
                st.image(logo_home, width=40)
            st.write(home)
        with cols[1]:
            st.write(f"**{hora}** | {competicao} | {home} x {away}")
        with cols[2]:
            if logo_away:
                st.image(logo_away, width=40)
            st.write(away)

        st.markdown("---")
