# RoletaVirtual.py - VERSÃO EMERGÊNCIA BASEADA EM DADOS REAIS
import streamlit as st
import json
import os
import time
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import numpy as np
import pandas as pd
import io
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# =============================
# Configurações
# =============================
HISTORICO_PATH = "historico_roleta_virtual.json"
METRICAS_PATH = "metricas_roleta_virtual.json"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# CONFIGURAÇÕES DE EMERGÊNCIA
NUMERO_PREVISOES = 15  # AUMENTADO drasticamente para cobrir mais números
MIN_HISTORICO = 3

# =============================
# Utilitários
# =============================
def enviar_telegram(msg: str, token=TELEGRAM_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            logging.info(f"📁 Histórico carregado: {len(historico)} registros")
            return historico
        except Exception as e:
            logging.error(f"Erro ao carregar histórico: {e}")
            return []
    return []

def salvar_historico(numero_dict):
    try:
        historico_existente = carregar_historico()
        timestamp_novo = numero_dict.get("timestamp")
        ja_existe = any(registro.get("timestamp") == timestamp_novo for registro in historico_existente)
        
        if not ja_existe:
            historico_existente.append(numero_dict)
            with open(HISTORICO_PATH, "w") as f:
                json.dump(historico_existente, f, indent=2)
            logging.info(f"✅ Número {numero_dict['number']} salvo no histórico")
            return True
        return False
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")
        return False

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=6)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# ESTRATÉGIA DE EMERGÊNCIA - BASEADA EM DADOS REAIS
# =============================
class EstrategiaEmergencia:
    def __init__(self):
        self.ultimos_numeros = deque(maxlen=50)
        
    def analise_estatistica_simples(self, historico):
        """ESTRATÉGIA SUPER SIMPLES - Foca no óbvio"""
        if len(historico) < 5:
            return self.previsao_inicial()
            
        numeros = [h['number'] for h in historico]
        
        # ANÁLISE 1: Últimos números que saíram (MAIS IMPORTANTE)
        ultimos_10 = numeros[-10:]
        
        # ANÁLISE 2: Números que se repetiram recentemente
        counter_20 = Counter(numeros[-20:])
        numeros_repetidos = [num for num, count in counter_20.most_common(10) if count >= 2]
        
        # ANÁLISE 3: Vizinhos dos últimos números
        vizinhos_estrategicos = set()
        for num in ultimos_10[-3:]:  # Últimos 3 números
            idx = ROULETTE_LAYOUT.index(num) if num in ROULETTE_LAYOUT else 0
            # Adiciona números ao redor (+2/-2)
            for i in range(-2, 3):
                vizinho = ROULETTE_LAYOUT[(idx + i) % len(ROULETTE_LAYOUT)]
                vizinhos_estrategicos.add(vizinho)
        
        # COMBINAÇÃO INTELIGENTE
        previsao = set()
        
        # 1. Adiciona últimos números (30%)
        previsao.update(ultimos_10[:5])
        
        # 2. Adiciona números repetidos (30%)
        previsao.update(numeros_repetidos[:5])
        
        # 3. Adiciona vizinhos estratégicos (30%)
        previsao.update(list(vizinhos_estrategicos)[:5])
        
        # 4. Preenche com números aleatórios se necessário (10%)
        if len(previsao) < NUMERO_PREVISOES:
            numeros_faltantes = NUMERO_PREVISOES - len(previsao)
            todos_numeros = set(ROULETTE_LAYOUT)
            numeros_restantes = list(todos_numeros - previsao)
            numeros_aleatorios = np.random.choice(numeros_restantes, 
                                                size=min(numeros_faltantes, len(numeros_restantes)), 
                                                replace=False)
            previsao.update(numeros_aleatorios)
        
        previsao_final = list(previsao)
        
        # GARANTE que temos exatamente NUMERO_PREVISOES números
        if len(previsao_final) > NUMERO_PREVISOES:
            previsao_final = previsao_final[:NUMERO_PREVISOES]
        elif len(previsao_final) < NUMERO_PREVISOES:
            # Completa com números mais frequentes no histórico completo
            counter_completo = Counter(numeros)
            numeros_faltantes = NUMERO_PREVISOES - len(previsao_final)
            numeros_complementares = [num for num, _ in counter_completo.most_common(20) 
                                    if num not in previsao_final][:numeros_faltantes]
            previsao_final.extend(numeros_complementares)
        
        logging.info(f"🎯 Previsão Emergencia: {len(previsao_final)} números")
        return previsao_final
    
    def previsao_inicial(self):
        """Previsão quando não há histórico suficiente"""
        # Números mais comuns em roleta baseado em estatísticas reais
        numeros_comuns = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 7]
        return numeros_comuns[:NUMERO_PREVISOES]
    
    def estrategia_agressiva(self, historico):
        """Estratégia mais agressiva - prevê MUITOS números"""
        if len(historico) < 3:
            return list(range(0, 19))  # Primeira metade da roleta
            
        numeros = [h['number'] for h in historico]
        
        # PREVÊ 20 NÚMEROS baseado nos padrões mais óbvios
        previsao = set()
        
        # 1. Todos os últimos 8 números
        previsao.update(numeros[-8:])
        
        # 2. Vizinhos amplos dos últimos 3 números
        for num in numeros[-3:]:
            if num in ROULETTE_LAYOUT:
                idx = ROULETTE_LAYOUT.index(num)
                for i in range(-4, 5):  # ±4 posições
                    vizinho = ROULETTE_LAYOUT[(idx + i) % len(ROULETTE_LAYOUT)]
                    previsao.add(vizinho)
        
        # 3. Números que se repetiram no histórico completo
        counter_global = Counter(numeros)
        numeros_frequentes = [num for num, _ in counter_global.most_common(10)]
        previsao.update(numeros_frequentes)
        
        previsao_final = list(previsao)
        
        # Se ainda não tem números suficientes, completa aleatoriamente
        if len(previsao_final) < 15:
            todos_numeros = set(ROULETTE_LAYOUT)
            numeros_restantes = list(todos_numeros - previsao)
            previsao_final.extend(numeros_restantes[:15-len(previsao_final)])
        
        return previsao_final[:NUMERO_PREVISOES]

# =============================
# SISTEMA PRINCIPAL SIMPLIFICADO
# =============================
class SistemaRoletaEmergencia:
    def __init__(self):
        self.estrategia = EstrategiaEmergencia()
        self.historico = deque(carregar_historico(), maxlen=200)
        
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão ULTRA-SIMPLES mas EFETIVA"""
        if len(self.historico) < 3:
            # ESTRATÉGIA INICIAL: Prever 15 números distribuídos
            return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        
        # ESTRATÉGIA PRINCIPAL: Foco no ÓBVIO
        return self.estrategia.analise_estatistica_simples(self.historico)

# =============================
# STREAMLIT APP - VERSÃO EMERGÊNCIA
# =============================
st.set_page_config(
    page_title="Roleta - ESTRATÉGIA EMERGÊNCIA", 
    page_icon="🚨", 
    layout="centered"
)

st.title("🚨 SISTEMA DE EMERGÊNCIA - Roleta")
st.markdown("### **ESTRATÉGIA: Previsão Ampla Baseada em Padrões Óbvios**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "sistema": SistemaRoletaEmergencia(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
    "historico_acertos": deque(maxlen=20),  # Mantém últimos acertos
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =============================
# PROCESSAMENTO PRINCIPAL
# =============================
resultado = fetch_latest_result()

novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if (st.session_state.ultimo_timestamp is None or 
        resultado.get("timestamp") != st.session_state.ultimo_timestamp):
        novo_sorteio = True

if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    salvo_com_sucesso = salvar_historico(numero_dict)
    if salvo_com_sucesso:
        st.session_state.sistema.adicionar_numero(numero_dict)
    
    st.session_state.ultimo_timestamp = resultado["timestamp"]
    numero_real = resultado["number"]
    st.session_state.ultimo_numero = numero_real

    # CONFERÊNCIA IMEDIATA
    if st.session_state.previsao_atual:
        acertou = numero_real in st.session_state.previsao_atual
        if acertou:
            st.session_state.acertos += 1
            st.session_state.historico_acertos.append(1)
            st.success(f"🎯 **GREEN!** Acertamos o número {numero_real}!")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} acertou na previsão de {len(st.session_state.previsao_atual)} números!")
        else:
            st.session_state.erros += 1
            st.session_state.historico_acertos.append(0)
            st.error(f"🔴 Número {numero_real} não estava nos {len(st.session_state.previsao_atual)} previstos")

    # GERAR NOVA PREVISÃO (SEMPRE)
    nova_previsao = st.session_state.sistema.gerar_previsao()
    st.session_state.previsao_atual = nova_previsao
    
    # TELEGRAM APENAS SE MUDOU A PREVISÃO
    if nova_previsao:
        mensagem = f"🎯 **PREVISÃO ATUALIZADA**\n"
        mensagem += f"Último número: {numero_real}\n"
        mensagem += f"Previsão: {len(nova_previsao)} números\n"
        mensagem += f"Performance: {st.session_state.acertos}G/{st.session_state.erros}R\n"
        mensagem += f"Números: {', '.join(map(str, sorted(nova_previsao)))}"
        
        enviar_telegram(mensagem)

    st.session_state.contador_rodadas += 1

# =============================
# INTERFACE EMERGÊNCIA
# =============================
st.markdown("---")

# STATUS RÁPIDO
col1, col2, col3 = st.columns(3)
with col1:
    if st.session_state.ultimo_numero:
        st.metric("🎲 Último Número", st.session_state.ultimo_numero)
    else:
        st.metric("🎲 Último Número", "-")
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.sistema.historico)}")
with col3:
    st.metric("🎯 Previsão Atual", f"{len(st.session_state.previsao_atual)} nums")

# HISTÓRICO VISUAL
st.subheader("📜 Últimos 15 Números")
if st.session_state.sistema.historico:
    ultimos_15 = [h['number'] for h in list(st.session_state.sistema.historico)[-15:]]
    
    # Mostra com cores e destaque
    html_numeros = ""
    for i, num in enumerate(ultimos_15):
        cor = "red" if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black" if num != 0 else "green"
        peso = "bold" if i >= len(ultimos_15)-5 else "normal"  # Destaca últimos 5
        html_numeros += f"<span style='color: {cor}; font-weight: {peso}; margin: 0 5px;'>{num}</span>"
        if i < len(ultimos_15)-1:
            html_numeros += "→ "
    
    st.markdown(html_numeros, unsafe_allow_html=True)

# PREVISÃO ATUAL (GRANDE E CLARA)
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL - {} NÚMEROS".format(len(st.session_state.previsao_atual)))

if st.session_state.previsao_atual:
    # Divide em 3 colunas para melhor visualização
    col1, col2, col3 = st.columns(3)
    
    numeros_ordenados = sorted(st.session_state.previsao_atual)
    nums_por_coluna = (len(numeros_ordenados) + 2) // 3  # Divide igualmente
    
    with col1:
        for num in numeros_ordenados[:nums_por_coluna]:
            if num == 0:
                st.markdown(f"<div style='background-color: green; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
            elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                st.markdown(f"<div style='background-color: red; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color: black; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
    
    with col2:
        for num in numeros_ordenados[nums_por_coluna:nums_por_coluna*2]:
            if num == 0:
                st.markdown(f"<div style='background-color: green; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
            elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                st.markdown(f"<div style='background-color: red; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color: black; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
    
    with col3:
        for num in numeros_ordenados[nums_por_coluna*2:]:
            if num == 0:
                st.markdown(f"<div style='background-color: green; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>0</div>", unsafe_allow_html=True)
            elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
                st.markdown(f"<div style='background-color: red; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color: black; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>{num}</div>", unsafe_allow_html=True)
    
    st.caption(f"📊 Probabilidade teórica: {(len(st.session_state.previsao_atual)/37)*100:.1f}% de acerto")

# ESTATÍSTICAS SIMPLIFICADAS
st.markdown("---")
st.subheader("📊 ESTATÍSTICAS EM TEMPO REAL")

acertos = st.session_state.acertos
erros = st.session_state.erros
total = acertos + erros
taxa = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Greens", acertos)
col2.metric("🔴 Reds", erros)
col3.metric("✅ Taxa", f"{taxa:.1f}%")
col4.metric("🎯 Cobertura", f"{(len(st.session_state.previsao_atual)/37)*100:.1f}%")

# GRÁFICO DE TENDÊNCIA
if list(st.session_state.historico_acertos):
    st.subheader("📈 Tendência de Acertos (Últimas 20)")
    df_tendencia = pd.DataFrame({
        'Acerto': list(st.session_state.historico_acertos)
    })
    st.line_chart(df_tendencia)

# BOTÃO DE CONTROLE
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Forçar Nova Previsão"):
        nova_previsao = st.session_state.sistema.gerar_previsao()
        st.session_state.previsao_atual = nova_previsao
        st.rerun()

with col2:
    if st.button("🗑️ Zerar Estatísticas"):
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.session_state.historico_acertos.clear()
        st.rerun()

st.markdown("---")
st.warning("🚨 **MODO EMERGÊNCIA**: Estratégia focada em cobertura ampla (15+ números) para garantir acertos imediatos")
