import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - ANALISADOR DNA PRO",
    layout="wide"
)

# =====================================================
# CLASSE PRINCIPAL
# =====================================================
class AnaliseLotofacilAvancada:

    def __init__(self, concursos):
        self.concursos = concursos
        self.total_concursos = len(concursos)
        self.numeros = list(range(1, 26))

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

    # =================================================
    # ESTATÍSTICAS
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
        return {
            "somas": [sum(c) for c in self.concursos],
            "pares": [sum(1 for n in c if n % 2 == 0) for c in self.concursos]
        }

    def _numeros_chave(self):
        c = Counter()
        for con in self.concursos[:20]:
            c.update(con)
        return [n for n, q in c.items() if q >= 10]

    # =================================================
    # SCORE
    # =================================================
    def score_numero(self, n):
        return (
            self.frequencias[n] * self.dna["freq"] +
            (1 - self.defasagens[n] / self.total_concursos) * self.dna["defas"] +
            (self.dna["chave"] if n in self.numeros_chave else 0)
        )

    # =================================================
    # FECHAMENTO
    # =================================================
    def gerar_fechamento(self, tamanho):
        scores = {n: self.score_numero(n) for n in self.numeros}
        base = sorted(scores, key=scores.get, reverse=True)[:tamanho]
        return sorted(base)

    def gerar_jogos(self, fechamento, qtd):
        jogos = set()
        while len(jogos) < qtd:
            j = sorted(random.sample(fechamento, 15))
            soma = sum(j)
            pares = sum(1 for n in j if n % 2 == 0)
            if 180 <= soma <= 220 and 6 <= pares <= 9:
                jogos.add(tuple(j))
        return [list(j) for j in jogos]

    # =================================================
    # CONFERÊNCIA
    # =================================================
    def conferir(self, jogos, resultado):
        dados = []
        for i, j in enumerate(jogos, 1):
            dados.append({
                "Jogo": i,
                "Dezenas": ", ".join(f"{n:02d}" for n in j),
                "Acertos": len(set(j) & set(resultado)),
                "Soma": sum(j),
                "Pares": sum(1 for n in j if n % 2 == 0)
            })
        return pd.DataFrame(dados)

    # =================================================
    # APRENDIZADO (11–14)
    # =================================================
    def reforcar_dna_por_acertos(self, jogos, resultado):
        for jogo in jogos:
            acertos = len(set(jogo) & set(resultado))
            if acertos < 11:
                continue

            reforco = {11: 0.02, 12: 0.04, 13: 0.06, 14: 0.08}.get(acertos, 0)

            soma = sum(jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)

            if soma >= np.mean(self.padroes["somas"]):
                self.dna["soma"] += reforco

            if pares >= np.mean(self.padroes["pares"]):
                self.dna["pares"] += reforco

            # sequência
            max_seq, atual = 1, 1
            for i in range(1, len(jogo)):
                if jogo[i] == jogo[i-1] + 1:
                    atual += 1
                    max_seq = max(max_seq, atual)
                else:
                    atual = 1

            if max_seq >= 3:
                self.dna["seq"] += reforco

            for n in jogo:
                if self.frequencias[n] >= 0.5:
                    self.dna["freq"] += reforco / 15
                if self.defasagens[n] <= 10:
                    self.dna["defas"] += reforco / 15

            if any(n in self.numeros_chave for n in jogo):
                self.dna["chave"] += reforco

        for k in self.dna:
            self.dna[k] = max(0.5, min(2.0, self.dna[k]))

# =====================================================
# APP
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL – DNA PROFISSIONAL")

    if "analise" not in st.session_state:
        st.session_state.analise = None
    if "jogos" not in st.session_state:
        st.session_state.jogos = []

    # SIDEBAR
    with st.sidebar:
        qtd = st.slider("Qtd concursos", 50, 1000, 200)
        if st.button("📥 Carregar concursos"):
            url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            data = requests.get(url).json()
            concursos = [sorted(map(int, d["dezenas"])) for d in data[:qtd]]
            st.session_state.analise = AnaliseLotofacilAvancada(concursos)
            st.success("Concursos carregados")

    if not st.session_state.analise:
        st.info("Carregue os concursos para iniciar")
        return

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Análise", "🧩 Fechamento", "🎯 Conferência", "🧬 DNA"]
    )

    with tab1:
        st.write("🔑 Números-chave:", st.session_state.analise.numeros_chave)

    with tab2:
        tamanho = st.radio("Fechamento", [16, 17, 18], horizontal=True)
        qtd_jogos = st.slider("Qtd jogos", 4, 20, 8)

        if st.button("🚀 Gerar jogos"):
            fechamento = st.session_state.analise.gerar_fechamento(tamanho)
            jogos = st.session_state.analise.gerar_jogos(fechamento, qtd_jogos)
            st.session_state.jogos = jogos

            st.write("🔒 Fechamento:", ", ".join(f"{n:02d}" for n in fechamento))

            df = pd.DataFrame({
                "Jogo": range(1, len(jogos)+1),
                "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                "Soma": [sum(j) for j in jogos],
                "Pares": [sum(1 for n in j if n % 2 == 0) for j in jogos]
            })
            st.dataframe(df, use_container_width=True)

    #with tab3:
    with tab3:
        st.subheader("🎯 Digite o resultado oficial (15 dezenas)")
        entrada = st.text_input(
        "Aceita vírgula, traço ou espaço",
        placeholder="01-02-04-07-08-10-11-12-13-16-19-20-21-22-23"
    )

    if st.button("📊 Conferir jogos"):
        try:
            if not entrada.strip():
                st.error("❌ Informe as 15 dezenas do resultado")
                st.stop()

            # 🔹 Normalização: troca tudo por vírgula
            limpa = (
                entrada.replace("-", ",")
                       .replace(" ", ",")
            )

            partes = [p for p in limpa.split(",") if p != ""]

            resultado = sorted(map(int, partes))

            if len(resultado) != 15:
                st.error("❌ O resultado deve conter exatamente 15 dezenas")
                st.stop()

            if len(set(resultado)) != 15:
                st.error("❌ Não repita dezenas")
                st.stop()

            if any(n < 1 or n > 25 for n in resultado):
                st.error("❌ As dezenas devem estar entre 01 e 25")
                st.stop()

            df = st.session_state.analise.conferir(
                st.session_state.jogos, resultado
            )
            st.dataframe(df, use_container_width=True)

            # 🔹 Reforço do DNA baseado nos acertos
            st.session_state.analise.reforcar_dna_por_acertos(
                st.session_state.jogos, resultado
            )

            st.success("🧬 DNA ajustado com base no desempenho real")

        except ValueError:
            st.error("❌ Use apenas números (01 a 25) separados por vírgula, traço ou espaço.")    
    with tab4:
        st.json(st.session_state.analise.dna)

if __name__ == "__main__":
    main()
