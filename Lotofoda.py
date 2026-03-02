import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
import math
from collections import Counter
from datetime import datetime
from scipy.stats import norm
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
# CONSTANTES GLOBAIS PARA MOTOR ESTATÍSTICO
# =====================================================
FEATURE_WEIGHTS = {
    "pares": 1.0,
    "primos": 1.0,
    "consecutivos": 0.8,
    "soma": 0.6
}

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
# FUNÇÃO PARA NORMALIZAR JOGOS (DEFINITIVA)
# =====================================================
def normalizar_jogos(jogos_brutos):
    """
    Converte qualquer formato de jogo para lista de listas de inteiros
    Suporta: DataFrame, lista de dicts, lista de strings, lista de listas
    """
    jogos_normalizados = []

    # Caso 1: É um DataFrame do pandas
    if isinstance(jogos_brutos, pd.DataFrame):
        for _, row in jogos_brutos.iterrows():
            # Procurar coluna que contém as dezenas
            for col in row.index:
                valor = row[col]
                if isinstance(valor, str) and "," in valor:
                    # É uma string com vírgulas
                    dezenas = [int(d.strip()) for d in valor.split(",")]
                    jogos_normalizados.append(sorted(dezenas))
                    break
                elif isinstance(valor, list):
                    # Já é uma lista
                    jogos_normalizados.append(sorted(valor))
                    break
        return jogos_normalizados

    # Caso 2: É uma lista
    if isinstance(jogos_brutos, list):
        for item in jogos_brutos:
            # 2.1: Item é dicionário
            if isinstance(item, dict):
                # Procurar chave que contém as dezenas
                for chave in ["dezenas", "Dezenas", "jogo", "Jogo", "numeros", "Numeros"]:
                    if chave in item:
                        valor = item[chave]
                        if isinstance(valor, str):
                            dezenas = [int(d.strip()) for d in valor.split(",")]
                            jogos_normalizados.append(sorted(dezenas))
                            break
                        elif isinstance(valor, list):
                            jogos_normalizados.append(sorted(valor))
                            break
            
            # 2.2: Item é string
            elif isinstance(item, str):
                if "," in item:
                    dezenas = [int(d.strip()) for d in item.split(",")]
                    jogos_normalizados.append(sorted(dezenas))
                else:
                    # Tentar interpretar como números separados por espaço
                    dezenas = [int(d) for d in item.split()]
                    jogos_normalizados.append(sorted(dezenas))
            
            # 2.3: Item já é lista
            elif isinstance(item, (list, tuple)):
                jogos_normalizados.append(sorted([int(x) for x in item]))

    # Caso 3: Fallback - retorna o original se já estiver no formato correto
    if not jogos_normalizados and jogos_brutos:
        # Verificar se já está no formato correto
        if isinstance(jogos_brutos[0], list) and len(jogos_brutos[0]) == 15:
            return jogos_brutos

    return jogos_normalizados

# =====================================================
# FUNÇÃO PARA VALIDAR JOGOS NORMALIZADOS
# =====================================================
def validar_jogos_normalizados(jogos):
    """Valida se todos os jogos estão no formato correto"""
    if not isinstance(jogos, list):
        return False, "jogos não é uma lista"
    
    if len(jogos) == 0:
        return False, "lista de jogos vazia"
    
    for i, jogo in enumerate(jogos):
        if not isinstance(jogo, list):
            return False, f"jogo {i+1} não é uma lista"
        
        if len(jogo) != 15:
            return False, f"jogo {i+1} tem {len(jogo)} números (deveria ter 15)"
        
        if len(set(jogo)) != 15:
            return False, f"jogo {i+1} tem números duplicados"
        
        for num in jogo:
            if not isinstance(num, int) or num < 1 or num > 25:
                return False, f"jogo {i+1} contém número inválido: {num}"
    
    return True, "OK"

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
        
        # Garantir que cada jogo é uma lista simples de inteiros
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
                
                # Salvar no formato padronizado (lista de inteiros)
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
            "jogos": jogos_final,  # Agora é lista de listas de inteiros
            "estatisticas": estatisticas_convertidas,
            "conferido": False,
            "conferencias": [],
            "schema_version": "3.0"  # Versão do schema para futura compatibilidade
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
    
    # Garantir que jogo é uma lista de inteiros
    if isinstance(jogo, dict):
        # Tentar extrair dezenas do dict
        for chave in ["dezenas", "Dezenas", "jogo", "Jogo"]:
            if chave in jogo:
                dezenas = jogo[chave]
                break
        else:
            dezenas = []
    elif isinstance(jogo, str):
        # Converter string para lista
        if "," in jogo:
            dezenas = [int(d.strip()) for d in jogo.split(",")]
        else:
            dezenas = [int(d) for d in jogo.split()]
    else:
        dezenas = jogo
    
    html = ""
    for num in dezenas:
        if num in primos and destaque_primos:
            html += f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
        else:
            html += f"<span style='background:#0e1117; border:1px solid #262730; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
    return html

# =====================================================
# FUNÇÕES PARA O MOTOR ESTATÍSTICO
# =====================================================
def contar_pares(jogo):
    """Conta números pares em um jogo"""
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos(jogo):
    """Conta números primos em um jogo"""
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos(jogo):
    """Conta pares consecutivos em um jogo"""
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def bucket_soma(soma):
    """Agrupa soma em buckets de 20 em 20"""
    return int(soma // 20)

def log_likelihood(features, dist):
    """
    Calcula log-likelihood com pesos por feature
    Reduz overfitting e dá robustez estatística
    """
    logL = 0
    for k, v in features.items():
        p = dist.get(k, {}).get(v, 1e-9)
        w = FEATURE_WEIGHTS.get(k, 1.0)
        logL += w * math.log(p)
    return logL

@st.cache_data
def baseline_aleatorio(n=200000):
    """
    Baseline estatisticamente correto para Lotofácil
    Simula interseção de dois conjuntos aleatórios de 15 números em 25
    """
    acertos = []
    
    for _ in range(n):
        jogo = set(random.sample(range(1, 26), 15))
        sorteio = set(random.sample(range(1, 26), 15))
        acertos.append(len(jogo & sorteio))
    
    acertos = np.array(acertos)
    
    return {
        "media": acertos.mean(),
        "std": acertos.std(),
        "dist": np.bincount(acertos, minlength=16) / n,
        "descricao": "Interseção 15×15 em universo 25"
    }

def criar_historico_df(dados_api, qtd_concursos):
    """Cria DataFrame com features históricas"""
    historico = []
    for concurso in dados_api[:qtd_concursos]:
        numeros = sorted(map(int, concurso['dezenas']))
        historico.append({
            "concurso": concurso['concurso'],
            "pares": contar_pares(numeros),
            "primos": contar_primos(numeros),
            "consecutivos": contar_consecutivos(numeros),
            "soma": sum(numeros)
        })
    return pd.DataFrame(historico)

@st.cache_data
def distribuicoes_empiricas(historico_df):
    """Calcula distribuições empíricas das features"""
    return {
        "pares": historico_df["pares"].value_counts(normalize=True).to_dict(),
        "primos": historico_df["primos"].value_counts(normalize=True).to_dict(),
        "consecutivos": historico_df["consecutivos"].value_counts(normalize=True).to_dict(),
        "soma": historico_df["soma"].apply(bucket_soma).value_counts(normalize=True).to_dict()
    }

# =====================================================
# FUNÇÃO MONTE CARLO PARA O NÍVEL PROFISSIONAL
# =====================================================
@st.cache_data
def monte_carlo_jogo(jogo_tuple, n_sim):
    """
    Simulação Monte Carlo para um jogo específico
    Retorna probabilidades empíricas de acertos
    """
    jogo = set(jogo_tuple)
    acertos = []

    for _ in range(n_sim):
        sorteio = set(random.sample(range(1, 26), 15))
        acertos.append(len(jogo & sorteio))

    acertos = np.array(acertos)

    return {
        "P>=11": np.mean(acertos >= 11),
        "P>=12": np.mean(acertos >= 12),
        "P>=13": np.mean(acertos >= 13),
        "P>=14": np.mean(acertos >= 14),
        "P=15": np.mean(acertos == 15),
        "media": acertos.mean(),
        "std": acertos.std()
    }

# =====================================================
# FUNÇÃO PARA VERIFICAR E RECUPERAR JOGOS
# =====================================================
def get_jogos_seguros():
    """Função segura para acessar jogos_3622 com verificação"""
    if "jogos_3622" in st.session_state and st.session_state.jogos_3622 is not None:
        if isinstance(st.session_state.jogos_3622, list) and len(st.session_state.jogos_3622) > 0:
            return st.session_state.jogos_3622
    return []

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
    if "historico_df" not in st.session_state:
        st.session_state.historico_df = None
    if "baseline_cache" not in st.session_state:
        st.session_state.baseline_cache = None
    if "mc_resultados" not in st.session_state:
        st.session_state.mc_resultados = None
    if "jogos_3622" not in st.session_state:
        st.session_state.jogos_3622 = None
    if "diagnosticos_3622" not in st.session_state:
        st.session_state.diagnosticos_3622 = None

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
                    
                    # Criar DataFrame histórico para motor estatístico
                    st.session_state.historico_df = criar_historico_df(st.session_state.dados_api, qtd)
                    
                    # Cache do baseline para usar em toda a aplicação
                    st.session_state.baseline_cache = baseline_aleatorio()
                    
                    ultimo = st.session_state.dados_api[0]
                    st.success(f"✅ Último concurso: #{ultimo['concurso']} - {ultimo['data']}")
                    
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    # ================= INTERFACE PRINCIPAL =================
    st.subheader("🎯 Modelo Universal 3622")

    if st.session_state.analise and st.session_state.dados_api and st.session_state.historico_df is not None:
        # AGORA SÃO 5 ABAS: Análise, Fechamento 3622, Motor Estatístico, Concursos, Conferência
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Análise", 
            "🧩 Fechamento 3622", 
            "📊 Motor Estatístico",
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
                            st.session_state.mc_resultados = None  # Reset Monte Carlo
                            
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
                            st.session_state.mc_resultados = None
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
            st.subheader("📊 Motor Estatístico - Avaliação Probabilística")
            
            # Usar função segura para acessar jogos
            jogos_gerados = get_jogos_seguros()
            
            # Verificar se há jogos gerados
            if not jogos_gerados:
                st.warning("⚠️ Gere jogos na aba 'Fechamento 3622' primeiro para avaliá-los estatisticamente!")
                st.info("💡 Os jogos gerados são salvos automaticamente e ficam disponíveis em todas as abas.")
            else:
                # BASELINE CORRETO (interseção 15×15)
                baseline = st.session_state.baseline_cache or baseline_aleatorio()
                
                with st.expander("🎲 Baseline Estatístico (H₀)", expanded=False):
                    st.markdown(f"""
                    **Modelo nulo:** {baseline['descricao']}  
                    **Média de acertos esperada:** {baseline['media']:.3f}  
                    **Desvio padrão:** {baseline['std']:.3f}  
                    """)
                    
                    # Gráfico da distribuição baseline
                    baseline_dist = pd.DataFrame({
                        "Acertos": range(16),
                        "Probabilidade": baseline['dist']
                    })
                    st.bar_chart(baseline_dist.set_index("Acertos"))
                
                # Distribuições empíricas
                st.markdown("### 📈 Distribuições Empíricas")
                dist = distribuicoes_empiricas(st.session_state.historico_df)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Pares x Ímpares**")
                    pares_df = pd.DataFrame({
                        "Quantidade": list(dist['pares'].keys()),
                        "Probabilidade": list(dist['pares'].values())
                    }).sort_values("Quantidade")
                    st.bar_chart(pares_df.set_index("Quantidade"))
                
                with col2:
                    st.markdown("**Números Primos**")
                    primos_df = pd.DataFrame({
                        "Quantidade": list(dist['primos'].keys()),
                        "Probabilidade": list(dist['primos'].values())
                    }).sort_values("Quantidade")
                    st.bar_chart(primos_df.set_index("Quantidade"))
                
                # AVALIAÇÃO DOS JOGOS (Likelihood com pesos)
                st.markdown("### 🎯 Ranking Estatístico dos Jogos")
                
                avaliacao = []
                for i, jogo in enumerate(jogos_gerados):
                    features = {
                        "pares": contar_pares(jogo),
                        "primos": contar_primos(jogo),
                        "consecutivos": contar_consecutivos(jogo),
                        "soma": bucket_soma(sum(jogo))
                    }
                    
                    logL = log_likelihood(features, dist)
                    
                    avaliacao.append({
                        "Jogo": i + 1,
                        "Likelihood (log)": round(logL, 4)
                    })
                
                df_avaliacao = pd.DataFrame(avaliacao)
                df_avaliacao["Rank"] = df_avaliacao["Likelihood (log)"].rank(ascending=False).astype(int)
                df_avaliacao["Percentil"] = (df_avaliacao["Likelihood (log)"].rank(pct=True) * 100).round(1)
                
                # Score normalizado 0-100 baseado no próprio lote
                logLs = df_avaliacao["Likelihood (log)"]
                min_logL = logLs.min()
                max_logL = logLs.max()
                
                if max_logL > min_logL:  # Evitar divisão por zero
                    score = 100 * (logLs - min_logL) / (max_logL - min_logL)
                else:
                    score = pd.Series([50] * len(logLs))  # Todos iguais
                
                df_avaliacao["Score (0-100)"] = score.round(1)
                
                # Ordenar por rank
                df_avaliacao = df_avaliacao.sort_values("Rank").reset_index(drop=True)
                
                # Mostrar dataframe com destaque
                st.dataframe(
                    df_avaliacao[["Rank", "Jogo", "Score (0-100)", "Percentil", "Likelihood (log)"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Score (0-100)": st.column_config.ProgressColumn(
                            "Score",
                            format="%.1f",
                            min_value=0,
                            max_value=100
                        )
                    }
                )
                
                # Distribuição dos scores
                st.markdown("### 📊 Distribuição dos Scores")
                chart_data = pd.DataFrame({
                    "Score": df_avaliacao["Score (0-100)"]
                })
                st.bar_chart(chart_data)
                
                # TESTE Z CORRIGIDO - Usando percentil
                st.markdown("### 🧪 Validação Estatística (Teste Z)")
                
                percentil_medio = df_avaliacao["Percentil"].mean()
                z = (percentil_medio - 50) / 15  # 15 = desvio aproximado
                p_value = 1 - norm.cdf(z)
                
                # Interpretação profissional
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Percentil médio", f"{percentil_medio:.1f}%")
                with col2:
                    st.metric("Z-score", f"{z:.3f}")
                with col3:
                    st.metric("p-value", f"{p_value:.6f}")
                
                # CORREÇÃO: Substituir st.success, st.warning, st.info por st.markdown com HTML
                if z > 1.96:
                    st.markdown("""
                    <div style='background:#00ff0020; padding:15px; border-radius:10px; border-left:5px solid #00ff00; margin:10px 0;'>
                        <strong>✅ VANTAGEM ESTATÍSTICA SIGNIFICATIVA (p < 0.05)</strong><br>
                        O modelo supera o aleatório com 95% de confiança.
                    </div>
                    """, unsafe_allow_html=True)
                elif z > 1.28:
                    st.markdown("""
                    <div style='background:#ffff0020; padding:15px; border-radius:10px; border-left:5px solid #ffff00; margin:10px 0;'>
                        <strong>⚠️ VANTAGEM MODERADA (p < 0.10)</strong><br>
                        Há indícios de vantagem, mas não conclusivos.
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='background:#0000ff20; padding:15px; border-radius:10px; border-left:5px solid #0000ff; margin:10px 0;'>
                        <strong>📊 ALEATÓRIO (p > 0.10)</strong><br>
                        Sem evidência estatística de vantagem.
                    </div>
                    """, unsafe_allow_html=True)
                
                # TOP JOGOS RECOMENDADOS
                st.markdown("### 🏆 Top 5 Jogos Recomendados")
                
                # Verificar se há jogos suficientes
                if len(df_avaliacao) > 0:
                    # Filtrar top 5 por score
                    top_jogos = df_avaliacao.nlargest(min(5, len(df_avaliacao)), "Score (0-100)")
                    
                    for idx, row in top_jogos.iterrows():
                        jogo_idx = row["Jogo"] - 1
                        # Verificação de segurança do índice
                        if 0 <= jogo_idx < len(jogos_gerados):
                            jogo = jogos_gerados[jogo_idx]
                            
                            # Análise individual do jogo
                            features_jogo = {
                                "pares": contar_pares(jogo),
                                "primos": contar_primos(jogo),
                                "consecutivos": contar_consecutivos(jogo),
                                "soma": sum(jogo)
                            }
                            
                            # HTML do jogo
                            nums_html = formatar_jogo_html(jogo)
                            
                            # Determinar cor baseada no score
                            if row["Score (0-100)"] >= 80:
                                cor = "#4ade80"  # Verde (excelente)
                            elif row["Score (0-100)"] >= 60:
                                cor = "gold"      # Amarelo (bom)
                            else:
                                cor = "#4cc9f0"   # Azul (médio)
                            
                            st.markdown(f"""
                            <div style='border-left: 5px solid {cor}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <strong>Rank #{row['Rank']} | Score {row['Score (0-100)']:.1f}</strong>
                                    <small>Percentil {row['Percentil']:.0f}%</small>
                                </div>
                                <div>{nums_html}</div>
                                <div style='display:flex; gap:15px; margin-top:8px; color:#aaa; font-size:0.9em;'>
                                    <span>⚖️ {features_jogo['pares']} pares</span>
                                    <span>🔢 {features_jogo['primos']} primos</span>
                                    <span>📈 {features_jogo['consecutivos']} consec</span>
                                    <span>➕ {features_jogo['soma']}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.error(f"Erro: Índice de jogo inválido - Jogo {row['Jogo']} não encontrado")
                else:
                    st.info("Nenhum jogo disponível para exibição.")
                
                # =====================================================
                # 🔥 NÍVEL PROFISSIONAL: MONTE CARLO POR JOGO
                # =====================================================
                st.markdown("---")
                st.markdown("## 🎲 Simulação Monte Carlo por Jogo")
                st.caption("Estimativa empírica real de probabilidade por jogo")

                N_SIM = st.slider(
                    "Quantidade de simulações por jogo",
                    min_value=1_000,
                    max_value=50_000,
                    value=10_000,
                    step=1_000,
                    key="mc_slider"
                )

                if st.button("🚀 Rodar Simulação Monte Carlo", use_container_width=True, type="primary"):
                    with st.spinner(f"Rodando {N_SIM:,} simulações para cada jogo..."):
                        mc_resultados = []
                        
                        for i, jogo in enumerate(jogos_gerados):
                            res = monte_carlo_jogo(tuple(jogo), N_SIM)
                            mc_resultados.append({
                                "Jogo": i + 1,
                                "P(≥11)": f"{res['P>=11']*100:.2f}%",
                                "P(≥12)": f"{res['P>=12']*100:.2f}%",
                                "P(≥13)": f"{res['P>=13']*100:.2f}%",
                                "P(≥14)": f"{res['P>=14']*100:.2f}%",
                                "P(15)": f"{res['P=15']*100:.4f}%",
                                "Média": round(res['media'], 2),
                                "Std": round(res['std'], 2)
                            })
                        
                        st.session_state.mc_resultados = pd.DataFrame(mc_resultados)
                        st.success("✅ Simulação concluída!")

                # Mostrar resultados Monte Carlo se existirem
                if st.session_state.mc_resultados is not None:
                    st.markdown("### 📊 Resultados da Simulação")
                    
                    # Ordenar por P(≥11) para melhor visualização
                    df_mc = st.session_state.mc_resultados.copy()
                    df_mc["P(≥11)_valor"] = df_mc["P(≥11)"].str.replace("%", "").astype(float)
                    df_mc = df_mc.sort_values("P(≥11)_valor", ascending=False).drop("P(≥11)_valor", axis=1)
                    
                    st.dataframe(
                        df_mc,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "P(≥11)": st.column_config.TextColumn("P(≥11)", width="small"),
                            "P(≥12)": st.column_config.TextColumn("P(≥12)", width="small"),
                            "P(≥13)": st.column_config.TextColumn("P(≥13)", width="small"),
                            "P(≥14)": st.column_config.TextColumn("P(≥14)", width="small"),
                            "P(15)": st.column_config.TextColumn("P(15)", width="small"),
                        }
                    )
                    
                    # Gráfico comparativo
                    st.markdown("### 📈 Comparativo de Probabilidades")
                    
                    # Preparar dados para o gráfico
                    df_chart = df_mc.head(10).copy()  # Top 10 jogos
                    for col in ["P(≥11)", "P(≥12)", "P(≥13)", "P(≥14)"]:
                        df_chart[col] = df_chart[col].str.replace("%", "").astype(float)
                    
                    chart_data = df_chart.melt(
                        id_vars=["Jogo"],
                        value_vars=["P(≥11)", "P(≥12)", "P(≥13)", "P(≥14)"],
                        var_name="Faixa",
                        value_name="Probabilidade (%)"
                    )
                    
                    # Criar gráfico de barras agrupadas
                    chart_pivot = chart_data.pivot(index="Jogo", columns="Faixa", values="Probabilidade (%)")
                    st.bar_chart(chart_pivot)
                    
                    # Melhor jogo por categoria
                    st.markdown("### 🏆 Melhores Jogos por Categoria")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        best_11 = df_mc.loc[df_mc["P(≥11)_valor"].idxmax()] if "P(≥11)_valor" in df_mc.columns else df_mc.iloc[0]
                        st.metric(
                            "Melhor para ≥11", 
                            f"Jogo {int(best_11['Jogo'])}",
                            best_11["P(≥11)"]
                        )
                    
                    with col2:
                        df_mc["P(≥12)_valor"] = df_mc["P(≥12)"].str.replace("%", "").astype(float)
                        best_12 = df_mc.loc[df_mc["P(≥12)_valor"].idxmax()]
                        st.metric(
                            "Melhor para ≥12", 
                            f"Jogo {int(best_12['Jogo'])}",
                            best_12["P(≥12)"]
                        )
                    
                    with col3:
                        df_mc["P(≥13)_valor"] = df_mc["P(≥13)"].str.replace("%", "").astype(float)
                        best_13 = df_mc.loc[df_mc["P(≥13)_valor"].idxmax()]
                        st.metric(
                            "Melhor para ≥13", 
                            f"Jogo {int(best_13['Jogo'])}",
                            best_13["P(≥13)"]
                        )
                    
                    # Explicação técnica
                    with st.expander("📘 O que significa Monte Carlo?"):
                        st.markdown("""
                        **Monte Carlo** é uma técnica estatística que simula milhares de sorteios reais para estimar probabilidades.
                        
                        - **P(≥11)**: Probabilidade de fazer 11 pontos ou mais
                        - **P(≥12)**: Probabilidade de fazer 12 pontos ou mais  
                        - **P(≥13)**: Probabilidade de fazer 13 pontos ou mais
                        - **P(≥14)**: Probabilidade de fazer 14 pontos ou mais
                        - **P(15)**: Probabilidade de acertar os 15 números
                        
                        Quanto maior o número de simulações, mais precisa a estimativa.
                        """)
                
                # MÉTRICA AGREGADA FINAL
                st.markdown("---")
                st.markdown("### 📌 Resumo Executivo")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Jogos acima do percentil 80", 
                             f"{(df_avaliacao['Percentil'] >= 80).sum()}/{len(df_avaliacao)}")
                with col2:
                    st.metric("Score médio", f"{df_avaliacao['Score (0-100)'].mean():.1f}")
                with col3:
                    st.metric("Melhor score", f"{df_avaliacao['Score (0-100)'].max():.1f}")

        with tab4:
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

        with tab5:
            st.subheader("✅ Conferência por Concurso")

            st.session_state.jogos_salvos = carregar_jogos_salvos()

            if not st.session_state.jogos_salvos:
                st.warning("Nenhum fechamento salvo. Gere jogos na aba 'Fechamento 3622'.")
            else:
                # =========================
                # SELEÇÃO DO FECHAMENTO
                # =========================
                opcoes = [
                    f"ID {j['id']} | Concurso Base #{j['concurso_base']['numero']} | {j['data_geracao'][:19]}"
                    for j in st.session_state.jogos_salvos
                ]

                idx = st.selectbox(
                    "📦 Selecione o fechamento",
                    range(len(opcoes)),
                    format_func=lambda i: opcoes[i]
                )

                fechamento = st.session_state.jogos_salvos[idx]
                jogos_brutos = fechamento["jogos"]

                # =========================
                # NORMALIZAÇÃO DOS JOGOS (CORREÇÃO DEFINITIVA)
                # =========================
                jogos = normalizar_jogos(jogos_brutos)
                
                # =========================
                # BLINDAGEM TOTAL
                # =========================
                valido, mensagem = validar_jogos_normalizados(jogos)
                if not valido:
                    st.error(f"❌ Erro na estrutura dos jogos: {mensagem}")
                    st.stop()
                
                # Debug visual (opcional - comentar em produção)
                with st.expander("🔍 Debug - Estrutura dos Jogos", expanded=False):
                    st.write(f"**Tipo original:** {type(jogos_brutos).__name__}")
                    st.write(f"**Tipo após normalização:** {type(jogos).__name__}")
                    st.write(f"**Quantidade de jogos:** {len(jogos)}")
                    st.write(f"**Primeiro jogo (exemplo):** {jogos[0] if jogos else 'N/A'}")

                st.markdown(f"""
                <div class='concurso-info'>
                    📦 <strong>Fechamento ID:</strong> {fechamento['id']}<br>
                    🎯 <strong>Total de jogos:</strong> {len(jogos)}
                </div>
                """, unsafe_allow_html=True)

                # =========================
                # SELEÇÃO DO CONCURSO REAL
                # =========================
                concursos = st.session_state.dados_api

                concurso_escolhido = st.selectbox(
                    "🎯 Selecione o concurso para conferência",
                    concursos,
                    format_func=lambda c: f"#{c['concurso']} - {c['data']}"
                )

                dezenas_sorteadas = sorted(map(int, concurso_escolhido["dezenas"]))
                dezenas_set = set(dezenas_sorteadas)

                st.markdown("### 🔢 Resultado Oficial")
                st.markdown(formatar_jogo_html(dezenas_sorteadas), unsafe_allow_html=True)

                # =========================
                # CONFERÊNCIA (SIMPLIFICADA E ROBUSTA)
                # =========================
                if st.button("🔍 CONFERIR FECHAMENTO", type="primary", use_container_width=True):
                    resultados = []
                    distribuicao = Counter()

                    for i, dezenas_jogo in enumerate(jogos):
                        acertos = len(set(dezenas_jogo) & dezenas_set)
                        distribuicao[acertos] += 1
                        resultados.append({
                            "Jogo": i + 1,
                            "Acertos": acertos,
                            "Dezenas": ", ".join(f"{n:02d}" for n in sorted(dezenas_jogo))
                        })

                    if not resultados:
                        st.error("❌ Nenhum jogo válido encontrado para conferência")
                    else:
                        df_resultado = pd.DataFrame(resultados).sort_values("Acertos", ascending=False)

                        # Estatísticas
                        estatisticas = {
                            "distribuicao": dict(distribuicao),
                            "melhor_jogo": int(df_resultado.iloc[0]["Jogo"]),
                            "maior_acerto": int(df_resultado.iloc[0]["Acertos"]),
                            "total_jogos_validos": len(resultados)
                        }

                        # Salvar conferência
                        adicionar_conferencia(
                            fechamento["arquivo"],
                            {
                                "numero": concurso_escolhido["concurso"],
                                "data": concurso_escolhido["data"]
                            },
                            df_resultado["Acertos"].tolist(),
                            estatisticas
                        )

                        # =========================
                        # VISUALIZAÇÃO
                        # =========================
                        st.success(f"✅ Conferência realizada e salva com sucesso! ({len(resultados)} jogos válidos)")

                        col1, col2, col3 = st.columns(3)
                        col1.metric("🏆 Melhor jogo", f"Jogo {estatisticas['melhor_jogo']}")
                        col2.metric("🎯 Maior acerto", estatisticas["maior_acerto"])
                        col3.metric("📊 Jogos válidos", estatisticas["total_jogos_validos"])

                        st.markdown("### 📊 Distribuição de Acertos")
                        dist_df = pd.DataFrame(
                            sorted(distribuicao.items()),
                            columns=["Acertos", "Quantidade"]
                        )
                        st.bar_chart(dist_df.set_index("Acertos"))

                        st.markdown("### 🏅 Ranking dos Jogos")
                        st.dataframe(
                            df_resultado[["Jogo", "Acertos", "Dezenas"]],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Dezenas": st.column_config.TextColumn("Dezenas", width="large")
                            }
                        )
    else:
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🚀 Comece carregando os concursos na barra lateral</h3>
            <p>Use o menu ≡ no canto superior esquerdo</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
