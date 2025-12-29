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
import warnings
warnings.filterwarnings('ignore')

# =============================
# CONFIGURAÇÕES DE LOGGING
# =============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"
ML_MODEL_PATH = "ml_roleta_model.pkl"
SCALER_PATH = "ml_scaler.pkl"
META_PATH = "ml_meta.pkl"

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO - CHECKBOXES
# =============================
def inicializar_config_alertas():
    """Inicializa configurações de alertas se não existirem"""
    if 'alertas_config' not in st.session_state:
        st.session_state.alertas_config = {
            'alertas_previsao': True,
            'alertas_resultado': True,
            'alertas_rotacao': True,
            'alertas_tendencia': True,
            'alertas_treinamento': True,
            'alertas_erros': True,
            'alertas_acertos': True
        }

# Chama a função na inicialização
inicializar_config_alertas()

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        if 'sistema' not in st.session_state:
            logging.warning("❌ Sistema não está na sessão")
            return False
            
        sistema = st.session_state.sistema
        
        # Coletar dados basicos primeiro
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'alertas_config': st.session_state.get('alertas_config', {
                'alertas_previsao': True,
                'alertas_resultado': True,
                'alertas_rotacao': True,
                'alertas_tendencia': True,
                'alertas_treinamento': True,
                'alertas_erros': True,
                'alertas_acertos': True
            }),
            'sistema_acertos': sistema.acertos,
            'sistema_erros': sistema.erros,
            'sistema_estrategias_contador': sistema.estrategias_contador,
            'sistema_historico_desempenho': sistema.historico_desempenho,
            'sistema_contador_sorteios_global': sistema.contador_sorteios_global,
            'sistema_sequencia_erros': sistema.sequencia_erros,
            'sistema_ultima_estrategia_erro': sistema.ultima_estrategia_erro,
            'sistema_sequencia_acertos': sistema.sequencia_acertos,
            'sistema_ultima_combinacao_acerto': sistema.ultima_combinacao_acerto,
            'sistema_historico_combinacoes_acerto': sistema.historico_combinacoes_acerto,
            'estrategia_selecionada': sistema.estrategia_selecionada,
            'sistema_historico_combinacoes': sistema.historico_combinacoes,
            'sistema_combinacoes_quentes': sistema.combinacoes_quentes,
            'sistema_combinacoes_frias': sistema.combinacoes_frias,
            'sistema_contador_otimizacoes_aplicadas': sistema.contador_otimizacoes_aplicadas if hasattr(sistema, 'contador_otimizacoes_aplicadas') else 0,
        }
        
        # Adicionar dados da estratégia Zonas se existir
        if hasattr(sistema, 'estrategia_zonas'):
            session_data['zonas_historico'] = list(sistema.estrategia_zonas.historico)
            session_data['zonas_stats'] = sistema.estrategia_zonas.stats_zonas
            
        if hasattr(sistema, 'sistema_tendencias'):
            session_data['sistema_tendencias_historico'] = list(sistema.sistema_tendencias.historico_tendencias)
            session_data['sistema_tendencias_estado'] = sistema.sistema_tendencias.estado_tendencia
            session_data['sistema_tendencias_ativa'] = sistema.sistema_tendencias.tendencia_ativa
            session_data['sistema_tendencias_confirmacoes'] = sistema.sistema_tendencias.contador_confirmacoes
            session_data['sistema_tendencias_acertos'] = sistema.sistema_tendencias.contador_acertos_tendencia
            session_data['sistema_tendencias_erros'] = sistema.sistema_tendencias.contador_erros_tendencia
            session_data['sistema_tendencias_operacoes'] = sistema.sistema_tendencias.rodadas_operando
            session_data['sistema_tendencias_historico_zonas'] = list(sistema.sistema_tendencias.historico_zonas_dominantes)
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        logging.info(f"✅ Sessão salva com {len(session_data)} itens")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}", exc_info=True)
        return False

def carregar_sessao():
    """Carrega todos os dados da sessão do arquivo"""
    try:
        if not os.path.exists(SESSION_DATA_PATH):
            logging.info("ℹ️  Nenhuma sessão salva encontrada")
            return False
            
        with open(SESSION_DATA_PATH, 'rb') as f:
            session_data = pickle.load(f)
        
        if not isinstance(session_data, dict):
            logging.error("❌ Dados de sessão corrompidos")
            return False
            
        # Inicializar config de alertas primeiro
        inicializar_config_alertas()
        
        # Carregar dados básicos
        st.session_state.historico = session_data.get('historico', [])
        st.session_state.telegram_token = session_data.get('telegram_token', '')
        st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
        
        # Carregar configurações de alertas (se existirem)
        if 'alertas_config' in session_data:
            st.session_state.alertas_config = session_data['alertas_config']
        
        if 'sistema' not in st.session_state:
            st.session_state.sistema = SistemaRoletaCompleto()
            
        sistema = st.session_state.sistema
        
        # Carregar dados do sistema
        sistema.acertos = session_data.get('sistema_acertos', 0)
        sistema.erros = session_data.get('sistema_erros', 0)
        sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
        sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
        sistema.contador_sorteios_global = session_data.get('sistema_contador_sorteios_global', 0)
        sistema.sequencia_erros = session_data.get('sistema_sequencia_erros', 0)
        sistema.ultima_estrategia_erro = session_data.get('sistema_ultima_estrategia_erro', '')
        sistema.sequencia_acertos = session_data.get('sistema_sequencia_acertos', 0)
        sistema.ultima_combinacao_acerto = session_data.get('sistema_ultima_combinacao_acerto', [])
        sistema.historico_combinacoes_acerto = session_data.get('sistema_historico_combinacoes_acerto', [])
        sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Zonas')
        sistema.historico_combinacoes = session_data.get('sistema_historico_combinacoes', {})
        sistema.combinacoes_quentes = session_data.get('sistema_combinacoes_quentes', [])
        sistema.combinacoes_frias = session_data.get('sistema_combinacoes_frias', [])
        sistema.contador_otimizacoes_aplicadas = session_data.get('sistema_contador_otimizacoes_aplicadas', 0)
        
        # Carregar dados da estratégia Zonas
        if hasattr(sistema, 'estrategia_zonas'):
            zonas_historico = session_data.get('zonas_historico', [])
            sistema.estrategia_zonas.historico = deque(zonas_historico, maxlen=70)
            sistema.estrategia_zonas.stats_zonas = session_data.get('zonas_stats', {
                'Vermelha': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                'Azul': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                'Amarela': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
            })
            
            # Reconstruir números das zonas
            for zona, central in sistema.estrategia_zonas.zonas.items():
                qtd = sistema.estrategia_zonas.quantidade_zonas.get(zona, 6)
                sistema.estrategia_zonas.numeros_zonas[zona] = sistema.estrategia_zonas.roleta.get_vizinhos_zona(central, qtd)
        
        if hasattr(sistema, 'sistema_tendencias'):
            tendencias_historico = session_data.get('sistema_tendencias_historico', [])
            sistema.sistema_tendencias.historico_tendencias = deque(tendencias_historico, maxlen=50)
            sistema.sistema_tendencias.estado_tendencia = session_data.get('sistema_tendencias_estado', 'aguardando')
            sistema.sistema_tendencias.tendencia_ativa = session_data.get('sistema_tendencias_ativa', None)
            sistema.sistema_tendencias.contador_confirmacoes = session_data.get('sistema_tendencias_confirmacoes', 0)
            sistema.sistema_tendencias.contador_acertos_tendencia = session_data.get('sistema_tendencias_acertos', 0)
            sistema.sistema_tendencias.contador_erros_tendencia = session_data.get('sistema_tendencias_erros', 0)
            sistema.sistema_tendencias.rodadas_operando = session_data.get('sistema_tendencias_operacoes', 0)
            
            tendencias_historico_zonas = session_data.get('sistema_tendencias_historico_zonas', [])
            sistema.sistema_tendencias.historico_zonas_dominantes = deque(tendencias_historico_zonas, maxlen=10)
        
        logging.info(f"✅ Sessão carregada: {sistema.acertos} acertos, {sistema.erros} erros")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}", exc_info=True)
        return False

def limpar_sessao():
    """Limpa todos os dados da sessão"""
    try:
        arquivos = [SESSION_DATA_PATH, HISTORICO_PATH, ML_MODEL_PATH, SCALER_PATH, META_PATH]
        for arquivo in arquivos:
            if os.path.exists(arquivo):
                os.remove(arquivo)
                logging.info(f"🗑️ Removido: {arquivo}")
        
        # Limpar session state
        chaves = list(st.session_state.keys())
        for chave in chaves:
            del st.session_state[chave]
            
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
        # Verificar se alertas de previsão estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_previsao', True):
                return
        
        if not previsao:
            return
            
        nome_estrategia = previsao.get('nome', 'Desconhecida')
        numeros_apostar = previsao.get('numeros_apostar', [])
        
        if not numeros_apostar:
            logging.warning("⚠️ Previsão sem números para apostar")
            return
        
        numeros_apostar = sorted(numeros_apostar)
        
        if 'Zonas' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            confianca = previsao.get('confianca', 'Média')
            
            if len(zonas_envolvidas) > 1:
                nucleo1 = "7" if zonas_envolvidas[0] == 'Vermelha' else "10" if zonas_envolvidas[0] == 'Azul' else "2"
                nucleo2 = "7" if zonas_envolvidas[1] == 'Vermelha' else "10" if zonas_envolvidas[1] == 'Azul' else "2"
                mensagem = f"🔥 NÚCLEOS {nucleo1}+{nucleo2} - CONFIANÇA {confianca.upper()}"
                
                if 'sistema' in st.session_state:
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
            
        else:
            mensagem = f"💰 {nome_estrategia} - APOSTAR AGORA"
        
        st.toast(f"🎯 PREVISÃO CONFIRMADA", icon="🔥")
        st.warning(f"🔔 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_previsao', True)):
                enviar_alerta_numeros_simplificado(previsao)
                enviar_telegram(f"🚨 PREVISÃO ATIVA\n{mensagem}\n💎 CONFIANÇA: {previsao.get('confianca', 'ALTA')}")
                
        salvar_sessao()
        
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_alerta_numeros_simplificado(previsao):
    """Envia alerta alternativo super simplificado com os números para apostar"""
    try:
        if not previsao:
            return
            
        nome_estrategia = previsao.get('nome', '')
        numeros_apostar = previsao.get('numeros_apostar', [])
        
        if not numeros_apostar:
            return
            
        numeros_apostar = sorted(numeros_apostar)
        
        metade = len(numeros_apostar) // 2
        linha1 = " ".join(map(str, numeros_apostar[:metade]))
        linha2 = " ".join(map(str, numeros_apostar[metade:]))
        
        if 'Zonas' in nome_estrategia:
            emoji = "🔥"
        else:
            emoji = "💰"
            
        mensagem_simplificada = f"{emoji} APOSTAR AGORA\n{linha1}\n{linha2}"
        
        enviar_telegram(mensagem_simplificada)
        logging.info("🔔 Alerta simplificado enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta simplificado: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    """Envia notificação de resultado super simplificada"""
    try:
        # Verificar se alertas de resultado estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_resultado', True):
                return
        
        # Verificar se alertas específicos por tipo estão ativados
        if acerto and not st.session_state.alertas_config.get('alertas_acertos', True):
            return
        if not acerto and not st.session_state.alertas_config.get('alertas_erros', True):
            return
            
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
            else:
                mensagem = f"✅ Acerto\n🎲 Número: {numero_real}"
        else:
            mensagem = f"❌ Erro\n🎲 Número: {numero_real}"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        
        if acerto:
            st.success(f"📢 {mensagem}")
        else:
            st.error(f"📢 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state):
                
                # Verificar se alertas de resultado estão ativados
                if st.session_state.alertas_config.get('alertas_resultado', True):
                    # Verificar se alertas específicos por tipo estão ativados
                    if (acerto and st.session_state.alertas_config.get('alertas_acertos', True)) or \
                       (not acerto and st.session_state.alertas_config.get('alertas_erros', True)):
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
        # Verificar se alertas de rotação estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_rotacao', True):
                return
                
        mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(f"🔄 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_rotacao', True)):
                enviar_telegram(f"🔄 ROTAÇÃO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

def enviar_rotacao_por_acertos_combinacoes(combinacao_anterior, combinacao_nova):
    """Envia notificação de rotação por acertos em combinações"""
    try:
        # Verificar se alertas de rotação estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_rotacao', True):
                return
                
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
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_rotacao', True)):
                enviar_telegram(f"🎯 ROTAÇÃO POR ACERTOS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação por acertos: {e}")

def enviar_rotacao_por_2_erros(combinacao_antiga, combinacao_nova):
    """Envia notificação de rotação por 2 erros seguidos"""
    try:
        # Verificar se alertas de rotação estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_rotacao', True):
                return
                
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
        
        nucleo_antigo = combo_para_nucleos(combinacao_antiga)
        nucleo_novo = combo_para_nucleos(combinacao_nova)
        
        mensagem = f"🚨 ROTAÇÃO POR 2 ERROS SEGUIDOS\nNúcleos {nucleo_antigo} → Núcleos {nucleo_novo}\n⚠️ 2 erros consecutivos - Mudando de combinação"
        
        st.toast("🚨 Rotação por 2 Erros", icon="⚠️")
        st.warning(f"🚨 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_rotacao', True)):
                enviar_telegram(f"🚨 ROTAÇÃO POR 2 ERROS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação por 2 erros: {e}")

def enviar_alerta_tendencia(analise_tendencia):
    """Envia alerta de tendência na interface"""
    estado = analise_tendencia['estado']
    zona = analise_tendencia['zona_dominante']
    mensagem = analise_tendencia['mensagem']
    
    # Verificar se alertas de tendência estão ativados
    if 'alertas_config' in st.session_state:
        if not st.session_state.alertas_config.get('alertas_tendencia', True):
            return
    
    if estado == "ativa" and analise_tendencia['acao'] == "operar":
        st.toast("🎯 TENDÊNCIA CONFIRMADA - OPERAR!", icon="🔥")
        st.success(f"📈 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_tendencia', True)):
                enviar_telegram(f"🎯 TENDÊNCIA CONFIRMADA\n📍 Zona: {zona}\n📈 Estado: {estado}\n💡 Ação: OPERAR\n📊 {mensagem}")
        
    elif estado == "enfraquecendo":
        st.toast("⚠️ TENDÊNCIA ENFRAQUECENDO", icon="⚠️")
        st.warning(f"📉 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_tendencia', True)):
                enviar_telegram(f"⚠️ TENDÊNCIA ENFRAQUECENDO\n📍 Zona: {zona}\n📈 Estado: {estado}\n💡 Ação: AGUARDAR\n📊 {mensagem}")
        
    elif estado == "morta":
        st.toast("🟥 TENDÊNCIA MORTA - PARAR", icon="🛑")
        st.error(f"💀 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_tendencia', True)):
                enviar_telegram(f"🟥 TENDÊNCIA MORTA\n📈 Estado: {estado}\n💡 Ação: PARAR\n📊 {mensagem}")

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    try:
        if 'telegram_token' not in st.session_state or 'telegram_chat_id' not in st.session_state:
            return
            
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        
        if not token or not chat_id:
            return
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info("✅ Mensagem enviada para Telegram com sucesso")
        else:
            logging.error(f"❌ Erro ao enviar para Telegram: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Erro na conexão com Telegram: {e}")

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
        self.ultima_zona_dominante = None
        self.historico_zonas_dominantes = deque(maxlen=10)
        self.rodadas_operando = 0
        self.max_operacoes_por_tendencia = 4
        
    def analisar_tendencia(self, zonas_rankeadas, acerto_ultima=False, zona_acertada=None):
        """
        Analisa a tendência atual baseado no fluxograma
        """
        if not zonas_rankeadas or len(zonas_rankeadas) < 2:
            return self._criar_resposta_tendencia("aguardando", None, "Aguardando dados suficientes")
        
        try:
            zona_top1, score_top1 = zonas_rankeadas[0]
            zona_top2, score_top2 = zonas_rankeadas[1] if len(zonas_rankeadas) > 1 else (None, 0)
            
            # Registrar zona dominante atual
            if zona_top1:
                self.historico_zonas_dominantes.append(zona_top1)
            
            # Analisar estado atual
            if self.estado_tendencia in ["aguardando", "formando"]:
                return self._analisar_formacao_tendencia(zona_top1, zona_top2, score_top1, zonas_rankeadas)
            
            elif self.estado_tendencia == "ativa":
                return self._analisar_tendencia_ativa(zona_top1, zona_top2, acerto_ultima, zona_acertada)
            
            elif self.estado_tendencia == "enfraquecendo":
                return self._analisar_tendencia_enfraquecendo(zona_top1, zona_top2, acerto_ultima, zona_acertada)
            
            elif self.estado_tendencia == "morta":
                return self._analisar_reinicio_tendencia(zona_top1, zonas_rankeadas)
            
        except Exception as e:
            logging.error(f"Erro na análise de tendência: {e}")
            
        return self._criar_resposta_tendencia("aguardando", None, "Estado não reconhecido")
    
    def _analisar_formacao_tendencia(self, zona_top1, zona_top2, score_top1, zonas_rankeadas):
        """Etapa 2 do fluxograma - Formação da Tendência"""
        
        if not zona_top1:
            return self._criar_resposta_tendencia("aguardando", None, "Sem zona dominante")
        
        # Verificar se a mesma zona aparece repetidamente
        freq_zona_top1 = list(self.historico_zonas_dominantes).count(zona_top1)
        frequencia_minima = 3 if len(self.historico_zonas_dominantes) >= 5 else 2
        
        # Verificar dispersão
        dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
        
        if (freq_zona_top1 >= frequencia_minima and 
            score_top1 >= 25 and
            dispersao <= 0.6):
            
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
        
        if not self.tendencia_ativa:
            return self._criar_resposta_tendencia("aguardando", None, "Sem tendência ativa")
        
        # Verificar se ainda é a mesma zona dominante
        mesma_zona = zona_top1 == self.tendencia_ativa
        
        # Atualizar contadores
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        self.rodadas_operando += 1
        
        # HORA DE OPERAR
        if (self.contador_acertos_tendencia >= 1 and 
            self.contador_erros_tendencia == 0 and
            self.rodadas_operando <= self.max_operacoes_por_tendencia):
            
            acao = "operar" if mesma_zona else "aguardar"
            mensagem = f"🔥 OPERAR - Tendência {self.tendencia_ativa} forte ({self.contador_acertos_tendencia} acertos)"
            
            return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, mensagem, acao)
        
        # VERIFICAR ENFRAQUECIMENTO
        sinais_enfraquecimento = self._detectar_enfraquecimento(zona_top1, zona_top2, acerto_ultima)
        
        if sinais_enfraquecimento:
            self.estado_tendencia = "enfraquecendo"
            return self._criar_resposta_tendencia(
                "enfraquecendo", self.tendencia_ativa,
                f"⚠️ Tendência enfraquecendo - {sinais_enfraquecimento}"
            )
        
        # VERIFICAR SE TENDÊNCIA MORREU
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
        
        # VERIFICAR MORTE DEFINITIVA
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
        
        if rodadas_desde_morte >= 8:
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
        
        if not self.tendencia_ativa:
            return None
        
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
        
        if not self.tendencia_ativa:
            return True
        
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
            if taxa_acertos < 0.5:
                return True
        
        return False
    
    def _calcular_dispersao_zonas(self, zonas_rankeadas):
        """Calcula o nível de dispersão entre as zonas"""
        if not zonas_rankeadas:
            return 1.0
        
        scores = [score for _, score in zonas_rankeadas[:4]]
        if not scores:
            return 1.0
        
        max_score = max(scores)
        if max_score == 0:
            return 1.0
        
        try:
            scores_normalizados = [score / max_score for score in scores]
            dispersao = np.std(scores_normalizados) if len(scores_normalizados) > 1 else 0
            return float(dispersao)
        except:
            return 1.0
    
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
    
    def enviar_notificacoes_tendencia(self, analise_tendencia):
        estado = analise_tendencia['estado']
        mensagem = analise_tendencia['mensagem']
        zona = analise_tendencia['zona_dominante']
        
        # Verificar configurações de alertas
        if 'alertas_config' not in st.session_state:
            return
        
        alertas_config = st.session_state.alertas_config
        
        # Verificar se alertas de tendência estão ativados
        if not alertas_config.get('alertas_tendencia', True):
            return
        
        if estado == "ativa" and analise_tendencia['acao'] == "operar":
            # Verificar se alertas do Telegram estão configurados e ativados
            if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    enviar_telegram(f"🎯 TENDÊNCIA CONFIRMADA\n"
                                  f"📍 Zona: {zona}\n"
                                  f"📈 Estado: {estado}\n"
                                  f"💡 Ação: OPERAR\n"
                                  f"📊 {mensagem}")
            
        elif estado == "enfraquecendo":
            if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    enviar_telegram(f"⚠️ TENDÊNCIA ENFRAQUECENDO\n"
                                  f"📍 Zona: {zona}\n"
                                  f"📈 Estado: {estado}\n"
                                  f"💡 Ação: AGUARDAR\n"
                                  f"📊 {mensagem}")
            
        elif estado == "morta":
            if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    enviar_telegram(f"🟥 TENDÊNCIA MORTA\n"
                                  f"📈 Estado: {estado}\n"
                                  f"💡 Ação: PARAR\n"
                                  f"📊 {mensagem}")

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
        
    def selecionar_melhores_10_numeros(self, numeros_candidatos, historico, estrategia_tipo="Zonas"):
        if len(numeros_candidatos) <= 10:
            return numeros_candidatos
            
        scores = {}
        for numero in numeros_candidatos:
            scores[numero] = self.calcular_score_numero(numero, historico, estrategia_tipo)
        
        numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhores_10 = [num for num, score in numeros_ordenados[:10]]
        
        logging.info(f"🎯 Seleção Inteligente: {len(numeros_candidatos)} → 10 números")
        return melhores_10
    
    def calcular_score_numero(self, numero, historico, estrategia_tipo):
        try:
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
            
        except Exception as e:
            logging.error(f"Erro ao calcular score: {e}")
            return 0.5
    
    def calcular_score_frequencia(self, numero, historico):
        if len(historico) < 3:
            return 0.7
        
        try:
            historico_lista = list(historico)
            
            janela_curta = historico_lista[-8:] if len(historico_lista) >= 8 else historico_lista
            freq_curta = sum(1 for n in janela_curta if n == numero) / len(janela_curta)
            
            janela_media = historico_lista[-20:] if len(historico_lista) >= 20 else historico_lista
            freq_media = sum(1 for n in janela_media if n == numero) / len(janela_media)
            
            janela_longa = historico_lista[-40:] if len(historico_lista) >= 40 else historico_lista
            freq_longa = sum(1 for n in janela_longa if n == numero) / len(janela_longa)
            
            score = (freq_curta * 0.7 + freq_media * 0.2 + freq_longa * 0.1)
            return min(score * 4, 1.0)
            
        except Exception as e:
            logging.error(f"Erro no cálculo de frequência: {e}")
            return 0.5
    
    def calcular_score_posicao_roda(self, numero, historico):
        if len(historico) < 3:
            return 0.5
        
        try:
            ultimo_numero = historico[-1] if historico else 0
            penultimo_numero = historico[-2] if len(historico) >= 2 else ultimo_numero
            
            posicao_alvo = self.roleta.get_posicao_race(numero)
            posicao_ultimo = self.roleta.get_posicao_race(ultimo_numero)
            posicao_penultimo = self.roleta.get_posicao_race(penultimo_numero)
            
            if posicao_alvo == -1 or posicao_ultimo == -1 or posicao_penultimo == -1:
                return 0.5
            
            dist_ultimo = self.calcular_distancia_roda(posicao_alvo, posicao_ultimo)
            score_dist_ultimo = max(0, 1 - (dist_ultimo / 18))
            
            dist_penultimo = self.calcular_distancia_roda(posicao_alvo, posicao_penultimo)
            score_dist_penultimo = max(0, 1 - (dist_penultimo / 18))
            
            score_final = (score_dist_ultimo * 0.7 + score_dist_penultimo * 0.3)
            return score_final
            
        except Exception as e:
            logging.error(f"Erro no cálculo de posição: {e}")
            return 0.5
    
    def calcular_distancia_roda(self, pos1, pos2):
        total_posicoes = 37
        distancia_direta = abs(pos1 - pos2)
        distancia_inversa = total_posicoes - distancia_direta
        return min(distancia_direta, distancia_inversa)
    
    def calcular_score_vizinhos(self, numero, historico):
        if len(historico) < 5:
            return 0.5
        
        try:
            vizinhos = self.roleta.get_vizinhos_fisicos(numero, raio=3)
            ultimos_15 = list(historico)[-15:] if len(historico) >= 15 else list(historico)
            count_vizinhos_recentes = sum(1 for n in ultimos_15 if n in vizinhos)
            
            if len(ultimos_15) == 0:
                return 0.5
                
            score = min(count_vizinhos_recentes / len(ultimos_15) * 2, 1.0)
            return score
            
        except Exception as e:
            logging.error(f"Erro no cálculo de vizinhos: {e}")
            return 0.5
    
    def calcular_score_tendencia(self, numero, historico):
        if len(historico) < 10:
            return 0.5
        
        try:
            historico_lista = list(historico)
            
            segmento_recente = historico_lista[-5:]
            segmento_anterior = historico_lista[-10:-5] if len(historico_lista) >= 10 else historico_lista[:5]
            
            if len(segmento_recente) == 0:
                return 0.5
                
            freq_recente = sum(1 for n in segmento_recente if n == numero) / len(segmento_recente)
            
            if len(segmento_anterior) == 0:
                freq_anterior = 0
            else:
                freq_anterior = sum(1 for n in segmento_anterior if n == numero) / len(segmento_anterior)
            
            if freq_anterior == 0:
                tendencia = 1.0 if freq_recente > 0 else 0.5
            else:
                tendencia = min(freq_recente / freq_anterior, 2.0)
                
            return tendencia * 0.5
            
        except Exception as e:
            logging.error(f"Erro no cálculo de tendência: {e}")
            return 0.5

    def get_analise_selecao(self, numeros_originais, numeros_selecionados, historico):
        analise = f"🎯 ANÁLISE DA SELEÇÃO INTELIGENTE\n"
        analise += f"📊 Redução: {len(numeros_originais)} → {len(numeros_selecionados)} números\n"
        analise += f"🎲 Números selecionados: {sorted(numeros_selecionados)}\n"
        
        if historico:
            ultimos_20 = list(historico)[-20:] if len(historico) >= 20 else list(historico)
            if ultimos_20:
                acertos_potenciais = sum(1 for n in ultimos_20 if n in numeros_selecionados)
                analise += f"📈 Eficiência teórica: {acertos_potenciais}/20 ({acertos_potenciais/len(ultimos_20)*100:.1f}%)\n"
        
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
        
        for offset in range(-quantidade, quantidade + 1):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        return list(set(vizinhos))  # Remover duplicatas

    def get_posicao_race(self, numero):
        try:
            if numero in self.race:
                return self.race.index(numero)
            return -1
        except:
            return -1

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
# ESTRATÉGIA DAS ZONAS ATUALIZADA
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
            if total_numeros > 0:
                percentual_geral = freq_geral / total_numeros
                score += percentual_geral * 25
            
            ultimos_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:] if total_numeros >= self.janelas_analise['curto_prazo'] else list(self.historico)
            if ultimos_curto:
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
        
        if not zonas_score:
            return None
            
        zona_vencedora = max(zonas_score, key=zonas_score.get)
        
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
        
        if not zonas_score:
            return None
            
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
        
        # Verificar se o sistema existe na sessão
        if 'sistema' not in st.session_state:
            return self.criar_previsao_unica(zona_primaria)
            
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
                
                if hasattr(sistema, 'deve_evitar_combinacao') and sistema.deve_evitar_combinacao(combinacao_teste):
                    continue
                
                threshold_secundario = threshold_base - 4
                
                if score_secundario >= threshold_secundario:
                    return self.criar_previsao_dupla(zona_primaria, zona_secundaria, "RANQUEADA")
        
        return self.criar_previsao_unica(zona_primaria)

    def criar_previsao_dupla(self, zona_primaria, zona_secundaria, tipo):
        numeros_primarios = self.numeros_zonas[zona_primaria]
        numeros_secundarios = self.numeros_zonas[zona_secundaria]
        
        numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
        
        if len(numeros_combinados) > 10:
            numeros_combinados = self.sistema_selecao.selecionar_melhores_10_numeros(
                numeros_combinados, self.historico, "Zonas"
            )
        
        info_eficiencia = ""
        if 'sistema' in st.session_state:
            sistema = st.session_state.sistema
            combinacao = tuple(sorted([zona_primaria, zona_secundaria]))
            dados_combinacao = sistema.historico_combinacoes.get(combinacao, {})
            eficiencia = dados_combinacao.get('eficiencia', 0)
            total = dados_combinacao.get('total', 0)
            
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
        
        if len(numeros_apostar) > 10:
            numeros_apostar = self.sistema_selecao.selecionar_melhores_10_numeros(
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
        if historico_curto:
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
        
        if sum(pesos) == 0:
            return 'Média'
            
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
        if total_numeros > 0:
            percentual_geral = freq_geral / total_numeros
            score += percentual_geral * 25
        
        for janela_nome, tamanho in self.janelas_analise.items():
            if janela_nome != 'performance':
                historico_janela = list(self.historico)[-tamanho:] if total_numeros >= tamanho else list(self.historico)
                if historico_janela:
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
            freq_total = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
            if len(self.historico) > 0:
                perc_total = (freq_total / len(self.historico)) * 100
            else:
                perc_total = 0
            
            freq_curto = sum(1 for n in list(self.historico)[-self.janelas_analise['curto_prazo']:] if n in self.numeros_zonas[zona])
            janela_curto_len = min(self.janelas_analise['curto_prazo'], len(self.historico))
            if janela_curto_len > 0:
                perc_curto = (freq_curto / janela_curto_len) * 100
            else:
                perc_curto = 0
            
            score = self.get_zona_score(zona)
            qtd_numeros = len(self.numeros_zonas[zona])
            analise += f"📍 {zona}: Total:{freq_total}/{len(self.historico)}({perc_total:.1f}%) | Curto:{freq_curto}/{janela_curto_len}({perc_curto:.1f}%) | Score: {score:.1f}\n"
        
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
# SISTEMA DE APRENDIZADO POR REFORÇO (REINFORCEMENT LEARNING)
# =============================
class SistemaAprendizadoReforco:
    def __init__(self):
        self.historico_aprendizado = deque(maxlen=100)
        self.melhores_combinacoes = {}
        self.piores_combinacoes = {}
        self.padroes_ganhadores = []
        self.sequencias_vencedoras = []
        self.contador_analise = 0
        self.ultimo_estado = None
        
    def analisar_resultado(self, resultado):
        """Analisa resultado e aprende padrões"""
        try:
            self.contador_analise += 1
            
            # Extrair dados do resultado
            acerto = resultado['acerto']
            estrategia = resultado['estrategia']
            numero = resultado['numero']
            previsao = resultado['previsao']
            zona_acertada = resultado.get('zona_acertada', '')
            zonas_envolvidas = resultado.get('zonas_envolvidas', [])
            
            # ANALISAR PADRÕES DE ACERTO
            if acerto:
                self.registrar_padrao_ganhador(numero, zonas_envolvidas, estrategia)
                
                # Analisar características do número acertado
                caracteristicas = self.analisar_caracteristicas_numero(numero)
                
                # Registrar sequência vencedora
                self.registrar_sequencia_vencedora(caracteristicas, zonas_envolvidas)
                
            # ATUALIZAR ESTATÍSTICAS DE COMBINAÇÕES
            if len(zonas_envolvidas) > 1:
                combinacao = tuple(sorted(zonas_envolvidas))
                self.atualizar_estatisticas_combinacao(combinacao, acerto)
            
            # ANALISAR TENDÊNCIAS TEMPORAIS
            self.analisar_tendencias_temporais(numero, acerto)
            
            # GERAR RECOMENDAÇÕES
            recomendacoes = self.gerar_recomendacoes()
            
            return recomendacoes
            
        except Exception as e:
            logging.error(f"Erro no sistema de aprendizado: {e}")
            return {}
    
    def analisar_caracteristicas_numero(self, numero):
        """Analisa características do número que acertou"""
        caracteristicas = {
            'numero': numero,
            'paridade': 'par' if numero % 2 == 0 else 'ímpar',
            'cor': self.get_cor_numero(numero),
            'duzia': self.get_duzia_numero(numero),
            'coluna': self.get_coluna_numero(numero),
            'baixo_alto': 'baixo' if 1 <= numero <= 18 else 'alto' if 19 <= numero <= 36 else 'zero',
            'vizinhanca': self.get_vizinhanca_numero(numero)
        }
        return caracteristicas
    
    def get_cor_numero(self, numero):
        """Retorna a cor do número"""
        vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        if numero == 0:
            return 'verde'
        elif numero in vermelhos:
            return 'vermelho'
        else:
            return 'preto'
    
    def get_duzia_numero(self, numero):
        """Retorna a duzia do número"""
        if 1 <= numero <= 12:
            return '1a_duzia'
        elif 13 <= numero <= 24:
            return '2a_duzia'
        elif 25 <= numero <= 36:
            return '3a_duzia'
        else:
            return 'zero'
    
    def get_coluna_numero(self, numero):
        """Retorna a coluna do número"""
        coluna_1 = {1,4,7,10,13,16,19,22,25,28,31,34}
        coluna_2 = {2,5,8,11,14,17,20,23,26,29,32,35}
        coluna_3 = {3,6,9,12,15,18,21,24,27,30,33,36}
        
        if numero in coluna_1:
            return 'coluna_1'
        elif numero in coluna_2:
            return 'coluna_2'
        elif numero in coluna_3:
            return 'coluna_3'
        else:
            return 'zero'
    
    def get_vizinhanca_numero(self, numero):
        """Retorna vizinhança do número na roda"""
        roleta = RoletaInteligente()
        vizinhos = roleta.get_vizinhos_fisicos(numero, raio=2)
        return vizinhos
    
    def registrar_padrao_ganhador(self, numero, zonas_envolvidas, estrategia):
        """Registra padrões que estão ganhando"""
        padrao = {
            'numero': numero,
            'zonas': zonas_envolvidas,
            'estrategia': estrategia,
            'timestamp': len(self.historico_aprendizado),
            'contagem': 1
        }
        
        # Verificar se padrão similar já existe
        padrao_existente = None
        for p in self.padroes_ganhadores:
            if (p['zonas'] == zonas_envolvidas and 
                abs(p['numero'] - numero) <= 3):  # Números próximos
                padrao_existente = p
                break
        
        if padrao_existente:
            padrao_existente['contagem'] += 1
        else:
            self.padroes_ganhadores.append(padrao)
            
        # Manter apenas os 20 padrões mais frequentes
        if len(self.padroes_ganhadores) > 20:
            self.padroes_ganhadores.sort(key=lambda x: x['contagem'], reverse=True)
            self.padroes_ganhadores = self.padroes_ganhadores[:20]
    
    def registrar_sequencia_vencedora(self, caracteristicas, zonas_envolvidas):
        """Registra sequências de características que estão vencendo"""
        sequencia = {
            'caracteristicas': caracteristicas,
            'zonas': zonas_envolvidas,
            'timestamp': len(self.historico_aprendizado)
        }
        
        self.sequencias_vencedoras.append(sequencia)
        
        # Manter apenas as últimas 50 sequências
        if len(self.sequencias_vencedoras) > 50:
            self.sequencias_vencedoras = self.sequencias_vencedoras[-50:]
    
    def atualizar_estatisticas_combinacao(self, combinacao, acerto):
        """Atualiza estatísticas da combinação"""
        if combinacao not in self.melhores_combinacoes:
            self.melhores_combinacoes[combinacao] = {
                'acertos': 0,
                'tentativas': 0,
                'eficiencia': 0,
                'sequencia_atual_acertos': 0,
                'sequencia_atual_erros': 0,
                'ultimos_resultados': deque(maxlen=10)
            }
        
        dados = self.melhores_combinacoes[combinacao]
        dados['tentativas'] += 1
        dados['ultimos_resultados'].append(acerto)
        
        if acerto:
            dados['acertos'] += 1
            dados['sequencia_atual_acertos'] += 1
            dados['sequencia_atual_erros'] = 0
        else:
            dados['sequencia_atual_erros'] += 1
            dados['sequencia_atual_acertos'] = 0
        
        if dados['tentativas'] > 0:
            dados['eficiencia'] = (dados['acertos'] / dados['tentativas']) * 100
        
        # Se eficiência < 30%, mover para piores combinações
        if dados['tentativas'] >= 5 and dados['eficiencia'] < 30:
            if combinacao not in self.piores_combinacoes:
                self.piores_combinacoes[combinacao] = dados
                if combinacao in self.melhores_combinacoes:
                    del self.melhores_combinacoes[combinacao]
    
    def analisar_tendencias_temporais(self, numero, acerto):
        """Analisa tendências temporais nos resultados"""
        # Registrar no histórico
        registro = {
            'numero': numero,
            'acerto': acerto,
            'timestamp': len(self.historico_aprendizado),
            'hora': pd.Timestamp.now().strftime('%H:%M')
        }
        
        self.historico_aprendizado.append(registro)
    
    def gerar_recomendacoes(self):
        """Gera recomendações baseadas no aprendizado"""
        recomendacoes = {
            'melhor_combinacao': None,
            'probabilidade': 0,
            'evitar_combinacao': None,
            'padroes_ativos': [],
            'alerta': None
        }
        
        # ENCONTRAR MELHOR COMBINAÇÃO
        combinacoes_validas = []
        for combinacao, dados in self.melhores_combinacoes.items():
            if dados['tentativas'] >= 3 and dados['eficiencia'] >= 60:
                score = dados['eficiencia']
                
                # Bônus para sequência de acertos
                if dados['sequencia_atual_acertos'] >= 2:
                    score *= 1.2
                
                # Penalidade para sequência de erros
                if dados['sequencia_atual_erros'] >= 2:
                    score *= 0.7
                
                combinacoes_validas.append({
                    'combinacao': combinacao,
                    'score': score,
                    'eficiencia': dados['eficiencia'],
                    'sequencia_acertos': dados['sequencia_atual_acertos']
                })
        
        if combinacoes_validas:
            combinacoes_validas.sort(key=lambda x: x['score'], reverse=True)
            melhor = combinacoes_validas[0]
            recomendacoes['melhor_combinacao'] = melhor['combinacao']
            recomendacoes['probabilidade'] = min(melhor['score'], 95)
            
            # Verificar se deve alertar sobre sequência forte
            if melhor['sequencia_acertos'] >= 3:
                recomendacoes['alerta'] = f"🔥 SEQUÊNCIA FORTE: {melhor['combinacao']} com {melhor['sequencia_acertos']} acertos seguidos!"
        
        # IDENTIFICAR COMBINAÇÕES PARA EVITAR
        if self.piores_combinacoes:
            piores = list(self.piores_combinacoes.items())
            piores.sort(key=lambda x: x[1]['eficiencia'])
            if piores:
                recomendacoes['evitar_combinacao'] = piores[0][0]
        
        # IDENTIFICAR PADRÕES ATIVOS
        padroes_recentes = []
        for padrao in self.padroes_ganhadores[-5:]:
            idade = len(self.historico_aprendizado) - padrao['timestamp']
            if idade <= 10:  # Padrões recentes
                padroes_recentes.append({
                    'zonas': padrao['zonas'],
                    'contagem': padrao['contagem'],
                    'idade': idade
                })
        
        recomendacoes['padroes_ativos'] = padroes_recentes
        
        return recomendacoes
    
    def get_estatisticas_aprendizado(self):
        """Retorna estatísticas do aprendizado"""
        total_registros = len(self.historico_aprendizado)
        acertos_totais = sum(1 for r in self.historico_aprendizado if r['acerto'])
        
        estatisticas = {
            'total_analises': self.contador_analise,
            'total_registros': total_registros,
            'taxa_acerto_historico': (acertos_totais / total_registros * 100) if total_registros > 0 else 0,
            'melhores_combinacoes_count': len(self.melhores_combinacoes),
            'piores_combinacoes_count': len(self.piores_combinacoes),
            'padroes_identificados': len(self.padroes_ganhadores),
            'sequencias_vencedoras': len(self.sequencias_vencedoras)
        }
        
        # Top 3 melhores combinações
        melhores = []
        for combo, dados in self.melhores_combinacoes.items():
            if dados['tentativas'] >= 3:
                melhores.append({
                    'combinacao': combo,
                    'eficiencia': dados['eficiencia'],
                    'tentativas': dados['tentativas'],
                    'sequencia_acertos': dados['sequencia_atual_acertos']
                })
        
        melhores.sort(key=lambda x: x['eficiencia'], reverse=True)
        estatisticas['top_3_melhores'] = melhores[:3]
        
        return estatisticas
    
    def sugerir_ajustes_estrategia(self, historico_recente):
        """Sugere ajustes na estratégia baseado no aprendizado"""
        if len(historico_recente) < 10:
            return "Aguardando mais dados para análise..."
        
        # Analisar padrões recentes
        acertos_recentes = sum(1 for r in historico_recente if r['acerto'])
        taxa_recente = (acertos_recentes / len(historico_recente)) * 100
        
        sugestoes = []
        
        if taxa_recente < 70:
            sugestoes.append("📉 **Taxa recente baixa** - Considerar pausa ou reduzir apostas")
            
            # Verificar se há combinação com sequência de erros
            for combo, dados in self.melhores_combinacoes.items():
                if dados['sequencia_atual_erros'] >= 2:
                    sugestoes.append(f"🚨 **{combo} com {dados['sequencia_atual_erros']} erros seguidos** - Trocar combinação")
        
        if taxa_recente > 80:
            sugestoes.append("📈 **Taxa recente alta** - Aumentar confiança na estratégia atual")
            
            # Identificar combinação em sequência positiva
            for combo, dados in self.melhores_combinacoes.items():
                if dados['sequencia_atual_acertos'] >= 3:
                    sugestoes.append(f"🔥 **{combo} com {dados['sequencia_atual_acertos']} acertos seguidos** - Manter foco")
        
        # Verificar padrões de horário
        horas = [r['hora'] for r in historico_recente[-20:]]
        if horas:
            hora_mais_comum = max(set(horas), key=horas.count)
            sugestoes.append(f"🕒 **Horário produtivo:** {hora_mais_comum}")
        
        return "\n".join(sugestoes) if sugestoes else "✅ Estratégia atual funcionando bem. Continuar."

# =============================
# SISTEMA DE OTIMIZAÇÃO DINÂMICA
# =============================
class SistemaOtimizacaoDinamica:
    def __init__(self):
        self.aprendizado = SistemaAprendizadoReforco()
        self.ultima_recomendacao = None
        self.contador_otimizacoes = 0
        self.estrategia_ativa = None
        self.performance_historica = deque(maxlen=50)
        self.alertas_otimizacao = []
        
    def processar_resultado(self, resultado):
        """Processa resultado e otimiza estratégia"""
        try:
            # 1. Aprender com o resultado
            recomendacoes = self.aprendizado.analisar_resultado(resultado)
            
            # 2. Atualizar performance histórica
            self.performance_historica.append({
                'timestamp': len(self.performance_historica),
                'acerto': resultado['acerto'],
                'estrategia': resultado['estrategia'],
                'numero': resultado['numero']
            })
            
            # 3. Gerar otimizações
            otimizacao = self.gerar_otimizacao(recomendacoes, resultado)
            
            # 4. Atualizar última recomendação
            self.ultima_recomendacao = {
                'recomendacoes': recomendacoes,
                'otimizacao': otimizacao,
                'timestamp': len(self.performance_historica)
            }
            
            self.contador_otimizacoes += 1
            
            return otimizacao
            
        except Exception as e:
            logging.error(f"Erro no sistema de otimização: {e}")
            return None
    
    def gerar_otimizacao(self, recomendacoes, resultado):
        """Gera otimizações baseadas nas recomendações"""
        otimizacao = {
            'acao': 'manter',
            'combinacao_sugerida': None,
            'confianca': 0,
            'razoes': [],
            'alerta': None
        }
        
        # VERIFICAR SE DEVE MUDAR COMBINAÇÃO
        if recomendacoes.get('melhor_combinacao'):
            melhor_combo = recomendacoes['melhor_combinacao']
            probabilidade = recomendacoes['probabilidade']
            
            # Verificar combinação atual do resultado
            zonas_atual = resultado.get('zonas_envolvidas', [])
            if len(zonas_atual) > 1:
                combinacao_atual = tuple(sorted(zonas_atual))
                
                # Se não for a melhor combinação e probabilidade > 75%
                if combinacao_atual != melhor_combo and probabilidade > 75:
                    otimizacao['acao'] = 'mudar'
                    otimizacao['combinacao_sugerida'] = melhor_combo
                    otimizacao['confianca'] = probabilidade
                    otimizacao['razoes'].append(f"Melhor combinação ({probabilidade:.1f}%)")
                    
                    # Verificar se combinação atual está ruim
                    estatisticas = self.aprendizado.melhores_combinacoes.get(combinacao_atual, {})
                    if estatisticas and estatisticas.get('eficiencia', 100) < 50:
                        otimizacao['razoes'].append(f"Combinação atual com baixa eficiência ({estatisticas['eficiencia']:.1f}%)")
        
        # VERIFICAR ALERTAS
        if recomendacoes.get('alerta'):
            otimizacao['alerta'] = recomendacoes['alerta']
            
            # Se for alerta de sequência forte, aumentar confiança
            if 'SEQUÊNCIA FORTE' in recomendacoes['alerta']:
                otimizacao['confianca'] = max(otimizacao['confianca'], 85)
                otimizacao['razoes'].append("Sequência forte detectada")
        
        # VERIFICAR PADRÕES ATIVOS
        if recomendacoes.get('padroes_ativos'):
            padroes_recentes = recomendacoes['padroes_ativos']
            if padroes_recentes:
                # Verificar se há padrão recorrente
                padroes_por_zona = {}
                for p in padroes_recentes:
                    for zona in p['zonas']:
                        if zona not in padroes_por_zona:
                            padroes_por_zona[zona] = 0
                        padroes_por_zona[zona] += p['contagem']
                
                # Identificar zona mais ativa
                if padroes_por_zona:
                    zona_mais_ativa = max(padroes_por_zona.items(), key=lambda x: x[1])
                    otimizacao['razoes'].append(f"Zona {zona_mais_ativa[0]} ativa em padrões recentes")
        
        # SE NÃO HOUVER RAZÕES, MANTER STATUS QUO
        if not otimizacao['razoes']:
            otimizacao['razoes'].append("Performance estável - manter estratégia atual")
        
        return otimizacao
    
    def aplicar_otimizacao(self, sistema_principal, otimizacao):
        """Aplica otimização ao sistema principal"""
        try:
            if otimizacao['acao'] == 'mudar' and otimizacao['combinacao_sugerida']:
                combinacao = otimizacao['combinacao_sugerida']
                
                # Criar nova previsão com a combinação sugerida
                if sistema_principal.criar_previsao_com_combinacao(combinacao):
                    logging.info(f"🔄 OTIMIZAÇÃO APLICADA: Mudou para combinação {combinacao}")
                    
                    # Registrar alerta
                    self.alertas_otimizacao.append({
                        'tipo': 'otimizacao',
                        'mensagem': f"Otimização aplicada: {combinacao} (Confiança: {otimizacao['confianca']:.1f}%)",
                        'timestamp': len(self.performance_historica)
                    })
                    
                    return True
            
            elif otimizacao['alerta']:
                # Apenas registrar alerta
                self.alertas_otimizacao.append({
                    'tipo': 'alerta',
                    'mensagem': otimizacao['alerta'],
                    'timestamp': len(self.performance_historica)
                })
                
                logging.info(f"⚠️ ALERTA OTIMIZAÇÃO: {otimizacao['alerta']}")
            
            return False
            
        except Exception as e:
            logging.error(f"Erro ao aplicar otimização: {e}")
            return False
    
    def get_resumo_otimizacao(self):
        """Retorna resumo das otimizações"""
        resumo = {
            'total_otimizacoes': self.contador_otimizacoes,
            'ultima_recomendacao': self.ultima_recomendacao,
            'alertas_ativos': len(self.alertas_otimizacao[-5:]),
            'performance_recente': self.calcular_performance_recente()
        }
        
        # Estatísticas do aprendizado
        estatisticas_aprendizado = self.aprendizado.get_estatisticas_aprendizado()
        resumo['estatisticas_aprendizado'] = estatisticas_aprendizado
        
        return resumo
    
    def calcular_performance_recente(self):
        """Calcula performance recente"""
        if len(self.performance_historica) < 10:
            return {"total": 0, "acertos": 0, "taxa": 0}
        
        recentes = list(self.performance_historica)[-10:]
        acertos = sum(1 for r in recentes if r['acerto'])
        total = len(recentes)
        
        return {
            "total": total,
            "acertos": acertos,
            "taxa": (acertos / total * 100) if total > 0 else 0
        }
    
    def sugerir_melhoria_estrategia(self, sistema_principal):
        """Sugere melhorias na estratégia global"""
        sugestoes = []
        
        # Analisar combinações do sistema principal
        if hasattr(sistema_principal, 'historico_combinacoes'):
            combinacoes = sistema_principal.historico_combinacoes
            
            # Identificar combinação mais eficiente
            combinacoes_eficientes = []
            for combo, dados in combinacoes.items():
                if dados.get('total', 0) >= 5:
                    eficiencia = dados.get('eficiencia', 0)
                    if eficiencia >= 70:
                        combinacoes_eficientes.append((combo, eficiencia))
            
            if combinacoes_eficientes:
                melhor = max(combinacoes_eficientes, key=lambda x: x[1])
                sugestoes.append(f"🎯 **Focar em {melhor[0]}** ({melhor[1]:.1f}% eficiência)")
            
            # Identificar combinações problemáticas
            combinacoes_problematicas = []
            for combo, dados in combinacoes.items():
                if dados.get('total', 0) >= 3:
                    eficiencia = dados.get('eficiencia', 0)
                    if eficiencia < 40:
                        combinacoes_problematicas.append((combo, eficiencia))
            
            if combinacoes_problematicas:
                pior = min(combinacoes_problematicas, key=lambda x: x[1])
                sugestoes.append(f"🚫 **Evitar {pior[0]}** ({pior[1]:.1f}% eficiência)")
        
        # Sugestões do aprendizado por reforço
        if self.ultima_recomendacao:
            rec = self.ultima_recomendacao['recomendacoes']
            if rec.get('melhor_combinacao'):
                sugestoes.append(f"🤖 **Sistema AI recomenda:** {rec['melhor_combinacao']}")
        
        return sugestoes

# =============================
# SISTEMA DE GESTÃO ATUALIZADO E CORRIGIDO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Zonas"
        self.contador_sorteios_global = 0
        
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        self.todas_combinacoes_zonas = [
            ['Vermelha', 'Azul'],
            ['Vermelha', 'Amarela'], 
            ['Azul', 'Amarela']
        ]
        
        self.sistema_tendencias = SistemaTendencias()
        
        # ===== NOVO: SISTEMA DE APRENDIZADO POR REFORÇO =====
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()
        self.ultima_otimizacao = None
        self.contador_otimizacoes_aplicadas = 0

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    # =============================
    # FUNÇÕES DE ROTAÇÃO CORRIGIDAS
    # =============================
    
    def rotacionar_estrategia_automaticamente(self, acerto, nome_estrategia, zonas_envolvidas):
        """ROTAÇÃO AUTOMÁTICA CORRIGIDA - Lógica simplificada e funcional"""
        
        # Atualizar desempenho da combinação
        dados_combinacao = self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
        
        # Atualizar sequências globais
        if acerto:
            self.sequencia_acertos += 1
            self.sequencia_erros = 0
        else:
            self.sequencia_erros += 1
            self.sequencia_acertos = 0
            self.ultima_estrategia_erro = nome_estrategia
        
        # Verificar se é uma combinação dupla
        if len(zonas_envolvidas) > 1:
            combinacao_atual = tuple(sorted(zonas_envolvidas))
            
            # REGRA 1: ROTAÇÃO POR 3 ACERTOS SEGUIDOS NA MESMA COMBINAÇÃO
            if acerto and dados_combinacao and dados_combinacao.get('sequencia_acertos', 0) >= 3:
                logging.info(f"🎯 REGRA ATIVADA: 3 acertos seguidos na combinação {combinacao_atual}")
                
                # Resetar sequência de acertos desta combinação
                if combinacao_atual in self.historico_combinacoes:
                    self.historico_combinacoes[combinacao_atual]['sequencia_acertos'] = 0
                
                # Tentar rotação por novas zonas
                if self.rotacionar_por_novas_zonas(combinacao_atual):
                    return True
                
                # Se não conseguir, usar rotação por acertos
                return self.aplicar_rotacao_por_acertos_combinacoes(combinacao_atual)
            
            # REGRA 2: ROTAÇÃO POR 2 ERROS SEGUIDOS NA MESMA COMBINAÇÃO
            if not acerto and dados_combinacao and dados_combinacao.get('sequencia_erros', 0) >= 2:
                logging.info(f"🚨 REGRA ATIVADA: 2 erros seguidos na combinação {combinacao_atual}")
                
                # Resetar sequência de erros desta combinação
                if combinacao_atual in self.historico_combinacoes:
                    self.historico_combinacoes[combinacao_atual]['sequencia_erros'] = 0
                
                # Adicionar à lista fria se não estiver
                if combinacao_atual not in self.combinacoes_frias:
                    self.combinacoes_frias.append(combinacao_atual)
                    logging.info(f"📝 Combinação {combinacao_atual} adicionada à lista fria")
                
                # Aplicar rotação inteligente
                return self.aplicar_rotacao_inteligente()
        
        return False

    def aplicar_rotacao_por_acertos_combinacoes(self, combinacao_atual):
        """Rotação após 3 acertos - VERSÃO CORRIGIDA"""
        logging.info(f"🎯 ROTAÇÃO POR ACERTOS: Analisando alternativas para {combinacao_atual}")
        
        # 1. Extrair zonas da combinação atual
        zona_atual_1, zona_atual_2 = combinacao_atual
        
        # 2. Encontrar zona que NÃO está na combinação atual
        todas_zonas = ['Vermelha', 'Azul', 'Amarela']
        zona_fora = [z for z in todas_zonas if z not in combinacao_atual]
        
        if zona_fora:
            zona_nova = zona_fora[0]
            logging.info(f"🎯 Zona disponível fora da combinação atual: {zona_nova}")
            
            # 3. Criar combinações com a zona nova + uma das zonas atuais
            combinacoes_possiveis = [
                tuple(sorted([zona_nova, zona_atual_1])),
                tuple(sorted([zona_nova, zona_atual_2]))
            ]
            
            # 4. Analisar cada combinação possível
            combinacoes_analisadas = []
            
            for combo in combinacoes_possiveis:
                # Pular se for a mesma combinação
                if combo == combinacao_atual:
                    continue
                    
                # Pular se estiver na lista fria
                if combo in self.combinacoes_frias:
                    continue
                
                # Obter dados da combinação
                dados_combo = self.historico_combinacoes.get(combo, {})
                eficiencia = dados_combo.get('eficiencia', 50)  # 50% se não testado
                total = dados_combo.get('total', 0)
                sequencia_erros = dados_combo.get('sequencia_erros', 0)
                
                # Filtrar combinações com problemas
                if total > 0:
                    if eficiencia < 20:  # Eficiência muito baixa
                        continue
                    if sequencia_erros >= 2:  # Recentemente teve 2 erros seguidos
                        continue
                
                # Calcular pontuação
                pontuacao = eficiencia
                if total == 0:  # Nunca testada - dar chance
                    pontuacao = 60
                
                combinacoes_analisadas.append({
                    'combo': combo,
                    'pontuacao': pontuacao,
                    'eficiencia': eficiencia,
                    'total': total,
                    'zona_nova': zona_nova
                })
            
            # 5. Escolher a melhor combinação
            if combinacoes_analisadas:
                combinacoes_analisadas.sort(key=lambda x: x['pontuacao'], reverse=True)
                melhor_combo = combinacoes_analisadas[0]['combo']
                
                logging.info(f"✅ MELHOR COMBINAÇÃO ESCOLHIDA: {melhor_combo}")
                logging.info(f"   • Pontuação: {combinacoes_analisadas[0]['pontuacao']:.1f}")
                logging.info(f"   • Eficiência: {combinacoes_analisadas[0]['eficiencia']:.1f}%")
                logging.info(f"   • Total jogos: {combinacoes_analisadas[0]['total']}")
                
                # 6. Criar previsão com a nova combinação
                if self.criar_previsao_com_combinacao(melhor_combo):
                    # Resetar sequências globais
                    self.sequencia_acertos = 0
                    
                    # Enviar notificação
                    enviar_rotacao_por_acertos_combinacoes(combinacao_atual, melhor_combo)
                    logging.info(f"🔄 ROTAÇÃO POR ACERTOS aplicada: {combinacao_atual} → {melhor_combo}")
                    return True
        
        # 7. Se não encontrou combinação com zona nova, usar lógica alternativa
        logging.info("⚠️  Não encontrou combinação com zona nova - usando lógica alternativa")
        
        combinacoes_alternativas = [
            tuple(combo) for combo in self.todas_combinacoes_zonas
            if tuple(combo) != combinacao_atual
            and tuple(combo) not in self.combinacoes_frias
        ]
        
        if combinacoes_alternativas:
            # Escolher aleatoriamente (para evitar padrões)
            import random
            nova_combinacao = random.choice(combinacoes_alternativas)
            
            if self.criar_previsao_com_combinacao(nova_combinacao):
                self.sequencia_acertos = 0
                enviar_rotacao_por_acertos_combinacoes(combinacao_atual, nova_combinacao)
                logging.info(f"🔄 ROTAÇÃO ALTERNATIVA: {combinacao_atual} → {nova_combinacao}")
                return True
        
        logging.warning(f"❌ Não foi possível encontrar combinação alternativa para {combinacao_atual}")
        return False

    def aplicar_rotacao_inteligente(self):
        """Rotação inteligente após 2 erros - VERSÃO CORRIGIDA"""
        estrategia_atual = self.estrategia_selecionada
        
        logging.info(f"🚨 APLICANDO ROTAÇÃO INTELIGENTE - Estratégia: {estrategia_atual}, Erros: {self.sequencia_erros}")
        
        # Verificar se temos previsão ativa e combinação
        if self.previsao_ativa and self.previsao_ativa.get('zonas_envolvidas'):
            combinacao_atual = tuple(sorted(self.previsao_ativa['zonas_envolvidas']))
            logging.info(f"🔍 ROTAÇÃO: Combinacao atual detectada: {combinacao_atual}")
            
            # TENTATIVA 1: Rotação para combinação diferente
            if self.rotacionar_por_novas_zonas(combinacao_atual):
                self.sequencia_erros = 0
                return True
        
        return False

    def rotacionar_por_novas_zonas(self, combinacao_atual):
        """Rotação para usar zonas diferentes - VERSÃO CORRIGIDA"""
        logging.info(f"🔄 ROTAÇÃO POR NOVAS ZONAS: Analisando alternativas para {combinacao_atual}")
        
        # Extrair zonas atuais
        zona_atual_1, zona_atual_2 = combinacao_atual
        
        # Todas as zonas disponíveis
        todas_zonas = ['Vermelha', 'Azul', 'Amarela']
        
        # Encontrar a zona que NÃO está na combinação atual
        zona_fora = [z for z in todas_zonas if z not in combinacao_atual]
        
        if zona_fora:
            zona_nova = zona_fora[0]
            logging.info(f"🎯 Zona disponível fora da combinação atual: {zona_nova}")
            
            # Criar combinações com a zona nova + uma das zonas atuais
            combinacoes_possiveis = [
                tuple(sorted([zona_nova, zona_atual_1])),
                tuple(sorted([zona_nova, zona_atual_2]))
            ]
            
            # Analisar cada combinação
            for combo in combinacoes_possiveis:
                if combo == combinacao_atual:
                    continue
                    
                # Verificar se não está na lista fria
                if combo in self.combinacoes_frias:
                    logging.info(f"  ⚠️ Combinação {combo} está na lista fria")
                    continue
                
                # Verificar dados históricos
                dados = self.historico_combinacoes.get(combo, {})
                if dados:
                    eficiencia = dados.get('eficiencia', 0)
                    total = dados.get('total', 0)
                    sequencia_erros = dados.get('sequencia_erros', 0)
                    
                    if total >= 3 and eficiencia < 20:
                        logging.info(f"  ⚠️ Combinação {combo} tem eficiência baixa ({eficiencia:.1f}%)")
                        continue
                        
                    if sequencia_erros >= 2:
                        logging.info(f"  ⚠️ Combinação {combo} teve 2 erros seguidos recentemente")
                        continue
                
                # Se chegou aqui, a combinação é válida
                if self.criar_previsao_com_combinacao(combo):
                    logging.info(f"✅ ROTAÇÃO SELECIONADA: {combinacao_atual} → {combo}")
                    
                    # Resetar sequências
                    self.sequencia_erros = 0
                    
                    # Enviar notificação
                    enviar_rotacao_por_2_erros(combinacao_atual, combo)
                    return True
        
        logging.info("⚠️  Não foi possível encontrar combinação com zona nova")
        return False

    def atualizar_desempenho_combinacao(self, zonas_envolvidas, acerto):
        """Atualiza desempenho de combinações - VERSÃO CORRIGIDA"""
        if len(zonas_envolvidas) > 1:
            combinacao = tuple(sorted(zonas_envolvidas))
            
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
            else:
                dados['sequencia_erros'] += 1
                dados['sequencia_acertos'] = 0
            
            if dados['total'] > 0:
                dados['eficiencia'] = (dados['acertos'] / dados['total']) * 100
            
            # Atualizar combinações quentes/frias
            self.atualizar_combinacoes_quentes_frias()
            
            return dados
        
        return None

    def atualizar_combinacoes_quentes_frias(self):
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        combinacoes_ativas = {k: v for k, v in self.historico_combinacoes.items() 
                             if v['total'] >= 2}
        
        for combinacao, dados in combinacoes_ativas.items():
            eficiencia = dados['eficiencia']
            total_jogos = dados['total']
            sequencia_acertos = dados['sequencia_acertos']
            sequencia_erros = dados['sequencia_erros']
            
            # Combinação quente
            if (eficiencia >= 50 or 
                (eficiencia >= 40 and total_jogos >= 3) or
                sequencia_acertos >= 2):
                self.combinacoes_quentes.append(combinacao)
            
            # Combinação fria
            elif (eficiencia < 25 and total_jogos >= 3) or sequencia_erros >= 2:
                self.combinacoes_frias.append(combinacao)
    
    def get_combinacao_recomendada(self):
        if not self.combinacoes_quentes:
            return None
        
        # Priorizar combinações com sequência de acertos
        combinacoes_com_sequencia = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if combo in self.combinacoes_quentes and dados['sequencia_acertos'] >= 1
        ]
        
        if combinacoes_com_sequencia:
            combinacoes_com_sequencia.sort(key=lambda x: x[1]['sequencia_acertos'], reverse=True)
            return combinacoes_com_sequencia[0][0]
        
        # Se não tiver sequência, usar eficiência
        combinacoes_eficientes = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if combo in self.combinacoes_quentes
        ]
        
        if combinacoes_eficientes:
            combinacoes_eficientes.sort(key=lambda x: x[1]['eficiencia'], reverse=True)
            return combinacoes_eficientes[0][0]
        
        return None

    def deve_evitar_combinacao(self, combinacao):
        if combinacao in self.combinacoes_frias:
            return True
        
        dados = self.historico_combinacoes.get(combinacao, {})
        if dados and dados.get('total', 0) >= 3 and dados.get('eficiencia', 0) < 20:
            return True
            
        return False

    def calcular_performance_estrategias(self):
        performance = {}
        historico_recente = self.historico_desempenho[-10:] if len(self.historico_desempenho) >= 10 else self.historico_desempenho
        
        for resultado in historico_recente:
            estrategia = resultado['estrategia']
            if estrategia not in performance:
                performance[estrategia] = {'acertos': 0, 'total': 0}
            
            performance[estrategia]['total'] += 1
            if resultado['acerto']:
                performance[estrategia]['acertos'] += 1
        
        for estrategia, dados in performance.items():
            if dados['total'] > 0:
                performance[estrategia] = (dados['acertos'] / dados['total']) * 100
            else:
                performance[estrategia] = 0
        
        return performance

    def combinacao_para_texto(self, combinacao):
        if len(combinacao) == 2:
            zona1, zona2 = combinacao
            return f"{zona1}+{zona2}"
        return str(combinacao)

    def criar_previsao_com_combinacao(self, combinacao):
        """Cria previsão com combinação específica - VERSÃO CORRIGIDA"""
        try:
            zonas_list = list(combinacao)
            
            # Usar a estratégia de zonas para criar a previsão
            if hasattr(self, 'estrategia_zonas'):
                if len(zonas_list) == 2:
                    previsao_forcada = self.estrategia_zonas.criar_previsao_dupla(
                        zonas_list[0], 
                        zonas_list[1], 
                        "ROTAÇÃO-AUTOMÁTICA"
                    )
                else:
                    previsao_forcada = self.estrategia_zonas.criar_previsao_unica(
                        zonas_list[0]
                    )
                
                if previsao_forcada:
                    self.previsao_ativa = previsao_forcada
                    self.estrategia_selecionada = "Zonas"
                    
                    logging.info(f"🎯 Nova previsão criada com combinação: {combinacao}")
                    return True
                    
        except Exception as e:
            logging.error(f"❌ Erro ao criar previsão com combinação {combinacao}: {e}")
        
        return False

    def get_status_rotacao(self):
        """Status da rotação - VERSÃO CORRIGIDA"""
        status = {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'ultima_estrategia_erro': self.ultima_estrategia_erro,
            'ultimas_combinacoes_acerto': self.ultima_combinacao_acerto,
            'proxima_rotacao_erros': max(0, 2 - self.sequencia_erros),
            'proxima_rotacao_acertos': max(0, 3 - self.sequencia_acertos),
            'combinacoes_quentes': len(self.combinacoes_quentes),
            'combinacoes_frias': len(self.combinacoes_frias)
        }
        
        # Adicionar sequências por combinação
        sequencias_combinacoes = {}
        for combo, dados in self.historico_combinacoes.items():
            if dados.get('total', 0) > 0:
                sequencias_combinacoes[str(combo)] = {
                    'sequencia_acertos': dados.get('sequencia_acertos', 0),
                    'sequencia_erros': dados.get('sequencia_erros', 0),
                    'eficiencia': dados.get('eficiencia', 0),
                    'total': dados.get('total', 0)
                }
        
        status['sequencias_combinacoes'] = sequencias_combinacoes
        
        return status

    def get_debug_rotacao(self):
        """Retorna informações detalhadas para debug da rotação"""
        debug_info = {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'previsao_ativa': bool(self.previsao_ativa),
            'historico_desempenho_tamanho': len(self.historico_desempenho),
            'combinacoes_registradas': len(self.historico_combinacoes)
        }
        
        if self.previsao_ativa:
            debug_info['previsao_tipo'] = self.previsao_ativa.get('nome', 'Desconhecido')
            debug_info['zonas_envolvidas'] = self.previsao_ativa.get('zonas_envolvidas', [])
        
        return debug_info

    def processar_com_otimizacao(self, resultado):
        """Processa resultado com otimização"""
        # Processar normalmente
        self.processar_novo_numero(resultado['numero'])
        
        # Aplicar otimização
        otimizacao = self.sistema_otimizacao.processar_resultado(resultado)
        
        if otimizacao:
            self.ultima_otimizacao = otimizacao
            
            # Aplicar otimização se necessário
            if otimizacao['acao'] == 'mudar':
                aplicada = self.sistema_otimizacao.aplicar_otimizacao(self, otimizacao)
                if aplicada:
                    self.contador_otimizacoes_aplicadas += 1
        
        return otimizacao

    def processar_novo_numero(self, numero):
        try:
            if isinstance(numero, dict) and 'number' in numero:
                numero_real = numero['number']
            else:
                numero_real = numero
                
            self.contador_sorteios_global += 1
            
            # Processar resultado da previsão anterior
            if self.previsao_ativa:
                acerto = False
                zonas_acertadas = []
                nome_estrategia = self.previsao_ativa['nome']
                
                zonas_envolvidas = self.previsao_ativa.get('zonas_envolvidas', [])
                if not zonas_envolvidas:
                    acerto = numero_real in self.previsao_ativa['numeros_apostar']
                    if acerto:
                        for zona, numeros in self.estrategia_zonas.numeros_zonas.items():
                            if numero_real in numeros:
                                zonas_acertadas.append(zona)
                                break
                else:
                    for zona in zonas_envolvidas:
                        numeros_zona = self.estrategia_zonas.numeros_zonas[zona]
                        
                        if numero_real in numeros_zona:
                            acerto = True
                            zonas_acertadas.append(zona)
                
                # Atualizar análise de tendências
                self.atualizar_analise_tendencias(numero_real, zonas_acertadas[0] if zonas_acertadas else None, acerto)
                
                # Tentar rotação automática
                rotacionou = self.rotacionar_estrategia_automaticamente(acerto, nome_estrategia, zonas_envolvidas)
                
                # Atualizar contadores de estratégias
                if nome_estrategia not in self.estrategias_contador:
                    self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[nome_estrategia]['total'] += 1
                if acerto:
                    self.estrategias_contador[nome_estrategia]['acertos'] += 1
                    self.acertos += 1
                else:
                    self.erros += 1
                
                # Criar resultado para otimização
                resultado_para_otimizacao = {
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'previsao': self.previsao_ativa['numeros_apostar'],
                    'zona_acertada': "+".join(zonas_acertadas) if zonas_acertadas else None,
                    'zonas_envolvidas': zonas_envolvidas
                }
                
                # Processar com otimização dinâmica
                otimizacao = self.processar_com_otimizacao(resultado_para_otimizacao)
                
                # Enviar notificação de resultado
                zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
                enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str)
                
                # Mostrar otimização se existir
                if otimizacao and otimizacao.get('alerta'):
                    st.warning(f"⚠️ {otimizacao['alerta']}")
                
                # Registrar no histórico
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
                    'ultima_combinacao_acerto': self.ultima_combinacao_acerto.copy(),
                    'otimizacao_aplicada': otimizacao.get('acao') if otimizacao else None
                })
                
                self.previsao_ativa = None
            
            # Adicionar número às estratégias
            self.estrategia_zonas.adicionar_numero(numero_real)
            
            # Gerar nova previsão
            nova_estrategia = self.estrategia_zonas.analisar_zonas()
            
            if nova_estrategia:
                self.previsao_ativa = nova_estrategia
                enviar_previsao_super_simplificada(nova_estrategia)
                
        except Exception as e:
            logging.error(f"Erro ao processar novo número: {e}")

    def atualizar_analise_tendencias(self, numero, zona_acertada=None, acerto_ultima=False):
        try:
            zonas_rankeadas = self.estrategia_zonas.get_zonas_rankeadas()
            if not zonas_rankeadas:
                return
            
            analise_tendencia = self.sistema_tendencias.analisar_tendencia(
                zonas_rankeadas, acerto_ultima, zona_acertada
            )
            
            self.sistema_tendencias.historico_tendencias.append(analise_tendencia)
            
            # Enviar notificações de tendência
            if 'alertas_config' in st.session_state and st.session_state.alertas_config.get('alertas_tendencia', True):
                self.sistema_tendencias.enviar_notificacoes_tendencia(analise_tendencia)
                enviar_alerta_tendencia(analise_tendencia)
            
        except Exception as e:
            logging.error(f"Erro na análise de tendências: {e}")

    def zerar_estatisticas_desempenho(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        self.estrategia_zonas.zerar_estatisticas()
        
        self.sistema_tendencias = SistemaTendencias()
        
        # Zerar sistema de otimização
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()
        self.ultima_otimizacao = None
        self.contador_otimizacoes_aplicadas = 0
        
        logging.info("📊 Todas as estatísticas de desempenho foram zeradas")
        salvar_sessao()

    def reset_recente_estatisticas(self):
        if len(self.historico_desempenho) > 10:
            self.historico_desempenho = self.historico_desempenho[-10:]
            
            self.acertos = sum(1 for resultado in self.historico_desempenho if resultado['acerto'])
            self.erros = len(self.historico_desempenho) - self.acertos
            
            self.estrategias_contador = {}
            for resultado in self.historico_desempenho:
                estrategia = resultado['estrategia']
                if estrategia not in self.estrategias_contador:
                    self.estrategias_contador[estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[estrategia]['total'] += 1
                if resultado['acerto']:
                    self.estrategias_contador[estrategia]['acertos'] += 1
            
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
            
            logging.info("🔄 Estatísticas recentes resetadas (mantidos últimos 10 resultados)")
        else:
            logging.info("ℹ️  Histórico muito pequeno para reset recente")
        
        salvar_sessao()

    def get_analise_tendencias_completa(self):
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
        
        if self.sistema_tendencias.historico_tendencias:
            ultima = self.sistema_tendencias.historico_tendencias[-1]
            analise += f"\n📝 ÚLTIMA ANÁLISE:\n"
            analise += f"  Estado: {ultima['estado']}\n"
            analise += f"  Confiança: {ultima['confianca']:.0%}\n"
            analise += f"  Ação: {ultima['acao'].upper()}\n"
            analise += f"  Mensagem: {ultima['mensagem']}\n"
        
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

    def get_relatorio_otimizacao(self):
        """Retorna relatório de otimização"""
        if not hasattr(self, 'sistema_otimizacao'):
            return "Sistema de otimização não inicializado"
        
        resumo = self.sistema_otimizacao.get_resumo_otimizacao()
        
        relatorio = "🤖 RELATÓRIO DE OTIMIZAÇÃO DINÂMICA\n"
        relatorio += "=" * 60 + "\n"
        
        relatorio += f"📊 Total de otimizações: {resumo['total_otimizacoes']}\n"
        relatorio += f"🔄 Otimizações aplicadas: {self.contador_otimizacoes_aplicadas}\n"
        
        # Performance recente
        perf = resumo['performance_recente']
        relatorio += f"🎯 Performance recente: {perf['acertos']}/{perf['total']} ({perf['taxa']:.1f}%)\n"
        
        # Última recomendação
        if resumo['ultima_recomendacao']:
            rec = resumo['ultima_recomendacao']['recomendacoes']
            if rec.get('melhor_combinacao'):
                relatorio += f"🏆 Melhor combinação atual: {rec['melhor_combinacao']} ({rec['probabilidade']:.1f}%)\n"
            
            if rec.get('evitar_combinacao'):
                relatorio += f"🚫 Evitar combinação: {rec['evitar_combinacao']}\n"
        
        # Estatísticas do aprendizado
        estat = resumo['estatisticas_aprendizado']
        relatorio += f"\n🧠 ESTATÍSTICAS DE APRENDIZADO:\n"
        relatorio += f"• Análises realizadas: {estat['total_analises']}\n"
        relatorio += f"• Padrões identificados: {estat['padroes_identificados']}\n"
        relatorio += f"• Combinações otimizadas: {estat['melhores_combinacoes_count']}\n"
        
        # Top combinações
        if estat.get('top_3_melhores'):
            relatorio += f"\n🥇 TOP 3 COMBINAÇÕES:\n"
            for i, combo in enumerate(estat['top_3_melhores'][:3], 1):
                relatorio += f"  {i}. {combo['combinacao']}: {combo['eficiencia']:.1f}% ({combo['tentativas']} testes)\n"
        
        # Sugestões
        sugestoes = self.sistema_otimizacao.sugerir_melhoria_estrategia(self)
        if sugestoes:
            relatorio += f"\n💡 SUGESTÕES DE MELHORIA:\n"
            for sugestao in sugestoes:
                relatorio += f"• {sugestao}\n"
        
        return relatorio

# =============================
# FUNÇÕES AUXILIARES
# =============================
def tocar_som_moeda():
    st.markdown("""<audio autoplay><source src="" type="audio/mp3"></audio>""", unsafe_allow_html=True)

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
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

# =============================
# FUNÇÃO PARA MOSTRAR COMBINAÇÕES DINÂMICAS
# =============================
def mostrar_combinacoes_dinamicas():
    if 'sistema' not in st.session_state:
        return
        
    sistema = st.session_state.sistema
    
    if hasattr(sistema, 'combinacoes_quentes') and sistema.combinacoes_quentes:
        st.sidebar.subheader("🔥 Combinações Quentes")
        for combo in sistema.combinacoes_quentes[:3]:
            dados = sistema.historico_combinacoes.get(combo, {})
            eff = dados.get('eficiencia', 0)
            total = dados.get('total', 0)
            seq = dados.get('sequencia_acertos', 0)
            st.sidebar.write(f"🎯 {combo[0]}+{combo[1]}: {eff:.1f}% ({seq}✓)")
    
    if hasattr(sistema, 'combinacoes_frias') and sistema.combinacoes_frias:
        st.sidebar.subheader("❌ Combinações Frias")
        for combo in sistema.combinacoes_frias[:3]:
            dados = sistema.historico_combinacoes.get(combo, {})
            eff = dados.get('eficiencia', 0)
            total = dados.get('total', 0)
            st.sidebar.write(f"🚫 {combo[0]}+{combo[1]}: {eff:.1f}%")

# =============================
# FUNÇÃO PARA VERIFICAR INTEGRIDADE DA SESSÃO
# =============================
def verificar_integridade_sessao():
    """Verifica a integridade dos dados da sessão"""
    problemas = []
    
    # Verificar se o sistema existe
    if 'sistema' not in st.session_state:
        problemas.append("❌ Sistema não encontrado na sessão")
        return False, problemas
    
    sistema = st.session_state.sistema
    
    # Verificar atributos essenciais
    atributos_essenciais = [
        'estrategia_zonas',
        'acertos', 'erros', 'historico_desempenho'
    ]
    
    for attr in atributos_essenciais:
        if not hasattr(sistema, attr):
            problemas.append(f"❌ Atributo {attr} não encontrado no sistema")
    
    # Verificar alertas_config
    if 'alertas_config' not in st.session_state:
        problemas.append("❌ alertas_config não encontrado")
        inicializar_config_alertas()
    
    return len(problemas) == 0, problemas

# =============================
# LIMPEZA SEGURA DE SESSÃO
# =============================
def limpar_sessao_confirmada():
    """Limpa todos os dados da sessão com confirmação"""
    try:
        # Guardar apenas alguns dados de configuração
        telegram_token = st.session_state.get('telegram_token', '')
        telegram_chat_id = st.session_state.get('telegram_chat_id', '')
        
        # Limpar session state
        for key in list(st.session_state.keys()):
            if key not in ['telegram_token', 'telegram_chat_id']:
                del st.session_state[key]
        
        # Restaurar configurações
        if telegram_token:
            st.session_state.telegram_token = telegram_token
        if telegram_chat_id:
            st.session_state.telegram_chat_id = telegram_chat_id
        
        # Reinicializar
        inicializar_config_alertas()
        st.session_state.sistema = SistemaRoletaCompleto()
        st.session_state.historico = []
        
        # Remover arquivos
        arquivos = [SESSION_DATA_PATH, HISTORICO_PATH, ML_MODEL_PATH, SCALER_PATH, META_PATH]
        for arquivo in arquivos:
            if os.path.exists(arquivo):
                try:
                    os.remove(arquivo)
                    logging.info(f"🗑️ Removido: {arquivo}")
                except:
                    pass
        
        st.success("✅ Sessão limpa com sucesso! Sistema reinicializado.")
        st.rerun()
        
    except Exception as e:
        logging.error(f"❌ Erro ao limpar sessão: {e}")
        st.error(f"Erro ao limpar sessão: {e}")

# =============================
# APLICAÇÃO STREAMLIT PRINCIPAL
# =============================
st.set_page_config(page_title="IA Roleta — Zonas Otimizadas", layout="centered")
st.title("🎯 IA Roleta — Sistema Zonas Otimizado + AI")

# 1. Primeiro inicializar config de alertas
inicializar_config_alertas()

# 2. Tentar carregar sessão salva
sessao_carregada = False
if os.path.exists(SESSION_DATA_PATH):
    try:
        sessao_carregada = carregar_sessao()
        if sessao_carregada:
            st.toast("✅ Sessão carregada com sucesso", icon="✅")
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
        sessao_carregada = False

# 3. Só então inicializar o sistema se necessário
if "sistema" not in st.session_state:
    if sessao_carregada and 'sistema' in st.session_state:
        # Sistema já foi carregado na função carregar_sessao()
        logging.info("✅ Sistema carregado da sessão")
    else:
        st.session_state.sistema = SistemaRoletaCompleto()
        logging.info("🆕 Sistema criado do zero")

if "historico" not in st.session_state:
    if not sessao_carregada and os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            st.session_state.historico = []
    elif not sessao_carregada:
        st.session_state.historico = []

if "telegram_token" not in st.session_state and not sessao_carregada:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state and not sessao_carregada:
    st.session_state.telegram_chat_id = ""

# Verificar integridade da sessão
integridade_ok, problemas = verificar_integridade_sessao()
if not integridade_ok:
    logging.warning(f"Problemas na sessão: {problemas}")
    st.warning("⚠️ Problemas detectados na sessão. Recriando sistema...")
    st.session_state.sistema = SistemaRoletaCompleto()

# =============================
# INTERFACE STREAMLIT PARA OTIMIZAÇÃO
# =============================
with st.sidebar.expander("🤖 OTIMIZAÇÃO DINÂMICA 90%", expanded=True):
    st.write("**Sistema de Aprendizado por Reforço**")
    
    if 'sistema' in st.session_state:
        sistema = st.session_state.sistema
        
        if hasattr(sistema, 'sistema_otimizacao'):
            # Botão para gerar relatório
            if st.button("📊 Gerar Relatório de Otimização", use_container_width=True):
                relatorio = sistema.get_relatorio_otimizacao()
                st.text_area("Relatório de Otimização", relatorio, height=400)
            
            # Botão para forçar otimização
            if st.button("🔄 Forçar Otimização Agora", use_container_width=True):
                if sistema.historico_desempenho:
                    # Usar último resultado para otimização
                    ultimo_resultado = sistema.historico_desempenho[-1]
                    otimizacao = sistema.sistema_otimizacao.processar_resultado(ultimo_resultado)
                    
                    if otimizacao:
                        st.success(f"✅ Otimização gerada: {otimizacao['acao']}")
                        if otimizacao.get('combinacao_sugerida'):
                            st.info(f"🎯 Sugestão: {otimizacao['combinacao_sugerida']}")
                    else:
                        st.warning("⚠️ Não foi possível gerar otimização")
            
            # Estatísticas rápidas
            if hasattr(sistema, 'contador_otimizacoes_aplicadas'):
                st.write(f"🔄 **Otimizações aplicadas:** {sistema.contador_otimizacoes_aplicadas}")
            
            # Sugestão automática
            if st.button("💡 Obter Sugestão Inteligente", use_container_width=True):
                if hasattr(sistema.sistema_otimizacao, 'sugerir_melhoria_estrategia'):
                    sugestoes = sistema.sistema_otimizacao.sugerir_melhoria_estrategia(sistema)
                    if sugestoes:
                        st.success("🤖 SUGESTÕES DO SISTEMA AI:")
                        for sugestao in sugestoes:
                            st.write(sugestao)
                    else:
                        st.info("ℹ️  O sistema ainda está aprendendo...")
        
        else:
            st.info("🔧 Sistema de otimização em inicialização...")
    
    st.write("---")
    st.write("**🎯 OBJETIVO: 90% DE ACERTOS**")
    st.write("• 🤖 Aprendizado por Reforço")
    st.write("• 📊 Análise de padrões em tempo real")
    st.write("• 🎯 Otimização dinâmica de combinações")
    st.write("• ⚡ Adaptação automática à mesa")

# Restante do código da aplicação Streamlit continua aqui...
# (A interface do usuário permanece a mesma)

# Sidebar - Configurações Avançadas
st.sidebar.title("⚙️ Configurações")

# Mostrar combinações dinâmicas
mostrar_combinacoes_dinamicas()

# Gerenciamento de Sessão
with st.sidebar.expander("💾 Gerenciamento de Sessão", expanded=False):
    st.write("**Persistência de Dados**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salvar Sessão", use_container_width=True):
            salvar_sessao()
            st.success("✅ Sessão salva!")
            
    with col2:
        if st.button("🔄 Carregar Sessão", use_container_width=True):
            if carregar_sessao():
                st.success("✅ Sessão carregada!")
                st.rerun()
            else:
                st.error("❌ Nenhuma sessão salva encontrada")
    
    st.write("---")
    
    st.write("**📊 Gerenciar Estatísticas**")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Estatísticas recentes resetadas!")
            st.rerun()
            
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
            if st.checkbox("Confirmar zerar TODAS as estatísticas"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Todas as estatísticas foram zeradas!")
                st.rerun()
    
    st.write("---")
    
    if st.button("🗑️ Limpar TODOS os Dados", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar limpeza total de todos os dados"):
            limpar_sessao()
            st.error("🗑️ Todos os dados foram limpos!")
            st.stop()

# Configurações dos Alertas - Checkboxes
with st.sidebar.expander("🔔 Configuração de Alertas", expanded=False):
    st.write("**Selecione quais alertas deseja receber:**")
    
    # Usar o estado salvo ou valores padrão
    alertas_config = st.session_state.get('alertas_config', {
        'alertas_previsao': True,
        'alertas_resultado': True,
        'alertas_rotacao': True,
        'alertas_tendencia': True,
        'alertas_treinamento': True,
        'alertas_erros': True,
        'alertas_acertos': True
    })
    
    # Checkboxes individuais
    col1, col2 = st.columns(2)
    
    with col1:
        alertas_previsao = st.checkbox(
            "🎯 Previsões", 
            value=alertas_config.get('alertas_previsao', True),
            help="Alertas de novas previsões"
        )
        
        alertas_resultado = st.checkbox(
            "📊 Resultados", 
            value=alertas_config.get('alertas_resultado', True),
            help="Alertas de resultados dos sorteios"
        )
        
        alertas_rotacao = st.checkbox(
            "🔄 Rotações", 
            value=alertas_config.get('alertas_rotacao', True),
            help="Alertas de rotação automática"
        )
        
        alertas_tendencia = st.checkbox(
            "📈 Tendências", 
            value=alertas_config.get('alertas_tendencia', True),
            help="Alertas de mudança de tendência"
        )
    
    with col2:
        alertas_treinamento = st.checkbox(
            "🧠 Treinamentos", 
            value=alertas_config.get('alertas_treinamento', True),
            help="Alertas de treinamento ML"
        )
        
        alertas_acertos = st.checkbox(
            "✅ Acertos", 
            value=alertas_config.get('alertas_acertos', True),
            help="Alertas quando acertar"
        )
        
        alertas_erros = st.checkbox(
            "❌ Erros", 
            value=alertas_config.get('alertas_erros', True),
            help="Alertas quando errar"
        )
    
    # Botões para seleção rápida
    st.write("**Seleção Rápida:**")
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("✅ Todos", use_container_width=True):
            st.session_state.alertas_config = {
                'alertas_previsao': True,
                'alertas_resultado': True,
                'alertas_rotacao': True,
                'alertas_tendencia': True,
                'alertas_treinamento': True,
                'alertas_erros': True,
                'alertas_acertos': True
            }
            st.success("✅ Todos os alertas ativados!")
            st.rerun()
    
    with col_btn2:
        if st.button("❌ Nenhum", use_container_width=True):
            st.session_state.alertas_config = {
                'alertas_previsao': False,
                'alertas_resultado': False,
                'alertas_rotacao': False,
                'alertas_tendencia': False,
                'alertas_treinamento': False,
                'alertas_erros': False,
                'alertas_acertos': False
            }
            st.warning("❌ Todos os alertas desativados!")
            st.rerun()
    
    with col_btn3:
        if st.button("💾 Salvar", use_container_width=True):
            # Atualizar configurações
            st.session_state.alertas_config = {
                'alertas_previsao': alertas_previsao,
                'alertas_resultado': alertas_resultado,
                'alertas_rotacao': alertas_rotacao,
                'alertas_tendencia': alertas_tendencia,
                'alertas_treinamento': alertas_treinamento,
                'alertas_erros': alertas_erros,
                'alertas_acertos': alertas_acertos
            }
            
            # Salvar na sessão
            salvar_sessao()
            st.success("✅ Configurações de alertas salvas!")

# Configurações do Telegram
with st.sidebar.expander("🔔 Configurações do Telegram", expanded=False):
    st.write("Configure as notificações do Telegram")
    
    telegram_token = st.text_input(
        "Bot Token do Telegram:",
        value=st.session_state.telegram_token,
        type="password",
        help="Obtenha com @BotFather no Telegram"
    )
    
    telegram_chat_id = st.text_input(
        "Chat ID do Telegram:",
        value=st.session_state.telegram_chat_id,
        help="Obtenha com @userinfobot no Telegram"
    )
    
    if st.button("Salvar Configurações Telegram"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Configurações do Telegram salvas!")
        
    if st.button("Testar Conexão Telegram"):
        if telegram_token and telegram_chat_id:
            try:
                enviar_telegram("🔔 Teste de conexão - IA Roleta funcionando!")
                st.success("✅ Mensagem de teste enviada para Telegram!")
            except Exception as e:
                st.error(f"❌ Erro ao enviar mensagem: {e}")
        else:
            st.error("❌ Preencha token e chat ID primeiro")

# Configurações dos Alertas Alternativos
with st.sidebar.expander("🔔 Alertas Alternativos", expanded=False):
    st.write("**Alertas Simplificados do Telegram**")
    
    st.info("""
    **📱 Alertas Ativados:**
    - 🔔 **Alerta de Aposta:** Números em 2 linhas
    - 📢 **Alerta de Resultado:** Confirmação simples
    - 🎯 **Previsão Detalhada:** Mensagem completa
    """)
    
    alertas_alternativos = st.checkbox(
        "Ativar Alertas Simplificados", 
        value=True,
        help="Envia alertas super simples junto com os detalhados"
    )
    
    if not alertas_alternativos:
        st.warning("⚠️ Alertas simplificados desativados")
    
    if st.button("Testar Alertas Simplificados"):
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            previsao_teste = {
                'nome': 'Zonas Teste',
                'numeros_apostar': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                'zonas_envolvidas': ['Vermelha']
            }
            
            try:
                enviar_alerta_numeros_simplificado(previsao_teste)
                st.success("✅ Alerta simplificado de teste enviado!")
            except Exception as e:
                st.error(f"❌ Erro: {e}")
        else:
            st.error("❌ Configure o Telegram primeiro")

# Status da Rotação Automática
with st.sidebar.expander("🔄 Rotação Automática", expanded=True):
    status_rotacao = st.session_state.sistema.get_status_rotacao()
    
    st.write("**Sistema de Rotação:**")
    st.write(f"🎯 **Estratégia Atual:** {status_rotacao['estrategia_atual']}")
    st.write(f"✅ **Acertos Seguidos:** {status_rotacao['sequencia_acertos']}/3")
    st.write(f"❌ **Erros Seguidos:** {status_rotacao['sequencia_erros']}/2")
    st.write(f"🔥 **Combinações Quentes:** {status_rotacao['combinacoes_quentes']}")
    st.write(f"❄️ **Combinações Frias:** {status_rotacao['combinacoes_frias']}")
    
    if status_rotacao['ultimas_combinacoes_acerto']:
        st.write(f"📊 **Últimas Combinações que Acertaram:**")
        for combo in status_rotacao['ultimas_combinacoes_acerto']:
            nucleos = []
            for zona in combo:
                if zona == 'Vermelha': nucleos.append("7")
                elif zona == 'Azul': nucleos.append("10")
                elif zona == 'Amarela': nucleos.append("2")
                else: nucleos.append(zona)
            st.write(f"   • {'+'.join(nucleos)}")
    
    st.write("---")
    st.write("**🎯 NOVAS Regras de Rotação:**")
    st.write("• 🚨 **QUALQUER combinação com 2 erros seguidos:** Troca para outra combinação")
    st.write("• ✅ **3 Acertos Seguidos na MESMA combinação:** Rota para OUTRAS combinações")
    st.write("• 🔄 **Combinações disponíveis:** Vermelho+Azul, Vermelho+Amarelo, Azul+Amarelo")
    
    # Botão para forçar rotação manual
    if st.button("🔄 Forçar Rotação", use_container_width=True):
        estrategia_atual = st.session_state.sistema.estrategia_selecionada
        # No sistema simplificado, apenas alterna entre combinações
        combinacoes_disponiveis = [
            ('Vermelha', 'Azul'),
            ('Vermelha', 'Amarela'),
            ('Azul', 'Amarela')
        ]
        
        import random
        nova_combinacao = random.choice(combinacoes_disponiveis)
        if st.session_state.sistema.criar_previsao_com_combinacao(nova_combinacao):
            st.success(f"🔄 Rotação forçada para combinação: {nova_combinacao[0]}+{nova_combinacao[1]}")
            st.rerun()
    
    # Debug da Rotação
    with st.sidebar.expander("🐛 Debug - Rotação", expanded=False):
        if st.button("🔍 Ver Debug Rotação"):
            debug_info = st.session_state.sistema.get_debug_rotacao()
            st.json(debug_info)
        
        if st.button("📋 Log Rotação", use_container_width=True):
            # Mostrar últimas 5 rotações
            rotacoes = []
            for i, resultado in enumerate(st.session_state.sistema.historico_desempenho[-10:]):
                if resultado.get('rotacionou', False):
                    rotacoes.append(f"Rodada {len(st.session_state.sistema.historico_desempenho)-i}: {resultado}")
            
            if rotacoes:
                st.write("Últimas rotações:")
                for rotacao in rotacoes[-5:]:
                    st.write(rotacao)
            else:
                st.write("Nenhuma rotação recente registrada")

# Informações sobre as Estratégias
with st.sidebar.expander("📊 Informações das Estratégias"):
    info_zonas = st.session_state.sistema.estrategia_zonas.get_info_zonas()
    st.write("**🎯 EstratEGIA Zonas v6 com APRENDIZADO POR REFORÇO:**")
    st.write("**CONFIGURAÇÃO:** 6 antes + 6 depois (13 números/zona)")
    st.write("**OTIMIZAÇÕES:**")
    st.write("- 📊 Histórico: 70 números")
    st.write("- 🎯 Múltiplas janelas: Curto(12) Médio(24) Longo(48)")
    st.write("- 📈 Threshold dinâmico por performance")
    st.write("- 🔄 **APRENDIZADO DINÂMICO:** Combinações que funcionam no momento")
    st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 10 números selecionados automaticamente")
    st.write("- 🚨 **REGRA UNIVERSAL:** Qualquer combinação com 2 erros seguidos → Troca imediata")
    st.write("- 🤖 **SISTEMA AI:** Aprendizado por reforço para otimização automática")
    st.write("- ⚡ **OTIMIZAÇÃO DINÂMICA:** Adaptação em tempo real às tendências")
    for zona, dados in info_zonas.items():
        st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
        st.write(f"Descrição: {dados['descricao']}")
        st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
        st.write(f"Total: {dados['quantidade']} números")
        st.write("---")

# Análise detalhada
with st.sidebar.expander(f"🔍 Análise - Zonas", expanded=False):
    analise = st.session_state.sistema.estrategia_zonas.get_analise_detalhada()
    st.text(analise)

# Entrada manual
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Digite números (0-36) separados por espaço:")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(n)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# Atualização automática
st_autorefresh(interval=3000, key="refresh")

# Buscar resultado da API
resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else:
    ultimo_ts = None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    numero_atual = resultado.get("number")
    if numero_atual is not None:
        st.session_state.historico.append(resultado)
        st.session_state.sistema.processar_novo_numero(resultado)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

# Interface principal
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(numeros_str)
else:
    st.write("Nenhum número registrado")

# Status da Rotação na Interface Principal
status_rotacao = st.session_state.sistema.get_status_rotacao()
col_status1, col_status2, col_status3, col_status4 = st.columns(4)
with col_status1:
    st.metric("🎯 Estratégia Atual", status_rotacao['estrategia_atual'])
with col_status2:
    st.metric("✅ Acertos Seguidos", f"{status_rotacao['sequencia_acertos']}/3")
with col_status3:
    st.metric("❌ Erros Seguidos", f"{status_rotacao['sequencia_erros']}/2")
with col_status4:
    st.metric("🔄 Próxima Rotação", f"A:{status_rotacao['proxima_rotacao_acertos']} E:{status_rotacao['proxima_rotacao_erros']}")

# NOVA SEÇÃO: ANÁLISE DE TENDÊNCIAS
st.subheader("📈 Análise de Tendências")

tendencia_analise = st.session_state.sistema.get_analise_tendencias_completa()
st.text_area("Estado da Tendência", tendencia_analise, height=400, key="tendencia_analise")

col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.button("🔄 Atualizar Análise de Tendência", use_container_width=True):
        zonas_rankeadas = st.session_state.sistema.estrategia_zonas.get_zonas_rankeadas()
        if zonas_rankeadas:
            analise = st.session_state.sistema.sistema_tendencias.analisar_tendencia(zonas_rankeadas)
            st.success(f"Análise atualizada: {analise['mensagem']}")
            st.rerun()

with col_t2:
    if st.button("📊 Detalhes da Tendência", use_container_width=True):
        resumo = st.session_state.sistema.sistema_tendencias.get_resumo_tendencia()
        st.write("**📊 Detalhes da Tendência:**")
        st.json(resumo)

# ALERTAS VISUAIS DE TENDÊNCIA
if (st.session_state.sistema.sistema_tendencias.historico_tendencias and 
    len(st.session_state.sistema.sistema_tendencias.historico_tendencias) > 0):
    
    ultima_analise = st.session_state.sistema.sistema_tendencias.historico_tendencias[-1]
    
    if ultima_analise['estado'] in ['ativa', 'enfraquecendo', 'morta']:
        enviar_alerta_tendencia(ultima_analise)

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if previsao.get('selecao_inteligente', False):
        st.success("🎯 **SELEÇÃO INTELIGENTE ATIVA** - 10 melhores números selecionados")
        st.info("📊 **Critérios:** Frequência + Posição + Vizinhança + Tendência")
    
    zonas_envolvidas = previsao.get('zonas_envolvidas', [])
    if len(zonas_envolvidas) > 1:
        zona1 = zonas_envolvidas[0]
        zona2 = zonas_envolvidas[1]
        
        nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
        nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
        
        st.write(f"**📍 Núcleos Combinados:** {nucleo1} + {nucleo2}")
        
        combinacao = tuple(sorted([zona1, zona2]))
        dados_combinacao = sistema.historico_combinacoes.get(combinacao, {})
        if dados_combinacao:
            eff = dados_combinacao.get('eficiencia', 0)
            total = dados_combinacao.get('total', 0)
            st.info(f"🏆 **Eficiência da Combinação:** {eff:.1f}% ({dados_combinacao.get('acertos', 0)}/{total})")
        
        st.info("🔄 **ESTRATÉGIA DUPLA:** Investindo nas 2 melhores zonas")
    else:
        zona = previsao.get('zona', '')
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
    
    tipo_aposta = previsao.get('tipo', 'unica')
    if tipo_aposta == 'dupla':
        st.success("🎯 **APOSTA DUPLA:** Maior cobertura com 2 zonas combinadas")
    else:
        st.info("🎯 **APOSTA SIMPLES:** Foco em uma zona principal")
    
    st.info("⏳ Aguardando próximo sorteio para conferência...")
else:
    st.info(f"🎲 Analisando padrões (Zonas)...")

# Desempenho
st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
if total > 0:
    taxa = (sistema.acertos / total * 100)
else:
    taxa = 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

# Botões de gerenciamento de estatísticas
st.write("**Gerenciar Estatísticas:**")
col5, col6 = st.columns(2)

with col5:
    if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
        st.session_state.sistema.reset_recente_estatisticas()
        st.success("✅ Estatísticas recentes resetadas!")
        st.rerun()

with col6:
    if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
        if st.checkbox("Confirmar zerar TODAS as estatísticas"):
            st.session_state.sistema.zerar_estatisticas_desempenho()
            st.error("🗑️ Todas as estatísticas foram zeradas!")
            st.rerun()

# Análise detalhada por estratégia
if sistema.estrategias_contador:
    st.write("**📊 Performance por Estratégia:**")
    for nome, dados in sistema.estrategias_contador.items():
        if isinstance(dados, dict) and 'total' in dados and dados['total'] > 0:
            taxa_estrategia = (dados['acertos'] / dados['total'] * 100)
            cor = "🟢" if taxa_estrategia >= 50 else "🟡" if taxa_estrategia >= 30 else "🔴"
            st.write(f"{cor} {nome}: {dados['acertos']}/{dados['total']} ({taxa_estrategia:.1f}%)")
        else:
            st.write(f"⚠️ {nome}: Dados de performance não disponíveis")

# Últimas conferências
if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for i, resultado in enumerate(sistema.historico_desempenho[-5:]):
        emoji = "🎉" if resultado['acerto'] else "❌"
        rotacao_emoji = " 🔄" if resultado.get('rotacionou', False) else ""
        zona_info = ""
        if resultado['acerto'] and resultado.get('zona_acertada'):
            if '+' in resultado['zona_acertada']:
                zonas = resultado['zona_acertada'].split('+')
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
                zona_info = f" (Núcleos {nucleo_str})"
            else:
                if resultado['zona_acertada'] == 'Vermelha':
                    nucleo = "7"
                elif resultado['zona_acertada'] == 'Azul':
                    nucleo = "10"
                elif resultado['zona_acertada'] == 'Amarela':
                    nucleo = "2"
                else:
                    nucleo = resultado['zona_acertada']
                zona_info = f" (Núcleo {nucleo})"
                
        tipo_aposta_info = ""
        if resultado.get('tipo_aposta') == 'dupla':
            tipo_aposta_info = " [DUPLA]"
        
        st.write(f"{emoji}{rotacao_emoji} {resultado['estrategia']}{tipo_aposta_info}: Número {resultado['numero']}{zona_info}")

# Download histórico
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_roleta.json")

# ✅ CORREÇÃO FINAL: Salvar sessão
salvar_sessao()
