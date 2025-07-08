import streamlit as st
import requests

TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

res = requests.get(url)
print(res.json())
