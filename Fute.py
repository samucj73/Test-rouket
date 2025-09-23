import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import time
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações API TheSportsDB v2
# =============================
API_KEY_TSB = "123 (Usuário gratuito)"  # <-- substitua pela sua chave da TheSportsDB v2
BASE_URL_TSB = f"https://www.thesportsdb.com/api/v2/json/{API_KEY_TSB}"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

# =============================
# Dicionário de Ligas (exemplo)
# =============================
liga_dict = {
    "FIFA World Cup": "FIFA",
    "UEFA Champions League": "UCL",
    "Bundesliga": "BL1",
    "Eredivisie": "DED",
    "Campeonato Brasileiro Série A": "BSA",
    "Primera Division": "PD",
    "Ligue 1": "FL1",
    "Championship (Inglaterra)": "ELC",
    "Primeira Liga (Portugal)": "PPL",
    "European Championship": "EC",
    "Serie A (Itália)": "SA",
    "Premier League (Inglaterra)": "PL"
}

# =============================
# Funções de persistência
# =============================
def carregar_json(caminho):
    if os.path.exists(caminho):
        with open(caminho, "r") as f:
            return json.load(f)
    return {}

def salvar_json(caminho, dados):
    with open(caminho, "w") as f:
        json.dump(dados, f)

def carregar_alertas():
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos():
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao():
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Funções de Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})
    except:
        pass

def enviar_alerta_telegram(fixture, tendencia, estimativa, confianca):
    home = fixture["homeTeam"]
    away = fixture["awayTeam"]
    data_jogo = datetime.strptime(fixture["dateEvent"], "%Y-%m-%d")
    hora_formatada = fixture.get("strTime", "00:00")
    competicao = fixture.get("league", "Desconhecido")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_jogo.strftime('%d/%m/%Y')} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Liga: {competicao}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    fixture_id = str(fixture["idEvent"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Controle de Rate Limit / Retry
# =============================
def requests_get_tsdb(endpoint, params=None, retries=3, sleep_sec=1):
    url = f"{BASE_URL_TSB}/{endpoint}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException:
            time.sleep(sleep_sec)
    return {}

# =============================
# Obter jogos do dia
# =============================
def obter_jogos(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]

    # TheSportsDB endpoint
    endpoint = f"eventsday.php"
    params = {"d": data, "s": "Soccer"}
    data_api = requests_get_tsdb(endpoint, params)
    jogos = []

    if "events" in data_api:
        for event in data_api["events"]:
            if liga_id not in event.get("strLeague", ""):
                continue
            jogos.append({
                "idEvent": event.get("idEvent"),
                "homeTeam": event.get("strHomeTeam"),
                "awayTeam": event.get("strAwayTeam"),
                "dateEvent": event.get("dateEvent"),
                "strTime": event.get("strTime"),
                "status": event.get("strStatus", "SCHEDULED"),
                "score": {
                    "fullTime": {
                        "home": int(event.get("intHomeScore") or 0),
                        "away": int(event.get("intAwayScore") or 0)
                    }
                },
                "league": event.get("strLeague")
            })

    cache[key] = jogos
    salvar_cache_jogos(cache)
    return jogos

# =============================
# Obter classificação
# =============================
def obter_classificacao(liga_id):
    cache = carregar_cache_classificacao()
    if liga_id in cache:
        return cache[liga_id]

    # TheSportsDB lookuptable endpoint
    season = datetime.today().year
    endpoint = f"lookuptable.php"
    params = {"l": liga_id, "s": season}
    data_api = requests_get_tsdb(endpoint, params)
    standings = {}

    if "table" in data_api:
        for t in data_api["table"]:
            name = t.get("name")
            standings[name] = {
                "scored": int(t.get("goalsfor") or 0),
                "against": int(t.get("goalsagainst") or 0),
                "played": int(t.get("played") or 1)
            }

    cache[liga_id] = standings
    salvar_cache_classificacao(cache)
    return standings

# =============================
# Cálculo tendência (igual ao anterior)
# =============================
def calcular_tendencia(home, away, classificacao):
    dados_home = classificacao.get(home, {"scored":0, "against":0, "played":1})
    dados_away = classificacao.get(away, {"scored":0, "against":0, "played":1})

    media_home_feitos = dados_home["scored"] / dados_home["played"]
    media_home_sofridos = dados_home["against"] / dados_home["played"]
    media_away_feitos = dados_away["scored"] / dados_away["played"]
    media_away_sofridos = dados_away["against"] / dados_away["played"]

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

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

data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

todas_ligas = st.checkbox("📌 Buscar jogos de todas as ligas do dia", value=True)

liga_selecionada = None
if not todas_ligas:
    liga_selecionada = st.selectbox("📌 Escolha a liga:", list(liga_dict.keys()))

# -----------------------------
# Botão para buscar partidas
# -----------------------------
if st.button("🔍 Buscar partidas"):
    ligas_busca = liga_dict.values() if todas_ligas else [liga_dict[liga_selecionada]]
    st.write(f"⏳ Buscando jogos para {data_selecionada}...")

    top_jogos = []

    for liga_id in ligas_busca:
        classificacao = obter_classificacao(liga_id)
        jogos = obter_jogos(liga_id, hoje)

        for match in jogos:
            home = match["homeTeam"]
            away = match["awayTeam"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)
            verificar_enviar_alerta(match, tendencia, estimativa, confianca)

            top_jogos.append({
                "id": match["idEvent"],
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("league", "Desconhecido"),
                "hora": datetime.strptime(match["dateEvent"], "%Y-%m-%d"),
                "status": match.get("status", "SCHEDULED"),
                "placar": f"{match['score']['fullTime']['home']} x {match['score']['fullTime']['away']}"
            })

    top_n = st.selectbox("📊 Quantos jogos mostrar no Top?", [3,5,10], index=0)

    if top_jogos:
        top_jogos_sorted = sorted(top_jogos, key=lambda x: x["confianca"], reverse=True)[:top_n]
        msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
        for j in top_jogos_sorted:
            hora_format = j["hora"].strftime("%H:%M")
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
                f"Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
                f"Confiança: {j['confianca']:.0f}%\n\n"
            )
        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
        st.success(f"🚀 Top {top_n} jogos enviados para o canal alternativo 2!")
    else:
        st.warning("⚠️ Nenhum jogo disponível ainda para montar o Top.")

# =============================
# Conferência de resultados, PDF e demais funções permanecem iguais
# =============================
# Você pode reaproveitar toda a lógica de conferência e geração de PDF existente
# apenas trocando os campos de JSON para se ajustar à estrutura do TheSportsDB
# =============================
# Conferência de resultados e geração de PDF (TheSportsDB)
# =============================
def abreviar_nome(nome, max_len=15):
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    if len(abreviado) > max_len:
        abreviado = abreviado[:max_len-3] + "..."
    return abreviado

if st.button("📊 Conferir resultados"):
    alertas = carregar_alertas()
    jogos_cache = carregar_cache_jogos()
    mudou = False
    jogos_conferidos = []

    if alertas:
        for fixture_id, info in alertas.items():
            if info.get("conferido"):
                continue

            # Procurar dados no cache
            jogo_dado = None
            for key, jogos in jogos_cache.items():
                for match in jogos:
                    if str(match["idEvent"]) == fixture_id:
                        jogo_dado = match
                        break
                if jogo_dado:
                    break

            if not jogo_dado:
                continue

            home = jogo_dado["homeTeam"]
            away = jogo_dado["awayTeam"]
            status = jogo_dado.get("status", "SCHEDULED")
            gols_home = jogo_dado.get("score", {}).get("fullTime", {}).get("home", 0)
            gols_away = jogo_dado.get("score", {}).get("fullTime", {}).get("away", 0)
            placar = f"{gols_home} x {gols_away}" if status == "FINISHED" else "-"

            # Determinar resultado
            total_gols = (gols_home or 0) + (gols_away or 0)
            if status == "FINISHED":
                tendencia = info["tendencia"]
                if "Mais 2.5" in tendencia:
                    resultado = "🟢 GREEN" if total_gols > 2 else "🔴 RED"
                elif "Mais 1.5" in tendencia:
                    resultado = "🟢 GREEN" if total_gols > 1 else "🔴 RED"
                elif "Menos 2.5" in tendencia:
                    resultado = "🟢 GREEN" if total_gols < 3 else "🔴 RED"
                else:
                    resultado = "-"
                
                # Enviar alerta de conferência
                msg_res = (
                    f"📊 Resultado Conferido\n"
                    f"🏟️ {home} vs {away}\n"
                    f"⚽ Tendência: {tendencia} | Estim.: {info['estimativa']:.2f} | Conf.: {info['confianca']:.0f}%\n"
                    f"📊 Placar Final: {placar}\n"
                    f"✅ Resultado: {resultado}"
                )
                enviar_telegram(msg_res, TELEGRAM_CHAT_ID_ALT2)
            else:
                resultado = "⏳ Aguardando"

            # Streamlit exibição
            bg_color = "#1e4620" if resultado == "🟢 GREEN" else "#5a1e1e" if resultado == "🔴 RED" else "#2c2c2c"
            st.markdown(f"""
            <div style="border:1px solid #444; border-radius:10px; padding:12px; margin-bottom:10px;
                        background-color:{bg_color}; font-size:15px; color:#f1f1f1;">
                <b>🏟️ {abreviar_nome(home)} vs {abreviar_nome(away)}</b><br>
                📌 Status: <b>{status}</b><br>
                ⚽ Tendência: <b>{info['tendencia']}</b> | Estim.: {info['estimativa']:.2f} | Conf.: {info['confianca']:.0f}%<br>
                📊 Placar: <b>{placar}</b><br>
                ✅ Resultado: {resultado}
            </div>
            """, unsafe_allow_html=True)

            # Adicionar à lista para PDF
            hora = datetime.strptime(jogo_dado["dateEvent"], "%Y-%m-%d")
            hora_format = hora.strftime("%d/%m %H:%M")
            jogos_conferidos.append([
                abreviar_nome(home),
                abreviar_nome(away),
                info['tendencia'],
                f"{info['estimativa']:.2f}",
                f"{info['confianca']:.0f}%",
                placar,
                status,
                resultado,
                hora_format
            ])

            if status == "FINISHED":
                info["conferido"] = True
                mudou = True

        if mudou:
            salvar_alertas(alertas)

        # -----------------------------
        # Gerar PDF estilo matriz
        # -----------------------------
        if jogos_conferidos:
            df_conferidos = pd.DataFrame(jogos_conferidos, columns=[
                "Home", "Away", "Tendência","Estimativa","Confiança","Placar","Status","Resultado","Hora"
            ])

            buffer = io.BytesIO()
            pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
            data = [df_conferidos.columns.tolist()] + df_conferidos.values.tolist()

            table = Table(data, repeatRows=1, colWidths=[70,70,70,60,60,50,70,60,70])
            style = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4B4B4B")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F5F5F5")),
                ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ])
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style.add('BACKGROUND', (0,i), (-1,i), colors.HexColor("#E0E0E0"))

            table.setStyle(style)
            pdf.build([table])
            buffer.seek(0)

            st.download_button(
                label="📄 Baixar Jogos Conferidos em PDF (Tabela Estilo Matriz)",
                data=buffer,
                file_name=f"jogos_conferidos_matriz_{datetime.today().strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("Nenhum jogo conferido disponível para gerar PDF.")
    else:
        st.info("Ainda não há resultados para conferir.")
