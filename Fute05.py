# Futebol_Alertas_OpenLiga_Top3.py
import streamlit as st
from datetime import datetime, date
import requests
import os
import json
import math

# =============================
# Configurações OpenLigaDB + Telegram
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"
ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb"
}

TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

TOP3_PATH = "top3.json"

# =============================
# Persistência
# =============================
def carregar_top3():
    if os.path.exists(TOP3_PATH):
        with open(TOP3_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_top3(lista):
    with open(TOP3_PATH, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")

# =============================
# OpenLigaDB helpers
# =============================
def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        r = requests.get(f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}", timeout=15)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []

def calcular_media_gols_times(jogos_hist):
    stats = {}
    for j in jogos_hist:
        home = j.get("team1", {}).get("teamName")
        away = j.get("team2", {}).get("teamName")
        placar = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if not placar:
            continue
        stats.setdefault(home, {"marcados": [], "sofridos": []})
        stats.setdefault(away, {"marcados": [], "sofridos": []})
        stats[home]["marcados"].append(placar[0])
        stats[home]["sofridos"].append(placar[1])
        stats[away]["marcados"].append(placar[1])
        stats[away]["sofridos"].append(placar[0])

    medias = {}
    for time, gols in stats.items():
        marc = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 1.5
        sofr = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 1.2
        medias[time] = {"media_gols_marcados": round(marc, 2), "media_gols_sofridos": round(sofr, 2)}
    return medias

def media_gols_confrontos_diretos_openliga(home, away, jogos_hist, max_jogos=5):
    confrontos = []
    for j in jogos_hist:
        t1, t2 = j.get("team1", {}).get("teamName"), j.get("team2", {}).get("teamName")
        if {t1, t2} == {home, away}:
            for r in j.get("matchResults", []):
                if r.get("resultTypeID") == 2:
                    gols = r.get("pointsTeam1", 0) + r.get("pointsTeam2", 0)
                    data_str = j.get("matchDateTimeUTC") or j.get("matchDateTime")
                    confrontos.append((data_str, gols))
                    break
    if not confrontos:
        return {"media_gols": 0, "total_jogos": 0}
    confrontos = sorted(confrontos, key=lambda x: x[0] or "", reverse=True)[:max_jogos]
    total_pontos, total_peso = 0, 0
    for idx, (_, total) in enumerate(confrontos):
        peso = max_jogos - idx
        total_pontos += total * peso
        total_peso += peso
    return {"media_gols": round(total_pontos / total_peso, 2) if total_peso else 0, "total_jogos": len(confrontos)}

def parse_data_openliga_to_datetime(s):
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00") if s.endswith("Z") else s
        return datetime.fromisoformat(s2)
    except Exception:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None

def filtrar_jogos_por_data(jogos_all, data_obj: date):
    out = []
    for j in jogos_all:
        date_str = j.get("matchDateTimeUTC") or j.get("matchDateTime")
        dt = parse_data_openliga_to_datetime(date_str)
        if dt and dt.date() == data_obj:
            out.append(j)
    return out

# =============================
# Estatística / Poisson
# =============================
def calcular_estimativa_consolidada(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    mc, sc = media_casa.get("media_gols_marcados", 1.5), media_casa.get("media_gols_sofridos", 1.2)
    mf, sf = media_fora.get("media_gols_marcados", 1.4), media_fora.get("media_gols_sofridos", 1.1)
    estimativa_base = (mc + sf + mf + sc) / 2
    h2h_media = media_h2h.get("media_gols", estimativa_base) if media_h2h.get("total_jogos", 0) > 0 else estimativa_base
    return round((1 - peso_h2h) * estimativa_base + peso_h2h * h2h_media, 2)

def poisson_cdf(k, lam):
    s = sum((lam**i) / math.factorial(i) for i in range(0, k+1))
    return math.exp(-lam) * s

def prob_over_k(estimativa, threshold): 
    k = {1.5:1, 2.5:2, 3.5:3}.get(threshold, int(math.floor(threshold)))
    return max(0.0, min(1.0, 1 - poisson_cdf(k, estimativa)))

def confidence_from_prob(prob):
    return round(max(30, min(95, 50 + (prob - 0.5) * 100)), 0)

# =============================
# Conferência via OpenLigaDB
# =============================
def conferir_jogo_openliga(fixture_id, liga_id, temporada, tipo_threshold):
    try:
        jogos = obter_jogos_liga_temporada(liga_id, temporada)
        match = next((j for j in jogos if str(j.get("matchID")) == str(fixture_id)), None)
        if not match:
            return None
        home, away = match.get("team1", {}).get("teamName"), match.get("team2", {}).get("teamName")
        final = None
        for r in match.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if final is None:
            return {"home": home, "away": away, "total_gols": None, "aposta": f"+{tipo_threshold}", "resultado": "Em andamento"}
        total = sum(final)
        green = total >= {"1.5":2, "2.5":3, "3.5":4}[tipo_threshold]
        return {"home": home, "away": away, "total_gols": total, "aposta": f"+{tipo_threshold}", "resultado": "🟢 GREEN" if green else "🔴 RED", "score": f"{final[0]} x {final[1]}"}
    except Exception:
        return None

# =============================
# UI Streamlit
# =============================
st.set_page_config(page_title="⚽ Alertas Top3 (OpenLigaDB) - Alemanha", layout="wide")
st.title("⚽ Alertas Top3 por Faixa (+1.5 / +2.5 / +3.5) — OpenLigaDB (Alemanha)")

aba = st.tabs(["⚡ Gerar & Enviar Top3", "📊 Jogos Históricos", "🎯 Conferência Top3"])

# ---------- ABA 1 ----------
with aba[0]:
    st.subheader("🔎 Buscar jogos e enviar Top3")
    temporada_hist = st.selectbox("📅 Temporada:", ["2022", "2023", "2024", "2025"], index=2)
    data_selecionada = st.date_input("📅 Data dos jogos:", value=datetime.today().date())
    hoje_str = data_selecionada.strftime("%Y-%m-%d")

    if st.button("🔍 Buscar jogos e enviar Top3"):
        with st.spinner("Processando..."):
            jogos_por_liga, medias_por_liga = {}, {}
            for liga_nome, liga_id in ligas_openliga.items():
                jogos_hist = obter_jogos_liga_temporada(liga_id, temporada_hist)
                jogos_por_liga[liga_id] = jogos_hist
                medias_por_liga[liga_id] = calcular_media_gols_times(jogos_hist)

            jogos_do_dia = []
            for liga_nome, liga_id in ligas_openliga.items():
                filtrados = filtrar_jogos_por_data(jogos_por_liga.get(liga_id, []), data_selecionada)
                for j in filtrados:
                    j.update({"_liga_id": liga_id, "_liga_nome": liga_nome, "_temporada": temporada_hist})
                    jogos_do_dia.append(j)

            if not jogos_do_dia:
                st.info("Nenhum jogo encontrado.")
            else:
                partidas_info = []
                for match in jogos_do_dia:
                    home, away = match["team1"]["teamName"], match["team2"]["teamName"]
                    hora_dt = parse_data_openliga_to_datetime(match.get("matchDateTimeUTC") or match.get("matchDateTime"))
                    hora_formatada = hora_dt.strftime("%H:%M") if hora_dt else "??:??"
                    liga_id, jogos_hist_liga, medias_liga = match["_liga_id"], jogos_por_liga.get(match["_liga_id"], []), medias_por_liga.get(match["_liga_id"], {})
                    media_h2h = media_gols_confrontos_diretos_openliga(home, away, jogos_hist_liga, 5)
                    media_casa, media_fora = medias_liga.get(home, {}), medias_liga.get(away, {})
                    estimativa = calcular_estimativa_consolidada(media_h2h, media_casa, media_fora, 0.3)
                    p15, p25, p35 = prob_over_k(estimativa, 1.5), prob_over_k(estimativa, 2.5), prob_over_k(estimativa, 3.5)
                    partidas_info.append({
                        "fixture_id": match["matchID"], "home": home, "away": away, "hora": hora_formatada,
                        "competicao": match["_liga_nome"], "estimativa": estimativa,
                        "prob_1_5": round(p15*100,1), "prob_2_5": round(p25*100,1), "prob_3_5": round(p35*100,1),
                        "conf_1_5": confidence_from_prob(p15), "conf_2_5": confidence_from_prob(p25), "conf_3_5": confidence_from_prob(p35),
                        "liga_id": liga_id, "temporada": match["_temporada"]
                    })

                top_15 = sorted(partidas_info, key=lambda x: (x["prob_1_5"], x["conf_1_5"], x["estimativa"]), reverse=True)[:3]
                top_25 = sorted(partidas_info, key=lambda x: (x["prob_2_5"], x["conf_2_5"], x["estimativa"]), reverse=True)[:3]
                top_35 = sorted(partidas_info, key=lambda x: (x["prob_3_5"], x["conf_3_5"], x["estimativa"]), reverse=True)[:3]

                for label, lista, key_prob, key_conf in [("+1.5", top_15, "prob_1_5", "conf_1_5"), ("+2.5", top_25, "prob_2_5", "conf_2_5"), ("+3.5", top_35, "prob_3_5", "conf_3_5")]:
                    if lista:
                        msg = f"🔔 *TOP 3 {label} GOLS — {hoje_str}*\n\n"
                        for idx, j in enumerate(lista, 1):
                            msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                    f"   • Est: {j['estimativa']:.2f} | P({label}): *{j[key_prob]}%* | Conf: *{j[key_conf]}%*\n")
                        enviar_telegram(msg, TELEGRAM_CHAT_ID)
                        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

                top3_list = carregar_top3()
                top3_list.append({"data_envio": hoje_str, "hora_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  "temporada": temporada_hist, "top_1_5": top_15, "top_2_5": top_25, "top_3_5": top_35})
                salvar_top3(top3_list)
                st.success("✅ Top3 gerados e enviados.")

# ---------- ABA 2 ----------
with aba[1]:
    st.subheader("📊 Jogos históricos")
    temporada_hist2 = st.selectbox("📅 Temporada histórica:", ["2022", "2023", "2024", "2025"], index=2, key="hist2")
    liga_nome_hist = st.selectbox("🏆 Liga:", list(ligas_openliga.keys()), key="hist_liga")
    if st.button("🔍 Buscar jogos", key="btn_hist"):
        with st.spinner("Buscando..."):
            jogos_hist = obter_jogos_liga_temporada(ligas_openliga[liga_nome_hist], temporada_hist2)
            st.write(f"Total: {len(jogos_hist)} jogos")
            for j in jogos_hist[:30]:
                home, away = j["team1"]["teamName"], j["team2"]["teamName"]
                placar = "-"
                for r in j.get("matchResults", []):
                    if r.get("resultTypeID") == 2:
                        placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                        break
                st.write(f"🏟️ {home} vs {away} | ⚽ {placar}")

# ---------- ABA 3 ----------
with aba[2]:
    st.subheader("🎯 Conferência dos Top 3 enviados")
    top3_salvos = carregar_top3()
    if not top3_salvos:
        st.info("Nenhum Top 3 registrado ainda.")
    else:
        options = [f"{idx+1} - {t['data_envio']} ({t['hora_envio']})" for idx, t in enumerate(top3_salvos)]
        seletor = st.selectbox("Selecione o lote:", options, index=len(options)-1)
        lote = top3_salvos[options.index(seletor)]
        if st.button("🔄 Conferir resultados e enviar"):
            for label, lista in [("1.5", lote.get("top_1_5", [])), ("2.5", lote.get("top_2_5", [])), ("3.5", lote.get("top_3_5", []))]:
                detalhes, greens, reds = [], 0, 0
                lines = []
                for j in lista:
                    info = conferir_jogo_openliga(j["fixture_id"], j["liga_id"], j["temporada"], label)
                    if not info or info["total_gols"] is None:
                        lines.append(f"🏟️ {j['home']} x {j['away']} — sem resultado")
                    else:
                        lines.append(f"🏟️ {info['home']} {info['score']} {info['away']} — {info['resultado']}")
                        greens += "GREEN" in info["resultado"]
                        reds += "RED" in info["resultado"]
                msg = f"✅ RESULTADOS +{label}\n(Lote: {lote['data_envio']})\n\n" + "\n".join(lines) + f"\n\nResumo: 🟢 {greens} | 🔴 {reds}"
                enviar_telegram(msg, TELEGRAM_CHAT_ID)
                enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
            st.success("✅ Conferência enviada.")
