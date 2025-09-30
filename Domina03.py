# RoletaVirtual.py - Versão Corrigida (Previsão Dinâmica)
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

# Configurações da Roleta Virtual
SETOR_SIZE = 5
MIN_HISTORICO = 10  # REDUZIDO para começar mais rápido
MAX_PREVISOES = 8

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

def obter_vizinhos(numero, layout, antes=2, depois=2):
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
# SISTEMA DE ROLETA VIRTUAL CORRIGIDO
# =============================
class RoletaVirtual:
    def __init__(self, layout=ROULETTE_LAYOUT, setor_size=SETOR_SIZE):
        self.layout = layout
        self.setor_size = setor_size
        self.setores = self._criar_setores()
        self.ultimo_setor_utilizado = None
        
    def _criar_setores(self):
        """Divide a roleta em setores sobrepostos"""
        setores = []
        n = len(self.layout)
        for i in range(n):
            setor = [self.layout[(i + j) % n] for j in range(self.setor_size)]
            setores.append(setor)
        logging.info(f"🎯 Roleta Virtual criada com {len(setores)} setores")
        return setores
    
    def encontrar_setor_ultimo_numero(self, ultimo_numero):
        """Encontra setores que contêm o último número"""
        setores_com_ultimo = []
        for i, setor in enumerate(self.setores):
            if ultimo_numero in setor:
                posicao = setor.index(ultimo_numero)
                setores_com_ultimo.append((i, setor, posicao))
        return setores_com_ultimo
    
    def analisar_historico_setores(self, historico, ultimo_numero):
        """Analisa qual setor tem maior probabilidade - CORRIGIDO"""
        if len(historico) < 5:  # REDUZIDO o mínimo
            return self.fallback_posicao_fisica(ultimo_numero)
            
        historico_numeros = [h['number'] for h in historico]
        setores_com_ultimo = self.encontrar_setor_ultimo_numero(ultimo_numero)
        
        if not setores_com_ultimo:
            return self.fallback_posicao_fisica(ultimo_numero)
        
        performance_setores = {}
        
        for idx_setor, setor, pos_ultimo in setores_com_ultimo:
            acertos = 0
            total_ocorrencias = 0
            
            # Analisa os últimos 20 números para padrões recentes
            for i in range(max(0, len(historico_numeros)-20), len(historico_numeros)-1):
                if historico_numeros[i] == ultimo_numero:
                    proximo_numero = historico_numeros[i + 1]
                    if proximo_numero in setor:
                        acertos += 1
                    total_ocorrencias += 1
            
            if total_ocorrencias > 0:
                taxa_acerto = acertos / total_ocorrencias
                bonus_posicao = 1.0 - (abs(pos_ultimo - (self.setor_size // 2)) / self.setor_size)
                
                # EVITA REPETIR O MESMO SETOR
                penalty_repeticao = 0.0
                if self.ultimo_setor_utilizado and setor == self.ultimo_setor_utilizado:
                    penalty_repeticao = 0.5  # Penalidade de 50% para setor repetido
                
                performance_setores[idx_setor] = {
                    'setor': setor,
                    'taxa_acerto': taxa_acerto,
                    'score': taxa_acerto * (1.0 + bonus_posicao * 0.3) * (1.0 - penalty_repeticao),
                    'acertos': acertos,
                    'total': total_ocorrencias
                }
        
        # Se não encontrou padrões fortes, usa vários critérios
        if not performance_setores:
            return self.fallback_avancado(historico_numeros, ultimo_numero)
        
        # Ordena e seleciona o MELHOR setor (não o primeiro)
        setores_ordenados = sorted(performance_setores.items(), 
                                 key=lambda x: x[1]['score'], reverse=True)
        
        # NÃO pega sempre o primeiro - às vezes pega o segundo ou terceiro para variar
        if len(setores_ordenados) >= 3:
            # 70% de chance de pegar o melhor, 30% de pegar outro entre top 3
            if np.random.random() < 0.7:
                melhor_idx = 0
            else:
                melhor_idx = np.random.randint(1, min(3, len(setores_ordenados)))
        else:
            melhor_idx = 0
            
        if setores_ordenados:
            melhor_setor_idx, dados = setores_ordenados[melhor_idx]
            melhor_setor = dados['setor']
            self.ultimo_setor_utilizado = melhor_setor
            
            logging.info(f"🎯 Setor escolhido: {melhor_setor} (Score: {dados['score']:.3f}, Posição: {melhor_idx+1})")
            return melhor_setor
        
        return self.fallback_posicao_fisica(ultimo_numero)
    
    def fallback_avancado(self, historico_numeros, ultimo_numero):
        """Fallback mais inteligente quando não há padrões claros"""
        if ultimo_numero not in self.layout:
            return []
        
        idx_ultimo = self.layout.index(ultimo_numero)
        
        # Analisa a direção predominante dos últimos números
        if len(historico_numeros) >= 10:
            direcoes = []
            for i in range(len(historico_numeros)-10, len(historico_numeros)-1):
                num_atual = historico_numeros[i]
                num_proximo = historico_numeros[i+1]
                if num_atual in self.layout and num_proximo in self.layout:
                    idx_atual = self.layout.index(num_atual)
                    idx_prox = self.layout.index(num_proximo)
                    direcao = (idx_prox - idx_atual) % len(self.layout)
                    if direcao > len(self.layout)//2:
                        direcao -= len(self.layout)
                    direcoes.append(direcao)
            
            if direcoes:
                direcao_media = int(np.mean(direcoes))
                deslocamento = max(1, min(6, abs(direcao_media)))
            else:
                deslocamento = 3
        else:
            deslocamento = 3
        
        # Aleatoriedade controlada no deslocamento
        deslocamento += np.random.randint(-1, 2)  # -1, 0, ou +1
        
        idx_alvo = (idx_ultimo + deslocamento) % len(self.layout)
        
        setor_fallback = []
        for i in range(self.setor_size):
            pos = (idx_alvo + i - self.setor_size//2) % len(self.layout)
            setor_fallback.append(self.layout[pos])
        
        logging.info(f"🔄 Fallback avançado: Deslocamento {deslocamento} -> Setor {setor_fallback}")
        return setor_fallback
    
    def fallback_posicao_fisica(self, ultimo_numero):
        """Fallback básico baseado na posição física"""
        if ultimo_numero not in self.layout:
            return []
        
        idx_ultimo = self.layout.index(ultimo_numero)
        
        # Deslocamento VARIÁVEL entre 2 e 4
        deslocamento = np.random.randint(2, 5)
        
        idx_alvo = (idx_ultimo + deslocamento) % len(self.layout)
        
        setor_fallback = []
        for i in range(self.setor_size):
            pos = (idx_alvo + i - self.setor_size//2) % len(self.layout)
            setor_fallback.append(self.layout[pos])
        
        logging.info(f"🔄 Fallback básico: Deslocamento {deslocamento} -> Setor {setor_fallback}")
        return setor_fallback

    def prever_proximo_setor(self, historico):
        """Previsão principal - CORRIGIDA para ser mais dinâmica"""
        if len(historico) < 2:
            return self.fallback_aleatorio()
            
        ultimo_numero = historico[-1]['number'] if isinstance(historico[-1], dict) else None
        if ultimo_numero is None:
            return self.fallback_aleatorio()
        
        # 1. Análise estatística do setor mais provável
        setor_previsto = self.analisar_historico_setores(historico, ultimo_numero)
        
        return setor_previsto
    
    def fallback_aleatorio(self):
        """Fallback totalmente aleatório quando não há dados"""
        idx_aleatorio = np.random.randint(0, len(self.layout))
        setor_aleatorio = []
        for i in range(self.setor_size):
            pos = (idx_aleatorio + i) % len(self.layout)
            setor_aleatorio.append(self.layout[pos])
        
        logging.info(f"🎲 Fallback aleatório: Setor {setor_aleatorio}")
        return setor_aleatorio

    def expandir_previsao_com_vizinhos(self, setor_previsto):
        """Expande o setor previsto incluindo vizinhos físicos - CORRIGIDO"""
        if not setor_previsto:
            return self.fallback_aleatorio()
            
        previsao_expandida = set(setor_previsto.copy())
        
        # Para cada número no setor, adiciona seus vizinhos
        for numero in setor_previsto:
            vizinhos = obter_vizinhos(numero, self.layout, antes=1, depois=1)
            previsao_expandida.update(vizinhos)
        
        # Converte para lista
        previsao_final = list(previsao_expandida)
        
        # ORDENA por proximidade física ao setor original
        def distancia_ao_setor(numero):
            if numero in setor_previsto:
                return 0  # Prioridade máxima para números do setor
            # Calcula distância mínima a qualquer número do setor
            distancias = []
            for num_setor in setor_previsto:
                idx_num = self.layout.index(numero)
                idx_setor = self.layout.index(num_setor)
                distancia = min(abs(idx_num - idx_setor), 
                              len(self.layout) - abs(idx_num - idx_setor))
                distancias.append(distancia)
            return min(distancias)
        
        previsao_final.sort(key=distancia_ao_setor)
        
        # Limita o tamanho mantendo os mais próximos
        if len(previsao_final) > MAX_PREVISOES:
            previsao_final = previsao_final[:MAX_PREVISOES]
        
        logging.info(f"📈 Previsão expandida: {len(setor_previsto)} → {len(previsao_final)} números")
        return previsao_final

# =============================
# GESTOR PRINCIPAL CORRIGIDO
# =============================
class GestorRoletaVirtual:
    def __init__(self):
        self.roleta_virtual = RoletaVirtual()
        self.historico = deque(carregar_historico(), maxlen=1000)
        self.ultima_previsao = None
        
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão dinâmica - CORRIGIDO"""
        if len(self.historico) < 2:  # REDUZIDO o mínimo
            setor_aleatorio = self.roleta_virtual.fallback_aleatorio()
            previsao_final = self.roleta_virtual.expandir_previsao_com_vizinhos(setor_aleatorio)
            return setor_aleatorio, previsao_final
            
        # 1. Previsão do setor principal (AGORA DINÂMICA)
        setor_previsto = self.roleta_virtual.prever_proximo_setor(self.historico)
        
        # 2. Expansão com vizinhos
        previsao_final = self.roleta_virtual.expandir_previsao_com_vizinhos(setor_previsto)
        
        # EVITA REPETIR A MESMA PREVISÃO
        previsao_atual = str(sorted(previsao_final))
        if previsao_atual == self.ultima_previsao and len(self.historico) > 10:
            logging.info("🔄 Previsão repetida, gerando alternativa...")
            setor_previsto = self.roleta_virtual.fallback_avancado(
                [h['number'] for h in self.historico], 
                self.historico[-1]['number']
            )
            previsao_final = self.roleta_virtual.expandir_previsao_com_vizinhos(setor_previsto)
        
        self.ultima_previsao = str(sorted(previsao_final))
        return setor_previsto, previsao_final

# =============================
# STREAMLIT APP CORRIGIDO
# =============================
st.set_page_config(
    page_title="Roleta Virtual - Previsão Dinâmica", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Roleta Virtual - Previsão Dinâmica")
st.markdown("### Sistema Inteligente de Previsão por Áreas - **VERSÃO CORRIGIDA**")

st_autorefresh(interval=3000, key="refresh")

# Inicialização session_state
defaults = {
    "gestor": GestorRoletaVirtual(),
    "setor_previsto": [],
    "previsao_final": [],
    "acertos_setor": 0,
    "erros_setor": 0,
    "acertos_previsao": 0,
    "erros_previsao": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp_processado": None,
    "aguardando_novo_sorteio": False,
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
        logging.info(f"🎲 NOVO SORTEIO: {resultado['number']}")

if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    salvo_com_sucesso = salvar_historico(numero_dict)
    if salvo_com_sucesso:
        st.session_state.gestor.adicionar_numero(numero_dict)
    
    st.session_state.ultimo_timestamp_processado = resultado["timestamp"]
    numero_real = numero_dict["number"]

    # CONFERÊNCIA
    if st.session_state.setor_previsto:
        if numero_real in st.session_state.setor_previsto:
            st.session_state.acertos_setor += 1
            st.success(f"🎯 **ACERTO NO SETOR!** Número {numero_real} estava no setor previsto!")
            enviar_telegram(f"🎯 ACERTO SETOR! Número {numero_real} estava em {st.session_state.setor_previsto}")
        else:
            st.session_state.erros_setor += 1
            st.error(f"🔴 Setor não acertou. Número {numero_real} não estava em {st.session_state.setor_previsto}")
    
    if st.session_state.previsao_final:
        if numero_real in st.session_state.previsao_final:
            st.session_state.acertos_previsao += 1
            st.success(f"🟢 **GREEN!** Número {numero_real} estava na previsão final!")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} estava na previsão: {st.session_state.previsao_final}")
        else:
            st.session_state.erros_previsao += 1

    # GERAÇÃO DE NOVA PREVISÃO (SEMPRE que há novo sorteio)
    setor_previsto, previsao_final = st.session_state.gestor.gerar_previsao()
    
    st.session_state.setor_previsto = setor_previsto
    st.session_state.previsao_final = previsao_final
    
    # Envia alerta no Telegram
    if setor_previsto:
        mensagem = f"🎯 **NOVA PREVISÃO ROLETA VIRTUAL**\n"
        mensagem += f"📊 Setor Principal: {', '.join(map(str, sorted(setor_previsto)))}\n"
        mensagem += f"🎲 Previsão Final: {', '.join(map(str, sorted(previsao_final)))}\n"
        mensagem += f"📈 Histórico: {len(st.session_state.gestor.historico)} números"
        
        enviar_telegram(mensagem)
        logging.info("🔔 Nova previsão gerada e enviada para Telegram")

    st.session_state.contador_rodadas += 1

# =============================
# INTERFACE CORRIGIDA
# =============================
st.markdown("---")

# Status do Sistema
if resultado and not novo_sorteio:
    st.info(f"⏳ Aguardando novo sorteio...")

# Histórico Recente
st.subheader("📜 Últimos Números Sorteados")
ultimos_numeros = [h['number'] for h in list(st.session_state.gestor.historico)[-8:]]
if ultimos_numeros:
    st.write(" → ".join(map(str, ultimos_numeros)))
    st.caption(f"Total no histórico: {len(st.session_state.gestor.historico)} números")
else:
    st.write("Nenhum número registrado ainda")

# PREVISÃO ATUAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL")

if st.session_state.setor_previsto:
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("🎯 Setor Principal", f"{len(st.session_state.setor_previsto)} números")
        st.info(f"**Setor:** {', '.join(map(str, sorted(st.session_state.setor_previsto)))}")
    
    with col2:
        st.metric("🎲 Previsão Final", f"{len(st.session_state.previsao_final)} números")
        st.success(f"**Previsão:** {', '.join(map(str, sorted(st.session_state.previsao_final)))}")
        
    st.progress(min(100, len(st.session_state.gestor.historico)))
    st.caption(f"📊 Baseado em {len(st.session_state.gestor.historico)} números históricos")
else:
    st.info("🔄 **Gerando primeira previsão...**")

# ESTATÍSTICAS
st.markdown("---")
st.subheader("📊 ESTATÍSTICAS DE PERFORMANCE")

col1, col2, col3, col4 = st.columns(4)

acertos_setor = st.session_state.acertos_setor
erros_setor = st.session_state.erros_setor
total_setor = acertos_setor + erros_setor
taxa_setor = (acertos_setor / total_setor * 100) if total_setor > 0 else 0.0

col1.metric("🎯 Acertos Setor", acertos_setor)
col2.metric("🔴 Erros Setor", erros_setor)
col3.metric("✅ Taxa Setor", f"{taxa_setor:.1f}%")
col4.metric("📊 Total Jogadas", total_setor)

acertos_previsao = st.session_state.acertos_previsao
erros_previsao = st.session_state.erros_previsao
total_previsao = acertos_previsao + erros_previsao
taxa_previsao = (acertos_previsao / total_previsao * 100) if total_previsao > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Greens", acertos_previsao)
col2.metric("🔴 Reds", erros_previsao)
col3.metric("✅ Taxa Acerto", f"{taxa_previsao:.1f}%")
col4.metric("🎯 Números Previstos", f"{len(st.session_state.previsao_final)}")

# INFORMAÇÕES DO SISTEMA
st.markdown("---")
st.subheader("ℹ️ INFORMAÇÕES DO SISTEMA")

col1, col2, col3 = st.columns(3)
col1.metric("📈 Histórico", f"{len(st.session_state.gestor.historico)} números")
col2.metric("🔄 Rodadas", st.session_state.contador_rodadas)
col3.metric("🎯 Estratégia", "Setores Dinâmicos")

st.caption("🔄 **Sistema Corrigido**: Previsões agora variam dinamicamente baseado no histórico recente")
