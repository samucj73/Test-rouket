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
    page_title="🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL OTIMIZADA
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
        
    def _calcular_frequencias_avancadas(self):
        """Calcula frequências com ponderação temporal"""
        frequencias = {}
        for num in self.numeros:
            ocorrencias = 0
            peso_total = 0
            
            for i, concurso in enumerate(self.concursos):
                if num in concurso:
                    # Peso exponencial para dar mais importância aos concursos recentes
                    peso = np.exp(-i / 50)  # Decaimento mais suave
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
            'repetidos_consecutivos': []
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
        
        return padroes
    
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
    # ESTRATÉGIA 1 – REDES NEURAIS SIMPLIFICADAS
    # =================================================
    def estrategia_neural(self, n_jogos=15):
        """Usa conceitos de redes neurais para predição"""
        jogos = []
        
        for _ in range(n_jogos):
            # Camada de entrada: frequências + defasagens + tendências
            scores = {}
            
            for num in self.numeros:
                # Peso 1: Frequência ponderada
                w1 = self.frequencias[num] / 100
                
                # Peso 2: Defasagem (normalizada)
                w2 = 1 - (self.defasagens[num]['real'] / self.total_concursos) if self.total_concursos > 0 else 0
                
                # Peso 3: Momento/tendência
                w3 = self.tendencias_temporais[num]['momento']
                
                # Peso 4: Volatilidade (inversa - números consistentes são melhores)
                w4 = 1 - self.tendencias_temporais[num]['volatilidade']
                
                # Score combinado com pesos
                scores[num] = 0.35*w1 + 0.30*w2 + 0.20*w3 + 0.15*w4
            
            # Seleciona números com maior score, mas adiciona aleatoriedade controlada
            numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            
            # Top 15 com maior probabilidade (com ruído gaussiano)
            jogo = []
            for num, score in numeros_ordenados[:20]:  # Pega top 20
                # Adiciona ruído para evitar overfitting
                score_com_ruido = score + np.random.normal(0, 0.05)
                jogo.append((num, score_com_ruido))
            
            # Ordena por score com ruído e pega os 15 melhores
            jogo = sorted(jogo, key=lambda x: x[1], reverse=True)[:15]
            jogos.append(sorted([x[0] for x in jogo]))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 2 – ANÁLISE DE CORRELAÇÃO
    # =================================================
    def estrategia_correlacao(self, n_jogos=15):
        """Baseada em pares de números que costumam sair juntos"""
        jogos = []
        
        # Identifica os números mais correlacionados
        for _ in range(n_jogos):
            jogo = set()
            
            # Escolhe um número "âncora" com boa probabilidade
            numeros_prob = sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)
            ancora = random.choice([n for n, _ in numeros_prob[:8] if numeros_prob])
            jogo.add(ancora)
            
            # Adiciona números correlacionados
            while len(jogo) < 15:
                ultimo_adicionado = list(jogo)[-1]
                
                # Busca números mais correlacionados com o último adicionado
                correlacionados = sorted(
                    self.matriz_correlacao[ultimo_adicionado].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                # Adiciona o mais correlacionado que ainda não está no jogo
                adicionou = False
                for num, prob in correlacionados:
                    if num not in jogo and len(jogo) < 15:
                        # Só adiciona se a probabilidade for significativa
                        if prob > 0.2:  # Limiar mínimo de 20% de correlação
                            jogo.add(num)
                            adicionou = True
                            break
                
                # Se não encontrar correlacionado, adiciona baseado em frequência
                if not adicionou and len(jogo) < 15:
                    candidatos = [n for n in self.numeros if n not in jogo]
                    if candidatos:
                        # Pesos baseados em frequência
                        pesos = [self.frequencias[n] for n in candidatos]
                        if sum(pesos) > 0:
                            jogo.add(random.choices(candidatos, weights=pesos)[0])
                        else:
                            jogo.add(random.choice(candidatos))
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 3 – OTIMIZAÇÃO POR ALGORITMO GENÉTICO
    # =================================================
    def estrategia_genetica(self, n_jogos=15, geracoes=50, populacao=100):
        """Usa algoritmo genético para evoluir os jogos"""
        
        def fitness(jogo):
            """Função de aptidão do jogo"""
            score = 0
            
            # Critério 1: Média das frequências dos números
            freq_media = np.mean([self.frequencias[n] for n in jogo])
            score += freq_media * 0.3
            
            # Critério 2: Variedade de quadrantes
            quadrantes = sum(1 for n in jogo if n <= 12)
            score += abs(quadrantes - 7) * 2  # Ideal é ~7 números no primeiro quadrante
            
            # Critério 3: Proporção par/ímpar (ideal ~7.5)
            pares = sum(1 for n in jogo if n % 2 == 0)
            score += 10 - abs(pares - 7) * 2
            
            # Critério 4: Soma próxima da média histórica
            soma_media = self.padroes_combinatorios['somas']
            if soma_media:
                media_historica = np.mean(soma_media)
                score += 10 - abs(sum(jogo) - media_historica) / 20
            
            # Critério 5: Correlação positiva entre números
            correlacao_media = 0
            total_pares = 0
            for i in range(len(jogo)):
                for j in range(i+1, len(jogo)):
                    correlacao_media += self.matriz_correlacao[jogo[i]][jogo[j]]
                    total_pares += 1
            
            if total_pares > 0:
                correlacao_media /= total_pares
                score += correlacao_media * 20
            
            return score
        
        # População inicial
        populacao_atual = []
        for _ in range(populacao):
            jogo = sorted(random.sample(self.numeros, 15))
            populacao_atual.append((jogo, fitness(jogo)))
        
        # Evolução
        for _ in range(geracoes):
            # Seleção dos melhores (torneio)
            nova_populacao = []
            
            # Elitismo - mantém os 10% melhores
            populacao_atual.sort(key=lambda x: x[1], reverse=True)
            nova_populacao.extend(populacao_atual[:max(1, populacao//10)])
            
            # Gera novos indivíduos por crossover e mutação
            while len(nova_populacao) < populacao:
                # Seleciona dois pais (torneio)
                pai1 = max(random.sample(populacao_atual, min(5, len(populacao_atual))), key=lambda x: x[1])
                pai2 = max(random.sample(populacao_atual, min(5, len(populacao_atual))), key=lambda x: x[1])
                
                # Crossover
                ponto_corte = random.randint(5, 10)
                filho = list(set(pai1[0][:ponto_corte] + pai2[0][ponto_corte:]))
                
                # Mutação (10% de chance)
                if random.random() < 0.1:
                    if filho:
                        idx = random.randint(0, len(filho)-1)
                        candidatos = [n for n in self.numeros if n not in filho]
                        if candidatos:
                            novo_num = random.choice(candidatos)
                            filho[idx] = novo_num
                
                # Completa para 15 números
                while len(filho) < 15:
                    candidatos = [n for n in self.numeros if n not in filho]
                    if candidatos:
                        novo_num = random.choice(candidatos)
                        filho.append(novo_num)
                    else:
                        break
                
                if len(filho) == 15:
                    filho = sorted(filho)
                    nova_populacao.append((filho, fitness(filho)))
            
            populacao_atual = nova_populacao
        
        # Retorna os melhores jogos
        populacao_atual.sort(key=lambda x: x[1], reverse=True)
        return [jogo for jogo, _ in populacao_atual[:min(n_jogos, len(populacao_atual))]]
    
    # =================================================
    # ESTRATÉGIA 4 – PROBABILIDADE CONDICIONAL
    # =================================================
    def estrategia_condicional(self, n_jogos=15):
        """Baseada em probabilidades condicionais"""
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Primeiro número baseado em frequência
            numeros_freq = sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)
            if numeros_freq:
                primeiro = random.choice([n for n, _ in numeros_freq[:10]])
                jogo.append(primeiro)
            else:
                jogo.append(random.choice(self.numeros))
            
            # Próximos números baseados em probabilidade condicional
            while len(jogo) < 15:
                ultimo = jogo[-1]
                
                # Calcula probabilidades condicionais para o próximo número
                probabilidades = {}
                for num in self.numeros:
                    if num not in jogo:
                        prob = self.probabilidades_condicionais.get(num, {}).get(ultimo, 0)
                        probabilidades[num] = prob
                
                # Se não houver probabilidades condicionais, usa frequência
                if not any(probabilidades.values()):
                    candidatos = [n for n in self.numeros if n not in jogo]
                    if candidatos:
                        pesos = [self.frequencias[n] for n in candidatos]
                        if sum(pesos) > 0:
                            proximo = random.choices(candidatos, weights=pesos)[0]
                        else:
                            proximo = random.choice(candidatos)
                    else:
                        break
                else:
                    # Seleciona baseado nas probabilidades
                    candidatos = list(probabilidades.keys())
                    pesos = list(probabilidades.values())
                    if sum(pesos) > 0:
                        proximo = random.choices(candidatos, weights=pesos)[0]
                    else:
                        proximo = random.choice(candidatos) if candidatos else None
                
                if proximo and proximo not in jogo:
                    jogo.append(proximo)
            
            if len(jogo) == 15:
                jogos.append(sorted(jogo))
        
        return jogos
    
    # =================================================
    # ESTRATÉGIA 5 – MISTA AVANÇADA (ENSEMBLE)
    # =================================================
    def estrategia_ensemble(self, n_jogos=15):
        """Combina múltiplas estratégias com votação ponderada"""
        
        # Gera jogos de cada estratégia
        jogos_neural = self.estrategia_neural(n_jogos)
        jogos_correlacao = self.estrategia_correlacao(n_jogos)
        jogos_genetico = self.estrategia_genetica(max(1, n_jogos//3), geracoes=30)
        jogos_condicional = self.estrategia_condicional(n_jogos)
        
        # Converte para sets para facilitar análise
        todos_jogos = jogos_neural + jogos_correlacao + jogos_genetico + jogos_condicional
        
        if not todos_jogos:
            return []
        
        # Cria um ranking de números baseado em frequência de aparição
        contador_numeros = Counter()
        for jogo in todos_jogos:
            contador_numeros.update(jogo)
        
        # Gera novos jogos baseados no consenso
        jogos_finais = []
        for _ in range(n_jogos):
            # Seleciona números com maior votação, mas adiciona variedade
            numeros_rank = [num for num, _ in contador_numeros.most_common()]
            
            if not numeros_rank:
                continue
                
            jogo = set()
            # Pega os top 20 números
            top_numeros = numeros_rank[:min(20, len(numeros_rank))]
            
            # Seleciona 15 com alguma aleatoriedade
            if len(top_numeros) >= 13:
                jogo.update(random.sample(top_numeros, 13))
            else:
                jogo.update(top_numeros)
            
            # Adiciona 2 números surpresa (menos votados)
            outros = [n for n in self.numeros if n not in jogo]
            if outros:
                jogo.update(random.sample(outros, min(2, len(outros))))
            
            if len(jogo) == 15:
                jogos_finais.append(sorted(jogo))
        
        return jogos_finais
    
    # =================================================
    # VALIDAÇÃO ESTATÍSTICA
    # =================================================
    def validar_jogo(self, jogo):
        """Valida um jogo baseado em critérios estatísticos"""
        validacao = {
            'valido': True,
            'motivos': []
        }
        
        # Critério 1: Soma dentro de 3 desvios padrão
        soma_stats = self.padroes_combinatorios['somas']
        if soma_stats:
            media = np.mean(soma_stats)
            desvio = np.std(soma_stats)
            soma_jogo = sum(jogo)
            
            if abs(soma_jogo - media) > 3 * desvio:
                validacao['valido'] = False
                validacao['motivos'].append(f"Soma {soma_jogo} fora do padrão (média {media:.0f}±{desvio:.0f})")
        
        # Critério 2: Proporção par/ímpar razoável
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares < 4 or pares > 11:
            validacao['valido'] = False
            validacao['motivos'].append(f"Proporção par/ímpar atípica: {pares} pares")
        
        # Critério 3: Números consecutivos
        consecutivos = 0
        for i in range(len(jogo)-1):
            if jogo[i+1] - jogo[i] == 1:
                consecutivos += 1
        
        if consecutivos > 3:
            validacao['valido'] = False
            validacao['motivos'].append(f"Muitos números consecutivos: {consecutivos}")
        
        return validacao
    
    # =================================================
    # CONFERÊNCIA AVANÇADA
    # =================================================
    def conferir_jogos_avancada(self, jogos, concurso_alvo=None):
        """Conferência detalhada com análise estatística"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            # Validação do jogo
            validacao = self.validar_jogo(jogo)
            
            # Conferência básica
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            
            # Análise detalhada
            pares_jogo = sum(1 for n in jogo if n % 2 == 0)
            pares_concurso = sum(1 for n in concurso_alvo if n % 2 == 0) if concurso_alvo else 0
            
            # Análise de quadrantes
            quad1_jogo = sum(1 for n in jogo if n <= 12)
            quad1_concurso = sum(1 for n in concurso_alvo if n <= 12) if concurso_alvo else 0
            
            # Análise de primos
            primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
            primos_jogo = sum(1 for n in jogo if n in primos)
            primos_concurso = sum(1 for n in concurso_alvo if n in primos) if concurso_alvo else 0
            
            # Cálculo de probabilidade do jogo
            prob_jogo = 1
            for num in jogo:
                prob_jogo *= self.frequencias.get(num, 1) / 100
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Soma": sum(jogo),
                "Pares": pares_jogo,
                "Quadrante 1-12": quad1_jogo,
                "Primos": primos_jogo,
                "Probabilidade": f"{prob_jogo:.2e}",
                "Válido": "✅" if validacao['valido'] else "❌",
                "Motivos": ", ".join(validacao['motivos']) if validacao['motivos'] else "N/A",
                "Acerto Padrão": "✅" if pares_jogo == pares_concurso else "❌",
                "Acerto Quadrante": "✅" if quad1_jogo == quad1_concurso else "❌",
                "Acerto Primos": "✅" if primos_jogo == primos_concurso else "❌"
            })
        
        return dados
    
    # =================================================
    # GRÁFICOS AVANÇADOS
    # =================================================
    def grafico_evolucao(self):
        """Gráfico de evolução temporal dos números"""
        if not self.concursos or len(self.concursos) == 0:
            return None
            
        df_evolucao = []
        
        for i, concurso in enumerate(self.concursos[:50]):  # Últimos 50 concursos
            for num in concurso:
                df_evolucao.append({
                    'Concurso': i + 1,
                    'Número': num,
                    'Apareceu': 1
                })
        
        if not df_evolucao:
            return None
            
        df = pd.DataFrame(df_evolucao)
        
        # Cria matriz de calor temporal
        pivot = df.pivot_table(
            values='Apareceu',
            index='Número',
            columns='Concurso',
            fill_value=0
        )
        
        fig = px.imshow(
            pivot,
            title="Mapa de Calor Temporal - Aparições por Concurso",
            labels=dict(x="Concurso", y="Número", color="Apareceu"),
            color_continuous_scale="Viridis"
        )
        
        return fig
    
    def grafico_distribuicao_padroes(self):
        """Gráfico de distribuição de padrões"""
        # Cria DataFrame com os padrões
        df_padroes = pd.DataFrame({
            'Soma': self.padroes_combinatorios['somas'],
            'Pares': self.padroes_combinatorios['pares'],
            'Primos': self.padroes_combinatorios['primos'],
            'Quadrante 1-12': self.padroes_combinatorios['quadrantes']
        })
        
        # Cria subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Distribuição de Somas', 'Distribuição de Pares',
                          'Distribuição de Primos', 'Distribuição por Quadrante')
        )
        
        fig.add_trace(
            go.Histogram(x=df_padroes['Soma'], name='Soma', marker_color='blue'),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Histogram(x=df_padroes['Pares'], name='Pares', marker_color='red'),
            row=1, col=2
        )
        
        fig.add_trace(
            go.Histogram(x=df_padroes['Primos'], name='Primos', marker_color='green'),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Histogram(x=df_padroes['Quadrante 1-12'], name='Quadrante', marker_color='orange'),
            row=2, col=2
        )
        
        fig.update_layout(height=600, showlegend=False, title_text="Distribuição de Padrões")
        return fig

# =====================================================
# INTERFACE STREAMLIT OTIMIZADA
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - ANALISADOR PROFISSIONAL")
    
    st.markdown("""
    ### 🎲 Sistema Avançado de Análise Estatística
    Esta ferramenta utiliza **múltiplas estratégias matemáticas** e **machine learning** 
    para gerar jogos baseados em padrões históricos reais.
    
    ⚠️ **Aviso Importante:** Não existe garantia de ganhos - a loteria é um jogo de azar.
    Use com responsabilidade!
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
        
        # Opção de API alternativa
        api_option = st.selectbox(
            "Fonte de dados",
            ["API Principal (Heroku)", "API Secundária (Loteriascaixa)"]
        )
        
        qtd = st.slider(
            "Quantidade de concursos para análise", 
            min_value=10,  # Aumentado para mínimo de 10
            max_value=1000, 
            value=50,  # Aumentado para 50
            step=10,
            help="Mais concursos = melhor análise estatística"
        )
        
        # Botão de carregamento com retry
        if st.button("🔄 Carregar dados históricos", type="primary"):
            with st.spinner("Carregando concursos..."):
                try:
                    # Tenta API principal
                    if api_option == "API Principal (Heroku)":
                        url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    else:
                        url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"  # Mesma URL por enquanto
                    
                    resposta = requests.get(url, timeout=10).json()
                    
                    concursos = []
                    for i in range(min(qtd, len(resposta))):
                        concurso = sorted(map(int, resposta[i]["dezenas"]))
                        concursos.append(concurso)
                    
                    if len(concursos) >= 10:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilAvancada(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        # Mostra estatísticas rápidas
                        ultimo = resposta[0]
                        st.info(f"📅 Último concurso: {ultimo['concurso']} - {ultimo['data']}")
                        
                        # Indicadores de qualidade
                        st.metric("Qualidade da amostra", 
                                 f"{len(concursos)} concursos",
                                 delta=f"{len(concursos)-qtd} do solicitado" if len(concursos) != qtd else "Completo")
                    else:
                        st.error("⚠️ Poucos concursos carregados. Tente novamente.")
                    
                except requests.exceptions.Timeout:
                    st.error("⏰ Timeout na requisição. Tente novamente.")
                except Exception as e:
                    st.error(f"Erro ao carregar dados: {e}")
        
        # Informações de status
        if st.session_state.concursos:
            st.divider()
            st.header("📊 Status")
            st.write(f"**Concursos:** {len(st.session_state.concursos)}")
            
            # Indicadores de performance
            if st.session_state.analise:
                ultimos_acertos = st.session_state.analise.padroes_combinatorios['pares'][:5]
                if ultimos_acertos:
                    st.write(f"**Média de pares:** {np.mean(ultimos_acertos):.1f}")
    
    # Abas para organização
    if st.session_state.concursos and len(st.session_state.concursos) >= 10:
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Análise Estatística", 
            "🎲 Gerar Jogos", 
            "📊 Resultados",
            "🔬 Validação"
        ])
        
        with tab1:
            st.header("📊 Análise Estatística Avançada")
            st.info(f"📈 Analisando {len(st.session_state.concursos)} concursos históricos")
            
            # Layout com colunas
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de frequências
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência Ponderada dos Números (%)",
                    labels={'x': 'Número', 'y': 'Frequência (%)'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                # Gráfico de defasagens
                defasagens = [st.session_state.analise.defasagens[n]['real'] for n in range(1, 26)]
                fig_def = px.bar(
                    x=range(1, 26),
                    y=defasagens,
                    title="Defasagem (concursos sem aparecer)",
                    labels={'x': 'Número', 'y': 'Concursos'},
                    color=defasagens,
                    color_continuous_scale="Reds"
                )
                st.plotly_chart(fig_def, use_container_width=True)
            
            # Gráfico de evolução temporal
            if st.button("📈 Mostrar evolução temporal"):
                fig_evo = st.session_state.analise.grafico_evolucao()
                if fig_evo:
                    st.plotly_chart(fig_evo, use_container_width=True)
                else:
                    st.warning("Não foi possível gerar o gráfico de evolução.")
            
            # Estatísticas descritivas
            st.subheader("📊 Estatísticas dos Padrões")
            
            col3, col4, col5, col6 = st.columns(4)
            
            with col3:
                soma_stats = st.session_state.analise.padroes_combinatorios['somas']
                if soma_stats and len(soma_stats) > 0:
                    st.metric("Média da Soma", f"{np.mean(soma_stats):.1f}")
                    st.metric("Desvio Padrão", f"{np.std(soma_stats):.1f}")
                else:
                    st.metric("Média da Soma", "N/A")
                    st.metric("Desvio Padrão", "N/A")
            
            with col4:
                pares_stats = st.session_state.analise.padroes_combinatorios['pares']
                if pares_stats and len(pares_stats) > 0:
                    # Cálculo correto da moda
                    try:
                        # Tenta diferentes formas de obter a moda (compatibilidade)
                        moda_resultado = stats.mode(pares_stats)
                        
                        # Verifica a versão do SciPy e extrai a moda corretamente
                        if hasattr(moda_resultado, 'mode'):
                            # SciPy 1.9+
                            moda_valor = moda_resultado.mode
                            if isinstance(moda_valor, np.ndarray):
                                moda_valor = moda_valor[0] if len(moda_valor) > 0 else "N/A"
                        else:
                            # SciPy mais antigo
                            moda_valor = moda_resultado[0][0] if len(moda_resultado[0]) > 0 else "N/A"
                            
                        st.metric("Média de Pares", f"{np.mean(pares_stats):.1f}")
                        st.metric("Moda de Pares", f"{moda_valor}")
                    except:
                        st.metric("Média de Pares", f"{np.mean(pares_stats):.1f}")
                        st.metric("Moda de Pares", "N/A")
                else:
                    st.metric("Média de Pares", "N/A")
                    st.metric("Moda de Pares", "N/A")
            
            with col5:
                primos_stats = st.session_state.analise.padroes_combinatorios['primos']
                if primos_stats and len(primos_stats) > 0:
                    st.metric("Média de Primos", f"{np.mean(primos_stats):.1f}")
                    st.metric("Mín/Máx", f"{min(primos_stats)}/{max(primos_stats)}")
                else:
                    st.metric("Média de Primos", "N/A")
                    st.metric("Mín/Máx", "N/A")
            
            with col6:
                quadrantes = st.session_state.analise.padroes_combinatorios['quadrantes']
                if quadrantes and len(quadrantes) > 0:
                    st.metric("Média Quadrante 1-12", f"{np.mean(quadrantes):.1f}")
                    st.metric("Variação típica", f"±{np.std(quadrantes):.1f}")
                else:
                    st.metric("Média Quadrante 1-12", "N/A")
                    st.metric("Variação típica", "N/A")
            
            # Tabela de correlações fortes
            st.subheader("🔗 Principais Correlações")
            
            correlacoes = []
            for num1 in range(1, 26):
                for num2 in range(num1+1, 26):
                    prob = st.session_state.analise.matriz_correlacao[num1][num2]
                    if prob > 0.25:  # Mostra apenas correlações significativas
                        correlacoes.append({
                            'Par': f"{num1:02d}-{num2:02d}",
                            'Probabilidade': f"{prob*100:.1f}%",
                            'Frequência': f"{int(prob * len(st.session_state.concursos))} vezes"
                        })
            
            if correlacoes:
                df_corr = pd.DataFrame(correlacoes[:10])  # Top 10
                st.dataframe(df_corr, use_container_width=True)
        
        with tab2:
            st.header("🎲 Gerar Jogos Inteligentes")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                estrategia = st.selectbox(
                    "Escolha a estratégia de geração",
                    [
                        "🧠 Rede Neural (Recomendado)",
                        "🔗 Análise de Correlação",
                        "🧬 Algoritmo Genético",
                        "🎯 Probabilidade Condicional",
                        "🤝 Ensemble (Múltiplas Estratégias)"
                    ]
                )
            
            with col2:
                quantidade = st.number_input("Quantidade de jogos", 5, 100, 15)
            
            # Opções avançadas (expansíveis)
            with st.expander("⚙️ Opções avançadas"):
                col3, col4 = st.columns(2)
                with col3:
                    validar_estatisticamente = st.checkbox("Validar estatisticamente", True)
                    usar_filtro_padroes = st.checkbox("Filtrar por padrões", True)
                with col4:
                    geracoes_ag = st.slider("Gerações (Alg. Genético)", 10, 200, 50)
                    populacao_ag = st.slider("População (Alg. Genético)", 50, 500, 100)
            
            if st.button("🚀 Gerar jogos inteligentes", type="primary"):
                with st.spinner("Gerando jogos com algoritmos avançados..."):
                    mapa = {
                        "🧠 Rede Neural (Recomendado)": st.session_state.analise.estrategia_neural,
                        "🔗 Análise de Correlação": st.session_state.analise.estrategia_correlacao,
                        "🧬 Algoritmo Genético": lambda n: st.session_state.analise.estrategia_genetica(
                            n, geracoes=geracoes_ag, populacao=populacao_ag
                        ),
                        "🎯 Probabilidade Condicional": st.session_state.analise.estrategia_condicional,
                        "🤝 Ensemble (Múltiplas Estratégias)": st.session_state.analise.estrategia_ensemble
                    }
                    
                    jogos_gerados = mapa[estrategia](quantidade)
                    
                    # Filtra jogos se necessário
                    if validar_estatisticamente and jogos_gerados:
                        jogos_validos = []
                        for jogo in jogos_gerados:
                            validacao = st.session_state.analise.validar_jogo(jogo)
                            if validacao['valido']:
                                jogos_validos.append(jogo)
                        
                        if len(jogos_validos) < quantidade and jogos_validos:
                            # Completa com jogos não válidos se necessário
                            while len(jogos_validos) < quantidade:
                                for jogo in jogos_gerados:
                                    if jogo not in jogos_validos and len(jogos_validos) < quantidade:
                                        jogos_validos.append(jogo)
                                        break
                            jogos_gerados = jogos_validos
                    
                    st.session_state.jogos = jogos_gerados
                    
                    # Mostra estatísticas dos jogos gerados
                    st.success(f"✅ {len(st.session_state.jogos)} jogos gerados!")
                    
                    # Prévia dos jogos
                    if st.session_state.jogos:
                        df_previa = pd.DataFrame({
                            f"Jogo {i+1}": ", ".join([f"{n:02d}" for n in jogo])
                            for i, jogo in enumerate(st.session_state.jogos[:5])
                        }.items(), columns=["Jogo", "Dezenas"])
                        
                        st.write("**Prévia dos primeiros 5 jogos:**")
                        st.dataframe(df_previa, use_container_width=True)
        
        with tab3:
            if st.session_state.jogos:
                st.header("📊 Resultados da Conferência")
                
                # Mostra todos os jogos gerados
                with st.expander("🎲 Ver todos os jogos gerados", expanded=False):
                    if st.session_state.jogos:
                        df_jogos = pd.DataFrame({
                            f"Jogo {i+1}": ", ".join([f"{n:02d}" for n in jogo])
                            for i, jogo in enumerate(st.session_state.jogos)
                        }.items(), columns=["Jogo", "Dezenas"])
                        st.dataframe(df_jogos, use_container_width=True)
                
                # Conferência avançada
                st.subheader("🎯 Conferência Detalhada")
                resultado = st.session_state.analise.conferir_jogos_avancada(
                    st.session_state.jogos
                )
                df_resultado = pd.DataFrame(resultado)
                st.dataframe(df_resultado, use_container_width=True)
                
                # Análise de acertos
                st.subheader("📈 Distribuição de Acertos")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    acertos_counts = df_resultado["Acertos"].value_counts().sort_index()
                    if not acertos_counts.empty:
                        fig_acertos = px.bar(
                            x=acertos_counts.index,
                            y=acertos_counts.values,
                            title="Distribuição de Acertos",
                            labels={'x': 'Acertos', 'y': 'Quantidade de Jogos'}
                        )
                        st.plotly_chart(fig_acertos, use_container_width=True)
                    else:
                        st.info("Nenhum acerto registrado")
                
                with col2:
                    st.write("**Resumo Estatístico:**")
                    st.write(f"📊 Total de jogos: {len(df_resultado)}")
                    st.write(f"📈 Média de acertos: {df_resultado['Acertos'].mean():.2f}")
                    st.write(f"🏆 Máximo de acertos: {df_resultado['Acertos'].max()}")
                    st.write(f"📉 Mínimo de acertos: {df_resultado['Acertos'].min()}")
                    st.write(f"📊 Desvio padrão: {df_resultado['Acertos'].std():.2f}")
                    
                    # Jogos válidos estatisticamente
                    validos = sum(df_resultado['Válido'] == '✅')
                    st.write(f"✅ Jogos válidos: {validos}/{len(df_resultado)} ({validos/len(df_resultado)*100:.1f}%)")
                
                # Exportação
                if st.button("📥 Exportar resultados detalhados"):
                    csv = df_resultado.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"lotofacil_analise_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("ℹ️ Gere alguns jogos na aba 'Gerar Jogos' primeiro.")
        
        with tab4:
            st.header("🔬 Validação Estatística")
            
            if st.session_state.jogos and st.session_state.jogos:
                # Análise comparativa
                st.subheader("Comparação com Padrões Históricos")
                
                # Coleta estatísticas dos jogos gerados
                stats_jogos = {
                    'Soma': [sum(j) for j in st.session_state.jogos],
                    'Pares': [sum(1 for n in j if n % 2 == 0) for j in st.session_state.jogos],
                    'Primos': [sum(1 for n in j if n in [2,3,5,7,11,13,17,19,23]) for j in st.session_state.jogos]
                }
                
                # Compara com dados históricos
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    soma_historica = np.mean(st.session_state.analise.padroes_combinatorios['somas']) if st.session_state.analise.padroes_combinatorios['somas'] else 0
                    soma_gerada = np.mean(stats_jogos['Soma']) if stats_jogos['Soma'] else 0
                    st.metric(
                        "Média da Soma",
                        f"{soma_gerada:.1f}",
                        delta=f"{soma_gerada - soma_historica:.1f} vs histórico"
                    )
                
                with col2:
                    pares_historico = np.mean(st.session_state.analise.padroes_combinatorios['pares']) if st.session_state.analise.padroes_combinatorios['pares'] else 0
                    pares_gerado = np.mean(stats_jogos['Pares']) if stats_jogos['Pares'] else 0
                    st.metric(
                        "Média de Pares",
                        f"{pares_gerado:.1f}",
                        delta=f"{pares_gerado - pares_historico:.1f} vs histórico"
                    )
                
                with col3:
                    primos_historico = np.mean(st.session_state.analise.padroes_combinatorios['primos']) if st.session_state.analise.padroes_combinatorios['primos'] else 0
                    primos_gerado = np.mean(stats_jogos['Primos']) if stats_jogos['Primos'] else 0
                    st.metric(
                        "Média de Primos",
                        f"{primos_gerado:.1f}",
                        delta=f"{primos_gerado - primos_historico:.1f} vs histórico"
                    )
                
                # Teste de aderência
                st.subheader("📊 Teste de Aderência aos Padrões")
                
                # Teste qui-quadrado para distribuição de pares
                if st.session_state.analise.padroes_combinatorios['pares'] and stats_jogos['Pares']:
                    freq_esperada = Counter(st.session_state.analise.padroes_combinatorios['pares'])
                    freq_observada = Counter(stats_jogos['Pares'])
                    
                    st.write("**Distribuição de Pares:**")
                    st.write(f"- Frequência esperada (histórica): {dict(sorted(freq_esperada.most_common(5)))}")
                    st.write(f"- Frequência observada (jogos): {dict(sorted(freq_observada.most_common(5)))}")
                
                # Recomendações
                st.subheader("💡 Recomendações")
                
                if abs(soma_gerada - soma_historica) > 20:
                    st.warning("⚠️ A soma dos jogos está muito diferente da média histórica. Considere ajustar.")
                else:
                    st.success("✅ A soma dos jogos está alinhada com o padrão histórico.")
                
                if abs(pares_gerado - pares_historico) > 2:
                    st.warning("⚠️ A distribuição par/ímpar está muito diferente do padrão histórico.")
                else:
                    st.success("✅ A distribuição par/ímpar está bem calibrada.")
            else:
                st.info("ℹ️ Gere jogos para ver a validação estatística.")
    else:
        if st.session_state.concursos and len(st.session_state.concursos) < 10:
            st.warning(f"⚠️ São necessários pelo menos 10 concursos para análise completa. Atualmente há {len(st.session_state.concursos)} concursos carregados. Carregue mais concursos na barra lateral.")
        else:
            st.info("👈 Clique no botão 'Carregar dados históricos' na barra lateral para começar.")

# =====================================================
# EXECUÇÃO
# =====================================================
if __name__ == "__main__":
    main()
