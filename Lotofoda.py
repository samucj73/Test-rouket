import streamlit as st
import requests
import numpy as np
import pandas as pd

st.set_page_config(page_title="Lotofácil - Visualização 5x5", layout="centered")

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
# Extrai distribuição de linhas e colunas
# =========================
def extrair_distribuicao(jogo):
    linhas = [[i for i in range(l*5+1, l*5+6)] for l in range(5)]
    colunas = [[i for i in range(c+1, 26, 5)] for c in range(5)]
    dist_linhas = [sum(1 for n in jogo if n in linha) for linha in linhas]
    dist_colunas = [sum(1 for n in jogo if n in coluna) for coluna in colunas]
    return tuple(dist_linhas), tuple(dist_colunas)

# =========================
# Encontra médias por linha e coluna
# =========================
def medias_linha_coluna(concursos):
    tot_linhas = np.zeros(5)
    tot_colunas = np.zeros(5)
    for jogo in concursos:
        dl, dc = extrair_distribuicao(jogo)
        tot_linhas += np.array(dl)
        tot_colunas += np.array(dc)
    media_linhas = np.round(tot_linhas / len(concursos)).astype(int)
    media_colunas = np.round(tot_colunas / len(concursos)).astype(int)
    # Ajusta para soma 15
    while media_linhas.sum() > 15:
        idx = np.argmax(media_linhas)
        media_linhas[idx] -= 1
    while media_linhas.sum() < 15:
        idx = np.argmin(media_linhas)
        media_linhas[idx] += 1
    return media_linhas, media_colunas

# =========================
# Gera jogos aleatórios baseados nas médias
# =========================
def gerar_jogos(concursos, qtd_jogos=10):
    linhas = [[i for i in range(l*5+1, l*5+6)] for l in range(5)]
    colunas = [[i for i in range(c+1, 26, 5)] for c in range(5)]
    
    media_linhas, media_colunas = medias_linha_coluna(concursos)
    
    jogos = []
    for _ in range(qtd_jogos):
        dezenas = []
        for l, qtd in enumerate(media_linhas):
            dezenas += list(np.random.choice(linhas[l], qtd, replace=False))
        dezenas = dezenas[:15]
        for c, qtd in enumerate(media_colunas):
            faltando = qtd - sum(1 for n in dezenas if n in colunas[c])
            if faltando > 0:
                candidatos = [n for n in colunas[c] if n not in dezenas]
                if candidatos:
                    dezenas += list(np.random.choice(candidatos, min(faltando, len(candidatos)), replace=False))
        if len(dezenas) < 15:
            resto = [n for n in range(1,26) if n not in dezenas]
            dezenas += list(np.random.choice(resto, 15-len(dezenas), replace=False))
        jogos.append(sorted(dezenas[:15]))
    return jogos

# =========================
# Converte jogo em matriz 5x5
# =========================
def jogo_para_matriz(jogo):
    matriz = np.array([[l*5 + c + 1 for c in range(5)] for l in range(5)])
    df = pd.DataFrame(matriz)
    # Destaca os números do jogo
    df_styled = df.style.applymap(lambda x: 'background-color: yellow; font-weight:bold' if x in jogo else '')
    return df_styled

# =========================
# APP STREAMLIT
# =========================
st.title("🎯 Lotofácil - Visualização 5x5")

qtd_concursos = st.slider("Quantidade de concursos para análise:", 50, 500, 200)
concursos = capturar_ultimos_resultados(qtd_concursos)

if concursos:
    qtd_jogos = st.slider("Quantos jogos deseja gerar?", 1, 10, 5)
    jogos = gerar_jogos(concursos, qtd_jogos)

    st.subheader("🎲 Jogos Gerados")
    for i, jogo in enumerate(jogos, 1):
        st.write(f"**Jogo {i}: {jogo}**")
        st.dataframe(jogo_para_matriz(jogo))
