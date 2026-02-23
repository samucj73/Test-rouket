import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL PREMIUM",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1,h2,h3 { text-align: center; }
.card { background: #0e1117; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid #262730; color: white; }
.stButton>button { width: 100%; height: 3.2em; border-radius: 14px; font-size: 1.05em; }
input, textarea { border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL PREMIUM")
st.caption("DNA • Fechamento • Desdobramento • Mobile First")

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

    # ================= DNA =================
    def _dna_inicial(self):
        return {"freq":1.0,"defas":1.0,"soma":1.0,"pares":1.0,"seq":1.0,"chave":1.0}

    def auto_ajustar_dna(self, concurso_real):
        lr = 0.05
        soma_r = sum(concurso_real)
        pares_r = sum(1 for n in concurso_real if n % 2 == 0)
        soma_m = np.mean(self.padroes["somas"])
        pares_m = np.mean(self.padroes["pares"])

        self.dna["soma"] += lr if soma_r > soma_m else -lr
        self.dna["pares"] += lr if pares_r > pares_m else -lr

        tem_seq = any(concurso_real[i+1] == concurso_real[i] + 1 for i in range(len(concurso_real)-1))
        self.dna["seq"] += lr if tem_seq else -lr

        for k in self.dna:
            self.dna[k] = max(0.5, min(2.0, self.dna[k]))

    # ================= BASE ESTATÍSTICA =================
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
        for c in self.concursos[:-25]:
            cont.update(c)
        return [n for n, q in cont.items() if q >= 10]

    def score_numero(self, n):
        return (
            self.frequencias[n] * self.dna["freq"]
            + (1 - self.defasagens[n] / self.total_concursos) * self.dna["defas"]
            + (self.dna["chave"] if n in self.numeros_chave else 0)
        )

    # ================= FECHAMENTO =================
    def gerar_fechamento(self, tamanho):
        scores = {n: self.score_numero(n) for n in self.numeros}
        base = sorted(scores, key=scores.get, reverse=True)[:tamanho]
        return sorted(base)

    # ================= ESTRATÉGIA =================
    def classificar_numeros(self):
        freq_ord = sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)
        quentes = [n for n,_ in freq_ord[:15]]
        frios = [n for n,_ in freq_ord[-10:]]
        medios = [n for n,_ in freq_ord[15:-10]]
        return quentes, medios, frios

    def tem_sequencia(self, jogo):
        jogo = sorted(jogo)
        return any(jogo[i+1] == jogo[i] + 1 for i in range(len(jogo)-1))

    # ================= SUBJOGOS 15 =================
    def gerar_subjogos(self, fechamento, qtd_jogos):
        jogos = set()
        quentes, medios, frios = self.classificar_numeros()
        ultimo = set(self.ultimo_concurso)

        while len(jogos) < qtd_jogos:
            jogo = set(random.sample(list(ultimo), random.randint(8, 10)))
            jogo |= set(random.sample(quentes, 9))
            jogo |= set(random.sample(medios, 4))
            jogo |= set(random.sample(frios, 2))

            jogo = list(jogo)
            if len(jogo) > 15:
                jogo = random.sample(jogo, 15)
            elif len(jogo) < 15:
                jogo += random.sample([n for n in fechamento if n not in jogo], 15-len(jogo))

            if 180 <= sum(jogo) <= 220 and 6 <= sum(1 for n in jogo if n%2==0) <= 9 and self.tem_sequencia(jogo):
                jogos.add(tuple(sorted(jogo)))

        return [list(j) for j in jogos]

    # ================= DESDOBRAMENTO =================
    def gerar_base_desdobramento(self, tamanho):
        return self.gerar_fechamento(tamanho)

    def desdobrar_base(self, base, qtd_jogos):
        jogos = set()
        quentes, medios, frios = self.classificar_numeros()
        ultimo = set(self.ultimo_concurso)

        while len(jogos) < qtd_jogos:
            jogo = set(random.sample(list(ultimo & set(base)), min(8, len(ultimo & set(base)))))
            jogo |= set(random.sample([n for n in base if n in quentes], 6))
            jogo |= set(random.sample([n for n in base if n in medios], 5))

            frios_base = [n for n in base if n in frios]
            if frios_base:
                jogo |= set(random.sample(frios_base, min(2, len(frios_base))))

            jogo = list(jogo)
            if len(jogo) > 15:
                jogo = random.sample(jogo, 15)
            elif len(jogo) < 15:
                jogo += random.sample([n for n in base if n not in jogo], 15-len(jogo))

            if 180 <= sum(jogo) <= 220 and 6 <= sum(1 for n in jogo if n%2==0) <= 9 and self.tem_sequencia(jogo):
                jogos.add(tuple(sorted(jogo)))

        return [list(j) for j in jogos]

# =====================================================
# INTERFACE
# =====================================================
def main():
    if "analise" not in st.session_state:
        st.session_state.analise = None

    with st.sidebar:
        qtd = st.slider("Qtd concursos históricos", 50, 1000, 200)
        if st.button("📥 Carregar concursos"):
            url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            data = requests.get(url).json()
            concursos = [sorted(map(int, d["dezenas"])) for d in data[:qtd]]
            st.session_state.analise = AnaliseLotofacilAvancada(concursos)
            st.session_state.analise.auto_ajustar_dna(concursos[0])
            st.success("✅ Concursos carregados")

    st.subheader("🎯 Fechamento & Desdobramento")

    if st.session_state.analise:
        modo = st.radio("Modo", ["Fechamento 16–17", "Desdobramento 18–19–20"], horizontal=True)

        if modo == "Fechamento 16–17":
            tamanho = st.radio("Tamanho", [16,17], horizontal=True)
            qtd_jogos = st.slider("Qtd jogos", 4, 10, 6)
            if st.button("🚀 Gerar"):
                base = st.session_state.analise.gerar_fechamento(tamanho)
                jogos = st.session_state.analise.gerar_subjogos(base, qtd_jogos)
        else:
            tamanho = st.selectbox("Base", [18,19,20])
            mapa = {18:15, 19:21, 20:30}
            qtd_jogos = mapa[tamanho]
            if st.button("🔥 Gerar Desdobramento"):
                base = st.session_state.analise.gerar_base_desdobramento(tamanho)
                jogos = st.session_state.analise.desdobrar_base(base, qtd_jogos)

        if "jogos" in locals():
            st.markdown("<div class='card'>🧱 Base: "+", ".join(f"{n:02d}" for n in base)+"</div>", unsafe_allow_html=True)
            df = pd.DataFrame({
                "Jogo": range(1,len(jogos)+1),
                "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                "Soma": [sum(j) for j in jogos],
                "Pares": [sum(1 for n in j if n%2==0) for j in jogos]
            })
            st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
