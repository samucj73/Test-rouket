# ================================
# 📊 API MLS - Elite
# ================================
import streamlit as st
import requests
from datetime import datetime
import time

st.set_page_config(page_title="⚽ API MLS - Elite", page_icon="⚽", layout="wide")

st.title("⚽ API MLS - Elite")
st.caption("Fonte: ESPN | Atualização automática a cada 15 minutos")

# ==================================
# Função para buscar dados da ESPN
# ==================================
def buscar_dados_mls():
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dados = response.json()
        partidas = []

        for evento in dados.get("events", []):
            nome = evento.get("name", "")
            status = evento.get("status", {}).get("type", {}).get("description", "")
            hora = evento.get("date", "")
            hora_formatada = (
                datetime.fromisoformat(hora.replace("Z", "+00:00"))
                .strftime("%d/%m/%Y %H:%M")
                if hora
                else ""
            )

            competicao = evento.get("competitions", [])[0]
            times = competicao.get("competitors", [])

            if len(times) == 2:
                home = times[0]["team"]["displayName"]
                away = times[1]["team"]["displayName"]
                placar_home = times[0].get("score", "-")
                placar_away = times[1].get("score", "-")
            else:
                home = away = placar_home = placar_away = "-"

            partidas.append({
                "Jogo": nome,
                "Mandante": home,
                "Visitante": away,
                "Placar": f"{placar_home} - {placar_away}",
                "Status": status,
                "Horário": hora_formatada
            })

        return partidas

    except Exception as e:
        st.error(f"Erro ao buscar dados da MLS: {e}")
        return []


# ==================================
# Interface Streamlit
# ==================================
atualizacao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
st.markdown(f"🕒 **Última atualização:** {atualizacao} | Atualização automática a cada 15 minutos.")

partidas = buscar_dados_mls()

if partidas:
    st.dataframe(partidas, use_container_width=True)
else:
    st.warning("Nenhum dado disponível no momento. Aguarde a atualização automática.")

# ==================================
# Atualização automática
# ==================================
with st.empty():
    while True:
        time.sleep(900)  # 15 minutos
        st.rerun()
