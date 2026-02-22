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
st.caption("DNA Evolutivo • Superando o Aleatório • Mobile First")

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
        
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_base": {
                "numero": numero_concurso_atual,
                "data": data_concurso_atual
            },
            "fechamento_base": fechamento,
            "dna_params": dna_params,
            "jogos": jogos,
            "estatisticas": estatisticas or {},
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
        
        nova_conferencia = {
            "concurso": concurso_info,
            "acertos": acertos,
            "estatisticas": estatisticas or {},
            "data_conferencia": datetime.now().isoformat()
        }
        
        dados["conferencias"].append(nova_conferencia)
        dados["conferido"] = True
        
        # Atualizar estatísticas acumuladas
        if "estatisticas_historicas" not in dados:
            dados["estatisticas_historicas"] = []
        dados["estatisticas_historicas"].append(estatisticas)
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar conferência: {e}")
        return False

# =====================================================
# CLASSE PRINCIPAL MELHORADA
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
            "freq": 1.2,      # Aumentado para dar mais peso à frequência
            "defas": 1.3,      # Defasagem com peso maior
            "soma": 1.1,
            "pares": 1.1,
            "seq": 1.0,
            "chave": 1.2,      # Números-chave com mais peso
            "repeticao": 1.3,  # NOVO: Padrões de repetição
            "linha_coluna": 1.1, # NOVO: Distribuição em linhas/colunas
            "intervalo": 1.1,   # NOVO: Intervalos entre números
            "tendencia": 1.2    # NOVO: Tendências recentes
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
            frequencias_ponderadas[n] = peso_total / self.total_concursos * 2
        return frequencias_ponderadas

    def _defasagens(self):
        d = {}
        for n in self.numeros:
            for i, c in enumerate(self.concursos):
                if n in c:
                    d[n] = i
                    break
            else:
                d[n] = self.total_concursos
        return d

    def _padroes(self):
        p = {"somas": [], "pares": []}
        for c in self.concursos:
            p["somas"].append(sum(c))
            p["pares"].append(sum(1 for n in c if n % 2 == 0))
        return p

    def _numeros_chave(self):
        cont = Counter()
        # Usar apenas os últimos 50 concursos para números-chave mais atuais
        for c in self.concursos[:50]: 
            cont.update(c)
        # Números que aparecem em mais de 30% dos concursos recentes
        limite = 50 * 0.3
        return [n for n, q in cont.items() if q >= limite]

    # NOVAS ANÁLISES
    def _analisar_padroes_repeticao(self):
        """Analisa padrões de repetição entre concursos consecutivos"""
        repeticoes = []
        for i in range(len(self.concursos) - 1):
            repetidos = len(set(self.concursos[i]) & set(self.concursos[i + 1]))
            repeticoes.append(repetidos)
        
        if repeticoes:
            media_repeticao = np.mean(repeticoes)
            desvio_repeticao = np.std(repeticoes)
            return {
                "media": media_repeticao,
                "desvio": desvio_repeticao,
                "ultima": repeticoes[0] if repeticoes else 9,
                "tendencia": repeticoes[:10]  # Últimas 10 repetições
            }
        return {"media": 9, "desvio": 2, "ultima": 9, "tendencia": [9] * 10}

    def _analisar_linhas_colunas(self):
        """Analisa distribuição por linhas (1-5,6-10,11-15,16-20,21-25)"""
        linhas = {1: [], 2: [], 3: [], 4: [], 5: []}
        for c in self.concursos[:30]:  # Últimos 30
            cont_linhas = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for n in c:
                linha = (n - 1) // 5 + 1
                cont_linhas[linha] += 1
            for linha in linhas:
                linhas[linha].append(cont_linhas[linha])
        
        return {f"linha_{l}": np.mean(cont) for l, cont in linhas.items()}

    def _analisar_pares_impares(self):
        """Analisa tendência de pares/ímpares"""
        pares_tendencia = []
        for c in self.concursos[:20]:  # Últimos 20
            pares = sum(1 for n in c if n % 2 == 0)
            pares_tendencia.append(pares)
        
        if len(pares_tendencia) > 5:
            media_recente = np.mean(pares_tendencia[:5])
            media_antiga = np.mean(pares_tendencia[5:10]) if len(pares_tendencia) > 10 else media_recente
            tendencia = "crescendo" if media_recente > media_antiga else "decrescendo" if media_recente < media_antiga else "estavel"
        else:
            tendencia = "estavel"
        
        return {
            "media": np.mean(pares_tendencia) if pares_tendencia else 7.5,
            "desvio": np.std(pares_tendencia) if pares_tendencia else 1,
            "tendencia": tendencia,
            "ultimos": pares_tendencia[:5]
        }

    def _analisar_intervalos(self):
        """Analisa intervalos médios entre números consecutivos"""
        intervalos = []
        for c in self.concursos[:30]:
            c_ordenado = sorted(c)
            diffs = [c_ordenado[i+1] - c_ordenado[i] for i in range(len(c_ordenado)-1)]
            intervalos.extend(diffs)
        
        return {
            "media_intervalo": np.mean(intervalos) if intervalos else 1.6,
            "intervalos_comuns": Counter(intervalos).most_common(3) if intervalos else [(1, 10)]
        }

    def score_numero_evolutivo(self, n):
        """Score avançado com múltiplos fatores"""
        score = 0
        
        # Frequência (ponderada)
        score += self.frequencias[n] * self.dna_evolutivo["freq"]
        
        # Defasagem
        score += (1 - self.defasagens[n] / self.total_concursos) * self.dna_evolutivo["defas"]
        
        # Números-chave
        if n in self.numeros_chave:
            score += 0.8 * self.dna_evolutivo["chave"]
        
        # NOVO: Tendência de repetição
        if n in self.concursos[0] if self.concursos else []:
            score += 0.5 * self.dna_evolutivo["repeticao"]
        elif len(self.concursos) > 1 and n in self.concursos[1]:
            score += 0.3 * self.dna_evolutivo["repeticao"]
        
        # NOVO: Distribuição ideal por linha
        linha = (n - 1) // 5 + 1
        media_linha = self.tendencias_linhas_colunas.get(f"linha_{linha}", 3)
        if media_linha > 2.8:  # Linha com mais números
            score += 0.2 * self.dna_evolutivo["linha_coluna"]
        
        # NOVO: Ajuste baseado em pares/ímpares
        par_impar_tend = self.pares_impares_tendencia["tendencia"]
        if (n % 2 == 0 and par_impar_tend == "crescendo") or (n % 2 == 1 and par_impar_tend == "decrescendo"):
            score += 0.2 * self.dna_evolutivo["tendencia"]
        
        return score

    def gerar_fechamento_evolutivo(self, tamanho=17):
        """Gera fechamento usando o score evolutivo"""
        scores = {n: self.score_numero_evolutivo(n) for n in self.numeros}
        
        # Garantir diversidade incluindo números com scores médios
        base = sorted(scores, key=scores.get, reverse=True)
        
        # Pegar top N mas garantir 2 números de fora para diversidade
        if tamanho <= 20:
            base = base[:tamanho-2]
            # Adicionar 2 números aleatórios do meio da lista
            meio = base[len(base)//2:len(base)//2 + 10]
            extras = random.sample(meio, min(2, len(meio)))
            base.extend(extras)
        
        return sorted(base)

    def gerar_jogos_otimizados(self, fechamento, qtd_jogos=8):
        """Gera jogos com otimização para superar aleatório"""
        jogos = set()
        tentativas = 0
        max_tentativas = 500
        
        # Parâmetros ideais baseados em análise histórica
        soma_alvo = 195  # Ligeiramente abaixo da média
        pares_alvo = 7   # Ligeiramente abaixo da média
        
        # Usar variação controlada
        variacao_soma = 15
        variacao_pares = 2
        
        while len(jogos) < qtd_jogos and tentativas < max_tentativas:
            # Estratégia: 70% dos números do topo, 30% variados
            top_numeros = fechamento[:12]
            outros_numeros = fechamento[12:]
            
            if outros_numeros:
                num_top = random.randint(9, 11)  # 9-11 do topo
                num_outros = 15 - num_top
                
                selecao = random.sample(top_numeros, min(num_top, len(top_numeros)))
                if outros_numeros and num_outros > 0:
                    selecao.extend(random.sample(outros_numeros, min(num_outros, len(outros_numeros))))
            else:
                selecao = random.sample(fechamento, 15)
            
            jogo = sorted(selecao)
            soma = sum(jogo)
            pares = sum(1 for n in jogo if n % 2 == 0)
            
            # Critérios mais flexíveis para aumentar diversidade
            if (soma_alvo - variacao_soma <= soma <= soma_alvo + variacao_soma and
                pares_alvo - variacao_pares <= pares <= pares_alvo + variacao_pares):
                jogos.add(tuple(jogo))
            
            tentativas += 1
        
        # Se não conseguir todos, completar com variações
        while len(jogos) < qtd_jogos:
            jogo = sorted(random.sample(fechamento, 15))
            jogos.add(tuple(jogo))
        
        return [list(j) for j in jogos]

    def aprender_com_resultados(self, jogos_gerados, resultado_real):
        """Aprende com os resultados para melhorar futuras gerações"""
        acertos_por_jogo = [len(set(j) & set(resultado_real)) for j in jogos_gerados]
        media_acertos = np.mean(acertos_por_jogo)
        
        # Identificar números que mais acertaram
        numeros_acertadores = Counter()
        for jogo in jogos_gerados:
            for num in jogo:
                if num in resultado_real:
                    numeros_acertadores[num] += 1
        
        # Ajustar DNA evolutivo baseado no desempenho
        if media_acertos > 9.5:  # Bom desempenho
            # Reforçar o que funcionou
            for num in resultado_real:
                self.frequencias[num] *= 1.05
        elif media_acertos < 8.5:  # Desempenho ruim
            # Penalizar números que não funcionaram
            for num in set().union(*jogos_gerados) - set(resultado_real):
                if num in self.frequencias:
                    self.frequencias[num] *= 0.98
        
        self.historico_acertos.append(media_acertos)
        return media_acertos

    def auto_ajustar_dna(self, concurso_real):
        """Ajuste fino do DNA baseado em resultados reais"""
        lr = 0.03  # Learning rate reduzido para mais estabilidade
        soma_r = sum(concurso_real)
        pares_r = sum(1 for n in concurso_real if n % 2 == 0)
        soma_m = np.mean(self.padroes["somas"])
        pares_m = np.mean(self.padroes["pares"])
        
        # Ajustes mais suaves
        self.dna_evolutivo["soma"] += lr if abs(soma_r - soma_m) < 15 else -lr/2
        self.dna_evolutivo["pares"] += lr if abs(pares_r - pares_m) < 2 else -lr/2
        
        # Padrões de repetição
        if self.padroes_repeticao:
            rep_esperada = self.padroes_repeticao["media"]
            rep_real = len(set(concurso_real) & set(self.concursos[0] if self.concursos else []))
            self.dna_evolutivo["repeticao"] += lr if abs(rep_real - rep_esperada) < 2 else -lr/2
        
        # Manter limites
        for k in self.dna_evolutivo:
            self.dna_evolutivo[k] = max(0.7, min(1.8, self.dna_evolutivo[k]))

    def comparar_com_aleatorio(self, jogos_gerados, num_simulacoes=1000):
        """Compara desempenho com escolhas aleatórias"""
        acertos_sistema = []
        acertos_aleatorio = []
        
        for _ in range(min(num_simulacoes, 100)):  # Limitado para performance
            resultado_simulado = sorted(random.sample(range(1, 26), 15))
            
            # Acertos do sistema
            for jogo in jogos_gerados:
                acertos_sistema.append(len(set(jogo) & set(resultado_simulado)))
            
            # Acertos aleatórios
            for _ in range(len(jogos_gerados)):
                aleatorio = sorted(random.sample(range(1, 26), 15))
                acertos_aleatorio.append(len(set(aleatorio) & set(resultado_simulado)))
        
        stats = {
            "sistema_media": np.mean(acertos_sistema) if acertos_sistema else 0,
            "sistema_max": np.max(acertos_sistema) if acertos_sistema else 0,
            "aleatorio_media": np.mean(acertos_aleatorio) if acertos_aleatorio else 0,
            "aleatorio_max": np.max(acertos_aleatorio) if acertos_aleatorio else 0,
            "vantagem_media": np.mean(acertos_sistema) - np.mean(acertos_aleatorio) if acertos_sistema and acertos_aleatorio else 0
        }
        
        return stats

    def conferir(self, jogos, resultado):
        dados = []
        for i, j in enumerate(jogos, 1):
            dados.append({
                "Jogo": i,
                "Dezenas": ", ".join(f"{n:02d}" for n in j),
                "Acertos": len(set(j) & set(resultado)),
                "Soma": sum(j),
                "Pares": sum(1 for n in j if n % 2 == 0)
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
    return repetidos, media

def repeticao_ultimo_penultimo(concursos):
    if len(concursos) < 2: return None
    ultimo = set(concursos[0])
    penultimo = set(concursos[1])
    repetidos = len(ultimo & penultimo)
    media = repetidos / 15
    return repetidos, media

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
                    st.session_state.dados_api = requests.get(url).json()
                    concursos = [sorted(map(int, d["dezenas"])) for d in st.session_state.dados_api[:qtd]]
                    st.session_state.analise = AnaliseLotofacilAvancada(concursos, st.session_state.dados_api[:qtd])
                    
                    # Auto-ajustar com último concurso
                    st.session_state.analise.auto_ajustar_dna(concursos[0])
                    
                    ultimo = st.session_state.dados_api[0]
                    st.success(f"✅ Último concurso: #{ultimo['concurso']} - {ultimo['data']}")

                    # Mostrar estatísticas de repetição
                    rep_penultimo = repeticao_ultimo_penultimo(concursos)
                    if rep_penultimo:
                        repetidos, media = rep_penultimo
                        st.info(f"🔁 Repetição último x penúltimo: {repetidos} ({media*100:.1f}%)")
                    
                    # Comparação inicial com aleatório
                    st.info("🔄 DNA Evolutivo ativado - Objetivo: superar aleatório")
                    
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
            colunas = st.columns(5)
            for i, num in enumerate(sorted(numeros_chave)[:15]):
                with colunas[i % 5]:
                    st.markdown(f"<h3 style='text-align:center'>{num:02d}</h3>", unsafe_allow_html=True)
            
            st.markdown("### 📊 Tendências Atuais")
            col1, col2, col3 = st.columns(3)
            with col1:
                media_repeticao = st.session_state.analise.padroes_repeticao.get("media", 9)
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
                with st.spinner("Gerando jogos otimizados..."):
                    # Gerar fechamento com o novo método evolutivo
                    fechamento = st.session_state.analise.gerar_fechamento_evolutivo(tamanho)
                    jogos = st.session_state.analise.gerar_jogos_otimizados(fechamento, qtd_jogos)
                    
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
                        
                        # Mostrar vantagem sobre aleatório
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
                        
                        # Mostrar fechamento
                        st.markdown("### 🔒 Fechamento Base")
                        st.markdown(f"<div class='card'>{', '.join(f'{n:02d}' for n in fechamento)}</div>", 
                                  unsafe_allow_html=True)
                        
                        # Mostrar jogos
                        df_jogos = pd.DataFrame({
                            "Jogo": range(1, len(jogos)+1),
                            "Dezenas": [", ".join(f"{n:02d}" for n in j) for j in jogos],
                            "Soma": [sum(j) for j in jogos],
                            "Pares": [sum(1 for n in j if n%2==0) for j in jogos]
                        })
                        st.dataframe(df_jogos, use_container_width=True)
                        
                        # Atualizar lista de jogos salvos
                        st.session_state.jogos_salvos = carregar_jogos_salvos()
                        
                        # Guardar no histórico de comparação
                        st.session_state.historico_comparacao.append({
                            "id": jogo_id,
                            "concurso_base": ultimo['concurso'],
                            "vantagem": vantagem,
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
                
                # Filtrar não conferidos
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
                    
                    # Selecionar fechamento
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
                        
                        # Mostrar detalhes
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
                        
                        # Verificar concursos futuros
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
                                
                                # Calcular acertos
                                acertos = []
                                for jogo in jogo_sel["jogos"]:
                                    acertos.append(len(set(jogo) & set(numeros)))
                                
                                # Estatísticas da conferência
                                stats_conf = {
                                    "media": np.mean(acertos),
                                    "max": max(acertos),
                                    "min": min(acertos),
                                    "distribuicao": dict(Counter(acertos))
                                }
                                
                                # Salvar conferência
                                info_salvar = {
                                    "numero": concurso_info["concurso"],
                                    "data": concurso_info["data"],
                                    "resultado": numeros
                                }
                                
                                if adicionar_conferencia(jogo_sel["arquivo"], info_salvar, 
                                                        acertos, stats_conf):
                                    st.success(f"✅ Conferido com concurso #{num_futuro}!")
                                    
                                    # Mostrar resultados
                                    df_res = pd.DataFrame({
                                        "Jogo": range(1, len(jogo_sel["jogos"])+1),
                                        "Dezenas": [", ".join(f"{n:02d}" for n in j) 
                                                   for j in jogo_sel["jogos"]],
                                        "Acertos": acertos
                                    })
                                    st.dataframe(df_res, use_container_width=True)
                                    
                                    # Métricas
                                    m1, m2, m3 = st.columns(3)
                                    with m1:
                                        st.metric("Média", f"{np.mean(acertos):.1f}")
                                    with m2:
                                        st.metric("Máximo", max(acertos))
                                    with m3:
                                        # Comparar com aleatório teórico
                                        acertos_rand = np.random.choice(range(11, 16), 1000)
                                        st.metric("Vs aleatório", 
                                                 f"{np.mean(acertos) - 9.5:.2f}")
                                    
                                    st.rerun()
                        else:
                            st.warning("Aguardando próximos concursos...")

        with tab5:
            st.subheader("📈 Comparação vs Aleatório")
            
            if st.session_state.historico_comparacao:
                df_hist = pd.DataFrame(st.session_state.historico_comparacao)
                
                # Gráfico de evolução
                st.line_chart(df_hist.set_index("concurso_base")["vantagem"])
                
                # Média geral
                media_vantagem = df_hist["vantagem"].mean()
                if media_vantagem > 0:
                    st.success(f"🎯 Vantagem média: {media_vantagem:.2f} pontos")
                else:
                    st.warning(f"📉 Desvantagem média: {abs(media_vantagem):.2f} pontos")
                
                # Últimas comparações
                st.dataframe(df_hist[["concurso_base", "vantagem"]].tail(), 
                           use_container_width=True)
            else:
                st.info("Gere fechamentos para ver a comparação com o aleatório")

    else:
        # Tela inicial
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🚀 Comece carregando os concursos na barra lateral</h3>
            <p>Use o menu ≡ no canto superior esquerdo</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
