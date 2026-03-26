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
from itertools import combinations  # ADICIONADO para fechamento
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
# EMS 3.0 - SCORE + GENÉTICO + FECHAMENTO
# =====================================================

def score_jogo_ems(jogo, dist_emp, motor_geo, ultimo):
    """Score inteligente que combina múltiplos critérios matemáticos"""
    
    pares = contar_pares(jogo)
    primos = contar_primos(jogo)
    consecutivos = contar_consecutivos(jogo)
    soma = (sum(jogo)//20)*20
    repetidas = len(set(jogo) & set(ultimo))

    features = {
        "pares": pares,
        "primos": primos,
        "consecutivos": consecutivos,
        "soma": soma
    }

    logL = log_likelihood(features, dist_emp)

    geo = motor_geo.analisar_jogo(jogo)
    dispersao = geo.get("dispersao_media", 2.2)

    score_geo = 1 / (1 + abs(dispersao - 2.2))
    score_rep = 1 - abs(repetidas - 9)/9
    penalty_cons = max(0, consecutivos - 4) * 0.1

    score = (
        logL * 0.5 +
        score_geo * 2.0 +
        score_rep * 2.0 -
        penalty_cons +
        random.random() * 0.2
    )

    return score


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


def algoritmo_genetico_ems(
    gerador,
    dist_emp,
    motor_geo,
    ultimo,
    config_filtros,
    populacao_size=80,
    geracoes=25
):
    """Algoritmo genético para evoluir jogos de alta qualidade"""
    
    populacao = gerador.gerar_multiplos_jogos(populacao_size, config_filtros)

    for _ in range(geracoes):
        
        avaliados = [
            (j, score_jogo_ems(j, dist_emp, motor_geo, ultimo))
            for j in populacao
        ]
        
        avaliados.sort(key=lambda x: x[1], reverse=True)
        sobreviventes = [j for j, _ in avaliados[:int(populacao_size * 0.3)]]
        
        nova_pop = sobreviventes.copy()
        
        while len(nova_pop) < populacao_size:
            p1, p2 = random.sample(sobreviventes, 2)
            filho = mutacao(crossover(p1, p2))
            
            if gerador.aplicar_filtros(filho, config_filtros):
                nova_pop.append(filho)
        
        populacao = nova_pop
    
    final = [
        (j, score_jogo_ems(j, dist_emp, motor_geo, ultimo))
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
    dist_emp,
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
            score = score_jogo_ems(j, dist_emp, motor_geo, ultimo)
            avaliados.append((j, score))
    
    avaliados.sort(key=lambda x: x[1], reverse=True)
    
    return avaliados[:qtd_jogos], pool


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
            if n in self.ultimo:
                peso *= 2.0 # Peso extra para números do último concurso
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
    st.subheader("🎯 Análise e Geração de Jogos")

    # Reorganização das abas para conter apenas o que é matematicamente relevante
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Análise do Último Concurso",
        "🎲 Gerador de Jogos (Filtros Ajustáveis)",
        "📈 Avaliação Estatística",
        "📐 Geometria do Volante",
        "✅ Conferência de Jogos Salvos"
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

    # ================= TAB 2: GERADOR DE JOGOS (FILTROS AJUSTÁVEIS) =================
    with tab2:
        st.markdown("### 🎲 Gerador de Jogos com Filtros Ajustáveis")
        st.caption("Base estatística: Frequência e atraso dos números, com pesos configuráveis.")
        
        with st.expander("⚙️ Configuração dos Filtros", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
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
            st.caption("Filtros adicionais (consecutivos, linhas, colunas) podem ser ativados para uma geração mais restritiva.")

        col1, col2, col3 = st.columns(3)
        with col1:
            qtd_jogos = st.slider("Quantidade de jogos", 5, 50, 10)
        
        with col2:
            if st.button("🚀 GERAR JOGOS", use_container_width=True):
                with st.spinner(f"Gerando {qtd_jogos} jogos..."):
                    jogos = st.session_state.gerador_principal.gerar_multiplos_jogos(qtd_jogos, st.session_state.config_filtros)
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.session_state.scores = []
                        st.success(f"✅ {len(jogos)} jogos gerados!")
        
        with col3:
            if st.button("🔥 EMS 3.0", use_container_width=True, type="primary"):
                with st.spinner("Gerando jogos com Algoritmo Genético..."):
                    dist_emp = distribuicoes_empiricas(st.session_state.historico_df)
                    
                    resultados = algoritmo_genetico_ems(
                        st.session_state.gerador_principal,
                        dist_emp,
                        st.session_state.motor_geometria,
                        st.session_state.gerador_principal.ultimo,
                        st.session_state.config_filtros
                    )
                    
                    st.session_state.jogos_gerados = [r[0] for r in resultados]
                    st.session_state.scores = [r[1] for r in resultados]
                    st.success(f"✅ {len(resultados)} jogos gerados com EMS 3.0!")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💣 FECHAMENTO INTELIGENTE", use_container_width=True):
                with st.spinner("Gerando fechamento inteligente..."):
                    dist_emp = distribuicoes_empiricas(st.session_state.historico_df)
                    
                    resultados, pool = fechamento_inteligente_ems(
                        st.session_state.gerador_principal,
                        dist_emp,
                        st.session_state.motor_geometria,
                        st.session_state.gerador_principal.ultimo,
                        st.session_state.config_filtros,
                        qtd_jogos
                    )
                    
                    st.session_state.jogos_gerados = [r[0] for r in resultados]
                    st.session_state.scores = [r[1] for r in resultados]
                    st.success(f"✅ {len(resultados)} jogos gerados com Fechamento!")
                    st.info(f"🎯 Pool de números selecionado: {pool}")
        
        with col2:
            if st.button("🔁 Executar Backtest", use_container_width=True):
                with st.spinner("Executando backtest..."):
                    score = backtest_estrategia([sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:qtd]], st.session_state.config_filtros)
                    st.info(f"Score médio nos últimos 30 concursos: {score:.2f} acertos (baseline teórico: ~11.5)")

        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            jogos = st.session_state.jogos_gerados
            st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
            
            for i, jogo in enumerate(jogos):
                score = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🔹"
                
                nums_html = formatar_jogo_html(jogo)
                stats = f"⚖️ {contar_pares(jogo)}p | ➕ {sum(jogo)} | 🔁 {len(set(jogo) & set(st.session_state.gerador_principal.ultimo))} rep | 📊 {contar_por_faixa(jogo, [(1,8),(9,16),(17,25)])}"
                
                st.markdown(f"""
                <div style='border-left: 5px solid #4cc9f0; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — Score: {round(score,2)}<br>
                    {nums_html}<br>
                    <small style='color:#aaa;'>{stats}</small>
                </div>
                """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Salvar Jogos", key="salvar_jogos", use_container_width=True):
                    ultimo = st.session_state.dados_api[0]
                    arquivo, jogo_id = salvar_jogos_gerados(
                        jogos, 
                        [], 
                        {"filtros": st.session_state.config_filtros, "score": st.session_state.scores}, 
                        ultimo['concurso'], 
                        ultimo['data']
                    )
                    if arquivo:
                        st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                        st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            with col2:
                df_export = pd.DataFrame({
                    "Jogo": range(1, len(jogos)+1),
                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                    "Score": [round(s, 2) for s in st.session_state.scores] if st.session_state.scores else [0]*len(jogos),
                    "Pares": [contar_pares(j) for j in jogos],
                    "Soma": [sum(j) for j in jogos],
                    "Repetidas": [len(set(j) & set(st.session_state.gerador_principal.ultimo)) for j in jogos],
                    "Baixas(1-8)": [contar_por_faixa(j, [(1,8)])[0] for j in jogos],
                    "Médias(9-16)": [contar_por_faixa(j, [(9,16)])[0] for j in jogos],
                    "Altas(17-25)": [contar_por_faixa(j, [(17,25)])[0] for j in jogos]
                })
                st.download_button(
                    label="📥 Exportar CSV", 
                    data=df_export.to_csv(index=False), 
                    file_name=f"jogos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                    mime="text/csv", 
                    use_container_width=True
                )

    # ================= TAB 3: AVALIAÇÃO ESTATÍSTICA =================
    with tab3:
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
            for i, jogo in enumerate(st.session_state.jogos_gerados):
                features = {"pares": contar_pares(jogo), "primos": contar_primos(jogo), "consecutivos": contar_consecutivos(jogo), "soma": (sum(jogo)//20)*20}
                logL = log_likelihood(features, dist_emp)
                score_ems = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                avaliacao.append({
                    "Jogo": i+1, 
                    "Log-Likelihood": round(logL, 4),
                    "Score EMS": round(score_ems, 2)
                })
            df_avaliacao = pd.DataFrame(avaliacao)
            df_avaliacao["Score Normalizado (0-100)"] = 100 * (df_avaliacao["Score EMS"] - df_avaliacao["Score EMS"].min()) / (df_avaliacao["Score EMS"].max() - df_avaliacao["Score EMS"].min()) if df_avaliacao["Score EMS"].max() > df_avaliacao["Score EMS"].min() else 50
            st.dataframe(df_avaliacao.sort_values("Score EMS", ascending=False).reset_index(drop=True), use_container_width=True, hide_index=True)

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

    # ================= TAB 4: GEOMETRIA DO VOLANTE =================
    with tab4:
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

    # ================= TAB 5: CONFERÊNCIA =================
    with tab5:
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
