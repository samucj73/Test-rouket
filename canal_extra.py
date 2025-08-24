# canal_extra.py
import requests

# =========================
# CONFIGURAÇÃO DO CANAL EXTRA
# =========================
#TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
#TELEGRAM_CHAT_ID_EXTRA = "-1002880411750"

# =========================
# ESTADO INTERNO
# =========================
entrada_atual = []         # números da última entrada registrada (já com inversão aplicada)
resultado_enviado = False  # flag para evitar múltiplos envios do resultado

# Atalho para ligar/desligar a inversão de coluna (se precisar)
INVERTER_COLUNA_EXTRA = True

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
    if coluna == 1: nums_coluna = {n for n in range(1,37) if (n-1) % 3 == 0}
    elif coluna == 2: nums_coluna = {n for n in range(1,37) if (n-1) % 3 == 1}
    elif coluna == 3: nums_coluna = {n for n in range(1,37) if (n-1) % 3 == 2}
    else: return []

    # Interseção (até 4 números)
    return sorted(nums_duzia & nums_coluna)

def _colunas_invertidas(coluna:int):
    """Retorna as duas colunas invertidas (ex.: 3 -> [1,2])"""
    if coluna == 1: return [2, 3]
    if coluna == 2: return [1, 3]
    if coluna == 3: return [1, 2]
    return []

def reset_canal_extra():
    """Reseta a entrada e a flag de resultado no início de cada nova rodada"""
    global entrada_atual, resultado_enviado
    entrada_atual = []
    resultado_enviado = False

def registrar_entrada(duzia:int, coluna:int):
    """
    Registra a entrada para o canal extra e envia a mensagem.
    Lógica: mantém a DÚZIA recebida e INVERTE a COLUNA para as outras duas.
            Ex.: (duzia=2, coluna=3) -> usa colunas [1,2] e envia a união das interseções.
    """
    global entrada_atual, resultado_enviado

    if duzia not in (1,2,3):
        return

    # Define colunas alvo (invertidas) ou usa a original se inversão estiver desligada
    if INVERTER_COLUNA_EXTRA and coluna in (1,2,3):
        colunas_alvo = _colunas_invertidas(coluna)
    elif coluna in (1,2,3):
        colunas_alvo = [coluna]
    else:
        return

    # Constrói a união das interseções (geralmente 8 números quando há inversão)
    numeros = set()
    for c in colunas_alvo:
        numeros.update(gerar_intersecao_numeros(duzia, c))

    intersecao_invertida = sorted(numeros)

    if intersecao_invertida and intersecao_invertida != entrada_atual:
        entrada_atual = intersecao_invertida
        resultado_enviado = False  # reset da flag para nova rodada
        enviar_telegram_extra(f"🎯 {entrada_atual}")

def processar_resultado(numero:int):
    """
    Verifica se saiu GREEN ou RED para a entrada atual.
    (Sem inversão na conferência: GREEN se o número estiver na lista enviada)
    """
    global entrada_atual, resultado_enviado
    if not entrada_atual or resultado_enviado:
        return

    if numero in entrada_atual:
        enviar_telegram_extra(f"🟢 {numero}")
    else:
        enviar_telegram_extra(f"🔴 {numero}")

    resultado_enviado = True
