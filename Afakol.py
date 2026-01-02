
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
# NOVA CLASSE: Backtest Estratégias
# =========================
class BacktestEstrategias:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        
    def executar_backtest_completo(self, concursos_teste=50):
        """Executa backtest de todas as estratégias contra concursos passados"""
        if len(self.concursos) < concursos_teste + 10:
            return {"erro": f"Necessário pelo menos {concursos_teste + 10} concursos para backtest"}
        
        resultados = {}
        
        # Testar cada concurso do passado
        for i in range(concursos_teste):
            concurso_alvo = self.concursos[i]  # Concurso a ser "previsto"
            dados_treino = self.concursos[i+1:i+51]  # 50 concursos anteriores como treino
            
            if len(dados_treino) < 10:
                continue
            
            # Gerar previsões com cada estratégia
            estrategias = self._gerar_previsoes_estrategias(dados_treino)
            
            # Avaliar acertos
            for estrategia_nome, jogos in estrategias.items():
                if estrategia_nome not in resultados:
                    resultados[estrategia_nome] = {
                        'acertos_11': 0, 'acertos_12': 0, 'acertos_13': 0,
                        'acertos_14': 0, 'acertos_15': 0, 'total_jogos': 0
                    }
                
                for jogo in jogos[:5]:  # Avaliar apenas 5 jogos por estratégia
                    acertos = len(set(jogo) & set(concurso_alvo))
                    resultados[estrategia_nome]['total_jogos'] += 1
                    
                    if acertos == 15:
                        resultados[estrategia_nome]['acertos_15'] += 1
                    elif acertos == 14:
                        resultados[estrategia_nome]['acertos_14'] += 1
                    elif acertos == 13:
                        resultados[estrategia_nome]['acertos_13'] += 1
                    elif acertos == 12:
                        resultados[estrategia_nome]['acertos_12'] += 1
                    elif acertos == 11:
                        resultados[estrategia_nome]['acertos_11'] += 1
        
        # Calcular estatísticas finais
        return self._calcular_estatisticas_finais(resultados)
    
    def _gerar_previsoes_estrategias(self, dados_treino):
        """Gera jogos usando todas as estratégias disponíveis"""
        estrategias = {}
        
        # 1. Estratégia IA CatBoost
        try:
            ia = LotoFacilIA(dados_treino)
            probs = ia.prever_proximo()
            if probs:
                estrategias['IA_CatBoost'] = ia.gerar_5_jogos(probs)
        except:
            pass
        
        # 2. Estratégia Sequência/Falha Balanceada
        analise_sf = AnaliseSequenciaFalha(dados_treino)
        estrategias['Sequencia_Falha_Balanceada'] = analise_sf.gerar_jogos_estrategicos(5, "balanceada")
        
        # 3. Estratégia Fibonacci
        fib = EstrategiaFibonacci(dados_treino)
        estrategias['Fibonacci_Padrao'] = fib.gerar_cartoes_fibonacci(5, usar_estatisticas=True)
        
        # 4. Estratégia por Padrões
        ia_padroes = LotoFacilIA(dados_treino)
        estrategias['Padroes_Janela20'] = ia_padroes.gerar_cartoes_por_padroes(5, janela=20)
        
        # 5. Estratégia Híbrida (NOVA)
        estrategias['Hibrida_Otimizada'] = self._gerar_estrategia_hibrida(dados_treino)
        
        # 6. Aleatório (baseline)
        estrategias['Aleatorio_Balanceado'] = self._gerar_aleatorio_balanceado(5)
        
        return estrategias
    
    def _gerar_estrategia_hibrida(self, dados_treino):
        """NOVA ESTRATÉGIA HÍBRIDA OTIMIZADA"""
        jogos_hibridos = []
        
        # Analisar dados de treino
        analise_sf = AnaliseSequenciaFalha(dados_treino)
        fib = EstrategiaFibonacci(dados_treino)
        
        for _ in range(8):  # Gerar 8 tentativas para garantir 5 jogos bons
            jogo = set()
            
            # 1. 6 números da Sequência/Falha (mais quentes)
            tabela = analise_sf.criar_tabela_completa()
            top_sequencia = tabela.sort_values("Sequência", ascending=False).head(10)
            numeros_quentes = top_sequencia['Número'].tolist()
            jogo.update(random.sample(numeros_quentes, 6))
            
            # 2. 4 números Fibonacci (priorizando atraso)
            stats_fib = fib.analisar_fibonacci()
            if stats_fib and 'atraso_fib' in stats_fib:
                fib_atrasados = sorted(
                    fib.fibonacci, 
                    key=lambda x: stats_fib['atraso_fib'][x], 
                    reverse=True
                )[:5]
                jogo.update(random.sample(fib_atrasados, 4))
            else:
                jogo.update(random.sample(fib.fibonacci, 4))
            
            # 3. 3 números de ciclos atrasados (usando análise própria)
            atraso = self._calcular_atraso_simples(dados_treino)
            atrasados = sorted(atraso.items(), key=lambda x: x[1], reverse=True)[:10]
            numeros_atrasados = [n for n, _ in atrasados if n not in jogo]
            if len(numeros_atrasados) >= 3:
                jogo.update(random.sample(numeros_atrasados, 3))
            else:
                # Completar com números aleatórios que não estão no jogo
                disponiveis = [n for n in self.numeros if n not in jogo]
                jogo.update(random.sample(disponiveis, 3))
            
            # 4. 2 números de média frequência (para balancear)
            freq = self._calcular_frequencia(dados_treino[:20])
            medios = sorted(freq.items(), key=lambda x: x[1])[5:15]
            numeros_medios = [n for n, _ in medios if n not in jogo]
            if len(numeros_medios) >= 2:
                jogo.update(random.sample(numeros_medios, 2))
            
            # Garantir 15 números
            while len(jogo) < 15:
                disponiveis = [n for n in self.numeros if n not in jogo]
                if disponiveis:
                    jogo.add(random.choice(disponiveis))
            
            # Balancear pares/ímpares
            jogo_balanceado = self._balancear_jogo(list(jogo))
            
            if len(jogo_balanceado) == 15:
                jogos_hibridos.append(sorted(jogo_balanceado))
            
            if len(jogos_hibridos) >= 5:
                break
        
        return jogos_hibridos[:5]
    
    def _calcular_atraso_simples(self, concursos):
        """Calcula atraso simples dos números"""
        atraso = {n: 0 for n in self.numeros}
        for i, concurso in enumerate(concursos):
            for n in self.numeros:
                if n in concurso:
                    atraso[n] = i
        return atraso
    
    def _calcular_frequencia(self, concursos):
        """Calcula frequência dos números"""
        freq = Counter()
        for concurso in concursos:
            freq.update(concurso)
        return freq
    
    def _balancear_jogo(self, jogo):
        """Balanceia pares/ímpares do jogo"""
        pares = sum(1 for n in jogo if n % 2 == 0)
        
        # Alvo: 6-9 pares (ideal Lotofácil)
        if pares < 6:
            # Trocar ímpares por pares
            impares_no_jogo = [n for n in jogo if n % 2 == 1]
            pares_fora = [n for n in self.numeros if n % 2 == 0 and n not in jogo]
            
            while pares < 6 and impares_no_jogo and pares_fora:
                jogo.remove(impares_no_jogo.pop())
                jogo.append(pares_fora.pop())
                pares += 1
        
        elif pares > 9:
            # Trocar pares por ímpares
            pares_no_jogo = [n for n in jogo if n % 2 == 0]
            impares_fora = [n for n in self.numeros if n % 2 == 1 and n not in jogo]
            
            while pares > 9 and pares_no_jogo and impares_fora:
                jogo.remove(pares_no_jogo.pop())
                jogo.append(impares_fora.pop())
                pares -= 1
        
        return jogo
    
    def _gerar_aleatorio_balanceado(self, n_jogos):
        """Gera jogos aleatórios balanceados (baseline)"""
        jogos = []
        for _ in range(n_jogos):
            while True:
                jogo = sorted(random.sample(self.numeros, 15))
                pares = sum(1 for n in jogo if n % 2 == 0)
                if 6 <= pares <= 9:
                    jogos.append(jogo)
                    break
        return jogos
    
    def _calcular_estatisticas_finais(self, resultados):
        """Calcula estatísticas finais do backtest"""
        estatisticas = {}
        
        for estrategia, dados in resultados.items():
            if dados['total_jogos'] == 0:
                continue
                
            estatisticas[estrategia] = {
                'total_jogos': dados['total_jogos'],
                'taxa_11_pontos': (dados['acertos_11'] / dados['total_jogos']) * 100,
                'taxa_12_pontos': (dados['acertos_12'] / dados['total_jogos']) * 100,
                'taxa_13_pontos': (dados['acertos_13'] / dados['total_jogos']) * 100,
                'taxa_14_pontos': (dados['acertos_14'] / dados['total_jogos']) * 100,
                'taxa_15_pontos': (dados['acertos_15'] / dados['total_jogos']) * 100,
                'taxa_13_plus': ((dados['acertos_13'] + dados['acertos_14'] + dados['acertos_15']) / dados['total_jogos']) * 100,
                'pontuacao_media': self._calcular_pontuacao_media(dados)
            }
        
        # Ordenar por taxa de 13+ pontos
        return dict(sorted(estatisticas.items(), 
                          key=lambda x: x[1]['taxa_13_plus'], 
                          reverse=True))
    
    def _calcular_pontuacao_media(self, dados):
        """Calcula pontuação média ponderada"""
        if dados['total_jogos'] == 0:
            return 0
            
        total_pontos = (
            dados['acertos_11'] * 11 +
            dados['acertos_12'] * 12 +
            dados['acertos_13'] * 13 +
            dados['acertos_14'] * 14 +
            dados['acertos_15'] * 15
        )
        return total_pontos / dados['total_jogos']
    
    def gerar_relatorio_backtest(self, resultados_backtest):
        """Gera relatório formatado do backtest"""
        relatorio = "📊 RELATÓRIO DE BACKTEST - LOTOFÁCIL\n"
        relatorio += "=" * 60 + "\n\n"
        
        relatorio += f"Período analisado: {len(self.concursos)} concursos\n"
        relatorio += f"Estratégias testadas: {len(resultados_backtest)}\n\n"
        
        relatorio += "🏆 RANKING DE ESTRATÉGIAS (por taxa 13+ pontos)\n"
        relatorio += "-" * 60 + "\n\n"
        
        for i, (estrategia, stats) in enumerate(resultados_backtest.items(), 1):
            relatorio += f"{i}º {estrategia.replace('_', ' ').title()}:\n"
            relatorio += f"  • Pontuação média: {stats['pontuacao_media']:.2f} pontos\n"
            relatorio += f"  • 11 pontos: {stats['taxa_11_pontos']:.1f}%\n"
            relatorio += f"  • 12 pontos: {stats['taxa_12_pontos']:.1f}%\n"
            relatorio += f"  • 13+ pontos: {stats['taxa_13_plus']:.2f}%\n"
            relatorio += f"  • 14 pontos: {stats['taxa_14_pontos']:.3f}%\n"
            relatorio += f"  • 15 pontos: {stats['taxa_15_pontos']:.5f}%\n"
            relatorio += f"  • Total jogos: {stats['total_jogos']}\n"
            relatorio += "-" * 40 + "\n"
        
        # Análise comparativa
        relatorio += "\n📈 ANÁLISE COMPARATIVA:\n"
        melhor = list(resultados_backtest.items())[0]
        aleatorio = resultados_backtest.get('Aleatorio_Balanceado', {})
        
        if aleatorio:
            relatorio += f"• Melhor vs Aleatório: {melhor[1]['taxa_13_plus']:.2f}% vs {aleatorio['taxa_13_plus']:.2f}%\n"
            relatorio += f"• Vantagem: {melhor[1]['taxa_13_plus'] - aleatorio['taxa_13_plus']:.2f}%\n"
        
        # Recomendação
        relatorio += "\n🎯 RECOMENDAÇÃO BASEADA EM DADOS:\n"
        relatorio += f"Estratégia recomendada: {list(resultados_backtest.keys())[0].replace('_', ' ')}\n"
        relatorio += f"Expectativa realista: {melhor[1]['pontuacao_media']:.1f} pontos por jogo\n"
        
        # Aviso estatístico
        relatorio += "\n⚠️ AVISO ESTATÍSTICO:\n"
        relatorio += "• Chance matemática 14 pontos: 0,0046%\n"
        relatorio += "• Chance matemática 15 pontos: 0,00003%\n"
        relatorio += "• Nenhuma estratégia altera significativamente essas probabilidades\n"
        
        return relatorio

# =========================
# NOVA CLASSE: FechamentoLotofacil
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
            # Completar com números restantes
            restantes = [n for n in self.numeros if n not in grupo1]
            grupo1.extend(random.sample(restantes, tamanho_grupo - len(grupo1)))
        grupos_sugeridos.append(sorted(grupo1[:tamanho_grupo]))
        
        # Grupo 2: Focado em Fibonacci
        fibonacci = [1, 2, 3, 5, 8, 13, 21]
        grupo2 = fibonacci.copy()
        # Adicionar números complementares baseados em frequência
        complementares = [n for n in top_frequentes if n not in grupo2]
        grupo2.extend(complementares[:tamanho_grupo - len(grupo2)])
        grupos_sugeridos.append(sorted(grupo2[:tamanho_grupo]))
        
        return grupos_sugeridos
    
    def gerar_fechamento_18_15(self, numeros_escolhidos, max_jogos=80, estrategia="cobertura"):
        """
        Fechamento de 18 números, gerando combinações otimizadas de 15.
        - 'numeros_escolhidos': lista de 18 números escolhidos pelo usuário ou pela IA.
        - 'max_jogos': limite de combinações a gerar.
        - 'estrategia': 'cobertura' ou 'estatistica'
        """
        if len(numeros_escolhidos) != 18:
            st.warning(f"Fechamento precisa de exatamente 18 números. Recebidos: {len(numeros_escolhidos)}")
            return []
        
        jogos = set()
        
        if estrategia == "cobertura":
            # Estratégia de cobertura sistemática
            # Garantir que cada número apareça em aproximadamente X jogos
            for i in range(max_jogos * 2):
                # Selecionar base fixa de 12 números com bom histórico
                base_fixa = random.sample(numeros_escolhidos, 12)
                
                # Completar com 3 números variáveis
                complemento = random.sample([n for n in numeros_escolhidos if n not in base_fixa], 3)
                
                jogo = sorted(base_fixa + complemento)
                
                # Validar estatísticas do jogo
                if self._validar_jogo_fechamento(jogo):
                    jogos.add(tuple(jogo))
                
                if len(jogos) >= max_jogos:
                    break
        
        elif estrategia == "estatistica":
            # Estratégia baseada em estatísticas dos últimos concursos
            if len(self.concursos) >= 10:
                # Analisar padrões dos últimos concursos
                for _ in range(max_jogos * 3):
                    # Priorizar números que seguem padrões recentes
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
        faixa1 = sum(1 for n in jogo if 1 <= n <= 8)    # Baixos
        faixa2 = sum(1 for n in jogo if 9 <= n <= 16)   # Médios
        faixa3 = sum(1 for n in jogo if 17 <= n <= 25)  # Altos
        
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
        
        # Contar quantas vezes cada número aparece
        contagem_numeros = Counter()
        for jogo in jogos_gerados:
            contagem_numeros.update(jogo)
        
        # Calcular estatísticas de cobertura
        total_numeros = len(numeros_escolhidos)
        cobertura_por_numero = {}
        
        for num in numeros_escolhidos:
            freq = contagem_numeros.get(num, 0)
            percentual = (freq / len(jogos_gerados)) * 100
            cobertura_por_numero[num] = {
                "frequencia": freq,
                "percentual": round(percentual, 1)
            }
        
        # Cobertura média
        cobertura_media = np.mean([cobertura_por_numero[n]["percentual"] for n in numeros_escolhidos])
        
        return {
            "cobertura_media": round(cobertura_media, 1),
            "cobertura_por_numero": cobertura_por_numero,
            "total_jogos": len(jogos_gerados),
            "total_numeros_cobertos": total_numeros
        }

# =========================
# NOVA FUNÇÃO: Análise de Sequência e Falha (Método da Tabela Lotofácil)
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
        """Cria tabela completa de análise (como na imagem enviada)."""
        sequencias = self.calcular_sequencias()
        falhas = self.calcular_falhas()
        
        # Ordenar números por sequência (mais para menos)
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
            # Top 10 números com maior sequência (mais frequentes)
            melhores = sorted(range(1, 26), key=lambda x: sequencias[x-1], reverse=True)[:10]
            
            # Top 10 números com maior falha (potencial retorno)
            retorno = sorted(range(1, 26), key=lambda x: falhas[x-1], reverse=True)[:10]
            
            # Misturar: 8 dos melhores + 7 dos que podem retornar
            combo = set(random.sample(melhores, 8) + random.sample(retorno, 7))
            
            # Garantir 15 números
            while len(combo) < 15:
                combo.add(random.choice([n for n in range(1, 26) if n not in combo]))
            
            # Ordenar o jogo
            jogos.append(sorted(list(combo)))
        
        return jogos
    
    def gerar_jogos_estrategicos(self, n_jogos=5, estrategia="balanceada"):
        """Gera jogos com estratégias específicas."""
        sequencias = self.calcular_sequencias()
        falhas = self.calcular_falhas()
        
        jogos = []
        
        # Classificar números em categorias
        melhores = sorted(range(1, 26), key=lambda x: sequencias[x-1], reverse=True)
        piores = sorted(range(1, 26), key=lambda x: sequencias[x-1])
        retorno = sorted(range(1, 26), key=lambda x: falhas[x-1], reverse=True)
        
        for _ in range(n_jogos):
            if estrategia == "balanceada":
                # 6 melhores, 5 médios, 4 retorno
                combo = set(random.sample(melhores[:10], 6) + 
                           random.sample(melhores[10:20], 5) + 
                           random.sample(retorno[:10], 4))
            
            elif estrategia == "conservadora":
                # 10 melhores, 5 médios
                combo = set(random.sample(melhores[:12], 10) + 
                           random.sample(melhores[12:20], 5))
            
            elif estrategia == "agressiva":
                # 5 melhores, 10 retorno
                combo = set(random.sample(melhores[:10], 5) + 
                           random.sample(retorno[:15], 10))
            
            elif estrategia == "aleatoria_padrao":
                # Aleatória respeitando padrões históricos
                pares = random.randint(6, 9)
                impares = 15 - pares
                
                numeros_pares = [n for n in range(1, 26) if n % 2 == 0]
                numeros_impares = [n for n in range(1, 26) if n % 2 == 1]
                
                combo = set(random.sample(numeros_pares, pares) + 
                           random.sample(numeros_impares, impares))
            
            # Garantir 15 números
            while len(combo) < 15:
                combo.add(random.choice([n for n in range(1, 26) if n not in combo]))
            
            # Ordenar o jogo
            jogos.append(sorted(list(combo)))
        
        return jogos

# =========================
# NOVA FUNÇÃO: Análise Estatística Avançada
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
            q1 = sum(1 for n in concurso_atual if 1 <= n <= 6)   # Quadrante 1
            q2 = sum(1 for n in concurso_atual if 7 <= n <= 13)  # Quadrante 2
            q3 = sum(1 for n in concurso_atual if 14 <= n <= 19) # Quadrante 3
            q4 = sum(1 for n in concurso_atual if 20 <= n <= 25) # Quadrante 4
            
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
            
            # 5. Variação do concurso anterior (se disponível)
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
        return np.mean(distancias)
    
    def analisar_padroes_sazonais(self, janela=30):
        """Analisa padrões sazonais nos concursos."""
        if len(self.concursos) < janela:
            return {}
        
        concursos_janela = self.concursos[:janela]
        
        # Padrões por dia da semana (se tiver datas)
        padroes = {
            "media_pares": [],
            "media_primos": [],
            "media_soma": [],
            "numeros_quentes_janela": [],
            "numeros_frios_janela": []
        }
        
        for concurso in concursos_janela:
            pares = sum(1 for n in concurso if n % 2 == 0)
            primos = sum(1 for n in concurso if n in self.primos)
            soma = sum(concurso)
            
            padroes["media_pares"].append(pares)
            padroes["media_primos"].append(primos)
            padroes["media_soma"].append(soma)
        
        # Calcular números quentes e frios na janela
        freq = Counter()
        for concurso in concursos_janela:
            freq.update(concurso)
        
        quentes = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
        frios = sorted(freq.items(), key=lambda x: x[1])[:10]
        
        padroes["numeros_quentes_janela"] = [n for n, _ in quentes]
        padroes["numeros_frios_janela"] = [n for n, _ in frios]
        
        # Calcular médias
        padroes["media_pares_final"] = np.mean(padroes["media_pares"])
        padroes["media_primos_final"] = np.mean(padroes["media_primos"])
        padroes["media_soma_final"] = np.mean(padroes["media_soma"])
        
        return padroes

# =========================
# CLASSE: AnaliseCiclos (Ciclo Dinâmico Real) - MODIFICADA
# =========================
class AnaliseCiclos:
    """
    Implementa o ciclo dinâmico:
    - Recebe concursos (lista, onde index 0 = concurso mais recente)
    - Permite definir um limite de concursos para analisar
    - Percorre do mais recente para o mais antigo acumulando dezenas até todas as 25 sejam vistas ou atingir o limite
    - Expõe: numeros_presentes_no_ciclo, numeros_faltantes, concursos_no_ciclo (lista), tamanho, status (normal/atrasado)
    - Gera 5 cartoes priorizando dezenas faltantes e atrasadas no ciclo
    """
    def __init__(self, concursos, concursos_info=None, limite_concursos=None):
        self.concursos = concursos  # espera lista: [mais recente, ...]
        self.concursos_info = concursos_info or {}  # Dicionário com informações dos concursos
        self.TODAS = set(range(1,26))
        self.ciclo_concursos = []  # lista de concursos (cada concurso = lista de 15 dezenas) pertencentes ao ciclo (do mais recente para o mais antigo)
        self.ciclo_concursos_info = []  # Informações dos concursos no ciclo
        self.numeros_presentes = set()
        self.numeros_faltantes = set(self.TODAS)
        self.tamanho = 0  # número de concursos no ciclo
        self.iniciar_indice = None  # indice do concurso mais antigo que entrou no ciclo (0 = mais recente)
        self.limite_concursos = limite_concursos  # Novo: limite de concursos a analisar
        self.analisar()
    
    def analisar(self):
        """Detecta o ciclo dinâmico atual: acumula concursos até todas as 25 dezenas aparecerem ou atingir o limite."""
        self.ciclo_concursos = []
        self.ciclo_concursos_info = []
        self.numeros_presentes = set()
        self.numeros_faltantes = set(self.TODAS)
        self.iniciar_indice = None
        
        # Determinar o limite máximo de concursos a analisar
        max_concursos = len(self.concursos)
        if self.limite_concursos is not None:
            max_concursos = min(self.limite_concursos, len(self.concursos))
        
        # Ajustar mínimo para 10 concursos
        if max_concursos < 10:
            max_concursos = min(10, len(self.concursos))
        
        # percorre do mais recente (0) para o mais antigo
        for idx, concurso in enumerate(self.concursos[:max_concursos]):
            if not concurso:
                continue
            self.ciclo_concursos.append(concurso)
            
            # Armazenar informações do concurso, se disponíveis
            if idx in self.concursos_info:
                self.ciclo_concursos_info.append(self.concursos_info[idx])
            else:
                # Criar informações básicas se não houver
                self.ciclo_concursos_info.append({
                    "indice": idx,
                    "numero_concurso": f"Concurso {len(self.concursos) - idx}",
                    "dezenas": concurso
                })
            
            self.numeros_presentes.update(concurso)
            self.numeros_faltantes = self.TODAS - self.numeros_presentes
            # marca o índice mais antigo que foi considerado até agora
            self.iniciar_indice = idx
            
            if not self.numeros_faltantes:  # ciclo fechado
                break
        
        self.tamanho = len(self.ciclo_concursos)
    
    def status(self):
        """Define estado do ciclo"""
        if not self.numeros_faltantes:
            return "Fechado"
        
        # Definir status baseado no tamanho do ciclo
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
        """Retorna atraso (em concursos) por número dentro do ciclo (quanto tempo desde que saiu pela última vez dentro do ciclo)."""
        # Para cada número, contar quantos concursos desde a sua última aparição (0 = apareceu no concurso mais recente)
        atraso = {n: None for n in range(1,26)}
        # percorre concursos do mais recente para o mais antigo
        for idx, concurso in enumerate(self.ciclo_concursos):
            for n in self.TODAS:
                if atraso[n] is None and n in concurso:
                    atraso[n] = idx  # idx concursos desde o mais recente onde apareceu
        # para os que nunca apareceram no ciclo -> definir como tamanho (maior atraso)
        for n in range(1,26):
            if atraso[n] is None:
                atraso[n] = self.tamanho
        return atraso
    
    def gerar_5_cartoes_ciclo(self, n_cartoes=5, seed=None, incluir_todas_faltantes=False):
        """
        Gera n_cartoes=5 cartoes de 15 dezenas garantindo que sejam DISTINTOS.
        Prioridades:
        1) Dezenas faltantes (incluir todas nas primeiras combinações quando possível)
        2) Dezenas com maior atraso dentro do ciclo
        3) Diversidade entre os cartões
        4) Equilíbrio pares/impares
        """
        if seed is not None:
            random.seed(seed)
        
        atraso = self.contar_atrasos_no_ciclo()
        faltantes = sorted(list(self.numeros_faltantes))
        todas_dezenas = list(range(1, 26))
        
        # Ordenar números por atraso (maior atraso primeiro)
        ordenado_por_atraso = sorted(todas_dezenas, key=lambda x: atraso[x], reverse=True)
        
        cartoes = []
        tentativas_max = n_cartoes * 50  # Limite para evitar loop infinito
        tentativas = 0
        
        # Se o usuário quiser incluir todas as faltantes
        if incluir_todas_faltantes and faltantes:
            # Estratégia 1: Distribuir todas as faltantes entre os cartões
            return self._gerar_cartoes_distribuindo_faltantes(faltantes, n_cartoes, atraso)
        
        # Estratégia normal: garantir 5 cartões distintos
        while len(cartoes) < n_cartoes and tentativas < tentativas_max:
            tentativas += 1
            cartao_set = set()
            
            # 1. Incluir algumas dezenas faltantes (30-40% do cartão)
            if faltantes:
                max_faltantes = min(len(faltantes), random.randint(4, 6))  # 4-6 faltantes
                faltantes_escolhidas = random.sample(faltantes, max_faltantes)
                cartao_set.update(faltantes_escolhidas)
            
            # 2. Adicionar números com maior atraso (não-faltantes)
            # Filtrar números que não são faltantes e não estão no cartão
            numeros_nao_faltantes = [n for n in ordenado_por_atraso if n not in faltantes]
            numeros_disponiveis = [n for n in numeros_nao_faltantes if n not in cartao_set]
            
            if numeros_disponiveis:
                # Adicionar 4-6 números de alto atraso
                qtd_atraso = random.randint(4, 6)
                qtd_atraso = min(qtd_atraso, len(numeros_disponiveis))
                if qtd_atraso > 0:
                    atraso_escolhidos = random.sample(numeros_disponiveis[:15], qtd_atraso)
                    cartao_set.update(atraso_escolhidos)
            
            # 3. Completar com números aleatórios (garantindo diversidade)
            # Verificar quais cartões já foram gerados para evitar similaridade excessiva
            numeros_restantes = [n for n in todas_dezenas if n not in cartao_set]
            
            while len(cartao_set) < 15 and numeros_restantes:
                # Priorizar números que não apareceram muito nos cartões anteriores
                if cartoes:
                    # Contar frequência nos cartões existentes
                    freq_cartoes = Counter()
                    for c in cartoes:
                        freq_cartoes.update(c)
                    
                    # Ordenar números restantes por menor frequência primeiro (para diversificar)
                    numeros_restantes.sort(key=lambda x: freq_cartoes[x])
                
                # Escolher um número dos restantes
                escolha = random.choice(numeros_restantes[:10]) if len(numeros_restantes) >= 10 else random.choice(numeros_restantes)
                cartao_set.add(escolha)
                numeros_restantes = [n for n in todas_dezenas if n not in cartao_set]
            
            # 4. Ajustar equilíbrio de pares/ímpares
            self._ajustar_equilibrio(cartao_set, todas_dezenas)
            
            # 5. Converter para lista ordenada
            cartao_ordenado = sorted(list(cartao_set))
            
            # 6. Verificar se é distinto dos cartões já gerados
            if self._cartao_eh_distinto(cartao_ordenado, cartoes, limite_similaridade=10):
                cartoes.append(cartao_ordenado)
        
        # Se não conseguiu gerar cartões suficientes, completar com cartões aleatórios mas distintos
        while len(cartoes) < n_cartoes:
            cartao_novo = sorted(random.sample(todas_dezenas, 15))
            
            # Ajustar equilíbrio
            pares = sum(1 for n in cartao_novo if n % 2 == 0)
            if pares < 6 or pares > 9:
                # Regerar até ter equilíbrio
                cartao_novo = self._gerar_cartao_balanceado(todas_dezenas)
            
            if self._cartao_eh_distinto(cartao_novo, cartoes, limite_similaridade=10):
                cartoes.append(cartao_novo)
        
        return cartoes[:n_cartoes]
    
    def _gerar_cartoes_distribuindo_faltantes(self, faltantes, n_cartoes, atraso):
        """Estratégia especial quando queremos incluir todas as faltantes"""
        todas_dezenas = list(range(1, 26))
        ordenado_por_atraso = sorted(todas_dezenas, key=lambda x: atraso[x], reverse=True)
        
        cartoes = []
        
        # Se há 15 ou menos faltantes, podemos distribuir uniformemente
        if len(faltantes) <= 15:
            # Calcular quantas faltantes por cartão
            faltantes_por_cartao = max(1, len(faltantes) // n_cartoes)
            
            for i in range(n_cartoes):
                cartao_set = set()
                
                # Determinar quais faltantes este cartão recebe
                inicio_idx = i * faltantes_por_cartao
                fim_idx = inicio_idx + faltantes_por_cartao if i < n_cartoes - 1 else len(faltantes)
                
                if inicio_idx < len(faltantes):
                    faltantes_do_cartao = faltantes[inicio_idx:fim_idx]
                    cartao_set.update(faltantes_do_cartao)
                
                # Completar com números de alto atraso
                numeros_nao_faltantes = [n for n in ordenado_por_atraso if n not in faltantes]
                numeros_disponiveis = [n for n in numeros_nao_faltantes if n not in cartao_set]
                
                qtd_necessaria = 15 - len(cartao_set)
                if numeros_disponiveis and qtd_necessaria > 0:
                    qtd_escolher = min(qtd_necessaria, len(numeros_disponiveis))
                    complemento = random.sample(numeros_disponiveis[:20], qtd_escolher)
                    cartao_set.update(complemento)
                
                # Completar se ainda faltar
                while len(cartao_set) < 15:
                    candidatos = [n for n in todas_dezenas if n not in cartao_set]
                    if candidatos:
                        cartao_set.add(random.choice(candidatos))
                
                # Ajustar equilíbrio
                self._ajustar_equilibrio(cartao_set, todas_dezenas)
                cartoes.append(sorted(list(cartao_set)))
        
        else:
            # Mais de 15 faltantes: cada cartão foca em um subconjunto diferente
            for i in range(n_cartoes):
                cartao_set = set()
                
                # Escolher 6-8 faltantes diferentes para cada cartão
                qtd_faltantes = random.randint(6, 8)
                faltantes_escolhidas = random.sample(faltantes, qtd_faltantes)
                cartao_set.update(faltantes_escolhidas)
                
                # Completar com outros números
                while len(cartao_set) < 15:
                    # Misturar: alguns de alto atraso, alguns aleatórios
                    if random.random() < 0.7 and len(cartao_set) < 12:
                        # Adicionar número de alto atraso
                        numeros_alto_atraso = [n for n in ordenado_por_atraso[:15] if n not in cartao_set]
                        if numeros_alto_atraso:
                            cartao_set.add(random.choice(numeros_alto_atraso[:5]))
                    else:
                        # Adicionar número aleatório
                        candidatos = [n for n in todas_dezenas if n not in cartao_set]
                        if candidatos:
                            cartao_set.add(random.choice(candidatos))
                
                # Ajustar equilíbrio
                self._ajustar_equilibrio(cartao_set, todas_dezenas)
                cartao_ordenado = sorted(list(cartao_set))
                
                # Garantir que não é muito similar aos anteriores
                if self._cartao_eh_distinto(cartao_ordenado, cartoes, limite_similaridade=9):
                    cartoes.append(cartao_ordenado)
        
        # Garantir exatamente n_cartoes distintos
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
        """
        Verifica se um cartão é suficientemente distinto dos cartões existentes.
        limite_similaridade: número máximo de dezenas em comum para considerar distinto.
        """
        if not cartoes_existentes:
            return True
        
        for cartao_existente in cartoes_existentes:
            # Contar quantas dezenas em comum
            dezenas_comuns = len(set(cartao_novo) & set(cartao_existente))
            
            # Se tiver mais de 'limite_similaridade' dezenas em comum, não é suficientemente distinto
            if dezenas_comuns > limite_similaridade:
                return False
        
        return True
    
    def _gerar_cartao_balanceado(self, todas_dezenas):
        """Gera um cartão balanceado com equilíbrio de pares/ímpares"""
        while True:
            cartao = sorted(random.sample(todas_dezenas, 15))
            pares = sum(1 for n in cartao if n % 2 == 0)
            primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
            
            # Critérios de balanceamento para Lotofácil
            if 6 <= pares <= 9 and 3 <= primos <= 7:
                return cartao
    
    def _ajustar_equilibrio(self, cartao_set, todas_dezenas):
        """Ajusta o equilíbrio de pares/ímpares no cartão"""
        pares = sum(1 for n in cartao_set if n % 2 == 0)
        
        # Balancear para ter entre 6 e 9 pares (ideal para Lotofácil)
        if pares < 6:
            # Trocar um ímpar por um par
            impares_no_cartao = [n for n in cartao_set if n % 2 == 1]
            pares_fora_cartao = [n for n in todas_dezenas if n % 2 == 0 and n not in cartao_set]
            
            if impares_no_cartao and pares_fora_cartao:
                cartao_set.remove(random.choice(impares_no_cartao))
                cartao_set.add(random.choice(pares_fora_cartao))
        
        elif pares > 9:
            # Trocar um par por um ímpar
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
# CLASSE: Análise Combinatória
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
                    # Evitar duplicatas
                    if combo not in combinacoes_geradas:
                        combinacoes_geradas.append(combo)
                
                tentativas += 1
            
            # Analisar e ranquear as combinações
            combinacoes_ranqueadas = self.ranquear_combinacoes(combinacoes_geradas, tamanho)
            todas_combinacoes[tamanho] = combinacoes_ranqueadas[:quantidade_por_tamanho]
            
        return todas_combinacoes

    def validar_combinacao(self, combinacao, tamanho):
        """Valida combinação com base em estatísticas históricas"""
        pares = sum(1 for n in combinacao if n % 2 == 0)
        impares = len(combinacao) - pares
        soma = sum(combinacao)
        primos = sum(1 for n in combinacao if n in self.primos)
        
        # Critérios baseados no tamanho da combinação
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
        
        # Ordenar por score (maiores primeiro)
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def calcular_score_combinacao(self, combinacao, tamanho):
        """Calcula score baseado em múltiplos fatores estatísticos"""
        score = 0
        
        # Fator par/ímpar
        pares = sum(1 for n in combinacao if n % 2 == 0)
        if tamanho == 15 and 6 <= pares <= 8:
            score += 3
        elif tamanho == 14 and 5 <= pares <= 8:
            score += 3
        elif tamanho == 13 and 5 <= pares <= 7:
            score += 3
        elif tamanho == 12 and 4 <= pares <= 6:
            score += 3
            
        # Fator soma
        soma = sum(combinacao)
        if tamanho == 15 and 180 <= soma <= 200:
            score += 3
        elif tamanho == 14 and 160 <= soma <= 190:
            score += 3
        elif tamanho == 13 and 150 <= soma <= 180:
            score += 3
        elif tamanho == 12 and 130 <= soma <= 160:
            score += 3
            
        # Fator números consecutivos
        consecutivos = self.contar_consecutivos(combinacao)
        if consecutivos <= 4:
            score += 2
            
        # Fator números primos
        primos = sum(1 for n in combinacao if n in self.primos)
        if 3 <= primos <= 6:
            score += 2
            
        # Fator de distribuição
        if self.validar_distribuicao(combinacao):
            score += 2
            
        # Fator de frequência histórica
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
        faixa1 = sum(1 for n in combinacao if 1 <= n <= 9)   # 1-9
        faixa2 = sum(1 for n in combinacao if 10 <= n <= 19) # 10-19
        faixa3 = sum(1 for n in combinacao if 20 <= n <= 25) # 20-25
        
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
            
        # Calcular frequência dos números nos últimos concursos
        freq = Counter()
        for concurso in self.concursos[:50]:  # Últimos 50 concursos
            for numero in concurso:
                freq[numero] += 1
                
        # Score baseado na frequência média dos números na combinação
        freq_media = sum(freq[n] for n in combinacao) / len(combinacao)
        freq_max = max(freq.values()) if freq.values() else 1
        
        # Normalizar score (0 a 2 pontos)
        return (freq_media / freq_max) * 2

    def gerar_relatorio_estatistico(self, combinacoes_por_tamanho):
        """Gera relatório estatístico das combinações"""
        relatorio = {}
        
        for tamanho, combinacoes in combinacoes_por_tamanho.items():
            if not combinacoes:
                continue
                
            stats = {
                'total_combinacoes': len(combinacoes),
                'media_score': np.mean([score for _, score in combinacoes]),
                'melhor_score': max([score for _, score in combinacoes]),
                'pior_score': min([score for _, score in combinacoes]),
                'exemplos_top5': combinacoes[:5]
            }
            relatorio[tamanho] = stats
            
        return relatorio

    def formatar_como_cartao(self, combinacao):
        """Formata uma combinação como cartão da Lotofácil 5x5"""
        cartao = []
        for i in range(5):
            linha = []
            for j in range(5):
                numero = i * 5 + j + 1
                if numero in combinacao:
                    linha.append(f"[{numero:2d}]")  # Número marcado
                else:
                    linha.append(f" {numero:2d} ")  # Número não marcado
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
                
                # Adicionar lista dos números selecionados
                numeros_selecionados = [n for n in combo]
                conteudo += f"Números: {numeros_selecionados}\n"
                
                # Estatísticas do cartão
                pares = sum(1 for n in combo if n % 2 == 0)
                primos = sum(1 for n in combo if n in self.primos)
                soma = sum(combo)
                conteudo += f"Pares: {pares}, Ímpares: {len(combo)-pares}, Primos: {primos}, Soma: {soma}\n"
                conteudo += "\n" + "=" * 50 + "\n\n"
        
        return conteudo

# =========================
# IA Avançada com CatBoost
# =========================
class LotoFacilIA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}
        self.models = {}
        if len(concursos) > 10:  # Ajustado para mínimo de 10 concursos
            self.X = self.gerar_features()[:-1] if len(concursos) > 1 else np.array([])
            self.Y = self.matriz_binaria()[1:] if len(concursos) > 1 else np.array([])
            if len(self.X) > 0 and len(self.Y) > 0:
                try:
                    self.treinar_modelos()
                except Exception as e:
                    # Em ambiente com pouco dado ou CatBoost ausente, ignorar treinamento
                    st.warning(f"CatBoost não pôde ser carregado: {e}")
                    self.models = {}

    def matriz_binaria(self):
        return np.array([[1 if n in jogo else 0 for n in self.numeros] for jogo in self.concursos])

    def frequencia(self, janela=10):
        janela = min(janela, max(1, len(self.concursos)-1))
        if janela < 10:  # Garantir mínimo de 10 concursos
            janela = min(10, len(self.concursos))
        freq = {n:0 for n in self.numeros}
        # considerar os concursos mais recentes (índice 0 é mais recente)
        if len(self.concursos) <= 1:
            return freq
        limite = min(len(self.concursos)-1, janela)
        for jogo in self.concursos[0:limite]:
            for d in jogo:
                freq[d] +=1
        return freq

    def atraso(self):
        atraso = {n:0 for n in self.numeros}
        # calcula atraso em relação ao mais recente (índice 0)
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
        # último concurso = índice 0 (mais recente)
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
        # usar concursos mais recentes: índices 0..janela-1
        for jogo in self.concursos[0:janela]:
            for i in range(15):
                for j in range(i+1,15):
                    matriz[jogo[i]-1, jogo[j]-1] += 1
                    matriz[jogo[j]-1, jogo[i]-1] += 1
        return matriz

    def prob_condicional(self, janela=50):
        matriz = self.interacoes(janela)
        prob = np.zeros((25,25))
        freq = np.array([v for v in self.frequencia(janela).values()])
        for i in range(25):
            for j in range(25):
                if freq[i] > 0:
                    prob[i,j] = matriz[i,j]/freq[i]
        return prob

    def gap_medio(self):
        gaps = {n:[] for n in self.numeros}
        # percorre concursos mais antigos para recentes
        total = len(self.concursos)
        for i, jogo in enumerate(self.concursos):
            for n in self.numeros:
                if n not in jogo:
                    gaps[n].append(total - i)
        return {n: np.mean(gaps[n]) if gaps[n] else 0 for n in self.numeros}

    def gerar_features(self):
        features = []
        if len(self.concursos) < 10:  # Ajustado para mínimo de 10
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
        if len(self.concursos) < 10:  # Ajustado para mínimo de 10
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
            # fallback: usar frequencias normalizadas
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
        
        # garantir distintos
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
        base = list(set(base))  # dedup
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
        media_pares = max(5, min(10, media_pares))  # limitar pra não travar
        media_impares = 15 - media_pares

        jogos=[]
        for _ in range(n_jogos):
            cartao = set()
            # escolhe pares
            candidatos_pares = evens_q if len(evens_q) >= media_pares else [x for x in range(2,26,2)]
            cartao.update(random.sample(candidatos_pares, media_pares))
            # escolhe ímpares
            candidatos_impares = odds_q if len(odds_q) >= media_impares else [x for x in range(1,26,2)]
            faltam = media_impares
            cartao.update(random.sample(candidatos_impares, faltam))
            # completa se faltar
            while len(cartao) < 15:
                cartao.add(random.choice(frios if frios else list(range(1,26))))
            jogos.append(sorted(list(cartao)))
        # garantir distintos
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
# ESTRATÉGIA FIBONACCI
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
            
        # Analisar últimos concursos (mínimo 10)
        janela = min(50, len(self.concursos))
        if janela < 10:
            janela = min(10, len(self.concursos))
        concursos_recentes = self.concursos[:janela]
        
        # Estatísticas das dezenas Fibonacci
        stats = {
            'frequencia_fib': {num: 0 for num in self.fibonacci},
            'media_por_concurso': [],
            'ultima_aparicao': {num: 0 for num in self.fibonacci},
            'atraso_fib': {num: 0 for num in self.fibonacci}
        }
        
        # Calcular frequência e última aparição
        for idx, concurso in enumerate(concursos_recentes):
            fib_no_concurso = [num for num in concurso if num in self.fibonacci]
            stats['media_por_concurso'].append(len(fib_no_concurso))
            
            for num in self.fibonacci:
                if num in concurso:
                    stats['frequencia_fib'][num] += 1
                    stats['ultima_aparicao'][num] = idx
        
        # Calcular atraso (concursos desde a última aparição)
        for num in self.fibonacci:
            if stats['ultima_aparicao'][num] > 0:
                stats['atraso_fib'][num] = stats['ultima_aparicao'][num]
            else:
                stats['atraso_fib'][num] = janela  # Nunca apareceu na janela
        
        # Calcular estatísticas gerais
        stats['media_geral'] = np.mean(stats['media_por_concurso']) if stats['media_por_concurso'] else 0
        stats['moda_geral'] = max(set(stats['media_por_concurso']), key=stats['media_por_concurso'].count) if stats['media_por_concurso'] else 0
        stats['min_geral'] = min(stats['media_por_concurso']) if stats['media_por_concurso'] else 0
        stats['max_geral'] = max(stats['media_por_concurso']) if stats['media_por_concurso'] else 0
        
        return stats
    
    def gerar_cartoes_fibonacci(self, n_cartoes=10, usar_estatisticas=True):
        """Gera cartões usando estratégia Fibonacci com 4 ou 5 números Fibonacci"""
        cartoes = []
        
        # Obter estatísticas se solicitado
        stats = self.analisar_fibonacci() if usar_estatisticas else {}
        
        for _ in range(n_cartoes * 3):  # Gerar mais para garantir diversidade e exclusividade
            # Escolher 4 ou 5 números Fibonacci
            qtd_fib = random.choice([4, 5])
            
            if usar_estatisticas and stats:
                # Priorizar Fibonacci com maior atraso ou menor frequência
                fib_ordenados = sorted(
                    self.fibonacci, 
                    key=lambda x: (stats['atraso_fib'][x], -stats['frequencia_fib'][x]), 
                    reverse=True
                )
                fib_selecionadas = random.sample(fib_ordenados[:5], qtd_fib)
            else:
                # Seleção aleatória pura
                fib_selecionadas = random.sample(self.fibonacci, qtd_fib)
            
            # Dezenas não-Fibonacci
            nao_fib = [num for num in self.numeros if num not in self.fibonacci]
            
            # Se estiver usando estatísticas, obter frequência dos não-Fibonacci
            if usar_estatisticas and self.concursos:
                # Calcular frequência dos não-Fibonacci nos últimos concursos
                janela = min(30, len(self.concursos))
                if janela < 10:
                    janela = min(10, len(self.concursos))
                freq_nao_fib = Counter()
                for concurso in self.concursos[:janela]:
                    for num in concurso:
                        if num in nao_fib:
                            freq_nao_fib[num] += 1
                
                # Ordenar não-Fibonacci por frequência (mais frequentes primeiro)
                nao_fib_ordenados = sorted(nao_fib, key=lambda x: freq_nao_fib[x], reverse=True)
                
                # Selecionar não-Fibonacci: 60% dos mais frequentes, 40% aleatórios
                qtd_nao_fib = 15 - qtd_fib
                qtd_frequentes = int(qtd_nao_fib * 0.6)
                qtd_aleatorios = qtd_nao_fib - qtd_frequentes
                
                # Selecionar dos mais frequentes (garantindo não repetição)
                selecao_frequentes = []
                if len(nao_fib_ordenados) >= qtd_frequentes:
                    candidatos = [n for n in nao_fib_ordenados[:20] if n not in fib_selecionadas]
                    if len(candidatos) >= qtd_frequentes:
                        selecao_frequentes = random.sample(candidatos, qtd_frequentes)
                    else:
                        selecao_frequentes = candidatos
                
                # Selecionar aleatórios para completar (garantindo não repetição)
                restantes = [num for num in nao_fib if num not in fib_selecionadas and num not in selecao_frequentes]
                if restantes and qtd_aleatorios > 0:
                    if len(restantes) >= qtd_aleatorios:
                        selecao_aleatorios = random.sample(restantes, qtd_aleatorios)
                    else:
                        selecao_aleatorios = restantes
                    
                    selecao_nao_fib = selecao_frequentes + selecao_aleatorios
                else:
                    selecao_nao_fib = selecao_frequentes
                
                # Completar se necessário (garantindo não repetição)
                while len(selecao_nao_fib) < qtd_nao_fib:
                    candidatos = [num for num in nao_fib if num not in fib_selecionadas and num not in selecao_nao_fib]
                    if candidatos:
                        selecao_nao_fib.append(random.choice(candidatos))
                    else:
                        # Se não houver mais candidatos únicos, reiniciar
                        break
            else:
                # Seleção aleatória simples (garantindo não repetição)
                qtd_nao_fib = 15 - qtd_fib
                candidatos_nao_fib = [num for num in nao_fib if num not in fib_selecionadas]
                if len(candidatos_nao_fib) >= qtd_nao_fib:
                    selecao_nao_fib = random.sample(candidatos_nao_fib, qtd_nao_fib)
                else:
                    selecao_nao_fib = candidatos_nao_fib
            
            # Combinar e ordenar
            cartao = sorted(fib_selecionadas + selecao_nao_fib)
            
            # Verificar se tem 15 números únicos
            if len(set(cartao)) != 15:
                continue  # Pular cartões com números repetidos
            
            # Validar equilíbrio de pares/ímpares
            pares = sum(1 for n in cartao if n % 2 == 0)
            if 6 <= pares <= 9:  # Faixa ideal para Lotofácil
                # Verificar se cartão é único (não repetido)
                if cartao not in cartoes:
                    cartoes.append(cartao)
            
            # Parar quando tiver cartões suficientes
            if len(cartoes) >= n_cartoes:
                break
        
        # Garantir número exato de cartões (com números únicos)
        while len(cartoes) < n_cartoes:
            # Fallback: geração simples com garantia de números únicos
            qtd_fib = random.choice([4, 5])
            fib_selecionadas = random.sample(self.fibonacci, qtd_fib)
            nao_fib = [num for num in self.numeros if num not in self.fibonacci]
            candidatos_nao_fib = [num for num in nao_fib if num not in fib_selecionadas]
            
            if len(candidatos_nao_fib) >= (15 - qtd_fib):
                selecao_nao_fib = random.sample(candidatos_nao_fib, 15 - qtd_fib)
                cartao = sorted(fib_selecionadas + selecao_nao_fib)
                
                # Verificar exclusividade e não repetição
                if len(set(cartao)) == 15 and cartao not in cartoes:
                    cartoes.append(cartao)
            else:
                # Se não houver números suficientes, usar todos os disponíveis
                cartao = sorted(fib_selecionadas + candidatos_nao_fib)
                # Completar com números aleatórios únicos
                while len(cartao) < 15:
                    candidato = random.choice([n for n in self.numeros if n not in cartao])
                    cartao.append(candidato)
                cartao = sorted(cartao)
                
                if len(set(cartao)) == 15 and cartao not in cartoes:
                    cartoes.append(cartao)
        
        return cartoes[:n_cartoes]
    
    def gerar_cartoes_fibonacci_estrategia(self, estrategia="padrao", n_cartoes=10):
        """Gera cartões com diferentes estratégias Fibonacci"""
        cartoes = []
        
        if estrategia == "padrao":
            # Estratégia padrão: 4-5 Fibonacci + estatísticas
            return self.gerar_cartoes_fibonacci(n_cartoes, usar_estatisticas=True)
        
        elif estrategia == "fibonacci_quentes":
            # Foca nos Fibonacci mais frequentes
            stats = self.analisar_fibonacci()
            fib_ordenados = sorted(
                self.fibonacci, 
                key=lambda x: stats['frequencia_fib'][x], 
                reverse=True
            )
            
            for _ in range(n_cartoes * 2):  # Gerar mais para garantir números únicos
                qtd_fib = random.choice([4, 5])
                fib_selecionadas = random.sample(fib_ordenados[:5], qtd_fib)
                
                # Complementar com números quentes não-Fibonacci
                nao_fib = [num for num in self.numeros if num not in self.fibonacci]
                
                # Calcular frequência dos não-Fibonacci
                janela = min(30, len(self.concursos))
                if janela < 10:
                    janela = min(10, len(self.concursos))
                freq_nao_fib = Counter()
                for concurso in self.concursos[:janela]:
                    for num in concurso:
                        if num in nao_fib:
                            freq_nao_fib[num] += 1
                
                nao_fib_ordenados = sorted(nao_fib, key=lambda x: freq_nao_fib[x], reverse=True)
                
                # Selecionar não-Fibonacci únicos
                candidatos_quentes = [n for n in nao_fib_ordenados[:20] if n not in fib_selecionadas]
                if len(candidatos_quentes) >= (15 - qtd_fib):
                    selecao_nao_fib = random.sample(candidatos_quentes, 15 - qtd_fib)
                    cartao = sorted(fib_selecionadas + selecao_nao_fib)
                    
                    # Verificar exclusividade
                    if len(set(cartao)) == 15 and cartao not in cartoes:
                        cartoes.append(cartao)
        
        elif estrategia == "fibonacci_atrasados":
            # Foca nos Fibonacci com maior atraso
            stats = self.analisar_fibonacci()
            fib_ordenados = sorted(
                self.fibonacci, 
                key=lambda x: stats['atraso_fib'][x], 
                reverse=True
            )
            
            for _ in range(n_cartoes * 2):  # Gerar mais para garantir números únicos
                qtd_fib = random.choice([4, 5])
                fib_selecionadas = random.sample(fib_ordenados[:5], qtd_fib)
                
                # Complementar com números atrasados não-Fibonacci
                nao_fib = [num for num in self.numeros if num not in self.fibonacci]
                
                # Calcular atraso dos não-Fibonacci
                atraso_nao_fib = {num: 0 for num in nao_fib}
                for num in nao_fib:
                    for idx, concurso in enumerate(self.concursos):
                        if num in concurso:
                            atraso_nao_fib[num] = idx
                            break
                    else:
                        atraso_nao_fib[num] = len(self.concursos)
                
                nao_fib_ordenados = sorted(nao_fib, key=lambda x: atraso_nao_fib[x], reverse=True)
                
                # Selecionar não-Fibonacci únicos
                candidatos_atrasados = [n for n in nao_fib_ordenados[:20] if n not in fib_selecionadas]
                if len(candidatos_atrasados) >= (15 - qtd_fib):
                    selecao_nao_fib = random.sample(candidatos_atrasados, 15 - qtd_fib)
                    cartao = sorted(fib_selecionadas + selecao_nao_fib)
                    
                    # Verificar exclusividade
                    if len(set(cartao)) == 15 and cartao not in cartoes:
                        cartoes.append(cartao)
        
        elif estrategia == "fibonacci_balanceado":
            # Balanceia entre Fibonacci e não-Fibonacci baseado em estatísticas
            for _ in range(n_cartoes * 3):  # Gerar mais para garantir números únicos
                qtd_fib = random.choice([4, 5])
                
                # Selecionar Fibonacci: 2-3 quentes, 2-3 atrasados
                stats = self.analisar_fibonacci()
                
                fib_quentes = sorted(self.fibonacci, key=lambda x: stats['frequencia_fib'][x], reverse=True)[:4]
                fib_atrasados = sorted(self.fibonacci, key=lambda x: stats['atraso_fib'][x], reverse=True)[:4]
                
                # Misturar estratégias
                if qtd_fib == 4:
                    # Selecionar 2 quentes e 2 atrasados
                    selecao_quentes = random.sample(fib_quentes[:3], 2)
                    selecao_atrasados = random.sample(fib_atrasados[:3], 2)
                    fib_selecionadas = selecao_quentes + selecao_atrasados
                else:  # qtd_fib == 5
                    # Selecionar 2 quentes e 3 atrasados
                    selecao_quentes = random.sample(fib_quentes[:3], 2)
                    selecao_atrasados = random.sample(fib_atrasados[:3], 3)
                    fib_selecionadas = selecao_quentes + selecao_atrasados
                
                # Garantir que não há Fibonacci repetidos
                fib_selecionadas = list(set(fib_selecionadas))
                if len(fib_selecionadas) < min(qtd_fib, 4):
                    # Se perdeu números, completar
                    while len(fib_selecionadas) < min(qtd_fib, 4):
                        candidato = random.choice([n for n in self.fibonacci if n not in fib_selecionadas])
                        fib_selecionadas.append(candidato)
                
                # Complementar com mix de estatísticas
                nao_fib = [num for num in self.numeros if num not in self.fibonacci]
                
                # Misturar não-Fibonacci: 50% quentes, 50% atrasados
                qtd_nao_fib = 15 - len(fib_selecionadas)
                qtd_quentes = qtd_nao_fib // 2
                qtd_atrasados = qtd_nao_fib - qtd_quentes
                
                # Calcular frequência e atraso
                janela = min(30, len(self.concursos))
                if janela < 10:
                    janela = min(10, len(self.concursos))
                freq_nao_fib = Counter()
                atraso_nao_fib = {}
                
                for num in nao_fib:
                    atraso_nao_fib[num] = len(self.concursos)
                    for idx, concurso in enumerate(self.concursos):
                        if num in concurso:
                            freq_nao_fib[num] += 1
                            if idx < atraso_nao_fib[num]:
                                atraso_nao_fib[num] = idx
                
                nao_fib_quentes = sorted(nao_fib, key=lambda x: freq_nao_fib[x], reverse=True)[:20]
                nao_fib_atrasados = sorted(nao_fib, key=lambda x: atraso_nao_fib[x], reverse=True)[:20]
                
                # Selecionar quentes únicos
                candidatos_quentes = [n for n in nao_fib_quentes if n not in fib_selecionadas]
                selecao_quentes = []
                if len(candidatos_quentes) >= qtd_quentes:
                    selecao_quentes = random.sample(candidatos_quentes, min(qtd_quentes, len(candidatos_quentes)))
                
                # Selecionar atrasados únicos
                candidatos_atrasados = [n for n in nao_fib_atrasados if n not in fib_selecionadas and n not in selecao_quentes]
                selecao_atrasados = []
                if len(candidatos_atrasados) >= qtd_atrasados:
                    selecao_atrasados = random.sample(candidatos_atrasados, min(qtd_atrasados, len(candidatos_atrasados)))
                
                cartao = sorted(fib_selecionadas + selecao_quentes + selecao_atrasados)
                
                # Ajustar tamanho se necessário (garantindo exclusividade)
                if len(cartao) > 15:
                    cartao = sorted(random.sample(cartao, 15))
                elif len(cartao) < 15:
                    faltam = 15 - len(cartao)
                    complemento = random.sample([n for n in self.numeros if n not in cartao], faltam)
                    cartao = sorted(cartao + complemento)
                
                # Verificar se tem números únicos e não é repetido
                if len(set(cartao)) == 15 and cartao not in cartoes:
                    cartoes.append(cartao)
                
                # Parar quando tiver cartões suficientes
                if len(cartoes) >= n_cartoes:
                    break
        
        # Se não gerou cartões suficientes, completar com método padrão
        if len(cartoes) < n_cartoes:
            cartoes.extend(self.gerar_cartoes_fibonacci(n_cartoes - len(cartoes), usar_estatisticas=True))
        
        return cartoes[:n_cartoes]
    
    def obter_relatorio_fibonacci(self):
        """Retorna relatório completo da análise Fibonacci"""
        stats = self.analisar_fibonacci()
        
        relatorio = {
            'dezenas_fibonacci': self.fibonacci,
            'estatisticas_gerais': {
                'media_fibonacci_por_concurso': stats.get('media_geral', 0),
                'moda_fibonacci_por_concurso': stats.get('moda_geral', 0),
                'min_fibonacci_por_concurso': stats.get('min_geral', 0),
                'max_fibonacci_por_concurso': stats.get('max_geral', 0),
                'concursos_analisados': min(50, len(self.concursos))
            },
            'frequencia_individual': stats.get('frequencia_fib', {}),
            'atraso_individual': stats.get('atraso_fib', {}),
            'distribuicao_historica': stats.get('media_por_concurso', [])
        }
        
        return relatorio


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
    # NOVOS: Fechamento
    if "fechamento_gerado" not in st.session_state:
        st.session_state.fechamento_gerado = []
    if "grupos_fechamento" not in st.session_state:
        st.session_state.grupos_fechamento = []
    if "analise_estatistica_avancada" not in st.session_state:
        st.session_state.analise_estatistica_avancada = None
    # NOVOS: Backtest e Híbrida
    if "resultados_backtest" not in st.session_state:
        st.session_state.resultados_backtest = None
    if "relatorio_backtest" not in st.session_state:
        st.session_state.relatorio_backtest = None
    if "cartoes_hibridos" not in st.session_state:
        st.session_state.cartoes_hibridos = []

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
                
                # Criar informações dos concursos para exibição
                concursos_info = {}
                total_concursos = len(concursos)
                for idx, concurso in enumerate(concursos):
                    # índice 0 = mais recente
                    numero_concurso = total_concursos - idx
                    concursos_info[idx] = {
                        "indice": idx,
                        "numero_concurso": f"Concurso {numero_concurso}",
                        "posicao": f"{idx+1}º mais recente" if idx == 0 else f"{idx+1}º após o mais recente",
                        "dezenas": concurso
                    }
                st.session_state.concursos_info = concursos_info
                
                st.success(f"{len(concursos)} concursos capturados com sucesso!")
                
                # Limpar dados antigos ao capturar novos concursos
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
                st.session_state.analise_estatistica_avancada = None
                # Limpar dados do backtest
                st.session_state.resultados_backtest = None
                st.session_state.relatorio_backtest = None
                st.session_state.cartoes_hibridos = []
            else:
                st.error("Não foi possível capturar concursos.")

# --- Abas principais ---
if st.session_state.concursos:
    # Verificar se tem pelo menos 10 concursos
    if len(st.session_state.concursos) < 10:
        st.warning("⚠️ São necessários pelo menos 10 concursos para análises precisas. Capture mais concursos.")
    
    # Inicializar todas as análises
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    jogos_gerados = ia.gerar_5_jogos(probs) if probs else []
    quentes_frios = ia.quentes_frios()
    pares_impares_primos = ia.pares_impares_primos()
    
    # Inicializar análise de sequência/falha
    analise_sf = AnaliseSequenciaFalha(st.session_state.concursos)
    
    # Inicializar análise estatística avançada
    analise_estatistica = AnaliseEstatisticaAvancada(st.session_state.concursos)
    
    # Inicializar fechamento
    fechamento = FechamentoLotofacil(st.session_state.concursos)
    
    # Abas atualizadas com nova aba de backtest
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
        "📊 Backtest & Hibrida"  # NOVA ABA
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
                    # Estatísticas rápidas do jogo
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
                ["balanceada", "conservadora", "agressiva", "aleatoria_padrao", "metodo_tabela"],
                help="""
                balanceada: 6 melhores + 5 médios + 4 retorno\n
                conservadora: 10 melhores + 5 médios\n
                agressiva: 5 melhores + 10 retorno\n
                aleatoria_padrao: Aleatória com padrões históricos\n
                metodo_tabela: Método original da tabela (8 melhores + 7 retorno)
                """
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
                    # Analisar estatísticas do jogo
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
            
            # Exportar combinações
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
                min_value=10,  # Ajustado para mínimo 10
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
        
        # Inicializar estratégia Fibonacci
        estrategia_fib = EstrategiaFibonacci(st.session_state.concursos)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔢 Dezenas Fibonacci")
            st.write(f"**7 Dezenas Fibonacci:** {estrategia_fib.fibonacci}")
            
            if st.button("📊 Analisar Estatísticas Fibonacci"):
                with st.spinner("Analisando desempenho das dezenas Fibonacci..."):
                    relatorio = estrategia_fib.obter_relatorio_fibonacci()
                    st.session_state.relatorio_fibonacci = relatorio
                    st.success("Análise Fibonacci concluída!")
        
        with col2:
            st.markdown("### 🎯 Configuração")
            estrategia = st.selectbox(
                "Selecione a estratégia de geração:",
                ["padrao", "fibonacci_quentes", "fibonacci_atrasados", "fibonacci_balanceado"],
                format_func=lambda x: {
                    "padrao": "Padrão (4-5 Fibonacci + estatísticas)",
                    "fibonacci_quentes": "Fibonacci Quentes + Não-Fibonacci Quentes",
                    "fibonacci_atrasados": "Fibonacci Atrasados + Não-Fibonacci Atrasados",
                    "fibonacci_balanceado": "Balanceado (mistura de estratégias)"
                }[x]
            )
            
            n_cartoes = st.slider("Número de cartões a gerar:", 1, 20, 10)
        
        # Mostrar relatório Fibonacci se existir
        if hasattr(st.session_state, 'relatorio_fibonacci') and st.session_state.relatorio_fibonacci:
            relatorio = st.session_state.relatorio_fibonacci
            
            st.markdown("### 📈 Estatísticas das Dezenas Fibonacci")
            
            # Tabela de frequência e atraso
            dados_tabela = []
            for num in estrategia_fib.fibonacci:
                dados_tabela.append({
                    "Número": num,
                    "Frequência (últimos concursos)": relatorio['frequencia_individual'].get(num, 0),
                    "Atraso (concursos)": relatorio['atraso_individual'].get(num, 0),
                    "Status": "🔥 Quente" if relatorio['frequencia_individual'].get(num, 0) > 10 else 
                             "⚠️ Média" if relatorio['frequencia_individual'].get(num, 0) > 5 else 
                             "❄️ Frio"
                })
            
            df_fib = pd.DataFrame(dados_tabela)
            st.dataframe(df_fib, hide_index=True)
            
            # Estatísticas gerais
            st.markdown("#### 📊 Estatísticas Gerais dos Fibonacci")
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric("Média por concurso", f"{relatorio['estatisticas_gerais']['media_fibonacci_por_concurso']:.1f}")
            with col_stat2:
                st.metric("Moda (mais comum)", relatorio['estatisticas_gerais']['moda_fibonacci_por_concurso'])
            with col_stat3:
                st.metric("Mínimo por concurso", relatorio['estatisticas_gerais']['min_fibonacci_por_concurso'])
            with col_stat4:
                st.metric("Máximo por concurso", relatorio['estatisticas_gerais']['max_fibonacci_por_concurso'])
            
            # Distribuição histórica
            if relatorio['distribuicao_historica']:
                st.markdown("#### 📊 Distribuição Histórica de Fibonacci por Concurso")
                dist_df = pd.DataFrame({
                    'Concursos': list(range(1, len(relatorio['distribuicao_historica'])+1)),
                    'Fibonacci no Concurso': relatorio['distribuicao_historica']
                })
                st.bar_chart(dist_df.set_index('Concursos'))
        
        st.markdown("---")
        st.markdown("### 🎰 Gerar Cartões Fibonacci")
        
        if st.button("🚀 Gerar Cartões com Estratégia Fibonacci", type="primary"):
            with st.spinner(f"Gerando {n_cartoes} cartões com estratégia Fibonacci..."):
                if estrategia == "padrao":
                    cartoes_fib = estrategia_fib.gerar_cartoes_fibonacci(n_cartoes, usar_estatisticas=True)
                else:
                    cartoes_fib = estrategia_fib.gerar_cartoes_fibonacci_estrategia(estrategia, n_cartoes)
                
                st.session_state.cartoes_fibonacci = cartoes_fib
                st.success(f"{len(cartoes_fib)} cartões Fibonacci gerados com sucesso!")
        
        # Mostrar cartões gerados
        if hasattr(st.session_state, 'cartoes_fibonacci') and st.session_state.cartoes_fibonacci:
            cartoes_fib = st.session_state.cartoes_fibonacci
            
            st.markdown(f"### 📋 Cartões Gerados ({estrategia.replace('_', ' ').title()})")
            
            # Estatísticas dos cartões
            stats_cartoes = []
            for i, cartao in enumerate(cartoes_fib, 1):
                # Contar Fibonacci no cartão
                fib_no_cartao = [num for num in cartao if num in estrategia_fib.fibonacci]
                qtd_fib = len(fib_no_cartao)
                
                # Outras estatísticas
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
            
            # Exibir como DataFrame
            df_cartoes_fib = pd.DataFrame(stats_cartoes)
            st.dataframe(df_cartoes_fib, hide_index=True, use_container_width=True)
            
            # Detalhes expandidos
            with st.expander("🔍 Ver Detalhes de Cada Cartão"):
                for i, cartao in enumerate(cartoes_fib, 1):
                    fib_no_cartao = [num for num in cartao if num in estrategia_fib.fibonacci]
                    qtd_fib = len(fib_no_cartao)
                    pares = sum(1 for n in cartao if n % 2 == 0)
                    primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
                    soma = sum(cartao)
                    
                    col_c1, col_c2 = st.columns([3, 2])
                    with col_c1:
                        st.write(f"**Cartão {i}:** {cartao}")
                        st.write(f"**Fibonacci ({qtd_fib}):** {fib_no_cartao}")
                    with col_c2:
                        st.write(f"**Estatísticas:**")
                        st.write(f"- Fibonacci: {qtd_fib}/15")
                        st.write(f"- Pares/Ímpares: {pares}/{15-pares}")
                        st.write(f"- Primos: {primos}")
                        st.write(f"- Soma: {soma}")
                    
                    # Verificar se segue a regra (4 ou 5 Fibonacci)
                    if qtd_fib in [4, 5]:
                        st.success(f"✅ Segue a regra: {qtd_fib} números Fibonacci")
                    else:
                        st.warning(f"⚠️ Não segue a regra: {qtd_fib} números Fibonacci (deveria ser 4 ou 5)")
                    
                    st.write("---")
            
            # Exportar cartões
            st.markdown("### 💾 Exportar Cartões Fibonacci")
            conteudo_fib = "\n".join(",".join(str(n) for n in cartao) for cartao in cartoes_fib)
            st.download_button(
                "📥 Baixar Cartões Fibonacci", 
                data=conteudo_fib, 
                file_name=f"cartoes_fibonacci_{estrategia}.txt", 
                mime="text/plain"
            )
            
            # Adicionar estatísticas de exportação
            st.info(f"""
            **Resumo da geração:**
            - Total de cartões: {len(cartoes_fib)}
            - Estratégia: {estrategia.replace('_', ' ').title()}
            - Fibonacci por cartão: 4 ou 5 (regra da estratégia)
            - Cartões únicos e balanceados
            """)

    # Aba 8 - Fechamentos Matemáticos
    with abas[7]:
        st.subheader("🎲 Fechamentos Matemáticos - Desdobramentos")
        st.write("Gere múltiplos cartões a partir de um grupo maior de números (ex: 18 números) para aumentar a cobertura e garantia de acertos.")
        
        if len(st.session_state.concursos) < 10:
            st.warning("⚠️ São necessários pelo menos 10 concursos para análises precisas de fechamento.")
        
        col_config1, col_config2 = st.columns(2)
        
        with col_config1:
            st.markdown("### ⚙️ Configuração do Fechamento")
            
            # Opção: usar grupos sugeridos ou personalizados
            modo_grupo = st.radio(
                "Selecione o modo de escolha dos números:",
                ["Usar grupos sugeridos pela IA", "Inserir números manualmente"]
            )
            
            tamanho_grupo = st.slider(
                "Tamanho do grupo de números para fechamento:",
                min_value=16,
                max_value=20,
                value=18,
                step=1,
                help="Quantos números selecionar para gerar os cartões de 15 números"
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
                ["cobertura", "estatistica"],
                format_func=lambda x: "Cobertura sistemática" if x == "cobertura" else "Baseada em estatísticas"
            )
        
        with col_config2:
            st.markdown("### 📊 Análise para Sugestões")
            
            if st.button("🔍 Analisar para Sugestões de Grupos"):
                with st.spinner("Analisando estatísticas para sugestões de grupos..."):
                    grupos_sugeridos = fechamento.analisar_grupos_otimos(tamanho_grupo, analise_concursos=30)
                    st.session_state.grupos_fechamento = grupos_sugeridos
                    st.success(f"{len(grupos_sugeridos)} grupos sugeridos gerados!")
        
        # Mostrar grupos sugeridos
        if st.session_state.grupos_fechamento:
            st.markdown("### 🎯 Grupos Sugeridos para Fechamento")
            
            for i, grupo in enumerate(st.session_state.grupos_fechamento, 1):
                col_g1, col_g2 = st.columns([3, 1])
                with col_g1:
                    st.write(f"**Grupo {i} ({len(grupo)} números):** {grupo}")
                with col_g2:
                    if st.button(f"Usar Grupo {i}", key=f"usar_grupo_{i}"):
                        grupo_selecionado = grupo
        
        # Seleção de números manual
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
        
        # Gerar fechamento
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
                        
                        # Calcular cobertura
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
        
        # Mostrar resultados do fechamento
        if st.session_state.fechamento_gerado:
            jogos_fechamento = st.session_state.fechamento_gerado
            
            st.markdown(f"### 📋 Fechamento Gerado ({len(jogos_fechamento)} jogos)")
            
            # Estatísticas do fechamento
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
                
                # Tabela de cobertura por número
                with st.expander("📈 Ver Cobertura Detalhada por Número"):
                    dados_cobertura = []
                    for num, info in cobertura['cobertura_por_numero'].items():
                        dados_cobertura.append({
                            "Número": num,
                            "Frequência": info['frequencia'],
                            "Cobertura (%)": info['percentual'],
                            "Status": "✅ Boa" if info['percentual'] >= 50 else "⚠️ Média" if info['percentual'] >= 30 else "❌ Baixa"
                        })
                    
                    df_cobertura = pd.DataFrame(dados_cobertura)
                    df_cobertura = df_cobertura.sort_values("Cobertura (%)", ascending=False)
                    st.dataframe(df_cobertura, hide_index=True)
            
            # Lista de jogos
            st.markdown("#### 🎯 Jogos do Fechamento")
            
            # Mostrar primeiros 10 jogos
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
            
            # Exportar fechamento
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
            
            # Informações sobre a estratégia
            st.info(f"""
            **Resumo do Fechamento:**
            - Números no grupo: {len(grupo_selecionado)}
            - Jogos gerados: {len(jogos_fechamento)}
            - Cobertura média: {cobertura['cobertura_media'] if 'cobertura' in locals() else 'N/A'}%
            - Estratégia: {estrategia_fechamento}
            
            **Vantagens do fechamento:**
            1. Maior garantia de acertos (11-14 pontos)
            2. Cobertura mais ampla dos números escolhidos
            3. Redução do risco de sair sem prêmio
            """)

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
                # Cartões IA
                if st.session_state.cartoes_gerados:
                    st.markdown("### 🧠 Cartões Gerados por IA")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Jogo {i}: {cartao} - **{acertos} acertos**")
                
                # Cartões Sequência/Falha
                if st.session_state.jogos_sequencia_falha:
                    st.markdown("### 📈 Cartões Sequência/Falha")
                    for i, cartao in enumerate(st.session_state.jogos_sequencia_falha, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Jogo {i}: {cartao} - **{acertos} acertos**")
                
                # Cartões por Padrões
                if st.session_state.cartoes_gerados_padrao:
                    st.markdown("### 🧩 Cartões por Padrões")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados_padrao, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
                
                # Cartões Fibonacci
                if hasattr(st.session_state, 'cartoes_fibonacci') and st.session_state.cartoes_fibonacci:
                    st.markdown("### 🎯 Cartões Fibonacci")
                    for i, cartao in enumerate(st.session_state.cartoes_fibonacci, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        fib_no_cartao = [num for num in cartao if num in [1,2,3,5,8,13,21]]
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos** (Fibonacci: {len(fib_no_cartao)})")
                
                # Combinações Combinatorias
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
                
                # Fechamentos
                if st.session_state.fechamento_gerado:
                    st.markdown("### 🎲 Fechamentos Gerados")
                    for i, cartao in enumerate(st.session_state.fechamento_gerado[:5], 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Fechamento Jogo {i}: {cartao} - **{acertos} acertos**")
                    
                    if len(st.session_state.fechamento_gerado) > 5:
                        st.info(f"Mostrando 5 de {len(st.session_state.fechamento_gerado)} jogos do fechamento")
                
                # Cartões Híbridos
                if hasattr(st.session_state, 'cartoes_hibridos') and st.session_state.cartoes_hibridos:
                    st.markdown("### 🧬 Cartões Híbridos")
                    for i, cartao in enumerate(st.session_state.cartoes_hibridos, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão Híbrido {i}: {cartao} - **{acertos} acertos**")

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
        
        # Configuração do limite de concursos
        st.markdown("### ⚙️ Configuração da Análise de Ciclos")
        
        col_config1, col_config2 = st.columns([2, 1])
        
        with col_config1:
            # Slider para escolher quantos concursos analisar
            max_concursos_disponiveis = len(st.session_state.concursos)
            limite_ciclos = st.slider(
                "Número de concursos anteriores para análise:",
                min_value=10,  # Ajustado para mínimo 10
                max_value=min(50, max_concursos_disponiveis),
                value=st.session_state.limite_ciclos or 15,
                step=1,
                help="Quantos concursos mais recentes analisar para detectar o ciclo atual"
            )
            
            # Opção para incluir todas as dezenas faltantes
            incluir_todas_faltantes = st.checkbox(
                "Forçar inclusão de todas as dezenas faltantes nos cartões",
                value=False,
                help="Se marcado, garantirá que todas as dezenas que ainda não saíram no ciclo sejam incluídas nos cartões gerados"
            )
        
        with col_config2:
            st.metric("Concursos Disponíveis", max_concursos_disponiveis)
            if limite_ciclos:
                st.metric("Concursos a Analisar", limite_ciclos)
        
        # Botão para aplicar configurações e analisar
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
        
        # Mostrar estatísticas do ciclo se existir
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
            
            # Detalhes do ciclo
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
                
                # Informação sobre o limite
                if resumo.get("limite_concursos"):
                    st.write(f"**Limite de análise:** {resumo['limite_concursos']} concursos")
                    if not resumo["ciclo_completo"] and resumo["tamanho"] >= resumo["limite_concursos"]:
                        st.warning(f"⚠️ O ciclo não foi completado dentro do limite de {resumo['limite_concursos']} concursos analisados.")
            
            # Concursos Analisados no Ciclo
            with st.expander("📊 Concursos Analisados no Ciclo", expanded=True):
                st.write(f"### 🗂️ Concursos considerados (últimos {limite_ciclos if st.session_state.limite_ciclos else resumo['tamanho']})")
                st.write("(Ordenados do mais recente para o mais antigo)")
                
                concursos_no_ciclo = analise_ciclos.obter_concursos_no_ciclo_formatados()
                
                if concursos_no_ciclo:
                    # Criar DataFrame para exibição
                    dados_concursos = []
                    for concurso_info in concursos_no_ciclo:
                        dados_concursos.append({
                            "Ordem": concurso_info["ordem"],
                            "Concurso": concurso_info["numero_concurso"],
                            "Posição": f"{concurso_info['ordem']}º mais recente",
                            "Dezenas": ", ".join(str(d) for d in concurso_info["dezenas"]),
                            "Total Dezenas": len(concurso_info["dezenas"])
                        })
                    
                    df_concursos = pd.DataFrame(dados_concursos)
                    st.dataframe(df_concursos, hide_index=True, use_container_width=True)
                    
                    # Estatísticas dos concursos no ciclo
                    st.write("### 📈 Estatísticas dos Concursos no Ciclo")
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Total Concursos", len(concursos_no_ciclo))
                    with col_stat2:
                        # Média de dezenas por concurso (deve ser 15)
                        media_dezenas = np.mean([len(c["dezenas"]) for c in concursos_no_ciclo])
                        st.metric("Média Dezenas/Concurso", f"{media_dezenas:.1f}")
                    with col_stat3:
                        # Dezenas únicas totais
                        dezenas_unicas = len(resumo["numeros_presentes"])
                        st.metric("Dezenas Únicas", dezenas_unicas)
                    
                    # Gráfico de evolução do ciclo
                    st.write("### 📊 Evolução das Dezenas por Concurso")
                    dezenas_acumuladas = []
                    dezenas_unicas_acum = []
                    for i, concurso_info in enumerate(concursos_no_ciclo, 1):
                        dezenas_ate_agora = set()
                        for j in range(i):
                            dezenas_ate_agora.update(concursos_no_ciclo[j-1]["dezenas"])
                        dezenas_acumuladas.append(len(concursos_no_ciclo[i-1]["dezenas"]))
                        dezenas_unicas_acum.append(len(dezenas_ate_agora))
                    
                    evolucao_df = pd.DataFrame({
                        "Concurso": [f"Concurso {i}" for i in range(1, len(concursos_no_ciclo)+1)],
                        "Dezenas no Concurso": dezenas_acumuladas,
                        "Dezenas Únicas Acumuladas": dezenas_unicas_acum
                    })
                    
                    st.line_chart(evolucao_df.set_index("Concurso"))
                    
                else:
                    st.warning("Nenhum concurso foi analisado para o ciclo.")
            
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
                    analise_ciclos = st.session_state.analise_ciclos
                    st.session_state.resultado_ciclos = analise_ciclos.resumo()
                    st.session_state.cartoes_ciclos = []
                    st.success("Ciclo reanalisado com sucesso!")
                    st.rerun()
            
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
            
            # Mostrar cartões gerados
            if st.session_state.cartoes_ciclos:
                st.subheader("📋 Cartões Gerados (Priorizando Dezenas do Ciclo)")
                
                # Verificar se os cartões são distintos
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
                
                # Se ainda não tem 5 cartões distintos, completar
                while len(st.session_state.cartoes_ciclos) < 5:
                    novo_cartao = sorted(random.sample(range(1, 26), 15))
                    if tuple(novo_cartao) not in cartoes_vistos:
                        cartoes_vistos.add(tuple(novo_cartao))
                        st.session_state.cartoes_ciclos.append(novo_cartao)
                
                st.success(f"✅ Gerados {len(st.session_state.cartoes_ciclos)} cartões distintos!")
                
                if incluir_todas_faltantes and resumo["numeros_faltantes"]:
                    st.info(f"✅ Configuração ativa: Incluindo todas as {len(resumo['numeros_faltantes'])} dezenas faltantes nos cartões.")
                
                # Tabela de estatísticas dos cartões
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
                
                # Exibir como DataFrame
                df_cartoes = pd.DataFrame(stats_cartoes)
                st.dataframe(df_cartoes, hide_index=True, use_container_width=True)
                
                # Detalhes expandidos de cada cartão
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
                
                # Botão para exportar
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
            
            # Exemplo de como funciona
            with st.expander("ℹ️ Como funciona a análise de ciclos?"):
                st.write("""
                **Análise de Ciclos da Lotofácil:**
                
                1. **Coleta de dados**: Analisa os concursos mais recentes (você escolhe quantos)
                2. **Detecção de ciclo**: Verifica quantos concursos são necessários para que todas as 25 dezenas apareçam pelo menos uma vez
                3. **Identificação**: Separa as dezenas que já saíram (presentes) e as que ainda não saíram (faltantes) no ciclo atual
                4. **Geração de cartões**: Cria jogos priorizando as dezenas faltantes e as que têm maior atraso
                
                **Benefícios:**
                - Identifica dezenas "atrasadas" que têm maior probabilidade de sair
                - Ajuda a diversificar os jogos incluindo dezenas que estão em falta
                - Fornece uma visão dinâmica do comportamento das dezenas ao longo do tempo
                
                **Recomendações:**
                - Analise entre 10 e 25 concursos para um bom equilíbrio
                - Se o ciclo estiver "Atrasado", as dezenas faltantes têm alta prioridade
                - Use a opção "Incluir todas as faltantes" para garantir cobertura máxima
                """)

    # Aba 12 - Backtest & Estratégia Híbrida (NOVA ABA)
    with abas[11]:
        st.subheader("📊 Backtest de Estratégias & Estratégia Híbrida")
        
        # Inicializar backtest
        backtester = BacktestEstrategias(st.session_state.concursos)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🔬 Backtest Científico")
            st.write("Testa todas as estratégias contra concursos passados para medir performance real.")
            
            concursos_testar = st.slider(
                "Número de concursos para testar:",
                min_value=20,
                max_value=min(100, len(st.session_state.concursos) - 50),
                value=50,
                step=5,
                help="Quantos concursos passados usar como 'teste'"
            )
            
            if st.button("🚀 Executar Backtest Completo", type="primary"):
                with st.spinner(f"Executando backtest com {concursos_testar} concursos..."):
                    resultados = backtester.executar_backtest_completo(concursos_testar)
                    
                    if "erro" in resultados:
                        st.error(resultados["erro"])
                    else:
                        st.session_state.resultados_backtest = resultados
                        
                        # Gerar relatório
                        relatorio = backtester.gerar_relatorio_backtest(resultados)
                        st.session_state.relatorio_backtest = relatorio
                        
                        st.success(f"Backtest concluído! {len(resultados)} estratégias analisadas.")
        
        with col2:
            st.markdown("### 🎯 Estratégia Híbrida")
            st.write("Combinação otimizada das melhores abordagens.")
            
            if st.button("🧬 Gerar 5 Cartões Híbridos"):
                with st.spinner("Gerando cartões com estratégia híbrida..."):
                    cartoes_hibridos = backtester._gerar_estrategia_hibrida(st.session_state.concursos[:50])
                    st.session_state.cartoes_hibridos = cartoes_hibridos
                    st.success("5 cartões híbridos gerados!")
        
        # Mostrar resultados do backtest
        if hasattr(st.session_state, 'resultados_backtest') and st.session_state.resultados_backtest:
            resultados = st.session_state.resultados_backtest
            
            st.markdown("### 📈 Resultados do Backtest")
            
            # Criar DataFrame para visualização
            dados_grafico = []
            for estrategia, stats in resultados.items():
                dados_grafico.append({
                    'Estratégia': estrategia.replace('_', ' '),
                    'Pontuação Média': stats['pontuacao_media'],
                    '13+ Pontos %': stats['taxa_13_plus'],
                    '14 Pontos %': stats['taxa_14_pontos'] * 100,  # Multiplicado para visualização
                    '11 Pontos %': stats['taxa_11_pontos']
                })
            
            df_backtest = pd.DataFrame(dados_grafico)
            
            # Gráfico de comparação
            st.markdown("#### 📊 Comparação de Pontuação Média")
            chart_data = df_backtest.set_index('Estratégia')[['Pontuação Média']]
            st.bar_chart(chart_data)
            
            # Tabela detalhada
            st.markdown("#### 📋 Estatísticas Detalhadas")
            st.dataframe(df_backtest, hide_index=True, use_container_width=True)
            
            # Mostrar relatório completo
            with st.expander("📄 Ver Relatório Completo do Backtest"):
                st.text(st.session_state.relatorio_backtest)
            
            # Download do relatório
            st.download_button(
                "💾 Baixar Relatório Completo",
                data=st.session_state.relatorio_backtest,
                file_name=f"backtest_lotofacil_{len(st.session_state.concursos)}.txt",
                mime="text/plain"
            )
        
        # Mostrar cartões híbridos
        if hasattr(st.session_state, 'cartoes_hibridos') and st.session_state.cartoes_hibridos:
            st.markdown("### 🧬 Cartões Híbridos Gerados")
            st.info("Estratégia: 6 números quentes + 4 Fibonacci atrasados + 3 ciclos atrasados + 2 médios")
            
            for i, cartao in enumerate(st.session_state.cartoes_hibridos, 1):
                # Analisar composição
                fib_nums = [n for n in cartao if n in [1, 2, 3, 5, 8, 13, 21]]
                
                col_c1, col_c2 = st.columns([3, 2])
                with col_c1:
                    st.write(f"**Cartão {i}:** {cartao}")
                with col_c2:
                    pares = sum(1 for n in cartao if n % 2 == 0)
                    primos = sum(1 for n in cartao if n in {2,3,5,7,11,13,17,19,23})
                    st.write(f"Pares: {pares}, Primos: {primos}, Fibonacci: {len(fib_nums)}")
                    if fib_nums:
                        st.write(f"Fibonacci: {fib_nums}")
            
            # Exportar cartões híbridos
            conteudo_hibrido = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_hibridos)
            st.download_button(
                "📥 Baixar Cartões Híbridos",
                data=conteudo_hibrido,
                file_name="cartoes_hibridos_lotofacil.txt",
                mime="text/plain"
            )
        
        # Informações sobre a estratégia híbrida
        with st.expander("ℹ️ Sobre a Estratégia Híbrida"):
            st.write("""
            **🧬 Composição da Estratégia Híbrida:**
            
            1. **6 números quentes** - Baseado na análise de Sequência/Falha
               - Maior probabilidade estatística de repetição
            
            2. **4 números Fibonacci atrasados** - Foco em retorno estatístico
               - Dezenas Fibonacci (01,02,03,05,08,13,21) com maior atraso
            
            3. **3 números de ciclos atrasados** - Explora lacunas temporais
               - Números que não saem há mais tempo
            
            4. **2 números de média frequência** - Balanceamento estatístico
               - Evita foco excessivo em extremos
            
            **🎯 Vantagens:**
            - Diversificação estatística
            - Combina múltiplas abordagens comprovadas
            - Balanceamento automático pares/ímpares
            - Custo-efetivo (5 cartões = R$7,50)
            
            **📊 Expectativas Realistas (baseado em backtest):**
            - 11 pontos: ~20% dos jogos
            - 12 pontos: ~5% dos jogos  
            - 13 pontos: ~0.5-1% dos jogos
            - 14 pontos: ~0.01-0.05% dos jogos
            - 15 pontos: Chance estatisticamente irrelevante
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
    if hasattr(st.session_state, 'cartoes_hibridos') and st.session_state.cartoes_hibridos:
        st.write(f"Cartões Híbridos: {len(st.session_state.cartoes_hibridos)}")
    
    if hasattr(st.session_state, 'resultados_backtest') and st.session_state.resultados_backtest:
        st.write(f"Estratégias testadas: {len(st.session_state.resultados_backtest)}")
        # Mostrar a melhor estratégia
        melhor = list(st.session_state.resultados_backtest.items())[0] if st.session_state.resultados_backtest else None
        if melhor:
            st.write(f"Melhor estratégia: {melhor[0].replace('_', ' ')}")
            st.write(f"Pontuação média: {melhor[1]['pontuacao_media']:.1f}")
    
    # Informações sobre o ciclo atual na sidebar
    if st.session_state.analise_ciclos:
        st.markdown("### 🔁 Informações do Ciclo Atual")
        ciclo_resumo = st.session_state.analise_ciclos.resumo()
        st.write(f"**Status:** {ciclo_resumo['status']}")
        st.write(f"**Concursos analisados:** {ciclo_resumo['tamanho']}")
        st.write(f"**Dezenas faltantes:** {len(ciclo_resumo['numeros_faltantes'])}")
        if st.session_state.limite_ciclos:
            st.write(f"**Limite configurado:** {st.session_state.limite_ciclos} concursos")

st.markdown("<hr><p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
