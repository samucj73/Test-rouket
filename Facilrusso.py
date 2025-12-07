import streamlit as st
import requests
import numpy as np
import random
from collections import Counter
from catboost import CatBoostClassifier
import itertools
import math
import json
from datetime import datetime  # ADICIONADO: importação faltando

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
        dezenas = sorted([int(d) for d in ultimo.get("dezenas")])
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
                    dezenas_i = sorted([int(d) for d in data_i.get("dezenas")])
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
# NOVA CLASSE: Gerador de Cartões com Regras Específicas
# =========================
class GeradorCartoesRegrasEspecificas:
    def __init__(self, probabilidades):
        self.probabilidades = probabilidades
        self.numeros = list(range(1, 26))
        
        # Definir as regras específicas da imagem
        self.regras = {
            1: {"min": 1, "max": 1, "nome": "1 Dezena", "total_numeros": 1},
            2: {"min": 1, "max": 2, "nome": "2 Dezenas", "total_numeros": 2},
            3: {"min": 1, "max": 3, "nome": "3 Dezenas", "total_numeros": 3},
            4: {"min": 1, "max": 2, "nome": "4 Dezenas", "total_numeros": 4},
            5: {"min": 1, "max": 1, "nome": "5 Dezenas", "total_numeros": 5}
        }
    
    def determinar_tipo_automatico(self):
        """
        Determina automaticamente quantas dezenas por linha usar
        baseado nas estatísticas
        """
        # Ordenar números por probabilidade
        numeros_ordenados = sorted(self.probabilidades.items(), 
                                  key=lambda x: x[1], 
                                  reverse=True)
        
        valores_probabilidade = [prob for _, prob in numeros_ordenados]
        media = np.mean(valores_probabilidade)
        desvio = np.std(valores_probabilidade)
        
        # Top números
        top1_prob = numeros_ordenados[0][1]
        top5_prob_avg = np.mean([prob for _, prob in numeros_ordenados[:5]])
        
        # Decisão baseada na distribuição:
        
        # 1. Se há 1 número MUITO destacado
        if top1_prob > media + (desvio * 2.5):
            return 1  # 1 Dezena - foco no número mais forte
        
        # 2. Se há 2 números muito fortes
        elif numeros_ordenados[1][1] > media + (desvio * 1.8):
            return 2  # 2 Dezenas - par forte
        
        # 3. Se há 3 números bem destacados
        elif numeros_ordenados[2][1] > media + (desvio * 1.2):
            return 3  # 3 Dezenas - trio forte
        
        # 4. Se há 4-5 números consistentes
        elif top5_prob_avg > media:
            if desvio < 0.07:  # Baixa variação
                return 5  # 5 Dezenas - muitos números consistentes
            else:
                return 4  # 4 Dezenas - grupo consistente
        
        # 5. Padrão default
        else:
            return 3  # 3 Dezenas - opção mais equilibrada
    
    def determinar_num_linhas_automatico(self, tipo_dezenas):
        """
        Determina quantas linhas gerar baseado no tipo de dezenas
        e nas estatísticas
        """
        regra = self.regras[tipo_dezenas]
        
        # Se só pode ter 1 linha
        if regra["min"] == regra["max"]:
            return 1
        
        # Calcular consistência das probabilidades
        valores_probabilidade = [prob for _, prob in self.probabilidades.items()]
        desvio = np.std(valores_probabilidade)
        
        if tipo_dezenas == 2:
            # Para 2 dezenas: 1 ou 2 linhas
            numeros_ordenados = sorted(self.probabilidades.items(), 
                                      key=lambda x: x[1], 
                                      reverse=True)
            # Se os 4 primeiros são muito fortes, fazer 2 linhas
            top4_avg = np.mean([prob for _, prob in numeros_ordenados[:4]])
            if top4_avg > np.mean(valores_probabilidade) * 1.15:
                return 2
            else:
                return 1
        
        elif tipo_dezenas == 3:
            # Para 3 dezenas: 1, 2 ou 3 linhas
            if desvio < 0.06:
                return 3  # Alta consistência
            elif desvio < 0.1:
                return 2  # Média consistência
            else:
                return 1  # Baixa consistência
        
        elif tipo_dezenas == 4:
            # Para 4 dezenas: 1 ou 2 linhas
            numeros_ordenados = sorted(self.probabilidades.items(), 
                                      key=lambda x: x[1], 
                                      reverse=True)
            # Se os 8 primeiros são bons, fazer 2 linhas
            top8_avg = np.mean([prob for _, prob in numeros_ordenados[:8]])
            if top8_avg > np.mean(valores_probabilidade) * 1.1:
                return 2
            else:
                return 1
        
        return regra["min"]  # Default
    
    def selecionar_melhores_numeros(self, quantidade):
        """Seleciona a quantidade especificada de melhores números"""
        numeros_ordenados = sorted(self.probabilidades.items(), 
                                  key=lambda x: x[1], 
                                  reverse=True)
        return [n for n, _ in numeros_ordenados[:quantidade]]
    
    def distribuir_15_numeros_em_linhas(self, tipo_dezenas, num_linhas):
        """
        Distribui 15 números em linhas seguindo exatamente as regras
        
        Cada linha tem 'tipo_dezenas' números
        Total de linhas: 'num_linhas'
        Total números: tipo_dezenas × num_linhas = 15
        """
        # Verificar se a combinação é válida
        total_numeros = tipo_dezenas * num_linhas
        if total_numeros != 15:
            raise ValueError(f"Combinação inválida: {tipo_dezenas} dezenas × {num_linhas} linhas = {total_numeros} números (deveria ser 15)")
        
        # Selecionar os 15 melhores números
        melhores_15 = self.selecionar_melhores_numeros(15)
        
        # Distribuir em linhas
        linhas = []
        for i in range(num_linhas):
            inicio = i * tipo_dezenas
            fim = inicio + tipo_dezenas
            linha = melhores_15[inicio:fim]
            linhas.append(sorted(linha))
        
        return {
            "tipo_dezenas": tipo_dezenas,
            "num_linhas": num_linhas,
            "melhores_15": melhores_15,
            "linhas": linhas,
            "distribuicao": self.calcular_distribuicao(linhas)
        }
    
    def encontrar_combinacao_valida(self):
        """
        Encontra uma combinação válida de tipo_dezenas × num_linhas = 15
        que siga as regras da imagem
        """
        combinacoes_validas = []
        
        # Gerar todas combinações possíveis que dão 15 números
        for tipo in [1, 2, 3, 4, 5]:
            regra = self.regras[tipo]
            for linhas in range(regra["min"], regra["max"] + 1):
                if tipo * linhas == 15:
                    combinacoes_validas.append((tipo, linhas))
        
        # Se não encontrou combinação exata, usar a mais próxima
        if not combinacoes_validas:
            # Encontrar a combinação mais próxima de 15
            melhor_combinacao = None
            menor_diferenca = float('inf')
            
            for tipo in [1, 2, 3, 4, 5]:
                regra = self.regras[tipo]
                for linhas in range(regra["min"], regra["max"] + 1):
                    total = tipo * linhas
                    diferenca = abs(15 - total)
                    if diferenca < menor_diferenca:
                        menor_diferenca = diferenca
                        melhor_combinacao = (tipo, linhas, total)
            
            # Usar a melhor combinação encontrada
            tipo, linhas, total = melhor_combinacao
            
            # Ajustar: se total < 15, adicionar números extras
            # se total > 15, remover alguns números
            return tipo, linhas, total
        
        # Escolher a melhor combinação baseado nas estatísticas
        # Prioridade: 3×5, 5×3, 1×15, etc.
        combinacoes_priorizadas = [(3, 5), (5, 3), (1, 15), (15, 1)]
        
        for priorizada in combinacoes_priorizadas:
            if priorizada in combinacoes_validas:
                return priorizada[0], priorizada[1], 15
        
        # Se não encontrou priorizada, pegar a primeira
        tipo, linhas = combinacoes_validas[0]
        return tipo, linhas, 15
    
    def calcular_distribuicao(self, linhas):
        """Calcula distribuição estatística das linhas"""
        distribuicao = []
        for i, linha in enumerate(linhas, 1):
            # Estatísticas da linha
            pares = sum(1 for n in linha if n % 2 == 0)
            primos = sum(1 for n in linha if n in {2,3,5,7,11,13,17,19,23})
            soma = sum(linha)
            prob_media = np.mean([self.probabilidades.get(n, 0) for n in linha])
            prob_total = sum([self.probabilidades.get(n, 0) for n in linha])
            
            distribuicao.append({
                "linha": i,
                "numeros": linha,
                "pares": pares,
                "impares": len(linha) - pares,
                "primos": primos,
                "soma": soma,
                "probabilidade_media": prob_media,
                "probabilidade_total": prob_total
            })
        
        return distribuicao
    
    def gerar_cartao_completo(self):
        """
        Gera um cartão completo com 15 números distribuídos em linhas
        que seguem exatamente as regras da imagem
        """
        # 1. Determinar tipo automaticamente
        tipo_dezenas = self.determinar_tipo_automatico()
        
        # 2. Determinar número de linhas automaticamente
        num_linhas = self.determinar_num_linhas_automatico(tipo_dezenas)
        
        # 3. Verificar se a combinação dá 15 números
        total_numeros = tipo_dezenas * num_linhas
        
        if total_numeros != 15:
            # Encontrar combinação válida
            tipo_dezenas, num_linhas, total_numeros = self.encontrar_combinacao_valida()
        
        # 4. Distribuir os 15 números em linhas
        resultado = self.distribuir_15_numeros_em_linhas(tipo_dezenas, num_linhas)
        
        # 5. Calcular cartão completo (todos os 25 números)
        todos_numeros = list(range(1, 26))
        numeros_marcados = resultado["melhores_15"]
        
        cartao_completo = []
        for i in range(5):
            linha_cartao = []
            for j in range(5):
                numero = i * 5 + j + 1
                if numero in numeros_marcados:
                    # Verificar em qual linha da regra está
                    linha_regra = None
                    for idx, linha_nums in enumerate(resultado["linhas"]):
                        if numero in linha_nums:
                            linha_regra = idx + 1
                            break
                    
                    if linha_regra:
                        linha_cartao.append(f"[{numero:2d}]L{linha_regra}")
                    else:
                        linha_cartao.append(f"[{numero:2d}]   ")
                else:
                    linha_cartao.append(f" {numero:2d}   ")
            cartao_completo.append(linha_cartao)
        
        resultado["cartao_completo"] = cartao_completo
        
        return resultado
    
    def formatar_para_download(self, resultado):
        """Formata resultado para download"""
        tipo = resultado["tipo_dezenas"]
        linhas = resultado["num_linhas"]
        regra = self.regras[tipo]
        
        conteudo = "=" * 70 + "\n"
        conteudo += "LOTOFÁCIL - CARTÃO COM REGRAS ESPECÍFICAS\n"
        conteudo += "=" * 70 + "\n\n"
        
        conteudo += f"REGRAS APLICADAS:\n"
        conteudo += f"- Tipo: {regra['nome']}\n"
        conteudo += f"- Linhas: {linhas}\n"
        conteudo += f"- Números por linha: {tipo}\n"
        conteudo += f"- Total números: {tipo * linhas}\n"
        conteudo += f"- Regra: {regra['nome']} - {regra['min']} a {regra['max']} linha(s)\n\n"
        
        conteudo += "MELHORES 15 NÚMEROS (ORDENADOS POR PROBABILIDADE):\n"
        for i, num in enumerate(resultado["melhores_15"], 1):
            prob = self.probabilidades.get(num, 0)
            conteudo += f"{i:2d}. Número {num:2d}: {prob:.2%}\n"
        
        conteudo += "\n" + "=" * 70 + "\n"
        conteudo += "DISTRIBUIÇÃO NAS LINHAS:\n"
        conteudo += "=" * 70 + "\n\n"
        
        for dist in resultado["distribuicao"]:
            conteudo += f"LINHA {dist['linha']} ({len(dist['numeros'])} números):\n"
            conteudo += f"Números: {dist['numeros']}\n"
            conteudo += f"Pares: {dist['pares']} | Ímpares: {dist['impares']} "
            conteudo += f"| Primos: {dist['primos']} | Soma: {dist['soma']}\n"
            conteudo += f"Prob. média: {dist['probabilidade_media']:.2%} | Prob. total: {dist['probabilidade_total']:.2%}\n\n"
        
        conteudo += "=" * 70 + "\n"
        conteudo += "CARTÃO COMPLETO DA LOTOFÁCIL (L1, L2, ... = Linha da regra):\n"
        conteudo += "=" * 70 + "\n\n"
        
        for linha in resultado["cartao_completo"]:
            conteudo += " ".join(linha) + "\n"
        
        # Estatísticas gerais
        conteudo += "\n" + "=" * 70 + "\n"
        conteudo += "ESTATÍSTICAS GERAIS DO CARTÃO:\n"
        conteudo += "=" * 70 + "\n\n"
        
        todos_numeros = resultado["melhores_15"]
        pares_total = sum(1 for n in todos_numeros if n % 2 == 0)
        primos_total = sum(1 for n in todos_numeros if n in {2,3,5,7,11,13,17,19,23})
        soma_total = sum(todos_numeros)
        prob_media_total = np.mean([self.probabilidades.get(n, 0) for n in todos_numeros])
        
        conteudo += f"Pares totais: {pares_total} | Ímpares: {15 - pares_total}\n"
        conteudo += f"Primos totais: {primos_total}\n"
        conteudo += f"Soma total: {soma_total}\n"
        conteudo += f"Probabilidade média total: {prob_media_total:.2%}\n"
        
        return conteudo

# =========================
# CLASSE ORIGINAL: Estratégia de Grupos (Baseada no documento)
# =========================
class EstrategiaGrupos:
    def __init__(self, probabilidades, concursos):
        """
        Inicializa a estratégia com as probabilidades do seu código
        """
        self.probabilidades = probabilidades
        self.concursos = concursos
        self.numeros = list(range(1, 26))
        
        # Ordenar números por probabilidade (do mais provável ao menos)
        self.numeros_ordenados = sorted(probabilidades.items(), 
                                       key=lambda x: x[1], 
                                       reverse=True)
        
        # Classificar números nos grupos A e B
        self.classificar_nos_grupos()
        
    def classificar_nos_grupos(self):
        """
        Classifica os 25 números em Grupos A e B baseado nas probabilidades
        """
        # Pegar os 25 números ordenados por probabilidade
        numeros_provaveis = [n for n, _ in self.numeros_ordenados]
        
        # Estratégia do documento: Dividir em 2 conjuntos principais
        # Grupo A: 15 números (mais quentes/prováveis)
        # Grupo B: 10 números (menos quentes/prováveis)
        
        self.grupo_a = numeros_provaveis[:15]  # 15 mais prováveis
        self.grupo_b = numeros_provaveis[15:]   # 10 menos prováveis
        
        # Dentro do Grupo A: Separar em Fixas, G1 e G2
        # Fixas A: 3 números mais prováveis do Grupo A
        self.fixas_a = self.grupo_a[:3]
        
        # Restante do Grupo A dividido em G1 e G2
        restante_a = self.grupo_a[3:]
        meio = len(restante_a) // 2
        self.grupo_a1 = restante_a[:meio]  # G1
        self.grupo_a2 = restante_a[meio:]  # G2
        
        # Dentro do Grupo B: Separar em Fixas, H1 e H2
        # Fixas B: 3 números mais prováveis do Grupo B
        self.fixas_b = self.grupo_b[:3]
        
        # Restante do Grupo B dividido em H1 e H2
        restante_b = self.grupo_b[3:]
        meio_b = len(restante_b) // 2
        self.grupo_b1 = restante_b[:meio_b]  # H1
        self.grupo_b2 = restante_b[meio_b:]  # H2
        
    def gerar_combinacoes_estrategia(self, n_combinacoes=10):
        """
        Gera combinações seguindo a estratégia do documento
        """
        combinacoes = []
        
        # Critérios da estratégia:
        # 1. Sempre incluir as FIXAS de cada grupo
        # 2. Combinar números dos subgrupos
        # 3. Total deve ser 15 números
        
        for i in range(n_combinacoes):
            # Método 1: Combinação balanceada (recomendada)
            if i % 3 == 0:
                combo = self._gerar_combinacao_balanceada()
            
            # Método 2: Foco no Grupo A
            elif i % 3 == 1:
                combo = self._gerar_combinacao_foco_a()
            
            # Método 3: Mistura intensa A/B
            else:
                combo = self._gerar_combinacao_mistura_ab()
            
            if combo and len(combo) == 15:
                combinacoes.append(combo)
        
        return combinacoes
    
    def _gerar_combinacao_balanceada(self):
        """
        Combinação balanceada seguindo a estratégia do documento
        """
        combo = set()
        
        # 1. Adicionar todas as fixas (A e B) - total 6 números
        combo.update(self.fixas_a)
        combo.update(self.fixas_b)
        
        # 2. Adicionar números dos subgrupos de A
        # Do Grupo A1: 3 números
        if len(self.grupo_a1) >= 3:
            combo.update(random.sample(self.grupo_a1, 3))
        else:
            combo.update(self.grupo_a1)
        
        # Do Grupo A2: 3 números
        if len(self.grupo_a2) >= 3:
            combo.update(random.sample(self.grupo_a2, 3))
        else:
            combo.update(self.grupo_a2)
        
        # 3. Adicionar números dos subgrupos de B
        # Se ainda não temos 15 números, completar com B
        if len(combo) < 15:
            faltam = 15 - len(combo)
            todos_b = self.grupo_b1 + self.grupo_b2
            
            # Remover duplicatas
            disponiveis_b = [n for n in todos_b if n not in combo]
            
            if len(disponiveis_b) >= faltam:
                combo.update(random.sample(disponiveis_b, faltam))
            else:
                # Se não tem números B suficientes, completar com qualquer número
                todos_numeros = set(range(1, 26))
                disponiveis = list(todos_numeros - combo)
                combo.update(random.sample(disponiveis, faltam))
        
        return sorted(list(combo))
    
    def _gerar_combinacao_foco_a(self):
        """
        Combinação com foco no Grupo A
        """
        combo = set()
        
        # 1. Todas as fixas A
        combo.update(self.fixas_a)
        
        # 2. Muitos números do Grupo A
        # Pegar 8 números de A1 e A2 combinados
        todos_a = self.grupo_a1 + self.grupo_a2
        if len(todos_a) >= 8:
            combo.update(random.sample(todos_a, 8))
        else:
            combo.update(todos_a)
        
        # 3. Alguns números do Grupo B para completar
        if len(combo) < 15:
            faltam = 15 - len(combo)
            todos_b = self.grupo_b1 + self.grupo_b2
            disponiveis_b = [n for n in todos_b if n not in combo]
            
            if len(disponiveis_b) >= faltam:
                combo.update(random.sample(disponiveis_b, faltam))
            else:
                # Completar com qualquer número
                todos_numeros = set(range(1, 26))
                disponiveis = list(todos_numeros - combo)
                combo.update(random.sample(disponiveis, faltam))
        
        return sorted(list(combo))
    
    def _gerar_combinacao_mistura_ab(self):
        """
        Mistura intensa entre Grupos A e B
        """
        combo = set()
        
        # 1. Fixas de ambos os grupos
        combo.update(self.fixas_a[:2])  # 2 fixas A
        combo.update(self.fixas_b[:2])  # 2 fixas B
        
        # 2. Números igualmente distribuídos
        # Do Grupo A1: 2 números
        if len(self.grupo_a1) >= 2:
            combo.update(random.sample(self.grupo_a1, 2))
        
        # Do Grupo A2: 2 números
        if len(self.grupo_a2) >= 2:
            combo.update(random.sample(self.grupo_a2, 2))
        
        # Do Grupo B1: 2 números
        if len(self.grupo_b1) >= 2:
            combo.update(random.sample(self.grupo_b1, 2))
        
        # Do Grupo B2: 2 números
        if len(self.grupo_b2) >= 2:
            combo.update(random.sample(self.grupo_b2, 2))
        
        # 3. Completar até 15 com números de qualquer grupo
        if len(combo) < 15:
            faltam = 15 - len(combo)
            todos_numeros = self.grupo_a1 + self.grupo_a2 + self.grupo_b1 + self.grupo_b2
            disponiveis = [n for n in todos_numeros if n not in combo]
            
            if len(disponiveis) >= faltam:
                combo.update(random.sample(disponiveis, faltam))
            else:
                # Completar com qualquer número
                todos_numeros = set(range(1, 26))
                disponiveis = list(todos_numeros - combo)
                combo.update(random.sample(disponiveis, faltam))
        
        return sorted(list(combo))
    
    def get_info_grupos(self):
        """
        Retorna informações sobre a classificação dos grupos
        """
        return {
            "grupo_a": {
                "fixas": self.fixas_a,
                "grupo_a1": self.grupo_a1,
                "grupo_a2": self.grupo_a2,
                "total_numeros": len(self.fixas_a) + len(self.grupo_a1) + len(self.grupo_a2)
            },
            "grupo_b": {
                "fixas": self.fixas_b,
                "grupo_b1": self.grupo_b1,
                "grupo_b2": self.grupo_b2,
                "total_numeros": len(self.fixas_b) + len(self.grupo_b1) + len(self.grupo_b2)
            },
            "probabilidades": self.probabilidades
        }
    
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

# =========================
# CLASSE ORIGINAL: Análise Combinatória (mantida)
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
# IA Avançada com CatBoost (ORIGINAL)
# =========================
class LotoFacilIA:
    def __init__(self, concursos):
        self.concursos = concursos
        self.numeros = list(range(1,26))
        self.primos = {2,3,5,7,11,13,17,19,23}
        self.models = {}
        self.X = self.gerar_features()[:-1] if len(concursos) > 1 else np.array([])
        self.Y = self.matriz_binaria()[1:] if len(concursos) > 1 else np.array([])
        if len(self.X) > 0 and len(self.Y) > 0:
            self.treinar_modelos()

    def matriz_binaria(self):
        return np.array([[1 if n in jogo else 0 for n in self.numeros] for jogo in self.concursos])

    def frequencia(self, janela=10):
        janela = min(janela, max(1, len(self.concursos)-1))
        freq = {n:0 for n in self.numeros}
        for jogo in self.concursos[-janela-1:-1]:
            for d in jogo:
                freq[d] +=1
        return freq

    def atraso(self):
        atraso = {n:0 for n in self.numeros}
        for i in range(len(self.concursos)-2, -1, -1):
            jogo = self.concursos[i]
            for n in self.numeros:
                if atraso[n]==0 and n not in jogo:
                    atraso[n] = len(self.concursos)-1 - i
        return atraso

    def quentes_frios(self, top=10):
        freq = self.frequencia()
        numeros_ordenados = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        quentes = [n for n,_ in numeros_ordenados[:top]]
        frios = [n for n,_ in numeros_ordenados[-top:]]
        return {"quentes": quentes, "frios": frios}

    def pares_impares_primos(self):
        ultimo = self.concursos[-1]
        pares = sum(1 for n in ultimo if n%2==0)
        impares = 15 - pares
        primos = sum(1 for n in ultimo if n in self.primos)
        return {"pares": pares, "impares": impares, "primos": primos}

    def interacoes(self, janela=50):
        janela = min(janela, max(1, len(self.concursos)-1))
        matriz = np.zeros((25,25), dtype=int)
        for jogo in self.concursos[-janela-1:-1]:
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
        for i, jogo in enumerate(self.concursos[:-1]):
            for n in self.numeros:
                if n not in jogo:
                    gaps[n].append(len(self.concursos)-1-i)
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
            model = CatBoostClassifier(iterations=600, verbose=0, random_state=42)
            y = self.Y[:,i]
            model.fit(self.X, y)
            self.models[n] = model

    def prever_proximo(self):
        if not self.models:
            return {n: 0.5 for n in self.numeros}
        ultima = self.gerar_features()[-1].reshape(1,-1)
        probabilidades = {}
        for n in self.numeros:
            prob = self.models[n].predict_proba(ultima)[0][1]
            probabilidades[n] = prob
        return probabilidades

    def gerar_5_jogos(self, probabilidades):
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
        janela = min(janela, len(self.concursos))
        ultimos = self.concursos[-janela:]
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
        media_pares = int(np.round(np.mean([p for p,_ in padrao_par_impar])))
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
# PADRÕES LINHA×COLUNA (ORIGINAL)
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
# FUNÇÕES DE PERSISTÊNCIA (ATUALIZADA)
# =========================
def salvar_estado():
    estado = {
        'concursos': st.session_state.concursos,
        'cartoes_gerados': st.session_state.cartoes_gerados,
        'cartoes_gerados_padrao': st.session_state.cartoes_gerados_padrao,
        'info_ultimo_concurso': st.session_state.info_ultimo_concurso,
        'combinacoes_combinatorias': st.session_state.combinacoes_combinatorias,
        'combinacoes_estrategia': st.session_state.get('combinacoes_estrategia', []),
        'cartoes_regras_especificas': st.session_state.get('cartoes_regras_especificas', {})
    }
    return estado

def carregar_estado():
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
    if "combinacoes_estrategia" not in st.session_state:
        st.session_state.combinacoes_estrategia = []
    if "info_estrategia" not in st.session_state:
        st.session_state.info_estrategia = {}
    if "cartoes_regras_especificas" not in st.session_state:
        st.session_state.cartoes_regras_especificas = {}

# =========================
# Streamlit - Estado
# =========================
carregar_estado()

st.markdown("<h1 style='text-align: center;'>Lotofácil Inteligente</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- Captura concursos ---
with st.expander("📥 Capturar Concursos"):
    qtd_concursos = st.slider("Quantidade de concursos para análise", 10, 250, 100)
    if st.button("🔄 Capturar Agora"):
        with st.spinner("Capturando concursos da Lotofácil..."):
            concursos, info = capturar_ultimos_resultados(qtd_concursos)
            if concursos:
                st.session_state.concursos = concursos
                st.session_state.info_ultimo_concurso = info
                st.success(f"{len(concursos)} concursos capturados com sucesso!")
            else:
                st.error("Não foi possível capturar concursos.")

# --- Abas principais ---
# Variável abas precisa ser definida antes de ser usada
abas = []

if st.session_state.concursos:
    ia = LotoFacilIA(st.session_state.concursos)
    probs = ia.prever_proximo()
    jogos_gerados = ia.gerar_5_jogos(probs) if probs else []
    quentes_frios = ia.quentes_frios()
    pares_impares_primos = ia.pares_impares_primos()

    # ABAS PRINCIPAIS (ATUALIZADO COM NOVA ABA)
    abas = st.tabs([
        "📊 Estatísticas", 
        "🧠 Gerar Cartões", 
        "🧩 Gerar Cartões por Padrões",
        "🔢 Análises Combinatórias",
        "🎯 ESTRATÉGIA DE GRUPOS",
        "🎰 CARTÕES COM REGRAS ESPECÍFICAS",  # NOVA ABA
        "📐 Padrões Linha×Coluna",
        "✅ Conferência", 
        "📤 Conferir Arquivo TXT"
    ])

    # Aba 1 - Estatísticas (original)
    with abas[0]:
        st.subheader("📈 Estatísticas Gerais")
        st.write(f"Números quentes: {quentes_frios['quentes']}")
        st.write(f"Números frios: {quentes_frios['frios']}")
        st.write(f"Pares/Ímpares/Primos último concurso: {pares_impares_primos}")
        st.write(f"Frequência últimos 50 concursos (excluindo último): {ia.frequencia()}")
        st.write(f"Atraso de cada número (excluindo último concurso): {ia.atraso()}")

    # Aba 2 - Gerar Cartões (original)
    with abas[1]:
        st.subheader("🧾 Geração de Cartões Inteligentes")
        if st.button("🚀 Gerar 5 Cartões"):
            st.session_state.cartoes_gerados = jogos_gerados
            st.success("5 Cartões gerados com sucesso!")
        if st.session_state.cartoes_gerados:
            for i, c in enumerate(st.session_state.cartoes_gerados,1):
                st.write(f"Jogo {i}: {c}")
            conteudo = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados)
            st.download_button("💾 Baixar Arquivo", data=conteudo, file_name="cartoes_lotofacil.txt", mime="text/plain")

    # Aba 3 - Gerar Cartões por Padrões (original)
    with abas[2]:
        st.subheader("🧩 Geração de Cartões com Base em Padrões")
        janela_padrao = st.slider("Janela (nº de concursos recentes)", 5, 100, 10, 5)
        if st.button("🚀 Gerar 5 Cartões por Padrões"):
            cartoes_padrao = ia.gerar_cartoes_por_padroes(n_jogos=5, janela=janela_padrao)
            st.session_state.cartoes_gerados_padrao = cartoes_padrao
            st.success("5 Cartões por Padrões gerados com sucesso!")
        
        if st.session_state.cartoes_gerados_padrao:
            for i, c in enumerate(st.session_state.cartoes_gerados_padrao,1):
                st.write(f"Cartão {i}: {c}")
            conteudo_padrao = "\n".join(",".join(str(n) for n in cartao) for cartao in st.session_state.cartoes_gerados_padrao)
            st.download_button("💾 Baixar Arquivo Padrões", data=conteudo_padrao, file_name="cartoes_padroes_lotofacil.txt", mime="text/plain")

    # Aba 4 - Análises Combinatórias (original)
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
            
            st.markdown("### 📋 Relatório Estatístico")
            relatorio = analisador_combinatorio.gerar_relatorio_estatistico(
                st.session_state.combinacoes_combinatorias
            )
            for tamanho, stats in relatorio.items():
                with st.expander(f"Estatísticas para {tamanho} números"):
                    st.write(f"Total de combinações: {stats['total_combinacoes']}")
                    st.write(f"Score médio: {stats['media_score']:.2f}")
                    st.write(f"Melhor score: {stats['melhor_score']:.2f}")
                    st.write(f"Pior score: {stats['pior_score']:.2f}")
            
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

    # Aba 5 - ESTRATÉGIA DE GRUPOS (original)
    with abas[4]:
        st.subheader("🎯 ESTRATÉGIA DE GRUPOS A/B")
        st.markdown("""
        **Baseado no documento russo:** Divide números em:
        - **Grupo A:** 15 números mais prováveis (com Fixas, G1, G2)
        - **Grupo B:** 10 números menos prováveis (com Fixas, H1, H2)
        
        **Estratégia:** Combina números seguindo padrões específicos de distribuição
        """)
        
        # Criar estratégia com as probabilidades do seu código
        estrategia = EstrategiaGrupos(probs, st.session_state.concursos)
        
        # Mostrar classificação dos grupos
        info_grupos = estrategia.get_info_grupos()
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("### 📊 GRUPO A (15 mais prováveis)")
            st.write(f"**Fixas A:** {sorted(info_grupos['grupo_a']['fixas'])}")
            st.write(f"**Grupo A1:** {sorted(info_grupos['grupo_a']['grupo_a1'])}")
            st.write(f"**Grupo A2:** {sorted(info_grupos['grupo_a']['grupo_a2'])}")
            st.write(f"Total: {info_grupos['grupo_a']['total_numeros']} números")
            
            # Mostrar probabilidades do Grupo A
            st.markdown("#### Probabilidades do Grupo A:")
            for num in sorted(info_grupos['grupo_a']['fixas'] + 
                             info_grupos['grupo_a']['grupo_a1'] + 
                             info_grupos['grupo_a']['grupo_a2']):
                prob = info_grupos['probabilidades'].get(num, 0)
                st.write(f"Número {num:2d}: {prob:.2%}")
        
        with col_g2:
            st.markdown("### 📊 GRUPO B (10 menos prováveis)")
            st.write(f"**Fixas B:** {sorted(info_grupos['grupo_b']['fixas'])}")
            st.write(f"**Grupo B1:** {sorted(info_grupos['grupo_b']['grupo_b1'])}")
            st.write(f"**Grupo B2:** {sorted(info_grupos['grupo_b']['grupo_b2'])}")
            st.write(f"Total: {info_grupos['grupo_b']['total_numeros']} números")
            
            # Mostrar probabilidades do Grupo B
            st.markdown("#### Probabilidades do Grupo B:")
            for num in sorted(info_grupos['grupo_b']['fixas'] + 
                             info_grupos['grupo_b']['grupo_b1'] + 
                             info_grupos['grupo_b']['grupo_b2']):
                prob = info_grupos['probabilidades'].get(num, 0)
                st.write(f"Número {num:2d}: {prob:.2%}")
        
        # Gerar combinações com a estratégia
        st.markdown("### 🎲 Gerar Combinações com a Estratégia")
        
        col_qtd, col_tipo = st.columns(2)
        
        with col_qtd:
            n_combinacoes = st.slider("Número de combinações", 1, 20, 10)
        
        with col_tipo:
            tipo_estrategia = st.selectbox(
                "Tipo de estratégia:",
                ["Balanceada (recomendada)", "Foco no Grupo A", "Mistura intensa A/B"]
            )
        
        if st.button("🚀 Gerar Combinações com Estratégia", type="primary"):
            with st.spinner("Gerando combinações usando estratégia de grupos..."):
                # Salvar informações da estratégia
                st.session_state.info_estrategia = info_grupos
                
                # Gerar combinações
                combinacoes = estrategia.gerar_combinacoes_estrategia(n_combinacoes)
                st.session_state.combinacoes_estrategia = combinacoes
                st.success(f"{len(combinacoes)} combinações geradas com sucesso!")
        
        # Mostrar combinações geradas
        if st.session_state.combinacoes_estrategia:
            st.markdown(f"### 📋 {len(st.session_state.combinacoes_estrategia)} Combinações Geradas")
            
            for i, combo in enumerate(st.session_state.combinacoes_estrategia, 1):
                with st.expander(f"Combinação {i}: {combo}"):
                    # Mostrar cartão formatado
                    st.markdown("#### Cartão da Lotofácil:")
                    cartao = estrategia.formatar_como_cartao(combo)
                    for linha in cartao:
                        st.code(" ".join(linha))
                    
                    # Estatísticas da combinação
                    st.markdown("#### Estatísticas:")
                    
                    col_e1, col_e2, col_e3 = st.columns(3)
                    
                    with col_e1:
                        pares = sum(1 for n in combo if n % 2 == 0)
                        st.metric("Pares", pares)
                        st.metric("Ímpares", 15 - pares)
                    
                    with col_e2:
                        primos = sum(1 for n in combo if n in {2,3,5,7,11,13,17,19,23})
                        st.metric("Primos", primos)
                        soma = sum(combo)
                        st.metric("Soma", soma)
                    
                    with col_e3:
                        # Distribuição por grupos
                        grupo_a_count = sum(1 for n in combo if n in info_grupos['grupo_a']['fixas'] + 
                                          info_grupos['grupo_a']['grupo_a1'] + 
                                          info_grupos['grupo_a']['grupo_a2'])
                        grupo_b_count = 15 - grupo_a_count
                        st.metric("Grupo A", grupo_a_count)
                        st.metric("Grupo B", grupo_b_count)
            
            # Botão para exportar
            st.markdown("### 💾 Exportar Combinações")
            
            conteudo_estrategia = "COMBINAÇÕES ESTRATÉGIA DE GRUPOS A/B\n"
            conteudo_estrategia += "=" * 50 + "\n\n"
            
            # Adicionar informações dos grupos
            conteudo_estrategia += "INFORMAÇÕES DOS GRUPOS:\n"
            conteudo_estrategia += f"Grupo A (mais prováveis): {sorted(info_grupos['grupo_a']['fixas'] + info_grupos['grupo_a']['grupo_a1'] + info_grupos['grupo_a']['grupo_a2'])}\n"
            conteudo_estrategia += f"Grupo B (menos prováveis): {sorted(info_grupos['grupo_b']['fixas'] + info_grupos['grupo_b']['grupo_b1'] + info_grupos['grupo_b']['grupo_b2'])}\n\n"
            
            conteudo_estrategia += "COMBINAÇÕES GERADAS:\n"
            conteudo_estrategia += "=" * 50 + "\n\n"
            
            for i, combo in enumerate(st.session_state.combinacoes_estrategia, 1):
                conteudo_estrategia += f"Combinação {i}:\n"
                conteudo_estrategia += f"{','.join(map(str, combo))}\n\n"
            
            st.download_button(
                "📥 Baixar Combinações da Estratégia",
                data=conteudo_estrategia,
                file_name="estrategia_grupos_lotofacil.txt",
                mime="text/plain"
            )

    # NOVA ABA 6 - CARTÕES COM REGRAS ESPECÍFICAS (AGORA AUTOMÁTICO)
    # NOVA ABA 6 - CARTÕES COM REGRAS ESPECÍFICAS (AGORA AUTOMÁTICO)
    with abas[5]:
        st.subheader("🎰 CARTÕES COM REGRAS ESPECÍFICAS")
        st.markdown("""
        **Regras EXATAS da imagem:**
    
    | Tipo | Linhas Permitidas | Exemplo Válido | Total Números |
    |------|-------------------|----------------|---------------|
    | **1** | Máximo 1 linha   | 1×15 = 15      | 15 números    |
    | **2** | 1 a 2 linhas     | 2×8 = 16*      | 15-16 números |
    | **3** | 1 a 3 linhas     | 3×5 = 15       | 15 números    |
    | **4** | 1 a 2 linhas     | 4×4 = 16*      | 15-16 números |
    | **5** | Máximo 1 linha   | 5×3 = 15       | 15 números    |
    
    *Ajustado para dar exatamente 15 números
    
    **💡 COMO FUNCIONA:**
    1. Sistema escolhe automaticamente 1-5 dezenas por linha
    2. Escolhe 1-3 linhas (dentro das regras)
    3. Distribui os **15 melhores números** nessas linhas
    4. **Cada linha segue exatamente a regra escolhida**
    5. **Soma total: SEMPRE 15 números** (cartão completo)
    """)
    
    # Inicializar gerador
    gerador_regras = GeradorCartoesRegrasEspecificas(probs)
    
    # Mostrar estatísticas atuais
    st.markdown("### 📊 Análise das Probabilidades para Decisão")
    
    col_stat1, col_stat2 = st.columns(2)
    
    with col_stat1:
        # Estatísticas básicas
        valores_prob = [prob for _, prob in probs.items()]
        media = np.mean(valores_prob)
        desvio = np.std(valores_prob)
        
        st.metric("Média probabilidade", f"{media:.2%}")
        st.metric("Desvio padrão", f"{desvio:.4f}")
        st.metric("Variação", f"{(desvio/media)*100:.1f}%")
        
        # Top números
        numeros_ordenados = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        st.write("**Top 3 mais prováveis:**")
        for i, (num, prob) in enumerate(numeros_ordenados[:3], 1):
            st.write(f"{i}. Número {num}: {prob:.2%}")
    
    with col_stat2:
        # Distribuição por faixas
        baixas = sum(1 for prob in valores_prob if prob < 0.4)
        medias = sum(1 for prob in valores_prob if 0.4 <= prob <= 0.6)
        altas = sum(1 for prob in valores_prob if prob > 0.6)
        
        st.metric("Baixas (<40%)", baixas)
        st.metric("Médias (40-60%)", medias)
        st.metric("Altas (>60%)", altas)
        
        # Força dos tops
        top5_avg = np.mean([prob for _, prob in numeros_ordenados[:5]])
        top10_avg = np.mean([prob for _, prob in numeros_ordenados[:10]])
        st.metric("Média top 5", f"{top5_avg:.2%}")
        st.metric("Média top 10", f"{top10_avg:.2%}")
    
    # Botão para gerar
    st.markdown("### 🎯 Gerar Cartão com Distribuição por Regras")
    
    if st.button("🚀 Gerar Cartão com Regras Específicas", type="primary"):
        try:
            with st.spinner("Calculando melhor distribuição dos 15 números..."):
                # Gerar cartão completo
                resultado = gerador_regras.gerar_cartao_completo()
                
                # Salvar no session state
                st.session_state.cartoes_regras_especificas = {
                    "resultado": resultado,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                st.success("✅ Cartão gerado com sucesso!")
                
                # Mostrar decisão
                tipo = resultado["tipo_dezenas"]
                linhas = resultado["num_linhas"]
                regra = gerador_regras.regras[tipo]
                
                st.info(f"""
                **📋 DECISÃO DO SISTEMA:**
                - **Regra aplicada:** {regra['nome']}
                - **Números por linha:** {tipo}
                - **Total de linhas:** {linhas}
                - **Total números:** {tipo} × {linhas} = {tipo * linhas}
                - **Combinação:** {tipo} dezenas × {linhas} linhas
                """)
        
        except Exception as e:
            st.error(f"❌ Erro: {str(e)}")
    
    # CORREÇÃO AQUI: Verificar se o resultado existe corretamente
    if st.session_state.get('cartoes_regras_especificas'):
        dados = st.session_state.cartoes_regras_especificas
        
        # CORREÇÃO: Usar get() para evitar KeyError
        resultado = dados.get("resultado")
        
        if resultado:
            tipo = resultado.get("tipo_dezenas", 0)
            linhas = resultado.get("num_linhas", 0)
            regra = gerador_regras.regras.get(tipo, {"nome": "Desconhecida"})
            
            st.markdown(f"### 🎰 CARTÃO GERADO: {regra['nome']} × {linhas} Linhas")
            
            # Cartão visual
            st.markdown("#### Cartão da Lotofácil (L1, L2... = Linha da regra):")
            cartao_completo = resultado.get("cartao_completo", [])
            
            if cartao_completo:
                # Criar visualização bonita
                for linha_cartao in cartao_completo:
                    col1, col2, col3, col4, col5 = st.columns(5)
                    cols = [col1, col2, col3, col4, col5]
                    
                    for idx, celula in enumerate(linha_cartao):
                        with cols[idx]:
                            if "[" in celula:  # Número marcado
                                if "L" in celula:  # Tem indicação de linha
                                    num = celula.split("L")[0].replace("[", "").replace("]", "").strip()
                                    linha_num = celula.split("L")[1]
                                    st.markdown(f"<div style='background-color: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center;'>"
                                              f"<strong>{num}</strong><br><small>L{linha_num}</small></div>", 
                                              unsafe_allow_html=True)
                                else:
                                    num = celula.replace("[", "").replace("]", "").strip()
                                    st.markdown(f"<div style='background-color: #2196F3; color: white; padding: 10px; border-radius: 5px; text-align: center;'>"
                                              f"<strong>{num}</strong></div>", 
                                              unsafe_allow_html=True)
                            else:  # Número não marcado
                                num = celula.strip()
                                st.markdown(f"<div style='background-color: #f5f5f5; padding: 10px; border-radius: 5px; text-align: center; color: #666;'>"
                                          f"{num}</div>", 
                                          unsafe_allow_html=True)
            
                # Detalhes das linhas
                distribuicao = resultado.get("distribuicao", [])
                if distribuicao:
                    st.markdown("#### 📋 Distribuição Detalhada das Linhas:")
                    
                    for dist in distribuicao:
                        with st.expander(f"Linha {dist.get('linha', '?')}: {dist.get('numeros', [])}", expanded=True):
                            col_lin1, col_lin2, col_lin3 = st.columns(3)
                            
                            with col_lin1:
                                st.metric("Pares", dist.get("pares", 0))
                                st.metric("Ímpares", dist.get("impares", 0))
                            
                            with col_lin2:
                                st.metric("Primos", dist.get("primos", 0))
                                st.metric("Soma", dist.get("soma", 0))
                            
                            with col_lin3:
                                st.metric("Prob. média", f"{dist.get('probabilidade_media', 0):.2%}")
                                st.metric("Prob. total", f"{dist.get('probabilidade_total', 0):.2%}")
                            
                            # Probabilidades individuais
                            numeros_linha = dist.get("numeros", [])
                            if numeros_linha:
                                st.markdown("**Probabilidades dos números:**")
                                for num in numeros_linha:
                                    prob = probs.get(num, 0)
                                    st.progress(prob, text=f"Número {num}: {prob:.2%}")
                
                # Estatísticas gerais
                melhores_15 = resultado.get("melhores_15", [])
                if melhores_15:
                    st.markdown("#### 📊 Estatísticas Gerais do Cartão:")
                    
                    todos_numeros = melhores_15
                    pares_total = sum(1 for n in todos_numeros if n % 2 == 0)
                    primos_total = sum(1 for n in todos_numeros if n in {2,3,5,7,11,13,17,19,23})
                    soma_total = sum(todos_numeros)
                    prob_media_total = np.mean([probs.get(n, 0) for n in todos_numeros])
                    
                    col_ger1, col_ger2, col_ger3, col_ger4 = st.columns(4)
                    
                    with col_ger1:
                        st.metric("Pares totais", pares_total)
                        st.metric("Ímpares totais", 15 - pares_total)
                    
                    with col_ger2:
                        st.metric("Primos totais", primos_total)
                        st.metric("Não primos", 15 - primos_total)
                    
                    with col_ger3:
                        st.metric("Soma total", soma_total)
                        st.metric("Média por número", f"{soma_total/15:.1f}")
                    
                    with col_ger4:
                        st.metric("Prob. média total", f"{prob_media_total:.2%}")
                        st.metric("Força do cartão", f"{(prob_media_total/0.5-1)*100:.1f}%")
                    
                    # Download
                    st.markdown("### 💾 Exportar Cartão")
                    
                    conteudo = gerador_regras.formatar_para_download(resultado)
                    
                    st.download_button(
                        "📥 Baixar Cartão Completo",
                        data=conteudo,
                        file_name=f"cartao_regras_{tipo}dezenas_{linhas}linhas.txt",
                        mime="text/plain"
                    )
        else:
            st.info("Clique no botão acima para gerar um cartão com regras específicas.")
    
    # Explicação completa
    with st.expander("📚 Explicação Detalhada do Sistema"):
        st.markdown("""
        **🎯 OBJETIVO DO SISTEMA:**
        Criar cartões da Lotofácil com **EXATAMENTE 15 NÚMEROS** distribuídos 
        em linhas que seguem **EXATAMENTE AS REGRAS DA IMAGEM**.
        
        **🔢 COMO FUNCIONA:**
        
        1. **ANÁLISE ESTATÍSTICA:**
           - Sistema analisa as probabilidades de todos os 25 números
           - Calcula média, desvio padrão, distribuição
           - Identifica números "fortes", "médios" e "fracos"
        
        2. **DECISÃO DA REGRA:**
           - **1 Dezena:** Quando há 1 número MUITO forte
           - **2 Dezenas:** Quando há 2 números muito fortes  
           - **3 Dezenas:** Quando há 3 números bem destacados
           - **4 Dezenas:** Quando há 4-5 números consistentes
           - **5 Dezenas:** Quando muitos números têm probabilidade similar
        
        3. **DISTRIBUIÇÃO DOS 15 NÚMEROS:**
           - Pega os **15 números mais prováveis**
           - Divide em linhas com número fixo de números (1-5)
           - **Exemplo (3 Dezenas × 5 Linhas):**
             - Linha 1: 3 números (1-3 mais prováveis)
             - Linha 2: 3 números (4-6 mais prováveis)
             - Linha 3: 3 números (7-9 mais prováveis)
             - Linha 4: 3 números (10-12 mais prováveis)
             - Linha 5: 3 números (13-15 mais prováveis)
        
        4. **CARTÃO FINAL:**
           - **Total: SEMPRE 15 números** (cartão completo jogável)
           - **Cada linha segue a regra escolhida**
           - **Visualização mostra em qual linha cada número está**
        
        **📈 BENEFÍCIOS:**
        - Cartões **completamente jogáveis** (15 números)
        - Distribuição **estatisticamente otimizada**
        - **Transparência total** na decisão do sistema
        - **Flexibilidade** para diferentes situações estatísticas
        """)

    # Aba 7 - Padrões Linha×Coluna (original)
    with abas[6]:
        st.subheader("📐 Padrões de Linhas × Colunas")
        concursos = st.session_state.concursos
        if not concursos:
            st.info("Capture concursos na seção acima para analisar os padrões.")
        else:
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

    # Aba 8 - Conferência (ATUALIZADA com nova estratégia)
    with abas[7]:
        st.subheader("🎯 Conferência de Cartões")
        if st.session_state.info_ultimo_concurso:
            info = st.session_state.info_ultimo_concurso
            st.markdown(
                f"<h4 style='text-align: center;'>Último Concurso #{info['numero']} ({info['data']})<br>Dezenas: {info['dezenas']}</h4>",
                unsafe_allow_html=True
            )
            
            if st.button("🔍 Conferir Todos os Cartões"):
                # Conferir Cartões IA
                if st.session_state.cartoes_gerados:
                    st.markdown("### 🧠 Cartões Gerados por IA")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Jogo {i}: {cartao} - **{acertos} acertos**")
                
                # Conferir Cartões por Padrões
                if st.session_state.cartoes_gerados_padrao:
                    st.markdown("### 🧩 Cartões por Padrões")
                    for i, cartao in enumerate(st.session_state.cartoes_gerados_padrao, 1):
                        acertos = len(set(cartao) & set(info['dezenas']))
                        st.write(f"Cartão {i}: {cartao} - **{acertos} acertos**")
                
                # Conferir Combinações Combinatorias
                if st.session_state.combinacoes_combinatorias:
                    st.markdown("### 🔢 Combinações Combinatorias (Top 3 por Tamanho)")
                    analisador_combinatorio = AnaliseCombinatoria(st.session_state.concursos)
                    
                    for tamanho in sorted(st.session_state.combinacoes_combinatorias.keys()):
                        combinacoes_tamanho = st.session_state.combinacoes_combinatorias[tamanho][:3]
                        if combinacoes_tamanho:
                            st.markdown(f"#### 📊 Combinações com {tamanho} números")
                            for idx, (combo, score) in enumerate(combinacoes_tamanho, 1):
                                acertos = len(set(combo) & set(info['dezenas']))
                                col1, col2 = st.columns([2, 1])
                                with col1:
                                    st.write(f"**Cartão {idx}** (Score: {score:.1f}) - **{acertos} acertos**")
                                    cartao = analisador_combinatorio.formatar_como_cartao(combo)
                                    for linha in cartao:
                                        st.code(" ".join(linha))
                                with col2:
                                    pares = sum(1 for n in combo if n % 2 == 0)
                                    primos = sum(1 for n in combo if n in analisador_combinatorio.primos)
                                    soma = sum(combo)
                                    st.write(f"**Estatísticas:**")
                                    st.write(f"Pares: {pares}")
                                    st.write(f"Ímpares: {len(combo)-pares}")
                                    st.write(f"Primos: {primos}")
                                    st.write(f"Soma: {soma}")
                                st.write("---")
                
                # Conferir Combinações da Estratégia
                if st.session_state.combinacoes_estrategia:
                    st.markdown("### 🎯 Combinações da Estratégia de Grupos")
                    estrategia = EstrategiaGrupos(probs, st.session_state.concursos)
                    
                    for i, combo in enumerate(st.session_state.combinacoes_estrategia, 1):
                        acertos = len(set(combo) & set(info['dezenas']))
                        
                        with st.expander(f"Combinação {i}: {acertos} acertos - {combo}"):
                            # Cartão formatado
                            st.markdown("#### Cartão:")
                            cartao = estrategia.formatar_como_cartao(combo)
                            for linha in cartao:
                                st.code(" ".join(linha))
                            
                            # Estatísticas
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                pares = sum(1 for n in combo if n % 2 == 0)
                                primos = sum(1 for n in combo if n in {2,3,5,7,11,13,17,19,23})
                                soma = sum(combo)
                                st.metric("Pares", pares)
                                st.metric("Ímpares", 15 - pares)
                                st.metric("Primos", primos)
                                st.metric("Soma", soma)
                            
                            with col_e2:
                                # Distribuição por grupos
                                if st.session_state.info_estrategia:
                                    grupo_a = (st.session_state.info_estrategia['grupo_a']['fixas'] + 
                                              st.session_state.info_estrategia['grupo_a']['grupo_a1'] + 
                                              st.session_state.info_estrategia['grupo_a']['grupo_a2'])
                                    grupo_b = (st.session_state.info_estrategia['grupo_b']['fixas'] + 
                                              st.session_state.info_estrategia['grupo_b']['grupo_b1'] + 
                                              st.session_state.info_estrategia['grupo_b']['grupo_b2'])
                                    
                                    grupo_a_count = sum(1 for n in combo if n in grupo_a)
                                    grupo_b_count = 15 - grupo_a_count
                                    
                                    st.metric("Grupo A", grupo_a_count)
                                    st.metric("Grupo B", grupo_b_count)
                                    
                                    # Acertos por grupo
                                    acertos_a = len(set(combo) & set(grupo_a) & set(info['dezenas']))
                                    acertos_b = len(set(combo) & set(grupo_b) & set(info['dezenas']))
                                    st.metric("Acertos Grupo A", acertos_a)
                                    st.metric("Acertos Grupo B", acertos_b)
                
                # NOVO: Conferir Cartões com Regras Específicas
                if "cartoes_regras_especificas" in st.session_state:
                    dados = st.session_state.cartoes_regras_especificas
                    resultado = dados.get("resultado", {})
                    
                    if resultado and "melhores_15" in resultado:
                        todos_numeros = resultado["melhores_15"]
                        tipo_dezenas = resultado.get("tipo_dezenas", 0)
                        num_linhas = resultado.get("num_linhas", 0)
                        linhas = resultado.get("linhas", [])
                        
                        st.markdown("### 🎰 Cartões com Regras Específicas")
                        
                        # Conferir cartão completo (15 números)
                        acertos_completo = len(set(todos_numeros) & set(info['dezenas']))
                        
                        with st.expander(f"Cartão Completo ({tipo_dezenas} dezenas × {num_linhas} linhas): {acertos_completo} acertos", expanded=True):
                            # Mostrar as linhas individualmente
                            st.markdown("#### 📋 Análise por Linhas:")
                            
                            for idx, linha in enumerate(linhas, 1):
                                acertos_linha = len(set(linha) & set(info['dezenas']))
                                
                                col_l1, col_l2, col_l3 = st.columns([3, 2, 2])
                                
                                with col_l1:
                                    st.write(f"**Linha {idx}:** {linha}")
                                    st.write(f"Acertos na linha: **{acertos_linha}**")
                                
                                with col_l2:
                                    pares = sum(1 for n in linha if n % 2 == 0)
                                    primos = sum(1 for n in linha if n in {2,3,5,7,11,13,17,19,23})
                                    st.write(f"Pares: {pares}")
                                    st.write(f"Primos: {primos}")
                                
                                with col_l3:
                                    # Mostrar quais números acertaram
                                    acertos_numeros = sorted(set(linha) & set(info['dezenas']))
                                    if acertos_numeros:
                                        st.write(f"**Números acertados:**")
                                        for num in acertos_numeros:
                                            st.write(f"• {num}")
                                
                                st.markdown("---")
                            
                            # Estatísticas gerais
                            st.markdown("#### 📊 Estatísticas do Cartão Completo:")
                            
                            col_c1, col_c2, col_c3 = st.columns(3)
                            
                            with col_c1:
                                pares_total = sum(1 for n in todos_numeros if n % 2 == 0)
                                primos_total = sum(1 for n in todos_numeros if n in {2,3,5,7,11,13,17,19,23})
                                st.metric("Acertos totais", acertos_completo)
                                st.metric("Pares totais", pares_total)
                                st.metric("Primos totais", primos_total)
                            
                            with col_c2:
                                soma_total = sum(todos_numeros)
                                media_acertos = acertos_completo / 15 * 100
                                st.metric("Soma total", soma_total)
                                st.metric("Taxa de acerto", f"{media_acertos:.1f}%")
                            
                            with col_c3:
                                # Números acertados
                                acertos_numeros = sorted(set(todos_numeros) & set(info['dezenas']))
                                if acertos_numeros:
                                    st.write("**Números acertados:**")
                                    st.write(acertos_numeros)
                                
                                # Números que não saíram
                                erros_numeros = sorted(set(todos_numeros) - set(info['dezenas']))
                                if erros_numeros:
                                    st.write("**Números não sorteados:**")
                                    st.write(erros_numeros)

    # Aba 9 - Conferir Arquivo TXT (original)
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

# Botão para limpar todos os dados (FORA DO BLOCO CONDICIONAL)
with st.sidebar:
    st.markdown("---")
    st.subheader("⚙️ Gerenciamento de Dados")
    if st.button("🗑️ Limpar Todos os Dados"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    # Mostrar estatísticas de uso
    st.markdown("### 📊 Estatísticas da Sessão")
    if st.session_state.get('concursos'):
        st.write(f"Concursos carregados: {len(st.session_state.concursos)}")
    if st.session_state.get('cartoes_gerados'):
        st.write(f"Cartões IA gerados: {len(st.session_state.cartoes_gerados)}")
    if st.session_state.get('cartoes_gerados_padrao'):
        st.write(f"Cartões por padrões: {len(st.session_state.cartoes_gerados_padrao)}")
    if st.session_state.get('combinacoes_combinatorias'):
        total_combinacoes = sum(len(combinacoes) for combinacoes in st.session_state.combinacoes_combinatorias.values())
        st.write(f"Combinações combinatorias: {total_combinacoes}")
    if st.session_state.get('combinacoes_estrategia'):
        st.write(f"Combinações estratégia: {len(st.session_state.combinacoes_estrategia)}")
    if st.session_state.get('cartoes_regras_especificas'):
        resultado = st.session_state.cartoes_regras_especificas.get("resultado", {})
        if resultado:
            tipo = resultado.get("tipo_dezenas", 0)
            linhas = resultado.get("num_linhas", 0)
            st.write(f"Cartões regras específicas: {tipo} dezena(s), {linhas} linha(s)")

st.markdown("<hr><p style='text-align: center;'>SAMUCJ TECHNOLOGY</p>", unsafe_allow_html=True)
