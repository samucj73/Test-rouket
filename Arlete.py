
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
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"
ML_MODEL_PATH = "ml_roleta_model.pkl"
SCALER_PATH = "ml_scaler.pkl"
META_PATH = "ml_meta.pkl"

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        session_data = {
            'historico': st.session_state.historico,
            'telegram_token': st.session_state.telegram_token,
            'telegram_chat_id': st.session_state.telegram_chat_id,
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_estrategias_contador': st.session_state.sistema.estrategias_contador,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'sistema_contador_sorteios_global': st.session_state.sistema.contador_sorteios_global,
            'sistema_sequencia_erros': st.session_state.sistema.sequencia_erros,
            'sistema_ultima_estrategia_erro': st.session_state.sistema.ultima_estrategia_erro,
            # NOVO: Dados da estratégia de 3 acertos
            'sistema_sequencia_acertos': st.session_state.sistema.sequencia_acertos,
            'sistema_ultima_combinacao_acerto': st.session_state.sistema.ultima_combinacao_acerto,
            'sistema_historico_combinacoes_acerto': st.session_state.sistema.historico_combinacoes_acerto,
            # Dados da estratégia Zonas
            'zonas_historico': list(st.session_state.sistema.estrategia_zonas.historico),
            'zonas_stats': st.session_state.sistema.estrategia_zonas.stats_zonas,
            # Dados da estratégia Midas
            'midas_historico': list(st.session_state.sistema.estrategia_midas.historico),
            # Dados da estratégia ML
            'ml_historico': list(st.session_state.sistema.estrategia_ml.historico),
            'ml_contador_sorteios': st.session_state.sistema.estrategia_ml.contador_sorteios,
            'ml_sequencias_padroes': st.session_state.sistema.estrategia_ml.sequencias_padroes,
            'ml_metricas_padroes': st.session_state.sistema.estrategia_ml.metricas_padroes,
            'estrategia_selecionada': st.session_state.sistema.estrategia_selecionada,
            # Dados das combinações dinâmicas
            'sistema_historico_combinacoes': st.session_state.sistema.historico_combinacoes,
            'sistema_combinacoes_quentes': st.session_state.sistema.combinacoes_quentes,
            'sistema_combinacoes_frias': st.session_state.sistema.combinacoes_frias,
            # 🎯 NOVO: Dados do sistema de tendências
            'sistema_tendencias_historico': list(st.session_state.sistema.sistema_tendencias.historico_tendencias),
            'sistema_tendencias_estado': st.session_state.sistema.sistema_tendencias.estado_tendencia,
            'sistema_tendencias_ativa': st.session_state.sistema.sistema_tendencias.tendencia_ativa,
            'sistema_tendencias_confirmacoes': st.session_state.sistema.sistema_tendencias.contador_confirmacoes,
            'sistema_tendencias_acertos': st.session_state.sistema.sistema_tendencias.contador_acertos_tendencia,
            'sistema_tendencias_erros': st.session_state.sistema.sistema_tendencias.contador_erros_tendencia,
            'sistema_tendencias_operacoes': st.session_state.sistema.sistema_tendencias.rodadas_operando,
            'sistema_tendencias_historico_zonas': list(st.session_state.sistema.sistema_tendencias.historico_zonas_dominantes),
            # 🎯 NOVO: Dados do sistema de foco dinâmico
            'sistema_combinacoes_em_alta': st.session_state.sistema.combinacoes_em_alta,
            'sistema_combinacoes_em_baixa': st.session_state.sistema.combinacoes_em_baixa,
            'sistema_historico_performance': st.session_state.sistema.historico_performance,
            'sistema_ultima_analise_performance': st.session_state.sistema.ultima_analise_performance
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info("✅ Sessão salva com sucesso")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}")
        return False

def carregar_sessao():
    """Carrega todos os dados da sessão do arquivo"""
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                session_data = pickle.load(f)
            
            if not isinstance(session_data, dict):
                logging.error("❌ Dados de sessão corrompidos - não é um dicionário")
                return False
                
            chaves_essenciais = ['historico', 'sistema_acertos', 'sistema_erros']
            if not all(chave in session_data for chave in chaves_essenciais):
                logging.error("❌ Dados de sessão incompletos")
                return False
                
            st.session_state.historico = session_data.get('historico', [])
            st.session_state.telegram_token = session_data.get('telegram_token', '')
            st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
            
            if 'sistema' in st.session_state:
                estrategias_contador = session_data.get('sistema_estrategias_contador', {})
                if not isinstance(estrategias_contador, dict):
                    estrategias_contador = {}
                    
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.estrategias_contador = estrategias_contador
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.contador_sorteios_global = session_data.get('sistema_contador_sorteios_global', 0)
                st.session_state.sistema.sequencia_erros = session_data.get('sistema_sequencia_erros', 0)
                st.session_state.sistema.ultima_estrategia_erro = session_data.get('sistema_ultima_estrategia_erro', '')
                
                # NOVO: Carregar dados da estratégia de 3 acertos
                st.session_state.sistema.sequencia_acertos = session_data.get('sistema_sequencia_acertos', 0)
                st.session_state.sistema.ultima_combinacao_acerto = session_data.get('sistema_ultima_combinacao_acerto', [])
                st.session_state.sistema.historico_combinacoes_acerto = session_data.get('sistema_historico_combinacoes_acerto', [])
                
                st.session_state.sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Zonas')
                
                st.session_state.sistema.historico_combinacoes = session_data.get('sistema_historico_combinacoes', {})
                st.session_state.sistema.combinacoes_quentes = session_data.get('sistema_combinacoes_quentes', [])
                st.session_state.sistema.combinacoes_frias = session_data.get('sistema_combinacoes_frias', [])
                
                # 🎯 NOVO: Carregar dados do sistema de foco dinâmico
                st.session_state.sistema.combinacoes_em_alta = session_data.get('sistema_combinacoes_em_alta', [])
                st.session_state.sistema.combinacoes_em_baixa = session_data.get('sistema_combinacoes_em_baixa', [])
                st.session_state.sistema.historico_performance = session_data.get('sistema_historico_performance', {})
                st.session_state.sistema.ultima_analise_performance = session_data.get('sistema_ultima_analise_performance', None)
                
                zonas_historico = session_data.get('zonas_historico', [])
                st.session_state.sistema.estrategia_zonas.historico = deque(zonas_historico, maxlen=70)
                st.session_state.sistema.estrategia_zonas.stats_zonas = session_data.get('zonas_stats', {
                    'Vermelha': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                    'Azul': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                    'Amarela': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
                })
                
                midas_historico = session_data.get('midas_historico', [])
                st.session_state.sistema.estrategia_midas.historico = deque(midas_historico, maxlen=15)
                
                ml_historico = session_data.get('ml_historico', [])
                st.session_state.sistema.estrategia_ml.historico = deque(ml_historico, maxlen=30)
                st.session_state.sistema.estrategia_ml.contador_sorteios = session_data.get('ml_contador_sorteios', 0)
                st.session_state.sistema.estrategia_ml.sequencias_padroes = session_data.get('ml_sequencias_padroes', {
                    'sequencias_ativas': {},
                    'historico_sequencias': [],
                    'padroes_detectados': []
                })
                st.session_state.sistema.estrategia_ml.metricas_padroes = session_data.get('ml_metricas_padroes', {
                    'padroes_detectados_total': 0,
                    'padroes_acertados': 0,
                    'padroes_errados': 0,
                    'eficiencia_por_tipo': {},
                    'historico_validacao': []
                })
                
                # 🎯 NOVO: Carregar dados do sistema de tendências
                tendencias_historico = session_data.get('sistema_tendencias_historico', [])
                st.session_state.sistema.sistema_tendencias.historico_tendencias = deque(tendencias_historico, maxlen=50)
                st.session_state.sistema.sistema_tendencias.estado_tendencia = session_data.get('sistema_tendencias_estado', 'aguardando')
                st.session_state.sistema.sistema_tendencias.tendencia_ativa = session_data.get('sistema_tendencias_ativa', None)
                st.session_state.sistema.sistema_tendencias.contador_confirmacoes = session_data.get('sistema_tendencias_confirmacoes', 0)
                st.session_state.sistema.sistema_tendencias.contador_acertos_tendencia = session_data.get('sistema_tendencias_acertos', 0)
                st.session_state.sistema.sistema_tendencias.contador_erros_tendencia = session_data.get('sistema_tendencias_erros', 0)
                st.session_state.sistema.sistema_tendencias.rodadas_operando = session_data.get('sistema_tendencias_operacoes', 0)
                
                tendencias_historico_zonas = session_data.get('sistema_tendencias_historico_zonas', [])
                st.session_state.sistema.sistema_tendencias.historico_zonas_dominantes = deque(tendencias_historico_zonas, maxlen=10)
            
            logging.info("✅ Sessão carregada com sucesso")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
    return False

def limpar_sessao():
    """Limpa todos os dados da sessão"""
    try:
        if os.path.exists(SESSION_DATA_PATH):
            os.remove(SESSION_DATA_PATH)
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
        logging.info("🗑️ Sessão limpa com sucesso")
    except Exception as e:
        logging.error(f"❌ Erro ao limpar sessão: {e}")

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================
def enviar_previsao_super_simplificada(previsao):
    """Envia notificação de previsão super simplificada"""
    try:
        nome_estrategia = previsao['nome']
        numeros_apostar = sorted(previsao['numeros_apostar'])
        
        if 'Zonas' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            confianca = previsao.get('confianca', 'Média')
            
            if len(zonas_envolvidas) > 1:
                nucleo1 = "7" if zonas_envolvidas[0] == 'Vermelha' else "10" if zonas_envolvidas[0] == 'Azul' else "2"
                nucleo2 = "7" if zonas_envolvidas[1] == 'Vermelha' else "10" if zonas_envolvidas[1] == 'Azul' else "2"
                mensagem = f"🔥 NÚCLEOS {nucleo1}+{nucleo2} - CONFIANÇA {confianca.upper()}"
                
                sistema = st.session_state.sistema
                combinacao = tuple(sorted(zonas_envolvidas))
                if hasattr(sistema, 'combinacoes_quentes') and combinacao in sistema.combinacoes_quentes:
                    dados = sistema.historico_combinacoes.get(combinacao, {})
                    eff = dados.get('eficiencia', 0)
                    mensagem += f" 🏆 COMBO EFICIENTE ({eff:.1f}%)"
                    
            else:
                zona = previsao.get('zona', '')
                nucleo = "7" if zona == 'Vermelha' else "10" if zona == 'Azul' else "2"
                mensagem = f"🎯 NÚCLEO {nucleo} - CONFIANÇA {confianca.upper()}"
            
        elif 'Machine Learning' in nome_estrategia or 'ML' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            confianca = previsao.get('confianca', 'Média')
            
            if len(zonas_envolvidas) > 1:
                nucleo1 = "7" if zonas_envolvidas[0] == 'Vermelha' else "10" if zonas_envolvidas[0] == 'Azul' else "2"
                nucleo2 = "7" if zonas_envolvidas[1] == 'Vermelha' else "10" if zonas_envolvidas[1] == 'Azul' else "2"
                mensagem = f"🤖 NÚCLEOS {nucleo1}+{nucleo2} - CONFIANÇA {confianca.upper()}"
            else:
                zona_ml = previsao.get('zona_ml', '')
                nucleo = "7" if zona_ml == 'Vermelha' else "10" if zona_ml == 'Azul' else "2"
                mensagem = f"🤖 NÚCLEO {nucleo} - CONFIANÇA {confianca.upper()}"
        
        else:
            mensagem = f"💰 {previsao['nome']} - APOSTAR AGORA"
        
        st.toast(f"🎯 PREVISÃO CONFIRMADA", icon="🔥")
        st.warning(f"🔔 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_alerta_numeros_simplificado(previsao)
                enviar_telegram(f"🚨 PREVISÃO ATIVA\n{mensagem}\n💎 CONFIANÇA: {previsao.get('confianca', 'ALTA')}")
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_alerta_numeros_simplificado(previsao):
    """Envia alerta alternativo super simplificado com os números para apostar"""
    try:
        nome_estrategia = previsao['nome']
        numeros_apostar = sorted(previsao['numeros_apostar'])
        
        metade = len(numeros_apostar) // 2
        linha1 = " ".join(map(str, numeros_apostar[:metade]))
        linha2 = " ".join(map(str, numeros_apostar[metade:]))
        
        if 'Zonas' in nome_estrategia:
            emoji = "🔥"
        elif 'ML' in nome_estrategia:
            emoji = "🤖"
        else:
            emoji = "💰"
            
        mensagem_simplificada = f"{emoji} APOSTAR AGORA\n{linha1}\n{linha2}"
        
        enviar_telegram(mensagem_simplificada)
        logging.info("🔔 Alerta simplificado enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta simplificado: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    """Envia notificação de resultado super simplificado"""
    try:
        if acerto:
            if 'Zonas' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha':
                            nucleos.append("7")
                        elif zona == 'Azul':
                            nucleos.append("10")
                        elif zona == 'Amarela':
                            nucleos.append("2")
                        else:
                            nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            elif 'ML' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha':
                            nucleos.append("7")
                        elif zona == 'Azul':
                            nucleos.append("10")
                        elif zona == 'Amarela':
                            nucleos.append("2")
                        else:
                            nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            else:
                mensagem = f"✅ Acerto\n🎲 Número: {numero_real}"
        else:
            mensagem = f"❌ Erro\n🎲 Número: {numero_real}"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        st.success(f"📢 {mensagem}") if acerto else st.error(f"📢 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"📢 RESULTADO\n{mensagem}")
                enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia)
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia):
    """Envia alerta de conferência super simplificado"""
    try:
        if acerto:
            mensagem = f"🎉 ACERTOU! {numero_real}"
        else:
            mensagem = f"💥 ERROU! {numero_real}"
            
        enviar_telegram(mensagem)
        logging.info("🔔 Alerta de conferência enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta de conferência: {e}")

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova):
    """Envia notificação de rotação automática"""
    try:
        mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(f"🔄 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"🔄 ROTAÇÃO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

# NOVA FUNÇÃO: Notificação para rotação por 3 acertos
def enviar_rotacao_por_acertos_combinacoes(combinacao_anterior, combinacao_nova):
    """Envia notificação de rotação por acertos em combinações"""
    try:
        def combo_para_nucleos(combo):
            nucleos = []
            for zona in combo:
                if zona == 'Vermelha':
                    nucleos.append("7")
                elif zona == 'Azul':
                    nucleos.append("10") 
                elif zona == 'Amarela':
                    nucleos.append("2")
                else:
                    nucleos.append(zona)
            return "+".join(nucleos)
        
        nucleo_anterior = combo_para_nucleos(combinacao_anterior)
        nucleo_novo = combo_para_nucleos(combinacao_nova)
        
        mensagem = f"🎯 ROTAÇÃO POR 3 ACERTOS SEGUIDOS\nNúcleos {nucleo_anterior} → Núcleos {nucleo_novo}\n✅ 3 acertos consecutivos - Alternando combinações"
        
        st.toast("🎯 Rotação por Acertos", icon="✅")
        st.success(f"🎯 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"🎯 ROTAÇÃO POR ACERTOS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação por acertos: {e}")

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    try:
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info("Mensagem enviada para Telegram com sucesso")
        else:
            logging.error(f"Erro ao enviar para Telegram: {response.status_code}")
    except Exception as e:
        logging.error(f"Erro na conexão com Telegram: {e}")

# =============================
# SISTEMA DE DETECÇÃO DE TENDÊNCIAS
# =============================
class SistemaTendencias:
    def __init__(self):
        self.historico_tendencias = deque(maxlen=50)
        self.tendencia_ativa = None
        self.estado_tendencia = "aguardando"  # aguardando, formando, ativa, enfraquecendo, morta
        self.contador_confirmacoes = 0
        self.contador_erros_tendencia = 0
        self.contador_acertos_tendencia = 0
        self.ultima_zona_dominante = None
        self.historico_zonas_dominantes = deque(maxlen=10)
        self.rodadas_operando = 0
        self.max_operacoes_por_tendencia = 4
        
    def analisar_tendencia(self, zonas_rankeadas, acerto_ultima=False, zona_acertada=None):
        """
        Analisa a tendência atual baseado no fluxograma
        
        Retorna: {
            'estado': 'aguardando'|'formando'|'ativa'|'enfraquecendo'|'morta',
            'zona_dominante': str,
            'confianca': float,
            'acao': 'operar'|'aguardar'|'parar',
            'mensagem': str
        }
        """
        if not zonas_rankeadas or len(zonas_rankeadas) < 2:
            return self._criar_resposta_tendencia("aguardando", None, "Aguardando dados suficientes")
        
        zona_top1, score_top1 = zonas_rankeadas[0]
        zona_top2, score_top2 = zonas_rankeadas[1] if len(zonas_rankeadas) > 1 else (None, 0)
        
        # Registrar zona dominante atual
        self.historico_zonas_dominantes.append(zona_top1)
        
        # 1. VERIFICAR SE TENDÊNCIA ESTÁ SE FORMANDO
        if self.estado_tendencia in ["aguardando", "formando"]:
            return self._analisar_formacao_tendencia(zona_top1, zona_top2, score_top1, zonas_rankeadas)
        
        # 2. VERIFICAR SE TENDÊNCIA ESTÁ ATIVA
        elif self.estado_tendencia == "ativa":
            return self._analisar_tendencia_ativa(zona_top1, zona_top2, acerto_ultima, zona_acertada)
        
        # 3. VERIFICAR SE TENDÊNCIA ESTÁ ENFRAQUECENDO
        elif self.estado_tendencia == "enfraquecendo":
            return self._analisar_tendencia_enfraquecendo(zona_top1, zona_top2, acerto_ultima, zona_acertada)
        
        # 4. VERIFICAR SE TENDÊNCIA ESTÁ MORTA
        elif self.estado_tendencia == "morta":
            return self._analisar_reinicio_tendencia(zona_top1, zonas_rankeadas)
        
        return self._criar_resposta_tendencia("aguardando", None, "Estado não reconhecido")
    
    def _analisar_formacao_tendencia(self, zona_top1, zona_top2, score_top1, zonas_rankeadas):
        """Etapa 2 do fluxograma - Formação da Tendência"""
        
        # Verificar se a mesma zona aparece repetidamente
        freq_zona_top1 = list(self.historico_zonas_dominantes).count(zona_top1)
        frequencia_minima = 3 if len(self.historico_zonas_dominantes) >= 5 else 2
        
        # Verificar dispersão (se outras zonas estão fracas)
        dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
        
        if (freq_zona_top1 >= frequencia_minima and 
            score_top1 >= 25 and  # Score mínimo para considerar dominante
            dispersao <= 0.6):    # Baixa dispersão = zonas concentradas
            
            if self.estado_tendencia == "aguardando":
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                
                return self._criar_resposta_tendencia(
                    "formando", zona_top1, 
                    f"Tendência se formando - Zona {zona_top1} aparecendo repetidamente"
                )
            
            elif self.estado_tendencia == "formando":
                self.contador_confirmacoes += 1
                
                if self.contador_confirmacoes >= 2:
                    self.estado_tendencia = "ativa"
                    self.contador_acertos_tendencia = 0
                    self.contador_erros_tendencia = 0
                    self.rodadas_operando = 0
                    
                    return self._criar_resposta_tendencia(
                        "ativa", zona_top1,
                        f"✅ TENDÊNCIA CONFIRMADA - Zona {zona_top1} dominante. Pode operar!"
                    )
        
        return self._criar_resposta_tendencia(
            self.estado_tendencia, self.tendencia_ativa,
            f"Aguardando confirmação - {zona_top1} no Top 1"
        )
    
    def _analisar_tendencia_ativa(self, zona_top1, zona_top2, acerto_ultima, zona_acertada):
        """Etapa 3-4 do fluxograma - Tendência Ativa e Hora de Operar"""
        
        # Verificar se ainda é a mesma zona dominante
        mesma_zona = zona_top1 == self.tendencia_ativa
        
        # Atualizar contadores baseado no último resultado
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        self.rodadas_operando += 1
        
        # 🔥 HORA DE OPERAR (se ainda dentro dos limites)
        if (self.contador_acertos_tendencia >= 1 and 
            self.contador_erros_tendencia == 0 and
            self.rodadas_operando <= self.max_operacoes_por_tendencia):
            
            acao = "operar" if mesma_zona else "aguardar"
            mensagem = f"🔥 OPERAR - Tendência {self.tendencia_ativa} forte ({self.contador_acertos_tendencia} acertos)"
            
            return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, mensagem, acao)
        
        # ⚠️ VERIFICAR ENFRAQUECIMENTO
        sinais_enfraquecimento = self._detectar_enfraquecimento(zona_top1, zona_top2, acerto_ultima)
        
        if sinais_enfraquecimento:
            self.estado_tendencia = "enfraquecendo"
            return self._criar_resposta_tendencia(
                "enfraquecendo", self.tendencia_ativa,
                f"⚠️ Tendência enfraquecendo - {sinais_enfraquecimento}"
            )
        
        # 🟥 VERIFICAR SE TENDÊNCIA MORREU
        if self._detectar_morte_tendencia(zona_top1):
            self.estado_tendencia = "morta"
            return self._criar_resposta_tendencia(
                "morta", None,
                f"🟥 TENDÊNCIA MORTA - {self.tendencia_ativa} não é mais dominante"
            )
        
        return self._criar_resposta_tendencia(
            "ativa", self.tendencia_ativa,
            f"Tendência ativa - {self.tendencia_ativa} ({self.contador_acertos_tendencia} acertos, {self.contador_erros_tendencia} erros)"
        )
    
    def _analisar_tendencia_enfraquecendo(self, zona_top1, zona_top2, acerto_ultima, zona_acertada):
        """Etapa 5 do fluxograma - Tendência Enfraquecendo"""
        
        # Atualizar contadores
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
            
            # Se recuperou, voltar para ativa
            if self.contador_acertos_tendencia >= 2:
                self.estado_tendencia = "ativa"
                return self._criar_resposta_tendencia(
                    "ativa", self.tendencia_ativa,
                    f"✅ Tendência recuperada - {self.tendencia_ativa} voltou forte"
                )
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        # 🟥 VERIFICAR MORTE DEFINITIVA
        if self._detectar_morte_tendencia(zona_top1):
            self.estado_tendencia = "morta"
            return self._criar_resposta_tendencia(
                "morta", None,
                f"🟥 TENDÊNCIA MORTA a partir do estado enfraquecido"
            )
        
        return self._criar_resposta_tendencia(
            "enfraquecendo", self.tendencia_ativa,
            f"⚠️ Tendência enfraquecendo - {self.tendencia_ativa} (cuidado)"
        )
    
    def _analisar_reinicio_tendencia(self, zona_top1, zonas_rankeadas):
        """Etapa 7 do fluxograma - Reinício e Nova Tendência"""
        
        # Aguardar rodadas suficientes após morte da tendência
        rodadas_desde_morte = len([z for z in self.historico_zonas_dominantes if z != self.tendencia_ativa])
        
        if rodadas_desde_morte >= 8:  # Aguardar 8-10 rodadas
            # Verificar se nova tendência está se formando
            freq_zona_atual = list(self.historico_zonas_dominantes).count(zona_top1)
            dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
            
            if freq_zona_atual >= 3 and dispersao <= 0.6:
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                
                return self._criar_resposta_tendencia(
                    "formando", zona_top1,
                    f"🔄 NOVA TENDÊNCIA se formando - {zona_top1}"
                )
        
        return self._criar_resposta_tendencia(
            "morta", None,
            f"🔄 Aguardando nova tendência ({rodadas_desde_morte}/8 rodadas)"
        )
    
    def _detectar_enfraquecimento(self, zona_top1, zona_top2, acerto_ultima):
        """Detecta sinais de enfraquecimento da tendência"""
        sinais = []
        
        # 1. Zona dominante saindo do Top 1
        if zona_top1 != self.tendencia_ativa:
            sinais.append("zona saiu do Top 1")
        
        # 2. Nova zona aparecendo forte no Top 2
        if (zona_top2 and zona_top2 != self.tendencia_ativa and 
            zona_top2 not in [self.tendencia_ativa, zona_top1]):
            sinais.append("nova zona no Top 2")
        
        # 3. Padrão de alternância (acerta/erra)
        if self.contador_erros_tendencia > 0 and self.contador_acertos_tendencia > 0:
            total_operacoes = self.contador_acertos_tendencia + self.contador_erros_tendencia
            if total_operacoes >= 3 and self.contador_erros_tendencia >= total_operacoes * 0.4:
                sinais.append("padrão acerta/erra")
        
        # 4. Muitas operações já realizadas
        if self.rodadas_operando >= self.max_operacoes_por_tendencia:
            sinais.append("máximo de operações atingido")
        
        return " | ".join(sinais) if sinais else None
    
    def _detectar_morte_tendencia(self, zona_top1):
        """Detecta se a tendência morreu completamente"""
        
        # 1. Dois erros seguidos
        if self.contador_erros_tendencia >= 2:
            return True
        
        # 2. Zona dominante sumiu dos primeiros lugares
        if (zona_top1 != self.tendencia_ativa and 
            self.tendencia_ativa not in list(self.historico_zonas_dominantes)[-3:]):
            return True
        
        # 3. Muitas zonas diferentes aparecendo
        zonas_recentes = list(self.historico_zonas_dominantes)[-5:]
        zonas_unicas = len(set(zonas_recentes))
        if len(zonas_recentes) >= 3 and zonas_unicas >= 3:
            return True
        
        # 4. Taxa de acertos baixa
        total_tentativas = self.contador_acertos_tendencia + self.contador_erros_tendencia
        if total_tentativas >= 3:
            taxa_acertos = self.contador_acertos_tendencia / total_tentativas
            if taxa_acertos < 0.5:  # Menos de 50% de acertos
                return True
        
        return False
    
    def _calcular_dispersao_zonas(self, zonas_rankeadas):
        """Calcula o nível de dispersão entre as zonas (0-1, onde 0 é concentrado, 1 é disperso)"""
        if not zonas_rankeadas:
            return 1.0
        
        scores = [score for _, score in zonas_rankeadas[:4]]  # Top 4 zonas
        if not scores:
            return 1.0
        
        max_score = max(scores)
        if max_score == 0:
            return 1.0
        
        # Normalizar scores
        scores_normalizados = [score / max_score for score in scores]
        
        # Dispersão é o desvio padrão dos scores normalizados
        dispersao = np.std(scores_normalizados) if len(scores_normalizados) > 1 else 0
        return dispersao
    
    def _criar_resposta_tendencia(self, estado, zona_dominante, mensagem, acao="aguardar"):
        """Cria resposta padronizada da análise de tendência"""
        return {
            'estado': estado,
            'zona_dominante': zona_dominante,
            'confianca': self._calcular_confianca_tendencia(estado),
            'acao': acao,
            'mensagem': mensagem,
            'contadores': {
                'confirmacoes': self.contador_confirmacoes,
                'acertos': self.contador_acertos_tendencia,
                'erros': self.contador_erros_tendencia,
                'operacoes': self.rodadas_operando
            }
        }
    
    def _calcular_confianca_tendencia(self, estado):
        """Calcula nível de confiança baseado no estado da tendência"""
        confiancas = {
            'aguardando': 0.1,
            'formando': 0.4,
            'ativa': 0.8,
            'enfraquecendo': 0.3,
            'morta': 0.0
        }
        return confiancas.get(estado, 0.0)
    
    def get_resumo_tendencia(self):
        """Retorna resumo atual do estado da tendência"""
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
# CONFIGURAÇÕES
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# SISTEMA DE SELEÇÃO INTELIGENTE DE NÚMEROS
# =============================
class SistemaSelecaoInteligente:
    def __init__(self):
        self.roleta = RoletaInteligente()
        
    def selecionar_melhores_15_numeros(self, numeros_candidatos, historico, estrategia_tipo="Zonas"):
        if len(numeros_candidatos) <= 15:
            return numeros_candidatos
            
        scores = {}
        for numero in numeros_candidatos:
            scores[numero] = self.calcular_score_numero(numero, historico, estrategia_tipo)
        
        numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhores_15 = [num for num, score in numeros_ordenados[:15]]
        
        logging.info(f"🎯 Seleção Inteligente: {len(numeros_candidatos)} → 15 números")
        return melhores_15
    
    def calcular_score_numero(self, numero, historico, estrategia_tipo):
        score_total = 0
        
        score_frequencia = self.calcular_score_frequencia(numero, historico)
        score_total += score_frequencia * 0.45
        
        score_posicao = self.calcular_score_posicao_roda(numero, historico)
        score_total += score_posicao * 0.20
        
        score_vizinhos = self.calcular_score_vizinhos(numero, historico)
        score_total += score_vizinhos * 0.25
        
        score_tendencia = self.calcular_score_tendencia(numero, historico)
        score_total += score_tendencia * 0.10
        
        return score_total
    
    def calcular_score_frequencia(self, numero, historico):
        if len(historico) < 3:
            return 0.7
            
        historico_lista = list(historico)
        
        janela_curta = historico_lista[-8:] if len(historico_lista) >= 8 else historico_lista
        freq_curta = sum(1 for n in janela_curta if n == numero) / len(janela_curta)
        
        janela_media = historico_lista[-20:] if len(historico_lista) >= 20 else historico_lista
        freq_media = sum(1 for n in janela_media if n == numero) / len(janela_media)
        
        janela_longa = historico_lista[-40:] if len(historico_lista) >= 40 else historico_lista
        freq_longa = sum(1 for n in janela_longa if n == numero) / len(janela_longa)
        
        score = (freq_curta * 0.7 + freq_media * 0.2 + freq_longa * 0.1)
        return min(score * 4, 1.0)
    
    def calcular_score_posicao_roda(self, numero, historico):
        if len(historico) < 3:
            return 0.5
            
        ultimo_numero = historico[-1] if historico else 0
        penultimo_numero = historico[-2] if len(historico) >= 2 else ultimo_numero
        
        posicao_alvo = self.roleta.get_posicao_race(numero)
        posicao_ultimo = self.roleta.get_posicao_race(ultimo_numero)
        posicao_penultimo = self.roleta.get_posicao_race(penultimo_numero)
        
        dist_ultimo = self.calcular_distancia_roda(posicao_alvo, posicao_ultimo)
        score_dist_ultimo = max(0, 1 - (dist_ultimo / 18))
        
        dist_penultimo = self.calcular_distancia_roda(posicao_alvo, posicao_penultimo)
        score_dist_penultimo = max(0, 1 - (dist_penultimo / 18))
        
        score_final = (score_dist_ultimo * 0.7 + score_dist_penultimo * 0.3)
        return score_final
    
    def calcular_distancia_roda(self, pos1, pos2):
        total_posicoes = 37
        distancia_direta = abs(pos1 - pos2)
        distancia_inversa = total_posicoes - distancia_direta
        return min(distancia_direta, distancia_inversa)
    
    def calcular_score_vizinhos(self, numero, historico):
        if len(historico) < 5:
            return 0.5
            
        vizinhos = self.roleta.get_vizinhos_fisicos(numero, raio=3)
        
        ultimos_15 = list(historico)[-15:] if len(historico) >= 15 else list(historico)
        count_vizinhos_recentes = sum(1 for n in ultimos_15 if n in vizinhos)
        
        score = min(count_vizinhos_recentes / len(ultimos_15) * 2, 1.0)
        return score
    
    def calcular_score_tendencia(self, numero, historico):
        if len(historico) < 10:
            return 0.5
            
        historico_lista = list(historico)
        
        segmento_recente = historico_lista[-5:]
        segmento_anterior = historico_lista[-10:-5] if len(historico_lista) >= 10 else historico_lista[:5]
        
        freq_recente = sum(1 for n in segmento_recente if n == numero) / len(segmento_recente)
        freq_anterior = sum(1 for n in segmento_anterior if n == numero) / len(segmento_anterior) if segmento_anterior else 0
        
        if freq_anterior == 0:
            tendencia = 1.0 if freq_recente > 0 else 0.5
        else:
            tendencia = min(freq_recente / freq_anterior, 2.0)
            
        return tendencia * 0.5

    def get_analise_selecao(self, numeros_originais, numeros_selecionados, historico):
        analise = f"🎯 ANÁLISE DA SELEÇÃO INTELIGENTE\n"
        analise += f"📊 Redução: {len(numeros_originais)} → {len(numeros_selecionados)} números\n"
        analise += f"🎲 Números selecionados: {sorted(numeros_selecionados)}\n"
        
        if historico:
            ultimos_20 = list(historico)[-20:] if len(historico) >= 20 else list(historico)
            acertos_potenciais = sum(1 for n in ultimos_20 if n in numeros_selecionados)
            analise += f"📈 Eficiência teórica: {acertos_potenciais}/20 ({acertos_potenciais/20*100:.1f}%)\n"
        
        return analise

# =============================
# CLASSE PRINCIPAL DA ROLETA ATUALIZADA
# =============================
class RoletaInteligente:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_zona(self, numero_central, quantidade=6):
        if numero_central not in self.race:
            return []
        
        posicao = self.race.index(numero_central)
        vizinhos = []
        
        for offset in range(-quantidade, 0):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        vizinhos.append(numero_central)
        
        for offset in range(1, quantidade + 1):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        return vizinhos

    def get_posicao_race(self, numero):
        return self.race.index(numero) if numero in self.race else -1

    def get_vizinhos_fisicos(self, numero, raio=3):
        if numero not in self.race:
            return []
        
        posicao = self.race.index(numero)
        vizinhos = []
        
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinho = self.race[(posicao + offset) % len(self.race)]
                vizinhos.append(vizinho)
        
        return vizinhos

# =============================
# MÓDULO DE MACHINE LEARNING ATUALIZADO COM CATBOOST - OTIMIZADO
# =============================
class MLRoletaOtimizada:
    def __init__(
        self,
        roleta_obj,
        min_training_samples: int = 200,
        max_history: int = 1000,
        retrain_every_n: int = 15,
        seed: int = 42
    ):
        self.roleta = roleta_obj
        self.min_training_samples = min_training_samples
        self.max_history = max_history
        self.retrain_every_n = retrain_every_n
        self.seed = seed

        self.models = []
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        self.contador_treinamento = 0
        self.meta = {}

        self.window_for_features = [3, 8, 15, 30, 60, 120]
        self.k_vizinhos = 2
        self.numeros = list(range(37))
        self.ensemble_size = 3

    def get_neighbors(self, numero, k=None):
        if k is None:
            k = self.k_vizinhos
        try:
            race = list(self.roleta.race)
            n = len(race)
            idx = race.index(numero)
            neighbors = []
            for offset in range(-k, k+1):
                neighbors.append(race[(idx + offset) % n])
            return neighbors
        except Exception:
            return [numero]

    def extrair_features(self, historico, numero_alvo=None):
        try:
            historico = list(historico)
            N = len(historico)
            
            if N < 10:
                return None, None

            features = []
            names = []

            K_seq = 10
            ultimos = historico[-K_seq:]
            for i in range(K_seq):
                val = ultimos[i] if i < len(ultimos) else -1
                features.append(val)
                names.append(f"ultimo_{i+1}")

            for w in self.window_for_features:
                janela = historico[-w:] if N >= w else historico[:]
                arr = np.array(janela, dtype=float)
                features.append(arr.mean() if len(arr) > 0 else 0.0); names.append(f"media_{w}")
                features.append(arr.std() if len(arr) > 1 else 0.0); names.append(f"std_{w}")
                features.append(np.median(arr) if len(arr) > 0 else 0.0); names.append(f"mediana_{w}")

            counter_full = Counter(historico)
            for w in self.window_for_features:
                janela = historico[-w:] if N >= w else historico[:]
                c = Counter(janela)
                features.append(len(c) / (w if w>0 else 1)); names.append(f"diversidade_{w}")
                top1_count = c.most_common(1)[0][1] if len(c)>0 else 0
                features.append(top1_count / (w if w>0 else 1)); names.append(f"top1_prop_{w}")

            for num in self.numeros:
                try:
                    rev_idx = historico[::-1].index(num)
                    tempo = rev_idx
                except ValueError:
                    tempo = N + 1
                features.append(tempo)
                names.append(f"tempo_desde_{num}")

            janela50 = historico[-50:] if N >= 50 else historico[:]
            vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
            pretos = set(self.numeros[1:]) - vermelhos
            count_verm = sum(1 for x in janela50 if x in vermelhos)
            count_pret = sum(1 for x in janela50 if x in pretos)
            count_zero = sum(1 for x in janela50 if x == 0)
            features.extend([count_verm/len(janela50), count_pret/len(janela50), count_zero/len(janela50)])
            names.extend(["prop_vermelhos_50", "prop_pretos_50", "prop_zero_50"])

            def duzia_of(x):
                if x == 0: return 0
                if 1 <= x <= 12: return 1
                if 13 <= x <= 24: return 2
                return 3
            for d in [1,2,3]:
                features.append(sum(1 for x in janela50 if duzia_of(x)==d)/len(janela50))
                names.append(f"prop_duzia_{d}_50")

            ultimo_num = historico[-1]
            vizinhos_k = self.get_neighbors(ultimo_num, k=6)
            count_in_vizinhos = sum(1 for x in ultimos if x in vizinhos_k) / len(ultimos)
            features.append(count_in_vizinhos); names.append("prop_ultimos_em_vizinhos_6")

            features.append(1 if N>=2 and historico[-1] == historico[-2] else 0); names.append("repetiu_ultimo")
            features.append(1 if N>=2 and (historico[-1] % 2) == (historico[-2] % 2) else 0); names.append("repetiu_paridade")
            features.append(1 if N>=2 and duzia_of(historico[-1]) == duzia_of(historico[-2]) else 0); names.append("repetiu_duzia")

            if N >= max(self.window_for_features):
                small = np.mean(historico[-self.window_for_features[0]:])
                large = np.mean(historico[-self.window_for_features[-1]:])
                features.append(small - large); names.append("delta_media_small_large")
            else:
                features.append(0.0); names.append("delta_media_small_large")

            diffs = [abs(historico[i] - historico[i-1]) for i in range(1, len(historico))]
            features.append(np.mean(diffs) if len(diffs)>0 else 0.0); names.append("media_transicoes")
            features.append(np.std(diffs) if len(diffs)>1 else 0.0); names.append("std_transicoes")

            self.feature_names = names
            return features, names

        except Exception as e:
            logging.error(f"[extrair_features] Erro: {e}")
            return None, None

    def preparar_dados_treinamento(self, historico_completo):
        historico_completo = list(historico_completo)
        if len(historico_completo) > self.max_history:
            historico_completo = historico_completo[-self.max_history:]

        X = []
        y = []
        
        start_index = max(50, len(historico_completo) // 10)
        
        for i in range(start_index, len(historico_completo)):
            janela = historico_completo[:i]
            feats, _ = self.extrair_features(janela)
            if feats is None:
                continue
            X.append(feats)
            y.append(historico_completo[i])
        
        if len(X) == 0:
            return np.array([]), np.array([])
        
        class_counts = Counter(y)
        if len(class_counts) < 10:
            logging.warning(f"Pouca variedade de classes: apenas {len(class_counts)} números únicos")
            return np.array([]), np.array([])
        
        return np.array(X), np.array(y)

    def _build_and_train_model(self, X_train, y_train, X_val=None, y_val=None, seed=0):
        try:
            try:
                from catboost import CatBoostClassifier
                model = CatBoostClassifier(
                    iterations=1500,
                    learning_rate=0.05,
                    depth=10,
                    l2_leaf_reg=5,
                    bagging_temperature=0.8,
                    random_strength=1.0,
                    loss_function='MultiClass',
                    eval_metric='MultiClass',
                    random_seed=seed,
                    use_best_model=True,
                    early_stopping_rounds=100,
                    verbose=False
                )
                if X_val is not None and y_val is not None:
                    model.fit(X_train, y_train, eval_set=(X_val, y_val), verbose=False)
                else:
                    model.fit(X_train, y_train, verbose=False)
                return model, "CatBoost"
            except ImportError:
                raise Exception("CatBoost não disponível")
                
        except Exception as e:
            logging.warning(f"CatBoost não disponível ou falha ({e}). Usando RandomForest como fallback.")
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=400,
                max_depth=20,
                min_samples_split=3,
                min_samples_leaf=2,
                random_state=seed,
                n_jobs=-1
            )
            model.fit(X_train, y_train)
            return model, "RandomForest"

    def treinar_modelo(self, historico_completo, force_retrain: bool = False, balance: bool = True):
        try:
            if len(historico_completo) < self.min_training_samples and not force_retrain:
                return False, f"Necessário mínimo de {self.min_training_samples} amostras. Atual: {len(historico_completo)}"

            X, y = self.preparar_dados_treinamento(historico_completo)
            if X.size == 0 or len(X) < 50:
                return False, f"Dados insuficientes para treino: {len(X)} amostras"

            X_scaled = self.scaler.fit_transform(X)

            try:
                class_counts = Counter(y)
                min_samples_per_class = min(class_counts.values())
                
                can_stratify = min_samples_per_class >= 2 and len(class_counts) > 1
                
                X_train, X_val, y_train, y_val = train_test_split(
                    X_scaled, y, 
                    test_size=0.2, 
                    random_state=self.seed, 
                    stratify=y if can_stratify else None
                )
                
                logging.info(f"Split realizado: estratificação = {can_stratify}, classes = {len(class_counts)}, min_amostras = {min_samples_per_class}")
                
            except Exception as e:
                logging.warning(f"Erro no split estratificado: {e}. Usando split sem estratificação.")
                X_train, X_val, y_train, y_val = train_test_split(
                    X_scaled, y, test_size=0.2, random_state=self.seed
                )

            if balance and len(X_train) > 0:
                try:
                    df_train = pd.DataFrame(X_train, columns=[f"f{i}" for i in range(X_train.shape[1])])
                    df_train['y'] = y_train
                    
                    value_counts = df_train['y'].value_counts()
                    if len(value_counts) == 0:
                        raise ValueError("Nenhuma classe encontrada")
                    
                    max_count = value_counts.max()
                    
                    if len(value_counts) < 2:
                        logging.warning("Apenas uma classe disponível, pulando balanceamento")
                        balance = False
                    else:
                        frames = []
                        for cls, grp in df_train.groupby('y'):
                            if len(grp) < max_count:
                                if len(grp) >= 1:
                                    min_samples = max(5, max_count // 3)
                                    n_samples = min(max_count, min_samples)
                                    grp_up = resample(grp, replace=True, n_samples=n_samples, random_state=self.seed)
                                    frames.append(grp_up)
                                else:
                                    frames.append(grp)
                            else:
                                frames.append(grp)
                        
                        if frames:
                            df_bal = pd.concat(frames)
                            y_train = df_bal['y'].values
                            X_train = df_bal.drop(columns=['y']).values
                        else:
                            balance = False
                            
                except Exception as e:
                    logging.warning(f"Erro no balanceamento: {e}. Continuando sem balanceamento.")
                    balance = False

            models = []
            model_names = []
            
            for s in [self.seed, self.seed + 7, self.seed + 13]:
                try:
                    model, name = self._build_and_train_model(X_train, y_train, X_val, y_val, seed=s)
                    models.append(model)
                    model_names.append(name)
                except Exception as e:
                    logging.error(f"Erro ao treinar modelo {s}: {e}")

            if not models:
                return False, "Todos os modelos falharam no treinamento"

            try:
                probs = []
                for m in models:
                    if hasattr(m, 'predict_proba'):
                        probs.append(m.predict_proba(X_val))
                    else:
                        preds = m.predict(X_val)
                        prob = np.zeros((len(preds), len(self.numeros)))
                        for i, p in enumerate(preds):
                            prob[i, p] = 1.0
                        probs.append(prob)
                
                if probs:
                    avg_prob = np.mean(probs, axis=0)
                    y_pred = np.argmax(avg_prob, axis=1)
                    acc = accuracy_score(y_val, y_pred)
                else:
                    acc = 0.0
                    
            except Exception as e:
                logging.warning(f"Erro na avaliação: {e}")
                acc = 0.0

            self.models = models
            self.is_trained = True
            self.contador_treinamento += 1
            self.meta['last_accuracy'] = acc
            self.meta['trained_on'] = len(historico_completo)
            self.meta['last_training_size'] = len(X)

            try:
                joblib.dump({'models': self.models}, ML_MODEL_PATH)
                joblib.dump(self.scaler, SCALER_PATH)
                joblib.dump(self.meta, META_PATH)
                logging.info(f"Modelos salvos em disco: {ML_MODEL_PATH}")
            except Exception as e:
                logging.warning(f"Falha ao salvar modelos: {e}")

            return True, f"Ensemble treinado ({', '.join(model_names)}) com {len(X)} amostras. Acurácia validação: {acc:.2%}"

        except Exception as e:
            logging.error(f"[treinar_modelo] Erro: {e}", exc_info=True)
            return False, f"Erro no treinamento: {str(e)}"

    def carregar_modelo(self):
        try:
            if os.path.exists(ML_MODEL_PATH) and os.path.exists(SCALER_PATH):
                data = joblib.load(ML_MODEL_PATH)
                self.models = data.get('models', [])
                self.scaler = joblib.load(SCALER_PATH)
                if os.path.exists(META_PATH):
                    self.meta = joblib.load(META_PATH)
                self.is_trained = len(self.models) > 0
                return True
            return False
        except Exception as e:
            logging.error(f"[carregar_modelo] Erro: {e}")
            return False

    def _ensemble_predict_proba(self, X_scaled):
        if not self.models:
            return np.ones((len(X_scaled), len(self.numeros))) / len(self.numeros)

        probs = []
        for m in self.models:
            if hasattr(m, 'predict_proba'):
                probs.append(m.predict_proba(X_scaled))
            else:
                preds = m.predict(X_scaled)
                prob = np.zeros((len(preds), len(self.numeros)))
                for i, p in enumerate(preds):
                    prob[i, p] = 1.0
                probs.append(prob)
        return np.mean(probs, axis=0)

    def prever_proximo_numero(self, historico, top_k: int = 25):
        if not self.is_trained:
            return None, "Modelo não treinado"

        feats, _ = self.extrair_features(historico)
        if feats is None:
            return None, "Features insuficientes"

        Xs = np.array([feats])
        Xs_scaled = self.scaler.transform(Xs)
        try:
            probs = self._ensemble_predict_proba(Xs_scaled)[0]
            top_idx = np.argsort(probs)[-top_k:][::-1]
            top = [(int(idx), float(probs[idx])) for idx in top_idx]
            return top, "Previsão ML realizada"
        except Exception as e:
            return None, f"Erro na previsão: {str(e)}"

    def prever_blocos_vizinhos(self, historico, k_neighbors: int = 2, top_blocks: int = 5):
        pred, msg = self.prever_proximo_numero(historico, top_k=37)
        if pred is None:
            return None, msg
        prob = {num: p for num, p in pred}
        blocks = []
        for num in range(37):
            neigh = self.get_neighbors(num, k=k_neighbors)
            agg_prob = sum(prob.get(n, 0.0) for n in neigh)
            blocks.append((num, tuple(neigh), agg_prob))
        blocks_sorted = sorted(blocks, key=lambda x: x[2], reverse=True)[:top_blocks]
        formatted = [{"central": b[0], "vizinhos": list(b[1]), "prob": float(b[2])} for b in blocks_sorted]
        return formatted, "Previsão de blocos realizada"

    def registrar_resultado(self, historico, previsao_top, resultado_real):
        try:
            hit = resultado_real in [p for p,_ in previsao_top] if isinstance(previsao_top[0], tuple) else resultado_real in previsao_top
            log_entry = {
                'prev_top': previsao_top,
                'resultado': resultado_real,
                'hit': bool(hit)
            }
            self.meta.setdefault('history_feedback', []).append(log_entry)
            recent = self.meta['history_feedback'][-10:]
            hits = sum(1 for r in recent if r['hit'])
            if len(recent) >= 5 and hits / len(recent) < 0.25:
                logging.info("[feedback] Baixa performance detectada — forçando retreinamento incremental")
                self.treinar_modelo(historico, force_retrain=True, balance=True)
            return True
        except Exception as e:
            logging.error(f"[registrar_resultado] Erro: {e}")
            return False

    def verificar_treinamento_automatico(self, historico_completo):
        try:
            n = len(historico_completo)
            if n >= self.min_training_samples:
                if n % self.retrain_every_n == 0:
                    return self.treinar_modelo(historico_completo)
            return False, "Aguardando próximo ciclo de treinamento"
        except Exception as e:
            return False, f"Erro ao verificar retrain: {e}"

    def resumo_meta(self):
        return {
            "is_trained": self.is_trained,
            "contador_treinamento": self.contador_treinamento,
            "meta": self.meta
        }

# =============================
# ESTRATÉGIA DAS ZONAS ATUALIZADA - COM APRENDIZADO DINÂMICO DE COMBINAÇÕES
# =============================
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Zonas Ultra Otimizada v6"
        
        self.zonas = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.quantidade_zonas = {
            'Vermelha': 6,
            'Azul': 6,
            'Amarela': 6
        }
        
        self.stats_zonas = {zona: {
            'acertos': 0, 
            'tentativas': 0, 
            'sequencia_atual': 0,
            'sequencia_maxima': 0,
            'performance_media': 0
        } for zona in self.zonas.keys()}
        
        self.numeros_zonas = {}
        for nome, central in self.zonas.items():
            qtd = self.quantidade_zonas.get(nome, 6)
            self.numeros_zonas[nome] = self.roleta.get_vizinhos_zona(central, qtd)

        self.janelas_analise = {
            'curto_prazo': 12,
            'medio_prazo': 24,  
            'longo_prazo': 48,
            'performance': 100
        }
        
        self.threshold_base = 22
        
        self.sistema_selecao = SistemaSelecaoInteligente()

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        resultado = self.atualizar_stats(numero)
        if 'sistema' in st.session_state:
            salvar_sessao()
        return resultado

    def atualizar_stats(self, ultimo_numero):
        acertou_zona = None
        for zona, numeros in self.numeros_zonas.items():
            if ultimo_numero in numeros:
                self.stats_zonas[zona]['acertos'] += 1
                self.stats_zonas[zona]['sequencia_atual'] += 1
                if self.stats_zonas[zona]['sequencia_atual'] > self.stats_zonas[zona]['sequencia_maxima']:
                    self.stats_zonas[zona]['sequencia_maxima'] = self.stats_zonas[zona]['sequencia_atual']
                acertou_zona = zona
            else:
                self.stats_zonas[zona]['sequencia_atual'] = 0
            self.stats_zonas[zona]['tentativas'] += 1
            
            if self.stats_zonas[zona]['tentativas'] > 0:
                self.stats_zonas[zona]['performance_media'] = (
                    self.stats_zonas[zona]['acertos'] / self.stats_zonas[zona]['tentativas'] * 100
                )
        
        return acertou_zona

    def get_threshold_dinamico(self, zona):
        if zona not in self.stats_zonas:
            return 20
        
        perf = self.stats_zonas[zona]['performance_media']
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        
        if perf > 35 and sequencia >= 1:  
            return 18
        elif perf > 30:
            return 20
        elif perf > 25:
            return 22
        elif perf < 15:
            return 28
        else:
            return 24

    def get_zona_mais_quente(self):
        if len(self.historico) < 10:
            return None
            
        zonas_score = {}
        total_numeros = len(self.historico)
        
        for zona in self.zonas.keys():
            score = 0
            
            freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
            percentual_geral = freq_geral / total_numeros
            score += percentual_geral * 25
            
            ultimos_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:] if total_numeros >= self.janelas_analise['curto_prazo'] else list(self.historico)
            freq_curto = sum(1 for n in ultimos_curto if n in self.numeros_zonas[zona])
            percentual_curto = freq_curto / len(ultimos_curto)
            score += percentual_curto * 35
            
            if self.stats_zonas[zona]['tentativas'] > 10:
                taxa_acerto = self.stats_zonas[zona]['performance_media']
                if taxa_acerto > 40: 
                    score += 30
                elif taxa_acerto > 35:
                    score += 25
                elif taxa_acerto > 30:
                    score += 20
                elif taxa_acerto > 25:
                    score += 15
                else:
                    score += 10
            else:
                score += 10
            
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            if sequencia >= 2:
                score += min(sequencia * 3, 12)
            
            zonas_score[zona] = score
        
        zona_vencedora = max(zonas_score, key=zonas_score.get) if zonas_score else None
        
        if zona_vencedora:
            threshold = self.get_threshold_dinamico(zona_vencedora)
            
            if self.stats_zonas[zona_vencedora]['sequencia_atual'] >= 2:
                threshold -= 2
            
            return zona_vencedora if zonas_score[zona_vencedora] >= threshold else None
        
        return None

    def get_zonas_rankeadas(self):
        if len(self.historico) < 10:
            return None
            
        zonas_score = {}
        
        for zona in self.zonas.keys():
            score = self.get_zona_score(zona)
            zonas_score[zona] = score
        
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def analisar_zonas_com_inversao(self):
        if len(self.historico) < 10:
            return None
            
        zonas_rankeadas = self.get_zonas_rankeadas()
        if not zonas_rankeadas:
            return None
        
        zona_primaria, score_primario = zonas_rankeadas[0]
        
        threshold_base = 22
        
        if score_primario < threshold_base:
            return None
        
        sistema = st.session_state.sistema
        combinacao_recomendada = sistema.get_combinacao_recomendada()
        
        if combinacao_recomendada and zona_primaria in combinacao_recomendada:
            zona_secundaria = [z for z in combinacao_recomendada if z != zona_primaria][0]
            
            zonas_secundarias_disponiveis = [z for z, s in zonas_rankeadas if z == zona_secundaria]
            if zonas_secundarias_disponiveis:
                return self.criar_previsao_dupla(zona_primaria, zona_secundaria, "RECOMENDADA")
        
        if len(zonas_rankeadas) > 1:
            for i in range(1, min(3, len(zonas_rankeadas))):
                zona_secundaria, score_secundario = zonas_rankeadas[i]
                combinacao_teste = tuple(sorted([zona_primaria, zona_secundaria]))
                
                if sistema.deve_evitar_combinacao(combinacao_teste):
                    continue
                
                threshold_secundario = threshold_base - 4
                
                if score_secundario >= threshold_secundario:
                    return self.criar_previsao_dupla(zona_primaria, zona_secundaria, "RANQUEADA")
        
        return self.criar_previsao_unica(zona_primaria)

    def criar_previsao_dupla(self, zona_primaria, zona_secundaria, tipo):
        numeros_primarios = self.numeros_zonas[zona_primaria]
        numeros_secundarios = self.numeros_zonas[zona_secundaria]
        
        numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
        
        if len(numeros_combinados) > 15:
            numeros_combinados = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_combinados, self.historico, "Zonas"
            )
        
        sistema = st.session_state.sistema
        combinacao = tuple(sorted([zona_primaria, zona_secundaria]))
        dados_combinacao = sistema.historico_combinacoes.get(combinacao, {})
        eficiencia = dados_combinacao.get('eficiencia', 0)
        total = dados_combinacao.get('total', 0)
        
        info_eficiencia = ""
        if total > 0:
            info_eficiencia = f" | Eff: {eficiencia:.1f}% ({dados_combinacao.get('acertos', 0)}/{total})"
        
        gatilho = f'Zona {zona_primaria} + {zona_secundaria} - {tipo}{info_eficiencia}'
        
        return {
            'nome': f'Zonas Duplas - {zona_primaria} + {zona_secundaria}',
            'numeros_apostar': numeros_combinados,
            'gatilho': gatilho,
            'confianca': self.calcular_confianca_ultra(zona_primaria),
            'zona': f'{zona_primaria}+{zona_secundaria}',
            'zonas_envolvidas': [zona_primaria, zona_secundaria],
            'tipo': 'dupla',
            'selecao_inteligente': True
        }

    def criar_previsao_unica(self, zona_primaria):
        numeros_apostar = self.numeros_zonas[zona_primaria]
        
        if len(numeros_apostar) > 15:
            numeros_apostar = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_apostar, self.historico, "Zonas"
            )
        
        return {
            'nome': f'Zona {zona_primaria}',
            'numeros_apostar': numeros_apostar,
            'gatilho': f'Zona {zona_primaria} - Única',
            'confianca': self.calcular_confianca_ultra(zona_primaria),
            'zona': zona_primaria,
            'zonas_envolvidas': [zona_primaria],
            'tipo': 'unica',
            'selecao_inteligente': len(numeros_apostar) < len(self.numeros_zonas[zona_primaria])
        }

    def analisar_zonas(self):
        return self.analisar_zonas_com_inversao()

    def calcular_confianca_ultra(self, zona):
        if len(self.historico) < 8:
            return 'Média'
            
        fatores = []
        pesos = []
        
        perf_historica = self.stats_zonas[zona]['performance_media']
        if perf_historica > 45: 
            fatores.append(4)
            pesos.append(5)
        elif perf_historica > 35: 
            fatores.append(3)
            pesos.append(4)
        elif perf_historica > 25: 
            fatores.append(2)
            pesos.append(4)
        else: 
            fatores.append(1)
            pesos.append(3)
        
        historico_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:] 
        freq_curto = sum(1 for n in historico_curto if n in self.numeros_zonas[zona])
        perc_curto = (freq_curto / len(historico_curto)) * 100
        
        if perc_curto > 60:
            fatores.append(4)
        elif perc_curto > 45: 
            fatores.append(3)
        elif perc_curto > 30: 
            fatores.append(2)
        else: 
            fatores.append(1)
        pesos.append(4)
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 3: 
            fatores.append(4)
            pesos.append(3)
        elif sequencia >= 2: 
            fatores.append(3)
            pesos.append(3)
        else: 
            fatores.append(1)
            pesos.append(2)
        
        if len(self.historico) >= 10:
            ultimos_5 = list(self.historico)[-5:]
            anteriores_5 = list(self.historico)[-10:-5]
            
            freq_ultimos = sum(1 for n in ultimos_5 if n in self.numeros_zonas[zona])
            freq_anteriores = sum(1 for n in anteriores_5 if n in self.numeros_zonas[zona]) if anteriores_5 else 0
            
            if freq_ultimos > freq_anteriores: 
                fatores.append(3)
                pesos.append(2)
            elif freq_ultimos == freq_anteriores: 
                fatores.append(2)
                pesos.append(2)
            else: 
                fatores.append(1)
                pesos.append(2)
        
        total_pontos = sum(f * p for f, p in zip(fatores, pesos))
        total_pesos = sum(pesos)
        score_confianca = total_pontos / total_pesos
        
        if score_confianca >= 2.8: 
            return 'Excelente'
        elif score_confianca >= 2.4: 
            return 'Muito Alta'
        elif score_confianca >= 2.0: 
            return 'Alta'
        elif score_confianca >= 1.6: 
            return 'Média'
        else: 
            return 'Baixa'

    def get_zona_score(self, zona):
        if len(self.historico) < 10:
            return 0
            
        score = 0
        total_numeros = len(self.historico)
        
        freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
        percentual_geral = freq_geral / total_numeros
        score += percentual_geral * 25
        
        for janela_nome, tamanho in self.janelas_analise.items():
            if janela_nome != 'performance':
                historico_janela = list(self.historico)[-tamanho:] if total_numeros >= tamanho else list(self.historico)
                freq_janela = sum(1 for n in historico_janela if n in self.numeros_zonas[zona])
                percentual_janela = freq_janela / len(historico_janela)
                peso = 35 if janela_nome == 'curto_prazo' else 15
                score += percentual_janela * peso
        
        if self.stats_zonas[zona]['tentativas'] > 10:
            taxa_acerto = self.stats_zonas[zona]['performance_media']
            if taxa_acerto > 40: score += 30
            elif taxa_acerto > 35: score += 25
            elif taxa_acerto > 30: score += 20
            elif taxa_acerto > 25: score += 15
            else: score += 10
        else:
            score += 10
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 2:
            score += min(sequencia * 3, 12)
            
        return score

    def get_info_zonas(self):
        info = {}
        for zona, numeros in self.numeros_zonas.items():
            info[zona] = {
                'numeros': sorted(numeros),
                'quantidade': len(numeros),
                'central': self.zonas[zona],
                'descricao': f"6 antes + 6 depois do {self.zonas[zona]}"
            }
        return info

    def get_analise_detalhada(self):
        if len(self.historico) == 0:
            return "Aguardando dados..."
        
        analise = "🎯 ANÁLISE ULTRA OTIMIZADA - ZONAS v6\n"
        analise += "=" * 55 + "\n"
        analise += "🔧 CONFIGURAÇÃO: 6 antes + 6 depois (13 números/zona)\n"
        analise += f"📊 JANELAS: Curto({self.janelas_analise['curto_prazo']}) Médio({self.janelas_analise['medio_prazo']}) Longo({self.janelas_analise['longo_prazo']})\n"
        analise += "=" * 55 + "\n"
        
        analise += "📊 PERFORMANCE AVANÇADADA:\n"
        for zona in self.zonas.keys():
            tentativas = self.stats_zonas[zona]['tentativas']
            acertos = self.stats_zonas[zona]['acertos']
            taxa = self.stats_zonas[zona]['performance_media']
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            seq_maxima = self.stats_zonas[zona]['sequencia_maxima']
            threshold = self.get_threshold_dinamico(zona)
            
            analise += f"📍 {zona}: {acertos}/{tentativas} → {taxa:.1f}% | Seq: {sequencia} | Máx: {seq_maxima} | Thr: {threshold}\n"
        
        analise += "\n📈 FREQUÊNCIA MULTI-JANELAS:\n"
        for zona in self.zonas.keys():
            freq_total = sum(1 for n in self.historico if isinstance(n, (int, float)) and n in self.numeros_zonas[zona])
            perc_total = (freq_total / len(self.historico)) * 100
            
            freq_curto = sum(1 for n in list(self.historico)[-self.janelas_analise['curto_prazo']:] if n in self.numeros_zonas[zona])
            perc_curto = (freq_curto / min(self.janelas_analise['curto_prazo'], len(self.historico))) * 100
            
            score = self.get_zona_score(zona)
            qtd_numeros = len(self.numeros_zonas[zona])
            analise += f"📍 {zona}: Total:{freq_total}/{len(self.historico)}({perc_total:.1f}%) | Curto:{freq_curto}/{self.janelas_analise['curto_prazo']}({perc_curto:.1f}%) | Score: {score:.1f}\n"
        
        analise += "\n📊 TENDÊNCIAS AVANÇADAS:\n"
        if len(self.historico) >= 10:
            for zona in self.zonas.keys():
                ultimos_5 = list(self.historico)[-5:]
                anteriores_5 = list(self.historico)[-10:-5]
                
                freq_ultimos = sum(1 for n in ultimos_5 if n in self.numeros_zonas[zona])
                freq_anteriores = sum(1 for n in anteriores_5 if n in self.numeros_zonas[zona]) if anteriores_5 else 0
                
                tendencia = "↗️" if freq_ultimos > freq_anteriores else "↘️" if freq_ultimos < freq_anteriores else "➡️"
                variacao = freq_ultimos - freq_anteriores
                analise += f"📍 {zona}: {freq_ultimos}/5 vs {freq_anteriores}/5 {tendencia} (Δ: {variacao:+d})\n"
        
        zona_recomendada = self.get_zona_mais_quente()
        if zona_recomendada:
            analise += f"\n💡 RECOMENDAÇÃO ULTRA: Zona {zona_recomendada}\n"
            analise += f"🎯 Números: {sorted(self.numeros_zonas[zona_recomendada])}\n"
            analise += f"📈 Confiança: {self.calcular_confianca_ultra(zona_recomendada)}\n"
            analise += f"🔥 Score: {self.get_zona_score(zona_recomendada):.1f}\n"
            analise += f"🎯 Threshold: {self.get_threshold_dinamico(zona_recomendada)}\n"
            analise += f"🔢 Quantidade: {len(self.numeros_zonas[zona_recomendada])} números\n"
            analise += f"📊 Performance: {self.stats_zonas[zona_recomendada]['performance_media']:.1f}%\n"
            
            perf = self.stats_zonas[zona_recomendada]['performance_media']
            if perf > 35:
                analise += f"💎 ESTRATÉGIA: Zona de ALTA performance - Aposta forte recomendada!\n"
            elif perf > 25:
                analise += f"🎯 ESTRATÉGIA: Zona de performance sólida - Aposta moderada\n"
            else:
                analise += f"⚡ ESTRATÉGIA: Zona em desenvolvimento - Aposta conservadora\n"
        else:
            analise += "\n⚠️  AGUARDAR: Nenhuma zona com confiança suficiente\n"
            analise += f"📋 Histórico atual: {len(self.historico)} números\n"
            analise += f"🎯 Threshold base: {self.threshold_base}+ | Performance >25%\n"
        
        return analise

    def get_analise_atual(self):
        return self.get_analise_detalhada()

    def zerar_estatisticas(self):
        for zona in self.stats_zonas.keys():
            self.stats_zonas[zona] = {
                'acertos': 0, 
                'tentativas': 0, 
                'sequencia_atual': 0,
                'sequencia_maxima': 0,
                'performance_media': 0
            }
        logging.info("📊 Estatísticas das Zonas zeradas")

# =============================
# ESTRATÉGIA MIDAS (MANTIDA)
# =============================
class EstrategiaMidas:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=15)
        self.terminais = {
            '0': [0, 10, 20, 30], '1': [1, 11, 21, 31], '2': [2, 12, 22, 32],
            '3': [3, 13, 23, 33], '4': [4, 14, 24, 34], '5': [5, 15, 25, 35],
            '6': [6, 16, 26, 36], '7': [7, 17, 27], '8': [8, 18, 28], '9': [9, 19, 29]
        }

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        if 'sistema' in st.session_state:
            salvar_sessao()

    def analisar_midas(self):
        if len(self.historico) < 5:
            return None
            
        ultimo_numero = self.historico[-1]
        historico_recente = self.historico[-5:]

        if ultimo_numero in [0, 10, 20, 30]:
            count_zero = sum(1 for n in historico_recente if n in [0, 10, 20, 30])
            if count_zero >= 1:
                return {
                    'nome': 'Padrão do Zero',
                    'numeros_apostar': [0, 10, 20, 30],
                    'gatilho': f'Terminal 0 ativado ({count_zero}x)',
                    'confianca': 'Média'
                }

        if ultimo_numero in [7, 17, 27]:
            count_sete = sum(1 for n in historico_recente if n in [7, 17, 27])
            if count_sete >= 1:
                return {
                    'nome': 'Padrão do Sete',
                    'numeros_apostar': [7, 17, 27],
                    'gatilho': f'Terminal 7 ativado ({count_sete}x)',
                    'confianca': 'Média'
                }

        if ultimo_numero in [5, 15, 25, 35]:
            count_cinco = sum(1 for n in historico_recente if n in [5, 15, 25, 35])
            if count_cinco >= 1:
                return {
                    'nome': 'Padrão do Cinco',
                    'numeros_apostar': [5, 15, 25, 35],
                    'gatilho': f'Terminal 5 ativado ({count_cinco}x)',
                    'confianca': 'Média'
                }

        return None

# =============================
# ESTRATÉGIA ML ATUALIZADA
# =============================
class EstrategiaML:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.ml = MLRoletaOtimizada(self.roleta)
        self.historico = deque(maxlen=30)
        self.nome = "Machine Learning (CatBoost)"
        self.ml.carregar_modelo()
        self.contador_sorteios = 0
        
        self.zonas_ml = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.quantidade_zonas_ml = {
            'Vermelha': 6,
            'Azul': 6,
            'Amarela': 6
        }
        
        self.numeros_zonas_ml = {}
        for nome, central in self.zonas_ml.items():
            qtd = self.quantidade_zonas_ml.get(nome, 6)
            self.numeros_zonas_ml[nome] = self.roleta.get_vizinhos_zona(central, qtd)

        self.sequencias_padroes = {
            'sequencias_ativas': {},
            'historico_sequencias': [],
            'padroes_detectados': []
        }
        
        self.adicionar_metricas_padroes()
        
        self.sistema_selecao = SistemaSelecaoInteligente()

    def adicionar_metricas_padroes(self):
        self.metricas_padroes = {
            'padroes_detectados_total': 0,
            'padroes_acertados': 0,
            'padroes_errados': 0,
            'eficiencia_por_tipo': {},
            'historico_validacao': []
        }

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.contador_sorteios += 1
        
        if len(self.historico) > 1:
            numero_anterior = list(self.historico)[-2]
            self.validar_padrao_acerto(numero, self.get_previsao_atual())
        
        self.analisar_padroes_sequenciais(numero)
        
        if self.contador_sorteios >= 15:
            self.contador_sorteios = 0
            self.treinar_automatico()
            
        if 'sistema' in st.session_state:
            salvar_sessao()

    def get_previsao_atual(self):
        try:
            resultado = self.analisar_ml()
            return resultado
        except:
            return None

    def validar_padrao_acerto(self, numero_sorteado, previsao_ml):
        zona_sorteada = None
        for zona, numeros in self.numeros_zonas_ml.items():
            if numero_sorteado in numeros:
                zona_sorteada = zona
                break
        
        if not zona_sorteada:
            return
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if len(self.historico) - p['detectado_em'] <= 3]
        
        for padrao in padroes_recentes:
            self.metricas_padroes['padroes_detectados_total'] += 1
            
            if padrao['zona'] == zona_sorteada:
                self.metricas_padroes['padroes_acertados'] += 1
                tipo = padrao['tipo']
                if tipo not in self.metricas_padroes['eficiencia_por_tipo']:
                    self.metricas_padroes['eficiencia_por_tipo'][tipo] = {'acertos': 0, 'total': 0}
                self.metricas_padroes['eficiencia_por_tipo'][tipo]['acertos'] += 1
                self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1
            else:
                self.metricas_padroes['padroes_errados'] += 1
                tipo = padrao['tipo']
                if tipo in self.metricas_padroes['eficiencia_por_tipo']:
                    self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1

    def analisar_padroes_sequenciais(self, numero):
        if len(self.historico) < 5:
            return
            
        historico_recente = list(self.historico)[-8:]
        
        zona_atual = None
        for zona, numeros in self.numeros_zonas_ml.items():
            if numero in numeros:
                zona_atual = zona
                break
        
        if not zona_atual:
            return
        
        self.atualizar_sequencias_ativas(zona_atual, historico_recente)
        self.otimizar_deteccao_padroes(historico_recente)
        self.limpar_padroes_antigos()

    def otimizar_deteccao_padroes(self, historico_recente):
        if len(historico_recente) < 5:
            return
        
        zonas_recentes = []
        for num in historico_recente:
            zona_num = None
            for zona, numeros in self.numeros_zonas_ml.items():
                if num in numeros:
                    zona_num = zona
                    break
            zonas_recentes.append(zona_num)
        
        for i in range(len(zonas_recentes) - 3):
            janela = zonas_recentes[i:i+4]
            if (janela[0] and janela[1] and janela[2] and janela[3] and
                janela[0] == janela[1] == janela[2] == janela[3]):
                
                self.registrar_padrao_sequencia_forte(janela[0], i)

        for i in range(len(zonas_recentes) - 3):
            janela = zonas_recentes[i:i+4]
            if (janela[0] and janela[1] and janela[3] and
                janela[0] == janela[1] == janela[3] and
                janela[2] != janela[0]):
                
                self.registrar_padrao_retorno_imediato(janela[0], i)

        for i in range(len(zonas_recentes) - 5):
            janela = zonas_recentes[i:i+6]
            if (janela[0] and janela[1] and janela[2] and janela[4] and janela[5] and
                janela[0] == janela[1] == janela[2] == janela[4] == janela[5] and
                janela[3] != janela[0]):
                
                self.registrar_padrao_sequencia_interrompida(janela[0], i)

        for i in range(len(zonas_recentes) - 4):
            janela = zonas_recentes[i:i+5]
            if (janela[0] and janela[1] and janela[3] and janela[4] and
                janela[0] == janela[1] == janela[3] == janela[4] and
                janela[2] != janela[0]):
                
                self.registrar_padrao_retorno_rapido(janela[0], i)

    def registrar_padrao_sequencia_forte(self, zona, posicao):
        padrao = {
            'tipo': 'sequencia_forte_4',
            'zona': zona,
            'padrao': 'AAAA',
            'forca': 0.95,
            'duracao': 4,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao, janela=8):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO FORTE 4x: {zona} - {padrao['padrao']}")

    def registrar_padrao_retorno_imediato(self, zona, posicao):
        padrao = {
            'tipo': 'retorno_imediato',
            'zona': zona,
            'padrao': 'AA_B_A',
            'forca': 0.80,
            'duracao': 4,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao, janela=10):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO RÁPIDO: {zona} - {padrao['padrao']}")

    def registrar_padrao_sequencia_interrompida(self, zona, posicao):
        padrao = {
            'tipo': 'sequencia_interrompida_forte',
            'zona': zona,
            'padrao': 'AAA_B_AA',
            'forca': 0.85,
            'duracao': 6,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO FORTE: {zona} - {padrao['padrao']}")

    def registrar_padrao_retorno_rapido(self, zona, posicao):
        padrao = {
            'tipo': 'retorno_rapido',
            'zona': zona,
            'padrao': 'AA_B_AA',
            'forca': 0.75,
            'duracao': 5,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO RÁPIDO: {zona} - {padrao['padrao']}")

    def padrao_recente_similar(self, novo_padrao, janela=12):
        for padrao in self.sequencias_padroes['padroes_detectados'][-10:]:
            if (padrao['zona'] == novo_padrao['zona'] and 
                padrao['tipo'] == novo_padrao['tipo'] and
                len(self.historico) - padrao['detectado_em'] < janela):
                return True
        return False

    def limpar_padroes_antigos(self, limite=20):
        padroes_validos = []
        for padrao in self.sequencias_padroes['padroes_detectados']:
            if len(self.historico) - padrao['detectado_em'] <= limite:
                padroes_validos.append(padrao)
        self.sequencias_padroes['padroes_detectados'] = padroes_validos

    def atualizar_sequencias_ativas(self, zona_atual, historico_recente):
        if zona_atual in self.sequencias_padroes['sequencias_ativas']:
            sequencia = self.sequencias_padroes['sequencias_ativas'][zona_atual]
            sequencia['contagem'] += 1
            sequencia['ultimo_numero'] = historico_recente[-1]
        else:
            self.sequencias_padroes['sequencias_ativas'][zona_atual] = {
                'contagem': 1,
                'inicio': len(self.historico) - 1,
                'ultimo_numero': historico_recente[-1],
                'quebras': 0
            }
        
        zonas_ativas = list(self.sequencias_padroes['sequencias_ativas'].keys())
        for zona in zonas_ativas:
            if zona != zona_atual:
                self.sequencias_padroes['sequencias_ativas'][zona]['quebras'] += 1
                
                if self.sequencias_padroes['sequencias_ativas'][zona]['quebras'] >= 3:
                    sequencia_final = self.sequencias_padroes['sequencias_ativas'][zona]
                    if sequencia_final['contagem'] >= 3:
                        self.sequencias_padroes['historico_sequencias'].append({
                            'zona': zona,
                            'tamanho': sequencia_final['contagem'],
                            'finalizado_em': len(self.historico) - 1
                        })
                    del self.sequencias_padroes['sequencias_ativas'][zona]

    def aplicar_padroes_na_previsao(self, distribuicao_zonas):
        if not self.sequencias_padroes['padroes_detectados']:
            return distribuicao_zonas
        
        distribuicao_ajustada = distribuicao_zonas.copy()
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if len(self.historico) - p['detectado_em'] <= 15]
        
        for padrao in padroes_recentes:
            zona = padrao['zona']
            forca = padrao['forca']
            
            if zona in distribuicao_ajustada:
                aumento = max(1, int(distribuicao_ajustada[zona] * forca * 0.3))
                distribuicao_ajustada[zona] += aumento
                logging.info(f"🎯 Aplicando padrão {padrao['tipo']} à zona {zona}: +{aumento}")
        
        return distribuicao_ajustada

    def calcular_confianca_com_padroes(self, distribuicao, zona_alvo):
        confianca_base = self.calcular_confianca_zona_ml({
            'contagem': distribuicao[zona_alvo],
            'total_zonas': 25
        })
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if p['zona'] == zona_alvo and 
                           len(self.historico) - p['detectado_em'] <= 15]
        
        bonus_confianca = len(padroes_recentes) * 0.15
        confianca_final = min(1.0, self.confianca_para_valor(confianca_base) + bonus_confianca)
        
        return self.valor_para_confianca(confianca_final)

    def confianca_para_valor(self, confianca_texto):
        mapa_confianca = {
            'Muito Baixa': 0.3,
            'Baixa': 0.5,
            'Média': 0.65,
            'Alta': 0.8,
            'Muito Alta': 0.9
        }
        return mapa_confianca.get(confianca_texto, 0.5)

    def valor_para_confianca(self, valor):
        if valor >= 0.85: return 'Muito Alta'
        elif valor >= 0.7: return 'Alta'
        elif valor >= 0.6: return 'Média'
        elif valor >= 0.45: return 'Baixa'
        else: return 'Muito Baixa'

    def analisar_distribuicao_zonas_rankeadas(self, top_25_numeros):
        contagem_zonas = {}
        
        for zona, numeros in self.numeros_zonas_ml.items():
            count = sum(1 for num in top_25_numeros if num in numeros)
            contagem_zonas[zona] = count
        
        if not contagem_zonas:
            return None
            
        zonas_rankeadas = sorted(contagem_zonas.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def analisar_ml_com_inversao(self):
        if len(self.historico) < 10:
            return None

        if not self.ml.is_trained:
            return None

        historico_numeros = self.extrair_numeros_historico()

        if len(historico_numeros) < 10:
            return None

        previsao_ml, msg_ml = self.ml.prever_proximo_numero(historico_numeros, top_k=25)
        
        if previsao_ml:
            top_25_numeros = [num for num, prob in previsao_ml[:25]]
            
            distribuicao_zonas = self.analisar_distribuicao_zonas_rankeadas(top_25_numeros)
            
            if not distribuicao_zonas:
                return None
                
            distribuicao_dict = dict(distribuicao_zonas)
            distribuicao_ajustada = self.aplicar_padroes_na_previsao(distribuicao_dict)
            
            zonas_rankeadas_ajustadas = sorted(distribuicao_ajustada.items(), key=lambda x: x[1], reverse=True)
            
            zona_primaria, contagem_primaria = zonas_rankeadas_ajustadas[0]
            
            if contagem_primaria < 7:
                return None
            
            zona_secundaria = None
            contagem_secundaria = 0
            
            if len(zonas_rankeadas_ajustadas) > 1:
                zona_secundaria, contagem_secundaria = zonas_rankeadas_ajustadas[1]
                
                if contagem_secundaria >= 5:
                    numeros_primarios = self.numeros_zonas_ml[zona_primaria]
                    numeros_secundarios = self.numeros_zonas_ml[zona_secundaria]
                    
                    numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
                    
                    if len(numeros_combinados) > 15:
                        numeros_combinados = self.sistema_selecao.selecionar_melhores_15_numeros(
                            numeros_combinados, self.historico, "ML"
                        )
                    
                    confianca = self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_primaria)
                    
                    padroes_aplicados = [p for p in self.sequencias_padroes['padroes_detectados'] 
                                       if p['zona'] in [zona_primaria, zona_secundaria] and 
                                       len(self.historico) - p['detectado_em'] <= 15]
                    
                    gatilho_extra = ""
                    if padroes_aplicados:
                        gatilho_extra = f" | Padrões: {len(padroes_aplicados)}"
                    
                    contagem_original_primaria = distribuicao_dict[zona_primaria]
                    contagem_original_secundaria = distribuicao_dict.get(zona_secundaria, 0)
                    
                    gatilho = f'ML CatBoost - Zona {zona_primaria} ({contagem_original_primaria}→{contagem_primaria}/25) + Zona {zona_secundaria} ({contagem_original_secundaria}→{contagem_secundaria}/25) | SEL: {len(numeros_combinados)} números{gatilho_extra}'
                    
                    return {
                        'nome': 'Machine Learning - CatBoost (Duplo)',
                        'numeros_apostar': numeros_combinados,
                        'gatilho': gatilho,
                        'confianca': confianca,
                        'previsao_ml': previsao_ml,
                        'zona_ml': f'{zona_primaria}+{zona_secundaria}',
                        'distribuicao': distribuicao_ajustada,
                        'padroes_aplicados': len(padroes_aplicados),
                        'zonas_envolvidas': [zona_primaria, zona_secundaria],
                        'tipo': 'dupla',
                        'selecao_inteligente': True
                    }
            
            numeros_zona = self.numeros_zonas_ml[zona_primaria]
            
            if len(numeros_zona) > 15:
                numeros_zona = self.sistema_selecao.selecionar_melhores_15_numeros(
                    numeros_zona, self.historico, "ML"
                )
            
            contagem_original = distribuicao_dict[zona_primaria]
            contagem_ajustada = contagem_primaria
            
            confianca = self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_primaria)
            
            padroes_aplicados = [p for p in self.sequencias_padroes['padroes_detectados'] 
                               if p['zona'] == zona_primaria and 
                               len(self.historico) - p['detectado_em'] <= 15]
            
            gatilho_extra = ""
            if padroes_aplicados:
                gatilho_extra = f" | Padrões: {len(padroes_aplicados)}"
            
            return {
                'nome': 'Machine Learning - CatBoost',
                'numeros_apostar': numeros_zona,
                'gatilho': f'ML CatBoost - Zona {zona_primaria} ({contagem_original}→{contagem_ajustada}/25) | SEL: {len(numeros_zona)} números{gatilho_extra}',
                'confianca': confianca,
                'previsao_ml': previsao_ml,
                'zona_ml': zona_primaria,
                'distribuicao': distribuicao_ajustada,
                'padroes_aplicados': len(padroes_aplicados),
                'zonas_envolvidas': [zona_primaria],
                'tipo': 'unica',
                'selecao_inteligente': len(numeros_zona) < len(self.numeros_zonas_ml[zona_primaria])
            }
        
        return None

    def analisar_ml(self):
        return self.analisar_ml_com_inversao()

    def treinar_automatico(self):
        historico_numeros = self.extrair_numeros_historico()
        
        if len(historico_numeros) >= self.ml.min_training_samples:
            try:
                success, message = self.ml.treinar_modelo(historico_numeros)
                if success:
                    logging.info(f"✅ Treinamento automático ML: {message}")
                else:
                    logging.warning(f"⚠️ Treinamento automático falhou: {message}")
            except Exception as e:
                logging.error(f"❌ Erro no treinamento automático: {e}")

    def extrair_numeros_historico(self):
        historico_numeros = []
        for item in list(self.historico):
            if isinstance(item, dict) and 'number' in item:
                historico_numeros.append(item['number'])
            elif isinstance(item, (int, float)):
                historico_numeros.append(int(item))
        return historico_numeros

    def analisar_distribuicao_zonas(self, top_25_numeros):
        contagem_zonas = {}
        
        for zona, numeros in self.numeros_zonas_ml.items():
            count = sum(1 for num in top_25_numeros if num in numeros)
            contagem_zonas[zona] = count
        
        return contagem_zonas if contagem_zonas else None

    def calcular_confianca_zona_ml(self, distribuicao):
        contagem = distribuicao['contagem']
        total = distribuicao['total_zonas']
        percentual = (contagem / total) * 100
        
        if percentual >= 50:
            return 'Muito Alta'
        elif percentual >= 40:
            return 'Alta'
        elif percentual >= 30:
            return 'Média'
        elif percentual >= 25:
            return 'Baixa'
        else:
            return 'Muito Baixa'

    def treinar_modelo_ml(self, historico_completo=None):
        if historico_completo is not None:
            historico_numeros = historico_completo
        else:
            historico_numeros = self.extrair_numeros_historico()
        
        if len(historico_numeros) >= self.ml.min_training_samples:
            success, message = self.ml.treinar_modelo(historico_numeros)
            return success, message
        else:
            return False, f"Histórico insuficiente: {len(historico_numeros)}/{self.ml.min_training_samples} números"

    def get_analise_ml(self):
        if not self.ml.is_trained:
            return "🤖 ML: Modelo não treinado"
        
        if len(self.historico) < 10:
            return "🤖 ML: Aguardando mais dados para análise"
        
        historico_numeros = self.extrair_numeros_historico()
        previsao_ml, msg = self.ml.prever_proximo_numero(historico_numeros, top_k=25)
        
        if previsao_ml:
            if self.ml.models:
                primeiro_modelo = self.ml.models[0]
                modelo_tipo = "CatBoost" if hasattr(primeiro_modelo, 'iterations') else "RandomForest"
            else:
                modelo_tipo = "Não treinado"
            
            analise = f"🤖 ANÁLISE ML - {modelo_tipo.upper()} (TOP 25):\n"
            analise += f"🔄 Treinamentos realizados: {self.ml.contador_treinamento}\n"
            analise += f"📊 Próximo treinamento: {15 - self.contador_sorteios} sorteios\n"
            analise += f"📈 Ensemble: {len(self.ml.models)} modelos\n"
            
            padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                              if len(self.historico) - p['detectado_em'] <= 20]
            
            if padroes_recentes:
                analise += f"🔍 Padrões ativos: {len(padroes_recentes)}\n"
                for padrao in padroes_recentes[-3:]:
                    idade = len(self.historico) - padrao['detectado_em']
                    analise += f"   📈 {padrao['zona']}: {padrao['tipo']} (há {idade} jogos)\n"
            
            analise += "🎯 Previsões (Top 10):\n"
            for i, (num, prob) in enumerate(previsao_ml[:10]):
                analise += f"  {i+1}. Número {num}: {prob:.2%}\n"
            
            top_25_numeros = [num for num, prob in previsao_ml[:25]]
            distribuicao = self.analisar_distribuicao_zonas(top_25_numeros)
            
            if distribuicao:
                distribuicao_ajustada = self.aplicar_padroes_na_previsao(distribuicao)
                
                analise += f"\n🎯 DISTRIBUIÇÃO POR ZONAS (25 números):\n"
                for zona, count in distribuicao_ajustada.items():
                    count_original = distribuicao[zona]
                    ajuste = count - count_original
                    simbolo_ajuste = f" (+{ajuste})" if ajuste > 0 else ""
                    analise += f"  📍 {zona}: {count_original}→{count}/25{simbolo_ajuste}\n"
                
                zona_vencedora = max(distribuicao_ajustada, key=distribuicao_ajustada.get)
                analise += f"\n💡 ZONA RECOMENDADA: {zona_vencedora}\n"
                analise += f"🎯 Confiança: {self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_vencedora)}\n"
                analise += f"🔢 Números da zona: {sorted(self.numeros_zonas_ml[zona_vencedora])}\n"
                analise += f"📈 Percentual: {(distribuicao_ajustada[zona_vencedora]/25)*100:.1f}%\n"
            else:
                analise += "\n⚠️  Nenhuma zona com predominância suficiente (mínimo 7 números)\n"
            
            return analise
        else:
            return "🤖 ML: Erro na previsão"

    def get_estatisticas_padroes(self):
        if not hasattr(self, 'metricas_padroes'):
            return "📊 Métricas de padrões: Não disponível"
        
        total = self.metricas_padroes['padroes_detectados_total']
        if total == 0:
            return "📊 Métricas de padrões: Nenhum padrão validado ainda"
        
        acertos = self.metricas_padroes['padroes_acertados']
        eficiencia = (acertos / total) * 100 if total > 0 else 0
        
        estatisticas = f"📊 EFICIÊNCIA DOS PADRÕES:\n"
        estatisticas += f"✅ Padrões que acertaram: {acertos}/{total} ({eficiencia:.1f}%)\n"
        
        for tipo, dados in self.metricas_padroes['eficiencia_por_tipo'].items():
            if dados['total'] > 0:
                eff_tipo = (dados['acertos'] / dados['total']) * 100
                estatisticas += f"   🎯 {tipo}: {dados['acertos']}/{dados['total']} ({eff_tipo:.1f}%)\n"
        
        padroes_ativos = [p for p in self.sequencias_padroes['padroes_detectados'] 
                         if len(self.historico) - p['detectado_em'] <= 10]
        
        estatisticas += f"🔍 Padrões ativos: {len(padroes_ativos)}\n"
        for padrao in padroes_ativos[-3:]:
            idade = len(self.historico) - padrao['detectado_em']
            estatisticas += f"   📈 {padrao['zona']}: {padrao['tipo']} (há {idade} jogos)\n"
        
        return estatisticas

    def get_info_zonas_ml(self):
        info = {}
        for zona, numeros in self.numeros_zonas_ml.items():
            info[zona] = {
                'numeros': sorted(numeros),
                'quantidade': len(numeros),
                'central': self.zonas_ml[zona],
                'descricao': f"6 antes + 6 depois do {self.zonas_ml[zona]}"
            }
        return info

    def zerar_padroes(self):
        self.sequencias_padroes = {
            'sequencias_ativas': {},
            'historico_sequencias': [],
            'padroes_detectados': []
        }
        self.metricas_padroes = {
            'padroes_detectados_total': 0,
            'padroes_acertados': 0,
            'padroes_errados': 0,
            'eficiencia_por_tipo': {},
            'historico_validacao': []
        }
        logging.info("🔄 Padrões sequenciais e métricas zerados")

# =============================
# SISTEMA DE GESTÃO ATUALIZADO COM ROTAÇÃO POR 3 ACERTOS EM COMBINAÇÕES
# E SISTEMA DE FOCO DINÂMICO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.estrategia_midas = EstrategiaMidas()
        self.estrategia_ml = EstrategiaML()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Zonas"
        self.contador_sorteios_global = 0
        
        # Sistema de rotação automática
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        
        # 🎯 NOVO: Sistema de rotação por 3 acertos em combinações
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []  # Combinações que acertaram na sequência
        self.historico_combinacoes_acerto = []  # Histórico das combinações que acertaram
        
        # 🎯 NOVO: Sistema de combinações dinâmicas
        self.historico_combinacoes = {}  # Combinações dinâmicas
        self.combinacoes_quentes = []    # Combinações com bom desempenho recente
        self.combinacoes_frias = []      # Combinações com mau desempenho recente
        
        # 🎯 NOVO: Definir todas as combinações possíveis de zonas
        self.todas_combinacoes_zonas = [
            ['Vermelha', 'Azul'],
            ['Vermelha', 'Amarela'], 
            ['Azul', 'Amarela']
        ]
        
        # 🎯 ADICIONAR SISTEMA DE TENDÊNCIAS
        self.sistema_tendencias = SistemaTendencias()
        
        # 🎯 NOVO: Sistema de foco dinâmico (ADICIONADO)
        self.combinacoes_em_alta = []  # Combinações com performance crescente
        self.combinacoes_em_baixa = []  # Combinações com performance decrescente
        self.historico_performance = {}  # Performance ao longo do tempo
        self.ultima_analise_performance = None

    # =============================
    # 🎯 MÉTODOS DO SISTEMA DE FOCO DINÂMICO
    # =============================

    def analisar_performance_dinamica(self):
        """🎯 Analisa performance das combinações em tempo real"""
        combinacoes_performance = {}
        
        # Analisar cada combinação
        for combinacao, dados in self.historico_combinacoes.items():
            if dados['total'] >= 3:  # Pelo menos 3 tentativas
                eficiencia_atual = dados.get('eficiencia', 0)
                sequencia = dados.get('sequencia_acertos', 0)
                total = dados['total']
                
                # 🎯 TENDÊNCIA: Performance está melhorando ou piorando?
                if combinacao in self.historico_performance:
                    historico = self.historico_performance[combinacao]
                    
                    if len(historico) >= 3:
                        # Calcular tendência (últimos 3 vs anteriores)
                        ultimos_3 = historico[-3:] if len(historico) >= 3 else historico
                        anteriores_3 = historico[-6:-3] if len(historico) >= 6 else []
                        
                        media_ultimos = sum(ultimos_3) / len(ultimos_3) if ultimos_3 else 0
                        media_anteriores = sum(anteriores_3) / len(anteriores_3) if anteriores_3 else 0
                        
                        tendencia = "CRESCENTE" if media_ultimos > media_anteriores else "DECRESCENTE"
                    else:
                        tendencia = "NEUTRA"
                else:
                    tendencia = "NEUTRA"
                    self.historico_performance[combinacao] = []
                
                # Adicionar performance atual ao histórico
                self.historico_performance[combinacao].append(eficiencia_atual)
                if len(self.historico_performance[combinacao]) > 10:
                    self.historico_performance[combinacao].pop(0)
                
                # 🎯 SCORE DINÂMICO: Combinar eficiência + tendência + sequência
                score = eficiencia_atual
                
                # Bônus por tendência crescente
                if tendencia == "CRESCENTE":
                    score += 15
                elif tendencia == "DECRESCENTE":
                    score -= 10
                
                # Bônus por sequência de acertos
                if sequencia >= 2:
                    score += (sequencia * 5)  # +5% por acerto consecutivo
                
                # Bônus por volume de dados (mais confiável)
                if total >= 5:
                    score += 5
                if total >= 10:
                    score += 10
                
                combinacoes_performance[combinacao] = {
                    'eficiencia': eficiencia_atual,
                    'score': score,
                    'tendencia': tendencia,
                    'sequencia': sequencia,
                    'total': total
                }
        
        # 🎯 CLASSIFICAR COMBINAÇÕES
        self.combinacoes_em_alta = []
        self.combinacoes_em_baixa = []
        
        for combo, dados in combinacoes_performance.items():
            if dados['score'] >= 60:  # Score mínimo para ser considerada "em alta"
                if dados['tendencia'] == "CRESCENTE" or dados['sequencia'] >= 2:
                    self.combinacoes_em_alta.append((combo, dados))
            elif dados['score'] < 40:  # Score baixo para ser considerada "em baixa"
                self.combinacoes_em_baixa.append((combo, dados))
        
        # Ordenar combinações em alta por score (melhores primeiro)
        self.combinacoes_em_alta.sort(key=lambda x: x[1]['score'], reverse=True)
        
        self.ultima_analise_performance = combinacoes_performance
        return combinacoes_performance

    def get_melhor_combinacao_atual(self):
        """🎯 Retorna a melhor combinação baseada em performance dinâmica"""
        # Atualizar análise
        self.analisar_performance_dinamica()
        
        if not self.combinacoes_em_alta:
            # Se não há combinações em alta, usar histórico
            if self.combinacoes_quentes:
                return self.combinacoes_quentes[0]
            return None
        
        # 🎯 ESCOLHER A MELHOR COMBINAÇÃO EM ALTA
        melhor_combo, dados = self.combinacoes_em_alta[0]
        
        # Log detalhado
        logging.info(f"🎯 MELHOR COMBO DETECTADO: {melhor_combo}")
        logging.info(f"   Eficiência: {dados['eficiencia']:.1f}%")
        logging.info(f"   Score: {dados['score']:.1f}")
        logging.info(f"   Tendência: {dados['tendencia']}")
        logging.info(f"   Sequência: {dados['sequencia']} acertos seguidos")
        logging.info(f"   Total: {dados['total']} jogos")
        
        return melhor_combo

    def aplicar_rotacao_inteligente(self):
        """🎯 ROTAÇÃO BASEADA NAS COMBINAÇÕES QUE ESTÃO FUNCIONANDO"""
        estrategia_atual = self.estrategia_selecionada
        
        # 🎯 SE É ESTRATÉGIA ZONAS
        if estrategia_atual == "Zonas":
            # Primeiro: Identificar melhor combinação ATUAL
            melhor_combo = self.get_melhor_combinacao_atual()
            
            if melhor_combo:
                # Verificar se já estamos usando a melhor combinação
                if self.previsao_ativa and self.previsao_ativa.get('zonas_envolvidas'):
                    combinacao_atual = tuple(sorted(self.previsao_ativa['zonas_envolvidas']))
                    
                    if combinacao_atual == melhor_combo:
                        # 🎯 JÁ ESTAMOS NA MELHOR - MANTER
                        logging.info(f"🎯 JÁ ESTAMOS NA MELHOR COMBINAÇÃO: {melhor_combo}")
                        self.sequencia_erros = 0
                        return False
                    else:
                        # 🎯 MUDAR PARA A MELHOR COMBINAÇÃO
                        success = self.criar_previsao_com_combinacao(melhor_combo)
                        if success:
                            self.sequencia_erros = 0
                            
                            # Notificação
                            enviar_rotacao_automatica(
                                f"Zonas {self.combinacao_para_texto(combinacao_atual)}",
                                f"Zonas {self.combinacao_para_texto(melhor_combo)} (MELHOR)"
                            )
                            logging.info(f"🔄 MUDANDO PARA MELHOR COMBO: {combinacao_atual} → {melhor_combo}")
                            return True
            
            # Se não conseguiu mudar para melhor combo, tentar outras
            if self.previsao_ativa and self.previsao_ativa.get('zonas_envolvidas'):
                combinacao_atual = tuple(sorted(self.previsao_ativa['zonas_envolvidas']))
                
                # 🎯 EVITAR COMBINAÇÕES EM BAIXA
                if combinacao_atual in [c for c, _ in self.combinacoes_em_baixa]:
                    # Rotacionar para qualquer outra que não seja em baixa
                    todas = [('Vermelha', 'Azul'), ('Vermelha', 'Amarela'), ('Azul', 'Amarela')]
                    
                    for combo in todas:
                        combo_tuple = tuple(sorted(combo))
                        if (combo_tuple != combinacao_atual and 
                            combo_tuple not in [c for c, _ in self.combinacoes_em_baixa]):
                            
                            success = self.criar_previsao_com_combinacao(combo_tuple)
                            if success:
                                self.sequencia_erros = 0
                                logging.info(f"🔄 EVITANDO COMBO EM BAIXA: {combinacao_atual} → {combo_tuple}")
                                return True
        
        # Rotação normal se nada acima funcionou
        if estrategia_atual == "Zonas":
            self.estrategia_selecionada = "ML"
            self.sequencia_erros = 0
            enviar_rotacao_automatica("Zonas", "ML")
            return True
        elif estrategia_atual == "ML":
            self.estrategia_selecionada = "Zonas"
            self.sequencia_erros = 0
            enviar_rotacao_automatica("ML", "Zonas")
            return True
        
        return False

    def criar_previsao_inteligente(self):
        """🎯 CRIAR PREVISÃO BASEADA NAS COMBINAÇÕES QUE FUNCIONAM"""
        # Atualizar análise
        self.analisar_performance_dinamica()
        
        # 🎯 TENTAR USAR A MELHOR COMBINAÇÃO EM ALTA
        melhor_combo = self.get_melhor_combinacao_atual()
        
        if melhor_combo:
            success = self.criar_previsao_com_combinacao(melhor_combo)
            if success:
                logging.info(f"🎯 PREVISÃO INTELIGENTE: Usando melhor combo {melhor_combo}")
                return True
        
        # 🎯 SE NÃO HÁ COMBINAÇÕES EM ALTA, USAR QUALQUER UMA QUE NÃO ESTEJA EM BAIXA
        todas = [('Vermelha', 'Azul'), ('Vermelha', 'Amarela'), ('Azul', 'Amarela')]
        
        for combo in todas:
            combo_tuple = tuple(sorted(combo))
            
            # Evitar combinações em baixa
            combos_em_baixa_lista = [c for c, _ in self.combinacoes_em_baixa]
            if combo_tuple not in combos_em_baixa_lista:
                success = self.criar_previsao_com_combinacao(combo_tuple)
                if success:
                    logging.info(f"🎯 PREVISÃO ALTERNATIVA: Usando combo {combo_tuple}")
                    return True
        
        return False

    # =============================
    # MÉTODOS ADICIONAIS PARA MONITORAMENTO
    # =============================

    def get_analise_performance_completa(self):
        """Retorna análise completa das performances"""
        analise = "📊 ANÁLISE DE PERFORMANCE DINÂMICA\n"
        analise += "=" * 60 + "\n"
        
        if not self.ultima_analise_performance:
            return analise + "Aguardando dados suficientes..."
        
        analise += "🎯 COMBINAÇÕES EM ALTA (FOCAR AQUI):\n"
        for combo, dados in self.combinacoes_em_alta[:3]:  # Top 3
            analise += f"  🔥 {combo[0]}+{combo[1]}: {dados['eficiencia']:.1f}% "
            analise += f"(Score: {dados['score']:.1f}, Tendência: {dados['tendencia']})\n"
        
        if self.combinacoes_em_baixa:
            analise += "\n🚫 COMBINAÇÕES EM BAIXA (EVITAR):\n"
            for combo, dados in self.combinacoes_em_baixa:
                analise += f"  ❌ {combo[0]}+{combo[1]}: {dados['eficiencia']:.1f}%\n"
        
        analise += "\n📈 PERFORMANCE DETALHADA:\n"
        for combo, dados in self.ultima_analise_performance.items():
            analise += f"  📊 {combo[0]}+{combo[1]}: {dados['eficiencia']:.1f}% "
            analise += f"| Score: {dados['score']:.1f} | Tendência: {dados['tendencia']} "
            analise += f"| Seq: {dados['sequencia']} | Jogos: {dados['total']}\n"
        
        # 🎯 RECOMENDAÇÃO
        if self.combinacoes_em_alta:
            melhor = self.combinacoes_em_alta[0]
            analise += f"\n💡 RECOMENDAÇÃO: FOCAR em {melhor[0][0]}+{melhor[0][1]} "
            analise += f"(Score: {melhor[1]['score']:.1f})\n"
        
        return analise

    # =============================
    # MÉTODOS EXISTENTES DO SISTEMA (MANTIDOS COM ATUALIZAÇÕES)
    # =============================

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def treinar_modelo_ml(self, historico_completo=None):
        return self.estrategia_ml.treinar_modelo_ml(historico_completo)

    def atualizar_desempenho_combinacao(self, zonas_envolvidas, acerto):
        """Atualiza desempenho de combinações de forma dinâmica"""
        if len(zonas_envolvidas) > 1:
            combinacao = tuple(sorted(zonas_envolvidas))
            
            # Inicializar se não existe
            if combinacao not in self.historico_combinacoes:
                self.historico_combinacoes[combinacao] = {
                    'acertos': 0, 
                    'total': 0, 
                    'eficiencia': 0.0,
                    'ultimo_jogo': len(self.historico_desempenho),
                    'sequencia_acertos': 0,
                    'sequencia_erros': 0
                }
            
            dados = self.historico_combinacoes[combinacao]
            dados['total'] += 1
            dados['ultimo_jogo'] = len(self.historico_desempenho)
            
            if acerto:
                dados['acertos'] += 1
                dados['sequencia_acertos'] += 1
                dados['sequencia_erros'] = 0
                
                # 🎯 NOVO: Registrar combinação que acertou para sequência
                if combinacao not in self.ultima_combinacao_acerto:
                    self.ultima_combinacao_acerto.append(combinacao)
                    # Manter apenas as últimas 3 combinações únicas
                    if len(self.ultima_combinacao_acerto) > 3:
                        self.ultima_combinacao_acerto.pop(0)
                
                # 🎯 NOVO: Adicionar ao histórico geral
                self.historico_combinacoes_acerto.append(combinacao)
                if len(self.historico_combinacoes_acerto) > 10:
                    self.historico_combinacoes_acerto.pop(0)
                    
            else:
                dados['sequencia_erros'] += 1
                dados['sequencia_acertos'] = 0
            
            # Calcular eficiência
            if dados['total'] > 0:
                dados['eficiencia'] = (dados['acertos'] / dados['total']) * 100
            
            # 🎯 ATUALIZAR LISTAS DINÂMICAS (INCLUINDO FOCO DINÂMICO)
            self.atualizar_combinacoes_quentes_frias()
            # 🎯 ATUALIZAR ANÁLISE DINÂMICA
            self.analisar_performance_dinamica()
    
    def atualizar_combinacoes_quentes_frias(self):
        """Atualiza dinamicamente as combinações quentes e frias"""
        # Resetar listas
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        # Analisar apenas combinações com pelo menos 2 tentativas
        combinacoes_ativas = {k: v for k, v in self.historico_combinacoes.items() 
                             if v['total'] >= 2}
        
        for combinacao, dados in combinacoes_ativas.items():
            eficiencia = dados['eficiencia']
            total_jogos = dados['total']
            sequencia_acertos = dados['sequencia_acertos']
            
            # 🎯 CRITÉRIOS PARA COMBINAÇÃO QUENTE
            if (eficiencia >= 50 or 
                (eficiencia >= 40 and total_jogos >= 3) or
                sequencia_acertos >= 2):
                self.combinacoes_quentes.append(combinacao)
            
            # 🎯 CRITÉRIOS PARA COMBINAÇÃO FRIA
            elif (eficiencia < 25 and total_jogos >= 3) or dados['sequencia_erros'] >= 2:
                self.combinacoes_frias.append(combinacao)

    def get_combinacao_recomendada(self):
        """Retorna a melhor combinação baseada em desempenho recente"""
        if not self.combinacoes_quentes:
            return None
        
        # 🎯 PRIORIZAR COMBINAÇÕES COM SEQUÊNCIA DE ACERTOS
        combinacoes_com_sequencia = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if combo in self.combinacoes_quentes and dados['sequencia_acertos'] >= 1
        ]
        
        if combinacoes_com_sequencia:
            # Ordenar por sequência de acertos (maior primeiro)
            combinacoes_com_sequencia.sort(key=lambda x: x[1]['sequencia_acertos'], reverse=True)
            return combinacoes_com_sequencia[0][0]
        
        # 🎯 SE NÃO HÁ SEQUÊNCIA, USAR EFICIÊNCIA
        combinacoes_eficientes = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if combo in self.combinacoes_quentes
        ]
        
        if combinacoes_eficientes:
            combinacoes_eficientes.sort(key=lambda x: x[1]['eficiencia'], reverse=True)
            return combinacoes_eficientes[0][0]
        
        return None

    def get_combinacoes_alternativas(self, combinacao_evitar):
        """🎯 NOVO: Retorna combinações alternativas excluindo as que acertaram recentemente"""
        combinacoes_disponiveis = []
        
        for combo in self.todas_combinacoes_zonas:
            combo_tuple = tuple(sorted(combo))
            
            # Evitar a combinação atual
            if combo_tuple == combinacao_evitar:
                continue
                
            # Evitar combinações que acertaram nos últimos 3 acertos
            if combo_tuple in self.ultima_combinacao_acerto:
                continue
                
            # 🎯 EVITAR COMBINAÇÕES EM BAIXA (FOCO DINÂMICO)
            if combo_tuple in [c for c, _ in self.combinacoes_em_baixa]:
                continue
                
            # Verificar eficiência da combinação
            dados_combo = self.historico_combinacoes.get(combo_tuple, {})
            eficiencia = dados_combo.get('eficiencia', 0)
            total = dados_combo.get('total', 0)
            
            # Priorizar combinações com boa eficiência ou poucos dados
            if total == 0 or eficiencia >= 25:  # Reduzido de 30 para 25
                combinacoes_disponiveis.append(combo_tuple)
    
        # 🎯 SE NÃO ENCONTROU COMBINAÇÕES BOAS, USAR TODAS EXCETO A ATUAL
        if not combinacoes_disponiveis:
            for combo in self.todas_combinacoes_zonas:
                combo_tuple = tuple(sorted(combo))
                if combo_tuple != combinacao_evitar:
                    combinacoes_disponiveis.append(combo_tuple)
        
        return combinacoes_disponiveis

    def deve_evitar_combinacao(self, combinacao):
        """Verifica se deve evitar uma combinação específica"""
        if combinacao in self.combinacoes_frias:
            return True
        
        # 🎯 EVITAR COMBINAÇÕES COM MAU DESEMPENHO NO FOCO DINÂMICO
        if combinacao in [c for c, _ in self.combinacoes_em_baixa]:
            return True
        
        # 🎯 EVITAR COMBINAÇÕES COM MAU DESEMPENHO HISTÓRICO
        dados = self.historico_combinacoes.get(combinacao, {})
        if dados and dados.get('total', 0) >= 3 and dados.get('eficiencia', 0) < 20:
            return True
            
        return False

    def calcular_performance_estrategias(self):
        """Calcula performance recente das estratégias"""
        performance = {}
        historico_recente = self.historico_desempenho[-10:] if len(self.historico_desempenho) >= 10 else self.historico_desempenho
        
        for resultado in historico_recente:
            estrategia = resultado['estrategia']
            if estrategia not in performance:
                performance[estrategia] = {'acertos': 0, 'total': 0}
            
            performance[estrategia]['total'] += 1
            if resultado['acerto']:
                performance[estrategia]['acertos'] += 1
        
        # Calcular percentuais
        for estrategia, dados in performance.items():
            if dados['total'] > 0:
                performance[estrategia] = (dados['acertos'] / dados['total']) * 100
            else:
                performance[estrategia] = 0
        
        return performance

    def rotacionar_estrategia_automaticamente(self, acerto, nome_estrategia, zonas_envolvidas):
        """🎯 ROTAÇÃO OTIMIZADA - FOCA NO QUE FUNCIONA"""
        
        # Atualizar desempenho
        self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
        
        if acerto:
            self.sequencia_acertos += 1
            self.sequencia_erros = 0
            
            # 🎯 SE ESTÁ ACERTANDO MUITO (>70%), MANTER MESMO COM MUITOS ACERTOS
            if len(zonas_envolvidas) > 1:
                combinacao_atual = tuple(sorted(zonas_envolvidas))
                dados = self.historico_combinacoes.get(combinacao_atual, {})
                eficiencia = dados.get('eficiencia', 0)
                
                # Se eficiência > 70%, pode manter por mais tempo
                if eficiencia > 70:
                    max_acertos_para_rotacao = 5  # Aumenta de 3 para 5
                else:
                    max_acertos_para_rotacao = 3
                
                if self.sequencia_acertos >= max_acertos_para_rotacao:
                    # Verificar se realmente foram na mesma combinação
                    ultimos_acertos = []
                    for resultado in reversed(self.historico_desempenho[-max_acertos_para_rotacao:]):
                        if resultado['acerto'] and resultado.get('zonas_envolvidas'):
                            ultima_combinacao = tuple(sorted(resultado['zonas_envolvidas']))
                            ultimos_acertos.append(ultima_combinacao)
                    
                    if (len(ultimos_acertos) >= max_acertos_para_rotacao and 
                        all(combo == combinacao_atual for combo in ultimos_acertos)):
                        
                        # 🎯 MAS SÓ ROTACIONA SE A COMBO NÃO FOR MUITO BOA
                        if eficiencia < 80:  # Se for muito boa (<80%), mantém
                            return self.aplicar_rotacao_por_acertos_combinacoes(combinacao_atual)
            
            return False
        
        else:
            self.sequencia_erros += 1
            self.sequencia_acertos = 0
            
            # 🎯 ATUALIZAR ANÁLISE DINÂMICA
            self.analisar_performance_dinamica()
            
            if len(zonas_envolvidas) > 1:
                combinacao = tuple(sorted(zonas_envolvidas))
                
                # 🎯 SE A COMBO ESTÁ EM BAIXA (FOCO DINÂMICO), ROTACIONAR RÁPIDO
                combos_em_baixa_lista = [c for c, _ in self.combinacoes_em_baixa]
                if combinacao in combos_em_baixa_lista and self.sequencia_erros >= 1:
                    logging.info(f"🚫 Combo em baixa detectada - Rotacionando após 1 erro")
                    return self.aplicar_rotacao_inteligente()
                
                # 🎯 SE EFICIÊNCIA < 50%, ROTACIONAR RÁPIDO
                dados = self.historico_combinacoes.get(combinacao, {})
                eficiencia = dados.get('eficiencia', 0)
                
                if eficiencia < 50 and self.sequencia_erros >= 1:
                    logging.info(f"🚫 Combo ineficiente ({eficiencia:.1f}%) - Rotacionando após 1 erro")
                    return self.aplicar_rotacao_inteligente()
            
            # Rotação normal após 2 erros
            if self.sequencia_erros >= 2:
                return self.aplicar_rotacao_inteligente()
            
            return False

    def aplicar_rotacao_por_acertos_combinacoes(self, combinacao_atual):
        """🎯 NOVA REGRA: Rotação após 3 acertos seguidos - alterna para outras combinações"""
        
        # 🎯 OBTER COMBINAÇÕES ALTERNATIVAS (excluindo as que acertaram recentemente)
        combinacoes_alternativas = self.get_combinacoes_alternativas(combinacao_atual)
        
        if not combinacoes_alternativas:
            logging.info("⚠️ Nenhuma combinação alternativa disponível - mantendo atual")
            return False
        
        # 🎯 ESCOLHER A MELHOR COMBINAÇÃO ALTERNATIVA (USANDO FOCO DINÂMICO)
        combinacao_escolhida = self.escolher_melhor_combinacao_alternativa(combinacoes_alternativas)
        
        if not combinacao_escolhida:
            logging.info("⚠️ Não foi possível escolher uma combinação alternativa")
            return False
        
        # 🎯 FORÇAR A CRIAÇÃO DE UMA NOVA PREVISÃO COM A COMBINAÇÃO ALTERNATIVA
        success = self.criar_previsao_com_combinacao(combinacao_escolhida)
        
        if success:
            self.sequencia_acertos = 0  # Resetar contador após rotação
            self.ultima_combinacao_acerto = []  # Limpar histórico de combinações que acertaram
            
            # Enviar notificação especial
            enviar_rotacao_por_acertos_combinacoes(combinacao_atual, combinacao_escolhida)
            logging.info(f"🔄 ROTAÇÃO POR ACERTOS: {combinacao_atual} → {combinacao_escolhida}")
            return True
        
        return False

    def escolher_melhor_combinacao_alternativa(self, combinacoes):
        """Escolhe a melhor combinação alternativa baseada em desempenho e foco dinâmico"""
        if not combinacoes:
            return None
        
        # 🎯 ESTRATÉGIA: Priorizar combinações em ALTA no foco dinâmico
        for combo in combinacoes:
            if combo in [c for c, _ in self.combinacoes_em_alta]:
                return combo
        
        # 🎯 Se nenhuma em alta, tentar incluir a zona Amarela se não estava na combinação anterior
        for combo in combinacoes:
            if 'Amarela' in combo:
                return combo
        
        # 🎯 Se ainda não escolheu, usar combinação com melhor eficiência
        melhor_eficiencia = -1
        melhor_combo = None
        
        for combo in combinacoes:
            dados = self.historico_combinacoes.get(combo, {})
            eficiencia = dados.get('eficiencia', 0) if dados else 0
            
            if eficiencia > melhor_eficiencia:
                melhor_eficiencia = eficiencia
                melhor_combo = combo
        
        return melhor_combo if melhor_combo else combinacoes[0]

    def criar_previsao_com_combinacao(self, combinacao):
        """Cria uma nova previsão forçada com a combinação especificada"""
        try:
            zonas_list = list(combinacao)
            
            # 🎯 CRIAR PREVISÃO FORÇADA COM A NOVA COMBINAÇÃO
            previsao_forcada = self.estrategia_zonas.criar_previsao_dupla(
                zonas_list[0], 
                zonas_list[1], 
                "ROTAÇÃO-AUTOMÁTICA"
            )
            
            if previsao_forcada:
                self.previsao_ativa = previsao_forcada
                self.estrategia_selecionada = "Zonas"
                
                # 🎯 FORÇAR O SISTEMA A USAR ESTA PREVISÃO IMEDIATAMENTE
                logging.info(f"🎯 Nova previsão criada com combinação: {combinacao}")
                return True
                
        except Exception as e:
            logging.error(f"❌ Erro ao criar previsão com combinação {combinacao}: {e}")
        
        return False

    def combinacao_para_texto(self, combinacao):
        """Converte combinação para texto legível"""
        if len(combinacao) == 2:
            zona1, zona2 = combinacao
            return f"{zona1}+{zona2}"
        return str(combinacao)

    def processar_novo_numero(self, numero):
        if isinstance(numero, dict) and 'number' in numero:
            numero_real = numero['number']
        else:
            numero_real = numero
            
        self.contador_sorteios_global += 1
            
        if self.previsao_ativa:
            # VERIFICAÇÃO DE ACERTO PARA MÚLTIPLAS ZONAS
            acerto = False
            zonas_acertadas = []
            nome_estrategia = self.previsao_ativa['nome']
            
            # Verificar se o número está em qualquer uma das zonas envolvidas
            zonas_envolvidas = self.previsao_ativa.get('zonas_envolvidas', [])
            if not zonas_envolvidas:
                # Fallback para lógica antiga
                acerto = numero_real in self.previsao_ativa['numeros_apostar']
                if acerto:
                    # Descobrir qual zona acertou
                    if 'Zonas' in nome_estrategia:
                        for zona, numeros in self.estrategia_zonas.numeros_zonas.items():
                            if numero_real in numeros:
                                zonas_acertadas.append(zona)
                                break
                    elif 'ML' in nome_estrategia:
                        for zona, numeros in self.estrategia_ml.numeros_zonas_ml.items():
                            if numero_real in numeros:
                                zonas_acertadas.append(zona)
                                break
            else:
                # Nova lógica para múltiplas zonas
                for zona in zonas_envolvidas:
                    if 'Zonas' in nome_estrategia:
                        numeros_zona = self.estrategia_zonas.numeros_zonas[zona]
                    elif 'ML' in nome_estrategia:
                        numeros_zona = self.estrategia_ml.numeros_zonas_ml[zona]
                    else:
                        continue
                    
                    if numero_real in numeros_zona:
                        acerto = True
                        zonas_acertadas.append(zona)
            
            # 🎯 ATUALIZAR DESEMPENHO DA COMBINAÇÃO
            self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
            
            # 🎯 ATUALIZAR ANÁLISE DE TENDÊNCIAS
            self.atualizar_analise_tendencias(numero_real, zonas_acertadas[0] if zonas_acertadas else None, acerto)
            
            # Verifica e aplica rotação automática se necessário
            rotacionou = self.rotacionar_estrategia_automaticamente(acerto, nome_estrategia, zonas_envolvidas)
            
            if nome_estrategia not in self.estrategias_contador:
                self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
            
            self.estrategias_contador[nome_estrategia]['total'] += 1
            if acerto:
                self.estrategias_contador[nome_estrategia]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1
            
            # Envia resultado super simplificado
            zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
            enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome_estrategia,
                'previsao': self.previsao_ativa['numeros_apostar'],
                'rotacionou': rotacionou,
                'zona_acertada': zona_acertada_str,
                'zonas_envolvidas': zonas_envolvidas,
                'tipo_aposta': self.previsao_ativa.get('tipo', 'unica'),
                'sequencia_acertos': self.sequencia_acertos,
                'sequencia_erros': self.sequencia_erros,
                'ultima_combinacao_acerto': self.ultima_combinacao_acerto.copy()
            })
            
            self.previsao_ativa = None
        
        self.estrategia_zonas.adicionar_numero(numero_real)
        self.estrategia_midas.adicionar_numero(numero_real)
        self.estrategia_ml.adicionar_numero(numero_real)
        
        nova_estrategia = None
        
        if self.estrategia_selecionada == "Zonas":
            nova_estrategia = self.estrategia_zonas.analisar_zonas()
        elif self.estrategia_selecionada == "Midas":
            nova_estrategia = self.estrategia_midas.analisar_midas()
        elif self.estrategia_selecionada == "ML":
            nova_estrategia = self.estrategia_ml.analisar_ml()
        
        if nova_estrategia:
            self.previsao_ativa = nova_estrategia
            enviar_previsao_super_simplificada(nova_estrategia)

    def atualizar_analise_tendencias(self, numero, zona_acertada=None, acerto_ultima=False):
        """Atualiza a análise de tendências"""
        try:
            # Obter zonas rankeadas atuais
            zonas_rankeadas = self.estrategia_zonas.get_zonas_rankeadas()
            if not zonas_rankeadas:
                return
            
            # Analisar tendência
            analise_tendencia = self.sistema_tendencias.analisar_tendencia(
                zonas_rankeadas, acerto_ultima, zona_acertada
            )
            
            # Registrar no histórico
            self.sistema_tendencias.historico_tendencias.append(analise_tendencia)
            
            # 🚨 NOTIFICAÇÕES AUTOMÁTICAS BASEADAS NA TENDÊNCIA
            self.enviar_notificacoes_tendencia(analise_tendencia)
            
        except Exception as e:
            logging.error(f"Erro na análise de tendências: {e}")

    def enviar_notificacoes_tendencia(self, analise_tendencia):
        """Envia notificações baseadas no estado da tendência"""
        estado = analise_tendencia['estado']
        mensagem = analise_tendencia['mensagem']
        zona = analise_tendencia['zona_dominante']
        
        if estado == "ativa" and analise_tendencia['acao'] == "operar":
            # 🔥 TENDÊNCIA CONFIRMADA - OPERAR
            enviar_telegram(f"🎯 TENDÊNCIA CONFIRMADA\n"
                          f"📍 Zona: {zona}\n"
                          f"📈 Estado: {estado}\n"
                          f"💡 Ação: OPERAR\n"
                          f"📊 {mensagem}")
            
        elif estado == "enfraquecendo":
            # ⚠️ TENDÊNCIA ENFRAQUECENDO - CUIDADO
            enviar_telegram(f"⚠️ TENDÊNCIA ENFRAQUECENDO\n"
                          f"📍 Zona: {zona}\n"
                          f"📈 Estado: {estado}\n"
                          f"💡 Ação: AGUARDAR\n"
                          f"📊 {mensagem}")
            
        elif estado == "morta":
            # 🟥 TENDÊNCIA MORTA - PARAR
            enviar_telegram(f"🟥 TENDÊNCIA MORTA\n"
                          f"📈 Estado: {estado}\n"
                          f"💡 Ação: PARAR\n"
                          f"📊 {mensagem}")

    def get_analise_tendencias_completa(self):
        """Retorna análise completa das tendências"""
        analise = "🎯 SISTEMA DE DETECÇÃO DE TENDÊNCIAS\n"
        analise += "=" * 60 + "\n"
        
        resumo = self.sistema_tendencias.get_resumo_tendencia()
        
        analise += f"📊 ESTADO ATUAL: {resumo['estado'].upper()}\n"
        analise += f"📍 ZONA ATIVA: {resumo['zona_ativa'] or 'Nenhuma'}\n"
        analise += f"🎯 CONTADORES: {resumo['contadores']['acertos']} acertos, {resumo['contadores']['erros']} erros\n"
        analise += f"📈 CONFIRMAÇÕES: {resumo['contadores']['confirmacoes']}\n"
        analise += f"🔄 OPERAÇÕES: {resumo['contadores']['operacoes']}\n"
        
        analise += "\n📋 HISTÓRICO RECENTE DE ZONAS:\n"
        for i, zona in enumerate(resumo['historico_zonas'][-8:]):
            analise += f"  {i+1:2d}. {zona}\n"
        
        # Última análise detalhada
        if self.sistema_tendencias.historico_tendencias:
            ultima = self.sistema_tendencias.historico_tendencias[-1]
            analise += f"\n📝 ÚLTIMA ANÁLISE:\n"
            analise += f"  Estado: {ultima['estado']}\n"
            analise += f"  Confiança: {ultima['confianca']:.0%}\n"
            analise += f"  Ação: {ultima['acao'].upper()}\n"
            analise += f"  Mensagem: {ultima['mensagem']}\n"
        
        # RECOMENDAÇÃO BASEADA NO FLUXOGRAMA
        analise += "\n💡 RECOMENDAÇÃO DO FLUXOGRAMA:\n"
        estado = resumo['estado']
        if estado == "aguardando":
            analise += "  👀 Observar últimas 10-20 rodadas\n"
            analise += "  🎯 Identificar zona dupla mais forte\n"
        elif estado == "formando":
            analise += "  📈 Tendência se formando\n"
            analise += "  ⏳ Aguardar confirmação (1-2 acertos)\n"
        elif estado == "ativa":
            analise += "  🔥 TENDÊNCIA CONFIRMADA\n"
            analise += "  💰 Operar por 2-4 jogadas no máximo\n"
            analise += "  🎯 Apostar na zona dominante\n"
            analise += "  ⛔ Parar ao primeiro erro\n"
        elif estado == "enfraquecendo":
            analise += "  ⚠️ TENDÊNCIA ENFRAQUECENDO\n"
            analise += "  🚫 Evitar novas entradas\n"
            analise += "  👀 Observar sinais de morte\n"
        elif estado == "morta":
            analise += "  🟥 TENDÊNCIA MORTA\n"
            analise += "  🛑 PARAR OPERAÇÕES\n"
            analise += "  🔄 Aguardar 10-20 rodadas\n"
            analise += "  📊 Observar novo padrão\n"
        
        return analise

    def zerar_estatisticas_desempenho(self):
        """Zera todas as estatísticas de desempenho"""
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        
        # 🎯 ZERAR NOVAS VARIÁVEIS DE ACERTOS
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        # 🎯 ZERAR COMBINAÇÕES DINÂMICAS
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        # 🎯 ZERAR SISTEMA DE FOCO DINÂMICO
        self.combinacoes_em_alta = []
        self.combinacoes_em_baixa = []
        self.historico_performance = {}
        self.ultima_analise_performance = None
        
        # Zerar estatísticas das estratégias
        self.estrategia_zonas.zerar_estatisticas()
        
        # 🎯 ZERAR SISTEMA DE TENDÊNCIAS
        self.sistema_tendencias = SistemaTendencias()
        
        logging.info("📊 Todas as estatísticas de desempenho foram zeradas")
        salvar_sessao()

    def reset_recente_estatisticas(self):
        """Faz um reset recente mantendo apenas os últimos 10 resultados"""
        if len(self.historico_desempenho) > 10:
            # Manter apenas os últimos 10 resultados
            self.historico_desempenho = self.historico_desempenho[-10:]
            
            # Recalcular acertos e erros
            self.acertos = sum(1 for resultado in self.historico_desempenho if resultado['acerto'])
            self.erros = len(self.historico_desempenho) - self.acertos
            
            # Recalcular contadores por estratégia
            self.estrategias_contador = {}
            for resultado in self.historico_desempenho:
                estrategia = resultado['estrategia']
                if estrategia not in self.estrategias_contador:
                    self.estrategias_contador[estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[estrategia]['total'] += 1
                if resultado['acerto']:
                    self.estrategias_contador[estrategia]['acertos'] += 1
            
            # Recalcular sequências
            ultimos_resultados = self.historico_desempenho[-5:]
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            
            for resultado in reversed(ultimos_resultados):
                if resultado['acerto']:
                    self.sequencia_acertos += 1
                else:
                    break
                    
            for resultado in reversed(ultimos_resultados):
                if not resultado['acerto']:
                    self.sequencia_erros += 1
                else:
                    break
            
         #   logging.info("🔄 Estatísticas recent
            logging.info("🔄 Estatísticas recentes recalculadas (últimos 10 resultados)")
        else:
            logging.info("📊 Histórico menor que 10 resultados, mantendo tudo")
        
        salvar_sessao()

    def get_estatisticas_gerais(self):
        """Retorna estatísticas gerais do sistema"""
        total = self.acertos + self.erros
        acuracia = (self.acertos / total * 100) if total > 0 else 0
        
        return {
            'acertos': self.acertos,
            'erros': self.erros,
            'total': total,
            'acuracia': f"{acuracia:.1f}%",
            'sequencia_acertos': self.sequencia_acertos,
            'sequencia_erros': self.sequencia_erros,
            'estrategia_atual': self.estrategia_selecionada,
            'sorteios_processados': self.contador_sorteios_global,
            'estrategias_contador': self.estrategias_contador,
            'previsao_ativa': bool(self.previsao_ativa),
            'tendencias_estado': self.sistema_tendencias.estado_tendencia if hasattr(self, 'sistema_tendencias') else 'N/A'
        }

    def get_analise_completa_combinacoes(self):
        """Retorna análise completa das combinações"""
        analise = "🎯 SISTEMA DE COMBINAÇÕES DINÂMICAS\n"
        analise += "=" * 60 + "\n"
        
        # Resumo
        total_combinacoes = len(self.historico_combinacoes)
        combos_quentes = len(self.combinacoes_quentes)
        combos_frias = len(self.combinacoes_frias)
        
        analise += f"📊 RESUMO: {total_combinacoes} combinações | {combos_quentes} quentes | {combos_frias} frias\n\n"
        
        # 🎯 FOCO DINÂMICO
        analise += "🔥 COMBINAÇÕES EM ALTA (FOCO):\n"
        if self.combinacoes_em_alta:
            for combo, dados in self.combinacoes_em_alta[:3]:  # Top 3
                analise += f"  🎯 {combo[0]}+{combo[1]}: {dados['eficiencia']:.1f}% "
                analise += f"(Score: {dados['score']:.1f}, Tendência: {dados['tendencia']}, "
                analise += f"Seq: {dados['sequencia']} acertos)\n"
        else:
            analise += "  📭 Nenhuma combinação em alta\n"
        
        # 🎯 COMBINAÇÕES QUENTES
        analise += "\n🔥 COMBINAÇÕES QUENTES:\n"
        if self.combinacoes_quentes:
            for combo in self.combinacoes_quentes[:5]:
                dados = self.historico_combinacoes.get(combo, {})
                eficiencia = dados.get('eficiencia', 0)
                sequencia = dados.get('sequencia_acertos', 0)
                total = dados.get('total', 0)
                
                em_alta = "🎯" if combo in [c for c, _ in self.combinacoes_em_alta] else ""
                
                analise += f"  {em_alta} {combo[0]}+{combo[1]}: {eficiencia:.1f}% "
                analise += f"({dados.get('acertos', 0)}/{total}) "
                analise += f"| Seq: {sequencia} acertos\n"
        else:
            analise += "  📭 Nenhuma combinação quente\n"
        
        # 🎯 COMBINAÇÕES FRIAS
        analise += "\n❌ COMBINAÇÕES FRIAS (EVITAR):\n"
        if self.combinacoes_frias:
            for combo in self.combinacoes_frias:
                dados = self.historico_combinacoes.get(combo, {})
                eficiencia = dados.get('eficiencia', 0)
                total = dados.get('total', 0)
                
                em_baixa = "🚫" if combo in [c for c, _ in self.combinacoes_em_baixa] else ""
                
                analise += f"  {em_baixa} {combo[0]}+{combo[1]}: {eficiencia:.1f}% "
                analise += f"({dados.get('acertos', 0)}/{total}) "
                analise += f"| Seq erros: {dados.get('sequencia_erros', 0)}\n"
        else:
            analise += "  ✅ Nenhuma combinação fria\n"
        
        # 🎯 HISTÓRICO DE ACERTOS RECENTES
        analise += "\n📈 ÚLTIMAS COMBINAÇÕES QUE ACERTARAM:\n"
        if self.ultima_combinacao_acerto:
            for combo in self.ultima_combinacao_acerto[-3:]:
                analise += f"  ✅ {combo[0]}+{combo[1]}\n"
        else:
            analise += "  📭 Nenhuma combinação acertou recentemente\n"
        
        # 🎯 TODAS AS COMBINAÇÕES COM DESEMPENHO
        analise += "\n📋 TODAS AS COMBINAÇÕES:\n"
        for combo, dados in self.historico_combinacoes.items():
            if dados['total'] > 0:
                status = "🔥" if combo in self.combinacoes_quentes else "❄️" if combo in self.combinacoes_frias else "➖"
                em_alta = "🎯" if combo in [c for c, _ in self.combinacoes_em_alta] else ""
                em_baixa = "🚫" if combo in [c for c, _ in self.combinacoes_em_baixa] else ""
                
                analise += f"  {status}{em_alta}{em_baixa} {combo[0]}+{combo[1]}: "
                analise += f"{dados['eficiencia']:.1f}% ({dados['acertos']}/{dados['total']}) "
                analise += f"| Seq: +{dados.get('sequencia_acertos', 0)}/-{dados.get('sequencia_erros', 0)}\n"
        
        return analise

    def get_analise_previsao_atual(self):
        """Retorna análise da previsão atual"""
        if not self.previsao_ativa:
            return "📭 Nenhuma previsão ativa no momento"
        
        previsao = self.previsao_ativa
        analise = "🎯 PREVISÃO ATIVA\n"
        analise += "=" * 60 + "\n"
        
        analise += f"📊 Estratégia: {previsao['nome']}\n"
        analise += f"🎯 Confiança: {previsao.get('confianca', 'Média')}\n"
        analise += f"📍 Zonas: {previsao.get('zonas_envolvidas', ['N/A'])}\n"
        analise += f"🔢 Quantidade: {len(previsao['numeros_apostar'])} números\n"
        analise += f"🎲 Números: {sorted(previsao['numeros_apostar'])}\n"
        analise += f"📈 Gatilho: {previsao['gatilho']}\n"
        analise += f"🧠 Seleção Inteligente: {'✅ Sim' if previsao.get('selecao_inteligente', False) else '❌ Não'}\n"
        
        if previsao.get('tipo') == 'dupla' and len(previsao.get('zonas_envolvidas', [])) == 2:
            zonas = previsao['zonas_envolvidas']
            combo = tuple(sorted(zonas))
            
            if combo in self.historico_combinacoes:
                dados = self.historico_combinacoes[combo]
                analise += f"\n📊 DESEMPENHO DA COMBINAÇÃO:\n"
                analise += f"  📈 Eficiência: {dados['eficiencia']:.1f}%\n"
                analise += f"  🎯 Acertos/Total: {dados['acertos']}/{dados['total']}\n"
                analise += f"  🔄 Sequência atual: {dados.get('sequencia_acertos', 0)} acertos\n"
                
                # Verificar status
                if combo in self.combinacoes_quentes:
                    analise += "  🔥 STATUS: COMBINAÇÃO QUENTE\n"
                elif combo in self.combinacoes_frias:
                    analise += "  ❌ STATUS: COMBINAÇÃO FRIA\n"
                else:
                    analise += "  ⚪ STATUS: NEUTRA\n"
                
                # Verificar foco dinâmico
                combos_em_alta_lista = [c for c, _ in self.combinacoes_em_alta]
                combos_em_baixa_lista = [c for c, _ in self.combinacoes_em_baixa]
                
                if combo in combos_em_alta_lista:
                    analise += "  🎯 FOCO DINÂMICO: EM ALTA (Prioridade máxima)\n"
                elif combo in combos_em_baixa_lista:
                    analise += "  🚫 FOCO DINÂMICO: EM BAIXA (Evitar)\n"
        
        return analise

# =============================
# FUNÇÃO PRINCIPAL DO STREAMLIT
# =============================
def main():
    st.set_page_config(
        page_title="Sistema de Roleta Inteligente",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializar session state
    if 'historico' not in st.session_state:
        st.session_state.historico = []
    
    if 'telegram_token' not in st.session_state:
        st.session_state.telegram_token = ""
    
    if 'telegram_chat_id' not in st.session_state:
        st.session_state.telegram_chat_id = ""
    
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaRoletaCompleto()
        carregar_sessao()
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Auto-refresh a cada 10 segundos
    st_autorefresh(interval=10000, key="auto_refresh")
    
    # Título principal
    st.title("🎯 Sistema de Roleta Inteligente - IA Avançada")
    
    # Barra lateral
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Configurações do Telegram
        st.subheader("📱 Notificações Telegram")
        telegram_token = st.text_input("Token do Bot:", value=st.session_state.telegram_token, type="password")
        telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
        
        if telegram_token != st.session_state.telegram_token or telegram_chat_id != st.session_state.telegram_chat_id:
            st.session_state.telegram_token = telegram_token
            st.session_state.telegram_chat_id = telegram_chat_id
            salvar_sessao()
            st.success("✅ Configurações do Telegram salvas!")
        
        # Botão de teste do Telegram
        if st.button("📱 Testar Conexão Telegram"):
            if telegram_token and telegram_chat_id:
                try:
                    enviar_telegram("🔔 Teste de conexão - Sistema de Roleta Inteligente")
                    st.success("✅ Mensagem de teste enviada com sucesso!")
                except Exception as e:
                    st.error(f"❌ Erro ao enviar mensagem: {e}")
            else:
                st.warning("⚠️ Preencha o Token e Chat ID primeiro")
        
        st.divider()
        
        # Gerenciamento de dados
        st.subheader("💾 Gerenciamento de Dados")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Salvar Sessão"):
                if salvar_sessao():
                    st.success("✅ Sessão salva!")
                else:
                    st.error("❌ Erro ao salvar sessão")
        
        with col2:
            if st.button("🔄 Carregar Sessão"):
                if carregar_sessao():
                    st.success("✅ Sessão carregada!")
                else:
                    st.warning("⚠️ Nenhuma sessão salva encontrada")
        
        if st.button("🗑️ Limpar Sessão"):
            if st.checkbox("Confirmar limpeza completa"):
                limpar_sessao()
                st.success("✅ Sessão limpa! A página será recarregada.")
        
        st.divider()
        
        # Configurações do sistema
        st.subheader("🎯 Configurações do Sistema")
        
        estrategia_selecionada = st.selectbox(
            "Estratégia Ativa:",
            ["Zonas", "ML", "Midas"],
            index=["Zonas", "ML", "Midas"].index(st.session_state.sistema.estrategia_selecionada)
        )
        
        if estrategia_selecionada != st.session_state.sistema.estrategia_selecionada:
            st.session_state.sistema.set_estrategia(estrategia_selecionada)
            st.success(f"✅ Estratégia alterada para: {estrategia_selecionada}")
        
        # Botão para forçar rotação
        if st.button("🔄 Forçar Rotação Estratégica"):
            rotacionou = st.session_state.sistema.aplicar_rotacao_inteligente()
            if rotacionou:
                st.success("✅ Rotação forçada aplicada!")
            else:
                st.warning("⚠️ Não foi possível rotacionar no momento")
        
        st.divider()
        
        # Estatísticas rápidas
        st.subheader("📊 Estatísticas Rápidas")
        stats = st.session_state.sistema.get_estatisticas_gerais()
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.metric("✅ Acertos", stats['acertos'])
            st.metric("🔄 Sequência Acertos", stats['sequencia_acertos'])
            st.metric("🎯 Estratégia Atual", stats['estrategia_atual'])
        
        with col_stat2:
            st.metric("❌ Erros", stats['erros'])
            st.metric("💥 Sequência Erros", stats['sequencia_erros'])
            st.metric("📈 Acurácia", stats['acuracia'])
        
        st.divider()
        
        # Botão para treinar ML
        if st.button("🤖 Treinar Modelo ML"):
            with st.spinner("Treinando modelo de Machine Learning..."):
                success, message = st.session_state.sistema.treinar_modelo_ml()
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
        
        # Botão para resetar estatísticas
        if st.button("📊 Resetar Estatísticas"):
            if st.checkbox("Confirmar reset de estatísticas"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.success("✅ Estatísticas resetadas!")
    
    # Área principal
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🎯 Principal", 
        "📊 Análises", 
        "🤖 Machine Learning", 
        "📈 Tendências", 
        "🔥 Combinações",
        "⚙️ Sistema"
    ])
    
    with tab1:
        st.header("🎯 Sistema Principal")
        
        col_principal1, col_principal2 = st.columns([2, 1])
        
        with col_principal1:
            # Entrada manual de número
            st.subheader("🎲 Adicionar Número Manualmente")
            col_num1, col_num2 = st.columns(2)
            
            with col_num1:
                numero_manual = st.number_input("Número (0-36):", min_value=0, max_value=36, step=1)
            
            with col_num2:
                if st.button("➕ Adicionar Número", use_container_width=True):
                    st.session_state.sistema.processar_novo_numero(numero_manual)
                    st.session_state.historico.append(numero_manual)
                    salvar_sessao()
                    st.success(f"✅ Número {numero_manual} adicionado!")
            
            # Botão para buscar último resultado da API
            if st.button("🌐 Buscar Último Resultado da API"):
                try:
                    response = requests.get(API_URL, headers=HEADERS, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            ultimo_resultado = data[0]
                            numero_api = ultimo_resultado.get('number', None)
                            
                            if numero_api is not None:
                                st.session_state.sistema.processar_novo_numero(numero_api)
                                st.session_state.historico.append(numero_api)
                                salvar_sessao()
                                st.success(f"✅ Número {numero_api} da API adicionado!")
                            else:
                                st.warning("⚠️ Número não encontrado na resposta da API")
                        else:
                            st.warning("⚠️ Nenhum dado retornado pela API")
                    else:
                        st.error(f"❌ Erro na API: {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Erro ao buscar dados da API: {e}")
            
            # Exibir histórico recente
            st.subheader("📜 Histórico Recente")
            if st.session_state.historico:
                historico_recente = st.session_state.historico[-20:]
                historico_formatado = [f"🎲 {n}" for n in historico_recente]
                st.write(" ".join(historico_formatado))
                
                # Estatísticas do histórico
                if len(historico_recente) >= 5:
                    st.caption(f"📊 Últimos {len(historico_recente)} números")
            else:
                st.info("📭 Nenhum número no histórico")
        
        with col_principal2:
            # Previsão atual
            st.subheader("🔮 Previsão Ativa")
            if st.session_state.sistema.previsao_ativa:
                previsao = st.session_state.sistema.previsao_ativa
                
                # Card da previsão
                with st.container():
                    st.markdown(f"""
                    <div style="padding: 20px; border-radius: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                        <h3 style="margin: 0;">{previsao['nome']}</h3>
                        <p style="margin: 5px 0;">🎯 Confiança: {previsao.get('confianca', 'Média')}</p>
                        <p style="margin: 5px 0;">📍 Zonas: {', '.join(previsao.get('zonas_envolvidas', ['N/A']))}</p>
                        <p style="margin: 5px 0;">🔢 Números: {len(previsao['numeros_apostar'])}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Números para apostar
                st.subheader("🎲 Números para Apostar")
                numeros = sorted(previsao['numeros_apostar'])
                
                # Mostrar em grade
                cols = st.columns(6)
                for i, num in enumerate(numeros):
                    with cols[i % 6]:
                        st.markdown(f"""
                        <div style="text-align: center; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; background-color: #f0f8ff;">
                            <h3 style="margin: 0;">{num}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Botão para forçar nova previsão
                if st.button("🎯 Gerar Nova Previsão Inteligente"):
                    success = st.session_state.sistema.criar_previsao_inteligente()
                    if success:
                        st.success("✅ Nova previsão inteligente gerada!")
                        st.rerun()
                    else:
                        st.error("❌ Não foi possível gerar nova previsão")
            else:
                st.info("📭 Nenhuma previsão ativa no momento")
                
                # Botão para forçar criação de previsão
                if st.button("🎯 Criar Previsão Agora"):
                    success = st.session_state.sistema.criar_previsao_inteligente()
                    if success:
                        st.success("✅ Previsão criada com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Não foi possível criar previsão")
    
    with tab2:
        st.header("📊 Análises Detalhadas")
        
        col_analise1, col_analise2 = st.columns(2)
        
        with col_analise1:
            # Análise das Zonas
            st.subheader("📍 Análise das Zonas")
            analise_zonas = st.session_state.sistema.estrategia_zonas.get_analise_atual()
            st.text_area("Análise Detalhada:", value=analise_zonas, height=400)
        
        with col_analise2:
            # Estatísticas de desempenho
            st.subheader("📈 Desempenho do Sistema")
            
            # Gráfico de desempenho
            if st.session_state.sistema.historico_desempenho:
                df_desempenho = pd.DataFrame(st.session_state.sistema.historico_desempenho[-20:])
                
                if not df_desempenho.empty:
                    # Adicionar coluna de resultado
                    df_desempenho['resultado'] = df_desempenho['acerto'].apply(lambda x: '✅' if x else '❌')
                    df_desempenho['numero'] = df_desempenho['numero'].astype(str)
                    
                    # Mostrar tabela
                    st.dataframe(
                        df_desempenho[['numero', 'resultado', 'estrategia', 'zona_acertada']].tail(10),
                        use_container_width=True
                    )
            
            # Estatísticas por estratégia
            st.subheader("🎯 Desempenho por Estratégia")
            estrategias_stats = st.session_state.sistema.estrategias_contador
            
            for estrategia, dados in estrategias_stats.items():
                if dados['total'] > 0:
                    acuracia = (dados['acertos'] / dados['total']) * 100
                    st.metric(
                        label=estrategia,
                        value=f"{dados['acertos']}/{dados['total']}",
                        delta=f"{acuracia:.1f}%"
                    )
    
    with tab3:
        st.header("🤖 Machine Learning")
        
        # Status do modelo ML
        st.subheader("🤖 Status do Modelo ML")
        
        ml_status = st.session_state.sistema.estrategia_ml.ml.resumo_meta()
        
        col_ml1, col_ml2, col_ml3 = st.columns(3)
        
        with col_ml1:
            st.metric("Treinado", "✅" if ml_status['is_trained'] else "❌")
        
        with col_ml2:
            st.metric("Treinamentos", ml_status['contador_treinamento'])
        
        with col_ml3:
            if 'last_accuracy' in ml_status['meta']:
                st.metric("Acurácia", f"{ml_status['meta']['last_accuracy']:.1%}")
            else:
                st.metric("Acurácia", "N/A")
        
        # Análise ML
        st.subheader("📊 Análise do Machine Learning")
        analise_ml = st.session_state.sistema.estrategia_ml.get_analise_ml()
        st.text_area("Análise ML:", value=analise_ml, height=300)
        
        # Estatísticas de padrões
        st.subheader("🎯 Estatísticas de Padrões")
        stats_padroes = st.session_state.sistema.estrategia_ml.get_estatisticas_padroes()
        st.text_area("Eficiência dos Padrões:", value=stats_padroes, height=200)
        
        # Botões de controle ML
        col_ml_btn1, col_ml_btn2 = st.columns(2)
        
        with col_ml_btn1:
            if st.button("🔄 Treinar ML Agora"):
                with st.spinner("Treinando modelo..."):
                    historico_numeros = []
                    for item in st.session_state.historico:
                        if isinstance(item, (int, float)):
                            historico_numeros.append(int(item))
                    
                    success, message = st.session_state.sistema.estrategia_ml.treinar_modelo_ml(historico_numeros)
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
        
        with col_ml_btn2:
            if st.button("🗑️ Limpar Padrões ML"):
                st.session_state.sistema.estrategia_ml.zerar_padroes()
                st.success("✅ Padrões ML zerados!")
    
    with tab4:
        st.header("📈 Sistema de Tendências")
        
        # Análise de tendências
        analise_tendencias = st.session_state.sistema.get_analise_tendencias_completa()
        st.text_area("📊 Análise de Tendências:", value=analise_tendencias, height=400)
        
        # Estado atual das tendências
        st.subheader("🎯 Estado Atual da Tendência")
        
        if st.session_state.sistema.sistema_tendencias.historico_tendencias:
            ultima_tendencia = st.session_state.sistema.sistema_tendencias.historico_tendencias[-1]
            
            # Card de status
            cor_status = {
                'aguardando': 'gray',
                'formando': 'orange',
                'ativa': 'green',
                'enfraquecendo': 'yellow',
                'morta': 'red'
            }.get(ultima_tendencia['estado'], 'gray')
            
            st.markdown(f"""
            <div style="padding: 20px; border-radius: 10px; background-color: {cor_status}20; border-left: 5px solid {cor_status};">
                <h3 style="margin: 0; color: {cor_status};">📊 {ultima_tendencia['estado'].upper()}</h3>
                <p style="margin: 5px 0;"><strong>Zona Dominante:</strong> {ultima_tendencia['zona_dominante'] or 'Nenhuma'}</p>
                <p style="margin: 5px 0;"><strong>Confiança:</strong> {ultima_tendencia['confianca']:.0%}</p>
                <p style="margin: 5px 0;"><strong>Ação Recomendada:</strong> {ultima_tendencia['acao'].upper()}</p>
                <p style="margin: 5px 0;"><strong>Mensagem:</strong> {ultima_tendencia['mensagem']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Botão para forçar análise
        if st.button("🔍 Analisar Tendência Agora"):
            try:
                # Obter zonas rankeadas atuais
                zonas_rankeadas = st.session_state.sistema.estrategia_zonas.get_zonas_rankeadas()
                if zonas_rankeadas:
                    analise = st.session_state.sistema.sistema_tendencias.analisar_tendencia(zonas_rankeadas)
                    st.success(f"✅ Análise realizada: {analise['mensagem']}")
                else:
                    st.warning("⚠️ Aguardando dados suficientes para análise")
            except Exception as e:
                st.error(f"❌ Erro na análise: {e}")
    
    with tab5:
        st.header("🔥 Sistema de Combinações")
        
        # Análise completa das combinações
        analise_combinacoes = st.session_state.sistema.get_analise_completa_combinacoes()
        st.text_area("📊 Análise de Combinações:", value=analise_combinacoes, height=400)
        
        # Performance dinâmica
        st.subheader("🎯 Performance Dinâmica")
        performance_analise = st.session_state.sistema.get_analise_performance_completa()
        st.text_area("📈 Análise de Performance:", value=performance_analise, height=300)
        
        # Controles das combinações
        col_combo1, col_combo2 = st.columns(2)
        
        with col_combo1:
            if st.button("🔄 Atualizar Análise de Combinações"):
                st.session_state.sistema.analisar_performance_dinamica()
                st.success("✅ Análise atualizada!")
                st.rerun()
        
        with col_combo2:
            if st.button("🎯 Forçar Melhor Combinação"):
                melhor_combo = st.session_state.sistema.get_melhor_combinacao_atual()
                if melhor_combo:
                    success = st.session_state.sistema.criar_previsao_com_combinacao(melhor_combo)
                    if success:
                        st.success(f"✅ Previsão criada com combinação {melhor_combo}!")
                        st.rerun()
                    else:
                        st.error("❌ Não foi possível criar previsão")
                else:
                    st.warning("⚠️ Nenhuma combinação recomendada no momento")
    
    with tab6:
        st.header("⚙️ Sistema e Configurações")
        
        # Informações do sistema
        st.subheader("ℹ️ Informações do Sistema")
        
        col_sys1, col_sys2 = st.columns(2)
        
        with col_sys1:
            st.info(f"**Versão:** Sistema de Roleta Inteligente v3.0")
            st.info(f"**Estratégia Ativa:** {st.session_state.sistema.estrategia_selecionada}")
            st.info(f"**Sorteios Processados:** {st.session_state.sistema.contador_sorteios_global}")
        
        with col_sys2:
            st.info(f"**Modelo ML:** {'✅ Treinado' if st.session_state.sistema.estrategia_ml.ml.is_trained else '❌ Não treinado'}")
            st.info(f"**Tendências:** {st.session_state.sistema.sistema_tendencias.estado_tendencia}")
            st.info(f"**Combinações Ativas:** {len(st.session_state.sistema.historico_combinacoes)}")
        
        # Gerenciamento avançado
        st.subheader("⚙️ Gerenciamento Avançado")
        
        col_adv1, col_adv2 = st.columns(2)
        
        with col_adv1:
            if st.button("🔄 Reset Recente (10 últimos)"):
                st.session_state.sistema.reset_recente_estatisticas()
                st.success("✅ Reset recente aplicado!")
        
        with col_adv2:
            if st.button("🗑️ Zerar Tudo (Completo)"):
                if st.checkbox("⚠️ Confirmar zeragem completa de TODOS os dados"):
                    st.session_state.sistema.zerar_estatisticas_desempenho()
                    st.success("✅ Todos os dados foram zerados!")
        
        # Exportação de dados
        st.subheader("💾 Exportação de Dados")
        
        if st.button("📥 Exportar Dados da Sessão"):
            session_data = {
                'historico': st.session_state.historico,
                'estatisticas': st.session_state.sistema.get_estatisticas_gerais(),
                'desempenho': st.session_state.sistema.historico_desempenho,
                'combinacoes': st.session_state.sistema.historico_combinacoes,
                'tendencias': list(st.session_state.sistema.sistema_tendencias.historico_tendencias)
            }
            
            st.download_button(
                label="⬇️ Baixar JSON",
                data=json.dumps(session_data, indent=2),
                file_name="sistema_roleta_dados.json",
                mime="application/json"
            )
        
        # Informações de debug
        st.subheader("🐛 Informações de Debug")
        
        if st.checkbox("Mostrar dados de debug"):
            st.json({
                "historico_tamanho": len(st.session_state.historico),
                "desempenho_tamanho": len(st.session_state.sistema.historico_desempenho),
                "combinacoes_tamanho": len(st.session_state.sistema.historico_combinacoes),
                "ultima_previsao": st.session_state.sistema.previsao_ativa,
                "session_keys": list(st.session_state.keys())
            })
    
    # Rodapé
    st.divider()
    st.caption("🎯 Sistema de Roleta Inteligente - IA Avançada • Desenvolvido com Streamlit • v3.0")
    st.caption("⚠️ Uso responsável apenas. O sistema é para estudo e análise estatística.")

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Erro crítico no sistema: {e}")
        logging.error(f"Erro crítico: {e}", exc_info=True)
        
        # Tentar salvar sessão em caso de erro
        try:
            salvar_sessao()
            st.warning("⚠️ Sessão salva devido a erro. Recarregue a página.")
        except:
            st.error("⚠️ Não foi possível salvar a sessão.")
