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
        
        # 4. VERIFICAR SE TENDência ESTÁ MORTA
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

    #def verificar_treinamento_automatico(self, historico_completo):
       # try:
         #   n = len(historico_completo)
         #   if n >= self.min_training_samples:
              #  if n % self.retrain_every_n == 0:
                    # return self.treinar_modelo(historico
    def verificar_treinamento_automatico(self, historico_completo):
        try:
            n = len(historico_completo)
            if n >= self.min_training_samples:
                if n % self.retrain_every_n == 0:
                    return self.treinar_modelo(historico_completo, force_retrain=True, balance=True)
            return False, None
        except Exception as e:
            logging.error(f"[verificar_treinamento_automatico] Erro: {e}")
            return False, None

    def get_status(self):
        return {
            'is_trained': self.is_trained,
            'model_count': len(self.models),
            'last_accuracy': self.meta.get('last_accuracy', 0.0),
            'trained_on': self.meta.get('trained_on', 0),
            'retrain_counter': self.contador_treinamento
        }

# =============================
# ESTRATÉGIAS DE APOSTA
# =============================
class EstrategiaZonas:
    def __init__(self, roleta_obj):
        self.roleta = roleta_obj
        self.historico = deque(maxlen=70)
        self.stats_zonas = {
            'Vermelha': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
            'Azul': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
            'Amarela': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
        }
        
    def analisar_zonas(self, historico_global):
        if not historico_global:
            return []
            
        ultimo_numero = historico_global[-1]
        zona_ultima = self.identificar_zona_numero(ultimo_numero)
        
        self.historico.append(zona_ultima)
        
        zonas = ['Vermelha', 'Azul', 'Amarela']
        performances = []
        
        for zona in zonas:
            stats = self.stats_zonas[zona]
            
            acertos = stats['acertos']
            tentativas = stats['tentativas']
            
            performance = (acertos / tentativas * 100) if tentativas > 0 else 33.3
            
            if tentativas > 0:
                stats['performance_media'] = (stats['performance_media'] * 0.8) + (performance * 0.2)
            
            performances.append((zona, stats['performance_media']))
        
        performances.sort(key=lambda x: x[1], reverse=True)
        
        if len(historico_global) >= 3:
            ultimas_3 = historico_global[-3:]
            ultimas_zonas = [self.identificar_zona_numero(n) for n in ultimas_3]
            
            zona_repeticoes = Counter(ultimas_zonas)
            
            for zona, count in zona_repeticoes.items():
                if count >= 2:
                    performances = [(z, p + 15) if z == zona else (z, p) for z, p in performances]
        
        zona_forte = performances[0][0]
        performance_forte = performances[0][1]
        
        return performances

    def identificar_zona_numero(self, numero):
        if numero == 0:
            return "Azul"
        
        vizinhos = self.roleta.get_vizinhos_zona(numero, 4)
        
        vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        total_vermelhos = sum(1 for n in vizinhos if n in vermelhos)
        total_azuis = sum(1 for n in vizinhos if n == 0)
        total_amarelos = len(vizinhos) - total_vermelhos - total_azuis
        
        if total_azuis >= 2:
            return "Azul"
        elif total_vermelhos >= 5:
            return "Vermelha"
        elif total_amarelos >= 5:
            return "Amarela"
        elif numero in vermelhos:
            return "Vermelha"
        else:
            return "Amarela"

    def atualizar_stats(self, zona, acerto):
        stats = self.stats_zonas[zona]
        stats['tentativas'] += 1
        
        if acerto:
            stats['acertos'] += 1
            stats['sequencia_atual'] += 1
            stats['sequencia_maxima'] = max(stats['sequencia_maxima'], stats['sequencia_atual'])
        else:
            stats['sequencia_atual'] = 0

    def gerar_previsao(self, historico_global, ranking_zonas):
        if not historico_global or not ranking_zonas:
            return None
            
        zona_top1, score_top1 = ranking_zonas[0]
        zona_top2, score_top2 = ranking_zonas[1] if len(ranking_zonas) > 1 else (None, 0)
        
        threshold_combinacao = 45
        
        if len(ranking_zonas) > 1 and score_top1 >= threshold_combinacao and score_top2 >= threshold_combinacao * 0.8:
            zonas_envolvidas = [zona_top1, zona_top2]
            zona_desc = f"{zona_top1}+{zona_top2}"
            
            numeros_apostar = set()
            for zona in zonas_envolvidas:
                if zona == 'Vermelha':
                    numeros = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
                elif zona == 'Azul':
                    numeros = {0}
                else:  # Amarela
                    numeros = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
                numeros_apostar.update(numeros)
            
            confianca = self.calcular_confianca_combinacao(zona_top1, zona_top2, score_top1, score_top2)
            confianca_texto = "Alta" if confianca >= 65 else "Média" if confianca >= 50 else "Baixa"
            
            previsao = {
                'nome': f"🔥 Zonas {zona_desc}",
                'tipo': 'zonas_combinacao',
                'zonas_envolvidas': zonas_envolvidas,
                'zona': zona_desc,
                'numeros_apostar': sorted(numeros_apostar),
                'confianca': confianca_texto,
                'confianca_valor': confianca,
                'score_zona1': score_top1,
                'score_zona2': score_top2,
                'qtd_numeros': len(numeros_apostar),
                'estrategia': 'Zonas'
            }
        else:
            zona = zona_top1
            zona_desc = zona
            
            if zona == 'Vermelha':
                numeros_apostar = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
            elif zona == 'Azul':
                numeros_apostar = {0}
            else:  # Amarela
                numeros_apostar = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
            
            confianca = self.calcular_confianca_zona(zona, score_top1)
            confianca_texto = "Alta" if confianca >= 70 else "Média" if confianca >= 55 else "Baixa"
            
            previsao = {
                'nome': f"🎯 Zona {zona}",
                'tipo': 'zona_simples',
                'zona': zona,
                'numeros_apostar': sorted(numeros_apostar),
                'confianca': confianca_texto,
                'confianca_valor': confianca,
                'score_zona': score_top1,
                'qtd_numeros': len(numeros_apostar),
                'estrategia': 'Zonas'
            }
        
        return previsao

    def calcular_confianca_zona(self, zona, score):
        stats = self.stats_zonas[zona]
        
        base_confianca = min(score / 100 * 70, 70)
        
        if stats['tentativas'] > 0:
            taxa_acerto = stats['acertos'] / stats['tentativas'] * 100
            base_confianca += min(taxa_acerto * 0.3, 20)
        
        sequencia_atual = stats['sequencia_atual']
        if sequencia_atual >= 2:
            base_confianca += min(sequencia_atual * 5, 10)
        
        return min(base_confianca, 95)

    def calcular_confianca_combinacao(self, zona1, zona2, score1, score2):
        conf1 = self.calcular_confianca_zona(zona1, score1)
        conf2 = self.calcular_confianca_zona(zona2, score2)
        
        conf_media = (conf1 + conf2) / 2
        
        combo_bonus = 0
        if (zona1 == 'Vermelha' and zona2 == 'Azul') or (zona1 == 'Azul' and zona2 == 'Vermelha'):
            combo_bonus = 10
        elif (zona1 == 'Amarela' and zona2 == 'Vermelha') or (zona1 == 'Vermelha' and zona2 == 'Amarela'):
            combo_bonus = 8
        elif (zona1 == 'Azul' and zona2 == 'Amarela') or (zona1 == 'Amarela' and zona2 == 'Azul'):
            combo_bonus = 5
        
        return min(conf_media + combo_bonus, 90)

    def get_status(self):
        status_str = "📊 Status Zonas:\n"
        for zona, stats in self.stats_zonas.items():
            acertos = stats['acertos']
            tentativas = stats['tentativas']
            taxa = (acertos / tentativas * 100) if tentativas > 0 else 0
            status_str += f"  {zona}: {acertos}/{tentativas} ({taxa:.1f}%) | Seq: {stats['sequencia_atual']}\n"
        return status_str

class EstrategiaMidas:
    def __init__(self, roleta_obj):
        self.roleta = roleta_obj
        self.historico = deque(maxlen=15)
        self.numeros_candidatos = []
        
    def analisar(self, historico_global):
        if len(historico_global) < 3:
            return []
            
        ultimo = historico_global[-1]
        penultimo = historico_global[-2] if len(historico_global) >= 2 else ultimo
        antipenultimo = historico_global[-3] if len(historico_global) >= 3 else penultimo
        
        vizinhos_ultimo = self.roleta.get_vizinhos_zona(ultimo, 3)
        vizinhos_penultimo = self.roleta.get_vizinhos_zona(penultimo, 2)
        vizinhos_antepenultimo = self.roleta.get_vizinhos_zona(antipenultimo, 2)
        
        todos_vizinhos = set(vizinhos_ultimo + vizinhos_penultimo + vizinhos_antepenultimo)
        
        proximo_candidato = []
        for num in todos_vizinhos:
            score = 0
            
            if num in vizinhos_ultimo:
                score += 40
            if num in vizinhos_penultimo:
                score += 30
            if num in vizinhos_antepenultimo:
                score += 20
            
            distancia_ultimo = abs(self.roleta.get_posicao_race(num) - self.roleta.get_posicao_race(ultimo))
            if distancia_ultimo <= 5:
                score += 15
            elif distancia_ultimo <= 10:
                score += 5
            
            if num % 2 == 0:
                score += 5
            else:
                score += 3
            
            frequencia_recente = sum(1 for n in historico_global[-10:] if n == num)
            if frequencia_recente == 0:
                score += 25
            elif frequencia_recente == 1:
                score += 10
            else:
                score -= frequencia_recente * 5
            
            proximo_candidato.append((num, score))
        
        proximo_candidato.sort(key=lambda x: x[1], reverse=True)
        
        self.numeros_candidatos = [num for num, score in proximo_candidato[:12]]
        
        return self.numeros_candidatos

    def gerar_previsao(self, historico_global):
        candidatos = self.analisar(historico_global)
        
        if not candidatos:
            return None
        
        previsao = {
            'nome': "💰 Midas Touch",
            'tipo': 'midas',
            'numeros_apostar': candidatos[:15],
            'confianca': "Média",
            'confianca_valor': 55,
            'qtd_numeros': len(candidatos[:15]),
            'estrategia': 'Midas'
        }
        
        self.historico.append({
            'candidatos': candidatos,
            'timestamp': len(historico_global)
        })
        
        return previsao

class EstrategiaML:
    def __init__(self, roleta_obj):
        self.roleta = roleta_obj
        self.ml_model = MLRoletaOtimizada(roleta_obj, min_training_samples=150)
        self.historico = deque(maxlen=30)
        self.contador_sorteios = 0
        self.ultima_previsao = None
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
        
        # Tentar carregar modelo salvo
        self.ml_model.carregar_modelo()
        
    def analisar(self, historico_global):
        if len(historico_global) < self.ml_model.min_training_samples:
            return None
            
        resultado, msg = self.ml_model.prever_proximo_numero(historico_global, top_k=25)
        
        if resultado is None:
            return None
        
        self.contador_sorteios += 1
        
        resultado_formatado = [
            {'numero': num, 'probabilidade': prob} 
            for num, prob in resultado[:15]
        ]
        
        # Detectar padrões de sequência
        padroes = self.detectar_padroes_sequencia(historico_global)
        if padroes:
            for padrao in padroes[:2]:
                self.sequencias_padroes['padroes_detectados'].append(padrao)
                self.metricas_padroes['padroes_detectados_total'] += 1
        
        return {
            'previsao': resultado_formatado,
            'mensagem': msg,
            'padroes_detectados': padroes[:2] if padroes else [],
            'contador_sorteios': self.contador_sorteios
        }

    def detectar_padroes_sequencia(self, historico):
        if len(historico) < 8:
            return []
            
        padroes = []
        ultimos_10 = list(historico)[-10:]
        
        # Padrão: Repetição de paridade
        paridades = [n % 2 for n in ultimos_10]
        if len(set(paridades[-4:])) == 1:
            padroes.append({
                'tipo': 'paridade_constante',
                'valor': 'Par' if paridades[-1] == 0 else 'Ímpar',
                'comprimento': 4,
                'probabilidade': 0.65
            })
        
        # Padrão: Alternância
        alternancias = all(paridades[i] != paridades[i+1] for i in range(len(paridades)-1))
        if alternancias and len(paridades) >= 4:
            padroes.append({
                'tipo': 'alternancia_paridade',
                'valor': 'Alternando',
                'comprimento': len(paridades),
                'probabilidade': 0.60
            })
        
        # Padrão: Faixa de números
        numeros_sem_zero = [n for n in ultimos_10 if n != 0]
        if numeros_sem_zero:
            min_num = min(numeros_sem_zero)
            max_num = max(numeros_sem_zero)
            amplitude = max_num - min_num
            
            if amplitude <= 12 and len(numeros_sem_zero) >= 5:
                padroes.append({
                    'tipo': 'faixa_concentrada',
                    'valor': f"{min_num}-{max_num}",
                    'comprimento': len(numeros_sem_zero),
                    'probabilidade': 0.55
                })
        
        # Padrão: Vizinhos físicos
        posicoes = [self.roleta.get_posicao_race(n) for n in ultimos_10 if n != -1]
        if len(posicoes) >= 4:
            distancias = [abs(posicoes[i] - posicoes[i-1]) for i in range(1, len(posicoes))]
            dist_media = np.mean(distancias) if distancias else 0
            
            if dist_media <= 6:
                padroes.append({
                    'tipo': 'proximidade_fisica',
                    'valor': f"Distância média {dist_media:.1f}",
                    'comprimento': len(posicoes),
                    'probabilidade': 0.70
                })
        
        return padroes

    def gerar_previsao(self, historico_global):
        analise = self.analisar(historico_global)
        
        if analise is None or not analise['previsao']:
            return None
        
        previsao_ml = analise['previsao']
        padroes = analise.get('padroes_detectados', [])
        
        numeros_ml = [item['numero'] for item in previsao_ml[:15]]
        
        # Ajustar previsão baseado em padrões detectados
        if padroes:
            numeros_ajustados = self.aplicar_padroes_numeros(numeros_ml, padroes, historico_global)
            if numeros_ajustados:
                numeros_ml = numeros_ajustados[:15]
        
        zona_ml = self.determinar_zona_ml(numeros_ml)
        confianca = self.calcular_confianca_ml(analise, padroes)
        confianca_texto = "Alta" if confianca >= 70 else "Média" if confianca >= 55 else "Baixa"
        
        previsao = {
            'nome': "🤖 Machine Learning",
            'tipo': 'ml',
            'numeros_apostar': numeros_ml,
            'confianca': confianca_texto,
            'confianca_valor': confianca,
            'zona_ml': zona_ml,
            'padroes_detectados': padroes[:2],
            'qtd_numeros': len(numeros_ml),
            'estrategia': 'ML',
            'detalhes_ml': analise
        }
        
        self.ultima_previsao = previsao
        self.historico.append({
            'previsao': previsao,
            'timestamp': len(historico_global),
            'padroes': padroes
        })
        
        return previsao

    def aplicar_padroes_numeros(self, numeros_base, padroes, historico):
        numeros_ajustados = set(numeros_base)
        
        for padrao in padroes[:2]:
            if padrao['tipo'] == 'paridade_constante':
                paridade_alvo = 0 if padrao['valor'] == 'Par' else 1
                numeros_filtrados = [n for n in range(37) if n % 2 == paridade_alvo]
                numeros_ajustados.update(numeros_filtrados[:8])
            
            elif padrao['tipo'] == 'faixa_concentrada':
                try:
                    min_val, max_val = map(int, padrao['valor'].split('-'))
                    numeros_faixa = [n for n in range(37) if min_val <= n <= max_val]
                    numeros_ajustados.update(numeros_faixa)
                except:
                    pass
            
            elif padrao['tipo'] == 'proximidade_fisica':
                if historico:
                    ultimo_num = historico[-1]
                    vizinhos = self.roleta.get_vizinhos_fisicos(ultimo_num, raio=5)
                    numeros_ajustados.update(vizinhos[:10])
        
        return list(numeros_ajustados)[:20]

    def determinar_zona_ml(self, numeros):
        estrategia_zonas = EstrategiaZonas(self.roleta)
        zonas_count = Counter()
        
        for num in numeros:
            zona = estrategia_zonas.identificar_zona_numero(num)
            zonas_count[zona] += 1
        
        if zonas_count:
            zona_principal = zonas_count.most_common(1)[0][0]
            
            # Verificar se há combinação forte
            top2 = zonas_count.most_common(2)
            if len(top2) > 1:
                zona1, count1 = top2[0]
                zona2, count2 = top2[1]
                
                if count1 >= 5 and count2 >= 4:
                    return f"{zona1}+{zona2}"
            
            return zona_principal
        
        return "Mista"

    def calcular_confianca_ml(self, analise, padroes):
        confianca_base = 50
        
        # Baseado na probabilidade média das previsões
        if analise['previsao']:
            prob_media = np.mean([item['probabilidade'] for item in analise['previsao'][:10]])
            confianca_base += min(prob_media * 40, 30)
        
        # Bônus por padrões detectados
        if padroes:
            confianca_base += len(padroes) * 5
            for padrao in padroes[:2]:
                confianca_base += padrao.get('probabilidade', 0) * 10
        
        # Bônus por histórico de treinamento
        status_ml = self.ml_model.get_status()
        if status_ml['is_trained']:
            confianca_base += min(status_ml['last_accuracy'] * 50, 15)
        
        return min(confianca_base, 85)

    def registrar_resultado(self, historico_global, numero_real, previsao_usada):
        if previsao_usada and 'detalhes_ml' in previsao_usada:
            previsao_top = [(item['numero'], item['probabilidade']) 
                           for item in previsao_usada['detalhes_ml']['previsao']]
            
            self.ml_model.registrar_resultado(historico_global, previsao_top, numero_real)
            
            # Atualizar métricas de padrões
            if previsao_usada.get('padroes_detectados'):
                acerto = numero_real in previsao_usada['numeros_apostar']
                
                for padrao in previsao_usada['padroes_detectados']:
                    tipo = padrao['tipo']
                    
                    if acerto:
                        self.metricas_padroes['padroes_acertados'] += 1
                    else:
                        self.metricas_padroes['padroes_errados'] += 1
                    
                    if tipo not in self.metricas_padroes['eficiencia_por_tipo']:
                        self.metricas_padroes['eficiencia_por_tipo'][tipo] = {'acertos': 0, 'total': 0}
                    
                    self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1
                    if acerto:
                        self.metricas_padroes['eficiencia_por_tipo'][tipo]['acertos'] += 1
        
        # Verificar treinamento automático
        self.ml_model.verificar_treinamento_automatico(historico_global)

    def get_status(self):
        status_ml = self.ml_model.get_status()
        
        status_str = "🤖 Status ML:\n"
        status_str += f"  Modelo treinado: {'✅' if status_ml['is_trained'] else '❌'}\n"
        status_str += f"  Modelos ativos: {status_ml['model_count']}\n"
        status_str += f"  Última acurácia: {status_ml['last_accuracy']:.1%}\n"
        status_str += f"  Treinamentos: {status_ml['retrain_counter']}\n"
        status_str += f"  Padrões detectados: {self.metricas_padroes['padroes_detectados_total']}\n"
        
        if self.metricas_padroes['padroes_detectados_total'] > 0:
            taxa_acerto = self.metricas_padroes['padroes_acertados'] / self.metricas_padroes['padroes_detectados_total'] * 100
            status_str += f"  Eficiência padrões: {taxa_acerto:.1f}%\n"
        
        return status_str

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaApostaRoleta:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.seletor_inteligente = SistemaSelecaoInteligente()
        
        self.estrategia_zonas = EstrategiaZonas(self.roleta)
        self.estrategia_midas = EstrategiaMidas(self.roleta)
        self.estrategia_ml = EstrategiaML(self.roleta)
        
        self.sistema_tendencias = SistemaTendencias()
        
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ''
        
        # NOVO: Sistema de 3 acertos consecutivos
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        self.estrategia_selecionada = 'Zonas'
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        # 🎯 NOVO: Sistema de foco dinâmico
        self.combinacoes_em_alta = []
        self.combinacoes_em_baixa = []
        self.historico_performance = {}
        self.ultima_analise_performance = None
        
        # Inicializar contadores de estratégias
        for estrategia in ['Zonas', 'Midas', 'ML']:
            self.estrategias_contador[estrategia] = {'acertos': 0, 'tentativas': 0}

    def analisar_tendencia_atual(self, historico):
        if not historico:
            return None
            
        ranking_zonas = self.estrategia_zonas.analisar_zonas(historico)
        
        analise_tendencia = self.sistema_tendencias.analisar_tendencia(
            ranking_zonas,
            acerto_ultima=(self.historico_desempenho[-1] if self.historico_desempenho else False),
            zona_acertada=self.obter_ultima_zona_acertada()
        )
        
        return analise_tendencia

    def obter_ultima_zona_acertada(self):
        if not self.historico_desempenho:
            return None
        
        # Obter a última zona que acertou
        for i in range(len(self.historico_desempenho)-1, -1, -1):
            if self.historico_desempenho[i]:
                # Precisa ter informação da estratégia usada
                return self.obter_zona_da_estrategia(i)
        return None

    def obter_zona_da_estrategia(self, index):
        # Implementação simplificada - na prática, você precisaria armazenar mais informações
        return None

    def selecionar_estrategia(self, historico, ultimo_numero=None):
        if len(historico) < 10:
            return 'Zonas'
        
        # 🎯 NOVA LÓGICA: Sistema de tendências
        analise_tendencia = self.analisar_tendencia_atual(historico)
        
        if analise_tendencia and analise_tendencia['acao'] == 'operar':
            zona_alvo = analise_tendencia['zona_dominante']
            
            if zona_alvo:
                if '+' in zona_alvo:
                    zonas = zona_alvo.split('+')
                    if len(zonas) == 2:
                        self.estrategia_selecionada = 'Zonas'
                        return 'Zonas'
                else:
                    if zona_alvo in ['Vermelha', 'Azul', 'Amarela']:
                        self.estrategia_selecionada = 'Zonas'
                        return 'Zonas'
        
        # Lógica original de rotação baseada em desempenho
        desempenho_zonas = self.calcular_desempenho_estrategia('Zonas')
        desempenho_ml = self.calcular_desempenho_estrategia('ML')
        
        # Priorizar ML se estiver bem treinado
        status_ml = self.estrategia_ml.ml_model.get_status()
        if status_ml['is_trained'] and desempenho_ml >= 0.5:
            ml_superior = desempenho_ml > desempenho_zonas * 1.2
            if ml_superior:
                self.estrategia_selecionada = 'ML'
                return 'ML'
        
        # Sistema de rotação por erros consecutivos
        if self.sequencia_erros >= 3:
            estrategia_atual = self.estrategia_selecionada
            
            if estrategia_atual == 'Zonas':
                self.estrategia_selecionada = 'ML' if status_ml['is_trained'] else 'Midas'
            elif estrategia_atual == 'ML':
                self.estrategia_selecionada = 'Zonas'
            else:
                self.estrategia_selecionada = 'Zonas'
            
            enviar_rotacao_automatica(estrategia_atual, self.estrategia_selecionada)
            self.sequencia_erros = 0
            self.ultima_estrategia_erro = ''
        
        # 🎯 NOVA LÓGICA: Sistema de 3 acertos consecutivos em combinações
        if self.sequencia_acertos >= 3 and self.ultima_combinacao_acerto:
            combinacao_atual = self.ultima_combinacao_acerto
            
            if combinacao_atual:
                # Alternar para outra combinação
                outras_combinacoes = self.obter_outras_combinacoes_quentes(combinacao_atual)
                if outras_combinacoes:
                    nova_combinacao = outras_combinacoes[0]
                    self.ultima_combinacao_acerto = nova_combinacao
                    self.sequencia_acertos = 0
                    
                    enviar_rotacao_por_acertos_combinacoes(combinacao_atual, nova_combinacao)
        
        return self.estrategia_selecionada

    def obter_outras_combinacoes_quentes(self, combinacao_excluir):
        outras = []
        for combo in self.combinacoes_quentes:
            if combo != combinacao_excluir:
                if combo in self.historico_combinacoes:
                    dados = self.historico_combinacoes[combo]
                    if dados.get('eficiencia', 0) >= 60:
                        outras.append(combo)
        return outras[:2]

    def calcular_desempenho_estrategia(self, estrategia):
        if estrategia not in self.estrategias_contador:
            return 0.5
        
        stats = self.estrategias_contador[estrategia]
        tentativas = stats['tentativas']
        
        if tentativas == 0:
            return 0.5
        
        return stats['acertos'] / tentativas

    def gerar_previsao(self, historico):
        if not historico:
            return None
        
        estrategia = self.selecionar_estrategia(historico)
        
        previsao = None
        
        if estrategia == 'Zonas':
            ranking_zonas = self.estrategia_zonas.analisar_zonas(historico)
            previsao = self.estrategia_zonas.gerar_previsao(historico, ranking_zonas)
            
        elif estrategia == 'Midas':
            previsao = self.estrategia_midas.gerar_previsao(historico)
            
        elif estrategia == 'ML':
            previsao = self.estrategia_ml.gerar_previsao(historico)
        
        if previsao:
            # 🎯 Aplicar seleção inteligente para reduzir para 15 números
            if len(previsao['numeros_apostar']) > 15:
                numeros_originais = previsao['numeros_apostar']
                numeros_selecionados = self.seletor_inteligente.selecionar_melhores_15_numeros(
                    numeros_originais, 
                    historico, 
                    estrategia
                )
                previsao['numeros_apostar'] = numeros_selecionados
                previsao['qtd_numeros'] = len(numeros_selecionados)
            
            previsao['estrategia_usada'] = estrategia
            previsao['timestamp'] = len(historico)
        
        return previsao

    def processar_resultado(self, previsao, numero_real, historico):
        if not previsao:
            return False
        
        estrategia = previsao.get('estrategia_usada', 'Desconhecida')
        acerto = numero_real in previsao['numeros_apostar']
        
        # Atualizar estatísticas globais
        self.contador_sorteios_global += 1
        
        if acerto:
            self.acertos += 1
            self.sequencia_erros = 0
            
            # 🎯 NOVO: Atualizar sequência de acertos para combinações
            if 'zonas_envolvidas' in previsao:
                zonas_combo = tuple(sorted(previsao['zonas_envolvidas']))
                
                if zonas_combo == self.ultima_combinacao_acerto:
                    self.sequencia_acertos += 1
                else:
                    self.ultima_combinacao_acerto = zonas_combo
                    self.sequencia_acertos = 1
                
                # Registrar histórico de combinações que acertaram
                self.historico_combinacoes_acerto.append({
                    'combinacao': zonas_combo,
                    'timestamp': self.contador_sorteios_global,
                    'sequencia_atual': self.sequencia_acertos
                })
        else:
            self.erros += 1
            self.sequencia_erros += 1
            self.ultima_estrategia_erro = estrategia
            self.sequencia_acertos = 0
        
        # Atualizar estatísticas da estratégia específica
        if estrategia in self.estrategias_contador:
            self.estrategias_contador[estrategia]['tentativas'] += 1
            if acerto:
                self.estrategias_contador[estrategia]['acertos'] += 1
        
        # Atualizar histórico de desempenho
        self.historico_desempenho.append(acerto)
        if len(self.historico_desempenho) > 100:
            self.historico_desempenho.pop(0)
        
        # Atualizar estratégia específica
        if estrategia == 'Zonas':
            if 'zonas_envolvidas' in previsao:
                zonas = previsao['zonas_envolvidas']
                for zona in zonas:
                    self.estrategia_zonas.atualizar_stats(zona, acerto)
            
            elif 'zona' in previsao:
                zona = previsao['zona']
                if '+' in zona:
                    zonas = zona.split('+')
                    for z in zonas:
                        self.estrategia_zonas.atualizar_stats(z, acerto)
                else:
                    self.estrategia_zonas.atualizar_stats(zona, acerto)
        
        elif estrategia == 'ML':
            self.estrategia_ml.registrar_resultado(historico, numero_real, previsao)
        
        # 🎯 Atualizar sistema de tendências
        if 'zonas_envolvidas' in previsao or 'zona' in previsao:
            zona_acertada = None
            if acerto:
                if 'zonas_envolvidas' in previsao:
                    zona_acertada = '+'.join(previsao['zonas_envolvidas'])
                elif 'zona' in previsao:
                    zona_acertada = previsao['zona']
            
            ranking_zonas = self.estrategia_zonas.analisar_zonas(historico)
            self.sistema_tendencias.analisar_tendencia(
                ranking_zonas,
                acerto_ultima=acerto,
                zona_acertada=zona_acertada
            )
        
        # 🎯 Atualizar sistema de foco dinâmico
        self.atualizar_foco_dinamico(previsao, acerto, numero_real)
        
        return acerto

    def atualizar_foco_dinamico(self, previsao, acerto, numero_real):
        if 'zonas_envolvidas' in previsao:
            combinacao = tuple(sorted(previsao['zonas_envolvidas']))
            
            if combinacao not in self.historico_combinacoes:
                self.historico_combinacoes[combinacao] = {
                    'acertos': 0,
                    'tentativas': 0,
                    'ultimo_acerto': None,
                    'sequencia_atual': 0,
                    'sequencia_maxima': 0,
                    'eficiencia': 0
                }
            
            dados = self.historico_combinacoes[combinacao]
            dados['tentativas'] += 1
            
            if acerto:
                dados['acertos'] += 1
                dados['ultimo_acerto'] = self.contador_sorteios_global
                dados['sequencia_atual'] += 1
                dados['sequencia_maxima'] = max(dados['sequencia_maxima'], dados['sequencia_atual'])
            else:
                dados['sequencia_atual'] = 0
            
            # Calcular eficiência
            if dados['tentativas'] > 0:
                dados['eficiencia'] = dados['acertos'] / dados['tentativas'] * 100
            
            # Atualizar listas de combinações quentes/frias
            self.atualizar_listas_combinacoes()
            
            # 🎯 Atualizar combinações em alta/baixa
            self.analisar_performance_combinacoes()

    def atualizar_listas_combinacoes(self):
        todas_combinacoes = list(self.historico_combinacoes.items())
        
        # Ordenar por eficiência
        combinacoes_ordenadas = sorted(
            todas_combinacoes,
            key=lambda x: x[1]['eficiencia'] if x[1]['tentativas'] >= 3 else -1,
            reverse=True
        )
        
        # Top 3 combinações quentes
        self.combinacoes_quentes = [
            combo for combo, dados in combinacoes_ordenadas[:3]
            if dados['tentativas'] >= 3 and dados['eficiencia'] >= 60
        ]
        
        # Combinações frias (eficiencia < 40%)
        self.combinacoes_frias = [
            combo for combo, dados in todas_combinacoes
            if dados['tentativas'] >= 5 and dados['eficiencia'] < 40
        ]

    def analisar_performance_combinacoes(self):
        if not self.historico_combinacoes:
            return
        
        analise = {
            'timestamp': self.contador_sorteios_global,
            'total_combinacoes': len(self.historico_combinacoes),
            'combinacoes_quentes': len(self.combinacoes_quentes),
            'combinacoes_frias': len(self.combinacoes_frias),
            'melhor_combinacao': None,
            'pior_combinacao': None,
            'tendencia_geral': 'estavel'
        }
        
        # Encontrar melhor e pior combinação
        combinacoes_validas = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if dados['tentativas'] >= 5
        ]
        
        if combinacoes_validas:
            melhor = max(combinacoes_validas, key=lambda x: x[1]['eficiencia'])
            pior = min(combinacoes_validas, key=lambda x: x[1]['eficiencia'])
            
            analise['melhor_combinacao'] = {
                'combinacao': melhor[0],
                'eficiencia': melhor[1]['eficiencia'],
                'tentativas': melhor[1]['tentativas']
            }
            
            analise['pior_combinacao'] = {
                'combinacao': pior[0],
                'eficiencia': pior[1]['eficiencia'],
                'tentativas': pior[1]['tentativas']
            }
        
        # Determinar tendência
        if len(self.combinacoes_quentes) >= 2:
            analise['tendencia_geral'] = 'alta'
            self.combinacoes_em_alta = self.combinacoes_quentes[:2]
            self.combinacoes_em_baixa = self.combinacoes_frias[:1] if self.combinacoes_frias else []
        elif len(self.combinacoes_frias) >= 2:
            analise['tendencia_geral'] = 'baixa'
            self.combinacoes_em_baixa = self.combinacoes_frias[:2]
            self.combinacoes_em_alta = self.combinacoes_quentes[:1] if self.combinacoes_quentes else []
        
        self.ultima_analise_performance = analise
        
        # Armazenar histórico
        chave = f"analise_{self.contador_sorteios_global}"
        self.historico_performance[chave] = analise
        
        # Manter apenas últimas 20 análises
        if len(self.historico_performance) > 20:
            chaves_antigas = sorted(self.historico_performance.keys())[:-20]
            for chave in chaves_antigas:
                del self.historico_performance[chave]

    def get_estatisticas(self):
        total_tentativas = self.acertos + self.erros
        taxa_acerto = (self.acertos / total_tentativas * 100) if total_tentativas > 0 else 0
        
        stats = {
            'acertos': self.acertos,
            'erros': self.erros,
            'total': total_tentativas,
            'taxa_acerto': taxa_acerto,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'estrategia_atual': self.estrategia_selecionada,
            'contador_sorteios': self.contador_sorteios_global
        }
        
        # Adicionar estatísticas por estratégia
        stats['estrategias'] = {}
        for estrategia, dados in self.estrategias_contador.items():
            tentativas = dados['tentativas']
            acertos = dados['acertos']
            taxa = (acertos / tentativas * 100) if tentativas > 0 else 0
            stats['estrategias'][estrategia] = {
                'acertos': acertos,
                'tentativas': tentativas,
                'taxa_acerto': taxa
            }
        
        # Adicionar informações de combinações
        stats['combinacoes_quentes'] = self.combinacoes_quentes
        stats['combinacoes_frias'] = self.combinacoes_frias
        stats['total_combinacoes'] = len(self.historico_combinacoes)
        
        # Adicionar status do sistema de tendências
        stats['tendencias'] = self.sistema_tendencias.get_resumo_tendencia()
        
        return stats

# =============================
# FUNÇÕES AUXILIARES
# =============================
def obter_historico_aleatorio(quantidade=50):
    return [np.random.randint(0, 37) for _ in range(quantidade)]

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_historico(historico):
    try:
        with open(HISTORICO_PATH, 'w') as f:
            json.dump(list(historico)[-500:], f)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")
        return False

def buscar_ultimo_sorteio():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                ultimo_sorteio = data[0]
                if 'result' in ultimo_sorteio:
                    return ultimo_sorteio['result']
                elif 'number' in ultimo_sorteio:
                    return ultimo_sorteio['number']
                elif 'outcome' in ultimo_sorteio:
                    return ultimo_sorteio['outcome']
            
            elif isinstance(data, dict):
                if 'result' in data:
                    return data['result']
                elif 'number' in data:
                    return data['number']
                elif 'outcome' in data:
                    return data['outcome']
            
            logging.warning(f"Resposta da API inesperada: {data}")
            return None
            
    except Exception as e:
        logging.error(f"Erro ao buscar último sorteio: {e}")
    
    return None

# =============================
# INTERFACE STREAMLIT
# =============================
def main():
    st.set_page_config(
        page_title="Roleta Inteligente - Sistema Avançado",
        page_icon="🎰",
        layout="wide"
    )
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Inicializar estado da sessão
    if 'historico' not in st.session_state:
        st.session_state.historico = carregar_historico()
        if not st.session_state.historico:
            st.session_state.historico = obter_historico_aleatorio(30)
    
    if 'telegram_token' not in st.session_state:
        st.session_state.telegram_token = ''
    
    if 'telegram_chat_id' not in st.session_state:
        st.session_state.telegram_chat_id = ''
    
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaApostaRoleta()
        carregar_sessao()
    
    if 'ultima_previsao' not in st.session_state:
        st.session_state.ultima_previsao = None
    
    if 'auto_buscar' not in st.session_state:
        st.session_state.auto_buscar = False
    
    # Auto-refresh a cada 15 segundos se ativado
    if st.session_state.auto_buscar:
        count = st_autorefresh(interval=15000, key="autorefresh")
    
    # Sidebar
    with st.sidebar:
        st.title("🎰 Controle")
        
        st.subheader("🔧 Configurações")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Atualizar Sorteio", use_container_width=True):
                with st.spinner("Buscando último sorteio..."):
                    novo_numero = buscar_ultimo_sorteio()
                    if novo_numero is not None:
                        if (not st.session_state.historico or 
                            novo_numero != st.session_state.historico[-1]):
                            st.session_state.historico.append(novo_numero)
                            salvar_historico(st.session_state.historico)
                            
                            # Processar resultado se houver previsão
                            if st.session_state.ultima_previsao:
                                sistema = st.session_state.sistema
                                acerto = sistema.processar_resultado(
                                    st.session_state.ultima_previsao,
                                    novo_numero,
                                    st.session_state.historico
                                )
                                
                                # Enviar notificação
                                estrategia_nome = st.session_state.ultima_previsao.get('nome', 'Desconhecida')
                                zona_acertada = None
                                
                                if 'zonas_envolvidas' in st.session_state.ultima_previsao:
                                    zona_acertada = '+'.join(st.session_state.ultima_previsao['zonas_envolvidas'])
                                elif 'zona' in st.session_state.ultima_previsao:
                                    zona_acertada = st.session_state.ultima_previsao['zona']
                                elif 'zona_ml' in st.session_state.ultima_previsao:
                                    zona_acertada = st.session_state.ultima_previsao['zona_ml']
                                
                                enviar_resultado_super_simplificado(
                                    novo_numero, 
                                    acerto, 
                                    estrategia_nome,
                                    zona_acertada
                                )
                                
                                # Limpar previsão após processamento
                                st.session_state.ultima_previsao = None
                                
                            st.rerun()
                        else:
                            st.warning("Número repetido - aguardando novo sorteio")
                    else:
                        st.error("Erro ao buscar sorteio")
        
        with col2:
            st.session_state.auto_buscar = st.toggle("🔄 Auto-buscar", 
                                                    value=st.session_state.auto_buscar,
                                                    help="Atualiza automaticamente a cada 15 segundos")
        
        st.divider()
        
        st.subheader("🤖 Estratégia Ativa")
        estrategia_atual = st.session_state.sistema.estrategia_selecionada
        st.info(f"**{estrategia_atual}**")
        
        if st.button("🔄 Alternar Estratégia", use_container_width=True):
            sistema = st.session_state.sistema
            estrategia_atual = sistema.estrategia_selecionada
            
            if estrategia_atual == 'Zonas':
                sistema.estrategia_selecionada = 'ML'
            elif estrategia_atual == 'ML':
                sistema.estrategia_selecionada = 'Midas'
            else:
                sistema.estrategia_selecionada = 'Zonas'
            
            st.success(f"Estratégia alterada para: {sistema.estrategia_selecionada}")
            salvar_sessao()
            st.rerun()
        
        st.divider()
        
        st.subheader("📊 Gerenciamento")
        
        if st.button("🎯 Gerar Nova Previsão", use_container_width=True):
            with st.spinner("Analisando padrões e gerando previsão..."):
                sistema = st.session_state.sistema
                previsao = sistema.gerar_previsao(st.session_state.historico)
                
                if previsao:
                    st.session_state.ultima_previsao = previsao
                    salvar_sessao()
                    
                    # Enviar notificação
                    enviar_previsao_super_simplificada(previsao)
                    
                    st.rerun()
                else:
                    st.error("Não foi possível gerar previsão")
        
        if st.button("🧹 Limpar Histórico", use_container_width=True):
            if st.button("⚠️ Confirmar Limpeza", type="secondary", use_container_width=True):
                st.session_state.historico = obter_historico_aleatorio(10)
                salvar_historico(st.session_state.historico)
                st.success("Histórico limpo!")
                st.rerun()
        
        st.divider()
        
        st.subheader("💾 Persistência")
        
        col_save, col_load = st.columns(2)
        with col_save:
            if st.button("💾 Salvar Sessão", use_container_width=True):
                if salvar_sessao():
                    st.success("Sessão salva!")
                else:
                    st.error("Erro ao salvar sessão")
        
        with col_load:
            if st.button("📂 Carregar Sessão", use_container_width=True):
                if carregar_sessao():
                    st.success("Sessão carregada!")
                    st.rerun()
                else:
                    st.error("Erro ao carregar sessão")
        
        if st.button("🗑️ Limpar Sessão", type="secondary", use_container_width=True):
            if st.button("✅ Confirmar Limpeza Total", type="primary", use_container_width=True):
                limpar_sessao()
        
        st.divider()
        
        st.subheader("🔔 Notificações Telegram")
        
        st.session_state.telegram_token = st.text_input(
            "Token do Bot",
            value=st.session_state.telegram_token,
            type="password"
        )
        
        st.session_state.telegram_chat_id = st.text_input(
            "Chat ID",
            value=st.session_state.telegram_chat_id
        )
        
        if st.button("📱 Testar Conexão Telegram", use_container_width=True):
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                try:
                    enviar_telegram("✅ Conexão Telegram testada com sucesso!")
                    st.success("Mensagem enviada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao enviar: {e}")
            else:
                st.warning("Preencha Token e Chat ID primeiro")
    
    # Área principal
    st.title("🎰 Roleta Inteligente - Sistema Avançado")
    
    # Layout principal
    col_principal1, col_principal2 = st.columns([2, 1])
    
    with col_principal1:
        st.subheader("📈 Dashboard em Tempo Real")
        
        # Mostrar último número
        if st.session_state.historico:
            ultimo_numero = st.session_state.historico[-1]
            
            cor_numero = "red" if ultimo_numero in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black"
            if ultimo_numero == 0:
                cor_numero = "green"
            
            st.markdown(f"""
                <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin: 10px 0;">
                    <h1 style="color: white; font-size: 48px; margin: 0;">Último Número</h1>
                    <div style="font-size: 120px; font-weight: bold; color: {cor_numero}; text-shadow: 3px 3px 6px rgba(0,0,0,0.3);">
                        {ultimo_numero}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Mostrar estatísticas
        st.subheader("📊 Estatísticas do Sistema")
        
        sistema = st.session_state.sistema
        stats = sistema.get_estatisticas()
        
        col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
        
        with col_stats1:
            st.metric(
                "✅ Acertos",
                stats['acertos'],
                delta=f"{stats['taxa_acerto']:.1f}%"
            )
        
        with col_stats2:
            st.metric(
                "❌ Erros",
                stats['erros'],
                delta=f"-{100 - stats['taxa_acerto']:.1f}%",
                delta_color="inverse"
            )
        
        with col_stats3:
            st.metric(
                "🔢 Total Sorteios",
                stats['contador_sorteios']
            )
        
        with col_stats4:
            st.metric(
                "⚡ Estratégia Ativa",
                stats['estrategia_atual']
            )
        
        # Gráfico de desempenho
        if sistema.historico_desempenho:
            st.subheader("📈 Desempenho Recente")
            
            df_desempenho = pd.DataFrame({
                'Acerto': sistema.historico_desempenho
            })
            
            # Calcular média móvel
            if len(sistema.historico_desempenho) >= 5:
                df_desempenho['Media_Movel'] = df_desempenho['Acerto'].rolling(window=5).mean()
            
            st.line_chart(df_desempenho)
    
    with col_principal2:
        st.subheader("🎯 Previsão Ativa")
        
        if st.session_state.ultima_previsao:
            previsao = st.session_state.ultima_previsao
            
            # Card da previsão
            cor_confianca = "green" if previsao['confianca'] == "Alta" else "orange" if previsao['confianca'] == "Média" else "red"
            
            st.markdown(f"""
                <div style="padding: 20px; background: #1e1e1e; border-radius: 10px; border-left: 5px solid {cor_confianca}; margin: 10px 0;">
                    <h3 style="color: white; margin-top: 0;">{previsao['nome']}</h3>
                    <p style="color: #aaa;">Confiança: <span style="color: {cor_confianca}; font-weight: bold;">{previsao['confianca']}</span></p>
                    <p style="color: #aaa;">Números: {previsao['qtd_numeros']}</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Mostrar números para apostar
            st.markdown("**🎲 Números para Apostar:**")
            
            numeros_formatados = []
            for i, num in enumerate(previsao['numeros_apostar'], 1):
                cor = "red" if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black"
                if num == 0:
                    cor = "green"
                
                numeros_formatados.append(f"<span style='color: {cor}; font-weight: bold; padding: 5px; margin: 2px; display: inline-block;'>{num}</span>")
                
                if i % 6 == 0:
                    numeros_formatados.append("<br>")
            
            st.markdown(f"<div style='line-height: 2.5;'>{''.join(numeros_formatados)}</div>", 
                       unsafe_allow_html=True)
            
            # Botão para registrar resultado
            st.divider()
            st.subheader("📝 Registrar Resultado")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                numero_resultado = st.number_input("Número sorteado", 
                                                  min_value=0, 
                                                  max_value=36, 
                                                  value=0)
            
            with col_res2:
                st.write("")  # Espaçamento
                st.write("")  # Espaçamento
                if st.button("✅ Registrar Acerto", use_container_width=True):
                    sistema = st.session_state.sistema
                    acerto = sistema.processar_resultado(
                        previsao,
                        numero_resultado,
                        st.session_state.historico
                    )
                    
                    # Adicionar ao histórico
                    if numero_resultado not in st.session_state.historico or st.session_state.historico[-1] != numero_resultado:
                        st.session_state.historico.append(numero_resultado)
                        salvar_historico(st.session_state.historico)
                    
                    # Enviar notificação
                    estrategia_nome = previsao.get('nome', 'Desconhecida')
                    zona_acertada = None
                    
                    if 'zonas_envolvidas' in previsao:
                        zona_acertada = '+'.join(previsao['zonas_envolvidas'])
                    elif 'zona' in previsao:
                        zona_acertada = previsao['zona']
                    elif 'zona_ml' in previsao:
                        zona_acertada = previsao['zona_ml']
                    
                    enviar_resultado_super_simplificado(
                        numero_resultado, 
                        acerto, 
                        estrategia_nome,
                        zona_acertada
                    )
                    
                    # Limpar previsão
                    st.session_state.ultima_previsao = None
                    salvar_sessao()
                    st.rerun()
                
                if st.button("❌ Registrar Erro", type="secondary", use_container_width=True):
                    # Simular erros
                    sistema = st.session_state.sistema
                    acerto = False
                    sistema.processar_resultado(
                        previsao,
                        -1,  # Número que garante erro
                        st.session_state.historico
                    )
                    
                    # Enviar notificação
                    estrategia_nome = previsao.get('nome', 'Desconhecida')
                    enviar_resultado_super_simplificado(
                        -1, 
                        acerto, 
                        estrategia_nome
                    )
                    
                    # Limpar previsão
                    st.session_state.ultima_previsao = None
                    salvar_sessao()
                    st.rerun()
        else:
            st.info("Nenhuma previsão ativa. Gere uma nova previsão na sidebar.")
    
    # Abas de informações detalhadas
    st.divider()
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Detalhes", "🤖 Machine Learning", "🎯 Combinações", "📈 Tendências"])
    
    with tab1:
        st.subheader("Detalhes das Estratégias")
        
        col_tab1_1, col_tab1_2 = st.columns(2)
        
        with col_tab1_1:
            st.markdown("#### 🎯 Estratégia Zonas")
            st.text(st.session_state.sistema.estrategia_zonas.get_status())
        
        with col_tab1_2:
            st.markdown("#### 🤖 Estratégia ML")
            st.text(st.session_state.sistema.estrategia_ml.get_status())
        
        st.markdown("#### 📈 Estatísticas por Estratégia")
        for estrategia, dados in stats['estrategias'].items():
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                st.metric(f"{estrategia} - Acertos", dados['acertos'])
            with col_e2:
                st.metric(f"{estrategia} - Tentativas", dados['tentativas'])
            with col_e3:
                st.metric(f"{estrategia} - Taxa", f"{dados['taxa_acerto']:.1f}%")
    
    with tab2:
        st.subheader("Status do Machine Learning")
        
        status_ml = st.session_state.sistema.estrategia_ml.ml_model.get_status()
        
        col_ml1, col_ml2, col_ml3 = st.columns(3)
        
        with col_ml1:
            st.metric(
                "Modelo Treinado",
                "✅ Sim" if status_ml['is_trained'] else "❌ Não"
            )
        
        with col_ml2:
            st.metric(
                "Acurácia Validação",
                f"{status_ml['last_accuracy']:.1%}"
            )
        
        with col_ml3:
            st.metric(
                "Treinamentos Realizados",
                status_ml['retrain_counter']
            )
        
        # Botão para treinar ML manualmente
        if st.button("🎯 Treinar Modelo ML Manualmente", use_container_width=True):
            with st.spinner("Treinando modelo ML..."):
                historico = st.session_state.historico
                sistema = st.session_state.sistema
                sucesso, mensagem = sistema.estrategia_ml.ml_model.treinar_modelo(
                    historico, 
                    force_retrain=True
                )
                
                if sucesso:
                    st.success(mensagem)
                else:
                    st.error(mensagem)
                
                salvar_sessao()
    
    with tab3:
        st.subheader("Combinações Quentes e Frias")
        
        sistema = st.session_state.sistema
        
        col_comb1, col_comb2 = st.columns(2)
        
        with col_comb1:
            st.markdown("#### 🔥 Combinações Quentes")
            if sistema.combinacoes_quentes:
                for i, combo in enumerate(sistema.combinacoes_quentes[:3], 1):
                    dados = sistema.historico_combinacoes.get(combo, {})
                    eficiencia = dados.get('eficiencia', 0)
                    tentativas = dados.get('tentativas', 0)
                    
                    st.markdown(f"""
                        <div style="padding: 10px; background: #2d2d2d; border-radius: 5px; margin: 5px 0;">
                            <strong>{i}. {combo}</strong><br>
                            Eficiência: <span style="color: #4CAF50;">{eficiencia:.1f}%</span> | 
                            Tentativas: {tentativas}
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Nenhuma combinação quente detectada ainda")
        
        with col_comb2:
            st.markdown("#### ❄️ Combinações Frias")
            if sistema.combinacoes_frias:
                for i, combo in enumerate(sistema.combinacoes_frias[:3], 1):
                    dados = sistema.historico_combinacoes.get(combo, {})
                    eficiencia = dados.get('eficiencia', 0)
                    tentativas = dados.get('tentativas', 0)
                    
                    st.markdown(f"""
                        <div style="padding: 10px; background: #2d2d2d; border-radius: 5px; margin: 5px 0;">
                            <strong>{i}. {combo}</strong><br>
                            Eficiência: <span style="color: #F44336;">{eficiencia:.1f}%</span> | 
                            Tentativas: {tentativas}
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Nenhuma combinação fria detectada ainda")
        
        # Mostrar análise de performance
        if sistema.ultima_analise_performance:
            st.divider()
            st.markdown("#### 📊 Análise de Performance")
            
            analise = sistema.ultima_analise_performance
            
            col_an1, col_an2, col_an3 = st.columns(3)
            
            with col_an1:
                st.metric("Total Combinações", analise['total_combinacoes'])
            
            with col_an2:
                st.metric("Combinações Quentes", analise['combinacoes_quentes'])
            
            with col_an3:
                st.metric("Tendência Geral", analise['tendencia_geral'].upper())
    
    with tab4:
        st.subheader("Análise de Tendências")
        
        sistema = st.session_state.sistema
        
        # Obter análise atual de tendências
        ranking_zonas = sistema.estrategia_zonas.analisar_zonas(st.session_state.historico)
        analise_tendencia = sistema.sistema_tendencias.analisar_tendencia(
            ranking_zonas,
            acerto_ultima=(sistema.historico_desempenho[-1] if sistema.historico_desempenho else False),
            zona_acertada=sistema.obter_ultima_zona_acertada()
        )
        
        if analise_tendencia:
            # Card de status da tendência
            estado = analise_tendencia['estado']
            estado_cores = {
                'aguardando': 'gray',
                'formando': 'orange',
                'ativa': 'green',
                'enfraquecendo': 'red',
                'morta': 'black'
            }
            
            cor_estado = estado_cores.get(estado, 'gray')
            
            st.markdown(f"""
                <div style="padding: 20px; background: #1e1e1e; border-radius: 10px; border-left: 5px solid {cor_estado}; margin: 10px 0;">
                    <h3 style="color: white; margin-top: 0;">Estado da Tendência: {estado.upper()}</h3>
                    <p style="color: #aaa;">{analise_tendencia['mensagem']}</p>
                    <p style="color: #aaa;">Zona Dominante: <strong>{analise_tendencia['zona_dominante'] or 'Nenhuma'}</strong></p>
                    <p style="color: #aaa;">Ação Recomendada: <strong>{analise_tendencia['acao'].upper()}</strong></p>
                    <p style="color: #aaa;">Confiança: <strong>{analise_tendencia['confianca']:.0%}</strong></p>
                </div>
            """, unsafe_allow_html=True)
            
            # Contadores
            contadores = analise_tendencia['contadores']
            
            col_tend1, col_tend2, col_tend3, col_tend4 = st.columns(4)
            
            with col_tend1:
                st.metric("Confirmações", contadores['confirmacoes'])
            
            with col_tend2:
                st.metric("Acertos", contadores['acertos'])
            
            with col_tend3:
                st.metric("Erros", contadores['erros'])
            
            with col_tend4:
                st.metric("Operações", contadores['operacoes'])
            
            # Ranking de zonas atual
            st.divider()
            st.markdown("#### 🏆 Ranking de Zonas Atual")
            
            if ranking_zonas:
                for i, (zona, score) in enumerate(ranking_zonas[:3], 1):
                    col_z1, col_z2, col_z3 = st.columns([1, 3, 1])
                    with col_z1:
                        st.write(f"**#{i}**")
                    with col_z2:
                        st.progress(score/100, text=f"{zona}: {score:.1f}")
                    with col_z3:
                        stats = sistema.estrategia_zonas.stats_zonas.get(zona, {})
                        taxa = (stats.get('acertos', 0) / stats.get('tentativas', 1) * 100) if stats.get('tentativas', 0) > 0 else 0
                        st.write(f"{taxa:.1f}%")
        
        else:
            st.info("Aguardando dados suficientes para análise de tendências")
    
    # Rodapé
    st.divider()
    st.caption("🎰 Sistema de Roleta Inteligente - Desenvolvido com Streamlit e Machine Learning")
    st.caption(f"📊 Histórico atual: {len(st.session_state.historico)} sorteios | "
               f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if __name__ == "__main__":
    main()
