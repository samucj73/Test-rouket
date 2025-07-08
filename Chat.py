import requests

TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
print(res.json())
