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
from scipy.stats import norm, binom
from itertools import combinations
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# TENTAR IMPORTAR OR-TOOLS (SOLVER PROFISSIONAL)
# =====================================================
try:
    from ortools.linear_solver import pywraplp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - EMS 8.0 ILP Professional",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
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
.highlight { background: #00ffaa20; border-left: 4px solid #00ffaa; padding: 10px; border-radius: 8px; margin: 10px 0; }
.ilp-highlight { background: linear-gradient(135deg, #00ffaa20 0%, #00aaff20 100%); border: 2px solid #00ffaa; padding: 15px; border-radius: 12px; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 LOTOFÁCIL - EMS 8.0 ILP PROFESSIONAL")
st.caption("Programação Linear Inteira (ILP) - Otimização Combinatória com Solver Profissional")

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def garantir_jogos_como_listas(jogos_entrada):
    if jogos_entrada is None:
        return []
    if isinstance(jogos_entrada, list) and len(jogos_entrada) > 0:
        if isinstance(jogos_entrada[0], list) and all(isinstance(n, int) for n in jogos_entrada[0]):
            return jogos_entrada
    jogos_normalizados = []
    if isinstance(jogos_entrada, pd.DataFrame):
        for _, row in jogos_entrada.iterrows():
            for col in row.index:
                valor = row[col]
                if isinstance(valor, str) and ("," in valor or " " in valor):
                    if "," in valor:
                        dezenas = [int(d.strip()) for d in valor.split(",")]
                    else:
                        dezenas = [int(d) for d in valor.split()]
                    jogos_normalizados.append(sorted(dezenas))
                    break
                elif isinstance(valor, list):
                    jogos_normalizados.append(sorted([int(x) for x in valor]))
                    break
        return jogos_normalizados
    if isinstance(jogos_entrada, list):
        for item in jogos_entrada:
            if isinstance(item, dict):
                for chave in ["Dezenas", "dezenas", "Jogo", "jogo"]:
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
            elif isinstance(item, str):
                if "," in item:
                    dezenas = [int(d.strip()) for d in item.split(",")]
                else:
                    dezenas = [int(d) for d in item.split()]
                jogos_normalizados.append(sorted(dezenas))
            elif isinstance(item, (list, tuple)):
                jogos_normalizados.append(sorted([int(x) for x in item]))
    return jogos_normalizados

def convert_numpy_types(obj):
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
    elif isinstance(obj, Counter):
        return dict(obj)
    else:
        return obj

def salvar_jogos_gerados(jogos, fechamento, dna_params, numero_concurso_atual, data_concurso_atual, estatisticas=None):
    try:
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/jogos_{data_hora}_{jogo_id}.json"
        jogos_convertidos = convert_numpy_types(jogos)
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_base": {"numero": int(numero_concurso_atual), "data": str(data_concurso_atual)},
            "jogos": jogos_convertidos,
            "estatisticas": convert_numpy_types(estatisticas) if estatisticas else {},
            "schema_version": "2.0"
        }
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_salvos():
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
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception:
                        continue
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos salvos: {e}")
    return jogos_salvos

def adicionar_conferencia(arquivo, concurso_info, acertos, estatisticas=None):
    try:
        caminho = f"jogos_salvos/{arquivo}"
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        if "conferencias" not in dados:
            dados["conferencias"] = []
        acertos_convertidos = [int(a) for a in acertos]
        nova_conferencia = {
            "concurso": concurso_info,
            "acertos": acertos_convertidos,
            "estatisticas": convert_numpy_types(estatisticas) if estatisticas else {},
            "data_conferencia": datetime.now().isoformat()
        }
        dados["conferencias"].append(nova_conferencia)
        dados["conferido"] = True
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar conferência: {e}")
        return False

def formatar_jogo_html(jogo, destaque_primos=True):
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
    if isinstance(jogo, dict):
        dezenas = []
        for chave in ["dezenas", "Dezenas", "jogo", "Jogo"]:
            if chave in jogo:
                val = jogo[chave]
                if isinstance(val, str):
                    dezenas = [int(d.strip()) for d in val.split(",") if d.strip()]
                elif isinstance(val, list):
                    dezenas = [int(d) for d in val]
                break
    elif isinstance(jogo, str):
        if "," in jogo:
            dezenas = [int(d.strip()) for d in jogo.split(",")]
        else:
            dezenas = [int(d) for d in jogo.split()]
    else:
        dezenas = jogo
    if not dezenas:
        return "Jogo inválido"
    html = ""
    for num in dezenas:
        if num in primos and destaque_primos:
            html += f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
        else:
            html += f"<span style='background:#0e1117; border:1px solid #262730; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
    return html

# =====================================================
# FUNÇÕES DE ANÁLISE ESTATÍSTICA
# =====================================================
def contar_pares(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def contar_por_faixa(jogo, faixa_limites):
    contagem = []
    for inicio, fim in faixa_limites:
        contagem.append(sum(1 for n in jogo if inicio <= n <= fim))
    return contagem

def distribuir_por_linhas(jogo):
    linhas = [0] * 5
    for n in jogo:
        linhas[(n-1)//5] += 1
    return linhas

def distribuir_por_colunas(jogo):
    colunas = [0] * 5
    for n in jogo:
        colunas[(n-1)%5] += 1
    return colunas

@st.cache_data
def baseline_aleatorio(n=200000):
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
    historico = []
    for concurso in dados_api[:qtd_concursos]:
        numeros = sorted(map(int, concurso['dezenas']))
        historico.append({
            "concurso": concurso['concurso'],
            "pares": contar_pares(numeros),
            "primos": contar_primos(numeros),
            "consecutivos": contar_consecutivos(numeros),
            "soma": sum(numeros),
            "linhas": tuple(distribuir_por_linhas(numeros))
        })
    return pd.DataFrame(historico)

# =====================================================
# EMS 8.0 - ILP PROFISSIONAL
# =====================================================

@st.cache_data
def monte_carlo_jogo(jogo_tuple, n_sim):
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

def calcular_pesos_inteligentes(gerador, ultimo_concurso, usar_frequencia=True, usar_atraso=True, usar_ultimo=True):
    """
    Calcula pesos inteligentes para cada dezena baseado em:
    - Frequência histórica
    - Atraso (tempo desde última aparição)
    - Repetição do último concurso
    
    Retorna um array numpy de 25 posições com os pesos normalizados.
    """
    # Inicializa array de pesos com zeros
    pesos = np.zeros(25)
    
    # Verifica se gerador existe e tem os atributos necessários
    if gerador is not None:
        if usar_frequencia and hasattr(gerador, 'frequencias'):
            freq = gerador.frequencias
            if freq:
                max_freq = max(freq.values())
                if max_freq > 0:
                    for i in range(1, 26):
                        pesos[i-1] += (freq.get(i, 0) / max_freq) * 0.5
        
        if usar_atraso and hasattr(gerador, 'atrasos'):
            atrasos = gerador.atrasos
            if atrasos:
                max_atraso = max(atrasos.values())
                if max_atraso > 0:
                    for i in range(1, 26):
                        pesos[i-1] += (atrasos.get(i, 0) / max_atraso) * 0.3
    
    # Adiciona peso para números do último concurso
    if usar_ultimo and ultimo_concurso is not None:
        if isinstance(ultimo_concurso, (set, list)):
            for num in ultimo_concurso:
                idx = num - 1
                if 0 <= idx < 25:
                    pesos[idx] += 0.2
        elif isinstance(ultimo_concurso, dict):
            for num in ultimo_concurso.get('dezenas', []):
                idx = int(num) - 1
                if 0 <= idx < 25:
                    pesos[idx] += 0.2
    
    # Normaliza para soma 1
    soma_pesos = pesos.sum()
    if soma_pesos > 0:
        pesos = pesos / soma_pesos
    
    return pesos

def gerar_jogo_ilp_profissional(pesos, ultimo_concurso, config_filtros, solver_timeout=10):
    """
    Gera o jogo otimizado usando Programação Linear Inteira (ILP)
    com OR-Tools SCIP solver.
    """
    if not ORTOOLS_AVAILABLE:
        return None, "OR-Tools não disponível"
    
    NUM_DEZENAS = 25
    NUM_ESCOLHER = 15
    
    try:
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            return None, "Solver SCIP não disponível"
    except Exception as e:
        return None, f"Erro ao criar solver: {e}"
    
    # Variáveis binárias
    x = {}
    for i in range(NUM_DEZENAS):
        x[i] = solver.IntVar(0, 1, f'x[{i}]')
    
    # Função objetivo
    objective = solver.Objective()
    for i in range(NUM_DEZENAS):
        objective.SetCoefficient(x[i], pesos[i])
    objective.SetMaximization()
    
    # Restrição: exatamente 15 dezenas
    solver.Add(solver.Sum(x[i] for i in range(NUM_DEZENAS)) == NUM_ESCOLHER)
    
    # Restrição: pares/ímpares
    pares = [i for i in range(NUM_DEZENAS) if (i+1) % 2 == 0]
    pares_min = config_filtros.get('pares_min', 6)
    pares_max = config_filtros.get('pares_max', 9)
    solver.Add(solver.Sum(x[i] for i in pares) >= pares_min)
    solver.Add(solver.Sum(x[i] for i in pares) <= pares_max)
    
    # Restrição: repetição do último concurso
    if ultimo_concurso:
        if isinstance(ultimo_concurso, (set, list)):
            indices_ultimo = [i for i in range(NUM_DEZENAS) if (i+1) in ultimo_concurso]
        elif isinstance(ultimo_concurso, dict):
            ultimo_set = set(map(int, ultimo_concurso.get('dezenas', [])))
            indices_ultimo = [i for i in range(NUM_DEZENAS) if (i+1) in ultimo_set]
        else:
            indices_ultimo = []
        
        if indices_ultimo:
            rep_min = config_filtros.get('repetidas_min', 7)
            rep_max = config_filtros.get('repetidas_max', 10)
            solver.Add(solver.Sum(x[i] for i in indices_ultimo) >= rep_min)
            solver.Add(solver.Sum(x[i] for i in indices_ultimo) <= rep_max)
    
    # Restrição: linhas
    linhas = [
        range(0, 5), range(5, 10), range(10, 15),
        range(15, 20), range(20, 25)
    ]
    linha_min = config_filtros.get('linhas_min_max', [(2,4)]*5)
    for idx, linha in enumerate(linhas):
        min_q = linha_min[idx][0] if idx < len(linha_min) else 2
        max_q = linha_min[idx][1] if idx < len(linha_min) else 4
        solver.Add(solver.Sum(x[i] for i in linha) >= min_q)
        solver.Add(solver.Sum(x[i] for i in linha) <= max_q)
    
    # Restrição: colunas
    colunas = [
        [0,5,10,15,20], [1,6,11,16,21], [2,7,12,17,22],
        [3,8,13,18,23], [4,9,14,19,24]
    ]
    coluna_min = config_filtros.get('colunas_min_max', [(2,4)]*5)
    for idx, coluna in enumerate(colunas):
        min_q = coluna_min[idx][0] if idx < len(coluna_min) else 2
        max_q = coluna_min[idx][1] if idx < len(coluna_min) else 4
        solver.Add(solver.Sum(x[i] for i in coluna) >= min_q)
        solver.Add(solver.Sum(x[i] for i in coluna) <= max_q)
    
    # Restrição: soma das dezenas
    soma_min = config_filtros.get('soma_min', 160)
    soma_max = config_filtros.get('soma_max', 240)
    solver.Add(solver.Sum((i+1) * x[i] for i in range(NUM_DEZENAS)) >= soma_min)
    solver.Add(solver.Sum((i+1) * x[i] for i in range(NUM_DEZENAS)) <= soma_max)
    
    # Restrição: consecutivos
    consecutivos_max = config_filtros.get('consecutivos_max', 5)
    for i in range(NUM_DEZENAS - consecutivos_max):
        sequencia = list(range(i, i + consecutivos_max + 1))
        solver.Add(solver.Sum(x[j] for j in sequencia) <= consecutivos_max)
    
    # Resolver
    solver.SetTimeLimit(solver_timeout * 1000)
    status = solver.Solve()
    
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        jogo = [i+1 for i in range(NUM_DEZENAS) if x[i].solution_value() > 0.5]
        return sorted(jogo), f"Ótimo encontrado (status: {status})"
    else:
        return None, f"Nenhuma solução (status: {status})"

def gerar_multiplos_jogos_ilp(gerador, ultimo_concurso, config_filtros, qtd_jogos=10, timeout_por_jogo=5, usar_diversidade=True):
    """Gera múltiplos jogos otimizados via ILP"""
    if not ORTOOLS_AVAILABLE:
        st.error("OR-Tools não disponível")
        return []
    
    jogos = []
    
    for idx in range(qtd_jogos):
        with st.spinner(f"Gerando jogo {idx+1}/{qtd_jogos} via ILP..."):
            pesos = calcular_pesos_inteligentes(gerador, ultimo_concurso, True, True, True)
            
            if usar_diversidade and jogos:
                for jogo_existente in jogos:
                    for num in jogo_existente:
                        idx_num = num - 1
                        if 0 <= idx_num < 25:
                            pesos[idx_num] *= 0.95
                soma_pesos = pesos.sum()
                if soma_pesos > 0:
                    pesos = pesos / soma_pesos
            
            jogo, status = gerar_jogo_ilp_profissional(pesos, ultimo_concurso, config_filtros, timeout_por_jogo)
            
            if jogo:
                jogos.append(jogo)
                st.success(f"Jogo {idx+1}: {jogo[:5]}... - OK")
            else:
                st.warning(f"Jogo {idx+1} falhou: {status}")
    
    return jogos

# =====================================================
# GERADOR BASE
# =====================================================
class GeradorLotofacil:
    def __init__(self, historico_concursos, ultimo_concurso):
        self.historico = historico_concursos
        self.ultimo = set(ultimo_concurso) if ultimo_concurso else set()
        self.frequencias = self._calcular_frequencias()
        self.atrasos = self._calcular_atrasos()
        self.pool_ponderado = self._criar_pool_ponderado()

    def _calcular_frequencias(self):
        freq = Counter()
        for concurso in self.historico:
            freq.update(concurso)
        total = sum(freq.values())
        return {n: freq.get(n, 0) / total for n in range(1, 26)} if total > 0 else {n: 0 for n in range(1, 26)}

    def _calcular_atrasos(self):
        if not self.historico:
            return {n: 0 for n in range(1, 26)}
        atrasos = {}
        for num in range(1, 26):
            atraso = 0
            for concurso in self.historico:
                if num in concurso:
                    break
                atraso += 1
            atrasos[num] = atraso
        return atrasos

    def _criar_pool_ponderado(self, peso_freq=0.7, peso_atraso=0.3):
        max_freq = max(self.frequencias.values()) if self.frequencias else 1
        max_atraso = max(self.atrasos.values()) if self.atrasos else 1
        numeros = []
        pesos = []
        for n in range(1, 26):
            freq_norm = self.frequencias.get(n, 0) / max_freq if max_freq > 0 else 0
            atraso_norm = self.atrasos.get(n, 0) / max_atraso if max_atraso > 0 else 0
            peso = freq_norm * peso_freq + atraso_norm * peso_atraso
            if n in self.ultimo:
                peso *= 1.2
            numeros.append(n)
            pesos.append(peso)
        pesos = np.array(pesos)
        if pesos.sum() > 0:
            pesos /= pesos.sum()
        return numeros, pesos

    def aplicar_filtros(self, jogo, config_filtros):
        # Pares
        if config_filtros.get('pares_min', 0) > 0:
            pares = contar_pares(jogo)
            if not (config_filtros['pares_min'] <= pares <= config_filtros['pares_max']):
                return False
        # Soma
        if config_filtros.get('soma_min', 0) > 0:
            soma = sum(jogo)
            if not (config_filtros['soma_min'] <= soma <= config_filtros['soma_max']):
                return False
        # Faixas
        if config_filtros.get('faixas', []):
            faixas = [(1, 8), (9, 16), (17, 25)]
            contagem = contar_por_faixa(jogo, faixas)
            for i, (min_q, max_q) in enumerate(config_filtros['faixas']):
                if not (min_q <= contagem[i] <= max_q):
                    return False
        # Consecutivos
        if config_filtros.get('consecutivos_max', 0) > 0:
            if contar_consecutivos(jogo) > config_filtros['consecutivos_max']:
                return False
        # Linhas
        if config_filtros.get('linhas_min_max', []):
            linhas = distribuir_por_linhas(jogo)
            for i, (min_q, max_q) in enumerate(config_filtros['linhas_min_max']):
                if not (min_q <= linhas[i] <= max_q):
                    return False
        # Colunas
        if config_filtros.get('colunas_min_max', []):
            colunas = distribuir_por_colunas(jogo)
            for i, (min_q, max_q) in enumerate(config_filtros['colunas_min_max']):
                if not (min_q <= colunas[i] <= max_q):
                    return False
        # Repetidas
        if config_filtros.get('repetidas_min', 0) > 0:
            repetidas = len(set(jogo) & self.ultimo)
            if not (config_filtros['repetidas_min'] <= repetidas <= config_filtros['repetidas_max']):
                return False
        return True

    def gerar_jogo(self, config_filtros, max_tentativas=5000):
        numeros, pesos = self.pool_ponderado
        for _ in range(max_tentativas):
            indices = np.random.choice(len(numeros), size=15, replace=False, p=pesos)
            jogo = sorted([numeros[i] for i in indices])
            if self.aplicar_filtros(jogo, config_filtros):
                return jogo
        return sorted(random.sample(range(1, 26), 15))

    def gerar_multiplos_jogos(self, quantidade, config_filtros, max_tentativas_por_jogo=2000):
        jogos = []
        tentativas_totais = 0
        progress_bar = st.progress(0, text="Gerando jogos...")
        while len(jogos) < quantidade and tentativas_totais < quantidade * max_tentativas_por_jogo:
            jogo = self.gerar_jogo(config_filtros, max_tentativas=max_tentativas_por_jogo)
            if jogo and jogo not in jogos:
                jogos.append(jogo)
            tentativas_totais += 1
            progress_bar.progress(min(len(jogos) / quantidade, 1.0), text=f"Gerados {len(jogos)}/{quantidade}")
        progress_bar.empty()
        if len(jogos) < quantidade:
            st.warning(f"Apenas {len(jogos)} jogos gerados em {tentativas_totais} tentativas.")
        return jogos

# =====================================================
# GEOMETRIA
# =====================================================
class MotorGeometria:
    def __init__(self, concursos_historico):
        self.concursos = concursos_historico
        self.volante = np.array([[1,2,3,4,5],[6,7,8,9,10],[11,12,13,14,15],[16,17,18,19,20],[21,22,23,24,25]])
        self.coordenadas = {self.volante[i][j]:(i,j) for i in range(5) for j in range(5)}
        self.matriz_coocorrencia = self._calcular_matriz_coocorrencia()

    def _calcular_matriz_coocorrencia(self):
        M = np.zeros((26, 26))
        for jogo in self.concursos:
            for i in jogo:
                for j in jogo:
                    if i != j:
                        M[i][j] += 1
        return M

    def get_pares_recomendados(self, numero_base, top_n=5):
        if numero_base < 1 or numero_base > 25:
            return []
        linha = self.matriz_coocorrencia[numero_base]
        pares = [(i, linha[i]) for i in range(1, 26) if i != numero_base and linha[i] > 0]
        pares.sort(key=lambda x: x[1], reverse=True)
        return pares[:top_n]

# =====================================================
# CONFERIDOR
# =====================================================
def parse_dezenas(dezenas_str):
    if isinstance(dezenas_str, str):
        return set(map(int, dezenas_str.replace('"', '').replace(' ', '').split(',')))
    elif isinstance(dezenas_str, list):
        return set(dezenas_str)
    return set()

def conferir_jogos_inteligente(jogos, resultado_set):
    resultados = []
    for i, jogo in enumerate(jogos):
        if isinstance(jogo, str):
            dezenas = parse_dezenas(jogo)
        else:
            dezenas = set(jogo)
        acertos = dezenas.intersection(resultado_set)
        resultados.append({
            "Jogo": i + 1,
            "Acertos": len(acertos),
            "Acertos_Dezenas": sorted(acertos),
            "Dezenas": sorted(dezenas)
        })
    df = pd.DataFrame(resultados)
    return df.sort_values(by="Acertos", ascending=False).reset_index(drop=True)

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================
def main():
    # Inicialização
    if "dados_api" not in st.session_state:
        st.session_state.dados_api = None
    if "gerador_principal" not in st.session_state:
        st.session_state.gerador_principal = None
    if "motor_geometria" not in st.session_state:
        st.session_state.motor_geometria = None
    if "jogos_gerados" not in st.session_state:
        st.session_state.jogos_gerados = None
    if "scores" not in st.session_state:
        st.session_state.scores = []
    if "baseline_cache" not in st.session_state:
        st.session_state.baseline_cache = baseline_aleatorio()
    if "config_filtros" not in st.session_state:
        st.session_state.config_filtros = {
            'pares_min': 6, 'pares_max': 9,
            'soma_min': 180, 'soma_max': 210,
            'faixas': [(5, 6), (5, 6), (3, 4)],
            'consecutivos_max': 5,
            'linhas_min_max': [(2, 4)] * 5,
            'colunas_min_max': [(2, 4)] * 5,
            'repetidas_min': 7, 'repetidas_max': 10
        }

    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Qtd concursos históricos", 20, 500, 100)
        if st.button("📥 Carregar concursos", use_container_width=True):
            with st.spinner("Carregando dados..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    response = requests.get(url)
                    st.session_state.dados_api = response.json()
                    concursos = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
                    st.session_state.baseline_cache = baseline_aleatorio()
                    st.session_state.motor_geometria = MotorGeometria(concursos)
                    st.session_state.gerador_principal = GeradorLotofacil(concursos, concursos[0])
                    st.success(f"✅ Último concurso: #{st.session_state.dados_api[0]['concurso']}")
                except Exception as e:
                    st.error(f"Erro: {e}")

    if not st.session_state.dados_api:
        st.info("👈 Carregue os concursos na barra lateral para começar.")
        return

    st.subheader("🎯 EMS 8.0 - ILP Professional")

    if not ORTOOLS_AVAILABLE:
        st.warning("⚠️ OR-Tools não instalado. Execute: pip install ortools")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🔥 ILP PROFESSIONAL",
        "🎯 Gerador Tradicional",
        "🔍 Conferência",
        "📐 Geometria"
    ])

    # ================= TAB 1: ILP PROFESSIONAL =================
    with tab1:
        st.markdown("### 🔥 ILP PROFESSIONAL")
        st.markdown("""
        <div class="ilp-highlight">
        <strong>🎯 Programação Linear Inteira (ILP):</strong><br>
        • Transforma a Lotofácil em um problema de otimização combinatória exata<br>
        • Usa solver profissional (OR-Tools/SCIP) para encontrar a solução ótima<br>
        • Todas as restrições são aplicadas como equações lineares<br>
        • GARANTE o melhor jogo possível dentro das restrições!
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("⚙️ Configurações ILP", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                pares_min = st.number_input("Mínimo Pares", 0, 15, value=6, key="ilp_pmin")
                pares_max = st.number_input("Máximo Pares", 0, 15, value=9, key="ilp_pmax")
                soma_min = st.number_input("Soma Mínima", 150, 300, value=180, key="ilp_smin")
                soma_max = st.number_input("Soma Máxima", 150, 300, value=210, key="ilp_smax")
                rep_min = st.number_input("Mínimo Repetidas", 0, 15, value=7, key="ilp_rmin")
                rep_max = st.number_input("Máximo Repetidas", 0, 15, value=10, key="ilp_rmax")
            with col2:
                cons_max = st.number_input("Máx Consecutivos", 0, 10, value=5, key="ilp_cmax")
                linha_min = st.number_input("Mínimo/Linha", 0, 5, value=2, key="ilp_lmin")
                linha_max = st.number_input("Máximo/Linha", 0, 5, value=4, key="ilp_lmax")
                coluna_min = st.number_input("Mínimo/Coluna", 0, 5, value=2, key="ilp_colmin")
                coluna_max = st.number_input("Máximo/Coluna", 0, 5, value=4, key="ilp_colmax")
            
            st.session_state.config_filtros.update({
                'pares_min': pares_min, 'pares_max': pares_max,
                'soma_min': soma_min, 'soma_max': soma_max,
                'repetidas_min': rep_min, 'repetidas_max': rep_max,
                'consecutivos_max': cons_max,
                'linhas_min_max': [(linha_min, linha_max)] * 5,
                'colunas_min_max': [(coluna_min, coluna_max)] * 5
            })
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_ilp = st.slider("Quantidade de jogos", 1, 15, 5, key="qtd_ilp")
        with col2:
            timeout = st.slider("Timeout (segundos)", 2, 20, 8, key="timeout_ilp")
        
        if st.button("🚀 GERAR JOGO ÓTIMO VIA ILP", use_container_width=True, type="primary"):
            if not ORTOOLS_AVAILABLE:
                st.error("OR-Tools não disponível")
            else:
                ultimo = st.session_state.dados_api[0]
                pesos = calcular_pesos_inteligentes(
                    st.session_state.gerador_principal,
                    ultimo,
                    usar_frequencia=True,
                    usar_atraso=True,
                    usar_ultimo=True
                )
                
                with st.spinner("Resolvendo otimização..."):
                    jogo, status = gerar_jogo_ilp_profissional(
                        pesos, ultimo, st.session_state.config_filtros, timeout
                    )
                    
                    if jogo:
                        st.session_state.jogos_gerados = [jogo]
                        mc = monte_carlo_jogo(tuple(jogo), 2000)
                        st.success("✅ Jogo ótimo encontrado!")
                        
                        st.markdown(f"""
                        <div class="ilp-highlight">
                        <strong>🎲 Jogo Gerado:</strong> {formatar_jogo_html(jogo)}<br>
                        <strong>📊 P(13+):</strong> {mc['P>=13']*100:.2f}%<br>
                        <strong>📊 P(14+):</strong> {mc['P>=14']*100:.2f}%<br>
                        <strong>🔧 Status:</strong> {status}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error(f"Falha: {status}")
        
        if st.button("🎲 GERAR MÚLTIPLOS JOGOS ILP", use_container_width=True):
            if not ORTOOLS_AVAILABLE:
                st.error("OR-Tools não disponível")
            else:
                ultimo = st.session_state.dados_api[0]
                jogos = gerar_multiplos_jogos_ilp(
                    st.session_state.gerador_principal,
                    ultimo,
                    st.session_state.config_filtros,
                    qtd_jogos=qtd_ilp,
                    timeout_por_jogo=timeout,
                    usar_diversidade=True
                )
                if jogos:
                    st.session_state.jogos_gerados = jogos
                    st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)['P>=13'] * 100 for j in jogos]
                    st.success(f"✅ {len(jogos)} jogos gerados!")
        
        if st.session_state.jogos_gerados:
            st.markdown(f"### 📋 {len(st.session_state.jogos_gerados)} Jogos Gerados")
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                prob = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                st.markdown(f"""
                <div style='border-left: 5px solid #00ffaa; background:#0e1117; border-radius:10px; padding:12px; margin:8px 0;'>
                    <strong>Jogo {i+1}</strong> — P(13+): {prob:.2f}%<br>
                    {formatar_jogo_html(jogo)}
                </div>
                """, unsafe_allow_html=True)
            
            if st.button("💾 Salvar Jogos", use_container_width=True):
                ultimo = st.session_state.dados_api[0]
                arquivo, _ = salvar_jogos_gerados(
                    st.session_state.jogos_gerados, [], {},
                    ultimo['concurso'], ultimo['data']
                )
                if arquivo:
                    st.success("✅ Jogos salvos!")

    # ================= TAB 2: GERADOR TRADICIONAL =================
    with tab2:
        st.markdown("### 🎲 Gerador Tradicional")
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_trad = st.slider("Quantidade", 5, 30, 10, key="trad_qtd")
        with col2:
            if st.button("🎲 GERAR JOGOS", use_container_width=True):
                with st.spinner(f"Gerando {qtd_trad} jogos..."):
                    jogos = st.session_state.gerador_principal.gerar_multiplos_jogos(
                        qtd_trad, st.session_state.config_filtros
                    )
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)['P>=13'] * 100 for j in jogos]
                        st.success(f"✅ {len(jogos)} jogos gerados!")
        
        if st.session_state.jogos_gerados:
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                prob = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                st.markdown(f"""
                <div style='border-left: 5px solid #4cc9f0; background:#0e1117; border-radius:10px; padding:12px; margin:8px 0;'>
                    <strong>Jogo {i+1}</strong> — P(13+): {prob:.2f}%<br>
                    {formatar_jogo_html(jogo)}
                </div>
                """, unsafe_allow_html=True)

    # ================= TAB 3: CONFERÊNCIA =================
    with tab3:
        st.markdown("### 🔍 Conferência")
        
        concurso = st.selectbox(
            "Concurso para conferir",
            st.session_state.dados_api,
            format_func=lambda c: f"#{c['concurso']} - {c['data']}"
        )
        
        if concurso:
            resultado = set(map(int, concurso['dezenas']))
            st.markdown(f"**Resultado #{concurso['concurso']}:** {formatar_jogo_html(sorted(resultado))}", unsafe_allow_html=True)
        
        if st.session_state.jogos_gerados and concurso:
            if st.button("🔍 CONFERIR", use_container_width=True):
                df = conferir_jogos_inteligente(st.session_state.jogos_gerados, resultado)
                st.dataframe(df, use_container_width=True, hide_index=True)

    # ================= TAB 4: GEOMETRIA =================
    with tab4:
        st.markdown("### 📐 Geometria do Volante")
        
        num = st.number_input("Número base", 1, 25, 13)
        pares = st.session_state.motor_geometria.get_pares_recomendados(num, 10)
        if pares:
            st.markdown(f"**Números relacionados ao {num:02d}:**")
            st.markdown(" ".join(f"<span style='border:1px solid #00ffaa; border-radius:15px; padding:5px; margin:2px; display:inline-block;'>{p[0]:02d} ({p[1]})</span>" for p in pares), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
