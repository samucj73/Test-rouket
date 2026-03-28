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
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL - Análise e Geração",
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
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 LOTOFÁCIL - Análise e Geração")
st.caption("Análise Estatística e Geração de Jogos com Filtros Matemáticos")

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
    """faixa_limites: lista de tuplas (inicio, fim)"""
    contagem = []
    for inicio, fim in faixa_limites:
        contagem.append(sum(1 for n in jogo if inicio <= n <= fim))
    return contagem

def distribuir_por_linhas(jogo):
    """Conta quantos números em cada linha do volante 5x5"""
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
    """Baseline: interseção de dois conjuntos aleatórios de 15 números em 25"""
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
# NOVO SCORE BASEADO EM MONTE CARLO (MELHORIA 1)
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

def score_jogo_real(jogo, n_sim=2000):
    """
    Score baseado na probabilidade real de acertos altos via Monte Carlo.
    Este é o substituto para score_jogo_ems, que era estético.
    """
    jogo_set = set(jogo)
    acertos = []

    for _ in range(n_sim):
        sorteio = set(random.sample(range(1, 26), 15))
        acertos.append(len(jogo_set & sorteio))

    acertos = np.array(acertos)

    # Foco em alta performance (não média)
    score = (
        np.mean(acertos >= 11) * 1 +
        np.mean(acertos >= 12) * 3 +
        np.mean(acertos >= 13) * 8 +
        np.mean(acertos >= 14) * 20
    )

    return score


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
# EMS 3.0 - GENÉTICO + FECHAMENTO (ATUALIZADO)
# =====================================================

# --- MELHORIA 4: Função para forçar diversidade ---
def distancia_jogos(j1, j2):
    """Calcula a distância (número de elementos diferentes) entre dois jogos."""
    return len(set(j1) ^ set(j2))

def crossover(j1, j2):
    """Operador de crossover entre dois jogos"""
    corte = random.randint(5, 10)
    filho = list(set(j1[:corte] + j2[corte:]))

    while len(filho) < 15:
        n = random.randint(1, 25)
        if n not in filho:
            filho.append(n)

    return sorted(filho[:15])


def mutacao(jogo, taxa=0.2):
    """Operador de mutação com taxa configurável"""
    jogo = jogo.copy()
    if random.random() < taxa:
        idx = random.randint(0, 14)
        novo = random.randint(1, 25)
        while novo in jogo:
            novo = random.randint(1, 25)
        jogo[idx] = novo
    return sorted(jogo)


# --- MELHORIA 2: Algoritmo Genético atualizado para usar score_jogo_real ---
def algoritmo_genetico_ems(
    gerador,
    motor_geo, # Mantido para compatibilidade, mas não usado no novo score
    ultimo,    # Mantido para compatibilidade, mas não usado no novo score
    config_filtros,
    populacao_size=80,
    geracoes=25
):
    """Algoritmo genético evoluindo jogos com base no score real (Monte Carlo)"""
    
    populacao = gerador.gerar_multiplos_jogos(populacao_size, config_filtros)

    for _ in range(geracoes):
        
        # Avalia usando o novo score real
        avaliados = [
            (j, score_jogo_real(j, n_sim=1500)) # Usa 1500 simulações para equilibrar velocidade e precisão
            for j in populacao
        ]
        
        avaliados.sort(key=lambda x: x[1], reverse=True)
        sobreviventes = [j for j, _ in avaliados[:int(populacao_size * 0.3)]]
        
        nova_pop = sobreviventes.copy()
        
        while len(nova_pop) < populacao_size:
            p1, p2 = random.sample(sobreviventes, 2)
            filho = mutacao(crossover(p1, p2))
            
            # Aplica os filtros tradicionais
            if gerador.aplicar_filtros(filho, config_filtros):
                # --- MELHORIA 4: Garantir diversidade na nova população ---
                if all(distancia_jogos(filho, j) > 6 for j in nova_pop):
                    nova_pop.append(filho)
                # Se não houver diversidade suficiente, tenta novamente (loop irá continuar)
        
        populacao = nova_pop
    
    final = [
        (j, score_jogo_real(j, n_sim=1500))
        for j in populacao
    ]
    
    final.sort(key=lambda x: x[1], reverse=True)
    return final[:20]


# ================= FECHAMENTO INTELIGENTE =================

def gerar_pool_inteligente(gerador, tamanho=20):
    """Gera um pool de números baseado em frequência e atraso"""
    numeros, pesos = gerador.pool_ponderado
    escolhidos = set()
    
    while len(escolhidos) < tamanho:
        n = random.choices(numeros, weights=pesos, k=1)[0]
        escolhidos.add(n)
    
    return sorted(escolhidos)


def gerar_fechamento(pool, qtd_jogos=15):
    """Gera fechamento inteligente com cobertura de combinações de 14 números"""
    jogos = []
    cobertura = set()
    
    while len(jogos) < qtd_jogos:
        melhor_jogo = None
        melhor_score = -1
        
        for _ in range(200):
            jogo = sorted(random.sample(pool, 15))
            
            cobertos = 0
            for comb in combinations(jogo, 14):
                if comb not in cobertura:
                    cobertos += 1
            
            if cobertos > melhor_score:
                melhor_score = cobertos
                melhor_jogo = jogo
        
        jogos.append(melhor_jogo)
        
        for comb in combinations(melhor_jogo, 14):
            cobertura.add(comb)
    
    return jogos


def fechamento_inteligente_ems(
    gerador,
    dist_emp, # Mantido para compatibilidade
    motor_geo,
    ultimo,
    config_filtros,
    qtd_jogos=15
):
    """Sistema completo de fechamento inteligente com pool otimizado"""
    
    pool = gerar_pool_inteligente(gerador, 20)
    
    jogos_base = gerar_fechamento(pool, qtd_jogos * 2)
    
    avaliados = []
    
    for j in jogos_base:
        if gerador.aplicar_filtros(j, config_filtros):
            # Usa o novo score real
            score = score_jogo_real(j, n_sim=1500)
            avaliados.append((j, score))
    
    avaliados.sort(key=lambda x: x[1], reverse=True)
    
    return avaliados[:qtd_jogos], pool


# =====================================================
# EMS 5.0 - ENGENHARIA COMBINATÓRIA FORMAL
# =====================================================

def gerar_pool_cirurgico_balanceado(gerador=None, tamanho=20):
    """
    Gera pool cirúrgico com balanceamento matemático:
    - Distribuição equilibrada no volante 5x5
    - Balanceamento par/ímpar (10/10)
    - Evita clusters
    - Cobertura de todas colunas e linhas
    """
    
    if gerador:
        numeros, pesos = gerador.pool_ponderado
        # Seleciona baseado em pesos, mas garante balanceamento
        candidatos = list(range(1, 26))
        escolhidos = set()
        
        # Primeiro, garante cobertura de todas linhas e colunas
        linhas_necessarias = 4  # mínimo por linha
        colunas_necessarias = 4  # mínimo por coluna
        
        # Seleciona números estratégicos
        for linha in range(5):
            for coluna in range(5):
                num = linha * 5 + coluna + 1
                if len(escolhidos) < tamanho:
                    if random.random() < 0.3:  # 30% de chance de incluir
                        escolhidos.add(num)
        
        # Completa com pesos
        while len(escolhidos) < tamanho:
            n = random.choices(numeros, weights=pesos, k=1)[0]
            escolhidos.add(n)
        
        pool = sorted(escolhidos)
    else:
        # Fallback: seleção aleatória balanceada
        pool = []
        pares = [n for n in range(1, 26) if n % 2 == 0]
        impares = [n for n in range(1, 26) if n % 2 != 0]
        
        # Balanceamento 10/10
        pool.extend(random.sample(pares, tamanho // 2))
        pool.extend(random.sample(impares, tamanho - tamanho // 2))
        pool.sort()
    
    # Verifica balanceamento
    stats = {
        "pares": len([n for n in pool if n % 2 == 0]),
        "impares": len([n for n in pool if n % 2 != 0]),
        "linhas": [len([n for n in pool if (n-1)//5 == i]) for i in range(5)],
        "colunas": [len([n for n in pool if (n-1)%5 == i]) for i in range(5)]
    }
    
    return pool, stats


def gerar_base_estrategica(pool, tamanho_base=15):
    """Gera base inicial estratégica dentro do pool"""
    base = set(random.sample(pool, tamanho_base))
    return sorted(base)


def gerar_vizinhos_combinatorios(base, pool):
    """
    Gera vizinhos por trocas controladas:
    - Remove 1 número
    - Adiciona 1 número do pool
    """
    jogos = []
    base_set = set(base)
    
    for out in base:
        for new in pool:
            if new not in base_set:
                novo = base_set.copy()
                novo.remove(out)
                novo.add(new)
                jogos.append(sorted(novo))
    
    return jogos


def calcular_cobertura(jogo, cobertura_set):
    """Calcula quantas novas combinações de 14 um jogo cobre"""
    ganho = 0
    for comb in combinations(jogo, 14):
        if comb not in cobertura_set:
            ganho += 1
    return ganho


def fechamento_v5_avancado(pool, limite_jogos=30, usar_pesos=False, gerador=None):
    """
    EMS 5.0: Engenharia combinatória formal com cobertura otimizada
    
    Args:
        pool: lista de números (20 números)
        limite_jogos: número máximo de jogos a gerar
        usar_pesos: se True, usa pesos do gerador para ordenar
        gerador: instância do GeradorLotofacil para pesos
    
    Returns:
        jogos_finais: lista de jogos otimizados
        cobertura_stats: estatísticas de cobertura
    """
    
    # Gera base inicial
    base = gerar_base_estrategica(pool)
    
    # Gera todos os vizinhos possíveis
    candidatos = gerar_vizinhos_combinatorios(base, pool)
    
    # Se usar pesos, ordena candidatos por score
    if usar_pesos and gerador:
        numeros, pesos = gerador.pool_ponderado
        peso_dict = {num: peso for num, peso in zip(numeros, pesos)}
        
        def calcular_peso_total(jogo):
            return sum(peso_dict.get(n, 0) for n in jogo)
        
        candidatos.sort(key=calcular_peso_total, reverse=True)
    else:
        random.shuffle(candidatos)
    
    # Matriz de cobertura
    cobertura = set()
    jogos_finais = []
    
    progress_bar = st.progress(0, text="Construindo cobertura combinatória...")
    
    while len(jogos_finais) < limite_jogos and candidatos:
        melhor_jogo = None
        melhor_ganho = -1
        
        # Avalia melhores candidatos
        for jogo in candidatos[:min(500, len(candidatos))]:
            ganho = calcular_cobertura(jogo, cobertura)
            if ganho > melhor_ganho:
                melhor_ganho = ganho
                melhor_jogo = jogo
        
        if melhor_jogo is None:
            break
        
        jogos_finais.append(melhor_jogo)
        
        # Atualiza cobertura
        for comb in combinations(melhor_jogo, 14):
            cobertura.add(comb)
        
        # Remove jogo usado
        if melhor_jogo in candidatos:
            candidatos.remove(melhor_jogo)
        
        progress_bar.progress(min(len(jogos_finais)/limite_jogos, 1.0), 
                            text=f"Cobertura: {len(cobertura)} combinações de 14")
    
    progress_bar.empty()
    
    # Estatísticas de cobertura
    total_combinacoes = len(list(combinations(pool, 14)))
    cobertura_stats = {
        "combinacoes_14_cobertas": len(cobertura),
        "total_combinacoes_possiveis": total_combinacoes,
        "percentual_cobertura": (len(cobertura) / total_combinacoes * 100) if total_combinacoes > 0 else 0,
        "jogos_gerados": len(jogos_finais),
        "pool_utilizado": pool
    }
    
    return jogos_finais, cobertura_stats


def multi_pool_fechamento(gerador, num_pools=3, jogos_por_pool=15):
    """
    Estratégia multi-pool: gera múltiplos pools e seus fechamentos
    Aumenta drasticamente a cobertura global
    """
    todos_jogos = []
    todos_pools = []
    
    for i in range(num_pools):
        with st.spinner(f"Gerando Pool {i+1}/{num_pools}..."):
            # Gera pool cirúrgico
            pool, pool_stats = gerar_pool_cirurgico_balanceado(gerador, 20)
            
            # Gera fechamento para este pool
            jogos, cobertura_stats = fechamento_v5_avancado(
                pool, 
                limite_jogos=jogos_por_pool,
                usar_pesos=True,
                gerador=gerador
            )
            
            todos_jogos.extend(jogos)
            todos_pools.append({
                "pool": pool,
                "stats": pool_stats,
                "cobertura": cobertura_stats,
                "jogos": jogos
            })
    
    # Remove duplicatas
    jogos_unicos = []
    for j in todos_jogos:
        if j not in jogos_unicos:
            jogos_unicos.append(j)
    
    return jogos_unicos, todos_pools


# =====================================================
# CONFERIDOR INTELIGENTE + OTIMIZADOR
# =====================================================

def parse_dezenas(dezenas_str):
    """Converte string de dezenas para set de inteiros"""
    if isinstance(dezenas_str, str):
        return set(map(int, dezenas_str.replace('"', '').replace(' ', '').split(',')))
    elif isinstance(dezenas_str, list):
        return set(dezenas_str)
    else:
        return set()


def conferir_jogos_inteligente(jogos, resultado_set):
    """
    Confere jogos contra um resultado oficial
    
    Args:
        jogos: lista de jogos (cada jogo pode ser lista ou string)
        resultado_set: set com os números sorteados
    
    Returns:
        DataFrame com resultados ordenados por acertos
    """
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
    """
    Analisa a frequência dos números em um conjunto de jogos
    
    Args:
        jogos: lista de jogos
    
    Returns:
        DataFrame com frequência ordenada
    """
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


def gerar_jogos_otimizados(base_jogos, resultado_set, n_jogos=10, estrategia="inteligente"):
    """
    Gera jogos otimizados baseado nos jogos existentes e resultado
    
    Args:
        base_jogos: lista de jogos base
        resultado_set: set com números do último concurso
        n_jogos: quantidade de jogos a gerar
        estrategia: "inteligente", "frequencia", "hibrido"
    
    Returns:
        lista de jogos otimizados
    """
    todos_numeros = set(range(1, 26))
    jogos_novos = []
    
    # Analisa frequência dos jogos base
    freq = analisar_frequencia_jogos(base_jogos)
    numeros_frequentes = set(freq.head(10)["Número"].tolist())
    numeros_raros = set(freq.tail(10)["Número"].tolist())
    
    for _ in range(n_jogos):
        if estrategia == "inteligente":
            # Pega um jogo base aleatório
            jogo_base = base_jogos[random.randint(0, len(base_jogos) - 1)]
            if isinstance(jogo_base, str):
                base = parse_dezenas(jogo_base)
            else:
                base = set(jogo_base)
            
            # Remove 2-3 números para variar
            remover_qtd = random.randint(2, 3)
            remover = set(random.sample(list(base), min(remover_qtd, len(base))))
            base -= remover
            
            # Adiciona números do resultado (que são mais prováveis)
            if len(resultado_set) > 0:
                novos_do_resultado = list(resultado_set - base)
                if novos_do_resultado:
                    base.add(random.choice(novos_do_resultado))
            
            # Adiciona números frequentes se faltar
            if len(base) < 12:
                faltantes = numeros_frequentes - base
                if faltantes:
                    base.add(random.choice(list(faltantes)))
        
        elif estrategia == "frequencia":
            # Baseado puramente em frequência
            base = set()
            numeros_prioridade = list(numeros_frequentes) + list(resultado_set)
            while len(base) < 15 and numeros_prioridade:
                n = random.choice(numeros_prioridade)
                base.add(n)
                numeros_prioridade = [x for x in numeros_prioridade if x != n]
        
        else:  # híbrido
            base = set()
            # 50% números frequentes, 50% resultado
            metade = n_jogos // 2
            base.update(random.sample(list(numeros_frequentes), min(metade, len(numeros_frequentes))))
            base.update(random.sample(list(resultado_set), min(metade, len(resultado_set))))
        
        # Completa até 15 números
        while len(base) < 15:
            disponiveis = list(todos_numeros - base)
            if disponiveis:
                base.add(random.choice(disponiveis))
        
        jogos_novos.append(sorted(base))
    
    return jogos_novos


def analisar_padroes_avancados(jogos, resultado_set):
    """
    Análise avançada de padrões nos jogos
    
    Returns:
        dict com estatísticas detalhadas
    """
    todas_dezenas = []
    pares_total = []
    primos_total = []
    consecutivos_total = []
    somas_total = []
    
    for jogo in jogos:
        if isinstance(jogo, str):
            dezenas = parse_dezenas(jogo)
        else:
            dezenas = set(jogo)
        
        todas_dezenas.extend(dezenas)
        pares_total.append(contar_pares(list(dezenas)))
        primos_total.append(contar_primos(list(dezenas)))
        consecutivos_total.append(contar_consecutivos(list(dezenas)))
        somas_total.append(sum(dezenas))
    
    freq_total = Counter(todas_dezenas)
    
    # Identifica números que mais acertaram
    if resultado_set:
        acertos_por_numero = {}
        for jogo in jogos:
            if isinstance(jogo, str):
                dezenas = parse_dezenas(jogo)
            else:
                dezenas = set(jogo)
            for num in dezenas & resultado_set:
                acertos_por_numero[num] = acertos_por_numero.get(num, 0) + 1
    
    return {
        "frequencia_geral": dict(sorted(freq_total.items(), key=lambda x: x[1], reverse=True)[:15]),
        "media_pares": np.mean(pares_total),
        "media_primos": np.mean(primos_total),
        "media_consecutivos": np.mean(consecutivos_total),
        "media_soma": np.mean(somas_total),
        "std_soma": np.std(somas_total),
        "acertos_por_numero": acertos_por_numero if resultado_set else {},
        "total_jogos": len(jogos)
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
            # Quanto maior a frequência e o atraso, maior o peso
            peso = freq_norm * peso_freq + atraso_norm * peso_atraso
            # --- MELHORIA 3: REMOVER VÍCIO DO ÚLTIMO CONCURSO ---
            # Peso reduzido de 2.0 para 1.2 para não dominar
            if n in self.ultimo:
                peso *= 1.2
            numeros.append(n)
            pesos.append(peso)
        pesos = np.array(pesos)
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
        # Fallback: gerar aleatório
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
# BACKTESTING
# =====================================================
def backtest_estrategia(historico, config_filtros, num_testes=30):
    """Testa a estratégia de geração nos últimos 'num_testes' concursos históricos."""
    resultados = []
    for i in range(1, num_testes+1):
        # Usa os concursos anteriores ao concurso alvo para treino
        idx_alvo = -i
        if abs(idx_alvo) > len(historico):
            continue
        concurso_alvo = historico[idx_alvo]
        historico_treino = historico[:idx_alvo] if idx_alvo != 0 else []
        if not historico_treino:
            continue
        gerador_teste = GeradorLotofacil(historico_treino, historico_treino[0])
        # Gera alguns jogos e pega o melhor
        jogos_teste = gerador_teste.gerar_multiplos_jogos(5, config_filtros, max_tentativas_por_jogo=1000)
        melhor_acerto = 0
        for j in jogos_teste:
            acertos = len(set(j) & set(concurso_alvo))
            melhor_acerto = max(melhor_acerto, acertos)
        resultados.append(melhor_acerto)
    return np.mean(resultados) if resultados else 0

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
    if "cobertura_stats" not in st.session_state: st.session_state.cobertura_stats = None
    if "multi_pool_results" not in st.session_state: st.session_state.multi_pool_results = None
    # --- MELHORIA 5: QUEBRAR PADRÃO DE FILTROS (limites mais amplos) ---
    if "config_filtros" not in st.session_state:
        st.session_state.config_filtros = {
            'pares_min': 5, 'pares_max': 10, # Era 6-9, agora mais amplo
            'soma_min': 160, 'soma_max': 240, # Era 180-210, agora mais amplo
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
    st.subheader("🎯 Análise e Geração de Jogos")

    # Reorganização das abas
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Análise do Último Concurso",
        "🎲 Gerador de Jogos",
        "🚀 EMS 5.0 - Cobertura",
        "🔍 Conferência Inteligente",
        "📈 Avaliação Estatística",
        "📐 Geometria do Volante",
        "✅ Conferência Salvos"
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
        # Estatísticas básicas da última
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

    # ================= TAB 2: GERADOR DE JOGOS =================
    with tab2:
        st.markdown("### 🎲 Gerador de Jogos com Filtros Ajustáveis")
        st.caption("Base estatística: Frequência e atraso dos números, com pesos configuráveis.")
        
        with st.expander("⚙️ Configuração dos Filtros", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                # --- MELHORIA 5: Atualizando valores padrão nos inputs ---
                pares_min = st.number_input("Mínimo de Pares", 0, 15, value=st.session_state.config_filtros['pares_min'])
                pares_max = st.number_input("Máximo de Pares", 0, 15, value=st.session_state.config_filtros['pares_max'])
                soma_min = st.number_input("Soma Mínima", 150, 300, value=st.session_state.config_filtros['soma_min'])
                soma_max = st.number_input("Soma Máxima", 150, 300, value=st.session_state.config_filtros['soma_max'])
                repetidas_min = st.number_input("Mínimo de Repetidas do Último", 0, 15, value=st.session_state.config_filtros['repetidas_min'])
                repetidas_max = st.number_input("Máximo de Repetidas do Último", 0, 15, value=st.session_state.config_filtros['repetidas_max'])
            with col2:
                b_min = st.number_input("Mínimo Baixas (1-8)", 0, 15, value=st.session_state.config_filtros['faixas'][0][0])
                b_max = st.number_input("Máximo Baixas (1-8)", 0, 15, value=st.session_state.config_filtros['faixas'][0][1])
                m_min = st.number_input("Mínimo Médias (9-16)", 0, 15, value=st.session_state.config_filtros['faixas'][1][0])
                m_max = st.number_input("Máximo Médias (9-16)", 0, 15, value=st.session_state.config_filtros['faixas'][1][1])
                a_min = st.number_input("Mínimo Altas (17-25)", 0, 15, value=st.session_state.config_filtros['faixas'][2][0])
                a_max = st.number_input("Máximo Altas (17-25)", 0, 15, value=st.session_state.config_filtros['faixas'][2][1])
            st.session_state.config_filtros.update({
                'pares_min': pares_min, 'pares_max': pares_max,
                'soma_min': soma_min, 'soma_max': soma_max,
                'repetidas_min': repetidas_min, 'repetidas_max': repetidas_max,
                'faixas': [(b_min, b_max), (m_min, m_max), (a_min, a_max)]
            })

        col1, col2, col3 = st.columns(3)
        with col1:
            qtd_jogos = st.slider("Quantidade de jogos", 5, 50, 10)
        
        with col2:
            if st.button("🚀 GERAR JOGOS", use_container_width=True):
                with st.spinner(f"Gerando {qtd_jogos} jogos..."):
                    jogos = st.session_state.gerador_principal.gerar_multiplos_jogos(qtd_jogos, st.session_state.config_filtros)
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.session_state.scores = [score_jogo_real(j) for j in jogos]
                        st.success(f"✅ {len(jogos)} jogos gerados!")
        
        with col3:
            if st.button("🔥 EMS 3.0 (Probabilístico)", use_container_width=True):
                with st.spinner("Gerando jogos com Algoritmo Genético baseado em Monte Carlo..."):
                    # --- MELHORIA 2: Usando o novo score no genético ---
                    # O genético agora usa score_jogo_real e garante diversidade
                    resultados = algoritmo_genetico_ems(
                        st.session_state.gerador_principal,
                        st.session_state.motor_geometria, # Passado mas não usado no novo score
                        st.session_state.gerador_principal.ultimo,
                        st.session_state.config_filtros
                    )
                    
                    st.session_state.jogos_gerados = [r[0] for r in resultados]
                    st.session_state.scores = [r[1] for r in resultados]
                    st.success(f"✅ {len(resultados)} jogos gerados com EMS 3.0 (Probabilístico)!")

        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            jogos = st.session_state.jogos_gerados
            st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
            
            for i, jogo in enumerate(jogos[:20]):
                score = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🔹"
                nums_html = formatar_jogo_html(jogo)
                # Adicionando informação de probabilidade de 13+ baseada no score
                prob_13_plus = score / 20 # Aproximação, pois score máximo é 20 (1*1 + 1*3 + 1*8 + 1*20)
                stats = f"⚖️ {contar_pares(jogo)}p | ➕ {sum(jogo)} | 🔁 {len(set(jogo) & set(st.session_state.gerador_principal.ultimo))} rep"
                
                st.markdown(f"""
                <div style='border-left: 5px solid #4cc9f0; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — Score Prob.: {round(score,2)}<br>
                    {nums_html}<br>
                    <small style='color:#aaa;'>{stats}</small>
                </div>
                """, unsafe_allow_html=True)
            
            if len(jogos) > 20:
                st.info(f"Exibindo os primeiros 20 de {len(jogos)} jogos. Salve para ver todos.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Salvar Jogos", key="salvar_jogos", use_container_width=True):
                    ultimo = st.session_state.dados_api[0]
                    arquivo, jogo_id = salvar_jogos_gerados(jogos, [], {"filtros": st.session_state.config_filtros}, ultimo['concurso'], ultimo['data'])
                    if arquivo:
                        st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                        st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            with col2:
                df_export = pd.DataFrame({
                    "Jogo": range(1, len(jogos)+1),
                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                    "Score_Prob": [round(s, 2) for s in st.session_state.scores] if st.session_state.scores else [0]*len(jogos),
                    "Pares": [contar_pares(j) for j in jogos],
                    "Soma": [sum(j) for j in jogos],
                    "Repetidas": [len(set(j) & set(st.session_state.gerador_principal.ultimo)) for j in jogos]
                })
                st.download_button(label="📥 Exportar CSV", data=df_export.to_csv(index=False), 
                                 file_name=f"jogos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                                 mime="text/csv", use_container_width=True)

    # ================= TAB 3: EMS 5.0 - COBERTURA =================
    with tab3:
        st.markdown("### 🚀 EMS 5.0 - Engenharia Combinatória Formal")
        st.caption("Cobertura garantida de combinações de 14 números dentro do pool selecionado")
        
        st.markdown("""
        <div class="cover-stats">
        <strong>🎯 Conceito:</strong> Se os 15 números sorteados estiverem dentro do seu pool, 
        este sistema GARANTE cobertura de combinações de 14 números.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            tamanho_pool = st.selectbox("Tamanho do Pool", [18, 19, 20], index=2)
        with col2:
            qtd_jogos_v5 = st.slider("Jogos por pool", 10, 40, 25)
        with col3:
            num_pools = st.selectbox("Multi-Pool", [1, 2, 3, 4, 5], index=2, 
                                    help="Múltiplos pools aumentam a cobertura global")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎯 POOL CIRÚRGICO", use_container_width=True):
                with st.spinner("Gerando pool balanceado..."):
                    pool, stats = gerar_pool_cirurgico_balanceado(st.session_state.gerador_principal, tamanho_pool)
                    st.session_state.pool_atual = pool
                    st.session_state.pool_stats = stats
                    
                    st.markdown(f"**Pool Selecionado ({len(pool)} números):**")
                    st.markdown(" ".join(f"<span style='background:#0e1117; border:1px solid #00ffaa; border-radius:15px; padding:5px 10px; margin:2px; display:inline-block;'>{n:02d}</span>" for n in pool), unsafe_allow_html=True)
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Pares/Ímpares", f"{stats['pares']}/{stats['impares']}")
                    with col_b:
                        st.metric("Distribuição Linhas", f"{stats['linhas']}")
                    with col_c:
                        st.metric("Distribuição Colunas", f"{stats['colunas']}")
        
        with col2:
            if st.button("💣 FECHAMENTO V5", use_container_width=True, type="primary"):
                if "pool_atual" not in st.session_state:
                    st.warning("Gere um pool cirúrgico primeiro!")
                else:
                    with st.spinner("Construindo matriz de cobertura..."):
                        jogos, cobertura = fechamento_v5_avancado(
                            st.session_state.pool_atual,
                            limite_jogos=qtd_jogos_v5,
                            usar_pesos=True,
                            gerador=st.session_state.gerador_principal
                        )
                        
                        st.session_state.jogos_gerados = jogos
                        st.session_state.cobertura_stats = cobertura
                        st.session_state.scores = [score_jogo_real(j) for j in jogos]
                        
                        st.success(f"✅ {len(jogos)} jogos gerados!")
                        
                        st.markdown("### 📊 Estatísticas de Cobertura")
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Combinações de 14 cobertas", f"{cobertura['combinacoes_14_cobertas']:,}")
                        with col_b:
                            st.metric("Total combinações possíveis", f"{cobertura['total_combinacoes_possiveis']:,}")
                        with col_c:
                            st.metric("% Cobertura", f"{cobertura['percentual_cobertura']:.2f}%")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔁 MULTI-POOL (Recomendado)", use_container_width=True):
                # --- MELHORIA 6: Multi-pool já é usado, mas garantimos que a função está atualizada ---
                with st.spinner(f"Gerando {num_pools} pools com fechamento..."):
                    todos_jogos, pools_info = multi_pool_fechamento(
                        st.session_state.gerador_principal,
                        num_pools=num_pools,
                        jogos_por_pool=qtd_jogos_v5
                    )
                    
                    st.session_state.jogos_gerados = todos_jogos
                    st.session_state.multi_pool_results = pools_info
                    st.session_state.scores = [score_jogo_real(j) for j in todos_jogos]
                    
                    st.success(f"✅ {len(todos_jogos)} jogos únicos gerados com {num_pools} pools!")
                    
                    st.markdown("### 📊 Estatísticas Multi-Pool")
                    for i, pool_info in enumerate(pools_info):
                        with st.expander(f"Pool {i+1} - {len(pool_info['pool'])} números"):
                            st.markdown(f"**Pool:** {pool_info['pool']}")
                            st.markdown(f"**Cobertura:** {pool_info['cobertura']['percentual_cobertura']:.2f}%")
                            st.markdown(f"**Jogos:** {len(pool_info['jogos'])}")
        
        with col2:
            if st.button("📊 Calcular Probabilidade Real", use_container_width=True):
                if "pool_atual" in st.session_state:
                    pool = st.session_state.pool_atual
                    prob_pool_acertar = math.comb(len(pool), 15) / math.comb(25, 15)
                    prob_14_se_pool_acertar = st.session_state.cobertura_stats['percentual_cobertura'] / 100 if st.session_state.cobertura_stats else 0
                    
                    prob_total_14 = prob_pool_acertar * prob_14_se_pool_acertar
                    
                    st.markdown(f"""
                    <div class="cover-stats">
                    <strong>🎲 Análise de Probabilidade Real:</strong><br>
                    • Probabilidade do sorteio cair DENTRO do pool: {prob_pool_acertar:.4%}<br>
                    • Probabilidade de GARANTIR 14 pontos SE cair no pool: {prob_14_se_pool_acertar:.2%}<br>
                    • <strong>Probabilidade TOTAL de 14 pontos garantidos: {prob_total_14:.4%}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Gere um pool primeiro!")

        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown(f"### 📋 Jogos Gerados ({len(st.session_state.jogos_gerados)})")
            
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                nums_html = formatar_jogo_html(jogo)
                st.markdown(f"""
                <div style='border-left: 5px solid #f97316; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>
                    <strong>Jogo {i+1:2d}</strong><br>
                    {nums_html}
                </div>
                """, unsafe_allow_html=True)
            
            if len(st.session_state.jogos_gerados) > 20:
                st.info(f"Exibindo os primeiros 20 de {len(st.session_state.jogos_gerados)} jogos. Salve para ver todos.")
            
            if st.button("💾 Salvar Jogos EMS 5.0", key="salvar_v5", use_container_width=True):
                ultimo = st.session_state.dados_api[0]
                arquivo, jogo_id = salvar_jogos_gerados(
                    st.session_state.jogos_gerados, 
                    [], 
                    {"versao": "EMS 5.0", "pool": st.session_state.get("pool_atual", [])}, 
                    ultimo['concurso'], 
                    ultimo['data']
                )
                if arquivo:
                    st.success(f"✅ {len(st.session_state.jogos_gerados)} jogos salvos! ID: {jogo_id}")
                    st.session_state.jogos_salvos = carregar_jogos_salvos()

    # ================= TAB 4: CONFERÊNCIA INTELIGENTE =================
    with tab4:
        st.markdown("### 🔍 Conferência Inteligente de Jogos")
        st.caption("Confira seus jogos contra qualquer resultado e obtenha análises detalhadas")
        
        # Seleção do resultado oficial
        st.markdown("#### 📌 Resultado Oficial")
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
        
        # Entrada dos jogos para conferir
        st.markdown("#### 📋 Jogos para Conferir")
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
                st.warning("Nenhum jogo gerado na sessão atual. Gere jogos na aba 'Gerador de Jogos' primeiro.")
        
        elif opcao_jogos == "Carregar de arquivo CSV":
            uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
            if uploaded_file:
                df_carregado = pd.read_csv(uploaded_file)
                if "Dezenas" in df_carregado.columns:
                    jogos_para_conferir = df_carregado["Dezenas"].tolist()
                    st.success(f"{len(jogos_para_conferir)} jogos carregados do CSV")
                else:
                    st.error("Arquivo CSV deve conter uma coluna 'Dezenas'")
        
        else:  # Digitar manualmente
            jogos_texto = st.text_area(
                "Digite os jogos (um por linha, números separados por vírgula)",
                placeholder="Exemplo:\n1,2,3,4,5,6,7,8,9,10,11,12,13,14,15\n2,4,6,8,10,12,14,16,18,20,22,24,1,3,5"
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
                    st.success(f"{len(jogos_para_conferir)} jogos carregados manualmente")
                else:
                    st.warning("Nenhum jogo válido encontrado")
        
        # Botão para conferir
        if jogos_para_conferir and concurso_resultado:
            if st.button("🔍 CONFERIR JOGOS", use_container_width=True, type="primary"):
                with st.spinner("Conferindo jogos..."):
                    df_conferencia = conferir_jogos_inteligente(jogos_para_conferir, resultado_oficial)
                    
                    st.markdown("### 📊 Resultados da Conferência")
                    
                    # Resumo
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Jogos", len(df_conferencia))
                    with col2:
                        st.metric("Melhor Acerto", df_conferencia.iloc[0]["Acertos"])
                    with col3:
                        st.metric("Média Acertos", round(df_conferencia["Acertos"].mean(), 1))
                    with col4:
                        st.metric("Jogos com 11+", len(df_conferencia[df_conferencia["Acertos"] >= 11]))
                    
                    # Tabela de resultados
                    st.markdown("#### 🎯 Classificação dos Jogos")
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
                    
                    # Exportar resultado
                    df_export_conferencia = df_conferencia.copy()
                    df_export_conferencia["Dezenas"] = df_export_conferencia["Dezenas"].apply(lambda x: ", ".join(f"{n:02d}" for n in x))
                    df_export_conferencia["Acertos_Dezenas"] = df_export_conferencia["Acertos_Dezenas"].apply(lambda x: ", ".join(f"{n:02d}" for n in x))
                    
                    st.download_button(
                        label="📥 Exportar Resultado da Conferência",
                        data=df_export_conferencia.to_csv(index=False),
                        file_name=f"conferencia_{concurso_resultado['concurso']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        # Análise de frequência
        st.markdown("### 📊 Análise de Frequência dos Jogos")
        if jogos_para_conferir:
            if st.button("📈 Analisar Frequência", use_container_width=True):
                with st.spinner("Analisando frequência..."):
                    df_freq = analisar_frequencia_jogos(jogos_para_conferir)
                    
                    st.markdown("#### 🔢 Frequência dos Números")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.dataframe(df_freq.head(15), use_container_width=True, hide_index=True)
                    with col2:
                        st.dataframe(df_freq.tail(15), use_container_width=True, hide_index=True)
                    
                    # Gráfico de barras
                    st.markdown("#### 📊 Distribuição de Frequência")
                    st.bar_chart(df_freq.set_index("Número")["Frequência"])
                    
                    # Estatísticas
                    st.markdown("#### 📈 Estatísticas Gerais")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Números mais frequentes", f"{df_freq.iloc[0]['Número']} ({df_freq.iloc[0]['Frequência']}x)")
                    with col2:
                        st.metric("Números menos frequentes", f"{df_freq.iloc[-1]['Número']} ({df_freq.iloc[-1]['Frequência']}x)")
                    with col3:
                        st.metric("Média de aparições", f"{df_freq['Frequência'].mean():.1f}")
        
        # Gerador Otimizado
        st.markdown("### 🤖 Gerador de Jogos Otimizados")
        st.caption("Baseado na análise dos seus jogos e nos resultados recentes")
        
        if jogos_para_conferir and concurso_resultado:
            col1, col2 = st.columns(2)
            with col1:
                qtd_otimizados = st.slider("Quantidade de jogos otimizados", 5, 30, 10)
            with col2:
                estrategia_otimizacao = st.selectbox(
                    "Estratégia de otimização",
                    ["inteligente", "frequencia", "hibrido"],
                    format_func=lambda x: {"inteligente": "🧠 Inteligente (híbrido)", 
                                          "frequencia": "📊 Baseado em Frequência", 
                                          "hibrido": "🎯 Híbrido + Resultado"}[x]
                )
            
            if st.button("🚀 GERAR JOGOS OTIMIZADOS", use_container_width=True, type="primary"):
                with st.spinner("Gerando jogos otimizados..."):
                    jogos_otimizados = gerar_jogos_otimizados(
                        jogos_para_conferir,
                        resultado_oficial,
                        n_jogos=qtd_otimizados,
                        estrategia=estrategia_otimizacao
                    )
                    
                    st.session_state.jogos_otimizados = jogos_otimizados
                    st.success(f"✅ {len(jogos_otimizados)} jogos otimizados gerados!")
                    
                    st.markdown("### 🎯 Jogos Otimizados")
                    for i, jogo in enumerate(jogos_otimizados):
                        st.markdown(f"""
                        <div style='border-left: 5px solid #00ffaa; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>
                            <strong>Jogo {i+1:2d}</strong><br>
                            {formatar_jogo_html(jogo)}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Botão para usar esses jogos
                    if st.button("💾 Usar estes jogos como base", use_container_width=True):
                        st.session_state.jogos_gerados = jogos_otimizados
                        st.session_state.scores = [score_jogo_real(j) for j in jogos_otimizados]
                        st.success("Jogos otimizados carregados na aba 'Gerador de Jogos'!")

    # ================= TAB 5: AVALIAÇÃO ESTATÍSTICA =================
    with tab5:
        st.markdown("### 📈 Avaliação Estatística dos Jogos")
        baseline = st.session_state.baseline_cache
        st.markdown(f"**Baseline Aleatório:** Média = {baseline['media']:.3f}, Desvio = {baseline['std']:.3f}")
        dist_emp = distribuicoes_empiricas(st.session_state.historico_df)
        
        with st.expander("📊 Distribuições Empíricas Históricas"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Pares**")
                st.bar_chart(pd.DataFrame(dist_emp['pares'].items(), columns=["Quantidade", "Probabilidade"]).set_index("Quantidade"))
            with col2:
                st.markdown("**Primos**")
                st.bar_chart(pd.DataFrame(dist_emp['primos'].items(), columns=["Quantidade", "Probabilidade"]).set_index("Quantidade"))

        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            avaliacao = []
            for i, jogo in enumerate(st.session_state.jogos_gerados[:50]):
                features = {"pares": contar_pares(jogo), "primos": contar_primos(jogo), 
                           "consecutivos": contar_consecutivos(jogo), "soma": (sum(jogo)//20)*20}
                logL = log_likelihood(features, dist_emp)
                score_ems = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                avaliacao.append({
                    "Jogo": i+1, 
                    "Log-Likelihood": round(logL, 4),
                    "Score Prob.": round(score_ems, 2)
                })
            df_avaliacao = pd.DataFrame(avaliacao)
            st.dataframe(df_avaliacao.sort_values("Score Prob.", ascending=False).reset_index(drop=True), use_container_width=True, hide_index=True)

        st.markdown("### 🎲 Simulação Monte Carlo")
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            n_sim = st.slider("Simulações por jogo", 1000, 50000, 10000, key="mc_sim")
            if st.button("Executar Monte Carlo"):
                with st.spinner(f"Simulando {n_sim} sorteios para cada jogo..."):
                    mc_res = []
                    for i, jogo in enumerate(st.session_state.jogos_gerados[:10]):
                        res = monte_carlo_jogo(tuple(jogo), n_sim)
                        mc_res.append({
                            "Jogo": i+1, 
                            "P(≥11)": f"{res['P>=11']*100:.2f}%", 
                            "P(≥12)": f"{res['P>=12']*100:.2f}%", 
                            "P(≥13)": f"{res['P>=13']*100:.2f}%", 
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

        st.markdown("### 📊 Analisar um Jogo")
        jogo_input = st.text_input("Digite 15 números separados por vírgula", placeholder="Ex: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15")
        if jogo_input:
            try:
                numeros = [int(n.strip()) for n in jogo_input.split(",")]
                if len(numeros) == 15 and len(set(numeros)) == 15 and all(1 <= n <= 25 for n in numeros):
                    analise = motor_geo.analisar_jogo(numeros)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Centroide", f"({analise['centroide'][0]}, {analise['centroide'][1]})")
                    with col2:
                        st.metric("Dispersão Média", analise['dispersao_media'])
                    with col3:
                        st.metric("Pares Adjacentes", analise['pares_adjacentes'])
                else:
                    st.error("Jogo inválido. Deve ter 15 números únicos entre 1 e 25.")
            except:
                st.error("Formato inválido. Use números separados por vírgula.")

    # ================= TAB 7: CONFERÊNCIA SALVOS =================
    with tab7:
        st.markdown("### ✅ Conferência de Jogos Salvos")
        st.session_state.jogos_salvos = carregar_jogos_salvos()
        if not st.session_state.jogos_salvos:
            st.warning("Nenhum jogo salvo encontrado.")
        else:
            opcoes = [f"ID {j['id']} | Concurso #{j['concurso_base']['numero']} | {j['data_geracao'][:19]}" for j in st.session_state.jogos_salvos]
            idx = st.selectbox("Selecione o fechamento", range(len(opcoes)), format_func=lambda i: opcoes[i])
            fechamento = st.session_state.jogos_salvos[idx]
            jogos = garantir_jogos_como_listas(fechamento["jogos"])
            concurso_escolhido = st.selectbox("Selecione o concurso para conferência", st.session_state.dados_api, format_func=lambda c: f"#{c['concurso']} - {c['data']}")
            dezenas_sorteadas = set(map(int, concurso_escolhido["dezenas"]))
            if st.button("🔍 CONFERIR", use_container_width=True):
                resultados = []
                for i, jogo in enumerate(jogos):
                    acertos = len(set(jogo) & dezenas_sorteadas)
                    resultados.append({"Jogo": i+1, "Acertos": acertos})
                df_resultado = pd.DataFrame(resultados).sort_values("Acertos", ascending=False)
                st.dataframe(df_resultado, use_container_width=True, hide_index=True)
                adicionar_conferencia(fechamento["arquivo"], {"numero": concurso_escolhido["concurso"], "data": concurso_escolhido["data"]}, df_resultado["Acertos"].tolist(), {})
                st.success("Conferência salva!")

if __name__ == "__main__":
    main()

st.markdown("""
<style>
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#00ffcc,#00aaff,#00ffcc);box-shadow:0 0 10px #00ffcc;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(0,255,200,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
<div class="footer-premium"><div class="footer-title">ELITE MASTER SYSTEM</div><div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div></div>
""", unsafe_allow_html=True)
