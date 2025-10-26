import streamlit as st
import requests
import numpy as np
import random
from collections import Counter
from catboost import CatBoostClassifier
import itertools
import math

st.set_page_config(page_title="Lotofácil Inteligente", layout="centered")

# =========================
# Captura concursos via API (robusta)
# =========================
def capturar_ultimos_resultados(qtd=250):
    url_base = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
    concursos = []

    try:
        resp = requests.get(url_base, timeout=20)
        if resp.status_code != 200:
            st.error("Erro ao buscar o último concurso.")
            return [], None

        dados = resp.json()
        ultimo = dados[0] if isinstance(dados, list) else dados

        numero_atual = int(ultimo.get("concurso"))
        data_concurso = ultimo.get("data")
        dezenas = sorted([int(d) for d in ultimo.get("dezenas")])
        concursos.append(dezenas)

        info_ultimo = {
            "numero": numero_atual,
            "data": data_concurso,
            "dezenas": dezenas
        }

        for i in range(1, qtd):
            concurso_numero = numero_atual - i
            try:
                resp_i = requests.get(f"{url_base}{concurso_numero}", timeout=20)
                if resp_i.status_code == 200:
                    dados_i = resp_i.json()
                    data_i = dados_i[0] if isinstance(dados_i, list) else dados_i
                    dezenas_i = sorted([int(d) for d in data_i.get("dezenas")])
                    concursos.append(dezenas_i)
                else:
                    break
            except Exception:
                break

        return concursos, info_ultimo

    except Exception as e:
        st.error(f"Erro ao acessar API: {type(e).__name__}: {e}")
        return [], None

# =========================
# NOVA CLASSE: Análise Combinatória
# =========================
class AnaliseCombinatoria:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        
    def calcular_estatisticas_base(self):
        """Calcula estatísticas base dos concursos históricos"""
        if not self.concursos:
            return {}
            
        stats = {
            'media_pares': [],
            'media_soma': [],
            'media_primos': [],
            'distribuicoes': []
        }
        
        for concurso in self.concursos:
            pares = sum(1 for n in concurso if n % 2 == 0)
            soma = sum(concurso)
            primos = sum(1 for n in concurso if n in self.primos)
            
            stats['media_pares'].append(pares)
            stats['media_soma'].append(soma)
            stats['media_primos'].append(primos)
            
        return stats

    def gerar_combinacoes_otimizadas(self, tamanhos, quantidade_por_tamanho=1000):
        """Gera combinações otimizadas com filtros estatísticos"""
        todas_combinacoes = {}
        
        for tamanho in tamanhos:
            combinacoes_geradas = []
            tentativas = 0
            max_tentativas = quantidade_por_tamanho * 3
            
            while len(combinacoes_geradas) < quantidade_por_tamanho and tentativas < max_tentativas:
                combo = sorted(random.sample(self.numeros, tamanho))
                
                if self.validar_combinacao(combo, tamanho):
                    # Evitar duplicatas
                    if combo not in combinacoes_geradas:
                        combinacoes_geradas.append(combo)
                
                tentativas += 1
            
            # Analisar e ranquear as combinações
            combinacoes_ranqueadas = self.ranquear_combinacoes(combinacoes_geradas, tamanho)
            todas_combinacoes[tamanho] = combinacoes_ranqueadas[:quantidade_por_tamanho]
            
        return todas_combinacoes

    def validar_combinacao(self, combinacao, tamanho):
        """Valida combinação com base em estatísticas históricas"""
        pares = sum(1 for n in combinacao if n % 2 == 0)
        impares = len(combinacao) - pares
        soma = sum(combinacao)
        primos = sum(1 for n in combinacao if n in self.primos)
        
        # Critérios baseados no tamanho da combinação
        if tamanho == 15:
            return (6 <= pares <= 9 and 
                    170 <= soma <= 210 and
                    3 <= primos <= 7)
        
        elif tamanho == 14:
            return (5 <= pares <= 8 and 
                    160 <= soma <= 200 and
                    2 <= primos <= 6)
        
        elif tamanho == 13:
            return (5 <= pares <= 8 and 
                    150 <= soma <= 190 and
                    2 <= primos <= 6)
        
        elif tamanho == 12:
            return (4 <= pares <= 7 and 
                    130 <= soma <= 170 and
                    2 <= primos <= 5)
        
        return True

    def ranquear_combinacoes(self, combinacoes, tamanho):
        """Ranqueia combinações por probabilidade"""
        scores = []
        
        for combo in combinacoes:
            score = self.calcular_score_combinacao(combo, tamanho)
            scores.append((combo, score))
        
        # Ordenar por score (maiores primeiro)
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def calcular_score_combinacao(self, combinacao, tamanho):
        """Calcula score baseado em múltiplos fatores estatísticos"""
        score = 0
        
        # Fator par/ímpar
        pares = sum(1 for n in combinacao if n % 2 == 0)
        if tamanho == 15 and 6 <= pares <= 8:
            score += 3
        elif tamanho == 14 and 5 <= pares <= 8:
            score += 3
        elif tamanho == 13 and 5 <= pares <= 7:
            score += 3
        elif tamanho == 12 and 4 <= pares <= 6:
            score += 3
            
        # Fator soma
        soma = sum(combinacao)
        if tamanho == 15 and 180 <= soma <= 200:
            score += 3
        elif tamanho == 14 and 160 <= soma <= 190:
            score += 3
        elif tamanho == 13 and 150 <= soma <= 180:
            score += 3
        elif tamanho == 12 and 130 <= soma <= 160:
            score += 3
            
        # Fator números consecutivos
        consecutivos = self.contar_consecutivos(combinacao)
        if consecutivos <= 4:
            score += 2
            
        # Fator números primos
        primos = sum(1 for n in combinacao if n in self.primos)
        if 3 <= primos <= 6:
            score += 2
            
        # Fator de distribuição
        if self.validar_distribuicao(combinacao):
            score += 2
            
        # Fator de frequência histórica
        score += self.calcular_score_frequencia(combinacao)
        
        return score

    def contar_consecutivos(self, combinacao):
        """Conta números consecutivos na combinação"""
        consecutivos = 0
        for i in range(len(combinacao)-1):
            if combinacao[i+1] - combinacao[i] == 1:
                consecutivos += 1
        return consecutivos

    def validar_distribuicao(self, combinacao):
        """Valida distribuição por faixas de números"""
        faixa1 = sum(1 for n in combinacao if 1 <= n <= 9)   # 1-9
        faixa2 = sum(1 for n in combinacao if 10 <= n <= 19) # 10-19
        faixa3 = sum(1 for n in combinacao if 20 <= n <= 25) # 20-25
        
        total = len(combinacao)
        if total == 15:
            return (faixa1 >= 4 and faixa2 >= 5 and faixa3 >= 4)
        elif total == 14:
            return (faixa1 >= 4 and faixa2 >= 4 and faixa3 >= 4)
        elif total == 13:
            return (faixa1 >= 3 and faixa2 >= 4 and faixa3 >= 3)
        elif total == 12:
            return (faixa1 >= 3 and faixa2 >= 4 and faixa3 >= 3)
        
        return True

    def calcular_score_frequencia(self, combinacao):
        """Calcula score baseado na frequência histórica dos números"""
        if not self.concursos:
            return 0
            
        # Calcular frequência dos números nos últimos concursos
        freq = Counter()
        for concurso in self.concursos[:50]:  # Últimos 50 concursos
            for numero in concurso:
                freq[numero] += 1
                
        # Score baseado na frequência média dos números na combinação
        freq_media = sum(freq[n] for n in combinacao) / len(combinacao)
        freq_max = max(freq.values()) if freq.values() else 1
        
        # Normalizar score (0 a 2 pontos)
        return (freq_media / freq_max) * 2

    def gerar_relatorio_estatistico(self, combinacoes_por_tamanho):
        """Gera relatório estatístico das combinações"""
        relatorio = {}
        
        for tamanho, combinacoes in combinacoes_por_tamanho.items():
            if not combinacoes:
                continue
                
            stats = {
                'total_combinacoes': len(combinacoes),
                'media_score': np.mean([score for _, score in combinacoes]),
                'melhor_score': max([score for _, score in combinacoes]),
                'pior_score': min([score for _, score in combinacoes]),
                'exemplos_top5': combinacoes[:5]
            }
            relatorio[tamanho] = stats
            
        return relatorio

# =========================
# IA Avançada com CatBoost
# =========================
class LotoFacilIA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}
        self.models = {}
        self.X = self.gerar_features()[:-1] if len(concursos) > 1 else np.array([])
        self.Y = self.matriz_binaria()[1:] if len(concursos) > 1 else np.array([])
        if len(self.X) > 0 and len(self.Y) > 0:
            self.treinar_modelos()

    def matriz_binaria(self):
        return np.array([[1 if n in jogo else 0 for n in self.numeros] for jogo in self.concursos])

    def frequencia(self, janela=10):
        janela = min(janela, max(1, len(self.concursos)-1))
        freq = {n:0 for n in self.numeros}
        for jogo in self.concursos[-janela-1:-1]:
            for d in jogo:
                freq[d] +=1
        return freq

    def atraso(self):
        atraso = {n:0 for n in self.numeros}
        for i in range(len(self.concursos)-2, -1, -1):
            jogo = self.concursos[i]
            for n in self.numeros:
                if atraso[n]==0 and n not in jogo:
                    atraso[n] = len(self.concursos)-1 - i
        return atraso

    def quentes_frios(self, top=10):
        freq = self.frequencia()
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        quentes = [n for n,_ in numeros_ordenados[:top]]
        frios = [n for n,_ in numeros_ordenados[-top:]]
        return {"quentes": quentes, "frios": frios}

    def pares_impares_primos(self):
        ultimo = self.concursos[-1]
        pares = sum(1 for n in ultimo if n%2==0)
        impares = 15 - pares
        primos = sum(1 for n in ultimo if n in self.primos)
        return {"pares": pares, "impares": impares, "primos": primos}

    def interacoes(self, janela=50):
        janela = min(janela, max(1, len(self.concursos)-1))
        matriz = np.zeros((25,25), dtype=int)
        for jogo in self.concursos[-janela-1:-1]:
            for i in range(15):
                for j in range(i+1,15):
                    matriz[jogo[i]-1, jogo[j]-1] += 1
                    matriz[jogo[j]-1, jogo[i]-1] += 1
        return matriz

    def prob_condicional(self, janela=50):
        matriz = self.interacoes(janela)
        prob = np.zeros((25,25))
        freq = np.array([v for v in self.frequencia(janela).values()])
        for i in range(25):
            for j in range(25):
                if freq[i] > 0:
                    prob[i,j] = matriz[i,j]/freq[i]
        return prob

    def gap_medio(self):
        gaps = {n:[] for n in self.numeros}
        for i, jogo in enumerate(self.concursos[:-1]):
            for n in self.numeros:
                if n not in jogo:
                    gaps[n].append(len(self.concursos)-1-i)
        return {n: np.mean(gaps[n]) if gaps[n] else 0 for n in self.numeros}

    def gerar_features(self):
        features = []
        if len(self.concursos) < 2:
            return np.array([])
        freq = self.frequencia(janela=len(self.concursos)-1)
        gaps = self.gap_medio()
        for jogo in self.concursos:
            f = []
            for n in self.numeros:
                f.append(1 if n in jogo else 0)
                f.append(freq[n])
                f.append(gaps[n])
                f.append(1 if n%2==0 else 0)
                f.append(1 if n in self.primos else 0)
            features.append(f)
        return np.array(features)

    def treinar_modelos(self):
        for i, n in enumerate(self.numeros):
            model = CatBoostClassifier(iterations=600, verbose=0, random_state=42)
            y = self.Y[:,i]
            model.fit(self.X, y)
            self.models[n] = model

    def prever_proximo(self):
        if not self.models:
            return {n: 0.5 for n in self.numeros}
        ultima = self.gerar_features()[-1].reshape(1,-1)
        probabilidades = {}
        for n in self.numeros:
            prob = self.models[n].predict_proba(ultima)[0][1]
            probabilidades[n] = prob
        return probabilidades

    def gerar_5_jogos(self, probabilidades):
        ordenado = sorted(probabilidades.items(), key=lambda x:x[1], reverse=True)
        top15 = [n for n,_ in ordenado[:15]]
        top20 = [n for n,_ in ordenado[:20]]
        mid = [n for n,_ in ordenado[10:20]]
        frios = [n for n,_ in sorted(probabilidades.items(), key=lambda x:x[1])[:10]]

        jogos=[]
        jogos.append(sorted(top15))
        jogos.append(sorted(random.sample(top15, 10) + random.sample(mid,5)))
        jogos.append(sorted(random.sample(top15, 12) + random.sample(frios,3)))
        jogos.append(self._equilibrado(top20))
        jogos.append(self._equilibrado(top20, forcar_primos=True))
        # garantir distintos
        unicos = []
        seen = set()
        for j in jogos:
            t = tuple(j)
            if t not in seen:
                seen.add(t); unicos.append(j)
        while len(unicos) < 5:
            unicos.append(self._equilibrado(top20))
        return unicos

    def _equilibrado(self, base, forcar_primos=False):
        base = list(set(base))  # dedup
        while True:
            if len(base) < 15:
                base = list(range(1,26))
            cartao = sorted(random.sample(base,15))
            pares = sum(1 for n in cartao if n%2==0)
            primos_count = sum(1 for n in cartao if n in self.primos)
            if 7 <= pares <=10 and (not forcar_primos or primos_count>=3):
                return cartao

    # =========================
    # NOVO: Gerar 5 cartões por padrões últimos concursos (já existia no seu código)
    # =========================
    def gerar_cartoes_por_padroes(self, n_jogos=5, janela=10):
        janela = min(janela, len(self.concursos))
        ultimos = self.concursos[-janela:]
        freq = {n:0 for n in self.numeros}
        for jogo in ultimos:
            for n in jogo:
                freq[n] += 1

        quentes = [n for n,_ in sorted(freq.items(), key=lambda x:x[1], reverse=True)[:15]]
        evens_q = [x for x in quentes if x%2==0]
        odds_q  = [x for x in quentes if x%2==1]
        frios = [n for n,_ in sorted(freq.items(), key=lambda x:x[1])[:10]]

        padrao_par_impar = []
        for jogo in ultimos:
            pares = sum(1 for x in jogo if x%2==0)
            padrao_par_impar.append((pares, 15-pares))
        media_pares = int(np.round(np.mean([p for p,_ in padrao_par_impar])))
        media_pares = max(5, min(10, media_pares))  # limitar pra não travar
        media_impares = 15 - media_pares

        jogos=[]
        for _ in range(n_jogos):
            cartao = set()
            # escolhe pares
            candidatos_pares = evens_q if len(evens_q) >= media_pares else [x for x in range(2,26,2)]
            cartao.update(random.sample(candidatos_pares, media_pares))
            # escolhe ímpares
            candidatos_impares = odds_q if len(odds_q) >= media_impares else [x for x in range(1,26,2)]
            faltam = media_impares
            cartao.update(random.sample(candidatos_impares, faltam))
            # completa se faltar
            while len(cartao) < 15:
                cartao.add(random.choice(frios if frios else list(range(1,26))))
            jogos.append(sorted(list(cartao)))
        # garantir distintos
        unicos = []
        seen = set()
        for j in jogos:
            t = tuple(j)
            if t not in seen:
                seen.add(t); unicos.append(j)
        while len(unicos) < n_jogos:
            unicos.append(sorted(random.sample(range(1,26),15)))
        return unicos

# =========================
# PADRÕES LINHA×COLUNA
# =========================
# Mapeamento fixo 5x5 (linhas e colunas)
LINHAS = [
    list(range(1, 6)),
    list(range(6, 11)),
    list(range(11, 16)),
    list(range(16, 21)),
    list(range(21, 26))
]
COLUNAS = [
    list(range(1, 26, 5)),
    list(range(2, 26, 5)),
    list(range(3, 26, 5)),
    list(range(4, 26, 5)),
    list(range(5, 26, 5))
]

def contar_padroes_linha_coluna(concursos):
    padrao_linhas = []
    padrao_colunas = []
    for concurso in concursos:
        linha_cont = [sum(1 for n in concurso if n in l) for l in LINHAS]
        col_cont = [sum(1 for n in concurso if n in c) for c in COLUNAS]
        padrao_linhas.append(tuple(linha_cont))
        padrao_colunas.append(tuple(col_cont))
    return Counter(padrao_linhas), Counter(padrao_colunas)

def sugerir_padroes_futuros(freq_linhas, freq_colunas, n=5):
    pads_l = [p for p,_ in freq_linhas.most_common(n)] or [(3,3,3,3,3)]
    pads_c = [p for p,_ in freq_colunas.most_common(n)] or [(3,3,3,3,3)]
    futuros = []
    for i in range(n):
        futuros.append({"linhas": pads_l[i % len(pads_l)], "colunas": pads_c[i % len(pads_c)]})
    return futuros

# =========================
# Streamlit - Estado
# =========================
if "concursos" not in st.session_state:
    st.session_state.concursos = []
if "cartoes_gerados" not in st.session_state:
    st.session_state.cartoes_gerados = []
if "cartoes_gerados_padrao" not in st.session_state:
    st.session_state.cartoes_gerados_padrao = []
if "info_ultimo_concurso" not in st.session_state:
    st.session_state.info_ultimo_concurso = None
if "combinacoes_combinatorias" not in st.session_state:  # NOVO
    st.session_state.combinacoes_combinatorias = {}

st.markdown("<h1 style='text-align: center;'>Lotofácil Inteligente</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- Captura concursos ---
with st.expander("📥 Capturar Concursos"):
    qtd_concursos = st.slider("Quantidade de concursos para análise", 10, 250, 100)
    if st.button("🔄 Capturar Agora"):
        with st.spinner("Capturando concursos da Lotofácil..."):
            concursos, info = capturar_ultimos_resultados(qtd_concursos)
            if concursos:
                st.session_state.concursos = concursos
                st.session_state.info_ultimo_concurso = info
                st.success(f"{len(concursos)} concursos capturados com sucesso!")
            else:
                st.error("Não foi possível capturar concursos.")

# --- Abas principais ---
if st.session_state.concursos:
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    jogos_gerados = ia.gerar_5_jogos(probs) if probs else []
    quentes_frios = ia.quentes_frios()
    pares_impares_primos = ia.pares_impares_primos()

    # NOVA ABA: Análises Combinatórias
    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões", 
        "🧩 Gerar Cartões por Padrões",
        "🔢 Análises Combinatórias",  # NOVA ABA
        "📐 Padrões Linha×Coluna",
        "✅ Conferência", 
        "📤 Conferir Arquivo TXT"
    ])

    # Aba 1 - Estatísticas
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Números quentes: {quentes_frios['quentes']}")
        st.write(f"Números frios: {quentes_frios['frios']}")
        st.write(f"Pares/Ímpares/Primos último concurso: {pares_impares_primos}")
        st.write(f"Frequência últimos 50 concursos (excluindo último): {ia.frequencia()}")
        st.write(f"Atraso de cada número (excluindo último concurso): {ia.atraso()}")

    # Aba 2 - Gerar Cartões
    with abas[1]:
        st.subheader("🧾 Geração de Cartões Inteligentes")
        if st.button("🚀 Gerar 5 Cartões"):
            st.session_state.cartoes_gerados = jogos_gerados
            st.success("5 Cartões gerados com sucesso!")
        if st.session_state.cartoes_gerados:
            for i, c in enumerate(st.session_state.cartoes_gerados,1):
                st.write(f"Jogo {i}: {c}")

            st.subheader("📁 Exportar Cartões para TXT")
            conteudo = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados)
            st.download_button("💾 Baixar Arquivo", data=conteudo, file_name="cartoes_lotofacil.txt", mime="text/plain")

    # Aba 3 - Gerar Cartões por Padrões (já tinha)
    with abas[2]:
        st.subheader("🧩 Geração de Cartões com Base em Padrões")
        janela_padrao = st.slider("Janela (nº de concursos recentes)", 5, 100, 10, 5)
        if st.button("🚀 Gerar 5 Cartões por Padrões"):
            cartoes_padrao = ia.gerar_cartoes_por_padroes(n_jogos=5, janela=janela_padrao)
            st.session_state.cartoes_gerados_padrao = cartoes_padrao
            st.success("5 Cartões por Padrões gerados com sucesso!")
        
        if st.session_state.cartoes_gerados_padrao:
            for i, c in enumerate(st.session_state.cartoes_gerados_padrao,1):
                st.write(f"Cartão {i}: {c}")

            st.subheader("📁 Exportar Cartões por Padrões para TXT")
            conteudo_padrao = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados_padrao)
            st.download_button("💾 Baixar Arquivo Padrões", data=conteudo_padrao, file_name="cartoes_padroes_lotofacil.txt", mime="text/plain")

    # NOVA ABA 4 - Análises Combinatórias
    with abas[3]:
        st.subheader("🔢 Análises Combinatórias - Combinações Matemáticas")
        
        # Inicializar analisador combinatorio
        analisador_combinatorio = AnaliseCombinatoria(st.session_state.concursos)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ⚙️ Configurações")
            tamanhos_selecionados = st.multiselect(
                "Selecione os tamanhos de combinação:",
                [12, 13, 14, 15],
                default=[14, 15]
            )
            
            quantidade_por_tamanho = st.slider(
                "Quantidade de combinações por tamanho:",
                min_value=10,
                max_value=500,
                value=100,
                step=10
            )
            
            if st.button("🎯 Gerar Combinações Otimizadas", type="primary"):
                with st.spinner("Gerando e analisando combinações..."):
                    combinacoes = analisador_combinatorio.gerar_combinacoes_otimizadas(
                        tamanhos_selecionados, 
                        quantidade_por_tamanho
                    )
                    st.session_state.combinacoes_combinatorias = combinacoes
                    st.success(f"Combinações geradas com sucesso!")
        
        with col2:
            st.markdown("### 📈 Estatísticas dos Filtros")
            stats_base = analisador_combinatorio.calcular_estatisticas_base()
            if stats_base:
                st.write(f"**Média de pares (histórico):** {np.mean(stats_base['media_pares']):.1f}")
                st.write(f"**Média de soma (histórico):** {np.mean(stats_base['media_soma']):.1f}")
                st.write(f"**Média de primos (histórico):** {np.mean(stats_base['media_primos']):.1f}")
        
        # Mostrar resultados
        if st.session_state.combinacoes_combinatorias:
            st.markdown("### 🎯 Combinações Geradas (Top 10 por Tamanho)")
            
            for tamanho in sorted(st.session_state.combinacoes_combinatorias.keys()):
                combinacoes_tamanho = st.session_state.combinacoes_combinatorias[tamanho]
                
                if combinacoes_tamanho:
                    st.markdown(f"#### 📊 Combinações com {tamanho} números (Top 10)")
                    
                    # Criar colunas para exibição
                    cols = st.columns(2)
                    for idx, (combo, score) in enumerate(combinacoes_tamanho[:10]):
                        with cols[idx % 2]:
                            st.code(f"Score: {score:.1f} → {combo}")
            
            # Relatório estatístico
            st.markdown("### 📋 Relatório Estatístico")
            relatorio = analisador_combinatorio.gerar_relatorio_estatistico(
                st.session_state.combinacoes_combinatorias
            )
            
            for tamanho, stats in relatorio.items():
                with st.expander(f"Estatísticas para {tamanho} números"):
                    st.write(f"Total de combinações: {stats['total_combinacoes']}")
                    st.write(f"Score médio: {stats['media_score']:.2f}")
                    st.write(f"Melhor score: {stats['melhor_score']:.2f}")
                    st.write(f"Pior score: {stats['pior_score']:.2f}")
            
            # Exportar combinações
            st.markdown("### 💾 Exportar Combinações")
            conteudo_combinacoes = ""
            for tamanho, combinacoes_list in st.session_state.combinacoes_combinatorias.items():
                conteudo_combinacoes += f"# Combinações com {tamanho} números\n"
                for combo, score in combinacoes_list[:20]:  # Top 20 de cada
                    conteudo_combinacoes += f"{','.join(map(str, combo))} # Score: {score:.1f}\n"
                conteudo_combinacoes += "\n"
            
            st.download_button(
                "📥 Baixar Todas as Combinações",
                data=conteudo_combinacoes,
                file_name="combinacoes_otimizadas.txt",
                mime="text/plain"
            )

    # Aba 5 - Padrões Linha×Coluna (antiga 4)
    with abas[4]:
        st.subheader("📐 Padrões de Linhas × Colunas")
        concursos = st.session_state.concursos
        if not concursos:
            st.info("Capture concursos na seção acima para analisar os padrões.")
        else:
            # CORREÇÃO AQUI: Slider com parâmetros nomeados corretamente
            max_concursos = min(500, len(concursos))
            valor_padrao = min(100, len(concursos))
            
            janela_lc = st.slider(
                "Concursos a considerar (mais recentes)", 
                min_value=20, 
                max_value=max_concursos, 
                value=valor_padrao, 
                step=10
            )
            
            subset = concursos[:janela_lc]

            if st.button("🔍 Analisar Padrões Linha×Coluna"):
                freq_linhas, freq_colunas = contar_padroes_linha_coluna(subset)

                st.markdown("### 📌 Padrões mais frequentes de **Linhas** (top 5)")
                for padrao, freq in freq_linhas.most_common(5):
                    st.write(f"{padrao} → {freq} vezes")

                st.markdown("### 📌 Padrões mais frequentes de **Colunas** (top 5)")
                for padrao, freq in freq_colunas.most_common(5):
                    st.write(f"{padrao} → {freq} vezes")

                st.markdown("### 🎯 Padrões futuros sugeridos (5 combinações)")
                futuros = sugerir_padroes_futuros(freq_linhas, freq_colunas, n=5)
                for i, p in enumerate(futuros, 1):
                    st.write(f"**Padrão Futuro {i}:** Linhas {p['linhas']} | Colunas {p['colunas']}")

    # Aba 6 - Conferência (antiga 5)
    with abas[5]:
        st.subheader("🎯 Conferência de Cartões")
        if st.session_state.info_ultimo_concurso:
            info = st.session_state.info_ultimo_concurso
            st.markdown(
                f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                unsafe_allow_html=True
            )
            if st.button("🔍 Conferir agora"):
                for i, cartao in enumerate(st.session_state.cartoes_gerados,1):
                    acertos = len(set(cartao) & set(info['dezenas']))
                    st.write(f"Jogo {i}: {cartao} - **{acertos} acertos**")
                if st.session_state.cartoes_gerados_padrao:
                    st.markdown("**Cartões por Padrões:**")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados_padrao,1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")

    # Aba 7 - Conferir Arquivo TXT (antiga 6)
    with abas[6]:
        st.subheader("📤 Conferir Cartões de um Arquivo TXT")
        uploaded_file = st.file_uploader("Faça upload do arquivo TXT com os cartões (15 dezenas separadas por vírgula)", type="txt")
        if uploaded_file:
            linhas = uploaded_file.read().decode("utf-8").splitlines()
            cartoes_txt = []
            for linha in linhas:
                try:
                    dezenas = sorted([int(x) for x in linha.strip().split(",")])
                    if len(dezenas) == 15 and all(1 <= x <= 25 for x in dezenas):
                        cartoes_txt.append(dezenas)
                except:
                    continue

            if cartoes_txt:
                st.success(f"{len(cartoes_txt)} cartões carregados com sucesso.")
                if st.session_state.info_ultimo_concurso:
                    info = st.session_state.info_ultimo_concurso
                    st.markdown(
                        f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                        unsafe_allow_html=True
                    )
                    if st.button("📊 Conferir Cartões do Arquivo"):
                        for i, cartao in enumerate(cartoes_txt,1):
                            acertos = len(set(cartao) & set(info['dezenas']))
                            st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
            else:
                st.warning("Nenhum cartão válido foi encontrado no arquivo.")

st.markdown("<hr><p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
