import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
import os

# Layout visual estilo trader
st.set_page_config(page_title="Modo Trader - Roleta", layout="wide")
st.markdown("""
    <style>
    body { background-color: #0f1117; color: #ffffff; }
    .main { background-color: #0f1117; }
    h1, h2, h3, h4 { color: #f1c40f; }
    .stButton>button {
        background-color: #f1c40f;
        color: black;
        border-radius: 8px;
        padding: 0.5em 1em;
        font-weight: bold;
    }
    .stDownloadButton>button {
        background-color: #27ae60;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    .css-1v0mbdj, .css-1cpxqw2 {
        background-color: #1f2233;
        padding: 10px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>Painel Modo Trader - Roleta</h1>", unsafe_allow_html=True)

# 1. Banca
st.markdown("### 1. Configuração da Banca")
banca = st.number_input("Insira o valor da banca inicial (R$):", min_value=0.0, step=1.0)

# 2. Upload da imagem com resultados da roleta
st.markdown("### 2. Enviar imagem com os números sorteados")
imagem = st.file_uploader("Envie uma imagem com os 100 últimos números da roleta:", type=["png", "jpg", "jpeg"])

numeros = []

if imagem:
    img = Image.open(imagem)
    texto = pytesseract.image_to_string(img)
    numeros_extraidos = [int(s) for s in texto.split() if s.isdigit()]
    numeros = numeros_extraidos[:100]
    st.success(f"Números extraídos (primeiros 100): {numeros}")

# 3. Análise estatística
if numeros:
    st.markdown("### 3. Análise Estatística")
    df = pd.Series(numeros)
    st.write("Frequência dos números:")
    st.bar_chart(df.value_counts().sort_index())

    st.write(f"**Média:** {df.mean():.2f}")
    st.write(f"**Moda:** {df.mode().values}")
    st.write(f"**Mediana:** {df.median()}")
    st.write(f"**Desvio padrão:** {df.std():.2f()}")

    st.write(f"**Números pares:** {sum(n % 2 == 0 for n in numeros)}")
    st.write(f"**Números ímpares:** {sum(n % 2 != 0 for n in numeros)}")

# 4. Previsão com IA simples
    st.markdown("### 4. Previsão Inteligente dos Próximos Números")
    def prever_proximos_numeros(numeros, qtd=10):
        freq = pd.Series(numeros).value_counts()
        quentes = freq.head(10).index.tolist()
        frios = freq.tail(10).index.tolist()

        sugestao = []
        while len(sugestao) < qtd:
            for n in quentes + frios:
                if n not in sugestao:
                    sugestao.append(n)
                if len(sugestao) >= qtd:
                    break
        return sugestao

    sugestao_numeros = prever_proximos_numeros(numeros)
    st.success(f"Números sugeridos: {sugestao_numeros}")

# 5. Relatório PDF
    st.markdown("### 5. Gerar Relatório PDF")

    def gerar_pdf(numeros, sugestao):
        freq = pd.Series(numeros).value_counts().sort_index()

        fig, ax = plt.subplots()
        freq.plot(kind='bar', ax=ax)
        ax.set_title('Frequência dos Números')
        ax.set_xlabel('Número')
        ax.set_ylabel('Ocorrências')

        temp_chart = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        fig.savefig(temp_chart.name)
        plt.close()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Análise da Roleta - Modo Trader", ln=True, align="C")

        pdf.ln(10)
        pdf.multi_cell(0, 10, f"Banca inicial: R$ {banca}")
        pdf.multi_cell(0, 10, f"Números extraídos: {numeros}")
        pdf.multi_cell(0, 10, f"Números sugeridos (IA): {sugestao}")

        pdf.image(temp_chart.name, x=10, y=None, w=180)

        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(temp_pdf.name)

        os.unlink(temp_chart.name)
        return temp_pdf.name

    if st.button("Gerar PDF"):
        caminho_pdf = gerar_pdf(numeros, sugestao_numeros)
        with open(caminho_pdf, "rb") as file:
            st.download_button("Baixar Relatório PDF", file, file_name="relatorio_roleta.pdf", mime="application/pdf")
