import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
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
.concurso-info { background: #1e1e2e; padding: 10px; border-radius: 10px; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL PREMIUM")
st.caption("DNA • Fechamento • Conferência por Concurso • Mobile First")

# =====================================================
# FUNÇÕES DE ARQUIVO LOCAL
# =====================================================
def salvar_jogos_gerados(jogos, fechamento, dna_params, numero_concurso_atual, data_concurso_atual):
    """Salva os jogos gerados em arquivo JSON local com o número do concurso atual"""
    try:
        # Criar diretório se não existir
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        
        # Gerar ID único
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/fechamento_{data_hora}_{jogo_id}.json"
        
        # Preparar dados com número do concurso atual
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_base": {
                "numero": numero_concurso_atual,
                "data": data_concurso_atual
            },
            "fechamento_base": fechamento,
            "dna_params": dna_params,
            "jogos": jogos,
            "conferido": False,
            "conferencias": []  # Lista para múltiplas conferências futuras
        }
        
        # Salvar arquivo
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_salvos():
    """Carrega todos os jogos salvos com compatibilidade para versões antigas"""
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos"):
            for arquivo in os.listdir("jogos_salvos"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos/{arquivo}", 'r', encoding='utf-8') as f:
                            dados = json.load(f)
                            
                            # === COMPATIBILIDADE COM VERSÕES ANTIGAS ===
                            # Verificar se é um formato antigo (sem concurso_base)
                            if "concurso_base" not in dados:
                                # Converter formato antigo para novo
                                dados["concurso_base"] = {
                                    "numero": 0,  # Valor padrão para arquivos antigos
                                    "data": "Desconhecido"
                                }
                            
                            # Verificar se tem campo conferencias
                            if "conferencias" not in dados:
                                # Se tem resultado_futuro antigo, converter para conferencias
                                if dados.get("resultado_futuro") and dados.get("acertos"):
                                    dados["conferencias"] = [{
                                        "concurso": {
                                            "numero": dados.get("concurso_conferido", {}).get("numero", 0),
                                            "data": dados.get("concurso_conferido", {}).get("data", "Desconhecido"),
                                            "resultado": dados.get("resultado_futuro", [])
                                        },
                                        "acertos": dados.get("acertos", []),
                                        "data_conferencia": dados.get("data_conferencia", dados.get("data_geracao"))
                                    }]
                                else:
                                    dados["conferencias"] = []
                            
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception as e:
                        st.warning(f"Erro ao ler arquivo {arquivo}: {e}")
                        continue
            
            # Ordenar por data (mais recentes primeiro)
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos salvos: {e}")
    
    return jogos_salvos

def adicionar_conferencia(arquivo, concurso_info, acertos):
    """Adiciona uma nova conferência ao histórico do fechamento"""
    try:
        caminho = f"jogos_salvos/{arquivo}"
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        # Inicializar lista de conferências se não existir
        if "conferencias" not in dados:
            dados["conferencias"] = []
        
        # Adicionar nova conferência
        nova_conferencia = {
            "concurso": concurso_info,
            "acertos": acertos,
            "data_conferencia": datetime.now().isoformat()
        }
        
        dados["conferencias"].append(nova_conferencia)
        dados["conferido"] = True  # Marcar como conferido pelo menos uma vez
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar conferência: {e}")
        return False

def verificar_concurso_futuro(concurso_analisado, concurso_futuro):
    """Verifica se o concurso futuro é realmente posterior ao concurso base"""
    return concurso_futuro > concurso_analisado

# =====================================================
# CLASSE PRINCIPAL
# =====================================================
class AnaliseLotofacilAvancada:

    def __init__(self, concursos, dados_completos=None):
        self.concursos = concursos
        self.dados_completos = dados_completos or []
        self.ultimo_concurso = concursos[0] if concursos else []
        self.ultimo_concurso_numero = dados_completos[0]["concurso"] if dados_completos else 0
        self.ultimo_concurso_data = dados_completos[0]["data"] if dados_completos else ""
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
# FUNÇÃO PARA OBTER INFO DO CONCURSO COM SEGURANÇA
# =====================================================
def get_concurso_info_seguro(jogo):
    """Obtém informações do concurso base de forma segura"""
    try:
        if "concurso_base" in jogo:
            return jogo["concurso_base"]
        else:
            return {"numero": 0, "data": "Formato antigo"}
    except:
        return {"numero": 0, "data": "Desconhecido"}

def get_conferencias_seguro(jogo):
    """Obtém lista de conferências de forma segura"""
    try:
        if "conferencias" in jogo:
            return jogo["conferencias"]
        else:
            return []
    except:
        return []

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
            st.session_state.analise=AnaliseLotofacilAvancada(concursos, st.session_state.dados_api[:qtd])
            st.session_state.analise.auto_ajustar_dna(concursos[0])
            
            # Mostrar informação do último concurso
            ultimo = st.session_state.dados_api[0]
            st.success(f"✅ Concursos carregados - Último: #{ultimo['concurso']} - {ultimo['data']}")

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
        tab1,tab2,tab3,tab4=st.tabs(["📊 Análise","🧩 Fechamento","🧬 DNA","✅ Conferência por Concurso"])

        with tab1:
            st.markdown("<div class='card'>🔑 Números-chave: "+", ".join(str(n) for n in st.session_state.analise.numeros_chave)+"</div>",unsafe_allow_html=True)

        with tab2:
            st.subheader("🧩 Fechamento Inteligente (DNA)")
            
            # Mostrar concurso atual
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                st.markdown(f"""
                <div class='concurso-info'>
                    📅 <strong>Concurso base atual:</strong> #{ultimo['concurso']} - {ultimo['data']}
                </div>
                """, unsafe_allow_html=True)

            tamanho=st.radio("Tamanho do fechamento",[16,17],horizontal=True, key="tam_fech")
            qtd_jogos=st.slider("Qtd de jogos (15 dezenas)",4,10,6, key="qtd_jogos")

            if st.button("🚀 Gerar e Salvar Fechamento"):
                fechamento=st.session_state.analise.gerar_fechamento(tamanho)
                jogos=st.session_state.analise.gerar_subjogos(fechamento,qtd_jogos)
                
                # Salvar jogos em arquivo com número do concurso atual
                ultimo = st.session_state.dados_api[0]
                arquivo, jogo_id = salvar_jogos_gerados(
                    jogos, 
                    fechamento, 
                    st.session_state.analise.dna,
                    ultimo['concurso'],
                    ultimo['data']
                )
                
                if arquivo:
                    st.success(f"✅ Fechamento salvo com ID: {jogo_id} (Baseado no concurso #{ultimo['concurso']})")
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
            st.subheader("✅ Conferência por Número de Concurso")
            
            # Carregar jogos salvos
            st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            if not st.session_state.jogos_salvos:
                st.warning("Nenhum jogo salvo encontrado. Gere um fechamento na aba anterior.")
            elif not st.session_state.dados_api:
                st.warning("Carregue os concursos primeiro na barra lateral!")
            else:
                # Último concurso disponível
                ultimo_concurso_api = st.session_state.dados_api[0]
                
                # Filtrar apenas fechamentos NÃO conferidos
                fechamentos_nao_conferidos = []
                for j in st.session_state.jogos_salvos:
                    # Verificar se tem conferências
                    conferencias = get_conferencias_seguro(j)
                    if len(conferencias) == 0:
                        fechamentos_nao_conferidos.append(j)
                
                if not fechamentos_nao_conferidos:
                    st.info("✅ Todos os fechamentos já foram conferidos!")
                    
                    # Mostrar histórico de todos os fechamentos
                    with st.expander("📜 Ver histórico completo de fechamentos"):
                        for jogo in st.session_state.jogos_salvos:
                            status = "✅" if get_conferencias_seguro(jogo) else "⏳"
                            data = datetime.fromisoformat(jogo["data_geracao"]).strftime("%d/%m/%Y")
                            concurso_base = get_concurso_info_seguro(jogo)
                            st.write(f"{status} ID: {jogo['id']} - Base: #{concurso_base['numero']} - {data}")
                else:
                    st.markdown(f"""
                    <div class='concurso-info'>
                        🎯 <strong>Último concurso disponível:</strong> #{ultimo_concurso_api['concurso']} - {ultimo_concurso_api['data']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Selecionar fechamento para conferir
                    opcoes = []
                    for i, jogo in enumerate(fechamentos_nao_conferidos[:10]):
                        data = datetime.fromisoformat(jogo["data_geracao"]).strftime("%d/%m/%Y %H:%M")
                        concurso_base = get_concurso_info_seguro(jogo)
                        opcoes.append(f"{i+1} - Fechamento baseado no concurso #{concurso_base['numero']} - {data} (ID: {jogo['id']})")
                    
                    if opcoes:
                        selecao = st.selectbox("Selecione o fechamento para conferir", opcoes)
                        
                        if selecao:
                            idx = int(selecao.split(" - ")[0]) - 1
                            jogo_selecionado = fechamentos_nao_conferidos[idx]
                            concurso_base = get_concurso_info_seguro(jogo_selecionado)
                            
                            st.markdown("### 📋 Detalhes do Fechamento")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**ID:** {jogo_selecionado['id']}")
                                st.markdown(f"**Baseado no concurso:** #{concurso_base['numero']}")
                                st.markdown(f"**Data do concurso base:** {concurso_base['data']}")
                            with col2:
                                st.markdown(f"**Data geração:** {datetime.fromisoformat(jogo_selecionado['data_geracao']).strftime('%d/%m/%Y %H:%M')}")
                                st.markdown(f"**Fechamento base:** {jogo_selecionado['fechamento_base']}")
                            
                            # Verificar se há concurso futuro disponível
                            concurso_base_num = concurso_base['numero']
                            concurso_atual_num = ultimo_concurso_api['concurso']
                            
                            if concurso_atual_num <= concurso_base_num:
                                st.warning(f"⏳ Aguardando sorteio futuro... (Concurso base: #{concurso_base_num} | Atual: #{concurso_atual_num})")
                                st.info("O próximo sorteio ainda não ocorreu. Volte após o resultado!")
                            else:
                                # Encontrar todos os concursos futuros disponíveis
                                concursos_futuros = []
                                for conc in st.session_state.dados_api:
                                    if conc['concurso'] > concurso_base_num:
                                        concursos_futuros.append(conc)
                                
                                if concursos_futuros:
                                    st.success(f"✅ {len(concursos_futuros)} concurso(s) futuro(s) disponível(is)!")
                                    
                                    # Opções de concursos futuros
                                    opcoes_futuros = []
                                    for conc in concursos_futuros[:5]:  # Mostrar até 5
                                        opcoes_futuros.append(f"Concurso #{conc['concurso']} - {conc['data']}")
                                    
                                    concurso_futuro_sel = st.selectbox(
                                        "Selecione o concurso futuro para conferir",
                                        opcoes_futuros,
                                        key="futuro_sel"
                                    )
                                    
                                    if concurso_futuro_sel and st.button("🔍 Conferir com concurso selecionado"):
                                        # Extrair número do concurso
                                        num_futuro = int(concurso_futuro_sel.split(" - ")[0].replace("Concurso #", ""))
                                        
                                        # Encontrar dados do concurso
                                        concurso_info = next(c for c in concursos_futuros if c['concurso'] == num_futuro)
                                        numeros_sorteados = sorted(map(int, concurso_info["dezenas"]))
                                        
                                        # Calcular acertos
                                        acertos_por_jogo = []
                                        for jogo in jogo_selecionado["jogos"]:
                                            acertos = len(set(jogo) & set(numeros_sorteados))
                                            acertos_por_jogo.append(acertos)
                                        
                                        # Salvar conferência
                                        concurso_info_salvar = {
                                            "numero": concurso_info["concurso"],
                                            "data": concurso_info["data"],
                                            "resultado": numeros_sorteados
                                        }
                                        
                                        if adicionar_conferencia(jogo_selecionado["arquivo"], concurso_info_salvar, acertos_por_jogo):
                                            st.success(f"✅ Conferência realizada com sucesso para o concurso #{num_futuro}!")
                                            
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
                                            
                                            # Mostrar distribuição de acertos
                                            dist = Counter(acertos_por_jogo)
                                            st.markdown("**Distribuição de acertos:**")
                                            for pontos in sorted(dist.keys()):
                                                st.markdown(f"- {pontos} pontos: {dist[pontos]} jogo(s)")
                                            
                                            st.rerun()
                                else:
                                    st.warning("Nenhum concurso futuro encontrado na API!")
                    else:
                        st.info("Nenhum fechamento não conferido encontrado.")

if __name__=="__main__":
    main()
