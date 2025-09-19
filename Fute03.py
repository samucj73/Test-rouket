import streamlit as st
import requests
from datetime import datetime

# =============================
# Configurações
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"

ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb",
    "Premier League (Inglaterra)": "eng1",
    "La Liga (Espanha)": "esp1",
    "Serie A (Itália)": "ita1",
    "Ligue 1 (França)": "fra1"
}

# Telegram
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        st.error(f"Erro ao enviar para Telegram: {e}")


def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.error(f"Erro ao obter jogos: {e}")
    return []


def calcular_media_gols_time(jogos, nome_time):
    gols = []
    for j in jogos:
        if j.get("matchIsFinished"):
            placar = None
            for r in j.get("matchResults", []):
                if r.get("resultTypeID") == 2:  # resultado final
                    placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                    break
            if placar:
                if j["team1"]["teamName"] == nome_time:
                    gols.append(placar[0])
                elif j["team2"]["teamName"] == nome_time:
                    gols.append(placar[1])
    return sum(gols) / len(gols) if gols else 0


def calcular_media_gols_h2h(jogos, time1, time2):
    gols = []
    for j in jogos:
        if j.get("matchIsFinished"):
            teams = {j["team1"]["teamName"], j["team2"]["teamName"]}
            if time1 in teams and time2 in teams:
                placar = None
                for r in j.get("matchResults", []):
                    if r.get("resultTypeID") == 2:
                        placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                        break
                if placar:
                    gols.append(sum(placar))
    return sum(gols) / len(gols) if gols else 0


def analisar_tendencia_gols(media_home, media_away, media_h2h):
    media_total = (media_home + media_away + media_h2h) / 3
    tendencia = []
    if media_total >= 1.5:
        tendencia.append("+1.5")
    if media_total >= 2.5:
        tendencia.append("+2.5")
    return media_total, tendencia


# =============================
# Streamlit interface
# =============================
st.set_page_config(page_title="📊 Tendência de Gols (OpenLigaDB)", layout="wide")
st.title("📊 Tendências de Gols com base na OpenLigaDB")

temporada = st.selectbox("📅 Escolha a temporada:", ["2022", "2023", "2024", "2025"], index=2)
liga_nome = st.selectbox("🏆 Escolha a Liga:", list(ligas_openliga.keys()))
liga_id = ligas_openliga[liga_nome]

if st.button("🔍 Buscar tendências"):
    with st.spinner("Buscando dados e analisando..."):
        jogos = obter_jogos_liga_temporada(liga_id, temporada)
        if not jogos:
            st.info("Nenhum jogo encontrado para essa temporada/ligue.")
        else:
            st.success(f"{len(jogos)} jogos encontrados na {liga_nome} ({temporada})")

            # separa passados e futuros
            futuros = [j for j in jogos if not j.get("matchIsFinished")]
            passados = [j for j in jogos if j.get("matchIsFinished")]

            if not futuros:
                st.warning("Nenhum jogo futuro encontrado.")
            else:
                for j in futuros[:20]:
                    home = j["team1"]["teamName"]
                    away = j["team2"]["teamName"]

                    media_home = calcular_media_gols_time(passados, home)
                    media_away = calcular_media_gols_time(passados, away)
                    media_h2h = calcular_media_gols_h2h(passados, home, away)

                    media_total, tendencia = analisar_tendencia_gols(media_home, media_away, media_h2h)

                    data = j.get("matchDateTime") or j.get("matchDateTimeUTC") or "Desconhecida"
                    data_fmt = data
                    try:
                        data_fmt = datetime.fromisoformat(data.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
                    except:
                        pass

                    # exibição no Streamlit
                    st.write(f"🏟️ {home} vs {away} | 📅 {data_fmt}")
                    st.write(f"   📊 Média gols {home}: {media_home:.2f}")
                    st.write(f"   📊 Média gols {away}: {media_away:.2f}")
                    st.write(f"   📊 Média H2H: {media_h2h:.2f}")
                    st.write(f"   🔮 Estimativa total: {media_total:.2f} | Tendência: {', '.join(tendencia) if tendencia else 'Sem tendência clara'}")
                    st.markdown("---")

                    # envio ao Telegram se houver tendência
                    if tendencia:
                        msg = (
                            f"📊 <b>Tendência de Gols Detectada</b>\n\n"
                            f"🏆 Liga: {liga_nome} ({temporada})\n"
                            f"🏟️ {home} vs {away}\n"
                            f"📅 {data_fmt}\n\n"
                            f"⚽ Média {home}: {media_home:.2f}\n"
                            f"⚽ Média {away}: {media_away:.2f}\n"
                            f"🤝 Média H2H: {media_h2h:.2f}\n\n"
                            f"🔮 Estimativa total: {media_total:.2f}\n"
                            f"🔥 Tendência: {', '.join(tendencia)}"
                        )
                        enviar_telegram(msg)
