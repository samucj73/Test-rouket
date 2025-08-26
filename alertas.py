# alertas.py
import requests
import time

# =========================
# CONFIGURAÇÕES TELEGRAM
# =========================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"


def send_telegram_message(message: str):
    """Envia mensagem para o Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")


def enviar_previsao(previsao: int):
    """
    Envia alerta com a previsão final
    """
    msg = f"📊 <b>Previsão Final</b>\n🎯 Dúzia {previsao}"
    send_telegram_message(msg)


def get_duzia(n: int):
    """Cálculo da dúzia (0 = zero, 1 = 1-12, 2 = 13-24, 3 = 25-36)"""
    if n == 0:
        return 0
    elif 1 <= n <= 12:
        return 1
    elif 13 <= n <= 24:
        return 2
    elif 25 <= n <= 36:
        return 3
    return None

def enviar_resultado(numero_sorteado, acertou: bool):
    """Envia alerta do resultado da rodada para o Telegram"""
    status = "🟢 GREEN! Acertou!" if acertou else "🔴 RED! Errou!"
    mensagem = f"🎲 Resultado: {numero_sorteado}\n{status}"
    enviar_alerta(mensagem)

