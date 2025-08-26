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


def enviar_previsao(previsao: str):
    """
    Envia alerta com a previsão final
    """
    msg = f"📊 <b>Previsão Final</b>\n🎯 Dúzia {previsao}"
    send_telegram_message(msg)


def enviar_resultado(numero: int, duzia_prevista: int):
    """
    Envia alerta com o resultado e se deu GREEN ou RED
    """
    from main import get_duzia  # usa sua própria função para calcular a dúzia

    duzia_resultado = get_duzia(numero)
    deu_green = duzia_resultado == duzia_prevista
    status = "🟢 GREEN" if deu_green else "🔴 RED"
    msg = f"🎲 Resultado: {numero} (Dúzia {duzia_resultado})\n➡️ {status}"
    time.sleep(4)  # dá tempo entre previsão e resultado
    send_telegram_message(msg)
