import streamlit as st
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import threading

st.title("Bot de Cliques Aleatórios")

# Entrada da URL
url = st.text_input("Digite a URL do site:", "")

# Slider para controlar frequência de cliques (0 a 100%)
frequencia = st.slider("Chance de clicar a cada ciclo (%)", min_value=0, max_value=100, value=20)

# Botão para iniciar
if st.button("Iniciar Bot") and url:
    st.write(f"Iniciando bot em: {url} com {frequencia}% de chance de clicar a cada ciclo")

    def rodar_bot(APP_URL, chance):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(options=options)

        try:
            driver.get(APP_URL)
            st.write(f"Bot iniciado no site: {APP_URL}")

            while True:
                # Encontrar botões visíveis
                botoes = driver.find_elements(By.TAG_NAME, "button")
                botoes_visiveis = [b for b in botoes if b.is_displayed() and b.is_enabled()]

                # Clicar em um botão aleatório com chance 
                if botoes_visiveis and random.random() < (chance / 100):
                    botao = random.choice(botoes_visiveis)
                    try:
                        botao.click()
                        st.write("Clicou em um botão")
                        time.sleep(random.uniform(1, 3))
                    except Exception as e:
                        st.write(f"Erro ao clicar no botão: {e}")

                # Pequena pausa entre ações
                time.sleep(random.uniform(2, 5))

        except Exception as e:
            st.write(f"Erro no bot: {e}")

        finally:
            driver.quit()
            st.write("Bot finalizado")

    # Rodar o bot em thread separada
    threading.Thread(target=rodar_bot, args=(url, frequencia), daemon=True).start()
