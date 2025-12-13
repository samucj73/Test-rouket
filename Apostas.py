import streamlit as st
import requests
import numpy as np
import random
import pandas as pd
from collections import Counter
from catboost import CatBoostClassifier
import json
import io
import math
from scipy import stats
import itertools

st.set_page_config(page_title="Lotofácil Inteligente", layout="centered")

# =========================
# Captura concursos via API (robusta)
# =========================
def capturar_ultimos_resultados(qtd=250):
    url_base = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
    concursos = []

    try:
        resp = requests.get(url_base, timeout=20)
        if resp.status_code != 200:
            st.error("Erro ao buscar o último concurso.")
            return [], None

        dados = resp.json()
        ultimo = dados[0] if isinstance(dados, list) else dados

        numero_atual = int(ultimo.get("concurso"))
        data_concurso = ultimo.get("data")
        # A API pode devolver 'dezenas' ou 'resultado' em formatos diferentes.
        if "dezenas" in ultimo:
            dezenas = sorted([int(d) for d in ultimo.get("dezenas")])
        elif "resultado" in ultimo:
            # Pode ser string "01 02 ..." ou lista de ints
            res = ultimo.get("resultado")
            if isinstance(res, str):
                dezenas = sorted([int(x) for x in res.split() if x.strip()])
            else:
                dezenas = sorted([int(x) for x in res])
        else:
            dezenas = []

        concursos.append(dezenas)

        info_ultimo = {
            "numero": numero_atual,
            "data": data_concurso,
            "dezenas": dezenas
        }

        for i in range(1, qtd):
            concurso_numero = numero_atual - i
            try:
                resp_i = requests.get(f"{url_base}{concurso_numero}", timeout=20)
                if resp_i.status_code == 200:
                    dados_i = resp_i.json()
                    data_i = dados_i[0] if isinstance(dados_i, list) else dados_i
                    if "dezenas" in data_i:
                        dezenas_i = sorted([int(d) for d in data_i.get("dezenas")])
                    elif "resultado" in data_i:
                        res_i = data_i.get("resultado")
                        if isinstance(res_i, str):
                            dezenas_i = sorted([int(x) for x in res_i.split() if x.strip()])
                        else:
                            dezenas_i = sorted([int(x) for x in res_i])
                    else:
                        dezenas_i = []
                    concursos.append(dezenas_i)
                else:
                    break
            except Exception:
                break

        return concursos, info_ultimo

    except Exception as e:
        st.error(f"Erro ao acessar API: {type(e).__name__}: {e}")
        return [], None

# =========================
# NOVA CLASSE: Estratégias Avançadas de Geração
# =========================
class EstrategiasAvancadas:
    def __init__(self, concursos):
        self.concursos = concursos if concursos else []
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        self.fibonacci = {1, 2, 3, 5, 8, 13, 21}
        self.multiplos_5 = {5, 10, 15, 20, 25}
        self.quadrados = {1, 4, 9, 16, 25}
        
    def calcular_raiz_digital(self, numero):
        """Calcula raiz digital de um número"""
        while numero > 9:
            numero = sum(int(d) for d in str(numero))
        return numero
    
    def analise_raiz_digital(self):
        """Analisa padrões de raiz digital nos concursos"""
        if not self.concursos:
            return {i: 0 for i in range(1, 10)}
        
        resultados = []
        concursos_analisar = self.concursos[:min(100, len(self.concursos))]
        
        for concurso in concursos_analisar:
            raizes = [self.calcular_raiz_digital(n) for n in concurso]
            contagem = Counter(raizes)
            resultados.append(contagem)
        
        # Média de distribuição
        distribuicao_media = {i: 0 for i in range(1, 10)}
        for resultado in resultados:
            for raiz, count in resultado.items():
                distribuicao_media[raiz] += count
        for raiz in distribuicao_media:
            if len(resultados) > 0:
                distribuicao_media[raiz] /= len(resultados)
        
        return distribuicao_media
    
    def analise_quadrantes(self):
        """Analisa distribuição por quadrantes do cartão"""
        # Definir quadrantes do cartão 5x5
        quadrantes = {
            'Q1': [1, 2, 3, 6, 7, 8, 11, 12, 13],           # Superior esquerdo
            'Q2': [4, 5, 9, 10, 14, 15],                    # Superior direito
            'Q3': [16, 17, 18, 21, 22, 23],                 # Inferior esquerdo
            'Q4': [19, 20, 24, 25]                          # Inferior direito
        }
        
        if not self.concursos:
            return quadrantes, {k: 0 for k in quadrantes.keys()}, []
        
        distribuicoes = []
        concursos_analisar = self.concursos[:min(50, len(self.concursos))]
        
        for concurso in concursos_analisar:
            dist = {}
            for q_name, q_nums in quadrantes.items():
                dist[q_name] = len([n for n in concurso if n in q_nums])
            distribuicoes.append(dist)
        
        # Calcular médias
        medias = {}
        for q_name in quadrantes.keys():
            valores = [d[q_name] for d in distribuicoes]
            medias[q_name] = np.mean(valores) if valores else 0
        
        return quadrantes, medias, distribuicoes
    
    def calcular_media_movel_ponderada(self, janela=10, fator_peso=2):
        """
        Calcula média móvel ponderada dando mais peso a concursos recentes
        fator_peso: quanto maior, mais peso nos concursos recentes
        """
        if len(self.concursos) < janela:
            return {}
        
        pesos = [1 / ((janela - i) ** fator_peso) for i in range(janela)]
        pesos = [p / sum(pesos) for p in pesos]  # Normalizar
        
        freq_ponderada = {n: 0 for n in self.numeros}
        
        for i in range(len(self.concursos) - janela + 1):
            periodo = self.concursos[i:i+janela]
            for j, concurso in enumerate(periodo):
                peso = pesos[j]
                for n in concurso:
                    freq_ponderada[n] += peso
        
        return freq_ponderada
    
    def analise_sazonalidade(self, periodo=10):
        """Analisa padrões de repetição em intervalos fixos"""
        padroes = {}
        
        if not self.concursos:
            return padroes
        
        concursos_analisar = self.concursos[:min(100, len(self.concursos))]
        
        for n in self.numeros:
            posicoes = []
            for i, concurso in enumerate(concursos_analisar):
                if n in concurso:
                    posicoes.append(i)
            
            if len(posicoes) >= 3:
                intervalos = [posicoes[i+1] - posicoes[i] for i in range(len(posicoes)-1)]
                intervalo_medio = np.mean(intervalos) if intervalos else 0
                padroes[n] = {
                    'frequencia': len(posicoes),
                    'intervalo_medio': intervalo_medio,
                    'ultimo_sorteio': posicoes[0] if posicoes else 100,
                    'atraso': (len(concursos_analisar) - posicoes[0]) if posicoes else 100
                }
        
        return padroes
    
    def analise_correlacao(self):
        """Analisa correlação entre pares de números"""
        matriz_correlacao = np.zeros((25, 25))
        
        if not self.concursos:
            return matriz_correlacao
        
        # Contar co-ocorrências nos últimos concursos
        concursos_analisar = self.concursos[:min(100, len(self.concursos))]
        
        for concurso in concursos_analisar:
            for i in range(len(concurso)):
                for j in range(i+1, len(concurso)):
                    n1, n2 = concurso[i] - 1, concurso[j] - 1
                    matriz_correlacao[n1][n2] += 1
                    matriz_correlacao[n2][n1] += 1
        
        # Normalizar pela frequência individual
        freq_individual = {n: 0 for n in self.numeros}
        for concurso in concursos_analisar:
            for n in concurso:
                freq_individual[n] += 1
        
        for i in range(25):
            for j in range(25):
                if i != j and freq_individual[i+1] > 0 and freq_individual[j+1] > 0:
                    esperado = (freq_individual[i+1] * freq_individual[j+1]) / len(concursos_analisar)
                    if esperado > 0:
                        matriz_correlacao[i][j] = matriz_correlacao[i][j] / esperado
        
        return matriz_correlacao
    
    def identificar_combinacoes_raras(self, tamanho=3, limite_concursos=100):
        """Identifica combinações de números que raramente saem juntas"""
        todas_combinacoes = {}
        
        if not self.concursos:
            return []
        
        concursos_analisar = self.concursos[:min(limite_concursos, len(self.concursos))]
        
        # Gerar todas combinações possíveis de tamanho especificado
        for concurso in concursos_analisar:
            for comb in itertools.combinations(sorted(concurso), tamanho):
                comb_key = tuple(sorted(comb))
                todas_combinacoes[comb_key] = todas_combinacoes.get(comb_key, 0) + 1
        
        # Encontrar combinações mais raras
        combinacoes_raras = sorted(todas_combinacoes.items(), key=lambda x: x[1])[:20]
        
        return combinacoes_raras
    
    def analise_gaps(self):
        """Analisa gaps (intervalos) entre aparições de cada número"""
        gaps_por_numero = {n: [] for n in self.numeros}
        
        if not self.concursos:
            return {n: {'media': 0, 'mediana': 0, 'desvio': 0, 'max': 0, 'min': 0} 
                    for n in self.numeros}
        
        concursos_analisar = self.concursos[:min(100, len(self.concursos))]
        
        for n in self.numeros:
            ultima_posicao = None
            for i, concurso in enumerate(concursos_analisar):
                if n in concurso:
                    if ultima_posicao is not None:
                        gaps_por_numero[n].append(i - ultima_posicao)
                    ultima_posicao = i
        
        # Calcular estatísticas
        estatisticas = {}
        for n in self.numeros:
            if gaps_por_numero[n]:
                estatisticas[n] = {
                    'media': np.mean(gaps_por_numero[n]),
                    'mediana': np.median(gaps_por_numero[n]),
                    'desvio': np.std(gaps_por_numero[n]),
                    'max': max(gaps_por_numero[n]) if gaps_por_numero[n] else 0,
                    'min': min(gaps_por_numero[n]) if gaps_por_numero[n] else 0
                }
            else:
                estatisticas[n] = {'media': 0, 'mediana': 0, 'desvio': 0, 'max': 0, 'min': 0}
        
        return estatisticas
    
    def analise_padrao_repeticao(self):
        """Analisa padrão de repetição entre concursos consecutivos"""
        if len(self.concursos) < 2:
            return {'media': 0, 'mediana': 0, 'desvio': 0, 'min': 0, 'max': 0, 'moda': 0}, []
        
        repeticoes = []
        
        for i in range(len(self.concursos) - 1):
            concurso_atual = set(self.concursos[i])
            concurso_proximo = set(self.concursos[i + 1])
            repetidos = len(concurso_atual.intersection(concurso_proximo))
            repeticoes.append(repetidos)
        
        if repeticoes:
            stats = {
                'media': np.mean(repeticoes),
                'mediana': np.median(repeticoes),
                'desvio': np.std(repeticoes),
                'min': min(repeticoes),
                'max': max(repeticoes),
                'moda': Counter(repeticoes).most_common(1)[0][0] if repeticoes else 0
            }
        else:
            stats = {'media': 0, 'mediana': 0, 'desvio': 0, 'min': 0, 'max': 0, 'moda': 0}
        
        return stats, repeticoes
    
    def calcular_entropia(self, janela=20):
        """Calcula entropia (grau de aleatoriedade) dos resultados"""
        if len(self.concursos) < janela:
            return []
        
        entropias = []
        
        for i in range(len(self.concursos) - janela + 1):
            periodo = self.concursos[i:i+janela]
            
            # Calcular frequência de cada número no período
            freq = Counter()
            for concurso in periodo:
                for n in concurso:
                    freq[n] += 1
            
            # Calcular probabilidades
            total_sorteios = sum(freq.values())
            probabilidades = [freq[n] / total_sorteios for n in self.numeros]
            
            # Calcular entropia de Shannon
            entropia = 0
            for p in probabilidades:
                if p > 0:
                    entropia += p * math.log2(p)
            entropia = -entropia
            entropias.append(entropia)
        
        return entropias
    
    def gerar_cartao_estrategia_raiz_digital(self):
        """Gera cartão com distribuição equilibrada de raízes digitais"""
        distribuicao_ideal = {
            1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1
        }
        
        cartao = set()
        numeros_disponiveis = self.numeros.copy()
        random.shuffle(numeros_disponiveis)
        
        for raiz, quantidade in distribuicao_ideal.items():
            numeros_com_raiz = [n for n in numeros_disponiveis 
                              if self.calcular_raiz_digital(n) == raiz 
                              and n not in cartao]
            
            if len(numeros_com_raiz) >= quantidade:
                selecionados = random.sample(numeros_com_raiz, quantidade)
                cartao.update(selecionados)
        
        # Completar se necessário
        while len(cartao) < 15:
            numeros_restantes = [num for num in self.numeros if num not in cartao]
            if numeros_restantes:
                n = random.choice(numeros_restantes)
                cartao.add(n)
            else:
                break
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_quadrantes(self):
        """Gera cartão com distribuição balanceada por quadrantes"""
        quadrantes, medias, _ = self.analise_quadrantes()
        
        # Distribuição ideal baseada nas médias históricas
        distribuicao_ideal = {}
        total = sum(medias.values())
        if total > 0:
            for q_name, media in medias.items():
                distribuicao_ideal[q_name] = max(1, round((media / total) * 15))
        else:
            # Distribuição uniforme se não houver dados
            for q_name in quadrantes.keys():
                distribuicao_ideal[q_name] = 4
        
        # Ajustar para total 15
        total_atual = sum(distribuicao_ideal.values())
        while total_atual != 15 and total_atual > 0:
            if total_atual < 15:
                # Adicionar ao quadrante com maior média
                q_max = max(medias, key=medias.get) if medias else list(quadrantes.keys())[0]
                distribuicao_ideal[q_max] += 1
            else:
                # Remover do quadrante com menor média
                q_min = min(medias, key=medias.get) if medias else list(quadrantes.keys())[0]
                distribuicao_ideal[q_min] = max(1, distribuicao_ideal[q_min] - 1)
            total_atual = sum(distribuicao_ideal.values())
        
        cartao = set()
        for q_name, quantidade in distribuicao_ideal.items():
            numeros_quadrante = [n for n in quadrantes[q_name] if n not in cartao]
            if len(numeros_quadrante) >= quantidade:
                selecionados = random.sample(numeros_quadrante, quantidade)
                cartao.update(selecionados)
            elif numeros_quadrante:
                cartao.update(numeros_quadrante)
        
        # Completar se necessário
        while len(cartao) < 15:
            numeros_restantes = [num for num in self.numeros if num not in cartao]
            if numeros_restantes:
                n = random.choice(numeros_restantes)
                cartao.add(n)
            else:
                break
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_media_movel(self, janela=10):
        """Gera cartão baseado em média móvel ponderada"""
        freq_ponderada = self.calcular_media_movel_ponderada(janela)
        
        if not freq_ponderada:
            return sorted(random.sample(self.numeros, 15))
        
        # Selecionar top 15 números por frequência ponderada
        top_numeros = sorted(freq_ponderada.items(), key=lambda x: x[1], reverse=True)[:20]
        numeros_top = [n for n, _ in top_numeros]
        
        # Escolher 15 números do top 20, garantindo diversidade
        cartao = set()
        
        # Adicionar 10 dos top 15
        if len(numeros_top) >= 15:
            cartao.update(random.sample(numeros_top[:15], min(10, len(numeros_top[:15]))))
        else:
            cartao.update(numeros_top)
        
        # Adicionar 3 dos próximos 5 (para diversificação)
        if len(numeros_top) > 15:
            cartao.update(random.sample(numeros_top[15:20], min(3, len(numeros_top[15:20]))))
        
        # Adicionar números aleatórios (para surpresa)
        numeros_restantes = [n for n in self.numeros if n not in cartao]
        if numeros_restantes:
            cartao.update(random.sample(numeros_restantes, min(2, len(numeros_restantes))))
        
        # Garantir 15 números
        while len(cartao) < 15:
            numeros_restantes = [n for n in self.numeros if n not in cartao]
            if numeros_restantes:
                cartao.add(random.choice(numeros_restantes))
            else:
                break
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_sazonalidade(self):
        """Gera cartão baseado em análise de sazonalidade"""
        padroes = self.analise_sazonalidade()
        
        # Classificar números por atraso vs intervalo médio
        numeros_promissores = []
        for n, dados in padroes.items():
            if dados.get('intervalo_medio', 0) > 0:
                # Número está "atrasado" para sair
                atraso = dados.get('atraso', 100)
                intervalo_medio = dados.get('intervalo_medio', 10)
                if atraso >= intervalo_medio * 0.8:
                    score = atraso / max(intervalo_medio, 1)
                    numeros_promissores.append((n, score))
        
        # Ordenar por score (mais atrasados primeiro)
        numeros_promissores.sort(key=lambda x: x[1], reverse=True)
        
        cartao = set()
        if numeros_promissores:
            # Adicionar até 10 números mais atrasados
            for i in range(min(10, len(numeros_promissores))):
                cartao.add(numeros_promissores[i][0])
        else:
            # Se não houver atrasados, adicionar aleatórios
            cartao.update(random.sample(self.numeros, min(10, len(self.numeros))))
        
        # Adicionar números quentes se houver concursos
        if self.concursos:
            freq = Counter()
            concursos_analisar = self.concursos[:min(20, len(self.concursos))]
            for concurso in concursos_analisar:
                for n in concurso:
                    freq[n] += 1
            
            numeros_quentes = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
            numeros_quentes_lista = [n for n, _ in numeros_quentes]
            
            # Filtrar números quentes que não estão no cartão
            numeros_quentes_disponiveis = [num for num in numeros_quentes_lista if num not in cartao]
            
            while len(cartao) < 15 and numeros_quentes_disponiveis:
                n = random.choice(numeros_quentes_disponiveis)
                cartao.add(n)
                numeros_quentes_disponiveis.remove(n)
        
        # Completar se necessário
        while len(cartao) < 15:
            numeros_restantes = [num for num in self.numeros if num not in cartao]
            if numeros_restantes:
                n = random.choice(numeros_restantes)
                cartao.add(n)
            else:
                break
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_correlacao(self):
        """Gera cartão considerando correlação entre números"""
        matriz_correlacao = self.analise_correlacao()
        
        # Encontrar pares mais correlacionados
        pares_correlacionados = []
        for i in range(25):
            for j in range(i+1, 25):
                if matriz_correlacao[i][j] > 1.2:  # Correlação acima do esperado
                    pares_correlacionados.append(((i+1, j+1), matriz_correlacao[i][j]))
        
        # Ordenar por força de correlação
        pares_correlacionados.sort(key=lambda x: x[1], reverse=True)
        
        cartao = set()
        
        # Adicionar alguns pares correlacionados
        for (n1, n2), _ in pares_correlacionados[:3]:
            if len(cartao) < 13:  # Deixar espaço para outros números
                if n1 not in cartao:
                    cartao.add(n1)
                if n2 not in cartao:
                    cartao.add(n2)
        
        # Se não houver pares correlacionados, começar com alguns números aleatórios
        if len(cartao) == 0:
            cartao.update(random.sample(self.numeros, min(5, len(self.numeros))))
        
        # Adicionar números independentes (baixa correlação com os já escolhidos)
        numeros_restantes = [n for n in self.numeros if n not in cartao]
        
        while len(cartao) < 15 and numeros_restantes:
            # Escolher número com menor correlação média com os já selecionados
            melhores = []
            for n in numeros_restantes:
                correl_total = 0
                count = 0
                for n_cartao in cartao:
                    correl_total += matriz_correlacao[n-1][n_cartao-1]
                    count += 1
                correl_media = correl_total / count if count > 0 else 0
                melhores.append((n, correl_media))
            
            # Escolher número com menor correlação média
            if melhores:
                melhores.sort(key=lambda x: x[1])
                cartao.add(melhores[0][0])
                numeros_restantes.remove(melhores[0][0])
            else:
                break
        
        # Completar se necessário
        while len(cartao) < 15:
            numeros_restantes = [num for num in self.numeros if num not in cartao]
            if numeros_restantes:
                cartao.add(random.choice(numeros_restantes))
            else:
                break
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_combinacoes_raras(self):
        """Gera cartão incluindo combinações raras"""
        combinacoes_raras = self.identificar_combinacoes_raras(tamanho=3)
        
        cartao = set()
        
        # Adicionar algumas combinações raras
        for comb, _ in combinacoes_raras[:2]:  # 2 combinações de 3 números = 6 números
            for n in comb:
                if n not in cartao:
                    cartao.add(n)
        
        # Completar com estratégia balanceada se houver concursos
        if self.concursos:
            freq = Counter()
            concursos_analisar = self.concursos[:min(30, len(self.concursos))]
            for concurso in concursos_analisar:
                for n in concurso:
                    freq[n] += 1
            
            # Adicionar números quentes
            numeros_quentes = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            for n, _ in numeros_quentes:
                if len(cartao) >= 15:
                    break
                if n not in cartao:
                    cartao.add(n)
        else:
            # Se não houver concursos, adicionar aleatórios
            while len(cartao) < 15:
                n = random.choice([num for num in self.numeros if num not in cartao])
                cartao.add(n)
        
        # Garantir equilíbrio par/ímpar
        pares = sum(1 for n in cartao if n % 2 == 0)
        tentativas = 0
        while (pares < 6 or pares > 9) and tentativas < 10:
            if pares < 6:
                # Trocar ímpar por par
                impares_no_cartao = [n for n in cartao if n % 2 == 1]
                pares_fora = [n for n in self.numeros if n % 2 == 0 and n not in cartao]
                if impares_no_cartao and pares_fora:
                    cartao.remove(random.choice(impares_no_cartao))
                    cartao.add(random.choice(pares_fora))
            elif pares > 9:
                # Trocar par por ímpar
                pares_no_cartao = [n for n in cartao if n % 2 == 0]
                impares_fora = [n for n in self.numeros if n % 2 == 1 and n not in cartao]
                if pares_no_cartao and impares_fora:
                    cartao.remove(random.choice(pares_no_cartao))
                    cartao.add(random.choice(impares_fora))
            
            pares = sum(1 for n in cartao if n % 2 == 0)
            tentativas += 1
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_gaps(self):
        """Gera cartão baseado em análise de gaps"""
        estatisticas_gaps = self.analise_gaps()
        
        # Classificar números por desvio do gap médio
        numeros_otimos = []
        for n, stats in estatisticas_gaps.items():
            if stats['media'] > 0:
                # Quanto mais próximo do gap médio, melhor
                atraso = 100  # Valor padrão se não houver dados
                diff = abs(atraso - stats['media'])
                score = 1 / (diff + 1)  # Quanto menor a diferença, maior o score
                numeros_otimos.append((n, score))
        
        # Ordenar por score
        numeros_otimos.sort(key=lambda x: x[1], reverse=True)
        
        cartao = set()
        
        # Adicionar até 8 números com gaps mais próximos da média
        if numeros_otimos:
            for i in range(min(8, len(numeros_otimos))):
                cartao.add(numeros_otimos[i][0])
        else:
            # Se não houver análise de gaps, adicionar aleatórios
            cartao.update(random.sample(self.numeros, min(8, len(self.numeros))))
        
        # Adicionar números Fibonacci se disponíveis
        fibonacci_disponiveis = [n for n in self.fibonacci if n not in cartao]
        if fibonacci_disponiveis:
            cartao.update(random.sample(fibonacci_disponiveis, min(3, len(fibonacci_disponiveis))))
        
        # Adicionar números primos se disponíveis
        primos_disponiveis = [n for n in self.primos if n not in cartao]
        if primos_disponiveis:
            cartao.update(random.sample(primos_disponiveis, min(3, len(primos_disponiveis))))
        
        # Completar se necessário
        while len(cartao) < 15:
            numeros_restantes = [num for num in self.numeros if num not in cartao]
            if numeros_restantes:
                n = random.choice(numeros_restantes)
                cartao.add(n)
            else:
                break
        
        return sorted(list(cartao))
    
    def gerar_cartao_estrategia_entropia(self, janela=20):
        """Gera cartão baseado em análise de entropia"""
        entropias = self.calcular_entropia(janela)
        
        if not entropias:
            return sorted(random.sample(self.numeros, 15))
        
        # Identificar período de maior entropia (mais aleatório)
        entropia_media = np.mean(entropias)
        
        # Encontrar concursos em períodos de alta entropia
        periodos_alta_entropia = []
        for i in range(len(entropias)):
            if entropias[i] > entropia_media:
                periodo_inicio = i
                periodo_fim = min(i + janela, len(self.concursos))
                periodos_alta_entropia.extend(self.concursos[periodo_inicio:periodo_fim])
        
        if not periodos_alta_entropia:
            periodos_alta_entropia = self.concursos[:min(30, len(self.concursos))]
        
        # Analisar números que aparecem em períodos de alta entropia
        freq_alta_entropia = Counter()
        for concurso in periodos_alta_entropia:
            for n in concurso:
                freq_alta_entropia[n] += 1
        
        # Selecionar números
        cartao = set()
        
        # Adicionar números mais frequentes em alta entropia
        top_alta_entropia = sorted(freq_alta_entropia.items(), key=lambda x: x[1], reverse=True)[:15]
        for n, _ in top_alta_entropia[:min(10, len(top_alta_entropia))]:
            cartao.add(n)
        
        # Adicionar números menos frequentes (para diversidade)
        todos_numeros = set(self.numeros)
        numeros_nao_usados = todos_numeros - cartao
        
        # Escolher alguns números que raramente aparecem juntos
        combinacoes_raras = self.identificar_combinacoes_raras(tamanho=2, limite_concursos=50)
        for comb, _ in combinacoes_raras[:3]:
            for n in comb:
                if n in numeros_nao_usados and len(cartao) < 15:
                    cartao.add(n)
        
        # Completar se necessário
        while len(cartao) < 15:
            numeros_restantes = [num for num in self.numeros if num not in cartao]
            if numeros_restantes:
                n = random.choice(numeros_restantes)
                cartao.add(n)
            else:
                break
        
        return sorted(list(cartao))

# =========================
# CLASSE: Sistema de Geração Híbrida
# =========================
class SistemaGeracaoHibrida:
    def __init__(self, concursos):
        self.concursos = concursos if concursos else []
        self.numeros = list(range(1, 26))
        self.estrategias = EstrategiasAvancadas(concursos)
        
    def gerar_portfolio_estrategias(self, n_cartoes=10):
        """Gera um portfolio diversificado usando múltiplas estratégias"""
        portfolio = []
        
        # Lista de estratégias disponíveis
        estrategias_disponiveis = [
            ('Raiz Digital Balanceada', self.estrategias.gerar_cartao_estrategia_raiz_digital, 'raiz_digital'),
            ('Distribuição por Quadrantes', self.estrategias.gerar_cartao_estrategia_quadrantes, 'quadrantes'),
            ('Média Móvel Ponderada', lambda: self.estrategias.gerar_cartao_estrategia_media_movel(), 'media_movel'),
            ('Análise de Sazonalidade', self.estrategias.gerar_cartao_estrategia_sazonalidade, 'sazonalidade'),
            ('Otimização por Correlação', self.estrategias.gerar_cartao_estrategia_correlacao, 'correlacao'),
            ('Combinações Raras', self.estrategias.gerar_cartao_estrategia_combinacoes_raras, 'combinacoes_raras'),
            ('Análise de Gaps', self.estrategias.gerar_cartao_estrategia_gaps, 'gaps'),
            ('Maximização de Entropia', lambda: self.estrategias.gerar_cartao_estrategia_entropia(), 'entropia'),
            ('Híbrida Inteligente', self.gerar_cartao_hibrido, 'hibrida'),
            ('Aleatória Otimizada', self.gerar_cartao_aleatorio_otimizado, 'aleatoria_otimizada')
        ]
        
        # Gerar cartões para cada estratégia
        for nome, funcao_geracao, estrategia_key in estrategias_disponiveis[:n_cartoes]:
            try:
                cartao = funcao_geracao()
                if cartao and len(cartao) == 15:
                    portfolio.append({
                        'nome': nome,
                        'cartao': cartao,
                        'estrategia': estrategia_key
                    })
            except Exception as e:
                st.warning(f"Erro na estratégia {nome}: {e}")
                # Se falhar, gera um cartão aleatório otimizado
                portfolio.append({
                    'nome': f"{nome} (Alternativa)",
                    'cartao': self.gerar_cartao_aleatorio_otimizado(),
                    'estrategia': estrategia_key
                })
        
        return portfolio
    
    def gerar_cartao_hibrido(self):
        """Combina as melhores características de múltiplas estratégias"""
        try:
            cartoes_parciais = []
            
            # Gerar cartões parciais com diferentes estratégias
            estrategias_para_hibrido = [
                self.estrategias.gerar_cartao_estrategia_media_movel,
                self.estrategias.gerar_cartao_estrategia_sazonalidade,
                self.estrategias.gerar_cartao_estrategia_correlacao
            ]
            
            for estrategia in estrategias_para_hibrido:
                try:
                    cartoes_parciais.append(set(estrategia()))
                except:
                    continue
            
            # Se não conseguiu gerar cartões parciais, retorna aleatório otimizado
            if len(cartoes_parciais) < 2:
                return self.gerar_cartao_aleatorio_otimizado()
            
            # Encontrar interseção (números recomendados por múltiplas estratégias)
            interseccao = set.intersection(*cartoes_parciais[:2])
            
            cartao_final = set()
            
            # Adicionar interseção (máximo 8 números)
            if interseccao:
                cartao_final.update(list(interseccao)[:8])
            
            # Adicionar números únicos de cada estratégia
            todos_numeros = set()
            for c in cartoes_parciais:
                todos_numeros.update(c)
            
            numeros_unicos = todos_numeros - cartao_final
            
            # Selecionar números únicos com base em frequência se houver concursos
            if self.concursos:
                freq = Counter()
                concursos_analisar = self.concursos[:min(30, len(self.concursos))]
                for concurso in concursos_analisar:
                    for n in concurso:
                        freq[n] += 1
                
                numeros_unicos_lista = list(numeros_unicos)
                numeros_unicos_lista.sort(key=lambda x: freq.get(x, 0), reverse=True)
            else:
                numeros_unicos_lista = list(numeros_unicos)
                random.shuffle(numeros_unicos_lista)
            
            # Adicionar números únicos até completar 15
            for n in numeros_unicos_lista:
                if len(cartao_final) >= 15:
                    break
                cartao_final.add(n)
            
            # Completar se necessário
            while len(cartao_final) < 15:
                numeros_restantes = [num for num in self.numeros if num not in cartao_final]
                if numeros_restantes:
                    n = random.choice(numeros_restantes)
                    cartao_final.add(n)
                else:
                    break
            
            return sorted(list(cartao_final))
            
        except Exception:
            return self.gerar_cartao_aleatorio_otimizado()
    
    def gerar_cartao_aleatorio_otimizado(self):
        """Gera cartão aleatório mas com restrições estatísticas"""
        tentativas = 0
        max_tentativas = 1000
        
        while tentativas < max_tentativas:
            cartao = sorted(random.sample(self.numeros, 15))
            
            # Verificar restrições
            pares = sum(1 for n in cartao if n % 2 == 0)
            primos = sum(1 for n in cartao if n in self.estrategias.primos)
            soma_total = sum(cartao)
            
            # Verificar se atende critérios básicos
            criterios_ok = (
                6 <= pares <= 9 and
                3 <= primos <= 7 and
                170 <= soma_total <= 210
            )
            
            if criterios_ok:
                return cartao
            
            tentativas += 1
        
        # Se não encontrou após muitas tentativas, retorna qualquer um
        return sorted(random.sample(self.numeros, 15))
    
    def analisar_performance_estrategias(self, concursos_teste=50):
        """Analisa performance histórica das estratégias"""
        if len(self.concursos) < concursos_teste + 10:
            return {}
        
        resultados = {}
        
        # Testar cada estratégia
        estrategias_testar = [
            ('raiz_digital', self.estrategias.gerar_cartao_estrategia_raiz_digital),
            ('quadrantes', self.estrategias.gerar_cartao_estrategia_quadrantes),
            ('media_movel', lambda: self.estrategias.gerar_cartao_estrategia_media_movel()),
            ('sazonalidade', self.estrategias.gerar_cartao_estrategia_sazonalidade),
            ('correlacao', self.estrategias.gerar_cartao_estrategia_correlacao),
            ('combinacoes_raras', self.estrategias.gerar_cartao_estrategia_combinacoes_raras),
            ('gaps', self.estrategias.gerar_cartao_estrategia_gaps),
            ('entropia', lambda: self.estrategias.gerar_cartao_estrategia_entropia()),
            ('hibrida', self.gerar_cartao_hibrido),
            ('aleatoria_otimizada', self.gerar_cartao_aleatorio_otimizado)
        ]
        
        for nome, funcao_geracao in estrategias_testar:
            acertos_totais = []
            
            # Testar em diferentes pontos no tempo
            for inicio in range(0, len(self.concursos) - concursos_teste, 10):
                # Gerar cartão baseado nos concursos até 'inicio'
                concursos_base = self.concursos[inicio:inicio+30]
                if len(concursos_base) < 20:
                    continue
                    
                estrategia_temp = EstrategiasAvancadas(concursos_base)
                sistema_temp = SistemaGeracaoHibrida(concursos_base)
                
                # Tentar gerar cartão com a estratégia
                try:
                    if nome == 'raiz_digital':
                        cartao = estrategia_temp.gerar_cartao_estrategia_raiz_digital()
                    elif nome == 'quadrantes':
                        cartao = estrategia_temp.gerar_cartao_estrategia_quadrantes()
                    elif nome == 'sazonalidade':
                        cartao = estrategia_temp.gerar_cartao_estrategia_sazonalidade()
                    elif nome == 'correlacao':
                        cartao = estrategia_temp.gerar_cartao_estrategia_correlacao()
                    elif nome == 'combinacoes_raras':
                        cartao = estrategia_temp.gerar_cartao_estrategia_combinacoes_raras()
                    elif nome == 'gaps':
                        cartao = estrategia_temp.gerar_cartao_estrategia_gaps()
                    elif nome == 'hibrida':
                        cartao = sistema_temp.gerar_cartao_hibrido()
                    elif nome == 'aleatoria_otimizada':
                        cartao = sistema_temp.gerar_cartao_aleatorio_otimizado()
                    elif nome == 'media_movel':
                        cartao = estrategia_temp.gerar_cartao_estrategia_media_movel()
                    elif nome == 'entropia':
                        cartao = estrategia_temp.gerar_cartao_estrategia_entropia()
                    else:
                        continue
                    
                    # Testar em concursos futuros
                    acertos_periodo = []
                    for i in range(inicio + 30, min(inicio + 30 + concursos_teste, len(self.concursos))):
                        concurso_real = set(self.concursos[i])
                        acertos = len(set(cartao).intersection(concurso_real))
                        acertos_periodo.append(acertos)
                    
                    if acertos_periodo:
                        acertos_totais.extend(acertos_periodo)
                        
                except Exception:
                    continue
            
            if acertos_totais:
                resultados[nome] = {
                    'media_acertos': np.mean(acertos_totais),
                    'desvio_acertos': np.std(acertos_totais),
                    'max_acertos': max(acertos_totais),
                    'min_acertos': min(acertos_totais),
                    'amostras': len(acertos_totais)
                }
        
        return resultados

# =========================
# CLASSE: AnaliseSequenciaFalha
# =========================
class AnaliseSequenciaFalha:
    def __init__(self, concursos):
        self.concursos = concursos if concursos else []
        self.numeros = list(range(1, 26))
        
    def calcular_sequencias(self):
        """Retorna uma lista com contagem de sequências de acertos por posição."""
        sequencias = [0] * 25
        if not self.concursos:
            return sequencias
            
        for jogo in self.concursos:
            for num in jogo:
                sequencias[num - 1] += 1
        return sequencias
    
    def calcular_falhas(self):
        """Retorna quantas vezes cada número NÃO apareceu."""
        falhas = [0] * 25
        if not self.concursos:
            return falhas
            
        for linha in self.concursos:
            presentes = set(linha)
            for n in range(1, 26):
                if n not in presentes:
                    falhas[n - 1] += 1
        return falhas
    
    def criar_tabela_completa(self):
        """Cria tabela completa de análise."""
        sequencias = self.calcular_sequencias()
        falhas = self.calcular_falhas()
        
        numeros_por_sequencia = sorted(range(1, 26), key=lambda x: sequencias[x-1], reverse=True)
        numeros_por_falha = sorted(range(1, 26), key=lambda x: falhas[x-1], reverse=True)
        
        tabela = {
            "Número": list(range(1, 26)),
            "Sequência": sequencias,
            "Falha": falhas,
            "Posição_Sequência": [numeros_por_sequencia.index(n)+1 for n in range(1, 26)],
            "Posição_Falha": [numeros_por_falha.index(n)+1 for n in range(1, 26)]
        }
        
        return pd.DataFrame(tabela)
    
    def gerar_jogos_metodo_tabela(self, n_jogos=5):
        """Gera jogos usando o método da tabela."""
        sequencias = self.calcular_sequencias()
        falhas = self.calcular_falhas()
        
        jogos = []
        for _ in range(n_jogos):
            melhores = sorted(range(1, 26), key=lambda x: sequencias[x-1], reverse=True)[:10]
            retorno = sorted(range(1, 26), key=lambda x: falhas[x-1], reverse=True)[:10]
            
            combo = set(random.sample(melhores, 8) + random.sample(retorno, 7))
            
            while len(combo) < 15:
                numeros_restantes = [n for n in range(1, 26) if n not in combo]
                if numeros_restantes:
                    combo.add(random.choice(numeros_restantes))
                else:
                    break
            
            jogos.append(sorted(list(combo)))
        
        return jogos

# =========================
# CLASSE: AnaliseCiclos
# =========================
class AnaliseCiclos:
    def __init__(self, concursos, concursos_info=None, limite_concursos=None):
        self.concursos = concursos if concursos else []
        self.concursos_info = concursos_info or {}
        self.TODAS = set(range(1,26))
        self.ciclo_concursos = []
        self.ciclo_concursos_info = []
        self.numeros_presentes = set()
        self.numeros_faltantes = set(self.TODAS)
        self.tamanho = 0
        self.iniciar_indice = None
        self.limite_concursos = limite_concursos
        self.analisar()
    
    def analisar(self):
        self.ciclo_concursos = []
        self.ciclo_concursos_info = []
        self.numeros_presentes = set()
        self.numeros_faltantes = set(self.TODAS)
        self.iniciar_indice = None
        
        if not self.concursos:
            return
        
        max_concursos = len(self.concursos)
        if self.limite_concursos is not None:
            max_concursos = min(self.limite_concursos, len(self.concursos))
        
        for idx, concurso in enumerate(self.concursos[:max_concursos]):
            if not concurso:
                continue
            self.ciclo_concursos.append(concurso)
            
            if idx in self.concursos_info:
                self.ciclo_concursos_info.append(self.concursos_info[idx])
            else:
                self.ciclo_concursos_info.append({
                    "indice": idx,
                    "numero_concurso": f"Concurso {len(self.concursos) - idx}",
                    "dezenas": concurso
                })
            
            self.numeros_presentes.update(concurso)
            self.numeros_faltantes = self.TODAS - self.numeros_presentes
            self.iniciar_indice = idx
            
            if not self.numeros_faltantes:
                break
        
        self.tamanho = len(self.ciclo_concursos)
    
    def resumo(self):
        return {
            "tamanho": self.tamanho,
            "numeros_presentes": sorted(list(self.numeros_presentes)),
            "numeros_faltantes": sorted(list(self.numeros_faltantes)),
            "inicio_indice": self.iniciar_indice,
            "concursos_analisados": self.ciclo_concursos_info,
            "limite_concursos": self.limite_concursos
        }

# =========================
# Streamlit Interface
# =========================
def carregar_estado():
    """Carrega o estado da sessão"""
    estados = [
        "concursos", "cartoes_gerados", "cartoes_gerados_padrao", 
        "info_ultimo_concurso", "combinacoes_combinatorias", 
        "tabela_sequencia_falha", "jogos_sequencia_falha", 
        "resultado_ciclos", "cartoes_ciclos", "analise_ciclos", 
        "concursos_info", "limite_ciclos", "portfolio_estrategias",
        "performance_estrategias"
    ]
    
    for estado in estados:
        if estado not in st.session_state:
            if estado in ["portfolio_estrategias", "cartoes_ciclos", "jogos_sequencia_falha", 
                          "cartoes_gerados", "cartoes_gerados_padrao"]:
                st.session_state[estado] = []
            elif estado == "performance_estrategias":
                st.session_state[estado] = {}
            elif estado == "combinacoes_combinatorias":
                st.session_state[estado] = {}
            elif estado == "concursos_info":
                st.session_state[estado] = {}
            else:
                st.session_state[estado] = None

st.markdown("<h1 style='text-align: center;'>Lotofácil Inteligente</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# Inicializar estado
carregar_estado()

# --- Captura concursos ---
with st.expander("📥 Capturar Concursos"):
    qtd_concursos = st.slider("Quantidade de concursos para análise", 10, 250, 100)
    if st.button("🔄 Capturar Agora"):
        with st.spinner("Capturando concursos da Lotofácil..."):
            concursos, info = capturar_ultimos_resultados(qtd_concursos)
            if concursos:
                st.session_state.concursos = concursos
                st.session_state.info_ultimo_concurso = info
                
                concursos_info = {}
                total_concursos = len(concursos)
                for idx, concurso in enumerate(concursos):
                    numero_concurso = total_concursos - idx
                    concursos_info[idx] = {
                        "indice": idx,
                        "numero_concurso": f"Concurso {numero_concurso}",
                        "dezenas": concurso
                    }
                st.session_state.concursos_info = concursos_info
                
                st.success(f"{len(concursos)} concursos capturados com sucesso!")
                
                # Limpar dados antigos
                estados_para_limpar = [
                    "tabela_sequencia_falha", "resultado_ciclos", 
                    "analise_ciclos", "limite_ciclos"
                ]
                
                for estado in estados_para_limpar:
                    st.session_state[estado] = None
                    
                # Limpar listas
                listas_para_limpar = [
                    "portfolio_estrategias", "cartoes_ciclos", 
                    "jogos_sequencia_falha", "cartoes_gerados", 
                    "cartoes_gerados_padrao"
                ]
                
                for lista in listas_para_limpar:
                    st.session_state[lista] = []
                    
                st.session_state.performance_estrategias = {}
                st.session_state.combinacoes_combinatorias = {}
            else:
                st.error("Não foi possível capturar concursos.")

# --- Abas principais ---
if st.session_state.concursos:
    # Criar sistema de geração híbrida
    sistema_hibrido = SistemaGeracaoHibrida(st.session_state.concursos)
    
    # Abas principais
    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões IA", 
        "📈 Método Sequência/Falha",
        "🚀 Estratégias Avançadas",  # NOVA ABA
        "🔢 Análises Combinatórias",
        "🧩 Gerar Cartões por Padrões",
        "📐 Padrões Linha×Coluna",
        "✅ Conferência", 
        "📤 Conferir Arquivo TXT",
        "🔁 Ciclos da Lotofácil"
    ])

    # Aba 4 - ESTRATÉGIAS AVANÇADAS (NOVA)
    with abas[3]:
        st.subheader("🚀 Estratégias Avançadas de Geração")
        st.write("Gere cartões usando algoritmos matemáticos e estatísticos avançados.")
        
        # Configurações
        col_config1, col_config2 = st.columns(2)
        
        with col_config1:
            n_cartoes = st.slider("Número de cartões a gerar:", 1, 10, 5)
        
        with col_config2:
            if st.button("📊 Analisar Performance das Estratégias", use_container_width=True):
                with st.spinner("Analisando performance histórica..."):
                    try:
                        performance = sistema_hibrido.analisar_performance_estrategias(concursos_teste=30)
                        st.session_state.performance_estrategias = performance
                        st.success("Análise de performance concluída!")
                    except Exception as e:
                        st.error(f"Erro na análise: {e}")
        
        # Botão principal de geração
        if st.button("🎯 Gerar Portfolio de Estratégias", type="primary", use_container_width=True):
            with st.spinner("Gerando cartões com múltiplas estratégias..."):
                try:
                    portfolio = sistema_hibrido.gerar_portfolio_estrategias(n_cartoes)
                    st.session_state.portfolio_estrategias = portfolio
                    st.success(f"{len(portfolio)} cartões gerados com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao gerar portfolio: {e}")
                    st.session_state.portfolio_estrategias = []
        
        # Mostrar performance das estratégias
        if st.session_state.performance_estrategias and len(st.session_state.performance_estrategias) > 0:
            st.subheader("📈 Performance Histórica das Estratégias")
            
            # Converter para DataFrame
            dados_performance = []
            for estrategia, dados in st.session_state.performance_estrategias.items():
                dados_performance.append({
                    'Estratégia': estrategia.replace('_', ' ').title(),
                    'Média Acertos': f"{dados['media_acertos']:.2f}",
                    'Desvio Padrão': f"{dados['desvio_acertos']:.2f}",
                    'Máximo': dados['max_acertos'],
                    'Mínimo': dados['min_acertos'],
                    'Amostras': dados['amostras']
                })
            
            if dados_performance:
                df_performance = pd.DataFrame(dados_performance)
                st.dataframe(df_performance.sort_values('Média Acertos', ascending=False), 
                            hide_index=True, use_container_width=True)
        
        # Mostrar portfolio gerado
        if st.session_state.portfolio_estrategias and len(st.session_state.portfolio_estrategias) > 0:
            st.subheader("🎰 Portfolio de Cartões Gerados")
            
            # Mostrar cada cartão
            for i, item in enumerate(st.session_state.portfolio_estrategias):
                cartao = item['cartao']
                
                # Calcular estatísticas
                pares = sum(1 for n in cartao if n % 2 == 0)
                primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
                soma = sum(cartao)
                fibonacci = sum(1 for n in cartao if n in {1,2,3,5,8,13,21})
                
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{item['nome']}:** {cartao}")
                with col2:
                    st.write(f"**Estatísticas:**")
                    st.write(f"- Pares: {pares}")
                    st.write(f"- Primos: {primos}")
                    st.write(f"- Fibonacci: {fibonacci}")
                with col3:
                    st.write(f"- Soma: {soma}")
                
                st.write("---")
            
            # Botões de exportação
            st.subheader("💾 Exportar Portfolio")
            
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                # Exportar como texto simples
                conteudo_simples = ""
                for item in st.session_state.portfolio_estrategias:
                    conteudo_simples += f"{item['nome']}: {','.join(str(n) for n in item['cartao'])}\n"
                
                st.download_button(
                    "📥 Baixar como Texto",
                    data=conteudo_simples,
                    file_name="portfolio_estrategias.txt",
                    mime="text/plain"
                )
            
            with col_exp2:
                # Exportar como CSV
                dados_csv = []
                for item in st.session_state.portfolio_estrategias:
                    cartao = item['cartao']
                    pares = sum(1 for n in cartao if n % 2 == 0)
                    primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
                    soma = sum(cartao)
                    
                    dados_csv.append({
                        'Estrategia': item['nome'],
                        'Cartao': ','.join(str(n) for n in cartao),
                        'Pares': pares,
                        'Primos': primos,
                        'Soma': soma
                    })
                
                if dados_csv:
                    df_csv = pd.DataFrame(dados_csv)
                    csv_content = df_csv.to_csv(index=False)
                    
                    st.download_button(
                        "📊 Baixar como CSV",
                        data=csv_content,
                        file_name="portfolio_estrategias.csv",
                        mime="text/csv"
                    )
        
        # Seção de explicação das estratégias
        with st.expander("📚 Explicação das Estratégias", expanded=False):
            st.markdown("""
            ### **Estratégias Implementadas:**
            
            **1. Raiz Digital Balanceada**
            - Calcula raiz digital de cada número (ex: 25 → 2+5=7)
            - Garante distribuição equilibrada de raízes 1-9
            
            **2. Distribuição por Quadrantes**
            - Divide o cartão em 4 quadrantes
            - Balanceia números por região do cartão
            
            **3. Média Móvel Ponderada**
            - Dá mais peso aos concursos recentes
            - Identifica tendências de curto prazo
            
            **4. Análise de Sazonalidade**
            - Detecta padrões de repetição em intervalos fixos
            - Prioriza números "atrasados" para sair
            
            **5. Otimização por Correlação**
            - Analisa quais números tendem a sair juntos
            - Evita combinações improváveis
            
            **6. Combinações Raras**
            - Identifica grupos de números que raramente saem juntos
            - Explora combinações "esquecidas"
            
            **7. Análise de Gaps**
            - Estuda intervalos entre aparições de cada número
            - Prioriza números com gaps próximos da média histórica
            
            **8. Maximização de Entropia**
            - Analisa períodos de maior aleatoriedade
            - Gera cartões otimizados para períodos imprevisíveis
            
            **9. Híbrida Inteligente**
            - Combina as melhores características de múltiplas estratégias
            - Usa interseção de recomendações
            
            **10. Aleatória Otimizada**
            - Aleatoriedade com restrições estatísticas
            - Garante equilíbrio básico
            """)

# Sidebar
with st.sidebar:
    st.markdown("---")
    st.subheader("⚙️ Gerenciamento de Dados")
    if st.button("🗑️ Limpar Todos os Dados"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.markdown("### 📊 Estatísticas da Sessão")
    if st.session_state.concursos:
        st.write(f"Concursos carregados: {len(st.session_state.concursos)}")
    if st.session_state.portfolio_estrategias:
        st.write(f"Cartões Estratégias: {len(st.session_state.portfolio_estrategias)}")
    if st.session_state.performance_estrategias:
        st.write(f"Estratégias analisadas: {len(st.session_state.performance_estrategias)}")

st.markdown("<hr><p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
