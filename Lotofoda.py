import streamlit as st
import requests
import numpy as np
import random
from catboost import CatBoostClassifier

st.set_page_config(page_title="Lotofácil Inteligente", layout="centered")

# =========================
# Captura concursos via API
# =========================
def capturar_ultimos_resultados(qtd=250):
    url_base = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
    concursos = []

    try:
        resp = requests.get(url_base)
        if resp.status_code != 200:
            st.error("Erro ao buscar o último concurso.")
            return [], None

        dados = resp.json()
        ultimo = dados[0] if isinstance(dados, list) else dados
        numero_atual = int(ultimo.get("concurso"))
        data_concurso = ultimo.get("data")
        dezenas = sorted([int(d) for d in ultimo.get("dezenas")])
        concursos.append(dezenas)
        info_ultimo = {"numero": numero_atual, "data": data_concurso, "dezenas": dezenas}

        for i in range(1, qtd):
            concurso_numero = numero_atual - i
            resp = requests.get(f"{url_base}{concurso_numero}")
            if resp.status_code == 200:
                dados = resp.json()
                data = dados[0] if isinstance(dados, list) else dados
                dezenas = sorted([int(d) for d in data.get("dezenas")])
                concursos.append(dezenas)
            else:
                break
        return concursos, info_ultimo

    except Exception as e:
        st.error(f"Erro ao acessar API: {e}")
        return [], None

# =========================
# Classe IA / Análise
# =========================
class LotoFacilIA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}
        self.models = {}
        self.X = self.gerar_features()[:-1]
        self.Y = self.matriz_binaria()[1:]
        if len(self.X) > 0:
            self.treinar_modelos()

    def matriz_binaria(self):
        return np.array([[1 if n in jogo else 0 for n in self.numeros] for jogo in self.concursos])

    def frequencia(self, janela=50):
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
        max_atraso = len(self.concursos)-1
        for n in atraso:
            if atraso[n]==0:
                atraso[n] = max_atraso
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

    def gerar_features(self):
        features = []
        freq = self.frequencia(janela=len(self.concursos)-1)
        atraso = self.atraso()
        for jogo in self.concursos:
            f = []
            for n in self.numeros:
                f.append(1 if n in jogo else 0)
                f.append(freq[n])
                f.append(atraso[n])
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
        ultima = self.gerar_features()[-1].reshape(1,-1)
        probabilidades = {}
        for n in self.numeros:
            prob = self.models[n].predict_proba(ultima)[0][1]
            probabilidades[n] = prob
        return probabilidades

    def gerar_cartoes_por_linha_coluna(self, n_jogos=5, janela=50):
        ultimos = self.concursos[-janela:]
        padroes_linhas = [0]*5
        padroes_colunas = [0]*5
        for jogo in ultimos:
            for n in jogo:
                linha = (n-1)//5
                coluna = (n-1)%5
                padroes_linhas[linha] += 1
                padroes_colunas[coluna] += 1
        media_linhas = [max(1, int(round(c/len(ultimos)))) for c in padroes_linhas]
        media_colunas = [max(1, int(round(c/len(ultimos)))) for c in padroes_colunas]
        jogos = []
        tentativas_max = 1000
        while len(jogos) < n_jogos and tentativas_max > 0:
            cartao = set()
            linhas_atuais = [0]*5
            colunas_atuais = [0]*5
            while len(cartao) < 15:
                n = random.randint(1,25)
                linha = (n-1)//5
                coluna = (n-1)%5
                if linhas_atuais[linha] < media_linhas[linha] and colunas_atuais[coluna] < media_colunas[coluna]:
                    cartao.add(n)
                    linhas_atuais[linha] += 1
                    colunas_atuais[coluna] += 1
            cartao_sorted = tuple(sorted(cartao))
            if cartao_sorted not in jogos:
                jogos.append(cartao_sorted)
            tentativas_max -= 1
        return [list(c) for c in jogos]

# =========================
# Streamlit Interface
# =========================
st.title("Lotofácil Inteligente 🎯")

if "concursos" not in st.session_state:
    st.session_state.concursos = []
if "cartoes_gerados" not in st.session_state:
    st.session_state.cartoes_gerados = []
if "cartoes_linha_coluna" not in st.session_state:
    st.session_state.cartoes_linha_coluna = []
if "info_ultimo_concurso" not in st.session_state:
    st.session_state.info_ultimo_concurso = None

# Captura concursos
with st.expander("📥 Capturar Concursos"):
    qtd_concursos = st.slider("Quantidade de concursos para análise", 10, 250, 100)
    if st.button("🔄 Capturar Agora"):
        with st.spinner("Capturando concursos..."):
            concursos, info = capturar_ultimos_resultados(qtd_concursos)
            if concursos:
                st.session_state.concursos = concursos
                st.session_state.info_ultimo_concurso = info
                st.success(f"{len(concursos)} concursos capturados com sucesso!")

# Interface principal
if st.session_state.concursos:
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    cartoes_gerados = ia.gerar_cartoes_por_linha_coluna(5)

    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões", 
        "📐 Linha×Coluna", 
        "✅ Conferência", 
        "📤 Conferir TXT"
    ])

    # Aba Estatísticas
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Números quentes: {ia.quentes_frios()['quentes']}")
        st.write(f"Números frios: {ia.quentes_frios()['frios']}")
        st.write(f"Pares/Ímpares/Primos último concurso: {ia.pares_impares_primos()}")
        st.write(f"Frequência últimos 50 concursos (excluindo último): {ia.frequencia()}")
        st.write(f"Atraso de cada número (excluindo último concurso): {ia.atraso()}")

    # Aba Gerar Cartões
    with abas[1]:
        st.subheader("🧾 Cartões Inteligentes")
        if st.button("🚀 Gerar 5 Cartões"):
            st.session_state.cartoes_gerados = cartoes_gerados
            st.success("5 Cartões gerados!")
        if st.session_state.cartoes_gerados:
            for i, c in enumerate(st.session_state.cartoes_gerados,1):
                st.write(f"Cartão {i}: {c}")

    # Aba Linha×Coluna
    with abas[2]:
        st.subheader("📐 Linha×Coluna")
        if st.button("🚀 Gerar 5 Cartões Linha×Coluna"):
            lc = ia.gerar_cartoes_por_linha_coluna()
            st.session_state.cartoes_linha_coluna = lc
            st.success("5 Cartões Linha×Coluna gerados!")
        if st.session_state.cartoes_linha_coluna:
            for i, c in enumerate(st.session_state.cartoes_linha_coluna,1):
                st.write(f"Cartão {i}: {c}")

    # Aba Conferência
    with abas[3]:
        st.subheader("🎯 Conferência de Cartões")
        info = st.session_state.info_ultimo_concurso
        if info:
            st.markdown(f"Último Concurso #{info['numero']} ({info['data']}): {info['dezenas']}")
            if st.button("🔍 Conferir agora"):
                for i, cartao in enumerate(st.session_state.cartoes_gerados,1):
                    acertos = len(set(cartao) & set(info['dezenas']))
                    st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
                for i, cartao in enumerate(st.session_state.cartoes_linha_coluna,1):
                    acertos = len(set(cartao) & set(info['dezenas']))
                    st.write(f"Cartão LC {i}: {cartao} - **{acertos} acertos**")

    # Aba Conferir TXT
    with abas[4]:
        st.subheader("📤 Conferir Arquivo TXT")
        uploaded_file = st.file_uploader("Arquivo TXT com cartões (15 dezenas)", type="txt")
        if uploaded_file:
            linhas = uploaded_file.read().decode("utf-8").splitlines()
            cartoes_txt = []
            for linha in linhas:
                try:
                    dezenas = sorted([int(x) for x in linha.strip().split(",")])
                    if len(dezenas)==15 and all(1<=x<=25 for x in dezenas):
                        cartoes_txt.append(dezenas)
                except:
                    continue
            if cartoes_txt:
                st.success(f"{len(cartoes_txt)} cartões carregados")
                st.write(cartoes_txt)
