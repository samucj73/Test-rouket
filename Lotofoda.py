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
    page_title="🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL V2 (FILTROS BALANCEADOS)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL OTIMIZADA - VERSÃO BALANCEADA
# =====================================================
class AnaliseLotofacilAvancada:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # Análises estatísticas avançadas
        self.frequencias = self._calcular_frequencias_avancadas()
        self.defasagens = self._calcular_defasagens()
        self.padroes_combinatorios = self._analisar_padroes_combinatorios()
        self.matriz_correlacao = self._calcular_matriz_correlacao()
        self.probabilidades_condicionais = self._calcular_prob_condicionais()
        self.tendencias_temporais = self._analisar_tendencias_temporais()
        
        # Análise de sequências e padrões específicos
        self.padroes_sequencia = self._analisar_sequencias()
        self.numeros_chave = self._identificar_numeros_chave()
        
    def _calcular_frequencias_avancadas(self):
        """Calcula frequências com ponderação temporal"""
        frequencias = {}
        for num in self.numeros:
            ocorrencias = 0
            peso_total = 0
            
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    # Peso exponencial para dar mais importância aos concursos recentes
                    peso = np.exp(-i / 30)
                    ocorrencias += 1
                    peso_total += peso
            
            # Frequência ponderada
            frequencias[num] = (peso_total / self.total_concursos) * 100 if self.total_concursos > 0 else 0
            
        return frequencias
    
    def _calcular_matriz_correlacao(self):
        """Calcula correlação entre números"""
        matriz = defaultdict(lambda: defaultdict(float))
        
        for num1 in self.numeros:
            for num2 in self.numeros:
                if num1 < num2:
                    # Conta quantas vezes aparecem juntos
                    juntos = sum(1 for c in self.concursos if num1 in c and num2 in c)
                    probabilidade = juntos / self.total_concursos if self.total_concursos > 0 else 0
                    matriz[num1][num2] = probabilidade
                    matriz[num2][num1] = probabilidade
        
        return matriz
    
    def _calcular_prob_condicionais(self):
        """Calcula probabilidades condicionais P(A|B)"""
        prob_cond = defaultdict(lambda: defaultdict(float))
        
        for num1 in self.numeros:
            for num2 in self.numeros:
                if num1 != num2:
                    # Probabilidade de num1 dado que num2 apareceu
                    concursos_com_num2 = [c for c in self.concursos if num2 in c]
                    if concursos_com_num2:
                        juntos = sum(1 for c in concursos_com_num2 if num1 in c)
                        prob_cond[num1][num2] = juntos / len(concursos_com_num2)
        
        return prob_cond
    
    def _analisar_padroes_combinatorios(self):
        """Análise avançada de padrões combinatórios"""
        padroes = {
            'somas': [],
            'pares': [],
            'impares': [],
            'primos': [],
            'quadrantes': [],
            'intervalos': [],
            'repetidos_consecutivos': [],
            'sequencias': []
        }
        
        for concurso in self.concursos:
            # Análise de somas
            padroes['somas'].append(sum(concurso))
            
            # Análise par/ímpar
            pares = sum(1 for n in concurso if n % 2 == 0)
            padroes['pares'].append(pares)
            padroes['impares'].append(15 - pares)
            
            # Análise de números primos (até 25)
            primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
            padroes['primos'].append(sum(1 for n in concurso if n in primos))
            
            # Análise por quadrantes (1-12, 13-25)
            padroes['quadrantes'].append(sum(1 for n in concurso if n <= 12))
            
            # Análise de intervalos entre números
            if len(concurso) > 1:
                intervalos = [concurso[i+1] - concurso[i] for i in range(len(concurso)-1)]
                padroes['intervalos'].append(np.mean(intervalos))
            
            # Análise de números repetidos do concurso anterior
            if len(self.concursos) > 1 and concurso != self.concursos[0]:
                idx = self.concursos.index(concurso)
                if idx < len(self.concursos) - 1:
                    anterior = self.concursos[idx + 1]
                    repetidos = len(set(concurso) & set(anterior))
                    padroes['repetidos_consecutivos'].append(repetidos)
            
            # Detectar sequências (3+ números consecutivos)
            seq_count = 0
            i = 0
            while i < len(concurso)-2:
                if concurso[i+2] - concurso[i+1] == 1 and concurso[i+1] - concurso[i] == 1:
                    seq_count += 1
                    i += 3
                else:
                    i += 1
            padroes['sequencias'].append(seq_count)
        
        return padroes
    
    def _analisar_sequencias(self):
        """Analisa padrões de sequências numéricas"""
        sequencias = {
            '2_consecutivos': [],
            '3_consecutivos': [],
            '4_consecutivos': [],
            'intervalos_comuns': []
        }
        
        for concurso in self.concursos:
            # Conta pares consecutivos
            pares_consec = 0
            triplas_consec = 0
            quadras_consec = 0
            
            i = 0
            while i < len(concurso)-1:
                if concurso[i+1] - concurso[i] == 1:
                    pares_consec += 1
                    
                    if i < len(concurso)-2 and concurso[i+2] - concurso[i+1] == 1:
                        triplas_consec += 1
                        
                        if i < len(concurso)-3 and concurso[i+3] - concurso[i+2] == 1:
                            quadras_consec += 1
                            i += 3
                        else:
                            i += 2
                    else:
                        i += 1
                else:
                    i += 1
            
            sequencias['2_consecutivos'].append(pares_consec)
            sequencias['3_consecutivos'].append(triplas_consec)
            sequencias['4_consecutivos'].append(quadras_consec)
        
        return sequencias
    
    def _identificar_numeros_chave(self):
        """Identifica números que frequentemente aparecem juntos"""
        numeros_chave = []
        
        # Números que aparecem em mais de 50% dos concursos recentes
        for num in self.numeros:
            freq_recente = sum(1 for c in self.concursos[:20] if num in c)
            if freq_recente > 10:  # Apareceu em mais da metade dos últimos 20
                numeros_chave.append(num)
        
        return numeros_chave
    
    def _analisar_tendencias_temporais(self):
        """Analisa tendências temporais dos números"""
        tendencias = {}
        
        for num in self.numeros:
            # Cria série temporal de aparições
            serie = [1 if num in c else 0 for c in self.concursos]
            
            # Média móvel dos últimos 10 concursos
            if len(serie) >= 10:
                media_movel = np.convolve(serie, np.ones(10)/10, mode='valid')
                tendencias[num] = {
                    'tendencia': 'alta' if len(media_movel) > 1 and media_movel[-1] > media_movel[0] else 'baixa',
                    'momento': media_movel[-1] if len(media_movel) > 0 else 0,
                    'volatilidade': np.std(serie)
                }
            else:
                tendencias[num] = {
                    'tendencia': 'estável',
                    'momento': 0,
                    'volatilidade': 0
                }
        
        return tendencias
    
    def _calcular_defasagens(self):
        """Calcula defasagem real e defasagem ponderada"""
        defasagens = {}
        
        for num in self.numeros:
            # Encontra última aparição
            ultima_aparicao = None
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    ultima_aparicao = i
                    break
            
            if ultima_aparicao is not None:
                defasagem_real = ultima_aparicao
                # Defasagem ponderada pela frequência histórica
                frequencia_historica = self.frequencias[num]
                defasagem_ponderada = defasagem_real * (1 - frequencia_historica/100)
                defasagens[num] = {
                    'real': defasagem_real,
                    'ponderada': defasagem_ponderada,
                    'status': 'atrasado' if defasagem_real > 5 else 'normal'
                }
            else:
                defasagens[num] = {
                    'real': len(self.concursos),
                    'ponderada': len(self.concursos),
                    'status': 'critico'
                }
        
        return defasagens
    
    # =================================================
    # FUNÇÃO DE VALIDAÇÃO BALANCEADA
    # =================================================
    def validar_jogo_balanceado(self, jogo):
        """VALIDAÇÃO BALANCEADA - Rigorosa mas realista"""
        validacao = {
            'valido': True,
            'motivos': [],
            'score': 0,
            'avisos': []
        }
        
        # =============================================
        # FILTRO 1: LIMITE DE SEQUÊNCIAS (MAIS REALISTA)
        # =============================================
        # Verifica sequência MÁXIMA de números consecutivos
        max_consecutivo = 0
        atual = 1
        
        for i in range(len(jogo)-1):
            if jogo[i+1] - jogo[i] == 1:
                atual += 1
                max_consecutivo = max(max_consecutivo, atual)
            else:
                atual = 1
        
        # Bloqueia apenas sequências MUITO longas (6+)
        if max_consecutivo >= 6:
            validacao['valido'] = False
            validacao['motivos'].append(f"Sequência muito longa de {max_consecutivo} números")
            return validacao
        
        # Conta pares consecutivos totais (aviso, não bloqueio)
        consecutivos = 0
        for i in range(len(jogo)-1):
            if jogo[i+1] - jogo[i] == 1:
                consecutivos += 1
        
        if consecutivos > 6:
            validacao['avisos'].append(f"Muitos consecutivos ({consecutivos})")
        
        # =============================================
        # FILTRO 2: PARES x ÍMPARES (MAIS FLEXÍVEL)
        # =============================================
        pares = sum(1 for n in jogo if n % 2 == 0)
        impares = 15 - pares
        
        # Aceita 6-9 pares (antes era só 7-8)
        if pares < 6 or pares > 9:
            validacao['valido'] = False
            validacao['motivos'].append(f"Proporção par/ímpar inválida ({pares}-{impares})")
            return validacao
        
        # =============================================
        # FILTRO 3: SOMA (MAIS FLEXÍVEL)
        # =============================================
        soma_jogo = sum(jogo)
        if soma_jogo < 165 or soma_jogo > 215:
            validacao['valido'] = False
            validacao['motivos'].append(f"Soma {soma_jogo} fora do intervalo 165-215")
            return validacao
        
        # =============================================
        # FILTRO 4: PRIMOS (MAIS FLEXÍVEL)
        # =============================================
        primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        qtd_primos = sum(1 for n in jogo if n in primos)
        
        # Aceita 4-7 primos (antes era só 5-6)
        if qtd_primos < 4 or qtd_primos > 7:
            validacao['valido'] = False
            validacao['motivos'].append(f"Quantidade de primos inválida ({qtd_primos})")
            return validacao
        
        # =============================================
        # FILTRO 5: QUADRANTES (MAIS FLEXÍVEL)
        # =============================================
        # Quadrante 1: 1-12
        quad1 = sum(1 for n in jogo if 1 <= n <= 12)
        # Quadrante 2: 13-25
        quad2 = sum(1 for n in jogo if 13 <= n <= 25)
        
        # Aceita até 8 em um quadrante (antes era 6)
        if quad1 > 8 or quad2 > 8:
            validacao['valido'] = False
            validacao['motivos'].append(f"Concentração no quadrante (Q1:{quad1}, Q2:{quad2})")
            return validacao
        
        # =============================================
        # FILTRO 6: REPETIÇÃO DO ÚLTIMO CONCURSO (MAIS FLEXÍVEL)
        # =============================================
        if self.ultimo_concurso:
            repeticoes = len(set(jogo) & set(self.ultimo_concurso))
            
            # Aceita 5-9 repetições (antes era 6-8)
            if repeticoes < 5 or repeticoes > 9:
                validacao['valido'] = False
                validacao['motivos'].append(f"Repetição do último concurso: {repeticoes} (deve ser 5-9)")
                return validacao
        
        # =============================================
        # FILTRO 7: DISTRIBUIÇÃO POR EXTREMOS (AVISO, NÃO BLOQUEIO)
        # =============================================
        baixos = sum(1 for n in jogo if 1 <= n <= 5)
        altos = sum(1 for n in jogo if 21 <= n <= 25)
        
        if baixos < 1 or baixos > 5:
            validacao['avisos'].append(f"Distribuição de baixos atípica ({baixos})")
        
        if altos < 1 or altos > 5:
            validacao['avisos'].append(f"Distribuição de altos atípica ({altos})")
        
        # =============================================
        # CÁLCULO DO SCORE DE QUALIDADE
        # =============================================
        score = 100  # Base
        
        # Penaliza proporção par/ímpar
        score -= abs(pares - 7.5) * 5
        
        # Penaliza soma distante da média
        score -= abs(soma_jogo - 190) / 2
        
        # Premia quantidade ideal de primos (5-6)
        if 5 <= qtd_primos <= 6:
            score += 10
        elif 4 <= qtd_primos <= 7:
            score += 5
        
        # Premia boa distribuição
        if 6 <= quad1 <= 8:
            score += 5
        
        # Premia repetição ideal (6-8)
        if self.ultimo_concurso:
            if 6 <= repeticoes <= 8:
                score += 10
            elif 5 <= repeticoes <= 9:
                score += 5
        
        # Penaliza muitos consecutivos
        score -= consecutivos * 2
        
        validacao['score'] = max(0, round(score, 2))
        
        return validacao
    
    # =================================================
    # ESTRATÉGIA BALANCEADA
    # =================================================
    def estrategia_balanceada(self, n_jogos=15):
        """Estratégia com filtros balanceados"""
        jogos = []
        tentativas = 0
        max_tentativas = n_jogos * 50  # Reduzido porque mais jogos vão passar
        
        while len(jogos) < n_jogos and tentativas < max_tentativas:
            tentativas += 1
            
            # =========================================
            # 1. BASE: 5 a 9 números do último concurso
            # =========================================
            jogo = set()
            
            # Define quantos repetir do último concurso (5 a 9)
            qtd_repetir = random.randint(5, 9)
            
            # Seleciona números do último concurso
            if self.ultimo_concurso:
                repetidos = random.sample(self.ultimo_concurso, min(qtd_repetir, len(self.ultimo_concurso)))
                jogo.update(repetidos)
            
            # =========================================
            # 2. ADICIONA NÚMEROS CHAVE
            # =========================================
            if self.numeros_chave:
                chave_disponiveis = [n for n in self.numeros_chave if n not in jogo]
                if chave_disponiveis:
                    qtd_chave = random.randint(1, min(3, len(chave_disponiveis)))
                    jogo.update(random.sample(chave_disponiveis, qtd_chave))
            
            # =========================================
            # 3. COMPLETA COM NÚMEROS ESTRATÉGICOS
            # =========================================
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros if n not in jogo]
                
                if not candidatos:
                    break
                
                # Calcula pesos para cada candidato
                pesos = []
                for num in candidatos:
                    peso = 0
                    
                    # Peso por frequência
                    peso += self.frequencias[num]
                    
                    # Peso por defasagem
                    defasagem = self.defasagens[num]['real']
                    peso += defasagem * 2
                    
                    # Peso por tendência
                    if self.tendencias_temporais[num]['tendencia'] == 'alta':
                        peso += 15
                    
                    pesos.append(max(peso, 1))
                
                # Seleciona próximo número
                if sum(pesos) > 0:
                    novo_num = random.choices(candidatos, weights=pesos)[0]
                else:
                    novo_num = random.choice(candidatos)
                
                jogo.add(novo_num)
            
            jogo_ordenado = sorted(jogo)
            
            # =========================================
            # 4. APLICA FILTROS BALANCEADOS
            # =========================================
            if len(jogo_ordenado) == 15:
                validacao = self.validar_jogo_balanceado(jogo_ordenado)
                
                if validacao['valido']:
                    # Adiciona score e avisos ao jogo
                    jogos.append((jogo_ordenado, validacao['score'], validacao['avisos']))
        
        # Ordena por score e retorna apenas os jogos
        jogos.sort(key=lambda x: x[1], reverse=True)
        return [jogo for jogo, _, _ in jogos[:n_jogos]]
    
    # =================================================
    # ESTRATÉGIA ULTRA (OPÇÃO MAIS RIGOROSA)
    # =================================================
    def estrategia_ultra(self, n_jogos=15):
        """Versão ultra rigorosa (poucos jogos, altíssima qualidade)"""
        jogos = []
        tentativas = 0
        max_tentativas = n_jogos * 200  # Mais tentativas porque é mais rigoroso
        
        while len(jogos) < n_jogos and tentativas < max_tentativas:
            tentativas += 1
            
            # Processo similar mas com validação mais rigorosa
            jogo = set()
            
            # Repetição ideal (6-8)
            qtd_repetir = random.randint(6, 8)
            if self.ultimo_concurso:
                repetidos = random.sample(self.ultimo_concurso, min(qtd_repetir, len(self.ultimo_concurso)))
                jogo.update(repetidos)
            
            # Completa com inteligência
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros if n not in jogo]
                if candidatos:
                    # Prioriza números com alta frequência
                    candidatos_freq = sorted(candidatos, key=lambda x: self.frequencias[x], reverse=True)
                    jogo.add(random.choice(candidatos_freq[:10]))
                else:
                    break
            
            jogo_ordenado = sorted(jogo)
            
            if len(jogo_ordenado) == 15:
                # Usa uma validação ainda mais rigorosa
                # (podemos implementar depois se necessário)
                validacao = self.validar_jogo_balanceado(jogo_ordenado)
                if validacao['valido'] and validacao['score'] > 85:  # Score mínimo
                    jogos.append(jogo_ordenado)
        
        return jogos[:n_jogos]
    
    # =================================================
    # CONFERÊNCIA AVANÇADA
    # =================================================
    def conferir_jogos_avancada(self, jogos, concurso_alvo=None):
        """Conferência detalhada com análise estatística"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            # Validação com filtros balanceados
            validacao = self.validar_jogo_balanceado(jogo)
            
            # Conferência básica
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            
            # Análise detalhada
            pares_jogo = sum(1 for n in jogo if n % 2 == 0)
            
            # Análise de quadrantes
            quad1_jogo = sum(1 for n in jogo if n <= 12)
            
            # Análise de primos
            primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
            primos_jogo = sum(1 for n in jogo if n in primos)
            
            # Análise de sequências
            max_consecutivo = 0
            atual = 1
            for i in range(len(jogo)-1):
                if jogo[i+1] - jogo[i] == 1:
                    atual += 1
                    max_consecutivo = max(max_consecutivo, atual)
                else:
                    atual = 1
            
            # Repetições do último concurso
            repeticoes = len(set(jogo) & set(self.ultimo_concurso)) if self.ultimo_concurso else 0
            
            # Formata avisos
            avisos_str = ", ".join(validacao['avisos']) if validacao['avisos'] else "N/A"
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Soma": sum(jogo),
                "Pares": pares_jogo,
                "Q1 (1-12)": quad1_jogo,
                "Primos": primos_jogo,
                "Max Seq": max_consecutivo,
                "Repetidos": repeticoes,
                "Score": validacao['score'],
                "Válido": "✅" if validacao['valido'] else "❌",
                "Avisos": avisos_str
            })
        
        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - VERSÃO BALANCEADA")
    
    st.markdown("""
    ### ⚖️ Versão com Filtros Balanceados - Qualidade sem Exagero
    
    **Filtros ativos (realistas):**
    - 📊 Soma: 165-215 (mais flexível)
    - ⚖️ Pares/Ímpares: 6-9 (mais opções)
    - 🔢 Primos: 4-7 (mais realista)
    - 📍 Quadrantes: máx 8 (menos restritivo)
    - 🔁 Repetições: 5-9 (mais natural)
    - 🚫 Sequências: bloqueia apenas 6+ consecutivos
    
    ✅ **Agora vai gerar jogos!** Os filtros estão rigorosos mas realistas.
    """)
    
    # Inicialização da sessão
    if "concursos" not in st.session_state:
        st.session_state.concursos = []
    
    if "jogos" not in st.session_state:
        st.session_state.jogos = []
    
    if "analise" not in st.session_state:
        st.session_state.analise = None
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd = st.slider(
            "Quantidade de concursos para análise", 
            min_value=20, 
            max_value=1000, 
            value=100,
            step=20
        )
        
        if st.button("🔄 Carregar dados históricos", type="primary"):
            with st.spinner("Carregando concursos..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if len(concursos) >= 20:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilAvancada(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        ultimo = resposta[0]
                        st.info(f"📅 Último concurso: {ultimo['concurso']} - {ultimo['data']}")
                        
                except Exception as e:
                    st.error(f"Erro: {e}")
        
        # Mostra estatísticas se disponíveis
        if st.session_state.analise:
            st.divider()
            st.subheader("📊 Estatísticas")
            
            # Último concurso
            if st.session_state.analise.ultimo_concurso:
                st.write("**Último concurso:**")
                st.write(", ".join([f"{n:02d}" for n in st.session_state.analise.ultimo_concurso]))
            
            # Números chave
            if st.session_state.analise.numeros_chave:
                st.write("**Números chave:**")
                st.write(", ".join([str(n) for n in sorted(st.session_state.analise.numeros_chave)]))
    
    # Abas
    if st.session_state.concursos and len(st.session_state.concursos) >= 20:
        tab1, tab2, tab3 = st.tabs(["📈 Análise", "🎲 Gerar Jogos", "📊 Resultados"])
        
        with tab1:
            st.header("📊 Análise Estatística")
            st.info(f"📈 Analisando {len(st.session_state.concursos)} concursos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência Ponderada (%)",
                    labels={'x': 'Número', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                fig_def = px.bar(
                    x=range(1, 26),
                    y=[st.session_state.analise.defasagens[n]['real'] for n in range(1, 26)],
                    title="Defasagem (concursos sem sair)",
                    labels={'x': 'Número', 'y': 'Concursos'}
                )
                st.plotly_chart(fig_def, use_container_width=True)
            
            # Distribuição de somas
            fig_soma = px.histogram(
                st.session_state.analise.padroes_combinatorios['somas'],
                nbins=30,
                title="Distribuição das Somas (Intervalo Alvo: 165-215)",
                labels={'value': 'Soma', 'count': 'Frequência'}
            )
            fig_soma.add_vline(x=165, line_dash="dash", line_color="red")
            fig_soma.add_vline(x=215, line_dash="dash", line_color="red")
            st.plotly_chart(fig_soma, use_container_width=True)
        
        with tab2:
            st.header("🎲 GERAR JOGOS COM FILTROS BALANCEADOS")
            
            estrategia = st.radio(
                "Escolha o nível de rigor:",
                [
                    "⚖️ Balanceada (recomendada) - Mais jogos, boa qualidade",
                    "🔥 Ultra - Menos jogos, qualidade superior"
                ]
            )
            
            quantidade = st.number_input("Quantidade de jogos desejada", 5, 50, 15)
            
            if st.button("🎲 GERAR JOGOS", type="primary"):
                with st.spinner("Gerando jogos com filtros balanceados..."):
                    if "Balanceada" in estrategia:
                        st.session_state.jogos = st.session_state.analise.estrategia_balanceada(quantidade)
                    else:
                        st.session_state.jogos = st.session_state.analise.estrategia_ultra(quantidade)
                    
                    if len(st.session_state.jogos) < quantidade:
                        st.warning(f"⚠️ Gerados apenas {len(st.session_state.jogos)} jogos que passaram nos filtros")
                    else:
                        st.success(f"✅ {len(st.session_state.jogos)} jogos de alta qualidade gerados!")
        
        with tab3:
            if st.session_state.jogos:
                st.header("📊 Resultados")
                
                # Permite inserir resultado manual
                with st.expander("🔢 Inserir resultado do sorteio manualmente"):
                    resultado_input = st.text_input(
                        "Digite os números (separados por vírgula ou espaço)",
                        placeholder="Ex: 01,04,05,06,10,11,13,14,16,18,19,20,21,23,24"
                    )
                    
                    if st.button("Conferir com resultado manual"):
                        try:
                            if ',' in resultado_input:
                                nums = [int(x.strip()) for x in resultado_input.split(',')]
                            else:
                                nums = [int(x) for x in resultado_input.split()]
                            
                            if len(nums) == 15:
                                st.session_state.resultado_manual = sorted(nums)
                                st.success("Resultado carregado!")
                            else:
                                st.error("Digite exatamente 15 números!")
                        except:
                            st.error("Formato inválido!")
                
                # Escolhe concurso alvo
                concurso_alvo = st.session_state.get('resultado_manual', st.session_state.analise.ultimo_concurso)
                
                # Conferência
                resultado = st.session_state.analise.conferir_jogos_avancada(
                    st.session_state.jogos, concurso_alvo
                )
                df_resultado = pd.DataFrame(resultado)
                
                # Ordena por score
                df_resultado = df_resultado.sort_values('Score', ascending=False)
                
                st.dataframe(df_resultado, use_container_width=True)
                
                # Estatísticas
                st.subheader("📈 Estatísticas de Acertos")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Média", f"{df_resultado['Acertos'].mean():.2f}")
                with col2:
                    st.metric("Máximo", df_resultado['Acertos'].max())
                with col3:
                    st.metric("Mínimo", df_resultado['Acertos'].min())
                with col4:
                    acima_10 = sum(df_resultado['Acertos'] >= 11)
                    st.metric("≥11 pontos", acima_10)
                with col5:
                    st.metric("Jogos Válidos", sum(df_resultado['Válido'] == "✅"))
                
                # Distribuição
                fig = px.histogram(df_resultado, x='Acertos', nbins=15, 
                                  title='Distribuição de Acertos')
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
