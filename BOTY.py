import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# === CONFIGURAÇÕES ===
#APP_URL = "https://test-rouket-jcdijgmwnb8vlhv9v86scu.streamlit.app/"

# Configurações do Chrome para ambiente sem interface (headless)
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
    print("Bot iniciado no app!")

    while True:
        # Simula rolagem
        scroll_y = random.randint(200, 800)
        driver.execute_script(f"window.scrollBy(0, {scroll_y});")
        print(f"Rolou {scroll_y} pixels")

        time.sleep(random.uniform(2, 5))

        # Volta pro topo
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.HOME)

        # Simula clique aleatório se houver botões
        botoes = driver.find_elements(By.TAG_NAME, "button")
        if botoes:
            botao = random.choice(botoes)
            try:
                botao.click()
                print("Clicou em um botão")
            except:
                pass

        time.sleep(random.uniform(10, 20))  # Pausa antes da próxima ação

except Exception as e:
    print("Erro no bot:", e)

finally:
    driver.quit()
