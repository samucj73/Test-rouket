# RoletaVirtual.py - App Especializado em Previsão por Setores
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

# Canal Telegram para Roleta Virtual
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

ROULETTE_LAYOUT = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6,
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24,
    16, 33, 1, 20, 14, 31, 9, 22, 18, 29,
    7, 28, 12, 35, 3, 26
]

# Configurações da Roleta Virtual
SETOR_SIZE = 5           # Tamanho do setor de previsão
MIN_HISTORICO = 20       # Mínimo de registros para começar previsões
MAX_PREVISOES = 8        # Máximo de números na previsão final

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
    """Carrega histórico persistente do arquivo"""
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
    """Salva número diretamente da API no arquivo histórico persistente"""
    try:
        historico_existente = carregar_historico()
        
        # Verifica se o número já existe (pelo timestamp)
        timestamp_novo = numero_dict.get("timestamp")
        ja_existe = any(registro.get("timestamp") == timestamp_novo for registro in historico_existente)
        
        # Só adiciona se for um novo registro
        if not ja_existe:
            historico_existente.append(numero_dict)
            
            # Salva no arquivo
            with open(HISTORICO_PATH, "w") as f:
                json.dump(historico_existente, f, indent=2)
            
            logging.info(f"✅ Número {numero_dict['number']} salvo no histórico")
            return True
        else:
            logging.info(f"⏳ Número {numero_dict['number']} já existe no histórico")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")
        return False

def salvar_metricas(m):
    try:
        hist = []
        if os.path.exists(METRICAS_PATH):
            try:
                with open(METRICAS_PATH, "r") as f:
                    hist = json.load(f)
            except Exception:
                hist = []
        hist.append(m)
        with open(METRICAS_PATH, "w") as f:
            json.dump(hist, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar métricas: {e}")

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
    """Obtém vizinhos físicos na roleta"""
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
# SISTEMA DE ROLETA VIRTUAL
# =============================
class RoletaVirtual:
    def __init__(self, layout=ROULETTE_LAYOUT, setor_size=SETOR_SIZE):
        self.layout = layout
        self.setor_size = setor_size
        self.setores = self._criar_setores()
        
    def _criar_setores(self):
        """Divide a roleta em setores sobrepostos de 5 números"""
        setores = []
        n = len(self.layout)
        
        # Cria setores sobrepostos a cada posição
        for i in range(n):
            setor = []
            for j in range(self.setor_size):
                setor.append(self.layout[(i + j) % n])
            setores.append(setor)
        
        logging.info(f"🎯 Roleta Virtual criada com {len(setores)} setores de {self.setor_size} números")
        return setores
    
    def encontrar_setor_ultimo_numero(self, ultimo_numero):
        """Encontra todos os setores que contêm o último número"""
        setores_com_ultimo = []
        
        for i, setor in enumerate(self.setores):
            if ultimo_numero in setor:
                # Calcula a posição relativa do último número no setor
                posicao = setor.index(ultimo_numero)
                setores_com_ultimo.append((i, setor, posicao))
        
        return setores_com_ultimo
    
    def analisar_historico_setores(self, historico, ultimo_numero):
        """Analisa qual setor tem maior probabilidade baseado no histórico"""
        if len(historico) < 10:
            return []
            
        historico_numeros = [h['number'] for h in historico]
        setores_com_ultimo = self.encontrar_setor_ultimo_numero(ultimo_numero)
        
        if not setores_com_ultimo:
            return []
        
        # Analisa a performance de cada setor após o último número
        performance_setores = {}
        
        for idx_setor, setor, pos_ultimo in setores_com_ultimo:
            acertos = 0
            total_ocorrencias = 0
            
            # Procura no histórico por padrões similares
            for i in range(len(historico_numeros) - 1):
                if historico_numeros[i] == ultimo_numero:
                    # Verifica se o próximo número está neste setor
                    proximo_numero = historico_numeros[i + 1]
                    if proximo_numero in setor:
                        acertos += 1
                    total_ocorrencias += 1
            
            if total_ocorrencias > 0:
                taxa_acerto = acertos / total_ocorrencias
                # Bonus para setores onde o último número está mais no centro
                bonus_posicao = 1.0 - (abs(pos_ultimo - (self.setor_size // 2)) / self.setor_size)
                performance_setores[idx_setor] = {
                    'setor': setor,
                    'taxa_acerto': taxa_acerto,
                    'score': taxa_acerto * (1.0 + bonus_posicao * 0.3),
                    'acertos': acertos,
                    'total': total_ocorrencias
                }
        
        # Ordena por performance e pega o melhor
        setores_ordenados = sorted(performance_setores.items(), 
                                 key=lambda x: x[1]['score'], reverse=True)
        
        if setores_ordenados:
            melhor_setor_idx, dados = setores_ordenados[0]
            melhor_setor = dados['setor']
            
            logging.info(f"🎯 Melhor setor: {melhor_setor} (Score: {dados['score']:.3f}, Acertos: {dados['acertos']}/{dados['total']})")
            return melhor_setor
        
        return []
    
    def prever_proximo_setor(self, historico):
        """Previsão principal do sistema de roleta virtual"""
        if len(historico) < 2:
            return []
            
        ultimo_numero = historico[-1]['number'] if isinstance(historico[-1], dict) else None
        if ultimo_numero is None:
            return []
        
        # 1. Análise estatística do setor mais provável
        setor_previsto = self.analisar_historico_setores(historico, ultimo_numero)
        
        # 2. Se não encontrou padrão forte, usa fallback baseado na posição física
        if not setor_previsto:
            setor_previsto = self.fallback_posicao_fisica(ultimo_numero)
        
        return setor_previsto
    
    def fallback_posicao_fisica(self, ultimo_numero):
        """Fallback: setor ao redor do último número + deslocamento estratégico"""
        if ultimo_numero not in self.layout:
            return []
        
        idx_ultimo = self.layout.index(ultimo_numero)
        
        # Deslocamento baseado em estatísticas de roleta (tendência de +2 a +4 posições)
        deslocamento = 3
        
        idx_alvo = (idx_ultimo + deslocamento) % len(self.layout)
        
        # Pega setor centrado na posição alvo
        setor_fallback = []
        for i in range(self.setor_size):
            pos = (idx_alvo + i - self.setor_size//2) % len(self.layout)
            setor_fallback.append(self.layout[pos])
        
        logging.info(f"🔄 Fallback: Setor ao redor da posição {idx_alvo} -> {setor_fallback}")
        return setor_fallback

    def expandir_previsao_com_vizinhos(self, setor_previsto):
        """Expande o setor previsto incluindo vizinhos físicos"""
        if not setor_previsto:
            return setor_previsto
            
        previsao_expandida = set(setor_previsto.copy())
        
        # Para cada número no setor, adiciona seus vizinhos
        for numero in setor_previsto:
            vizinhos = obter_vizinhos(numero, self.layout, antes=1, depois=1)
            previsao_expandida.update(vizinhos)
        
        # Converte para lista e limita o tamanho
        previsao_final = list(previsao_expandida)
        if len(previsao_final) > MAX_PREVISOES:
            # Prioriza números do setor original
            numeros_prioridade = [n for n in previsao_final if n in setor_previsto]
            outros_numeros = [n for n in previsao_final if n not in setor_previsto]
            previsao_final = numeros_prioridade + outros_numeros
            previsao_final = previsao_final[:MAX_PREVISOES]
        
        return previsao_final

# =============================
# GESTOR DE ESTRATÉGIA PRINCIPAL
# =============================
class GestorRoletaVirtual:
    def __init__(self):
        self.roleta_virtual = RoletaVirtual()
        self.historico = deque(carregar_historico(), maxlen=1000)
        
    def adicionar_numero(self, numero_dict):
        self.historico.append(numero_dict)
        
    def gerar_previsao(self):
        """Gera previsão usando apenas a Roleta Virtual"""
        if len(self.historico) < MIN_HISTORICO:
            return [], []
            
        # 1. Previsão do setor principal
        setor_previsto = self.roleta_virtual.prever_proximo_setor(self.historico)
        
        # 2. Expansão com vizinhos
        previsao_final = self.roleta_virtual.expandir_previsao_com_vizinhos(setor_previsto)
        
        return setor_previsto, previsao_final

# =============================
# STREAMLIT APP - ROLETA VIRTUAL
# =============================
st.set_page_config(
    page_title="Roleta Virtual - Previsão por Setores", 
    page_icon="🎯", 
    layout="centered"
)

st.title("🎯 Roleta Virtual - Previsão por Setores")
st.markdown("### Sistema Inteligente de Previsão por Áreas da Roleta")

# Auto-refresh a cada 3 segundos
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

# Verificação de novo sorteio
novo_sorteio = False
if resultado and resultado.get("timestamp"):
    if (st.session_state.ultimo_timestamp_processado is None or 
        resultado.get("timestamp") != st.session_state.ultimo_timestamp_processado):
        novo_sorteio = True
        logging.info(f"🎲 NOVO SORTEIO: {resultado['number']}")

# Processamento do novo sorteio
if resultado and novo_sorteio:
    numero_dict = {"number": resultado["number"], "timestamp": resultado["timestamp"]}
    
    # Salva no histórico persistente
    salvo_com_sucesso = salvar_historico(numero_dict)
    
    if salvo_com_sucesso:
        st.session_state.gestor.adicionar_numero(numero_dict)
    
    st.session_state.ultimo_timestamp_processado = resultado["timestamp"]
    numero_real = numero_dict["number"]

    # =============================
    # CONFERÊNCIA DE RESULTADOS
    # =============================
    # Conferência do SETOR PREVISTO
    if st.session_state.setor_previsto:
        if numero_real in st.session_state.setor_previsto:
            st.session_state.acertos_setor += 1
            st.success(f"🎯 **ACERTO NO SETOR!** Número {numero_real} estava no setor previsto!")
            enviar_telegram(f"🎯 ACERTO SETOR! Número {numero_real} estava em {st.session_state.setor_previsto}")
        else:
            st.session_state.erros_setor += 1
            st.error(f"🔴 Setor não acertou. Número {numero_real} não estava em {st.session_state.setor_previsto}")
    
    # Conferência da PREVISÃO FINAL
    if st.session_state.previsao_final:
        if numero_real in st.session_state.previsao_final:
            st.session_state.acertos_previsao += 1
            st.success(f"🟢 **GREEN!** Número {numero_real} estava na previsão final!")
            enviar_telegram(f"🟢 GREEN! Número {numero_real} estava na previsão: {st.session_state.previsao_final}")
        else:
            st.session_state.erros_previsao += 1
            st.error(f"🔴 Previsão final errou. Número {numero_real} não estava na lista.")

    # =============================
    # GERAÇÃO DE NOVA PREVISÃO
    # =============================
    if not st.session_state.aguardando_novo_sorteio:
        # Gera nova previsão
        setor_previsto, previsao_final = st.session_state.gestor.gerar_previsao()
        
        if setor_previsto:
            st.session_state.setor_previsto = setor_previsto
            st.session_state.previsao_final = previsao_final
            st.session_state.aguardando_novo_sorteio = True
            
            # Envia alerta no Telegram
            mensagem = f"🎯 **NOVA PREVISÃO ROLETA VIRTUAL**\n"
            mensagem += f"📊 Setor Principal: {', '.join(map(str, sorted(setor_previsto)))}\n"
            mensagem += f"🎲 Previsão Final: {', '.join(map(str, sorted(previsao_final)))}\n"
            mensagem += f"📈 Histórico: {len(st.session_state.gestor.historico)} números"
            
            enviar_telegram(mensagem)
            logging.info("🔔 Nova previsão gerada e enviada para Telegram")

    st.session_state.contador_rodadas += 1

    # Salva métricas
    metrics = {
        "timestamp": resultado.get("timestamp"),
        "numero_real": numero_real,
        "setor_previsto": st.session_state.setor_previsto,
        "previsao_final": st.session_state.previsao_final,
        "acertos_setor": st.session_state.acertos_setor,
        "erros_setor": st.session_state.erros_setor,
        "acertos_previsao": st.session_state.acertos_previsao,
        "erros_previsao": st.session_state.erros_previsao,
    }
    salvar_metricas(metrics)

# =============================
# INTERFACE DO USUÁRIO
# =============================
st.markdown("---")

# Status do Sistema
if resultado and not novo_sorteio:
    st.info(f"⏳ Aguardando novo sorteio...")

if st.session_state.aguardando_novo_sorteio:
    st.warning("🔄 Aguardando próximo sorteio para nova previsão...")

# Histórico Recente
st.subheader("📜 Últimos Números Sorteados")
ultimos_numeros = [h['number'] for h in list(st.session_state.gestor.historico)[-5:]]
if ultimos_numeros:
    st.write(" → ".join(map(str, ultimos_numeros)))
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
else:
    st.info("🔄 **Aguardando dados suficientes para primeira previsão...**")
    st.write(f"Necessário: {MIN_HISTORICO} números | Atual: {len(st.session_state.gestor.historico)}")

# ESTATÍSTICAS DE PERFORMANCE
st.markdown("---")
st.subheader("📊 ESTATÍSTICAS DE PERFORMANCE")

col1, col2, col3, col4 = st.columns(4)

# Estatísticas do SETOR
acertos_setor = st.session_state.acertos_setor
erros_setor = st.session_state.erros_setor
total_setor = acertos_setor + erros_setor
taxa_setor = (acertos_setor / total_setor * 100) if total_setor > 0 else 0.0

col1.metric("🎯 Acertos Setor", acertos_setor)
col2.metric("🔴 Erros Setor", erros_setor)
col3.metric("✅ Taxa Setor", f"{taxa_setor:.1f}%")
col4.metric("📊 Total Jogadas", total_setor)

# Estatísticas da PREVISÃO FINAL
acertos_previsao = st.session_state.acertos_previsao
erros_previsao = st.session_state.erros_previsao
total_previsao = acertos_previsao + erros_previsao
taxa_previsao = (acertos_previsao / total_previsao * 100) if total_previsao > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Greens", acertos_previsao)
col2.metric("🔴 Reds", erros_previsao)
col3.metric("✅ Taxa Acerto", f"{taxa_previsao:.1f}%")
col4.metric("🎯 Precisão", f"{len(st.session_state.previsao_final)} nums" if st.session_state.previsao_final else "0")

# INFORMAÇÕES DO SISTEMA
st.markdown("---")
st.subheader("ℹ️ INFORMAÇÕES DO SISTEMA")

col1, col2, col3 = st.columns(3)
col1.metric("📈 Histórico", f"{len(st.session_state.gestor.historico)} números")
col2.metric("🔄 Rodadas", st.session_state.contador_rodadas)
col3.metric("🎯 Tamanho Setor", SETOR_SIZE)

# COMO FUNCIONA
with st.expander("🔍 **Como funciona a Roleta Virtual?**"):
    st.markdown("""
    **🎯 Estratégia de Setores:**
    - Divide a roleta em **37 setores sobrepostos** de 5 números cada
    - Analisa **padrões de transição** entre setores no histórico
    - Identifica o **setor mais provável** após cada número
    
    **📊 Método de Previsão:**
    1. **Análise Estatística**: Encontra setores com melhor performance histórica
    2. **Posição Física**: Considera a disposição real dos números na roleta
    3. **Expansão Inteligente**: Inclui vizinhos físicos dos números do setor
    
    **🎲 Vantagens:**
    - Foca em **áreas** ao invés de números isolados
    - Mais **consistência** que previsões pontuais
    - **Adaptável** aos padrões recentes da roleta
    """)

# BOTÃO DE DOWNLOAD
st.markdown("---")
st.subheader("📥 EXPORTAR DADOS")

def gerar_download_roleta_virtual():
    try:
        historico = carregar_historico()
        if not historico:
            return None
        
        df = pd.DataFrame(historico)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Historico_Completo', index=False)
            
            stats_data = {
                'Metrica': ['Total Registros', 'Acertos Setor', 'Erros Setor', 'Taxa Setor', 'Acertos Previsão', 'Erros Previsão', 'Taxa Previsão'],
                'Valor': [
                    len(df),
                    st.session_state.acertos_setor,
                    st.session_state.erros_setor,
                    f"{taxa_setor:.1f}%",
                    st.session_state.acertos_previsao,
                    st.session_state.erros_previsao,
                    f"{taxa_previsao:.1f}%"
                ]
            }
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Estatisticas', index=False)
        
        output.seek(0)
        return output
    
    except Exception as e:
        logging.error(f"Erro ao gerar download: {e}")
        return None

if st.button("💾 Exportar Dados Completos", type="primary"):
    with st.spinner("Gerando arquivo..."):
        arquivo = gerar_download_roleta_virtual()
        
        if arquivo:
            nome_arquivo = f"roleta_virtual_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            st.download_button(
                label="⬇️ Baixar Excel",
                data=arquivo,
                file_name=nome_arquivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("✅ Arquivo gerado com sucesso!")
        else:
            st.error("❌ Erro ao gerar arquivo")

# FOOTER
st.markdown("---")
st.caption("🎯 **Roleta Virtual** - Sistema Especializado em Previsão por Setores | Desenvolvido para máxima eficiência")
