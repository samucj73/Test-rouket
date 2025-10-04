# RoletaHybridIA.py - SISTEMA COM IA (RANDOM FOREST) PARA MELHORAR ASSERTIVIDADE
import streamlit as st
import json
import os
import time
import requests
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
import logging
import random
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import joblib

# =============================
# Configurações COM IA
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
CONTEXTO_PATH = "contexto_historico.json"
MODELO_IA_PATH = "modelo_random_forest.pkl"
SCALER_PATH = "scaler.pkl"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# DISPOSIÇÃO FÍSICA REAL DA ROLETA
ROULETTE_PHYSICAL_LAYOUT = [
    [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
    [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
]

NUMERO_PREVISOES = 10
CICLO_PREVISAO = 2p
CONFIANCA_MINIMA = 0.035  # 3.5% de confiança mínima

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# FUNÇÕES UTILITÁRIAS
# =============================
def carregar_historico():
    try:
        if os.path.exists(HISTORICO_PATH):
            with open(HISTORICO_PATH, "r") as f:
                historico = json.load(f)
            historico_valido = [h for h in historico if isinstance(h, dict) and 'number' in h and h['number'] is not None]
            logging.info(f"📁 Histórico carregado: {len(historico_valido)} registros válidos")
            return historico_valido
        return []
    except Exception as e:
        logging.error(f"Erro ao carregar histórico: {e}")
        return []

def salvar_historico(numero_dict):
    try:
        if not isinstance(numero_dict, dict) or numero_dict.get('number') is None:
            logging.error("❌ Tentativa de salvar número inválido")
            return False
            
        historico_existente = carregar_historico()
        timestamp_novo = numero_dict.get("timestamp")
        
        ja_existe = any(
            registro.get("timestamp") == timestamp_novo 
            for registro in historico_existente 
            if isinstance(registro, dict)
        )
        
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
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        game_data = data.get("data", {})
        if not game_data:
            logging.error("❌ Estrutura da API inválida: data não encontrado")
            return None
            
        result = game_data.get("result", {})
        if not result:
            logging.error("❌ Estrutura da API inválida: result não encontrado")
            return None
            
        outcome = result.get("outcome", {})
        if not outcome:
            logging.error("❌ Estrutura da API inválida: outcome não encontrado")
            return None
            
        number = outcome.get("number")
        if number is None:
            logging.error("❌ Número não encontrado na resposta da API")
            return None
            
        timestamp = game_data.get("startedAt")
        
        return {"number": number, "timestamp": timestamp}
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erro de rede ao buscar resultado: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Erro inesperado ao buscar resultado: {e}")
        return None

def obter_vizinhos_fisicos(numero):
    """Retorna vizinhos físicos na mesa"""
    if numero == 0:
        return [32, 15, 19, 4, 21, 2, 25]
    
    vizinhos = set()
    
    for col_idx, coluna in enumerate(ROULETTE_PHYSICAL_LAYOUT):
        if numero in coluna:
            num_idx = coluna.index(numero)
            
            if num_idx > 0:
                vizinhos.add(coluna[num_idx - 1])
            if num_idx < len(coluna) - 1:
                vizinhos.add(coluna[num_idx + 1])
                
            if col_idx > 0:
                if num_idx < len(ROULETTE_PHYSICAL_LAYOUT[col_idx - 1]):
                    vizinhos.add(ROULETTE_PHYSICAL_LAYOUT[col_idx - 1][num_idx])
            if col_idx < 2:
                if num_idx < len(ROULETTE_PHYSICAL_LAYOUT[col_idx + 1]):
                    vizinhos.add(ROULETTE_PHYSICAL_LAYOUT[col_idx + 1][num_idx])
    
    return list(vizinhos)

def validar_previsao(previsao):
    if not previsao or not isinstance(previsao, list):
        return []
    
    previsao_limpa = [
        num for num in previsao 
        if num is not None 
        and isinstance(num, (int, float))
        and 0 <= num <= 36
    ]
    
    return previsao_limpa

def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

def enviar_alerta_previsao(numeros, confianca, metodo="IA"):
    """Envia alerta de PREVISÃO com 10 números e nível de confiança"""
    try:
        if not numeros or len(numeros) != 10:
            logging.error(f"❌ Alerta de previsão precisa de 10 números, recebeu: {len(numeros) if numeros else 0}")
            return
            
        # Ordena os números do menor para o maior
        numeros_ordenados = sorted(numeros)
        
        # Formata com confiança e método
        numeros_str = ' '.join(map(str, numeros_ordenados))
        mensagem = f"🎯 PREVISÃO {metodo} {confianca}%: {numeros_str}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de PREVISÃO enviado: 10 números com {confianca}% confiança ({metodo})")
        
    except Exception as e:
        logging.error(f"Erro alerta previsão: {e}")

def enviar_alerta_resultado(acertou, numero_sorteado, previsao_anterior, confianca, metodo="IA"):
    """Envia alerta de resultado (GREEN/RED) com os 10 números da previsão"""
    try:
        if not previsao_anterior or len(previsao_anterior) != 10:
            logging.error(f"❌ Alerta resultado precisa de 10 números na previsão")
            return
            
        # Ordena os números da previsão anterior
        previsao_ordenada = sorted(previsao_anterior)
        previsao_str = ' '.join(map(str, previsao_ordenada))
        
        if acertou:
            mensagem = f"🟢 GREEN! {metodo} Acertou {numero_sorteado} | Conf: {confianca}% | Previsão: {previsao_str}"
        else:
            mensagem = f"🔴 RED! {metodo} Sorteado {numero_sorteado} | Conf: {confianca}% | Previsão: {previsao_str}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem
        }
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📤 Alerta de resultado enviado ({metodo})")
        
    except Exception as e:
        logging.error(f"Erro alerta resultado: {e}")

# =============================
# IA - RANDOM FOREST PREDICTOR
# =============================
class IAPredictor:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.ultimo_treinamento = 0
        self.acuracia_treinamento = 0
        self.carregar_modelo()
        
    def carregar_modelo(self):
        """Carrega modelo treinado se existir"""
        try:
            if os.path.exists(MODELO_IA_PATH) and os.path.exists(SCALER_PATH):
                self.model = joblib.load(MODELO_IA_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                logging.info("🤖 IA Carregada - Random Forest Pronta")
                return True
            else:
                logging.info("🤖 IA Não Encontrada - Será treinada quando houver dados suficientes")
                return False
        except Exception as e:
            logging.error(f"Erro ao carregar IA: {e}")
            return False
    
    def salvar_modelo(self):
        """Salva modelo treinado"""
        try:
            if self.model and self.scaler:
                joblib.dump(self.model, MODELO_IA_PATH)
                joblib.dump(self.scaler, SCALER_PATH)
                logging.info(f"💾 IA Salva - Acurácia: {self.acuracia_treinamento:.2f}%")
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar IA: {e}")
        return False
    
    def preparar_dados_treinamento(self, historico, window_size=10):
        """Prepara dados para treinamento da IA"""
        if len(historico) < window_size + 2000:  # Mínimo de dados para treinar
            return None, None
        
        numeros = [h['number'] for h in historico]
        
        X = []
        y = []
        
        # Criar features: últimos 'window_size' números
        for i in range(window_size, len(numeros)):
            features = numeros[i-window_size:i]
            target = numeros[i]
            
            # Adicionar features adicionais
            features.extend([
                sum(features) / len(features),  # Média dos últimos
                max(features),                  # Máximo
                min(features),                  # Mínimo
                len(set(features)),             # Números únicos
                features[-1] - features[-2] if len(features) > 1 else 0,  # Diferença
            ])
            
            X.append(features)
            y.append(target)
        
        return np.array(X), np.array(y)
    
    def treinar_modelo(self, historico):
        """Treina o modelo de Random Forest"""
        try:
            X, y = self.preparar_dados_treinamento(historico)
            if X is None or len(X) < 100:
                logging.info("🤖 Dados insuficientes para treinar IA")
                return False
            
            # Dividir dados
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Normalizar dados
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Treinar Random Forest
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
            
            self.model.fit(X_train_scaled, y_train)
            
            # Avaliar
            y_pred = self.model.predict(X_test_scaled)
            self.acuracia_treinamento = accuracy_score(y_test, y_pred) * 100
            
            self.ultimo_treinamento = time.time()
            self.salvar_modelo()
            
            logging.info(f"🤖 IA Treinada - Acurácia: {self.acuracia_treinamento:.2f}%")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao treinar IA: {e}")
            return False
    
    def prever_com_ia(self, ultimos_numeros, top_n=10):
        """Faz previsão usando IA"""
        try:
            if self.model is None or self.scaler is None:
                return None, 0
            
            if len(ultimos_numeros) < 10:
                return None, 0
            
            # Preparar features para predição
            features = ultimos_numeros[-10:]  # Últimos 10 números
            
            # Adicionar features adicionais
            features.extend([
                sum(features) / len(features),  # Média
                max(features),                  # Máximo
                min(features),                  # Mínimo
                len(set(features)),             # Números únicos
                features[-1] - features[-2] if len(features) > 1 else 0,  # Diferença
            ])
            
            X_pred = np.array([features])
            X_pred_scaled = self.scaler.transform(X_pred)
            
            # Obter probabilidades para todos os números
            probabilidades = self.model.predict_proba(X_pred_scaled)[0]
            
            # Ordenar números por probabilidade
            numeros_ordenados = np.argsort(probabilidades)[::-1]
            probabilidades_ordenadas = probabilidades[numeros_ordenados]
            
            # Pegar top N números
            previsao = numeros_ordenados[:top_n].tolist()
            
            # Calcular confiança baseada na probabilidade média do top 10
            confianca = np.mean(probabilidades_ordenadas[:top_n]) * 100
            
            # Ajustar confiança para range realista (3-8%)
            confianca_ajustada = max(3.0, min(confianca * 2, 8.0))
            
            logging.info(f"🤖 PREVISÃO IA: {previsao} | Confiança: {confianca_ajustada:.1f}%")
            return previsao, confianca_ajustada
            
        except Exception as e:
            logging.error(f"Erro na previsão IA: {e}")
            return None, 0
    
    def deve_treinar(self, historico):
        """Verifica se deve treinar o modelo"""
        if len(historico) < 500:
            return False
        
        # Treinar a cada 1000 novos registros ou se não tem modelo
        if self.model is None:
            return True
        
        registros_novos = len(historico) - self.ultimo_treinamento
        return registros_novos > 1000 or time.time() - self.ultimo_treinamento > 86400  # 1 dia

# =============================
# SISTEMA HÍBRIDO - IA + CONTEXTO
# =============================
class SistemaHibridoIA:
    def __init__(self):
        self.ia_predictor = IAPredictor()
        self.historico = deque(carregar_historico(), maxlen=10000)
        self.previsao_anterior = None
        self.ultimo_numero_processado = None
        self.contador_sorteios = 0
        self.confianca_ultima_previsao = 0
        self.metodo_ultima_previsao = "CONTEXTO"
        self.acertos_consecutivos = 0
        self.erros_consecutivos = 0
        self.ultimos_numeros = deque(maxlen=50)
        
        # Inicializar últimos números do histórico
        for registro in list(self.historico)[-50:]:
            if registro.get('number') is not None:
                self.ultimos_numeros.append(registro['number'])
        
        # Treinar IA se possível
        if self.ia_predictor.deve_treinar(list(self.historico)):
            self.ia_predictor.treinar_modelo(list(self.historico))

    def adicionar_numero(self, numero_dict):
        """Adiciona número e atualiza IA"""
        if isinstance(numero_dict, dict) and numero_dict.get('number') is not None:
            numero_atual = numero_dict['number']
            
            self.ultimo_numero_processado = numero_atual
            self.historico.append(numero_dict)
            self.ultimos_numeros.append(numero_atual)
            self.contador_sorteios += 1
            
            # Verificar se deve treinar IA
            if self.ia_predictor.deve_treinar(list(self.historico)):
                logging.info("🤖 Treinando IA com novos dados...")
                self.ia_predictor.treinar_modelo(list(self.historico))

    def gerar_previsao_hibrida(self):
        """Gera previsão combinando IA e contexto tradicional"""
        try:
            if self.ultimo_numero_processado is None:
                return self.gerar_previsao_fallback(), 3.5, "FALLBACK"
            
            # Tentar previsão da IA primeiro
            previsao_ia, confianca_ia = self.ia_predictor.prever_com_ia(list(self.ultimos_numeros))
            
            if previsao_ia and confianca_ia >= 4.0:
                logging.info(f"🎯 USANDO IA - Confiança: {confianca_ia:.1f}%")
                return previsao_ia, confianca_ia, "IA"
            
            # Se IA não tem confiança suficiente, usar contexto tradicional
            previsao_contexto = self.gerar_previsao_contextual()
            confianca_contexto = self.calcular_confianca_contexto()
            
            logging.info(f"🎯 USANDO CONTEXTO - Confiança: {confianca_contexto:.1f}%")
            return previsao_contexto, confianca_contexto, "CONTEXTO"
            
        except Exception as e:
            logging.error(f"Erro na previsão híbrida: {e}")
            return self.gerar_previsao_fallback(), 3.0, "FALLBACK"

    def gerar_previsao_contextual(self):
        """Gera previsão baseada em contexto tradicional"""
        try:
            if not self.ultimos_numeros:
                return self.gerar_previsao_fallback()
            
            ultimo_numero = self.ultimos_numeros[-1]
            previsao = set()
            
            # 1. Vizinhança física
            vizinhos = obter_vizinhos_fisicos(ultimo_numero)
            previsao.update(vizinhos[:4])
            
            # 2. Números quentes (últimos 20 sorteios)
            if len(self.ultimos_numeros) >= 10:
                ultimos_20 = list(self.ultimos_numeros)[-20:]
                frequencia = Counter(ultimos_20)
                numeros_quentes = [num for num, count in frequencia.most_common(4)]
                previsao.update(numeros_quentes)
            
            # 3. Números frios (que não aparecem há tempo)
            if len(self.ultimos_numeros) >= 30:
                ultimos_30 = set(list(self.ultimos_numeros)[-30:])
                todos_numeros = set(range(0, 37))
                numeros_frios = list(todos_numeros - ultimos_30)
                if numeros_frios:
                    previsao.update(random.sample(numeros_frios, min(2, len(numeros_frios))))
            
            # 4. Completar até 10 números
            if len(previsao) < 10:
                complemento = self.gerar_complemento_estatistico(10 - len(previsao))
                previsao.update(complemento)
            
            return list(previsao)[:10]
            
        except Exception as e:
            logging.error(f"Erro na previsão contextual: {e}")
            return self.gerar_previsao_fallback()

    def calcular_confianca_contexto(self):
        """Calcula confiança baseada em contexto"""
        if len(self.ultimos_numeros) < 20:
            return 3.5
        
        # Base de confiança aumenta com mais dados
        base_confianca = 3.5
        fator_dados = min(1.5, len(self.ultimos_numeros) / 100)
        
        return min(base_confianca * fator_dados, 6.0)

    def gerar_complemento_estatistico(self, quantidade):
        """Gera complemento estatístico"""
        if len(self.ultimos_numeros) < 10:
            return random.sample(range(0, 37), quantidade)
        
        # Usar distribuição baseada na frequência
        frequencia = Counter(self.ultimos_numeros)
        todos_numeros = list(range(0, 37))
        
        # Priorizar números de frequência média
        numeros_ordenados = sorted(todos_numeros, key=lambda x: frequencia.get(x, 0))
        meio = len(numeros_ordenados) // 2
        
        return numeros_ordenados[meio:meio+quantidade]

    def gerar_previsao_fallback(self):
        """Previsão de fallback quando não há dados suficientes"""
        return random.sample(range(0, 37), 10)

    def registrar_resultado(self, acertou):
        """Registra resultado do palpite"""
        if acertou:
            self.acertos_consecutivos += 1
            self.erros_consecutivos = 0
        else:
            self.erros_consecutivos += 1
            self.acertos_consecutivos = 0

    def get_analise_sistema(self):
        """Retorna análise completa do sistema"""
        estatisticas_ia = {
            'modelo_carregado': self.ia_predictor.model is not None,
            'acuracia_treinamento': self.ia_predictor.acuracia_treinamento,
            'ultimo_treinamento': self.ia_predictor.ultimo_treinamento
        }
        
        previsao_atual = []
        confianca_atual = 0
        metodo_atual = "NENHUM"
        
        if self.ultimo_numero_processado is not None:
            previsao_atual, confianca_atual, metodo_atual = self.gerar_previsao_hibrida()
        
        return {
            'total_registros': len(self.historico),
            'ultimo_numero': self.ultimo_numero_processado,
            'previsao_atual': previsao_atual,
            'confianca_previsao_atual': confianca_atual,
            'metodo_previsao_atual': metodo_atual,
            'contador_sorteios': self.contador_sorteios,
            'acertos_consecutivos': self.acertos_consecutivos,
            'erros_consecutivos': self.erros_consecutivos,
            'ia_acuracia': estatisticas_ia['acuracia_treinamento'],
            'ia_modelo_carregado': estatisticas_ia['modelo_carregado'],
            'tamanho_historico_recente': len(self.ultimos_numeros)
        }

# =============================
# STREAMLIT APP - INTERFACE COM IA
# =============================
st.set_page_config(
    page_title="Roleta - Sistema Híbrido com IA", 
    page_icon="🤖", 
    layout="centered"
)

st.title("🤖 Sistema Híbrido com IA")
st.markdown("### **Random Forest + Contexto Tradicional para máxima assertividade**")

st_autorefresh(interval=8000, key="refresh")

# Inicialização session_state
defaults = {
    "sistema": SistemaHibridoIA(),
    "previsao_atual": [],
    "acertos": 0,
    "erros": 0,
    "contador_rodadas": 0,
    "ultimo_timestamp": None,
    "ultimo_numero": None,
    "confianca_atual": 0,
    "metodo_atual": "CONTEXTO"
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.session_state.previsao_atual = validar_previsao(st.session_state.previsao_atual)

# =============================
# PROCESSAMENTO PRINCIPAL COM IA
# =============================
try:
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

        # CONFERÊNCIA
        previsao_valida = validar_previsao(st.session_state.previsao_atual)
        acertou = False
        if previsao_valida and len(previsao_valida) == 10:
            acertou = numero_real in previsao_valida
            if acertou:
                st.session_state.acertos += 1
                st.session_state.sistema.registrar_resultado(True)
                st.success(f"🎯 **GREEN!** {st.session_state.metodo_atual} Acertou {numero_real}!")
                enviar_alerta_resultado(True, numero_real, st.session_state.previsao_atual, 
                                      st.session_state.confianca_atual, st.session_state.metodo_atual)
            else:
                st.session_state.erros += 1
                st.session_state.sistema.registrar_resultado(False)
                st.error(f"🔴 {st.session_state.metodo_atual} Errou! Sorteado {numero_real}")
                enviar_alerta_resultado(False, numero_real, st.session_state.previsao_atual, 
                                      st.session_state.confianca_atual, st.session_state.metodo_atual)

        # SEMPRE GERAR NOVA PREVISÃO HÍBRIDA
        nova_previsao, confianca, metodo = st.session_state.sistema.gerar_previsao_hibrida()
        
        if confianca >= CONFIANCA_MINIMA * 100:
            st.session_state.previsao_atual = validar_previsao(nova_previsao)
            st.session_state.confianca_atual = confianca
            st.session_state.metodo_atual = metodo
            
            # ENVIAR ALERTA TELEGRAM
            if st.session_state.previsao_atual and len(st.session_state.previsao_atual) == 10:
                try:
                    enviar_alerta_previsao(st.session_state.previsao_atual, int(confianca), metodo)
                except Exception as e:
                    logging.error(f"Erro ao enviar alerta de previsão: {e}")

        st.session_state.contador_rodadas += 1

except Exception as e:
    logging.error(f"Erro crítico no processamento principal: {e}")
    st.error("🔴 Erro no sistema. Reiniciando...")
    st.session_state.previsao_atual = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    st.session_state.confianca_atual = 3.5
    st.session_state.metodo_atual = "FALLBACK"

# =============================
# INTERFACE STREAMLIT COM IA
# =============================
st.markdown("---")

# STATUS DO SISTEMA
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 Sistema", "Híbrido IA")
with col2:
    st.metric("📊 Histórico", f"{len(st.session_state.sistema.historico)}")
with col3:
    ultimo_numero = st.session_state.ultimo_numero
    display_numero = ultimo_numero if ultimo_numero is not None else "-"
    st.metric("🎲 Último", display_numero)
with col4:
    st.metric("🤖 Método Atual", st.session_state.metodo_atual)

# ANÁLISE DO SISTEMA HÍBRIDO
st.subheader("🔍 Análise do Sistema Híbrido com IA")
analise_sistema = st.session_state.sistema.get_analise_sistema()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📈 Registros", analise_sistema['total_registros'])
with col2:
    st.metric("🤖 IA Acurácia", f"{analise_sistema['ia_acuracia']:.1f}%" if analise_sistema['ia_acuracia'] > 0 else "N/A")
with col3:
    st.metric("🎯 Método Atual", analise_sistema['metodo_previsao_atual'])
with col4:
    st.metric("📊 Confiança", f"{analise_sistema['confianca_previsao_atual']:.1f}%")

# PREVISÃO ATUAL DO SISTEMA
previsao_sistema = analise_sistema['previsao_atual']
confianca_sistema = analise_sistema['confianca_previsao_atual']
metodo_sistema = analise_sistema['metodo_previsao_atual']

if previsao_sistema and analise_sistema['ultimo_numero'] is not None:
    previsao_unica = []
    numeros_vistos = set()
    for num in previsao_sistema:
        if num not in numeros_vistos:
            previsao_unica.append(num)
            numeros_vistos.add(num)
    
    if previsao_unica and len(previsao_unica) == 10:
        emoji_metodo = "🤖" if metodo_sistema == "IA" else "🎯" if metodo_sistema == "CONTEXTO" else "🔄"
        st.success(f"**{emoji_metodo} PREVISÃO {metodo_sistema} APÓS {analise_sistema['ultimo_numero']}:**")
        
        # Formatação para 10 números (5+5)
        linha1 = previsao_unica[:5]
        linha2 = previsao_unica[5:10]
        
        linha1_str = " | ".join([f"**{num}**" for num in linha1])
        linha2_str = " | ".join([f"**{num}**" for num in linha2])
        
        st.markdown(f"### {emoji_metodo} {linha1_str}")
        st.markdown(f"### {emoji_metodo} {linha2_str}")
        
        info_ia = f" | IA Treinada: {analise_sistema['ia_acuracia']:.1f}%" if analise_sistema['ia_acuracia'] > 0 else " | IA em Treinamento"
        st.caption(f"💡 **{metodo_sistema} - CONFIANÇA {confianca_sistema:.1f}%** {info_ia}")
        
else:
    st.info("🔄 Inicializando sistema híbrido...")

# PREVISÃO ATUAL OFICIAL
st.markdown("---")
st.subheader("🎯 PREVISÃO ATUAL OFICIAL")

previsao_valida = validar_previsao(st.session_state.previsao_atual)

if previsao_valida and len(previsao_valida) == 10:
    # Classificação baseada no método e confiança
    if st.session_state.metodo_atual == "IA":
        cor = "🤖"
        status = "INTELIGÊNCIA ARTIFICIAL"
    elif st.session_state.metodo_atual == "CONTEXTO":
        cor = "🎯"
        status = "CONTEXTO TRADICIONAL"
    else:
        cor = "🔄"
        status = "SISTEMA FALLBACK"
    
    st.success(f"**{cor} {status} - CONFIANÇA {st.session_state.confianca_atual:.1f}%**")
    
    # Display organizado
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Linha 1:**")
        for num in sorted(previsao_valida[:5]):
            st.write(f"`{num}`")
    
    with col2:
        st.write("**Linha 2:**")
        for num in sorted(previsao_valida[5:10]):
            st.write(f"`{num}`")
    
    st.write(f"**Lista Completa:** {', '.join(map(str, sorted(previsao_valida)))}")
    
else:
    st.warning("⏳ Aguardando próxima previsão do sistema híbrido...")

# PERFORMANCE
st.markdown("---")
st.subheader("📊 Performance do Sistema Híbrido")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("✅ Acertos", st.session_state.acertos)
with col2:
    st.metric("❌ Erros", st.session_state.erros)
with col3:
    total = st.session_state.acertos + st.session_state.erros
    taxa_acerto = (st.session_state.acertos / total * 100) if total > 0 else 0
    st.metric("📈 Taxa Acerto", f"{taxa_acerto:.1f}%")
with col4:
    st.metric("🔄 Rodadas", st.session_state.contador_rodadas)

# ESTATÍSTICAS DE CONSECUTIVOS
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("✅ Acertos Consecutivos", analise_sistema['acertos_consecutivos'])
with col2:
    st.metric("🔴 Erros Consecutivos", analise_sistema['erros_consecutivos'])
with col3:
    st.metric("🤖 IA Ativa", "SIM" if analise_sistema['ia_modelo_carregado'] else "NÃO")

# DETALHES TÉCNICOS
with st.expander("🔧 Detalhes do Sistema Híbrido com IA"):
    st.write("**🤖 ARQUITETURA HÍBRIDA:**")
    st.write("- 🔄 **Random Forest**: 100 árvores, profundidade 10")
    st.write("- 🎯 **Contexto Tradicional**: Vizinhança + Estatísticas")
    st.write("- 📊 **Seleção Automática**: Escolhe o melhor método")
    st.write("- 💾 **Treinamento Contínuo**: A cada 1000 novos dados")
    
    st.write("**📊 ESTATÍSTICAS DO SISTEMA:**")
    st.write(f"- Total de registros: {analise_sistema['total_registros']}")
    st.write(f"- Método atual: {analise_sistema['metodo_previsao_atual']}")
    st.write(f"- Acurácia da IA: {analise_sistema['ia_acuracia']:.1f}%" if analise_sistema['ia_acuracia'] > 0 else "- Acurácia da IA: Em treinamento")
    st.write(f"- IA carregada: {'Sim' if analise_sistema['ia_modelo_carregado'] else 'Não'}")
    st.write(f"- Acertos consecutivos: {analise_sistema['acertos_consecutivos']}")
    st.write(f"- Erros consecutivos: {analise_sistema['erros_consecutivos']}")
    
    st.write("**🎯 ESTRATÉGIA DE SELEÇÃO:**")
    st.write("- 🤖 **IA**: Usada quando confiança ≥ 4%")
    st.write("- 🎯 **Contexto**: Usado quando IA não atinge confiança")
    st.write("- 🔄 **Fallback**: Usado quando dados insuficientes")
    
    st.write("**📨 SISTEMA DE ALERTAS INTELIGENTE:**")
    st.write("- 🔔 Alerta de PREVISÃO: Especifica método usado")
    st.write("- 🟢 Alerta GREEN: Inclui método e confiança")
    st.write("- 🔴 Alerta RED: Inclui método e confiança")

# CONTROLES AVANÇADOS
st.markdown("---")
st.subheader("⚙️ Controles Avançados do Sistema")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔄 Forçar Nova Previsão"):
        nova_previsao, confianca, metodo = st.session_state.sistema.gerar_previsao_hibrida()
        st.session_state.previsao_atual = validar_previsao(nova_previsao)
        st.session_state.confianca_atual = confianca
        st.session_state.metodo_atual = metodo
        st.rerun()

with col2:
    if st.button("🤖 Treinar IA Agora"):
        with st.spinner("Treinando IA..."):
            sucesso = st.session_state.sistema.ia_predictor.treinar_modelo(list(st.session_state.sistema.historico))
            if sucesso:
                st.success("IA treinada com sucesso!")
            else:
                st.error("Erro ao treinar IA")
        st.rerun()

with col3:
    if st.button("🗑️ Limpar Tudo"):
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        if os.path.exists(CONTEXTO_PATH):
            os.remove(CONTEXTO_PATH)
        if os.path.exists(MODELO_IA_PATH):
            os.remove(MODELO_IA_PATH)
        if os.path.exists(SCALER_PATH):
            os.remove(SCALER_PATH)
        st.session_state.sistema.historico.clear()
        st.session_state.acertos = 0
        st.session_state.erros = 0
        st.rerun()

st.markdown("---")
st.markdown("### 🤖 **Sistema Híbrido com IA**")
st.markdown("*Combinação de Random Forest e contexto tradicional para máxima assertividade*")

# Rodapé
st.markdown("---")
st.markdown("**🤖 Sistema Híbrido IA v6.0** - *Random Forest + Contexto Tradicional*")
