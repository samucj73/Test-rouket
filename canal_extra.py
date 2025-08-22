# canal_extra.py
import requests

# =========================
# CONFIGURAÇÃO DO CANAL EXTRA
# =========================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID_EXTRA = "-1002880411750"

# =========================
# ESTADO INTERNO
# =========================
entrada_atual = []  # lista dos 4 números da última entrada registrada

# =========================
# FUNÇÕES
# =========================
def enviar_telegram_extra(msg: str):
    """Envia mensagem curta para o canal extra"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID_EXTRA,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=5)
    except Exception:
        pass

def gerar_intersecao_numeros(duzia:int, coluna:int):
    """Retorna os 4 números da interseção da dúzia + coluna"""
    # Define intervalo da dúzia
    if duzia == 1: nums_duzia = set(range(1,13))
    elif duzia == 2: nums_duzia = set(range(13,25))
    elif duzia == 3: nums_duzia = set(range(25,37))
    else: return []

    # Define números da coluna
    if coluna == 1: nums_coluna = set(n for n in range(1,37) if (n-1)%3==0)
    elif coluna == 2: nums_coluna = set(n for n in range(1,37) if (n-1)%3==1)
    elif coluna == 3: nums_coluna = set(n for n in range(1,37) if (n-1)%3==2)
    else: return []

    # Interseção
    return sorted(list(nums_duzia & nums_coluna))

def registrar_entrada(duzia:int, coluna:int):
    """Registra a entrada para o canal extra e envia a mensagem"""
    global entrada_atual
    intersecao = gerar_intersecao_numeros(duzia, coluna)
    if intersecao:
        entrada_atual = intersecao
        enviar_telegram_extra(f"🎯 {entrada_atual}")

def processar_resultado(numero:int):
    """Verifica se saiu GREEN ou RED para a entrada atual"""
    global entrada_atual
    if not entrada_atual:
        return
    if numero in entrada_atual:
        enviar_telegram_extra(f"🟢 {numero}")
    else:
        enviar_telegram_extra(f"🔴 {numero}")
    entrada_atual = []  # zera após enviar resultado
