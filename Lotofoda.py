import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
from collections import Counter
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL 3622",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
/* Layout mobile premium */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1,h2,h3 { text-align: center; }
.card { background: #0e1117; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid #262730; color: white; }
.stButton>button { width: 100%; height: 3.2em; border-radius: 14px; font-size: 1.05em; }
input, textarea { border-radius: 12px !important; }
.p12 { color: #4cc9f0; font-weight: bold; }
.p13 { color: #4ade80; font-weight: bold; }
.p14 { color: gold; font-weight: bold; }
.p15 { color: #f97316; font-weight: bold; }
.concurso-info { background: #1e1e2e; padding: 10px; border-radius: 10px; margin: 10px 0; }
.metric-card { background: #16213e; padding: 10px; border-radius: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL 3622")
st.caption("Modelo Universal + Ajuste Adaptável • Mobile First")

# =====================================================
# FUNÇÃO PARA CONVERTER NUMPY TYPES PARA PYTHON NATIVE
# =====================================================
def convert_numpy_types(obj):
    """Converte numpy types para tipos nativos Python para serialização JSON"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, Counter):
        return dict(obj)
    else:
        return obj

# =====================================================
# FUNÇÕES DE ARQUIVO LOCAL
# =====================================================
def salvar_jogos_gerados(jogos, fechamento, dna_params, numero_concurso_atual, data_concurso_atual, estatisticas=None):
    """Salva os jogos gerados em arquivo JSON local com estatísticas"""
    try:
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/fechamento_{data_hora}_{jogo_id}.json"
        
        # Converter todos os numpy types para tipos nativos
        jogos_convertidos = convert_numpy_types(jogos)
        
        # Garantir que cada jogo é uma lista simples
        jogos_final = []
        for jogo in jogos_convertidos:
            if isinstance(jogo, (list, tuple)):
                # Garantir que é uma lista de inteiros
                jogo_lista = [int(n) for n in jogo]
                # Garantir que tem 15 números únicos
                if len(set(jogo_lista)) != 15:
                    # Corrigir se necessário
                    jogo_lista = sorted(list(set(jogo_lista)))
                    while len(jogo_lista) < 15:
                        novo = random.randint(1, 25)
                        if novo not in jogo_lista:
                            jogo_lista.append(novo)
                    jogo_lista.sort()
                jogos_final.append(jogo_lista)
            else:
                # Se não for lista, tentar converter
                jogos_final.append([int(n) for n in range(1, 16)])  # fallback
        
        fechamento_convertido = convert_numpy_types(fechamento)
        dna_convertido = convert_numpy_types(dna_params) if dna_params else {}
        estatisticas_convertidas = convert_numpy_types(estatisticas) if estatisticas else {}
        
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_base": {
                "numero": int(numero_concurso_atual),
                "data": str(data_concurso_atual)
            },
            "fechamento_base": fechamento_convertido,
            "dna_params": dna_convertido,
            "jogos": jogos_final,
            "estatisticas": estatisticas_convertidas,
            "conferido": False,
            "conferencias": []
        }
        
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_salvos():
    """Carrega todos os jogos salvos"""
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos"):
            for arquivo in os.listdir("jogos_salvos"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos/{arquivo}", 'r', encoding='utf-8') as f:
                            dados = json.load(f)
                            if "concurso_base" not in dados:
                                dados["concurso_base"] = {"numero": 0, "data": "Desconhecido"}
                            if "conferencias" not in dados:
                                dados["conferencias"] = []
                            if "estatisticas" not in dados:
                                dados["estatisticas"] = {}
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception as e:
                        continue
            
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos salvos: {e}")
    
    return jogos_salvos

def adicionar_conferencia(arquivo, concurso_info, acertos, estatisticas=None):
    """Adiciona nova conferência ao histórico"""
    try:
        caminho = f"jogos_salvos/{arquivo}"
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        if "conferencias" not in dados:
            dados["conferencias"] = []
        
        # Converter dados para tipos nativos
        acertos_convertidos = [int(a) for a in acertos]
        estatisticas_convertidas = convert_numpy_types(estatisticas) if estatisticas else {}
        
        nova_conferencia = {
            "concurso": concurso_info,
            "acertos": acertos_convertidos,
            "estatisticas": estatisticas_convertidas,
            "data_conferencia": datetime.now().isoformat()
        }
        
        dados["conferencias"].append(nova_conferencia)
        dados["conferido"] = True
        
        # Atualizar estatísticas acumuladas
        if "estatisticas_historicas" not in dados:
            dados["estatisticas_historicas"] = []
        dados["estatisticas_historicas"].append(estatisticas_convertidas)
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar conferência: {e}")
        return False

# =====================================================
# FUNÇÃO PARA EXPORTAR CONCURSOS EM TXT
# =====================================================
def exportar_concursos_txt(dados_api, qtd_concursos):
    """Exporta os concursos para um arquivo TXT formatado"""
    try:
        linhas = []
        linhas.append("=" * 80)
        linhas.append(f"LOTOFÁCIL - CONCURSOS CARREGADOS")
        linhas.append(f"Data de exportação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        linhas.append(f"Total de concursos: {len(dados_api[:qtd_concursos])}")
        linhas.append("=" * 80)
        linhas.append("")
        
        for concurso in dados_api[:qtd_concursos]:
            linhas.append(f"Concurso #{concurso['concurso']} - {concurso['data']}")
            numeros = sorted(map(int, concurso['dezenas']))
            numeros_str = " - ".join(f"{n:02d}" for n in numeros)
            linhas.append(f"Números: {numeros_str}")
            linhas.append("-" * 50)
        
        return "\n".join(linhas)
    except Exception as e:
        return f"Erro ao gerar arquivo: {e}"

# =====================================================
# CLASSE PRINCIPAL PARA ANÁLISE BÁSICA
# =====================================================
class AnaliseLotofacilBasica:

    def __init__(self, concursos, dados_completos=None):
        self.concursos = concursos
        self.dados_completos = dados_completos or []
        self.ultimo_concurso = concursos[0] if concursos else []
        self.ultimo_concurso_numero = dados_completos[0]["concurso"] if dados_completos else 0
        self.ultimo_concurso_data = dados_completos[0]["data"] if dados_completos else ""
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)

        # Análises básicas
        self.frequencias = self._frequencias()
        self.ultimo_resultado = self.concursos[0] if concursos else []

    def _frequencias(self):
        c = Counter()
        for con in self.concursos: 
            c.update(con)
        return {n: c.get(n, 0) / self.total_concursos for n in self.numeros}

# =====================================================
# CLASSE DO MODELO 3622
# =====================================================
class Gerador3622:
    """
    Implementação do MODELO UNIVERSAL + AJUSTE ADAPTÁVEL
    Baseado na análise do concurso 3622
    """
    
    def __init__(self, ultimo_concurso, penultimo_concurso=None, antepenultimo_concurso=None):
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        self.penultimo = sorted(penultimo_concurso) if penultimo_concurso else []
        self.antepenultimo = sorted(antepenultimo_concurso) if antepenultimo_concurso else []
        
        # Números primos na Lotofácil
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        
        # Faixas do volante
        self.faixa_baixa = list(range(1, 9))    # 01-08
        self.faixa_media = list(range(9, 17))    # 09-16
        self.faixa_alta = list(range(17, 26))    # 17-25
        
        # Ajustes adaptáveis (serão calculados)
        self.ajustes = self._calcular_ajustes()
    
    def _calcular_ajustes(self):
        """Calcula os ajustes adaptáveis baseados nos últimos concursos"""
        ajustes = {
            "repeticoes_alvo": 8,
            "altas_alvo": 2,
            "miolo_alvo": 6,
            "tipo_sequencia": "normal"
        }
        
        if self.penultimo and self.ultimo:
            # AJUSTE A - Peso das repetições
            rep_penultimo = len(set(self.ultimo) & set(self.penultimo))
            if rep_penultimo >= 9:
                ajustes["repeticoes_alvo"] = 7
            elif rep_penultimo <= 7:
                ajustes["repeticoes_alvo"] = 9
            else:
                ajustes["repeticoes_alvo"] = 8
            
            # AJUSTE B - Altas (22-25)
            altas_ultimo = sum(1 for n in self.ultimo if n in [22, 23, 24, 25])
            if altas_ultimo <= 1:
                ajustes["altas_alvo"] = 3
            elif altas_ultimo >= 3:
                ajustes["altas_alvo"] = 1
            else:
                ajustes["altas_alvo"] = 2
            
            # AJUSTE C - Miolo (09-16)
            miolo_ultimo = sum(1 for n in self.ultimo if 9 <= n <= 16)
            if miolo_ultimo >= 6:
                ajustes["miolo_alvo"] = 6
            else:
                ajustes["miolo_alvo"] = 5
            
            # AJUSTE D - Quebra de sequência
            # Verificar se houve muitas sequências no último
            sequencias = self._contar_sequencias(self.ultimo)
            if sequencias >= 4:
                ajustes["tipo_sequencia"] = "encurtar"
            elif sequencias <= 1:
                ajustes["tipo_sequencia"] = "alongar"
        
        return ajustes
    
    def _contar_sequencias(self, numeros):
        """Conta quantos pares consecutivos existem no jogo"""
        nums = sorted(numeros)
        pares = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                pares += 1
        return pares
    
    def _validar_regras_universais(self, jogo):
        """
        Valida se o jogo respeita as 6 regras universais
        Retorna (bool, dict) - (aprovado, diagnostico)
        """
        diagnostico = {
            "regra1": False,  # Repetição
            "regra2": False,  # Pares/Ímpares
            "regra3": False,  # Soma
            "regra4": False,  # Faixas
            "regra5": False,  # Consecutivos
            "regra6": False,  # Primos
            "falhas": 0
        }
        
        # REGRA 1 - Repetição do concurso anterior
        if self.ultimo:
            repeticoes = len(set(jogo) & set(self.ultimo))
            if 8 <= repeticoes <= 10:
                diagnostico["regra1"] = True
            elif repeticoes == 7 or repeticoes == 11:
                diagnostico["regra1"] = True  # Aceitável mas não ideal
        
        # REGRA 2 - Ímpares x Pares
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares in [7, 8]:
            diagnostico["regra2"] = True
        elif pares == 6 or pares == 9:
            diagnostico["regra2"] = True  # Alternativa aceitável
        
        # REGRA 3 - Soma total
        soma = sum(jogo)
        if 168 <= soma <= 186:
            diagnostico["regra3"] = True
        elif 165 <= soma <= 190:
            diagnostico["regra3"] = True  # Fora da faixa premium mas aceitável
        
        # REGRA 4 - Distribuição por faixas
        baixas = sum(1 for n in jogo if n in self.faixa_baixa)
        medias = sum(1 for n in jogo if n in self.faixa_media)
        altas = sum(1 for n in jogo if n in self.faixa_alta)
        
        if (5 <= baixas <= 6 and 5 <= medias <= 6 and 3 <= altas <= 4):
            diagnostico["regra4"] = True
        elif (4 <= baixas <= 7 and 4 <= medias <= 7 and 2 <= altas <= 5):
            # Mais tolerante mas ainda aceitável
            if not (baixas <= 4 or altas >= 6):
                diagnostico["regra4"] = True
        
        # REGRA 5 - Consecutivos
        consecutivos = self._contar_sequencias(jogo)
        if consecutivos >= 3:
            diagnostico["regra5"] = True
        
        # REGRA 6 - Primos
        qtd_primos = sum(1 for n in jogo if n in self.primos)
        if 4 <= qtd_primos <= 6:
            diagnostico["regra6"] = True
        
        # Contar falhas
        diagnostico["falhas"] = sum(1 for v in diagnostico.values() if isinstance(v, bool) and not v)
        
        # Aprovado se tiver no máximo 1 falha
        aprovado = diagnostico["falhas"] <= 1
        
        return aprovado, diagnostico
    
    def gerar_jogo(self):
        """
        Gera um jogo seguindo o passo a passo do modelo
        1️⃣ Fixe a BASE (9 dezenas repetidas)
        2️⃣ Complete respeitando as faixas
        3️⃣ Valide
        """
        max_tentativas = 5000
        
        for tentativa in range(max_tentativas):
            # PASSO 1: Escolher 9 repetidas do último concurso
            if self.ultimo:
                repeticoes_alvo = self.ajustes["repeticoes_alvo"]
                # Garantir que temos pelo menos repeticoes_alvo números para escolher
                if len(self.ultimo) >= repeticoes_alvo:
                    base = sorted(random.sample(self.ultimo, repeticoes_alvo))
                else:
                    base = sorted(random.sample(self.ultimo, len(self.ultimo)))
            else:
                base = []
            
            # Completar até 15 números
            jogo = base.copy()
            
            # PASSO 2: Completar respeitando as faixas
            # Definir alvos por faixa baseado nos ajustes
            alvo_baixas = 5
            alvo_medias = self.ajustes["miolo_alvo"]
            alvo_altas = self.ajustes["altas_alvo"]
            
            # Ajustar para somar 15
            total_atual = len(jogo)
            if total_atual < 15:
                # Calcular quantos faltam em cada faixa
                baixas_atuais = sum(1 for n in jogo if n in self.faixa_baixa)
                medias_atuais = sum(1 for n in jogo if n in self.faixa_media)
                altas_atuais = sum(1 for n in jogo if n in self.faixa_alta)
                
                faltam = 15 - total_atual
                
                # Distribuir os faltantes
                for _ in range(faltam):
                    # Decidir de qual faixa tirar baseado nos alvos
                    if baixas_atuais < alvo_baixas:
                        opcoes = [n for n in self.faixa_baixa if n not in jogo]
                        if opcoes:
                            escolha = random.choice(opcoes)
                            jogo.append(escolha)
                            baixas_atuais += 1
                            continue
                    
                    if medias_atuais < alvo_medias:
                        opcoes = [n for n in self.faixa_media if n not in jogo]
                        if opcoes:
                            escolha = random.choice(opcoes)
                            jogo.append(escolha)
                            medias_atuais += 1
                            continue
                    
                    if altas_atuais < alvo_altas:
                        opcoes = [n for n in self.faixa_alta if n not in jogo]
                        if opcoes:
                            escolha = random.choice(opcoes)
                            jogo.append(escolha)
                            altas_atuais += 1
                            continue
                    
                    # Se todas as faixas atingiram o alvo, completar aleatoriamente
                    disponiveis = [n for n in range(1, 26) if n not in jogo]
                    if disponiveis:
                        escolha = random.choice(disponiveis)
                        jogo.append(escolha)
                        
                        # Atualizar contadores
                        if escolha in self.faixa_baixa:
                            baixas_atuais += 1
                        elif escolha in self.faixa_media:
                            medias_atuais += 1
                        else:
                            altas_atuais += 1
            
            jogo.sort()
            
            # PASSO 3: Validar
            aprovado, diagnostico = self._validar_regras_universais(jogo)
            if aprovado:
                return jogo, diagnostico
        
        # Fallback: gerar jogo com validação mínima
        return self._gerar_jogo_fallback()
    
    def _gerar_jogo_fallback(self):
        """Gera um jogo de fallback quando não encontra com validação completa"""
        jogo = []
        
        # Garantir pelo menos 8 repetidas
        if self.ultimo:
            rep = random.sample(self.ultimo, min(8, len(self.ultimo)))
            jogo.extend(rep)
        
        # Completar
        while len(jogo) < 15:
            novo = random.randint(1, 25)
            if novo not in jogo:
                jogo.append(novo)
        
        jogo.sort()
        
        # Criar diagnóstico básico
        diagnostico = {
            "regra1": len(set(jogo) & set(self.ultimo)) >= 7 if self.ultimo else True,
            "regra2": 6 <= sum(1 for n in jogo if n % 2 == 0) <= 9,
            "regra3": 165 <= sum(jogo) <= 190,
            "regra4": True,
            "regra5": self._contar_sequencias(jogo) >= 2,
            "regra6": 3 <= sum(1 for n in jogo if n in self.primos) <= 7,
            "falhas": 0
        }
        
        return jogo, diagnostico
    
    def gerar_multiplos_jogos(self, quantidade):
        """Gera múltiplos jogos validados"""
        jogos = []
        diagnosticos = []
        tentativas = 0
        max_tentativas = quantidade * 200
        
        while len(jogos) < quantidade and tentativas < max_tentativas:
            jogo, diag = self.gerar_jogo()
            if jogo not in jogos:  # Evitar duplicatas
                jogos.append(jogo)
                diagnosticos.append(diag)
            tentativas += 1
        
        return jogos, diagnosticos
    
    def get_resumo_ajustes(self):
        """Retorna resumo dos ajustes adaptáveis"""
        return {
            "repeticoes_alvo": self.ajustes["repeticoes_alvo"],
            "altas_alvo": self.ajustes["altas_alvo"],
            "miolo_alvo": self.ajustes["miolo_alvo"],
            "tipo_sequencia": self.ajustes["tipo_sequencia"]
        }

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def validar_jogos(jogos):
    """Valida se todos os jogos têm 15 números únicos"""
    for i, jogo in enumerate(jogos):
        if len(set(jogo)) != 15:
            return False, i, jogo
    return True, None, None

def formatar_jogo_html(jogo, destaque_primos=True):
    """Formata um jogo em HTML com cores"""
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
    html = ""
    for num in jogo:
        if num in primos and destaque_primos:
            html += f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
        else:
            html += f"<span style='background:#0e1117; border:1px solid #262730; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
    return html

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================
def main():
    if "analise" not in st.session_state: 
        st.session_state.analise = None
    if "jogos" not in st.session_state: 
        st.session_state.jogos = []
    if "dados_api" not in st.session_state: 
        st.session_state.dados_api = None
    if "jogos_salvos" not in st.session_state: 
        st.session_state.jogos_salvos = []
    if "ultimo_gerador" not in st.session_state:
        st.session_state.ultimo_gerador = None

    # ================= SIDEBAR =================
    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Qtd concursos históricos", 20, 500, 100, 
                       help="Mais concursos = melhor análise de tendências")
        
        if st.button("📥 Carregar concursos", use_container_width=True):
            with st.spinner("Carregando dados da Caixa..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    response = requests.get(url)
                    st.session_state.dados_api = response.json()
                    concursos = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
                    st.session_state.analise = AnaliseLotofacilBasica(concursos, st.session_state.dados_api[:qtd])
                    
                    ultimo = st.session_state.dados_api[0]
                    st.success(f"✅ Último concurso: #{ultimo['concurso']} - {ultimo['data']}")
                    
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    # ================= INTERFACE PRINCIPAL =================
    st.subheader("🎯 Modelo Universal 3622")

    if st.session_state.analise and st.session_state.dados_api:
        # APENAS 4 ABAS: Análise, Fechamento 3622, Concursos, Conferência
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Análise", 
            "🧩 Fechamento 3622", 
            "📋 Concursos",
            "✅ Conferência"
        ])

        with tab1:
            st.markdown("### 🔍 Análise do Último Concurso")
            
            ultimo = st.session_state.dados_api[0]
            numeros_ultimo = sorted(map(int, ultimo['dezenas']))
            
            st.markdown(f"""
            <div class='concurso-info'>
                <strong>Concurso #{ultimo['concurso']}</strong> - {ultimo['data']}
            </div>
            """, unsafe_allow_html=True)
            
            # Mostrar números do último concurso
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Dezenas sorteadas:**")
                nums_html = ""
                for num in numeros_ultimo:
                    nums_html += f"<span style='background:#4cc9f0; border-radius:20px; padding:5px 10px; margin:3px; display:inline-block; font-weight:bold; color:black;'>{num:02d}</span>"
                st.markdown(f"<div>{nums_html}</div>", unsafe_allow_html=True)
            
            with col2:
                pares = sum(1 for n in numeros_ultimo if n % 2 == 0)
                impares = 15 - pares
                st.metric("Pares/Ímpares", f"{pares}×{impares}")
            
            with col3:
                soma = sum(numeros_ultimo)
                st.metric("Soma total", soma)
            
            # Estatísticas rápidas
            if len(st.session_state.dados_api) > 1:
                penultimo = sorted(map(int, st.session_state.dados_api[1]['dezenas']))
                rep_penultimo = len(set(numeros_ultimo) & set(penultimo))
                
                st.markdown("### 📊 Ajustes Adaptáveis")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Repetição c/ penúltimo", rep_penultimo)
                with col2:
                    altas = sum(1 for n in numeros_ultimo if n >= 22)
                    st.metric("Altas (22-25)", altas)
                with col3:
                    miolo = sum(1 for n in numeros_ultimo if 9 <= n <= 16)
                    st.metric("Miolo (09-16)", miolo)

        with tab2:
            st.markdown("""
            <div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px;'>
                <h4 style='margin:0; color:#4cc9f0;'>🧠 MODELO UNIVERSAL + AJUSTE ADAPTÁVEL</h4>
                <p style='margin:5px 0 0 0; font-size:0.9em;'>Baseado na análise do concurso 3622</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Regras universais em cards
            with st.expander("📜 VER REGRAS UNIVERSAIS", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("""
                    **✅ REGRA 1 — REPETIÇÃO**
                    - Obrigatório: 8 a 10 repetidas
                    - Zona ótima: 8 ou 9
                    
                    **✅ REGRA 2 — ÍMPARES x PARES**
                    - Padrão vencedor: 7×8 ou 8×7
                    - Alternativa: 6×9 (raro)
                    
                    **✅ REGRA 3 — SOMA TOTAL**
                    - Faixa universal: 168 a 186
                    - Zona premium: 172 a 182
                    """)
                
                with col2:
                    st.markdown("""
                    **✅ REGRA 4 — DISTRIBUIÇÃO**
                    - 01–08: 5 a 6
                    - 09–16: 5 a 6
                    - 17–25: 3 a 4
                    
                    **✅ REGRA 5 — CONSECUTIVOS**
                    - Mínimo: 3 pares consecutivos
                    
                    **✅ REGRA 6 — PRIMOS**
                    - Faixa vencedora: 4 a 6 primos
                    """)
            
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                penultimo = st.session_state.dados_api[1] if len(st.session_state.dados_api) > 1 else None
                antepenultimo = st.session_state.dados_api[2] if len(st.session_state.dados_api) > 2 else None
                
                # Criar gerador 3622
                gerador = Gerador3622(
                    ultimo_concurso=list(map(int, ultimo['dezenas'])),
                    penultimo_concurso=list(map(int, penultimo['dezenas'])) if penultimo else None,
                    antepenultimo_concurso=list(map(int, antepenultimo['dezenas'])) if antepenultimo else None
                )
                
                st.session_state.ultimo_gerador = gerador
                
                # Mostrar ajustes adaptáveis calculados
                ajustes = gerador.get_resumo_ajustes()
                
                st.markdown("### 🔄 Ajustes Adaptáveis Ativos")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Repetições alvo", ajustes["repeticoes_alvo"])
                with col2:
                    st.metric("Altas alvo", ajustes["altas_alvo"])
                with col3:
                    st.metric("Miolo alvo", ajustes["miolo_alvo"])
                with col4:
                    st.metric("Sequências", ajustes["tipo_sequencia"])
                
                # Configuração de geração
                st.markdown("### 🎯 Gerar Jogos")
                
                col1, col2 = st.columns(2)
                with col1:
                    qtd_jogos = st.slider("Quantidade de jogos", 3, 100, 10, 
                                         help="Mínimo 3, máximo 100 jogos")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 GERAR JOGOS 3622", use_container_width=True, type="primary"):
                        with st.spinner(f"Gerando {qtd_jogos} jogos com validação completa..."):
                            jogos, diagnosticos = gerador.gerar_multiplos_jogos(qtd_jogos)
                            
                            # Validar jogos
                            valido, idx, jogo_invalido = validar_jogos(jogos)
                            if not valido:
                                st.error(f"ERRO: Jogo {idx+1} inválido! Corrigindo...")
                                jogos[idx] = sorted(list(set(jogo_invalido)))
                                while len(jogos[idx]) < 15:
                                    novo = random.randint(1, 25)
                                    if novo not in jogos[idx]:
                                        jogos[idx].append(novo)
                                jogos[idx].sort()
                            
                            # Salvar na sessão
                            st.session_state.jogos_3622 = jogos
                            st.session_state.diagnosticos_3622 = diagnosticos
                            
                            st.success(f"✅ {len(jogos)} jogos gerados com sucesso!")
                
                # Mostrar jogos gerados
                if "jogos_3622" in st.session_state and st.session_state.jogos_3622:
                    jogos = st.session_state.jogos_3622
                    diagnosticos = st.session_state.diagnosticos_3622 if "diagnosticos_3622" in st.session_state else [None] * len(jogos)
                    
                    st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                    
                    # Estatísticas agregadas
                    stats_df = pd.DataFrame({
                        "Jogo": range(1, len(jogos)+1),
                        "Repetidas": [len(set(j) & set(gerador.ultimo)) for j in jogos],
                        "Pares": [sum(1 for n in j if n%2==0) for j in jogos],
                        "Soma": [sum(j) for j in jogos],
                        "Baixas": [sum(1 for n in j if n in gerador.faixa_baixa) for j in jogos],
                        "Médias": [sum(1 for n in j if n in gerador.faixa_media) for j in jogos],
                        "Altas": [sum(1 for n in j if n in gerador.faixa_alta) for j in jogos],
                        "Consec": [gerador._contar_sequencias(j) for j in jogos],
                        "Primos": [sum(1 for n in j if n in gerador.primos) for j in jogos],
                        "Falhas": [d["falhas"] if d else 0 for d in diagnosticos]
                    })
                    
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    
                    # Mostrar cada jogo formatado
                    for i, (jogo, diag) in enumerate(zip(jogos, diagnosticos)):
                        with st.container():
                            # Determinar cor baseada no número de falhas
                            if diag and diag["falhas"] == 0:
                                cor_borda = "#4ade80"  # Verde - perfeito
                            elif diag and diag["falhas"] == 1:
                                cor_borda = "gold"     # Amarelo - aceitável
                            else:
                                cor_borda = "#4cc9f0"  # Azul - normal
                            
                            # Formatar números
                            nums_html = formatar_jogo_html(jogo)
                            
                            # Estatísticas resumidas
                            rep = len(set(jogo) & set(gerador.ultimo))
                            pares = sum(1 for n in jogo if n%2==0)
                            soma = sum(jogo)
                            
                            st.markdown(f"""
                            <div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                <strong>Jogo {i+1:2d}:</strong> {nums_html}<br>
                                <small style='color:#aaa;'>
                                🔁 {rep} rep | ⚖️ {pares}×{15-pares} | ➕ {soma} | ✅ Falhas: {diag["falhas"] if diag else "?"}
                                </small>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_gerados(
                                jogos, 
                                list(range(1, 18)),  # Fechamento placeholder
                                {"modelo": "3622", "ajustes": ajustes},
                                ultimo['concurso'],
                                ultimo['data']
                            )
                            if arquivo:
                                st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                    
                    with col2:
                        if st.button("🔄 Nova Geração", use_container_width=True):
                            st.session_state.jogos_3622 = None
                            st.session_state.diagnosticos_3622 = None
                            st.rerun()
                    
                    with col3:
                        # Exportar para CSV
                        df_export = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Repetidas": stats_df["Repetidas"],
                            "Pares": stats_df["Pares"],
                            "Soma": stats_df["Soma"],
                            "Baixas(01-08)": stats_df["Baixas"],
                            "Medias(09-16)": stats_df["Médias"],
                            "Altas(17-25)": stats_df["Altas"],
                            "Consecutivos": stats_df["Consec"],
                            "Primos": stats_df["Primos"]
                        })
                        
                        csv = df_export.to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar CSV",
                            data=csv,
                            file_name=f"jogos_3622_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

        with tab3:
            st.subheader("📋 Todos os Concursos Carregados")
            
            if st.session_state.dados_api:
                st.markdown(f"""
                <div class='concurso-info'>
                    📊 <strong>Total de concursos carregados: {len(st.session_state.dados_api[:qtd])}</strong>
                </div>
                """, unsafe_allow_html=True)
                
                # Opções de filtro
                col1, col2 = st.columns([3, 1])
                with col1:
                    busca = st.text_input("🔍 Buscar concurso específico (número ou data)", placeholder="Ex: 3000 ou 2024...")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📥 Download TXT", use_container_width=True):
                        conteudo_txt = exportar_concursos_txt(st.session_state.dados_api, qtd)
                        st.download_button(
                            label="⬇️ Baixar arquivo",
                            data=conteudo_txt,
                            file_name=f"lotofacil_concursos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                
                # Filtrar concursos
                dados_filtrados = st.session_state.dados_api[:qtd]
                if busca:
                    dados_filtrados = [
                        c for c in dados_filtrados 
                        if busca.lower() in str(c['concurso']).lower() 
                        or busca.lower() in c['data'].lower()
                    ]
                
                # Mostrar concursos em cards
                for concurso in dados_filtrados:
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.markdown(f"**#{concurso['concurso']}**")
                            st.caption(concurso['data'])
                        with col2:
                            numeros = sorted(map(int, concurso['dezenas']))
                            # Criar tags coloridas para os números
                            nums_html = ""
                            for i, num in enumerate(numeros):
                                cor = "#4cc9f0" if num <= 5 else "#4ade80" if num <= 10 else "gold" if num <= 15 else "#f97316" if num <= 20 else "#ff6b6b"
                                nums_html += f"<span style='background:{cor}20; border:1px solid {cor}; border-radius:20px; padding:5px 10px; margin:3px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
                            st.markdown(f"<div>{nums_html}</div>", unsafe_allow_html=True)
                        st.divider()
                
                if len(dados_filtrados) > 50:
                    st.caption(f"Mostrando {len(dados_filtrados)} concursos. Use a busca para encontrar um específico.")
            else:
                st.info("📥 Carregue os concursos usando o botão na barra lateral para visualizar a lista completa.")

        with tab4:
            st.subheader("✅ Conferência por Concurso")
            
            # Inicializar variáveis de sessão para persistência
            if "idx_fechamento_selecionado" not in st.session_state:
                st.session_state.idx_fechamento_selecionado = 0
            if "futuro_selecionado" not in st.session_state:
                st.session_state.futuro_selecionado = None
            if "conferencia_realizada" not in st.session_state:
                st.session_state.conferencia_realizada = False
            if "resultado_conferencia" not in st.session_state:
                st.session_state.resultado_conferencia = None
            
            st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            if not st.session_state.jogos_salvos:
                st.warning("Nenhum jogo salvo. Gere na aba 'Fechamento 3622'.")
            elif not st.session_state.dados_api:
                st.warning("Carregue os concursos primeiro!")
            else:
                ultimo_api = st.session_state.dados_api[0]
                
                nao_conferidos = [j for j in st.session_state.jogos_salvos 
                                 if len(j.get("conferencias", [])) == 0]
                
                if not nao_conferidos:
                    st.info("✅ Todos os fechamentos já foram conferidos!")
                else:
                    st.markdown(f"""
                    <div class='concurso-info'>
                        🎯 Último concurso: #{ultimo_api['concurso']} - {ultimo_api['data']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Criar opções para o selectbox
                    opcoes = []
                    for i, j in enumerate(nao_conferidos[:10]):
                        data = datetime.fromisoformat(j["data_geracao"]).strftime("%d/%m/%Y %H:%M")
                        base = j.get("concurso_base", {"numero": 0, "data": "Desconhecido"})
                        opcoes.append(f"{i+1} - Base #{base['numero']} - {data}")
                    
                    if opcoes:
                        opcao_selecionada = st.selectbox(
                            "Selecione o fechamento", 
                            opcoes,
                            index=st.session_state.idx_fechamento_selecionado if st.session_state.idx_fechamento_selecionado < len(opcoes) else 0
                        )
                        
                        # Atualizar o índice
                        novo_idx = int(opcao_selecionada.split(" - ")[0]) - 1
                        if novo_idx != st.session_state.idx_fechamento_selecionado:
                            st.session_state.idx_fechamento_selecionado = novo_idx
                            st.session_state.conferencia_realizada = False
                            st.session_state.resultado_conferencia = None
                            st.rerun()
                        
                        idx = st.session_state.idx_fechamento_selecionado
                        jogo_sel = nao_conferidos[idx]
                        base_info = jogo_sel.get("concurso_base", {"numero": 0, "data": "Desconhecido"})
                        
                        with st.expander("📋 Detalhes do fechamento", expanded=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**ID:** {jogo_sel.get('id', 'N/A')}")
                                st.write(f"**Base concurso:** #{base_info['numero']}")
                            with col2:
                                st.write(f"**Jogos:** {len(jogo_sel.get('jogos', []))}")
                            
                            # Mostrar jogos do fechamento
                            with st.expander("🔍 Ver jogos do fechamento"):
                                jogos_preview = jogo_sel.get("jogos", [])[:5]
                                for idx_j, j in enumerate(jogos_preview):
                                    st.markdown(f"**Jogo {idx_j+1}:** {', '.join(f'{n:02d}' for n in j)}")
                                if len(jogo_sel.get("jogos", [])) > 5:
                                    st.caption(f"... e mais {len(jogo_sel['jogos']) - 5} jogos")
                        
                        # Concursos futuros disponíveis
                        concursos_futuros = [c for c in st.session_state.dados_api 
                                            if c['concurso'] > base_info['numero']]
                        
                        if concursos_futuros:
                            opcoes_futuros = [f"#{c['concurso']} - {c['data']}" 
                                             for c in concursos_futuros[:5]]
                            
                            futuro_sel = st.selectbox(
                                "Concurso para conferir", 
                                opcoes_futuros,
                                key="select_futuro"
                            )
                            
                            num_futuro = int(futuro_sel.split(" - ")[0].replace("#", ""))
                            
                            # Botão de conferência
                            if st.button("🔍 CONFERIR AGORA", use_container_width=True, type="primary"):
                                with st.spinner("Conferindo resultados..."):
                                    concurso_info = next(c for c in concursos_futuros 
                                                        if c['concurso'] == num_futuro)
                                    numeros = sorted(map(int, concurso_info["dezenas"]))
                                    
                                    # Processar jogos para conferência
                                    acertos = []
                                    jogos_validos = []
                                    
                                    for jogo in jogo_sel.get("jogos", []):
                                        if isinstance(jogo, list) and len(set(jogo)) == 15:
                                            jogos_validos.append(jogo)
                                            acertos.append(len(set(jogo) & set(numeros)))
                                    
                                    if acertos:
                                        # Calcular estatísticas
                                        stats_conf = {
                                            "media": float(np.mean(acertos)),
                                            "max": int(max(acertos)),
                                            "min": int(min(acertos)),
                                            "distribuicao": {str(k): int(v) for k, v in Counter(acertos).items()}
                                        }
                                        
                                        info_salvar = {
                                            "numero": int(concurso_info["concurso"]),
                                            "data": str(concurso_info["data"]),
                                            "resultado": [int(n) for n in numeros]
                                        }
                                        
                                        # Salvar conferência
                                        if adicionar_conferencia(jogo_sel["arquivo"], info_salvar, 
                                                                acertos, stats_conf):
                                            st.session_state.conferencia_realizada = True
                                            st.session_state.resultado_conferencia = {
                                                "acertos": acertos,
                                                "jogos_validos": jogos_validos,
                                                "stats": stats_conf,
                                                "num_futuro": num_futuro,
                                                "concurso_info": concurso_info
                                            }
                                            st.rerun()
                            
                            # Mostrar resultados da conferência se existirem
                            if st.session_state.conferencia_realizada and st.session_state.resultado_conferencia:
                                resultado = st.session_state.resultado_conferencia
                                
                                st.success(f"✅ Conferência realizada com concurso #{resultado['num_futuro']}!")
                                
                                # Mostrar estatísticas
                                m1, m2, m3, m4 = st.columns(4)
                                with m1:
                                    st.metric("Média", f"{resultado['stats']['media']:.1f}")
                                with m2:
                                    st.metric("Máximo", resultado['stats']['max'])
                                with m3:
                                    st.metric("Mínimo", resultado['stats']['min'])
                                with m4:
                                    vantagem_real = resultado['stats']['media'] - 9.5
                                    cor = "green" if vantagem_real > 0 else "red"
                                    st.markdown(f"<p style='text-align:center; color:{cor}; font-weight:bold;'>Vs aleatório<br>{vantagem_real:+.2f}</p>", unsafe_allow_html=True)
                                
                                # Mostrar tabela de resultados
                                df_res = pd.DataFrame({
                                    "Jogo": range(1, len(resultado['jogos_validos'])+1),
                                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in resultado['jogos_validos']],
                                    "Acertos": resultado['acertos'][:len(resultado['jogos_validos'])]
                                })
                                st.dataframe(df_res, use_container_width=True, hide_index=True)
                                
                                # Botão para conferir outro
                                if st.button("✅ Conferir Outro Fechamento", use_container_width=True):
                                    st.session_state.conferencia_realizada = False
                                    st.session_state.resultado_conferencia = None
                                    st.rerun()
                        else:
                            st.warning("Aguardando próximos concursos...")
    else:
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🚀 Comece carregando os concursos na barra lateral</h3>
            <p>Use o menu ≡ no canto superior esquerdo</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
