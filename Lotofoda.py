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
            "jogos": jogos_convertidos,
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
        for c in self.concursos[:15]: 
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
        qtd = st.slider("Qtd concursos históricos", 50, 1000, 300, 
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
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Análise", "🧩 Fechamento", "🧬 DNA", "✅ Conferência", "📈 Comparação"
        ])

        with tab1:
            st.markdown("### 🔑 Números-chave (últimos 50 concursos)")
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
                    
                    opcoes = []
                    for i, j in enumerate(nao_conferidos[:10]):
                        data = datetime.fromisoformat(j["data_geracao"]).strftime("%d/%m/%Y %H:%M")
                        base = get_concurso_info_seguro(j)
                        opcoes.append(f"{i+1} - Base #{base['numero']} - {data}")
                    
                    if opcoes:
                        selecao = st.selectbox("Selecione o fechamento", opcoes)
                        idx = int(selecao.split(" - ")[0]) - 1
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
                        
                        concursos_futuros = [c for c in st.session_state.dados_api 
                                            if c['concurso'] > base_info['numero']]
                        
                        if concursos_futuros:
                            opcoes_futuros = [f"#{c['concurso']} - {c['data']}" 
                                             for c in concursos_futuros[:5]]
                            futuro_sel = st.selectbox("Concurso para conferir", opcoes_futuros)
                            
                            if st.button("🔍 Conferir", use_container_width=True):
                                num_futuro = int(futuro_sel.split(" - ")[0].replace("#", ""))
                                concurso_info = next(c for c in concursos_futuros 
                                                    if c['concurso'] == num_futuro)
                                numeros = sorted(map(int, concurso_info["dezenas"]))
                                
                                acertos = []
                                for jogo in jogo_sel["jogos"]:
                                    # Garantir que o jogo tem números únicos
                                    if len(set(jogo)) != 15:
                                        st.warning("Jogo com números repetidos encontrado! Ignorando...")
                                        acertos.append(0)
                                    else:
                                        acertos.append(len(set(jogo) & set(numeros)))
                                
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
                                
                                if adicionar_conferencia(jogo_sel["arquivo"], info_salvar, 
                                                        acertos, stats_conf):
                                    st.success(f"✅ Conferido com concurso #{num_futuro}!")
                                    
                                    df_res = pd.DataFrame({
                                        "Jogo": range(1, len(jogo_sel["jogos"])+1),
                                        "Dezenas": [", ".join(f"{n:02d}" for n in j) 
                                                   for j in jogo_sel["jogos"]],
                                        "Acertos": acertos
                                    })
                                    st.dataframe(df_res, use_container_width=True, hide_index=True)
                                    
                                    m1, m2, m3 = st.columns(3)
                                    with m1:
                                        st.metric("Média", f"{np.mean(acertos):.1f}")
                                    with m2:
                                        st.metric("Máximo", max(acertos))
                                    with m3:
                                        vantagem_real = np.mean(acertos) - 9.5
                                        st.metric("Vs aleatório", f"{vantagem_real:+.2f}")
                                    
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

    else:
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🚀 Comece carregando os concursos na barra lateral</h3>
            <p>Use o menu ≡ no canto superior esquerdo</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
