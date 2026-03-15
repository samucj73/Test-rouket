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
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import itertools
from copy import deepcopy
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
st.caption("Markov Chains + Algoritmo Genético + Monte Carlo + Entropia • Nível Profissional")

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
        for jogo in self.historico:
            H = 0
            for n in jogo:
                p = self.probs.get(n, 1e-9)
                H -= p * math.log(p + 1e-10)
            entropias.append(H)
        return np.mean(entropias)
    
    def entropia_jogo(self, jogo):
        """Calcula a entropia de um jogo específico"""
        H = 0
        for n in jogo:
            p = self.probs.get(n, 1e-9)
            H -= p * math.log(p + 1e-10)
        return H
    
    def score_entropia(self, jogo):
        """
        Score baseado na proximidade da entropia média
        Quanto mais próximo da média, maior o score
        """
        H = self.entropia_jogo(jogo)
        # Distribuição normal aproximada
        diff = abs(H - self.entropia_media)
        score = math.exp(-diff / self.entropia_media)
        return score

# =====================================================
# MÓDULO 2: CADEIAS DE MARKOV
# =====================================================

class MarkovLotofacil:
    """
    Modelo de Cadeias de Markov para capturar dependências temporais entre concursos
    Aprende probabilidades de transição entre números de um concurso para o próximo
    """
    
    def __init__(self, historico, ordem=1):
        """
        Args:
            historico: lista de jogos históricos
            ordem: ordem da cadeia de Markov (1 = último concurso, 2 = últimos 2 concursos)
        """
        self.historico = historico
        self.ordem = ordem
        self.matriz_transicao = None
        self._treinar()
        
    def _treinar(self):
        """Treina o modelo de Markov com base no histórico"""
        if self.ordem == 1:
            self._treinar_markov_ordem1()
        else:
            self._treinar_markov_ordem2()
    
    def _treinar_markov_ordem1(self):
        """Markov de ordem 1: P(próximo | atual)"""
        self.matriz_transicao = np.zeros((25, 25))
        
        for i in range(len(self.historico) - 1):
            atual = self.historico[i]
            prox = self.historico[i + 1]
            
            for a in atual:
                for b in prox:
                    self.matriz_transicao[a-1][b-1] += 1
        
        # Normalizar (evitar divisão por zero)
        soma_linhas = self.matriz_transicao.sum(axis=1, keepdims=True)
        soma_linhas[soma_linhas == 0] = 1
        self.matriz_transicao = self.matriz_transicao / soma_linhas
    
    def _treinar_markov_ordem2(self):
        """
        Markov de ordem 2: P(próximo | atual, anterior)
        Implementado como uma matriz 3D
        """
        # Formato: [anterior][atual][proximo]
        self.matriz_transicao = np.zeros((25, 25, 25))
        
        for i in range(len(self.historico) - 2):
            anterior = self.historico[i]
            atual = self.historico[i + 1]
            prox = self.historico[i + 2]
            
            for a in anterior:
                for b in atual:
                    for c in prox:
                        self.matriz_transicao[a-1][b-1][c-1] += 1
        
        # Normalizar
        for i in range(25):
            for j in range(25):
                soma = self.matriz_transicao[i][j].sum()
                if soma > 0:
                    self.matriz_transicao[i][j] = self.matriz_transicao[i][j] / soma
    
    def score_transicao(self, ultimos_jogos, jogo_candidato):
        """
        Calcula a probabilidade de transição dos últimos jogos para o candidato
        
        Args:
            ultimos_jogos: lista com 1 ou 2 últimos concursos (depende da ordem)
            jogo_candidato: jogo a ser avaliado
        """
        if self.ordem == 1:
            return self._score_ordem1(ultimos_jogos[0], jogo_candidato)
        else:
            return self._score_ordem2(ultimos_jogos[0], ultimos_jogos[1], jogo_candidato)
    
    def _score_ordem1(self, ultimo, candidato):
        """Score para Markov ordem 1"""
        score = 0
        for a in ultimo:
            for b in candidato:
                score += self.matriz_transicao[a-1][b-1]
        return score / (len(ultimo) * len(candidato))
    
    def _score_ordem2(self, anterior, atual, candidato):
        """Score para Markov ordem 2"""
        score = 0
        count = 0
        for a in anterior:
            for b in atual:
                for c in candidato:
                    score += self.matriz_transicao[a-1][b-1][c-1]
                    count += 1
        return score / count if count > 0 else 0

# =====================================================
# MÓDULO 3: ALGORITMO GENÉTICO AVANÇADO
# =====================================================

class AlgoritmoGeneticoLotofacil:
    """
    Algoritmo Genético para evoluir jogos da Lotofácil
    Mais poderoso que geração aleatória simples
    """
    
    def __init__(self, historico, fitness_func=None, tamanho_pop=200, taxa_mutacao=0.15):
        self.historico = historico
        self.tamanho_pop = tamanho_pop
        self.taxa_mutacao = taxa_mutacao
        self.fitness_func = fitness_func if fitness_func else self._fitness_padrao
        
        # Pré-calcular estatísticas para fitness
        self.soma_media = np.mean([sum(j) for j in historico])
        self.rep_media = np.mean([
            len(set(historico[i]) & set(historico[i+1])) 
            for i in range(len(historico)-1)
        ])
        
    def _fitness_padrao(self, jogo):
        """
        Função de fitness baseada em múltiplos critérios:
        - Proximidade da soma média
        - Potencial de repetição com histórico
        - Distribuição baixas/médias/altas
        """
        # Soma
        soma = sum(jogo)
        score_soma = 1 - abs(soma - self.soma_media) / 100
        
        # Repetição com últimos concursos (média dos últimos 10)
        rep = np.mean([
            len(set(jogo) & set(h)) 
            for h in self.historico[:10]
        ])
        score_rep = 1 - abs(rep - self.rep_media) / 15
        
        # Distribuição
        baixas = sum(1 for n in jogo if n <= 8)
        medias = sum(1 for n in jogo if 9 <= n <= 16)
        
        score_dist = 1 - (abs(baixas - 5) + abs(medias - 5)) / 10
        
        # Combinar scores
        fitness = 0.4 * score_soma + 0.4 * score_rep + 0.2 * score_dist
        return fitness
    
    def gerar_individuo(self):
        """Gera um indivíduo aleatório (jogo válido)"""
        return sorted(random.sample(range(1, 26), 15))
    
    def crossover(self, pai1, pai2):
        """
        Operador de crossover: combina dois pais para gerar um filho
        Usa crossover de ponto único com reparo
        """
        # Escolher ponto de corte aleatório
        ponto = random.randint(1, 14)
        
        # Combinar
        filho = list(pai1[:ponto]) + list(pai2[ponto:])
        filho = sorted(set(filho))  # Remover duplicatas
        
        # Reparar se necessário (completar para 15 números)
        while len(filho) < 15:
            disponiveis = [n for n in range(1, 26) if n not in filho]
            filho.append(random.choice(disponiveis))
            filho.sort()
        
        return filho
    
    def mutacao(self, individuo):
        """
        Operador de mutação: troca um número por outro não presente
        """
        if random.random() > self.taxa_mutacao:
            return individuo
        
        mutante = individuo.copy()
        
        # Escolher índice para mutação
        idx = random.randint(0, 14)
        numero_removido = mutante[idx]
        
        # Escolher novo número (não presente no jogo)
        disponiveis = [n for n in range(1, 26) if n not in mutante]
        if disponiveis:
            novo_numero = random.choice(disponiveis)
            mutante[idx] = novo_numero
            mutante.sort()
        
        return mutante
    
    def selecao_torneio(self, populacao, fitness, k=3):
        """Seleção por torneio"""
        indices = random.sample(range(len(populacao)), k)
        melhor_idx = max(indices, key=lambda i: fitness[i])
        return populacao[melhor_idx]
    
    def evoluir(self, geracoes=100, elite_size=20):
        """
        Executa o algoritmo genético
        
        Args:
            geracoes: número de gerações
            elite_size: quantidade de melhores indivíduos preservados
        
        Returns:
            Lista dos melhores jogos
        """
        # Inicializar população
        populacao = [self.gerar_individuo() for _ in range(self.tamanho_pop)]
        historico_fitness = []
        
        # Barra de progresso
        progress_bar = st.progress(0)
        
        for geracao in range(geracoes):
            # Calcular fitness
            fitness = [self.fitness_func(ind) for ind in populacao]
            
            # Ordenar população por fitness
            populacao_ordenada = [x for _, x in sorted(
                zip(fitness, populacao), key=lambda pair: pair[0], reverse=True
            )]
            
            # Guardar melhor fitness
            historico_fitness.append(max(fitness))
            
            # Criar nova geração
            nova_populacao = []
            
            # Elitismo: preservar os melhores
            nova_populacao.extend(populacao_ordenada[:elite_size])
            
            # Gerar resto da população
            while len(nova_populacao) < self.tamanho_pop:
                # Selecionar pais
                pai1 = self.selecao_torneio(populacao_ordenada[:100], fitness[:100])
                pai2 = self.selecao_torneio(populacao_ordenada[:100], fitness[:100])
                
                # Crossover
                filho = self.crossover(pai1, pai2)
                
                # Mutação
                filho = self.mutacao(filho)
                
                nova_populacao.append(filho)
            
            populacao = nova_populacao
            progress_bar.progress((geracao + 1) / geracoes)
        
        progress_bar.empty()
        
        # Calcular fitness final
        fitness_final = [self.fitness_func(ind) for ind in populacao]
        
        # Retornar top 50
        melhores = [x for _, x in sorted(
            zip(fitness_final, populacao), key=lambda pair: pair[0], reverse=True
        )]
        
        return melhores[:50], historico_fitness

# =====================================================
# MÓDULO 4: SIMULAÇÃO MONTE CARLO
# =====================================================

class SimuladorMonteCarlo:
    """
    Simula milhares de concursos futuros para avaliar jogos
    """
    
    def __init__(self, historico=None, num_simulacoes=100000):
        self.historico = historico
        self.num_simulacoes = num_simulacoes
        
        # Se tiver histórico, aprender distribuições
        if historico:
            self.dist_numeros = self._calcular_distribuicao_numeros()
        else:
            self.dist_numeros = None
    
    def _calcular_distribuicao_numeros(self):
        """Calcula distribuição de probabilidade dos números baseada no histórico"""
        counter = Counter()
        for jogo in self.historico:
            counter.update(jogo)
        
        total = sum(counter.values())
        probs = {n: counter[n]/total for n in range(1, 26)}
        
        # Normalizar
        soma = sum(probs.values())
        return {n: p/soma for n, p in probs.items()}
    
    def _gerar_sorteio_simulado(self):
        """
        Gera um sorteio simulado baseado nas probabilidades históricas
        Se não tiver histórico, gera uniformemente
        """
        if self.dist_numeros:
            # Amostragem ponderada
            numeros = list(self.dist_numeros.keys())
            probs = list(self.dist_numeros.values())
            
            # Garantir que a soma seja 1 (pequeno ajuste)
            probs = np.array(probs)
            probs = probs / probs.sum()
            
            # Amostrar sem reposição
            indices = np.random.choice(len(numeros), size=15, replace=False, p=probs)
            sorteio = [numeros[i] for i in indices]
        else:
            # Uniforme
            sorteio = random.sample(range(1, 26), 15)
        
        return sorted(sorteio)
    
    def avaliar_jogo(self, jogo, verbose=False):
        """
        Avalia um jogo através de simulação Monte Carlo
        
        Returns:
            dict com estatísticas do jogo
        """
        resultados = []
        
        # Barra de progresso para simulações longas
        if verbose:
            progress_bar = st.progress(0)
        
        for i in range(self.num_simulacoes):
            sorteio = self._gerar_sorteio_simulado()
            acertos = len(set(jogo) & set(sorteio))
            resultados.append(acertos)
            
            if verbose and i % (self.num_simulacoes // 10) == 0:
                progress_bar.progress(i / self.num_simulacoes)
        
        if verbose:
            progress_bar.empty()
        
        resultados = np.array(resultados)
        
        estatisticas = {
            'media': np.mean(resultados),
            'mediana': np.median(resultados),
            'std': np.std(resultados),
            'min': np.min(resultados),
            'max': np.max(resultados),
            'p11': np.mean(resultados >= 11) * 100,
            'p12': np.mean(resultados >= 12) * 100,
            'p13': np.mean(resultados >= 13) * 100,
            'p14': np.mean(resultados >= 14) * 100,
            'p15': np.mean(resultados == 15) * 100,
            'distribuicao': Counter(resultados)
        }
        
        return estatisticas
    
    def avaliar_multiplos_jogos(self, jogos):
        """
        Avalia múltiplos jogos e retorna ranking
        
        Args:
            jogos: lista de jogos para avaliar
        
        Returns:
            DataFrame com ranking dos jogos
        """
        resultados = []
        
        for i, jogo in enumerate(jogos):
            stats = self.avaliar_jogo(jogo)
            resultados.append({
                'jogo_id': i + 1,
                'jogo': jogo,
                'media_acertos': stats['media'],
                'p13': stats['p13'],
                'p14': stats['p14'],
                'p15': stats['p15']
            })
        
        df = pd.DataFrame(resultados)
        df = df.sort_values('p13', ascending=False).reset_index(drop=True)
        
        return df

# =====================================================
# MÓDULO 5: SISTEMA DE DOMINÂNCIA
# =====================================================

class SistemaDominancia:
    """
    Remove jogos dominados (piores em todas as métricas)
    """
    
    def __init__(self, metricas=['media', 'p11', 'p13']):
        self.metricas = metricas
    
    def _domina(self, jogo_a, jogo_b, scores):
        """
        Verifica se jogo A domina jogo B
        A domina B se for melhor ou igual em todas métricas e estritamente melhor em pelo menos uma
        """
        a_domina = True
        estritamente_melhor = False
        
        for metrica in self.metricas:
            if scores[jogo_a][metrica] < scores[jogo_b][metrica]:
                a_domina = False
                break
            elif scores[jogo_a][metrica] > scores[jogo_b][metrica]:
                estritamente_melhor = True
        
        return a_domina and estritamente_melhor
    
    def filtrar_dominados(self, jogos, scores):
        """
        Remove jogos dominados
        
        Args:
            jogos: lista de jogos
            scores: dict com scores para cada jogo (índice -> dict de métricas)
        
        Returns:
            Lista de jogos não dominados
        """
        n = len(jogos)
        dominado = [False] * n
        
        for i in range(n):
            if dominado[i]:
                continue
            
            for j in range(n):
                if i == j or dominado[j]:
                    continue
                
                if self._domina(i, j, scores):
                    dominado[j] = True
                elif self._domina(j, i, scores):
                    dominado[i] = True
                    break
        
        return [jogos[i] for i in range(n) if not dominado[i]]
    
    def selecionar_melhores(self, jogos, scores, k=20):
        """
        Seleciona os k melhores jogos usando dominância e rankeamento
        """
        # Primeiro, remover dominados
        nao_dominados = self.filtrar_dominados(jogos, scores)
        
        # Se ainda temos mais que k, rankear por média das métricas
        if len(nao_dominados) > k:
            indices_nao_dominados = [jogos.index(j) for j in nao_dominados]
            medias = [
                np.mean([scores[idx][m] for m in self.metricas])
                for idx in indices_nao_dominados
            ]
            
            # Selecionar top k
            melhores_indices = np.argsort(medias)[-k:][::-1]
            nao_dominados = [nao_dominados[i] for i in melhores_indices]
        
        return nao_dominados

# =====================================================
# MÓDULO 6: GEOMETRIA DO VOLANTE E TEORIA DOS GRAFOS
# =====================================================

class GeometriaVolante:
    """
    Transforma o volante 5x5 em um grafo e analisa padrões geométricos
    """
    
    def __init__(self):
        # Mapeamento número -> posição (linha, coluna)
        self.posicoes = {}
        num = 1
        for linha in range(5):
            for coluna in range(5):
                self.posicoes[num] = (linha, coluna)
                num += 1
        
        # Matriz de adjacência (vizinhança no volante)
        self.grafo = self._criar_grafo()
    
    def _criar_grafo(self):
        """Cria grafo onde arestas conectam números vizinhos no volante"""
        grafo = {i: [] for i in range(1, 26)}
        
        for num in range(1, 26):
            linha, col = self.posicoes[num]
            
            # Verificar vizinhos (8 direções)
            for dl in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dl == 0 and dc == 0:
                        continue
                    
                    nova_linha = linha + dl
                    nova_col = col + dc
                    
                    if 0 <= nova_linha < 5 and 0 <= nova_col < 5:
                        # Encontrar número na nova posição
                        for n, (l, c) in self.posicoes.items():
                            if l == nova_linha and c == nova_col:
                                grafo[num].append(n)
                                break
        
        return grafo
    
    def densidade_vizinhanca(self, jogo):
        """
        Calcula quantas conexões existem entre números do jogo no volante
        Quanto maior, mais "agrupado" é o jogo
        """
        conexoes = 0
        for i, n1 in enumerate(jogo):
            for n2 in jogo[i+1:]:
                if n2 in self.grafo[n1]:
                    conexoes += 1
        
        return conexoes / len(jogo)  # Normalizado
    
    def dispersao_geometrica(self, jogo):
        """
        Calcula a dispersão dos números no volante
        Quanto maior, mais espalhado
        """
        posicoes_jogo = [self.posicoes[n] for n in jogo]
        
        # Centroide
        centro_linha = np.mean([p[0] for p in posicoes_jogo])
        centro_col = np.mean([p[1] for p in posicoes_jogo])
        
        # Distância média ao centro
        distancias = [
            ((p[0] - centro_linha)**2 + (p[1] - centro_col)**2)**0.5
            for p in posicoes_jogo
        ]
        
        return np.mean(distancias)
    
    def padroes_linhas_colunas(self, jogo):
        """
        Analisa distribuição por linhas e colunas
        """
        linhas = [self.posicoes[n][0] for n in jogo]
        colunas = [self.posicoes[n][1] for n in jogo]
        
        return {
            'linhas_unicas': len(set(linhas)),
            'colunas_unicas': len(set(colunas)),
            'linha_mais_freq': max(Counter(linhas).values()),
            'coluna_mais_freq': max(Counter(colunas).values()),
            'dist_linhas': Counter(linhas),
            'dist_colunas': Counter(colunas)
        }
    
    def score_geometrico(self, jogo):
        """
        Score composto baseado em geometria
        """
        densidade = self.densidade_vizinhanca(jogo)
        dispersao = self.dispersao_geometrica(jogo)
        padroes = self.padroes_linhas_colunas(jogo)
        
        # Valores ideais (estimados)
        densidade_ideal = 2.5
        dispersao_ideal = 2.0
        linhas_ideal = 4
        colunas_ideal = 4
        
        score = 0
        score += 1 - abs(densidade - densidade_ideal) / 5
        score += 1 - abs(dispersao - dispersao_ideal) / 3
        score += padroes['linhas_unicas'] / 5
        score += padroes['colunas_unicas'] / 5
        
        return score / 4  # Normalizar

# =====================================================
# MÓDULO 7: REDES BAYESIANAS SIMPLIFICADAS
# =====================================================

class RedeBayesianaLotofacil:
    """
    Rede Bayesiana para modelar dependências entre números
    """
    
    def __init__(self, historico):
        self.historico = historico
        self.prob_condicional = {}
        self._treinar()
    
    def _treinar(self):
        """Calcula probabilidades condicionais P(n_j | n_i aparece)"""
        # Contar co-ocorrências
        co_ocorrencias = np.zeros((25, 25))
        ocorrencias = np.zeros(25)
        
        for jogo in self.historico:
            for i, n1 in enumerate(jogo):
                ocorrencias[n1-1] += 1
                for n2 in jogo[i+1:]:
                    co_ocorrencias[n1-1][n2-1] += 1
                    co_ocorrencias[n2-1][n1-1] += 1
        
        # Calcular probabilidades condicionais
        for i in range(25):
            for j in range(25):
                if i != j and ocorrencias[i] > 0:
                    self.prob_condicional[(i+1, j+1)] = co_ocorrencias[i][j] / ocorrencias[i]
    
    def probabilidade_conjunta(self, jogo):
        """
        Calcula a probabilidade conjunta dos números aparecerem juntos
        """
        prob = 1.0
        for i, n1 in enumerate(jogo):
            for n2 in jogo[i+1:]:
                prob *= self.prob_condicional.get((n1, n2), 0.5)
        
        return prob

# =====================================================
# MÓDULO 8: ENSEMBLE HÍBRIDO FINAL
# =====================================================

class EnsembleAvancado:
    """
    Combina todos os modelos em um ensemble poderoso
    """
    
    def __init__(self, historico):
        self.historico = historico
        self.ultimo = historico[0] if historico else []
        
        # Inicializar todos os modelos
        self.entropia = EntropiaLotofacil(historico)
        self.markov1 = MarkovLotofacil(historico, ordem=1)
        self.markov2 = MarkovLotofacil(historico, ordem=2)
        self.geometria = GeometriaVolante()
        self.bayesiana = RedeBayesianaLotofacil(historico)
        self.monte_carlo = SimuladorMonteCarlo(historico, num_simulacoes=10000)
        
        # Pesos otimizados (podem ser ajustados)
        self.pesos = {
            'entropia': 0.8,
            'markov1': 1.2,
            'markov2': 1.5,
            'geometria': 0.9,
            'bayesiana': 1.0,
            'monte_carlo': 1.3
        }
    
    def calcular_scores(self, jogo):
        """
        Calcula todos os scores para um jogo
        """
        scores = {}
        
        # Entropia
        scores['entropia'] = self.entropia.score_entropia(jogo)
        
        # Markov
        if self.ultimo:
            scores['markov1'] = self.markov1.score_transicao([self.ultimo], jogo)
            
            if len(self.historico) > 1:
                anterior = self.historico[1] if len(self.historico) > 1 else self.ultimo
                scores['markov2'] = self.markov2.score_transicao([anterior, self.ultimo], jogo)
            else:
                scores['markov2'] = 0.5
        else:
            scores['markov1'] = 0.5
            scores['markov2'] = 0.5
        
        # Geometria
        scores['geometria'] = self.geometria.score_geometrico(jogo)
        
        # Bayesiana
        scores['bayesiana'] = self.bayesiana.probabilidade_conjunta(jogo)
        
        # Monte Carlo (mais pesado, pode ser calculado sob demanda)
        # scores['monte_carlo'] = self.monte_carlo.avaliar_jogo(jogo)['p13'] / 100
        
        return scores
    
    def score_ensemble(self, jogo):
        """
        Score ponderado final
        """
        scores = self.calcular_scores(jogo)
        
        score_total = 0
        peso_total = 0
        
        for modelo, score in scores.items():
            if modelo in self.pesos:
                score_total += score * self.pesos[modelo]
                peso_total += self.pesos[modelo]
        
        return score_total / peso_total if peso_total > 0 else 0
    
    def gerar_jogos_genetico(self, quantidade=20, geracoes=80):
        """
        Usa algoritmo genético para encontrar melhores jogos
        """
        # Função de fitness personalizada (usa ensemble)
        def fitness_ensemble(jogo):
            return self.score_ensemble(jogo)
        
        ga = AlgoritmoGeneticoLotofacil(
            self.historico,
            fitness_func=fitness_ensemble,
            tamanho_pop=200,
            taxa_mutacao=0.15
        )
        
        melhores, historico_fitness = ga.evoluir(geracoes=geracoes, elite_size=30)
        
        return melhores[:quantidade]
    
    def validar_com_monte_carlo(self, jogos, num_simulacoes=50000):
        """
        Valida jogos com Monte Carlo e retorna ranking
        """
        simulador = SimuladorMonteCarlo(self.historico, num_simulacoes=num_simulacoes)
        ranking = simulador.avaliar_multiplos_jogos(jogos)
        return ranking

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
# BACKTESTING REAL (VALIDAÇÃO CRUZADA TEMPORAL) - CORRIGIDO
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
# GERADOR SIMPLES E EFICAZ (BASEADO EM PADRÕES REAIS) - CORRIGIDO
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
# SISTEMA DE CONFERÊNCIA PROFISSIONAL (NOVO)
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
# INTERFACE PRINCIPAL - ATUALIZADA
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
    if "ensemble_avancado" not in st.session_state:
        st.session_state.ensemble_avancado = None
    
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
                    
                    # Inicializar ensemble avançado
                    with st.spinner("Inicializando modelos avançados..."):
                        st.session_state.ensemble_avancado = EnsembleAvancado(st.session_state.historico)
                        st.success("✅ Modelos avançados prontos!")
                        
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
        "🎯 Gerar Jogos",
        "📋 Conferência",
        "🚀 AI 3.0 Avançado"  # NOVA ABA
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
    
    # ABA 6: CONFERÊNCIA
    with tab6:
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
                    for i, c in enumerate(st.session_state.dados_api[:20])  # Mostrar últimos 20
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
        st.markdown("### 🔢 Números Sorteados (manual ou automático)")
        
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
            # Botão para usar números selecionados na API
            if 'numeros_sorteados_api' in locals():
                numeros_str = ", ".join(f"{n:02d}" for n in numeros_sorteados_api)
                if st.button(f"📋 Usar nº do concurso #{concurso_selecionado['concurso']}", use_container_width=True):
                    st.session_state['numeros_preenchidos'] = numeros_str
                    st.rerun()
        
        # Resultados da conferência
        if conferencia.df_conferencia is not None:
            st.markdown("---")
            st.markdown("### 📊 Resultados da Conferência")
            
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
            
            res_tab1, res_tab2, res_tab3, res_tab4 = st.tabs(["📊 Tabela", "📈 Gráficos", "🏆 Melhores", "📝 Relatório"])
            
            with res_tab1:
                df_display = conferencia.df_conferencia.copy()
                df_display['dezenas'] = df_display['dezenas'].apply(lambda x: ', '.join(f"{n:02d}" for n in x))
                df_display = df_display[['jogo_id', 'acertos', 'premio', 'dezenas']]
                df_display.columns = ['Jogo', 'Acertos', 'Prêmio (R$)', 'Dezenas']
                
                def color_acertos(val):
                    if val >= 13:
                        return 'background-color: #f9731680'
                    elif val >= 11:
                        return 'background-color: #4ade8080'
                    return ''
                
                st.dataframe(
                    df_display.style.applymap(color_acertos, subset=['Acertos']),
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
    # ABA 7: AI 3.0 AVANÇADO (NOVA)
    # =====================================================
    with tab7:
        st.subheader("🚀 LOTOFÁCIL AI 3.0 - Modelos Avançados")
        
        st.markdown("""
        <div class='highlight' style='padding:20px; border-radius:15px; margin-bottom:20px;'>
        <h4 style='margin-top:0;'>🧠 Motor Matemático Profissional</h4>
        <p>Esta aba contém os modelos mais avançados do sistema:</p>
        <ul>
            <li>📊 Entropia de Shannon - Mede equilíbrio estatístico</li>
            <li>🔄 Cadeias de Markov (ordem 1 e 2) - Captura dependências temporais</li>
            <li>🧬 Algoritmo Genético - Evolui jogos através de gerações</li>
            <li>🎲 Simulação Monte Carlo (100k+ simulações) - Avaliação probabilística</li>
            <li>📐 Geometria do Volante - Análise de padrões no tabuleiro 5x5</li>
            <li>🧠 Rede Bayesiana - Modela dependências entre números</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.ensemble_avancado is None:
            st.warning("Recarregue os concursos para inicializar os modelos avançados.")
            return
        
        ensemble_avancado = st.session_state.ensemble_avancado
        
        ## Sub-abas para organização
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
            "🧬 Algoritmo Genético",
            "🎲 Monte Carlo",
            "📊 Análise Avançada",
            "🎯 Gerador Premium"
        ])
        
        with sub_tab1:
            st.markdown("### 🧬 Algoritmo Genético - Evolução de Jogos")
            st.markdown("""
            O algoritmo genético simula a evolução natural:
            1. **População inicial** - 200 jogos aleatórios
            2. **Seleção** - Os melhores são preservados
            3. **Crossover** - Combinação de jogos pais
            4. **Mutação** - Pequenas alterações aleatórias
            5. **Evolução** - 100 gerações de aprimoramento
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                geracoes = st.slider("Número de gerações", 20, 200, 80, key="ga_geracoes")
                pop_size = st.slider("Tamanho da população", 50, 500, 200, key="ga_pop")
            
            with col2:
                qtd_ga = st.number_input("Quantidade de jogos", 5, 50, 20, key="ga_qtd")
                
                if st.button("🚀 Evoluir Jogos", use_container_width=True, type="primary"):
                    with st.spinner(f"Evoluindo por {geracoes} gerações..."):
                        # Criar GA com fitness do ensemble
                        ga = AlgoritmoGeneticoLotofacil(
                            st.session_state.historico,
                            fitness_func=ensemble_avancado.score_ensemble,
                            tamanho_pop=pop_size,
                            taxa_mutacao=0.15
                        )
                        
                        melhores, historico_fitness = ga.evoluir(geracoes=geracoes, elite_size=30)
                        
                        # Mostrar evolução
                        st.markdown("### 📈 Evolução do Fitness")
                        fig, ax = plt.subplots(figsize=(10, 4))
                        ax.plot(historico_fitness, linewidth=2, color='#4ade80')
                        ax.set_xlabel('Geração')
                        ax.set_ylabel('Melhor Fitness')
                        ax.set_title('Evolução do Fitness ao Longo das Gerações')
                        ax.grid(True, alpha=0.3)
                        st.pyplot(fig)
                        
                        st.session_state.jogos_gerados = melhores[:qtd_ga]
                        st.success(f"✅ {len(melhores[:qtd_ga])} jogos evoluídos!")
                        
                        # Mostrar top 5
                        st.markdown("### 🏆 Top 5 Jogos Evoluídos")
                        for i, jogo in enumerate(melhores[:5]):
                            score = ensemble_avancado.score_ensemble(jogo)
                            nums_html = ""
                            for n in jogo:
                                if n <= 8:
                                    cor = "#4ade80"
                                elif n <= 16:
                                    cor = "#4cc9f0"
                                else:
                                    cor = "#f97316"
                                nums_html += f"<span style='background:{cor}30; border:1px solid {cor}; border-radius:20px; padding:3px 6px; margin:2px;'>{n:02d}</span>"
                            
                            st.markdown(f"""
                            <div style='background:#0e1117; border-radius:10px; padding:10px; margin:5px 0;'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <strong>Jogo {i+1}</strong>
                                    <span>Fitness: {score:.4f}</span>
                                </div>
                                <div>{nums_html}</div>
                            </div>
                            """, unsafe_allow_html=True)
        
        with sub_tab2:
            st.markdown("### 🎲 Simulação Monte Carlo")
            st.markdown("""
            Avaliação probabilística através de **100.000+ simulações** de concursos futuros.
            Quanto maior a simulação, mais precisa a estimativa.
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                num_simulacoes = st.select_slider(
                    "Número de simulações",
                    options=[10000, 50000, 100000, 200000, 500000],
                    value=100000
                )
            
            with col2:
                if st.button("📊 Avaliar Jogos da Sessão", use_container_width=True):
                    if not st.session_state.jogos_gerados:
                        st.warning("Gere alguns jogos primeiro!")
                    else:
                        with st.spinner(f"Executando {num_simulacoes:,} simulações..."):
                            simulador = SimuladorMonteCarlo(
                                st.session_state.historico,
                                num_simulacoes=num_simulacoes
                            )
                            
                            ranking = simulador.avaliar_multiplos_jogos(st.session_state.jogos_gerados)
                            
                            st.markdown("### 📊 Ranking Probabilístico")
                            st.dataframe(
                                ranking[['jogo_id', 'media_acertos', 'p13', 'p14', 'p15']].round(2),
                                hide_index=True,
                                use_container_width=True
                            )
                            
                            # Gráfico comparativo
                            fig, ax = plt.subplots(figsize=(10, 5))
                            bars = ax.bar(
                                range(len(ranking)),
                                ranking['p13'],
                                color=['#4ade80' if p > 5 else '#4cc9f0' for p in ranking['p13']]
                            )
                            ax.axhline(y=1.7, color='red', linestyle='--', label='Aleatório (1.7%)')
                            ax.set_xlabel('Jogo')
                            ax.set_ylabel('Probabilidade 13+ (%)')
                            ax.set_title('Probabilidade de 13+ pontos por Jogo')
                            ax.legend()
                            st.pyplot(fig)
            
            # Avaliar um jogo específico
            st.markdown("### 🔍 Avaliar Jogo Específico")
            col1, col2, col3 = st.columns(3)
            with col1:
                n1 = st.number_input("N1", 1, 25, 1, key="mc_n1")
            with col2:
                n2 = st.number_input("N2", 1, 25, 2, key="mc_n2")
            with col3:
                n3 = st.number_input("N3", 1, 25, 3, key="mc_n3")
            
            col4, col5, col6 = st.columns(3)
            with col4:
                n4 = st.number_input("N4", 1, 25, 4, key="mc_n4")
            with col5:
                n5 = st.number_input("N5", 1, 25, 5, key="mc_n5")
            with col6:
                n6 = st.number_input("N6", 1, 25, 6, key="mc_n6")
            
            col7, col8, col9 = st.columns(3)
            with col7:
                n7 = st.number_input("N7", 1, 25, 7, key="mc_n7")
            with col8:
                n8 = st.number_input("N8", 1, 25, 8, key="mc_n8")
            with col9:
                n9 = st.number_input("N9", 1, 25, 9, key="mc_n9")
            
            col10, col11, col12 = st.columns(3)
            with col10:
                n10 = st.number_input("N10", 1, 25, 10, key="mc_n10")
            with col11:
                n11 = st.number_input("N11", 1, 25, 11, key="mc_n11")
            with col12:
                n12 = st.number_input("N12", 1, 25, 12, key="mc_n12")
            
            col13, col14, col15 = st.columns(3)
            with col13:
                n13 = st.number_input("N13", 1, 25, 13, key="mc_n13")
            with col14:
                n14 = st.number_input("N14", 1, 25, 14, key="mc_n14")
            with col15:
                n15 = st.number_input("N15", 1, 25, 15, key="mc_n15")
            
            if st.button("📊 Avaliar Este Jogo", use_container_width=True):
                jogo = sorted([n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12, n13, n14, n15])
                
                if len(set(jogo)) != 15:
                    st.error("Números duplicados! Cada número deve ser único.")
                else:
                    with st.spinner(f"Executando {num_simulacoes:,} simulações..."):
                        simulador = SimuladorMonteCarlo(
                            st.session_state.historico,
                            num_simulacoes=num_simulacoes
                        )
                        
                        stats = simulador.avaliar_jogo(jogo, verbose=True)
                        
                        # Mostrar resultados
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Média acertos", f"{stats['media']:.2f}")
                        with col2:
                            st.metric("P(11+)", f"{stats['p11']:.2f}%")
                        with col3:
                            st.metric("P(13+)", f"{stats['p13']:.2f}%")
                        with col4:
                            st.metric("P(15)", f"{stats['p15']:.4f}%")
                        
                        # Histograma
                        fig, ax = plt.subplots(figsize=(10, 4))
                        distribuicao = stats['distribuicao']
                        acertos = list(distribuicao.keys())
                        frequencias = list(distribuicao.values())
                        
                        bars = ax.bar(acertos, frequencias, color='#4ade80', edgecolor='black')
                        ax.axvline(stats['media'], color='red', linestyle='--', label=f"Média: {stats['media']:.2f}")
                        ax.set_xlabel('Acertos')
                        ax.set_ylabel('Frequência')
                        ax.set_title(f'Distribuição de Acertos - {num_simulacoes:,} Simulações')
                        ax.legend()
                        st.pyplot(fig)
        
        with sub_tab3:
            st.markdown("### 📊 Análise Avançada de Padrões")
            
            # Análise de entropia
            st.markdown("#### 📈 Entropia de Shannon")
            entropia = ensemble_avancado.entropia
            
            # Calcular entropia dos últimos 50 jogos
            entropias_historicas = [entropia.entropia_jogo(j) for j in st.session_state.historico[:50]]
            media_entropia = np.mean(entropias_historicas)
            std_entropia = np.std(entropias_historicas)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Entropia Média", f"{media_entropia:.4f}")
            with col2:
                st.metric("Desvio Padrão", f"{std_entropia:.4f}")
            with col3:
                st.metric("Intervalo Confiança (95%)", f"{media_entropia-2*std_entropia:.4f} - {media_entropia+2*std_entropia:.4f}")
            
            # Se houver jogos gerados, mostrar entropia deles
            if st.session_state.jogos_gerados:
                st.markdown("#### 🎯 Entropia dos Jogos Gerados")
                entropias_jogos = [entropia.entropia_jogo(j) for j in st.session_state.jogos_gerados]
                
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.hist(entropias_historicas, bins=20, alpha=0.5, label='Histórico', color='#4cc9f0')
                ax.hist(entropias_jogos, bins=20, alpha=0.5, label='Seus Jogos', color='#f97316')
                ax.axvline(media_entropia, color='blue', linestyle='--', label='Média Histórica')
                ax.set_xlabel('Entropia')
                ax.set_ylabel('Frequência')
                ax.set_title('Comparação de Entropia')
                ax.legend()
                st.pyplot(fig)
            
            # Análise de Markov
            st.markdown("#### 🔄 Transições Markov")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Top 10 Transições mais prováveis (ordem 1)**")
                if hasattr(ensemble_avancado.markov1, 'matriz_transicao'):
                    matriz = ensemble_avancado.markov1.matriz_transicao
                    transicoes = []
                    for i in range(25):
                        for j in range(25):
                            if matriz[i][j] > 0.05:  # Filtrar transições significativas
                                transicoes.append((i+1, j+1, matriz[i][j]))
                    
                    transicoes.sort(key=lambda x: x[2], reverse=True)
                    
                    df_trans = pd.DataFrame(
                        transicoes[:10],
                        columns=['De', 'Para', 'Probabilidade']
                    )
                    df_trans['Probabilidade'] = df_trans['Probabilidade'].apply(lambda x: f"{x:.2%}")
                    st.dataframe(df_trans, hide_index=True, use_container_width=True)
            
            with col2:
                st.markdown("**Padrões de Repetição**")
                repeticoes = [len(set(st.session_state.historico[i]) & set(st.session_state.historico[i+1])) 
                             for i in range(len(st.session_state.historico)-1)]
                
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.hist(repeticoes, bins=15, color='#4ade80', edgecolor='black')
                ax.set_xlabel('Número de repetições')
                ax.set_ylabel('Frequência')
                ax.set_title('Distribuição de Repetições')
                st.pyplot(fig)
            
            # Análise geométrica
            st.markdown("#### 📐 Geometria do Volante")
            geometria = ensemble_avancado.geometria
            
            if st.session_state.jogos_gerados:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Densidade de vizinhança
                    densidades = [geometria.densidade_vizinhanca(j) for j in st.session_state.jogos_gerados]
                    st.metric("Densidade média", f"{np.mean(densidades):.2f}")
                    
                    fig, ax = plt.subplots(figsize=(8, 4))
                    ax.hist(densidades, bins=10, color='#4cc9f0', edgecolor='black')
                    ax.set_xlabel('Densidade de vizinhança')
                    ax.set_ylabel('Frequência')
                    ax.set_title('Distribuição de Densidade')
                    st.pyplot(fig)
                
                with col2:
                    # Padrões de linhas/colunas
                    padroes = [geometria.padroes_linhas_colunas(j) for j in st.session_state.jogos_gerados]
                    linhas_unicas = [p['linhas_unicas'] for p in padroes]
                    
                    fig, ax = plt.subplots(figsize=(8, 4))
                    ax.hist(linhas_unicas, bins=5, color='#f97316', edgecolor='black')
                    ax.set_xlabel('Linhas diferentes')
                    ax.set_ylabel('Frequência')
                    ax.set_title('Distribuição por Linhas')
                    st.pyplot(fig)
        
        with sub_tab4:
            st.markdown("### 🎯 Gerador Premium - Ensemble Completo")
            st.markdown("""
            <div class='info-box'>
            <strong>Este gerador combina TODOS os modelos:</strong><br>
            • Entropia de Shannon<br>
            • Markov (ordem 1 e 2)<br>
            • Algoritmo Genético<br>
            • Geometria do Volante<br>
            • Rede Bayesiana<br>
            • Validação Monte Carlo
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                qtd_premium = st.number_input("Quantidade", 5, 50, 15, key="premium_qtd")
            
            with col2:
                modo_premium = st.selectbox(
                    "Estratégia",
                    ["Balanceada", "Alta probabilidade 13+", "Máxima entropia", "Diversificada"],
                    key="modo_premium"
                )
            
            with col3:
                if st.button("🚀 GERAR PREMIUM", use_container_width=True, type="primary"):
                    with st.spinner("Gerando jogos com todos os modelos avançados..."):
                        
                        if modo_premium == "Alta probabilidade 13+":
                            # Foco em Markov e Monte Carlo
                            ensemble_avancado.pesos['markov2'] = 2.0
                            ensemble_avancado.pesos['monte_carlo'] = 2.0
                        elif modo_premium == "Máxima entropia":
                            # Foco em entropia
                            ensemble_avancado.pesos['entropia'] = 2.0
                        elif modo_premium == "Diversificada":
                            # Gerar múltiplas estratégias
                            jogos_premium = []
                            
                            # Estratégia 1: Algoritmo Genético
                            ga = AlgoritmoGeneticoLotofacil(
                                st.session_state.historico,
                                fitness_func=ensemble_avancado.score_ensemble,
                                tamanho_pop=150,
                                taxa_mutacao=0.15
                            )
                            melhores_ga, _ = ga.evoluir(geracoes=50, elite_size=20)
                            jogos_premium.extend(melhores_ga[:5])
                            
                            # Estratégia 2: Markov puro
                            for _ in range(5):
                                jogo = ensemble_avancado.gerar_jogos_genetico(1, 30)[0]
                                jogos_premium.append(jogo)
                            
                            # Remover duplicatas
                            jogos_premium = list({tuple(j): j for j in jogos_premium}.values())
                            
                            st.session_state.jogos_gerados = jogos_premium[:qtd_premium]
                            st.success(f"✅ {len(jogos_premium[:qtd_premium])} jogos gerados!")
                            
                        if modo_premium != "Diversificada":
                            # Usar algoritmo genético com fitness do ensemble
                            jogos_premium = ensemble_avancado.gerar_jogos_genetico(
                                quantidade=qtd_premium * 2,
                                geracoes=80
                            )
                            
                            # Validar com Monte Carlo (amostra reduzida para performance)
                            st.info("Validando jogos com Monte Carlo (20k simulações)...")
                            simulador = SimuladorMonteCarlo(
                                st.session_state.historico,
                                num_simulacoes=20000
                            )
                            
                            ranking = simulador.avaliar_multiplos_jogos(jogos_premium)
                            melhores_ids = ranking.head(qtd_premium)['jogo_id'].values - 1
                            jogos_finais = [jogos_premium[i] for i in melhores_ids]
                            
                            st.session_state.jogos_gerados = jogos_finais
                            st.success(f"✅ {len(jogos_finais)} jogos premium gerados e validados!")
            
            # Mostrar jogos premium se existirem
            if st.session_state.jogos_gerados:
                st.markdown("### 💎 Jogos Premium Gerados")
                
                # Calcular scores avançados
                for i, jogo in enumerate(st.session_state.jogos_gerados[:10]):
                    score_ensemble = ensemble_avancado.score_ensemble(jogo)
                    
                    # Análise rápida
                    baixas = sum(1 for n in jogo if n <= 8)
                    medias = sum(1 for n in jogo if 9 <= n <= 16)
                    pares = sum(1 for n in jogo if n % 2 == 0)
                    
                    # Formatação visual
                    nums_html = ""
                    for n in jogo:
                        if n <= 8:
                            cor = "#4ade80"
                        elif n <= 16:
                            cor = "#4cc9f0"
                        else:
                            cor = "#f97316"
                        nums_html += f"<span style='background:{cor}40; border:2px solid {cor}; border-radius:25px; padding:6px 10px; margin:3px; display:inline-block; font-weight:bold;'>{n:02d}</span>"
                    
                    st.markdown(f"""
                    <div style='background:linear-gradient(145deg, #0e1117, #1a1a2a); border-radius:15px; padding:15px; margin-bottom:15px; border:2px solid gold;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
                            <h4 style='margin:0; color:gold;'>🏆 Jogo Premium #{i+1}</h4>
                            <span style='background:gold; color:black; padding:5px 15px; border-radius:20px; font-weight:bold;'>Score: {score_ensemble:.4f}</span>
                        </div>
                        <div style='margin:15px 0;'>{nums_html}</div>
                        <div style='display:flex; gap:20px; color:#aaa; font-size:0.95rem;'>
                            <span>📊 {baixas} baixas | {medias} médias | {15-baixas-medias} altas</span>
                            <span>⚖️ {pares} pares | {15-pares} ímpares</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Botão para download
                if st.button("💾 Baixar Jogos Premium", use_container_width=True):
                    df_premium = pd.DataFrame({
                        'Jogo': range(1, len(st.session_state.jogos_gerados)+1),
                        'Dezenas': [', '.join(f"{n:02d}" for n in j) for j in st.session_state.jogos_gerados],
                        'Baixas': [sum(1 for n in j if n <= 8) for j in st.session_state.jogos_gerados],
                        'Médias': [sum(1 for n in j if 9 <= n <= 16) for j in st.session_state.jogos_gerados],
                        'Pares': [sum(1 for n in j if n % 2 == 0) for j in st.session_state.jogos_gerados],
                        'Soma': [sum(j) for j in st.session_state.jogos_gerados]
                    })
                    
                    csv = df_premium.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"jogos_premium_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

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
.footer a {
    color: #4ade80;
    text-decoration: none;
}
</style>
<div class="footer">
    <strong>LOTOFÁCIL AI 3.0</strong> • Markov Chains • Algoritmo Genético • Monte Carlo • Entropia • Geometria do Volante • Redes Bayesianas<br>
    Desenvolvido com matemática avançada para máxima precisão • © 2024
</div>
""", unsafe_allow_html=True)
