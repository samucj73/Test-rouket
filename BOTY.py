import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# === CONFIGURAÇÕES ===
APP_URL = "https://test-rouket-jcdijgmwnb8vlhv9v86scu.streamlit.app/"

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
        # Scroll parcial
        scroll_y = random.randint(100, 500)
        driver.execute_script(f"window.scrollBy(0, {scroll_y});")
        print(f"Rolou {scroll_y} pixels para baixo")
        time.sleep(random.uniform(1, 3))

        # Chance de clicar em botão visível
        botoes = driver.find_elements(By.TAG_NAME, "button")
        botoes_visiveis = [b for b in botoes if b.is_displayed() and b.is_enabled()]
        if botoes_visiveis and random.random() < 0.2:  # 20% de chance
            botao = random.choice(botoes_visiveis)
            try:
                botao.click()
                print("Clicou em um botão")
                time.sleep(random.uniform(1, 3))  # pausa após clique
            except Exception as e:
                print("Erro ao clicar no botão:", e)

        # Pequena pausa entre ações
        time.sleep(random.uniform(2, 5))

except Exception as e:
    print("Erro no bot:", e)

finally:
    driver.quit()
