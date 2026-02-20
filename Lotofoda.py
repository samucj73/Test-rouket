import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from datetime import datetime
import plotly.express as px
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIG STREAMLIT
# =====================================================
st.set_page_config(
    page_title="🎯 Lotofácil Profissional V3",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL
# =====================================================
class AnaliseLotofacil:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo = concursos[0]
        self.numeros = list(range(1, 26))
        self.total = len(concursos)

        self.mapa = defaultdict(list)
        for c in concursos:
            for n in c:
                self.mapa[n].append(c)

        self.freq = self._frequencia_ponderada()
        self.defasagem = self._defasagem()
        self.correlacao = self._correlacao()
        self.condicional = self._prob_condicional()
        self.tendencia = self._tendencias()
        self.padroes = self._padroes()
        self.numeros_chave = self._numeros_chave()

    # =================================================
    def _frequencia_ponderada(self):
        peso_total = sum(np.exp(-i/30) for i in range(self.total))
        f = {}
        for n in self.numeros:
            soma = sum(np.exp(-i/30) for i,c in enumerate(self.concursos) if n in c)
            f[n] = (soma/peso_total)*100 if peso_total else 0
        return f

    def _defasagem(self):
        d = {}
        for n in self.numeros:
            idx = next((i for i,c in enumerate(self.concursos) if n in c), None)
            if idx is None:
                d[n] = self.total
            else:
                d[n] = idx
        return d

    def _correlacao(self):
        c = defaultdict(lambda: defaultdict(float))
        for n1 in self.numeros:
            for n2 in self.numeros:
                if n1 < n2:
                    juntos = sum(1 for c1 in self.mapa[n1] if n2 in c1)
                    base = min(len(self.mapa[n1]), len(self.mapa[n2]))
                    p = juntos/base if base else 0
                    c[n1][n2] = c[n2][n1] = p
        return c

    def _prob_condicional(self):
        p = defaultdict(lambda: defaultdict(float))
        for n1 in self.numeros:
            for n2 in self.numeros:
                if n1 != n2 and self.mapa[n2]:
                    juntos = sum(1 for c in self.mapa[n2] if n1 in c)
                    p[n1][n2] = juntos/len(self.mapa[n2])
        return p

    def _tendencias(self):
        t = {}
        for n in self.numeros:
            serie = [1 if n in c else 0 for c in self.concursos]
            if len(serie) >= 10:
                mm = np.mean(serie[:10])
                atual = np.mean(serie[-10:])
                t[n] = "alta" if atual > mm else "baixa"
            else:
                t[n] = "neutra"
        return t

    def _padroes(self):
        p = defaultdict(list)
        for c in self.concursos:
            p["soma"].append(sum(c))
            p["pares"].append(sum(1 for n in c if n%2==0))
            p["repetidos"].append(len(set(c)&set(self.ultimo)))
        return p

    def _numeros_chave(self):
        chave = []
        for n in self.numeros:
            score = self.freq[n]*0.5 + (20-self.defasagem[n])*0.3
            if self.tendencia[n] == "alta":
                score += 10
            if score > 30:
                chave.append(n)
        return chave

    # =================================================
    # ENSEMBLE STRATEGY
    # =================================================
    def gerar_jogo_ensemble(self, modo="Balanceado"):
        votos = Counter()

        for n in self.numeros:
            votos[n] += self.freq[n]
            votos[n] += max(0, 15-self.defasagem[n])
            votos[n] += 5 if self.tendencia[n]=="alta" else 0
            votos[n] += 8 if n in self.numeros_chave else 0

        if modo == "Conservador":
            selecionados = [n for n,_ in votos.most_common(18)]
        elif modo == "Agressivo":
            selecionados = random.sample(self.numeros, 18)
        else:
            selecionados = [n for n,_ in votos.most_common(22)]

        jogo = sorted(random.sample(selecionados, 15))
        return jogo

    # =================================================
    def validar_jogo(self, jogo):
        motivos = []
        soma_media = np.mean(self.padroes["soma"])
        desvio = np.std(self.padroes["soma"])

        if abs(sum(jogo)-soma_media) > 2.5*desvio:
            motivos.append("Soma fora do padrão")

        pares = sum(1 for n in jogo if n%2==0)
        if pares < 5 or pares > 10:
            motivos.append("Par/Ímpar fora")

        chave = sum(1 for n in jogo if n in self.numeros_chave)
        if chave < 2:
            motivos.append("Poucos números-chave")

        return "✅" if not motivos else "❌", ", ".join(motivos) if motivos else "OK"

    # =================================================
    def conferir(self, jogos):
        dados = []
        for i,j in enumerate(jogos,1):
            valido, motivo = self.validar_jogo(j)
            dados.append({
                "Jogo": i,
                "Dezenas": ", ".join(f"{n:02d}" for n in j),
                "Acertos": len(set(j)&set(self.ultimo)),
                "Soma": sum(j),
                "Válido": valido,
                "Motivos": motivo
            })
        return dados

# =====================================================
# INTERFACE
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL – ANALISADOR PROFISSIONAL V3")

    if "analise" not in st.session_state:
        st.session_state.analise = None
    if "jogos" not in st.session_state:
        st.session_state.jogos = []

    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Concursos", 50, 1000, 200, 50)
        modo = st.selectbox("Modo de Jogo", ["Conservador","Balanceado","Agressivo"])

        if st.button("🔄 Carregar Concursos", type="primary"):
            dados = requests.get("https://loteriascaixa-api.herokuapp.com/api/lotofacil").json()
            concursos = [sorted(map(int,d["dezenas"])) for d in dados[:qtd]]
            st.session_state.analise = AnaliseLotofacil(concursos)
            st.success("Concursos carregados")

    if st.session_state.analise:
        tab1, tab2, tab3 = st.tabs(["📊 Análise","🎲 Jogos","📈 Conferência"])

        with tab1:
            df = pd.DataFrame({
                "Número": list(st.session_state.analise.freq.keys()),
                "Frequência": list(st.session_state.analise.freq.values())
            })
            st.plotly_chart(px.bar(df, x="Número", y="Frequência"), use_container_width=True)

        with tab2:
            if st.button("🎯 Gerar Jogos"):
                st.session_state.jogos = [
                    st.session_state.analise.gerar_jogo_ensemble(modo)
                    for _ in range(15)
                ]
                st.success("Jogos gerados")

        with tab3:
            if st.session_state.jogos:
                resultado = st.session_state.analise.conferir(st.session_state.jogos)
                df = pd.DataFrame(resultado)
                st.dataframe(df, use_container_width=True)

                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Exportar CSV",
                    csv,
                    f"resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

if __name__ == "__main__":
    main()
