import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timedelta
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
# FUNÇÕES DE ARQUIVO LOCAL
# =====================================================
def salvar_jogos_gerados(jogos, fechamento, dna_params):
    """Salva os jogos gerados em arquivo JSON local"""
    try:
        # Criar diretório se não existir
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        
        # Gerar ID único
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/fechamento_{data_hora}_{jogo_id}.json"
        
        # Preparar dados
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_alvo": "Próximo sorteio futuro",
            "fechamento_base": fechamento,
            "dna_params": dna_params,
            "jogos": jogos,
            "conferido": False,
            "resultado_futuro": None,
            "acertos": None,
            "concurso_conferido": None
        }
        
        # Salvar arquivo
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_salvos():
    """Carrega todos os jogos salvos"""
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos"):
            for arquivo in os.listdir("jogos_salvos"):
                if arquivo.endswith(".json"):
                    with open(f"jogos_salvos/{arquivo}", 'r', encoding='utf-8') as f:
                        dados = json.load(f)
                        dados["arquivo"] = arquivo
                        jogos_salvos.append(dados)
            
            # Ordenar por data (mais recentes primeiro)
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos salvos: {e}")
    
    return jogos_salvos

def atualizar_conferencia(arquivo, resultado, acertos, concurso_info):
    """Atualiza arquivo com resultado da conferência"""
    try:
        caminho = f"jogos_salvos/{arquivo}"
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        dados["conferido"] = True
        dados["resultado_futuro"] = resultado
        dados["acertos"] = acertos
        dados["concurso_conferido"] = concurso_info
        dados["data_conferencia"] = datetime.now().isoformat()
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar conferência: {e}")
        return False

def buscar_concursos_futuros(api_data, data_referencia):
    """Busca concursos que ocorreram APÓS a data de referência"""
    try:
        if not api_data:
            return []
        
        # Converter data_referencia para datetime
        if isinstance(data_referencia, str):
            data_ref = datetime.fromisoformat(data_referencia).date()
        else:
            data_ref = data_referencia.date() if hasattr(data_referencia, 'date') else data_referencia
        
        concursos_futuros = []
        for concurso in api_data:
            # Converter data do concurso
            data_concurso = datetime.strptime(concurso["data"], "%d/%m/%Y").date()
            
            # Se a data do concurso é MAIOR que a data de referência
            if data_concurso > data_ref:
                concursos_futuros.append(concurso)
        
        return concursos_futuros
    except Exception as e:
        st.error(f"Erro ao filtrar concursos futuros: {e}")
        return []

def verificar_se_concurso_eh_futuro(data_concurso, data_referencia):
    """Verifica se a data do concurso é futura em relação à data de referência"""
    try:
        if isinstance(data_concurso, str):
            data_conc = datetime.strptime(data_concurso, "%d/%m/%Y").date()
        else:
            data_conc = data_concurso
        
        if isinstance(data_referencia, str):
            data_ref = datetime.fromisoformat(data_referencia).date()
        else:
            data_ref = data_referencia.date() if hasattr(data_referencia, 'date') else data_referencia
        
        return data_conc > data_ref
    except:
        return False

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
    if "dados_api" not in st.session_state: st.session_state.dados_api=None
    if "jogos_salvos" not in st.session_state: st.session_state.jogos_salvos=[]

    # ================= SIDEBAR =================
    with st.sidebar:
        qtd=st.slider("Qtd concursos históricos",50,1000,200)
        if st.button("📥 Carregar concursos"):
            url="https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            st.session_state.dados_api = requests.get(url).json()
            concursos=[sorted(map(int,d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
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
        tab1,tab2,tab3,tab4=st.tabs(["📊 Análise","🧩 Fechamento","🧬 DNA","✅ Conferência"])

        with tab1:
            st.markdown("<div class='card'>🔑 Números-chave: "+", ".join(str(n) for n in st.session_state.analise.numeros_chave)+"</div>",unsafe_allow_html=True)

        with tab2:
            st.subheader("🧩 Fechamento Inteligente (DNA)")

            tamanho=st.radio("Tamanho do fechamento",[16,17],horizontal=True, key="tam_fech")
            qtd_jogos=st.slider("Qtd de jogos (15 dezenas)",4,10,6, key="qtd_jogos")

            if st.button("🚀 Gerar e Salvar Fechamento"):
                fechamento=st.session_state.analise.gerar_fechamento(tamanho)
                jogos=st.session_state.analise.gerar_subjogos(fechamento,qtd_jogos)
                
                # Salvar jogos em arquivo
                arquivo, jogo_id = salvar_jogos_gerados(jogos, fechamento, st.session_state.analise.dna)
                
                if arquivo:
                    st.success(f"✅ Fechamento salvo com ID: {jogo_id}")
                    st.markdown("<div class='card'>🔒 Fechamento Base: "+", ".join(f"{n:02d}" for n in fechamento)+"</div>",unsafe_allow_html=True)
                    
                    # Atualizar lista de jogos salvos
                    st.session_state.jogos_salvos = carregar_jogos_salvos()
                    
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

        with tab4:
            st.subheader("✅ Conferência com Sorteio Futuro")
            
            # Carregar jogos salvos
            st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            if not st.session_state.jogos_salvos:
                st.warning("Nenhum jogo salvo encontrado. Gere um fechamento na aba anterior.")
            else:
                # Selecionar jogo para conferir
                opcoes = []
                for i, jogo in enumerate(st.session_state.jogos_salvos[:10]):  # Últimos 10
                    data = datetime.fromisoformat(jogo["data_geracao"]).strftime("%d/%m/%Y %H:%M")
                    status = "✅ Conferido" if jogo.get("conferido") else "⏳ Aguardando"
                    opcoes.append(f"{i+1} - {status} - {data} (ID: {jogo['id']})")
                
                selecao = st.selectbox("Selecione o fechamento para conferir", opcoes)
                
                if selecao:
                    idx = int(selecao.split(" - ")[0]) - 1
                    jogo_selecionado = st.session_state.jogos_salvos[idx]
                    
                    st.markdown("### 📋 Detalhes do Fechamento")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**ID:** {jogo_selecionado['id']}")
                        data_geracao = datetime.fromisoformat(jogo_selecionado["data_geracao"])
                        st.markdown(f"**Data Geração:** {data_geracao.strftime('%d/%m/%Y %H:%M')}")
                    with col2:
                        st.markdown(f"**Status:** {'✅ Conferido' if jogo_selecionado.get('conferido') else '⏳ Aguardando'}")
                        st.markdown(f"**Fechamento Base:** {jogo_selecionado['fechamento_base']}")
                    
                    if jogo_selecionado.get("conferido"):
                        concurso_info = jogo_selecionado.get("concurso_conferido", {})
                        st.info(f"✅ Já conferido com o concurso {concurso_info.get('concurso', 'N/A')} - {concurso_info.get('data', 'N/A')}")
                        st.markdown(f"**Resultado:** {jogo_selecionado['resultado_futuro']}")
                        st.metric("Melhor acerto", f"{max(jogo_selecionado['acertos'])} pontos")
                        
                        # Mostrar tabela de acertos
                        df_resultado = pd.DataFrame({
                            "Jogo": range(1, len(jogo_selecionado["jogos"]) + 1),
                            "Acertos": jogo_selecionado["acertos"]
                        })
                        st.dataframe(df_resultado, use_container_width=True)
                    
                    # Botão para conferir (apenas se não conferido ainda)
                    if not jogo_selecionado.get("conferido"):
                        if st.button("🔍 Buscar Concursos Futuros"):
                            if st.session_state.dados_api:
                                # Buscar concursos que ocorreram APÓS a data de geração
                                concursos_futuros = buscar_concursos_futuros(
                                    st.session_state.dados_api, 
                                    jogo_selecionado["data_geracao"]
                                )
                                
                                if not concursos_futuros:
                                    st.warning("⏳ Ainda não houve sorteio futuro desde a data de geração deste fechamento. Aguarde o próximo sorteio!")
                                else:
                                    st.success(f"📅 Encontrados {len(concursos_futuros)} concursos futuros!")
                                    
                                    # Mostrar opções de concursos futuros
                                    opcoes_futuros = []
                                    for conc in concursos_futuros[:5]:  # Mostrar até 5 futuros
                                        opcoes_futuros.append(f"Concurso {conc['concurso']} - {conc['data']}")
                                    
                                    concurso_selecionado = st.selectbox(
                                        "Selecione o concurso futuro para conferir",
                                        opcoes_futuros,
                                        key="concurso_futuro"
                                    )
                                    
                                    if concurso_selecionado and st.button("✅ Confirmar Conferência"):
                                        # Extrair número do concurso selecionado
                                        num_concurso = int(concurso_selecionado.split(" - ")[0].replace("Concurso ", ""))
                                        
                                        # Encontrar o concurso completo
                                        concurso_info = next(
                                            (c for c in concursos_futuros if c["concurso"] == num_concurso), 
                                            None
                                        )
                                        
                                        if concurso_info:
                                            numeros_sorteados = sorted(map(int, concurso_info["dezenas"]))
                                            
                                            st.info(f"📊 Conferindo com Concurso {concurso_info['concurso']} - {concurso_info['data']}")
                                            st.write(f"Números sorteados: {numeros_sorteados}")
                                            
                                            # Conferir jogos
                                            acertos_por_jogo = []
                                            for jogo in jogo_selecionado["jogos"]:
                                                acertos = len(set(jogo) & set(numeros_sorteados))
                                                acertos_por_jogo.append(acertos)
                                            
                                            # Atualizar arquivo
                                            if atualizar_conferencia(
                                                jogo_selecionado["arquivo"], 
                                                numeros_sorteados, 
                                                acertos_por_jogo,
                                                {"concurso": concurso_info["concurso"], "data": concurso_info["data"]}
                                            ):
                                                st.success(f"✅ Conferência realizada com o concurso {concurso_info['concurso']}!")
                                                
                                                # Mostrar resultados
                                                df_resultado = pd.DataFrame({
                                                    "Jogo": range(1, len(jogo_selecionado["jogos"]) + 1),
                                                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogo_selecionado["jogos"]],
                                                    "Acertos": acertos_por_jogo
                                                })
                                                st.dataframe(df_resultado, use_container_width=True)
                                                
                                                # Estatísticas
                                                col1, col2, col3 = st.columns(3)
                                                with col1:
                                                    st.metric("Média acertos", f"{np.mean(acertos_por_jogo):.1f}")
                                                with col2:
                                                    st.metric("Máximo", f"{max(acertos_por_jogo)}")
                                                with col3:
                                                    st.metric("Mínimo", f"{min(acertos_por_jogo)}")
                                                
                                                # Recarregar lista
                                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                                                st.rerun()
                            else:
                                st.error("Carregue os concursos primeiro na barra lateral!")

if __name__=="__main__":
    main()
