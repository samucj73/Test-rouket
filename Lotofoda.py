import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
from collections import Counter
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# =====================================================
# CONFIGURAÇÃO MOBILE PREMIUM
# =====================================================
st.set_page_config(
    page_title="🎯 LOTOFÁCIL PREMIUM",
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

st.title("🧠🎯 LOTOFÁCIL PREMIUM")
st.caption("DNA Evolutivo • Sem Repetições • Mobile First")

# =====================================================
# FUNÇÃO PARA CONVERTER NUMPY TYPES PARA PYTHON NATIVE
# =====================================================
def convert_numpy_types(obj):
    """Converte numpy types para tipos nativos Python para serialização JSON"""
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

# =====================================================
# FUNÇÕES DE ARQUIVO LOCAL
# =====================================================
def salvar_jogos_gerados(jogos, fechamento, dna_params, numero_concurso_atual, data_concurso_atual, estatisticas=None):
    """Salva os jogos gerados em arquivo JSON local com estatísticas"""
    try:
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/fechamento_{data_hora}_{jogo_id}.json"
        
        # Converter todos os numpy types para tipos nativos
        jogos_convertidos = convert_numpy_types(jogos)
        
        # Garantir que cada jogo é uma lista simples
        jogos_final = []
        for jogo in jogos_convertidos:
            if isinstance(jogo, (list, tuple)):
                # Garantir que é uma lista de inteiros
                jogo_lista = [int(n) for n in jogo]
                # Garantir que tem 15 números únicos
                if len(set(jogo_lista)) != 15:
                    # Corrigir se necessário
                    jogo_lista = sorted(list(set(jogo_lista)))
                    while len(jogo_lista) < 15:
                        novo = random.randint(1, 25)
                        if novo not in jogo_lista:
                            jogo_lista.append(novo)
                    jogo_lista.sort()
                jogos_final.append(jogo_lista)
            else:
                # Se não for lista, tentar converter
                jogos_final.append([int(n) for n in range(1, 16)])  # fallback
        
        fechamento_convertido = convert_numpy_types(fechamento)
        dna_convertido = convert_numpy_types(dna_params)
        estatisticas_convertidas = convert_numpy_types(estatisticas) if estatisticas else {}
        
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_base": {
                "numero": int(numero_concurso_atual),
                "data": str(data_concurso_atual)
            },
            "fechamento_base": fechamento_convertido,
            "dna_params": dna_convertido,
            "jogos": jogos_final,
            "estatisticas": estatisticas_convertidas,
            "conferido": False,
            "conferencias": []
        }
        
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_salvos():
    """Carrega todos os jogos salvos"""
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
    """Adiciona nova conferência ao histórico"""
    try:
        caminho = f"jogos_salvos/{arquivo}"
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        if "conferencias" not in dados:
            dados["conferencias"] = []
        
        # Converter dados para tipos nativos
        acertos_convertidos = [int(a) for a in acertos]
        estatisticas_convertidas = convert_numpy_types(estatisticas) if estatisticas else {}
        
        nova_conferencia = {
            "concurso": concurso_info,
            "acertos": acertos_convertidos,
            "estatisticas": estatisticas_convertidas,
            "data_conferencia": datetime.now().isoformat()
        }
        
        dados["conferencias"].append(nova_conferencia)
        dados["conferido"] = True
        
        # Atualizar estatísticas acumuladas
        if "estatisticas_historicas" not in dados:
            dados["estatisticas_historicas"] = []
        dados["estatisticas_historicas"].append(estatisticas_convertidas)
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar conferência: {e}")
        return False

# =====================================================
# FUNÇÃO PARA EXPORTAR CONCURSOS EM TXT
# =====================================================
def exportar_concursos_txt(dados_api, qtd_concursos):
    """Exporta os concursos para um arquivo TXT formatado"""
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

# =====================================================
# CLASSE PRINCIPAL MELHORADA - SEM REPETIÇÕES
# =====================================================
class AnaliseLotofacilAvancada:

    def __init__(self, concursos, dados_completos=None):
        self.concursos = concursos
        self.dados_completos = dados_completos or []
        self.ultimo_concurso = concursos[0] if concursos else []
        self.ultimo_concurso_numero = dados_completos[0]["concurso"] if dados_completos else 0
        self.ultimo_concurso_data = dados_completos[0]["data"] if dados_completos else ""
        self.numeros = list(range(1, 26))
        self.total_concursos = len(concursos)

        # Análises básicas
        self.frequencias = self._frequencias()
        self.defasagens = self._defasagens()
        self.padroes = self._padroes()
        self.numeros_chave = self._numeros_chave()
        
        # NOVAS ANÁLISES PARA SUPERAR O ALEATÓRIO
        self.padroes_repeticao = self._analisar_padroes_repeticao()
        self.tendencias_linhas_colunas = self._analisar_linhas_colunas()
        self.pares_impares_tendencia = self._analisar_pares_impares()
        self.intervalos_tendencia = self._analisar_intervalos()
        self.dna_evolutivo = self._inicializar_dna_evolutivo()
        
        # Memória de acertos para aprendizado
        self.historico_acertos = []
        self.melhor_combinacao_dna = None

    def _inicializar_dna_evolutivo(self):
        """DNA mais complexo com múltiplos fatores"""
        return {
            "freq": 1.2,
            "defas": 1.3,
            "soma": 1.1,
            "pares": 1.1,
            "seq": 1.0,
            "chave": 1.2,
            "repeticao": 1.3,
            "linha_coluna": 1.1,
            "intervalo": 1.1,
            "tendencia": 1.2
        }

    def _frequencias(self):
        c = Counter()
        for con in self.concursos: 
            c.update(con)
        # Normalizar com peso maior para concursos recentes
        frequencias_ponderadas = {}
        for n in self.numeros:
            peso_total = 0
            for i, con in enumerate(self.concursos):
                if n in con:
                    # Peso exponencial para concursos recentes
                    peso = 1.5 ** (self.total_concursos - i) / self.total_concursos
                    peso_total += peso
            frequencias_ponderadas[n] = float(peso_total / self.total_concursos * 2)
        return frequencias_ponderadas

    def _defasagens(self):
        d = {}
        for n in self.numeros:
            for i, c in enumerate(self.concursos):
                if n in c:
                    d[n] = int(i)
                    break
            else:
                d[n] = int(self.total_concursos)
        return d

    def _padroes(self):
        p = {"somas": [], "pares": []}
        for c in self.concursos:
            p["somas"].append(int(sum(c)))
            p["pares"].append(int(sum(1 for n in c if n % 2 == 0)))
        return p

    def _numeros_chave(self):
        cont = Counter()
        # Usar apenas os últimos 50 concursos para números-chave mais atuais
        for c in self.concursos[:30]: 
            cont.update(c)
        # Números que aparecem em mais de 30% dos concursos recentes
        limite = 50 * 0.3
        return [int(n) for n, q in cont.items() if q >= limite]

    def _analisar_padroes_repeticao(self):
        """Analisa padrões de repetição entre concursos consecutivos"""
        repeticoes = []
        for i in range(len(self.concursos) - 1):
            repetidos = len(set(self.concursos[i]) & set(self.concursos[i + 1]))
            repeticoes.append(int(repetidos))
        
        if repeticoes:
            media_repeticao = float(np.mean(repeticoes))
            desvio_repeticao = float(np.std(repeticoes))
            return {
                "media": media_repeticao,
                "desvio": desvio_repeticao,
                "ultima": int(repeticoes[0]) if repeticoes else 9,
                "tendencia": [int(r) for r in repeticoes[:10]]
            }
        return {"media": 9.0, "desvio": 2.0, "ultima": 9, "tendencia": [9] * 10}

    def _analisar_linhas_colunas(self):
        """Analisa distribuição por linhas (1-5,6-10,11-15,16-20,21-25)"""
        linhas = {1: [], 2: [], 3: [], 4: [], 5: []}
        for c in self.concursos[:30]:
            cont_linhas = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for n in c:
                linha = (n - 1) // 5 + 1
                cont_linhas[linha] += 1
            for linha in linhas:
                linhas[linha].append(cont_linhas[linha])
        
        return {f"linha_{l}": float(np.mean(cont)) for l, cont in linhas.items()}

    def _analisar_pares_impares(self):
        """Analisa tendência de pares/ímpares"""
        pares_tendencia = []
        for c in self.concursos[:20]:
            pares = sum(1 for n in c if n % 2 == 0)
            pares_tendencia.append(int(pares))
        
        if len(pares_tendencia) > 5:
            media_recente = float(np.mean(pares_tendencia[:5]))
            media_antiga = float(np.mean(pares_tendencia[5:10])) if len(pares_tendencia) > 10 else media_recente
            if media_recente > media_antiga:
                tendencia = "crescendo"
            elif media_recente < media_antiga:
                tendencia = "decrescendo"
            else:
                tendencia = "estavel"
        else:
            tendencia = "estavel"
        
        return {
            "media": float(np.mean(pares_tendencia)) if pares_tendencia else 7.5,
            "desvio": float(np.std(pares_tendencia)) if pares_tendencia else 1.0,
            "tendencia": tendencia,
            "ultimos": [int(p) for p in pares_tendencia[:5]]
        }

    def _analisar_intervalos(self):
        """Analisa intervalos médios entre números consecutivos"""
        intervalos = []
        for c in self.concursos[:30]:
            c_ordenado = sorted(c)
            diffs = [c_ordenado[i+1] - c_ordenado[i] for i in range(len(c_ordenado)-1)]
            intervalos.extend([int(d) for d in diffs])
        
        cont_intervalos = Counter(intervalos)
        intervalos_comuns = [(int(k), int(v)) for k, v in cont_intervalos.most_common(3)]
        
        return {
            "media_intervalo": float(np.mean(intervalos)) if intervalos else 1.6,
            "intervalos_comuns": intervalos_comuns
        }

    def score_numero_evolutivo(self, n):
        """Score avançado com múltiplos fatores"""
        score = 0.0
        
        # Frequência (ponderada)
        score += self.frequencias.get(n, 0.5) * self.dna_evolutivo["freq"]
        
        # Defasagem
        score += (1.0 - self.defasagens.get(n, self.total_concursos) / self.total_concursos) * self.dna_evolutivo["defas"]
        
        # Números-chave
        if n in self.numeros_chave:
            score += 0.8 * self.dna_evolutivo["chave"]
        
        # Tendência de repetição
        if self.concursos and n in self.concursos[0]:
            score += 0.5 * self.dna_evolutivo["repeticao"]
        elif len(self.concursos) > 1 and n in self.concursos[1]:
            score += 0.3 * self.dna_evolutivo["repeticao"]
        
        # Distribuição por linha
        linha = (n - 1) // 5 + 1
        media_linha = self.tendencias_linhas_colunas.get(f"linha_{linha}", 3.0)
        if media_linha > 2.8:
            score += 0.2 * self.dna_evolutivo["linha_coluna"]
        
        # Ajuste baseado em pares/ímpares
        par_impar_tend = self.pares_impares_tendencia["tendencia"]
        if (n % 2 == 0 and par_impar_tend == "crescendo") or (n % 2 == 1 and par_impar_tend == "decrescendo"):
            score += 0.2 * self.dna_evolutivo["tendencia"]
        
        return float(score)

    def gerar_fechamento_evolutivo(self, tamanho=17):
        """Gera fechamento usando o score evolutivo - GARANTE NÚMEROS ÚNICOS"""
        scores = {n: self.score_numero_evolutivo(n) for n in self.numeros}
        
        # Ordenar por score
        numeros_ordenados = sorted(scores, key=scores.get, reverse=True)
        
        # Pegar os melhores números (garantindo que são únicos)
        fechamento = list(numeros_ordenados[:tamanho-2])
        
        # Adicionar 2 números do meio para diversidade (garantindo que não há duplicatas)
        disponiveis = [n for n in numeros_ordenados[tamanho-2:] if n not in fechamento]
        if len(disponiveis) >= 2:
            extras = random.sample(disponiveis, 2)
            fechamento.extend(extras)
        else:
            # Se não houver suficientes, pegar do início (garantindo que não duplica)
            for n in numeros_ordenados:
                if n not in fechamento and len(fechamento) < tamanho:
                    fechamento.append(n)
        
        return sorted([int(n) for n in fechamento])

    def gerar_jogos_otimizados(self, fechamento, qtd_jogos=8):
        """Gera jogos com otimização - GARANTE QUE CADA JOGO TEM 15 NÚMEROS ÚNICOS"""
        jogos = set()
        tentativas = 0
        max_tentativas = 1000
        
        # Parâmetros ideais
        soma_alvo = 195
        pares_alvo = 7
        variacao_soma = 15
        variacao_pares = 2
        
        # Garantir que o fechamento não tem duplicatas
        fechamento = sorted(list(set(fechamento)))
        
        while len(jogos) < qtd_jogos and tentativas < max_tentativas:
            # Escolher números aleatórios do fechamento SEM REPETIÇÃO
            # sample já garante que não há repetição
            if len(fechamento) >= 15:
                jogo = sorted(random.sample(fechamento, 15))
            else:
                # Se fechamento for menor que 15, completar com números aleatórios
                jogo = sorted(random.sample(fechamento, len(fechamento)))
                # Adicionar números faltantes de fora do fechamento (garantindo unicidade)
                while len(jogo) < 15:
                    novo_num = random.randint(1, 25)
                    if novo_num not in jogo:
                        jogo.append(novo_num)
                jogo.sort()
            
            # Verificar soma e pares
            soma = sum(jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)
            
            # Critérios de aceitação
            if (soma_alvo - variacao_soma <= soma <= soma_alvo + variacao_soma and
                pares_alvo - variacao_pares <= pares <= pares_alvo + variacao_pares):
                # Converter para tupla e adicionar ao set (já garante unicidade)
                jogos.add(tuple(jogo))
            
            tentativas += 1
        
        # Se não conseguir todos, gerar jogos aleatórios SEM REPETIÇÃO
        while len(jogos) < qtd_jogos:
            # Gerar jogo aleatório SEM números repetidos
            jogo = sorted(random.sample(range(1, 26), 15))
            jogos.add(tuple(jogo))
        
        # Converter de volta para lista e garantir que cada jogo está ordenado
        jogos_lista = [list(j) for j in jogos]
        
        # Verificação final de segurança
        for jogo in jogos_lista:
            assert len(set(jogo)) == 15, f"Jogo tem números repetidos: {jogo}"
        
        return jogos_lista

    def aprender_com_resultados(self, jogos_gerados, resultado_real):
        """Aprende com os resultados"""
        acertos_por_jogo = [len(set(j) & set(resultado_real)) for j in jogos_gerados]
        media_acertos = float(np.mean(acertos_por_jogo))
        
        if media_acertos > 9.5:
            for num in resultado_real:
                if num in self.frequencias:
                    self.frequencias[num] = float(self.frequencias[num] * 1.05)
        elif media_acertos < 8.5:
            for num in set().union(*jogos_gerados) - set(resultado_real):
                if num in self.frequencias:
                    self.frequencias[num] = float(self.frequencias[num] * 0.98)
        
        self.historico_acertos.append(media_acertos)
        return media_acertos

    def auto_ajustar_dna(self, concurso_real):
        """Ajuste fino do DNA"""
        lr = 0.03
        soma_r = sum(concurso_real)
        pares_r = sum(1 for n in concurso_real if n % 2 == 0)
        soma_m = float(np.mean(self.padroes["somas"]))
        pares_m = float(np.mean(self.padroes["pares"]))
        
        self.dna_evolutivo["soma"] += lr if abs(soma_r - soma_m) < 15 else -lr/2
        self.dna_evolutivo["pares"] += lr if abs(pares_r - pares_m) < 2 else -lr/2
        
        if self.padroes_repeticao:
            rep_esperada = self.padroes_repeticao["media"]
            rep_real = len(set(concurso_real) & set(self.concursos[0] if self.concursos else []))
            self.dna_evolutivo["repeticao"] += lr if abs(rep_real - rep_esperada) < 2 else -lr/2
        
        for k in self.dna_evolutivo:
            self.dna_evolutivo[k] = float(max(0.7, min(1.8, self.dna_evolutivo[k])))

    def comparar_com_aleatorio(self, jogos_gerados, num_simulacoes=1000):
        """Compara desempenho com escolhas aleatórias"""
        acertos_sistema = []
        acertos_aleatorio = []
        
        for _ in range(min(num_simulacoes, 100)):
            resultado_simulado = sorted(random.sample(range(1, 26), 15))
            
            for jogo in jogos_gerados:
                acertos_sistema.append(len(set(jogo) & set(resultado_simulado)))
            
            for _ in range(len(jogos_gerados)):
                aleatorio = sorted(random.sample(range(1, 26), 15))
                acertos_aleatorio.append(len(set(aleatorio) & set(resultado_simulado)))
        
        stats = {
            "sistema_media": float(np.mean(acertos_sistema)) if acertos_sistema else 0.0,
            "sistema_max": int(np.max(acertos_sistema)) if acertos_sistema else 0,
            "aleatorio_media": float(np.mean(acertos_aleatorio)) if acertos_aleatorio else 0.0,
            "aleatorio_max": int(np.max(acertos_aleatorio)) if acertos_aleatorio else 0,
            "vantagem_media": float(np.mean(acertos_sistema) - np.mean(acertos_aleatorio)) if acertos_sistema and acertos_aleatorio else 0.0
        }
        
        return stats

    def conferir(self, jogos, resultado):
        dados = []
        for i, j in enumerate(jogos, 1):
            # Garantir que o jogo não tem números repetidos antes de conferir
            if len(set(j)) != 15:
                st.warning(f"Jogo {i} tem números repetidos! Corrigindo...")
                j = sorted(list(set(j)))
                while len(j) < 15:
                    novo = random.randint(1, 25)
                    if novo not in j:
                        j.append(novo)
                j.sort()
            
            dados.append({
                "Jogo": i,
                "Dezenas": ", ".join(f"{n:02d}" for n in j),
                "Acertos": int(len(set(j) & set(resultado))),
                "Soma": int(sum(j)),
                "Pares": int(sum(1 for n in j if n % 2 == 0))
            })
        return pd.DataFrame(dados)

# =====================================================
# NOVA CLASSE: ANÁLISE DE JOGOS HISTÓRICOS (600 CONCURSOS)
# =====================================================
class AnaliseHistoricaLotofacil:
    """
    Análise aprofundada dos 600 concursos históricos
    Identifica padrões reais para geração de jogos inteligentes
    """
    
    def __init__(self, concursos_historicos, dados_completos=None):
        self.concursos = concursos_historicos  # Lista de listas com números
        self.dados_completos = dados_completos or []  # Dados completos da API
        self.total_concursos = len(concursos_historicos)
        self.numeros = list(range(1, 26))
        
        # Análises principais
        self.frequencias = self._calcular_frequencias()
        self.numeros_quentes = self._identificar_quentes_frios()[0]
        self.numeros_frios = self._identificar_quentes_frios()[1]
        self.numeros_atrasados = self._calcular_atraso()
        self.numeros_repetentes = self._identificar_repetentes_recentes()
        
        # Padrões estatísticos
        self.padroes_pares_impares = self._analisar_pares_impares()
        self.padroes_soma = self._analisar_somas()
        self.padroes_primos = self._analisar_numeros_primos()
        self.padroes_linhas = self._analisar_linhas()
        self.padroes_repeticao_entre_concursos = self._analisar_repeticao_entre_concursos()
        
        # Estatísticas descritivas
        self.estatisticas_gerais = self._calcular_estatisticas_gerais()
        
    def _calcular_frequencias(self):
        """Calcula frequência absoluta e relativa de cada número"""
        contador = Counter()
        for concurso in self.concursos:
            contador.update(concurso)
        
        frequencias = {}
        for num in self.numeros:
            frequencias[num] = {
                'absoluta': contador[num],
                'relativa': contador[num] / self.total_concursos * 100,
                'percentual': (contador[num] / self.total_concursos) * 100
            }
        return frequencias
    
    def _identificar_quentes_frios(self, top_n=8):
        """Identifica números quentes (mais frequentes) e frios (menos frequentes)"""
        sorted_nums = sorted(
            self.numeros, 
            key=lambda x: self.frequencias[x]['absoluta'], 
            reverse=True
        )
        quentes = sorted_nums[:top_n]
        frios = sorted_nums[-top_n:]
        return quentes, frios
    
    def _calcular_atraso(self, ultimos_n_concursos=10):
        """Calcula números mais atrasados (que não aparecem há mais tempo)"""
        ultimos_concursos = self.concursos[:ultimos_n_concursos]
        numeros_ultimos = set()
        for concurso in ultimos_concursos:
            numeros_ultimos.update(concurso)
        
        atrasados = []
        for num in self.numeros:
            if num not in numeros_ultimos:
                atrasados.append(num)
            else:
                # Verificar há quantos concursos não aparece
                for i, concurso in enumerate(self.concursos[:30]):  # Verificar últimos 30
                    if num in concurso:
                        if i > 5:  # Se passou mais de 5 concursos
                            atrasados.append(num)
                        break
        
        return sorted(list(set(atrasados)))[:10]  # Top 10 atrasados
    
    def _identificar_repetentes_recentes(self, ultimos_n=5):
        """Identifica números que se repetem muito nos últimos concursos"""
        ultimos_concursos = self.concursos[:ultimos_n]
        contador_recente = Counter()
        for concurso in ultimos_concursos:
            contador_recente.update(concurso)
        
        repetentes = []
        for num, freq in contador_recente.most_common():
            if freq >= 3:  # Apareceu em pelo menos 3 dos últimos 5
                repetentes.append(num)
        
        return repetentes[:8]  # Top 8 repetentes
    
    def _analisar_pares_impares(self):
        """Analisa distribuição de pares e ímpares nos concursos"""
        distribuicao = []
        for concurso in self.concursos:
            pares = sum(1 for n in concurso if n % 2 == 0)
            impares = 15 - pares
            distribuicao.append({
                'pares': pares,
                'impares': impares,
                'tipo': f"{pares}-{impares}"
            })
        
        # Contar frequência de cada tipo
        tipos = Counter([d['tipo'] for d in distribuicao])
        
        return {
            'distribuicao': distribuicao,
            'tipos_frequentes': tipos.most_common(3),
            'media_pares': float(np.mean([d['pares'] for d in distribuicao])),
            'desvio_pares': float(np.std([d['pares'] for d in distribuicao])),
            'tipo_dominante': tipos.most_common(1)[0][0] if tipos else "8-7"
        }
    
    def _analisar_somas(self):
        """Analisa a soma dos números em cada concurso"""
        somas = [sum(concurso) for concurso in self.concursos]
        
        return {
            'somas': somas,
            'media': float(np.mean(somas)),
            'mediana': float(np.median(somas)),
            'minimo': int(min(somas)),
            'maximo': int(max(somas)),
            'desvio': float(np.std(somas)),
            'intervalo_confianca': (
                int(np.mean(somas) - np.std(somas)),
                int(np.mean(somas) + np.std(somas))
            ),
            'faixa_mais_comum': (180, 210)  # Faixa observada empiricamente
        }
    
    def _analisar_numeros_primos(self):
        """Analisa quantidade de números primos por concurso"""
        primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        qtd_primos = []
        
        for concurso in self.concursos:
            qtd = sum(1 for n in concurso if n in primos)
            qtd_primos.append(qtd)
        
        distribuicao = Counter(qtd_primos)
        
        return {
            'quantidades': qtd_primos,
            'media': float(np.mean(qtd_primos)),
            'mediana': float(np.median(qtd_primos)),
            'moda': int(distribuicao.most_common(1)[0][0]) if distribuicao else 5,
            'distribuicao': dict(distribuicao.most_common()),
            'faixa_ideal': (5, 6)  # 5 ou 6 primos é o mais comum
        }
    
    def _analisar_linhas(self):
        """Analisa distribuição por linhas (1-5, 6-10, 11-15, 16-20, 21-25)"""
        linhas = {1: [], 2: [], 3: [], 4: [], 5: []}
        
        for concurso in self.concursos:
            cont_linhas = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for n in concurso:
                linha = (n - 1) // 5 + 1
                cont_linhas[linha] += 1
            
            for linha in linhas:
                linhas[linha].append(cont_linhas[linha])
        
        return {
            f"linha_{l}": {
                'media': float(np.mean(cont)) if cont else 3.0,
                'desvio': float(np.std(cont)) if cont else 1.0,
                'min': int(min(cont)) if cont else 0,
                'max': int(max(cont)) if cont else 5
            } for l, cont in linhas.items()
        }
    
    def _analisar_repeticao_entre_concursos(self):
        """Analisa quantos números se repetem entre concursos consecutivos"""
        repeticoes = []
        for i in range(len(self.concursos) - 1):
            repetidos = len(set(self.concursos[i]) & set(self.concursos[i + 1]))
            repeticoes.append(repetidos)
        
        return {
            'media': float(np.mean(repeticoes)) if repeticoes else 9.0,
            'desvio': float(np.std(repeticoes)) if repeticoes else 2.0,
            'min': int(min(repeticoes)) if repeticoes else 5,
            'max': int(max(repeticoes)) if repeticoes else 13,
            'distribuicao': dict(Counter(repeticoes).most_common(5)) if repeticoes else {}
        }
    
    def _calcular_estatisticas_gerais(self):
        """Calcula estatísticas descritivas gerais"""
        return {
            'total_concursos': self.total_concursos,
            'periodo': {
                'inicio': self.dados_completos[-1]['data'] if self.dados_completos else 'N/A',
                'fim': self.dados_completos[0]['data'] if self.dados_completos else 'N/A'
            },
            'frequencia_media': float(np.mean([self.frequencias[n]['absoluta'] for n in self.numeros])),
            'numeros_por_faixa': self._classificar_por_faixa()
        }
    
    def _classificar_por_faixa(self):
        """Classifica números por faixa de frequência"""
        faixas = {
            'quentes': [],
            'neutros': [],
            'frios': []
        }
        
        for num in self.numeros:
            freq = self.frequencias[num]['absoluta']
            if freq > np.mean([self.frequencias[n]['absoluta'] for n in self.numeros]) + np.std([self.frequencias[n]['absoluta'] for n in self.numeros]):
                faixas['quentes'].append(num)
            elif freq < np.mean([self.frequencias[n]['absoluta'] for n in self.numeros]) - np.std([self.frequencias[n]['absoluta'] for n in self.numeros]):
                faixas['frios'].append(num)
            else:
                faixas['neutros'].append(num)
        
        return faixas
    
    def gerar_jogo_historico_inteligente(self):
        """
        Gera um jogo baseado nos padrões históricos reais
        Usa os padrões identificados para criar combinações mais prováveis
        """
        # Peso para cada número baseado em múltiplos fatores
        pesos = {}
        for num in self.numeros:
            peso = 1.0
            
            # Fator frequência (quentes têm mais peso)
            if num in self.numeros_quentes:
                peso *= 2.5
            elif num in self.numeros_frios:
                peso *= 0.8
            
            # Fator atraso (atrasados têm mais chance de sair)
            if num in self.numeros_atrasados:
                peso *= 2.0
            
            # Fator repetição recente
            if num in self.numeros_repetentes:
                peso *= 1.5
            
            pesos[num] = peso
        
        # Gerar jogos até encontrar um que satisfaça todos os padrões
        max_tentativas = 5000
        for _ in range(max_tentativas):
            # Selecionar números baseado nos pesos
            numeros_pesados = []
            for num, peso in pesos.items():
                numeros_pesados.extend([num] * int(peso * 10))
            
            jogo = []
            while len(jogo) < 15:
                candidato = random.choice(numeros_pesados)
                if candidato not in jogo:
                    jogo.append(candidato)
            jogo.sort()
            
            # Validar padrões
            if self._validar_jogo_padroes(jogo):
                return jogo
        
        # Fallback: gerar jogo aleatório balanceado
        return self._gerar_jogo_balanceado()
    
    def _validar_jogo_padroes(self, jogo):
        """Valida se o jogo segue os padrões históricos"""
        
        # 1. Validar pares/ímpares
        pares = sum(1 for n in jogo if n % 2 == 0)
        if pares not in [7, 8]:
            return False
        
        # 2. Validar soma
        soma = sum(jogo)
        faixa_soma = self.padroes_soma['faixa_mais_comum']
        if not (faixa_soma[0] <= soma <= faixa_soma[1]):
            return False
        
        # 3. Validar números primos
        primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        qtd_primos = sum(1 for n in jogo if n in primos)
        faixa_primos = self.padroes_primos['faixa_ideal']
        if not (faixa_primos[0] <= qtd_primos <= faixa_primos[1]):
            return False
        
        # 4. Validar distribuição por linhas (não pode ter linha vazia)
        linhas_presentes = set()
        for n in jogo:
            linha = (n - 1) // 5 + 1
            linhas_presentes.add(linha)
        
        if len(linhas_presentes) < 4:  # Pelo menos 4 linhas diferentes
            return False
        
        return True
    
    def _gerar_jogo_balanceado(self):
        """Gera um jogo balanceado como fallback"""
        while True:
            jogo = sorted(random.sample(range(1, 26), 15))
            pares = sum(1 for n in jogo if n % 2 == 0)
            if pares in [7, 8] and 180 <= sum(jogo) <= 210:
                return jogo
    
    def gerar_multiplos_jogos(self, quantidade=10):
        """Gera múltiplos jogos baseados nos padrões históricos"""
        jogos = []
        tentativas = 0
        max_tentativas = quantidade * 100
        
        while len(jogos) < quantidade and tentativas < max_tentativas:
            jogo = self.gerar_jogo_historico_inteligente()
            if jogo not in jogos:
                jogos.append(jogo)
            tentativas += 1
        
        return jogos
    
    def get_resumo_padroes(self):
        """Retorna um resumo formatado dos padrões encontrados"""
        return {
            'numeros_quentes': self.numeros_quentes,
            'numeros_frios': self.numeros_frios,
            'numeros_atrasados': self.numeros_atrasados[:8],
            'numeros_repetentes': self.numeros_repetentes,
            'padrao_pares_impares': self.padroes_pares_impares['tipo_dominante'],
            'faixa_soma_ideal': self.padroes_soma['faixa_mais_comum'],
            'qtd_primos_ideal': self.padroes_primos['faixa_ideal'],
            'media_repeticao': f"{self.padroes_repeticao_entre_concursos['media']:.1f}"
        }

# =====================================================
# FUNÇÕES AUXILIARES PARA ANÁLISE HISTÓRICA
# =====================================================
def criar_analise_historica(concursos, dados_completos, qtd_concursos=600):
    """Cria análise histórica com os concursos carregados"""
    # Pegar apenas os primeiros N concursos (mais antigos para mais recentes)
    # Como a API retorna do mais recente para o mais antigo, invertemos
    concursos_historicos = [sorted(map(int, d["dezenas"])) for d in dados_completos[:qtd_concursos]]
    
    # Inverter para ordem cronológica (mais antigo primeiro)
    concursos_historicos.reverse()
    dados_historicos = list(reversed(dados_completos[:qtd_concursos]))
    
    return AnaliseHistoricaLotofacil(concursos_historicos, dados_historicos)

def formatar_numero_com_cor(num, analise_historica):
    """Formata número com cor baseada em sua classificação"""
    if num in analise_historica.numeros_quentes:
        return f"<span style='color:#ff6b6b; font-weight:bold;'>{num:02d} 🔥</span>"
    elif num in analise_historica.numeros_frios:
        return f"<span style='color:#4ade80; font-weight:bold;'>{num:02d} ❄️</span>"
    elif num in analise_historica.numeros_atrasados:
        return f"<span style='color:#f97316; font-weight:bold;'>{num:02d} ⏰</span>"
    elif num in analise_historica.numeros_repetentes:
        return f"<span style='color:#4cc9f0; font-weight:bold;'>{num:02d} 🔁</span>"
    else:
        return f"<span style='color:white;'>{num:02d}</span>"

# =====================================================
# FUNÇÕES DE REPETIÇÃO
# =====================================================
def repeticao_ultimo_antepenultimo(concursos):
    if len(concursos) < 3: return None
    ultimo = set(concursos[0])
    antepenultimo = set(concursos[2])
    repetidos = len(ultimo & antepenultimo)
    media = repetidos / 15
    return int(repetidos), float(media)

def repeticao_ultimo_penultimo(concursos):
    if len(concursos) < 2: return None
    ultimo = set(concursos[0])
    penultimo = set(concursos[1])
    repetidos = len(ultimo & penultimo)
    media = repetidos / 15
    return int(repetidos), float(media)

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def get_concurso_info_seguro(jogo):
    try:
        if "concurso_base" in jogo:
            return jogo["concurso_base"]
        else:
            return {"numero": 0, "data": "Formato antigo"}
    except:
        return {"numero": 0, "data": "Desconhecido"}

def get_conferencias_seguro(jogo):
    try:
        if "conferencias" in jogo:
            return jogo["conferencias"]
        else:
            return []
    except:
        return []

def validar_jogos(jogos):
    """Valida se todos os jogos têm 15 números únicos"""
    for i, jogo in enumerate(jogos):
        if len(set(jogo)) != 15:
            return False, i, jogo
    return True, None, None

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================
def main():
    if "analise" not in st.session_state: 
        st.session_state.analise = None
    if "jogos" not in st.session_state: 
        st.session_state.jogos = []
    if "dados_api" not in st.session_state: 
        st.session_state.dados_api = None
    if "jogos_salvos" not in st.session_state: 
        st.session_state.jogos_salvos = []
    if "historico_comparacao" not in st.session_state:
        st.session_state.historico_comparacao = []

    # ================= SIDEBAR =================
    with st.sidebar:
        st.header("⚙️ Configurações")
        qtd = st.slider("Qtd concursos históricos", 20, 1000, 300, 
                       help="Mais concursos = melhor análise de tendências")
        
        if st.button("📥 Carregar concursos", use_container_width=True):
            with st.spinner("Carregando dados da Caixa..."):
                try:
                    url = "https://loteriascaixa-api.herokuapp.com/api/lotofacil/"
                    response = requests.get(url)
                    st.session_state.dados_api = response.json()
                    concursos = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
                    st.session_state.analise = AnaliseLotofacilAvancada(concursos, st.session_state.dados_api[:qtd])
                    
                    st.session_state.analise.auto_ajustar_dna(concursos[0])
                    
                    ultimo = st.session_state.dados_api[0]
                    st.success(f"✅ Último concurso: #{ultimo['concurso']} - {ultimo['data']}")

                    rep_penultimo = repeticao_ultimo_penultimo(concursos)
                    if rep_penultimo:
                        repetidos, media = rep_penultimo
                        st.info(f"🔁 Repetição último x penúltimo: {repetidos} ({media*100:.1f}%)")
                    
                    st.info("🔄 DNA Evolutivo ativado - Sem números repetidos!")
                    
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    # ================= INTERFACE PRINCIPAL =================
    st.subheader("🎯 Análise e Fechamento Evolutivo")

    if st.session_state.analise:
        # CORREÇÃO: Adicionar vírgulas entre os nomes das abas
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 Análise", 
            "🧩 Fechamento", 
            "🧬 DNA", 
            "✅ Conferência", 
            "📈 Comparação", 
            "📋 Concursos",
            "📊 Jogos Históricos"
        ])

        with tab1:
            st.markdown("### 🔑 Números-chave (últimos 20 concursos)")
            numeros_chave = st.session_state.analise.numeros_chave
            if numeros_chave:
                colunas = st.columns(5)
                for i, num in enumerate(sorted(numeros_chave)[:15]):
                    with colunas[i % 5]:
                        st.markdown(f"<h3 style='text-align:center'>{num:02d}</h3>", unsafe_allow_html=True)
            else:
                st.info("Poucos números-chave identificados")
            
            st.markdown("### 📊 Tendências Atuais")
            col1, col2, col3 = st.columns(3)
            with col1:
                media_repeticao = st.session_state.analise.padroes_repeticao.get("media", 9.0)
                st.metric("Média repetição", f"{media_repeticao:.1f}")
            with col2:
                media_pares = st.session_state.analise.pares_impares_tendencia.get("media", 7.5)
                st.metric("Média pares", f"{media_pares:.1f}")
            with col3:
                tendencia = st.session_state.analise.pares_impares_tendencia.get("tendencia", "estavel")
                st.metric("Tendência", tendencia.capitalize())

        with tab2:
            st.subheader("🧩 Fechamento Evolutivo")
            
            if st.session_state.dados_api:
                ultimo = st.session_state.dados_api[0]
                st.markdown(f"""
                <div class='concurso-info'>
                    📅 <strong>Base: concurso #{ultimo['concurso']}</strong> - {ultimo['data']}
                </div>
                """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                tamanho = st.radio("Tamanho", [16, 17, 18], horizontal=True, key="tam_fech_evo")
            with col2:
                qtd_jogos = st.slider("Jogos", 6, 12, 8, key="qtd_jogos_evo")

            if st.button("🚀 Gerar Fechamento Evolutivo", use_container_width=True):
                with st.spinner("Gerando jogos otimizados (sem repetições)..."):
                    # Gerar fechamento
                    fechamento = st.session_state.analise.gerar_fechamento_evolutivo(tamanho)
                    jogos = st.session_state.analise.gerar_jogos_otimizados(fechamento, qtd_jogos)
                    
                    # Validar jogos
                    valido, idx, jogo_invalido = validar_jogos(jogos)
                    if not valido:
                        st.error(f"ERRO: Jogo {idx+1} tem números repetidos! Corrigindo...")
                        # Corrigir o jogo problemático
                        jogos[idx] = sorted(list(set(jogo_invalido)))
                        while len(jogos[idx]) < 15:
                            novo = random.randint(1, 25)
                            if novo not in jogos[idx]:
                                jogos[idx].append(novo)
                        jogos[idx].sort()
                    
                    # Comparar com aleatório
                    stats_comparacao = st.session_state.analise.comparar_com_aleatorio(jogos)
                    
                    # Salvar jogos
                    ultimo = st.session_state.dados_api[0]
                    arquivo, jogo_id = salvar_jogos_gerados(
                        jogos, fechamento, 
                        st.session_state.analise.dna_evolutivo,
                        ultimo['concurso'], ultimo['data'],
                        estatisticas=stats_comparacao
                    )
                    
                    if arquivo:
                        st.success(f"✅ Fechamento salvo! ID: {jogo_id}")
                        
                        vantagem = stats_comparacao["vantagem_media"]
                        if vantagem > 0:
                            st.markdown(f"""
                            <div style='background: #00ff0022; padding: 10px; border-radius: 10px; text-align: center;'>
                                🏆 <strong>Vantagem sobre aleatório: {vantagem:.2f} pontos</strong>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style='background: #ff000022; padding: 10px; border-radius: 10px; text-align: center;'>
                                ⚠️ <strong>Desvantagem: {abs(vantagem):.2f} pontos</strong>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("### 🔒 Fechamento Base")
                        st.markdown(f"<div class='card'>{', '.join(f'{n:02d}' for n in fechamento)}</div>", 
                                  unsafe_allow_html=True)
                        
                        # Mostrar jogos com verificação de unicidade
                        df_jogos = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Qtd": [len(set(j)) for j in jogos],  # Coluna de verificação
                            "Soma": [sum(j) for j in jogos],
                            "Pares": [sum(1 for n in j if n%2==0) for j in jogos]
                        })
                        st.dataframe(df_jogos, use_container_width=True, hide_index=True)
                        
                        st.caption("✅ Todos os jogos têm 15 números únicos")
                        
                        st.session_state.jogos_salvos = carregar_jogos_salvos()
                        
                        st.session_state.historico_comparacao.append({
                            "id": jogo_id,
                            "concurso_base": int(ultimo['concurso']),
                            "vantagem": float(vantagem),
                            "stats": stats_comparacao
                        })

        with tab3:
            st.subheader("🧬 DNA Evolutivo Atual")
            
            dna = st.session_state.analise.dna_evolutivo
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Fatores Principais:**")
                for key in ["freq", "defas", "chave", "repeticao"]:
                    if key in dna:
                        st.metric(key.capitalize(), f"{dna[key]:.2f}")
            
            with col2:
                st.markdown("**Fatores de Ajuste:**")
                for key in ["soma", "pares", "linha_coluna", "tendencia"]:
                    if key in dna:
                        st.metric(key.replace("_", " ").capitalize(), f"{dna[key]:.2f}")
            
            if st.button("🔄 Recalibrar DNA", use_container_width=True):
                if st.session_state.dados_api and len(st.session_state.dados_api) > 1:
                    segundo_ultimo = st.session_state.dados_api[1]
                    numeros_segundo = sorted(map(int, segundo_ultimo["dezenas"]))
                    st.session_state.analise.auto_ajustar_dna(numeros_segundo)
                    st.success("DNA recalibrado com sucesso!")
                    st.rerun()

        with tab4:
            st.subheader("✅ Conferência por Concurso")
            
            # Inicializar variáveis de sessão para persistência
            if "idx_fechamento_selecionado" not in st.session_state:
                st.session_state.idx_fechamento_selecionado = 0
            if "futuro_selecionado" not in st.session_state:
                st.session_state.futuro_selecionado = None
            if "conferencia_realizada" not in st.session_state:
                st.session_state.conferencia_realizada = False
            if "resultado_conferencia" not in st.session_state:
                st.session_state.resultado_conferencia = None
            
            st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            if not st.session_state.jogos_salvos:
                st.warning("Nenhum jogo salvo. Gere na aba 'Fechamento'.")
            elif not st.session_state.dados_api:
                st.warning("Carregue os concursos primeiro!")
            else:
                ultimo_api = st.session_state.dados_api[0]
                
                nao_conferidos = [j for j in st.session_state.jogos_salvos 
                                 if len(get_conferencias_seguro(j)) == 0]
                
                if not nao_conferidos:
                    st.info("✅ Todos os fechamentos já foram conferidos!")
                else:
                    st.markdown(f"""
                    <div class='concurso-info'>
                        🎯 Último concurso: #{ultimo_api['concurso']} - {ultimo_api['data']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Criar opções para o selectbox
                    opcoes = []
                    for i, j in enumerate(nao_conferidos[:10]):
                        data = datetime.fromisoformat(j["data_geracao"]).strftime("%d/%m/%Y %H:%M")
                        base = get_concurso_info_seguro(j)
                        opcoes.append(f"{i+1} - Base #{base['numero']} - {data}")
                    
                    if opcoes:
                        # Usar session_state para manter a seleção
                        opcao_selecionada = st.selectbox(
                            "Selecione o fechamento", 
                            opcoes,
                            index=st.session_state.idx_fechamento_selecionado,
                            key="select_fechamento"
                        )
                        
                        # Atualizar o índice no session_state quando mudar
                        novo_idx = int(opcao_selecionada.split(" - ")[0]) - 1
                        if novo_idx != st.session_state.idx_fechamento_selecionado:
                            st.session_state.idx_fechamento_selecionado = novo_idx
                            st.session_state.conferencia_realizada = False
                            st.session_state.resultado_conferencia = None
                            st.rerun()
                        
                        idx = st.session_state.idx_fechamento_selecionado
                        jogo_sel = nao_conferidos[idx]
                        base_info = get_concurso_info_seguro(jogo_sel)
                        
                        with st.expander("📋 Detalhes do fechamento", expanded=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**ID:** {jogo_sel['id']}")
                                st.write(f"**Base concurso:** #{base_info['numero']}")
                            with col2:
                                st.write(f"**Fechamento:** {len(jogo_sel['fechamento_base'])} números")
                                if "estatisticas" in jogo_sel and jogo_sel["estatisticas"]:
                                    vantagem = jogo_sel["estatisticas"].get("vantagem_media", 0)
                                    st.write(f"**Vantagem estimada:** {vantagem:.2f}")
                            
                            # Mostrar jogos do fechamento
                            with st.expander("🔍 Ver jogos do fechamento"):
                                df_preview = pd.DataFrame({
                                    "Jogo": range(1, len(jogo_sel["jogos"][:5])+1),
                                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogo_sel["jogos"][:5]]
                                })
                                st.dataframe(df_preview, use_container_width=True, hide_index=True)
                                if len(jogo_sel["jogos"]) > 5:
                                    st.caption(f"... e mais {len(jogo_sel['jogos']) - 5} jogos")
                        
                        # Concursos futuros disponíveis
                        concursos_futuros = [c for c in st.session_state.dados_api 
                                            if c['concurso'] > base_info['numero']]
                        
                        if concursos_futuros:
                            opcoes_futuros = [f"#{c['concurso']} - {c['data']}" 
                                             for c in concursos_futuros[:5]]
                            
                            # Definir índice padrão para o selectbox de futuro
                            futuro_idx = 0
                            if st.session_state.futuro_selecionado:
                                for i, opt in enumerate(opcoes_futuros):
                                    if f"#{st.session_state.futuro_selecionado}" in opt:
                                        futuro_idx = i
                                        break
                            
                            futuro_sel = st.selectbox(
                                "Concurso para conferir", 
                                opcoes_futuros,
                                index=futuro_idx,
                                key="select_futuro"
                            )
                            
                            num_futuro = int(futuro_sel.split(" - ")[0].replace("#", ""))
                            st.session_state.futuro_selecionado = num_futuro
                            
                            # Botão de conferência
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                if st.button("🔍 CONFERIR AGORA", use_container_width=True, type="primary"):
                                    with st.spinner("Conferindo resultados..."):
                                        concurso_info = next(c for c in concursos_futuros 
                                                            if c['concurso'] == num_futuro)
                                        numeros = sorted(map(int, concurso_info["dezenas"]))
                                        
                                        # Processar jogos para conferência
                                        acertos = []
                                        jogos_validos = []
                                        
                                        if isinstance(jogo_sel["jogos"], list):
                                            for jogo in jogo_sel["jogos"]:
                                                # Converter para lista se necessário
                                                if isinstance(jogo, (list, tuple)):
                                                    jogo_lista = list(jogo)
                                                elif isinstance(jogo, str):
                                                    try:
                                                        jogo_lista = [int(x.strip()) for x in jogo.replace('[', '').replace(']', '').split(',')]
                                                    except:
                                                        jogo_lista = []
                                                else:
                                                    jogo_lista = []
                                                
                                                # Validar jogo
                                                if jogo_lista and len(set(jogo_lista)) == 15:
                                                    jogos_validos.append(jogo_lista)
                                                    acertos.append(len(set(jogo_lista) & set(numeros)))
                                                else:
                                                    acertos.append(0)
                                        
                                        if acertos:
                                            # Calcular estatísticas
                                            stats_conf = {
                                                "media": float(np.mean(acertos)),
                                                "max": int(max(acertos)),
                                                "min": int(min(acertos)),
                                                "distribuicao": {str(k): int(v) for k, v in Counter(acertos).items()}
                                            }
                                            
                                            info_salvar = {
                                                "numero": int(concurso_info["concurso"]),
                                                "data": str(concurso_info["data"]),
                                                "resultado": [int(n) for n in numeros]
                                            }
                                            
                                            # Salvar conferência
                                            if adicionar_conferencia(jogo_sel["arquivo"], info_salvar, 
                                                                    acertos, stats_conf):
                                                # Guardar resultados na sessão
                                                st.session_state.conferencia_realizada = True
                                                st.session_state.resultado_conferencia = {
                                                    "acertos": acertos,
                                                    "jogos_validos": jogos_validos,
                                                    "stats": stats_conf,
                                                    "num_futuro": num_futuro,
                                                    "concurso_info": concurso_info
                                                }
                                                st.rerun()
                                        else:
                                            st.error("Não foi possível processar os jogos para conferência.")
                            
                            with col2:
                                if st.button("🔄 Limpar", use_container_width=True):
                                    st.session_state.conferencia_realizada = False
                                    st.session_state.resultado_conferencia = None
                                    st.rerun()
                            
                            # Mostrar resultados da conferência se existirem
                            if st.session_state.conferencia_realizada and st.session_state.resultado_conferencia:
                                resultado = st.session_state.resultado_conferencia
                                
                                st.success(f"✅ Conferência realizada com concurso #{resultado['num_futuro']}!")
                                
                                # Mostrar estatísticas
                                m1, m2, m3, m4 = st.columns(4)
                                with m1:
                                    st.metric("Média", f"{resultado['stats']['media']:.1f}")
                                with m2:
                                    st.metric("Máximo", resultado['stats']['max'])
                                with m3:
                                    st.metric("Mínimo", resultado['stats']['min'])
                                with m4:
                                    vantagem_real = resultado['stats']['media'] - 9.5
                                    cor = "green" if vantagem_real > 0 else "red"
                                    st.markdown(f"<p style='text-align:center; color:{cor}; font-weight:bold;'>Vs aleatório<br>{vantagem_real:+.2f}</p>", unsafe_allow_html=True)
                                
                                # Mostrar tabela de resultados
                                df_res = pd.DataFrame({
                                    "Jogo": range(1, len(resultado['jogos_validos'])+1),
                                    "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in resultado['jogos_validos']],
                                    "Acertos": resultado['acertos'][:len(resultado['jogos_validos'])]
                                })
                                st.dataframe(df_res, use_container_width=True, hide_index=True)
                                
                                # Gráfico de distribuição
                                if resultado['stats']['distribuicao']:
                                    st.subheader("📊 Distribuição de Acertos")
                                    df_dist = pd.DataFrame(
                                        list(resultado['stats']['distribuicao'].items()),
                                        columns=["Acertos", "Quantidade"]
                                    ).sort_values("Acertos")
                                    st.bar_chart(df_dist.set_index("Acertos"))
                                
                                # Botão para conferir outro
                                if st.button("✅ Conferir Outro Fechamento", use_container_width=True):
                                    st.session_state.conferencia_realizada = False
                                    st.session_state.resultado_conferencia = None
                                    st.rerun()
                        else:
                            st.warning("Aguardando próximos concursos...")    

        with tab5:
            st.subheader("📈 Comparação vs Aleatório")
            
            if st.session_state.historico_comparacao:
                df_hist = pd.DataFrame(st.session_state.historico_comparacao)
                
                st.line_chart(df_hist.set_index("concurso_base")["vantagem"])
                
                media_vantagem = df_hist["vantagem"].mean()
                if media_vantagem > 0:
                    st.success(f"🎯 Vantagem média: {media_vantagem:.2f} pontos")
                else:
                    st.warning(f"📉 Desvantagem média: {abs(media_vantagem):.2f} pontos")
                
                st.dataframe(df_hist[["concurso_base", "vantagem"]].tail(), 
                           use_container_width=True, hide_index=True)
            else:
                st.info("Gere fechamentos para ver a comparação com o aleatório")

        # ================= ABA: CONCURSOS =================
        with tab6:
            st.subheader("📋 Todos os Concursos Carregados")
            
            if st.session_state.dados_api:
                st.markdown(f"""
                <div class='concurso-info'>
                    📊 <strong>Total de concursos carregados: {len(st.session_state.dados_api[:qtd])}</strong>
                </div>
                """, unsafe_allow_html=True)
                
                # Opções de filtro
                col1, col2 = st.columns([3, 1])
                with col1:
                    busca = st.text_input("🔍 Buscar concurso específico (número ou data)", placeholder="Ex: 3000 ou 2024...")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📥 Download TXT", use_container_width=True):
                        conteudo_txt = exportar_concursos_txt(st.session_state.dados_api, qtd)
                        st.download_button(
                            label="⬇️ Baixar arquivo",
                            data=conteudo_txt,
                            file_name=f"lotofacil_concursos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                
                # Filtrar concursos
                dados_filtrados = st.session_state.dados_api[:qtd]
                if busca:
                    dados_filtrados = [
                        c for c in dados_filtrados 
                        if busca.lower() in str(c['concurso']).lower() 
                        or busca.lower() in c['data'].lower()
                    ]
                
                # Mostrar concursos em cards
                for concurso in dados_filtrados:
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.markdown(f"**#{concurso['concurso']}**")
                            st.caption(concurso['data'])
                        with col2:
                            numeros = sorted(map(int, concurso['dezenas']))
                            # Criar tags coloridas para os números
                            nums_html = ""
                            for i, num in enumerate(numeros):
                                cor = "#4cc9f0" if num <= 5 else "#4ade80" if num <= 10 else "gold" if num <= 15 else "#f97316" if num <= 20 else "#ff6b6b"
                                nums_html += f"<span style='background:{cor}20; border:1px solid {cor}; border-radius:20px; padding:5px 10px; margin:3px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
                            st.markdown(f"<div>{nums_html}</div>", unsafe_allow_html=True)
                        st.divider()
                
                # Paginação simples
                if len(dados_filtrados) > 50:
                    st.caption(f"Mostrando {len(dados_filtrados)} concursos. Use a busca para encontrar um específico.")
            else:
                st.info("📥 Carregue os concursos usando o botão na barra lateral para visualizar a lista completa.")
        
        # ================= NOVA ABA: JOGOS HISTÓRICOS (600 CONCURSOS) =================
        with tab7:
            st.subheader("📊 Análise de 600 Concursos Históricos")
            
            if not st.session_state.dados_api:
                st.warning("📥 Carregue os concursos primeiro usando o botão na barra lateral")
            else:
                # Inicializar análise histórica na session_state se não existir
                if "analise_historica" not in st.session_state:
                    with st.spinner("🔄 Analisando 600 concursos históricos..."):
                        st.session_state.analise_historica = criar_analise_historica(
                            st.session_state.analise.concursos if st.session_state.analise else [],
                            st.session_state.dados_api,
                            qtd_concursos=600
                        )
                
                analise_hist = st.session_state.analise_historica
                
                # Menu de opções para a aba histórica
                opcao_historica = st.radio(
                    "Selecione uma opção:",
                    ["📈 Visão Geral dos Padrões", "🎯 Gerar Jogos Inteligentes", "🔍 Explorar Números"],
                    horizontal=True
                )
                
                if opcao_historica == "📈 Visão Geral dos Padrões":
                    # Métricas principais
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Concursos", analise_hist.total_concursos)
                    with col2:
                        st.metric("Média Soma", f"{analise_hist.padroes_soma['media']:.0f}")
                    with col3:
                        st.metric("Média Pares", f"{analise_hist.padroes_pares_impares['media_pares']:.1f}")
                    with col4:
                        st.metric("Média Primos", f"{analise_hist.padroes_primos['media']:.1f}")
                    
                    # Números Quentes e Frios
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 🔥 Números Quentes (Mais Frequentes)")
                        quentes_html = ""
                        for num in analise_hist.numeros_quentes[:8]:
                            freq = analise_hist.frequencias[num]['percentual']
                            quentes_html += f"<span style='background:#ff6b6b20; border:1px solid #ff6b6b; border-radius:20px; padding:8px 12px; margin:5px; display:inline-block; font-weight:bold;'>{num:02d} ({freq:.1f}%)</span>"
                        st.markdown(f"<div>{quentes_html}</div>", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("### ❄️ Números Frios (Menos Frequentes)")
                        frios_html = ""
                        for num in analise_hist.numeros_frios[:8]:
                            freq = analise_hist.frequencias[num]['percentual']
                            frios_html += f"<span style='background:#4ade8020; border:1px solid #4ade80; border-radius:20px; padding:8px 12px; margin:5px; display:inline-block; font-weight:bold;'>{num:02d} ({freq:.1f}%)</span>"
                        st.markdown(f"<div>{frios_html}</div>", unsafe_allow_html=True)
                    
                    # Números Atrasados e Repetentes
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### ⏰ Números Atrasados (Maior Jejum)")
                        atrasados_html = ""
                        for num in analise_hist.numeros_atrasados[:8]:
                            atrasados_html += f"<span style='background:#f9731620; border:1px solid #f97316; border-radius:20px; padding:8px 12px; margin:5px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
                        st.markdown(f"<div>{atrasados_html}</div>", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("### 🔁 Números Repetentes (Últimos 5)")
                        repetentes_html = ""
                        for num in analise_hist.numeros_repetentes[:8]:
                            repetentes_html += f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:20px; padding:8px 12px; margin:5px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
                        st.markdown(f"<div>{repetentes_html}</div>", unsafe_allow_html=True)
                    
                    # Padrões Estatísticos
                    st.markdown("### 📊 Padrões Estatísticos Identificados")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**🎯 Pares/Ímpares**")
                        st.markdown(f"""
                        - Tipo dominante: **{analise_hist.padroes_pares_impares['tipo_dominante']}**
                        - Média de pares: **{analise_hist.padroes_pares_impares['media_pares']:.1f}**
                        - Desvio: ±{analise_hist.padroes_pares_impares['desvio_pares']:.1f}
                        """)
                    
                    with col2:
                        st.markdown("**➕ Soma dos Números**")
                        st.markdown(f"""
                        - Faixa ideal: **{analise_hist.padroes_soma['faixa_mais_comum'][0]}–{analise_hist.padroes_soma['faixa_mais_comum'][1]}**
                        - Média: **{analise_hist.padroes_soma['media']:.0f}**
                        - Intervalo confiança: **{analise_hist.padroes_soma['intervalo_confianca'][0]}–{analise_hist.padroes_soma['intervalo_confianca'][1]}**
                        """)
                    
                    with col3:
                        st.markdown("**🔢 Números Primos**")
                        st.markdown(f"""
                        - Quantidade ideal: **{analise_hist.padroes_primos['faixa_ideal'][0]}–{analise_hist.padroes_primos['faixa_ideal'][1]}**
                        - Média: **{analise_hist.padroes_primos['media']:.1f}**
                        - Moda: **{analise_hist.padroes_primos['moda']}** primos
                        """)
                    
                    # Tabela de frequência completa
                    with st.expander("📋 Ver tabela completa de frequência"):
                        freq_data = []
                        for num in range(1, 26):
                            freq_data.append({
                                "Número": num,
                                "Frequência": analise_hist.frequencias[num]['absoluta'],
                                "Percentual": f"{analise_hist.frequencias[num]['percentual']:.1f}%",
                                "Classificação": "Quente 🔥" if num in analise_hist.numeros_quentes else "Frio ❄️" if num in analise_hist.numeros_frios else "Normal"
                            })
                        df_freq = pd.DataFrame(freq_data)
                        st.dataframe(df_freq, use_container_width=True, hide_index=True)
                
                elif opcao_historica == "🎯 Gerar Jogos Inteligentes":
                    st.markdown("### 🎯 Jogos Baseados em Padrões Reais")
                    st.markdown("""
                    <div style='background:#1e1e2e; padding:10px; border-radius:10px; margin-bottom:20px;'>
                    ✅ Jogos gerados respeitando os padrões identificados nos 600 concursos:
                    • Equilíbrio de pares/ímpares (7-8)
                    • Soma entre 180 e 210
                    • 5-6 números primos
                    • Distribuição balanceada por linhas
                    • Peso maior para números quentes e atrasados
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        qtd_jogos_hist = st.slider("Quantidade de jogos", 5, 20, 10, key="qtd_jogos_hist")
                    with col2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🎲 Gerar Jogos Históricos", use_container_width=True, type="primary"):
                            with st.spinner("Gerando jogos baseados em padrões reais..."):
                                jogos_historicos = analise_hist.gerar_multiplos_jogos(qtd_jogos_hist)
                                
                                # Salvar na sessão
                                st.session_state.jogos_historicos_gerados = jogos_historicos
                                
                                st.success(f"✅ {len(jogos_historicos)} jogos gerados com sucesso!")
                    
                    # Mostrar jogos gerados
                    if "jogos_historicos_gerados" in st.session_state:
                        jogos_hist = st.session_state.jogos_historicos_gerados
                        
                        st.markdown("### 📋 Jogos Gerados")
                        
                        for i, jogo in enumerate(jogos_hist, 1):
                            with st.container():
                                # Formatar números com cores
                                nums_html = ""
                                for num in jogo:
                                    nums_html += formatar_numero_com_cor(num, analise_hist)
                                
                                # Calcular estatísticas do jogo
                                pares = sum(1 for n in jogo if n % 2 == 0)
                                primos = sum(1 for n in jogo if n in [2,3,5,7,11,13,17,19,23])
                                soma = sum(jogo)
                                
                                st.markdown(f"""
                                <div style='background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                                    <strong>Jogo {i:2d}:</strong> {nums_html}<br>
                                    <small>📊 Pares: {pares} | Primos: {primos} | Soma: {soma}</small>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        # Opção de exportar
                        if st.button("📥 Exportar Jogos", use_container_width=True):
                            # Criar DataFrame para exportação
                            df_export = pd.DataFrame({
                                "Jogo": range(1, len(jogos_hist)+1),
                                "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos_hist],
                                "Pares": [sum(1 for n in j if n%2==0) for j in jogos_hist],
                                "Primos": [sum(1 for n in j if n in [2,3,5,7,11,13,17,19,23]) for j in jogos_hist],
                                "Soma": [sum(j) for j in jogos_hist]
                            })
                            
                            # Converter para CSV
                            csv = df_export.to_csv(index=False)
                            st.download_button(
                                label="⬇️ Baixar CSV",
                                data=csv,
                                file_name=f"jogos_historicos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                
                elif opcao_historica == "🔍 Explorar Números":
                    st.markdown("### 🔍 Análise Individual por Número")
                    
                    # Seletor de número
                    num_selecionado = st.selectbox("Selecione um número:", range(1, 26))
                    
                    if num_selecionado:
                        freq = analise_hist.frequencias[num_selecionado]
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Frequência", f"{freq['absoluta']}x")
                        with col2:
                            st.metric("Percentual", f"{freq['percentual']:.1f}%")
                        with col3:
                            # Classificação
                            if num_selecionado in analise_hist.numeros_quentes:
                                st.markdown("<p style='color:#ff6b6b; font-weight:bold;'>🔥 QUENTE</p>", unsafe_allow_html=True)
                            elif num_selecionado in analise_hist.numeros_frios:
                                st.markdown("<p style='color:#4ade80; font-weight:bold;'>❄️ FRIO</p>", unsafe_allow_html=True)
                            elif num_selecionado in analise_hist.numeros_atrasados:
                                st.markdown("<p style='color:#f97316; font-weight:bold;'>⏰ ATRASADO</p>", unsafe_allow_html=True)
                            elif num_selecionado in analise_hist.numeros_repetentes:
                                st.markdown("<p style='color:#4cc9f0; font-weight:bold;'>🔁 REPETENTE</p>", unsafe_allow_html=True)
                        
                        # Últimas aparições
                        st.markdown("#### 📅 Últimas aparições")
                        aparicoes = []
                        for i, concurso in enumerate(analise_hist.concursos[:20]):
                            if num_selecionado in concurso:
                                if i < len(analise_hist.dados_completos):
                                    aparicoes.append({
                                        "concurso": analise_hist.dados_completos[i]["concurso"],
                                        "data": analise_hist.dados_completos[i]["data"]
                                    })
                        
                        if aparicoes:
                            df_aparicoes = pd.DataFrame(aparicoes[:10])
                            st.dataframe(df_aparicoes, use_container_width=True, hide_index=True)
                        else:
                            st.info("Número não encontrado nos últimos 20 concursos")

    else:
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🚀 Comece carregando os concursos na barra lateral</h3>
            <p>Use o menu ≡ no canto superior esquerdo</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
