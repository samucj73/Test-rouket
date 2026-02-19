import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="📊 LOTOFÁCIL - ANÁLISE ESTATÍSTICA 2024",
    layout="wide"
)

# =====================================================
# CLASSE PRINCIPAL MELHORADA
# =====================================================
class AnaliseLotofacil:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        
        # Análises estatísticas reais
        self.frequencias = self._calcular_frequencias()
        self.defasagens = self._calcular_defasagens()
        self.padroes_par_impar = self._analisar_padroes_par_impar()
        self.distribuicao_soma = self._analisar_somas()
        
    def _calcular_frequencias(self):
        """Calcula frequência real de cada número"""
        todas_dezenas = []
        for concurso in self.concursos:
            todas_dezenas.extend(concurso)
        
        frequencias = Counter(todas_dezenas)
        total = len(todas_dezenas)
        
        return {num: (freq/total)*100 for num, freq in frequencias.items()}
    
    def _calcular_defasagens(self):
        """Calcula há quantos concursos cada número não aparece"""
        defasagens = {}
        for num in self.numeros:
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    defasagens[num] = i
                    break
            else:
                defasagens[num] = len(self.concursos)
        return defasagens
    
    def _analisar_padroes_par_impar(self):
        """Analisa distribuição histórica de pares/ímpares"""
        padroes = []
        for concurso in self.concursos:
            pares = sum(1 for n in concurso if n % 2 == 0)
            padroes.append(pares)
        return padroes
    
    def _analisar_somas(self):
        """Analisa soma total dos números nos concursos históricos"""
        somas = [sum(concurso) for concurso in self.concursos]
        return {
            'media': np.mean(somas),
            'std': np.std(somas),
            'min': min(somas),
            'max': max(somas)
        }
    
    # =================================================
    # ESTRATÉGIA 1 – BASEADA EM FREQUÊNCIA REAL
    # =================================================
    def estrategia_frequencia(self, n_jogos=15):
        """Gera jogos baseados na frequência real dos números"""
        jogos = []
        
        # Peso baseado na frequência real
        pesos = [self.frequencias.get(num, 0) for num in self.numeros]
        
        for _ in range(n_jogos):
            jogo = set()
            
            # 70% dos números baseados em frequência, 30% aleatórios
            n_frequentes = random.randint(9, 11)
            n_aleatorios = 15 - n_frequentes
            
            # Seleciona números frequentes
            candidatos_frequentes = random.choices(
                self.numeros, 
                weights=pesos, 
                k=n_frequentes * 2
            )
            for num in candidatos_frequentes:
                if len(jogo) < n_frequentes:
                    jogo.add(num)
            
            # Completa com números aleatórios
            while len(jogo) < 15:
                jogo.add(random.choice(self.numeros))
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 2 – BASEADA EM DEFASAGEM
    # =================================================
    def estrategia_defasagem(self, n_jogos=15):
        """Prioriza números que estão há mais tempo sem sair"""
        jogos = []
        
        # Ordena números por defasagem (maior defasagem = maior peso)
        numeros_ordenados = sorted(
            self.numeros, 
            key=lambda x: self.defasagens[x], 
            reverse=True
        )
        
        for _ in range(n_jogos):
            jogo = set()
            
            # Pega os números mais defasados
            top_defasados = numeros_ordenados[:10]
            jogo.update(random.sample(top_defasados, random.randint(8, 10)))
            
            # Completa com números aleatórios
            while len(jogo) < 15:
                jogo.add(random.choice(self.numeros))
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 3 – REPRODUÇÃO DE PADRÕES HISTÓRICOS
    # =================================================
    def estrategia_padroes(self, n_jogos=15):
        """Reproduz padrões estatísticos dos concursos anteriores"""
        jogos = []
        
        # Distribuição de pares/ímpares mais comum
        pares_comum = Counter(self.padroes_par_impar).most_common(1)[0][0]
        
        for _ in range(n_jogos):
            jogo = set()
            
            # Define quantidade de pares baseada no padrão histórico
            qtd_pares = pares_comum + random.randint(-1, 1)
            qtd_pares = max(5, min(12, qtd_pares))  # Mantém dentro do range razoável
            
            # Seleciona números pares e ímpares
            pares = [n for n in self.numeros if n % 2 == 0]
            impares = [n for n in self.numeros if n % 2 == 1]
            
            jogo.update(random.sample(pares, min(qtd_pares, len(pares))))
            jogo.update(random.sample(impares, 15 - qtd_pares))
            
            # Ajusta soma para próximo da média histórica
            soma_atual = sum(jogo)
            media_alvo = self.distribuicao_soma['media']
            
            # Tenta ajustar para chegar próximo da média
            tentativas = 0
            while abs(soma_atual - media_alvo) > 30 and tentativas < 100:
                # Remove um número e adiciona outro
                if soma_atual > media_alvo:
                    removido = max(jogo)
                    adicionado = random.choice([n for n in self.numeros if n < removido and n not in jogo])
                else:
                    removido = min(jogo)
                    adicionado = random.choice([n for n in self.numeros if n > removido and n not in jogo])
                
                if adicionado:
                    jogo.remove(removido)
                    jogo.add(adicionado)
                    soma_atual = sum(jogo)
                
                tentativas += 1
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 4 – MISTA (COMBINA AS ABORDAGENS)
    # =================================================
    def estrategia_mista(self, n_jogos=15):
        """Combina diferentes estratégias para diversificar"""
        jogos = []
        
        for i in range(n_jogos):
            if i % 3 == 0:
                jogos.extend(self.estrategia_frequencia(1))
            elif i % 3 == 1:
                jogos.extend(self.estrategia_defasagem(1))
            else:
                jogos.extend(self.estrategia_padroes(1))
        
        return jogos
    
    # =================================================
    # CONFERÊNCIA DOS JOGOS
    # =================================================
    def conferir_jogos(self, jogos, concurso_alvo=None):
        """Conferência detalhada dos jogos"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            acertos = len(set(jogo) & set(concurso_alvo))
            
            # Análise detalhada
            pares_jogo = sum(1 for n in jogo if n % 2 == 0)
            pares_concurso = sum(1 for n in concurso_alvo if n % 2 == 0)
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Soma": sum(jogo),
                "Pares": pares_jogo,
                "Acerto Padrão": "✅" if pares_jogo == pares_concurso else "❌"
            })
        
        return dados
    
    # =================================================
    # GRÁFICOS E ANÁLISES
    # =================================================
    def grafico_frequencias(self):
        """Gera gráfico de frequências"""
        df_freq = pd.DataFrame([
            {"Número": num, "Frequência (%)": freq}
            for num, freq in self.frequencias.items()
        ])
        
        fig = px.bar(
            df_freq, 
            x="Número", 
            y="Frequência (%)",
            title="Frequência de Aparição dos Números",
            color="Frequência (%)",
            color_continuous_scale="Viridis"
        )
        return fig
    
    def grafico_defasagens(self):
        """Gera gráfico de defasagens"""
        df_def = pd.DataFrame([
            {"Número": num, "Concursos sem sair": self.defasagens[num]}
            for num in self.numeros
        ])
        
        fig = px.bar(
            df_def,
            x="Número",
            y="Concursos sem sair",
            title="Números por Defasagem (concursos sem aparecer)",
            color="Concursos sem sair",
            color_continuous_scale="Reds"
        )
        return fig

# =====================================================
# INTERFACE STREAMLIT MELHORADA
# =====================================================
def main():
    st.title("📊 LOTOFÁCIL - ANALISADOR ESTATÍSTICO")
    
    st.markdown("""
    ### 🎯 Sobre esta ferramenta
    Esta aplicação analisa dados reais da Lotofácil e gera jogos baseados em **padrões estatísticos históricos**.
    Lembre-se: **não existe garantia de ganhos** - a loteria é um jogo de azar.
    """)
    
    # Inicialização da sessão
    if "concursos" not in st.session_state:
        st.session_state.concursos = []
    
    if "jogos" not in st.session_state:
        st.session_state.jogos = []
    
    if "analise" not in st.session_state:
        st.session_state.analise = None
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd = st.slider("Quantidade de concursos para análise", 20, 500, 200, 10)
        
        if st.button("🔄 Carregar dados históricos", type="primary"):
            with st.spinner("Carregando concursos..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    st.session_state.concursos = concursos
                    st.session_state.analise = AnaliseLotofacil(concursos)
                    
                    st.success(f"✅ {len(concursos)} concursos carregados!")
                    
                    # Mostra info do último concurso
                    ultimo = resposta[0]
                    st.info(f"📅 Último concurso: {ultimo['concurso']} - {ultimo['data']}")
                    
                except Exception as e:
                    st.error(f"Erro ao carregar dados: {e}")
    
    # Abas para organização
    if st.session_state.concursos:
        tab1, tab2, tab3 = st.tabs(["📈 Análise Estatística", "🎲 Gerar Jogos", "📊 Resultados"])
        
        with tab1:
            st.header("Análise dos Dados Históricos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de frequências
                fig_freq = st.session_state.analise.grafico_frequencias()
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                # Gráfico de defasagens
                fig_def = st.session_state.analise.grafico_defasagens()
                st.plotly_chart(fig_def, use_container_width=True)
            
            # Estatísticas descritivas
            st.subheader("📊 Estatísticas Descritivas")
            
            col3, col4, col5 = st.columns(3)
            
            with col3:
                soma_stats = st.session_state.analise.distribuicao_soma
                st.metric("Média da soma dos números", f"{soma_stats['media']:.1f}")
                st.metric("Desvio padrão", f"{soma_stats['std']:.1f}")
            
            with col4:
                # Números mais frequentes
                top_numeros = sorted(
                    st.session_state.analise.frequencias.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                
                st.write("**Números mais frequentes:**")
                for num, freq in top_numeros:
                    st.write(f"Nº {num:02d}: {freq:.2f}%")
            
            with col5:
                # Números mais defasados
                top_defasados = sorted(
                    st.session_state.analise.defasagens.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                
                st.write("**Números mais atrasados:**")
                for num, defas in top_defasados:
                    st.write(f"Nº {num:02d}: {defas} concursos")
        
        with tab2:
            st.header("Gerar Jogos Baseados em Estatísticas")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                estrategia = st.selectbox(
                    "Escolha a estratégia de geração",
                    [
                        "📈 Baseada em Frequência",
                        "⏰ Baseada em Defasagem",
                        "📊 Baseada em Padrões Históricos",
                        "🔄 Estratégia Mista"
                    ]
                )
            
            with col2:
                quantidade = st.number_input("Quantidade de jogos", 5, 100, 15)
            
            if st.button("🚀 Gerar jogos", type="primary"):
                mapa = {
                    "📈 Baseada em Frequência": st.session_state.analise.estrategia_frequencia,
                    "⏰ Baseada em Defasagem": st.session_state.analise.estrategia_defasagem,
                    "📊 Baseada em Padrões Históricos": st.session_state.analise.estrategia_padroes,
                    "🔄 Estratégia Mista": st.session_state.analise.estrategia_mista
                }
                
                st.session_state.jogos = mapa[estrategia](quantidade)
                st.success(f"✅ {len(st.session_state.jogos)} jogos gerados!")
        
        with tab3:
            if st.session_state.jogos:
                st.header("Resultados da Conferência")
                
                # Mostra jogos gerados
                with st.expander("🎲 Ver jogos gerados", expanded=False):
                    df_jogos = pd.DataFrame({
                        f"Jogo {i+1}": ", ".join([f"{n:02d}" for n in jogo])
                        for i, jogo in enumerate(st.session_state.jogos)
                    }.items(), columns=["Jogo", "Dezenas"])
                    st.dataframe(df_jogos, use_container_width=True)
                
                # Conferência com último concurso
                st.subheader("🎯 Conferência com o último concurso")
                resultado = st.session_state.analise.conferir_jogos(
                    st.session_state.jogos
                )
                df_resultado = pd.DataFrame(resultado)
                st.dataframe(df_resultado, use_container_width=True)
                
                # Resumo de acertos
                st.subheader("📊 Distribuição de Acertos")
                acertos_counts = df_resultado["Acertos"].value_counts().sort_index()
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.bar_chart(acertos_counts)
                
                with col2:
                    st.write("**Resumo:**")
                    st.write(f"Total de jogos: {len(df_resultado)}")
                    st.write(f"Média de acertos: {df_resultado['Acertos'].mean():.2f}")
                    st.write(f"Máximo de acertos: {df_resultado['Acertos'].max()}")
                    st.write(f"Mínimo de acertos: {df_resultado['Acertos'].min()}")
                
                # Exportação
                if st.button("📥 Exportar resultados para CSV"):
                    csv = df_resultado.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"lotofacil_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("ℹ️ Gere alguns jogos na aba 'Gerar Jogos' primeiro.")

# =====================================================
# EXECUÇÃO
# =====================================================
if __name__ == "__main__":
    main()
