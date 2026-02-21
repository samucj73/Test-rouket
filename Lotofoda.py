import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIGURAÇÃO
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V3",
    layout="wide"
)

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
        self.defasagens = self._defasagens()
        self.padroes = self._padroes()
        self.numeros_chave = self._numeros_chave()

        self.dna = self._dna_inicial()

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
            "chave": 1.0
        }

    def auto_ajustar_dna(self, concurso_real):
        lr = 0.05

        soma_r = sum(concurso_real)
        pares_r = sum(1 for n in concurso_real if n % 2 == 0)

        soma_m = np.mean(self.padroes["somas"])
        pares_m = np.mean(self.padroes["pares"])

        self.dna["soma"] += lr if soma_r > soma_m else -lr
        self.dna["pares"] += lr if pares_r > pares_m else -lr

        tem_seq = any(
            concurso_real[i+2] == concurso_real[i] + 2
            for i in range(len(concurso_real)-2)
        )
        self.dna["seq"] += lr if tem_seq else -lr

        for k in self.dna:
            self.dna[k] = max(0.5, min(2.0, self.dna[k]))

    # =================================================
    # ANÁLISES
    # =================================================
    def _frequencias(self):
        c = Counter()
        for con in self.concursos:
            c.update(con)
        return {n: c[n] / self.total_concursos for n in self.numeros}

    def _defasagens(self):
        d = {}
        for n in self.numeros:
            for i, c in enumerate(self.concursos):
                if n in c:
                    d[n] = i
                    break
            else:
                d[n] = self.total_concursos
        return d

    def _padroes(self):
        p = {"somas": [], "pares": []}
        for c in self.concursos:
            p["somas"].append(sum(c))
            p["pares"].append(sum(1 for n in c if n % 2 == 0))
        return p

    def _numeros_chave(self):
        cont = Counter()
        for c in self.concursos[:20]:
            cont.update(c)
        return sorted([n for n, q in cont.items() if q >= 10])

    # =================================================
    # SCORE
    # =================================================
    def score_numero(self, n):
        return (
            self.frequencias[n] * self.dna["freq"] +
            (1 - self.defasagens[n]/self.total_concursos) * self.dna["defas"] +
            (self.dna["chave"] if n in self.numeros_chave else 0)
        )

    def score_jogo(self, jogo, jogos_existentes):
        score = 0
        score += abs(sum(jogo) - np.mean(self.padroes["somas"])) * -0.05
        score += abs(sum(n % 2 == 0 for n in jogo) - 7) * -1

        # Sequências
        for i in range(len(jogo)-2):
            if jogo[i+2] == jogo[i] + 2:
                score += self.dna["seq"]

        # Anti clones
        for j in jogos_existentes:
            if len(set(jogo) & set(j)) >= 13:
                score -= 10

        return score

    # =================================================
    # FECHAMENTO
    # =================================================
    def gerar_fechamento(self, tamanho=16):
        scores = {n: self.score_numero(n) for n in self.numeros}
        base = sorted(scores, key=scores.get, reverse=True)
        return sorted(base[:tamanho])

    def gerar_jogos(self, fechamento, qtd=6):

        jogos_finais = []
        tentativas = 0

        nucleo_tam = 8 if len(fechamento) >= 17 else 7
        nucleo = fechamento[:nucleo_tam]
        resto = list(set(fechamento) - set(nucleo))

        if len(nucleo) + len(resto) < 15:
            return []

        while len(jogos_finais) < qtd and tentativas < 800:
            tentativas += 1

            complemento_tam = 15 - len(nucleo)
            if len(resto) < complemento_tam:
                continue

            complemento = random.sample(resto, complemento_tam)
            jogo = sorted(nucleo + complemento)

            soma = sum(jogo)
            pares = sum(n % 2 == 0 for n in jogo)

            if not (185 <= soma <= 215):
                continue
            if not (6 <= pares <= 9):
                continue

            score = self.score_jogo(jogo, jogos_finais)
            if score < -8:
                continue

            if jogo not in jogos_finais:
                jogos_finais.append(jogo)

        jogos_rank = [(j, self.score_jogo(j, [])) for j in jogos_finais]
        jogos_rank.sort(key=lambda x: x[1], reverse=True)

        return [j for j, _ in jogos_rank[:qtd]]

# =====================================================
# INTERFACE
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V3")

    if "engine" not in st.session_state:
        st.session_state.engine = None

    with st.sidebar:
        qtd = st.slider("Qtd concursos", 50, 1000, 200)
        if st.button("📥 Carregar concursos"):
            url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            data = requests.get(url).json()
            concursos = [sorted(map(int, d["dezenas"])) for d in data[:qtd]]
            engine = AnaliseLotofacilAvancada(concursos)
            engine.auto_ajustar_dna(concursos[0])
            st.session_state.engine = engine
            st.success("Concursos carregados e DNA ajustado")

    if st.session_state.engine:
        tab1, tab2, tab3 = st.tabs(["📊 Análise", "🧩 Fechamento", "🧬 DNA"])

        with tab1:
            st.write("🔑 Números-chave:", st.session_state.engine.numeros_chave)

        with tab2:
            tamanho = st.radio("Fechamento", [16, 17], horizontal=True)
            qtd_jogos = st.slider("Jogos (15 dezenas)", 4, 10, 6)

            if st.button("🚀 Gerar"):
                fechamento = st.session_state.engine.gerar_fechamento(tamanho)
                jogos = st.session_state.engine.gerar_jogos(fechamento, qtd_jogos)

                st.markdown("### 🔒 Fechamento Base")
                st.write(", ".join(f"{n:02d}" for n in fechamento))

                st.markdown("### 🎯 Jogos")
                df = pd.DataFrame({
                    "Jogo": range(1, len(jogos)+1),
                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                    "Soma": [sum(j) for j in jogos],
                    "Pares": [sum(n % 2 == 0 for n in j) for j in jogos]
                })
                st.dataframe(df, use_container_width=True)

        with tab3:
            st.subheader("🧬 DNA Atual")
            st.json(st.session_state.engine.dna)

if __name__ == "__main__":
    main()
