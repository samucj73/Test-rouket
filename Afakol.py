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

try:
    from ortools.linear_solver import pywraplp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

st.set_page_config(
    page_title="🎯 LOTOFÁCIL - Análise e Geração",
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
.metric-card { background: #16213e; padding: 10px; border-radius: 10px; text-align: center; }
.cover-stats { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 15px; border-radius: 12px; margin: 10px 0; border: 1px solid #00ffaa20; }
.highlight { background: #00ffaa20; border-left: 4px solid #00ffaa; padding: 10px; border-radius: 8px; margin: 10px 0; }
.ilp-highlight { background: linear-gradient(135deg, #ff00ff20 0%, #aa00ff20 100%); border: 2px solid #ff00ff; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ia7-highlight { background: linear-gradient(135deg, #ff880020 0%, #ff440020 100%); border: 2px solid #ff8800; padding: 15px; border-radius: 12px; margin: 10px 0; }
.nash-highlight { background: linear-gradient(135deg, #9b59b620 0%, #6c348320 100%); border: 2px solid #9b59b6; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ev-highlight { background: linear-gradient(135deg, #00ff8820 0%, #00cc6620 100%); border: 2px solid #00ff88; padding: 15px; border-radius: 12px; margin: 10px 0; }
.img-analysis-highlight { background: linear-gradient(135deg, #ffd70020 0%, #ff8c0020 100%); border: 2px solid #ffd700; padding: 15px; border-radius: 12px; margin: 10px 0; }
.elite-master-highlight { background: linear-gradient(135deg, #ff880030 0%, #ff440030 100%); border: 2px solid #ff8800; padding: 15px; border-radius: 12px; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 LOTOFÁCIL - Análise e Geração")
st.caption("Análise Estatística e Geração de Jogos com Filtros Matemáticos")

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
# 🧠 MOTOR DE PESOS DINÂMICOS - ELITE MASTER 8.0
# =====================================================
class MotorPesosDinamicos:
    """
    Sistema Elite Master de Pesos Dinâmicos
    
    Estratégias integradas:
    1. EWMA (Média Móvel Ponderada Exponencial)
    2. Análise de Co-ocorrência
    3. Filtro de Entropia
    4. Pontuação de Nash
    """
    
    def __init__(self, dados_api, qtd_concursos=100):
        self.dados_api = dados_api
        self.qtd_concursos = min(qtd_concursos, len(dados_api))
        self.dezenas_totais = list(range(1, 26))
        
        self.concursos = []
        for concurso in dados_api[:self.qtd_concursos]:
            dezenas = sorted(map(int, concurso['dezenas']))
            self.concursos.append(dezenas)
        
        self.ultimo_concurso = self.concursos[0] if self.concursos else []
        self._calcular_ewma()
        self._calcular_atrasos()
        self._calcular_coocorrencia()
        
    def _calcular_ewma(self):
        alpha = 0.85
        freq_dict = {i: 0.0 for i in self.dezenas_totais}
        
        if not self.concursos:
            self.probabilidades_ewma = {i: 1.0 for i in self.dezenas_totais}
            return
        
        for idx, concurso in enumerate(self.concursos):
            peso = alpha ** idx
            for dezena in concurso:
                freq_dict[dezena] += peso
        
        max_freq = max(freq_dict.values()) if freq_dict.values() else 1
        if max_freq > 0:
            self.probabilidades_ewma = {k: v/max_freq for k, v in freq_dict.items()}
        else:
            self.probabilidades_ewma = {i: 1.0 for i in self.dezenas_totais}
    
    def _calcular_atrasos(self):
        self.atrasos = {i: 0 for i in self.dezenas_totais}
        if not self.concursos:
            return
        for dezena in self.dezenas_totais:
            atraso = 0
            for concurso in self.concursos:
                if dezena in concurso:
                    break
                atraso += 1
            self.atrasos[dezena] = atraso
    
    def _calcular_coocorrencia(self):
        self.matriz_coocorrencia = np.zeros((26, 26))
        for concurso in self.concursos:
            for i in concurso:
                for j in concurso:
                    if i != j:
                        self.matriz_coocorrencia[i][j] += 1
        
        self.pares_coocorrentes = {}
        for num in self.dezenas_totais:
            pares = []
            for j in self.dezenas_totais:
                if j != num and self.matriz_coocorrencia[num][j] > 0:
                    pares.append((j, self.matriz_coocorrencia[num][j]))
            pares.sort(key=lambda x: x[1], reverse=True)
            self.pares_coocorrentes[num] = pares
    
    def calcular_pesos_finais(self, peso_ewma=0.7, peso_atraso=0.3):
        pesos = []
        for dezena in self.dezenas_totais:
            freq = self.probabilidades_ewma.get(dezena, 0)
            atraso = min(self.atrasos.get(dezena, 0), 5) / 5.0
            peso = (freq * peso_ewma) + (atraso * peso_atraso)
            pesos.append(peso)
        pesos_array = np.array(pesos)
        if pesos_array.sum() > 0:
            pesos_array = pesos_array / pesos_array.sum()
        return self.dezenas_totais, pesos_array
    
    def gerar_jogo_probabilistico(self, peso_ewma=0.7, peso_atraso=0.3):
        numeros, pesos = self.calcular_pesos_finais(peso_ewma, peso_atraso)
        try:
            jogo = sorted(np.random.choice(numeros, size=15, replace=False, p=pesos))
            return [int(n) for n in jogo]
        except:
            return sorted(random.sample(self.dezenas_totais, 15))
    
    def calcular_score_elite(self, jogo):
        score = 0
        jogo_set = set(jogo)
        
        pares = contar_pares(jogo)
        if pares in [7, 8, 9]:
            score += 2
        
        primos_lista = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        primos_count = len([n for n in jogo if n in primos_lista])
        if primos_count in [5, 6]:
            score += 2
        
        if self.ultimo_concurso:
            repetidos = len(jogo_set.intersection(set(self.ultimo_concurso)))
            if repetidos in [8, 9, 10]:
                score += 2
        
        soma = sum(jogo)
        if 180 <= soma <= 210:
            score += 1
        
        moldura = [1,2,3,4,5,6,10,11,15,16,20,21,22,23,24,25]
        moldura_count = len([n for n in jogo if n in moldura])
        if 9 <= moldura_count <= 11:
            score += 1
        
        stats = {
            "pares": pares,
            "primos": primos_count,
            "repetidos": repetidos if self.ultimo_concurso else 0,
            "soma": soma,
            "moldura": moldura_count
        }
        
        return score, stats
    
    def calcular_entropia_jogo(self, jogo):
        penalty = 0
        consecutivos = contar_consecutivos(jogo)
        if consecutivos > 3:
            penalty += (consecutivos - 3) * 0.15
        
        linhas = distribuir_por_linhas(jogo)
        if max(linhas) - min(linhas) > 2:
            penalty += 0.1
        
        colunas = distribuir_por_colunas(jogo)
        if max(colunas) - min(colunas) > 2:
            penalty += 0.1
        
        return penalty
    
    def calcular_pontuacao_nash(self, jogo):
        penalty = 0
        numeros_baixos = len([n for n in jogo if n <= 12])
        if numeros_baixos > 8:
            penalty += 0.2
        elif numeros_baixos < 4:
            penalty += 0.1
        
        sequencias = 0
        jogo_ord = sorted(jogo)
        for i in range(len(jogo_ord)-2):
            if jogo_ord[i+1] == jogo_ord[i] + 1 and jogo_ord[i+2] == jogo_ord[i] + 2:
                sequencias += 1
        if sequencias > 2:
            penalty += 0.15
        
        for linha in range(5):
            nums_linha = [linha*5 + c + 1 for c in range(5)]
            if all(n in jogo for n in nums_linha):
                penalty += 0.3
        
        for coluna in range(5):
            nums_coluna = [linha*5 + coluna + 1 for linha in range(5)]
            if all(n in jogo for n in nums_coluna):
                penalty += 0.3
        
        return penalty
    
    def gerar_jogos_elite(self, qtd_jogos=10, peso_ewma=0.7, peso_atraso=0.3, 
                          filtro_rigido=True, score_minimo=7, max_tentativas=5000):
        jogos_finais = []
        scores_finais = []
        tentativas = 0
        
        progress_bar = st.progress(0, text="Gerando jogos de elite...")
        
        while len(jogos_finais) < qtd_jogos and tentativas < max_tentativas:
            tentativas += 1
            jogo = self.gerar_jogo_probabilistico(peso_ewma, peso_atraso)
            score, stats = self.calcular_score_elite(jogo)
            penalty_entropia = self.calcular_entropia_jogo(jogo)
            penalty_nash = self.calcular_pontuacao_nash(jogo)
            score_ajustado = score - penalty_entropia - penalty_nash
            
            if filtro_rigido and score < score_minimo:
                continue
            if penalty_entropia > 0.5:
                continue
            if jogo not in jogos_finais:
                jogos_finais.append(jogo)
                scores_finais.append({
                    "score": score,
                    "score_ajustado": score_ajustado,
                    "penalty_entropia": penalty_entropia,
                    "penalty_nash": penalty_nash,
                    "stats": stats
                })
            
            if tentativas % 100 == 0:
                progress_bar.progress(
                    min(len(jogos_finais)/qtd_jogos, 1.0),
                    text=f"Encontrados {len(jogos_finais)}/{qtd_jogos} jogos (tentativas: {tentativas})"
                )
        
        progress_bar.empty()
        
        indices_ordenados = sorted(range(len(scores_finais)), 
                                   key=lambda i: scores_finais[i]["score_ajustado"], 
                                   reverse=True)
        
        jogos_ordenados = [jogos_finais[i] for i in indices_ordenados]
        scores_ordenados = [scores_finais[i] for i in indices_ordenados]
        
        return jogos_ordenados, scores_ordenados, tentativas
    
    def get_top_pares_coocorrentes(self, numero, top_n=5):
        return self.pares_coocorrentes.get(numero, [])[:top_n]
    
    def get_mapa_calor_probabilidades(self):
        mapa = np.zeros((5, 5))
        for i in range(25):
            row, col = i // 5, i % 5
            mapa[row][col] = self.probabilidades_ewma.get(i+1, 0)
        return mapa

# =====================================================
# MODELO PROFISSIONAL DE VALOR ESPERADO (EV)
# =====================================================

def simular_apostadores_realistas(num_apostas=10000):
    apostas = []
    for _ in range(int(num_apostas * 0.5)):
        base = list(range(1, 16))
        jogo = set(random.sample(base, min(15, len(base))))
        while len(jogo) < 15:
            jogo.add(random.randint(1, 25))
        apostas.append(sorted(jogo))
    for _ in range(int(num_apostas * 0.2)):
        jogo = set()
        linhas = random.sample(range(5), random.randint(2, 3))
        for linha in linhas:
            for col in range(5):
                jogo.add(linha * 5 + col + 1)
        while len(jogo) < 15:
            jogo.add(random.randint(1, 25))
        apostas.append(sorted(jogo))
    for _ in range(int(num_apostas * 0.2)):
        apostas.append(sorted(random.sample(range(1, 26), 15)))
    for _ in range(int(num_apostas * 0.1)):
        jogo = set()
        jogo.update(random.sample(range(1, 32), min(8, 31)))
        while len(jogo) < 15:
            jogo.add(random.randint(1, 25))
        apostas.append(sorted(jogo))
    return apostas

def estimar_divisao_premio(jogo, apostas_simuladas):
    iguais = 0
    similares = 0
    for aposta in apostas_simuladas:
        inter = len(set(jogo) & set(aposta))
        if inter == 15:
            iguais += 1
        elif inter >= 13:
            similares += 1
    competicao = iguais * 1.0 + similares * 0.3
    return competicao

def calcular_ev(jogo, apostas_simuladas, premio_base=1500000):
    competicao = estimar_divisao_premio(jogo, apostas_simuladas)
    premio_esperado = premio_base / (competicao + 1)
    prob = 1 / 3268760
    ev = prob * premio_esperado
    return ev

def penalizar_padroes_humanos(jogo):
    penalty = 0
    consecutivos = contar_consecutivos(jogo)
    if consecutivos > 3:
        penalty += 0.2 * (consecutivos - 3)
    baixos = len([n for n in jogo if n <= 15])
    if baixos > 10:
        penalty += 0.3 * (baixos - 10)
    elif baixos < 5:
        penalty += 0.1
    linhas = [list(range(i*5+1, (i+1)*5+1)) for i in range(5)]
    for linha in linhas:
        if set(linha).issubset(set(jogo)):
            penalty += 0.3
    colunas = [[1,6,11,16,21], [2,7,12,17,22], [3,8,13,18,23], [4,9,14,19,24], [5,10,15,20,25]]
    for coluna in colunas:
        if set(coluna).issubset(set(jogo)):
            penalty += 0.3
    return penalty

def penalizar_repetidas(jogo, ultimo_concurso):
    if not ultimo_concurso:
        return 0
    repetidas = len(set(jogo) & set(ultimo_concurso))
    if repetidas > 9:
        return 0.2 * (repetidas - 9)
    elif repetidas < 6:
        return 0.1
    return 0

def score_final_profissional(jogo, apostas_simuladas, ultimo_concurso=None):
    ev = calcular_ev(jogo, apostas_simuladas)
    penalty_humano = penalizar_padroes_humanos(jogo)
    if ultimo_concurso:
        penalty_rep = penalizar_repetidas(jogo, ultimo_concurso)
    else:
        penalty_rep = 0
    score = ev * (1 - penalty_humano - penalty_rep)
    score_normalizado = score * 1e9
    return score_normalizado, ev

def gerar_jogos_ev_otimizados(apostas_simuladas, qtd_jogos=10, amostragem=5000, ultimo_concurso=None):
    jogos_candidatos = []
    progress_bar = st.progress(0, text=f"Gerando e avaliando {amostragem} jogos...")
    for i in range(amostragem):
        if random.random() < 0.7:
            pares = random.randint(6, 9)
            impares = 15 - pares
            jogo = set()
            jogo.update(random.sample([n for n in range(1, 26) if n % 2 == 0], pares))
            jogo.update(random.sample([n for n in range(1, 26) if n % 2 != 0], impares))
            jogo = sorted(jogo)
        else:
            jogo = sorted(random.sample(range(1, 26), 15))
        score, ev = score_final_profissional(jogo, apostas_simuladas, ultimo_concurso)
        jogos_candidatos.append({'jogo': jogo, 'score': score, 'ev': ev})
        if (i + 1) % 500 == 0:
            progress_bar.progress((i + 1) / amostragem)
    progress_bar.empty()
    jogos_candidatos.sort(key=lambda x: x['score'], reverse=True)
    jogos_unicos = []
    for item in jogos_candidatos:
        if item['jogo'] not in [j['jogo'] for j in jogos_unicos]:
            jogos_unicos.append(item)
    return jogos_unicos[:qtd_jogos]

def analisar_ev_detalhado(jogo, apostas_simuladas, premio_base=1500000):
    competicao = estimar_divisao_premio(jogo, apostas_simuladas)
    premio_esperado = premio_base / (competicao + 1)
    prob = 1 / 3268760
    ev = prob * premio_esperado
    penalty_humano = penalizar_padroes_humanos(jogo)
    return {
        'competidores_diretos': int(competicao),
        'premio_esperado': premio_esperado,
        'probabilidade': prob,
        'ev_bruto': ev,
        'penalidade': penalty_humano,
        'ev_ajustado': ev * (1 - penalty_humano)
    }

# =====================================================
# EMS 8.0 - ILP PROFESSIONAL
# =====================================================

def calcular_pesos_inteligentes(gerador, ultimo_concurso, usar_frequencia=True, usar_atraso=True, usar_ultimo=True):
    pesos = np.zeros(25)
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
    if usar_ultimo and ultimo_concurso is not None:
        if isinstance(ultimo_concurso, (set, list)):
            for num in ultimo_concurso:
                idx = num - 1
                if 0 <= idx < 25:
                    pesos[idx] += 0.2
        elif isinstance(ultimo_concurso, dict) and 'dezenas' in ultimo_concurso:
            for num in ultimo_concurso['dezenas']:
                idx = int(num) - 1
                if 0 <= idx < 25:
                    pesos[idx] += 0.2
    soma_pesos = pesos.sum()
    if soma_pesos > 0:
        pesos = pesos / soma_pesos
    return pesos

def gerar_jogo_ilp_profissional(pesos, ultimo_concurso, config_filtros, solver_timeout=10):
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
    x = {}
    for i in range(NUM_DEZENAS):
        x[i] = solver.IntVar(0, 1, f'x[{i}]')
    objective = solver.Objective()
    for i in range(NUM_DEZENAS):
        objective.SetCoefficient(x[i], pesos[i])
    objective.SetMaximization()
    solver.Add(solver.Sum(x[i] for i in range(NUM_DEZENAS)) == NUM_ESCOLHER)
    pares = [i for i in range(NUM_DEZENAS) if (i+1) % 2 == 0]
    pares_min = config_filtros.get('pares_min', 6)
    pares_max = config_filtros.get('pares_max', 9)
    solver.Add(solver.Sum(x[i] for i in pares) >= pares_min)
    solver.Add(solver.Sum(x[i] for i in pares) <= pares_max)
    if ultimo_concurso:
        if isinstance(ultimo_concurso, (set, list)):
            indices_ultimo = [i for i in range(NUM_DEZENAS) if (i+1) in ultimo_concurso]
        elif isinstance(ultimo_concurso, dict) and 'dezenas' in ultimo_concurso:
            ultimo_set = set(map(int, ultimo_concurso['dezenas']))
            indices_ultimo = [i for i in range(NUM_DEZENAS) if (i+1) in ultimo_set]
        else:
            indices_ultimo = []
        if indices_ultimo:
            rep_min = config_filtros.get('repetidas_min', 7)
            rep_max = config_filtros.get('repetidas_max', 10)
            solver.Add(solver.Sum(x[i] for i in indices_ultimo) >= rep_min)
            solver.Add(solver.Sum(x[i] for i in indices_ultimo) <= rep_max)
    linhas = [range(0,5), range(5,10), range(10,15), range(15,20), range(20,25)]
    linha_min = config_filtros.get('linhas_min_max', [(2,4)]*5)
    for idx, linha in enumerate(linhas):
        min_q = linha_min[idx][0] if idx < len(linha_min) else 2
        max_q = linha_min[idx][1] if idx < len(linha_min) else 4
        solver.Add(solver.Sum(x[i] for i in linha) >= min_q)
        solver.Add(solver.Sum(x[i] for i in linha) <= max_q)
    colunas = [[0,5,10,15,20], [1,6,11,16,21], [2,7,12,17,22], [3,8,13,18,23], [4,9,14,19,24]]
    coluna_min = config_filtros.get('colunas_min_max', [(2,4)]*5)
    for idx, coluna in enumerate(colunas):
        min_q = coluna_min[idx][0] if idx < len(coluna_min) else 2
        max_q = coluna_min[idx][1] if idx < len(coluna_min) else 4
        solver.Add(solver.Sum(x[i] for i in coluna) >= min_q)
        solver.Add(solver.Sum(x[i] for i in coluna) <= max_q)
    soma_min = config_filtros.get('soma_min', 160)
    soma_max = config_filtros.get('soma_max', 240)
    solver.Add(solver.Sum((i+1) * x[i] for i in range(NUM_DEZENAS)) >= soma_min)
    solver.Add(solver.Sum((i+1) * x[i] for i in range(NUM_DEZENAS)) <= soma_max)
    consecutivos_max = config_filtros.get('consecutivos_max', 5)
    for i in range(NUM_DEZENAS - consecutivos_max):
        sequencia = list(range(i, i + consecutivos_max + 1))
        solver.Add(solver.Sum(x[j] for j in sequencia) <= consecutivos_max)
    solver.SetTimeLimit(solver_timeout * 1000)
    status = solver.Solve()
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        jogo = [i+1 for i in range(NUM_DEZENAS) if x[i].solution_value() > 0.5]
        return sorted(jogo), f"Ótimo encontrado (status: {status})"
    else:
        return None, f"Nenhuma solução (status: {status})"

def gerar_multiplos_jogos_ilp(gerador, ultimo_concurso, config_filtros, qtd_jogos=10, timeout_por_jogo=5, usar_diversidade=True):
    if not ORTOOLS_AVAILABLE:
        return []
    jogos = []
    for idx in range(qtd_jogos):
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
    return jogos

# =====================================================
# EMS 3.0 - SCORE + GENÉTICO + FECHAMENTO
# =====================================================

def score_jogo_ems(jogo, dist_emp, motor_geo, ultimo):
    pares = contar_pares(jogo)
    primos = contar_primos(jogo)
    consecutivos = contar_consecutivos(jogo)
    soma = (sum(jogo)//20)*20
    repetidas = len(set(jogo) & set(ultimo))
    features = {"pares": pares, "primos": primos, "consecutivos": consecutivos, "soma": soma}
    logL = log_likelihood(features, dist_emp)
    geo = motor_geo.analisar_jogo(jogo)
    dispersao = geo.get("dispersao_media", 2.2)
    score_geo = 1 / (1 + abs(dispersao - 2.2))
    score_rep = 1 - abs(repetidas - 9)/9
    penalty_cons = max(0, consecutivos - 4) * 0.1
    score = (logL * 0.5 + score_geo * 2.0 + score_rep * 2.0 - penalty_cons + random.random() * 0.2)
    return score

def crossover(j1, j2):
    corte = random.randint(5, 10)
    filho = list(set(j1[:corte] + j2[corte:]))
    while len(filho) < 15:
        n = random.randint(1, 25)
        if n not in filho:
            filho.append(n)
    return sorted(filho[:15])

def mutacao(jogo, taxa=0.2):
    jogo = jogo.copy()
    if random.random() < taxa:
        idx = random.randint(0, 14)
        novo = random.randint(1, 25)
        while novo in jogo:
            novo = random.randint(1, 25)
        jogo[idx] = novo
    return sorted(jogo)

def algoritmo_genetico_ems(gerador, dist_emp, motor_geo, ultimo, config_filtros, populacao_size=80, geracoes=25):
    populacao = gerador.gerar_multiplos_jogos(populacao_size, config_filtros)
    for _ in range(geracoes):
        avaliados = [(j, score_jogo_ems(j, dist_emp, motor_geo, ultimo)) for j in populacao]
        avaliados.sort(key=lambda x: x[1], reverse=True)
        sobreviventes = [j for j, _ in avaliados[:int(populacao_size * 0.3)]]
        nova_pop = sobreviventes.copy()
        while len(nova_pop) < populacao_size:
            p1, p2 = random.sample(sobreviventes, 2)
            filho = mutacao(crossover(p1, p2))
            if gerador.aplicar_filtros(filho, config_filtros):
                nova_pop.append(filho)
        populacao = nova_pop
    final = [(j, score_jogo_ems(j, dist_emp, motor_geo, ultimo)) for j in populacao]
    final.sort(key=lambda x: x[1], reverse=True)
    return final[:20]

def gerar_pool_inteligente(gerador, tamanho=20):
    numeros, pesos = gerador.pool_ponderado
    escolhidos = set()
    while len(escolhidos) < tamanho:
        n = random.choices(numeros, weights=pesos, k=1)[0]
        escolhidos.add(n)
    return sorted(escolhidos)

def gerar_fechamento(pool, qtd_jogos=15):
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

def fechamento_inteligente_ems(gerador, dist_emp, motor_geo, ultimo, config_filtros, qtd_jogos=15):
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
# EMS 5.0 - ENGENHARIA COMBINATÓRIA FORMAL
# =====================================================

def gerar_pool_cirurgico_balanceado(gerador=None, tamanho=20):
    if gerador:
        numeros, pesos = gerador.pool_ponderado
        escolhidos = set()
        for linha in range(5):
            for coluna in range(5):
                num = linha * 5 + coluna + 1
                if len(escolhidos) < tamanho:
                    if random.random() < 0.3:
                        escolhidos.add(num)
        while len(escolhidos) < tamanho:
            n = random.choices(numeros, weights=pesos, k=1)[0]
            escolhidos.add(n)
        pool = sorted(escolhidos)
    else:
        pool = []
        pares = [n for n in range(1, 26) if n % 2 == 0]
        impares = [n for n in range(1, 26) if n % 2 != 0]
        pool.extend(random.sample(pares, tamanho // 2))
        pool.extend(random.sample(impares, tamanho - tamanho // 2))
        pool.sort()
    stats = {
        "pares": len([n for n in pool if n % 2 == 0]),
        "impares": len([n for n in pool if n % 2 != 0]),
        "linhas": [len([n for n in pool if (n-1)//5 == i]) for i in range(5)],
        "colunas": [len([n for n in pool if (n-1)%5 == i]) for i in range(5)]
    }
    return pool, stats

def gerar_base_estrategica(pool, tamanho_base=15):
    base = set(random.sample(pool, tamanho_base))
    return sorted(base)

def gerar_vizinhos_combinatorios(base, pool):
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
    ganho = 0
    for comb in combinations(jogo, 14):
        if comb not in cobertura_set:
            ganho += 1
    return ganho

def fechamento_v5_avancado(pool, limite_jogos=30, usar_pesos=False, gerador=None):
    base = gerar_base_estrategica(pool)
    candidatos = gerar_vizinhos_combinatorios(base, pool)
    if usar_pesos and gerador:
        numeros, pesos = gerador.pool_ponderado
        peso_dict = {num: peso for num, peso in zip(numeros, pesos)}
        def calcular_peso_total(jogo):
            return sum(peso_dict.get(n, 0) for n in jogo)
        candidatos.sort(key=calcular_peso_total, reverse=True)
    else:
        random.shuffle(candidatos)
    cobertura = set()
    jogos_finais = []
    progress_bar = st.progress(0, text="Construindo cobertura combinatória...")
    while len(jogos_finais) < limite_jogos and candidatos:
        melhor_jogo = None
        melhor_ganho = -1
        for jogo in candidatos[:min(500, len(candidatos))]:
            ganho = calcular_cobertura(jogo, cobertura)
            if ganho > melhor_ganho:
                melhor_ganho = ganho
                melhor_jogo = jogo
        if melhor_jogo is None:
            break
        jogos_finais.append(melhor_jogo)
        for comb in combinations(melhor_jogo, 14):
            cobertura.add(comb)
        if melhor_jogo in candidatos:
            candidatos.remove(melhor_jogo)
        progress_bar.progress(min(len(jogos_finais)/limite_jogos, 1.0), 
                            text=f"Cobertura: {len(cobertura)} combinações de 14")
    progress_bar.empty()
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
    todos_jogos = []
    todos_pools = []
    for i in range(num_pools):
        with st.spinner(f"Gerando Pool {i+1}/{num_pools}..."):
            pool, pool_stats = gerar_pool_cirurgico_balanceado(gerador, 20)
            jogos, cobertura_stats = fechamento_v5_avancado(
                pool, limite_jogos=jogos_por_pool, usar_pesos=True, gerador=gerador
            )
            todos_jogos.extend(jogos)
            todos_pools.append({
                "pool": pool, "stats": pool_stats,
                "cobertura": cobertura_stats, "jogos": jogos
            })
    jogos_unicos = []
    for j in todos_jogos:
        if j not in jogos_unicos:
            jogos_unicos.append(j)
    return jogos_unicos, todos_pools

# =====================================================
# IA 7.0 - MOTOR PROFISSIONAL AVANÇADO
# =====================================================

def gerar_jogos_ia_70(qtd_jogos, dados_api, qtd_concursos_base=20):
    try:
        if dados_api is None or len(dados_api) < 10:
            st.error("❌ Nenhum concurso carregado. Clique em 'Carregar concursos' na barra lateral primeiro.")
            return [], None
        dados = dados_api[:min(qtd_concursos_base, len(dados_api))]
        if len(dados) < 10:
            st.warning(f"⚠️ Poucos concursos carregados ({len(dados)}). Mínimo recomendado: 10")
            return [], None
        concursos = []
        for d in dados:
            if isinstance(d['dezenas'], list):
                dezenas = [int(x) for x in d['dezenas']]
            elif isinstance(d['dezenas'], str):
                dezenas = [int(x.strip()) for x in d['dezenas'].split(',')]
            else:
                continue
            concursos.append(sorted(dezenas))
        if not concursos:
            st.error("❌ Não foi possível extrair os números dos concursos.")
            return [], None
        ultimo_concurso = concursos[0]
        freq = {i: 0 for i in range(1, 26)}
        atraso = {i: 0 for i in range(1, 26)}
        total_concursos = len(concursos)
        for idx, concurso in enumerate(concursos):
            peso = (total_concursos - idx) / total_concursos
            for dez in concurso:
                freq[dez] += peso
        for dez in range(1, 26):
            for idx, concurso in enumerate(concursos):
                if dez in concurso:
                    atraso[dez] = idx
                    break
            else:
                atraso[dez] = total_concursos
        score = {}
        max_freq = max(freq.values()) if freq.values() else 1
        max_atraso = max(atraso.values()) if atraso.values() else 1
        for dez in range(1, 26):
            freq_norm = freq[dez] / max_freq
            atraso_norm = atraso[dez] / max_atraso
            score[dez] = (freq_norm * 0.6) + ((1 - atraso_norm) * 0.4)
        ordenados = sorted(score.items(), key=lambda x: x[1], reverse=True)
        base_forte = [d[0] for d in ordenados[:15]]
        base_media = [d[0] for d in ordenados[15:22]]
        base_fraca = [d[0] for d in ordenados[22:]]
        candidatos = []
        for _ in range(qtd_jogos * 15):
            jogo = set()
            jogo.update(random.sample(base_forte, min(8, len(base_forte))))
            jogo.update(random.sample(base_media, min(4, len(base_media))))
            jogo.update(random.sample(base_fraca, min(3, len(base_fraca))))
            qtd_repetidos = random.randint(6, 9)
            repetidos = random.sample(ultimo_concurso, min(qtd_repetidos, len(ultimo_concurso)))
            jogo.update(repetidos)
            while len(jogo) < 15:
                novo = random.randint(1, 25)
                if novo not in jogo:
                    jogo.add(novo)
            jogo = sorted(list(jogo))[:15]
            candidatos.append(jogo)
        def avaliar_jogo_ia(jogo):
            s = 0
            s += sum(score[n] for n in jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)
            if 6 <= pares <= 9: s += 5
            elif pares == 7 or pares == 8: s += 3
            soma = sum(jogo)
            if 180 <= soma <= 220: s += 5
            elif 170 <= soma <= 230: s += 2
            repetidos = len(set(jogo) & set(ultimo_concurso))
            if 6 <= repetidos <= 9: s += 5
            elif repetidos == 7 or repetidos == 8: s += 3
            linhas = distribuir_por_linhas(jogo)
            if max(linhas) <= 4 and min(linhas) >= 2: s += 3
            consec = contar_consecutivos(jogo)
            if consec > 4: s -= consec - 4
            return s
        candidatos = list(set(tuple(j) for j in candidatos))
        candidatos = [list(j) for j in candidatos]
        candidatos.sort(key=avaliar_jogo_ia, reverse=True)
        finais = []
        for jogo in candidatos:
            if len(finais) >= qtd_jogos:
                break
            diferente = True
            for j in finais:
                if len(set(jogo) & set(j)) >= 11:
                    diferente = False
                    break
            if diferente:
                finais.append(jogo)
        if len(finais) < qtd_jogos:
            finais = candidatos[:qtd_jogos]
        concurso_info = (dados[0]['concurso'], dados[0]['data'])
        return finais, concurso_info
    except Exception as e:
        st.error(f"❌ Erro na IA 7.0: {str(e)}")
        return [], None

# =====================================================
# CONFERIDOR INTELIGENTE + OTIMIZADOR
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

def gerar_jogos_otimizados(base_jogos, resultado_set, n_jogos=10, estrategia="inteligente"):
    todos_numeros = set(range(1, 26))
    jogos_novos = []
    freq = analisar_frequencia_jogos(base_jogos)
    numeros_frequentes = set(freq.head(10)["Número"].tolist())
    numeros_raros = set(freq.tail(10)["Número"].tolist())
    for _ in range(n_jogos):
        if estrategia == "inteligente":
            jogo_base = base_jogos[random.randint(0, len(base_jogos) - 1)]
            if isinstance(jogo_base, str):
                base = parse_dezenas(jogo_base)
            else:
                base = set(jogo_base)
            remover_qtd = random.randint(2, 3)
            remover = set(random.sample(list(base), min(remover_qtd, len(base))))
            base -= remover
            if len(resultado_set) > 0:
                novos_do_resultado = list(resultado_set - base)
                if novos_do_resultado:
                    base.add(random.choice(novos_do_resultado))
            if len(base) < 12:
                faltantes = numeros_frequentes - base
                if faltantes:
                    base.add(random.choice(list(faltantes)))
        elif estrategia == "frequencia":
            base = set()
            numeros_prioridade = list(numeros_frequentes) + list(resultado_set)
            while len(base) < 15 and numeros_prioridade:
                n = random.choice(numeros_prioridade)
                base.add(n)
                numeros_prioridade = [x for x in numeros_prioridade if x != n]
        else:
            base = set()
            metade = n_jogos // 2
            base.update(random.sample(list(numeros_frequentes), min(metade, len(numeros_frequentes))))
            base.update(random.sample(list(resultado_set), min(metade, len(resultado_set))))
        while len(base) < 15:
            disponiveis = list(todos_numeros - base)
            if disponiveis:
                base.add(random.choice(disponiveis))
        jogos_novos.append(sorted(base))
    return jogos_novos

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
        return {n: freq.get(n,0)/total for n in range(1,26)} if total > 0 else {n:0 for n in range(1,26)}

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
        max_freq = max(self.frequencias.values()) if self.frequencias else 1
        max_atraso = max(self.atrasos.values()) if self.atrasos else 1
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
# BACKTESTING
# =====================================================
def backtest_estrategia(historico, config_filtros, num_testes=30):
    resultados = []
    for i in range(1, num_testes+1):
        idx_alvo = -i
        if abs(idx_alvo) > len(historico):
            continue
        concurso_alvo = historico[idx_alvo]
        historico_treino = historico[:idx_alvo] if idx_alvo != 0 else []
        if not historico_treino:
            continue
        gerador_teste = GeradorLotofacil(historico_treino, historico_treino[0])
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
    if "apostas_simuladas" not in st.session_state: st.session_state.apostas_simuladas = None
    if "motor_pesos_dinamicos" not in st.session_state: st.session_state.motor_pesos_dinamicos = None
    if "elite_scores" not in st.session_state: st.session_state.elite_scores = []
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
                    st.session_state.apostas_simuladas = simular_apostadores_realistas(10000)
                    st.session_state.motor_pesos_dinamicos = MotorPesosDinamicos(
                        st.session_state.dados_api, qtd
                    )
                    st.success(f"✅ Último concurso: #{st.session_state.dados_api[0]['concurso']} - {st.session_state.dados_api[0]['data']}")
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    if not st.session_state.dados_api:
        st.info("👈 Carregue os concursos na barra lateral para começar.")
        return

    st.subheader("🎯 Análise e Geração de Jogos")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = st.tabs([
        "📊 Análise do Último",
        "🎲 Gerador",
        "🚀 EMS 5.0",
        "🔥 ILP PRO",
        "🤖 IA 7.0",
        "🎲 NASH (EV)",
        "🔍 Conferência",
        "📈 Avaliação",
        "📐 Geometria",
        "✅ Salvos",
        "👑 Regras Ouro",
        "📋 Padrão 3124",
        "🧠 ELITE MASTER 8.0"
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

    # ================= TAB 2: GERADOR DE JOGOS =================
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
                repetidas_min = st.number_input("Mínimo de Repetidas", 0, 15, value=st.session_state.config_filtros['repetidas_min'])
                repetidas_max = st.number_input("Máximo de Repetidas", 0, 15, value=st.session_state.config_filtros['repetidas_max'])
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
                        st.session_state.scores = []
                        st.success(f"✅ {len(jogos)} jogos gerados!")
        with col3:
            if st.button("🔥 EMS 3.0", use_container_width=True):
                with st.spinner("Gerando jogos com Algoritmo Genético..."):
                    dist_emp = distribuicoes_empiricas(st.session_state.historico_df)
                    resultados = algoritmo_genetico_ems(
                        st.session_state.gerador_principal, dist_emp, st.session_state.motor_geometria,
                        st.session_state.gerador_principal.ultimo, st.session_state.config_filtros
                    )
                    st.session_state.jogos_gerados = [r[0] for r in resultados]
                    st.session_state.scores = [r[1] for r in resultados]
                    st.success(f"✅ {len(resultados)} jogos gerados com EMS 3.0!")

        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            jogos = st.session_state.jogos_gerados
            st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
            for i, jogo in enumerate(jogos[:20]):
                score = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🔹"
                nums_html = formatar_jogo_html(jogo)
                stats = f"⚖️ {contar_pares(jogo)}p | ➕ {sum(jogo)} | 🔁 {len(set(jogo) & set(st.session_state.gerador_principal.ultimo))} rep"
                st.markdown(f"""
                <div style='border-left: 5px solid #4cc9f0; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — Score: {round(score,2)}<br>
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
                    "Score": [round(s, 2) for s in st.session_state.scores] if st.session_state.scores else [0]*len(jogos),
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
        st.markdown("""<div class="cover-stats"><strong>🎯 Conceito:</strong> Se os 15 números sorteados estiverem dentro do seu pool, este sistema GARANTE cobertura de combinações de 14 números.</div>""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            tamanho_pool = st.selectbox("Tamanho do Pool", [18, 19, 20], index=2)
        with col2:
            qtd_jogos_v5 = st.slider("Jogos por pool", 10, 40, 25)
        with col3:
            num_pools = st.selectbox("Multi-Pool", [1, 2, 3, 4, 5], index=2, help="Múltiplos pools aumentam a cobertura global")
        
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
                        jogos, cobertura = fechamento_v5_avancado(st.session_state.pool_atual, limite_jogos=qtd_jogos_v5, usar_pesos=True, gerador=st.session_state.gerador_principal)
                        st.session_state.jogos_gerados = jogos
                        st.session_state.cobertura_stats = cobertura
                        st.session_state.scores = []
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
            if st.button("🔁 MULTI-POOL", use_container_width=True):
                with st.spinner(f"Gerando {num_pools} pools com fechamento..."):
                    todos_jogos, pools_info = multi_pool_fechamento(st.session_state.gerador_principal, num_pools=num_pools, jogos_por_pool=qtd_jogos_v5)
                    st.session_state.jogos_gerados = todos_jogos
                    st.session_state.multi_pool_results = pools_info
                    st.session_state.scores = []
                    st.success(f"✅ {len(todos_jogos)} jogos únicos gerados com {num_pools} pools!")
        with col2:
            if st.button("📊 Probabilidade Real", use_container_width=True):
                if "pool_atual" in st.session_state:
                    pool = st.session_state.pool_atual
                    prob_pool_acertar = math.comb(len(pool), 15) / math.comb(25, 15)
                    prob_14_se_pool_acertar = st.session_state.cobertura_stats['percentual_cobertura'] / 100 if st.session_state.cobertura_stats else 0
                    prob_total_14 = prob_pool_acertar * prob_14_se_pool_acertar
                    st.markdown(f"""<div class="cover-stats"><strong>🎲 Análise de Probabilidade Real:</strong><br>• Probabilidade do sorteio cair DENTRO do pool: {prob_pool_acertar:.4%}<br>• Probabilidade de GARANTIR 14 pontos SE cair no pool: {prob_14_se_pool_acertar:.2%}<br>• <strong>Probabilidade TOTAL de 14 pontos garantidos: {prob_total_14:.4%}</strong></div>""", unsafe_allow_html=True)

        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown(f"### 📋 Jogos Gerados ({len(st.session_state.jogos_gerados)})")
            for i, jogo in enumerate(st.session_state.jogos_gerados[:20]):
                st.markdown(f"""<div style='border-left: 5px solid #f97316; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'><strong>Jogo {i+1:2d}</strong><br>{formatar_jogo_html(jogo)}</div>""", unsafe_allow_html=True)
            if st.button("💾 Salvar Jogos EMS 5.0", key="salvar_v5", use_container_width=True):
                ultimo = st.session_state.dados_api[0]
                arquivo, jogo_id = salvar_jogos_gerados(st.session_state.jogos_gerados, [], {"versao": "EMS 5.0", "pool": st.session_state.get("pool_atual", [])}, ultimo['concurso'], ultimo['data'])
                if arquivo:
                    st.success(f"✅ {len(st.session_state.jogos_gerados)} jogos salvos! ID: {jogo_id}")
                    st.session_state.jogos_salvos = carregar_jogos_salvos()

    # ================= TAB 4: ILP PROFESSIONAL =================
    with tab4:
        st.markdown("### 🔥 ILP PROFESSIONAL - Programação Linear Inteira")
        st.markdown("""<div class="ilp-highlight"><strong>🎯 O QUE É ILP:</strong><br>• Transforma a Lotofácil em um problema de otimização combinatória exata<br>• Usa solver profissional (OR-Tools/SCIP) para encontrar a solução ótima<br>• GARANTE que o jogo gerado é o MELHOR POSSÍVEL dentro das restrições!</div>""", unsafe_allow_html=True)
        
        if not ORTOOLS_AVAILABLE:
            st.warning("⚠️ OR-Tools não instalado. Execute: pip install ortools")
        
        with st.expander("⚙️ Configuração das Restrições ILP", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                pares_min_ilp = st.number_input("Mínimo de Pares", 0, 15, value=6, key="ilp_pares_min")
                pares_max_ilp = st.number_input("Máximo de Pares", 0, 15, value=9, key="ilp_pares_max")
                soma_min_ilp = st.number_input("Soma Mínima", 150, 300, value=180, key="ilp_soma_min")
                soma_max_ilp = st.number_input("Soma Máxima", 150, 300, value=210, key="ilp_soma_max")
                repetidas_min_ilp = st.number_input("Mínimo de Repetidas", 0, 15, value=7, key="ilp_rep_min")
                repetidas_max_ilp = st.number_input("Máximo de Repetidas", 0, 15, value=10, key="ilp_rep_max")
            with col2:
                consecutivos_max_ilp = st.number_input("Máximo de Consecutivos", 0, 10, value=5, key="ilp_cons_max")
                linha_min_ilp = st.number_input("Mínimo por Linha", 0, 5, value=2, key="ilp_linha_min")
                linha_max_ilp = st.number_input("Máximo por Linha", 0, 5, value=4, key="ilp_linha_max")
                coluna_min_ilp = st.number_input("Mínimo por Coluna", 0, 5, value=2, key="ilp_coluna_min")
                coluna_max_ilp = st.number_input("Máximo por Coluna", 0, 5, value=4, key="ilp_coluna_max")
            config_ilp = {
                'pares_min': pares_min_ilp, 'pares_max': pares_max_ilp,
                'soma_min': soma_min_ilp, 'soma_max': soma_max_ilp,
                'repetidas_min': repetidas_min_ilp, 'repetidas_max': repetidas_max_ilp,
                'consecutivos_max': consecutivos_max_ilp,
                'linhas_min_max': [(linha_min_ilp, linha_max_ilp)] * 5,
                'colunas_min_max': [(coluna_min_ilp, coluna_max_ilp)] * 5
            }
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_ilp = st.slider("Quantidade de jogos", 1, 15, 5, key="qtd_ilp")
        with col2:
            timeout = st.slider("Timeout por jogo (segundos)", 2, 20, 8, key="timeout_ilp")
        
        if st.button("🚀 GERAR JOGO ÓTIMO VIA ILP", use_container_width=True, type="primary"):
            if not ORTOOLS_AVAILABLE:
                st.error("OR-Tools não disponível.")
            else:
                ultimo_concurso = st.session_state.dados_api[0]
                pesos = calcular_pesos_inteligentes(st.session_state.gerador_principal, ultimo_concurso, True, True, True)
                with st.spinner("Resolvendo problema de otimização combinatória..."):
                    jogo, status = gerar_jogo_ilp_profissional(pesos, ultimo_concurso, config_ilp, timeout)
                    if jogo:
                        st.session_state.jogos_gerados = [jogo]
                        mc = monte_carlo_jogo(tuple(jogo), 2000)
                        st.session_state.scores = [mc['P>=13'] * 100]
                        st.success("✅ Jogo ótimo encontrado!")
                        st.markdown(f"""<div class="ilp-highlight"><strong>🎲 Jogo Gerado:</strong> {formatar_jogo_html(jogo)}<br><strong>📊 P(13+):</strong> {mc['P>=13']*100:.2f}%<br><strong>🔧 Status Solver:</strong> {status}</div>""", unsafe_allow_html=True)
        if st.button("🎲 GERAR MÚLTIPLOS JOGOS ILP", use_container_width=True):
            if not ORTOOLS_AVAILABLE:
                st.error("OR-Tools não disponível.")
            else:
                ultimo_concurso = st.session_state.dados_api[0]
                jogos = gerar_multiplos_jogos_ilp(st.session_state.gerador_principal, ultimo_concurso, config_ilp, qtd_jogos=qtd_ilp, timeout_por_jogo=timeout, usar_diversidade=True)
                if jogos:
                    st.session_state.jogos_gerados = jogos
                    st.session_state.scores = [monte_carlo_jogo(tuple(j), 2000)['P>=13'] * 100 for j in jogos]
                    st.success(f"✅ {len(jogos)} jogos gerados via ILP!")

    # ================= TAB 5: IA 7.0 =================
    with tab5:
        st.markdown("### 🤖 IA 7.0 - Motor Profissional Avançado")
        st.markdown("""<div class="ia7-highlight"><strong>🎯 COMO FUNCIONA:</strong><br>• Ranking Inteligente por frequência ponderada + atraso<br>• Geração Estratificada das categorias forte/média/fraca<br>• Diversificação Controlada entre jogos<br>• Balanceamento Automático de paridade, soma, repetições</div>""", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            qtd_ia = st.slider("Quantidade de jogos", 5, 50, 15, key="qtd_ia")
        with col2:
            qtd_concursos_base = st.slider("Concursos para análise", 10, 50, 20)
        if st.button("🤖 GERAR COM IA 7.0", use_container_width=True, type="primary"):
            with st.spinner(f"IA 7.0 gerando {qtd_ia} jogos otimizados..."):
                jogos, concurso_info = gerar_jogos_ia_70(qtd_ia, st.session_state.dados_api, qtd_concursos_base)
                if jogos:
                    st.session_state.jogos_gerados = jogos
                    scores_calculados = []
                    for jogo in jogos:
                        pares = contar_pares(jogo)
                        soma = sum(jogo)
                        repetidas = len(set(jogo) & set(st.session_state.gerador_principal.ultimo))
                        consec = contar_consecutivos(jogo)
                        score = 0
                        if 6 <= pares <= 9: score += 2
                        if 180 <= soma <= 220: score += 2
                        if 6 <= repetidas <= 9: score += 2
                        if consec <= 4: score += 1
                        scores_calculados.append(score)
                    st.session_state.scores = scores_calculados
                    st.success(f"✅ {len(jogos)} jogos gerados com IA 7.0!")
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            jogos = st.session_state.jogos_gerados
            st.markdown(f"### 📋 Jogos Gerados pela IA 7.0 ({len(jogos)})")
            for i, jogo in enumerate(jogos[:20]):
                score = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "🤖"
                stats = f"⚖️ {contar_pares(jogo)}p/{15-contar_pares(jogo)}i | ➕ {sum(jogo)} | 🔁 {len(set(jogo) & set(st.session_state.gerador_principal.ultimo))} rep"
                st.markdown(f"""<div style='border-left: 5px solid #ff8800; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>{medalha} <strong>Jogo {i+1:2d}</strong> — Score IA: {score}/7<br>{formatar_jogo_html(jogo)}<br><small style='color:#aaa;'>{stats}</small></div>""", unsafe_allow_html=True)

    # ================= TAB 6: TEORIA DE NASH (EV) =================
    with tab6:
        st.markdown("### 🎲 Teoria de Nash - Maximização do Valor Esperado (EV)")
        st.markdown("""<div class="ev-highlight"><strong>📈 VALOR ESPERADO (EV):</strong> EV = Probabilidade × Prêmio esperado<br>A probabilidade é fixa (1/3.268.760), então o foco é MAXIMIZAR O PRÊMIO quando acertar!<br>✅ Evita padrões que todo mundo joga<br>✅ Busca números "esquecidos"</div>""", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            qtd_ev = st.slider("Quantidade de jogos", 5, 30, 10, key="qtd_ev")
        with col2:
            amostragem_ev = st.slider("Amostragem de jogos", 1000, 20000, 5000, key="amostragem_ev")
        if st.button("🎯 OTIMIZAR POR VALOR ESPERADO", use_container_width=True, type="primary"):
            with st.spinner(f"Analisando {amostragem_ev} jogos e calculando EV..."):
                ultimo_concurso = st.session_state.gerador_principal.ultimo if st.session_state.gerador_principal else None
                top_jogos = gerar_jogos_ev_otimizados(st.session_state.apostas_simuladas, qtd_jogos=qtd_ev, amostragem=amostragem_ev, ultimo_concurso=ultimo_concurso)
                if top_jogos:
                    st.session_state.jogos_gerados = [item['jogo'] for item in top_jogos]
                    st.session_state.scores = [item['score'] for item in top_jogos]
                    st.session_state.ev_detalhes = [analisar_ev_detalhado(item['jogo'], st.session_state.apostas_simuladas) for item in top_jogos]
                    st.success(f"✅ {len(top_jogos)} jogos otimizados por Valor Esperado!")
                    st.markdown(f"### 📋 TOP {len(top_jogos)} Jogos por Valor Esperado")
                    for i, item in enumerate(top_jogos):
                        jogo = item['jogo']
                        medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                        stats = f"⚖️ {contar_pares(jogo)}p | ➕ {sum(jogo)}"
                        st.markdown(f"""<div style='border-left: 5px solid #00ff88; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>{medalha} <strong>Jogo {i+1:2d}</strong> — EV Score: {item['score']:.2f}<br>{formatar_jogo_html(jogo)}<br><small style='color:#aaa;'>{stats}</small></div>""", unsafe_allow_html=True)

    # ================= TAB 7: CONFERÊNCIA INTELIGENTE =================
    with tab7:
        st.markdown("### 🔍 Conferência Inteligente de Jogos")
        concurso_resultado = st.selectbox("Selecione o concurso para conferência", st.session_state.dados_api, format_func=lambda c: f"#{c['concurso']} - {c['data']}", key="conferencia_resultado")
        if concurso_resultado:
            resultado_oficial = set(map(int, concurso_resultado["dezenas"]))
            st.markdown(f"""<div class="highlight"><strong>🎯 Resultado #{concurso_resultado['concurso']}:</strong><br>{formatar_jogo_html(sorted(resultado_oficial))}</div>""", unsafe_allow_html=True)
        opcao_jogos = st.radio("Origem dos jogos:", ["Jogos gerados na sessão atual", "Carregar de arquivo CSV", "Digitar manualmente"], horizontal=True)
        jogos_para_conferir = []
        if opcao_jogos == "Jogos gerados na sessão atual":
            if st.session_state.jogos_gerados:
                jogos_para_conferir = st.session_state.jogos_gerados
                st.info(f"{len(jogos_para_conferir)} jogos carregados da sessão atual")
        elif opcao_jogos == "Carregar de arquivo CSV":
            uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
            if uploaded_file:
                df_carregado = pd.read_csv(uploaded_file)
                if "Dezenas" in df_carregado.columns:
                    jogos_para_conferir = df_carregado["Dezenas"].tolist()
        else:
            jogos_texto = st.text_area("Digite os jogos (um por linha, números separados por vírgula)", placeholder="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15")
            if jogos_texto:
                for linha in jogos_texto.strip().split('\n'):
                    if linha.strip():
                        try:
                            dezenas = [int(n.strip()) for n in linha.split(',')]
                            if len(dezenas) == 15 and all(1 <= n <= 25 for n in dezenas):
                                jogos_para_conferir.append(sorted(dezenas))
                        except:
                            pass
        if jogos_para_conferir and concurso_resultado:
            if st.button("🔍 CONFERIR JOGOS", use_container_width=True, type="primary"):
                df_conferencia = conferir_jogos_inteligente(jogos_para_conferir, resultado_oficial)
                st.markdown("### 📊 Resultados da Conferência")
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Total Jogos", len(df_conferencia))
                with col2: st.metric("Melhor Acerto", df_conferencia.iloc[0]["Acertos"])
                with col3: st.metric("Média Acertos", round(df_conferencia["Acertos"].mean(), 1))
                with col4: st.metric("Jogos com 11+", len(df_conferencia[df_conferencia["Acertos"] >= 11]))
                for i, row in df_conferencia.head(20).iterrows():
                    medalha = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    st.markdown(f"""<div style='border-left: 5px solid {"#ffd700" if i == 0 else "#c0c0c0" if i == 1 else "#cd7f32" if i == 2 else "#4cc9f0"}; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>{medalha} <strong>Jogo {row['Jogo']}</strong> — <span style='color:#00ffaa;'>{row['Acertos']} acertos</span><br>{formatar_jogo_html(row['Dezenas'])}</div>""", unsafe_allow_html=True)

    # ================= TAB 8: AVALIAÇÃO ESTATÍSTICA =================
    with tab8:
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
                features = {"pares": contar_pares(jogo), "primos": contar_primos(jogo), "consecutivos": contar_consecutivos(jogo), "soma": (sum(jogo)//20)*20}
                logL = log_likelihood(features, dist_emp)
                score_ems = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                avaliacao.append({"Jogo": i+1, "Log-Likelihood": round(logL, 4), "Score EMS": round(score_ems, 2)})
            df_avaliacao = pd.DataFrame(avaliacao)
            st.dataframe(df_avaliacao.sort_values("Score EMS", ascending=False).reset_index(drop=True), use_container_width=True, hide_index=True)
        st.markdown("### 🎲 Simulação Monte Carlo")
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            n_sim = st.slider("Simulações por jogo", 1000, 50000, 10000, key="mc_sim")
            if st.button("Executar Monte Carlo"):
                with st.spinner(f"Simulando {n_sim} sorteios..."):
                    mc_res = []
                    for i, jogo in enumerate(st.session_state.jogos_gerados[:10]):
                        res = monte_carlo_jogo(tuple(jogo), n_sim)
                        mc_res.append({"Jogo": i+1, "P(≥11)": f"{res['P>=11']*100:.2f}%", "P(≥12)": f"{res['P>=12']*100:.2f}%", "P(≥13)": f"{res['P>=13']*100:.2f}%"})
                    st.session_state.mc_resultados = pd.DataFrame(mc_res)
            if st.session_state.mc_resultados is not None:
                st.dataframe(st.session_state.mc_resultados, use_container_width=True, hide_index=True)

    # ================= TAB 9: GEOMETRIA DO VOLANTE =================
    with tab9:
        st.markdown("### 📐 Geometria Analítica do Volante 5x5")
        motor_geo = st.session_state.motor_geometria
        stats_geo = motor_geo.get_estatisticas_geometricas()
        col1, col2 = st.columns(2)
        with col1: st.metric("Centroide Médio Histórico", f"({stats_geo['centroide_medio'][0]}, {stats_geo['centroide_medio'][1]})")
        with col2: st.metric("Dispersão Média Histórica", stats_geo['dispersao_media'])
        st.markdown("### 🔗 Pares Fortes (Co-ocorrência)")
        num_consulta = st.number_input("Número base", 1, 25, 13)
        pares = motor_geo.get_pares_recomendados(num_consulta, 8)
        if pares:
            st.markdown(f"**Números mais relacionados ao {num_consulta:02d}:**")
            st.markdown(" ".join(f"<span style='border:1px solid #00ffaa; border-radius:15px; padding:3px 8px; margin:2px;'>{p[0]:02d} ({p[1]})</span>" for p in pares), unsafe_allow_html=True)
        st.markdown("### 📊 Analisar um Jogo")
        jogo_input = st.text_input("Digite 15 números separados por vírgula", "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15")
        if jogo_input:
            try:
                numeros = [int(n.strip()) for n in jogo_input.split(",")]
                if len(numeros) == 15 and len(set(numeros)) == 15 and all(1 <= n <= 25 for n in numeros):
                    analise = motor_geo.analisar_jogo(numeros)
                    col1, col2, col3 = st.columns(3)
                    with col1: st.metric("Centroide", f"({analise['centroide'][0]}, {analise['centroide'][1]})")
                    with col2: st.metric("Dispersão Média", analise['dispersao_media'])
                    with col3: st.metric("Pares Adjacentes", analise['pares_adjacentes'])
            except:
                st.error("Formato inválido.")

    # ================= TAB 10: CONFERÊNCIA SALVOS =================
    with tab10:
        st.markdown("### ✅ Conferência de Jogos Salvos")
        st.session_state.jogos_salvos = carregar_jogos_salvos()
        if not st.session_state.jogos_salvos:
            st.warning("Nenhum jogo salvo encontrado.")
        else:
            opcoes = [f"ID {j['id']} | Concurso #{j['concurso_base']['numero']} | {j['data_geracao'][:19]}" for j in st.session_state.jogos_salvos]
            idx = st.selectbox("Selecione o fechamento", range(len(opcoes)), format_func=lambda i: opcoes[i])
            fechamento = st.session_state.jogos_salvos[idx]
            jogos = garantir_jogos_como_listas(fechamento["jogos"])
            concurso_escolhido = st.selectbox("Selecione o concurso", st.session_state.dados_api, format_func=lambda c: f"#{c['concurso']} - {c['data']}")
            dezenas_sorteadas = set(map(int, concurso_escolhido["dezenas"]))
            if st.button("🔍 CONFERIR", use_container_width=True):
                resultados = []
                for i, jogo in enumerate(jogos):
                    acertos = len(set(jogo) & dezenas_sorteadas)
                    resultados.append({"Jogo": i+1, "Acertos": acertos})
                df_resultado = pd.DataFrame(resultados).sort_values("Acertos", ascending=False)
                st.dataframe(df_resultado, use_container_width=True, hide_index=True)

    # ================= TAB 11: REGRAS DE OURO =================
    with tab11:
        st.markdown("### 👑 Regras de Ouro - Baseado nos Slides Estratégicos")
        with st.expander("📜 Visualizar Regras de Ouro", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Regra #1: Bordas Iniciais**\n`P1 ∈ {01, 02, 03, 04}`")
                st.markdown("**Regra #2: Ancoragem Final**\n`P15 ∈ {22, 23, 24, 25}`")
            with col2:
                st.markdown("**Regra #3: Morte das Sequências**\n`Consecutivos ≤ 4`")
                st.markdown("**Regra #4: Centro Gravitacional**\n`P08 ∈ {12, 13, 14}`")
            with col3:
                st.markdown("**Regra #5: Navegando o Caos**\n`P07, P08, P09 ∈ {11, 12, 13, 14, 15}`")
                st.markdown("**Filtro Global: Soma**\n`180 ≤ Soma ≤ 210`")
        col1, col2 = st.columns(2)
        with col1:
            qtd_jogos_ouro = st.slider("Quantidade de Jogos", 1, 30, 10, key="qtd_ouro")
        with col2:
            usar_pesos = st.checkbox("Usar pesos estatísticos", value=True)
        if st.button("👑 GERAR JOGOS PELAS REGRAS DE OURO", use_container_width=True, type="primary"):
            if not st.session_state.gerador_principal:
                st.error("Carregue os concursos primeiro!")
            else:
                with st.spinner(f"Aplicando tática posicional para gerar {qtd_jogos_ouro} jogos..."):
                    numeros_pool = list(range(1, 26))
                    pesos_pool = None
                    if usar_pesos:
                        numeros_pool, pesos_pool = st.session_state.gerador_principal.pool_ponderado
                    jogos_gerados_ouro = []
                    tentativas = 0
                    max_tentativas = qtd_jogos_ouro * 1000
                    while len(jogos_gerados_ouro) < qtd_jogos_ouro and tentativas < max_tentativas:
                        tentativas += 1
                        if usar_pesos and pesos_pool is not None and np.sum(pesos_pool) > 0:
                            jogo = sorted(np.random.choice(numeros_pool, size=15, replace=False, p=pesos_pool))
                        else:
                            jogo = sorted(random.sample(numeros_pool, 15))
                        if jogo[0] not in [1, 2, 3, 4]: continue
                        if jogo[14] not in [22, 23, 24, 25]: continue
                        max_consec = 1
                        current_consec = 1
                        for i in range(1, len(jogo)):
                            if jogo[i] == jogo[i-1] + 1:
                                current_consec += 1
                                max_consec = max(max_consec, current_consec)
                            else:
                                current_consec = 1
                        if max_consec > 4: continue
                        if jogo[7] not in [12, 13, 14]: continue
                        zona_caos_set = {11, 12, 13, 14, 15}
                        if not (jogo[6] in zona_caos_set and jogo[7] in zona_caos_set and jogo[8] in zona_caos_set): continue
                        if not (180 <= sum(jogo) <= 210): continue
                        if jogo not in jogos_gerados_ouro:
                            jogos_gerados_ouro.append(jogo)
                    if jogos_gerados_ouro:
                        st.session_state.jogos_gerados = jogos_gerados_ouro
                        st.session_state.scores = []
                        st.success(f"✅ {len(jogos_gerados_ouro)} jogos gerados!")
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            is_ouro_style = (st.session_state.jogos_gerados[0][0] in [1,2,3,4] and st.session_state.jogos_gerados[0][14] in [22,23,24,25])
            if is_ouro_style:
                st.markdown(f"### 📋 Jogos Táticos ({len(st.session_state.jogos_gerados)})")
                for i, jogo in enumerate(st.session_state.jogos_gerados[:15]):
                    nums_html = ""
                    for idx, num in enumerate(jogo):
                        if idx == 0:
                            nums_html += f"<span style='background:#4cc9f040; border:2px solid #4cc9f0; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
                        elif idx in [6, 7, 8]:
                            nums_html += f"<span style='background:#ff880040; border:2px solid #ff8800; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
                        elif idx == 14:
                            nums_html += f"<span style='background:#00ff8840; border:2px solid #00ff88; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
                        else:
                            nums_html += f"<span style='background:#0e1117; border:1px solid #262730; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
                    st.markdown(f"""<div style='border-left: 5px solid gold; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'><strong>Jogo {i+1:2d}</strong><br>{nums_html}</div>""", unsafe_allow_html=True)

    # ================= TAB 12: PADRÃO 3124 =================
    with tab12:
        st.markdown("### 📋 REGRAS DE OURO AVANÇADO - Padrão Concurso 3124")
        st.markdown("""<div class="img-analysis-highlight"><strong>🎯 PADRÃO 3124:</strong><br>• Soma: 140-200 | Paridade: 7-8 pares | Consecutivos ≤ 2<br>• Saltos (Atrasos): 10-12 números com salto 3-5<br>• Distribuição Dezenas: 3-4-2-3-3 | Quadrante inf. esquerdo dominante<br>• 7 primos | Baixo risco</div>""", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            qtd_jogos_img = st.slider("Quantidade de Jogos", 5, 50, 15, key="qtd_img")
        with col2:
            st.markdown("**Filtros Ativos:** ✅ Soma: 140-200 | ✅ Paridade: 7-8 pares | ✅ Consecutivos ≤ 2 | ✅ 7 primos")
        if st.button("🎲 GERAR JOGOS PADRÃO 3124", use_container_width=True, type="primary"):
            if not st.session_state.gerador_principal:
                st.error("Carregue os concursos primeiro!")
            else:
                with st.spinner(f"Analisando padrões do Concurso 3124..."):
                    concursos = st.session_state.gerador_principal.historico
                    candidatos = []
                    tentativas = 0
                    max_tentativas = qtd_jogos_img * 2000
                    while len(candidatos) < qtd_jogos_img and tentativas < max_tentativas:
                        tentativas += 1
                        jogo = sorted(random.sample(range(1, 26), 15))
                        soma = sum(jogo)
                        if not (140 <= soma <= 200): continue
                        pares = contar_pares(jogo)
                        if pares not in [7, 8]: continue
                        pares_consecutivos = sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)
                        if pares_consecutivos > 2: continue
                        primos = contar_primos(jogo)
                        if primos != 7: continue
                        dezenas_dist = [0]*5
                        for num in jogo:
                            dezenas_dist[(num-1)//5] += 1
                        padrao_ideal = [3, 4, 2, 3, 3]
                        diff = sum(abs(dezenas_dist[i] - padrao_ideal[i]) for i in range(5))
                        if diff > 3: continue
                        quadrante_inf_esq = {16, 17, 21, 22}
                        outros_sup = {1,2,3,4,5,6,7,8,9,10}
                        count_inf = len(set(jogo) & quadrante_inf_esq)
                        count_sup = len(set(jogo) & outros_sup)
                        if count_inf < 2 or count_inf <= count_sup: continue
                        if jogo not in candidatos:
                            candidatos.append(jogo)
                    if candidatos:
                        st.session_state.jogos_gerados = candidatos
                        scores_img = []
                        for jogo in candidatos:
                            score = 0
                            if 150 <= sum(jogo) <= 180: score += 3
                            elif 140 <= sum(jogo) <= 200: score += 1
                            if contar_pares(jogo) in [7, 8]: score += 2
                            if contar_primos(jogo) == 7: score += 2
                            scores_img.append(score)
                        st.session_state.scores = scores_img
                        st.success(f"✅ {len(candidatos)} jogos gerados!")
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            jogos = st.session_state.jogos_gerados
            st.markdown(f"### 📋 Jogos Gerados - Padrão 3124 ({len(jogos)})")
            for i, jogo in enumerate(jogos[:20]):
                score = st.session_state.scores[i] if i < len(st.session_state.scores) else 0
                medalha = ["🥇","🥈","🥉"][i] if i < 3 else "📋"
                stats = f"⚖️ {contar_pares(jogo)}p | ➕ {sum(jogo)} | 🔢 {contar_primos(jogo)} primos"
                st.markdown(f"""<div style='border-left: 5px solid #ffd700; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>{medalha} <strong>Jogo {i+1:2d}</strong> — Score: {score}/10<br>{formatar_jogo_html(jogo)}<br><small style='color:#aaa;'>{stats}</small></div>""", unsafe_allow_html=True)

    # ================= TAB 13: ELITE MASTER 8.0 =================
    with tab13:
        st.markdown("### 🧠 ELITE MASTER 8.0 - Motor de Pesos Dinâmicos")
        st.markdown("""<div class="elite-master-highlight"><strong>🎯 ARQUITETURA:</strong><br>• EWMA: Concursos recentes têm peso 3x maior<br>• Análise de Co-ocorrência: Clusters de números<br>• Amostragem Ponderada: Números com melhor comportamento<br>• Score de Elite (0-8): Pares, primos, soma, moldura<br>• Filtro de Entropia: Elimina padrões "bonitos"<br>• Pontuação de Nash: Evita divisão de prêmio</div>""", unsafe_allow_html=True)
        
        if st.session_state.motor_pesos_dinamicos is None:
            st.warning("⚠️ Carregue os concursos primeiro na barra lateral!")
        else:
            motor = st.session_state.motor_pesos_dinamicos
            
            with st.expander("⚙️ Configuração dos Pesos", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    peso_ewma = st.slider("Peso EWMA (Recência)", 0.0, 1.0, 0.7, 0.05, help="Prioriza concursos recentes")
                with col2:
                    peso_atraso = st.slider("Peso do Atraso", 0.0, 1.0, 0.3, 0.05, help="Prioriza números atrasados")
                with col3:
                    score_minimo = st.slider("Score Mínimo", 0, 8, 7, help="Filtro de qualidade")
            
            col1, col2 = st.columns(2)
            with col1:
                qtd_elite = st.slider("Quantidade de Jogos", 1, 50, 10, key="qtd_elite")
            with col2:
                filtro_rigido = st.checkbox("Filtro de Elite", value=True)
            
            if st.button("🧠 GERAR JOGOS ELITE MASTER", use_container_width=True, type="primary"):
                with st.spinner(f"Motor de Pesos Dinâmicos processando {qtd_elite} jogos..."):
                    jogos, scores_info, tentativas = motor.gerar_jogos_elite(
                        qtd_jogos=qtd_elite, peso_ewma=peso_ewma, peso_atraso=peso_atraso,
                        filtro_rigido=filtro_rigido, score_minimo=score_minimo, max_tentativas=10000
                    )
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.session_state.elite_scores = scores_info
                        st.session_state.scores = [s["score_ajustado"] for s in scores_info]
                        st.success(f"✅ {len(jogos)} jogos de elite gerados em {tentativas} simulações!")
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Score Médio", f"{np.mean([s['score'] for s in scores_info]):.1f}/8")
                        with col_b:
                            st.metric("Penalidade Nash Média", f"{np.mean([s['penalty_nash'] for s in scores_info]):.2f}")
                        with col_c:
                            st.metric("Taxa de Aceitação", f"{len(jogos)/tentativas*100:.1f}%")
            
            st.markdown("### 📊 Mapa de Calor - Probabilidades EWMA")
            mapa = motor.get_mapa_calor_probabilidades()
            df_mapa = pd.DataFrame(mapa, columns=[1,2,3,4,5], index=[1,2,3,4,5])
            st.dataframe(df_mapa.style.background_gradient(cmap='YlOrRd', axis=None), use_container_width=True)
            st.caption("🔴 Tons mais escuros = Maior probabilidade de saída")
            
            st.markdown("### 🔗 Análise de Co-ocorrência")
            num_consulta_elite = st.number_input("Consultar pares do número:", 1, 25, 13, key="cooc_elite")
            pares_cooc = motor.get_top_pares_coocorrentes(num_consulta_elite, 8)
            if pares_cooc:
                pares_html = " ".join(f"<span style='background:#ff880020; border:1px solid #ff8800; border-radius:15px; padding:5px 10px; margin:2px; display:inline-block;'>{n:02d} ({c}x)</span>" for n, c in pares_cooc)
                st.markdown(f"**Números que mais saem com {num_consulta_elite:02d}:**")
                st.markdown(pares_html, unsafe_allow_html=True)
            
            if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados and "elite_scores" in st.session_state:
                jogos = st.session_state.jogos_gerados
                scores_info = st.session_state.elite_scores
                st.markdown(f"### 📋 Jogos Elite Master ({len(jogos)})")
                for i, (jogo, info) in enumerate(zip(jogos[:20], scores_info[:20])):
                    score = info["score"]
                    score_ajustado = info["score_ajustado"]
                    stats = info["stats"]
                    medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    score_details = f"⚖️ {stats['pares']}p | 🔢 {stats['primos']} primos | 🔁 {stats['repetidos']} rep | ➕ {stats['soma']}"
                    penalty_details = f"🧹 Entropia: {info['penalty_entropia']:.2f} | 💰 Nash: {info['penalty_nash']:.2f}"
                    st.markdown(f"""<div style='border-left: 5px solid #ff8800; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>{medalha} <strong>Jogo {i+1:2d}</strong> — Score: {score}/8 | Ajustado: {score_ajustado:.2f}<br>{formatar_jogo_html(jogo)}<br><small style='color:#aaa;'>{score_details}</small><br><small style='color:#ff8800;'>{penalty_details}</small></div>""", unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Salvar Jogos Elite", key="salvar_elite", use_container_width=True):
                        ultimo = st.session_state.dados_api[0]
                        arquivo, jogo_id = salvar_jogos_gerados(jogos, [], {"versao": "Elite Master 8.0"}, ultimo['concurso'], ultimo['data'])
                        if arquivo:
                            st.success(f"✅ {len(jogos)} jogos salvos! ID: {jogo_id}")
                with col2:
                    df_export = pd.DataFrame({
                        "Jogo": range(1, len(jogos)+1),
                        "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                        "Score": [s["score"] for s in scores_info],
                        "Score_Ajustado": [round(s["score_ajustado"], 2) for s in scores_info],
                        "Pares": [s["stats"]["pares"] for s in scores_info],
                        "Soma": [s["stats"]["soma"] for s in scores_info]
                    })
                    st.download_button(label="📥 Exportar CSV", data=df_export.to_csv(index=False), file_name=f"elite_master_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)

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
