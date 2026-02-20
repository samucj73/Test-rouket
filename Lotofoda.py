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
    page_title="🎯 LOTOFÁCIL - DNA DO JOGO 5 V4",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CLASSE PRINCIPAL - BASEADA NO JOGO 5 (REFERÊNCIA)
# =====================================================
class AnaliseLotofacilDNA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        
        # DNA do JOGO 5 (referência)
        self.jogo_referencia = [3, 4, 5, 6, 7, 8, 9, 11, 19, 20, 21, 23, 24]
        # Complemento para 15 números (média)
        
        # Análises
        self.frequencias = self._calcular_frequencias()
        self.numeros_quentes = self._identificar_quentes()
        self.numeros_frios = self._identificar_frios()
        
    def _calcular_frequencias(self):
        """Frequência simples nos últimos 100 concursos"""
        ultimos_100 = self.concursos[:100]
        frequencias = {}
        
        for num in self.numeros:
            freq = sum(1 for c in ultimos_100 if num in c) / max(1, len(ultimos_100))
            frequencias[num] = freq * 100
            
        return frequencias
    
    def _identificar_quentes(self):
        """Top 8 números mais frequentes"""
        return [n for n, _ in sorted(self.frequencias.items(), key=lambda x: x[1], reverse=True)[:8]]
    
    def _identificar_frios(self):
        """Bottom 8 números menos frequentes"""
        return [n for n, _ in sorted(self.frequencias.items(), key=lambda x: x[1])[:8]]
    
    def _calcular_max_sequencia(self, jogo):
        """Calcula maior sequência consecutiva"""
        if not jogo:
            return 0
            
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
    # FILTROS AGRESSIVOS (baseados no Jogo 5)
    # =================================================
    def aplicar_filtros_dna(self, jogo):
        """
        Aplica as 3 regras obrigatórias baseadas no Jogo 5
        """
        if len(jogo) != 15:
            return False, "Tamanho inválido"
        
        # REGRA 1: DNA do Jogo 5
        soma = sum(jogo)
        max_seq = self._calcular_max_sequencia(jogo)
        num_frios = len([n for n in jogo if n in self.numeros_frios])
        
        if soma < 195:
            return False, f"Soma {soma} < 195"
        
        if max_seq > 4:
            return False, f"Sequência {max_seq} > 4"
        
        if num_frios < 6:
            return False, f"Frios {num_frios} < 6"
        
        # REGRA 2: Limpeza dos RUINS
        num_quentes = len([n for n in jogo if n in self.numeros_quentes])
        
        if soma < 175:
            return False, f"Soma {soma} < 175 (RUIM)"
        
        if num_quentes >= 6 and num_frios <= 5:
            return False, f"Quentes {num_quentes} ≥6 e Frios {num_frios} ≤5 (RUIM)"
        
        return True, "APROVADO"
    
    def classificar_jogo(self, jogo):
        """
        Classifica o jogo em Potencial, Bom, Regular ou Ruim
        """
        if len(jogo) != 15:
            return "❌ INVÁLIDO"
        
        soma = sum(jogo)
        max_seq = self._calcular_max_sequencia(jogo)
        num_frios = len([n for n in jogo if n in self.numeros_frios])
        num_quentes = len([n for n in jogo if n in self.numeros_quentes])
        
        # Critérios baseados no Jogo 5
        if soma >= 195 and max_seq <= 4 and num_frios >= 6:
            return "🔥 POTENCIAL"
        elif soma >= 185 and max_seq <= 5 and num_frios >= 4:
            return "✅ BOM"
        elif soma >= 175 and max_seq <= 6 and num_frios >= 3:
            return "⚠️ REGULAR"
        else:
            return "❌ RUIM"
    
    # =================================================
    # ESTRATÉGIA PRINCIPAL - DNA DO JOGO 5
    # =================================================
    def estrategia_dna_jogo5(self, n_jogos=15):
        """
        Gera jogos baseados no DNA do Jogo 5:
        - Soma ≥195
        - Máx sequência ≤4
        - Frios ≥6
        - Distribuição controlada por lote
        """
        jogos = []
        
        # Define a composição do lote (REGRA 3)
        n_potencial = max(1, int(n_jogos * 0.2))  # 20% potencial
        n_bom = max(3, int(n_jogos * 0.5))        # 50% bom
        n_regular = max(2, int(n_jogos * 0.2))    # 20% regular
        n_ruim_max = max(1, int(n_jogos * 0.1))   # Máx 10% ruim
        
        # Números base do Jogo 5 (os mais frequentes)
        base_forte = [3, 4, 5, 6, 7, 8, 9, 11, 19, 20, 21, 23, 24]
        
        tentativas = 0
        max_tentativas = n_jogos * 100
        
        while len(jogos) < n_jogos and tentativas < max_tentativas:
            tentativas += 1
            
            # Decide a classe do jogo baseado na necessidade
            classes_atuais = [self.classificar_jogo(j) for j in jogos]
            
            if classes_atuais.count("🔥 POTENCIAL") < n_potencial:
                classe_alvo = "POTENCIAL"
            elif classes_atuais.count("✅ BOM") < n_bom:
                classe_alvo = "BOM"
            elif classes_atuais.count("⚠️ REGULAR") < n_regular:
                classe_alvo = "REGULAR"
            else:
                classe_alvo = "RUIM" if classes_atuais.count("❌ RUIM") < n_ruim_max else None
            
            if not classe_alvo:
                # Se já atingiu o limite de ruins, tenta gerar um bom/potencial
                classe_alvo = random.choice(["POTENCIAL", "BOM"])
            
            # Gera jogo baseado na classe alvo
            jogo = set()
            
            # SEMPRE inclui a base forte do Jogo 5 (mas com variação)
            qtd_base = random.randint(8, 11)  # Mantém 8-11 números da base
            base_escolhida = random.sample(base_forte, min(qtd_base, len(base_forte)))
            jogo.update(base_escolhida)
            
            # Adiciona frios para garantir a regra
            if classe_alvo == "POTENCIAL":
                # Potencial: muitos frios
                qtd_frios = random.randint(6, 8)
            elif classe_alvo == "BOM":
                qtd_frios = random.randint(5, 7)
            elif classe_alvo == "REGULAR":
                qtd_frios = random.randint(4, 6)
            else:  # RUIM
                qtd_frios = random.randint(3, 5)
            
            # Adiciona frios disponíveis
            frios_disponiveis = [f for f in self.numeros_frios if f not in jogo]
            if frios_disponiveis:
                qtd_frios_real = min(qtd_frios, len(frios_disponiveis))
                jogo.update(random.sample(frios_disponiveis, qtd_frios_real))
            
            # Completa com números variados
            while len(jogo) < 15:
                candidatos = [n for n in self.numeros if n not in jogo]
                if candidatos:
                    # Prioriza números que não criam sequências longas
                    melhor_candidato = None
                    melhor_seq = 100
                    
                    for c in candidatos:
                        jogo_teste = sorted(jogo | {c})
                        seq_teste = self._calcular_max_sequencia(jogo_teste)
                        
                        if seq_teste < melhor_seq:
                            melhor_seq = seq_teste
                            melhor_candidato = c
                    
                    if melhor_candidato:
                        jogo.add(melhor_candidato)
                    else:
                        jogo.add(random.choice(candidatos))
            
            jogo_ordenado = sorted(jogo)
            
            # Aplica filtros baseados na classe alvo
            if classe_alvo == "POTENCIAL":
                valido, motivo = self.aplicar_filtros_dna(jogo_ordenado)
                if valido and self.classificar_jogo(jogo_ordenado) == "🔥 POTENCIAL":
                    if jogo_ordenado not in jogos:
                        jogos.append(jogo_ordenado)
            
            elif classe_alvo == "BOM":
                soma = sum(jogo_ordenado)
                max_seq = self._calcular_max_sequencia(jogo_ordenado)
                num_frios = len([n for n in jogo_ordenado if n in self.numeros_frios])
                
                if soma >= 185 and max_seq <= 5 and num_frios >= 4:
                    if jogo_ordenado not in jogos:
                        jogos.append(jogo_ordenado)
            
            elif classe_alvo == "REGULAR":
                soma = sum(jogo_ordenado)
                max_seq = self._calcular_max_sequencia(jogo_ordenado)
                
                if soma >= 175 and max_seq <= 6:
                    if jogo_ordenado not in jogos:
                        jogos.append(jogo_ordenado)
            
            else:  # RUIM (controlado)
                if classes_atuais.count("❌ RUIM") < n_ruim_max:
                    # Permite ruins mas com limite
                    if jogo_ordenado not in jogos:
                        jogos.append(jogo_ordenado)
        
        return jogos[:n_jogos]
    
    # =================================================
    # CONFERÊNCIA
    # =================================================
    def conferir_jogos(self, jogos, concurso_alvo=None):
        """Conferência com classificação"""
        if concurso_alvo is None:
            concurso_alvo = self.ultimo_concurso
        
        dados = []
        
        for idx, jogo in enumerate(jogos, start=1):
            acertos = len(set(jogo) & set(concurso_alvo)) if concurso_alvo else 0
            classificacao = self.classificar_jogo(jogo)
            
            # Aplica filtros DNA
            valido_dna, motivo_dna = self.aplicar_filtros_dna(jogo)
            
            dados.append({
                "Jogo": idx,
                "Dezenas": ", ".join([f"{n:02d}" for n in jogo]),
                "Acertos": acertos,
                "Classificação": classificacao,
                "Soma": sum(jogo),
                "Max Seq": self._calcular_max_sequencia(jogo),
                "Frios": len([n for n in jogo if n in self.numeros_frios]),
                "Quentes": len([n for n in jogo if n in self.numeros_quentes]),
                "DNA OK": "✅" if valido_dna else "❌",
                "Motivo": motivo_dna if not valido_dna else "-"
            })
        
        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("🎯 LOTOFÁCIL - DNA DO JOGO 5 V4")
    
    st.markdown("""
    ### 🧬 Estratégia Baseada no Jogo 5 (Referência)
    
    **Regras Obrigatórias:**
    1. **DNA do Jogo 5:** Soma ≥195 | Máx Sequência ≤4 | Frios ≥6
    2. **Limpeza dos RUINS:** Eliminar Soma <175 ou Quentes≥6 e Frios≤5
    3. **Lote Ideal (15 jogos):** 3🔥 Potencial | 7✅ Bom | 3⚠️ Regular | 0-2❌ Ruim
    
    ⚠️ **Use com responsabilidade!**
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
                    
                    if len(concursos) >= 20:
                        st.session_state.concursos = concursos
                        st.session_state.analise = AnaliseLotofacilDNA(concursos)
                        
                        st.success(f"✅ {len(concursos)} concursos")
                        
                        # Mostra estatísticas
                        st.subheader("📊 Referência Jogo 5")
                        st.info("DNA: Soma≥195 | Seq≤4 | Frios≥6")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("🔥 Quentes", len(st.session_state.analise.numeros_quentes))
                        with col2:
                            st.metric("❄️ Frios", len(st.session_state.analise.numeros_frios))
                        
                except Exception as e:
                    st.error(f"Erro: {e}")
    
    # Abas
    if st.session_state.concursos and len(st.session_state.concursos) >= 20:
        tab1, tab2, tab3 = st.tabs(["📊 Análise", "🧬 Gerar DNA", "📈 Resultados"])
        
        with tab1:
            st.header("📊 Análise do DNA")
            
            # Mostra números quentes e frios
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🔥 Números Quentes (Top 8)")
                st.write(f"**{', '.join([str(n) for n in st.session_state.analise.numeros_quentes])}**")
                
                fig_freq = px.bar(
                    x=list(st.session_state.analise.frequencias.keys()),
                    y=list(st.session_state.analise.frequencias.values()),
                    title="Frequência (%)",
                    labels={'x': 'Número', 'y': 'Frequência'}
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            
            with col2:
                st.subheader("❄️ Números Frios (Bottom 8)")
                st.write(f"**{', '.join([str(n) for n in st.session_state.analise.numeros_frios])}**")
                
                # Simulação de acertos baseados no DNA
                st.subheader("🎯 Meta DNA Jogo 5")
                st.metric("Soma Mínima", "195", "≥195")
                st.metric("Sequência Máx", "4", "≤4")
                st.metric("Frios Mínimos", "6", "≥6")
        
        with tab2:
            st.header("🧬 Gerar Jogos com DNA do Jogo 5")
            
            quantidade = st.number_input("Quantidade de jogos", 5, 50, 15)
            
            if st.button("🧬 Gerar com DNA Jogo 5", type="primary"):
                with st.spinner("Aplicando filtros do Jogo 5..."):
                    st.session_state.jogos = st.session_state.analise.estrategia_dna_jogo5(quantidade)
                    
                    # Estatísticas do lote gerado
                    classes = [st.session_state.analise.classificar_jogo(j) for j in st.session_state.jogos]
                    
                    st.success(f"✅ {len(st.session_state.jogos)} jogos gerados!")
                    
                    # Mostra distribuição do lote
                    st.subheader("📊 Distribuição do Lote (Regra 3)")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("🔥 Potencial", classes.count("🔥 POTENCIAL"), "Meta: 3")
                    with col2:
                        st.metric("✅ Bom", classes.count("✅ BOM"), "Meta: 7")
                    with col3:
                        st.metric("⚠️ Regular", classes.count("⚠️ REGULAR"), "Meta: 3")
                    with col4:
                        st.metric("❌ Ruim", classes.count("❌ RUIM"), "Máx: 2")
        
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
                resultado = st.session_state.analise.conferir_jogos(
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
                
                # Verifica quantos jogos passaram no DNA
                dna_ok = sum(df_resultado['DNA OK'] == "✅")
                st.metric("✅ Jogos com DNA OK", dna_ok)
                
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
                    file_name=f"resultados_dna_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ℹ️ Gere jogos primeiro!")

if __name__ == "__main__":
    main()
