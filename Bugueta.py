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
from datetime import datetime

# =============================
# CONFIGURAÇÕES INICIAIS
# =============================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"
ML_MODEL_PATH = "ml_roleta_model.pkl"
SCALER_PATH = "ml_scaler.pkl"
META_PATH = "ml_meta.pkl"

# =============================
# VERIFICAÇÃO DE DEPENDÊNCIAS
# =============================
try:
    from catboost import CatBoostClassifier
    CATBOOST_DISPONIVEL = True
except ImportError:
    CATBOOST_DISPONIVEL = False
    logging.warning("CatBoost não disponível. Usando RandomForest como fallback.")

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        if 'sistema' not in st.session_state:
            logging.error("❌ Sistema não inicializado para salvar sessão")
            return False
            
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
                
            # INICIALIZAÇÃO SEGURA DO SISTEMA
            if 'sistema' not in st.session_state:
                st.session_state.sistema = SistemaRoletaCompleto()
                logging.info("✅ Sistema inicializado do zero durante carregamento")
                
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
                st.session_state.sistema.sistema_tendencias.historico_zonas_dominantes = deque(tendencias_historico_zonas, maxlen=12)
            
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

def criar_backup_automatico():
    """Cria backup automático da sessão"""
    try:
        if os.path.exists(SESSION_DATA_PATH):
            backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            import shutil
            shutil.copy2(SESSION_DATA_PATH, backup_path)
            logging.info(f"✅ Backup criado: {backup_path}")
    except Exception as e:
        logging.error(f"❌ Erro ao criar backup: {e}")

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO - COM CANAL AUXILIAR
# =============================
def enviar_telegram_mensagem(mensagem, chat_id=None):
    """Envia mensagem para o Telegram - Versão genérica com timeout"""
    try:
        token = st.session_state.get('telegram_token', '')
        if not token:
            logging.warning("❌ Token do Telegram não configurado")
            return False
            
        if chat_id is None:
            chat_id = st.session_state.get('telegram_chat_id', '')
            
        if not chat_id:
            logging.warning("❌ Chat ID do Telegram não configurado")
            return False
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info(f"✅ Mensagem enviada para Telegram (chat: {chat_id})")
            return True
        else:
            logging.error(f"❌ Erro Telegram: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Erro na conexão com Telegram: {e}")
        return False

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram (chat principal)"""
    return enviar_telegram_mensagem(mensagem, st.session_state.telegram_chat_id)

def enviar_para_canal_auxiliar(previsao):
    """🆕 ENVIA ALERTA DOS 15 NÚMEROS PARA O CANAL AUXILIAR"""
    try:
        nome_estrategia = previsao['nome']
        numeros_apostar = sorted(previsao['numeros_apostar'])
        
        # Formatar os 15 números em linhas
        metade = len(numeros_apostar) // 2
        linha1 = " ".join(map(str, numeros_apostar[:metade]))
        linha2 = " ".join(map(str, numeros_apostar[metade:]))
        
        # Determinar emoji baseado na estratégia
        if 'Zonas' in nome_estrategia:
            emoji = "🔥"
            tipo = "ZONAS"
        elif 'ML' in nome_estrategia:
            emoji = "🤖" 
            tipo = "MACHINE LEARNING"
        else:
            emoji = "💰"
            tipo = "MIDAS"
            
        # Mensagem para o canal auxiliar
        mensagem_auxiliar = (
            f"`{linha1}`\n"
            f"`{linha2}`\n"
        )
        
        # 🆕 CHAT ID FIXO DO CANAL AUXILIAR
        chat_id_auxiliar = "-1002932611974"
        
        return enviar_telegram_mensagem(mensagem_auxiliar, chat_id_auxiliar)
        
    except Exception as e:
        logging.error(f"❌ Erro ao enviar para canal auxiliar: {e}")
        return False

def enviar_resultado_para_canal_auxiliar(numero_real, acerto, nome_estrategia, zona_acertada=None):
    """🆕 ENVIA RESULTADO PARA O CANAL AUXILIAR"""
    try:
        if acerto:
            emoji = "🎉"
            resultado_texto = "ACERTOU"
            
            if zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha': nucleos.append("7")
                        elif zona == 'Azul': nucleos.append("10") 
                        elif zona == 'Amarela': nucleos.append("2")
                        else: nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    detalhe = f"Núcleos {nucleo_str}"
                else:
                    if zona_acertada == 'Vermelha': nucleo = "7"
                    elif zona_acertada == 'Azul': nucleo = "10"
                    elif zona_acertada == 'Amarela': nucleo = "2"
                    else: nucleo = zona_acertada
                    detalhe = f"Núcleo {nucleo}"
            else:
                detalhe = "Acerto direto"
        else:
            emoji = "💥"
            resultado_texto = "ERROU"
            detalhe = "Número fora da previsão"
        
        mensagem_auxiliar = (
            f"{emoji} *RESULTADO - {resultado_texto}*\n"
            f"🎲 *Número Sorteado:* `{numero_real}`\n"
        )
        
        # 🆕 CHAT ID FIXO DO CANAL AUXILIAR
        chat_id_auxiliar = "-1002932611974"
        
        return enviar_telegram_mensagem(mensagem_auxiliar, chat_id_auxiliar)
        
    except Exception as e:
        logging.error(f"❌ Erro ao enviar resultado para canal auxiliar: {e}")
        return False

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
        
        # 🆕 ENVIAR PARA CANAL AUXILIAR - ALERTA DOS 15 NÚMEROS
        if 'telegram_token' in st.session_state:
            if st.session_state.telegram_token:
                # Enviar alerta principal para o chat principal (se configurado)
                if st.session_state.telegram_chat_id:
                    enviar_alerta_numeros_simplificado(previsao)
                    enviar_telegram(f"🚨 PREVISÃO ATIVA\n{mensagem}\n💎 CONFIANÇA: {previsao.get('confianca', 'ALTA')}")
                
                # 🆕 SEMPRE enviar para o canal auxiliar
                enviar_para_canal_auxiliar(previsao)
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"❌ Erro ao enviar previsão: {e}")

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
        
        return enviar_telegram(mensagem_simplificada)
        
    except Exception as e:
        logging.error(f"❌ Erro ao enviar alerta simplificado: {e}")
        return False

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    """Envia notificação de resultado super simplificado"""
    try:
        if acerto:
            if 'Zonas' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha': nucleos.append("7")
                        elif zona == 'Azul': nucleos.append("10")
                        elif zona == 'Amarela': nucleos.append("2")
                        else: nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha': nucleo = "7"
                    elif zona_acertada == 'Azul': nucleo = "10"
                    elif zona_acertada == 'Amarela': nucleo = "2"
                    else: nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            elif 'ML' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha': nucleos.append("7")
                        elif zona == 'Azul': nucleos.append("10")
                        elif zona == 'Amarela': nucleos.append("2")
                        else: nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha': nucleo = "7"
                    elif zona_acertada == 'Azul': nucleo = "10"
                    elif zona_acertada == 'Amarela': nucleo = "2"
                    else: nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            else:
                mensagem = f"✅ Acerto\n🎲 Número: {numero_real}"
        else:
            mensagem = f"❌ Erro\n🎲 Número: {numero_real}"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        st.success(f"📢 {mensagem}") if acerto else st.error(f"📢 {mensagem}")
        
        # 🆕 ENVIAR PARA CANAL AUXILIAR - RESULTADO
        if 'telegram_token' in st.session_state:
            if st.session_state.telegram_token:
                # Enviar para chat principal (se configurado)
                if st.session_state.telegram_chat_id:
                    enviar_telegram(f"📢 RESULTADO\n{mensagem}")
                    enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia)
                
                # 🆕 SEMPRE enviar para o canal auxiliar
                enviar_resultado_para_canal_auxiliar(numero_real, acerto, nome_estrategia, zona_acertada)
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"❌ Erro ao enviar resultado: {e}")

def enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia):
    """Envia alerta de conferência super simplificado"""
    try:
        if acerto:
            mensagem = f"🎉 ACERTOU! {numero_real}"
        else:
            mensagem = f"💥 ERROU! {numero_real}"
            
        return enviar_telegram(mensagem)
        
    except Exception as e:
        logging.error(f"❌ Erro ao enviar alerta de conferência: {e}")
        return False

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova):
    """Envia notificação de rotação automática"""
    try:
        mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(f"🔄 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                return enviar_telegram(f"🔄 ROTAÇÃO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"❌ Erro ao enviar rotação: {e}")
        return False

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
                return enviar_telegram(f"🎯 ROTAÇÃO POR ACERTOS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"❌ Erro ao enviar rotação por acertos: {e}")
        return False

# =============================
# SISTEMA DE DETECÇÃO DE TENDÊNCIAS - VERSÃO MÉDIA/EQUILIBRADA
# =============================
class SistemaTendencias:
    def __init__(self):
        self.historico_tendencias = deque(maxlen=50)
        self.tendencia_ativa = None
        self.estado_tendencia = "aguardando"
        self.contador_confirmacoes = 0
        self.contador_erros_tendencia = 0
        self.contador_acertos_tendencia = 0
        self.ultima_zona_dominante = None
        self.historico_zonas_dominantes = deque(maxlen=12)  # 🔄 MÉDIO
        
        # ⚖️ CONFIGURAÇÃO MÉDIA/EQUILIBRADA
        self.max_operacoes_por_tendencia = 10      # 🔥 10 OPERAÇÕES
        self.requer_confirmacoes = 2               # ⚖️ 2 confirmações (médio)
        self.stop_loss_erros = 2                   # ⚖️ 2 erros para parar (médio)
        self.min_acertos_operar = 1                # ⚖️ 1 acerto para operar
        
        self.rodadas_operando = 0
        
    def analisar_tendencia(self, zonas_rankeadas, acerto_ultima=False, zona_acertada=None):
        """
        ⚖️ SISTEMA MÉDIO/EQUILIBRADO - Fluxograma completo
        """
        try:
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
        except Exception as e:
            logging.error(f"❌ Erro na análise de tendência: {e}")
            return self._criar_resposta_tendencia("aguardando", None, f"Erro na análise: {str(e)}")
    
    def _analisar_formacao_tendencia(self, zona_top1, zona_top2, score_top1, zonas_rankeadas):
        """⚖️ CRITÉRIOS MÉDIOS PARA FORMAÇÃO DA TENDÊNCIA"""
        
        # Verificar se a mesma zona aparece repetidamente
        freq_zona_top1 = list(self.historico_zonas_dominantes).count(zona_top1)
        frequencia_minima = 3 if len(self.historico_zonas_dominantes) >= 6 else 2
        
        # Verificar dispersão (se outras zonas estão fracas)
        dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
        
        # ⚖️ CRITÉRIOS MÉDIOS/EQUILIBRADOS
        if (freq_zona_top1 >= frequencia_minima and 
            score_top1 >= 23 and  # ⚖️ MÉDIO (entre 22 e 25)
            dispersao <= 0.65):   # ⚖️ MÉDIO (entre 0.6 e 0.7)
            
            if self.estado_tendencia == "aguardando":
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                logging.info(f"📈 Tendência FORMANDO - {zona_top1} (freq: {freq_zona_top1}, score: {score_top1:.1f})")
                
                return self._criar_resposta_tendencia(
                    "formando", zona_top1, 
                    f"Tendência se formando - Zona {zona_top1} aparecendo repetidamente"
                )
            
            elif self.estado_tendencia == "formando":
                self.contador_confirmacoes += 1
                logging.info(f"📈 Tendência confirmando - {zona_top1} ({self.contador_confirmacoes}/{self.requer_confirmacoes})")
                
                if self.contador_confirmacoes >= self.requer_confirmacoes:
                    self.estado_tendencia = "ativa"
                    self.contador_acertos_tendencia = 0
                    self.contador_erros_tendencia = 0
                    self.rodadas_operando = 0
                    logging.info(f"🎯 TENDÊNCIA ATIVA - {zona_top1} - 10 OPERAÇÕES MÉDIAS")
                    
                    return self._criar_resposta_tendencia(
                        "ativa", zona_top1,
                        f"✅ TENDÊNCIA CONFIRMADA - Zona {zona_top1}. Sistema MÉDIO ativado (10 operações)",
                        "operar"
                    )
        
        return self._criar_resposta_tendencia(
            self.estado_tendencia, self.tendencia_ativa,
            f"Aguardando confirmação - {zona_top1} no Top 1"
        )
    
    def _analisar_tendencia_ativa(self, zona_top1, zona_top2, acerto_ultima, zona_acertada):
        """⚖️ SISTEMA MÉDIO DE OPERAÇÕES - 10 PARTIDAS"""
        
        # Verificar se ainda é a mesma zona dominante
        mesma_zona = zona_top1 == self.tendencia_ativa
        
        # Atualizar contadores baseado no último resultado
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0  # Reset erros ao acertar
            logging.info(f"🎯 Acerto na tendência {self.tendencia_ativa} - Total: {self.contador_acertos_tendencia}")
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
            logging.info(f"⚠️ Erro na tendência {self.tendencia_ativa} - Sequência: {self.contador_erros_tendencia}")
        
        self.rodadas_operando += 1
        
        # ⚖️ CRITÉRIOS MÉDIOS PARA OPERAR
        pode_operar = (
            self.contador_acertos_tendencia >= self.min_acertos_operar and  # Pelo menos 1 acerto
            self.contador_erros_tendencia < self.stop_loss_erros and       # Menos de 2 erros
            self.rodadas_operando <= self.max_operacoes_por_tendencia and  # Máximo 10 ops
            mesma_zona                                                     # Ainda mesma zona
        )
        
        if pode_operar:
            operacoes_restantes = self.max_operacoes_por_tendencia - self.rodadas_operando
            mensagem = f"🔥 OPERAR - Tendência {self.tendencia_ativa} ({self.contador_acertos_tendencia}✓ {self.contador_erros_tendencia}✗) - {operacoes_restantes} ops restantes"
            
            return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, mensagem, "operar")
        
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
        """⚖️ REINÍCIO MÉDIO APÓS MORTE DA TENDÊNCIA"""
        
        # Aguardar rodadas suficientes após morte da tendência
        rodadas_desde_morte = len([z for z in self.historico_zonas_dominantes if z != self.tendencia_ativa])
        
        # ⚖️ Aguardar período médio
        if rodadas_desde_morte >= 7:  # 🔄 MÉDIO (entre 6-8)
            # Verificar se nova tendência está se formando
            freq_zona_atual = list(self.historico_zonas_dominantes).count(zona_top1)
            dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
            
            # ⚖️ Critérios médios para nova tendência
            if freq_zona_atual >= 3 and dispersao <= 0.65:
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                
                return self._criar_resposta_tendencia(
                    "formando", zona_top1,
                    f"🔄 NOVA TENDÊNCIA MÉDIA se formando - {zona_top1}"
                )
        
        return self._criar_resposta_tendencia(
            "morta", None,
            f"🔄 Aguardando nova tendência ({rodadas_desde_morte}/7 rodadas)"
        )
    
    def _detectar_enfraquecimento(self, zona_top1, zona_top2, acerto_ultima):
        """⚖️ SINAIS MÉDIOS DE ENFRAQUECIMENTO"""
        sinais = []
        
        # 1. Zona dominante saindo do Top 1
        if zona_top1 != self.tendencia_ativa:
            sinais.append("zona saiu do Top 1")
        
        # 2. Nova zona aparecendo forte no Top 2
        if (zona_top2 and zona_top2 != self.tendencia_ativa and 
            zona_top2 not in [self.tendencia_ativa, zona_top1]):
            sinais.append("nova zona forte no Top 2")
        
        # 3. ⚖️ Padrão médio de alternância (acerta/erra)
        if (self.contador_erros_tendencia >= 1 and 
            self.contador_acertos_tendencia >= 1 and
            self.rodadas_operando >= 4):
            sinais.append("padrão acerta/erra")
        
        # 4. ⚖️ Muitas operações (mais da metade)
        if self.rodadas_operando >= 6:
            sinais.append("6+ operações realizadas")
        
        return " | ".join(sinais) if sinais else None
    
    def _detectar_morte_tendencia(self, zona_top1):
        """⚖️ CRITÉRIOS MÉDIOS PARA MORTE DA TENDÊNCIA"""
        
        # 1. ❌ Stop loss médio - 2 erros seguidos
        if self.contador_erros_tendencia >= self.stop_loss_erros:
            return True
        
        # 2. ❌ Zona dominante sumiu dos primeiros lugares
        if (zona_top1 != self.tendencia_ativa and 
            self.tendencia_ativa not in list(self.historico_zonas_dominantes)[-3:]):
            return True
        
        # 3. ❌ Muitas zonas diferentes aparecendo
        zonas_recentes = list(self.historico_zonas_dominantes)[-6:]
        zonas_unicas = len(set(zonas_recentes))
        if len(zonas_recentes) >= 4 and zonas_unicas >= 3:
            return True
        
        # 4. ❌ Taxa de acertos baixa
        total_tentativas = self.contador_acertos_tendencia + self.contador_erros_tendencia
        if total_tentativas >= 5:
            taxa_acertos = self.contador_acertos_tendencia / total_tentativas
            if taxa_acertos < 0.4:  # ⚖️ 40% de acertos mínimo
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
                'operacoes': self.rodadas_operando,
                'max_operacoes': self.max_operacoes_por_tendencia
            }
        }
    
    def _calcular_confianca_tendencia(self, estado):
        """⚖️ NÍVEIS DE CONFIABILIDADE MÉDIOS"""
        confiancas = {
            'aguardando': 0.15,
            'formando': 0.50,    # ⚖️ MÉDIO
            'ativa': 0.75,       # ⚖️ MÉDIO  
            'enfraquecendo': 0.40,
            'morta': 0.05
        }
        return confiancas.get(estado, 0.15)
    
    def get_resumo_tendencia(self):
        """Retorna resumo atual do estado da tendência"""
        return {
            'estado': self.estado_tendencia,
            'zona_ativa': self.tendencia_ativa,
            'configuracao': {
                'max_operacoes': self.max_operacoes_por_tendencia,
                'stop_loss': self.stop_loss_erros,
                'confirmacoes_necessarias': self.requer_confirmacoes
            },
            'contadores': {
                'confirmacoes': self.contador_confirmacoes,
                'acertos': self.contador_acertos_tendencia,
                'erros': self.contador_erros_tendencia,
                'operacoes': self.rodadas_operando,
                'operacoes_restantes': max(0, self.max_operacoes_por_tendencia - self.rodadas_operando)
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
            if CATBOOST_DISPONIVEL:
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
            else:
                # Fallback para RandomForest
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
                
        except Exception as e:
            logging.warning(f"Erro no treinamento do modelo ({e}). Usando RandomForest como fallback.")
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
                    X_scaled, y, 
                    test_size=0.2, 
                    random_state=self.seed
                )

            self.models = []
            model_types = []
            
            for i in range(self.ensemble_size):
                model, model_type = self._build_and_train_model(
                    X_train, y_train, X_val, y_val, seed=self.seed + i
                )
                self.models.append(model)
                model_types.append(model_type)
            
            self.is_trained = True
            self.contador_treinamento += 1
            
            acc_val = accuracy_score(y_val, self.prever(X_val))
            
            self.meta = {
                'ultimo_treinamento': datetime.now().isoformat(),
                'tamanho_dataset': len(X),
                'accuracy_val': acc_val,
                'model_types': model_types,
                'classes_unicas': len(set(y)),
                'contador_treinamentos': self.contador_treinamento
            }
            
            logging.info(f"✅ Modelo treinado com sucesso. Acurácia val: {acc_val:.3f}")
            return True, f"Modelo treinado com {len(X)} amostras. Acurácia val: {acc_val:.3f}"
            
        except Exception as e:
            logging.error(f"❌ Erro no treinamento: {e}")
            return False, f"Erro no treinamento: {str(e)}"

    def prever(self, X):
        if not self.is_trained or not self.models:
            return None
        
        try:
            if isinstance(X, list):
                X = np.array(X)
            
            if X.ndim == 1:
                X = X.reshape(1, -1)
            
            X_scaled = self.scaler.transform(X)
            
            preds = []
            for model in self.models:
                if hasattr(model, 'predict_proba'):
                    probas = model.predict_proba(X_scaled)
                    preds.append(probas)
                else:
                    pred = model.predict(X_scaled)
                    preds.append(pred)
            
            if hasattr(self.models[0], 'predict_proba'):
                avg_proba = np.mean(preds, axis=0)
                final_pred = np.argmax(avg_proba, axis=1)
            else:
                final_pred = np.array(preds).mean(axis=0).round().astype(int)
            
            return final_pred
            
        except Exception as e:
            logging.error(f"❌ Erro na previsão: {e}")
            return None

    def prever_proximo_numero(self, historico):
        try:
            if not self.is_trained:
                return None, 0.0
            
            feats, _ = self.extrair_features(historico)
            if feats is None:
                return None, 0.0
            
            pred = self.prever([feats])
            if pred is None or len(pred) == 0:
                return None, 0.0
            
            numero_predito = pred[0]
            
            if hasattr(self.models[0], 'predict_proba'):
                X_scaled = self.scaler.transform([feats])
                probas = self.models[0].predict_proba(X_scaled)
                confianca = np.max(probas[0])
            else:
                confianca = 0.5
            
            return numero_predito, confianca
            
        except Exception as e:
            logging.error(f"❌ Erro ao prever próximo número: {e}")
            return None, 0.0

    def get_estatisticas_modelo(self):
        if not self.is_trained:
            return "Modelo não treinado"
        
        info = f"📊 ESTATÍSTICAS DO MODELO (Ensemble)\n"
        info += f"✅ Modelos treinados: {len(self.models)}\n"
        info += f"📈 Tipo dos modelos: {', '.join(set([type(model).__name__ for model in self.models]))}\n"
        info += f"🔄 Contador de treinamentos: {self.meta.get('contador_treinamentos', 0)}\n"
        info += f"📦 Tamanho do dataset: {self.meta.get('tamanho_dataset', 0)} amostras\n"
        info += f"🎯 Acurácia val: {self.meta.get('accuracy_val', 0):.3f}\n"
        info += f"🔢 Classes únicas: {self.meta.get('classes_unicas', 0)}\n"
        info += f"⏰ Último treinamento: {self.meta.get('ultimo_treinamento', 'Nunca')}\n"
        
        return info

# =============================
# ESTRATÉGIA DE MACHINE LEARNING
# =============================
class EstrategiaML:
    def __init__(self, roleta_inteligente):
        self.roleta = roleta_inteligente
        self.historico = deque(maxlen=30)
        self.contador_sorteios = 0
        self.ml_model = MLRoletaOtimizada(roleta_inteligente)
        
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

    def gerar_previsao(self, historico_geral):
        try:
            if len(historico_geral) < 50:
                return {
                    'nome': 'Machine Learning',
                    'numeros_apostar': [],
                    'confianca': 'Baixa',
                    'mensagem': 'Dados insuficientes para ML (mínimo 50 sorteios)'
                }
            
            # Treinar modelo se necessário
            if not self.ml_model.is_trained or self.contador_sorteios % 15 == 0:
                sucesso, mensagem = self.ml_model.treinar_modelo(historico_geral)
                if sucesso:
                    logging.info(f"✅ Modelo ML treinado: {mensagem}")
                else:
                    logging.warning(f"⚠️ Falha no treinamento ML: {mensagem}")
            
            # Fazer previsão
            numero_predito, confianca = self.ml_model.prever_proximo_numero(historico_geral)
            
            if numero_predito is None:
                return {
                    'nome': 'Machine Learning',
                    'numeros_apostar': [],
                    'confianca': 'Baixa', 
                    'mensagem': 'Falha na previsão do modelo'
                }
            
            # Converter confiança numérica para textual
            if confianca >= 0.7:
                confianca_texto = 'Alta'
            elif confianca >= 0.5:
                confianca_texto = 'Média'
            else:
                confianca_texto = 'Baixa'
            
            # Selecionar números baseados na previsão
            numeros_apostar = self._selecionar_numeros_ml(numero_predito, historico_geral, confianca)
            
            self.contador_sorteios += 1
            
            return {
                'nome': f'Machine Learning (Conf: {confianca_texto})',
                'numeros_apostar': numeros_apostar,
                'confianca': confianca_texto,
                'numero_predito': numero_predito,
                'confianca_num': confianca,
                'mensagem': f'Previsão ML: {numero_predito} (conf: {confianca:.2f})'
            }
            
        except Exception as e:
            logging.error(f"❌ Erro na estratégia ML: {e}")
            return {
                'nome': 'Machine Learning',
                'numeros_apostar': [],
                'confianca': 'Baixa',
                'mensagem': f'Erro: {str(e)}'
            }

    def _selecionar_numeros_ml(self, numero_central, historico, confianca):
        """Seleciona 15 números baseados na previsão do ML"""
        if confianca >= 0.7:
            # Alta confiança: foco no número predito e vizinhos próximos
            vizinhos = self.roleta.get_vizinhos_zona(numero_central, quantidade=7)
            numeros_selecionados = list(set(vizinhos))[:15]
        elif confianca >= 0.5:
            # Média confiança: número predito + vizinhos médios
            vizinhos = self.roleta.get_vizinhos_zona(numero_central, quantidade=10)
            numeros_selecionados = list(set(vizinhos))[:15]
        else:
            # Baixa confiança: estratégia mais diversificada
            vizinhos = self.roleta.get_vizinhos_zona(numero_central, quantidade=12)
            numeros_selecionados = list(set(vizinhos))[:15]
        
        # Garantir que temos exatamente 15 números
        while len(numeros_selecionados) < 15:
            numeros_selecionados.append(np.random.randint(0, 37))
        
        return numeros_selecionados[:15]

    def processar_resultado(self, numero_sorteado, previsao, acerto):
        self.historico.append({
            'numero_sorteado': numero_sorteado,
            'previsao': previsao,
            'acerto': acerto,
            'timestamp': datetime.now()
        })

# =============================
# ESTRATÉGIA DAS ZONAS
# =============================
class EstrategiaZonas:
    def __init__(self, roleta_inteligente):
        self.roleta = roleta_inteligente
        self.historico = deque(maxlen=70)
        
        # Definir as zonas na roleta
        self.zonas = {
            'Vermelha': [32, 19, 21, 25, 34, 27, 36, 30, 23, 5, 16, 1, 14, 9, 18, 7, 12, 3],
            'Azul': [15, 4, 2, 17, 6, 13, 11, 8, 10, 24, 33, 20, 31, 22, 29, 28, 35, 26],
            'Amarela': [0]  # Zero como zona especial
        }
        
        # Estatísticas por zona
        self.stats_zonas = {
            'Vermelha': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
            'Azul': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
            'Amarela': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
        }

    def identificar_zona(self, numero):
        for zona, numeros in self.zonas.items():
            if numero in numeros:
                return zona
        return None

    def analisar_desempenho_zonas(self):
        zonas_rankeadas = []
        
        for zona, stats in self.stats_zonas.items():
            if stats['tentativas'] > 0:
                performance = stats['acertos'] / stats['tentativas']
                score = self._calcular_score_zona(zona, stats, performance)
                zonas_rankeadas.append((zona, score))
        
        # Ordenar por score (maior primeiro)
        zonas_rankeadas.sort(key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def _calcular_score_zona(self, zona, stats, performance):
        score = performance * 100
        
        # Bônus por sequência atual
        score += stats['sequencia_atual'] * 2
        
        # Bônus por performance consistente
        if stats['tentativas'] >= 10:
            score += min(20, (performance - 0.3) * 100)
        
        # Bônus especial para zona quente
        if stats['sequencia_atual'] >= 2:
            score += 15
        
        return score

    def gerar_previsao(self, historico_geral):
        try:
            if len(historico_geral) < 10:
                return {
                    'nome': 'Zonas Quentes',
                    'numeros_apostar': [],
                    'confianca': 'Baixa',
                    'mensagem': 'Aguardando mais dados históricos'
                }
            
            # Analisar desempenho das zonas
            zonas_rankeadas = self.analisar_desempenho_zonas()
            
            if not zonas_rankeadas:
                return {
                    'nome': 'Zonas Quentes',
                    'numeros_apostar': [],
                    'confianca': 'Baixa',
                    'mensagem': 'Sem zonas com dados suficientes'
                }
            
            zona_principal, score_principal = zonas_rankeadas[0]
            
            # Determinar confiança baseada no score
            if score_principal >= 60:
                confianca = 'Alta'
                zonas_apostar = [zona_principal]
            elif score_principal >= 40:
                confianca = 'Média'
                # Incluir segunda melhor zona se estiver próxima
                if len(zonas_rankeadas) > 1 and zonas_rankeadas[1][1] >= 35:
                    zonas_apostar = [zona_principal, zonas_rankeadas[1][0]]
                else:
                    zonas_apostar = [zona_principal]
            else:
                confianca = 'Baixa'
                zonas_apostar = [zona_principal]
            
            # Selecionar números das zonas escolhidas
            numeros_apostar = []
            for zona in zonas_apostar:
                numeros_apostar.extend(self.zonas[zona])
            
            # Remover duplicatas e limitar a 15 números
            numeros_apostar = list(set(numeros_apostar))
            
            # Usar seleção inteligente se necessário
            if len(numeros_apostar) > 15:
                selecionador = SistemaSelecaoInteligente()
                numeros_apostar = selecionador.selecionar_melhores_15_numeros(
                    numeros_apostar, historico_geral, 'Zonas'
                )
            
            return {
                'nome': f'Zonas Quentes ({zona_principal})',
                'numeros_apostar': numeros_apostar,
                'confianca': confianca,
                'zona': zona_principal,
                'zonas_envolvidas': zonas_apostar,
                'score_zona': score_principal,
                'mensagem': f'Zona {zona_principal} com score {score_principal:.1f}'
            }
            
        except Exception as e:
            logging.error(f"❌ Erro na estratégia de Zonas: {e}")
            return {
                'nome': 'Zonas Quentes',
                'numeros_apostar': [],
                'confianca': 'Baixa',
                'mensagem': f'Erro: {str(e)}'
            }

    def processar_resultado(self, numero_sorteado, previsao, acerto):
        zona_sorteada = self.identificar_zona(numero_sorteado)
        
        if zona_sorteada:
            # Atualizar estatísticas da zona sorteada
            self.stats_zonas[zona_sorteada]['tentativas'] += 1
            if acerto:
                self.stats_zonas[zona_sorteada]['acertos'] += 1
                self.stats_zonas[zona_sorteada]['sequencia_atual'] += 1
                self.stats_zonas[zona_sorteada]['sequencia_maxima'] = max(
                    self.stats_zonas[zona_sorteada]['sequencia_maxima'],
                    self.stats_zonas[zona_sorteada]['sequencia_atual']
                )
            else:
                self.stats_zonas[zona_sorteada]['sequencia_atual'] = 0
            
            # Calcular performance média
            if self.stats_zonas[zona_sorteada]['tentativas'] > 0:
                self.stats_zonas[zona_sorteada]['performance_media'] = (
                    self.stats_zonas[zona_sorteada]['acertos'] / 
                    self.stats_zonas[zona_sorteada]['tentativas']
                )
        
        self.historico.append({
            'numero_sorteado': numero_sorteado,
            'zona_sorteada': zona_sorteada,
            'previsao': previsao,
            'acerto': acerto,
            'timestamp': datetime.now()
        })

# =============================
# ESTRATÉGIA MIDAS
# =============================
class EstrategiaMidas:
    def __init__(self, roleta_inteligente):
        self.roleta = roleta_inteligente
        self.historico = deque(maxlen=15)
        self.contador_operacoes = 0

    def gerar_previsao(self, historico_geral):
        try:
            if len(historico_geral) < 5:
                return {
                    'nome': 'Midas',
                    'numeros_apostar': [],
                    'confianca': 'Baixa',
                    'mensagem': 'Aguardando mais dados históricos'
                }
            
            # Estratégia Midas: foco nos últimos números sorteados
            ultimos_numeros = list(historico_geral)[-5:]
            
            # Selecionar números baseados nos últimos resultados
            numeros_candidatos = set()
            for numero in ultimos_numeros:
                vizinhos = self.roleta.get_vizinhos_zona(numero, quantidade=8)
                numeros_candidatos.update(vizinhos)
            
            numeros_candidatos = list(numeros_candidatos)
            
            # Usar seleção inteligente para escolher os 15 melhores
            selecionador = SistemaSelecaoInteligente()
            numeros_apostar = selecionador.selecionar_melhores_15_numeros(
                numeros_candidatos, historico_geral, 'Midas'
            )
            
            self.contador_operacoes += 1
            
            return {
                'nome': 'Midas (Últimos Números)',
                'numeros_apostar': numeros_apostar,
                'confianca': 'Média',
                'mensagem': f'Baseado nos últimos {len(ultimos_numeros)} números sorteados'
            }
            
        except Exception as e:
            logging.error(f"❌ Erro na estratégia Midas: {e}")
            return {
                'nome': 'Midas',
                'numeros_apostar': [],
                'confianca': 'Baixa',
                'mensagem': f'Erro: {str(e)}'
            }

    def processar_resultado(self, numero_sorteado, previsao, acerto):
        self.historico.append({
            'numero_sorteado': numero_sorteado,
            'previsao': previsao,
            'acerto': acerto,
            'timestamp': datetime.now()
        })

# =============================
# SISTEMA PRINCIPAL COMPLETO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.roleta = RoletaInteligente()
        
        # Inicializar estratégias
        self.estrategia_zonas = EstrategiaZonas(self.roleta)
        self.estrategia_midas = EstrategiaMidas(self.roleta)
        self.estrategia_ml = EstrategiaML(self.roleta)
        
        # 🎯 ADICIONAR SISTEMA DE TENDÊNCIAS MÉDIO/EQUILIBRADO
        self.sistema_tendencias = SistemaTendencias()
        
        # Contadores gerais
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ''
        
        # NOVO: Sistema de 3 acertos para combinações
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        # Sistema de seleção inteligente
        self.selecionador_inteligente = SistemaSelecaoInteligente()
        
        # Estratégia selecionada
        self.estrategia_selecionada = 'Zonas'
        
        # Combinações dinâmicas
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        logging.info("✅ Sistema de Tendências MÉDIO/EQUILIBRADO inicializado - 10 operações, stop loss 2 erros")

    def get_analise_tendencias_completa(self):
        """Retorna análise completa das tendências - VERSÃO MÉDIA"""
        analise = "🎯 SISTEMA DE DETECÇÃO DE TENDÊNCIAS - MÉDIO/EQUILIBRADO\n"
        analise += "=" * 70 + "\n"
        
        resumo = self.sistema_tendencias.get_resumo_tendencia()
        
        analise += f"📊 ESTADO ATUAL: {resumo['estado'].upper()}\n"
        analise += f"📍 ZONA ATIVA: {resumo['zona_ativa'] or 'Nenhuma'}\n"
        analise += f"⚙️  CONFIGURAÇÃO: {resumo['configuracao']['max_operacoes']} operações | Stop: {resumo['configuracao']['stop_loss']} erros | Conf: {resumo['configuracao']['confirmacoes_necessarias']}\n"
        analise += f"🎯 CONTADORES: {resumo['contadores']['acertos']} acertos, {resumo['contadores']['erros']} erros\n"
        analise += f"📈 CONFIRMAÇÕES: {resumo['contadores']['confirmacoes']}\n"
        analise += f"🔄 OPERAÇÕES: {resumo['contadores']['operacoes']}/{resumo['contadores']['max_operacoes']} ({resumo['contadores']['operacoes_restantes']} restantes)\n"
        
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
        
        # ⚖️ RECOMENDAÇÃO BASEADA NO SISTEMA MÉDIO
        analise += "\n💡 RECOMENDAÇÃO DO SISTEMA MÉDIO:\n"
        estado = resumo['estado']
        if estado == "aguardando":
            analise += "  👀 Observar últimas 6-8 rodadas\n"
            analise += "  🎯 Identificar zona com frequência ≥3 em 6 rodadas\n"
            analise += "  📊 Score mínimo: 23 | Dispersão máxima: 0.65\n"
        elif estado == "formando":
            analise += "  📈 Tendência se formando\n"
            analise += "  ⏳ Aguardar 2ª confirmação para ativar\n"
            analise += "  🔄 Sistema médio: 10 operações disponíveis\n"
        elif estado == "ativa":
            analise += "  🔥 TENDÊNCIA CONFIRMADA - SISTEMA MÉDIO ATIVO\n"
            analise += "  💰 Operar por até 10 jogadas\n"
            analise += "  🎯 Stop loss: 2 erros consecutivos\n"
            analise += "  ✅ Pelo menos 1 acerto para continuar\n"
            analise += "  📊 Operações restantes: {}\n".format(resumo['contadores']['operacoes_restantes'])
        elif estado == "enfraquecendo":
            analise += "  ⚠️ TENDÊNCIA ENFRAQUECENDO\n"
            analise += "  🚫 Reduzir exposição\n"
            analise += "  👀 Observar sinais de morte (2 erros ou zona sair do Top 3)\n"
        elif estado == "morta":
            analise += "  🟥 TENDÊNCIA MORTA\n"
            analise += "  🛑 PARAR OPERAÇÕES\n"
            analise += "  🔄 Aguardar 7 rodadas para nova análise\n"
            analise += "  📊 Observar novo padrão de zonas\n"
        
        return analise

    def enviar_notificacoes_tendencia(self, analise_tendencia):
        """Envia notificações baseadas no estado da tendência - SISTEMA MÉDIO"""
        estado = analise_tendencia['estado']
        mensagem = analise_tendencia['mensagem']
        zona = analise_tendencia['zona_dominante']
        contadores = analise_tendencia['contadores']
        
        if estado == "ativa" and analise_tendencia['acao'] == "operar":
            # 🔥 TENDÊNCIA CONFIRMADA - OPERAR (SISTEMA MÉDIO)
            operacoes_restantes = 10 - contadores['operacoes']
            enviar_telegram(f"🎯 TENDÊNCIA CONFIRMADA - SISTEMA MÉDIO\n"
                          f"📍 Zona: {zona}\n"
                          f"📈 Estado: {estado}\n"
                          f"💡 Ação: OPERAR\n"
                          f"🔥 Operações restantes: {operacoes_restantes}/10\n"
                          f"📊 Performance: {contadores['acertos']}✓ {contadores['erros']}✗\n"
                          f"💎 {mensagem}")
            
        elif estado == "enfraquecendo":
            # ⚠️ TENDÊNCIA ENFRAQUECENDO - CUIDADO
            enviar_telegram(f"⚠️ TENDÊNCIA ENFRAQUECENDO - SISTEMA MÉDIO\n"
                          f"📍 Zona: {zona}\n"
                          f"📈 Estado: {estado}\n"
                          f"💡 Ação: AGUARDAR\n"
                          f"📊 {mensagem}")
            
        elif estado == "morta":
            # 🟥 TENDÊNCIA MORTA - PARAR
            enviar_telegram(f"🟥 TENDÊNCIA MORTA - SISTEMA MÉDIO\n"
                          f"📈 Estado: {estado}\n"
                          f"💡 Ação: PARAR\n"
                          f"📊 {mensagem}")

    def selecionar_estrategia_inteligente(self, historico):
        """Seleciona a melhor estratégia baseada no desempenho recente"""
        try:
            # Se temos menos de 20 sorteios, usar Zonas como padrão
            if len(historico) < 20:
                return 'Zonas'
            
            # Analisar tendências primeiro
            zonas_rankeadas = self.estrategia_zonas.analisar_desempenho_zonas()
            analise_tendencia = self.sistema_tendencias.analisar_tendencia(zonas_rankeadas)
            
            # Se tendência ativa, priorizar Zonas
            if analise_tendencia['estado'] == 'ativa' and analise_tendencia['acao'] == 'operar':
                self.enviar_notificacoes_tendencia(analise_tendencia)
                return 'Zonas'
            
            # Verificar sequência de erros para rotação
            if self.sequencia_erros >= 3:
                estrategia_anterior = self.estrategia_selecionada
                
                # Rotação cíclica entre estratégias
                if self.estrategia_selecionada == 'Zonas':
                    nova_estrategia = 'Machine Learning'
                elif self.estrategia_selecionada == 'Machine Learning':
                    nova_estrategia = 'Midas'
                else:
                    nova_estrategia = 'Zonas'
                
                self.sequencia_erros = 0
                self.estrategia_selecionada = nova_estrategia
                
                # Enviar notificação de rotação
                enviar_rotacao_automatica(estrategia_anterior, nova_estrategia)
                return nova_estrategia
            
            # Sistema de 3 acertos para combinações (Zonas)
            if (self.estrategia_selecionada == 'Zonas' and 
                self.sequencia_acertos >= 3 and
                len(self.ultima_combinacao_acerto) > 0):
                
                combinacao_anterior = self.ultima_combinacao_acerto.copy()
                
                # Alternar para próxima combinação quente
                if self.combinacoes_quentes:
                    proxima_combinacao = None
                    for combo in self.combinacoes_quentes:
                        if combo != tuple(combinacao_anterior):
                            proxima_combinacao = list(combo)
                            break
                    
                    if proxima_combinacao:
                        self.ultima_combinacao_acerto = proxima_combinacao
                        self.sequencia_acertos = 0
                        
                        # Enviar notificação de rotação por acertos
                        enviar_rotacao_por_acertos_combinacoes(combinacao_anterior, proxima_combinacao)
            
            return self.estrategia_selecionada
            
        except Exception as e:
            logging.error(f"❌ Erro na seleção inteligente: {e}")
            return 'Zonas'

    def gerar_previsao(self, historico):
        """Gera previsão usando a estratégia selecionada"""
        try:
            # Selecionar estratégia inteligente
            estrategia = self.selecionar_estrategia_inteligente(historico)
            self.estrategia_selecionada = estrategia
            
            # Gerar previsão baseada na estratégia
            if estrategia == 'Zonas':
                previsao = self.estrategia_zonas.gerar_previsao(historico)
            elif estrategia == 'Machine Learning':
                previsao = self.estrategia_ml.gerar_previsao(historico)
            elif estrategia == 'Midas':
                previsao = self.estrategia_midas.gerar_previsao(historico)
            else:
                previsao = self.estrategia_zonas.gerar_previsao(historico)
            
            # Registrar uso da estratégia
            if estrategia in self.estrategias_contador:
                self.estrategias_contador[estrategia] += 1
            else:
                self.estrategias_contador[estrategia] = 1
            
            return previsao
            
        except Exception as e:
            logging.error(f"❌ Erro ao gerar previsão: {e}")
            return {
                'nome': 'Sistema',
                'numeros_apostar': [],
                'confianca': 'Baixa',
                'mensagem': f'Erro no sistema: {str(e)}'
            }

    def processar_resultado(self, numero_sorteado, previsao):
        """Processa o resultado do sorteio e atualiza estatísticas"""
        try:
            # Verificar acerto
            acerto = numero_sorteado in previsao['numeros_apostar']
            
            # Atualizar contadores gerais
            if acerto:
                self.acertos += 1
                self.sequencia_erros = 0
                self.sequencia_acertos += 1
            else:
                self.erros += 1
                self.sequencia_erros += 1
                self.sequencia_acertos = 0
                self.ultima_estrategia_erro = previsao['nome']
            
            # Atualizar estratégia específica
            if 'Zonas' in previsao['nome']:
                zona_acertada = None
                if acerto:
                    zona_acertada = self.estrategia_zonas.identificar_zona(numero_sorteado)
                self.estrategia_zonas.processar_resultado(numero_sorteado, previsao, acerto)
                
                # Atualizar sistema de tendências
                zonas_rankeadas = self.estrategia_zonas.analisar_desempenho_zonas()
                self.sistema_tendencias.analisar_tendencia(zonas_rankeadas, acerto, zona_acertada)
                
            elif 'Machine Learning' in previsao['nome']:
                self.estrategia_ml.processar_resultado(numero_sorteado, previsao, acerto)
            elif 'Midas' in previsao['nome']:
                self.estrategia_midas.processar_resultado(numero_sorteado, previsao, acerto)
            
            # Atualizar histórico de desempenho
            self.historico_desempenho.append({
                'numero_sorteado': numero_sorteado,
                'previsao': previsao,
                'acerto': acerto,
                'estrategia': previsao['nome'],
                'timestamp': datetime.now()
            })
            
            self.contador_sorteios_global += 1
            
            return acerto
            
        except Exception as e:
            logging.error(f"❌ Erro ao processar resultado: {e}")
            return False

    def get_estatisticas(self):
        """Retorna estatísticas completas do sistema"""
        total_tentativas = self.acertos + self.erros
        eficiencia = (self.acertos / total_tentativas * 100) if total_tentativas > 0 else 0
        
        estatisticas = {
            'acertos': self.acertos,
            'erros': self.erros,
            'eficiencia_geral': eficiencia,
            'total_tentativas': total_tentativas,
            'sequencia_erros_atual': self.sequencia_erros,
            'sequencia_acertos_atual': self.sequencia_acertos,
            'estrategia_atual': self.estrategia_selecionada,
            'contador_sorteios': self.contador_sorteios_global,
            'uso_estrategias': self.estrategias_contador
        }
        
        return estatisticas

# =============================
# FUNÇÃO PRINCIPAL DO STREAMLIT
# =============================
def main():
    st.set_page_config(
        page_title="Sistema de Roleta Inteligente - MÉDIO/EQUILIBRADO",
        page_icon="🎰",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializar sessão
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaRoletaCompleto()
        st.session_state.historico = deque(maxlen=1000)
        st.session_state.telegram_token = ''
        st.session_state.telegram_chat_id = ''
        
        # Tentar carregar sessão anterior
        carregar_sessao()
    
    # Auto-refresh a cada 30 segundos
    st_autorefresh(interval=30000, key="auto_refresh")
    
    # Header
    st.title("🎰 Sistema de Roleta Inteligente - MÉDIO/EQUILIBRADO")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Configurações do Telegram
        st.subheader("🔔 Notificações Telegram")
        st.session_state.telegram_token = st.text_input("Token do Bot Telegram", 
                                                       value=st.session_state.telegram_token,
                                                       type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", 
                                                         value=st.session_state.telegram_chat_id)
        
        # Gerenciamento de sessão
        st.subheader("💾 Gerenciamento de Sessão")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Salvar Sessão", use_container_width=True):
                if salvar_sessao():
                    st.success("Sessão salva!")
                else:
                    st.error("Erro ao salvar sessão")
        
        with col2:
            if st.button("🗑️ Limpar Sessão", use_container_width=True):
                limpar_sessao()
        
        if st.button("🔄 Carregar Sessão", use_container_width=True):
            if carregar_sessao():
                st.success("Sessão carregada!")
            else:
                st.error("Erro ao carregar sessão")
        
        # Backup automático
        if st.button("📦 Criar Backup", use_container_width=True):
            criar_backup_automatico()
            st.success("Backup criado!")
        
        st.markdown("---")
        
        # Estatísticas rápidas
        st.subheader("📊 Estatísticas Rápidas")
        stats = st.session_state.sistema.get_estatisticas()
        st.metric("Acertos", stats['acertos'])
        st.metric("Erros", stats['erros'])
        st.metric("Eficiência", f"{stats['eficiencia_geral']:.1f}%")
        st.metric("Estratégia Atual", stats['estrategia_atual'])
    
    # Layout principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎯 Sistema de Previsão")
        
        # Entrada manual de números
        st.subheader("🔢 Entrada de Números")
        col_a, col_b = st.columns([3, 1])
        
        with col_a:
            numero_input = st.number_input("Número Sorteado (0-36)", 
                                         min_value=0, max_value=36, value=0)
        
        with col_b:
            st.write("")
            st.write("")
            if st.button("🎲 Processar Sorteio", use_container_width=True):
                if numero_input is not None:
                    # Gerar previsão
                    previsao = st.session_state.sistema.gerar_previsao(st.session_state.historico)
                    
                    # Processar resultado
                    acerto = st.session_state.sistema.processar_resultado(numero_input, previsao)
                    
                    # Adicionar ao histórico
                    st.session_state.historico.append(numero_input)
                    
                    # Enviar notificações
                    zona_acertada = None
                    if 'Zonas' in previsao['nome'] and acerto:
                        zona_acertada = st.session_state.sistema.estrategia_zonas.identificar_zona(numero_input)
                    
                    enviar_previsao_super_simplificada(previsao)
                    enviar_resultado_super_simplificada(numero_input, acerto, previsao['nome'], zona_acertada)
                    
                    # Salvar sessão
                    salvar_sessao()
                    
                    st.rerun()
        
        # Exibir previsão atual
        if st.session_state.historico:
            st.subheader("📈 Previsão Atual")
            previsao_atual = st.session_state.sistema.gerar_previsao(st.session_state.historico)
            
            if previsao_atual['numeros_apostar']:
                st.success(f"**Estratégia:** {previsao_atual['nome']}")
                st.info(f"**Confiança:** {previsao_atual['confianca']}")
                
                # Mostrar números para apostar
                numeros_ordenados = sorted(previsao_atual['numeros_apostar'])
                st.write(f"**🎯 Números para Apostar ({len(numeros_ordenados)}):**")
                
                # Dividir em duas colunas para melhor visualização
                col_n1, col_n2 = st.columns(2)
                metade = len(numeros_ordenados) // 2
                
                with col_n1:
                    for num in numeros_ordenados[:metade]:
                        st.write(f"- {num}")
                
                with col_n2:
                    for num in numeros_ordenados[metade:]:
                        st.write(f"- {num}")
                
                if 'mensagem' in previsao_atual:
                    st.write(f"**💡 Detalhes:** {previsao_atual['mensagem']}")
            else:
                st.warning("Nenhuma previsão disponível no momento")
        
        # Histórico recente
        if st.session_state.historico:
            st.subheader("📋 Histórico Recente")
            historico_recente = list(st.session_state.historico)[-20:]
            st.write(f"Últimos {len(historico_recente)} números: {historico_recente}")
    
    with col2:
        st.header("📊 Análises")
        
        # Sistema de Tendências
        st.subheader("🎯 Sistema de Tendências - MÉDIO")
        analise_tendencias = st.session_state.sistema.get_analise_tendencias_completa()
        st.text_area("Análise de Tendências", analise_tendencias, height=400)
        
        # Estatísticas das estratégias
        st.subheader("📈 Estatísticas por Estratégia")
        stats = st.session_state.sistema.get_estatisticas()
        
        for estrategia, count in stats['uso_estrategias'].items():
            st.write(f"**{estrategia}:** {count} usos")
        
        # Estatísticas das zonas
        st.subheader("🎨 Desempenho das Zonas")
        zonas_rankeadas = st.session_state.sistema.estrategia_zonas.analisar_desempenho_zonas()
        
        for zona, score in zonas_rankeadas:
            stats_zona = st.session_state.sistema.estrategia_zonas.stats_zonas[zona]
            eficiencia = (stats_zona['acertos'] / stats_zona['tentativas'] * 100) if stats_zona['tentativas'] > 0 else 0
            st.write(f"**{zona}:** {eficiencia:.1f}% (Score: {score:.1f})")

if __name__ == "__main__":
    main()
