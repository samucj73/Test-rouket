import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# === CONFIGURAÇÕES ===
URL_APP = "https://test-rouket-jcdijgmwnb8vlhv9v86scu.streamlit.app/"

# Inicia navegador
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
driver.get(URL_APP)

actions = ActionChains(driver)

print("Bot iniciado, interagindo com o app...")

while True:
    acao = random.choice(["mover_mouse", "rolar", "clicar_botao", "pressionar_tecla"])

    if acao == "mover_mouse":
        actions.move_by_offset(random.randint(-50, 50), random.randint(-50, 50)).perform()

    elif acao == "rolar":
        driver.execute_script(f"window.scrollBy(0, {random.randint(-200, 200)});")

    elif acao == "clicar_botao":
        botoes = driver.find_elements(By.TAG_NAME, "button")
        if botoes:
            botao = random.choice(botoes)
            try:
                botao.click()
            except:
                pass

    elif acao == "pressionar_tecla":
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.SPACE)  # simula espaço
        time.sleep(0.5)
        body.send_keys(Keys.ARROW_DOWN)  # seta para baixo

    time.sleep(random.uniform(5, 15))  # pausa aleatória
