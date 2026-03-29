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
    # Não mostra warning aqui para não poluir a interface

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
.cover-stats { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 15px; border-radius: 12px; margin: 10px 0; border: 1px solid #00ffaa20; }
.highlight { background: #00ffaa20; border-left: 4px solid #00ffaa; padding: 10px; border-radius: 8px; margin: 10px 0; }
.ev-highlight { background: linear-gradient(135deg, #ffd70020 0%, #ffa50020 100%); border: 1px solid #ffd700; padding: 15px; border-radius: 12px; margin: 10px 0; }
.pro-highlight { background: linear-gradient(135deg, #ff00ff20 0%, #aa00ff20 100%); border: 2px solid #ff00ff; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ilp-highlight { background: linear-gradient(135deg, #00ffaa20 0%, #00aaff20 100%); border: 2px solid #00ffaa; padding: 15px; border-radius: 12px; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 LOTOFÁCIL - EMS 8.0 ILP PROFESSIONAL")
st.caption("Programação Linear Inteira (ILP) - Otimização Combinatória com Solver Profissional")

# =====================================================
# FUNÇÕES AUXILIARES (GARANTIR JOGOS COMO LISTAS)
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

@st.cache_data
def distribuicoes_empiricas(historico_df):
    return {
        "pares": historico_df["pares"].value_counts(normalize=True).to_dict(),
        "primos": historico_df["primos"].value_counts(normalize=True).to_dict(),
        "consecutivos": historico_df["consecutivos"].value_counts(normalize=True).to_dict(),
        "soma": historico_df["soma"].apply(lambda s: (s//20)*20).value_counts(normalize=True).to_dict()
    }

def log_likelihood(features, dist):
    logL = 0
    for k, v in features.items():
        p = dist.get(k, {}).get(v, 1e-9)
        logL += math.log(p)
    return logL

# =====================================================
# EMS 8.0 - ILP PROFISSIONAL COM OR-TOOLS
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
    - Padrões estruturais
    
    Retorna um array numpy de 25 posições com os pesos normalizados.
    """
    # Inicializa array de pesos com zeros
    pesos = np.zeros(25)
    
    if usar_frequencia and gerador:
        freq = gerador.frequencias
        max_freq = max(freq.values()) if freq else 1
        for i in range(25):
            pesos[i] += (freq.get(i+1, 0) / max_freq) * 0.5
    
    if usar_atraso and gerador:
        atrasos = gerador.atrasos
        max_atraso = max(atrasos.values()) if atrasos else 1
        for i in range(25):
            pesos[i] += (atrasos.get(i+1, 0) / max_atraso) * 0.3
    
    if usar_ultimo and ultimo_concurso:
        for num in ultimo_concurso:
            idx = num - 1
            if 0 <= idx < 25:
                pesos[idx] += 0.2
    
    # Normaliza para soma 1
    soma_pesos = pesos.sum()
    if soma_pesos > 0:
        pesos = pesos / soma_pesos
    
    return pesos

def gerar_jogo_ilp_profissional(
    pesos,
    ultimo_concurso,
    config_filtros,
    solver_timeout=10
):
    """
    Gera o jogo otimizado usando Programação Linear Inteira (ILP)
    com OR-Tools SCIP solver.
    
    Args:
        pesos: array com pesos para cada dezena (1-25)
        ultimo_concurso: set com números do último concurso
        config_filtros: dicionário com restrições
        solver_timeout: tempo máximo em segundos
    
    Returns:
        jogo otimizado como lista de 15 números
        status do solver
    """
    
    if not ORTOOLS_AVAILABLE:
        return None, "OR-Tools não disponível"
    
    NUM_DEZENAS = 25
    NUM_ESCOLHER = 15
    
    # Cria solver SCIP (melhor para problemas inteiros)
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        return None, "Solver SCIP não disponível"
    
    # Variáveis binárias: x[i] = 1 se dezena i+1 for escolhida
    x = {}
    for i in range(NUM_DEZENAS):
        x[i] = solver.IntVar(0, 1, f'x[{i}]')
    
    # =====================================================
    # FUNÇÃO OBJETIVO: Maximizar soma dos pesos
    # =====================================================
    objective = solver.Objective()
    for i in range(NUM_DEZENAS):
        objective.SetCoefficient(x[i], pesos[i])
    objective.SetMaximization()
    
    # =====================================================
    # RESTRIÇÃO 1: Exatamente 15 dezenas
    # =====================================================
    solver.Add(solver.Sum(x[i] for i in range(NUM_DEZENAS)) == NUM_ESCOLHER)
    
    # =====================================================
    # RESTRIÇÃO 2: Pares / Ímpares
    # =====================================================
    pares = [i for i in range(NUM_DEZENAS) if (i+1) % 2 == 0]
    pares_min = config_filtros.get('pares_min', 6)
    pares_max = config_filtros.get('pares_max', 9)
    solver.Add(solver.Sum(x[i] for i in pares) >= pares_min)
    solver.Add(solver.Sum(x[i] for i in pares) <= pares_max)
    
    # =====================================================
    # RESTRIÇÃO 3: Repetição do último concurso
    # =====================================================
    if ultimo_concurso:
        rep_min = config_filtros.get('repetidas_min', 7)
        rep_max = config_filtros.get('repetidas_max', 10)
        indices_ultimo = [i for i in range(NUM_DEZENAS) if (i+1) in ultimo_concurso]
        if indices_ultimo:
            solver.Add(solver.Sum(x[i] for i in indices_ultimo) >= rep_min)
            solver.Add(solver.Sum(x[i] for i in indices_ultimo) <= rep_max)
    
    # =====================================================
    # RESTRIÇÃO 4: Linhas do volante (0-4)
    # =====================================================
    linhas = [
        range(0, 5),   # Linha 1: 1-5
        range(5, 10),  # Linha 2: 6-10
        range(10, 15), # Linha 3: 11-15
        range(15, 20), # Linha 4: 16-20
        range(20, 25)  # Linha 5: 21-25
    ]
    linha_min = config_filtros.get('linhas_min_max', [(2,4)]*5)
    for idx, linha in enumerate(linhas):
        min_q = linha_min[idx][0] if idx < len(linha_min) else 2
        max_q = linha_min[idx][1] if idx < len(linha_min) else 4
        solver.Add(solver.Sum(x[i] for i in linha) >= min_q)
        solver.Add(solver.Sum(x[i] for i in linha) <= max_q)
    
    # =====================================================
    # RESTRIÇÃO 5: Colunas do volante
    # =====================================================
    colunas = [
        [0,5,10,15,20],   # Coluna 1: 1,6,11,16,21
        [1,6,11,16,21],   # Coluna 2: 2,7,12,17,22
        [2,7,12,17,22],   # Coluna 3: 3,8,13,18,23
        [3,8,13,18,23],   # Coluna 4: 4,9,14,19,24
        [4,9,14,19,24]    # Coluna 5: 5,10,15,20,25
    ]
    coluna_min = config_filtros.get('colunas_min_max', [(2,4)]*5)
    for idx, coluna in enumerate(colunas):
        min_q = coluna_min[idx][0] if idx < len(coluna_min) else 2
        max_q = coluna_min[idx][1] if idx < len(coluna_min) else 4
        solver.Add(solver.Sum(x[i] for i in coluna) >= min_q)
        solver.Add(solver.Sum(x[i] for i in coluna) <= max_q)
    
    # =====================================================
    # RESTRIÇÃO 6: Soma das dezenas
    # =====================================================
    soma_min = config_filtros.get('soma_min', 160)
    soma_max = config_filtros.get('soma_max', 240)
    solver.Add(solver.Sum((i+1) * x[i] for i in range(NUM_DEZENAS)) >= soma_min)
    solver.Add(solver.Sum((i+1) * x[i] for i in range(NUM_DEZENAS)) <= soma_max)
    
    # =====================================================
    # RESTRIÇÃO 7: Consecutivos (evita sequências muito longas)
    # =====================================================
    consecutivos_max = config_filtros.get('consecutivos_max', 5)
    # Adiciona restrições para cada possível sequência de (consecutivos_max+1) números
    for i in range(NUM_DEZENAS - consecutivos_max):
        sequencia = list(range(i, i + consecutivos_max + 1))
        solver.Add(solver.Sum(x[j] for j in sequencia) <= consecutivos_max)
    
    # =====================================================
    # RESOLVER
    # =====================================================
    solver.SetTimeLimit(solver_timeout * 1000)  # Converte para milissegundos
    
    status = solver.Solve()
    
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        jogo = [i+1 for i in range(NUM_DEZENAS) if x[i].solution_value() > 0.5]
        return sorted(jogo), f"Ótimo encontrado (status: {status})"
    else:
        return None, f"Nenhuma solução encontrada (status: {status})"

def gerar_multiplos_jogos_ilp(
    gerador,
    ultimo_concurso,
    config_filtros,
    qtd_jogos=10,
    timeout_por_jogo=5,
    usar_diversidade=True
):
    """
    Gera múltiplos jogos otimizados via ILP
    Com opção de diversidade via restrições adicionais
    """
    if not ORTOOLS_AVAILABLE:
        st.error("OR-Tools não está instalado. Execute: pip install ortools")
        return []
    
    jogos = []
    
    for idx in range(qtd_jogos):
        with st.spinner(f"Gerando jogo {idx+1}/{qtd_jogos} via ILP..."):
            # Calcula pesos (pode variar para cada jogo se usar diversidade)
            pesos = calcular_pesos_inteligentes(
                gerador, 
                ultimo_concurso,
                usar_frequencia=True,
                usar_atraso=True,
                usar_ultimo=True
            )
            
            # Se usar diversidade, penaliza números já muito usados
            if usar_diversidade and jogos:
                for jogo_existente in jogos:
                    for num in jogo_existente:
                        idx_num = num - 1
                        if 0 <= idx_num < 25:
                            pesos[idx_num] *= 0.95  # Reduz peso de números já usados
                # Re-normaliza
                soma_pesos = pesos.sum()
                if soma_pesos > 0:
                    pesos = pesos / soma_pesos
            
            jogo, status = gerar_jogo_ilp_profissional(
                pesos,
                ultimo_concurso,
                config_filtros,
                solver_timeout=timeout_por_jogo
            )
            
            if jogo:
                jogos.append(jogo)
                st.success(f"Jogo {idx+1}: {jogo} - {status}")
            else:
                st.warning(f"Jogo {idx+1} falhou: {status}")
    
    return jogos

# =====================================================
# GEOMETRIA ANALÍTICA
# =====================================================
class MotorGeometria:
    def __init__(self, concursos_historico):
        self.concursos = concursos_historico
        self.total_concursos = len(concursos_historico)
        self.volante = np.array([[1,2,3,4,5],[6,7,8,9,10],[11,12,13,14,15],[16,17,18,19,20],[21,22,23,24,25]])
        self.coordenadas = {self.volante[i][j]:(i,j) for i in range(5) for j in range(5)}
        self.matriz_coocorrencia = self._calcular_matriz_coocorrencia()
        self.centroides = self._calcular_centroides()
        self.frequencias = self._calcular_frequencias()

    def num_to_coord(self, numero):
        return self.coordenadas.get(numero, (None, None))

    def _calcular_matriz_coocorrencia(self):
        M = np.zeros((26, 26))
        for jogo in self.concursos:
            for i in jogo:
                for j in jogo:
                    if i != j:
                        M[i][j] += 1
        return M

    def _calcular_centroides(self):
        centroides = []
        for jogo in self.concursos:
            xs, ys = [], []
            for num in jogo:
                x, y = self.num_to_coord(num)
                if x is not None:
                    xs.append(x)
                    ys.append(y)
            if xs and ys:
                centroides.append((sum(xs)/len(xs), sum(ys)/len(ys)))
            else:
                centroides.append((None, None))
        return centroides

    def _calcular_frequencias(self):
        freq = [0]*26
        for jogo in self.concursos:
            for num in jogo:
                freq[num] += 1
        return freq

    def dispersao_geometrica(self, jogo):
        coords = [self.num_to_coord(n) for n in jogo if n in self.coordenadas]
        if len(coords) < 2:
            return 0
        xs, ys = zip(*coords)
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
        distancias = [math.sqrt((x-cx)**2 + (y-cy)**2) for x,y in coords]
        return sum(distancias)/len(distancias)

    def get_estatisticas_geometricas(self):
        xs_validos = [c[0] for c in self.centroides if c[0] is not None]
        ys_validos = [c[1] for c in self.centroides if c[1] is not None]
        if not xs_validos or not ys_validos:
            return {}
        return {
            'centroide_medio': (round(np.mean(xs_validos), 2), round(np.mean(ys_validos), 2)),
            'dispersao_media': round(np.mean([self.dispersao_geometrica(c) for c in self.concursos]), 2)
        }

    def get_pares_recomendados(self, numero_base, top_n=5):
        if numero_base < 1 or numero_base > 25:
            return []
        linha = self.matriz_coocorrencia[numero_base]
        pares = [(i, linha[i]) for i in range(1, 26) if i != numero_base and linha[i] > 0]
        pares.sort(key=lambda x: x[1], reverse=True)
        return pares[:top_n]

    def analisar_jogo(self, jogo):
        jogo = sorted(jogo)
        xs, ys = zip(*[self.num_to_coord(n) for n in jogo if self.num_to_coord(n)[0] is not None])
        if not xs:
            return {}
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
        dist_centro = [math.sqrt((x-cx)**2 + (y-cy)**2) for x,y in zip(xs,ys)]
        return {
            'centroide': (round(cx, 2), round(cy, 2)),
            'dispersao_media': round(sum(dist_centro)/len(dist_centro), 2),
            'pares_adjacentes': sum(1 for i in range(len(jogo)) for j in range(i+1, len(jogo))
                                    if abs(xs[i]-xs[j]) + abs(ys[i]-ys[j]) == 1)
        }

# =====================================================
# GERADOR BASE (POOL PONDERADO + FILTROS)
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
        return {n: freq.get(n,0)/total for n in range(1,26)}

    def _calcular_atrasos(self):
        if not self.historico:
            return {n:0 for n in range(1,26)}
        atrasos = {}
        for num in range(1,26):
            atraso = 0
            for concurso in self.historico:
                if num in concurso:
                    break
                atraso += 1
            atrasos[num] = atraso
        return atrasos

    def _criar_pool_ponderado(self, peso_freq=0.7, peso_atraso=0.3):
        max_freq = max(self.frequencias.values())
        max_atraso = max(self.atrasos.values())
        pesos = []
        numeros = []
        for n in range(1,26):
            freq_norm = self.frequencias[n]/max_freq if max_freq > 0 else 0
            atraso_norm = self.atrasos[n]/max_atraso if max_atraso > 0 else 0
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
        if config_filtros.get('pares_min', 0) > 0:
            pares = contar_pares(jogo)
            if not (config_filtros['pares_min'] <= pares <= config_filtros['pares_max']):
                return False
        if config_filtros.get('soma_min', 0) > 0:
            soma = sum(jogo)
            if not (config_filtros['soma_min'] <= soma <= config_filtros['soma_max']):
                return False
        if config_filtros.get('faixas', []):
            faixas = [(1,8), (9,16), (17,25)]
            contagem = contar_por_faixa(jogo, faixas)
            for i, (min_q, max_q) in enumerate(config_filtros['faixas']):
                if not (min_q <= contagem[i] <= max_q):
                    return False
        if config_filtros.get('consecutivos_max', 0) > 0:
            if contar_consecutivos(jogo) > config_filtros['consecutivos_max']:
                return False
        if config_filtros.get('linhas_min_max', []):
            linhas = distribuir_por_linhas(jogo)
            for i, (min_q, max_q) in enumerate(config_filtros['linhas_min_max']):
                if not (min_q <= linhas[i] <= max_q):
                    return False
        if config_filtros.get('colunas_min_max', []):
            colunas = distribuir_por_colunas(jogo)
            for i, (min_q, max_q) in enumerate(config_filtros['colunas_min_max']):
                if not (min_q <= colunas[i] <= max_q):
                    return False
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
        return sorted(random.sample(range(1,26), 15))

    def gerar_multiplos_jogos(self, quantidade, config_filtros, max_tentativas_por_jogo=2000):
        jogos = []
        tentativas_totais = 0
        progress_bar = st.progress(0, text="Gerando jogos...")
        while len(jogos) < quantidade and tentativas_totais < quantidade * max_tentativas_por_jogo:
            jogo = self.gerar_jogo(config_filtros, max_tentativas=max_tentativas_por_jogo)
            if jogo and jogo not in jogos:
                jogos.append(jogo)
            tentativas_totais += 1
            progress_bar.progress(min(len(jogos)/quantidade, 1.0), text=f"Gerados {len(jogos)}/{quantidade} jogos")
        progress_bar.empty()
        if len(jogos) < quantidade:
            st.warning(f"Apenas {len(jogos)} jogos gerados em {tentativas_totais} tentativas.")
        return jogos

# =====================================================
# CONFERIDOR INTELIGENTE
# =====================================================

def parse_dezenas(dezenas_str):
    if isinstance(dezenas_str, str):
        return set(map(int, dezenas_str.replace('"', '').replace(' ', '').split(',')))
    elif isinstance(dezenas_str, list):
        return set(dezenas_str)
    else:
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

def analisar_frequencia_jogos(jogos):
    todas = []
    
    for jogo in jogos:
        if isinstance(jogo, str):
            dezenas = parse_dezenas(jogo)
        else:
            dezenas = set(jogo)
        todas.extend(dezenas)
    
    freq = Counter(todas)
    
    df_freq = pd.DataFrame({
        "Número": list(freq.keys()),
        "Frequência": list(freq.values())
    }).sort_values(by="Frequência", ascending=False).reset_index(drop=True)
    
    df_freq["%"] = (df_freq["Frequência"] / len(jogos) * 100).round(1)
    
    return df_freq

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================
def main():
    # Inicialização de estados da sessão
    if "analise" not in st.session_state: st.session_state.analise = None
    if "jogos" not in st.session_state: st.session_state.jogos = []
    if "dados_api" not in st.session_state: st.session_state.dados_api = None
    if "jogos_salvos" not in st.session_state: st.session_state.jogos_salvos = []
    if "historico_df" not in st.session_state: st.session_state.historico_df = None
    if "baseline_cache" not in st.session_state: st.session_state.baseline_cache = None
    if "mc_resultados" not in st.session_state: st.session_state.mc_resultados = None
    if "motor_geometria" not in st.session_state: st.session_state.motor_geometria = None
    if "gerador_principal" not in st.session_state: st.session_state.gerador_principal = None
    if "jogos_gerados" not in st.session_state: st.session_state.jogos_gerados = None
    if "scores" not in st.session_state: st.session_state.scores = []
    if "config_filtros" not in st.session_state:
        st.session_state.config_filtros = {
            'pares_min': 6, 'pares_max': 9,
            'soma_min': 180, 'soma_max': 210,
            'faixas': [(5,6), (5,6), (3,4)],
            'consecutivos_max': 5,
            'linhas_min_max': [(2,4)]*5,
            'colunas_min_max': [(2,4)]*5,
            'repetidas_min': 7, 'repetidas_max': 10
        }

    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Qtd concursos históricos", 20, 500, 100)
        if st.button("📥 Carregar concursos", use_container_width=True):
            with st.spinner("Carregando dados da Caixa..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    response = requests.get(url)
                    st.session_state.dados_api = response.json()
                    concursos = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
                    st.session_state.historico_df = criar_historico_df(st.session_state.dados_api, qtd)
                    st.session_state.baseline_cache = baseline_aleatorio()
                    st.session_state.motor_geometria = MotorGeometria(concursos)
                    st.session_state.gerador_principal = GeradorLotofacil(concursos, concursos[0])
                    st.success(f"✅ Último concurso: #{st.session_state.dados_api[0]['concurso']} - {st.session_state.dados_api[0]['data']}")
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    if not st.session_state.dados_api:
        st.info("👈 Carregue os concursos na barra lateral para começar.")
        return

    # ================= INTERFACE PRINCIPAL =================
    st.subheader("🎯 EMS 8.0 - ILP Professional (Otimização Combinatória Exata)")

    # Alerta sobre OR-Tools
    if not ORTOOLS_AVAILABLE:
        st.warning("""
        ⚠️ **OR-Tools não está instalado!**  
        Para usar o sistema ILP profissional, execute no terminal:  
        ```bash
        pip install ortools
        ```
        Enquanto isso, apenas os geradores tradicionais estarão disponíveis.
        """)
    
    # Abas reorganizadas
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Análise do Último Concurso",
        "🔥 ILP PROFESSIONAL",
        "🎯 Gerador Tradicional",
        "🔍 Conferência Inteligente",
        "📈 Avaliação Estatística",
        "📐 Geometria do Volante"
    ])

    # ================= TAB 1: ANÁLISE DO ÚLTIMO CONCURSO =================
    with tab1:
        ultimo = st.session_state.dados_api[0]
        numeros_ultimo = sorted(map(int, ultimo['dezenas']))
        st.markdown(f"""
        <div class='concurso-info'>
            <strong>Concurso #{ultimo['concurso']}</strong> - {ultimo['data']}
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Dezenas sorteadas:**")
            st.markdown(formatar_jogo_html(numeros_ultimo), unsafe_allow_html=True)
        with col2:
            pares = contar_pares(numeros_ultimo)
            st.metric("Pares/Ímpares", f"{pares}×{15-pares}")
        with col3:
            st.metric("Soma total", sum(numeros_ultimo))
        
        st.markdown("### 📊 Estatísticas do Último Concurso")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Primos", contar_primos(numeros_ultimo))
        with col2:
            st.metric("Consecutivos", contar_consecutivos(numeros_ultimo))
        with col3:
            baixas = sum(1 for n in numeros_ultimo if n <= 8)
            medias = sum(1 for n in numeros_ultimo if 9 <= n <= 16)
            altas = sum(1 for n in numeros_ultimo if n >= 17)
            st.metric("Distribuição (B/M/A)", f"{baixas}/{medias}/{altas}")
        with col4:
            linhas = distribuir_por_linhas(numeros_ultimo)
            st.metric("Linhas (0-4)", f"{linhas[0]}-{linhas[1]}-{linhas[2]}-{linhas[3]}-{linhas[4]}")

    # ================= TAB 2: ILP PROFESSIONAL =================
    with tab2:
        st.markdown("### 🔥 ILP PROFESSIONAL - Programação Linear Inteira")
        st.markdown("""
        <div class="ilp-highlight">
        <strong>🎯 O QUE É ILP (Programação Linear Inteira):</strong><br>
        • Transforma a Lotofácil em um <strong>problema de otimização combinatória exata</strong><br>
        • Usa um <strong>solver profissional (OR-Tools/SCIP)</strong> para encontrar a solução ótima<br>
        • Todas as restrições matemáticas são aplicadas como <strong>equações lineares</strong><br>
        • <strong>GARANTE</strong> que o jogo gerado é o MELHOR POSSÍVEL dentro das restrições!
        </div>
        """, unsafe_allow_html=True)
        
        # Configurações dos filtros
        with st.expander("⚙️ Configuração das Restrições ILP", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                pares_min = st.number_input("Mínimo de Pares", 0, 15, value=st.session_state.config_filtros['pares_min'], key="ilp_pares_min")
                pares_max = st.number_input("Máximo de Pares", 0, 15, value=st.session_state.config_filtros['pares_max'], key="ilp_pares_max")
                soma_min = st.number_input("Soma Mínima", 150, 300, value=st.session_state.config_filtros['soma_min'], key="ilp_soma_min")
                soma_max = st.number_input("Soma Máxima", 150, 300, value=st.session_state.config_filtros['soma_max'], key="ilp_soma_max")
                repetidas_min = st.number_input("Mínimo de Repetidas do Último", 0, 15, value=st.session_state.config_filtros['repetidas_min'], key="ilp_rep_min")
                repetidas_max = st.number_input("Máximo de Repetidas do Último", 0, 15, value=st.session_state.config_filtros['repetidas_max'], key="ilp_rep_max")
            with col2:
                consecutivos_max = st.number_input("Máximo de Consecutivos", 0, 10, value=st.session_state.config_filtros['consecutivos_max'], key="ilp_cons_max")
                linha_min = st.number_input("Mínimo por Linha", 0, 5, value=2, key="ilp_linha_min")
                linha_max = st.number_input("Máximo por Linha", 0, 5, value=4, key="ilp_linha_max")
                coluna_min = st.number_input("Mínimo por Coluna", 0, 5, value=2, key="ilp_coluna_min")
                coluna_max = st.number_input("Máximo por Coluna", 0, 5, value=4, key="ilp_coluna_max")
            
            # Atualiza configurações
            st.session_state.config_filtros.update({
                'pares_min': pares_min, 'pares_max': pares_max,
                'soma_min': soma_min, 'soma_max': soma_max,
                'repetidas_min': repetidas_min, 'repetidas_max': repetidas_max,
                'consecutivos_max': consecutivos_max,
                'linhas_min_max': [(linha_min, linha_max)]*5,
                'colunas_min_max': [(coluna_min, coluna_max)]*5
            })
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_jogos_ilp = st.slider("Quantidade de jogos", 1, 20, 5, key="qtd_ilp")
        with col2:
            timeout = st.slider("Timeout por jogo (segundos)", 2, 30, 10, key="timeout_ilp")
        
        if st.button("🚀 GERAR JOGO ÓTIMO VIA ILP", use_container_width=True, type="primary"):
            if not ORTOOLS_AVAILABLE:
                st.error("OR-Tools não disponível. Instale com: pip install ortools")
            else:
                ultimo_concurso_set = set(st.session_state.dados_api[0]['dezenas'])
                
                # Gera um único jogo ótimo
                pesos = calcular_pesos_inteligentes(
                    st.session_state.gerador_principal,
                    ultimo_concurso_set,
                    usar_frequencia=True,
                    usar_atraso=True,
                    usar_ultimo=True
                )
                
                with st.spinner("Resolvendo problema de otimização combinatória..."):
                    jogo, status = gerar_jogo_ilp_profissional(
                        pesos,
                        ultimo_concurso_set,
                        st.session_state.config_filtros,
                        solver_timeout=timeout
                    )
                    
                    if jogo:
                        st.session_state.jogos_gerados = [jogo]
                        # Calcula EV e probabilidades
                        mc = monte_carlo_jogo(tuple(jogo), 3000)
                        st.session_state.scores = [mc['P>=13'] * 100]
                        
                        st.success(f"✅ Jogo ótimo encontrado!")
                        
                        st.markdown("### 🏆 Jogo Otimizado pelo Solver ILP")
                        st.markdown(f"""
                        <div class="pro-highlight">
                        <strong>🎲 Jogo Gerado:</strong> {formatar_jogo_html(jogo)}<br>
                        <strong>📊 P(13+):</strong> {mc['P>=13']*100:.2f}%<br>
                        <strong>📊 P(14+):</strong> {mc['P>=14']*100:.2f}%<br>
                        <strong>🔧 Status Solver:</strong> {status}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Mostra restrições atendidas
                        st.markdown("### ✅ Restrições Atendidas")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Pares", f"{contar_pares(jogo)} (limite: {pares_min}-{pares_max})")
                            st.metric("Repetidas", f"{len(set(jogo) & ultimo_concurso_set)} (limite: {repetidas_min}-{repetidas_max})")
                        with col2:
                            st.metric("Soma", f"{sum(jogo)} (limite: {soma_min}-{soma_max})")
                            st.metric("Consecutivos", f"{contar_consecutivos(jogo)} (max: {consecutivos_max})")
                        with col3:
                            linhas = distribuir_por_linhas(jogo)
                            st.metric("Linhas", f"{min(linhas)}-{max(linhas)} (limite: {linha_min}-{linha_max})")
                            colunas = distribuir_por_colunas(jogo)
                            st.metric("Colunas", f"{min(colunas)}-{max(colunas)} (limite: {coluna_min}-{coluna_max})")
                    else:
                        st.error(f"Falha ao encontrar solução: {status}")
        
        # Gerar múltiplos jogos com diversidade
        if st.button("🎲 GERAR MÚLTIPLOS JOGOS ILP", use_container_width=True):
            if not ORTOOLS_AVAILABLE:
                st.error("OR-Tools não disponível.")
            else:
                ultimo_concurso_set = set(st.session_state.dados_api[0]['dezenas'])
                
                jogos = gerar_multiplos_jogos_ilp(
                    st.session_state.gerador_principal,
                    ultimo_concurso_set,
                    st.session_state.config_filtros,
                    qtd_jogos=qtd_jogos_ilp,
                    timeout_por_jogo=timeout,
                    usar_diversidade=True
                )
                
                if jogos:
                    st.session_state.jogos_gerados = jogos
                    st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)['P>=13'] * 100 for j in jogos]
                    st.success(f"✅ {len(jogos)} jogos gerados via ILP!")
        
        # Botão para salvar
        if st.session_state.jogos_gerados and st.button("💾 Salvar Jogos ILP", use_container_width=True):
            ultimo = st.session_state.dados_api[0]
            arquivo, jogo_id = salvar_jogos_gerados(
                st.session_state.jogos_gerados, 
                [], 
                {"versao": "EMS 8.0 ILP", "config": st.session_state.config_filtros}, 
                ultimo['concurso'], 
                ultimo['data']
            )
            if arquivo:
                st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                st.session_state.jogos_salvos = carregar_jogos_salvos()
        
        # Exibir jogos gerados
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown(f"### 📋 {len(st.session_state.jogos_gerados)} Jogos Gerados")
            
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                prob_13 = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🔹"
                nums_html = formatar_jogo_html(jogo)
                
                st.markdown(f"""
                <div style='border-left: 5px solid #00ffaa; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — P(13+): {prob_13:.2f}%<br>
                    {nums_html}
                </div>
                """, unsafe_allow_html=True)
            
            if len(st.session_state.jogos_gerados) > 20:
                st.info(f"Exibindo os primeiros 20 de {len(st.session_state.jogos_gerados)} jogos.")
            
            # Exportar CSV
            df_export = pd.DataFrame({
                "Jogo": range(1, len(st.session_state.jogos_gerados)+1),
                "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in st.session_state.jogos_gerados],
                "P_13+_%": [round(p, 2) for p in st.session_state.scores]
            })
            st.download_button(
                label="📥 Exportar CSV", 
                data=df_export.to_csv(index=False), 
                file_name=f"ilp_jogos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                mime="text/csv", 
                use_container_width=True
            )

    # ================= TAB 3: GERADOR TRADICIONAL =================
    with tab3:
        st.markdown("### 🎲 Gerador Tradicional (Pool Ponderado)")
        
        with st.expander("⚙️ Configuração dos Filtros", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                pares_min_trad = st.number_input("Mínimo de Pares", 0, 15, value=st.session_state.config_filtros['pares_min'], key="trad_pares_min")
                pares_max_trad = st.number_input("Máximo de Pares", 0, 15, value=st.session_state.config_filtros['pares_max'], key="trad_pares_max")
                soma_min_trad = st.number_input("Soma Mínima", 150, 300, value=st.session_state.config_filtros['soma_min'], key="trad_soma_min")
                soma_max_trad = st.number_input("Soma Máxima", 150, 300, value=st.session_state.config_filtros['soma_max'], key="trad_soma_max")
                repetidas_min_trad = st.number_input("Mínimo de Repetidas", 0, 15, value=st.session_state.config_filtros['repetidas_min'], key="trad_rep_min")
                repetidas_max_trad = st.number_input("Máximo de Repetidas", 0, 15, value=st.session_state.config_filtros['repetidas_max'], key="trad_rep_max")
            with col2:
                b_min = st.number_input("Mínimo Baixas (1-8)", 0, 15, value=st.session_state.config_filtros['faixas'][0][0], key="trad_b_min")
                b_max = st.number_input("Máximo Baixas (1-8)", 0, 15, value=st.session_state.config_filtros['faixas'][0][1], key="trad_b_max")
                m_min = st.number_input("Mínimo Médias (9-16)", 0, 15, value=st.session_state.config_filtros['faixas'][1][0], key="trad_m_min")
                m_max = st.number_input("Máximo Médias (9-16)", 0, 15, value=st.session_state.config_filtros['faixas'][1][1], key="trad_m_max")
                a_min = st.number_input("Mínimo Altas (17-25)", 0, 15, value=st.session_state.config_filtros['faixas'][2][0], key="trad_a_min")
                a_max = st.number_input("Máximo Altas (17-25)", 0, 15, value=st.session_state.config_filtros['faixas'][2][1], key="trad_a_max")
            
            config_trad = {
                'pares_min': pares_min_trad, 'pares_max': pares_max_trad,
                'soma_min': soma_min_trad, 'soma_max': soma_max_trad,
                'repetidas_min': repetidas_min_trad, 'repetidas_max': repetidas_max_trad,
                'faixas': [(b_min, b_max), (m_min, m_max), (a_min, a_max)],
                'consecutivos_max': st.session_state.config_filtros['consecutivos_max'],
                'linhas_min_max': st.session_state.config_filtros['linhas_min_max'],
                'colunas_min_max': st.session_state.config_filtros['colunas_min_max']
            }
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_jogos_trad = st.slider("Quantidade de jogos", 5, 50, 10, key="trad_qtd")
        
        with col2:
            if st.button("🎲 GERAR JOGOS TRADICIONAIS", use_container_width=True):
                with st.spinner(f"Gerando {qtd_jogos_trad} jogos..."):
                    jogos = st.session_state.gerador_principal.gerar_multiplos_jogos(qtd_jogos_trad, config_trad)
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)['P>=13'] * 100 for j in jogos]
                        st.success(f"✅ {len(jogos)} jogos gerados!")
        
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown(f"### 📋 {len(st.session_state.jogos_gerados)} Jogos Gerados")
            
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                prob_13 = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🔹"
                nums_html = formatar_jogo_html(jogo)
                
                st.markdown(f"""
                <div style='border-left: 5px solid #4cc9f0; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — P(13+): {prob_13:.2f}%<br>
                    {nums_html}
                </div>
                """, unsafe_allow_html=True)
            
            if len(st.session_state.jogos_gerados) > 20:
                st.info(f"Exibindo os primeiros 20 de {len(st.session_state.jogos_gerados)} jogos.")
            
            if st.button("💾 Salvar Jogos", key="salvar_trad", use_container_width=True):
                ultimo = st.session_state.dados_api[0]
                arquivo, jogo_id = salvar_jogos_gerados(
                    st.session_state.jogos_gerados, 
                    [], 
                    {"versao": "Tradicional", "config": config_trad}, 
                    ultimo['concurso'], 
                    ultimo['data']
                )
                if arquivo:
                    st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                    st.session_state.jogos_salvos = carregar_jogos_salvos()

    # ================= TAB 4: CONFERÊNCIA INTELIGENTE =================
    with tab4:
        st.markdown("### 🔍 Conferência Inteligente de Jogos")
        
        concurso_resultado = st.selectbox(
            "Selecione o concurso para conferência",
            st.session_state.dados_api,
            format_func=lambda c: f"#{c['concurso']} - {c['data']}",
            key="conferencia_resultado"
        )
        
        if concurso_resultado:
            resultado_oficial = set(map(int, concurso_resultado["dezenas"]))
            st.markdown(f"""
            <div class="highlight">
            <strong>🎯 Resultado #{concurso_resultado['concurso']}:</strong><br>
            {formatar_jogo_html(sorted(resultado_oficial))}
            </div>
            """, unsafe_allow_html=True)
        
        opcao_jogos = st.radio(
            "Origem dos jogos:",
            ["Jogos gerados na sessão atual", "Carregar de arquivo CSV", "Digitar manualmente"],
            horizontal=True
        )
        
        jogos_para_conferir = []
        
        if opcao_jogos == "Jogos gerados na sessão atual":
            if st.session_state.jogos_gerados:
                jogos_para_conferir = st.session_state.jogos_gerados
                st.info(f"{len(jogos_para_conferir)} jogos carregados da sessão atual")
            else:
                st.warning("Nenhum jogo gerado na sessão atual.")
        
        elif opcao_jogos == "Carregar de arquivo CSV":
            uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
            if uploaded_file:
                df_carregado = pd.read_csv(uploaded_file)
                if "Dezenas" in df_carregado.columns:
                    jogos_para_conferir = df_carregado["Dezenas"].tolist()
                    st.success(f"{len(jogos_para_conferir)} jogos carregados")
        
        else:
            jogos_texto = st.text_area(
                "Digite os jogos (um por linha, números separados por vírgula)",
                placeholder="Exemplo:\n1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"
            )
            if jogos_texto:
                for linha in jogos_texto.strip().split('\n'):
                    if linha.strip():
                        try:
                            dezenas = [int(n.strip()) for n in linha.split(',')]
                            if len(dezenas) == 15 and all(1 <= n <= 25 for n in dezenas):
                                jogos_para_conferir.append(sorted(dezenas))
                        except:
                            pass
                if jogos_para_conferir:
                    st.success(f"{len(jogos_para_conferir)} jogos carregados")
        
        if jogos_para_conferir and concurso_resultado:
            if st.button("🔍 CONFERIR JOGOS", use_container_width=True, type="primary"):
                with st.spinner("Conferindo jogos..."):
                    df_conferencia = conferir_jogos_inteligente(jogos_para_conferir, resultado_oficial)
                    
                    st.markdown("### 📊 Resultados da Conferência")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Jogos", len(df_conferencia))
                    with col2:
                        st.metric("Melhor Acerto", df_conferencia.iloc[0]["Acertos"])
                    with col3:
                        st.metric("Média Acertos", round(df_conferencia["Acertos"].mean(), 1))
                    with col4:
                        st.metric("Jogos com 13+", len(df_conferencia[df_conferencia["Acertos"] >= 13]))
                    
                    for i, row in df_conferencia.head(20).iterrows():
                        medalha = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                        st.markdown(f"""
                        <div style='border-left: 5px solid {"#ffd700" if i == 0 else "#c0c0c0" if i == 1 else "#cd7f32" if i == 2 else "#4cc9f0"}; 
                                    background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>
                            {medalha} <strong>Jogo {row['Jogo']}</strong> — <span style='color:#00ffaa; font-weight:bold;'>{row['Acertos']} acertos</span><br>
                            {formatar_jogo_html(row['Dezenas'])}<br>
                            <small style='color:#aaa;'>Acertou: {", ".join(f"{n:02d}" for n in row['Acertos_Dezenas'])}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    if len(df_conferencia) > 20:
                        st.info(f"Exibindo os primeiros 20 de {len(df_conferencia)} jogos")

    # ================= TAB 5: AVALIAÇÃO ESTATÍSTICA =================
    with tab5:
        st.markdown("### 📈 Avaliação Estatística dos Jogos")
        baseline = st.session_state.baseline_cache
        st.markdown(f"**Baseline Aleatório:** Média = {baseline['media']:.3f}, Desvio = {baseline['std']:.3f}")
        
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown("### 🎲 Simulação Monte Carlo")
            n_sim = st.slider("Simulações por jogo", 1000, 50000, 10000, key="mc_sim")
            if st.button("Executar Monte Carlo"):
                with st.spinner(f"Simulando {n_sim} sorteios..."):
                    mc_res = []
                    for i, jogo in enumerate(st.session_state.jogos_gerados[:10]):
                        res = monte_carlo_jogo(tuple(jogo), n_sim)
                        mc_res.append({
                            "Jogo": i+1, 
                            "P(≥11)": f"{res['P>=11']*100:.2f}%", 
                            "P(≥12)": f"{res['P>=12']*100:.2f}%", 
                            "P(≥13)": f"{res['P>=13']*100:.2f}%", 
                            "P(≥14)": f"{res['P>=14']*100:.2f}%",
                            "Média": round(res['media'], 2)
                        })
                    st.session_state.mc_resultados = pd.DataFrame(mc_res)
            if st.session_state.mc_resultados is not None:
                st.dataframe(st.session_state.mc_resultados, use_container_width=True, hide_index=True)

    # ================= TAB 6: GEOMETRIA DO VOLANTE =================
    with tab6:
        st.markdown("### 📐 Geometria Analítica do Volante 5x5")
        motor_geo = st.session_state.motor_geometria
        stats_geo = motor_geo.get_estatisticas_geometricas()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Centroide Médio Histórico", f"({stats_geo['centroide_medio'][0]}, {stats_geo['centroide_medio'][1]})")
        with col2:
            st.metric("Dispersão Média Histórica", stats_geo['dispersao_media'])
        
        st.markdown("### 🔗 Pares Fortes (Co-ocorrência)")
        num_consulta = st.number_input("Número base", 1, 25, 13)
        pares = motor_geo.get_pares_recomendados(num_consulta, 8)
        if pares:
            st.markdown(f"**Números mais relacionados ao {num_consulta:02d}:**")
            st.markdown(" ".join(f"<span style='border:1px solid #00ffaa; border-radius:15px; padding:3px 8px; margin:2px;'>{p[0]:02d} ({p[1]})</span>" for p in pares), unsafe_allow_html=True)

if __name__ == "__main__":
    main()

st.markdown("""
<style>
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#00ffaa,#00aaff,#00ffaa);box-shadow:0 0 10px #00ffaa;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(0,255,170,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
<div class="footer-premium"><div class="footer-title">EMS 8.0 - ILP PROFESSIONAL SOLVER</div><div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div></div>
""", unsafe_allow_html=True)
