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
    page_title="🎯 LOTOFÁCIL - FECHAMENTO AVANÇADO",
    layout="wide"
)

# =====================================================
# MOTOR AVANÇADO
# =====================================================
class LotofacilEngine:

    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.total = len(concursos)

        self.freq = self._frequencias()
        self.defas = self._defasagens()
        self.padroes = self._padroes()

        self.dna = self._dna_inicial()
        self.chaves = self._numeros_chave_avancado()

    # =================================================
    # DNA
    # =================================================
    def _dna_inicial(self):
        return {
            "freq": 1.0,
            "defas": 1.0,
            "soma": 1.0,
            "pares": 1.0,
            "seq": 1.0,
            "ruptura": 0.6
        }

    def ajustar_dna(self, resultado):
        lr = 0.05
        soma = sum(resultado)
        pares = sum(n % 2 == 0 for n in resultado)

        soma_med = np.mean(self.padroes["somas"])
        pares_med = np.mean(self.padroes["pares"])

        self.dna["soma"] += lr if soma > soma_med else -lr
        self.dna["pares"] += lr if pares > pares_med else -lr

        for k in self.dna:
            self.dna[k] = min(2.0, max(0.4, self.dna[k]))

    # =================================================
    # ANÁLISES
    # =================================================
    def _frequencias(self):
        c = Counter()
        for con in self.concursos:
            c.update(con)
        return {n: c[n] / self.total for n in self.numeros}

    def _defasagens(self):
        d = {}
        for n in self.numeros:
            for i, c in enumerate(self.concursos):
                if n in c:
                    d[n] = i
                    break
            else:
                d[n] = self.total
        return d

    def _padroes(self):
        return {
            "somas": [sum(c) for c in self.concursos],
            "pares": [sum(n % 2 == 0 for n in c) for c in self.concursos]
        }

    # =================================================
    # NÚMEROS-CHAVE AVANÇADOS
    # =================================================
    def _numeros_chave_avancado(self):
        scores = {}
        for n in self.numeros:
            scores[n] = (
                self.freq[n] * 1.5 +
                (1 - self.defas[n] / self.total) +
                random.uniform(0, self.dna["ruptura"])
            )

        ordenado = sorted(scores, key=scores.get, reverse=True)

        return {
            "fixos": ordenado[:7],
            "condicionais": ordenado[7:14],
            "ruptura": ordenado[14:20]
        }

    # =================================================
    # FECHAMENTO EM CAMADAS
    # =================================================
    def gerar_fechamento(self, tamanho=16):

        base = (
            self.chaves["fixos"] +
            self.chaves["condicionais"][:(tamanho - len(self.chaves["fixos"]))]
        )

        return sorted(base[:tamanho])

    # =================================================
    # SCORE DO JOGO
    # =================================================
    def score_jogo(self, jogo):
        soma = sum(jogo)
        pares = sum(n % 2 == 0 for n in jogo)
        seq = max(
            len(list(g)) for _, g in
            itertools.groupby(
                [jogo[i+1] - jogo[i] == 1 for i in range(len(jogo)-1)]
            ) if _ is True
        ) if len(jogo) > 2 else 0

        score = 0
        score += -abs(195 - soma) * self.dna["soma"]
        score += -abs(7 - pares) * self.dna["pares"]
        score += -seq * self.dna["seq"]

        return score

    # =================================================
    # GERADOR AVANÇADO DE JOGOS
    # =================================================
    def gerar_jogos(self, fechamento, qtd=6):

        candidatos = []

        while len(candidatos) < 30:
            jogo = sorted(random.sample(fechamento, 15))
            soma = sum(jogo)
            pares = sum(n % 2 == 0 for n in jogo)

            if 185 <= soma <= 215 and 6 <= pares <= 9:
                score = self.score_jogo(jogo)
                candidatos.append((jogo, score))

        candidatos.sort(key=lambda x: x[1], reverse=True)
        return candidatos[:qtd]

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():

    st.title("🎯 LOTOFÁCIL — FECHAMENTO AVANÇADO")

    if "engine" not in st.session_state:
        st.session_state.engine = None

    with st.sidebar:
        qtd = st.slider("Qtd concursos", 100, 1000, 300)
        if st.button("📥 Carregar Concursos"):
            url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            data = requests.get(url).json()
            concursos = [sorted(map(int, d["dezenas"])) for d in data[:qtd]]
            st.session_state.engine = LotofacilEngine(concursos)
            st.session_state.engine.ajustar_dna(concursos[0])
            st.success("Motor avançado carregado")

    if st.session_state.engine:
        tab1, tab2, tab3 = st.tabs(
            ["🧠 Números-Chave", "🧩 Fechamento Avançado", "🧬 DNA"]
        )

        with tab1:
            st.json(st.session_state.engine.chaves)

        with tab2:
            tamanho = st.radio("Fechamento", [16, 17], horizontal=True)
            qtd = st.slider("Qtd jogos", 4, 8, 6)

            if st.button("🚀 Gerar Fechamento"):
                fechamento = st.session_state.engine.gerar_fechamento(tamanho)
                jogos = st.session_state.engine.gerar_jogos(fechamento, qtd)

                st.markdown("### 🔒 Fechamento Base")
                st.write(", ".join(f"{n:02d}" for n in fechamento))

                df = pd.DataFrame([{
                    "Jogo": i+1,
                    "Dezenas": ", ".join(f"{n:02d}" for n in j),
                    "Score": round(s, 2),
                    "Soma": sum(j),
                    "Pares": sum(n % 2 == 0 for n in j)
                } for i, (j, s) in enumerate(jogos)])

                st.dataframe(df, use_container_width=True)

        with tab3:
            st.json(st.session_state.engine.dna)

if __name__ == "__main__":
    import itertools
    main()
