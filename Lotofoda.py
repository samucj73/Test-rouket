import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V2",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL OTIMIZADA - VERSÃO REFORÇADA
# =====================================================
class AnaliseLotofacilAvancada:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # Análises estatísticas avançadas
        self.frequencias = self._calcular_frequencias_avancadas()
        self.defasagens = self._calcular_defasagens()
        self.padroes_combinatorios = self._analisar_padroes_combinatorios()
        self.matriz_correlacao = self._calcular_matriz_correlacao()
        self.probabilidades_condicionais = self._calcular_prob_condicionais()
        self.tendencias_temporais = self._analisar_tendencias_temporais()
        
        # NOVO: Análise de sequências e padrões específicos
        self.padroes_sequencia = self._analisar_sequencias()
        self.numeros_chave = self._identificar_numeros_chave()
        
    def _calcular_frequencias_avancadas(self):
        """Calcula frequências com ponderação temporal"""
        frequencias = {}
        for num in self.numeros:
            ocorrencias = 0
            peso_total = 0
            
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    # Peso exponencial para dar mais importância aos concursos recentes
                    peso = np.exp(-i / 30)  # Decaimento mais acentuado (antes era 50)
                    ocorrencias += 1
                    peso_total += peso
            
            # Frequência ponderada
            frequencias[num] = (peso_total / self.total_concursos) * 100 if self.total_concursos > 0 else 0
            
        return frequencias
    
    def _calcular_matriz_correlacao(self):
        """Calcula correlação entre números"""
        matriz = defaultdict(lambda: defaultdict(float))
        
        for num1 in self.numeros:
            for num2 in self.numeros:
                if num1 < num2:
                    # Conta quantas vezes aparecem juntos
                    juntos = sum(1 for c in self.concursos if num1 in c and num2 in c)
                    probabilidade = juntos / self.total_concursos if self.total_concursos > 0 else 0
                    matriz[num1][num2] = probabilidade
                    matriz[num2][num1] = probabilidade
        
        return matriz
    
    def _calcular_prob_condicionais(self):
        """Calcula probabilidades condicionais P(A|B)"""
        prob_cond = defaultdict(lambda: defaultdict(float))
        
        for num1 in self.numeros:
            for num2 in self.numeros:
                if num1 != num2:
                    # Probabilidade de num1 dado que num2 apareceu
                    concursos_com_num2 = [c for c in self.concursos if num2 in c]
                    if concursos_com_num2:
                        juntos = sum(1 for c in concursos_com_num2 if num1 in c)
                        prob_cond[num1][num2] = juntos / len(concursos_com_num2)
        
        return prob_cond
    
    def _analisar_padroes_combinatorios(self):
        """Análise avançada de padrões combinatórios"""
        padroes = {
            'somas': [],
            'pares': [],
            'impares': [],
            'primos': [],
            'quadrantes': [],
            'intervalos': [],
            'repetidos_consecutivos': [],
            'sequencias': []  # NOVO
        }
        
        for concurso in self.concursos:
            # Análise de somas
            padroes['somas'].append(sum(concurso))
            
            # Análise par/ímpar
            pares = sum(1 for n in concurso if n % 2 == 0)
            padroes['pares'].append(pares)
            padroes['impares'].append(15 - pares)
            
            # Análise de números primos (até 25)
            primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
            padroes['primos'].append(sum(1 for n in concurso if n in primos))
            
            # Análise por quadrantes (1-12, 13-25)
            padroes['quadrantes'].append(sum(1 for n in concurso if n <= 12))
            
            # Análise de intervalos entre números
            if len(concurso) > 1:
                intervalos = [concurso[i+1] - concurso[i] for i in range(len(concurso)-1)]
                padroes['intervalos'].append(np.mean(intervalos))
            
            # Análise de números repetidos do concurso anterior
            if len(self.concursos) > 1 and concurso != self.concursos[0]:
                idx = self.concursos.index(concurso)
                if idx < len(self.concursos) - 1:
                    anterior = self.concursos[idx + 1]
                    repetidos = len(set(concurso) & set(anterior))
                    padroes['repetidos_consecutivos'].append(repetidos)
            
            # NOVO: Detectar sequências (3+ números consecutivos)
            seq_count = 0
            i = 0
            while i < len(concurso) - 2:
                if concurso[i+2] - concurso[i+1] == 1 and concurso[i+1] - concurso[i] == 1:
                    seq_count += 1
                    i += 3  # Pula a sequência já contada
                else:
                    i += 1
            padroes['sequencias'].append(seq_count)
        
        return padroes
    
    def _analisar_sequencias(self):
        """NOVO: Analisa padrões de sequências numéricas"""
        sequencias = {
            '2_consecutivos': [],
            '3_consecutivos': [],
            '4_consecutivos': [],
            'intervalos_comuns': []
        }
        
        for concurso in self.concursos:
            # Conta pares consecutivos
            pares_consec = 0
            triplas_consec = 0
            quadras_consec = 0
            
            i = 0
            while i < len(concurso)-1:
                if concurso[i+1] - concurso[i] == 1:
                    pares_consec += 1
                    
                    if i < len(concurso)-2 and concurso[i+2] - concurso[i+1] == 1:
                        triplas_consec += 1
                        
                        if i < len(concurso)-3 and concurso[i+3] - concurso[i+2] == 1:
                            quadras_consec += 1
                            i += 3
                        else:
                            i += 2
                    else:
                        i += 1
                else:
                    i += 1
            
            sequencias['2_consecutivos'].append(pares_consec)
            sequencias['3_consecutivos'].append(triplas_consec)
            sequencias['4_consecutivos'].append(quadras_consec)
        
        return sequencias
    
    def _identificar_numeros_chave(self):
        """NOVO: Identifica números que frequentemente aparecem juntos"""
        numeros_chave = []
        
        # Números que aparecem em mais de 50% dos concursos recentes
        limiar = self.total_concursos * 0.5
        for num in self.numeros:
            freq_recente = sum(1 for c in self.concursos[:20] if num in c)
            if freq_recente > 10:  # Apareceu em mais da metade dos últimos 20
                numeros_chave.append(num)
        
        return numeros_chave
    
    def _analisar_tendencias_temporais(self):
        """Analisa tendências temporais dos números"""
        tendencias = {}
        
        for num in self.numeros:
            # Cria série temporal de aparições
            serie = [1 if num in c else 0 for c in self.concursos]
            
            # Média móvel dos últimos 10 concursos
            if len(serie) >= 10:
                media_movel = np.convolve(serie, np.ones(10)/10, mode='valid')
                tendencias[num] = {
                    'tendencia': 'alta' if len(media_movel) > 1 and media_movel[-1] > media_movel[0] else 'baixa',
                    'momento': media_movel[-1] if len(media_movel) > 0 else 0,
                    'volatilidade': np.std(serie)
                }
            else:
                tendencias[num] = {
                    'tendencia': 'estável',
                    'momento': 0,
                    'volatilidade': 0
                }
        
        return tendencias
    
    def _calcular_defasagens(self):
        """Calcula defasagem real e defasagem ponderada"""
        defasagens = {}
        
        for num in self.numeros:
            # Encontra última aparição
            ultima_aparicao = None
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    ultima_aparicao = i
                    break
            
            if ultima_aparicao is not None:
                defasagem_real = ultima_aparicao
                # Defasagem ponderada pela frequência histórica
                frequencia_historica = self.frequencias[num]
                defasagem_ponderada = defasagem_real * (1 - frequencia_historica/100)
                defasagens[num] = {
                    'real': defasagem_real,
                    'ponderada': defasagem_ponderada,
                    'status': 'atrasado' if defasagem_real > 5 else 'normal'
                }
            else:
                defasagens[num] = {
                    'real': len(self.concursos),
                    'ponderada': len(self.concursos),
                    'status': 'critico'
                }
        
        return defasagens
    
    # =================================================
    # NOVA ESTRATÉGIA - CAÇA SEQUÊNCIAS
    # =================================================
    def estrategia_caca_sequencias(self, n_jogos=15):
        """NOVA: Especializada em capturar sequências como 04-05-06"""
        jogos = []
        
        # Analisa frequência de sequências nos últimos concursos
        ultimos_concursos = self.concursos[:20]
        sequencias_frequentes = []
        
        for concurso in ultimos_concursos:
            for i in range(len(concurso)-2):
                if concurso[i+2] - concurso[i+1] == 1 and concurso[i+1] - concurso[i] == 1:
                    sequencias_frequentes.append((concurso[i], concurso[i+1], concurso[i+2]))
        
        # Conta sequências mais comuns
        counter_sequencias = Counter(sequencias_frequentes)
        
        for _ in range(n_jogos):
            jogo = set()
            
            # 40% de chance de incluir uma sequência de 3 números
            if random.random() < 0.4 and counter_sequencias:
                sequencia_escolhida = random.choice(list(counter_sequencias.keys()))
                jogo.update(sequencia_escolhida)
            
            # Inclui números chave
            if self.numeros_chave:
                num_chave = random.choice(self.numeros_chave)
                jogo.add(num_chave)
            
            # Completa com números baseados em frequência
            while len(jogo) < 15:
                # Pesos baseados em frequência
                candidatos = [n for n in self.numeros if n not in jogo]
                if candidatos:
                    pesos = [self.frequencias[n] for n in candidatos]
                    if sum(pesos) > 0:
                        novo_num = random.choices(candidatos, weights=pesos)[0]
                    else:
                        novo_num = random.choice(candidatos)
                    jogo.add(novo_num)
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 1 – REDES NEURAIS SIMPLIFICADAS (REFORÇADA)
    # =================================================
    def estrategia_neural_reforcada(self, n_jogos=15):
        """Usa conceitos de redes neurais com ênfase em números recentes"""
        jogos = []
        
        for _ in range(n_jogos):
            # Camada de entrada: frequências + defasagens + tendências
            scores = {}
            
            for num in self.numeros:
                # Peso 1: Frequência ponderada (maior peso)
                w1 = self.frequencias[num] / 100
                
                # Peso 2: Defasagem (normalizada)
                w2 = 1 - (self.defasagens[num]['real'] / self.total_concursos) if self.total_concursos > 0 else 0
                
                # Peso 3: Momento/tendência
                w3 = self.tendencias_temporais[num]['momento']
                
                # Peso 4: Volatilidade (inversa)
                w4 = 1 - self.tendencias_temporais[num]['volatilidade']
                
                # Peso 5: Números chave (bonus)
                w5 = 0.2 if num in self.numeros_chave else 0
                
                # Score combinado com pesos ajustados
                scores[num] = 0.30*w1 + 0.25*w2 + 0.20*w3 + 0.15*w4 + 0.10*w5
            
            # Seleciona números com maior score
            numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            
            # Pega top 20 e adiciona ruído
            jogo = []
            for num, score in numeros_ordenados[:20]:
                score_com_ruido = score + np.random.normal(0, 0.03)  # Menos ruído
                jogo.append((num, score_com_ruido))
            
            # Ordena por score e pega os 15 melhores
            jogo = sorted(jogo, key=lambda x: x[1], reverse=True)[:15]
            jogos.append(sorted([x[0] for x in jogo]))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 2 – ANÁLISE DE CORRELAÇÃO (REFORÇADA)
    # =================================================
    def estrategia_correlacao_reforcada(self, n_jogos=15):
        """Baseada em pares de números que costumam sair juntos"""
        jogos = []
        
        # Identifica os pares mais fortes
        pares_fortes = []
        for num1 in range(1, 26):
            for num2 in range(num1+1, 26):
                prob = self.matriz_correlacao[num1][num2]
                if prob > 0.3:  # Correlação forte
                    pares_fortes.append((num1, num2, prob))
        
        pares_fortes.sort(key=lambda x: x[2], reverse=True)
        
        for _ in range(n_jogos):
            jogo = set()
            
            # Adiciona um par forte
            if pares_fortes:
                par = random.choice(pares_fortes[:10])
                jogo.add(par[0])
                jogo.add(par[1])
            
            # Adiciona números chave
            if self.numeros_chave:
                jogo.add(random.choice(self.numeros_chave))
            
            # Completa com base em correlação
            while len(jogo) < 15:
                ultimos = list(jogo)[-3:] if len(jogo) >= 3 else list(jogo)
                
                candidatos = []
                pesos = []
                
                for num in self.numeros:
                    if num not in jogo:
                        # Média das correlações com os últimos números
                        correlacao_media = np.mean([self.matriz_correlacao[num][u] for u in ultimos])
                        candidatos.append(num)
                        pesos.append(correlacao_media)
                
                if candidatos and sum(pesos) > 0:
                    novo_num = random.choices(candidatos, weights=pesos)[0]
                elif candidatos:
                    novo_num = random.choice(candidatos)
                else:
                    break
                
                jogo.add(novo_num)
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 3 – ALGORITMO GENÉTICO (REFORÇADO)
    # =================================================
    def estrategia_genetica_reforcada(self, n_jogos=15, geracoes=70, populacao=150):
        """Usa algoritmo genético com função fitness melhorada"""
        
        def fitness(jogo):
            """Função de aptidão do jogo - REFORÇADA"""
            score = 0
            
            # Critério 1: Média das frequências dos números
            freq_media = np.mean([self.frequencias[n] for n in jogo])
            score += freq_media * 0.25
            
            # Critério 2: Variedade de quadrantes
            quadrantes = sum(1 for n in jogo if n <= 12)
            score += 15 - abs(quadrantes - 7) * 2
            
            # Critério 3: Proporção par/ímpar
            pares = sum(1 for n in jogo if n % 2 == 0)
            score += 15 - abs(pares - 7) * 2
            
            # Critério 4: Soma próxima da média histórica
            soma_media = self.padroes_combinatorios['somas']
            if soma_media:
                media_historica = np.mean(soma_media)
                score += 15 - abs(sum(jogo) - media_historica) / 15
            
            # Critério 5: Correlação positiva entre números
            correlacao_media = 0
            total_pares = 0
            for i in range(len(jogo)):
                for j in range(i+1, len(jogo)):
                    correlacao_media += self.matriz_correlacao[jogo[i]][jogo[j]]
                    total_pares += 1
            
            if total_pares > 0:
                correlacao_media /= total_pares
                score += correlacao_media * 25
            
            # NOVO Critério 6: Presença de números chave
            num_chave_presentes = sum(1 for n in jogo if n in self.numeros_chave)
            score += num_chave_presentes * 3
            
            # NOVO Critério 7: Potencial para sequências (AJUSTADO)
            tem_sequencia = 0
            i = 0
            while i < len(jogo)-2:
                if jogo[i+2] - jogo[i+1] == 1 and jogo[i+1] - jogo[i] == 1:
                    tem_sequencia += 3  # Reduzido de 5 para 3
                    i += 3
                else:
                    i += 1
            score += tem_sequencia
            
            return score
        
        # População inicial
        populacao_atual = []
        for _ in range(populacao):
            jogo = sorted(random.sample(self.numeros, 15))
            populacao_atual.append((jogo, fitness(jogo)))
        
        # Evolução
        for _ in range(geracoes):
            # Seleção dos melhores
            nova_populacao = []
            
            # Elitismo - mantém os 15% melhores
            populacao_atual.sort(key=lambda x: x[1], reverse=True)
            nova_populacao.extend(populacao_atual[:max(1, populacao//6)])
            
            # Gera novos indivíduos
            while len(nova_populacao) < populacao:
                # Seleciona dois pais
                pai1 = max(random.sample(populacao_atual, min(5, len(populacao_atual))), key=lambda x: x[1])
                pai2 = max(random.sample(populacao_atual, min(5, len(populacao_atual))), key=lambda x: x[1])
                
                # Crossover com 2 pontos
                ponto1 = random.randint(3, 7)
                ponto2 = random.randint(8, 12)
                filho = list(set(pai1[0][:ponto1] + pai2[0][ponto1:ponto2] + pai1[0][ponto2:]))
                
                # Mutação (15% de chance)
                if random.random() < 0.15:
                    if filho:
                        idx = random.randint(0, len(filho)-1)
                        candidatos = [n for n in self.numeros if n not in filho]
                        if candidatos:
                            novo_num = random.choice(candidatos)
                            filho[idx] = novo_num
                
                # Completa para 15 números
                while len(filho) < 15:
                    candidatos = [n for n in self.numeros if n not in filho]
                    if candidatos:
                        # Prioriza números chave
                        chave_disponiveis = [n for n in candidatos if n in self.numeros_chave]
                        if chave_disponiveis and random.random() < 0.3:
                            novo_num = random.choice(chave_disponiveis)
                        else:
                            novo_num = random.choice(candidatos)
                        filho.append(novo_num)
                    else:
                        break
                
                if len(filho) == 15:
                    filho = sorted(filho)
                    nova_populacao.append((filho, fitness(filho)))
            
            populacao_atual = nova_populacao
        
        # Retorna os melhores jogos
        populacao_atual.sort(key=lambda x: x[1], reverse=True)
        return [jogo for jogo, _ in populacao_atual[:min(n_jogos, len(populacao_atual))]]
    
    # =================================================
    # ESTRATÉGIA 4 – PROBABILIDADE CONDICIONAL (REFORÇADA)
    # =================================================
    def estrategia_condicional_reforcada(self, n_jogos=15):
        """Baseada em probabilidades condicionais com cadeias mais longas"""
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Primeiro número: prioriza números chave
            if self.numeros_chave and random.random() < 0.7:
                primeiro = random.choice(self.numeros_chave)
            else:
                numeros_freq = sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)
                primeiro = random.choice([n for n, _ in numeros_freq[:8]])
            jogo.append(primeiro)
            
            # Próximos números: cadeia de Markov de ordem 2
            while len(jogo) < 15:
                ultimos = jogo[-2:] if len(jogo) >= 2 else [jogo[-1]] * 2
                
                # Calcula probabilidades baseadas nos últimos 2 números
                probabilidades = {}
                for num in self.numeros:
                    if num not in jogo:
                        # Média ponderada das probabilidades condicionais
                        prob1 = self.probabilidades_condicionais.get(num, {}).get(ultimos[-1], 0)
                        prob2 = self.probabilidades_condicionais.get(num, {}).get(ultimos[-2], 0) if len(ultimos) > 1 else 0
                        prob = (prob1 * 0.7 + prob2 * 0.3)
                        probabilidades[num] = prob
                
                # Seleciona próximo número
                candidatos = list(probabilidades.keys())
                pesos = list(probabilidades.values())
                
                if sum(pesos) > 0:
                    proximo = random.choices(candidatos, weights=pesos)[0]
                else:
                    # Fallback para frequência
                    candidatos_freq = [n for n in self.numeros if n not in jogo]
                    if candidatos_freq:
                        pesos_freq = [self.frequencias[n] for n in candidatos_freq]
                        if sum(pesos_freq) > 0:
                            proximo = random.choices(candidatos_freq, weights=pesos_freq)[0]
                        else:
                            proximo = random.choice(candidatos_freq)
                    else:
                        break
                
                jogo.append(proximo)
            
            if len(jogo) == 15:
                jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 5 – ENSEMBLE REFORÇADO
    # =================================================
    def estrategia_ensemble_reforcada(self, n_jogos=15):
        """Combina múltiplas estratégias com pesos otimizados"""
        
        # Gera jogos de cada estratégia
        jogos_neural = self.estrategia_neural_reforcada(n_jogos)
        jogos_correlacao = self.estrategia_correlacao_reforcada(n_jogos)
        jogos_genetico = self.estrategia_genetica_reforcada(max(1, n_jogos//2))
        jogos_condicional = self.estrategia_condicional_reforcada(n_jogos)
        jogos_sequencia = self.estrategia_caca_sequencias(n_jogos//2)
        
        # Converte para sets
        todos_jogos = jogos_neural + jogos_correlacao + jogos_genetico + jogos_condicional + jogos_sequencia
        
        if not todos_jogos:
            return []
        
        # Cria ranking de números
        contador_numeros = Counter()
        for jogo in todos_jogos:
            contador_numeros.update(jogo)
        
        # Gera novos jogos
        jogos_finais = []
        for _ in range(n_jogos):
            numeros_rank = [num for num, _ in contador_numeros.most_common()]
            
            if not numeros_rank:
                continue
                
            jogo = set()
            
            # Garante números do topo (60%)
            top_numeros = numeros_rank[:min(18, len(numeros_rank))]
            qtd_top = random.randint(8, 10)
            jogo.update(random.sample(top_numeros, min(qtd_top, len(top_numeros))))
            
            # Garante números chave
            if self.numeros_chave:
                chave_disponiveis = [n for n in self.numeros_chave if n not in jogo]
                if chave_disponiveis and len(jogo) < 13:
                    qtd_chave = min(2, len(chave_disponiveis))
                    jogo.update(random.sample(chave_disponiveis, qtd_chave))
            
            # Completa com números variados
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros if n not in jogo]
                if candidatos:
                    # 30% de chance de pegar um número menos frequente
                    if random.random() < 0.3 and len(candidatos) > 5:
                        menos_freq = sorted(candidatos, key=lambda x: self.frequencias[x])[:5]
                        jogo.add(random.choice(menos_freq))
                    else:
                        jogo.add(random.choice(candidatos))
                else:
                    break
            
            if len(jogo) == 15:
                jogos_finais.append(sorted(jogo))
        
        return jogos_finais
    
    # =================================================
    # VALIDAÇÃO ESTATÍSTICA - CORRIGIDA
    # =================================================
    def validar_jogo(self, jogo):
        """Valida um jogo baseado em critérios estatísticos - VERSÃO CORRIGIDA"""
        validacao = {
            'valido': True,
            'motivos': []
        }
        
        # Critério 1: Soma dentro de 2.5 desvios padrão
        soma_stats = self.padroes_combinatorios['somas']
        if soma_stats:
            media = np.mean(soma_stats)
            desvio = np.std(soma_stats)
            soma_jogo = sum(jogo)
            
            if abs(soma_jogo - media) > 2.5 * desvio:
                validacao['valido'] = False
                validacao['motivos'].append(f"Soma {soma_jogo} fora do padrão")
        
        # Critério 2: Proporção par/ímpar
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares < 5 or pares > 10:
            validacao['valido'] = False
            validacao['motivos'].append(f"Proporção par/ímpar atípica")
        
        # CRITÉRIO 3 CORRIGIDO: Números consecutivos (ajustado ao padrão real)
        consecutivos = 0
        for i in range(len(jogo)-1):
            if jogo[i+1] - jogo[i] == 1:
                consecutivos += 1
        
        # Lotofácil aceita bem até 7 consecutivos
        if consecutivos > 7:
            validacao['valido'] = False
            validacao['motivos'].append(f"Muitos consecutivos")
        
        # CRITÉRIO 4 CORRIGIDO: Presença de números chave (menos restritivo)
        num_chave = sum(1 for n in jogo if n in self.numeros_chave)
        if num_chave < 2:  # Reduzido de 3 para 2
            validacao['valido'] = False
            validacao['motivos'].append(f"Poucos números chave")
        
        return validacao
    
    # =================================================
    # CONFERÊNCIA AVANÇADA - CORRIGIDA
    # =================================================
    def conferir_jogos_avancada(self, jogos, concurso_alvo=None):
        """Conferência detalhada com análise estatística - VERSÃO CORRIGIDA"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            # Validação do jogo
            validacao = self.validar_jogo(jogo)
            
            # Conferência básica
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            
            # Análise detalhada
            pares_jogo = sum(1 for n in jogo if n % 2 == 0)
            pares_concurso = sum(1 for n in concurso_alvo if n % 2 == 0) if concurso_alvo else 0
            
            # Análise de quadrantes
            quad1_jogo = sum(1 for n in jogo if n <= 12)
            quad1_concurso = sum(1 for n in concurso_alvo if n <= 12) if concurso_alvo else 0
            
            # Análise de primos
            primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
            primos_jogo = sum(1 for n in jogo if n in primos)
            primos_concurso = sum(1 for n in concurso_alvo if n in primos) if concurso_alvo else 0
            
            # Análise de sequências - CORRIGIDA (não conta múltiplas vezes)
            seq_jogo = 0
            i = 0
            while i < len(jogo)-2:
                if jogo[i+2] - jogo[i+1] == 1 and jogo[i+1] - jogo[i] == 1:
                    seq_jogo += 1
                    i += 3  # Pula a sequência já contada
                else:
                    i += 1
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Soma": sum(jogo),
                "Pares": pares_jogo,
                "Quadrante": quad1_jogo,
                "Primos": primos_jogo,
                "Sequências": seq_jogo,
                "Válido": "✅" if validacao['valido'] else "❌",
                "Motivos": ", ".join(validacao['motivos']) if validacao['motivos'] else "N/A"
            })
        
        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V2")
    
    st.markdown("""
    ### 🎲 Sistema Avançado de Análise Estatística - Versão Reforçada
    Esta versão é **especializada em capturar sequências e números chave** 
    que costumam aparecer nos sorteios da Lotofácil.
    
    ⚠️ **Aviso Importante:** Não existe garantia de ganhos - a loteria é um jogo de azar.
    Use com responsabilidade!
    """)
    
    # Inicialização da sessão
    if "concursos" not in st.session_state:
        st.session_state.concursos = []
    
    if "jogos" not in st.session_state:
        st.session_state.jogos = []
    
    if "analise" not in st.session_state:
        st.session_state.analise = None
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd = st.slider(
            "Quantidade de concursos para análise", 
            min_value=20, 
            max_value=1000, 
            value=100,
            step=20
        )
        
        if st.button("🔄 Carregar dados históricos", type="primary"):
            with st.spinner("Carregando concursos..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if len(concursos) >= 20:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilAvancada(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        ultimo = resposta[0]
                        st.info(f"📅 Último concurso: {ultimo['concurso']} - {ultimo['data']}")
                        
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Abas
    if st.session_state.concursos and len(st.session_state.concursos) >= 20:
        tab1, tab2, tab3 = st.tabs(["📈 Análise", "🎲 Gerar Jogos", "📊 Resultados"])
        
        with tab1:
            st.header("📊 Análise Estatística")
            st.info(f"📈 Analisando {len(st.session_state.concursos)} concursos")
            
            # Mostra números chave
            if st.session_state.analise.numeros_chave:
                st.subheader("🔑 Números Chave Identificados")
                st.write(f"**{', '.join([str(n) for n in sorted(st.session_state.analise.numeros_chave)])}**")
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência Ponderada (%)",
                    labels={'x': 'Número', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                fig_def = px.bar(
                    x=range(1, 26),
                    y=[st.session_state.analise.defasagens[n]['real'] for n in range(1, 26)],
                    title="Defasagem (concursos sem sair)",
                    labels={'x': 'Número', 'y': 'Concursos'}
                )
                st.plotly_chart(fig_def, use_container_width=True)
        
        with tab2:
            st.header("🎲 Gerar Jogos Inteligentes - VERSÃO REFORÇADA")
            
            estrategia = st.selectbox(
                "Escolha a estratégia (Recomendado: Ensemble Reforçado)",
                [
                    "🧠 Ensemble Reforçado (RECOMENDADO)",
                    "🔗 Caça Sequências",
                    "🧬 Algoritmo Genético Reforçado",
                    "🎯 Rede Neural Reforçada"
                ]
            )
            
            quantidade = st.number_input("Quantidade de jogos", 5, 50, 15)
            
            if st.button("🚀 Gerar jogos", type="primary"):
                with st.spinner("Gerando jogos com algoritmos reforçados..."):
                    mapa = {
                        "🧠 Ensemble Reforçado (RECOMENDADO)": st.session_state.analise.estrategia_ensemble_reforcada,
                        "🔗 Caça Sequências": st.session_state.analise.estrategia_caca_sequencias,
                        "🧬 Algoritmo Genético Reforçado": lambda n: st.session_state.analise.estrategia_genetica_reforcada(n, geracoes=70),
                        "🎯 Rede Neural Reforçada": st.session_state.analise.estrategia_neural_reforcada
                    }
                    
                    st.session_state.jogos = mapa[estrategia](quantidade)
                    st.success(f"✅ {len(st.session_state.jogos)} jogos gerados!")
        
        with tab3:
            if st.session_state.jogos:
                st.header("📊 Resultados")
                
                # Permite inserir resultado manual
                with st.expander("🔢 Inserir resultado do sorteio manualmente"):
                    resultado_input = st.text_input(
                        "Digite os números (separados por vírgula ou espaço)",
                        placeholder="Ex: 01,04,05,06,10,11,13,14,16,18,19,20,21,23,24"
                    )
                    
                    if st.button("Conferir com resultado manual"):
                        try:
                            if ',' in resultado_input:
                                nums = [int(x.strip()) for x in resultado_input.split(',')]
                            else:
                                nums = [int(x) for x in resultado_input.split()]
                            
                            if len(nums) == 15:
                                st.session_state.resultado_manual = sorted(nums)
                                st.success("Resultado carregado!")
                            else:
                                st.error("Digite exatamente 15 números!")
                        except:
                            st.error("Formato inválido!")
                
                # Escolhe concurso alvo
                concurso_alvo = st.session_state.get('resultado_manual', st.session_state.analise.ultimo_concurso)
                
                # Conferência
                resultado = st.session_state.analise.conferir_jogos_avancada(
                    st.session_state.jogos, concurso_alvo
                )
                df_resultado = pd.DataFrame(resultado)
                st.dataframe(df_resultado, use_container_width=True)
                
                # Estatísticas
                st.subheader("📈 Estatísticas de Acertos")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Média", f"{df_resultado['Acertos'].mean():.2f}")
                with col2:
                    st.metric("Máximo", df_resultado['Acertos'].max())
                with col3:
                    st.metric("Mínimo", df_resultado['Acertos'].min())
                with col4:
                    acima_10 = sum(df_resultado['Acertos'] >= 11)
                    st.metric("≥11 pontos", acima_10)
                
                # Distribuição
                fig = px.histogram(df_resultado, x='Acertos', nbins=15, 
                                  title='Distribuição de Acertos')
                st.plotly_chart(fig, use_container_width=True)
                
                # Exportação
                csv = df_resultado.to_csv(index=False)
                st.download_button(
                    label="📥 Exportar CSV",
                    data=csv,
                    file_name=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ℹ️ Gere jogos primeiro!")

if __name__ == "__main__":
    main()
