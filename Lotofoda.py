import streamlit as st
import requests
import random
import numpy as np
from collections import Counter

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
# Classe de Estatísticas
# =========================
class LotoFacilStats:
    def __init__(self, concursos):
        self.concursos = concursos[:-1]  # excluir o último
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}

    def frequencia_numeros(self):
        freq = {n:0 for n in self.numeros}
        for jogo in self.concursos:
            for n in jogo:
                freq[n] +=1
        return freq

    def soma_media(self):
        return np.mean([sum(j) for j in self.concursos])

    def pares_impares_distribuicao(self):
        pares = [sum(1 for n in j if n%2==0) for j in self.concursos]
        impares = [15-p for p in pares]
        return {"pares": np.mean(pares), "impares": np.mean(impares)}

    def numeros_consecutivos(self):
        total = 0
        for j in self.concursos:
            count = 1
            max_count = 1
            for i in range(1,len(j)):
                if j[i] == j[i-1]+1:
                    count +=1
                    max_count = max(max_count,count)
                else:
                    count =1
            total += max_count
        return total / len(self.concursos)

    def grupos_distribuicao(self):
        grupos = {1:0,2:0,3:0,4:0,5:0}
        for j in self.concursos:
            for n in j:
                g = (n-1)//5 +1
                grupos[g] +=1
        for k in grupos:
            grupos[k] /= len(self.concursos)
        return grupos

    def numeros_quentes_frios(self, top=10):
        freq = self.frequencia_numeros()
        ordenado = sorted(freq.items(), key=lambda x:x[1], reverse=True)
        quentes = [n for n,_ in ordenado[:top]]
        frios = [n for n,_ in ordenado[-top:]]
        return {"quentes": quentes, "frios": frios}

# =========================
# Classe Avançada de Geração
# =========================
class LotoFacilAvancado:
    def __init__(self, concursos):
        self.concursos = concursos[:-1]  # excluir último
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}

    def calcular_padroes_linha_coluna(self):
        linhas = [0]*5
        colunas = [0]*5
        for jogo in self.concursos:
            for n in jogo:
                linhas[(n-1)//5] +=1
                colunas[(n-1)%5] +=1
        total = len(self.concursos)
        media_linhas = [max(1,int(round(c/total))) for c in linhas]
        media_colunas = [max(1,int(round(c/total))) for c in colunas]
        return media_linhas, media_colunas

    def gerar_cartoes_por_padrao(self, n_cartoes=5):
        media_linhas, media_colunas = self.calcular_padroes_linha_coluna()
        cartoes = []
        tentativas_max = 1000
        while len(cartoes) < n_cartoes and tentativas_max>0:
            cartao = set()
            linhas_atual = [0]*5
            colunas_atual = [0]*5
            while len(cartao)<15:
                n = random.randint(1,25)
                l = (n-1)//5
                c = (n-1)%5
                if linhas_atual[l] < media_linhas[l] and colunas_atual[c] < media_colunas[c]:
                    cartao.add(n)
                    linhas_atual[l]+=1
                    colunas_atual[c]+=1
            c_sorted = tuple(sorted(cartao))
            if c_sorted not in cartoes:
                cartoes.append(c_sorted)
            tentativas_max -=1
        return [list(c) for c in cartoes]

# =========================
# Streamlit
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

# Captura de concursos
with st.expander("📥 Capturar Concursos"):
    qtd_concursos = st.slider("Quantidade de concursos para análise", 10, 250, 100)
    if st.button("🔄 Capturar Agora"):
        with st.spinner("Capturando concursos da Lotofácil..."):
            concursos, info = capturar_ultimos_resultados(qtd_concursos)
            if concursos:
                st.session_state.concursos = concursos
                st.session_state.info_ultimo_concurso = info
                st.success(f"{len(concursos)} concursos capturados com sucesso!")

if st.session_state.concursos:
    stats = LotoFacilStats(st.session_state.concursos)
    adv = LotoFacilAvancado(st.session_state.concursos)
    abas = st.tabs(["📊 Estatísticas", "🧠 Gerar Cartões", "✅ Conferência", "📤 Conferir Arquivo TXT"])

    # --- Estatísticas ---
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Frequência dos números: {stats.frequencia_numeros()}")
        st.write(f"Soma média dos concursos: {stats.soma_media():.2f}")
        st.write(f"Média de pares/impares: {stats.pares_impares_distribuicao()}")
        st.write(f"Média de consecutivos: {stats.numeros_consecutivos():.2f}")
        st.write(f"Distribuição por grupos: {stats.grupos_distribuicao()}")
        qf = stats.numeros_quentes_frios()
        st.write(f"Números quentes: {qf['quentes']}")
        st.write(f"Números frios: {qf['frios']}")

    # --- Gerar Cartões ---
    with abas[1]:
        st.subheader("🧾 Geração de Cartões Otimizados")
        n_cartoes = st.slider("Quantidade de cartões", 1, 220, 5)
        if st.button("🚀 Gerar Cartões"):
            cartoes = adv.gerar_cartoes_por_padrao(n_cartoes)
            st.session_state.cartoes_gerados = cartoes
            st.success(f"{len(cartoes)} cartões gerados!")

        if st.session_state.cartoes_gerados:
            for i,c in enumerate(st.session_state.cartoes_gerados,1):
                st.write(f"Cartão {i}: {c}")

            st.subheader("📁 Exportar Cartões para TXT")
            conteudo = "\n".join(",".join(str(n) for n in c) for c in st.session_state.cartoes_gerados)
            st.download_button("💾 Baixar Arquivo", data=conteudo, file_name="cartoes_lotofacil.txt", mime="text/plain")

    # --- Conferência ---
    with abas[2]:
        st.subheader("🎯 Conferência de Cartões")
        if st.session_state.info_ultimo_concurso:
            info = st.session_state.info_ultimo_concurso
            dezenas_ultimo = info["dezenas"]
            st.markdown(f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {dezenas_ultimo}</h4>", unsafe_allow_html=True)
            if st.button("🔍 Conferir agora"):
                for i,c in enumerate(st.session_state.cartoes_gerados,1):
                    acertos = len(set(c) & set(dezenas_ultimo))
                    st.write(f"Cartão {i}: {c} - **{acertos} acertos**")
        else:
            st.warning("Informações do último concurso indisponíveis.")

    # --- Conferir arquivo TXT ---
    with abas[3]:
        st.subheader("📤 Conferir Cartões de um Arquivo TXT")
        uploaded_file = st.file_uploader("Upload do arquivo TXT (15 dezenas separadas por vírgula)", type="txt")
        if uploaded_file:
            linhas = uploaded_file.read().decode("utf-8").splitlines()
            cartoes_txt = []
            for l in linhas:
                try:
                    dezenas = sorted([int(x) for x in l.strip().split(",")])
                    if len(dezenas)==15 and all(1<=x<=25 for x in dezenas):
                        cartoes_txt.append(dezenas)
                except:
                    continue
            if cartoes_txt:
                st.success(f"{len(cartoes_txt)} cartões carregados com sucesso.")
                if st.session_state.info_ultimo_concurso:
                    info = st.session_state.info_ultimo_concurso
                    dezenas_ultimo = info["dezenas"]
                    st.markdown(f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {dezenas_ultimo}</h4>", unsafe_allow_html=True)
                    if st.button("📊 Conferir Cartões do Arquivo"):
                        for i,c in enumerate(cartoes_txt,1):
                            acertos = len(set(c) & set(dezenas_ultimo))
                            st.write(f"Cartão {i}: {c} - **{acertos} acertos**")
st.markdown("<hr><p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
