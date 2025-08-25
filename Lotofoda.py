import streamlit as st
import requests
import numpy as np
from collections import Counter

st.set_page_config(page_title="Lotofácil - Padrões Linha x Coluna", layout="centered")

# =========================
# Captura concursos via API
# =========================
def capturar_ultimos_resultados(qtd=250):
    url_base = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
    concursos = []
    for i in range(1, qtd+1):
        try:
            resp = requests.get(f"{url_base}{i}", timeout=10)
            if resp.status_code == 200:
                dados = resp.json()
                if "dezenas" in dados:
                    dezenas = [int(d) for d in dados["dezenas"]]
                    concursos.append(dezenas)
        except:
            pass
    return concursos

# =========================
# Pega padrão (linhas e colunas)
# =========================
def extrair_padrao(jogo):
    linhas = [[i for i in range(l*5+1, l*5+6)] for l in range(5)]
    colunas = [[i for i in range(c+1, 26, 5)] for c in range(5)]
    dist_linha = [sum(1 for n in jogo if n in linha) for linha in linhas]
    dist_coluna = [sum(1 for n in jogo if n in coluna) for coluna in colunas]
    return tuple(dist_linha), tuple(dist_coluna)

# =========================
# Identifica padrões mais comuns
# =========================
def encontrar_padroes(concursos, top=10):
    padroes = []
    for jogo in concursos:
        pl, pc = extrair_padrao(jogo)
        padroes.append((pl, pc))
    contagem = Counter(padroes)
    return contagem.most_common(top)

# =========================
# Gera jogos baseado nos padrões mais comuns
# =========================
def gerar_jogos(concursos, qtd_jogos=10):
    padroes_comuns = encontrar_padroes(concursos, top=10)
    linhas = [[i for i in range(l*5+1, l*5+6)] for l in range(5)]
    colunas = [[i for i in range(c+1, 26, 5)] for c in range(5)]
    
    jogos = []
    for _ in range(qtd_jogos):
        # escolhe um padrão real
        (pl, pc), _ = padroes_comuns[np.random.randint(len(padroes_comuns))]
        
        dezenas = []
        # aplica distribuição por linha
        for i, linha in enumerate(linhas):
            qtd = min(pl[i], len(linha))
            dezenas += list(np.random.choice(linha, qtd, replace=False))
        # corrige excesso
        dezenas = dezenas[:15]
        # aplica ajuste por colunas (se faltar algum)
        for i, coluna in enumerate(colunas):
            faltando = pc[i] - sum(1 for n in dezenas if n in coluna)
            if faltando > 0:
                candidatos = [n for n in coluna if n not in dezenas]
                if candidatos:
                    dezenas += list(np.random.choice(candidatos, min(faltando, len(candidatos)), replace=False))
        jogos.append(sorted(dezenas[:15]))
    return jogos, padroes_comuns

# =========================
# APP STREAMLIT
# =========================
st.title("🎯 Lotofácil - Padrões de Interseção Linha x Coluna")

qtd_concursos = st.slider("Quantidade de concursos para análise:", 50, 500, 200)
concursos = capturar_ultimos_resultados(qtd_concursos)

if concursos:
    qtd_jogos = st.slider("Quantos jogos deseja gerar?", 1, 20, 10)
    jogos, padroes = gerar_jogos(concursos, qtd_jogos)

    st.subheader("📊 Padrões mais comuns")
    for (pl, pc), freq in padroes:
        st.write(f"Linhas {pl} | Colunas {pc} → {freq} vezes")

    st.subheader("🎲 Jogos Gerados")
    for i, jogo in enumerate(jogos, 1):
        st.write(f"Jogo {i}: {jogo}")
