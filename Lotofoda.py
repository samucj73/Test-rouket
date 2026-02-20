import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import warnings
warnings.filterwarnings('ignore')

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="⚡ LOTOFÁCIL - GERADOR RÁPIDO",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL - VERSÃO OTIMIZADA (RÁPIDA)
# =====================================================
class AnaliseLotofacilRapida:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # PRÉ-CALCULA TUDO para ser rápido
        self.frequencias = self._calcular_frequencias()
        self.defasagens = self._calcular_defasagens()
        self.numeros_quentes = self._numeros_quentes()
        self.numeros_frios = self._numeros_frios()
        
        # Estatísticas dos últimos concursos
        self.ultimos_10 = concursos[:10] if len(concursos) >= 10 else concursos
        self.ultimos_20 = concursos[:20] if len(concursos) >= 20 else concursos
        
    def _calcular_frequencias(self):
        """Cálculo simples e rápido de frequências"""
        todas = []
        for c in self.concursos:
            todas.extend(c)
        counter = Counter(todas)
        total = len(todas)
        return {num: (count/total)*100 for num, count in counter.items()}
    
    def _calcular_defasagens(self):
        """Cálculo rápido de defasagem"""
        defasagens = {}
        for num in self.numeros:
            for i, c in enumerate(self.concursos):
                if num in c:
                    defasagens[num] = i
                    break
            else:
                defasagens[num] = len(self.concursos)
        return defasagens
    
    def _numeros_quentes(self):
        """Números que mais saíram nos últimos 20 concursos"""
        if not self.ultimos_20:
            return []
        todas = []
        for c in self.ultimos_20:
            todas.extend(c)
        counter = Counter(todas)
        return [num for num, _ in counter.most_common(8)]
    
    def _numeros_frios(self):
        """Números que menos saíram nos últimos 20 concursos"""
        if not self.ultimos_20:
            return []
        todas = []
        for c in self.ultimos_20:
            todas.extend(c)
        counter = Counter(todas)
        return [num for num, _ in counter.most_common()[-8:]]
    
    # =================================================
    # FILTROS RÁPIDOS (OTIMIZADOS)
    # =================================================
    def verificar_filtros(self, jogo):
        """
        Verifica filtros de forma RÁPIDA
        Retorna: (bool, str)
        """
        # FILTRO 1: Consecutivos (rápido)
        consecutivos = 0
        for i in range(len(jogo)-1):
            if jogo[i+1] - jogo[i] == 1:
                consecutivos += 1
                # Se já tem 3 consecutivos, reprova
                if i < len(jogo)-2 and jogo[i+2] - jogo[i+1] == 1:
                    return False, "Sequência de 3 números"
        
        if consecutivos > 3:
            return False, f"Muitos consecutivos ({consecutivos})"
        
        # FILTRO 2: Quadrantes (rápido)
        q1 = sum(1 for n in jogo if n <= 5)
        q2 = sum(1 for n in jogo if 6 <= n <= 10)
        q3 = sum(1 for n in jogo if 11 <= n <= 15)
        q4 = sum(1 for n in jogo if 16 <= n <= 20)
        q5 = sum(1 for n in jogo if 21 <= n <= 25)
        
        if min(q1, q2, q3, q4, q5) < 1:
            return False, "Quadrante vazio"
        if max(q1, q2, q3, q4, q5) > 6:
            return False, "Quadrante sobrecarregado"
        
        # FILTRO 3: Par/Ímpar (rápido)
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares < 5 or pares > 10:
            return False, f"Pares: {pares}"
        
        # FILTRO 4: Soma (rápido)
        soma = sum(jogo)
        if soma < 180 or soma > 210:
            return False, f"Soma: {soma}"
        
        # FILTRO 5: Números quentes (rápido)
        quentes_no_jogo = sum(1 for n in jogo if n in self.numeros_quentes)
        if quentes_no_jogo < 3:
            return False, f"Poucos números quentes ({quentes_no_jogo})"
        
        return True, "OK"
    
    # =================================================
    # GERADOR RÁPIDO - SEM ALGORITMO GENÉTICO LENTO
    # =================================================
    def gerar_jogos_rapido(self, n_jogos=15):
        """
        Gera jogos de forma RÁPIDA usando amostragem inteligente
        """
        jogos = []
        tentativas = 0
        max_tentativas = n_jogos * 100  # Limite para não travar
        
        # PRÉ-CALCULA distribuição alvo
        alvo_quadrantes = [3, 3, 3, 3, 3]  # 3 números por quadrante
        
        with st.spinner("Gerando jogos..."):
            progress_bar = st.progress(0)
            
            while len(jogos) < n_jogos and tentativas < max_tentativas:
                tentativas += 1
                
                # Atualiza progresso a cada 10 tentativas
                if tentativas % 10 == 0:
                    progress_bar.progress(min(len(jogos)/n_jogos, 1.0))
                
                # GERA JOGO DE FORMA INTELIGENTE
                jogo = []
                
                # Passo 1: Distribui por quadrantes
                for q_idx, (inicio, fim) in enumerate([(1,5), (6,10), (11,15), (16,20), (21,25)]):
                    # Quantos números pegar deste quadrante
                    qtd = alvo_quadrantes[q_idx]
                    
                    # Lista de números do quadrante
                    numeros_q = list(range(inicio, fim+1))
                    
                    # Prioriza números quentes
                    quentes_q = [n for n in numeros_q if n in self.numeros_quentes]
                    frios_q = [n for n in numeros_q if n in self.numeros_frios]
                    normais_q = [n for n in numeros_q if n not in self.numeros_quentes and n not in self.numeros_frios]
                    
                    # Seleciona números para este quadrante
                    selecionados = []
                    
                    # Pega pelo menos 1 quente se possível
                    if quentes_q and len(selecionados) < qtd:
                        selecionados.append(random.choice(quentes_q))
                    
                    # Completa com normais
                    while len(selecionados) < qtd and normais_q:
                        selecionados.append(random.choice(normais_q))
                        normais_q.remove(selecionados[-1])
                    
                    # Se ainda falta, pega frios
                    while len(selecionados) < qtd and frios_q:
                        selecionados.append(random.choice(frios_q))
                        frios_q.remove(selecionados[-1])
                    
                    jogo.extend(selecionados)
                
                # Passo 2: Ordena
                jogo = sorted(jogo)
                
                # Passo 3: Verifica filtros
                aprovado, motivo = self.verificar_filtros(jogo)
                
                if aprovado and jogo not in jogos:
                    jogos.append(jogo)
            
            progress_bar.empty()
        
        # Se não gerou todos, completa com variações
        if len(jogos) < n_jogos:
            st.warning(f"Gerou {len(jogos)} de {n_jogos} jogos. Completando com variações...")
            
            while len(jogos) < n_jogos and jogos:
                # Pega um jogo existente e varia
                base = random.choice(jogos)
                novo = base.copy()
                
                # Troca 2 números
                for _ in range(2):
                    idx_troca = random.randint(0, 14)
                    numero_antigo = novo[idx_troca]
                    quadrante = (numero_antigo-1)//5
                    
                    # Busca substituto no mesmo quadrante
                    candidatos = [n for n in range(quadrante*5+1, (quadrante+1)*5+1) 
                                 if n not in novo]
                    if candidatos:
                        novo[idx_troca] = random.choice(candidatos)
                
                novo = sorted(novo)
                aprovado, _ = self.verificar_filtros(novo)
                
                if aprovado and novo not in jogos:
                    jogos.append(novo)
        
        return jogos[:n_jogos]
    
    # =================================================
    # GERADOR ULTRA RÁPIDO - PARA TESTES
    # =================================================
    def gerar_jogos_ultra_rapido(self, n_jogos=15):
        """
        Versão mais rápida ainda - usa templates pré-aprovados
        """
        # Templates de jogos que passam nos filtros
        templates = [
            [1,3,5,7,9,11,13,15,17,19,21,22,23,24,25],  # ímpares
            [2,4,6,8,10,12,14,16,18,20,21,22,23,24,25],  # pares
            [1,2,3,4,5,11,12,13,14,15,21,22,23,24,25],   # blocos
            [1,2,3,4,5,6,7,8,9,10,21,22,23,24,25],       # baixos
            [1,2,3,4,5,16,17,18,19,20,21,22,23,24,25],    # extremos
        ]
        
        jogos = []
        
        # Usa templates e varia
        for i in range(n_jogos):
            if i < len(templates):
                base = templates[i]
            else:
                base = random.choice(templates)
            
            # Varia levemente
            novo = base.copy()
            for _ in range(3):  # 3 modificações
                idx = random.randint(0, 14)
                novo[idx] = random.choice([n for n in range(1,26) if n not in novo])
            
            novo = sorted(novo)
            
            # Verifica filtros
            aprovado, _ = self.verificar_filtros(novo)
            if aprovado and novo not in jogos:
                jogos.append(novo)
            else:
                # Se não passou, tenta de novo
                for _ in range(10):
                    novo2 = random.sample(range(1,26), 15)
                    novo2 = sorted(novo2)
                    if self.verificar_filtros(novo2)[0] and novo2 not in jogos:
                        jogos.append(novo2)
                        break
        
        return jogos[:n_jogos]
    
    # =================================================
    # CONFERÊNCIA
    # =================================================
    def conferir_jogos(self, jogos, concurso_alvo=None):
        """Conferência rápida"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            
            # Análise rápida
            pares = sum(1 for n in jogo if n % 2 == 0)
            consec = 0
            for i in range(len(jogo)-1):
                if jogo[i+1] - jogo[i] == 1:
                    consec += 1
            
            aprovado, motivo = self.verificar_filtros(jogo)
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Soma": sum(jogo),
                "Pares": pares,
                "Consec": consec,
                "Status": "✅" if aprovado else "❌",
                "Motivo": motivo if not aprovado else "OK"
            })
        
        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("⚡ LOTOFÁCIL - GERADOR RÁPIDO")
    
    st.markdown("""
    ### 🚀 Versão Otimizada para Velocidade
    - ⚡ Geração em segundos (não minutos)
    - 🔧 Filtros rigorosos mas rápidos
    - 📊 Baseado em templates inteligentes
    """)
    
    # Inicialização
    if "concursos" not in st.session_state:
        st.session_state.concursos = []
    if "jogos" not in st.session_state:
        st.session_state.jogos = []
    if "analise" not in st.session_state:
        st.session_state.analise = None
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd = st.slider("Concursos para análise", 20, 200, 50, 10)
        
        if st.button("🔄 Carregar dados", type="primary"):
            with st.spinner("Carregando..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if concursos:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilRapida(concursos)
                        st.success(f"✅ {len(concursos)} concursos!")
                        
                        # Mostra estatísticas rápidas
                        st.info(f"📊 Quentes: {st.session_state.analise.numeros_quentes[:5]}")
                        st.info(f"❄️ Frios: {st.session_state.analise.numeros_frios[:5]}")
                    
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Conteúdo principal
    if st.session_state.analise:
        tab1, tab2, tab3 = st.tabs(["📊 Análise", "⚡ Gerar Jogos", "📈 Resultados"])
        
        with tab1:
            st.header("📊 Análise Rápida")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Frequências
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência dos Números (%)",
                    labels={'x': 'Número', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                # Defasagens
                fig_def = px.bar(
                    x=range(1, 26),
                    y=[st.session_state.analise.defasagens[n] for n in range(1, 26)],
                    title="Concursos sem sair",
                    labels={'x': 'Número', 'y': 'Defasagem'}
                )
                st.plotly_chart(fig_def, use_container_width=True)
        
        with tab2:
            st.header("⚡ Gerar Jogos Rápidos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                qtd_jogos = st.number_input("Quantidade", 5, 50, 15)
            
            with col2:
                modo = st.selectbox(
                    "Modo de geração",
                    ["⚡ Rápido", "🚀 Ultra Rápido"]
                )
            
            if st.button("🎲 Gerar jogos agora!", type="primary"):
                start_time = time.time()
                
                if modo == "⚡ Rápido":
                    st.session_state.jogos = st.session_state.analise.gerar_jogos_rapido(qtd_jogos)
                else:
                    st.session_state.jogos = st.session_state.analise.gerar_jogos_ultra_rapido(qtd_jogos)
                
                elapsed = time.time() - start_time
                st.success(f"✅ {len(st.session_state.jogos)} jogos em {elapsed:.2f} segundos!")
        
        with tab3:
            if st.session_state.jogos:
                st.header("📈 Resultados")
                
                # Input manual
                with st.expander("🔢 Inserir resultado"):
                    res_input = st.text_input(
                        "Números (separados por vírgula)",
                        placeholder="01,04,05,06,10,11,13,14,16,18,19,20,21,23,24"
                    )
                    if st.button("Conferir"):
                        try:
                            nums = [int(x.strip()) for x in res_input.split(',')]
                            if len(nums) == 15:
                                st.session_state.resultado = sorted(nums)
                                st.success("OK!")
                        except:
                            st.error("Inválido")
                
                concurso_alvo = st.session_state.get('resultado', 
                                                     st.session_state.analise.ultimo_concurso)
                
                # Conferência
                resultado = st.session_state.analise.conferir_jogos(
                    st.session_state.jogos, concurso_alvo
                )
                df = pd.DataFrame(resultado)
                st.dataframe(df, use_container_width=True)
                
                # Estatísticas
                st.subheader("📊 Distribuição")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Média", f"{df['Acertos'].mean():.2f}")
                with col2:
                    st.metric("Máximo", df['Acertos'].max())
                with col3:
                    st.metric("Mínimo", df['Acertos'].min())
                with col4:
                    acima_11 = sum(df['Acertos'] >= 11)
                    st.metric("≥11 pontos", acima_11)
                
                # Gráfico
                fig = px.histogram(df, x='Acertos', nbins=15)
                st.plotly_chart(fig, use_container_width=True)
                
                # Export
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Exportar CSV",
                    data=csv,
                    file_name=f"jogos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )
            else:
                st.info("ℹ️ Gere jogos primeiro!")

if __name__ == "__main__":
    main()
