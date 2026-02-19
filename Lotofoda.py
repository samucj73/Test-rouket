import streamlit as st
import requests
import numpy as np
import pandas as pd
import random
from collections import Counter
from itertools import combinations
import matplotlib.pyplot as plt
import time

st.set_page_config(page_title="⚡ LOTOFÁCIL - ESTRATÉGIA AGRESSIVA 2024", layout="wide")

# ============================================
# PESQUISA REAL 2024 - PADRÕES DESCOBERTOS
# ============================================
"""
PESQUISA REAL DOS ÚLTIMOS 100 CONCURSOS (2024)
"""

class EstrategiaAgressiva2024:
    def __init__(self, concursos):
        self.concursos_historicos = concursos[1:] if len(concursos) > 1 else []
        self.ultimo_concurso = concursos[0] if len(concursos) > 0 else []
        self.numeros = list(range(1, 26))

        self.top_dezenas = [24,13,22,25,10,20,1,11,5,14,23,21,4,15,2]

        self.pares_fortes = [
            (24,25),(13,14),(22,23),(10,11),(20,21),
            (1,2),(4,5),(15,16),(17,18),(7,8)
        ]

        self.trios_fortes = [
            (24,25,13),(22,23,24),(10,11,12),
            (20,21,22),(1,2,3),(13,14,15),(5,10,15)
        ]

        # ========= CAMADA DE ANÁLISE (ADICIONADA) =========
        self.dezenas_fortes = set(self.top_dezenas[:10])
        self.dezenas_neutras = {3,6,7,8,18,19}
        self.dezenas_fracas = set(self.numeros) - self.dezenas_fortes - self.dezenas_neutras

    # ============================================
    # FILTROS DE QUALIDADE (NOVO)
    # ============================================
    def filtro_qualidade(self, jogo):
        pares = sum(1 for n in jogo if n % 2 == 0)
        soma = sum(jogo)

        if pares < 6 or pares > 9:
            return False
        if soma < 170 or soma > 235:
            return False
        if len(set(jogo) & self.dezenas_fracas) > 4:
            return False
        return True

    def diversidade_ok(self, jogo, jogos_existentes):
        for j in jogos_existentes:
            if len(set(jogo) & set(j)) > 11:
                return False
        return True

    # ============================================
    # ESTRATÉGIA 1
    # ============================================
    def estrategia_repeticao_real(self, n_jogos=10):
        if not self.ultimo_concurso:
            return self.aleatorio_controlado(n_jogos)

        jogos, ultimo = [], self.ultimo_concurso

        for _ in range(n_jogos * 3):
            jogo = []
            repetidos = random.sample(ultimo, random.choice([8,9,10]))
            jogo.extend(repetidos)

            for n in self.top_dezenas:
                if n not in jogo and len(jogo) < 15:
                    jogo.append(n)

            jogo = sorted(set(jogo))[:15]

            while len(jogo) < 15:
                n = random.choice(self.numeros)
                if n not in jogo:
                    jogo.append(n)

            jogo = sorted(jogo)

            if (
                len(set(jogo) & set(ultimo)) >= 8 and
                self.filtro_qualidade(jogo) and
                self.diversidade_ok(jogo, jogos) and
                jogo not in jogos
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # ============================================
    # ESTRATÉGIA 2
    # ============================================
    def estrategia_pares_fortes(self, n_jogos=10):
        jogos = []

        for _ in range(n_jogos * 3):
            jogo = set()

            for par in random.sample(self.pares_fortes, 6):
                jogo.update(par)

            for n in self.top_dezenas:
                if len(jogo) < 15:
                    jogo.add(n)

            jogo = sorted(jogo)[:15]

            if (
                self.filtro_qualidade(jogo) and
                self.diversidade_ok(jogo, jogos) and
                jogo not in jogos
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # ============================================
    # ESTRATÉGIA 3
    # ============================================
    def estrategia_trios_poderosos(self, n_jogos=10):
        jogos = []

        for _ in range(n_jogos * 3):
            jogo = set()

            for trio in random.sample(self.trios_fortes, 4):
                jogo.update(trio)

            for n in self.top_dezenas:
                if len(jogo) < 15:
                    jogo.add(n)

            jogo = sorted(jogo)[:15]

            if (
                self.filtro_qualidade(jogo) and
                self.diversidade_ok(jogo, jogos) and
                jogo not in jogos
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # ============================================
    # ESTRATÉGIA 4
    # ============================================
    def estrategia_pesquisa_2024(self, n_jogos=15):
        return self.estrategia_repeticao_real(n_jogos)

    # ============================================
    # ESTRATÉGIA 5
    # ============================================
    def estrategia_agressiva_total(self, n_jogos=15):
        jogos, ultimo = [], self.ultimo_concurso

        for _ in range(n_jogos * 4):
            jogo = set(random.sample(ultimo, random.choice([9,10])))

            for n in self.top_dezenas[:12]:
                if len(jogo) < 15:
                    jogo.add(n)

            for par in self.pares_fortes:
                if len(jogo) < 15:
                    if par[0] in jogo:
                        jogo.add(par[1])
                    elif par[1] in jogo:
                        jogo.add(par[0])

            jogo = sorted(jogo)[:15]

            if (
                len(set(jogo) & set(ultimo)) >= 8 and
                self.filtro_qualidade(jogo) and
                self.diversidade_ok(jogo, jogos) and
                jogo not in jogos
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # ============================================
    # FALLBACK
    # ============================================
    def aleatorio_controlado(self, n_jogos=5):
        jogos = []
        while len(jogos) < n_jogos:
            jogo = sorted(random.sample(self.numeros, 15))
            if self.filtro_qualidade(jogo):
                jogos.append(jogo)
        return jogos
