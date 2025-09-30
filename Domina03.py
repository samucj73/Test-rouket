# RoletaVirtual.py - VERSÃO OTIMIZADA URGENTE
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

# NOVAS CONFIGURAÇÕES OTIMIZADAS
SETOR_SIZE = 8  # AUMENTADO para capturar mais números
MIN_HISTORICO = 5
MAX_PREVISOES = 12

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
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def obter_vizinhos(numero, layout, antes=3, depois=3):
    """Obtém vizinhos físicos na roleta - AUMENTADO o alcance"""
    if numero not in layout:
        return [numero]
    idx = layout.index(numero)
    n = len(layout)
    vizinhos = []
    for i in range(antes, 0, -1):
        vizinhos.append(layout[(idx - i) % n])
    vizinhos.append(numero)
    for i in range(1, depois + 1):
        vizinhos.append(layout[(idx + i) % n])
    return vizinhos

# =============================
# SISTEMA DE ROLETA VIRTUAL - ESTRATÉGIA CORRIGIDA
# =============================
class RoletaVirtualOtimizada:
    def __init__(self, layout=ROULETTE_LAYOUT, setor_size=SETOR_SIZE):
        self.layout = layout
        self.setor_size = setor_size
        
    def analisar_padroes_quentes(self, historico):
        """ANÁLISE COMPLETAMENTE NOVA - Foca em números QUENTES"""
        if len(historico) < 10:
            return self.estrategia_conservadora(historico)
            
        numeros = [h['number'] for h in historico]
        ultimos_30 = numeros[-30:]  # Foca nos últimos 30 números
        
        # 1. ANÁLISE DE NÚMEROS QUENTES (últimas 20 jogadas)
        frequencia_20 = Counter(numeros[-20:])
        numeros_quentes = [num for num, freq in frequencia_20.most_common(10) if freq >= 2]
        
        # 2. ANÁLISE DE NÚMEROS FRIOS (não apareceram recentemente)
        ultimos_15 = set(numeros[-15:])
        numeros_frios = [num for num in self.layout if num not in ultimos_15]
        
        # 3. PADRÃO DE REPETIÇÃO (números que se repetem em sequência)
        padroes_repeticao = self.detectar_padroes_repeticao(numeros)
        
        # 4. VIZINHANÇA DO ÚLTIMO NÚMERO
        ultimo_numero = numeros[-1] if numeros else None
        if ultimo_numero is not None:
            vizinhos_ultimo = obter_vizinhos(ultimo_numero, self.layout, antes=4, depois=4)
        else:
            vizinhos_ultimo = []
        
        logging.info(f"🔥 Análise: {len(numeros_quentes)} quentes, {len(numeros_frios)} frios, {len(padroes_repeticao)} padrões")
        
        # COMBINAÇÃO INTELIGENTE DAS ESTRATÉGIAS
        candidatos = set()
        
        # PRIORIDADE 1: Números quentes (40% da previsão)
        if numeros_quentes:
            candidatos.update(numeros_quentes[:4])
        
        # PRIORIDADE 2: Vizinhos do último número (30% da previsão)
        if vizinhos_ultimo:
            candidatos.update(vizinhos_ultimo[:3])
        
        # PRIORIDADE 3: Números frios estratégicos (20% da previsão)
        if numeros_frios:
            # Escolhe frios que estão perto de números quentes
            frios_estrategicos = self.selecionar_frios_estrategicos(numeros_frios, numeros_quentes)
            candidatos.update(frios_estrategicos[:2])
        
        # PRIORIDADE 4: Padrões de repetição (10% da previsão)
        if padroes_repeticao:
            candidatos.update(padroes_repeticao[:2])
        
        # Garante diversidade (não só números consecutivos)
        previsao_final = self.diversificar_previsao(list(candidatos))
        
        logging.info(f"🎯 Previsão final: {len(previsao_final)} números -> {sorted(previsao_final)}")
        return previsao_final
    
    def estrategia_conservadora(self, historico):
        """Estratégia para quando há poucos dados"""
        numeros = [h['number'] for h in historico]
        if not numeros:
            return [0, 32, 15, 19, 4, 21, 2, 25]  # Setor inicial padrão
        
        ultimo_numero = numeros[-1]
        
        # Estratégia básica: vizinhos amplos do último número
        vizinhos = obter_vizinhos(ultimo_numero, self.layout, antes=4, depois=4)
        
        # Adiciona alguns números aleatórios para diversidade
        numeros_aleatorios = np.random.choice(self.layout, size=3, replace=False)
        
        previsao = list(set(vizinhos + numeros_aleatorios.tolist()))
        return previsao[:MAX_PREVISOES]
    
    def detectar_padroes_repeticao(self, numeros):
        """Detecta padrões de repetição nos últimos números"""
        padroes = []
        
        if len(numeros) < 5:
            return padroes
        
        # Procura por números que se repetem em intervalos curtos
        for i in range(len(numeros)-4):
            sequencia = numeros[i:i+5]
            contador = Counter(sequencia)
            for num, freq in contador.items():
                if freq >= 2 and num not in padroes:
                    padroes.append(num)
        
        return padroes
    
    def selecionar_frios_estrategicos(self, numeros_frios, numeros_quentes):
        """Seleciona números frios que estão perto de números quentes"""
        frios_estrategicos = []
        
        for frio in numeros_frios:
            # Encontra o número quente mais próximo
            distancias = []
            for quente in numeros_quentes:
                idx_frio = self.layout.index(frio)
                idx_quente = self.layout.index(quente)
                distancia = min(abs(idx_frio - idx_quente), 
                              len(self.layout) - abs(idx_frio - idx_quente))
                distancias.append(distancia)
            
            if distancias and min(distancias) <= 5:  # Está perto de um número quente
                frios_estrategicos.append(frio)
        
        return frios_estrategicos
    
    def diversificar_previsao(self, previsao):
        """Garante que a previsão tenha números de diferentes áreas da roleta"""
        if len(previsao) <= 6:
            return previsao
        
        # Classifica números por setores da roleta
        setores = {
            'zero': [0],
            'vermelhos_baixos': [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36],
            'pretos_baixos': [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        }
        
        previsao_diversificada = []
        setores_cobertos = set()
        
        # Primeiro passa: garante cobertura de todos os setores
        for numero in previsao:
            for setor_nome, numeros_setor in setores.items():
                if numero in numeros_setor and setor_nome not in setores_cobertos:
                    previsao_diversificada.append(numero)
                    setores_cobertos.add(setor_nome)
                    break
        
        # Segundo passa: adiciona o restante
        for numero in previsao:
            if numero not in previsao_diversificada:
                previsao_diversificada.append(numero)
        
        return previsao_diversificada[:MAX_PREVISOES]

# =============================
# GESTOR PRINCIPAL OTIMIZADO
# =============================
class GestorRoletaVirtualOtimizado:
    def __init__(self):
        self.roleta_virtual = RoletaVirtualOtimizada()
        self.historico = deque(carregar_historico(), maxlen=500)
        
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão usando a NOVA estratégia"""
        if len(self.historico) < 2:
            # Estratégia inicial conservadora
            return [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27]
            
        return self.roleta_virtual.analisar_padroes_quentes(self.historico)

# =============================
# STREAMLIT APP - VERSÃO OTIMIZADA
# =============================
st.set_page_config(
    page_title="Roleta Virtual - ESTRATÉGIA CORRIGIDA", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Roleta Virtual - ESTRATÉGIA CORRIGIDA")
st.markdown("### **🔥 NOVA ESTRATÉGIA: Análise de Números Quentes + Padrões**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorRoletaVirtualOtimizado(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp_processado": None,
    "ultimo_numero_sorteado": None,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =============================
# CAPTURA E PROCESSAMENTO
# =============================
resultado = fetch_latest_result()

novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if (st.session_state.ultimo_timestamp_processado is None or 
        resultado.get("timestamp") != st.session_state.ultimo_timestamp_processado):
        novo_sorteio = True

if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    salvo_com_sucesso = salvar_historico(numero_dict)
    if salvo_com_sucesso:
        st.session_state.gestor.adicionar_numero(numero_dict)
    
    st.session_state.ultimo_timestamp_processado = resultado["timestamp"]
    numero_real = resultado["number"]
    st.session_state.ultimo_numero_sorteado = numero_real

    # CONFERÊNCIA DA PREVISÃO ANTERIOR
    if st.session_state.previsao_atual:
        if numero_real in st.session_state.previsao_atual:
            st.session_state.acertos += 1
            st.success(f"🎯 **GREEN!** Número {numero_real} estava na previsão!")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} acertou na previsão!")
        else:
            st.session_state.erros += 1
            st.error(f"🔴 Número {numero_real} não estava na previsão")

    # GERAÇÃO DE NOVA PREVISÃO
    nova_previsao = st.session_state.gestor.gerar_previsao()
    st.session_state.previsao_atual = nova_previsao
    
    # Envia alerta no Telegram
    if nova_previsao:
        mensagem = f"🎯 **NOVA PREVISÃO - ESTRATÉGIA CORRIGIDA**\n"
        mensagem += f"🔢 Número anterior: {st.session_state.ultimo_numero_sorteado or 'N/A'}\n"
        mensagem += f"🎲 Previsão ({len(nova_previsao)} números): {', '.join(map(str, sorted(nova_previsao)))}\n"
        mensagem += f"📈 Performance: {st.session_state.acertos}/{st.session_state.acertos + st.session_state.erros} greens\n"
        mensagem += f"📊 Histórico: {len(st.session_state.gestor.historico)} números"
        
        enviar_telegram(mensagem)

    st.session_state.contador_rodadas += 1

# =============================
# INTERFACE OTIMIZADA
# =============================
st.markdown("---")

# Status do Sistema
if resultado and not novo_sorteio:
    st.info(f"⏳ Aguardando novo sorteio...")

# ÚLTIMO NÚMERO E HISTÓRICO
col1, col2 = st.columns(2)
with col1:
    if st.session_state.ultimo_numero_sorteado is not None:
        st.metric("🎲 Último Número", st.session_state.ultimo_numero_sorteado)
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.gestor.historico)} números")

# HISTÓRICO RECENTE
st.subheader("📜 Últimos Números")
ultimos_numeros = [h['number'] for h in list(st.session_state.gestor.historico)[-10:]]
if ultimos_numeros:
    # Mostra com cores para melhor visualização
    html_numeros = " → ".join([f"<span style='color: {'red' if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'black' if num != 0 else 'green'}; font-weight: bold'>{num}</span>" for num in ultimos_numeros])
    st.markdown(html_numeros, unsafe_allow_html=True)

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL")

if st.session_state.previsao_atual:
    st.success(f"**🎲 {len(st.session_state.previsao_atual)} NÚMEROS PREVISTOS:**")
    
    # Mostra a previsão formatada
    previsao_formatada = []
    for num in sorted(st.session_state.previsao_atual):
        if num == 0:
            previsao_formatada.append(f"🟢 {num}")
        elif num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
            previsao_formatada.append(f"🔴 {num}")
        else:
            previsao_formatada.append(f"⚫ {num}")
    
    # Divide em colunas para melhor visualização
    col1, col2, col3 = st.columns(3)
    num_por_coluna = len(previsao_formatada) // 3 + 1
    
    with col1:
        for num in previsao_formatada[:num_por_coluna]:
            st.write(num)
    with col2:
        for num in previsao_formatada[num_por_coluna:num_por_coluna*2]:
            st.write(num)
    with col3:
        for num in previsao_formatada[num_por_coluna*2:]:
            st.write(num)
    
    st.caption(f"📈 Estratégia: Análise de números quentes + padrões + diversificação")
else:
    st.info("🔄 **Gerando primeira previsão...**")

# ESTATÍSTICAS
st.markdown("---")
st.subheader("📊 PERFORMANCE DA NOVA ESTRATÉGIA")

acertos = st.session_state.acertos
erros = st.session_state.erros
total = acertos + erros
taxa_acerto = (acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Greens", acertos)
col2.metric("🔴 Reds", erros)
col3.metric("✅ Taxa Acerto", f"{taxa_acerto:.1f}%")
col4.metric("🎯 Números por Previsão", len(st.session_state.previsao_atual) if st.session_state.previsao_atual else 0)

# BARRA DE PROGRESSO
if total > 0:
    st.progress(acertos / total)
    st.caption(f"Progresso: {acertos} acertos em {total} tentativas")

# EXPLICAÇÃO DA NOVA ESTRATÉGIA
with st.expander("🔍 **COMO FUNCIONA A NOVA ESTRATÉGIA**"):
    st.markdown("""
    **🎯 ESTRATÉGIA CORRIGIDA - Análise Multi-dimensional:**
    
    **1. 🔥 Números Quentes** (40%)
    - Foca nos números que mais apareceram nas últimas 20 jogadas
    - Prioriza números com frequência ≥ 2
    
    **2. 📍 Vizinhos Amplos** (30%) 
    - Analisa área ampla ao redor do último número (+4/-4 posições)
    - Considera a física real da roleta
    
    **3. ❄️ Números Frios Estratégicos** (20%)
    - Números que não apareceram recentemente
    - Mas que estão perto de números quentes
    
    **4. 🔄 Padrões de Repetição** (10%)
    - Detecta números que se repetem em sequências curtas
    
    **5. 🎲 Diversificação**
    - Garante cobertura de diferentes áreas da roleta
    - Balanceamento entre vermelhos/pretos/zero
    """)

# BOTÃO DE RESET (para testes)
if st.button("🔄 Reiniciar Estatísticas"):
    st.session_state.acertos = 0
    st.session_state.erros = 0
    st.session_state.contador_rodadas = 0
    st.success("Estatísticas reiniciadas!")

st.markdown("---")
st.caption("🎯 **Roleta Virtual - Estratégia Corrigida** | Desenvolvido para máxima eficiência com base em análise estatística avançada")
