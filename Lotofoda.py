import streamlit as st
import requests
from collections import Counter

# =========================
# FUNÇÕES AUXILIARES
# =========================

# Linhas e colunas fixas da Lotofácil
linhas = [
    list(range(1, 6)),
    list(range(6, 11)),
    list(range(11, 16)),
    list(range(16, 21)),
    list(range(21, 26))
]

colunas = [
    list(range(1, 26, 5)),
    list(range(2, 26, 5)),
    list(range(3, 26, 5)),
    list(range(4, 26, 5)),
    list(range(5, 26, 5))
]

def capturar_ultimos_resultados(qtd=100):
    """Captura os últimos resultados da Lotofácil"""
    url_base = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
    concursos = []
    try:
        resp = requests.get(url_base)
        if resp.status_code != 200:
            return []
        dados = resp.json()
        ultimo_numero = int(dados[0]['concurso'])
        for i in range(qtd):
            resp = requests.get(f"{url_base}{ultimo_numero - i}")
            if resp.status_code == 200:
                data = resp.json()[0]
                dezenas = [int(d) for d in data['dezenas']]
                concursos.append(dezenas)
    except Exception as e:
        st.error(f"Erro ao capturar resultados: {e}")
    return concursos

def contar_padroes(concursos):
    """Conta os padrões de linhas e colunas"""
    padrao_linhas = []
    padrao_colunas = []

    for concurso in concursos:
        linha_cont = [sum(1 for n in concurso if n in l) for l in linhas]
        col_cont = [sum(1 for n in concurso if n in c) for c in colunas]
        padrao_linhas.append(tuple(linha_cont))
        padrao_colunas.append(tuple(col_cont))

    freq_linhas = Counter(padrao_linhas)
    freq_colunas = Counter(padrao_colunas)
    return freq_linhas, freq_colunas

def gerar_padroes_futuros(freq_linhas, freq_colunas, n=5):
    """Gera n padrões futuros combinando os mais frequentes"""
    padroes_linhas = [p for p, _ in freq_linhas.most_common(n)]
    padroes_colunas = [p for p, _ in freq_colunas.most_common(n)]
    futuros = []
    for i in range(n):
        futuros.append({
            "linhas": padroes_linhas[i % len(padroes_linhas)],
            "colunas": padroes_colunas[i % len(padroes_colunas)]
        })
    return futuros

# =========================
# APP STREAMLIT
# =========================

st.set_page_config(page_title="Sistema Lotofácil", layout="wide")

# Menu lateral
menu = st.sidebar.radio("Navegar", [
    "Início",
    "Gerar Cartões",
    "Estatísticas",
    "Padrões Linha×Coluna"  # <- nova aba adicionada
])

# =========================
# CONTEÚDO DAS ABAS
# =========================

if menu == "Início":
    st.title("📊 Sistema de Análise da Lotofácil")
    st.write("Bem-vindo! Escolha uma aba no menu lateral.")

elif menu == "Gerar Cartões":
    st.title("🃏 Gerar Cartões")
    st.write("Aqui entra sua lógica já existente para geração de cartões.")

elif menu == "Estatísticas":
    st.title("📈 Estatísticas")
    st.write("Aqui você mantém suas estatísticas atuais.")

elif menu == "Padrões Linha×Coluna":
    st.title("🔢 Padrões de Linhas × Colunas")
    st.write("Análise de concursos anteriores para detectar padrões de linhas e colunas.")

    qtd = st.slider("Quantidade de concursos para analisar", 50, 500, 100, 10)

    if st.button("🔍 Analisar Padrões"):
        concursos = capturar_ultimos_resultados(qtd)
        if not concursos:
            st.error("Não foi possível capturar concursos.")
        else:
            freq_linhas, freq_colunas = contar_padroes(concursos)

            st.subheader("📌 Padrões mais frequentes de Linhas")
            for padrao, freq in freq_linhas.most_common(5):
                st.write(f"{padrao} → {freq} vezes")

            st.subheader("📌 Padrões mais frequentes de Colunas")
            for padrao, freq in freq_colunas.most_common(5):
                st.write(f"{padrao} → {freq} vezes")

            st.subheader("🎯 Padrões futuros sugeridos")
            futuros = gerar_padroes_futuros(freq_linhas, freq_colunas)
            for i, p in enumerate(futuros, 1):
                st.write(f"**Padrão Futuro {i}:** Linhas {p['linhas']} | Colunas {p['colunas']}")
