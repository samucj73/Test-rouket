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

# Slider para controlar frequência de cliques
frequencia = st.slider("Chance de clicar a cada ciclo (%)", 0, 100, 20)

# Inicializa estado do bot
if "bot_ativo" not in st.session_state:
    st.session_state.bot_ativo = False

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

        while st.session_state.bot_ativo:
            botoes = driver.find_elements(By.TAG_NAME, "button")
            botoes_visiveis = [b for b in botoes if b.is_displayed() and b.is_enabled()]

            if botoes_visiveis and random.random() < (chance / 100):
                botao = random.choice(botoes_visiveis)
                try:
                    botao.click()
                    st.write("Clicou em um botão")
                    time.sleep(random.uniform(1, 3))
                except Exception as e:
                    st.write(f"Erro ao clicar no botão: {e}")

            time.sleep(random.uniform(2, 5))

    except Exception as e:
        st.write(f"Erro no bot: {e}")

    finally:
        driver.quit()
        st.write("Bot finalizado")
        st.session_state.bot_ativo = False

# Botão para iniciar/parar
if st.button("Iniciar / Parar Bot") and url:
    if not st.session_state.bot_ativo:
        st.session_state.bot_ativo = True
        threading.Thread(target=rodar_bot, args=(url, frequencia), daemon=True).start()
    else:
        st.session_state.bot_ativo = False
        st.write("Parando o bot...")
