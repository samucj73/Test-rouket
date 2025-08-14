import streamlit as st
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import threading

st.title("Bot de Cliques Aleatórios com Rolagem")

# Entrada da URL
url = st.text_input("Digite a URL do site:", "")

# Slider para controlar frequência de cliques
frequencia = st.slider("Chance de clicar a cada ciclo (%)", 0, 100, 20)

# Inicializa estado do bot
if "bot_ativo" not in st.session_state:
    st.session_state.bot_ativo = False
if "bot_status" not in st.session_state:
    st.session_state.bot_status = "Inativo"

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
        st.session_state.bot_status = f"Bot iniciado no site: {APP_URL}"

        while st.session_state.bot_ativo:
            # Rolagem aleatória
            scroll = random.randint(100, 800)
            driver.execute_script(f"window.scrollBy(0, {scroll});")
            st.session_state.bot_status = f"Rolou a página {scroll}px"

            # Seleciona botões visíveis
            botoes = driver.find_elements(By.TAG_NAME, "button")
            botoes_visiveis = [b for b in botoes if b.is_displayed() and b.is_enabled()]

            # Clique aleatório com base na chance
            if botoes_visiveis and random.random() < (chance / 100):
                botao = random.choice(botoes_visiveis)
                try:
                    botao.click()
                    st.session_state.bot_status = "Clicou em um botão"
                    time.sleep(random.uniform(1, 2))
                except:
                    st.session_state.bot_status = "Erro ao clicar em um botão"

            # Pausa aleatória entre ciclos
            time.sleep(random.uniform(2, 5))

    except:
        st.session_state.bot_status = "Erro no bot"

    finally:
        driver.quit()
        st.session_state.bot_status = "Bot finalizado"
        st.session_state.bot_ativo = False

# Botão para iniciar/parar
if st.button("Iniciar / Parar Bot") and url:
    if not st.session_state.bot_ativo:
        st.session_state.bot_ativo = True
        threading.Thread(target=rodar_bot, args=(url, frequencia), daemon=True).start()
    else:
        st.session_state.bot_ativo = False
        st.session_state.bot_status = "Parando o bot..."

# Atualiza status na interface
st.write("Status do Bot:", st.session_state.bot_status)
