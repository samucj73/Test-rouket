import requests
import datetime
import time
import streamlit as st
from typing import Dict, List, Tuple, Optional

# =============================
# Configurações
# =============================
class Config:
    API_KEY = "9058de85e3324bdb969adc005b5d918a"
    HEADERS = {"X-Auth-Token": API_KEY}
    BASE_URL_FD = "https://api.football-data.org/v4"
    
    TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
    TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
    BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    LIGAS = {
        "PL": "Premier League",
        "PD": "La Liga",
        "BL1": "Bundesliga", 
        "SA": "Serie A",
        "FL1": "Ligue 1",
        "BSA": "Brasileirão Série A"
    }
    
    FAIXAS_GOLS = {
        "+1.5": 1.5,
        "+2.5": 2.5, 
        "+3.5": 3.5
    }

# =============================
# Funções utilitárias
# =============================
def enviar_alerta(msg: str) -> bool:
    """Envia mensagem para o Telegram"""
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID, 
        "text": msg, 
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(Config.BASE_URL_TG, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"❌ Erro ao enviar alerta: {e}")
        return False

def fazer_requisicao_api(url: str) -> Optional[dict]:
    """Faz requisições para a API com tratamento de erros"""
    try:
        response = requests.get(url, headers=Config.HEADERS, timeout=15)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            st.warning("⚠️ Limite de requisições excedido. Aguardando...")
            time.sleep(60)
            return fazer_requisicao_api(url)
        else:
            st.error(f"Erro API: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Erro na requisição: {e}")
        return None

def carregar_estatisticas_liga(codigo_liga: str) -> Dict:
    """Carrega estatísticas de times de uma liga"""
    url = f"{Config.BASE_URL_FD}/competitions/{codigo_liga}/standings"
    data = fazer_requisicao_api(url)
    
    if not data:
        return {}
    
    stats = {}
    for table in data.get("standings", []):
        for entry in table.get("table", []):
            team_id = entry["team"]["id"]
            stats[team_id] = {
                "name": entry["team"]["name"],
                "played": entry["playedGames"],
                "gf": entry["goalsFor"],
                "ga": entry["goalsAgainst"],
                "gd": entry["goalDifference"]
            }
    return stats

def calcular_gols_estimados(match: dict, stats_liga: Dict) -> float:
    """Calcula estimativa de gols baseado em estatísticas"""
    home_id = match["homeTeam"]["id"]
    away_id = match["awayTeam"]["id"]

    home_stats = stats_liga.get(home_id)
    away_stats = stats_liga.get(away_id)

    if not home_stats or not away_stats:
        return 2.5  # Valor padrão

    def calcular_media(time_stats: dict) -> float:
        if time_stats["played"] > 0:
            return (time_stats["gf"] + time_stats["ga"]) / time_stats["played"]
        return 2.5

    media_home = calcular_media(home_stats)
    media_away = calcular_media(away_stats)
    
    # Ajuste para time mandante (pequeno bônus)
    media_ajustada = (media_home * 1.1 + media_away) / 2
    
    return round(media_ajustada, 2)

def buscar_jogos_dia(codigo_liga: str, data: str) -> List[dict]:
    """Busca jogos de uma liga para uma data específica"""
    url = f"{Config.BASE_URL_FD}/competitions/{codigo_liga}/matches?dateFrom={data}&dateTo={data}"
    data = fazer_requisicao_api(url)
    return data.get("matches", []) if data else []

def classificar_jogos_por_faixa(partidas_info: List[dict]) -> Dict[str, List[dict]]:
    """Classifica jogos por faixa de gols estimada"""
    faixas = {
        "+1.5": [],
        "+2.5": [], 
        "+3.5": []
    }
    
    for jogo in partidas_info:
        estimativa = jogo["estimativa"]
        
        if estimativa >= 3.2:
            faixas["+3.5"].append(jogo)
        elif estimativa >= 2.7:
            faixas["+2.5"].append(jogo)
        elif estimativa >= 1.8:
            faixas["+1.5"].append(jogo)
    
    # Ordena cada faixa por estimativa (maior primeiro)
    for faixa in faixas:
        faixas[faixa].sort(key=lambda x: x["estimativa"], reverse=True)
    
    return faixas

def selecionar_melhores_jogos(faixas_jogos: Dict[str, List[dict]], max_por_faixa: int = 3) -> Dict[str, List[dict]]:
    """Seleciona os melhores jogos de cada faixa"""
    melhores = {}
    times_utilizados = set()
    
    for faixa, jogos in faixas_jogos.items():
        melhores[faixa] = []
        for jogo in jogos:
            if len(melhores[faixa]) >= max_por_faixa:
                break
                
            # Evita repetir times no mesmo dia
            chave_time = f"{jogo['home']}_{jogo['away']}"
            if chave_time not in times_utilizados:
                melhores[faixa].append(jogo)
                times_utilizados.add(chave_time)
    
    return melhores

def conferir_resultados(jogos_previstos: Dict[str, List[dict]]) -> List[str]:
    """Confere resultados dos jogos previstos"""
    resultados = []
    
    for faixa, jogos in jogos_previstos.items():
        for jogo in jogos:
            url = f"{Config.BASE_URL_FD}/matches/{jogo['id']}"
            data = fazer_requisicao_api(url)
            
            if not data:
                continue
                
            match_data = data["match"]
            
            if match_data["status"] == "FINISHED":
                gols_home = match_data["score"]["fullTime"]["home"] or 0
                gols_away = match_data["score"]["fullTime"]["away"] or 0
                total_gols = gols_home + gols_away
                
                limite_gols = Config.FAIXAS_GOLS[faixa]
                bateu = total_gols > limite_gols
                
                status = "🟢 GREEN" if bateu else "🔴 RED"
                emoji = "✅" if bateu else "❌"
                
                msg = (
                    f"{emoji} *RESULTADO* {emoji}\n"
                    f"🏆 {jogo['liga']}\n"
                    f"⚽ {jogo['home']} {gols_home} - {gols_away} {jogo['away']}\n"
                    f"🎯 Aposta: {faixa}\n" 
                    f"📊 Total: {total_gols} gols\n"
                    f"📈 Estimativa: {jogo['estimativa']}\n"
                    f"Status: {status}"
                )
                
                if enviar_alerta(msg):
                    resultados.append(msg)
    
    return resultados

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="Alertas de Gols", page_icon="⚽", layout="wide")
    
    st.title("⚽ Alertas Automáticos de Gols")
    st.write("Sistema inteligente de previsão de jogos com muitos gols")
    
    # Sidebar
    st.sidebar.header("⚙️ Configurações")
    data_selecionada = st.sidebar.date_input("Data", datetime.date.today())
    max_jogos = st.sidebar.slider("Máx. jogos por faixa", 1, 5, 3)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🔍 Buscar Jogos do Dia", type="primary"):
            with st.spinner("Buscando jogos e calculando estimativas..."):
                buscar_e_analisar_jogos(data_selecionada, max_jogos)
    
    with col2:
        if st.button("✅ Conferir Resultados"):
            with st.spinner("Conferindo resultados..."):
                # Aqui você precisaria carregar os jogos previstos do estado da sessão
                st.info("Funcionalidade precisa dos jogos já buscados")

def buscar_e_analisar_jogos(data_selecionada: datetime.date, max_jogos: int):
    """Função principal para buscar e analisar jogos"""
    data_str = data_selecionada.strftime("%Y-%m-%d")
    todas_partidas = []
    stats_cache = {}
    
    # Barra de progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Coleta dados das ligas
    for i, (codigo_liga, nome_liga) in enumerate(Config.LIGAS.items()):
        status_text.text(f"📊 Analisando {nome_liga}...")
        stats_cache[codigo_liga] = carregar_estatisticas_liga(codigo_liga)
        jogos = buscar_jogos_dia(codigo_liga, data_str)
        
        for jogo in jogos:
            estimativa = calcular_gols_estimados(jogo, stats_cache[codigo_liga])
            todas_partidas.append({
                "id": jogo["id"],
                "home": jogo["homeTeam"]["name"],
                "away": jogo["awayTeam"]["name"], 
                "liga": nome_liga,
                "estimativa": estimativa,
                "data": jogo.get("utcDate", data_str)
            })
        
        progress_bar.progress((i + 1) / len(Config.LIGAS))
    
    if not todas_partidas:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada")
        return
    
    # Classifica e seleciona jogos
    faixas_jogos = classificar_jogos_por_faixa(todas_partidas)
    melhores_jogos = selecionar_melhores_jogos(faixas_jogos, max_jogos)
    
    # Exibe resultados
    exibir_resultados(melhores_jogos, data_str)
    
    # Botão de enviar alertas
    if st.button("🚀 Enviar Alertas no Telegram", type="secondary"):
        enviar_alertas_telegram(melhores_jogos, data_str)

def exibir_resultados(jogos: Dict[str, List[dict]], data: str):
    """Exibe os jogos selecionados na interface"""
    st.subheader(f"🎯 Melhores Jogos - {data}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("#### 🟢 +1.5 Gols")
        for jogo in jogos.get("+1.5", []):
            st.write(f"**{jogo['home']} vs {jogo['away']}**")
            st.write(f"📈 Estimativa: {jogo['estimativa']} gols")
            st.write(f"🏆 {jogo['liga']}")
            st.divider()
    
    with col2:
        st.write("#### 🟡 +2.5 Gols") 
        for jogo in jogos.get("+2.5", []):
            st.write(f"**{jogo['home']} vs {jogo['away']}**")
            st.write(f"📈 Estimativa: {jogo['estimativa']} gols")
            st.write(f"🏆 {jogo['liga']}")
            st.divider()
    
    with col3:
        st.write("#### 🔴 +3.5 Gols")
        for jogo in jogos.get("+3.5", []):
            st.write(f"**{jogo['home']} vs {jogo['away']}**")
            st.write(f"📈 Estimativa: {jogo['estimativa']} gols")
            st.write(f"🏆 {jogo['liga']}") 
            st.divider()

def enviar_alertas_telegram(jogos: Dict[str, List[dict]], data: str):
    """Envia alertas formatados para o Telegram"""
    alerta = f"🚨 *ALERTAS DE JOGOS - {data}* 🚨\n\n"
    
    for faixa, jogos_faixa in jogos.items():
        if jogos_faixa:
            alerta += f"*{faixa} GOLS:*\n"
            for jogo in jogos_faixa:
                alerta += f"• {jogo['home']} vs {jogo['away']}\n"
                alerta += f"  📈 {jogo['estimativa']} gols | 🏆 {jogo['liga']}\n"
            alerta += "\n"
    
    if enviar_alerta(alerta):
        st.success("✅ Alertas enviados para o Telegram!")
    else:
        st.error("❌ Erro ao enviar alertas")

if __name__ == "__main__":
    main()
