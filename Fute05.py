# Fute05.py (atualizado com médias reais de gols por time)
import streamlit as st
from datetime import datetime
import requests
import os
import json
import math

# =============================
# Configurações
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"
CACHE_FILE = "top3_cache.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2")

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg, chat_id):
    if not TELEGRAM_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Erro Telegram:", e)

def carregar_top3():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_top3(entry):
    dados = carregar_top3()
    dados.append(entry)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def get_partidas(liga, temporada):
    url = f"{OPENLIGA_BASE}/getmatchdata/{liga}/{temporada}"
    r = requests.get(url, timeout=15)
    return r.json() if r.status_code == 200 else []

# =============================
# Cálculo das médias por equipe
# =============================
def calcular_medias_equipe(liga, temporada):
    partidas = get_partidas(liga, temporada)
    medias = {}
    for jogo in partidas:
        if not jogo.get("matchIsFinished"):
            continue
        home = jogo["team1"]["teamName"]
        away = jogo["team2"]["teamName"]
        g_home = jogo["matchResults"][-1]["pointsTeam1"]
        g_away = jogo["matchResults"][-1]["pointsTeam2"]

        for time, gf, gs in [(home, g_home, g_away), (away, g_away, g_home)]:
            if time not in medias:
                medias[time] = {"jogos": 0, "gf": 0, "gs": 0}
            medias[time]["jogos"] += 1
            medias[time]["gf"] += gf
            medias[time]["gs"] += gs

    # converte para médias
    for t in medias:
        jogos = medias[t]["jogos"]
        medias[t]["media_gf"] = medias[t]["gf"] / jogos if jogos else 0
        medias[t]["media_gs"] = medias[t]["gs"] / jogos if jogos else 0
    return medias

# =============================
# Função de probabilidade de gols
# =============================
def calcular_probabilidades(home, away, medias):
    media_home = (medias.get(home, {}).get("media_gf", 1.2) + medias.get(away, {}).get("media_gs", 1.2)) / 2
    media_away = (medias.get(away, {}).get("media_gf", 1.2) + medias.get(home, {}).get("media_gs", 1.2)) / 2
    estimativa = media_home + media_away

    # distribuições Poisson
    p0 = math.exp(-estimativa)
    p1 = estimativa * p0
    prob_1_5 = round((1 - (p0 + p1)) * 100, 1)
    prob_2_5 = round((1 - (p0 + p1 + (estimativa**2/2) * p0)) * 100, 1)
    prob_3_5 = round((1 - (p0 + p1 + (estimativa**2/2) * p0 + (estimativa**3/6) * p0)) * 100, 1)

    # BTTS
    p_home_gol = 1 - math.exp(-media_home)
    p_away_gol = 1 - math.exp(-media_away)
    prob_btts = round(p_home_gol * p_away_gol * 100, 1)

    return {
        "estimativa": round(estimativa, 2),
        "prob_1_5": prob_1_5,
        "conf_1_5": round((media_home + media_away) / 2 * 40, 1),
        "prob_2_5": prob_2_5,
        "conf_2_5": round((media_home + media_away) / 2 * 30, 1),
        "prob_3_5": prob_3_5,
        "conf_3_5": round((media_home + media_away) / 2 * 20, 1),
        "prob_btts": prob_btts,
        "conf_btts": round((p_home_gol + p_away_gol) / 2 * 100, 1)
    }

# =============================
# Seleção dos Top 3 distintos
# =============================
def selecionar_top3_distintos(lista, prob_key, times_usados=set()):
    conf_key = "conf_" + prob_key.split("_")[1] if "prob_" in prob_key else "conf_btts"
    selecionados = []
    for j in sorted(lista, key=lambda x: (x[prob_key], x[conf_key], x["estimativa"]), reverse=True):
        if j["home"] not in times_usados and j["away"] not in times_usados:
            selecionados.append(j)
            times_usados.update([j["home"], j["away"]])
        if len(selecionados) >= 3:
            break
    return selecionados

# =============================
# Streamlit UI
# =============================
st.set_page_config("Futebol Top3", layout="wide")
aba = st.tabs(["📌 Gerar Top3", "📊 Histórico", "🎯 Conferência"])

# --- ABA 1
with aba[0]:
    st.subheader("📌 Seleção dos Top 3")
    liga = st.text_input("Liga ID (ex: bl1)", "bl1")
    temporada = st.text_input("Temporada (ex: 2024)", "2024")
    if st.button("Gerar Top 3"):
        medias = calcular_medias_equipe(liga, temporada)
        partidas = get_partidas(liga, temporada)
        partidas_info = []

        for jogo in partidas:
            if jogo.get("matchIsFinished"):
                continue
            home = jogo["team1"]["teamName"]
            away = jogo["team2"]["teamName"]
            fixture_id = jogo["matchID"]

            probs = calcular_probabilidades(home, away, medias)
            partidas_info.append({
                "home": home, "away": away,
                "liga_id": liga, "temporada": temporada, "fixture_id": fixture_id,
                **probs
            })

        times_usados = set()
        top_15 = selecionar_top3_distintos(partidas_info, "prob_1_5", times_usados)
        top_25 = selecionar_top3_distintos(partidas_info, "prob_2_5", times_usados)
        top_35 = selecionar_top3_distintos(partidas_info, "prob_3_5", times_usados)
        top_btts = selecionar_top3_distintos(partidas_info, "prob_btts", times_usados)

        data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
        entry = {
            "data_envio": data_hoje, "temporada": temporada,
            "top_1_5": top_15, "top_2_5": top_25, "top_3_5": top_35, "top_btts": top_btts
        }
        salvar_top3(entry)

        # Envia alertas
        for faixa, top, key in [("+1.5", top_15, "prob_1_5"), ("+2.5", top_25, "prob_2_5"),
                                ("+3.5", top_35, "prob_3_5"), ("Ambas Marcam", top_btts, "prob_btts")]:
            if top:
                msg = f"📊 *Top 3 {faixa}* ({data_hoje})\n\n"
                for t in top:
                    msg += f"- {t['home']} x {t['away']} | {key}: {t[key]}% | Conf: {t['conf_'+key.split('_')[1]] if 'prob_' in key else t['conf_btts']}%\n"
                enviar_telegram(msg, TELEGRAM_CHAT_ID)
                enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

        # Exibir na tela
        st.write("### Top 3 +1.5")
        st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_1_5']}%", "Conf": f"{t['conf_1_5']}%" } for t in top_15])
        st.write("### Top 3 +2.5")
        st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_2_5']}%", "Conf": f"{t['conf_2_5']}%" } for t in top_25])
        st.write("### Top 3 +3.5")
        st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_3_5']}%", "Conf": f"{t['conf_3_5']}%" } for t in top_35])
        st.write("### Top 3 Ambas Marcam")
        st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_btts']}%", "Conf": f"{t['conf_btts']}%" } for t in top_btts])

# --- ABA 2 (Histórico)
with aba[1]:
    st.subheader("📊 Histórico de Top3")
    top3_list = carregar_top3()
    if not top3_list:
        st.info("Nenhum Top3 salvo ainda.")
    else:
        for entry in reversed(top3_list[-5:]):
            st.markdown(f"**{entry['data_envio']} (Temp. {entry['temporada']})**")
            for faixa, key, prob, conf in [
                ("+1.5", "top_1_5", "prob_1_5", "conf_1_5"),
                ("+2.5", "top_2_5", "prob_2_5", "conf_2_5"),
                ("+3.5", "top_3_5", "prob_3_5", "conf_3_5"),
                ("Ambas Marcam", "top_btts", "prob_btts", "conf_btts")
            ]:
                st.write(f"**Top 3 {faixa}**")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t[prob]}%", "Conf": f"{t[conf]}%" } for t in entry.get(key, [])])
            st.markdown("---")

# --- ABA 3 (Conferência)
#with aba[2]:
#    st.subheader("🎯 Conferência (em desenvolvimento)")
  #  st.info("Aqui será feito o GREEN/RED puxando os placares finais da OpenLigaDB.")

# --- ABA 3 (Conferência)
with aba[2]:
    st.subheader("🎯 Conferência de Resultados dos Top3")
    top3_list = carregar_top3()
    if not top3_list:
        st.info("Nenhum Top3 salvo ainda.")
    else:
        ultima = top3_list[-1]
        st.markdown(f"**Últimos Top3 conferidos ({ultima['data_envio']})**")

        # Função para buscar placar final
        def buscar_resultado(match_id):
            try:
                url = f"{OPENLIGA_BASE}/getmatchdata/{match_id}"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    jogo = r.json()
                    if jogo.get("matchIsFinished"):
                        home = jogo["team1"]["teamName"]
                        away = jogo["team2"]["teamName"]
                        score_home = jogo["matchResults"][-1]["pointsTeam1"]
                        score_away = jogo["matchResults"][-1]["pointsTeam2"]
                        return home, away, score_home, score_away
            except:
                return None
            return None

        # Conferência por faixa
        for faixa, key, prob in [
            ("+1.5", "top_1_5", "prob_1_5"),
            ("+2.5", "top_2_5", "prob_2_5"),
            ("+3.5", "top_3_5", "prob_3_5"),
            ("Ambas Marcam", "top_btts", "prob_btts")
        ]:
            st.write(f"### Conferência Top 3 {faixa}")
            conferencias = []
            for j in ultima.get(key, []):
                res = buscar_resultado(j["fixture_id"])
                if not res:
                    continue
                home, away, g_home, g_away = res
                total = g_home + g_away
                score_str = f"{g_home}:{g_away}"

                if faixa == "Ambas Marcam":
                    resultado = "🟢 GREEN" if g_home > 0 and g_away > 0 else "🔴 RED"
                elif faixa == "+1.5":
                    resultado = "🟢 GREEN" if total >= 2 else "🔴 RED"
                elif faixa == "+2.5":
                    resultado = "🟢 GREEN" if total >= 3 else "🔴 RED"
                elif faixa == "+3.5":
                    resultado = "🟢 GREEN" if total >= 4 else "🔴 RED"

                conferencias.append({
                    "Jogo": f"{home} x {away}",
                    "Placar": score_str,
                    "Total Gols": total,
                    "Aposta": faixa,
                    "Prob": f"{j[prob]}%",
                    "Resultado": resultado
                })

            if conferencias:
                st.table(conferencias)

                # Envia resumo para o Telegram
                msg_conf = f"📊 *Conferência Top 3 {faixa}* ({ultima['data_envio']})\n\n"
                for c in conferencias:
                    msg_conf += f"- {c['Jogo']} | {c['Placar']} | {c['Aposta']} | {c['Resultado']}\n"
                enviar_telegram(msg_conf, TELEGRAM_CHAT_ID)
                enviar_telegram(msg_conf, TELEGRAM_CHAT_ID_ALT2)
            else:
                st.info(f"Aguardando jogos finalizados para {faixa}.")
