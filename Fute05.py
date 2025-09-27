# Futebol_Alertas_OpenLiga_Top3.py
import streamlit as st
from datetime import datetime, timedelta, date
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

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
TOP3_PATH = "top3.json"

# =============================
# Persistência
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w", encoding="utf-8") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

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
        if r.status_code == 200:
            return r.json()
        else:
            return []
    except Exception as e:
        st.warning(f"Erro OpenLigaDB {liga_id}/{temporada}: {e}")
        return []

def calcular_media_gols_times(jogos_hist):
    stats = {}
    for j in jogos_hist:
        # estrutura OpenLigaDB: team1/team2, matchResults -> resultTypeID==2 é final
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
        media_marcados = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 1.5
        media_sofridos = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 1.2
        medias[time] = {"media_gols_marcados": round(media_marcados, 2), "media_gols_sofridos": round(media_sofridos, 2)}
    return medias

def media_gols_confrontos_diretos_openliga(home, away, jogos_hist, max_jogos=5):
    # busca confrontos diretos na lista de jogos_hist (mesma liga/temporada)
    confrontos = []
    for j in jogos_hist:
        t1 = j.get("team1", {}).get("teamName")
        t2 = j.get("team2", {}).get("teamName")
        if {t1, t2} == {home, away}:
            # pegar placar final se houver
            for r in j.get("matchResults", []):
                if r.get("resultTypeID") == 2:
                    gols = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                    total = gols[0] + gols[1]
                    # use a data string como peso (mais recente = maior)
                    data_str = j.get("matchDateTimeUTC") or j.get("matchDateTime")
                    confrontos.append((data_str, total))
                    break
    if not confrontos:
        return {"media_gols": 0, "total_jogos": 0}
    # ordena por data desc e pega max_jogos mais recentes
    confrontos = sorted(confrontos, key=lambda x: x[0] or "", reverse=True)[:max_jogos]
    total_pontos, total_peso = 0, 0
    for idx, (_, total) in enumerate(confrontos):
        peso = max_jogos - idx
        total_pontos += total * peso
        total_peso += peso
    media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
    return {"media_gols": media_ponderada, "total_jogos": len(confrontos)}

def parse_data_openliga_to_datetime(s):
    if not s:
        return None
    try:
        # exemplos: "2024-08-23T20:30:00Z" ou "2024-08-23T20:30:00+00:00"
        if s.endswith("Z"):
            s2 = s.replace("Z", "+00:00")
        else:
            s2 = s
        return datetime.fromisoformat(s2)
    except Exception:
        try:
            # fallback simples
            return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None

def filtrar_jogos_por_data(jogos_all, data_obj: date):
    out = []
    for j in jogos_all:
        date_str = j.get("matchDateTimeUTC") or j.get("matchDateTime")
        dt = parse_data_openliga_to_datetime(date_str)
        if not dt:
            continue
        if dt.date() == data_obj:
            out.append(j)
    return out

# =============================
# Estatística / Poisson
# =============================
def calcular_estimativa_consolidada(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    # similar à sua função anterior: combina médias (marcados/sofridos) para estimativa total
    media_casa_marcados = media_casa.get("media_gols_marcados", 1.5)
    media_casa_sofridos = media_casa.get("media_gols_sofridos", 1.2)
    media_fora_marcados = media_fora.get("media_gols_marcados", 1.4)
    media_fora_sofridos = media_fora.get("media_gols_sofridos", 1.1)
    media_time_casa = media_casa_marcados + media_fora_sofridos
    media_time_fora = media_fora_marcados + media_casa_sofridos
    estimativa_base = (media_time_casa + media_time_fora) / 2
    h2h_media = media_h2h.get("media_gols", estimativa_base) if media_h2h.get("total_jogos", 0) > 0 else estimativa_base
    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * h2h_media
    return round(estimativa_final, 2)

def poisson_cdf(k, lam):
    # P(X <= k)
    s = 0.0
    for i in range(0, k+1):
        s += (lam**i) / math.factorial(i)
    return math.exp(-lam) * s

def prob_over_k(estimativa, threshold): 
    # threshold: 1.5 -> prob of >=2 (k=1); 2.5 -> >=3 (k=2); 3.5 -> >=4 (k=3)
    if threshold == 1.5:
        k = 1
    elif threshold == 2.5:
        k = 2
    elif threshold == 3.5:
        k = 3
    else:
        k = int(math.floor(threshold))
    p = 1 - poisson_cdf(k, estimativa)
    return max(0.0, min(1.0, p))

def confidence_from_prob(prob):
    # transforma prob (0..1) em % de confiança (30..95)
    conf = 50 + (prob - 0.5) * 100  # prob=0.5 => 50; prob=1 => 100
    conf = max(30, min(95, conf))
    return round(conf, 0)

# =============================
# Conferência via OpenLigaDB (reconsulta)
# =============================
def conferir_jogo_openliga(fixture_id, liga_id, temporada, tipo_threshold):
    """
    fixture_id: matchID do OpenLigaDB (int ou str)
    liga_id, temporada: para reconsultar a temporada correta
    tipo_threshold: "1.5"/"2.5"/"3.5"
    """
    try:
        jogos = obter_jogos_liga_temporada(liga_id, temporada)
        # procurar match com matchID == fixture_id
        match = None
        for j in jogos:
            if str(j.get("matchID")) == str(fixture_id):
                match = j
                break
        if not match:
            return None
        home = match.get("team1", {}).get("teamName")
        away = match.get("team2", {}).get("teamName")
        # procurar placar final
        final = None
        for r in match.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if final is None:
            return {
                "home": home,
                "away": away,
                "total_gols": None,
                "aposta": f"+{tipo_threshold}",
                "resultado": "Em andamento / sem resultado"
            }
        total = final[0] + final[1]
        if tipo_threshold == "1.5":
            green = total >= 2
        elif tipo_threshold == "2.5":
            green = total >= 3
        else:
            green = total >= 4
        return {
            "home": home,
            "away": away,
            "total_gols": total,
            "aposta": f"+{tipo_threshold}",
            "resultado": "🟢 GREEN" if green else "🔴 RED",
            "score": f"{final[0]} x {final[1]}"
        }
    except Exception as e:
        return None

# =============================
# Helpers para selecionar Top3 distintos entre faixas
# =============================
def selecionar_top3_distintos(partidas_info, max_por_faixa=3):
    """
    Seleciona Top3 para +1.5, +2.5 e +3.5 garantindo:
      - prioridade +2.5 -> +1.5 -> +3.5
      - não repetir fixture_id entre faixas
      - evita repetir times (home/away) entre faixas quando possível
    Retorna (top_15, top_25, top_35)
    """
    if not partidas_info:
        return [], [], []

    # lista base (cópia)
    base = list(partidas_info)

    # Top +1.5 (maior prob_1_5)
    top_15 = sorted(base, key=lambda x: (x.get("prob_1_5", 0), x.get("conf_1_5", 0), x.get("estimativa", 0)), reverse=True)[:max_por_faixa]
    selected_ids = set(str(j.get("fixture_id")) for j in top_15)
    selected_teams = set()
    for j in top_15:
        selected_teams.add(j.get("home"))
        selected_teams.add(j.get("away"))

    # candidatos para +2.5: exclui fixtures já selecionados
    candidatos_25 = sorted([j for j in base if str(j.get("fixture_id")) not in selected_ids],
                           key=lambda x: (x.get("prob_2_5", 0), x.get("conf_2_5", 0), x.get("estimativa", 0)), reverse=True)
    top_25 = []
    for c in candidatos_25:
        if len(top_25) >= max_por_faixa:
            break
        # evita times repetidos entre faixas (home/away)
        if c.get("home") in selected_teams or c.get("away") in selected_teams:
            continue
        top_25.append(c)
        selected_ids.add(str(c.get("fixture_id")))
        selected_teams.add(c.get("home"))
        selected_teams.add(c.get("away"))

    # candidatos para +3.5: exclui fixtures já selecionados
    candidatos_35 = sorted([j for j in base if str(j.get("fixture_id")) not in selected_ids],
                           key=lambda x: (x.get("prob_3_5", 0), x.get("conf_3_5", 0), x.get("estimativa", 0)), reverse=True)
    top_35 = []
    for c in candidatos_35:
        if len(top_35) >= max_por_faixa:
            break
        if c.get("home") in selected_teams or c.get("away") in selected_teams:
            continue
        top_35.append(c)
        selected_ids.add(str(c.get("fixture_id")))
        selected_teams.add(c.get("home"))
        selected_teams.add(c.get("away"))

    return top_15, top_25, top_35

# =============================
# UI Streamlit
# =============================
st.set_page_config(page_title="⚽ Alertas Top3 (OpenLigaDB) - Alemanha", layout="wide")
st.title("⚽ Alertas Top3 por Faixa (+1.5 / +2.5 / +3.5) — OpenLigaDB (Alemanha)")

aba = st.tabs(["⚡ Gerar & Enviar Top3 (pré-jogo)", "📊 Jogos Históricos", "🎯 Conferência Top3 (pós-jogo)"])

# ---------- ABA 1: Gerar & Enviar Top3 ----------
with aba[0]:
    st.subheader("🔎 Buscar jogos do dia nas ligas da Alemanha e enviar Top3 por faixa")
    temporada_hist = st.selectbox("📅 Temporada (para médias):", ["2022", "2023", "2024", "2025"], index=2)
    data_selecionada = st.date_input("📅 Data dos jogos:", value=datetime.today().date())
    hoje_str = data_selecionada.strftime("%Y-%m-%d")

    st.markdown("**Obs:** as listas são agora *distintas*: um jogo/time selecionado em +1.5 não será repetido em +2.5 ou +3.5 (prioridade: +1.5 → +2.5 → +3.5).")

    if st.button("🔍 Buscar jogos do dia e enviar Top3 (cada faixa uma mensagem)"):
        with st.spinner("Buscando jogos e calculando probabilidades..."):
            # coletar jogos e médias por liga
            jogos_por_liga = {}
            medias_por_liga = {}
            for liga_nome, liga_id in ligas_openliga.items():
                jogos_hist = obter_jogos_liga_temporada(liga_id, temporada_hist)
                jogos_por_liga[liga_id] = jogos_hist
                medias_por_liga[liga_id] = calcular_media_gols_times(jogos_hist)

            # agregar jogos do dia (todas ligas)
            jogos_do_dia = []
            for liga_nome, liga_id in ligas_openliga.items():
                jogos_hist = jogos_por_liga.get(liga_id, [])
                filtrados = filtrar_jogos_por_data(jogos_hist, data_selecionada)
                for j in filtrados:
                    # adicione infos de liga/temporada para rechecagem futura
                    j["_liga_id"] = liga_id
                    j["_liga_nome"] = liga_nome
                    j["_temporada"] = temporada_hist
                    jogos_do_dia.append(j)

            if not jogos_do_dia:
                st.info("Nenhum jogo encontrado para essa data nas ligas selecionadas.")
            else:
                # calcula estimativas e probabilidades
                partidas_info = []
                for match in jogos_do_dia:
                    home = match.get("team1", {}).get("teamName")
                    away = match.get("team2", {}).get("teamName")
                    hora_dt = parse_data_openliga_to_datetime(match.get("matchDateTimeUTC") or match.get("matchDateTime"))
                    hora_formatada = hora_dt.strftime("%H:%M") if hora_dt else "??:??"
                    liga_id = match.get("_liga_id")
                    jogos_hist_liga = jogos_por_liga.get(liga_id, [])
                    medias_liga = medias_por_liga.get(liga_id, {})

                    media_h2h = media_gols_confrontos_diretos_openliga(home, away, jogos_hist_liga, max_jogos=5)
                    media_casa = medias_liga.get(home, {"media_gols_marcados":1.5, "media_gols_sofridos":1.2})
                    media_fora = medias_liga.get(away, {"media_gols_marcados":1.4, "media_gols_sofridos":1.1})

                    estimativa = calcular_estimativa_consolidada(media_h2h, media_casa, media_fora, peso_h2h=0.3)

                    p15 = prob_over_k(estimativa, 1.5)
                    p25 = prob_over_k(estimativa, 2.5)
                    p35 = prob_over_k(estimativa, 3.5)
                    c15 = confidence_from_prob(p15)
                    c25 = confidence_from_prob(p25)
                    c35 = confidence_from_prob(p35)

                    partidas_info.append({
                        "fixture_id": match.get("matchID"),
                        "home": home, "away": away,
                        "hora": hora_formatada,
                        "competicao": match.get("_liga_nome"),
                        "estimativa": estimativa,
                        "prob_1_5": round(p15*100,1),
                        "prob_2_5": round(p25*100,1),
                        "prob_3_5": round(p35*100,1),
                        "conf_1_5": c15,
                        "conf_2_5": c25,
                        "conf_3_5": c35,
                        "liga_id": liga_id,
                        "temporada": match.get("_temporada")
                    })

                # --- Seleciona Top3 distintos usando a função de prioridade ---
                top_15, top_25, top_35 = selecionar_top3_distintos(partidas_info, max_por_faixa=3)

                # --- Envia 3 mensagens separadas (uma por faixa) ---
                # Mensagem +1.5
                if top_15:
                    msg = f"🔔 *TOP 3 +1.5 GOLS — {hoje_str}*\n\n"
                    for idx, j in enumerate(top_15, start=1):
                        msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                f"   • Est: {j['estimativa']:.2f} gols | P(+1.5): *{j['prob_1_5']:.1f}%* | Conf: *{j['conf_1_5']:.0f}%*\n")
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

                # Mensagem +2.5
                if top_25:
                    msg = f"🔔 *TOP 3 +2.5 GOLS — {hoje_str}*\n\n"
                    for idx, j in enumerate(top_25, start=1):
                        msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                f"   • Est: {j['estimativa']:.2f} gols | P(+2.5): *{j['prob_2_5']:.1f}%* | Conf: *{j['conf_2_5']:.0f}%*\n")
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

                # Mensagem +3.5
                if top_35:
                    msg = f"🔔 *TOP 3 +3.5 GOLS — {hoje_str}*\n\n"
                    for idx, j in enumerate(top_35, start=1):
                        msg += (f"{idx}️⃣ *{j['home']} x {j['away']}* — {j['competicao']} — {j['hora']} BRT\n"
                                f"   • Est: {j['estimativa']:.2f} gols | P(+3.5): *{j['prob_3_5']:.1f}%* | Conf: *{j['conf_3_5']:.0f}%*\n")
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

                # salva o lote Top3 (persistente)
                top3_list = carregar_top3()
                novo_top = {
                    "data_envio": hoje_str,
                    "hora_envio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "temporada": temporada_hist,
                    "top_1_5": top_15,
                    "top_2_5": top_25,
                    "top_3_5": top_35
                }
                top3_list.append(novo_top)
                salvar_top3(top3_list)

                st.success("✅ Top3 gerados e enviados (uma mensagem por faixa).")
                st.write("### Top 3 +1.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P(+1.5)": f"{t['prob_1_5']}%", "Conf": f"{t['conf_1_5']}%"} for t in top_15])
                st.write("### Top 3 +2.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P(+2.5)": f"{t['prob_2_5']}%", "Conf": f"{t['conf_2_5']}%"} for t in top_25])
                st.write("### Top 3 +3.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P(+3.5)": f"{t['prob_3_5']}%", "Conf": f"{t['conf_3_5']}%"} for t in top_35])

# ---------- ABA 2: Jogos históricos ----------
with aba[1]:
    st.subheader("📊 Jogos de Temporadas Passadas (OpenLigaDB) — Ligas da Alemanha")
    temporada_hist2 = st.selectbox("📅 Temporada histórica:", ["2022", "2023", "2024", "2025"], index=2, key="hist2")
    liga_nome_hist = st.selectbox("🏆 Escolha a Liga:", list(ligas_openliga.keys()), key="hist_liga")
    liga_id_hist = ligas_openliga[liga_nome_hist]

    if st.button("🔍 Buscar jogos da temporada", key="btn_hist"):
        with st.spinner("Buscando jogos..."):
            jogos_hist = obter_jogos_liga_temporada(liga_id_hist, temporada_hist2)
            if not jogos_hist:
                st.info("Nenhum jogo encontrado para essa temporada/liga.")
            else:
                st.success(f"{len(jogos_hist)} jogos encontrados na {liga_nome_hist} ({temporada_hist2})")
                for j in jogos_hist[:50]:
                    home = j.get("team1", {}).get("teamName")
                    away = j.get("team2", {}).get("teamName")
                    placar = "-"
                    for r in j.get("matchResults", []):
                        if r.get("resultTypeID") == 2:
                            placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                            break
                    data = j.get("matchDateTimeUTC") or j.get("matchDateTime") or "Desconhecida"
                    st.write(f"🏟️ {home} vs {away} | 📅 {data} | ⚽ Placar: {placar}")

# ---------- ABA 3: Conferência Top 3 ----------
with aba[2]:
    st.subheader("🎯 Conferência dos Top 3 enviados — enviar conferência por faixa (cada faixa uma mensagem)")
    top3_salvos = carregar_top3()

    if not top3_salvos:
        st.info("Nenhum Top 3 registrado ainda. Gere e envie um Top 3 na aba 'Gerar & Enviar Top3'.")
    else:
        st.write(f"✅ Total de envios registrados: {len(top3_salvos)}")
        options = [f"{idx+1} - {t['data_envio']} ({t['hora_envio']})" for idx, t in enumerate(top3_salvos)]
        seletor = st.selectbox("Selecione o lote Top3 para conferir:", options, index=len(options)-1)
        idx_selecionado = options.index(seletor)
        lote = top3_salvos[idx_selecionado]
        st.markdown(f"### Lote selecionado — Envio: **{lote['data_envio']}** às **{lote['hora_envio']}**")
        st.markdown("---")

        if st.button("🔄 Rechecar resultados agora e enviar conferência (uma mensagem por faixa)"):
            with st.spinner("Conferindo resultados e enviando mensagens..."):
                detalhes_1_5 = []
                detalhes_2_5 = []
                detalhes_3_5 = []
                greens_1_5 = reds_1_5 = 0
                greens_2_5 = reds_2_5 = 0
                greens_3_5 = reds_3_5 = 0

                # função auxiliar para processar uma lista e retornar mensagem e resumo
                def processar_lista_e_mandar(lista_top, threshold_label):
                    detalhes_local = []
                    greens = reds = 0
                    lines_for_msg = []
                    for j in lista_top:
                        fixture_id = j.get("fixture_id")
                        liga_id = j.get("liga_id")
                        temporada = j.get("temporada")
                        info = conferir_jogo_openliga(fixture_id, liga_id, temporada, threshold_label)
                        if not info:
                            detalhes_local.append({
                                "home": j.get("home"),
                                "away": j.get("away"),
                                "aposta": f"+{threshold_label}",
                                "status": "Não encontrado / sem resultado"
                            })
                            lines_for_msg.append(f"🏟️ {j.get('home')} x {j.get('away')} — _sem resultado disponível_")
                            continue
                        if info.get("total_gols") is None:
                            lines_for_msg.append(f"🏟️ {info['home']} {info.get('score','')} — _Em andamento / sem resultado_")
                            detalhes_local.append({
                                "home": info["home"],
                                "away": info["away"],
                                "aposta": info["aposta"],
                                "status": "Em andamento"
                            })
                            continue
                        resultado_text = info["resultado"]
                        score = info.get("score", "")
                        lines_for_msg.append(f"🏟️ {info['home']} {score} {info['away']} — {info['aposta']} → {resultado_text}")
                        detalhes_local.append({
                            "home": info["home"],
                            "away": info["away"],
                            "aposta": info["aposta"],
                            "total_gols": info["total_gols"],
                            "resultado": resultado_text
                        })
                        if "GREEN" in resultado_text:
                            greens += 1
                        else:
                            reds += 1
                    # construir e enviar mensagem separada por faixa
                    header = f"✅ RESULTADOS - CONFERÊNCIA +{threshold_label}\n(Lote: {lote['data_envio']})\n\n"
                    if lines_for_msg:
                        body = "\n".join(lines_for_msg)
                    else:
                        body = "_Nenhum jogo para conferir nesta faixa no lote selecionado._"
                    resumo = f"\n\nResumo: 🟢 {greens} GREEN | 🔴 {reds} RED"
                    msg = header + body + resumo
                    enviar_telegram(msg, TELEGRAM_CHAT_ID)
                    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
                    return detalhes_local, {"greens": greens, "reds": reds}

                detalhes_1_5, resumo_1_5 = processar_lista_e_mandar(lote.get("top_1_5", []), "1.5")
                detalhes_2_5, resumo_2_5 = processar_lista_e_mandar(lote.get("top_2_5", []), "2.5")
                detalhes_3_5, resumo_3_5 = processar_lista_e_mandar(lote.get("top_3_5", []), "3.5")

                st.success("✅ Mensagens de conferência enviadas (uma por faixa).")
                st.markdown("**Resumo das conferências enviadas:**")
                st.write(f"+1.5 → 🟢 {resumo_1_5['greens']} | 🔴 {resumo_1_5['reds']}")
                st.write(f"+2.5 → 🟢 {resumo_2_5['greens']} | 🔴 {resumo_2_5['reds']}")
                st.write(f"+3.5 → 🟢 {resumo_3_5['greens']} | 🔴 {resumo_3_5['reds']}")

        # também manter a opção de simplesmente re-checar (sem enviar telegram)
        if st.button("🔎 Rechecar resultados aqui (sem enviar Telegram)"):
            with st.spinner("Conferindo resultados localmente..."):
                detalhes, resumo = [], {"greens":0,"reds":0}
                # Processa +1.5 e +2.5 e +3.5 e imprime
                for label, lista in [("1.5", lote.get("top_1_5", [])), ("2.5", lote.get("top_2_5", [])), ("3.5", lote.get("top_3_5", []))]:
                    st.write(f"### Conferência +{label}")
                    for j in lista:
                        info = conferir_jogo_openliga(j.get("fixture_id"), j.get("liga_id"), j.get("temporada"), label)
                        if not info:
                            st.warning(f"🏟️ {j.get('home')} x {j.get('away')} — Resultado não encontrado / sem atualização")
                            continue
                        if info.get("total_gols") is None:
                            st.info(f"🏟️ {info['home']} — Em andamento / sem resultado")
                            continue
                        if "GREEN" in info["resultado"]:
                            st.success(f"🏟️ {info['home']} {info.get('score','')} {info['away']} → {info['resultado']}")
                        else:
                            st.error(f"🏟️ {info['home']} {info.get('score','')} {info['away']} → {info['resultado']}")

        # opção de exportar lote
        if st.button("📥 Exportar lote selecionado (.json)"):
            nome_arquivo = f"relatorio_top3_{lote['data_envio'].replace('/','-')}_{lote['hora_envio'].replace(':','-').replace(' ','_')}.json"
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(lote, f, ensure_ascii=False, indent=2)
            st.success(f"Lote exportado: {nome_arquivo}")

# Fim do arquivo
