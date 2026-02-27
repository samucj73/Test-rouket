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
    page_title="🎯 LOTOFÁCIL 3622",
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
.regra-ok { color: #4ade80; font-weight: bold; }
.regra-alerta { color: #f97316; font-weight: bold; }
.regra-ruim { color: #ff6b6b; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🎯🧠 LOTOFÁCIL 3622")
st.caption("Modelo Universal + Ajuste Adaptável • Baseado em Padrões Reais")

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
# CLASSE: MODELO 3622 (UNIVERSAL + AJUSTE ADAPTÁVEL)
# =====================================================
class Modelo3622:
    """
    Implementação do MODELO UNIVERSAL + AJUSTE ADAPTÁVEL para LOTOFácil
    Baseado nas regras do concurso 3622
    """
    
    def __init__(self, analise_principal, ultimo_concurso, ultimo_concurso_numero, ultimo_concurso_data):
        self.analise = analise_principal
        self.ultimo_concurso = ultimo_concurso  # Lista de números do último concurso
        self.ultimo_numero = ultimo_concurso_numero
        self.ultimo_data = ultimo_concurso_data
        self.numeros = list(range(1, 26))
        
        # REGRAS UNIVERSAIS (BASE FIXA)
        self.regras_universais = {
            "repeticao": {"min": 8, "max": 10, "otimo": (8, 9), "descricao": "Repetição do concurso anterior"},
            "pares_impares": {"tipos": ["7x8", "8x7"], "alternativo": "6x9", "descricao": "Ímpares x Pares"},
            "soma": {"min": 168, "max": 186, "premium": (172, 182), "descricao": "Soma total"},
            "faixas": {
                "01-08": {"min": 5, "max": 6},
                "09-16": {"min": 5, "max": 6},
                "17-25": {"min": 3, "max": 4}
            },
            "consecutivos": {"min_pares": 3, "ideal": "2 blocos + 1 triplo", "descricao": "Números consecutivos"},
            "primos": {"min": 4, "max": 6, "descricao": "Números primos"}
        }
        
        # Lista de números primos
        self.primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        
        # AJUSTES ADAPTÁVEIS (calculados com base no último concurso)
        self.ajustes = self._calcular_ajustes()
        
    def _calcular_ajustes(self):
        """Calcula os ajustes adaptáveis com base no último concurso"""
        ajustes = {}
        
        # AJUSTE A: Peso das repetições
        if self.analise and self.analise.padroes_repeticao:
            ultima_rep = self.analise.padroes_repeticao.get("ultima", 8)
            
            if ultima_rep >= 9:
                ajustes["repeticao_alvo"] = (7, 8)  # Se veio 9 ou 10, reduzir
            elif ultima_rep <= 7:
                ajustes["repeticao_alvo"] = (9, 10)  # Se veio ≤7, aumentar
            else:
                ajustes["repeticao_alvo"] = (8, 8)  # Manter 8
        else:
            ajustes["repeticao_alvo"] = (8, 9)
        
        # AJUSTE B: Altas (22-25)
        if self.ultimo_concurso:
            altas_ultimo = sum(1 for n in self.ultimo_concurso if n >= 22)
            
            if altas_ultimo <= 1:
                ajustes["altas_alvo"] = (2, 3)  # Tendência a aumentar
            elif altas_ultimo >= 3:
                ajustes["altas_alvo"] = (0, 1)  # Tendência a diminuir
            else:
                ajustes["altas_alvo"] = (1, 2)  # Neutro
        else:
            ajustes["altas_alvo"] = (1, 2)
        
        # AJUSTE C: Miolo (09-16)
        if self.ultimo_concurso:
            miolo_ultimo = sum(1 for n in self.ultimo_concurso if 9 <= n <= 16)
            
            # Concurso 3622 é "limpo" (miolo forte)
            if miolo_ultimo >= 6:
                ajustes["miolo_alvo"] = (5, 6)  # Manter forte
            else:
                ajustes["miolo_alvo"] = (4, 5)  # Reduzir
        else:
            ajustes["miolo_alvo"] = (5, 6)
        
        # AJUSTE D: Quebra de sequência
        if self.analise and hasattr(self.analise, 'padroes_repeticao'):
            # Análise simplificada de sequências
            if self.analise.padroes_repeticao.get("media", 9) > 9.5:
                ajustes["sequencias"] = "encurtar"
            else:
                ajustes["sequencias"] = "manter"
        else:
            ajustes["sequencias"] = "manter"
        
        return ajustes
    
    def validar_jogo(self, jogo):
        """
        Valida um jogo contra todas as regras universais
        Retorna: (valido, violacoes, pontuacao)
        """
        violacoes = []
        pontuacao = 0
        
        # REGRA 1: Repetição do último concurso
        if self.ultimo_concurso:
            repetidos = len(set(jogo) & set(self.ultimo_concurso))
            if repetidos < 7:
                violacoes.append(f"❌ Repetição muito baixa: {repetidos} (mínimo 7)")
            elif repetidos > 11:
                violacoes.append(f"❌ Repetição muito alta: {repetidos} (máximo 11)")
            elif 8 <= repetidos <= 9:
                pontuacao += 2  # Zona ótima
            elif 7 <= repetidos <= 10:
                pontuacao += 1  # Aceitável
        
        # REGRA 2: Ímpares x Pares
        pares = sum(1 for n in jogo if n % 2 == 0)
        impares = 15 - pares
        
        if f"{impares}x{pares}" in ["7x8", "8x7"]:
            pontuacao += 2
        elif f"{impares}x{pares}" == "6x9":
            pontuacao += 1  # Alternativa aceitável
        else:
            violacoes.append(f"❌ Distribuição ruim: {impares} ímpares x {pares} pares")
        
        # REGRA 3: Soma total
        soma = sum(jogo)
        if 172 <= soma <= 182:
            pontuacao += 2  # Zona premium
        elif 168 <= soma <= 186:
            pontuacao += 1  # Faixa universal
        else:
            violacoes.append(f"❌ Soma fora da faixa: {soma} (deve ser 168-186)")
        
        # REGRA 4: Distribuição por faixas
        faixa1 = sum(1 for n in jogo if 1 <= n <= 8)
        faixa2 = sum(1 for n in jogo if 9 <= n <= 16)
        faixa3 = sum(1 for n in jogo if 17 <= n <= 25)
        
        # Faixa 01-08
        if 5 <= faixa1 <= 6:
            pontuacao += 1
        elif faixa1 < 5:
            violacoes.append(f"❌ Faixa 01-08 com apenas {faixa1} números (mínimo 5)")
        
        # Faixa 09-16
        if 5 <= faixa2 <= 6:
            pontuacao += 1
        elif faixa2 < 5:
            violacoes.append(f"❌ Faixa 09-16 com apenas {faixa2} números (mínimo 5)")
        
        # Faixa 17-25
        if 3 <= faixa3 <= 4:
            pontuacao += 1
        elif faixa3 > 6:
            violacoes.append(f"❌ Faixa 17-25 com {faixa3} números (máximo 6)")
        
        # REGRA 5: Consecutivos
        jogo_ord = sorted(jogo)
        pares_consec = 0
        triplas_consec = 0
        i = 0
        
        while i < len(jogo_ord) - 1:
            if jogo_ord[i+1] - jogo_ord[i] == 1:
                # Encontrou um par
                tamanho_seq = 2
                j = i + 1
                while j < len(jogo_ord) - 1 and jogo_ord[j+1] - jogo_ord[j] == 1:
                    tamanho_seq += 1
                    j += 1
                
                if tamanho_seq >= 3:
                    triplas_consec += 1
                else:
                    pares_consec += 1
                
                i = j
            else:
                i += 1
        
        total_consec = pares_consec + triplas_consec * 2  # Cada tripla conta como 2 pares
        
        if total_consec >= 3:
            pontuacao += 1
        else:
            violacoes.append(f"❌ Apenas {total_consec} pares consecutivos (mínimo 3)")
        
        # REGRA 6: Primos
        qtd_primos = sum(1 for n in jogo if n in self.primos)
        if 4 <= qtd_primos <= 6:
            pontuacao += 1
        else:
            violacoes.append(f"❌ {qtd_primos} números primos (deve ser 4-6)")
        
        # Verificar ajustes adaptáveis
        if self.ajustes:
            # Altas (22-25)
            altas = sum(1 for n in jogo if n >= 22)
            alvo_altas = self.ajustes.get("altas_alvo", (1, 2))
            if alvo_altas[0] <= altas <= alvo_altas[1]:
                pontuacao += 1
            else:
                violacoes.append(f"⚠️ Altas: {altas} (tendência sugere {alvo_altas[0]}-{alvo_altas[1]})")
            
            # Miolo (09-16)
            miolo = sum(1 for n in jogo if 9 <= n <= 16)
            alvo_miolo = self.ajustes.get("miolo_alvo", (5, 6))
            if alvo_miolo[0] <= miolo <= alvo_miolo[1]:
                pontuacao += 1
        
        # Decisão final
        if len(violacoes) >= 2:
            return False, violacoes, pontuacao
        elif len(violacoes) == 1:
            return True, violacoes, pontuacao  # Jogo secundário
        else:
            return True, [], pontuacao  # Jogo principal
    
    def gerar_jogo(self, max_tentativas=5000):
        """
        Gera um jogo seguindo o passo a passo do modelo
        """
        for _ in range(max_tentativas):
            # PASSO 1: Fixar base com repetições
            if self.ultimo_concurso and self.ajustes.get("repeticao_alvo"):
                alvo_rep = self.ajustes["repeticao_alvo"]
                qtd_repetir = random.randint(alvo_rep[0], alvo_rep[1])
                
                # Selecionar números do último concurso para repetir
                base = random.sample(self.ultimo_concurso, min(qtd_repetir, len(self.ultimo_concurso)))
            else:
                base = []
                qtd_repetir = 0
            
            # PASSO 2: Completar respeitando faixas
            jogo = list(base)
            
            # Definir alvos para cada faixa
            alvo_faixa1 = random.randint(5, 6)
            alvo_faixa2 = random.randint(5, 6)
            alvo_faixa3 = random.randint(3, 4)
            
            # Ajustar com base nos números já selecionados
            atuais_faixa1 = sum(1 for n in jogo if 1 <= n <= 8)
            atuais_faixa2 = sum(1 for n in jogo if 9 <= n <= 16)
            atuais_faixa3 = sum(1 for n in jogo if 17 <= n <= 25)
            
            # Criar pool de números disponíveis por faixa
            disponiveis_faixa1 = [n for n in range(1, 9) if n not in jogo]
            disponiveis_faixa2 = [n for n in range(9, 17) if n not in jogo]
            disponiveis_faixa3 = [n for n in range(17, 26) if n not in jogo]
            
            # Completar faixa 1
            while len(jogo) < 15 and atuais_faixa1 < alvo_faixa1 and disponiveis_faixa1:
                n = random.choice(disponiveis_faixa1)
                jogo.append(n)
                disponiveis_faixa1.remove(n)
                atuais_faixa1 += 1
            
            # Completar faixa 2
            while len(jogo) < 15 and atuais_faixa2 < alvo_faixa2 and disponiveis_faixa2:
                n = random.choice(disponiveis_faixa2)
                jogo.append(n)
                disponiveis_faixa2.remove(n)
                atuais_faixa2 += 1
            
            # Completar faixa 3
            while len(jogo) < 15 and atuais_faixa3 < alvo_faixa3 and disponiveis_faixa3:
                n = random.choice(disponiveis_faixa3)
                jogo.append(n)
                disponiveis_faixa3.remove(n)
                atuais_faixa3 += 1
            
            # Se ainda faltam números, completar com qualquer número disponível
            todos_disponiveis = [n for n in range(1, 26) if n not in jogo]
            while len(jogo) < 15 and todos_disponiveis:
                n = random.choice(todos_disponiveis)
                jogo.append(n)
                todos_disponiveis.remove(n)
            
            jogo.sort()
            
            # PASSO 3: Validar o jogo
            valido, violacoes, pontuacao = self.validar_jogo(jogo)
            
            if valido:
                return jogo, violacoes, pontuacao
        
        # Fallback: gerar jogo aleatório e tentar validar
        for _ in range(1000):
            jogo = sorted(random.sample(range(1, 26), 15))
            valido, violacoes, pontuacao = self.validar_jogo(jogo)
            if valido:
                return jogo, violacoes, pontuacao
        
        # Último recurso
        return sorted(random.sample(range(1, 26), 15)), ["⚠️ Jogo gerado sem validação completa"], 0
    
    def gerar_multiplos_jogos(self, quantidade=10):
        """Gera múltiplos jogos usando o modelo"""
        jogos = []
        violacoes_list = []
        pontuacoes = []
        
        tentativas = 0
        max_tentativas = quantidade * 200
        
        while len(jogos) < quantidade and tentativas < max_tentativas:
            jogo, violacoes, pontuacao = self.gerar_jogo()
            
            # Evitar duplicatas
            if jogo not in jogos:
                jogos.append(jogo)
                violacoes_list.append(violacoes)
                pontuacoes.append(pontuacao)
            
            tentativas += 1
        
        return jogos, violacoes_list, pontuacoes
    
    def get_resumo_regras(self):
        """Retorna resumo formatado das regras"""
        resumo = {
            "universais": self.regras_universais,
            "ajustes": self.ajustes,
            "ultimo_concurso": {
                "numero": self.ultimo_numero,
                "data": self.ultimo_data,
                "dezenas": self.ultimo_concurso
            }
        }
        return resumo
    
    def analisar_ultimo_concurso(self):
        """Analisa o último concurso para mostrar ajustes"""
        if not self.ultimo_concurso:
            return {}
        
        analise = {
            "repetidos_ultimo": "N/A",
            "altas_ultimo": sum(1 for n in self.ultimo_concurso if n >= 22),
            "miolo_ultimo": sum(1 for n in self.ultimo_concurso if 9 <= n <= 16),
            "soma_ultimo": sum(self.ultimo_concurso),
            "pares_ultimo": sum(1 for n in self.ultimo_concurso if n % 2 == 0),
            "primos_ultimo": sum(1 for n in self.ultimo_concurso if n in self.primos)
        }
        
        # Análise de repetição (se houver penúltimo)
        if self.analise and hasattr(self.analise, 'concursos') and len(self.analise.concursos) > 1:
            penultimo = self.analise.concursos[1]
            analise["repetidos_ultimo"] = len(set(self.ultimo_concurso) & set(penultimo))
        
        return analise


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
    if "modelo_3622" not in st.session_state:
        st.session_state.modelo_3622 = None

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

                    # Inicializar modelo 3622
                    st.session_state.modelo_3622 = Modelo3622(
                        st.session_state.analise,
                        concursos[0],
                        ultimo['concurso'],
                        ultimo['data']
                    )
                    
                    rep_penultimo = repeticao_ultimo_penultimo(concursos)
                    if rep_penultimo:
                        repetidos, media = rep_penultimo
                        st.info(f"🔁 Repetição último x penúltimo: {repetidos} ({media*100:.1f}%)")
                    
                    st.info("🧠 MODELO 3622 ativado - Regras universais + ajustes adaptáveis!")
                    
                except Exception as e:
                    st.error(f"Erro ao carregar: {e}")

    # ================= INTERFACE PRINCIPAL =================
    st.subheader("🎯 Geração de Jogos Inteligente")

    if st.session_state.analise:
        # APENAS DUAS ABAS: Fechamento Evolutivo e MODELO 3622
        tab1, tab2 = st.tabs(["🧩 Fechamento Evolutivo", "🎯 MODELO 3622"])

        # ================= ABA 1: Fechamento Evolutivo (original) =================
        with tab1:
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

        # ================= ABA 2: MODELO 3622 (NOVA) =================
        with tab2:
            st.subheader("🎯 MODELO 3622 - Universal + Ajuste Adaptável")
            
            if not st.session_state.modelo_3622:
                st.warning("📥 Carregue os concursos primeiro usando o botão na barra lateral")
            else:
                modelo = st.session_state.modelo_3622
                
                # Informações do último concurso
                analise_ultimo = modelo.analisar_ultimo_concurso()
                
                st.markdown(f"""
                <div class='concurso-info'>
                    📅 <strong>Base: concurso #{modelo.ultimo_numero}</strong> - {modelo.ultimo_data}
                </div>
                """, unsafe_allow_html=True)
                
                # Menu de opções
                opcao = st.radio(
                    "Selecione uma opção:",
                    ["📋 Regras do Modelo", "🎯 Gerar Jogos 3622", "📊 Análise do Último Concurso"],
                    horizontal=True
                )
                
                if opcao == "📋 Regras do Modelo":
                    st.markdown("### 🧠 REGRAS UNIVERSAIS (BASE FIXA)")
                    st.markdown("Essas regras NÃO mudam. Se quebrar 2 delas, o jogo já nasce morto.")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**✅ REGRA 1 — REPETIÇÃO**")
                        st.markdown(f"""
                        - Obrigatório: **{modelo.regras_universais['repeticao']['min']} a {modelo.regras_universais['repeticao']['max']}** repetidas
                        - Zona ótima: **{modelo.regras_universais['repeticao']['otimo'][0]} ou {modelo.regras_universais['repeticao']['otimo'][1]}**
                        """)
                        
                        st.markdown("**✅ REGRA 2 — ÍMPARES x PARES**")
                        st.markdown(f"""
                        - Padrão vencedor: **{modelo.regras_universais['pares_impares']['tipos'][0]} ou {modelo.regras_universais['pares_impares']['tipos'][1]}**
                        - Alternativa: **{modelo.regras_universais['pares_impares']['alternativo']}** (raro)
                        """)
                        
                        st.markdown("**✅ REGRA 3 — SOMA TOTAL**")
                        st.markdown(f"""
                        - Faixa universal: **{modelo.regras_universais['soma']['min']} a {modelo.regras_universais['soma']['max']}**
                        - Zona premium: **{modelo.regras_universais['soma']['premium'][0]} a {modelo.regras_universais['soma']['premium'][1]}**
                        """)
                    
                    with col2:
                        st.markdown("**✅ REGRA 4 — DISTRIBUIÇÃO POR FAIXAS**")
                        st.markdown(f"""
                        - **01–08:** {modelo.regras_universais['faixas']['01-08']['min']} a {modelo.regras_universais['faixas']['01-08']['max']}
                        - **09–16:** {modelo.regras_universais['faixas']['09-16']['min']} a {modelo.regras_universais['faixas']['09-16']['max']}
                        - **17–25:** {modelo.regras_universais['faixas']['17-25']['min']} a {modelo.regras_universais['faixas']['17-25']['max']}
                        """)
                        
                        st.markdown("**✅ REGRA 5 — CONSECUTIVOS**")
                        st.markdown(f"""
                        - Mínimo: **{modelo.regras_universais['consecutivos']['min_pares']}** pares consecutivos
                        - Ideal: **{modelo.regras_universais['consecutivos']['ideal']}**
                        """)
                        
                        st.markdown("**✅ REGRA 6 — PRIMOS**")
                        st.markdown(f"""
                        - Faixa vencedora: **{modelo.regras_universais['primos']['min']} a {modelo.regras_universais['primos']['max']}** primos
                        """)
                    
                    st.markdown("---")
                    st.markdown("### 🧩 AJUSTES ADAPTÁVEIS (Baseados no Último Concurso)")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**🔁 AJUSTE A — Peso das Repetições**")
                        st.markdown(f"""
                        - Alvo para este concurso: **{modelo.ajustes.get('repeticao_alvo', (8,9))[0]} a {modelo.ajustes.get('repeticao_alvo', (8,9))[1]}** repetições
                        """)
                        
                        st.markdown("**📉 AJUSTE B — Altas (22–25)**")
                        st.markdown(f"""
                        - Alvo para este concurso: **{modelo.ajustes.get('altas_alvo', (1,2))[0]} a {modelo.ajustes.get('altas_alvo', (1,2))[1]}** números altos
                        """)
                    
                    with col2:
                        st.markdown("**🎯 AJUSTE C — Miolo (09–16)**")
                        st.markdown(f"""
                        - Alvo para este concurso: **{modelo.ajustes.get('miolo_alvo', (5,6))[0]} a {modelo.ajustes.get('miolo_alvo', (5,6))[1]}** números no miolo
                        """)
                        
                        st.markdown("**🔄 AJUSTE D — Quebra de Sequência**")
                        st.markdown(f"""
                        - Tendência: **{modelo.ajustes.get('sequencias', 'manter').upper()}** sequências
                        """)
                
                elif opcao == "🎯 Gerar Jogos 3622":
                    st.markdown("### 🎯 Gerar Jogos com Modelo Universal")
                    
                    st.markdown("""
                    <div style='background:#1e1e2e; padding:10px; border-radius:10px; margin-bottom:20px;'>
                    <strong>PASSO A PASSO DO MODELO:</strong><br>
                    1️⃣ Fixe a BASE com 9 repetições do último concurso<br>
                    2️⃣ Complete respeitando as faixas (6 baixas, 6 médias, 3 altas)<br>
                    3️⃣ Valide o jogo contra todas as regras universais
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        qtd_jogos_3622 = st.slider("Quantidade de jogos", 5, 20, 10, key="qtd_3622")
                    with col2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🎲 Gerar Jogos 3622", use_container_width=True, type="primary"):
                            with st.spinner("Gerando jogos com validação rigorosa..."):
                                jogos_3622, violacoes_list, pontuacoes = modelo.gerar_multiplos_jogos(qtd_jogos_3622)
                                st.session_state.jogos_3622_gerados = jogos_3622
                                st.session_state.jogos_3622_violacoes = violacoes_list
                                st.session_state.jogos_3622_pontuacoes = pontuacoes
                                st.success(f"✅ {len(jogos_3622)} jogos gerados com validação!")
                    
                    # Mostrar jogos gerados
                    if "jogos_3622_gerados" in st.session_state:
                        jogos_3622 = st.session_state.jogos_3622_gerados
                        violacoes_list = st.session_state.jogos_3622_violacoes
                        pontuacoes = st.session_state.jogos_3622_pontuacoes
                        
                        st.markdown("### 📋 Jogos Gerados - MODELO 3622")
                        
                        # Estatísticas agregadas
                        df_stats = pd.DataFrame({
                            "Jogo": range(1, len(jogos_3622)+1),
                            "Pontuação": pontuacoes,
                            "Violações": [len(v) for v in violacoes_list],
                            "Status": ["✅ Principal" if len(v) == 0 else "⚠️ Secundário" if len(v) == 1 else "❌ Ruim" for v in violacoes_list]
                        })
                        st.dataframe(df_stats, use_container_width=True, hide_index=True)
                        
                        # Mostrar cada jogo
                        for i, jogo in enumerate(jogos_3622, 1):
                            with st.container():
                                # Calcular estatísticas do jogo
                                pares = sum(1 for n in jogo if n % 2 == 0)
                                impares = 15 - pares
                                soma = sum(jogo)
                                primos = sum(1 for n in jogo if n in modelo.primos)
                                faixa1 = sum(1 for n in jogo if 1 <= n <= 8)
                                faixa2 = sum(1 for n in jogo if 9 <= n <= 16)
                                faixa3 = sum(1 for n in jogo if 17 <= n <= 25)
                                
                                # Cor de fundo baseada na pontuação
                                cor_fundo = "#0e1117"
                                if pontuacoes[i-1] >= 10:
                                    cor_fundo = "#1a3b2e"  # Verde escuro para jogos principais
                                elif pontuacoes[i-1] >= 7:
                                    cor_fundo = "#3b3a1a"  # Amarelo escuro para secundários
                                
                                st.markdown(f"""
                                <div style='background:{cor_fundo}; border-radius:10px; padding:15px; margin-bottom:10px; border-left: 5px solid #4cc9f0;'>
                                    <strong>Jogo {i:2d} (Pontuação: {pontuacoes[i-1]})</strong><br>
                                    <span style='font-size:1.1em;'>{', '.join(f"{n:02d}" for n in jogo)}</span><br>
                                    <small>
                                    📊 Pares: {pares} | Ímpares: {impares} | Soma: {soma} | Primos: {primos}<br>
                                    📈 Faixas: {faixa1}/01-08 | {faixa2}/09-16 | {faixa3}/17-25
                                    </small>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Mostrar violações se houver
                                if violacoes_list[i-1]:
                                    with st.expander(f"⚠️ Ver {len(violacoes_list[i-1])} violação(s)"):
                                        for v in violacoes_list[i-1]:
                                            st.markdown(v)
                        
                        # Opção de exportar
                        if st.button("📥 Exportar Jogos 3622", use_container_width=True):
                            df_export = pd.DataFrame({
                                "Jogo": range(1, len(jogos_3622)+1),
                                "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos_3622],
                                "Pontuacao": pontuacoes,
                                "Pares": [sum(1 for n in j if n%2==0) for j in jogos_3622],
                                "Impares": [15 - sum(1 for n in j if n%2==0) for j in jogos_3622],
                                "Soma": [sum(j) for j in jogos_3622],
                                "Primos": [sum(1 for n in j if n in modelo.primos) for j in jogos_3622],
                                "Faixa01_08": [sum(1 for n in j if 1<=n<=8) for j in jogos_3622],
                                "Faixa09_16": [sum(1 for n in j if 9<=n<=16) for j in jogos_3622],
                                "Faixa17_25": [sum(1 for n in j if 17<=n<=25) for j in jogos_3622]
                            })
                            
                            csv = df_export.to_csv(index=False)
                            st.download_button(
                                label="⬇️ Baixar CSV",
                                data=csv,
                                file_name=f"jogos_modelo3622_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                
                elif opcao == "📊 Análise do Último Concurso":
                    st.markdown("### 📊 Análise do Último Concurso")
                    
                    if analise_ultimo:
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Soma", analise_ultimo.get("soma_ultimo", "N/A"))
                            st.metric("Pares", analise_ultimo.get("pares_ultimo", "N/A"))
                        
                        with col2:
                            st.metric("Primos", analise_ultimo.get("primos_ultimo", "N/A"))
                            st.metric("Repetição", analise_ultimo.get("repetidos_ultimo", "N/A"))
                        
                        with col3:
                            st.metric("Altas (22-25)", analise_ultimo.get("altas_ultimo", "N/A"))
                            st.metric("Miolo (09-16)", analise_ultimo.get("miolo_ultimo", "N/A"))
                        
                        st.markdown("### 📋 Dezenas do Último Concurso")
                        
                        # Mostrar números com cores
                        nums_html = ""
                        for num in sorted(modelo.ultimo_concurso):
                            # Classificar o número
                            if num >= 22:
                                cor = "#ff6b6b"  # Vermelho para altas
                                icone = "🔴"
                            elif 9 <= num <= 16:
                                cor = "#4cc9f0"  # Azul para miolo
                                icone = "🔵"
                            else:
                                cor = "#4ade80"  # Verde para baixas
                                icone = "🟢"
                            
                            nums_html += f"<span style='background:{cor}30; border:1px solid {cor}; border-radius:30px; padding:8px 15px; margin:5px; display:inline-block; font-weight:bold; font-size:1.2em;'>{num:02d} {icone}</span>"
                        
                        st.markdown(f"<div style='text-align:center;'>{nums_html}</div>", unsafe_allow_html=True)
                        
                        st.markdown("### 🔍 Ajustes Adaptáveis Calculados")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Com base neste último concurso:**")
                            st.markdown(f"""
                            - Último teve **{analise_ultimo.get('altas_ultimo', 0)}** altas → próximo tende a **{modelo.ajustes.get('altas_alvo', (1,2))[0]}-{modelo.ajustes.get('altas_alvo', (1,2))[1]}**
                            - Último teve **{analise_ultimo.get('miolo_ultimo', 0)}** no miolo → próximo tende a **{modelo.ajustes.get('miolo_alvo', (5,6))[0]}-{modelo.ajustes.get('miolo_alvo', (5,6))[1]}**
                            """)
                        
                        with col2:
                            st.markdown("**Recomendações para o próximo concurso:**")
                            st.markdown(f"""
                            - Repetir **{modelo.ajustes.get('repeticao_alvo', (8,9))[0]}-{modelo.ajustes.get('repeticao_alvo', (8,9))[1]}** números
                            - Manter {modelo.ajustes.get('sequencias', 'manter')} sequências
                            - Soma entre 168-186 (ideal 172-182)
                            """)
    else:
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🚀 Comece carregando os concursos na barra lateral</h3>
            <p>Use o menu ≡ no canto superior esquerdo</p>
        </div>
        """, unsafe_allow_html=True)

# =====================================================
# FUNÇÕES DE REPETIÇÃO (MANTIDAS DO CÓDIGO ORIGINAL)
# =====================================================
def repeticao_ultimo_penultimo(concursos):
    if len(concursos) < 2: return None
    ultimo = set(concursos[0])
    penultimo = set(concursos[1])
    repetidos = len(ultimo & penultimo)
    media = repetidos / 15
    return int(repetidos), float(media)

def repeticao_ultimo_antepenultimo(concursos):
    if len(concursos) < 3: return None
    ultimo = set(concursos[0])
    antepenultimo = set(concursos[2])
    repetidos = len(ultimo & antepenultimo)
    media = repetidos / 15
    return int(repetidos), float(media)

if __name__ == "__main__":
    main()
