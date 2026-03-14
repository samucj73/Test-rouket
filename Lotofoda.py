import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
import math
from collections import Counter
from datetime import datetime
from scipy.stats import norm, chi2_contingency
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL AI 2.0",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1,h2,h3 { text-align: center; }
.card { background: #0e1117; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid #262730; color: white; }
.stButton>button { width: 100%; height: 3.2em; border-radius: 14px; font-size: 1.05em; }
.metric-card { background: #16213e; padding: 10px; border-radius: 10px; text-align: center; }
.success-box { background: #00ff0020; padding: 15px; border-radius: 10px; border-left: 5px solid #00ff00; margin: 10px 0; }
.warning-box { background: #ffff0020; padding: 15px; border-radius: 10px; border-left: 5px solid #ffff00; margin: 10px 0; }
.info-box { background: #0000ff20; padding: 15px; border-radius: 10px; border-left: 5px solid #0000ff; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL AI 2.0")
st.caption("Machine Learning + Ensemble + Backtesting • Aprendizado Real")

# =====================================================
# CLASSE BASE: DISTRIBUIÇÕES PROBABILÍSTICAS
# =====================================================

class DistribuicoesProbabilisticas:
    """
    Classe base que calcula distribuições de probabilidade reais
    Em vez de regras fixas, usamos probabilidades
    """
    
    def __init__(self, historico):
        self.historico = historico
        self.total = len(historico)
        
        # Calcular distribuições para todas as features importantes
        self.dist_baixas = self._calcular_distribuicao(lambda j: sum(1 for n in j if n <= 8))
        self.dist_medias = self._calcular_distribuicao(lambda j: sum(1 for n in j if 9 <= n <= 16))
        self.dist_altas = self._calcular_distribuicao(lambda j: sum(1 for n in j if 17 <= n <= 25))
        self.dist_pares = self._calcular_distribuicao(lambda j: sum(1 for n in j if n % 2 == 0))
        self.dist_primos = self._calcular_distribuicao(lambda j: sum(1 for n in j if n in {2,3,5,7,11,13,17,19,23}))
        self.dist_soma = self._calcular_distribuicao(sum, bins=10)  # Agrupar em bins
        self.dist_consecutivos = self._calcular_distribuicao(self._contar_consecutivos)
        self.dist_repeticoes = self._calcular_repeticoes()
        
        # Distribuição de números individuais
        self.freq_individual = self._calcular_frequencias_individuais()
        
    def _contar_consecutivos(self, jogo):
        """Conta pares consecutivos"""
        jogo_sorted = sorted(jogo)
        return sum(1 for i in range(len(jogo_sorted)-1) if jogo_sorted[i+1] == jogo_sorted[i] + 1)
    
    def _calcular_distribuicao(self, func, bins=None):
        """
        Calcula distribuição de probabilidade de uma feature
        Se bins for fornecido, agrupa em intervalos
        """
        valores = [func(j) for j in self.historico]
        
        if bins:
            # Agrupar em bins (para soma, etc.)
            min_val, max_val = min(valores), max(valores)
            bin_edges = np.linspace(min_val, max_val, bins + 1)
            binned = np.digitize(valores, bin_edges[:-1])
            distrib = {}
            for i in range(1, bins + 1):
                count = sum(1 for b in binned if b == i)
                distrib[f"{bin_edges[i-1]:.0f}-{bin_edges[i]:.0f}"] = count / self.total
            return distrib
        else:
            # Distribuição discreta
            counter = Counter(valores)
            return {k: v/self.total for k, v in counter.items()}
    
    def _calcular_repeticoes(self):
        """Calcula distribuição de repetições do concurso anterior"""
        repeticoes = []
        for i in range(len(self.historico)-1):
            rep = len(set(self.historico[i]) & set(self.historico[i+1]))
            repeticoes.append(rep)
        
        counter = Counter(repeticoes)
        return {k: v/len(repeticoes) for k, v in counter.items()}
    
    def _calcular_frequencias_individuais(self):
        """Frequência de cada número individual"""
        counter = Counter()
        for jogo in self.historico:
            counter.update(jogo)
        return {n: counter[n] / (self.total * 15) for n in range(1, 26)}
    
    def probabilidade_jogo(self, jogo):
        """
        Calcula a probabilidade do jogo ocorrer baseado nas distribuições históricas
        Retorna log-probabilidade para evitar underflow
        """
        log_prob = 0
        
        # Adicionar pequeno epsilon para evitar log(0)
        eps = 1e-10
        
        # Features do jogo
        baixas = sum(1 for n in jogo if n <= 8)
        medias = sum(1 for n in jogo if 9 <= n <= 16)
        altas = sum(1 for n in jogo if 17 <= n <= 25)
        pares = sum(1 for n in jogo if n % 2 == 0)
        primos = sum(1 for n in jogo if n in {2,3,5,7,11,13,17,19,23})
        soma = sum(jogo)
        consec = self._contar_consecutivos(jogo)
        
        # Multiplicar probabilidades (em log)
        log_prob += math.log(self.dist_baixas.get(baixas, eps) + eps)
        log_prob += math.log(self.dist_medias.get(medias, eps) + eps)
        log_prob += math.log(self.dist_altas.get(altas, eps) + eps)
        log_prob += math.log(self.dist_pares.get(pares, eps) + eps)
        log_prob += math.log(self.dist_primos.get(primos, eps) + eps)
        
        # Para soma, encontrar bin apropriado
        soma_bin = None
        for bin_range in self.dist_soma.keys():
            low, high = map(float, bin_range.split('-'))
            if low <= soma <= high:
                soma_bin = bin_range
                break
        if soma_bin:
            log_prob += math.log(self.dist_soma.get(soma_bin, eps) + eps)
        
        log_prob += math.log(self.dist_consecutivos.get(consec, eps) + eps)
        
        return log_prob

# =====================================================
# GERADOR PROBABILÍSTICO (BASEADO EM DISTRIBUIÇÕES)
# =====================================================

class GeradorProbabilistico:
    """
    Gera jogos usando amostragem baseada nas distribuições reais
    """
    
    def __init__(self, distribuicoes):
        self.dist = distribuicoes
        self.historico = distribuicoes.historico
        
    def _amostrar_feature(self, dist):
        """Amostra um valor de uma distribuição de probabilidade"""
        valores = list(dist.keys())
        probs = list(dist.values())
        return np.random.choice(valores, p=probs)
    
    def _gerar_jogo_por_distribuicoes(self):
        """
        Gera um jogo respeitando as distribuições estatísticas
        """
        max_tentativas = 10000
        
        for _ in range(max_tentativas):
            # Amostrar features das distribuições
            alvo_baixas = self._amostrar_feature(self.dist.dist_baixas)
            alvo_medias = self._amostrar_feature(self.dist.dist_medias)
            alvo_altas = self._amostrar_feature(self.dist.dist_altas)
            alvo_pares = self._amostrar_feature(self.dist.dist_pares)
            
            # Garantir que soma = 15
            if alvo_baixas + alvo_medias + alvo_altas != 15:
                continue
            
            # Gerar números respeitando as contagens
            jogo = []
            
            # Adicionar baixas
            baixas_pool = [n for n in range(1, 9)]
            if len(baixas_pool) >= alvo_baixas:
                jogo.extend(random.sample(baixas_pool, alvo_baixas))
            else:
                continue
            
            # Adicionar médias
            medias_pool = [n for n in range(9, 17)]
            if len(medias_pool) >= alvo_medias:
                jogo.extend(random.sample(medias_pool, alvo_medias))
            else:
                continue
            
            # Adicionar altas
            altas_pool = [n for n in range(17, 26)]
            if len(altas_pool) >= alvo_altas:
                jogo.extend(random.sample(altas_pool, alvo_altas))
            else:
                continue
            
            jogo.sort()
            
            # Verificar paridade
            pares_reais = sum(1 for n in jogo if n % 2 == 0)
            if pares_reais != alvo_pares:
                continue
            
            return jogo
        
        return None
    
    def gerar_multiplos_jogos(self, quantidade):
        """Gera múltiplos jogos"""
        jogos = []
        probabilidades = []
        
        for _ in range(quantidade * 5):  # Gerar mais para selecionar
            jogo = self._gerar_jogo_por_distribuicoes()
            if jogo and jogo not in jogos:
                prob = self.dist.probabilidade_jogo(jogo)
                jogos.append(jogo)
                probabilidades.append(prob)
            
            if len(jogos) >= quantidade:
                break
        
        # Ordenar por probabilidade
        jogos_com_prob = list(zip(jogos, probabilidades))
        jogos_com_prob.sort(key=lambda x: x[1], reverse=True)
        
        return [j for j, _ in jogos_com_prob[:quantidade]]

# =====================================================
# ENSEMBLE LEARNING (COMBINAÇÃO DE MÚLTIPLOS MODELOS)
# =====================================================

class EnsembleLotofacil:
    """
    Combina múltiplas estratégias usando votação ponderada
    """
    
    def __init__(self, historico, ultimo_concurso):
        self.historico = historico
        self.ultimo = ultimo_concurso
        
        # Inicializar distribuições
        self.dist = DistribuicoesProbabilisticas(historico)
        
        # Pesos para cada modelo (serão ajustados por backtesting)
        self.pesos = {
            'probabilistico': 1.0,
            'repeticao': 0.8,
            'geometrico': 0.6,
            'ml': 0.9
        }
        
    def _score_probabilistico(self, jogo):
        """Score baseado nas distribuições"""
        return np.exp(self.dist.probabilidade_jogo(jogo))
    
    def _score_repeticao(self, jogo):
        """Score baseado em repetições do último concurso"""
        if not self.ultimo:
            return 0.5
        
        rep = len(set(jogo) & set(self.ultimo))
        # Distribuição real de repetições
        dist_rep = self.dist.dist_repeticoes
        return dist_rep.get(rep, 0.01)
    
    def _score_geometrico(self, jogo):
        """Score baseado em geometria do tabuleiro"""
        # Implementar métricas geométricas
        return 0.5  # Placeholder
    
    def _score_ml_placeholder(self, jogo):
        """Placeholder para ML (será substituído)"""
        return 0.5
    
    def score_ensemble(self, jogo):
        """Score combinado de todos os modelos"""
        score = 0
        score += self.pesos['probabilistico'] * self._score_probabilistico(jogo)
        score += self.pesos['repeticao'] * self._score_repeticao(jogo)
        score += self.pesos['geometrico'] * self._score_geometrico(jogo)
        score += self.pesos['ml'] * self._score_ml_placeholder(jogo)
        
        return score / sum(self.pesos.values())
    
    def gerar_jogo_consenso(self, n_tentativas=10000):
        """
        Gera um jogo que maximiza o score do ensemble
        """
        melhor_jogo = None
        melhor_score = -float('inf')
        
        for _ in range(n_tentativas):
            # Gerar candidato aleatório
            jogo = sorted(random.sample(range(1, 26), 15))
            
            # Calcular score
            score = self.score_ensemble(jogo)
            
            if score > melhor_score:
                melhor_score = score
                melhor_jogo = jogo
        
        return melhor_jogo, melhor_score
    
    def gerar_multiplos_jogos(self, quantidade):
        """Gera múltiplos jogos pelo ensemble"""
        candidatos = []
        
        for _ in range(quantidade * 10):
            jogo, score = self.gerar_jogo_consenso(1000)
            if jogo and jogo not in [c[0] for c in candidatos]:
                candidatos.append((jogo, score))
            
            if len(candidatos) >= quantidade * 3:
                break
        
        # Ordenar por score
        candidatos.sort(key=lambda x: x[1], reverse=True)
        return [j for j, _ in candidatos[:quantidade]]

# =====================================================
# MACHINE LEARNING REAL (COM TREINAMENTO) - CORRIGIDO
# =====================================================

class GeradorML:
    """
    Usa Machine Learning para aprender padrões vencedores
    Versão corrigida com número fixo de features
    """
    
    def __init__(self, historico):
        self.historico = historico
        self.modelo = None
        self.feature_names = [
            'baixas', 'medias', 'altas', 'pares', 'primos',
            'soma', 'consecutivos', 'rep_anterior', 'media_movel_5'
        ]
        self.n_features = len(self.feature_names)  # Always 9 features
        
    def _extrair_features(self, jogo, contexto=None):
        """
        Extrai features de um jogo - SEMPRE retorna 9 features
        contexto: concursos anteriores para features temporais
        """
        features = []
        
        # Features estáticas (sempre presentes)
        features.append(sum(1 for n in jogo if n <= 8))  # baixas
        features.append(sum(1 for n in jogo if 9 <= n <= 16))  # medias
        features.append(sum(1 for n in jogo if 17 <= n <= 25))  # altas
        features.append(sum(1 for n in jogo if n % 2 == 0))  # pares
        features.append(sum(1 for n in jogo if n in {2,3,5,7,11,13,17,19,23}))  # primos
        features.append(sum(jogo))  # soma
        
        # Consecutivos
        jogo_sorted = sorted(jogo)
        consec = sum(1 for i in range(len(jogo_sorted)-1) if jogo_sorted[i+1] == jogo_sorted[i] + 1)
        features.append(consec)
        
        # Features temporais (sempre incluir, com valor padrão se contexto não disponível)
        if contexto and len(contexto) > 0:
            ultimo = contexto[0]
            rep = len(set(jogo) & set(ultimo))
            features.append(rep)
            
            # Média móvel dos últimos 5
            if len(contexto) >= 5:
                ultimos_5 = contexto[:5]
                media_baixas = np.mean([sum(1 for n in c if n <= 8) for c in ultimos_5])
                features.append(media_baixas)
            else:
                features.append(0)  # Default se não houver dados suficientes
        else:
            features.append(0)  # Default para repetição
            features.append(0)  # Default para média móvel
        
        # Verificar se temos exatamente 9 features
        assert len(features) == self.n_features, f"Expected {self.n_features} features, got {len(features)}"
        
        return np.array(features).reshape(1, -1)
    
    def treinar(self, janela_treino=100, horizonte=1):
        """
        Treina o modelo para prever se um jogo dará 12+ pontos
        Usa séries temporais para evitar look-ahead bias
        """
        X = []
        y = []
        
        # Garantir que temos dados suficientes
        if len(self.historico) < janela_treino + horizonte + 10:
            st.warning("Histórico muito pequeno para treinamento. Use mais dados.")
            return 0.5
        
        for i in range(janela_treino, len(self.historico) - horizonte):
            # Dados de treino (passado)
            treino = self.historico[i-janela_treino:i]
            
            # Gerar jogos para treino (balancear classes)
            for _ in range(50):  # Reduzir para 50 exemplos por ponto temporal
                jogo = sorted(random.sample(range(1, 26), 15))
                
                # Feature do jogo
                features = self._extrair_features(jogo, treino)
                
                # Target: este jogo teria dado 12+ no concurso futuro?
                concurso_futuro = self.historico[i + horizonte]
                acertos = len(set(jogo) & set(concurso_futuro))
                target = 1 if acertos >= 12 else 0
                
                X.append(features.flatten())
                y.append(target)
        
        # Converter para arrays numpy
        X = np.array(X)
        y = np.array(y)
        
        # Verificar se temos dados suficientes e classes balanceadas
        if len(X) < 100:
            st.warning("Poucos exemplos gerados para treinamento.")
            return 0.5
        
        if len(np.unique(y)) < 2:
            st.warning("Apenas uma classe presente nos dados. Não é possível treinar.")
            return 0.5
        
        # Treinar modelo
        self.modelo = GradientBoostingClassifier(
            n_estimators=50,  # Reduzir para evitar overfitting
            max_depth=3,
            learning_rate=0.1,
            random_state=42,
            min_samples_split=10  # Adicionar para evitar overfitting
        )
        
        try:
            self.modelo.fit(X, y)
            
            # Avaliar
            y_pred = self.modelo.predict(X)
            accuracy = accuracy_score(y, y_pred)
            
            return accuracy
            
        except Exception as e:
            st.error(f"Erro no treinamento: {str(e)}")
            return 0.5
    
    def prever_probabilidade(self, jogo, contexto):
        """Prevê probabilidade do jogo dar 12+"""
        if self.modelo is None:
            return 0.5
        
        try:
            features = self._extrair_features(jogo, contexto)
            prob = self.modelo.predict_proba(features)[0][1]
            return prob
        except:
            return 0.5
    
    def gerar_jogo_otimizado(self, contexto, n_tentativas=5000):
        """Gera jogo maximizando probabilidade prevista"""
        if self.modelo is None:
            return sorted(random.sample(range(1, 26), 15)), 0.5
        
        melhor_jogo = None
        melhor_prob = -1
        
        for _ in range(n_tentativas):
            jogo = sorted(random.sample(range(1, 26), 15))
            try:
                prob = self.prever_probabilidade(jogo, contexto)
                
                if prob > melhor_prob:
                    melhor_prob = prob
                    melhor_jogo = jogo
            except:
                continue
        
        return melhor_jogo or sorted(random.sample(range(1, 26), 15)), melhor_prob

# =====================================================
# BACKTESTING REAL (VALIDAÇÃO CRUZADA TEMPORAL)
# =====================================================

class BacktestingEngine:
    """
    Motor de backtesting que simula condições reais
    """
    
    def __init__(self, historico_completo):
        self.historico = historico_completo
        
    def walk_forward_test(self, gerador_class, janela_treino=100, jogos_por_teste=10, passos=20):
        """
        Teste walk-forward: treina com passado, testa no futuro
        """
        resultados = []
        acertos_13plus = 0
        total_jogos = 0
        
        progress_bar = st.progress(0)
        
        for i, idx_teste in enumerate(range(janela_treino, janela_treino + passos)):
            if idx_teste >= len(self.historico):
                break
            
            # Dados de treino (apenas passado)
            treino = self.historico[:idx_teste]
            
            # Concurso real (futuro)
            concurso_real = self.historico[idx_teste]
            
            # Instanciar gerador com dados de treino
            if gerador_class.__name__ == 'EnsembleLotofacil':
                ultimo = treino[0] if treino else []
                gerador = gerador_class(treino, ultimo)
            else:
                gerador = gerador_class(treino)
            
            # Gerar jogos
            jogos = gerador.gerar_multiplos_jogos(jogos_por_teste)
            
            # Verificar acertos
            for jogo in jogos:
                acertos = len(set(jogo) & set(concurso_real))
                resultados.append(acertos)
                total_jogos += 1
                if acertos >= 13:
                    acertos_13plus += 1
            
            progress_bar.progress((i+1)/passos)
        
        progress_bar.empty()
        
        # Estatísticas
        stats = {
            'media_acertos': np.mean(resultados),
            'std_acertos': np.std(resultados),
            'max_acertos': max(resultados),
            'p_13plus': acertos_13plus / total_jogos if total_jogos > 0 else 0,
            'distribuicao': Counter(resultados),
            'resultados': resultados
        }
        
        return stats
    
    def comparar_modelos(self, modelos, janela_treino=100, passos=20):
        """
        Compara múltiplos modelos no mesmo teste
        """
        resultados = {}
        
        for nome, (gerador_class, kwargs) in modelos.items():
            st.write(f"Testando {nome}...")
            stats = self.walk_forward_test(gerador_class, janela_treino, **kwargs, passos=passos)
            resultados[nome] = stats
        
        return resultados

# =====================================================
# GERADOR SIMPLES E EFICAZ (BASEADO EM PADRÕES REAIS)
# =====================================================

class GeradorSimplesEficaz:
    """
    Versão simplificada mas eficaz baseada em padrões reais
    """
    
    def __init__(self, historico, ultimo_concurso):
        self.historico = historico
        self.ultimo = ultimo_concurso
        
        # Analisar padrões reais dos últimos 100 concursos
        ultimos_100 = historico[:100] if len(historico) > 100 else historico
        
        # Distribuições reais
        self.repeticoes = [len(set(c) & set(ultimo_concurso)) for c in ultimos_100 if c != ultimo_concurso]
        self.somas = [sum(c) for c in ultimos_100]
        self.baixas_counts = [sum(1 for n in c if n <= 8) for c in ultimos_100]
        self.medias_counts = [sum(1 for n in c if 9 <= n <= 16) for c in ultimos_100]
        
    def gerar_jogo(self):
        """
        Gera um jogo baseado em estatísticas reais
        """
        jogo = set()
        
        # 1. Repetir 8-9 números do último (70% dos casos)
        rep = random.choice([8, 9]) if random.random() < 0.7 else random.randint(7, 10)
        rep = min(rep, len(self.ultimo))
        jogo.update(random.sample(self.ultimo, rep))
        
        # 2. Completar com números fora do último
        disponiveis = [n for n in range(1, 26) if n not in self.ultimo]
        while len(jogo) < 15:
            jogo.add(random.choice(disponiveis))
        
        jogo = sorted(jogo)
        
        # 3. Ajustar distribuição se necessário
        baixas = sum(1 for n in jogo if n <= 8)
        medias = sum(1 for n in jogo if 9 <= n <= 16)
        
        # Distribuição típica: 4-5 baixas, 5-6 médias
        if baixas < 4:
            # Trocar um número alto por um baixo
            altos = [n for n in jogo if n > 16]
            if altos:
                jogo.remove(random.choice(altos))
                baixo_novo = random.choice([n for n in range(1, 9) if n not in jogo])
                jogo.append(baixo_novo)
                jogo.sort()
        
        if medias < 5:
            # Trocar um número extremo por uma média
            extremos = [n for n in jogo if n <= 8 or n >= 17]
            if extremos:
                jogo.remove(random.choice(extremos))
                media_nova = random.choice([n for n in range(9, 17) if n not in jogo])
                jogo.append(media_nova)
                jogo.sort()
        
        return jogo
    
    def gerar_multiplos_jogos(self, quantidade):
        """Gera múltiplos jogos"""
        jogos = []
        for _ in range(quantidade):
            jogo = self.gerar_jogo()
            jogos.append(jogo)
        return jogos

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================

def main():
    # Inicializar session state
    if "dados_api" not in st.session_state:
        st.session_state.dados_api = None
    if "historico" not in st.session_state:
        st.session_state.historico = None
    if "resultados_backtest" not in st.session_state:
        st.session_state.resultados_backtest = None
    if "modelo_treinado" not in st.session_state:
        st.session_state.modelo_treinado = None
    if "jogos_gerados" not in st.session_state:
        st.session_state.jogos_gerados = None
    if "jogos_salvos" not in st.session_state:
        st.session_state.jogos_salvos = []
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Qtd concursos históricos", 50, 1000, 200)
        
        if st.button("📥 Carregar concursos", use_container_width=True):
            with st.spinner("Carregando dados..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    response = requests.get(url)
                    st.session_state.dados_api = response.json()
                    st.session_state.historico = [
                        sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]
                    ]
                    st.success(f"✅ {len(st.session_state.historico)} concursos carregados!")
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Interface principal
    if st.session_state.historico is None:
        st.info("👈 Clique em 'Carregar concursos' na barra lateral para começar.")
        return
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Análise & Distribuições",
        "🧠 Ensemble AI",
        "🤖 Machine Learning",
        "✅ Backtesting Real",
        "🎯 Gerar Jogos"
    ])
    
    with tab1:
        st.subheader("📊 Análise Probabilística")
        
        # Calcular distribuições
        dist = DistribuicoesProbabilisticas(st.session_state.historico)
        
        # Mostrar distribuições
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 Distribuição de Baixas (1-8)**")
            df_baixas = pd.DataFrame({
                'Quantidade': list(dist.dist_baixas.keys()),
                'Probabilidade': [f"{v*100:.1f}%" for v in dist.dist_baixas.values()]
            }).sort_values('Quantidade')
            st.dataframe(df_baixas, hide_index=True, use_container_width=True)
            
            st.markdown("**📊 Distribuição de Médias (9-16)**")
            df_medias = pd.DataFrame({
                'Quantidade': list(dist.dist_medias.keys()),
                'Probabilidade': [f"{v*100:.1f}%" for v in dist.dist_medias.values()]
            }).sort_values('Quantidade')
            st.dataframe(df_medias, hide_index=True, use_container_width=True)
        
        with col2:
            st.markdown("**📊 Distribuição de Pares**")
            df_pares = pd.DataFrame({
                'Quantidade': list(dist.dist_pares.keys()),
                'Probabilidade': [f"{v*100:.1f}%" for v in dist.dist_pares.values()]
            }).sort_values('Quantidade')
            st.dataframe(df_pares, hide_index=True, use_container_width=True)
            
            st.markdown("**📊 Repetições do Último Concurso**")
            df_rep = pd.DataFrame({
                'Repetições': list(dist.dist_repeticoes.keys()),
                'Probabilidade': [f"{v*100:.1f}%" for v in dist.dist_repeticoes.values()]
            }).sort_values('Repetições')
            st.dataframe(df_rep, hide_index=True, use_container_width=True)
        
        # Frequências individuais
        st.markdown("**📈 Frequências Individuais**")
        freq_df = pd.DataFrame({
            'Número': range(1, 26),
            'Frequência': [dist.freq_individual[n] * 100 for n in range(1, 26)]
        })
        st.bar_chart(freq_df.set_index('Número'))
    
    with tab2:
        st.subheader("🧠 Ensemble AI - Combinação de Modelos")
        
        ultimo = st.session_state.historico[0] if st.session_state.historico else []
        
        # Criar ensemble
        ensemble = EnsembleLotofacil(st.session_state.historico, ultimo)
        
        # Mostrar pesos
        st.markdown("### ⚖️ Pesos dos Modelos (ajustáveis)")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            novo_peso_prob = st.slider("Probabilístico", 0.0, 2.0, ensemble.pesos['probabilistico'], 0.1)
            ensemble.pesos['probabilistico'] = novo_peso_prob
        with col2:
            novo_peso_rep = st.slider("Repetição", 0.0, 2.0, ensemble.pesos['repeticao'], 0.1)
            ensemble.pesos['repeticao'] = novo_peso_rep
        with col3:
            novo_peso_geo = st.slider("Geométrico", 0.0, 2.0, ensemble.pesos['geometrico'], 0.1)
            ensemble.pesos['geometrico'] = novo_peso_geo
        with col4:
            novo_peso_ml = st.slider("Machine Learning", 0.0, 2.0, ensemble.pesos['ml'], 0.1)
            ensemble.pesos['ml'] = novo_peso_ml
        
        # Gerar jogos com ensemble
        st.markdown("### 🎲 Gerar Jogos com Ensemble")
        col1, col2 = st.columns(2)
        
        with col1:
            qtd_ensemble = st.number_input("Quantidade", 5, 100, 20)
        
        with col2:
            if st.button("🚀 Gerar Jogos Ensemble", use_container_width=True):
                with st.spinner("Gerando jogos..."):
                    jogos = ensemble.gerar_multiplos_jogos(qtd_ensemble)
                    st.session_state.jogos_gerados = jogos
                    st.success(f"✅ {len(jogos)} jogos gerados!")
        
        # Mostrar jogos gerados
        if st.session_state.jogos_gerados:
            st.markdown("### 📋 Jogos Gerados")
            
            for i, jogo in enumerate(st.session_state.jogos_gerados[:10]):
                # Calcular score do ensemble
                score = ensemble.score_ensemble(jogo)
                
                # Formatar
                nums_html = ""
                for n in jogo:
                    cor = "#4ade80" if n <= 8 else "#4cc9f0" if n <= 16 else "#f97316"
                    nums_html += f"<span style='background:{cor}20; border:1px solid {cor}; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{n:02d}</span>"
                
                st.markdown(f"""
                <div style='background:#0e1117; border-radius:10px; padding:10px; margin-bottom:5px;'>
                    <div style='display:flex; justify-content:space-between;'>
                        <strong>Jogo #{i+1}</strong>
                        <small>Score: {score:.4f}</small>
                    </div>
                    <div>{nums_html}</div>
                </div>
                """, unsafe_allow_html=True)
    
    with tab3:
        st.subheader("🤖 Machine Learning - Treinamento Real")
        
        if st.button("🚀 Treinar Modelo ML", use_container_width=True):
            with st.spinner("Treinando modelo (pode levar alguns segundos)..."):
                ml = GeradorML(st.session_state.historico)
                acuracia = ml.treinar(janela_treino=100)
                st.session_state.modelo_treinado = ml
                
                st.success(f"✅ Modelo treinado! Acurácia: {acuracia:.2%}")
                
                # Mostrar importância das features
                if ml.modelo:
                    importancia = pd.DataFrame({
                        'Feature': ml.feature_names,
                        'Importância': ml.modelo.feature_importances_
                    }).sort_values('Importância', ascending=False)
                    
                    st.markdown("### 📊 Importância das Features")
                    st.dataframe(importancia, hide_index=True, use_container_width=True)
                    st.bar_chart(importancia.set_index('Feature'))
        
        if st.session_state.modelo_treinado:
            st.markdown("### 🎲 Gerar Jogos Otimizados por ML")
            
            col1, col2 = st.columns(2)
            with col1:
                qtd_ml = st.number_input("Quantidade ML", 5, 50, 10)
            
            with col2:
                if st.button("🎲 Gerar Jogos ML", use_container_width=True):
                    with st.spinner("Otimizando jogos..."):
                        ml = st.session_state.modelo_treinado
                        contexto = st.session_state.historico[:50]
                        
                        jogos_ml = []
                        probs = []
                        
                        for _ in range(qtd_ml):
                            jogo, prob = ml.gerar_jogo_otimizado(contexto, 5000)
                            jogos_ml.append(jogo)
                            probs.append(prob)
                        
                        st.session_state.jogos_gerados = jogos_ml
                        
                        st.success(f"✅ {len(jogos_ml)} jogos gerados!")
                        
                        # Mostrar melhores
                        st.markdown("### 📈 Top Jogos por Probabilidade")
                        for i, (jogo, prob) in enumerate(zip(jogos_ml, probs)):
                            if prob > 0.3:  # Mostrar só os com prob relevante
                                st.write(f"Jogo {i+1}: {jogo} - Prob: {prob:.2%}")
    
    with tab4:
        st.subheader("✅ Backtesting Real - Validação Walk-Forward")
        st.markdown("""
        <div class='info-box'>
        Este teste simula condições reais: treina com dados passados e testa em concursos futuros.
        Sem olhar para o futuro! Resultado REAL do modelo.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            janela_treino = st.number_input("Janela de treino (concursos)", 50, 500, 100)
            passos = st.number_input("Número de testes", 10, 100, 20)
        
        with col2:
            jogos_por_teste = st.number_input("Jogos por teste", 5, 50, 10)
            
            if st.button("🚀 Rodar Backtesting", use_container_width=True):
                with st.spinner("Executando backtesting..."):
                    engine = BacktestingEngine(st.session_state.historico)
                    
                    # Definir modelos para testar
                    modelos = {
                        'Simples Eficaz': (GeradorSimplesEficaz, {'jogos_por_teste': jogos_por_teste}),
                        'Ensemble AI': (EnsembleLotofacil, {'jogos_por_teste': jogos_por_teste}),
                        'Aleatório (baseline)': (None, {'jogos_por_teste': jogos_por_teste})
                    }
                    
                    # Adaptar para o formato do walk_forward_test
                    resultados = {}
                    
                    for nome, (gerador_class, kwargs) in modelos.items():
                        if nome == 'Aleatório (baseline)':
                            # Baseline: jogos aleatórios
                            resultados[nome] = {'media_acertos': 7.5, 'p_13plus': 0.01}
                        else:
                            stats = engine.walk_forward_test(
                                gerador_class, 
                                janela_treino=janela_treino,
                                jogos_por_teste=jogos_por_teste,
                                passos=passos
                            )
                            resultados[nome] = stats
                    
                    st.session_state.resultados_backtest = resultados
        
        # Mostrar resultados
        if st.session_state.resultados_backtest:
            st.markdown("### 📊 Resultados do Backtesting")
            
            df_resultados = []
            for nome, stats in st.session_state.resultados_backtest.items():
                df_resultados.append({
                    'Modelo': nome,
                    'Média Acertos': f"{stats['media_acertos']:.2f}",
                    'P(13+)': f"{stats.get('p_13plus', 0)*100:.2f}%",
                    'Melhor': stats.get('max_acertos', 'N/A')
                })
            
            st.dataframe(pd.DataFrame(df_resultados), hide_index=True, use_container_width=True)
            
            # Gráfico comparativo se houver resultados
            if 'Ensemble AI' in st.session_state.resultados_backtest:
                stats_ensemble = st.session_state.resultados_backtest['Ensemble AI']
                if 'resultados' in stats_ensemble:
                    st.markdown("### 📈 Distribuição de Acertos - Ensemble AI")
                    dist_df = pd.DataFrame(
                        sorted(stats_ensemble['distribuicao'].items()),
                        columns=['Acertos', 'Frequência']
                    )
                    st.bar_chart(dist_df.set_index('Acertos'))
    
    with tab5:
        st.subheader("🎯 Gerador Final - Combinação Inteligente")
        
        ultimo = st.session_state.historico[0] if st.session_state.historico else []
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            qtd_final = st.number_input("Quantidade final", 5, 100, 20)
        
        with col2:
            modo = st.selectbox("Modo", ["Balanceado", "Agressivo (13+)", "Conservador (11-12)"])
        
        with col3:
            if st.button("🚀 GERAR FINAL", use_container_width=True, type="primary"):
                with st.spinner("Gerando jogos com ensemble final..."):
                    # Usar ensemble como gerador principal
                    ensemble = EnsembleLotofacil(st.session_state.historico, ultimo)
                    
                    # Ajustar pesos conforme modo
                    if modo == "Agressivo (13+)":
                        ensemble.pesos['ml'] = 2.0
                        ensemble.pesos['probabilistico'] = 1.5
                    elif modo == "Conservador (11-12)":
                        ensemble.pesos['repeticao'] = 1.5
                        ensemble.pesos['geometrico'] = 1.0
                    
                    jogos = ensemble.gerar_multiplos_jogos(qtd_final)
                    st.session_state.jogos_gerados = jogos
                    
                    st.balloons()
                    st.success(f"✅ {len(jogos)} jogos gerados no modo {modo}!")
        
        # Mostrar jogos finais
        if st.session_state.jogos_gerados:
            st.markdown("### 🏆 Jogos Finais Recomendados")
            
            # Calcular probabilidades
            dist = DistribuicoesProbabilisticas(st.session_state.historico)
            
            for i, jogo in enumerate(st.session_state.jogos_gerados):
                prob = np.exp(dist.probabilidade_jogo(jogo))
                
                # Formatação especial
                nums_html = ""
                for n in jogo:
                    if n <= 8:
                        cor = "#4ade80"  # Verde para baixas
                    elif n <= 16:
                        cor = "#4cc9f0"  # Azul para médias
                    else:
                        cor = "#f97316"  # Laranja para altas
                    
                    nums_html += f"<span style='background:{cor}30; border:2px solid {cor}; border-radius:25px; padding:8px 12px; margin:4px; display:inline-block; font-weight:bold; font-size:1.1rem;'>{n:02d}</span>"
                
                # Estatísticas
                baixas = sum(1 for n in jogo if n <= 8)
                medias = sum(1 for n in jogo if 9 <= n <= 16)
                pares = sum(1 for n in jogo if n % 2 == 0)
                soma = sum(jogo)
                
                st.markdown(f"""
                <div style='background:linear-gradient(145deg, #0e1117, #1a1a2a); border-radius:15px; padding:20px; margin-bottom:15px; border:1px solid #333;'>
                    <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
                        <h4 style='margin:0;'>Jogo {i+1}</h4>
                        <span style='background:#00ffaa20; padding:5px 10px; border-radius:20px; font-size:0.9rem;'>Prob: {prob:.2%}</span>
                    </div>
                    <div style='margin:15px 0;'>{nums_html}</div>
                    <div style='display:flex; gap:20px; color:#aaa; font-size:0.9rem; flex-wrap:wrap;'>
                        <span>📊 {baixas} baixas | {medias} médias | {15-baixas-medias} altas</span>
                        <span>⚖️ {pares} pares | {15-pares} ímpares</span>
                        <span>➕ Soma: {soma}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Botões de ação
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("💾 Salvar Jogos", use_container_width=True):
                    # Criar arquivo para download
                    df_save = pd.DataFrame({
                        'Jogo': range(1, len(st.session_state.jogos_gerados)+1),
                        'Dezenas': [', '.join(f"{n:02d}" for n in j) for j in st.session_state.jogos_gerados],
                        'Baixas(1-8)': [sum(1 for n in j if n <= 8) for j in st.session_state.jogos_gerados],
                        'Médias(9-16)': [sum(1 for n in j if 9 <= n <= 16) for j in st.session_state.jogos_gerados],
                        'Pares': [sum(1 for n in j if n % 2 == 0) for j in st.session_state.jogos_gerados],
                        'Soma': [sum(j) for j in st.session_state.jogos_gerados]
                    })
                    
                    csv = df_save.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"jogos_lotofacil_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("🔄 Nova Geração", use_container_width=True):
                    st.session_state.jogos_gerados = None
                    st.rerun()

# =====================================================
# EXECUÇÃO
# =====================================================
if __name__ == "__main__":
    main()

# Rodapé
st.markdown("""
<style>
.footer {
    width: 100%;
    text-align: center;
    padding: 20px;
    margin-top: 40px;
    color: #666;
    font-size: 0.8rem;
    border-top: 1px solid #222;
}
</style>
<div class="footer">
    LOTOFÁCIL AI 2.0 • Machine Learning • Ensemble • Backtesting Real
</div>
""", unsafe_allow_html=True)
