import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os

# =============================
# Configurações API Football-Data.org
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"

# =============================
# Persistência de alertas
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

# =============================
# Envio de alertas Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})
    except:
        pass

def enviar_alerta_telegram(fixture, tendencia, estimativa, confianca):
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_iso = fixture["utcDate"]
    data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
    data_formatada = data_jogo.strftime("%d/%m/%Y")
    hora_formatada = data_jogo.strftime("%H:%M")
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")

    # Status e placar
    status = fixture.get("status", "DESCONHECIDO")
    gols_home = fixture.get("score", {}).get("fullTime", {}).get("home")
    gols_away = fixture.get("score", {}).get("fullTime", {}).get("away")
    placar = None
    if gols_home is not None and gols_away is not None:
        placar = f"{gols_home} x {gols_away}"

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"📌 Status: {status}\n"
    )
    if placar:
        msg += f"📊 Placar: {placar}\n"
    msg += (
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Liga: {competicao}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    precisa_enviar = fixture_id not in alertas
    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca
        }
        salvar_alertas(alertas)

# =============================
# Funções de API Football-Data
# =============================
def obter_ligas():
    try:
        url = f"{BASE_URL_FD}/competitions"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json().get("competitions", [])
    except:
        st.error("Erro ao obter ligas")
        return []

def obter_classificacao(liga_id):
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        standings = {}
        for s in data.get("standings", []):
            if s["type"] != "TOTAL":
                continue
            for t in s["table"]:
                name = t["team"]["name"]
                gols_marcados = t.get("goalsFor", 0)
                gols_sofridos = t.get("goalsAgainst", 0)
                partidas = t.get("playedGames", 1)
                standings[name] = {
                    "scored": gols_marcados,
                    "against": gols_sofridos,
                    "played": partidas
                }
        return standings
    except:
        st.error(f"Erro ao obter classificação da liga {liga_id}")
        return {}

def obter_jogos(liga_id, data):
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except:
        st.error(f"Erro ao obter jogos da liga {liga_id}")
        return []

# =============================
# Cálculo tendência
# =============================
def calcular_tendencia(home, away, classificacao):
    dados_home = classificacao.get(home, {"scored":0, "against":0, "played":1})
    dados_away = classificacao.get(away, {"scored":0, "against":0, "played":1})

    # Médias por jogo
    media_home_feitos = dados_home["scored"] / dados_home["played"]
    media_home_sofridos = dados_home["against"] / dados_home["played"]

    media_away_feitos = dados_away["scored"] / dados_away["played"]
    media_away_sofridos = dados_away["against"] / dados_away["played"]

    # Estimativa ataque vs defesa
    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    # Tendência
    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0)*10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0)*10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa)*10)

    return estimativa, confianca, tendencia

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")

# Data
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

# Checkbox para buscar todas ligas
#todas_ligas = st.checkbox("📌 Buscar jogos de todas as ligas do dia", value=True)
# =============================
# Seleção de Liga
# =============================
todas_ligas = st.checkbox("Buscar em todas as ligas", value=False)
liga_selecionada = st.selectbox("Selecione a Liga", list(liga_dict.keys()))

if todas_ligas:
    ligas_busca = list(liga_dict.values())
else:
    ligas_busca = [liga_dict.get(liga_selecionada)] if liga_dict.get(liga_selecionada) else []
    if not ligas_busca:
        st.warning("⚠️ Liga selecionada não encontrada. Escolha outra.")

# Obter ligas
ligas = obter_ligas()
liga_dict = {liga["name"]: liga["id"] for liga in ligas}

liga_selecionada = None
if not todas_ligas:
    liga_selecionada = st.selectbox("📌 Escolha a liga:", list(liga_dict.keys()))

# Botão para iniciar pesquisa
if st.button("🔍 Buscar partidas"):
    ligas_busca = liga_dict.values() if todas_ligas else [liga_dict[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {data_selecionada}...")

    top_jogos = []

    for liga_id in ligas_busca:
        classificacao = obter_classificacao(liga_id)
        jogos = obter_jogos(liga_id, hoje)

        for match in jogos:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            status = match.get("status", "DESCONHECIDO")

            gols_home = match.get("score", {}).get("fullTime", {}).get("home")
            gols_away = match.get("score", {}).get("fullTime", {}).get("away")
            placar = None
            if gols_home is not None and gols_away is not None:
                placar = f"{gols_home} x {gols_away}"

            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)

            verificar_enviar_alerta(match, tendencia, estimativa, confianca)

            top_jogos.append({
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": datetime.fromisoformat(match["utcDate"].replace("Z","+00:00"))-timedelta(hours=3),
                "status": status,
                "placar": placar
            })

    # Ordenar top 3 por confiança
    top_jogos_sorted = sorted(top_jogos, key=lambda x: x["confianca"], reverse=True)[:3]

    if top_jogos_sorted:
        msg = "📢 TOP 3 Jogos do Dia\n\n"
        for j in top_jogos_sorted:
            hora_format = j["hora"].strftime("%H:%M")
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
            )
            if j["placar"]:
                msg += f"📊 Placar: {j['placar']}\n"
            msg += (
                f"Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
                f"Confiança: {j['confianca']:.0f}%\n\n"
            )
        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
        st.success("🚀 Top 3 jogos enviados para o canal alternativo 2!")

    st.info("✅ Busca finalizada.")

# =============================
# =============================
# Conferência dos resultados
# =============================
st.subheader("📊 Conferência dos Resultados")

if st.button("🔍 Conferir agora"):
    alertas = carregar_alertas()
    resultados = []

    for fixture_id, info in alertas.items():
        url = f"{BASE_URL_FD}/matches/{fixture_id}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            match = resp.json()

            status = match.get("status", "DESCONHECIDO")
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]

            gols_home = match.get("score", {}).get("fullTime", {}).get("home")
            gols_away = match.get("score", {}).get("fullTime", {}).get("away")
            total_gols = (gols_home or 0) + (gols_away or 0)

            resultado = "-"
            if status == "FINISHED":
                tendencia = info["tendencia"]

                if tendencia == "Mais 2.5":
                    resultado = "🟢 GREEN" if total_gols > 2 else "🔴 RED"
                elif tendencia == "Mais 1.5":
                    resultado = "🟢 GREEN" if total_gols > 1 else "🔴 RED"
                elif tendencia == "Menos 2.5":
                    resultado = "🟢 GREEN" if total_gols < 3 else "🔴 RED"

            resultados.append({
                "Jogo": f"{home} vs {away}",
                "Tendência": info["tendencia"],
                "Estimativa": f"{info['estimativa']:.2f}",
                "Confiança": f"{info['confianca']:.0f}%",
                "Placar": f"{gols_home} x {gols_away}" if gols_home is not None else "-",
                "Status": status,
                "Resultado": resultado
            })

        except:
            continue

    if resultados:
        for r in resultados:
            # Fundo escuro com destaque
            if r["Resultado"] == "🟢 GREEN":
                bg_color = "#1e4620"   # verde escuro
            elif r["Resultado"] == "🔴 RED":
                bg_color = "#5a1e1e"   # vermelho escuro
            else:
                bg_color = "#2c2c2c"   # cinza escuro

            st.markdown(f"""
            <div style="border:1px solid #444; border-radius:10px; padding:12px; margin-bottom:10px;
                        background-color:{bg_color}; font-size:15px; color:#f1f1f1;">
                <b>🏟️ {r['Jogo']}</b><br>
                📌 Status: <b>{r['Status']}</b><br>
                ⚽ Tendência: <b>{r['Tendência']}</b> | Estim.: {r['Estimativa']} | Conf.: {r['Confiança']}<br>
                📊 Placar: <b>{r['Placar']}</b><br>
                ✅ Resultado: {r['Resultado']}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Ainda não há resultados para conferir.")
