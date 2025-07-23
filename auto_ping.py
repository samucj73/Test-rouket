# auto_ping.py

import threading
import time
import requests

URL_APP = "https://seuapp.streamlit.app"  # 🔁 Substitua com o link real do seu app

def manter_app_ativo():
    def ping_loop():
        while True:
            try:
                requests.get(URL_APP)
                print("🔄 Ping enviado para manter o app ativo.")
            except Exception as e:
                print(f"⚠️ Erro ao pingar o app: {e}")
            time.sleep(20)  # 5 minutos (300 segundos)

    # Inicia a thread como daemon (roda em paralelo ao app)
    thread = threading.Thread(target=ping_loop, daemon=True)
    thread.start()
