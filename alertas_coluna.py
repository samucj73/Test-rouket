# alertas_coluna.py
import requests

# =========================
# CONFIGURAÇÕES TELEGRAM
# =========================
#TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
#TELEGRAM_CHAT_ID = "5121457416"

# -------------------------
def send_telegram_message(message: str):
    """Envia mensagem para o Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")

# -------------------------
def enviar_previsao(coluna: int):
    """
    Envia alerta com a previsão final da coluna
    """
    msg = f"📊 <b>Previsão Final de Coluna</b>\n🎯 Coluna {coluna}"
    send_telegram_message(msg)

# -------------------------
def enviar_resultado(numero_sorteado: int, acertou: bool):
    """
    Envia alerta do resultado da rodada para o Telegram
    """
    status = "🟢 GREEN! Acertou!" if acertou else "🔴 RED! Errou!"
    mensagem = f"🎲 Resultado: {numero_sorteado}\n{status}"
    send_telegram_message(mensagem)

# -------------------------
def get_coluna(n: int):
    """
    Retorna a coluna de um número:
    0 = zero, 1 = primeira coluna, 2 = segunda, 3 = terceira
    """
    if n == 0:
        return 0
    elif n % 3 == 1:
        return 1
    elif n % 3 == 2:
        return 2
    elif n % 3 == 0:
        return 3
    return None
