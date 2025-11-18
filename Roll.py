import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import pandas as pd
from collections import Counter, deque
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.utils import resample
import joblib
from streamlit_autorefresh import st_autorefresh
import pickle

# =============================
# CONFIGURAÇÕES BÁSICAS
# =============================
logging.basicConfig(level=logging.INFO)
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"

# =============================
# SISTEMA DE DETECÇÃO DE TENDÊNCIAS
# =============================
class SistemaTendencias:
    def __init__(self):
        self.historico_tendencias = deque(maxlen=50)
        self.tendencia_ativa = None
        self.estado_tendencia = "aguardando"
        self.contador_confirmacoes = 0
        self.contador_erros_tendencia = 0
        self.contador_acertos_tendencia = 0
        self.historico_zonas_dominantes = deque(maxlen=10)
        self.rodadas_operando = 0
        self.max_operacoes_por_tendencia = 4
        
    def analisar_tendencia(self, zonas_rankeadas, acerto_ultima=False, zona_acertada=None):
        if not zonas_rankeadas or len(zonas_rankeadas) < 2:
            return self._criar_resposta_tendencia("aguardando", None, "Aguardando dados suficientes")
        
        zona_top1, score_top1 = zonas_rankeadas[0]
        self.historico_zonas_dominantes.append(zona_top1)
        
        if self.estado_tendencia in ["aguardando", "formando"]:
            return self._analisar_formacao_tendencia(zona_top1, score_top1)
        elif self.estado_tendencia == "ativa":
            return self._analisar_tendencia_ativa(zona_top1, acerto_ultima, zona_acertada)
        elif self.estado_tendencia == "enfraquecendo":
            return self._analisar_tendencia_enfraquecendo(zona_top1, acerto_ultima, zona_acertada)
        elif self.estado_tendencia == "morta":
            return self._analisar_reinicio_tendencia(zona_top1)
        
        return self._criar_resposta_tendencia("aguardando", None, "Estado não reconhecido")
    
    def _analisar_formacao_tendencia(self, zona_top1, score_top1):
        freq_zona_top1 = list(self.historico_zonas_dominantes).count(zona_top1)
        frequencia_minima = 3 if len(self.historico_zonas_dominantes) >= 5 else 2
        
        if (freq_zona_top1 >= frequencia_minima and score_top1 >= 25):
            if self.estado_tendencia == "aguardando":
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                return self._criar_resposta_tendencia("formando", zona_top1, f"Tendência se formando - {zona_top1}")
            elif self.estado_tendencia == "formando":
                self.contador_confirmacoes += 1
                if self.contador_confirmacoes >= 2:
                    self.estado_tendencia = "ativa"
                    self.contador_acertos_tendencia = 0
                    self.contador_erros_tendencia = 0
                    self.rodadas_operando = 0
                    return self._criar_resposta_tendencia("ativa", zona_top1, f"✅ TENDÊNCIA CONFIRMADA - {zona_top1}")
        
        return self._criar_resposta_tendencia(self.estado_tendencia, self.tendencia_ativa, f"Aguardando confirmação - {zona_top1}")
    
    def _analisar_tendencia_ativa(self, zona_top1, acerto_ultima, zona_acertada):
        mesma_zona = zona_top1 == self.tendencia_ativa
        
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        self.rodadas_operando += 1
        
        if (self.contador_acertos_tendencia >= 1 and 
            self.contador_erros_tendencia == 0 and
            self.rodadas_operando <= self.max_operacoes_por_tendencia):
            
            acao = "operar" if mesma_zona else "aguardar"
            return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, f"🔥 OPERAR - {self.tendencia_ativa}", acao)
        
        if self._detectar_enfraquecimento():
            self.estado_tendencia = "enfraquecendo"
            return self._criar_resposta_tendencia("enfraquecendo", self.tendencia_ativa, "⚠️ Tendência enfraquecendo")
        
        if self._detectar_morte_tendencia(zona_top1):
            self.estado_tendencia = "morta"
            return self._criar_resposta_tendencia("morta", None, f"🟥 TENDÊNCIA MORTA - {self.tendencia_ativa}")
        
        return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, f"Tendência ativa - {self.tendencia_ativa}")
    
    def _analisar_tendencia_enfraquecendo(self, zona_top1, acerto_ultima, zona_acertada):
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
            if self.contador_acertos_tendencia >= 2:
                self.estado_tendencia = "ativa"
                return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, f"✅ Tendência recuperada")
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        if self._detectar_morte_tendencia(zona_top1):
            self.estado_tendencia = "morta"
            return self._criar_resposta_tendencia("morta", None, "🟥 TENDÊNCIA MORTA")
        
        return self._criar_resposta_tendencia("enfraquecendo", self.tendencia_ativa, "⚠️ Tendência enfraquecendo")
    
    def _analisar_reinicio_tendencia(self, zona_top1):
        rodadas_desde_morte = len([z for z in self.historico_zonas_dominantes if z != self.tendencia_ativa])
        
        if rodadas_desde_morte >= 8:
            freq_zona_atual = list(self.historico_zonas_dominantes).count(zona_top1)
            if freq_zona_atual >= 3:
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                return self._criar_resposta_tendencia("formando", zona_top1, f"🔄 NOVA TENDÊNCIA - {zona_top1}")
        
        return self._criar_resposta_tendencia("morta", None, f"Aguardando nova tendência ({rodadas_desde_morte}/8)")
    
    def _detectar_enfraquecimento(self):
        if self.contador_erros_tendencia > 0 and self.contador_acertos_tendencia > 0:
            total_operacoes = self.contador_acertos_tendencia + self.contador_erros_tendencia
            if total_operacoes >= 3 and self.contador_erros_tendencia >= total_operacoes * 0.4:
                return True
        if self.rodadas_operando >= self.max_operacoes_por_tendencia:
            return True
        return False
    
    def _detectar_morte_tendencia(self, zona_top1):
        if self.contador_erros_tendencia >= 2:
            return True
        if (zona_top1 != self.tendencia_ativa and 
            self.tendencia_ativa not in list(self.historico_zonas_dominantes)[-3:]):
            return True
        return False
    
    def _criar_resposta_tendencia(self, estado, zona_dominante, mensagem, acao="aguardar"):
        confiancas = {'aguardando': 0.1, 'formando': 0.4, 'ativa': 0.8, 'enfraquecendo': 0.3, 'morta': 0.0}
        return {
            'estado': estado,
            'zona_dominante': zona_dominante,
            'confianca': confiancas.get(estado, 0.0),
            'acao': acao,
            'mensagem': mensagem,
            'contadores': {
                'confirmacoes': self.contador_confirmacoes,
                'acertos': self.contador_acertos_tendencia,
                'erros': self.contador_erros_tendencia,
                'operacoes': self.rodadas_operando
            }
        }
    
    def get_resumo_tendencia(self):
        return {
            'estado': self.estado_tendencia,
            'zona_ativa': self.tendencia_ativa,
            'contadores': {
                'confirmacoes': self.contador_confirmacoes,
                'acertos': self.contador_acertos_tendencia,
                'erros': self.contador_erros_tendencia,
                'operacoes': self.rodadas_operando
            },
            'historico_zonas': list(self.historico_zonas_dominantes)
        }

# =============================
# SISTEMA PRINCIPAL SIMPLIFICADO
# =============================
class RoletaInteligente:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_zona(self, numero_central, quantidade=6):
        if numero_central not in self.race:
            return []
        posicao = self.race.index(numero_central)
        vizinhos = []
        for offset in range(-quantidade, quantidade + 1):
            if offset != 0:
                vizinho = self.race[(posicao + offset) % len(self.race)]
                vizinhos.append(vizinho)
        return vizinhos

class EstrategiaZonasBasica:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.zonas = {'Vermelha': 7, 'Azul': 10, 'Amarela': 2}
        self.numeros_zonas = {}
        for nome, central in self.zonas.items():
            self.numeros_zonas[nome] = self.roleta.get_vizinhos_zona(central, 6)
        
        self.stats_zonas = {zona: {'acertos': 0, 'tentativas': 0, 'performance_media': 0} for zona in self.zonas.keys()}

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        acertou_zona = None
        for zona, numeros in self.numeros_zonas.items():
            if numero in numeros:
                self.stats_zonas[zona]['acertos'] += 1
                acertou_zona = zona
            self.stats_zonas[zona]['tentativas'] += 1
            if self.stats_zonas[zona]['tentativas'] > 0:
                self.stats_zonas[zona]['performance_media'] = (
                    self.stats_zonas[zona]['acertos'] / self.stats_zonas[zona]['tentativas'] * 100
                )
        return acertou_zona

    def get_zonas_rankeadas(self):
        if len(self.historico) < 10:
            return None
        zonas_score = {}
        for zona in self.zonas.keys():
            score = 0
            freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
            percentual_geral = freq_geral / len(self.historico)
            score += percentual_geral * 25
            
            ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
            freq_curto = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona])
            percentual_curto = freq_curto / len(ultimos_12)
            score += percentual_curto * 35
            
            if self.stats_zonas[zona]['tentativas'] > 10:
                taxa_acerto = self.stats_zonas[zona]['performance_media']
                if taxa_acerto > 40: score += 30
                elif taxa_acerto > 35: score += 25
                elif taxa_acerto > 30: score += 20
                elif taxa_acerto > 25: score += 15
                else: score += 10
            else:
                score += 10
            zonas_score[zona] = score
        
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def analisar_zonas(self):
        zonas_rankeadas = self.get_zonas_rankeadas()
        if not zonas_rankeadas:
            return None
        
        zona_primaria, score_primario = zonas_rankeadas[0]
        if score_primario < 22:
            return None
        
        numeros_apostar = self.numeros_zonas[zona_primaria]
        
        return {
            'nome': f'Zona {zona_primaria}',
            'numeros_apostar': numeros_apostar,
            'gatilho': f'Zona {zona_primaria} - Score: {score_primario:.1f}',
            'confianca': 'Alta' if score_primario > 30 else 'Média',
            'zona': zona_primaria,
            'zonas_envolvidas': [zona_primaria]
        }

class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasBasica()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategia_selecionada = "Zonas"
        
        # 🎯 ADICIONAR SISTEMA DE TENDÊNCIAS
        self.sistema_tendencias = SistemaTendencias()

    def processar_novo_numero(self, numero):
        if isinstance(numero, dict) and 'number' in numero:
            numero_real = numero['number']
        else:
            numero_real = numero
            
        if self.previsao_ativa:
            acerto = False
            zonas_acertadas = []
            nome_estrategia = self.previsao_ativa['nome']
            
            zonas_envolvidas = self.previsao_ativa.get('zonas_envolvidas', [])
            for zona in zonas_envolvidas:
                numeros_zona = self.estrategia_zonas.numeros_zonas[zona]
                if numero_real in numeros_zona:
                    acerto = True
                    zonas_acertadas.append(zona)
            
            # 🎯 ATUALIZAR ANÁLISE DE TENDÊNCIAS
            self.atualizar_analise_tendencias(numero_real, zonas_acertadas[0] if zonas_acertadas else None, acerto)
            
            if acerto:
                self.acertos += 1
            else:
                self.erros += 1
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome_estrategia,
                'zona_acertada': "+".join(zonas_acertadas) if zonas_acertadas else None
            })
            
            self.previsao_ativa = None
        
        self.estrategia_zonas.adicionar_numero(numero_real)
        
        nova_estrategia = self.estrategia_zonas.analisar_zonas()
        
        if nova_estrategia:
            self.previsao_ativa = nova_estrategia

    def atualizar_analise_tendencias(self, numero, zona_acertada=None, acerto_ultima=False):
        try:
            zonas_rankeadas = self.estrategia_zonas.get_zonas_rankeadas()
            if not zonas_rankeadas:
                return
            
            analise_tendencia = self.sistema_tendencias.analisar_tendencia(
                zonas_rankeadas, acerto_ultima, zona_acertada
            )
            
            self.sistema_tendencias.historico_tendencias.append(analise_tendencia)
            
        except Exception as e:
            logging.error(f"Erro na análise de tendências: {e}")

    def get_analise_tendencias_completa(self):
        analise = "🎯 SISTEMA DE DETECÇÃO DE TENDÊNCIAS\n"
        analise += "=" * 50 + "\n"
        
        resumo = self.sistema_tendencias.get_resumo_tendencia()
        
        analise += f"📊 ESTADO ATUAL: {resumo['estado'].upper()}\n"
        analise += f"📍 ZONA ATIVA: {resumo['zona_ativa'] or 'Nenhuma'}\n"
        analise += f"🎯 CONTADORES: {resumo['contadores']['acertos']} acertos, {resumo['contadores']['erros']} erros\n"
        analise += f"📈 CONFIRMAÇÕES: {resumo['contadores']['confirmacoes']}\n"
        
        analise += "\n📋 HISTÓRICO RECENTE DE ZONAS:\n"
        for i, zona in enumerate(resumo['historico_zonas'][-8:]):
            analise += f"  {i+1:2d}. {zona}\n"
        
        if self.sistema_tendencias.historico_tendencias:
            ultima = self.sistema_tendencias.historico_tendencias[-1]
            analise += f"\n📝 ÚLTIMA ANÁLISE:\n"
            analise += f"  Estado: {ultima['estado']}\n"
            analise += f"  Confiança: {ultima['confianca']:.0%}\n"
            analise += f"  Ação: {ultima['acao'].upper()}\n"
            analise += f"  Mensagem: {ultima['mensagem']}\n"
        
        return analise

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_sessao():
    try:
        session_data = {
            'historico': st.session_state.historico,
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'zonas_historico': list(st.session_state.sistema.estrategia_zonas.historico),
            'zonas_stats': st.session_state.sistema.estrategia_zonas.stats_zonas,
            'sistema_tendencias_estado': st.session_state.sistema.sistema_tendencias.estado_tendencia,
            'sistema_tendencias_ativa': st.session_state.sistema.sistema_tendencias.tendencia_ativa,
            'sistema_tendencias_confirmacoes': st.session_state.sistema.sistema_tendencias.contador_confirmacoes,
            'sistema_tendencias_acertos': st.session_state.sistema.sistema_tendencias.contador_acertos_tendencia,
            'sistema_tendencias_erros': st.session_state.sistema.sistema_tendencias.contador_erros_tendencia,
            'sistema_tendencias_historico_zonas': list(st.session_state.sistema.sistema_tendencias.historico_zonas_dominantes)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info("✅ Sessão salva com sucesso")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}")
        return False

def carregar_sessao():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                session_data = pickle.load(f)
            
            st.session_state.historico = session_data.get('historico', [])
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                
                zonas_historico = session_data.get('zonas_historico', [])
                st.session_state.sistema.estrategia_zonas.historico = deque(zonas_historico, maxlen=70)
                st.session_state.sistema.estrategia_zonas.stats_zonas = session_data.get('zonas_stats', {
                    'Vermelha': {'acertos': 0, 'tentativas': 0, 'performance_media': 0},
                    'Azul': {'acertos': 0, 'tentativas': 0, 'performance_media': 0},
                    'Amarela': {'acertos': 0, 'tentativas': 0, 'performance_media': 0}
                })
                
                st.session_state.sistema.sistema_tendencias.estado_tendencia = session_data.get('sistema_tendencias_estado', 'aguardando')
                st.session_state.sistema.sistema_tendencias.tendencia_ativa = session_data.get('sistema_tendencias_ativa', None)
                st.session_state.sistema.sistema_tendencias.contador_confirmacoes = session_data.get('sistema_tendencias_confirmacoes', 0)
                st.session_state.sistema.sistema_tendencias.contador_acertos_tendencia = session_data.get('sistema_tendencias_acertos', 0)
                st.session_state.sistema.sistema_tendencias.contador_erros_tendencia = session_data.get('sistema_tendencias_erros', 0)
                
                tendencias_historico_zonas = session_data.get('sistema_tendencias_historico_zonas', [])
                st.session_state.sistema.sistema_tendencias.historico_zonas_dominantes = deque(tendencias_historico_zonas, maxlen=10)
            
            logging.info("✅ Sessão carregada com sucesso")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
    return False

def enviar_alerta_tendencia(analise_tendencia):
    estado = analise_tendencia['estado']
    zona = analise_tendencia['zona_dominante']
    mensagem = analise_tendencia['mensagem']
    
    if estado == "ativa" and analise_tendencia['acao'] == "operar":
        st.toast("🎯 TENDÊNCIA CONFIRMADA - OPERAR!", icon="🔥")
        st.success(f"📈 {mensagem}")
    elif estado == "enfraquecendo":
        st.toast("⚠️ TENDÊNCIA ENFRAQUECENDO", icon="⚠️")
        st.warning(f"📉 {mensagem}")
    elif estado == "morta":
        st.toast("🟥 TENDÊNCIA MORTA - PARAR", icon="🛑")
        st.error(f"💀 {mensagem}")

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="IA Roleta — Sistema de Tendências", layout="centered")
st.title("🎯 IA Roleta — Sistema de Tendências")

# Inicialização
if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaCompleto()

if "historico" not in st.session_state:
    st.session_state.historico = []

# Carregar sessão
sessao_carregada = carregar_sessao()

# Sidebar
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("💾 Gerenciamento de Sessão"):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Salvar Sessão"):
            salvar_sessao()
            st.success("✅ Sessão salva!")
    with col2:
        if st.button("🔄 Carregar Sessão"):
            if carregar_sessao():
                st.success("✅ Sessão carregada!")
                st.rerun()

# Entrada de números
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Digite números (0-36) separados por espaço:")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(n)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# Atualização automática
st_autorefresh(interval=5000, key="refresh")

# Interface principal
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(numeros_str)
else:
    st.write("Nenhum número registrado")

# 🎯 NOVA SEÇÃO: ANÁLISE DE TENDÊNCIAS
st.subheader("📈 Análise de Tendências")

tendencia_analise = st.session_state.sistema.get_analise_tendencias_completa()
st.text_area("Estado da Tendência", tendencia_analise, height=300, key="tendencia_analise")

col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.button("🔄 Atualizar Análise"):
        zonas_rankeadas = st.session_state.sistema.estrategia_zonas.get_zonas_rankeadas()
        if zonas_rankeadas:
            analise = st.session_state.sistema.sistema_tendencias.analisar_tendencia(zonas_rankeadas)
            st.success(f"Análise atualizada: {analise['mensagem']}")
            st.rerun()

# Alertas de tendência
if (st.session_state.sistema.sistema_tendencias.historico_tendencias and 
    len(st.session_state.sistema.sistema_tendencias.historico_tendencias) > 0):
    
    ultima_analise = st.session_state.sistema.sistema_tendencias.historico_tendencias[-1]
    if ultima_analise['estado'] in ['ativa', 'enfraquecendo', 'morta']:
        enviar_alerta_tendencia(ultima_analise)

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if 'Zonas' in previsao['nome']:
        zonas_envolvidas = previsao.get('zonas_envolvidas', [])
        if len(zonas_envolvidas) > 0:
            zona = zonas_envolvidas[0]
            if zona == 'Vermelha':
                nucleo = "7"
            elif zona == 'Azul':
                nucleo = "10"
            elif zona == 'Amarela':
                nucleo = "2"
            else:
                nucleo = zona
            st.write(f"**📍 Núcleo:** {nucleo}")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    st.write(", ".join(map(str, sorted(previsao['numeros_apostar']))))
    
    st.info("⏳ Aguardando próximo sorteio...")
else:
    st.info("🎲 Analisando padrões...")

# Desempenho
st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

# Últimas conferências
if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for i, resultado in enumerate(sistema.historico_desempenho[-5:]):
        emoji = "🎉" if resultado['acerto'] else "❌"
        zona_info = f" ({resultado['zona_acertada']})" if resultado['zona_acertada'] else ""
        st.write(f"{emoji} {resultado['estrategia']}: Número {resultado['numero']}{zona_info}")

# Salvar sessão ao final
salvar_sessao()
