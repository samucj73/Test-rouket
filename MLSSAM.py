import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
BASE_URL_NEW_API = "https://test-rouket-nvgsix9abxckpjrnlfz79b.streamlit.app/"

ALERTAS_PATH = "alertas.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Funções de cache
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except:
        pass

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

# =============================
# Funções utilitárias
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except:
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Comunicação APIs
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        r = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        return r.status_code == 200
    except:
        return False

def obter_jogos_nova_api(data: str, liga: str | None = None) -> list:
    try:
        params = {"data": data}
        if liga:
            params["liga"] = liga
        r = requests.get(BASE_URL_NEW_API, params=params, timeout=10)
        r.raise_for_status()
        jogos = r.json()
        return jogos if isinstance(jogos, list) else []
    except:
        return []

# =============================
# Lógica de tendência
# =============================
def calcular_tendencia(home: str, away: str) -> tuple[float, float, str]:
    estimativa = 2.2
    confianca = 70
    tendencia = "Mais 1.5"
    return estimativa, confianca, tendencia

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    home = fixture.get("mandante", fixture.get("home", "Desconhecido"))
    away = fixture.get("visitante", fixture.get("away", "Desconhecido"))
    data_formatada, hora_formatada = formatar_data_iso(fixture.get("horário", datetime.now().isoformat()))
    competicao = fixture.get("liga", "Desconhecido")
    status = fixture.get("status", "DESCONHECIDO")
    placar = None
    if fixture.get("placar_m") is not None:
        placar = f"{fixture.get('placar_m')} x {fixture.get('placar_v')}"

    msg = (
        f"⚽ <b>Alerta de Gols!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"📌 Status: {status}\n"
    )
    if placar:
        msg += f"📊 Placar: <b>{placar}</b>\n"
    msg += f"📈 Tendência: <b>{tendencia}</b>\n🎯 Estimativa: <b>{estimativa:.2f}</b>\n💯 Confiança: <b>{confianca:.0f}%</b>\n🏆 Liga: {competicao}"
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    alertas = carregar_alertas()
    fixture_id = str(fixture.get("id", fixture.get("mandante","")) + "_" + str(fixture.get("visitante","")))
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca, "conferido": False}
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Relatório PDF
# =============================
def gerar_relatorio_pdf(jogos_conferidos: list) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    data = [["Jogo","Tendência","Estimativa","Confiança","Placar","Status","Resultado","Hora"]]+jogos_conferidos
    table = Table(data, repeatRows=1, colWidths=[120,70,60,60,50,70,60,70])
    style = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#4B4B4B")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),10),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey)
    ])
    table.setStyle(style)
    pdf.build([table])
    buffer.seek(0)
    return buffer

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols - Nova API", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols - Nova API")

    col1, col2 = st.columns([2,1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.text_input("📌 Liga específica:")

    top_n = st.selectbox("📊 Top N Jogos:", [3,5,10], index=0)

    if st.button("🔍 Buscar Partidas", type="primary"):
        hoje = data_selecionada.strftime("%Y-%m-%d")
        jogos = obter_jogos_nova_api(hoje, liga_selecionada if not todas_ligas else None)
        if not jogos:
            st.warning("Nenhum jogo encontrado.")
            return

        jogos_conferidos = []

        for jogo in jogos:
            home = jogo.get("mandante")
            away = jogo.get("visitante")
            st.markdown(f"🏟️ **{home} vs {away}**")
            try:
                st.image([jogo.get("mandante_logo"), jogo.get("visitante_logo")], width=60,
                         caption=[home, away])
            except:
                pass

            estimativa, confianca, tendencia = calcular_tendencia(home, away)
            verificar_enviar_alerta(jogo, tendencia, estimativa, confianca)

            # Preparar dados PDF
            hora = jogo.get("horário", datetime.now().isoformat())
            placar = f"{jogo.get('placar_m','-')} x {jogo.get('placar_v','-')}" if jogo.get("placar_m") else "-"
            jogos_conferidos.append([
                f"{abreviar_nome(home)} vs {abreviar_nome(away)}",
                tendencia,
                f"{estimativa:.2f}",
                f"{confianca:.0f}%",
                placar,
                jogo.get("status","DESCONHECIDO"),
                "⏳ Aguardando",
                datetime.fromisoformat(hora.replace("Z","+00:00")).strftime("%d/%m %H:%M")
            ])

        # Top N Jogos
        top_jogos_msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
        for j in jogos_conferidos[:top_n]:
            top_jogos_msg += f"🏟️ {j[0]} | Tendência: {j[1]} | Estimativa: {j[2]} | Conf.: {j[3]}\n"
        enviar_telegram(top_jogos_msg, TELEGRAM_CHAT_ID_ALT2)
        st.success(f"✅ Top {top_n} jogos enviados para o Telegram!")

        # PDF
                # PDF
        buffer = gerar_relatorio_pdf(jogos_conferidos)
        st.download_button(
            "📄 Baixar Relatório PDF",
            data=buffer,
            file_name=f"relatorio_jogos_{data_selecionada}.pdf",
            mime="application/pdf"
        )

if __name__ == "__main__":
    main()
