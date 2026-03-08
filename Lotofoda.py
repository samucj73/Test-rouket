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
# FUNÇÃO PARA GARANTIR QUE JOGOS SÃO LISTAS DE INTEIROS
# =====================================================
def garantir_jogos_como_listas(jogos_entrada):
    """
    Converte QUALQUER formato de jogos para lista de listas de inteiros
    Funciona com: DataFrame, lista de dicts, lista de strings, lista de listas
    """
    # Se for None ou vazio
    if jogos_entrada is None:
        return []
    
    # Se já for lista de listas de inteiros válida
    if isinstance(jogos_entrada, list) and len(jogos_entrada) > 0:
        if isinstance(jogos_entrada[0], list) and all(isinstance(n, int) for n in jogos_entrada[0]):
            return jogos_entrada
    
    jogos_normalizados = []
    
    # CASO 1: DataFrame do pandas
    if isinstance(jogos_entrada, pd.DataFrame):
        for _, row in jogos_entrada.iterrows():
            # Procurar coluna que contém as dezenas
            for col in row.index:
                valor = row[col]
                if isinstance(valor, str) and ("," in valor or " " in valor):
                    # String com separadores
                    if "," in valor:
                        dezenas = [int(d.strip()) for d in valor.split(",")]
                    else:
                        dezenas = [int(d) for d in valor.split()]
                    jogos_normalizados.append(sorted(dezenas))
                    break
                elif isinstance(valor, list):
                    # Já é lista
                    jogos_normalizados.append(sorted([int(x) for x in valor]))
                    break
        return jogos_normalizados
    
    # CASO 2: Lista de objetos
    if isinstance(jogos_entrada, list):
        for item in jogos_entrada:
            # 2.1: Item é dicionário
            if isinstance(item, dict):
                # Procurar chave com as dezenas
                for chave in ["Dezenas", "dezenas", "Numeros", "numeros", "Jogo", "jogo"]:
                    if chave in item:
                        valor = item[chave]
                        if isinstance(valor, str):
                            if "," in valor:
                                dezenas = [int(d.strip()) for d in valor.split(",")]
                            else:
                                dezenas = [int(d) for d in valor.split()]
                        elif isinstance(valor, list):
                            dezenas = [int(x) for x in valor]
                        else:
                            continue
                        jogos_normalizados.append(sorted(dezenas))
                        break
            
            # 2.2: Item é string
            elif isinstance(item, str):
                if "," in item:
                    dezenas = [int(d.strip()) for d in item.split(",")]
                else:
                    dezenas = [int(d) for d in item.split()]
                jogos_normalizados.append(sorted(dezenas))
            
            # 2.3: Item já é lista/tupla
            elif isinstance(item, (list, tuple)):
                jogos_normalizados.append(sorted([int(x) for x in item]))
    
    return jogos_normalizados

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
# ===== GERADOR 12+ (MODELO COBERTURA) =====
# =====================================================

class Gerador12Plus:
    """
    Gerador Otimizado para 12+ pontos
    Baseado na análise dos 20 concursos mais recentes
    """
    
    def __init__(self, concursos_historico, ultimo_concurso):
        """
        Args:
            concursos_historico: Lista de listas com os últimos N concursos
            ultimo_concurso: Lista com o resultado do último concurso
        """
        self.concursos = concursos_historico
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        
        # Definir faixas
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 26))
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        
        # Calcular frequências dos últimos 10 concursos para ponderação
        self.frequencias_recentes = self._calcular_frequencias_recentes()
        
        # Peso extra para números do último concurso
        self.peso_ultimo = 3.0
        
    def _calcular_frequencias_recentes(self, n=10):
        """Calcula frequências dos últimos N concursos para ponderação"""
        frequencias = Counter()
        total = 0
        
        # Pegar os últimos N concursos (excluindo o último)
        ultimos_n = self.concursos[1:n+1] if len(self.concursos) > n else self.concursos[1:]
        
        for concurso in ultimos_n:
            frequencias.update(concurso)
            total += len(concurso)
        
        # Converter para probabilidades
        if total > 0:
            return {num: count/total for num, count in frequencias.items()}
        return {}
    
    def _maior_bloco_consecutivo(self, jogo):
        """Retorna o tamanho do maior bloco de números consecutivos"""
        if not jogo:
            return 0
        
        nums = sorted(jogo)
        maior = 1
        atual = 1
        
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                atual += 1
                maior = max(maior, atual)
            else:
                atual = 1
        
        return maior
    
    def _contar_consecutivos(self, jogo):
        """Conta pares consecutivos (não blocos)"""
        nums = sorted(jogo)
        count = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                count += 1
        return count
    
    def jogo_valido(self, jogo):
        """
        Valida se o jogo respeita TODAS as regras do modelo 12+
        Retorna (bool, dict) com diagnóstico
        """
        if len(jogo) != 15:
            return False, {"erro": "Tamanho incorreto"}
        
        # Calcular métricas
        baixas = sum(1 for n in jogo if n in self.baixas)
        medias = sum(1 for n in jogo if n in self.medias)
        altas = sum(1 for n in jogo if n in self.altas)
        
        pares = sum(1 for n in jogo if n % 2 == 0)
        primos = sum(1 for n in jogo if n in self.primos)
        soma = sum(jogo)
        
        repetidas = len(set(jogo) & set(self.ultimo))
        consecutivos = self._contar_consecutivos(jogo)
        maior_bloco = self._maior_bloco_consecutivo(jogo)
        
        # Diagnóstico detalhado
        diag = {
            "baixas": baixas,
            "medias": medias,
            "altas": altas,
            "pares": pares,
            "primos": primos,
            "soma": soma,
            "repetidas": repetidas,
            "consecutivos": consecutivos,
            "maior_bloco": maior_bloco,
            "regras": {}
        }
        
        # ===== REGRAS OBRIGATÓRIAS =====
        
        # Regra 1: Distribuição
        diag["regras"]["distribuicao"] = (4 <= baixas <= 5) and (5 <= medias <= 6) and (5 <= altas <= 6)
        
        # Regra 2: Pares
        diag["regras"]["pares"] = (7 <= pares <= 8)
        
        # Regra 3: Soma (faixa premium 190-210)
        diag["regras"]["soma"] = (190 <= soma <= 210)
        
        # Regra 4: Primos
        diag["regras"]["primos"] = (5 <= primos <= 6)
        
        # Regra 5: Repetidas
        diag["regras"]["repetidas"] = (9 <= repetidas <= 11)
        
        # Regra 6: Consecutivos (quantidade)
        diag["regras"]["consecutivos_qtd"] = (2 <= consecutivos <= 4)
        
        # Regra 7: Bloco grande (pelo menos 3 consecutivos)
        diag["regras"]["bloco_grande"] = (maior_bloco >= 3)
        
        # ===== REGRAS DE BLOQUEIO (ANTI-QUEBRA) =====
        bloqueios = [
            soma < 185,
            soma > 215,
            pares <= 6,
            pares >= 9,
            altas <= 4,
            maior_bloco < 3,
            repetidas <= 7
        ]
        
        # Verificar se alguma regra de bloqueio foi ativada
        tem_bloqueio = any(bloqueios)
        diag["bloqueio"] = tem_bloqueio
        
        # Aprovado se todas as regras obrigatórias forem verdadeiras E nenhum bloqueio
        aprovado = all(diag["regras"].values()) and not tem_bloqueio
        
        # Contar regras aprovadas
        diag["regras_aprovadas"] = sum(1 for v in diag["regras"].values() if v)
        diag["total_regras"] = len(diag["regras"])
        
        return aprovado, diag
    
    def _gerar_jogo_ponderado(self):
        """
        Gera um jogo usando pool ponderado baseado em:
        - Frequências recentes
        - Números do último concurso (peso extra)
        """
        # Criar pool com pesos
        pool = []
        pesos = []
        
        for num in range(1, 26):
            pool.append(num)
            
            # Peso base: frequência recente (ou 1.0 se não apareceu)
            peso = self.frequencias_recentes.get(num, 1.0)
            
            # Peso extra se está no último concurso
            if num in self.ultimo:
                peso *= self.peso_ultimo
            
            pesos.append(peso)
        
        # Normalizar pesos
        pesos = np.array(pesos) / sum(pesos)
        
        return pool, pesos
    
    def gerar_jogo(self, max_tentativas=10000):
        """
        Gera um único jogo válido
        """
        pool, pesos = self._gerar_jogo_ponderado()
        
        for _ in range(max_tentativas):
            # Gerar 15 números com pesos
            indices = np.random.choice(len(pool), size=15, replace=False, p=pesos)
            jogo = sorted([pool[i] for i in indices])
            
            # Validar
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        
        # Fallback: gerar aleatório simples e tentar validar
        for _ in range(max_tentativas):
            jogo = sorted(random.sample(range(1, 26), 15))
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        
        # Último fallback: retornar None
        return None, None
    
    def gerar_multiplos_jogos(self, quantidade, max_total_tentativas=100000):
        """
        Gera múltiplos jogos válidos
        Retorna lista de jogos e lista de diagnósticos
        """
        jogos = []
        diagnosticos = []
        tentativas = 0
        
        # Barra de progresso (simulada)
        progress_text = "Gerando jogos válidos..."
        progress_bar = st.progress(0, text=progress_text)
        
        while len(jogos) < quantidade and tentativas < max_total_tentativas:
            jogo, diag = self.gerar_jogo()
            tentativas += 1
            
            if jogo and jogo not in jogos:  # Evitar duplicatas
                jogos.append(jogo)
                diagnosticos.append(diag)
                
                # Atualizar progresso
                progress_bar.progress(len(jogos) / quantidade, text=progress_text)
        
        progress_bar.empty()
        
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos válidos em {tentativas} tentativas")
        
        return jogos, diagnosticos
    
    def get_estatisticas_recentes(self):
        """Retorna estatísticas dos últimos concursos para exibição"""
        if len(self.concursos) < 2:
            return {}
        
        # Calcular médias dos últimos 20 concursos
        ultimos = self.concursos[:20]
        
        medias = {
            "baixas": np.mean([sum(1 for n in c if n in self.baixas) for c in ultimos]),
            "medias": np.mean([sum(1 for n in c if n in self.medias) for c in ultimos]),
            "altas": np.mean([sum(1 for n in c if n in self.altas) for c in ultimos]),
            "pares": np.mean([sum(1 for n in c if n % 2 == 0) for c in ultimos]),
            "primos": np.mean([sum(1 for n in c if n in self.primos) for c in ultimos]),
            "soma": np.mean([sum(c) for c in ultimos]),
            "repetidas": np.mean([len(set(c) & set(self.ultimo)) for c in ultimos[1:]]) if len(ultimos) > 1 else 0,
        }
        
        return medias

# =====================================================
# ===== NOVO: GERADOR 13+ (MODELO ULTRA) =====
# =====================================================

class Gerador13Plus:
    """
    Gerador Ultra para 13+ pontos
    Zona de convergência máxima - tiro de precisão
    """
    
    def __init__(self, concursos_historico, ultimo_concurso):
        """
        Args:
            concursos_historico: Lista de listas com os últimos N concursos
            ultimo_concurso: Lista com o resultado do último concurso
        """
        self.concursos = concursos_historico
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        
        # Definir faixas
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 26))
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        
        # Calcular frequências dos últimos 20 concursos para ponderação
        self.frequencias_recentes = self._calcular_frequencias_recentes()
        
        # Peso extra para números do último concurso (mais importante para 13+)
        self.peso_ultimo = 4.0
        
    def _calcular_frequencias_recentes(self, n=20):
        """Calcula frequências dos últimos N concursos para ponderação"""
        frequencias = Counter()
        total = 0
        
        # Pegar os últimos N concursos (excluindo o último)
        ultimos_n = self.concursos[1:n+1] if len(self.concursos) > n else self.concursos[1:]
        
        for concurso in ultimos_n:
            frequencias.update(concurso)
            total += len(concurso)
        
        # Converter para probabilidades
        if total > 0:
            return {num: count/total for num, count in frequencias.items()}
        return {}
    
    def _maior_bloco_consecutivo(self, jogo):
        """Retorna o tamanho do maior bloco de números consecutivos"""
        if not jogo:
            return 0
        
        nums = sorted(jogo)
        maior = 1
        atual = 1
        
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                atual += 1
                maior = max(maior, atual)
            else:
                atual = 1
        
        return maior
    
    def _contar_consecutivos(self, jogo):
        """Conta pares consecutivos (não blocos)"""
        nums = sorted(jogo)
        count = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                count += 1
        return count
    
    def _tem_dois_blocos(self, jogo):
        """Verifica se tem pelo menos 2 blocos consecutivos diferentes"""
        nums = sorted(jogo)
        blocos = []
        atual = 1
        
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                atual += 1
            else:
                if atual >= 2:
                    blocos.append(atual)
                atual = 1
        
        # Verificar último bloco
        if atual >= 2:
            blocos.append(atual)
        
        # Para 13+: precisa de 1 bloco longo (≥3) e 1 bloco curto (2)
        return len(blocos) >= 2 and max(blocos) >= 3
    
    def jogo_valido(self, jogo):
        """
        Valida se o jogo respeita TODAS as regras do modelo 13+
        Retorna (bool, dict) com diagnóstico
        """
        if len(jogo) != 15:
            return False, {"erro": "Tamanho incorreto"}
        
        # Calcular métricas
        baixas = sum(1 for n in jogo if n in self.baixas)
        medias = sum(1 for n in jogo if n in self.medias)
        altas = sum(1 for n in jogo if n in self.altas)
        
        pares = sum(1 for n in jogo if n % 2 == 0)
        primos = sum(1 for n in jogo if n in self.primos)
        soma = sum(jogo)
        
        repetidas = len(set(jogo) & set(self.ultimo))
        consecutivos = self._contar_consecutivos(jogo)
        maior_bloco = self._maior_bloco_consecutivo(jogo)
        tem_dois_blocos = self._tem_dois_blocos(jogo)
        
        # Diagnóstico detalhado
        diag = {
            "baixas": baixas,
            "medias": medias,
            "altas": altas,
            "pares": pares,
            "primos": primos,
            "soma": soma,
            "repetidas": repetidas,
            "consecutivos": consecutivos,
            "maior_bloco": maior_bloco,
            "tem_dois_blocos": tem_dois_blocos,
            "regras": {}
        }
        
        # ===== REGRAS FIXAS (ZONA 13+) =====
        
        # Regra 1: Distribuição estrutural CRÍTICA
        diag["regras"]["distribuicao"] = (baixas == 4) and (medias == 6) and (altas == 5)
        
        # Regra 2: Pares - janela ótima
        diag["regras"]["pares"] = (pares == 7)
        
        # Regra 3: Soma - zona premium
        diag["regras"]["soma"] = (195 <= soma <= 205)
        
        # Regra 4: Primos
        diag["regras"]["primos"] = (primos == 5)
        
        # Regra 5: Repetidas do concurso anterior
        diag["regras"]["repetidas"] = (repetidas in (10, 11))
        
        # Regra 6: Consecutivos (quantidade)
        diag["regras"]["consecutivos_qtd"] = (consecutivos in (3, 4))
        
        # Regra 7: Bloco grande
        diag["regras"]["bloco_grande"] = (maior_bloco >= 3)
        
        # Regra 8: Dois blocos (1 longo + 1 curto)
        diag["regras"]["dois_blocos"] = tem_dois_blocos
        
        # ===== REGRAS DE BLOQUEIO (ANTI-12, ANTI-11) =====
        bloqueios = [
            soma < 190 or soma > 210,  # Faixa mais restrita que 12+
            pares <= 6 or pares >= 9,
            altas <= 4,
            maior_bloco < 3,
            repetidas <= 9,
            medias <= 5,
            not tem_dois_blocos  # Obrigatório ter 2 blocos
        ]
        
        # Verificar se alguma regra de bloqueio foi ativada
        tem_bloqueio = any(bloqueios)
        diag["bloqueio"] = tem_bloqueio
        
        # Aprovado se todas as regras obrigatórias forem verdadeiras E nenhum bloqueio
        aprovado = all(diag["regras"].values()) and not tem_bloqueio
        
        # Contar regras aprovadas
        diag["regras_aprovadas"] = sum(1 for v in diag["regras"].values() if v)
        diag["total_regras"] = len(diag["regras"])
        
        return aprovado, diag
    
    def _gerar_jogo_ponderado(self):
        """
        Gera um jogo usando pool ponderado baseado em:
        - Frequências recentes (20 concursos)
        - Números do último concurso (peso extra 4x)
        """
        # Criar pool com pesos
        pool = []
        pesos = []
        
        for num in range(1, 26):
            pool.append(num)
            
            # Peso base: frequência recente (ou 1.0 se não apareceu)
            peso = self.frequencias_recentes.get(num, 1.0)
            
            # Peso extra se está no último concurso (mais importante para 13+)
            if num in self.ultimo:
                peso *= self.peso_ultimo
            
            pesos.append(peso)
        
        # Normalizar pesos
        pesos = np.array(pesos) / sum(pesos)
        
        return pool, pesos
    
    def gerar_jogo(self, max_tentativas=20000):
        """
        Gera um único jogo válido
        Mais tentativas porque 13+ é mais restritivo
        """
        pool, pesos = self._gerar_jogo_ponderado()
        
        for _ in range(max_tentativas):
            # Gerar 15 números com pesos
            indices = np.random.choice(len(pool), size=15, replace=False, p=pesos)
            jogo = sorted([pool[i] for i in indices])
            
            # Validar
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        
        # Fallback: gerar aleatório simples e tentar validar
        for _ in range(max_tentativas * 2):
            jogo = sorted(random.sample(range(1, 26), 15))
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        
        return None, None
    
    def gerar_multiplos_jogos(self, quantidade, max_total_tentativas=500000):
        """
        Gera múltiplos jogos válidos
        MUITAS tentativas porque 13+ é extremamente restritivo
        """
        jogos = []
        diagnosticos = []
        tentativas = 0
        
        # Barra de progresso
        progress_text = "Gerando jogos 13+ (paciência, é restritivo)..."
        progress_bar = st.progress(0, text=progress_text)
        
        while len(jogos) < quantidade and tentativas < max_total_tentativas:
            jogo, diag = self.gerar_jogo()
            tentativas += 1
            
            if jogo and jogo not in jogos:  # Evitar duplicatas
                jogos.append(jogo)
                diagnosticos.append(diag)
                
                # Atualizar progresso
                progress_bar.progress(len(jogos) / quantidade, text=progress_text)
            
            # Atualizar a cada 1000 tentativas para não travar
            if tentativas % 1000 == 0:
                progress_bar.progress(len(jogos) / quantidade, 
                                     text=f"{len(jogos)}/{quantidade} jogos encontrados em {tentativas} tentativas...")
        
        progress_bar.empty()
        
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos 13+ em {tentativas} tentativas (taxa de acerto: {len(jogos)/tentativas*100:.4f}%)")
        else:
            st.success(f"✅ {len(jogos)} jogos 13+ gerados em {tentativas} tentativas (taxa: {len(jogos)/tentativas*100:.4f}%)")
        
        return jogos, diagnosticos
    
    def get_estatisticas_recentes(self):
        """Retorna estatísticas dos últimos concursos para exibição"""
        if len(self.concursos) < 2:
            return {}
        
        # Calcular médias dos últimos 20 concursos
        ultimos = self.concursos[:20]
        
        medias = {
            "baixas": np.mean([sum(1 for n in c if n in self.baixas) for c in ultimos]),
            "medias": np.mean([sum(1 for n in c if n in self.medias) for c in ultimos]),
            "altas": np.mean([sum(1 for n in c if n in self.altas) for c in ultimos]),
            "pares": np.mean([sum(1 for n in c if n % 2 == 0) for c in ultimos]),
            "primos": np.mean([sum(1 for n in c if n in self.primos) for c in ultimos]),
            "soma": np.mean([sum(c) for c in ultimos]),
            "repetidas": np.mean([len(set(c) & set(self.ultimo)) for c in ultimos[1:]]) if len(ultimos) > 1 else 0,
        }
        
        return medias

# =====================================================
# GERADOR PROFISSIONAL (BASEADO NOS CÓDIGOS FORNECIDOS)
# =====================================================

class GeradorProfissional:
    """
    Gerador profissional baseado nos padrões estatísticos mais fortes:
    - Distribuição Baixa-Média-Alta: 5-7-3
    - Pares/Ímpares: 7-8
    - Repetidas do último concurso: 8-9
    - Sequências consecutivas: 4-6 números
    - Soma: 180-220
    """
    
    def __init__(self, ultimo_concurso):
        """
        Args:
            ultimo_concurso: Lista com o resultado do último concurso
        """
        self.ultimo_concurso = set(ultimo_concurso) if ultimo_concurso else set()
        
        # Faixas do volante
        self.baixas = list(range(1, 9))    # 01-08
        self.medias = list(range(9, 17))   # 09-16
        self.altas = list(range(17, 26))   # 17-25
        
    def contar_consecutivos(self, jogo):
        """
        Conta o tamanho da maior sequência consecutiva no jogo
        """
        jogo_sorted = sorted(jogo)
        maior = 1
        atual = 1
        
        for i in range(1, len(jogo_sorted)):
            if jogo_sorted[i] == jogo_sorted[i-1] + 1:
                atual += 1
                maior = max(maior, atual)
            else:
                atual = 1
                
        return maior
    
    def gerar_jogo(self, max_tentativas=10000):
        """
        Gera um único jogo respeitando todos os filtros estatísticos
        """
        for tentativa in range(max_tentativas):
            jogo = set()
            
            # PASSO 1: Distribuição estrutural 5-7-3
            jogo.update(random.sample(self.baixas, 5))
            jogo.update(random.sample(self.medias, 7))
            jogo.update(random.sample(self.altas, 3))
            
            jogo = sorted(jogo)
            
            # PASSO 2: Verificar pares/ímpares
            pares = sum(1 for n in jogo if n % 2 == 0)
            if pares not in [6, 7, 8]:
                continue
            
            # PASSO 3: Verificar repetidas do último concurso
            if self.ultimo_concurso:
                repetidas = len(set(jogo) & self.ultimo_concurso)
                if repetidas not in [8, 9]:
                    continue
            
            # PASSO 4: Verificar sequências consecutivas
            seq = self.contar_consecutivos(jogo)
            if seq < 4 or seq > 6:
                continue
            
            # PASSO 5: Verificar soma total
            soma = sum(jogo)
            if soma < 180 or soma > 220:
                continue
            
            # Se passou por todos os filtros, jogo é válido
            return jogo, {
                "distribuicao": "5-7-3",
                "pares": pares,
                "repetidas": repetidas if self.ultimo_concurso else 0,
                "sequencia_max": seq,
                "soma": soma
            }
        
        # Fallback: gerar jogo com regras mais flexíveis
        return self._gerar_jogo_fallback()
    
    def _gerar_jogo_fallback(self):
        """Gera um jogo de fallback quando não encontra com validação completa"""
        jogo = set()
        
        # Manter distribuição 5-7-3
        jogo.update(random.sample(self.baixas, 5))
        jogo.update(random.sample(self.medias, 7))
        jogo.update(random.sample(self.altas, 3))
        
        jogo = sorted(jogo)
        
        # Estatísticas do jogo fallback
        pares = sum(1 for n in jogo if n % 2 == 0)
        repetidas = len(set(jogo) & self.ultimo_concurso) if self.ultimo_concurso else 0
        seq = self.contar_consecutivos(jogo)
        soma = sum(jogo)
        
        diagnostico = {
            "distribuicao": "5-7-3",
            "pares": pares,
            "repetidas": repetidas,
            "sequencia_max": seq,
            "soma": soma,
            "fallback": True
        }
        
        return jogo, diagnostico
    
    def gerar_multiplos_jogos(self, quantidade):
        """
        Gera múltiplos jogos válidos
        """
        jogos = []
        diagnosticos = []
        tentativas = 0
        max_tentativas = quantidade * 5000
        
        # Barra de progresso
        progress_text = "Gerando jogos profissionais..."
        progress_bar = st.progress(0, text=progress_text)
        
        while len(jogos) < quantidade and tentativas < max_tentativas:
            jogo, diag = self.gerar_jogo()
            tentativas += 1
            
            if jogo and jogo not in jogos:  # Evitar duplicatas
                jogos.append(jogo)
                diagnosticos.append(diag)
                
                # Atualizar progresso
                progress_bar.progress(len(jogos) / quantidade, text=progress_text)
        
        progress_bar.empty()
        
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos profissionais em {tentativas} tentativas")
        
        return jogos, diagnosticos
    
    def get_info(self):
        """Retorna informações sobre o gerador"""
        return {
            "nome": "Gerador Profissional",
            "distribuicao": "5-7-3 (Baixas:5, Médias:7, Altas:3)",
            "pares": "6-8 pares",
            "repetidas": "8-9 do último concurso",
            "sequencias": "4-6 números consecutivos",
            "soma": "180-220"
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
# FUNÇÃO PARA EXTRAIR JOGO POR ÍNDICE
# =====================================================
def extrair_jogo_por_indice(jogos_gerados, indice):
    """
    Extrai um jogo específico por índice, independente do formato de entrada
    Retorna uma lista de inteiros
    """
    if jogos_gerados is None:
        return []
    
    # Verificar se o índice é válido
    if indice < 0 or indice >= len(jogos_gerados):
        return []
    
    # Caso 1: É DataFrame
    if isinstance(jogos_gerados, pd.DataFrame):
        try:
            jogo_row = jogos_gerados.iloc[indice]
            # Procurar coluna com as dezenas
            for col in ["Dezenas", "dezenas", "Jogo", "jogo", "Numeros", "numeros"]:
                if col in jogo_row:
                    valor = jogo_row[col]
                    if isinstance(valor, str):
                        if "," in valor:
                            return [int(d.strip()) for d in valor.split(",")]
                        else:
                            return [int(d) for d in valor.split()]
                    elif isinstance(valor, list):
                        return [int(d) for d in valor]
                    elif isinstance(valor, (int, float)):
                        # Pode ser o número do jogo, não as dezenas
                        continue
            # Se não encontrou, tentar a primeira coluna que parece lista
            for col in jogo_row.index:
                valor = jogo_row[col]
                if isinstance(valor, str) and ("," in valor or " " in valor):
                    if "," in valor:
                        return [int(d.strip()) for d in valor.split(",")]
                    else:
                        return [int(d) for d in valor.split()]
            return []
        except:
            return []
    
    # Caso 2: É lista
    elif isinstance(jogos_gerados, list):
        try:
            item = jogos_gerados[indice]
            
            # 2.1: Item é dicionário
            if isinstance(item, dict):
                for chave in ["Dezenas", "dezenas", "Jogo", "jogo", "Numeros", "numeros"]:
                    if chave in item:
                        valor = item[chave]
                        if isinstance(valor, str):
                            if "," in valor:
                                return [int(d.strip()) for d in valor.split(",")]
                            else:
                                return [int(d) for d in valor.split()]
                        elif isinstance(valor, list):
                            return [int(d) for d in valor]
                return []
            
            # 2.2: Item é string
            elif isinstance(item, str):
                if "," in item:
                    return [int(d.strip()) for d in item.split(",")]
                else:
                    return [int(d) for d in item.split()]
            
            # 2.3: Item já é lista
            elif isinstance(item, (list, tuple)):
                return [int(d) for d in item]
            
            else:
                return []
        except:
            return []
    
    return []

# =====================================================
# MÓDULO DE INTELIGÊNCIA: DETECTOR DE SINAL + FILTRO 5-7-3
# =====================================================

def faixa_573(n):
    """Classifica um número em faixa para o filtro 5-7-3."""
    if 1 <= n <= 8:
        return "baixa"
    elif 9 <= n <= 16:
        return "media"
    else:
        return "alta"

def contar_faixas_573(jogo):
    """Conta quantos números em cada faixa (baixa, media, alta)."""
    f = {"baixa": 0, "media": 0, "alta": 0}
    for n in jogo:
        f[faixa_573(n)] += 1
    return f

def paridade_573(jogo):
    """Retorna a contagem de pares e ímpares."""
    pares = sum(1 for n in jogo if n % 2 == 0)
    return pares, 15 - pares

def soma_573(jogo):
    """Calcula a soma total do jogo."""
    return sum(jogo)

def maior_bloco_consecutivo_573(jogo):
    """Encontra o tamanho do maior bloco de números consecutivos."""
    jogo_sorted = sorted(jogo)
    if not jogo_sorted:
        return 0
    maior = atual = 1
    for i in range(1, len(jogo_sorted)):
        if jogo_sorted[i] == jogo_sorted[i-1] + 1:
            atual += 1
            maior = max(maior, atual)
        else:
            atual = 1
    return maior

def detectar_sinal(concursos_historico, lookback=5):
    """
    Detecta se o sistema deve entrar em modo 'SNIPER' (Sinal ON).
    Args:
        concursos_historico: Lista de listas com os últimos N concursos.
        lookback: Número de concursos recentes para análise.
    Returns:
        bool: True se o sinal está ON (ativar filtro), False caso contrário.
    """
    if len(concursos_historico) < 3:
        return False  # Não há dados suficientes para detectar sinal

    recentes = concursos_historico[:lookback]
    sinais_detectados = 0

    # --- SINAL A: Excesso de Altas (17-25) nos últimos 3 concursos ---
    altas_excesso_count = 0
    for c in recentes[:3]:
        if contar_faixas_573(c)["alta"] >= 6:
            altas_excesso_count += 1
    if altas_excesso_count >= 2:
        sinais_detectados += 1

    # --- SINAL B: Médias (9-16) Reprimidas nos últimos 2 concursos ---
    if len(recentes) >= 2:
        medias_baixas_count = 0
        for c in recentes[:2]:
            if contar_faixas_573(c)["media"] <= 5:
                medias_baixas_count += 1
        if medias_baixas_count == 2:
            sinais_detectados += 1

    # --- SINAL C: Falta de Blocos Grandes nos últimos 2 concursos ---
    if len(recentes) >= 2 and all(maior_bloco_consecutivo_573(c) <= 3 for c in recentes[:2]):
        sinais_detectados += 1

    # --- SINAL D: Soma Fora da Zona Premium nos últimos 2 concursos ---
    if len(recentes) >= 2:
        soma_fora_count = 0
        for c in recentes[:2]:
            s = soma_573(c)
            if s < 180 or s > 210:
                soma_fora_count += 1
        if soma_fora_count >= 1: # Se pelo menos um deles está fora
            sinais_detectados += 1

    # REGRA FINAL: Sinal ON se pelo menos 3 sinais forem detectados
    return sinais_detectados >= 3

def filtro_573_ultra(jogo):
    """
    Filtro ultra-restritivo baseado nos 4 padrões prioritários:
    5-7-3 (PRIORIDADE MÁXIMA), 5-6-4, 6-6-3, 4-7-4
    Estes 4 padrões cobrem ~68% dos concursos reais.
    Retorna True se o jogo PASSA no filtro.
    """
    f = contar_faixas_573(jogo)
    pares, _ = paridade_573(jogo)
    s = soma_573(jogo)
    bloco = maior_bloco_consecutivo_573(jogo)

    # PADRÕES PRIORITÁRIOS (os únicos aceitos)
    padrao_valido = False
    
    # 1. 5-7-3 (PRIORIDADE MÁXIMA)
    if f["baixa"] == 5 and f["media"] == 7 and f["alta"] == 3:
        padrao_valido = True
    
    # 2. 5-6-4
    elif f["baixa"] == 5 and f["media"] == 6 and f["alta"] == 4:
        padrao_valido = True
    
    # 3. 6-6-3
    elif f["baixa"] == 6 and f["media"] == 6 and f["alta"] == 3:
        padrao_valido = True
    
    # 4. 4-7-4
    elif f["baixa"] == 4 and f["media"] == 7 and f["alta"] == 4:
        padrao_valido = True
    
    if not padrao_valido:
        return False

    # Paridade: 6 a 8 pares
    if not (6 <= pares <= 8):
        return False

    # Soma: 185 a 205
    if not (185 <= s <= 205):
        return False

    # Bloco: Pelo menos 4 números consecutivos em algum lugar
    if bloco < 4:
        return False

    # Altas Frias (23-25): No máximo 1
    altas_frias = sum(1 for n in jogo if n >= 23)
    if altas_frias > 1:
        return False

    # Médias Blindadas: Pelo menos 6 números no coração do volante (9-16)
    medias_centro = {9, 10, 11, 12, 13, 14, 15, 16}
    if len(set(jogo) & medias_centro) < 6:
        return False

    return True

def score_jogo_573(jogo):
    """
    Atribui uma pontuação de qualidade ao jogo. Quanto maior, melhor.
    Prioridade máxima para o padrão 5-7-3.
    """
    pontos = 0
    f = contar_faixas_573(jogo)
    pares, _ = paridade_573(jogo)
    s = soma_573(jogo)
    bloco = maior_bloco_consecutivo_573(jogo)

    # Pontos extras por padrões prioritários
    if f["baixa"] == 5 and f["media"] == 7 and f["alta"] == 3:
        pontos += 5  # PRIORIDADE MÁXIMA
    elif f["baixa"] == 5 and f["media"] == 6 and f["alta"] == 4:
        pontos += 4
    elif f["baixa"] == 6 and f["media"] == 6 and f["alta"] == 3:
        pontos += 4
    elif f["baixa"] == 4 and f["media"] == 7 and f["alta"] == 4:
        pontos += 4

    # Pontos por forte presença no miolo
    if f["media"] >= 7:
        pontos += 2
    elif f["media"] == 6:
        pontos += 1

    # Pontos por blocos longos
    if bloco >= 5:
        pontos += 2
    elif bloco == 4:
        pontos += 1

    # Pontos por paridade equilibrada
    if pares == 7:
        pontos += 1
    elif pares == 8:
        pontos += 0.5

    # Pontos por soma na zona premium
    if 190 <= s <= 200:
        pontos += 2
    elif 185 <= s <= 205:
        pontos += 1

    return pontos

def pipeline_selecao_inteligente(jogos_gerados, concursos_historico, modo_operacao="auto", threshold_score=6):
    """
    Pipeline completo que decide se aplica o filtro pesado baseado no sinal.
    Args:
        jogos_gerados: Lista de jogos a serem filtrados.
        concursos_historico: Lista de listas com os últimos concursos.
        modo_operacao: "auto", "forcar_on", "forcar_off".
        threshold_score: Pontuação mínima para um jogo ser aprovado.
    Returns:
        tuple: (jogos_aprovados, sinal_ativo, estatisticas)
    """
    sinal_ativo = False
    if modo_operacao == "auto":
        sinal_ativo = detectar_sinal(concursos_historico)
    elif modo_operacao == "forcar_on":
        sinal_ativo = True
    elif modo_operacao == "forcar_off":
        sinal_ativo = False

    jogos_aprovados = []
    estatisticas = {
        "total_jogos_analisados": len(jogos_gerados),
        "sinal_estava_ativo": sinal_ativo,
        "jogos_filtrados_573": 0,
        "jogos_reprovados_score": 0,
        "threshold_score": threshold_score,
        "jogos_por_padrao": {
            "5-7-3": 0,
            "5-6-4": 0,
            "6-6-3": 0,
            "4-7-4": 0,
            "outros": 0
        }
    }

    for jogo in jogos_gerados:
        # Identificar padrão do jogo
        f = contar_faixas_573(jogo)
        padrao = f"{f['baixa']}-{f['media']}-{f['alta']}"
        
        if padrao == "5-7-3":
            estatisticas["jogos_por_padrao"]["5-7-3"] += 1
        elif padrao == "5-6-4":
            estatisticas["jogos_por_padrao"]["5-6-4"] += 1
        elif padrao == "6-6-3":
            estatisticas["jogos_por_padrao"]["6-6-3"] += 1
        elif padrao == "4-7-4":
            estatisticas["jogos_por_padrao"]["4-7-4"] += 1
        else:
            estatisticas["jogos_por_padrao"]["outros"] += 1

        passa_pelo_filtro = True
        if sinal_ativo:
            # Modo SNIPER: Aplica o filtro ultra
            if not filtro_573_ultra(jogo):
                passa_pelo_filtro = False
                estatisticas["jogos_filtrados_573"] += 1

        if passa_pelo_filtro:
            # Sempre aplica o score, independente do modo
            if score_jogo_573(jogo) >= threshold_score:
                jogos_aprovados.append(jogo)
            else:
                estatisticas["jogos_reprovados_score"] += 1

    estatisticas["jogos_aprovados"] = len(jogos_aprovados)
    return jogos_aprovados, sinal_ativo, estatisticas

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
    if "jogos_otimizados" not in st.session_state:
        st.session_state.jogos_otimizados = None
    if "logs_otimizados" not in st.session_state:
        st.session_state.logs_otimizados = None
    if "jogos_12plus" not in st.session_state:
        st.session_state.jogos_12plus = None
    if "diagnosticos_12plus" not in st.session_state:
        st.session_state.diagnosticos_12plus = None
    if "jogos_13plus" not in st.session_state:
        st.session_state.jogos_13plus = None
    if "diagnosticos_13plus" not in st.session_state:
        st.session_state.diagnosticos_13plus = None
    if "jogos_inteligentes" not in st.session_state:
        st.session_state.jogos_inteligentes = None
    if "stats_inteligentes" not in st.session_state:
        st.session_state.stats_inteligentes = None
    if "jogos_profissionais" not in st.session_state:
        st.session_state.jogos_profissionais = None
    if "diagnosticos_profissionais" not in st.session_state:
        st.session_state.diagnosticos_profissionais = None
    
    # =====================================================
    # NOVOS ESTADOS PARA PERSISTÊNCIA
    # =====================================================
    if "fonte_inteligencia" not in st.session_state:
        st.session_state.fonte_inteligencia = "Jogos do Fechamento 3622"
    if "modo_intel" not in st.session_state:
        st.session_state.modo_intel = "auto"
    if "threshold_intel" not in st.session_state:
        st.session_state.threshold_intel = 6
    if "idx_fechamento_conferencia" not in st.session_state:
        st.session_state.idx_fechamento_conferencia = 0
    if "qtd_12plus" not in st.session_state:
        st.session_state.qtd_12plus = 10
    if "qtd_13plus" not in st.session_state:
        st.session_state.qtd_13plus = 5
    if "qtd_3622" not in st.session_state:
        st.session_state.qtd_3622 = 10
    if "mc_sim_value" not in st.session_state:
        st.session_state.mc_sim_value = 10000
    if "jogos_teste_intel" not in st.session_state:
        st.session_state.jogos_teste_intel = None

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
        # AGORA SÃO 8 ABAS (adicionada a nova aba de inteligência)
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "📊 Análise", 
            "🧩 Fechamento 3622", 
            "📊 Motor Estatístico",
            "📋 Concursos",
            "✅ Conferência",
            "🚀 Gerador 12+",
            "🔥 Gerador 13+",
            "🧠 Inteligência 5-7-3"
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
                    qtd_jogos = st.slider(
                        "Quantidade de jogos", 
                        3, 100, 
                        value=st.session_state.qtd_3622,
                        key="slider_qtd_3622",
                        help="Mínimo 3, máximo 100 jogos"
                    )
                    st.session_state.qtd_3622 = qtd_jogos
                
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
                        if st.button("💾 Salvar Jogos", key="salvar_3622", use_container_width=True):
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
                        if st.button("🔄 Nova Geração", key="nova_geracao_3622", use_container_width=True):
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
                
                # =====================================================
                # GERADOR PROFISSIONAL (INTEGRADO)
                # =====================================================
                st.markdown("---")
                st.markdown("## 🏆 GERADOR PROFISSIONAL")
                st.caption("Baseado nos padrões estatísticos mais fortes: distribuição 5-7-3, repetidas 8-9, sequências 4-6, soma 180-220")
                
                # Criar gerador profissional
                gerador_profissional = GeradorProfissional(numeros_ultimo)
                
                # Mostrar informações do gerador
                info = gerador_profissional.get_info()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**📊 {info['distribuicao']}**")
                with col2:
                    st.markdown(f"**⚖️ {info['pares']}**")
                with col3:
                    st.markdown(f"**🔄 {info['repetidas']}**")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**📈 {info['sequencias']}**")
                with col2:
                    st.markdown(f"**➕ {info['soma']}**")
                with col3:
                    st.markdown("")
                
                # Configuração de geração
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    qtd_profissional = st.slider(
                        "Quantidade de jogos profissionais",
                        min_value=3,
                        max_value=50,
                        value=10,
                        key="slider_qtd_profissional"
                    )
                
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🏆 GERAR JOGOS PROFISSIONAIS", key="gerar_profissional", use_container_width=True, type="secondary"):
                        with st.spinner(f"Gerando {qtd_profissional} jogos profissionais..."):
                            jogos, diagnosticos = gerador_profissional.gerar_multiplos_jogos(qtd_profissional)
                            
                            if jogos:
                                # Salvar na sessão
                                st.session_state.jogos_profissionais = jogos
                                st.session_state.diagnosticos_profissionais = diagnosticos
                                
                                st.success(f"✅ {len(jogos)} jogos profissionais gerados!")
                
                with col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔄 Reset", key="reset_profissional", use_container_width=True):
                        st.session_state.jogos_profissionais = None
                        st.rerun()
                
                # Mostrar jogos gerados
                if "jogos_profissionais" in st.session_state and st.session_state.jogos_profissionais:
                    jogos = st.session_state.jogos_profissionais
                    diagnosticos = st.session_state.diagnosticos_profissionais if "diagnosticos_profissionais" in st.session_state else [None] * len(jogos)
                    
                    st.markdown(f"### 📋 Jogos Profissionais ({len(jogos)})")
                    
                    # Estatísticas agregadas
                    stats_df = pd.DataFrame({
                        "Jogo": range(1, len(jogos)+1),
                        "Pares": [sum(1 for n in j if n%2==0) for j in jogos],
                        "Repetidas": [len(set(j) & set(numeros_ultimo)) for j in jogos],
                        "Soma": [sum(j) for j in jogos],
                        "Sequência Max": [gerador_profissional.contar_consecutivos(j) for j in jogos],
                        "Baixas": [sum(1 for n in j if n in gerador_profissional.baixas) for j in jogos],
                        "Médias": [sum(1 for n in j if n in gerador_profissional.medias) for j in jogos],
                        "Altas": [sum(1 for n in j if n in gerador_profissional.altas) for j in jogos]
                    })
                    
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    
                    # Mostrar cada jogo formatado
                    for i, (jogo, diag) in enumerate(zip(jogos, diagnosticos)):
                        with st.container():
                            # Determinar cor baseada na qualidade
                            if diag and diag.get("fallback", False):
                                cor_borda = "#f97316"  # Laranja - fallback
                            else:
                                cor_borda = "#4ade80"  # Verde - perfeito
                            
                            # Formatar números
                            nums_html = formatar_jogo_html(jogo)
                            
                            # Estatísticas resumidas
                            pares = sum(1 for n in jogo if n%2==0)
                            repetidas = len(set(jogo) & set(numeros_ultimo))
                            soma = sum(jogo)
                            seq = gerador_profissional.contar_consecutivos(jogo)
                            
                            st.markdown(f"""
                            <div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <strong>🏆 Jogo Profissional #{i+1:2d}</strong>
                                    <small>⚖️ {pares}×{15-pares} | 🔁 {repetidas} rep | ➕ {soma} | 📈 seq {seq}</small>
                                </div>
                                <div>{nums_html}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos Profissionais", key="salvar_profissional", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_gerados(
                                jogos,
                                list(range(1, 18)),
                                {"modelo": "Profissional", "regras": info},
                                ultimo['concurso'],
                                ultimo['data']
                            )
                            if arquivo:
                                st.success(f"✅ Jogos profissionais salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                    
                    with col2:
                        if st.button("🔄 Nova Geração", key="nova_geracao_profissional", use_container_width=True):
                            st.session_state.jogos_profissionais = None
                            st.rerun()
                    
                    with col3:
                        # Exportar para CSV
                        df_export_prof = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Pares": stats_df["Pares"],
                            "Repetidas": stats_df["Repetidas"],
                            "Soma": stats_df["Soma"],
                            "Sequência_Max": stats_df["Sequência Max"],
                            "Baixas(01-08)": stats_df["Baixas"],
                            "Médias(09-16)": stats_df["Médias"],
                            "Altas(17-25)": stats_df["Altas"]
                        })
                        
                        csv_prof = df_export_prof.to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar CSV Profissional",
                            data=csv_prof,
                            file_name=f"jogos_profissionais_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

        with tab3:
            st.subheader("📊 Motor Estatístico - Avaliação Probabilística")
            
            # Usar função segura para acessar jogos
            jogos_gerados = get_jogos_seguros()
            
            # GARANTIR QUE OS JOGOS ESTÃO NO FORMATO CORRETO
            if jogos_gerados:
                jogos_gerados = garantir_jogos_como_listas(jogos_gerados)
            
            # Verificar se há jogos gerados
            if not jogos_gerados:
                st.warning("⚠️ Gere jogos na aba 'Fechamento 3622' primeiro para avaliá-los estatisticamente!")
                st.info("💡 Os jogos gerados são salvos automaticamente e ficam disponíveis em todas as abas.")
            
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
            
            # =====================================================
            # 🎲 GERADOR OTIMIZADO PELO MOTOR ESTATÍSTICO
            # =====================================================
            st.markdown("---")
            st.markdown("## 🎲 Gerador Otimizado pelo Motor Estatístico")
            st.caption("5 jogos gerados com base nas distribuições empíricas e features históricas")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("🚀 GERAR 5 JOGOS OTIMIZADOS", key="gerar_otimizados", use_container_width=True, type="primary"):
                    with st.spinner("Gerando jogos com base nas distribuições estatísticas..."):
                        
                        # =========================================
                        # FUNÇÃO INTERNA PARA GERAR JOGO OTIMIZADO
                        # =========================================
                        def gerar_jogo_otimizado(dist, historico_df):
                            """
                            Gera um jogo otimizado usando as distribuições empíricas
                            """
                            max_tentativas = 11280000
                            melhor_jogo = None
                            melhor_logL = -float('inf')
                            
                            for tentativa in range(max_tentativas):
                                # GERAR JOGO ALEATÓRIO BASE
                                jogo_candidato = sorted(random.sample(range(1, 26), 15))
                                
                                # CALCULAR FEATURES
                                features = {
                                    "pares": contar_pares(jogo_candidato),
                                    "primos": contar_primos(jogo_candidato),
                                    "consecutivos": contar_consecutivos(jogo_candidato),
                                    "soma": bucket_soma(sum(jogo_candidato))
                                }
                                
                                # CALCULAR LIKELIHOOD
                                logL = log_likelihood(features, dist)
                                
                                # MANTER O MELHOR
                                if logL > melhor_logL:
                                    melhor_logL = logL
                                    melhor_jogo = jogo_candidato
                            
                            return melhor_jogo, melhor_logL
                        
                        # =========================================
                        # GERAR 5 JOGOS OTIMIZADOS
                        # =========================================
                        jogos_otimizados = []
                        logs_otimizados = []
                        
                        for i in range(5):
                            jogo, logL = gerar_jogo_otimizado(dist, st.session_state.historico_df)
                            if jogo:
                                jogos_otimizados.append(jogo)
                                logs_otimizados.append(logL)
                        
                        # SALVAR NA SESSÃO
                        st.session_state.jogos_otimizados = jogos_otimizados
                        st.session_state.logs_otimizados = logs_otimizados
                        
                        st.success(f"✅ 5 jogos gerados com sucesso! Log-likelihood médio: {np.mean(logs_otimizados):.4f}")
            
            # MOSTRAR JOGOS OTIMIZADOS SE EXISTIREM
            if "jogos_otimizados" in st.session_state and st.session_state.jogos_otimizados:
                jogos_otimizados = st.session_state.jogos_otimizados
                logs_otimizados = st.session_state.logs_otimizados
                
                st.markdown("### 📊 Jogos Otimizados pelo Motor Estatístico")
                
                # COMPARAR COM BASELINE
                baseline = st.session_state.baseline_cache or baseline_aleatorio()
                
                # CALCULAR PERCENTIS RELATIVOS AO BASELINE
                percentis = []
                for jogo in jogos_otimizados:
                    # Simular probabilidade de acertos via Monte Carlo rápido
                    mc_fast = monte_carlo_jogo(tuple(jogo), 5000)  # Rápido para não travar
                    percentis.append(mc_fast["P>=11"] * 100)
                
                # MOSTrar cada jogo
                for i, (jogo, logL, pct) in enumerate(zip(jogos_otimizados, logs_otimizados, percentis)):
                    with st.container():
                        # Calcular features para exibição
                        features_jogo = {
                            "pares": contar_pares(jogo),
                            "primos": contar_primos(jogo),
                            "consecutivos": contar_consecutivos(jogo),
                            "soma": sum(jogo)
                        }
                        
                        # Determinar cor baseada no logL
                        if logL > np.percentile(logs_otimizados, 80):
                            cor = "#4ade80"  # Verde (excelente)
                        elif logL > np.percentile(logs_otimizados, 50):
                            cor = "gold"      # Amarelo (bom)
                        else:
                            cor = "#4cc9f0"   # Azul (médio)
                        
                        # HTML do jogo
                        nums_html = formatar_jogo_html(jogo)
                        
                        st.markdown(f"""
                        <div style='border-left: 5px solid {cor}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                            <div style='display:flex; justify-content:space-between;'>
                                <strong>Jogo Otimizado #{i+1}</strong>
                                <small>LogL: {logL:.4f}</small>
                            </div>
                            <div>{nums_html}</div>
                            <div style='display:flex; gap:15px; margin-top:8px; color:#aaa; font-size:0.9em; flex-wrap:wrap;'>
                                <span>⚖️ {features_jogo['pares']} pares</span>
                                <span>🔢 {features_jogo['primos']} primos</span>
                                <span>🔗 {features_jogo['consecutivos']} consec</span>
                                <span>➕ {features_jogo['soma']}</span>
                                <span>🎯 P(≥11): {pct:.1f}%</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # BOTÕES DE AÇÃO PARA JOGOS OTIMIZADOS
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Salvar Jogos Otimizados", key="salvar_otimizados", use_container_width=True):
                        if st.session_state.dados_api:
                            ultimo = st.session_state.dados_api[0]
                            arquivo, jogo_id = salvar_jogos_gerados(
                                jogos_otimizados,
                                list(range(1, 18)),
                                {"modelo": "Motor Estatístico", "tipo": "otimizado"},
                                ultimo['concurso'],
                                ultimo['data']
                            )
                            if arquivo:
                                st.success(f"✅ Jogos otimizados salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                
                with col2:
                    if st.button("🔄 Nova Geração", key="nova_geracao_otimizados", use_container_width=True):
                        st.session_state.jogos_otimizados = None
                        st.rerun()
                
                with col3:
                    # Exportar para CSV
                    df_export_otimizado = pd.DataFrame({
                        "Jogo": range(1, len(jogos_otimizados)+1),
                        "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos_otimizados],
                        "Pares": [contar_pares(j) for j in jogos_otimizados],
                        "Primos": [contar_primos(j) for j in jogos_otimizados],
                        "Consecutivos": [contar_consecutivos(j) for j in jogos_otimizados],
                        "Soma": [sum(j) for j in jogos_otimizados],
                        "Log-Likelihood": [round(l, 4) for l in logs_otimizados],
                        "P(≥11)": [f"{p:.1f}%" for p in percentis]
                    })
                    
                    csv_otimizado = df_export_otimizado.to_csv(index=False)
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=csv_otimizado,
                        file_name=f"jogos_otimizados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                # COMPARAÇÃO COM BASELINE
                st.markdown("### 📊 Análise Comparativa")
                
                # Calcular médias dos jogos otimizados
                media_pares = np.mean([contar_pares(j) for j in jogos_otimizados])
                media_primos = np.mean([contar_primos(j) for j in jogos_otimizados])
                media_consec = np.mean([contar_consecutivos(j) for j in jogos_otimizados])
                media_soma = np.mean([sum(j) for j in jogos_otimizados])
                
                # Calcular médias históricas
                hist_pares = st.session_state.historico_df["pares"].mean()
                hist_primos = st.session_state.historico_df["primos"].mean()
                hist_consec = st.session_state.historico_df["consecutivos"].mean()
                hist_soma = st.session_state.historico_df["soma"].mean()
                
                # Criar DataFrame comparativo
                df_comp = pd.DataFrame({
                    "Feature": ["Pares", "Primos", "Consecutivos", "Soma"],
                    "Jogos Otimizados": [media_pares, media_primos, media_consec, media_soma],
                    "Média Histórica": [hist_pares, hist_primos, hist_consec, hist_soma]
                })
                
                st.dataframe(df_comp, use_container_width=True, hide_index=True)
                
                # Probabilidade média de acertos
                st.markdown("### 🎯 Probabilidade Média de Acertos")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("P(≥11) média", f"{np.mean(percentis):.1f}%")
                with col2:
                    st.metric("P(≥12) média", "---")
                with col3:
                    st.metric("vs Baseline", f"{np.mean(percentis) - baseline['media']*100:.1f}%")
                
                st.markdown("---")
            
            # AVALIAÇÃO DOS JOGOS (Likelihood com pesos)
            st.markdown("### 🎯 Ranking Estatístico dos Jogos")
            
            if jogos_gerados:
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
                
                # =====================================================
                # TOP JOGOS RECOMENDADOS
                # =====================================================
                st.markdown("### 🏆 Top 5 Jogos Recomendados")
                
                # Verificar se há jogos suficientes
                if len(df_avaliacao) > 0:
                    # Filtrar top 5 por score
                    top_jogos = df_avaliacao.nlargest(min(5, len(df_avaliacao)), "Score (0-100)")
                    
                    for idx, row in top_jogos.iterrows():
                        jogo_idx = row["Jogo"] - 1
                        
                        # USAR FUNÇÃO DE EXTRAÇÃO SEGURA
                        jogo = extrair_jogo_por_indice(jogos_gerados, jogo_idx)
                        
                        # Verificar se conseguiu extrair o jogo
                        if not jogo:
                            st.error(f"❌ Não foi possível extrair o jogo {row['Jogo']}")
                            continue
                        
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
                            <div style='display:flex; gap:15px; margin-top:8px; color:#aaa; font-size:0.9em; flex-wrap:wrap;'>
                                <span>⚖️ {features_jogo['pares']} pares</span>
                                <span>🔢 {features_jogo['primos']} primos</span>
                                <span>🔗 {features_jogo['consecutivos']} consecutivos</span>
                                <span>➕ {features_jogo['soma']} soma</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
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
                    value=st.session_state.mc_sim_value,
                    step=1_000,
                    key="mc_slider_principal"
                )
                st.session_state.mc_sim_value = N_SIM

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
            else:
                st.info("👆 Gere jogos na aba 'Fechamento 3622' primeiro para ver o ranking estatístico.")

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
                # SELEÇÃO DO FECHAMENTO COM PERSISTÊNCIA
                # =========================
                opcoes = [
                    f"ID {j['id']} | Concurso Base #{j['concurso_base']['numero']} | {j['data_geracao'][:19]}"
                    for j in st.session_state.jogos_salvos
                ]

                # Verificar se o índice salvo ainda é válido
                if st.session_state.idx_fechamento_conferencia >= len(opcoes):
                    st.session_state.idx_fechamento_conferencia = 0

                idx = st.selectbox(
                    "📦 Selecione o fechamento",
                    range(len(opcoes)),
                    format_func=lambda i: opcoes[i],
                    index=st.session_state.idx_fechamento_conferencia,
                    key="select_fechamento_conferencia"
                )
                
                # ATUALIZAR ESTADO
                st.session_state.idx_fechamento_conferencia = idx

                fechamento = st.session_state.jogos_salvos[idx]
                jogos_brutos = fechamento["jogos"]

                # =========================
                # NORMALIZAÇÃO DOS JOGOS
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

        # =====================================================
        # ABA: GERADOR 12+
        # =====================================================
        with tab6:
            st.markdown("""
            <div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px;'>
                <h4 style='margin:0; color:#4ade80;'>🚀 GERADOR 12+ (MODELO COBERTURA)</h4>
                <p style='margin:5px 0 0 0; font-size:0.9em;'>Baseado na análise dos últimos 20 concursos • Foco em 12+ pontos</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                
                # Pegar os últimos 20 concursos para análise
                ultimos_concursos = [
                    sorted(map(int, c['dezenas'])) 
                    for c in st.session_state.dados_api[:20]
                ]
                
                # Criar gerador 12+
                gerador_12plus = Gerador12Plus(
                    concursos_historico=ultimos_concursos,
                    ultimo_concurso=numeros_ultimo
                )
                
                # Mostrar estatísticas recentes
                st.markdown("### 📊 Estatísticas dos Últimos 20 Concursos")
                stats = gerador_12plus.get_estatisticas_recentes()
                
                if stats:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Média Baixas", f"{stats['baixas']:.1f}")
                    with col2:
                        st.metric("Média Médias", f"{stats['medias']:.1f}")
                    with col3:
                        st.metric("Média Altas", f"{stats['altas']:.1f}")
                    with col4:
                        st.metric("Média Soma", f"{stats['soma']:.1f}")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Média Pares", f"{stats['pares']:.1f}")
                    with col2:
                        st.metric("Média Primos", f"{stats['primos']:.1f}")
                    with col3:
                        st.metric("Média Repetidas", f"{stats['repetidas']:.1f}")
                    with col4:
                        st.metric("", "")  # Espaço vazio
                
                # Mostrar regras do modelo 12+
                with st.expander("📜 VER REGRAS DO MODELO 12+", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""
                        **📊 REGRAS FIXAS (OBRIGATÓRIAS)**
                        
                        **Distribuição:**
                        - Baixas (01-08): **4 ou 5**
                        - Médias (09-16): **5 ou 6**
                        - Altas (17-25): **5 ou 6**
                        
                        **Pares/Ímpares:** 7 ou 8 pares
                        
                        **Soma:** 190 a 210 (janela premium)
                        
                        **Primos:** 5 ou 6 números primos
                        """)
                    
                    with col2:
                        st.markdown("""
                        **🛡️ REGRAS DE BLOQUEIO**
                        
                        **Repetidas do último concurso:** 9 a 11
                        
                        **Consecutivos:**
                        - 2 a 4 pares consecutivos
                        - Pelo menos 1 bloco ≥ 3 números
                        
                        **❌ PROIBIDO:**
                        - Altas ≤ 4
                        - Repetidas ≤ 7
                        - Soma < 185 ou > 215
                        - Pares ≤ 6 ou ≥ 9
                        """)
                
                # Configuração de geração
                st.markdown("### 🎯 Gerar Jogos 12+")
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    qtd_jogos_12plus = st.slider(
                        "Quantidade de jogos", 
                        min_value=3, 
                        max_value=50, 
                        value=st.session_state.qtd_12plus,
                        key="slider_qtd_12plus"
                    )
                    st.session_state.qtd_12plus = qtd_jogos_12plus
                
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 GERAR JOGOS 12+", key="gerar_12plus", use_container_width=True, type="primary"):
                        with st.spinner(f"Gerando {qtd_jogos_12plus} jogos com validação rigorosa..."):
                            jogos, diagnosticos = gerador_12plus.gerar_multiplos_jogos(qtd_jogos_12plus)
                            
                            if jogos:
                                st.session_state.jogos_12plus = jogos
                                st.session_state.diagnosticos_12plus = diagnosticos
                                st.success(f"✅ {len(jogos)} jogos válidos gerados!")
                            else:
                                st.error("❌ Não foi possível gerar jogos válidos. Tente novamente.")
                
                with col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔄 Reset", key="reset_12plus", use_container_width=True):
                        st.session_state.jogos_12plus = None
                        st.rerun()
                
                # Mostrar jogos gerados
                if "jogos_12plus" in st.session_state and st.session_state.jogos_12plus:
                    jogos = st.session_state.jogos_12plus
                    diagnosticos = st.session_state.diagnosticos_12plus if "diagnosticos_12plus" in st.session_state else [None] * len(jogos)
                    
                    st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                    
                    # Estatísticas agregadas
                    stats_df = pd.DataFrame({
                        "Jogo": range(1, len(jogos)+1),
                        "Baixas": [sum(1 for n in j if n in gerador_12plus.baixas) for j in jogos],
                        "Médias": [sum(1 for n in j if n in gerador_12plus.medias) for j in jogos],
                        "Altas": [sum(1 for n in j if n in gerador_12plus.altas) for j in jogos],
                        "Pares": [sum(1 for n in j if n % 2 == 0) for j in jogos],
                        "Primos": [sum(1 for n in j if n in gerador_12plus.primos) for j in jogos],
                        "Soma": [sum(j) for j in jogos],
                        "Repetidas": [len(set(j) & set(gerador_12plus.ultimo)) for j in jogos],
                        "Consec": [gerador_12plus._contar_consecutivos(j) for j in jogos],
                        "Bloco": [gerador_12plus._maior_bloco_consecutivo(j) for j in jogos]
                    })
                    
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    
                    # Mostrar cada jogo formatado
                    for i, (jogo, diag) in enumerate(zip(jogos, diagnosticos)):
                        with st.container():
                            # Determinar cor baseada na qualidade
                            if diag and diag.get("regras_aprovadas", 0) == diag.get("total_regras", 7):
                                cor_borda = "#4ade80"  # Verde - perfeito
                            elif diag and diag.get("regras_aprovadas", 0) >= 6:
                                cor_borda = "gold"     # Amarelo - bom
                            else:
                                cor_borda = "#f97316"  # Laranja - regular
                            
                            # Formatar números
                            nums_html = formatar_jogo_html(jogo)
                            
                            # Estatísticas resumidas
                            baixas = sum(1 for n in jogo if n in gerador_12plus.baixas)
                            medias = sum(1 for n in jogo if n in gerador_12plus.medias)
                            altas = sum(1 for n in jogo if n in gerador_12plus.altas)
                            pares = sum(1 for n in jogo if n % 2 == 0)
                            soma = sum(jogo)
                            
                            st.markdown(f"""
                            <div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                <strong>Jogo {i+1:2d}:</strong> {nums_html}<br>
                                <small style='color:#aaa;'>
                                📊 {baixas}B/{medias}M/{altas}A | ⚖️ {pares}×{15-pares} | ➕ {soma}
                                </small>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos 12+", key="salvar_12plus", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_gerados(
                                jogos, 
                                list(range(1, 18)),  # Fechamento placeholder
                                {"modelo": "12+", "tipo": "cobertura"},
                                ultimo['concurso'],
                                ultimo['data']
                            )
                            if arquivo:
                                st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                    
                    with col2:
                        if st.button("🔄 Nova Geração", key="nova_geracao_12plus", use_container_width=True):
                            st.session_state.jogos_12plus = None
                            st.rerun()
                    
                    with col3:
                        # Exportar para CSV
                        df_export_12plus = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Baixas(01-08)": stats_df["Baixas"],
                            "Médias(09-16)": stats_df["Médias"],
                            "Altas(17-25)": stats_df["Altas"],
                            "Pares": stats_df["Pares"],
                            "Primos": stats_df["Primos"],
                            "Soma": stats_df["Soma"],
                            "Repetidas": stats_df["Repetidas"],
                            "Consecutivos": stats_df["Consec"],
                            "Maior_Bloco": stats_df["Bloco"]
                        })
                        
                        csv_12plus = df_export_12plus.to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar CSV",
                            data=csv_12plus,
                            file_name=f"jogos_12plus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    # Explicação do modelo
                    with st.expander("📘 Como funciona o Gerador 12+?"):
                        st.markdown("""
                        ### 🎯 Estratégia do Gerador 12+
                        
                        **1. Pool ponderado:**
                        - Números mais frequentes nos últimos 10 concursos têm maior peso
                        - Números do último concurso têm peso extra (3x)
                        
                        **2. Validação rigorosa:**
                        - 7 regras obrigatórias (distribuição, pares, soma, primos, repetidas, consecutivos, bloco grande)
                        - 7 regras de bloqueio que eliminam jogos fora do padrão
                        
                        **3. Otimização:**
                        - Geração de milhares de jogos até encontrar os que atendem TODAS as regras
                        - Eliminação de duplicatas
                        
                        **4. Foco em 12+ pontos:**
                        - Baseado nos padrões reais dos últimos 20 concursos
                        - Elimina exceções estatísticas (apenas 0.1% dos jogos aleatórios passam)
                        """)

        # =====================================================
        # ABA: GERADOR 13+
        # =====================================================
        with tab7:
            st.markdown("""
            <div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #f97316;'>
                <h4 style='margin:0; color:#f97316;'>🔥 GERADOR 13+ (MODELO ULTRA)</h4>
                <p style='margin:5px 0 0 0; font-size:0.9em;'>Zona de convergência máxima • Tiro de precisão para 13+ pontos</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                
                # Pegar os últimos 20 concursos para análise
                ultimos_concursos = [
                    sorted(map(int, c['dezenas'])) 
                    for c in st.session_state.dados_api[:20]
                ]
                
                # Criar gerador 13+
                gerador_13plus = Gerador13Plus(
                    concursos_historico=ultimos_concursos,
                    ultimo_concurso=numeros_ultimo
                )
                
                # Mostrar estatísticas recentes
                st.markdown("### 📊 Estatísticas dos Últimos 20 Concursos")
                stats = gerador_13plus.get_estatisticas_recentes()
                
                if stats:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Média Baixas", f"{stats['baixas']:.1f}")
                    with col2:
                        st.metric("Média Médias", f"{stats['medias']:.1f}")
                    with col3:
                        st.metric("Média Altas", f"{stats['altas']:.1f}")
                    with col4:
                        st.metric("Média Soma", f"{stats['soma']:.1f}")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Média Pares", f"{stats['pares']:.1f}")
                    with col2:
                        st.metric("Média Primos", f"{stats['primos']:.1f}")
                    with col3:
                        st.metric("Média Repetidas", f"{stats['repetidas']:.1f}")
                    with col4:
                        st.metric("", "")  # Espaço vazio
                
                # Mostrar regras do modelo 13+
                with st.expander("📜 VER REGRAS DO MODELO 13+", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""
                        **📊 REGRAS FIXAS (ZONA 13+)**
                        
                        **Distribuição CRÍTICA:**
                        - Baixas (01-08): **4** (fixo)
                        - Médias (09-16): **6** (fixo)
                        - Altas (17-25): **5** (fixo)
                        
                        **Pares:** **7** (fixo)
                        
                        **Soma (zona premium):** **195 a 205**
                        
                        **Primos:** **5** (fixo)
                        """)
                    
                    with col2:
                        st.markdown("""
                        **🛡️ REGRAS DE BLOQUEIO (ANTI-12)**
                        
                        **Repetidas do último:** **10 ou 11**
                        
                        **Consecutivos:**
                        - Quantidade: **3 ou 4**
                        - 1 bloco longo (≥3)
                        - 1 bloco curto (2)
                        
                        **❌ PROIBIDO:**
                        - Soma < 190 ou > 210
                        - Altas ≤ 4
                        - Repetidas ≤ 9
                        - Médias ≤ 5
                        - Menos de 2 blocos
                        """)
                
                # Configuração de geração
                st.markdown("### 🎯 Gerar Jogos 13+ (Precisão)")
                st.caption("⚠️ Modelo extremamente restritivo. Pode levar alguns segundos para encontrar jogos válidos.")
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    qtd_jogos_13plus = st.slider(
                        "Quantidade de jogos", 
                        min_value=1, 
                        max_value=20, 
                        value=st.session_state.qtd_13plus,
                        key="slider_qtd_13plus"
                    )
                    st.session_state.qtd_13plus = qtd_jogos_13plus
                
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔥 GERAR JOGOS 13+", key="gerar_13plus", use_container_width=True, type="primary"):
                        with st.spinner(f"Gerando {qtd_jogos_13plus} jogos 13+ (pode levar alguns segundos)..."):
                            jogos, diagnosticos = gerador_13plus.gerar_multiplos_jogos(qtd_jogos_13plus)
                            
                            if jogos:
                                st.session_state.jogos_13plus = jogos
                                st.session_state.diagnosticos_13plus = diagnosticos
                                st.balloons()
                            else:
                                st.error("❌ Não foi possível gerar jogos 13+. Tente novamente ou reduza a quantidade.")
                
                with col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔄 Reset", key="reset_13plus", use_container_width=True):
                        st.session_state.jogos_13plus = None
                        st.rerun()
                
                # Mostrar jogos gerados
                if "jogos_13plus" in st.session_state and st.session_state.jogos_13plus:
                    jogos = st.session_state.jogos_13plus
                    diagnosticos = st.session_state.diagnosticos_13plus if "diagnosticos_13plus" in st.session_state else [None] * len(jogos)
                    
                    st.markdown(f"### 📋 Jogos 13+ Gerados ({len(jogos)})")
                    
                    # Estatísticas agregadas
                    stats_df = pd.DataFrame({
                        "Jogo": range(1, len(jogos)+1),
                        "Baixas": [sum(1 for n in j if n in gerador_13plus.baixas) for j in jogos],
                        "Médias": [sum(1 for n in j if n in gerador_13plus.medias) for j in jogos],
                        "Altas": [sum(1 for n in j if n in gerador_13plus.altas) for j in jogos],
                        "Pares": [sum(1 for n in j if n % 2 == 0) for j in jogos],
                        "Primos": [sum(1 for n in j if n in gerador_13plus.primos) for j in jogos],
                        "Soma": [sum(j) for j in jogos],
                        "Repetidas": [len(set(j) & set(gerador_13plus.ultimo)) for j in jogos],
                        "Consec": [gerador_13plus._contar_consecutivos(j) for j in jogos],
                        "Bloco": [gerador_13plus._maior_bloco_consecutivo(j) for j in jogos],
                        "2Blocos": [gerador_13plus._tem_dois_blocos(j) for j in jogos]
                    })
                    
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    
                    # Mostrar cada jogo formatado com destaque especial
                    for i, (jogo, diag) in enumerate(zip(jogos, diagnosticos)):
                        with st.container():
                            # Cor especial para 13+
                            cor_borda = "#f97316"  # Laranja
                            
                            # Formatar números
                            nums_html = formatar_jogo_html(jogo)
                            
                            # Estatísticas resumidas
                            baixas = sum(1 for n in jogo if n in gerador_13plus.baixas)
                            medias = sum(1 for n in jogo if n in gerador_13plus.medias)
                            altas = sum(1 for n in jogo if n in gerador_13plus.altas)
                            pares = sum(1 for n in jogo if n % 2 == 0)
                            soma = sum(jogo)
                            repetidas = len(set(jogo) & set(gerador_13plus.ultimo))
                            bloco = gerador_13plus._maior_bloco_consecutivo(jogo)
                            
                            st.markdown(f"""
                            <div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <strong>🔥 Jogo 13+ #{i+1:2d}</strong>
                                    <small style='color:#f97316;'>Precisão</small>
                                </div>
                                <div>{nums_html}</div>
                                <div style='display:flex; gap:15px; margin-top:8px; color:#aaa; font-size:0.9em; flex-wrap:wrap;'>
                                    <span>📊 {baixas}B/{medias}M/{altas}A</span>
                                    <span>⚖️ {pares}×{15-pares}</span>
                                    <span>➕ {soma}</span>
                                    <span>🔁 {repetidas} rep</span>
                                    <span>🔗 bloco {bloco}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos 13+", key="salvar_13plus", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_gerados(
                                jogos, 
                                list(range(1, 18)),  # Fechamento placeholder
                                {"modelo": "13+", "tipo": "ultra"},
                                ultimo['concurso'],
                                ultimo['data']
                            )
                            if arquivo:
                                st.success(f"✅ Jogos 13+ salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                    
                    with col2:
                        if st.button("🔄 Nova Geração", key="nova_geracao_13plus", use_container_width=True):
                            st.session_state.jogos_13plus = None
                            st.rerun()
                    
                    with col3:
                        # Exportar para CSV
                        df_export_13plus = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Baixas(01-08)": stats_df["Baixas"],
                            "Médias(09-16)": stats_df["Médias"],
                            "Altas(17-25)": stats_df["Altas"],
                            "Pares": stats_df["Pares"],
                            "Primos": stats_df["Primos"],
                            "Soma": stats_df["Soma"],
                            "Repetidas": stats_df["Repetidas"],
                            "Consecutivos": stats_df["Consec"],
                            "Maior_Bloco": stats_df["Bloco"],
                            "Tem_2_Blocos": stats_df["2Blocos"]
                        })
                        
                        csv_13plus = df_export_13plus.to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar CSV",
                            data=csv_13plus,
                            file_name=f"jogos_13plus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    # Explicação do modelo Ultra
                    with st.expander("📘 Como funciona o Gerador 13+?"):
                        st.markdown("""
                        ### 🎯 Estratégia do Gerador 13+ (Modelo Ultra)
                        
                        **Diferente do 12+, este modelo é extremamente restritivo:**
                        
                        **1. Pool ponderado agressivo:**
                        - Números mais frequentes nos últimos 20 concursos
                        - Números do último concurso têm peso 4x
                        
                        **2. Validação ultra rigorosa:**
                        - 8 regras fixas (valores exatos, não faixas)
                        - 8 regras de bloqueio
                        - Exige 2 blocos consecutivos (1 longo + 1 curto)
                        
                        **3. Estatísticas:**
                        - Apenas ~0.01% dos jogos aleatórios passam
                        - Geração de 500.000 tentativas para encontrar 5-10 jogos
                        
                        **4. Foco:**
                        - 13+ pontos (zona de convergência máxima)
                        - Tiro de precisão, não cobertura
                        """)

        # =====================================================
        # ABA 8: INTELIGÊNCIA 5-7-3 (CORRIGIDA - AGORA DENTRO DA FUNÇÃO MAIN)
        # =====================================================
        with tab8:
            st.markdown("""
            <div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #aa00ff;'>
                <h4 style='margin:0; color:#aa00ff;'>🧠 MODO INTELIGENTE 5-7-3</h4>
                <p style='margin:5px 0 0 0; font-size:0.9em;'>Detector de Sinal Automático + Filtro de Elite com os 4 padrões prioritários</p>
                <p style='margin:2px 0 0 0; font-size:0.85em; color:#ccc;'>Padrões aceitos: <strong>5-7-3</strong> (prioridade máxima), 5-6-4, 6-6-3, 4-7-4 (cobrem 68% dos concursos)</p>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.dados_api:
                # Pega os últimos concursos para análise de sinal
                ultimos_concursos_para_sinal = [
                    sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:10]
                ]

                # --- DETECTOR DE SINAL EM TEMPO REAL ---
                st.markdown("### 🔍 Análise de Sinal em Tempo Real")
                sinal_detectado = detectar_sinal(ultimos_concursos_para_sinal)

                # Indicador visual do sinal
                if sinal_detectado:
                    st.markdown("""
                    <div style='background:#aa00ff20; padding:20px; border-radius:15px; text-align:center; border:2px solid #aa00ff; margin-bottom:15px;'>
                        <h2 style='color:#aa00ff; margin:0;'>🟢 SINAL SNIPER ATIVADO</h2>
                        <p style='margin:0;'>Modo de alta precisão. Apenas os 4 padrões prioritários são aceitos.</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='background:#66666620; padding:20px; border-radius:15px; text-align:center; border:2px solid #666; margin-bottom:15px;'>
                        <h2 style='color:#ccc; margin:0;'>⚪ SINAL DESLIGADO</h2>
                        <p style='margin:0;'>Modo livre. Apenas score mínimo aplicado, mas padrões fora dos 4 prioritários são tolerados.</p>
                    </div>
                    """, unsafe_allow_html=True)

                # --- ESTATÍSTICAS DOS PADRÕES NOS CONCURSOS REAIS ---
                with st.expander("📊 Análise dos Padrões nos Concursos Reais", expanded=False):
                    # Analisar os últimos 50 concursos
                    ultimos_50 = [sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:50]]
                    contagem_padroes = {
                        "5-7-3": 0,
                        "5-6-4": 0,
                        "6-6-3": 0,
                        "4-7-4": 0,
                        "outros": 0
                    }
                    
                    for c in ultimos_50:
                        f = contar_faixas_573(c)
                        padrao = f"{f['baixa']}-{f['media']}-{f['alta']}"
                        if padrao in contagem_padroes:
                            contagem_padroes[padrao] += 1
                        else:
                            contagem_padroes["outros"] += 1
                    
                    # Mostrar tabela
                    df_padroes = pd.DataFrame({
                        "Padrão": list(contagem_padroes.keys()),
                        "Ocorrências": list(contagem_padroes.values()),
                        "Percentual": [f"{v/len(ultimos_50)*100:.1f}%" for v in contagem_padroes.values()]
                    })
                    
                    st.dataframe(df_padroes, use_container_width=True, hide_index=True)
                    
                    total_cobertura = (contagem_padroes["5-7-3"] + contagem_padroes["5-6-4"] + 
                                      contagem_padroes["6-6-3"] + contagem_padroes["4-7-4"])
                    st.metric("Cobertura dos 4 padrões", f"{total_cobertura/len(ultimos_50)*100:.1f}%", 
                             f"{total_cobertura}/{len(ultimos_50)} concursos")

                # --- SELEÇÃO DE JOGOS PARA FILTRAR ---
                st.markdown("### 🎯 Aplicar Inteligência aos Jogos")
                
                # Opção de escolher de qual gerador pegar os jogos
                fonte_jogos = st.radio(
                    "Selecione a fonte dos jogos:",
                    [
                        "Jogos do Fechamento 3622", 
                        "Jogos do Gerador 12+", 
                        "Jogos do Gerador 13+",
                        "Jogos do Gerador Profissional",
                        "Gerar Novos Jogos 12+ para Teste"
                    ],
                    horizontal=True,
                    key="fonte_inteligencia_radio"
                )
                
                # ATUALIZAR ESTADO
                st.session_state.fonte_inteligencia = fonte_jogos

                # Preparar lista de jogos baseado na fonte selecionada
                jogos_para_filtrar = []
                
                if st.session_state.fonte_inteligencia == "Jogos do Fechamento 3622" and st.session_state.jogos_3622:
                    jogos_para_filtrar = st.session_state.jogos_3622
                    st.caption(f"📋 {len(jogos_para_filtrar)} jogos do Fechamento 3622 carregados")
                
                elif st.session_state.fonte_inteligencia == "Jogos do Gerador 12+" and st.session_state.jogos_12plus:
                    jogos_para_filtrar = st.session_state.jogos_12plus
                    st.caption(f"📋 {len(jogos_para_filtrar)} jogos do Gerador 12+ carregados")
                
                elif st.session_state.fonte_inteligencia == "Jogos do Gerador 13+" and st.session_state.jogos_13plus:
                    jogos_para_filtrar = st.session_state.jogos_13plus
                    st.caption(f"📋 {len(jogos_para_filtrar)} jogos do Gerador 13+ carregados")
                
                elif st.session_state.fonte_inteligencia == "Jogos do Gerador Profissional" and st.session_state.jogos_profissionais:
                    jogos_para_filtrar = st.session_state.jogos_profissionais
                    st.caption(f"📋 {len(jogos_para_filtrar)} jogos do Gerador Profissional carregados")
                
                elif st.session_state.fonte_inteligencia == "Gerar Novos Jogos 12+ para Teste":
                    if "jogos_teste_intel" not in st.session_state or st.session_state.jogos_teste_intel is None:
                        with st.spinner("Gerando 20 jogos 12+ para teste..."):
                            ultimo = st.session_state.dados_api[0]
                            numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                            ultimos_concursos = [
                                sorted(map(int, c['dezenas'])) 
                                for c in st.session_state.dados_api[:20]
                            ]
                            gerador_12plus = Gerador12Plus(ultimos_concursos, numeros_ultimo)
                            jogos_temp, _ = gerador_12plus.gerar_multiplos_jogos(20)
                            if jogos_temp:
                                st.session_state.jogos_teste_intel = jogos_temp
                                jogos_para_filtrar = jogos_temp
                                st.success(f"✅ 20 jogos 12+ gerados!")
                    else:
                        jogos_para_filtrar = st.session_state.jogos_teste_intel
                        st.caption(f"📋 {len(jogos_para_filtrar)} jogos de teste carregados")

                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    threshold_score = st.slider(
                        "Score Mínimo", 
                        0, 10, 
                        value=st.session_state.threshold_intel,
                        key="slider_threshold_intel"
                    )
                    st.session_state.threshold_intel = threshold_score
                
                with col2:
                    modo_operacao = st.selectbox(
                        "Modo de Operação", 
                        ["auto", "forcar_on", "forcar_off"],
                        index=["auto", "forcar_on", "forcar_off"].index(st.session_state.modo_intel),
                        key="select_modo_intel"
                    )
                    st.session_state.modo_intel = modo_operacao
                
                with col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    botao_filtrar = st.button("✨ FILTRAR JOGOS", type="primary", use_container_width=True, key="filtrar_intel")

                if botao_filtrar:
                    if not jogos_para_filtrar:
                        st.warning("⚠️ Nenhum jogo encontrado na fonte selecionada. Gere jogos primeiro ou escolha outra fonte.")
                    else:
                        with st.spinner("Aplicando inteligência aos jogos..."):
                            jogos_aprovados, sinal_estava_ativo, stats = pipeline_selecao_inteligente(
                                jogos_para_filtrar, 
                                ultimos_concursos_para_sinal,
                                modo_operacao=modo_operacao,
                                threshold_score=threshold_score
                            )
                        
                        st.session_state.jogos_inteligentes = jogos_aprovados
                        st.session_state.stats_inteligentes = stats
                        st.success(f"✅ Filtragem concluída! {len(jogos_aprovados)} jogos aprovados.")

                # --- EXIBIÇÃO DOS RESULTADOS ---
                if "jogos_inteligentes" in st.session_state and st.session_state.jogos_inteligentes:
                    jogos_finais = st.session_state.jogos_inteligentes
                    stats = st.session_state.stats_inteligentes

                    st.markdown("---")
                    st.markdown("### 📊 Resultado da Seleção Inteligente")

                    # Estatísticas do processo
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Jogos Analisados", stats['total_jogos_analisados'])
                    with col2:
                        st.metric("Jogos Aprovados", stats['jogos_aprovados'])
                    with col3:
                        if stats['sinal_estava_ativo']:
                            st.metric("Filtro 5-7-3 Bloqueou", stats['jogos_filtrados_573'])
                        else:
                            st.metric("Filtro 5-7-3", "Inativo")
                    with col4:
                        st.metric("Reprovados por Score", stats['jogos_reprovados_score'])

                    # Distribuição dos padrões
                    st.markdown("#### 📈 Distribuição dos Padrões nos Jogos Analisados")
                    df_padroes_analisados = pd.DataFrame({
                        "Padrão": list(stats['jogos_por_padrao'].keys()),
                        "Quantidade": list(stats['jogos_por_padrao'].values())
                    })
                    st.dataframe(df_padroes_analisados, use_container_width=True, hide_index=True)

                    # Tabela com scores dos jogos aprovados
                    scores_data = []
                    for i, jogo in enumerate(jogos_finais):
                        f = contar_faixas_573(jogo)
                        padrao = f"{f['baixa']}-{f['media']}-{f['alta']}"
                        scores_data.append({
                            "Rank": i+1,
                            "Padrão": padrao,
                            "Score": score_jogo_573(jogo),
                            "Dezenas": ", ".join(f"{n:02d}" for n in jogo)
                        })
                    
                    scores_df = pd.DataFrame(scores_data).sort_values("Score", ascending=False).reset_index(drop=True)
                    scores_df["Rank"] = scores_df.index + 1
                    st.dataframe(scores_df[["Rank", "Padrão", "Score", "Dezenas"]], use_container_width=True, hide_index=True)

                    # Mostrar cada jogo formatado
                    for i, jogo in enumerate(jogos_finais[:10]):
                        with st.container():
                            f = contar_faixas_573(jogo)
                            padrao = f"{f['baixa']}-{f['media']}-{f['alta']}"
                            pares, _ = paridade_573(jogo)
                            s = soma_573(jogo)
                            score = score_jogo_573(jogo)
                            
                            nums_html = formatar_jogo_html(jogo)
                            
                            if padrao == "5-7-3":
                                cor_borda = "#aa00ff"
                                destaque = "🔥 PRIORIDADE MÁXIMA"
                            elif score >= 8:
                                cor_borda = "#4ade80"
                                destaque = "✅ Excelente"
                            elif score >= 6:
                                cor_borda = "#4cc9f0"
                                destaque = "👍 Bom"
                            else:
                                cor_borda = "#f97316"
                                destaque = "⚠️ Regular"
                            
                            st.markdown(f"""
                            <div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <strong>Jogo Elite #{i+1} - Padrão {padrao}</strong>
                                    <span style='color:{cor_borda}; font-weight:bold;'>Score: {score:.1f} | {destaque}</span>
                                </div>
                                <div>{nums_html}</div>
                                <div style='display:flex; gap:15px; margin-top:8px; color:#aaa; font-size:0.9em; flex-wrap:wrap;'>
                                    <span>📊 {f['baixa']}B/{f['media']}M/{f['alta']}A</span>
                                    <span>⚖️ {pares}×{15-pares}</span>
                                    <span>➕ {s}</span>
                                    <span>🔗 bloco {maior_bloco_consecutivo_573(jogo)}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos Inteligentes", key="salvar_intel", use_container_width=True):
                            ultimo = st.session_state.dados_api[0]
                            arquivo, jogo_id = salvar_jogos_gerados(
                                jogos_finais,
                                list(range(1, 18)),
                                {"modelo": "Inteligencia 5-7-3", "sinal": sinal_detectado, "padroes": "4 prioritários"},
                                ultimo['concurso'],
                                ultimo['data']
                            )
                            if arquivo:
                                st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                    
                    with col2:
                        if st.button("🔄 Nova Filtragem", use_container_width=True, key="nova_intel"):
                            st.session_state.jogos_inteligentes = None
                            st.rerun()
                    
                    with col3:
                        df_export_intel = pd.DataFrame({
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos_finais],
                            "Padrão": [f"{contar_faixas_573(j)['baixa']}-{contar_faixas_573(j)['media']}-{contar_faixas_573(j)['alta']}" for j in jogos_finais],
                            "Score": [score_jogo_573(j) for j in jogos_finais],
                            "Baixas": [contar_faixas_573(j)["baixa"] for j in jogos_finais],
                            "Médias": [contar_faixas_573(j)["media"] for j in jogos_finais],
                            "Altas": [contar_faixas_573(j)["alta"] for j in jogos_finais],
                            "Pares": [paridade_573(j)[0] for j in jogos_finais],
                            "Soma": [soma_573(j) for j in jogos_finais],
                            "Maior_Bloco": [maior_bloco_consecutivo_573(j) for j in jogos_finais]
                        })
                        csv_intel = df_export_intel.to_csv(index=False)
                        st.download_button(
                            label="📥 Exportar CSV",
                            data=csv_intel,
                            file_name=f"jogos_inteligentes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
            else:
                st.info("📥 Carregue os concursos na barra lateral para ativar a inteligência 5-7-3.")

# =====================================================
# EXECUÇÃO PRINCIPAL (FORA DA FUNÇÃO MAIN)
# =====================================================
if __name__ == "__main__":
    main()
