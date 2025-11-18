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
            'sistema_combinacoes_frias': st.session_state.sistema.combinacoes_frias
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
# ESTRATÉGIA DAS ZONAS ATUALIZADA - COM APRENDIZADO DINÂMICO DE COMBINAÇões
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
        
        analise += "📊 PERFORMANCE AVANÇADA:\n"
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
            
            # 🎯 ATUALIZAR LISTAS DINÂMICAS
            self.atualizar_combinacoes_quentes_frias()
    
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
                
            # Evitar combinações frias
            if combo_tuple in self.combinacoes_frias:
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
        """Rotação baseada em desempenho de combinações específicas - COM NOVA REGRA DE 3 ACERTOS"""
        
        # Atualizar desempenho da combinação
        self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
        
        if acerto:
            # 🎯 NOVA REGRA: Contar acertos consecutivos
            self.sequencia_acertos += 1
            self.sequencia_erros = 0
            
            # 🎯 NOVA REGRA: Rotação após 3 acertos seguidos na MESMA combinação
            if len(zonas_envolvidas) > 1:
                combinacao_atual = tuple(sorted(zonas_envolvidas))
                
                # 🎯 VERIFICAR SE OS 3 ACERTOS FORAM NA MESMA COMBINAÇÃO
                if self.sequencia_acertos >= 3:
                    # Verificar se os últimos 3 acertos foram na mesma combinação
                    ultimos_3_acertos = []
                    for resultado in reversed(self.historico_desempenho[-3:]):
                        if resultado['acerto'] and resultado.get('zonas_envolvidas'):
                            ultima_combinacao = tuple(sorted(resultado['zonas_envolvidas']))
                            ultimos_3_acertos.append(ultima_combinacao)
                    
                    # Se todos os últimos 3 acertos foram na mesma combinação
                    if (len(ultimos_3_acertos) >= 3 and 
                        all(combo == combinacao_atual for combo in ultimos_3_acertos)):
                        
                        logging.info(f"🎯 3 ACERTOS SEGUIDOS detectados na combinação {combinacao_atual} - Rotacionando para combinações alternativas")
                        return self.aplicar_rotacao_por_acertos_combinacoes(combinacao_atual)
            
            return False
        
        else:
            self.sequencia_erros += 1
            self.sequencia_acertos = 0  # Resetar sequência de acertos
            self.ultima_estrategia_erro = nome_estrategia
            
            # 🎯 ROTAÇÃO RÁPIDA PARA COMBINAÇÕES FRIA
            if len(zonas_envolvidas) > 1:
                combinacao = tuple(sorted(zonas_envolvidas))
                
                if combinacao in self.combinacoes_frias and self.sequencia_erros >= 1:
                    logging.info(f"🚫 Combinação fria detectada: {combinacao} - Rotacionando")
                    return self.aplicar_rotacao_inteligente()
            
            # 🎯 ROTAÇÃO PARA MÁ PERFORMANCE GERAL
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
        
        # 🎯 ESCOLHER A MELHOR COMBINAÇÃO ALTERNATIVA
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

    def criar_previsao_com_combinacao(self, combinacao):
        """Cria uma nova previsão forçada com a combinação especificada"""
        try:
            zonas_list = list(combinacao)
            
            # 🎯 CRIAR PREVISÃO FORÇADA COM A NOVA COMBINAÇÃO
            previsao_forcada = self.estrategia_zonas.criar_previsao_dupla(
                zonas_list[0], 
                zonas_list[1], 
                "ROTAÇÃO-3-ACERTOS"
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

    def escolher_melhor_combinacao_alternativa(self, combinacoes):
        """Escolhe a melhor combinação alternativa baseada em desempenho"""
        if not combinacoes:
            return None
        
        # Tentar encontrar combinações com boa eficiência
        combinacoes_com_dados = []
        combinacoes_sem_dados = []
        
        for combo in combinacoes:
            dados = self.historico_combinacoes.get(combo, {})
            if dados and dados.get('total', 0) > 0:
                combinacoes_com_dados.append((combo, dados))
            else:
                combinacoes_sem_dados.append(combo)
        
        # Priorizar combinações com dados e boa eficiência
        if combinacoes_com_dados:
            # Ordenar por eficiência (melhor primeiro)
            combinacoes_com_dados.sort(key=lambda x: x[1].get('eficiencia', 0), reverse=True)
            melhor_combo = combinacoes_com_dados[0][0]
            
            # Verificar se a eficiência é aceitável
            eficiencia = combinacoes_com_dados[0][1].get('eficiencia', 0)
            if eficiencia >= 25:
                return melhor_combo
        
        # Se não há combinações com boa eficiência, usar uma sem dados
        if combinacoes_sem_dados:
            return combinacoes_sem_dados[0]
        
        # Último recurso: usar a primeira disponível
        return combinacoes[0] if combinacoes else None

    def aplicar_rotacao_inteligente(self):
        """Aplica rotação baseada em aprendizado contínuo"""
        estrategia_atual = self.estrategia_selecionada
        
        # 🎯 SE HÁ COMBINAÇÕES QUENTES, MANTER NA ESTRATÉGIA
        if self.combinacoes_quentes and estrategia_atual == "Zonas":
            logging.info(f"🎯 MANTENDO ZONAS - {len(self.combinacoes_quentes)} combinações quentes")
            self.sequencia_erros = 0
            return False
        
        # Rotação normal
        if estrategia_atual == "Zonas":
            nova_estrategia = "ML"
        else:
            nova_estrategia = "Zonas"
        
        self.estrategia_selecionada = nova_estrategia
        self.sequencia_erros = 0
        
        enviar_rotacao_automatica(estrategia_atual, nova_estrategia)
        logging.info(f"🔄 ROTAÇÃO: {estrategia_atual} → {nova_estrategia}")
        return True

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
        
        # Zerar estatísticas das estratégias
        self.estrategia_zonas.zerar_estatisticas()
        
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
            
            logging.info("🔄 Estatísticas recentes resetadas (mantidos últimos 10 resultados)")
        else:
            logging.info("ℹ️  Histórico muito pequeno para reset recente")
        
        salvar_sessao()

    def get_status_rotacao(self):
        """Retorna o status atual do sistema de rotação - ATUALIZADO COM COMBINAÇÕES"""
        return {
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
    """Mostra as combinações quentes e frias atuais"""
    sistema = st.session_state.sistema
    
    if hasattr(sistema, 'combinacoes_quentes') and sistema.combinacoes_quentes:
        st.sidebar.subheader("🔥 Combinações Quentes")
        for combo in sistema.combinacoes_quentes:
            dados = sistema.historico_combinacoes.get(combo, {})
            eff = dados.get('eficiencia', 0)
            total = dados.get('total', 0)
            seq = dados.get('sequencia_acertos', 0)
            st.sidebar.write(f"🎯 {combo[0]}+{combo[1]}: {eff:.1f}% ({seq}✓)")
    
    if hasattr(sistema, 'combinacoes_frias') and sistema.combinacoes_frias:
        st.sidebar.subheader("❌ Combinações Frias")
        for combo in sistema.combinacoes_frias:
            dados = sistema.historico_combinacoes.get(combo, {})
            eff = dados.get('eficiencia', 0)
            total = dados.get('total', 0)
            st.sidebar.write(f"🚫 {combo[0]}+{combo[1]}: {eff:.1f}%")

# =============================
# APLICAÇÃO STREAMLIT ATUALIZADA
# =============================
st.set_page_config(page_title="IA Roleta — Multi-Estratégias", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias")

# Inicialização com persistência
if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaCompleto()

# Tentar carregar sessão salva
sessao_carregada = carregar_sessao()

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

# Sidebar - Configurações Avançadas
st.sidebar.title("⚙️ Configurações")

# 🎯 NOVO: Mostrar combinações dinâmicas
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
    
    # Botões para zerar estatísticas
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

# Seleção de Estratégia
estrategia = st.sidebar.selectbox(
    "🎯 Selecione a Estratégia:",
    ["Zonas", "Midas", "ML"],
    key="estrategia_selecionada"
)

# Aplicar estratégia selecionada
if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)
    st.toast(f"🔄 Estratégia alterada para: {estrategia}")

# Status da Rotação Automática - ATUALIZADO
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
    st.write("• ✅ **3 Acertos Seguidos na MESMA combinação:** Rota para OUTRAS combinações (NOVO)")
    st.write("• ❌ **2 Erros Seguidos:** Rotação entre Zonas ↔ ML")
    st.write("• 🔄 **Combinações disponíveis:** Vermelho+Azul, Vermelho+Amarelo, Azul+Amarelo")
    
    # Botão para forçar rotação manual
    if st.button("🔄 Forçar Rotação", use_container_width=True):
        estrategia_atual = st.session_state.sistema.estrategia_selecionada
        if estrategia_atual == "Zonas":
            nova_estrategia = "ML"
        else:
            nova_estrategia = "Zonas"
        
        st.session_state.sistema.estrategia_selecionada = nova_estrategia
        st.session_state.sistema.sequencia_erros = 0
        st.session_state.sistema.sequencia_acertos = 0
        st.success(f"🔄 Rotação forçada: {estrategia_atual} → {nova_estrategia}")
        st.rerun()

# Treinamento ML
with st.sidebar.expander("🧠 Treinamento ML", expanded=False):
    numeros_disponiveis = 0
    numeros_lista = []
    
    for item in st.session_state.historico:
        if isinstance(item, dict) and 'number' in item and item['number'] is not None:
            numeros_disponiveis += 1
            numeros_lista.append(item['number'])
        elif isinstance(item, (int, float)) and item is not None:
            numeros_disponiveis += 1
            numeros_lista.append(int(item))
            
    st.write(f"📊 **Números disponíveis:** {numeros_disponiveis}")
    st.write(f"🎯 **Mínimo necessário:** 200 números")
    st.write(f"🔄 **Treinamento automático:** A cada 15 sorteios")
    st.write(f"🤖 **Modelo:** CatBoost (mais preciso)")
    st.write(f"🎯 **Ensemble:** 3 modelos")
    
    if numeros_disponiveis > 0:
        numeros_unicos = len(set(numeros_lista))
        st.write(f"🎲 **Números únicos:** {numeros_unicos}/37")
        
        if numeros_unicos < 10:
            st.warning(f"⚠️ **Pouca variedade:** Necessário pelo menos 10 números diferentes")
        else:
            st.success(f"✅ **Variedade adequada:** {numeros_unicos} números diferentes")
    
    st.write(f"✅ **Status:** {'Dados suficientes' if numeros_disponiveis >= 200 else 'Coletando dados...'}")
    
    if numeros_disponiveis >= 200:
        st.success("✨ **Pronto para treinar!**")
        
        if st.button("🚀 Treinar Modelo ML", type="primary", use_container_width=True):
            with st.spinner("Treinando modelo ML com CatBoost... Isso pode levar alguns segundos"):
                try:
                    success, message = st.session_state.sistema.treinar_modelo_ml(numeros_lista)
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                    else:
                        st.error(f"❌ {message}")
                except Exception as e:
                    st.error(f"💥 Erro no treinamento: {str(e)}")
    
    else:
        st.warning(f"📥 Colete mais {200 - numeros_disponiveis} números para treinar o ML")
        
    st.write("---")
    st.write("**Status do ML:**")
    if st.session_state.sistema.estrategia_ml.ml.is_trained:
        if st.session_state.sistema.estrategia_ml.ml.models:
            primeiro_modelo = st.session_state.sistema.estrategia_ml.ml.models[0]
            modelo_tipo = "CatBoost" if hasattr(primeiro_modelo, 'iterations') else "RandomForest"
        else:
            modelo_tipo = "Não treinado"
            
        st.success(f"✅ Modelo {modelo_tipo} treinado ({st.session_state.sistema.estrategia_ml.ml.contador_treinamento} vezes)")
        if 'last_accuracy' in st.session_state.sistema.estrategia_ml.ml.meta:
            acc = st.session_state.sistema.estrategia_ml.ml.meta['last_accuracy']
            st.info(f"📊 Última acurácia: {acc:.2%}")
        st.info(f"🔄 Próximo treinamento automático em: {15 - st.session_state.sistema.estrategia_ml.contador_sorteios} sorteios")
        st.info(f"🎯 Ensemble: {len(st.session_state.sistema.estrategia_ml.ml.models)} modelos ativos")
    else:
        st.info("🤖 ML aguardando treinamento")

# Estatísticas de Padrões ML
with st.sidebar.expander("🔍 Estatísticas de Padrões ML", expanded=False):
    if st.session_state.sistema.estrategia_selecionada == "ML":
        estatisticas_padroes = st.session_state.sistema.estrategia_ml.get_estatisticas_padroes()
        st.text(estatisticas_padroes)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("🔄 Zerar Padrões", use_container_width=True):
                st.session_state.sistema.estrategia_ml.zerar_padroes()
                st.success("✅ Padrões zerados!")
                st.rerun()
                
        with col_p2:
            if st.button("📊 Atualizar Métricas", use_container_width=True):
                st.rerun()
    else:
        st.info("🔍 Ative a estratégia ML para ver estatísticas de padrões")

# Informações sobre as Estratégias
with st.sidebar.expander("📊 Informações das Estratégias"):
    if estrategia == "Zonas":
        info_zonas = st.session_state.sistema.estrategia_zonas.get_info_zonas()
        st.write("**🎯 Estratégia Zonas v6:**")
        st.write("**CONFIGURAÇÃO:** 6 antes + 6 depois (13 números/zona)")
        st.write("**OTIMIZAÇÕES:**")
        st.write("- 📊 Histórico: 70 números")
        st.write("- 🎯 Múltiplas janelas: Curto(12) Médio(24) Longo(48)")
        st.write("- 📈 Threshold dinâmico por performance")
        st.write("- 🔄 **APRENDIZADO DINÂMICO:** Combinações que funcionam no momento")
        st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 15 números selecionados automaticamente")
        st.write("- 🎯 **NOVA REGRA:** 3 acertos seguidos → Rota para outras combinações")
        for zona, dados in info_zonas.items():
            st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
            st.write(f"Descrição: {dados['descricao']}")
            st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
            st.write(f"Total: {dados['quantidade']} números")
            st.write("---")
    
    elif estrategia == "Midas":
        st.write("**🎯 Estratégia Midas:**")
        st.write("Padrões baseados em terminais:")
        st.write("- **Terminal 0**: 0, 10, 20, 30")
        st.write("- **Terminal 7**: 7, 17, 27") 
        st.write("- **Terminal 5**: 5, 15, 25, 35")
        st.write("---")
    
    elif estrategia == "ML":
        st.write("**🤖 Estratégia Machine Learning - CATBOOST OTIMIZADO:**")
        st.write("- **Modelo**: CatBoost (Gradient Boosting)")
        st.write("- **Ensemble**: 3 modelos")
        st.write("- **Amostras mínimas**: 200")
        st.write("- **Histórico máximo**: 1000 números")
        st.write("- **Treinamento**: A cada 15 sorteios")
        st.write("- **Janelas**: [3, 8, 15, 30, 60, 120]")
        st.write("- **Zonas**: 6 antes + 6 depois (13 números/zona)")
        st.write("- **Threshold**: Mínimo 7 números na mesma zona")
        st.write("- **Saída**: Zona com maior concentração")
        st.write("- 🔄 **APRENDIZADO DINÂMICO:** Combinações que funcionam no momento")
        st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 15 números selecionados automaticamente")
        
        info_zonas_ml = st.session_state.sistema.estrategia_ml.get_info_zonas_ml()
        for zona, dados in info_zonas_ml.items():
            st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
            st.write(f"Descrição: {dados['descricao']}")
            st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
            st.write(f"Total: {dados['quantidade']} números")
            st.write("---")

# Análise detalhada
with st.sidebar.expander(f"🔍 Análise - {estrategia}", expanded=False):
    if estrategia == "Zonas":
        analise = st.session_state.sistema.estrategia_zonas.get_analise_detalhada()
    elif estrategia == "ML":
        analise = st.session_state.sistema.estrategia_ml.get_analise_ml()
    else:
        analise = "🎯 Estratégia Midas ativa\nAnalisando padrões de terminais..."
    
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

# Status da Rotação na Interface Principal - ATUALIZADO
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

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if previsao.get('selecao_inteligente', False):
        st.success("🎯 **SELEÇÃO INTELIGENTE ATIVA** - 15 melhores números selecionados")
        st.info("📊 **Critérios:** Frequência + Posição + Vizinhança + Tendência")
    
    if 'Zonas' in previsao['nome']:
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
            
    elif 'ML' in previsao['nome']:
        zonas_envolvidas = previsao.get('zonas_envolvidas', [])
        if len(zonas_envolvidas) > 1:
            zona1 = zonas_envolvidas[0]
            zona2 = zonas_envolvidas[1]
            
            nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
            nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
            
            st.write(f"**🤖 Núcleos Combinados:** {nucleo1} + {nucleo2}")
            st.info("🔄 **ESTRATÉGIA DUPLA:** Investindo nas 2 melhores zonas")
        else:
            zona_ml = previsao.get('zona_ml', '')
            if zona_ml == 'Vermelha':
                nucleo = "7"
            elif zona_ml == 'Azul':
                nucleo = "10"
            elif zona_ml == 'Amarela':
                nucleo = "2"
            else:
                nucleo = zona_ml
            st.write(f"**🤖 Núcleo:** {nucleo}")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    st.write(", ".join(map(str, sorted(previsao['numeros_apostar']))))
    
    if 'ML' in previsao['nome'] and previsao.get('padroes_aplicados', 0) > 0:
        st.info(f"🔍 **Padrões aplicados:** {previsao['padroes_aplicados']} padrões sequenciais detectados")
    
    tipo_aposta = previsao.get('tipo', 'unica')
    if tipo_aposta == 'dupla':
        st.success("🎯 **APOSTA DUPLA:** Maior cobertura com 2 zonas combinadas")
    else:
        st.info("🎯 **APOSTA SIMPLES:** Foco em uma zona principal")
    
    st.info("⏳ Aguardando próximo sorteio para conferência...")
else:
    st.info(f"🎲 Analisando padrões ({estrategia})...")

# Desempenho
st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

# Botões de gerenciamento de estatísticas na seção de desempenho
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
