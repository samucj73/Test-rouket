import streamlit as st
import requests
from datetime import date

BASE_URL = "https://api.football-data.org/v4"
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_TOKEN}

# =============================
# Funções auxiliares com CACHE
# =============================
@st.cache_data(ttl=60)
def listar_competicoes():
    try:
        r = requests.get(f"{BASE_URL}/competitions", headers=HEADERS)
        r.raise_for_status()
        return r.json().get("competitions", [])
    except Exception as e:
        return {"erro": str(e)}

@st.cache_data(ttl=60)
def listar_partidas(codigo, data_escolhida=None, status=None):
    try:
        url = f"{BASE_URL}/competitions/{codigo}/matches"
        params = {}
        if data_escolhida:
            params["dateFrom"] = data_escolhida
            params["dateTo"] = data_escolhida
        if status:
            params["status"] = status
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception as e:
        return {"erro": str(e)}

@st.cache_data(ttl=60)
def historico_time(time_id, limite=10):
    try:
        r = requests.get(f"{BASE_URL}/teams/{time_id}/matches?status=FINISHED&limit={limite}", headers=HEADERS)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception:
        return []

# =============================
# Cálculo avançado de Mais/Menos gols
# =============================
def calcular_mais_menos_gols_avancado(home_id, away_id, linha_gols=2.5, limite=10):
    home_historico = historico_time(home_id, limite)
    away_historico = historico_time(away_id, limite)

    if not home_historico or not away_historico:
        return "Não foi possível calcular (sem histórico suficiente)"

    def media_gols(matches, time_id):
        gols_marcados, gols_sofridos, cont = 0, 0, 0
        for m in matches:
            if not isinstance(m, dict):
                continue
            ht = m.get("homeTeam", {})
            at = m.get("awayTeam", {})
            score = m.get("score", {}).get("fullTime", {})
            if not ht or not at or not score:
                continue
            ht_id = ht.get("id")
            at_id = at.get("id")
            if not ht_id or not at_id:
                continue
            if ht_id == time_id:
                gols_marcados += score.get("home", 0)
                gols_sofridos += score.get("away", 0)
            elif at_id == time_id:
                gols_marcados += score.get("away", 0)
                gols_sofridos += score.get("home", 0)
            cont += 1
        if cont == 0:
            return 0, 0
        return gols_marcados/cont, gols_sofridos/cont

    home_marcados, home_sofridos = media_gols(home_historico, home_id)
    away_marcados, away_sofridos = media_gols(away_historico, away_id)

    gols_esperados = (home_marcados + away_sofridos + away_marcados + home_sofridos)/2

    if gols_esperados > linha_gols:
        return f"Mais de {linha_gols} gols 🟢 (esperado: {gols_esperados:.1f})"
    else:
        return f"Menos de {linha_gols} gols 🔴 (esperado: {gols_esperados:.1f})"

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="Futebol - Mais/Menos Gols", layout="centered")
st.title("⚽ Futebol - Mais/Menos Gols (Segurança Total)")

# Seleção de data
data_escolhida = st.date_input("Escolha a data:", value=date.today())
data_formatada = data_escolhida.strftime("%Y-%m-%d")

# Status da partida
status_selecionado = st.selectbox("Status da partida:", ["SCHEDULED", "LIVE", "FINISHED"], index=0)

# Listar competições com partidas disponíveis
competicoes_disponiveis = []
dados_comp = listar_competicoes()

if isinstance(dados_comp, dict) and dados_comp.get("erro"):
    st.error(f"❌ {dados_comp['erro']}")
elif not dados_comp:
    st.warning("⚠️ Nenhuma competição disponível na API.")
else:
    for c in dados_comp:
        codigo = c.get("code", "")
        partidas = listar_partidas(codigo, data_formatada, status_selecionado)
        if isinstance(partidas, list) and partidas:
            competicoes_disponiveis.append({"nome": c.get("name","Desconhecido"), "codigo": codigo})

    if not competicoes_disponiveis:
        st.warning("⚠️ Nenhuma competição com partidas disponíveis nessa data.")
    else:
        nomes = [f"{c['nome']} ({c['codigo']})" for c in competicoes_disponiveis]
        selecao = st.selectbox("Selecione uma competição:", nomes)

        if selecao:
            codigo = selecao.split("(")[1].split(")")[0]

            linha_gols = st.number_input("Linha de gols (ex: 2.5):", min_value=0.0, max_value=10.0,
                                         value=2.5, step=0.1)

            partidas = listar_partidas(codigo, data_formatada, status_selecionado)
            if not isinstance(partidas, list) or not partidas:
                st.warning("⚠️ Nenhum jogo encontrado para os filtros selecionados.")
            else:
                for p in partidas:
                    if not isinstance(p, dict):
                        continue
                    home = p.get("homeTeam")
                    away = p.get("awayTeam")
                    if not home or not away:
                        continue
                    home_id = home.get("id")
                    away_id = away.get("id")
                    if not home_id or not away_id:
                        continue
                    sugestao = calcular_mais_menos_gols_avancado(home_id, away_id, linha_gols)
                    st.write(f"**{home.get('name','Desconhecido')} vs {away.get('name','Desconhecido')}**")
                    st.write(f"📅 {p.get('utcDate','-')}")
                    st.write(f"🏆 Status: {p.get('status','-')}")
                    st.write(f"💡 Sugestão: {sugestao}")
                    st.write("---")
