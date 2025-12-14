

import streamlit as st
import requests
import numpy as np
import random
import pandas as pd
from collections import Counter
from catboost import CatBoostClassifier
import json
import io

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
# NOVA CLASSE: AnaliseCiclos (Ciclo Dinâmico Real) - MODIFICADA
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
        Gera n_cartoes=5 cartoes de 15 dezenas priorizando:
        1) Dezenas faltantes (incluir todas nas primeiras combinações quando possível)
        2) Dezenas com maior atraso dentro do ciclo
        3) Dezenas frequentes no ciclo (para balancear)
        4) Equilíbrio pares/impares e primos
        
        Parâmetro novo: incluir_todas_faltantes - força a inclusão de todas as dezenas faltantes nos cartões
        """
        if seed is not None:
            random.seed(seed)
        
        atraso = self.contar_atrasos_no_ciclo()
        # listas ordenadas por prioridade
        faltantes = sorted(list(self.numeros_faltantes))
        
        # Se o usuário quiser incluir todas as faltantes, distribuímos entre os cartões
        if incluir_todas_faltantes and faltantes:
            return self._gerar_cartoes_com_todas_faltantes(faltantes, n_cartoes, atraso)
        
        # ordena por atraso decrescente (maior atraso primeiro) -> ou seja, mais "pedidos"
        ordenado_por_atraso = sorted(list(self.TODAS), key=lambda x: atraso[x], reverse=True)
        # frequência dentro do ciclo - para completar
        freq = Counter()
        for concurso in self.ciclo_concursos:
            for n in concurso:
                freq[n] += 1
        ordenado_por_freq = sorted(list(self.TODAS), key=lambda x: freq.get(x,0), reverse=True)
        
        cartoes = []
        base_universe = list(self.TODAS)
        attempts = 0
        
        while len(cartoes) < n_cartoes and attempts < 500:
            attempts += 1
            card = set()
            
            # incluir algumas faltantes sempre que existirem (distribuir entre os cartões)
            if faltantes:
                # tentamos incluir uma porção das faltantes
                take_falt = min(len(faltantes), random.randint(1, min(8, len(faltantes))))
                escolhidas_falt = random.sample(faltantes, take_falt)
                card.update(escolhidas_falt)
            
            # adicionar números de alto atraso
            needed = 15 - len(card)
            candidatos_atraso = [n for n in ordenado_por_atraso if n not in card]
            if candidatos_atraso:
                to_add = min(needed, max(0, int(needed * 0.6)))
                escolha = random.sample(candidatos_atraso[:20], to_add) if len(candidatos_atraso[:20]) >= to_add else random.sample(candidatos_atraso, to_add)
                card.update(escolha)
            
            # completar por frequência
            needed = 15 - len(card)
            candidatos_freq = [n for n in ordenado_por_freq if n not in card]
            if candidatos_freq:
                choose_freq = random.sample(candidatos_freq[:20], min(needed, len(candidatos_freq[:20])))
                card.update(choose_freq)
            
            # se ainda faltar, completar aleatoriamente buscando equilíbrio par/impar
            while len(card) < 15:
                cand = random.choice(base_universe)
                if cand not in card:
                    card.add(cand)
            
            # checar paridade e primos; ajustar até obter equilíbrio mínimo
            self._ajustar_equilibrio(card, base_universe)
            
            cartao_sorted = sorted(list(card))
            if cartao_sorted not in cartoes:
                cartoes.append(cartao_sorted)
        
        # garantir que são n_cartoes cartoes distintos
        while len(cartoes) < n_cartoes:
            novo = sorted(random.sample(base_universe, 15))
            if novo not in cartoes:
                cartoes.append(novo)
        
        return cartoes
    
    def _gerar_cartoes_com_todas_faltantes(self, faltantes, n_cartoes, atraso):
        """Gera cartões garantindo que todas as dezenas faltantes sejam incluídas"""
        base_universe = list(self.TODAS)
        cartoes = []
        
        # Ordenar por atraso
        ordenado_por_atraso = sorted(list(self.TODAS), key=lambda x: atraso[x], reverse=True)
        
        # Se há muitas faltantes (>15), não podemos incluí-las todas em um único cartão
        # Nesse caso, distribuímos entre os cartões
        if len(faltantes) > 15:
            # Distribuir as faltantes entre os cartões
            for i in range(n_cartoes):
                card = set()
                # Pegar uma parte das faltantes para este cartão
                inicio = (i * len(faltantes)) // n_cartoes
                fim = ((i + 1) * len(faltantes)) // n_cartoes
                faltantes_para_cartao = faltantes[inicio:fim]
                
                if faltantes_para_cartao:
                    card.update(faltantes_para_cartao)
                
                # Completar com números de alto atraso
                needed = 15 - len(card)
                candidatos_atraso = [n for n in ordenado_por_atraso if n not in card]
                if candidatos_atraso and needed > 0:
                    to_add = min(needed, len(candidatos_atraso))
                    escolha = random.sample(candidatos_atraso[:max(10, to_add)], to_add)
                    card.update(escolha)
                
                # Completar se necessário
                while len(card) < 15:
                    cand = random.choice([n for n in base_universe if n not in card])
                    card.add(cand)
                
                self._ajustar_equilibrio(card, base_universe)
                cartoes.append(sorted(list(card)))
        else:
            # Se há 15 ou menos faltantes, podemos incluí-las todas no primeiro cartão
            # e distribuir nos demais
            for i in range(n_cartoes):
                card = set()
                
                if i == 0:
                    # Primeiro cartão inclui todas as faltantes
                    card.update(faltantes)
                else:
                    # Outros cartões incluem algumas faltantes
                    if faltantes:
                        take_falt = min(len(faltantes), random.randint(1, len(faltantes)//2))
                        escolhidas_falt = random.sample(faltantes, take_falt)
                        card.update(escolhidas_falt)
                
                # Completar
                needed = 15 - len(card)
                if needed > 0:
                    candidatos_atraso = [n for n in ordenado_por_atraso if n not in card]
                    if candidatos_atraso:
                        to_add = min(needed, len(candidatos_atraso))
                        escolha = random.sample(candidatos_atraso[:max(10, to_add)], to_add)
                        card.update(escolha)
                
                while len(card) < 15:
                    cand = random.choice([n for n in base_universe if n not in card])
                    card.add(cand)
                
                self._ajustar_equilibrio(card, base_universe)
                cartoes.append(sorted(list(card)))
        
        return cartoes
    
    def _ajustar_equilibrio(self, card, base_universe):
        """Ajusta o equilíbrio de pares/ímpares no cartão"""
        pares = sum(1 for n in card if n%2==0)
        if pares < 6:
            # trocar um ímpar por um par disponível
            poss_pares = [n for n in base_universe if n%2==0 and n not in card]
            poss_impares = [n for n in card if n%2==1]
            if poss_pares and poss_impares:
                card.remove(random.choice(poss_impares))
                card.add(random.choice(poss_pares))
        elif pares > 10:
            poss_impares = [n for n in base_universe if n%2==1 and n not in card]
            poss_pares_in = [n for n in card if n%2==0]
            if poss_impares and poss_pares_in:
                card.remove(random.choice(poss_pares_in))
                card.add(random.choice(poss_impares))
    
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
        if len(concursos) > 1:
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
        if len(self.concursos) < 2:
            return np.array([])
        freq = self.frequencia(janela=len(self.concursos)-1)
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
            freq = self.frequencia(janela=50)
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
        janela = min(janela, len(self.concursos))
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

# =========================
# ESTRATÉGIA FIBONACCI - CORRIGIDA
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
            
        # Analisar últimos 50 concursos (ou menos se não houver)
        janela = min(50, len(self.concursos))
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
        st.session_state.limite_ciclos = None  # Novo: limite de concursos para análise de ciclos
    if "cartoes_fibonacci" not in st.session_state:
        st.session_state.cartoes_fibonacci = []
    if "relatorio_fibonacci" not in st.session_state:
        st.session_state.relatorio_fibonacci = None

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
            else:
                st.error("Não foi possível capturar concursos.")

# --- Abas principais ---
if st.session_state.concursos:
    # Inicializar todas as análises
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    jogos_gerados = ia.gerar_5_jogos(probs) if probs else []
    quentes_frios = ia.quentes_frios()
    pares_impares_primos = ia.pares_impares_primos()
    
    # Inicializar análise de sequência/falha
    analise_sf = AnaliseSequenciaFalha(st.session_state.concursos)
    
    # Abas
    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões IA", 
        "📈 Método Sequência/Falha",
        "🔢 Análises Combinatórias",
        "🧩 Gerar Cartões por Padrões",
        "📐 Padrões Linha×Coluna",
        "🎯 Estratégia Fibonacci",
        "✅ Conferência", 
        "📤 Conferir Arquivo TXT",
        "🔁 Ciclos da Lotofácil"
    ])

    # Aba 1 - Estatísticas
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Números quentes: {quentes_frios['quentes']}")
        st.write(f"Números frios: {quentes_frios['frios']}")
        st.write(f"Pares/Ímpares/Primos último concurso: {pares_impares_primos}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Frequência últimos 50 concursos:**")
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
        if st.button("🚀 Gerar 5 Cartões com IA"):
            st.session_state.cartoes_gerados = jogos_gerados
            st.success("5 Cartões gerados com sucesso pela IA!")
        
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
        janela_padrao = st.slider("Janela (nº de concursos recentes)", 5, 100, 10, 5)
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
                min_value=20, 
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
                    "Frequência (últimos 50)": relatorio['frequencia_individual'].get(num, 0),
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

    # Aba 8 - Conferência
    with abas[7]:
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

    # Aba 9 - Conferir Arquivo TXT
    with abas[8]:
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

    # Aba 10 - Ciclos da Lotofácil
    with abas[9]:
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
                min_value=3,
                max_value=min(50, max_concursos_disponiveis),
                value=st.session_state.limite_ciclos or 10,
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
                - Analise entre 5 e 25 concursos para um bom equilíbrio
                - Se o ciclo estiver "Atrasado", as dezenas faltantes têm alta prioridade
                - Use a opção "Incluir todas as faltantes" para garantir cobertura máxima
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
