
# =====================================================
# LOTOFÁCIL AI 2.0 - VERSÃO CORRIGIDA
# Correções aplicadas sem alterar a estrutura original
# =====================================================

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

# =====================================================
# CLASSE BASE: DISTRIBUIÇÕES PROBABILÍSTICAS
# =====================================================

class DistribuicoesProbabilisticas:

    def __init__(self, historico):
        self.historico = historico
        self.total = len(historico)

        self.dist_baixas = self._calcular_distribuicao(lambda j: sum(1 for n in j if n <= 8))
        self.dist_medias = self._calcular_distribuicao(lambda j: sum(1 for n in j if 9 <= n <= 16))
        self.dist_altas = self._calcular_distribuicao(lambda j: sum(1 for n in j if 17 <= n <= 25))
        self.dist_pares = self._calcular_distribuicao(lambda j: sum(1 for n in j if n % 2 == 0))
        self.dist_primos = self._calcular_distribuicao(lambda j: sum(1 for n in j if n in {2,3,5,7,11,13,17,19,23}))
        self.dist_soma = self._calcular_distribuicao(sum, bins=10)
        self.dist_consecutivos = self._calcular_distribuicao(self._contar_consecutivos)
        self.dist_repeticoes = self._calcular_repeticoes()

        self.freq_individual = self._calcular_frequencias_individuais()

    def _contar_consecutivos(self, jogo):
        jogo_sorted = sorted(jogo)
        return sum(1 for i in range(len(jogo_sorted)-1) if jogo_sorted[i+1] == jogo_sorted[i] + 1)

    def _calcular_distribuicao(self, func, bins=None):

        valores = [func(j) for j in self.historico]

        if bins:
            min_val, max_val = min(valores), max(valores)
            bin_edges = np.linspace(min_val, max_val, bins + 1)

            # CORREÇÃO digitize
            binned = np.clip(np.digitize(valores, bin_edges[:-1]), 1, bins)

            distrib = {}
            for i in range(1, bins + 1):
                count = sum(1 for b in binned if b == i)
                distrib[f"{bin_edges[i-1]:.0f}-{bin_edges[i]:.0f}"] = count / self.total
            return distrib

        counter = Counter(valores)
        return {k: v/self.total for k, v in counter.items()}

    def _calcular_repeticoes(self):

        repeticoes = []
        for i in range(len(self.historico)-1):
            rep = len(set(self.historico[i]) & set(self.historico[i+1]))
            repeticoes.append(rep)

        counter = Counter(repeticoes)
        return {k: v/len(repeticoes) for k, v in counter.items()}

    def _calcular_frequencias_individuais(self):

        counter = Counter()
        for jogo in self.historico:
            counter.update(jogo)

        return {n: counter[n] / (self.total * 15) for n in range(1, 26)}

    def probabilidade_jogo(self, jogo):

        log_prob = 0
        eps = 1e-10

        baixas = sum(1 for n in jogo if n <= 8)
        medias = sum(1 for n in jogo if 9 <= n <= 16)
        altas = sum(1 for n in jogo if 17 <= n <= 25)
        pares = sum(1 for n in jogo if n % 2 == 0)
        primos = sum(1 for n in jogo if n in {2,3,5,7,11,13,17,19,23})
        soma = sum(jogo)
        consec = self._contar_consecutivos(jogo)

        log_prob += math.log(self.dist_baixas.get(baixas, eps) + eps)
        log_prob += math.log(self.dist_medias.get(medias, eps) + eps)
        log_prob += math.log(self.dist_altas.get(altas, eps) + eps)
        log_prob += math.log(self.dist_pares.get(pares, eps) + eps)
        log_prob += math.log(self.dist_primos.get(primos, eps) + eps)

        soma_bin = None
        for bin_range in self.dist_soma.keys():
            low, high = map(float, bin_range.split('-'))
            if low <= soma <= high:
                soma_bin = bin_range
                break

        if soma_bin:
            log_prob += math.log(self.dist_soma.get(soma_bin, eps) + eps)

        log_prob += math.log(self.dist_consecutivos.get(consec, eps) + eps)

        # NORMALIZAÇÃO
        return log_prob / 7

# =====================================================
# GERADOR ALEATÓRIO (BASELINE PARA BACKTEST)
# =====================================================

class GeradorAleatorio:

    def __init__(self, historico):
        self.historico = historico

    def gerar_multiplos_jogos(self, quantidade):
        jogos = []
        for _ in range(quantidade):
            jogos.append(sorted(random.sample(range(1,26),15)))
        return jogos

# =====================================================
# GERADOR PROBABILÍSTICO
# =====================================================

class GeradorProbabilistico:

    def __init__(self, distribuicoes):
        self.dist = distribuicoes
        self.historico = distribuicoes.historico

    def _amostrar_feature(self, dist):
        valores = list(dist.keys())
        probs = list(dist.values())
        return np.random.choice(valores, p=probs)

    def _gerar_jogo_por_distribuicoes(self):

        max_tentativas = 10000

        for _ in range(max_tentativas):

            alvo_baixas = self._amostrar_feature(self.dist.dist_baixas)
            alvo_medias = self._amostrar_feature(self.dist.dist_medias)
            alvo_altas = self._amostrar_feature(self.dist.dist_altas)

            total = alvo_baixas + alvo_medias + alvo_altas

            if total > 15:
                continue

            if total < 15:
                alvo_altas += (15 - total)

            jogo = []

            jogo.extend(random.sample(range(1,9), alvo_baixas))
            jogo.extend(random.sample(range(9,17), alvo_medias))
            jogo.extend(random.sample(range(17,26), alvo_altas))

            jogo.sort()

            return jogo

        return None

# =====================================================
# MACHINE LEARNING
# =====================================================

class GeradorML:

    def __init__(self, historico):
        self.historico = historico
        self.modelo = None

    def treinar(self, janela_treino=100):

        X = []
        y = []

        for i in range(janela_treino, len(self.historico)-1):

            treino = self.historico[i-janela_treino:i]

            # REDUÇÃO DE CARGA
            for _ in range(40):

                jogo = sorted(random.sample(range(1,26),15))

                features = [
                    sum(1 for n in jogo if n<=8),
                    sum(1 for n in jogo if n%2==0),
                    sum(jogo)
                ]

                futuro = self.historico[i+1]
                acertos = len(set(jogo)&set(futuro))

                X.append(features)
                y.append(1 if acertos>=12 else 0)

        X = np.array(X)
        y = np.array(y)

        self.modelo = GradientBoostingClassifier()
        self.modelo.fit(X,y)

        y_pred = self.modelo.predict(X)
        acc = accuracy_score(y,y_pred)

        return acc

# =====================================================
# BACKTESTING
# =====================================================

class BacktestingEngine:

    def __init__(self, historico):
        self.historico = historico

    def walk_forward_test(self, gerador_class, janela_treino=100, jogos_por_teste=10, passos=20):

        resultados = []
        acertos_13 = 0
        total = 0

        for idx in range(janela_treino, janela_treino+passos):

            treino = self.historico[:idx]
            real = self.historico[idx]

            if gerador_class:
                gerador = gerador_class(treino)
                jogos = gerador.gerar_multiplos_jogos(jogos_por_teste)
            else:
                jogos = [sorted(random.sample(range(1,26),15)) for _ in range(jogos_por_teste)]

            for jogo in jogos:
                acertos = len(set(jogo)&set(real))

                resultados.append(acertos)
                total += 1

                if acertos>=13:
                    acertos_13+=1

        return {
            "media": np.mean(resultados),
            "max": max(resultados),
            "p13": acertos_13/total
        }

# =====================================================
# INTERFACE STREAMLIT
# =====================================================

def main():

    st.title("🧠🎯 LOTOFÁCIL AI 2.0")

    if "historico" not in st.session_state:
        st.session_state.historico=None

    if st.button("📥 Carregar concursos"):

        # API OFICIAL (CORRIGIDA)
        url="https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"

        try:
            data=requests.get(url).json()

            jogos=[]
            for c in data["listaResultados"]:
                jogos.append(sorted(map(int,c["listaDezenas"])))

            st.session_state.historico=jogos
            st.success("Concursos carregados")

        except:
            st.error("Erro ao carregar API")

    if st.session_state.historico is None:
        st.warning("Carregue os concursos primeiro")
        return

    st.write("Total concursos:",len(st.session_state.historico))

    if st.button("🚀 Treinar ML"):

        ml=GeradorML(st.session_state.historico)
        acc=ml.treinar()

        st.success(f"Acurácia treino {acc:.2%}")

# =====================================================
# EXECUÇÃO
# =====================================================

if __name__=="__main__":
    main()
