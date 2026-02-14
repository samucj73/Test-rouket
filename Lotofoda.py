import streamlit as st
import requests
import numpy as np
import pandas as pd
import random
from collections import Counter
import matplotlib.pyplot as plt

st.set_page_config(page_title="⚡ LOTOFÁCIL - ÚLTIMO CONCURSO FORA DOS CÁLCULOS", layout="wide")

# ============================================
# CLASSE CORRIGIDA - ÚLTIMO CONCURSO EXCLUÍDO
# ============================================
class EstrategiasLotofacil:
    def __init__(self, concursos):
        """
        CORREÇÃO ABSOLUTA:
        - concursos[0] = MAIS RECENTE (NÃO usado nos cálculos) → SÓ CONFERÊNCIA
        - concursos[1:] = HISTÓRICO (USADO nos cálculos)
        """
        # ÚLTIMO CONCURSO (MAIS RECENTE) - APENAS PARA CONFERÊNCIA
        self.ultimo_concurso = concursos[0] if len(concursos) > 0 else []
        
        # TODOS OS OUTROS CONCURSOS - USADOS NOS CÁLCULOS
        self.concursos_historicos = concursos[1:] if len(concursos) > 1 else []
        
        self.numeros = list(range(1, 26))
        
        # AVISO VISUAL
        print("🔴 ÚLTIMO CONCURSO (MAIS RECENTE) EXCLUÍDO DOS CÁLCULOS:")
        print(f"📌 Último (só conferência): {self.ultimo_concurso}")
        print(f"📚 Histórico (usado): {len(self.concursos_historicos)} concursos")
    
    # ============================================
    # ESTRATÉGIA 1: REPETIÇÃO DO PENÚLTIMO
    # ============================================
    def estrategia_repeticao_penultimo(self, n_jogos=10):
        """
        USA O PENÚLTIMO CONCURSO (concursos_historicos[0]) como base
        O ÚLTIMO (mais recente) NÃO é usado
        """
        if len(self.concursos_historicos) < 1:
            return self.aleatorio_controlado(n_jogos)
        
        # USA O PENÚLTIMO CONCURSO (índice 0 do histórico = segundo mais recente)
        penultimo = self.concursos_historicos[0]
        
        jogos = []
        for _ in range(n_jogos * 2):
            jogo = []
            
            # Repete 8-10 números do PENÚLTIMO
            qtd_repetir = random.randint(8, 10)
            repetidos = random.sample(penultimo, min(qtd_repetir, len(penultimo)))
            jogo.extend(repetidos)
            
            # Completa com números aleatórios
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            while len(jogo) > 15:
                jogo.pop()
            
            jogo = sorted(jogo)
            
            # Verifica se já existe
            if jogo not in jogos:
                jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 2: TOP DEZENAS DO HISTÓRICO
    # ============================================
    def estrategia_top_historico(self, n_jogos=10):
        """
        USA SOMENTE DADOS HISTÓRICOS (excluindo o último)
        """
        if len(self.concursos_historicos) < 20:
            return self.aleatorio_controlado(n_jogos)
        
        # Calcula frequência APENAS do HISTÓRICO (NÃO inclui o último)
        freq = Counter()
        for concurso in self.concursos_historicos[:50]:  # USA SÓ HISTÓRICO
            freq.update(concurso)
        
        top15 = [n for n, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15]]
        
        jogos = []
        for _ in range(n_jogos):
            # Pega 12-14 números do top15
            qtd_top = random.randint(12, 14)
            jogo = random.sample(top15, min(qtd_top, len(top15)))
            
            # Completa
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogos.append(sorted(jogo))
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 3: PADRÃO DE REPETIÇÃO REAL
    # ============================================
    def estrategia_padrao_repeticao(self, n_jogos=15):
        """
        Analisa padrões de repetição do HISTÓRICO (excluindo último)
        """
        if len(self.concursos_historicos) < 20:
            return self.aleatorio_controlado(n_jogos)
        
        # Calcula média de repetição do HISTÓRICO
        repeticoes = []
        for i in range(len(self.concursos_historicos) - 1):
            rep = len(set(self.concursos_historicos[i]) & set(self.concursos_historicos[i + 1]))
            repeticoes.append(rep)
        
        media_rep = np.mean(repeticoes) if repeticoes else 9
        rep_min = max(7, int(media_rep - 1.5))
        rep_max = min(11, int(media_rep + 1.5))
        
        # Base = primeiro do histórico (segundo mais recente)
        base = self.concursos_historicos[0]
        
        jogos = []
        for _ in range(n_jogos * 2):
            qtd_rep = random.randint(rep_min, rep_max)
            
            # Pega repetidos do base
            repetidos = random.sample(base, min(qtd_rep, len(base)))
            jogo = list(repetidos)
            
            # Completa com números que complementam
            while len(jogo) < 15:
                candidato = random.choice(self.numeros)
                if candidato not in jogo:
                    jogo.append(candidato)
            
            jogo = sorted(jogo)
            
            # Valida se repete a quantidade esperada
            rep_final = len(set(jogo) & set(base))
            if rep_min <= rep_final <= rep_max and jogo not in jogos:
                jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # ESTRATÉGIA 4: AGRESSIVA TOTAL
    # ============================================
    def estrategia_agressiva_total(self, n_jogos=15):
        """
        Combina TODOS os padrões do HISTÓRICO
        """
        if len(self.concursos_historicos) < 20:
            return self.aleatorio_controlado(n_jogos)
        
        # Top dezenas do histórico
        freq = Counter()
        for c in self.concursos_historicos[:50]:
            freq.update(c)
        top15 = [n for n, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15]]
        
        # Base = penúltimo
        base = self.concursos_historicos[0]
        
        jogos = []
        for _ in range(n_jogos * 3):
            jogo = set()
            
            # 1. Repete 8-10 do base
            qtd_base = random.randint(8, 10)
            repetidos = random.sample(base, min(qtd_base, len(base)))
            jogo.update(repetidos)
            
            # 2. Adiciona top dezenas
            for top in top15[:10]:
                if len(jogo) < 15:
                    jogo.add(top)
            
            # 3. Completa
            while len(jogo) < 15:
                jogo.add(random.choice(self.numeros))
            
            jogo = sorted(list(jogo))[:15]
            
            # Valida
            rep_base = len(set(jogo) & set(base))
            top_count = len([n for n in jogo if n in top15[:12]])
            
            if rep_base >= 7 and top_count >= 10:
                if jogo not in jogos:
                    jogos.append(jogo)
            
            if len(jogos) >= n_jogos:
                break
        
        return jogos[:n_jogos]
    
    # ============================================
    # CONFERÊNCIA COM O ÚLTIMO CONCURSO
    # ============================================
    def conferir_com_ultimo(self, jogos):
        """
        Confere os jogos com o ÚLTIMO CONCURSO (que NÃO foi usado)
        """
        if not self.ultimo_concurso:
            return []
        
        resultados = []
        for i, jogo in enumerate(jogos, 1):
            acertos = len(set(jogo) & set(self.ultimo_concurso))
            
            status = "⚪ SEM PREMIAÇÃO"
            if acertos >= 15:
                status = "🏆 SENA"
            elif acertos == 14:
                status = "💰 QUINA"
            elif acertos == 13:
                status = "🎯 QUADRA"
            elif acertos == 12:
                status = "✨ TERNO"
            elif acertos == 11:
                status = "⭐ DUQUE"
            
            resultados.append({
                'Jogo': i,
                'Dezenas': str(jogo),
                'Acertos': acertos,
                'Status': status
            })
        
        return resultados
    
    def aleatorio_controlado(self, n_jogos=5):
        """Fallback"""
        jogos = []
        for _ in range(n_jogos):
            jogo = sorted(random.sample(self.numeros, 15))
            jogos.append(jogo)
        return jogos


# ============================================
# INTERFACE STREAMLIT - COM AVISOS CLAROS
# ============================================
def main():
    st.title("⚡ LOTOFÁCIL - ÚLTIMO CONCURSO EXCLUÍDO DOS CÁLCULOS")
    
    st.error("""
    ### 🔴 AVISO IMPORTANTE - LEIA ANTES DE CONTINUAR:
    
    **O ÚLTIMO CONCURSO (MAIS RECENTE) ESTÁ TOTALMENTE EXCLUÍDO DOS CÁLCULOS!**
    
    - ✅ **Último concurso** → Usado APENAS para CONFERÊNCIA
    - ✅ **Histórico** → Usado para TODOS os cálculos
    - ✅ Backtesting 100% honesto e sem viés
    """)
    
    # Inicialização
    if 'concursos' not in st.session_state:
        st.session_state.concursos = []
    if 'jogos_atuais' not in st.session_state:
        st.session_state.jogos_atuais = []
    
    # Sidebar
    with st.sidebar:
        st.header("📥 CARREGAR CONCURSOS")
        
        qtd = st.slider("Quantidade de concursos", min_value=16, max_value=300, value=100, step=10)
        
        if st.button("🔄 CARREGAR CONCURSOS", use_container_width=True, type="primary"):
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
                        
                        # MOSTRA CLARAMENTE A SEPARAÇÃO
                        st.success(f"✅ {len(concursos)} concursos carregados!")
                        
                        st.divider()
                        
                        # ÚLTIMO CONCURSO (NÃO USADO)
                        st.error("🚫 **EXCLUÍDO DOS CÁLCULOS:**")
                        st.code(f"Último: {concursos[0]}")
                        
                        # HISTÓRICO (USADO)
                        st.success("✅ **USADO NOS CÁLCULOS:**")
                        st.caption(f"{len(concursos)-1} concursos")
                        if len(concursos) > 1:
                            st.code(f"Penúltimo: {concursos[1]}")
                        
                except Exception as e:
                    st.error(f"Erro: {e}")
        
        if st.session_state.concursos:
            st.divider()
            st.metric("Total carregado", len(st.session_state.concursos))
            st.metric("Base de cálculos", len(st.session_state.concursos) - 1)
            st.metric("Conferência apenas", 1)
    
    # Main content
    if st.session_state.concursos and len(st.session_state.concursos) >= 16:
        # CRIA INSTÂNCIA COM A CORREÇÃO
        estrategia = EstrategiasLotofacil(st.session_state.concursos)
        
        tab1, tab2 = st.tabs(["⚡ GERAR JOGOS", "✅ CONFERIR COM ÚLTIMO"])
        
        with tab1:
            st.header("⚡ GERAR JOGOS (USANDO SÓ HISTÓRICO)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                estrategia_sel = st.selectbox(
                    "Escolha a estratégia (todas usam apenas HISTÓRICO):",
                    [
                        "1. Repetição do Penúltimo",
                        "2. Top Dezenas do Histórico",
                        "3. Padrão de Repetição",
                        "4. Agressiva Total"
                    ]
                )
            
            with col2:
                n_jogos = st.number_input("Quantidade de jogos", min_value=5, max_value=50, value=15)
            
            if st.button("🚀 GERAR JOGOS", use_container_width=True):
                with st.spinner("Gerando jogos com dados HISTÓRICOS..."):
                    mapa = {
                        "1. Repetição do Penúltimo": estrategia.estrategia_repeticao_penultimo,
                        "2. Top Dezenas do Histórico": estrategia.estrategia_top_historico,
                        "3. Padrão de Repetição": estrategia.estrategia_padrao_repeticao,
                        "4. Agressiva Total": estrategia.estrategia_agressiva_total
                    }
                    
                    jogos = mapa[estrategia_sel](n_jogos)
                    st.session_state.jogos_atuais = jogos
                    
                    st.success(f"✅ {len(jogos)} jogos gerados!")
                    
                    # Mostra jogos
                    st.subheader("📋 JOGOS GERADOS:")
                    for i, jogo in enumerate(jogos, 1):
                        st.write(f"{i:2d}. {jogo}")
            
            if st.session_state.jogos_atuais:
                # Download
                conteudo = "\n".join([",".join(map(str, j)) for j in st.session_state.jogos_atuais])
                st.download_button(
                    "💾 BAIXAR JOGOS",
                    data=conteudo,
                    file_name=f"jogos_{len(st.session_state.jogos_atuais)}.txt",
                    use_container_width=True
                )
        
        with tab2:
            st.header("✅ CONFERIR COM O ÚLTIMO CONCURSO")
            
            if st.session_state.concursos:
                ultimo = st.session_state.concursos[0]
                
                st.info("🎯 **ÚLTIMO CONCURSO (NÃO USADO NOS CÁLCULOS):**")
                st.code(ultimo)
                
                if st.session_state.jogos_atuais:
                    st.subheader("📊 RESULTADOS DA CONFERÊNCIA")
                    
                    resultados = estrategia.conferir_com_ultimo(st.session_state.jogos_atuais)
                    
                    if resultados:
                        df = pd.DataFrame(resultados)
                        
                        # Destaca acertos
                        def cor_acertos(val):
                            if val >= 14:
                                return 'background-color: #ff4444'
                            elif val >= 13:
                                return 'background-color: #ff8844'
                            elif val >= 11:
                                return 'background-color: #44ff44'
                            return ''
                        
                        st.dataframe(df.style.applymap(cor_acertos, subset=['Acertos']), 
                                   use_container_width=True, hide_index=True)
                        
                        # Estatísticas
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Média de Acertos", f"{df['Acertos'].mean():.1f}")
                        with col2:
                            premiados = len(df[df['Acertos'] >= 11])
                            st.metric("Jogos Premiados", premiados)
                        with col3:
                            st.metric("Maior Acerto", df['Acertos'].max())
    
    else:
        st.warning("👈 **Carregue no mínimo 16 concursos no menu lateral**")
        st.info("""
        **Por que 16 concursos?**
        - 1 concurso para CONFERÊNCIA (excluído)
        - 15 concursos para BASE DE CÁLCULO (usados)
        """)

if __name__ == "__main__":
    main()
