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
# MOTOR LOTOFÁCIL PRO (6 CAMADAS)
# =====================================================

class MotorLotofacilPro:
    def __init__(self, dados_historicos, ultimo_concurso=None):
        self.historico = dados_historicos
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        
        self.volante = np.array([
            [1, 2, 3, 4, 5],
            [6, 7, 8, 9, 10],
            [11, 12, 13, 14, 15],
            [16, 17, 18, 19, 20],
            [21, 22, 23, 24, 25]
        ])
        
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        self.baixos = list(range(1, 13))
        self.altos = list(range(13, 26))
        
        self.frequencias = self._calcular_frequencias()
        self.quentes, self.mornos, self.frios = self._classificar_frequencias()
        self.atrasos = self._calcular_atrasos()
        self.atrasados = self._get_top_atrasados(5)
        self.padroes_geometricos = self._detectar_padroes_geometricos()
        self.padroes_estatisticos = self._calcular_padroes_estatisticos()
    
    def _calcular_frequencias(self):
        counter = Counter()
        for concurso in self.historico:
            counter.update(concurso)
        total = len(self.historico) * 15
        return {num: count/total for num, count in counter.items()}
    
    def _classificar_frequencias(self, percentis=(0.33, 0.66)):
        valores = sorted(self.frequencias.values())
        n = len(valores)
        limiar_frio = valores[int(n * percentis[0])]
        limiar_quente = valores[int(n * percentis[1])]
        quentes = [n for n, f in self.frequencias.items() if f >= limiar_quente]
        frios = [n for n, f in self.frequencias.items() if f <= limiar_frio]
        mornos = [n for n in range(1, 26) if n not in quentes + frios]
        return quentes, mornos, frios
    
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
    
    def _get_top_atrasados(self, n=5):
        return sorted(self.atrasos.items(), key=lambda x: x[1], reverse=True)[:n]
    
    def _coordenadas(self, numero):
        linha = (numero - 1) // 5
        coluna = (numero - 1) % 5
        return linha, coluna
    
    def _detectar_padroes_geometricos(self):
        padroes = {'diagonal_principal': 0, 'diagonal_secundaria': 0, 'cruz': 0, 'quadrantes': {1: 0, 2: 0, 3: 0, 4: 0}}
        for concurso in self.historico:
            diag_principal = {1, 7, 13, 19, 25}
            if len(set(concurso) & diag_principal) >= 3:
                padroes['diagonal_principal'] += 1
            diag_secundaria = {5, 9, 13, 17, 21}
            if len(set(concurso) & diag_secundaria) >= 3:
                padroes['diagonal_secundaria'] += 1
            cruz = {3, 11, 13, 15, 23}
            if len(set(concurso) & cruz) >= 3:
                padroes['cruz'] += 1
            for num in concurso:
                linha, coluna = self._coordenadas(num)
                if linha < 2.5 and coluna < 2.5:
                    padroes['quadrantes'][1] += 1
                elif linha < 2.5 and coluna >= 2.5:
                    padroes['quadrantes'][2] += 1
                elif linha >= 2.5 and coluna < 2.5:
                    padroes['quadrantes'][3] += 1
                else:
                    padroes['quadrantes'][4] += 1
        total = len(self.historico) * 15
        for q in padroes['quadrantes']:
            padroes['quadrantes'][q] /= total
        return padroes
    
    def _calcular_padroes_estatisticos(self):
        pares_count, baixos_count, soma_total = [], [], []
        for concurso in self.historico:
            pares_count.append(sum(1 for n in concurso if n % 2 == 0))
            baixos_count.append(sum(1 for n in concurso if n <= 12))
            soma_total.append(sum(concurso))
        return {
            'pares': {'media': np.mean(pares_count), 'dist': Counter(pares_count)},
            'baixos': {'media': np.mean(baixos_count), 'dist': Counter(baixos_count)},
            'soma': {'media': np.mean(soma_total), 'min': np.min(soma_total), 'max': np.max(soma_total), 'intervalo': (170, 210)}
        }
    
    def _verificar_filtros_matematicos(self, jogo):
        diag = {'sequencia_max': 0, 'repeticao_anterior': 0, 'distribuicao_linhas': {}, 'aprovado': False}
        jogo_sorted = sorted(jogo)
        max_seq = atual = 1
        for i in range(1, len(jogo_sorted)):
            if jogo_sorted[i] == jogo_sorted[i-1] + 1:
                atual += 1
                max_seq = max(max_seq, atual)
            else:
                atual = 1
        diag['sequencia_max'] = max_seq
        if max_seq > 3:
            return False, diag
        if self.ultimo:
            rep = len(set(jogo) & set(self.ultimo))
            diag['repeticao_anterior'] = rep
            if rep < 7 or rep > 11:
                return False, diag
        linhas = {i: 0 for i in range(5)}
        for num in jogo:
            linha = (num - 1) // 5
            linhas[linha] += 1
        diag['distribuicao_linhas'] = linhas
        for linha, count in linhas.items():
            if count < 2 or count > 4:
                return False, diag
        diag['aprovado'] = True
        return True, diag
    
    def _gerar_jogo_base(self):
        jogo = set()
        quentes_disp = self.quentes if len(self.quentes) >= 6 else self.quentes + self.mornos[:6-len(self.quentes)]
        mornos_disp = self.mornos if len(self.mornos) >= 5 else self.mornos + self.frios[:5-len(self.mornos)]
        frios_disp = self.frios if len(self.frios) >= 4 else self.frios + [n for n in range(1,26) if n not in jogo][:4-len(self.frios)]
        jogo.update(random.sample(quentes_disp, min(6, len(quentes_disp))))
        mornos_restantes = [n for n in mornos_disp if n not in jogo]
        if mornos_restantes:
            jogo.update(random.sample(mornos_restantes, min(5, len(mornos_restantes))))
        frios_restantes = [n for n in frios_disp if n not in jogo]
        if frios_restantes:
            jogo.update(random.sample(frios_restantes, min(4, len(frios_restantes))))
        while len(jogo) < 15:
            atrasados_disp = [n for n, _ in self.atrasados if n not in jogo]
            if atrasados_disp:
                jogo.add(random.choice(atrasados_disp))
            else:
                jogo.add(random.choice([n for n in range(1, 26) if n not in jogo]))
        return sorted(jogo)
    
    def gerar_jogo_inteligente(self, max_tentativas=10000):
        for tentativa in range(max_tentativas):
            jogo = self._gerar_jogo_base()
            pares = sum(1 for n in jogo if n % 2 == 0)
            if pares not in [7, 8]:
                continue
            baixos = sum(1 for n in jogo if n <= 12)
            if baixos not in [7, 8]:
                continue
            soma = sum(jogo)
            if soma < 170 or soma > 210:
                continue
            aprovado, diag = self._verificar_filtros_matematicos(jogo)
            if aprovado:
                score_geo = self._calcular_score_geometrico(jogo)
                return jogo, {'frequencias': self._classificar_jogo(jogo), 'pares': pares, 'baixos': baixos, 'soma': soma, 'geometria': score_geo, 'filtros': diag}
        return None, None
    
    def _calcular_score_geometrico(self, jogo):
        score = 0
        jogo_set = set(jogo)
        diag_principal = {1, 7, 13, 19, 25}
        diag_secundaria = {5, 9, 13, 17, 21}
        cruz = {3, 11, 13, 15, 23}
        score += len(jogo_set & diag_principal) * 0.5
        score += len(jogo_set & diag_secundaria) * 0.5
        score += len(jogo_set & cruz) * 0.3
        quadrantes = {1: 0, 2: 0, 3: 0, 4: 0}
        for num in jogo:
            linha, coluna = self._coordenadas(num)
            if linha < 2.5 and coluna < 2.5:
                quadrantes[1] += 1
            elif linha < 2.5 and coluna >= 2.5:
                quadrantes[2] += 1
            elif linha >= 2.5 and coluna < 2.5:
                quadrantes[3] += 1
            else:
                quadrantes[4] += 1
        for q in quadrantes:
            if 3 <= quadrantes[q] <= 5:
                score += 1
        return round(score, 1)
    
    def _classificar_jogo(self, jogo):
        result = {'quentes': 0, 'mornos': 0, 'frios': 0}
        for num in jogo:
            if num in self.quentes:
                result['quentes'] += 1
            elif num in self.mornos:
                result['mornos'] += 1
            else:
                result['frios'] += 1
        return result
    
    def gerar_multiplos_jogos(self, quantidade, max_global=20000):
        jogos, diagnosticos = [], []
        candidatos = []
        progress_text = "🧠 Motor PRO gerando jogos inteligentes..."
        progress_bar = st.progress(0, text=progress_text)
        for _ in range(max_global):
            jogo, diag = self.gerar_jogo_inteligente(max_tentativas=100)
            if jogo and jogo not in [c[0] for c in candidatos]:
                score_total = (diag['geometria'] + (10 if diag['pares'] in [7,8] else 0) + (10 if 170 <= diag['soma'] <= 210 else 0) + (5 if diag['filtros']['aprovado'] else 0))
                candidatos.append((jogo, diag, score_total))
            if len(candidatos) >= quantidade * 5:
                break
        candidatos.sort(key=lambda x: x[2], reverse=True)
        for jogo, diag, _ in candidatos[:quantidade]:
            jogos.append(jogo)
            diagnosticos.append(diag)
            progress_bar.progress(len(jogos) / quantidade, text=progress_text)
        progress_bar.empty()
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos PRO (meta: {quantidade})")
        return jogos, diagnosticos
    
    def get_resumo(self):
        return {'quentes': len(self.quentes), 'mornos': len(self.mornos), 'frios': len(self.frios), 'top_atrasados': [f"{n} ({a} conc.)" for n, a in self.atrasados[:3]], 'padroes_geo': {'diag_principal': self.padroes_geometricos['diagonal_principal'], 'diag_secundaria': self.padroes_geometricos['diagonal_secundaria'], 'cruz': self.padroes_geometricos['cruz']}, 'padroes_est': {'pares_medio': round(self.padroes_estatisticos['pares']['media'], 1), 'baixos_medio': round(self.padroes_estatisticos['baixos']['media'], 1), 'soma_media': round(self.padroes_estatisticos['soma']['media'], 1)}}

# =====================================================
# MOTOR DE GEOMETRIA ANALÍTICA
# =====================================================

class MotorGeometriaAvancada:
    def __init__(self, concursos_historico):
        self.concursos = concursos_historico
        self.total_concursos = len(concursos_historico)
        self.volante = np.array([[1,2,3,4,5],[6,7,8,9,10],[11,12,13,14,15],[16,17,18,19,20],[21,22,23,24,25]])
        self.coordenadas = {}
        for i in range(5):
            for j in range(5):
                self.coordenadas[self.volante[i][j]] = (i, j)
        self.matriz_coocorrencia = self._calcular_matriz_coocorrencia()
        self.centroides = self._calcular_centroides()
        self.frequencias = self._calcular_frequencias()
        self.entropia_global = self._calcular_entropia(self.frequencias)
        self.pares_fortes = self._identificar_pares_fortes()
    
    def num_to_coord(self, numero):
        return self.coordenadas.get(numero, (None, None))
    
    def coord_to_num(self, linha, coluna):
        if 0 <= linha < 5 and 0 <= coluna < 5:
            return self.volante[linha][coluna]
        return None
    
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
        freq = [0] * 26
        for jogo in self.concursos:
            for num in jogo:
                freq[num] += 1
        return freq
    
    def _calcular_entropia(self, frequencias):
        total = sum(frequencias)
        if total == 0:
            return 0
        H = 0
        for f in frequencias:
            if f > 0:
                p = f / total
                H -= p * math.log2(p)
        return H
    
    def _identificar_pares_fortes(self, limiar_percentil=90):
        valores = []
        for i in range(1, 26):
            for j in range(i+1, 26):
                if self.matriz_coocorrencia[i][j] > 0:
                    valores.append(self.matriz_coocorrencia[i][j])
        if not valores:
            return []
        limiar = np.percentile(valores, limiar_percentil)
        pares_fortes = []
        for i in range(1, 26):
            for j in range(i+1, 26):
                if self.matriz_coocorrencia[i][j] >= limiar:
                    pares_fortes.append({'par': (i, j), 'ocorrencias': int(self.matriz_coocorrencia[i][j])})
        pares_fortes.sort(key=lambda x: x['ocorrencias'], reverse=True)
        return pares_fortes
    
    def distancia_euclidiana(self, coord1, coord2):
        if None in coord1 or None in coord2:
            return None
        return math.sqrt((coord1[0]-coord2[0])**2 + (coord1[1]-coord2[1])**2)
    
    def distancia_manhattan(self, coord1, coord2):
        if None in coord1 or None in coord2:
            return None
        return abs(coord1[0]-coord2[0]) + abs(coord1[1]-coord2[1])
    
    def dispersao_geometrica(self, jogo):
        coords = [self.num_to_coord(n) for n in jogo if n in self.coordenadas]
        if len(coords) < 2:
            return 0
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
        distancias = [math.sqrt((x-cx)**2 + (y-cy)**2) for x, y in coords]
        return sum(distancias)/len(distancias)
    
    def get_pares_recomendados(self, numero_base, top_n=5):
        if numero_base < 1 or numero_base > 25:
            return []
        linha = self.matriz_coocorrencia[numero_base]
        pares = []
        for i in range(1, 26):
            if i != numero_base and linha[i] > 0:
                pares.append((i, linha[i]))
        pares.sort(key=lambda x: x[1], reverse=True)
        return pares[:top_n]
    
    def analisar_jogo(self, jogo):
        jogo = sorted(jogo)
        xs, ys = [], []
        for num in jogo:
            x, y = self.num_to_coord(num)
            if x is not None:
                xs.append(x)
                ys.append(y)
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
        dist_centro = []
        for num in jogo:
            x, y = self.num_to_coord(num)
            dist_centro.append(math.sqrt((x-cx)**2 + (y-cy)**2))
        adjacentes = 0
        for i in range(len(jogo)):
            for j in range(i+1, len(jogo)):
                x1, y1 = self.num_to_coord(jogo[i])
                x2, y2 = self.num_to_coord(jogo[j])
                if abs(x1-x2) + abs(y1-y2) == 1:
                    adjacentes += 1
        quadrantes = {'Q1': 0, 'Q2': 0, 'Q3': 0, 'Q4': 0}
        for num in jogo:
            x, y = self.num_to_coord(num)
            if x < 2.5 and y < 2.5:
                quadrantes['Q1'] += 1
            elif x < 2.5 and y >= 2.5:
                quadrantes['Q2'] += 1
            elif x >= 2.5 and y < 2.5:
                quadrantes['Q3'] += 1
            else:
                quadrantes['Q4'] += 1
        linhas = {i: 0 for i in range(5)}
        colunas = {i: 0 for i in range(5)}
        for num in jogo:
            x, y = self.num_to_coord(num)
            linhas[x] += 1
            colunas[y] += 1
        return {'centroide': (round(cx,2), round(cy,2)), 'dispersao_media': round(sum(dist_centro)/len(dist_centro),2), 'distancia_max_centro': round(max(dist_centro),2), 'pares_adjacentes': adjacentes, 'quadrantes': quadrantes, 'linhas': linhas, 'colunas': colunas, 'distribuicao_linhas': list(linhas.values()), 'distribuicao_colunas': list(colunas.values())}
    
    def get_estatisticas_geometricas(self):
        if not self.centroides:
            return {}
        xs_validos = [c[0] for c in self.centroides if c[0] is not None]
        ys_validos = [c[1] for c in self.centroides if c[1] is not None]
        if not xs_validos or not ys_validos:
            return {}
        return {'centroide_medio': (round(np.mean(xs_validos),2), round(np.mean(ys_validos),2)), 'variancia_x': round(np.var(xs_validos),2), 'variancia_y': round(np.var(ys_validos),2), 'entropia_global': round(self.entropia_global,3), 'total_pares_fortes': len(self.pares_fortes), 'max_coocorrencia': int(np.max(self.matriz_coocorrencia))}
    
    def gerar_jogo_geometrico(self, target_centroide=None, tolerancia=0.5):
        if target_centroide is None:
            stats = self.get_estatisticas_geometricas()
            target_centroide = stats.get('centroide_medio', (2,2))
        melhor_jogo, melhor_distancia = None, float('inf')
        for _ in range(10000):
            jogo = sorted(random.sample(range(1,26),15))
            xs, ys = [], []
            for num in jogo:
                x, y = self.num_to_coord(num)
                xs.append(x)
                ys.append(y)
            cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
            dist = math.sqrt((cx-target_centroide[0])**2 + (cy-target_centroide[1])**2)
            if dist < melhor_distancia:
                melhor_distancia = dist
                melhor_jogo = jogo
            if dist <= tolerancia:
                break
        return melhor_jogo, round(melhor_distancia,2)
    
    def plot_matriz_coocorrencia(self):
        dados = []
        for i in range(1,26):
            for j in range(i+1,26):
                if self.matriz_coocorrencia[i][j] > 0:
                    dados.append({'num1': i, 'num2': j, 'ocorrencias': int(self.matriz_coocorrencia[i][j])})
        return pd.DataFrame(dados).sort_values('ocorrencias', ascending=False)

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(page_title="🎯 LOTOFÁCIL 3622", layout="centered", initial_sidebar_state="collapsed")

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
</style>
""", unsafe_allow_html=True)

st.title("🧠🎯 LOTOFÁCIL 3622")
st.caption("Modelo Universal + Ajuste Adaptável • Mobile First")

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
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, Counter):
        return dict(obj)
    else:
        return obj

def normalizar_jogos(jogos_brutos):
    jogos_normalizados = []
    if isinstance(jogos_brutos, pd.DataFrame):
        for _, row in jogos_brutos.iterrows():
            for col in row.index:
                valor = row[col]
                if isinstance(valor, str) and "," in valor:
                    dezenas = [int(d.strip()) for d in valor.split(",")]
                    jogos_normalizados.append(sorted(dezenas))
                    break
                elif isinstance(valor, list):
                    jogos_normalizados.append(sorted(valor))
                    break
        return jogos_normalizados
    if isinstance(jogos_brutos, list):
        for item in jogos_brutos:
            if isinstance(item, dict):
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
            elif isinstance(item, str):
                if "," in item:
                    dezenas = [int(d.strip()) for d in item.split(",")]
                else:
                    dezenas = [int(d) for d in item.split()]
                jogos_normalizados.append(sorted(dezenas))
            elif isinstance(item, (list, tuple)):
                jogos_normalizados.append(sorted([int(x) for x in item]))
    if not jogos_normalizados and jogos_brutos:
        if isinstance(jogos_brutos[0], list) and len(jogos_brutos[0]) == 15:
            return jogos_brutos
    return jogos_normalizados

def validar_jogos_normalizados(jogos):
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

def salvar_jogos_gerados(jogos, fechamento, dna_params, numero_concurso_atual, data_concurso_atual, estatisticas=None):
    try:
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/fechamento_{data_hora}_{jogo_id}.json"
        jogos_convertidos = convert_numpy_types(jogos)
        jogos_final = []
        for jogo in jogos_convertidos:
            if isinstance(jogo, (list, tuple)):
                jogo_lista = [int(n) for n in jogo]
                if len(set(jogo_lista)) != 15:
                    jogo_lista = sorted(list(set(jogo_lista)))
                    while len(jogo_lista) < 15:
                        novo = random.randint(1, 25)
                        if novo not in jogo_lista:
                            jogo_lista.append(novo)
                    jogo_lista.sort()
                jogos_final.append(jogo_lista)
            else:
                jogos_final.append([int(n) for n in range(1, 16)])
        fechamento_convertido = convert_numpy_types(fechamento)
        dna_convertido = convert_numpy_types(dna_params) if dna_params else {}
        estatisticas_convertidas = convert_numpy_types(estatisticas) if estatisticas else {}
        dados = {"id": jogo_id, "data_geracao": datetime.now().isoformat(), "concurso_base": {"numero": int(numero_concurso_atual), "data": str(data_concurso_atual)}, "fechamento_base": fechamento_convertido, "dna_params": dna_convertido, "jogos": jogos_final, "estatisticas": estatisticas_convertidas, "conferido": False, "conferencias": [], "schema_version": "3.0"}
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
    try:
        caminho = f"jogos_salvos/{arquivo}"
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        if "conferencias" not in dados:
            dados["conferencias"] = []
        acertos_convertidos = [int(a) for a in acertos]
        estatisticas_convertidas = convert_numpy_types(estatisticas) if estatisticas else {}
        nova_conferencia = {"concurso": concurso_info, "acertos": acertos_convertidos, "estatisticas": estatisticas_convertidas, "data_conferencia": datetime.now().isoformat()}
        dados["conferencias"].append(nova_conferencia)
        dados["conferido"] = True
        if "estatisticas_historicas" not in dados:
            dados["estatisticas_historicas"] = []
        dados["estatisticas_historicas"].append(estatisticas_convertidas)
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar conferência: {e}")
        return False

def exportar_concursos_txt(dados_api, qtd_concursos):
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

class AnaliseLotofacilBasica:
    def __init__(self, concursos, dados_completos=None):
        self.concursos = concursos
        self.dados_completos = dados_completos or []
        self.ultimo_concurso = concursos[0] if concursos else []
        self.ultimo_concurso_numero = dados_completos[0]["concurso"] if dados_completos else 0
        self.ultimo_concurso_data = dados_completos[0]["data"] if dados_completos else ""
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)
        self.frequencias = self._frequencias()
        self.ultimo_resultado = self.concursos[0] if concursos else []
    def _frequencias(self):
        c = Counter()
        for con in self.concursos: 
            c.update(con)
        return {n: c.get(n, 0) / self.total_concursos for n in self.numeros}

# =====================================================
# DETECTOR MASTER DE PADRÕES B-M-A
# =====================================================

def contar_bma(concurso):
    baixas = sum(1 for n in concurso if 1 <= n <= 8)
    medias = sum(1 for n in concurso if 9 <= n <= 16)
    altas = sum(1 for n in concurso if 17 <= n <= 25)
    return (baixas, medias, altas)

def analisar_padroes(lista_concursos):
    padroes = [contar_bma(c) for c in lista_concursos]
    freq = Counter(padroes)
    atraso = {}
    ultima_aparicao = {}
    total = len(lista_concursos)
    for i in range(total-1, -1, -1):
        p = padroes[i]
        if p not in ultima_aparicao:
            ultima_aparicao[p] = i
    for p in freq:
        if p in ultima_aparicao:
            atraso[p] = total - 1 - ultima_aparicao[p]
        else:
            atraso[p] = total
    return freq, atraso, padroes

def detector_sinais(lista_concursos, limiar=1.5):
    freq, atraso, _ = analisar_padroes(lista_concursos)
    total = len(lista_concursos)
    sinais = []
    for p in freq:
        ciclo_medio = total / freq[p]
        if atraso[p] > ciclo_medio * limiar:
            intensidade = atraso[p] / ciclo_medio
            sinais.append({"padrao": p, "frequencia": freq[p], "ciclo_medio": round(ciclo_medio, 1), "atraso": atraso[p], "intensidade": round(intensidade, 1), "nivel": "🚨 FORTE" if intensidade > 2 else "⚠️ MÉDIO" if intensidade > 1.5 else "🔔 FRACO"})
    sinais.sort(key=lambda x: x["intensidade"], reverse=True)
    return sinais

def detector_alvos(lista_concursos, padroes_alvo=None):
    if padroes_alvo is None:
        padroes_alvo = [(7,4,4), (3,6,6), (4,5,6), (6,5,4), (4,6,5), (5,6,4), (5,7,3), (6,6,3), (4,7,4), (5,5,5)]
    padroes = [contar_bma(c) for c in lista_concursos]
    ultimos_10 = padroes[:10]
    ultimos_5 = padroes[:5]
    ultimo = padroes[0] if padroes else None
    resultados = []
    for p in padroes_alvo:
        total_ocorrencias = padroes.count(p)
        ocorrencias_10 = ultimos_10.count(p)
        ocorrencias_5 = ultimos_5.count(p)
        atraso = 0
        for i, padrao in enumerate(padroes):
            if padrao == p:
                atraso = i
                break
        if p == ultimo:
            status, cor = "🎯 NO ÚLTIMO CONCURSO", "gold"
        elif p in ultimos_5:
            status, cor = "✅ RECENTE (últimos 5)", "#4ade80"
        elif p in ultimos_10:
            status, cor = "📊 APARECEU (últimos 10)", "#4cc9f0"
        elif atraso > 20:
            status, cor = "🔥 MUITO ATRASADO", "#f97316"
        elif atraso > 10:
            status, cor = "⚠️ ATRASADO", "#ff6b6b"
        else:
            status, cor = "⏳ AUSENTE", "#aaa"
        resultados.append({"padrao": f"{p[0]}-{p[1]}-{p[2]}", "total": total_ocorrencias, "ultimos_10": ocorrencias_10, "ultimos_5": ocorrencias_5, "atraso": atraso, "status": status, "cor": cor})
    return resultados

def top_padroes_frequentes(lista_concursos, n=15):
    padroes = [contar_bma(c) for c in lista_concursos]
    freq = Counter(padroes)
    top = []
    for p, count in freq.most_common(n):
        percentual = (count / len(lista_concursos)) * 100
        top.append({"padrao": f"{p[0]}-{p[1]}-{p[2]}", "ocorrencias": count, "percentual": round(percentual, 1)})
    return top

def formatar_padrao_html(padrao_str, destaque=False):
    partes = padrao_str.split('-')
    if len(partes) == 3:
        b, m, a = partes
        return f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:15px; padding:3px 8px; margin:2px; display:inline-block;'><span style='color:#4cc9f0; font-weight:bold;'>{b}</span>-<span style='color:#4ade80; font-weight:bold;'>{m}</span>-<span style='color:#f97316; font-weight:bold;'>{a}</span></span>"
    return padrao_str

# =====================================================
# CLASSE DO MODELO 3622
# =====================================================

class Gerador3622:
    def __init__(self, ultimo_concurso, penultimo_concurso=None, antepenultimo_concurso=None):
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        self.penultimo = sorted(penultimo_concurso) if penultimo_concurso else []
        self.antepenultimo = sorted(antepenultimo_concurso) if antepenultimo_concurso else []
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        self.faixa_baixa = list(range(1, 9))
        self.faixa_media = list(range(9, 17))
        self.faixa_alta = list(range(17, 26))
        self.ajustes = self._calcular_ajustes()
    
    def _calcular_ajustes(self):
        ajustes = {"repeticoes_alvo": 8, "altas_alvo": 2, "miolo_alvo": 6, "tipo_sequencia": "normal"}
        if self.penultimo and self.ultimo:
            rep_penultimo = len(set(self.ultimo) & set(self.penultimo))
            if rep_penultimo >= 9:
                ajustes["repeticoes_alvo"] = 7
            elif rep_penultimo <= 7:
                ajustes["repeticoes_alvo"] = 9
            altas_ultimo = sum(1 for n in self.ultimo if n in [22, 23, 24, 25])
            if altas_ultimo <= 1:
                ajustes["altas_alvo"] = 3
            elif altas_ultimo >= 3:
                ajustes["altas_alvo"] = 1
            miolo_ultimo = sum(1 for n in self.ultimo if 9 <= n <= 16)
            if miolo_ultimo >= 6:
                ajustes["miolo_alvo"] = 6
            else:
                ajustes["miolo_alvo"] = 5
            sequencias = self._contar_sequencias(self.ultimo)
            if sequencias >= 4:
                ajustes["tipo_sequencia"] = "encurtar"
            elif sequencias <= 1:
                ajustes["tipo_sequencia"] = "alongar"
        return ajustes
    
    def _contar_sequencias(self, numeros):
        nums = sorted(numeros)
        pares = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                pares += 1
        return pares
    
    def _validar_regras_universais(self, jogo):
        diagnostico = {"regra1": False, "regra2": False, "regra3": False, "regra4": False, "regra5": False, "regra6": False, "falhas": 0}
        if self.ultimo:
            repeticoes = len(set(jogo) & set(self.ultimo))
            if 8 <= repeticoes <= 10:
                diagnostico["regra1"] = True
            elif repeticoes == 7 or repeticoes == 11:
                diagnostico["regra1"] = True
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares in [7, 8]:
            diagnostico["regra2"] = True
        elif pares == 6 or pares == 9:
            diagnostico["regra2"] = True
        soma = sum(jogo)
        if 168 <= soma <= 186:
            diagnostico["regra3"] = True
        elif 165 <= soma <= 190:
            diagnostico["regra3"] = True
        baixas = sum(1 for n in jogo if n in self.faixa_baixa)
        medias = sum(1 for n in jogo if n in self.faixa_media)
        altas = sum(1 for n in jogo if n in self.faixa_alta)
        if (5 <= baixas <= 6 and 5 <= medias <= 6 and 3 <= altas <= 4):
            diagnostico["regra4"] = True
        elif (4 <= baixas <= 7 and 4 <= medias <= 7 and 2 <= altas <= 5):
            if not (baixas <= 4 or altas >= 6):
                diagnostico["regra4"] = True
        consecutivos = self._contar_sequencias(jogo)
        if consecutivos >= 3:
            diagnostico["regra5"] = True
        qtd_primos = sum(1 for n in jogo if n in self.primos)
        if 4 <= qtd_primos <= 6:
            diagnostico["regra6"] = True
        diagnostico["falhas"] = sum(1 for v in diagnostico.values() if isinstance(v, bool) and not v)
        return diagnostico["falhas"] <= 1, diagnostico
    
    def gerar_jogo(self):
        max_tentativas = 5000
        for tentativa in range(max_tentativas):
            if self.ultimo:
                repeticoes_alvo = self.ajustes["repeticoes_alvo"]
                if len(self.ultimo) >= repeticoes_alvo:
                    base = sorted(random.sample(self.ultimo, repeticoes_alvo))
                else:
                    base = sorted(random.sample(self.ultimo, len(self.ultimo)))
            else:
                base = []
            jogo = base.copy()
            alvo_baixas, alvo_medias, alvo_altas = 5, self.ajustes["miolo_alvo"], self.ajustes["altas_alvo"]
            total_atual = len(jogo)
            if total_atual < 15:
                baixas_atuais = sum(1 for n in jogo if n in self.faixa_baixa)
                medias_atuais = sum(1 for n in jogo if n in self.faixa_media)
                altas_atuais = sum(1 for n in jogo if n in self.faixa_alta)
                faltam = 15 - total_atual
                for _ in range(faltam):
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
                    disponiveis = [n for n in range(1, 26) if n not in jogo]
                    if disponiveis:
                        escolha = random.choice(disponiveis)
                        jogo.append(escolha)
                        if escolha in self.faixa_baixa:
                            baixas_atuais += 1
                        elif escolha in self.faixa_media:
                            medias_atuais += 1
                        else:
                            altas_atuais += 1
            jogo.sort()
            aprovado, diagnostico = self._validar_regras_universais(jogo)
            if aprovado:
                return jogo, diagnostico
        return self._gerar_jogo_fallback()
    
    def _gerar_jogo_fallback(self):
        jogo = []
        if self.ultimo:
            rep = random.sample(self.ultimo, min(8, len(self.ultimo)))
            jogo.extend(rep)
        while len(jogo) < 15:
            novo = random.randint(1, 25)
            if novo not in jogo:
                jogo.append(novo)
        jogo.sort()
        diagnostico = {"regra1": len(set(jogo) & set(self.ultimo)) >= 7 if self.ultimo else True, "regra2": 6 <= sum(1 for n in jogo if n % 2 == 0) <= 9, "regra3": 165 <= sum(jogo) <= 190, "regra4": True, "regra5": self._contar_sequencias(jogo) >= 2, "regra6": 3 <= sum(1 for n in jogo if n in self.primos) <= 7, "falhas": 0}
        return jogo, diagnostico
    
    def gerar_multiplos_jogos(self, quantidade):
        jogos, diagnosticos = [], []
        tentativas, max_tentativas = 0, quantidade * 200
        while len(jogos) < quantidade and tentativas < max_tentativas:
            jogo, diag = self.gerar_jogo()
            if jogo not in jogos:
                jogos.append(jogo)
                diagnosticos.append(diag)
            tentativas += 1
        return jogos, diagnosticos
    
    def get_resumo_ajustes(self):
        return {"repeticoes_alvo": self.ajustes["repeticoes_alvo"], "altas_alvo": self.ajustes["altas_alvo"], "miolo_alvo": self.ajustes["miolo_alvo"], "tipo_sequencia": self.ajustes["tipo_sequencia"]}

# =====================================================
# GERADOR 12+
# =====================================================

class Gerador12Plus:
    def __init__(self, concursos_historico, ultimo_concurso):
        self.concursos = concursos_historico
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 26))
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        self.frequencias_recentes = self._calcular_frequencias_recentes()
        self.peso_ultimo = 3.0
    
    def _calcular_frequencias_recentes(self, n=10):
        frequencias = Counter()
        total = 0
        ultimos_n = self.concursos[1:n+1] if len(self.concursos) > n else self.concursos[1:]
        for concurso in ultimos_n:
            frequencias.update(concurso)
            total += len(concurso)
        if total > 0:
            return {num: count/total for num, count in frequencias.items()}
        return {}
    
    def _maior_bloco_consecutivo(self, jogo):
        if not jogo:
            return 0
        nums = sorted(jogo)
        maior, atual = 1, 1
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                atual += 1
                maior = max(maior, atual)
            else:
                atual = 1
        return maior
    
    def _contar_consecutivos(self, jogo):
        nums = sorted(jogo)
        count = 0
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                count += 1
        return count
    
    def jogo_valido(self, jogo):
        if len(jogo) != 15:
            return False, {"erro": "Tamanho incorreto"}
        baixas = sum(1 for n in jogo if n in self.baixas)
        medias = sum(1 for n in jogo if n in self.medias)
        altas = sum(1 for n in jogo if n in self.altas)
        pares = sum(1 for n in jogo if n % 2 == 0)
        primos = sum(1 for n in jogo if n in self.primos)
        soma = sum(jogo)
        repetidas = len(set(jogo) & set(self.ultimo))
        consecutivos = self._contar_consecutivos(jogo)
        maior_bloco = self._maior_bloco_consecutivo(jogo)
        diag = {"baixas": baixas, "medias": medias, "altas": altas, "pares": pares, "primos": primos, "soma": soma, "repetidas": repetidas, "consecutivos": consecutivos, "maior_bloco": maior_bloco, "regras": {}}
        diag["regras"]["distribuicao"] = (4 <= baixas <= 5) and (5 <= medias <= 6) and (5 <= altas <= 6)
        diag["regras"]["pares"] = (7 <= pares <= 8)
        diag["regras"]["soma"] = (190 <= soma <= 210)
        diag["regras"]["primos"] = (5 <= primos <= 6)
        diag["regras"]["repetidas"] = (9 <= repetidas <= 11)
        diag["regras"]["consecutivos_qtd"] = (2 <= consecutivos <= 4)
        diag["regras"]["bloco_grande"] = (maior_bloco >= 3)
        bloqueios = [soma < 185, soma > 215, pares <= 6, pares >= 9, altas <= 4, maior_bloco < 3, repetidas <= 7]
        tem_bloqueio = any(bloqueios)
        diag["bloqueio"] = tem_bloqueio
        aprovado = all(diag["regras"].values()) and not tem_bloqueio
        diag["regras_aprovadas"] = sum(1 for v in diag["regras"].values() if v)
        diag["total_regras"] = len(diag["regras"])
        return aprovado, diag
    
    def _gerar_jogo_ponderado(self):
        pool, pesos = [], []
        for num in range(1, 26):
            pool.append(num)
            peso = self.frequencias_recentes.get(num, 1.0)
            if num in self.ultimo:
                peso *= self.peso_ultimo
            pesos.append(peso)
        pesos = np.array(pesos) / sum(pesos)
        return pool, pesos
    
    def gerar_jogo(self, max_tentativas=10000):
        pool, pesos = self._gerar_jogo_ponderado()
        for _ in range(max_tentativas):
            indices = np.random.choice(len(pool), size=15, replace=False, p=pesos)
            jogo = sorted([pool[i] for i in indices])
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        for _ in range(max_tentativas):
            jogo = sorted(random.sample(range(1, 26), 15))
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        return None, None
    
    def gerar_multiplos_jogos(self, quantidade, max_total_tentativas=100000):
        jogos, diagnosticos = [], []
        tentativas = 0
        progress_text = "Gerando jogos válidos..."
        progress_bar = st.progress(0, text=progress_text)
        while len(jogos) < quantidade and tentativas < max_total_tentativas:
            jogo, diag = self.gerar_jogo()
            tentativas += 1
            if jogo and jogo not in jogos:
                jogos.append(jogo)
                diagnosticos.append(diag)
                progress_bar.progress(len(jogos) / quantidade, text=progress_text)
        progress_bar.empty()
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos válidos em {tentativas} tentativas")
        return jogos, diagnosticos
    
    def get_estatisticas_recentes(self):
        if len(self.concursos) < 2:
            return {}
        ultimos = self.concursos[:20]
        return {"baixas": np.mean([sum(1 for n in c if n in self.baixas) for c in ultimos]), "medias": np.mean([sum(1 for n in c if n in self.medias) for c in ultimos]), "altas": np.mean([sum(1 for n in c if n in self.altas) for c in ultimos]), "pares": np.mean([sum(1 for n in c if n % 2 == 0) for c in ultimos]), "primos": np.mean([sum(1 for n in c if n in self.primos) for c in ultimos]), "soma": np.mean([sum(c) for c in ultimos]), "repetidas": np.mean([len(set(c) & set(self.ultimo)) for c in ultimos[1:]]) if len(ultimos) > 1 else 0}

# =====================================================
# GERADOR 13+
# =====================================================

class Gerador13Plus:
    def __init__(self, concursos_historico, ultimo_concurso):
        self.concursos = concursos_historico
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 26))
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        self.frequencias_recentes = self._calcular_frequencias_recentes()
        self.peso_ultimo = 4.0
    
    def _calcular_frequencias_recentes(self, n=20):
        frequencias = Counter()
        total = 0
        ultimos_n = self.concursos[1:n+1] if len(self.concursos) > n else self.concursos[1:]
        for concurso in ultimos_n:
            frequencias.update(concurso)
            total += len(concurso)
        if total > 0:
            return {num: count/total for num, count in frequencias.items()}
        return {}
    
    def _maior_bloco_consecutivo(self, jogo):
        if not jogo:
            return 0
        nums = sorted(jogo)
        maior, atual = 1, 1
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                atual += 1
                maior = max(maior, atual)
            else:
                atual = 1
        return maior
    
    def _contar_consecutivos(self, jogo):
        nums = sorted(jogo)
        count = 0
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                count += 1
        return count
    
    def _tem_dois_blocos(self, jogo):
        nums = sorted(jogo)
        blocos = []
        atual = 1
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                atual += 1
            else:
                if atual >= 2:
                    blocos.append(atual)
                atual = 1
        if atual >= 2:
            blocos.append(atual)
        return len(blocos) >= 2 and max(blocos) >= 3
    
    def jogo_valido(self, jogo):
        if len(jogo) != 15:
            return False, {"erro": "Tamanho incorreto"}
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
        diag = {"baixas": baixas, "medias": medias, "altas": altas, "pares": pares, "primos": primos, "soma": soma, "repetidas": repetidas, "consecutivos": consecutivos, "maior_bloco": maior_bloco, "tem_dois_blocos": tem_dois_blocos, "regras": {}}
        diag["regras"]["distribuicao"] = (baixas == 4) and (medias == 6) and (altas == 5)
        diag["regras"]["pares"] = (pares == 7)
        diag["regras"]["soma"] = (195 <= soma <= 205)
        diag["regras"]["primos"] = (primos == 5)
        diag["regras"]["repetidas"] = (repetidas in (10, 11))
        diag["regras"]["consecutivos_qtd"] = (consecutivos in (3, 4))
        diag["regras"]["bloco_grande"] = (maior_bloco >= 3)
        diag["regras"]["dois_blocos"] = tem_dois_blocos
        bloqueios = [soma < 190 or soma > 210, pares <= 6 or pares >= 9, altas <= 4, maior_bloco < 3, repetidas <= 9, medias <= 5, not tem_dois_blocos]
        tem_bloqueio = any(bloqueios)
        diag["bloqueio"] = tem_bloqueio
        aprovado = all(diag["regras"].values()) and not tem_bloqueio
        diag["regras_aprovadas"] = sum(1 for v in diag["regras"].values() if v)
        diag["total_regras"] = len(diag["regras"])
        return aprovado, diag
    
    def _gerar_jogo_ponderado(self):
        pool, pesos = [], []
        for num in range(1, 26):
            pool.append(num)
            peso = self.frequencias_recentes.get(num, 1.0)
            if num in self.ultimo:
                peso *= self.peso_ultimo
            pesos.append(peso)
        pesos = np.array(pesos) / sum(pesos)
        return pool, pesos
    
    def gerar_jogo(self, max_tentativas=20000):
        pool, pesos = self._gerar_jogo_ponderado()
        for _ in range(max_tentativas):
            indices = np.random.choice(len(pool), size=15, replace=False, p=pesos)
            jogo = sorted([pool[i] for i in indices])
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        for _ in range(max_tentativas * 2):
            jogo = sorted(random.sample(range(1, 26), 15))
            aprovado, diag = self.jogo_valido(jogo)
            if aprovado:
                return jogo, diag
        return None, None
    
    def gerar_multiplos_jogos(self, quantidade, max_total_tentativas=500000):
        jogos, diagnosticos = [], []
        tentativas = 0
        progress_text = "Gerando jogos 13+ (paciência, é restritivo)..."
        progress_bar = st.progress(0, text=progress_text)
        while len(jogos) < quantidade and tentativas < max_total_tentativas:
            jogo, diag = self.gerar_jogo()
            tentativas += 1
            if jogo and jogo not in jogos:
                jogos.append(jogo)
                diagnosticos.append(diag)
                progress_bar.progress(len(jogos) / quantidade, text=progress_text)
            if tentativas % 1000 == 0:
                progress_bar.progress(len(jogos) / quantidade, text=f"{len(jogos)}/{quantidade} jogos encontrados em {tentativas} tentativas...")
        progress_bar.empty()
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos 13+ em {tentativas} tentativas (taxa de acerto: {len(jogos)/tentativas*100:.4f}%)")
        else:
            st.success(f"✅ {len(jogos)} jogos 13+ gerados em {tentativas} tentativas (taxa: {len(jogos)/tentativas*100:.4f}%)")
        return jogos, diagnosticos
    
    def get_estatisticas_recentes(self):
        if len(self.concursos) < 2:
            return {}
        ultimos = self.concursos[:20]
        return {"baixas": np.mean([sum(1 for n in c if n in self.baixas) for c in ultimos]), "medias": np.mean([sum(1 for n in c if n in self.medias) for c in ultimos]), "altas": np.mean([sum(1 for n in c if n in self.altas) for c in ultimos]), "pares": np.mean([sum(1 for n in c if n % 2 == 0) for c in ultimos]), "primos": np.mean([sum(1 for n in c if n in self.primos) for c in ultimos]), "soma": np.mean([sum(c) for c in ultimos]), "repetidas": np.mean([len(set(c) & set(self.ultimo)) for c in ultimos[1:]]) if len(ultimos) > 1 else 0}

# =====================================================
# GERADOR PROFISSIONAL
# =====================================================

class GeradorProfissional:
    PADROES_DISPONIVEIS = {"5-7-3": {"baixas": 5, "medias": 7, "altas": 3, "desc": "Padrão mais comum (prioridade máxima)"}, "5-5-5": {"baixas": 5, "medias": 5, "altas": 5, "desc": "Equilíbrio perfeito"}, "6-4-5": {"baixas": 6, "medias": 4, "altas": 5, "desc": "Mais baixas, menos médias"}, "5-4-6": {"baixas": 5, "medias": 4, "altas": 6, "desc": "Mais altas, menos médias"}, "5-6-4": {"baixas": 5, "medias": 6, "altas": 4, "desc": "Mais médias, menos altas"}, "4-5-6": {"baixas": 4, "medias": 5, "altas": 6, "desc": "Menos baixas, mais altas"}, "6-5-4": {"baixas": 6, "medias": 5, "altas": 4, "desc": "Mais baixas, menos altas"}, "4-6-5": {"baixas": 4, "medias": 6, "altas": 5, "desc": "Menos baixas, mais médias"}, "7-4-4": {"baixas": 7, "medias": 4, "altas": 4, "desc": "Muitas baixas"}, "3-6-6": {"baixas": 3, "medias": 6, "altas": 6, "desc": "Poucas baixas"}}
    
    def __init__(self, ultimo_concurso, padroes_selecionados=None):
        self.ultimo_concurso = set(ultimo_concurso) if ultimo_concurso else set()
        self.padroes_ativos = padroes_selecionados if padroes_selecionados and len(padroes_selecionados) > 0 else ["5-7-3"]
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 25))
    
    def contar_consecutivos(self, jogo):
        jogo_sorted = sorted(jogo)
        maior, atual = 1, 1
        for i in range(1, len(jogo_sorted)):
            if jogo_sorted[i] == jogo_sorted[i-1] + 1:
                atual += 1
                maior = max(maior, atual)
            else:
                atual = 1
        return maior
    
    def verificar_padrao(self, jogo, padrao):
        baixas = sum(1 for n in jogo if n in self.baixas)
        medias = sum(1 for n in jogo if n in self.medias)
        altas = sum(1 for n in jogo if n in self.altas)
        config = self.PADROES_DISPONIVEIS[padrao]
        return baixas == config["baixas"] and medias == config["medias"] and altas == config["altas"]
    
    def gerar_jogo_com_padrao(self, padrao, max_tentativas=5000):
        config = self.PADROES_DISPONIVEIS[padrao]
        for tentativa in range(max_tentativas):
            jogo = set()
            jogo.update(random.sample(self.baixas, config["baixas"]))
            jogo.update(random.sample(self.medias, config["medias"]))
            jogo.update(random.sample(self.altas, config["altas"]))
            jogo = sorted(jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)
            if pares not in [6, 7, 8]:
                continue
            if self.ultimo_concurso:
                repetidas = len(set(jogo) & self.ultimo_concurso)
                if repetidas not in [8, 9]:
                    continue
            seq = self.contar_consecutivos(jogo)
            if seq < 4 or seq > 6:
                continue
            soma = sum(jogo)
            if soma < 180 or soma > 220:
                continue
            return jogo, {"padrao": padrao, "distribuicao": f"{config['baixas']}-{config['medias']}-{config['altas']}", "pares": pares, "repetidas": repetidas if self.ultimo_concurso else 0, "sequencia_max": seq, "soma": soma}
        return None, None
    
    def gerar_jogo(self):
        if self.padroes_ativos:
            padrao_escolhido = random.choice(self.padroes_ativos)
            return self.gerar_jogo_com_padrao(padrao_escolhido)
        return None, None
    
    def gerar_multiplos_jogos(self, quantidade, distribuicao_por_padrao=None):
        jogos, diagnosticos = [], []
        tentativas = 0
        max_tentativas = quantidade * 10000
        if not distribuicao_por_padrao:
            jogos_por_padrao = {p: max(1, quantidade // len(self.padroes_ativos)) for p in self.padroes_ativos}
            total = sum(jogos_por_padrao.values())
            if total < quantidade:
                primeiro_padrao = self.padroes_ativos[0]
                jogos_por_padrao[primeiro_padrao] += quantidade - total
        else:
            jogos_por_padrao = {}
            for padrao, percent in distribuicao_por_padrao.items():
                if padrao in self.padroes_ativos:
                    jogos_por_padrao[padrao] = int(quantidade * percent / 100)
            if sum(jogos_por_padrao.values()) < quantidade:
                jogos_por_padrao["5-7-3"] = jogos_por_padrao.get("5-7-3", 0) + (quantidade - sum(jogos_por_padrao.values()))
        progress_text = "Gerando jogos profissionais com padrões selecionados..."
        progress_bar = st.progress(0, text=progress_text)
        total_gerados = 0
        for padrao, qtd_alvo in jogos_por_padrao.items():
            qtd_gerados_padrao = 0
            while qtd_gerados_padrao < qtd_alvo and tentativas < max_tentativas:
                jogo, diag = self.gerar_jogo_com_padrao(padrao)
                tentativas += 1
                if jogo and jogo not in jogos:
                    jogos.append(jogo)
                    diagnosticos.append(diag)
                    qtd_gerados_padrao += 1
                    total_gerados += 1
                    progress_bar.progress(total_gerados / quantidade, text=progress_text)
                if tentativas % 1000 == 0:
                    progress_bar.progress(total_gerados / quantidade, text=f"{total_gerados}/{quantidade} jogos encontrados ({tentativas} tentativas)...")
        progress_bar.empty()
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos profissionais em {tentativas} tentativas")
        return jogos, diagnosticos
    
    def get_info(self):
        return {"nome": "Gerador Profissional", "padroes_ativos": self.padroes_ativos, "pares": "6-8 pares", "repetidas": "8-9 do último concurso", "sequencias": "4-6 números consecutivos", "soma": "180-220"}

# =====================================================
# SISTEMA AUTÔNOMO
# =====================================================

class SistemaAutonomo:
    def __init__(self, concursos_historico):
        self.concursos = concursos_historico
        self.total_concursos = len(concursos_historico)
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 26))
        self.num_testes = 50
    
    def estrategia_frequencia(self, qtd=18):
        freq = Counter()
        for c in self.concursos:
            freq.update(c)
        return sorted(freq, key=freq.get, reverse=True)[:qtd]
    
    def estrategia_atraso(self, qtd=18):
        atraso = {n: 0 for n in range(1, 26)}
        for c in reversed(self.concursos):
            for n in range(1, 26):
                if n not in c:
                    atraso[n] += 1
        return sorted(atraso, key=atraso.get, reverse=True)[:qtd]
    
    def estrategia_hibrida(self, qtd=18):
        freq = Counter()
        for c in self.concursos:
            freq.update(c)
        atraso = {n: 0 for n in range(1, 26)}
        for c in reversed(self.concursos):
            for n in range(1, 26):
                if n not in c:
                    atraso[n] += 1
        max_freq = max(freq.values()) if freq.values() else 1
        max_atraso = max(atraso.values()) if atraso.values() else 1
        score = {}
        for n in range(1, 26):
            freq_norm = freq[n] / max_freq if max_freq > 0 else 0
            atraso_norm = atraso[n] / max_atraso if max_atraso > 0 else 0
            score[n] = freq_norm * 0.7 + atraso_norm * 0.3
        return sorted(score, key=score.get, reverse=True)[:qtd]
    
    def estrategia_aleatoria(self, qtd=18):
        return sorted(random.sample(range(1, 26), qtd))
    
    def jogo_valido(self, jogo):
        pares = sum(1 for n in jogo if n % 2 == 0)
        if not (6 <= pares <= 9):
            return False
        linhas = [0] * 5
        for n in jogo:
            linhas[(n-1)//5] += 1
        if any(l < 2 or l > 4 for l in linhas):
            return False
        seq = 0
        for i in range(len(jogo)-1):
            if jogo[i] + 1 == jogo[i+1]:
                seq += 1
        if not (2 <= seq <= 5):
            return False
        return True
    
    def gerar_jogos_base(self, base, qtd=10):
        jogos = []
        max_tentativas = qtd * 1000
        tentativas = 0
        while len(jogos) < qtd and tentativas < max_tentativas:
            jogo = sorted(random.sample(base, 15))
            if self.jogo_valido(jogo) and jogo not in jogos:
                jogos.append(jogo)
            tentativas += 1
        return jogos
    
    def avaliar_estrategia(self, estrategia_func):
        if self.total_concursos < 100:
            return 0
        resultados = []
        num_testes = self.num_testes
        for i in range(50, min(50 + num_testes, self.total_concursos - 1)):
            historico = self.concursos[:i]
            resultado_real = set(self.concursos[i])
            base = estrategia_func(qtd=18)
            jogos = self.gerar_jogos_base(base, qtd=10)
            melhor = 0
            for j in jogos:
                acertos = len(set(j) & resultado_real)
                melhor = max(melhor, acertos)
            resultados.append(melhor)
        return np.mean(resultados) if resultados else 0
    
    def escolher_melhor_estrategia(self, progress_callback=None):
        estrategias = {"🎯 Frequência (quentes)": self.estrategia_frequencia, "⏱️ Atraso (frias)": self.estrategia_atraso, "🧬 Híbrida (70/30)": self.estrategia_hibrida, "🎲 Aleatória": self.estrategia_aleatoria}
        scores, detalhes = {}, {}
        total_estrategias = len(estrategias)
        for idx, (nome, func) in enumerate(estrategias.items()):
            if progress_callback:
                progress_callback(idx / total_estrategias, f"Testando {nome}...")
            score = self.avaliar_estrategia(func)
            scores[nome] = score
            detalhes[nome] = {"score": score, "func": func}
        melhor_nome = max(scores, key=scores.get)
        melhor_score = scores[melhor_nome]
        melhor_func = detalhes[melhor_nome]["func"]
        return melhor_nome, melhor_func, melhor_score, scores
    
    def sistema_autonomo_completo(self, qtd_jogos=10, progress_callback=None):
        melhor_nome, melhor_func, melhor_score, todos_scores = self.escolher_melhor_estrategia(progress_callback)
        base = melhor_func(qtd=18)
        jogos = self.gerar_jogos_base(base, qtd=qtd_jogos)
        return {"melhor_estrategia": melhor_nome, "melhor_score": melhor_score, "todos_scores": todos_scores, "base_utilizada": sorted(base), "jogos": jogos, "quantidade_jogos": len(jogos)}

# =====================================================
# GERADOR AUTÔNOMO HISTÓRICO (NOVO)
# =====================================================

class GeradorAutonomoHistorico:
    def __init__(self, dados_historicos, ultimo_concurso):
        self.historico = dados_historicos
        self.ultimo = sorted(ultimo_concurso) if ultimo_concurso else []
        self.total_concursos = len(dados_historicos)
        self.baixas = list(range(1, 9))
        self.medias = list(range(9, 17))
        self.altas = list(range(17, 26))
        self.pares_min, self.pares_max = 7, 8
        self.soma_min, self.soma_max = 180, 230
        self.linhas_min, self.linhas_max = 2, 4
    
    def contar_pares_impares(self, jogo):
        pares = sum(1 for n in jogo if n % 2 == 0)
        return pares, 15 - pares
    
    def soma_total(self, jogo):
        return sum(jogo)
    
    def linhas(self, jogo):
        linhas = {i: 0 for i in range(5)}
        for n in jogo:
            linha = (n - 1) // 5
            linhas[linha] += 1
        return linhas
    
    def validar_jogo(self, jogo):
        pares, _ = self.contar_pares_impares(jogo)
        if pares < self.pares_min or pares > self.pares_max:
            return False
        s = self.soma_total(jogo)
        if s < self.soma_min or s > self.soma_max:
            return False
        dist_linhas = self.linhas(jogo)
        if any(v < self.linhas_min for v in dist_linhas.values()):
            return False
        if any(v > self.linhas_max for v in dist_linhas.values()):
            return False
        return True
    
    def _gerar_jogo_base(self, base_numeros):
        if len(base_numeros) > 15:
            base_numeros = random.sample(base_numeros, 15)
        elif len(base_numeros) < 15:
            restantes = [n for n in range(1, 26) if n not in base_numeros]
            completar = random.sample(restantes, 15 - len(base_numeros))
            base_numeros.extend(completar)
        return sorted(base_numeros)
    
    def gerar_jogo_por_estatistica(self, top_n=15, tipo="frequencia"):
        freq = Counter()
        for c in self.historico:
            freq.update(c)
        atraso = {}
        for num in range(1, 26):
            for i, concurso in enumerate(self.historico):
                if num in concurso:
                    atraso[num] = i
                    break
            else:
                atraso[num] = self.total_concursos
        if tipo == "frequencia":
            numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            base = [n for n, _ in numeros_ordenados[:top_n]]
        elif tipo == "atraso":
            numeros_ordenados = sorted(atraso.items(), key=lambda x: x[1], reverse=True)
            base = [n for n, _ in numeros_ordenados[:top_n]]
        else:
            freq_ord = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            atraso_ord = sorted(atraso.items(), key=lambda x: x[1], reverse=True)
            base_freq = [n for n, _ in freq_ord[:int(top_n * 0.7)]]
            base_atraso = [n for n, _ in atraso_ord[:int(top_n * 0.3)]]
            base = list(set(base_freq + base_atraso))
            random.shuffle(base)
            base = base[:top_n]
        max_tentativas = 5000
        for _ in range(max_tentativas):
            jogo = self._gerar_jogo_base(base[:])
            if self.validar_jogo(jogo):
                return jogo
        return self._gerar_jogo_base(base[:])
    
    def gerar_jogo_aleatorio_estatistico(self):
        max_tentativas = 10000
        for _ in range(max_tentativas):
            jogo = sorted(random.sample(range(1, 26), 15))
            if self.validar_jogo(jogo):
                return jogo
        return None
    
    def gerar_multiplos_jogos(self, quantidade, estrategia="aleatoria"):
        jogos, diagnosticos = [], []
        tentativas = 0
        max_tentativas = quantidade * 10000
        while len(jogos) < quantidade and tentativas < max_tentativas:
            if estrategia == "aleatoria":
                jogo = self.gerar_jogo_aleatorio_estatistico()
            else:
                jogo = self.gerar_jogo_por_estatistica(tipo=estrategia)
            tentativas += 1
            if jogo and jogo not in jogos:
                jogos.append(jogo)
                pares, impares = self.contar_pares_impares(jogo)
                s = self.soma_total(jogo)
                diagnosticos.append({"pares": pares, "impares": impares, "soma": s, "validado": self.validar_jogo(jogo)})
        if len(jogos) < quantidade:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} jogos com a estratégia '{estrategia}'")
        return jogos, diagnosticos

# =====================================================
# FUNÇÕES AUXILIARES (CONTINUAÇÃO)
# =====================================================

def validar_jogos(jogos):
    for i, jogo in enumerate(jogos):
        if len(set(jogo)) != 15:
            return False, i, jogo
    return True, None, None

def formatar_jogo_html(jogo, destaque_primos=True):
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
    if isinstance(jogo, dict):
        for chave in ["dezenas", "Dezenas", "jogo", "Jogo"]:
            if chave in jogo:
                dezenas = jogo[chave]
                break
        else:
            dezenas = []
    elif isinstance(jogo, str):
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

def contar_pares(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def bucket_soma(soma):
    return int(soma // 20)

def log_likelihood(features, dist):
    logL = 0
    for k, v in features.items():
        p = dist.get(k, {}).get(v, 1e-9)
        w = FEATURE_WEIGHTS.get(k, 1.0)
        logL += w * math.log(p)
    return logL

@st.cache_data
def baseline_aleatorio(n=200000):
    acertos = []
    for _ in range(n):
        jogo = set(random.sample(range(1, 26), 15))
        sorteio = set(random.sample(range(1, 26), 15))
        acertos.append(len(jogo & sorteio))
    acertos = np.array(acertos)
    return {"media": acertos.mean(), "std": acertos.std(), "dist": np.bincount(acertos, minlength=16) / n, "descricao": "Interseção 15×15 em universo 25"}

def criar_historico_df(dados_api, qtd_concursos):
    historico = []
    for concurso in dados_api[:qtd_concursos]:
        numeros = sorted(map(int, concurso['dezenas']))
        historico.append({"concurso": concurso['concurso'], "pares": contar_pares(numeros), "primos": contar_primos(numeros), "consecutivos": contar_consecutivos(numeros), "soma": sum(numeros)})
    return pd.DataFrame(historico)

@st.cache_data
def distribuicoes_empiricas(historico_df):
    return {"pares": historico_df["pares"].value_counts(normalize=True).to_dict(), "primos": historico_df["primos"].value_counts(normalize=True).to_dict(), "consecutivos": historico_df["consecutivos"].value_counts(normalize=True).to_dict(), "soma": historico_df["soma"].apply(bucket_soma).value_counts(normalize=True).to_dict()}

FEATURE_WEIGHTS = {"pares": 1.0, "primos": 1.0, "consecutivos": 0.8, "soma": 0.6}

@st.cache_data
def monte_carlo_jogo(jogo_tuple, n_sim):
    jogo = set(jogo_tuple)
    acertos = []
    for _ in range(n_sim):
        sorteio = set(random.sample(range(1, 26), 15))
        acertos.append(len(jogo & sorteio))
    acertos = np.array(acertos)
    return {"P>=11": np.mean(acertos >= 11), "P>=12": np.mean(acertos >= 12), "P>=13": np.mean(acertos >= 13), "P>=14": np.mean(acertos >= 14), "P=15": np.mean(acertos == 15), "media": acertos.mean(), "std": acertos.std()}

def get_jogos_seguros():
    if "jogos_3622" in st.session_state and st.session_state.jogos_3622 is not None:
        if isinstance(st.session_state.jogos_3622, list) and len(st.session_state.jogos_3622) > 0:
            return st.session_state.jogos_3622
    return []

def extrair_jogo_por_indice(jogos_gerados, indice):
    if jogos_gerados is None:
        return []
    if indice < 0 or indice >= len(jogos_gerados):
        return []
    if isinstance(jogos_gerados, pd.DataFrame):
        try:
            jogo_row = jogos_gerados.iloc[indice]
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
    elif isinstance(jogos_gerados, list):
        try:
            item = jogos_gerados[indice]
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
            elif isinstance(item, str):
                if "," in item:
                    return [int(d.strip()) for d in item.split(",")]
                else:
                    return [int(d) for d in item.split()]
            elif isinstance(item, (list, tuple)):
                return [int(d) for d in item]
            return []
        except:
            return []
    return []

# =====================================================
# MÓDULO DE INTELIGÊNCIA: DETECTOR DE SINAL + FILTRO 5-7-3
# =====================================================

def faixa_573(n):
    if 1 <= n <= 8:
        return "baixa"
    elif 9 <= n <= 16:
        return "media"
    else:
        return "alta"

def contar_faixas_573(jogo):
    f = {"baixa": 0, "media": 0, "alta": 0}
    for n in jogo:
        f[faixa_573(n)] += 1
    return f

def paridade_573(jogo):
    pares = sum(1 for n in jogo if n % 2 == 0)
    return pares, 15 - pares

def soma_573(jogo):
    return sum(jogo)

def maior_bloco_consecutivo_573(jogo):
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
    if len(concursos_historico) < 3:
        return False
    recentes = concursos_historico[:lookback]
    sinais_detectados = 0
    altas_excesso_count = 0
    for c in recentes[:3]:
        if contar_faixas_573(c)["alta"] >= 6:
            altas_excesso_count += 1
    if altas_excesso_count >= 2:
        sinais_detectados += 1
    if len(recentes) >= 2:
        medias_baixas_count = 0
        for c in recentes[:2]:
            if contar_faixas_573(c)["media"] <= 5:
                medias_baixas_count += 1
        if medias_baixas_count == 2:
            sinais_detectados += 1
    if len(recentes) >= 2 and all(maior_bloco_consecutivo_573(c) <= 3 for c in recentes[:2]):
        sinais_detectados += 1
    if len(recentes) >= 2:
        soma_fora_count = 0
        for c in recentes[:2]:
            s = soma_573(c)
            if s < 180 or s > 210:
                soma_fora_count += 1
        if soma_fora_count >= 1:
            sinais_detectados += 1
    return sinais_detectados >= 3

def filtro_573_ultra(jogo):
    f = contar_faixas_573(jogo)
    pares, _ = paridade_573(jogo)
    s = soma_573(jogo)
    bloco = maior_bloco_consecutivo_573(jogo)
    padrao_valido = False
    if f["baixa"] == 5 and f["media"] == 7 and f["alta"] == 3:
        padrao_valido = True
    elif f["baixa"] == 5 and f["media"] == 6 and f["alta"] == 4:
        padrao_valido = True
    elif f["baixa"] == 6 and f["media"] == 6 and f["alta"] == 3:
        padrao_valido = True
    elif f["baixa"] == 4 and f["media"] == 7 and f["alta"] == 4:
        padrao_valido = True
    if not padrao_valido:
        return False
    if not (6 <= pares <= 8):
        return False
    if not (185 <= s <= 205):
        return False
    if bloco < 4:
        return False
    altas_frias = sum(1 for n in jogo if n >= 23)
    if altas_frias > 1:
        return False
    medias_centro = {9, 10, 11, 12, 13, 14, 15, 16}
    if len(set(jogo) & medias_centro) < 6:
        return False
    return True

def score_jogo_573(jogo):
    pontos = 0
    f = contar_faixas_573(jogo)
    pares, _ = paridade_573(jogo)
    s = soma_573(jogo)
    bloco = maior_bloco_consecutivo_573(jogo)
    if f["baixa"] == 5 and f["media"] == 7 and f["alta"] == 3:
        pontos += 5
    elif f["baixa"] == 5 and f["media"] == 6 and f["alta"] == 4:
        pontos += 4
    elif f["baixa"] == 6 and f["media"] == 6 and f["alta"] == 3:
        pontos += 4
    elif f["baixa"] == 4 and f["media"] == 7 and f["alta"] == 4:
        pontos += 4
    if f["media"] >= 7:
        pontos += 2
    elif f["media"] == 6:
        pontos += 1
    if bloco >= 5:
        pontos += 2
    elif bloco == 4:
        pontos += 1
    if pares == 7:
        pontos += 1
    elif pares == 8:
        pontos += 0.5
    if 190 <= s <= 200:
        pontos += 2
    elif 185 <= s <= 205:
        pontos += 1
    return pontos

def pipeline_selecao_inteligente(jogos_gerados, concursos_historico, modo_operacao="auto", threshold_score=6):
    sinal_ativo = False
    if modo_operacao == "auto":
        sinal_ativo = detectar_sinal(concursos_historico)
    elif modo_operacao == "forcar_on":
        sinal_ativo = True
    jogos_aprovados = []
    estatisticas = {"total_jogos_analisados": len(jogos_gerados), "sinal_estava_ativo": sinal_ativo, "jogos_filtrados_573": 0, "jogos_reprovados_score": 0, "threshold_score": threshold_score, "jogos_por_padrao": {"5-7-3": 0, "5-6-4": 0, "6-6-3": 0, "4-7-4": 0, "outros": 0}}
    for jogo in jogos_gerados:
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
            if not filtro_573_ultra(jogo):
                passa_pelo_filtro = False
                estatisticas["jogos_filtrados_573"] += 1
        if passa_pelo_filtro:
            if score_jogo_573(jogo) >= threshold_score:
                jogos_aprovados.append(jogo)
            else:
                estatisticas["jogos_reprovados_score"] += 1
    estatisticas["jogos_aprovados"] = len(jogos_aprovados)
    return jogos_aprovados, sinal_ativo, estatisticas

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================

def main():
    # Inicialização dos estados da sessão
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
    if "jogos_teste_intel" not in st.session_state:
        st.session_state.jogos_teste_intel = None
    if "jogos_pro" not in st.session_state:
        st.session_state.jogos_pro = None
    if "diagnosticos_pro" not in st.session_state:
        st.session_state.diagnosticos_pro = None
    if "motor_geometria" not in st.session_state:
        st.session_state.motor_geometria = None
    if "analise_geometrica_jogo" not in st.session_state:
        st.session_state.analise_geometrica_jogo = None
    if "jogos_geometricos" not in st.session_state:
        st.session_state.jogos_geometricos = None
    if "sistema_autonomo" not in st.session_state:
        st.session_state.sistema_autonomo = None
    if "resultado_autonomo" not in st.session_state:
        st.session_state.resultado_autonomo = None
    if "jogos_autonomos_historicos" not in st.session_state:
        st.session_state.jogos_autonomos_historicos = None
    if "diagnosticos_autonomos_historicos" not in st.session_state:
        st.session_state.diagnosticos_autonomos_historicos = None
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
    if "qtd_autonomo" not in st.session_state:
        st.session_state.qtd_autonomo = 10
    if "num_testes_autonomo" not in st.session_state:
        st.session_state.num_testes_autonomo = 30

    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Qtd concursos históricos", 20, 500, 100, help="Mais concursos = melhor análise de tendências")
        if st.button("📥 Carregar concursos", use_container_width=True):
            with st.spinner("Carregando dados da Caixa..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    response = requests.get(url)
                    st.session_state.dados_api = response.json()
                    concursos = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
                    st.session_state.analise = AnaliseLotofacilBasica(concursos, st.session_state.dados_api[:qtd])
                    st.session_state.historico_df = criar_historico_df(st.session_state.dados_api, qtd)
                    st.session_state.baseline_cache = baseline_aleatorio()
                    st.session_state.sistema_autonomo = SistemaAutonomo(concursos)
                    ultimo = st.session_state.dados_api[0]
                    st.success(f"✅ Último concurso: #{ultimo['concurso']} - {ultimo['data']}")
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    # INTERFACE PRINCIPAL
    st.subheader("🎯 Modelo Universal 3622")

    if st.session_state.analise and st.session_state.dados_api and st.session_state.historico_df is not None:
        # DEFINIÇÃO DAS 13 ABAS
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = st.tabs([
            "📊 Análise", 
            "🧩 Fechamento 3622", 
            "📊 Motor Estatístico",
            "📋 Concursos",
            "✅ Conferência",
            "🚀 Gerador 12+",
            "🔥 Gerador 13+",
            "🧠 Inteligência 5-7-3",
            "📡 Detector MASTER B-M-A",
            "🧠 Motor PRO",
            "📐 Geometria Analítica",
            "🤖 Sistema Autônomo",
            "📊 SISTEMA AUTÔNOMO (GERADOR HISTÓRICO)"
        ])

        # =====================================================
        # TAB 1: ANÁLISE
        # =====================================================
        with tab1:
            st.markdown("### 🔍 Análise do Último Concurso")
            ultimo = st.session_state.dados_api[0]
            numeros_ultimo = sorted(map(int, ultimo['dezenas']))
            st.markdown(f"<div class='concurso-info'><strong>Concurso #{ultimo['concurso']}</strong> - {ultimo['data']}</div>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Dezenas sorteadas:**")
                nums_html = "".join(f"<span style='background:#4cc9f0; border-radius:20px; padding:5px 10px; margin:3px; display:inline-block; font-weight:bold; color:black;'>{num:02d}</span>" for num in numeros_ultimo)
                st.markdown(f"<div>{nums_html}</div>", unsafe_allow_html=True)
            with col2:
                pares = sum(1 for n in numeros_ultimo if n % 2 == 0)
                st.metric("Pares/Ímpares", f"{pares}×{15-pares}")
            with col3:
                st.metric("Soma total", sum(numeros_ultimo))
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

        # =====================================================
        # TAB 2: FECHAMENTO 3622
        # =====================================================
        with tab2:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px;'><h4 style='margin:0; color:#4cc9f0;'>🧠 MODELO UNIVERSAL + AJUSTE ADAPTÁVEL</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Baseado na análise do concurso 3622</p></div>", unsafe_allow_html=True)
            with st.expander("📜 VER REGRAS UNIVERSAIS", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**✅ REGRA 1 — REPETIÇÃO**\n- Obrigatório: 8 a 10 repetidas\n- Zona ótima: 8 ou 9\n\n**✅ REGRA 2 — ÍMPARES x PARES**\n- Padrão vencedor: 7×8 ou 8×7\n- Alternativa: 6×9 (raro)\n\n**✅ REGRA 3 — SOMA TOTAL**\n- Faixa universal: 168 a 186\n- Zona premium: 172 a 182")
                with col2:
                    st.markdown("**✅ REGRA 4 — DISTRIBUIÇÃO**\n- 01–08: 5 a 6\n- 09–16: 5 a 6\n- 17–25: 3 a 4\n\n**✅ REGRA 5 — CONSECUTIVOS**\n- Mínimo: 3 pares consecutivos\n\n**✅ REGRA 6 — PRIMOS**\n- Faixa vencedora: 4 a 6 primos")
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                penultimo = st.session_state.dados_api[1] if len(st.session_state.dados_api) > 1 else None
                antepenultimo = st.session_state.dados_api[2] if len(st.session_state.dados_api) > 2 else None
                gerador = Gerador3622(ultimo_concurso=list(map(int, ultimo['dezenas'])), penultimo_concurso=list(map(int, penultimo['dezenas'])) if penultimo else None, antepenultimo_concurso=list(map(int, antepenultimo['dezenas'])) if antepenultimo else None)
                st.session_state.ultimo_gerador = gerador
                ajustes = gerador.get_resumo_ajustes()
                st.markdown("### 🔄 Ajustes Adaptáveis Ativos")
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Repetições alvo", ajustes["repeticoes_alvo"])
                with col2: st.metric("Altas alvo", ajustes["altas_alvo"])
                with col3: st.metric("Miolo alvo", ajustes["miolo_alvo"])
                with col4: st.metric("Sequências", ajustes["tipo_sequencia"])
                st.markdown("### 🎯 Gerar Jogos")
                col1, col2 = st.columns(2)
                with col1:
                    qtd_jogos = st.slider("Quantidade de jogos", 3, 100, value=st.session_state.qtd_3622, key="slider_qtd_3622")
                    st.session_state.qtd_3622 = qtd_jogos
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 GERAR JOGOS 3622", use_container_width=True, type="primary"):
                        with st.spinner(f"Gerando {qtd_jogos} jogos com validação completa..."):
                            jogos, diagnosticos = gerador.gerar_multiplos_jogos(qtd_jogos)
                            valido, idx, jogo_invalido = validar_jogos(jogos)
                            if not valido:
                                st.error(f"ERRO: Jogo {idx+1} inválido! Corrigindo...")
                                jogos[idx] = sorted(list(set(jogo_invalido)))
                                while len(jogos[idx]) < 15:
                                    novo = random.randint(1, 25)
                                    if novo not in jogos[idx]:
                                        jogos[idx].append(novo)
                                jogos[idx].sort()
                            st.session_state.jogos_3622 = jogos
                            st.session_state.diagnosticos_3622 = diagnosticos
                            st.session_state.mc_resultados = None
                            st.success(f"✅ {len(jogos)} jogos gerados com sucesso!")
                if "jogos_3622" in st.session_state and st.session_state.jogos_3622:
                    jogos = st.session_state.jogos_3622
                    diagnosticos = st.session_state.diagnosticos_3622 if "diagnosticos_3622" in st.session_state else [None] * len(jogos)
                    st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                    stats_df = pd.DataFrame({"Jogo": range(1, len(jogos)+1), "Repetidas": [len(set(j) & set(gerador.ultimo)) for j in jogos], "Pares": [sum(1 for n in j if n%2==0) for j in jogos], "Soma": [sum(j) for j in jogos], "Baixas": [sum(1 for n in j if n in gerador.faixa_baixa) for j in jogos], "Médias": [sum(1 for n in j if n in gerador.faixa_media) for j in jogos], "Altas": [sum(1 for n in j if n in gerador.faixa_alta) for j in jogos], "Consec": [gerador._contar_sequencias(j) for j in jogos], "Primos": [sum(1 for n in j if n in gerador.primos) for j in jogos], "Falhas": [d["falhas"] if d else 0 for d in diagnosticos]})
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    for i, (jogo, diag) in enumerate(zip(jogos, diagnosticos)):
                        cor_borda = "#4ade80" if diag and diag["falhas"] == 0 else "gold" if diag and diag["falhas"] == 1 else "#4cc9f0"
                        nums_html = formatar_jogo_html(jogo)
                        rep = len(set(jogo) & set(gerador.ultimo))
                        pares = sum(1 for n in jogo if n%2==0)
                        soma = sum(jogo)
                        st.markdown(f"<div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'><strong>Jogo {i+1:2d}:</strong> {nums_html}<br><small style='color:#aaa;'>🔁 {rep} rep | ⚖️ {pares}×{15-pares} | ➕ {soma} | ✅ Falhas: {diag['falhas'] if diag else '?'}</small></div>", unsafe_allow_html=True)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos", key="salvar_3622", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_gerados(jogos, list(range(1,18)), {"modelo": "3622", "ajustes": ajustes}, ultimo['concurso'], ultimo['data'])
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
                        df_export = pd.DataFrame({"Jogo": range(1, len(jogos)+1), "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos], "Repetidas": stats_df["Repetidas"], "Pares": stats_df["Pares"], "Soma": stats_df["Soma"], "Baixas(01-08)": stats_df["Baixas"], "Medias(09-16)": stats_df["Médias"], "Altas(17-25)": stats_df["Altas"], "Consecutivos": stats_df["Consec"], "Primos": stats_df["Primos"]})
                        csv = df_export.to_csv(index=False)
                        st.download_button(label="📥 Exportar CSV", data=csv, file_name=f"jogos_3622_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)

        # =====================================================
        # TAB 3: MOTOR ESTATÍSTICO (SIMPLIFICADO)
        # =====================================================
        with tab3:
            st.subheader("📊 Motor Estatístico - Avaliação Probabilística")
            st.info("Para visualizar o Motor Estatístico completo, gere jogos na aba 'Fechamento 3622' primeiro.")
            st.markdown("---")
            st.markdown("### 📈 Distribuições Empíricas")
            dist = distribuicoes_empiricas(st.session_state.historico_df)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Pares x Ímpares**")
                pares_df = pd.DataFrame({"Quantidade": list(dist['pares'].keys()), "Probabilidade": list(dist['pares'].values())}).sort_values("Quantidade")
                st.bar_chart(pares_df.set_index("Quantidade"))
            with col2:
                st.markdown("**Números Primos**")
                primos_df = pd.DataFrame({"Quantidade": list(dist['primos'].keys()), "Probabilidade": list(dist['primos'].values())}).sort_values("Quantidade")
                st.bar_chart(primos_df.set_index("Quantidade"))

        # =====================================================
        # TAB 4: CONCURSOS
        # =====================================================
        with tab4:
            st.subheader("📋 Todos os Concursos Carregados")
            if st.session_state.dados_api:
                st.markdown(f"<div class='concurso-info'>📊 <strong>Total de concursos carregados: {len(st.session_state.dados_api[:qtd])}</strong></div>", unsafe_allow_html=True)
                col1, col2 = st.columns([3,1])
                with col1:
                    busca = st.text_input("🔍 Buscar concurso específico (número ou data)", placeholder="Ex: 3000 ou 2024...")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📥 Download TXT", use_container_width=True):
                        conteudo_txt = exportar_concursos_txt(st.session_state.dados_api, qtd)
                        st.download_button(label="⬇️ Baixar arquivo", data=conteudo_txt, file_name=f"lotofacil_concursos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain", use_container_width=True)
                dados_filtrados = st.session_state.dados_api[:qtd]
                if busca:
                    dados_filtrados = [c for c in dados_filtrados if busca.lower() in str(c['concurso']).lower() or busca.lower() in c['data'].lower()]
                for concurso in dados_filtrados:
                    with st.container():
                        col1, col2 = st.columns([1,3])
                        with col1:
                            st.markdown(f"**#{concurso['concurso']}**")
                            st.caption(concurso['data'])
                        with col2:
                            numeros = sorted(map(int, concurso['dezenas']))
                            nums_html = ""
                            for num in numeros:
                                cor = "#4cc9f0" if num <= 5 else "#4ade80" if num <= 10 else "gold" if num <= 15 else "#f97316" if num <= 20 else "#ff6b6b"
                                nums_html += f"<span style='background:{cor}20; border:1px solid {cor}; border-radius:20px; padding:5px 10px; margin:3px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
                            st.markdown(f"<div>{nums_html}</div>", unsafe_allow_html=True)
                        st.divider()
                if len(dados_filtrados) > 50:
                    st.caption(f"Mostrando {len(dados_filtrados)} concursos. Use a busca para encontrar um específico.")
            else:
                st.info("📥 Carregue os concursos usando o botão na barra lateral para visualizar a lista completa.")

        # =====================================================
        # TAB 5: CONFERÊNCIA
        # =====================================================
        with tab5:
            st.subheader("✅ Conferência por Concurso")
            st.session_state.jogos_salvos = carregar_jogos_salvos()
            if not st.session_state.jogos_salvos:
                st.warning("Nenhum fechamento salvo. Gere jogos na aba 'Fechamento 3622'.")
            else:
                opcoes = [f"ID {j['id']} | Concurso Base #{j['concurso_base']['numero']} | {j['data_geracao'][:19]}" for j in st.session_state.jogos_salvos]
                if st.session_state.idx_fechamento_conferencia >= len(opcoes):
                    st.session_state.idx_fechamento_conferencia = 0
                idx = st.selectbox("📦 Selecione o fechamento", range(len(opcoes)), format_func=lambda i: opcoes[i], index=st.session_state.idx_fechamento_conferencia, key="select_fechamento_conferencia")
                st.session_state.idx_fechamento_conferencia = idx
                fechamento = st.session_state.jogos_salvos[idx]
                jogos_brutos = fechamento["jogos"]
                jogos = normalizar_jogos(jogos_brutos)
                valido, mensagem = validar_jogos_normalizados(jogos)
                if not valido:
                    st.error(f"❌ Erro na estrutura dos jogos: {mensagem}")
                    st.stop()
                st.markdown(f"<div class='concurso-info'>📦 <strong>Fechamento ID:</strong> {fechamento['id']}<br>🎯 <strong>Total de jogos:</strong> {len(jogos)}</div>", unsafe_allow_html=True)
                concursos = st.session_state.dados_api
                concurso_escolhido = st.selectbox("🎯 Selecione o concurso para conferência", concursos, format_func=lambda c: f"#{c['concurso']} - {c['data']}")
                dezenas_sorteadas = sorted(map(int, concurso_escolhido["dezenas"]))
                dezenas_set = set(dezenas_sorteadas)
                st.markdown("### 🔢 Resultado Oficial")
                st.markdown(formatar_jogo_html(dezenas_sorteadas), unsafe_allow_html=True)
                if st.button("🔍 CONFERIR FECHAMENTO", type="primary", use_container_width=True):
                    resultados, distribuicao = [], Counter()
                    for i, dezenas_jogo in enumerate(jogos):
                        acertos = len(set(dezenas_jogo) & dezenas_set)
                        distribuicao[acertos] += 1
                        resultados.append({"Jogo": i+1, "Acertos": acertos, "Dezenas": ", ".join(f"{n:02d}" for n in sorted(dezenas_jogo))})
                    if not resultados:
                        st.error("❌ Nenhum jogo válido encontrado para conferência")
                    else:
                        df_resultado = pd.DataFrame(resultados).sort_values("Acertos", ascending=False)
                        estatisticas = {"distribuicao": dict(distribuicao), "melhor_jogo": int(df_resultado.iloc[0]["Jogo"]), "maior_acerto": int(df_resultado.iloc[0]["Acertos"]), "total_jogos_validos": len(resultados)}
                        adicionar_conferencia(fechamento["arquivo"], {"numero": concurso_escolhido["concurso"], "data": concurso_escolhido["data"]}, df_resultado["Acertos"].tolist(), estatisticas)
                        st.success(f"✅ Conferência realizada e salva com sucesso! ({len(resultados)} jogos válidos)")
                        col1, col2, col3 = st.columns(3)
                        col1.metric("🏆 Melhor jogo", f"Jogo {estatisticas['melhor_jogo']}")
                        col2.metric("🎯 Maior acerto", estatisticas["maior_acerto"])
                        col3.metric("📊 Jogos válidos", estatisticas["total_jogos_validos"])
                        st.markdown("### 📊 Distribuição de Acertos")
                        dist_df = pd.DataFrame(sorted(distribuicao.items()), columns=["Acertos", "Quantidade"])
                        st.bar_chart(dist_df.set_index("Acertos"))
                        st.markdown("### 🏅 Ranking dos Jogos")
                        st.dataframe(df_resultado[["Jogo","Acertos","Dezenas"]], use_container_width=True, hide_index=True, column_config={"Dezenas": st.column_config.TextColumn("Dezenas", width="large")})

        # =====================================================
        # TAB 6: GERADOR 12+
        # =====================================================
        with tab6:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px;'><h4 style='margin:0; color:#4ade80;'>🚀 GERADOR 12+ (MODELO COBERTURA)</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Baseado na análise dos últimos 20 concursos • Foco em 12+ pontos</p></div>", unsafe_allow_html=True)
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                ultimos_concursos = [sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:20]]
                gerador_12plus = Gerador12Plus(concursos_historico=ultimos_concursos, ultimo_concurso=numeros_ultimo)
                st.markdown("### 📊 Estatísticas dos Últimos 20 Concursos")
                stats = gerador_12plus.get_estatisticas_recentes()
                if stats:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.metric("Média Baixas", f"{stats['baixas']:.1f}")
                    with col2: st.metric("Média Médias", f"{stats['medias']:.1f}")
                    with col3: st.metric("Média Altas", f"{stats['altas']:.1f}")
                    with col4: st.metric("Média Soma", f"{stats['soma']:.1f}")
                st.markdown("### 🎯 Gerar Jogos 12+")
                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    qtd_jogos_12plus = st.slider("Quantidade de jogos", min_value=3, max_value=50, value=st.session_state.qtd_12plus, key="slider_qtd_12plus")
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
                if "jogos_12plus" in st.session_state and st.session_state.jogos_12plus:
                    jogos = st.session_state.jogos_12plus
                    st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                    for i, jogo in enumerate(jogos):
                        nums_html = formatar_jogo_html(jogo)
                        st.markdown(f"<div style='border-left: 5px solid #4ade80; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'><strong>Jogo {i+1:2d}:</strong> {nums_html}</div>", unsafe_allow_html=True)

        # =====================================================
        # TAB 7: GERADOR 13+
        # =====================================================
        with tab7:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #f97316;'><h4 style='margin:0; color:#f97316;'>🔥 GERADOR 13+ (MODELO ULTRA)</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Zona de convergência máxima • Tiro de precisão para 13+ pontos</p></div>", unsafe_allow_html=True)
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                ultimos_concursos = [sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:20]]
                gerador_13plus = Gerador13Plus(concursos_historico=ultimos_concursos, ultimo_concurso=numeros_ultimo)
                st.markdown("### 🎯 Gerar Jogos 13+ (Precisão)")
                st.caption("⚠️ Modelo extremamente restritivo. Pode levar alguns segundos para encontrar jogos válidos.")
                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    qtd_jogos_13plus = st.slider("Quantidade de jogos", min_value=1, max_value=20, value=st.session_state.qtd_13plus, key="slider_qtd_13plus")
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
                if "jogos_13plus" in st.session_state and st.session_state.jogos_13plus:
                    jogos = st.session_state.jogos_13plus
                    st.markdown(f"### 📋 Jogos 13+ Gerados ({len(jogos)})")
                    for i, jogo in enumerate(jogos):
                        nums_html = formatar_jogo_html(jogo)
                        st.markdown(f"<div style='border-left: 5px solid #f97316; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'><strong>🔥 Jogo 13+ #{i+1:2d}:</strong> {nums_html}</div>", unsafe_allow_html=True)

        # =====================================================
        # TAB 8: INTELIGÊNCIA 5-7-3
        # =====================================================
        with tab8:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #aa00ff;'><h4 style='margin:0; color:#aa00ff;'>🧠 MODO INTELIGENTE 5-7-3</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Detector de Sinal Automático + Filtro de Elite com os 4 padrões prioritários</p></div>", unsafe_allow_html=True)
            st.info("Para utilizar o MODO INTELIGENTE 5-7-3, gere jogos primeiro nas abas de geradores.")

        # =====================================================
        # TAB 9: DETECTOR MASTER DE PADRÕES B-M-A
        # =====================================================
        with tab9:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #ffaa00;'><h4 style='margin:0; color:#ffaa00;'>📡 DETECTOR MASTER DE PADRÕES B-M-A</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Análise completa de padrões Baixa-Média-Alta com detecção de atrasos</p></div>", unsafe_allow_html=True)
            if st.session_state.dados_api:
                todos_concursos = [sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:qtd]]
                ultimo = st.session_state.dados_api[0]
                numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                padrao_ultimo = contar_bma(numeros_ultimo)
                st.markdown("### 🎯 Último Concurso Analisado")
                col1, col2, col3 = st.columns([1,2,1])
                with col1: st.metric("Concurso", f"#{ultimo['concurso']}")
                with col2: st.markdown(f"<div style='text-align:center; background:#0e1117; padding:10px; border-radius:10px;'><span style='font-size:1.2rem;'>Padrão B-M-A</span><br><span style='font-size:2rem; font-weight:bold; color:#ffaa00;'>{padrao_ultimo[0]}-{padrao_ultimo[1]}-{padrao_ultimo[2]}</span></div>", unsafe_allow_html=True)
                with col3: st.metric("Data", ultimo['data'][:10])
                st.markdown("### 🚨 Sinais de Atraso Detectados")
                sinais = detector_sinais(todos_concursos, limiar=1.5)
                if sinais:
                    for sinal in sinais:
                        padrao_str = f"{sinal['padrao'][0]}-{sinal['padrao'][1]}-{sinal['padrao'][2]}"
                        cor = "#ff6b6b" if sinal['nivel'] == "🚨 FORTE" else "#ffaa00" if sinal['nivel'] == "⚠️ MÉDIO" else "#4cc9f0"
                        st.markdown(f"<div style='border-left: 5px solid {cor}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'><div style='display:flex; justify-content:space-between;'><strong style='color:{cor};'>{sinal['nivel']}</strong><span>Padrão <strong style='font-size:1.2rem;'>{padrao_str}</strong></span></div><div style='display:flex; gap:20px; margin-top:10px; flex-wrap:wrap;'><span>📊 Frequência: {sinal['frequencia']}x</span><span>⏱️ Ciclo médio: {sinal['ciclo_medio']} concursos</span><span>⌛ Atraso atual: <strong>{sinal['atraso']}</strong> concursos</span><span>📈 Intensidade: {sinal['intensidade']}x</span></div></div>", unsafe_allow_html=True)
                else:
                    st.info("Nenhum padrão significativamente atrasado detectado no momento.")
                st.markdown("### 🎯 Monitoramento de Padrões Específicos")
                alvos = detector_alvos(todos_concursos)
                for _, row in pd.DataFrame(alvos).iterrows():
                    col1, col2, col3, col4, col5 = st.columns([1,1,1,1,2])
                    with col1: st.markdown(formatar_padrao_html(row['padrao']), unsafe_allow_html=True)
                    with col2: st.markdown(f"**{row['total']}**")
                    with col3: st.markdown(f"**{row['ultimos_10']}**")
                    with col4: st.markdown(f"**{row['atraso']}**")
                    with col5: st.markdown(f"<span style='color:{row['cor']}; font-weight:bold;'>{row['status']}</span>", unsafe_allow_html=True)
                st.markdown("### 📊 Top 15 Padrões Mais Frequentes")
                top_padroes = top_padroes_frequentes(todos_concursos, n=15)
                df_top = pd.DataFrame(top_padroes)
                st.dataframe(df_top, use_container_width=True, hide_index=True)

        # =====================================================
        # TAB 10: MOTOR PRO
        # =====================================================
        with tab10:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #ff00ff;'><h4 style='margin:0; color:#ff00ff;'>🧠 MOTOR LOTOFÁCIL PRO (6 CAMADAS)</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Frequência + Atraso + Geometria + Estatística + Filtros + Gerador Inteligente</p></div>", unsafe_allow_html=True)
            st.info("Para utilizar o Motor PRO, carregue os concursos e gere jogos.")

        # =====================================================
        # TAB 11: GEOMETRIA ANALÍTICA
        # =====================================================
        with tab11:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #00ffaa;'><h4 style='margin:0; color:#00ffaa;'>📐 GEOMETRIA ANALÍTICA DO TABULEIRO</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Matriz de co-ocorrência • Centroides • Entropia • Grafos de relação</p></div>", unsafe_allow_html=True)
            if st.session_state.dados_api:
                qtd_historico = qtd
                historico_selecionado = [sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:qtd_historico]]
                st.info(f"📊 Analisando **{qtd_historico}** concursos históricos (baseado na sua seleção de {qtd} concursos)")
                if st.session_state.motor_geometria is None or len(historico_selecionado) != st.session_state.motor_geometria.total_concursos:
                    st.session_state.motor_geometria = MotorGeometriaAvancada(historico_selecionado)
                motor = st.session_state.motor_geometria
                st.markdown("### 🎲 Tabuleiro Lotofácil (5x5)")
                tabuleiro_html = "<table style='width:100%; border-collapse:collapse; text-align:center;'>"
                for i in range(5):
                    tabuleiro_html += "患"
                    for j in range(5):
                        num = motor.volante[i][j]
                        freq = motor.frequencias[num]
                        max_freq = max(motor.frequencias) if max(motor.frequencias) > 0 else 1
                        intensidade = min(255, int(100 + 155 * (freq / max_freq)))
                        cor = f"rgba({intensidade}, 100, 200, 0.3)"
                        tabuleiro_html += f"<td style='border:1px solid #444; padding:12px; background:{cor};'><strong>{num:02d}</strong>脉"
                    tabuleiro_html += "缁"
                tabuleiro_html += "缁"
                st.markdown(tabuleiro_html, unsafe_allow_html=True)
                st.caption("Intensidade da cor representa frequência histórica")
                st.markdown("### 📊 Estatísticas Globais")
                stats_geo = motor.get_estatisticas_geometricas()
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Centroide Médio", f"({stats_geo['centroide_medio'][0]}, {stats_geo['centroide_medio'][1]})")
                with col2: st.metric("Entropia Global", f"{stats_geo['entropia_global']:.3f}")
                with col3: st.metric("Pares Fortes", stats_geo['total_pares_fortes'])
                with col4: st.metric("Max Co-ocorrência", stats_geo['max_coocorrencia'])
            else:
                st.info("📥 Carregue os concursos na barra lateral para ativar a Geometria Analítica.")

        # =====================================================
        # TAB 12: SISTEMA AUTÔNOMO
        # =====================================================
        with tab12:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #ff6600;'><h4 style='margin:0; color:#ff6600;'>🤖 SISTEMA AUTÔNOMO</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Auto-estratégia: testa frequência, atraso, híbrida e aleatória, escolhe a melhor e gera jogos</p></div>", unsafe_allow_html=True)
            if st.session_state.dados_api and st.session_state.sistema_autonomo:
                st.markdown("### ⚙️ Configuração da Geração")
                col1, col2 = st.columns(2)
                with col1:
                    qtd_autonomo = st.slider("Quantidade de jogos a gerar", min_value=5, max_value=50, value=st.session_state.qtd_autonomo, step=5, key="slider_qtd_autonomo")
                    st.session_state.qtd_autonomo = qtd_autonomo
                with col2:
                    num_testes = st.slider("Número de testes no backtest", min_value=20, max_value=100, value=st.session_state.num_testes_autonomo, step=10, key="slider_testes_autonomo", help="Mais testes = mais preciso, porém mais lento")
                    st.session_state.num_testes_autonomo = num_testes
                if st.button("🚀 EXECUTAR SISTEMA AUTÔNOMO", type="primary", use_container_width=True):
                    progress_bar = st.progress(0, text="Inicializando sistema autônomo...")
                    status_text = st.empty()
                    def update_progress(progress, message):
                        progress_bar.progress(progress, text=message)
                        status_text.text(message)
                    with st.spinner("Executando backtest e gerando jogos..."):
                        try:
                            st.session_state.sistema_autonomo.num_testes = num_testes
                            resultado = st.session_state.sistema_autonomo.sistema_autonomo_completo(qtd_jogos=qtd_autonomo, progress_callback=update_progress)
                            st.session_state.resultado_autonomo = resultado
                            progress_bar.progress(1.0, text="✅ Sistema autônomo concluído!")
                            status_text.success("✅ Sistema autônomo executado com sucesso!")
                        except Exception as e:
                            st.error(f"❌ Erro ao executar sistema autônomo: {e}")
                            progress_bar.empty()
                            status_text.empty()
                if st.session_state.resultado_autonomo:
                    resultado = st.session_state.resultado_autonomo
                    st.markdown("---")
                    st.markdown("## 📊 RESULTADOS DO SISTEMA AUTÔNOMO")
                    st.markdown(f"""
                    <div style='background:#1e1e2e; padding:20px; border-radius:15px; margin-bottom:20px; text-align:center; border:2px solid #ff6600;'>
                        <h3 style='margin:0; color:#ff6600;'>🏆 MELHOR ESTRATÉGIA</h3>
                        <p style='font-size:2rem; font-weight:bold; margin:10px 0; color:#fff;'>{resultado['melhor_estrategia']}</p>
                        <p style='font-size:1.2rem; color:#4ade80;'>Score médio: {resultado['melhor_score']:.2f} acertos</p>
                        <p style='color:#aaa;'>Base de {len(resultado['base_utilizada'])} números selecionados</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("### 📈 Score das Estratégias Testadas")
                    scores_data = [{"Estratégia": nome, "Score Médio": round(score,2)} for nome, score in resultado['todos_scores'].items()]
                    df_scores = pd.DataFrame(scores_data).sort_values("Score Médio", ascending=False)
                    st.bar_chart(df_scores.set_index("Estratégia"))
                    st.markdown("### 🎲 Jogos Gerados")
                    for i, jogo in enumerate(resultado['jogos']):
                        nums_html = formatar_jogo_html(jogo)
                        st.markdown(f"<div style='border-left: 5px solid #ff6600; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'><strong>🤖 Jogo Autônomo #{i+1}</strong><br>{nums_html}</div>", unsafe_allow_html=True)
            else:
                st.info("📥 Carregue os concursos na barra lateral para ativar o Sistema Autônomo.")

        # =====================================================
        # TAB 13: SISTEMA AUTÔNOMO (GERADOR HISTÓRICO) - NOVA ABA
        # =====================================================
        with tab13:
            st.markdown("<div style='background:#1e1e2e; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #00ffaa;'><h4 style='margin:0; color:#00ffaa;'>📊 SISTEMA AUTÔNOMO (GERADOR HISTÓRICO)</h4><p style='margin:5px 0 0 0; font-size:0.9em;'>Gerador de jogos baseado no histórico de concursos, aplicando os filtros do estudo original</p></div>", unsafe_allow_html=True)
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                numeros_ultimo = sorted(map(int, ultimo['dezenas']))
                todos_concursos = [sorted(map(int, c['dezenas'])) for c in st.session_state.dados_api[:qtd]]
                gerador_autonomo = GeradorAutonomoHistorico(todos_concursos, numeros_ultimo)
                st.markdown("### 🎲 Configuração da Geração")
                estrategia = st.selectbox(
                    "Estratégia de seleção de números:",
                    ["aleatoria", "frequencia", "atraso", "mistura"],
                    format_func=lambda x: {
                        "aleatoria": "🎲 Aleatória (segue os filtros)",
                        "frequencia": "🔥 Números mais frequentes (quentes)",
                        "atraso": "⏱️ Números mais atrasados (frios)",
                        "mistura": "🧬 Mistura (70% quentes + 30% frios)"
                    }.get(x, x),
                    key="estrategia_autonoma_historica"
                )
                col1, col2 = st.columns(2)
                with col1:
                    qtd_jogos_auto = st.slider("Quantidade de jogos a gerar", min_value=5, max_value=100, value=15, step=5, key="slider_qtd_auto_historica")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 GERAR JOGOS", key="gerar_auto_historica", use_container_width=True, type="primary"):
                        with st.spinner(f"Gerando {qtd_jogos_auto} jogos com estratégia '{estrategia}'..."):
                            jogos, diagnosticos = gerador_autonomo.gerar_multiplos_jogos(qtd_jogos_auto, estrategia=estrategia)
                            if jogos:
                                st.session_state.jogos_autonomos_historicos = jogos
                                st.session_state.diagnosticos_autonomos_historicos = diagnosticos
                                st.success(f"✅ {len(jogos)} jogos gerados com sucesso!")
                            else:
                                st.error("❌ Não foi possível gerar jogos válidos. Tente novamente.")
                if "jogos_autonomos_historicos" in st.session_state and st.session_state.jogos_autonomos_historicos:
                    jogos = st.session_state.jogos_autonomos_historicos
                    diagnosticos = st.session_state.diagnosticos_autonomos_historicos if "diagnosticos_autonomos_historicos" in st.session_state else [None] * len(jogos)
                    st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                    stats_df = pd.DataFrame({
                        "Jogo": range(1, len(jogos)+1),
                        "Pares": [d['pares'] if d else 0 for d in diagnosticos],
                        "Ímpares": [d['impares'] if d else 0 for d in diagnosticos],
                        "Soma": [d['soma'] if d else 0 for d in diagnosticos],
                        "Validado": [d['validado'] if d else False for d in diagnosticos]
                    })
                    validados = stats_df[stats_df["Validado"] == True].shape[0]
                    st.markdown(f"**Jogos que passaram em todos os filtros:** {validados}/{len(jogos)}")
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
                    for i, (jogo, diag) in enumerate(zip(jogos, diagnosticos)):
                        cor_borda = "#4ade80" if diag and diag['validado'] else "#f97316"
                        nums_html = formatar_jogo_html(jogo)
                        st.markdown(f"""
                        <div style='border-left: 5px solid {cor_borda}; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                            <div style='display:flex; justify-content:space-between;'>
                                <strong>Jogo #{i+1:2d}</strong>
                                <small style='color:{"#4ade80" if diag and diag["validado"] else "#f97316"}'>
                                    {'✅ Válido' if diag and diag["validado"] else '⚠️ Filtro não passou'}
                                </small>
                            </div>
                            <div>{nums_html}</div>
                            <div style='display:flex; gap:15px; margin-top:8px; color:#aaa; font-size:0.9em; flex-wrap:wrap;'>
                                <span>⚖️ {diag['pares']}×{diag['impares']}</span>
                                <span>➕ {diag['soma']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Salvar Jogos", key="salvar_auto_historica", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_gerados(jogos, list(range(1,18)), {"modelo": "Sistema Autônomo Histórico", "estrategia": estrategia, "concursos_analisados": qtd}, ultimo['concurso'], ultimo['data'], {"validados": validados, "estatisticas": stats_df.to_dict()})
                            if arquivo:
                                st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                                st.session_state.jogos_salvos = carregar_jogos_salvos()
                    with col2:
                        if st.button("🔄 Nova Geração", key="nova_auto_historica", use_container_width=True):
                            st.session_state.jogos_autonomos_historicos = None
                            st.rerun()
                    with col3:
                        df_export_auto = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Pares": stats_df["Pares"],
                            "Ímpares": stats_df["Ímpares"],
                            "Soma": stats_df["Soma"],
                            "Validado": stats_df["Validado"]
                        })
                        csv_auto = df_export_auto.to_csv(index=False)
                        st.download_button(label="📥 Exportar CSV", data=csv_auto, file_name=f"jogos_autonomos_historicos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)
                    with st.expander("📘 Como funciona o Sistema Autônomo (Gerador Histórico)?"):
                        st.markdown(f"""
                        ### 🤖 Sistema Autônomo baseado em Histórico
                        
                        **Como funciona:**
                        1. Analisa os **{qtd}** concursos históricos carregados
                        2. Permite escolher a **estratégia** de seleção de números:
                           - **Aleatória:** Gera jogos aleatórios e aplica os filtros
                           - **Frequência:** Prioriza os números que mais saíram no histórico
                           - **Atraso:** Prioriza os números que estão há mais tempo sem sair
                           - **Mistura:** Combina 70% dos números frequentes com 30% dos atrasados
                        3. Aplica os **filtros do estudo original**:
                           - Pares/Ímpares: 7 a 8 pares
                           - Soma total: 180 a 230
                           - Distribuição por linhas: 2 a 4 números por linha
                        
                        **Vantagens:**
                        - Utiliza dados reais do histórico
                        - Respeita os padrões estatísticos
                        - Totalmente automático
                        - Permite testar diferentes estratégias
                        """)
            else:
                st.info("📥 Carregue os concursos na barra lateral para ativar o Gerador Autônomo Histórico.")

    else:
        st.info("📥 Clique no botão 'Carregar concursos' na barra lateral para começar.")

if __name__ == "__main__":
    main()

# Rodapé Premium Neon
st.markdown("""
<style>
.footer-premium{
    width:100%;
    text-align:center;
    padding:22px 10px;
    margin-top:40px;
    background:linear-gradient(180deg,#0b0b0b,#050505);
    color:#ffffff;
    font-family:Arial, Helvetica, sans-serif;
    border-top:1px solid #222;
    position:relative;
}
.footer-premium::before{
    content:"";
    position:absolute;
    top:0;
    left:0;
    width:100%;
    height:2px;
    background:linear-gradient(90deg,#00ffcc,#00aaff,#00ffcc);
    box-shadow:0 0 10px #00ffcc;
}
.footer-title{
    font-size:16px;
    font-weight:800;
    letter-spacing:3px;
    text-transform:uppercase;
    text-shadow:0 0 6px rgba(0,255,200,0.6);
}
.footer-sub{
    font-size:11px;
    color:#bfbfbf;
    margin-top:4px;
    letter-spacing:1.5px;
}
</style>
<div class="footer-premium">
    <div class="footer-title">ELITE MASTER SYSTEM</div>
    <div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div>
</div>
""", unsafe_allow_html=True)
