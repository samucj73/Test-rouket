# Fute05_fixed.py
# Versão corrigida — tratamento de KeyError em selecionar_top3_distintos, conf_key robusto,
# uso de times_usados compartilhado para evitar repetição de times entre faixas,
# e conferência usando a função conferir_jogo_openliga.

import streamlit as st
from datetime import datetime, date
import requests
import os
import json
import math

# =============================
# Configurações
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"
TOP3_FILE = "top3.json"

# TELEGRAM: prefira usar variáveis de ambiente em produção
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002932611974")

# =============================
# Persistência
# =============================
def carregar_top3():
    if os.path.exists(TOP3_FILE):
        with open(TOP3_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_top3(entry):
    dados = carregar_top3()
    dados.append(entry)
    with open(TOP3_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    if not TELEGRAM_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        st.warning(f"Erro ao enviar Telegram: {e}")

# =============================
# OpenLiga helpers
# =============================
def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        r = requests.get(f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}", timeout=15)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception as e:
        st.warning(f"Erro OpenLigaDB {liga_id}/{temporada}: {e}")
        return []

def conferir_jogo_openliga(fixture_id, liga_id, temporada, tipo_threshold):
    """
    procura na lista da liga/temporada o matchID == fixture_id e retorna info/comparação:
    tipo_threshold: "1.5" / "2.5" / "3.5" / "btts"
    """
    try:
        jogos = obter_jogos_liga_temporada(liga_id, temporada)
        match = next((j for j in jogos if str(j.get("matchID")) == str(fixture_id)), None)
        if not match:
            return None
        home = match.get("team1", {}).get("teamName")
        away = match.get("team2", {}).get("teamName")
        final = None
        for r in match.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if final is None:
            return {"home": home, "away": away, "total_gols": None, "aposta": f"+{tipo_threshold}", "resultado": "Em andamento / sem resultado"}
        total = final[0] + final[1]
        if tipo_threshold == "1.5":
            green = total >= 2
        elif tipo_threshold == "2.5":
            green = total >= 3
        elif tipo_threshold == "3.5":
            green = total >= 4
        elif tipo_threshold == "btts":
            green = (final[0] > 0 and final[1] > 0)
        else:
            green = False
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
# Médias por equipe (temporada)
# =============================
def calcular_medias_equipe(liga_id, temporada):
    partidas = obter_jogos_liga_temporada(liga_id, temporada)
    medias = {}
    for jogo in partidas:
        # considerar apenas partidas com resultado final
        final = None
        for r in jogo.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if final is None:
            continue
        home = jogo.get("team1", {}).get("teamName")
        away = jogo.get("team2", {}).get("teamName")
        g_home, g_away = final
        # registra estatísticas
        for time, gf, gs in [(home, g_home, g_away), (away, g_away, g_home)]:
            if time not in medias:
                medias[time] = {"jogos": 0, "gf": 0, "gs": 0}
            medias[time]["jogos"] += 1
            medias[time]["gf"] += gf
            medias[time]["gs"] += gs
    # converte para médias
    for t, s in medias.items():
        jogos = s["jogos"] or 1
        s["media_gf"] = s["gf"] / jogos
        s["media_gs"] = s["gs"] / jogos
    return medias

# =============================
# Probabilidades (Poisson / BTTS)
# =============================
def calcular_probabilidades(home, away, medias):
    # usa média caso time não exista no dict
    home_gf = medias.get(home, {}).get("media_gf", 1.2)
    home_gs = medias.get(home, {}).get("media_gs", 1.2)
    away_gf = medias.get(away, {}).get("media_gf", 1.2)
    away_gs = medias.get(away, {}).get("media_gs", 1.2)

    media_home = (home_gf + away_gs) / 2
    media_away = (away_gf + home_gs) / 2
    estimativa = max(0.1, media_home + media_away)  # garantia > 0

    # Poisson CDF helpers
    def p_poisson(k, lam):
        return math.exp(-lam) * (lam**k) / math.factorial(k)

    # Probabilidades acumuladas
    p0 = p_poisson(0, estimativa)
    p1 = p_poisson(1, estimativa)
    p2 = p_poisson(2, estimativa)
    p3 = p_poisson(3, estimativa)

    prob_1_5 = round((1 - (p0 + p1)) * 100, 1)  # >=2
    prob_2_5 = round((1 - (p0 + p1 + p2)) * 100, 1)  # >=3
    prob_3_5 = round((1 - (p0 + p1 + p2 + p3)) * 100, 1)  # >=4

    p_home_gol = 1 - math.exp(-media_home)
    p_away_gol = 1 - math.exp(-media_away)
    prob_btts = round(p_home_gol * p_away_gol * 100, 1)

    # confs simples (ajuste livre)
    conf_1_5 = round(min(95, 30 + prob_1_5 * 0.6), 1)
    conf_2_5 = round(min(95, 20 + prob_2_5 * 0.6), 1)
    conf_3_5 = round(min(95, 10 + prob_3_5 * 0.6), 1)
    conf_btts = round(min(95, 20 + prob_btts * 0.6), 1)

    return {
        "estimativa": round(estimativa, 2),
        "prob_1_5": prob_1_5, "conf_1_5": conf_1_5,
        "prob_2_5": prob_2_5, "conf_2_5": conf_2_5,
        "prob_3_5": prob_3_5, "conf_3_5": conf_3_5,
        "prob_btts": prob_btts, "conf_btts": conf_btts
    }

# =============================
# Função robusta para selecionar top3 sem repetir times
# =============================
def selecionar_top3_distintos(lista, prob_key, times_usados=None):
    """
    Corrigido para evitar KeyError:
    - usa x.get(...) em vez de x[...] para keys que podem faltar
    - constrói conf_key de forma robusta (ex: prob_1_5 -> conf_1_5 ; prob_btts -> conf_btts)
    - ignora entradas sem 'home'/'away'
    - aceita times_usados (set) compartilhado para evitar repetir times entre faixas
    """
    if times_usados is None:
        times_usados = set()

    # conf_key robusto
    if prob_key.startswith("prob_"):
        suffix = "_".join(prob_key.split("_")[1:])  # ex: "1_5" ou "btts"
        conf_key = f"conf_{suffix}"
    else:
        conf_key = "conf_btts"

    selecionados = []
    # ordena usando get(...) com default 0 para evitar KeyError
    sorted_list = sorted(lista, key=lambda x: (x.get(prob_key, 0), x.get(conf_key, 0), x.get("estimativa", 0)), reverse=True)
    for j in sorted_list:
        home = j.get("home")
        away = j.get("away")
        if not home or not away:
            continue
        if home not in times_usados and away not in times_usados:
            selecionados.append(j)
            times_usados.update([home, away])
        if len(selecionados) >= 3:
            break
    return selecionados

# =============================
# Streamlit UI
# =============================
st.set_page_config(page_title="⚽ Alertas Top3 (OpenLigaDB) - FIX", layout="wide")
st.title("⚽ Alertas Top3 por Faixa (+1.5 / +2.5 / +3.5 / BTTS) — OpenLigaDB")

aba = st.tabs(["⚡ Gerar & Enviar Top3", "📊 Histórico", "🎯 Conferência"])

# ---------- ABA 1: Gerar & Enviar Top3 ----------
with aba[0]:
    st.subheader("🔎 Buscar jogos do dia nas ligas e enviar Top3 por faixa (times distintos entre faixas)")
    liga = st.text_input("Liga ID (ex: bl1, bl2, dfb):", "bl1")
    temporada = st.text_input("Temporada (ex: 2024):", "2024")
    data_selecionada = st.date_input("Data (usada apenas para UI):", value=datetime.today().date())

    if st.button("🔍 Gerar Top3 (times distintos)"):
        with st.spinner("Calculando..."):
            medias = calcular_medias_equipe(liga, temporada)
            partidas = obter_jogos_liga_temporada(liga, temporada)
            partidas_info = []
            for jogo in partidas:
                # considerar apenas jogos futuros (não finalizados) para sugestões
                # se quiser incluir todos, remova a condicion
                if jogo.get("matchIsFinished"):
                    continue
                home = jogo.get("team1", {}).get("teamName")
                away = jogo.get("team2", {}).get("teamName")
                fixture_id = jogo.get("matchID")
                probs = calcular_probabilidades(home, away, medias)
                partidas_info.append({
                    "home": home, "away": away,
                    "liga_id": liga, "temporada": temporada, "fixture_id": fixture_id,
                    **probs
                })

            if not partidas_info:
                st.info("Nenhuma partida disponível (ou todas finalizadas) para gerar Top3.")
            else:
                times_usados = set()
                top_15 = selecionar_top3_distintos(partidas_info, "prob_1_5", times_usados)
                top_25 = selecionar_top3_distintos(partidas_info, "prob_2_5", times_usados)
                top_35 = selecionar_top3_distintos(partidas_info, "prob_3_5", times_usados)
                top_btts = selecionar_top3_distintos(partidas_info, "prob_btts", times_usados)

                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry = {
                    "data_envio": agora.split()[0],
                    "hora_envio": agora.split()[1],
                    "temporada": temporada,
                    "liga_id": liga,
                    "top_1_5": top_15,
                    "top_2_5": top_25,
                    "top_3_5": top_35,
                    "top_btts": top_btts
                }
                salvar_top3(entry)

                # envia separadamente
                for faixa, topx, key in [
                    ("+1.5", top_15, "prob_1_5"),
                    ("+2.5", top_25, "prob_2_5"),
                    ("+3.5", top_35, "prob_3_5"),
                    ("Ambas Marcam", top_btts, "prob_btts")
                ]:
                    if topx:
                        conf_key = "conf_" + "_".join(key.split("_")[1:]) if key.startswith("prob_") else "conf_btts"
                        msg = f"🔔 *TOP 3 {faixa} — {agora.split()[0]}*\n\n"
                        for idx, j in enumerate(topx, start=1):
                            prob = j.get(key, 0)
                            conf = j.get(conf_key, 0)
                            msg += f"{idx}️⃣ *{j.get('home')} x {j.get('away')}* — P: *{prob}%* | Conf: *{conf}%*\n"
                        enviar_telegram(msg, TELEGRAM_CHAT_ID)
                        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

                st.success("✅ Top3 gerados, salvos e enviados (faixas sem repetir times).")
                st.write("### Top 3 +1.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_1_5']}%", "Conf": f"{t['conf_1_5']}%" } for t in top_15])
                st.write("### Top 3 +2.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_2_5']}%", "Conf": f"{t['conf_2_5']}%" } for t in top_25])
                st.write("### Top 3 +3.5")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_3_5']}%", "Conf": f"{t['conf_3_5']}%" } for t in top_35])
                st.write("### Top 3 Ambas Marcam (BTTS)")
                st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_btts']}%", "Conf": f"{t['conf_btts']}%" } for t in top_btts])

# ---------- ABA 2: Histórico ----------
with aba[1]:
    st.subheader("📊 Histórico de Top3")
    lista = carregar_top3()
    if not lista:
        st.info("Nenhum Top3 salvo ainda.")
    else:
        for entry in reversed(lista[-10:]):
            st.markdown(f"**{entry['data_envio']} {entry['hora_envio']} — Temp {entry['temporada']} — Liga {entry.get('liga_id')}**")
            st.write("**Top 1.5**")
            st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_1_5']}%", "Conf": f"{t['conf_1_5']}%" } for t in entry.get("top_1_5",[])])
            st.write("**Top 2.5**")
            st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_2_5']}%", "Conf": f"{t['conf_2_5']}%" } for t in entry.get("top_2_5",[])])
            st.write("**Top 3.5**")
            st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_3_5']}%", "Conf": f"{t['conf_3_5']}%" } for t in entry.get("top_3_5",[])])
            st.write("**Top BTTS**")
            st.table([{ "Jogo": f"{t['home']} x {t['away']}", "P": f"{t['prob_btts']}%", "Conf": f"{t['conf_btts']}%" } for t in entry.get("top_btts",[])])
            st.markdown("---")

# ---------- ABA 3: Conferência ----------
with aba[2]:
    st.subheader("🎯 Conferência dos Top3 (último lote salvo)")
    lista = carregar_top3()
    if not lista:
        st.info("Nenhum Top3 salvo para conferir.")
    else:
        ultima = lista[-1]
        st.markdown(f"**Último lote: {ultima['data_envio']} {ultima['hora_envio']} (Temp {ultima['temporada']})**")

        for faixa, key, tipo in [
            ("+1.5", "top_1_5", "1.5"),
            ("+2.5", "top_2_5", "2.5"),
            ("+3.5", "top_3_5", "3.5"),
            ("Ambas Marcam", "top_btts", "btts")
        ]:
            st.write(f"### Conferência {faixa}")
            jogos_para_conferir = ultima.get(key, [])
            resultados = []
            for j in jogos_para_conferir:
                info = conferir_jogo_openliga(j.get("fixture_id"), j.get("liga_id", ultima.get("liga_id")), ultima.get("temporada"), tipo)
                if not info:
                    continue
                resultados.append({
                    "Jogo": f"{info.get('home')} x {info.get('away')}",
                    "Score": info.get("score", "-"),
                    "Total Gols": info.get("total_gols"),
                    "Aposta": info.get("aposta"),
                    "Resultado": info.get("resultado")
                })
            if resultados:
                st.table(resultados)
                # enviar resumo ao Telegram
                msg = f"📊 *Conferência {faixa}* ({ultima['data_envio']})\n\n"
                for r in resultados:
                    msg += f"- {r['Jogo']} | {r['Score']} | {r['Aposta']} → {r['Resultado']}\n"
                enviar_telegram(msg, TELEGRAM_CHAT_ID)
                enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
            else:
                st.info(f"Sem resultados finais disponíveis ainda para {faixa}.")

# Fim do arquivo
