import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL PREMIUM",
    layout="centered"
)

# =====================================================
# FUNÇÃO SEGURA (ANTI-ERRO)
# =====================================================
def sample_safe(lista, n):
    if not lista:
        return []
    return random.sample(lista, min(n, len(lista)))

# =====================================================
# CLASSE PRINCIPAL
# =====================================================
class AnaliseLotofacilAvancada:

    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0]
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)

        self.frequencias = self._frequencias()

    # ================= ESTATÍSTICA =================
    def _frequencias(self):
        c = Counter()
        for con in self.concursos:
            c.update(con)
        return c

    def classificar_numeros(self):
        freq_ord = sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)
        quentes = [n for n,_ in freq_ord[:15]]
        frios = [n for n,_ in freq_ord[-10:]]
        medios = [n for n,_ in freq_ord[15:-10]]
        return quentes, medios, frios

    def tem_sequencia(self, jogo):
        jogo = sorted(jogo)
        return any(jogo[i+1] == jogo[i] + 1 for i in range(len(jogo)-1))

    # ================= FECHAMENTO =================
    def gerar_fechamento(self, tamanho):
        freq_ord = sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)
        return sorted([n for n,_ in freq_ord[:tamanho]])

    # ================= JOGOS 15 =================
    def gerar_subjogos(self, fechamento, qtd):
        jogos = set()
        quentes, medios, frios = self.classificar_numeros()
        ultimo = set(self.ultimo_concurso)

        while len(jogos) < qtd:
            jogo = set()

            jogo |= set(sample_safe(list(ultimo), random.randint(8, 10)))
            jogo |= set(sample_safe(quentes, 7))
            jogo |= set(sample_safe(medios, 4))
            jogo |= set(sample_safe(frios, 2))

            jogo = list(jogo)

            if len(jogo) > 15:
                jogo = random.sample(jogo, 15)
            elif len(jogo) < 15:
                comp = [n for n in fechamento if n not in jogo]
                jogo += sample_safe(comp, 15 - len(jogo))

            if 180 <= sum(jogo) <= 220 and self.tem_sequencia(jogo):
                jogos.add(tuple(sorted(jogo)))

        return [list(j) for j in jogos]

    # ================= DESDOBRAMENTO =================
    def desdobrar_base(self, base, qtd):
        jogos = set()
        quentes, medios, frios = self.classificar_numeros()
        ultimo = set(self.ultimo_concurso)

        while len(jogos) < qtd:
            jogo = set()

            jogo |= set(sample_safe(list(ultimo & set(base)), random.randint(7, 9)))
            jogo |= set(sample_safe([n for n in base if n in quentes], 6))
            jogo |= set(sample_safe([n for n in base if n in medios], 5))
            jogo |= set(sample_safe([n for n in base if n in frios], 2))

            jogo = list(jogo)

            if len(jogo) > 15:
                jogo = random.sample(jogo, 15)
            elif len(jogo) < 15:
                comp = [n for n in base if n not in jogo]
                jogo += sample_safe(comp, 15 - len(jogo))

            if 180 <= sum(jogo) <= 220 and self.tem_sequencia(jogo):
                jogos.add(tuple(sorted(jogo)))

        return [list(j) for j in jogos]

# =====================================================
# INTERFACE
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL PREMIUM")

    if "analise" not in st.session_state:
        st.session_state.analise = None

    if st.button("📥 Carregar concursos"):
        url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
        data = requests.get(url).json()
        concursos = [sorted(map(int, d["dezenas"])) for d in data[:200]]
        st.session_state.analise = AnaliseLotofacilAvancada(concursos)
        st.success("Concursos carregados")

    if st.session_state.analise:
        modo = st.radio("Modo", ["Fechamento", "Desdobramento"], horizontal=True)

        if modo == "Fechamento":
            base = st.session_state.analise.gerar_fechamento(17)
            jogos = st.session_state.analise.gerar_subjogos(base, 6)
        else:
            base = st.session_state.analise.gerar_fechamento(19)
            jogos = st.session_state.analise.desdobrar_base(base, 21)

        st.write("Base:", base)
        for i, j in enumerate(jogos, 1):
            st.write(f"Jogo {i}: {j}")

if __name__ == "__main__":
    main()
