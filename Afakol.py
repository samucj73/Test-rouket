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
    page_title="🎯 LOTOFÁCIL - EMS 7.0 Cobertura Profissional",
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
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 LOTOFÁCIL - EMS 7.0 COBERTURA PROFISSIONAL")
st.caption("Sistema de Cobertura Combinatória - Garantia de 13 Pontos via Set Cover Optimization")

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
# EMS 7.0 - SISTEMA PROFISSIONAL DE COBERTURA DE 13 NÚMEROS
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

def calcular_ganho_cobertura(jogo, coberto_set):
    """
    Calcula quantas novas combinações de 13 números um jogo cobre
    Cada jogo de 15 números cobre C(15,13) = 105 combinações de 13
    """
    ganho = 0
    for comb in combinations(jogo, 13):
        if comb not in coberto_set:
            ganho += 1
    return ganho

def gerar_sistema_cobertura_13(qtd_jogos=20, iteracoes_por_jogo=2000, usar_pool=None):
    """
    SISTEMA PROFISSIONAL DE COBERTURA DE 13 NÚMEROS
    
    Este é um solver para o problema Set Cover:
    - Cada jogo cobre 105 combinações de 13 números
    - O objetivo é maximizar a cobertura única dessas combinações
    - Algoritmo Greedy: a cada passo, escolhe o jogo que cobre mais combinações novas
    
    Args:
        qtd_jogos: número de jogos a gerar
        iteracoes_por_jogo: intensidade de busca para cada jogo
        usar_pool: lista de números para restringir o espaço (opcional)
    
    Returns:
        jogos: lista de jogos selecionados
        cobertura_stats: estatísticas de cobertura
    """
    
    # Universo de números
    if usar_pool:
        universo_numeros = usar_pool
    else:
        universo_numeros = list(range(1, 26))
    
    # Conjunto de combinações já cobertas
    coberto = set()
    jogos = []
    
    progress_bar = st.progress(0, text="Construindo cobertura de 13 números...")
    
    for idx in range(qtd_jogos):
        melhor_jogo = None
        melhor_ganho = -1
        
        # Busca intensiva pelo jogo que cobre mais combinações novas
        for _ in range(iteracoes_por_jogo):
            jogo = tuple(sorted(random.sample(universo_numeros, 15)))
            ganho = calcular_ganho_cobertura(jogo, coberto)
            
            if ganho > melhor_ganho:
                melhor_ganho = ganho
                melhor_jogo = jogo
        
        if melhor_jogo is None:
            break
        
        jogos.append(list(melhor_jogo))
        
        # Atualiza cobertura
        for comb in combinations(melhor_jogo, 13):
            coberto.add(comb)
        
        # Calcula estatísticas
        total_combinacoes_possiveis = len(list(combinations(universo_numeros, 13)))
        percentual = (len(coberto) / total_combinacoes_possiveis * 100) if total_combinacoes_possiveis > 0 else 0
        
        progress_bar.progress(
            (idx + 1) / qtd_jogos,
            text=f"Jogo {idx+1}/{qtd_jogos} | Ganho: {melhor_ganho} | Cobertura: {len(coberto):,} / {total_combinacoes_possiveis:,} ({percentual:.2f}%)"
        )
    
    progress_bar.empty()
    
    # Estatísticas finais
    total_combinacoes = len(list(combinations(universo_numeros, 13)))
    cobertura_stats = {
        "combinacoes_13_cobertas": len(coberto),
        "total_combinacoes_possiveis": total_combinacoes,
        "percentual_cobertura": (len(coberto) / total_combinacoes * 100) if total_combinacoes > 0 else 0,
        "jogos_gerados": len(jogos),
        "media_ganho_por_jogo": sum(len(list(combinations(j, 13))) for j in jogos) / len(jogos) if jogos else 0
    }
    
    return jogos, cobertura_stats

def gerar_sistema_pool_13(pool, qtd_jogos=20, iteracoes_por_jogo=1000):
    """
    Versão otimizada que trabalha dentro de um pool de números
    Isso reduz drasticamente o espaço de busca e aumenta eficiência
    
    Args:
        pool: lista de 20 números
        qtd_jogos: número de jogos a gerar
        iteracoes_por_jogo: intensidade de busca
    
    Returns:
        jogos: lista de jogos selecionados
        cobertura_stats: estatísticas de cobertura
    """
    
    coberto = set()
    jogos = []
    
    progress_bar = st.progress(0, text=f"Construindo cobertura no pool de {len(pool)} números...")
    
    for idx in range(qtd_jogos):
        melhor_jogo = None
        melhor_ganho = -1
        
        for _ in range(iteracoes_por_jogo):
            jogo = tuple(sorted(random.sample(pool, 15)))
            ganho = calcular_ganho_cobertura(jogo, coberto)
            
            if ganho > melhor_ganho:
                melhor_ganho = ganho
                melhor_jogo = jogo
        
        if melhor_jogo is None:
            break
        
        jogos.append(list(melhor_jogo))
        
        for comb in combinations(melhor_jogo, 13):
            coberto.add(comb)
        
        total_combinacoes_pool = len(list(combinations(pool, 13)))
        percentual = (len(coberto) / total_combinacoes_pool * 100) if total_combinacoes_pool > 0 else 0
        
        progress_bar.progress(
            (idx + 1) / qtd_jogos,
            text=f"Jogo {idx+1}/{qtd_jogos} | Cobertura pool: {percentual:.2f}%"
        )
    
    progress_bar.empty()
    
    total_combinacoes_pool = len(list(combinations(pool, 13)))
    cobertura_stats = {
        "combinacoes_13_cobertas": len(coberto),
        "total_combinacoes_possiveis": total_combinacoes_pool,
        "percentual_cobertura": (len(coberto) / total_combinacoes_pool * 100) if total_combinacoes_pool > 0 else 0,
        "jogos_gerados": len(jogos),
        "pool_utilizado": pool
    }
    
    return jogos, cobertura_stats

def gerar_pool_inteligente_para_cobertura(gerador, tamanho=20):
    """
    Gera pool inteligente baseado em frequência e atraso
    Otimizado para maximizar cobertura de 13 números
    """
    if gerador:
        numeros, pesos = gerador.pool_ponderado
        # Seleciona números com maior peso
        escolhidos = set()
        
        # Primeiro, garante distribuição balanceada
        for linha in range(5):
            for coluna in range(5):
                num = linha * 5 + coluna + 1
                if len(escolhidos) < tamanho and random.random() < 0.4:
                    escolhidos.add(num)
        
        # Completa com os números de maior peso
        candidatos_restantes = [n for n in numeros if n not in escolhidos]
        pesos_restantes = [pesos[numeros.index(n)] for n in candidatos_restantes if n in numeros]
        
        while len(escolhidos) < tamanho and candidatos_restantes:
            if pesos_restantes:
                n = random.choices(candidatos_restantes, weights=pesos_restantes, k=1)[0]
            else:
                n = random.choice(candidatos_restantes)
            escolhidos.add(n)
            if n in candidatos_restantes:
                idx = candidatos_restantes.index(n)
                candidatos_restantes.pop(idx)
                if idx < len(pesos_restantes):
                    pesos_restantes.pop(idx)
        
        pool = sorted(escolhidos)
    else:
        # Fallback: seleção aleatória balanceada
        pool = []
        pares = [n for n in range(1, 26) if n % 2 == 0]
        impares = [n for n in range(1, 26) if n % 2 != 0]
        pool.extend(random.sample(pares, tamanho // 2))
        pool.extend(random.sample(impares, tamanho - tamanho // 2))
        pool.sort()
    
    return pool

def calcular_probabilidade_13_garantido(pool, cobertura_stats):
    """
    Calcula a probabilidade real de garantir 13 pontos
    Se o sorteio cair dentro do pool, a garantia é dada pelo percentual de cobertura
    """
    prob_pool_acertar = math.comb(len(pool), 15) / math.comb(25, 15) if pool else 0
    prob_13_se_pool = cobertura_stats['percentual_cobertura'] / 100 if cobertura_stats else 0
    
    prob_total_13 = prob_pool_acertar * prob_13_se_pool
    
    return {
        "prob_pool_acertar": prob_pool_acertar,
        "prob_13_se_pool": prob_13_se_pool,
        "prob_total_13_garantido": prob_total_13
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
    """Converte string de dezenas para set de inteiros"""
    if isinstance(dezenas_str, str):
        return set(map(int, dezenas_str.replace('"', '').replace(' ', '').split(',')))
    elif isinstance(dezenas_str, list):
        return set(dezenas_str)
    else:
        return set()

def conferir_jogos_inteligente(jogos, resultado_set):
    """Confere jogos contra um resultado oficial"""
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
    """Analisa a frequência dos números em um conjunto de jogos"""
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
# BACKTESTING
# =====================================================
def backtest_cobertura(historico, jogos_sistema, num_testes=30):
    """Testa o sistema de cobertura nos últimos concursos"""
    resultados = []
    for i in range(1, min(num_testes, len(historico)) + 1):
        concurso_alvo = set(historico[-i])
        melhor_acerto = 0
        for jogo in jogos_sistema:
            acertos = len(set(jogo) & concurso_alvo)
            melhor_acerto = max(melhor_acerto, acertos)
        resultados.append(melhor_acerto)
    return {
        "media": np.mean(resultados) if resultados else 0,
        "max": max(resultados) if resultados else 0,
        "min": min(resultados) if resultados else 0,
        "p13": sum(1 for r in resultados if r >= 13) / len(resultados) if resultados else 0
    }

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
    if "config_filtros" not in st.session_state:
        st.session_state.config_filtros = {
            'pares_min': 5, 'pares_max': 10,
            'soma_min': 160, 'soma_max': 240,
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
    st.subheader("🎯 EMS 7.0 - Sistema Profissional de Cobertura de 13 Números")

    # Abas reorganizadas
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Análise do Último Concurso",
        "🔥 COBERTURA 13 (Set Cover)",
        "🎯 COBERTURA COM POOL",
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

    # ================= TAB 2: COBERTURA 13 (SET COVER) =================
    with tab2:
        st.markdown("### 🔥 SISTEMA PROFISSIONAL DE COBERTURA DE 13 NÚMEROS")
        st.markdown("""
        <div class="pro-highlight">
        <strong>🎯 CONCEITO MATEMÁTICO:</strong><br>
        • Cada jogo de 15 números cobre <strong>C(15,13) = 105 combinações de 13 números</strong><br>
        • Universo total: <strong>C(25,13) = 5.200.300 combinações</strong><br>
        • Este sistema resolve o problema de <strong>Set Cover</strong> para maximizar cobertura única<br>
        • <strong>GARANTIA:</strong> Se o sorteio tiver 13 números dentro do espaço coberto, você GARANTE 13 pontos!
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_jogos = st.slider("Quantidade de jogos", 10, 50, 20, key="qtd_jogos_cover")
        with col2:
            iteracoes = st.slider("Intensidade de busca (por jogo)", 500, 5000, 2000, key="iter_cover",
                                 help="Maior intensidade = melhor cobertura, porém mais lento")
        
        if st.button("🔥 GERAR SISTEMA DE COBERTURA 13", use_container_width=True, type="primary"):
            with st.spinner(f"Construindo cobertura de 13 números com {qtd_jogos} jogos..."):
                jogos, stats = gerar_sistema_cobertura_13(
                    qtd_jogos=qtd_jogos,
                    iteracoes_por_jogo=iteracoes
                )
                
                st.session_state.jogos_gerados = jogos
                st.session_state.cobertura_stats = stats
                st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)["P>=13"] * 100 for j in jogos]
                
                st.success(f"✅ {len(jogos)} jogos gerados!")
                
                # Estatísticas de cobertura
                st.markdown("### 📊 Estatísticas de Cobertura")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Combinações de 13 cobertas", f"{stats['combinacoes_13_cobertas']:,}")
                with col2:
                    st.metric("Total combinações possíveis", f"{stats['total_combinacoes_possiveis']:,}")
                with col3:
                    st.metric("% de Cobertura", f"{stats['percentual_cobertura']:.4f}%")
                
                # Probabilidade real
                prob_13_garantido = stats['percentual_cobertura'] / 100
                st.markdown(f"""
                <div class="ev-highlight">
                <strong>🎲 PROBABILIDADE REAL:</strong><br>
                Se o sorteio cair em QUALQUER combinação de 15 números, a probabilidade de você ter GARANTIDO 13 pontos é de:<br>
                <strong style="font-size: 1.4rem;">{stats['percentual_cobertura']:.6f}%</strong><br>
                <small>Isso significa que em aproximadamente 1 a cada {int(100 / stats['percentual_cobertura'] if stats['percentual_cobertura'] > 0 else 0):,} sorteios, você garante 13 pontos!</small>
                </div>
                """, unsafe_allow_html=True)
        
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown(f"### 📋 {len(st.session_state.jogos_gerados)} Jogos Gerados")
            
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                prob_13 = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🔹"
                nums_html = formatar_jogo_html(jogo)
                
                st.markdown(f"""
                <div style='border-left: 5px solid #ff00ff; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — P(13+): {prob_13:.2f}%<br>
                    {nums_html}
                </div>
                """, unsafe_allow_html=True)
            
            if len(st.session_state.jogos_gerados) > 20:
                st.info(f"Exibindo os primeiros 20 de {len(st.session_state.jogos_gerados)} jogos.")
            
            # Backtesting
            if st.button("📊 Executar Backtesting", use_container_width=True):
                with st.spinner("Executando backtesting nos últimos concursos..."):
                    historico = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:100]]
                    resultados = backtest_cobertura(historico, st.session_state.jogos_gerados, num_testes=50)
                    
                    st.markdown("### 📈 Resultados do Backtesting")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Média de acertos", f"{resultados['media']:.2f}")
                    with col2:
                        st.metric("Melhor acerto", resultados['max'])
                    with col3:
                        st.metric("Pior acerto", resultados['min'])
                    with col4:
                        st.metric("Frequência de 13+", f"{resultados['p13']*100:.1f}%")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Salvar Jogos", key="salvar_cover", use_container_width=True):
                    ultimo = st.session_state.dados_api[0]
                    arquivo, jogo_id = salvar_jogos_gerados(
                        st.session_state.jogos_gerados, 
                        [], 
                        {"versao": "EMS 7.0 Cobertura 13", "stats": st.session_state.cobertura_stats}, 
                        ultimo['concurso'], 
                        ultimo['data']
                    )
                    if arquivo:
                        st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                        st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            with col2:
                df_export = pd.DataFrame({
                    "Jogo": range(1, len(st.session_state.jogos_gerados)+1),
                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in st.session_state.jogos_gerados],
                    "P_13+_%": [round(p, 2) for p in st.session_state.scores]
                })
                st.download_button(
                    label="📥 Exportar CSV", 
                    data=df_export.to_csv(index=False), 
                    file_name=f"cobertura_13_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                    mime="text/csv", 
                    use_container_width=True
                )

    # ================= TAB 3: COBERTURA COM POOL =================
    with tab3:
        st.markdown("### 🎯 COBERTURA DE 13 NÚMEROS COM POOL REDUZIDO")
        st.markdown("""
        <div class="cover-stats">
        <strong>💡 ESTRATÉGIA AVANÇADA:</strong><br>
        Trabalhar com um pool de 20 números reduz drasticamente o espaço de busca:<br>
        • Universo total: C(25,13) = 5.200.300 combinações<br>
        • Pool de 20: C(20,13) = 77.520 combinações (67x menor!)<br>
        • Isso permite coberturas muito mais densas com poucos jogos
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            tamanho_pool = st.selectbox("Tamanho do Pool", [18, 19, 20, 21, 22], index=2)
        with col2:
            qtd_jogos_pool = st.slider("Jogos por pool", 10, 40, 20, key="qtd_jogos_pool")
        with col3:
            iter_pool = st.slider("Intensidade de busca", 500, 3000, 1000, key="iter_pool")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎯 GERAR POOL INTELIGENTE", use_container_width=True):
                with st.spinner(f"Gerando pool inteligente de {tamanho_pool} números..."):
                    pool = gerar_pool_inteligente_para_cobertura(st.session_state.gerador_principal, tamanho_pool)
                    st.session_state.pool_atual = pool
                    
                    st.markdown(f"**Pool Selecionado ({len(pool)} números):**")
                    st.markdown(" ".join(f"<span style='background:#0e1117; border:1px solid #ff00ff; border-radius:15px; padding:5px 10px; margin:2px; display:inline-block;'>{n:02d}</span>" for n in pool), unsafe_allow_html=True)
                    
                    # Estatísticas do pool
                    pares_pool = len([n for n in pool if n % 2 == 0])
                    impares_pool = len([n for n in pool if n % 2 != 0])
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Pares/Ímpares", f"{pares_pool}/{impares_pool}")
                    with col_b:
                        st.metric("Combinações de 13 possíveis", f"{len(list(combinations(pool, 13))):,}")
        
        with col2:
            if st.button("💣 GERAR COBERTURA NO POOL", use_container_width=True, type="primary"):
                if "pool_atual" not in st.session_state:
                    st.warning("Gere um pool primeiro!")
                else:
                    with st.spinner(f"Construindo cobertura no pool de {len(st.session_state.pool_atual)} números..."):
                        jogos, stats = gerar_sistema_pool_13(
                            st.session_state.pool_atual,
                            qtd_jogos=qtd_jogos_pool,
                            iteracoes_por_jogo=iter_pool
                        )
                        
                        st.session_state.jogos_gerados = jogos
                        st.session_state.cobertura_stats = stats
                        st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)["P>=13"] * 100 for j in jogos]
                        
                        st.success(f"✅ {len(jogos)} jogos gerados!")
                        
                        st.markdown("### 📊 Estatísticas de Cobertura no Pool")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Combinações de 13 cobertas", f"{stats['combinacoes_13_cobertas']:,}")
                        with col2:
                            st.metric("Total combinações no pool", f"{stats['total_combinacoes_possiveis']:,}")
                        with col3:
                            st.metric("% Cobertura do Pool", f"{stats['percentual_cobertura']:.2f}%")
                        
                        # Probabilidade real
                        probs = calcular_probabilidade_13_garantido(st.session_state.pool_atual, stats)
                        st.markdown(f"""
                        <div class="ev-highlight">
                        <strong>🎲 PROBABILIDADE REAL DE GARANTIR 13 PONTOS:</strong><br>
                        • Chance do sorteio cair DENTRO do pool: {probs['prob_pool_acertar']:.4%}<br>
                        • Chance de GARANTIR 13 pontos SE cair no pool: {probs['prob_13_se_pool']:.2f}%<br>
                        • <strong style="font-size: 1.2rem;">PROBABILIDADE TOTAL: {probs['prob_total_13_garantido']:.6f}%</strong><br>
                        <small>Isso significa 1 a cada {int(1 / probs['prob_total_13_garantido'] if probs['prob_total_13_garantido'] > 0 else 0):,} sorteios!</small>
                        </div>
                        """, unsafe_allow_html=True)
        
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown(f"### 📋 {len(st.session_state.jogos_gerados)} Jogos Gerados")
            
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                prob_13 = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                nums_html = formatar_jogo_html(jogo)
                
                st.markdown(f"""
                <div style='border-left: 5px solid #ffa500; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>
                    <strong>Jogo {i+1:2d}</strong> — P(13+): {prob_13:.2f}%<br>
                    {nums_html}
                </div>
                """, unsafe_allow_html=True)
            
            if len(st.session_state.jogos_gerados) > 20:
                st.info(f"Exibindo os primeiros 20 de {len(st.session_state.jogos_gerados)} jogos.")
            
            if st.button("💾 Salvar Jogos com Pool", key="salvar_pool", use_container_width=True):
                ultimo = st.session_state.dados_api[0]
                arquivo, jogo_id = salvar_jogos_gerados(
                    st.session_state.jogos_gerados, 
                    [], 
                    {"versao": "EMS 7.0 Pool Coverage", "pool": st.session_state.get("pool_atual", [])}, 
                    ultimo['concurso'], 
                    ultimo['data']
                )
                if arquivo:
                    st.success(f"✅ {len(st.session_state.jogos_gerados)} jogos salvos! ID: {jogo_id}")
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
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#ff00ff,#aa00ff,#ff00ff);box-shadow:0 0 10px #ff00ff;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(255,0,255,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
<div class="footer-premium"><div class="footer-title">EMS 7.0 - SET COVER PROFESSIONAL</div><div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div></div>
""", unsafe_allow_html=True)
