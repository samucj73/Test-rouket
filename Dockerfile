FROM python:3.10-slim

# Instala dependências do sistema e o Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean

# Define diretório do app
WORKDIR /app

# Copia os arquivos do projeto
COPY . /app

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta usada pelo Streamlit
EXPOSE 8000

# Comando para iniciar o app
CMD ["streamlit", "run", "src/app.py", "--server.port=8000", "--server.address=0.0.0.0"]
