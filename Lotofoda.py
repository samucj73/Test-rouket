import streamlit as st
import requests
import random
import pandas as pd

# =====================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================
st.set_page_config(
    page_title="⚡ LOTOFÁCIL - ESTRATÉGIA AGRESSIVA 2024",
    layout="wide"
)

# =====================================================
# CLASSE PRINCIPAL
# =====================================================
class EstrategiaAgressiva2024:
    def __init__(self, concursos):
        self.concursos_historicos = concursos[1:] if len(concursos) > 1 else []
        self.ultimo_concurso = concursos[0] if concursos else []
        self.numeros = list(range(1, 26))

        self.top_dezenas = [
            24, 13, 22, 25, 10,
            20, 1, 11, 5, 14,
            23, 21, 4, 15, 2
        ]

        self.pares_fortes = [
            (24, 25), (13, 14), (22, 23), (10, 11), (20, 21),
            (1, 2), (4, 5), (15, 16), (17, 18), (7, 8)
        ]

        self.trios_fortes = [
            (24, 25, 13), (22, 23, 24), (10, 11, 12),
            (20, 21, 22), (1, 2, 3),
            (13, 14, 15), (5, 10, 15)
        ]

    # =================================================
    # FILTROS ESTATÍSTICOS
    # =================================================
    def _filtro_estatistico(self, jogo):
        pares = sum(1 for n in jogo if n % 2 == 0)
        soma = sum(jogo)
        if pares < 6 or pares > 9:
            return False
        if soma < 170 or soma > 235:
            return False
        return True

    def _controle_diversidade(self, jogo, jogos):
        for j in jogos:
            if len(set(jogo) & set(j)) > 11:
                return False
        return True

    # =================================================
    # ESTRATÉGIA 1 – REPETIÇÃO REAL
    # =================================================
    def estrategia_repeticao_real(self, n_jogos=15):
        jogos = []
        ultimo = self.ultimo_concurso

        for _ in range(n_jogos * 2):
            jogo = random.sample(ultimo, random.choice([8, 9, 10]))

            for n in self.top_dezenas:
                if n not in jogo and len(jogo) < 15:
                    jogo.append(n)

            while len(jogo) < 15:
                n = random.choice(self.numeros)
                if n not in jogo:
                    jogo.append(n)

            jogo = sorted(jogo)

            if (
                len(set(jogo) & set(ultimo)) >= 8 and
                self._filtro_estatistico(jogo) and
                self._controle_diversidade(jogo, jogos)
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # =================================================
    # ESTRATÉGIA 2 – PARES FORTES
    # =================================================
    def estrategia_pares_fortes(self, n_jogos=15):
        jogos = []

        for _ in range(n_jogos * 2):
            jogo = set()

            for par in random.sample(self.pares_fortes, random.randint(5, 7)):
                jogo.update(par)

            while len(jogo) < 15:
                jogo.add(random.choice(self.top_dezenas))

            jogo = sorted(jogo)

            if (
                self._filtro_estatistico(jogo) and
                self._controle_diversidade(jogo, jogos)
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # =================================================
    # ESTRATÉGIA 3 – TRIOS PODEROSOS
    # =================================================
    def estrategia_trios_poderosos(self, n_jogos=15):
        jogos = []

        for _ in range(n_jogos * 2):
            jogo = set()

            for trio in random.sample(self.trios_fortes, random.randint(3, 4)):
                jogo.update(trio)

            while len(jogo) < 15:
                jogo.add(random.choice(self.top_dezenas))

            jogo = sorted(jogo)

            if (
                self._filtro_estatistico(jogo) and
                self._controle_diversidade(jogo, jogos)
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # =================================================
    # ESTRATÉGIA 4 – PESQUISA 2024
    # =================================================
    def estrategia_pesquisa_2024(self, n_jogos=15):
        jogos = []
        ultimo = self.ultimo_concurso

        for _ in range(n_jogos * 2):
            jogo = random.sample(ultimo, random.choice([8, 9, 10]))

            for n in self.top_dezenas:
                if n not in jogo and len(jogo) < 15:
                    jogo.append(n)

            while len(jogo) < 15:
                jogo.append(random.choice(self.numeros))

            jogo = sorted(set(jogo))

            if (
                len(set(jogo) & set(ultimo)) >= 7 and
                self._filtro_estatistico(jogo) and
                self._controle_diversidade(jogo, jogos)
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # =================================================
    # ESTRATÉGIA 5 – AGRESSIVA TOTAL
    # =================================================
    def estrategia_agressiva_total(self, n_jogos=15):
        jogos = []
        ultimo = self.ultimo_concurso

        for _ in range(n_jogos * 3):
            jogo = set(random.sample(ultimo, random.choice([9, 10])))

            for n in self.top_dezenas[:12]:
                if len(jogo) < 15:
                    jogo.add(n)

            jogo = sorted(jogo)

            if (
                len(set(jogo) & set(ultimo)) >= 8 and
                self._filtro_estatistico(jogo) and
                self._controle_diversidade(jogo, jogos)
            ):
                jogos.append(jogo)

            if len(jogos) >= n_jogos:
                break

        return jogos

    # =================================================
    # CONFERÊNCIA DOS JOGOS
    # =================================================
    def conferir_jogos(self, jogos):
        resultado = self.ultimo_concurso
        dados = []

        for idx, jogo in enumerate(jogos, start=1):
            acertos = len(set(jogo) & set(resultado))
            dados.append({
                "Jogo": idx,
                "Dezenas": jogo,
                "Acertos": acertos
            })

        return dados

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
def main():
    st.title("⚡ LOTOFÁCIL - ESTRATÉGIA AGRESSIVA 2024")

    if "concursos" not in st.session_state:
        st.session_state.concursos = []

    if "jogos" not in st.session_state:
        st.session_state.jogos = []

    with st.sidebar:
        qtd = st.slider("Quantidade de concursos", 20, 300, 100, 10)

        if st.button("🔄 Carregar concursos"):
            url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
            resposta = requests.get(url).json()

            concursos = []
            for i in range(min(qtd, len(resposta))):
                concursos.append(sorted(map(int, resposta[i]["dezenas"])))

            st.session_state.concursos = concursos
            st.success(f"{len(concursos)} concursos carregados")

    if st.session_state.concursos:
        estrategia = EstrategiaAgressiva2024(st.session_state.concursos)

        escolha = st.selectbox(
            "Escolha a estratégia",
            [
                "Repetição Real",
                "Pares Fortes",
                "Trios Poderosos",
                "Pesquisa 2024",
                "Agressiva Total"
            ]
        )

        quantidade = st.number_input("Quantidade de jogos", 5, 50, 15)

        if st.button("🚀 Gerar jogos"):
            mapa = {
                "Repetição Real": estrategia.estrategia_repeticao_real,
                "Pares Fortes": estrategia.estrategia_pares_fortes,
                "Trios Poderosos": estrategia.estrategia_trios_poderosos,
                "Pesquisa 2024": estrategia.estrategia_pesquisa_2024,
                "Agressiva Total": estrategia.estrategia_agressiva_total
            }

            st.session_state.jogos = mapa[escolha](quantidade)

    if st.session_state.jogos:
        st.subheader("📋 Jogos Gerados")
        st.dataframe(pd.DataFrame(st.session_state.jogos))

        st.subheader("🎯 Conferência com o último concurso")
        resultado = estrategia.conferir_jogos(st.session_state.jogos)
        df = pd.DataFrame(resultado)
        st.dataframe(df, use_container_width=True)

        st.subheader("📊 Resumo de acertos")
        st.write(df["Acertos"].value_counts().sort_index())

# =====================================================
# EXECUÇÃO
# =====================================================
if __name__ == "__main__":
    main()
