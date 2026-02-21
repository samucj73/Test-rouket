import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
from io import StringIO
import plotly.express as px
import warnings
warnings.filterwarnings("ignore")

# =============================
# CONFIGURAÇÃO MOBILE PREMIUM
# =============================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL PREMIUM",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
/* Layout mobile premium */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1,h2,h3 { text-align: center; }
.card { background: #0e1117; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid #262730; color: white; }
.stButton>button { width: 100%; height: 3.2em; border-radius: 14px; font-size: 1.05em; }
input, textarea { border-radius: 12px !important; }
.p12 { color: #4cc9f0; font-weight: bold; }
.p13 { color: #4ade80; font-weight: bold; }
.p14 { color: gold; font-weight: bold; }
.p15 { color: #f97316; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL PREMIUM")
st.caption("Conferência • DNA • Fechamento • Mobile First")

# =============================
# CLASSE ANALISADOR V2
# =============================
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

    def _dna_inicial(self):
        return { "freq":1.0,"defas":1.0,"soma":1.0,"pares":1.0,"seq":1.0,"chave":1.0 }

    def auto_ajustar_dna(self, concurso_real):
        lr = 0.05
        soma_r = sum(concurso_real)
        pares_r = sum(1 for n in concurso_real if n % 2 == 0)
        soma_m = np.mean(self.padroes["somas"])
        pares_m = np.mean(self.padroes["pares"])
        self.dna["soma"] += lr if soma_r > soma_m else -lr
        self.dna["pares"] += lr if pares_r > pares_m else -lr
        tem_seq = any(concurso_real[i+2]==concurso_real[i]+2 for i in range(len(concurso_real)-2))
        self.dna["seq"] += lr if tem_seq else -lr
        for k in self.dna:
            self.dna[k] = max(0.5, min(2.0, self.dna[k]))

    def _frequencias(self):
        c = Counter()
        for con in self.concursos:
            c.update(con)
        return {n: c[n]/self.total_concursos for n in self.numeros}

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
        p = {"somas":[],"pares":[]}
        for c in self.concursos:
            p["somas"].append(sum(c))
            p["pares"].append(sum(1 for n in c if n % 2 == 0))
        return p

    def _numeros_chave(self):
        cont = Counter()
        for c in self.concursos[:-15]:
            cont.update(c)
        return [n for n,q in cont.items() if q>=10]

    def score_numero(self, n):
        return (
            self.frequencias[n]*self.dna["freq"]+
            (1-self.defasagens[n]/self.total_concursos)*self.dna["defas"]+
            (self.dna["chave"] if n in self.numeros_chave else 0)
        )

    def gerar_fechamento(self, tamanho=16):
        scores = {n:self.score_numero(n) for n in self.numeros}
        base = sorted(scores,key=scores.get,reverse=True)[:tamanho]
        return sorted(base)

    def gerar_subjogos(self, fechamento, qtd_jogos=6):
        jogos=set()
        while len(jogos)<qtd_jogos:
            jogo=sorted(random.sample(fechamento,15))
            soma=sum(jogo)
            pares=sum(1 for n in jogo if n%2==0)
            if 180<=soma<=220 and 6<=pares<=9:
                jogos.add(tuple(jogo))
        return [list(j) for j in jogos]

# =============================
# SESSION STATE
# =============================
if "concursos_raw" not in st.session_state: st.session_state.concursos_raw=None
if "concursos_processados" not in st.session_state: st.session_state.concursos_processados=None
if "analise" not in st.session_state: st.session_state.analise=None

# =============================
# SIDEBAR - API LOTOFÁCIL
# =============================
with st.sidebar:
    qtd = st.slider("Qtd concursos históricos",50,1000,200)
    if st.button("📥 Carregar concursos"):
        url="https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
        data=requests.get(url).json()
        st.session_state.concursos_raw=data[:qtd]
        concursos=[sorted(map(int,d["dezenas"])) for d in data[:qtd]]
        st.session_state.concursos_processados=concursos
        st.session_state.analise=AnaliseLotofacilAvancada(concursos)
        st.session_state.analise.auto_ajustar_dna(concursos[0])
        st.success(f"✅ {qtd} concursos carregados e mantidos em memória")

# =============================
# FUNÇÃO PRINCIPAL
# =============================
def main():
    st.subheader("🎯 Conferência de Jogos & Fechamento Inteligente")

    # ===== Entrada Jogos =====
    csv_upload=st.file_uploader("Upload CSV (opcional)",type=["csv"])
    csv_text=st.text_area("Ou cole os jogos aqui (CSV)",height=200)

    if csv_upload:
        df=pd.read_csv(csv_upload)
    elif csv_text.strip():
        df=pd.read_csv(StringIO(csv_text))
    else:
        df=None

    # ===== Conferência automática apenas (mobile premium) =====
    if df is not None and st.session_state.analise:
        df["Lista"]=[[int(i.strip()) for i in x.split(",")] for x in df["Dezenas"]]
        dezenas_sorteadas=[int(d) for d in st.session_state.concursos_processados[0]]

        resultados=[]
        for _,row in df.iterrows():
            acertos=sorted(set(row["Lista"]) & set(dezenas_sorteadas))
            resultados.append({
                "Jogo":row["Jogo"],
                "Pontos":len(acertos),
                "Acertos":", ".join(f"{d:02d}" for d in acertos)
            })
        df_res=pd.DataFrame(resultados).sort_values("Pontos",ascending=False)

        c1,c2,c3=st.columns(3)
        c1.metric("🏆 Máx",df_res["Pontos"].max())
        c2.metric("🎯 Jogos",len(df_res))
        c3.metric("🔥 12+",(df_res["Pontos"]>=12).sum())

        st.subheader("✅ Conferência")
        for _,row in df_res.iterrows():
            pontos=row["Pontos"]
            cls=f"p{pontos}" if pontos>=12 else ""
            st.markdown(f"""
            <div class="card">
                <b>Jogo {row['Jogo']}</b><br>
                <span class="{cls}">{pontos} pontos</span><br>
                <small>{row['Acertos']}</small>
            </div>
            """,unsafe_allow_html=True)

    # ===== Interface completa do segundo código =====
    if st.session_state.analise:
        tab1, tab2, tab3 = st.tabs(["📊 Análise","🧩 Fechamento 16–17","🧬 DNA"])
        with tab1:
            st.subheader("🔑 Números-chave")
            st.write(st.session_state.analise.numeros_chave)
        with tab2:
            st.subheader("🧩 Fechamento Inteligente")
            tamanho=st.radio("Tamanho do fechamento",[16,17],horizontal=True)
            qtd_jogos=st.slider("Qtd de jogos (15 dezenas)",4,10,6)
            if st.button("🚀 Gerar Fechamento"):
                fechamento=st.session_state.analise.gerar_fechamento(tamanho)
                jogos=st.session_state.analise.gerar_subjogos(fechamento,qtd_jogos)
                st.markdown("### 🔒 Fechamento Base")
                st.write(", ".join(f"{n:02d}" for n in fechamento))
                dfj=pd.DataFrame({
                    "Jogo":range(1,len(jogos)+1),
                    "Dezenas":[", ".join(f"{n:02d}" for n in j) for j in jogos],
                    "Soma":[sum(j) for j in jogos],
                    "Pares":[sum(1 for n in j if n%2==0) for j in jogos]
                })
                st.markdown("### 🎯 Jogos Gerados")
                st.dataframe(dfj,use_container_width=True)
        with tab3:
            st.subheader("🧬 DNA Atual")
            st.json(st.session_state.analise.dna)

if __name__=="__main__":
    main()
