# RoletaHybridIA_v3.py - SISTEMA HÍBRIDO OTIMIZADO (IA + CONTEXTO) - "Elite Master"
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
import functools
import statistics
import csv

# =============================
# CONFIGURAÇÕES GLOBAIS
# =============================
HISTORICO_PATH = "historico_hybrid_ia.json"
CONTEXTO_PATH = "contexto_historico.json"
MODELO_IA_PATH = "modelo_random_forest_v3.pkl"
SCALER_PATH = "scaler_v3.pkl"
LOG_CSV_PATH = "logs_resultados.csv"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# <-- mantenha ou substitua pelo seu token/chat -->
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"

# DISPOSIÇÃO FÍSICA REAL DA ROLETA
ROULETTE_PHYSICAL_LAYOUT = [
    [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
    [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
]

# listas de cores (R/B) - padrão europeu/offset conforme seu código base
VERMELHO = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
PRETO = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

# PARÂMETROS OPERACIONAIS
MIN_DADOS_TREINAMENTO = 75         # dados mínimos para treinar modelo (ajustado para v3)
TREINAMENTO_INTERVALO = 1          # treinar incremental a cada X novos registros
WINDOW_SIZE = 20                    # janela usada para features
CACHE_INTERVAL = 20                 # segundos para cache de previsão
CONFIANCA_MINIMA = 0.32             # confiança mínima (0-1) para enviar sinal
RELATORIO_RODADAS = 10              # enviar relatório telegram a cada N rodadas
MAX_HISTORY_LEN = 2000

# Configurar logging avançado (arquivo + console)
def setup_advanced_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # remover handlers duplicados se existirem (reexecução no Streamlit)
    if logger.handlers:
        logger.handlers = []
    file_handler = logging.FileHandler('sistema_hibrido_ia_v3.log')
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

setup_advanced_logging()

# =============================
# DECORATORS DE PERFORMANCE
# =============================
def timing_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.debug(f"⏱️ {func.__name__} executado em {end_time - start_time:.4f}s")
        return result
    return wrapper

# =============================
# FUNÇÕES UTILITÁRIAS
# =============================
@timing_decorator
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

@timing_decorator
def salvar_historico(numero_dict):
    try:
        if not isinstance(numero_dict, dict) or numero_dict.get('number') is None:
            logging.error("❌ Tentativa de salvar número inválido")
            return False
        historico_existente = carregar_historico()
        timestamp_novo = numero_dict.get("timestamp")
        ja_existe = any(registro.get("timestamp") == timestamp_novo for registro in historico_existente if isinstance(registro, dict))
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

@timing_decorator
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

@timing_decorator
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

@timing_decorator
def validar_previsao(previsao):
    if not previsao or not isinstance(previsao, list):
        return []
    previsao_limpa = [int(num) for num in previsao if num is not None and isinstance(num, (int, float)) and 0 <= int(num) <= 36]
    return previsao_limpa

@timing_decorator
def enviar_telegram(msg: str):
    try:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logging.warning("Telegram não configurado (token/chat_id ausente).")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=10)
        logging.info(f"📤 Telegram enviado: {msg}")
    except Exception as e:
        logging.error(f"Erro ao enviar para Telegram: {e}")

@timing_decorator
def enviar_alerta_previsao(numeros, confianca, metodo="IA"):
    """Envia alerta de PREVISÃO com 10 números e nível de confiança"""
    try:
        if not numeros or len(numeros) < 1:
            logging.error("❌ Alerta de previsão precisa de números válidos")
            return
        numeros_ordenados = sorted(numeros)[:10]
        numeros_str = ', '.join(map(str, numeros_ordenados))
        mensagem = f"🎯 NOVO SINAL - ELITE MASTER\n🔹 Método: {metodo}\n🔹 Confiança: {int(confianca*100)}%\n🔹 Números: {numeros_str}\n📊 Acurácia atual: {st.session_state.get('acuracia_geral', 0):.1f}%"
        enviar_telegram(mensagem)
    except Exception as e:
        logging.error(f"Erro alerta previsão: {e}")

@timing_decorator
def enviar_alerta_resultado(acertou, numero_sorteado, previsao_anterior, confianca, metodo="IA"):
    """Envia alerta de resultado (GREEN/RED) com a previsão anterior"""
    try:
        previsao_ordenada = sorted(previsao_anterior) if previsao_anterior else []
        previsao_str = ', '.join(map(str, previsao_ordenada))
        if acertou:
            mensagem = f"🟢 GREEN - ELITE MASTER\n{metodo} acertou {numero_sorteado}\nConfiança: {int(confianca*100)}%\nPrevisão: {previsao_str}"
        else:
            mensagem = f"🔴 RED - ELITE MASTER\n{metodo} errou. Sorteado: {numero_sorteado}\nConfiança: {int(confianca*100)}%\nPrevisão: {previsao_str}"
        enviar_telegram(mensagem)
    except Exception as e:
        logging.error(f"Erro alerta resultado: {e}")

# =============================
# IA - RANDOM FOREST PREDICTOR V3
# =============================
class IAPredictorV3:
    """Random Forest com features expandidas e treino incremental"""
    def __init__(self):
        self.model = None
        self.scaler = None
        self.ultimo_treinamento = 0
        self.acuracia_treinamento = 0.0
        self.min_samples_data = MIN_DADOS_TREINAMENTO
        self._carregar_modelo()

    def _carregar_modelo(self):
        try:
            if os.path.exists(MODELO_IA_PATH) and os.path.exists(SCALER_PATH):
                self.model = joblib.load(MODELO_IA_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                logging.info("🤖 IA v3 carregada do disco.")
                return True
            logging.info("🤖 IA v3 não encontrada no disco.")
            return False
        except Exception as e:
            logging.error(f"Erro ao carregar modelo IA v3: {e}")
            return False

    def _salvar_modelo(self):
        try:
            if self.model is not None and self.scaler is not None:
                joblib.dump(self.model, MODELO_IA_PATH)
                joblib.dump(self.scaler, SCALER_PATH)
                logging.info("💾 Modelo IA v3 salvo.")
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar modelo: {e}")
        return False

    def numero_to_features(self, janela):
        """
        Recebe uma lista de últimos N números e gera feature vector:
        - Para cada posição: número normalizado (0-36), cor (1/-1/0), paridade (0/1), duzia (0,1,2), metade (0/1)
        - Estatísticas adicionais: média, std, contagem_pares, contagem_vermelho, contagem_preto, ultima_diferenca
        """
        # janela: lista de ints
        features = []
        for n in janela:
            n_int = int(n)
            cor = 1 if n_int in VERMELHO else (-1 if n_int in PRETO else 0)
            par = 1 if (n_int % 2 == 0) else 0
            duzia = 0 if n_int == 0 else ((n_int - 1) // 12)
            metade = 0 if n_int == 0 else (0 if n_int <= 18 else 1)
            features.extend([n_int, cor, par, duzia, metade])
        # estatísticas
        media = float(np.mean(janela)) if len(janela) > 0 else 0.0
        std = float(np.std(janela)) if len(janela) > 0 else 0.0
        pares = sum(1 for x in janela if x % 2 == 0)
        vermelhos = sum(1 for x in janela if x in VERMELHO)
        pretos = sum(1 for x in janela if x in PRETO)
        ultima_diff = janela[-1] - janela[-2] if len(janela) > 1 else 0
        features.extend([media, std, pares, vermelhos, pretos, ultima_diff])
        return np.array(features, dtype=float)

    @timing_decorator
    def preparar_dataset(self, historico, window_size=WINDOW_SIZE):
        """Transforma historico (lista de dicts com 'number') em X, y"""
        numeros = [h['number'] for h in historico]
        if len(numeros) < window_size + 30:
            return None, None
        X, y = [], []
        for i in range(window_size, len(numeros)):
            janela = numeros[i-window_size:i]
            X.append(self.numero_to_features(janela))
            y.append(int(numeros[i]))
        return np.vstack(X), np.array(y, dtype=int)

    @timing_decorator
    def treinar(self, historico):
        try:
            X, y = self.preparar_dataset(historico, WINDOW_SIZE)
            if X is None or len(X) < 50:
                logging.info("IA v3: dados insuficientes para treinar.")
                return False
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            self.model = RandomForestClassifier(
                n_estimators=150,
                max_depth=None,
                min_samples_split=4,
                min_samples_leaf=1,
                random_state=42,
                n_jobs=-1,
                bootstrap=True,
                max_features='sqrt'
            )
            self.model.fit(X_train_scaled, y_train)
            y_pred = self.model.predict(X_test_scaled)
            self.acuracia_treinamento = accuracy_score(y_test, y_pred) * 100
            self.ultimo_treinamento = time.time()
            self._salvar_modelo()
            logging.info(f"🤖 IA v3 treinada - Acurácia: {self.acuracia_treinamento:.2f}%")
            return True
        except Exception as e:
            logging.error(f"Erro ao treinar IA v3: {e}")
            return False

    @timing_decorator
    def predict_top_probs(self, ultimos_numeros, top_n=12):
        """Retorna os top_n números ordenados por probabilidade e as probabilidades normalizadas"""
        try:
            if self.model is None or self.scaler is None:
                return None, None
            if len(ultimos_numeros) < WINDOW_SIZE:
                return None, None
            features = self.numero_to_features(list(ultimos_numeros)[-WINDOW_SIZE:])
            Xp = self.scaler.transform([features])
            probs = self.model.predict_proba(Xp)[0]  # length 37
            # predict_proba returns probabilities aligned with model.classes_
            classes = list(self.model.classes_)
            # map to full 0..36 probabilities
            prob_map = {c: probs[i] for i, c in enumerate(classes)}
            all_probs = np.array([prob_map.get(i, 0.0) for i in range(37)])
            order = np.argsort(all_probs)[::-1]
            top = order[:top_n].tolist()
            top_probs = all_probs[order][:top_n]
            return top, top_probs
        except Exception as e:
            logging.error(f"Erro predict IA v3: {e}")
            return None, None

    def deve_treinar(self, historico):
        if len(historico) < self.min_samples_data:
            return False
        if self.model is None:
            return True
        # Treinar incremental a cada TREINAMENTO_INTERVALO novos registros
        tempo_desde = time.time() - getattr(self, "ultimo_treinamento", 0)
        return tempo_desde > 60*30  # ou também por volume - aqui por tempo > 30 min

# =============================
# SISTEMA HÍBRIDO V3 (IA + CONTEXTO)
# =============================
class SistemaHibridoV3:
    def __init__(self):
        self.ia = IAPredictorV3()
        self.historico = deque(carregar_historico(), maxlen=MAX_HISTORY_LEN)
        self.ultimos_numeros = deque(maxlen=200)  # para análises rápidas
        self.previsao_atual = []
        self.confianca_atual = 0.0
        self.metodo_atual = "NENHUM"
        self.cache_previsoes = {}
        self.ultima_previsao_time = 0
        self.contador_rodadas = 0
        self.acertos = 0
        self.erros = 0
        self.acertos_consecutivos = 0
        self.erros_consecutivos = 0
        self.historico_confianca = deque(maxlen=100)
        # carregar últimos números
        for r in list(self.historico)[-200:]:
            if r.get('number') is not None:
                self.ultimos_numeros.append(int(r['number']))
        # treinar se necessário
        try:
            if len(self.historico) >= MIN_DADOS_TREINAMENTO:
                self.ia.treinar(list(self.historico))
        except Exception as e:
            logging.error(f"Erro ao treinar inicial: {e}")

    # ---------- utilitários ----------
    def adicionar_numero(self, numero_dict):
        if not isinstance(numero_dict, dict) or numero_dict.get('number') is None:
            return
        numero = int(numero_dict['number'])
        self.historico.append(numero_dict)
        self.ultimos_numeros.append(numero)
        self.contador_rodadas += 1
        # limpar cache
        self.cache_previsoes.clear()
        # grava CSV log parcial
        self._log_round(numero)
        # treino incremental se tiver muitos novos dados
        if len(self.historico) % TREINAMENTO_INTERVALO == 0:
            try:
                self.ia.treinar(list(self.historico))
            except Exception as e:
                logging.error(f"Erro no treino incremental: {e}")

    def _log_round(self, numero_real):
        # escreve linha em CSV com timestamp, numero, previsao atual, confianca, metodo, acertos, erros
        try:
            exists = os.path.exists(LOG_CSV_PATH)
            with open(LOG_CSV_PATH, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(["timestamp", "numero_real", "previsao", "confianca", "metodo", "acertos", "erros"])
                writer.writerow([time.time(), numero_real, '|'.join(map(str, self.previsao_atual)), f"{self.confianca_atual:.3f}", self.metodo_atual, self.acertos, self.erros])
        except Exception as e:
            logging.error(f"Erro ao logar round: {e}")

    # ---------- contexto ----------
    def gerar_previsao_contextual(self, top_n=10):
        """Gera previsão contextual combinando vizinhança, quentes e frios, cor/paridade"""
        try:
            if len(self.ultimos_numeros) == 0:
                return random.sample(range(0, 37), top_n), 0.35
            previsao = []
            ultimo = self.ultimos_numeros[-1]
            # vizinhos físicos
            viz = obter_vizinhos_fisicos(ultimo)
            random.shuffle(viz)
            previsao.extend(viz[:3])
            # numeros quentes (ultimos 30)
            ult30 = list(self.ultimos_numeros)[-30:]
            freq = Counter(ult30)
            quentes = [n for n, c in freq.most_common(4)]
            previsao.extend([n for n in quentes if n not in previsao][:4])
            # cor/paridade bias: se 3+ vermelhos seguidos -> priorizar pretos
            ult5 = list(self.ultimos_numeros)[-5:]
            cor_sum = sum(1 if x in VERMELHO else -1 if x in PRETO else 0 for x in ult5)
            candidatos = list(range(37))
            if cor_sum >= 3:
                candidatos = list(PRETO)
            elif cor_sum <= -3:
                candidatos = list(VERMELHO)
            # completar com frios (não vistos em ult30)
            todos = set(range(0,37))
            frios = list(todos - set(ult30))
            random.shuffle(frios)
            # priorizar candidatos que são frios e na cor desejada
            complement = [n for n in frios if n in candidatos][: (top_n - len(previsao))]
            previsao.extend(complement)
            # Se não completar, preencher por frequencia média
            if len(previsao) < top_n:
                meio_sorted = sorted(list(todos), key=lambda x: freq.get(x,0))
                previsao.extend([n for n in meio_sorted if n not in previsao][: (top_n - len(previsao))])
            previsao = previsao[:top_n]
            # confiança heurística baseada em quantos itens eram quentes/vidas vizinhas
            score = (sum(1 for p in previsao if p in quentes) * 0.12) + (len(set(previsao)) / top_n * 0.3)
            confianca = min(0.85, max(0.25, 0.35 + score))
            return previsao, confianca
        except Exception as e:
            logging.error(f"Erro gerar_previsao_contextual: {e}")
            return random.sample(range(0,37), top_n), 0.25

    # ---------- IA ----------
    def prever_ia(self, top_n=12):
        top, probs = self.ia.predict_top_probs(list(self.ultimos_numeros), top_n=top_n)
        if top is None or probs is None:
            return None, 0.0
        # converter probs para confiança média dos top
        confianca = float(np.mean(probs))
        return top, confianca

    # ---------- fusão híbrida (voto ponderado) ----------
    def prever_hibrida(self, top_n=10):
        # cache simple
        cache_key = hash(tuple(self.ultimos_numeros)) if self.ultimos_numeros else 0
        now = time.time()
        if cache_key in self.cache_previsoes and (now - self.ultima_previsao_time) < CACHE_INTERVAL:
            return self.cache_previsoes[cache_key]
        # obter previsões
        previsao_ia, conf_ia = self.prever_ia(top_n=12)
        previsao_ctx, conf_ctx = self.gerar_previsao_contextual(top_n=12)
        # normalizar confidancas (garantir 0-1)
        conf_ia = float(conf_ia) if conf_ia is not None else 0.0
        conf_ctx = float(conf_ctx) if conf_ctx is not None else 0.0
        # pesos dinâmicos baseados em acuracia móvel (ultimas 50 rodadas)
        acuracia_movel = self._acuracia_movel(50)
        peso_ia = 0.6 + 0.2 * (acuracia_movel / 100)   # aumenta se performance boa
        peso_ctx = 1.0 - peso_ia
        # construir contagem ponderada
        contador = Counter()
        if previsao_ia:
            for i, n in enumerate(previsao_ia):
                contador[int(n)] += peso_ia * (1.0 - i*0.02)  # peso decrescente por ranking
        if previsao_ctx:
            for i, n in enumerate(previsao_ctx):
                contador[int(n)] += peso_ctx * (1.0 - i*0.02)
        # escolher top_n por votos
        final = [n for n, _ in contador.most_common(top_n)]
        # calcular confiança combinada
        # média ponderada das confidências ajustadas pelos pesos e pela diversidade
        conf_comb = (conf_ia * peso_ia + conf_ctx * peso_ctx) / (peso_ia + peso_ctx)
        # penalizar caso pouca diversidade (muitos duplicados)
        diversidade = len(set(final)) / top_n
        conf_final = max(0.0, min(0.99, conf_comb * (0.6 + 0.4*diversidade)))
        metodo = "HÍBRIDO" if abs(conf_ia - conf_ctx) < 0.08 else ("IA" if conf_ia > conf_ctx else "CONTEXTO")
        # cache
        self.cache_previsoes[cache_key] = (final, conf_final, metodo)
        self.ultima_previsao_time = now
        return final, conf_final, metodo

    def _acuracia_movel(self, n=50):
        # calcular acuracia movel a partir do CSV (ultima N linhas) ou de st.session_state
        try:
            # preferir estado em memória (se disponível)
            ac = st.session_state.get('acuracia_geral', None)
            if ac is not None:
                return ac
            # fallback: ler CSV e calcular
            if os.path.exists(LOG_CSV_PATH):
                df = pd.read_csv(LOG_CSV_PATH)
                last = df.tail(n)
                if len(last) == 0:
                    return 0.0
                # considerar sucesso quando numero_real in previsao
                wins = 0
                for _, row in last.iterrows():
                    previs = str(row.get('previsao', ''))
                    real = int(row.get('numero_real', -1))
                    if previs and str(real) in previs:
                        wins += 1
                return (wins / len(last)) * 100
            return 0.0
        except Exception as e:
            logging.error(f"Erro acuracia_movel: {e}")
            return 0.0

    # ---------- decisão de envio ----------
    def gerar_sinal(self):
        previsao, confianca, metodo = self.prever_hibrida(top_n=10)
        # evitar sinal repetido (mesmo conjunto) ou baixa confiança
        previsao_valida = validar_previsao(previsao)
        if not previsao_valida:
            return [], 0.0, "NENHUM"
        # padrão: confiança deve ser >= CONFIANCA_MINIMA
        if confianca < CONFIANCA_MINIMA:
            logging.info(f"Sinal bloqueado por baixa confiança: {confianca:.3f}")
            return [], confianca, "BAIXA_CONF"
        # prevenir repetição: comparar com ultima previsao
        ultima = getattr(self, 'previsao_atual', None)
        if ultima and set(ultima) == set(previsao_valida):
            logging.info("Sinal idêntico ao anterior — bloqueado para evitar repetição.")
            return [], confianca, "REPETIDO"
        # atualizar estado
        self.previsao_atual = previsao_valida
        self.confianca_atual = confianca
        self.metodo_atual = metodo
        self.historico_confianca.append(confianca)
        # enviar telegram e retornar
        return previsao_valida, confianca, metodo

    # ---------- registro de acerto/erro ----------
    def registrar_resultado(self, numero_real):
        previs = self.previsao_atual or []
        acertou = numero_real in previs
        if acertou:
            self.acertos += 1
            self.acertos_consecutivos += 1
            self.erros_consecutivos = 0
        else:
            self.erros += 1
            self.erros_consecutivos += 1
            self.acertos_consecutivos = 0
        # salvar resultado no CSV
        self._log_round(numero_real)
        # a cada RELATORIO_RODADAS enviar resumo telegram
        if self.contador_rodadas % RELATORIO_RODADAS == 0:
            self.enviar_relatorio_periodico()
        return acertou

    def enviar_relatorio_periodico(self):
        try:
            total = self.acertos + self.erros
            taxa = (self.acertos / total * 100) if total > 0 else 0.0
            conf_media = (sum(self.historico_confianca)/len(self.historico_confianca)) if self.historico_confianca else 0.0
            mensagem = f"📊 RELATÓRIO - ELITE MASTER\n🔸 Rodadas: {self.contador_rodadas}\n🔸 Acertos: {self.acertos}\n🔸 Erros: {self.erros}\n🔸 Taxa: {taxa:.1f}%\n🔸 Confiança média: {conf_media*100:.1f}%"
            enviar_telegram(mensagem)
        except Exception as e:
            logging.error(f"Erro enviar_relatorio_periodico: {e}")

    def get_status(self):
        return {
            "previsao_atual": self.previsao_atual,
            "confianca_atual": self.confianca_atual,
            "metodo_atual": self.metodo_atual,
            "acertos": self.acertos,
            "erros": self.erros,
            "acertos_consecutivos": self.acertos_consecutivos,
            "erros_consecutivos": self.erros_consecutivos,
            "contador_rodadas": self.contador_rodadas,
            "tamanho_historico": len(self.historico)
        }

# =============================
# STREAMLIT APP - INTERFACE (ELITE MASTER)
# =============================
st.set_page_config(page_title="Elite Master - Roleta Híbrida IA", page_icon="🤖", layout="centered")
st.title("🔮 Elite Master — Roleta Híbrida (IA + Contexto) v3.0")
st.markdown("Combinação avançada de **Random Forest** + análise contextual. Integrado com bot Telegram para envio de sinais e relatórios.")

st_autorefresh(interval=8000, key="refresh")

# session_state init
if 'sistema' not in st.session_state:
    st.session_state['sistema'] = SistemaHibridoV3()
    st.session_state['previsao_atual'] = []
    st.session_state['confianca_atual'] = 0.0
    st.session_state['metodo_atual'] = "NENHUM"
    st.session_state['acertos'] = 0
    st.session_state['erros'] = 0
    st.session_state['contador_rodadas'] = 0
    st.session_state['ultimo_timestamp'] = None
    st.session_state['ultimo_numero'] = None
    st.session_state['acuracia_geral'] = 0.0

sistema = st.session_state['sistema']

# Painel lateral - controles
with st.sidebar:
    st.header("⚙️ Controles")
    st.write("Botões rápidos para operar o sistema")
    if st.button("🔄 Forçar Nova Previsão (Gerar Sinal)"):
        previsao_valida, conf, metodo = sistema.gerar_sinal()
        st.session_state['previsao_atual'] = previsao_valida
        st.session_state['confianca_atual'] = conf
        st.session_state['metodo_atual'] = metodo
        if previsao_valida and conf >= CONFIANCA_MINIMA:
            enviar_alerta_previsao(previsao_valida, conf, metodo)
        st.experimental_rerun()
    if st.button("🤖 Treinar IA Agora"):
        with st.spinner("Treinando IA..."):
            sucesso = sistema.ia.treinar(list(sistema.historico))
            if sucesso:
                st.success(f"IA treinada! Acurácia: {sistema.ia.acuracia_treinamento:.1f}%")
            else:
                st.error("Treino falhou ou dados insuficientes.")
    if st.button("🗑️ Reset Tudo (Histórico + Modelos)"):
        # apagar arquivos e resetar estados
        for p in [HISTORICO_PATH, MODELO_IA_PATH, SCALER_PATH, LOG_CSV_PATH]:
            if os.path.exists(p):
                os.remove(p)
        st.session_state.clear()
        st.experimental_rerun()
    st.markdown("---")
    st.write("Configurações")
    st.write(f"- Confiança mínima: {CONFIANCA_MINIMA*100:.0f}%")
    st.write(f"- Relatório a cada {RELATORIO_RODADAS} rodadas")
    st.markdown("---")
    st.write("Telegram")
    st.write(f"Token: {'(configurado)' if TELEGRAM_TOKEN else '(não configurado)'}")
    st.write(f"Chat ID: {'(configurado)' if TELEGRAM_CHAT_ID else '(não configurado)'}")

# Main area - status
col1, col2, col3 = st.columns([2,2,2])
with col1:
    st.metric("📊 Rodadas", sistema.contador_rodadas)
    st.metric("✅ Acertos", sistema.acertos)
    st.metric("❌ Erros", sistema.erros)
with col2:
    acur_total = (sistema.acertos / (sistema.acertos + sistema.erros) * 100) if (sistema.acertos + sistema.erros) > 0 else 0
    st.metric("📈 Taxa Acerto", f"{acur_total:.1f}%")
    st.metric("🔁 Acertos Consecutivos", sistema.acertos_consecutivos)
    st.metric("🔻 Erros Consecutivos", sistema.erros_consecutivos)
with col3:
    st.metric("🤖 IA Treinada", "SIM" if sistema.ia.model is not None else "NÃO")
    st.metric("🧾 Histórico", len(sistema.historico))
    st.metric("⏱️ Uptime (approx)", f"{time.time() / 3600:.1f}h")

st.markdown("---")

# Exibe previsão atual gerada
st.subheader("🎯 Previsão Atual (Oficial)")
previsao_atual = st.session_state.get('previsao_atual', sistema.previsao_atual)
confianca_atual = st.session_state.get('confianca_atual', sistema.confianca_atual)
metodo_atual = st.session_state.get('metodo_atual', sistema.metodo_atual)

if previsao_atual and len(previsao_atual) == 10:
    st.success(f"🔹 Método: {metodo_atual}  |  Confiança: {confianca_atual*100:.1f}%")
    # exibir em duas linhas
    linha1 = previsao_atual[:5]
    linha2 = previsao_atual[5:10]
    st.markdown("### " + " | ".join([f"**{n}**" for n in linha1]))
    st.markdown("### " + " | ".join([f"**{n}**" for n in linha2]))
else:
    st.info("Nenhuma previsão ativa (ou aguardando confiança suficiente).")

# Mostrar histórico dos ultimos números
st.subheader("🔍 Últimos Resultados")
ultimos = list(sistema.ultimos_numeros)[-20:][::-1]
if ultimos:
    st.write(", ".join(map(str, ultimos)))
else:
    st.write("Sem resultados ainda.")

# Botão de simular chegada de novo resultado manual (para testes)
st.markdown("---")
st.subheader("🛠️ Testes / Injeção Manual")
colA, colB = st.columns(2)
with colA:
    numero_manual = st.number_input("Inserir número sorteado (0-36)", min_value=0, max_value=36, value=0, step=1)
    if st.button("➕ Inserir resultado manual"):
        timestamp_now = str(time.time())
        numero_dict = {"number": int(numero_manual), "timestamp": timestamp_now}
        salvo = salvar_historico(numero_dict)
        if salvo:
            sistema.adicionar_numero(numero_dict)
            # registrar resultado (conferir previsão atual)
            acertou = sistema.registrar_resultado(int(numero_manual))
            enviar_alerta_resultado(acertou, int(numero_manual), sistema.previsao_atual, sistema.confianca_atual, sistema.metodo_atual)
            st.success(f"Resultado {numero_manual} inserido!")
            # atualizar sessão
            st.session_state['previsao_atual'] = sistema.previsao_atual
            st.session_state['confianca_atual'] = sistema.confianca_atual
            st.session_state['metodo_atual'] = sistema.metodo_atual
            st.session_state['acertos'] = sistema.acertos
            st.session_state['erros'] = sistema.erros
            st.experimental_rerun()
        else:
            st.error("Falha ao salvar histórico (provavelmente duplicado).")
with colB:
    if st.button("🔮 Gerar sinal (sem enviar Telegram)"):
        previsao_valida, conf, metodo = sistema.gerar_sinal()
        st.session_state['previsao_atual'] = previsao_valida
        st.session_state['confianca_atual'] = conf
        st.session_state['metodo_atual'] = metodo
        if previsao_valida:
            st.write("Previsão:", previsao_valida)
            st.write(f"Confiança: {conf*100:.1f}%  | Metodo: {metodo}")
        else:
            st.info("Nenhum sinal gerado (baixa confiança ou repetido).")

# Automatização: buscar resultado real da API (se disponível) - execução principal
st.markdown("---")
st.subheader("🔄 Processamento Automático (API)")
try:
    resultado = fetch_latest_result()
    novo_sorteio = False
    if resultado and resultado.get("timestamp"):
        if st.session_state.get('ultimo_timestamp') is None or resultado.get('timestamp') != st.session_state.get('ultimo_timestamp'):
            novo_sorteio = True
    if resultado and novo_sorteio:
        numero_dict = {"number": int(resultado["number"]), "timestamp": resultado["timestamp"]}
        salvo = salvar_historico(numero_dict)
        if salvo:
            sistema.adicionar_numero(numero_dict)
        st.session_state['ultimo_timestamp'] = resultado["timestamp"]
        st.session_state['ultimo_numero'] = resultado["number"]
        # conferir resultado vs previa
        previsao_valida = validar_previsao(st.session_state.get('previsao_atual', []))
        acertou = False
        if previsao_valida and len(previsao_valida) == 10:
            acertou = int(resultado["number"]) in previsao_valida
            sistema.registrar_resultado(int(resultado["number"]))
            enviar_alerta_resultado(acertou, int(resultado["number"]), previsao_valida, st.session_state.get('confianca_atual', 0.0), st.session_state.get('metodo_atual', 'NENHUM'))
        # sempre gerar nova previsao após registro
        nova_previsao, conf, metodo = sistema.gerar_sinal()
        # se confianca ok envia telegram
        if nova_previsao and conf >= CONFIANCA_MINIMA:
            st.session_state['previsao_atual'] = nova_previsao
            st.session_state['confianca_atual'] = conf
            st.session_state['metodo_atual'] = metodo
            enviar_alerta_previsao(nova_previsao, conf, metodo)
        # atualizar acuracia geral no estado
        total = sistema.acertos + sistema.erros
        st.session_state['acuracia_geral'] = (sistema.acertos / total * 100) if total > 0 else 0.0
        st.session_state['acertos'] = sistema.acertos
        st.session_state['erros'] = sistema.erros
        st.experimental_rerun()
except Exception as e:
    logging.error(f"Erro no loop automático: {e}")
    st.warning("⚠️ Erro ao buscar/processar resultado automático (ver logs).")

st.markdown("---")
st.caption("RoletaHybridIA v3.0 — Elite Master. Use com responsabilidade. Este sistema fornece sinais estatísticos; jogos de azar envolvem risco.")

# fim do arquivo
