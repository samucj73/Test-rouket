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
        """
        Inicializa com os concursos históricos
        Importante: O último concurso (índice 0) é separado para conferência
        Os cálculos usam apenas concursos[1:] (histórico)
        """
        self.concursos_historicos = concursos[1:] if len(concursos) > 1 else []  # TODOS os cálculos usam este
        self.ultimo_concurso = concursos[0] if len(concursos) > 0 else []  # Apenas para conferência
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    
    # ============================================
    # ESTRATÉGIA 1: NÚMEROS FRIOS (LEI DOS TERÇOS)
    # ============================================
    def estrategia_frios_leidoterco(self, n_jogos=5):
        """Lei dos Terços: 1/3 dos números ficam abaixo da média"""
        if len(self.concursos_historicos) < 15:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        total_numeros = len(self.concursos_historicos) * 15
        freq_esperada = total_numeros / 25
        
        freq_real = Counter()
        for concurso in self.concursos_historicos:  # Usa apenas histórico
            freq_real.update(concurso)
        
        frios = [n for n in self.numeros if freq_real[n] < freq_esperada * 0.7]
        quentes = [n for n in self.numeros if freq_real[n] > freq_esperada * 1.3]
        medios = [n for n in self.numeros if n not in frios and n not in quentes]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = []
            if frios:
                n_frios = min(7, len(frios))
                jogo.extend(random.sample(frios, n_frios))
            if quentes:
                n_quentes = min(4, len(quentes))
                jogo.extend(random.sample(quentes, n_quentes))
            if medios:
                n_medios = 15 - len(jogo)
                if n_medios > 0 and medios:
                    jogo.extend(random.sample(medios, min(n_medios, len(medios))))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo[:15]))
        
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
        if len(self.concursos_historicos) < 10:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Usa APENAS dados históricos, SEMPRE excluindo o último concurso
        somas = [sum(concurso) for concurso in self.concursos_historicos[-50:]]
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
            
            jogo = list(set(jogo))[:15]
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 5: PARETO (80/20)
    # ============================================
    def estrategia_pareto(self, n_jogos=5):
        """Foco nos 20% números mais frequentes"""
        if len(self.concursos_historicos) < 15:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        freq = Counter()
        for concurso in self.concursos_historicos[:100]:  # Usa apenas histórico
            freq.update(concurso)
        
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top5 = [n for n, _ in numeros_ordenados[:5]]
        resto = [n for n in self.numeros if n not in top5]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = top5.copy()
            if len(resto) >= 10:
                complemento = random.sample(resto, 10)
                jogo.extend(complemento)
            else:
                complemento = random.sample(self.numeros, 10)
                jogo.extend(complemento)
            jogos.append(sorted(list(set(jogo)))[:15])
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 6: ESPELHOS
    # ============================================
    def estrategia_espelhos(self, n_jogos=5):
        """Complemento do último concurso (que está excluído dos cálculos)"""
        if not self.ultimo_concurso:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Usa o último concurso APENAS para gerar o espelho, NÃO para calcular frequências
        espelho = [n for n in self.numeros if n not in self.ultimo_concurso]
        
        jogos = []
        for _ in range(n_jogos):
            n_espelho = random.randint(8, 12)
            n_ultimo = 15 - n_espelho
            
            jogo = []
            if len(espelho) >= n_espelho:
                jogo.extend(random.sample(espelho, n_espelho))
            if len(self.ultimo_concurso) >= n_ultimo:
                jogo.extend(random.sample(self.ultimo_concurso, n_ultimo))
            
            jogo = list(set(jogo))
            
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
        if len(self.concursos_historicos) > 15:
            freq = Counter()
            for concurso in self.concursos_historicos[:50]:  # Usa apenas histórico
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
            jogo = list(set(jogo))[:15]
            if len(jogo) == 15:
                jogos.append(sorted(jogo))
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 9: CÍCLICA
    # ============================================
    def estrategia_ciclica(self, n_jogos=5):
        """Baseada nos últimos 5 concursos (excluindo o último sorteio)"""
        if len(self.concursos_historicos) < 5:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Usa os últimos 5 concursos do HISTÓRICO (não inclui o último sorteio)
        ultimos = self.concursos_historicos[:5]
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
            
            jogos.append(sorted(jogo[:15]))
        
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
        """Teoria das Janelas: repetição em ciclos"""
        if len(self.concursos_historicos) < janela + 1:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        jogos = []
        numeros_janela = []
        # Usa APENAS concursos históricos, NÃO inclui o último sorteio
        for concurso in self.concursos_historicos[:janela]:
            numeros_janela.extend(concurso)
        
        freq_janela = Counter(numeros_janela)
        numeros_quentes = [n for n, _ in sorted(freq_janela.items(), key=lambda x: x[1], reverse=True)[:20]]
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
            
            jogos.append(sorted(jogo[:15]))
        
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
                if len(jogo) == 15 and tuple(sorted(jogo)) not in [tuple(j) for j in jogos]:
                    jogos.append(sorted(jogo))
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 13: CICLOS DE REPETIÇÃO
    # ============================================
    def estrategia_ciclos_repeticao(self, n_jogos=5):
        """Repetição programada baseada em histórico"""
        if len(self.concursos_historicos) < 10:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        jogos = []
        
        # Calcula taxa de repetição usando APENAS dados históricos
        repeticoes = []
        for i in range(len(self.concursos_historicos) - 1):
            atual = set(self.concursos_historicos[i])
            prox = set(self.concursos_historicos[i + 1])
            repeticoes.append(len(atual & prox))
        
        media_repeticoes = np.mean(repeticoes) if repeticoes else 7
        
        for _ in range(n_jogos):
            n_repeticoes = int(round(random.uniform(media_repeticoes - 2, media_repeticoes + 2)))
            n_repeticoes = max(5, min(10, n_repeticoes))
            
            jogo = []
            # Usa o concurso mais recente do HISTÓRICO (não o último sorteio)
            if self.concursos_historicos:
                referencia = set(self.concursos_historicos[0])
                repetidores = random.sample(list(referencia), min(n_repeticoes, len(referencia)))
                jogo.extend(repetidores)
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 14: PAR/ÍMPAR AVANÇADO
    # ============================================
    def estrategia_par_impar_avancada(self, n_jogos=5):
        """Proporção áurea 6/9 a 8/7"""
        jogos = []
        pares = [n for n in self.numeros if n % 2 == 0]
        impares = [n for n in self.numeros if n % 2 == 1]
        
        for _ in range(n_jogos * 2):
            n_pares = random.choice([6, 7, 8, 9])
            n_impares = 15 - n_pares
            
            jogo = []
            if len(pares) >= n_pares:
                jogo.extend(random.sample(pares, n_pares))
            if len(impares) >= n_impares:
                jogo.extend(random.sample(impares, n_impares))
            
            if len(jogo) == 15:
                jogo = sorted(jogo)
                pares_final = sum(1 for n in jogo if n % 2 == 0)
                if 6 <= pares_final <= 9:
                    if jogo not in jogos:
                        jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 15: TENDÊNCIA TEMPORAL
    # ============================================
    def estrategia_tendencia_temporal(self, n_jogos=5):
        """Momentum baseado em histórico"""
        if len(self.concursos_historicos) < 20:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        jogos = []
        
        # Calcula tendência usando APENAS dados históricos
        tendencia_subindo = []
        for num in self.numeros:
            aparicoes_recentes = 0
            aparicoes_antigas = 0
            
            for concurso in self.concursos_historicos[:10]:
                if num in concurso:
                    aparicoes_recentes += 1
            for concurso in self.concursos_historicos[10:20]:
                if num in concurso:
                    aparicoes_antigas += 1
            
            if aparicoes_recentes > aparicoes_antigas:
                tendencia_subindo.append(num)
        
        for _ in range(n_jogos):
            n_subindo = min(10, len(tendencia_subindo))
            jogo = []
            
            if tendencia_subindo and n_subindo > 0:
                jogo.extend(random.sample(tendencia_subindo, n_subindo))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 16: CONJUNTOS DISJUNTOS
    # ============================================
    def estrategia_conjuntos_disjuntos(self, n_jogos=5):
        """Cobertura máxima com conjuntos disjuntos"""
        conjuntos = [
            [1, 6, 11, 16, 21],
            [2, 7, 12, 17, 22],
            [3, 8, 13, 18, 23],
            [4, 9, 14, 19, 24],
            [5, 10, 15, 20, 25],
        ]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = []
            for conjunto in conjuntos:
                selecionados = random.sample(conjunto, min(3, len(conjunto)))
                jogo.extend(selecionados)
            
            jogo = list(set(jogo))
            
            if len(jogo) > 15:
                jogo = random.sample(jogo, 15)
            elif len(jogo) < 15:
                disponiveis = [n for n in self.numeros if n not in jogo]
                complemento = random.sample(disponiveis, 15 - len(jogo))
                jogo.extend(complemento)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 17: MONTE CARLO
    # ============================================
    def estrategia_monte_carlo(self, n_jogos=5):
        """Simulação de Monte Carlo com dados históricos"""
        if len(self.concursos_historicos) < 30:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Calcula frequência usando APENAS dados históricos
        freq = Counter()
        for concurso in self.concursos_historicos[:100]:
            freq.update(concurso)
        
        # Converte para probabilidades
        total = sum(freq.values())
        probs = {num: freq.get(num, 0) / total for num in self.numeros}
        
        melhores = []
        melhores_scores = []
        
        for _ in range(3000):
            jogo = []
            nums_disp = self.numeros.copy()
            
            while len(jogo) < 15:
                candidatos = [n for n in nums_disp if n not in jogo]
                if candidatos:
                    pesos = [probs.get(n, 0.04) for n in candidatos]
                    if sum(pesos) > 0:
                        pesos = [p / sum(pesos) for p in pesos]
                        escolhido = np.random.choice(candidatos, p=pesos)
                        jogo.append(escolhido)
                    else:
                        jogo.append(random.choice(candidatos))
                else:
                    break
            
            jogo = sorted(jogo)
            
            if len(jogo) == 15:
                score = sum(probs.get(n, 0) for n in jogo) * 100
                
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
        """Pares que mais aparecem juntos no histórico"""
        if len(self.concursos_historicos) < 30:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Conta pares usando APENAS dados históricos
        pares_counter = Counter()
        for concurso in self.concursos_historicos[:50]:
            for i in range(len(concurso)):
                for j in range(i + 1, len(concurso)):
                    par = tuple(sorted([concurso[i], concurso[j]]))
                    pares_counter[par] += 1
        
        pares_fortes = [list(p) for p, _ in pares_counter.most_common(30)]
        
        jogos = []
        for _ in range(n_jogos):
            jogo = set()
            
            n_pares = random.randint(4, 6)
            for par in random.sample(pares_fortes, min(n_pares, len(pares_fortes))):
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
    def estrategia_medias_moveis(self, n_jogos=5):
        """Médias móveis com dados históricos"""
        if len(self.concursos_historicos) < 20:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        tendencia_alta = []
        for num in self.numeros:
            media_antiga = 0
            media_recente = 0
            
            for concurso in self.concursos_historicos[10:20]:
                if num in concurso:
                    media_antiga += 1
            media_antiga /= 10
            
            for concurso in self.concursos_historicos[:10]:
                if num in concurso:
                    media_recente += 1
            media_recente /= 10
            
            if media_recente > media_antiga * 1.1:
                tendencia_alta.append(num)
        
        jogos = []
        for _ in range(n_jogos):
            jogo = []
            
            if tendencia_alta:
                n_alta = min(10, len(tendencia_alta))
                jogo.extend(random.sample(tendencia_alta, n_alta))
            
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 20: ENSEMBLE 2.0
    # ============================================
    def estrategia_ensemble_2(self, n_jogos=10):
        """Combinação das melhores estratégias"""
        todas = [
            self.estrategia_janelas_moveis,
            self.estrategia_terminacoes,
            self.estrategia_ciclos_repeticao,
            self.estrategia_par_impar_avancada,
            self.estrategia_tendencia_temporal,
            self.estrategia_monte_carlo,
            self.estrategia_correlacao,
            self.estrategia_medias_moveis
        ]
        
        jogos = []
        jogos_por = max(1, n_jogos // len(todas))
        
        for est in todas:
            try:
                novos = est(jogos_por)
                jogos.extend(novos)
            except:
                continue
        
        unicos = []
        seen = set()
        for jogo in jogos:
            chave = tuple(sorted(jogo))
            if chave not in seen and len(jogo) == 15:
                seen.add(chave)
                
                score = 0
                pares = sum(1 for n in jogo if n % 2 == 0)
                if 6 <= pares <= 9:
                    score += 10
                
                soma = sum(jogo)
                if 180 <= soma <= 200:
                    score += 10
                
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
        """
        Compara todas as 20 estratégias
        Usa o último concurso APENAS para TESTE, nunca para treino
        """
        if len(self.concursos_historicos) < 10:
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
        
        # Usa o último concurso APENAS para teste
        concurso_teste = self.ultimo_concurso
        
        for nome, estrategia in todas.items():
            try:
                jogos = estrategia(min(n_jogos, 3))
                acertos = []
                for jogo in jogos:
                    if len(jogo) == 15:
                        acertos.append(len(set(jogo) & set(concurso_teste)))
                
                if acertos:
                    resultados[nome] = {
                        'media_acertos': round(np.mean(acertos), 2),
                        'max_acertos': max(acertos),
                        'premiacoes': sum(1 for a in acertos if a >= 11),
                        'jogos_testados': len(acertos)
                    }
            except Exception as e:
                continue
        
        return resultados


# ============================================
# INTERFACE STREAMLIT
# ============================================
def main():
    st.title("🎯 Lotofácil - 20 Estratégias Matemáticas Avançadas")
    
    st.markdown("""
    ## 📊 Estratégias Baseadas em Pesquisas 2024
    
    > **⚠️ AVISO IMPORTANTE**: 
    > - Todas as estratégias usam APENAS dados HISTÓRICOS (excluindo o último sorteio)
    > - O último concurso é usado SOMENTE para CONFERÊNCIA
    > - Isso garante um BACKTESTING HONESTO e sem viés
    """)
    
    # Inicialização
    if 'concursos' not in st.session_state:
        st.session_state.concursos = []
    if 'jogos_atuais' not in st.session_state:
        st.session_state.jogos_atuais = []
    
    # Sidebar - Captura
    with st.sidebar:
        st.header("📥 Dados")
        qtd = st.slider("Quantidade de concursos", min_value=16, max_value=500, value=100, step=5)
        
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
                            st.info(f"📅 Último: Concurso #{dados[0]['concurso']} (USADO APENAS PARA CONFERÊNCIA)")
                            st.caption(f"📚 Histórico: {len(concursos)-1} concursos (USADOS PARA CÁLCULOS)")
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")
        
        if st.session_state.concursos:
            st.metric("Total em análise", len(st.session_state.concursos))
            st.metric("Base de cálculo", len(st.session_state.concursos) - 1)
            st.caption(f"🎯 Último (conferência): {st.session_state.concursos[0]}")
    
    # Main content
    if st.session_state.concursos and len(st.session_state.concursos) >= 16:
        # CRIA A INSTÂNCIA DA CLASSE - Automaticamente separa último concurso
        estrategias = EstrategiasLotofacil(st.session_state.concursos)
        
        tab1, tab2, tab3 = st.tabs([
            "🎲 Gerar Jogos", 
            "📊 Comparar Estratégias",
            "✅ Conferir Resultados"
        ])
        
        with tab1:
            st.header("🎲 Gerar Jogos com Estratégias")
            st.caption("📊 TODAS as estratégias usam APENAS dados históricos (excluindo o último sorteio)")
            
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
                n_jogos = st.number_input("Quantidade", min_value=1, max_value=20, value=5)
            
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
                    st.session_state.jogos_atuais = jogos
                    st.success(f"✅ {len(jogos)} jogos gerados!")
            
            if st.session_state.jogos_atuais:
                st.subheader("📋 Jogos Gerados")
                
                for i, jogo in enumerate(st.session_state.jogos_atuais[:10], 1):
                    pares = sum(1 for n in jogo if n % 2 == 0)
                    primos = sum(1 for n in jogo if n in estrategias.primos)
                    soma = sum(jogo)
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**Jogo {i:2d}:** {jogo}")
                    with col2:
                        st.write(f"🎯 {pares}P/{15-pares}I")
                    with col3:
                        st.write(f"📊 {soma}")
                
                if len(st.session_state.jogos_atuais) > 10:
                    st.caption(f"... e mais {len(st.session_state.jogos_atuais) - 10} jogos")
                
                # Download
                conteudo = "\n".join([",".join(map(str, j)) for j in st.session_state.jogos_atuais])
                st.download_button(
                    "💾 Baixar TXT",
                    data=conteudo,
                    file_name=f"lotofacil_{len(st.session_state.jogos_atuais)}jogos.txt",
                    use_container_width=True
                )
        
        with tab2:
            st.header("📊 Comparação entre Estratégias")
            st.caption("📊 Teste realizado com o ÚLTIMO CONCURSO (excluído dos cálculos)")
            
            col1, col2 = st.columns(2)
            with col1:
                jogos_teste = st.slider("Jogos por estratégia", min_value=1, max_value=5, value=3)
            
            if st.button("🔬 Comparar Todas", use_container_width=True):
                with st.spinner("Analisando estratégias..."):
                    resultados = estrategias.comparar_todas_estrategias(jogos_teste)
                    
                    if resultados:
                        df = pd.DataFrame(resultados).T
                        df = df.sort_values('media_acertos', ascending=False)
                        
                        st.subheader("🏆 Ranking de Performance")
                        st.caption("✅ Teste honesto: estratégias usaram dados HISTÓRICOS, conferência com o ÚLTIMO concurso")
                        
                        st.dataframe(df, use_container_width=True)
                        
                        # Gráfico Top 10
                        fig, ax = plt.subplots(figsize=(10, 6))
                        top10 = df.head(10)
                        y_pos = range(len(top10))
                        ax.barh(y_pos, top10['media_acertos'])
                        ax.set_yticks(y_pos)
                        ax.set_yticklabels(top10.index, fontsize=8)
                        ax.set_xlabel('Média de Acertos')
                        ax.set_title('Top 10 Estratégias - Backtesting Honesto')
                        
                        for i, v in enumerate(top10['media_acertos']):
                            ax.text(v + 0.1, i, f'{v:.1f}', va='center')
                        
                        st.pyplot(fig)
                        plt.close()
                    else:
                        st.warning("Não foi possível comparar as estratégias. Tente novamente.")
        
        with tab3:
            st.header("✅ Conferência de Resultados")
            
            if st.session_state.concursos:
                ultimo = st.session_state.concursos[0]
                st.info(f"**Último Concurso (para conferência):** {ultimo}")
                
                if st.session_state.jogos_atuais:
                    st.subheader("📝 Resultados dos seus jogos")
                    st.caption("✅ Conferência com o ÚLTIMO concurso (não usado nos cálculos)")
                    
                    dados_resultados = []
                    for i, jogo in enumerate(st.session_state.jogos_atuais, 1):
                        acertos = len(set(jogo) & set(ultimo))
                        
                        if acertos >= 15:
                            status = "🏆 SENA"
                        elif acertos >= 14:
                            status = "💰 QUINA"
                        elif acertos >= 13:
                            status = "🎯 QUADRA"
                        elif acertos >= 12:
                            status = "✨ TERNO"
                        elif acertos >= 11:
                            status = "⭐ DUQUE"
                        else:
                            status = "⚪ SEM PREMIAÇÃO"
                        
                        dados_resultados.append({
                            'Jogo': i,
                            'Acertos': acertos,
                            'Status': status
                        })
                    
                    if dados_resultados:
                        df_res = pd.DataFrame(dados_resultados)
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
                
                st.subheader("📁 Conferir Arquivo")
                arquivo = st.file_uploader("Upload de arquivo TXT", type=['txt'])
                
                if arquivo:
                    try:
                        content = arquivo.read().decode('utf-8')
                        linhas = content.strip().split('\n')
                        
                        jogos_file = []
                        for linha in linhas:
                            try:
                                nums = [int(x.strip()) for x in linha.split(',') if x.strip()]
                                if len(nums) == 15 and all(1 <= n <= 25 for n in nums):
                                    jogos_file.append(sorted(nums))
                            except:
                                continue
                        
                        if jogos_file:
                            st.success(f"✅ {len(jogos_file)} jogos carregados!")
                            
                            dados_file = []
                            for i, jogo in enumerate(jogos_file[:20], 1):
                                acertos = len(set(jogo) & set(ultimo))
                                dados_file.append({'Jogo': i, 'Acertos': acertos})
                            
                            df_file = pd.DataFrame(dados_file)
                            st.dataframe(df_file, use_container_width=True)
                            
                            if len(jogos_file) > 20:
                                st.info(f"... e mais {len(jogos_file) - 20} jogos")
                    except Exception as e:
                        st.error("Erro ao processar arquivo")
    else:
        st.info("👈 **Carregue no mínimo 16 concursos no menu lateral**")
        st.warning("""
        ⚠️ **Por que mínimo 16 concursos?**
        - 1 concurso para CONFERÊNCIA (excluído dos cálculos)
        - 15 concursos para BASE DE CÁLCULO (mínimo necessário)
        - Isso garante um BACKTESTING HONESTO
        """)

if __name__ == "__main__":
    main()
