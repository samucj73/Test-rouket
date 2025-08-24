import streamlit as st
import requests
import numpy as np
import random
from sklearn.ensemble import RandomForestClassifier

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
# IA e Features
# =========================
class LotoFacilIA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2,3,5,7,11,13,17,19,23}
        self.model = RandomForestClassifier(n_estimators=200, random_state=42)
        self.X = self.matriz_binaria()
        self.Y = self.X.copy()  # Multi-label
        if len(self.X) > 1:
            self.treinar_modelo()

    def matriz_binaria(self):
        return np.array([[1 if n in jogo else 0 for n in self.numeros] for jogo in self.concursos])

    def frequencia(self, janela=50):
        freq = {n:0 for n in self.numeros}
        for jogo in self.concursos[-janela:]:
            for d in jogo:
                freq[d] += 1
        return freq

    def atraso(self):
        atraso = {n:0 for n in self.numeros}
        for i in range(len(self.concursos)-1, -1, -1):
            jogo = self.concursos[i]
            for n in self.numeros:
                if atraso[n] == 0 and n not in jogo:
                    atraso[n] = len(self.concursos) - i
        return atraso

    def quentes_frios(self, top=10):
        freq = self.frequencia()
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        quentes = [n for n,_ in numeros_ordenados[:top]]
        frios = [n for n,_ in numeros_ordenados[-top:]]
        return {"quentes": quentes, "frios": frios}

    def pares_impares_primos(self):
        pares = sum(1 for n in self.concursos[-1] if n %2==0)
        impares = 15 - pares
        primos = sum(1 for n in self.concursos[-1] if n in self.primos)
        return {"pares": pares, "impares": impares, "primos": primos}

    def treinar_modelo(self):
        X_train = self.X[:-1]
        Y_train = self.Y[1:]
        self.model.fit(X_train, Y_train)

    def prever_proximo(self):
        ultima = self.X[-1].reshape(1,-1)
        probs_list = self.model.predict_proba(ultima)
        probabilidades = {n+1: probs_list[n][0][1] for n in range(25)}
        return probabilidades

    def gerar_5_jogos(self, probabilidades):
        top15 = [n for n,_ in sorted(probabilidades.items(), key=lambda x: x[1], reverse=True)[:15]]
        top20 = [n for n,_ in sorted(probabilidades.items(), key=lambda x: x[1], reverse=True)[:20]]
        mid = [n for n,_ in sorted(probabilidades.items(), key=lambda x: x[1])[10:20]]
        frios = [n for n,_ in sorted(probabilidades.items(), key=lambda x: x[1])[:10]]

        jogos = []
        # Jogo 1: top15
        jogos.append(sorted(top15))
        # Jogo 2: top10 + 5 do meio
        jogos.append(sorted(top15[:10] + random.sample(mid, 5)))
        # Jogo 3: top12 + 3 frios
        jogos.append(sorted(top15[:12] + random.sample(frios, 3)))
        # Jogo 4: equilíbrio pares/ímpares
        jogos.append(self._equilibrado(top20))
        # Jogo 5: equilíbrio pares/ímpares + primos
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
# Sessão Streamlit
# =========================
if "concursos" not in st.session_state:
    st.session_state.concursos = []

if "cartoes_gerados" not in st.session_state:
    st.session_state.cartoes_gerados = []

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

    abas = st.tabs(["📊 Estatísticas", "🧠 Gerar Cartões", "✅ Conferência", "📤 Conferir Arquivo TXT"])

    # --- Aba 1 ---
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Números quentes: {quentes_frios['quentes']}")
        st.write(f"Números frios: {quentes_frios['frios']}")
        st.write(f"Pares/Ímpares/Primos último concurso: {pares_impares_primos}")
        st.write(f"Frequência últimos 50 concursos: {ia.frequencia()}")
        st.write(f"Atraso de cada número: {ia.atraso()}")

    # --- Aba 2 ---
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

    # --- Aba 3 ---
    with abas[2]:
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

    # --- Aba 4 ---
    with abas[3]:
        st.subheader("📤 Conferir Cartões de um Arquivo TXT")
        uploaded_file = st.file_uploader("Faça upload do arquivo TXT com os cartões (formato: 15 dezenas separadas por vírgula)", type="txt")
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
                            acertos = len(set(cartao) & set(info['dezenas
