import telebot
import json
from random import randint

# TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
# CANAL_ID = -1002796136111
USUARIOS_JSON = "usuarios_autorizados.json"

bot = telebot.TeleBot(TOKEN)

def carregar_autorizados():
    try:
        with open(USUARIOS_JSON, "r") as f:
            return json.load(f)
    except:
        return []

def salvar_autorizados(lista):
    with open(USUARIOS_JSON, "w") as f:
        json.dump(lista, f)

@bot.message_handler(commands=["start"])
def iniciar(msg):
    chat_id = msg.chat.id
    autorizados = carregar_autorizados()
    if chat_id in autorizados:
        bot.send_message(chat_id, "✅ Acesso ativo ao Canal Sinais VIP.")
    else:
        bot.send_message(chat_id, "🔒 Seu acesso ainda não foi liberado. Aguardando aprovação.")
        if chat_id not in autorizados:
            autorizados.append(chat_id)
            salvar_autorizados(autorizados)

# Exemplo de função que envia sinal
def enviar_sinal(sinal_texto):
    autorizados = carregar_autorizados()
    for uid in autorizados:
        bot.send_message(uid, sinal_texto)
    bot.send_message(CANAL_ID, sinal_texto)

# Simulação de envio de sinal (exemplo)
if __name__ == "__main__":
    @bot.message_handler(commands=["teste_sinal"])
    def teste(msg):
        enviar_sinal(f"🎯 Sinal de teste: número {randint(0,36)}")

    bot.polling()
