import streamlit as st
from lotofacil_stats import LotoFacilStats
from lotofacil_avancado import LotoFacilAvancado
import requests
import random

st.set_page_config(page_title="Lotofácil Inteligente", layout="centered")

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

# Sessão
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

if not st.session_state.concursos:
    st.warning("Capture os concursos antes de utilizar as funcionalidades abaixo.")
else:
    abas = st.tabs(["📊 Estatísticas", "🧠 Gerar Cartões", "✅ Conferência", "📤 Conferir Arquivo TXT"])
    stats = LotoFacilStats(st.session_state.concursos)
    stats_adv = LotoFacilAvancado(st.session_state.concursos)

    # --- Aba 1 ---
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Frequência dos números: {stats.frequencia_numeros()}")
        st.write(f"Soma média dos concursos: {stats.soma_media():.2f}")
        st.write(f"Média de pares/impares: {stats.pares_impares_distribuicao()}")
        st.write(f"Média de consecutivos: {stats.numeros_consecutivos():.2f}")
        st.write(f"Distribuição por grupos: {stats.grupos_distribuicao()}")
        quentes_frios = stats.numeros_quentes_frios()
        st.write(f"Números quentes: {quentes_frios['quentes']}")
        st.write(f"Números frios: {quentes_frios['frios']}")

        st.divider()
        st.subheader("📐 Estatísticas Avançadas")
        st.write(f"Média de primos por jogo: {stats_adv.media_primos():.2f}")
        st.write(f"Distribuição de primos: {stats_adv.distribuicao_primos()}")
        st.write(f"Média de múltiplos de 3 por jogo: {stats_adv.media_multiplos_3():.2f}")
        st.write(f"Distribuição de múltiplos de 3: {stats_adv.distribuicao_multiplos_3()}")

    # --- Aba 2 ---
    with abas[1]:
        st.subheader("🧾 Geração de Cartões Equilibrados com Padrões e Features")
        n_cartoes = st.slider("Quantidade de cartões", 1, 220, 10)

        if st.button("🚀 Gerar Cartões Equilibrados"):
            concursos_hist = st.session_state.concursos[:-1]
            freq = stats.frequencia_numeros()
            quentes_frios = stats.numeros_quentes_frios()

            # Identifica padrões linha×coluna mais frequentes
            def extrair_distribuicao(jogo):
                linhas = [[i for i in range(l*5+1, l*5+6)] for l in range(5)]
                colunas = [[i for i in range(c+1, 26, 5)] for c in range(5)]
                dist_linhas = tuple(sum(1 for n in jogo if n in linha) for linha in linhas)
                dist_colunas = tuple(sum(1 for n in jogo if n in coluna) for coluna in colunas)
                return dist_linhas, dist_colunas

            from collections import Counter
            padroes = [extrair_distribuicao(jogo) for jogo in concursos_hist]
            padroes_freq = [p for p,_ in Counter(padroes).most_common(5)]

            # Função para calcular features do cartão
            def calcular_features(cartao):
                pares = sum(1 for n in cartao if n % 2 == 0)
                primos = sum(1 for n in cartao if n in stats_adv.primos)
                consecutivos = sum(1 for i in range(1,15) if cartao[i]-cartao[i-1]==1)
                multiplos3 = sum(1 for n in cartao if n%3==0)
                quentes = sum(1 for n in cartao if n in quentes_frios['quentes'])
                frios = sum(1 for n in cartao if n in quentes_frios['frios'])
                return {"pares": pares, "primos": primos, "consecutivos": consecutivos, "mult3": multiplos3, "quentes": quentes, "frios": frios}

            # Geração dos cartões
            cartoes = []
            tentativas = 0
            while len(cartoes) < n_cartoes and tentativas < 3000:
                padrao_linhas, padrao_colunas = padroes_freq[random.randint(0, len(padroes_freq)-1)]
                jogo = []

                # Construção por linha
                linhas_def = [[i for i in range(l*5+1, l*5+6)] for l in range(5)]
                for l, qtd in enumerate(padrao_linhas):
                    candidatos = [n for n in linhas_def[l] if n not in jogo]
                    candidatos = sorted(candidatos, key=lambda x: (-freq.get(x,0), x in quentes_frios['quentes']))
                    jogo += candidatos[:qtd]

                # Completa 15 dezenas
                if len(jogo) < 15:
                    restantes = [n for n in range(1,26) if n not in jogo]
                    restantes = sorted(restantes, key=lambda x: (-freq.get(x,0), x in quentes_frios['quentes']))
                    jogo += restantes[:15-len(jogo)]
                elif len(jogo) > 15:
                    jogo = sorted(jogo, key=lambda x: -freq.get(x,0))[:15]

                jogo_sorted = sorted(jogo)

                # Checa se já existe
                if jogo_sorted in cartoes:
                    tentativas +=1
                    continue

                # Ajusta características para equilibrar features
                feats = calcular_features(jogo_sorted)
                if 7 <= feats['pares'] <= 9 and feats['primos'] >= 3 and 2 <= feats['consecutivos'] <= 4 and 4 <= feats['mult3'] <= 6:
                    cartoes.append(jogo_sorted)
                tentativas += 1

            st.session_state.cartoes_gerados = cartoes
            st.success(f"{len(cartoes)} cartões equilibrados gerados com padrões e features!")

        # Exibe cartões
        if st.session_state.cartoes_gerados:
            st.subheader("📄 Cartões Gerados")
            for i, c in enumerate(st.session_state.cartoes_gerados, 1):
                st.write(f"Cartão {i}: {c}")

            st.subheader("📁 Exportar Cartões para TXT")
            if st.button("💾 Exportar"):
                conteudo = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados)
                st.download_button("📥 Baixar Arquivo", data=conteudo, file_name="cartoes_lotofacil.txt", mime="text/plain")

    # --- Aba 3 ---
    with abas[2]:
        st.subheader("🎯 Conferência de Cartões")
        if st.session_state.info_ultimo_concurso:
            info = st.session_state.info_ultimo_concurso
            st.markdown(
                f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                unsafe_allow_html=True
            )
        else:
            st.warning("Informações do último concurso indisponíveis.")

        if st.button("🔍 Conferir agora"):
            if not st.session_state.cartoes_gerados:
                st.info("Gere os cartões primeiro.")
            elif not st.session_state.info_ultimo_concurso:
                st.warning("Dados do último concurso não encontrados.")
            else:
                dezenas_ultimo = st.session_state.info_ultimo_concurso["dezenas"]
                for i, cartao in enumerate(st.session_state.cartoes_gerados, 1):
                    acertos = len(set(cartao) & set(dezenas_ultimo))
                    st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")

    # --- Aba 4 ---
    with abas[3]:
        st.subheader("📤 Conferir Cartões de um Arquivo TXT")
        uploaded_file = st.file_uploader("Faça upload do arquivo TXT com os cartões (formato: 15 dezenas separadas por vírgula)", type="txt")

        if uploaded_file is not None:
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
                    dezenas_ultimo = info["dezenas"]
                    st.markdown(
                        f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                        unsafe_allow_html=True
                    )
                    if st.button("📊 Conferir Cartões do Arquivo"):
                        for i, cartao in enumerate(cartoes_txt, 1):
                            acertos = len(set(cartao) & set(dezenas_ultimo))
                            st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")

                else:
                    st.warning("Capture os concursos para saber o resultado mais recente.")
            else:
                st.error("Nenhum cartão válido foi encontrado no arquivo.")

st.markdown("<hr><p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
