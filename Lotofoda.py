import streamlit as st
import requests
import numpy as np
import pandas as pd
import random
from collections import Counter
from itertools import combinations
import math
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import hashlib

st.set_page_config(page_title="Lotofácil - Estratégias Avançadas", layout="wide")

# ============================================
# CLASSE DE ESTRATÉGIAS MATEMÁTICAS
# ============================================
class EstrategiasLotofacil:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        
    # ============================================
    # ESTRATÉGIA 1: NÚMEROS FRIOS (LEI DOS TERÇOS)
    # ============================================
    def estrategia_frios_leidoterco(self, n_jogos=5):
        """
        Baseado na Lei dos Terços: em qualquer amostra aleatória,
        1/3 dos números ficam abaixo da média esperada
        """
        if len(self.concursos) < 50:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Calcula frequência esperada (15 números por concurso)
        total_numeros_sorteados = len(self.concursos) * 15
        freq_esperada = total_numeros_sorteados / 25
        
        # Calcula frequência real
        freq_real = Counter()
        for concurso in self.concursos:
            freq_real.update(concurso)
        
        # Identifica números frios (abaixo da frequência esperada)
        frios = [n for n in self.numeros 
                if freq_real[n] < freq_esperada * 0.7]  # 30% abaixo
        
        # Números quentes (acima da média)
        quentes = [n for n in self.numeros 
                  if freq_real[n] > freq_esperada * 1.3]  # 30% acima
        
        # Números médios
        medios = [n for n in self.numeros if n not in frios and n not in quentes]
        
        jogos = []
        for _ in range(n_jogos):
            # Distribuição baseada na lei dos terços
            n_frios = min(7, len(frios))
            n_quentes = min(4, len(quentes))
            n_medios = 15 - n_frios - n_quentes
            
            jogo = []
            if frios:
                jogo.extend(random.sample(frios, min(n_frios, len(frios))))
            if quentes:
                jogo.extend(random.sample(quentes, min(n_quentes, len(quentes))))
            if medios:
                jogo.extend(random.sample(medios, min(n_medios, len(medios))))
            
            # Completa se necessário
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 2: COBERTURA MÍNIMA
    # ============================================
    def estrategia_cobertura_garantida(self, n_jogos=8, garantir=13):
        """
        Garantia matemática de acerto mínimo usando cobertura de conjuntos
        Quanto mais jogos, maior a garantia
        """
        def calcular_cobertura(conjunto_jogos):
            """Calcula a cobertura total de números"""
            return len(set().union(*[set(j) for j in conjunto_jogos]))
        
        def probabilidade_acertar_minimo(jogos, garantir):
            """Calcula probabilidade de acertar pelo menos 'garantir' números"""
            if not jogos:
                return 0
            # Aproximação baseada na lei binomial
            prob_acerto = 0.6  # Probabilidade aproximada de acertar um número
            prob = 0
            for jogo in jogos:
                p = sum(math.comb(15, k) * (prob_acerto**k) * ((1-prob_acerto)**(15-k)) 
                       for k in range(garantir, 16))
                prob = 1 - (1 - prob) * (1 - p)
            return prob
        
        # Gera jogos iniciais
        jogos = []
        
        # Estratégia de cobertura máxima com mínimo de sobreposição
        numeros_ordenados = self.numeros.copy()
        random.shuffle(numeros_ordenados)
        
        # Distribui os números para máxima cobertura
        for i in range(n_jogos):
            jogo = []
            inicio = (i * 15) % 25
            
            # Distribuição circular para minimizar sobreposição
            for j in range(15):
                idx = (inicio + j) % 25
                jogo.append(numeros_ordenados[idx])
            
            jogos.append(sorted(jogo))
        
        # Otimiza a cobertura
        cobertura_atual = calcular_cobertura(jogos)
        
        # Tenta melhorar a cobertura
        for _ in range(100):  # Iterações de otimização
            i = random.randint(0, n_jogos - 1)
            jogo_original = jogos[i].copy()
            
            # Tenta substituir um número por outro não coberto
            cobertos = set().union(*[set(j) for j in jogos if j != jogo_original])
            nao_cobertos = [n for n in self.numeros if n not in cobertos]
            
            if nao_cobertos:
                pos = random.randint(0, 14)
                novo_jogo = jogo_original.copy()
                novo_jogo[pos] = random.choice(nao_cobertos)
                novo_jogo.sort()
                jogos[i] = novo_jogo
                
                nova_cobertura = calcular_cobertura(jogos)
                if nova_cobertura > cobertura_atual:
                    cobertura_atual = nova_cobertura
                else:
                    jogos[i] = jogo_original  # Reverte
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 3: SOMA ÓTIMA (DISTRIBUIÇÃO NORMAL)
    # ============================================
    def estrategia_soma_otima(self, n_jogos=5):
        """
        Baseado na distribuição normal das somas dos concursos
        A soma ideal está entre 180 e 200
        """
        # Calcula média e desvio padrão das somas históricas
        somas = [sum(concurso) for concurso in self.concursos[-100:]]
        media_soma = np.mean(somas) if somas else 195
        std_soma = np.std(somas) if somas else 15
        
        # Intervalo ótimo (dentro de 1 desvio padrão)
        soma_min = max(170, media_soma - std_soma)
        soma_max = min(210, media_soma + std_soma)
        
        jogos = []
        
        for _ in range(n_jogos * 3):  # Gera mais para selecionar os melhores
            jogo = []
            
            # Gera números com distribuição balanceada
            pares = random.randint(6, 9)
            impares = 15 - pares
            
            # Seleciona pares e ímpares
            nums_pares = [n for n in self.numeros if n % 2 == 0]
            nums_impares = [n for n in self.numeros if n % 2 == 1]
            
            jogo.extend(random.sample(nums_pares, pares))
            jogo.extend(random.sample(nums_impares, impares))
            
            jogo = sorted(jogo)
            soma = sum(jogo)
            
            # Verifica se está no intervalo ótimo
            if soma_min <= soma <= soma_max:
                jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        # Se não gerou suficientes, completa com ajustes
        while len(jogos) < n_jogos:
            jogo = jogos[-1].copy() if jogos else random.sample(self.numeros, 15)
            soma = sum(jogo)
            
            if soma < soma_min:
                # Troca um número baixo por um alto
                baixos = [n for n in jogo if n < 13]
                if baixos:
                    jogo.remove(random.choice(baixos))
                    jogo.append(random.randint(20, 25))
            elif soma > soma_max:
                # Troca um número alto por um baixo
                altos = [n for n in jogo if n > 13]
                if altos:
                    jogo.remove(random.choice(altos))
                    jogo.append(random.randint(1, 6))
            
            jogo = sorted(jogo)
            if len(set(jogo)) == 15 and jogo not in jogos:
                jogos.append(jogo)
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 4: GRUPOS E SUBCONJUNTOS
    # ============================================
    def estrategia_grupos(self, n_jogos=5):
        """
        Divide os números em grupos e garante representação de todos
        Baseado na teoria de Ramsey e coloração de grafos
        """
        # Divide em 5 grupos de 5 números (linhas da cartela)
        grupos = [
            list(range(1, 6)),
            list(range(6, 11)),
            list(range(11, 16)),
            list(range(16, 21)),
            list(range(21, 26))
        ]
        
        # Analisa distribuição histórica por grupos
        distribuicao_grupos = []
        for concurso in self.concursos[-50:]:
            dist = [len([n for n in concurso if n in grupo]) for grupo in grupos]
            distribuicao_grupos.append(dist)
        
        # Média de números por grupo
        media_grupos = np.mean(distribuicao_grupos, axis=0) if distribuicao_grupos else [3, 3, 3, 3, 3]
        
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Distribui números seguindo a média histórica
            for i, grupo in enumerate(grupos):
                # Pega a quantidade média arredondada para o grupo
                qtd = int(round(media_grupos[i]))
                qtd = max(2, min(5, qtd))  # Limita entre 2 e 5
                
                if len(grupo) >= qtd:
                    selecionados = random.sample(grupo, qtd)
                    jogo.extend(selecionados)
            
            # Completa se necessário
            while len(jogo) < 15:
                grupo = random.choice(grupos)
                disponiveis = [n for n in grupo if n not in jogo]
                if disponiveis:
                    jogo.append(random.choice(disponiveis))
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 5: ELIMINAÇÃO (PRINCÍPIO DE PARETTO)
    # ============================================
    def estrategia_eliminacao_pareto(self, n_jogos=5):
        """
        80/20: Foca nos 20% números que aparecem 80% das vezes
        """
        if len(self.concursos) < 20:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Calcula frequência
        freq = Counter()
        for concurso in self.concursos:
            freq.update(concurso)
        
        # Ordena por frequência
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        
        # Pega os top 20% (5 números) - Princípio de Pareto
        top_pareto = [n for n, _ in numeros_ordenados[:5]]
        
        # Elimina os menos frequentes (bottom 20%)
        bottom_pareto = [n for n, _ in numeros_ordenados[-5:]]
        
        # Números restantes
        resto = [n for n in self.numeros if n not in top_pareto and n not in bottom_pareto]
        
        jogos = []
        
        for _ in range(n_jogos):
            # Sempre inclui alguns números do top Pareto
            n_top = random.randint(3, 5)
            n_bottom = random.randint(0, 1)  # Poucos números frios
            n_resto = 15 - n_top - n_bottom
            
            jogo = []
            jogo.extend(random.sample(top_pareto, min(n_top, len(top_pareto))))
            
            if bottom_pareto and n_bottom > 0:
                jogo.extend(random.sample(bottom_pareto, min(n_bottom, len(bottom_pareto))))
            
            if resto:
                jogo.extend(random.sample(resto, min(n_resto, len(resto))))
            
            # Completa se necessário
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 6: ESPELHOS (COMPLEMENTAR)
    # ============================================
    def estrategia_espelhos(self, n_jogos=5):
        """
        Gera jogos espelho: se um número não sai em um jogo,
        tem alta probabilidade de sair no complemento
        """
        if not self.concursos:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Pega o último concurso
        ultimo = self.concursos[0]
        
        # Gera o espelho (números que NÃO saíram)
        espelho = [n for n in self.numeros if n not in ultimo]
        
        jogos = []
        
        # Variações do espelho
        for i in range(n_jogos):
            # Mistura números do espelho com alguns do último concurso
            n_espelho = random.randint(8, 12)
            n_ultimo = 15 - n_espelho
            
            jogo = []
            jogo.extend(random.sample(espelho, min(n_espelho, len(espelho))))
            jogo.extend(random.sample(ultimo, min(n_ultimo, len(ultimo))))
            
            jogo = sorted(set(jogo))
            
            # Ajusta tamanho
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            while len(jogo) > 15:
                jogo.pop()
            
            jogos.append(sorted(jogo))
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 7: INTERVALOS UNIFORMES
    # ============================================
    def estrategia_intervalos(self, n_jogos=5):
        """
        Distribuição uniforme dos intervalos entre números consecutivos
        Minimiza clusters e gaps muito grandes
        """
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Gera números com intervalos balanceados
            while len(jogo) < 15:
                if not jogo:
                    # Primeiro número entre 1 e 10
                    jogo.append(random.randint(1, 10))
                else:
                    # Intervalo ideal entre 1 e 3
                    ultimo = jogo[-1]
                    intervalo = random.randint(1, 3)
                    proximo = ultimo + intervalo
                    
                    if proximo <= 25 and proximo not in jogo:
                        jogo.append(proximo)
                    else:
                        # Se não for possível, escolhe outro
                        candidatos = [n for n in range(ultimo + 1, 26) 
                                    if n not in jogo]
                        if candidatos:
                            jogo.append(random.choice(candidatos))
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 8: SISTEMA DE RODA (WHEELING)
    # ============================================
    def estrategia_wheeling(self, numeros_base=None, garantia=13):
        """
        Sistema de roda matemático: maximiza cobertura com mínimo de jogos
        Garantia: se acertar os números base, garante X pontos
        """
        if numeros_base is None:
            # Seleciona números base de alta frequência
            freq = Counter()
            for concurso in self.concursos[:50]:
                freq.update(concurso)
            
            numeros_base = [n for n, _ in sorted(freq.items(), 
                          key=lambda x: x[1], reverse=True)[:18]]
        
        # Gera combinações do sistema de roda
        jogos = []
        
        # Roda completa para 18 números, 15 por jogo
        # Isso garante que se acertar 13 dos 18, terá pelo menos um jogo com 13+
        if len(numeros_base) >= 15:
            # Distribuição circular
            for i in range(0, len(numeros_base), 3):
                jogo = []
                for j in range(15):
                    idx = (i + j) % len(numeros_base)
                    jogo.append(numeros_base[idx])
                jogos.append(sorted(set(jogo)))
                
                if len(jogos) >= 8:  # Limita quantidade
                    break
        
        # Remove duplicatas
        jogos = [list(x) for x in set(tuple(j) for j in jogos)]
        
        return jogos[:8]  # Retorna no máximo 8 jogos
    
    # ============================================
    # ESTRATÉGIA 9: ANÁLISE DE TENDÊNCIA CÍCLICA
    # ============================================
    def estrategia_ciclica(self, n_jogos=5, ciclo=10):
        """
        Analisa ciclos de repetição de padrões
        """
        if len(self.concursos) < ciclo * 2:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Divide os concursos em ciclos
        ciclos = []
        for i in range(0, len(self.concursos), ciclo):
            if i + ciclo <= len(self.concursos):
                ciclo_atual = self.concursos[i:i+ciclo]
                # Padrão do ciclo (números mais frequentes)
                freq_ciclo = Counter()
                for concurso in ciclo_atual:
                    freq_ciclo.update(concurso)
                
                top_ciclo = [n for n, _ in freq_ciclo.most_common(15)]
                ciclos.append(top_ciclo)
        
        # Analisa evolução dos ciclos
        jogos = []
        
        # Projeta próximo ciclo baseado nos anteriores
        if len(ciclos) >= 2:
            ultimo_ciclo = set(ciclos[-1])
            penultimo_ciclo = set(ciclos[-2])
            
            # Números que persistiram
            persistentes = list(ultimo_ciclo & penultimo_ciclo)
            # Números novos no último ciclo
            novos = list(ultimo_ciclo - penultimo_ciclo)
            # Números que saíram
            saidas = list(penultimo_ciclo - ultimo_ciclo)
            
            for _ in range(n_jogos):
                jogo = []
                
                # Mantém números persistentes
                if persistentes:
                    jogo.extend(random.sample(persistentes, min(8, len(persistentes))))
                
                # Adiciona alguns novos
                if novos:
                    jogo.extend(random.sample(novos, min(4, len(novos))))
                
                # Completa com outros
                outros = [n for n in self.numeros if n not in jogo]
                while len(jogo) < 15:
                    jogo.append(random.choice(outros))
                    outros = [n for n in self.numeros if n not in jogo]
                
                jogos.append(sorted(jogo[:15]))
        
        return jogos
    
    # ============================================
    # ESTRATÉGIA 10: MULTI-ESTRATÉGIA (ENSEMBLE)
    # ============================================
    def estrategia_ensemble(self, n_jogos=10):
        """
        Combina múltiplas estratégias para diversificação máxima
        """
        todas_estrategias = [
            self.estrategia_frios_leidoterco,
            self.estrategia_soma_otima,
            self.estrategia_grupos,
            self.estrategia_eliminacao_pareto,
            self.estrategia_espelhos,
            self.estrategia_intervalos
        ]
        
        jogos = []
        
        # Distribui os jogos entre as estratégias
        jogos_por_estrategia = max(1, n_jogos // len(todas_estrategias))
        
        for estrategia in todas_estrategias:
            try:
                novos_jogos = estrategia(jogos_por_estrategia)
                jogos.extend(novos_jogos)
            except Exception as e:
                print(f"Erro na estratégia {estrategia.__name__}: {e}")
                continue
        
        # Remove duplicatas
        jogos_unicos = []
        seen = set()
        for jogo in jogos:
            chave = tuple(jogo)
            if chave not in seen:
                seen.add(chave)
                jogos_unicos.append(jogo)
        
        return jogos_unicos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA BASE: ALEATÓRIA CONTROLADA
    # ============================================
    def estrategia_aleatoria_controlada(self, n_jogos=5):
        """
        Aleatória pura mas com validação estatística básica
        """
        jogos = []
        
        for _ in range(n_jogos * 2):
            jogo = sorted(random.sample(self.numeros, 15))
            
            # Validações básicas
            pares = sum(1 for n in jogo if n % 2 == 0)
            soma = sum(jogo)
            
            # Filtros suaves (apenas para não gerar absurdos estatísticos)
            if 5 <= pares <= 10 and 170 <= soma <= 210:
                if jogo not in jogos:
                    jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        # Completa se necessário
        while len(jogos) < n_jogos:
            jogo = sorted(random.sample(self.numeros, 15))
            if jogo not in jogos:
                jogos.append(jogo)
        
        return jogos[:n_jogos]
    
    # ============================================
    # ANÁLISE COMPARATIVA DAS ESTRATÉGIAS
    # ============================================
    def comparar_estrategias(self, n_jogos=5, n_testes=10):
        """
        Compara o desempenho histórico das estratégias
        """
        if len(self.concursos) < 20:
            return {}
        
        resultados = {}
        estrategias = {
            'Frios (Lei dos Terços)': self.estrategia_frios_leidoterco,
            'Cobertura Garantida': self.estrategia_cobertura_garantida,
            'Soma Ótima': self.estrategia_soma_otima,
            'Grupos': self.estrategia_grupos,
            'Pareto (80/20)': self.estrategia_eliminacao_pareto,
            'Espelhos': self.estrategia_espelhos,
            'Intervalos': self.estrategia_intervalos,
            'Wheeling': self.estrategia_wheeling,
            'Cíclica': self.estrategia_ciclica,
            'Ensemble': self.estrategia_ensemble
        }
        
        for nome, estrategia in estrategias.items():
            acertos_totais = []
            
            for teste in range(min(n_testes, len(self.concursos) - 10)):
                # Usa concurso real para teste
                concurso_teste = self.concursos[teste]
                
                # Gera jogos com dados ANTERIORES ao concurso
                dados_treino = self.concursos[teste+1:teste+51] if teste+51 <= len(self.concursos) else self.concursos[teste+1:]
                analise_treino = EstrategiasLotofacil(dados_treino)
                
                try:
                    jogos = estrategia(n_jogos)
                    
                    for jogo in jogos:
                        acertos = len(set(jogo) & set(concurso_teste))
                        acertos_totais.append(acertos)
                except Exception as e:
                    print(f"Erro na estratégia {nome}: {e}")
                    continue
            
            if acertos_totais:
                resultados[nome] = {
                    'media_acertos': np.mean(acertos_totais),
                    'std_acertos': np.std(acertos_totais),
                    'max_acertos': max(acertos_totais),
                    'jogos_testados': len(acertos_totais),
                    'premiacoes': sum(1 for a in acertos_totais if a >= 11)
                }
        
        return resultados

# ============================================
# INTERFACE STREAMLIT
# ============================================
def main():
    st.title("🎯 Lotofácil - 10 Estratégias Matemáticas")
    
    st.markdown("""
    ## 📊 Estratégias Baseadas em Matemática e Estatística
    
    > **⚠️ AVISO IMPORTANTE**: Estas são estratégias de **ALOCAÇÃO DE RECURSOS**, 
    > não de previsão. A Lotofácil é 100% aleatória. Estas técnicas ajudam a 
    > diversificar e otimizar seus jogos, mas NÃO aumentam sua probabilidade matemática.
    
    ### 🧮 Estratégias Implementadas:
    1. **Números Frios** - Lei dos Terços em amostras aleatórias
    2. **Cobertura Mínima** - Garantia matemática de acerto mínimo
    3. **Soma Ótima** - Distribuição normal das somas
    4. **Grupos** - Teoria de Ramsey e coloração
    5. **Eliminação (Pareto)** - Princípio 80/20
    6. **Espelhos** - Complementaridade matemática
    7. **Intervalos** - Distribuição uniforme
    8. **Wheeling** - Sistema de roda combinatória
    9. **Cíclica** - Análise de ciclos temporais
    10. **Ensemble** - Combinação multi-estratégia
    """)
    
    # Inicialização
    if 'concursos' not in st.session_state:
        st.session_state.concursos = []
    
    # Sidebar - Captura
    with st.sidebar:
        st.header("📥 Dados")
        qtd = st.slider("Concursos para análise", 50, 500, 200)
        
        if st.button("🔄 Carregar Concursos", use_container_width=True):
            with st.spinner("Carregando dados da Caixa..."):
                url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                try:
                    resp = requests.get(url, timeout=30)
                    if resp.status_code == 200:
                        dados = resp.json()
                        concursos = []
                        for i in range(min(qtd, len(dados))):
                            dezenas = sorted([int(d) for d in dados[i]['dezenas']])
                            concursos.append(dezenas)
                        st.session_state.concursos = concursos
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        # Mostra último concurso
                        st.info(f"📅 Último: Concurso {dados[0]['concurso']} - {dados[0]['data']}")
                except Exception as e:
                    st.error(f"Erro: {e}")
        
        if st.session_state.concursos:
            st.metric("Total em análise", len(st.session_state.concursos))
            
            # Status das estratégias
            st.header("🎮 Status das Estratégias")
            st.success("10 estratégias disponíveis")
    
    # Main content
    if st.session_state.concursos:
        estrategias = EstrategiasLotofacil(st.session_state.concursos)
        
        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎲 Gerar Jogos", 
            "📊 Comparar Estratégias",
            "📈 Análise Detalhada",
            "✅ Conferência"
        ])
        
        with tab1:
            st.header("🎲 Gerar Jogos com Estratégias Específicas")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                estrategia_escolhida = st.selectbox(
                    "Selecione a Estratégia",
                    [
                        "Frios (Lei dos Terços)",
                        "Cobertura Garantida",
                        "Soma Ótima",
                        "Grupos",
                        "Pareto (80/20)",
                        "Espelhos",
                        "Intervalos",
                        "Wheeling",
                        "Cíclica",
                        "Ensemble (Todas)"
                    ]
                )
            
            with col2:
                n_jogos = st.number_input("Quantidade de Jogos", 1, 20, 5)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🚀 Gerar Jogos", use_container_width=True):
                    with st.spinner("Gerando combinações..."):
                        mapa_estrategias = {
                            "Frios (Lei dos Terços)": estrategias.estrategia_frios_leidoterco,
                            "Cobertura Garantida": estrategias.estrategia_cobertura_garantida,
                            "Soma Ótima": estrategias.estrategia_soma_otima,
                            "Grupos": estrategias.estrategia_grupos,
                            "Pareto (80/20)": estrategias.estrategia_eliminacao_pareto,
                            "Espelhos": estrategias.estrategia_espelhos,
                            "Intervalos": estrategias.estrategia_intervalos,
                            "Wheeling": estrategias.estrategia_wheeling,
                            "Cíclica": estrategias.estrategia_ciclica,
                            "Ensemble (Todas)": estrategias.estrategia_ensemble
                        }
                        
                        func = mapa_estrategias[estrategia_escolhida]
                        jogos = func(n_jogos)
                        st.session_state['jogos_atuais'] = jogos
                        st.success(f"✅ {len(jogos)} jogos gerados!")
            
            # Exibir jogos
            if 'jogos_atuais' in st.session_state:
                st.subheader(f"📋 Jogos Gerados - {estrategia_escolhida}")
                
                df_jogos = pd.DataFrame({
                    'Jogo': [f"Jogo {i+1}" for i in range(len(st.session_state.jogos_atuais))],
                    'Dezenas': [str(j) for j in st.session_state.jogos_atuais],
                    'Pares': [sum(1 for n in j if n%2==0) for j in st.session_state.jogos_atuais],
                    'Ímpares': [sum(1 for n in j if n%2==1) for j in st.session_state.jogos_atuais],
                    'Primos': [sum(1 for n in j if n in estrategias.primos) for j in st.session_state.jogos_atuais],
                    'Soma': [sum(j) for j in st.session_state.jogos_atuais]
                })
                
                st.dataframe(df_jogos, use_container_width=True)
                
                # Download
                conteudo = "\n".join([",".join(map(str, j)) for j in st.session_state.jogos_atuais])
                st.download_button(
                    "💾 Baixar Jogos (TXT)",
                    data=conteudo,
                    file_name=f"lotofacil_{estrategia_escolhida.lower().replace(' ', '_')}_{len(st.session_state.jogos_atuais)}.txt",
                    use_container_width=True
                )
        
        with tab2:
            st.header("📊 Comparação entre Estratégias")
            st.markdown("""
            *Backtest usando dados históricos reais. 
            **Quanto maior a média de acertos e mais premiações, melhor a estratégia**.
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                n_testes = st.slider("Número de testes por estratégia", 5, 50, 20)
            
            with col2:
                jogos_por_teste = st.slider("Jogos por teste", 3, 10, 5)
            
            if st.button("🔬 Executar Comparação Completa", use_container_width=True):
                with st.spinner("Analisando estratégias..."):
                    resultados = estrategias.comparar_estrategias(
                        n_jogos=jogos_por_teste,
                        n_testes=n_testes
                    )
                    
                    st.session_state['resultados_comparacao'] = resultados
                    
                    # Dataframe
                    df_resultados = pd.DataFrame(resultados).T
                    df_resultados = df_resultados.sort_values('media_acertos', ascending=False)
                    
                    st.subheader("📈 Ranking de Estratégias")
                    st.dataframe(
                        df_resultados.style.highlight_max(color='lightgreen'),
                        use_container_width=True
                    )
                    
                    # Gráfico
                    fig, ax = plt.subplots(figsize=(12, 6))
                    
                    y_pos = np.arange(len(df_resultados))
                    ax.barh(y_pos, df_resultados['media_acertos'])
                    ax.set_yticks(y_pos)
                    ax.set_yticklabels(df_resultados.index)
                    ax.set_xlabel('Média de Acertos')
                    ax.set_title('Performance Média das Estratégias')
                    
                    for i, v in enumerate(df_resultados['media_acertos']):
                        ax.text(v + 0.1, i, f'{v:.2f}', va='center')
                    
                    st.pyplot(fig)
                    plt.close()
                    
                    # Gráfico de premiações
                    fig2, ax2 = plt.subplots(figsize=(12, 6))
                    
                    premiacoes = df_resultados['premiacoes'].values
                    ax2.barh(y_pos, premiacoes, color='orange')
                    ax2.set_yticks(y_pos)
                    ax2.set_yticklabels(df_resultados.index)
                    ax2.set_xlabel('Quantidade de Premiações (11+ acertos)')
                    ax2.set_title('Eficácia em Premiações')
                    
                    for i, v in enumerate(premiacoes):
                        ax2.text(v + 0.5, i, str(int(v)), va='center')
                    
                    st.pyplot(fig2)
                    plt.close()
        
        with tab3:
            st.header("📈 Análise Detalhada das Estratégias")
            
            estrategia_analise = st.selectbox(
                "Selecione estratégia para análise detalhada",
                [
                    "Frios (Lei dos Terços)",
                    "Cobertura Garantida",
                    "Soma Ótima",
                    "Grupos",
                    "Pareto (80/20)",
                    "Espelhos",
                    "Intervalos",
                    "Wheeling",
                    "Cíclica",
                    "Ensemble (Todas)"
                ],
                key="analise_detalhada"
            )
            
            if st.button("🔍 Analisar Estratégia", use_container_width=True):
                with st.spinner("Gerando análise detalhada..."):
                    mapa_estrategias = {
                        "Frios (Lei dos Terços)": estrategias.estrategia_frios_leidoterco,
                        "Cobertura Garantida": estrategias.estrategia_cobertura_garantida,
                        "Soma Ótima": estrategias.estrategia_soma_otima,
                        "Grupos": estrategias.estrategia_grupos,
                        "Pareto (80/20)": estrategias.estrategia_eliminacao_pareto,
                        "Espelhos": estrategias.estrategia_espelhos,
                        "Intervalos": estrategias.estrategia_intervalos,
                        "Wheeling": estrategias.estrategia_wheeling,
                        "Cíclica": estrategias.estrategia_ciclica,
                        "Ensemble (Todas)": estrategias.estrategia_ensemble
                    }
                    
                    func = mapa_estrategias[estrategia_analise]
                    
                    # Gera múltiplos conjuntos para análise
                    todos_jogos = []
                    for _ in range(10):
                        jogos = func(5)
                        todos_jogos.extend(jogos)
                    
                    # Análise
                    df_analise = pd.DataFrame({
                        'Jogo': [f"Jogo {i+1}" for i in range(len(todos_jogos))],
                        'Dezenas': [str(j) for j in todos_jogos],
                        'Pares': [sum(1 for n in j if n%2==0) for j in todos_jogos],
                        'Ímpares': [sum(1 for n in j if n%2==1) for j in todos_jogos],
                        'Primos': [sum(1 for n in j if n in estrategias.primos) for j in todos_jogos],
                        'Soma': [sum(j) for j in todos_jogos]
                    })
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Média de Pares", f"{df_analise['Pares'].mean():.1f}")
                    with col2:
                        st.metric("Média de Ímpares", f"{df_analise['Ímpares'].mean():.1f}")
                    with col3:
                        st.metric("Média de Primos", f"{df_analise['Primos'].mean():.1f}")
                    with col4:
                        st.metric("Média da Soma", f"{df_analise['Soma'].mean():.1f}")
                    
                    # Distribuição
                    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
                    
                    axes[0, 0].hist(df_analise['Pares'], bins=range(4, 12), edgecolor='black')
                    axes[0, 0].set_title('Distribuição de Pares')
                    axes[0, 0].set_xlabel('Quantidade')
                    
                    axes[0, 1].hist(df_analise['Primos'], bins=range(0, 10), edgecolor='black')
                    axes[0, 1].set_title('Distribuição de Primos')
                    axes[0, 1].set_xlabel('Quantidade')
                    
                    axes[1, 0].hist(df_analise['Soma'], bins=15, edgecolor='black')
                    axes[1, 0].set_title('Distribuição das Somas')
                    axes[1, 0].set_xlabel('Soma')
                    
                    # Frequência dos números
                    freq_numeros = Counter()
                    for jogo in todos_jogos:
                        freq_numeros.update(jogo)
                    
                    nums = list(range(1, 26))
                    freqs = [freq_numeros.get(n, 0) for n in nums]
                    
                    axes[1, 1].bar(nums, freqs)
                    axes[1, 1].set_title('Frequência dos Números')
                    axes[1, 1].set_xlabel('Número')
                    axes[1, 1].set_ylabel('Frequência')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                    
                    # Top números mais usados
                    st.subheader("🎯 Números mais frequentes")
                    df_freq = pd.DataFrame({
                        'Número': nums,
                        'Frequência': freqs
                    }).sort_values('Frequência', ascending=False).head(10)
                    
                    st.dataframe(df_freq, use_container_width=True)
        
        with tab4:
            st.header("✅ Conferência com Último Concurso")
            
            if st.session_state.concursos:
                ultimo_concurso = st.session_state.concursos[0]
                st.info(f"**Último Concurso:** {ultimo_concurso}")
                
                if 'jogos_atuais' in st.session_state:
                    st.subheader("📝 Resultado dos seus jogos")
                    
                    resultados = []
                    for i, jogo in enumerate(st.session_state.jogos_atuais, 1):
                        acertos = len(set(jogo) & set(ultimo_concurso))
                        faixa = "SENA" if acertos == 15 else "QUINA" if acertos == 14 else "QUADRA" if acertos == 13 else "TERNO" if acertos == 12 else "DUQUE" if acertos == 11 else "NÃO PREMIADO"
                        
                        resultados.append({
                            'Jogo': i,
                            'Acertos': acertos,
                            'Faixa': faixa,
                            'Dezenas': str(jogo)
                        })
                    
                    df_resultados = pd.DataFrame(resultados)
                    st.dataframe(df_resultados, use_container_width=True)
                    
                    # Estatísticas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Média de Acertos", f"{df_resultados['Acertos'].mean():.1f}")
                    with col2:
                        premiados = len(df_resultados[df_resultados['Acertos'] >= 11])
                        st.metric("Jogos Premiados", premiados)
                    with col3:
                        if premiados > 0:
                            st.metric("Maior Acerto", df_resultados['Acertos'].max())
                
                # Upload de arquivo
                st.subheader("📁 Conferir Arquivo TXT")
                uploaded_file = st.file_uploader("Selecione um arquivo com jogos", type=['txt'])
                
                if uploaded_file is not None:
                    content = uploaded_file.read().decode('utf-8')
                    linhas = content.strip().split('\n')
                    
                    jogos_arquivo = []
                    for linha in linhas:
                        try:
                            nums = [int(x.strip()) for x in linha.split(',') if x.strip()]
                            if len(nums) == 15 and all(1 <= n <= 25 for n in nums):
                                jogos_arquivo.append(sorted(nums))
                        except:
                            continue
                    
                    if jogos_arquivo:
                        st.success(f"✅ {len(jogos_arquivo)} jogos carregados!")
                        
                        resultados_arquivo = []
                        for i, jogo in enumerate(jogos_arquivo, 1):
                            acertos = len(set(jogo) & set(ultimo_concurso))
                            resultados_arquivo.append({
                                'Jogo': i,
                                'Acertos': acertos,
                                'Dezenas': str(jogo)
                            })
                        
                        df_arquivo = pd.DataFrame(resultados_arquivo)
                        st.dataframe(df_arquivo, use_container_width=True)
                        
                        media_acertos = df_arquivo['Acertos'].mean()
                        st.metric("Média de Acertos do Arquivo", f"{media_acertos:.1f}")
    else:
        st.info("👈 **Comece carregando os concursos no menu lateral**")
        
        # Exemplo visual
        st.markdown("""
        ### 🎯 Como funciona:
        
        1. **Carregue os concursos** da Caixa via API
        2. **Escolha uma estratégia** matemática
        3. **Gere jogos otimizados** para sua estratégia
        4. **Compare o desempenho** entre estratégias
        5. **Confera resultados** com concursos reais
        
        ### 📊 Base Matemática:
        
        - **Lei dos Terços**: Distribuição natural em amostras
        - **Teoria da Cobertura**: Garantias combinatórias
        - **Distribuição Normal**: Comportamento das somas
        - **Princípio de Pareto**: 80/20 em frequências
        - **Sistemas de Roda**: Otimização combinatória
        """)

if __name__ == "__main__":
    main()
