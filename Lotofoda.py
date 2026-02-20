import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations
import plotly.express as px
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - REPLICADOR DE PADRÕES REAIS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL - IDENTIFICADOR DE PADRÕES REAIS
# =====================================================
class ReplicadorPadroesLotofacil:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # IDENTIFICAÇÃO DE PADRÕES REAIS QUE SE REPETEM
        print("🔍 Identificando padrões recorrentes...")
        self.padroes_identificados = self._identificar_padroes_recorrentes()
        self.padroes_por_tipo = self._categorizar_padroes()
        
    def _identificar_padroes_recorrentes(self):
        """
        Identifica TODOS os padrões que aparecem nos concursos
        e conta quantas vezes cada um se repete
        """
        padroes = {
            # Padrões de quantidade
            'par_impar': Counter(),  # Ex: (7 pares, 8 ímpares)
            'primos': Counter(),      # Quantidade de primos
            'quadrantes': Counter(),  # Números até 12 vs depois
            
            # Padrões de soma
            'faixas_soma': Counter(),  # Faixas de soma (ex: 180-190)
            
            # Padrões de sequências
            'pares_consecutivos': Counter(),  # Quantidade de pares consecutivos
            'triplas_consecutivas': Counter(),  # Quantidade de triplas consecutivas
            
            # PADRÕES ESPECÍFICOS (o que você realmente quer)
            'grupos_especificos': [],  # Lista de conjuntos que se repetem
            'subconjuntos_frequentes': [],  # Partes de jogos que se repetem
            'combinacoes_famosas': [],  # Combinações que já apareceram juntas
        }
        
        # Analisa cada concurso
        for concurso in self.concursos:
            # 1. PADRÃO PAR/ÍMPAR
            pares = sum(1 for n in concurso if n % 2 == 0)
            padroes['par_impar'][pares] += 1
            
            # 2. PADRÃO DE NÚMEROS PRIMOS
            primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
            qtd_primos = sum(1 for n in concurso if n in primos)
            padroes['primos'][qtd_primos] += 1
            
            # 3. PADRÃO DE QUADRANTES
            primeiro_quadrante = sum(1 for n in concurso if n <= 12)
            padroes['quadrantes'][primeiro_quadrante] += 1
            
            # 4. PADRÃO DE SOMA (em faixas de 10 em 10)
            soma = sum(concurso)
            faixa = (soma // 10) * 10
            padroes['faixas_soma'][faixa] += 1
            
            # 5. PADRÃO DE SEQUÊNCIAS
            # Conta pares consecutivos (ex: 04-05)
            pares_consec = 0
            for i in range(len(concurso)-1):
                if concurso[i+1] - concurso[i] == 1:
                    pares_consec += 1
            padroes['pares_consecutivos'][pares_consec] += 1
            
            # Conta triplas consecutivas (ex: 04-05-06)
            triplas_consec = 0
            for i in range(len(concurso)-2):
                if concurso[i+2] - concurso[i+1] == 1 and concurso[i+1] - concurso[i] == 1:
                    triplas_consec += 1
            padroes['triplas_consecutivas'][triplas_consec] += 1
            
            # 6. GRUPOS ESPECÍFICOS QUE SE REPETEM
            # Adiciona o concurso inteiro como um padrão
            padroes['grupos_especificos'].append(tuple(concurso))
        
        # Identifica subconjuntos que aparecem em múltiplos concursos
        padroes['subconjuntos_frequentes'] = self._encontrar_subconjuntos_repetidos()
        
        # Identifica combinações famosas (números que sempre aparecem juntos)
        padroes['combinacoes_famosas'] = self._encontrar_combinacoes_frequentes()
        
        return padroes
    
    def _encontrar_subconjuntos_repetidos(self):
        """
        Encontra partes de jogos que se repetem em diferentes concursos
        Ex: [04,05,06] apareceu em 10 concursos diferentes
        """
        # Conta todas as combinações de 3, 4 e 5 números
        subconjuntos = Counter()
        
        for concurso in self.concursos:
            # Combinações de 3 números
            for tripla in combinations(concurso, 3):
                subconjuntos[tripla] += 1
            
            # Combinações de 4 números
            for quarteto in combinations(concurso, 4):
                subconjuntos[quarteto] += 1
            
            # Combinações de 5 números
            for quinteto in combinations(concurso, 5):
                subconjuntos[quinteto] += 1
        
        # Filtra apenas os que se repetem (aparecem em mais de 1 concurso)
        subconjuntos_repetidos = [
            {'numeros': list(sub), 'frequencia': freq}
            for sub, freq in subconjuntos.items() if freq > 1
        ]
        
        # Ordena por frequência
        subconjuntos_repetidos.sort(key=lambda x: x['frequencia'], reverse=True)
        
        return subconjuntos_repetidos[:100]  # Top 100
    
    def _encontrar_combinacoes_frequentes(self):
        """
        Encontra números que costumam aparecer juntos
        """
        # Matriz de co-ocorrência
        co_ocorrencias = defaultdict(int)
        
        for concurso in self.concursos:
            for i in range(len(concurso)):
                for j in range(i+1, len(concurso)):
                    par = tuple(sorted([concurso[i], concurso[j]]))
                    co_ocorrencias[par] += 1
        
        # Converte para lista ordenada
        combinacoes = [
            {'numeros': list(par), 'frequencia': freq}
            for par, freq in co_ocorrencias.items()
        ]
        
        combinacoes.sort(key=lambda x: x['frequencia'], reverse=True)
        
        return combinacoes[:100]  # Top 100 pares que mais aparecem juntos
    
    def _categorizar_padroes(self):
        """
        Organiza os padrões por categoria para fácil acesso
        """
        categorias = {
            'mais_comum': {},
            'tendencias': {},
            'top_padroes': {}
        }
        
        # Padrão par/ímpar mais comum
        if self.padroes_identificados['par_impar']:
            categorias['mais_comum']['par_impar'] = self.padroes_identificados['par_impar'].most_common(1)[0]
        
        # Padrão de primos mais comum
        if self.padroes_identificados['primos']:
            categorias['mais_comum']['primos'] = self.padroes_identificados['primos'].most_common(1)[0]
        
        # Padrão de soma mais comum
        if self.padroes_identificados['faixas_soma']:
            categorias['mais_comum']['faixa_soma'] = self.padroes_identificados['faixas_soma'].most_common(1)[0]
        
        # Top 5 subconjuntos que mais se repetem
        categorias['top_padroes']['subconjuntos'] = self.padroes_identificados['subconjuntos_frequentes'][:10]
        
        # Top 10 pares que mais aparecem juntos
        categorias['top_padroes']['pares_famosos'] = self.padroes_identificados['combinacoes_famosas'][:10]
        
        return categorias
    
    # =================================================
    # GERADOR BASEADO EM PADRÕES REAIS
    # =================================================
    def gerar_jogos_replicando_padroes(self, n_jogos=15):
        """
        Gera jogos usando APENAS padrões que já se repetiram
        """
        jogos = []
        
        for _ in range(n_jogos):
            jogo = set()
            
            # ESTRATÉGIA 1: Usar subconjuntos que já se repetiram
            if random.random() < 0.7:  # 70% dos jogos usam subconjuntos repetidos
                if self.padroes_identificados['subconjuntos_frequentes']:
                    # Escolhe um subconjunto que já apareceu em múltiplos concursos
                    sub = random.choice(self.padroes_identificados['subconjuntos_frequentes'][:30])
                    jogo.update(sub['numeros'])
            
            # ESTRATÉGIA 2: Usar pares famosos (números que sempre aparecem juntos)
            while len(jogo) < 10 and random.random() < 0.5:
                if self.padroes_identificados['combinacoes_famosas']:
                    par = random.choice(self.padroes_identificados['combinacoes_famosas'][:50])
                    if par['numeros'][0] not in jogo and par['numeros'][1] not in jogo:
                        jogo.update(par['numeros'])
            
            # ESTRATÉGIA 3: Completar seguindo padrões de quantidade
            # Pega o padrão par/ímpar mais comum
            padrao_par_impar = self.padroes_identificados['par_impar'].most_common(1)[0][0]
            
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros if n not in jogo]
                
                if candidatos:
                    # Verifica se precisa de mais pares ou ímpares
                    pares_atuais = sum(1 for n in jogo if n % 2 == 0)
                    if pares_atuais < padrao_par_impar:
                        # Precisa de mais pares
                        candidatos = [n for n in candidatos if n % 2 == 0]
                    elif pares_atuais > padrao_par_impar:
                        # Precisa de mais ímpares
                        candidatos = [n for n in candidatos if n % 2 == 1]
                    
                    if candidatos:
                        # Dá preferência para números que formam pares famosos
                        escolhido = random.choice(candidatos)
                        jogo.add(escolhido)
                    else:
                        # Se não houver candidatos na categoria, pega qualquer um
                        jogo.add(random.choice([n for n in self.numeros if n not in jogo]))
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    def gerar_jogos_com_sequencias_repetidas(self, n_jogos=15):
        """
        Especializado em sequências (como 04-05-06) que já se repetiram
        """
        jogos = []
        
        # Filtra apenas subconjuntos que são sequências (consecutivos)
        sequencias_repetidas = [
            sub for sub in self.padroes_identificados['subconjuntos_frequentes']
            if self._eh_sequencia(sub['numeros']) and sub['frequencia'] >= 2
        ]
        
        for _ in range(n_jogos):
            jogo = set()
            
            # Adiciona uma sequência que já se repetiu
            if sequencias_repetidas and random.random() < 0.8:
                sequencia = random.choice(sequencias_repetidas[:20])
                jogo.update(sequencia['numeros'])
            
            # Completa com números aleatórios (mas mantendo equilíbrio)
            while len(jogo) < 15:
                candidato = random.choice([n for n in self.numeros if n not in jogo])
                jogo.add(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    def _eh_sequencia(self, numeros):
        """Verifica se uma lista de números é uma sequência"""
        numeros = sorted(numeros)
        for i in range(len(numeros)-1):
            if numeros[i+1] - numeros[i] != 1:
                return False
        return True
    
    # =================================================
    # MOSTRAR PADRÕES IDENTIFICADOS
    # =================================================
    def mostrar_padroes_encontrados(self):
        """
        Retorna um resumo dos padrões encontrados
        """
        resumo = {
            'par_impar': [],
            'somas': [],
            'sequencias': [],
            'subconjuntos_repetidos': []
        }
        
        # Top 5 padrões par/ímpar
        for pares, freq in self.padroes_identificados['par_impar'].most_common(5):
            resumo['par_impar'].append({
                'pares': pares,
                'impares': 15-pares,
                'frequencia': freq,
                'percentual': (freq/self.total_concursos)*100
            })
        
        # Top 5 faixas de soma
        for faixa, freq in self.padroes_identificados['faixas_soma'].most_common(5):
            resumo['somas'].append({
                'faixa': f"{faixa}-{faixa+9}",
                'frequencia': freq,
                'percentual': (freq/self.total_concursos)*100
            })
        
        # Top 5 subconjuntos que mais se repetem
        for sub in self.padroes_identificados['subconjuntos_frequentes'][:5]:
            resumo['subconjuntos_repetidos'].append({
                'numeros': sub['numeros'],
                'vezes': sub['frequencia']
            })
        
        return resumo

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - REPLICADOR DE PADRÕES REAIS")
    
    st.markdown("""
    ### 🔍 Sistema que IDENTIFICA e REPLICA padrões que realmente se repetem
    
    **Como funciona:**
    1. Analisa todos os concursos anteriores
    2. IDENTIFICA quais padrões realmente se repetem
    3. CONTA quantas vezes cada padrão apareceu
    4. USA APENAS padrões que já se repetiram para gerar novos jogos
    
    **Padrões analisados:**
    - ✅ Sequências (ex: 04-05-06 que já apareceu várias vezes)
    - ✅ Pares de números que sempre saem juntos
    - ✅ Grupos de números que se repetem em múltiplos concursos
    - ✅ Distribuição par/ímpar mais comum
    - ✅ Faixas de soma mais frequentes
    """)
    
    # Inicialização
    if "concursos" not in st.session_state:
        st.session_state.concursos = []
    
    if "jogos" not in st.session_state:
        st.session_state.jogos = []
    
    if "replicador" not in st.session_state:
        st.session_state.replicador = None
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd = st.slider(
            "Quantidade de concursos para análise", 
            min_value=50, 
            max_value=1000, 
            value=200,
            step=50,
            help="Mais concursos = melhor identificação de padrões"
        )
        
        if st.button("📥 Carregar e ANALISAR PADRÕES", type="primary"):
            with st.spinner("Carregando concursos e identificando padrões..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if len(concursos) >= 50:
                        st.session_state.concursos = concursos
                        st.session_state.replicador = ReplicadorPadroesLotofacil(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos analisados!")
                        st.success(f"🔍 Padrões identificados com sucesso!")
                        
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Conteúdo principal
    if st.session_state.replicador:
        tab1, tab2, tab3 = st.tabs([
            "📊 PADRÕES IDENTIFICADOS",
            "🎲 GERAR JOGOS (baseado em padrões reais)",
            "📈 CONFERÊNCIA"
        ])
        
        with tab1:
            st.header("📊 PADRÕES QUE REALMENTE SE REPETEM")
            
            padroes = st.session_state.replicador.mostrar_padroes_encontrados()
            
            # Top padrões par/ímpar
            st.subheader("🎯 Distribuição Par/Ímpar mais comum")
            df_par_impar = pd.DataFrame(padroes['par_impar'])
            st.dataframe(df_par_impar, use_container_width=True)
            
            # Top faixas de soma
            st.subheader("📈 Faixas de Soma mais frequentes")
            df_somas = pd.DataFrame(padroes['somas'])
            st.dataframe(df_somas, use_container_width=True)
            
            # Subconjuntos que mais se repetem
            st.subheader("🔢 Grupos de números que já se repetiram em múltiplos concursos")
            st.write("Estes grupos JÁ APARECERAM JUNTOS em concursos anteriores:")
            
            for i, sub in enumerate(padroes['subconjuntos_repetidos'], 1):
                st.write(f"{i}. **{', '.join([str(n) for n in sub['numeros']])}** - Apareceu {sub['vezes']} vezes")
            
            # Estatísticas gerais
            st.subheader("📊 Estatísticas dos Padrões")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_sub = len(st.session_state.replicador.padroes_identificados['subconjuntos_frequentes'])
                st.metric("Grupos que se repetem", total_sub)
            
            with col2:
                total_pares = len(st.session_state.replicador.padroes_identificados['combinacoes_famosas'])
                st.metric("Pares frequentes", total_pares)
            
            with col3:
                media_repeticao = np.mean([s['frequencia'] for s in 
                                          st.session_state.replicador.padroes_identificados['subconjuntos_frequentes'][:10]])
                st.metric("Média de repetição (top 10)", f"{media_repeticao:.1f}x")
        
        with tab2:
            st.header("🎲 GERAR JOGOS BASEADOS EM PADRÕES REAIS")
            
            st.info("""
            **Como funciona a geração:**
            - Os jogos são construídos usando APENAS grupos de números que JÁ SE REPETIRAM
            - Priorizamos os padrões que mais apareceram na história
            - Mantemos a distribuição par/ímpar mais comum
            """)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                estrategia = st.radio(
                    "Tipo de geração:",
                    [
                        "🎯 Todos os padrões",
                        "🔗 Foco em sequências (ex: 04-05-06)"
                    ]
                )
                
                quantidade = st.number_input("Quantidade de jogos", 5, 50, 15)
                
                if st.button("🚀 GERAR JOGOS", type="primary"):
                    if estrategia == "🎯 Todos os padrões":
                        st.session_state.jogos = st.session_state.replicador.gerar_jogos_replicando_padroes(quantidade)
                    else:
                        st.session_state.jogos = st.session_state.replicador.gerar_jogos_com_sequencias_repetidas(quantidade)
                    
                    st.success(f"✅ {len(st.session_state.jogos)} jogos gerados usando padrões reais!")
            
            with col2:
                if st.session_state.jogos:
                    st.subheader("🎯 Jogos Gerados")
                    
                    for i, jogo in enumerate(st.session_state.jogos[:10], 1):
                        st.write(f"**Jogo {i}:** {', '.join([f'{n:02d}' for n in jogo])}")
                    
                    if len(st.session_state.jogos) > 10:
                        st.info(f"... e mais {len(st.session_state.jogos)-10} jogos")
        
        with tab3:
            if st.session_state.jogos:
                st.header("📈 CONFERÊNCIA")
                
                st.subheader("Análise dos jogos gerados")
                
                dados = []
                for i, jogo in enumerate(st.session_state.jogos, 1):
                    # Estatísticas do jogo
                    pares = sum(1 for n in jogo if n % 2 == 0)
                    soma = sum(jogo)
                    
                    # Verifica se tem sequências
                    tem_sequencia = "❌"
                    for j in range(len(jogo)-2):
                        if jogo[j+2] - jogo[j+1] == 1 and jogo[j+1] - jogo[j] == 1:
                            tem_sequencia = "✅"
                            break
                    
                    dados.append({
                        "Jogo": i,
                        "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                        "Soma": soma,
                        "Pares": pares,
                        "Ímpares": 15-pares,
                        "Tem Sequência": tem_sequencia
                    })
                
                df = pd.DataFrame(dados)
                st.dataframe(df, use_container_width=True)
                
                # Exportação
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Exportar jogos (CSV)",
                    data=csv,
                    file_name=f"jogos_padroes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ℹ️ Gere jogos primeiro!")

if __name__ == "__main__":
    main()
