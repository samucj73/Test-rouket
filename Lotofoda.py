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

        info_ultimo = {
            "numero": numero_atual,
            "data": data_concurso,
            "dezenas": dezenas
        }

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
# IA Avançada com CatBoost
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
        ultima = self.gerar_features()[-1].reshape(1,-1)
        probabilidades = {}
        for n in self.numeros:
            prob = self.models[n].predict_proba(ultima)[0][1]
            probabilidades[n] = prob
        return probabilidades

    def gerar_5_jogos(self, probabilidades):
        top15 = [n for n,_ in sorted(probabilidades.items(), key=lambda x:x[1], reverse=True)[:15]]
        top20 = [n for n,_ in sorted(probabilidades.items(), key=lambda x:x[1], reverse=True)[:20]]
        mid = [n for n,_ in sorted(probabilidades.items(), key=lambda x:x[1])[10:20]]
        frios = [n for n,_ in sorted(probabilidades.items(), key=lambda x:x[1])[:10]]

        jogos=[]
        jogos.append(sorted(top15))
        jogos.append(sorted(top15[:10] + random.sample(mid,5)))
        jogos.append(sorted(top15[:12] + random.sample(frios,3)))
        jogos.append(self._equilibrado(top20))
        jogos.append(self._equilibrado(top20, forcar_primos=True))
        return jogos

    def _equilibrado(self, base, forcar_primos=False):
        while True:
            cartao = sorted(random.sample(base,15))
            pares = sum(1 for n in cartao if n%2==0)
            primos_count = sum(1 for n in cartao if n in self.primos)
            if 7 <= pares <=10 and (not forcar_primos or primos_count>=3):
                return cartao

    # =========================
    # Novo: Gerar 5 cartões por linha x coluna
    # =========================
# Novo método: calcular padrões linha×coluna
    def calcular_padroes_linha_coluna(self, janela=50):
        ultimos = self.concursos[-janela:]
        padroes_linhas = [0]*5
        padroes_colunas = [0]*5

        for jogo in ultimos:
            for n in jogo:
                linha = (n-1)//5
                coluna = (n-1)%5
                padroes_linhas[linha] += 1
                padroes_colunas[coluna] += 1

        media_linhas = [max(1, round(c/len(ultimos),2)) for c in padroes_linhas]
        media_colunas = [max(1, round(c/len(ultimos),2)) for c in padroes_colunas]

        return media_linhas, media_colunas

    # Novo método melhorado: geração distinta por linha×coluna
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
# Streamlit
# =========================
if "concursos" not in st.session_state:
    st.session_state.concursos = []

if "cartoes_gerados" not in st.session_state:
    st.session_state.cartoes_gerados = []

if "cartoes_linha_coluna" not in st.session_state:
    st.session_state.cartoes_linha_coluna = []

if "info_ultimo_concurso" not in st.session_state:
    st.session_state.info_ultimo_concurso = None

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

# --- Abas principais ---
if st.session_state.concursos:
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    jogos_gerados = ia.gerar_5_jogos(probs)
    quentes_frios = ia.quentes_frios()
    pares_impares_primos = ia.pares_impares_primos()

    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões", 
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

    # Aba 3 - Padrões Linha×Coluna
    with abas[2]:
        st.subheader("📐 Geração de Cartões por Padrões Linha×Coluna")
        if st.button("🚀 Gerar 5 Cartões por Linha×Coluna"):
            cartoes_lc = ia.gerar_cartoes_por_linha_coluna()
            st.session_state.cartoes_linha_coluna = cartoes_lc
            st.success("5 Cartões por Linha×Coluna gerados com sucesso!")

        if st.session_state.cartoes_linha_coluna:
            for i, c in enumerate(st.session_state.cartoes_linha_coluna,1):
                st.write(f"Cartão {i}: {c}")

            st.subheader("📁 Exportar Cartões Linha×Coluna para TXT")
            conteudo_lc = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_linha_coluna)
            st.download_button("💾 Baixar Arquivo Linha×Coluna", data=conteudo_lc, file_name="cartoes_linha_coluna_lotofacil.txt", mime="text/plain")

    # Aba 4 - Conferência
    with abas[3]:
        st.subheader("🎯 Conferência de Cartões")
        if st.session_state.info_ultimo_concurso:
            info = st.session_state.info_ultimo_concurso
            st.markdown(
                f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                unsafe_allow_html=True
            )
            if st.button("🔍 Conferir agora"):
                # Conferir cartões inteligentes
                for i, cartao in enumerate(st.session_state.cartoes_gerados,1):
                    acertos = len(set(cartao) & set(info['dezenas']))
                    st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
                # Conferir cartões linha×coluna
                if st.session_state.cartoes_linha_coluna:
                    st.markdown("**Cartões Linha×Coluna:**")
                    for i, cartao in enumerate(st.session_state.cartoes_linha_coluna,1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")

    # Aba 5 - Conferir Arquivo TXT
    with abas[4]:
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
