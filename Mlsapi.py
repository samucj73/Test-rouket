import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
from bs4 import BeautifulSoup

# =====================================
# ⚽ CONFIGURAÇÕES GERAIS
# =====================================
st.set_page_config(page_title="⚽ API MLS - Elite", layout="wide")
st.title("⚽ API MLS - Elite Master")

st.markdown("""
Esta API coleta automaticamente os **dados mais recentes da MLS (Major League Soccer)** diretamente da ESPN,
atualizando automaticamente a cada **15 minutos**, sem necessidade de apps externos.
""")

# =====================================
# 🔄 FUNÇÃO PARA RASPAGEM DA ESPN
# =====================================
def buscar_partidas_mls():
    try:
        url = "https://www.espn.com/soccer/scoreboard/_/league/usa.1"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")

        partidas = []

        blocos = soup.find_all("section", class_="Scoreboard")
        for bloco in blocos:
            equipes = bloco.find_all("span", class_="sb-team-short")
            if len(equipes) != 2:
                continue

            time_casa = equipes[0].text.strip()
            time_fora = equipes[1].text.strip()

            placares = bloco.find_all("span", class_="sb-team-score")
            if len(placares) == 2:
                placar_casa = placares[0].text.strip()
                placar_fora = placares[1].text.strip()
            else:
                placar_casa = placar_fora = "-"

            status = bloco.find("span", class_="sb-status-text").text.strip() if bloco.find("span", class_="sb-status-text") else "Agendado"
            hora = bloco.find("span", class_="sb-date-time").text.strip() if bloco.find("span", class_="sb-date-time") else "-"

            partidas.append({
                "Casa": time_casa,
                "Fora": time_fora,
                "Placar Casa": placar_casa,
                "Placar Fora": placar_fora,
                "Status": status,
                "Horário": hora
            })

        df = pd.DataFrame(partidas)
        return df if not df.empty else None

    except Exception as e:
        st.error(f"Erro ao buscar dados da MLS (ESPN): {e}")
        return None

# =====================================
# ⏰ ATUALIZAÇÃO AUTOMÁTICA
# =====================================
ATUALIZACAO_INTERVALO = 15 * 60  # 15 minutos

if "ultimo_update" not in st.session_state:
    st.session_state["ultimo_update"] = None

if "dados_mls" not in st.session_state:
    st.session_state["dados_mls"] = None

def atualizar_dados():
    st.session_state["dados_mls"] = buscar_partidas_mls()
    st.session_state["ultimo_update"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

# =====================================
# 🚀 EXECUÇÃO
# =====================================
if st.button("🔄 Atualizar agora"):
    atualizar_dados()

if st.session_state["dados_mls"] is None:
    atualizar_dados()

dados = st.session_state["dados_mls"]
ultima = st.session_state["ultimo_update"]

if dados is not None:
    st.markdown(f"🕒 **Última atualização:** {ultima} | Próxima em 15 minutos automaticamente.")
    st.dataframe(dados, use_container_width=True)
else:
    st.warning("Nenhum dado disponível. Aguarde a atualização automática.")

# =====================================
# ♻️ LOOP DE ATUALIZAÇÃO AUTOMÁTICA
# =====================================
st.markdown("---")
st.markdown("⏳ Atualização automática em segundo plano...")

with st.empty():
    while True:
        time.sleep(ATUALIZACAO_INTERVALO)
        atualizar_dados()
        st.rerun()
