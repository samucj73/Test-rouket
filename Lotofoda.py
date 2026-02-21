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
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
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
st.caption("DNA • Fechamento • Conferência • Mobile First")

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
        tem_seq = any(concurso_real[i+2]==concurso_real[i]+2 for i in range(len(concurso_real)-2))
        self.dna["seq"] += lr if tem_seq else -lr
        for k in self.dna:
            self.dna[k] = max(0.5,min(2.0,self.dna[k]))

    def _frequencias(self):
        c=Counter()
        for con in self.concursos: c.update(con)
        return {n:c[n]/self.total_concursos for n in self.numeros}

    def _defasagens(self):
        d={}
        for n in self.numeros:
            for i,c in enumerate(self.concursos):
                if n in c:
                    d[n]=i
                    break
            else:
                d[n]=self.total_concursos
        return d

    def _padroes(self):
        p={"somas":[],"pares":[]}
        for c in self.concursos:
            p["somas"].append(sum(c))
            p["pares"].append(sum(1 for n in c if n%2==0))
        return p

    def _numeros_chave(self):
        cont=Counter()
        for c in self.concursos[:-25]: cont.update(c)
        return [n for n,q in cont.items() if q>=10]

    def score_numero(self,n):
        return self.frequencias[n]*self.dna["freq"] + (1-self.defasagens[n]/self.total_concursos)*self.dna["defas"] + (self.dna["chave"] if n in self.numeros_chave else 0)

    def gerar_fechamento(self,tamanho=16):
        scores={n:self.score_numero(n) for n in self.numeros}
        base=sorted(scores,key=scores.get,reverse=True)[:tamanho]
        return sorted(base)

    def gerar_subjogos(self,fechamento,qtd_jogos=6):
        jogos=set()
        while len(jogos)<qtd_jogos:
            jogo=sorted(random.sample(fechamento,15))
            soma=sum(jogo)
            pares=sum(1 for n in jogo if n%2==0)
            if 180<=soma<=220 and 6<=pares<=9: jogos.add(tuple(jogo))
        return [list(j) for j in jogos]

    def conferir(self,jogos,resultado):
        dados=[]
        for i,j in enumerate(jogos,1):
            dados.append({
                "Jogo":i,
                "Dezenas":", ".join(f"{n:02d}" for n in j),
                "Acertos":len(set(j)&set(resultado)),
                "Soma":sum(j),
                "Pares":sum(1 for n in j if n%2==0)
            })
        return pd.DataFrame(dados)

# =====================================================
# FUNÇÕES DE REPETIÇÃO
# =====================================================
def repeticao_ultimo_antepenultimo(concursos):
    if len(concursos)<3: return None
    ultimo=set(concursos[0])
    antepenultimo=set(concursos[2])
    repetidos=len(ultimo & antepenultimo)
    media=repetidos/15
    return repetidos,media

def repeticao_ultimo_penultimo(concursos):
    if len(concursos)<2: return None
    ultimo=set(concursos[0])
    penultimo=set(concursos[1])
    repetidos=len(ultimo & penultimo)
    media=repetidos/15
    return repetidos,media

# =====================================================
# INTERFACE
# =====================================================
def main():
    if "analise" not in st.session_state: st.session_state.analise=None
    if "jogos" not in st.session_state: st.session_state.jogos=[]

    # ================= SIDEBAR =================
    with st.sidebar:
        qtd=st.slider("Qtd concursos históricos",50,1000,200)
        if st.button("📥 Carregar concursos"):
            url="https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            data=requests.get(url).json()
            concursos=[sorted(map(int,d["dezenas"])) for d in data[:qtd]]
            st.session_state.analise=AnaliseLotofacilAvancada(concursos)
            st.session_state.analise.auto_ajustar_dna(concursos[0])
            st.success("✅ Concursos carregados e DNA ajustado")

            # ===== Repetições =====
            rep_antepenultimo=repeticao_ultimo_antepenultimo(concursos)
            if rep_antepenultimo:
                repetidos,media=rep_antepenultimo
                st.info(f"🔁 Último x Antepenúltimo: {repetidos} dezenas ({media*100:.2f}%)")

            rep_penultimo=repeticao_ultimo_penultimo(concursos)
            if rep_penultimo:
                repetidos,media=rep_penultimo
                st.info(f"🔁 Último x Penúltimo: {repetidos} dezenas ({media*100:.2f}%)")

    # ================= INTERFACE PRINCIPAL =================
    st.subheader("🎯 Análise e Fechamento Inteligente")

    if st.session_state.analise:
        tab1,tab2,tab3=st.tabs(["📊 Análise","🧩 Fechamento 16–17","🧬 DNA"])

        with tab1:
            st.markdown("<div class='card'>🔑 Números-chave: "+", ".join(str(n) for n in st.session_state.analise.numeros_chave)+"</div>",unsafe_allow_html=True)

        with tab2:
            st.subheader("🧩 Fechamento Inteligente (DNA)")

            tamanho=st.radio("Tamanho do fechamento",[16,17],horizontal=True)
            qtd_jogos=st.slider("Qtd de jogos (15 dezenas)",4,10,6)

            if st.button("🚀 Gerar Fechamento"):
                fechamento=st.session_state.analise.gerar_fechamento(tamanho)
                jogos=st.session_state.analise.gerar_subjogos(fechamento,qtd_jogos)

                st.markdown("<div class='card'>🔒 Fechamento Base: "+", ".join(f"{n:02d}" for n in fechamento)+"</div>",unsafe_allow_html=True)

                df=pd.DataFrame({
                    "Jogo":range(1,len(jogos)+1),
                    "Dezenas":[", ".join(f"{n:02d}" for n in j) for j in jogos],
                    "Soma":[sum(j) for j in jogos],
                    "Pares":[sum(1 for n in j if n%2==0) for j in jogos]
                })
                st.markdown("### 🎯 Jogos Gerados")
                st.dataframe(df,use_container_width=True)

        with tab3:
            st.subheader("🧬 DNA Adaptativo Atual")
            st.json(st.session_state.analise.dna)

if __name__=="__main__":
    main()
