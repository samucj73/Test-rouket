import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - ANALISADOR AGRESSIVO V3",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL - VERSÃO AGRESSIVA PARA 12-14 PONTOS
# =====================================================
class AnaliseLotofacilAgressiva:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # Análises estatísticas avançadas
        self.frequencias = self._calcular_frequencias_avancadas()
        self.defasagens = self._calcular_defasagens()
        self.tendencias_temporais = self._analisar_tendencias_temporais()
        
        # NOVO: Identificação de padrões críticos
        self.numeros_quentes = self._identificar_quentes()
        self.numeros_frios = self._identificar_frios()
        self.padroes_vencedores = self._analisar_padroes_12_14_pontos()
        
    def _calcular_frequencias_avancadas(self):
        """Frequência com peso nos últimos 30 concursos (mais relevante)"""
        frequencias = {}
        ultimos_30 = self.concursos[:30]
        
        for num in self.numeros:
            # Peso total: 70% últimos 30, 30% histórico completo
            freq_recente = sum(1 for c in ultimos_30 if num in c) / max(1, len(ultimos_30))
            freq_historica = sum(1 for c in self.concursos if num in c) / self.total_concursos
            
            frequencias[num] = (freq_recente * 0.7 + freq_historica * 0.3) * 100
            
        return frequencias
    
    def _identificar_quentes(self):
        """Top 8 números mais frequentes nos últimos 30"""
        ultimos_30 = self.concursos[:30]
        contador = Counter()
        for c in ultimos_30:
            contador.update(c)
        
        return [num for num, _ in contador.most_common(8)]
    
    def _identificar_frios(self):
        """Bottom 8 números menos frequentes nos últimos 30"""
        ultimos_30 = self.concursos[:30]
        contador = Counter()
        for c in ultimos_30:
            contador.update(c)
        
        # Inverte a ordem
        return [num for num, _ in sorted(contador.items(), key=lambda x: x[1])[:8]]
    
    def _analisar_padroes_12_14_pontos(self):
        """Análise específica de concursos que tiveram 12-14 pontos"""
        padroes = {
            'somas': [],
            'pares': [],
            'sequencias_max': [],
            'repeticao_anterior': []
        }
        
        # Identifica concursos com pontuação alta (simulado)
        for i in range(len(self.concursos)-1):
            concurso_atual = self.concursos[i]
            concurso_anterior = self.concursos[i+1]
            
            # Calcula "pontuação simulada" baseada em padrões vencedores
            repetidos = len(set(concurso_atual) & set(concurso_anterior))
            
            # Se teve muitos repetidos, é um padrão forte
            if repetidos >= 9:
                padroes['somas'].append(sum(concurso_atual))
                padroes['pares'].append(sum(1 for n in concurso_atual if n % 2 == 0))
                
                # Máximo de sequências consecutivas
                max_seq = 0
                seq_atual = 1
                for j in range(len(concurso_atual)-1):
                    if concurso_atual[j+1] - concurso_atual[j] == 1:
                        seq_atual += 1
                        max_seq = max(max_seq, seq_atual)
                    else:
                        seq_atual = 1
                
                padroes['sequencias_max'].append(max_seq)
                padroes['repeticao_anterior'].append(repetidos)
        
        return padroes
    
    def _calcular_defasagens(self):
        """Calcula defasagem atual"""
        defasagens = {}
        for num in self.numeros:
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    defasagens[num] = i
                    break
            else:
                defasagens[num] = len(self.concursos)
        
        return defasagens
    
    def _analisar_tendencias_temporais(self):
        """Tendências básicas"""
        tendencias = {}
        for num in self.numeros:
            # Média móvel simples
            ultimos_10 = sum(1 for c in self.concursos[:10] if num in c)
            tendencias[num] = ultimos_10 / 10
        
        return tendencias
    
    # =================================================
    # NOVA ESTRATÉGIA 1 - ROMPEDORA DE TETO (12-14 PONTOS)
    # =================================================
    def estrategia_rompedora(self, n_jogos=15, jogos_existentes=[]):
        """
        Estratégia agressiva focada em romper o teto de 11 pontos
        - Sacrifica 2-3 números quentes
        - Insere números frios estratégicos
        - Limita sequências a NO MÁXIMO 4
        - Garante diversidade entre jogos
        """
        jogos = []
        tentativas = 0
        max_tentativas = n_jogos * 20  # Evita loop infinito
        
        # Parâmetros agressivos
        CONSECUTIVOS_MAX = 4
        REPETICAO_MAX = 9  # Máx dezenas iguais entre jogos
        
        while len(jogos) < n_jogos and tentativas < max_tentativas:
            tentativas += 1
            
            # Decide perfil do jogo (variação forçada)
            perfil = random.choice(['agressivo', 'conservador', 'equilibrado', 'extremo'])
            
            jogo = set()
            
            # === FASE 1: NÚCLEO BASE (7-8 números) ===
            if perfil == 'agressivo':
                # Sacrifica quentes, prioriza frios
                nucleo = random.sample(self.numeros_frios, min(5, len(self.numeros_frios)))
                nucleo += random.sample(self.numeros_quentes, min(3, len(self.numeros_quentes)))
            elif perfil == 'conservador':
                # Mantém quentes
                nucleo = random.sample(self.numeros_quentes, min(6, len(self.numeros_quentes)))
                nucleo += random.sample(self.numeros_frios, min(2, len(self.numeros_frios)))
            elif perfil == 'extremo':
                # Radical: só frios ou só quentes
                if random.random() < 0.5:
                    nucleo = random.sample(self.numeros_frios, min(8, len(self.numeros_frios)))
                else:
                    nucleo = random.sample(self.numeros_quentes, min(8, len(self.numeros_quentes)))
            else:  # equilibrado
                nucleo = random.sample(self.numeros_quentes, min(4, len(self.numeros_quentes)))
                nucleo += random.sample(self.numeros_frios, min(4, len(self.numeros_frios)))
            
            jogo.update(nucleo)
            
            # === FASE 2: COMPLEMENTO INTELIGENTE ===
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros if n not in jogo]
                
                if not candidatos:
                    break
                
                # Filtra candidatos que não criam sequências longas
                candidatos_filtrados = []
                for c in candidatos:
                    # Simula adição e verifica sequências
                    jogo_teste = sorted(jogo | {c})
                    max_seq = self._calcular_max_sequencia(jogo_teste)
                    
                    if max_seq <= CONSECUTIVOS_MAX:
                        candidatos_filtrados.append(c)
                
                # Se não houver candidatos filtrados, usa qualquer um
                if not candidatos_filtrados:
                    candidatos_filtrados = candidatos
                
                # Pesos: equilibra frequência
                pesos = [self.frequencias[c] for c in candidatos_filtrados]
                if sum(pesos) > 0:
                    novo = random.choices(candidatos_filtrados, weights=pesos)[0]
                else:
                    novo = random.choice(candidatos_filtrados)
                
                jogo.add(novo)
            
            # === FASE 3: VALIDAÇÕES AGRESSIVAS ===
            if len(jogo) != 15:
                continue
            
            jogo_ordenado = sorted(jogo)
            
            # Validação 1: Sequências consecutivas
            if self._calcular_max_sequencia(jogo_ordenado) > CONSECUTIVOS_MAX:
                continue
            
            # Validação 2: Diversidade entre jogos
            if jogos_existentes:
                repetido_demais = False
                for j_existente in jogos_existentes:
                    dezenas_comuns = len(set(j_existente) & jogo)
                    if dezenas_comuns > REPETICAO_MAX:
                        repetido_demais = True
                        break
                
                if repetido_demais:
                    continue
            
            # Validação 3: Soma dentro de limites aceitáveis (mas com variação)
            soma_jogo = sum(jogo_ordenado)
            if perfil == 'extremo':
                # Permite somas extremas
                if soma_jogo < 160 or soma_jogo > 220:
                    jogos.append(jogo_ordenado)
            else:
                # Soma entre 170 e 210 para outros perfis
                if 165 <= soma_jogo <= 215:
                    jogos.append(jogo_ordenado)
        
        return jogos[:n_jogos]
    
    # =================================================
    # NOVA ESTRATÉGIA 2 - CAÇA REPETIÇÕES (PADRÕES FORTES)
    # =================================================
    def estrategia_repeticao(self, n_jogos=15, jogos_existentes=[]):
        """
        Focada em repetição de padrões de concursos anteriores
        - Identifica concursos com 9+ repetições
        - Usa como base para novos jogos
        """
        jogos = []
        
        # Identifica concursos com alto potencial
        concursos_potenciais = []
        for i in range(len(self.concursos)-1):
            repetidos = len(set(self.concursos[i]) & set(self.concursos[i+1]))
            if repetidos >= 9:
                concursos_potenciais.append(self.concursos[i])
        
        if not concursos_potenciais:
            concursos_potenciais = self.concursos[:10]
        
        for _ in range(n_jogos):
            # Escolhe um concurso base
            base = random.choice(concursos_potenciais)
            jogo = set(base)
            
            # Muta 3-4 números (sacrifício estratégico)
            n_mutacoes = random.randint(3, 4)
            numeros_para_remover = random.sample(list(jogo), n_mutacoes)
            
            for remover in numeros_para_remover:
                jogo.remove(remover)
            
            # Adiciona novos números (priorizando frios)
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros_frios if n not in jogo]
                if not candidatos:
                    candidatos = [n for n in self.numeros if n not in jogo]
                
                if candidatos:
                    jogo.add(random.choice(candidatos))
            
            jogo_ordenado = sorted(jogo)
            
            # Validação básica
            if self._calcular_max_sequencia(jogo_ordenado) <= 4:
                jogos.append(jogo_ordenado)
        
        return jogos[:n_jogos]
    
    # =================================================
    # ESTRATÉGIA 3 - ENSEMBLE ROMPEDOR (RECOMENDADA)
    # =================================================
    def estrategia_ensemble_rompedor(self, n_jogos=15):
        """
        Combina múltiplas abordagens com diversidade forçada
        """
        jogos_finais = []
        
        # Distribuição estratégica
        n_rompedores = n_jogos // 3
        n_repeticao = n_jogos // 3
        n_extremos = n_jogos - n_rompedores - n_repeticao
        
        # Gera jogos de cada tipo
        jogos_rompedores = self.estrategia_rompedora(n_rompedores * 2, jogos_finais)
        jogos_repeticao = self.estrategia_repeticao(n_repeticao * 2, jogos_finais + jogos_rompedores)
        
        # Seleciona os melhores garantindo diversidade
        todos_candidatos = jogos_rompedores + jogos_repeticao
        
        # Embaralha para garantir variedade
        random.shuffle(todos_candidatos)
        
        for jogo in todos_candidatos:
            if len(jogos_finais) >= n_jogos:
                break
            
            # Verifica diversidade
            repetido = False
            for existente in jogos_finais:
                if len(set(existente) & set(jogo)) > 9:
                    repetido = True
                    break
            
            if not repetido:
                jogos_finais.append(jogo)
        
        # Completa com extremos se necessário
        while len(jogos_finais) < n_jogos:
            # Gera um jogo extremo (soma baixa ou alta)
            if random.random() < 0.5:
                # Soma baixa: prioriza números pequenos
                jogo = sorted(random.sample(range(1, 13), 8) + random.sample(range(13, 26), 7))
            else:
                # Soma alta: prioriza números grandes
                jogo = sorted(random.sample(range(1, 13), 7) + random.sample(range(13, 26), 8))
            
            if self._calcular_max_sequencia(jogo) <= 4:
                jogos_finais.append(jogo)
        
        return jogos_finais[:n_jogos]
    
    def _calcular_max_sequencia(self, jogo):
        """Calcula o tamanho máximo de sequência consecutiva"""
        max_seq = 1
        seq_atual = 1
        
        for i in range(len(jogo)-1):
            if jogo[i+1] - jogo[i] == 1:
                seq_atual += 1
                max_seq = max(max_seq, seq_atual)
            else:
                seq_atual = 1
        
        return max_seq
    
    # =================================================
    # CONFERÊNCIA AVANÇADA
    # =================================================
    def conferir_jogos_avancada(self, jogos, concurso_alvo=None):
        """Conferência detalhada"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            
            # Análise de padrões
            max_seq = self._calcular_max_sequencia(jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)
            
            # Classificação do jogo
            if acertos >= 12:
                classificacao = "🔥 POTENCIAL"
            elif acertos >= 11:
                classificacao = "✅ BOM"
            elif acertos >= 10:
                classificacao = "⚠️ REGULAR"
            else:
                classificacao = "❌ RUIM"
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Classificação": classificacao,
                "Soma": sum(jogo),
                "Pares": pares,
                "Ímpares": 15 - pares,
                "Max Sequência": max_seq,
                "Números Quentes": len([n for n in jogo if n in self.numeros_quentes]),
                "Números Frios": len([n for n in jogo if n in self.numeros_frios])
            })
        
        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - ANALISADOR AGRESSIVO V3")
    
    st.markdown("""
    ### 🚀 Versão Especializada para 12-14 Pontos
    
    **Principais melhorias:**
    - 🔥 **Limite rígido de 4 números consecutivos**
    - 🎯 **Sacrifício estratégico de números quentes**
    - ❄️ **Inclusão forçada de números frios**
    - 📊 **Diversidade garantida entre jogos**
    - ⚡ **Jogos extremos para romper o teto**
    
    ⚠️ **Aviso:** Não há garantia de ganhos. Use com responsabilidade!
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
        
        qtd = st.slider("Concursos para análise", 50, 1000, 150, 50)
        
        if st.button("🔄 Carregar dados", type="primary"):
            with st.spinner("Carregando..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if len(concursos) >= 20:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilAgressiva(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos")
                        
                        # Mostra números quentes/frios
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"🔥 Quentes: {st.session_state.analise.numeros_quentes}")
                        with col2:
                            st.warning(f"❄️ Frios: {st.session_state.analise.numeros_frios}")
                        
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Abas
    if st.session_state.concursos and len(st.session_state.concursos) >= 20:
        tab1, tab2, tab3 = st.tabs(["📊 Análise", "🎲 Gerar Jogos", "📈 Resultados"])
        
        with tab1:
            st.header("📊 Análise Estratégica")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Frequência
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência (%) - Peso nos últimos 30",
                    labels={'x': 'Número', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                # Defasagem
                fig_def = px.bar(
                    x=range(1, 26),
                    y=[st.session_state.analise.defasagens[n] for n in range(1, 26)],
                    title="Concursos sem sair",
                    labels={'x': 'Número', 'y': 'Defasagem'}
                )
                st.plotly_chart(fig_def, use_container_width=True)
            
            # Estatísticas de sequências
            st.subheader("📈 Análise de Sequências")
            
            sequencias_data = []
            for concurso in st.session_state.concursos[:50]:  # Últimos 50
                max_seq = 0
                seq_atual = 1
                for i in range(len(concurso)-1):
                    if concurso[i+1] - concurso[i] == 1:
                        seq_atual += 1
                        max_seq = max(max_seq, seq_atual)
                    else:
                        seq_atual = 1
                sequencias_data.append(max_seq)
            
            fig_seq = px.histogram(
                sequencias_data, 
                nbins=10,
                title="Distribuição de Sequências nos Últimos 50 Concursos"
            )
            st.plotly_chart(fig_seq, use_container_width=True)
        
        with tab2:
            st.header("🎲 Gerar Jogos - Modo Agressivo")
            
            estrategia = st.selectbox(
                "Estratégia (Recomendado: Ensemble Rompedor)",
                [
                    "🚀 Ensemble Rompedor (RECOMENDADO)",
                    "⚡ Rompedora de Teto",
                    "🔄 Caça Repetições"
                ]
            )
            
            quantidade = st.number_input("Quantidade de jogos", 5, 50, 15)
            
            if st.button("🔥 Gerar jogos agressivos", type="primary"):
                with st.spinner("Gerando jogos com quebra de padrão..."):
                    mapa = {
                        "🚀 Ensemble Rompedor (RECOMENDADO)": st.session_state.analise.estrategia_ensemble_rompedor,
                        "⚡ Rompedora de Teto": st.session_state.analise.estrategia_rompedora,
                        "🔄 Caça Repetições": st.session_state.analise.estrategia_repeticao
                    }
                    
                    st.session_state.jogos = mapa[estrategia](quantidade)
                    st.success(f"✅ {len(st.session_state.jogos)} jogos gerados!")
                    
                    # Mostra estatísticas dos jogos gerados
                    if st.session_state.jogos:
                        st.subheader("📊 Estatísticas dos jogos gerados")
                        
                        # Calcula médias
                        somas = [sum(j) for j in st.session_state.jogos]
                        quentes = [len([n for n in j if n in st.session_state.analise.numeros_quentes]) 
                                  for j in st.session_state.jogos]
                        frios = [len([n for n in j if n in st.session_state.analise.numeros_frios]) 
                                for j in st.session_state.jogos]
                        sequencias = [st.session_state.analise._calcular_max_sequencia(j) 
                                     for j in st.session_state.jogos]
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Média Soma", f"{np.mean(somas):.0f}")
                        with col2:
                            st.metric("Média Quentes", f"{np.mean(quentes):.1f}")
                        with col3:
                            st.metric("Média Frios", f"{np.mean(frios):.1f}")
                        with col4:
                            st.metric("Max Sequência", f"{max(sequencias)}")
        
        with tab3:
            if st.session_state.jogos:
                st.header("📈 Resultados")
                
                # Opção de resultado manual
                with st.expander("🔢 Inserir resultado do sorteio"):
                    resultado_input = st.text_input(
                        "15 números separados por vírgula",
                        placeholder="01,02,03,04,05,06,07,08,09,10,11,12,13,14,15"
                    )
                    
                    if st.button("Conferir"):
                        try:
                            nums = [int(x.strip()) for x in resultado_input.split(',')]
                            if len(nums) == 15:
                                st.session_state.resultado_manual = sorted(nums)
                                st.success("Resultado carregado!")
                            else:
                                st.error("Digite exatamente 15 números!")
                        except:
                            st.error("Formato inválido!")
                
                # Define concurso alvo
                concurso_alvo = st.session_state.get(
                    'resultado_manual', 
                    st.session_state.analise.ultimo_concurso
                )
                
                # Conferência
                resultado = st.session_state.analise.conferir_jogos_avancada(
                    st.session_state.jogos, concurso_alvo
                )
                df_resultado = pd.DataFrame(resultado)
                st.dataframe(df_resultado, use_container_width=True)
                
                # Estatísticas
                st.subheader("📊 Análise de Desempenho")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    media = df_resultado['Acertos'].mean()
                    st.metric("Média Acertos", f"{media:.2f}")
                
                with col2:
                    max_acertos = df_resultado['Acertos'].max()
                    st.metric("Máximo", max_acertos)
                
                with col3:
                    acima_11 = sum(df_resultado['Acertos'] >= 11)
                    st.metric("≥11 pontos", acima_11)
                
                with col4:
                    acima_12 = sum(df_resultado['Acertos'] >= 12)
                    st.metric("≥12 pontos", acima_12)
                
                # Distribuição
                fig = px.histogram(
                    df_resultado, 
                    x='Acertos', 
                    nbins=15,
                    title='Distribuição de Acertos',
                    color_discrete_sequence=['#FF4B4B']
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Exportação
                csv = df_resultado.to_csv(index=False)
                st.download_button(
                    label="📥 Exportar CSV",
                    data=csv,
                    file_name=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ℹ️ Gere jogos primeiro!")

if __name__ == "__main__":
    main()
