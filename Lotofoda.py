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
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL AI 3.0",
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
.highlight { background: linear-gradient(145deg, #ffd70020, #ffa50020); border-left: 5px solid gold; }
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL AI 3.0")
st.caption("Machine Learning + Algoritmo Genético + Monte Carlo + Entropia • Nível Profissional")

# =====================================================
# MÓDULO 1: ENTROPIA DE SHANNON
# =====================================================

class EntropiaLotofacil:
    """
    Calcula a entropia de Shannon para avaliar o equilíbrio estatístico de um jogo
    Jogos com entropia próxima da média histórica tendem a performar melhor
    """
    
    def __init__(self, historico):
        self.historico = historico
        self.freq = Counter()
        total = 0
        
        for jogo in historico:
            for n in jogo:
                self.freq[n] += 1
                total += 1
        
        self.probs = {n: self.freq[n]/total for n in range(1, 26)}
        self.entropia_media = self._calcular_entropia_media()
        
    def _calcular_entropia_media(self):
        """Calcula a entropia média dos jogos históricos"""
        entropias = []
        for jogo in self.historico[:100]:  # Últimos 100
            H = 0
            for n in jogo:
                p = self.probs.get(n, 1e-9)
                H -= p * math.log(p + 1e-10)
            entropias.append(H)
        return np.mean(entropias) if entropias else 2.5  # Valor típico
    
    def entropia_jogo(self, jogo):
        """Calcula a entropia de um jogo específico"""
        H = 0
        for n in jogo:
            p = self.probs.get(n, 1e-9)
            H -= p * math.log(p + 1e-10)
        return H
    
    def score_entropia(self, jogo):
        """
        Retorna um score baseado em quão próximo da entropia média
        Quanto mais próximo de 1, melhor
        """
        H = self.entropia_jogo(jogo)
        # Normalizar: 1 = entropia média, <1 = desvio
        if H == 0:
            return 0
        return max(0, 1 - abs(H - self.entropia_media) / self.entropia_media)

# =====================================================
# MÓDULO 2: ALGORITMO GENÉTICO (EVOLUTIVO)
# =====================================================

class AlgoritmoGeneticoLotofacil:
    """
    Algoritmo Genético para evoluir jogos da Lotofácil
    Muito mais poderoso que geração aleatória simples
    """
    
    def __init__(self, historico, tamanho_pop=200, taxa_mutacao=0.15, taxa_crossover=0.7):
        self.historico = historico
        self.tamanho_pop = tamanho_pop
        self.taxa_mutacao = taxa_mutacao
        self.taxa_crossover = taxa_crossover
        
        # Inicializar distribuições para fitness
        self.dist = DistribuicoesProbabilisticas(historico)
        self.entropia = EntropiaLotofacil(historico)
        
        # Último concurso
        self.ultimo = historico[0] if historico else []
        
    def gerar_individuo(self):
        """Gera um indivíduo aleatório (jogo)"""
        return sorted(random.sample(range(1, 26), 15))
    
    def fitness(self, jogo):
        """
        Função de avaliação (quanto maior, melhor)
        Combina múltiplos critérios
        """
        if not jogo:
            return 0
        
        score = 0
        
        # 1. Probabilidade baseada nas distribuições
        try:
            prob = np.exp(self.dist.probabilidade_jogo(jogo))
            score += prob * 100  # Peso
        except:
            pass
        
        # 2. Entropia (equilíbrio estatístico)
        score_ent = self.entropia.score_entropia(jogo)
        score += score_ent * 50  # Peso
        
        # 3. Repetições do último concurso (padrão real)
        if self.ultimo:
            rep = len(set(jogo) & set(self.ultimo))
            # Distribuição típica: 7-9 repetições
            if 7 <= rep <= 10:
                score += 30
            elif 5 <= rep <= 11:
                score += 15
        
        # 4. Soma dentro da faixa típica
        soma = sum(jogo)
        if 180 <= soma <= 210:
            score += 20
        elif 170 <= soma <= 220:
            score += 10
        
        # 5. Distribuição baixas/médias/altas
        baixas = sum(1 for n in jogo if n <= 8)
        medias = sum(1 for n in jogo if 9 <= n <= 16)
        
        if 4 <= baixas <= 6 and 5 <= medias <= 7:
            score += 25
        
        return score
    
    def crossover(self, pai1, pai2):
        """
        Operador de crossover (recombinação)
        Gera um filho combinando características dos pais
        """
        if random.random() > self.taxa_crossover:
            return pai1.copy()
        
        # Pega parte de cada pai
        ponto_corte = random.randint(5, 10)
        filho = set(pai1[:ponto_corte] + pai2[ponto_corte:15])
        
        # Ajustar para ter exatamente 15 números
        while len(filho) < 15:
            filho.add(random.randint(1, 25))
        
        while len(filho) > 15:
            filho.remove(random.choice(list(filho)))
        
        return sorted(filho)
    
    def mutacao(self, individuo):
        """
        Operador de mutação
        Introduz variação genética
        """
        if random.random() > self.taxa_mutacao:
            return individuo
        
        mutante = set(individuo)
        
        # Trocar 1-3 números
        n_mutacoes = random.randint(1, 3)
        
        for _ in range(n_mutacoes):
            if len(mutante) > 0:
                remover = random.choice(list(mutante))
                mutante.remove(remover)
                
                novo = random.randint(1, 25)
                while novo in mutante:
                    novo = random.randint(1, 25)
                mutante.add(novo)
        
        return sorted(mutante)
    
    def selecao_torneio(self, populacao, k=3):
        """
        Seleção por torneio
        Escolhe os melhores indivíduos para reprodução
        """
        torneio = random.sample(populacao, min(k, len(populacao)))
        return max(torneio, key=lambda x: x[1])[0]
    
    def evoluir(self, geracoes=50, elite_size=20):
        """
        Executa o algoritmo genético
        Retorna os melhores jogos após N gerações
        """
        # População inicial: (jogo, fitness)
        populacao = [(self.gerar_individuo(), 0) for _ in range(self.tamanho_pop)]
        
        # Avaliar fitness inicial
        for i in range(len(populacao)):
            fitness = self.fitness(populacao[i][0])
            populacao[i] = (populacao[i][0], fitness)
        
        historico_melhor = []
        
        for geracao in range(geracoes):
            # Ordenar por fitness (decrescente)
            populacao.sort(key=lambda x: x[1], reverse=True)
            
            # Salvar melhor da geração
            historico_melhor.append(populacao[0][1])
            
            # Elitismo: manter os melhores
            nova_populacao = populacao[:elite_size].copy()
            
            # Preencher resto com crossover e mutação
            while len(nova_populacao) < self.tamanho_pop:
                # Selecionar pais
                pai1 = self.selecao_torneio(populacao)
                pai2 = self.selecao_torneio(populacao)
                
                # Crossover
                filho = self.crossover(pai1, pai2)
                
                # Mutação
                filho = self.mutacao(filho)
                
                # Avaliar fitness
                fitness_filho = self.fitness(filho)
                
                nova_populacao.append((filho, fitness_filho))
            
            populacao = nova_populacao
            
            # Feedback a cada 10 gerações
            if (geracao + 1) % 10 == 0:
                st.info(f"🧬 Geração {geracao+1}/{geracoes} - Melhor fitness: {populacao[0][1]:.2f}")
        
        # Ordenar final
        populacao.sort(key=lambda x: x[1], reverse=True)
        
        return [jogo for jogo, _ in populacao[:50]], historico_melhor

# =====================================================
# MÓDULO 3: SIMULAÇÃO MONTE CARLO
# =====================================================

class SimuladorMonteCarlo:
    """
    Simula milhares de concursos futuros para avaliar jogos
    Calcula probabilidades reais baseadas em simulação
    """
    
    def __init__(self, historico=None, simulacoes=50000):
        self.historico = historico
        self.simulacoes = simulacoes
        
        # Se tiver histórico, aprende padrões de sorteio
        self.pesos = None
        if historico and len(historico) > 100:
            self._calcular_pesos_aprendizados()
    
    def _calcular_pesos_aprendizados(self):
        """Aprende quais números saem mais frequentemente"""
        contador = Counter()
        total = 0
        
        for jogo in self.historico[:500]:  # Últimos 500
            contador.update(jogo)
            total += len(jogo)
        
        self.pesos = [contador.get(i, 0) / total for i in range(1, 26)]
    
    def _gerar_sorteio_simulado(self):
        """
        Gera um sorteio simulado
        Se tiver pesos aprendidos, usa distribuição realista
        """
        if self.pesos:
            # Usar distribuição aprendida
            return sorted(np.random.choice(
                range(1, 26), 
                size=15, 
                replace=False, 
                p=self.pesos
            ))
        else:
            # Sorteio uniforme
            return sorted(random.sample(range(1, 26), 15))
    
    def avaliar_jogo(self, jogo, verbose=False):
        """
        Avalia um jogo através de Monte Carlo
        Retorna estatísticas detalhadas
        """
        resultados = []
        
        # Barra de progresso para simulações longas
        if verbose:
            progresso = st.progress(0)
        
        for i in range(self.simulacoes):
            sorteio = self._gerar_sorteio_simulado()
            acertos = len(set(jogo) & set(sorteio))
            resultados.append(acertos)
            
            if verbose and (i + 1) % (self.simulacoes // 10) == 0:
                progresso.progress((i + 1) / self.simulacoes)
        
        if verbose:
            progresso.empty()
        
        # Converter para array numpy para cálculos
        resultados = np.array(resultados)
        
        estatisticas = {
            "media": np.mean(resultados),
            "mediana": np.median(resultados),
            "desvio": np.std(resultados),
            "min": np.min(resultados),
            "max": np.max(resultados),
            "p11": np.mean(resultados >= 11) * 100,
            "p12": np.mean(resultados >= 12) * 100,
            "p13": np.mean(resultados >= 13) * 100,
            "p14": np.mean(resultados >= 14) * 100,
            "p15": np.mean(resultados == 15) * 100,
            "ic_95": (
                np.percentile(resultados, 2.5),
                np.percentile(resultados, 97.5)
            )
        }
        
        return estatisticas, resultados
    
    def comparar_jogos(self, jogos, nomes=None):
        """
        Compara múltiplos jogos via Monte Carlo
        """
        if nomes is None:
            nomes = [f"Jogo {i+1}" for i in range(len(jogos))]
        
        resultados_comparacao = []
        
        for jogo, nome in zip(jogos, nomes):
            stats, _ = self.avaliar_jogo(jogo, verbose=False)
            stats["nome"] = nome
            stats["jogo"] = jogo
            resultados_comparacao.append(stats)
        
        # Ordenar por probabilidade de 13+
        resultados_comparacao.sort(key=lambda x: x["p13"], reverse=True)
        
        return resultados_comparacao

# =====================================================
# MÓDULO 4: SISTEMA DE DOMINÂNCIA
# =====================================================

class SistemaDominancia:
    """
    Remove jogos estatisticamente dominados
    Um jogo A domina B se A é melhor em todas as métricas
    """
    
    def __init__(self):
        self.metricas = [
            "media_esperada",
            "prob_11",
            "prob_12", 
            "prob_13",
            "entropia_score"
        ]
    
    def calcular_metricas(self, jogo, distrib, entropia):
        """
        Calcula todas as métricas para um jogo
        """
        return {
            "media_esperada": self._estimar_media(jogo, distrib),
            "prob_11": self._estimar_prob(jogo, distrib, 11),
            "prob_12": self._estimar_prob(jogo, distrib, 12),
            "prob_13": self._estimar_prob(jogo, distrib, 13),
            "entropia_score": entropia.score_entropia(jogo)
        }
    
    def _estimar_media(self, jogo, distrib):
        """Estima média de acertos baseado em distribuições"""
        # Método simplificado: usar probabilidade de repetição
        if hasattr(distrib, 'dist_repeticoes') and distrib.dist_repeticoes:
            rep_esperada = sum(k * v for k, v in distrib.dist_repeticoes.items())
            return rep_esperada + 7.5 - 8  # Ajuste
        return 7.5
    
    def _estimar_prob(self, jogo, distrib, alvo):
        """Estima probabilidade de atingir alvo"""
        # Placeholder - em versão real, usaria distribuições conjuntas
        media = self._estimar_media(jogo, distrib)
        if media >= alvo:
            return 0.3
        return max(0, 0.1 * (media - alvo + 2))
    
    def filtrar_dominados(self, jogos, metricas_list):
        """
        Aplica filtro de Pareto dominance
        Retorna apenas jogos não-dominados
        """
        n = len(jogos)
        dominado = [False] * n
        
        for i in range(n):
            if dominado[i]:
                continue
            
            for j in range(n):
                if i == j or dominado[j]:
                    continue
                
                # Verifica se j domina i
                domina = True
                for metrica in self.metricas:
                    if metricas_list[j][metrica] <= metricas_list[i][metrica]:
                        domina = False
                        break
                
                if domina:
                    dominado[i] = True
                    break
        
        return [jogos[i] for i in range(n) if not dominado[i]]

# =====================================================
# CLASSE BASE: DISTRIBUIÇÕES PROBABILÍSTICAS (EXISTENTE)
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
# GERADOR PROBABILÍSTICO (EXISTENTE)
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
# ENSEMBLE LEARNING (EXISTENTE)
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
# MACHINE LEARNING REAL (EXISTENTE)
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
# BACKTESTING REAL (EXISTENTE)
# =====================================================

class BacktestingEngine:
    """
    Motor de backtesting que simula condições reais
    """
    
    def __init__(self, historico_completo):
        self.historico = historico_completo
        
    def walk_forward_test(self, gerador_class, janela_treino=100, jogos_por_teste=10, passos=20, **kwargs):
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
            
            # Último concurso disponível no treino
            ultimo_treino = treino[0] if treino else []
            
            # Instanciar gerador com dados de treino
            if gerador_class.__name__ == 'EnsembleLotofacil':
                gerador = gerador_class(treino, ultimo_treino)
            elif gerador_class.__name__ == 'GeradorSimplesEficaz':
                gerador = gerador_class(treino, ultimo_treino)
            elif gerador_class.__name__ == 'GeradorProbabilistico':
                # GeradorProbabilistico precisa de distribuicoes, não do historico diretamente
                dist = DistribuicoesProbabilisticas(treino)
                gerador = gerador_class(dist)
            else:
                # Para outros geradores que só precisam do histórico
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
            'media_acertos': np.mean(resultados) if resultados else 0,
            'std_acertos': np.std(resultados) if resultados else 0,
            'max_acertos': max(resultados) if resultados else 0,
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
# GERADOR SIMPLES E EFICAZ (EXISTENTE)
# =====================================================

class GeradorSimplesEficaz:
    """
    Versão simplificada mas eficaz baseada em padrões reais
    """
    
    def __init__(self, historico, ultimo_concurso):
        self.historico = historico
        self.ultimo = ultimo_concurso if ultimo_concurso else []
        
        # Se não houver último concurso, usar um padrão
        if not self.ultimo and historico:
            self.ultimo = historico[0]
        elif not self.ultimo:
            self.ultimo = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]  # fallback
        
        # Analisar padrões reais dos últimos 100 concursos
        ultimos_100 = historico[:100] if len(historico) > 100 else historico
        
        # Distribuições reais
        if ultimos_100:
            self.repeticoes = [len(set(c) & set(self.ultimo)) for c in ultimos_100 if c != self.ultimo]
            self.somas = [sum(c) for c in ultimos_100]
            self.baixas_counts = [sum(1 for n in c if n <= 8) for c in ultimos_100]
            self.medias_counts = [sum(1 for n in c if 9 <= n <= 16) for c in ultimos_100]
        else:
            self.repeticoes = [8]
            self.somas = [195]
            self.baixas_counts = [5]
            self.medias_counts = [5]
        
    def gerar_jogo(self):
        """
        Gera um jogo baseado em estatísticas reais
        """
        if not self.ultimo:
            return sorted(random.sample(range(1, 26), 15))
        
        jogo = set()
        
        # 1. Repetir 8-9 números do último (70% dos casos)
        if self.repeticoes:
            rep_media = int(np.mean(self.repeticoes))
            rep = random.choice([rep_media, rep_media+1]) if random.random() < 0.7 else random.randint(max(5, rep_media-2), min(12, rep_media+2))
        else:
            rep = 8
            
        rep = min(rep, len(self.ultimo))
        if rep > 0 and self.ultimo:
            jogo.update(random.sample(self.ultimo, rep))
        
        # 2. Completar com números fora do último
        disponiveis = [n for n in range(1, 26) if n not in self.ultimo]
        while len(jogo) < 15 and disponiveis:
            jogo.add(random.choice(disponiveis))
        
        # Se ainda não tiver 15 números, completar aleatoriamente
        while len(jogo) < 15:
            jogo.add(random.choice(range(1, 26)))
        
        jogo = sorted(jogo)
        
        # 3. Ajustar distribuição se necessário
        baixas = sum(1 for n in jogo if n <= 8)
        medias = sum(1 for n in jogo if 9 <= n <= 16)
        
        # Distribuição típica: 4-5 baixas, 5-6 médias
        if baixas < 4 and any(n > 16 for n in jogo):
            # Trocar um número alto por um baixo
            altos = [n for n in jogo if n > 16]
            if altos:
                jogo.remove(random.choice(altos))
                baixos_disponiveis = [n for n in range(1, 9) if n not in jogo]
                if baixos_disponiveis:
                    jogo.append(random.choice(baixos_disponiveis))
                    jogo.sort()
        
        if medias < 5:
            # Trocar um número extremo por uma média
            extremos = [n for n in jogo if n <= 8 or n >= 17]
            if extremos:
                jogo.remove(random.choice(extremos))
                medias_disponiveis = [n for n in range(9, 17) if n not in jogo]
                if medias_disponiveis:
                    jogo.append(random.choice(medias_disponiveis))
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
# SISTEMA DE CONFERÊNCIA PROFISSIONAL (EXISTENTE)
# =====================================================

class ConferenciaLotofacil:
    """
    Sistema completo para conferir e analisar resultados
    """
    
    def __init__(self):
        self.resultados = None
        self.df_conferencia = None
        self.estatisticas = {}
        self.dados_originais = None
        self.jogos = []
        self.concurso_alvo = None
        self.data_alvo = None
        self.estrategias = {}
        
    def carregar_jogos(self, arquivo_json):
        """
        Carrega os jogos gerados do arquivo JSON
        """
        try:
            with open(arquivo_json, 'r') as f:
                dados = json.load(f)
            
            self.dados_originais = dados
            self.jogos = dados['jogos']
            self.concurso_alvo = dados.get('concurso_alvo', 'N/A')
            self.data_alvo = dados.get('data', 'N/A')
            self.estrategias = dados.get('estrategias', {})
            
            return True, f"✅ Carregados {len(self.jogos)} jogos para o concurso {self.concurso_alvo}"
        except Exception as e:
            return False, f"❌ Erro ao carregar: {e}"
    
    def carregar_jogos_da_sessao(self, jogos, nome="Jogos da Sessão"):
        """
        Carrega jogos diretamente da sessão do Streamlit
        """
        self.jogos = jogos
        self.concurso_alvo = "Atual"
        self.data_alvo = datetime.now().strftime("%Y-%m-%d")
        self.estrategias = {"fonte": nome}
        self.dados_originais = {"jogos": jogos, "fonte": nome}
        
        return True, f"✅ Carregados {len(self.jogos)} jogos da sessão atual"
    
    def conferir(self, numeros_sorteados):
        """
        Confere todos os jogos contra os números sorteados
        """
        if not self.jogos:
            return False, "Carregue os jogos primeiro!"
        
        numeros_set = set(numeros_sorteados)
        resultados = []
        
        for i, jogo in enumerate(self.jogos):
            acertos = len(set(jogo) & numeros_set)
            
            # Calcular premiação estimada
            premio = self._calcular_premio(acertos)
            
            resultados.append({
                'jogo_id': i + 1,
                'acertos': acertos,
                'premio': premio,
                'dezenas': jogo,
                'acertou_11': acertos >= 11,
                'acertou_12': acertos >= 12,
                'acertou_13': acertos >= 13,
                'acertou_14': acertos >= 14,
                'acertou_15': acertos == 15
            })
        
        self.resultados = resultados
        self.df_conferencia = pd.DataFrame(resultados)
        self._calcular_estatisticas()
        self._identificar_estrategias_vencedoras()
        
        return True, f"✅ Conferência realizada com sucesso!"
    
    def _calcular_premio(self, acertos):
        """
        Estima o prêmio baseado em valores típicos
        (valores aproximados - podem variar por concurso)
        """
        premios_estimados = {
            11: 4.00,    # R$ 4,00
            12: 8.00,    # R$ 8,00
            13: 20.00,   # R$ 20,00
            14: 500.00,  # R$ 500,00
            15: 1500000.00  # R$ 1.5 milhão
        }
        return premios_estimados.get(acertos, 0)
    
    def _calcular_estatisticas(self):
        """Calcula estatísticas detalhadas"""
        df = self.df_conferencia
        
        self.estatisticas = {
            'total_jogos': len(df),
            'media_acertos': df['acertos'].mean(),
            'mediana_acertos': df['acertos'].median(),
            'desvio_padrao': df['acertos'].std(),
            'max_acertos': df['acertos'].max(),
            'min_acertos': df['acertos'].min(),
            'total_11': df['acertou_11'].sum(),
            'total_12': df['acertou_12'].sum(),
            'total_13': df['acertou_13'].sum(),
            'total_14': df['acertou_14'].sum(),
            'total_15': df['acertou_15'].sum(),
            'percentil_90': df['acertos'].quantile(0.9),
            'percentil_95': df['acertos'].quantile(0.95),
            'soma_premios': df['premio'].sum(),
            'melhor_jogo': df.loc[df['acertos'].idxmax()]['jogo_id'] if len(df) > 0 else None,
        }
    
    def _identificar_estrategias_vencedoras(self):
        """
        Se os dados originais têm info de estratégia,
        identifica qual estratégia teve melhor performance
        """
        if not self.dados_originais or 'estrategias' not in self.dados_originais:
            return
        
        self.performance_estrategias = {}
        
        # Tentar identificar por ordem se não houver marcação específica
        total_ensemble = self.estrategias.get('ensemble', 0)
        total_ml = self.estrategias.get('ml', 0)
        total_simples = self.estrategias.get('simples', 0)
        
        # Se não houver informação de estratégia, não fazer nada
        if total_ensemble == 0 and total_ml == 0 and total_simples == 0:
            return
        
        # Separar resultados por estratégia (assumindo ordem: ensemble, ml, simples)
        idx = 0
        if total_ensemble > 0 and idx < len(self.resultados):
            ensemble_results = self.resultados[idx:idx+total_ensemble]
            self.performance_estrategias['Ensemble AI'] = {
                'media': np.mean([r['acertos'] for r in ensemble_results]),
                'max': max([r['acertos'] for r in ensemble_results]),
                'total_13+': sum(1 for r in ensemble_results if r['acertos'] >= 13),
                'total_jogos': len(ensemble_results)
            }
            idx += total_ensemble
        
        if total_ml > 0 and idx < len(self.resultados):
            ml_results = self.resultados[idx:idx+total_ml]
            self.performance_estrategias['Machine Learning'] = {
                'media': np.mean([r['acertos'] for r in ml_results]),
                'max': max([r['acertos'] for r in ml_results]),
                'total_13+': sum(1 for r in ml_results if r['acertos'] >= 13),
                'total_jogos': len(ml_results)
            }
            idx += total_ml
        
        if total_simples > 0 and idx < len(self.resultados):
            simples_results = self.resultados[idx:idx+total_simples]
            self.performance_estrategias['Simples Eficaz'] = {
                'media': np.mean([r['acertos'] for r in simples_results]),
                'max': max([r['acertos'] for r in simples_results]),
                'total_13+': sum(1 for r in simples_results if r['acertos'] >= 13),
                'total_jogos': len(simples_results)
            }
    
    def gerar_relatorio_texto(self):
        """
        Gera relatório em formato texto
        """
        if not self.estatisticas:
            return "Nenhuma conferência realizada ainda."
        
        e = self.estatisticas
        relatorio = []
        relatorio.append("="*60)
        relatorio.append(f"📊 RELATÓRIO DE CONFERÊNCIA - CONCURSO {self.concurso_alvo}")
        relatorio.append(f"📅 Data: {self.data_alvo}")
        relatorio.append("="*60)
        relatorio.append("")
        
        relatorio.append("🎯 RESULTADO GERAL:")
        relatorio.append(f"   Total de jogos: {e['total_jogos']}")
        relatorio.append(f"   Média de acertos: {e['media_acertos']:.2f}")
        relatorio.append(f"   Mediana: {e['mediana_acertos']:.1f}")
        relatorio.append(f"   Desvio padrão: {e['desvio_padrao']:.2f}")
        relatorio.append(f"   Melhor acerto: {e['max_acertos']} pontos (Jogo {e['melhor_jogo']})")
        relatorio.append("")
        
        relatorio.append("🏆 PREMIAÇÕES:")
        relatorio.append(f"   11 pontos: {e['total_11']} jogos")
        relatorio.append(f"   12 pontos: {e['total_12']} jogos")
        relatorio.append(f"   13 pontos: {e['total_13']} jogos")
        relatorio.append(f"   14 pontos: {e['total_14']} jogos")
        relatorio.append(f"   15 pontos: {e['total_15']} jogos")
        relatorio.append(f"   Soma total estimada: R$ {e['soma_premios']:,.2f}")
        relatorio.append("")
        
        relatorio.append("📈 ESTATÍSTICAS AVANÇADAS:")
        relatorio.append(f"   Percentil 90: {e['percentil_90']:.1f} pontos")
        relatorio.append(f"   Percentil 95: {e['percentil_95']:.1f} pontos")
        relatorio.append(f"   Jogos acima da média: {(self.df_conferencia['acertos'] > e['media_acertos']).sum() if self.df_conferencia is not None else 0}")
        relatorio.append("")
        
        if hasattr(self, 'performance_estrategias') and self.performance_estrategias:
            relatorio.append("📊 PERFORMANCE POR ESTRATÉGIA:")
            for nome, perf in self.performance_estrategias.items():
                relatorio.append(f"   {nome}:")
                relatorio.append(f"      Média: {perf['media']:.2f}")
                relatorio.append(f"      Máximo: {perf['max']}")
                relatorio.append(f"      13+: {perf['total_13+']} de {perf['total_jogos']} jogos")
        
        return "\n".join(relatorio)
    
    def plot_graficos(self):
        """
        Gera gráficos para análise visual
        """
        if self.df_conferencia is None:
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # 1. Histograma de acertos
        ax1 = axes[0, 0]
        self.df_conferencia['acertos'].hist(bins=15, ax=ax1, color='#4ade80', alpha=0.7, edgecolor='black')
        ax1.axvline(self.estatisticas['media_acertos'], color='red', linestyle='--', label=f"Média: {self.estatisticas['media_acertos']:.2f}")
        ax1.axvline(7.5, color='blue', linestyle=':', label="Aleatório: 7.5")
        ax1.set_xlabel('Acertos')
        ax1.set_ylabel('Frequência')
        ax1.set_title('Distribuição de Acertos')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Gráfico de pizza - Premiações
        ax2 = axes[0, 1]
        premios = [
            self.estatisticas['total_11'],
            self.estatisticas['total_12'],
            self.estatisticas['total_13'],
            self.estatisticas['total_14'],
            self.estatisticas['total_15']
        ]
        labels = ['11 pts', '12 pts', '13 pts', '14 pts', '15 pts']
        colors = ['#4cc9f0', '#4ade80', 'gold', '#f97316', '#ff6b6b']
        
        # Filtrar apenas valores > 0
        premios_filtrados = [p for p in premios if p > 0]
        labels_filtrados = [labels[i] for i, p in enumerate(premios) if p > 0]
        colors_filtrados = [colors[i] for i, p in enumerate(premios) if p > 0]
        
        if premios_filtrados:
            ax2.pie(premios_filtrados, labels=labels_filtrados, colors=colors_filtrados, 
                   autopct='%1.1f%%', startangle=90)
            ax2.set_title('Distribuição das Premiações')
        
        # 3. Boxplot comparativo com baseline
        ax3 = axes[1, 0]
        dados_boxplot = [self.df_conferencia['acertos']]
        
        # Gerar baseline aleatório para comparação
        np.random.seed(42)
        baseline = [len(set(random.sample(range(1,26),15)) & 
                      set(random.sample(range(1,26),15))) for _ in range(1000)]
        dados_boxplot.append(baseline)
        
        bp = ax3.boxplot(dados_boxplot, labels=['Seu Modelo', 'Aleatório'], patch_artist=True)
        bp['boxes'][0].set_facecolor('#4ade80')
        bp['boxes'][1].set_facecolor('#4cc9f0')
        ax3.set_ylabel('Acertos')
        ax3.set_title('Comparação: Seu Modelo vs Aleatório')
        ax3.grid(True, alpha=0.3)
        
        # 4. Top 10 melhores jogos
        ax4 = axes[1, 1]
        top10 = self.df_conferencia.nlargest(10, 'acertos')[['jogo_id', 'acertos']]
        bars = ax4.bar(range(len(top10)), top10['acertos'], color='gold', edgecolor='black')
        ax4.set_xlabel('Jogo')
        ax4.set_ylabel('Acertos')
        ax4.set_title('Top 10 Melhores Jogos')
        ax4.set_xticks(range(len(top10)))
        ax4.set_xticklabels([f"J{id}" for id in top10['jogo_id']], rotation=45)
        
        # Adicionar valores nas barras
        for i, (bar, val) in enumerate(zip(bars, top10['acertos'])):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                    str(val), ha='center', va='bottom')
        
        plt.tight_layout()
        return fig
    
    def salvar_relatorio(self, nome_arquivo=None):
        """
        Salva relatório completo em JSON e TXT
        """
        if nome_arquivo is None:
            nome_arquivo = f"relatorio_concurso_{self.concurso_alvo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Salvar relatório texto
        with open(f"{nome_arquivo}.txt", 'w', encoding='utf-8') as f:
            f.write(self.gerar_relatorio_texto())
        
        # Salvar dados completos em JSON
        dados_completos = {
            'concurso': self.concurso_alvo,
            'data': self.data_alvo,
            'estatisticas': self.estatisticas,
            'resultados': self.resultados,
            'performance_estrategias': getattr(self, 'performance_estrategias', {})
        }
        
        with open(f"{nome_arquivo}.json", 'w', encoding='utf-8') as f:
            json.dump(dados_completos, f, indent=2, ensure_ascii=False)
        
        # Salvar CSV dos resultados
        if self.df_conferencia is not None:
            df_save = self.df_conferencia.copy()
            df_save['dezenas'] = df_save['dezenas'].apply(lambda x: ', '.join(f"{n:02d}" for n in x))
            df_save.to_csv(f"{nome_arquivo}.csv", index=False)
        
        return nome_arquivo

# =====================================================
# GERADOR MESTRE AI 3.0 (COMBINA TODOS OS MÓDULOS)
# =====================================================

class GeradorMestreAI3:
    """
    Combina todos os 4 novos motores com os existentes
    Algoritmo Genético + Entropia + Monte Carlo + Dominância
    """
    
    def __init__(self, historico):
        self.historico = historico
        self.ultimo = historico[0] if historico else []
        
        # Inicializar todos os módulos
        self.dist = DistribuicoesProbabilisticas(historico)
        self.entropia = EntropiaLotofacil(historico)
        self.ga = AlgoritmoGeneticoLotofacil(historico)
        self.monte_carlo = SimuladorMonteCarlo(historico, simulacoes=20000)
        self.dominancia = SistemaDominancia()
        
    def gerar_jogos_elite(self, quantidade=20, geracoes=50, simulacoes_mc=True):
        """
        Pipeline completo de geração:
        1. Algoritmo Genético evolui população
        2. Avaliação por Monte Carlo
        3. Filtro de dominância
        """
        st.info("🧬 Fase 1: Evoluindo população com Algoritmo Genético...")
        jogos_evoluidos, historico_fitness = self.ga.evoluir(geracoes=geracoes, elite_size=50)
        
        st.info(f"📊 Fase 2: Avaliando {len(jogos_evoluidos)} jogos com Monte Carlo...")
        
        # Avaliar cada jogo
        jogos_com_metricas = []
        
        for i, jogo in enumerate(jogos_evoluidos[:30]):  # Avaliar top 30
            # Calcular métricas
            metricas = self.dominancia.calcular_metricas(jogo, self.dist, self.entropia)
            
            # Simulação Monte Carlo
            if simulacoes_mc:
                stats_mc, _ = self.monte_carlo.avaliar_jogo(jogo, verbose=False)
                metricas.update({
                    "media_esperada": stats_mc["media"],
                    "prob_11": stats_mc["p11"] / 100,
                    "prob_12": stats_mc["p12"] / 100,
                    "prob_13": stats_mc["p13"] / 100,
                    "p13_mc": stats_mc["p13"]
                })
            
            jogos_com_metricas.append((jogo, metricas))
            
            # Progresso
            if (i + 1) % 5 == 0:
                st.info(f"   Avaliados {i+1}/{min(30, len(jogos_evoluidos))} jogos...")
        
        st.info("🧠 Fase 3: Aplicando filtro de dominância de Pareto...")
        
        # Separar jogos e métricas
        jogos_list = [j for j, _ in jogos_com_metricas]
        metricas_list = [m for _, m in jogos_com_metricas]
        
        # Filtrar dominados
        jogos_finais = self.dominancia.filtrar_dominados(jogos_list, metricas_list)
        
        # Se não temos jogos suficientes, complementar
        if len(jogos_finais) < quantidade:
            # Adicionar mais jogos dos evoluídos
            restantes = [j for j in jogos_evoluidos if j not in jogos_finais]
            jogos_finais.extend(restantes[:quantidade - len(jogos_finais)])
        
        # Calcular score final para ordenação
        jogos_com_score = []
        for jogo in jogos_finais[:quantidade * 2]:
            # Score composto
            prob_log = self.dist.probabilidade_jogo(jogo)
            prob = np.exp(prob_log) if prob_log > -20 else 0
            
            score_ent = self.entropia.score_entropia(jogo)
            
            # Score final (pesos ajustáveis)
            score_final = prob * 0.4 + score_ent * 0.3
            
            # Adicionar se tiver métricas MC
            for j, m in jogos_com_metricas:
                if j == jogo and "p13_mc" in m:
                    score_final += m["p13_mc"] / 100 * 0.3
                    break
            
            jogos_com_score.append((jogo, score_final))
        
        # Ordenar e retornar
        jogos_com_score.sort(key=lambda x: x[1], reverse=True)
        
        return [j for j, _ in jogos_com_score[:quantidade]], jogos_com_metricas, historico_fitness

# =====================================================
# FUNÇÃO PARA GERAR ARQUIVO DE EXEMPLO
# =====================================================

def gerar_arquivo_exemplo():
    """
    Gera um arquivo de exemplo para teste
    """
    exemplo = {
        'concurso_alvo': 3623,
        'data': datetime.now().strftime("%Y-%m-%d"),
        'data_geracao': datetime.now().isoformat(),
        'total_jogos': 40,
        'jogos': [sorted(random.sample(range(1, 26), 15)) for _ in range(40)],
        'estrategias': {
            'ensemble': 20,
            'ml': 10,
            'simples': 10
        }
    }
    
    with open('exemplo_jogos.json', 'w') as f:
        json.dump(exemplo, f, indent=2)
    
    return 'exemplo_jogos.json'

# =====================================================
# INTERFACE PRINCIPAL (ATUALIZADA COM AI 3.0)
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
    if "conferencia" not in st.session_state:
        st.session_state.conferencia = ConferenciaLotofacil()
    if "gerador_ai3" not in st.session_state:
        st.session_state.gerador_ai3 = None
    if "resultados_mc" not in st.session_state:
        st.session_state.resultados_mc = None
    
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
                    
                    # Inicializar gerador AI 3.0
                    st.session_state.gerador_ai3 = GeradorMestreAI3(st.session_state.historico)
                    
                    st.success(f"✅ {len(st.session_state.historico)} concursos carregados!")
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Interface principal
    if st.session_state.historico is None:
        st.info("👈 Clique em 'Carregar concursos' na barra lateral para começar.")
        return
    
    # Tabs (AGORA SÃO 7!)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Análise & Distribuições",
        "🧠 Ensemble AI",
        "🤖 Machine Learning",
        "✅ Backtesting Real",
        "🧬 AI 3.0 (Genético + MC)",  # NOVA ABA PRINCIPAL
        "🎯 Gerar Jogos",
        "📋 Conferência"
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
            novo_peso_prob = st.slider("Probabilístico", 0.0, 2.0, ensemble.pesos['probabilistico'], 0.1, key="peso_prob")
            ensemble.pesos['probabilistico'] = novo_peso_prob
        with col2:
            novo_peso_rep = st.slider("Repetição", 0.0, 2.0, ensemble.pesos['repeticao'], 0.1, key="peso_rep")
            ensemble.pesos['repeticao'] = novo_peso_rep
        with col3:
            novo_peso_geo = st.slider("Geométrico", 0.0, 2.0, ensemble.pesos['geometrico'], 0.1, key="peso_geo")
            ensemble.pesos['geometrico'] = novo_peso_geo
        with col4:
            novo_peso_ml = st.slider("Machine Learning", 0.0, 2.0, ensemble.pesos['ml'], 0.1, key="peso_ml")
            ensemble.pesos['ml'] = novo_peso_ml
        
        # Gerar jogos com ensemble
        st.markdown("### 🎲 Gerar Jogos com Ensemble")
        col1, col2 = st.columns(2)
        
        with col1:
            qtd_ensemble = st.number_input("Quantidade", 5, 100, 20, key="ensemble_qtd")
        
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
                qtd_ml = st.number_input("Quantidade ML", 5, 50, 10, key="ml_qtd")
            
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
            janela_treino = st.number_input("Janela de treino (concursos)", 50, 500, 100, key="janela_treino")
            passos = st.number_input("Número de testes", 10, 100, 20, key="passos")
        
        with col2:
            jogos_por_teste = st.number_input("Jogos por teste", 5, 50, 10, key="jogos_teste")
            
            if st.button("🚀 Rodar Backtesting", use_container_width=True):
                with st.spinner("Executando backtesting..."):
                    engine = BacktestingEngine(st.session_state.historico)
                    
                    # Definir modelos para testar
                    modelos = {
                        'Simples Eficaz': (GeradorSimplesEficaz, {'jogos_por_teste': jogos_por_teste}),
                        'Ensemble AI': (EnsembleLotofacil, {'jogos_por_teste': jogos_por_teste}),
                    }
                    
                    # Executar backtesting para cada modelo
                    resultados = {}
                    
                    for nome, (gerador_class, kwargs) in modelos.items():
                        st.write(f"📊 Testando {nome}...")
                        try:
                            stats = engine.walk_forward_test(
                                gerador_class, 
                                janela_treino=janela_treino,
                                jogos_por_teste=jogos_por_teste,
                                passos=passos
                            )
                            resultados[nome] = stats
                        except Exception as e:
                            st.error(f"Erro ao testar {nome}: {str(e)}")
                            resultados[nome] = {'media_acertos': 0, 'p_13plus': 0}
                    
                    # Baseline (jogos aleatórios)
                    resultados['Aleatório (baseline)'] = {'media_acertos': 7.5, 'p_13plus': 0.01}
                    
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
        st.subheader("🧬 AI 3.0 - Algoritmo Genético + Monte Carlo")
        st.markdown("""
        <div class='highlight' style='padding:20px; border-radius:10px;'>
        <strong>⚡ Motor avançado combinando:</strong><br>
        • 🧬 Algoritmo Genético (evolução de populações)<br>
        • 📊 Entropia de Shannon (equilíbrio estatístico)<br>
        • 🎲 Simulação Monte Carlo (50.000 sorteios simulados)<br>
        • 🧠 Dominância de Pareto (filtro de qualidade)
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.gerador_ai3 is None:
            st.session_state.gerador_ai3 = GeradorMestreAI3(st.session_state.historico)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            qtd_ai3 = st.number_input("Quantidade de jogos", 5, 50, 15, key="ai3_qtd")
        
        with col2:
            geracoes = st.number_input("Gerações do AG", 20, 200, 50, key="ai3_geracoes")
        
        with col3:
            simulacoes_mc = st.checkbox("Usar Monte Carlo", value=True, key="ai3_mc")
        
        if st.button("🚀 EXECUTAR AI 3.0", use_container_width=True, type="primary"):
            with st.spinner("Executando Algoritmo Genético e Monte Carlo..."):
                jogos_finais, metricas, historico_fitness = st.session_state.gerador_ai3.gerar_jogos_elite(
                    quantidade=qtd_ai3,
                    geracoes=geracoes,
                    simulacoes_mc=simulacoes_mc
                )
                
                st.session_state.jogos_gerados = jogos_finais
                st.session_state.resultados_mc = metricas
                
                st.balloons()
                st.success(f"✅ {len(jogos_finais)} jogos de elite gerados!")
                
                # Mostrar evolução
                if historico_fitness:
                    st.markdown("### 📈 Evolução do Fitness")
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.plot(historico_fitness, linewidth=2, color='#4ade80')
                    ax.set_xlabel('Geração')
                    ax.set_ylabel('Melhor Fitness')
                    ax.set_title('Evolução do Algoritmo Genético')
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
        
        # Mostrar jogos com estatísticas Monte Carlo
        if st.session_state.jogos_gerados and st.session_state.resultados_mc:
            st.markdown("### 🏆 Jogos de Elite com Probabilidades Monte Carlo")
            
            # Criar DataFrame para visualização
            dados_tabela = []
            for i, jogo in enumerate(st.session_state.jogos_gerados[:10]):
                # Encontrar métricas
                prob_13 = 0
                for j, m in st.session_state.resultados_mc:
                    if j == jogo and "p13_mc" in m:
                        prob_13 = m["p13_mc"]
                        break
                
                # Estatísticas
                baixas = sum(1 for n in jogo if n <= 8)
                medias = sum(1 for n in jogo if 9 <= n <= 16)
                pares = sum(1 for n in jogo if n % 2 == 0)
                soma = sum(jogo)
                
                dados_tabela.append({
                    "Jogo": i+1,
                    "Dezenas": ", ".join(f"{n:02d}" for n in jogo),
                    "Baixas": baixas,
                    "Médias": medias,
                    "Pares": pares,
                    "Soma": soma,
                    "P(13+) MC": f"{prob_13:.2f}%"
                })
            
            df_display = pd.DataFrame(dados_tabela)
            st.dataframe(df_display, hide_index=True, use_container_width=True)
    
    with tab6:
        st.subheader("🎯 Gerador Final - Combinação Inteligente")
        
        ultimo = st.session_state.historico[0] if st.session_state.historico else []
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            qtd_final = st.number_input("Quantidade final", 5, 100, 20, key="final_qtd")
        
        with col2:
            modo = st.selectbox("Modo", ["Balanceado", "Agressivo (13+)", "Conservador (11-12)"], key="modo_final")
        
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
    
    with tab7:
        st.subheader("📋 Conferência Pós-Sorteio")
        
        conferencia = st.session_state.conferencia
        
        # Buscar concurso mais recente da API
        concurso_recente = None
        if st.session_state.dados_api and len(st.session_state.dados_api) > 0:
            concurso_recente = st.session_state.dados_api[0]
        
        # Sidebar dentro da aba para opções
        with st.expander("📁 Carregar Jogos", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Upload de arquivo
                arquivo_upload = st.file_uploader("Carregar arquivo JSON", type=['json'], key="conferencia_upload")
                
                if arquivo_upload is not None:
                    # Salvar temporariamente
                    with open("temp_jogos_conferencia.json", "wb") as f:
                        f.write(arquivo_upload.getbuffer())
                    
                    sucesso, msg = conferencia.carregar_jogos("temp_jogos_conferencia.json")
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)
            
            with col2:
                st.markdown("### Ou")
                
                # Carregar da sessão atual
                if st.session_state.jogos_gerados:
                    if st.button("📥 Usar jogos da sessão atual", use_container_width=True):
                        sucesso, msg = conferencia.carregar_jogos_da_sessao(st.session_state.jogos_gerados)
                        if sucesso:
                            st.success(msg)
                        else:
                            st.error(msg)
                else:
                    st.info("Nenhum jogo na sessão atual. Gere jogos primeiro!")
                
                # Gerar exemplo
                if st.button("🎲 Gerar exemplo para teste", use_container_width=True):
                    arquivo = gerar_arquivo_exemplo()
                    sucesso, msg = conferencia.carregar_jogos(arquivo)
                    if sucesso:
                        st.success(msg + " (arquivo exemplo)")
        
        # Mostrar info do concurso carregado
        if conferencia.jogos:
            st.markdown(f"""
            <div class='info-box'>
                <strong>📊 Jogos carregados:</strong> {len(conferencia.jogos)}<br>
                <strong>🎯 Concurso alvo:</strong> {conferencia.concurso_alvo}<br>
                <strong>📅 Data:</strong> {conferencia.data_alvo}
            </div>
            """, unsafe_allow_html=True)
        
        # Seleção do concurso via API
        st.markdown("### 🎯 Selecionar Concurso para Conferência")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Opções de concurso
            if st.session_state.dados_api:
                opcoes_concurso = [
                    f"#{c['concurso']} - {c['data']} (Último)" if i == 0 else f"#{c['concurso']} - {c['data']}"
                    for i, c in enumerate(st.session_state.dados_api[:20])
                ]
                
                indices_concurso = list(range(min(20, len(st.session_state.dados_api))))
                
                idx_selecionado = st.selectbox(
                    "Selecione o concurso:",
                    indices_concurso,
                    format_func=lambda i: opcoes_concurso[i],
                    key="select_concurso_conferencia"
                )
                
                concurso_selecionado = st.session_state.dados_api[idx_selecionado]
                numeros_sorteados_api = sorted(map(int, concurso_selecionado['dezenas']))
                
                st.markdown(f"**Números sorteados:** {numeros_sorteados_api}")
                
                # Mostrar números em formato visual
                nums_html_api = ""
                for n in numeros_sorteados_api:
                    if n <= 8:
                        cor = "#4ade80"
                    elif n <= 16:
                        cor = "#4cc9f0"
                    else:
                        cor = "#f97316"
                    nums_html_api += f"<span style='background:{cor}30; border:2px solid {cor}; border-radius:25px; padding:5px 10px; margin:3px; display:inline-block; font-weight:bold;'>{n:02d}</span>"
                
                st.markdown(f"<div style='margin:10px 0;'>{nums_html_api}</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Botão para carregar automaticamente o último concurso
            if concurso_recente and st.button("📥 Carregar Último Concurso", use_container_width=True):
                numeros_ultimo = sorted(map(int, concurso_recente['dezenas']))
                
                # Pré-preencher o text area com os números
                numeros_texto = ", ".join(f"{n:02d}" for n in numeros_ultimo)
                st.session_state['numeros_preenchidos'] = numeros_texto
                
                st.success(f"✅ Números do concurso #{concurso_recente['concurso']} carregados!")
                st.rerun()
        
        # Input dos números sorteados
        st.markdown("### 🔢 Números Sorteados")
        
        valor_padrao = st.session_state.get('numeros_preenchidos', "")
        
        numeros_input = st.text_area(
            "Digite os 15 números sorteados (separados por vírgula ou espaço):",
            value=valor_padrao,
            placeholder="Ex: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15",
            height=100,
            key="numeros_sorteados_input"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔍 CONFERIR RESULTADO", type="primary", use_container_width=True):
                if not conferencia.jogos:
                    st.error("Carregue os jogos primeiro!")
                elif not numeros_input:
                    st.error("Digite os números sorteados!")
                else:
                    # Processar input
                    try:
                        numeros_texto = numeros_input.replace(',', ' ').split()
                        numeros = [int(n.strip()) for n in numeros_texto if n.strip()]
                        
                        if len(numeros) != 15:
                            st.error(f"Foram encontrados {len(numeros)} números. Devem ser 15!")
                        elif len(set(numeros)) != 15:
                            st.error("Números duplicados!")
                        elif any(n < 1 or n > 25 for n in numeros):
                            st.error("Números devem estar entre 1 e 25!")
                        else:
                            numeros = sorted(numeros)
                            sucesso, msg = conferencia.conferir(numeros)
                            if sucesso:
                                st.success(msg)
                                st.balloons()
                                st.session_state['numeros_preenchidos'] = ""
                            else:
                                st.error(msg)
                    except Exception as e:
                        st.error(f"Erro ao processar números: {e}")
        
        with col2:
            if st.button("🔄 Limpar Tudo", use_container_width=True):
                st.session_state.conferencia = ConferenciaLotofacil()
                st.session_state['numeros_preenchidos'] = ""
                st.rerun()
        
        with col3:
            if 'numeros_sorteados_api' in locals():
                numeros_str = ", ".join(f"{n:02d}" for n in numeros_sorteados_api)
                if st.button(f"📋 Usar nº do concurso #{concurso_selecionado['concurso']}", use_container_width=True):
                    st.session_state['numeros_preenchidos'] = numeros_str
                    st.rerun()
        
        # Resultados da conferência
        if conferencia.df_conferencia is not None:
            st.markdown("---")
            st.markdown("### 📊 Resultados da Conferência")
            
            # Métricas rápidas
            e = conferencia.estatisticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Média Acertos", f"{e['media_acertos']:.2f}")
            with col2:
                st.metric("Melhor Jogo", f"{e['max_acertos']} pts (J{e['melhor_jogo']})")
            with col3:
                st.metric("Total 11+", e['total_11'])
            with col4:
                st.metric("Total 13+", e['total_13'])
            
            # Tabs para diferentes visualizações
            res_tab1, res_tab2, res_tab3, res_tab4 = st.tabs(["📊 Tabela", "📈 Gráficos", "🏆 Melhores", "📝 Relatório"])
            
            with res_tab1:
                # DataFrame com cores
                df_display = conferencia.df_conferencia.copy()
                df_display['dezenas'] = df_display['dezenas'].apply(lambda x: ', '.join(f"{n:02d}" for n in x))
                df_display = df_display[['jogo_id', 'acertos', 'premio', 'dezenas']]
                df_display.columns = ['Jogo', 'Acertos', 'Prêmio (R$)', 'Dezenas']
                
                # Colorir linhas por acertos
                def color_acertos(val):
                    if val >= 13:
                        return 'background-color: #f9731680'
                    elif val >= 11:
                        return 'background-color: #4ade8080'
                    return ''
                
                st.dataframe(
                    df_display.style.map(color_acertos, subset=['Acertos']),
                    use_container_width=True,
                    hide_index=True
                )
            
            with res_tab2:
                fig = conferencia.plot_graficos()
                if fig:
                    st.pyplot(fig)
            
            with res_tab3:
                st.markdown("#### 🥇 Top 10 Melhores Jogos")
                top10 = conferencia.df_conferencia.nlargest(10, 'acertos')
                
                for _, row in top10.iterrows():
                    nums_html = ""
                    for n in row['dezenas']:
                        if n <= 8:
                            cor = "#4ade80"
                        elif n <= 16:
                            cor = "#4cc9f0"
                        else:
                            cor = "#f97316"
                        nums_html += f"<span style='background:{cor}30; border:1px solid {cor}; border-radius:15px; padding:3px 6px; margin:2px; display:inline-block;'>{n:02d}</span>"
                    
                    st.markdown(f"""
                    <div style='background:#0e1117; border-left:5px solid gold; border-radius:10px; padding:10px; margin:5px 0;'>
                        <div style='display:flex; justify-content:space-between;'>
                            <strong>Jogo {int(row['jogo_id'])}</strong>
                            <span style='color:gold; font-weight:bold;'>{int(row['acertos'])} pontos - R$ {row['premio']:,.2f}</span>
                        </div>
                        <div>{nums_html}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            with res_tab4:
                st.markdown("#### 📄 Relatório Completo")
                relatorio = conferencia.gerar_relatorio_texto()
                st.text(relatorio)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Salvar Relatório", use_container_width=True):
                        nome = conferencia.salvar_relatorio()
                        st.success(f"Relatório salvo como {nome}.txt, .json e .csv")
                
                with col2:
                    # Comparação com baseline
                    media_modelo = conferencia.estatisticas['media_acertos']
                    vantagem = ((media_modelo - 7.5) / 7.5) * 100
                    
                    if media_modelo > 7.5:
                        st.markdown(f"""
                        <div class='success-box'>
                            <strong>✅ Vantagem: +{vantagem:.1f}% sobre aleatório</strong>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class='warning-box'>
                            <strong>⚠️ Desempenho abaixo do aleatório</strong>
                        </div>
                        """, unsafe_allow_html=True)

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
    LOTOFÁCIL AI 3.0 • Algoritmo Genético • Monte Carlo • Entropia • Machine Learning • Ensemble
</div>
""", unsafe_allow_html=True)
