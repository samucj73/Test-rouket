
import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import pandas as pd
from collections import Counter, deque
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.utils import resample
import joblib
from streamlit_autorefresh import st_autorefresh
import pickle
import warnings
import math
from scipy.stats import binomtest, chi2_contingency
import random
warnings.filterwarnings('ignore')

# =============================
# CONFIGURAÇÕES DE LOGGING
# =============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"
ML_MODEL_PATH = "ml_roleta_model.pkl"
SCALER_PATH = "ml_scaler.pkl"
META_PATH = "ml_meta.pkl"
RL_MODEL_PATH = "rl_model.pkl"

# =============================
# SISTEMA DE VALIDAÇÃO ESTATÍSTICA
# =============================
class SistemaValidacaoEstatistica:
    def __init__(self):
        self.testes_realizados = 0
        self.falsos_positivos = 0
        self.verdadeiros_positivos = 0
        self.confianca_minima = 0.95  # 95% de confiança
        
    def teste_binomial_90porcento(self, acertos, tentativas):
        """
        Testa estatisticamente se a taxa de 90% é realista
        H0: taxa_real <= 90% vs H1: taxa_real > 90%
        """
        if tentativas < 30:
            return {
                'confianca': 0,
                'p_value': 1.0,
                'mensagem': f"Amostra muito pequena (n={tentativas})"
            }
        
        # Teste binomial unilateral
        resultado = binomtest(
            k=acertos,
            n=tentativas,
            p=0.90,  # Testando contra 90%
            alternative='greater'
        )
        
        confianca = 1 - resultado.pvalue
        
        return {
            'confianca': confianca,
            'p_value': resultado.pvalue,
            'mensagem': f"Confiança estatística: {confianca:.1%}",
            'rejeita_h0': resultado.pvalue < 0.05  # α = 0.05
        }
    
    def calcular_intervalo_confianca(self, acertos, tentativas):
        """Calcula intervalo de confiança 95% para a proporção"""
        if tentativas == 0:
            return (0, 0, 0)
        
        p = acertos / tentativas
        z = 1.96  # Para 95% de confiança
        margem = z * math.sqrt((p * (1 - p)) / tentativas)
        
        return (p - margem, p, p + margem)
    
    def teste_aleatoriedade(self, sequencia):
        """
        Testa se a sequência é aleatória usando teste de corridas
        """
        if len(sequencia) < 20:
            return {'aleatorio': True, 'p_value': 1.0}
        
        # Converter para binário (acerto=1, erro=0)
        binario = [1 if x else 0 for x in sequencia]
        
        # Teste de corridas (Wald-Wolfowitz)
        n = len(binario)
        n1 = sum(binario)
        n0 = n - n1
        
        if n0 == 0 or n1 == 0:
            return {'aleatorio': True, 'p_value': 1.0}
        
        corridas = 1
        for i in range(1, n):
            if binario[i] != binario[i-1]:
                corridas += 1
        
        # Estatística Z
        media_corridas = (2 * n0 * n1) / n + 1
        var_corridas = (2 * n0 * n1 * (2 * n0 * n1 - n)) / (n**2 * (n - 1))
        
        if var_corridas > 0:
            z_score = (corridas - media_corridas) / math.sqrt(var_corridas)
            p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z_score) / math.sqrt(2))))
        else:
            p_value = 1.0
        
        return {
            'aleatorio': p_value > 0.05,
            'p_value': p_value,
            'corridas': corridas,
            'esperado': media_corridas
        }
    
    def validar_padrao(self, padrao, dados_validacao):
        """
        Valida padrão em conjunto de dados separado
        Retorna True se o padrão se mantém
        """
        if len(dados_validacao) < 10:
            return False
        
        # Separar 70% treino, 30% validação
        ponto_corte = int(len(dados_validacao) * 0.7)
        treino = dados_validacao[:ponto_corte]
        validacao = dados_validacao[ponto_corte:]
        
        # Calcular performance em treino
        acertos_treino = padrao.get('acertos', 0)
        tentativas_treino = padrao.get('tentativas', 0)
        if tentativas_treino == 0:
            return False
        
        perf_treino = acertos_treino / tentativas_treino
        
        # Calcular performance em validação
        acertos_valid = 0
        tentativas_valid = 0
        
        for dado in validacao:
            if self.padrao_aplica(padrao, dado):
                tentativas_valid += 1
                if dado.get('acerto', False):
                    acertos_valid += 1
        
        if tentativas_valid < 5:
            return False
        
        perf_valid = acertos_valid / tentativas_valid
        
        # Padrão é válido se performance em validação for > 80% da performance em treino
        return perf_valid > (perf_treino * 0.8)
    
    def padrao_aplica(self, padrao, dado):
        """Verifica se o padrão se aplica ao dado"""
        # Implementação básica - adaptar conforme necessário
        return True
    
    def get_analise_estatistica_completa(self, historico):
        """Retorna análise estatística completa do sistema"""
        if len(historico) < 20:
            return "Aguardando mais dados para análise estatística..."
        
        acertos = sum(1 for h in historico if h.get('acerto', False))
        total = len(historico)
        taxa = acertos / total if total > 0 else 0
        
        analise = "📊 ANÁLISE ESTATÍSTICA AVANÇADA\n"
        analise += "=" * 60 + "\n"
        
        # Teste de 90%
        teste_90 = self.teste_binomial_90porcento(acertos, total)
        analise += f"🎯 TESTE DE 90% DE ACERTOS:\n"
        analise += f"   • P-value: {teste_90['p_value']:.4f}\n"
        analise += f"   • Confiança: {teste_90['confianca']:.1%}\n"
        analise += f"   • Status: {'✅ VIÁVEL' if teste_90['rejeita_h0'] else '❌ INVIÁVEL'}\n"
        
        # Intervalo de confiança
        inf, p, sup = self.calcular_intervalo_confianca(acertos, total)
        analise += f"\n📈 INTERVALO DE CONFIANÇA 95%:\n"
        analise += f"   • Inferior: {inf:.1%}\n"
        analise += f"   • Média: {p:.1%}\n"
        analise += f"   • Superior: {sup:.1%}\n"
        
        # Teste de aleatoriedade
        sequencia_acertos = [h.get('acerto', False) for h in historico]
        teste_aleat = self.teste_aleatoriedade(sequencia_acertos)
        analise += f"\n🎲 TESTE DE ALEATORIEDADE:\n"
        analise += f"   • P-value: {teste_aleat['p_value']:.4f}\n"
        analise += f"   • Aleatório: {'✅ SIM' if teste_aleat['aleatorio'] else '❌ NÃO'}\n"
        analise += f"   • Corridas: {teste_aleat['corridas']} (esperado: {teste_aleat['esperado']:.1f})\n"
        
        # Análise de sequências
        analise += f"\n📋 ANÁLISE DE SEQUÊNCIAS:\n"
        
        # Maior sequência de acertos
        max_seq_acertos = 0
        current_seq = 0
        for acerto in sequencia_acertos:
            if acerto:
                current_seq += 1
                max_seq_acertos = max(max_seq_acertos, current_seq)
            else:
                current_seq = 0
        
        # Maior sequência de erros
        max_seq_erros = 0
        current_seq = 0
        for acerto in sequencia_acertos:
            if not acerto:
                current_seq += 1
                max_seq_erros = max(max_seq_erros, current_seq)
            else:
                current_seq = 0
        
        analise += f"   • Maior sequência de acertos: {max_seq_acertos}\n"
        analise += f"   • Maior sequência de erros: {max_seq_erros}\n"
        
        # Distribuição por hora
        if len(historico) > 50:
            horas = []
            for h in historico:
                if 'timestamp' in h:
                    try:
                        hora = pd.to_datetime(h['timestamp']).hour
                        horas.append(hora)
                    except:
                        pass
            
            if horas:
                hora_contagem = Counter(horas)
                hora_mais_comum = hora_contagem.most_common(1)[0]
                analise += f"\n🕒 ANÁLISE TEMPORAL:\n"
                analise += f"   • Hora mais produtiva: {hora_mais_comum[0]}h ({hora_mais_comum[1]} jogos)\n"
        
        # Recomendações
        analise += f"\n💡 RECOMENDAÇÕES ESTATÍSTICAS:\n"
        
        if teste_90['rejeita_h0']:
            analise += f"   1. ✅ Continue com estratégia atual - 90% estatisticamente viável\n"
        else:
            analise += f"   1. ⚠️  Meta de 90% não suportada estatisticamente\n"
            analise += f"   2. 📊 Coletar mais dados para análise\n"
        
        if not teste_aleat['aleatorio']:
            analise += f"   2. 🎯 Padrões não-aleatórios detectados - explore estratégias\n"
        
        if sup < 0.9:
            analise += f"   3. 📉 Máximo teórico atual: {sup:.1%} - ajuste expectativas\n"
        
        return analise

# =============================
# SISTEMA DE APRENDIZADO POR REFORÇO COM VALIDAÇÃO
# =============================
class SistemaAprendizadoReforco:
    def __init__(self):
        self.historico_aprendizado = deque(maxlen=1000)
        self.melhores_combinacoes = {}
        self.piores_combinacoes = {}
        self.padroes_ganhadores = []
        self.sequencias_vencedoras = []
        self.contador_analise = 0
        self.ultimo_estado = None
        self.padroes_validados = []
        self.falso_positivos = 0
        self.validacao = SistemaValidacaoEstatistica()
        
    def calcular_probabilidade_teorica(self, combinacao):
        """Calcula probabilidade teórica baseada no tipo de combinação"""
        if not combinacao:
            return 1/37
        
        # Analisar tipo de combinação
        primeiro = str(combinacao[0]).lower() if isinstance(combinacao[0], str) else ""
        
        if 'numero' in primeiro or (isinstance(combinacao[0], int) and len(combinacao) == 1):
            return 1/37
        elif 'duzia' in primeiro:
            return 12/37
        elif 'coluna' in primeiro:
            return 12/37
        elif 'vermelho' in primeiro or 'preto' in primeiro:
            return 18/37
        else:
            # Combinação de zonas - estimar
            return 24/37  # ~65% para 2 zonas
        
        return 1/3  # Default
    
    def calcular_eficiencia_ajustada(self, dados_combinacao, probabilidade_teorica):
        """Calcula eficiência ajustada pela probabilidade teórica"""
        if dados_combinacao['tentativas'] == 0:
            return 50.0  # Neutro
        
        eficiencia_bruta = dados_combinacao['acertos'] / dados_combinacao['tentativas']
        
        # Eficiência ajustada = (observado - esperado) / (1 - esperado)
        if probabilidade_teorica < 1:
            eficiencia_ajustada = (eficiencia_bruta - probabilidade_teorica) / (1 - probabilidade_teorica)
        else:
            eficiencia_ajustada = eficiencia_bruta - probabilidade_teorica
        
        # Converter para porcentagem positiva
        return max(eficiencia_ajustada * 100, 0)
    
    def calcular_confianca_estatistica(self, acertos, tentativas, probabilidade_teorica):
        """Calcula confiança estatística usando teste binomial"""
        if tentativas < 5:
            return 0.0
        
        try:
            resultado = binomtest(
                k=acertos,
                n=tentativas,
                p=probabilidade_teorica,
                alternative='greater'
            )
            
            confianca = (1 - resultado.pvalue) * 100
            
            # Penalizar amostras pequenas
            if tentativas < 20:
                confianca *= (tentativas / 20)
            
            return min(confianca, 99.9)
        except:
            return 50.0
    
    def analisar_resultado(self, resultado):
        """Analisa resultado com validação estatística"""
        try:
            self.contador_analise += 1
            
            acerto = resultado['acerto']
            estrategia = resultado['estrategia']
            numero = resultado['numero']
            zonas_envolvidas = resultado.get('zonas_envolvidas', [])
            
            # ANALISAR COM VALIDAÇÃO ESTATÍSTICA
            if len(zonas_envolvidas) > 1:
                combinacao = tuple(sorted(zonas_envolvidas))
                prob_teorica = self.calcular_probabilidade_teorica(combinacao)
                
                # Atualizar estatísticas
                self.atualizar_estatisticas_combinacao(combinacao, acerto, prob_teorica)
                
                # Validar estatisticamente
                if acerto:
                    self.validar_padrao_estatistico(combinacao, numero, zonas_envolvidas, estrategia)
            
            # ANALISAR TENDÊNCIAS
            self.analisar_tendencias_temporais(numero, acerto)
            
            # GERAR RECOMENDAÇÕES VALIDADAS
            recomendacoes = self.gerar_recomendacoes_validas()
            
            return recomendacoes
            
        except Exception as e:
            logging.error(f"Erro no sistema de aprendizado: {e}")
            return {}
    
    def atualizar_estatisticas_combinacao(self, combinacao, acerto, probabilidade_teorica):
        """Atualiza estatísticas com validação estatística"""
        if combinacao not in self.melhores_combinacoes:
            self.melhores_combinacoes[combinacao] = {
                'acertos': 0,
                'tentativas': 0,
                'eficiencia_bruta': 0,
                'eficiencia_ajustada': 50,
                'confianca_estatistica': 0,
                'sequencia_atual_acertos': 0,
                'sequencia_atual_erros': 0,
                'ultimos_resultados': deque(maxlen=10),
                'probabilidade_teorica': probabilidade_teorica
            }
        
        dados = self.melhores_combinacoes[combinacao]
        dados['tentativas'] += 1
        dados['ultimos_resultados'].append(acerto)
        
        if acerto:
            dados['acertos'] += 1
            dados['sequencia_atual_acertos'] += 1
            dados['sequencia_atual_erros'] = 0
        else:
            dados['sequencia_atual_erros'] += 1
            dados['sequencia_atual_acertos'] = 0
        
        # Calcular eficiências
        if dados['tentativas'] > 0:
            dados['eficiencia_bruta'] = (dados['acertos'] / dados['tentativas']) * 100
            dados['eficiencia_ajustada'] = self.calcular_eficiencia_ajustada(dados, probabilidade_teorica)
            dados['confianca_estatistica'] = self.calcular_confianca_estatistica(
                dados['acertos'], dados['tentativas'], probabilidade_teorica
            )
        
        # VALIDAÇÃO ESTATÍSTICA: só mover para piores após validação
        if (dados['tentativas'] >= 10 and 
            dados['confianca_estatistica'] < 30 and
            dados['eficiencia_ajustada'] < 30):
            
            # Testar se a baixa performance é estatisticamente significativa
            teste = self.validacao.teste_binomial_90porcento(
                dados['acertos'], dados['tentativas']
            )
            
            if not teste['rejeita_h0']:  # Performance ruim é real
                if combinacao not in self.piores_combinacoes:
                    self.piores_combinacoes[combinacao] = dados.copy()
                    self.piores_combinacoes[combinacao]['motivo'] = 'baixa_eficiencia_validada'
                    
                    # Não remover imediatamente, apenas marcar
                    # del self.melhores_combinacoes[combinacao]
    
    def validar_padrao_estatistico(self, combinacao, numero, zonas_envolvidas, estrategia):
        """Valida padrões estatisticamente antes de aceitar"""
        if len(self.historico_aprendizado) < 20:
            return
        
        # Coletar dados recentes para validação
        dados_recentes = list(self.historico_aprendizado)[-50:]
        
        padrao = {
            'combinacao': combinacao,
            'numero': numero,
            'zonas': zonas_envolvidas,
            'estrategia': estrategia,
            'timestamp': len(self.historico_aprendizado)
        }
        
        # Validar usando teste estatístico
        if self.validacao.validar_padrao(padrao, dados_recentes):
            self.padroes_validados.append(padrao)
            
            # Limitar tamanho
            if len(self.padroes_validados) > 20:
                self.padroes_validados = self.padroes_validados[-20:]
        else:
            self.falso_positivos += 1
    
    def analisar_tendencias_temporais(self, numero, acerto):
        """Analisa tendências com análise estatística"""
        registro = {
            'numero': numero,
            'acerto': acerto,
            'timestamp': len(self.historico_aprendizado),
            'hora': pd.Timestamp.now().strftime('%H:%M'),
            'minuto': pd.Timestamp.now().minute
        }
        
        self.historico_aprendizado.append(registro)
    
    def gerar_recomendacoes_validas(self):
        """Gera recomendações validadas estatisticamente"""
        recomendacoes = {
            'melhor_combinacao': None,
            'probabilidade_ajustada': 0,
            'confianca_estatistica': 0,
            'evitar_combinacao': None,
            'padroes_validados': [],
            'alerta': None,
            'viabilidade_90porcento': False
        }
        
        # VERIFICAR VIABILIDADE DA META DE 90%
        if len(self.historico_aprendizado) >= 30:
            acertos_totais = sum(1 for r in self.historico_aprendizado if r['acerto'])
            teste_90 = self.validacao.teste_binomial_90porcento(
                acertos_totais, len(self.historico_aprendizado)
            )
            
            recomendacoes['viabilidade_90porcento'] = teste_90['rejeita_h0']
            
            if not teste_90['rejeita_h0']:
                recomendacoes['alerta'] = f"⚠️ Meta de 90% não suportada estatisticamente (p={teste_90['p_value']:.3f})"
        
        # ENCONTRAR MELHOR COMBINAÇÃO COM VALIDAÇÃO
        combinacoes_validadas = []
        
        for combinacao, dados in self.melhores_combinacoes.items():
            if (dados['tentativas'] >= 10 and  # Mínimo de amostras
                dados['confianca_estatistica'] >= 70 and  # Alta confiança estatística
                dados['eficiencia_ajustada'] >= 40):  # Eficiência ajustada boa
                
                score = dados['eficiencia_ajustada']
                
                # Bônus para confiança estatística alta
                if dados['confianca_estatistica'] >= 90:
                    score *= 1.3
                elif dados['confianca_estatistica'] >= 80:
                    score *= 1.2
                
                # Bônus para sequência de acertos (mas com cuidado)
                if dados['sequencia_atual_acertos'] >= 2:
                    # Verificar se não é apenas sorte
                    prob_sequencia = (dados['probabilidade_teorica'] ** dados['sequencia_atual_acertos'])
                    if prob_sequencia > 0.05:  # Não muito improvável
                        score *= 1.1
                
                combinacoes_validadas.append({
                    'combinacao': combinacao,
                    'score': score,
                    'eficiencia_ajustada': dados['eficiencia_ajustada'],
                    'confianca_estatistica': dados['confianca_estatistica'],
                    'tentativas': dados['tentativas'],
                    'sequencia_acertos': dados['sequencia_atual_acertos']
                })
        
        if combinacoes_validadas:
            # Ordenar por score ajustado
            combinacoes_validadas.sort(key=lambda x: x['score'], reverse=True)
            melhor = combinacoes_validadas[0]
            
            recomendacoes['melhor_combinacao'] = melhor['combinacao']
            recomendacoes['probabilidade_ajustada'] = min(melhor['score'], 95)
            recomendacoes['confianca_estatistica'] = melhor['confianca_estatistica']
            
            # Alerta para sequência forte com validação
            if (melhor['sequencia_acertos'] >= 3 and 
                melhor['confianca_estatistica'] >= 80):
                recomendacoes['alerta'] = f"🔥 SEQUÊNCIA FORTE VALIDADA: {melhor['combinacao']}"
        
        # IDENTIFICAR COMBINAÇÕES PARA EVITAR (com validação)
        for combinacao, dados in self.piores_combinacoes.items():
            if (dados.get('tentativas', 0) >= 10 and
                dados.get('confianca_estatistica', 0) < 30):
                recomendacoes['evitar_combinacao'] = combinacao
                break
        
        # PADRÕES VALIDADOS
        padroes_recentes = []
        for padrao in self.padroes_validados[-5:]:
            idade = len(self.historico_aprendizado) - padrao['timestamp']
            if idade <= 20:  # Padrões recentes
                padroes_recentes.append({
                    'combinacao': padrao.get('combinacao'),
                    'zonas': padrao.get('zonas', []),
                    'idade': idade
                })
        
        recomendacoes['padroes_validados'] = padroes_recentes
        
        return recomendacoes
    
    def get_estatisticas_aprendizado(self):
        """Retorna estatísticas detalhadas do aprendizado"""
        total_registros = len(self.historico_aprendizado)
        acertos_totais = sum(1 for r in self.historico_aprendizado if r['acerto'])
        
        estatisticas = {
            'total_analises': self.contador_analise,
            'total_registros': total_registros,
            'taxa_acerto_historico': (acertos_totais / total_registros * 100) if total_registros > 0 else 0,
            'melhores_combinacoes_count': len(self.melhores_combinacoes),
            'piores_combinacoes_count': len(self.piores_combinacoes),
            'padroes_validados_count': len(self.padroes_validados),
            'falso_positivos': self.falso_positivos,
            'taxa_validacao': (len(self.padroes_validados) / max(self.contador_analise, 1)) * 100
        }
        
        # Top combinações validadas
        top_combinacoes = []
        for combo, dados in self.melhores_combinacoes.items():
            if dados['tentativas'] >= 5:
                top_combinacoes.append({
                    'combinacao': combo,
                    'eficiencia_ajustada': dados['eficiencia_ajustada'],
                    'confianca_estatistica': dados['confianca_estatistica'],
                    'tentativas': dados['tentativas'],
                    'sequencia_acertos': dados['sequencia_atual_acertos']
                })
        
        top_combinacoes.sort(key=lambda x: x['eficiencia_ajustada'], reverse=True)
        estatisticas['top_combinacoes'] = top_combinacoes[:5]
        
        # Análise de viabilidade de 90%
        if total_registros >= 30:
            teste_90 = self.validacao.teste_binomial_90porcento(acertos_totais, total_registros)
            estatisticas['viabilidade_90porcento'] = {
                'p_value': teste_90['p_value'],
                'confianca': teste_90['confianca'],
                'viavel': teste_90['rejeita_h0']
            }
        
        return estatisticas
    
    def sugerir_ajustes_baseados_em_dados(self, historico_recente):
        """Sugere ajustes baseados em análise estatística"""
        if len(historico_recente) < 15:
            return "📊 Coletando dados para análise..."
        
        acertos_recentes = sum(1 for r in historico_recente if r['acerto'])
        taxa_recente = (acertos_recentes / len(historico_recente)) * 100
        
        # Teste estatístico da taxa recente
        prob_teorica = 24/37  # ~65% para 2 zonas
        teste_recente = binomtest(
            k=acertos_recentes,
            n=len(historico_recente),
            p=prob_teorica,
            alternative='greater'
        )
        
        sugestoes = []
        
        if teste_recente.pvalue < 0.05:
            # Performance recente é estatisticamente boa
            if taxa_recente > 70:
                sugestoes.append("📈 **Performance excelente** - Aumentar confiança")
            
            # Identificar combinações validadas
            for combo, dados in self.melhores_combinacoes.items():
                if (dados['confianca_estatistica'] >= 80 and
                    dados['sequencia_atual_acertos'] >= 2):
                    sugestoes.append(f"🎯 **{combo} validado estatisticamente** - Foco recomendado")
        
        else:
            # Performance não estatisticamente significativa
            sugestoes.append("📉 **Performance dentro do esperado** - Manter estratégia")
            
            # Verificar combinações problemáticas
            for combo, dados in self.piores_combinacoes.items():
                if dados.get('tentativas', 0) >= 5:
                    sugestoes.append(f"⚠️  **Evitar {combo}** - Baixa performance validada")
        
        # Sugestões baseadas em padrões temporais
        if len(historico_recente) > 20:
            horas = [r.get('hora', '') for r in historico_recente[-20:] if 'hora' in r]
            if horas:
                hora_contagem = Counter(horas)
                if hora_contagem:
                    hora_mais_comum = hora_contagem.most_common(1)[0]
                    sugestoes.append(f"🕒 **Horário produtivo:** {hora_mais_comum[0]} ({hora_mais_comum[1]} jogos)")
        
        return "\n".join(sugestoes) if sugestoes else "📊 Performance dentro das expectativas estatísticas"

# =============================
# SISTEMA DE OTIMIZAÇÃO DINÂMICA COM VALIDAÇÃO
# =============================
class SistemaOtimizacaoDinamica:
    def __init__(self):
        self.aprendizado = SistemaAprendizadoReforco()
        self.ultima_recomendacao = None
        self.contador_otimizacoes = 0
        self.estrategia_ativa = None
        self.performance_historica = deque(maxlen=100)
        self.alertas_otimizacao = []
        self.validacao = SistemaValidacaoEstatistica()
        
    def processar_resultado(self, resultado):
        """Processa resultado com otimização estatística"""
        try:
            # 1. Aprender com validação estatística
            recomendacoes = self.aprendizado.analisar_resultado(resultado)
            
            # 2. Atualizar performance histórica
            self.performance_historica.append({
                'timestamp': len(self.performance_historica),
                'acerto': resultado['acerto'],
                'estrategia': resultado['estrategia'],
                'numero': resultado['numero'],
                'zonas': resultado.get('zonas_envolvidas', [])
            })
            
            # 3. Gerar otimização validada
            otimizacao = self.gerar_otimizacao_validada(recomendacoes, resultado)
            
            # 4. Atualizar última recomendação
            self.ultima_recomendacao = {
                'recomendacoes': recomendacoes,
                'otimizacao': otimizacao,
                'timestamp': len(self.performance_historica)
            }
            
            self.contador_otimizacoes += 1
            
            return otimizacao
            
        except Exception as e:
            logging.error(f"Erro no sistema de otimização: {e}")
            return None
    
    def gerar_otimizacao_validada(self, recomendacoes, resultado):
        """Gera otimizações validadas estatisticamente"""
        otimizacao = {
            'acao': 'manter',
            'combinacao_sugerida': None,
            'probabilidade_ajustada': 0,
            'confianca_estatistica': 0,
            'razoes': [],
            'alerta': None,
            'viabilidade_90porcento': False
        }
        
        # VERIFICAR VIABILIDADE DE 90%
        if recomendacoes.get('viabilidade_90porcento') is not None:
            otimizacao['viabilidade_90porcento'] = recomendacoes['viabilidade_90porcento']
        
        if recomendacoes.get('alerta'):
            otimizacao['alerta'] = recomendacoes['alerta']
        
        # VERIFICAR MUDANÇA DE COMBINAÇÃO COM VALIDAÇÃO
        if recomendacoes.get('melhor_combinacao'):
            melhor_combo = recomendacoes['melhor_combinacao']
            prob_ajustada = recomendacoes['probabilidade_ajustada']
            confianca_estat = recomendacoes['confianca_estatistica']
            
            # Verificar combinação atual
            zonas_atual = resultado.get('zonas_envolvidas', [])
            if len(zonas_atual) > 1:
                combinacao_atual = tuple(sorted(zonas_atual))
                
                # Critérios para mudança:
                # 1. Combinação diferente
                # 2. Probabilidade ajustada alta (> 70%)
                # 3. Confiança estatística alta (> 75%)
                # 4. Combinação atual não é validada
                
                deve_mudar = False
                razoes_mudanca = []
                
                if combinacao_atual != melhor_combo:
                    if prob_ajustada >= 70:
                        razoes_mudanca.append(f"Melhor probabilidade ({prob_ajustada:.1f}%)")
                    
                    if confianca_estat >= 75:
                        razoes_mudanca.append(f"Alta confiança estatística ({confianca_estat:.1f}%)")
                    
                    # Verificar se combinação atual tem problemas
                    dados_atual = self.aprendizado.melhores_combinacoes.get(combinacao_atual)
                    if dados_atual:
                        if dados_atual.get('confianca_estatistica', 0) < 50:
                            razoes_mudanca.append("Baixa confiança na combinação atual")
                        if dados_atual.get('eficiencia_ajustada', 50) < 40:
                            razoes_mudanca.append("Baixa eficiência ajustada atual")
                    
                    if razoes_mudanca:
                        deve_mudar = True
                
                if deve_mudar:
                    otimizacao['acao'] = 'mudar'
                    otimizacao['combinacao_sugerida'] = melhor_combo
                    otimizacao['probabilidade_ajustada'] = prob_ajustada
                    otimizacao['confianca_estatistica'] = confianca_estat
                    otimizacao['razoes'] = razoes_mudanca
        
        # SE NÃO HOUVER RAZÕES ESTATÍSTICAS PARA MUDAR, MANTER
        if not otimizacao['razoes']:
            otimizacao['razoes'].append("Performance dentro das expectativas estatísticas")
        
        return otimizacao
    
    def aplicar_otimizacao(self, sistema_principal, otimizacao):
        """Aplica otimização com validação"""
        try:
            if (otimizacao['acao'] == 'mudar' and 
                otimizacao['combinacao_sugerida'] and
                otimizacao['confianca_estatistica'] >= 70):
                
                combinacao = otimizacao['combinacao_sugerida']
                
                # Verificar se o sistema principal pode criar previsão
                if sistema_principal.criar_previsao_com_combinacao(combinacao):
                    logging.info(f"🔄 OTIMIZAÇÃO VALIDADA APLICADA: {combinacao}")
                    
                    # Registrar alerta
                    self.alertas_otimizacao.append({
                        'tipo': 'otimizacao_validada',
                        'mensagem': f"Otimização aplicada: {combinacao} (Conf: {otimizacao['confianca_estatistica']:.1f}%)",
                        'timestamp': len(self.performance_historica),
                        'confianca': otimizacao['confianca_estatistica']
                    })
                    
                    return True
            
            elif otimizacao.get('alerta'):
                # Registrar alerta com prioridade
                prioridade = 'alta' if '90%' in otimizacao['alerta'] else 'media'
                
                self.alertas_otimizacao.append({
                    'tipo': 'alerta_estatistico',
                    'mensagem': otimizacao['alerta'],
                    'timestamp': len(self.performance_historica),
                    'prioridade': prioridade
                })
                
                logging.info(f"⚠️ ALERTA ESTATÍSTICO: {otimizacao['alerta']}")
            
            return False
            
        except Exception as e:
            logging.error(f"Erro ao aplicar otimização: {e}")
            return False
    
    def get_resumo_otimizacao(self):
        """Retorna resumo das otimizações com análise estatística"""
        resumo = {
            'total_otimizacoes': self.contador_otimizacoes,
            'ultima_recomendacao': self.ultima_recomendacao,
            'alertas_ativos': len([a for a in self.alertas_otimizacao[-10:] 
                                  if a.get('prioridade') == 'alta']),
            'performance_recente': self.calcular_performance_recente(),
            'viabilidade_90porcento': False
        }
        
        # Estatísticas do aprendizado
        estatisticas_aprendizado = self.aprendizado.get_estatisticas_aprendizado()
        resumo['estatisticas_aprendizado'] = estatisticas_aprendizado
        
        # Verificar viabilidade de 90%
        if 'viabilidade_90porcento' in estatisticas_aprendizado:
            resumo['viabilidade_90porcento'] = estatisticas_aprendizado['viabilidade_90porcento'].get('viavel', False)
        
        return resumo
    
    def calcular_performance_recente(self):
        """Calcula performance recente com análise estatística"""
        if len(self.performance_historica) < 10:
            return {"total": 0, "acertos": 0, "taxa": 0, "confianca": 0}
        
        recentes = list(self.performance_historica)[-10:]
        acertos = sum(1 for r in recentes if r['acerto'])
        total = len(recentes)
        taxa = (acertos / total * 100) if total > 0 else 0
        
        # Calcular confiança estatística da performance recente
        confianca = 0
        if total >= 5:
            prob_teorica = 24/37  # ~65% para 2 zonas
            teste = binomtest(k=acertos, n=total, p=prob_teorica, alternative='greater')
            confianca = (1 - teste.pvalue) * 100
        
        return {
            "total": total,
            "acertos": acertos,
            "taxa": taxa,
            "confianca": confianca
        }
    
    def sugerir_melhoria_estrategia(self, sistema_principal):
        """Sugere melhorias baseadas em análise estatística"""
        sugestoes = []
        
        # 1. Análise de combinações com validação estatística
        combinacoes_validadas = []
        for combo, dados in self.aprendizado.melhores_combinacoes.items():
            if (dados['tentativas'] >= 10 and
                dados['confianca_estatistica'] >= 75 and
                dados['eficiencia_ajustada'] >= 50):
                
                combinacoes_validadas.append((combo, dados['eficiencia_ajustada']))
        
        if combinacoes_validadas:
            melhor_combo, melhor_eff = max(combinacoes_validadas, key=lambda x: x[1])
            sugestoes.append(f"🎯 **Focar em {melhor_combo}** ({melhor_eff:.1f}% eff ajustada)")
        
        # 2. Combinações para evitar
        combinacoes_evitar = []
        for combo, dados in self.aprendizado.piores_combinacoes.items():
            if dados.get('tentativas', 0) >= 5:
                combinacoes_evitar.append((combo, dados.get('eficiencia_ajustada', 0)))
        
        if combinacoes_evitar:
            pior_combo, pior_eff = min(combinacoes_evitar, key=lambda x: x[1])
            sugestoes.append(f"🚫 **Evitar {pior_combo}** ({pior_eff:.1f}% eff ajustada)")
        
        # 3. Recomendações do aprendizado por reforço
        if self.ultima_recomendacao:
            rec = self.ultima_recomendacao['recomendacoes']
            if rec.get('melhor_combinacao'):
                confianca = rec.get('confianca_estatistica', 0)
                if confianca >= 70:
                    sugestoes.append(f"🤖 **Recomendação validada:** {rec['melhor_combinacao']} (Conf: {confianca:.1f}%)")
        
        # 4. Análise de viabilidade de 90%
        estatisticas = self.aprendizado.get_estatisticas_aprendizado()
        if 'viabilidade_90porcento' in estatisticas:
            viabilidade = estatisticas['viabilidade_90porcento']
            if viabilidade.get('viavel', False):
                sugestoes.append(f"✅ **Meta de 90% viável** (p={viabilidade['p_value']:.3f})")
            else:
                sugestoes.append(f"⚠️  **Meta de 90% não suportada** (p={viabilidade['p_value']:.3f})")
        
        return sugestoes if sugestoes else ["📊 Coletando dados para recomendações estatísticas"]

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO - CHECKBOXES
# =============================
def inicializar_config_alertas():
    """Inicializa configurações de alertas se não existirem"""
    if 'alertas_config' not in st.session_state:
        st.session_state.alertas_config = {
            'alertas_previsao': True,
            'alertas_resultado': True,
            'alertas_rotacao': True,
            'alertas_tendencia': True,
            'alertas_treinamento': True,
            'alertas_erros': True,
            'alertas_acertos': True,
            'alertas_estatisticos': True  # Novo: alertas estatísticos
        }

# Chama a função na inicialização
inicializar_config_alertas()

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        if 'sistema' not in st.session_state:
            logging.warning("❌ Sistema não está na sessão")
            return False
            
        sistema = st.session_state.sistema
        
        # Coletar dados básicos primeiro
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'alertas_config': st.session_state.get('alertas_config', {
                'alertas_previsao': True,
                'alertas_resultado': True,
                'alertas_rotacao': True,
                'alertas_tendencia': True,
                'alertas_treinamento': True,
                'alertas_erros': True,
                'alertas_acertos': True,
                'alertas_estatisticos': True
            }),
            'sistema_acertos': sistema.acertos,
            'sistema_erros': sistema.erros,
            'sistema_estrategias_contador': sistema.estrategias_contador,
            'sistema_historico_desempenho': sistema.historico_desempenho,
            'sistema_contador_sorteios_global': sistema.contador_sorteios_global,
            'sistema_sequencia_erros': sistema.sequencia_erros,
            'sistema_ultima_estrategia_erro': sistema.ultima_estrategia_erro,
            'sistema_sequencia_acertos': sistema.sequencia_acertos,
            'sistema_ultima_combinacao_acerto': sistema.ultima_combinacao_acerto,
            'sistema_historico_combinacoes_acerto': sistema.historico_combinacoes_acerto,
            'estrategia_selecionada': sistema.estrategia_selecionada,
            'sistema_historico_combinacoes': sistema.historico_combinacoes,
            'sistema_combinacoes_quentes': sistema.combinacoes_quentes,
            'sistema_combinacoes_frias': sistema.combinacoes_frias,
        }
        
        # Adicionar dados do sistema de otimização se existir
        if hasattr(sistema, 'sistema_otimizacao'):
            try:
                # Salvar dados do aprendizado
                session_data['rl_historico_aprendizado'] = list(sistema.sistema_otimizacao.aprendizado.historico_aprendizado)
                session_data['rl_melhores_combinacoes'] = sistema.sistema_otimizacao.aprendizado.melhores_combinacoes
                session_data['rl_piores_combinacoes'] = sistema.sistema_otimizacao.aprendizado.piores_combinacoes
                session_data['rl_padroes_validados'] = sistema.sistema_otimizacao.aprendizado.padroes_validados
                session_data['rl_contador_analise'] = sistema.sistema_otimizacao.aprendizado.contador_analise
                
                # Salvar dados da otimização
                session_data['opt_contador_otimizacoes'] = sistema.sistema_otimizacao.contador_otimizacoes
                session_data['opt_ultima_recomendacao'] = sistema.sistema_otimizacao.ultima_recomendacao
                session_data['opt_performance_historica'] = list(sistema.sistema_otimizacao.performance_historica)
                session_data['opt_alertas_otimizacao'] = sistema.sistema_otimizacao.alertas_otimizacao
                
                logging.info(f"✅ Dados do sistema de otimização salvos")
            except Exception as e:
                logging.warning(f"⚠️ Erro ao salvar dados de otimização: {e}")
        
        # Adicionar dados específicos das estratégias se existirem
        if hasattr(sistema, 'estrategia_zonas'):
            session_data['zonas_historico'] = list(sistema.estrategia_zonas.historico)
            session_data['zonas_stats'] = sistema.estrategia_zonas.stats_zonas
            
        if hasattr(sistema, 'estrategia_midas'):
            session_data['midas_historico'] = list(sistema.estrategia_midas.historico)
            
        if hasattr(sistema, 'estrategia_ml'):
            session_data['ml_historico'] = list(sistema.estrategia_ml.historico)
            session_data['ml_contador_sorteios'] = sistema.estrategia_ml.contador_sorteios
            session_data['ml_sequencias_padroes'] = getattr(sistema.estrategia_ml, 'sequencias_padroes', {})
            session_data['ml_metricas_padroes'] = getattr(sistema.estrategia_ml, 'metricas_padroes', {})
            
        if hasattr(sistema, 'sistema_tendencias'):
            session_data['sistema_tendencias_historico'] = list(sistema.sistema_tendencias.historico_tendencias)
            session_data['sistema_tendencias_estado'] = sistema.sistema_tendencias.estado_tendencia
            session_data['sistema_tendencias_ativa'] = sistema.sistema_tendencias.tendencia_ativa
            session_data['sistema_tendencias_confirmacoes'] = sistema.sistema_tendencias.contador_confirmacoes
            session_data['sistema_tendencias_acertos'] = sistema.sistema_tendencias.contador_acertos_tendencia
            session_data['sistema_tendencias_erros'] = sistema.sistema_tendencias.contador_erros_tendencia
            session_data['sistema_tendencias_operacoes'] = sistema.sistema_tendencias.rodadas_operando
            session_data['sistema_tendencias_historico_zonas'] = list(sistema.sistema_tendencias.historico_zonas_dominantes)
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        logging.info(f"✅ Sessão salva com {len(session_data)} itens")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}", exc_info=True)
        return False

def carregar_sessao():
    """Carrega todos os dados da sessão do arquivo"""
    try:
        if not os.path.exists(SESSION_DATA_PATH):
            logging.info("ℹ️  Nenhuma sessão salva encontrada")
            return False
            
        with open(SESSION_DATA_PATH, 'rb') as f:
            session_data = pickle.load(f)
        
        if not isinstance(session_data, dict):
            logging.error("❌ Dados de sessão corrompidos")
            return False
            
        # Inicializar config de alertas primeiro
        inicializar_config_alertas()
        
        # Carregar dados básicos
        st.session_state.historico = session_data.get('historico', [])
        st.session_state.telegram_token = session_data.get('telegram_token', '')
        st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
        
        # Carregar configurações de alertas (se existirem)
        if 'alertas_config' in session_data:
            st.session_state.alertas_config = session_data['alertas_config']
        
        if 'sistema' not in st.session_state:
            st.session_state.sistema = SistemaRoletaCompleto()
            
        sistema = st.session_state.sistema
        
        # Carregar dados do sistema
        sistema.acertos = session_data.get('sistema_acertos', 0)
        sistema.erros = session_data.get('sistema_erros', 0)
        sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
        sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
        sistema.contador_sorteios_global = session_data.get('sistema_contador_sorteios_global', 0)
        sistema.sequencia_erros = session_data.get('sistema_sequencia_erros', 0)
        sistema.ultima_estrategia_erro = session_data.get('sistema_ultima_estrategia_erro', '')
        sistema.sequencia_acertos = session_data.get('sistema_sequencia_acertos', 0)
        sistema.ultima_combinacao_acerto = session_data.get('sistema_ultima_combinacao_acerto', [])
        sistema.historico_combinacoes_acerto = session_data.get('sistema_historico_combinacoes_acerto', [])
        sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Zonas')
        sistema.historico_combinacoes = session_data.get('sistema_historico_combinacoes', {})
        sistema.combinacoes_quentes = session_data.get('sistema_combinacoes_quentes', [])
        sistema.combinacoes_frias = session_data.get('sistema_combinacoes_frias', [])
        
        # Carregar dados do sistema de otimização
        if hasattr(sistema, 'sistema_otimizacao'):
            try:
                # Carregar dados do aprendizado
                rl_historico = session_data.get('rl_historico_aprendizado', [])
                sistema.sistema_otimizacao.aprendizado.historico_aprendizado = deque(rl_historico, maxlen=1000)
                sistema.sistema_otimizacao.aprendizado.melhores_combinacoes = session_data.get('rl_melhores_combinacoes', {})
                sistema.sistema_otimizacao.aprendizado.piores_combinacoes = session_data.get('rl_piores_combinacoes', {})
                sistema.sistema_otimizacao.aprendizado.padroes_validados = session_data.get('rl_padroes_validados', [])
                sistema.sistema_otimizacao.aprendizado.contador_analise = session_data.get('rl_contador_analise', 0)
                
                # Carregar dados da otimização
                sistema.sistema_otimizacao.contador_otimizacoes = session_data.get('opt_contador_otimizacoes', 0)
                sistema.sistema_otimizacao.ultima_recomendacao = session_data.get('opt_ultima_recomendacao', None)
                
                opt_performance = session_data.get('opt_performance_historica', [])
                sistema.sistema_otimizacao.performance_historica = deque(opt_performance, maxlen=100)
                sistema.sistema_otimizacao.alertas_otimizacao = session_data.get('opt_alertas_otimizacao', [])
                
                logging.info(f"✅ Dados do sistema de otimização carregados")
            except Exception as e:
                logging.warning(f"⚠️ Erro ao carregar dados de otimização: {e}")
        
        # Carregar dados das estratégias
        if hasattr(sistema, 'estrategia_zonas'):
            zonas_historico = session_data.get('zonas_historico', [])
            sistema.estrategia_zonas.historico = deque(zonas_historico, maxlen=70)
            sistema.estrategia_zonas.stats_zonas = session_data.get('zonas_stats', {
                'Vermelha': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                'Azul': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                'Amarela': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
            })
            
            # Reconstruir números das zonas
            for zona, central in sistema.estrategia_zonas.zonas.items():
                qtd = sistema.estrategia_zonas.quantidade_zonas.get(zona, 6)
                sistema.estrategia_zonas.numeros_zonas[zona] = sistema.estrategia_zonas.roleta.get_vizinhos_zona(central, qtd)
            
        if hasattr(sistema, 'estrategia_midas'):
            midas_historico = session_data.get('midas_historico', [])
            sistema.estrategia_midas.historico = deque(midas_historico, maxlen=15)
            
        if hasattr(sistema, 'estrategia_ml'):
            ml_historico = session_data.get('ml_historico', [])
            sistema.estrategia_ml.historico = deque(ml_historico, maxlen=30)
            sistema.estrategia_ml.contador_sorteios = session_data.get('ml_contador_sorteios', 0)
            
            # Carregar dados do ML
            sequencias_padroes = session_data.get('ml_sequencias_padroes', {})
            if isinstance(sequencias_padroes, dict):
                sistema.estrategia_ml.sequencias_padroes = sequencias_padroes
            else:
                sistema.estrategia_ml.sequencias_padroes = {
                    'sequencias_ativas': {},
                    'historico_sequencias': [],
                    'padroes_detectados': []
                }
                
            metricas_padroes = session_data.get('ml_metricas_padroes', {})
            if isinstance(metricas_padroes, dict):
                sistema.estrategia_ml.metricas_padroes = metricas_padroes
            else:
                sistema.estrategia_ml.metricas_padroes = {
                    'padroes_detectados_total': 0,
                    'padroes_acertados': 0,
                    'padroes_errados': 0,
                    'eficiencia_por_tipo': {},
                    'historico_validacao': []
                }
                
            # Reconstruir números das zonas do ML
            for zona, central in sistema.estrategia_ml.zonas_ml.items():
                qtd = sistema.estrategia_ml.quantidade_zonas_ml.get(zona, 6)
                sistema.estrategia_ml.numeros_zonas_ml[zona] = sistema.estrategia_ml.roleta.get_vizinhos_zona(central, qtd)
        
        if hasattr(sistema, 'sistema_tendencias'):
            tendencias_historico = session_data.get('sistema_tendencias_historico', [])
            sistema.sistema_tendencias.historico_tendencias = deque(tendencias_historico, maxlen=50)
            sistema.sistema_tendencias.estado_tendencia = session_data.get('sistema_tendencias_estado', 'aguardando')
            sistema.sistema_tendencias.tendencia_ativa = session_data.get('sistema_tendencias_ativa', None)
            sistema.sistema_tendencias.contador_confirmacoes = session_data.get('sistema_tendencias_confirmacoes', 0)
            sistema.sistema_tendencias.contador_acertos_tendencia = session_data.get('sistema_tendencias_acertos', 0)
            sistema.sistema_tendencias.contador_erros_tendencia = session_data.get('sistema_tendencias_erros', 0)
            sistema.sistema_tendencias.rodadas_operando = session_data.get('sistema_tendencias_operacoes', 0)
            
            tendencias_historico_zonas = session_data.get('sistema_tendencias_historico_zonas', [])
            sistema.sistema_tendencias.historico_zonas_dominantes = deque(tendencias_historico_zonas, maxlen=10)
        
        logging.info(f"✅ Sessão carregada: {sistema.acertos} acertos, {sistema.erros} erros")
        return True
        
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}", exc_info=True)
        return False

def limpar_sessao():
    """Limpa todos os dados da sessão"""
    try:
        arquivos = [SESSION_DATA_PATH, HISTORICO_PATH, ML_MODEL_PATH, SCALER_PATH, META_PATH, RL_MODEL_PATH]
        for arquivo in arquivos:
            if os.path.exists(arquivo):
                os.remove(arquivo)
                logging.info(f"🗑️ Removido: {arquivo}")
        
        # Limpar session state
        chaves = list(st.session_state.keys())
        for chave in chaves:
            del st.session_state[chave]
            
        st.rerun()
        logging.info("🗑️ Sessão limpa com sucesso")
        
    except Exception as e:
        logging.error(f"❌ Erro ao limpar sessão: {e}")

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================
def enviar_previsao_super_simplificada(previsao):
    """Envia notificação de previsão super simplificada"""
    try:
        # Verificar se alertas de previsão estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_previsao', True):
                return
        
        if not previsao:
            return
            
        nome_estrategia = previsao.get('nome', 'Desconhecida')
        numeros_apostar = previsao.get('numeros_apostar', [])
        
        if not numeros_apostar:
            logging.warning("⚠️ Previsão sem números para apostar")
            return
        
        numeros_apostar = sorted(numeros_apostar)
        
        if 'Zonas' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            confianca = previsao.get('confianca', 'Média')
            
            if len(zonas_envolvidas) > 1:
                nucleo1 = "7" if zonas_envolvidas[0] == 'Vermelha' else "10" if zonas_envolvidas[0] == 'Azul' else "2"
                nucleo2 = "7" if zonas_envolvidas[1] == 'Vermelha' else "10" if zonas_envolvidas[1] == 'Azul' else "2"
                mensagem = f"🔥 NÚCLEOS {nucleo1}+{nucleo2} - CONFIANÇA {confianca.upper()}"
                
                if 'sistema' in st.session_state:
                    sistema = st.session_state.sistema
                    combinacao = tuple(sorted(zonas_envolvidas))
                    if hasattr(sistema, 'combinacoes_quentes') and combinacao in sistema.combinacoes_quentes:
                        dados = sistema.historico_combinacoes.get(combinacao, {})
                        eff = dados.get('eficiencia', 0)
                        mensagem += f" 🏆 COMBO EFICIENTE ({eff:.1f}%)"
            else:
                zona = previsao.get('zona', '')
                nucleo = "7" if zona == 'Vermelha' else "10" if zona == 'Azul' else "2"
                mensagem = f"🎯 NÚCLEO {nucleo} - CONFIANÇA {confianca.upper()}"
            
        elif 'Machine Learning' in nome_estrategia or 'ML' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            confianca = previsao.get('confianca', 'Média')
            
            if len(zonas_envolvidas) > 1:
                nucleo1 = "7" if zonas_envolvidas[0] == 'Vermelha' else "10" if zonas_envolvidas[0] == 'Azul' else "2"
                nucleo2 = "7" if zonas_envolvidas[1] == 'Vermelha' else "10" if zonas_envolvidas[1] == 'Azul' else "2"
                mensagem = f"🤖 NÚCLEOS {nucleo1}+{nucleo2} - CONFIANÇA {confianca.upper()}"
            else:
                zona_ml = previsao.get('zona_ml', '')
                nucleo = "7" if zona_ml == 'Vermelha' else "10" if zona_ml == 'Azul' else "2"
                mensagem = f"🤖 NÚCLEO {nucleo} - CONFIANÇA {confianca.upper()}"
        
        else:
            mensagem = f"💰 {nome_estrategia} - APOSTAR AGORA"
        
        st.toast(f"🎯 PREVISÃO CONFIRMADA", icon="🔥")
        st.warning(f"🔔 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_previsao', True)):
                enviar_alerta_numeros_simplificado(previsao)
                enviar_telegram(f"🚨 PREVISÃO ATIVA\n{mensagem}\n💎 CONFIANÇA: {previsao.get('confianca', 'ALTA')}")
                
        salvar_sessao()
        
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_alerta_numeros_simplificado(previsao):
    """Envia alerta alternativo super simplificado com os números para apostar"""
    try:
        if not previsao:
            return
            
        nome_estrategia = previsao.get('nome', '')
        numeros_apostar = previsao.get('numeros_apostar', [])
        
        if not numeros_apostar:
            return
            
        numeros_apostar = sorted(numeros_apostar)
        
        metade = len(numeros_apostar) // 2
        linha1 = " ".join(map(str, numeros_apostar[:metade]))
        linha2 = " ".join(map(str, numeros_apostar[metade:]))
        
        if 'Zonas' in nome_estrategia:
            emoji = "🔥"
        elif 'ML' in nome_estrategia:
            emoji = "🤖"
        else:
            emoji = "💰"
            
        mensagem_simplificada = f"{emoji} APOSTAR AGORA\n{linha1}\n{linha2}"
        
        enviar_telegram(mensagem_simplificada)
        logging.info("🔔 Alerta simplificado enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta simplificado: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    """Envia notificação de resultado super simplificada"""
    try:
        # Verificar se alertas de resultado estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_resultado', True):
                return
        
        # Verificar se alertas específicos por tipo estão ativados
        if acerto and not st.session_state.alertas_config.get('alertas_acertos', True):
            return
        if not acerto and not st.session_state.alertas_config.get('alertas_erros', True):
            return
            
        if acerto:
            if 'Zonas' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha':
                            nucleos.append("7")
                        elif zona == 'Azul':
                            nucleos.append("10")
                        elif zona == 'Amarela':
                            nucleos.append("2")
                        else:
                            nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            elif 'ML' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha':
                            nucleos.append("7")
                        elif zona == 'Azul':
                            nucleos.append("10")
                        elif zona == 'Amarela':
                            nucleos.append("2")
                        else:
                            nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            else:
                mensagem = f"✅ Acerto\n🎲 Número: {numero_real}"
        else:
            mensagem = f"❌ Erro\n🎲 Número: {numero_real}"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        
        if acerto:
            st.success(f"📢 {mensagem}")
        else:
            st.error(f"📢 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state):
                
                # Verificar se alertas de resultado estão ativados
                if st.session_state.alertas_config.get('alertas_resultado', True):
                    # Verificar se alertas específicos por tipo estão ativados
                    if (acerto and st.session_state.alertas_config.get('alertas_acertos', True)) or \
                       (not acerto and st.session_state.alertas_config.get('alertas_erros', True)):
                        enviar_telegram(f"📢 RESULTADO\n{mensagem}")
                        enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia)
                
        salvar_sessao()
        
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia):
    """Envia alerta de conferência super simplificado"""
    try:
        if acerto:
            mensagem = f"🎉 ACERTOU! {numero_real}"
        else:
            mensagem = f"💥 ERROU! {numero_real}"
            
        enviar_telegram(mensagem)
        logging.info("🔔 Alerta de conferência enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta de conferência: {e}")

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova):
    """Envia notificação de rotação automática"""
    try:
        # Verificar se alertas de rotação estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_rotacao', True):
                return
                
        mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(f"🔄 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_rotacao', True)):
                enviar_telegram(f"🔄 ROTAÇÃO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

def enviar_rotacao_por_acertos_combinacoes(combinacao_anterior, combinacao_nova):
    """Envia notificação de rotação por acertos em combinações"""
    try:
        # Verificar se alertas de rotação estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_rotacao', True):
                return
                
        def combo_para_nucleos(combo):
            nucleos = []
            for zona in combo:
                if zona == 'Vermelha':
                    nucleos.append("7")
                elif zona == 'Azul':
                    nucleos.append("10") 
                elif zona == 'Amarela':
                    nucleos.append("2")
                else:
                    nucleos.append(zona)
            return "+".join(nucleos)
        
        nucleo_anterior = combo_para_nucleos(combinacao_anterior)
        nucleo_novo = combo_para_nucleos(combinacao_nova)
        
        mensagem = f"🎯 ROTAÇÃO POR 3 ACERTOS SEGUIDOS\nNúcleos {nucleo_anterior} → Núcleos {nucleo_novo}\n✅ 3 acertos consecutivos - Alternando combinações"
        
        st.toast("🎯 Rotação por Acertos", icon="✅")
        st.success(f"🎯 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_rotacao', True)):
                enviar_telegram(f"🎯 ROTAÇÃO POR ACERTOS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação por acertos: {e}")

def enviar_rotacao_por_2_erros(combinacao_antiga, combinacao_nova):
    """Envia notificação de rotação por 2 erros seguidos"""
    try:
        # Verificar se alertas de rotação estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_rotacao', True):
                return
                
        def combo_para_nucleos(combo):
            nucleos = []
            for zona in combo:
                if zona == 'Vermelha':
                    nucleos.append("7")
                elif zona == 'Azul':
                    nucleos.append("10") 
                elif zona == 'Amarela':
                    nucleos.append("2")
                else:
                    nucleos.append(zona)
            return "+".join(nucleos)
        
        nucleo_antigo = combo_para_nucleos(combinacao_antiga)
        nucleo_novo = combo_para_nucleos(combinacao_nova)
        
        mensagem = f"🚨 ROTAÇÃO POR 2 ERROS SEGUIDOS\nNúcleos {nucleo_antigo} → Núcleos {nucleo_novo}\n⚠️ 2 erros consecutivos - Mudando de combinação"
        
        st.toast("🚨 Rotação por 2 Erros", icon="⚠️")
        st.warning(f"🚨 {mensagem}")
        
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_rotacao', True)):
                enviar_telegram(f"🚨 ROTAÇÃO POR 2 ERROS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação por 2 erros: {e}")

def enviar_alerta_tendencia(analise_tendencia):
    """Envia alerta de tendência na interface"""
    estado = analise_tendencia['estado']
    zona = analise_tendencia['zona_dominante']
    mensagem = analise_tendencia['mensagem']
    
    # Verificar se alertas de tendência estão ativados
    if 'alertas_config' in st.session_state:
        if not st.session_state.alertas_config.get('alertas_tendencia', True):
            return
    
    if estado == "ativa" and analise_tendencia['acao'] == "operar":
        st.toast("🎯 TENDÊNCIA CONFIRMADA - OPERAR!", icon="🔥")
        st.success(f"📈 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_tendencia', True)):
                enviar_telegram(f"🎯 TENDÊNCIA CONFIRMADA\n📍 Zona: {zona}\n📈 Estado: {estado}\n💡 Ação: OPERAR\n📊 {mensagem}")
        
    elif estado == "enfraquecendo":
        st.toast("⚠️ TENDÊNCIA ENFRAQUECENDO", icon="⚠️")
        st.warning(f"📉 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_tendencia', True)):
                enviar_telegram(f"⚠️ TENDÊNCIA ENFRAQUECENDO\n📍 Zona: {zona}\n📈 Estado: {estado}\n💡 Ação: AGUARDAR\n📊 {mensagem}")
        
    elif estado == "morta":
        st.toast("🟥 TENDÊNCIA MORTA - PARAR", icon="🛑")
        st.error(f"💀 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_tendencia', True)):
                enviar_telegram(f"🟥 TENDÊNCIA MORTA\n📈 Estado: {estado}\n💡 Ação: PARAR\n📊 {mensagem}")

def enviar_alerta_estatistico(mensagem, prioridade='media'):
    """Envia alerta estatístico"""
    try:
        # Verificar se alertas estatísticos estão ativados
        if 'alertas_config' in st.session_state:
            if not st.session_state.alertas_config.get('alertas_estatisticos', True):
                return
        
        if prioridade == 'alta':
            st.toast("📊 ALERTA ESTATÍSTICO IMPORTANTE", icon="⚠️")
            st.error(f"📊 {mensagem}")
        else:
            st.toast("📊 Análise Estatística", icon="📈")
            st.info(f"📊 {mensagem}")
        
        # Enviar para Telegram se configurado
        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
            if (st.session_state.telegram_token and st.session_state.telegram_chat_id and 
                'alertas_config' in st.session_state and 
                st.session_state.alertas_config.get('alertas_estatisticos', True)):
                enviar_telegram(f"📊 ALERTA ESTATÍSTICO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar alerta estatístico: {e}")

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    try:
        if 'telegram_token' not in st.session_state or 'telegram_chat_id' not in st.session_state:
            return
            
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        
        if not token or not chat_id:
            return
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info("✅ Mensagem enviada para Telegram com sucesso")
        else:
            logging.error(f"❌ Erro ao enviar para Telegram: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Erro na conexão com Telegram: {e}")

# =============================
# SISTEMA DE DETECÇÃO DE TENDÊNCIAS
# =============================
class SistemaTendencias:
    def __init__(self):
        self.historico_tendencias = deque(maxlen=50)
        self.tendencia_ativa = None
        self.estado_tendencia = "aguardando"
        self.contador_confirmacoes = 0
        self.contador_erros_tendencia = 0
        self.contador_acertos_tendencia = 0
        self.ultima_zona_dominante = None
        self.historico_zonas_dominantes = deque(maxlen=10)
        self.rodadas_operando = 0
        self.max_operacoes_por_tendencia = 4
        
    def analisar_tendencia(self, zonas_rankeadas, acerto_ultima=False, zona_acertada=None):
        """
        Analisa a tendência atual baseado no fluxograma
        """
        if not zonas_rankeadas or len(zonas_rankeadas) < 2:
            return self._criar_resposta_tendencia("aguardando", None, "Aguardando dados suficientes")
        
        try:
            zona_top1, score_top1 = zonas_rankeadas[0]
            zona_top2, score_top2 = zonas_rankeadas[1] if len(zonas_rankeadas) > 1 else (None, 0)
            
            # Registrar zona dominante atual
            if zona_top1:
                self.historico_zonas_dominantes.append(zona_top1)
            
            # Analisar estado atual
            if self.estado_tendencia in ["aguardando", "formando"]:
                return self._analisar_formacao_tendencia(zona_top1, zona_top2, score_top1, zonas_rankeadas)
            
            elif self.estado_tendencia == "ativa":
                return self._analisar_tendencia_ativa(zona_top1, zona_top2, acerto_ultima, zona_acertada)
            
            elif self.estado_tendencia == "enfraquecendo":
                return self._analisar_tendencia_enfraquecendo(zona_top1, zona_top2, acerto_ultima, zona_acertada)
            
            elif self.estado_tendencia == "morta":
                return self._analisar_reinicio_tendencia(zona_top1, zonas_rankeadas)
            
        except Exception as e:
            logging.error(f"Erro na análise de tendência: {e}")
            
        return self._criar_resposta_tendencia("aguardando", None, "Estado não reconhecido")
    
    def _analisar_formacao_tendencia(self, zona_top1, zona_top2, score_top1, zonas_rankeadas):
        """Etapa 2 do fluxograma - Formação da Tendência"""
        
        if not zona_top1:
            return self._criar_resposta_tendencia("aguardando", None, "Sem zona dominante")
        
        # Verificar se a mesma zona aparece repetidamente
        freq_zona_top1 = list(self.historico_zonas_dominantes).count(zona_top1)
        frequencia_minima = 3 if len(self.historico_zonas_dominantes) >= 5 else 2
        
        # Verificar dispersão
        dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
        
        if (freq_zona_top1 >= frequencia_minima and 
            score_top1 >= 25 and
            dispersao <= 0.6):
            
            if self.estado_tendencia == "aguardando":
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                
                return self._criar_resposta_tendencia(
                    "formando", zona_top1, 
                    f"Tendência se formando - Zona {zona_top1} aparecendo repetidamente"
                )
            
            elif self.estado_tendencia == "formando":
                self.contador_confirmacoes += 1
                
                if self.contador_confirmacoes >= 2:
                    self.estado_tendencia = "ativa"
                    self.contador_acertos_tendencia = 0
                    self.contador_erros_tendencia = 0
                    self.rodadas_operando = 0
                    
                    return self._criar_resposta_tendencia(
                        "ativa", zona_top1,
                        f"✅ TENDÊNCIA CONFIRMADA - Zona {zona_top1} dominante. Pode operar!"
                    )
        
        return self._criar_resposta_tendencia(
            self.estado_tendencia, self.tendencia_ativa,
            f"Aguardando confirmação - {zona_top1} no Top 1"
        )
    
    def _analisar_tendencia_ativa(self, zona_top1, zona_top2, acerto_ultima, zona_acertada):
        """Etapa 3-4 do fluxograma - Tendência Ativa e Hora de Operar"""
        
        if not self.tendencia_ativa:
            return self._criar_resposta_tendencia("aguardando", None, "Sem tendência ativa")
        
        # Verificar se ainda é a mesma zona dominante
        mesma_zona = zona_top1 == self.tendencia_ativa
        
        # Atualizar contadores
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        self.rodadas_operando += 1
        
        # HORA DE OPERAR
        if (self.contador_acertos_tendencia >= 1 and 
            self.contador_erros_tendencia == 0 and
            self.rodadas_operando <= self.max_operacoes_por_tendencia):
            
            acao = "operar" if mesma_zona else "aguardar"
            mensagem = f"🔥 OPERAR - Tendência {self.tendencia_ativa} forte ({self.contador_acertos_tendencia} acertos)"
            
            return self._criar_resposta_tendencia("ativa", self.tendencia_ativa, mensagem, acao)
        
        # VERIFICAR ENFRAQUECIMENTO
        sinais_enfraquecimento = self._detectar_enfraquecimento(zona_top1, zona_top2, acerto_ultima)
        
        if sinais_enfraquecimento:
            self.estado_tendencia = "enfraquecendo"
            return self._criar_resposta_tendencia(
                "enfraquecendo", self.tendencia_ativa,
                f"⚠️ Tendência enfraquecendo - {sinais_enfraquecimento}"
            )
        
        # VERIFICAR SE TENDÊNCIA MORREU
        if self._detectar_morte_tendencia(zona_top1):
            self.estado_tendencia = "morta"
            return self._criar_resposta_tendencia(
                "morta", None,
                f"🟥 TENDÊNCIA MORTA - {self.tendencia_ativa} não é mais dominante"
            )
        
        return self._criar_resposta_tendencia(
            "ativa", self.tendencia_ativa,
            f"Tendência ativa - {self.tendencia_ativa} ({self.contador_acertos_tendencia} acertos, {self.contador_erros_tendencia} erros)"
        )
    
    def _analisar_tendencia_enfraquecendo(self, zona_top1, zona_top2, acerto_ultima, zona_acertada):
        """Etapa 5 do fluxograma - Tendência Enfraquecendo"""
        
        # Atualizar contadores
        if acerto_ultima and zona_acertada == self.tendencia_ativa:
            self.contador_acertos_tendencia += 1
            self.contador_erros_tendencia = 0
            
            # Se recuperou, voltar para ativa
            if self.contador_acertos_tendencia >= 2:
                self.estado_tendencia = "ativa"
                return self._criar_resposta_tendencia(
                    "ativa", self.tendencia_ativa,
                    f"✅ Tendência recuperada - {self.tendencia_ativa} voltou forte"
                )
        elif not acerto_ultima:
            self.contador_erros_tendencia += 1
        
        # VERIFICAR MORTE DEFINITIVA
        if self._detectar_morte_tendencia(zona_top1):
            self.estado_tendencia = "morta"
            return self._criar_resposta_tendencia(
                "morta", None,
                f"🟥 TENDÊNCIA MORTA a partir do estado enfraquecido"
            )
        
        return self._criar_resposta_tendencia(
            "enfraquecendo", self.tendencia_ativa,
            f"⚠️ Tendência enfraquecendo - {self.tendencia_ativa} (cuidado)"
        )
    
    def _analisar_reinicio_tendencia(self, zona_top1, zonas_rankeadas):
        """Etapa 7 do fluxograma - Reinício e Nova Tendência"""
        
        # Aguardar rodadas suficientes após morte da tendência
        rodadas_desde_morte = len([z for z in self.historico_zonas_dominantes if z != self.tendencia_ativa])
        
        if rodadas_desde_morte >= 8:
            # Verificar se nova tendência está se formando
            freq_zona_atual = list(self.historico_zonas_dominantes).count(zona_top1)
            dispersao = self._calcular_dispersao_zonas(zonas_rankeadas)
            
            if freq_zona_atual >= 3 and dispersao <= 0.6:
                self.estado_tendencia = "formando"
                self.tendencia_ativa = zona_top1
                self.contador_confirmacoes = 1
                
                return self._criar_resposta_tendencia(
                    "formando", zona_top1,
                    f"🔄 NOVA TENDÊNCIA se formando - {zona_top1}"
                )
        
        return self._criar_resposta_tendencia(
            "morta", None,
            f"🔄 Aguardando nova tendência ({rodadas_desde_morte}/8 rodadas)"
        )
    
    def _detectar_enfraquecimento(self, zona_top1, zona_top2, acerto_ultima):
        """Detecta sinais de enfraquecimento da tendência"""
        sinais = []
        
        if not self.tendencia_ativa:
            return None
        
        # 1. Zona dominante saindo do Top 1
        if zona_top1 != self.tendencia_ativa:
            sinais.append("zona saiu do Top 1")
        
        # 2. Nova zona aparecendo forte no Top 2
        if (zona_top2 and zona_top2 != self.tendencia_ativa and 
            zona_top2 not in [self.tendencia_ativa, zona_top1]):
            sinais.append("nova zona no Top 2")
        
        # 3. Padrão de alternância (acerta/erra)
        if self.contador_erros_tendencia > 0 and self.contador_acertos_tendencia > 0:
            total_operacoes = self.contador_acertos_tendencia + self.contador_erros_tendencia
            if total_operacoes >= 3 and self.contador_erros_tendencia >= total_operacoes * 0.4:
                sinais.append("padrão acerta/erra")
        
        # 4. Muitas operações já realizadas
        if self.rodadas_operando >= self.max_operacoes_por_tendencia:
            sinais.append("máximo de operações atingido")
        
        return " | ".join(sinais) if sinais else None
    
    def _detectar_morte_tendencia(self, zona_top1):
        """Detecta se a tendência morreu completamente"""
        
        if not self.tendencia_ativa:
            return True
        
        # 1. Dois erros seguidos
        if self.contador_erros_tendencia >= 2:
            return True
        
        # 2. Zona dominante sumiu dos primeiros lugares
        if (zona_top1 != self.tendencia_ativa and 
            self.tendencia_ativa not in list(self.historico_zonas_dominantes)[-3:]):
            return True
        
        # 3. Muitas zonas diferentes aparecendo
        zonas_recentes = list(self.historico_zonas_dominantes)[-5:]
        zonas_unicas = len(set(zonas_recentes))
        if len(zonas_recentes) >= 3 and zonas_unicas >= 3:
            return True
        
        # 4. Taxa de acertos baixa
        total_tentativas = self.contador_acertos_tendencia + self.contador_erros_tendencia
        if total_tentativas >= 3:
            taxa_acertos = self.contador_acertos_tendencia / total_tentativas
            if taxa_acertos < 0.5:
                return True
        
        return False
    
    def _calcular_dispersao_zonas(self, zonas_rankeadas):
        """Calcula o nível de dispersão entre as zonas"""
        if not zonas_rankeadas:
            return 1.0
        
        scores = [score for _, score in zonas_rankeadas[:4]]
        if not scores:
            return 1.0
        
        max_score = max(scores)
        if max_score == 0:
            return 1.0
        
        try:
            scores_normalizados = [score / max_score for score in scores]
            dispersao = np.std(scores_normalizados) if len(scores_normalizados) > 1 else 0
            return float(dispersao)
        except:
            return 1.0
    
    def _criar_resposta_tendencia(self, estado, zona_dominante, mensagem, acao="aguardar"):
        """Cria resposta padronizada da análise de tendência"""
        return {
            'estado': estado,
            'zona_dominante': zona_dominante,
            'confianca': self._calcular_confianca_tendencia(estado),
            'acao': acao,
            'mensagem': mensagem,
            'contadores': {
                'confirmacoes': self.contador_confirmacoes,
                'acertos': self.contador_acertos_tendencia,
                'erros': self.contador_erros_tendencia,
                'operacoes': self.rodadas_operando
            }
        }
    
    def _calcular_confianca_tendencia(self, estado):
        """Calcula nível de confiança baseado no estado da tendência"""
        confiancas = {
            'aguardando': 0.1,
            'formando': 0.4,
            'ativa': 0.8,
            'enfraquecendo': 0.3,
            'morta': 0.0
        }
        return confiancas.get(estado, 0.0)
    
    def get_resumo_tendencia(self):
        """Retorna resumo atual do estado da tendência"""
        return {
            'estado': self.estado_tendencia,
            'zona_ativa': self.tendencia_ativa,
            'contadores': {
                'confirmacoes': self.contador_confirmacoes,
                'acertos': self.contador_acertos_tendencia,
                'erros': self.contador_erros_tendencia,
                'operacoes': self.rodadas_operando
            },
            'historico_zonas': list(self.historico_zonas_dominantes)
        }
    
    def enviar_notificacoes_tendencia(self, analise_tendencia):
        estado = analise_tendencia['estado']
        mensagem = analise_tendencia['mensagem']
        zona = analise_tendencia['zona_dominante']
        
        # Verificar configurações de alertas
        if 'alertas_config' not in st.session_state:
            return
        
        alertas_config = st.session_state.alertas_config
        
        # Verificar se alertas de tendência estão ativados
        if not alertas_config.get('alertas_tendencia', True):
            return
        
        if estado == "ativa" and analise_tendencia['acao'] == "operar":
            # Verificar se alertas do Telegram estão configurados e ativados
            if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    enviar_telegram(f"🎯 TENDÊNCIA CONFIRMADA\n"
                                  f"📍 Zona: {zona}\n"
                                  f"📈 Estado: {estado}\n"
                                  f"💡 Ação: OPERAR\n"
                                  f"📊 {mensagem}")
            
        elif estado == "enfraquecendo":
            if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    enviar_telegram(f"⚠️ TENDÊNCIA ENFRAQUECENDO\n"
                                  f"📍 Zona: {zona}\n"
                                  f"📈 Estado: {estado}\n"
                                  f"💡 Ação: AGUARDAR\n"
                                  f"📊 {mensagem}")
            
        elif estado == "morta":
            if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                    enviar_telegram(f"🟥 TENDÊNCIA MORTA\n"
                                  f"📈 Estado: {estado}\n"
                                  f"💡 Ação: PARAR\n"
                                  f"📊 {mensagem}")

# =============================
# CONFIGURAÇÕES
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# SISTEMA DE SELEÇÃO INTELIGENTE DE NÚMEROS
# =============================
class SistemaSelecaoInteligente:
    def __init__(self):
        self.roleta = RoletaInteligente()
        
    def selecionar_melhores_10_numeros(self, numeros_candidatos, historico, estrategia_tipo="Zonas"):
        if len(numeros_candidatos) <= 10:
            return numeros_candidatos
            
        scores = {}
        for numero in numeros_candidatos:
            scores[numero] = self.calcular_score_numero(numero, historico, estrategia_tipo)
        
        numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhores_10 = [num for num, score in numeros_ordenados[:10]]
        
        logging.info(f"🎯 Seleção Inteligente: {len(numeros_candidatos)} → 10 números")
        return melhores_10
    
    def calcular_score_numero(self, numero, historico, estrategia_tipo):
        try:
            score_total = 0
            
            score_frequencia = self.calcular_score_frequencia(numero, historico)
            score_total += score_frequencia * 0.45
            
            score_posicao = self.calcular_score_posicao_roda(numero, historico)
            score_total += score_posicao * 0.20
            
            score_vizinhos = self.calcular_score_vizinhos(numero, historico)
            score_total += score_vizinhos * 0.25
            
            score_tendencia = self.calcular_score_tendencia(numero, historico)
            score_total += score_tendencia * 0.10
            
            return score_total
            
        except Exception as e:
            logging.error(f"Erro ao calcular score: {e}")
            return 0.5
    
    def calcular_score_frequencia(self, numero, historico):
        if len(historico) < 3:
            return 0.7
        
        try:
            historico_lista = list(historico)
            
            janela_curta = historico_lista[-8:] if len(historico_lista) >= 8 else historico_lista
            freq_curta = sum(1 for n in janela_curta if n == numero) / len(janela_curta)
            
            janela_media = historico_lista[-20:] if len(historico_lista) >= 20 else historico_lista
            freq_media = sum(1 for n in janela_media if n == numero) / len(janela_media)
            
            janela_longa = historico_lista[-40:] if len(historico_lista) >= 40 else historico_lista
            freq_longa = sum(1 for n in janela_longa if n == numero) / len(janela_longa)
            
            score = (freq_curta * 0.7 + freq_media * 0.2 + freq_longa * 0.1)
            return min(score * 4, 1.0)
            
        except Exception as e:
            logging.error(f"Erro no cálculo de frequência: {e}")
            return 0.5
    
    def calcular_score_posicao_roda(self, numero, historico):
        if len(historico) < 3:
            return 0.5
        
        try:
            ultimo_numero = historico[-1] if historico else 0
            penultimo_numero = historico[-2] if len(historico) >= 2 else ultimo_numero
            
            posicao_alvo = self.roleta.get_posicao_race(numero)
            posicao_ultimo = self.roleta.get_posicao_race(ultimo_numero)
            posicao_penultimo = self.roleta.get_posicao_race(penultimo_numero)
            
            if posicao_alvo == -1 or posicao_ultimo == -1 or posicao_penultimo == -1:
                return 0.5
            
            dist_ultimo = self.calcular_distancia_roda(posicao_alvo, posicao_ultimo)
            score_dist_ultimo = max(0, 1 - (dist_ultimo / 18))
            
            dist_penultimo = self.calcular_distancia_roda(posicao_alvo, posicao_penultimo)
            score_dist_penultimo = max(0, 1 - (dist_penultimo / 18))
            
            score_final = (score_dist_ultimo * 0.7 + score_dist_penultimo * 0.3)
            return score_final
            
        except Exception as e:
            logging.error(f"Erro no cálculo de posição: {e}")
            return 0.5
    
    def calcular_distancia_roda(self, pos1, pos2):
        total_posicoes = 37
        distancia_direta = abs(pos1 - pos2)
        distancia_inversa = total_posicoes - distancia_direta
        return min(distancia_direta, distancia_inversa)
    
    def calcular_score_vizinhos(self, numero, historico):
        if len(historico) < 5:
            return 0.5
        
        try:
            vizinhos = self.roleta.get_vizinhos_fisicos(numero, raio=3)
            ultimos_15 = list(historico)[-15:] if len(historico) >= 15 else list(historico)
            count_vizinhos_recentes = sum(1 for n in ultimos_15 if n in vizinhos)
            
            if len(ultimos_15) == 0:
                return 0.5
                
            score = min(count_vizinhos_recentes / len(ultimos_15) * 2, 1.0)
            return score
            
        except Exception as e:
            logging.error(f"Erro no cálculo de vizinhos: {e}")
            return 0.5
    
    def calcular_score_tendencia(self, numero, historico):
        if len(historico) < 10:
            return 0.5
        
        try:
            historico_lista = list(historico)
            
            segmento_recente = historico_lista[-5:]
            segmento_anterior = historico_lista[-10:-5] if len(historico_lista) >= 10 else historico_lista[:5]
            
            if len(segmento_recente) == 0:
                return 0.5
                
            freq_recente = sum(1 for n in segmento_recente if n == numero) / len(segmento_recente)
            
            if len(segmento_anterior) == 0:
                freq_anterior = 0
            else:
                freq_anterior = sum(1 for n in segmento_anterior if n == numero) / len(segmento_anterior)
            
            if freq_anterior == 0:
                tendencia = 1.0 if freq_recente > 0 else 0.5
            else:
                tendencia = min(freq_recente / freq_anterior, 2.0)
                
            return tendencia * 0.5
            
        except Exception as e:
            logging.error(f"Erro no cálculo de tendência: {e}")
            return 0.5

    def get_analise_selecao(self, numeros_originais, numeros_selecionados, historico):
        analise = f"🎯 ANÁLISE DA SELEÇÃO INTELIGENTE\n"
        analise += f"📊 Redução: {len(numeros_originais)} → {len(numeros_selecionados)} números\n"
        analise += f"🎲 Números selecionados: {sorted(numeros_selecionados)}\n"
        
        if historico:
            ultimos_20 = list(historico)[-20:] if len(historico) >= 20 else list(historico)
            if ultimos_20:
                acertos_potenciais = sum(1 for n in ultimos_20 if n in numeros_selecionados)
                analise += f"📈 Eficiência teórica: {acertos_potenciais}/20 ({acertos_potenciais/len(ultimos_20)*100:.1f}%)\n"
        
        return analise

# =============================
# CLASSE PRINCIPAL DA ROLETA ATUALIZADA
# =============================
class RoletaInteligente:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_zona(self, numero_central, quantidade=6):
        if numero_central not in self.race:
            return []
        
        posicao = self.race.index(numero_central)
        vizinhos = []
        
        for offset in range(-quantidade, quantidade + 1):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        return list(set(vizinhos))  # Remover duplicatas

    def get_posicao_race(self, numero):
        try:
            if numero in self.race:
                return self.race.index(numero)
            return -1
        except:
            return -1

    def get_vizinhos_fisicos(self, numero, raio=3):
        if numero not in self.race:
            return []
        
        posicao = self.race.index(numero)
        vizinhos = []
        
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinho = self.race[(posicao + offset) % len(self.race)]
                vizinhos.append(vizinho)
        
        return vizinhos

# =============================
# MÓDULO DE MACHINE LEARNING ATUALIZADO
# =============================
class MLRoletaOtimizada:
    def __init__(
        self,
        roleta_obj,
        min_training_samples: int = 500,
        max_history: int = 1000,
        retrain_every_n: int = 15,
        seed: int = 42
    ):
        self.roleta = roleta_obj
        self.min_training_samples = min_training_samples
        self.max_history = max_history
        self.retrain_every_n = retrain_every_n
        self.seed = seed

        self.models = []
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        self.contador_treinamento = 0
        self.meta = {}

        self.window_for_features = [3, 8, 15, 30, 60, 120]
        self.k_vizinhos = 2
        self.numeros = list(range(37))
        self.ensemble_size = 1

    def get_neighbors(self, numero, k=None):
        if k is None:
            k = self.k_vizinhos
        try:
            race = list(self.roleta.race)
            n = len(race)
            idx = race.index(numero)
            neighbors = []
            for offset in range(-k, k+1):
                neighbors.append(race[(idx + offset) % n])
            return neighbors
        except Exception:
            return [numero]

    def extrair_features_melhoradas(self, historico):
        """Features específicas para prever roleta"""
        try:
            historico = list(historico)
            N = len(historico)
            
            if N < 10:
                return None, None

            features = []
            names = []

            # 1. HISTÓRICO RECENTE
            K_seq = 5
            ultimos = historico[-K_seq:] if N >= K_seq else historico
            for i in range(K_seq):
                val = ultimos[i] if i < len(ultimos) else -1
                features.append(val)
                names.append(f"ultimo_{i+1}")

            # 2. ESTATÍSTICAS DE FREQUÊNCIA POR ZONA
            zonas = {
                'vermelha': {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36},
                'preta': {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35},
                'baixa': set(range(1, 19)),
                'alta': set(range(19, 37)),
                'primeira_duzia': set(range(1, 13)),
                'segunda_duzia': set(range(13, 25)),
                'terceira_duzia': set(range(25, 37)),
                'coluna_1': {1,4,7,10,13,16,19,22,25,28,31,34},
                'coluna_2': {2,5,8,11,14,17,20,23,26,29,32,35},
                'coluna_3': {3,6,9,12,15,18,21,24,27,30,33,36}
            }
            
            janela_recente = historico[-20:] if N >= 20 else historico
            for nome_zona, numeros_zona in zonas.items():
                if len(janela_recente) > 0:
                    count = sum(1 for x in janela_recente if x in numeros_zona)
                    features.append(count / len(janela_recente))
                else:
                    features.append(0)
                names.append(f"freq_{nome_zona}")

            # 3. PADRÕES DE SEQUÊNCIA
            if N >= 3:
                cores = []
                for num in historico[-3:]:
                    if num == 0:
                        cores.append(2)
                    elif num in zonas['vermelha']:
                        cores.append(0)
                    else:
                        cores.append(1)
                
                for i in range(len(cores)-1):
                    features.append(1 if cores[i] == cores[i+1] else 0)
                    names.append(f"mesma_cor_{i}")
            
            # 4. DISTÂNCIA NA RODA DA ROLETA
            if N >= 2:
                ultimo = historico[-1]
                penultimo = historico[-2]
                
                pos_ultimo = self.roleta.get_posicao_race(ultimo)
                pos_penultimo = self.roleta.get_posicao_race(penultimo)
                
                if pos_ultimo != -1 and pos_penultimo != -1:
                    distancia = min(abs(pos_ultimo - pos_penultimo), 
                                  37 - abs(pos_ultimo - pos_penultimo))
                    features.append(distancia)
                else:
                    features.append(0)
                names.append("distancia_roda")
            
            # 5. FREQUÊNCIA DE REPETIÇÃO
            if N >= 10:
                ultimos_10 = historico[-10:]
                unicos = len(set(ultimos_10))
                features.append(unicos / 10)
                names.append("diversidade_recente")
            
            # 6. TEMPERATURA DOS NÚMEROS
            if N >= 20:
                ultimos_20 = historico[-20:]
                freq_numeros = Counter(ultimos_20)
                
                if freq_numeros:
                    num_quente, freq = freq_numeros.most_common(1)[0]
                    features.append(freq / 20)
                else:
                    features.append(0)
                names.append("freq_num_quente")
            
            # 7. PADRÕES DE PARIDADE
            if N >= 5:
                ultimos_5 = historico[-5:]
                pares = sum(1 for x in ultimos_5 if x > 0 and x % 2 == 0)
                features.append(pares / len(ultimos_5) if len(ultimos_5) > 0 else 0)
                names.append("freq_pares_recente")
            
            # 8. FREQUÊNCIA DE ZERO
            if N >= 10:
                zeros = sum(1 for x in historico[-10:] if x == 0)
                features.append(zeros / 10)
                names.append("freq_zero_recente")
            
            return np.array(features), names

        except Exception as e:
            logging.error(f"[extrair_features_melhoradas] Erro: {e}")
            return None, None

    def preparar_dados_treinamento(self, historico_completo):
        historico_completo = list(historico_completo)
        if len(historico_completo) > self.max_history:
            historico_completo = historico_completo[-self.max_history:]

        X = []
        y = []
        
        start_index = max(50, len(historico_completo) // 10)
        
        for i in range(start_index, len(historico_completo)):
            janela = historico_completo[:i]
            feats, _ = self.extrair_features_melhoradas(janela)
            if feats is None:
                continue
            X.append(feats)
            y.append(historico_completo[i])
        
        if len(X) == 0:
            return np.array([]), np.array([])
        
        class_counts = Counter(y)
        if len(class_counts) < 5:
            logging.warning(f"Pouca variedade de classes: apenas {len(class_counts)} números únicos")
            return np.array([]), np.array([])
        
        return np.array(X), np.array(y)

    def _build_and_train_model_corrigido(self, X_train, y_train, X_val=None, y_val=None, seed=0):
        try:
            # Tentar CatBoost primeiro
            try:
                from catboost import CatBoostClassifier
                
                model = CatBoostClassifier(
                    iterations=500,
                    learning_rate=0.05,
                    depth=6,
                    l2_leaf_reg=10,
                    random_strength=0.5,
                    loss_function='MultiClass',
                    eval_metric='MultiClass',
                    random_seed=seed,
                    use_best_model=True,
                    early_stopping_rounds=50,
                    verbose=0,
                    task_type='CPU',
                    auto_class_weights='Balanced',
                    bootstrap_type='Bernoulli',
                    subsample=0.8
                )
                
                if X_val is not None and y_val is not None:
                    model.fit(
                        X_train, y_train, 
                        eval_set=(X_val, y_val), 
                        verbose=100
                    )
                else:
                    model.fit(X_train, y_train, verbose=100)
                
                return model, "CatBoost-Corrigido"
                
            except ImportError:
                logging.warning("CatBoost não disponível. Usando RandomForest.")
                from sklearn.ensemble import RandomForestClassifier
                
                model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    min_samples_split=10,
                    min_samples_leaf=5,
                    max_features='sqrt',
                    random_state=seed,
                    n_jobs=-1,
                    class_weight='balanced'
                )
                model.fit(X_train, y_train)
                return model, "RandomForest-Simples"
                
        except Exception as e:
            logging.warning(f"Falha nos modelos principais: {e}. Tentando modelo simples.")
            from sklearn.ensemble import RandomForestClassifier
            
            model = RandomForestClassifier(
                n_estimators=50,
                max_depth=5,
                random_state=seed
            )
            model.fit(X_train, y_train)
            return model, "RandomForest-Simples"

    def treinar_modelo_corrigido(self, historico_completo, force_retrain: bool = False):
        """Treinamento corrigido e simplificado"""
        try:
            if len(historico_completo) < self.min_training_samples and not force_retrain:
                return False, f"Necessário mínimo de {self.min_training_samples} amostras. Atual: {len(historico_completo)}"

            X, y = self.preparar_dados_treinamento(historico_completo)
            if len(X) < 100:
                return False, f"Dados insuficientes para treino: {len(X)} amostras"

            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=self.seed, shuffle=True
            )
            
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            model, model_name = self._build_and_train_model_corrigido(
                X_train_scaled, y_train, X_val_scaled, y_val, self.seed
            )
            
            y_pred = model.predict(X_val_scaled)
            acc = accuracy_score(y_val, y_pred)
            
            self.models = [model]
            self.is_trained = True
            self.contador_treinamento += 1
            self.meta['last_accuracy'] = acc
            self.meta['trained_on'] = len(historico_completo)
            self.meta['model_name'] = model_name
            
            # Salvar em disco
            try:
                joblib.dump({'models': self.models}, ML_MODEL_PATH)
                joblib.dump(self.scaler, SCALER_PATH)
                joblib.dump(self.meta, META_PATH)
                logging.info(f"Modelo salvo em disco: {ML_MODEL_PATH}")
            except Exception as e:
                logging.warning(f"Falha ao salvar modelo: {e}")

            return True, f"Modelo {model_name} treinado: {len(X)} amostras. Acurácia validação: {acc:.2%}"

        except Exception as e:
            logging.error(f"[treinar_modelo_corrigido] Erro: {e}", exc_info=True)
            return False, f"Erro: {str(e)}"

    def carregar_modelo(self):
        try:
            if os.path.exists(ML_MODEL_PATH) and os.path.exists(SCALER_PATH):
                data = joblib.load(ML_MODEL_PATH)
                self.models = data.get('models', [])
                self.scaler = joblib.load(SCALER_PATH)
                if os.path.exists(META_PATH):
                    self.meta = joblib.load(META_PATH)
                self.is_trained = len(self.models) > 0
                return True
            return False
        except Exception as e:
            logging.error(f"[carregar_modelo] Erro: {e}")
            return False

    def _ensemble_predict_proba(self, X_scaled):
        if not self.models:
            return np.ones((len(X_scaled), len(self.numeros))) / len(self.numeros)

        probs = []
        for m in self.models:
            if hasattr(m, 'predict_proba'):
                probs.append(m.predict_proba(X_scaled))
            else:
                preds = m.predict(X_scaled)
                prob = np.zeros((len(preds), len(self.numeros)))
                for i, p in enumerate(preds):
                    prob[i, p] = 1.0
                probs.append(prob)
        return np.mean(probs, axis=0)

    def prever_zona_proxima(self, historico):
        """Prever ZONA em vez de número específico"""
        if not self.is_trained:
            return None, "Modelo não treinado"

        feats, _ = self.extrair_features_melhoradas(historico)
        if feats is None:
            return None, "Features insuficientes"

        Xs = np.array([feats])
        Xs_scaled = self.scaler.transform(Xs)
        
        try:
            probs = self._ensemble_predict_proba(Xs_scaled)[0]
            
            zonas_ml = {
                'Vermelha': 7,
                'Azul': 10,  
                'Amarela': 2
            }
            
            numeros_por_zona = {}
            roleta = RoletaInteligente()
            
            for zona_nome, central in zonas_ml.items():
                numeros_zona = roleta.get_vizinhos_zona(central, 6)
                numeros_por_zona[zona_nome] = numeros_zona
            
            zonas_prob = {}
            for zona_nome, numeros_zona in numeros_por_zona.items():
                prob_total = 0.0
                for num in numeros_zona:
                    if num < len(probs):
                        prob_total += probs[num]
                zonas_prob[zona_nome] = prob_total
            
            total = sum(zonas_prob.values())
            if total > 0:
                for zona in zonas_prob:
                    zonas_prob[zona] /= total
            
            zonas_ordenadas = sorted(zonas_prob.items(), key=lambda x: x[1], reverse=True)
            
            return zonas_ordenadas, "Previsão de zona realizada"
            
        except Exception as e:
            logging.error(f"Erro na previsão de zona: {e}")
            return None, f"Erro na previsão: {str(e)}"

    def prever_proximo_numero(self, historico, top_k: int = 25):
        """Mantido para compatibilidade"""
        if not self.is_trained:
            return None, "Modelo não treinado"

        feats, _ = self.extrair_features_melhoradas(historico)
        if feats is None:
            return None, "Features insuficientes"

        Xs = np.array([feats])
        Xs_scaled = self.scaler.transform(Xs)
        try:
            probs = self._ensemble_predict_proba(Xs_scaled)[0]
            top_idx = np.argsort(probs)[-top_k:][::-1]
            top = [(int(idx), float(probs[idx])) for idx in top_idx]
            return top, "Previsão ML realizada"
        except Exception as e:
            return None, f"Erro na previsão: {str(e)}"

    def registrar_resultado(self, historico, previsao_top, resultado_real):
        try:
            if not previsao_top:
                return False
                
            hit = resultado_real in [p for p,_ in previsao_top] if isinstance(previsao_top[0], tuple) else resultado_real in previsao_top
            log_entry = {
                'prev_top': previsao_top,
                'resultado': resultado_real,
                'hit': bool(hit)
            }
            self.meta.setdefault('history_feedback', []).append(log_entry)
            recent = self.meta['history_feedback'][-10:]
            hits = sum(1 for r in recent if r['hit'])
            if len(recent) >= 5 and hits / len(recent) < 0.25:
                logging.info("[feedback] Baixa performance detectada — forçando retreinamento")
                self.treinar_modelo_corrigido(historico, force_retrain=True)
            return True
        except Exception as e:
            logging.error(f"[registrar_resultado] Erro: {e}")
            return False

    def verificar_treinamento_automatico(self, historico_completo):
        try:
            n = len(historico_completo)
            if n >= self.min_training_samples:
                if n % self.retrain_every_n == 0:
                    return self.treinar_modelo_corrigido(historico_completo)
            return False, "Aguardando próximo ciclo de treinamento"
        except Exception as e:
            return False, f"Erro ao verificar retrain: {e}"

    def resumo_meta(self):
        return {
            "is_trained": self.is_trained,
            "contador_treinamento": self.contador_treinamento,
            "meta": self.meta
        }

# =============================
# ESTRATÉGIA DAS ZONAS ATUALIZADA
# =============================
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Zonas Ultra Otimizada v6"
        
        self.zonas = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.quantidade_zonas = {
            'Vermelha': 6,
            'Azul': 6,
            'Amarela': 6
        }
        
        self.stats_zonas = {zona: {
            'acertos': 0, 
            'tentativas': 0, 
            'sequencia_atual': 0,
            'sequencia_maxima': 0,
            'performance_media': 0
        } for zona in self.zonas.keys()}
        
        self.numeros_zonas = {}
        for nome, central in self.zonas.items():
            qtd = self.quantidade_zonas.get(nome, 6)
            self.numeros_zonas[nome] = self.roleta.get_vizinhos_zona(central, qtd)

        self.janelas_analise = {
            'curto_prazo': 12,
            'medio_prazo': 24,  
            'longo_prazo': 48,
            'performance': 100
        }
        
        self.threshold_base = 22
        
        self.sistema_selecao = SistemaSelecaoInteligente()

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        resultado = self.atualizar_stats(numero)
        return resultado

    def atualizar_stats(self, ultimo_numero):
        acertou_zona = None
        for zona, numeros in self.numeros_zonas.items():
            if ultimo_numero in numeros:
                self.stats_zonas[zona]['acertos'] += 1
                self.stats_zonas[zona]['sequencia_atual'] += 1
                if self.stats_zonas[zona]['sequencia_atual'] > self.stats_zonas[zona]['sequencia_maxima']:
                    self.stats_zonas[zona]['sequencia_maxima'] = self.stats_zonas[zona]['sequencia_atual']
                acertou_zona = zona
            else:
                self.stats_zonas[zona]['sequencia_atual'] = 0
            self.stats_zonas[zona]['tentativas'] += 1
            
            if self.stats_zonas[zona]['tentativas'] > 0:
                self.stats_zonas[zona]['performance_media'] = (
                    self.stats_zonas[zona]['acertos'] / self.stats_zonas[zona]['tentativas'] * 100
                )
        
        return acertou_zona

    def get_threshold_dinamico(self, zona):
        if zona not in self.stats_zonas:
            return 20
        
        perf = self.stats_zonas[zona]['performance_media']
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        
        if perf > 35 and sequencia >= 1:  
            return 18
        elif perf > 30:
            return 20
        elif perf > 25:
            return 22
        elif perf < 15:
            return 28
        else:
            return 24

    def get_zona_mais_quente(self):
        if len(self.historico) < 10:
            return None
            
        zonas_score = {}
        total_numeros = len(self.historico)
        
        for zona in self.zonas.keys():
            score = 0
            
            freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
            if total_numeros > 0:
                percentual_geral = freq_geral / total_numeros
                score += percentual_geral * 25
            
            ultimos_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:] if total_numeros >= self.janelas_analise['curto_prazo'] else list(self.historico)
            if ultimos_curto:
                freq_curto = sum(1 for n in ultimos_curto if n in self.numeros_zonas[zona])
                percentual_curto = freq_curto / len(ultimos_curto)
                score += percentual_curto * 35
            
            if self.stats_zonas[zona]['tentativas'] > 10:
                taxa_acerto = self.stats_zonas[zona]['performance_media']
                if taxa_acerto > 40: 
                    score += 30
                elif taxa_acerto > 35:
                    score += 25
                elif taxa_acerto > 30:
                    score += 20
                elif taxa_acerto > 25:
                    score += 15
                else:
                    score += 10
            else:
                score += 10
            
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            if sequencia >= 2:
                score += min(sequencia * 3, 12)
            
            zonas_score[zona] = score
        
        if not zonas_score:
            return None
            
        zona_vencedora = max(zonas_score, key=zonas_score.get)
        
        if zona_vencedora:
            threshold = self.get_threshold_dinamico(zona_vencedora)
            
            if self.stats_zonas[zona_vencedora]['sequencia_atual'] >= 2:
                threshold -= 2
            
            return zona_vencedora if zonas_score[zona_vencedora] >= threshold else None
        
        return None

    def get_zonas_rankeadas(self):
        if len(self.historico) < 10:
            return None
            
        zonas_score = {}
        
        for zona in self.zonas.keys():
            score = self.get_zona_score(zona)
            zonas_score[zona] = score
        
        if not zonas_score:
            return None
            
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def analisar_zonas_com_inversao(self):
        if len(self.historico) < 10:
            return None
            
        zonas_rankeadas = self.get_zonas_rankeadas()
        if not zonas_rankeadas:
            return None
        
        zona_primaria, score_primario = zonas_rankeadas[0]
        
        threshold_base = 22
        
        if score_primario < threshold_base:
            return None
        
        # Verificar se o sistema existe na sessão
        if 'sistema' not in st.session_state:
            return self.criar_previsao_unica(zona_primaria)
            
        sistema = st.session_state.sistema
        combinacao_recomendada = sistema.get_combinacao_recomendada()
        
        if combinacao_recomendada and zona_primaria in combinacao_recomendada:
            zona_secundaria = [z for z in combinacao_recomendada if z != zona_primaria][0]
            
            zonas_secundarias_disponiveis = [z for z, s in zonas_rankeadas if z == zona_secundaria]
            if zonas_secundarias_disponiveis:
                return self.criar_previsao_dupla(zona_primaria, zona_secundaria, "RECOMENDADA")
        
        if len(zonas_rankeadas) > 1:
            for i in range(1, min(3, len(zonas_rankeadas))):
                zona_secundaria, score_secundario = zonas_rankeadas[i]
                combinacao_teste = tuple(sorted([zona_primaria, zona_secundaria]))
                
                if hasattr(sistema, 'deve_evitar_combinacao') and sistema.deve_evitar_combinacao(combinacao_teste):
                    continue
                
                threshold_secundario = threshold_base - 4
                
                if score_secundario >= threshold_secundario:
                    return self.criar_previsao_dupla(zona_primaria, zona_secundaria, "RANQUEADA")
        
        return self.criar_previsao_unica(zona_primaria)

    def criar_previsao_dupla(self, zona_primaria, zona_secundaria, tipo):
        numeros_primarios = self.numeros_zonas[zona_primaria]
        numeros_secundarios = self.numeros_zonas[zona_secundaria]
        
        numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
        
        if len(numeros_combinados) > 10:
            numeros_combinados = self.sistema_selecao.selecionar_melhores_10_numeros(
                numeros_combinados, self.historico, "Zonas"
            )
        
        info_eficiencia = ""
        if 'sistema' in st.session_state:
            sistema = st.session_state.sistema
            combinacao = tuple(sorted([zona_primaria, zona_secundaria]))
            dados_combinacao = sistema.historico_combinacoes.get(combinacao, {})
            eficiencia = dados_combinacao.get('eficiencia', 0)
            total = dados_combinacao.get('total', 0)
            
            if total > 0:
                info_eficiencia = f" | Eff: {eficiencia:.1f}% ({dados_combinacao.get('acertos', 0)}/{total})"
        
        gatilho = f'Zona {zona_primaria} + {zona_secundaria} - {tipo}{info_eficiencia}'
        
        return {
            'nome': f'Zonas Duplas - {zona_primaria} + {zona_secundaria}',
            'numeros_apostar': numeros_combinados,
            'gatilho': gatilho,
            'confianca': self.calcular_confianca_ultra(zona_primaria),
            'zona': f'{zona_primaria}+{zona_secundaria}',
            'zonas_envolvidas': [zona_primaria, zona_secundaria],
            'tipo': 'dupla',
            'selecao_inteligente': True
        }

    def criar_previsao_unica(self, zona_primaria):
        numeros_apostar = self.numeros_zonas[zona_primaria]
        
        if len(numeros_apostar) > 10:
            numeros_apostar = self.sistema_selecao.selecionar_melhores_10_numeros(
                numeros_apostar, self.historico, "Zonas"
            )
        
        return {
            'nome': f'Zona {zona_primaria}',
            'numeros_apostar': numeros_apostar,
            'gatilho': f'Zona {zona_primaria} - Única',
            'confianca': self.calcular_confianca_ultra(zona_primaria),
            'zona': zona_primaria,
            'zonas_envolvidas': [zona_primaria],
            'tipo': 'unica',
            'selecao_inteligente': len(numeros_apostar) < len(self.numeros_zonas[zona_primaria])
        }

    def analisar_zonas(self):
        return self.analisar_zonas_com_inversao()

    def calcular_confianca_ultra(self, zona):
        if len(self.historico) < 8:
            return 'Média'
            
        fatores = []
        pesos = []
        
        perf_historica = self.stats_zonas[zona]['performance_media']
        if perf_historica > 45: 
            fatores.append(4)
            pesos.append(5)
        elif perf_historica > 35: 
            fatores.append(3)
            pesos.append(4)
        elif perf_historica > 25: 
            fatores.append(2)
            pesos.append(4)
        else: 
            fatores.append(1)
            pesos.append(3)
        
        historico_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:] 
        if historico_curto:
            freq_curto = sum(1 for n in historico_curto if n in self.numeros_zonas[zona])
            perc_curto = (freq_curto / len(historico_curto)) * 100
            
            if perc_curto > 60:
                fatores.append(4)
            elif perc_curto > 45: 
                fatores.append(3)
            elif perc_curto > 30: 
                fatores.append(2)
            else: 
                fatores.append(1)
            pesos.append(4)
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 3: 
            fatores.append(4)
            pesos.append(3)
        elif sequencia >= 2: 
            fatores.append(3)
            pesos.append(3)
        else: 
            fatores.append(1)
            pesos.append(2)
        
        if len(self.historico) >= 10:
            ultimos_5 = list(self.historico)[-5:]
            anteriores_5 = list(self.historico)[-10:-5]
            
            freq_ultimos = sum(1 for n in ultimos_5 if n in self.numeros_zonas[zona])
            freq_anteriores = sum(1 for n in anteriores_5 if n in self.numeros_zonas[zona]) if anteriores_5 else 0
            
            if freq_ultimos > freq_anteriores: 
                fatores.append(3)
                pesos.append(2)
            elif freq_ultimos == freq_anteriores: 
                fatores.append(2)
                pesos.append(2)
            else: 
                fatores.append(1)
                pesos.append(2)
        
        if sum(pesos) == 0:
            return 'Média'
            
        total_pontos = sum(f * p for f, p in zip(fatores, pesos))
        total_pesos = sum(pesos)
        score_confianca = total_pontos / total_pesos
        
        if score_confianca >= 2.8: 
            return 'Excelente'
        elif score_confianca >= 2.4: 
            return 'Muito Alta'
        elif score_confianca >= 2.0: 
            return 'Alta'
        elif score_confianca >= 1.6: 
            return 'Média'
        else: 
            return 'Baixa'

    def get_zona_score(self, zona):
        if len(self.historico) < 10:
            return 0
            
        score = 0
        total_numeros = len(self.historico)
        
        freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
        if total_numeros > 0:
            percentual_geral = freq_geral / total_numeros
            score += percentual_geral * 25
        
        for janela_nome, tamanho in self.janelas_analise.items():
            if janela_nome != 'performance':
                historico_janela = list(self.historico)[-tamanho:] if total_numeros >= tamanho else list(self.historico)
                if historico_janela:
                    freq_janela = sum(1 for n in historico_janela if n in self.numeros_zonas[zona])
                    percentual_janela = freq_janela / len(historico_janela)
                    peso = 35 if janela_nome == 'curto_prazo' else 15
                    score += percentual_janela * peso
        
        if self.stats_zonas[zona]['tentativas'] > 10:
            taxa_acerto = self.stats_zonas[zona]['performance_media']
            if taxa_acerto > 40: score += 30
            elif taxa_acerto > 35: score += 25
            elif taxa_acerto > 30: score += 20
            elif taxa_acerto > 25: score += 15
            else: score += 10
        else:
            score += 10
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 2:
            score += min(sequencia * 3, 12)
            
        return score

    def get_info_zonas(self):
        info = {}
        for zona, numeros in self.numeros_zonas.items():
            info[zona] = {
                'numeros': sorted(numeros),
                'quantidade': len(numeros),
                'central': self.zonas[zona],
                'descricao': f"6 antes + 6 depois do {self.zonas[zona]}"
            }
        return info

    def get_analise_detalhada(self):
        if len(self.historico) == 0:
            return "Aguardando dados..."
        
        analise = "🎯 ANÁLISE ULTRA OTIMIZADA - ZONAS v6\n"
        analise += "=" * 55 + "\n"
        analise += "🔧 CONFIGURAÇÃO: 6 antes + 6 depois (13 números/zona)\n"
        analise += f"📊 JANELAS: Curto({self.janelas_analise['curto_prazo']}) Médio({self.janelas_analise['medio_prazo']}) Longo({self.janelas_analise['longo_prazo']})\n"
        analise += "=" * 55 + "\n"
        
        analise += "📊 PERFORMANCE AVANÇADADA:\n"
        for zona in self.zonas.keys():
            tentativas = self.stats_zonas[zona]['tentativas']
            acertos = self.stats_zonas[zona]['acertos']
            taxa = self.stats_zonas[zona]['performance_media']
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            seq_maxima = self.stats_zonas[zona]['sequencia_maxima']
            threshold = self.get_threshold_dinamico(zona)
            
            analise += f"📍 {zona}: {acertos}/{tentativas} → {taxa:.1f}% | Seq: {sequencia} | Máx: {seq_maxima} | Thr: {threshold}\n"
        
        analise += "\n📈 FREQUÊNCIA MULTI-JANELAS:\n"
        for zona in self.zonas.keys():
            freq_total = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
            if len(self.historico) > 0:
                perc_total = (freq_total / len(self.historico)) * 100
            else:
                perc_total = 0
            
            freq_curto = sum(1 for n in list(self.historico)[-self.janelas_analise['curto_prazo']:] if n in self.numeros_zonas[zona])
            janela_curto_len = min(self.janelas_analise['curto_prazo'], len(self.historico))
            if janela_curto_len > 0:
                perc_curto = (freq_curto / janela_curto_len) * 100
            else:
                perc_curto = 0
            
            score = self.get_zona_score(zona)
            qtd_numeros = len(self.numeros_zonas[zona])
            analise += f"📍 {zona}: Total:{freq_total}/{len(self.historico)}({perc_total:.1f}%) | Curto:{freq_curto}/{janela_curto_len}({perc_curto:.1f}%) | Score: {score:.1f}\n"
        
        analise += "\n📊 TENDÊNCIAS AVANÇADAS:\n"
        if len(self.historico) >= 10:
            for zona in self.zonas.keys():
                ultimos_5 = list(self.historico)[-5:]
                anteriores_5 = list(self.historico)[-10:-5]
                
                freq_ultimos = sum(1 for n in ultimos_5 if n in self.numeros_zonas[zona])
                freq_anteriores = sum(1 for n in anteriores_5 if n in self.numeros_zonas[zona]) if anteriores_5 else 0
                
                tendencia = "↗️" if freq_ultimos > freq_anteriores else "↘️" if freq_ultimos < freq_anteriores else "➡️"
                variacao = freq_ultimos - freq_anteriores
                analise += f"📍 {zona}: {freq_ultimos}/5 vs {freq_anteriores}/5 {tendencia} (Δ: {variacao:+d})\n"
        
        zona_recomendada = self.get_zona_mais_quente()
        if zona_recomendada:
            analise += f"\n💡 RECOMENDAÇÃO ULTRA: Zona {zona_recomendada}\n"
            analise += f"🎯 Números: {sorted(self.numeros_zonas[zona_recomendada])}\n"
            analise += f"📈 Confiança: {self.calcular_confianca_ultra(zona_recomendada)}\n"
            analise += f"🔥 Score: {self.get_zona_score(zona_recomendada):.1f}\n"
            analise += f"🎯 Threshold: {self.get_threshold_dinamico(zona_recomendada)}\n"
            analise += f"🔢 Quantidade: {len(self.numeros_zonas[zona_recomendada])} números\n"
            analise += f"📊 Performance: {self.stats_zonas[zona_recomendada]['performance_media']:.1f}%\n"
            
            perf = self.stats_zonas[zona_recomendada]['performance_media']
            if perf > 35:
                analise += f"💎 ESTRATÉGIA: Zona de ALTA performance - Aposta forte recomendada!\n"
            elif perf > 25:
                analise += f"🎯 ESTRATÉGIA: Zona de performance sólida - Aposta moderada\n"
            else:
                analise += f"⚡ ESTRATÉGIA: Zona em desenvolvimento - Aposta conservadora\n"
        else:
            analise += "\n⚠️  AGUARDAR: Nenhuma zona com confiança suficiente\n"
            analise += f"📋 Histórico atual: {len(self.historico)} números\n"
            analise += f"🎯 Threshold base: {self.threshold_base}+ | Performance >25%\n"
        
        return analise

    def get_analise_atual(self):
        return self.get_analise_detalhada()

    def zerar_estatisticas(self):
        for zona in self.stats_zonas.keys():
            self.stats_zonas[zona] = {
                'acertos': 0, 
                'tentativas': 0, 
                'sequencia_atual': 0,
                'sequencia_maxima': 0,
                'performance_media': 0
            }
        logging.info("📊 Estatísticas das Zonas zeradas")

# =============================
# ESTRATÉGIA MIDAS
# =============================
class EstrategiaMidas:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=15)
        self.terminais = {
            '0': [0, 10, 20, 30], '1': [1, 11, 21, 31], '2': [2, 12, 22, 32],
            '3': [3, 13, 23, 33], '4': [4, 14, 24, 34], '5': [5, 15, 25, 35],
            '6': [6, 16, 26, 36], '7': [7, 17, 27], '8': [8, 18, 28], '9': [9, 19, 29]
        }

    def adicionar_numero(self, numero):
        self.historico.append(numero)

    def analisar_midas(self):
        if len(self.historico) < 5:
            return None
            
        ultimo_numero = self.historico[-1]
        historico_recente = self.historico[-5:]

        if ultimo_numero in [0, 10, 20, 30]:
            count_zero = sum(1 for n in historico_recente if n in [0, 10, 20, 30])
            if count_zero >= 1:
                return {
                    'nome': 'Padrão do Zero',
                    'numeros_apostar': [0, 10, 20, 30],
                    'gatilho': f'Terminal 0 ativado ({count_zero}x)',
                    'confianca': 'Média'
                }

        if ultimo_numero in [7, 17, 27]:
            count_sete = sum(1 for n in historico_recente if n in [7, 17, 27])
            if count_sete >= 1:
                return {
                    'nome': 'Padrão do Sete',
                    'numeros_apostar': [7, 17, 27],
                    'gatilho': f'Terminal 7 ativado ({count_sete}x)',
                    'confianca': 'Média'
                }

        if ultimo_numero in [5, 15, 25, 35]:
            count_cinco = sum(1 for n in historico_recente if n in [5, 15, 25, 35])
            if count_cinco >= 1:
                return {
                    'nome': 'Padrão do Cinco',
                    'numeros_apostar': [5, 15, 25, 35],
                    'gatilho': f'Terminal 5 ativado ({count_cinco}x)',
                    'confianca': 'Média'
                }

        return None

# =============================
# ESTRATÉGIA ML ATUALIZADA E CORRIGIDA
# =============================
class EstrategiaML:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.ml = MLRoletaOtimizada(self.roleta)
        self.historico = deque(maxlen=30)
        self.nome = "Machine Learning (CatBoost)"
        self.ml.carregar_modelo()
        self.contador_sorteios = 0
        
        self.zonas_ml = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.quantidade_zonas_ml = {
            'Vermelha': 6,
            'Azul': 6,
            'Amarela': 6
        }
        
        self.numeros_zonas_ml = {}
        for nome, central in self.zonas_ml.items():
            qtd = self.quantidade_zonas_ml.get(nome, 6)
            self.numeros_zonas_ml[nome] = self.roleta.get_vizinhos_zona(central, qtd)

        self.sequencias_padroes = {
            'sequencias_ativas': {},
            'historico_sequencias': [],
            'padroes_detectados': []
        }
        
        self.metricas_padroes = {
            'padroes_detectados_total': 0,
            'padroes_acertados': 0,
            'padroes_errados': 0,
            'eficiencia_por_tipo': {},
            'historico_validacao': []
        }
        
        self.sistema_selecao = SistemaSelecaoInteligente()

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.contador_sorteios += 1
        
        if len(self.historico) > 1:
            numero_anterior = list(self.historico)[-2]
            self.validar_padrao_acerto(numero, self.get_previsao_atual())
        
        self.analisar_padroes_sequenciais(numero)
        
        if self.contador_sorteios >= 15:
            self.contador_sorteios = 0
            self.treinar_automatico()

    def get_previsao_atual(self):
        try:
            resultado = self.analisar_ml_corrigido()
            return resultado
        except:
            return None

    def validar_padrao_acerto(self, numero_sorteado, previsao_ml):
        if not previsao_ml:
            return
            
        zona_sorteada = None
        for zona, numeros in self.numeros_zonas_ml.items():
            if numero_sorteado in numeros:
                zona_sorteada = zona
                break
        
        if not zona_sorteada:
            return
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if len(self.historico) - p['detectado_em'] <= 3]
        
        for padrao in padroes_recentes:
            self.metricas_padroes['padroes_detectados_total'] += 1
            
            if padrao['zona'] == zona_sorteada:
                self.metricas_padroes['padroes_acertados'] += 1
                tipo = padrao['tipo']
                if tipo not in self.metricas_padroes['eficiencia_por_tipo']:
                    self.metricas_padroes['eficiencia_por_tipo'][tipo] = {'acertos': 0, 'total': 0}
                self.metricas_padroes['eficiencia_por_tipo'][tipo]['acertos'] += 1
                self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1
            else:
                self.metricas_padroes['padroes_errados'] += 1
                tipo = padrao['tipo']
                if tipo in self.metricas_padroes['eficiencia_por_tipo']:
                    self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1

    def analisar_padroes_sequenciais(self, numero):
        if len(self.historico) < 5:
            return
            
        historico_recente = list(self.historico)[-8:]
        
        zona_atual = None
        for zona, numeros in self.numeros_zonas_ml.items():
            if numero in numeros:
                zona_atual = zona
                break
        
        if not zona_atual:
            return
        
        self.atualizar_sequencias_ativas(zona_atual, historico_recente)
        self.otimizar_deteccao_padroes(historico_recente)
        self.limpar_padroes_antigos()

    def otimizar_deteccao_padroes(self, historico_recente):
        if len(historico_recente) < 5:
            return
        
        zonas_recentes = []
        for num in historico_recente:
            zona_num = None
            for zona, numeros in self.numeros_zonas_ml.items():
                if num in numeros:
                    zona_num = zona
                    break
            zonas_recentes.append(zona_num)
        
        for i in range(len(zonas_recentes) - 3):
            janela = zonas_recentes[i:i+4]
            if (janela[0] and janela[1] and janela[2] and janela[3] and
                janela[0] == janela[1] == janela[2] == janela[3]):
                
                self.registrar_padrao_sequencia_forte(janela[0], i)

        for i in range(len(zonas_recentes) - 3):
            janela = zonas_recentes[i:i+4]
            if (janela[0] and janela[1] and janela[3] and
                janela[0] == janela[1] == janela[3] and
                janela[2] != janela[0]):
                
                self.registrar_padrao_retorno_imediato(janela[0], i)

        for i in range(len(zonas_recentes) - 5):
            janela = zonas_recentes[i:i+6]
            if (janela[0] and janela[1] and janela[2] and janela[4] and janela[5] and
                janela[0] == janela[1] == janela[2] == janela[4] == janela[5] and
                janela[3] != janela[0]):
                
                self.registrar_padrao_sequencia_interrompida(janela[0], i)

        for i in range(len(zonas_recentes) - 4):
            janela = zonas_recentes[i:i+5]
            if (janela[0] and janela[1] and janela[3] and janela[4] and
                janela[0] == janela[1] == janela[3] == janela[4] and
                janela[2] != janela[0]):
                
                self.registrar_padrao_retorno_rapido(janela[0], i)

    def registrar_padrao_sequencia_forte(self, zona, posicao):
        padrao = {
            'tipo': 'sequencia_forte_4',
            'zona': zona,
            'padrao': 'AAAA',
            'forca': 0.95,
            'duracao': 4,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao, janela=8):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO FORTE 4x: {zona} - {padrao['padrao']}")

    def registrar_padrao_retorno_imediato(self, zona, posicao):
        padrao = {
            'tipo': 'retorno_imediato',
            'zona': zona,
            'padrao': 'AA_B_A',
            'forca': 0.80,
            'duracao': 4,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao, janela=10):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO RÁPIDO: {zona} - {padrao['padrao']}")

    def registrar_padrao_sequencia_interrompida(self, zona, posicao):
        padrao = {
            'tipo': 'sequencia_interrompida_forte',
            'zona': zona,
            'padrao': 'AAA_B_AA',
            'forca': 0.85,
            'duracao': 6,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO FORTE: {zona} - {padrao['padrao']}")

    def registrar_padrao_retorno_rapido(self, zona, posicao):
        padrao = {
            'tipo': 'retorno_rapido',
            'zona': zona,
            'padrao': 'AA_B_AA',
            'forca': 0.75,
            'duracao': 5,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO RÁPIDO: {zona} - {padrao['padrao']}")

    def padrao_recente_similar(self, novo_padrao, janela=12):
        for padrao in self.sequencias_padroes['padroes_detectados'][-10:]:
            if (padrao['zona'] == novo_padrao['zona'] and 
                padrao['tipo'] == novo_padrao['tipo'] and
                len(self.historico) - padrao['detectado_em'] < janela):
                return True
        return False

    def limpar_padroes_antigos(self, limite=20):
        padroes_validos = []
        for padrao in self.sequencias_padroes['padroes_detectados']:
            if len(self.historico) - padrao['detectado_em'] <= limite:
                padroes_validos.append(padrao)
        self.sequencias_padroes['padroes_detectados'] = padroes_validos

    def atualizar_sequencias_ativas(self, zona_atual, historico_recente):
        if zona_atual in self.sequencias_padroes['sequencias_ativas']:
            sequencia = self.sequencias_padroes['sequencias_ativas'][zona_atual]
            sequencia['contagem'] += 1
            sequencia['ultimo_numero'] = historico_recente[-1]
        else:
            self.sequencias_padroes['sequencias_ativas'][zona_atual] = {
                'contagem': 1,
                'inicio': len(self.historico) - 1,
                'ultimo_numero': historico_recente[-1],
                'quebras': 0
            }
        
        zonas_ativas = list(self.sequencias_padroes['sequencias_ativas'].keys())
        for zona in zonas_ativas:
            if zona != zona_atual:
                self.sequencias_padroes['sequencias_ativas'][zona]['quebras'] += 1
                
                if self.sequencias_padroes['sequencias_ativas'][zona]['quebras'] >= 3:
                    sequencia_final = self.sequencias_padroes['sequencias_ativas'][zona]
                    if sequencia_final['contagem'] >= 3:
                        self.sequencias_padroes['historico_sequencias'].append({
                            'zona': zona,
                            'tamanho': sequencia_final['contagem'],
                            'finalizado_em': len(self.historico) - 1
                        })
                    del self.sequencias_padroes['sequencias_ativas'][zona]

    def analisar_ml_corrigido(self):
        """Nova estratégia ML focada em prever zonas"""
        if len(self.historico) < 50:
            return None

        if not self.ml.is_trained:
            return None

        historico_numeros = self.extrair_numeros_historico()
        
        zonas_previstas, msg = self.ml.prever_zona_proxima(historico_numeros)
        
        if zonas_previstas is None:
            return None
        
        zonas_top = [zona for zona, prob in zonas_previstas[:2]]
        
        if not zonas_top:
            return None
        
        numeros_combinados = []
        for zona in zonas_top:
            numeros_combinados.extend(self.numeros_zonas_ml[zona])
        
        numeros_combinados = list(set(numeros_combinados))
        
        if len(numeros_combinados) > 10:
            numeros_combinados = self.sistema_selecao.selecionar_melhores_10_numeros(
                numeros_combinados, self.historico, "ML-Corrigido"
            )
        
        if len(zonas_previstas) >= 2:
            prob1 = zonas_previstas[0][1]
            prob2 = zonas_previstas[1][1] if len(zonas_previstas) > 1 else 0
            diff = prob1 - prob2
            
            if diff > 0.3:
                confianca = 'Alta'
            elif diff > 0.15:
                confianca = 'Média'
            else:
                confianca = 'Baixa'
        else:
            confianca = 'Baixa'
        
        return {
            'nome': 'ML Corrigido - Previsão de Zona',
            'numeros_apostar': numeros_combinados,
            'gatilho': f'ML - Zonas: {", ".join(zonas_top)} | Prob: {zonas_previstas[0][1]:.2%}',
            'confianca': confianca,
            'zonas_envolvidas': zonas_top,
            'tipo': 'dupla' if len(zonas_top) > 1 else 'unica',
            'selecao_inteligente': True
        }

    def treinar_automatico(self):
        historico_numeros = self.extrair_numeros_historico()
        
        if len(historico_numeros) >= self.ml.min_training_samples:
            try:
                success, message = self.ml.treinar_modelo_corrigido(historico_numeros)
                if success:
                    logging.info(f"✅ Treinamento automático ML: {message}")
                    
                    # Enviar notificação de treinamento se ativado
                    if 'alertas_config' in st.session_state and st.session_state.alertas_config.get('alertas_treinamento', True):
                        if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                                enviar_telegram(f"🧠 TREINAMENTO ML COMPLETO\n{message}")
                else:
                    logging.warning(f"⚠️ Treinamento automático falhou: {message}")
            except Exception as e:
                logging.error(f"❌ Erro no treinamento automático: {e}")

    def extrair_numeros_historico(self):
        historico_numeros = []
        for item in list(self.historico):
            if isinstance(item, dict) and 'number' in item:
                historico_numeros.append(item['number'])
            elif isinstance(item, (int, float)):
                historico_numeros.append(int(item))
        return historico_numeros

    def analisar_distribuicao_zonas(self, top_25_numeros):
        contagem_zonas = {}
        
        for zona, numeros in self.numeros_zonas_ml.items():
            count = sum(1 for num in top_25_numeros if num in numeros)
            contagem_zonas[zona] = count
        
        return contagem_zonas if contagem_zonas else None

    def calcular_confianca_zona_ml(self, distribuicao):
        contagem = distribuicao['contagem']
        total = distribuicao['total_zonas']
        if total > 0:
            percentual = (contagem / total) * 100
        else:
            percentual = 0
        
        if percentual >= 50:
            return 'Muito Alta'
        elif percentual >= 40:
            return 'Alta'
        elif percentual >= 30:
            return 'Média'
        elif percentual >= 25:
            return 'Baixa'
        else:
            return 'Muito Baixa'

    def treinar_modelo_ml(self, historico_completo=None):
        if historico_completo is not None:
            historico_numeros = historico_completo
        else:
            historico_numeros = self.extrair_numeros_historico()
        
        if len(historico_numeros) >= self.ml.min_training_samples:
            success, message = self.ml.treinar_modelo_corrigido(historico_numeros)
            
            # Enviar notificação de treinamento se ativado
            if success and 'alertas_config' in st.session_state and st.session_state.alertas_config.get('alertas_treinamento', True):
                if all(key in st.session_state for key in ['telegram_token', 'telegram_chat_id']):
                    if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                        enviar_telegram(f"🧠 TREINAMENTO ML COMPLETO\n{message}")
            
            return success, message
        else:
            return False, f"Histórico insuficiente: {len(historico_numeros)}/{self.ml.min_training_samples} números"

    def get_analise_ml(self):
        if not self.ml.is_trained:
            return "🤖 ML: Modelo não treinado"
        
        if len(self.historico) < 10:
            return "🤖 ML: Aguardando mais dados para análise"
        
        historico_numeros = self.extrair_numeros_historico()
        
        zonas_previstas, msg = self.ml.prever_zona_proxima(historico_numeros)
        
        if zonas_previstas:
            if self.ml.models:
                primeiro_modelo = self.ml.models[0]
                modelo_tipo = "CatBoost" if hasattr(primeiro_modelo, 'iterations') else "RandomForest"
            else:
                modelo_tipo = "Não treinado"
            
            analise = f"🤖 ANÁLISE ML CORRIGIDO - PREVISÃO DE ZONA\n"
            analise += f"🔄 Modelo: {modelo_tipo}\n"
            analise += f"📊 Treinamentos realizados: {self.ml.contador_treinamento}\n"
            analise += f"🎯 Próximo treinamento: {15 - self.contador_sorteios} sorteios\n"
            
            if 'last_accuracy' in self.ml.meta:
                acc = self.ml.meta['last_accuracy']
                analise += f"📈 Última acurácia: {acc:.2%}\n"
            
            analise += f"\n🎯 PREVISÃO DE ZONAS (probabilidades):\n"
            for zona, prob in zonas_previstas:
                analise += f"  📍 {zona}: {prob:.2%}\n"
            
            zona_recomendada = zonas_previstas[0][0] if zonas_previstas else None
            if zona_recomendada:
                numeros_zona = self.numeros_zonas_ml[zona_recomendada]
                analise += f"\n🎯 ZONA RECOMENDADA: {zona_recomendada}\n"
                analise += f"🔢 Números: {sorted(numeros_zona)}\n"
                analise += f"📊 Quantidade: {len(numeros_zona)} números\n"
            
            return analise
        else:
            return "🤖 ML: Erro na previsão"

    def get_estatisticas_padroes(self):
        if not hasattr(self, 'metricas_padroes'):
            return "📊 Métricas de padrões: Não disponível"
        
        total = self.metricas_padroes['padroes_detectados_total']
        if total == 0:
            return "📊 Métricas de padrões: Nenhum padrão validado ainda"
        
        acertos = self.metricas_padroes['padroes_acertados']
        if total > 0:
            eficiencia = (acertos / total) * 100
        else:
            eficiencia = 0
        
        estatisticas = f"📊 EFICIÊNCIA DOS PADRÕES:\n"
        estatisticas += f"✅ Padrões que acertaram: {acertos}/{total} ({eficiencia:.1f}%)\n"
        
        for tipo, dados in self.metricas_padroes['eficiencia_por_tipo'].items():
            if dados['total'] > 0:
                eff_tipo = (dados['acertos'] / dados['total']) * 100
                estatisticas += f"   🎯 {tipo}: {dados['acertos']}/{dados['total']} ({eff_tipo:.1f}%)\n"
        
        padroes_ativos = [p for p in self.sequencias_padroes['padroes_detectados'] 
                         if len(self.historico) - p['detectado_em'] <= 10]
        
        estatisticas += f"🔍 Padrões ativos: {len(padroes_ativos)}\n"
        for padrao in padroes_ativos[-3:]:
            idade = len(self.historico) - padrao['detectado_em']
            estatisticas += f"   📈 {padrao['zona']}: {padrao['tipo']} (há {idade} jogos)\n"
        
        return estatisticas

    def get_info_zonas_ml(self):
        info = {}
        for zona, numeros in self.numeros_zonas_ml.items():
            info[zona] = {
                'numeros': sorted(numeros),
                'quantidade': len(numeros),
                'central': self.zonas_ml[zona],
                'descricao': f"6 antes + 6 depois do {self.zonas_ml[zona]}"
            }
        return info

    def zerar_padroes(self):
        self.sequencias_padroes = {
            'sequencias_ativas': {},
            'historico_sequencias': [],
            'padroes_detectados': []
        }
        self.metricas_padroes = {
            'padroes_detectados_total': 0,
            'padroes_acertados': 0,
            'padroes_errados': 0,
            'eficiencia_por_tipo': {},
            'historico_validacao': []
        }
        logging.info("🔄 Padrões sequenciais e métricas zerados")

    def analisar_ml(self):
        return self.analisar_ml_corrigido()

# =============================
# SISTEMA DE GESTÃO ATUALIZADO E CORRIGIDO COM APRENDIZADO POR REFORÇO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.estrategia_midas = EstrategiaMidas()
        self.estrategia_ml = EstrategiaML()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Zonas"
        self.contador_sorteios_global = 0
        
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        self.todas_combinacoes_zonas = [
            ['Vermelha', 'Azul'],
            ['Vermelha', 'Amarela'], 
            ['Azul', 'Amarela']
        ]
        
        self.sistema_tendencias = SistemaTendencias()
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()  # NOVO
        self.ultima_otimizacao = None
        self.contador_otimizacoes_aplicadas = 0

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def treinar_modelo_ml(self, historico_completo=None):
        return self.estrategia_ml.treinar_modelo_ml(historico_completo)

    # =============================
    # FUNÇÕES DE ROTAÇÃO CORRIGIDAS
    # =============================
    
    def rotacionar_estrategia_automaticamente(self, acerto, nome_estrategia, zonas_envolvidas):
        """ROTAÇÃO AUTOMÁTICA CORRIGIDA - Lógica simplificada e funcional"""
        
        # Atualizar desempenho da combinação
        dados_combinacao = self.atualizar_desempenho_combinacao(zonas_envolvidas, acerto)
        
        # Atualizar sequências globais
        if acerto:
            self.sequencia_acertos += 1
            self.sequencia_erros = 0
        else:
            self.sequencia_erros += 1
            self.sequencia_acertos = 0
            self.ultima_estrategia_erro = nome_estrategia
        
        # Verificar se é uma combinação dupla
        if len(zonas_envolvidas) > 1:
            combinacao_atual = tuple(sorted(zonas_envolvidas))
            
            # REGRA 1: ROTAÇÃO POR 3 ACERTOS SEGUIDOS NA MESMA COMBINAÇÃO
            if acerto and dados_combinacao and dados_combinacao.get('sequencia_acertos', 0) >= 3:
                logging.info(f"🎯 REGRA ATIVADA: 3 acertos seguidos na combinação {combinacao_atual}")
                
                # Resetar sequência de acertos desta combinação
                if combinacao_atual in self.historico_combinacoes:
                    self.historico_combinacoes[combinacao_atual]['sequencia_acertos'] = 0
                
                # Tentar rotação por novas zonas
                if self.rotacionar_por_novas_zonas(combinacao_atual):
                    return True
                
                # Se não conseguir, usar rotação por acertos
                return self.aplicar_rotacao_por_acertos_combinacoes(combinacao_atual)
            
            # REGRA 2: ROTAÇÃO POR 2 ERROS SEGUIDOS NA MESMA COMBINAÇÃO
            if not acerto and dados_combinacao and dados_combinacao.get('sequencia_erros', 0) >= 2:
                logging.info(f"🚨 REGRA ATIVADA: 2 erros seguidos na combinação {combinacao_atual}")
                
                # Resetar sequência de erros desta combinação
                if combinacao_atual in self.historico_combinacoes:
                    self.historico_combinacoes[combinacao_atual]['sequencia_erros'] = 0
                
                # Adicionar à lista fria se não estiver
                if combinacao_atual not in self.combinacoes_frias:
                    self.combinacoes_frias.append(combinacao_atual)
                    logging.info(f"📝 Combinação {combinacao_atual} adicionada à lista fria")
                
                # Aplicar rotação inteligente
                return self.aplicar_rotacao_inteligente()
        
        # REGRA 3: ROTAÇÃO GLOBAL POR 2 ERROS SEGUIDOS (qualquer estratégia)
        if not acerto and self.sequencia_erros >= 2:
            logging.info(f"🌍 REGRA GLOBAL: 2 erros seguidos no sistema")
            
            # Se está em Zonas, mudar para ML
            if self.estrategia_selecionada == "Zonas":
                self.estrategia_selecionada = "ML"
                self.sequencia_erros = 0
                self.sequencia_acertos = 0
                enviar_rotacao_automatica("Zonas", "ML")
                logging.info(f"🔄 ROTAÇÃO GLOBAL: Zonas → ML")
                return True
            # Se está em ML, voltar para Zonas
            elif self.estrategia_selecionada == "ML":
                self.estrategia_selecionada = "Zonas"
                self.sequencia_erros = 0
                self.sequencia_acertos = 0
                enviar_rotacao_automatica("ML", "Zonas")
                logging.info(f"🔄 ROTAÇÃO GLOBAL: ML → Zonas")
                return True
            # Se está em Midas, voltar para Zonas
            elif self.estrategia_selecionada == "Midas":
                self.estrategia_selecionada = "Zonas"
                self.sequencia_erros = 0
                self.sequencia_acertos = 0
                enviar_rotacao_automatica("Midas", "Zonas")
                logging.info(f"🔄 ROTAÇÃO GLOBAL: Midas → Zonas")
                return True
        
        return False

    def aplicar_rotacao_por_acertos_combinacoes(self, combinacao_atual):
        """Rotação após 3 acertos - VERSÃO CORRIGIDA"""
        logging.info(f"🎯 ROTAÇÃO POR ACERTOS: Analisando alternativas para {combinacao_atual}")
        
        # 1. Extrair zonas da combinação atual
        zona_atual_1, zona_atual_2 = combinacao_atual
        
        # 2. Encontrar zona que NÃO está na combinação atual
        todas_zonas = ['Vermelha', 'Azul', 'Amarela']
        zona_fora = [z for z in todas_zonas if z not in combinacao_atual]
        
        if zona_fora:
            zona_nova = zona_fora[0]
            logging.info(f"🎯 Zona disponível fora da combinação atual: {zona_nova}")
            
            # 3. Criar combinações com a zona nova + uma das zonas atuais
            combinacoes_possiveis = [
                tuple(sorted([zona_nova, zona_atual_1])),
                tuple(sorted([zona_nova, zona_atual_2]))
            ]
            
            # 4. Analisar cada combinação possível
            combinacoes_analisadas = []
            
            for combo in combinacoes_possiveis:
                # Pular se for a mesma combinação
                if combo == combinacao_atual:
                    continue
                    
                # Pular se estiver na lista fria
                if combo in self.combinacoes_frias:
                    continue
                
                # Obter dados da combinação
                dados_combo = self.historico_combinacoes.get(combo, {})
                eficiencia = dados_combo.get('eficiencia', 50)  # 50% se não testado
                total = dados_combo.get('total', 0)
                sequencia_erros = dados_combo.get('sequencia_erros', 0)
                
                # Filtrar combinações com problemas
                if total > 0:
                    if eficiencia < 20:  # Eficiência muito baixa
                        continue
                    if sequencia_erros >= 2:  # Recentemente teve 2 erros seguidos
                        continue
                
                # Calcular pontuação
                pontuacao = eficiencia
                if total == 0:  # Nunca testada - dar chance
                    pontuacao = 60
                
                combinacoes_analisadas.append({
                    'combo': combo,
                    'pontuacao': pontuacao,
                    'eficiencia': eficiencia,
                    'total': total,
                    'zona_nova': zona_nova
                })
            
            # 5. Escolher a melhor combinação
            if combinacoes_analisadas:
                combinacoes_analisadas.sort(key=lambda x: x['pontuacao'], reverse=True)
                melhor_combo = combinacoes_analisadas[0]['combo']
                
                logging.info(f"✅ MELHOR COMBINAÇÃO ESCOLHIDA: {melhor_combo}")
                logging.info(f"   • Pontuação: {combinacoes_analisadas[0]['pontuacao']:.1f}")
                logging.info(f"   • Eficiência: {combinacoes_analisadas[0]['eficiencia']:.1f}%")
                logging.info(f"   • Total jogos: {combinacoes_analisadas[0]['total']}")
                
                # 6. Criar previsão com a nova combinação
                if self.criar_previsao_com_combinacao(melhor_combo):
                    # Resetar sequências globais
                    self.sequencia_acertos = 0
                    
                    # Enviar notificação
                    enviar_rotacao_por_acertos_combinacoes(combinacao_atual, melhor_combo)
                    logging.info(f"🔄 ROTAÇÃO POR ACERTOS aplicada: {combinacao_atual} → {melhor_combo}")
                    return True
        
        # 7. Se não encontrou combinação com zona nova, usar lógica alternativa
        logging.info("⚠️  Não encontrou combinação com zona nova - usando lógica alternativa")
        
        combinacoes_alternativas = [
            tuple(combo) for combo in self.todas_combinacoes_zonas
            if tuple(combo) != combinacao_atual
            and tuple(combo) not in self.combinacoes_frias
        ]
        
        if combinacoes_alternativas:
            # Escolher aleatoriamente (para evitar padrões)
            import random
            nova_combinacao = random.choice(combinacoes_alternativas)
            
            if self.criar_previsao_com_combinacao(nova_combinacao):
                self.sequencia_acertos = 0
                enviar_rotacao_por_acertos_combinacoes(combinacao_atual, nova_combinacao)
                logging.info(f"🔄 ROTAÇÃO ALTERNATIVA: {combinacao_atual} → {nova_combinacao}")
                return True
        
        logging.warning(f"❌ Não foi possível encontrar combinação alternativa para {combinacao_atual}")
        return False

    def aplicar_rotacao_inteligente(self):
        """Rotação inteligente após 2 erros - VERSÃO CORRIGIDA"""
        estrategia_atual = self.estrategia_selecionada
        
        logging.info(f"🚨 APLICANDO ROTAÇÃO INTELIGENTE - Estratégia: {estrategia_atual}, Erros: {self.sequencia_erros}")
        
        # Verificar se temos previsão ativa e combinação
        if self.previsao_ativa and self.previsao_ativa.get('zonas_envolvidas'):
            combinacao_atual = tuple(sorted(self.previsao_ativa['zonas_envolvidas']))
            logging.info(f"🔍 ROTAÇÃO: Combinacao atual detectada: {combinacao_atual}")
            
            # TENTATIVA 1: Rotação para combinação diferente
            if self.rotacionar_por_novas_zonas(combinacao_atual):
                self.sequencia_erros = 0
                return True
        
        # TENTATIVA 2: Rotação entre estratégias
        if estrategia_atual == "Zonas":
            self.estrategia_selecionada = "ML"
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            enviar_rotacao_automatica("Zonas", "ML")
            logging.info(f"🔄 ROTAÇÃO: Zonas → ML")
            return True
        elif estrategia_atual == "ML":
            self.estrategia_selecionada = "Zonas"
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            enviar_rotacao_automatica("ML", "Zonas")
            logging.info(f"🔄 ROTAÇÃO: ML → Zonas")
            return True
        elif estrategia_atual == "Midas":
            self.estrategia_selecionada = "Zonas"
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            enviar_rotacao_automatica("Midas", "Zonas")
            logging.info(f"🔄 ROTAÇÃO: Midas → Zonas")
            return True
        
        return False

    def rotacionar_por_novas_zonas(self, combinacao_atual):
        """Rotação para usar zonas diferentes - VERSÃO CORRIGIDA"""
        logging.info(f"🔄 ROTAÇÃO POR NOVAS ZONAS: Analisando alternativas para {combinacao_atual}")
        
        # Extrair zonas atuais
        zona_atual_1, zona_atual_2 = combinacao_atual
        
        # Todas as zonas disponíveis
        todas_zonas = ['Vermelha', 'Azul', 'Amarela']
        
        # Encontrar a zona que NÃO está na combinação atual
        zona_fora = [z for z in todas_zonas if z not in combinacao_atual]
        
        if zona_fora:
            zona_nova = zona_fora[0]
            logging.info(f"🎯 Zona disponível fora da combinação atual: {zona_nova}")
            
            # Criar combinações com a zona nova + uma das zonas atuais
            combinacoes_possiveis = [
                tuple(sorted([zona_nova, zona_atual_1])),
                tuple(sorted([zona_nova, zona_atual_2]))
            ]
            
            # Analisar cada combinação
            for combo in combinacoes_possiveis:
                if combo == combinacao_atual:
                    continue
                    
                # Verificar se não está na lista fria
                if combo in self.combinacoes_frias:
                    logging.info(f"  ⚠️ Combinação {combo} está na lista fria")
                    continue
                
                # Verificar dados históricos
                dados = self.historico_combinacoes.get(combo, {})
                if dados:
                    eficiencia = dados.get('eficiencia', 0)
                    total = dados.get('total', 0)
                    sequencia_erros = dados.get('sequencia_erros', 0)
                    
                    if total >= 3 and eficiencia < 20:
                        logging.info(f"  ⚠️ Combinação {combo} tem eficiência baixa ({eficiencia:.1f}%)")
                        continue
                        
                    if sequencia_erros >= 2:
                        logging.info(f"  ⚠️ Combinação {combo} teve 2 erros seguidos recentemente")
                        continue
                
                # Se chegou aqui, a combinação é válida
                if self.criar_previsao_com_combinacao(combo):
                    logging.info(f"✅ ROTAÇÃO SELECIONADA: {combinacao_atual} → {combo}")
                    
                    # Resetar sequências
                    self.sequencia_erros = 0
                    
                    # Enviar notificação
                    enviar_rotacao_por_2_erros(combinacao_atual, combo)
                    return True
        
        logging.info("⚠️  Não foi possível encontrar combinação com zona nova")
        return False

    def atualizar_desempenho_combinacao(self, zonas_envolvidas, acerto):
        """Atualiza desempenho de combinações - VERSÃO CORRIGIDA"""
        if len(zonas_envolvidas) > 1:
            combinacao = tuple(sorted(zonas_envolvidas))
            
            if combinacao not in self.historico_combinacoes:
                self.historico_combinacoes[combinacao] = {
                    'acertos': 0, 
                    'total': 0, 
                    'eficiencia': 0.0,
                    'ultimo_jogo': len(self.historico_desempenho),
                    'sequencia_acertos': 0,
                    'sequencia_erros': 0
                }
            
            dados = self.historico_combinacoes[combinacao]
            dados['total'] += 1
            dados['ultimo_jogo'] = len(self.historico_desempenho)
            
            if acerto:
                dados['acertos'] += 1
                dados['sequencia_acertos'] += 1
                dados['sequencia_erros'] = 0
            else:
                dados['sequencia_erros'] += 1
                dados['sequencia_acertos'] = 0
            
            if dados['total'] > 0:
                dados['eficiencia'] = (dados['acertos'] / dados['total']) * 100
            
            # Atualizar combinações quentes/frias
            self.atualizar_combinacoes_quentes_frias()
            
            return dados
        
        return None

    def atualizar_combinacoes_quentes_frias(self):
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        combinacoes_ativas = {k: v for k, v in self.historico_combinacoes.items() 
                             if v['total'] >= 2}
        
        for combinacao, dados in combinacoes_ativas.items():
            eficiencia = dados['eficiencia']
            total_jogos = dados['total']
            sequencia_acertos = dados['sequencia_acertos']
            sequencia_erros = dados['sequencia_erros']
            
            # Combinação quente
            if (eficiencia >= 50 or 
                (eficiencia >= 40 and total_jogos >= 3) or
                sequencia_acertos >= 2):
                self.combinacoes_quentes.append(combinacao)
            
            # Combinação fria
            elif (eficiencia < 25 and total_jogos >= 3) or sequencia_erros >= 2:
                self.combinacoes_frias.append(combinacao)
    
    def get_combinacao_recomendada(self):
        if not self.combinacoes_quentes:
            return None
        
        # Priorizar combinações com sequência de acertos
        combinacoes_com_sequencia = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if combo in self.combinacoes_quentes and dados['sequencia_acertos'] >= 1
        ]
        
        if combinacoes_com_sequencia:
            combinacoes_com_sequencia.sort(key=lambda x: x[1]['sequencia_acertos'], reverse=True)
            return combinacoes_com_sequencia[0][0]
        
        # Se não tiver sequência, usar eficiência
        combinacoes_eficientes = [
            (combo, dados) for combo, dados in self.historico_combinacoes.items()
            if combo in self.combinacoes_quentes
        ]
        
        if combinacoes_eficientes:
            combinacoes_eficientes.sort(key=lambda x: x[1]['eficiencia'], reverse=True)
            return combinacoes_eficientes[0][0]
        
        return None

    def deve_evitar_combinacao(self, combinacao):
        if combinacao in self.combinacoes_frias:
            return True
        
        dados = self.historico_combinacoes.get(combinacao, {})
        if dados and dados.get('total', 0) >= 3 and dados.get('eficiencia', 0) < 20:
            return True
            
        return False

    def calcular_performance_estrategias(self):
        performance = {}
        historico_recente = self.historico_desempenho[-10:] if len(self.historico_desempenho) >= 10 else self.historico_desempenho
        
        for resultado in historico_recente:
            estrategia = resultado['estrategia']
            if estrategia not in performance:
                performance[estrategia] = {'acertos': 0, 'total': 0}
            
            performance[estrategia]['total'] += 1
            if resultado['acerto']:
                performance[estrategia]['acertos'] += 1
        
        for estrategia, dados in performance.items():
            if dados['total'] > 0:
                performance[estrategia] = (dados['acertos'] / dados['total']) * 100
            else:
                performance[estrategia] = 0
        
        return performance

    def combinacao_para_texto(self, combinacao):
        if len(combinacao) == 2:
            zona1, zona2 = combinacao
            return f"{zona1}+{zona2}"
        return str(combinacao)

    def criar_previsao_com_combinacao(self, combinacao):
        """Cria previsão com combinação específica - VERSÃO CORRIGIDA"""
        try:
            zonas_list = list(combinacao)
            
            # Usar a estratégia de zonas para criar a previsão
            if hasattr(self, 'estrategia_zonas'):
                if len(zonas_list) == 2:
                    previsao_forcada = self.estrategia_zonas.criar_previsao_dupla(
                        zonas_list[0], 
                        zonas_list[1], 
                        "ROTAÇÃO-AUTOMÁTICA"
                    )
                else:
                    previsao_forcada = self.estrategia_zonas.criar_previsao_unica(
                        zonas_list[0]
                    )
                
                if previsao_forcada:
                    self.previsao_ativa = previsao_forcada
                    self.estrategia_selecionada = "Zonas"
                    
                    logging.info(f"🎯 Nova previsão criada com combinação: {combinacao}")
                    return True
                    
        except Exception as e:
            logging.error(f"❌ Erro ao criar previsão com combinação {combinacao}: {e}")
        
        return False

    def get_status_rotacao(self):
        """Status da rotação - VERSÃO CORRIGIDA"""
        status = {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'ultima_estrategia_erro': self.ultima_estrategia_erro,
            'ultimas_combinacoes_acerto': self.ultima_combinacao_acerto,
            'proxima_rotacao_erros': max(0, 2 - self.sequencia_erros),
            'proxima_rotacao_acertos': max(0, 3 - self.sequencia_acertos),
            'combinacoes_quentes': len(self.combinacoes_quentes),
            'combinacoes_frias': len(self.combinacoes_frias)
        }
        
        # Adicionar sequências por combinação
        sequencias_combinacoes = {}
        for combo, dados in self.historico_combinacoes.items():
            if dados.get('total', 0) > 0:
                sequencias_combinacoes[str(combo)] = {
                    'sequencia_acertos': dados.get('sequencia_acertos', 0),
                    'sequencia_erros': dados.get('sequencia_erros', 0),
                    'eficiencia': dados.get('eficiencia', 0),
                    'total': dados.get('total', 0)
                }
        
        status['sequencias_combinacoes'] = sequencias_combinacoes
        
        return status

    def get_debug_rotacao(self):
        """Retorna informações detalhadas para debug da rotação"""
        debug_info = {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'previsao_ativa': bool(self.previsao_ativa),
            'historico_desempenho_tamanho': len(self.historico_desempenho),
            'combinacoes_registradas': len(self.historico_combinacoes)
        }
        
        if self.previsao_ativa:
            debug_info['previsao_tipo'] = self.previsao_ativa.get('nome', 'Desconhecido')
            debug_info['zonas_envolvidas'] = self.previsao_ativa.get('zonas_envolvidas', [])
        
        return debug_info

    # =============================
    # NOVO: PROCESSAMENTO COM OTIMIZAÇÃO
    # =============================
    def processar_com_otimizacao(self, resultado):
        """Processa resultado com otimização estatística"""
        # Processar normalmente
        self.processar_novo_numero(resultado['numero'])
        
        # Aplicar otimização
        otimizacao = self.sistema_otimizacao.processar_resultado(resultado)
        
        if otimizacao:
            self.ultima_otimizacao = otimizacao
            
            # Aplicar otimização se necessário
            if otimizacao['acao'] == 'mudar' and otimizacao['confianca_estatistica'] >= 70:
                aplicada = self.sistema_otimizacao.aplicar_otimizacao(self, otimizacao)
                if aplicada:
                    self.contador_otimizacoes_aplicadas += 1
            
            # Enviar alertas estatísticos
            if otimizacao.get('alerta'):
                prioridade = 'alta' if '90%' in otimizacao['alerta'] else 'media'
                enviar_alerta_estatistico(otimizacao['alerta'], prioridade)
        
        return otimizacao

    def get_relatorio_otimizacao(self):
        """Retorna relatório de otimização"""
        if not hasattr(self, 'sistema_otimizacao'):
            return "Sistema de otimização não inicializado"
        
        resumo = self.sistema_otimizacao.get_resumo_otimizacao()
        
        relatorio = "🤖 RELATÓRIO DE OTIMIZAÇÃO DINÂMICA\n"
        relatorio += "=" * 60 + "\n"
        
        relatorio += f"📊 Total de otimizações: {resumo['total_otimizacoes']}\n"
        relatorio += f"🔄 Otimizações aplicadas: {self.contador_otimizacoes_aplicadas}\n"
        
        # Performance recente
        perf = resumo['performance_recente']
        relatorio += f"🎯 Performance recente: {perf['acertos']}/{perf['total']} ({perf['taxa']:.1f}%)\n"
        relatorio += f"📈 Confiança estatística recente: {perf['confianca']:.1f}%\n"
        
        # Viabilidade de 90%
        if resumo.get('viabilidade_90porcento') is not None:
            status = "✅ VIÁVEL" if resumo['viabilidade_90porcento'] else "❌ INVIÁVEL"
            relatorio += f"🎯 Meta de 90%: {status}\n"
        
        # Última recomendação
        if resumo['ultima_recomendacao']:
            rec = resumo['ultima_recomendacao']['recomendacoes']
            if rec.get('melhor_combinacao'):
                confianca = rec.get('confianca_estatistica', 0)
                relatorio += f"🏆 Melhor combinação: {rec['melhor_combinacao']} (Conf: {confianca:.1f}%)\n"
            
            if rec.get('evitar_combinacao'):
                relatorio += f"🚫 Evitar combinação: {rec['evitar_combinacao']}\n"
        
        # Estatísticas do aprendizado
        estat = resumo['estatisticas_aprendizado']
        relatorio += f"\n🧠 ESTATÍSTICAS DE APRENDIZADO:\n"
        relatorio += f"• Análises realizadas: {estat['total_analises']}\n"
        relatorio += f"• Padrões validados: {estat['padroes_validados_count']}\n"
        relatorio += f"• Combinações otimizadas: {estat['melhores_combinacoes_count']}\n"
        relatorio += f"• Taxa de validação: {estat['taxa_validacao']:.1f}%\n"
        
        # Top combinações
        if estat.get('top_combinacoes'):
            relatorio += f"\n🥇 TOP COMBINAÇÕES VALIDADAS:\n"
            for i, combo in enumerate(estat['top_combinacoes'][:3], 1):
                relatorio += f"  {i}. {combo['combinacao']}: {combo['eficiencia_ajustada']:.1f}% (Conf: {combo['confianca_estatistica']:.1f}%)\n"
        
        # Sugestões
        sugestoes = self.sistema_otimizacao.sugerir_melhoria_estrategia(self)
        if sugestoes:
            relatorio += f"\n💡 SUGESTÕES DE MELHORIA:\n"
            for sugestao in sugestoes:
                relatorio += f"• {sugestao}\n"
        
        return relatorio

    def processar_novo_numero(self, numero):
        try:
            if isinstance(numero, dict) and 'number' in numero:
                numero_real = numero['number']
            else:
                numero_real = numero
                
            self.contador_sorteios_global += 1
            
            # Processar resultado da previsão anterior
            if self.previsao_ativa:
                acerto = False
                zonas_acertadas = []
                nome_estrategia = self.previsao_ativa['nome']
                
                zonas_envolvidas = self.previsao_ativa.get('zonas_envolvidas', [])
                if not zonas_envolvidas:
                    acerto = numero_real in self.previsao_ativa['numeros_apostar']
                    if acerto:
                        if 'Zonas' in nome_estrategia:
                            for zona, numeros in self.estrategia_zonas.numeros_zonas.items():
                                if numero_real in numeros:
                                    zonas_acertadas.append(zona)
                                    break
                        elif 'ML' in nome_estrategia:
                            for zona, numeros in self.estrategia_ml.numeros_zonas_ml.items():
                                if numero_real in numeros:
                                    zonas_acertadas.append(zona)
                                    break
                else:
                    for zona in zonas_envolvidas:
                        if 'Zonas' in nome_estrategia:
                            numeros_zona = self.estrategia_zonas.numeros_zonas[zona]
                        elif 'ML' in nome_estrategia:
                            numeros_zona = self.estrategia_ml.numeros_zonas_ml[zona]
                        else:
                            continue
                        
                        if numero_real in numeros_zona:
                            acerto = True
                            zonas_acertadas.append(zona)
                
                # Criar resultado para otimização
                resultado_processado = {
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'previsao': self.previsao_ativa['numeros_apostar'],
                    'zona_acertada': "+".join(zonas_acertadas) if zonas_acertadas else None,
                    'zonas_envolvidas': zonas_envolvidas
                }
                
                # Processar com otimização
                otimizacao = self.processar_com_otimizacao(resultado_processado)
                
                # Atualizar análise de tendências
                self.atualizar_analise_tendencias(numero_real, zonas_acertadas[0] if zonas_acertadas else None, acerto)
                
                # Tentar rotação automática
                rotacionou = self.rotacionar_estrategia_automaticamente(acerto, nome_estrategia, zonas_envolvidas)
                
                # Atualizar contadores de estratégias
                if nome_estrategia not in self.estrategias_contador:
                    self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[nome_estrategia]['total'] += 1
                if acerto:
                    self.estrategias_contador[nome_estrategia]['acertos'] += 1
                    self.acertos += 1
                else:
                    self.erros += 1
                
                # Enviar notificação de resultado
                zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
                enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str)
                
                # Registrar no histórico
                self.historico_desempenho.append({
                    'numero': numero_real,
                    'acerto': acerto,
                    'estrategia': nome_estrategia,
                    'previsao': self.previsao_ativa['numeros_apostar'],
                    'rotacionou': rotacionou,
                    'zona_acertada': zona_acertada_str,
                    'zonas_envolvidas': zonas_envolvidas,
                    'tipo_aposta': self.previsao_ativa.get('tipo', 'unica'),
                    'sequencia_acertos': self.sequencia_acertos,
                    'sequencia_erros': self.sequencia_erros,
                    'ultima_combinacao_acerto': self.ultima_combinacao_acerto.copy(),
                    'otimizacao_aplicada': otimizacao is not None
                })
                
                self.previsao_ativa = None
            
            # Adicionar número às estratégias
            self.estrategia_zonas.adicionar_numero(numero_real)
            self.estrategia_midas.adicionar_numero(numero_real)
            self.estrategia_ml.adicionar_numero(numero_real)
            
            # Gerar nova previsão
            nova_estrategia = None
            
            if self.estrategia_selecionada == "Zonas":
                nova_estrategia = self.estrategia_zonas.analisar_zonas()
            elif self.estrategia_selecionada == "Midas":
                nova_estrategia = self.estrategia_midas.analisar_midas()
            elif self.estrategia_selecionada == "ML":
                nova_estrategia = self.estrategia_ml.analisar_ml()
            
            if nova_estrategia:
                self.previsao_ativa = nova_estrategia
                enviar_previsao_super_simplificada(nova_estrategia)
                
        except Exception as e:
            logging.error(f"Erro ao processar novo número: {e}")

    def atualizar_analise_tendencias(self, numero, zona_acertada=None, acerto_ultima=False):
        try:
            zonas_rankeadas = self.estrategia_zonas.get_zonas_rankeadas()
            if not zonas_rankeadas:
                return
            
            analise_tendencia = self.sistema_tendencias.analisar_tendencia(
                zonas_rankeadas, acerto_ultima, zona_acertada
            )
            
            self.sistema_tendencias.historico_tendencias.append(analise_tendencia)
            
            # Enviar notificações de tendência
            if 'alertas_config' in st.session_state and st.session_state.alertas_config.get('alertas_tendencia', True):
                self.sistema_tendencias.enviar_notificacoes_tendencia(analise_tendencia)
                enviar_alerta_tendencia(analise_tendencia)
            
        except Exception as e:
            logging.error(f"Erro na análise de tendências: {e}")

    def zerar_estatisticas_desempenho(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        
        self.sequencia_acertos = 0
        self.ultima_combinacao_acerto = []
        self.historico_combinacoes_acerto = []
        
        self.historico_combinacoes = {}
        self.combinacoes_quentes = []
        self.combinacoes_frias = []
        
        self.estrategia_zonas.zerar_estatisticas()
        
        self.sistema_tendencias = SistemaTendencias()
        self.sistema_otimizacao = SistemaOtimizacaoDinamica()  # Resetar otimização
        
        logging.info("📊 Todas as estatísticas de desempenho foram zeradas")
        salvar_sessao()

    def reset_recente_estatisticas(self):
        if len(self.historico_desempenho) > 10:
            self.historico_desempenho = self.historico_desempenho[-10:]
            
            self.acertos = sum(1 for resultado in self.historico_desempenho if resultado['acerto'])
            self.erros = len(self.historico_desempenho) - self.acertos
            
            self.estrategias_contador = {}
            for resultado in self.historico_desempenho:
                estrategia = resultado['estrategia']
                if estrategia not in self.estrategias_contador:
                    self.estrategias_contador[estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[estrategia]['total'] += 1
                if resultado['acerto']:
                    self.estrategias_contador[estrategia]['acertos'] += 1
            
            ultimos_resultados = self.historico_desempenho[-5:]
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            
            for resultado in reversed(ultimos_resultados):
                if resultado['acerto']:
                    self.sequencia_acertos += 1
                else:
                    break
                    
            for resultado in reversed(ultimos_resultados):
                if not resultado['acerto']:
                    self.sequencia_erros += 1
                else:
                    break
            
            logging.info("🔄 Estatísticas recentes resetadas (mantidos últimos 10 resultados)")
        else:
            logging.info("ℹ️  Histórico muito pequeno para reset recente")
        
        salvar_sessao()

    def get_analise_tendencias_completa(self):
        analise = "🎯 SISTEMA DE DETECÇÃO DE TENDÊNCIAS\n"
        analise += "=" * 60 + "\n"
        
        resumo = self.sistema_tendencias.get_resumo_tendencia()
        
        analise += f"📊 ESTADO ATUAL: {resumo['estado'].upper()}\n"
        analise += f"📍 ZONA ATIVA: {resumo['zona_ativa'] or 'Nenhuma'}\n"
        analise += f"🎯 CONTADORES: {resumo['contadores']['acertos']} acertos, {resumo['contadores']['erros']} erros\n"
        analise += f"📈 CONFIRMAÇÕES: {resumo['contadores']['confirmacoes']}\n"
        analise += f"🔄 OPERAÇÕES: {resumo['contadores']['operacoes']}\n"
        
        analise += "\n📋 HISTÓRICO RECENTE DE ZONAS:\n"
        for i, zona in enumerate(resumo['historico_zonas'][-8:]):
            analise += f"  {i+1:2d}. {zona}\n"
        
        if self.sistema_tendencias.historico_tendencias:
            ultima = self.sistema_tendencias.historico_tendencias[-1]
            analise += f"\n📝 ÚLTIMA ANÁLISE:\n"
            analise += f"  Estado: {ultima['estado']}\n"
            analise += f"  Confiança: {ultima['confianca']:.0%}\n"
            analise += f"  Ação: {ultima['acao'].upper()}\n"
            analise += f"  Mensagem: {ultima['mensagem']}\n"
        
        analise += "\n💡 RECOMENDAÇÃO DO FLUXOGRAMA:\n"
        estado = resumo['estado']
        if estado == "aguardando":
            analise += "  👀 Observar últimas 10-20 rodadas\n"
            analise += "  🎯 Identificar zona dupla mais forte\n"
        elif estado == "formando":
            analise += "  📈 Tendência se formando\n"
            analise += "  ⏳ Aguardar confirmação (1-2 acertos)\n"
        elif estado == "ativa":
            analise += "  🔥 TENDÊNCIA CONFIRMADA\n"
            analise += "  💰 Operar por 2-4 jogadas no máximo\n"
            analise += "  🎯 Apostar na zona dominante\n"
            analise += "  ⛔ Parar ao primeiro erro\n"
        elif estado == "enfraquecendo":
            analise += "  ⚠️ TENDÊNCIA ENFRAQUECENDO\n"
            analise += "  🚫 Evitar novas entradas\n"
            analise += "  👀 Observar sinais de morte\n"
        elif estado == "morta":
            analise += "  🟥 TENDÊNCIA MORTA\n"
            analise += "  🛑 PARAR OPERAÇÕES\n"
            analise += "  🔄 Aguardar 10-20 rodadas\n"
            analise += "  📊 Observar novo padrão\n"
        
        return analise

# =============================
# FUNÇÕES AUXILIARES
# =============================
def tocar_som_moeda():
    st.markdown("""<audio autoplay><source src="" type="audio/mp3"></audio>""", unsafe_allow_html=True)

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# FUNÇÃO PARA MOSTRAR COMBINAÇÕES DINÂMICAS
# =============================
def mostrar_combinacoes_dinamicas():
    if 'sistema' not in st.session_state:
        return
        
    sistema = st.session_state.sistema
    
    if hasattr(sistema, 'combinacoes_quentes') and sistema.combinacoes_quentes:
        st.sidebar.subheader("🔥 Combinações Quentes")
        for combo in sistema.combinacoes_quentes[:3]:
            dados = sistema.historico_combinacoes.get(combo, {})
            eff = dados.get('eficiencia', 0)
            total = dados.get('total', 0)
            seq = dados.get('sequencia_acertos', 0)
            st.sidebar.write(f"🎯 {combo[0]}+{combo[1]}: {eff:.1f}% ({seq}✓)")
    
    if hasattr(sistema, 'combinacoes_frias') and sistema.combinacoes_frias:
        st.sidebar.subheader("❌ Combinações Frias")
        for combo in sistema.combinacoes_frias[:3]:
            dados = sistema.historico_combinacoes.get(combo, {})
            eff = dados.get('eficiencia', 0)
            total = dados.get('total', 0)
            st.sidebar.write(f"🚫 {combo[0]}+{combo[1]}: {eff:.1f}%")

# =============================
# FUNÇÃO PARA VERIFICAR INTEGRIDADE DA SESSÃO
# =============================
def verificar_integridade_sessao():
    """Verifica a integridade dos dados da sessão"""
    problemas = []
    
    # Verificar se o sistema existe
    if 'sistema' not in st.session_state:
        problemas.append("❌ Sistema não encontrado na sessão")
        return False, problemas
    
    sistema = st.session_state.sistema
    
    # Verificar atributos essenciais
    atributos_essenciais = [
        'estrategia_zonas', 'estrategia_midas', 'estrategia_ml',
        'acertos', 'erros', 'historico_desempenho'
    ]
    
    for attr in atributos_essenciais:
        if not hasattr(sistema, attr):
            problemas.append(f"❌ Atributo {attr} não encontrado no sistema")
    
    # Verificar alertas_config
    if 'alertas_config' not in st.session_state:
        problemas.append("❌ alertas_config não encontrado")
        inicializar_config_alertas()
    
    return len(problemas) == 0, problemas

# =============================
# LIMPEZA SEGURA DE SESSÃO
# =============================
def limpar_sessao_confirmada():
    """Limpa todos os dados da sessão com confirmação"""
    try:
        # Guardar apenas alguns dados de configuração
        telegram_token = st.session_state.get('telegram_token', '')
        telegram_chat_id = st.session_state.get('telegram_chat_id', '')
        
        # Limpar session state
        for key in list(st.session_state.keys()):
            if key not in ['telegram_token', 'telegram_chat_id']:
                del st.session_state[key]
        
        # Restaurar configurações
        if telegram_token:
            st.session_state.telegram_token = telegram_token
        if telegram_chat_id:
            st.session_state.telegram_chat_id = telegram_chat_id
        
        # Reinicializar
        inicializar_config_alertas()
        st.session_state.sistema = SistemaRoletaCompleto()
        st.session_state.historico = []
        
        # Remover arquivos
        arquivos = [SESSION_DATA_PATH, HISTORICO_PATH, ML_MODEL_PATH, SCALER_PATH, META_PATH, RL_MODEL_PATH]
        for arquivo in arquivos:
            if os.path.exists(arquivo):
                try:
                    os.remove(arquivo)
                    logging.info(f"🗑️ Removido: {arquivo}")
                except:
                    pass
        
        st.success("✅ Sessão limpa com sucesso! Sistema reinicializado.")
        st.rerun()
        
    except Exception as e:
        logging.error(f"❌ Erro ao limpar sessão: {e}")
        st.error(f"Erro ao limpar sessão: {e}")

# =============================
# APLICAÇÃO STREAMLIT PRINCIPAL
# =============================
st.set_page_config(page_title="IA Roleta — Multi-Estratégias", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias com Aprendizado por Reforço")

# 1. Primeiro inicializar config de alertas
inicializar_config_alertas()

# 2. Tentar carregar sessão salva
sessao_carregada = False
if os.path.exists(SESSION_DATA_PATH):
    try:
        sessao_carregada = carregar_sessao()
        if sessao_carregada:
            st.toast("✅ Sessão carregada com sucesso", icon="✅")
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
        sessao_carregada = False

# 3. Só então inicializar o sistema se necessário
if "sistema" not in st.session_state:
    if sessao_carregada and 'sistema' in st.session_state:
        # Sistema já foi carregado na função carregar_sessao()
        logging.info("✅ Sistema carregado da sessão")
    else:
        st.session_state.sistema = SistemaRoletaCompleto()
        logging.info("🆕 Sistema criado do zero")

if "historico" not in st.session_state:
    if not sessao_carregada and os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            st.session_state.historico = []
    elif not sessao_carregada:
        st.session_state.historico = []

if "telegram_token" not in st.session_state and not sessao_carregada:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state and not sessao_carregada:
    st.session_state.telegram_chat_id = ""

# Verificar integridade da sessão
integridade_ok, problemas = verificar_integridade_sessao()
if not integridade_ok:
    logging.warning(f"Problemas na sessão: {problemas}")
    st.warning("⚠️ Problemas detectados na sessão. Recriando sistema...")
    st.session_state.sistema = SistemaRoletaCompleto()

# Sidebar - Configurações Avançadas
st.sidebar.title("⚙️ Configurações")

# Mostrar combinações dinâmicas
mostrar_combinacoes_dinamicas()

# =============================
# NOVA SEÇÃO: OTIMIZAÇÃO DINÂMICA
# =============================
with st.sidebar.expander("🤖 OTIMIZAÇÃO DINÂMICA 90%", expanded=True):
    st.write("**Sistema de Aprendizado por Reforço**")
    
    if 'sistema' in st.session_state:
        sistema = st.session_state.sistema
        
        if hasattr(sistema, 'sistema_otimizacao'):
            # Botão para gerar relatório
            if st.button("📊 Gerar Relatório de Otimização", use_container_width=True):
                relatorio = sistema.get_relatorio_otimizacao()
                st.text_area("Relatório de Otimização", relatorio, height=400)
            
            # Botão para forçar otimização
            if st.button("🔄 Forçar Otimização Agora", use_container_width=True):
                if sistema.historico_desempenho:
                    # Usar último resultado para otimização
                    ultimo_resultado = sistema.historico_desempenho[-1]
                    otimizacao = sistema.sistema_otimizacao.processar_resultado(ultimo_resultado)
                    
                    if otimizacao:
                        st.success(f"✅ Otimização gerada: {otimizacao['acao']}")
                        if otimizacao.get('combinacao_sugerida'):
                            st.info(f"🎯 Sugestão: {otimizacao['combinacao_sugerida']}")
                    else:
                        st.warning("⚠️ Não foi possível gerar otimização")
            
            # Estatísticas rápidas
            if hasattr(sistema, 'contador_otimizacoes_aplicadas'):
                st.write(f"🔄 **Otimizações aplicadas:** {sistema.contador_otimizacoes_aplicadas}")
            
            # Sugestão automática
            if st.button("💡 Obter Sugestão Inteligente", use_container_width=True):
                if hasattr(sistema.sistema_otimizacao, 'sugerir_melhoria_estrategia'):
                    sugestoes = sistema.sistema_otimizacao.sugerir_melhoria_estrategia(sistema)
                    if sugestoes:
                        st.success("🤖 SUGESTÕES DO SISTEMA AI:")
                        for sugestao in sugestoes:
                            st.write(sugestao)
                    else:
                        st.info("ℹ️  O sistema ainda está aprendendo...")
        
        else:
            st.info("🔧 Sistema de otimização em inicialização...")
    
    st.write("---")
    st.write("**🎯 OBJETIVO: 90% DE ACERTOS**")
    st.write("• 🤖 Aprendizado por Reforço")
    st.write("• 📊 Análise de padrões em tempo real")
    st.write("• 🎯 Otimização dinâmica de combinações")
    st.write("• ⚡ Adaptação automática à mesa")

# Gerenciamento de Sessão
with st.sidebar.expander("💾 Gerenciamento de Sessão", expanded=False):
    st.write("**Persistência de Dados**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salvar Sessão", use_container_width=True):
            salvar_sessao()
            st.success("✅ Sessão salva!")
            
    with col2:
        if st.button("🔄 Carregar Sessão", use_container_width=True):
            if carregar_sessao():
                st.success("✅ Sessão carregada!")
                st.rerun()
            else:
                st.error("❌ Nenhuma sessão salva encontrada")
    
    st.write("---")
    
    st.write("**📊 Gerenciar Estatísticas**")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Estatísticas recentes resetadas!")
            st.rerun()
            
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
            if st.checkbox("Confirmar zerar TODAS as estatísticas"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Todas as estatísticas foram zeradas!")
                st.rerun()
    
    st.write("---")
    
    if st.button("🗑️ Limpar TODOS os Dados", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar limpeza total de todos os dados"):
            limpar_sessao()
            st.error("🗑️ Todos os dados foram limpos!")
            st.stop()

# Configurações dos Alertas - Checkboxes
with st.sidebar.expander("🔔 Configuração de Alertas", expanded=False):
    st.write("**Selecione quais alertas deseja receber:**")
    
    # Usar o estado salvo ou valores padrão
    alertas_config = st.session_state.get('alertas_config', {
        'alertas_previsao': True,
        'alertas_resultado': True,
        'alertas_rotacao': True,
        'alertas_tendencia': True,
        'alertas_treinamento': True,
        'alertas_erros': True,
        'alertas_acertos': True,
        'alertas_estatisticos': True
    })
    
    # Checkboxes individuais
    col1, col2 = st.columns(2)
    
    with col1:
        alertas_previsao = st.checkbox(
            "🎯 Previsões", 
            value=alertas_config.get('alertas_previsao', True),
            help="Alertas de novas previsões"
        )
        
        alertas_resultado = st.checkbox(
            "📊 Resultados", 
            value=alertas_config.get('alertas_resultado', True),
            help="Alertas de resultados dos sorteios"
        )
        
        alertas_rotacao = st.checkbox(
            "🔄 Rotações", 
            value=alertas_config.get('alertas_rotacao', True),
            help="Alertas de rotação automática"
        )
        
        alertas_tendencia = st.checkbox(
            "📈 Tendências", 
            value=alertas_config.get('alertas_tendencia', True),
            help="Alertas de mudança de tendência"
        )
    
    with col2:
        alertas_treinamento = st.checkbox(
            "🧠 Treinamentos", 
            value=alertas_config.get('alertas_treinamento', True),
            help="Alertas de treinamento ML"
        )
        
        alertas_acertos = st.checkbox(
            "✅ Acertos", 
            value=alertas_config.get('alertas_acertos', True),
            help="Alertas quando acertar"
        )
        
        alertas_erros = st.checkbox(
            "❌ Erros", 
            value=alertas_config.get('alertas_erros', True),
            help="Alertas quando errar"
        )
        
        alertas_estatisticos = st.checkbox(
            "📊 Estatísticos", 
            value=alertas_config.get('alertas_estatisticos', True),
            help="Alertas de análise estatística"
        )
    
    # Botões para seleção rápida
    st.write("**Seleção Rápida:**")
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("✅ Todos", use_container_width=True):
            st.session_state.alertas_config = {
                'alertas_previsao': True,
                'alertas_resultado': True,
                'alertas_rotacao': True,
                'alertas_tendencia': True,
                'alertas_treinamento': True,
                'alertas_erros': True,
                'alertas_acertos': True,
                'alertas_estatisticos': True
            }
            st.success("✅ Todos os alertas ativados!")
            st.rerun()
    
    with col_btn2:
        if st.button("❌ Nenhum", use_container_width=True):
            st.session_state.alertas_config = {
                'alertas_previsao': False,
                'alertas_resultado': False,
                'alertas_rotacao': False,
                'alertas_tendencia': False,
                'alertas_treinamento': False,
                'alertas_erros': False,
                'alertas_acertos': False,
                'alertas_estatisticos': False
            }
            st.warning("❌ Todos os alertas desativados!")
            st.rerun()
    
    with col_btn3:
        if st.button("💾 Salvar", use_container_width=True):
            # Atualizar configurações
            st.session_state.alertas_config = {
                'alertas_previsao': alertas_previsao,
                'alertas_resultado': alertas_resultado,
                'alertas_rotacao': alertas_rotacao,
                'alertas_tendencia': alertas_tendencia,
                'alertas_treinamento': alertas_treinamento,
                'alertas_erros': alertas_erros,
                'alertas_acertos': alertas_acertos,
                'alertas_estatisticos': alertas_estatisticos
            }
            
            # Salvar na sessão
            salvar_sessao()
            st.success("✅ Configurações de alertas salvas!")

# Configurações do Telegram
with st.sidebar.expander("🔔 Configurações do Telegram", expanded=False):
    st.write("Configure as notificações do Telegram")
    
    telegram_token = st.text_input(
        "Bot Token do Telegram:",
        value=st.session_state.telegram_token,
        type="password",
        help="Obtenha com @BotFather no Telegram"
    )
    
    telegram_chat_id = st.text_input(
        "Chat ID do Telegram:",
        value=st.session_state.telegram_chat_id,
        help="Obtenha com @userinfobot no Telegram"
    )
    
    if st.button("Salvar Configurações Telegram"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Configurações do Telegram salvas!")
        
    if st.button("Testar Conexão Telegram"):
        if telegram_token and telegram_chat_id:
            try:
                enviar_telegram("🔔 Teste de conexão - IA Roleta funcionando!")
                st.success("✅ Mensagem de teste enviada para Telegram!")
            except Exception as e:
                st.error(f"❌ Erro ao enviar mensagem: {e}")
        else:
            st.error("❌ Preencha token e chat ID primeiro")

# Configurações dos Alertas Alternativos
with st.sidebar.expander("🔔 Alertas Alternativos", expanded=False):
    st.write("**Alertas Simplificados do Telegram**")
    
    st.info("""
    **📱 Alertas Ativados:**
    - 🔔 **Alerta de Aposta:** Números em 2 linhas
    - 📢 **Alerta de Resultado:** Confirmação simples
    - 🎯 **Previsão Detalhada:** Mensagem completa
    """)
    
    alertas_alternativos = st.checkbox(
        "Ativar Alertas Simplificados", 
        value=True,
        help="Envia alertas super simples junto com os detalhados"
    )
    
    if not alertas_alternativos:
        st.warning("⚠️ Alertas simplificados desativados")
    
    if st.button("Testar Alertas Simplificados"):
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            previsao_teste = {
                'nome': 'Zonas Teste',
                'numeros_apostar': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                'zonas_envolvidas': ['Vermelha']
            }
            
            try:
                enviar_alerta_numeros_simplificado(previsao_teste)
                st.success("✅ Alerta simplificado de teste enviado!")
            except Exception as e:
                st.error(f"❌ Erro: {e}")
        else:
            st.error("❌ Configure o Telegram primeiro")

# Seleção de Estratégia
estrategia = st.sidebar.selectbox(
    "🎯 Selecione a Estratégia:",
    ["Zonas", "Midas", "ML"],
    key="estrategia_selecionada"
)

# Aplicar estratégia selecionada
if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)
    st.toast(f"🔄 Estratégia alterada para: {estrategia}")

# Status da Rotação Automática
with st.sidebar.expander("🔄 Rotação Automática", expanded=True):
    status_rotacao = st.session_state.sistema.get_status_rotacao()
    
    st.write("**Sistema de Rotação:**")
    st.write(f"🎯 **Estratégia Atual:** {status_rotacao['estrategia_atual']}")
    st.write(f"✅ **Acertos Seguidos:** {status_rotacao['sequencia_acertos']}/3")
    st.write(f"❌ **Erros Seguidos:** {status_rotacao['sequencia_erros']}/2")
    st.write(f"🔥 **Combinações Quentes:** {status_rotacao['combinacoes_quentes']}")
    st.write(f"❄️ **Combinações Frias:** {status_rotacao['combinacoes_frias']}")
    
    if status_rotacao['ultimas_combinacoes_acerto']:
        st.write(f"📊 **Últimas Combinações que Acertaram:**")
        for combo in status_rotacao['ultimas_combinacoes_acerto']:
            nucleos = []
            for zona in combo:
                if zona == 'Vermelha': nucleos.append("7")
                elif zona == 'Azul': nucleos.append("10")
                elif zona == 'Amarela': nucleos.append("2")
                else: nucleos.append(zona)
            st.write(f"   • {'+'.join(nucleos)}")
    
    st.write("---")
    st.write("**🎯 NOVAS Regras de Rotação:**")
    st.write("• 🚨 **QUALQUER combinação com 2 erros seguidos:** Troca para outra combinação")
    st.write("• ✅ **3 Acertos Seguidos na MESMA combinação:** Rota para OUTRAS combinações")
    st.write("• 🔄 **Combinações disponíveis:** Vermelho+Azul, Vermelho+Amarelo, Azul+Amarelo")
    
    # Botão para forçar rotação manual
    if st.button("🔄 Forçar Rotação", use_container_width=True):
        estrategia_atual = st.session_state.sistema.estrategia_selecionada
        if estrategia_atual == "Zonas":
            nova_estrategia = "ML"
        else:
            nova_estrategia = "Zonas"
        
        st.session_state.sistema.estrategia_selecionada = nova_estrategia
        st.session_state.sistema.sequencia_erros = 0
        st.session_state.sistema.sequencia_acertos = 0
        st.success(f"🔄 Rotação forçada: {estrategia_atual} → {nova_estrategia}")
        st.rerun()
    
    # Debug da Rotação
    with st.sidebar.expander("🐛 Debug - Rotação", expanded=False):
        if st.button("🔍 Ver Debug Rotação"):
            debug_info = st.session_state.sistema.get_debug_rotacao()
            st.json(debug_info)
        
        if st.button("📋 Log Rotação", use_container_width=True):
            # Mostrar últimas 5 rotações
            rotacoes = []
            for i, resultado in enumerate(st.session_state.sistema.historico_desempenho[-10:]):
                if resultado.get('rotacionou', False):
                    rotacoes.append(f"Rodada {len(st.session_state.sistema.historico_desempenho)-i}: {resultado}")
            
            if rotacoes:
                st.write("Últimas rotações:")
                for rotacao in rotacoes[-5:]:
                    st.write(rotacao)
            else:
                st.write("Nenhuma rotação recente registrada")

# Treinamento ML
with st.sidebar.expander("🧠 Treinamento ML", expanded=False):
    numeros_disponiveis = 0
    numeros_lista = []
    
    for item in st.session_state.historico:
        if isinstance(item, dict) and 'number' in item and item['number'] is not None:
            numeros_disponiveis += 1
            numeros_lista.append(item['number'])
        elif isinstance(item, (int, float)) and item is not None:
            numeros_disponiveis += 1
            numeros_lista.append(int(item))
            
    st.write(f"📊 **Números disponíveis:** {numeros_disponiveis}")
    st.write(f"🎯 **Mínimo necessário:** 500 números")
    st.write(f"🔄 **Treinamento automático:** A cada 15 sorteios")
    st.write(f"🤖 **Modelo:** CatBoost CORRIGIDO")
    st.write(f"🎯 **Features:** Específicas para roleta")
    st.write(f"🎯 **Estratégia:** Previsão de ZONAS")
    
    if numeros_disponiveis > 0:
        numeros_unicos = len(set(numeros_lista))
        st.write(f"🎲 **Números únicos:** {numeros_unicos}/37")
        
        if numeros_unicos < 10:
            st.warning(f"⚠️ **Pouca variedade:** Necessário pelo menos 10 números diferentes")
        else:
            st.success(f"✅ **Variedade adequada:** {numeros_unicos} números diferentes")
    
    st.write(f"✅ **Status:** {'Dados suficientes' if numeros_disponiveis >= 500 else 'Coletando dados...'}")
    
    if numeros_disponiveis >= 500:
        st.success("✨ **Pronto para treinar!**")
        
        if st.button("🚀 Treinar Modelo ML CORRIGIDO", type="primary", use_container_width=True):
            with st.spinner("Treinando modelo ML CORRIGIDO... Isso pode levar alguns segundos"):
                try:
                    success, message = st.session_state.sistema.treinar_modelo_ml(numeros_lista)
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                    else:
                        st.error(f"❌ {message}")
                except Exception as e:
                    st.error(f"💥 Erro no treinamento: {str(e)}")
    
    else:
        st.warning(f"📥 Colete mais {500 - numeros_disponiveis} números para treinar o ML CORRIGIDO")
        
    st.write("---")
    st.write("**Status do ML CORRIGIDO:**")
    if st.session_state.sistema.estrategia_ml.ml.is_trained:
        modelo_tipo = st.session_state.sistema.estrategia_ml.ml.meta.get('model_name', 'Não identificado')
            
        st.success(f"✅ Modelo {modelo_tipo} treinado ({st.session_state.sistema.estrategia_ml.ml.contador_treinamento} vezes)")
        if 'last_accuracy' in st.session_state.sistema.estrategia_ml.ml.meta:
            acc = st.session_state.sistema.estrategia_ml.ml.meta['last_accuracy']
            st.info(f"📊 Última acurácia: {acc:.2%}")
        st.info(f"🔄 Próximo treinamento automático em: {15 - st.session_state.sistema.estrategia_ml.contador_sorteios} sorteios")
        st.info(f"🎯 Estratégia: Previsão de ZONAS")
    else:
        st.info("🤖 ML aguardando treinamento CORRIGIDO (mínimo 500 números)")

# Estatísticas de Padrões ML
with st.sidebar.expander("🔍 Estatísticas de Padrões ML", expanded=False):
    if st.session_state.sistema.estrategia_selecionada == "ML":
        estatisticas_padroes = st.session_state.sistema.estrategia_ml.get_estatisticas_padroes()
        st.text(estatisticas_padroes)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("🔄 Zerar Padrões", use_container_width=True):
                st.session_state.sistema.estrategia_ml.zerar_padroes()
                st.success("✅ Padrões zerados!")
                st.rerun()
                
        with col_p2:
            if st.button("📊 Atualizar Métricas", use_container_width=True):
                st.rerun()
    else:
        st.info("🔍 Ative a estratégia ML para ver estatísticas de padrões")

# Informações sobre as Estratégias
with st.sidebar.expander("📊 Informações das Estratégias"):
    if estrategia == "Zonas":
        info_zonas = st.session_state.sistema.estrategia_zonas.get_info_zonas()
        st.write("**🎯 Estratégia Zonas v6:**")
        st.write("**CONFIGURAÇÃO:** 6 antes + 6 depois (13 números/zona)")
        st.write("**OTIMIZAÇÕES:**")
        st.write("- 📊 Histórico: 70 números")
        st.write("- 🎯 Múltiplas janelas: Curto(12) Médio(24) Longo(48)")
        st.write("- 📈 Threshold dinâmico por performance")
        st.write("- 🔄 **APRENDIZADO DINÂMICO:** Combinações que funcionam no momento")
        st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 10 números selecionados automaticamente")
        st.write("- 🚨 **REGRA UNIVERSAL:** Qualquer combinação com 2 erros seguidos → Troca imediata")
        for zona, dados in info_zonas.items():
            st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
            st.write(f"Descrição: {dados['descricao']}")
            st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
            st.write(f"Total: {dados['quantidade']} números")
            st.write("---")
    
    elif estrategia == "Midas":
        st.write("**🎯 Estratégia Midas:**")
        st.write("Padrões baseados em terminais:")
        st.write("- **Terminal 0**: 0, 10, 20, 30")
        st.write("- **Terminal 7**: 7, 17, 27") 
        st.write("- **Terminal 5**: 5, 15, 25, 35")
        st.write("---")
    
    elif estrategia == "ML":
        st.write("**🤖 Estratégia Machine Learning - CATBOOT CORRIGIDO:**")
        st.write("- **Modelo**: CatBoost com configuração otimizada")
        st.write("- **Amostras mínimas**: 500 números")
        st.write("- **Features**: Específicas para roleta (cores, dezenas, colunas, etc)")
        st.write("- **Treinamento**: A cada 15 sorteios")
        st.write("- **Estratégia**: PREVISÃO DE ZONAS, não números específicos")
        st.write("- **Zonas**: 6 antes + 6 depois (13 números/zona)")
        st.write("- **Saída**: 2 zonas com maior probabilidade")
        st.write("- 🔄 **APRENDIZADO DINÂMICO:** Combinações que funcionam no momento")
        st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 10 números selecionados automaticamente")
        
        info_zonas_ml = st.session_state.sistema.estrategia_ml.get_info_zonas_ml()
        for zona, dados in info_zonas_ml.items():
            st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
            st.write(f"Descrição: {dados['descricao']}")
            st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
            st.write(f"Total: {dados['quantidade']} números")
            st.write("---")

# Análise detalhada
with st.sidebar.expander(f"🔍 Análise - {estrategia}", expanded=False):
    if estrategia == "Zonas":
        analise = st.session_state.sistema.estrategia_zonas.get_analise_detalhada()
    elif estrategia == "ML":
        analise = st.session_state.sistema.estrategia_ml.get_analise_ml()
    else:
        analise = "🎯 Estratégia Midas ativa\nAnalisando padrões de terminais..."
    
    st.text(analise)

# Entrada manual
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Digite números (0-36) separados por espaço:")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(n)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# Atualização automática
st_autorefresh(interval=3000, key="refresh")

# Buscar resultado da API
resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else:
    ultimo_ts = None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    numero_atual = resultado.get("number")
    if numero_atual is not None:
        st.session_state.historico.append(resultado)
        st.session_state.sistema.processar_novo_numero(resultado)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

# Interface principal
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(numeros_str)
else:
    st.write("Nenhum número registrado")

# Status da Rotação na Interface Principal
status_rotacao = st.session_state.sistema.get_status_rotacao()
col_status1, col_status2, col_status3, col_status4 = st.columns(4)
with col_status1:
    st.metric("🎯 Estratégia Atual", status_rotacao['estrategia_atual'])
with col_status2:
    st.metric("✅ Acertos Seguidos", f"{status_rotacao['sequencia_acertos']}/3")
with col_status3:
    st.metric("❌ Erros Seguidos", f"{status_rotacao['sequencia_erros']}/2")
with col_status4:
    st.metric("🔄 Próxima Rotação", f"A:{status_rotacao['proxima_rotacao_acertos']} E:{status_rotacao['proxima_rotacao_erros']}")

# NOVA SEÇÃO: ANÁLISE DE TENDÊNCIAS
st.subheader("📈 Análise de Tendências")

tendencia_analise = st.session_state.sistema.get_analise_tendencias_completa()
st.text_area("Estado da Tendência", tendencia_analise, height=400, key="tendencia_analise")

col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.button("🔄 Atualizar Análise de Tendência", use_container_width=True):
        zonas_rankeadas = st.session_state.sistema.estrategia_zonas.get_zonas_rankeadas()
        if zonas_rankeadas:
            analise = st.session_state.sistema.sistema_tendencias.analisar_tendencia(zonas_rankeadas)
            st.success(f"Análise atualizada: {analise['mensagem']}")
            st.rerun()

with col_t2:
    if st.button("📊 Detalhes da Tendência", use_container_width=True):
        resumo = st.session_state.sistema.sistema_tendencias.get_resumo_tendencia()
        st.write("**📊 Detalhes da Tendência:**")
        st.json(resumo)

# ALERTAS VISUAIS DE TENDÊNCIA
if (st.session_state.sistema.sistema_tendencias.historico_tendencias and 
    len(st.session_state.sistema.sistema_tendencias.historico_tendencias) > 0):
    
    ultima_analise = st.session_state.sistema.sistema_tendencias.historico_tendencias[-1]
    
    if ultima_analise['estado'] in ['ativa', 'enfraquecendo', 'morta']:
        enviar_alerta_tendencia(ultima_analise)

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if previsao.get('selecao_inteligente', False):
        st.success("🎯 **SELEÇÃO INTELIGENTE ATIVA** - 10 melhores números selecionados")
        st.info("📊 **Critérios:** Frequência + Posição + Vizinhança + Tendência")
    
    if 'Zonas' in previsao['nome']:
        zonas_envolvidas = previsao.get('zonas_envolvidas', [])
        if len(zonas_envolvidas) > 1:
            zona1 = zonas_envolvidas[0]
            zona2 = zonas_envolvidas[1]
            
            nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
            nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
            
            st.write(f"**📍 Núcleos Combinados:** {nucleo1} + {nucleo2}")
            
            combinacao = tuple(sorted([zona1, zona2]))
            dados_combinacao = sistema.historico_combinacoes.get(combinacao, {})
            if dados_combinacao:
                eff = dados_combinacao.get('eficiencia', 0)
                total = dados_combinacao.get('total', 0)
                st.info(f"🏆 **Eficiência da Combinação:** {eff:.1f}% ({dados_combinacao.get('acertos', 0)}/{total})")
            
            st.info("🔄 **ESTRATÉGIA DUPLA:** Investindo nas 2 melhores zonas")
        else:
            zona = previsao.get('zona', '')
            if zona == 'Vermelha':
                nucleo = "7"
            elif zona == 'Azul':
                nucleo = "10"
            elif zona == 'Amarela':
                nucleo = "2"
            else:
                nucleo = zona
            st.write(f"**📍 Núcleo:** {nucleo}")
            
    elif 'ML' in previsao['nome']:
        zonas_envolvidas = previsao.get('zonas_envolvidas', [])
        if len(zonas_envolvidas) > 1:
            zona1 = zonas_envolvidas[0]
            zona2 = zonas_envolvidas[1]
            
            nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
            nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
            
            st.write(f"**🤖 Núcleos Combinados (ML):** {nucleo1} + {nucleo2}")
            st.info("🔄 **ESTRATÉGIA DUPLA:** Previsão ML baseada em probabilidade de zonas")
        else:
            zona_ml = previsao.get('zonas_envolvidas', [''])[0]
            if zona_ml == 'Vermelha':
                nucleo = "7"
            elif zona_ml == 'Azul':
                nucleo = "10"
            elif zona_ml == 'Amarela':
                nucleo = "2"
            else:
                nucleo = zona_ml
            st.write(f"**🤖 Núcleo (ML):** {nucleo}")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    st.write(", ".join(map(str, sorted(previsao['numeros_apostar']))))
    
    if 'ML' in previsao['nome'] and previsao.get('padroes_aplicados', 0) > 0:
        st.info(f"🔍 **Padrões aplicados:** {previsao['padroes_aplicados']} padrões sequenciais detectados")
    
    tipo_aposta = previsao.get('tipo', 'unica')
    if tipo_aposta == 'dupla':
        st.success("🎯 **APOSTA DUPLA:** Maior cobertura com 2 zonas combinadas")
    else:
        st.info("🎯 **APOSTA SIMPLES:** Foco em uma zona principal")
    
    st.info("⏳ Aguardando próximo sorteio para conferência...")
else:
    st.info(f"🎲 Analisando padrões ({estrategia})...")

# Desempenho
st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
if total > 0:
    taxa = (sistema.acertos / total * 100)
else:
    taxa = 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

# Botões de gerenciamento de estatísticas
st.write("**Gerenciar Estatísticas:**")
col5, col6 = st.columns(2)

with col5:
    if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
        st.session_state.sistema.reset_recente_estatisticas()
        st.success("✅ Estatísticas recentes resetadas!")
        st.rerun()

with col6:
    if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
        if st.checkbox("Confirmar zerar TODAS as estatísticas"):
            st.session_state.sistema.zerar_estatisticas_desempenho()
            st.error("🗑️ Todas as estatísticas foram zeradas!")
            st.rerun()

# Análise detalhada por estratégia
if sistema.estrategias_contador:
    st.write("**📊 Performance por Estratégia:**")
    for nome, dados in sistema.estrategias_contador.items():
        if isinstance(dados, dict) and 'total' in dados and dados['total'] > 0:
            taxa_estrategia = (dados['acertos'] / dados['total'] * 100)
            cor = "🟢" if taxa_estrategia >= 50 else "🟡" if taxa_estrategia >= 30 else "🔴"
            st.write(f"{cor} {nome}: {dados['acertos']}/{dados['total']} ({taxa_estrategia:.1f}%)")
        else:
            st.write(f"⚠️ {nome}: Dados de performance não disponíveis")

# Últimas conferências
if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for i, resultado in enumerate(sistema.historico_desempenho[-5:]):
        emoji = "🎉" if resultado['acerto'] else "❌"
        rotacao_emoji = " 🔄" if resultado.get('rotacionou', False) else ""
        zona_info = ""
        if resultado['acerto'] and resultado.get('zona_acertada'):
            if '+' in resultado['zona_acertada']:
                zonas = resultado['zona_acertada'].split('+')
                nucleos = []
                for zona in zonas:
                    if zona == 'Vermelha':
                        nucleos.append("7")
                    elif zona == 'Azul':
                        nucleos.append("10")
                    elif zona == 'Amarela':
                        nucleos.append("2")
                    else:
                        nucleos.append(zona)
                nucleo_str = "+".join(nucleos)
                zona_info = f" (Núcleos {nucleo_str})"
            else:
                if resultado['zona_acertada'] == 'Vermelha':
                    nucleo = "7"
                elif resultado['zona_acertada'] == 'Azul':
                    nucleo = "10"
                elif resultado['zona_acertada'] == 'Amarela':
                    nucleo = "2"
                else:
                    nucleo = resultado['zona_acertada']
                zona_info = f" (Núcleo {nucleo})"
                
        tipo_aposta_info = ""
        if resultado.get('tipo_aposta') == 'dupla':
            tipo_aposta_info = " [DUPLA]"
        
        st.write(f"{emoji}{rotacao_emoji} {resultado['estrategia']}{tipo_aposta_info}: Número {resultado['numero']}{zona_info}")

# Download histórico
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_roleta.json")

# ✅ CORREÇÃO FINAL: Salvar sessão
salvar_sessao()
