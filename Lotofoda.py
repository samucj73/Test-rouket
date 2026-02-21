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
    page_title="🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V2",
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
        return [n for n, q in cont.items() if q >= 10]

    # =================================================
    # SCORE DNA
    # =================================================
    def score_numero(self, n):
        return (
            self.frequencias[n] * self.dna["freq"] +
            (1 - self.defasagens[n]/self.total_concursos) * self.dna["defas"] +
            (self.dna["chave"] if n in self.numeros_chave else 0)
        )

    # =================================================
    # FECHAMENTO 16–17 DEZENAS
    # =================================================
    def gerar_fechamento(self, tamanho=16):
        scores = {n: self.score_numero(n) for n in self.numeros}
        base = sorted(scores, key=scores.get, reverse=True)[:tamanho]
        return sorted(base)

    def gerar_subjogos(self, fechamento, qtd_jogos=6):
        jogos = set()

        while len(jogos) < qtd_jogos:
            jogo = sorted(random.sample(fechamento, 15))
            soma = sum(jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)

            if 180 <= soma <= 220 and 6 <= pares <= 9:
                jogos.add(tuple(jogo))

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

# =====================================================
# INTERFACE
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V2")

    if "analise" not in st.session_state:
        st.session_state.analise = None
    if "jogos" not in st.session_state:
        st.session_state.jogos = []

    with st.sidebar:
        qtd = st.slider("Qtd concursos", 50, 1000, 200)
        #if st.button("📥 Carregar concursos"):
        #if st.button("📥 Carregar concursos"):
        if st.button("📥 Carregar concursos"):
            url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        st.error("❌ Erro ao conectar com a API da Lotofácil")
        st.stop()

    if not isinstance(data, list) or len(data) == 0:
        st.error("❌ API retornou dados inválidos ou vazios")
        st.stop()

    # ===============================
    # CONCURSO MAIS RECENTE
    # ===============================
    ultimo = data[0]
    numero_concurso = ultimo.get("concurso", "—")
    dezenas_ultimo = sorted(map(int, ultimo.get("dezenas", [])))
    data_concurso = ultimo.get("data", "—")

    if len(dezenas_ultimo) != 15:
        st.error("❌ Último concurso inválido (dezenas incorretas)")
        st.stop()

    # ===============================
    # LISTA DE CONCURSOS PARA ANÁLISE
    # ===============================
    concursos = [
        sorted(map(int, d["dezenas"]))
        for d in data[:qtd]
        if "dezenas" in d and len(d["dezenas"]) == 15
    ]

    if len(concursos) < 10:
        st.error("❌ Concursos insuficientes para análise")
        st.stop()

    st.session_state.analise = AnaliseLotofacilAvancada(concursos)
    st.session_state.analise.auto_ajustar_dna(dezenas_ultimo)

    st.success("✅ Concursos carregados e DNA ajustado com sucesso")

    st.markdown("### 🏆 Último Concurso Carregado")
    st.markdown(f"""
    **Concurso:** `{numero_concurso}`  
    **Data:** `{data_concurso}`  
    **Dezenas:**  
    🔢 **{", ".join(f"{n:02d}" for n in dezenas_ultimo)}**
    """)    

    if st.session_state.analise:
        tab1, tab2, tab3 = st.tabs(
            ["📊 Análise", "🧩 Fechamento 16–17", "🧬 DNA"]
        )

        with tab1:
            st.write("🔑 Números-chave:", st.session_state.analise.numeros_chave)

        # =================================================
        # ABA FECHAMENTO
        # =================================================
        with tab2:
            st.subheader("🧩 Fechamento Inteligente (DNA)")

            tamanho = st.radio("Tamanho do fechamento", [16, 17], horizontal=True)
            qtd_jogos = st.slider("Qtd de jogos (15 dezenas)", 4, 10, 6)

            if st.button("🚀 Gerar Fechamento"):
                fechamento = st.session_state.analise.gerar_fechamento(tamanho)
                jogos = st.session_state.analise.gerar_subjogos(fechamento, qtd_jogos)

                st.markdown("### 🔒 Fechamento Base")
                st.write(", ".join(f"{n:02d}" for n in fechamento))

                st.markdown("### 🎯 Jogos Gerados")
                df = pd.DataFrame({
                    "Jogo": range(1, len(jogos)+1),
                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                    "Soma": [sum(j) for j in jogos],
                    "Pares": [sum(1 for n in j if n % 2 == 0) for j in jogos]
                })
                st.dataframe(df, use_container_width=True)

        with tab3:
            st.subheader("🧬 DNA Adaptativo Atual")
            st.json(st.session_state.analise.dna)

if __name__ == "__main__":
    main()
