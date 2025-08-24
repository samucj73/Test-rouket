import streamlit as st
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import threading

st.title("Bot de Movimento de Mouse")

# Entrada da URL
url = st.text_input("Digite a URL do site:", "")

# Slider para controlar velocidade dos movimentos
intervalo = st.slider("Intervalo médio entre movimentos (segundos)", min_value=2, max_value=10, value=4)

# Botão para iniciar
if st.button("Iniciar Bot") and url:
    st.write(f"Iniciando bot em: {url} (movimento de mouse aleatório a cada {intervalo}s)")

    def rodar_bot(APP_URL, delay):
        options = Options()
        options.add_argument("--headless=new")  # roda sem abrir janela
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(options=options)

        try:
            driver.get(APP_URL)
            st.write(f"Bot iniciado no site: {APP_URL}")

            largura = driver.execute_script("return window.innerWidth")
            altura = driver.execute_script("return window.innerHeight")

            while True:
                # Posição aleatória dentro da tela
                x = random.randint(50, largura - 50)
                y = random.randint(50, altura - 50)

                # Movimento suave do mouse com steps
                for i in range(20):
                    xi = int(x * i / 20)
                    yi = int(y * i / 20)
                    driver.execute_script(
                        "window.dispatchEvent(new MouseEvent('mousemove', {clientX: arguments[0], clientY: arguments[1]}));",
                        xi, yi
                    )
                    time.sleep(0.02)

                st.write(f"Movendo mouse para: ({x}, {y})")

                # Pausa antes do próximo movimento
                time.sleep(random.uniform(delay * 0.7, delay * 1.3))

        except Exception as e:
            st.write(f"Erro no bot: {e}")

        finally:
            driver.quit()
            st.write("Bot finalizado")

    # Rodar em thread separada
    threading.Thread(target=rodar_bot, args=(url, intervalo), daemon=True).start()
