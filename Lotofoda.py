import streamlit as st
import requests
import numpy as np
import pandas as pd
import random
from collections import Counter
from itertools import combinations
import math
import matplotlib.pyplot as plt

st.set_page_config(page_title="Lotofácil - 20 Estratégias Avançadas", layout="wide")

# ============================================
# CLASSE ÚNICA COM TODAS AS 20 ESTRATÉGIAS
# ============================================
class EstrategiasLotofacil:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    
    # ============================================
    # ESTRATÉGIA 1: NÚMEROS FRIOS (LEI DOS TERÇOS)
    # ============================================
    def estrategia_frios_leidoterco(self, n_jogos=5):
        """Lei dos Terços: 1/3 dos números ficam abaixo da média"""
        if len(self.concursos) < 15:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        total_numeros = len(self.concursos) * 15
        freq_esperada = total_numeros / 25
        
        freq_real = Counter()
        for concurso in self.concursos:
            freq_real.update(concurso)
        
        frios = [n for n in self.numeros if freq_real[n] < freq_esperada * 0.7]
        quentes = [n for n in self.numeros if freq_real[n] > freq_esperada * 1.3]
        medios = [n for n in self.numeros if n not in frios and n not in quentes]
        
        jogos = []
        for _ in range(n_jogos):
            n_frios = min(7, len(frios))
            n_quentes = min(4, len(quentes))
            n_medios = 15 - n_frios - n_quentes
            
            jogo = []
            if frios:
                jogo.extend(random.sample(frios, min(n_frios, len(frios))))
            if quentes:
                jogo.extend(random.sample(quentes, min(n_quentes, len(quentes))))
            if medios:
                jogo.extend(random.sample(medios, min(n_medios, len(medios))))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 2: COBERTURA MÍNIMA
    # ============================================
    def estrategia_cobertura_garantida(self, n_jogos=8):
        """Cobertura máxima com mínima sobreposição"""
        jogos = []
        numeros_ordenados = self.numeros.copy()
        random.shuffle(numeros_ordenados)
        
        for i in range(n_jogos):
            jogo = []
            inicio = (i * 15) % 25
            for j in range(15):
                idx = (inicio + j) % 25
                jogo.append(numeros_ordenados[idx])
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 3: SOMA ÓTIMA
    # ============================================
    def estrategia_soma_otima(self, n_jogos=5):
        """Soma entre 180-200 (68% dos concursos)"""
        if len(self.concursos) < 10:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        somas = [sum(concurso) for concurso in self.concursos[-50:]]
        media_soma = np.mean(somas) if somas else 195
        
        soma_min = max(170, media_soma - 15)
        soma_max = min(210, media_soma + 15)
        
        jogos = []
        for _ in range(n_jogos * 3):
            pares = random.randint(6, 9)
            impares = 15 - pares
            
            nums_pares = [n for n in self.numeros if n % 2 == 0]
            nums_impares = [n for n in self.numeros if n % 2 == 1]
            
            jogo = []
            if len(nums_pares) >= pares:
                jogo.extend(random.sample(nums_pares, pares))
            if len(nums_impares) >= impares:
                jogo.extend(random.sample(nums_impares, impares))
            
            jogo = sorted(jogo)
            
            if len(jogo) == 15:
                soma = sum(jogo)
                if soma_min <= soma <= soma_max:
                    if jogo not in jogos:
                        jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 4: GRUPOS (LINHAS)
    # ============================================
    def estrategia_grupos(self, n_jogos=5):
        """Distribuição por linhas da cartela"""
        grupos = [
            list(range(1, 6)),
            list(range(6, 11)),
            list(range(11, 16)),
            list(range(16, 21)),
            list(range(21, 26))
        ]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = []
            for grupo in grupos:
                selecionados = random.sample(grupo, min(3, len(grupo)))
                jogo.extend(selecionados)
            
            jogo = sorted(set(jogo))[:15]
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 5: PARETO (80/20)
    # ============================================
    def estrategia_pareto(self, n_jogos=5):
        """Foco nos 20% números mais frequentes"""
        if len(self.concursos) < 15:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        freq = Counter()
        for concurso in self.concursos[:100]:
            freq.update(concurso)
        
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top5 = [n for n, _ in numeros_ordenados[:5]]
        resto = [n for n in self.numeros if n not in top5]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = top5.copy()
            complemento = random.sample(resto, 10)
            jogo.extend(complemento)
            jogos.append(sorted(set(jogo))[:15])
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 6: ESPELHOS
    # ============================================
    def estrategia_espelhos(self, n_jogos=5):
        """Complemento do último concurso"""
        if not self.concursos:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        ultimo = self.concursos[0]
        espelho = [n for n in self.numeros if n not in ultimo]
        
        jogos = []
        for _ in range(n_jogos):
            n_espelho = random.randint(8, 12)
            n_ultimo = 15 - n_espelho
            
            jogo = []
            if len(espelho) >= n_espelho:
                jogo.extend(random.sample(espelho, n_espelho))
            if len(ultimo) >= n_ultimo:
                jogo.extend(random.sample(ultimo, n_ultimo))
            
            jogo = sorted(set(jogo))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            while len(jogo) > 15:
                jogo.pop()
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 7: INTERVALOS UNIFORMES
    # ============================================
    def estrategia_intervalos(self, n_jogos=5):
        """Gaps uniformes entre números"""
        jogos = []
        for _ in range(n_jogos):
            jogo = []
            jogo.append(random.randint(1, 5))
            
            while len(jogo) < 15:
                ultimo = jogo[-1]
                intervalo = random.randint(1, 2)
                proximo = ultimo + intervalo
                
                if proximo <= 25 and proximo not in jogo:
                    jogo.append(proximo)
                else:
                    disponiveis = [n for n in range(ultimo + 1, 26) if n not in jogo]
                    if disponiveis:
                        jogo.append(random.choice(disponiveis))
                    else:
                        jogo = [random.randint(1, 5)]
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 8: WHEELING
    # ============================================
    def estrategia_wheeling(self, n_jogos=5):
        """Sistema de roda para 18 números"""
        if len(self.concursos) > 15:
            freq = Counter()
            for concurso in self.concursos[:50]:
                freq.update(concurso)
            numeros_base = [n for n, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:18]]
        else:
            numeros_base = random.sample(self.numeros, 18)
        
        jogos = []
        for i in range(0, 15, 3):
            jogo = []
            for j in range(15):
                idx = (i + j) % 18
                jogo.append(numeros_base[idx])
            jogos.append(sorted(set(jogo))[:15])
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 9: CÍCLICA
    # ============================================
    def estrategia_ciclica(self, n_jogos=5):
        """Baseada nos últimos 5 concursos"""
        if len(self.concursos) < 5:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        ultimos = self.concursos[:5]
        freq = Counter()
        for concurso in ultimos:
            freq.update(concurso)
        
        top15 = [n for n, _ in freq.most_common(15)]
        
        jogos = []
        for _ in range(n_jogos):
            n_top = random.randint(10, 12)
            jogo = random.sample(top15, min(n_top, len(top15)))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 10: ENSEMBLE 1.0
    # ============================================
    def estrategia_ensemble(self, n_jogos=10):
        """Combinação de 6 estratégias"""
        todas = [
            self.estrategia_frios_leidoterco,
            self.estrategia_soma_otima,
            self.estrategia_grupos,
            self.estrategia_pareto,
            self.estrategia_espelhos,
            self.estrategia_intervalos
        ]
        
        jogos = []
        jogos_por = max(1, n_jogos // len(todas))
        
        for estrategia in todas:
            try:
                novos = estrategia(jogos_por)
                jogos.extend(novos)
            except:
                continue
        
        # Remove duplicatas
        unicos = []
        seen = set()
        for jogo in jogos:
            chave = tuple(jogo)
            if chave not in seen and len(jogo) == 15:
                seen.add(chave)
                unicos.append(jogo)
        
        return unicos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 11: JANELAS MÓVEIS
    # ============================================
    def estrategia_janelas_moveis(self, n_jogos=5, janela=5):
        """Teoria das Janelas: repetição em ciclos de 5-8 concursos"""
        if len(self.concursos) < janela + 1:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        jogos = []
        numeros_janela = []
        for concurso in self.concursos[:janela]:
            numeros_janela.extend(concurso)
        
        freq_janela = Counter(numeros_janela)
        total = len(numeros_janela)
        
        probabilidades = {num: (freq_janela.get(num, 0) / total * 100) if total > 0 else 0 
                         for num in self.numeros}
        
        numeros_quentes = [n for n, _ in sorted(probabilidades.items(), key=lambda x: x[1], reverse=True)[:20]]
        numeros_frios = [n for n in self.numeros if n not in numeros_janela]
        
        for _ in range(n_jogos):
            n_quentes = random.randint(10, 12)
            n_frios = 15 - n_quentes
            
            jogo = []
            if numeros_quentes:
                jogo.extend(random.sample(numeros_quentes[:15], min(n_quentes, len(numeros_quentes[:15]))))
            if numeros_frios and n_frios > 0:
                jogo.extend(random.sample(numeros_frios, min(n_frios, len(numeros_frios))))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 12: TERMINAÇÕES
    # ============================================
    def estrategia_terminacoes(self, n_jogos=5):
        """Análise de dígitos finais (0-9)"""
        jogos = []
        terminacoes = list(range(10))
        
        nums_por_terminacao = {t: [] for t in terminacoes}
        for num in self.numeros:
            nums_por_terminacao[num % 10].append(num)
        
        for _ in range(n_jogos * 2):
            jogo = []
            terminacoes_usadas = set()
            qtde_alvo = random.randint(4, 6)
            
            terminacoes_sel = random.sample(terminacoes, min(qtde_alvo, len(terminacoes)))
            
            for t in terminacoes_sel:
                if nums_por_terminacao[t]:
                    qtd = random.randint(2, 4)
                    disponiveis = [n for n in nums_por_terminacao[t] if n not in jogo]
                    if len(disponiveis) >= qtd:
                        selecionados = random.sample(disponiveis, qtd)
                        jogo.extend(selecionados)
                        terminacoes_usadas.add(t)
            
            while len(jogo) < 15:
                t = random.choice(terminacoes)
                disponiveis = [n for n in nums_por_terminacao[t] if n not in jogo]
                if disponiveis:
                    jogo.append(random.choice(disponiveis))
                    terminacoes_usadas.add(t)
            
            if 4 <= len(terminacoes_usadas) <= 6:
                if len(jogo) == 15 and jogo not in jogos:
                    jogos.append(sorted(jogo))
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 13: CICLOS DE REPETIÇÃO
    # ============================================
    def estrategia_ciclos_repeticao(self, n_jogos=5):
        """Repetição programada a cada 3-7 concursos"""
        if len(self.concursos) < 10:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        jogos = []
        ciclos = {num: [] for num in self.numeros}
        
        for i in range(len(self.concursos) - 1):
            atual = set(self.concursos[i])
            prox = set(self.concursos[i + 1])
            repeticoes = atual & prox
            for num in repeticoes:
                ciclos[num].append(1)
        
        medias = {}
        for num in self.numeros:
            medias[num] = sum(ciclos[num]) / len(ciclos[num]) if ciclos[num] else 0.3
        
        top_repetidores = [n for n, _ in sorted(medias.items(), key=lambda x: x[1], reverse=True)[:12]]
        ultimo = set(self.concursos[0]) if self.concursos else set()
        
        for _ in range(n_jogos):
            jogo = []
            
            n_rep = random.randint(5, 8)
            if ultimo:
                repetidores = random.sample(list(ultimo), min(n_rep, len(ultimo)))
                jogo.extend(repetidores)
            
            n_outros = random.randint(4, 7)
            outros = [n for n in top_repetidores if n not in jogo]
            if outros:
                jogo.extend(random.sample(outros, min(n_outros, len(outros))))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 14: PAR/ÍMPAR AVANÇADO
    # ============================================
    def estrategia_par_impar_avancada(self, n_jogos=5):
        """Proporção áurea 6/9 a 8/7"""
        jogos = []
        pares = [n for n in self.numeros if n % 2 == 0]
        impares = [n for n in self.numeros if n % 2 == 1]
        
        distribuicoes = [(8, 7), (7, 8), (9, 6), (6, 9)]
        
        for _ in range(n_jogos):
            n_pares, n_impares = random.choice(distribuicoes)
            
            jogo = []
            if len(pares) >= n_pares:
                jogo.extend(random.sample(pares, n_pares))
            if len(impares) >= n_impares:
                jogo.extend(random.sample(impares, n_impares))
            
            if len(jogo) != 15:
                jogo = sorted(random.sample(self.numeros, 15))
            else:
                jogo = sorted(jogo)
            
            pares_final = sum(1 for n in jogo if n % 2 == 0)
            if 6 <= pares_final <= 9:
                jogos.append(jogo)
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 15: TENDÊNCIA TEMPORAL
    # ============================================
    def estrategia_tendencia_temporal(self, n_jogos=5):
        """Momentum e direção dos números"""
        if len(self.concursos) < 20:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        jogos = []
        tendencias = {}
        
        for num in self.numeros:
            aparicoes = []
            for concurso in self.concursos[:20]:
                aparicoes.append(1 if num in concurso else 0)
            
            if len(aparicoes) >= 5:
                recente = sum(aparicoes[:5])
                anterior = sum(aparicoes[5:10])
                
                if recente > anterior:
                    tendencias[num] = 'subindo'
                elif recente < anterior:
                    tendencias[num] = 'descendo'
                else:
                    tendencias[num] = 'estavel'
            else:
                tendencias[num] = 'estavel'
        
        subindo = [n for n in self.numeros if tendencias[n] == 'subindo']
        descendo = [n for n in self.numeros if tendencias[n] == 'descendo']
        estavel = [n for n in self.numeros if tendencias[n] == 'estavel']
        
        for _ in range(n_jogos):
            jogo = []
            
            n_subindo = min(8, len(subindo))
            if subindo:
                jogo.extend(random.sample(subindo, n_subindo))
            
            n_descendo = min(4, len(descendo))
            if descendo:
                jogo.extend(random.sample(descendo, n_descendo))
            
            while len(jogo) < 15:
                if estavel:
                    candidato = random.choice(estavel)
                    if candidato not in jogo:
                        jogo.append(candidato)
                else:
                    candidato = random.choice(self.numeros)
                    if candidato not in jogo:
                        jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 16: CONJUNTOS DISJUNTOS
    # ============================================
    def estrategia_conjuntos_disjuntos(self, n_jogos=5):
        """Cobertura máxima com conjuntos disjuntos"""
        conjuntos = [
            set([1, 6, 11, 16, 21]),
            set([2, 7, 12, 17, 22]),
            set([3, 8, 13, 18, 23]),
            set([4, 9, 14, 19, 24]),
            set([5, 10, 15, 20, 25]),
        ]
        
        jogos = []
        for i in range(n_jogos):
            jogo = set()
            
            for conjunto in conjuntos:
                selecionados = random.sample(list(conjunto), min(3, len(conjunto)))
                jogo.update(selecionados)
            
            if len(jogo) > 15:
                jogo = set(random.sample(list(jogo), 15))
            elif len(jogo) < 15:
                todos = set(self.numeros)
                disponiveis = list(todos - jogo)
                if disponiveis:
                    complemento = random.sample(disponiveis, 15 - len(jogo))
                    jogo.update(complemento)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 17: MONTE CARLO
    # ============================================
    def estrategia_monte_carlo(self, n_jogos=5, iteracoes=5000):
        """Simulação de Monte Carlo para combinações ótimas"""
        if len(self.concursos) < 30:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        freq = Counter()
        for concurso in self.concursos:
            freq.update(concurso)
        
        total = len(self.concursos) * 15
        probs = {num: freq.get(num, 0) / total for num in self.numeros}
        
        melhores = []
        melhores_scores = []
        
        for _ in range(iteracoes):
            jogo = []
            nums_disp = self.numeros.copy()
            pesos_disp = np.array([probs[n] for n in nums_disp])
            pesos_disp = pesos_disp / sum(pesos_disp) if sum(pesos_disp) > 0 else np.ones(25)/25
            
            for _ in range(15):
                if len(nums_disp) > 0:
                    idx = np.random.choice(len(nums_disp), p=pesos_disp)
                    jogo.append(nums_disp[idx])
                    nums_disp = np.delete(nums_disp, idx)
                    if len(nums_disp) > 0:
                        pesos_disp = np.array([probs[n] for n in nums_disp])
                        pesos_disp = pesos_disp / sum(pesos_disp) if sum(pesos_disp) > 0 else np.ones(len(nums_disp))/len(nums_disp)
            
            jogo = sorted(jogo)
            score = sum(probs[n] for n in jogo) * 100
            
            pares = sum(1 for n in jogo if n % 2 == 0)
            if 6 <= pares <= 9:
                score += 10
            
            if len(melhores) < n_jogos:
                melhores.append(jogo)
                melhores_scores.append(score)
            else:
                idx_pior = np.argmin(melhores_scores)
                if score > melhores_scores[idx_pior]:
                    melhores[idx_pior] = jogo
                    melhores_scores[idx_pior] = score
        
        return [sorted(j) for j in melhores]
    
    # ============================================
    # ESTRATÉGIA 18: CORRELAÇÃO
    # ============================================
    def estrategia_correlacao(self, n_jogos=5):
        """Pares de números correlacionados"""
        if len(self.concursos) < 30:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        correlacoes = {}
        for num1 in self.numeros:
            for num2 in self.numeros:
                if num1 < num2:
                    juntos = 0
                    for concurso in self.concursos[:50]:
                        if num1 in concurso and num2 in concurso:
                            juntos += 1
                    
                    freq1 = sum(1 for c in self.concursos[:50] if num1 in c)
                    freq2 = sum(1 for c in self.concursos[:50] if num2 in c)
                    
                    if freq1 > 0 and freq2 > 0:
                        correlacao = juntos / ((freq1 * freq2) ** 0.5)
                        correlacoes[(num1, num2)] = correlacao
        
        pares_fortes = sorted(correlacoes.items(), key=lambda x: x[1], reverse=True)[:30]
        pares_sel = [list(p) for p, _ in pares_fortes[:15]]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = set()
            n_pares = random.randint(4, 6)
            for par in random.sample(pares_sel, min(n_pares, len(pares_sel))):
                jogo.update(par)
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.add(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 19: MÉDIAS MÓVEIS
    # ============================================
    def estrategia_medias_moveis(self, n_jogos=5, periodo=10):
        """Médias móveis para detectar tendências"""
        if len(self.concursos) < periodo + 5:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        medias = {}
        for num in self.numeros:
            aparicoes = []
            for concurso in self.concursos[:periodo]:
                aparicoes.append(1 if num in concurso else 0)
            if aparicoes:
                medias[num] = sum(aparicoes) / len(aparicoes)
        
        tendencia_alta = []
        for num in self.numeros:
            if num in medias:
                recentes = []
                for concurso in self.concursos[:5]:
                    recentes.append(1 if num in concurso else 0)
                media_recente = sum(recentes) / 5 if recentes else 0
                if media_recente > medias[num]:
                    tendencia_alta.append(num)
        
        jogos = []
        for _ in range(n_jogos):
            jogo = []
            n_alta = min(10, len(tendencia_alta))
            if tendencia_alta:
                jogo.extend(random.sample(tendencia_alta, n_alta))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 20: ENSEMBLE 2.0
    # ============================================
    def estrategia_ensemble_2(self, n_jogos=10):
        """Combinação otimizada das 9 melhores estratégias"""
        todas = [
            self.estrategia_janelas_moveis,
            self.estrategia_terminacoes,
            self.estrategia_ciclos_repeticao,
            self.estrategia_par_impar_avancada,
            self.estrategia_tendencia_temporal,
            self.estrategia_conjuntos_disjuntos,
            self.estrategia_monte_carlo,
            self.estrategia_correlacao,
            self.estrategia_medias_moveis
        ]
        
        pesos = [0.15, 0.12, 0.13, 0.10, 0.11, 0.09, 0.12, 0.08, 0.10]
        jogos = []
        jogos_por = max(1, n_jogos // len(todas))
        
        for i, est in enumerate(todas):
            try:
                n_extra = int(jogos_por * pesos[i] * 2)
                novos = est(jogos_por + n_extra)
                jogos.extend(novos)
            except:
                continue
        
        unicos = []
        seen = set()
        for jogo in jogos:
            chave = tuple(jogo)
            if chave not in seen and len(jogo) == 15:
                seen.add(chave)
                
                score = 0
                pares = sum(1 for n in jogo if n % 2 == 0)
                if 6 <= pares <= 9:
                    score += 10
                
                soma = sum(jogo)
                if 180 <= soma <= 200:
                    score += 10
                
                terminacoes = len(set(n % 10 for n in jogo))
                if terminacoes >= 5:
                    score += 5
                
                unicos.append((jogo, score))
        
        unicos.sort(key=lambda x: x[1], reverse=True)
        return [j for j, _ in unicos[:n_jogos]]
    
    # ============================================
    # ESTRATÉGIA BASE: ALEATÓRIA CONTROLADA
    # ============================================
    def estrategia_aleatoria_controlada(self, n_jogos=5):
        """Aleatória com validação básica"""
        jogos = []
        for _ in range(n_jogos * 2):
            jogo = sorted(random.sample(self.numeros, 15))
            pares = sum(1 for n in jogo if n % 2 == 0)
            soma = sum(jogo)
            
            if 5 <= pares <= 10 and 170 <= soma <= 210:
                if jogo not in jogos:
                    jogos.append(jogo)
            if len(jogos) >= n_jogos:
                break
        
        while len(jogos) < n_jogos:
            jogo = sorted(random.sample(self.numeros, 15))
            if jogo not in jogos:
                jogos.append(jogo)
        
        return jogos[:n_jogos]
    
    # ============================================
    # COMPARAR TODAS AS ESTRATÉGIAS
    # ============================================
    def comparar_todas_estrategias(self, n_jogos=5):
        """Compara todas as 20 estratégias"""
        if len(self.concursos) < 10:
            return {}
        
        resultados = {}
        todas = {
            '01. Frios (Lei dos Terços)': self.estrategia_frios_leidoterco,
            '02. Cobertura': self.estrategia_cobertura_garantida,
            '03. Soma Ótima': self.estrategia_soma_otima,
            '04. Grupos': self.estrategia_grupos,
            '05. Pareto': self.estrategia_pareto,
            '06. Espelhos': self.estrategia_espelhos,
            '07. Intervalos': self.estrategia_intervalos,
            '08. Wheeling': self.estrategia_wheeling,
            '09. Cíclica': self.estrategia_ciclica,
            '10. Ensemble 1.0': self.estrategia_ensemble,
            '11. Janelas Móveis': self.estrategia_janelas_moveis,
            '12. Terminações': self.estrategia_terminacoes,
            '13. Ciclos Repetição': self.estrategia_ciclos_repeticao,
            '14. Par/Ímpar Avançado': self.estrategia_par_impar_avancada,
            '15. Tendência Temporal': self.estrategia_tendencia_temporal,
            '16. Conjuntos Disjuntos': self.estrategia_conjuntos_disjuntos,
            '17. Monte Carlo': self.estrategia_monte_carlo,
            '18. Correlação': self.estrategia_correlacao,
            '19. Médias Móveis': self.estrategia_medias_moveis,
            '20. Ensemble 2.0': self.estrategia_ensemble_2,
        }
        
        concurso_teste = self.concursos[0]
        
        for nome, estrategia in todas.items():
            try:
                jogos = estrategia(min(n_jogos, 5))
                acertos = []
                for jogo in jogos:
                    if len(jogo) == 15:
                        acertos.append(len(set(jogo) & set(concurso_teste)))
                
                if acertos:
                    resultados[nome] = {
                        'media_acertos': np.mean(acertos),
                        'max_acertos': max(acertos),
                        'min_acertos': min(acertos),
                        'premiacoes': sum(1 for a in acertos if a >= 11),
                        'jogos_testados': len(acertos)
                    }
            except Exception as e:
                resultados[nome] = {
                    'media_acertos': 0,
                    'max_acertos': 0,
                    'min_acertos': 0,
                    'premiacoes': 0,
                    'jogos_testados': 0
                }
        
        return resultados


# ============================================
# INTERFACE STREAMLIT
# ============================================
def main():
    st.title("🎯 Lotofácil - 20 Estratégias Matemáticas Avançadas")
    
    st.markdown("""
    ## 📊 Estratégias Baseadas em Pesquisas 2024
    
    > **⚠️ AVISO**: Estas são estratégias de **ALOCAÇÃO**, não de previsão. 
    > A Lotofácil é 100% aleatória. Use estas técnicas para DIVERSIFICAR seus jogos.
    """)
    
    # Inicialização
    if 'concursos' not in st.session_state:
        st.session_state.concursos = []
    
    # Sidebar - Captura
    with st.sidebar:
        st.header("📥 Dados")
        qtd = st.slider("Quantidade de concursos", min_value=15, max_value=500, value=100, step=5)
        
        if st.button("🔄 Carregar Concursos", use_container_width=True):
            with st.spinner("Carregando..."):
                url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                try:
                    resp = requests.get(url, timeout=30)
                    if resp.status_code == 200:
                        dados = resp.json()
                        concursos = []
                        for i in range(min(qtd, len(dados))):
                            dezenas = sorted([int(d) for d in dados[i]['dezenas']])
                            concursos.append(dezenas)
                        st.session_state.concursos = concursos
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        if dados:
                            st.info(f"📅 Último: Concurso #{dados[0]['concurso']}")
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")
        
        if st.session_state.concursos:
            st.metric("Total em análise", len(st.session_state.concursos))
    
    # Main content
    if st.session_state.concursos and len(st.session_state.concursos) >= 15:
        # CRIA A INSTÂNCIA DA CLASSE CORRETA
        estrategias = EstrategiasLotofacil(st.session_state.concursos)
        
        tab1, tab2, tab3 = st.tabs([
            "🎲 Gerar Jogos", 
            "📊 Comparar Estratégias",
            "✅ Conferir Resultados"
        ])
        
        with tab1:
            st.header("🎲 Gerar Jogos com Estratégias")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                estrategia = st.selectbox(
                    "Selecione a Estratégia",
                    [
                        "01. Frios (Lei dos Terços)",
                        "02. Cobertura",
                        "03. Soma Ótima",
                        "04. Grupos",
                        "05. Pareto",
                        "06. Espelhos",
                        "07. Intervalos",
                        "08. Wheeling",
                        "09. Cíclica",
                        "10. Ensemble 1.0",
                        "11. Janelas Móveis",
                        "12. Terminações",
                        "13. Ciclos Repetição",
                        "14. Par/Ímpar Avançado",
                        "15. Tendência Temporal",
                        "16. Conjuntos Disjuntos",
                        "17. Monte Carlo",
                        "18. Correlação",
                        "19. Médias Móveis",
                        "20. Ensemble 2.0"
                    ]
                )
            
            with col2:
                n_jogos = st.number_input("Quantidade de Jogos", min_value=1, max_value=50, value=5)
            
            if st.button("🚀 Gerar Jogos", use_container_width=True):
                with st.spinner("Gerando combinações..."):
                    mapa = {
                        "01. Frios (Lei dos Terços)": estrategias.estrategia_frios_leidoterco,
                        "02. Cobertura": estrategias.estrategia_cobertura_garantida,
                        "03. Soma Ótima": estrategias.estrategia_soma_otima,
                        "04. Grupos": estrategias.estrategia_grupos,
                        "05. Pareto": estrategias.estrategia_pareto,
                        "06. Espelhos": estrategias.estrategia_espelhos,
                        "07. Intervalos": estrategias.estrategia_intervalos,
                        "08. Wheeling": estrategias.estrategia_wheeling,
                        "09. Cíclica": estrategias.estrategia_ciclica,
                        "10. Ensemble 1.0": estrategias.estrategia_ensemble,
                        "11. Janelas Móveis": estrategias.estrategia_janelas_moveis,
                        "12. Terminações": estrategias.estrategia_terminacoes,
                        "13. Ciclos Repetição": estrategias.estrategia_ciclos_repeticao,
                        "14. Par/Ímpar Avançado": estrategias.estrategia_par_impar_avancada,
                        "15. Tendência Temporal": estrategias.estrategia_tendencia_temporal,
                        "16. Conjuntos Disjuntos": estrategias.estrategia_conjuntos_disjuntos,
                        "17. Monte Carlo": estrategias.estrategia_monte_carlo,
                        "18. Correlação": estrategias.estrategia_correlacao,
                        "19. Médias Móveis": estrategias.estrategia_medias_moveis,
                        "20. Ensemble 2.0": estrategias.estrategia_ensemble_2,
                    }
                    
                    jogos = mapa[estrategia](n_jogos)
                    st.session_state['jogos_atuais'] = jogos
                    st.success(f"✅ {len(jogos)} jogos gerados!")
            
            if 'jogos_atuais' in st.session_state:
                st.subheader(f"📋 Jogos Gerados")
                
                for i, jogo in enumerate(st.session_state.jogos_atuais[:10], 1):
                    pares = sum(1 for n in jogo if n%2==0)
                    primos = sum(1 for n in jogo if n in estrategias.primos)
                    soma = sum(jogo)
                    
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**Jogo {i:2d}:** {jogo}")
                        with col2:
                            st.write(f"🎯 {pares}P/{15-pares}I")
                        with col3:
                            st.write(f"📊 {soma}")
                
                # Download
                conteudo = "\n".join([",".join(map(str, j)) for j in st.session_state.jogos_atuais])
                st.download_button(
                    "💾 Baixar Jogos (TXT)",
                    data=conteudo,
                    file_name=f"lotofacil_{len(st.session_state.jogos_atuais)}jogos.txt",
                    use_container_width=True
                )
        
        with tab2:
            st.header("📊 Comparação entre Estratégias")
            
            col1, col2 = st.columns(2)
            with col1:
                jogos_teste = st.slider("Jogos por estratégia", min_value=3, max_value=10, value=5)
            
            if st.button("🔬 Comparar Todas as 20 Estratégias", use_container_width=True):
                with st.spinner("Analisando estratégias..."):
                    resultados = estrategias.comparar_todas_estrategias(jogos_teste)
                    
                    if resultados:
                        df = pd.DataFrame(resultados).T
                        df = df.sort_values('media_acertos', ascending=False)
                        
                        st.subheader("🏆 Ranking de Performance")
                        
                        df_display = df.copy()
                        df_display['media_acertos'] = df_display['media_acertos'].round(2)
                        df_display['premiacoes'] = df_display['premiacoes'].astype(int)
                        
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Gráfico Top 10
                        fig, ax = plt.subplots(figsize=(12, 6))
                        top10 = df.head(10)
                        y_pos = range(len(top10))
                        ax.barh(y_pos, top10['media_acertos'])
                        ax.set_yticks(y_pos)
                        ax.set_yticklabels(top10.index)
                        ax.set_xlabel('Média de Acertos')
                        ax.set_title('Top 10 Estratégias - Média de Acertos')
                        
                        for i, v in enumerate(top10['media_acertos']):
                            ax.text(v + 0.1, i, f'{v:.1f}', va='center')
                        
                        st.pyplot(fig)
                        plt.close()
        
        with tab3:
            st.header("✅ Conferência de Resultados")
            
            if st.session_state.concursos:
                ultimo = st.session_state.concursos[0]
                st.info(f"**Último Concurso:** {ultimo}")
                
                if 'jogos_atuais' in st.session_state:
                    st.subheader("📝 Resultados dos Seus Jogos")
                    
                    resultados = []
                    for i, jogo in enumerate(st.session_state.jogos_atuais, 1):
                        acertos = len(set(jogo) & set(ultimo))
                        status = "🏆 SENA" if acertos >= 15 else "💰 QUINA" if acertos >= 14 else "🎯 QUADRA" if acertos >= 13 else "✨ TERNO" if acertos >= 12 else "⭐ DUQUE" if acertos >= 11 else "⚪ SEM PREMIAÇÃO"
                        
                        resultados.append({
                            'Jogo': i,
                            'Acertos': acertos,
                            'Status': status,
                            'Dezenas': str(jogo)
                        })
                    
                    df_res = pd.DataFrame(resultados)
                    st.dataframe(df_res, use_container_width=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Média de Acertos", f"{df_res['Acertos'].mean():.1f}")
                    with col2:
                        premiados = len(df_res[df_res['Acertos'] >= 11])
                        st.metric("Jogos Premiados", premiados)
                    with col3:
                        if premiados > 0:
                            st.metric("Maior Acerto", df_res['Acertos'].max())
    else:
        st.info("👈 **Carregue no mínimo 15 concursos no menu lateral**")
        st.markdown("""
        ### 🎯 20 Estratégias Disponíveis:
        
        **Estratégias Clássicas:**
        1. Lei dos Terços - Distribuição natural
        2. Cobertura - Máxima variedade
        3. Soma Ótima - Média histórica
        4. Grupos - Linhas da cartela
        5. Pareto - 80/20
        6. Espelhos - Complemento
        7. Intervalos - Gaps uniformes
        8. Wheeling - Sistema de roda
        9. Cíclica - Tendência recente
        10. Ensemble 1.0 - Combinação simples
        
        **Estratégias Avançadas 2024:**
        11. Janelas Móveis - Ciclos de repetição
        12. Terminações - Dígitos finais
        13. Ciclos de Repetição - Repetição programada
        14. Par/Ímpar Avançado - Proporção áurea
        15. Tendência Temporal - Momentum
        16. Conjuntos Disjuntos - Cobertura máxima
        17. Monte Carlo - Simulação probabilística
        18. Correlação - Pares correlacionados
        19. Médias Móveis - Suavização
        20. Ensemble 2.0 - Combinação otimizada
        """)

if __name__ == "__main__":
    main()
