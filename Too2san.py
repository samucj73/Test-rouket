import streamlit as st
import threading
import requests
import joblib
import numpy as np
from collections import deque, Counter
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from catboost import CatBoostClassifier

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
HISTORICO_DUZIAS_PATH = Path("historico.pkl")          
HISTORICO_NUMEROS_PATH = Path("historico_numeros.pkl") 
ESTADO_PATH = Path("estado.pkl")
MODEL_PATH = Path("modelo.pkl")  # <<< modelo salvo
MAX_HIST_LEN = 4500
REFRESH_INTERVAL = 5000  
WINDOW_SIZE = 15         
TRAIN_EVERY = 10         

# === MAPAS AUXILIARES (roda europeia) ===
RED_SET = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
IDX = {n:i for i,n in enumerate(WHEEL)}
VOISINS = {22,18,29,7,28,12,35,3,26,0,32,15,19,4,21,2,25}
TIERS   = {27,13,36,11,30,8,23,10,5,24,16,33}
ORPH    = {1,20,14,31,9,17,34,6}

# ... [todas as funções auxiliares continuam iguais] ...

# === TREINAMENTO ===
def treinar_modelo_rf():
    X,y=criar_dataset_features(st.session_state.historico,st.session_state.historico_numeros,tamanho_janela)
    if len(y)>1 and len(set(y))>1 and len(X)==len(y):
        modelo=CatBoostClassifier(iterations=300,depth=6,learning_rate=0.08,
                                  loss_function='MultiClass',verbose=False)
        try:
            modelo.fit(X,y)
            st.session_state.modelo_rf=modelo
            joblib.dump(modelo, MODEL_PATH)  # <<< salva modelo treinado
            return True
        except Exception as e:
            print(f"[Treino] Erro ao treinar modelo: {e}")
            return False
    return False

# === RECUPERAÇÃO DO MODELO ===
if MODEL_PATH.exists() and "modelo_rf" not in st.session_state:
    try:
        st.session_state.modelo_rf = joblib.load(MODEL_PATH)
        print("[Init] Modelo carregado de disco.")
    except Exception as e:
        print(f"[Init] Erro ao carregar modelo: {e}")
        st.session_state.modelo_rf = None

# === PREVISÃO ===
def prever_duzia_rf():
    duz=list(st.session_state.historico)
    nums=list(st.session_state.historico_numeros)
    if len(duz)<tamanho_janela or st.session_state.modelo_rf is None:
        return None
    janela_duz=duz[-tamanho_janela:]
    janela_num=nums[-tamanho_janela:]
    feat = np.array([extrair_features(janela_duz,janela_num)],dtype=float)
    try:
        probs=st.session_state.modelo_rf.predict_proba(feat)[0]
        preds={i+1:p for i,p in enumerate(probs)}
        top2=sorted(preds.items(), key=lambda x: x[1], reverse=True)[:2]
        return top2
    except Exception as e:
        print(f"[Previsão] Erro: {e}")
        return None

# === ALERTA TELEGRAM ===
def enviar_alerta_duzia():
    top=prever_duzia_rf()
    if not top: return
    chave="_".join(str(d) for d,_ in top)
    if chave==st.session_state.ultima_chave_alerta and st.session_state.contador_sem_alerta<3:
        st.session_state.contador_sem_alerta+=1
        return
    st.session_state.ultima_chave_alerta=chave
    st.session_state.contador_sem_alerta=0
    
    # <<< Mensagem mais clara com probabilidade
    msg="🎯 Previsão de Dúzia:\n"
    for d, p in top:
        msg += f" - Dúzia {d}: {p*100:.1f}%\n"
    enviar_telegram_async(msg)

# === LOOP PRINCIPAL SEGURANÇA + LOG ===
def loop_principal():
    import time
    while True:
        numero = capturar_ultimo_numero()
        if numero is None:
            print("[Loop] Número não capturado, tentando novamente...")
            time.sleep(2)
            continue

        if numero != st.session_state.ultimo_numero_salvo:
            print(f"[Loop] Novo número capturado: {numero}")
            st.session_state.ultimo_numero_salvo = numero
            salvar_historico(numero)

            try:
                enviar_alerta_duzia()
            except Exception as e:
                print(f"[Loop] Erro ao enviar alerta Telegram: {e}")

            estado = dict(
                ultima_chave_alerta=st.session_state.ultima_chave_alerta,
                contador_sem_alerta=st.session_state.contador_sem_alerta
            )
            try:
                joblib.dump(estado, ESTADO_PATH)
            except Exception as e:
                print(f"[Loop] Erro ao salvar estado: {e}")

            if len(st.session_state.historico) % TRAIN_EVERY == 0:
                print("[Loop] Treinando modelo CatBoost...")
                sucesso = treinar_modelo_rf()
                if sucesso:
                    print("[Loop] Modelo treinado e salvo.")
                else:
                    print("[Loop] Falha no treinamento.")

        time.sleep(2)

# === THREAD ÚNICA ===
if "thread_started" not in st.session_state:
    threading.Thread(target=loop_principal,daemon=True).start()
    st.session_state.thread_started=True
    st.info("Sistema de previsão de Dúzia ativo. Alertas Telegram serão enviados automaticamente.")

# === AUTORELOAD STREAMLIT ===
st_autorefresh(interval=REFRESH_INTERVAL, key="autoreload")
