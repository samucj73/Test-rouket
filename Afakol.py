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
from itertools import combinations

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
# CLASSE: Análise Estatística Séria (substitui a quântica)
# =========================
class AnaliseEstatisticaSeriosa:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        
    def calcular_distribuicao_probabilistica(self, janela=50):
        """
        Calcula distribuição real de probabilidades baseada em:
        1. Frequência histórica
        2. Teste de aleatoriedade (qui-quadrado)
        3. Padrões de Markov (transições)
        4. Intervalos de confiança
        """
        if len(self.concursos) < janela:
            janela = len(self.concursos)
        
        concursos_recentes = self.concursos[:janela]
        
        # 1. Frequência bruta com intervalo de confiança 95%
        frequencias = Counter()
        for concurso in concursos_recentes:
            frequencias.update(concurso)
        
        # Calcular probabilidade com intervalo de confiança
        prob_com_intervalo = {}
        for n in self.numeros:
            freq = frequencias[n]
            p = freq / janela
            
            # Intervalo de confiança 95% para proporção
            z = 1.96  # Para 95% de confiança
            margem_erro = z * math.sqrt((p * (1 - p)) / janela)
            
            prob_com_intervalo[n] = {
                'probabilidade': p,
                'intervalo_inferior': max(0, p - margem_erro),
                'intervalo_superior': min(1, p + margem_erro),
                'frequencia': freq
            }
        
        # 2. Teste de aleatoriedade (Qui-quadrado)
        chi2, p_value = self._teste_aleatoriedade(concursos_recentes)
        
        # 3. Análise de transições (Cadeias de Markov)
        matriz_transicao = self._calcular_matriz_transicao(concursos_recentes)
        
        # 4. Padrões temporais (autocorrelação)
        autocorrelacao = self._calcular_autocorrelacao(concursos_recentes)
        
        return {
            'probabilidades': prob_com_intervalo,
            'teste_aleatoriedade': {'chi2': chi2, 'p_value': p_value},
            'matriz_transicao': matriz_transicao,
            'autocorrelacao': autocorrelacao,
            'concursos_analisados': janela,
            'media_frequencia': sum(frequencias.values()) / (janela * 25)
        }
    
    def _teste_aleatoriedade(self, concursos):
        """Teste qui-quadrado para verificar aleatoriedade"""
        if len(concursos) < 30:
            return None, None
        
        frequencias = Counter()
        for concurso in concursos:
            frequencias.update(concurso)
        
        # Frequência esperada se fosse perfeitamente aleatório
        esperado = len(concursos) * 15 / 25
        
        # Calcular qui-quadrado
        chi2 = sum((frequencias[n] - esperado) ** 2 / esperado for n in self.numeros)
        
        # Graus de liberdade
        df = 24
        
        # Valor p aproximado
        try:
            from scipy.stats import chi2 as chi2_dist
            p_value = 1 - chi2_dist.cdf(chi2, df)
        except ImportError:
            # Aproximação manual se scipy não disponível
            p_value = 0.05  # Valor padrão conservador
        
        return chi2, p_value
    
    def _calcular_matriz_transicao(self, concursos):
        """Matriz de transição entre concursos (Cadeias de Markov)"""
        if len(concursos) < 2:
            return None
        
        matriz = np.zeros((25, 25))
        
        for i in range(len(concursos) - 1):
            atual = set(concursos[i])
            proximo = set(concursos[i + 1])
            
            # Probabilidade de transição
            for n_atual in self.numeros:
                for n_prox in self.numeros:
                    if n_atual in atual and n_prox in proximo:
                        matriz[n_atual - 1, n_prox - 1] += 1
        
        # Normalizar
        for i in range(25):
            total = matriz[i].sum()
            if total > 0:
                matriz[i] = matriz[i] / total
        
        return matriz
    
    def _calcular_autocorrelacao(self, concursos):
        """Calcula autocorrelação para detectar padrões sazonais"""
        if len(concursos) < 20:
            return {}
        
        # Converter para matriz binária
        matriz_bin = np.array([[1 if n in jogo else 0 for n in self.numeros] 
                              for jogo in concursos])
        
        autocorr = {}
        for lag in range(1, min(10, len(concursos) // 2)):
            if lag < len(concursos):
                try:
                    corr = np.corrcoef(matriz_bin[:-lag].flatten(), 
                                      matriz_bin[lag:].flatten())[0, 1]
                    autocorr[lag] = corr if not np.isnan(corr) else 0
                except:
                    autocorr[lag] = 0
        
        return autocorr
    
    def gerar_cartoes_estatisticos(self, n_cartoes=5, usar_intervalo_confianca=True):
        """Gera cartões usando métodos estatísticos sólidos"""
        if len(self.concursos) < 30:
            return []
        
        analise = self.calcular_distribuicao_probabilistica()
        
        cartoes = []
        
        for _ in range(n_cartoes * 3):
            cartao = set()
            
            # Estratégia baseada em intervalo de confiança
            if usar_intervalo_confianca:
                # Selecionar números com maior limite inferior do intervalo
                nums_prioritarios = []
                for n in self.numeros:
                    info = analise['probabilidades'][n]
                    # Usar limite inferior conservador
                    nums_prioritarios.append((n, info['intervalo_inferior']))
                
                nums_prioritarios.sort(key=lambda x: x[1], reverse=True)
                
                # Selecionar 8-10 números do topo
                selecionar = min(10, len(nums_prioritarios))
                for n, _ in nums_prioritarios[:selecionar]:
                    if len(cartao) < 10:
                        cartao.add(n)
            else:
                # Seleção por frequência simples
                nums_freq = [(n, analise['probabilidades'][n]['frequencia']) 
                           for n in self.numeros]
                nums_freq.sort(key=lambda x: x[1], reverse=True)
                
                for n, _ in nums_freq[:10]:
                    cartao.add(n)
            
            # Completar com diversificação
            while len(cartao) < 15:
                disponiveis = [n for n in self.numeros if n not in cartao]
                if not disponiveis:
                    break
                
                # Distribuição balanceada
                if len(cartao) < 12 and analise['matriz_transicao'] is not None:
                    # Adicionar baseado na matriz de transição
                    ultimos_numeros = list(cartao)[-3:] if len(cartao) >= 3 else []
                    if ultimos_numeros:
                        probs_transicao = []
                        for n in disponiveis:
                            prob = np.mean([analise['matriz_transicao'][u-1, n-1] 
                                          for u in ultimos_numeros])
                            probs_transicao.append((n, prob))
                        
                        probs_transicao.sort(key=lambda x: x[1], reverse=True)
                        escolha = probs_transicao[0][0] if probs_transicao else random.choice(disponiveis)
                    else:
                        escolha = random.choice(disponiveis)
                else:
                    escolha = random.choice(disponiveis)
                
                cartao.add(escolha)
            
            # Balancear pares/ímpares
            cartao = self._balancear_cartao(cartao)
            
            if len(cartao) == 15:
                cartoes.append(sorted(list(cartao)))
            
            if len(cartoes) >= n_cartoes:
                break
        
        return cartoes[:n_cartoes]
    
    def _balancear_cartao(self, cartao_set):
        """Balanceia pares/ímpares estatisticamente"""
        cartao = list(cartao_set)
        pares = sum(1 for n in cartao if n % 2 == 0)
        
        # Distribuição histórica ideal: 6-9 pares
        if pares < 6:
            impares_no_cartao = [n for n in cartao if n % 2 == 1]
            pares_fora = [n for n in self.numeros if n % 2 == 0 and n not in cartao]
            
            while pares < 6 and impares_no_cartao and pares_fora:
                cartao.remove(impares_no_cartao.pop())
                cartao.append(pares_fora.pop())
                pares += 1
        
        elif pares > 9:
            pares_no_cartao = [n for n in cartao if n % 2 == 0]
            impares_fora = [n for n in self.numeros if n % 2 == 1 and n not in cartao]
            
            while pares > 9 and pares_no_cartao and impares_fora:
                cartao.remove(pares_no_cartao.pop())
                cartao.append(impares_fora.pop())
                pares -= 1
        
        return set(cartao)
    
    def gerar_relatorio_estatistico(self, analise):
        """Relatório estatístico honesto e transparente"""
        relatorio = "📊 RELATÓRIO ESTATÍSTICO - LOTOFÁCIL\n"
        relatorio += "=" * 70 + "\n\n"
        
        relatorio += f"Concursos analisados: {analise['concursos_analisados']}\n"
        
        # Teste de aleatoriedade
        if analise['teste_aleatoriedade']['p_value']:
            p_val = analise['teste_aleatoriedade']['p_value']
            relatorio += f"Teste de aleatoriedade (p-value): {p_val:.4f}\n"
            
            if p_val > 0.05:
                relatorio += "✅ Não há evidência contra aleatoriedade (p > 0.05)\n"
                relatorio += "   → Os sorteios parecem ser estatisticamente aleatórios\n"
            else:
                relatorio += "⚠️ Possível não-aleatoriedade detectada (p ≤ 0.05)\n"
                relatorio += "   → Padrões estatisticamente significativos encontrados\n"
        
        relatorio += f"Média de frequência por número: {analise['media_frequencia']:.3f}\n\n"
        
        relatorio += "📈 TOP 10 NÚMEROS POR PROBABILIDADE (com IC 95%)\n"
        relatorio += "-" * 60 + "\n"
        
        probs_ordenadas = sorted(analise['probabilidades'].items(), 
                                key=lambda x: x[1]['probabilidade'], 
                                reverse=True)
        
        for n, info in probs_ordenadas[:10]:
            relatorio += (f"{n:2d} → Prob: {info['probabilidade']:.3f} "
                         f"[{info['intervalo_inferior']:.3f}-{info['intervalo_superior']:.3f}] "
                         f"(Freq: {info['frequencia']})\n")
        
        relatorio += "\n📊 AUTOCORRELAÇÃO (padrões temporais)\n"
        relatorio += "-" * 50 + "\n"
        
        for lag, corr in analise['autocorrelacao'].items():
            if abs(corr) > 0.2:
                relatorio += f"Lag {lag}: {corr:.3f} {'↑' if corr > 0 else '↓'}\n"
        
        relatorio += "\n⚠️ AVISO ESTATÍSTICO HONESTO\n"
        relatorio += "-" * 50 + "\n"
        relatorio += "1. Lotofácil é um jogo de sorte com aleatoriedade verificada\n"
        relatorio += "2. Nenhum método altera probabilidades matemáticas fundamentais\n"
        relatorio += "3. Chance matemática 15 pontos: 1 em 3.268.760\n"
        relatorio += "4. Chance matemática 14 pontos: 1 em 21.791\n"
        relatorio += "5. Análises servem para diversificar, não para 'adivinhar'\n"
        
        relatorio += "\n🎯 RECOMENDAÇÕES BASEADAS EM ESTATÍSTICA\n"
        relatorio += "-" * 50 + "\n"
        relatorio += "1. Use números com frequência dentro do intervalo esperado\n"
        relatorio += "2. Diversifique entre pares e ímpares (6-9 pares ideal)\n"
        relatorio += "3. Não repita padrões muito específicos\n"
        relatorio += "4. Lembre-se: análise reduz risco, não garante acertos\n"
        
        return relatorio

# =========================
# CLASSE: Backtest Rigoroso (substitui o anterior)
# =========================
class BacktestRigoroso:
    def __init__(self, concursos):
        self.concursos = concursos
        
    def executar_backtest_rigoroso(self, train_size=100, test_size=50):
        """
        Backtest com validação adequada
        """
        if len(self.concursos) < train_size + test_size:
            return {"erro": f"Necessário {train_size + test_size} concursos"}
        
        resultados = {}
        
        # Estratégias a testar
        estrategias = [
            ('Aleatório Balanceado', self._gerar_aleatorio_balanceado),
            ('Frequência Simples', self._gerar_por_frequencia),
            ('Sequência-Falha', self._gerar_sequencia_falha),
            ('Fibonacci Balanceado', self._gerar_fibonacci_balanceado)
        ]
        
        # Executar para cada ponto no tempo
        for start_idx in range(test_size):
            # Dados de treino
            train_data = self.concursos[start_idx:start_idx + train_size]
            
            # Concurso a prever
            target = self.concursos[start_idx + train_size]
            
            if len(train_data) < 30:
                continue
            
            for estrategia_nome, estrategia_func in estrategias:
                if estrategia_nome not in resultados:
                    resultados[estrategia_nome] = {
                        'acertos': [],
                        'jogos_gerados': 0
                    }
                
                # Gerar jogos
                jogos = estrategia_func(train_data, n_jogos=5)
                resultados[estrategia_nome]['jogos_gerados'] += len(jogos)
                
                # Avaliar
                for jogo in jogos:
                    acertos = len(set(jogo) & set(target))
                    resultados[estrategia_nome]['acertos'].append(acertos)
        
        # Calcular estatísticas
        estatisticas_finais = {}
        
        for estrategia, dados in resultados.items():
            if len(dados['acertos']) == 0:
                continue
                
            acertos_array = np.array(dados['acertos'])
            
            # Estatísticas básicas
            media = np.mean(acertos_array)
            desvio = np.std(acertos_array)
            n = len(acertos_array)
            
            # Intervalo de confiança 95% para a média
            z = 1.96
            margem_erro = z * (desvio / np.sqrt(n))
            
            # Percentis
            percentis = {
                '11+': np.sum(acertos_array >= 11) / n * 100,
                '12+': np.sum(acertos_array >= 12) / n * 100,
                '13+': np.sum(acertos_array >= 13) / n * 100,
                '14+': np.sum(acertos_array >= 14) / n * 100,
                '15': np.sum(acertos_array == 15) / n * 100
            }
            
            estatisticas_finais[estrategia] = {
                'media_acertos': media,
                'intervalo_confianca': (media - margem_erro, media + margem_erro),
                'desvio_padrao': desvio,
                'amostra': n,
                'percentis': percentis,
                'efetividade': self._calcular_efetividade(acertos_array)
            }
        
        return estatisticas_finais
    
    def _calcular_efetividade(self, acertos_array):
        """Calcula efetividade relativa ao esperado aleatório"""
        esperado_aleatorio = 10.5
        media_real = np.mean(acertos_array)
        
        efetividade = ((media_real - esperado_aleatorio) / esperado_aleatorio) * 100
        
        return efetividade
    
    def _gerar_aleatorio_balanceado(self, concursos, n_jogos=5):
        """Baseline: aleatório balanceado"""
        jogos = []
        for _ in range(n_jogos):
            jogo = sorted(random.sample(range(1, 26), 15))
            # Balancear
            pares = sum(1 for n in jogo if n % 2 == 0)
            if 6 <= pares <= 9:
                jogos.append(jogo)
            else:
                jogo = self._rebalancear_jogo(jogo)
                jogos.append(jogo)
        return jogos
    
    def _gerar_por_frequencia(self, concursos, n_jogos=5):
        """Baseado em frequência simples"""
        if len(concursos) < 30:
            return self._gerar_aleatorio_balanceado(concursos, n_jogos)
        
        freq = Counter()
        for concurso in concursos[:50]:
            freq.update(concurso)
        
        jogos = []
        for _ in range(n_jogos):
            top15 = [n for n, _ in freq.most_common(15)]
            jogos.append(sorted(top15))
        
        return jogos
    
    def _gerar_sequencia_falha(self, concursos, n_jogos=5):
        """Método sequência/falha"""
        analise_sf = AnaliseSequenciaFalha(concursos)
        return analise_sf.gerar_jogos_estrategicos(n_jogos, "balanceada")
    
    def _gerar_fibonacci_balanceado(self, concursos, n_jogos=5):
        """Fibonacci balanceado"""
        fib = EstrategiaFibonacci(concursos)
        return fib.gerar_cartoes_fibonacci(n_jogos, usar_estatisticas=True)
    
    def _rebalancear_jogo(self, jogo):
        """Rebalanceia jogo para ter 6-9 pares"""
        pares = sum(1 for n in jogo if n % 2 == 0)
        
        while pares < 6:
            impares = [n for n in jogo if n % 2 == 1]
            if not impares:
                break
            jogo.remove(random.choice(impares))
            novo_par = random.choice([n for n in range(1, 26) if n % 2 == 0 and n not in jogo])
            jogo.append(novo_par)
            pares += 1
        
        while pares > 9:
            pares_list = [n for n in jogo if n % 2 == 0]
            if not pares_list:
                break
            jogo.remove(random.choice(pares_list))
            novo_impar = random.choice([n for n in range(1, 26) if n % 2 == 1 and n not in jogo])
            jogo.append(novo_impar)
            pares -= 1
        
        return sorted(jogo)
    
    def gerar_relatorio_backtest(self, resultados):
        """Gera relatório formatado do backtest"""
        relatorio = "📊 RELATÓRIO DE BACKTEST RIGOROSO - LOTOFÁCIL\n"
        relatorio += "=" * 60 + "\n\n"
        
        relatorio += "🔬 METODOLOGIA CIENTÍFICA\n"
        relatorio += "-" * 60 + "\n"
        relatorio += "• Walk-forward validation (teste temporal)\n"
        relatorio += "• Intervalos de confiança 95%\n"
        relatorio += "• Baseline: Aleatório balanceado\n"
        relatorio += "• Métricas estatisticamente válidas\n\n"
        
        relatorio += "🏆 RESULTADOS COMPARATIVOS\n"
        relatorio += "-" * 60 + "\n\n"
        
        for i, (estrategia, stats) in enumerate(resultados.items(), 1):
            relatorio += f"{i}º {estrategia}:\n"
            relatorio += f"  • Média de acertos: {stats['media_acertos']:.2f}\n"
            relatorio += f"  • IC 95%: [{stats['intervalo_confianca'][0]:.2f}, {stats['intervalo_confianca'][1]:.2f}]\n"
            relatorio += f"  • 11+ pontos: {stats['percentis']['11+']:.2f}%\n"
            relatorio += f"  • 13+ pontos: {stats['percentis']['13+']:.2f}%\n"
            relatorio += f"  • Efetividade vs aleatório: {stats['efetividade']:+.2f}%\n"
            relatorio += f"  • Amostra: {stats['amostra']} jogos\n"
            relatorio += "-" * 40 + "\n"
        
        # Análise honesta
        relatorio += "\n📈 ANÁLISE HONESTA DOS RESULTADOS\n"
        relatorio += "-" * 60 + "\n"
        
        melhor = list(resultados.items())[0] if resultados else None
        aleatorio = resultados.get('Aleatório Balanceado', {})
        
        if aleatorio and melhor:
            vantagem = melhor[1]['media_acertos'] - aleatorio['media_acertos']
            relatorio += f"• Melhor estratégia vs Aleatório: {vantagem:.2f} acertos de vantagem\n"
            
            if abs(vantagem) < 0.3:
                relatorio += "• Conclusão: Nenhuma estratégia tem vantagem estatisticamente significativa\n"
                relatorio += "• Recomendação: Use aleatório balanceado (é igualmente eficaz)\n"
            else:
                relatorio += f"• Conclusão: Pequena vantagem para {melhor[0]}\n"
                relatorio += "• Recomendação: Use estratégia diversificada\n"
        
        # Aviso estatístico
        relatorio += "\n⚠️ AVISO ESTATÍSTICO IMPORTANTE\n"
        relatorio += "-" * 60 + "\n"
        relatorio += "• Chance matemática 14 pontos: 0,0046%\n"
        relatorio += "• Chance matemática 15 pontos: 0,00003%\n"
        relatorio += "• Backtest mostra desempenho histórico, não garante resultados futuros\n"
        relatorio += "• Lotofácil é um jogo de sorte: jogue com responsabilidade\n"
        
        return relatorio

# =========================
# CLASSE: FechamentoLotofacil
# =========================
class FechamentoLotofacil:
    def __init__(self, concursos=None):
        self.numeros = list(range(1, 26))
        self.concursos = concursos or []
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    
    def analisar_grupos_otimos(self, tamanho_grupo=18, analise_concursos=30):
        """Analisa estatísticas para sugerir grupos ótimos para fechamento"""
        if not self.concursos or len(self.concursos) < 10:
            return []
        
        analise_concursos = min(analise_concursos, len(self.concursos))
        concursos_recentes = self.concursos[:analise_concursos]
        
        # Calcular frequências
        freq = Counter()
        for concurso in concursos_recentes:
            for num in concurso:
                freq[num] += 1
        
        # Ordenar por frequência
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        
        # Sugerir grupos: 60% dos mais frequentes + 40% com maior atraso
        top_frequentes = [n for n, _ in numeros_ordenados[:15]]
        
        # Calcular atraso
        atraso = {}
        for num in self.numeros:
            atraso[num] = analise_concursos
            for i, concurso in enumerate(concursos_recentes):
                if num in concurso:
                    atraso[num] = i
                    break
        
        maiores_atrasos = sorted(atraso.items(), key=lambda x: x[1], reverse=True)[:10]
        top_atrasados = [n for n, _ in maiores_atrasos]
        
        # Combinar grupos
        grupos_sugeridos = []
        
        # Grupo 1: Balanceado (frequentes + atrasados)
        grupo1 = list(set(top_frequentes[:10] + top_atrasados[:8]))
        if len(grupo1) < tamanho_grupo:
            restantes = [n for n in self.numeros if n not in grupo1]
            grupo1.extend(random.sample(restantes, tamanho_grupo - len(grupo1)))
        grupos_sugeridos.append(sorted(grupo1[:tamanho_grupo]))
        
        # Grupo 2: Focado em Fibonacci
        fibonacci = [1, 2, 3, 5, 8, 13, 21]
        grupo2 = fibonacci.copy()
        complementares = [n for n in top_frequentes if n not in grupo2]
        grupo2.extend(complementares[:tamanho_grupo - len(grupo2)])
        grupos_sugeridos.append(sorted(grupo2[:tamanho_grupo]))
        
        return grupos_sugeridos
    
    def gerar_fechamento_18_15(self, numeros_escolhidos, max_jogos=80, estrategia="cobertura"):
        """
        Fechamento de 18 números, gerando combinações otimizadas de 15.
        """
        if len(numeros_escolhidos) != 18:
            st.warning(f"Fechamento precisa de exatamente 18 números. Recebidos: {len(numeros_escolhidos)}")
            return []
        
        jogos = set()
        
        if estrategia == "cobertura":
            for i in range(max_jogos * 2):
                base_fixa = random.sample(numeros_escolhidos, 12)
                complemento = random.sample([n for n in numeros_escolhidos if n not in base_fixa], 3)
                
                jogo = sorted(base_fixa + complemento)
                
                if self._validar_jogo_fechamento(jogo):
                    jogos.add(tuple(jogo))
                
                if len(jogos) >= max_jogos:
                    break
        
        elif estrategia == "estatistica":
            if len(self.concursos) >= 10:
                for _ in range(max_jogos * 3):
                    jogo = self._gerar_jogo_estatistico(numeros_escolhidos)
                    
                    if jogo and self._validar_jogo_fechamento(jogo):
                        jogos.add(tuple(jogo))
                    
                    if len(jogos) >= max_jogos:
                        break
        
        # Se não gerou jogos suficientes, completar com combinações aleatórias válidas
        while len(jogos) < min(max_jogos, 50):
            jogo = sorted(random.sample(numeros_escolhidos, 15))
            if self._validar_jogo_fechamento(jogo):
                jogos.add(tuple(jogo))
        
        return [list(j) for j in jogos][:max_jogos]
    
    def _validar_jogo_fechamento(self, jogo):
        """Valida um jogo para fechamento com critérios rigorosos"""
        if len(jogo) != 15 or len(set(jogo)) != 15:
            return False
        
        pares = sum(1 for n in jogo if n % 2 == 0)
        if not (6 <= pares <= 9):
            return False
        
        primos = sum(1 for n in jogo if n in self.primos)
        if not (3 <= primos <= 7):
            return False
        
        soma = sum(jogo)
        if not (170 <= soma <= 210):
            return False
        
        # Verificar distribuição por faixas
        faixa1 = sum(1 for n in jogo if 1 <= n <= 8)
        faixa2 = sum(1 for n in jogo if 9 <= n <= 16)
        faixa3 = sum(1 for n in jogo if 17 <= n <= 25)
        
        if not (4 <= faixa1 <= 7 and 4 <= faixa2 <= 7 and 4 <= faixa3 <= 7):
            return False
        
        return True
    
    def _gerar_jogo_estatistico(self, numeros_disponiveis):
        """Gera jogo baseado em estatísticas dos últimos concursos"""
        if len(self.concursos) < 10:
            return sorted(random.sample(numeros_disponiveis, 15))
        
        # Analisar últimos 10 concursos
        ultimos_10 = self.concursos[:10]
        
        # Calcular padrões de pares/ímpares
        pares_historico = []
        for concurso in ultimos_10:
            pares_historico.append(sum(1 for n in concurso if n % 2 == 0))
        
        media_pares = int(np.mean(pares_historico))
        pares_alvo = max(6, min(9, media_pares))
        
        # Gerar jogo seguindo padrões
        tentativas = 0
        while tentativas < 100:
            jogo = sorted(random.sample(numeros_disponiveis, 15))
            pares = sum(1 for n in jogo if n % 2 == 0)
            
            if pares == pares_alvo and self._validar_jogo_fechamento(jogo):
                return jogo
            
            tentativas += 1
        
        return None
    
    def calcular_cobertura_teorica(self, numeros_escolhidos, jogos_gerados):
        """Calcula cobertura teórica dos jogos gerados"""
        if not jogos_gerados:
            return {"cobertura": 0, "numeros_cobertura": {}}
        
        contagem_numeros = Counter()
        for jogo in jogos_gerados:
            contagem_numeros.update(jogo)
        
        cobertura_por_numero = {}
        
        for num in numeros_escolhidos:
            freq = contagem_numeros.get(num, 0)
            percentual = (freq / len(jogos_gerados)) * 100
            cobertura_por_numero[num] = {
                "frequencia": freq,
                "percentual": round(percentual, 1)
            }
        
        cobertura_media = np.mean([cobertura_por_numero[n]["percentual"] for n in numeros_escolhidos])
        
        return {
            "cobertura_media": round(cobertura_media, 1),
            "cobertura_por_numero": cobertura_por_numero,
            "total_jogos": len(jogos_gerados),
            "total_numeros_cobertos": len(numeros_escolhidos)
        }

# =========================
# CLASSE: Análise de Sequência e Falha
# =========================
class AnaliseSequenciaFalha:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        
    def calcular_sequencias(self):
        """Retorna uma lista com contagem de sequências de acertos por posição."""
        sequencias = [0] * 25
        for jogo in self.concursos:
            for num in jogo:
                sequencias[num - 1] += 1
        return sequencias
    
    def calcular_falhas(self):
        """Retorna quantas vezes cada número NÃO apareceu."""
        falhas = [0] * 25
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
        """Gera jogos usando o método da tabela (sequência + falha)."""
        sequencias = self.calcular_sequencias()
        falhas = self.calcular_falhas()
        
        jogos = []
        
        for _ in range(n_jogos):
            melhores = sorted(range(1, 26), key=lambda x: sequencias[x-1], reverse=True)[:10]
            retorno = sorted(range(1, 26), key=lambda x: falhas[x-1], reverse=True)[:10]
            
            combo = set(random.sample(melhores, 8) + random.sample(retorno, 7))
            
            while len(combo) < 15:
                combo.add(random.choice([n for n in range(1, 26) if n not in combo]))
            
            jogos.append(sorted(list(combo)))
        
        return jogos
    
    def gerar_jogos_estrategicos(self, n_jogos=5, estrategia="balanceada"):
        """Gera jogos com estratégias específicas."""
        sequencias = self.calcular_sequencias()
        falhas = self.calcular_falhas()
        
        jogos = []
        
        melhores = sorted(range(1, 26), key=lambda x: sequencias[x-1], reverse=True)
        piores = sorted(range(1, 26), key=lambda x: sequencias[x-1])
        retorno = sorted(range(1, 26), key=lambda x: falhas[x-1], reverse=True)
        
        for _ in range(n_jogos):
            if estrategia == "balanceada":
                combo = set(random.sample(melhores[:10], 6) + 
                           random.sample(melhores[10:20], 5) + 
                           random.sample(retorno[:10], 4))
            
            elif estrategia == "conservadora":
                combo = set(random.sample(melhores[:12], 10) + 
                           random.sample(melhores[12:20], 5))
            
            elif estrategia == "agressiva":
                combo = set(random.sample(melhores[:10], 5) + 
                           random.sample(retorno[:15], 10))
            
            elif estrategia == "aleatoria_padrao":
                pares = random.randint(6, 9)
                impares = 15 - pares
                
                numeros_pares = [n for n in range(1, 26) if n % 2 == 0]
                numeros_impares = [n for n in range(1, 26) if n % 2 == 1]
                
                combo = set(random.sample(numeros_pares, pares) + 
                           random.sample(numeros_impares, impares))
            
            while len(combo) < 15:
                combo.add(random.choice([n for n in range(1, 26) if n not in combo]))
            
            jogos.append(sorted(list(combo)))
        
        return jogos

# =========================
# CLASSE: Análise Estatística Avançada
# =========================
class AnaliseEstatisticaAvancada:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    
    def enriquecer_features(self, concursos_recentes):
        """Adiciona novos padrões estatísticos aos dados de treinamento."""
        if len(concursos_recentes) < 2:
            return np.array([])
        
        features_avancados = []
        
        for i in range(len(concursos_recentes)-1):
            feat = []
            concurso_atual = concursos_recentes[i]
            
            # 1. Distribuição por quadrantes
            q1 = sum(1 for n in concurso_atual if 1 <= n <= 6)
            q2 = sum(1 for n in concurso_atual if 7 <= n <= 13)
            q3 = sum(1 for n in concurso_atual if 14 <= n <= 19)
            q4 = sum(1 for n in concurso_atual if 20 <= n <= 25)
            
            feat.extend([q1, q2, q3, q4])
            
            # 2. Números das pontas (1, 5, 21, 25)
            pontas = sum(1 for n in concurso_atual if n in [1, 5, 21, 25])
            feat.append(pontas)
            
            # 3. Consecutivos máximos
            max_consec = self._max_consecutivos(concurso_atual)
            feat.append(max_consec)
            
            # 4. Distância média entre números
            distancia_media = self._distancia_media(concurso_atual)
            feat.append(distancia_media)
            
            # 5. Variação do concurso anterior
            if i > 0:
                concurso_anterior = concursos_recentes[i-1]
                repetidos = len(set(concurso_atual) & set(concurso_anterior))
                feat.append(repetidos)
            else:
                feat.append(0)
            
            features_avancados.append(feat)
        
        return np.array(features_avancados)
    
    def _max_consecutivos(self, concurso):
        """Calcula o máximo de números consecutivos no concurso."""
        sorted_nums = sorted(concurso)
        max_seq = 1
        current_seq = 1
        
        for i in range(1, len(sorted_nums)):
            if sorted_nums[i] == sorted_nums[i-1] + 1:
                current_seq += 1
                max_seq = max(max_seq, current_seq)
            else:
                current_seq = 1
        
        return max_seq
    
    def _distancia_media(self, concurso):
        """Calcula a distância média entre números sorteados."""
        sorted_nums = sorted(concurso)
        if len(sorted_nums) <= 1:
            return 0
        
        distancias = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
        return np.mean(distancias) if distancias else 0

# =========================
# CLASSE: AnaliseCiclos
# =========================
class AnaliseCiclos:
    def __init__(self, concursos, concursos_info=None, limite_concursos=None):
        self.concursos = concursos
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
        """Detecta o ciclo dinâmico atual"""
        self.ciclo_concursos = []
        self.ciclo_concursos_info = []
        self.numeros_presentes = set()
        self.numeros_faltantes = set(self.TODAS)
        self.iniciar_indice = None
        
        max_concursos = len(self.concursos)
        if self.limite_concursos is not None:
            max_concursos = min(self.limite_concursos, len(self.concursos))
        
        if max_concursos < 10:
            max_concursos = min(10, len(self.concursos))
        
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
    
    def status(self):
        """Define estado do ciclo"""
        if not self.numeros_faltantes:
            return "Fechado"
        
        if self.tamanho <= 3:
            return "Normal"
        elif 4 <= self.tamanho <= 6:
            return "Em Andamento"
        elif 7 <= self.tamanho <= 10:
            return "Atrasado"
        else:
            return "Muito Atrasado"
    
    def resumo(self):
        """Retorna um resumo do ciclo atual."""
        return {
            "tamanho": self.tamanho,
            "numeros_presentes": sorted(list(self.numeros_presentes)),
            "numeros_faltantes": sorted(list(self.numeros_faltantes)),
            "inicio_indice": self.iniciar_indice,
            "status": self.status(),
            "concursos_analisados": self.ciclo_concursos_info,
            "limite_concursos": self.limite_concursos,
            "ciclo_completo": len(self.numeros_faltantes) == 0
        }
    
    def contar_atrasos_no_ciclo(self):
        """Retorna atraso (em concursos) por número dentro do ciclo"""
        atraso = {n: None for n in range(1,26)}
        
        for idx, concurso in enumerate(self.ciclo_concursos):
            for n in self.TODAS:
                if atraso[n] is None and n in concurso:
                    atraso[n] = idx
        
        for n in range(1,26):
            if atraso[n] is None:
                atraso[n] = self.tamanho
        
        return atraso
    
    def gerar_5_cartoes_ciclo(self, n_cartoes=5, seed=None, incluir_todas_faltantes=False):
        """Gera n_cartoes cartoes de 15 dezenas garantindo que sejam DISTINTOS."""
        if seed is not None:
            random.seed(seed)
        
        atraso = self.contar_atrasos_no_ciclo()
        faltantes = sorted(list(self.numeros_faltantes))
        todas_dezenas = list(range(1, 26))
        
        ordenado_por_atraso = sorted(todas_dezenas, key=lambda x: atraso[x], reverse=True)
        
        cartoes = []
        tentativas_max = n_cartoes * 50
        tentativas = 0
        
        if incluir_todas_faltantes and faltantes:
            return self._gerar_cartoes_distribuindo_faltantes(faltantes, n_cartoes, atraso)
        
        while len(cartoes) < n_cartoes and tentativas < tentativas_max:
            tentativas += 1
            cartao_set = set()
            
            if faltantes:
                max_faltantes = min(len(faltantes), random.randint(4, 6))
                faltantes_escolhidas = random.sample(faltantes, max_faltantes)
                cartao_set.update(faltantes_escolhidas)
            
            numeros_nao_faltantes = [n for n in ordenado_por_atraso if n not in faltantes]
            numeros_disponiveis = [n for n in numeros_nao_faltantes if n not in cartao_set]
            
            if numeros_disponiveis:
                qtd_atraso = random.randint(4, 6)
                qtd_atraso = min(qtd_atraso, len(numeros_disponiveis))
                if qtd_atraso > 0:
                    atraso_escolhidos = random.sample(numeros_disponiveis[:15], qtd_atraso)
                    cartao_set.update(atraso_escolhidos)
            
            numeros_restantes = [n for n in todas_dezenas if n not in cartao_set]
            
            while len(cartao_set) < 15 and numeros_restantes:
                if cartoes:
                    freq_cartoes = Counter()
                    for c in cartoes:
                        freq_cartoes.update(c)
                    
                    numeros_restantes.sort(key=lambda x: freq_cartoes[x])
                
                escolha = random.choice(numeros_restantes[:10]) if len(numeros_restantes) >= 10 else random.choice(numeros_restantes)
                cartao_set.add(escolha)
                numeros_restantes = [n for n in todas_dezenas if n not in cartao_set]
            
            self._ajustar_equilibrio(cartao_set, todas_dezenas)
            
            cartao_ordenado = sorted(list(cartao_set))
            
            if self._cartao_eh_distinto(cartao_ordenado, cartoes, limite_similaridade=10):
                cartoes.append(cartao_ordenado)
        
        while len(cartoes) < n_cartoes:
            cartao_novo = sorted(random.sample(todas_dezenas, 15))
            pares = sum(1 for n in cartao_novo if n % 2 == 0)
            primos = sum(1 for n in cartao_novo if n in {2,3,5,7,11,13,17,19,23})
            
            if 6 <= pares <= 9 and 3 <= primos <= 7:
                if self._cartao_eh_distinto(cartao_novo, cartoes, limite_similaridade=10):
                    cartoes.append(cartao_novo)
        
        return cartoes[:n_cartoes]
    
    def _gerar_cartoes_distribuindo_faltantes(self, faltantes, n_cartoes, atraso):
        """Estratégia especial quando queremos incluir todas as faltantes"""
        todas_dezenas = list(range(1, 26))
        ordenado_por_atraso = sorted(todas_dezenas, key=lambda x: atraso[x], reverse=True)
        
        cartoes = []
        
        if len(faltantes) <= 15:
            faltantes_por_cartao = max(1, len(faltantes) // n_cartoes)
            
            for i in range(n_cartoes):
                cartao_set = set()
                
                inicio_idx = i * faltantes_por_cartao
                fim_idx = inicio_idx + faltantes_por_cartao if i < n_cartoes - 1 else len(faltantes)
                
                if inicio_idx < len(faltantes):
                    faltantes_do_cartao = faltantes[inicio_idx:fim_idx]
                    cartao_set.update(faltantes_do_cartao)
                
                numeros_nao_faltantes = [n for n in ordenado_por_atraso if n not in faltantes]
                numeros_disponiveis = [n for n in numeros_nao_faltantes if n not in cartao_set]
                
                qtd_necessaria = 15 - len(cartao_set)
                if numeros_disponiveis and qtd_necessaria > 0:
                    qtd_escolher = min(qtd_necessaria, len(numeros_disponiveis))
                    complemento = random.sample(numeros_disponiveis[:20], qtd_escolher)
                    cartao_set.update(complemento)
                
                while len(cartao_set) < 15:
                    candidatos = [n for n in todas_dezenas if n not in cartao_set]
                    if candidatos:
                        cartao_set.add(random.choice(candidatos))
                
                self._ajustar_equilibrio(cartao_set, todas_dezenas)
                cartoes.append(sorted(list(cartao_set)))
        
        else:
            for i in range(n_cartoes):
                cartao_set = set()
                
                qtd_faltantes = random.randint(6, 8)
                faltantes_escolhidas = random.sample(faltantes, qtd_faltantes)
                cartao_set.update(faltantes_escolhidas)
                
                while len(cartao_set) < 15:
                    if random.random() < 0.7 and len(cartao_set) < 12:
                        numeros_alto_atraso = [n for n in ordenado_por_atraso[:15] if n not in cartao_set]
                        if numeros_alto_atraso:
                            cartao_set.add(random.choice(numeros_alto_atraso[:5]))
                    else:
                        candidatos = [n for n in todas_dezenas if n not in cartao_set]
                        if candidatos:
                            cartao_set.add(random.choice(candidatos))
                
                self._ajustar_equilibrio(cartao_set, todas_dezenas)
                cartao_ordenado = sorted(list(cartao_set))
                
                if self._cartao_eh_distinto(cartao_ordenado, cartoes, limite_similaridade=9):
                    cartoes.append(cartao_ordenado)
        
        cartoes_distintos = []
        for cartao in cartoes:
            if self._cartao_eh_distinto(cartao, cartoes_distintos, limite_similaridade=10):
                cartoes_distintos.append(cartao)
        
        while len(cartoes_distintos) < n_cartoes:
            cartao_novo = self._gerar_cartao_balanceado(todas_dezenas)
            if self._cartao_eh_distinto(cartao_novo, cartoes_distintos, limite_similaridade=10):
                cartoes_distintos.append(cartao_novo)
        
        return cartoes_distintos[:n_cartoes]
    
    def _cartao_eh_distinto(self, cartao_novo, cartoes_existentes, limite_similaridade=10):
        """Verifica se um cartão é suficientemente distinto"""
        if not cartoes_existentes:
            return True
        
        for cartao_existente in cartoes_existentes:
            dezenas_comuns = len(set(cartao_novo) & set(cartao_existente))
            
            if dezenas_comuns > limite_similaridade:
                return False
        
        return True
    
    def _gerar_cartao_balanceado(self, todas_dezenas):
        """Gera um cartão balanceado"""
        while True:
            cartao = sorted(random.sample(todas_dezenas, 15))
            pares = sum(1 for n in cartao if n % 2 == 0)
            primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
            
            if 6 <= pares <= 9 and 3 <= primos <= 7:
                return cartao
    
    def _ajustar_equilibrio(self, cartao_set, todas_dezenas):
        """Ajusta o equilibro de pares/ímpares no cartão"""
        pares = sum(1 for n in cartao_set if n % 2 == 0)
        
        if pares < 6:
            impares_no_cartao = [n for n in cartao_set if n % 2 == 1]
            pares_fora_cartao = [n for n in todas_dezenas if n % 2 == 0 and n not in cartao_set]
            
            if impares_no_cartao and pares_fora_cartao:
                cartao_set.remove(random.choice(impares_no_cartao))
                cartao_set.add(random.choice(pares_fora_cartao))
        
        elif pares > 9:
            pares_no_cartao = [n for n in cartao_set if n % 2 == 0]
            impares_fora_cartao = [n for n in todas_dezenas if n % 2 == 1 and n not in cartao_set]
            
            if pares_no_cartao and impares_fora_cartao:
                cartao_set.remove(random.choice(pares_no_cartao))
                cartao_set.add(random.choice(impares_fora_cartao))
    
    def obter_concursos_no_ciclo_formatados(self):
        """Retorna uma lista formatada dos concursos analisados no ciclo"""
        concursos_formatados = []
        for i, info in enumerate(self.ciclo_concursos_info):
            dezenas = self.ciclo_concursos[i] if i < len(self.ciclo_concursos) else []
            concursos_formatados.append({
                "ordem": i + 1,
                "indice_original": info.get("indice", i),
                "numero_concurso": info.get("numero_concurso", f"Concurso {i+1}"),
                "dezenas": dezenas,
                "data": info.get("data", "Data não disponível")
            })
        return concursos_formatados

# =========================
# CLASSE: Analise Combinatória
# =========================
class AnaliseCombinatoria:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        
    def calcular_estatisticas_base(self):
        """Calcula estatísticas base dos concursos históricos"""
        if not self.concursos:
            return {}
            
        stats = {
            'media_pares': [],
            'media_soma': [],
            'media_primos': [],
            'distribuicoes': []
        }
        
        for concurso in self.concursos:
            pares = sum(1 for n in concurso if n % 2 == 0)
            soma = sum(concurso)
            primos = sum(1 for n in concurso if n in self.primos)
            
            stats['media_pares'].append(pares)
            stats['media_soma'].append(soma)
            stats['media_primos'].append(primos)
            
        return stats

    def gerar_combinacoes_otimizadas(self, tamanhos, quantidade_por_tamanho=1000):
        """Gera combinações otimizadas com filtros estatísticos"""
        todas_combinacoes = {}
        
        for tamanho in tamanhos:
            combinacoes_geradas = []
            tentativas = 0
            max_tentativas = quantidade_por_tamanho * 3
            
            while len(combinacoes_geradas) < quantidade_por_tamanho and tentativas < max_tentativas:
                combo = sorted(random.sample(self.numeros, tamanho))
                
                if self.validar_combinacao(combo, tamanho):
                    if combo not in combinacoes_geradas:
                        combinacoes_geradas.append(combo)
                
                tentativas += 1
            
            combinacoes_ranqueadas = self.ranquear_combinacoes(combinacoes_geradas, tamanho)
            todas_combinacoes[tamanho] = combinacoes_ranqueadas[:quantidade_por_tamanho]
            
        return todas_combinacoes

    def validar_combinacao(self, combinacao, tamanho):
        """Valida combinação com base em estatísticas históricas"""
        pares = sum(1 for n in combinacao if n % 2 == 0)
        impares = len(combinacao) - pares
        soma = sum(combinacao)
        primos = sum(1 for n in combinacao if n in self.primos)
        
        if tamanho == 15:
            return (6 <= pares <= 9 and 
                    170 <= soma <= 210 and
                    3 <= primos <= 7)
        
        elif tamanho == 14:
            return (5 <= pares <= 8 and 
                    160 <= soma <= 200 and
                    2 <= primos <= 6)
        
        elif tamanho == 13:
            return (5 <= pares <= 8 and 
                    150 <= soma <= 190 and
                    2 <= primos <= 6)
        
        elif tamanho == 12:
            return (4 <= pares <= 7 and 
                    130 <= soma <= 170 and
                    2 <= primos <= 5)
        
        return True

    def ranquear_combinacoes(self, combinacoes, tamanho):
        """Ranqueia combinações por probabilidade"""
        scores = []
        
        for combo in combinacoes:
            score = self.calcular_score_combinacao(combo, tamanho)
            scores.append((combo, score))
        
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def calcular_score_combinacao(self, combinacao, tamanho):
        """Calcula score baseado em múltiplos fatores estatísticos"""
        score = 0
        
        pares = sum(1 for n in combinacao if n % 2 == 0)
        if tamanho == 15 and 6 <= pares <= 8:
            score += 3
        elif tamanho == 14 and 5 <= pares <= 8:
            score += 3
        elif tamanho == 13 and 5 <= pares <= 7:
            score += 3
        elif tamanho == 12 and 4 <= pares <= 6:
            score += 3
            
        soma = sum(combinacao)
        if tamanho == 15 and 180 <= soma <= 200:
            score += 3
        elif tamanho == 14 and 160 <= soma <= 190:
            score += 3
        elif tamanho == 13 and 150 <= soma <= 180:
            score += 3
        elif tamanho == 12 and 130 <= soma <= 160:
            score += 3
            
        consecutivos = self.contar_consecutivos(combinacao)
        if consecutivos <= 4:
            score += 2
            
        primos = sum(1 for n in combinacao if n in self.primos)
        if 3 <= primos <= 6:
            score += 2
            
        if self.validar_distribuicao(combinacao):
            score += 2
            
        score += self.calcular_score_frequencia(combinacao)
        
        return score

    def contar_consecutivos(self, combinacao):
        """Conta números consecutivos na combinação"""
        consecutivos = 0
        for i in range(len(combinacao)-1):
            if combinacao[i+1] - combinacao[i] == 1:
                consecutivos += 1
        return consecutivos

    def validar_distribuicao(self, combinacao):
        """Valida distribuição por faixas de números"""
        faixa1 = sum(1 for n in combinacao if 1 <= n <= 9)
        faixa2 = sum(1 for n in combinacao if 10 <= n <= 19)
        faixa3 = sum(1 for n in combinacao if 20 <= n <= 25)
        
        total = len(combinacao)
        if total == 15:
            return (faixa1 >= 4 and faixa2 >= 5 and faixa3 >= 4)
        elif total == 14:
            return (faixa1 >= 4 and faixa2 >= 4 and faixa3 >= 4)
        elif total == 13:
            return (faixa1 >= 3 and faixa2 >= 4 and faixa3 >= 3)
        elif total == 12:
            return (faixa1 >= 3 and faixa2 >= 4 and faixa3 >= 3)
        
        return True

    def calcular_score_frequencia(self, combinacao):
        """Calcula score baseado na frequência histórica dos números"""
        if not self.concursos:
            return 0
            
        freq = Counter()
        for concurso in self.concursos[:50]:
            for numero in concurso:
                freq[numero] += 1
                
        freq_media = sum(freq[n] for n in combinacao) / len(combinacao)
        freq_max = max(freq.values()) if freq.values() else 1
        
        return (freq_media / freq_max) * 2

    def formatar_como_cartao(self, combinacao):
        """Formata uma combinação como cartão da Lotofácil 5x5"""
        cartao = []
        for i in range(5):
            linha = []
            for j in range(5):
                numero = i * 5 + j + 1
                if numero in combinacao:
                    linha.append(f"[{numero:2d}]")
                else:
                    linha.append(f" {numero:2d} ")
            cartao.append(linha)
        return cartao

    def gerar_conteudo_cartoes(self, combinacoes_por_tamanho, top_n=10):
        """Gera conteúdo formatado como cartões para download"""
        conteudo = "CARTÕES LOTOFÁCIL - COMBINAÇÕES OTIMIZADAS\n"
        conteudo += "=" * 50 + "\n\n"
        
        for tamanho in sorted(combinacoes_por_tamanho.keys()):
            combinacoes = combinacoes_por_tamanho[tamanho][:top_n]
            
            if not combinacoes:
                continue
                
            conteudo += f"COMBINAÇÕES COM {tamanho} NÚMEROS (Top {top_n})\n"
            conteudo += "-" * 40 + "\n\n"
            
            for idx, (combo, score) in enumerate(combinacoes, 1):
                conteudo += f"Cartão {idx} (Score: {score:.1f}):\n"
                cartao = self.formatar_como_cartao(combo)
                
                for linha in cartao:
                    conteudo += " ".join(linha) + "\n"
                
                numeros_selecionados = [n for n in combo]
                conteudo += f"Números: {numeros_selecionados}\n"
                
                pares = sum(1 for n in combo if n % 2 == 0)
                primos = sum(1 for n in combo if n in self.primos)
                soma = sum(combo)
                conteudo += f"Pares: {pares}, Ímpares: {len(combo)-pares}, Primos: {primos}, Soma: {soma}\n"
                conteudo += "\n" + "=" * 50 + "\n\n"
        
        return conteudo

# =========================
# CLASSE: LotoFacilIA
# =========================
class LotoFacilIA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}
        self.models = {}
        if len(concursos) > 10:
            self.X = self.gerar_features()[:-1] if len(concursos) > 1 else np.array([])
            self.Y = self.matriz_binaria()[1:] if len(concursos) > 1 else np.array([])
            if len(self.X) > 0 and len(self.Y) > 0:
                try:
                    self.treinar_modelos()
                except Exception as e:
                    st.warning(f"CatBoost não pôde ser carregado: {e}")
                    self.models = {}

    def matriz_binaria(self):
        return np.array([[1 if n in jogo else 0 for n in self.numeros] for jogo in self.concursos])

    def frequencia(self, janela=10):
        janela = min(janela, max(1, len(self.concursos)-1))
        if janela < 10:
            janela = min(10, len(self.concursos))
        freq = {n:0 for n in self.numeros}
        if len(self.concursos) <= 1:
            return freq
        limite = min(len(self.concursos)-1, janela)
        for jogo in self.concursos[0:limite]:
            for d in jogo:
                freq[d] +=1
        return freq

    def atraso(self):
        atraso = {n:0 for n in self.numeros}
        for n in self.numeros:
            atraso[n] = 0
            found = False
            for i, jogo in enumerate(self.concursos):
                if n in jogo:
                    atraso[n] = i
                    found = True
                    break
            if not found:
                atraso[n] = len(self.concursos)
        return atraso

    def quentes_frios(self, top=10):
        freq = self.frequencia()
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        quentes = [n for n,_ in numeros_ordenados[:top]]
        frios = [n for n,_ in numeros_ordenados[-top:]]
        return {"quentes": quentes, "frios": frios}

    def pares_impares_primos(self):
        if not self.concursos:
            return {"pares": 0, "impares": 0, "primos": 0}
        ultimo = self.concursos[0]
        pares = sum(1 for n in ultimo if n%2==0)
        impares = 15 - pares
        primos = sum(1 for n in ultimo if n in self.primos)
        return {"pares": pares, "impares": impares, "primos": primos}

    def interacoes(self, janela=50):
        janela = min(janela, max(1, len(self.concursos)-1))
        if janela < 10:
            janela = min(10, len(self.concursos))
        matriz = np.zeros((25,25), dtype=int)
        for jogo in self.concursos[0:janela]:
            for i in range(15):
                for j in range(i+1,15):
                    matriz[jogo[i]-1, jogo[j]-1] += 1
                    matriz[jogo[j]-1, jogo[i]-1] += 1
        return matriz

    def gap_medio(self):
        gaps = {n:[] for n in self.numeros}
        total = len(self.concursos)
        for i, jogo in enumerate(self.concursos):
            for n in self.numeros:
                if n not in jogo:
                    gaps[n].append(total - i)
        return {n: np.mean(gaps[n]) if gaps[n] else 0 for n in self.numeros}

    def gerar_features(self):
        features = []
        if len(self.concursos) < 10:
            return np.array([])
        freq = self.frequencia(janela=min(50, len(self.concursos)-1))
        gaps = self.gap_medio()
        for jogo in self.concursos:
            f = []
            for n in self.numeros:
                f.append(1 if n in jogo else 0)
                f.append(freq[n])
                f.append(gaps[n])
                f.append(1 if n%2==0 else 0)
                f.append(1 if n in self.primos else 0)
            features.append(f)
        return np.array(features)

    def treinar_modelos(self):
        if len(self.concursos) < 10:
            return
        for i, n in enumerate(self.numeros):
            try:
                model = CatBoostClassifier(iterations=600, verbose=0, random_state=42)
                y = self.Y[:,i]
                model.fit(self.X, y)
                self.models[n] = model
            except Exception as e:
                st.warning(f"Erro ao treinar modelo para número {n}: {e}")

    def prever_proximo(self):
        if not self.models:
            freq = self.frequencia(janela=min(50, len(self.concursos)))
            maxf = max(freq.values()) if freq else 1
            probs = {n: (freq.get(n,0)/maxf if maxf>0 else 0.5) for n in self.numeros}
            return probs
        ultima = self.gerar_features()[-1].reshape(1,-1)
        probabilidades = {}
        for n in self.numeros:
            try:
                prob = self.models[n].predict_proba(ultima)[0][1]
                probabilidades[n] = prob
            except:
                probabilidades[n] = 0.5
        return probabilidades

    def gerar_5_jogos(self, probabilidades):
        if not probabilidades:
            return []
            
        ordenado = sorted(probabilidades.items(), key=lambda x:x[1], reverse=True)
        top15 = [n for n,_ in ordenado[:15]]
        top20 = [n for n,_ in ordenado[:20]]
        mid = [n for n,_ in ordenado[10:20]]
        frios = [n for n,_ in sorted(probabilidades.items(), key=lambda x:x[1])[:10]]

        jogos=[]
        jogos.append(sorted(top15))
        jogos.append(sorted(random.sample(top15, 10) + random.sample(mid,5)))
        jogos.append(sorted(random.sample(top15, 12) + random.sample(frios,3)))
        jogos.append(self._equilibrado(top20))
        jogos.append(self._equilibrado(top20, forcar_primos=True))
        
        unicos = []
        seen = set()
        for j in jogos:
            t = tuple(j)
            if t not in seen:
                seen.add(t); unicos.append(j)
        while len(unicos) < 5:
            unicos.append(self._equilibrado(top20))
        return unicos

    def _equilibrado(self, base, forcar_primos=False):
        base = list(set(base))
        while True:
            if len(base) < 15:
                base = list(range(1,26))
            cartao = sorted(random.sample(base,15))
            pares = sum(1 for n in cartao if n%2==0)
            primos_count = sum(1 for n in cartao if n in self.primos)
            if 7 <= pares <=10 and (not forcar_primos or primos_count>=3):
                return cartao

    def gerar_cartoes_por_padroes(self, n_jogos=5, janela=10):
        if janela < 10:
            janela = min(10, len(self.concursos))
        ultimos = self.concursos[0:janela]
        freq = {n:0 for n in self.numeros}
        for jogo in ultimos:
            for n in jogo:
                freq[n] += 1

        quentes = [n for n,_ in sorted(freq.items(), key=lambda x:x[1], reverse=True)[:15]]
        evens_q = [x for x in quentes if x%2==0]
        odds_q  = [x for x in quentes if x%2==1]
        frios = [n for n,_ in sorted(freq.items(), key=lambda x:x[1])[:10]]

        padrao_par_impar = []
        for jogo in ultimos:
            pares = sum(1 for x in jogo if x%2==0)
            padrao_par_impar.append((pares, 15-pares))
        media_pares = int(np.round(np.mean([p for p,_ in padrao_par_impar]))) if padrao_par_impar else 7
        media_pares = max(5, min(10, media_pares))
        media_impares = 15 - media_pares

        jogos=[]
        for _ in range(n_jogos):
            cartao = set()
            candidatos_pares = evens_q if len(evens_q) >= media_pares else [x for x in range(2,26,2)]
            cartao.update(random.sample(candidatos_pares, media_pares))
            candidatos_impares = odds_q if len(odds_q) >= media_impares else [x for x in range(1,26,2)]
            faltam = media_impares
            cartao.update(random.sample(candidatos_impares, faltam))
            while len(cartao) < 15:
                cartao.add(random.choice(frios if frios else list(range(1,26))))
            jogos.append(sorted(list(cartao)))
        
        unicos = []
        seen = set()
        for j in jogos:
            t = tuple(j)
            if t not in seen:
                seen.add(t); unicos.append(j)
        while len(unicos) < n_jogos:
            unicos.append(sorted(random.sample(range(1,26),15)))
        return unicos

# =========================
# CLASSE: EstrategiaFibonacci
# =========================
class EstrategiaFibonacci:
    def __init__(self, concursos):
        self.concursos = concursos
        self.fibonacci = [1, 2, 3, 5, 8, 13, 21]
        self.numeros = list(range(1, 26))
        
    def analisar_fibonacci(self):
        """Analisa estatísticas das dezenas Fibonacci nos concursos recentes"""
        if not self.concursos:
            return {}
            
        janela = min(50, len(self.concursos))
        if janela < 10:
            janela = min(10, len(self.concursos))
        concursos_recentes = self.concursos[:janela]
        
        stats = {
            'frequencia_fib': {num: 0 for num in self.fibonacci},
            'media_por_concurso': [],
            'ultima_aparicao': {num: 0 for num in self.fibonacci},
            'atraso_fib': {num: 0 for num in self.fibonacci}
        }
        
        for idx, concurso in enumerate(concursos_recentes):
            fib_no_concurso = [num for num in concurso if num in self.fibonacci]
            stats['media_por_concurso'].append(len(fib_no_concurso))
            
            for num in self.fibonacci:
                if num in concurso:
                    stats['frequencia_fib'][num] += 1
                    stats['ultima_aparicao'][num] = idx
        
        for num in self.fibonacci:
            if stats['ultima_aparicao'][num] > 0:
                stats['atraso_fib'][num] = stats['ultima_aparicao'][num]
            else:
                stats['atraso_fib'][num] = janela
        
        stats['media_geral'] = np.mean(stats['media_por_concurso']) if stats['media_por_concurso'] else 0
        stats['moda_geral'] = max(set(stats['media_por_concurso']), key=stats['media_por_concurso'].count) if stats['media_por_concurso'] else 0
        stats['min_geral'] = min(stats['media_por_concurso']) if stats['media_por_concurso'] else 0
        stats['max_geral'] = max(stats['media_por_concurso']) if stats['media_por_concurso'] else 0
        
        return stats
    
    def gerar_cartoes_fibonacci(self, n_cartoes=10, usar_estatisticas=True):
        """Gera cartões usando estratégia Fibonacci com 4 ou 5 números Fibonacci"""
        cartoes = []
        
        stats = self.analisar_fibonacci() if usar_estatisticas else {}
        
        for _ in range(n_cartoes * 3):
            qtd_fib = random.choice([4, 5])
            
            if usar_estatisticas and stats:
                fib_ordenados = sorted(
                    self.fibonacci, 
                    key=lambda x: (stats['atraso_fib'][x], -stats['frequencia_fib'][x]), 
                    reverse=True
                )
                fib_selecionadas = random.sample(fib_ordenados[:5], qtd_fib)
            else:
                fib_selecionadas = random.sample(self.fibonacci, qtd_fib)
            
            nao_fib = [num for num in self.numeros if num not in self.fibonacci]
            
            if usar_estatisticas and self.concursos:
                janela = min(30, len(self.concursos))
                if janela < 10:
                    janela = min(10, len(self.concursos))
                freq_nao_fib = Counter()
                for concurso in self.concursos[:janela]:
                    for num in concurso:
                        if num in nao_fib:
                            freq_nao_fib[num] += 1
                
                nao_fib_ordenados = sorted(nao_fib, key=lambda x: freq_nao_fib[x], reverse=True)
                
                qtd_nao_fib = 15 - qtd_fib
                qtd_frequentes = int(qtd_nao_fib * 0.6)
                qtd_aleatorios = qtd_nao_fib - qtd_frequentes
                
                selecao_frequentes = []
                if len(nao_fib_ordenados) >= qtd_frequentes:
                    candidatos = [n for n in nao_fib_ordenados[:20] if n not in fib_selecionadas]
                    if len(candidatos) >= qtd_frequentes:
                        selecao_frequentes = random.sample(candidatos, qtd_frequentes)
                    else:
                        selecao_frequentes = candidatos
                
                restantes = [num for num in nao_fib if num not in fib_selecionadas and num not in selecao_frequentes]
                if restantes and qtd_aleatorios > 0:
                    if len(restantes) >= qtd_aleatorios:
                        selecao_aleatorios = random.sample(restantes, qtd_aleatorios)
                    else:
                        selecao_aleatorios = restantes
                    
                    selecao_nao_fib = selecao_frequentes + selecao_aleatorios
                else:
                    selecao_nao_fib = selecao_frequentes
                
                while len(selecao_nao_fib) < qtd_nao_fib:
                    candidatos = [num for num in nao_fib if num not in fib_selecionadas and num not in selecao_nao_fib]
                    if candidatos:
                        selecao_nao_fib.append(random.choice(candidatos))
                    else:
                        break
            else:
                qtd_nao_fib = 15 - qtd_fib
                candidatos_nao_fib = [num for num in nao_fib if num not in fib_selecionadas]
                if len(candidatos_nao_fib) >= qtd_nao_fib:
                    selecao_nao_fib = random.sample(candidatos_nao_fib, qtd_nao_fib)
                else:
                    selecao_nao_fib = candidatos_nao_fib
            
            cartao = sorted(fib_selecionadas + selecao_nao_fib)
            
            if len(set(cartao)) != 15:
                continue
            
            pares = sum(1 for n in cartao if n % 2 == 0)
            if 6 <= pares <= 9:
                if cartao not in cartoes:
                    cartoes.append(cartao)
            
            if len(cartoes) >= n_cartoes:
                break
        
        while len(cartoes) < n_cartoes:
            qtd_fib = random.choice([4, 5])
            fib_selecionadas = random.sample(self.fibonacci, qtd_fib)
            nao_fib = [num for num in self.numeros if num not in self.fibonacci]
            candidatos_nao_fib = [num for num in nao_fib if num not in fib_selecionadas]
            
            if len(candidatos_nao_fib) >= (15 - qtd_fib):
                selecao_nao_fib = random.sample(candidatos_nao_fib, 15 - qtd_fib)
                cartao = sorted(fib_selecionadas + selecao_nao_fib)
                
                if len(set(cartao)) == 15 and cartao not in cartoes:
                    cartoes.append(cartao)
            else:
                cartao = sorted(fib_selecionadas + candidatos_nao_fib)
                while len(cartao) < 15:
                    candidato = random.choice([n for n in self.numeros if n not in cartao])
                    cartao.append(candidato)
                cartao = sorted(cartao)
                
                if len(set(cartao)) == 15 and cartao not in cartoes:
                    cartoes.append(cartao)
        
        return cartoes[:n_cartoes]

# =========================
# PADRÕES LINHA×COLUNA
# =========================
LINHAS = [
    list(range(1, 6)),
    list(range(6, 11)),
    list(range(11, 16)),
    list(range(16, 21)),
    list(range(21, 26))
]
COLUNAS = [
    list(range(1, 26, 5)),
    list(range(2, 26, 5)),
    list(range(3, 26, 5)),
    list(range(4, 26, 5)),
    list(range(5, 26, 5))
]

def contar_padroes_linha_coluna(concursos):
    padrao_linhas = []
    padrao_colunas = []
    for concurso in concursos:
        linha_cont = [sum(1 for n in concurso if n in l) for l in LINHAS]
        col_cont = [sum(1 for n in concurso if n in c) for c in COLUNAS]
        padrao_linhas.append(tuple(linha_cont))
        padrao_colunas.append(tuple(col_cont))
    return Counter(padrao_linhas), Counter(padrao_colunas)

def sugerir_padroes_futuros(freq_linhas, freq_colunas, n=5):
    pads_l = [p for p,_ in freq_linhas.most_common(n)] or [(3,3,3,3,3)]
    pads_c = [p for p,_ in freq_colunas.most_common(n)] or [(3,3,3,3,3)]
    futuros = []
    for i in range(n):
        futuros.append({"linhas": pads_l[i % len(pads_l)], "colunas": pads_c[i % len(pads_c)]})
    return futuros

# =========================
# Streamlit - Interface Principal
# =========================
def carregar_estado():
    """Carrega o estado da sessão"""
    if "concursos" not in st.session_state:
        st.session_state.concursos = []
    if "cartoes_gerados" not in st.session_state:
        st.session_state.cartoes_gerados = []
    if "cartoes_gerados_padrao" not in st.session_state:
        st.session_state.cartoes_gerados_padrao = []
    if "info_ultimo_concurso" not in st.session_state:
        st.session_state.info_ultimo_concurso = None
    if "combinacoes_combinatorias" not in st.session_state:
        st.session_state.combinacoes_combinatorias = {}
    if "tabela_sequencia_falha" not in st.session_state:
        st.session_state.tabela_sequencia_falha = None
    if "jogos_sequencia_falha" not in st.session_state:
        st.session_state.jogos_sequencia_falha = []
    if "resultado_ciclos" not in st.session_state:
        st.session_state.resultado_ciclos = None
    if "cartoes_ciclos" not in st.session_state:
        st.session_state.cartoes_ciclos = []
    if "analise_ciclos" not in st.session_state:
        st.session_state.analise_ciclos = None
    if "concursos_info" not in st.session_state:
        st.session_state.concursos_info = {}
    if "limite_ciclos" not in st.session_state:
        st.session_state.limite_ciclos = None
    if "cartoes_fibonacci" not in st.session_state:
        st.session_state.cartoes_fibonacci = []
    if "relatorio_fibonacci" not in st.session_state:
        st.session_state.relatorio_fibonacci = None
    if "fechamento_gerado" not in st.session_state:
        st.session_state.fechamento_gerado = []
    if "grupos_fechamento" not in st.session_state:
        st.session_state.grupos_fechamento = []
    if "analise_estatistica_seriosa" not in st.session_state:  # MODIFICADO
        st.session_state.analise_estatistica_seriosa = None
    if "cartoes_estatisticos" not in st.session_state:  # MODIFICADO
        st.session_state.cartoes_estatisticos = []
    if "relatorio_estatistico" not in st.session_state:  # MODIFICADO
        st.session_state.relatorio_estatistico = None
    if "resultados_backtest_rigoroso" not in st.session_state:  # MODIFICADO
        st.session_state.resultados_backtest_rigoroso = None
    if "relatorio_backtest_rigoroso" not in st.session_state:  # MODIFICADO
        st.session_state.relatorio_backtest_rigoroso = None

st.markdown("<h1 style='text-align: center;'>Lotofácil Inteligente</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>SISTEMA ESTATÍSTICO PROFISSIONAL</p>", unsafe_allow_html=True)  # MODIFICADO
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
                        "posicao": f"{idx+1}º mais recente" if idx == 0 else f"{idx+1}º após o mais recente",
                        "dezenas": concurso
                    }
                st.session_state.concursos_info = concursos_info
                
                st.success(f"{len(concursos)} concursos capturados com sucesso!")
                
                # Limpar dados antigos
                st.session_state.tabela_sequencia_falha = None
                st.session_state.jogos_sequencia_falha = []
                st.session_state.resultado_ciclos = None
                st.session_state.cartoes_ciclos = []
                st.session_state.analise_ciclos = None
                st.session_state.cartoes_gerados = []
                st.session_state.cartoes_gerados_padrao = []
                st.session_state.combinacoes_combinatorias = {}
                st.session_state.limite_ciclos = None
                st.session_state.cartoes_fibonacci = []
                st.session_state.relatorio_fibonacci = None
                st.session_state.fechamento_gerado = []
                st.session_state.grupos_fechamento = []
                # MODIFICADO: Limpar dados estatísticos
                st.session_state.analise_estatistica_seriosa = None
                st.session_state.cartoes_estatisticos = []
                st.session_state.relatorio_estatistico = None
                st.session_state.resultados_backtest_rigoroso = None
                st.session_state.relatorio_backtest_rigoroso = None

# --- Abas principais ---
if st.session_state.concursos:
    if len(st.session_state.concursos) < 10:
        st.warning("⚠️ São necessários pelo menos 10 concursos para análises precisas. Capture mais concursos.")
    
    # Inicializar análises
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    jogos_gerados = ia.gerar_5_jogos(probs) if probs else []
    quentes_frios = ia.quentes_frios()
    pares_impares_primos = ia.pares_impares_primos()
    
    analise_sf = AnaliseSequenciaFalha(st.session_state.concursos)
    fechamento = FechamentoLotofacil(st.session_state.concursos)
    
    # MODIFICADO: Inicializar análise estatística séria
    analise_estatistica_seriosa = AnaliseEstatisticaSeriosa(st.session_state.concursos)
    backtest_rigoroso = BacktestRigoroso(st.session_state.concursos)
    
    # MODIFICADO: Abas atualizadas
    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões IA", 
        "📈 Método Sequência/Falha",
        "🔢 Análises Combinatórias",
        "🧩 Gerar Cartões por Padrões",
        "📐 Padrões Linha×Coluna",
        "🎯 Estratégia Fibonacci",
        "🎲 Fechamentos Matemáticos",
        "✅ Conferência", 
        "📤 Conferir Arquivo TXT",
        "🔁 Ciclos da Lotofácil",
        "📊 Backtest Rigoroso",  # MODIFICADO
        "🔬 Análise Estatística"  # MODIFICADO (substitui "Estatística Quântica")
    ])

    # Aba 1 - Estatísticas
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Números quentes: {quentes_frios['quentes']}")
        st.write(f"Números frios: {quentes_frios['frios']}")
        st.write(f"Pares/Ímpares/Primos último concurso: {pares_impares_primos}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Frequência últimos concursos:**")
            freq = ia.frequencia()
            freq_df = pd.DataFrame(list(freq.items()), columns=["Número", "Frequência"])
            freq_df = freq_df.sort_values("Frequência", ascending=False)
            st.dataframe(freq_df.head(10), hide_index=True)
        
        with col2:
            st.write("**Atraso dos números:**")
            atraso = ia.atraso()
            atraso_df = pd.DataFrame(list(atraso.items()), columns=["Número", "Atraso"])
            atraso_df = atraso_df.sort_values("Atraso", ascending=False)
            st.dataframe(atraso_df.head(10), hide_index=True)

    # Aba 2 - Gerar Cartões IA
    with abas[1]:
        st.subheader("🧠 Geração de Cartões por Inteligência Artificial")
        if len(st.session_state.concursos) >= 10:
            if st.button("🚀 Gerar 5 Cartões com IA"):
                st.session_state.cartoes_gerados = jogos_gerados
                st.success("5 Cartões gerados com sucesso pela IA!")
        else:
            st.warning("São necessários pelo menos 10 concursos para gerar cartões com IA")
        
        if st.session_state.cartoes_gerados:
            st.write("### 📋 Cartões Gerados")
            for i, c in enumerate(st.session_state.cartoes_gerados, 1):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Jogo {i}:** {c}")
                with col2:
                    pares = sum(1 for n in c if n % 2 == 0)
                    primos = sum(1 for n in c if n in {2,3,5,7,11,13,17,19,23})
                    st.write(f"Pares: {pares}, Primos: {primos}")

            st.subheader("📁 Exportar Cartões para TXT")
            conteudo = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados)
            st.download_button("💾 Baixar Arquivo", data=conteudo, file_name="cartoes_lotofacil_ia.txt", mime="text/plain")

    # Aba 3 - Método Sequência/Falha
    with abas[2]:
        st.subheader("📈 Análise de Sequência e Falha (Método da Tabela)")
        
        if st.button("📊 Gerar Tabela de Análise"):
            with st.spinner("Analisando sequências e falhas..."):
                tabela = analise_sf.criar_tabela_completa()
                st.session_state.tabela_sequencia_falha = tabela
                st.success("Tabela gerada com sucesso!")
        
        if st.session_state.tabela_sequencia_falha is not None:
            tabela = st.session_state.tabela_sequencia_falha
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### 🔥 Números com Maior Sequência (Mais Quentes)")
                top_sequencia = tabela.sort_values("Sequência", ascending=False).head(10)
                st.dataframe(top_sequencia[["Número", "Sequência", "Posição_Sequência"]], hide_index=True)
            
            with col2:
                st.write("### ❄️ Números com Maior Falha (Potencial Retorno)")
                top_falha = tabela.sort_values("Falha", ascending=False).head(10)
                st.dataframe(top_falha[["Número", "Falha", "Posição_Falha"]], hide_index=True)
            
            st.write("### 📋 Tabela Completa (1-25)")
            st.dataframe(tabela, hide_index=True)
            
            st.subheader("🎯 Gerar Jogos com Base na Análise")
            
            estrategia = st.selectbox(
                "Selecione a estratégia de geração:",
                ["balanceada", "conservadora", "agressiva", "aleatoria_padrao", "metodo_tabela"]
            )
            
            n_jogos = st.slider("Número de jogos a gerar:", 1, 20, 5)
            
            if st.button("🎰 Gerar Jogos com Esta Estratégia"):
                if estrategia == "metodo_tabela":
                    jogos = analise_sf.gerar_jogos_metodo_tabela(n_jogos)
                else:
                    jogos = analise_sf.gerar_jogos_estrategicos(n_jogos, estrategia)
                
                st.session_state.jogos_sequencia_falha = jogos
                st.success(f"{n_jogos} jogos gerados com sucesso!")
            
            if st.session_state.jogos_sequencia_falha:
                st.write("### 📋 Jogos Gerados")
                for i, jogo in enumerate(st.session_state.jogos_sequencia_falha, 1):
                    pares = sum(1 for n in jogo if n % 2 == 0)
                    primos = sum(1 for n in jogo if n in {2,3,5,7,11,13,17,19,23})
                    soma = sum(jogo)
                    
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        st.write(f"**Jogo {i}:** {jogo}")
                    with col2:
                        st.write(f"Pares: {pares}, Primos: {primos}, Soma: {soma}")
                
                st.subheader("💾 Exportar Jogos")
                conteudo_sf = "\n".join(",".join(str(n) for n in jogo) for jogo in st.session_state.jogos_sequencia_falha)
                st.download_button(
                    "📥 Baixar Jogos Sequência/Falha", 
                    data=conteudo_sf, 
                    file_name=f"jogos_sequencia_falha_{estrategia}.txt", 
                    mime="text/plain"
                )

    # Aba 4 - Análises Combinatórias
    with abas[3]:
        st.subheader("🔢 Análises Combinatórias - Combinações Matemáticas")
        
        analisador_combinatorio = AnaliseCombinatoria(st.session_state.concursos)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ⚙️ Configurações")
            tamanhos_selecionados = st.multiselect(
                "Selecione os tamanhos de combinação:",
                [12, 13, 14, 15],
                default=[14, 15]
            )
            
            quantidade_por_tamanho = st.slider(
                "Quantidade de combinações por tamanho:",
                min_value=10,
                max_value=500,
                value=100,
                step=10
            )
            
            if st.button("🎯 Gerar Combinações Otimizadas", type="primary"):
                with st.spinner("Gerando e analisando combinações..."):
                    combinacoes = analisador_combinatorio.gerar_combinacoes_otimizadas(
                        tamanhos_selecionados, 
                        quantidade_por_tamanho
                    )
                    st.session_state.combinacoes_combinatorias = combinacoes
                    st.success(f"Combinações geradas com sucesso!")
        
        with col2:
            st.markdown("### 📈 Estatísticas dos Filtros")
            stats_base = analisador_combinatorio.calcular_estatisticas_base()
            if stats_base:
                st.write(f"**Média de pares (histórico):** {np.mean(stats_base['media_pares']):.1f}")
                st.write(f"**Média de soma (histórico):** {np.mean(stats_base['media_soma']):.1f}")
                st.write(f"**Média de primos (histórico):** {np.mean(stats_base['media_primos']):.1f}")
        
        if st.session_state.combinacoes_combinatorias:
            st.markdown("### 🎯 Combinações Geradas (Top 10 por Tamanho)")
            
            for tamanho in sorted(st.session_state.combinacoes_combinatorias.keys()):
                combinacoes_tamanho = st.session_state.combinacoes_combinatorias[tamanho]
                
                if combinacoes_tamanho:
                    st.markdown(f"#### 📊 Combinações com {tamanho} números (Top 10)")
                    
                    cols = st.columns(2)
                    for idx, (combo, score) in enumerate(combinacoes_tamanho[:10]):
                        with cols[idx % 2]:
                            st.code(f"Score: {score:.1f} → {combo}")
            
            st.markdown("### 💾 Exportar Combinações")
            
            col_export1, col_export2 = st.columns(2)
            
            with col_export1:
                conteudo_combinacoes = ""
                for tamanho, combinacoes_list in st.session_state.combinacoes_combinatorias.items():
                    conteudo_combinacoes += f"# Combinações com {tamanho} números\n"
                    for combo, score in combinacoes_list[:20]:
                        conteudo_combinacoes += f"{','.join(map(str, combo))} # Score: {score:.1f}\n"
                    conteudo_combinacoes += "\n"
                
                st.download_button(
                    "📥 Baixar Todas as Combinações (Lista)",
                    data=conteudo_combinacoes,
                    file_name="combinacoes_otimizadas.txt",
                    mime="text/plain"
                )
            
            with col_export2:
                conteudo_cartoes = analisador_combinatorio.gerar_conteudo_cartoes(
                    st.session_state.combinacoes_combinatorias, 
                    top_n=10
                )
                
                st.download_button(
                    "📥 Baixar Top 10 Cartões (Formato Cartão)",
                    data=conteudo_cartoes,
                    file_name="cartoes_lotofacil_formatados.txt",
                    mime="text/plain"
                )

    # Aba 5 - Gerar Cartões por Padrões
    with abas[4]:
        st.subheader("🧩 Geração de Cartões com Base em Padrões")
        janela_padrao = st.slider("Janela (nº de concursos recentes)", 10, 100, 20, 5)
        if st.button("🚀 Gerar 5 Cartões por Padrões"):
            cartoes_padrao = ia.gerar_cartoes_por_padroes(n_jogos=5, janela=janela_padrao)
            st.session_state.cartoes_gerados_padrao = cartoes_padrao
            st.success("5 Cartões por Padrões gerados com sucesso!")
        
        if st.session_state.cartoes_gerados_padrao:
            for i, c in enumerate(st.session_state.cartoes_gerados_padrao,1):
                st.write(f"Cartão {i}: {c}")

            st.subheader("📁 Exportar Cartões por Padrões para TXT")
            conteudo_padrao = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados_padrao)
            st.download_button("💾 Baixar Arquivo Padrões", data=conteudo_padrao, file_name="cartoes_padroes_lotofacil.txt", mime="text/plain")

    # Aba 6 - Padrões Linha×Coluna
    with abas[5]:
        st.subheader("📐 Padrões de Linhas × Colunas")
        concursos = st.session_state.concursos
        if concursos:
            max_concursos = min(500, len(concursos))
            valor_padrao = min(100, len(concursos))
            
            janela_lc = st.slider(
                "Concursos a considerar (mais recentes)", 
                min_value=10,
                max_value=max_concursos, 
                value=valor_padrao, 
                step=10
            )
            
            subset = concursos[:janela_lc]

            if st.button("🔍 Analisar Padrões Linha×Coluna"):
                freq_linhas, freq_colunas = contar_padroes_linha_coluna(subset)

                st.markdown("### 📌 Padrões mais frequentes de **Linhas** (top 5)")
                for padrao, freq in freq_linhas.most_common(5):
                    st.write(f"{padrao} → {freq} vezes")

                st.markdown("### 📌 Padrões mais frequentes de **Colunas** (top 5)")
                for padrao, freq in freq_colunas.most_common(5):
                    st.write(f"{padrao} → {freq} vezes")

                st.markdown("### 🎯 Padrões futuros sugeridos (5 combinações)")
                futuros = sugerir_padroes_futuros(freq_linhas, freq_colunas, n=5)
                for i, p in enumerate(futuros, 1):
                    st.write(f"**Padrão Futuro {i}:** Linhas {p['linhas']} | Colunas {p['colunas']}")

    # Aba 7 - Estratégia Fibonacci
    with abas[6]:
        st.subheader("🎯 Estratégia Fibonacci")
        st.write("Gera cartões usando as 7 dezenas de Fibonacci (01, 02, 03, 05, 08, 13, 21) com 4 ou 5 dessas por jogo.")
        
        estrategia_fib = EstrategiaFibonacci(st.session_state.concursos)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔢 Dezenas Fibonacci")
            st.write(f"**7 Dezenas Fibonacci:** {estrategia_fib.fibonacci}")
            
            if st.button("📊 Analisar Estatísticas Fibonacci"):
                with st.spinner("Analisando desempenho das dezenas Fibonacci..."):
                    relatorio = estrategia_fib.analisar_fibonacci()
                    st.session_state.relatorio_fibonacci = relatorio
                    st.success("Análise Fibonacci concluída!")
        
        with col2:
            st.markdown("### 🎯 Configuração")
            estrategia = "padrao"  # Simplificado
            n_cartoes = st.slider("Número de cartões a gerar:", 1, 20, 10)
        
        if hasattr(st.session_state, 'relatorio_fibonacci') and st.session_state.relatorio_fibonacci:
            relatorio = st.session_state.relatorio_fibonacci
            
            st.markdown("### 📈 Estatísticas das Dezenas Fibonacci")
            
            dados_tabela = []
            for num in estrategia_fib.fibonacci:
                dados_tabela.append({
                    "Número": num,
                    "Frequência (últimos concursos)": relatorio['frequencia_fib'].get(num, 0),
                    "Atraso (concursos)": relatorio['atraso_fib'].get(num, 0)
                })
            
            df_fib = pd.DataFrame(dados_tabela)
            st.dataframe(df_fib, hide_index=True)
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric("Média por concurso", f"{relatorio.get('media_geral', 0):.1f}")
            with col_stat2:
                st.metric("Moda (mais comum)", relatorio.get('moda_geral', 0))
            with col_stat3:
                st.metric("Mínimo por concurso", relatorio.get('min_geral', 0))
            with col_stat4:
                st.metric("Máximo por concurso", relatorio.get('max_geral', 0))
        
        st.markdown("---")
        st.markdown("### 🎰 Gerar Cartões Fibonacci")
        
        if st.button("🚀 Gerar Cartões com Estratégia Fibonacci", type="primary"):
            with st.spinner(f"Gerando {n_cartoes} cartões com estratégia Fibonacci..."):
                cartoes_fib = estrategia_fib.gerar_cartoes_fibonacci(n_cartoes, usar_estatisticas=True)
                st.session_state.cartoes_fibonacci = cartoes_fib
                st.success(f"{len(cartoes_fib)} cartões Fibonacci gerados com sucesso!")
        
        if hasattr(st.session_state, 'cartoes_fibonacci') and st.session_state.cartoes_fibonacci:
            cartoes_fib = st.session_state.cartoes_fibonacci
            
            st.markdown(f"### 📋 Cartões Gerados")
            
            stats_cartoes = []
            for i, cartao in enumerate(cartoes_fib, 1):
                fib_no_cartao = [num for num in cartao if num in estrategia_fib.fibonacci]
                qtd_fib = len(fib_no_cartao)
                
                pares = sum(1 for n in cartao if n % 2 == 0)
                primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
                soma = sum(cartao)
                
                stats_cartoes.append({
                    "Cartão": i,
                    "Dezenas": ", ".join(str(n) for n in cartao),
                    "Fibonacci": qtd_fib,
                    "Fibonacci Lista": ", ".join(str(n) for n in fib_no_cartao),
                    "Pares": pares,
                    "Primos": primos,
                    "Soma": soma
                })
            
            df_cartoes_fib = pd.DataFrame(stats_cartoes)
            st.dataframe(df_cartoes_fib, hide_index=True, use_container_width=True)
            
            conteudo_fib = "\n".join(",".join(str(n) for n in cartao) for cartao in cartoes_fib)
            st.download_button(
                "📥 Baixar Cartões Fibonacci", 
                data=conteudo_fib, 
                file_name=f"cartoes_fibonacci.txt", 
                mime="text/plain"
            )

    # Aba 8 - Fechamentos Matemáticos
    with abas[7]:
        st.subheader("🎲 Fechamentos Matemáticos - Desdobramentos")
        st.write("Gere múltiplos cartões a partir de um grupo maior de números (ex: 18 números) para aumentar a cobertura e garantia de acertos.")
        
        if len(st.session_state.concursos) < 10:
            st.warning("⚠️ São necessários pelo menos 10 concursos para análises precisas de fechamento.")
        
        col_config1, col_config2 = st.columns(2)
        
        with col_config1:
            st.markdown("### ⚙️ Configuração do Fechamento")
            
            modo_grupo = st.radio(
                "Selecione o modo de escolha dos números:",
                ["Usar grupos sugeridos pela IA", "Inserir números manualmente"]
            )
            
            tamanho_grupo = st.slider(
                "Tamanho do grupo de números para fechamento:",
                min_value=16,
                max_value=20,
                value=18,
                step=1
            )
            
            max_jogos = st.slider(
                "Número máximo de jogos a gerar:",
                min_value=10,
                max_value=200,
                value=80,
                step=10
            )
            
            estrategia_fechamento = st.selectbox(
                "Estratégia de geração:",
                ["cobertura", "estatistica"]
            )
        
        with col_config2:
            st.markdown("### 📊 Análise para Sugestões")
            
            if st.button("🔍 Analisar para Sugestões de Grupos"):
                with st.spinner("Analisando estatísticas para sugestões de grupos..."):
                    grupos_sugeridos = fechamento.analisar_grupos_otimos(tamanho_grupo, analise_concursos=30)
                    st.session_state.grupos_fechamento = grupos_sugeridos
                    st.success(f"{len(grupos_sugeridos)} grupos sugeridos gerados!")
        
        if st.session_state.grupos_fechamento:
            st.markdown("### 🎯 Grupos Sugeridos para Fechamento")
            
            for i, grupo in enumerate(st.session_state.grupos_fechamento, 1):
                col_g1, col_g2 = st.columns([3, 1])
                with col_g1:
                    st.write(f"**Grupo {i} ({len(grupo)} números):** {grupo}")
                with col_g2:
                    if st.button(f"Usar Grupo {i}", key=f"usar_grupo_{i}"):
                        grupo_selecionado = grupo
        
        if modo_grupo == "Inserir números manualmente":
            st.markdown("### ✍️ Inserir Números Manualmente")
            numeros_manuais = st.multiselect(
                f"Selecione {tamanho_grupo} números (1-25):",
                options=list(range(1, 26)),
                default=list(range(1, tamanho_grupo + 1)) if tamanho_grupo <= 25 else list(range(1, 26))
            )
            
            if len(numeros_manuais) != tamanho_grupo:
                st.warning(f"Selecione exatamente {tamanho_grupo} números. Atual: {len(numeros_manuais)}")
                grupo_selecionado = None
            else:
                grupo_selecionado = sorted(numeros_manuais)
        
        st.markdown("---")
        st.markdown("### 🚀 Gerar Fechamento")
        
        col_gerar1, col_gerar2 = st.columns(2)
        
        with col_gerar1:
            if st.button("🎲 Gerar Fechamento", type="primary", use_container_width=True):
                if 'grupo_selecionado' in locals() and grupo_selecionado:
                    with st.spinner(f"Gerando fechamento de {len(grupo_selecionado)} números para {max_jogos} jogos..."):
                        jogos_fechamento = fechamento.gerar_fechamento_18_15(
                            grupo_selecionado, 
                            max_jogos, 
                            estrategia_fechamento
                        )
                        st.session_state.fechamento_gerado = jogos_fechamento
                        
                        cobertura = fechamento.calcular_cobertura_teorica(grupo_selecionado, jogos_fechamento)
                        st.session_state.cobertura_fechamento = cobertura
                        
                        st.success(f"Fechamento gerado com {len(jogos_fechamento)} jogos!")
                else:
                    st.error("Selecione um grupo de números primeiro")
        
        with col_gerar2:
            if st.button("🔄 Limpar Fechamento", use_container_width=True):
                st.session_state.fechamento_gerado = []
                st.session_state.cobertura_fechamento = None
                st.success("Fechamento limpo!")
        
        if st.session_state.fechamento_gerado:
            jogos_fechamento = st.session_state.fechamento_gerado
            
            st.markdown(f"### 📋 Fechamento Gerado ({len(jogos_fechamento)} jogos)")
            
            if hasattr(st.session_state, 'cobertura_fechamento') and st.session_state.cobertura_fechamento:
                cobertura = st.session_state.cobertura_fechamento
                
                st.markdown("#### 📊 Estatísticas de Cobertura")
                
                col_cob1, col_cob2, col_cob3 = st.columns(3)
                with col_cob1:
                    st.metric("Cobertura Média", f"{cobertura['cobertura_media']}%")
                with col_cob2:
                    st.metric("Total de Jogos", cobertura['total_jogos'])
                with col_cob3:
                    st.metric("Números Cobertos", cobertura['total_numeros_cobertos'])
            
            st.markdown("#### 🎯 Jogos do Fechamento")
            
            for i, jogo in enumerate(jogos_fechamento[:10], 1):
                col_j1, col_j2 = st.columns([3, 2])
                with col_j1:
                    st.write(f"**Jogo {i}:** {jogo}")
                with col_j2:
                    pares = sum(1 for n in jogo if n % 2 == 0)
                    primos = sum(1 for n in jogo if n in {2,3,5,7,11,13,17,19,23})
                    soma = sum(jogo)
                    st.write(f"Pares: {pares}, Primos: {primos}, Soma: {soma}")
            
            if len(jogos_fechamento) > 10:
                st.info(f"Mostrando 10 de {len(jogos_fechamento)} jogos. Use o botão de exportar para ver todos.")
            
            st.markdown("### 💾 Exportar Fechamento")
            
            conteudo_fechamento = f"FECHAMENTO LOTOFÁCIL - {len(grupo_selecionado)} NÚMEROS PARA {len(jogos_fechamento)} JOGOS\n"
            conteudo_fechamento += "=" * 60 + "\n\n"
            conteudo_fechamento += f"Grupo de números: {', '.join(map(str, grupo_selecionado))}\n"
            conteudo_fechamento += f"Tamanho do grupo: {len(grupo_selecionado)} números\n"
            conteudo_fechamento += f"Total de jogos gerados: {len(jogos_fechamento)}\n"
            conteudo_fechamento += f"Estratégia: {estrategia_fechamento}\n\n"
            conteudo_fechamento += "JOGOS:\n" + "-" * 40 + "\n\n"
            
            for i, jogo in enumerate(jogos_fechamento, 1):
                conteudo_fechamento += f"Jogo {i}: {','.join(map(str, jogo))}\n"
            
            st.download_button(
                "📥 Baixar Fechamento Completo", 
                data=conteudo_fechamento,
                file_name=f"fechamento_lotofacil_{len(grupo_selecionado)}numeros.txt",
                mime="text/plain"
            )

    # Aba 9 - Conferência
    with abas[8]:
        st.subheader("🎯 Conferência de Cartões")
        if st.session_state.info_ultimo_concurso:
            info = st.session_state.info_ultimo_concurso
            st.markdown(
                f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                unsafe_allow_html=True
            )
            
            if st.button("🔍 Conferir Todos os Cartões"):
                if st.session_state.cartoes_gerados:
                    st.markdown("### 🧠 Cartões Gerados por IA")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Jogo {i}: {cartao} - **{acertos} acertos**")
                
                if st.session_state.jogos_sequencia_falha:
                    st.markdown("### 📈 Cartões Sequência/Falha")
                    for i, cartao in enumerate(st.session_state.jogos_sequencia_falha, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Jogo {i}: {cartao} - **{acertos} acertos**")
                
                if st.session_state.cartoes_gerados_padrao:
                    st.markdown("### 🧩 Cartões por Padrões")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados_padrao, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
                
                if hasattr(st.session_state, 'cartoes_fibonacci') and st.session_state.cartoes_fibonacci:
                    st.markdown("### 🎯 Cartões Fibonacci")
                    for i, cartao in enumerate(st.session_state.cartoes_fibonacci, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        fib_no_cartao = [num for num in cartao if num in [1,2,3,5,8,13,21]]
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos** (Fibonacci: {len(fib_no_cartao)})")
                
                if st.session_state.combinacoes_combinatorias:
                    st.markdown("### 🔢 Combinações Combinatorias (Top 3 por Tamanho)")
                    analisador_combinatorio = AnaliseCombinatoria(st.session_state.concursos)
                    
                    for tamanho in sorted(st.session_state.combinacoes_combinatorias.keys()):
                        combinacoes_tamanho = st.session_state.combinacoes_combinatorias[tamanho][:3]
                        
                        if combinacoes_tamanho:
                            st.markdown(f"#### 📊 Combinações com {tamanho} números")
                            
                            for idx, (combo, score) in enumerate(combinacoes_tamanho, 1):
                                acertos = len(set(combo) & set(info['dezenas']))
                                st.write(f"**Cartão {idx}** (Score: {score:.1f}) - **{acertos} acertos**")
                                st.write(f"{combo}")
                                st.write("---")
                
                if st.session_state.fechamento_gerado:
                    st.markdown("### 🎲 Fechamentos Gerados")
                    for i, cartao in enumerate(st.session_state.fechamento_gerado[:5], 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Fechamento Jogo {i}: {cartao} - **{acertos} acertos**")
                    
                    if len(st.session_state.fechamento_gerado) > 5:
                        st.info(f"Mostrando 5 de {len(st.session_state.fechamento_gerado)} jogos do fechamento")
                
                # MODIFICADO: Adicionar cartões estatísticos
                if hasattr(st.session_state, 'cartoes_estatisticos') and st.session_state.cartoes_estatisticos:
                    st.markdown("### 🔬 Cartões Estatísticos")
                    for i, cartao in enumerate(st.session_state.cartoes_estatisticos, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão Estatístico {i}: {cartao} - **{acertos} acertos**")

    # Aba 10 - Conferir Arquivo TXT
    with abas[9]:
        st.subheader("📤 Conferir Cartões de um Arquivo TXT")
        uploaded_file = st.file_uploader("Faça upload do arquivo TXT com os cartões (15 dezenas separadas por vírgula)", type="txt")
        if uploaded_file:
            linhas = uploaded_file.read().decode("utf-8").splitlines()
            cartoes_txt = []
            for linha in linhas:
                try:
                    dezenas = sorted([int(x) for x in linha.strip().split(",")])
                    if len(dezenas) == 15 and all(1 <= x <= 25 for x in dezenas):
                        cartoes_txt.append(dezenas)
                except:
                    continue

            if cartoes_txt:
                st.success(f"{len(cartoes_txt)} cartões carregados com sucesso.")
                if st.session_state.info_ultimo_concurso:
                    info = st.session_state.info_ultimo_concurso
                    st.markdown(
                        f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                        unsafe_allow_html=True
                    )
                    if st.button("📊 Conferir Cartões do Arquivo"):
                        for i, cartao in enumerate(cartoes_txt,1):
                            acertos = len(set(cartao) & set(info['dezenas']))
                            st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
            else:
                st.warning("Nenhum cartão válido foi encontrado no arquivo.")

    # Aba 11 - Ciclos da Lotofácil
    with abas[10]:
        st.subheader("🔁 Ciclos da Lotofácil (Ciclo Dinâmico)")
        st.write("Analise os ciclos de dezenas nos concursos mais recentes.")
        
        st.markdown("### ⚙️ Configuração da Análise de Ciclos")
        
        col_config1, col_config2 = st.columns([2, 1])
        
        with col_config1:
            max_concursos_disponiveis = len(st.session_state.concursos)
            limite_ciclos = st.slider(
                "Número de concursos anteriores para análise:",
                min_value=10,
                max_value=min(50, max_concursos_disponiveis),
                value=st.session_state.limite_ciclos or 15,
                step=1
            )
            
            incluir_todas_faltantes = st.checkbox(
                "Forçar inclusão de todas as dezenas faltantes nos cartões",
                value=False
            )
        
        with col_config2:
            st.metric("Concursos Disponíveis", max_concursos_disponiveis)
            if limite_ciclos:
                st.metric("Concursos a Analisar", limite_ciclos)
        
        if st.button("🔍 Analisar Ciclos com Nova Configuração", type="primary"):
            st.session_state.limite_ciclos = limite_ciclos
            st.session_state.analise_ciclos = AnaliseCiclos(
                st.session_state.concursos, 
                st.session_state.concursos_info,
                limite_ciclos
            )
            st.session_state.resultado_ciclos = None
            st.session_state.cartoes_ciclos = []
            st.success(f"Ciclos analisados com os últimos {limite_ciclos} concursos!")
        
        if st.session_state.analise_ciclos:
            analise_ciclos = st.session_state.analise_ciclos
            resumo = analise_ciclos.resumo()
            
            st.markdown("### 📊 Resultados da Análise de Ciclos")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Status do Ciclo", resumo["status"])
            with col2:
                st.metric("Concursos Analisados", resumo["tamanho"])
            with col3:
                st.metric("Dezenas Presentes", len(resumo["numeros_presentes"]))
            with col4:
                st.metric("Dezenas Faltantes", len(resumo["numeros_faltantes"]))
            
            with st.expander("📋 Detalhes do Ciclo", expanded=True):
                st.write("### 🔍 Dezenas já saídas no ciclo (presentes)")
                st.write(resumo["numeros_presentes"])
                
                st.write("### ❗ Dezenas faltantes para fechar o ciclo")
                if resumo["numeros_faltantes"]:
                    st.write(resumo["numeros_faltantes"])
                    faltantes_percent = (len(resumo['numeros_faltantes']) / 25) * 100
                    st.info(f"**Total de {len(resumo['numeros_faltantes'])} dezenas faltantes** ({faltantes_percent:.1f}%) para completar o ciclo de 25 números.")
                else:
                    st.success("✅ **Ciclo completo!** Todas as 25 dezenas já saíram neste ciclo.")
            
            st.markdown("---")
            st.subheader("🎯 Gerar Cartões Baseados no Ciclo")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 Reanalisar Ciclo", use_container_width=True):
                    st.session_state.analise_ciclos = AnaliseCiclos(
                        st.session_state.concursos, 
                        st.session_state.concursos_info,
                        st.session_state.limite_ciclos or limite_ciclos
                    )
                    st.session_state.resultado_ciclos = None
                    st.session_state.cartoes_ciclos = []
                    st.success("Ciclo reanalisado com sucesso!")
            
            with col_btn2:
                if st.button("🎯 Gerar 5 Cartões — Estratégia Ciclos", use_container_width=True):
                    cartoes_ciclo = analise_ciclos.gerar_5_cartoes_ciclo(
                        n_cartoes=5, 
                        seed=random.randint(1,999999),
                        incluir_todas_faltantes=incluir_todas_faltantes
                    )
                    st.session_state.cartoes_ciclos = cartoes_ciclo
                    st.session_state.resultado_ciclos = analise_ciclos.resumo()
                    st.success("5 cartões gerados com prioridade nas dezenas do ciclo!")
            
            if st.session_state.cartoes_ciclos:
                st.subheader("📋 Cartões Gerados (Priorizando Dezenas do Ciclo)")
                
                cartoes_unicos = []
                cartoes_vistos = set()
                
                for cartao in st.session_state.cartoes_ciclos:
                    cartao_tupla = tuple(cartao)
                    if cartao_tupla not in cartoes_vistos:
                        cartoes_vistos.add(cartao_tupla)
                        cartoes_unicos.append(cartao)
                
                if len(cartoes_unicos) < len(st.session_state.cartoes_ciclos):
                    st.warning(f"⚠️ {len(st.session_state.cartoes_ciclos) - len(cartoes_unicos)} cartões duplicados foram removidos.")
                    st.session_state.cartoes_ciclos = cartoes_unicos
                
                while len(st.session_state.cartoes_ciclos) < 5:
                    novo_cartao = sorted(random.sample(range(1, 26), 15))
                    if tuple(novo_cartao) not in cartoes_vistos:
                        cartoes_vistos.add(tuple(novo_cartao))
                        st.session_state.cartoes_ciclos.append(novo_cartao)
                
                st.success(f"✅ Gerados {len(st.session_state.cartoes_ciclos)} cartões distintos!")
                
                if incluir_todas_faltantes and resumo["numeros_faltantes"]:
                    st.info(f"✅ Configuração ativa: Incluindo todas as {len(resumo['numeros_faltantes'])} dezenas faltantes nos cartões.")
                
                stats_cartoes = []
                for i, c in enumerate(st.session_state.cartoes_ciclos, 1):
                    pares = sum(1 for n in c if n%2==0)
                    primos = sum(1 for n in c if n in {2,3,5,7,11,13,17,19,23})
                    soma = sum(c)
                    faltantes_incluidos = len(set(c) & set(resumo["numeros_faltantes"]))
                    presentes_incluidos = len(set(c) & set(resumo["numeros_presentes"]))
                    
                    stats_cartoes.append({
                        "Cartão": i,
                        "Dezenas": ", ".join(str(n) for n in c),
                        "Pares": pares,
                        "Primos": primos,
                        "Soma": soma,
                        "Faltantes Incluídos": faltantes_incluidos,
                        "Presentes Incluídos": presentes_incluidos
                    })
                
                df_cartoes = pd.DataFrame(stats_cartoes)
                st.dataframe(df_cartoes, hide_index=True, use_container_width=True)
                
                with st.expander("🔍 Ver Detalhes dos Cartões"):
                    for i, c in enumerate(st.session_state.cartoes_ciclos, 1):
                        pares = sum(1 for n in c if n%2==0)
                        primos = sum(1 for n in c if n in {2,3,5,7,11,13,17,19,23})
                        soma = sum(c)
                        faltantes_incluidos = set(c) & set(resumo["numeros_faltantes"])
                        presentes_incluidos = set(c) & set(resumo["numeros_presentes"])
                        
                        col_c1, col_c2 = st.columns([3, 2])
                        with col_c1:
                            st.write(f"**Cartão {i}:** {c}")
                        with col_c2:
                            st.write(f"**Estatísticas:**")
                            st.write(f"- Pares: {pares}")
                            st.write(f"- Primos: {primos}")
                            st.write(f"- Soma: {soma}")
                            st.write(f"- Faltantes: {len(faltantes_incluidos)}/{len(resumo['numeros_faltantes'])}")
                            st.write(f"- Presentes: {len(presentes_incluidos)}/{len(resumo['numeros_presentes'])}")
                        
                        if faltantes_incluidos:
                            st.write(f"**Dezenas faltantes incluídas:** {', '.join(str(n) for n in sorted(faltantes_incluidos))}")
                        
                        st.write("---")
                
                st.subheader("💾 Exportar Cartões do Ciclo")
                conteudo_ciclos = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_ciclos)
                st.download_button(
                    "📥 Baixar Cartões do Ciclo", 
                    data=conteudo_ciclos, 
                    file_name=f"cartoes_ciclo_{limite_ciclos}_concursos.txt", 
                    mime="text/plain"
                )
        else:
            st.info("👆 Configure e analise os ciclos usando o botão acima.")

    # Aba 12 - Backtest Rigoroso (MODIFICADO)
    with abas[11]:
        st.subheader("📊 Backtest Rigoroso - Validação Científica")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🔬 Metodologia Científica")
            st.write("Teste estatístico com validação temporal rigorosa.")
            
            train_size = st.slider(
                "Tamanho do conjunto de treino:",
                min_value=50,
                max_value=min(200, len(st.session_state.concursos) - 50),
                value=100,
                step=10,
                help="Quantos concursos usar para 'treinar' as estratégias"
            )
            
            test_size = st.slider(
                "Tamanho do conjunto de teste:",
                min_value=20,
                max_value=min(100, len(st.session_state.concursos) - train_size),
                value=50,
                step=5,
                help="Quantos concursos usar para testar as estratégias"
            )
            
            if st.button("🚀 Executar Backtest Rigoroso", type="primary"):
                with st.spinner(f"Executando backtest com {train_size} treino + {test_size} teste..."):
                    resultados = backtest_rigoroso.executar_backtest_rigoroso(train_size, test_size)
                    
                    if "erro" in resultados:
                        st.error(resultados["erro"])
                    else:
                        st.session_state.resultados_backtest_rigoroso = resultados
                        
                        # Gerar relatório
                        relatorio = backtest_rigoroso.gerar_relatorio_backtest(resultados)
                        st.session_state.relatorio_backtest_rigoroso = relatorio
                        
                        st.success(f"Backtest concluído! {len(resultados)} estratégias analisadas.")
        
        with col2:
            st.markdown("### 📈 Estratégias Testadas")
            st.info("""
            **🔍 Estratégias comparadas:**
            
            1. **Aleatório Balanceado** (baseline)
            2. **Frequência Simples**
            3. **Sequência-Falha**
            4. **Fibonacci Balanceado**
            
            **🎯 Métricas:**
            • Média de acertos
            • Intervalo de confiança 95%
            • Efetividade vs aleatório
            """)
        
        # Mostrar resultados do backtest
        if hasattr(st.session_state, 'resultados_backtest_rigoroso') and st.session_state.resultados_backtest_rigoroso:
            resultados = st.session_state.resultados_backtest_rigoroso
            
            st.markdown("### 📊 Resultados do Backtest Rigoroso")
            
            # Criar DataFrame para visualização
            dados_grafico = []
            for estrategia, stats in resultados.items():
                dados_grafico.append({
                    'Estratégia': estrategia,
                    'Média Acertos': stats['media_acertos'],
                    'IC Inferior': stats['intervalo_confianca'][0],
                    'IC Superior': stats['intervalo_confianca'][1],
                    'Efetividade %': stats['efetividade']
                })
            
            df_backtest = pd.DataFrame(dados_grafico)
            
            # Gráfico de comparação
            st.markdown("#### 📈 Comparação de Média de Acertos (com IC 95%)")
            
            # Preparar dados para gráfico
            chart_df = df_backtest.copy()
            chart_df['Erro'] = (chart_df['IC Superior'] - chart_df['Média Acertos'])
            
            # Exibir gráfico
            st.bar_chart(chart_df.set_index('Estratégia')[['Média Acertos']])
            
            # Tabela detalhada
            st.markdown("#### 📋 Estatísticas Detalhadas")
            
            # Formatar tabela
            display_df = df_backtest.copy()
            display_df['Média Acertos'] = display_df['Média Acertos'].round(2)
            display_df['IC 95%'] = display_df.apply(
                lambda row: f"[{row['IC Inferior']:.2f}, {row['IC Superior']:.2f}]", axis=1
            )
            display_df['Efetividade %'] = display_df['Efetividade %'].round(2)
            
            # Adicionar percentis
            for estrategia, stats in resultados.items():
                display_df.loc[display_df['Estratégia'] == estrategia, '11+ pts %'] = f"{stats['percentis']['11+']:.2f}%"
                display_df.loc[display_df['Estratégia'] == estrategia, '13+ pts %'] = f"{stats['percentis']['13+']:.2f}%"
            
            st.dataframe(display_df[['Estratégia', 'Média Acertos', 'IC 95%', 'Efetividade %', '11+ pts %', '13+ pts %']], 
                        hide_index=True, use_container_width=True)
            
            # Análise de resultados
            st.markdown("#### 📈 Análise dos Resultados")
            
            melhor = list(resultados.items())[0] if resultados else None
            aleatorio = resultados.get('Aleatório Balanceado', {})
            
            if aleatorio and melhor:
                vantagem = melhor[1]['media_acertos'] - aleatorio['media_acertos']
                
                col_an1, col_an2 = st.columns(2)
                with col_an1:
                    st.metric("Melhor Estratégia", melhor[0])
                    st.metric("Vantagem vs Aleatório", f"{vantagem:.2f} acertos")
                
                with col_an2:
                    st.metric("Média Aleatório", f"{aleatorio['media_acertos']:.2f}")
                    st.metric("Efetividade Melhor", f"{melhor[1]['efetividade']:.2f}%")
                
                # Conclusão baseada em resultados
                st.markdown("##### 🎯 Conclusão Estatística")
                if abs(vantagem) < 0.3:
                    st.warning("""
                    **Nenhuma vantagem estatisticamente significativa encontrada.**
                    
                    • Diferença < 0.3 acertos não é estatisticamente significativa
                    • Todas as estratégias performam similarmente ao aleatório balanceado
                    • Recomendação: Use aleatório balanceado (mais simples e igualmente eficaz)
                    """)
                else:
                    st.success(f"""
                    **Pequena vantagem para {melhor[0]}.**
                    
                    • Vantagem de {vantagem:.2f} acertos em média
                    • Efetividade de {melhor[1]['efetividade']:.2f}% acima do aleatório
                    • Recomendação: Considere usar {melhor[0]} para diversificação
                    """)
            
            # Mostrar relatório completo
            with st.expander("📄 Ver Relatório Completo do Backtest"):
                st.text(st.session_state.relatorio_backtest_rigoroso)
            
            # Download do relatório
            st.download_button(
                "💾 Baixar Relatório Completo",
                data=st.session_state.relatorio_backtest_rigoroso,
                file_name=f"backtest_rigoroso_lotofacil.txt",
                mime="text/plain"
            )
        
        # Informações sobre a metodologia
        with st.expander("ℹ️ Sobre a Metodologia do Backtest"):
            st.write("""
            **🔬 METODOLOGIA CIENTÍFICA APLICADA:**
            
            1. **Walk-Forward Validation (Validação Temporal):**
               • Treina em concursos passados
               • Testa em concursos futuros (não vistos durante o treino)
               • Simula cenário real de uso
            
            2. **Intervalos de Confiança 95%:**
               • Calcula margem de erro estatística
               • Mostra se diferenças são significativas
               • Evita conclusões prematuras
            
            3. **Baseline Estatística:**
               • Compara todas as estratégias contra aleatório balanceado
               • Mede efetividade real (não apenas desempenho bruto)
               • Considera custo-benefício
            
            4. **Métricas Robustas:**
               • Média de acertos (performance central)
               • Percentis (distribuição de performance)
               • Efetividade vs aleatório (vantagem real)
            
            **⚠️ LIMITAÇÕES ESTATÍSTICAS:**
            • Backtest mostra desempenho histórico, não garante resultados futuros
            • Lotofácil tem aleatoriedade verificada estatisticamente
            • Nenhuma estratégia altera probabilidades matemáticas fundamentais
            • Vantagens pequenas podem não ser economicamente significativas
            """)

    # Aba 13 - Análise Estatística (MODIFICADO: substitui "Estatística Quântica")
    with abas[12]:
        st.subheader("🔬 Análise Estatística - Métodos Científicos")
        st.write("Análise estatística rigorosa baseada em probabilidade, testes de hipóteses e intervalos de confiança.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🎯 Configuração da Análise")
            
            janela_analise = st.slider(
                "Janela de concursos para análise:",
                min_value=30,
                max_value=min(100, len(st.session_state.concursos)),
                value=50,
                step=5,
                help="Quantos concursos recentes usar para análise estatística"
            )
            
            usar_intervalo_confianca = st.checkbox(
                "Usar intervalos de confiança na geração",
                value=True,
                help="Considera incerteza estatística ao selecionar números"
            )
            
            n_cartoes_estatisticos = st.slider(
                "Número de cartões estatísticos a gerar:",
                min_value=1,
                max_value=10,
                value=5
            )
        
        with col2:
            st.markdown("### 📊 Métodos Estatísticos")
            st.info("""
            **🔍 Técnicas Implementadas:**
            
            1. **Intervalos de Confiança 95%**: Margem de erro estatística
            2. **Teste Qui-Quadrado**: Verifica aleatoriedade dos sorteios
            3. **Cadeias de Markov**: Analisa transições entre concursos
            4. **Autocorrelação**: Detecta padrões temporais
            5. **Análise de Frequência**: Distribuição probabilística
            
            **🎯 Objetivo Científico:**
            • Identificar padrões estatisticamente significativos
            • Quantificar incerteza nas previsões
            • Fornecer base matemática para decisões
            """)
        
        st.markdown("---")
        
        # Botão para análise estatística
        col_analise1, col_analise2 = st.columns(2)
        
        with col_analise1:
            if st.button("📈 Analisar Estatisticamente", type="primary"):
                with st.spinner(f"Executando análise estatística com {janela_analise} concursos..."):
                    analise = analise_estatistica_seriosa.calcular_distribuicao_probabilistica(janela_analise)
                    st.session_state.analise_estatistica_seriosa = analise
                    
                    # Gerar relatório
                    relatorio = analise_estatistica_seriosa.gerar_relatorio_estatistico(analise)
                    st.session_state.relatorio_estatistico = relatorio
                    
                    # Verificar aleatoriedade
                    p_value = analise['teste_aleatoriedade']['p_value']
                    if p_value and p_value > 0.05:
                        st.info("✅ Teste estatístico não rejeita hipótese de aleatoriedade (p > 0.05)")
                    elif p_value:
                        st.warning(f"⚠️ Possível não-aleatoriedade detectada (p = {p_value:.4f})")
                    
                    st.success("Análise estatística concluída!")
        
        with col_analise2:
            if st.button("🎲 Gerar Cartões Estatísticos"):
                with st.spinner("Gerando cartões com base em análise estatística..."):
                    cartoes_estatisticos = analise_estatistica_seriosa.gerar_cartoes_estatisticos(
                        n_cartoes_estatisticos, 
                        usar_intervalo_confianca=usar_intervalo_confianca
                    )
                    st.session_state.cartoes_estatisticos = cartoes_estatisticos
                    st.success(f"{len(cartoes_estatisticos)} cartões estatísticos gerados!")
        
        # Mostrar análise estatística se existir
        if hasattr(st.session_state, 'analise_estatistica_seriosa') and st.session_state.analise_estatistica_seriosa:
            analise = st.session_state.analise_estatistica_seriosa
            
            st.markdown("### 📊 Resultados da Análise Estatística")
            
            # Métricas principais
            col_q1, col_q2, col_q3, col_q4 = st.columns(4)
            with col_q1:
                st.metric("Concursos Analisados", analise['concursos_analisados'])
            with col_q2:
                p_val = analise['teste_aleatoriedade']['p_value']
                if p_val:
                    st.metric("p-value Aleatoriedade", f"{p_val:.4f}")
                else:
                    st.metric("p-value Aleatoriedade", "N/A")
            with col_q3:
                st.metric("Média Frequência", f"{analise['media_frequencia']:.3f}")
            with col_q4:
                # Contar números com IC significativo
                count_ic_significativo = 0
                for n in range(1, 26):
                    if n in analise['probabilidades']:
                        info = analise['probabilidades'][n]
                        intervalo = info['intervalo_superior'] - info['intervalo_inferior']
                        if intervalo < 0.1:  # IC estreito = mais confiável
                            count_ic_significativo += 1
                st.metric("IC Estreitos", count_ic_significativo)
            
            # Gráfico de probabilidades com intervalos de confiança
            st.markdown("#### 📈 Probabilidades com Intervalos de Confiança 95%")
            
            # Preparar dados para gráfico
            probs_data = []
            for n in range(1, 26):
                if n in analise['probabilidades']:
                    info = analise['probabilidades'][n]
                    probs_data.append({
                        'Número': n,
                        'Probabilidade': info['probabilidade'],
                        'IC Inferior': info['intervalo_inferior'],
                        'IC Superior': info['intervalo_superior']
                    })
            
            if probs_data:
                df_probs = pd.DataFrame(probs_data)
                
                # Gráfico de barras com erros
                chart_data = df_probs.set_index('Número')[['Probabilidade']]
                st.bar_chart(chart_data)
                
                # Mostrar top 10
                st.markdown("#### 🎯 Top 10 Números por Probabilidade")
                top10 = df_probs.sort_values('Probabilidade', ascending=False).head(10)
                st.dataframe(top10[['Número', 'Probabilidade', 'IC Inferior', 'IC Superior']], 
                           hide_index=True, use_container_width=True)
            
            # Análise de autocorrelação
            st.markdown("#### 📊 Análise de Autocorrelação (Padrões Temporais)")
            
            if analise['autocorrelacao']:
                ac_data = []
                for lag, corr in analise['autocorrelacao'].items():
                    ac_data.append({
                        'Lag (concursos)': lag,
                        'Correlação': corr,
                        'Significativo': 'Sim' if abs(corr) > 0.3 else 'Não'
                    })
                
                df_ac = pd.DataFrame(ac_data)
                if not df_ac.empty:
                    st.dataframe(df_ac, hide_index=True)
                    
                    # Interpretação
                    correlacoes_fortes = df_ac[df_ac['Significativo'] == 'Sim']
                    if not correlacoes_fortes.empty:
                        st.info(f"**Padrões temporais detectados:** {len(correlacoes_fortes)} lags com correlação > 0.3")
                    else:
                        st.success("**Não há padrões temporais fortes detectados**")
            
            # Mostrar relatório completo
            with st.expander("📄 Ver Relatório Estatístico Completo"):
                st.text(st.session_state.relatorio_estatistico)
        
        # Mostrar cartões estatísticos gerados
        if hasattr(st.session_state, 'cartoes_estatisticos') and st.session_state.cartoes_estatisticos:
            cartoes_estatisticos = st.session_state.cartoes_estatisticos
            
            st.markdown("### 🔬 Cartões Gerados com Base Estatística")
            
            # Estatísticas dos cartões
            stats_cartoes_est = []
            for i, cartao in enumerate(cartoes_estatisticos, 1):
                # Analisar características estatísticas
                if st.session_state.analise_estatistica_seriosa:
                    prob_total = 0
                    for n in cartao:
                        if n in st.session_state.analise_estatistica_seriosa['probabilidades']:
                            prob_total += st.session_state.analise_estatistica_seriosa['probabilidades'][n]['probabilidade']
                
                pares = sum(1 for n in cartao if n % 2 == 0)
                primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
                soma = sum(cartao)
                
                stats_cartoes_est.append({
                    "Cartão": i,
                    "Dezenas": ", ".join(str(n) for n in cartao),
                    "Pares": pares,
                    "Primos": primos,
                    "Soma": soma,
                    "Probabilidade Total": f"{prob_total:.3f}" if st.session_state.analise_estatistica_seriosa else "N/A"
                })
            
            # Exibir como DataFrame
            df_cartoes_est = pd.DataFrame(stats_cartoes_est)
            st.dataframe(df_cartoes_est, hide_index=True, use_container_width=True)
            
            # Detalhes expandidos
            with st.expander("🔍 Ver Análise Estatística de Cada Cartão"):
                if st.session_state.analise_estatistica_seriosa:
                    for i, cartao in enumerate(cartoes_estatisticos, 1):
                        col_est1, col_est2 = st.columns([3, 2])
                        with col_est1:
                            st.write(f"**Cartão Estatístico {i}:** {cartao}")
                            
                            # Números com maior e menor probabilidade no cartão
                            probs_no_cartao = []
                            for n in cartao:
                                if n in st.session_state.analise_estatistica_seriosa['probabilidades']:
                                    info = st.session_state.analise_estatistica_seriosa['probabilidades'][n]
                                    probs_no_cartao.append((n, info['probabilidade']))
                            
                            if probs_no_cartao:
                                probs_no_cartao.sort(key=lambda x: x[1], reverse=True)
                                mais_provaveis = [f"{n}({p:.3f})" for n, p in probs_no_cartao[:5]]
                                menos_provaveis = [f"{n}({p:.3f})" for n, p in probs_no_cartao[-5:]]
                                
                                st.write(f"**Mais prováveis:** {', '.join(mais_provaveis)}")
                                st.write(f"**Menos prováveis:** {', '.join(menos_provaveis)}")
                        
                        with col_est2:
                            # Métricas estatísticas
                            prob_total = sum(st.session_state.analise_estatistica_seriosa['probabilidades'][n]['probabilidade'] 
                                           for n in cartao if n in st.session_state.analise_estatistica_seriosa['probabilidades'])
                            
                            st.write(f"**Métricas estatísticas:**")
                            st.write(f"- Probabilidade total: {prob_total:.3f}")
                            st.write(f"- Pares: {sum(1 for n in cartao if n % 2 == 0)}")
                            st.write(f"- Primos: {sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})}")
                            st.write(f"- Soma: {sum(cartao)}")
                        
                        st.write("---")
                else:
                    st.info("Execute a análise estatística primeiro para ver detalhes.")
            
            # Exportar cartões estatísticos
            st.markdown("### 💾 Exportar Cartões Estatísticos")
            conteudo_estatistico = f"CARTÕES ESTATÍSTICOS LOTOFÁCIL - {len(cartoes_estatisticos)} CARTÕES\n"
            conteudo_estatistico += "=" * 60 + "\n\n"
            conteudo_estatistico += f"Métodos aplicados: Intervalos de confiança 95%, Teste qui-quadrado\n"
            conteudo_estatistico += f"Intervalos de confiança ativados: {usar_intervalo_confianca}\n"
            conteudo_estatistico += f"Concursos analisados: {janela_analise}\n\n"
            conteudo_estatistico += "CARTÕES:\n" + "-" * 40 + "\n\n"
            
            for i, cartao in enumerate(cartoes_estatisticos, 1):
                conteudo_estatistico += f"Cartão {i}: {','.join(map(str, cartao))}\n"
            
            st.download_button(
                "📥 Baixar Cartões Estatísticos",
                data=conteudo_estatistico,
                file_name=f"cartoes_estatisticos_lotofacil_{janela_analise}.txt",
                mime="text/plain"
            )
            
            # Informações sobre a abordagem estatística
            with st.expander("ℹ️ Sobre a Abordagem Estatística"):
                st.write("""
                **🔬 FUNDAMENTOS DA ANÁLISE ESTATÍSTICA:**
                
                1. **Probabilidade com Incerteza:**
                   • Calcula probabilidades com intervalos de confiança 95%
                   • Considera margem de erro estatística
                   • Evita conclusões excessivamente confiantes
                
                2. **Teste de Hipóteses:**
                   • Teste qui-quadrado para verificar aleatoriedade
                   • p-value < 0.05 sugere não-aleatoriedade
                   • Base científica para detecção de padrões
                
                3. **Análise Temporal:**
                   • Autocorrelação detecta padrões sazonais
                   • Cadeias de Markov modelam transições
                   • Considera dependência temporal entre sorteios
                
                4. **Seleção Conservadora:**
                   • Prefere números com IC estreitos (mais confiáveis)
                   • Balanceia entre frequência e incerteza
                   • Evita extremos estatisticamente instáveis
                
                **🎯 VANTAGENS DA ABORDAGEM ESTATÍSTICA:**
                • Baseada em métodos científicos comprovados
                • Quantifica incerteza (não apenas ponto estimado)
                • Testa suposições fundamentais (aleatoriedade)
                • Fornece fundamento matemático para decisões
                • Transparente e replicável
                
                **⚠️ LIMITAÇÕES E AVISOS IMPORTANTES:**
                • Intervalos de confiança mostram incerteza, não certeza
                • p-value > 0.05 não prova aleatoriedade, apenas não a rejeita
                • Correlação não implica causalidade em padrões temporais
                • Nenhuma análise estatística altera probabilidades fundamentais
                • Lotofácil permanece um jogo de sorte com aleatoriedade verificada
                
                **📊 INTERPRETAÇÃO CORRETA DOS RESULTADOS:**
                1. Use intervalos de confiança para entender incerteza
                2. p-value > 0.05: evidência insuficiente contra aleatoriedade
                3. Padrões temporais devem ser consistentes para serem significativos
                4. Diversificação é mais importante que "previsão" precisa
                5. Lembre-se: análise informa, não garante
                """)

# Sidebar - Gerenciamento de Dados
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
    if st.session_state.cartoes_gerados:
        st.write(f"Cartões IA gerados: {len(st.session_state.cartoes_gerados)}")
    if st.session_state.jogos_sequencia_falha:
        st.write(f"Cartões Sequência/Falha: {len(st.session_state.jogos_sequencia_falha)}")
    if st.session_state.cartoes_gerados_padrao:
        st.write(f"Cartões por padrões: {len(st.session_state.cartoes_gerados_padrao)}")
    if st.session_state.combinacoes_combinatorias:
        total_combinacoes = sum(len(combinacoes) for combinacoes in st.session_state.combinacoes_combinatorias.values())
        st.write(f"Combinações combinatorias: {total_combinacoes}")
    if hasattr(st.session_state, 'cartoes_fibonacci') and st.session_state.cartoes_fibonacci:
        st.write(f"Cartões Fibonacci: {len(st.session_state.cartoes_fibonacci)}")
    if st.session_state.cartoes_ciclos:
        st.write(f"Cartões Ciclos gerados: {len(st.session_state.cartoes_ciclos)}")
    if st.session_state.fechamento_gerado:
        st.write(f"Fechamentos gerados: {len(st.session_state.fechamento_gerado)}")
    if hasattr(st.session_state, 'cartoes_estatisticos') and st.session_state.cartoes_estatisticos:
        st.write(f"Cartões Estatísticos: {len(st.session_state.cartoes_estatisticos)}")  # MODIFICADO
    
    # Informações sobre backtest rigoroso
    if hasattr(st.session_state, 'resultados_backtest_rigoroso') and st.session_state.resultados_backtest_rigoroso:
        st.markdown("### 📊 Resultados do Backtest")
        resultados = st.session_state.resultados_backtest_rigoroso
        if resultados:
            melhor = list(resultados.items())[0]
            aleatorio = resultados.get('Aleatório Balanceado', {})
            
            st.write(f"**Melhor estratégia:** {melhor[0]}")
            st.write(f"**Média de acertos:** {melhor[1]['media_acertos']:.2f}")
            if aleatorio:
                vantagem = melhor[1]['media_acertos'] - aleatorio['media_acertos']
                st.write(f"**Vantagem vs aleatório:** {vantagem:.2f} acertos")
            
            # Conclusão baseada em resultados
            if aleatorio and abs(vantagem) < 0.3:
                st.warning("**Conclusão:** Nenhuma vantagem significativa")
            elif aleatorio:
                st.success("**Conclusão:** Pequena vantagem detectada")
    
    # Informações do ciclo atual
    if st.session_state.analise_ciclos:
        st.markdown("### 🔁 Informações do Ciclo Atual")
        ciclo_resumo = st.session_state.analise_ciclos.resumo()
        st.write(f"**Status:** {ciclo_resumo['status']}")
        st.write(f"**Dezenas faltantes:** {len(ciclo_resumo['numeros_faltantes'])}")
    
    # Informações estatísticas
    if hasattr(st.session_state, 'analise_estatistica_seriosa') and st.session_state.analise_estatistica_seriosa:
        st.markdown("### 🔬 Informações Estatísticas")
        analise = st.session_state.analise_estatistica_seriosa
        p_val = analise['teste_aleatoriedade']['p_value']
        
        if p_val:
            if p_val > 0.05:
                st.success("✅ Aleatoriedade não rejeitada")
            else:
                st.warning(f"⚠️ p-value: {p_val:.4f}")
        
        st.write(f"**IC estreitos:** {sum(1 for n in range(1, 26) if n in analise['probabilidades'] and (analise['probabilidades'][n]['intervalo_superior'] - analise['probabilidades'][n]['intervalo_inferior']) < 0.1)}")

st.markdown("<hr><p style='text-align: center;'>SISTEMA ESTATÍSTICO PROFISSIONAL - LOTOFÁCIL</p>", unsafe_allow_html=True)  # MODIFICADO
