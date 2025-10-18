import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# =====================================
# ⚽ CONFIGURAÇÕES GERAIS
# =====================================
st.set_page_config(page_title="⚽ API MLS - Elite", layout="wide")
st.title("⚽ API MLS - Elite Master")

st.markdown("""
Esta API coleta automaticamente os **dados mais recentes da MLS (Major League Soccer)** diretamente da ESPN,
atualizando automaticamente a cada **15 minutos**, sem apps externos.
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
            placar_casa = placares[0].text.strip() if len(placares) >= 1 else "-"
            placar_fora = placares[1].text.strip() if len(placares) >= 2 else "-"

            status = bloco.find("span", class_="sb-status-text")
            status_text = status.text.strip() if status else "Agendado"

            hora = bloco.find("span", class_="sb-date-time")
            hora_text = hora.text.strip() if hora else "-"

            partidas.append({
                "Casa": time_casa,
                "Fora": time_fora,
                "Placar Casa": placar_casa,
                "Placar Fora": placar_fora,
                "Status": status_text,
                "Horário": hora_text
            })

        return pd.DataFrame(partidas) if partidas else None

    except Exception as e:
        st.error(f"Erro ao buscar dados da MLS (ESPN): {e}")
        return None

# =====================================
# ⏰ ATUALIZAÇÃO AUTOMÁTICA (a cada 15 minutos)
# =====================================
from streamlit_autorefresh import st_autorefresh

# Atualiza a cada 15 minutos (900 segundos)
contador = st_autorefresh(interval=15 * 60 * 1000, key="auto_refresh")

if "dados_mls" not in st.session_state or contador == 0:
    st.session_state["dados_mls"] = buscar_partidas_mls()
    st.session_state["ultimo_update"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

dados = st.session_state.get("dados_mls")
ultima = st.session_state.get("ultimo_update")

# =====================================
# 🧾 EXIBIÇÃO
# =====================================
if dados is not None:
    st.markdown(f"🕒 **Última atualização:** {ultima} | Atualização automática a cada 15 minutos.")
    st.dataframe(dados, use_container_width=True)
else:
    st.warning("Nenhum dado disponível. Aguarde a atualização automática.")

st.markdown("---")
st.markdown("✅ Atualização automática em segundo plano habilitada.")
