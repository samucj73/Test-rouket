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
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="🏆 LOTOFÁCIL - FILTROS PROFISSIONAIS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL - VERSÃO COM FILTROS AJUSTADOS
# =====================================================
class AnaliseLotofacilFiltros:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # Análises estatísticas
        self.frequencias = self._calcular_frequencias_avancadas()
        self.defasagens = self._calcular_defasagens()
        self.padroes_combinatorios = self._analisar_padroes_combinatorios()
        self.matriz_correlacao = self._calcular_matriz_correlacao()
        self.numeros_chave = self._identificar_numeros_chave()
        
    def _calcular_frequencias_avancadas(self):
        """Calcula frequências com ponderação temporal"""
        frequencias = {}
        for num in self.numeros:
            peso_total = 0
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    peso = np.exp(-i / 25)  # Decaimento mais acentuado
                    peso_total += peso
            
            frequencias[num] = (peso_total / self.total_concursos) * 100 if self.total_concursos > 0 else 0
        return frequencias
    
    def _calcular_matriz_correlacao(self):
        """Calcula correlação entre números"""
        matriz = defaultdict(lambda: defaultdict(float))
        for num1 in self.numeros:
            for num2 in self.numeros:
                if num1 < num2:
                    juntos = sum(1 for c in self.concursos if num1 in c and num2 in c)
                    probabilidade = juntos / self.total_concursos if self.total_concursos > 0 else 0
                    matriz[num1][num2] = probabilidade
                    matriz[num2][num1] = probabilidade
        return matriz
    
    def _analisar_padroes_combinatorios(self):
        """Análise de padrões combinatórios"""
        padroes = {
            'somas': [],
            'pares': [],
            'impares': [],
            'primos': [],
            'quadrantes': [],
            'consecutivos': []  # NOVO: Contagem de pares consecutivos
        }
        
        primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        
        for concurso in self.concursos:
            padroes['somas'].append(sum(concurso))
            
            pares = sum(1 for n in concurso if n % 2 == 0)
            padroes['pares'].append(pares)
            padroes['impares'].append(15 - pares)
            
            padroes['primos'].append(sum(1 for n in concurso if n in primos))
            padroes['quadrantes'].append(sum(1 for n in concurso if n <= 12))
            
            # Conta pares consecutivos
            consec = 0
            for i in range(len(concurso)-1):
                if concurso[i+1] - concurso[i] == 1:
                    consec += 1
            padroes['consecutivos'].append(consec)
        
        return padroes
    
    def _identificar_numeros_chave(self):
        """Identifica números que frequentemente aparecem juntos"""
        numeros_chave = []
        for num in self.numeros:
            freq_recente = sum(1 for c in self.concursos[:20] if num in c)
            if freq_recente > 8:  # Apareceu em mais de 8 dos últimos 20
                numeros_chave.append(num)
        return numeros_chave
    
    def _calcular_defasagens(self):
        """Calcula defasagem dos números"""
        defasagens = {}
        for num in self.numeros:
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    defasagens[num] = i
                    break
            else:
                defasagens[num] = len(self.concursos)
        return defasagens
    
    # =================================================
    # FILTROS RIGOROSOS - CORAÇÃO DA MELHORIA
    # =================================================
    def aplicar_filtros(self, jogo):
        """
        APLICA FILTROS RIGOROSOS PARA EVITAR PADRÕES PROBLEMÁTICOS
        Retorna: (bool, str) - (aprovado, motivo_rejeicao)
        """
        
        # FILTRO 1: Consecutivos (CRÍTICO)
        consecutivos = 0
        sequencias_longas = 0
        i = 0
        while i < len(jogo)-1:
            if jogo[i+1] - jogo[i] == 1:
                consecutivos += 1
                # Detecta sequências de 3 ou mais
                if i < len(jogo)-2 and jogo[i+2] - jogo[i+1] == 1:
                    sequencias_longas += 1
                i += 1
            else:
                i += 1
        
        # Regras de consecutivos (MAIS RIGOROSAS)
        if consecutivos > 3:
            return False, f"❌ Muitos consecutivos ({consecutivos} pares)"
        if sequencias_longas > 1:
            return False, f"❌ Sequência longa demais"
        if any(jogo[i:i+3] == list(range(jogo[i], jogo[i]+3)) for i in range(len(jogo)-2)):
            # Verifica se há qualquer sequência de 3 números consecutivos
            return False, "❌ Sequência de 3 números detectada"
        
        # FILTRO 2: Distribuição por quadrantes
        q1 = sum(1 for n in jogo if 1 <= n <= 5)
        q2 = sum(1 for n in jogo if 6 <= n <= 10)
        q3 = sum(1 for n in jogo if 11 <= n <= 15)
        q4 = sum(1 for n in jogo if 16 <= n <= 20)
        q5 = sum(1 for n in jogo if 21 <= n <= 25)
        
        quadrantes = [q1, q2, q3, q4, q5]
        
        # Cada quadrante deve ter entre 2 e 5 números
        for i, qtd in enumerate(quadrantes):
            if qtd < 2:
                return False, f"❌ Quadrante {i+1} com apenas {qtd} números"
            if qtd > 5:
                return False, f"❌ Quadrante {i+1} com {qtd} números (excesso)"
        
        # FILTRO 3: Soma dentro de 2 desvios padrão
        soma_stats = self.padroes_combinatorios['somas']
        if soma_stats:
            media = np.mean(soma_stats)
            desvio = np.std(soma_stats)
            soma_jogo = sum(jogo)
            
            if abs(soma_jogo - media) > 2 * desvio:
                return False, f"❌ Soma {soma_jogo} fora do padrão"
        
        # FILTRO 4: Proporção par/ímpar
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares < 6 or pares > 9:  # Mais rigoroso: 6-9 pares
            return False, f"❌ Proporção par/ímpar: {pares} pares"
        
        # FILTRO 5: Números repetidos do último concurso (opcional)
        if self.ultimo_concurso:
            repetidos = len(set(jogo) & set(self.ultimo_concurso))
            if repetidos < 5 or repetidos > 10:
                return False, f"❌ Repetiu apenas {repetidos} do último concurso"
        
        # FILTRO 6: Presença de números chave
        num_chave = sum(1 for n in jogo if n in self.numeros_chave)
        if num_chave < 4:
            return False, f"❌ Apenas {num_chave} números chave"
        
        return True, "✅ Filtros aprovados"
    
    # =================================================
    # ESTRATÉGIA PRINCIPAL - ALGORITMO GENÉTICO COM FILTROS
    # =================================================
    def gerar_jogos_filtrados(self, n_jogos=15, populacao=500, geracoes=100):
        """
        Algoritmo genético com filtros rigorosos
        """
        
        def fitness(jogo):
            """Função de aptidão refinada"""
            score = 0
            
            # Critério 1: Frequência dos números
            freq_media = np.mean([self.frequencias[n] for n in jogo])
            score += freq_media * 2
            
            # Critério 2: Correlação entre números
            correlacao_total = 0
            count = 0
            for i in range(len(jogo)):
                for j in range(i+1, len(jogo)):
                    correlacao_total += self.matriz_correlacao[jogo[i]][jogo[j]]
                    count += 1
            if count > 0:
                score += (correlacao_total / count) * 30
            
            # Critério 3: Números chave
            score += sum(1 for n in jogo if n in self.numeros_chave) * 3
            
            # Critério 4: Distribuição ideal (penaliza extremos)
            pares = sum(1 for n in jogo if n % 2 == 0)
            score += 10 - abs(pares - 7) * 2
            
            return score
        
        # População inicial
        populacao_atual = []
        tentativas = 0
        max_tentativas = populacao * 10
        
        while len(populacao_atual) < populacao and tentativas < max_tentativas:
            tentativas += 1
            jogo = sorted(random.sample(self.numeros, 15))
            
            # Aplica filtros na população inicial
            aprovado, _ = self.aplicar_filtros(jogo)
            if aprovado:
                populacao_atual.append((jogo, fitness(jogo)))
        
        if not populacao_atual:
            # Fallback: gera sem filtros na inicialização
            populacao_atual = [(sorted(random.sample(self.numeros, 15)), 0) 
                              for _ in range(populacao)]
            for i, (jogo, _) in enumerate(populacao_atual):
                populacao_atual[i] = (jogo, fitness(jogo))
        
        # Evolução
        for geracao in range(geracoes):
            nova_populacao = []
            
            # Elitismo - mantém os 20% melhores
            populacao_atual.sort(key=lambda x: x[1], reverse=True)
            elite_size = max(1, populacao // 5)
            nova_populacao.extend(populacao_atual[:elite_size])
            
            # Gera novos indivíduos
            while len(nova_populacao) < populacao:
                # Seleciona pais (torneio)
                pai1 = max(random.sample(populacao_atual, min(5, len(populacao_atual))), 
                          key=lambda x: x[1])
                pai2 = max(random.sample(populacao_atual, min(5, len(populacao_atual))), 
                          key=lambda x: x[1])
                
                # Crossover
                ponto_corte = random.randint(4, 11)
                filho = list(set(pai1[0][:ponto_corte] + pai2[0][ponto_corte:]))
                
                # Mutação controlada
                if random.random() < 0.2:  # 20% de chance
                    if filho:
                        idx = random.randint(0, len(filho)-1)
                        candidatos = [n for n in self.numeros if n not in filho]
                        if candidatos:
                            # Prioriza números chave na mutação
                            chave_candidatos = [n for n in candidatos if n in self.numeros_chave]
                            if chave_candidatos and random.random() < 0.5:
                                filho[idx] = random.choice(chave_candidatos)
                            else:
                                filho[idx] = random.choice(candidatos)
                
                # Completa para 15 números
                while len(filho) < 15:
                    candidatos = [n for n in self.numeros if n not in filho]
                    if candidatos:
                        # Prioriza números chave
                        chave_disp = [n for n in candidatos if n in self.numeros_chave]
                        if chave_disp and random.random() < 0.4:
                            filho.append(random.choice(chave_disp))
                        else:
                            filho.append(random.choice(candidatos))
                    else:
                        break
                
                if len(filho) == 15:
                    filho = sorted(filho)
                    # APLICA FILTROS NO FILHO GERADO
                    aprovado, _ = self.aplicar_filtros(filho)
                    if aprovado:
                        nova_populacao.append((filho, fitness(filho)))
            
            # Se não gerou novos suficientes, completa com mutações dos melhores
            if len(nova_populacao) < populacao:
                needed = populacao - len(nova_populacao)
                for i in range(needed):
                    if populacao_atual:
                        base = random.choice(populacao_atual[:10])[0].copy()
                        # Mutação
                        idx = random.randint(0, 14)
                        candidatos = [n for n in self.numeros if n not in base]
                        if candidatos:
                            base[idx] = random.choice(candidatos)
                            base = sorted(base)
                            if self.aplicar_filtros(base)[0]:
                                nova_populacao.append((base, fitness(base)))
            
            populacao_atual = nova_populacao
        
        # Retorna os melhores jogos que passaram pelos filtros
        populacao_atual.sort(key=lambda x: x[1], reverse=True)
        jogos_finais = []
        
        for jogo, _ in populacao_atual:
            if len(jogos_finais) >= n_jogos:
                break
            # Dupla verificação dos filtros
            if self.aplicar_filtros(jogo)[0]:
                jogos_finais.append(jogo)
        
        # Se não gerou suficientes, complementa com geração controlada
        while len(jogos_finais) < n_jogos:
            novo_jogo = self._gerar_jogo_controlado()
            if novo_jogo and novo_jogo not in jogos_finais:
                jogos_finais.append(novo_jogo)
        
        return jogos_finais
    
    def _gerar_jogo_controlado(self):
        """Gera um jogo manualmente controlado quando o AG não produz suficientes"""
        for _ in range(100):  # 100 tentativas
            jogo = set()
            
            # Distribuição controlada por quadrantes
            quadrantes_alvo = [3, 3, 3, 3, 3]  # 3 números em cada quadrante
            
            for q_idx, (inicio, fim) in enumerate([(1,5), (6,10), (11,15), (16,20), (21,25)]):
                q_numeros = list(range(inicio, fim+1))
                q_escolhidos = random.sample(q_numeros, quadrantes_alvo[q_idx])
                jogo.update(q_escolhidos)
            
            # Ajusta par/ímpar
            jogo_list = sorted(jogo)
            pares = sum(1 for n in jogo_list if n % 2 == 0)
            
            # Balanceia se necessário
            if pares < 6:
                # Adiciona mais pares
                impares_idx = [i for i, n in enumerate(jogo_list) if n % 2 == 1]
                if impares_idx:
                    idx_troca = random.choice(impares_idx)
                    numero_antigo = jogo_list[idx_troca]
                    quadrante = (numero_antigo-1)//5
                    candidatos = [n for n in range(quadrante*5+1, (quadrante+1)*5+1) 
                                 if n % 2 == 0 and n not in jogo_list]
                    if candidatos:
                        novo_num = random.choice(candidatos)
                        jogo_list[idx_troca] = novo_num
            
            jogo_final = sorted(jogo_list)
            
            # Verifica filtros
            if self.aplicar_filtros(jogo_final)[0]:
                return jogo_final
        
        return None
    
    # =================================================
    # CONFERÊNCIA DETALHADA
    # =================================================
    def conferir_jogos(self, jogos, concurso_alvo=None):
        """Conferência com análise de filtros"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            
            # Aplica filtros para diagnóstico
            aprovado, motivo = self.aplicar_filtros(jogo)
            
            # Análise de consecutivos
            consecutivos = 0
            for i in range(len(jogo)-1):
                if jogo[i+1] - jogo[i] == 1:
                    consecutivos += 1
            
            # Distribuição por quadrantes
            q1 = sum(1 for n in jogo if 1 <= n <= 5)
            q2 = sum(1 for n in jogo if 6 <= n <= 10)
            q3 = sum(1 for n in jogo if 11 <= n <= 15)
            q4 = sum(1 for n in jogo if 16 <= n <= 20)
            q5 = sum(1 for n in jogo if 21 <= n <= 25)
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Soma": sum(jogo),
                "Pares": sum(1 for n in jogo if n % 2 == 0),
                "Consecutivos": consecutivos,
                "Quadrantes": f"{q1}-{q2}-{q3}-{q4}-{q5}",
                "Status Filtro": "✅" if aprovado else "❌",
                "Motivo": motivo if not aprovado else "OK",
                "Números Chave": sum(1 for n in jogo if n in self.numeros_chave)
            })
        
        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("🏆 LOTOFÁCIL - FILTROS PROFISSIONAIS")
    
    st.markdown("""
    ### 🎯 Sistema com Filtros Rigorosos
    **Versão otimizada** baseada na sua análise:
    - ✅ Base forte (prova: 12 pontos)
    - 🔧 Filtros de consecutivos ajustados
    - 📊 Distribuição balanceada por quadrantes
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
        
        qtd = st.slider("Concursos para análise", 50, 500, 150, 50)
        
        if st.button("🔄 Carregar dados", type="primary"):
            with st.spinner("Carregando..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if len(concursos) >= 50:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilFiltros(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        ultimo = resposta[0]
                        st.info(f"📅 Último: {ultimo['concurso']} - {ultimo['data']}")
                        
                        if st.session_state.analise.numeros_chave:
                            st.write("**Números chave:**", 
                                    ", ".join(map(str, st.session_state.analise.numeros_chave)))
                    
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Abas
    if st.session_state.analise:
        tab1, tab2, tab3 = st.tabs(["📊 Análise", "🎲 Gerar Jogos", "📈 Resultados"])
        
        with tab1:
            st.header("📊 Estatísticas dos Filtros")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Distribuição de consecutivos histórica
                fig_consec = px.histogram(
                    x=st.session_state.analise.padroes_combinatorios['consecutivos'],
                    nbins=10,
                    title="Distribuição Histórica de Consecutivos",
                    labels={'x': 'Pares Consecutivos', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_consec, use_container_width=True)
            
            with col2:
                # Frequências
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência Ponderada (%)",
                    labels={'x': 'Número', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
        
        with tab2:
            st.header("🎲 Gerar Jogos com Filtros Rigorosos")
            
            st.info("""
            **Filtros ativos:**
            - ❌ Máximo 3 pares consecutivos
            - ❌ Proibido sequências de 3 números
            - 📊 2-5 números por quadrante
            - ⚖️ 6-9 números pares
            - 🎯 Mínimo 4 números chave
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                qtd_jogos = st.number_input("Quantidade de jogos", 5, 50, 15)
            
            with col2:
                geracoes = st.slider("Gerações do algoritmo", 50, 200, 100)
            
            if st.button("🚀 Gerar jogos filtrados", type="primary"):
                with st.spinner("Gerando jogos com filtros rigorosos..."):
                    st.session_state.jogos = st.session_state.analise.gerar_jogos_filtrados(
                        n_jogos=qtd_jogos,
                        geracoes=geracoes
                    )
                    st.success(f"✅ {len(st.session_state.jogos)} jogos gerados!")
        
        with tab3:
            if st.session_state.jogos:
                st.header("📈 Resultados da Conferência")
                
                # Input manual do resultado
                with st.expander("🔢 Inserir resultado do sorteio"):
                    res_input = st.text_input(
                        "Números (separados por vírgula)",
                        placeholder="01,04,05,06,10,11,13,14,16,18,19,20,21,23,24"
                    )
                    if st.button("Carregar resultado"):
                        try:
                            nums = [int(x.strip()) for x in res_input.split(',')]
                            if len(nums) == 15:
                                st.session_state.resultado = sorted(nums)
                                st.success("Resultado carregado!")
                        except:
                            st.error("Formato inválido!")
                
                concurso_alvo = st.session_state.get('resultado', 
                                                     st.session_state.analise.ultimo_concurso)
                
                # Conferência
                resultado = st.session_state.analise.conferir_jogos(
                    st.session_state.jogos, concurso_alvo
                )
                df = pd.DataFrame(resultado)
                st.dataframe(df, use_container_width=True)
                
                # Estatísticas
                st.subheader("📊 Distribuição de Acertos")
                
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
                fig = px.histogram(df, x='Acertos', nbins=15,
                                  title='Distribuição de Acertos',
                                  color_discrete_sequence=['#2E86AB'])
                st.plotly_chart(fig, use_container_width=True)
                
                # Exportação
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Exportar CSV",
                    data=csv,
                    file_name=f"resultados_filtrados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ℹ️ Gere jogos primeiro!")

if __name__ == "__main__":
    main()
