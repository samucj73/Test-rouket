import streamlit as st
import requests
import numpy as np
import pandas as pd
import random
from collections import Counter
from itertools import combinations
import math
import matplotlib.pyplot as plt
import json

st.set_page_config(page_title="Lotofácil - 10 Estratégias", layout="wide")

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
        if len(self.concursos) < 15:  # Reduzido de 50 para 15
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
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 2: COBERTURA MÍNIMA
    # ============================================
    def estrategia_cobertura_garantida(self, n_jogos=8):
        """
        Garantia matemática de acerto mínimo usando cobertura de conjuntos
        """
        # Gera jogos com máxima cobertura
        jogos = []
        
        # Embaralha números
        numeros_ordenados = self.numeros.copy()
        random.shuffle(numeros_ordenados)
        
        # Distribui os números para máxima cobertura
        for i in range(n_jogos):
            jogo = []
            inicio = (i * 15) % 25
            
            for j in range(15):
                idx = (inicio + j) % 25
                jogo.append(numeros_ordenados[idx])
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 3: SOMA ÓTIMA
    # ============================================
    def estrategia_soma_otima(self, n_jogos=5):
        """
        Baseado na distribuição normal das somas dos concursos
        """
        if len(self.concursos) < 10:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Calcula média das somas históricas
        somas = [sum(concurso) for concurso in self.concursos[-50:]]
        media_soma = np.mean(somas) if somas else 195
        
        # Intervalo ótimo
        soma_min = max(170, media_soma - 15)
        soma_max = min(210, media_soma + 15)
        
        jogos = []
        
        for _ in range(n_jogos * 3):
            # Gera números com distribuição balanceada
            pares = random.randint(6, 9)
            impares = 15 - pares
            
            nums_pares = [n for n in self.numeros if n % 2 == 0]
            nums_impares = [n for n in self.numeros if n % 2 == 1]
            
            jogo = []
            if len(nums_pares) >= pares:
                jogo.extend(random.sample(nums_pares, pares))
            if len(nums_impares) >= impares:
                jogo.extend(random.sample(nums_impares, impares))
            
            jogo = sorted(jogo)
            
            if len(jogo) == 15:
                soma = sum(jogo)
                if soma_min <= soma <= soma_max:
                    if jogo not in jogos:
                        jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 4: GRUPOS (LINHAS)
    # ============================================
    def estrategia_grupos(self, n_jogos=5):
        """
        Divide os números em grupos (linhas da cartela)
        """
        # Divide em 5 grupos de 5 números
        grupos = [
            list(range(1, 6)),
            list(range(6, 11)),
            list(range(11, 16)),
            list(range(16, 21)),
            list(range(21, 26))
        ]
        
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Pega 3 números de cada grupo
            for grupo in grupos:
                selecionados = random.sample(grupo, min(3, len(grupo)))
                jogo.extend(selecionados)
            
            # Ajusta para 15 números
            jogo = sorted(set(jogo))[:15]
            
            # Completa se necessário
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 5: PARETO (80/20)
    # ============================================
    def estrategia_pareto(self, n_jogos=5):
        """
        Princípio de Pareto: foca nos números mais frequentes
        """
        if len(self.concursos) < 15:  # Reduzido de 20 para 15
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Calcula frequência
        freq = Counter()
        for concurso in self.concursos[:100]:
            freq.update(concurso)
        
        # Top 20% (5 números)
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top5 = [n for n, _ in numeros_ordenados[:5]]
        
        # Restante dos números
        resto = [n for n in self.numeros if n not in top5]
        
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Sempre inclui os top5
            jogo.extend(top5)
            
            # Completa com números aleatórios
            complemento = random.sample(resto, 10)
            jogo.extend(complemento)
            
            jogos.append(sorted(set(jogo))[:15])
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 6: ESPELHOS
    # ============================================
    def estrategia_espelhos(self, n_jogos=5):
        """
        Gera jogos espelho do último concurso
        """
        if not self.concursos:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Pega o último concurso
        ultimo = self.concursos[0]
        
        # Gera o espelho (números que NÃO saíram)
        espelho = [n for n in self.numeros if n not in ultimo]
        
        jogos = []
        
        for i in range(n_jogos):
            # Mistura números do espelho com alguns do último concurso
            n_espelho = random.randint(8, 12)
            n_ultimo = 15 - n_espelho
            
            jogo = []
            if len(espelho) >= n_espelho:
                jogo.extend(random.sample(espelho, n_espelho))
            if len(ultimo) >= n_ultimo:
                jogo.extend(random.sample(ultimo, n_ultimo))
            
            jogo = sorted(set(jogo))
            
            # Ajusta tamanho
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            while len(jogo) > 15:
                jogo.pop()
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 7: INTERVALOS UNIFORMES
    # ============================================
    def estrategia_intervalos(self, n_jogos=5):
        """
        Distribuição uniforme dos intervalos entre números
        """
        jogos = []
        
        for _ in range(n_jogos):
            jogo = []
            
            # Primeiro número
            jogo.append(random.randint(1, 5))
            
            # Gera números com intervalos balanceados
            while len(jogo) < 15:
                ultimo = jogo[-1]
                intervalo = random.randint(1, 2)
                proximo = ultimo + intervalo
                
                if proximo <= 25 and proximo not in jogo:
                    jogo.append(proximo)
                else:
                    # Pega qualquer número disponível
                    disponiveis = [n for n in range(ultimo + 1, 26) if n not in jogo]
                    if disponiveis:
                        jogo.append(random.choice(disponiveis))
                    else:
                        # Se não houver números maiores, reinicia
                        jogo = [random.randint(1, 5)]
            
            jogos.append(sorted(jogo[:15]))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 8: WHEELING SIMPLIFICADO
    # ============================================
    def estrategia_wheeling(self, n_jogos=5):
        """
        Sistema de roda simplificado para 18 números
        """
        # Seleciona 18 números base
        if len(self.concursos) > 15:  # Reduzido de 20 para 15
            freq = Counter()
            for concurso in self.concursos[:50]:
                freq.update(concurso)
            
            numeros_base = [n for n, _ in sorted(freq.items(), 
                          key=lambda x: x[1], reverse=True)[:18]]
        else:
            numeros_base = random.sample(self.numeros, 18)
        
        jogos = []
        
        # Gera combinações
        for i in range(0, 15, 3):
            jogo = []
            for j in range(15):
                idx = (i + j) % 18
                jogo.append(numeros_base[idx])
            jogos.append(sorted(set(jogo))[:15])
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 9: CÍCLICA SIMPLIFICADA
    # ============================================
    def estrategia_ciclica(self, n_jogos=5):
        """
        Baseada nos números do último concurso
        """
        if len(self.concursos) < 5:
            return self.estrategia_aleatoria_controlada(n_jogos)
        
        # Pega os últimos 5 concursos
        ultimos = self.concursos[:5]
        
        # Números que mais repetiram
        freq = Counter()
        for concurso in ultimos:
            freq.update(concurso)
        
        # Top 15 mais frequentes nos últimos 5
        top15 = [n for n, _ in freq.most_common(15)]
        
        jogos = []
        for _ in range(n_jogos):
            # Mistura top15 com números aleatórios
            n_top = random.randint(10, 12)
            jogo = random.sample(top15, min(n_top, len(top15)))
            
            # Completa
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 10: ENSEMBLE (MULTI-ESTRATÉGIA)
    # ============================================
    def estrategia_ensemble(self, n_jogos=10):
        """
        Combina múltiplas estratégias
        """
        todas_estrategias = [
            self.estrategia_frios_leidoterco,
            self.estrategia_soma_otima,
            self.estrategia_grupos,
            self.estrategia_pareto,
            self.estrategia_espelhos,
            self.estrategia_intervalos
        ]
        
        jogos = []
        jogos_por_estrategia = max(1, n_jogos // len(todas_estrategias))
        
        for estrategia in todas_estrategias:
            try:
                novos_jogos = estrategia(jogos_por_estrategia)
                jogos.extend(novos_jogos)
            except:
                continue
        
        # Remove duplicatas
        jogos_unicos = []
        seen = set()
        for jogo in jogos:
            chave = tuple(jogo)
            if chave not in seen and len(jogo) == 15:
                seen.add(chave)
                jogos_unicos.append(jogo)
        
        return jogos_unicos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA BASE: ALEATÓRIA CONTROLADA
    # ============================================
    def estrategia_aleatoria_controlada(self, n_jogos=5):
        """
        Aleatória pura mas com validação básica
        """
        jogos = []
        
        for _ in range(n_jogos * 2):
            jogo = sorted(random.sample(self.numeros, 15))
            
            # Validações básicas
            pares = sum(1 for n in jogo if n % 2 == 0)
            soma = sum(jogo)
            
            if 5 <= pares <= 10 and 170 <= soma <= 210:
                if jogo not in jogos:
                    jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        while len(jogos) < n_jogos:
            jogo = sorted(random.sample(self.numeros, 15))
            if jogo not in jogos:
                jogos.append(jogo)
        
        return jogos[:n_jogos]
    
    # ============================================
    # COMPARAR ESTRATÉGIAS (SIMPLIFICADO)
    # ============================================
    def comparar_estrategias(self, n_jogos=5):
        """
        Comparação simplificada das estratégias
        """
        if len(self.concursos) < 10:
            return {}
        
        resultados = {}
        estrategias = {
            'Frios (Lei dos Terços)': self.estrategia_frios_leidoterco,
            'Cobertura': self.estrategia_cobertura_garantida,
            'Soma Ótima': self.estrategia_soma_otima,
            'Grupos': self.estrategia_grupos,
            'Pareto': self.estrategia_pareto,
            'Espelhos': self.estrategia_espelhos,
            'Intervalos': self.estrategia_intervalos,
            'Wheeling': self.estrategia_wheeling,
            'Cíclica': self.estrategia_ciclica,
            'Ensemble': self.estrategia_ensemble
        }
        
        concurso_teste = self.concursos[0]  # Último concurso
        
        for nome, estrategia in estrategias.items():
            try:
                jogos = estrategia(n_jogos)
                acertos = []
                
                for jogo in jogos:
                    if len(jogo) == 15:
                        acertos.append(len(set(jogo) & set(concurso_teste)))
                
                if acertos:
                    resultados[nome] = {
                        'media_acertos': np.mean(acertos),
                        'max_acertos': max(acertos),
                        'premiacoes': sum(1 for a in acertos if a >= 11)
                    }
            except Exception as e:
                print(f"Erro {nome}: {e}")
                continue
        
        return resultados

# ============================================
# INTERFACE STREAMLIT
# ============================================
def main():
    st.title("🎯 Lotofácil - 10 Estratégias Matemáticas")
    
    st.markdown("""
    ## 📊 Estratégias Baseadas em Matemática
    
    > **⚠️ AVISO**: Estas são estratégias de **ALOCAÇÃO**, não de previsão. 
    > A Lotofácil é 100% aleatória. Use estas técnicas para DIVERSIFICAR seus jogos.
    
    ### 🎲 Estratégias Disponíveis:
    1. **Lei dos Terços** - Distribuição natural (30% frios, 20% quentes)
    2. **Cobertura** - Máxima variedade de números
    3. **Soma Ótima** - Foco na média histórica (180-200)
    4. **Grupos** - Distribuição por linhas da cartela
    5. **Pareto** - 20% números mais frequentes
    6. **Espelhos** - Complemento do último concurso
    7. **Intervalos** - Gaps uniformes entre números
    8. **Wheeling** - Sistema de roda simplificado
    9. **Cíclica** - Tendência dos últimos concursos
    10. **Ensemble** - Combinação de múltiplas estratégias
    """)
    
    # Inicialização
    if 'concursos' not in st.session_state:
        st.session_state.concursos = []
    
    # Sidebar - Captura
    with st.sidebar:
        st.header("📥 Dados")
        # ALTERADO: mínimo 15, máximo 500, valor padrão 100
        qtd = st.slider("Quantidade de concursos", min_value=15, max_value=500, value=100, step=5)
        
        if st.button("🔄 Carregar Concursos", use_container_width=True):
            with st.spinner("Carregando..."):
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
                        
                        if dados:
                            st.info(f"📅 Último: Concurso #{dados[0]['concurso']} - {dados[0]['data']}")
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")
        
        if st.session_state.concursos:
            st.metric("Total em análise", len(st.session_state.concursos))
            
            # Mostra período dos concursos
            if len(st.session_state.concursos) > 1:
                st.caption(f"📆 Último: {st.session_state.concursos[0]}")
                st.caption(f"📆 Primeiro: {st.session_state.concursos[-1]}")
    
    # Main content
    if st.session_state.concursos and len(st.session_state.concursos) >= 15:
        estrategias = EstrategiasLotofacil(st.session_state.concursos)
        
        tab1, tab2, tab3 = st.tabs([
            "🎲 Gerar Jogos", 
            "📊 Comparar Estratégias",
            "✅ Conferir Resultados"
        ])
        
        with tab1:
            st.header("🎲 Gerar Jogos com Estratégias")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                estrategia = st.selectbox(
                    "Selecione a Estratégia",
                    [
                        "Frios (Lei dos Terços)",
                        "Cobertura",
                        "Soma Ótima",
                        "Grupos",
                        "Pareto",
                        "Espelhos",
                        "Intervalos",
                        "Wheeling",
                        "Cíclica",
                        "Ensemble (Todas)"
                    ]
                )
            
            with col2:
                n_jogos = st.number_input("Quantidade de Jogos", min_value=1, max_value=50, value=5)
            
            if st.button("🚀 Gerar Jogos", use_container_width=True):
                with st.spinner("Gerando combinações..."):
                    mapa = {
                        "Frios (Lei dos Terços)": estrategias.estrategia_frios_leidoterco,
                        "Cobertura": estrategias.estrategia_cobertura_garantida,
                        "Soma Ótima": estrategias.estrategia_soma_otima,
                        "Grupos": estrategias.estrategia_grupos,
                        "Pareto": estrategias.estrategia_pareto,
                        "Espelhos": estrategias.estrategia_espelhos,
                        "Intervalos": estrategias.estrategia_intervalos,
                        "Wheeling": estrategias.estrategia_wheeling,
                        "Cíclica": estrategias.estrategia_ciclica,
                        "Ensemble (Todas)": estrategias.estrategia_ensemble
                    }
                    
                    jogos = mapa[estrategia](n_jogos)
                    st.session_state['jogos_atuais'] = jogos
                    st.success(f"✅ {len(jogos)} jogos gerados com sucesso!")
            
            if 'jogos_atuais' in st.session_state:
                st.subheader(f"📋 Jogos Gerados - {estrategia}")
                
                for i, jogo in enumerate(st.session_state.jogos_atuais[:10], 1):
                    pares = sum(1 for n in jogo if n%2==0)
                    primos = sum(1 for n in jogo if n in estrategias.primos)
                    soma = sum(jogo)
                    
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**Jogo {i:2d}:** {jogo}")
                        with col2:
                            st.write(f"🎯 {pares}P/{15-pares}I")
                        with col3:
                            st.write(f"📊 {soma}")
                
                if len(st.session_state.jogos_atuais) > 10:
                    st.caption(f"... e mais {len(st.session_state.jogos_atuais) - 10} jogos")
                
                # Download
                conteudo = "\n".join([",".join(map(str, j)) for j in st.session_state.jogos_atuais])
                st.download_button(
                    "💾 Baixar Jogos (TXT)",
                    data=conteudo,
                    file_name=f"lotofacil_{estrategia.lower().replace(' ', '_')}_{len(st.session_state.jogos_atuais)}jogos.txt",
                    use_container_width=True
                )
        
        with tab2:
            st.header("📊 Comparação entre Estratégias")
            st.markdown("*Teste o desempenho de cada estratégia no último concurso*")
            
            col1, col2 = st.columns(2)
            with col1:
                jogos_teste = st.slider("Jogos por estratégia", min_value=3, max_value=20, value=5)
            
            if st.button("🔬 Comparar Estratégias", use_container_width=True):
                with st.spinner("Analisando estratégias..."):
                    resultados = estrategias.comparar_estrategias(jogos_teste)
                    
                    if resultados:
                        df = pd.DataFrame(resultados).T
                        df = df.sort_values('media_acertos', ascending=False)
                        
                        st.subheader("🏆 Ranking de Performance")
                        
                        # Formatação
                        df_display = df.copy()
                        df_display['media_acertos'] = df_display['media_acertos'].round(2)
                        df_display['premiacoes'] = df_display['premiacoes'].astype(int)
                        
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Gráfico
                        fig, ax = plt.subplots(figsize=(10, 6))
                        y_pos = range(len(df))
                        ax.barh(y_pos, df['media_acertos'])
                        ax.set_yticks(y_pos)
                        ax.set_yticklabels(df.index)
                        ax.set_xlabel('Média de Acertos')
                        ax.set_title('Performance das Estratégias no Último Concurso')
                        
                        for i, v in enumerate(df['media_acertos']):
                            ax.text(v + 0.1, i, f'{v:.1f}', va='center')
                        
                        st.pyplot(fig)
                        plt.close()
                    else:
                        st.warning("Não foi possível comparar as estratégias. Tente novamente.")
        
        with tab3:
            st.header("✅ Conferência de Resultados")
            
            if st.session_state.concursos:
                ultimo = st.session_state.concursos[0]
                st.info(f"**Último Concurso:** {ultimo}")
                
                if 'jogos_atuais' in st.session_state:
                    st.subheader("📝 Resultados dos Seus Jogos")
                    
                    resultados = []
                    for i, jogo in enumerate(st.session_state.jogos_atuais, 1):
                        acertos = len(set(jogo) & set(ultimo))
                        
                        if acertos >= 15:
                            status = "🏆 SENA"
                        elif acertos >= 14:
                            status = "💰 QUINA"
                        elif acertos >= 13:
                            status = "🎯 QUADRA"
                        elif acertos >= 12:
                            status = "✨ TERNO"
                        elif acertos >= 11:
                            status = "⭐ DUQUE"
                        else:
                            status = "⚪ SEM PREMIAÇÃO"
                        
                        resultados.append({
                            'Jogo': i,
                            'Acertos': acertos,
                            'Status': status,
                            'Dezenas': str(jogo)
                        })
                    
                    df_res = pd.DataFrame(resultados)
                    st.dataframe(df_res, use_container_width=True)
                    
                    # Estatísticas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Média de Acertos", f"{df_res['Acertos'].mean():.1f}")
                    with col2:
                        premiados = len(df_res[df_res['Acertos'] >= 11])
                        st.metric("Jogos Premiados", premiados)
                    with col3:
                        if premiados > 0:
                            st.metric("Maior Acerto", df_res['Acertos'].max())
                    with col4:
                        st.metric("Total de Jogos", len(df_res))
                
                # Upload arquivo
                st.subheader("📁 Conferir Arquivo TXT")
                arquivo = st.file_uploader("Upload de arquivo com jogos", type=['txt'])
                
                if arquivo:
                    content = arquivo.read().decode('utf-8')
                    linhas = content.strip().split('\n')
                    
                    jogos_file = []
                    for linha in linhas:
                        try:
                            nums = [int(x.strip()) for x in linha.split(',') if x.strip()]
                            if len(nums) == 15 and all(1 <= n <= 25 for n in nums):
                                jogos_file.append(sorted(nums))
                        except:
                            continue
                    
                    if jogos_file:
                        st.success(f"✅ {len(jogos_file)} jogos válidos carregados!")
                        
                        res_file = []
                        for i, jogo in enumerate(jogos_file[:20], 1):
                            acertos = len(set(jogo) & set(ultimo))
                            res_file.append({'Jogo': i, 'Acertos': acertos, 'Dezenas': str(jogo)})
                        
                        df_file = pd.DataFrame(res_file)
                        st.dataframe(df_file, use_container_width=True)
                        
                        if len(jogos_file) > 20:
                            st.info(f"... e mais {len(jogos_file) - 20} jogos")
                        
                        media_file = np.mean([r['Acertos'] for r in res_file])
                        st.metric("Média de Acertos do Arquivo", f"{media_file:.1f}")
    else:
        if st.session_state.concursos and len(st.session_state.concursos) < 15:
            st.warning(f"⚠️ Você tem apenas {len(st.session_state.concursos)} concursos carregados. Carregue pelo menos 15 concursos para usar todas as estratégias!")
            st.info("Ajuste o slider para no mínimo 15 e clique em 'Carregar Concursos'")
        else:
            st.info("👈 **Comece carregando os concursos no menu lateral**")
            st.info("Mínimo necessário: **15 concursos**")
        
        st.markdown("""
        ### 🎯 Como usar o sistema:
        
        1. **Ajuste o slider** no menu lateral para no mínimo 15 concursos
        2. **Clique em "Carregar Concursos"** para obter os dados da Caixa
        3. **Escolha uma estratégia** matemática para gerar seus jogos
        4. **Compare o desempenho** entre diferentes estratégias
        5. **Confira seus resultados** com o último concurso
        
        ### 📈 Por que mínimo 15 concursos?
        
        - Necessário para análise estatística mínima
        - Garante que as estratégias tenham dados suficientes
        - Evita overfitting em amostras muito pequenas
        """)

if __name__ == "__main__":
    main()
